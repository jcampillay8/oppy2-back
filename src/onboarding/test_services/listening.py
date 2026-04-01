# src/onboarding/test_services/listening.py
import json
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai, generate_oppy_voice

logger = logging.getLogger(__name__)

class ListeningTestService:
    async def generate_listening_task(self, db: AsyncSession, user_id: int, user_bio: str) -> Dict[str, Any]:
        """
        Genera un script basado en la Bio, lo convierte a audio y define 3 preguntas.
        """
        system_instruction = """
        You are an expert English teacher. Create a B2 Listening task.
        The script must be a natural monologue (approx 150 words) based on the user's professional bio.
        Respond ONLY in valid JSON.
        """

        user_prompt = f"""
        CONTEXT: {user_bio}
        
        REQUIREMENTS:
        1. Script: A story about a professional challenge or achievement related to the bio.
        2. Questions: Exactly 3 multiple-choice questions.
        3. Options: 3 options per question (A, B, C).
        
        OUTPUT FORMAT:
        {{
            "title": "string",
            "script": "string",
            "questions": [
                {{
                    "id": 1,
                    "question_text": "string",
                    "options": [
                        {{"id": "A", "text": "string"}},
                        {{"id": "B", "text": "string"}},
                        {{"id": "C", "text": "string"}}
                    ],
                    "correct_option": "A"
                }}
            ]
        }}
        """

        # 1. Generar Contenido con Gemini
        response_json = await ask_oppy_ai(
            db=db,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            user_id=user_id,
            caller="placement_test_listening_gen",
            expect_json=True
        )

        try:
            task_data = json.loads(response_json)
            
            # 2. Generar Audio basado en el script de Gemini
            audio_content = await generate_oppy_voice(
                db=db,
                text=task_data["script"],
                user_id=user_id,
                caller="placement_test_listening_tts",
                voice_key="us_male" 
            )
            
            task_data["audio_content"] = audio_content
            return task_data
        except Exception as e:
            logger.error(f"Error in Listening service: {e}")
            return self._get_fallback_task()

    def calculate_listening_level(self, user_answers: List[str], correct_answers: List[str]) -> dict:
        """Lógica idéntica al Reading para consistencia CEFR."""
        hits = sum(1 for i, ans in enumerate(user_answers) if i < len(correct_answers) and ans == correct_answers[i])
        mapping = {
            0: {"level": "A1", "score": 0.0},
            1: {"level": "A2", "score": 33.3},
            2: {"level": "B1", "score": 66.6},
            3: {"level": "B2", "score": 100.0}
        }
        return mapping.get(hits, {"level": "A1", "score": 0.0})

    def _get_fallback_task(self) -> Dict[str, Any]:
        return {"title": "Professional Life", "script": "Hello, I am an engineer...", "questions": []}

listening_service = ListeningTestService()