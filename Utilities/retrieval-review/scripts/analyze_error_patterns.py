#!/usr/bin/env python3
"""
Analyze error patterns from retrieval failures.

This script examines response_body messages from failed retrievals to identify
common error patterns and categories.

Usage:
    python analyze_error_patterns.py [--input INPUT_FILE] [--summary-only]
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from config import get_file_path, get_path, get_storage_providers, load_config


def extract_error_pattern(response_body: str | None) -> str:
    """
    Extract a normalized error pattern from the response body.

    Replaces dynamic values (CIDs, multihashes) with placeholders to group similar errors.
    """
    if not response_body:
        return "<no response body>"

    # Normalize the error message by replacing dynamic parts
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


def categorize_error(response_body: str | None, error_message: str | None) -> str:
    """Categorize an error into a high-level category."""
    if not response_body and not error_message:
        return "unknown"

    text = (response_body or "") + " " + (error_message or "")
    text_lower = text.lower()

    # Categorize based on keywords
    if "not found" in text_lower:
        if "multihash" in text_lower:
            return "multihash_not_found"
        elif "piece" in text_lower:
            return "piece_not_found"
        elif "cid" in text_lower:
            return "cid_not_found"
        else:
            return "not_found_other"
    elif "timeout" in text_lower:
        return "timeout"
    elif "connection" in text_lower:
        return "connection_error"
    elif "failed to load root" in text_lower:
        return "root_load_failure"
    elif "ipld" in text_lower:
        return "ipld_error"
    elif "could not find node" in text_lower:
        return "node_not_found"
    else:
        return "other"


def get_file_extension(file_name: str | None) -> str:
    """Extract file extension from filename."""
    if not file_name:
        return "<no filename>"
    parts = file_name.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 10:
        return f".{parts[1].lower()}"
    return "<no extension>"


def get_size_bucket(file_size: int | None) -> str:
    """Categorize file size into buckets."""
    if file_size is None:
        return "<unknown size>"
    if file_size < 1024:
        return "< 1 KB"
    if file_size < 1024 * 1024:
        return "1 KB - 1 MB"
    if file_size < 10 * 1024 * 1024:
        return "1 MB - 10 MB"
    if file_size < 100 * 1024 * 1024:
        return "10 MB - 100 MB"
    if file_size < 1024 * 1024 * 1024:
        return "100 MB - 1 GB"
    return "> 1 GB"


def analyze_errors(
    input_path: Path,
    provider_ids: list[str],
    provider_filter: str | None = None,
) -> dict[str, Any]:
    """
    Analyze error patterns from retrieval data.

    Args:
        input_path: Path to input JSON file
        provider_ids: List of provider IDs from config
        provider_filter: Optional provider ID to filter by

    Returns:
        Analysis results dictionary
    """
    print(f"Reading from: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected input to be a JSON array")

    # Track providers found in data but not in config
    unknown_providers: set[str] = set()

    # Initialize tracking dicts dynamically from config
    patterns_by_provider: dict[str, Counter] = {pid: Counter() for pid in provider_ids}
    categories_by_provider: dict[str, Counter] = {pid: Counter() for pid in provider_ids}
    sample_errors_by_pattern: dict[str, dict[str, list]] = {pid: {} for pid in provider_ids}

    # Track by preparation
    patterns_by_prep: dict[str, Counter] = {}
    categories_by_prep: dict[str, Counter] = {}

    # Cross-provider failure tracking (provider-agnostic)
    all_fail_cids: list[dict] = []  # CIDs where ALL active providers failed
    some_fail_cids: list[dict] = []  # CIDs where SOME (but not all) active providers failed

    # Track file characteristics by error category
    file_ext_by_category: dict[str, Counter] = {}
    file_size_by_category: dict[str, Counter] = {}
    file_size_by_category_raw: dict[str, list] = {}  # For calculating averages

    total_500_errors = 0

    for record in data:
        active_providers = set(record.get("active_deal_providers", []))
        checks = record.get("storage_provider_retrieval_check", {})
        prep = str(record.get("preparation", "unknown"))
        file_name = record.get("file_name")
        file_size = record.get("file_size")

        # Check failure status for each provider
        provider_failures: dict[str, bool] = {}
        provider_categories: dict[str, str] = {}

        for provider_id in active_providers:
            if provider_filter and provider_id != provider_filter:
                continue

            check = checks.get(provider_id, {})
            status_code = check.get("status_code")

            if status_code == 500:
                total_500_errors += 1
                response_body = check.get("response_body")
                error_message = check.get("error_message")

                # Extract pattern and category
                pattern = extract_error_pattern(response_body)
                category = categorize_error(response_body, error_message)

                provider_failures[provider_id] = True
                provider_categories[provider_id] = category

                # Ensure provider exists in tracking dicts (handles new providers in data)
                if provider_id not in patterns_by_provider:
                    patterns_by_provider[provider_id] = Counter()
                    categories_by_provider[provider_id] = Counter()
                    sample_errors_by_pattern[provider_id] = {}
                    # Track that this provider wasn't in config
                    if provider_id not in provider_ids:
                        unknown_providers.add(provider_id)

                # Track by provider
                patterns_by_provider[provider_id][pattern] += 1
                categories_by_provider[provider_id][category] += 1

                # Store sample errors (up to 3 per pattern per provider)
                if pattern not in sample_errors_by_pattern[provider_id]:
                    sample_errors_by_pattern[provider_id][pattern] = []
                if len(sample_errors_by_pattern[provider_id][pattern]) < 3:
                    sample_errors_by_pattern[provider_id][pattern].append({
                        "cid": record.get("cid"),
                        "pieceCid": record.get("pieceCid"),
                        "file_name": file_name,
                        "response_body": response_body,
                    })

                # Track by preparation
                if prep not in patterns_by_prep:
                    patterns_by_prep[prep] = Counter()
                    categories_by_prep[prep] = Counter()
                patterns_by_prep[prep][pattern] += 1
                categories_by_prep[prep][category] += 1

                # Track file characteristics by category
                if category not in file_ext_by_category:
                    file_ext_by_category[category] = Counter()
                    file_size_by_category[category] = Counter()
                    file_size_by_category_raw[category] = []
                file_ext_by_category[category][get_file_extension(file_name)] += 1
                file_size_by_category[category][get_size_bucket(file_size)] += 1
                if file_size is not None:
                    file_size_by_category_raw[category].append(file_size)
            else:
                provider_failures[provider_id] = False

        # Cross-provider analysis (only for CIDs with multiple active providers)
        if len(active_providers) >= 2:
            failed_providers = [p for p, failed in provider_failures.items() if failed]
            succeeded_providers = [p for p, failed in provider_failures.items() if not failed]

            if failed_providers:  # At least one failure
                record_info = {
                    "cid": record.get("cid"),
                    "pieceCid": record.get("pieceCid"),
                    "file_name": file_name,
                    "file_size": file_size,
                    "preparation": prep,
                    "failed_providers": failed_providers,
                    "succeeded_providers": succeeded_providers,
                    "failure_categories": {p: provider_categories.get(p) for p in failed_providers},
                }

                if len(succeeded_providers) == 0:
                    # All active providers failed
                    all_fail_cids.append(record_info)
                else:
                    # Some providers failed, some succeeded
                    some_fail_cids.append(record_info)

    return {
        "total_500_errors": total_500_errors,
        "patterns_by_provider": patterns_by_provider,
        "categories_by_provider": categories_by_provider,
        "sample_errors_by_pattern": sample_errors_by_pattern,
        "patterns_by_prep": patterns_by_prep,
        "categories_by_prep": categories_by_prep,
        # Cross-provider fields (provider-agnostic)
        "all_fail_cids": all_fail_cids,
        "some_fail_cids": some_fail_cids,
        "file_ext_by_category": file_ext_by_category,
        "file_size_by_category": file_size_by_category,
        "file_size_by_category_raw": file_size_by_category_raw,
        # Providers found in data but not in config
        "unknown_providers": unknown_providers,
    }


def print_analysis(analysis: dict[str, Any], top_n: int = 10, provider_names: dict[str, str] | None = None) -> None:
    """Print a formatted analysis of error patterns."""
    if provider_names is None:
        provider_names = {}

    print("\n" + "=" * 80)
    print("ERROR PATTERN ANALYSIS")
    print("=" * 80)
    print(f"Total 500 errors analyzed: {analysis['total_500_errors']:,}")

    # Categories by provider
    print("\n" + "-" * 80)
    print("ERROR CATEGORIES BY PROVIDER")
    print("-" * 80)

    for provider_id, categories in analysis["categories_by_provider"].items():
        if not categories:
            continue
        name = provider_names.get(provider_id, provider_id)
        total = sum(categories.values())
        print(f"\n{name} ({provider_id}): {total:,} errors")
        print("-" * 40)
        for category, count in categories.most_common():
            pct = count / total * 100 if total > 0 else 0
            print(f"  {category}: {count:,} ({pct:.1f}%)")

    # Top patterns by provider
    print("\n" + "-" * 80)
    print(f"TOP {top_n} ERROR PATTERNS BY PROVIDER")
    print("-" * 80)

    for provider_id, patterns in analysis["patterns_by_provider"].items():
        if not patterns:
            continue
        name = provider_names.get(provider_id, provider_id)
        total = sum(patterns.values())
        print(f"\n{name} ({provider_id}): {len(patterns)} unique patterns, {total:,} total errors")
        print("-" * 40)
        for i, (pattern, count) in enumerate(patterns.most_common(top_n), 1):
            pct = count / total * 100 if total > 0 else 0
            # Truncate long patterns
            display_pattern = pattern[:100] + "..." if len(pattern) > 100 else pattern
            print(f"  {i}. [{count:,} | {pct:.1f}%] {display_pattern}")

    # Categories by preparation
    print("\n" + "-" * 80)
    print("ERROR CATEGORIES BY PREPARATION")
    print("-" * 80)

    for prep in sorted(analysis["categories_by_prep"].keys()):
        categories = analysis["categories_by_prep"][prep]
        if not categories:
            continue
        total = sum(categories.values())
        print(f"\nPrep {prep}: {total:,} errors")
        for category, count in categories.most_common(5):
            pct = count / total * 100 if total > 0 else 0
            print(f"  {category}: {count:,} ({pct:.1f}%)")

    print("\n" + "=" * 80)


def print_sample_errors(
    analysis: dict[str, Any],
    provider_id: str,
    pattern_limit: int = 5,
    provider_names: dict[str, str] | None = None,
) -> None:
    """Print sample errors for each pattern."""
    if provider_names is None:
        provider_names = {}

    samples = analysis["sample_errors_by_pattern"].get(provider_id, {})
    name = provider_names.get(provider_id, provider_id)

    print(f"\n{'=' * 80}")
    print(f"SAMPLE ERRORS FOR {name} ({provider_id})")
    print("=" * 80)

    patterns = analysis["patterns_by_provider"].get(provider_id, Counter())

    for i, (pattern, count) in enumerate(patterns.most_common(pattern_limit), 1):
        print(f"\n--- Pattern {i}: {count:,} occurrences ---")
        print(f"Pattern: {pattern[:150]}{'...' if len(pattern) > 150 else ''}")

        if pattern in samples:
            print("\nSamples:")
            for j, sample in enumerate(samples[pattern], 1):
                print(f"\n  Sample {j}:")
                print(f"    CID: {sample['cid']}")
                print(f"    PieceCID: {sample['pieceCid']}")
                print(f"    File: {sample['file_name']}")
                if sample["response_body"]:
                    body = sample["response_body"][:200]
                    print(f"    Response: {body}{'...' if len(sample['response_body']) > 200 else ''}")


def print_cross_provider_analysis(analysis: dict[str, Any], provider_names: dict[str, str]) -> None:
    """Print cross-provider failure analysis."""
    all_fail = analysis.get("all_fail_cids", [])
    some_fail = analysis.get("some_fail_cids", [])

    print("\n" + "=" * 80)
    print("CROSS-PROVIDER FAILURE ANALYSIS")
    print("=" * 80)

    total = len(all_fail) + len(some_fail)
    print(f"\nCIDs with 2+ active providers and at least one 500 error: {total:,}")
    print(f"  All providers fail:   {len(all_fail):,}")
    print(f"  Some providers fail:  {len(some_fail):,}")

    # Analyze all-fail CIDs
    if all_fail:
        print("\n" + "-" * 80)
        print("ALL-PROVIDER FAILURES")
        print("-" * 80)

        # Category breakdown across all failed providers
        category_counter: Counter = Counter()
        for record in all_fail:
            for category in record.get("failure_categories", {}).values():
                if category:
                    category_counter[category] += 1

        print(f"\nTotal CIDs where all providers fail: {len(all_fail):,}")
        print("\nError categories (across all failed providers):")
        for category, count in category_counter.most_common(10):
            print(f"  {category}: {count:,}")

        # Prep breakdown
        prep_counter: Counter = Counter()
        for record in all_fail:
            prep_counter[record.get("preparation", "unknown")] += 1

        print("\nBy preparation:")
        for prep, count in sorted(prep_counter.items()):
            pct = count / len(all_fail) * 100
            print(f"  Prep {prep}: {count:,} ({pct:.1f}%)")

        # File characteristics
        _print_file_characteristics_for_records(all_fail, "All-Provider Failures")

    # Analyze some-fail CIDs (partial success)
    if some_fail:
        print("\n" + "-" * 80)
        print("PARTIAL FAILURES (some providers succeed, some fail)")
        print("-" * 80)

        print(f"\nTotal CIDs with partial failures: {len(some_fail):,}")

        # Which providers are failing vs succeeding?
        failed_provider_counter: Counter = Counter()
        succeeded_provider_counter: Counter = Counter()
        for record in some_fail:
            for p in record.get("failed_providers", []):
                name = provider_names.get(p, p)
                failed_provider_counter[f"{name} ({p})"] += 1
            for p in record.get("succeeded_providers", []):
                name = provider_names.get(p, p)
                succeeded_provider_counter[f"{name} ({p})"] += 1

        print("\nProviders that FAILED (when others succeeded):")
        for provider, count in failed_provider_counter.most_common():
            pct = count / len(some_fail) * 100
            print(f"  {provider}: {count:,} ({pct:.1f}%)")

        print("\nProviders that SUCCEEDED (when others failed):")
        for provider, count in succeeded_provider_counter.most_common():
            pct = count / len(some_fail) * 100
            print(f"  {provider}: {count:,} ({pct:.1f}%)")

        # Category breakdown for failed providers
        category_counter: Counter = Counter()
        for record in some_fail:
            for category in record.get("failure_categories", {}).values():
                if category:
                    category_counter[category] += 1

        print("\nError categories for failed providers:")
        for category, count in category_counter.most_common(10):
            print(f"  {category}: {count:,}")

        # Prep breakdown
        prep_counter: Counter = Counter()
        for record in some_fail:
            prep_counter[record.get("preparation", "unknown")] += 1

        print("\nBy preparation:")
        for prep, count in sorted(prep_counter.items()):
            pct = count / len(some_fail) * 100
            print(f"  Prep {prep}: {count:,} ({pct:.1f}%)")

        # File characteristics
        _print_file_characteristics_for_records(some_fail, "Partial Failures")


def _print_file_characteristics_for_records(records: list[dict], label: str) -> None:
    """Print file characteristics for a list of records."""
    if not records:
        return

    ext_counter: Counter = Counter()
    size_counter: Counter = Counter()
    raw_sizes: list[int] = []

    for record in records:
        ext_counter[get_file_extension(record.get("file_name"))] += 1
        size_counter[get_size_bucket(record.get("file_size"))] += 1
        if record.get("file_size") is not None:
            raw_sizes.append(record["file_size"])

    total = len(records)
    print(f"\n  FILE CHARACTERISTICS ({label}):")

    print("\n    File Extensions (top 5):")
    for ext, count in ext_counter.most_common(5):
        pct = count / total * 100
        print(f"      {ext}: {count:,} ({pct:.1f}%)")

    print("\n    File Size Distribution:")
    for size_bucket, count in size_counter.most_common():
        pct = count / total * 100
        print(f"      {size_bucket}: {count:,} ({pct:.1f}%)")

    if raw_sizes:
        avg_size = sum(raw_sizes) / len(raw_sizes)
        min_size = min(raw_sizes)
        max_size = max(raw_sizes)
        print("\n    Size Statistics:")
        print(f"      Min: {_format_bytes(min_size)}")
        print(f"      Max: {_format_bytes(max_size)}")
        print(f"      Avg: {_format_bytes(avg_size)}")


def print_file_characteristics(analysis: dict[str, Any]) -> None:
    """Print file characteristics analysis by error category."""
    file_ext_by_cat = analysis.get("file_ext_by_category", {})
    file_size_by_cat = analysis.get("file_size_by_category", {})
    file_size_raw = analysis.get("file_size_by_category_raw", {})

    print("\n" + "=" * 80)
    print("FILE CHARACTERISTICS BY ERROR CATEGORY")
    print("=" * 80)

    for category in sorted(file_ext_by_cat.keys()):
        ext_counts = file_ext_by_cat[category]
        size_counts = file_size_by_cat.get(category, Counter())
        raw_sizes = file_size_raw.get(category, [])

        total = sum(ext_counts.values())
        print(f"\n{'-' * 60}")
        print(f"Category: {category} ({total:,} errors)")
        print(f"{'-' * 60}")

        # File extensions
        print("\n  File Extensions (top 10):")
        for ext, count in ext_counts.most_common(10):
            pct = count / total * 100
            print(f"    {ext}: {count:,} ({pct:.1f}%)")

        # File sizes
        print("\n  File Size Distribution:")
        for size_bucket, count in size_counts.most_common():
            pct = count / total * 100
            print(f"    {size_bucket}: {count:,} ({pct:.1f}%)")

        # Size statistics
        if raw_sizes:
            avg_size = sum(raw_sizes) / len(raw_sizes)
            min_size = min(raw_sizes)
            max_size = max(raw_sizes)
            print("\n  Size Statistics:")
            print(f"    Min: {_format_bytes(min_size)}")
            print(f"    Max: {_format_bytes(max_size)}")
            print(f"    Avg: {_format_bytes(avg_size)}")


def _format_bytes(size: float) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def prepare_analysis_for_json(analysis: dict[str, Any], provider_names: dict[str, str]) -> dict[str, Any]:
    """
    Prepare analysis results for JSON serialization.

    Converts Counter objects to dicts and adds summary statistics.
    """
    # Convert Counters to regular dicts with sorted items
    def counter_to_dict(counter: Counter) -> dict[str, int]:
        return dict(counter.most_common())

    # Build provider summaries
    provider_summaries = {}
    for provider_id, patterns in analysis["patterns_by_provider"].items():
        name = provider_names.get(provider_id, provider_id)
        categories = analysis["categories_by_provider"].get(provider_id, Counter())
        provider_summaries[provider_id] = {
            "name": name,
            "total_errors": sum(patterns.values()),
            "unique_patterns": len(patterns),
            "categories": counter_to_dict(categories),
            "top_patterns": [
                {"pattern": p[:200], "count": c}
                for p, c in patterns.most_common(20)
            ],
        }

    # Build prep summaries
    prep_summaries = {}
    for prep, categories in analysis["categories_by_prep"].items():
        prep_summaries[prep] = {
            "total_errors": sum(categories.values()),
            "categories": counter_to_dict(categories),
        }

    # Cross-provider summary (provider-agnostic)
    all_fail = analysis.get("all_fail_cids", [])
    some_fail = analysis.get("some_fail_cids", [])

    # Build detailed cross-provider analysis
    # Sample CIDs are included for:
    #   - Spot-checking/debugging specific failures
    #   - Re-testing after fixes are deployed
    #   - Sharing with providers for diagnosis
    #   - Cross-referencing with other datasets
    cross_provider = {
        "all_providers_fail": {
            "count": len(all_fail),
            "cids": [record["cid"] for record in all_fail[:100]],  # Sample of first 100 CIDs
        },
        "some_providers_fail": {
            "count": len(some_fail),
            "cids": [record["cid"] for record in some_fail[:100]],  # Sample of first 100 CIDs
        },
    }

    # Add per-provider failure breakdown for partial failures
    if some_fail:
        failed_provider_counts: dict[str, int] = {}
        succeeded_provider_counts: dict[str, int] = {}
        for record in some_fail:
            for p in record.get("failed_providers", []):
                name = provider_names.get(p, p)
                failed_provider_counts[f"{name} ({p})"] = failed_provider_counts.get(f"{name} ({p})", 0) + 1
            for p in record.get("succeeded_providers", []):
                name = provider_names.get(p, p)
                succeeded_provider_counts[f"{name} ({p})"] = succeeded_provider_counts.get(f"{name} ({p})", 0) + 1
        cross_provider["some_providers_fail"]["providers_that_failed"] = failed_provider_counts
        cross_provider["some_providers_fail"]["providers_that_succeeded"] = succeeded_provider_counts

    # File characteristics summary
    file_characteristics = {}
    for category, ext_counts in analysis.get("file_ext_by_category", {}).items():
        size_counts = analysis.get("file_size_by_category", {}).get(category, Counter())
        raw_sizes = analysis.get("file_size_by_category_raw", {}).get(category, [])

        file_characteristics[category] = {
            "total_errors": sum(ext_counts.values()),
            "file_extensions": counter_to_dict(ext_counts),
            "size_distribution": counter_to_dict(size_counts),
        }
        if raw_sizes:
            file_characteristics[category]["size_stats"] = {
                "min_bytes": min(raw_sizes),
                "max_bytes": max(raw_sizes),
                "avg_bytes": sum(raw_sizes) / len(raw_sizes),
            }

    return {
        "total_500_errors": analysis["total_500_errors"],
        "by_provider": provider_summaries,
        "by_preparation": prep_summaries,
        "cross_provider_analysis": cross_provider,
        "file_characteristics_by_category": file_characteristics,
    }


def main() -> int:
    """Main entry point for the script."""
    # Load config
    config = load_config()
    storage_providers = get_storage_providers(config)
    provider_names = {pid: pdata.get("name", pid) for pid, pdata in storage_providers.items()}

    # Build provider choices dynamically from config
    provider_ids = list(storage_providers.keys())
    provider_aliases = [pdata.get("name", "").lower() for pdata in storage_providers.values()]
    valid_choices = provider_ids + [a for a in provider_aliases if a]

    parser = argparse.ArgumentParser(
        description="Analyze error patterns from retrieval failures."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="Input JSON file path. Defaults to config cid_status_postprocessed_file.",
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default=None,
        choices=valid_choices,
        help="Filter to specific provider (by ID or name).",
    )
    parser.add_argument(
        "--show-samples",
        "-s",
        action="store_true",
        help="Show sample errors for each pattern.",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=10,
        help="Number of top patterns to show (default: 10).",
    )
    parser.add_argument(
        "--cross-provider",
        "-x",
        action="store_true",
        help="Show cross-provider failure analysis.",
    )
    parser.add_argument(
        "--file-characteristics",
        "-f",
        action="store_true",
        help="Show file characteristics by error category.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path for analysis results. Defaults to config error_patterns_filename.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print summary stats to console only, don't save analysis to file.",
    )

    args = parser.parse_args()

    # Normalize provider filter (name -> ID)
    provider_filter = None
    if args.provider:
        # Build reverse map: lowercase name -> provider_id
        name_to_id = {pdata.get("name", "").lower(): pid for pid, pdata in storage_providers.items()}
        provider_filter = name_to_id.get(args.provider.lower(), args.provider)

    # Resolve paths: CLI override > config value
    input_path = args.input or get_file_path(config, "cid_status_postprocessed_filename")

    # Validate input exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    # Analyze data
    analysis = analyze_errors(input_path, provider_ids, provider_filter)

    # Note any providers found in data but not in config
    unknown_providers = analysis.get("unknown_providers", set())
    if unknown_providers:
        print(f"\nNote: {len(unknown_providers)} provider(s) found in data but not in config (using ID as name):")
        for pid in sorted(unknown_providers):
            print(f"  - {pid}")

    # Print analysis
    print_analysis(analysis, top_n=args.top, provider_names=provider_names)

    # Print cross-provider analysis if requested
    if args.cross_provider:
        print_cross_provider_analysis(analysis, provider_names)

    # Print file characteristics if requested
    if args.file_characteristics:
        print_file_characteristics(analysis)

    # Print samples if requested
    if args.show_samples:
        for provider_id in provider_ids:
            if provider_filter and provider_id != provider_filter:
                continue
            if analysis["patterns_by_provider"].get(provider_id):
                print_sample_errors(analysis, provider_id, pattern_limit=args.top, provider_names=provider_names)

    # Save analysis to file unless --summary-only is specified
    if not args.summary_only:
        # Ensure error-analysis directory exists
        error_analysis_dir = get_path(config, "error_analysis_dir")
        error_analysis_dir.mkdir(parents=True, exist_ok=True)

        output_path = args.output or get_file_path(config, "error_patterns_filename")
        json_output = prepare_analysis_for_json(analysis, provider_names)

        print(f"\nSaving analysis to: {output_path}")
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
