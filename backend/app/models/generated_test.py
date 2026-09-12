from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class GeneratedTest(Base):
    __tablename__ = "generated_tests"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    subject_id: int = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    document_id: int | None = Column(Integer, ForeignKey("documents.id"), nullable=True)
    title: str | None = Column(String(500), nullable=True)
    total_marks: int = Column(Integer, nullable=False, default=50)
    total_questions: int | None = Column(Integer, nullable=True)
    test_data: str = Column(Text, nullable=False)
    question_ids: str | None = Column(Text, nullable=True)
    assembly_metadata: str | None = Column(Text, nullable=True)
    status: str = Column(String(50), default="generating")
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("Subject", back_populates="generated_tests")
    document = relationship("Document", back_populates="generated_tests")

    def __repr__(self) -> str:
        return f"<GeneratedTest(id={self.id}, title='{self.title}', status='{self.status}')>"
