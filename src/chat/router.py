# src/chat/router.py
from fastapi import APIRouter
from src.chat.router.rest_endpoints import router as rest_router
from src.chat.router.websocket_router import router as ws_router

# Definimos el router principal del módulo Chat
chat_router = APIRouter(prefix="/chats", tags=["Chat Management"])

# 1. Rutas REST (HTTP) -> GET /chats/, GET /chats/{guid}/messages
chat_router.include_router(rest_router)

# 2. Rutas WebSocket (WS) -> WS /chats/ws/{guid}
# Usamos el prefix /ws para diferenciar claramente el protocolo
chat_router.include_router(ws_router, prefix="/ws")