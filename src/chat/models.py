# src/chat/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
import uuid
from src.database import BaseModel
from typing import Dict, Any, List, Optional
from src.avatars.schemas import OutputFormatEnum, VoiceKeyEnum


class ChatFact(BaseModel):
    __tablename__ = "chat_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # ⭐ CAMBIO: Ahora apunta a avatar_definitions.guid
    avatar_definition_id: Mapped[int | None] = mapped_column(ForeignKey("avatar_definitions.id"), nullable=True)
    
    source_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)

    fact_type: Mapped[str] = mapped_column(String(255), nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # ⭐ RELACIÓN ACTUALIZADA
    avatar_definition_relation: Mapped["AvatarDefinition"] = relationship(back_populates="facts")
    chat: Mapped["Chat"] = relationship(back_populates="facts")
    user: Mapped["User"] = relationship(back_populates="chat_facts")
    source_message: Mapped["Message"] = relationship(back_populates="facts_as_source")
    

class UserMessageCorrection(BaseModel):
    __tablename__ = "user_message_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("messages.id"), nullable=True)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    highlighted_diff: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones - ⭐ SE MANTIENEN CONSISTENTES CON LA ESTRUCTURA DE AVATAR ⭐
    user: Mapped["User"] = relationship(back_populates="user_message_corrections")
    source_message: Mapped["Message"] = relationship(back_populates="user_message_corrections")

# src/chat/models.py

class OppyHostAvatarProfile(BaseModel): # <-- Cambiamos Bot por Avatar
    __tablename__ = "oppy_host_avatar_profile" # <-- El nombre que Alembic busca

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_avatar: Mapped[str] = mapped_column(String(500), nullable=False) # Antes role_bot
    role_usuario: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(String(500), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    character_traits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Nota: Aquí apunta a "AvatarDefinition" que es tu clase en src/avatars/models.py
    definitions: Mapped[List["AvatarDefinition"]] = relationship(back_populates="host_profile")