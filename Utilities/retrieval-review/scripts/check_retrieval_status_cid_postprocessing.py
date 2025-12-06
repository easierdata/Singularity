import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from config import get_file_path, get_path, load_config

Key = Tuple[str, str]
Value = Dict[str, object]


def _ensure_cid_entry(
    grouped: Dict[str, dict],
    cid: str,
    piece_cid: str,
    provider: str,
    record: dict,
) -> dict:
    entry = grouped.setdefault(
        cid,
        {
            "cid": cid,
            "pieceCid": piece_cid,
            "preparation": record.get("preparation") or "unknown",
            "provider_id": provider,
            "file_name": record.get("file_name"),
            "file_type": record.get("file_type") or "unknown",
            "file_size": record.get("file_size"),
            "storage_providers": set(),
            "active_deal_providers": set(),
            "storage_provider_retrieval_check": {},
            "has_active_deal": False,
        },
    )

    if not entry.get("provider_id"):
        entry["provider_id"] = provider
    if not entry.get("pieceCid"):
        entry["pieceCid"] = piece_cid
    if entry.get("preparation") in (None, "unknown") and record.get("preparation"):
        entry["preparation"] = record.get("preparation")
    return entry


def _attach_provider_details(
    entry: dict,
    record: dict,
    provider: str,
    piece_cid: str,
    deals_map: Dict[Key, Value],
) -> int:
    storage_providers: set[str] = entry["storage_providers"]
    storage_providers.add(provider)

    info = deals_map.get((piece_cid, provider))
    deal_state = (info or {}).get("deal_state") or "unknown"
    deal_id = (info or {}).get("deal_id")
    if info and isinstance(deal_state, str) and deal_state.lower() == "active":
        entry["active_deal_providers"].add(provider)
        entry["has_active_deal"] = True

    provider_record = {
        "provider_name": record.get("provider_name"),
        "provider_id": provider,
        "retrieval_type": record.get("retrieval_type"),
        "url": record.get("url"),
        "timestamp": record.get("timestamp"),
        "status": record.get("status"),
        "status_code": record.get("status_code"),
        "content_length": record.get("content_length"),
        "error_message": record.get("error_message"),
        "response_body": record.get("response_body"),
        "response_time_ms": record.get("response_time_ms"),
        "deal_state": deal_state,
        "deal_id": deal_id,
    }
    entry["storage_provider_retrieval_check"][provider] = provider_record
    return 1 if info else 0


def _apply_file_metadata(
    entry: dict,
    cid: str,
    file_meta: Dict[str, Dict[str, object]],
    applied: set[str],
) -> int:
    file_info = file_meta.get(cid)
    if file_info and cid not in applied:
        entry["file_name"] = file_info.get("file_name")
        entry["file_type"] = file_info.get("file_type", "unknown")
        entry["file_size"] = file_info.get("file_size")
        applied.add(cid)
        return 1
    if not entry.get("file_type"):
        entry["file_type"] = "unknown"
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attach latest deal_id and deal_state to CID retrieval status records"
        )
    )
    parser.add_argument(
        "--cid-status-file",
        type=Path,
        default=None,
        help="Path to final_retrieval_cid_status.json. Defaults to config value.",
    )
    parser.add_argument(
        "--deals-file",
        type=Path,
        default=None,
        help="Path to deals.json. Defaults to config value.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Where to write the enriched JSON output. Defaults to config value.",
    )
    parser.add_argument(
        "--file-metadata-dir",
        type=Path,
        default=None,
        help="Directory containing per-preparation file metadata CSVs. Defaults to config value.",
    )
    return parser.parse_args()


def load_deals_map(path: Path) -> Dict[Key, Value]:
    if not path.exists():
        raise FileNotFoundError(f"Deals file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected list of deals in {path}")

    mapping: Dict[Key, Value] = {}
    for deal in data:
        if not isinstance(deal, dict):
            continue
        piece_cid = deal.get("pieceCid")
        provider = deal.get("provider")
        if not isinstance(piece_cid, str) or not isinstance(provider, str):
            continue

        timestamp = str(deal.get("updatedAt") or deal.get("createdAt") or "")
        key = (piece_cid, provider)
        existing = mapping.get(key)
        existing_ts = str(existing.get("timestamp", "")) if existing else ""
        if existing is None or timestamp > existing_ts:
            mapping[key] = {
                "deal_state": deal.get("state") or "unknown",
                "deal_id": deal.get("dealId"),
                "timestamp": timestamp,
            }
    return mapping


