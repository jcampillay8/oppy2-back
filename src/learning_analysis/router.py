# src/learning_analysis/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from . import schemas, services

router = APIRouter(prefix="/learning-analysis", tags=["Learning Analysis"])

@router.get("/focus", response_model=List[schemas.LearningFocusResponse])
async def get_my_learning_focus(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    # Toda la lógica de filtrado y orden reside en persistence.py
    return await services.persistence.get_active_focus_by_user(db, user.id)

@router.get("/focus/{focus_id}/practice", response_model=schemas.FocusInstanceResponse)
async def get_practice_instance(
    focus_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    # La lógica de "selección aleatoria con rating" que tenías en el router pasado,
    # ahora la movemos a services/persistence.py
    instance = await services.persistence.get_random_practice_instance(db, focus_id, user.id)
    if not instance:
        raise HTTPException(status_code=404, detail="No exercises found for this focus")
    return instance

@router.post("/focus/{focus_id}/rate")
async def rate_error_instance(
    instance_id: UUID,
    new_rating: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    return await services.persistence.update_instance_rating(db, instance_id, user.id, new_rating)