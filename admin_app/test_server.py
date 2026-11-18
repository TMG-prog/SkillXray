import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from admin_app import server


ADMIN = "11111111-1111-4111-8111-111111111111"
TARGET = "22222222-2222-4222-8222-222222222222"


class FakeSupabase:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        value = self.handler(method, path, kwargs)
        if isinstance(value, httpx.Response):
            return value
        return httpx.Response(200, json=value)


@pytest.fixture
def client():
    with TestClient(server.app) as client:
        yield client
    server.app.dependency_overrides.clear()


def use_gateway(fake):
    server.app.dependency_overrides[server.gateway] = lambda: fake


def authenticate():
    server.app.dependency_overrides[server.admin_user] = lambda: ADMIN


def test_admin_authentication_and_membership(client):
    def handler(method, path, kwargs):
        if path == "/auth/v1/token":
            return {"access_token": "valid"}
        if path == "/auth/v1/user":
            return {"id": ADMIN}
        if path == "/rest/v1/admin_members":
            return []
        raise AssertionError(path)

    fake = FakeSupabase(handler)
    use_gateway(fake)
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/login", json={"email": "u@example.com", "password": "pw"}).status_code == 403
    assert client.get("/api/session", headers={"Authorization": "Bearer valid"}).status_code == 403
    fake.handler = lambda method, path, kwargs: {"id": ADMIN} if path == "/auth/v1/user" else [{"user_id": ADMIN}]
    assert client.get("/api/session", headers={"Authorization": "Bearer valid"}).json() == {"user_id": ADMIN}
    assert fake.calls[-1][2]["service"] is True


def test_user_search_across_pages_and_suspend_admin_rejected(client):
    authenticate()
    accounts = [{"id": str(uuid.UUID(int=i + 1)), "email": f"user{i}@example.com"} for i in range(50)]
    accounts.append({"id": TARGET, "email": "found@example.com"})

    def handler(method, path, kwargs):
        if path == "/auth/v1/admin/users":
            page = kwargs["params"]["page"]
            return {"users": accounts[(page - 1) * 50:page * 50]}
        if path == "/rest/v1/profiles":
            return []
        if path == "/rest/v1/admin_members":
            return [{"user_id": TARGET}]
        raise AssertionError(path)

    fake = FakeSupabase(handler)
    use_gateway(fake)
    result = client.get("/api/users", params={"search": "found"}).json()
    assert [item["id"] for item in result["users"]] == [TARGET]
    assert result["has_next"] is False
    assert client.put(f"/api/users/{TARGET}/suspension", json={"suspended": True}).status_code == 403
    assert not any(call[0] == "PUT" for call in fake.calls)


def test_profile_and_suspension_payloads(client):
    authenticate()
    fake = FakeSupabase(lambda method, path, kwargs: [] if method == "GET" else [kwargs.get("json", {})])
    use_gateway(fake)
    response = client.put(f"/api/users/{TARGET}/profile", json={"full_name": "  Ada  "})
    assert response.status_code == 200
    assert fake.calls[-1][2]["json"] == {"id": TARGET, "full_name": "Ada"}
    assert client.put(f"/api/users/{TARGET}/suspension", json={"suspended": True}).status_code == 200
    assert fake.calls[-1][2]["json"] == {"ban_duration": "876000h"}
    assert client.put(f"/api/users/{TARGET}/suspension", json={"suspended": False}).status_code == 200
    assert fake.calls[-1][2]["json"] == {"ban_duration": "none"}


@pytest.mark.parametrize("path", [f"/api/roles/{TARGET}", f"/api/postings/{TARGET}",
                                   f"/api/resources/{TARGET}", f"/api/taxonomy-changes/{TARGET}"])
def test_missing_delete_is_not_success(client, path):
    authenticate()
    use_gateway(FakeSupabase(lambda method, path, kwargs: []))
    assert client.delete(path).status_code == 404


