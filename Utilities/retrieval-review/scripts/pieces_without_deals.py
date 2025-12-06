#!/usr/bin/env python3
"""
Pieces Without Active Deals Report Generator

Generates a JSON report of all pieces that do not have active deals
with a specified storage provider, grouped by preparation.

Usage:
    python pieces_without_deals.py --storage-provider f02639429
    python pieces_without_deals.py --storage-provider f02639429 --preparation 1 2 3
    python pieces_without_deals.py --storage-provider f02639429 --output /path/to/output.json
    python pieces_without_deals.py --storage-provider f02639429 --list-only

Output JSON Structure (default):
{
    "metadata": {
        "generated_at": "<ISO timestamp>",
        "storage_provider": "<provider_id>",
        "preparations_requested": [<prep_ids>] or "all",
        "total_pieces_without_deals": <count>,
        "input_files": {
            "deals": "<path>",
            "piece_metadata_dir": "<path>"
        }
    },
    "by_preparation": {
        "<prep_id>": {
            "dataset_name": "<name>",
            "source_file": "<filename>",
            "total_pieces": <count>,
            "pieces_without_deals": <count>,
            "pieces": [
                {
                    "pieceCid": "<cid>",
                    "pieceSize": <bytes>,
                    "fileSize": <bytes>,
                    "numOfFiles": <count>,
                    "rootCid": "<cid>"
                },
                ...
            ]
        }
    },
    "summary": {
        "total_pieces_across_all_preps": <count>,
        "total_pieces_without_deals": <count>,
        "by_preparation": {
            "<prep_id>": {
                "total": <count>,
                "without_deals": <count>
            }
        }
    }
}

Output JSON Structure (--list-only):
{
    "metadata": {
        "generated_at": "<ISO timestamp>",
        "storage_provider": "<provider_id>",
        "preparations_requested": [<prep_ids>] or "all",
        "total_pieces_without_deals": <count>
    },
    "by_preparation": {
        "<prep_id>": ["<pieceCid1>", "<pieceCid2>", ...],
        ...
    }
}
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from config import get_file_path, get_path, load_config


def load_json_file(path: Path) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
    """Load a JSON file, returning None if file doesn't exist."""
    if not path.exists():
        print(f"Warning: File not found: {path}", file=sys.stderr)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_prep_id_from_filename(filename: str) -> Optional[str]:
    """Extract preparation ID from a piece metadata filename.

    Examples:
        GEDI02_B_prep1_details.json -> "1"
        GEDI_L4A_AGB_Density_V2_1_2056_prep7_details.json -> "7"
    """
    match = re.search(r"prep(\d+)", filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_dataset_name(filename: str) -> str:
    """Extract dataset name from a piece metadata filename.

    Examples:
        GEDI02_B_prep1_details.json -> "GEDI02_B"
        GEDI_L4A_AGB_Density_V2_1_2056_prep7_details.json -> "GEDI_L4A_AGB_Density_V2_1_2056"
    """
    # Remove _prepX_details.json suffix
    name = re.sub(r"_prep\d+_details\.json$", "", filename, flags=re.IGNORECASE)
    return name


def build_active_deals_set_for_provider(
    deals: List[Dict[str, Any]],
    provider_id: str
) -> Set[str]:
    """Build a set of pieceCids that have active deals with the specified provider.

    Args:
        deals: List of deal records from deals.json
        provider_id: Storage provider ID to filter by (e.g., "f02639429")

    Returns:
        Set of pieceCid strings that have active deals with the provider
    """
    active_pieces: Set[str] = set()
    for deal in deals:
        state = deal.get("state", "").lower()
        if state != "active":
            continue
        # Handle different field names for provider
        deal_provider = deal.get("provider") or deal.get("providerid") or deal.get("provider_id")
        if deal_provider != provider_id:
            continue
        piece_cid = deal.get("pieceCid")
        if piece_cid:
            active_pieces.add(piece_cid)
    return active_pieces



def load_piece_metadata(piece_metadata_dir: Path) -> Dict[str, Dict]:
    """Load all piece metadata files and organize by preparation ID.

    Returns:
        Dict mapping prep_id -> {
            "source_file": str,
            "dataset_name": str,
            "pieces": List[Dict]
        }
    """
    result = {}

    json_files = sorted(piece_metadata_dir.glob("*_details.json"))
    if not json_files:
        print(f"Warning: No piece metadata files found in {piece_metadata_dir}", file=sys.stderr)
        return result

    for json_path in json_files:
        prep_id = extract_prep_id_from_filename(json_path.name)
        if prep_id is None:
            print(f"Warning: Could not extract prep ID from {json_path.name}", file=sys.stderr)
            continue

        data = load_json_file(json_path)
        if data is None:
            continue

        # Extract pieces from the nested structure
        # Structure: [{"attachmentId": ..., "pieces": [...]}]
        all_pieces = []
        if isinstance(data, list):
            for attachment in data:
                pieces = attachment.get("pieces", [])
                all_pieces.extend(pieces)

        result[prep_id] = {
            "source_file": json_path.name,
            "dataset_name": extract_dataset_name(json_path.name),
            "pieces": all_pieces
        }

    return result


def filter_pieces_without_deals(
    pieces: List[Dict],
    active_piece_cids: Set[str]
) -> List[Dict]:
    """Filter pieces that do NOT have active deals.

    Args:
        pieces: List of piece records
        active_piece_cids: Set of pieceCids that have active deals

    Returns:
        List of piece records without active deals
    """
    pieces_without_deals = []
    for piece in pieces:
        piece_cid = piece.get("pieceCid")
        if piece_cid and piece_cid not in active_piece_cids:
            # Extract relevant fields for the output
            pieces_without_deals.append({
                "pieceCid": piece_cid,
                "pieceSize": piece.get("pieceSize"),
                "fileSize": piece.get("fileSize"),
                "numOfFiles": piece.get("numOfFiles"),
                "rootCid": piece.get("rootCid"),
            })
    return pieces_without_deals


def generate_report(
    piece_metadata_by_prep: Dict[str, Dict],
    active_piece_cids: Set[str],
    preparations: Optional[List[str]],
    storage_provider: str,
    deals_path: Path,
    piece_metadata_dir: Path,
) -> Dict[str, Any]:
    """Generate the pieces without deals report.

    Args:
        piece_metadata_by_prep: Dict of prep_id -> piece metadata
        active_piece_cids: Set of pieceCids with active deals for the provider
        preparations: List of prep IDs to include, or None for all
        storage_provider: The storage provider ID being analyzed
        deals_path: Path to deals.json
        piece_metadata_dir: Path to piece metadata directory

    Returns:
        Report dictionary
    """
    # Filter to requested preparations
    if preparations:
        prep_ids = [str(p) for p in preparations]
        filtered_preps = {k: v for k, v in piece_metadata_by_prep.items() if k in prep_ids}
        # Check for missing preps
        missing = set(prep_ids) - set(filtered_preps.keys())
        if missing:
            print(f"Warning: Requested preparations not found: {missing}", file=sys.stderr)
    else:
        filtered_preps = piece_metadata_by_prep
        prep_ids = "all"

    # Build report
    by_preparation = {}
    summary_by_prep = {}
    total_pieces = 0
    total_without_deals = 0

    for prep_id in sorted(filtered_preps.keys(), key=lambda x: int(x)):
        prep_data = filtered_preps[prep_id]
        all_pieces = prep_data["pieces"]
        pieces_without_deals = filter_pieces_without_deals(all_pieces, active_piece_cids)

        by_preparation[prep_id] = {
            "dataset_name": prep_data["dataset_name"],
            "source_file": prep_data["source_file"],
            "total_pieces": len(all_pieces),
            "pieces_without_deals": len(pieces_without_deals),
            "pieces": pieces_without_deals
        }

        summary_by_prep[prep_id] = {
            "total": len(all_pieces),
            "without_deals": len(pieces_without_deals)
        }

        total_pieces += len(all_pieces)
        total_without_deals += len(pieces_without_deals)

    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "storage_provider": storage_provider,
            "preparations_requested": prep_ids,
            "total_pieces_without_deals": total_without_deals,
            "input_files": {
                "deals": str(deals_path),
                "piece_metadata_dir": str(piece_metadata_dir)
            }
        },
        "by_preparation": by_preparation,
        "summary": {
            "total_pieces_across_all_preps": total_pieces,
            "total_pieces_without_deals": total_without_deals,
            "by_preparation": summary_by_prep
        }
    }

    return report


