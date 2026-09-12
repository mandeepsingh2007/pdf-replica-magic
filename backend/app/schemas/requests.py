from pydantic import BaseModel, Field
from typing import Optional, List, Any

class GenerateTestRequest(BaseModel):
    subject_id: int
    document_id: Optional[int] = None
    total_marks: int = Field(default=50, ge=10, le=100)
    difficulty: str = Field(default="mixed")
    include_types: Optional[List[str]] = Field(
        default=None,
        description="Question types: mcq, assertion_reason, true_false, fill_blank, word_match, picture_match",
    )
    chapter_ids: Optional[List[str]] = Field(
        default=None,
        description="Selected chapter IDs from the textbook TOC",
    )
    questions_per_type: int = Field(
        default=5,
        ge=1,
        le=5,
        description="Exact number of questions to include per selected format (max 5)",
    )


class SubmitTestRequest(BaseModel):
    answers: dict[str, Any] = Field(
        description="Map of question_id (string) to user answer (str, bool, etc.)"
    )
