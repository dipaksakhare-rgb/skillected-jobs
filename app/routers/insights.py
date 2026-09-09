"""Public market-intelligence pages (§25–27, §70–73)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.repositories import stats_repo
from app.services import market

settings = get_settings()
router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _ctx(request: Request, **extra) -> dict:
    sess = request.scope.get("session_data")
    return {"request": request, "session": sess, "active_nav": "insights", **extra}


@router.get("/placement-radar", response_class=HTMLResponse)
def placement_radar_page(request: Request):
    radar = stats_repo.placement_radar()
    trends = market.hiring_trends()
    return templates.TemplateResponse(request, "public/placement_radar.html", _ctx(
        request, radar=radar, trends=trends["trends"], trends_note=trends["note"]))


@router.get("/career-insights", response_class=HTMLResponse)
def career_insights_page(request: Request):
    skills = market.skill_demand_shift()
    demand = market.domain_demand()
    companies = market.company_hiring_intelligence()
    return templates.TemplateResponse(request, "public/career_insights.html", _ctx(
        request, skills=skills, demand=demand, companies=companies))


@router.get("/curriculum-intelligence", response_class=HTMLResponse)
def curriculum_page(request: Request):
    blocks = market.curriculum_intelligence()
    return templates.TemplateResponse(request, "public/curriculum.html", _ctx(
        request, blocks=blocks))
