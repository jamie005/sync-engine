from http import HTTPStatus
from pathlib import Path

from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError

from sync_engine.common.hashing import sha256_string
from sync_engine.common.schemas import (
    CreateFileRequest,
    DeleteFileRequest,
    ErrorResponse,
    FileActionResponse,
    RenameFileRequest,
    RenameFileResponse,
    UpdateFileRequest,
)


def _json_response(model: BaseModel, status_code: int):
    """Serialize a pydantic model into a Flask JSON response."""
    return jsonify(model.model_dump()), status_code


def _validation_error_response(exc: ValidationError):
    """Return a standardized 400 response for validation errors."""
    return _json_response(
        ErrorResponse(error="Invalid request payload", details=exc.errors()),
        HTTPStatus.BAD_REQUEST,
    )


def _resolve_safe_path(base_directory: Path, relative_path: str) -> Path:
    """Resolve a relative path and ensure it stays within base_directory."""
    if not relative_path:
        raise ValueError("'file path' must be a non-empty string")

    candidate = (base_directory / relative_path).resolve()
    base_resolved = base_directory.resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("Path must stay within the configured directory") from exc

    return candidate


def _file_hash_mismatch_response(expected_hash: str, content: str):
    """Return a 400 response when file content does not match the supplied hash."""
    computed_hash = sha256_string(content)
    if computed_hash == expected_hash:
        return None

    return _json_response(
        ErrorResponse(
            error="File content hash mismatch",
            details=[
                {"field": "file_hash", "expected": expected_hash, "received": computed_hash}
            ],
        ),
        HTTPStatus.BAD_REQUEST,
    )


def create_app(base_directory: Path) -> Flask:
    """Create and configure the Flask app for file synchronization routes."""
    app = Flask(__name__)
    app.config["BASE_DIRECTORY"] = base_directory.resolve()

    @app.post("/files")
    def create_file():
        payload = request.get_json(silent=True) or {}
        try:
            body = CreateFileRequest.model_validate(payload)
        except ValidationError as exc:
            return _validation_error_response(exc)

        hash_mismatch_response = _file_hash_mismatch_response(body.file_hash, body.content)
        if hash_mismatch_response is not None:
            return hash_mismatch_response

        try:
            target = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.file_name)
        except ValueError as exc:
            return _json_response(ErrorResponse(error=str(exc)), HTTPStatus.BAD_REQUEST)

        if target.exists():
            return _json_response(ErrorResponse(error="File already exists"), HTTPStatus.CONFLICT)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body.content, encoding="utf-8")
        except OSError as exc:
            return _json_response(
                ErrorResponse(error=f"Failed to create file: {str(exc)}"),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return _json_response(
            FileActionResponse(message="File created", file_name=body.file_name),
            HTTPStatus.CREATED,
        )

    @app.put("/files")
    def update_file():
        payload = request.get_json(silent=True) or {}
        try:
            body = UpdateFileRequest.model_validate(payload)
        except ValidationError as exc:
            return _validation_error_response(exc)

        hash_mismatch_response = _file_hash_mismatch_response(body.file_hash, body.content)
        if hash_mismatch_response is not None:
            return hash_mismatch_response

        try:
            target = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.file_name)
        except ValueError as exc:
            return _json_response(ErrorResponse(error=str(exc)), HTTPStatus.BAD_REQUEST)

        if not target.exists() or not target.is_file():
            return _json_response(ErrorResponse(error="File not found"), HTTPStatus.NOT_FOUND)

        # COMPROMISE: I used Path.write_text for simplicity and convenience. It does not support atomic
        # writes, so in a production system I would consider using a more robust approach to avoid data loss.
        try:
            target.write_text(body.content, encoding="utf-8")
        except OSError as exc:
            return _json_response(
                ErrorResponse(error=f"Failed to update file: {str(exc)}"),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return _json_response(
            FileActionResponse(message="File updated", file_name=body.file_name),
            HTTPStatus.OK,
        )

    @app.delete("/files")
    def delete_file():
        payload = request.get_json(silent=True) or {}
        try:
            body = DeleteFileRequest.model_validate(payload)
        except ValidationError as exc:
            return _validation_error_response(exc)

        try:
            target = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.file_name)
        except ValueError as exc:
            return _json_response(ErrorResponse(error=str(exc)), HTTPStatus.BAD_REQUEST)

        if not target.exists() or not target.is_file():
            return _json_response(ErrorResponse(error="File not found"), HTTPStatus.NOT_FOUND)

        try:
            target.unlink()
        except OSError as exc:
            return _json_response(
                ErrorResponse(error=f"Failed to delete file: {str(exc)}"),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return _json_response(
            FileActionResponse(message="File deleted", file_name=body.file_name),
            HTTPStatus.OK,
        )

    @app.post("/files/rename")
    def rename_file():
        payload = request.get_json(silent=True) or {}
        try:
            body = RenameFileRequest.model_validate(payload)
        except ValidationError as exc:
            return _validation_error_response(exc)

        try:
            source = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.old_file_name)
            destination = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.new_file_name)
        except ValueError as exc:
            return _json_response(ErrorResponse(error=str(exc)), HTTPStatus.BAD_REQUEST)

        if not source.exists() or not source.is_file():
            return _json_response(
                ErrorResponse(error="Source file not found"), HTTPStatus.NOT_FOUND
            )

        if destination.exists():
            return _json_response(
                ErrorResponse(error="Destination already exists"), HTTPStatus.CONFLICT
            )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        except OSError as exc:
            return _json_response(
                ErrorResponse(error=f"Failed to rename file: {str(exc)}"),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return _json_response(
            RenameFileResponse(
                message="File renamed",
                old_file_name=body.old_file_name,
                new_file_name=body.new_file_name,
            ),
            HTTPStatus.OK,
        )

    return app
