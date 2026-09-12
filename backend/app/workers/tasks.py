import asyncio

from app.services.pdf_ingestion import process_pdf_async
from app.workers.celery_app import celery_app


@celery_app.task(name="parse_pdf_task")
def parse_pdf_task(document_id: int, task_id: str):
    """
    Celery worker task that handles PDF processing in the background.
    Celery runs synchronous python code, so we use asyncio.run to execute the async pipeline.
    """
    asyncio.run(process_pdf_async(document_id, task_id))
