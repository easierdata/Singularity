"""
Error Analysis Module for Retrieval Failures

Analyzes HTTP 500 errors and other retrieval failures to identify patterns,
categorize errors, and compute cross-provider failure metrics.

This module provides functions for:
- Categorizing errors into high-level categories
- Extracting normalized error patterns
- Computing per-provider and per-preparation error breakdowns
- Analyzing cross-provider failure correlations
- Computing file characteristics by error category
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set


def extract_error_pattern(response_body: Optional[str]) -> str:
    """
    Extract a normalized error pattern from the response body.

    Replaces dynamic values (CIDs, multihashes) with placeholders to group similar errors.

    Args:
        response_body: The raw error response body from retrieval attempt

    Returns:
        Normalized error pattern string
    """
    if not response_body:
        return "<no response body>"

    pattern = response_body

    # Replace CIDs (bafkrei... format)
    pattern = re.sub(r"baf[a-z0-9]{50,}", "<CID>", pattern)

    # Replace multihashes (hex strings after "multihash")
    pattern = re.sub(r"multihash [a-f0-9]{64,}:", "multihash <HASH>:", pattern)

    # Replace piece CIDs (baga6ea4seaq... format)
    pattern = re.sub(r"baga6ea4seaq[a-z0-9]{50,}", "<PIECE_CID>", pattern)

    # Replace deal IDs
    pattern = re.sub(r"deal \d+", "deal <ID>", pattern)

    # Replace any remaining long hex strings
    pattern = re.sub(r"[a-f0-9]{32,}", "<HASH>", pattern)

    return pattern.strip()


def categorize_error(response_body: Optional[str], error_message: Optional[str]) -> str:
    """
    Categorize an error into a high-level category.

    Args:
        response_body: The raw error response body
        error_message: Optional error message field

    Returns:
        Category string (e.g., 'multihash_not_found', 'root_load_failure')
    """
    if not response_body and not error_message:
        return "unknown"

    text = (response_body or "") + " " + (error_message or "")
    text_lower = text.lower()

    # Categorize based on keywords (order matters - first match wins)
    # Order matches spec in 03-metric-calculations.md
    if "multihash" in text_lower and "not found" in text_lower:
        return "multihash_not_found"
    if "failed to load root" in text_lower:
        return "root_load_failure"
    if "piece" in text_lower and "not found" in text_lower:
        return "piece_not_found"
    if "cid" in text_lower and "not found" in text_lower:
        return "cid_not_found"
    if "timeout" in text_lower:
        return "timeout"
    if "connection" in text_lower:
        return "connection_error"
    if "ipld" in text_lower:
        return "ipld_error"
    if "could not find node" in text_lower:
        return "node_not_found"
    return "other"


def get_file_extension(file_name: Optional[str]) -> str:
    """Extract file extension from filename."""
    if not file_name:
        return "unknown"
    parts = file_name.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 10:
        return parts[1].lower()
    return "unknown"


def get_size_bucket(file_size: Optional[int]) -> str:
    """Categorize file size into buckets matching summary_report conventions."""
    if file_size is None:
        return "unknown"
    if file_size < 1024 * 1024:  # < 1MB
        return "0-1MB"
    if file_size < 10 * 1024 * 1024:  # < 10MB
        return "1-10MB"
    if file_size < 100 * 1024 * 1024:  # < 100MB
        return "10-100MB"
    if file_size < 1024 * 1024 * 1024:  # < 1GB
        return "100MB-1GB"
    return "1GB+"


def compute_error_analysis(
    cid_data: List[Dict[str, Any]],
    provider_names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Compute comprehensive error analysis from CID retrieval data.

    Analyzes HTTP 500 errors to identify patterns, categories, and correlations
    across providers and preparations.

    Args:
        cid_data: List of CID retrieval status records (postprocessed)
        provider_names: Optional dict mapping provider_id -> provider_name.
                       If not provided, provider IDs will be used as names.

    Returns:
        Dictionary with error analysis structure for summary_report.json
    """
    if provider_names is None:
        provider_names = {}

    # Initialize tracking structures
    total_500_errors = 0
    cids_with_any_500: Set[str] = set()
    cids_all_providers_failed: Set[str] = set()

    # Per-provider tracking
    provider_500_counts: Dict[str, int] = {}
    categories_by_provider: Dict[str, Counter] = {}
    patterns_by_provider: Dict[str, Counter] = {}

    # Per-preparation tracking
    categories_by_prep: Dict[str, Counter] = {}

    # Cross-provider tracking (for CIDs with deals on multiple providers)
    # all_fail = every active provider failed with 500
    # some_fail = at least one failed, at least one succeeded (or no 500)
    all_fail_records: List[Dict[str, Any]] = []
    some_fail_records: List[Dict[str, Any]] = []

    # File characteristics by category
    file_ext_by_category: Dict[str, Counter] = {}
    file_size_by_category: Dict[str, Counter] = {}

    for record in cid_data:
        cid = record.get("cid")
        if not cid:
            continue
        active_providers = set(record.get("active_deal_providers", []))
        checks = record.get("storage_provider_retrieval_check", {})
        prep = str(record.get("preparation", "unknown"))
        file_name = record.get("file_name")
        file_size = record.get("file_size")
        file_type = record.get("file_type", get_file_extension(file_name))

        # Skip if no active deals
        if not active_providers:
            continue

        # Track failure status for each provider
        provider_failures: Dict[str, bool] = {}
        provider_categories: Dict[str, str] = {}
        any_500_for_cid = False

        for provider_id in active_providers:
            check = checks.get(provider_id, {})
            status_code = check.get("status_code")

            if status_code == 500:
                total_500_errors += 1
                any_500_for_cid = True
                response_body = check.get("response_body")
                error_message = check.get("error_message")

                # Extract pattern and category
                pattern = extract_error_pattern(response_body)
                category = categorize_error(response_body, error_message)

                provider_failures[provider_id] = True
                provider_categories[provider_id] = category

                # Track per-provider
                provider_500_counts[provider_id] = provider_500_counts.get(provider_id, 0) + 1

                if provider_id not in categories_by_provider:
                    categories_by_provider[provider_id] = Counter()
                    patterns_by_provider[provider_id] = Counter()
                categories_by_provider[provider_id][category] += 1
                patterns_by_provider[provider_id][pattern] += 1

                # Track per-preparation
                if prep not in categories_by_prep:
                    categories_by_prep[prep] = Counter()
                categories_by_prep[prep][category] += 1

                # Track file characteristics by category
                if category not in file_ext_by_category:
                    file_ext_by_category[category] = Counter()
                    file_size_by_category[category] = Counter()
                file_ext_by_category[category][file_type] += 1
                file_size_by_category[category][get_size_bucket(file_size)] += 1
            else:
                provider_failures[provider_id] = False

        if any_500_for_cid:
            cids_with_any_500.add(cid)

        # Check if all active providers failed
        all_failed = all(provider_failures.get(p, True) for p in active_providers)
        if all_failed and active_providers:
            cids_all_providers_failed.add(cid)

        # Cross-provider analysis (only for CIDs with multiple providers)
        # Track all_fail (every provider got 500) and some_fail (mixed results)
        if len(active_providers) > 1 and any_500_for_cid:
            # Build provider categories dict for this record
            categories_for_record = {
                pid: provider_categories.get(pid, None)
                for pid in active_providers
            }

            record_info = {
                "cid": cid,
                "preparation": prep,
                "file_type": file_type,
                "file_size": file_size,
                "provider_categories": categories_for_record,
                "failed_providers": [p for p in active_providers if provider_failures.get(p, False)],
                "successful_providers": [p for p in active_providers if not provider_failures.get(p, False)],
            }

            if all_failed:
                all_fail_records.append(record_info)
            else:
                some_fail_records.append(record_info)

    # Compute records with active deals for percentage calculation
    records_with_active_deals = sum(
        1 for r in cid_data if r.get("active_deal_providers")
    )

    # Build the error_analysis structure
    return _build_error_analysis_structure(
        total_500_errors=total_500_errors,
        cids_with_any_500=cids_with_any_500,
        cids_all_providers_failed=cids_all_providers_failed,
        records_with_active_deals=records_with_active_deals,
        provider_500_counts=provider_500_counts,
        categories_by_provider=categories_by_provider,
        patterns_by_provider=patterns_by_provider,
        categories_by_prep=categories_by_prep,
        all_fail_records=all_fail_records,
        some_fail_records=some_fail_records,
        file_ext_by_category=file_ext_by_category,
        file_size_by_category=file_size_by_category,
        provider_names=provider_names,
    )


