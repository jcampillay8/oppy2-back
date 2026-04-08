# src/avatars/services.py
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Ajuste de imports según tu estructura
from src.models import Chat, User, Message, MessageRole, user_chat
from src.avatars.models import AvatarDefinition
from src.chat.models import ChatFact
from src.avatars.prompt_builder import build_system_prompt_from_avatar_definition
from src.ai_management.services import ask_oppy_ai as ask_llm

logger = logging.getLogger(__name__)

def _ensure_string(llm_response_raw) -> str:
    if isinstance(llm_response_raw, tuple):
        return str(llm_response_raw[0])
    return str(llm_response_raw) if llm_response_raw else ""

# --- SERVICIOS DE CRUD ---

async def get_user_avatar_definitions(db: AsyncSession, user_id: int) -> List[AvatarDefinition]:
    result = await db.execute(
        select(AvatarDefinition).where(
            AvatarDefinition.user_id == user_id,
            AvatarDefinition.is_deleted == False
        )
    )
    return result.scalars().all()

async def get_avatar_definition_by_guid(db: AsyncSession, avatar_guid: uuid.UUID, user_id: int) -> Optional[AvatarDefinition]:
    result = await db.execute(
        select(AvatarDefinition).where(
            AvatarDefinition.guid == avatar_guid,
            AvatarDefinition.user_id == user_id,
            AvatarDefinition.is_deleted == False
        )
    )
    return result.scalar_one_or_none()

async def create_avatar_definition(db: AsyncSession, user_id: int, avatar_data) -> AvatarDefinition:
    """Crea el avatar e inicia automáticamente su primera sesión de chat."""
    
    # --- LA CORRECCIÓN ESTÁ AQUÍ ---
    # Usamos model_dump para no tener que mapear a mano y no olvidar campos como 'title'
    avatar_dict = avatar_data.model_dump()
    
    new_avatar = AvatarDefinition(
        user_id=user_id,
        guid=uuid.uuid4(),
        **avatar_dict  # Esto expande title, name, context, role_avatar, etc.
    )
    # ------------------------------
    
    db.add(new_avatar)
    await db.flush()

    # Iniciamos el chat de bienvenida
    await create_avatar_chat_session(db, user_id, new_avatar)
    
    await db.commit()
    await db.refresh(new_avatar)
    return new_avatar

async def update_avatar_definition(db: AsyncSession, avatar_guid: uuid.UUID, user_id: int, avatar_data) -> Optional[AvatarDefinition]:
    """Actualiza una definición de avatar existente."""
    avatar = await get_avatar_definition_by_guid(db, avatar_guid, user_id)
    if not avatar:
        return None

    # Actualización dinámica de campos (exclude_unset asegura que no pise con None lo que no enviaste)
    update_data = avatar_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(avatar, key):
            setattr(avatar, key, value)
    
    avatar.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    await db.flush()
    await db.commit()
    await db.refresh(avatar)
    return avatar

# --- ORQUESTACIÓN DE CHAT Y AVATAR ---

async def create_avatar_chat_session(db: AsyncSession, user_id: int, avatar: AvatarDefinition) -> Chat:
    """Crea la entidad Chat y el primer mensaje 'in-character'."""
    # Generamos el prompt dinámico basado en la definición del avatar
    system_prompt = build_system_prompt_from_avatar_definition(avatar)
    
    new_chat = Chat(
        guid=uuid.uuid4(),
        title=f"Conversación con {avatar.name}",
        system_prompt=system_prompt,
        # ⭐ CAMBIO CLAVE AQUÍ ⭐
        # Usamos 'avatar_definition_id' porque el modelo Chat ahora espera el ID (int)
        avatar_definition_id=avatar.id, 
        is_tts_enabled=avatar.is_tts_enabled,
        selected_voice=avatar.selected_voice,
    )
    db.add(new_chat)
    
    # Flush para obtener el ID de new_chat antes de usarlo en las relaciones
    await db.flush()

    # Asociación Many-to-Many en la tabla intermedia user_chat
    await db.execute(user_chat.insert().values(user_id=user_id, chat_id=new_chat.id))

    # Generar el mensaje de apertura usando el LLM
    initial_content = await generate_avatar_opening_message(db, user_id, avatar)
    
    # Crear el primer mensaje del historial
    initial_msg = Message(
        chat_id=new_chat.id,
        user_id=user_id, 
        role=MessageRole.ASSISTANT,
        content=initial_content,
    )
    db.add(initial_msg)
    
    return new_chat

