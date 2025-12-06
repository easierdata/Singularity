"""
Constants for Summary Report Generation

Size bucket definitions and byte unit constants used throughout the
summary report generation process.
"""

from typing import List, Tuple

# Byte unit constants
MIB = 1024 * 1024  # 1 Mebibyte in bytes
GIB = 1024 * MIB   # 1 Gibibyte in bytes

# Size bucket boundaries: (label, lower_bound_bytes, upper_bound_bytes)
# Lower bound is inclusive, upper bound is exclusive
SIZE_BUCKETS: List[Tuple[str, int, float]] = [
    ("0-1MB", 0, 1 * MIB),
    ("1-10MB", 1 * MIB, 10 * MIB),
    ("10-100MB", 10 * MIB, 100 * MIB),
    ("100MB-1GB", 100 * MIB, 1 * GIB),
    ("1GB+", 1 * GIB, float("inf")),
]
