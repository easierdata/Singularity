#!/usr/bin/env python3
"""
Summary Report Generator for Filecoin Retrieval Checks

Reads post-processed retrieval status files and deals.json, computes summary
statistics, and outputs a structured JSON file for downstream consumption.

Output JSON Structure:
{
    "metadata": {
        "generated_at": "<ISO timestamp>",
        "input_files": { ... }
    },
    "overall_retrieval": {
        "counts": { ... },
        "piece_outcomes": { ... },
        "cid_outcomes": { ... },
        "unique_metrics": { ... },
        "by_filetype": { ... },
        "by_filesize_bucket": { ... },
        "non_active_deals": { ... }
    },
    "by_preparation": {
        "<prep_id>": {
            "piece_metrics": { ... },
            "cid_metrics": { ... },
            "by_filetype": { ... },
            "by_filesize_bucket": { ... },
            "non_active_deals": { ... }
        }
    },
    "by_storage_provider": {
        "<provider_id>": {
            "providerid": "<provider_id>",
            "providername": "<name>",
            "piece_metrics": { ... },
            "cid_metrics": { ... },
            "by_filetype": { ... },
            "by_filesize_bucket": { ... },
            "non_active_deals": { ... }
        }
    },
    "prepared_content": {
        "overall": {
            "cid_metrics": {
                "total_files": int,
                "unique_cids": int,
                "retrievable_by_any_provider": int,
                "retrievable_by_all_providers": int,
                "not_retrievable_by_any_provider": int,
                "not_in_any_active_deals": int,
                "by_provider": { "<provider_id>": { ... } }
            },
            "piece_metrics": {
                "total_pieces": int,
                "unique_piece_cids": int,
                "retrievable_by_any_provider": int,
                "retrievable_by_all_providers": int,
                "not_retrievable_by_any_provider": int,
                "not_in_any_active_deals": int,
                "by_provider": { "<provider_id>": { ... } }
            }
        },
        "by_preparation": {
            "<prep_id>": {
                "cid_metrics": { "source_file": ..., "total_files": ..., ... },
                "piece_metrics": { "source_file": ..., "total_pieces": ..., ... },
                "by_filetype": {
                    "<ext>": {
                        "unique_cids": int,
                        "by_provider": { "<provider_id>": { "retrievable": int, "not_retrievable": int, "not_in_deals": int } }
                    }
                },
                "by_filesize_bucket": {
                    "<bucket>": {
                        "unique_cids": int,
                        "by_provider": { "<provider_id>": { "retrievable": int, "not_retrievable": int, "not_in_deals": int } }
                    }
                }
            }
        },
        "providers": { "<provider_id>": "<provider_name>", ... }
    },
    "error_analysis": {
        "scope": "active_deals_only",
        "overview": {
            "total_500_errors": int,
            "cids_with_any_500_error": int,
            "cids_all_providers_failed": int,
            "percentage_of_active_deal_cids": float
        },
        "by_provider": {
            "<provider_id>": {
                "provider_name": str,
                "total_500_errors": int,
                "categories": { "<category>": int, ... },
                "top_patterns": [ { "pattern": str, "count": int, "percentage": float }, ... ]
            }
        },
        "by_preparation": {
            "<prep_id>": { "total_500_errors": int, "categories": { ... } }
        },
        "cross_provider_analysis": {
            "cids_with_deals_on_both_providers": int,
            "both_fail": int,
            "milad_only_fail": int,
            "decent_only_fail": int,
            "both_fail_characteristics": {
                "top_category_combinations": [ ... ],
                "by_preparation": { ... },
                "by_filetype": { ... },
                "by_filesize_bucket": { ... }
            }
        },
        "file_characteristics_by_category": {
            "<category>": {
                "total_errors": int,
                "by_filetype": { ... },
                "by_filesize_bucket": { ... }
            }
        }
    }
}

Note on CID deduplication: When the same CID appears multiple times in a preparation
(potentially with different filenames/extensions), we use "FIRST ONE IN" strategy -
the first occurrence's filetype and size are used for that CID's metrics. This is
deterministic and matches typical deduplication behavior.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import get_file_path, get_path, get_storage_providers, load_config

# Import from the summary_report package
from summary_report import (
    build_active_deals_set,
    build_retrieval_lookups,
    collect_cid_info_from_metadata,
    collect_piece_info_from_metadata,
    compute_error_analysis,
    compute_filesize_breakdown,
    compute_filetype_breakdown,
    compute_outcome_metrics,
    compute_per_provider_counts,
    compute_prep_filesize_breakdown,
    compute_prep_filetype_breakdown,
    compute_preparation_metrics,
    compute_provider_metrics,
    compute_retrievability_counts,
    compute_unique_metrics,
    extract_retrieval_checks,
    load_file_metadata_csvs,
    load_json_file,
    load_piece_metadata_jsons,
)


def compute_prepared_content_metrics(
    file_metadata: Dict[str, Dict[str, Any]],
    piece_metadata: Dict[str, Dict[str, Any]],
    cid_active: List[Dict],
    cid_non_active: List[Dict],
    piece_active: List[Dict],
    piece_non_active: List[Dict],
    active_deals: Set[Tuple[str, str]],
) -> Dict[str, Any]:
    """Compute comprehensive prepared content metrics from file-metadata CSVs and piece-metadata JSONs.

    Traces from original prepared files and pieces (source of truth) through to retrieval status,
    computing per-preparation and per-provider retrievability metrics at both CID and piece level.
    """
    if not file_metadata and not piece_metadata:
        return {"error": "No file-metadata CSVs or piece-metadata JSONs found"}

    # Build all lookup structures from retrieval check data
    lookups = build_retrieval_lookups(cid_active, cid_non_active, piece_active, piece_non_active)
    sorted_providers = lookups.sorted_providers

    # Collect CID info from file-metadata
    overall_total_files = 0
    overall_unique_cids: Set[str] = set()
    all_cids_retrievability: Dict[str, Dict[str, Any]] = {}

    if file_metadata:
        (
            overall_total_files,
            overall_unique_cids,
            all_cids_retrievability,
            _,  # all_cids_attributes - not used at overall level
        ) = collect_cid_info_from_metadata(
            file_metadata,
            lookups.cid_active_providers,
            lookups.cid_retrieval_results,
        )

    # Collect piece info from piece-metadata
    overall_total_pieces = 0
    overall_unique_piece_cids: Set[str] = set()
    all_pieces_retrievability: Dict[str, Dict[str, Any]] = {}

    if piece_metadata:
        (
            overall_total_pieces,
            overall_unique_piece_cids,
            all_pieces_retrievability,
        ) = collect_piece_info_from_metadata(
            piece_metadata,
            lookups.piece_active_providers,
            lookups.piece_retrieval_results,
        )

    # Compute overall CID retrievability counts
    cid_counts = compute_retrievability_counts(overall_unique_cids, all_cids_retrievability)

    # Compute overall piece retrievability counts
    piece_counts = compute_retrievability_counts(overall_unique_piece_cids, all_pieces_retrievability)

    # Compute per-provider overall metrics
    overall_cid_per_provider = compute_per_provider_counts(
        overall_unique_cids, all_cids_retrievability, lookups.provider_names, sorted_providers
    )
    overall_piece_per_provider = compute_per_provider_counts(
        overall_unique_piece_cids, all_pieces_retrievability, lookups.provider_names, sorted_providers
    )

    # Compute per-preparation metrics
    by_preparation = _compute_all_preparation_metrics(
        file_metadata,
        piece_metadata,
        all_cids_retrievability,
        all_pieces_retrievability,
        lookups.provider_names,
        sorted_providers,
    )

    return {
        "overall": {
            "cid_metrics": {
                "total_files": overall_total_files,
                "unique_cids": len(overall_unique_cids),
                "retrievable_by_any_provider": cid_counts.retrievable_by_any,
                "retrievable_by_all_providers": cid_counts.retrievable_by_all,
                "not_retrievable_by_any_provider": cid_counts.not_retrievable_by_any,
                "not_in_any_active_deals": cid_counts.not_in_any_active_deals,
                "by_provider": overall_cid_per_provider,
            },
            "piece_metrics": {
                "total_pieces": overall_total_pieces,
                "unique_piece_cids": len(overall_unique_piece_cids),
                "retrievable_by_any_provider": piece_counts.retrievable_by_any,
                "retrievable_by_all_providers": piece_counts.retrievable_by_all,
                "not_retrievable_by_any_provider": piece_counts.not_retrievable_by_any,
                "not_in_any_active_deals": piece_counts.not_in_any_active_deals,
                "by_provider": overall_piece_per_provider,
            },
        },
        "by_preparation": by_preparation,
        "providers": {p: lookups.provider_names.get(p, "") for p in sorted_providers},
    }


def _compute_all_preparation_metrics(
    file_metadata: Optional[Dict[str, Dict[str, Any]]],
    piece_metadata: Optional[Dict[str, Dict[str, Any]]],
    cids_retrievability: Dict[str, Dict[str, Any]],
    pieces_retrievability: Dict[str, Dict[str, Any]],
    provider_names: Dict[str, str],
    sorted_providers: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Compute metrics for all preparations.

    Args:
        file_metadata: Dict mapping prep_id -> file metadata
        piece_metadata: Dict mapping prep_id -> piece metadata
        cids_retrievability: Dict mapping cid -> retrieval info
        pieces_retrievability: Dict mapping pieceCid -> retrieval info
        provider_names: Dict mapping provider_id -> provider_name
        sorted_providers: Sorted list of all provider IDs

    Returns:
        Dict mapping prep_id -> preparation metrics
    """
    # Get all prep IDs from both file and piece metadata
    all_prep_ids: Set[str] = set()
    if file_metadata:
        all_prep_ids.update(file_metadata.keys())
    if piece_metadata:
        all_prep_ids.update(piece_metadata.keys())

    result = {}
    for prep_id in sorted(all_prep_ids, key=lambda x: int(x)):
        file_prep_data = file_metadata.get(prep_id, {}) if file_metadata else {}
        piece_prep_data = piece_metadata.get(prep_id, {}) if piece_metadata else {}

        result[prep_id] = _compute_single_preparation_metrics(
            file_prep_data,
            piece_prep_data,
            cids_retrievability,
            pieces_retrievability,
            provider_names,
            sorted_providers,
        )

    return result