async def reset_avatar_conversation(db: AsyncSession, user_id: int, avatar_guid: uuid.UUID) -> Chat:
    """Reinicia el chat: limpia mensajes y crea nuevo inicio."""
    
    # 🚀 AJUSTE AQUÍ: Entramos por AvatarDefinition para encontrar el GUID
    chat_query = await db.execute(
        select(Chat)
        .join(user_chat, Chat.id == user_chat.c.chat_id)
        .join(AvatarDefinition, Chat.avatar_definition_id == AvatarDefinition.id) # Unimos con la definición
        .where(
            user_chat.c.user_id == user_id,
            AvatarDefinition.guid == avatar_guid # Ahora sí podemos usar el GUID
        ).options(selectinload(Chat.avatar_definition))
    )
    chat_obj = chat_query.scalar_one_or_none()

    if not chat_obj:
        raise ValueError("No se encontró una conversación activa para reiniciar.")
    

    # Limpiar mensajes y hechos
    messages_result = await db.execute(select(Message.id).where(Message.chat_id == chat_obj.id))
    msg_ids = [r[0] for r in messages_result.fetchall()]

    if msg_ids:
        await db.execute(delete(ChatFact).where(ChatFact.source_message_id.in_(msg_ids)))
        await db.execute(
            update(Message).where(Message.chat_id == chat_obj.id)
            .values(is_deleted=True, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    # Regenerar el mensaje inicial
    new_content = await generate_avatar_opening_message(db, user_id, chat_obj.avatar_definition)
    
    new_start_msg = Message(
        chat_id=chat_obj.id,
        user_id=user_id,
        role=MessageRole.ASSISTANT,
        content=new_content
    )
    db.add(new_start_msg)
    
    # Corregido nombre de función
    chat_obj.system_prompt = build_system_prompt_from_avatar_definition(chat_obj.avatar_definition)
    await db.commit()
    await db.refresh(chat_obj)
    return chat_obj

async def generate_avatar_opening_message(db: AsyncSession, user_id: int, avatar: AvatarDefinition) -> str:
    """Usa el LLM para generar la primera frase del Avatar."""
    base_prompt = build_system_prompt_from_avatar_definition(avatar)
    
    instruction = (
        f"Genera el mensaje de apertura para una nueva conversación. "
        f"Debes presentarte según tu rol: {avatar.role_avatar}. "
        f"No saludes de forma genérica; entra directamente en tu personaje. "
        f"Idioma: {avatar.language_preference}. Máximo 2 frases."
    )

    messages = [
        {"role": "system", "content": f"{base_prompt}\n\n{instruction}"},
        {"role": "user", "content": "Inicia la conversación."}
    ]

    # ⭐ AJUSTE FINAL: Pasamos 'caller' como argumento posicional ⭐
    # Según el error, la función lo exige. Lo ponemos justo después de los básicos.
    response = await ask_llm(
        messages=messages,
        db=db,
        user_id=user_id,
        caller="avatar_opener"  # Probamos pasándolo así de nuevo, si falla es porque va en otra posición
    )
    return _ensure_string(response)

async def delete_avatar_definition(db: AsyncSession, avatar_guid: uuid.UUID, user_id: int) -> bool:
    """
    Realiza un borrado lógico (is_deleted = True) de una definición de avatar.
    """
    avatar = await get_avatar_definition_by_guid(db, avatar_guid, user_id)
    if not avatar:
        return False

    avatar.is_deleted = True
    avatar.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    await db.commit()
    return True