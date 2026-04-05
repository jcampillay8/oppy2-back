# websocket_router.py
import asyncio
import logging
from uuid import UUID
from json.decoder import JSONDecodeError

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# ✅ Solo lo que pertenece a SQLAlchemy
from src.database import async_session_maker 

# ✅ Lo que pertenece a la lógica de Inyección de Dependencias
from src.dependencies import (
    get_current_user_ws, 
    get_cache, 
    get_cache_setting
)
from src.models import User, Chat
from src.chat.manager import websocket_manager
from src.chat.services.notification_service import PresenceService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/{chat_guid}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_guid: UUID,
    # Nota: get_current_user debe manejar internamente el error de Auth para WS
    current_user: User = Depends(get_current_user_ws), 
    cache = Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting),
):
    # 1. Validación de existencia del Chat y acceso
    # Usamos un context manager de sesión aquí para asegurar que la sesión sea fresca
    async with async_session_maker() as db_session:
        chat_query = await db_session.execute(
            select(Chat)
            .where(Chat.guid == chat_guid)
            .options(selectinload(Chat.users))
        )
        chat_obj = chat_query.scalar_one_or_none()

        if not chat_obj or current_user not in chat_obj.users:
            logger.warning(f"WS Denied: Chat {chat_guid} not authorized for user {current_user.id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        chat_id = chat_obj.id # Guardamos el ID integer para el loop

    # 2. Inicialización de servicios y conexión
    presence = PresenceService(cache)
    await websocket_manager.connect_socket(websocket)
    
    # Registro de conexiones en el manager (PubSub interno)
    user_guid_str = str(current_user.guid)
    chat_guid_str = str(chat_guid)
    
    await websocket_manager.add_user_socket_connection(user_guid_str, websocket)
    await websocket_manager.add_user_to_chat(chat_guid_str, websocket)
    
    # Marcar presencia inicial
    await presence.set_user_online(current_user.id)

    try:
        while True:
            # Recibimos el JSON
            data = await websocket.receive_json()
            
            # Cada mensaje se procesa con su propia sesión de DB para evitar 
            # errores de 'Session is closed' en operaciones largas (como IA)
            async with async_session_maker() as db_session:
                
                message_type = data.get("type")
                handler = websocket_manager.handlers.get(message_type)

                if not handler:
                    await websocket_manager.send_error(f"Type {message_type} not supported", websocket)
                    continue

                # EJECUCIÓN DEL HANDLER MODULAR
                await handler(
                    websocket=websocket,
                    db_session=db_session,
                    cache=cache,
                    incoming_message=data,
                    chats={chat_guid_str: chat_id},
                    current_user=current_user,
                    cache_enabled=cache_enabled,
                )
                
                # Update de presencia "heartbeat"
                await presence.set_user_online(current_user.id)

    except WebSocketDisconnect:
        logger.info(f"WS Disconnect: User {current_user.id} left chat {chat_guid}")

    except JSONDecodeError:
        logger.error("Invalid JSON received")
        
    except Exception as e:
        logger.error(f"Fatal WS Error: {e}", exc_info=True)

    finally:
        # --- LIMPIEZA ---
        await websocket_manager.remove_user_from_chat(chat_guid_str, websocket)
        await websocket_manager.remove_user_guid_to_websocket(user_guid_str, websocket)
        
        # Marcar Offline en Redis
        await presence.set_user_offline(current_user.id)