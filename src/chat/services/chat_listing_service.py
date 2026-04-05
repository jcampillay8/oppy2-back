# src/chat/services/chat_listing_service.py
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.models import Chat, Message, ReadStatus, User, MessageRole, user_chat
from src.chat.schemas import BotChatOutSchema, LastMessagePreviewSchema

logger = logging.getLogger(__name__)

async def get_user_chat_list(
    db_session: AsyncSession, 
    current_user: User
) -> List[BotChatOutSchema]:
    """
    Obtiene la lista de chats del usuario con:
    1. Información del Chat.
    2. Conteo de mensajes no leídos (Assistant).
    3. Vista previa del último mensaje.
    """
    
    # 1. Obtener los objetos Chat base del usuario
    # Usamos join con la tabla intermedia user_chat
    stmt = (
        select(Chat)
        .join(user_chat, Chat.id == user_chat.c.chat_id)
        .where(user_chat.c.user_id == current_user.id)
        .order_by(desc(Chat.updated_at))
    )
    
    result = await db_session.execute(stmt)
    chats = result.scalars().all()
    
    if not chats:
        return []

    chat_ids = [c.id for c in chats]

    # 2. Obtener Estados de Lectura (Mapeo: chat_id -> last_read_message_id)
    read_status_stmt = select(ReadStatus).where(
        ReadStatus.user_id == current_user.id,
        ReadStatus.chat_id.in_(chat_ids)
    )
    read_status_res = await db_session.execute(read_status_stmt)
    read_map = {r.chat_id: r.last_read_message_id for r in read_status_res.scalars().all()}

    # 3. Obtener el Último Mensaje de cada chat para la Preview
    # Subconsulta para el ID del último mensaje por chat
    last_msg_subquery = (
        select(Message.chat_id, func.max(Message.id).label("max_id"))
        .where(Message.chat_id.in_(chat_ids))
        .group_by(Message.chat_id)
        .subquery()
    )

    last_msg_stmt = (
        select(Message)
        .join(last_msg_subquery, Message.id == last_msg_subquery.c.max_id)
    )
    last_msg_res = await db_session.execute(last_msg_stmt)
    last_messages_map = {m.chat_id: m for m in last_msg_res.scalars().all()}

    # 4. Construir la respuesta final
    final_list = []
    for chat in chats:
        # Calcular no leídos: Contar mensajes ASSISTANT con ID > last_read_id
        last_read_id = read_map.get(chat.id, 0) or 0
        
        unread_count_stmt = select(func.count(Message.id)).where(
            Message.chat_id == chat.id,
            Message.role == MessageRole.ASSISTANT,
            Message.id > last_read_id
        )
        unread_res = await db_session.execute(unread_count_stmt)
        unread_count = unread_res.scalar() or 0

        # Preparar Preview
        last_msg = last_messages_map.get(chat.id)
        preview = None
        if last_msg:
            preview = LastMessagePreviewSchema(
                content=last_msg.content,
                created_at=last_msg.created_at
            )

        # Mapear al esquema Pydantic
        final_list.append(BotChatOutSchema(
            guid=chat.guid,
            title=chat.title,
            updated_at=chat.updated_at,
            new_messages_count=unread_count,
            last_message=preview
        ))

    return final_list

async def update_last_read_status(
    db_session: AsyncSession, 
    chat_id: int, 
    user_id: int
):
    """
    Actualiza el puntero de 'visto' al último mensaje del asistente.
    """
    # Buscamos el ID del último mensaje del asistente en este chat
    last_assistant_msg_stmt = (
        select(func.max(Message.id))
        .where(Message.chat_id == chat_id, Message.role == MessageRole.ASSISTANT)
    )
    last_id_res = await db_session.execute(last_assistant_msg_stmt)
    last_id = last_id_res.scalar()

    if not last_id:
        return

    # Buscar si ya existe un registro en ReadStatus
    status_stmt = select(ReadStatus).where(
        ReadStatus.chat_id == chat_id, 
        ReadStatus.user_id == user_id
    )
    status_res = await db_session.execute(status_stmt)
    status = status_res.scalar_one_or_none()

    if status:
        status.last_read_message_id = last_id
    else:
        new_status = ReadStatus(
            chat_id=chat_id,
            user_id=user_id,
            last_read_message_id=last_id
        )
        db_session.add(new_status)
    
    await db_session.commit()