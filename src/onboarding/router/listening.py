# src/onboarding/router/listening.py
import base64
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User
from src.onboarding.models import PlacementTest, PlacementTestDetail
from src.onboarding.test_services.listening import listening_service # Instancia global
from .. import schemas

router = APIRouter(tags=["Listening Test"])

@router.get("/listening/question")
async def get_listening_question(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user.bio:
        raise HTTPException(status_code=400, detail="Bio required.")

    # 1. Generar tarea y audio
    task_data = await listening_service.generate_listening_task(db, current_user.id, current_user.bio)
    
    # 2. Extraer audio para el response y limpiar task_data para la DB
    audio_bytes = task_data.pop("audio_content")
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    # 3. Persistencia (Siguiendo tu lógica de Reading)
    test_stmt = select(PlacementTest).where(PlacementTest.user_id == current_user.id)
    result = await db.execute(test_stmt)
    placement_test = result.scalar_one_or_none()
    
    if not placement_test:
        placement_test = PlacementTest(user_id=current_user.id, target_language="en")
        db.add(placement_test)
        await db.flush()

    # Upsert del detalle de sección
    detail_stmt = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == placement_test.id,
        PlacementTestDetail.section == "listening"
    )
    detail_result = await db.execute(detail_stmt)
    detail = detail_result.scalar_one_or_none()
    
    question_json = json.dumps(task_data)

    if detail:
        detail.question_text = question_json
    else:
        detail = PlacementTestDetail(
            placement_test_id=placement_test.id,
            section="listening",
            question_text=question_json
        )
        db.add(detail)

    await db.commit()

    return {
        "task": task_data, # Incluye script, title y questions
        "audio_base64": audio_b64,
        "mime_type": "audio/mp3"
    }

@router.post("/listening/evaluate")
async def evaluate_listening(
    payload: schemas.ListeningSubmission, # Asegúrate de crear este schema similar al de Reading
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Lógica de recuperación de detail (idéntica a Reading)
    # ... (omitido por brevedad, recupera el PlacementTestDetail de 'listening')
    
    stored_task = json.loads(detail.question_text)
    correct_answers = [q['correct_option'] for q in stored_task['questions']]
    
    evaluation = listening_service.calculate_listening_level(payload.answers, correct_answers)
    
    detail.user_response = json.dumps(payload.answers)
    detail.score = evaluation["score"]
    placement_test.listening_result = evaluation["score"]
    
    await db.commit()
    
    return {
        "score": evaluation["score"],
        "assigned_level": evaluation["level"],
        "message": f"Listening completed: {evaluation['level']}"
    }