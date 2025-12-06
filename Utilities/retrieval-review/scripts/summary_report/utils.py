"""
Utility Functions for Summary Report Generation

Pure helper functions with no domain-specific logic. These are stateless
functions that perform common operations like success checking, file size
bucketing, and file type extraction.
"""

from typing import Optional

from .constants import SIZE_BUCKETS


def is_success(status: Optional[str], status_code: Optional[int]) -> bool:
    """Determine if a retrieval check was successful.

    Success criteria: status == "available" AND status_code in 200-299.

    Args:
        status: The retrieval status string (e.g., "available", "unavailable")
        status_code: The HTTP status code from the retrieval attempt

    Returns:
        True if the retrieval was successful, False otherwise
    """
    if status is None or status_code is None:
        return False
    return status.lower() == "available" and 200 <= status_code < 300


def bucket_filesize(filesize: Optional[int]) -> str:
    """Return the size bucket label for a given file size in bytes.

    Args:
        filesize: File size in bytes, or None if unknown

    Returns:
        A bucket label string (e.g., "0-1MB", "1-10MB", "unknown")
    """
    if filesize is None or filesize < 0:
        return "unknown"
    for label, low, high in SIZE_BUCKETS:
        if low <= filesize < high:
            return label
    return "unknown"


def extract_filetype(filename: Optional[str]) -> str:
    """Extract file extension (filetype) from a filename.

    Args:
        filename: The filename to extract extension from

    Returns:
        The lowercase extension without the dot, or "unknown" if not extractable
    """
    if not filename:
        return "unknown"
    # Get extension from filename
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext if ext else "unknown"
    return "unknown"


def safe_rate(success: int, failure: int) -> Optional[float]:
    """Compute success rate, returning None if no data.

    Args:
        success: Count of successful outcomes
        failure: Count of failed outcomes

    Returns:
        Success rate as a float rounded to 6 decimal places, or None if total is 0
    """
    total = success + failure
    if total == 0:
        return None
    return round(success / total, 6)
