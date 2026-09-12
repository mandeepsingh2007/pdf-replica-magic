from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class ExtractedImage(Base):
    __tablename__ = "extracted_images"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    document_id: int = Column(Integer, ForeignKey("documents.id"), nullable=False)
    image_path: str = Column(String(1000), nullable=False)
    page_number: int | None = Column(Integer, nullable=True)
    bbox_x: float | None = Column(Float, nullable=True)
    bbox_y: float | None = Column(Float, nullable=True)
    bbox_width: float | None = Column(Float, nullable=True)
    bbox_height: float | None = Column(Float, nullable=True)
    vlm_description: str | None = Column(Text, nullable=True)
    caption: str | None = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="images")

    def __repr__(self) -> str:
        return f"<ExtractedImage(id={self.id}, document_id={self.document_id}, page={self.page_number})>"
