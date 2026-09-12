from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Question(Base):
    __tablename__ = "questions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    document_id: int | None = Column(Integer, ForeignKey("documents.id"), nullable=True)
    subject_id: int = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    question_type: str = Column(String(50), nullable=False)
    question_data: str = Column(Text, nullable=False)
    mark_value: int = Column(Integer, nullable=False)
    difficulty: str = Column(String(20), default="medium")
    quality_score: float | None = Column(Float, nullable=True)
    source_chunks: str | None = Column(Text, nullable=True)
    is_used: bool = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="questions")
    subject = relationship("Subject", back_populates="questions")

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type='{self.question_type}', difficulty='{self.difficulty}')>"
