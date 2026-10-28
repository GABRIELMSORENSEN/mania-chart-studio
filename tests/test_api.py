import json
import uuid

from fastapi.testclient import TestClient
import pytest

import server
from tests.test_engine import sample


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    return TestClient(server.app)


def test_reject_foreign_origin(client):
    assert client.post("/api/generate", json={"url": "https://youtu.be/s4fuzKjr4cA"}, headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.get("/", headers={"Host": "evil.test"}).status_code == 400


def test_invalid_url_and_missing_project(client):
    assert client.post("/api/generate", json={"url": "https://localhost/test"}).status_code == 422
    assert client.get(f"/api/projects/{uuid.uuid4().hex}").status_code == 404
    assert client.get("/api/projects/not-a-uuid").status_code == 404


def test_project_save_and_export(client, tmp_path):
    ident = uuid.uuid4().hex
    folder = tmp_path / ident
    folder.mkdir()
    project = {"id": ident, "meta": {"title": "Test", "artist": "Artist"}, "analysis": {"duration": 5}, "charts": [sample()]}
    (folder / "project.json").write_text(json.dumps(project), encoding="utf8")
    (folder / "audio.wav").write_bytes(b"test-pcm")
    assert client.get("/api/projects").json()[0]["title"] == "Test"
    assert client.get(f"/api/projects/{ident}").status_code == 200
    project["charts"][0]["offset"] = 20
    saved = client.put(f"/api/projects/{ident}", json={"charts": project["charts"]})
    assert saved.status_code == 200
    assert saved.json()["charts"][0]["offset"] == 20
    assert client.get(f"/api/projects/{ident}/export").content.startswith(b"PK")
    project["charts"][0]["offset"] = -5000
    assert client.put(f"/api/projects/{ident}", json={"charts": project["charts"]}).status_code == 422
