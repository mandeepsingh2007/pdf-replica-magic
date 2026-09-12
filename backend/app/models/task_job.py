from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.database import Base


class TaskJob(Base):
    __tablename__ = "task_jobs"

    id: str = Column(String(36), primary_key=True)
    job_type: str = Column(String(50), nullable=False)
    status: str = Column(String(50), default="pending")
    progress: int = Column(Integer, default=0)
    current_step: str | None = Column(String(200), nullable=True)
    result_id: int | None = Column(Integer, nullable=True)
    error_message: str | None = Column(Text, nullable=True)
    metadata_json: str | None = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<TaskJob(id='{self.id}', type='{self.job_type}', status='{self.status}', progress={self.progress}%)>"
