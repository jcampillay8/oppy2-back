# src/books/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID

class SentenceBase(BaseModel):
    sentence_index: int
    content: str
    
class SentenceResponse(SentenceBase):
    id: int
    chapter_id: int
    
    model_config = ConfigDict(from_attributes=True)

class ChapterBase(BaseModel):
    chapter_number: int
    title: Optional[str] = None
    total_sentences: int

class ChapterResponse(ChapterBase):
    id: int
    book_id: int
    is_read: bool = False
    last_read_sentence_index: int = 0
    progress_percentage: float = 0.0
    
    model_config = ConfigDict(from_attributes=True)

class BookBase(BaseModel):
    title: str
    filename: str
    total_chapters: int

class BookResponse(BookBase):
    id: int
    guid: UUID
    uploaded_by_id: Optional[int] = None
    progress_percentage: float = 0.0
    is_completed: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class ProgressUpdateRequest(BaseModel):
    chapter_id: int
    current_sentence_index: int
