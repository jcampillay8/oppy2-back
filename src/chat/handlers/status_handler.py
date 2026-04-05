# src/chat/handlers/status_handler.py
import logging
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder
from src.chat.manager import websocket_manager
from src.chat.schemas import UserTypingSchema, AddUserToChatSchema, NotifyChatRemovedSchema
from src.chat.services.presence_service import PresenceService

logger = logging.getLogger(__name__)

async def user_typing_handler(cache, incoming_message, chats, current_user, **kwargs):
    try:
        schema = UserTypingSchema(**incoming_message)
        chat_guid = str(schema.chat_guid)
        
        if chat_guid not in chats: return

        # Rate limit con Redis
        cache_key = f"typing_limit:{chat_guid}:{current_user.id}"
        if await cache.get(cache_key): return
        
        await cache.set(cache_key, "1", ex=1)
        await websocket_manager.broadcast_to_chat(chat_guid, schema.model_dump_json())
    except Exception as e:
        logger.error(f"Typing handler error: {e}")

async def add_user_to_chat_handler(websocket, incoming_message, chats, current_user, cache, **kwargs):
    schema = AddUserToChatSchema(**incoming_message)
    await websocket_manager.add_user_to_chat(schema.chat_guid, websocket)
    chats[schema.chat_guid] = schema.chat_id
    await PresenceService(cache).set_user_online(current_user.id)

async def chat_deleted_handler(websocket, incoming_message, chats, current_user, **kwargs):
    schema = NotifyChatRemovedSchema(**incoming_message)
    chat_guid = schema.chat_guid
    
    if chat_guid in chats:
        outgoing = {
            "type": "chat_deleted",
            "user_guid": str(current_user.guid),
            "chat_guid": chat_guid,
        }
        # Notificar a otros, excepto al que borró (que ya lo sabe por REST)
        target_ws = websocket_manager.chats.get(chat_guid, set())
        for ws in target_ws:
            if ws != websocket:
                await ws.send_json(jsonable_encoder(outgoing))