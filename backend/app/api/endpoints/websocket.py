import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.task_job import TaskJob

router = APIRouter()

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        while True:
            # Re-fetch the task from DB
            result = await db.execute(select(TaskJob).where(TaskJob.id == task_id))
            task = result.scalars().first()
            
            if not task:
                await websocket.send_json({"error": "Task not found"})
                break
                
            payload = {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
            }
            await websocket.send_json(payload)
            
            if task.status in ["completed", "failed"]:
                break
                
            await asyncio.sleep(1) # Poll every 1 second
            
    except WebSocketDisconnect:
        print(f"Client disconnected for task {task_id}")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass # Already closed
