# src/chat/services/text_analysis_service.py
import logging
import re
from typing import Optional, Dict, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai as ask_llm
from src.models import User

logger = logging.getLogger(__name__)

def _ensure_string(llm_response_raw) -> str:
    if isinstance(llm_response_raw, tuple):
        return str(llm_response_raw[0])
    return str(llm_response_raw) if llm_response_raw else ""

async def correct_user_message(
    db: AsyncSession,
    user_message: str,
    user: Optional[User] = None,
    language: str = "English"
) -> Optional[str]:
    """
    Solicita a la IA que corrija gramaticalmente el mensaje. 
    Retorna el texto corregido o None si no hay cambios significativos.
    """
    if not user_message or not user_message.strip():
        return None

    system_prompt = (
        f"You are a professional {language} teacher. Correct the user's text for grammar, "
        "spelling, and natural phrasing. "
        "Return ONLY the corrected text. If it is already correct, return it as is."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Text: '{user_message}'"}
    ]

    try:
        response = await ask_llm(
            messages=messages,
            db=db,
            max_tokens=200,
            caller="text_correction",
            user_id=user.id if user else None
        )
        
        corrected = _ensure_string(response).strip()
        
        # Si la corrección es idéntica al original (ignorando mayúsculas/espacios), 
        # devolvemos None para no generar feedback innecesario.
        if corrected.lower() == user_message.strip().lower():
            return None
            
        return corrected

    except Exception as e:
        logger.error(f"Correction service error: {e}")
        return None

async def evaluate_user_message_score(
    db: AsyncSession,
    user_message: str,
    user: Optional[User] = None,
    language: str = "English"
) -> Optional[float]:
    """
    Evalúa el mensaje del usuario y devuelve un score de 1.0 a 10.0.
    """
    if not user_message or not user_message.strip():
        return None

    system_prompt = (
        f"Evaluate the following {language} text. Provide a score from 1.0 to 10.0 "
        "based on grammatical accuracy and professional phrasing. "
        "Response format: ONLY the number (e.g., 8.5)."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Text to score: '{user_message}'"}
    ]

    try:
        response = await ask_llm(
            messages=messages,
            db=db,
            max_tokens=10,
            caller="text_scoring",
            user_id=user.id if user else None
        )
        
        score_str = _ensure_string(response).strip()
        # Regex robusta para capturar el primer número con decimales
        match = re.search(r"(\d{1,2}(?:\.\d)?)", score_str)
        
        if match:
            score = float(match.group(1))
            return max(1.0, min(10.0, round(score, 1)))
            
        return None

    except Exception as e:
        logger.error(f"Scoring service error: {e}")
        return None