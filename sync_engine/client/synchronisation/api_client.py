from http import HTTPMethod
from typing import NoReturn, cast

import requests
from pydantic import BaseModel, ValidationError

from sync_engine.common.schemas import (
    CreateFileRequest,
    DeleteFileRequest,
    ErrorResponse,
    FileActionResponse,
    RenameFileRequest,
    RenameFileResponse,
    UpdateFileRequest,
)


class SyncApiClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_response: ErrorResponse | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_response = error_response


class HttpSyncApiClient:
    _REQUEST_RESPONSE_MAP: dict[type[BaseModel], type[BaseModel]] = {
        CreateFileRequest: FileActionResponse,
        UpdateFileRequest: FileActionResponse,
        DeleteFileRequest: FileActionResponse,
        RenameFileRequest: RenameFileResponse,
    }
    _HTTP_PREFIX = "http://"

    def __init__(self, server_host: str, server_port: int, timeout_seconds: float = 5.0) -> None:
        self._base_url = f"{self._HTTP_PREFIX}{server_host}:{server_port}"
        self._timeout_seconds = timeout_seconds

    def create_file(self, body: CreateFileRequest) -> FileActionResponse:
        return cast(FileActionResponse, self._request(HTTPMethod.POST, "/files", body))

    def delete_file(self, body: DeleteFileRequest) -> FileActionResponse:
        return cast(FileActionResponse, self._request(HTTPMethod.DELETE, "/files", body))

    def update_file(self, body: UpdateFileRequest) -> FileActionResponse:
        return cast(FileActionResponse, self._request(HTTPMethod.PUT, "/files", body))

    def rename_file(self, body: RenameFileRequest) -> RenameFileResponse:
        return cast(RenameFileResponse, self._request(HTTPMethod.POST, "/files/rename", body))

    def _request(self, method: HTTPMethod, path: str, request_model: BaseModel | None) -> BaseModel:
        payload, response_type = self._validate_and_prepare_request(request_model)

        try:
            response = requests.request(
                method=method.value,
                url=f"{self._base_url}{path}",
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            self._raise_http_error(exc)
        except requests.exceptions.RequestException as exc:
            raise SyncApiClientError(f"Failed to call sync server: {exc}") from exc

        try:
            response_json = response.json()
            return response_type.model_validate(response_json)
        except requests.exceptions.JSONDecodeError as exc:
            raise SyncApiClientError(f"Server returned invalid JSON: {exc}") from exc
        except ValidationError as exc:
            raise SyncApiClientError(f"Unexpected response payload: {exc}") from exc

    @classmethod
    def _validate_and_prepare_request(cls, request_model: BaseModel | None) -> tuple[dict | None, type[BaseModel]]:
        payload: dict | None = None
        response_type: type[BaseModel] | None = None

        if request_model is not None:
            request_type = type(request_model)
            if request_type not in cls._REQUEST_RESPONSE_MAP:
                raise SyncApiClientError(f"Unsupported request model: {request_type}")
            response_type = cls._REQUEST_RESPONSE_MAP[request_type]
            payload = request_model.model_dump()

        if response_type is None:
            raise SyncApiClientError("No response model defined for this request")

        return payload, response_type

    @staticmethod
    def _raise_http_error(exc: requests.exceptions.HTTPError) -> NoReturn:
        try:
            parsed_error = ErrorResponse.model_validate(exc.response.json())
            error_message = parsed_error.error
            raise SyncApiClientError(
                error_message,
                status_code=exc.response.status_code,
                error_response=parsed_error,
            ) from exc
        except (requests.exceptions.JSONDecodeError, ValidationError):
            raise SyncApiClientError(
                f"Server request failed with status {exc.response.status_code}: {exc.response.text}",
                status_code=exc.response.status_code,
            ) from exc
