# src/onboarding/router/__init__.py
from fastapi import APIRouter
from .onboarding import router as onboarding_router
from .reading import router as reading_router
from .writing import router as writing_router

# El prefijo global para todo el módulo de onboarding
router = APIRouter(prefix="/onboarding")

# Al incluirlos así, las rutas resultantes serán:
# /onboarding/status
# /onboarding/writing/question
# /onboarding/reading/question
router.include_router(onboarding_router)
router.include_router(writing_router)
router.include_router(reading_router)