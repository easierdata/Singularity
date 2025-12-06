#!/usr/bin/env python3
"""
Extract CIDs with status_code errors from retrieval check data.

This script reads CID retrieval status data and extracts all entries where
any storage provider returned a non-2xx status code during retrieval checks.

Usage:
    python extract_cids_with_status_errors.py [--input INPUT_FILE] [--output OUTPUT_FILE] [--summary-only]

Examples:
    # Use defaults (reads final_retrieval_cid_status_postprocessed.json from config)
    python extract_cids_with_status_errors.py

    # Summary only (no file output)
    python extract_cids_with_status_errors.py --summary-only

    # Include non-active deals in analysis
    python extract_cids_with_status_errors.py --include-non-active

    # Custom input/output
    python extract_cids_with_status_errors.py --input cid_sample.json --output my_errors.json
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from config import get_file_path, get_path, get_storage_providers, load_config

# Log directory and file configuration
LOG_DIR = Path("./output/logs")
LOG_FILE = LOG_DIR / "extract_cids_with_status_errors.log"


def setup_logging() -> logging.Logger:
    """
    Configure logging to write to both console and log file.

    Returns:
        Configured logger instance.
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("extract_cids_errors")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # File handler with UTF-8 encoding and append mode
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def write_to_log_file(text: str) -> None:
    """Write text directly to log file without timestamp formatting."""
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


# Initialize logger
logger = setup_logging()


def is_retrieval_success(check_data: dict[str, Any]) -> bool:
    """
    Determine if a retrieval check was successful.

    Args:
        check_data: Provider retrieval check data

    Returns:
        True if retrieval was successful (status 200-299), False otherwise
    """
    if not isinstance(check_data, dict):
        return False
    status_code = check_data.get("status_code")
    if status_code is None:
        return False
    return 200 <= status_code < 300


def get_active_deal_providers(record: dict[str, Any]) -> set[str]:
    """Get set of provider IDs that have active deals for this CID."""
    return set(record.get("active_deal_providers", []))


def has_error_status_active_deals(record: dict[str, Any], active_only: bool = True) -> bool:
    """
    Check if any provider with active deals has an error status code (non-2xx).

    Args:
        record: A CID record containing storage_provider_retrieval_check
        active_only: If True, only check providers with active deals

    Returns:
        True if any qualifying provider has a non-2xx status code, False otherwise
    """
    provider_checks = record.get("storage_provider_retrieval_check", {})
    active_providers = get_active_deal_providers(record) if active_only else None

    for provider_id, check_data in provider_checks.items():
        # Skip if we're only checking active deals and this provider doesn't have one
        if active_only and provider_id not in active_providers:
            continue

        if isinstance(check_data, dict) and not is_retrieval_success(check_data):
            return True

    return False


def all_active_providers_failed(record: dict[str, Any]) -> bool:
    """
    Check if ALL providers with active deals failed retrieval for this CID.

    Args:
        record: A CID record containing storage_provider_retrieval_check

    Returns:
        True if all active-deal providers failed (none succeeded), False otherwise
    """
    provider_checks = record.get("storage_provider_retrieval_check", {})
    active_providers = get_active_deal_providers(record)

    if not active_providers:
        return False  # No active deals means not in scope

    for provider_id in active_providers:
        check_data = provider_checks.get(provider_id, {})
        if is_retrieval_success(check_data):
            return False  # At least one active provider succeeded

    return True  # All active providers failed


def get_providers_with_errors_active(
    record: dict[str, Any], active_only: bool = True
) -> list[tuple[str, int]]:
    """
    Get list of (provider_id, status_code) for providers that returned errors.

    Args:
        record: A CID record containing storage_provider_retrieval_check
        active_only: If True, only include providers with active deals

    Returns:
        List of (provider_id, status_code) tuples for providers with non-2xx status
    """
    provider_checks = record.get("storage_provider_retrieval_check", {})
    active_providers = get_active_deal_providers(record) if active_only else None
    providers_with_errors = []

    for provider_id, check_data in provider_checks.items():
        if active_only and provider_id not in active_providers:
            continue

        if isinstance(check_data, dict) and not is_retrieval_success(check_data):
            status_code = check_data.get("status_code")
            providers_with_errors.append((provider_id, status_code))

    return providers_with_errors


