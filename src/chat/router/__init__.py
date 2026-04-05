# src/chat/router/__init__.py
from fastapi import APIRouter
from .rest_endpoints import router as rest_router
from .websocket_router import router as ws_router

# Creamos el router principal del módulo de chat
chat_router = APIRouter()

# Incluimos los sub-routers (REST y WebSocket)
# Esto hará que las rutas de cada uno se sumen a chat_router
chat_router.include_router(rest_router)
chat_router.include_router(ws_router)

# Exponemos explícitamente chat_router para que src/routers.py lo encuentre
__all__ = ["chat_router"]