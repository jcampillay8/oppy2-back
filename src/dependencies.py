# src/dependencies.py
from typing import Annotated, AsyncGenerator, Optional
from fastapi import WebSocket, Query
from jose import jwt, JWTError # <--- JWTError ya está importado
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.authentication.services import get_user_by_login_identifier
from src.config import settings
from src.database import get_async_session, redis_pool, async_session_maker
from src.models import User
from pydantic import ValidationError

# Esto permite que Swagger (docs) y Flutter envíen el token en el Header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login") 

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db_session: AsyncSession = Depends(get_async_session),
) -> User:
    try:
        payload = jwt.decode(token, settings.JWT_ACCESS_SECRET_KEY, algorithms=[settings.ENCRYPTION_ALGORITHM])
        login_identifier: str = payload.get("sub")
        if not login_identifier:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError: # <--- CAMBIO AQUÍ: Usamos JWTError en lugar de jwt.InvalidTokenError
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Access Token")

    user: User | None = await get_user_by_login_identifier(db_session, login_identifier=login_identifier)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    # get_current_user ya maneja si el usuario está "eliminado" (inactivo en este contexto)
    return current_user

async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin user"
        )
    return current_user

async def get_cache_setting():
    return settings.REDIS_CACHE_ENABLED


async def get_cache() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=redis_pool)

async def get_current_user_ws(
    websocket: WebSocket,
    db_session: AsyncSession = Depends(get_async_session),
    token: Optional[str] = Query(None), # Permite recibir ?token=XYZ en la URL del WS
) -> User:
    """
    Versión de get_current_user específica para WebSockets.
    Busca el token en los Query Params o en los Headers.
    """
    # 1. Intentar sacar el token del Header si no viene en Query
    if not token:
        authorization = websocket.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    try:
        payload = jwt.decode(
            token, 
            settings.JWT_ACCESS_SECRET_KEY, 
            algorithms=[settings.ENCRYPTION_ALGORITHM]
        )
        login_identifier: str = payload.get("sub")
        if not login_identifier:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
            
        user = await get_user_by_login_identifier(db_session, login_identifier=login_identifier)
        
        if not user or user.is_deleted:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
            
        return user

    except (JWTError, jwt.ExpiredSignatureError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None