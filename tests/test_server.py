"""Tests for sync_engine.server.server."""
from http import HTTPStatus

from sync_engine.common.hashing import sha256_string
from sync_engine.server.server import create_app


def _content_payload(file_name: str, content: str) -> dict:
    return {
        "file_name": file_name,
        "content": content,
        "file_hash": sha256_string(content),
    }


def test_create_file_success(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    payload = _content_payload("new.txt", "hello")
    response = client.post("/files", json=payload)

    assert response.status_code == HTTPStatus.CREATED
    assert (temp_dir / "new.txt").read_text(encoding="utf-8") == "hello"


def test_create_file_hash_mismatch(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    payload = {
        "file_name": "bad.txt",
        "content": "hello",
        "file_hash": "not-a-real-hash",
    }
    response = client.post("/files", json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"] == "File content hash mismatch"


def test_create_file_conflict(temp_dir):
    (temp_dir / "existing.txt").write_text("old", encoding="utf-8")
    app = create_app(temp_dir)
    client = app.test_client()

    payload = _content_payload("existing.txt", "new")
    response = client.post("/files", json=payload)

    assert response.status_code == HTTPStatus.CONFLICT


def test_create_file_rejects_path_traversal(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    payload = _content_payload("../escape.txt", "nope")
    response = client.post("/files", json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_update_file_success(temp_dir):
    target = temp_dir / "update.txt"
    target.write_text("before", encoding="utf-8")
    app = create_app(temp_dir)
    client = app.test_client()

    payload = _content_payload("update.txt", "after")
    response = client.put("/files", json=payload)

    assert response.status_code == HTTPStatus.OK
    assert target.read_text(encoding="utf-8") == "after"


def test_update_file_not_found(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    payload = _content_payload("missing.txt", "content")
    response = client.put("/files", json=payload)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_file_success(temp_dir):
    target = temp_dir / "delete.txt"
    target.write_text("bye", encoding="utf-8")
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.delete("/files", json={"file_name": "delete.txt"})

    assert response.status_code == HTTPStatus.OK
    assert not target.exists()


def test_delete_file_not_found(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.delete("/files", json={"file_name": "missing.txt"})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_rename_file_success(temp_dir):
    source = temp_dir / "old.txt"
    source.write_text("data", encoding="utf-8")
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.post(
        "/files/rename",
        json={"old_file_name": "old.txt", "new_file_name": "new.txt"},
    )

    assert response.status_code == HTTPStatus.OK
    assert not source.exists()
    assert (temp_dir / "new.txt").exists()


def test_rename_file_source_missing(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.post(
        "/files/rename",
        json={"old_file_name": "missing.txt", "new_file_name": "new.txt"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_rename_file_destination_exists(temp_dir):
    (temp_dir / "old.txt").write_text("old", encoding="utf-8")
    (temp_dir / "new.txt").write_text("new", encoding="utf-8")
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.post(
        "/files/rename",
        json={"old_file_name": "old.txt", "new_file_name": "new.txt"},
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_create_file_invalid_payload(temp_dir):
    app = create_app(temp_dir)
    client = app.test_client()

    response = client.post("/files", json={"file_name": "x.txt"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"] == "Invalid request payload"
