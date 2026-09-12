from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SubjectResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class ChapterResponse(BaseModel):
    id: str
    number: int
    title: str
    start_page: int
    end_page: Optional[int] = None

class DocumentUploadResponse(BaseModel):
    document_id: int
    task_id: str
    filename: str
    status: str
    message: str

    model_config = {"from_attributes": True}

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    current_step: Optional[str] = None
    result_id: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}

class QuestionResponse(BaseModel):
    id: int
    question_type: str
    question_data: dict
    mark_value: int
    difficulty: str
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}

class GeneratedTestResponse(BaseModel):
    id: int
    title: str
    subject_name: str
    total_marks: int
    total_questions: int
    test_data: dict
    created_at: datetime
    status: str

    model_config = {"from_attributes": True}

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class TestAttemptResponse(BaseModel):
    id: int
    title: str
    subject_name: str
    document_id: Optional[int] = None
    total_marks: int
    total_questions: int
    test_data: dict


class QuestionGradeResult(BaseModel):
    question_id: int
    section: str
    type: str
    marks_awarded: int
    max_marks: int
    is_correct: bool
    user_answer: Any = None
    correct_answer: str
    correction: str = ""
    pdf_excerpt: str = ""
    pdf_page_number: Optional[int] = None


class GradeResultResponse(BaseModel):
    total_score: int
    max_score: int
    percentage: float
    results: List[QuestionGradeResult]
