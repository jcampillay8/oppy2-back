# src/books/routers.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.books.models import Book, Chapter, Sentence, UserBookProgress, UserChapterProgress
from src.books.schemas import BookResponse, ChapterResponse, SentenceResponse, ProgressUpdateRequest
from src.books.services import process_pdf_upload

router = APIRouter(prefix="/api/books", tags=["Books"])

@router.post("/upload", response_model=BookResponse)
async def upload_book(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    book = await process_pdf_upload(file, current_user.id, db)
    return book

@router.get("/", response_model=List[BookResponse])
async def get_books(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    query = select(Book).where(Book.uploaded_by_id == current_user.id)
    result = await db.execute(query)
    books = result.scalars().all()
    
    response_books = []
    for book in books:
        prog_q = select(UserBookProgress).where(
            UserBookProgress.book_id == book.id,
            UserBookProgress.user_id == current_user.id
        )
        prog_res = await db.execute(prog_q)
        progress = prog_res.scalar_one_or_none()
        
        book_resp = BookResponse.model_validate(book)
        if progress:
            book_resp.progress_percentage = progress.progress_percentage
            book_resp.is_completed = progress.is_completed
        response_books.append(book_resp)
        
    return response_books

@router.get("/{book_id}/chapters", response_model=List[ChapterResponse])
async def get_chapters(
    book_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    query = select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number)
    result = await db.execute(query)
    chapters = result.scalars().all()
    
    response_chapters = []
    for chapter in chapters:
        prog_q = select(UserChapterProgress).where(
            UserChapterProgress.chapter_id == chapter.id,
            UserChapterProgress.user_id == current_user.id
        )
        prog_res = await db.execute(prog_q)
        progress = prog_res.scalar_one_or_none()
        
        chap_resp = ChapterResponse.model_validate(chapter)
        if progress:
            chap_resp.is_read = progress.is_read
            chap_resp.last_read_sentence_index = progress.last_read_sentence_index
            chap_resp.progress_percentage = progress.progress_percentage
        response_chapters.append(chap_resp)
        
    return response_chapters

@router.get("/{book_id}/chapters/{chapter_id}/sentences", response_model=List[SentenceResponse])
async def get_sentences(
    book_id: int,
    chapter_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    query = select(Sentence).where(Sentence.chapter_id == chapter_id).order_by(Sentence.sentence_index)
    result = await db.execute(query)
    sentences = result.scalars().all()
    return sentences

@router.put("/progress")
async def update_progress(
    req: ProgressUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    chap_query = select(Chapter).where(Chapter.id == req.chapter_id)
    chap_res = await db.execute(chap_query)
    chapter = chap_res.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
        
    ucp_query = select(UserChapterProgress).where(
        UserChapterProgress.chapter_id == chapter.id,
        UserChapterProgress.user_id == current_user.id
    )
    ucp_res = await db.execute(ucp_query)
    chapter_progress = ucp_res.scalar_one_or_none()
    
    if not chapter_progress:
        chapter_progress = UserChapterProgress(
            user_id=current_user.id,
            chapter_id=chapter.id
        )
        db.add(chapter_progress)
        
    chapter_progress.last_read_sentence_index = req.current_sentence_index
    if chapter.total_sentences > 0:
        pct = (req.current_sentence_index / chapter.total_sentences) * 100
        chapter_progress.progress_percentage = min(100.0, pct)
        if req.current_sentence_index >= chapter.total_sentences - 1:
            chapter_progress.is_read = True
            chapter_progress.progress_percentage = 100.0
            
    ubp_query = select(UserBookProgress).where(
        UserBookProgress.book_id == chapter.book_id,
        UserBookProgress.user_id == current_user.id
    )
    ubp_res = await db.execute(ubp_query)
    book_progress = ubp_res.scalar_one_or_none()
    
    if not book_progress:
        book_progress = UserBookProgress(
            user_id=current_user.id,
            book_id=chapter.book_id
        )
        db.add(book_progress)
        
    book_progress.current_chapter_id = chapter.id
    book_progress.current_sentence_index = req.current_sentence_index
    
    book_query = select(Book).where(Book.id == chapter.book_id)
    book_res = await db.execute(book_query)
    book = book_res.scalar_one()
    
    if book.total_chapters > 0:
        base_pct = ((chapter.chapter_number - 1) / book.total_chapters) * 100
        chap_contrib = (chapter_progress.progress_percentage / 100.0) * (100 / book.total_chapters)
        book_progress.progress_percentage = min(100.0, base_pct + chap_contrib)
        
        if chapter.chapter_number == book.total_chapters and chapter_progress.is_read:
            book_progress.is_completed = True
            book_progress.progress_percentage = 100.0

    await db.commit()
    return {"status": "ok"}
