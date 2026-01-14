import os
import tempfile
from unittest.mock import patch, MagicMock

from tablo_downloader.validation import (
    get_video_duration,
    validate_video_file,
    MIN_FILE_SIZE
)


class TestGetVideoDuration:
    @patch('tablo_downloader.validation.subprocess.run')
    def test_returns_duration_on_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "3456.789"}}'
        )
        duration = get_video_duration('/path/to/video.mp4')
        assert duration == 3456.789

    @patch('tablo_downloader.validation.subprocess.run')
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        duration = get_video_duration('/path/to/video.mp4')
        assert duration is None

    @patch('tablo_downloader.validation.subprocess.run')
    def test_returns_none_on_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='not json')
        duration = get_video_duration('/path/to/video.mp4')
        assert duration is None

    @patch('tablo_downloader.validation.subprocess.run')
    def test_returns_none_on_missing_duration(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {}}'
        )
        duration = get_video_duration('/path/to/video.mp4')
        assert duration is None


class TestValidateVideoFile:
    def test_nonexistent_file_returns_invalid(self):
        is_valid, reason = validate_video_file('/nonexistent/path.mp4')
        assert is_valid is False
        assert 'does not exist' in reason

    def test_small_file_returns_invalid(self):
        # Create a small temp file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'small')
            filepath = f.name
        try:
            is_valid, reason = validate_video_file(filepath)
            assert is_valid is False
            assert 'too small' in reason.lower()
        finally:
            os.unlink(filepath)

    @patch('tablo_downloader.validation.get_video_duration')
    @patch('tablo_downloader.validation.os.path.getsize')
    @patch('tablo_downloader.validation.os.path.exists')
    def test_cannot_determine_duration_returns_invalid(
            self, mock_exists, mock_size, mock_duration):
        mock_exists.return_value = True
        mock_size.return_value = MIN_FILE_SIZE + 1000
        mock_duration.return_value = None  # ffprobe failed

        is_valid, reason = validate_video_file('/path/to/video.mp4')
        assert is_valid is False
        assert 'Cannot determine' in reason

    @patch('tablo_downloader.validation.get_video_duration')
    @patch('tablo_downloader.validation.os.path.getsize')
    @patch('tablo_downloader.validation.os.path.exists')
    def test_duration_mismatch_returns_invalid(
            self, mock_exists, mock_size, mock_duration):
        mock_exists.return_value = True
        mock_size.return_value = MIN_FILE_SIZE + 1000
        mock_duration.return_value = 1000.0  # Actual duration

        # Expected 3600s but got 1000s - big deviation
        is_valid, reason = validate_video_file(
            '/path/to/video.mp4',
            expected_duration=3600
        )
        assert is_valid is False
        assert 'Duration mismatch' in reason

    @patch('tablo_downloader.validation.get_video_duration')
    @patch('tablo_downloader.validation.os.path.getsize')
    @patch('tablo_downloader.validation.os.path.exists')
    def test_valid_file_with_matching_duration(
            self, mock_exists, mock_size, mock_duration):
        mock_exists.return_value = True
        mock_size.return_value = MIN_FILE_SIZE + 1000
        mock_duration.return_value = 3500.0  # Close to expected

        is_valid, reason = validate_video_file(
            '/path/to/video.mp4',
            expected_duration=3600  # Within 10% tolerance
        )
        assert is_valid is True
        assert 'Valid' in reason

    @patch('tablo_downloader.validation.get_video_duration')
    @patch('tablo_downloader.validation.os.path.getsize')
    @patch('tablo_downloader.validation.os.path.exists')
    def test_valid_file_without_expected_duration(
            self, mock_exists, mock_size, mock_duration):
        mock_exists.return_value = True
        mock_size.return_value = MIN_FILE_SIZE + 1000
        mock_duration.return_value = 3600.0

        # No expected duration provided - just checks file is readable
        is_valid, reason = validate_video_file('/path/to/video.mp4')
        assert is_valid is True
        assert 'Valid' in reason

    @patch('tablo_downloader.validation.get_video_duration')
    @patch('tablo_downloader.validation.os.path.getsize')
    @patch('tablo_downloader.validation.os.path.exists')
    def test_custom_tolerance(
            self, mock_exists, mock_size, mock_duration):
        mock_exists.return_value = True
        mock_size.return_value = MIN_FILE_SIZE + 1000
        mock_duration.return_value = 3000.0  # 16.7% deviation from 3600

        # With default 10% tolerance, this should fail
        is_valid, _ = validate_video_file(
            '/path/to/video.mp4',
            expected_duration=3600,
            duration_tolerance=0.10
        )
        assert is_valid is False

        # With 20% tolerance, this should pass
        is_valid, _ = validate_video_file(
            '/path/to/video.mp4',
            expected_duration=3600,
            duration_tolerance=0.20
        )
        assert is_valid is True
