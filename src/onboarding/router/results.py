# src/onboarding/router/results.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_async_session
from src.dependencies import get_current_user
from src.onboarding.models import PlacementTest
from src.onboarding.test_services.consolidator import TestConsolidator

router = APIRouter(tags=["Final Results"])
consolidator = TestConsolidator()

@router.get("/final-status")
async def get_final_status(
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    # 1. Recuperar el test principal del usuario
    result = await db.execute(
        select(PlacementTest).where(PlacementTest.user_id == current_user.id)
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test no encontrado")

    # 2. Mapear scores asegurando que sean floats para la compatibilidad con Flutter (double)
    scores = {
        "writing": float(test.writing_result or 0.0),
        "reading": float(test.reading_result or 0.0),
        "listening": float(test.listening_result or 0.0),
        "speaking": float(test.speaking_result or 0.0)
    }

    # 3. Consolidación de resultados
    # Calculamos el promedio para determinar el nivel global CEFR (A1-C2)
    avg_score = sum(scores.values()) / 4
    global_level = consolidator.determine_global_level(avg_score)
    
    # Generar el análisis narrativo real de la IA pasando el test.id
    # Esto permite que la IA lea el feedback_text de cada sección en PlacementTestDetail
    ai_data = await consolidator.generate_final_analysis(
        db=db, 
        user_id=current_user.id, 
        test_id=test.id, 
        scores=scores
    )

    # 4. Actualizar el estado del test en la base de datos
    test.suggested_level = global_level
    test.is_completed = True
    await db.commit()

    # Mapeo amigable para el nombre del nivel en la UI de Flutter
    level_names_map = {
        "A1": "Principiante",
        "A2": "Elemental",
        "B1": "Intermedio",
        "B2": "Intermedio Alto",
        "C1": "Avanzado",
        "C2": "Maestría"
    }

    # 5. Retornar el JSON estructurado para el modelo TestResult.fromJson de la App
    return {
        "global_level": global_level,  # Ej: "B1" -> globalLevel en Dart
        "level_name": level_names_map.get(global_level, "Principiante"),
        "scores": scores,              # Mapea a Map<String, double>
        "ai_analysis": ai_data.get("analysis_text", "Análisis no disponible"),
        "suggested_plan": ai_data.get("suggested_plan", "Plan Personalizado"),
        "next_steps": [
            {
                "icon": "mic", 
                "title": "Speaking", 
                "desc": "Enfócate en la fluidez y conectores"
            },
            {
                "icon": "edit", 
                "title": "Writing", 
                "desc": "Revisa la estructura de tus párrafos"
            },
            {
                "icon": "auto_stories", 
                "title": "Reading", 
                "desc": "Lee artículos técnicos de ingeniería"
            }
        ]
    }