"""Notification routes."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from models.database import get_db
from services.notification import get_notifications, mark_all_as_read, mark_as_read
from routes.shared import require_auth, get_templates

router = APIRouter(tags=["notifications"])
templates = get_templates()


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    """Notifications page — list all recent notifications."""
    user = require_auth(request)
    notifications = get_notifications(user["id"], db)
    return templates.TemplateResponse(
        "notifications.html",
        {"request": request, "user": user, "notifications": notifications},
    )


@router.post("/notifications/read")
async def mark_notifications_read(request: Request, db: Session = Depends(get_db)):
    """Mark all unread notifications as read."""
    user = require_auth(request)
    count = mark_all_as_read(user["id"], db)
    db.commit()
    return JSONResponse({"success": True, "marked": count})


@router.post("/notifications/{notification_id}/read")
async def mark_one_read(notification_id: int, request: Request, db: Session = Depends(get_db)):
    """Mark a single notification as read."""
    user = require_auth(request)
    success = mark_as_read(notification_id, user["id"], db)
    db.commit()
    return JSONResponse({"success": success})
