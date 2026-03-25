# src/onboarding/constants.py

def calculate_cefr_level(score: float) -> str:
    """Mapea el puntaje numérico al nivel CEFR basado en los rangos de Jaime."""
    if score >= 95: return "C2"
    if score >= 86: return "C1"
    if score >= 76: return "B2"
    if score >= 51: return "B1"
    if score >= 31: return "A2"
    return "A1"