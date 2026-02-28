"""Tests for ytmv configuration."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

# Import after creating temp config
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig:
    """Tests for configuration handling."""

    def test_defaults(self):
        """Test default configuration values."""
        from ytmv import DEFAULTS

        assert 'output_dir_video' in DEFAULTS
        assert 'output_dir_audio' in DEFAULTS
        assert 'video_quality' in DEFAULTS
        assert 'audio_quality' in DEFAULTS
        assert 'max_retries' in DEFAULTS
        assert 'parallel_downloads' in DEFAULTS


class TestVideoInfo:
    """Tests for VideoInfo dataclass."""

    def test_creation(self):
        """Test VideoInfo creation."""
        from ytmv import VideoInfo

        info = VideoInfo(
            url="https://example.com/video",
            title="Test Video"
        )

        assert info.url == "https://example.com/video"
        assert info.title == "Test Video"
        assert info.duration is None
        assert info.thumbnail is None

    def test_with_optional_fields(self):
        """Test VideoInfo with optional fields."""
        from ytmv import VideoInfo

        info = VideoInfo(
            url="https://example.com/video",
            title="Test Video",
            duration=120,
            uploader="TestUser"
        )

        assert info.duration == 120
        assert info.uploader == "TestUser"


class TestDownloadOptions:
    """Tests for DownloadOptions dataclass."""

    def test_defaults(self):
        """Test DownloadOptions default values."""
        from ytmv import DownloadOptions, DownloadMode

        options = DownloadOptions()

        assert options.mode == DownloadMode.VIDEO
        assert options.video_quality == '1080'
        assert options.audio_quality == '192k'
        assert options.audio_format == 'm4a'
        assert options.download_thumbnail == False
        assert options.download_subtitles == False

    def test_custom_values(self):
        """Test DownloadOptions with custom values."""
        from ytmv import DownloadOptions, DownloadMode

        options = DownloadOptions(
            mode=DownloadMode.AUDIO,
            audio_format='mp3',
            audio_quality='320k'
        )

        assert options.mode == DownloadMode.AUDIO
        assert options.audio_format == 'mp3'
        assert options.audio_quality == '320k'
