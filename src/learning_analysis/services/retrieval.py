from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models import LearningFocus, AnalysisCategory

async def get_top_weaknesses(db: AsyncSession, user_id: int, limit: int = 3) -> List[Dict[str, str]]:
    stmt = (
        select(LearningFocus)
        .options(selectinload(LearningFocus.category))
        .where(LearningFocus.user_id == user_id)
        .order_by(LearningFocus.total_count.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    focuses = result.scalars().all()
    
    return [
        {
            "category": f.category.name,
            "count": f.total_count,
            "insight": f.insight_summary
        }
        for f in focuses
    ]