def _compute_single_preparation_metrics(
    file_prep_data: Dict[str, Any],
    piece_prep_data: Dict[str, Any],
    cids_retrievability: Dict[str, Dict[str, Any]],
    pieces_retrievability: Dict[str, Dict[str, Any]],
    provider_names: Dict[str, str],
    sorted_providers: List[str],
) -> Dict[str, Any]:
    """Compute metrics for a single preparation.

    Args:
        file_prep_data: File metadata for this prep (or empty dict)
        piece_prep_data: Piece metadata for this prep (or empty dict)
        cids_retrievability: Dict mapping cid -> retrieval info
        pieces_retrievability: Dict mapping pieceCid -> retrieval info
        provider_names: Dict mapping provider_id -> provider_name
        sorted_providers: Sorted list of all provider IDs

    Returns:
        Dict with cid_metrics, piece_metrics, by_filetype, by_filesize_bucket
    """
    # CID-level metrics
    unique_cids = file_prep_data.get("unique_cids", set())
    cid_counts = compute_retrievability_counts(unique_cids, cids_retrievability)
    cid_per_provider = compute_per_provider_counts(
        unique_cids, cids_retrievability, provider_names, sorted_providers
    )

    # Piece-level metrics
    unique_piece_cids = piece_prep_data.get("unique_piece_cids", set())
    piece_counts = compute_retrievability_counts(unique_piece_cids, pieces_retrievability)
    piece_per_provider = compute_per_provider_counts(
        unique_piece_cids, pieces_retrievability, provider_names, sorted_providers
    )

    # Filetype and filesize breakdowns
    prep_cid_attributes = file_prep_data.get("cid_attributes", {})
    filetype_breakdown = compute_prep_filetype_breakdown(
        unique_cids, prep_cid_attributes, cids_retrievability, provider_names, sorted_providers
    )
    filesize_breakdown = compute_prep_filesize_breakdown(
        unique_cids, prep_cid_attributes, cids_retrievability, provider_names, sorted_providers
    )

    return {
        "cid_metrics": {
            "source_file": file_prep_data.get("filename", ""),
            "total_files": file_prep_data.get("total_files", 0),
            "unique_cids": len(unique_cids),
            "retrievable_by_any_provider": cid_counts.retrievable_by_any,
            "retrievable_by_all_providers": cid_counts.retrievable_by_all,
            "not_retrievable_by_any_provider": cid_counts.not_retrievable_by_any,
            "not_in_any_active_deals": cid_counts.not_in_any_active_deals,
            "by_provider": cid_per_provider,
        },
        "piece_metrics": {
            "source_file": piece_prep_data.get("filename", ""),
            "total_pieces": piece_prep_data.get("total_pieces", 0),
            "unique_piece_cids": len(unique_piece_cids),
            "retrievable_by_any_provider": piece_counts.retrievable_by_any,
            "retrievable_by_all_providers": piece_counts.retrievable_by_all,
            "not_retrievable_by_any_provider": piece_counts.not_retrievable_by_any,
            "not_in_any_active_deals": piece_counts.not_in_any_active_deals,
            "by_provider": piece_per_provider,
        },
        "by_filetype": filetype_breakdown,
        "by_filesize_bucket": filesize_breakdown,
    }


