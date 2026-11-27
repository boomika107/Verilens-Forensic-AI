import re, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import func
from . import config
from .models import Base, engine, User, Case, Evidence, Statement, Claim, Event, Finding, Report, AuditLog, Job, now
from .security import hash_pw, check_pw, make_token, get_db, current_user, require_roles, get_case, audit
from .engine import statements as S, comparison as C, timeline as T, integrity as I, extractors as X, rag as R, report as RP

app = FastAPI(title="VERILENS FORENSIC AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)  # NOTE: swap for Alembic migrations in production (see README)

EXT = {".mp4": "video", ".avi": "video", ".mov": "video", ".mkv": "video", ".wav": "audio", ".mp3": "audio", ".m4a": "audio",
       ".aac": "audio", ".pdf": "document", ".docx": "document", ".txt": "document", ".csv": "document",
       ".jpg": "image", ".jpeg": "image", ".png": "image"}
MAGIC = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8"], ".jpeg": [b"\xff\xd8"], ".docx": [b"PK"],
         ".wav": [b"RIFF"], ".mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"], ".mkv": [b"\x1aE\xdf\xa3"], ".avi": [b"RIFF"]}
INVESTIGATE = ("administrator", "investigator")


def d(o, *skip):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in skip}


# ---------- auth ----------
class Reg(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register")
def register(b: Reg, db=Depends(get_db)):
    if db.query(User).filter((User.username == b.username) | (User.email == b.email)).first():
        raise HTTPException(409, "Username or email already exists")
    first = db.query(User).count() == 0  # first account bootstraps as administrator; all others are investigators
    u = User(username=b.username, email=b.email, password_hash=hash_pw(b.password), role="administrator" if first else "investigator")
    db.add(u); db.commit()
    audit(db, u, "user.register")
    return {"token": make_token(u), "user": d(u, "password_hash")}


@app.post("/api/auth/login")
def login(b: Login, db=Depends(get_db)):
    u = db.query(User).filter(User.username == b.username).first()
    if not u or not u.active or not check_pw(b.password, u.password_hash):
        audit(db, None, "user.login_failed", detail=b.username[:64])
        raise HTTPException(401, "Invalid credentials")
    audit(db, u, "user.login")
    return {"token": make_token(u), "user": d(u, "password_hash")}


@app.get("/api/auth/me")
def me(u=Depends(current_user)):
    return d(u, "password_hash")


@app.get("/api/users")
def users(u=Depends(require_roles("administrator")), db=Depends(get_db)):
    return [d(x, "password_hash") for x in db.query(User).all()]


class RoleBody(BaseModel):
    role: str = Field(pattern="^(administrator|investigator|reviewer)$")


@app.put("/api/users/{uid}/role")
def set_role(uid: int, b: RoleBody, u=Depends(require_roles("administrator")), db=Depends(get_db)):
    t = db.get(User, uid)
    if not t:
        raise HTTPException(404)
    t.role = b.role; db.commit(); audit(db, u, "user.role_change", detail=f"{t.username}->{b.role}")
    return d(t, "password_hash")


# ---------- cases ----------
class CaseIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    category: str = "general"
    notes: str = ""


def next_case_id(db):
    n = db.query(func.max(Case.id)).scalar() or 0
    return f"VL-CASE-{n + 1:03d}"


@app.post("/api/cases")
def create_case(b: CaseIn, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = Case(case_id=next_case_id(db), owner_id=u.id, **b.model_dump())
    db.add(c); db.commit()
    audit(db, u, "case.create", c.id, c.case_id)
    return d(c)


@app.get("/api/cases")
def list_cases(q: str = "", status: str = "", u=Depends(current_user), db=Depends(get_db)):
    qs = db.query(Case)
    if u.role == "investigator":
        qs = qs.filter(Case.owner_id == u.id)
    if q:
        qs = qs.filter(Case.title.ilike(f"%{q}%") | Case.case_id.ilike(f"%{q}%"))
    if status:
        qs = qs.filter(Case.status == status)
    return [d(c) for c in qs.order_by(Case.id.desc()).all()]


@app.get("/api/cases/{cid}")
def read_case(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    return {**d(c), "counts": {"evidence": db.query(Evidence).filter_by(case_pk=c.id).count(),
                               "events": db.query(Event).filter_by(case_pk=c.id).count(),
                               "statements": db.query(Statement).filter_by(case_pk=c.id).count()}}


@app.put("/api/cases/{cid}")
def update_case(cid: str, b: CaseIn, status: str | None = None, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    for k, v in b.model_dump().items():
        setattr(c, k, v)
    if status in ("active", "closed", "archived"):
        c.status = status
    db.commit(); audit(db, u, "case.update", c.id)
    return d(c)


@app.delete("/api/cases/{cid}")
def archive_case(cid: str, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)  # archive, never hard-delete evidence
    c.status = "archived"; db.commit(); audit(db, u, "case.archive", c.id)
    return {"ok": True}


# ---------- evidence ----------
@app.post("/api/cases/{cid}/evidence")
async def upload(cid: str, file: UploadFile = File(...), start_date: str | None = Form(None), start_time: str | None = Form(None),
                 u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in EXT:
        raise HTTPException(415, f"File type {ext or '(none)'} not allowed")
    if start_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date) or start_time and not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", start_time):
        raise HTTPException(422, "start_date must be YYYY-MM-DD and start_time HH:MM[:SS]")
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = config.STORAGE / "evidence" / stored
    dest.parent.mkdir(parents=True, exist_ok=True)
    import hashlib
    h, size, head = hashlib.sha256(), 0, b""
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            if not head:
                head = chunk[:8]
            size += len(chunk)
            if size > limit:
                f.close(); dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds {config.MAX_UPLOAD_MB} MB")
            h.update(chunk); f.write(chunk)
    if size == 0 or (ext in MAGIC and not any(head.startswith(m) for m in MAGIC[ext])):
        dest.unlink(missing_ok=True)
        raise HTTPException(415, "File content does not match its extension (or file is empty)")
    ev = Evidence(case_pk=c.id, original_name=Path(file.filename).name[:255], stored_name=stored, kind=EXT[ext], size=size,
                  sha256=h.hexdigest(), start_date=start_date, start_time=start_time, uploaded_by=u.id)
    db.add(ev); db.commit()
    audit(db, u, "evidence.upload", c.id, f"{ev.original_name} sha256={ev.sha256}")
    return d(ev, "analysis")


@app.get("/api/cases/{cid}/evidence")
def list_evidence(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    return [d(e, "analysis") for e in db.query(Evidence).filter_by(case_pk=c.id).order_by(Evidence.id).all()]


def own_evidence(db, eid, u, write=False):
    e = db.get(Evidence, eid)
    if not e:
        raise HTTPException(404)
    c = db.get(Case, e.case_pk)
    get_case(db, c.case_id, u, write)
    return e, c


@app.get("/api/evidence/{eid}")
def evidence_detail(eid: int, u=Depends(current_user), db=Depends(get_db)):
    e, _ = own_evidence(db, eid, u)
    return d(e)


@app.get("/api/evidence/{eid}/file")
def evidence_file(eid: int, u=Depends(current_user), db=Depends(get_db)):
    e, c = own_evidence(db, eid, u)
    audit(db, u, "evidence.view", c.id, e.original_name)
    return FileResponse(config.STORAGE / "evidence" / e.stored_name, filename=e.original_name)


@app.post("/api/evidence/{eid}/verify")
def verify(eid: int, u=Depends(current_user), db=Depends(get_db)):
    e, c = own_evidence(db, eid, u)
    p = config.STORAGE / "evidence" / e.stored_name
    ok = p.exists() and I.verify(p, e.sha256)
    e.last_integrity = f"{'MATCH' if ok else 'MISMATCH/MISSING'} @ {now().isoformat(timespec='seconds')}"
    db.commit(); audit(db, u, "evidence.verify", c.id, f"{e.original_name}: {e.last_integrity}")
    return {"match": ok, "recorded_sha256": e.sha256, "note": "A match means the bytes equal the hash recorded at upload; it does not prove authenticity."}


def wall(ev, offset_s):
    """Wall-clock time only if the investigator supplied the recording start; otherwise None (never invented)."""
    if not ev.start_time:
        return ev.start_date, None
    hh, mm, *ss = map(int, ev.start_time.split(":"))
    tot = hh * 3600 + mm * 60 + (ss[0] if ss else 0) + int(offset_s)
    day_shift, tot = divmod(tot, 86400)
    if day_shift:
        return None, f"{tot//3600:02d}:{(tot%3600)//60:02d}:{tot%60:02d}"  # crossed midnight: date left unknown
    return ev.start_date, f"{tot//3600:02d}:{(tot%3600)//60:02d}:{tot%60:02d}"


@app.post("/api/evidence/{eid}/analyze")
def analyze(eid: int, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    e, c = own_evidence(db, eid, u, True)
    path = config.STORAGE / "evidence" / e.stored_name
    if not I.verify(path, e.sha256):
        raise HTTPException(409, "Integrity check failed: stored file no longer matches its recorded SHA-256. Analysis refused.")
    job = Job(case_pk=c.id, evidence_id=e.id, kind=e.kind); db.add(job)
    e.status, e.error = "processing", None; db.commit()
    db.query(Event).filter_by(evidence_id=e.id, human_review_status="pending").filter(Event.extraction_method != "manual").delete()
    try:
        new = []
        if e.kind == "document":
            r = X.extract_document(str(path), Path(e.stored_name).suffix)
            e.analysis = r
            for pg in r["pages"]:
                for ev in S.extract_events_from_text(pg["text"], pg["ref"]):
                    new.append(Event(case_pk=c.id, description=ev["description"], date=ev["date"], time=ev["time"], location=ev["location"],
                                     source_type="document", evidence_id=e.id, source_file=e.original_name, source_ref=pg["ref"],
                                     extraction_method="rule-based text extraction"))
        elif e.kind == "video":
            fd = config.STORAGE / "frames" / str(e.id); fd.mkdir(parents=True, exist_ok=True)
            r = X.analyze_video(str(path), frames_dir=str(fd), use_yolo=config.ENABLE_YOLO)
            e.analysis = r
            merged = {}
            for o in r["observations"]:  # merge consecutive same-label detections within 10 s
                k = merged.get(o["label"])
                if k and o["offset_s"] - k["last"] <= 10:
                    k["last"] = o["offset_s"]; k["conf"] = max(k["conf"], o["confidence"]); continue
                merged[o["label"]] = k = {"first": o["offset_s"], "last": o["offset_s"], "conf": o["confidence"], "o": o}
                dt, tm = wall(e, o["offset_s"])
                new.append(Event(case_pk=c.id, description=f"{o['label']} detected (detector confidence {o['confidence']:.2f}; not identity)",
                                 date=dt, time=tm, source_type="cctv", evidence_id=e.id, source_file=e.original_name,
                                 source_ref=f"video offset {o['timestamp']}", extraction_method=o["model"],
                                 detail={"frame": o["frame_path"], "confidence": o["confidence"]}))
        elif e.kind == "audio":
            r = X.transcribe_audio(str(path), config.WHISPER_MODEL)
            e.analysis = r
            for sg in r["segments"]:
                dt, tm = wall(e, sg["start"])
                new.append(Event(case_pk=c.id, description=sg["text"], date=dt, time=tm, source_type="audio", evidence_id=e.id,
                                 source_file=e.original_name, source_ref=f"audio {T.fmt_seconds(sg['start'])}-{T.fmt_seconds(sg['end'])}",
                                 extraction_method=r["model"]))
        else:
            raise ValueError("Images are stored and hashed but have no automatic analysis in this version.")
        db.add_all(new)
        e.status, job.status, job.message = "analysed", "done", f"{len(new)} events"
    except Exception as ex:
        e.status, e.error, job.status, job.message = "failed", str(ex)[:1000], "failed", str(ex)[:500]
    job.finished_at = now(); db.commit()
    audit(db, u, "evidence.analyze", c.id, f"{e.original_name}: {job.status} {job.message}")
    if e.status == "failed":
        raise HTTPException(422, e.error)
    return d(e)


class Correction(BaseModel):
    segment_index: int
    text: str = Field(max_length=5000)


@app.put("/api/evidence/{eid}/transcript")
def correct_transcript(eid: int, b: Correction, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    e, c = own_evidence(db, eid, u, True)
    a = dict(e.analysis or {})
    segs = a.get("segments") or []
    if not 0 <= b.segment_index < len(segs):
        raise HTTPException(422, "Bad segment index")
    segs[b.segment_index]["original_text"] = segs[b.segment_index].get("original_text", segs[b.segment_index]["text"])
    segs[b.segment_index]["text"], segs[b.segment_index]["corrected_by"] = b.text, u.username
    e.analysis = {**a, "segments": segs}; db.commit()
    audit(db, u, "transcript.correct", c.id, f"{e.original_name}#{b.segment_index}")
    return {"ok": True}


# ---------- statements, events ----------
class StIn(BaseModel):
    text: str = Field(min_length=3, max_length=20000)
    speaker: str | None = Field(None, max_length=128)


@app.post("/api/cases/{cid}/statements")
def add_statement(cid: str, b: StIn, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    st = Statement(case_pk=c.id, text=b.text, speaker=b.speaker); db.add(st); db.commit()
    claims = []
    for i, sent in enumerate(S.split_statement(b.text)):
        x = S.extract_claim(sent, b.speaker, f"statement {st.id}, sentence {i+1}")
        cl = Claim(case_pk=c.id, statement_id=st.id, event_description=sent, speaker_reference=b.speaker, claimed_location=x["claimed_location"],
                   claimed_date=x["claimed_date"], claimed_time=x["claimed_time"], people=x["people"], objects=x["objects"], source_reference=x["source_reference"])
        db.add(cl); claims.append(cl)
        if x["claimed_time"] or x["claimed_date"]:
            db.add(Event(case_pk=c.id, description=sent, date=x["claimed_date"], time=x["claimed_time"], location=x["claimed_location"],
                         source_type="statement", source_ref=x["source_reference"], extraction_method="rule-based"))
    db.commit(); audit(db, u, "statement.add", c.id, f"statement {st.id}")
    return {"statement": d(st), "claims": [d(x) for x in claims]}


@app.get("/api/cases/{cid}/statements")
def list_statements(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    return {"statements": [d(x) for x in db.query(Statement).filter_by(case_pk=c.id)], "claims": [d(x) for x in db.query(Claim).filter_by(case_pk=c.id)]}


class EvIn(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    location: str | None = None
    human_review_status: str | None = Field(None, pattern="^(pending|reviewed|rejected)$")


@app.post("/api/cases/{cid}/events")
def add_event(cid: str, b: EvIn, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    ev = Event(case_pk=c.id, source_type="manual", extraction_method="manual", source_ref=f"entered by {u.username}", **b.model_dump(exclude_none=True))
    db.add(ev); db.commit(); audit(db, u, "event.create", c.id, str(ev.id))
    return d(ev)


@app.patch("/api/events/{evid}")
def patch_event(evid: int, b: EvIn, u=Depends(require_roles(*INVESTIGATE, "reviewer")), db=Depends(get_db)):
    ev = db.get(Event, evid)
    if not ev:
        raise HTTPException(404)
    c = db.get(Case, ev.case_pk)
    only_review = u.role == "reviewer"
    get_case(db, c.case_id, u, write=not only_review)
    changes = {"human_review_status": b.human_review_status} if only_review else b.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(ev, k, v)
    db.commit(); audit(db, u, "event.update", c.id, f"{ev.id}: {list(changes)}")
    return d(ev)


def events_of(db, c):
    return [{**d(e), "id": e.id} for e in db.query(Event).filter_by(case_pk=c.id)]


@app.get("/api/cases/{cid}/timeline")
def timeline(cid: str, source: str = "", q: str = "", u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    ev = [e for e in events_of(db, c) if (not source or e["source_type"] == source) and (not q or q.lower() in e["description"].lower())]
    return T.build_timeline(ev)


# ---------- comparison ----------
@app.post("/api/cases/{cid}/compare")
def run_compare(cid: str, window_min: int = 30, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    claims = [d(x) for x in db.query(Claim).filter_by(case_pk=c.id)]
    res = C.compare(claims, events_of(db, c), max(1, min(window_min, 240)))
    db.query(Finding).filter_by(case_pk=c.id, review_status="pending").delete()
    for r in res:
        db.add(Finding(case_pk=c.id, claim_id=r["claim_id"], label=r["label"], data=r))
    db.commit(); audit(db, u, "comparison.run", c.id, f"{len(res)} findings")
    return [d(f) for f in db.query(Finding).filter_by(case_pk=c.id)]


@app.get("/api/cases/{cid}/findings")
def findings(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    return [d(f) for f in db.query(Finding).filter_by(case_pk=c.id)]


class Review(BaseModel):
    review_status: str = Field(pattern="^(pending|approved|rejected)$")
    reviewer_note: str = Field("", max_length=2000)


@app.put("/api/findings/{fid}/review")
def review(fid: int, b: Review, u=Depends(require_roles("administrator", "reviewer")), db=Depends(get_db)):
    f = db.get(Finding, fid)
    if not f:
        raise HTTPException(404)
    f.review_status, f.reviewer_note = b.review_status, b.reviewer_note; db.commit()
    audit(db, u, "finding.review", f.case_pk, f"{fid}: {b.review_status}")
    return d(f)


# ---------- graph ----------
@app.get("/api/cases/{cid}/graph")
def graph(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    nodes = [{"id": "case", "type": "case", "label": c.case_id, "detail": c.title}]
    edges, seen = [], {}
    def node(i, t, l, det=""):
        if i not in seen:
            seen[i] = 1; nodes.append({"id": i, "type": t, "label": l, "detail": det})
    for ev in db.query(Evidence).filter_by(case_pk=c.id):
        node(f"ev{ev.id}", ev.kind, ev.original_name, f"sha256 {ev.sha256[:16]}…"); edges.append({"source": "case", "target": f"ev{ev.id}", "label": "contains", "basis": "recorded"})
    for e in db.query(Event).filter_by(case_pk=c.id):
        node(f"e{e.id}", "event", e.description[:40], f"{e.date or '?'} {e.time or '?'} — {e.source_file or e.source_type} {e.source_ref or ''}")
        edges.append({"source": f"ev{e.evidence_id}" if e.evidence_id else "case", "target": f"e{e.id}", "label": "recorded in" if e.evidence_id else "mentions", "basis": "extracted"})
        if e.location:
            node(f"l:{e.location}", "location", e.location); edges.append({"source": f"e{e.id}", "target": f"l:{e.location}", "label": "occurs at", "basis": "extracted"})
    for cl in db.query(Claim).filter_by(case_pk=c.id):
        node(f"c{cl.id}", "statement", cl.event_description[:40], cl.source_reference or ""); edges.append({"source": "case", "target": f"c{cl.id}", "label": "mentions", "basis": "recorded"})
    for f in db.query(Finding).filter_by(case_pk=c.id):
        if f.label in (C.INCONSISTENT, C.CONSISTENT):
            for ref in f.data["evidence"]:
                if ref.get("event_id"):
                    edges.append({"source": f"c{f.claim_id}", "target": f"e{ref['event_id']}", "label": "potentially conflicts with" if f.label == C.INCONSISTENT else "supports",
                                  "basis": "inferred by rule (unverified)"})
    return {"nodes": nodes, "edges": edges}


# ---------- assistant (case-scoped retrieval) ----------
class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@app.post("/api/cases/{cid}/assistant")
def assistant(cid: str, b: Ask, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    passages = []
    for ev in db.query(Evidence).filter_by(case_pk=c.id):
        a = ev.analysis or {}
        for pg in a.get("pages", []):
            passages.append({"text": pg["text"], "source_file": ev.original_name, "ref": pg["ref"]})
        for sg in a.get("segments", []):
            passages.append({"text": sg["text"], "source_file": ev.original_name, "ref": f"audio {T.fmt_seconds(sg['start'])}"})
    for st in db.query(Statement).filter_by(case_pk=c.id):
        passages.append({"text": st.text, "source_file": f"statement {st.id}", "ref": "full text"})
    audit(db, u, "assistant.query", c.id, b.question[:200])
    res = R.answer(b.question, passages)  # LLM adapter hook: pass llm=callable when LLM_PROVIDER is configured
    res["llm_configured"] = config.LLM_PROVIDER != "none"
    if res["llm_configured"] and res["provider"] != "llm":
        res["note"] = "An LLM provider is configured in .env but no adapter is implemented in this version; retrieval-only output shown."
    return res


# ---------- reports ----------
@app.post("/api/cases/{cid}/reports")
def make_report(cid: str, u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    c = get_case(db, cid, u, True)
    ev = [{"filename": e.original_name, "kind": e.kind, "sha256": e.sha256, "integrity": e.last_integrity or "not checked"} for e in db.query(Evidence).filter_by(case_pk=c.id)]
    claims = [d(x) for x in db.query(Claim).filter_by(case_pk=c.id)]
    pdf = RP.build_report({"case_id": c.case_id, "title": c.title, "category": c.category, "status": c.status, "created": c.created_at.isoformat()[:10]},
                          ev, claims, None, T.build_timeline(events_of(db, c)), [f.data | {"human_review_status": f.review_status} for f in db.query(Finding).filter_by(case_pk=c.id)],
                          c.notes, c.synthetic)
    name = f"{uuid.uuid4().hex}.pdf"
    (config.STORAGE / "reports").mkdir(exist_ok=True)
    (config.STORAGE / "reports" / name).write_bytes(pdf)
    r = Report(case_pk=c.id, filename=name, created_by=u.id); db.add(r); db.commit()
    audit(db, u, "report.generate", c.id, name)
    return d(r)


@app.get("/api/cases/{cid}/reports")
def list_reports(cid: str, u=Depends(current_user), db=Depends(get_db)):
    c = get_case(db, cid, u)
    return [d(r) for r in db.query(Report).filter_by(case_pk=c.id).order_by(Report.id.desc())]


@app.get("/api/reports/{rid}/download")
def dl_report(rid: int, u=Depends(current_user), db=Depends(get_db)):
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404)
    c = db.get(Case, r.case_pk); get_case(db, c.case_id, u)
    return FileResponse(config.STORAGE / "reports" / r.filename, media_type="application/pdf", filename=f"{c.case_id}-report-{r.id}.pdf")


# ---------- dashboard, audit, demo ----------
@app.get("/api/dashboard")
def dashboard(u=Depends(current_user), db=Depends(get_db)):
    cs = db.query(Case)
    if u.role == "investigator":
        cs = cs.filter(Case.owner_id == u.id)
    ids = [c.id for c in cs]
    q = lambda m: db.query(m).filter(m.case_pk.in_(ids))
    return {"total_cases": len(ids), "active_cases": cs.filter(Case.status == "active").count(), "evidence_files": q(Evidence).count(),
            "completed_analyses": q(Evidence).filter(Evidence.status == "analysed").count(),
            "pending_reviews": q(Finding).filter(Finding.review_status == "pending").count() + q(Event).filter(Event.human_review_status == "pending").count(),
            "status_distribution": {s: n for s, n in db.query(Case.status, func.count()).filter(Case.id.in_(ids)).group_by(Case.status)},
            "recent_jobs": [d(j) for j in q(Job).order_by(Job.id.desc()).limit(8)],
            "recent_activity": [d(a) for a in db.query(AuditLog).filter((AuditLog.case_pk.in_(ids)) | (AuditLog.user_id == u.id)).order_by(AuditLog.id.desc()).limit(10)]}


@app.get("/api/audit")
def audit_log(case: str = "", u=Depends(require_roles("administrator", "reviewer")), db=Depends(get_db)):
    qs = db.query(AuditLog)
    if case:
        c = get_case(db, case, u); qs = qs.filter(AuditLog.case_pk == c.id)
    return [d(a) for a in qs.order_by(AuditLog.id.desc()).limit(500)]


DEMO_DOC = ("SYNTHETIC DEMONSTRATION DOCUMENT - not real evidence.\nStation log: A dark sedan entered the railway station car park at 20:05 on 2024-03-05.\n"
            "Gate record: The barrier opened at 20:07 on 2024-03-05 at the railway station.\n")


@app.post("/api/demo/reset")
def demo_reset(u=Depends(require_roles(*INVESTIGATE)), db=Depends(get_db)):
    """Create/reset a clearly-labelled SYNTHETIC case owned by the caller."""
    old = db.query(Case).filter(Case.title.like("[SYNTHETIC]%"), Case.owner_id == u.id).all()
    for o in old:
        o.status = "archived"
    c = Case(case_id=next_case_id(db), title="[SYNTHETIC] Sample Timeline Investigation", category="demonstration", owner_id=u.id,
             synthetic=True, description="Fictional demonstration data. Not real evidence.")
    db.add(c); db.commit()
    import hashlib
    stored = f"{uuid.uuid4().hex}.txt"; p = config.STORAGE / "evidence" / stored; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(DEMO_DOC, encoding="utf-8")
    e = Evidence(case_pk=c.id, original_name="synthetic_station_log.txt", stored_name=stored, kind="document", size=p.stat().st_size,
                 sha256=hashlib.sha256(p.read_bytes()).hexdigest(), uploaded_by=u.id)
    db.add(e)
    db.add(Event(case_pk=c.id, description="[SYNTHETIC] Person observed on CCTV at railway station entrance", date="2024-03-05", time="20:05", location="railway station",
                 source_type="cctv", source_file="synthetic_cctv.mp4 (not supplied)", source_ref="00:02:14", extraction_method="synthetic seed"))
    db.commit(); audit(db, u, "demo.reset", c.id)
    return d(c)
