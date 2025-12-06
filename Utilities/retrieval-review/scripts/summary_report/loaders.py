"""
Data Loaders for Summary Report Generation

Functions for loading and parsing input data files including JSON files,
CSV metadata files, and deals data. Also includes functions for extracting
and transforming retrieval check records.
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .utils import extract_filetype


def load_json_file(path: Path) -> List[Dict]:
    """Load a JSON file, returning empty list if file doesn't exist or is empty.

    Args:
        path: Path to the JSON file to load

    Returns:
        List of dictionaries from the JSON file, or empty list if file
        doesn't exist or is empty

    Raises:
        SystemExit: If the JSON file exists but contains invalid JSON
    """
    if not path.exists():
        print(f"Warning: File not found: {path}", file=sys.stderr)
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data else []
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def build_active_deals_set(deals: List[Dict]) -> Set[Tuple[str, str]]:
    """Build a set of (pieceCid, provider_id) tuples for active deals.

    Uses deals.json as authoritative source. Handles both 'provider' and
    'providerid' fields for compatibility with different data formats.

    Args:
        deals: List of deal dictionaries from deals.json

    Returns:
        Set of (pieceCid, provider_id) tuples for all active deals
    """
    active_set = set()
    for deal in deals:
        state = deal.get("state", "").lower()
        if state != "active":
            continue
        piece_cid = deal.get("pieceCid")
        # Handle different field names for provider
        provider_id = deal.get("provider") or deal.get("providerid") or deal.get("provider_id")
        if piece_cid and provider_id:
            active_set.add((piece_cid, provider_id))
    return active_set


def extract_retrieval_checks(
    records: List[Dict],
    active_deals: Set[Tuple[str, str]],
    record_type: str,  # "piece" or "cid"
) -> Tuple[List[Dict], List[Dict]]:
    """Extract retrieval checks from records, splitting by active deal status.

    Flattens the nested storage_provider_retrieval_check structure into
    individual check records, each containing metadata about the record
    plus the provider check details.

    Args:
        records: List of piece or CID status records
        active_deals: Set of (pieceCid, provider_id) tuples for active deals
        record_type: Either "piece" or "cid" to indicate the record type

    Returns:
        Tuple of (active_checks, non_active_checks) where each check includes
        metadata about the record plus the provider check details
    """
    active_checks = []
    non_active_checks = []

    print(f"Number of {record_type} records to process: {len(records)}")

    for record in records:
        piece_cid = record.get("pieceCid")
        preparation = str(record.get("preparation", "unknown"))

        # Extra fields for CID records (handle both snake_case and camelCase)
        cid = record.get("cid") if record_type == "cid" else None
        filetype = (record.get("file_type") or record.get("filetype")) if record_type == "cid" else None
        filesize = (record.get("file_size") or record.get("filesize")) if record_type == "cid" else None
        filename = (record.get("file_name") or record.get("filename")) if record_type == "cid" else None

        # Piece-level filesize
        filesize_predeal = record.get("filesize_predeal") if record_type == "piece" else None

        # Get retrieval checks per provider
        retrieval_checks = record.get("storage_provider_retrieval_check", {})

        for provider_id, check in retrieval_checks.items():
            check_record = {
                "pieceCid": piece_cid,
                "provider_id": provider_id,
                "provider_name": check.get("provider_name", ""),
                "preparation": preparation,
                "status": check.get("status"),
                "status_code": check.get("status_code"),
                "record_type": record_type,
            }

            if record_type == "cid":
                check_record["cid"] = cid
                check_record["filetype"] = filetype
                check_record["filesize"] = filesize
                check_record["filename"] = filename
            else:
                check_record["filesize_predeal"] = filesize_predeal

            # Check if this (pieceCid, provider) is in active deals
            if (piece_cid, provider_id) in active_deals:
                active_checks.append(check_record)
            else:
                non_active_checks.append(check_record)

    return active_checks, non_active_checks


def load_file_metadata_csvs(file_metadata_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load all file-metadata CSVs and group by preparation ID.

    Returns a dict mapping preparation_id to:
        {
            "filename": "<source filename>",
            "files": [{"cid": ..., "pieceCid": ..., "size": ..., "fileName": ...}, ...],
            "total_files": int,
            "unique_cids": set of cids,
            "cid_attributes": dict mapping cid -> {"filetype": str, "size": int|None},
        }

    Note on CID deduplication strategy: When the same CID appears multiple times in a
    preparation (potentially with different filenames/extensions), we use "FIRST ONE IN"
    - the first occurrence's filetype and size are used for that CID's metrics.
    This is deterministic and matches typical deduplication behavior where the first
    occurrence establishes the canonical attributes.

    Args:
        file_metadata_dir: Path to directory containing file-metadata CSV files

    Returns:
        Dict mapping preparation_id to metadata about that preparation's files
    """
    if not file_metadata_dir.exists():
        print(f"Warning: file-metadata directory not found: {file_metadata_dir}")
        return {}

    result = {}
    prep_pattern = re.compile(r"prep(\d+)")

    for csv_path in sorted(file_metadata_dir.glob("*.csv")):
        # Extract prep ID from filename (e.g., "GEDI02_B_prep1_details.csv" -> "1")
        match = prep_pattern.search(csv_path.stem)
        if not match:
            print(f"Warning: Could not extract prep ID from {csv_path.name}, skipping")
            continue

        prep_id = match.group(1)

        files = []
        unique_cids: Set[str] = set()
        # Maps CID -> {filetype, size} using "first one in" strategy
        cid_attributes: Dict[str, Dict[str, Any]] = {}

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get("cid", "")
                piece_cid = row.get("pieceCid", "")
                size_str = row.get("size", "")
                file_name = row.get("fileName", "")

                # Parse size
                try:
                    size = int(size_str) if size_str else None
                except ValueError:
                    size = None

                files.append({
                    "cid": cid,
                    "pieceCid": piece_cid,
                    "size": size,
                    "fileName": file_name,
                })

                if cid:
                    unique_cids.add(cid)
                    # "First one in" strategy: only set attributes if CID not already seen
                    if cid not in cid_attributes:
                        cid_attributes[cid] = {
                            "filetype": extract_filetype(file_name),
                            "size": size,
                        }

        result[prep_id] = {
            "filename": csv_path.name,
            "files": files,
            "total_files": len(files),
            "unique_cids": unique_cids,
            "cid_attributes": cid_attributes,
        }

        print(f"Loaded prep {prep_id}: {len(files)} files, {len(unique_cids)} unique CIDs")

    return result


