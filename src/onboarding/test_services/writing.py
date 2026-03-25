# src/onboarding/test_services/writing.py
import json
import logging
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# IMPORTANTE: Añadir estas importaciones de tus modelos
from src.onboarding.models import PlacementTest, WritingTopic, UserWritingAssignment
from src.ai_management.services import ask_oppy_ai
from .. import schemas

logger = logging.getLogger(__name__)

async def evaluate_writing_task(
    db: AsyncSession, 
    user_id: int, 
    target_language: str, 
    user_text: str
) -> float:
    """Evalúa dinámicamente según el tema asignado."""
    try:
        # 1. Buscar asignación previa
        assign_stmt = select(UserWritingAssignment).where(
            UserWritingAssignment.user_id == user_id,
            UserWritingAssignment.target_language == target_language
        ).options(selectinload(UserWritingAssignment.topic))
        
        assign_res = await db.execute(assign_stmt)
        assignment = assign_res.scalar_one_or_none()
        
        # Consigna dinámica
        topic_title = assignment.topic.title if assignment else "General Topic"
        topic_prompt = assignment.topic.prompt if assignment else "General writing task"

        dynamic_system_prompt = f"""
        Eres un examinador experto en idiomas.
        Evalúa el texto basado en la consigna: '{topic_title}: {topic_prompt}'
        Criterios: Gramática (25%), Vocabulario (25%), Coherencia (25%), Relevancia (25%).

        DEBES responder ÚNICAMENTE en formato JSON:
        {{ "score": <float 0-100>, "feedback": "<explicación>", "detected_level": "<A1-C2>" }}
        """

        # 2. IA Call
        response_str = await ask_oppy_ai(
            db=db,
            system_instruction=dynamic_system_prompt,
            user_prompt=f"Texto del estudiante: {user_text}",
            user_id=user_id,
            caller="onboarding_writing",
            expect_json=True
        )

        data = json.loads(response_str)
        score = float(data.get("score", 0))

        # 3. Upsert Result
        query = select(PlacementTest).where(
            PlacementTest.user_id == user_id,
            PlacementTest.target_language == target_language
        )
        result = await db.execute(query)
        test = result.scalar_one_or_none()

        if not test:
            test = PlacementTest(user_id=user_id, target_language=target_language, writing_result=score)
            db.add(test)
        else:
            test.writing_result = score
        
        await db.commit()
        return score

    except Exception as e:
        logger.error(f"Error crítico en evaluate_writing_task: {e}")
        return 0.0

async def get_or_assign_writing_topic(
    db: AsyncSession, 
    user_id: int, 
    selection: schemas.WritingCategorySelection
) -> WritingTopic:
    """Busca una pregunta ya asignada o elige una nueva al azar de la categoría."""
    
    # 1. Check existing
    stmt = select(UserWritingAssignment).where(
        UserWritingAssignment.user_id == user_id,
        UserWritingAssignment.target_language == selection.target_language
    ).options(selectinload(UserWritingAssignment.topic))
    
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if assignment:
        return assignment.topic

    # 2. Pick new from bank
    query = select(WritingTopic).where(
        WritingTopic.category == selection.category,
        WritingTopic.target_language == selection.target_language
    )
    topics_result = await db.execute(query)
    topics = topics_result.scalars().all()

    if not topics:
        raise ValueError(f"No hay preguntas en la categoría: {selection.category}")

    chosen_topic = random.choice(topics)

    # 3. Save assignment
    new_assignment = UserWritingAssignment(
        user_id=user_id,
        topic_id=chosen_topic.id,
        target_language=selection.target_language
    )
    db.add(new_assignment)
    await db.commit()

    return chosen_topic