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
    chat: any,              # Recibe el objeto Chat completo desde el Handler
    user_id: int,
    user_message: str,      # Coincide con el nombre enviado por el Handler
    facts: List[ChatFact] = [],
    chat_history: List[Dict[str, str]] = [],
    system_prompt_override: Optional[str] = None,
    **kwargs                # Por si acaso el Handler envía chat_id u otros extras
) -> str:
    """
    Orquesta la generación de la respuesta del Avatar usando RAG (facts) y su personalidad.
    """
    
    # 0. Extraer el Avatar del objeto Chat
    # Esto es vital porque el Handler envía el objeto Chat, no el Avatar directamente
    avatar = chat.avatar_definition 

    # 1. Construir el contexto de hechos conocidos (RAG)
    context = build_fact_context(facts)

    # 2. Obtener la base de personalidad del Avatar
    # NOTA: Asegúrate de que esta función se llame así o build_system_prompt_from_avatar_definition
    base_avatar_prompt = build_system_prompt_from_avatar_definition(avatar)

    # 3. Ensamblar el System Prompt Final
    final_system_prompt = (
        f"--- START OF AVATAR PERSONALITY ---\n"
        f"{base_avatar_prompt}\n"
        f"--- END OF AVATAR PERSONALITY ---\n\n"
        
        f"--- RELEVANT CONTEXT ABOUT THE USER (FACTS) ---\n"
        f"{context if context else 'No previous facts known yet.'}\n"
        f"--- END OF CONTEXT ---\n\n"
        
        # 🚀 REGLAS DE CONTINUIDAD (Crucial para la inmersión)
        f"--- CHAT CONTINUITY RULES ---\n"
        f"- You are in an ongoing chat. DO NOT say 'Hello', 'Hi', or 'Nice to meet you'.\n"
        f"- Do not use any introductory greetings or pleasantries.\n"
        f"- Jump straight into the feedback or response naturally.\n"
        f"- Maintain a fluid conversation as if you were talking to a friend or colleague.\n\n"

        f"--- ADDITIONAL INTERACTION RULES ---\n"
        f"{system_prompt_override if system_prompt_override else ''}\n"
        f"Interact naturally in {avatar.language_preference}. Keep the character consistent."
    ).strip()

    # 4. Preparar el historial de mensajes para el LLM
    messages = [{"role": "system", "content": final_system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message})

    # 5. Determinar tokens según formato
    format_pref = str(avatar.output_format_preference).lower() if hasattr(avatar, 'output_format_preference') else "normal"
    # Si no tienes definida la constante OUTPUT_FORMAT_MAX_TOKENS, la definimos aquí rápido:
    max_tokens = {"short": 150, "normal": 300, "long": 600}.get(format_pref, 300)

    # 6. Llamar al LLM (Asegúrate de que ask_llm tenga **kwargs en su definición)
    response_raw = await ask_llm(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="avatar_response_generator",
        max_tokens=max_tokens,
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
    
    relevant_labels = [] # Inicialización de seguridad
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

        # ✅ MEJORA: Limpieza robusta de JSON (Markdown safe)
        if "```" in class_str:
            # Extraemos lo que esté entre los bloques de código o el último bloque
            class_str = class_str.split("```")[-2].replace("json", "").strip()
        
        # ✅ MEJORA: Try/Except específico para el parseo de JSON
        try:
            data = json.loads(class_str)
            relevant_labels = data.get("relevant_labels", [])
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON classification: {class_str}")
            relevant_labels = []

    except Exception as e:
        logger.error(f"Error classifying labels: {e}")

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
            f"Existing info: '{existing_val}'. "
            f"Respond ONLY with the merged concise fact or '[NO_FACT]'."
        )

        try:
            # ✅ CORRECCIÓN: Agregamos el mensaje del usuario con el texto a analizar 
            # para evitar el error "contents must not be empty"
            fact_res_raw = await ask_llm(
                messages=[
                    {"role": "system", "content": extraction_system},
                    {"role": "user", "content": f"New text to analyze: '{text}'"} 
                ],
                db=db,
                max_tokens=100,
                caller="fact_extractor",
                user_id=user_id
            )
            
            fact_val = _ensure_string(fact_res_raw).strip()

            if fact_val and fact_val != "[NO_FACT]":
                if existing_obj:
                    # ✅ Actualización de hecho existente
                    existing_obj.fact_value = fact_val
                    existing_obj.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    # ✅ Creación de hecho nuevo
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

    # Commit final de todos los hechos procesados
    await db.commit()
    return extracted_facts