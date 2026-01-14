"""Video file validation utilities for detecting incomplete downloads."""

import json
import logging
import os
import subprocess
from typing import Optional, Tuple

LOGGER = logging.getLogger(__name__)

# Minimum file size to be considered valid (1MB)
MIN_FILE_SIZE = 1024 * 1024


def get_video_duration(filepath: str) -> Optional[float]:
    """
    Get video duration in seconds using ffprobe.

    Args:
        filepath: Path to the video file

    Returns:
        Duration in seconds, or None if unable to determine
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        filepath
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration_str = data.get('format', {}).get('duration')
            if duration_str:
                return float(duration_str)
    except subprocess.TimeoutExpired:
        LOGGER.warning('ffprobe timed out for %s', filepath)
    except (json.JSONDecodeError, ValueError) as e:
        LOGGER.warning('Failed to parse ffprobe output for %s: %s', filepath, e)
    except FileNotFoundError:
        LOGGER.error('ffprobe not found. Ensure ffmpeg is installed.')
    return None


def validate_video_file(
    filepath: str,
    expected_duration: Optional[float] = None,
    duration_tolerance: float = 0.10
) -> Tuple[bool, str]:
    """
    Validate a downloaded video file for completeness.

    Args:
        filepath: Path to the video file
        expected_duration: Expected duration in seconds (from Tablo API)
        duration_tolerance: Acceptable deviation as a fraction (0.10 = 10%)

    Returns:
        Tuple of (is_valid, reason)
    """
    # Check file exists
    if not os.path.exists(filepath):
        return False, "File does not exist"

    # Check minimum file size
    file_size = os.path.getsize(filepath)
    if file_size < MIN_FILE_SIZE:
        return False, f"File too small ({file_size} bytes, minimum {MIN_FILE_SIZE})"

    # Get actual duration using ffprobe
    actual_duration = get_video_duration(filepath)
    if actual_duration is None:
        return False, "Cannot determine video duration (possibly corrupted)"

    # If we have expected duration, compare it
    if expected_duration is not None and expected_duration > 0:
        deviation = abs(actual_duration - expected_duration) / expected_duration
        if deviation > duration_tolerance:
            return False, (
                f"Duration mismatch: {actual_duration:.1f}s actual vs "
                f"{expected_duration:.1f}s expected ({deviation:.1%} deviation)"
            )

    return True, f"Valid (duration: {actual_duration:.1f}s)"


def validate_video_file_detailed(
    filepath: str,
    expected_duration: Optional[float] = None
) -> dict:
    """
    Validate a downloaded video file and return detailed results.

    Args:
        filepath: Path to the video file
        expected_duration: Expected duration in seconds (from Tablo API)

    Returns:
        Dict with keys: is_valid, reason, actual_duration, expected_duration, deviation
    """
    result = {
        'is_valid': False,
        'reason': '',
        'actual_duration': None,
        'expected_duration': expected_duration,
        'deviation': None
    }

    # Check file exists
    if not os.path.exists(filepath):
        result['reason'] = "File does not exist"
        return result

    # Check minimum file size
    file_size = os.path.getsize(filepath)
    if file_size < MIN_FILE_SIZE:
        result['reason'] = f"File too small ({file_size} bytes, minimum {MIN_FILE_SIZE})"
        return result

    # Get actual duration using ffprobe
    actual_duration = get_video_duration(filepath)
    result['actual_duration'] = actual_duration

    if actual_duration is None:
        result['reason'] = "Cannot determine video duration (possibly corrupted)"
        return result

    # If we have expected duration, calculate deviation
    if expected_duration is not None and expected_duration > 0:
        deviation = abs(actual_duration - expected_duration) / expected_duration
        result['deviation'] = deviation
        result['reason'] = (
            f"Duration: {actual_duration:.1f}s actual vs "
            f"{expected_duration:.1f}s expected ({deviation:.1%} deviation)"
        )
    else:
        result['reason'] = f"Duration: {actual_duration:.1f}s"

    result['is_valid'] = True
    return result
