"""Tests for ytmv utility functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from ytmv import sanitize_filename, transliterate  # noqa: E402


class TestTransliterate:
    """Tests for transliterate function."""

    def test_russian_basic(self):
        """Test basic Russian transliteration."""
        assert transliterate("привет") == "privet"
        assert transliterate("москва") == "moskva"
        assert transliterate("спасибо") == "spasibo"

    def test_russian_complex(self):
        """Test complex Russian letters."""
        assert transliterate("щука") == "shchuka"
        assert transliterate("ёжик") == "yozhik"
        assert transliterate("шш") == "shsh"

    def test_ukrainian(self):
        """Test Ukrainian letters."""
        assert transliterate("ї") == "yi"
        assert transliterate("і") == "i"

    def test_mixed(self):
        """Test mixed Cyrillic and Latin."""
        assert transliterate("Hello мир") == "hello mir"
        assert transliterate("Test123 тест") == "test123 test"

    def test_special_chars(self):
        """Test that special characters are removed."""
        result = transliterate("привет!")
        assert "!" not in result


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic(self):
        """Test basic filename sanitization."""
        assert sanitize_filename("привет") == "privet"
        assert sanitize_filename("мир") == "mir"

    def test_spaces_to_underscores(self):
        """Test that spaces are converted to underscores."""
        assert sanitize_filename("hello world") == "hello_world"
        assert sanitize_filename("test  file") == "test_file"

    def test_special_chars_removed(self):
        """Test that special characters are removed."""
        assert "!" not in sanitize_filename("test!")
        assert "?" not in sanitize_filename("what?")
        assert "@" not in sanitize_filename("email@test")

    def test_multiple_underscores(self):
        """Test that multiple underscores are collapsed."""
        result = sanitize_filename("a   b   c")
        assert "__" not in result

    def test_trim_underscores(self):
        """Test that leading/trailing underscores are trimmed."""
        assert not sanitize_filename("_test_").startswith("_")
        assert not sanitize_filename("_test_").endswith("_")

    def test_length_limit(self):
        """Test that long filenames are truncated."""
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_empty_fallback(self):
        """Test that empty names fallback to 'video'."""
        assert sanitize_filename("") == "video"
        assert sanitize_filename("!!!") == "video"

    def test_unicode_removal(self):
        """Test that non-ASCII characters are handled."""
        result = sanitize_filename("测试视频")  # Chinese characters
        assert result  # Should not be empty
