"""Unit tests for config.py — environment variable loading."""
import pytest
import os
from pathlib import Path
from unittest.mock import patch


class TestConfigDefaults:
    """Tests that config module exposes correct defaults when env vars are unset."""

    def test_app_name_default(self):
        import config
        assert config.APP_NAME == "JAIGP - Journal for AI Generated Papers"

    def test_debug_default_false(self):
        import config
        assert config.DEBUG is False

    def test_base_url_default(self):
        import config
        assert config.BASE_URL == "http://localhost:8002"

    def test_port_default(self):
        import config
        assert config.PORT == 8002

    def test_workers_default(self):
        import config
        assert config.WORKERS == 3

    def test_host_default(self):
        import config
        assert config.HOST == "127.0.0.1"

    def test_max_file_size_default(self):
        import config
        assert config.MAX_FILE_SIZE_MB == 20
        assert config.MAX_FILE_SIZE_BYTES == 20 * 1024 * 1024

    def test_allowed_pdf_types(self):
        import config
        assert "application/pdf" in config.ALLOWED_PDF_TYPES

    def test_allowed_image_types(self):
        import config
        types = config.ALLOWED_IMAGE_TYPES
        assert "image/jpeg" in types
        assert "image/png" in types

    def test_session_max_age_default(self):
        import config
        assert config.SESSION_MAX_AGE == 86400

    def test_session_cookie_name_default(self):
        import config
        assert config.SESSION_COOKIE_NAME == "jaigp_session"

    def test_admin_orcids_is_list(self):
        import config
        assert isinstance(config.ADMIN_ORCIDS, list)
        assert len(config.ADMIN_ORCIDS) >= 1

    def test_data_dir_is_path(self):
        import config
        assert isinstance(config.DATA_DIR, Path)

    def test_papers_dir_is_path(self):
        import config
        assert isinstance(config.PAPERS_DIR, Path)

    def test_base_dir_is_path(self):
        import config
        assert isinstance(config.BASE_DIR, Path)

    def test_directories_exist(self):
        import config
        assert config.DATA_DIR.exists()
        assert config.PAPERS_DIR.exists()


class TestConfigEnvironmentOverrides:
    """Tests that environment variables override defaults."""

    def test_debug_true_when_set(self):
        with patch.dict(os.environ, {"DEBUG": "true"}):
            # Need to reimport to pick up env changes
            import importlib
            import config
            importlib.reload(config)
            assert config.DEBUG is True
            # Reset
            importlib.reload(config)

    def test_port_override(self):
        with patch.dict(os.environ, {"PORT": "9000"}):
            import importlib
            import config
            importlib.reload(config)
            assert config.PORT == 9000
            importlib.reload(config)

    def test_max_file_size_override(self):
        with patch.dict(os.environ, {"MAX_FILE_SIZE_MB": "50"}):
            import importlib
            import config
            importlib.reload(config)
            assert config.MAX_FILE_SIZE_MB == 50
            assert config.MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024
            importlib.reload(config)
