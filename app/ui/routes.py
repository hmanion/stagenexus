from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings


router = APIRouter(tags=['ui'])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / 'templates')


@router.get('/', response_class=HTMLResponse)
@router.get('/home', response_class=HTMLResponse)
@router.get('/my-work', response_class=HTMLResponse)
@router.get('/deals', response_class=HTMLResponse)
@router.get('/scopes', response_class=HTMLResponse)
@router.get('/people', response_class=HTMLResponse)
@router.get('/campaigns', response_class=HTMLResponse)
@router.get('/gantt', response_class=HTMLResponse)
@router.get('/reviews', response_class=HTMLResponse)
@router.get('/risks', response_class=HTMLResponse)
@router.get('/capacity', response_class=HTMLResponse)
@router.get('/admin', response_class=HTMLResponse)
def index(request: Request):
    ui_flags = {
        'show_demo_rail': settings.show_demo_rail,
        'demo_rail_allowed_roles': list(settings.demo_rail_allowed_roles),
    }
    return templates.TemplateResponse('pages/index.html', {'request': request, 'ui_flags': ui_flags})
