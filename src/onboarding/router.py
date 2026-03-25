# src/onboarding/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User # Asegúrate de que la ruta al modelo User sea correcta
from . import schemas, services
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

# --- NUEVOS Endpoints para el Test de Writing ---

@router.post("/writing/setup", response_model=schemas.WritingTopicResponse)
async def setup_writing_test(
    selection: schemas.WritingCategorySelection,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    PASO 1: El usuario elige una categoría (narrative, opinion, descriptive).
    El backend busca una pregunta asignada o elige una al azar y la devuelve.
    """
    try:
        topic = await writing.get_or_assign_writing_topic(db, current_user.id, selection)
        return topic # FastAPI usará el schema WritingTopicResponse para filtrar los campos
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al asignar el tema de escritura.")

@router.post("/writing/evaluate")
async def submit_writing_test(
    payload: schemas.WritingAnswer,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    try:
        score = await writing.evaluate_writing_task(
            db=db,
            user_id=current_user.id,
            target_language=payload.target_language,
            user_text=payload.text
        )
        return {
            "status": "success", 
            "score": score,
            "message": "Evaluación completada con éxito."
        }
    except Exception as e:
        # Esto asegura que el frontend reciba un 500 claro si la IA falla
        raise HTTPException(status_code=500, detail="Error durante la evaluación de IA.")

# --- Finalización ---

@router.post("/submit-test", response_model=schemas.PlacementTestResponse)
async def submit_placement_test(
    payload: schemas.PlacementTestSubmit,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Cierra el proceso de Onboarding una vez que todos los tests (W/R/L/S) terminan."""
    return await services.process_test_results(db, current_user, payload)