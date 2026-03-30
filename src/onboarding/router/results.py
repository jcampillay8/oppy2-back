# src/onboarding/router/results.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.dependencies import get_current_user
from src.onboarding.models import PlacementTest
from src.onboarding.test_services.consolidator import TestConsolidator

router = APIRouter(prefix="/onboarding", tags=["Final Results"])
consolidator = TestConsolidator()

@router.get("/final-status")
async def get_final_status(
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    # 1. Recuperar el test y sus resultados
    result = await db.execute(
        select(PlacementTest).where(PlacementTest.user_id == current_user.id)
    )
    test = result.scalar_one_or_none()

    # 2. Preparar diccionario de scores
    scores = {
        "writing": test.writing_result or 0.0,
        "reading": test.reading_result or 0.0,
        "listening": test.listening_result or 0.0,
        "speaking": test.speaking_result or 0.0
    }

    # 3. Calcular promedio y nivel global
    avg_score = sum(scores.values()) / 4
    global_level = consolidator.determine_global_level(avg_score)

    # 4. Generar el Análisis narrativo con IA
    ai_analysis = await consolidator.generate_final_analysis(db, current_user.id, scores)

    # 5. Actualizar el test principal
    test.suggested_level = global_level
    test.is_completed = True
    await db.commit()

    return {
        "global_level": global_level,
        "level_name": "Intermedio Alto" if global_level == "B2" else "Principiante",
        "scores": scores,
        "ai_analysis": ai_analysis["analysis_text"],
        "suggested_plan": ai_analysis["suggested_plan"],
        "next_steps": [
            {"icon": "chat", "title": "Práctica Diaria", "desc": "5 min de conversación"},
            {"icon": "book", "title": "Gramática", "desc": "Repaso de tiempos"}
        ]
    }