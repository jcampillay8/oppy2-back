# src/avatars/router/__init__.py
from fastapi import APIRouter
from .avatar_endpoints import router as avatar_router

router = APIRouter(prefix="/avatars", tags=["Avatars"])
router.include_router(avatar_router)