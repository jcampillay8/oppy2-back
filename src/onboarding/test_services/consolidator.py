# src/onboarding/test_services/consolidator.py
import logging
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai
from src.onboarding.models import PlacementTestDetail

logger = logging.getLogger(__name__)

class TestConsolidator:
    def determine_global_level(self, avg_score: float) -> str:
        """Mapea el puntaje promedio al nivel CEFR basado en tus constantes."""
        if avg_score >= 95: return "C2"
        if avg_score >= 86: return "C1"
        if avg_score >= 76: return "B2"
        if avg_score >= 51: return "B1"
        if avg_score >= 31: return "A2"
        return "A1"

    async def generate_final_analysis(
        self, 
        db: AsyncSession, 
        user_id: int, 
        test_id: int, 
        scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Genera el análisis de IA consolidando los puntajes numéricos y 
        el feedback detallado de cada sección almacenado en la DB.
        """
        
        # 1. Recuperamos el feedback real de cada sección de la tabla de detalles
        result = await db.execute(
            select(PlacementTestDetail).where(PlacementTestDetail.placement_test_id == test_id)
        )
        details = result.scalars().all()

        # 2. Construimos el contexto de evidencia para Gemini
        evidence_context = ""
        for d in details:
            # Incluimos sección y el feedback que Gemini dio en ese momento
            evidence_context += f"- {d.section.upper()}: {d.feedback_text}\n"

        # 3. Definimos una instrucción que obligue a la IA a ser específica
        system_instruction = """
        Eres 'Oppy', un coach de idiomas experto y motivador. 
        Tu objetivo es analizar el desempeño global de un estudiante en su prueba de nivelación.
        
        Debes entregar una conclusión en ESPAÑOL que:
        1. Analice la relación entre los puntajes y el feedback de cada sección.
        2. Identifique la mayor fortaleza y el área crítica de mejora.
        3. Proporcione un consejo accionable y profesional.
        
        REGLAS:
        - Tono: Alentador pero técnicamente preciso.
        - Longitud: Máximo 70 palabras.
        - Idioma: Español.
        """

        user_prompt = f"""
        PUNTAJES OBTENIDOS:
        Writing: {scores['writing']}%
        Reading: {scores['reading']}%
        Listening: {scores['listening']}%
        Speaking: {scores['speaking']}%

        EVIDENCIA DETALLADA (FEEDBACK POR SECCIÓN):
        {evidence_context}
        """

        # 4. Llamada a Oppy para el análisis narrativo
        analysis_text = await ask_oppy_ai(
            db=db,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            user_id=user_id,
            caller="onboarding_final_analysis",
            expect_json=False 
        )

        avg_score = sum(scores.values()) / 4
        global_level = self.determine_global_level(avg_score)

        return {
            "analysis_text": analysis_text,
            "global_level": global_level,
            "suggested_plan": f"Plan Enfoque {global_level}"
        }