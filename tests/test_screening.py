"""Unit tests for services/screening.py — specifically _parse_response."""
import pytest
import sys
from pathlib import Path

# We need to mock config and models before importing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.screening import _parse_response


class TestParseResponse:
    """Tests for the _parse_response function that parses Claude screening output."""

    def test_standard_pass_response(self):
        text = (
            "OUTCOME: PASS\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN: None"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"
        assert confidence == "high"
        assert concern is None

    def test_standard_reject_response(self):
        text = (
            "OUTCOME: REJECT\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN: Contains no academic content"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "reject"
        assert confidence == "high"
        assert concern == "Contains no academic content"

    def test_borderline_response(self):
        text = (
            "OUTCOME: BORDERLINE\n"
            "CONFIDENCE: MEDIUM\n"
            "CONCERN: Abstract is vague"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "borderline"
        assert confidence == "medium"
        assert concern == "Abstract is vague"

    def test_case_insensitive_parsing(self):
        text = (
            "outcome: pass\n"
            "confidence: high\n"
            "concern: None"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"
        assert confidence == "high"
        assert concern is None

    def test_unknown_outcome_defaults_to_pass(self):
        text = (
            "OUTCOME: UNKNOWN\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN: None"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"

    def test_unknown_confidence_defaults_to_low(self):
        text = (
            "OUTCOME: PASS\n"
            "CONFIDENCE: EXTREME\n"
            "CONCERN: None"
        )
        outcome, confidence, concern = _parse_response(text)
        assert confidence == "low"

    def test_missing_fields_use_defaults(self):
        text = "Some garbage output"
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"
        assert confidence == "low"
        assert concern is None

    def test_concern_none_literal(self):
        text = (
            "OUTCOME: PASS\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN: none"
        )
        outcome, confidence, concern = _parse_response(text)
        assert concern is None

    def test_concern_with_whitespace(self):
        text = (
            "OUTCOME: REJECT\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN:   Spam content detected  "
        )
        outcome, confidence, concern = _parse_response(text)
        assert concern == "Spam content detected"

    def test_extra_lines_ignored(self):
        text = (
            "Here is my analysis:\n"
            "OUTCOME: PASS\n"
            "CONFIDENCE: HIGH\n"
            "CONCERN: None\n"
            "Additional notes..."
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"
        assert confidence == "high"
        assert concern is None

    def test_mixed_case_outcome_values(self):
        text = (
            "OUTCOME: Pass\n"
            "CONFIDENCE: Medium\n"
            "CONCERN: None"
        )
        outcome, confidence, concern = _parse_response(text)
        assert outcome == "pass"
        assert confidence == "medium"

    def test_empty_string(self):
        outcome, confidence, concern = _parse_response("")
        assert outcome == "pass"
        assert confidence == "low"
        assert concern is None
