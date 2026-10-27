"""SQLAlchemy models for Soul Sanctuary."""
from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """Registered person (admin or regular user)."""
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin','user')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="user", server_default="user", index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Survey(Base):
    """A survey (questionnaire)."""
    __tablename__ = "surveys"
    __table_args__ = (CheckConstraint("status IN ('draft','active','completed')", name="ck_surveys_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    sections: Mapped[list["SurveySection"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", order_by="SurveySection.order")


class SurveySection(Base):
    """A titled group of questions within a survey."""
    __tablename__ = "survey_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    survey: Mapped[Survey] = relationship(back_populates="sections")
    questions: Mapped[list["SurveyQuestion"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="SurveyQuestion.order")


class SurveyQuestion(Base):
    """A single question."""
    __tablename__ = "survey_questions"
    __table_args__ = (
        CheckConstraint("type IN ('single_choice','multi_choice','rating','text','number','dropdown')",
                        name="ck_questions_type"),
        Index("ix_questions_survey_order", "survey_id", "order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("survey_sections.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped[SurveySection] = relationship(back_populates="questions")
    options: Mapped[list["SurveyOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="SurveyOption.order")


class SurveyOption(Base):
    """An answer option of a choice/rating question."""
    __tablename__ = "survey_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("survey_questions.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(300))
    value: Mapped[int] = mapped_column(Integer)
    order: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[SurveyQuestion] = relationship(back_populates="options")


class SurveyResponse(Base):
    """One user's submission to a survey."""
    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("user_id", "survey_id", name="uq_response_user_survey"),
                      Index("ix_responses_survey_submitted", "survey_id", "submitted_at"))

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)


class SurveyAnswer(Base):
    """One answer (a multi-choice answer produces several rows)."""
    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("survey_responses.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("survey_questions.id", ondelete="CASCADE"), index=True)
    option_id: Mapped[int | None] = mapped_column(ForeignKey("survey_options.id", ondelete="SET NULL"), nullable=True, index=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    number_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class Project(Base):
    """A research project / dataset."""
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("status IN ('processed','active','pending_review')", name="ck_projects_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    entries_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    owner_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SocialStat(Base):
    """Latest social media numbers per platform, with '+' changes."""
    __tablename__ = "social_stats"
    __table_args__ = (CheckConstraint("platform IN ('instagram','facebook')", name="ck_social_platform"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(12), unique=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    followers: Mapped[int] = mapped_column(Integer, default=0)
    likes_delta: Mapped[int] = mapped_column(Integer, default=0)
    shares_delta: Mapped[int] = mapped_column(Integer, default=0)
    comments_delta: Mapped[int] = mapped_column(Integer, default=0)
    followers_delta: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SocialPost(Base):
    """A community feed post."""
    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped[User] = relationship()
