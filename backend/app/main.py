import json
import time

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.core.auth import require_roles
from app.core.config import settings
from app.database.db import Base, engine, get_db
from app.database.models import (
    AgentExecutionLog,
    AllocationResult,
    AllocationRun,
    AuditAttribute,
    Candidate,
    EligibilityResult,
    FairnessReport,
    Internship,
    MatchingScore,
    RagDocumentChunk,
    UploadedDocument,
)
from app.schemas import (
    AgentRequest,
    AllocationRequest,
    CandidateIn,
    DatasetUploadRequest,
    EligibilityRequest,
    GenerateRequest,
    InternshipIn,
    MatchingRequest,
    RagQueryRequest,
)
from app.services.allocation import allocate
from app.services.extraction import extract_resume
from app.services.fairness import fairness_report
from app.services.file_processing import (
    UploadValidationError,
    extract_text,
    parse_csv,
    validate_upload,
)
from app.services.llm import ProviderUnavailable, get_provider
from app.services.matching import eligibility, score
from app.services.rag import Retriever
from app.services.reports import allocation_csv, fairness_csv, simple_pdf
from app.services.synthetic_data import generate_dataset

Base.metadata.create_all(bind=engine)
app = FastAPI(title="AllocateAI API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])


async def _read_limited(file: UploadFile) -> bytes:
    content = bytearray()
    while True:
        chunk = await file.read(min(64 * 1024, settings.upload_max_bytes + 1 - len(content)))
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.upload_max_bytes:
            raise HTTPException(413, "File exceeds the configured size limit")
    return bytes(content)


def candidate_dict(row):
    return {key: getattr(row, key) for key in ["candidate_id", "name", "education", "specialization", "cgpa", "technical_skills", "soft_skills", "experience_months", "preferred_domains", "preferred_locations", "preferred_stipend", "preferred_duration", "preference_rank"]}


def internship_dict(row):
    return {key: getattr(row, key) for key in ["internship_id", "company_name", "role", "domain", "required_skills", "preferred_skills", "minimum_cgpa", "required_education", "minimum_experience", "location", "stipend", "duration", "available_seats", "mandatory_requirements"]}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AllocateAI"}


@app.get("/api/candidates")
def list_candidates(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return [candidate_dict(row) for row in db.scalars(select(Candidate)).all()]


@app.post("/api/candidates", status_code=201)
def create_candidate(payload: CandidateIn, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    if db.scalar(select(Candidate).where(Candidate.candidate_id == payload.candidate_id)):
        raise HTTPException(409, "Candidate ID already exists")
    row = Candidate(**payload.model_dump()); db.add(row); db.commit(); return candidate_dict(row)


@app.put("/api/candidates/{candidate_id}")
def update_candidate(candidate_id: str, payload: CandidateIn, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    row = db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id))
    if not row:
        raise HTTPException(404, "Candidate not found")
    if payload.candidate_id != candidate_id and db.scalar(select(Candidate).where(Candidate.candidate_id == payload.candidate_id)):
        raise HTTPException(409, "Candidate ID already exists")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return candidate_dict(row)


@app.delete("/api/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: str, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    row = db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id))
    if not row:
        raise HTTPException(404, "Candidate not found")
    db.delete(row); db.commit()


@app.get("/api/internships")
def list_internships(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return [internship_dict(row) for row in db.scalars(select(Internship)).all()]


@app.post("/api/internships", status_code=201)
def create_internship(payload: InternshipIn, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    if db.scalar(select(Internship).where(Internship.internship_id == payload.internship_id)):
        raise HTTPException(409, "Internship ID already exists")
    row = Internship(**payload.model_dump()); db.add(row); db.commit(); return internship_dict(row)


@app.put("/api/internships/{internship_id}")
def update_internship(internship_id: str, payload: InternshipIn, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    row = db.scalar(select(Internship).where(Internship.internship_id == internship_id))
    if not row:
        raise HTTPException(404, "Internship not found")
    if payload.internship_id != internship_id and db.scalar(select(Internship).where(Internship.internship_id == payload.internship_id)):
        raise HTTPException(409, "Internship ID already exists")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return internship_dict(row)


@app.delete("/api/internships/{internship_id}", status_code=204)
def delete_internship(internship_id: str, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    row = db.scalar(select(Internship).where(Internship.internship_id == internship_id))
    if not row:
        raise HTTPException(404, "Internship not found")
    db.delete(row); db.commit()


@app.post("/api/dataset/generate")
def generate(payload: GenerateRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    candidates, internships, audit = generate_dataset(payload.candidates, payload.internships, payload.seed)
    db.query(AllocationResult).delete(); db.query(EligibilityResult).delete(); db.query(MatchingScore).delete(); db.query(AuditAttribute).delete(); db.query(Candidate).delete(); db.query(Internship).delete()
    db.add_all([Candidate(**row) for row in candidates]); db.add_all([Internship(**row) for row in internships]); db.add_all([AuditAttribute(**row) for row in audit]); db.commit()
    return {"candidates": len(candidates), "internships": len(internships), "seed": payload.seed}


@app.post("/api/dataset/upload")
def upload_dataset(payload: DatasetUploadRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    if not payload.candidates and not payload.internships:
        raise HTTPException(422, "At least one candidate or internship is required")
    if payload.audit_attributes and _role not in {"development", "admin"}:
        raise HTTPException(403, "Only administrators may upload protected audit attributes")
    for candidate in payload.candidates:
        if db.scalar(select(Candidate).where(Candidate.candidate_id == candidate.candidate_id)):
            raise HTTPException(409, f"Candidate ID already exists: {candidate.candidate_id}")
    for internship in payload.internships:
        if db.scalar(select(Internship).where(Internship.internship_id == internship.internship_id)):
            raise HTTPException(409, f"Internship ID already exists: {internship.internship_id}")
    db.add_all([Candidate(**row.model_dump()) for row in payload.candidates])
    db.add_all([Internship(**row.model_dump()) for row in payload.internships])
    db.add_all([AuditAttribute(**row) for row in payload.audit_attributes if row.get("candidate_id") and row.get("group_name")])
    db.commit()
    return {"candidates": len(payload.candidates), "internships": len(payload.internships)}


@app.post("/api/dataset/upload-csv")
async def upload_dataset_csv(file: UploadFile = File(...), db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    content = await _read_limited(file)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Only CSV files are supported")
    try:
        rows = parse_csv(content, {"candidate_id", "name", "education", "specialization", "cgpa"}, settings.upload_max_csv_rows)
        candidates = []
        for row in rows:
            values = dict(row)
            for key in ("technical_skills", "soft_skills", "preferred_domains", "preferred_locations", "preference_rank"):
                values[key] = json.loads(values.get(key, "[]") or "[]")
            for key in ("cgpa",):
                values[key] = float(values[key])
            for key, default in (("experience_months", 0), ("preferred_stipend", 0), ("preferred_duration", 3)):
                values[key] = int(values.get(key, default) or default)
            candidates.append(CandidateIn(**values))
    except (UploadValidationError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if any(db.scalar(select(Candidate).where(Candidate.candidate_id == row.candidate_id)) for row in candidates):
        raise HTTPException(409, "A candidate ID already exists")
    db.add_all([Candidate(**row.model_dump()) for row in candidates]); db.commit()
    return {"candidates": len(candidates), "internships": 0}


@app.get("/api/dataset/summary")
def dataset_summary(db: Session = Depends(get_db)):
    return dashboard(db)


def _load_pairs(db: Session, request: EligibilityRequest | None = None):
    candidates = [candidate_dict(row) for row in db.scalars(select(Candidate)).all()]
    internships = [internship_dict(row) for row in db.scalars(select(Internship)).all()]
    if request and request.candidate_id:
        candidates = [row for row in candidates if row["candidate_id"] == request.candidate_id]
    if request and request.internship_id:
        internships = [row for row in internships if row["internship_id"] == request.internship_id]
    return candidates, internships


@app.post("/api/eligibility/check")
def check_eligibility(payload: EligibilityRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    candidates, internships = _load_pairs(db, payload)
    results = []
    for candidate in candidates:
        for internship in internships:
            result = eligibility(candidate, internship)
            row = EligibilityResult(candidate_id=candidate["candidate_id"], internship_id=internship["internship_id"], eligible=result["eligible"], reasons=result["reasons"], review_flags=result["review"])
            db.add(row)
            results.append({"candidate_id": candidate["candidate_id"], "internship_id": internship["internship_id"], **result})
    db.commit()
    return {"count": len(results), "results": results}


@app.get("/api/eligibility/results")
def eligibility_results(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return [{"candidate_id": row.candidate_id, "internship_id": row.internship_id, "eligible": row.eligible, "reasons": row.reasons, "review_flags": row.review_flags} for row in db.scalars(select(EligibilityResult).order_by(EligibilityResult.id.desc())).all()]


@app.post("/api/matching/run")
def run_matching(payload: MatchingRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    if abs(sum(payload.weights.values()) - 1) > 0.001:
        raise HTTPException(422, "Scoring weights must sum to 1")
    candidates, internships = _load_pairs(db)
    scores = []
    for candidate in candidates:
        for internship in internships:
            result = eligibility(candidate, internship)
            if result["eligible"]:
                value, components = score(candidate, internship, payload.weights)
                db.add(MatchingScore(candidate_id=candidate["candidate_id"], internship_id=internship["internship_id"], score=value, components=components))
                scores.append({"candidate_id": candidate["candidate_id"], "internship_id": internship["internship_id"], "score": value, "components": components})
    db.commit()
    return {"count": len(scores), "scores": scores}


@app.get("/api/matching/scores")
def matching_scores(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return [{"candidate_id": row.candidate_id, "internship_id": row.internship_id, "score": row.score, "components": row.components} for row in db.scalars(select(MatchingScore).order_by(MatchingScore.score.desc())).all()]


@app.post("/api/allocation/run")
def run_allocation(payload: AllocationRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    weight_sum = sum(payload.weights.values())
    if abs(weight_sum - 1) > 0.001:
        raise HTTPException(422, "Scoring weights must sum to 1")
    candidates = [candidate_dict(row) for row in db.scalars(select(Candidate)).all()]
    internships = [internship_dict(row) for row in db.scalars(select(Internship)).all()]
    weights = payload.weights
    result = allocate(candidates, internships, weights, settings.solver_timeout_seconds)
    run = AllocationRun(status=result["status"], objective_value=result["objective_value"], runtime_ms=result["runtime_ms"], allocated_count=len(result["allocations"])); db.add(run); db.flush()
    db.add_all([AllocationResult(run_id=run.id, candidate_id=row["candidate_id"], internship_id=row["internship_id"], score=row["score"], explanation=row) for row in result["allocations"]])
    db.commit()
    return {"run_id": run.id, **result}


@app.get("/api/allocation/results")
def allocation_results(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    latest_run = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
    if latest_run is None:
        return []
    rows = db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest_run.id).order_by(AllocationResult.id.desc())).all()
    return [{"candidate_id": row.candidate_id, "internship_id": row.internship_id, "score": row.score, "explanation": row.explanation} for row in rows]


@app.get("/api/allocation/history")
def allocation_history(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return [{"run_id": row.id, "status": row.status, "objective_value": row.objective_value, "runtime_ms": row.runtime_ms, "allocated_count": row.allocated_count, "created_at": row.created_at.isoformat()} for row in db.scalars(select(AllocationRun).order_by(AllocationRun.id.desc())).all()]


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    candidates = db.scalar(select(func.count(Candidate.id))) or 0
    internships = db.scalar(select(func.count(Internship.id))) or 0
    seats = db.scalar(select(func.sum(Internship.available_seats))) or 0
    latest_run = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
    results = db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest_run.id)).all() if latest_run else []
    return {"candidates": candidates, "internships": internships, "seats": seats, "allocated": len({row.candidate_id for row in results}), "allocation_rate": round(len({row.candidate_id for row in results}) / candidates * 100, 2) if candidates else 0, "average_score": round(sum(row.score for row in results) / len(results), 2) if results else 0}


@app.get("/api/fairness/report")
def fairness(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    audit = [{"candidate_id": row.candidate_id, "group_name": row.group_name} for row in db.scalars(select(AuditAttribute)).all()]
    candidates, internships = _load_pairs(db)
    eligible_ids = {
        candidate["candidate_id"]
        for candidate in candidates
        if any(eligibility(candidate, internship)["eligible"] for internship in internships)
    }
    latest = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
    allocations = [{"candidate_id": row.candidate_id} for row in db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest.id)).all()] if latest else []
    report = fairness_report(audit, allocations, eligible_ids)
    if latest:
        db.add(FairnessReport(run_id=latest.id, report=report)); db.commit()
    return report


@app.post("/api/fairness/evaluate")
def evaluate_fairness(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return fairness(db, _role)


@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    content = await _read_limited(file)
    try:
        suffix = validate_upload(file.filename, file.content_type, content, settings.upload_max_bytes)
        text = extract_text(content, suffix)
    except UploadValidationError as exc:
        code = 413 if "size limit" in str(exc) else 415
        raise HTTPException(code, str(exc)) from exc
    document = UploadedDocument(filename=file.filename or "resume", content_type=file.content_type or "", size_bytes=len(content), status="extracted", extracted_text=text)
    db.add(document); db.commit(); db.refresh(document)
    return {"document_id": document.id, "filename": document.filename, "status": document.status, "bytes": document.size_bytes, "extraction": _resume_extraction(text)}


def _resume_extraction(text: str):
    if settings.llm_provider == "disabled":
        return extract_resume(text).model_dump()
    try:
        from app.services.extraction import ResumeExtraction
        return get_provider(settings).extract(text, ResumeExtraction).model_dump()
    except ProviderUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/resumes/analyze")
def analyze_resume(document_id: int, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(404, "Resume document not found")
    extraction = _resume_extraction(document.extracted_text)
    return {"document_id": document.id, "status": "needs_review", "extraction": extraction, "source": "deterministic_text_extraction" if settings.llm_provider == "disabled" else settings.llm_provider}


@app.post("/api/rag/documents/upload")
async def upload_rag_document(file: UploadFile = File(...), db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    content = await _read_limited(file)
    try:
        suffix = validate_upload(file.filename, file.content_type, content, settings.upload_max_bytes)
        text = extract_text(content, suffix)
    except UploadValidationError as exc:
        raise HTTPException(415, str(exc)) from exc
    chunks = [text[index:index + 1200] for index in range(0, len(text), 1200)] or [""]
    db.add_all([RagDocumentChunk(document_name=file.filename or "document", chunk_text=chunk) for chunk in chunks])
    db.commit()
    return {"document_name": file.filename or "document", "chunks": len(chunks)}


@app.post("/api/rag/index")
def index_rag(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    return {"status": "ready", "chunks": db.scalar(select(func.count(RagDocumentChunk.id))) or 0, "provider": settings.llm_provider}


@app.post("/api/rag/query")
def query_rag(payload: RagQueryRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    documents = db.scalars(select(RagDocumentChunk)).all()
    results = Retriever([(row.chunk_text, {"document_name": row.document_name}) for row in documents]).search(payload.question)
    sources = [{"document_name": result.metadata.get("document_name", ""), "passage": result.text, "score": result.score} for result in results]
    return {"answer": "No grounded answer was found in the indexed documents." if not sources else "Relevant policy passages were retrieved. Review the cited sources before acting.", "sources": sources, "grounded": bool(sources)}


def _agent_result(agent: str, task: str, db: Session):
    def eligibility_tool(_task: str):
        candidates, internships = _load_pairs(db)
        total, accepted, reasons = 0, 0, {}
        for candidate in candidates:
            for internship in internships:
                decision = eligibility(candidate, internship)
                total += 1
                accepted += int(decision["eligible"])
                for reason in decision["reasons"]:
                    reasons[reason] = reasons.get(reason, 0) + 1
        return {"pairs_checked": total, "eligible_pairs": accepted, "ineligible_pairs": total - accepted, "failure_reasons": reasons}

    def matching_tool(_task: str):
        candidates, internships = _load_pairs(db)
        top = []
        for candidate in candidates:
            for internship in internships:
                if eligibility(candidate, internship)["eligible"]:
                    value, components = score(candidate, internship)
                    top.append({"candidate_id": candidate["candidate_id"], "internship_id": internship["internship_id"], "score": value, "components": components})
        top.sort(key=lambda row: (-row["score"], row["candidate_id"], row["internship_id"]))
        return {"eligible_pairs_scored": len(top), "top_matches": top[:10]}

    def allocation_tool(_task: str):
        latest = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
        if latest is None:
            return {"status": "no_run", "message": "Run the allocation endpoint to create authoritative solver results."}
        records = db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest.id)).all()
        return {"run_id": latest.id, "status": latest.status, "objective_value": latest.objective_value, "runtime_ms": latest.runtime_ms, "allocations": [{"candidate_id": row.candidate_id, "internship_id": row.internship_id, "score": row.score} for row in records]}

    def fairness_tool(_task: str):
        audit = [{"candidate_id": row.candidate_id, "group_name": row.group_name} for row in db.scalars(select(AuditAttribute)).all()]
        candidates, internships = _load_pairs(db)
        eligible_ids = {
            candidate["candidate_id"]
            for candidate in candidates
            if any(eligibility(candidate, internship)["eligible"] for internship in internships)
        }
        latest = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
        records = db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest.id)).all() if latest else []
        return fairness_report(audit, [{"candidate_id": row.candidate_id} for row in records], eligible_ids)

    def rag_tool(question: str):
        documents = db.scalars(select(RagDocumentChunk)).all()
        hits = Retriever([(row.chunk_text, {"document_name": row.document_name}) for row in documents]).search(question)
        return {"grounded": bool(hits), "sources": [{"document_name": hit.metadata.get("document_name", ""), "passage": hit.text, "score": hit.score} for hit in hits]}

    def explanation_tool(_task: str):
        latest = db.scalar(select(AllocationRun).order_by(AllocationRun.id.desc()))
        if latest is None:
            return {"status": "no_run", "message": "There are no allocation decisions to explain."}
        records = db.scalars(select(AllocationResult).where(AllocationResult.run_id == latest.id)).all()
        return {"run_id": latest.id, "explanations": [{"candidate_id": row.candidate_id, "internship_id": row.internship_id, "score": row.score, "evidence": row.explanation} for row in records]}

    def resume_tool(_task: str):
        document = db.scalar(select(UploadedDocument).order_by(UploadedDocument.id.desc()))
        if document is None:
            return {"status": "needs_input", "message": "Upload a resume before requesting analysis."}
        return {"document_id": document.id, "extraction": _resume_extraction(document.extracted_text), "status": "needs_review"}

    def internship_tool(_task: str):
        internships = [internship_dict(row) for row in db.scalars(select(Internship)).all()]
        return {"count": len(internships), "internships": internships[:25]}

    tools = {
        "eligibility": eligibility_tool,
        "matching": matching_tool,
        "allocation": allocation_tool,
        "fairness": fairness_tool,
        "rag": rag_tool,
        "explanation": explanation_tool,
        "resume_analysis": resume_tool,
        "internship_lookup": internship_tool,
    }
    started = time.perf_counter()
    status = "completed"
    try:
        if agent == "orchestrator":
            result = {
                "plan": ["inspect the relevant persisted evidence", "call deterministic read-only tools", "return validated results with their source"],
                "evidence": {
                    "eligibility": eligibility_tool(task),
                    "latest_allocation": allocation_tool(task),
                    "fairness": fairness_tool(task),
                },
                "authority": "Allocation decisions are produced only by the deterministic optimizer endpoint.",
            }
        else:
            tool_name = {"resume": "resume_analysis", "internship": "internship_lookup"}.get(agent, agent)
            result = AgentOrchestrator(tools).execute(agent, tool_name, task)
    except (PermissionError, LookupError) as exc:
        status = "failed"
        result = {"error": str(exc)}
        db.add(AgentExecutionLog(agent_name=agent, task="[redacted]", status=status, result={}, error=str(exc), runtime_ms=(time.perf_counter() - started) * 1000))
        db.commit()
        raise HTTPException(403 if isinstance(exc, PermissionError) else 400, str(exc)) from exc
    db.add(
        AgentExecutionLog(
            agent_name=agent,
            task="[redacted]",
            status=status,
            result={"result_type": "evidence_bundle", "task_length": len(task)},
            runtime_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    )
    db.commit()
    return result


@app.post("/api/agents/execute")
def execute_agent(payload: AgentRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    return {"agent": payload.agent, "result": _agent_result(payload.agent, payload.task, db), "provider": settings.llm_provider}


@app.post("/api/agents/chat")
def agent_chat(payload: AgentRequest, db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager"))):
    return {"agent": payload.agent, "result": _agent_result(payload.agent, payload.task, db), "provider": settings.llm_provider}


@app.get("/api/agents/status")
def agent_status():
    return {"provider": settings.llm_provider, "enabled": settings.llm_provider != "disabled", "agents": ["orchestrator", "resume", "internship", "eligibility", "matching", "allocation", "fairness", "explanation", "rag"]}


@app.get("/api/llm/status")
def llm_status():
    return {"provider": settings.llm_provider, "model": settings.llm_model if settings.llm_provider != "disabled" else None, "enabled": settings.llm_provider != "disabled", "timeout_seconds": settings.llm_timeout_seconds}


@app.get("/api/agents/logs")
def agent_logs(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "auditor"))):
    return [{"id": row.id, "agent": row.agent_name, "task": row.task, "status": row.status, "result": row.result, "created_at": row.created_at.isoformat()} for row in db.scalars(select(AgentExecutionLog).order_by(AgentExecutionLog.id.desc())).all()]


@app.get("/api/reports/allocation")
def allocation_report(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return {"dashboard": dashboard(db), "history": allocation_history(db), "results": allocation_results(db)}


@app.get("/api/reports/fairness")
def fairness_report_endpoint(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return fairness(db, _role)


@app.get("/api/reports/performance")
def performance_report(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "auditor"))):
    return {"allocation_runs": db.scalar(select(func.count(AllocationRun.id))) or 0, "agent_executions": db.scalar(select(func.count(AgentExecutionLog.id))) or 0, "llm_provider": settings.llm_provider}


@app.get("/api/reports/allocation.csv")
def allocation_report_csv(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    rows = allocation_results(db)
    return Response(
        allocation_csv([{"candidate_id": row["candidate_id"], "internship_id": row["internship_id"], "score": row["score"], "explanation": json.dumps(row["explanation"], ensure_ascii=True)} for row in rows]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="allocateai-allocation.csv"'},
    )


@app.get("/api/reports/allocation.pdf")
def allocation_report_pdf(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    rows = allocation_results(db)
    lines = ["AllocateAI Allocation Report", f"Assignments: {len(rows)}"]
    lines.extend(f"{row['candidate_id']} -> {row['internship_id']} | Score: {row['score']:.2f}" for row in rows)
    return Response(simple_pdf(lines), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="allocateai-allocation.pdf"'})


@app.get("/api/reports/fairness.csv")
def fairness_report_csv(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    return Response(fairness_csv(fairness(db, _role)), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="allocateai-fairness.csv"'})


@app.get("/api/reports/fairness.pdf")
def fairness_report_pdf(db: Session = Depends(get_db), _role: str = Depends(require_roles("admin", "placement_manager", "auditor"))):
    report = fairness(db, _role)
    lines = ["AllocateAI Fairness Report", f"Reference group: {report.get('reference_group')}", f"Demographic parity difference: {report.get('demographic_parity_difference')}", f"Disparate impact ratio: {report.get('disparate_impact_ratio')}"]
    lines.extend(f"{group}: selection rate {rate:.4f}" for group, rate in sorted(report.get("selection_rates", {}).items()))
    lines.append("Metrics are audit signals and do not establish legal compliance or prove fairness.")
    return Response(simple_pdf(lines), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="allocateai-fairness.pdf"'})


@app.get("/api/auth/status")
def auth_status():
    return {"enabled": settings.auth_enabled, "configured_roles": [role for role, token in (("admin", settings.admin_api_token), ("placement_manager", settings.placement_api_token), ("auditor", settings.auditor_api_token)) if token]}
