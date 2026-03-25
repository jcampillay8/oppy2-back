# src/ai_management/services.py
import asyncio
import logging
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from json_repair import repair_json as repair

from .client import call_gemini_api
from .models import LLMRequestLog, AIModelConfig
from .schemas import AIResponse

logger = logging.getLogger(__name__)

async def ask_oppy_ai(
    db: AsyncSession,
    system_instruction: str,
    user_prompt: str,
    user_id: int,
    caller: str,
    model_name: Optional[str] = None,
    expect_json: bool = False,
    retries: int = 2
) -> str:
    """
    Orquestador de IA: 
    1. Obtiene configuración dinámica de la DB.
    2. Ejecuta la llamada con reintentos y backoff.
    3. Repara el JSON si es necesario.
    4. Registra métricas y costos en LLMRequestLog.
    """
    attempt = 0
    last_error = None

    # 1. Obtener la configuración del modelo desde la DB (Data-Driven)
    try:
        query = select(AIModelConfig).where(AIModelConfig.is_active == True)
        if model_name:
            query = query.where(AIModelConfig.model_name == model_name)
        else:
            query = query.where(AIModelConfig.is_default == True)
        
        result = await db.execute(query)
        model_cfg = result.scalar_one_or_none()
        
        if not model_cfg:
            raise ValueError(f"Configuración de IA '{model_name or 'Default'}' no encontrada o inactiva.")
            
    except Exception as e:
        logger.error(f"Error crítico al consultar configuración de IA: {e}")
        return _fallback_message(expect_json)

    # 2. Bucle de ejecución con reintentos
    while attempt <= retries:
        try:
            ai_res: AIResponse = await call_gemini_api(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                model_cfg=model_cfg,
                expect_json=expect_json
            )

            # --- DEFENSA EN PROFUNDIDAD: Reparación de Contenido ---
            final_content = ai_res.content
            if expect_json:
                final_content = repair(ai_res.content)

            # 3. Registrar éxito y métricas
            log = LLMRequestLog(
                user_id=user_id,
                caller=caller,
                model_name=model_cfg.model_name,
                input_tokens=ai_res.input_tokens,
                output_tokens=ai_res.output_tokens,
                total_tokens=ai_res.total_tokens,
                estimated_cost=ai_res.estimated_cost,
                request_duration_ms=ai_res.duration_ms,
                api_success=True
            )
            db.add(log)
            await db.commit()
            
            return final_content

        except Exception as e:
            attempt += 1
            last_error = str(e)
            logger.warning(f"Intento {attempt}/{retries+1} fallido para {caller}: {e}")
            
            if attempt <= retries:
                # Backoff exponencial: 2s, 4s...
                await asyncio.sleep(2 ** attempt)
            else:
                # 4. Registro de fallo final persistente
                log = LLMRequestLog(
                    user_id=user_id,
                    caller=caller,
                    model_name=model_cfg.model_name,
                    api_success=False,
                    error_message=last_error,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    estimated_cost=0.0
                )
                db.add(log)
                await db.commit()
                
    return _fallback_message(expect_json)

def _fallback_message(expect_json: bool) -> str:
    """Retorna un mensaje de error consistente según el formato esperado."""
    if expect_json:
        return json.dumps({
            "error": "service_unavailable", 
            "message": "No pude procesar la respuesta adecuadamente.",
            "score": 0,
            "feedback": "Error de conexión con el evaluador."
        })
    return "Lo siento, tuve un problema técnico. Por favor intenta de nuevo en unos momentos."