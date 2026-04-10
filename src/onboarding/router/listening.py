# src/onboarding/router/listening.py
import base64
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User
from src.onboarding.models import PlacementTest, PlacementTestDetail
from src.onboarding.test_services.listening import listening_service 
from .. import schemas

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Listening Test"])

@router.get("/listening/question")
async def get_listening_question(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Genera el script de listening, el audio en base64 y las preguntas.
    Persiste la tarea en la base de datos y retorna el contenido para Flutter.
    """
    if not current_user.bio:
        raise HTTPException(status_code=400, detail="User biography is required.")

    # 1. Generar tarea y audio mediante el servicio
    # El servicio ya debe estar actualizado para manejar el argumento 'messages'
    task_data = await listening_service.generate_listening_task(
        db, 
        current_user.id, 
        current_user.bio
    )

    # 2. Manejo seguro del audio
    # Usamos .pop() con un valor por defecto para que no lance KeyError si el fallback falló
    audio_bytes = task_data.pop("audio_content", b"")
    
    if not audio_bytes:
        logger.warning(f"No audio content generated for user {current_user.id}")
        # Opcional: podrías usar un audio por defecto aquí si lo deseas
    
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else ""

    # 3. Persistencia en PlacementTest (Async)
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

    # 4. Upsert del detalle de la sección 'listening'
    detail_stmt = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == placement_test.id,
        PlacementTestDetail.section == "listening"
    )
    detail_result = await db.execute(detail_stmt)
    detail = detail_result.scalar_one_or_none()
    
    # Aseguramos que task_data sea un diccionario antes de serializar
    if isinstance(task_data, str):
        try:
            task_data = json.loads(task_data)
        except json.JSONDecodeError:
            logger.error("Failed to parse task_data from string during persistence.")
            raise HTTPException(status_code=500, detail="Error processing task data.")

    question_json = json.dumps(task_data)

    if detail:
        detail.question_text = question_json
        detail.score = None  # Reiniciamos el score si se vuelve a generar
    else:
        detail = PlacementTestDetail(
            placement_test_id=placement_test.id,
            section="listening",
            question_text=question_json
        )
        db.add(detail)

    await db.commit()

    return {
        "task": task_data, # title, script, questions
        "audio_base64": audio_b64,
        "mime_type": "audio/mp3"
    }

@router.post("/listening/evaluate")
async def evaluate_listening(
    payload: schemas.ListeningSubmission, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Recuperar el PlacementTest del usuario
    test_stmt = select(PlacementTest).where(PlacementTest.user_id == current_user.id)
    result = await db.execute(test_stmt)
    placement_test = result.scalar_one_or_none()
    
    if not placement_test:
        raise HTTPException(status_code=404, detail="Placement test record not found.")

    # 2. Recuperar el detalle de la sección 'listening'
    detail_stmt = select(PlacementTestDetail).where(
        PlacementTestDetail.placement_test_id == placement_test.id,
        PlacementTestDetail.section == "listening"
    )
    detail_result = await db.execute(detail_stmt)
    detail = detail_result.scalar_one_or_none() # <--- AQUÍ SE DEFINE 'detail'

    if not detail:
        raise HTTPException(status_code=404, detail="Listening test details not found.")

    # 3. Ahora sí, 'detail' existe y puedes usarlo
    stored_task = json.loads(detail.question_text)
    
    # Extraer las respuestas correctas guardadas anteriormente
    correct_answers = [q['correct_option'] for q in stored_task['questions']]
    
    # 4. Calcular nivel (Usando tu servicio)
    evaluation = listening_service.calculate_listening_level(payload.answers, correct_answers)
    
    # 5. Persistir resultados
    detail.user_response = json.dumps(payload.answers)
    detail.score = evaluation["score"]
    
    # Actualizar el score global en el test principal
    placement_test.listening_result = evaluation["score"]
    
    await db.commit()
    
    return {
        "score": evaluation["score"],
        "assigned_level": evaluation["level"],
        "message": f"Listening completed: {evaluation['level']}"
    }