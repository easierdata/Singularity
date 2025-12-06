"""Attach preparation IDs to piece retrieval status records from metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, cast

from config import get_file_path, get_path, load_config


def _iter_pieces_from_payload(payload: object, source: Path) -> Iterable[dict[str, str]]:
    if isinstance(payload, dict):
        containers: Iterable[dict[str, object]] = [payload]
    elif isinstance(payload, list):
        containers = payload
    else:
        raise ValueError(f"Unexpected JSON structure in {source}: {type(payload)}")

    for container in containers:
        pieces = container.get("pieces") or []
        if isinstance(pieces, list):
            yield from (piece for piece in pieces if isinstance(piece, dict))


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def load_piece_metadata(directory: Path) -> Dict[str, dict[str, object]]:
    """Return a mapping of pieceCid -> metadata values required for enrichment."""
    mapping: Dict[str, dict[str, object]] = {}
    if not directory.exists():
        raise FileNotFoundError(f"Piece metadata directory not found: {directory}")

    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No metadata JSON files found in {directory}")

    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            try:
                payload = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse {path}: {exc}") from exc

        for piece in _iter_pieces_from_payload(payload, path):
            piece_cid = piece.get("pieceCid") or piece.get("piece_cid")
            prep_id = piece.get("preparationId") or piece.get("preparation_id")
            file_size = piece.get("fileSize") or piece.get("file_size")
            if isinstance(piece_cid, str):
                mapping[piece_cid] = {
                    "preparation": str(prep_id) if prep_id is not None else None,
                    "filesize_predeal": _to_int(file_size),
                }
    return mapping


def load_deals_map(path: Path) -> Dict[Tuple[str, str], dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Deals file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected list of deals in {path}")

    mapping: Dict[Tuple[str, str], dict[str, object]] = {}
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


def load_piece_status(path: Path) -> List[dict[str, object]]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected list of records in {path}")
    return data


def enrich_records(
    records: Iterable[dict[str, object]],
    piece_meta: Dict[str, dict[str, object]],
    deals_map: Dict[Tuple[str, str], dict[str, object]],
) -> tuple[List[dict[str, object]], int, int]:
    grouped: Dict[str, dict[str, object]] = {}
    prep_matched = 0
    deal_matched = 0

    for record in records:
        piece_cid = record.get("piece_cid")
        provider_id = record.get("provider_id")
        if not isinstance(piece_cid, str) or not isinstance(provider_id, str):
            continue

        meta = piece_meta.get(piece_cid, {})
        if meta:
            prep_matched += 1

        entry = grouped.setdefault(
            piece_cid,
            {
                "pieceCid": piece_cid,
                "filesize_predeal": meta.get("filesize_predeal"),
                "preparation": meta.get("preparation") or "unknown",
                "storage_providers": set(),
                "active_deal_providers": set(),
                "storage_provider_retrieval_check": {},
            },
        )

        if entry["filesize_predeal"] is None and meta.get("filesize_predeal") is not None:
            entry["filesize_predeal"] = meta.get("filesize_predeal")
        if entry["preparation"] == "unknown" and meta.get("preparation"):
            entry["preparation"] = meta.get("preparation")
        # Only use content_length as fallback if it's a positive value
        # (content_length = -1 indicates "no active deal", not actual size)
        content_len = record.get("content_length")
        if (
            entry["filesize_predeal"] is None
            and isinstance(content_len, (int, float))
            and content_len > 0
        ):
            entry["filesize_predeal"] = int(content_len)
        storage_providers = cast(set[str], entry["storage_providers"])
        storage_providers.add(provider_id)

        deal_info = deals_map.get((piece_cid, provider_id))
        deal_state = (deal_info or {}).get("deal_state") or "unknown"
        deal_id = (deal_info or {}).get("deal_id")
        if deal_info:
            deal_matched += 1
            if isinstance(deal_state, str) and deal_state.lower() == "active":
                cast(set[str], entry["active_deal_providers"]).add(provider_id)

        provider_record = {
            "provider_name": record.get("provider_name"),
            "provider_id": provider_id,
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
        provider_map = cast(Dict[str, dict[str, object]], entry["storage_provider_retrieval_check"])
        provider_map[provider_id] = provider_record

    enriched: List[dict[str, object]] = []
    for piece_cid, entry in grouped.items():
        storage_providers = sorted(cast(set[str], entry["storage_providers"]))
        active_providers = sorted(cast(set[str], entry["active_deal_providers"]))
        enriched.append(
            {
                "pieceCid": piece_cid,
                "filesize_predeal": entry["filesize_predeal"],
                "preparation": entry["preparation"],
                "storage_providers": storage_providers,
                "has_active_deal": bool(active_providers),
                "active_deal_providers": active_providers,
                "storage_provider_retrieval_check": entry["storage_provider_retrieval_check"],
            }
        )

    enriched.sort(key=lambda item: cast(str, item["pieceCid"]))
    return enriched, prep_matched, deal_matched


def write_output(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach preparation IDs from metadata to piece retrieval records.",
    )
    parser.add_argument(
        "--piece-metadata-dir",
        type=Path,
        default=None,
        help="Directory containing piece metadata JSON files. Defaults to config value.",
    )
    parser.add_argument(
        "--piece-status-file",
        type=Path,
        default=None,
        help="Path to final_retrieval_piece_status.json. Defaults to config value.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Where to write the enriched JSON file. Defaults to config value.",
    )
    parser.add_argument(
        "--deals-file",
        type=Path,
        default=None,
        help="Path to deals.json for deal state information. Defaults to config value.",
    )
    return parser.parse_args()


def main() -> None:
    # Load config
    config = load_config()

    args = parse_args()

    # Resolve paths: CLI override > config value
    piece_metadata_dir = args.piece_metadata_dir or get_path(config, "piece_metadata_dir")
    piece_status_file = args.piece_status_file or get_file_path(config, "piece_status_filename")
    output_file = args.output_file or get_file_path(config, "piece_status_postprocessed_filename")
    deals_file = args.deals_file or get_path(config, "deals_file")

    mapping = load_piece_metadata(piece_metadata_dir)
    deals_map = load_deals_map(deals_file)
    records = load_piece_status(piece_status_file)
    enriched, prep_matched, deal_matched = enrich_records(records, mapping, deals_map)
    write_output(enriched, output_file)

    total = len(enriched)
    prep_unmatched = total - prep_matched
    deal_unmatched = total - deal_matched
    print(
        "Finished attaching preparation IDs:\n"
        f"  Source records : {total:,}\n"
        f"  Prep matched   : {prep_matched:,}\n"
        f"  Prep unmatched : {prep_unmatched:,}\n"
        f"  Deals matched  : {deal_matched:,}\n"
        f"  Deals unmatched: {deal_unmatched:,}\n"
        f"  Output file    : {output_file}"
    )


if __name__ == "__main__":
    main()
