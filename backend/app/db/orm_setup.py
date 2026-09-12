"""Import all models and configure mappers (required before any Subject query)."""

_configured = False


def ensure_orm_loaded() -> None:
    global _configured
    if _configured:
        return
    import app.models  # noqa: F401
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    _configured = True
