# src/onboarding/services.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from src.models import User
from src.onboarding.models import PlacementTest
from . import schemas

logger = logging.getLogger(__name__)

async def get_user_onboarding_status(db: AsyncSession, user: User) -> dict:
    is_default_google_username = user.username == user.email
    
    if not user.username or len(user.username.strip()) < 3 or is_default_google_username:
        return {"needs_onboarding": True, "current_step": 1, "target_language": None}
    
    if not user.occupation or len(user.occupation.strip()) < 2:
        return {"needs_onboarding": True, "current_step": 2, "target_language": None}
    if not user.bio or len(user.bio.strip()) < 5:
        return {"needs_onboarding": True, "current_step": 3, "target_language": None}

    # 2. Validar Selección de Idioma (Banderas)
    result = await db.execute(select(PlacementTest).where(PlacementTest.user_id == user.id))
    test_record = result.scalars().first()

    if not test_record:
        # Perfil completo (Vistas 1,2,3), ahora a la Vista 4 (Banderas)
        return {"needs_onboarding": True, "current_step": 4, "target_language": None}

    # 3. Validar Test (Vista 5)
    if not test_record.is_completed:
        return {"needs_onboarding": True, "current_step": 5, "target_language": test_record.target_language}

    # 4. Finalizado
    return {"needs_onboarding": False, "current_step": 6, "target_language": test_record.target_language}

async def update_onboarding_data(db: AsyncSession, user: User, data: schemas.OnboardingProfileUpdate):
    logger.info(f"--- ONBOARDING UPDATE START ---")
    logger.info(f"Incoming Data -> username: '{data.username}', occupation: '{data.occupation}', bio: '{data.bio}'")

    if data.username and data.username.strip():
        user.username = data.username
    
    if data.occupation and data.occupation.strip():
        user.occupation = data.occupation
        
    if data.bio and data.bio.strip():
        user.bio = data.bio

    try:
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"SUCCESS: Usuario {user.id} actualizado en DB")
        
        # 🚨 LA CLAVE: Retornamos el diccionario de estado que espera el schema
        # Esto llamará a tu lógica de 'if not user.username return step 1...'
        status = await get_user_onboarding_status(db, user)
        return status

    except Exception as e:
        logger.error(f"ERROR en update_onboarding_data: {str(e)}")
        await db.rollback()
        raise e
        
async def set_user_target_language(db: AsyncSession, user: User, selection: schemas.LanguageSelection):
    """Crea o inicializa el registro del test con el idioma seleccionado."""
    query = select(PlacementTest).where(
        PlacementTest.user_id == user.id,
        PlacementTest.target_language == selection.target_language
    )
    result = await db.execute(query)
    test = result.scalar_one_or_none()

    if not test:
        # Si no existe, creamos el registro inicial
        test = PlacementTest(
            user_id=user.id,
            target_language=selection.target_language,
            is_completed=False
        )
        db.add(test)
    else:
        # Si ya existe, nos aseguramos de que pueda re-intentarlo
        test.is_completed = False

    await db.commit()
    return {"status": "success", "target_language": selection.target_language}

async def process_test_results(db: AsyncSession, user: User, payload: schemas.PlacementTestSubmit):
    """Recibe puntajes, calcula nivel CEFR y guarda (Crea el registro si no existe)."""
    
    # Cálculo de nivel (Promedio simple)
    avg = (payload.writing_result + payload.reading_result + 
           payload.listening_result + payload.speaking_result) / 4
    
    level = "A1"
    if avg >= 95: level = "C2"
    elif avg >= 80: level = "C1"
    elif avg >= 60: level = "B2"
    elif avg >= 40: level = "B1"
    elif avg >= 20: level = "A2"

    # BUSCAR O CREAR (Upsert)
    query = select(PlacementTest).where(
        PlacementTest.user_id == user.id,
        PlacementTest.target_language == payload.target_language
    )
    result = await db.execute(query)
    test = result.scalar_one_or_none()

    if not test:
        # Si por algún motivo no se creó al elegir idioma, lo creamos ahora
        test = PlacementTest(
            user_id=user.id, 
            target_language=payload.target_language
        )
        db.add(test)

    # Actualizamos los datos
    test.writing_result = payload.writing_result
    test.reading_result = payload.reading_result
    test.listening_result = payload.listening_result
    test.speaking_result = payload.speaking_result
    test.suggested_level = level
    test.is_completed = True
    test.completed_at = datetime.now(timezone.utc) # Usar timezone.utc para consistencia

    await db.commit()
    await db.refresh(test)
    return test