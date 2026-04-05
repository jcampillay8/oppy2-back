# src/learning_analysis/models.py
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Asumiendo que tu Base declarativa está en src.database
from src.database import BaseModel

class AnalysisCategory(BaseModel):
    __tablename__ = "analysis_categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    
    # Opcional: Relación inversa para ver qué usuarios tienen este foco
    focuses: Mapped[List["LearningFocus"]] = relationship(back_populates="category")

class LearningFocus(BaseModel):
    __tablename__ = "learning_focus"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("analysis_categories.id"), nullable=False)
    
    insight_summary: Mapped[str] = mapped_column(Text)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    priority_score: Mapped[float] = mapped_column(Float, default=1.0)
    
    # Timestamps útiles para el frontend (Saber qué repasar primero)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relaciones
    category: Mapped["AnalysisCategory"] = relationship(back_populates="focuses")
    instances: Mapped[List["FocusInstance"]] = relationship(
        back_populates="parent", 
        cascade="all, delete-orphan",
        order_by="desc(FocusInstance.created_at)" # Así las instancias nuevas salen primero
    )

class FocusInstance(BaseModel):
    __tablename__ = "focus_instances"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learning_focus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_focus.id"))
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"))
    
    original_segment: Mapped[str] = mapped_column(Text)
    corrected_segment: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    exercise_text_es: Mapped[Optional[str]] = mapped_column(Text)
    
    rating: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    parent: Mapped["LearningFocus"] = relationship(back_populates="instances")