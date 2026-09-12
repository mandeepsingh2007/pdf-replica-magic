"""Import all models in dependency order and configure SQLAlchemy mappers."""

_configured = False


def ensure_orm_loaded() -> None:
    global _configured
    if _configured:
        return

    # Explicit imports (do not rely on app.models package re-exports on all hosts).
    from app.models.chunk import Chunk  # noqa: F401
    from app.models.extracted_image import ExtractedImage  # noqa: F401
    from app.models.generated_test import GeneratedTest  # noqa: F401
    from app.models.task_job import TaskJob  # noqa: F401
    from app.models.subject import Subject  # noqa: F401
    from app.models.document import Document  # noqa: F401
    from app.models.question import Question  # noqa: F401

    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    _configured = True
