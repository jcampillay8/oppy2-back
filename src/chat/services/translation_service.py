# src/chat/services/translation_service.py
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.avatars.config import DEFAULT_LLM_MODEL, LANGUAGE_MAP
from src.ai_management.services import ask_oppy_ai as ask_llm

logger = logging.getLogger(__name__)

def _ensure_string(llm_response_raw) -> str:
    if isinstance(llm_response_raw, tuple):
        return str(llm_response_raw[0])
    return str(llm_response_raw) if llm_response_raw else ""

async def translate_text(
    db: AsyncSession,
    text: str,
    from_lang: str,
    to_lang: str,
    user_id: Optional[int] = None,
    context: Optional[str] = None
) -> str:
    """
    Función única y universal de traducción.
    
    Args:
        text: El contenido a traducir.
        from_lang: Código ISO o nombre del idioma origen (ej. 'es', 'en', 'Spanish').
        to_lang: Código ISO o nombre del idioma destino (ej. 'en', 'fr', 'English').
        context: (Opcional) Nota sobre el tono o situación (ej. "diálogo médico", "jerga callejera").
    """
    if not text or not text.strip():
        return ""

    # Normalizamos los nombres de los idiomas usando el MAP (si existen los códigos)
    src_name = LANGUAGE_MAP.get(from_lang.lower(), from_lang)
    tgt_name = LANGUAGE_MAP.get(to_lang.lower(), to_lang)

    # Si el origen y destino terminan siendo lo mismo, devolvemos el texto original para ahorrar tokens
    if src_name.lower() == tgt_name.lower():
        return text.strip()

    system_instruction = (
        f"You are a professional translator specialized in {src_name} and {tgt_name}. "
        f"Translate the following text from {src_name} to {tgt_name}. "
        "Maintain the original meaning, nuances, and emotional tone. "
        "Output ONLY the translated text without quotes, explanations, or labels."
    )
    
    if context:
        system_instruction += f"\nSpecific Context: {context}"

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": text.strip()}
    ]

    try:
        translated_raw = await ask_llm(
            messages=messages,
            db=db,
            caller="universal_translator",
            user_id=user_id,
            model_name=DEFAULT_LLM_MODEL,
            max_tokens=1000, # Ajustado para textos más largos si es necesario
            temperature=0.2  # Buscamos precisión técnica
        )
        
        return _ensure_string(translated_raw).strip()

    except Exception as e:
        logger.error(
            f"Universal translation failed: {src_name} -> {tgt_name}. Error: {e}", 
            exc_info=True
        )
        # Fallback de seguridad: devolvemos el original para no interrumpir el flujo del usuario
        return text