def _build_error_analysis_structure(
    total_500_errors: int,
    cids_with_any_500: Set[str],
    cids_all_providers_failed: Set[str],
    records_with_active_deals: int,
    provider_500_counts: Dict[str, int],
    categories_by_provider: Dict[str, Counter],
    patterns_by_provider: Dict[str, Counter],
    categories_by_prep: Dict[str, Counter],
    all_fail_records: List[Dict[str, Any]],
    some_fail_records: List[Dict[str, Any]],
    file_ext_by_category: Dict[str, Counter],
    file_size_by_category: Dict[str, Counter],
    provider_names: Dict[str, str],
) -> Dict[str, Any]:
    """Build the final error_analysis JSON structure.

    Args:
        all_fail_records: Records where every active provider returned 500
        some_fail_records: Records where at least one provider failed but not all
        provider_names: Dict mapping provider_id -> provider_name
    """

    # Overview section
    percentage = (
        round(len(cids_with_any_500) / records_with_active_deals * 100, 2)
        if records_with_active_deals > 0
        else 0
    )

    overview = {
        "total_500_errors": total_500_errors,
        "cids_with_any_500_error": len(cids_with_any_500),
        "cids_all_providers_failed": len(cids_all_providers_failed),
        "percentage_of_active_deal_cids": percentage,
    }

    # By provider section
    by_provider = {}
    for provider_id in sorted(categories_by_provider.keys()):
        categories = categories_by_provider[provider_id]
        patterns = patterns_by_provider[provider_id]

        # Get top 5 patterns
        top_patterns = [
            {
                "pattern": pattern[:200] + "..." if len(pattern) > 200 else pattern,
                "count": count,
                "percentage": round(count / sum(patterns.values()) * 100, 1),
            }
            for pattern, count in patterns.most_common(5)
        ]

        by_provider[provider_id] = {
            "provider_name": provider_names.get(provider_id, provider_id),
            "total_500_errors": provider_500_counts.get(provider_id, 0),
            "categories": dict(categories.most_common()),
            "top_patterns": top_patterns,
        }

    # By preparation section
    by_preparation = {}
    for prep in sorted(categories_by_prep.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        categories = categories_by_prep[prep]
        by_preparation[prep] = {
            "total_500_errors": sum(categories.values()),
            "categories": dict(categories.most_common()),
        }

    # Cross-provider analysis
    cross_provider_analysis = _build_cross_provider_analysis(
        all_fail_records,
        some_fail_records,
        provider_names,
    )

    # File characteristics by category
    file_characteristics = {}
    for category in sorted(file_ext_by_category.keys()):
        ext_counts = file_ext_by_category[category]
        size_counts = file_size_by_category[category]
        file_characteristics[category] = {
            "total_errors": sum(ext_counts.values()),
            "by_filetype": dict(ext_counts.most_common(10)),
            "by_filesize_bucket": _sort_size_buckets(dict(size_counts)),
        }

    return {
        "scope": "active_deals_only",
        "overview": overview,
        "by_provider": by_provider,
        "by_preparation": by_preparation,
        "cross_provider_analysis": cross_provider_analysis,
        "file_characteristics_by_category": file_characteristics,
    }


def _build_cross_provider_analysis(
    all_fail_records: List[Dict[str, Any]],
    some_fail_records: List[Dict[str, Any]],
    provider_names: Dict[str, str],
) -> Dict[str, Any]:
    """Build the cross-provider analysis section.

    Args:
        all_fail_records: Records where all active providers returned 500
        some_fail_records: Records where some (but not all) providers returned 500
        provider_names: Dict mapping provider_id -> provider_name

    Returns:
        Dictionary with cross-provider failure analysis
    """
    total_with_any_error = len(all_fail_records) + len(some_fail_records)

    result: Dict[str, Any] = {
        "cids_with_multiple_providers_and_errors": total_with_any_error,
        "all_providers_fail": len(all_fail_records),
        "some_providers_fail": len(some_fail_records),
    }

    # Analyze all-fail characteristics if we have any
    if all_fail_records:
        by_prep: Counter = Counter()
        by_filetype: Counter = Counter()
        by_filesize: Counter = Counter()
        category_combos: Counter = Counter()

        for rec in all_fail_records:
            by_prep[rec.get("preparation", "unknown")] += 1
            by_filetype[rec.get("file_type", "unknown")] += 1
            by_filesize[get_size_bucket(rec.get("file_size"))] += 1

            # Build category combo from provider_categories dict
            # Sort by provider_id for consistent ordering
            provider_cats = rec.get("provider_categories", {})
            sorted_categories = tuple(
                provider_cats.get(pid, "unknown")
                for pid in sorted(provider_cats.keys())
            )
            category_combos[sorted_categories] += 1

        # Build top category combinations with provider names
        top_combos = []
        for combo, count in category_combos.most_common(5):
            # Get provider IDs from any record with this combo
            sample_rec = next(
                (r for r in all_fail_records
                 if tuple(r.get("provider_categories", {}).get(pid, "unknown")
                         for pid in sorted(r.get("provider_categories", {}).keys())) == combo),
                None
            )
            if sample_rec:
                provider_cats = sample_rec.get("provider_categories", {})
                combo_dict = {
                    provider_names.get(pid, pid): cat
                    for pid, cat in sorted(provider_cats.items())
                }
            else:
                combo_dict = {}

            top_combos.append({
                "categories": combo_dict,
                "count": count,
                "percentage": round(count / len(all_fail_records) * 100, 1),
            })

        result["all_fail_characteristics"] = {
            "top_category_combinations": top_combos,
            "by_preparation": dict(sorted(by_prep.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)),
            "by_filetype": dict(by_filetype.most_common()),
            "by_filesize_bucket": _sort_size_buckets(dict(by_filesize)),
        }

    # Analyze some-fail characteristics if we have any
    if some_fail_records:
        by_prep: Counter = Counter()
        by_filetype: Counter = Counter()
        by_filesize: Counter = Counter()

        for rec in some_fail_records:
            by_prep[rec.get("preparation", "unknown")] += 1
            by_filetype[rec.get("file_type", "unknown")] += 1
            by_filesize[get_size_bucket(rec.get("file_size"))] += 1

        result["some_fail_characteristics"] = {
            "by_preparation": dict(sorted(by_prep.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)),
            "by_filetype": dict(by_filetype.most_common()),
            "by_filesize_bucket": _sort_size_buckets(dict(by_filesize)),
        }

    return result


def _sort_size_buckets(size_dict: Dict[str, int]) -> Dict[str, int]:
    """Sort size buckets in logical order."""
    order = ["0-1MB", "1-10MB", "10-100MB", "100MB-1GB", "1GB+", "unknown"]
    return {k: size_dict[k] for k in order if k in size_dict}