def test_role_and_resource_validation(client):
    authenticate()
    fake = FakeSupabase(lambda method, path, kwargs: [kwargs.get("json", {})] if method == "POST" else [])
    use_gateway(fake)
    assert client.post("/api/roles", json={"title": "Engineer", "title_pattern": "["}).status_code == 422
    assert client.post("/api/roles", json={"title": " Engineer ", "title_pattern": "engineer"}).status_code == 200
    assert fake.calls[-1][2]["json"]["title"] == "Engineer"
    assert client.put(f"/api/roles/{TARGET}", json={"title": "Engineer"}).status_code == 404
    resource = {"title": " Course ", "provider": " Provider ", "url": "https://example.com",
                "keywords": [" Python ", "python"], "published": True}
    assert client.post("/api/resources", json={**resource, "url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/api/resources", json=resource).status_code == 200
    assert fake.calls[-1][2]["json"]["keywords"] == ["python"]
    assert client.put(f"/api/resources/{TARGET}", json=resource).status_code == 404


def test_posting_import_uniform_fields_and_validation(client):
    authenticate()
    fake = FakeSupabase(lambda method, path, kwargs: kwargs["json"])
    use_gateway(fake)
    csv = b"provider,external_id,role_key,title,company\np,1,software,Engineer,Company\np,2,software,Developer,\n"
    response = client.post("/api/postings/import", files={"file": ("jobs.csv", csv, "text/csv")})
    assert response.json() == {"imported": 2}
    rows = fake.calls[-1][2]["json"]
    assert rows[0].keys() == rows[1].keys()
    assert rows[1]["company"] is None
    assert rows[0]["job_role_id"] is None and rows[0]["dedupe_key"] is None
    assert client.post("/api/postings/import", files={"file": ("bad.csv", b"provider,title\np,x")}).status_code == 422
    assert client.post("/api/postings/import", files={"file": ("bad.csv", b"\xff")}).status_code == 422
    too_many = b"provider,external_id,role_key,title\n" + b"p,1,software,Engineer\n" * 1001
    assert client.post("/api/postings/import", files={"file": ("large.csv", too_many)}).status_code == 422


def test_ingestion_status_reports_quota_and_missing_tables(client, monkeypatch):
    authenticate()
    monkeypatch.setenv("JSEARCH_MONTHLY_QUOTA", "150")
    tables = {
        "/rest/v1/jsearch_usage": [{"requests": 42}],
        "/rest/v1/ingestion_runs": [{"id": "r1", "status": "success", "trigger": "scheduled"}],
        "/rest/v1/job_roles": [{"title": "Software Engineer", "model_role": "software", "last_ingested_at": None}],
    }
    use_gateway(FakeSupabase(lambda method, path, kwargs: tables[path]))
    result = client.get("/api/ingestion").json()
    assert result["quota"] == {"used": 42, "limit": 150, "reserve": 10}
    assert result["runs"][0]["status"] == "success" and result["roles"][0]["model_role"] == "software"
    assert result["setup_required"] is False

    def missing(method, path, kwargs):
        if path != "/rest/v1/job_roles":
            raise server.HTTPException(404, "Supabase rejected the request; check the submitted data.")
        return []

    use_gateway(FakeSupabase(missing))
    pending = client.get("/api/ingestion")
    assert pending.status_code == 200 and pending.json()["setup_required"] is True
    assert pending.json()["quota"]["used"] == 0


def test_taxonomy_staging_and_complete_export(client):
    authenticate()
    def handler(method, path, kwargs):
        if method == "POST":
            return [kwargs["json"]]
        offset = kwargs["params"]["offset"]
        return [{"id": str(i)} for i in range(offset, min(offset + 100, 205))]
    fake = FakeSupabase(handler)
    use_gateway(fake)
    change = {"kind": "skill", "operation": "upsert", "record_key": "s1",
              "record": {"conceptUri": "s1", "preferredLabel": "Skill"}}
    assert client.put("/api/taxonomy-changes", json={**change, "record_key": "wrong"}).status_code == 422
    assert client.put("/api/taxonomy-changes", json=change).status_code == 200
    exported = client.get("/api/taxonomy-export").json()
    assert exported["format"] == "skillxray-esco-changes-v1"
    assert len(exported["changes"]) == 205


def test_dataset_storage_operations_and_missing_delete(client):
    authenticate()
    def handler(method, path, kwargs):
        if method == "GET":
            return httpx.Response(200, content=b"dataset")
        if method == "DELETE":
            return []
        return {}
    fake = FakeSupabase(handler)
    use_gateway(fake)
    response = client.post("/api/datasets", files={"file": ("data.csv", b"dataset")})
    name = response.json()["name"]
    assert fake.calls[-1][1] == f"/storage/v1/object/admin-datasets/{name}"
    assert client.get(f"/api/datasets/{name}").content == b"dataset"
    assert client.delete(f"/api/datasets/{name}").status_code == 404
    fake.handler = lambda method, path, kwargs: [{"name": name}]
    assert client.delete(f"/api/datasets/{name}").status_code == 200
    assert client.get("/api/datasets/invalid").status_code == 422
    assert client.post("/api/datasets", files={"file": ("empty", b"")}).status_code == 422


def test_dataset_list_fetches_all_pages(client):
    authenticate()
    fake = FakeSupabase(lambda method, path, kwargs: [
        {"id": str(i), "name": str(i)}
        for i in range(kwargs["json"]["offset"], min(kwargs["json"]["offset"] + 100, 101))
    ])
    use_gateway(fake)
    assert len(client.get("/api/datasets").json()["files"]) == 101
