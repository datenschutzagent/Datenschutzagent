"""Pure unit tests for the upload magic-byte validator.

Exercises the signature-sniffing logic in isolation so the integration tests
in test_documents_api.py do not need to construct crafted payloads for every
mismatch case.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes.documents import _verify_magic_bytes


PDF_SAMPLE = b"%PDF-1.7\n...rest-of-pdf..."
DOCX_SAMPLE = b"PK\x03\x04" + b"\x00" * 12 + b"[Content_Types].xml"
DOC_SAMPLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8


def test_valid_pdf_passes():
    _verify_magic_bytes(PDF_SAMPLE, "pdf", "a.pdf")


def test_valid_docx_passes():
    _verify_magic_bytes(DOCX_SAMPLE, "docx", "a.docx")


def test_valid_xlsx_shares_zip_magic_with_docx():
    _verify_magic_bytes(DOCX_SAMPLE, "xlsx", "a.xlsx")


def test_valid_doc_passes():
    _verify_magic_bytes(DOC_SAMPLE, "doc", "a.doc")


def test_pdf_content_claiming_docx_is_rejected():
    with pytest.raises(HTTPException) as excinfo:
        _verify_magic_bytes(PDF_SAMPLE, "docx", "mismatch.docx")
    assert excinfo.value.status_code == 415


def test_docx_content_claiming_pdf_is_rejected():
    with pytest.raises(HTTPException) as excinfo:
        _verify_magic_bytes(DOCX_SAMPLE, "pdf", "mismatch.pdf")
    assert excinfo.value.status_code == 415


def test_plaintext_claiming_pdf_is_rejected():
    with pytest.raises(HTTPException) as excinfo:
        _verify_magic_bytes(b"Hello world", "pdf", "fake.pdf")
    assert excinfo.value.status_code == 415


def test_empty_content_is_rejected():
    with pytest.raises(HTTPException):
        _verify_magic_bytes(b"", "pdf", "empty.pdf")


def test_unknown_format_is_rejected():
    with pytest.raises(HTTPException):
        _verify_magic_bytes(PDF_SAMPLE, "rtf", "weird.rtf")
