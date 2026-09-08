import random
import unicodedata
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
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
        
    new_word = VocabularyWord(
        user_id=user_id,
        spanish_word=word_in.spanish_word,
        english_word=word_in.english_word,
        context_sentence=word_in.context_sentence,
        score=3,
        is_mastered=False
    )
    db.add(new_word)
    await db.commit()
    await db.refresh(new_word)
    return new_word

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

async def evaluate_word(db: AsyncSession, user_id: int, request: VocabularyPracticeRequest) -> VocabularyPracticeResult:
    word = await db.get(VocabularyWord, request.word_id)
    if not word or word.user_id != user_id:
        raise HTTPException(status_code=404, detail="Word not found")
        
    # Puede que estemos preguntando de Esp->Ing o Ing->Esp
    # Dado que el backend no sabe qué dirección se preguntó, vamos a verificar 
    # si la respuesta se parece al inglés o al español.
    # (Lo más robusto sería que el frontend envíe la dirección, pero podemos verificar ambos).
    
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
    
    return VocabularyPracticeResult(
        is_correct=is_correct,
        correct_answer=correct_ans,
        new_score=word.score,
        is_mastered=word.is_mastered,
        feedback=feedback
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

