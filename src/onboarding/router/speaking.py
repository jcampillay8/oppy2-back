# src/onboarding/router/speaking.py
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_async_session
from src.onboarding.test_services.speaking import SpeakingTestService
from src.dependencies import get_current_user 
from src.onboarding.models import PlacementTestDetail, PlacementTest

router = APIRouter(prefix="/speaking", tags=["Onboarding Speaking"])
speaking_service = SpeakingTestService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/evaluate")
async def evaluate_speaking_audio(
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    try:
        # 1. Transcribir el audio (Aquí deberías llamar a tu función de Whisper)
        # audio_bytes = await audio_file.read()
        # transcript = await transcribe_audio(audio_bytes) 
        transcript = "I want to learn English because it is essential for my career as an industrial engineer and to grow OppyChat." 

        # 2. Evaluar con Gemini
        evaluation_data = await speaking_service.evaluate_speaking(
            db=db, 
            user_id=current_user.id, 
            transcript=transcript, 
            target_language="English"
        )

        # 3. Buscar el test
        result = await db.execute(select(PlacementTest).where(PlacementTest.user_id == current_user.id))
        test = result.scalars().first()

        # 4. Upsert en PlacementTestDetail
        detail_result = await db.execute(
            select(PlacementTestDetail).where(
                PlacementTestDetail.placement_test_id == test.id,
                PlacementTestDetail.section == "speaking"
            )
        )
        existing_detail = detail_result.scalars().first()

        score_value = float(evaluation_data.get("score", 10.0))
        feedback = evaluation_data.get("feedback", "Buen trabajo")

        if existing_detail:
            existing_detail.user_response = transcript # GUARDAMOS LA TRANSCRIPCIÓN REAL
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
        
        # 5. Sincronizar con la tabla principal (IMPORTANTE PARA FLUTTER)
        test.speaking_result = score_value
        await db.commit()

        return {
            "status": "success",
            "evaluation": evaluation_data
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))