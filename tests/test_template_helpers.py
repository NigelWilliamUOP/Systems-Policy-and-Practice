"""Unit tests for template_helpers module."""
import pytest
from datetime import datetime
from template_helpers import format_date, smart_title_case, format_post


class TestFormatDate:
    """Tests for the format_date filter."""

    def test_none_returns_empty_string(self):
        assert format_date(None) == ""

    def test_string_input_returned_as_is(self):
        assert format_date("January 1, 2024") == "January 1, 2024"

    def test_datetime_default_format(self):
        dt = datetime(2024, 3, 15, 10, 30)
        assert format_date(dt) == "March 15, 2024"

    def test_datetime_custom_format(self):
        dt = datetime(2024, 12, 25)
        assert format_date(dt, "%Y-%m-%d") == "2024-12-25"

    def test_datetime_short_format(self):
        dt = datetime(2024, 1, 5)
        assert format_date(dt, "%d/%m/%Y") == "05/01/2024"


class TestSmartTitleCase:
    """Tests for the smart_title_case filter."""

    def test_none_returns_none(self):
        assert smart_title_case(None) is None

    def test_empty_string_returns_empty(self):
        assert smart_title_case("") == ""

    def test_all_caps_converted_to_title_case(self):
        result = smart_title_case("THE IMPACT OF AI ON MODERN SCIENCE")
        assert result == "The Impact of AI on Modern Science"

    def test_already_title_case_unchanged(self):
        text = "The Impact of AI on Modern Science"
        assert smart_title_case(text) == text

    def test_lowercase_words_stay_lowercase(self):
        result = smart_title_case("RESEARCH IN THE FIELD OF MACHINE LEARNING")
        assert "in" in result.split()
        assert "the" in result.split()
        assert "of" in result.split()

    def test_first_word_always_capitalized(self):
        result = smart_title_case("THE ANALYSIS OF DATA")
        assert result.startswith("The")

    def test_acronyms_preserved(self):
        result = smart_title_case("USING AI AND ML FOR NLP TASKS")
        assert "AI" in result
        assert "ML" in result
        assert "NLP" in result

    def test_hyphenated_words(self):
        result = smart_title_case("MULTI-AGENT REINFORCEMENT LEARNING")
        assert "Multi-Agent" in result

    def test_punctuation_triggers_capitalization(self):
        result = smart_title_case("FIRST PART: SECOND PART OF THE STUDY")
        # After colon, next word should be capitalized
        parts = result.split(": ")
        assert len(parts) == 2
        assert parts[1][0].isupper()

    def test_no_alpha_chars_returns_text_unchanged(self):
        assert smart_title_case("123 456") == "123 456"

    def test_below_threshold_text_unchanged(self):
        # Less than 70% uppercase — returned as-is
        text = "Already Properly Formatted Title"
        assert smart_title_case(text) == text


class TestFormatPost:
    """Tests for the format_post filter."""

    def test_none_returns_none(self):
        assert format_post(None) is None

    def test_empty_string_returns_empty(self):
        assert format_post("") == ""

    def test_bold_formatting(self):
        result = format_post("This is **bold** text")
        assert "<strong>bold</strong>" in str(result)

    def test_italic_formatting(self):
        result = format_post("This is *italic* text")
        assert "<em>italic</em>" in str(result)

    def test_bold_and_italic(self):
        result = format_post("**bold** and *italic*")
        assert "<strong>bold</strong>" in str(result)
        assert "<em>italic</em>" in str(result)

    def test_html_escaped(self):
        result = format_post("<script>alert('xss')</script>")
        assert "<script>" not in str(result)
        assert "&lt;script&gt;" in str(result)

    def test_plain_text_unchanged(self):
        result = format_post("Hello world")
        assert "Hello world" in str(result)

    def test_html_in_bold_escaped(self):
        result = format_post("**<b>bad</b>**")
        assert "<b>" not in str(result)
        assert "<strong>" in str(result)
