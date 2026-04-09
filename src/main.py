import logging
import logging.config
import redis.asyncio as aioredis
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# 🛑 COMENTADO: Causa ImportError en Python 3.12 con uv
# from fastapi_limiter.fastapi_limiter import FastAPILimiter 
from fastapi_pagination import add_pagination
from sqladmin import Admin
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.config import LOGGING_CONFIG, settings
from src.database import engine, redis_pool
from src.routers import routers
from src.models import User 
from src.registration.router import account_router

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# ==============================
# 🌐 Middleware for HTTPS redirect (Railway & proxies)
# ==============================
class ForceHTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # SI ESTAMOS EN DESARROLLO, NO REDIRIGIR A HTTPS
        if settings.ENVIRONMENT == "development":
            return await call_next(request)

        x_forwarded_proto = request.headers.get("x-forwarded-proto")
        if x_forwarded_proto == "https" and request.url.scheme == "http":
            request.scope["scheme"] = "https"
            request._url = request.url.replace(scheme="https")

        return await call_next(request)

# ==============================
# 🪵 Logging & Sentry
# ==============================
if settings.SENTRY_DSN and settings.ENVIRONMENT != "test":
    logging.config.dictConfig(LOGGING_CONFIG)
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        enable_tracing=True,
    )

logger = logging.getLogger(__name__)

# ==============================
# 🚀 FastAPI App Init
# ==============================
app = FastAPI(
    title="OppyChat API",
    description="Backend para práctica de inglés con IA",
    version="2.0.0"
)

# ==============================
# 🛡️ Trusted Hosts & Middlewares
# ==============================
if settings.ENVIRONMENT == "production":
    trusted_hosts = [
        "api.oppychat.com", 
        "*.oppychat.com",
        "oppy2-back-production.up.railway.app", # <-- AGREGA ESTO
        "*.up.railway.app"                       # <-- OPCIONAL: Para aceptar cualquier subdominio de Railway
    ]
else:
    trusted_hosts = ["localhost", "127.0.0.1", "10.0.2.2", "0.0.0.0", "*.ngrok-free.app"]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
app.add_middleware(ForceHTTPSRedirectMiddleware)
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    session_cookie="oppy_session"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# 🧭 Routers & Config
# ==============================
for router in routers:
    app.include_router(router)

add_pagination(app)

# ==============================
# ⏯️ Startup & Shutdown
# ==============================
@app.on_event("startup")
async def startup():
    logger.info(f"🚀 OppyChat API arrancando en modo: {settings.ENVIRONMENT}")
    
    # Construir URL de Redis con contraseña si existe
    if settings.REDIS_PASSWORD:
        redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    else:
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

    try:
        # Usamos el cliente asíncrono para verificar la conexión
        redis_client = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
        await redis_client.ping()
        logger.info(f"✅ Conexión a Redis exitosa en {settings.REDIS_HOST}")
        # Aquí podrías guardar el cliente en app.state si lo necesitas globalmente
        app.state.redis = redis_client 
    except Exception as e:
        logger.error(f"❌ Error crítico conectando a Redis: {e}")
        # En desarrollo podrías dejarlo pasar, en producción quizás quieras que falle

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Cerrando aplicación...")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Esto imprimirá en tu consola de Docker el error exacto de Pydantic
    print(f"--- ERRORES DE VALIDACIÓN ---")
    print(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )