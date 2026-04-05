# src/learning_analysis/utils.py
import json
import re
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

def clean_llm_json(raw_text: str) -> str:
    """Limpia bloques de código, etiquetas y errores de truncamiento del LLM."""
    if not raw_text: return ""
    cleaned = str(raw_text).strip()
    
    # Remover bloques Markdown
    cleaned = re.sub(r'^```json\s*|```$', '', cleaned, flags=re.MULTILINE | re.IGNORECASE).strip()
    
    # Eliminar caracteres de control y comillas envolventes
    cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()

    # Intentar cerrar llaves si parece truncado
    if cleaned.startswith("{") and not cleaned.endswith("}"):
        cleaned += "}"
    
    return cleaned

def parse_llm_json_safe(raw_text: str) -> Optional[Any]:
    """Parseo robusto que utiliza clean_llm_json y reintentos de substring."""
    cleaned = clean_llm_json(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Intento de extraer el último bloque válido {...}
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except: pass
    return None