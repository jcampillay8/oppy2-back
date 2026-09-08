import os
import logging
import httpx
from src.config import settings

logger = logging.getLogger(__name__)

async def translate_with_deepl(text: str, target_lang: str = "EN-US", source_lang: str = "ES") -> dict:
    api_key = settings.DEEPL_API_KEY or os.getenv("DeepL_API_KEY") or os.getenv("DEEPL_API_KEY")
    if not api_key:
        raise ValueError("DeepL API key is not configured in backend environment.")

    # Ensure target_lang is valid for DeepL
    valid_targets = ["EN-US", "EN-GB"]
    if target_lang.upper() not in valid_targets:
        target_lang = "EN-US"
    else:
        target_lang = target_lang.upper()

    url = "https://api-free.deepl.com/v2/translate"
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": [text],
        "source_lang": source_lang.upper(),
        "target_lang": target_lang
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            translations = data.get("translations", [])
            if translations:
                first = translations[0]
                return {
                    "translated_text": first.get("text", ""),
                    "detected_source_lang": first.get("detected_source_language", source_lang),
                    "target_lang": target_lang
                }
            return {
                "translated_text": "",
                "detected_source_lang": source_lang,
                "target_lang": target_lang
            }
    except Exception as e:
        logger.error(f"Error calling DeepL API: {e}")
        raise RuntimeError(f"Error al traducir con DeepL: {str(e)}")
