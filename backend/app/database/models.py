from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    education: Mapped[str] = mapped_column(String(80))
    specialization: Mapped[str] = mapped_column(String(80))
    cgpa: Mapped[float] = mapped_column(Float)
    technical_skills: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_months: Mapped[int] = mapped_column(Integer, default=0)
    preferred_domains: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    preferred_stipend: Mapped[int] = mapped_column(Integer, default=0)
    preferred_duration: Mapped[int] = mapped_column(Integer, default=3)
    preference_rank: Mapped[list] = mapped_column(JSON, default=list)


class Internship(Base):
    __tablename__ = "internships"
    id: Mapped[int] = mapped_column(primary_key=True)
    internship_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(80), index=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    minimum_cgpa: Mapped[float] = mapped_column(Float, default=0)
    required_education: Mapped[str] = mapped_column(String(80), default="Any")
    minimum_experience: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str] = mapped_column(String(80))
    stipend: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=3)
    available_seats: Mapped[int] = mapped_column(Integer, default=1)
    mandatory_requirements: Mapped[list] = mapped_column(JSON, default=list)


class AllocationRun(Base):
    __tablename__ = "allocation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(40))
    objective_value: Mapped[float] = mapped_column(Float, default=0)
    runtime_ms: Mapped[float] = mapped_column(Float, default=0)
    allocated_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AllocationResult(Base):
    __tablename__ = "allocation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("allocation_runs.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(40), index=True)
    internship_id: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSON)


class AuditAttribute(Base):
    __tablename__ = "audit_attributes"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    group_name: Mapped[str] = mapped_column(String(80))


class EligibilityResult(Base):
    __tablename__ = "eligibility_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(40), index=True)
    internship_id: Mapped[str] = mapped_column(String(40), index=True)
    eligible: Mapped[bool] = mapped_column(default=False)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    review_flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MatchingScore(Base):
    __tablename__ = "matching_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(40), index=True)
    internship_id: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FairnessReport(Base):
    __tablename__ = "fairness_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("allocation_runs.id"), nullable=True, index=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="stored")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_name: Mapped[str] = mapped_column(String(255), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(80), index=True)
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    runtime_ms: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
