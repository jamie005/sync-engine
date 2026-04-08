from http import HTTPMethod
from typing import Callable, NoReturn, cast

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

    def __init__(
        self,
        server_host: str,
        server_port: int,
        timeout_seconds: float = 5.0,
        request_sender: Callable[..., requests.Response] | None = None,
    ) -> None:
        self._base_url = f"{self._HTTP_PREFIX}{server_host}:{server_port}"
        self._timeout_seconds = timeout_seconds
        self._request_sender = request_sender or requests.request

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
            response = self._request_sender(
                method=method.value,
                url=f"{self._base_url}{path}",
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response is None:
                raise SyncApiClientError("Server request failed without a response") from exc
            self._raise_http_error(exc.response, source_error=exc)
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
    def _raise_http_error(response: requests.Response, source_error: Exception | None = None) -> NoReturn:
        try:
            parsed_error = ErrorResponse.model_validate(response.json())
            error_message = parsed_error.error
            raise SyncApiClientError(
                error_message,
                status_code=response.status_code,
                error_response=parsed_error,
            ) from source_error
        except (requests.exceptions.JSONDecodeError, ValidationError):
            raise SyncApiClientError(
                f"Server request failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
            ) from source_error
