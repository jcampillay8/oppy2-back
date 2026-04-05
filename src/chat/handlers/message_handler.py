# src/chat/handlers/message_handler.py
import logging
import asyncio
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from src.chat.manager import websocket_manager
from src.chat.schemas import ReceiveMessageSchema, SendMessageSchema
from src.chat.services.interaction_handler import InteractionHandler

logger = logging.getLogger(__name__)

async def new_message_handler(websocket, db_session, cache, incoming_message, chats, current_user, **kwargs):
    try:
        schema = ReceiveMessageSchema(**incoming_message)
        chat_guid = str(schema.chat_guid)
        
        # El InteractionHandler ahora orquestará: IA + Corrección + DB
        handler = InteractionHandler(db_session, current_user)
        user_msg, bot_msg, feedback = await handler.process_interaction_by_guid(
            chat_guid, 
            schema.content,
            client_msg_guid=schema.message_guid
        )
        
        await db_session.commit()

        # 1. Enviar Mensaje del Bot
        bot_out = SendMessageSchema(
            message_guid=bot_msg.guid, chat_guid=chat_guid,
            content=bot_msg.content, role=bot_msg.role, created_at=bot_msg.created_at
        )
        await websocket_manager.broadcast_to_chat(chat_guid, bot_out.model_dump_json())

        # 2. Enviar Audio si existe (Lógica opcional)
        # if bot_msg.audio_path: ...

        # 3. Enviar Feedback de Corrección (Solo al usuario que envió)
        if feedback:
            await _send_safe_feedback(current_user.guid, feedback)

    except Exception as e:
        logger.exception(f"Error procesando mensaje: {e}")
        await websocket_manager.send_error("Internal error processing message", websocket)

async def _send_safe_feedback(user_guid, payload):
    """Envío robusto de feedback para evitar errores de socket cerrado"""
    websockets = websocket_manager.user_guid_to_websocket.get(str(user_guid), [])
    for ws in websockets:
        try:
            await ws.send_json(jsonable_encoder(payload))
        except RuntimeError:
            continue # Socket ya cerrándose