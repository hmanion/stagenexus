from fastapi import APIRouter

from app.api.routes.deals import router as deals_router
from app.api.core_routes import router as core_router

router = APIRouter()
router.include_router(deals_router)
router.include_router(core_router)
