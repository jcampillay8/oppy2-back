# src/chat/router/__init__.py
from fastapi import APIRouter
from .rest_endpoints import router as rest_router
from .websocket_router import router as ws_router

# Definimos el router principal con el TAG que quieres ver en Swagger
chat_router = APIRouter(prefix="/chats", tags=["Chat Management"])

# Al incluir los sub-routers, heredan el prefijo /chats
chat_router.include_router(rest_router)
chat_router.include_router(ws_router, prefix="/ws")

__all__ = ["chat_router"]