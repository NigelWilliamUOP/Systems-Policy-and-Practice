"""Unit tests for services/categories.py."""
import pytest
import json
from unittest.mock import patch, mock_open
from services.categories import CategoryService


@pytest.fixture
def sample_categories():
    """A minimal hierarchical category structure for testing."""
    return {
        "Science": {
            "Physics": ["Quantum Mechanics", "Thermodynamics"],
            "Chemistry": {
                "Organic": ["Biochemistry", "Polymer Chemistry"],
                "Inorganic": ["Crystallography"]
            }
        },
        "Humanities": {
            "History": ["Ancient History", "Modern History"]
        }
    }


@pytest.fixture
def category_service(sample_categories, tmp_path):
    """A CategoryService backed by a temporary JSON file."""
    json_file = tmp_path / "academic_disciplines.json"
    json_file.write_text(json.dumps(sample_categories))
    service = CategoryService()
    service.categories_file = json_file
    return service


class TestCategoryService:
    """Tests for CategoryService."""

    def test_load_categories(self, category_service, sample_categories):
        result = category_service.load_categories()
        assert result == sample_categories

    def test_load_categories_cached(self, category_service):
        # First call loads from file
        result1 = category_service.load_categories()
        # Second call returns cached copy
        result2 = category_service.load_categories()
        assert result1 is result2

    def test_get_all_leaf_categories_returns_list(self, category_service):
        leaves = category_service.get_all_leaf_categories()
        assert isinstance(leaves, list)
        assert len(leaves) > 0

    def test_get_all_leaf_categories_format(self, category_service):
        leaves = category_service.get_all_leaf_categories()
        for full_path, leaf_name in leaves:
            assert isinstance(full_path, str)
            assert isinstance(leaf_name, str)
            assert " > " in full_path
            assert leaf_name in full_path

    def test_leaf_categories_includes_expected(self, category_service):
        leaves = category_service.get_all_leaf_categories()
        leaf_names = [leaf for _, leaf in leaves]
        assert "Quantum Mechanics" in leaf_names
        assert "Thermodynamics" in leaf_names
        assert "Biochemistry" in leaf_names
        assert "Crystallography" in leaf_names
        assert "Ancient History" in leaf_names

    def test_leaf_categories_sorted(self, category_service):
        leaves = category_service.get_all_leaf_categories()
        paths = [path for path, _ in leaves]
        assert paths == sorted(paths)

    def test_get_hierarchical_structure(self, category_service, sample_categories):
        result = category_service.get_hierarchical_structure()
        assert result == sample_categories

    def test_get_category_level(self, category_service):
        assert category_service.get_category_level("Science") == 1
        assert category_service.get_category_level("Science > Physics") == 2
        assert category_service.get_category_level("Science > Physics > Quantum Mechanics") == 3

    def test_search_categories_matches(self, category_service):
        results = category_service.search_categories("quantum")
        assert len(results) == 1
        assert results[0][1] == "Quantum Mechanics"

    def test_search_categories_case_insensitive(self, category_service):
        results = category_service.search_categories("HISTORY")
        assert len(results) >= 2  # Ancient History, Modern History

    def test_search_categories_no_match(self, category_service):
        results = category_service.search_categories("zzz_nonexistent")
        assert results == []

    def test_search_categories_limit(self, category_service):
        results = category_service.search_categories("y", limit=2)
        assert len(results) <= 2

    def test_get_categories_by_discipline(self, category_service):
        results = category_service.get_categories_by_discipline("Science")
        assert len(results) > 0
        for path, _ in results:
            assert path.startswith("Science")

    def test_get_categories_by_discipline_no_match(self, category_service):
        results = category_service.get_categories_by_discipline("Nonexistent")
        assert results == []
