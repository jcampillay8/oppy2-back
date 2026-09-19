import random
import unicodedata
import re
import json
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

def expand_contractions(text: str) -> str:
    contractions = {
        r"\bit's\b": "it is",
        r"\bthat's\b": "that is",
        r"\bthere's\b": "there is",
        r"\bwhat's\b": "what is",
        r"\bdon't\b": "do not",
        r"\bdoesn't\b": "does not",
        r"\bdidn't\b": "did not",
        r"\bcan't\b": "cannot",
        r"\bcouldn't\b": "could not",
        r"\bwon't\b": "will not",
        r"\bwouldn't\b": "would not",
        r"\bshouldn't\b": "should not",
        r"\bisn't\b": "is not",
        r"\baren't\b": "are not",
        r"\bwasn't\b": "was not",
        r"\bweren't\b": "were not",
        r"\bthey're\b": "they are",
        r"\bwe're\b": "we are",
        r"\byou're\b": "you are",
        r"\bi'm\b": "i am",
        r"\bhaven't\b": "have not",
        r"\bhasn't\b": "has not",
        r"\bhadn't\b": "had not",
    }
    for pattern, replacement in contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = expand_contractions(text)
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def strip_subject_pronouns(text: str) -> str:
    return re.sub(r'^(it|they|that|he|she|there)\s+', '', text.strip(), flags=re.IGNORECASE)

async def validate_semantic_translation(
    db: AsyncSession,
    user_id: int,
    spanish_word: str,
    english_word: str,
    context_sentence: str,
    user_answer: str
) -> bool:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert bilingual English-Spanish ESL evaluator. "
                "The student was asked to translate a word or short phrase.\n"
                f"Target Spanish: '{spanish_word}'\n"
                f"Canonical Target English: '{english_word}'\n"
                f"Context Sentence: '{context_sentence}'\n"
                f"Student Answer: '{user_answer}'\n\n"
                "Determine if the student's answer is a valid, correct, or acceptable translation, synonym, "
                "or grammatical variation (such as including/omitting subject pronouns or using valid synonyms like 'mandatory' for 'required').\n"
                "Respond strictly with a JSON object: {\"is_valid\": true/false}"
            )
        }
    ]
    try:
        raw_res = await ask_oppy_ai(
            db=db,
            messages=messages,
            user_id=user_id,
            caller="vocabulary_semantic_evaluator",
            expect_json=True
        )
        data = json.loads(raw_res)
        return bool(data.get("is_valid", False))
    except Exception as e:
        print(f"Error evaluating semantic translation: {e}")
        return False


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
    raw_user_ans = request.user_answer.strip()
    
    is_correct = False
    is_semantic_match = False
    
    if raw_user_ans != "" and raw_user_ans != "_timeout_":
        user_ans = normalize_text(raw_user_ans)
        eng_target = normalize_text(word.english_word)
        spa_target = normalize_text(word.spanish_word)
        
        dist_eng = levenshtein_distance(user_ans, eng_target)
        dist_spa = levenshtein_distance(user_ans, spa_target)
        
        # Probar remover pronombres de sujeto (ej. "it already existed" vs "already existed")
        user_no_p = strip_subject_pronouns(user_ans)
        eng_no_p = strip_subject_pronouns(eng_target)
        spa_no_p = strip_subject_pronouns(spa_target)
        
        dist_eng_no_p = levenshtein_distance(user_no_p, eng_no_p)
        dist_spa_no_p = levenshtein_distance(user_no_p, spa_no_p)
        
        is_direct_match = (
            dist_eng <= 1 or dist_spa <= 1 or 
            dist_eng_no_p <= 1 or dist_spa_no_p <= 1
        )
        
        if is_direct_match:
            is_correct = True
        else:
            # Fallback inteligente con IA para evaluar sinónimos legítimos (ej: mandatory vs required)
            is_semantic_match = await validate_semantic_translation(
                db=db,
                user_id=user_id,
                spanish_word=word.spanish_word,
                english_word=word.english_word,
                context_sentence=word.context_sentence or "",
                user_answer=raw_user_ans
            )
            is_correct = is_semantic_match
        
    feedback = ""
    correct_ans = word.english_word # Por defecto mostramos el inglés
    
    if is_correct:
        word.score = max(0, word.score - 1)
        if word.score == 0:
            word.is_mastered = True
            feedback = "¡Dominaste esta palabra!"
        else:
            if is_semantic_match:
                feedback = f"¡Excelente sinónimo! '{raw_user_ans}' es una traducción válida."
            else:
                feedback = "¡Correcto!"
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

