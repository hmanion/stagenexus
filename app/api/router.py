from fastapi import APIRouter

from app.api.routes.scopes import router as scopes_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.core_routes import router as core_router

router = APIRouter()
router.include_router(scopes_router)
router.include_router(campaigns_router)
router.include_router(core_router)
