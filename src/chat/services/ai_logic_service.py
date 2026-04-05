# src/chat/services/ai_logic_service.py
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Configuración y Clientes
from src.ai_management.config import DEFAULT_MODEL
from src.avatars.config import LABELS, LABEL_TO_FACT_TYPE
from src.ai_management.services import ask_oppy_ai as ask_llm
from src.avatars.prompt_builder import (
    build_system_prompt_from_avatar_definition, 
    build_fact_context
)
from src.chat.models import ChatFact

logger = logging.getLogger(__name__)

def _ensure_string(llm_response_raw) -> str:
    """Extrae el texto de una respuesta de LLM (soporta tuplas o None)."""
    if isinstance(llm_response_raw, tuple):
        return str(llm_response_raw[0])
    return str(llm_response_raw) if llm_response_raw else ""

# ==============================================================================
# 1. Generación de Respuestas (Avatar Interaction)
# ==============================================================================

async def generate_avatar_response(
    db: AsyncSession,
    user_message_content: str,
    chat_id: int,
    user_id: int,
    facts: List[ChatFact],
    chat_history: List[Dict[str, str]],
    avatar,  # AvatarDefinition object
    system_prompt_override: Optional[str] = None
) -> str:
    """
    Orquesta la generación de la respuesta del Avatar usando RAG (facts) y su personalidad.
    """
    # 1. Construir el contexto de hechos conocidos (RAG)
    context = build_fact_context(facts)

    # 2. Obtener la base de personalidad del Avatar
    base_avatar_prompt = build_system_prompt_from_avatar(avatar)

    # 3. Ensamblar el System Prompt Final
    final_system_prompt = (
        f"--- START OF AVATAR PERSONALITY ---\n"
        f"{base_avatar_prompt}\n"
        f"--- END OF AVATAR PERSONALITY ---\n\n"
        f"--- RELEVANT CONTEXT ABOUT THE USER (FACTS) ---\n"
        f"{context if context else 'No previous facts known yet.'}\n"
        f"--- END OF CONTEXT ---\n\n"
        f"--- ADDITIONAL INTERACTION RULES ---\n"
        f"{system_prompt_override if system_prompt_override else ''}\n"
        f"Interact naturally in {avatar.language_preference}. Keep the character consistent."
    ).strip()

    # 4. Preparar el historial de mensajes para el LLM
    messages = [{"role": "system", "content": final_system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message_content})

    # 5. Determinar tokens según formato (Short, Normal, Long)
    format_pref = str(avatar.output_format_preference).lower() if hasattr(avatar, 'output_format_preference') else "normal"
    max_tokens = OUTPUT_FORMAT_MAX_TOKENS.get(format_pref, 300)

    # 6. Llamar al LLM
    response_raw = await ask_llm(
        messages=messages,
        db=db,
        max_tokens=max_tokens,
        caller="avatar_response_generator",
        user_id=user_id,
        output_format_pref=format_pref
    )

    return _ensure_string(response_raw)

# ==============================================================================
# 2. Extracción de Hechos Semánticos (Fact Extraction)
# ==============================================================================

async def process_and_store_semantic_facts(
    db: AsyncSession,
    text: str,
    user_id: int,
    chat_id: int,
    message_id: int
) -> List[Dict[str, str]]:
    """
    Clasifica el mensaje del usuario y extrae/fusiona información (facts) 
    para persistir la memoria a largo plazo del Avatar.
    """
    
    # --- PASO A: Clasificación ---
    classification_prompt = (
        f"Identify relevant categories in the user message from this list: {', '.join(LABELS)}. "
        f"Respond ONLY in JSON: {{\"relevant_labels\": []}}"
    )
    
    try:
        class_res_raw = await ask_llm(
            messages=[
                {"role": "system", "content": classification_prompt},
                {"role": "user", "content": f'Text: "{text}"'}
            ],
            db=db,
            max_tokens=150,
            caller="fact_classifier",
            user_id=user_id,
            response_format={"type": "json_object"}
        )
        
        class_str = _ensure_string(class_res_raw)
        # Limpieza de markdown si el LLM lo incluye
        if "```json" in class_str:
            class_str = class_str.split("```json")[1].split("```")[0].strip()
        
        relevant_labels = json.loads(class_str).get("relevant_labels", [])
    except Exception as e:
        logger.error(f"Error classifying labels: {e}")
        relevant_labels = []

    extracted_facts = []

    # --- PASO B: Extracción y Fusión ---
    for label in relevant_labels:
        fact_type = LABEL_TO_FACT_TYPE.get(label)
        if not fact_type: continue

        # Buscar si ya existe un hecho de este tipo en este chat
        existing_stmt = select(ChatFact).where(
            ChatFact.chat_id == chat_id, 
            ChatFact.fact_type == fact_type
        )
        existing_obj = (await db.execute(existing_stmt)).scalar_one_or_none()
        existing_val = existing_obj.fact_value if existing_obj else "None"

        extraction_system = (
            f"You are an expert fact extractor. Extract or merge the fact of type '{fact_type}'. "
            f"Existing info: '{existing_val}'. New text: '{text}'. "
            f"Respond ONLY with the merged concise fact or '[NO_FACT]'."
        )

        try:
            fact_res_raw = await ask_llm(
                messages=[{"role": "system", "content": extraction_system}],
                db=db,
                max_tokens=100,
                caller="fact_extractor",
                user_id=user_id
            )
            
            fact_val = _ensure_string(fact_res_raw).strip()

            if fact_val and fact_val != "[NO_FACT]":
                if existing_obj:
                    existing_obj.fact_value = fact_val
                    existing_obj.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    new_fact = ChatFact(
                        chat_id=chat_id,
                        user_id=user_id,
                        fact_type=fact_type,
                        fact_value=fact_val,
                        source_message_id=message_id
                    )
                    db.add(new_fact)
                
                extracted_facts.append({"type": fact_type, "value": fact_val})

        except Exception as e:
            logger.error(f"Error extracting fact {fact_type}: {e}")

    await db.commit()
    return extracted_facts