# src/onboarding/test_services/reading.py
import json
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai

logger = logging.getLogger(__name__)

class ReadingTestService:
    async def generate_reading_task(self, db: AsyncSession, user_id: int, user_bio: str) -> Dict[str, Any]:
        """
        Usa el orquestador Oppy AI para generar la tarea de lectura.
        """
        system_instruction = """
        You are an expert English Language Teacher (CEFR Examiner).
        Your goal is to create a professional Reading Comprehension task at B2 level.
        You must ALWAYS respond in valid JSON format.
        """

        user_prompt = f"""
        CONTEXT: Use the following user biography to create a realistic, professional-themed 
        short story (approx 150-200 words) at CEFR B2 level:
        ---
        {user_bio}
        ---
        
        REQUIREMENTS:
        1. Title: An engaging title.
        2. Story: Two paragraphs of text based on the context.
        3. Questions: Exactly 3 multiple-choice questions.
        4. Options: Each question must have exactly 3 options (A, B, C).
        5. Correct Answer: Specify which option is correct.

        OUTPUT FORMAT (JSON):
        {{
            "title": "string",
            "story": "string",
            "estimated_time": "~8 min",
            "questions": [
                {{
                    "id": 1,
                    "question_text": "string",
                    "options": [
                        {{"id": "A", "text": "string"}},
                        {{"id": "B", "text": "string"}},
                        {{"id": "C", "text": "string"}}
                    ],
                    "correct_option": "B"
                }}
            ]
        }}
        """

        # Usamos tu orquestador centralizado
        response_json = await ask_oppy_ai(
            db=db,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            user_id=user_id,
            caller="placement_test_reading",
            expect_json=True
        )

        try:
            return json.loads(response_json)
        except Exception as e:
            logger.error(f"Error parsing JSON from Oppy AI: {e}")
            return self._get_fallback_task()

    def calculate_reading_level(self, user_answers: List[str], correct_answers: List[str]) -> dict:
        """
        Calcula el nivel CEFR basado en aciertos:
        0 aciertos -> A1 (0 pts)
        1 acierto  -> A2 (33 pts)
        2 aciertos -> B1 (66 pts)
        3 aciertos -> B2 (100 pts)
        """
        hits = 0
        for i, ans in enumerate(user_answers):
            if i < len(correct_answers) and ans == correct_answers[i]:
                hits += 1
        
        # Mapeo de lógica solicitada
        mapping = {
            0: {"level": "A1", "score": 0.0},
            1: {"level": "A2", "score": 33.3},
            2: {"level": "B1", "score": 66.6},
            3: {"level": "B2", "score": 100.0}
        }
        
        return mapping.get(hits, {"level": "A1", "score": 0.0})

    def _get_fallback_task(self) -> Dict[str, Any]:
        return {
            "title": "Professional Growth",
            "story": "The integration of engineering and data is key in modern industry...",
            "estimated_time": "~5 min",
            "questions": []
        }