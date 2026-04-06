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
    HealthResponse,
    RenameFileRequest,
    RenameFileResponse,
)


def _json_response(model: BaseModel, status_code: int):
    return jsonify(model.model_dump()), status_code


def _validation_error_response(exc: ValidationError):
    return _json_response(
        ErrorResponse(error="Invalid request payload", details=exc.errors()),
        HTTPStatus.BAD_REQUEST,
    )


def _resolve_safe_path(base_directory: Path, relative_path: str) -> Path:
    if not relative_path:
        raise ValueError("'file path' must be a non-empty string")

    candidate = (base_directory / relative_path).resolve()
    base_resolved = base_directory.resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("Path must stay within the configured directory") from exc

    return candidate


def create_app(base_directory: Path) -> Flask:
    app = Flask(__name__)
    app.config["BASE_DIRECTORY"] = base_directory.resolve()

    @app.post("/files")
    def create_file():
        payload = request.get_json(silent=True) or {}
        try:
            body = CreateFileRequest.model_validate(payload)
        except ValidationError as exc:
            return _validation_error_response(exc)

        # Verify file content integrity via hash
        computed_hash = sha256_string(body.content)
        if computed_hash != body.file_hash:
            return _json_response(
                ErrorResponse(
                    error="File content hash mismatch",
                    details=[
                        {"field": "file_hash", "expected": body.file_hash, "received": computed_hash}
                    ],
                ),
                HTTPStatus.BAD_REQUEST,
            )

        try:
            target = _resolve_safe_path(app.config["BASE_DIRECTORY"], body.file_name)
        except ValueError as exc:
            return _json_response(ErrorResponse(error=str(exc)), HTTPStatus.BAD_REQUEST)

        if target.exists():
            return _json_response(ErrorResponse(error="File already exists"), HTTPStatus.CONFLICT)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content, encoding="utf-8")

        return _json_response(
            FileActionResponse(message="File created", file_name=body.file_name),
            HTTPStatus.CREATED,
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

        target.unlink()
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

        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)

        return _json_response(
            RenameFileResponse(
                message="File renamed",
                old_file_name=body.old_file_name,
                new_file_name=body.new_file_name,
            ),
            HTTPStatus.OK,
        )

    @app.get("/health")
    def health():
        return _json_response(HealthResponse(status="ok"), HTTPStatus.OK)

    return app
