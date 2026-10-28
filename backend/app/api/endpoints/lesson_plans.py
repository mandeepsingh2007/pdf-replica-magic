from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.lesson_plan_service import generate_lesson_plan

router = APIRouter()


class LessonPlanRequest(BaseModel):
    class_level: int = Field(ge=1, le=7)
    subject: str
    chapter_id: str = Field(min_length=1)


@router.post("/lesson-plans")
async def create_lesson_plan(body: LessonPlanRequest, db: AsyncSession = Depends(get_db)):
    try:
        document, filename = await generate_lesson_plan(
            db,
            class_level=body.class_level,
            subject_key=body.subject,
            chapter_id=body.chapter_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "lesson-plan.pdf"
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=document,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
