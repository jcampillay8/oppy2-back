# src/chat/services/notification_service.py
import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from src.chat.manager import websocket_manager
from src.chat.schemas import BotChatOutSchema, LastMessagePreviewSchema
from src.models import Chat, User

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, ws_manager=websocket_manager):
        self.ws_manager = ws_manager

    async def notify_new_chat_created(self, user: User, chat: Chat, bot_definition: Any):
        """
        Notifica al usuario que se ha creado un nuevo chat.
        Esto permite que la lista de chats en Flutter se actualice automáticamente.
        """
        user_guid_str = str(user.guid)
        
        # Construimos el payload basado en el esquema que espera el frontend
        # (BotChatOutSchema que definimos antes)
        notification_payload = {
            "type": "new_chat_created",
            "data": {
                "guid": str(chat.guid),
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat(),
                "new_messages_count": 1,
                "bot_definition": {
                    "guid": str(bot_definition.guid),
                    "name": bot_definition.name,
                    "avatar_url": bot_definition.avatar_url,
                },
                "last_message": None # O un mensaje de bienvenida si existe
            }
        }

        # Buscamos si el usuario tiene una conexión activa
        target_websockets = self.ws_manager.user_guid_to_websocket.get(user_guid_str)

        if target_websockets:
            try:
                # Enviamos la notificación a todas sus pestañas/dispositivos abiertos
                tasks = [
                    ws.send_json(jsonable_encoder(notification_payload)) 
                    for ws in target_websockets
                ]
                await asyncio.gather(*tasks)
                logger.info(f"Notificación de nuevo chat enviada a usuario {user_guid_str}")
            except Exception as e:
                logger.error(f"Error enviando notificación de nuevo chat: {e}")

    async def broadcast_system_event(self, chat_guid: UUID, event_type: str, message: str):
        """
        Envía un evento de sistema a todos los participantes de un chat.
        Ejemplo: 'El bot está procesando...', 'Mantenimiento programado', etc.
        """
        payload = {
            "type": "system_event",
            "event": event_type,
            "message": message
        }
        await self.ws_manager.broadcast_to_chat(str(chat_guid), payload)

    async def notify_error(self, user_guid: UUID, error_message: str):
        """
        Envía un error específico a un usuario a través del socket.
        """
        user_guid_str = str(user_guid)
        payload = {
            "type": "error",
            "message": error_message
        }
        
        target_websockets = self.ws_manager.user_guid_to_websocket.get(user_guid_str)
        if target_websockets:
            for ws in target_websockets:
                await ws.send_json(payload)