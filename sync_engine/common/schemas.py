from typing import Any

from pydantic import BaseModel


class CreateFileRequest(BaseModel):
    file_name: str
    file_hash: str
    content: str = ""


class DeleteFileRequest(BaseModel):
    file_name: str


class RenameFileRequest(BaseModel):
    old_file_name: str
    new_file_name: str


class MessageResponse(BaseModel):
    message: str


class FileActionResponse(MessageResponse):
    file_name: str


class RenameFileResponse(MessageResponse):
    old_file_name: str
    new_file_name: str


class ErrorResponse(BaseModel):
    error: str
    details: list[Any] | None = None
