import logging
from uuid import UUID, uuid4
from typing import List, Annotated, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_async_session
from src.dependencies import get_current_user, get_cache, get_cache_setting
from src.models import User, Chat, Message, MessageRole
from src.avatars.models import AvatarDefinition
# Importamos los nombres REALES de tus schemas
from src.chat.schemas import (
    AvatarChatOutSchema, # Antes ChatOut
    MessageOut, 
    GetBotChatsResponse,
    MessageCreate
)
# Nota: Si ChatCreate y ChatWithMessages no existen en tu schemas.py, 
# deberás definirlos o usar los nombres correctos.

from src.chat.services.chat_listing_service import get_user_chat_list
from src.chat.services.message_service import get_chat_messages_paginated
from src.chat.services.read_status_service import ReadStatusService
from src.chat.services.interaction_handler import InteractionHandler
from src.avatars.services import create_avatar_chat_session

logger = logging.getLogger(__name__)
router = APIRouter()

# El GUID de Oppy (Avatar por defecto)
OPPY_GUID = UUID('34a6b8c1-1d2e-4f5a-6b7c-8d9e0f1a2b3c')

# --- CHATS ---

@router.post("/", response_model=AvatarChatOutSchema, status_code=status.HTTP_201_CREATED)
async def create_chat_with_avatar(
    chat_data: dict, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    cache = Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting),
):
    try:
        # 1. Buscar el Avatar
        avatar_guid = chat_data.get("avatar_definition_guid") or OPPY_GUID
        
        avatar_stmt = select(AvatarDefinition).where(AvatarDefinition.guid == avatar_guid)
        avatar_res = await db.execute(avatar_stmt)
        avatar_obj = avatar_res.scalar_one_or_none()

        if not avatar_obj:
            raise HTTPException(status_code=400, detail="Avatar definition not found.")

        # 2. ✅ CORRECCIÓN: Nombres de parámetros alineados con src/avatars/services.py
        # El servicio espera (db, user_id, avatar)
        new_chat = await create_avatar_chat_session(
            db=db,
            user_id=current_user.id,
            avatar=avatar_obj 
        )

        if cache_enabled:
            await cache.delete(f"avatar_chats_{current_user.guid}")

        # 3. Recarga
        stmt = select(Chat).where(Chat.guid == new_chat.guid).options(
            selectinload(Chat.avatar_definition),
            selectinload(Chat.users)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    except Exception as e:
        logger.error(f"Error creating chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during chat creation.")

@router.get("/", response_model=GetBotChatsResponse)
async def get_user_chats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    chats = await get_user_chat_list(db, current_user)
    total_unread = sum(c.new_messages_count for c in chats)
    return GetBotChatsResponse(chats=chats, total_unread_count=total_unread)

# --- MESSAGES ---

@router.get("/{chat_guid}/messages/", response_model=List[MessageOut])
async def get_chat_messages(
    chat_guid: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    messages, _ = await get_chat_messages_paginated(db, chat_guid, current_user.id)
    return messages

@router.post("/{chat_guid}/messages/")
async def send_message_rest(
    chat_guid: UUID,
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    handler = InteractionHandler(db, current_user)
    
    try:
        # ✅ USAMOS EL NOMBRE CORRECTO: process_interaction_by_guid
        user_msg, bot_msg, feedback = await handler.process_interaction_by_guid(
            chat_guid=chat_guid,
            user_message_content=message_data.content
        )
        
        await db.commit()

        return {
            "messages": [
                MessageOut.model_validate(user_msg), 
                MessageOut.model_validate(bot_msg)
            ],
            "feedback": feedback
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in send_message_rest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing interaction")