def load_piece_metadata_jsons(piece_metadata_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load all piece-metadata JSON files and group by preparation ID.

    The JSON structure is: [{"attachmentId": ..., "pieces": [...]}]
    where each piece has: pieceCid, pieceSize, fileSize, numOfFiles, etc.

    Args:
        piece_metadata_dir: Path to directory containing piece-metadata JSON files

    Returns:
        Dict mapping preparation_id to:
            {
                "filename": "<source filename>",
                "pieces": [{"pieceCid": ..., "pieceSize": ..., "fileSize": ..., "numOfFiles": ...}, ...],
                "total_pieces": int,
                "unique_piece_cids": set of pieceCids,
            }
    """
    if not piece_metadata_dir.exists():
        print(f"Warning: piece-metadata directory not found: {piece_metadata_dir}")
        return {}

    result = {}
    prep_pattern = re.compile(r"prep(\d+)")

    for json_path in sorted(piece_metadata_dir.glob("*.json")):
        # Extract prep ID from filename (e.g., "GEDI02_B_prep1_details.json" -> "1")
        match = prep_pattern.search(json_path.stem)
        if not match:
            print(f"Warning: Could not extract prep ID from {json_path.name}, skipping")
            continue

        prep_id = match.group(1)

        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {json_path.name}: {e}, skipping")
            continue

        pieces = []
        unique_piece_cids: Set[str] = set()

        # Handle the nested structure: [{"pieces": [...]}]
        if isinstance(data, list) and len(data) > 0:
            for item in data:
                if isinstance(item, dict) and "pieces" in item:
                    for record in item["pieces"]:
                        piece_cid = record.get("pieceCid", "")
                        piece_size = record.get("pieceSize")
                        file_size = record.get("fileSize")
                        num_of_files = record.get("numOfFiles", 0)

                        pieces.append({
                            "pieceCid": piece_cid,
                            "pieceSize": piece_size,
                            "fileSize": file_size,
                            "numOfFiles": num_of_files,
                        })

                        if piece_cid:
                            unique_piece_cids.add(piece_cid)

        result[prep_id] = {
            "filename": json_path.name,
            "pieces": pieces,
            "total_pieces": len(pieces),
            "unique_piece_cids": unique_piece_cids,
        }

        print(f"Loaded prep {prep_id}: {len(pieces)} pieces, {len(unique_piece_cids)} unique pieceCids")

    return result
