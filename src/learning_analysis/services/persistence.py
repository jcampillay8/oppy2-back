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

# --- LEARNING PATH PROGRESS ---

from ..models import LearningPathProgress

async def get_learning_path_progress(
    db: AsyncSession, 
    user_id: int, 
    course_type: str = "standard"
) -> List[LearningPathProgress]:
    stmt = (
        select(LearningPathProgress)
        .where(
            LearningPathProgress.user_id == user_id,
            LearningPathProgress.course_type == course_type
        )
        .order_by(LearningPathProgress.level.asc(), LearningPathProgress.unit.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def upsert_learning_path_progress(
    db: AsyncSession,
    user_id: int,
    level: int,
    unit: int,
    status: str,
    precision_score: Optional[float] = None,
    course_type: str = "standard"
) -> LearningPathProgress:
    stmt = select(LearningPathProgress).where(
        LearningPathProgress.user_id == user_id,
        LearningPathProgress.course_type == course_type,
        LearningPathProgress.level == level,
        LearningPathProgress.unit == unit
    )
    progress = (await db.execute(stmt)).scalar_one_or_none()
    
    # Normalize score if provided (e.g. 0.8 -> 80.0)
    norm_score = precision_score
    if norm_score is not None and 0.0 < norm_score <= 1.0:
        norm_score = norm_score * 100.0

    if progress:
        # 1. Retain highest score ever achieved (high-water mark)
        if norm_score is not None:
            if progress.precision_score is not None:
                existing_norm = progress.precision_score
                if 0.0 < existing_norm <= 1.0:
                    existing_norm = existing_norm * 100.0
                progress.precision_score = max(existing_norm, norm_score)
            else:
                progress.precision_score = norm_score

        # 2. Preserve mastered status permanently (never degrade to in_progress)
        is_already_mastered = (progress.status == "mastered")
        is_newly_mastered = (status == "mastered")
        score_is_mastered = (
            progress.precision_score is not None and progress.precision_score >= 80.0
        )

        if is_already_mastered or is_newly_mastered or score_is_mastered:
            progress.status = "mastered"
        else:
            progress.status = status

        progress.last_practiced_at = datetime.now(timezone.utc)
    else:
        final_status = status
        if norm_score is not None and norm_score >= 80.0:
            final_status = "mastered"

        progress = LearningPathProgress(
            user_id=user_id,
            course_type=course_type,
            level=level,
            unit=unit,
            status=final_status,
            precision_score=norm_score,
            last_practiced_at=datetime.now(timezone.utc)
        )
        db.add(progress)
        
    await db.commit()
    await db.refresh(progress)
    return progress

# --- USER DAILY ACTIVITY & STREAK ---

from datetime import date, timedelta
from ..models import UserDailyActivity

async def increment_user_daily_activity(
    db: AsyncSession,
    user_id: int,
    course_type: str = "ielts"
) -> UserDailyActivity:
    today_date = date.today()
    stmt = select(UserDailyActivity).where(
        UserDailyActivity.user_id == user_id,
        UserDailyActivity.course_type == course_type,
        UserDailyActivity.activity_date == today_date
    )
    activity = (await db.execute(stmt)).scalar_one_or_none()

    if activity:
        activity.response_count += 1
    else:
        activity = UserDailyActivity(
            user_id=user_id,
            course_type=course_type,
            activity_date=today_date,
            response_count=1
        )
        db.add(activity)

    await db.commit()
    await db.refresh(activity)
    return activity

async def get_user_activity_stats(
    db: AsyncSession,
    user_id: int,
    course_type: str = "ielts"
) -> Dict[str, Any]:
    stmt = (
        select(UserDailyActivity)
        .where(
            UserDailyActivity.user_id == user_id,
            UserDailyActivity.course_type == course_type
        )
        .order_by(UserDailyActivity.activity_date.asc())
    )
    result = await db.execute(stmt)
    records = list(result.scalars().all())

    activity_data = [
        {"date": r.activity_date.isoformat(), "count": r.response_count}
        for r in records
    ]

    total_responses = sum(r.response_count for r in records)
    active_days_count = len([r for r in records if r.response_count > 0])
    daily_average = round(total_responses / active_days_count, 1) if active_days_count > 0 else 0.0

    dates_set = {r.activity_date for r in records if r.response_count > 0}
    current_streak = 0
    today = date.today()
    check_date = today

    if check_date not in dates_set:
        check_date = today - timedelta(days=1)

    while check_date in dates_set:
        current_streak += 1
        check_date -= timedelta(days=1)

    return {
        "current_streak": current_streak,
        "total_responses": total_responses,
        "daily_average": daily_average,
        "activity_data": activity_data
    }