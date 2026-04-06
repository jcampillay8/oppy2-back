# src/avatars/router/__init__.py
from fastapi import APIRouter
from .avatar_endpoints import router as avatar_endpoints

# Asegúrate de que el nombre coincida con lo que importa src/routers.py
avatar_router = APIRouter(prefix="/avatars", tags=["Avatars"])

avatar_router.include_router(avatar_endpoints)