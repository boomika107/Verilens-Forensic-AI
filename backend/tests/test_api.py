"""API tests (RBAC, case isolation, upload validation, comparison). Requires the full requirements.txt. NOT executed in the authoring sandbox."""
import os, tempfile
_t = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_t}/t.db"; os.environ["STORAGE_DIR"] = f"{_t}/s"
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def reg(name):
    r = c.post("/api/auth/register", json={"username": name, "email": f"{name}@x.io", "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


admin, au = reg("admin1")
alice, _ = reg("alice")
bob, _ = reg("bob")


def test_roles_and_bootstrap():
    assert au["role"] == "administrator"
    assert c.get("/api/users", headers=alice).status_code == 403
    assert c.get("/api/cases").status_code == 401


def test_case_isolation_and_flow():
    case = c.post("/api/cases", json={"title": "Alice case"}, headers=alice).json()["case_id"]
    assert c.get(f"/api/cases/{case}", headers=bob).status_code == 404
    assert c.get(f"/api/cases/{case}", headers=alice).status_code == 200
    c.post(f"/api/cases/{case}/statements", json={"text": "I was at home at 8:00 PM."}, headers=alice)
    c.post(f"/api/cases/{case}/events", json={"description": "Person at station", "time": "20:05", "location": "railway station"}, headers=alice)
    f = c.post(f"/api/cases/{case}/compare", headers=alice).json()
    assert f[0]["label"] == "Potential inconsistency"
    assert c.put(f"/api/findings/{f[0]['id']}/review", json={"review_status": "approved"}, headers=alice).status_code == 403
    assert c.put(f"/api/findings/{f[0]['id']}/review", json={"review_status": "approved"}, headers=admin).status_code == 200
    r = c.post(f"/api/cases/{case}/reports", headers=alice)
    assert c.get(f"/api/reports/{r.json()['id']}/download", headers=alice).content[:4] == b"%PDF"
    assert c.get(f"/api/reports/{r.json()['id']}/download", headers=bob).status_code == 404


def test_upload_validation_and_hash():
    case = c.post("/api/cases", json={"title": "Upload case"}, headers=alice).json()["case_id"]
    bad = lambda n, b: c.post(f"/api/cases/{case}/evidence", files={"file": (n, b)}, headers=alice).status_code
    assert bad("x.exe", b"MZ") == 415
    assert bad("fake.pdf", b"not a pdf") == 415
    assert bad("empty.txt", b"") == 415
    ok = c.post(f"/api/cases/{case}/evidence", files={"file": ("../../a.txt", b"Gate opened at 20:07.")}, headers=alice)
    assert ok.status_code == 200 and ok.json()["original_name"] == "a.txt" and len(ok.json()["sha256"]) == 64
    eid = ok.json()["id"]
    assert c.post(f"/api/evidence/{eid}/analyze", headers=alice).status_code == 200
    assert c.post(f"/api/evidence/{eid}/verify", headers=alice).json()["match"] is True
    assert c.post(f"/api/evidence/{eid}/verify", headers=bob).status_code == 404
