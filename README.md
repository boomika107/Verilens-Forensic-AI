# VERILENS FORENSIC AI
**An AI-Powered Multimodal Forensic Evidence Analysis and Statement Verification System**
*Analyze Evidence. Reveal Connections. Support Justice.*

> **Read this first — honest status.** This v1 was authored in a sandbox with **no network access**, so FastAPI, SQLAlchemy, YOLO, Whisper and `npm install` could not be run there.
> - **Executed and passing (9/9):** the forensic engine unit tests (`backend/tests/test_engine.py`): claim extraction, comparison rules, timeline, SHA-256 integrity, retrieval.
> - **Executed manually:** PDF report generation (ReportLab) and OpenCV frame extraction on a synthetic video.
> - **Written but NOT executed:** the FastAPI app, database layer, API tests (`tests/test_api.py`), the React frontend (no `npm run build` yet), setup/start scripts, Docker files. Expect to fix small errors on first run. Run the commands below and report what fails.
> - **Not implemented in v1:** see *Known limitations*.

## Purpose
Helps investigators organise digital evidence (documents, CCTV, audio, statements), rebuild timelines, and flag **potential inconsistencies between a statement and independent records** with full source traceability. It **never** scores guilt, honesty or deception, never infers deception from faces/voice, and never identifies people.

## Quick start (Windows)
```
setup.bat        # checks Python 3.10+/Node 18+, creates .venv, installs deps, initialises DB
start.bat        # opens backend and frontend in separate terminals
```
- Frontend: http://localhost:5173 · Backend: http://localhost:8000 · API docs: http://localhost:8000/docs
- The **first registered user becomes administrator**; later registrations are investigators. Admins can change roles (`PUT /api/users/{id}/role`).
- Click **Cases → Load synthetic demo** for a labelled fictional case, then: Statements tab → add *"I was at home at 8:00 PM on 2024-03-05."* → Findings tab → *Compare* → Reports tab → *Generate*. Expected: **Potential inconsistency** (synthetic CCTV record at 20:05, railway station).

## Optional AI components (install separately; app degrades gracefully)
```
.venv\Scripts\pip install ultralytics        # YOLO detection (downloads yolov8n.pt; needs internet)
.venv\Scripts\pip install faster-whisper     # transcription incl. Tamil/English/Malayalam (downloads model)
```
Without them: video analysis extracts frames only (and says detection is unavailable); audio analysis returns a clear "not installed" error. Nothing is faked.
Scanned-PDF OCR needs Tesseract and is **not wired in v1** (the extractor warns when a page has no text layer).

## Database
SQLite by default. For PostgreSQL set `DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/verilens` in `backend/.env`. Tables are created at startup; **Alembic migrations are not yet generated** (dependency pinned; run `alembic init` and autogenerate before production).

## Tests
```
cd backend && ..\.venv\Scripts\python -m unittest tests.test_engine
cd backend && ..\.venv\Scripts\python -m pytest -q            # all tests incl. API (needs full requirements)
cd frontend && npm run build                                  # type-check + build
```

## Architecture
`backend/app/engine/` holds framework-free logic: `statements.py` (rule-based claim/date/time/location extraction), `comparison.py` (explainable matching), `timeline.py`, `integrity.py`, `extractors.py` (PDF/DOCX/TXT/CSV, OpenCV+YOLO, faster-whisper), `rag.py` (case-scoped TF-IDF retrieval with citations), `report.py` (PDF). `main.py` is the REST API; `security.py` JWT + bcrypt + RBAC + case-level access; every important action writes an audit row.

### Design decisions you should know
- **Comparison**: a claim with a time is matched against *independent* events (statement-derived events are excluded) within a window (default 30 min, same date if both known). Same place → *Consistent*; different place → *Potential inconsistency*; missing location → *Requires human review*; nothing nearby → *Insufficient evidence*; no claimed time → *Unverified*. Location matching is word-overlap, so it is crude ("home" vs "residence" would not match, producing false flags) — reviewers must confirm.
- **Video/audio timestamps** are file offsets. They become wall-clock times only if the investigator supplies the recording start; otherwise events stay in "no usable timestamp". Times are never invented.
- **Integrity**: SHA-256 recorded at upload; analysis is refused if the stored file no longer matches. A match does not prove authenticity.
- **Access**: investigators see only their cases (others return 404); reviewers read all cases and approve/reject findings and mark events reviewed; admins do everything.

## Known limitations (v1)
- **Assistant is retrieval-only (TF-IDF).** LLM adapters (OpenAI/Gemini), LangGraph multi-agent orchestration, FAISS/Chroma embeddings are **not implemented**; the UI states retrieval-only mode. The "agents" are the deterministic pipeline stages above, not an LLM agent graph.
- Analysis runs synchronously inside the request (long videos/audio will block; use a job queue next).
- No Alembic migrations, no OCR, no password reset/user-management UI, no predictive/RL/federated/GNN research modules, no SHAP model (no predictive model exists, so nothing to explain).
- Statement extraction is English-only and rule-based; transcripts in other languages can be stored and retrieved but claims are not extracted from them.
- Graph layout is a simple grid; frontend covers the core workflow, not all 15 navigation pages (audio/document/CCTV views are in the case's Evidence tab).
- Responsive layout, form validation and route flow are untested.

## Security notes
bcrypt hashing, JWT (set `SECRET_KEY`, otherwise a random key is used and logins reset on restart), extension + magic-byte + size checks, random stored filenames, original files never modified, no secrets in the frontend, CORS restricted. Tokens are kept in `localStorage` (XSS-sensitive); use httpOnly cookies for production. Do not upload sensitive real evidence to external AI services without authorisation.

## Legal disclaimer
This software is an AI-assisted analysis aid. It is not a determination of guilt, deception, identity or legal admissibility. All findings require independent verification by qualified human reviewers.
