from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Any

class GenerateTestRequest(BaseModel):
    subject_id: int
    document_id: Optional[int] = None
    total_marks: Literal[10, 20, 30, 50] = 50
    school_name: str = Field(min_length=1, max_length=120)

    @field_validator("school_name")
    @classmethod
    def clean_school_name(cls, value: str) -> str:
        text = " ".join(value.split())
        if not text:
            raise ValueError("Enter the school name.")
        return text[:120]
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
