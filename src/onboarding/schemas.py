# src/onboarding/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
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

class WritingAnswer(BaseModel):
    target_language: str
    text: str = Field(..., min_length=10)

class WritingCategorySelection(BaseModel):
    category: str = Field(..., pattern="^(narrative|opinion|descriptive)$")
    target_language: str = Field(..., pattern="^(en|es)$")

class WritingTopicResponse(BaseModel):
    id: int
    category: str
    title: str
    prompt: str
    
    class Config:
        from_attributes = True