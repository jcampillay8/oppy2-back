import json
import random
import re
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai
from src.utils import highlight_differences
from src.learning_analysis.schemas import (
    TranslationChallengeResponse,
    TranslationEvaluationRequest,
    TranslationEvaluationResponse,
    ErrorFound,
    TextDifference
)
from src.learning_analysis.services.persistence import get_active_focus_by_user
from sqlalchemy import update
from src.learning_analysis.models import LearningFocus

# Load Prompts
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""

async def generate_translation_challenge(db: AsyncSession, user_id: int) -> TranslationChallengeResponse:
    # 1. Tournament Selection
    active_focus = await get_active_focus_by_user(db, user_id)
    
    target_category = "VerbTenseError" # Fallback
    
    if active_focus:
        if len(active_focus) >= 2:
            # Seleccionar 2 al azar
            candidates = random.sample(active_focus, 2)
            # Elegir el de mayor puntaje
            winner = max(candidates, key=lambda f: f.priority_score)
            target_category = winner.category.name if winner.category else "VerbTenseError"
        else:
            target_category = active_focus[0].category.name if active_focus[0].category else "VerbTenseError"

    # 2. Call LLM
    system_prompt = load_prompt("translation_generator.md")
    
    # Lista de temas variados para evitar que el LLM repita las mismas oraciones
    topics = [
        "Tecnología e Inteligencia Artificial",
        "Cocina y recetas gourmet",
        "Viajes y culturas exóticas",
        "Deportes extremos",
        "Música y conciertos",
        "Arte y museos",
        "Historia antigua",
        "Ciencia ficción y el espacio",
        "Rutina de oficina y negocios",
        "Misterio y detectives",
        "Naturaleza y medio ambiente",
        "Fantasía épica",
        "Medicina y salud",
        "Psicología",
        "Videojuegos"
    ]
    random_topic = random.choice(topics)
    
    # Asumimos que el usuario tiene nivel, si no, usamos B1
    user_prompt = f"Target Category: {target_category}\nCEFR Level: B1\nTopic: {random_topic}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    raw_response = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="translation_challenge_generator",
        expect_json=True
    )
    
    # parse JSON
    data = json.loads(raw_response)
    return TranslationChallengeResponse(**data)

async def evaluate_translation(db: AsyncSession, user_id: int, request: TranslationEvaluationRequest) -> TranslationEvaluationResponse:
    system_prompt = load_prompt("evaluator.md")
    
    user_prompt = f"Student Profile: Weakness in {request.grammar_target}\nStudent Text: {request.user_translation}"
    if request.spanish_sentence:
        user_prompt += f"\nOriginal Spanish Sentence: {request.spanish_sentence}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    raw_response = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="translation_challenge_evaluator",
        expect_json=True
    )
    
    data = json.loads(raw_response)
    errors = data.get("errors_found", [])
    corrected_text = data.get("corrected_text", request.user_translation)
    
    # Programmatic Equivalence for Relative Pronouns (that/which/who/whom) and Singular Their (their vs his or her):
    # If the ONLY difference between user_translation and corrected_text is relative pronoun usage/omission
    # or using 'their' vs 'his or her', treat user_translation as 100% PERFECT (zero red diffs, clear all false errors).
    user_norm = re.sub(r'\b(that|which|who|whom|his or her|his/her|their)\b', '', request.user_translation, flags=re.IGNORECASE)
    user_norm = re.sub(r'\s+', ' ', user_norm).strip().rstrip('.!').lower()
    
    corr_norm = re.sub(r'\b(that|which|who|whom|his or her|his/her|their)\b', '', corrected_text, flags=re.IGNORECASE)
    corr_norm = re.sub(r'\s+', ' ', corr_norm).strip().rstrip('.!').lower()
    
    if user_norm == corr_norm:
        corrected_text = request.user_translation
        errors = []

    # 3. Update DB (Spaced Repetition +1 / -1)
    # Buscamos si el usuario cometió el error específico que estábamos probando
    failed_target = any(e.get("category") == request.grammar_target for e in errors)
    
    # Update logic
    active_focus = await get_active_focus_by_user(db, user_id)
    focus_to_update = next((f for f in active_focus if f.category and f.category.name == request.grammar_target), None)
    
    if focus_to_update:
        if failed_target:
            focus_to_update.priority_score += 1
            focus_to_update.total_count += 1
        else:
            focus_to_update.priority_score = max(0, focus_to_update.priority_score - 1)
        
        await db.commit()

    from src.learning_analysis.services.persistence import increment_user_daily_activity
    await increment_user_daily_activity(db, user_id, course_type="ielts")

    # 4. Highlight differences
    diffs_raw = highlight_differences(request.user_translation, corrected_text)
    differences = [TextDifference(**d) for d in diffs_raw]
    
    return TranslationEvaluationResponse(
        corrected_text=corrected_text,
        feedback_text=data.get("feedback_text", ""),
        errors_found=[ErrorFound(**e) for e in errors],
        differences=differences
    )

