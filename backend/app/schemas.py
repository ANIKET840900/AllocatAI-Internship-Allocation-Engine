from typing import Literal

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=40)
    name: str
    education: str
    specialization: str
    cgpa: float = Field(ge=0, le=10)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    experience_months: int = Field(default=0, ge=0)
    preferred_domains: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_stipend: int = Field(default=0, ge=0)
    preferred_duration: int = Field(default=3, ge=1)
    preference_rank: list[str] = Field(default_factory=list)


class InternshipIn(BaseModel):
    internship_id: str = Field(min_length=1, max_length=40)
    company_name: str
    role: str
    domain: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_cgpa: float = Field(default=0, ge=0, le=10)
    required_education: str = "Any"
    minimum_experience: int = Field(default=0, ge=0)
    location: str
    stipend: int = Field(default=0, ge=0)
    duration: int = Field(default=3, ge=1)
    available_seats: int = Field(default=1, ge=0)
    mandatory_requirements: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    candidates: int = Field(default=1000, ge=0, le=50000)
    internships: int = Field(default=100, ge=0, le=1000)
    seed: int = 42


class AllocationRequest(BaseModel):
    skill_weight: float = Field(default=0.35, ge=0)
    education_weight: float = Field(default=0.20, ge=0)
    preference_weight: float = Field(default=0.15, ge=0)
    location_weight: float = Field(default=0.15, ge=0)
    experience_weight: float = Field(default=0.10, ge=0)
    other_weight: float = Field(default=0.05, ge=0)

    @property
    def weights(self) -> dict[str, float]:
        return {
            "skill": self.skill_weight,
            "education": self.education_weight,
            "preference": self.preference_weight,
            "location": self.location_weight,
            "experience": self.experience_weight,
            "other": self.other_weight,
        }


class DatasetUploadRequest(BaseModel):
    candidates: list[CandidateIn] = Field(default_factory=list)
    internships: list[InternshipIn] = Field(default_factory=list)
    audit_attributes: list[dict] = Field(default_factory=list)


class EligibilityRequest(BaseModel):
    candidate_id: str | None = None
    internship_id: str | None = None


class MatchingRequest(AllocationRequest):
    pass


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AgentRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    agent: Literal["orchestrator", "resume", "internship", "eligibility", "matching", "allocation", "fairness", "explanation", "rag"] = "orchestrator"
