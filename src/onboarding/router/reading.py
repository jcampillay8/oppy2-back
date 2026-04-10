# src/onboarding/router/reading.py
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User
from src.onboarding.models import PlacementTest, PlacementTestDetail
from src.onboarding.test_services.reading import ReadingTestService
from .. import schemas 

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Reading Test"])
reading_service = ReadingTestService()

@router.get("/reading/question", response_model=dict)
async def get_reading_question(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user.bio:
        raise HTTPException(status_code=400, detail="User biography is required.")
        
    task_data = await reading_service.generate_reading_task(
        db=db, 
        user_id=current_user.id, 
        user_bio=current_user.bio
    )

    # Normalización: Aseguramos que sea un dict para el dumps
    if isinstance(task_data, str):
        try:
            task_data = json.loads(task_data)
        except:
            logger.error("Failed to parse task_data string")

    # 1. Buscar o crear el PlacementTest
    test_stmt = select(PlacementTest).where(
        PlacementTest.user_id == current_user.id,
        PlacementTest.target_language == "en"
    )
    result = await db.execute(test_stmt)
    placement_test = result.scalar_one_or_none()
    
    if not placement_test:
        placement_test = PlacementTest(user_id=current_user.id, target_language="en")
        db.add(placement_test)
        await db.flush()

    # 2. Upsert del detalle
    detail_stmt = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == placement_test.id,
        PlacementTestDetail.section == "reading"
    )
    detail_result = await db.execute(detail_stmt)
    detail = detail_result.scalar_one_or_none()
    
    # Serializamos una sola vez para la DB
    question_json = json.dumps(task_data)

    if detail:
        detail.question_text = question_json
        detail.score = None
    else:
        detail = PlacementTestDetail(
            placement_test_id=placement_test.id,
            section="reading",
            question_text=question_json
        )
        db.add(detail)

    await db.commit()
    return task_data

@router.post("/reading/evaluate")
async def evaluate_reading(
    payload: schemas.ReadingSubmission,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Evalúa las respuestas y asigna nivel CEFR según aciertos."""
    
    # 1. Obtener test y detalle (Mismo código de búsqueda)
    test_res = await db.execute(select(PlacementTest).where(
        PlacementTest.user_id == current_user.id,
        PlacementTest.target_language == "en"
    ))
    placement_test = test_res.scalar_one_or_none()
    
    if not placement_test:
        raise HTTPException(status_code=404, detail="Test not found.")

    detail_res = await db.execute(select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == placement_test.id,
        PlacementTestDetail.section == "reading"
    ))
    detail = detail_res.scalar_one_or_none()

    if not detail:
        raise HTTPException(status_code=400, detail="Reading task not generated.")

    # 2. Evaluar con la nueva lógica de niveles
    stored_task = json.loads(detail.question_text)
    correct_answers = [q['correct_option'] for q in stored_task['questions']]
    
    # Llamamos a la nueva función de nivel
    evaluation = reading_service.calculate_reading_level(payload.answers, correct_answers)
    final_score = evaluation["score"]
    assigned_level = evaluation["level"]

    # 3. Persistir
    detail.user_response = json.dumps(payload.answers)
    detail.score = final_score
    
    # Actualizamos el resultado de reading en el test principal
    placement_test.reading_result = final_score
    
    # OPCIONAL: Si quieres guardar el nivel literal en algún campo de la DB
    # placement_test.suggested_level = assigned_level 
    
    await db.commit()
    
    return {
        "score": final_score,
        "assigned_level": assigned_level,
        "correct_answers": correct_answers,
        "message": f"Reading section completed. Level attained: {assigned_level}"
    }