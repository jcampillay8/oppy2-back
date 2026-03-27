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

    details: Mapped[list["PlacementTestDetail"]] = relationship(
        "PlacementTestDetail", 
        back_populates="placement_test",
        cascade="all, delete-orphan"
    )

class PlacementTestDetail(BaseModel):
    __tablename__ = "placement_test_details"
    __table_args__ = (
        # Un detalle único por test e idioma por sección (ej: no dos 'writing' para el mismo test)
        UniqueConstraint('placement_test_id', 'section', name='_test_section_uc'),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placement_test_id: Mapped[int] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.placement_tests.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # "writing", "reading", "listening", "speaking"
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # El contenido generado por la IA o el sistema
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Lo que el usuario escribió o grabó (transcripción)
    user_response: Mapped[str] = mapped_column(Text, nullable=True)
    
    # El feedback detallado que nos dio Gemini
    feedback_text: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Puntaje específico de esta sección (redundante pero útil para histórico)
    score: Mapped[float] = mapped_column(Float, nullable=True)

    # Relación inversa
    placement_test: Mapped["PlacementTest"] = relationship(
        "PlacementTest", back_populates="details"
    )