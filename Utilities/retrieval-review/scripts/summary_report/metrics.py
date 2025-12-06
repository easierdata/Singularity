"""
Metrics Computation for Summary Report Generation

Functions for computing various metrics from retrieval check data,
including outcome metrics, unique metrics, and breakdowns by file type
and file size.
"""

from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from .constants import SIZE_BUCKETS
from .utils import bucket_filesize, is_success, safe_rate


def compute_outcome_metrics(checks: List[Dict]) -> Dict[str, Any]:
    """Compute success/failure counts and rate from a list of checks.

    Args:
        checks: List of check records with 'status' and 'status_code' fields

    Returns:
        Dict with 'success_count', 'failure_count', and 'success_rate' keys
    """
    success = sum(1 for c in checks if is_success(c.get("status"), c.get("status_code")))
    failure = len(checks) - success
    return {
        "success_count": success,
        "failure_count": failure,
        "success_rate": safe_rate(success, failure),
    }


def compute_unique_metrics(
    checks: List[Dict],
    id_field: str,  # "pieceCid" or "cid"
    active_deals: Set[Tuple[str, str]],
) -> Dict[str, int]:
    """Compute unique-level success/failure metrics.

    For each unique ID, tracks which providers succeeded/failed to determine:
    - How many unique IDs have at least one provider success
    - How many unique IDs have all providers succeed
    - How many unique IDs have all providers fail

    Args:
        checks: List of check records
        id_field: The field name to use for grouping ("pieceCid" or "cid")
        active_deals: Set of active (pieceCid, provider_id) tuples (unused but kept for API compatibility)

    Returns:
        Dict with unique success/failure counts keyed by the id_field name
    """
    # Group checks by unique ID
    by_id: Dict[str, List[Dict]] = defaultdict(list)
    for check in checks:
        uid = check.get(id_field)
        if uid:
            by_id[uid].append(check)

    # For each unique ID, determine:
    # - Does it have at least one provider success?
    # - Do all providers succeed?
    # - Do all providers fail?
    any_success = 0
    all_success = 0
    all_failed = 0

    for uid_checks in by_id.values():
        successes = [is_success(c.get("status"), c.get("status_code")) for c in uid_checks]
        if any(successes):
            any_success += 1
        if all(successes) and successes:
            all_success += 1
        if not any(successes) and successes:
            all_failed += 1

    return {
        f"unique_{id_field.lower()}s_with_any_provider_success": any_success,
        f"unique_{id_field.lower()}s_all_providers_success": all_success,
        f"unique_{id_field.lower()}s_all_providers_failed": all_failed,
    }


def compute_filetype_breakdown(cid_checks: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """Compute metrics grouped by file type.

    Args:
        cid_checks: List of CID check records with 'filetype' field

    Returns:
        Dict mapping filetype to metrics including total count and success/failure rates
    """
    by_type: Dict[str, List[Dict]] = defaultdict(list)
    for check in cid_checks:
        ft = check.get("filetype") or "unknown"
        by_type[ft].append(check)

    result = {}
    for ft, checks in sorted(by_type.items()):
        metrics = compute_outcome_metrics(checks)
        result[ft] = {
            "total_files_in_active_deals": len(checks),
            **metrics,
        }
    return result


def compute_filesize_breakdown(cid_checks: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """Compute metrics grouped by file size bucket.

    Args:
        cid_checks: List of CID check records with 'filesize' field

    Returns:
        Dict mapping size bucket label to metrics including total count
        and success/failure rates. All standard buckets are included even
        if empty.
    """
    by_bucket: Dict[str, List[Dict]] = defaultdict(list)
    for check in cid_checks:
        bucket = bucket_filesize(check.get("filesize"))
        by_bucket[bucket].append(check)

    # Ensure all standard buckets are present
    result = {}
    for label, _, _ in SIZE_BUCKETS:
        checks = by_bucket.get(label, [])
        metrics = compute_outcome_metrics(checks) if checks else {
            "success_count": 0, "failure_count": 0, "success_rate": None
        }
        result[label] = {
            "total_files_in_active_deals": len(checks),
            **metrics,
        }

    # Include unknown bucket if present
    if "unknown" in by_bucket:
        checks = by_bucket["unknown"]
        metrics = compute_outcome_metrics(checks)
        result["unknown"] = {
            "total_files_in_active_deals": len(checks),
            **metrics,
        }

    return result
