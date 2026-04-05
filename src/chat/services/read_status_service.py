# src/chat/services/read_status_service.py
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import ReadStatus, Message, MessageRole

logger = logging.getLogger(__name__)

class ReadStatusService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_last_read_message_id(self, chat_id: int, user_id: int) -> int:
        stmt = select(ReadStatus.last_read_message_id).where(
            ReadStatus.chat_id == chat_id,
            ReadStatus.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def mark_chat_as_read(self, chat_id: int, user_id: int) -> None:
        last_msg_stmt = (
            select(func.max(Message.id))
            .where(
                Message.chat_id == chat_id,
                Message.role == MessageRole.ASSISTANT
            )
        )
        last_msg_res = await self.db.execute(last_msg_stmt)
        last_message_id = last_msg_res.scalar()

        if not last_message_id:
            return

        status_stmt = select(ReadStatus).where(
            ReadStatus.chat_id == chat_id,
            ReadStatus.user_id == user_id
        )
        status_res = await self.db.execute(status_stmt)
        status_obj = status_res.scalar_one_or_none()

        if status_obj:
            if last_message_id > (status_obj.last_read_message_id or 0):
                status_obj.last_read_message_id = last_message_id
        else:
            new_status = ReadStatus(
                chat_id=chat_id,
                user_id=user_id,
                last_read_message_id=last_message_id
            )
            self.db.add(new_status)
        
        await self.db.flush()

    async def mark_specific_message_as_read(self, chat_id: int, user_id: int, message_id: int) -> None:
        # Nota: He renombrado esto a 'mark_as_read' si quieres que coincida 
        # exactamente con lo que llama tu read_handler.py
        status_stmt = select(ReadStatus).where(
            ReadStatus.chat_id == chat_id,
            ReadStatus.user_id == user_id
        )
        res = await self.db.execute(status_stmt)
        status = res.scalar_one_or_none()

        if status:
            status.last_read_message_id = max(status.last_read_message_id or 0, message_id)
        else:
            self.db.add(ReadStatus(
                chat_id=chat_id,
                user_id=user_id,
                last_read_message_id=message_id
            ))
        
        await self.db.flush()
    
    # Alias para compatibilidad con tu read_handler.py
    async def mark_as_read(self, user_id: int, chat_id: int, message_id: int):
        return await self.mark_specific_message_as_read(chat_id, user_id, message_id)