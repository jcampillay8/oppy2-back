# src/chat/services/message_service.py
import logging
import uuid
from typing import Optional, List, Sequence, Dict, Any
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from src.models import Message, MessageRole, User
from src.chat.models import ChatFact # Asegúrate de que la ruta sea correcta

logger = logging.getLogger(__name__)

class MessageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_message(
        self,
        chat_id: int,
        content: str,
        role: MessageRole,
        user_id: Optional[int] = None,
        guid: Optional[uuid.UUID] = None,
    ) -> Message:
        """Crea y persiste un nuevo mensaje."""
        new_message = Message(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            content=content,
            guid=guid or uuid.uuid4(),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) # Ajuste para consistencia DB
        )
        self.db.add(new_message)
        return new_message

    async def get_chat_history_for_llm(self, chat_id: int, limit: int = 15) -> List[Dict[str, str]]:
        """
        Recupera el historial formateado específicamente para la API de la LLM.
        Filtra mensajes eliminados y ordena cronológicamente.
        """
        stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.is_deleted == False # Filtro de seguridad
            )
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse() # Orden cronológico: [Antiguo -> Reciente]

        llm_history = []
        for msg in messages:
            # Normalización del rol (Enum a string 'user'/'assistant')
            role_str = msg.role.value if isinstance(msg.role, Enum) else str(msg.role)
            
            # Mapeo específico si los nombres del Enum no coinciden con los de la API LLM
            if role_str == MessageRole.ASSISTANT.value:
                role_str = "assistant"
            elif role_str == MessageRole.USER.value:
                role_str = "user"

            llm_history.append({
                "role": role_str,
                "content": msg.content
            })
        
        return llm_history

    async def get_chat_facts(self, chat_id: int) -> List[ChatFact]:
        """Recupera la memoria a largo plazo (hechos) asociada al chat."""
        stmt = (
            select(ChatFact)
            .where(ChatFact.chat_id == chat_id)
            .order_by(ChatFact.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_message_by_guid(self, message_guid: uuid.UUID) -> Optional[Message]:
        """Busca un mensaje por su GUID."""
        stmt = select(Message).where(Message.guid == message_guid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_message(self, message_id: int) -> bool:
        """Realiza un borrado lógico del mensaje."""
        stmt = select(Message).where(Message.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        
        if message:
            message.is_deleted = True
            message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            return True
        return False

    async def get_chat_messages_paginated(
            self, 
            chat_guid: uuid.UUID, 
            user_id: int, 
            limit: int = 50
        ) -> List[Message]:
            """
            Recupera los mensajes de un chat específico para mostrar en la UI.
            Incluye validación de que el chat pertenece al usuario.
            """
            from src.models import Chat # Import local para evitar círculos si es necesario
            
            stmt = (
                select(Message)
                .join(Chat)
                .where(
                    Chat.guid == chat_guid,
                    Message.is_deleted == False
                )
                .order_by(Message.created_at.asc()) # Orden natural para el chat
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            return list(result.scalars().all())