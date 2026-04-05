# src/learning_analysis/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Any, Dict

# --- CATEGORÍAS ---

class AnalysisCategory(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# --- FOCUS (EL PADRE / RESUMEN POR CATEGORÍA) ---

class LearningFocusBase(BaseModel):
    insight_summary: str = Field(..., alias="insightSummary")
    total_count: int = Field(..., alias="totalCount")
    priority_score: float = Field(1.0, alias="priorityScore")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LearningFocusResponse(LearningFocusBase):
    id: UUID
    user_id: int = Field(..., alias="userId")
    category_id: int = Field(..., alias="categoryId")
    # Para evitar circularidad o exceso de datos, enviamos el nombre de la categoría
    category_name: Optional[str] = Field(None, alias="categoryName") 


# --- INSTANCES (EL HIJO / EVIDENCIA ESPECÍFICA) ---

class FocusInstanceBase(BaseModel):
    original_segment: str = Field(..., alias="originalSegment")
    corrected_segment: str = Field(..., alias="correctedSegment")
    explanation: str
    exercise_text_es: Optional[str] = Field(None, alias="exerciseTextEs")
    rating: int = 3

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FocusInstanceResponse(FocusInstanceBase):
    id: UUID
    learning_focus_id: UUID = Field(..., alias="learningFocusId")
    message_id: int = Field(..., alias="messageId")
    created_at: datetime = Field(..., alias="createdAt")


# --- RESPUESTAS COMPUESTAS PARA EL FRONTEND ---

class UserLearningReport(BaseModel):
    """
    Útil para una vista general donde quieres ver el Focus 
    y quizás sus últimas 3 instancias.
    """
    focus: LearningFocusResponse
    latest_instances: List[FocusInstanceResponse] = Field(default_factory=list, alias="latestInstances")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorAuditSchema(BaseModel):
    """
    Este esquema es el que usa el 'analyzer.py' para 
    validar la respuesta que viene del LLM.
    """
    category: str
    incorrect_part: str
    correct_part: str
    explanation: str
    exercise_text_es: str