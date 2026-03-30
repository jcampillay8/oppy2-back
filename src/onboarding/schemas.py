# src/onboarding/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- SCHEMAS EXISTENTES (Perfil) ---
class OnboardingProfileUpdate(BaseModel):
    # Usamos default=None en lugar de elipsis (...)
    username: Optional[str] = Field(default=None, min_length=3, max_length=150)
    
    # IMPORTANTE: Eliminamos min_length para occupation y bio en este esquema
    # porque si Flutter envía "" (vacío), el min_length=2 causará el 422.
    occupation: Optional[str] = Field(default=None, max_length=150)
    bio: Optional[str] = Field(default=None, max_length=500)

class OnboardingStatusResponse(BaseModel):
    needs_onboarding: bool
    current_step: int  # 1: Perfil, 2: Idioma, 3: Test, 4: Finalizado
    target_language: Optional[str] = None # Para que el front sepa qué bandera mostrar si ya eligió

# --- NUEVOS SCHEMAS (Idioma y Test) ---

class LanguageSelection(BaseModel):
    """Para recibir la elección de la bandera (Inglés o Español)"""
    target_language: str = Field(..., pattern="^(en|es)$") # Solo permite 'en' o 'es'

class PlacementTestSubmit(BaseModel):
    """Para recibir los 4 puntajes finales desde Flutter"""
    target_language: str = Field(..., pattern="^(en|es)$")
    writing_result: float = Field(..., ge=0, le=100) # Escala 0-100
    reading_result: float = Field(..., ge=0, le=100)
    listening_result: float = Field(..., ge=0, le=100)
    speaking_result: float = Field(..., ge=0, le=100)

class PlacementTestResponse(BaseModel):
    """Para devolver el resultado calculado (B2, A1, etc.)"""
    target_language: str
    suggested_level: str
    is_completed: bool
    completed_at: datetime

    class Config:
        from_attributes = True # Permite leer desde el modelo de SQLAlchemy directamente

class WritingQuestionResponse(BaseModel):
    """Respuesta con la pregunta generada por la IA"""
    question: str
    target_language: str

class WritingSubmission(BaseModel):
    """Lo que el usuario envía desde Flutter para ser evaluado"""
    user_answer: str = Field(..., min_length=10, max_length=2000)
    target_language: str = Field(..., pattern="^(en|es)$")

class WritingEvaluationResponse(BaseModel):
    """Resultado de la evaluación de la IA"""
    score: float # 0 a 100
    feedback: str
    suggested_level: str # B1, B2, etc.


class ReadingSubmission(BaseModel):
    answers: List[str]