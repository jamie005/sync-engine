from typing import Any

from pydantic import BaseModel

# COMPROMISE: I used Pydantic models for request/response schemas as it provides convenient validation and
# serialisation. In an ideal world, I would have preferred to use Protobuf as it supports byte content and
# faster encoding/decoding.


class CreateFileRequest(BaseModel):
    file_name: str
    file_hash: str
    content: str = ""


class UpdateFileRequest(BaseModel):
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
