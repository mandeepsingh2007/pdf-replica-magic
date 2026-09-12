from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    document_id: int = Column(Integer, ForeignKey("documents.id"), nullable=False)
    content: str = Column(Text, nullable=False)
    chunk_index: int = Column(Integer, nullable=False)
    chunk_type: str | None = Column(String(50), nullable=True)
    page_number: int | None = Column(Integer, nullable=True)
    section_path: str | None = Column(String(500), nullable=True)
    embedding: str | None = Column(Text, nullable=True)
    token_count: int | None = Column(Integer, nullable=True)
    metadata_json: str | None = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