def generate_list_only_report(
    full_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a simplified report with just pieceCid lists.

    Args:
        full_report: The full report generated by generate_report()

    Returns:
        Simplified report with just pieceCid arrays per preparation
    """
    by_preparation_list: Dict[str, List[str]] = {}
    total_without_deals = 0

    for prep_id, prep_data in full_report["by_preparation"].items():
        piece_cids = [p["pieceCid"] for p in prep_data["pieces"]]
        by_preparation_list[prep_id] = piece_cids
        total_without_deals += len(piece_cids)

    return {
        "metadata": {
            "generated_at": full_report["metadata"]["generated_at"],
            "storage_provider": full_report["metadata"]["storage_provider"],
            "preparations_requested": full_report["metadata"]["preparations_requested"],
            "total_pieces_without_deals": total_without_deals
        },
        "by_preparation": by_preparation_list
    }



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a report of pieces without active deals for a storage provider.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # All preparations for a specific provider
    python pieces_without_deals.py --storage-provider f02639429

    # Specific preparations
    python pieces_without_deals.py --storage-provider f02639429 --preparation 1 2 3

    # Custom output path
    python pieces_without_deals.py --storage-provider f02639429 --output ./my_report.json

    # Custom input paths
    python pieces_without_deals.py --storage-provider f02639429 \\
        --deals ./data/deals.json \\
        --piece-metadata ./data/piece-metadata

    # List-only output (just pieceCids)
    python pieces_without_deals.py --storage-provider f02639429 --list-only
        """
    )

    parser.add_argument(
        "--storage-provider",
        required=True,
        help="Storage provider ID to check (e.g., f02639429). Required."
    )

    parser.add_argument(
        "--preparation", "-p",
        nargs="*",
        type=int,
        help="One or more preparation IDs to include (e.g., 1 2 3). Defaults to all preparations."
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output JSON file path. Defaults to output/pieces_without_deals_<provider>.json"
    )

    parser.add_argument(
        "--list-only", "-l",
        action="store_true",
        help="Output simplified format with just pieceCid arrays per preparation (for easy copy/paste)."
    )

    parser.add_argument(
        "--deals",
        type=Path,
        help="Path to deals.json. Defaults to output/deals.json"
    )

    parser.add_argument(
        "--piece-metadata",
        type=Path,
        help="Path to piece metadata directory. Defaults to output/piece-metadata"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config()

    # Set default paths from config, allow CLI overrides
    deals_path = args.deals or get_file_path(config, "deals_filename")
    piece_metadata_dir = args.piece_metadata or get_path(config, "piece_metadata_dir")
    output_dir = get_path(config, "output_dir")

    # Set default output path (dynamic filename based on provider)
    if args.output:
        output_path = args.output
    else:
        output_path = output_dir / f"pieces_without_deals_{args.storage_provider}.json"

    # Validate inputs
    if not deals_path.exists():
        print(f"Error: Deals file not found: {deals_path}", file=sys.stderr)
        sys.exit(1)

    if not piece_metadata_dir.exists():
        print(f"Error: Piece metadata directory not found: {piece_metadata_dir}", file=sys.stderr)
        sys.exit(1)
    # Load data
    print(f"Loading deals from {deals_path}...")
    deals_data = load_json_file(deals_path)
    if deals_data is None or not isinstance(deals_data, list):
        print("Error: Failed to load deals.json or invalid format", file=sys.stderr)
        sys.exit(1)
    deals: List[Dict[str, Any]] = deals_data

    print(f"Loading piece metadata from {piece_metadata_dir}...")
    piece_metadata_by_prep = load_piece_metadata(piece_metadata_dir)

    if not piece_metadata_by_prep:
        print("Error: No piece metadata loaded", file=sys.stderr)
        sys.exit(1)

    # Check if provider exists in deals data
    all_providers_in_deals: Set[str] = set()
    for deal in deals:
        if deal.get("state", "").lower() == "active":
            provider = deal.get("provider") or deal.get("providerid") or deal.get("provider_id")
            if provider:
                all_providers_in_deals.add(provider)

    if args.storage_provider not in all_providers_in_deals:
        print(f"Error: Storage provider '{args.storage_provider}' not found in deals.json", file=sys.stderr)
        print(f"Available providers with active deals: {sorted(all_providers_in_deals)}", file=sys.stderr)
        sys.exit(1)

    # Build set of pieceCids with active deals for this provider
    print(f"Finding active deals for provider {args.storage_provider}...")
    active_piece_cids = build_active_deals_set_for_provider(deals, args.storage_provider)
    print(f"Found {len(active_piece_cids)} pieces with active deals for {args.storage_provider}")

    # Generate report
    print("Generating report...")
    full_report = generate_report(
        piece_metadata_by_prep=piece_metadata_by_prep,
        active_piece_cids=active_piece_cids,
        preparations=[str(p) for p in args.preparation] if args.preparation else None,
        storage_provider=args.storage_provider,
        deals_path=deals_path,
        piece_metadata_dir=piece_metadata_dir,
    )

    # Convert to list-only format if requested
    if args.list_only:
        output_report = generate_list_only_report(full_report)
    else:
        output_report = full_report

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    print(f"Writing report to {output_path}...")
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_report, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Storage Provider: {args.storage_provider}")
    if args.list_only:
        print("Output format: list-only (pieceCids only)")
    print(f"Total pieces across selected preparations: {full_report['summary']['total_pieces_across_all_preps']}")
    print(f"Pieces WITHOUT active deals: {full_report['summary']['total_pieces_without_deals']}")
    print()
    print("By Preparation:")
    for prep_id, prep_summary in full_report["summary"]["by_preparation"].items():
        print(f"  Prep {prep_id}: {prep_summary['without_deals']} / {prep_summary['total']} pieces without deals")
    print()
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
