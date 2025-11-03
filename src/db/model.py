from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

DATABASE_URL = "sqlite:///jobs_analyzer.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class JobAnalysis(Base):
    __tablename__ = "job_analysis"

    id = Column(Integer, primary_key=True, index=True)
    link = Column(String(2048), nullable=False, unique=True)
    title = Column(String(256), nullable=False)
    location = Column(String(256))
    company = Column(String(256))
    salary = Column(String(256))
    description = Column(Text)
    cover_letter = Column(Text)
    page_text = Column(Text)
    expired = Column(Boolean, nullable=False, default=False)
    has_error = Column(Boolean, nullable=False, default=False)
    is_processing = Column(Boolean, nullable=False, default=False)
    is_processed = Column(Boolean, nullable=False, default=False)
    notes = Column(Text)
    is_agent_processed = Column(Boolean, nullable=False, default=False)
    installation_id = Column(String(128), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApplicationQuestions(Base):
    __tablename__ = "application_questions"
    id = Column(Integer, primary_key=True, index=True)
    job_analysis_id = Column(Integer, ForeignKey("job_analysis.id"), nullable=False)
    question_html = Column(Text, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    answer_execution_code = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApplicationActions(Base):
    __tablename__ = "application_actions"
    id = Column(Integer, primary_key=True, index=True)
    job_analysis_id = Column(Integer, ForeignKey("job_analysis.id"), nullable=False)
    question_html = Column(Text, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text)
    action = Column(Text, nullable=False)
    query_selector = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JobGoogleSearchQuery(Base):
    __tablename__ = "job_google_search_queries"

    id = Column(Integer, primary_key=True, index=True)
    installation_id = Column(String(128), nullable=False)
    site = Column(String(32), nullable=False)  # e.g., "lever"
    role_focus = Column(String(256), nullable=False)
    filters = Column(JSON, nullable=False)
    query = Column(Text, nullable=False)
    google_search_url = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Base.metadata.create_all(bind=engine)
