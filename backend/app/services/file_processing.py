"""Safe upload validation and document extraction helpers."""
from __future__ import annotations

import csv
import io
from pathlib import PurePath
from zipfile import BadZipFile

MAX_FILENAME_LENGTH = 255
SUPPORTED_RESUME_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain", "text/csv", "application/octet-stream"},
}


class UploadValidationError(ValueError):
    pass


def validate_upload(filename: str | None, content_type: str | None, content: bytes, max_bytes: int) -> str:
    name = PurePath(filename or "").name
    suffix = PurePath(name).suffix.lower()
    if not name or name != (filename or "") or len(name) > MAX_FILENAME_LENGTH:
        raise UploadValidationError("Unsafe filename")
    if suffix not in SUPPORTED_RESUME_TYPES:
        raise UploadValidationError("Unsupported file type")
    if len(content) > max_bytes:
        raise UploadValidationError("File exceeds the configured size limit")
    if content_type and content_type not in SUPPORTED_RESUME_TYPES[suffix]:
        raise UploadValidationError("Content type does not match file extension")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise UploadValidationError("Invalid PDF file")
    if suffix == ".docx" and not content.startswith(b"PK"):
        raise UploadValidationError("Invalid DOCX file")
    return suffix


def extract_text(content: bytes, suffix: str) -> str:
    if suffix == ".txt":
        return content.decode("utf-8-sig", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as exc:
            raise UploadValidationError("PDF extraction is unavailable; install pypdf") from exc
        try:
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages).strip()
        except (PdfReadError, ValueError) as exc:
            raise UploadValidationError("PDF could not be parsed") from exc
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise UploadValidationError("DOCX extraction is unavailable; install python-docx") from exc
        try:
            return "\n".join(p.text for p in Document(io.BytesIO(content)).paragraphs).strip()
        except (BadZipFile, ValueError) as exc:
            raise UploadValidationError("DOCX could not be parsed") from exc
    raise UploadValidationError("Unsupported file type")


def parse_csv(content: bytes, required_columns: set[str], max_rows: int = 10_000) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = {column.strip() for column in (reader.fieldnames or []) if column}
        missing = required_columns - columns
        if missing:
            raise UploadValidationError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for index, row in enumerate(reader):
            if index >= max_rows:
                raise UploadValidationError("CSV contains too many rows")
            rows.append({key.strip(): (value or "").strip() for key, value in row.items() if key})
        return rows
    except UnicodeDecodeError as exc:
        raise UploadValidationError("CSV must be UTF-8 encoded") from exc
