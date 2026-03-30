# src/onboarding/router/__init__.py
from fastapi import APIRouter
from .onboarding import router as onboarding_router
from .reading import router as reading_router
from .writing import router as writing_router
from .listening import router as listening_router
from .speaking import router as speaking_router
from .results import router as results_router

# Prefijo global: todas las rutas aquí colgarán de /onboarding
router = APIRouter(prefix="/onboarding")

# Registro de sub-routers
router.include_router(onboarding_router)
router.include_router(writing_router)
router.include_router(reading_router)
router.include_router(listening_router)
router.include_router(speaking_router)
router.include_router(results_router)