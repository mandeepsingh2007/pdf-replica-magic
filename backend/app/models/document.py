from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    subject_id: int = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    filename: str = Column(String(500), nullable=False)
    original_filename: str = Column(String(500), nullable=False)
    file_path: str = Column(String(1000), nullable=False)
    file_size_bytes: int | None = Column(BigInteger, nullable=True)
    total_pages: int | None = Column(Integer, nullable=True)
    status: str = Column(String(50), default="uploaded")
    error_message: str | None = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    subject = relationship("Subject", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    images = relationship("ExtractedImage", back_populates="document", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="document")
    generated_tests = relationship("GeneratedTest", back_populates="document")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"
