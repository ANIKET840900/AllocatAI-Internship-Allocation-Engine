# AllocateAI — AI-Powered Fair Internship Allocation Engine

AllocateAI is a local, database-backed decision-support platform for explainable, capacity-constrained internship allocation. Deterministic eligibility, matching, CP-SAT optimization, and fairness calculations are authoritative; optional agents and RAG provide controlled advisory workflows and never override allocation rules.

## Run locally

Backend (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

API role-token authentication is enabled by default. Configure one or more role tokens before using protected endpoints. For an isolated local development environment only, set `AUTH_ENABLED=false` in `backend\.env`.

Frontend (a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Use **Generate data**, run eligibility/matching, then **Run allocation**. API documentation is available at `http://localhost:8000/docs`.

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

The allocation engine uses OR-Tools CP-SAT with binary candidate/internship variables, at-most-one candidate constraints, internship capacity constraints, mandatory eligibility filtering, deterministic synthetic data, and a weighted compatibility objective. Fairness metrics are evaluation signals over the protected audit table, never matching features.

## Implemented API areas

- Candidate and internship list/create/update/delete
- Reproducible dataset generation and JSON dataset upload
- Dataset summary, eligibility checks, and persisted matching scores
- CP-SAT allocation, post-solve validation, unmatched candidates, and run history
- Fairness reports and persisted run reports
- Resume/document size and type validation
- PDF/DOCX/TXT resume text extraction and structured extraction with review-required status
- CSV candidate upload with schema, row-count, and field validation
- RAG document upload, persisted chunks, lexical source retrieval, and optional FAISS/Sentence-Transformers retrieval
- Agent status, advisory execution, chat, and execution logs
- Allocation, fairness, and performance report endpoints
- CSV and PDF allocation/fairness report downloads
- Optional role-based bearer-token checks for administrative operations
- Ollama local and Gemini structured extraction provider interfaces

## Frontend workspace

The React workspace includes API-driven views for overview, candidate/internship create and delete, CSV dataset upload and generation, allocation configuration, fairness, agent tool execution, RAG document upload/query, authentication token entry, and report downloads. It includes loading, error, empty, filtering, responsive, and export/print states.

## Test and build

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

## Configuration

Copy `.env.example` to `.env` when needed. Set `DATABASE_URL`, comma-separated `CORS_ORIGINS`, `SOLVER_TIMEOUT_SECONDS`, `UPLOAD_MAX_BYTES`, and `LLM_PROVIDER`. By default the LLM provider is `disabled`; this keeps local operation independent of paid APIs.

Optional extraction providers:

- `LLM_PROVIDER=ollama`, plus `LLM_BASE_URL` and `LLM_MODEL`, for a locally running Ollama service.
- `LLM_PROVIDER=gemini`, plus `LLM_API_KEY` and `LLM_MODEL`, for optional Gemini API extraction.

Role-token authentication is enabled by default. Configure long random values for `ADMIN_API_TOKEN`, `PLACEMENT_API_TOKEN`, and/or `AUDITOR_API_TOKEN`; protected endpoints fail closed when authentication is enabled without configured tokens. The frontend Agents view accepts a bearer token and stores it in the current browser's local storage. Tokens are not issued by this application; provision them securely outside the application. For an isolated local development environment only, set `AUTH_ENABLED=false` explicitly. Do not expose this development token scheme directly to the public internet.

Database schema:

```powershell
cd backend
python -m alembic upgrade head
python -m alembic current
```

## Scope and limitations

The current implementation is a local development slice. Alembic is configured and the initial schema migration is tested on SQLite; production PostgreSQL migration validation is still required. Authentication is a simple optional role-token mechanism, not production identity management. Resume extraction is conservative and requires human review. FAISS/Sentence Transformer retrieval is optional; lexical source retrieval is the no-model fallback. Agent task endpoints use controlled advisory tools and do not constitute a complete autonomous LangChain/ReAct system. Background jobs, production monitoring, secure key rotation, and measured 1k/5k/10k benchmarks remain deployment work. Fairness metrics are audit signals and do not establish legal compliance.

## Code quality and security checks

Install the additional development analyzers once:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\bandit.exe -r app -ll
.\.venv\Scripts\pip-audit.exe

cd ..\frontend
npm install
npm run lint
npm audit
npm run build
```
