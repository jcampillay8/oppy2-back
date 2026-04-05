# src/routers.py
from src.authentication.router import auth_router
from src.authentication.google_oauth_router import google_router
from src.authentication.user_details_router import user_details_router
from src.registration.router import account_router
from src.onboarding.router import router as onboarding_router
from src.avatars.router import avatar_router
from src.learning_analysis.router import router as learning_router

# IMPORTAMOS EL NUEVO ROUTER DE CHAT
from src.chat.router import chat_router

# Lista de routers activos para OppyChat
routers = [
    auth_router,
    google_router,
    user_details_router,
    account_router,
    onboarding_router,
    chat_router,
    avatar_router,
    learning_router
]