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


class DeepLTranslationRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_lang: str = Field("EN-US", alias="targetLang")

    model_config = ConfigDict(populate_by_name=True)

class DeepLTranslationResponse(BaseModel):
    translated_text: str = Field(..., alias="translatedText")
    detected_source_lang: str = Field(..., alias="detectedSourceLang")
    target_lang: str = Field(..., alias="targetLang")

    model_config = ConfigDict(populate_by_name=True)



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


# --- SCHEMAS PARA EL TUTOR (TRANSLATION CHALLENGE) ---

class TranslationChallengeResponse(BaseModel):
    context: str
    spanish_sentence: str
    ideal_english_translation: str
    grammar_target: str

class ListeningChallengeResponse(BaseModel):
    context: str
    english_sentence: str
    voice_name: str
    voice_gender: str
    audio_base64: str
    grammar_target: str
    
class TranslationEvaluationRequest(BaseModel):
    user_translation: str
    grammar_target: str
    spanish_sentence: Optional[str] = None
    
class ErrorFound(BaseModel):
    original_text: str
    category: str
    hint: str
    
class TextDifference(BaseModel):
    type: str # 'default', 'added', 'removed'
    text: str
    
class TranslationEvaluationResponse(BaseModel):
    corrected_text: str
    feedback_text: str
    errors_found: List[ErrorFound] = []
    differences: List[TextDifference] = []

# --- SCHEMAS PARA VOCABULARIO (SRS) ---

class VocabularyWordCreate(BaseModel):
    spanish_word: str
    english_word: str
    context_sentence: Optional[str] = None
    
class VocabularyWordResponse(BaseModel):
    id: int
    spanish_word: str
    english_word: str
    context_sentence: Optional[str] = None
    score: int
    is_mastered: bool
    
class VocabularyPracticeRequest(BaseModel):
    word_id: int
    user_answer: str
    
class VocabularyPracticeResult(BaseModel):
    is_correct: bool
    correct_answer: str
    new_score: int
    is_mastered: bool
    feedback: str

# --- SCHEMAS PARA LEARNING PATH (PRÁCTICA GUIADA) ---

class LearningPathUnitProgress(BaseModel):
    level: int
    unit: int
    status: str # "locked", "in_progress", "mastered"
    precision_score: Optional[float] = None
    last_practiced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LearningPathProgressResponse(BaseModel):
    progress: List[LearningPathUnitProgress]

class UnitCompleteRequest(BaseModel):
    level: int
    unit: int
    precision_score: float

class UnitCompleteResponse(BaseModel):
    level: int
    unit: int
    status: str
    precision_score: float
    unlocked_next: bool

class SmartReviewSuggestionResponse(BaseModel):
    has_mastered_units: bool
    level: Optional[int] = None
    unit: Optional[int] = None
    unit_title: Optional[str] = None
    precision_score: Optional[float] = None
    days_since_practiced: Optional[int] = None
    reason_text: Optional[str] = None