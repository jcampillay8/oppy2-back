# src/chat/manager.py
import asyncio
import json
import logging
from typing import Optional, Dict, Set, Any
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState
from src.managers.pubsub_manager import RedisPubSubManager

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.handlers: Dict[str, Any] = {}
        self.chats: Dict[str, Set[WebSocket]] = {} 
        self.pubsub_manager = RedisPubSubManager()
        self.user_guid_to_websocket: Dict[str, Set[WebSocket]] = {}
        self.pubsub_subscriber_task: Optional[asyncio.Task] = None

    def add_handler(self, message_type: str, func):
        """Registra un handler para un tipo de mensaje específico."""
        self.handlers[message_type] = func

    async def connect_socket(self, websocket: WebSocket):
        """Acepta la conexión inicial del WebSocket."""
        await websocket.accept()

    async def add_user_socket_connection(self, user_guid: str, websocket: WebSocket):
        """Asocia un WebSocket a un GUID de usuario (para mensajes directos)."""
        self.user_guid_to_websocket.setdefault(user_guid, set()).add(websocket)

    async def add_user_to_chat(self, chat_guid: str, websocket: WebSocket):
        """Añade un socket a un chat y asegura la suscripción a Redis."""
        await self.pubsub_manager.connect()

        if chat_guid not in self.chats:
            # Suscribirse al canal de Redis (PubSub)
            await self.pubsub_manager.subscribe(chat_guid)

            # Iniciar el loop de lectura si no existe
            if self.pubsub_subscriber_task is None or self.pubsub_subscriber_task.done():
                self.pubsub_subscriber_task = asyncio.create_task(
                    self._pubsub_data_reader()
                )

            self.chats[chat_guid] = {websocket}
        else:
            self.chats[chat_guid].add(websocket)

    async def broadcast_to_chat(self, chat_guid: str, message: Any) -> None:
        """Publica un mensaje en Redis para que todas las instancias lo procesen."""
        await self.pubsub_manager.publish(chat_guid, message)

    async def remove_user_from_chat(self, chat_guid: str, websocket: WebSocket) -> None:
        """Limpia el socket del set de chats y desuscribe de Redis si está vacío."""
        if chat_guid in self.chats and websocket in self.chats[chat_guid]:
            self.chats[chat_guid].remove(websocket)
            if not self.chats[chat_guid]:
                del self.chats[chat_guid]
                await self.pubsub_manager.unsubscribe(chat_guid)

    async def remove_user_guid_to_websocket(self, user_guid: str, websocket: WebSocket):
        """Limpia la asociación usuario-socket."""
        if user_guid in self.user_guid_to_websocket:
            self.user_guid_to_websocket[user_guid].discard(websocket)
            if not self.user_guid_to_websocket[user_guid]:
                del self.user_guid_to_websocket[user_guid]

    async def _pubsub_data_reader(self):
        """
        Escucha mensajes de Redis y los envía a los WebSockets conectados localmente.
        """
        try:
            pubsub = self.pubsub_manager.pubsub
            if not pubsub:
                return

            while True:
                # Obtenemos mensaje con timeout para no bloquear el hilo infinitamente
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None:
                    chat_guid = message["channel"].decode("utf-8")
                    data = message["data"]
                    
                    sockets = self.chats.get(chat_guid)
                    if sockets:
                        # Detectar si el mensaje es texto o binario (bytes)
                        is_text = True
                        if isinstance(data, bytes):
                            try:
                                payload = data.decode("utf-8")
                            except UnicodeDecodeError:
                                payload = data
                                is_text = False
                        else:
                            payload = str(data)

                        for socket in list(sockets):
                            try:
                                if socket.application_state == WebSocketState.CONNECTED:
                                    if is_text:
                                        await socket.send_text(payload)
                                    else:
                                        await socket.send_bytes(payload)
                            except Exception as e:
                                logger.error(f"Error enviando mensaje en {chat_guid}: {e}")
                                sockets.remove(socket)
        except asyncio.CancelledError:
            logger.info("PubSub reader task cancelled.")
        except Exception as e:
            logger.error(f"Error fatal en PubSub reader: {e}", exc_info=True)
        finally:
            self.pubsub_subscriber_task = None

    async def send_error(self, message: str, websocket: WebSocket):
        """Envía un mensaje de error JSON al socket."""
        await websocket.send_json({"type": "error", "message": message})

# --- INSTANCIA GLOBAL (LO QUE EL ROUTER NECESITA) ---
websocket_manager = WebSocketManager()