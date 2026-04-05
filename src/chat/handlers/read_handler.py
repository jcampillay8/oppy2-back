# src/chat/handlers/read_handler.py
import logging
from typing import Optional
from fastapi import WebSocket
from src.chat.manager import websocket_manager
from src.chat.schemas import MessageReadSchema
from src.chat.services.read_status_service import ReadStatusService
from src.chat.services.presence_service import PresenceService
from src.chat.services.message_service import MessageService # Para buscar mensaje por GUID

logger = logging.getLogger(__name__)

async def message_read_handler(websocket: WebSocket, db_session, cache, incoming_message: dict, chats: dict, current_user, cache_enabled: bool, **kwargs):
    try:
        schema = MessageReadSchema(**incoming_message)
        chat_guid = str(schema.chat_guid)
        
        if chat_guid not in chats:
            await websocket_manager.send_error(f"Chat {chat_guid} not active", websocket)
            return

        # 1. Obtener ID del mensaje desde el GUID
        msg_service = MessageService(db_session)
        message = await msg_service.get_message_by_guid(schema.message_guid)
        if not message:
            return

        # 2. Marcar lectura
        read_service = ReadStatusService(db_session)
        await read_service.mark_as_read(current_user.id, chats[chat_guid], message.id)
        await db_session.commit()

        # 3. Notificar a los demás y actualizar presencia
        presence = PresenceService(cache)
        await presence.set_user_online(current_user.id)
        
        outgoing = {
            "type": "message_read",
            "user_guid": str(current_user.guid),
            "chat_guid": chat_guid,
            "last_read_message_guid": str(message.guid),
            "last_read_message_created_at": message.created_at.isoformat(),
        }
        await websocket_manager.broadcast_to_chat(chat_guid, outgoing)

    except Exception as e:
        logger.error(f"Error in read_handler: {e}")