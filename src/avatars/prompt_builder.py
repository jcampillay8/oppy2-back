# src/ai_management/prompt_builder.py
#
# Este módulo ensambla las instrucciones (System Prompt) para los modelos LLM,
# utilizando la definición del Avatar y el contexto de hechos (facts).

from typing import List, Optional

# Importaciones ajustadas a tu nueva estructura modular
from src.avatars.config import LANGUAGE_MAP
from src.avatars.models import AvatarDefinition
from src.chat.models import ChatFact

def build_fact_context(facts: List[ChatFact]) -> str:
    """
    Construye una cadena de contexto a partir de una lista de hechos extraídos.
    Cada hecho se formatea en una frase separada.
    """
    return " ".join([f"{f.fact_value}." for f in facts if f.fact_value])

def _append_part_to_prompt(prompt_parts: list, prefix: str, value: str):
    """
    Función helper para añadir una parte al prompt, asegurando que termina en punto
    si el valor no lo tiene ya.
    """
    if value and isinstance(value, str):
        # Eliminar espacios en blanco y agregar punto si no está presente
        clean_value = value.strip()
        if not clean_value.endswith('.'):
            clean_value += '.'
        prompt_parts.append(f"{prefix}: {clean_value}")


def build_fact_context(facts: List[ChatFact]) -> str:
    """
    Convierte una lista de hechos (facts) extraídos de la base de datos 
    en un párrafo de contexto para que el Avatar "recuerde" detalles del usuario.
    """
    if not facts:
        return ""
    return " ".join([f"{f.fact_value}." for f in facts if f.fact_value])

def build_system_prompt_from_avatar_definition(avatar_def: AvatarDefinition) -> str:
    """
    Construye el prompt del sistema completo para un LLM a partir de un objeto AvatarDefinition.
    Transforma los campos de la DB en instrucciones narrativas.
    """
    prompt_parts = []
    
    # Lógica de herencia: Si el avatar tiene un 'host_profile' (perfil predefinido),
    # usamos esos datos; si no, usamos los datos personalizados del avatar_def.
    source_data = avatar_def.host_profile if avatar_def.host_profile_id else avatar_def
    
    # 1. Configuración de Idioma
    if avatar_def.language_preference:
        # Buscamos el nombre del idioma (ej: "English") basado en el código (ej: "en-US")
        llm_language_name = LANGUAGE_MAP.get(
            avatar_def.language_preference.lower(), 
            avatar_def.language_preference
        )
    else:
        llm_language_name = "English" # Default razonable para OppyChat

    prompt_parts.append(f"**IMPORTANT: All your responses MUST be in {llm_language_name}.**")

    # 2. Identidad y Roles
    if source_data.name:
        prompt_parts.append(f"Your name is {source_data.name}.")
    
    if source_data.role_avatar:
        prompt_parts.append(f"Your primary role is: {source_data.role_avatar}.")
    
    if source_data.role_usuario:
        prompt_parts.append(f"The user you are interacting with has the role of: {source_data.role_usuario}.")
    
    # 3. Misión y Contexto
    if source_data.objective:
        prompt_parts.append(f"Your primary objective is: {source_data.objective}.")
    
    if source_data.context:
        prompt_parts.append(f"The context of the interaction is as follows: {source_data.context}")

    # 4. Personalidad y Restricciones
    if source_data.character_traits:
        prompt_parts.append(f"Your character traits are: {source_data.character_traits}.")
    
    if source_data.rules:
        prompt_parts.append(f"You must strictly follow these rules: {source_data.rules}.")

    return "\n".join(prompt_parts).strip()