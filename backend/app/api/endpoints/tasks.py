from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.task_job import TaskJob
from app.schemas.responses import TaskStatusResponse

router = APIRouter()

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get the status of a background task."""
    result = await db.execute(select(TaskJob).where(TaskJob.id == task_id))
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.id,
        "status": task.status or "pending",
        "progress": task.progress or 0,
        "current_step": task.current_step,
        "result_id": task.result_id,
        "error_message": task.error_message
    }
