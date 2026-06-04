"""Shared route utilities — auth helpers, template setup, vote/delete/follow logic."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from template_helpers import register_filters


# ── Jinja2 template singleton ───────────────────────────────────────────────
_templates = None


def get_templates() -> Jinja2Templates:
    """Return a shared, filter-registered Jinja2Templates instance."""
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory="templates")
        _templates.env = register_filters(_templates.env)
    return _templates


# ── Authentication helpers ──────────────────────────────────────────────────

def require_auth(request: Request) -> dict:
    """Require an authenticated session; raise 401 otherwise."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_session_user(request: Request):
    """Return the session user dict or ``None``."""
    return request.session.get("user")


# ── Generic vote toggle ────────────────────────────────────────────────────

def toggle_vote(
    *,
    db: Session,
    vote_model,
    parent_id_field: str,
    parent_id_value: int,
    user_id: int,
    vote_type: str,
):
    """Toggle an upvote/downvote on any votable entity.

    Returns ``(toggled_off: bool)``.
    """
    if vote_type not in ("upvote", "downvote"):
        raise HTTPException(status_code=400, detail="Invalid vote type")

    filter_kwargs = {parent_id_field: parent_id_value, "user_id": user_id}
    existing = db.query(vote_model).filter_by(**filter_kwargs).first()

    toggled_off = False
    if existing:
        if existing.vote_type == vote_type:
            db.delete(existing)
            toggled_off = True
        else:
            existing.vote_type = vote_type
    else:
        new_vote = vote_model(
            **{parent_id_field: parent_id_value},
            user_id=user_id,
            vote_type=vote_type,
            created_at=datetime.utcnow(),
        )
        db.add(new_vote)

    return toggled_off


# ── Author-only delete ─────────────────────────────────────────────────────

def delete_owned_entity(
    *,
    db: Session,
    model,
    entity_id: int,
    user_id: int,
    not_found_detail: str = "Not found",
    forbidden_detail: str = "Only the author can delete this",
):
    """Delete a record only if the requesting user owns it.

    Returns a ``JSONResponse({"success": True})``.
    """
    entity = db.query(model).filter(model.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=not_found_detail)
    if entity.user_id != user_id:
        raise HTTPException(status_code=403, detail=forbidden_detail)
    db.delete(entity)
    db.commit()
    return JSONResponse({"success": True})


# ── Paper version lookup ───────────────────────────────────────────────────

def get_paper_and_version(paper_id: int, version: int | None, db: Session):
    """Fetch a Paper and its PaperVersion.

    Returns ``(paper, paper_version, resolved_version_number)``.
    Raises 404 if the paper or version does not exist.
    """
    from models.paper import Paper, PaperVersion

    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    v = version if version else paper.current_version
    paper_version = db.query(PaperVersion).filter(
        PaperVersion.paper_id == paper_id,
        PaperVersion.version_number == v,
    ).first()

    if not paper_version:
        raise HTTPException(status_code=404, detail="Paper version not found")

    return paper, paper_version, v


# ── Follow-set loader ──────────────────────────────────────────────────────

def get_user_following(user: dict | None, db: Session) -> set[int]:
    """Return the set of user IDs the current user follows."""
    if not user:
        return set()
    from models.discussion import UserFollow
    rows = db.query(UserFollow.followed_id).filter(
        UserFollow.follower_id == user["id"],
    ).all()
    return {r[0] for r in rows}


# ── Preview comments ────────────────────────────────────────────────────────

def build_preview_comments(posts) -> dict:
    """Pick the top comment per post for feed preview cards."""
    return {
        p.id: max(p.comments, key=lambda c: (c.net_votes, -c.created_at.timestamp()))
        for p in posts
        if p.comments
    }


# ── User votes loader ──────────────────────────────────────────────────────

def load_user_votes(
    *,
    db: Session,
    vote_model,
    parent_id_field: str,
    parent_ids: list[int],
    user_id: int,
) -> dict[int, str]:
    """Batch-load a user's votes for a list of parent entity IDs.

    Returns ``{parent_id: vote_type}`` mapping.
    """
    if not parent_ids:
        return {}
    parent_col = getattr(vote_model, parent_id_field)
    votes = db.query(vote_model).filter(
        parent_col.in_(parent_ids),
        vote_model.user_id == user_id,
    ).all()
    return {getattr(v, parent_id_field): v.vote_type for v in votes}
