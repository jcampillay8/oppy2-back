# src/learning_analysis/services/processor.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .analyzer import analyze_linguistic_errors
from .persistence import save_analysis_results

logger = logging.getLogger(__name__)

async def process_learning_analysis(
    db: AsyncSession,
    user_id: int,
    original_text: str,
    corrected_text: str,
    message_id: int,
    language: str = "English"
):
    """
    Coordina la auditoría de IA y la persistencia de errores detectados.
    """
    # 1. Early return si no hay cambios (ahorro de tokens y procesamiento)
    if not original_text or not corrected_text or original_text.strip() == corrected_text.strip():
        return

    try:
        # 2. Paso 1: Auditoría IA (Especialista)
        # Delegamos la lógica de prompts y llamadas al LLM a analyzer.py
        detected_errors = await analyze_linguistic_errors(
            db, user_id, original_text, corrected_text
        )

        # 3. Validación de integridad de la respuesta del LLM
        if not isinstance(detected_errors, list) or len(detected_errors) == 0:
            logger.debug(f"No se detectaron errores específicos para el mensaje {message_id}")
            return

        # 4. Paso 2: Persistencia (Bibliotecario)
        # save_analysis_results ya maneja su propio commit/rollback interno 
        # para no afectar el guardado del mensaje original si este falla.
        await save_analysis_results(db, user_id, message_id, detected_errors)
        
        logger.info(f"Successfully processed {len(detected_errors)} errors for user {user_id}")

    except Exception as e:
        # Logueamos el error pero no levantamos la excepción hacia el chat
        # No queremos que el usuario no reciba su corrección porque el análisis falló.
        logger.error(f"Critical error in Learning Analysis flow: {e}", exc_info=True)
        try:
            await db.rollback()
        except:
            pass