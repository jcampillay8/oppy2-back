# src/onboarding/router.py

# Importamos el router orquestador desde la nueva carpeta src/onboarding/router/
from .router import router as onboarding_package_router

# Lo exponemos con el mismo nombre 'router' para que src/routers.py lo encuentre
router = onboarding_package_router