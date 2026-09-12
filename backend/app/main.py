from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.db.bootstrap import ensure_sqlite_seed
from app.db.database import init_db, reset_engine

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-Grade AI Test Generator API",
    redirect_slashes=False,
)

# Set all CORS enabled origins
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=(
            r"https://(.*\.)?negraphics\.in|https://.*\.vercel\.app"
            r"|http://localhost:\d+|http://127\.0\.0\.1:\d+"
            r"|http://192\.168\.\d{1,3}\.\d{1,3}:\d+|http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.on_event("startup")
async def startup_event():
    if ensure_sqlite_seed(settings.DATABASE_URL):
        await reset_engine()
    await init_db()

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


@app.get("/health/db")
async def health_db():
    from sqlalchemy.future import select

    from app.db.database import async_session
    from app.models.subject import Subject

    try:
        async with async_session() as db:
            n = len((await db.execute(select(Subject))).scalars().all())
        return {"status": "ok", "subjects": n}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}

app.include_router(api_router, prefix="/api")
