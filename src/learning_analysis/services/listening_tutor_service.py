import json
import base64
import random
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_management.services import ask_oppy_ai
from src.ai_management.audio_client import tts_client, LISTENING_VOICES
from src.learning_analysis.schemas import (
    ListeningChallengeResponse, 
    TranslationEvaluationRequest, 
    TranslationEvaluationResponse,
    ErrorFound,
    TextDifference
)
from src.learning_analysis.services.ielts_syllabus import get_ielts_unit_info, get_ielts_unit_markdown
from src.learning_analysis.services.tutor_service import get_active_focus_by_user, evaluate_translation, load_prompt
from src.utils import highlight_differences

logger = logging.getLogger(__name__)

async def generate_listening_challenge(
    db: AsyncSession,
    user_id: int,
    level: int,
    unit: int
) -> ListeningChallengeResponse:
    """
    Genera un ejercicio de comprensión auditiva (Listening):
    1. Carga contexto del temario IELTS.
    2. Genera una oración en inglés acorde al target gramatical.
    3. Elige una voz al azar entre las 8 de Google Cloud TTS.
    4. Sintetiza el audio en MP3 y lo convierte a Data URI Base64.
    """
    unit_info = get_ielts_unit_info(level, unit)
    unit_title = unit_info["title"] if unit_info else f"Level {level} Unit {unit}"
    markdown_content = get_ielts_unit_markdown(level, unit) or ""
    context_snippet = markdown_content[:1500] if len(markdown_content) > 1500 else markdown_content

    scenarios = [
        "En una conversación telefónica laboral",
        "En un anuncio de aeropuerto o estación",
        "En una conferencia universitaria",
        "En una reunión de negocios",
        "En una entrevista de trabajo",
        "En un diálogo entre compañeros de estudio"
    ]
    random_scenario = random.choice(scenarios)

    system_prompt = load_prompt("guided_listening_generator.md")
    user_prompt = (
        f"Target Category: IELTS Grammar Target\n"
        f"Unit Title: {unit_title}\n"
        f"Grammar Lesson Context Snippet:\n{context_snippet}\n\n"
        f"Specific Scenario: {random_scenario}\n"
        f"Instruction: Generate a natural English sentence suitable for a listening dictation practice."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    raw_response = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="ielts_listening_challenge_generator",
        expect_json=True
    )

    data = json.loads(raw_response)
    english_sentence = data.get("english_sentence", "The team worked hard to finish the project on time.").strip()
    context_desc = data.get("context", "Escucha el siguiente audio y escribe exactamente lo que escuchas.")
    grammar_target = data.get("grammar_target", "VerbTenseError")

    # Selección aleatoria entre las 8 voces asignadas
    voice_names = list(LISTENING_VOICES.keys())
    selected_voice = random.choice(voice_names)
    voice_gender = LISTENING_VOICES[selected_voice]["gender"]

    # Sintetizar audio MP3 usando Google Cloud TTS
    audio_base64 = ""
    try:
        audio_bytes = await tts_client.synthesize_speech_voice(
            text=english_sentence,
            voice_name=selected_voice,
            speaking_rate=1.0
        )
        b64_str = base64.b64encode(audio_bytes).decode('utf-8')
        audio_base64 = f"data:audio/mp3;base64,{b64_str}"
    except Exception as e:
        logger.error(f"Error generando audio TTS para Listening Challenge: {e}")

    return ListeningChallengeResponse(
        context=context_desc,
        english_sentence=english_sentence,
        voice_name=selected_voice,
        voice_gender=voice_gender,
        audio_base64=audio_base64,
        grammar_target=grammar_target
    )
