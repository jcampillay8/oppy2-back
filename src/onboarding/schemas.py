# src/onboarding/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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


class ListeningQuestion(BaseModel):
    """Estructura de una pregunta individual dentro del test"""
    id: int
    question_text: str
    options: List[Dict[str, str]] # Ejemplo: [{"id": "A", "text": "Option..."}, ...]

class ListeningTaskResponse(BaseModel):
    """Lo que el router entrega al Frontend (con el audio)"""
    title: str
    script: str # Opcional: podrías ocultarlo si no quieres que lo lean mientras escuchan
    questions: List[Dict] # Estructura completa de preguntas y opciones
    audio_base64: str
    mime_type: str = "audio/mp3"

class ListeningSubmission(BaseModel):
    """Lo que el usuario envía desde Flutter para ser evaluado"""
    # Lista de strings con las respuestas del usuario, ej: ["A", "C", "B"]
    answers: List[str] = Field(..., min_items=1, max_items=5) 

class ListeningEvaluationResponse(BaseModel):
    """Resultado final de la sección de Listening"""
    score: float
    assigned_level: str # A1, A2, B1, B2
    correct_answers: List[str]
    message: str

class SpeakingEvaluationResponse(BaseModel):
    transcript: str
    score: float
    assigned_level: str
    feedback: str
    fluency_score: Optional[float] = None

class FinalResultsResponse(BaseModel):
    global_level: str
    level_name: str
    scores: Dict[str, float]
    ai_analysis: str
    suggested_plan: str
    next_steps: List[Dict[str, str]]