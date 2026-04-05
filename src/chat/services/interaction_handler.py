# src/chat/services/interaction_handler.py
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models import Message, Chat, MessageRole, User
# Asegúrate de que la ruta de UserMessageCorrection sea la correcta en tu nuevo proyecto
from src.chat.models import UserMessageCorrection 

# --- SERVICIOS REFACCIONADOS ---
from src.chat.services.message_service import MessageService
# Nota: He corregido el nombre de ReadStatusService que faltaba en tu snippet anterior
from src.chat.services.read_status_service import ReadStatusService 
from src.chat.services.ai_logic_service import (
    generate_avatar_response,
    process_and_store_semantic_facts
)
from src.chat.services.text_analysis_service import (
    correct_user_message, 
    evaluate_user_message_score
)

# ✅ CAMBIO CLAVE: Importamos el nuevo procesador de aprendizaje
from src.learning_analysis.services.processor import process_learning_analysis

from src.utils import highlight_differences

logger = logging.getLogger(__name__)

class InteractionHandler:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.msg_service = MessageService(db)
        self.read_service = ReadStatusService(db)

    # ... (el método process_interaction_by_guid se mantiene igual) ...

    async def _run_correction_pipeline(self, user_msg: Message, language: str) -> Optional[Dict[str, Any]]:
        """Analiza gramática, score y diferencias."""
        try:
            # 1. Obtener corrección de texto
            corrected_text = await correct_user_message(
                db=self.db,
                user_message=user_msg.content,
                user=self.user,
                language=language
            )
            
            # 2. Evaluar score
            score = await evaluate_user_message_score(
                db=self.db,
                user_message=user_msg.content,
                user=self.user,
                language=language
            )

            highlighted = None
            if corrected_text:
                highlighted = highlight_differences(user_msg.content, corrected_text)
                
                # ✅ CAMBIO CLAVE: Usamos el nuevo flujo de Learning Analysis
                # Este ya se encarga de llamar al analyzer y a la persistence.
                await process_learning_analysis(
                    db=self.db, 
                    user_id=self.user.id,
                    original_text=user_msg.content, 
                    corrected_text=corrected_text,
                    message_id=user_msg.id, 
                    language=language
                )

            # 3. Persistir log de corrección visual para el chat
            correction_log = UserMessageCorrection(
                user_id=self.user.id,
                message_id=user_msg.id,
                original_text=user_msg.content,
                corrected_text=corrected_text or user_msg.content,
                score=score,
                highlighted_diff=highlighted
            )
            self.db.add(correction_log)

            return {
                "type": "correction_feedback",
                "original_message_guid": str(user_msg.guid),
                "highlighted_diff": highlighted,
                "score": score,
                "corrected_text": corrected_text
            }
        except Exception as e:
            logger.error(f"Error in correction pipeline: {e}", exc_info=True)
            return None