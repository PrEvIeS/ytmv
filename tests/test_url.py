"""Tests for URL handling and playlist detection."""

import pytest
from ytmv import is_playlist


class TestIsPlaylist:
    """Tests for playlist detection."""

    def test_youtube_playlist_list_param(self):
        """Test detection of YouTube playlist with list parameter."""
        assert is_playlist("https://www.youtube.com/watch?v=abc&list=xyz")
        assert is_playlist("https://youtube.com/watch?v=abc&list=xyz")

    def test_youtube_playlist_url(self):
        """Test detection of YouTube playlist URL."""
        assert is_playlist("https://www.youtube.com/playlist?list=xyz")
        assert is_playlist("https://youtube.com/playlist?list=xyz")

    def test_single_video(self):
        """Test that single videos are not detected as playlists."""
        assert not is_playlist("https://www.youtube.com/watch?v=abc")
        assert not is_playlist("https://youtu.be/abc")

    def test_other_sites(self):
        """Test that other sites are not detected as playlists by default."""
        assert not is_playlist("https://vimeo.com/123456")
        assert not is_playlist("https://www.tiktok.com/@user/video/123")

    def test_edge_cases(self):
        """Test edge cases."""
        assert not is_playlist("")
        assert not is_playlist("not a url")
