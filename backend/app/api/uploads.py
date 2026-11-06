from dataclasses import dataclass
from typing import Any, Final

from fastapi import Request
from starlette.datastructures import UploadFile

_FILE_FIELD: Final[str] = "file"

# File() would be parsed before any dependency, so before require_admin
MULTIPART_FILE_BODY: Final[dict[str, Any]] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": [_FILE_FIELD],
                    "properties": {_FILE_FIELD: {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


@dataclass(frozen=True, kw_only=True)
class FormFile:
    content_type: str
    data: bytes


async def read_form_file(request: Request, limit: int) -> FormFile:
    """The form's `file` part, read up to one byte over `limit` for the usecase to
    reject; call it after the route's auth dependency has run."""
    async with request.form(max_files=1, max_fields=0) as form:
        upload = form.get(_FILE_FIELD)
        # no file part: the usecase refuses an empty, untyped upload
        if not isinstance(upload, UploadFile):
            return FormFile(content_type="", data=b"")
        return FormFile(content_type=upload.content_type or "", data=await upload.read(limit + 1))
