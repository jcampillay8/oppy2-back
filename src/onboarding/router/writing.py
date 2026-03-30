# src/onboarding/router/writing.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User
from src.onboarding import schemas
from src.onboarding.test_services import writing
from src.onboarding.models import PlacementTest, PlacementTestDetail
from src.onboarding.constants import calculate_cefr_level

# IMPORTANTE: Aquí NO ponemos prefix="/onboarding" porque ya lo pone el __init__.py
# Solo definimos el tag para la documentación Swagger.
router = APIRouter(tags=["Writing Test"])

@router.get("/writing/question", response_model=schemas.WritingQuestionResponse)
async def get_writing_question(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Buscamos el test activo
    result = await db.execute(
        select(PlacementTest).where(PlacementTest.user_id == current_user.id)
    )
    test_record = result.scalars().first()

    if not test_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Debes seleccionar un idioma antes de iniciar el test."
        )

    # 2. Generamos la pregunta con Gemini
    question_text = await writing.generate_writing_question(
        db, 
        current_user, 
        test_record.target_language
    )

    # 3. UPSERT del detalle
    detail_query = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == test_record.id,
        PlacementTestDetail.section == "writing"
    )
    detail_res = await db.execute(detail_query)
    detail = detail_res.scalar_one_or_none()

    if not detail:
        detail = PlacementTestDetail(
            placement_test_id=test_record.id,
            section="writing",
            question_text=question_text
        )
        db.add(detail)
    else:
        detail.question_text = question_text
        detail.user_response = None
        detail.feedback_text = None
        detail.score = None

    await db.commit()
    return {
        "question": question_text,
        "target_language": test_record.target_language
    }

@router.post("/writing/evaluate", response_model=schemas.WritingEvaluationResponse)
async def post_writing_evaluation(
    payload: schemas.WritingSubmission,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Evaluación de IA
    result = await writing.evaluate_writing_response(
        db, 
        current_user.id, 
        payload.user_answer, 
        payload.target_language
    )

    # 2. Mapeo de nivel CEFR
    real_level = calculate_cefr_level(result["score"])
    result["suggested_level"] = real_level

    # 3. Actualización de Test Principal
    query = select(PlacementTest).where(
        PlacementTest.user_id == current_user.id,
        PlacementTest.target_language == payload.target_language
    )
    db_result = await db.execute(query)
    test_record = db_result.scalars().first()

    if not test_record:
        raise HTTPException(status_code=404, detail="Test no encontrado")

    test_record.writing_result = result["score"]
    test_record.suggested_level = real_level 

    # 4. Actualización del Detalle
    detail_query = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == test_record.id,
        PlacementTestDetail.section == "writing"
    )
    detail_res = await db.execute(detail_query)
    detail = detail_res.scalar_one_or_none()

    if detail:
        detail.user_response = payload.user_answer
        detail.feedback_text = result["feedback"]
        detail.score = result["score"]
    
    await db.commit()
    return result