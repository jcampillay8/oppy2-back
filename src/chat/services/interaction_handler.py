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
        # Nota: Asegúrate de que MessageService y ReadStatusService acepten solo 'db' en su __init__
        self.msg_service = MessageService(db)
        self.read_service = ReadStatusService(db)

    async def process_interaction_by_guid(
        self, 
        chat_guid: uuid.UUID, 
        user_message_content: str
    ) -> Tuple[Message, Message, Optional[Dict[str, Any]]]:
        """
        Orquestador principal:
        1. Busca el chat y valida.
        2. Guarda mensaje del usuario.
        3. Ejecuta pipeline de corrección y aprendizaje.
        4. Genera respuesta de la IA (Avatar).
        """
        # 1. Buscar el Chat con su definición de avatar
        stmt = select(Chat).where(Chat.guid == chat_guid).options(
            selectinload(Chat.avatar_definition)
        )
        result = await self.db.execute(stmt)
        chat = result.scalar_one_or_none()

        if not chat:
            raise ValueError("Chat not found")

        # 2. Guardar mensaje del Usuario
        user_msg = await self.msg_service.create_message(
            chat_id=chat.id,
            user_id=self.user.id,
            role=MessageRole.USER,
            content=user_message_content
        )
        await self.db.flush() # Para tener el ID de user_msg

        # 3. Pipeline de Corrección (Gramática, Score, Hechos)
        # Usamos el idioma preferido del avatar o inglés por defecto
        lang = chat.avatar_definition.language_preference if chat.avatar_definition else "en-US"
        feedback = await self._run_correction_pipeline(user_msg, lang)

        # 4. Generar respuesta de la IA
        llm_history = await self.msg_service.get_chat_history_for_llm(chat_id=chat.id, limit=10)

        # Filtramos el mensaje que acabamos de guardar para no duplicarlo 
        # (porque get_chat_history_for_llm trae los últimos N, incluyendo el actual)
        chat_history = [msg for msg in llm_history if msg["content"] != user_message_content]

        bot_response_text = await generate_avatar_response(
            db=self.db,
            chat=chat,
            user_id=self.user.id,
            user_message=user_message_content,
            chat_history=chat_history  # Sarah ahora tiene el contexto limpio
        )

        bot_msg = await self.msg_service.create_message(
            chat_id=chat.id,
            user_id=self.user.id,
            role=MessageRole.ASSISTANT,
            content=bot_response_text
        )

        # 5. Actualizar estado de lectura
        await self.read_service.mark_chat_as_read(chat_id=chat.id, user_id=self.user.id)

        return user_msg, bot_msg, feedback

    async def _run_correction_pipeline(self, user_msg: Message, language: str) -> Optional[Dict[str, Any]]:
        """Analiza gramática, hechos semánticos, score y aprendizaje."""
        try:
            # 🚀 PASO 0: EXTRACCIÓN DE HECHOS (Esto llenará chat_facts)
            # Se hace antes para que Sarah pueda usar esta info en su respuesta inmediata
            await process_and_store_semantic_facts(
                db=self.db,
                text=user_msg.content,
                user_id=self.user.id,
                chat_id=user_msg.chat_id,
                message_id=user_msg.id
            )

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