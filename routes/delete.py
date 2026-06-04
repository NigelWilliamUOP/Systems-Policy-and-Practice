"""Paper deletion routes."""
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from models.database import get_db
from models.paper import Paper, PaperHumanAuthor
from services.file_storage import file_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper", tags=["delete"])

def require_auth(request: Request):
    """Dependency to require authentication."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

@router.post("/{paper_id}/delete")
async def delete_paper(
    paper_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a paper (only by authors).

    Screened-out papers are soft-deleted: they keep a tombstone record
    showing 'Deleted Paper' with dates, visible in the Screened Out tab.
    Other papers are fully deleted.
    """
    user_data = require_auth(request)

    # Get paper
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Check if user is an author
    is_author = db.query(PaperHumanAuthor).filter(
        PaperHumanAuthor.paper_id == paper_id,
        PaperHumanAuthor.user_id == user_data["id"]
    ).first() is not None

    if not is_author:
        raise HTTPException(status_code=403, detail="Only authors can delete this paper")

    # Screened-out papers: soft-delete (keep tombstone)
    if paper.status == "ai_screen_rejected":
        paper.withdrawn_at = datetime.utcnow()
        paper.title = "Deleted Paper"
        paper.abstract = ""
        # Remove files but keep the record
        for version in paper.versions:
            try:
                file_path = file_storage.get_file_path(version.pdf_filename, paper.published_date)
                file_storage.delete_file(file_path)
            except Exception:
                logger.warning("Failed to delete PDF %s for paper %d", version.pdf_filename, paper_id, exc_info=True)
        if paper.image_filename:
            try:
                image_path = file_storage.get_file_path(paper.image_filename, paper.published_date)
                file_storage.delete_file(image_path)
            except Exception:
                logger.warning("Failed to delete image %s for paper %d", paper.image_filename, paper_id, exc_info=True)
            paper.image_filename = None
        db.commit()
        return RedirectResponse(url="/auth/profile", status_code=303)

    if paper.is_locked:
        raise HTTPException(status_code=403, detail="Paper cannot be deleted while in the review pipeline.")

    # Full deletion for non-screened papers
    for version in paper.versions:
        try:
            file_path = file_storage.get_file_path(version.pdf_filename, paper.published_date)
            file_storage.delete_file(file_path)
        except Exception:
            logger.warning("Failed to delete PDF %s for paper %d", version.pdf_filename, paper_id, exc_info=True)

    if paper.image_filename:
        try:
            image_path = file_storage.get_file_path(paper.image_filename, paper.published_date)
            file_storage.delete_file(image_path)
        except Exception:
            logger.warning("Failed to delete image %s for paper %d", paper.image_filename, paper_id, exc_info=True)

    try:
        db.delete(paper)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete paper %d", paper_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete paper. Please contact support.")

    return RedirectResponse(url="/auth/profile", status_code=303)
