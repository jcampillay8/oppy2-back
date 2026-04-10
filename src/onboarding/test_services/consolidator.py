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
        """Mapea el puntaje promedio al nivel CEFR."""
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
        Genera el análisis de IA consolidando los puntajes y el feedback de la DB.
        """
        
        # 1. Recuperamos el feedback de la DB
        result = await db.execute(
            select(PlacementTestDetail).where(PlacementTestDetail.placement_test_id == test_id)
        )
        details = result.scalars().all()

        evidence_context = ""
        for d in details:
            # Manejo de feedback nulo para evitar errores de concatenación
            fb = d.feedback_text if d.feedback_text else "Sin feedback disponible."
            evidence_context += f"- {d.section.upper()}: {fb}\n"

        # 2. Definimos la instrucción del sistema
        system_instruction = """
        Eres 'Oppy', un coach de idiomas experto y motivador. 
        Analiza el desempeño global de un estudiante en su prueba de nivelación.
        
        Debes entregar una conclusión en ESPAÑOL que:
        1. Analice la relación entre puntajes y feedback.
        2. Identifique fortaleza y área de mejora.
        3. Proporcione un consejo accionable.
        
        REGLAS:
        - Tono: Alentador pero preciso.
        - Máximo 70 palabras.
        - Responde directamente con el texto del análisis.
        """

        user_prompt = f"""
        PUNTAJES:
        Writing: {scores.get('writing', 0)}%
        Reading: {scores.get('reading', 0)}%
        Listening: {scores.get('listening', 0)}%
        Speaking: {scores.get('speaking', 0)}%

        EVIDENCIA POR SECCIÓN:
        {evidence_context}
        """

        # --- AJUSTE CLAVE: Empaquetar en messages ---
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]

        # 3. Llamada a Sofia (Oppy AI)
        analysis_text = await ask_oppy_ai(
            db=db,
            messages=messages, # <--- Cambio de firma
            user_id=user_id,
            caller="onboarding_final_analysis",
            expect_json=False 
        )

        # 4. Cálculo de nivel global
        # Usamos .values() con seguridad
        total_scores = [float(v) for v in scores.values() if v is not None]
        avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
        
        global_level = self.determine_global_level(avg_score)

        return {
            "analysis_text": analysis_text if analysis_text else "Análisis no disponible en este momento.",
            "global_level": global_level,
            "suggested_plan": f"Plan Enfoque {global_level}",
            "average_score": round(avg_score, 2)
        }