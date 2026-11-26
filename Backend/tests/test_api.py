import io

import pytest
from fastapi.testclient import TestClient

RESUME = "Built services in Python and SQL for reporting. Strong teamwork across squads. " * 3


@pytest.fixture()
def client(pipeline, monkeypatch):
    monkeypatch.setenv("SKIP_LOAD", "1")
    from app import auth, main
    monkeypatch.setattr(auth, "REQUIRE_AUTH", False)
    main.STATE.update(pipeline=pipeline, error=None)
    with TestClient(main.app) as c:
        yield c
    main.STATE.update(pipeline=None, error=None)


def _docx_bytes(text):
    import docx
    d = docx.Document()
    for line in text.split(". "):
        d.add_paragraph(line)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def test_health_and_roles(client):
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/docs"
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/roles").json()["posting_roles"] == ["software"]


def test_health_reports_pipeline_startup_error(client):
    from app import main

    main.STATE["error"] = "RuntimeError: model startup failed"

    assert client.get("/health").json() == {
        "status": "error",
        "error": "RuntimeError: model startup failed",
    }


def test_ict_market_endpoint(client, monkeypatch):
    from types import SimpleNamespace
    from app import main

    engine = SimpleNamespace(_PROFILE_PROVIDER=None)
    monkeypatch.setattr(main.STATE["pipeline"], "engine", engine, raising=False)
    assert client.get("/market/ict").status_code == 503

    class Provider:
        def ict_market_analysis(self, directory):
            return {"posting_counts": {"ict": 3}}

    engine._PROFILE_PROVIDER = Provider()
    assert client.get("/market/ict").json() == {"posting_counts": {"ict": 3}}

    class BrokenProvider:
        def ict_market_analysis(self, directory):
            raise FileNotFoundError("missing ESCO data")

    engine._PROFILE_PROVIDER = BrokenProvider()
    assert client.get("/market/ict").status_code == 503


def test_analyze_docx(client):
    r = client.post("/analyze", data={"role": "software"},
                    files={"file": ("cv.docx", _docx_bytes(RESUME), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["readiness"] == pytest.approx(70.0, abs=0.1)


def test_analyze_text_field(client):
    r = client.post("/analyze", data={"role": "software", "text": RESUME})
    assert r.status_code == 200 and r.json()["n_required"] == 3
    result = r.json()
    assert all("frequency" in skill for skill in result["covered"] + result["gaps"])
    assert result["skill_relationships"]


@pytest.mark.parametrize("kwargs,code", [
    ({"data": {"role": "software"}}, 400),                                                    # nothing sent
    ({"data": {"role": "nobody", "text": RESUME}}, 404),                                      # unknown role
    ({"data": {"role": "software"}, "files": {"file": ("cv.doc", b"x" * 100, "x")}}, 415),    # legacy .doc
    ({"data": {"role": "software"}, "files": {"file": ("cv.exe", b"MZ" + b"x" * 100, "x")}}, 415),
    ({"data": {"role": "software"}, "files": {"file": ("cv.txt", b"too short", "x")}}, 415),   # no readable text
])
def test_errors(client, kwargs, code):
    assert client.post("/analyze", **kwargs).status_code == code


def test_file_too_large(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.0001)
    r = client.post("/analyze", data={"role": "software"}, files={"file": ("cv.txt", b"a" * 1000, "text/plain")})
    assert r.status_code == 413


def test_rate_limit(client, monkeypatch):
    from app import auth, config
    auth._hits.clear()
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 2)
    codes = [client.post("/analyze", data={"role": "software", "text": RESUME}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_loading_state(pipeline, monkeypatch):
    monkeypatch.setenv("SKIP_LOAD", "1")
    from app import auth, main
    monkeypatch.setattr(auth, "REQUIRE_AUTH", False)
    main.STATE.update(pipeline=None, error=None)
    with TestClient(main.app) as c:
        assert c.get("/health").json()["status"] == "loading"
        assert c.post("/analyze", data={"role": "software", "text": RESUME}).status_code == 503


def test_auth_required(pipeline, monkeypatch):
    monkeypatch.setenv("SKIP_LOAD", "1")
    from app import auth, main
    monkeypatch.setattr(auth, "REQUIRE_AUTH", True)
    monkeypatch.setattr(auth, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(auth, "SUPABASE_ANON_KEY", "anon")
    auth._cache.clear()
    main.STATE.update(pipeline=pipeline, error=None)

    class R:
        def __init__(self, code, body): self.status_code, self._b = code, body
        def json(self): return self._b
    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: R(200, {"id": "u1"}) if "good" in k["headers"]["Authorization"] else R(401, {}))
    with TestClient(main.app) as c:
        assert c.get("/roles").status_code == 401
        assert c.get("/roles", headers={"Authorization": "Bearer bad"}).status_code == 401
        assert c.get("/roles", headers={"Authorization": "Bearer good-token"}).status_code == 200
    main.STATE.update(pipeline=None, error=None)
