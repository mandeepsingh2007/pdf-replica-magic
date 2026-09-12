from fastapi import APIRouter
from app.api.endpoints import subjects, documents, tests, tasks, websocket

api_router = APIRouter()

api_router.include_router(subjects.router, prefix="/subjects", tags=["Subjects"])
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(tests.router, tags=["Tests"])
api_router.include_router(tasks.router, tags=["Tasks"])
api_router.include_router(websocket.router, tags=["WebSockets"])
