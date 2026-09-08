import asyncio
import pdfplumber
import nltk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile

from src.books.models import Book, Chapter, Sentence, UserBookProgress
import re

def _parse_pdf_to_chapters(file_path: str):
    text_content = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content += page_text + "\n"
                
    text_content = re.sub(r'(?<!\n)\n(?!\n)', ' ', text_content)
    chapter_chunks = re.split(r'(?i)^\s*(chapter \d+|prologue|epilogue)\s*$', text_content, flags=re.MULTILINE)
    
    chapters_to_create = []
    if len(chapter_chunks) == 1:
        chapters_to_create.append({"title": "Chapter 1", "text": chapter_chunks[0]})
    else:
        current_title = "Intro"
        for i, chunk in enumerate(chapter_chunks):
            if i % 2 == 1:
                current_title = chunk.strip().title()
            else:
                if chunk.strip():
                    chapters_to_create.append({"title": current_title, "text": chunk})
                    
    parsed_chapters = []
    for chap_data in chapters_to_create:
        sentences = nltk.tokenize.sent_tokenize(chap_data["text"])
        if not sentences:
            continue
        parsed_chapters.append({
            "title": chap_data["title"],
            "sentences": [s.strip() for s in sentences]
        })
        
    return parsed_chapters

async def process_pdf_upload(file: UploadFile, user_id: int, db: AsyncSession) -> Book:
    import tempfile
    import os
    
    # 1. Create book record
    book = Book(
        title=file.filename.replace(".pdf", ""),
        filename=file.filename,
        uploaded_by_id=user_id
    )
    db.add(book)
    await db.flush()

    # Save to temp file since pdfplumber needs a path or sync file object
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Run CPU-bound parsing in a background thread
        parsed_chapters = await asyncio.to_thread(_parse_pdf_to_chapters, tmp_path)
    finally:
        os.remove(tmp_path)
        
    chapter_number = 1
    for chap_data in parsed_chapters:
        chapter = Chapter(
            book_id=book.id,
            chapter_number=chapter_number,
            title=chap_data["title"],
            total_sentences=len(chap_data["sentences"])
        )
        db.add(chapter)
        await db.flush()
        
        for idx, sent_text in enumerate(chap_data["sentences"]):
            sentence = Sentence(
                chapter_id=chapter.id,
                sentence_index=idx,
                content=sent_text.strip()
            )
            db.add(sentence)
        
        chapter_number += 1
        
    book.total_chapters = chapter_number - 1
    
    # Create initial progress
    progress = UserBookProgress(
        user_id=user_id,
        book_id=book.id,
        current_chapter_id=None,
        current_sentence_index=0
    )
    db.add(progress)
    
    await db.commit()
    await db.refresh(book)
    return book