async def generate_guided_practice_challenge(
    db: AsyncSession, 
    user_id: int, 
    current_topic: str, 
    cefr_level: str, 
    past_topics: list[str]
) -> TranslationChallengeResponse:
    # 1. 80/20 Rule for Topic Selection
    use_past_topic = False
    if past_topics and random.random() < 0.2:
        target_topic = random.choice(past_topics)
        use_past_topic = True
    else:
        target_topic = current_topic

    # 2. Tournament Selection for Grammar Target (same as normal practice)
    active_focus = await get_active_focus_by_user(db, user_id)
    target_category = "VerbTenseError" # Fallback
    
    if active_focus:
        if len(active_focus) >= 2:
            candidates = random.sample(active_focus, 2)
            winner = max(candidates, key=lambda f: f.priority_score)
            target_category = winner.category.name if winner.category else "VerbTenseError"
        else:
            target_category = active_focus[0].category.name if active_focus[0].category else "VerbTenseError"

    # 3. Inject a random scenario to avoid repetitive sentences for the same topic
    scenarios = [
        "En una cafetería", "En la oficina", "Durante una entrevista de trabajo",
        "Chateando con un amigo", "En el aeropuerto", "En un restaurante",
        "En el médico", "Pidiendo indicaciones en la calle", "Comprando ropa",
        "En una fiesta", "En clases", "Escribiendo un correo",
        "En una llamada telefónica", "En la recepción del hotel", "En un taxi",
        "Hablando con un extraño", "Discutiendo con un compañero de cuarto",
        "Planeando un viaje", "Hablando de hobbies", "Haciendo un reclamo",
        "En el supermercado", "En el gimnasio", "Paseando al perro",
        "Conociendo a los suegros", "En una primera cita"
    ]
    random_scenario = random.choice(scenarios)

    # 4. Call LLM
    system_prompt = load_prompt("guided_practice_generator.md")
    
    user_prompt = (
        f"Target Category: {target_category}\n"
        f"CEFR Level: {cefr_level}\n"
        f"Topic: {target_topic}\n"
        f"Specific Scenario: {random_scenario}"
    )
    if use_past_topic:
        user_prompt += "\n(Note: This is a review topic from a past unit)"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    raw_response = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="guided_practice_challenge_generator",
        expect_json=True
    )
    
    data = json.loads(raw_response)
    return TranslationChallengeResponse(**data)

from src.learning_analysis.services.ielts_syllabus import get_ielts_unit_info, get_ielts_unit_markdown

async def generate_ielts_practice_challenge(
    db: AsyncSession,
    user_id: int,
    level: int,
    unit: int
) -> TranslationChallengeResponse:
    unit_info = get_ielts_unit_info(level, unit)
    unit_title = unit_info["title"] if unit_info else f"Level {level} Unit {unit}"
    markdown_content = get_ielts_unit_markdown(level, unit) or ""
    
    # Slice first 1500 chars of markdown content for context if long
    context_snippet = markdown_content[:1500] if len(markdown_content) > 1500 else markdown_content

    scenarios = [
        "En un ensayo académico de IELTS Writing Task 2",
        "En una respuesta de IELTS Speaking Part 2",
        "En una presentación profesional",
        "En un debate o discusión sobre temas globales",
        "En un correo formal de negocios",
        "En una conversación cotidiana en un ambiente universitario"
    ]
    random_scenario = random.choice(scenarios)

    system_prompt = load_prompt("guided_practice_generator.md")
    
    user_prompt = (
        f"Target Category: IELTS Grammar Target\n"
        f"Unit Title: {unit_title}\n"
        f"Grammar Lesson Context Snippet:\n{context_snippet}\n\n"
        f"Specific Scenario: {random_scenario}\n"
        f"Instruction: Generate a natural Spanish sentence and its English translation that requires using the grammar rule/structure described in the Unit Title/Grammar Lesson Context."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    raw_response = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="ielts_practice_challenge_generator",
        expect_json=True
    )
    
    data = json.loads(raw_response)
    return TranslationChallengeResponse(**data)


