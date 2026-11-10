import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.orchestrator import AgentOrchestrator
from app.core import config
from app.core.auth import require_roles
from app.database.db import Base, get_db
from app.main import app
from app.services.llm import (
    DisabledProvider,
    GeminiProvider,
    OllamaProvider,
    ProviderUnavailable,
)
from app.services.reports import allocation_csv, fairness_csv, simple_pdf


def test_report_exports_are_valid_and_escape_spreadsheet_formulas():
    csv_bytes = allocation_csv(
        [{"candidate_id": "=1+1", "internship_id": "I1", "score": 99, "explanation": {"ok": True}}]
    )
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    assert b"'=1+1" in csv_bytes
    fairness = fairness_csv({"selection_rates": {"Group A": 0.5}, "reference_group": "Group A"})
    assert b"Group A" in fairness
    pdf = simple_pdf(["AllocateAI Report", "Selection rate: 50%"])
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.endswith(b"%%EOF\n")


def test_agent_tool_permissions_are_enforced():
    runner = AgentOrchestrator({"eligibility": lambda task: {"task": task}})
    assert runner.execute("eligibility", "eligibility", "check") == {"task": "check"}
    with pytest.raises(PermissionError):
        runner.execute("eligibility", "allocation", "run allocation")


def test_disabled_provider_fails_explicitly():
    with pytest.raises(ProviderUnavailable, match="disabled"):
        DisabledProvider().extract("resume text", object)


def test_ollama_provider_validates_structured_output_without_real_network(monkeypatch):
    from pydantic import BaseModel

    class Output(BaseModel):
        name: str

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"name":"Jane"}'}

    monkeypatch.setattr("app.services.llm.httpx.post", lambda *args, **kwargs: Response())
    value = OllamaProvider("http://localhost:11434", "test-model", 1).extract("Jane", Output)
    assert value.name == "Jane"


def test_gemini_provider_requires_api_key():
    from pydantic import BaseModel

    class Output(BaseModel):
        name: str = ""

    with pytest.raises(ProviderUnavailable, match="LLM_API_KEY"):
        GeminiProvider("", "test-model", 1).extract("Jane", Output)


def test_auth_requires_valid_role_token(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(config.settings, "auth_enabled", True)
    monkeypatch.setattr(config.settings, "admin_api_token", "admin-test-secret")
    authorize = require_roles("admin")
    with pytest.raises(Exception) as missing:
        authorize(credentials=None)
    assert getattr(missing.value, "status_code", None) == 401
    role = authorize(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="admin-test-secret")
    )
    assert role == "admin"


def test_auth_defaults_to_enabled_without_environment_override(monkeypatch):
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    assert config.Settings(_env_file=None).auth_enabled is True


@pytest.fixture
def api_client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_db():
        session = test_sessions()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


def test_api_allocation_and_report_downloads(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "auth_enabled", False)
    candidate = {
        "candidate_id": "C-API",
        "name": "Test Candidate",
        "education": "B.Tech",
        "specialization": "CS",
        "cgpa": 8.5,
        "technical_skills": ["Python"],
        "soft_skills": [],
        "experience_months": 6,
        "preferred_domains": ["AI"],
        "preferred_locations": ["Remote"],
        "preferred_stipend": 10000,
        "preferred_duration": 3,
        "preference_rank": [],
    }
    internship = {
        "internship_id": "I-API",
        "company_name": "Test Company",
        "role": "AI Intern",
        "domain": "AI",
        "required_skills": ["Python"],
        "preferred_skills": [],
        "minimum_cgpa": 6,
        "required_education": "Any",
        "minimum_experience": 0,
        "location": "Remote",
        "stipend": 10000,
        "duration": 3,
        "available_seats": 1,
        "mandatory_requirements": [],
    }
    assert api_client.post("/api/candidates", json=candidate).status_code == 201
    assert api_client.post("/api/internships", json=internship).status_code == 201
    allocation = api_client.post("/api/allocation/run", json={})
    assert allocation.status_code == 200
    assert allocation.json()["validation"] == {"unique_candidates": True, "capacity_ok": True}
    agent = api_client.post("/api/agents/execute", json={"agent": "allocation", "task": "show latest"})
    assert agent.status_code == 200
    assert agent.json()["result"]["status"] == "OPTIMAL"
    assert api_client.post("/api/agents/execute", json={"agent": "eligibility", "task": "run allocation"}).status_code == 200
    rag_upload = api_client.post(
        "/api/rag/documents/upload",
        files={"file": ("policy.txt", b"Internship eligibility requires Python skills.", "text/plain")},
    )
    assert rag_upload.status_code == 200
    rag_query = api_client.post("/api/rag/query", json={"question": "internship eligibility Python"})
    assert rag_query.status_code == 200
    assert rag_query.json()["grounded"] is True
    assert rag_query.json()["sources"][0]["document_name"] == "policy.txt"
    csv_response = api_client.get("/api/reports/allocation.csv")
    assert csv_response.status_code == 200
    assert b"C-API" in csv_response.content
    pdf_response = api_client.get("/api/reports/allocation.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-1.4")


def test_api_csv_import_and_resume_extraction(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "auth_enabled", False)
    csv_file = (
        "candidate_id,name,education,specialization,cgpa,technical_skills\n"
        'C-CSV,CSV Candidate,B.Tech,CS,8.2,"[""Python""]"\n'
    ).encode()
    imported = api_client.post(
        "/api/dataset/upload-csv",
        files={"file": ("candidates.csv", csv_file, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["candidates"] == 1
    resume = api_client.post(
        "/api/resumes/upload",
        files={"file": ("resume.txt", b"Jane Candidate\njane@example.com", "text/plain")},
    )
    assert resume.status_code == 200
    assert resume.json()["extraction"]["name"] == "Jane Candidate"


def test_protected_api_requires_role_and_audit_group_is_not_public(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "auth_enabled", True)
    monkeypatch.setattr(config.settings, "admin_api_token", "admin-test-secret")
    monkeypatch.setattr(config.settings, "auditor_api_token", "audit-test-secret")
    assert api_client.get("/api/candidates").status_code == 401
    assert api_client.get("/api/allocation/results").status_code == 401
    assert api_client.get("/api/candidates", headers={"Authorization": "Bearer audit-test-secret"}).status_code == 200
    assert api_client.post(
        "/api/dataset/generate",
        json={"candidates": 1, "internships": 1, "seed": 1},
        headers={"Authorization": "Bearer audit-test-secret"},
    ).status_code == 403


def test_protected_api_fails_closed_when_auth_has_no_role_tokens(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "auth_enabled", True)
    monkeypatch.setattr(config.settings, "admin_api_token", "")
    monkeypatch.setattr(config.settings, "placement_api_token", "")
    monkeypatch.setattr(config.settings, "auditor_api_token", "")
    assert api_client.get("/api/candidates").status_code == 503
