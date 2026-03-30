# src/onboarding/router/onboarding.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user 
from src.models import User
from .. import schemas, services  # Subimos un nivel para encontrar schemas y services

# ✅ Eliminamos prefix="/onboarding" porque ya lo maneja el __init__.py del paquete router
router = APIRouter(tags=["Onboarding Core"])

# --- Endpoints de Perfil e Idioma ---

@router.get("/status", response_model=schemas.OnboardingStatusResponse)
async def check_status(
    db: AsyncSession = Depends(get_async_session), 
    current_user: User = Depends(get_current_user)
):
    """Verifica el estado actual del proceso de onboarding del usuario."""
    return await services.get_user_onboarding_status(db, current_user)

@router.patch("/update-profile", response_model=schemas.OnboardingStatusResponse)
async def update_profile(
    payload: schemas.OnboardingProfileUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza la información del perfil (bio, etc.) durante el onboarding."""
    return await services.update_onboarding_data(db, current_user, payload)

@router.post("/select-language")
async def select_language(
    selection: schemas.LanguageSelection,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Establece el idioma objetivo que el usuario desea aprender."""
    return await services.set_user_target_language(db, current_user, selection)