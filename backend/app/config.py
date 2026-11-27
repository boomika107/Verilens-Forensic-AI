import os
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE/'verilens.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    # Ephemeral key: tokens are invalidated on restart. Set SECRET_KEY in .env for persistence.
    SECRET_KEY = os.urandom(32).hex()
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "480"))
STORAGE = Path(os.getenv("STORAGE_DIR", BASE / "storage"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
ENABLE_YOLO = os.getenv("ENABLE_YOLO", "true").lower() == "true"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none")  # none | openai | gemini  (adapter hook; see llm.py)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
STORAGE.mkdir(parents=True, exist_ok=True)
