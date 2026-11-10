import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from app.services.file_processing import (
    UploadValidationError,
    extract_text,
    parse_csv,
    validate_upload,
)
from app.services.rag import Retriever


def test_upload_rejects_path_traversal_and_bad_pdf():
    with pytest.raises(UploadValidationError):
        validate_upload("../resume.pdf", "application/pdf", b"%PDF", 100)
    with pytest.raises(UploadValidationError):
        validate_upload("resume.pdf", "application/pdf", b"not a pdf", 100)
    with pytest.raises(UploadValidationError):
        extract_text(b"%PDF not a valid document", ".pdf")


def test_text_extraction_and_csv_validation():
    assert extract_text(b"Jane Doe\njane@example.com", ".txt").startswith("Jane Doe")
    rows = parse_csv(b"candidate_id,name,education,specialization,cgpa\nC1,A,B.Tech,CS,8.2\n", {"candidate_id", "name", "education", "specialization", "cgpa"})
    assert rows[0]["candidate_id"] == "C1"


def test_rag_lexical_fallback_is_deterministic():
    results = Retriever([("Python and SQL", {"id": 1}), ("design systems", {"id": 2})]).search("Python")
    assert results[0].metadata["id"] == 1
