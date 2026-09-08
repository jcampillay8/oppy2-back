# src/books/models.py
import uuid
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.database import BaseModel
from src.config import settings

class Book(BaseModel):
    __tablename__ = "books"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    total_chapters: Mapped[int] = mapped_column(default=0)
    
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"), nullable=True)

    chapters: Mapped[list["Chapter"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Chapter(BaseModel):
    __tablename__ = "chapters"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.books.id"))
    chapter_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    total_sentences: Mapped[int] = mapped_column(default=0)

    book: Mapped["Book"] = relationship(back_populates="chapters")
    sentences: Mapped[list["Sentence"]] = relationship(back_populates="chapter", cascade="all, delete-orphan", order_by="Sentence.sentence_index")


class Sentence(BaseModel):
    __tablename__ = "sentences"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.chapters.id"))
    sentence_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)

    chapter: Mapped["Chapter"] = relationship(back_populates="sentences")


class UserBookProgress(BaseModel):
    __tablename__ = "user_book_progress"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.books.id"))
    
    current_chapter_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.chapters.id"), nullable=True)
    current_sentence_index: Mapped[int] = mapped_column(default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)


class UserChapterProgress(BaseModel):
    __tablename__ = "user_chapter_progress"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    chapter_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.chapters.id"))
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    last_read_sentence_index: Mapped[int] = mapped_column(default=0)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)
