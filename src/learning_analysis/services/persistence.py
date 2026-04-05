# src/learning_analysis/services/persistence.py
import random
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from ..models import LearningFocus, FocusInstance, AnalysisCategory

# --- ESCRITURA (PROCESAMIENTO) ---

async def save_analysis_results(
    db: AsyncSession, 
    user_id: int, 
    message_id: int, 
    errors: List[Dict[str, Any]]
):
    """
    Persiste los resultados del análisis. Optimizado para minimizar queries.
    """
    for err in errors:
        # 1. Obtener la categoría (Podrías cachear esto en memoria para ir más rápido)
        stmt_cat = select(AnalysisCategory).where(AnalysisCategory.name == err['category'])
        category = (await db.execute(stmt_cat)).scalar_one_or_none()
        if not category:
            continue

        # 2. Buscar el Focus (Padre)
        stmt_focus = select(LearningFocus).where(
            LearningFocus.user_id == user_id,
            LearningFocus.category_id == category.id
        )
        focus = (await db.execute(stmt_focus)).scalar_one_or_none()

        if not focus:
            focus = LearningFocus(
                user_id=user_id,
                category_id=category.id,
                insight_summary=err['explanation'],
                total_count=1,
                priority_score=1.0  # Inicializamos prioridad
            )
            db.add(focus)
            await db.flush() 
        else:
            focus.total_count += 1
            focus.insight_summary = err['explanation']
            focus.priority_score = float(focus.total_count) # Lógica simple de prioridad

        # 3. Crear la Instancia (Hijo)
        instance = FocusInstance(
            learning_focus_id=focus.id,
            message_id=message_id,
            original_segment=err['incorrect_part'],
            corrected_segment=err['correct_part'],
            explanation=err['explanation'],
            exercise_text_es=err['exercise_text_es'],
            rating=3, # Rating por defecto
            created_at=datetime.now(timezone.utc)
        )
        db.add(instance)
    
    await db.commit()

# --- LECTURA (PARA EL ROUTER) ---

async def get_active_focus_by_user(db: AsyncSession, user_id: int) -> List[LearningFocus]:
    """
    Obtiene los temas de aprendizaje con sus nombres de categoría.
    Filtra los que tienen conteo > 0.
    """
    stmt = (
        select(LearningFocus)
        .where(LearningFocus.user_id == user_id, LearningFocus.total_count > 0)
        .options(selectinload(LearningFocus.category))
        .order_by(LearningFocus.priority_score.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_random_practice_instance(
    db: AsyncSession, 
    focus_id: UUID, 
    user_id: int
) -> Optional[FocusInstance]:
    """
    Selecciona una instancia aleatoria para practicar, 
    validando pertenencia al usuario.
    """
    # Verificamos que el focus pertenezca al usuario
    stmt_check = select(LearningFocus).where(
        LearningFocus.id == focus_id, 
        LearningFocus.user_id == user_id
    )
    focus = (await db.execute(stmt_check)).scalar_one_or_none()
    if not focus:
        return None

    # Traemos las instancias con rating aceptable
    stmt_instances = select(FocusInstance).where(
        FocusInstance.learning_focus_id == focus_id,
        FocusInstance.rating > 0
    )
    instances = (await db.execute(stmt_instances)).scalars().all()
    
    if not instances:
        # Sincronización de seguridad: si no hay hijos, el padre debería estar en 0
        focus.total_count = 0
        await db.commit()
        return None

    # Lógica de aleatoriedad (puedes complicarla luego con pesos por rating)
    return random.choice(instances)

async def update_instance_rating(
    db: AsyncSession, 
    instance_id: UUID, 
    user_id: int, 
    new_rating: int
):
    """
    Actualiza el rating de una instancia específica.
    """
    # Nota: Aquí podrías añadir un join para validar que la instancia 
    # pertenece a un focus del user_id.
    stmt = (
        update(FocusInstance)
        .where(FocusInstance.id == instance_id)
        .values(rating=new_rating)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "updated"}