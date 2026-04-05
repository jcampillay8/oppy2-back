# src/avatars/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
import uuid
from src.database import BaseModel
from typing import Dict, Any, List, Optional
from .enums import OutputFormatEnum, VoiceKeyEnum

class AvatarDefinition(BaseModel):
    __tablename__ = "avatar_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship(back_populates="avatar_definitions")

    host_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("oppy_host_avatar_profile.id"), nullable=True)
    host_profile: Mapped[Optional["OppyHostAvatarProfile"]] = relationship(back_populates="definitions")

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_avatar: Mapped[str | None] = mapped_column(String(500), nullable=True) # Antes role_bot
    role_usuario: Mapped[str | None] = mapped_column(String(255), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(500), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_traits: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format_preference: Mapped[OutputFormatEnum | None] = mapped_column(String(50), nullable=True)

    # ⭐ CONFIGURACIÓN DE VOZ E IDIOMA ⭐
    language_preference: Mapped[str | None] = mapped_column(String(10), nullable=True, default="en-US")
    selected_voice: Mapped[VoiceKeyEnum | None] = mapped_column(String(50), nullable=True, default="us_female")
    is_tts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # RELACIONES ACTUALIZADAS
    chats: Mapped[list["Chat"]] = relationship(back_populates="avatar_definition")
    facts: Mapped[list["ChatFact"]] = relationship(back_populates="avatar_definition_relation")
    translations: Mapped[List["AvatarDefinitionTranslation"]] = relationship(
        back_populates="avatar_definition_main", cascade="all, delete-orphan"
    )