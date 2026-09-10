# src/learning_analysis/services/smart_review_service.py
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import LearningPathProgress
from . import ielts_syllabus

async def get_smart_review_suggestion(
    db: AsyncSession,
    user_id: int,
    course_type: str = "ielts"
) -> Dict[str, Any]:
    """
    Finds all 'mastered' units for a user and ranks them using the combined priority formula:
    Priority = (100 - precision_score + 1.0) * (days_since_last_practiced + 0.1)
    Returns the top suggested unit for review.
    """
    stmt = select(LearningPathProgress).where(
        LearningPathProgress.user_id == user_id,
        LearningPathProgress.course_type == course_type,
        LearningPathProgress.status == "mastered"
    )
    result = await db.execute(stmt)
    mastered_units = list(result.scalars().all())

    if not mastered_units:
        return {
            "has_mastered_units": False,
            "level": None,
            "unit": None,
            "unit_title": None,
            "precision_score": None,
            "days_since_practiced": None,
            "reason_text": "Aún no tienes unidades aprobadas para repasar. ¡Completa tu primera lección!"
        }

    syllabus = ielts_syllabus.load_ielts_syllabus()
    now = datetime.now(timezone.utc)
    
    ranked_units = []

    for prog in mastered_units:
        # Calculate days since last practice
        last_practiced = prog.last_practiced_at
        if last_practiced is None:
            days_since = 1.0
        else:
            if last_practiced.tzinfo is None:
                last_practiced = last_practiced.replace(tzinfo=timezone.utc)
            delta = now - last_practiced
            days_since = max(0.1, delta.total_seconds() / 86400.0)

        # Normalize score (0..100)
        score = prog.precision_score if prog.precision_score is not None else 80.0
        if 0.0 < score <= 1.0:
            score = score * 100.0

        score_gap = max(0.0, 100.0 - score)
        # Priority formula: (gap + 1) * (days + 0.1)
        priority = (score_gap + 1.0) * (days_since + 0.1)

        # Find unit title from syllabus
        level_data = syllabus.get(prog.level, {})
        units_data = level_data.get("units", {})
        unit_info = units_data.get(prog.unit, {})
        unit_title = unit_info.get("title", f"Unidad {prog.unit}")

        ranked_units.append({
            "progress": prog,
            "priority": priority,
            "score": score,
            "days_since": int(days_since),
            "unit_title": unit_title
        })

    # Sort descending by priority
    ranked_units.sort(key=lambda x: x["priority"], reverse=True)
    top = ranked_units[0]
    top_prog = top["progress"]

    days_text = "hoy" if top["days_since"] == 0 else f"hace {top['days_since']} días"
    reason = f"Puntaje actual {int(top['score'])}% • Repasado por última vez {days_text}"

    return {
        "has_mastered_units": True,
        "level": top_prog.level,
        "unit": top_prog.unit,
        "unit_title": top["unit_title"],
        "precision_score": round(top["score"], 1),
        "days_since_practiced": top["days_since"],
        "reason_text": reason
    }
