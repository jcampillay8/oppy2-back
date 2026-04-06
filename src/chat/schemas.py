# src/chat/schemas.py
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, UUID4

# Importamos lo necesario de ai_management (ajusta según tus nombres actuales)
from src.avatars.schemas import AvatarDefinitionOut, to_camel, VoiceKeyEnum

# ==========================================
# 1. ENUMS Y TIPOS BASE
# ==========================================

class WebSocketMessageType(str, Enum):
    NEW = "new"
    CORRECTION_FEEDBACK = "correction_feedback"
    AUDIO_READY = "audio_ready"
    TYPING_STARTED = "typing_started"
    TYPING_STOPPED = "typing_stopped"
    CHAT_DELETED = "chat_deleted"
    NEW_CHAT_CREATED = "new_chat_created"
    ERROR = "error"
    STATUS = "status"

# ==========================================
# 2. ESQUEMAS DE DOMINIO (REST API)
# ==========================================

class LastMessagePreviewSchema(BaseModel):
    content: Optional[str] = None
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

class BotChatOutSchema(BaseModel):
    guid: UUID 
    created_at: datetime 
    updated_at: datetime 
    new_messages_count: int = 0 
    avatar_definition: Optional[AvatarDefinitionOut] = None 
    last_message: Optional[LastMessagePreviewSchema] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

class MessageOut(BaseModel):
    guid: UUID
    role: str
    content: str
    created_at: datetime
    # ✅ Cambio: Agregamos un valor por defecto para evitar el error "Field required"
    is_read: bool = False 

    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True, 
        from_attributes=True
    )

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

# ==========================================
# 3. ESQUEMAS DE WEBSOCKET (TIEMPO REAL)
# ==========================================

class WSReceiveMessage(BaseModel):
    """Lo que recibimos desde Flutter"""
    chat_guid: UUID4
    content: str
    message_guid: Optional[UUID4] = None # Generado por Flutter para optimismo en UI

class WSSendMessage(BaseModel):
    """Lo que enviamos a Flutter cuando hay un mensaje nuevo"""
    type: WebSocketMessageType = WebSocketMessageType.NEW
    message_guid: UUID4
    chat_guid: UUID4
    content: str
    role: str
    created_at: datetime
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class WSTypingSchema(BaseModel):
    type: WebSocketMessageType
    chat_guid: UUID4
    user_guid: UUID4

class WSStatusSchema(BaseModel):
    """Para presencia online/offline"""
    type: str = "status"
    user_guid: UUID4
    status: str # online, offline, inactive

class WSNotificationSchema(BaseModel):
    """Para eventos como NEW_CHAT_CREATED"""
    type: WebSocketMessageType
    data: Dict[str, Any]

# ==========================================
# 4. ESQUEMAS DE RESPUESTA GLOBALES
# ==========================================

class GetBotChatsResponse(BaseModel):
    chats: List[BotChatOutSchema]
    total_unread_count: int
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

# --- SCHEMAS DE MEMORIA (FACTS) ---

class ChatFactOut(BaseModel):
    id: UUID
    chat_id: int
    user_id: int
    # ⭐ Consistencia: Usamos avatar_definition_id para que coincida con el modelo
    avatar_definition_id: Optional[int] = None 
    fact_type: str
    fact_value: str
    source_message_id: int
    created_at: datetime
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

class ChatFactCreate(BaseModel):
    chat_id: int
    user_id: int
    avatar_definition_id: Optional[int] = None
    fact_type: str
    fact_value: str
    source_message_id: int
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

# --- MENSAJERÍA Y ACTIVACIÓN ---

class TextToSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1)
    selected_voice: VoiceKeyEnum
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class ActivateAvatarRequest(BaseModel):
    is_tts_enabled_by_user: Optional[bool] = False
    selected_voice_by_user: Optional[VoiceKeyEnum] = None
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class InitialMessageContentOut(BaseModel):
    text_content: str
    audio_data: Optional[bytes] = None
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    
class AvatarActivationResponse(BaseModel):
    # Antes decía AvatarDefinition, ahora debe ser AvatarDefinitionOut
    avatar_definition: AvatarDefinitionOut 
    initial_message: InitialMessageContentOut
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

# --- EXTRACCIÓN Y OTROS ---

class ExtractResponse(BaseModel):
    entidades: List[dict]
    hechos: List[dict]
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class ResetConversationRequest(BaseModel):
    is_tts_enabled: bool = False

class AvatarChatOutSchema(BaseModel):
    guid: UUID 
    created_at: datetime 
    updated_at: datetime 
    new_messages_count: int = 0 
    avatar_definition: Optional[AvatarDefinitionOut] = None # Asegúrate que este nombre también coincida
    last_message: Optional[LastMessagePreviewSchema] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)