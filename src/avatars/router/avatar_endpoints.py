# src/avatars/router/avatar_endpoints.py
import logging
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user, get_cache, get_cache_setting
from src.models import User
from src.avatars.models import AvatarDefinition, ScenarioCategory
from src.avatars.schemas import (
    AvatarDefinitionOut,
    AvatarDefinitionUpdate,
    AvatarDefinitionCreate,
    CategoryNodeOut
)
# Esquemas de Chat para el reset
from src.chat.schemas import AvatarChatOutSchema 

# Servicios de Avatars (Asegúrate de que existan en services.py)
from src.avatars.services import (
    reset_avatar_conversation,
    create_avatar_definition,
    get_avatar_definition_by_guid,
    get_user_avatar_definitions,
    update_avatar_definition,
    delete_avatar_definition
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ==========================================
# SECCIÓN: METADATOS / CONFIGURACIÓN (Rutas Estáticas)
# ==========================================

@router.get("/categories", response_model=List[CategoryNodeOut])
async def get_all_categories(db: AsyncSession = Depends(get_async_session)):
    """Retorna las categorías de escenarios en formato jerárquico."""
    result = await db.execute(
        select(ScenarioCategory).filter(ScenarioCategory.is_deleted == False)
    )
    categories = result.scalars().all()
    
    # 1. Convertimos los objetos de BD a diccionarios simples para evitar el error de Greenlet
    # Solo tomamos los campos escalares (id, name, parent_id)
    nodes = {
        c.id: CategoryNodeOut(
            id=c.id, 
            name=c.name, 
            parentId=c.parent_id, 
            children=[]
        ) 
        for c in categories
    }
    
    tree = []
    
    # 2. Construimos la jerarquía usando los objetos de Pydantic ya creados
    for c in categories:
        current_node = nodes[c.id]
        if c.parent_id:
            parent_node = nodes.get(c.parent_id)
            if parent_node:
                parent_node.children.append(current_node)
        else:
            # Si no tiene padre, es una raíz
            tree.append(current_node)
            
    return tree

# ==========================================
# SECCIÓN: CRUD DE AVATARES
# ==========================================

@router.get("/public", response_model=List[AvatarDefinitionOut])
async def list_public_avatars(
    db: AsyncSession = Depends(get_async_session),
    # Quitamos el current_user para que los públicos sean accesibles 
    # o puedes dejarlo si quieres que solo logueados los vean
):
    """Lista avatares globales marcados como públicos."""
    # Asumiendo que tienes un campo 'is_public' en tu modelo
    result = await db.execute(
        select(AvatarDefinition).where(AvatarDefinition.is_public == True)
    )
    return result.scalars().all()

@router.get("/me", response_model=List[AvatarDefinitionOut])
async def list_my_avatars(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Alias para listar solo los avatares creados por el usuario actual."""
    return await get_user_avatar_definitions(db, current_user.id)

@router.post("/", response_model=AvatarDefinitionOut, status_code=status.HTTP_201_CREATED)
async def create_avatar(
    avatar_data: AvatarDefinitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    cache=Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting),
):
    """Crea un nuevo Avatar y limpia la caché de chats."""
    try:
        new_avatar = await create_avatar_definition(db, current_user.id, avatar_data)
        
        if cache_enabled:
            await cache.delete(f"avatar_chats_{current_user.guid}")
            
        return new_avatar
    except Exception as e:
        logger.error(f"Error creating avatar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al crear el avatar.")

@router.get("/{avatar_guid}", response_model=AvatarDefinitionOut)
async def get_avatar(
    avatar_guid: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Obtiene un avatar específico."""
    avatar = await get_avatar_definition_by_guid(db, avatar_guid, current_user.id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar no encontrado.")
    return avatar

@router.patch("/{avatar_guid}", response_model=AvatarDefinitionOut)
async def update_avatar(
    avatar_guid: UUID,
    update_data: AvatarDefinitionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    cache=Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting)
):
    """Actualiza la configuración del avatar."""
    try:
        updated = await update_avatar_definition(db, avatar_guid, current_user.id, update_data)
        if cache_enabled:
            await cache.delete(f"avatar_chats_{current_user.guid}")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{avatar_guid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    avatar_guid: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    cache=Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting)
):
    """Eliminación lógica del avatar."""
    try:
        await delete_avatar_definition(db, avatar_guid, current_user.id)
        if cache_enabled:
            await cache.delete(f"avatar_chats_{current_user.guid}")
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ==========================================
# SECCIÓN: GESTIÓN DE CONVERSACIÓN
# ==========================================

@router.post("/{avatar_guid}/reset-conversation", response_model=AvatarChatOutSchema)
async def reset_conversation(
    avatar_guid: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    cache=Depends(get_cache),
    cache_enabled: bool = Depends(get_cache_setting),
):
    """Reinicia el chat con este avatar (borra historial y crea mensaje inicial)."""
    try:
        reset_chat = await reset_avatar_conversation(db, current_user.id, avatar_guid)
        if cache_enabled:
            await cache.delete(f"avatar_chats_{current_user.guid}")
        return reset_chat
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ==========================================
# SECCIÓN: CONFIGURACIÓN TTS (VOZ)
# ==========================================

@router.patch("/{avatar_guid}/tts", response_model=AvatarDefinitionOut)
async def update_avatar_tts_settings(
    avatar_guid: UUID,
    update_data: AvatarDefinitionUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza solo la configuración de voz del Avatar."""
    result = await db.execute(
        select(AvatarDefinition).where(
            AvatarDefinition.guid == avatar_guid,
            AvatarDefinition.user_id == current_user.id
        )
    )
    avatar = result.scalar_one_or_none()

    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar no encontrado.")

    if update_data.selected_voice is not None:
        avatar.selected_voice = update_data.selected_voice
    if update_data.is_tts_enabled is not None:
        avatar.is_tts_enabled = update_data.is_tts_enabled

    await db.commit()
    await db.refresh(avatar)
    return avatar

