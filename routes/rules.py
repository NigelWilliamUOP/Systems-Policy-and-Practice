"""Rules page — comprehensive documentation of JAIGP journal processes."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from routes.shared import get_templates

router = APIRouter(tags=["rules"])
templates = get_templates()


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
    """Display the journal rules and processes."""
    user = request.session.get("user")
    return templates.TemplateResponse("rules.html", {"request": request, "user": user})
