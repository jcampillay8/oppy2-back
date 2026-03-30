# src/onboarding/test_services/consolidator.py
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai

logger = logging.getLogger(__name__)

class TestConsolidator:
    def determine_global_level(self, avg_score: float) -> str:
        if avg_score >= 85: return "B2"
        if avg_score >= 60: return "B1"
        if avg_score >= 30: return "A2"
        return "A1"

    async def generate_final_analysis(
        self, db: AsyncSession, user_id: int, scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """Genera el análisis de IA que se ve en la tarjeta azul de la imagen."""
        
        system_instruction = """
        You are 'Oppy', an AI Language Coach. 
        Analyze the student's scores in Writing, Reading, Listening, and Speaking.
        Provide a professional yet encouraging analysis in SPANISH.
        Focus on identifying the strongest skill and the one that needs most work.
        Keep it under 60 words.
        """

        user_prompt = f"""
        SCORES:
        Writing: {scores['writing']}%
        Reading: {scores['reading']}%
        Listening: {scores['listening']}%
        Speaking: {scores['speaking']}%
        """

        analysis_text = await ask_oppy_ai(
            db=db,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            user_id=user_id,
            caller="onboarding_final_analysis",
            expect_json=False # Aquí queremos texto fluido para el párrafo
        )

        return {
            "analysis_text": analysis_text,
            "suggested_plan": f"Conversación {self.determine_global_level(sum(scores.values())/4)}"
        }