def load_cid_status_records(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"CID status file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected list of records in {path}")
    return data


def load_file_metadata(directory: Path) -> Dict[str, Dict[str, object]]:
    if not directory.exists():
        raise FileNotFoundError(f"File metadata directory not found: {directory}")

    mapping: Dict[str, Dict[str, object]] = {}
    csv_paths = sorted(directory.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {directory}")

    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cid = row.get("cid")
                if not isinstance(cid, str) or not cid:
                    continue
                if cid in mapping:
                    continue
                file_name = row.get("fileName") or ""
                size_value = row.get("size")
                try:
                    file_size = int(size_value) if size_value not in (None, "") else None
                except ValueError:
                    file_size = None
                file_type = "unknown"
                if file_name:
                    parts = file_name.rsplit(".", 1)
                    if len(parts) == 2 and parts[1]:
                        file_type = parts[1].lower()
                mapping[cid] = {
                    "file_name": file_name or None,
                    "file_type": file_type,
                    "file_size": file_size,
                }
    return mapping


def _pick_provider(record: dict) -> str | None:
    for key in ("provider_id", "provider", "providerId"):
        value = record.get(key)
        if isinstance(value, str):
            return value
    return None


def enrich_records(
    records: Iterable[dict],
    deals_map: Dict[Key, Value],
    file_meta: Dict[str, Dict[str, object]],
) -> tuple[List[dict], int, int]:
    grouped: Dict[str, dict] = {}
    deal_matched = 0
    file_matched = 0
    file_meta_applied: set[str] = set()

    for record in records:
        cid = record.get("cid")
        piece_cid = record.get("pieceCid")
        provider = _pick_provider(record)
        if not isinstance(cid, str) or not isinstance(piece_cid, str) or not provider:
            continue

        entry = _ensure_cid_entry(grouped, cid, piece_cid, provider, record)
        deal_matched += _attach_provider_details(entry, record, provider, piece_cid, deals_map)
        file_matched += _apply_file_metadata(entry, cid, file_meta, file_meta_applied)

    enriched: List[dict] = []
    for cid, entry in grouped.items():
        storage_providers = sorted(entry["storage_providers"])
        active_providers = sorted(entry["active_deal_providers"])
        enriched.append(
            {
                "cid": cid,
                "pieceCid": entry.get("pieceCid"),
                "preparation": entry.get("preparation"),
                "file_name": entry.get("file_name"),
                "file_type": entry.get("file_type"),
                "file_size": entry.get("file_size"),
                "provider_id": entry.get("provider_id"),
                "storage_providers": storage_providers,
                "has_active_deal": bool(active_providers),
                "active_deal_providers": active_providers,
                "storage_provider_retrieval_check": entry["storage_provider_retrieval_check"],
            }
        )

    enriched.sort(key=lambda item: item["cid"])
    return enriched, deal_matched, file_matched


def write_output(records: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)


def main() -> None:
    # Load config
    config = load_config()

    args = parse_args()

    # Resolve paths: CLI override > config value
    cid_status_file = args.cid_status_file or get_file_path(config, "cid_status_filename")
    deals_file = args.deals_file or get_path(config, "deals_file")
    output_file = args.output_file or get_file_path(config, "cid_status_postprocessed_filename")
    file_metadata_dir = args.file_metadata_dir or get_path(config, "file_metadata_dir")

    deals_map = load_deals_map(deals_file)
    records = load_cid_status_records(cid_status_file)
    file_metadata = load_file_metadata(file_metadata_dir)
    enriched, deal_matched, file_matched = enrich_records(records, deals_map, file_metadata)
    write_output(enriched, output_file)

    total = len(enriched)
    deal_unmatched = total - deal_matched
    file_unmatched = total - file_matched
    print(
        "Finished attaching deal info:\n"
        f"  Source records : {total:,}\n"
        f"  Deals matched  : {deal_matched:,}\n"
        f"  Deals unmatched: {deal_unmatched:,}\n"
        f"  Files matched  : {file_matched:,}\n"
        f"  Files unmatched: {file_unmatched:,}\n"
        f"  Output file    : {output_file}"
    )


if __name__ == "__main__":
    main()
