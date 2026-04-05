# src/chat/services/presence_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from redis.asyncio import Redis
from src.config import settings

logger = logging.getLogger(__name__)

# Prefijos consistentes (Globales al módulo)
USER_STATUS_KEY = "user:{user_id}:status"
LAST_SEEN_KEY = "user:{user_id}:last_seen"

class PresenceService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        # Intentamos sacar el TTL de settings, si no, 60 segundos por defecto
        self.ttl = getattr(settings, "SECONDS_FOR_USER_STATUS_EXPIRATION", 60)

    def _get_keys(self, user_id: int) -> Tuple[str, str]:
        """Helper para generar las llaves de Redis de forma consistente."""
        return (
            USER_STATUS_KEY.format(user_id=user_id),
            LAST_SEEN_KEY.format(user_id=user_id)
        )

    def _decode(self, value: Any) -> Optional[str]:
        """Helper para manejar la decodificación de bytes de Redis de forma segura."""
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    async def set_user_online(self, user_id: int):
        """Marca al usuario como online y actualiza su timestamp de última conexión."""
        try:
            status_key, last_seen_key = self._get_keys(user_id)
            
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(status_key, "online", ex=self.ttl)
                pipe.set(last_seen_key, datetime.now(timezone.utc).isoformat())
                await pipe.execute()
                
            logger.debug(f"Presence: User {user_id} is now ONLINE")
        except Exception as e:
            logger.error(f"Error setting user {user_id} online: {e}")

    async def set_user_offline(self, user_id: int):
        """Elimina el estado online (usado al cerrar el WebSocket)."""
        try:
            status_key, _ = self._get_keys(user_id)
            await self.redis.delete(status_key)
        except Exception as e:
            logger.error(f"Error setting user {user_id} offline: {e}")

    async def get_user_presence(self, user_id: int) -> Dict[str, Optional[str]]:
        """Retorna un diccionario con el estado actual y el ISO de última conexión."""
        status_key, last_seen_key = self._get_keys(user_id)
        res = await self.redis.mget([status_key, last_seen_key])
        
        return {
            "status": self._decode(res[0]) or "offline",
            "last_seen": self._decode(res[1])
        }

    async def get_multiple_users_status(self, user_ids: List[int]) -> Dict[int, str]:
        """Consulta masiva de estados (optimizado para listas de chats)."""
        if not user_ids:
            return {}
            
        keys = [USER_STATUS_KEY.format(user_id=uid) for uid in user_ids]
        try:
            statuses = await self.redis.mget(keys)
            return {
                int(uid): (self._decode(s) or "offline") 
                for uid, s in zip(user_ids, statuses)
            }
        except Exception as e:
            logger.error(f"Error fetching multiple users presence: {e}")
            return {uid: "offline" for uid in user_ids}

    async def extend_session(self, user_id: int):
        """Refresca el tiempo de expiración (Heartbeat)."""
        status_key, _ = self._get_keys(user_id)
        await self.redis.expire(status_key, self.ttl)