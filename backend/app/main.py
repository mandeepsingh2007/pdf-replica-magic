from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from app.core.config import settings
from app.db.orm_setup import ensure_orm_loaded

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
    force=True,
)
logging.getLogger("app").setLevel(logging.INFO)

ensure_orm_loaded()

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
    groq_on = "yes" if settings.GROQ_API_KEY else "NO"
    gemini_on = "yes" if settings.GEMINI_API_KEY else "NO"
    print(
        f"=== LLM provider={settings.LLM_PROVIDER} model={settings.LLM_MODEL} "
        f"groq_key={groq_on} gemini_key={gemini_on} ===",
        flush=True,
    )
    if ensure_sqlite_seed(settings.DATABASE_URL):
        await reset_engine()
        ensure_orm_loaded()
    await init_db()
    # Reload / crash leaves create_task jobs forever at mid-progress — clear them.
    try:
        from sqlalchemy import update
        from app.db.database import async_session
        from app.models.task_job import TaskJob

        async with async_session() as db:
            result = await db.execute(
                update(TaskJob)
                .where(TaskJob.status == "processing", TaskJob.job_type == "test_generation")
                .values(
                    status="failed",
                    progress=0,
                    current_step="Error: Server restarted during generation. Please try again.",
                    error_message="orphaned_on_startup",
                )
            )
            await db.commit()
            if result.rowcount:
                print(f"=== Cleared {result.rowcount} orphaned generation task(s) ===", flush=True)
    except Exception as exc:
        print(f"=== Orphan task cleanup skipped: {exc} ===", flush=True)

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
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "groq_key": bool(settings.GROQ_API_KEY),
        "gemini_key": bool(settings.GEMINI_API_KEY),
        "build": "local-groq-1",
    }


@app.get("/health/db")
async def health_db():
    from sqlalchemy.future import select

    from app.db.database import async_session
    from app.db.orm_setup import ensure_orm_loaded
    from app.models.subject import Subject

    ensure_orm_loaded()
    try:
        async with async_session() as db:
            n = len((await db.execute(select(Subject))).scalars().all())
        return {"status": "ok", "subjects": n}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}

app.include_router(api_router, prefix="/api")


@app.middleware("http")
async def log_api_hits(request: Request, call_next):
    path = request.url.path
    print(f">>> {request.method} {path}", flush=True)
    response = await call_next(request)
    print(f"<<< {request.method} {path} -> {response.status_code}", flush=True)
    return response
