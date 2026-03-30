# src/onboarding/test_services/speaking.pyimport logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai

logger = logging.getLogger(__name__)

class SpeakingTestService:
    async def evaluate_speaking(
        self, 
        db: AsyncSession, 
        user_id: int, 
        transcript: str, 
        target_language: str
    ) -> Dict[str, Any]:
        """
        Analiza la transcripción del usuario usando Gemini para 
        determinar fluidez, gramática y nivel CEFR.
        """
        
        system_instruction = f"""
        You are an expert {target_language} Language Examiner.
        Analyze the following transcript from a speaking test.
        The user was asked: "Why is it important for you to learn {target_language}?"
        
        Evaluate based on:
        1. Fluency (coherence).
        2. Grammar and Vocabulary.
        3. Level (A1 to B2).
        
        Respond ONLY in JSON.
        """

        user_prompt = f"TRANSCRIPT: \"{transcript}\""

        response_json = await ask_oppy_ai(
            db=db,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            user_id=user_id,
            caller="onboarding_speaking_eval",
            expect_json=True
        )

        try:
            # Gemini debería retornar algo como: 
            # {"score": 85.0, "level": "B2", "feedback": "...", "fluency": "High"}
            import json
            return json.loads(response_json)
        except Exception as e:
            logger.error(f"Error parsing Speaking eval: {e}")
            return {"score": 0.0, "level": "A1", "feedback": "Error in evaluation."}