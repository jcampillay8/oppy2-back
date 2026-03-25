# src/onboarding/models.py
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import BaseModel 
from src.config import settings

class PlacementTest(BaseModel): 
    __tablename__ = "placement_tests"
    __table_args__ = (
        # Esto permite que un usuario tenga un test de Inglés Y uno de Español,
        # pero no dos tests del mismo idioma.
        UniqueConstraint('user_id', 'target_language', name='_user_language_uc'),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.users.id"), 
        nullable=False
    )
    
    # Nuevo Campo: 'en' para inglés, 'es' para español, etc.
    target_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Resultados
    writing_result: Mapped[float] = mapped_column(Float, nullable=True)
    reading_result: Mapped[float] = mapped_column(Float, nullable=True)
    listening_result: Mapped[float] = mapped_column(Float, nullable=True)
    speaking_result: Mapped[float] = mapped_column(Float, nullable=True)
    
    suggested_level: Mapped[str] = mapped_column(String(10), nullable=True) # Ej: "B2", "A1"
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="placement_tests")

class WritingTopic(BaseModel):
    """Banco de preguntas para el test de Writing."""
    __tablename__ = "writing_topics"
    __table_args__ = {'schema': settings.DB_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50)) # 'narrative', 'opinion', 'descriptive'
    target_language: Mapped[str] = mapped_column(String(10)) # 'en', 'es'
    title: Mapped[str] = mapped_column(String(200)) # Ej: 'A Change of Plans'
    prompt: Mapped[str] = mapped_column(Text) # La descripción larga

class UserWritingAssignment(BaseModel):
    """Guarda qué pregunta se le asignó a un usuario para evitar que cambie al azar."""
    __tablename__ = "user_writing_assignments"
    __table_args__ = (
        UniqueConstraint('user_id', 'target_language', name='_user_lang_assignment_uc'),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.writing_topics.id"))
    target_language: Mapped[str] = mapped_column(String(10))
    
    topic: Mapped["WritingTopic"] = relationship("WritingTopic")