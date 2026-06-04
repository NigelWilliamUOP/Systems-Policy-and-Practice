"""Discussion feed routes — community conversation."""
import re
from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from models.database import get_db
from models.discussion import DiscussionPost, DiscussionComment, DiscussionCommentVote, DiscussionVote, UserFollow
from models.prompt import CommunityPrompt
from models.user import User
from datetime import datetime
from services.notification import create_notification
from routes.shared import (
    require_auth, get_templates, toggle_vote, delete_owned_entity,
    build_preview_comments, load_user_votes,
)

router = APIRouter(tags=["discussion"])
templates = get_templates()


@router.post("/discussion/summarize", response_class=HTMLResponse)
async def summarize_discussion_feed(
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate AI summary of the discussion feed."""
    from services.summarizer import summarize_discussion
    from models.discussion import DiscussionPost
    posts = db.query(DiscussionPost).order_by(DiscussionPost.created_at.desc()).limit(50).all()
    if not posts:
        return HTMLResponse('<p class="text-sm text-slate-500 italic">No discussion posts to summarize.</p>')
    count = len(posts)
    combined = "\n---\n".join(p.content[:200] for p in posts)
    try:
        summary = await summarize_discussion(combined, count)
    except Exception as e:
        return HTMLResponse(f'<p class="text-sm text-red-500">Summarization failed: {e}</p>')
    from fastapi.templating import Jinja2Templates
    tpl = Jinja2Templates(directory="templates")
    return tpl.TemplateResponse(
        "components/summary_card.html",
        {"request": request, "summary": summary, "count": count, "label": "posts"},
    )


@router.get("/discussion", response_class=HTMLResponse)
async def discussion_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Discussion feed — initial page load."""
    user = request.session.get("user")

    posts = (
        db.query(DiscussionPost)
        .order_by(DiscussionPost.created_at.desc())
        .limit(20)
        .all()
    )

    user_votes = load_user_votes(
        db=db, vote_model=DiscussionVote,
        parent_id_field="post_id",
        parent_ids=[p.id for p in posts],
        user_id=user["id"],
    ) if user else {}

    newest_id = posts[0].id if posts else 0
    oldest_id = posts[-1].id if posts else 0
    has_more = len(posts) == 20

    preview_comments = build_preview_comments(posts)

    return templates.TemplateResponse(
        "discussion.html",
        {
            "request": request,
            "user": user,
            "posts": posts,
            "user_votes": user_votes,
            "preview_comments": preview_comments,
            "newest_id": newest_id,
            "oldest_id": oldest_id,
            "has_more": has_more,
        },
    )


@router.get("/discussion/feed", response_class=HTMLResponse)
async def discussion_feed(
    request: Request,
    before_id: int = Query(None),
    after_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """Cursor-based feed endpoint. Returns HTML fragments.

    before_id: load older posts (infinite scroll)
    after_id: load newer posts (polling for new content)
    """
    user = request.session.get("user")
    query = db.query(DiscussionPost)

    if before_id:
        query = query.filter(DiscussionPost.id < before_id)
    elif after_id:
        query = query.filter(DiscussionPost.id > after_id)

    posts = query.order_by(DiscussionPost.created_at.desc()).limit(20).all()

    user_votes = load_user_votes(
        db=db, vote_model=DiscussionVote,
        parent_id_field="post_id",
        parent_ids=[p.id for p in posts],
        user_id=user["id"],
    ) if user else {}

    preview_comments = build_preview_comments(posts)

    # Return just the card fragments
    html_parts = []
    for post in posts:
        html_parts.append(
            templates.get_template("components/discussion_card.html").render(
                post=post, user=user, user_votes=user_votes, is_new=False,
                request=request, preview_comments=preview_comments
            )
        )
    return HTMLResponse("".join(html_parts))


@router.get("/discussion/feed/count")
async def discussion_feed_count(
    after_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Return count of new posts since after_id (for polling)."""
    count = db.query(DiscussionPost).filter(DiscussionPost.id > after_id).count()
    return JSONResponse({"count": count})


@router.post("/discussion/post", response_class=HTMLResponse)
async def create_post(
    request: Request,
    content: str = Form(...),
    prompt_id: int = Form(None),
    db: Session = Depends(get_db),
):
    """Create a new discussion post."""
    user = require_auth(request)
    content = content.strip()

    if not content or len(content) < 10:
        raise HTTPException(status_code=400, detail="Post must be at least 10 characters")
    if len(content) > 5000:
        raise HTTPException(status_code=400, detail="Post must be 5000 characters or fewer")

    # Validate prompt_id if provided
    if prompt_id:
        prompt = db.query(CommunityPrompt).filter(CommunityPrompt.id == prompt_id).first()
        if not prompt:
            prompt_id = None

    # Auto-detect prompt references like /prompts/123 or #prompt-123
    if not prompt_id:
        match = re.search(r'/prompts/(\d+)|#prompt-(\d+)', content)
        if match:
            ref_id = int(match.group(1) or match.group(2))
            if db.query(CommunityPrompt).filter(CommunityPrompt.id == ref_id).first():
                prompt_id = ref_id

    post = DiscussionPost(
        user_id=user["id"],
        content=content,
        prompt_id=prompt_id,
        created_at=datetime.utcnow(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return templates.TemplateResponse(
        "components/discussion_card.html",
        {
            "request": request,
            "post": post,
            "user": user,
            "user_votes": {},
            "preview_comments": {},
            "is_new": True,
        },
    )


@router.post("/discussion/{post_id}/vote")
async def vote_post(
    post_id: int,
    request: Request,
    vote_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """Vote on a discussion post."""
    user = require_auth(request)

    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    toggled_off = toggle_vote(
        db=db,
        vote_model=DiscussionVote,
        parent_id_field="post_id",
        parent_id_value=post_id,
        user_id=user["id"],
        vote_type=vote_type,
    )

    db.commit()
    db.refresh(post)

    if not toggled_off:
        create_notification(
            user_id=post.user_id, notification_type="discussion_vote",
            link=f"/discussion#disc-post-{post_id}", db=db,
            source_user_id=user["id"],
            content_preview=f"{'liked' if vote_type == 'upvote' else 'disliked'} your post",
        )
        db.commit()

    current_vote = db.query(DiscussionVote).filter(
        DiscussionVote.post_id == post_id,
        DiscussionVote.user_id == user["id"],
    ).first()

    return JSONResponse({
        "success": True,
        "upvotes": post.upvote_count,
        "downvotes": post.downvote_count,
        "net_votes": post.net_votes,
        "user_vote": current_vote.vote_type if current_vote else None,
    })


@router.post("/discussion/{post_id}/comment", response_class=HTMLResponse)
async def add_comment(
    post_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    """Add a comment to a discussion post."""
    user = require_auth(request)
    content = content.strip()

    if not content or len(content) < 2:
        raise HTTPException(status_code=400, detail="Comment too short")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="Comment must be 2000 characters or fewer")

    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = DiscussionComment(
        post_id=post_id,
        user_id=user["id"],
        content=content,
        created_at=datetime.utcnow(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Notify post author
    create_notification(
        user_id=post.user_id, notification_type="discussion_comment",
        link=f"/discussion#disc-post-{post_id}", db=db,
        source_user_id=user["id"], content_preview=content[:150],
    )
    db.commit()

    return templates.TemplateResponse(
        "components/discussion_comment.html",
        {"request": request, "comment": comment, "user": user, "comment_votes": {}, "is_new": True},
    )


@router.get("/discussion/{post_id}/comments", response_class=HTMLResponse)
async def get_comments(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get all comments for a post (loaded via HTMX)."""
    user = request.session.get("user")
    post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Get user votes on comments
    comment_votes = load_user_votes(
        db=db, vote_model=DiscussionCommentVote,
        parent_id_field="comment_id",
        parent_ids=[c.id for c in post.comments],
        user_id=user["id"],
    ) if user else {}

    return templates.TemplateResponse(
        "components/discussion_comments_list.html",
        {"request": request, "post": post, "user": user, "comment_votes": comment_votes},
    )


@router.post("/discussion/comment/{comment_id}/vote")
async def vote_discussion_comment(
    comment_id: int,
    request: Request,
    vote_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """Vote on a discussion comment."""
    user = require_auth(request)
    comment = db.query(DiscussionComment).filter(DiscussionComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404)
    toggled_off = toggle_vote(
        db=db,
        vote_model=DiscussionCommentVote,
        parent_id_field="comment_id",
        parent_id_value=comment_id,
        user_id=user["id"],
        vote_type=vote_type,
    )

    db.commit()
    db.refresh(comment)

    if not toggled_off:
        create_notification(
            user_id=comment.user_id, notification_type="discussion_comment_vote",
            link=f"/discussion#dcomment-{comment_id}", db=db,
            source_user_id=user["id"],
            content_preview=f"{'liked' if vote_type == 'upvote' else 'disliked'} your comment",
        )
        db.commit()

    cv = db.query(DiscussionCommentVote).filter(
        DiscussionCommentVote.comment_id == comment_id,
        DiscussionCommentVote.user_id == user["id"],
    ).first()

    return JSONResponse({
        "success": True, "net_votes": comment.net_votes,
        "upvotes": comment.upvote_count, "downvotes": comment.downvote_count,
        "user_vote": cv.vote_type if cv else None,
    })


@router.post("/discussion/{post_id}/delete")
async def delete_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a discussion post (author only)."""
    user = require_auth(request)
    return delete_owned_entity(
        db=db, model=DiscussionPost, entity_id=post_id,
        user_id=user["id"],
        not_found_detail="Post not found",
        forbidden_detail="Only the author can delete this post",
    )


@router.post("/discussion/comment/{comment_id}/delete")
async def delete_discussion_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a discussion comment (author only)."""
    user = require_auth(request)
    return delete_owned_entity(
        db=db, model=DiscussionComment, entity_id=comment_id,
        user_id=user["id"],
        not_found_detail="Comment not found",
        forbidden_detail="Only the author can delete this comment",
    )


@router.post("/user/{user_id}/follow")
async def follow_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Follow or unfollow a user."""
    current_user = require_auth(request)

    if current_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(UserFollow).filter(
        UserFollow.follower_id == current_user["id"],
        UserFollow.followed_id == user_id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        following = False
    else:
        follow = UserFollow(
            follower_id=current_user["id"],
            followed_id=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(follow)
        db.commit()
        following = True

    follower_count = db.query(UserFollow).filter(UserFollow.followed_id == user_id).count()

    return JSONResponse({
        "success": True,
        "following": following,
        "follower_count": follower_count,
    })
