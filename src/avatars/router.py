# src/avatars/router.py
from fastapi import APIRouter
# Importamos los endpoints específicos (suponiendo que moviste la lógica a avatar_endpoints)
from .router.avatar_endpoints import router as avatar_endpoints_router

# Definimos el router principal del módulo de Avatares
avatar_router = APIRouter(
    prefix="/avatars",
    tags=["Avatars"]
)

# Incluimos las rutas específicas
avatar_router.include_router(avatar_endpoints_router)