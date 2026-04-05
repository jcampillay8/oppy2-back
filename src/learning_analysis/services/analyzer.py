# src/learning_analysis/services/analyzer.py
from typing import List, Dict, Any
from src.ai_management.services import ask_oppy_ai as ask_llm
from ..utils import parse_llm_json_safe

ERROR_LABELS = [
    "Verb Tense", "False Friends", "Prepositions", "Word Order", 
    "Article Usage", "Phrasal Verbs", "Question Formation", "Vocabulary"
]

async def analyze_linguistic_errors(
    db, user_id: int, original: str, corrected: str
) -> List[Dict[str, Any]]:
    """
    Realiza una auditoría multietiqueta. El LLM debe revisar la oración 
    buscando CADA una de las categorías definidas.
    """
    
    system_instruction = (
        "You are a linguistic auditor for an EdTech platform. "
        "Your goal is to perform a MULTI-LABEL analysis of the differences between "
        "an original text and its corrected version.\n\n"
        "FOR EACH error found, you must map it to one or more of these categories:\n"
        f"{', '.join(ERROR_LABELS)}.\n\n"
        "If a single mistake falls into multiple categories (e.g., a Phrasal Verb "
        "with a wrong Verb Tense), you MUST include both.\n"
        "Return a JSON object with a list of 'detected_errors'."
    )

    user_prompt = f"""
    Compare these two versions:
    Original: "{original}"
    Corrected: "{corrected}"

    For each correction made, provide:
    1. "category": The exact category name from the list.
    2. "incorrect_part": The specific segment that was wrong.
    3. "correct_part": The corrected segment.
    4. "explanation": A brief, professional explanation (max 15 words).
    5. "exercise_text_es": A natural Spanish sentence that would force the user 
       to produce the 'correct_part' when translating back to English.

    Format:
    {{
      "detected_errors": [
        {{
          "category": "...",
          "incorrect_part": "...",
          "correct_part": "...",
          "explanation": "...",
          "exercise_text_es": "..."
        }}
      ]
    }}
    """

    response_raw = await ask_llm(
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        db=db,
        user_id=user_id,
        response_format={"type": "json_object"},
        caller="LearningAnalysis_Auditor"
    )

    parsed = parse_llm_json_safe(response_raw)
    return parsed.get("detected_errors", []) if parsed else []