from pydantic import BaseModel, Field
from typing import List, Dict

class MCQSchema(BaseModel):
    question_text: str = Field(description="The multiple choice question text")
    correct_answer: str = Field(description="The correct answer option")
    distractors: List[str] = Field(description="Exactly 3 incorrect plausible distractors")

class TrueFalseSchema(BaseModel):
    statement: str = Field(description="The true or false statement")
    is_true: bool = Field(description="Boolean indicating if the statement is true")
    explanation: str = Field(description="A brief explanation of why the statement is true or false")

class FillInBlankSchema(BaseModel):
    sentence_with_blank: str = Field(description="A sentence with exactly one '_____' representing the blank")
    correct_word: str = Field(description="The word that fills the blank")

class ShortAnswerSchema(BaseModel):
    question: str = Field(description="A subjective question requiring a short answer")
    ideal_answer: str = Field(description="The ideal detailed answer for the question")
    grading_rubric: List[str] = Field(description="List of key points that must be present in a correct answer")

class WordMatchSchema(BaseModel):
    column_a: List[str] = Field(description="5 items for the left column")
    column_b: List[str] = Field(description="5 items for the right column")
    correct_mapping: Dict[str, str] = Field(description="Dictionary mapping item from column_a to column_b")

class PictureMatchSchema(BaseModel):
    picture_captions: List[str] = Field(
        description="Exactly 5 brief figure/diagram descriptions from the textbook"
    )
    labels: List[str] = Field(description="Exactly 5 text labels to match with the pictures")
    correct_mapping: Dict[str, str] = Field(
        description="Maps figure keys '1','2','3','4','5' to the exact matching label string"
    )

class PictureMatchSingleSchema(BaseModel):
    labels: List[str] = Field(
        description="Exactly 5 short textbook terms — labels[i] describes figure i+1 in order"
    )

class AssertionReasonSchema(BaseModel):
    assertion: str = Field(description="The primary factual assertion")
    reason: str = Field(description="The secondary factual reason")
    logical_analysis: str = Field(description="Chain of thought explaining the causal link before choosing the option")
    correct_option_code: str = Field(description="Must be exactly A, B, C, or D based on standard Assertion-Reason rules")

class MCQListSchema(BaseModel):
    questions: List[MCQSchema]

class TrueFalseListSchema(BaseModel):
    questions: List[TrueFalseSchema]

class FillInBlankListSchema(BaseModel):
    questions: List[FillInBlankSchema]

class ShortAnswerListSchema(BaseModel):
    questions: List[ShortAnswerSchema]

class WordMatchListSchema(BaseModel):
    questions: List[WordMatchSchema]

class PictureMatchListSchema(BaseModel):
    questions: List[PictureMatchSchema]

class OralSchema(BaseModel):
    question: str = Field(description="An oral question in Hindi to be asked aloud")
    ideal_answer: str = Field(description="The expected spoken/written answer in Hindi")


class WhoSaidSchema(BaseModel):
    quote: str = Field(description="The exact or closely paraphrased line from the lesson")
    speaker: str = Field(description="Who said the line")
    listener: str = Field(description="To whom it was said; use 'स्वगत' if spoken to oneself")
    explanation: str = Field(description="One-line context from the lesson")


class CreativeWorkSchema(BaseModel):
    prompt: str = Field(description="A creative writing/drawing task grounded in the lesson")
    ideal_answer: str = Field(description="A model response a Class teacher would accept")
    grading_rubric: List[str] = Field(description="Key points for awarding marks")


class OralListSchema(BaseModel):
    questions: List[OralSchema]


class WhoSaidListSchema(BaseModel):
    questions: List[WhoSaidSchema]


class CreativeWorkListSchema(BaseModel):
    questions: List[CreativeWorkSchema]


class AssertionReasonListSchema(BaseModel):
    questions: List[AssertionReasonSchema]
