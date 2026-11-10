from pydantic import BaseModel, Field


class ResumeExtraction(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    education: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


def extract_resume(text: str) -> ResumeExtraction:
    """Conservative deterministic extraction used when no LLM is enabled."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = next((token for line in lines for token in line.split() if "@" in token and "." in token), "")
    return ResumeExtraction(name=lines[0] if lines else "", email=email)