def generate_summary_report(
    piece_status_path: Path,
    cid_status_path: Path,
    deals_path: Path,
    file_metadata_dir: Optional[Path] = None,
    piece_metadata_dir: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate the complete summary report."""
    # Load config if not provided
    if config is None:
        config = load_config()

    # Build provider_names from config for error analysis
    storage_providers = get_storage_providers(config)
    provider_names = {pid: info.get("name", pid) for pid, info in storage_providers.items()}

    # Load input files
    print(f"Loading piece status from: {piece_status_path}")
    piece_data = load_json_file(piece_status_path)

    print(f"Loading CID status from: {cid_status_path}")
    cid_data = load_json_file(cid_status_path)

    print(f"Loading deals from: {deals_path}")
    deals_data = load_json_file(deals_path)

    # Build active deals set
    active_deals = build_active_deals_set(deals_data)
    print(f"Found {len(active_deals)} active (pieceCid, provider) combinations")

    # Extract retrieval checks
    print("Processing piece retrieval checks...")
    piece_active, piece_non_active = extract_retrieval_checks(piece_data, active_deals, "piece")

    print("Processing CID retrieval checks...")
    cid_active, cid_non_active = extract_retrieval_checks(cid_data, active_deals, "cid")

    print(f"Active piece checks: {len(piece_active)}, Non-active: {len(piece_non_active)}")
    print(f"Active CID checks: {len(cid_active)}, Non-active: {len(cid_non_active)}")

    # Compute overall metrics
    unique_pieces = {c.get("pieceCid") for c in piece_active if c.get("pieceCid")}
    unique_cids = {c.get("cid") for c in cid_active if c.get("cid")}

    piece_outcomes = compute_outcome_metrics(piece_active)
    cid_outcomes = compute_outcome_metrics(cid_active)

    piece_unique = compute_unique_metrics(piece_active, "pieceCid", active_deals)
    cid_unique = compute_unique_metrics(cid_active, "cid", active_deals)

    # Non-active deals diagnostic
    non_active_pieces = {c.get("pieceCid") for c in piece_non_active if c.get("pieceCid")}
    non_active_cids = {c.get("cid") for c in cid_non_active if c.get("cid")}
    non_active_metrics = {
        "unique_pieces_not_in_active_deals": len(non_active_pieces),
        "unique_cids_not_in_active_deals": len(non_active_cids),
        "piece_retrieval_checks_not_in_active_deals": len(piece_non_active),
        "cid_retrieval_checks_not_in_active_deals": len(cid_non_active),
    }

    overall_retrieval = {
        "counts": {
            "total_unique_pieces_in_active_deals": len(unique_pieces),
            "total_unique_cids_in_active_deals": len(unique_cids),
            "total_piece_retrieval_checks": len(piece_active),
            "total_cid_retrieval_checks": len(cid_active),
        },
        "piece_outcomes": piece_outcomes,
        "cid_outcomes": cid_outcomes,
        "unique_metrics": {
            "pieces": {
                "with_any_provider_success": piece_unique.get("unique_piececids_with_any_provider_success", 0),
                "all_providers_success": piece_unique.get("unique_piececids_all_providers_success", 0),
                "all_providers_failed": piece_unique.get("unique_piececids_all_providers_failed", 0),
            },
            "cids": {
                "with_any_provider_success": cid_unique.get("unique_cids_with_any_provider_success", 0),
                "all_providers_success": cid_unique.get("unique_cids_all_providers_success", 0),
                "all_providers_failed": cid_unique.get("unique_cids_all_providers_failed", 0),
            },
        },
        "by_filetype": compute_filetype_breakdown(cid_active),
        "by_filesize_bucket": compute_filesize_breakdown(cid_active),
        "non_active_deals": non_active_metrics,
    }

    # By preparation
    by_preparation = compute_preparation_metrics(
        piece_active, cid_active, active_deals, piece_non_active, cid_non_active
    )

    # By storage provider
    by_storage_provider = compute_provider_metrics(
        piece_active, cid_active, piece_non_active, cid_non_active
    )

    # Load file-metadata CSVs and piece-metadata JSONs if directories exist
    prepared_content = None
    file_metadata = {}
    piece_metadata = {}

    if file_metadata_dir and file_metadata_dir.exists():
        print(f"\nLoading file-metadata CSVs from: {file_metadata_dir}")
        file_metadata = load_file_metadata_csvs(file_metadata_dir)

    if piece_metadata_dir and piece_metadata_dir.exists():
        print(f"Loading piece-metadata JSONs from: {piece_metadata_dir}")
        piece_metadata = load_piece_metadata_jsons(piece_metadata_dir)

    if file_metadata or piece_metadata:
        print("Computing prepared content metrics...")
        prepared_content = compute_prepared_content_metrics(
            file_metadata,
            piece_metadata,
            cid_active,
            cid_non_active,
            piece_active,
            piece_non_active,
            active_deals,
        )

    # Compute error analysis from raw CID data
    print("Computing error analysis...")
    error_analysis = compute_error_analysis(cid_data, provider_names)

    # Build final report
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_files": {
                "piece_status": str(piece_status_path),
                "cid_status": str(cid_status_path),
                "deals": str(deals_path),
                "file_metadata_dir": str(file_metadata_dir) if file_metadata_dir else None,
                "piece_metadata_dir": str(piece_metadata_dir) if piece_metadata_dir else None,
            },
            "active_deals_count": len(active_deals),
        },
        "overall_retrieval": overall_retrieval,
        "by_preparation": by_preparation,
        "by_storage_provider": by_storage_provider,
    }

    # Add prepared content section if computed
    if prepared_content:
        report["prepared_content"] = prepared_content

    # Add error analysis section
    if error_analysis:
        report["error_analysis"] = error_analysis

    return report


def main() -> None:
    """Main entry point."""
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Generate summary report from Filecoin retrieval check results."
    )
    parser.add_argument(
        "--piece-status",
        type=Path,
        default=None,
        help="Path to final_retrieval_piece_status_postprocessed.json",
    )
    parser.add_argument(
        "--cid-status",
        type=Path,
        default=None,
        help="Path to final_retrieval_cid_status_postprocessed.json",
    )
    parser.add_argument(
        "--deals",
        type=Path,
        default=None,
        help="Path to deals.json",
    )
    parser.add_argument(
        "--file-metadata",
        type=Path,
        default=None,
        help="Path to directory containing file-metadata CSVs (e.g., GEDI02_B_prep1_details.csv)",
    )
    parser.add_argument(
        "--piece-metadata",
        type=Path,
        default=None,
        help="Path to directory containing piece-metadata JSONs (e.g., GEDI02_B_prep1_details.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Path to output summary JSON file",
    )

    args = parser.parse_args()

    # Apply config defaults where args not provided
    piece_status = args.piece_status or get_file_path(config, "piece_status_postprocessed_filename")
    cid_status = args.cid_status or get_file_path(config, "cid_status_postprocessed_filename")
    deals = args.deals or get_file_path(config, "deals_filename")
    file_metadata_dir = args.file_metadata or get_path(config, "file_metadata_dir")
    piece_metadata_dir = args.piece_metadata or get_path(config, "piece_metadata_dir")
    out_path = args.out or get_file_path(config, "summary_report_filename")

    # Validate input files exist
    for path, name in [
        (piece_status, "piece-status"),
        (cid_status, "cid-status"),
        (deals, "deals"),
    ]:
        if not path.exists():
            print(f"Error: {name} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Generate report
    report = generate_summary_report(
        piece_status_path=piece_status,
        cid_status_path=cid_status,
        deals_path=deals,
        file_metadata_dir=file_metadata_dir,
        piece_metadata_dir=piece_metadata_dir,
        config=config,
    )

    # Ensure output directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    print(f"Writing summary report to: {out_path}")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Done!")

    # Print quick summary to console
    overall = report["overall_retrieval"]
    print("\n=== Quick Summary ===")
    print(f"Unique pieces in active deals: {overall['counts']['total_unique_pieces_in_active_deals']}")
    print(f"Unique CIDs in active deals: {overall['counts']['total_unique_cids_in_active_deals']}")
    print(f"Piece retrieval success rate: {overall['piece_outcomes']['success_rate']}")
    print(f"CID retrieval success rate: {overall['cid_outcomes']['success_rate']}")

    # Print prepared content summary if available
    if "prepared_content" in report:
        pc = report["prepared_content"]["overall"]
        cid_m = pc["cid_metrics"]
        piece_m = pc["piece_metrics"]
        print("\n=== Prepared Content Summary ===")
        print("CID-level metrics:")
        print(f"  Total files prepared: {cid_m['total_files']}")
        print(f"  Unique CIDs prepared: {cid_m['unique_cids']}")
        print(f"  Retrievable by at least one provider: {cid_m['retrievable_by_any_provider']}")
        print(f"  Retrievable by all providers: {cid_m['retrievable_by_all_providers']}")
        print(f"  Not retrievable by any provider: {cid_m['not_retrievable_by_any_provider']}")
        print(f"  Not in any active deals: {cid_m['not_in_any_active_deals']}")
        print("Piece-level metrics:")
        print(f"  Total pieces prepared: {piece_m['total_pieces']}")
        print(f"  Unique pieceCids prepared: {piece_m['unique_piece_cids']}")
        print(f"  Retrievable by at least one provider: {piece_m['retrievable_by_any_provider']}")
        print(f"  Retrievable by all providers: {piece_m['retrievable_by_all_providers']}")
        print(f"  Not retrievable by any provider: {piece_m['not_retrievable_by_any_provider']}")
        print(f"  Not in any active deals: {piece_m['not_in_any_active_deals']}")


if __name__ == "__main__":
    main()
