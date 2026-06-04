"""Unit tests for services/file_storage.py — path/filename generation logic."""
import sys
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mock fitz (PyMuPDF) before importing file_storage, since it's not installed
sys.modules.setdefault("fitz", MagicMock())

from services.file_storage import FileStorageService


@pytest.fixture
def storage_service(tmp_path):
    """A FileStorageService with a temporary base directory."""
    service = FileStorageService()
    service.base_dir = tmp_path
    return service


class TestGetDatePath:
    """Tests for date-based directory path generation."""

    def test_specific_date(self, storage_service, tmp_path):
        dt = datetime(2024, 3, 15)
        result = storage_service.get_date_path(dt)
        assert result == tmp_path / "2024" / "March" / "15"

    def test_single_digit_day_zero_padded(self, storage_service, tmp_path):
        dt = datetime(2024, 1, 5)
        result = storage_service.get_date_path(dt)
        assert result == tmp_path / "2024" / "January" / "05"

    def test_none_uses_current_time(self, storage_service):
        # Should not raise
        result = storage_service.get_date_path(None)
        assert isinstance(result, Path)

    def test_december_date(self, storage_service, tmp_path):
        dt = datetime(2025, 12, 31)
        result = storage_service.get_date_path(dt)
        assert result == tmp_path / "2025" / "December" / "31"


class TestEnsureDateDirectory:
    """Tests for directory creation."""

    def test_creates_directory(self, storage_service):
        dt = datetime(2024, 6, 20)
        result = storage_service.ensure_date_directory(dt)
        assert result.exists()
        assert result.is_dir()

    def test_idempotent(self, storage_service):
        dt = datetime(2024, 6, 20)
        result1 = storage_service.ensure_date_directory(dt)
        result2 = storage_service.ensure_date_directory(dt)
        assert result1 == result2
        assert result1.exists()


class TestGenerateFilename:
    """Tests for filename generation."""

    def test_standard_pdf(self, storage_service):
        result = storage_service.generate_filename(42, 1, ".pdf")
        assert result == "paper-42-v1.pdf"

    def test_version_2(self, storage_service):
        result = storage_service.generate_filename(7, 2, ".pdf")
        assert result == "paper-7-v2.pdf"

    def test_different_extension(self, storage_service):
        result = storage_service.generate_filename(1, 1, ".docx")
        assert result == "paper-1-v1.docx"


class TestGenerateImageFilename:
    """Tests for image filename generation."""

    def test_jpeg_image(self, storage_service):
        result = storage_service.generate_image_filename(10, ".jpg")
        assert result == "paper-10-image.jpg"

    def test_png_image(self, storage_service):
        result = storage_service.generate_image_filename(5, ".png")
        assert result == "paper-5-image.png"


class TestGetFilePath:
    """Tests for get_file_path."""

    def test_returns_full_path(self, storage_service, tmp_path):
        dt = datetime(2024, 3, 15)
        result = storage_service.get_file_path("paper-1-v1.pdf", dt)
        expected = tmp_path / "2024" / "March" / "15" / "paper-1-v1.pdf"
        assert result == expected
