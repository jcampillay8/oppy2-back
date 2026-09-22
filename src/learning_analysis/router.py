# src/learning_analysis/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from . import schemas, services
from .services import tutor_service

router = APIRouter(prefix="/learning-analysis", tags=["Learning Analysis"])

@router.get("/focus", response_model=List[schemas.LearningFocusResponse])
async def get_my_learning_focus(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    # Toda la lógica de filtrado y orden reside en persistence.py
    return await services.persistence.get_active_focus_by_user(db, user.id)

@router.get("/focus/{focus_id}/practice", response_model=schemas.FocusInstanceResponse)
async def get_practice_instance(
    focus_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    # La lógica de "selección aleatoria con rating" que tenías en el router pasado,
    # ahora la movemos a services/persistence.py
    instance = await services.persistence.get_random_practice_instance(db, focus_id, user.id)
    if not instance:
        raise HTTPException(status_code=404, detail="No exercises found for this focus")
    return instance

@router.post("/focus/{focus_id}/rate")
async def rate_error_instance(
    instance_id: UUID,
    new_rating: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await services.persistence.update_instance_rating(db, instance_id, user.id, new_rating)

# --- RUTAS DE VOCABULARIO (SRS) ---

from .services import vocabulary_service

@router.post("/vocabulary", response_model=schemas.VocabularyWordResponse)
async def create_vocabulary_word(
    word_in: schemas.VocabularyWordCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.save_word(db, user.id, word_in)

@router.get("/vocabulary/practice", response_model=schemas.VocabularyWordResponse)
async def get_practice_vocabulary_word(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    word = await vocabulary_service.get_practice_word(db, user.id)
    if not word:
        raise HTTPException(status_code=404, detail="No active vocabulary words to practice.")
    return word

@router.post("/vocabulary/evaluate", response_model=schemas.VocabularyPracticeResult)
async def evaluate_vocabulary_word(
    request: schemas.VocabularyPracticeRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.evaluate_word(db, user.id, request)

@router.post("/vocabulary/override", response_model=schemas.VocabularyPracticeResult)
async def override_vocabulary_word_eval(
    request: schemas.VocabularyPracticeRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.override_word_eval(db, user.id, request)

@router.get("/vocabulary/list", response_model=List[schemas.VocabularyWordResponse])
async def list_user_vocabulary_words(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.get_user_vocabulary_list(db, user.id)

@router.get("/vocabulary/stats")
async def get_user_vocabulary_stats(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.get_vocabulary_stats(db, user.id)


@router.delete("/vocabulary/{word_id}")
async def delete_vocabulary_word(
    word_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await vocabulary_service.delete_word(db, user.id, word_id)

# --- RUTAS DE GUÍA IELTS ---

from .services import ielts_syllabus
from .services.persistence import get_learning_path_progress, upsert_learning_path_progress

@router.get("/ielts-path/progress", response_model=schemas.LearningPathProgressResponse)
async def get_ielts_path_progress(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    progress_list = await get_learning_path_progress(db, user.id, course_type="ielts")
    if not progress_list:
        first_unit = await upsert_learning_path_progress(
            db, user.id, level=1, unit=1, status="in_progress", course_type="ielts"
        )
        progress_list = [first_unit]
    return schemas.LearningPathProgressResponse(progress=progress_list)

@router.get("/ielts-path/syllabus")
async def get_ielts_syllabus_info(
    user: User = Depends(get_current_user)
):
    return ielts_syllabus.load_ielts_syllabus()

from .services.persistence import get_user_activity_stats

@router.get("/ielts-path/activity")
async def get_ielts_activity_stats(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await get_user_activity_stats(db, user.id, course_type="ielts")

from .services import deepl_service

@router.post("/deepl/translate", response_model=schemas.DeepLTranslationResponse)
async def translate_text_with_deepl(
    payload: schemas.DeepLTranslationRequest,
    user: User = Depends(get_current_user)
):
    try:
        res = await deepl_service.translate_with_deepl(
            text=payload.text,
            target_lang=payload.target_lang,
            source_lang="ES"
        )
        return schemas.DeepLTranslationResponse(
            translated_text=res["translated_text"],
            detected_source_lang=res["detected_source_lang"],
            target_lang=res["target_lang"]
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/ielts-path/content")
async def get_ielts_unit_content(
    level: int,
    unit: int,
    user: User = Depends(get_current_user)
):
    content = ielts_syllabus.get_ielts_unit_markdown(level, unit)
    if not content:
        raise HTTPException(status_code=404, detail="Markdown content not found for specified level and unit.")
    unit_info = ielts_syllabus.get_ielts_unit_info(level, unit)
    return {
        "level": level,
        "unit": unit,
        "title": unit_info["title"] if unit_info else f"Unit {unit}",
        "markdown": content
    }

@router.get("/ielts-path/challenge/generate", response_model=schemas.TranslationChallengeResponse)
async def generate_ielts_guided_practice(
    level: int,
    unit: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await tutor_service.generate_ielts_practice_challenge(
        db=db,
        user_id=user.id,
        level=level,
        unit=unit
    )

@router.post("/translation_challenge/evaluate", response_model=schemas.TranslationEvaluationResponse)
@router.post("/ielts-path/evaluate", response_model=schemas.TranslationEvaluationResponse)
async def evaluate_challenge(
    request: schemas.TranslationEvaluationRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await tutor_service.evaluate_translation(db, user.id, request)

@router.post("/ielts-path/session/complete", response_model=schemas.UnitCompleteResponse)
async def complete_ielts_unit_session(
    request: schemas.UnitCompleteRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    score = request.precision_score
    if score <= 1.0:
        is_mastered = score >= 0.8
    else:
        is_mastered = score >= 80.0

    status = "mastered" if is_mastered else "in_progress"
    
    current_progress = await upsert_learning_path_progress(
        db,
        user.id,
        level=request.level,
        unit=request.unit,
        status=status,
        precision_score=request.precision_score,
        course_type="ielts"
    )
    
    unlocked_next = False
    if current_progress.status == "mastered":
        syllabus = ielts_syllabus.load_ielts_syllabus()
        level_data = syllabus.get(request.level, {})
        max_units = len(level_data.get("units", {}))
        
        next_level = request.level
        next_unit = request.unit + 1
        
        if next_unit > max_units:
            next_level = request.level + 1
            next_unit = 1
            
        if next_level in syllabus:
            await upsert_learning_path_progress(
                db,
                user.id,
                level=next_level,
                unit=next_unit,
                status="in_progress",
                course_type="ielts"
            )
            unlocked_next = True
            
    return schemas.UnitCompleteResponse(
        level=request.level,
        unit=request.unit,
        status=current_progress.status,
        precision_score=current_progress.precision_score,
        unlocked_next=unlocked_next
    )

from .services import smart_review_service

@router.get("/ielts-path/smart-review/suggest", response_model=schemas.SmartReviewSuggestionResponse)
async def get_smart_review_suggestion(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await smart_review_service.get_smart_review_suggestion(db, user.id, course_type="ielts")

# --- ENDPOINTS LISTENING IELTS ---

from .services import listening_tutor_service

@router.post("/ielts-listening/challenge/generate", response_model=schemas.ListeningChallengeResponse)
async def generate_ielts_listening_challenge(
    level: int,
    unit: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await listening_tutor_service.generate_listening_challenge(db, user.id, level, unit)

@router.post("/ielts-listening/evaluate", response_model=schemas.TranslationEvaluationResponse)
async def evaluate_ielts_listening_challenge(
    request: schemas.TranslationEvaluationRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await tutor_service.evaluate_translation(db, user.id, request)