from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(100), unique=True, nullable=False)
    display_name: str = Column(String(200), nullable=False)
    description: str | None = Column(Text, nullable=True)
    icon: str | None = Column(String(50), nullable=True)
    is_active: bool = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    documents = relationship("Document", back_populates="subject")
    questions = relationship("Question", back_populates="subject")
    generated_tests = relationship("GeneratedTest", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject(id={self.id}, name='{self.name}')>"
