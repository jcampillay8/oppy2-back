# src/onboarding/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User # Asegúrate de que la ruta al modelo User sea correcta
from . import schemas, services
from .test_services.writing import generate_writing_question
from .test_services import writing

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

# --- Endpoints Existentes (Perfil e Idioma) ---

@router.get("/status", response_model=schemas.OnboardingStatusResponse)
async def check_status(db: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    return await services.get_user_onboarding_status(db, current_user)

@router.patch("/update-profile", response_model=schemas.OnboardingStatusResponse)
async def update_profile(
    payload: schemas.OnboardingProfileUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 'services.update_onboarding_data' ahora devuelve el dict correcto para 'OnboardingStatusResponse'
    return await services.update_onboarding_data(db, current_user, payload)

@router.post("/select-language")
async def select_language(
    selection: schemas.LanguageSelection,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    return await services.set_user_target_language(db, current_user, selection)

@router.get("/writing/question", response_model=schemas.WritingQuestionResponse)
async def get_writing_question(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Necesitamos saber qué idioma eligió el usuario. 
    # Buscamos en su PlacementTest activo.
    from src.onboarding.models import PlacementTest
    from sqlalchemy import select
    
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
    question_text = await generate_writing_question(
        db, 
        current_user, 
        test_record.target_language
    )

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
    # 1. Obtenemos la evaluación de la IA (Score + Feedback + Nivel Sugerido por IA)
    result = await writing.evaluate_writing_response(
        db, 
        current_user.id, 
        payload.user_answer, 
        payload.target_language
    )

    # 2. 🚨 LA CORRECCIÓN: Sobrescribimos el nivel de la IA con tu escala oficial
    from src.onboarding.constants import calculate_cefr_level
    
    # Calculamos el nivel real según el score que dio la IA
    real_level = calculate_cefr_level(result["score"])
    
    # Actualizamos el diccionario del resultado antes de enviarlo al front o guardarlo
    result["suggested_level"] = real_level

    # 3. Actualizamos el registro del PlacementTest en la DB
    from src.onboarding.models import PlacementTest
    from sqlalchemy import select
    
    query = select(PlacementTest).where(
        PlacementTest.user_id == current_user.id,
        PlacementTest.target_language == payload.target_language # Mejor ser específicos con el idioma
    )
    db_result = await db.execute(query)
    test_record = db_result.scalars().first()

    if test_record:
        test_record.writing_result = result["score"]
        # Ahora sí guardamos el nivel real (ej: B2) en la base de datos
        test_record.suggested_level = real_level 
        await db.commit()

    # 4. Retornamos el resultado (que ahora dirá B2 en el JSON)
    return result