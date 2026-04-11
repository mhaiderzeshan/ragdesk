"""
Unit tests for app.services.storage — file validation and save_upload.
"""

import io
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.services.storage import (
    ALLOWED_EXTENSIONS,
    _get_extension,
    _validate_file,
    save_upload,
)


class TestGetExtension:
    def test_pdf_extension(self):
        assert _get_extension("report.pdf") == ".pdf"

    def test_uppercase_extension_lowercased(self):
        assert _get_extension("doc.PDF") == ".pdf"

    def test_no_extension(self):
        assert _get_extension("noext") == ""

    def test_double_extension(self):
        assert _get_extension("archive.tar.gz") == ".gz"

    def test_txt_extension(self):
        assert _get_extension("notes.txt") == ".txt"

    def test_md_extension(self):
        assert _get_extension("readme.md") == ".md"

    def test_docx_extension(self):
        assert _get_extension("report.docx") == ".docx"


class TestValidateFile:
    def _make_upload_file(self, filename: str) -> UploadFile:
        return UploadFile(filename=filename, file=io.BytesIO(b"data"))

    def test_valid_pdf(self):
        f = self._make_upload_file("doc.pdf")
        assert _validate_file(f) == ".pdf"

    def test_valid_txt(self):
        f = self._make_upload_file("doc.txt")
        assert _validate_file(f) == ".txt"

    def test_valid_md(self):
        f = self._make_upload_file("doc.md")
        assert _validate_file(f) == ".md"

    def test_valid_docx(self):
        f = self._make_upload_file("doc.docx")
        assert _validate_file(f) == ".docx"

    def test_invalid_extension_raises_400(self):
        f = self._make_upload_file("malware.exe")
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(f)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_invalid_python_file(self):
        f = self._make_upload_file("script.py")
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(f)
        assert exc_info.value.status_code == 400

    def test_allowed_extensions_set(self):
        assert ALLOWED_EXTENSIONS == {".pdf", ".txt", ".md", ".docx"}


class TestSaveUpload:
    def test_save_valid_file(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        content = b"%PDF-1.4 fake pdf content"
        upload_file = UploadFile(
            filename="test.pdf",
            file=io.BytesIO(content),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            doc_id, file_path = save_upload(upload_file)

        assert os.path.exists(file_path)
        assert file_path.endswith(".pdf")
        with open(file_path, "rb") as f:
            assert f.read() == content

    def test_save_empty_file_raises_400(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        upload_file = UploadFile(
            filename="empty.pdf",
            file=io.BytesIO(b""),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            with pytest.raises(HTTPException) as exc_info:
                save_upload(upload_file)
            assert exc_info.value.status_code == 400
            assert "empty" in exc_info.value.detail.lower()

    def test_save_oversized_file_raises_413(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        big_content = b"x" * (11 * 1024 * 1024)
        upload_file = UploadFile(
            filename="huge.pdf",
            file=io.BytesIO(big_content),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            with pytest.raises(HTTPException) as exc_info:
                save_upload(upload_file)
            assert exc_info.value.status_code == 413
            assert "exceeds" in exc_info.value.detail.lower()

    def test_save_creates_upload_directory(self, tmp_path):
        upload_dir = str(tmp_path / "new_uploads")
        assert not os.path.exists(upload_dir)

        upload_file = UploadFile(
            filename="test.txt",
            file=io.BytesIO(b"hello"),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            save_upload(upload_file)

        assert os.path.exists(upload_dir)

    def test_save_invalid_extension_raises_400(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        upload_file = UploadFile(
            filename="virus.exe",
            file=io.BytesIO(b"MZ"),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            with pytest.raises(HTTPException) as exc_info:
                save_upload(upload_file)
            assert exc_info.value.status_code == 400

    def test_save_returns_document_id_and_path(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        upload_file = UploadFile(
            filename="report.md",
            file=io.BytesIO(b"# Title"),
        )

        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.MAX_FILE_SIZE_MB = 10
            doc_id, file_path = save_upload(upload_file)

        assert doc_id  # not empty
        assert file_path.endswith(".md")
        assert upload_dir in file_path
