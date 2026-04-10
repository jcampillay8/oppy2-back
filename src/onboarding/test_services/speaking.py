# src/onboarding/test_services/speaking.py
import logging
import json
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
        Evalúa la transcripción de voz del usuario usando el orquestador Oppy AI.
        """
        
        system_instruction = f"""
        You are an expert {target_language} Language Examiner.
        Analyze the following transcript. The user was asked: "Why is it important for you to learn {target_language}?"
        
        CRITICAL RULES:
        1. Evaluate Score from 1 to 100 (where 100 is native-level).
        2. Assign CEFR Level based on: 1-30:A1, 31-50:A2, 51-75:B1, 76-85:B2, 86-94:C1, 95-100:C2.
        3. Provide a constructive feedback in Spanish.
        
        Respond ONLY in JSON with this structure:
        {{
            "score": float,
            "assigned_level": "string",
            "feedback": "string",
            "fluency_score": float
        }}
        """

        user_prompt = f"TRANSCRIPT: \"{transcript}\""

        # --- CORRECCIÓN CLAVE: Empaquetar en messages ---
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]

        # Llamada al orquestador con el formato correcto
        response_json = await ask_oppy_ai(
            db=db,
            messages=messages,  # Enviamos el argumento requerido
            user_id=user_id,
            caller="onboarding_speaking_eval",
            expect_json=True
        )

        try:
            # Normalización segura
            data = json.loads(response_json) if isinstance(response_json, str) else response_json
            
            # Aseguramos que la transcripción original se adjunte al resultado para persistir
            data["transcript"] = transcript
            return data
            
        except Exception as e:
            logger.error(f"Error parsing Speaking eval: {e}")
            return {
                "score": 10.0, 
                "assigned_level": "A1", 
                "feedback": "Error en la evaluación técnica.",
                "transcript": transcript
            }

# Instancia para uso global (opcional, según tu patrón de routers)
speaking_service = SpeakingTestService()