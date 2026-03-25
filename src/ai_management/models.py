# src/ai_management/models.py
from sqlalchemy import String, ForeignKey, Text, Boolean, Float, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
from src.database import BaseModel
from src.config import settings # Importamos settings para el schema

class LLMRequestLog(BaseModel): 
    __tablename__ = "llm_request_log" 
    # Mantenemos consistencia con el schema de la app
    __table_args__ = {'schema': settings.DB_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Apuntamos al schema.users.id
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.users.id"), 
        nullable=True
    )
    
    caller: Mapped[str] = mapped_column(String(255))
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, default="unknown") 
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    request_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    # Usamos string "User" para evitar el import circular
    user: Mapped["User"] = relationship(back_populates="llm_requests")


class AIModelConfig(BaseModel):
    """Configuración dinámica de modelos y precios."""
    __tablename__ = "ai_model_configs"
    __table_args__ = {'schema': settings.DB_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), unique=True) # ej: gemini-2.5-flash-lite
    input_price_per_million: Mapped[float] = mapped_column(Float)
    output_price_per_million: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)