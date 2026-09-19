import random
import unicodedata
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from src.ai_management.services import ask_oppy_ai
from src.learning_analysis.models import VocabularyWord
from src.learning_analysis.schemas import VocabularyWordCreate, VocabularyWordResponse, VocabularyPracticeRequest, VocabularyPracticeResult

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]

def normalize_text(text: str) -> str:
    # Quitar acentos, espacios extras y pasar a minúscula
    text = text.strip().lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

async def generate_vocabulary_context(db: AsyncSession, user_id: int, spanish_word: str, english_word: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert English-Spanish ESL tutor. Generate a simple, clear, natural example sentence pair "
                "using the Spanish word and English word provided. "
                "Output MUST be exactly in this format without markdown or extra text:\n"
                "ES: <Spanish sentence> | EN: <English sentence>"
            )
        },
        {
            "role": "user",
            "content": f"Spanish word: {spanish_word}\nEnglish word: {english_word}"
        }
    ]
    try:
        response_text = await ask_oppy_ai(
            db=db,
            messages=messages,
            user_id=user_id,
            caller="vocabulary_context_generator",
            expect_json=False
        )
        if response_text and "ES:" in response_text and "EN:" in response_text:
            return response_text.strip()
    except Exception as e:
        print(f"Error generating vocabulary context: {e}")
    
    return f"ES: Usamos la palabra '{spanish_word}' en esta oración. | EN: We use the word '{english_word}' in this sentence."

async def save_word(db: AsyncSession, user_id: int, word_in: VocabularyWordCreate) -> VocabularyWordResponse:
    # Ver si ya existe
    result = await db.execute(select(VocabularyWord).where(
        VocabularyWord.user_id == user_id,
        VocabularyWord.spanish_word == word_in.spanish_word,
        VocabularyWord.is_mastered == False
    ))
    existing = result.scalars().first()
    
    if existing:
        return existing
        
    context = word_in.context_sentence
    if not context or not context.strip():
        context = await generate_vocabulary_context(db, user_id, word_in.spanish_word, word_in.english_word)
        
    new_word = VocabularyWord(
        user_id=user_id,
        spanish_word=word_in.spanish_word,
        english_word=word_in.english_word,
        context_sentence=context,
        score=3,
        is_mastered=False
    )
    db.add(new_word)
    await db.commit()
    await db.refresh(new_word)
    return new_word

async def get_vocabulary_stats(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(select(VocabularyWord).where(VocabularyWord.user_id == user_id))
    all_words = result.scalars().all()
    
    total = len(all_words)
    in_review = sum(1 for w in all_words if not w.is_mastered)
    mastered = sum(1 for w in all_words if w.is_mastered)
    
    return {
        "total": total,
        "in_review": in_review,
        "mastered": mastered
    }


async def get_practice_word(db: AsyncSession, user_id: int) -> VocabularyWordResponse:
    result = await db.execute(select(VocabularyWord).where(
        VocabularyWord.user_id == user_id,
        VocabularyWord.is_mastered == False
    ))
    active_words = result.scalars().all()
    
    if not active_words:
        return None
        
    if len(active_words) >= 2:
        candidates = random.sample(list(active_words), 2)
        winner = max(candidates, key=lambda w: w.score)
        # Si empatan en score, max() ya devuelve el primero (tiebreak)
        return winner
        
    return active_words[0]

from src.learning_analysis.services.persistence import increment_user_vocab_activity

async def evaluate_word(db: AsyncSession, user_id: int, request: VocabularyPracticeRequest) -> VocabularyPracticeResult:
    word = await db.get(VocabularyWord, request.word_id)
    if not word or word.user_id != user_id:
        raise HTTPException(status_code=404, detail="Word not found")
        
    old_score = word.score
    
    user_ans = normalize_text(request.user_answer)
    eng_target = normalize_text(word.english_word)
    spa_target = normalize_text(word.spanish_word)
    
    dist_eng = levenshtein_distance(user_ans, eng_target)
    dist_spa = levenshtein_distance(user_ans, spa_target)
    
    # 1 de tolerancia por typo
    is_correct = dist_eng <= 1 or dist_spa <= 1
    
    # Manejar caso de timeout (el frontend mandará un string vacío o especial)
    if request.user_answer == "" or request.user_answer == "_timeout_":
        is_correct = False
        
    feedback = ""
    correct_ans = word.english_word # Por defecto mostramos el inglés
    
    if is_correct:
        word.score = max(0, word.score - 1)
        if word.score == 0:
            word.is_mastered = True
            feedback = "¡Dominaste esta palabra!"
        else:
            feedback = "¡Correcto!"
            if dist_eng == 1 or dist_spa == 1:
                feedback = "¡Casi perfecto! Ten cuidado con la ortografía."
    else:
        word.score += 1
        feedback = "Incorrecto o tiempo agotado."
        
    await db.commit()
    await db.refresh(word)
    
    # Incrementar actividad acumulada en el heatmap (3 vocabularios = +1 actividad)
    activity_incremented = await increment_user_vocab_activity(db, user_id)
    
    return VocabularyPracticeResult(
        is_correct=is_correct,
        correct_answer=correct_ans,
        old_score=old_score,
        new_score=word.score,
        is_mastered=word.is_mastered,
        feedback=feedback,
        activity_incremented=activity_incremented
    )


async def get_user_vocabulary_list(db: AsyncSession, user_id: int) -> list[VocabularyWordResponse]:
    result = await db.execute(
        select(VocabularyWord)
        .where(VocabularyWord.user_id == user_id)
        .order_by(VocabularyWord.created_at.desc())
    )
    words = result.scalars().all()
    return list(words)

async def delete_word(db: AsyncSession, user_id: int, word_id: int) -> dict:
    word = await db.get(VocabularyWord, word_id)
    if not word or word.user_id != user_id:
        raise HTTPException(status_code=404, detail="Word not found or not owned by user")
    
    await db.delete(word)
    await db.commit()
    return {"message": "Word deleted successfully", "id": word_id}

