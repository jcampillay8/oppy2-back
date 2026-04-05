# src/managers/pubsub_manager.py
import json
import logging
from uuid import UUID
from typing import Optional, Any

import redis.asyncio as aioredis
from src.database import redis_pool

logger = logging.getLogger(__name__)

class RedisPubSubManager:
    """
    Gestiona la capa de mensajería asíncrona entre instancias de la App.
    Permite que los mensajes de IA lleguen al WebSocket correcto a través de Redis.
    """
    def __init__(self):
        self.redis_connection: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None

    async def _get_redis_connection(self) -> aioredis.Redis:
        """Obtiene una instancia de Redis desde el pool global."""
        return aioredis.Redis(connection_pool=redis_pool)

    async def connect(self):
        """Inicializa la conexión y el objeto PubSub."""
        if self.redis_connection is None:
            try:
                self.redis_connection = await self._get_redis_connection()
                self.pubsub = self.redis_connection.pubsub()
                logger.info("✅ RedisPubSubManager conectado exitosamente.")
            except Exception as e:
                logger.error(f"❌ Error conectando a Redis en PubSubManager: {e}")
                raise

    async def subscribe(self, chat_guid: UUID) -> aioredis.client.PubSub:
        """Se suscribe a un canal específico (basado en el GUID del chat)."""
        if self.pubsub is None:
            await self.connect()
        
        channel_name = str(chat_guid)
        await self.pubsub.subscribe(channel_name)
        logger.debug(f"📡 Suscrito al canal de Redis: {channel_name}")
        return self.pubsub

    async def unsubscribe(self, chat_guid: UUID):
        """Cancela la suscripción a un canal."""
        if self.pubsub:
            channel_name = str(chat_guid)
            await self.pubsub.unsubscribe(channel_name)
            logger.debug(f"🔇 Desuscrito del canal: {channel_name}")

    async def publish(self, chat_guid: UUID, message: Any):
        """
        Publica un mensaje en un canal de Redis.
        Convierte automáticamente dicts a JSON válido para el frontend.
        """
        if self.redis_connection is None:
            await self.connect()

        channel = str(chat_guid)
        
        try:
            if isinstance(message, dict):
                # ✅ Usamos json.dumps para asegurar compatibilidad con Flutter (JSON estándar)
                payload = json.dumps(message)
            elif isinstance(message, str):
                payload = message
            elif isinstance(message, (bytes, bytearray)):
                payload = message
            else:
                # Intento genérico de conversión si es otro tipo de objeto
                payload = json.dumps(message)

            await self.redis_connection.publish(channel, payload)
            
        except (TypeError, ValueError) as e:
            logger.error(f"❌ Fallo al serializar mensaje para Redis: {e}")
            raise

    async def disconnect(self):
        """Cierra las conexiones activas de Redis."""
        if self.redis_connection:
            await self.redis_connection.close()
            self.redis_connection = None
            self.pubsub = None
            logger.info("🔌 RedisPubSubManager desconectado.")