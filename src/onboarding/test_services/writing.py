# src/onboarding/test_services/writing.py
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from src.ai_management.services import ask_oppy_ai
from src.models import User

logger = logging.getLogger(__name__)

async def generate_writing_question(db: AsyncSession, user: User, target_lang: str) -> str:
    """
    Genera una pregunta personalizada nivel B1 basada en la ocupación y bio.
    Aplica lógica de relevancia para decidir si usar la bio o no.
    """
    
    # Preparamos el contexto
    occupation = user.occupation or "Estudiante"
    bio = user.bio or ""
    idioma_nombre = "Inglés" if target_lang == "en" else "Español"

    system_instruction = f"""
    Eres un examinador de idiomas experto y empático para la app OppyChat.
    Tu objetivo es generar UNA sola pregunta de escritura para un test diagnóstico de {idioma_nombre}.
    
    PERFIL DEL USUARIO:
    - Nombre: {user.username}
    - Ocupación: {occupation}
    - Bio: {bio}

    REGLAS DE GENERACIÓN:
    1. NIVEL: La pregunta debe ser entendible para un nivel B1 (Intermedio bajo).
    2. RELEVANCIA: Analiza si la 'Bio' aporta información que complemente la 'Ocupación'. 
       - SI aporta (ej: Ocupación: Cineasta, Bio: Escribo en un blog): Conecta ambos mundos.
       - NO aporta (ej: Ocupación: Pastelera, Bio: Salgo a trotar): Ignora la bio y enfócate 100% en la ocupación.
    3. ESTRUCTURA: Sé directo. Empieza con un breve saludo validando su perfil y luego lanza la pregunta.
    4. IDIOMA: Escribe la pregunta COMPLETAMENTE en {idioma_nombre}.
    5. RESTRICCIÓN: No uses lenguaje técnico extremadamente complejo.
    """

    user_prompt = "Genera la pregunta de escritura ahora."

    # AJUSTE: Construimos la lista de mensajes que espera ask_oppy_ai
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt}
    ]

    # Llamamos a tu orquestador de IA con el argumento 'messages'
    question = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user.id,
        caller="writing_test_generator",
        expect_json=False
    )

    return question.strip()

async def evaluate_writing_response(db: AsyncSession, user_id: int, user_answer: str, target_lang: str) -> dict:
    """
    Usa la IA para evaluar la respuesta del usuario.
    Retorna un JSON con score, feedback y nivel.
    """
    idioma_nombre = "Inglés" if target_lang == "en" else "Español"

    system_instruction = f"""
    Eres un evaluador de idiomas oficial (tipo TOEFL/IELTS). 
    Debes calificar la respuesta de un usuario a una prueba de escritura de {idioma_nombre}.

    CRITERIOS DE EVALUACIÓN:
    1. Gramática y Estructura.
    2. Vocabulario y Variedad.
    3. Coherencia y respuesta a la pregunta.

    FORMATO DE SALIDA (ESTRICTAMENTE JSON):
    {{
      "score": (número del 0 al 100),
      "feedback": "Breve explicación en ESPAÑOL de lo que hizo bien y qué mejorar",
      "suggested_level": "A1, A2, B1, B2, C1 o C2"
    }}
    """

    user_prompt = f"Evalúa esta respuesta de nivel diagnóstico: '{user_answer}'"

    # AJUSTE: Construimos la lista de mensajes para la evaluación
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt}
    ]

    # Llamamos a la IA esperando un JSON
    evaluation_json = await ask_oppy_ai(
        db=db,
        messages=messages,
        user_id=user_id,
        caller="writing_test_evaluator",
        expect_json=True
    )
    
    try:
        return json.loads(evaluation_json)
    except json.JSONDecodeError:
        # Fallback en caso de que la reparación de JSON falle
        logger.error(f"Error decodificando JSON de evaluación: {evaluation_json}")
        return {
            "score": 0,
            "feedback": "Error al procesar la respuesta de la IA.",
            "suggested_level": "N/A"
        }