def get_failure_details_active(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Get failure details for each active-deal provider that failed.

    Args:
        record: A CID record containing storage_provider_retrieval_check

    Returns:
        Dict mapping provider_id to failure info (status_code, error_message)
    """
    provider_checks = record.get("storage_provider_retrieval_check", {})
    active_providers = get_active_deal_providers(record)
    failures = {}

    for provider_id in active_providers:
        check_data = provider_checks.get(provider_id, {})
        if isinstance(check_data, dict) and not is_retrieval_success(check_data):
            failures[provider_id] = {
                "status_code": check_data.get("status_code"),
                "error_message": check_data.get("error_message"),
                "status": check_data.get("status"),
            }

    return failures


def analyze_retrieval_data(input_path: Path, include_non_active: bool = False) -> dict[str, Any]:
    """
    Analyze CID retrieval data for errors and complete failures.

    Args:
        input_path: Path to input JSON file
        include_non_active: If True, include all providers; if False, only active deals

    Returns:
        Analysis results dictionary
    """
    logger.info(f"Reading from: {input_path}")
    scope_label = "all providers" if include_non_active else "active deals only"
    logger.info(f"Scope: {scope_label}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected input to be a JSON array")

    total_records = len(data)
    records_with_active_deals = 0
    records_with_errors: list[dict[str, Any]] = []
    records_all_failed: list[dict[str, Any]] = []

    # Track statistics by provider and status code for errors
    provider_error_stats: dict[str, int] = {}
    error_by_status_code: dict[str, int] = {}

    # Track failure reasons for all-failed CIDs
    all_failed_by_status: dict[str, int] = {}
    all_failed_by_preparation: dict[str, int] = {}
    all_failed_by_filetype: dict[str, int] = {}
    all_failed_by_filesize: dict[str, int] = {}

    for record in data:
        has_active = record.get("has_active_deal", False)
        if has_active:
            records_with_active_deals += 1

        # Skip records without active deals if we're in active-only mode
        if not include_non_active and not has_active:
            continue

        # Check for any errors (scoped to active providers)
        if has_error_status_active_deals(record, active_only=not include_non_active):
            records_with_errors.append(record)
            for provider_id, status_code in get_providers_with_errors_active(
                record, active_only=not include_non_active
            ):
                provider_error_stats[provider_id] = provider_error_stats.get(provider_id, 0) + 1
                status_key = str(status_code) if status_code is not None else "unknown"
                error_by_status_code[status_key] = error_by_status_code.get(status_key, 0) + 1

        # Check for all-active-providers-failed
        if all_active_providers_failed(record):
            records_all_failed.append(record)

            # Track by preparation
            prep = str(record.get("preparation", "unknown"))
            all_failed_by_preparation[prep] = all_failed_by_preparation.get(prep, 0) + 1

            # Track by filetype
            filetype = record.get("file_type", "unknown")
            all_failed_by_filetype[filetype] = all_failed_by_filetype.get(filetype, 0) + 1

            # Track by filesize bucket
            file_size = record.get("file_size", 0)
            bucket = get_filesize_bucket(file_size)
            all_failed_by_filesize[bucket] = all_failed_by_filesize.get(bucket, 0) + 1

            # Track failure status codes
            failures = get_failure_details_active(record)
            for failure_info in failures.values():
                status = str(failure_info.get("status_code", "unknown"))
                all_failed_by_status[status] = all_failed_by_status.get(status, 0) + 1

    logger.info(f"Found {len(records_with_errors):,} CIDs with errors out of {records_with_active_deals:,} active-deal CIDs")

    # Build analysis results
    analysis = {
        "input_file": str(input_path),
        "scope": scope_label,
        "total_records_scanned": total_records,
        "records_with_active_deals": records_with_active_deals,
        # Records with any error (non-2xx status)
        "records_with_any_error": {
            "count": len(records_with_errors),
            "percentage": round(len(records_with_errors) / records_with_active_deals * 100, 2)
            if records_with_active_deals > 0
            else 0,
            "by_status_code": dict(sorted(error_by_status_code.items(), key=lambda x: x[1], reverse=True)),
            "by_provider": provider_error_stats,
        },
        # Records where ALL active providers failed
        "records_all_providers_failed": {
            "count": len(records_all_failed),
            "percentage": round(len(records_all_failed) / records_with_active_deals * 100, 2)
            if records_with_active_deals > 0
            else 0,
            "by_status_code": dict(sorted(all_failed_by_status.items(), key=lambda x: x[1], reverse=True)),
            "by_preparation": dict(sorted(all_failed_by_preparation.items())),
            "by_filetype": dict(sorted(all_failed_by_filetype.items(), key=lambda x: x[1], reverse=True)),
            "by_filesize": dict(sorted(all_failed_by_filesize.items(), key=filesize_sort_key)),
        },
        # Raw data for output
        "_records_with_errors": records_with_errors,
        "_records_all_failed": records_all_failed,
    }

    return analysis


def get_filesize_bucket(size: int) -> str:
    """Categorize file size into buckets."""
    if size is None or size == 0:
        return "unknown"
    elif size < 1024 * 1024:  # < 1MB
        return "0-1MB"
    elif size < 10 * 1024 * 1024:  # < 10MB
        return "1-10MB"
    elif size < 100 * 1024 * 1024:  # < 100MB
        return "10-100MB"
    elif size < 1024 * 1024 * 1024:  # < 1GB
        return "100MB-1GB"
    else:
        return "1GB+"


def filesize_sort_key(item: tuple[str, int]) -> int:
    """Sort key for filesize buckets."""
    order = {"0-1MB": 0, "1-10MB": 1, "10-100MB": 2, "100MB-1GB": 3, "1GB+": 4, "unknown": 5}
    return order.get(item[0], 99)


def prepare_summary_for_json(analysis: dict[str, Any], provider_names: dict[str, str]) -> dict[str, Any]:
    """
    Prepare analysis summary for JSON output.

    Args:
        analysis: Analysis results from analyze_retrieval_data
        provider_names: Mapping of provider IDs to names

    Returns:
        JSON-serializable summary dictionary
    """
    any_error = analysis["records_with_any_error"]
    all_failed = analysis["records_all_providers_failed"]

    # Build provider breakdown with names
    provider_breakdown = {}
    for provider_id, count in any_error["by_provider"].items():
        name = provider_names.get(provider_id, provider_id)
        provider_breakdown[provider_id] = {
            "name": name,
            "error_count": count,
        }

    return {
        "input_file": analysis["input_file"],
        "scope": analysis["scope"],
        "total_records_scanned": analysis["total_records_scanned"],
        "records_with_active_deals": analysis["records_with_active_deals"],
        "records_with_any_error": {
            "count": any_error["count"],
            "percentage": any_error["percentage"],
            "by_status_code": any_error["by_status_code"],
            "by_provider": provider_breakdown,
        },
        "records_all_providers_failed": {
            "count": all_failed["count"],
            "percentage": all_failed["percentage"],
            "by_status_code": all_failed["by_status_code"],
            "by_preparation": all_failed["by_preparation"],
            "by_filetype": all_failed["by_filetype"],
            "by_filesize": all_failed["by_filesize"],
        },
    }


def print_summary(analysis: dict[str, Any], provider_names: dict[str, str]) -> None:
    """Print and log a formatted summary of the analysis."""
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("RETRIEVAL FAILURE ANALYSIS")
    lines.append("=" * 70)
    lines.append(f"Scope: {analysis['scope']}")
    lines.append(f"Total records scanned: {analysis['total_records_scanned']:,}")
    lines.append(f"Records with active deals: {analysis['records_with_active_deals']:,}")

    # Section 1: Any errors (non-2xx status)
    any_error = analysis["records_with_any_error"]
    lines.append("\n" + "-" * 70)
    lines.append("1. CIDs with ANY active-deal provider returning an error (non-2xx)")
    lines.append("-" * 70)
    lines.append(f"   Count: {any_error['count']:,} ({any_error['percentage']}% of active-deal CIDs)")

    lines.append("\n   By Status Code:")
    for status, count in any_error["by_status_code"].items():
        lines.append(f"      HTTP {status}: {count:,}")

    lines.append("\n   By Provider:")
    for provider_id, count in sorted(any_error["by_provider"].items()):
        name = provider_names.get(provider_id, provider_id)
        lines.append(f"      {name} ({provider_id}): {count:,}")

    # Section 2: All providers failed
    all_failed = analysis["records_all_providers_failed"]
    lines.append("\n" + "-" * 70)
    lines.append("2. CIDs where ALL active-deal providers FAILED retrieval")
    lines.append("-" * 70)
    lines.append(f"   Count: {all_failed['count']:,} ({all_failed['percentage']}% of active-deal CIDs)")

    lines.append("\n   By Status Code:")
    for status, count in all_failed["by_status_code"].items():
        lines.append(f"      HTTP {status}: {count:,}")

    lines.append("\n   By Preparation:")
    for prep, count in sorted(all_failed["by_preparation"].items()):
        lines.append(f"      Prep {prep}: {count:,}")

    lines.append("\n   By Filetype:")
    for filetype, count in all_failed["by_filetype"].items():
        lines.append(f"      {filetype}: {count:,}")

    lines.append("\n   By Filesize:")
    for bucket, count in all_failed["by_filesize"].items():
        lines.append(f"      {bucket}: {count:,}")

    lines.append("=" * 70)

    # Output to both console and log file (same clean format)
    output = "\n".join(lines)
    print(output)
    write_to_log_file(output)


def main() -> int:
    """Main entry point for the script."""
    logger.info("Starting CID error extraction analysis")

    # Load config
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Analyze CIDs with retrieval failures (any non-2xx status or all providers failed)."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="Input JSON file path. Defaults to config cid_status_postprocessed_file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path for CIDs with errors.",
    )
    parser.add_argument(
        "--output-all-failed",
        type=Path,
        default=None,
        help="Output JSON file path for CIDs where all providers failed.",
    )
    parser.add_argument(
        "--summary-only",
        "-s",
        action="store_true",
        help="Only print summary, don't write output files.",
    )
    parser.add_argument(
        "--include-non-active",
        action="store_true",
        help="Include providers without active deals in analysis. Default: active deals only.",
    )

    args = parser.parse_args()

    # Resolve paths: CLI override > config value
    input_path = args.input or get_file_path(config, "cid_status_postprocessed_filename")

    # Validate input exists
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    # Get provider names from config
    storage_providers = get_storage_providers(config)
    provider_names = {pid: pdata.get("name", pid) for pid, pdata in storage_providers.items()}

    # Analyze data
    analysis = analyze_retrieval_data(input_path, include_non_active=args.include_non_active)

    # Print summary
    print_summary(analysis, provider_names)

    # Write output files if not summary-only
    if not args.summary_only:
        # Ensure error-analysis directory exists
        error_analysis_dir = get_path(config, "error_analysis_dir")
        error_analysis_dir.mkdir(parents=True, exist_ok=True)

        # Output summary JSON
        summary_path = get_file_path(config, "cid_errors_summary_filename")
        summary_json = prepare_summary_for_json(analysis, provider_names)
        logger.info(f"Writing summary to: {summary_path}")
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary_json, f, indent=2)

        # Output for errors
        output_path = args.output or get_file_path(config, "cid_errors_filename")
        records_with_errors = analysis["_records_with_errors"]
        logger.info(f"Writing {len(records_with_errors):,} records with errors to: {output_path}")
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(records_with_errors, f, indent=2)

        # Output for all-failed
        output_all_failed = args.output_all_failed or get_file_path(config, "cid_all_failed_filename")
        records_all_failed = analysis["_records_all_failed"]
        logger.info(f"Writing {len(records_all_failed):,} records where all providers failed to: {output_all_failed}")
        with output_all_failed.open("w", encoding="utf-8") as f:
            json.dump(records_all_failed, f, indent=2)

    logger.info("Analysis complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
