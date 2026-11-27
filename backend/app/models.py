from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Integer, Float, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Mapped, mapped_column
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
now = lambda: datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="investigator")  # administrator|investigator|reviewer
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active|closed|archived
    notes: Mapped[str] = mapped_column(Text, default="")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    owner = relationship("User")


class Evidence(Base):
    __tablename__ = "evidence_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16))  # video|audio|document|image
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)   # wall-clock start of recording, supplied by investigator
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")  # uploaded|processing|analysed|failed
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # transcript / pages / observations (+ corrections)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_integrity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Statement(Base):
    __tablename__ = "statements"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    speaker: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Claim(Base):
    __tablename__ = "extracted_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id"))
    event_description: Mapped[str] = mapped_column(Text)
    speaker_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claimed_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    claimed_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    people: Mapped[list] = mapped_column(JSON, default=list)
    objects: Mapped[list] = mapped_column(JSON, default=list)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16))  # cctv|audio|document|statement|manual
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_files.id"), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(64), default="manual")
    verification_status: Mapped[str] = mapped_column(String(24), default="unverified")
    human_review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|reviewed|rejected
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Finding(Base):
    __tablename__ = "comparison_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(48))
    data: Mapped[dict] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Report(Base):
    __tablename__ = "investigation_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    case_pk: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Job(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_pk: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16), default="running")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
