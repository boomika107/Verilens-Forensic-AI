from datetime import datetime, timedelta, timezone
import bcrypt, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from .config import SECRET_KEY, TOKEN_MINUTES
from .models import SessionLocal, User, Case, AuditLog

bearer = HTTPBearer(auto_error=False)


def hash_pw(p): return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()
def check_pw(p, h): return bcrypt.checkpw(p.encode()[:72], h.encode())


def make_token(user):
    exp = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, SECRET_KEY, algorithm="HS256")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(cred=Depends(bearer), db=Depends(get_db)):
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = int(jwt.decode(cred.credentials, SECRET_KEY, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    u = db.get(User, uid)
    if not u or not u.active:
        raise HTTPException(401, "User inactive")
    return u


def require_roles(*roles):
    def dep(u=Depends(current_user)):
        if u.role not in roles:
            raise HTTPException(403, "Insufficient role")
        return u
    return dep


def get_case(db, case_id: str, user, write=False):
    """Case-level access: admin all; reviewer read + review all; investigator only own cases."""
    c = db.query(Case).filter(Case.case_id == case_id).first()
    if not c:
        raise HTTPException(404, "Case not found")
    if user.role == "administrator":
        return c
    if user.role == "reviewer":
        if write:
            raise HTTPException(403, "Reviewers have read/review access only")
        return c
    if c.owner_id != user.id:
        raise HTTPException(404, "Case not found")  # do not reveal existence
    return c


def audit(db, user, action, case_pk=None, detail=""):
    db.add(AuditLog(user_id=user.id if user else None, username=user.username if user else None,
                    action=action, case_pk=case_pk, detail=detail[:1000]))
    db.commit()
