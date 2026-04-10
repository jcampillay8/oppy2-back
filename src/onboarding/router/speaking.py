# src/onboarding/router/speaking.py
import logging
import json
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.onboarding.test_services.speaking import SpeakingTestService
from src.dependencies import get_current_user 
from src.onboarding.models import PlacementTestDetail, PlacementTest

# Instancia del servicio
speaking_service = SpeakingTestService()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speaking", tags=["Onboarding Speaking"])

@router.post("/evaluate")
async def evaluate_speaking_audio(
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    try:
        # 1. Simulación de transcripción (Luego integrarás Whisper aquí)
        # audio_bytes = await audio_file.read()
        transcript = "I want to learn English because it is essential for my career as an industrial engineer and to grow OppyChat." 

        # 2. Evaluación con el servicio (que ya corregimos con 'messages')
        evaluation_data = await speaking_service.evaluate_speaking(
            db=db, 
            user_id=current_user.id, 
            transcript=transcript, 
            target_language="English"
        )

        # 3. Buscar o crear el PlacementTest (Seguridad extra)
        stmt = select(PlacementTest).where(
            PlacementTest.user_id == current_user.id,
            PlacementTest.target_language == "en" # Opcional: filtrar por idioma
        )
        result = await db.execute(stmt)
        test = result.scalar_one_or_none()

        if not test:
            test = PlacementTest(user_id=current_user.id, target_language="en")
            db.add(test)
            await db.flush() # Para obtener el test.id

        # 4. Upsert en PlacementTestDetail
        detail_stmt = select(PlacementTestDetail).where(
            PlacementTestDetail.placement_test_id == test.id,
            PlacementTestDetail.section == "speaking"
        )
        detail_result = await db.execute(detail_stmt)
        existing_detail = detail_result.scalar_one_or_none()

        # Normalización de datos para la DB
        score_value = float(evaluation_data.get("score", 10.0))
        feedback = evaluation_data.get("feedback", "Buen trabajo")

        if existing_detail:
            existing_detail.user_response = transcript
            existing_detail.feedback_text = feedback
            existing_detail.score = score_value
        else:
            new_detail = PlacementTestDetail(
                placement_test_id=test.id,
                section="speaking",
                question_text="Why is it important for you to learn English?", 
                user_response=transcript,
                feedback_text=feedback,
                score=score_value
            )
            db.add(new_detail)
        
        # 5. Actualizar tabla principal para el progreso global
        test.speaking_result = score_value
        
        await db.commit()

        return {
            "status": "success",
            "evaluation": evaluation_data
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error in evaluate_speaking_audio: {str(e)}")
        # Importante: devolver el error real ayuda a debuguear en Flutter
        raise HTTPException(status_code=500, detail=str(e))