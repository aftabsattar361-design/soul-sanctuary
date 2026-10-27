"""Pydantic v2 schemas."""
import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SurveyStatus = Literal["draft", "active", "completed"]
QuestionType = Literal["single_choice", "multi_choice", "rating", "text", "number", "dropdown"]
ProjectStatus = Literal["processed", "active", "pending_review"]


def _check_email(v: str) -> str:
    v = v.strip().lower()
    if not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str
    confirm_password: str
    date_of_birth: date | None = None
    age: int | None = Field(default=None, ge=18, le=110)
    gender: Literal["Male", "Female", "Other", "Prefer not to say"] | None = None
    city: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _check_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain an uppercase letter, a lowercase letter and a digit")
        if len(v.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        if v is not None and v >= date.today():
            raise ValueError("Date of birth must be in the past")
        if v is not None:
            today = date.today()
            if today.year - v.year - ((today.month, today.day) < (v.month, v.day)) < 18:
                raise ValueError("You must be at least 18 years old to register")
        return v

    @model_validator(mode="after")
    def _match(self) -> "RegisterIn":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if self.date_of_birth is None and self.age is None:
            raise ValueError("Provide date of birth or age")
        return self


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    age: int | None = None
    gender: str | None = None
    city: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- surveys ----------
class OptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    value: int
    order: int


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: int
    text: str
    help_text: str | None = None
    type: str
    required: bool
    order: int
    options: list[OptionOut] = []


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None = None
    order: int
    questions: list[QuestionOut] = []


class SurveyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    sections: list[SectionOut] = []


class SurveySummary(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    response_count: int = 0
    question_count: int = 0


class AnswerIn(BaseModel):
    question_id: int
    option_id: int | None = None
    option_ids: list[int] | None = None
    text_value: str | None = None
    number_value: float | None = None


class SubmitIn(BaseModel):
    survey_id: int
    answers: list[AnswerIn]


class SubmitOut(BaseModel):
    response_id: int
    submitted_at: datetime
    message: str = "Thank you! Your response has been recorded."


class MyResponseOut(BaseModel):
    submitted: bool
    response_id: int | None = None
    submitted_at: datetime | None = None


class QuestionCreate(BaseModel):
    text: str = Field(min_length=3)
    type: QuestionType = "single_choice"
    required: bool = True
    help_text: str | None = None
    options: list[str] = []


class SectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    questions: list[QuestionCreate] = Field(min_length=1)


class SurveyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    status: SurveyStatus = "draft"
    sections: list[SectionCreate] = []


# ---------- projects / social ----------
class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    entries_count: int
    last_updated: datetime
    owner_name: str
    status: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    entries_count: int = Field(ge=0, default=0)
    owner_name: str = Field(min_length=2, max_length=120)
    status: ProjectStatus = "active"


class ProjectList(BaseModel):
    items: list[ProjectOut]
    total: int
    total_entries: int


class SocialStatIn(BaseModel):
    platform: Literal["instagram", "facebook"]
    likes: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    followers: int | None = Field(default=None, ge=0)
    likes_delta: int | None = None
    shares_delta: int | None = None
    comments_delta: int | None = None
    followers_delta: int | None = None


class SocialStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform: str
    likes: int
    shares: int
    comments: int
    followers: int
    likes_delta: int
    shares_delta: int
    comments_delta: int
    followers_delta: int
    updated_at: datetime


class PostIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class PostOut(BaseModel):
    id: int
    author: str
    content: str
    created_at: datetime
