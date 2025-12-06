#!/usr/bin/env python3
"""
Script to check retrieval status for pieces and CIDs from Curio Gateway endpoints.
Tests both piece-based and CID-based retrieval from configured storage providers.

Features:
- Checkpoint-based resume capability using parquet files
- Deals-aware processing (only checks providers with active deals)
- Configurable storage providers via config file
- Progress bars for large datasets

Usage:
    python check_retrieval_status.py                                # Uses config.json defaults
    python check_retrieval_status.py --prep-ids 1 2 3               # Specific preparations
    python check_retrieval_status.py --config ./my_config.json      # Override config path
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from config import get_path, get_retrieval_defaults, get_storage_providers, load_config
from tqdm import tqdm

# Constants
DEFAULT_BATCH_SIZE = 100
DEFAULT_CONCURRENCY = 10
DEFAULT_REQUEST_TIMEOUT = 30
DEALS_FRESHNESS_WARNING_DAYS = 30
NO_DEAL_STATUS_CODE = -1
NO_DEAL_RESPONSE_TIME = -1
NO_DEAL_CONTENT_LENGTH = -1

# Define explicit column ordering for consistent output schemas
PIECE_RESULT_COLUMNS = [
    "piece_cid",
    "provider_id",
    "provider_name",
    "retrieval_type",
    "url",
    "timestamp",
    "status",
    "status_code",
    "content_length",
    "error_message",
    "response_body",
    "response_time_ms",
]

CID_RESULT_COLUMNS = [
    "cid",
    "pieceCid",
    "preparation",
    "provider_id",
    "provider_name",
    "retrieval_type",
    "url",
    "timestamp",
    "status",
    "status_code",
    "content_length",
    "error_message",
    "response_body",
    "response_time_ms",
]

# Log directory and file configuration
LOG_DIR = Path("./output/logs")
LOG_FILE = LOG_DIR / "retrieval_status.log"


def setup_logging() -> logging.Logger:
    """
    Configure logging to write to both console and log file.

    Returns:
        Configured logger instance.
    """

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("retrieval_status")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers and create handlers list
    logger.handlers.clear()
    handlers: list[logging.Handler] = []

    # Create formatter - Use same format for both file and console
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # File handler with UTF-8 encoding and append mode
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # Configure root logger
    logging.basicConfig(level=logging.INFO, handlers=handlers)

    return logging.getLogger(__name__)


def load_deals(deals_path: Path, logger: logging.Logger) -> dict[str, dict[str, dict]]:
    """
    Load deals.json and build a lookup map.

    Returns: Dict[pieceCid, Dict[provider_id, latest_deal_info]]
    Only includes deals with state="active".
    """
    if not deals_path.exists():
        logger.warning(f"Deals file not found: {deals_path}")
        return {}

    # Check deals file freshness
    file_mtime = datetime.fromtimestamp(deals_path.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - file_mtime).days
    if age_days > DEALS_FRESHNESS_WARNING_DAYS:
        logger.warning(
            f"Deals file is {age_days} days old "
            f"(last modified: {file_mtime.strftime('%Y-%m-%d')}). "
            f"Consider refreshing it for accurate results."
        )

    logger.info(f"Loading deals from {deals_path}...")
    with deals_path.open("r", encoding="utf-8") as f:
        deals = json.load(f)

    # Build lookup: pieceCid -> provider_id -> latest deal
    deals_map: dict[str, dict[str, dict]] = {}

    for deal in deals:
        if deal.get("state") != "active":
            continue

        piece_cid = deal.get("pieceCid")
        provider_id = deal.get("provider")

        if not piece_cid or not provider_id:
            continue

        if piece_cid not in deals_map:
            deals_map[piece_cid] = {}

        # Keep the latest deal (by updatedAt) for each provider
        existing = deals_map[piece_cid].get(provider_id)
        if existing:
            existing_updated = existing.get("updatedAt", "")
            new_updated = deal.get("updatedAt", "")
            if new_updated > existing_updated:
                deals_map[piece_cid][provider_id] = deal
        else:
            deals_map[piece_cid][provider_id] = deal

    total_pieces = len(deals_map)
    total_provider_mappings = sum(len(v) for v in deals_map.values())
    logger.info(
        f"Loaded {total_provider_mappings} active deals across {total_pieces} pieces"
    )

    return deals_map


def load_checkpoint(
    checkpoint_path: Path, logger: logging.Logger
) -> pd.DataFrame | None:
    """Load existing checkpoint parquet file."""
    if not checkpoint_path.exists():
        return None

    logger.info(f"Loading checkpoint from {checkpoint_path}...")
    df = pd.read_parquet(checkpoint_path)
    logger.info(f"Loaded {len(df)} records from checkpoint")
    return df


def save_checkpoint(
    df: pd.DataFrame,
    checkpoint_path: Path,
    logger: logging.Logger,
) -> None:
    """Save checkpoint to parquet file atomically (write to temp, then rename)."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file first
    fd, temp_path = tempfile.mkstemp(suffix=".parquet", dir=checkpoint_path.parent)
    try:
        os.close(fd)
        df.to_parquet(temp_path, index=False)
        # Atomic rename (on same filesystem)
        shutil.move(temp_path, checkpoint_path)
        logger.debug(f"Saved checkpoint with {len(df)} records to {checkpoint_path}")
    except Exception:
        # Clean up temp file if something went wrong
        if Path(temp_path).exists():
            Path(temp_path).unlink()
        raise


def backup_checkpoint(checkpoint_path: Path, logger: logging.Logger) -> Path | None:
    """Backup existing checkpoint file with timestamp."""
    if not checkpoint_path.exists():
        return None

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = checkpoint_path.with_suffix(f".backup_{timestamp}.parquet")
    shutil.copy2(checkpoint_path, backup_path)
    logger.info(f"Backed up checkpoint to {backup_path}")
    return backup_path


def get_processed_keys(
    checkpoint_df: pd.DataFrame | None,
) -> set[tuple[str, str, str]]:
    """
    Extract set of processed (item_key, provider_id, retrieval_type) from checkpoint.

    For pieces: item_key = piece_cid
    For CIDs: item_key = cid
    """
    if checkpoint_df is None or checkpoint_df.empty:
        return set()

    processed = set()
    for _, row in checkpoint_df.iterrows():
        retrieval_type = row.get("retrieval_type", "")
        provider_id = row.get("provider_id", "")

        if retrieval_type == "piece":
            item_key = row.get("piece_cid", "")
        else:  # cid
            item_key = row.get("cid", "")

        if item_key and provider_id:
            processed.add((item_key, provider_id, retrieval_type))

    return processed


class RetrievalChecker:
    """Async retrieval checker with checkpoint and deals-aware processing."""

    def __init__(
        self,
        storage_providers: dict[str, dict[str, str]],
        deals_map: dict[str, dict[str, dict]],
        output_dir: Path,
        checkpoint_path: Path,
        concurrency: int = DEFAULT_CONCURRENCY,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        logger: logging.Logger | None = None,
    ):
        self.storage_providers = storage_providers
        self.deals_map = deals_map
        self.output_dir = output_dir
        self.checkpoint_path = checkpoint_path
        self.concurrency = concurrency
        self.request_timeout = request_timeout
        self.logger = logger or logging.getLogger(__name__)

        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.results: list[dict] = []
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "RetrievalChecker":
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": "sealed-data-retrieval-checker/2.0",
        }
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        if self.session:
            await self.session.close()

    def has_active_deal(self, piece_cid: str, provider_id: str) -> bool:
        """Check if there's an active deal for piece_cid with provider_id."""
        return provider_id in self.deals_map.get(piece_cid, {})

    def create_no_deal_result(
        self,
        retrieval_type: str,
        provider_id: str,
        provider_name: str,
        piece_cid: str | None = None,
        cid: str | None = None,
        preparation: str | None = None,
    ) -> dict:
        """Create a result record for items without active deals.

        Uses -1 for content_length to distinguish "no active deal" from
        "unknown content length" (which would be None).
        """
        if retrieval_type == "piece":
            return {
                "piece_cid": piece_cid,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "retrieval_type": retrieval_type,
                "url": None,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "status": "no active deal",
                "status_code": NO_DEAL_STATUS_CODE,
                "content_length": NO_DEAL_CONTENT_LENGTH,
                "error_message": "No active deal with this provider",
                "response_body": None,
                "response_time_ms": NO_DEAL_RESPONSE_TIME,
            }
        else:  # cid
            return {
                "cid": cid,
                "pieceCid": piece_cid,
                "preparation": preparation,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "retrieval_type": retrieval_type,
                "url": None,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "status": "no active deal",
                "status_code": NO_DEAL_STATUS_CODE,
                "content_length": NO_DEAL_CONTENT_LENGTH,
                "error_message": "No active deal with this provider",
                "response_body": None,
                "response_time_ms": NO_DEAL_RESPONSE_TIME,
            }

    async def check_piece_retrieval(
        self,
        piece_cid: str,
        provider_id: str,
        provider_config: dict[str, str],
    ) -> dict:
        """Check if a piece is retrievable from a storage provider."""
        url = f"{provider_config['retrieval_endpoint']}/piece/{piece_cid}"

        result = {
            "piece_cid": piece_cid,
            "provider_id": provider_id,
            "provider_name": provider_config["name"],
            "retrieval_type": "piece",
            "url": url,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "status": "unknown",
            "status_code": None,
            "content_length": None,
            "error_message": None,
            "response_body": None,
            "response_time_ms": None,
        }

        if not self.session:
            result["status"] = "error"
            result["error_message"] = "Session not initialized"
            return result

        try:
            start_time = asyncio.get_event_loop().time()

            # Try HEAD request first to check availability without downloading
            response_obj = None
            used_head = True
            try:
                response_obj = await self.session.head(url)
                # Fall back to GET if 405 Method Not Allowed
                if response_obj.status == 405:
                    response_obj.close()
                    response_obj = await self.session.get(url)
                    used_head = False
                # For non-200 responses with HEAD, do a GET to capture response body
                elif response_obj.status != 200:
                    response_obj.close()
                    response_obj = await self.session.get(url)
                    used_head = False
            except Exception:
                # If HEAD fails for any reason, try GET
                if response_obj:
                    response_obj.close()
                response_obj = await self.session.get(url)
                used_head = False

            async with response_obj as response:
                end_time = asyncio.get_event_loop().time()
                result["response_time_ms"] = int((end_time - start_time) * 1000)
                result["status_code"] = response.status

                if response.status == 200:
                    result["status"] = "available"
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        result["content_length"] = int(content_length)
                else:
                    result["status"] = "unavailable"
                    result["error_message"] = f"HTTP {response.status}"
                    # Only try to read body if we used GET (HEAD has no body)
                    if not used_head:
                        try:
                            response_text = await response.text()
                            if response_text:
                                result["response_body"] = response_text[:1024]
                        except Exception:
                            pass

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error_message"] = "Request timeout"
        except Exception as e:
            result["status"] = "error"
            result["error_message"] = str(e)

        return result

    async def check_cid_retrieval(
        self,
        cid: str,
        provider_id: str,
        provider_config: dict[str, str],
        piece_cid: str | None = None,
        preparation: str | None = None,
    ) -> dict:
        """Check if a CID is retrievable via IPFS gateway.

        Note: content_length will typically be None for CID retrievals because
        trustless IPFS gateways don't return Content-Length without downloading
        the entire file.
        """
        url = f"{provider_config['retrieval_endpoint']}/ipfs/{cid}"

        result = {
            "cid": cid,
            "pieceCid": piece_cid,
            "preparation": preparation,
            "provider_id": provider_id,
            "provider_name": provider_config["name"],
            "retrieval_type": "cid",
            "url": url,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "status": "unknown",
            "status_code": None,
            "content_length": None,  # Usually unavailable for trustless IPFS gateways
            "error_message": None,
            "response_body": None,
            "response_time_ms": None,
        }

        if not self.session:
            result["status"] = "error"
            result["error_message"] = "Session not initialized"
            return result

        try:
            start_time = asyncio.get_event_loop().time()

            # Try HEAD request first to check availability
            response_obj = None
            used_head = True
            try:
                response_obj = await self.session.head(url)
                # Fall back to GET if 405 Method Not Allowed
                if response_obj.status == 405:
                    response_obj.close()
                    response_obj = await self.session.get(url)
                    used_head = False
                # For non-200 responses with HEAD, do a GET to capture response body
                elif response_obj.status != 200:
                    response_obj.close()
                    response_obj = await self.session.get(url)
                    used_head = False
            except Exception:
                # If HEAD fails for any reason, try GET
                if response_obj:
                    response_obj.close()
                response_obj = await self.session.get(url)
                used_head = False

            async with response_obj as response:
                end_time = asyncio.get_event_loop().time()
                result["response_time_ms"] = int((end_time - start_time) * 1000)
                result["status_code"] = response.status

                if response.status == 200:
                    result["status"] = "available"
                    # Content-Length usually not available for trustless IPFS
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        result["content_length"] = int(content_length)
                else:
                    result["status"] = "unavailable"
                    result["error_message"] = f"HTTP {response.status}"
                    # Only try to read body if we used GET (HEAD has no body)
                    if not used_head:
                        try:
                            response_text = await response.text()
                            if response_text:
                                result["response_body"] = response_text[:1024]
                        except Exception:
                            pass

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error_message"] = "Request timeout"
        except Exception as e:
            result["status"] = "error"
            result["error_message"] = str(e)

        return result

    async def process_piece_batch(
        self,
        pieces: list[str],
        processed_keys: set[tuple[str, str, str]],
        pbar: tqdm | None = None,
    ) -> list[dict]:
        """Process a batch of pieces concurrently."""
        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[dict] = []

        async def check_piece(
            piece_cid: str,
            provider_id: str,
            provider_config: dict,
        ) -> dict | None:
            # Check if already processed
            if (piece_cid, provider_id, "piece") in processed_keys:
                return None

            async with semaphore:
                # Check if there's an active deal
                if not self.has_active_deal(piece_cid, provider_id):
                    result = self.create_no_deal_result(
                        retrieval_type="piece",
                        provider_id=provider_id,
                        provider_name=provider_config["name"],
                        piece_cid=piece_cid,
                    )
                else:
                    result = await self.check_piece_retrieval(
                        piece_cid, provider_id, provider_config
                    )

                if pbar:
                    pbar.update(1)
                return result

        tasks = []
        for piece_cid in pieces:
            for provider_id, provider_config in self.storage_providers.items():
                tasks.append(check_piece(piece_cid, provider_id, provider_config))

        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in task_results:
            if isinstance(r, Exception):
                self.logger.error(f"Task exception: {r}")
            elif r is not None:
                results.append(r)

        return results

    async def process_cid_batch(
        self,
        cid_records: list[dict],
        processed_keys: set[tuple[str, str, str]],
        pbar: tqdm | None = None,
    ) -> list[dict]:
        """Process a batch of CID records concurrently."""
        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[dict] = []

        async def check_cid(
            record: dict,
            provider_id: str,
            provider_config: dict,
        ) -> dict | None:
            cid = record["cid"]
            piece_cid = record["pieceCid"]
            preparation = record["preparation"]

            # Check if already processed
            if (cid, provider_id, "cid") in processed_keys:
                return None

            async with semaphore:
                # Check if there's an active deal for the piece
                if not self.has_active_deal(piece_cid, provider_id):
                    result = self.create_no_deal_result(
                        retrieval_type="cid",
                        provider_id=provider_id,
                        provider_name=provider_config["name"],
                        cid=cid,
                        piece_cid=piece_cid,
                        preparation=preparation,
                    )
                else:
                    result = await self.check_cid_retrieval(
                        cid, provider_id, provider_config, piece_cid, preparation
                    )

                if pbar:
                    pbar.update(1)
                return result

        tasks = []
        for record in cid_records:
            for provider_id, provider_config in self.storage_providers.items():
                tasks.append(check_cid(record, provider_id, provider_config))

        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in task_results:
            if isinstance(r, Exception):
                self.logger.error(f"Task exception: {r}")
            elif r is not None:
                results.append(r)

        return results

    def load_file_metadata(
        self,
        csv_files: list[Path],
        prep_ids: list[int] | None = None,
    ) -> tuple[list[str], list[dict]]:
        """
        Load file metadata from CSV files.

        Returns: (unique_pieces, unique_cid_records)
        """
        all_pieces: set[str] = set()
        all_cid_records: list[dict] = []
        seen_cids: set[tuple[str, str, str]] = set()

        for csv_file in csv_files:
            self.logger.info(f"Loading file metadata from {csv_file.name}")
            df = pd.read_csv(csv_file)

            # Filter by preparation IDs if specified
            if prep_ids:
                df = df[df["attachmentId"].isin(prep_ids)]
                self.logger.info(
                    f"  Filtered to {len(df)} records for prep IDs: {prep_ids}"
                )

            if df.empty:
                continue

            # Collect unique pieces
            all_pieces.update(df["pieceCid"].dropna().unique())

            # Collect CID records with metadata
            cid_df = df[["cid", "pieceCid", "attachmentId"]].dropna()
            for _, row in cid_df.iterrows():
                key = (row["cid"], row["pieceCid"], str(row["attachmentId"]))
                if key not in seen_cids:
                    seen_cids.add(key)
                    all_cid_records.append({
                        "cid": row["cid"],
                        "pieceCid": row["pieceCid"],
                        "preparation": str(int(row["attachmentId"])),
                    })

        self.logger.info(
            f"Found {len(all_pieces)} unique pieces and "
            f"{len(all_cid_records)} unique CID records"
        )
        return list(all_pieces), all_cid_records

    async def check_all_retrievals(
        self,
        csv_files: list[Path],
        batch_size: int = DEFAULT_BATCH_SIZE,
        prep_ids: list[int] | None = None,
        check_no_deals_only: bool = False,
        checkpoint_df: pd.DataFrame | None = None,
    ) -> None:
        """Check retrieval status for all pieces and CIDs."""
        # Load file metadata
        pieces, cid_records = self.load_file_metadata(csv_files, prep_ids)

        # Get already processed keys from checkpoint
        processed_keys = get_processed_keys(checkpoint_df)
        self.logger.info(
            f"Found {len(processed_keys)} already processed items in checkpoint"
        )

        # If check_no_deals_only mode, filter to only items with "no active deal"
        if check_no_deals_only and checkpoint_df is not None:
            no_deal_df = checkpoint_df[checkpoint_df["status"] == "no active deal"]
            self.logger.info(
                f"Check-no-deals mode: Found {len(no_deal_df)} records "
                f"with 'no active deal' status"
            )

            # Remove these from processed_keys so they get re-checked
            for _, row in no_deal_df.iterrows():
                retrieval_type = row.get("retrieval_type", "")
                provider_id = row.get("provider_id", "")
                if retrieval_type == "piece":
                    item_key = row.get("piece_cid", "")
                else:
                    item_key = row.get("cid", "")
                key = (item_key, provider_id, retrieval_type)
                processed_keys.discard(key)

            self.logger.info(
                "Removed 'no active deal' items from processed set for re-checking"
            )

        # Initialize results from checkpoint
        if checkpoint_df is not None and not checkpoint_df.empty:
            self.results = checkpoint_df.to_dict("records")

        # Calculate total work for progress bar
        num_providers = len(self.storage_providers)
        total_piece_checks = len(pieces) * num_providers
        total_cid_checks = len(cid_records) * num_providers

        # Process pieces
        self.logger.info("Checking piece retrievals...")
        with tqdm(total=total_piece_checks, desc="Pieces", unit="check") as pbar:
            for i in range(0, len(pieces), batch_size):
                batch = pieces[i : i + batch_size]
                batch_results = await self.process_piece_batch(
                    batch, processed_keys, pbar
                )

                if batch_results:
                    self.results.extend(batch_results)
                    # Update processed keys
                    for r in batch_results:
                        processed_keys.add((r["piece_cid"], r["provider_id"], "piece"))

                    # Save checkpoint
                    df = pd.DataFrame(self.results)
                    save_checkpoint(df, self.checkpoint_path, self.logger)

        # Process CIDs
        self.logger.info("Checking CID retrievals...")
        with tqdm(total=total_cid_checks, desc="CIDs", unit="check") as pbar:
            for i in range(0, len(cid_records), batch_size):
                batch = cid_records[i : i + batch_size]
                batch_results = await self.process_cid_batch(
                    batch, processed_keys, pbar
                )

                if batch_results:
                    self.results.extend(batch_results)
                    # Update processed keys
                    for r in batch_results:
                        processed_keys.add((r["cid"], r["provider_id"], "cid"))

                    # Save checkpoint
                    df = pd.DataFrame(self.results)
                    save_checkpoint(df, self.checkpoint_path, self.logger)

    def save_final_results(self) -> None:
        """Save final results to parquet and JSON files with consistent schemas."""
        if not self.results:
            self.logger.warning("No results to save")
            return

        df = pd.DataFrame(self.results)

        # Separate by type
        piece_results = df[df["retrieval_type"] == "piece"].copy()
        cid_results = df[df["retrieval_type"] == "cid"].copy()

        # Save piece results with explicit column ordering
        if not piece_results.empty:
            parquet_path = self.output_dir / "final_retrieval_piece_status.parquet"
            json_path = self.output_dir / "final_retrieval_piece_status.json"

            # Ensure all columns exist and are in correct order
            for col in PIECE_RESULT_COLUMNS:
                if col not in piece_results.columns:
                    piece_results[col] = None
            piece_results = piece_results[PIECE_RESULT_COLUMNS]

            piece_results.to_parquet(parquet_path, index=False)
            self.logger.info(
                f"Saved {len(piece_results)} piece results to {parquet_path}"
            )

            # Convert to records and replace NaN with None for valid JSON
            records = piece_results.to_dict("records")
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None

            with json_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            self.logger.info(f"Saved piece results JSON to {json_path}")

        # Save CID results with explicit column ordering
        if not cid_results.empty:
            parquet_path = self.output_dir / "final_retrieval_cid_status.parquet"
            json_path = self.output_dir / "final_retrieval_cid_status.json"

            # Ensure all columns exist and are in correct order
            for col in CID_RESULT_COLUMNS:
                if col not in cid_results.columns:
                    cid_results[col] = None
            cid_results = cid_results[CID_RESULT_COLUMNS]

            cid_results.to_parquet(parquet_path, index=False)
            self.logger.info(
                f"Saved {len(cid_results)} CID results to {parquet_path}"
            )

            # Convert to records and replace NaN with None for valid JSON
            records = cid_results.to_dict("records")
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None

            with json_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            self.logger.info(f"Saved CID results JSON to {json_path}")

    def generate_summary(self) -> dict:
        """Generate summary statistics of retrieval status."""
        if not self.results:
            return {}

        df = pd.DataFrame(self.results)

        # Count by type and status
        by_type_status: dict[str, dict[str, int]] = {}
        for rtype in df["retrieval_type"].unique():
            type_df = df[df["retrieval_type"] == rtype]
            by_type_status[rtype] = type_df["status"].value_counts().to_dict()

        # Count by provider and status
        by_provider_status: dict[str, dict[str, int]] = {}
        for provider in df["provider_name"].unique():
            provider_df = df[df["provider_name"] == provider]
            by_provider_status[provider] = provider_df["status"].value_counts().to_dict()

        # Calculate availability rates (excluding "no active deal")
        piece_df = df[df["retrieval_type"] == "piece"]
        piece_with_deals = piece_df[piece_df["status"] != "no active deal"]
        piece_available = piece_df[piece_df["status"] == "available"]

        cid_df = df[df["retrieval_type"] == "cid"]
        cid_with_deals = cid_df[cid_df["status"] != "no active deal"]
        cid_available = cid_df[cid_df["status"] == "available"]

        # Response time stats (only for actual requests)
        actual_requests = df[df["response_time_ms"] > 0]
        avg_response_time = None
        median_response_time = None
        if not actual_requests.empty:
            avg_response_time = actual_requests["response_time_ms"].mean()
            median_response_time = actual_requests["response_time_ms"].median()

        # Calculate rates
        piece_rate = 0.0
        if len(piece_with_deals) > 0:
            piece_rate = len(piece_available) / len(piece_with_deals) * 100

        cid_rate = 0.0
        if len(cid_with_deals) > 0:
            cid_rate = len(cid_available) / len(cid_with_deals) * 100

        summary = {
            "total_checks": len(df),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "by_type_status": by_type_status,
            "by_provider_status": by_provider_status,
            "response_times": {
                "avg_ms": avg_response_time,
                "median_ms": median_response_time,
            },
            "availability_rates": {
                "pieces": {
                    "with_deals_total": len(piece_with_deals),
                    "available": len(piece_available),
                    "rate_percent": piece_rate,
                },
                "cids": {
                    "with_deals_total": len(cid_with_deals),
                    "available": len(cid_available),
                    "rate_percent": cid_rate,
                },
            },
            "no_active_deal_counts": {
                "pieces": len(piece_df[piece_df["status"] == "no active deal"]),
                "cids": len(cid_df[cid_df["status"] == "no active deal"]),
            },
        }

        return summary


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Check retrieval status for pieces and CIDs from storage providers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic run using config.json defaults
  python check_retrieval_status.py

  # Specify preparations and concurrency
  python check_retrieval_status.py --prep-ids 1 2 3 --concurrency 20

  # Re-check items that previously had no active deals
  python check_retrieval_status.py --check-no-deals

  # Fresh start (backup existing checkpoint)
  python check_retrieval_status.py --refresh

  # Use custom config and checkpoint
  python check_retrieval_status.py --config my_config.json --checkpoint my_checkpoint.parquet
        """,
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file. Defaults to config.json in project root.",
    )
    parser.add_argument(
        "--deals-file",
        type=Path,
        default=None,
        help="Path to deals.json file. Defaults to config.json paths.deals_file.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory containing file metadata CSV files. Defaults to config.json paths.file_metadata_dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for results. Defaults to config.json paths.retrieval_status_dir.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to checkpoint parquet file (default: <output_dir>/checkpoint.parquet)",
    )
    parser.add_argument(
        "--prep-ids",
        type=int,
        nargs="+",
        default=None,
        help="Preparation IDs to filter by (default: all preparations)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for checkpointing. Defaults to config.json retrieval_defaults.batch_size.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent requests. Defaults to config.json retrieval_defaults.concurrency.",
    )
    parser.add_argument(
        "--check-no-deals",
        action="store_true",
        help="Re-check items that previously had 'no active deal' status",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Start fresh (backup existing checkpoint first)",
    )

    return parser.parse_args()


async def main() -> None:
    """Main function to run retrieval status checks."""
    args = parse_args()

    # Load config (shared module handles defaults and merging)
    config = load_config(args.config)

    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Starting retrieval status check")
    logger.info("=" * 60)

    # Log config source
    if args.config and args.config.exists():
        logger.info(f"Loaded config from {args.config}")
    else:
        logger.info("Using default config (config.json in project root or built-in defaults)")

    # Resolve paths: CLI override > config value
    output_dir = args.output_dir or get_path(config, "retrieval_status_dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    input_dir = args.input_dir or get_path(config, "file_metadata_dir")
    logger.info(f"Input directory: {input_dir}")

    deals_file = args.deals_file or get_path(config, "deals_file")
    logger.info(f"Deals file: {deals_file}")

    # Get storage providers from shared config
    storage_providers = get_storage_providers(config)
    logger.info(
        f"Using {len(storage_providers)} storage providers: "
        f"{list(storage_providers.keys())}"
    )

    # Load deals
    deals_map = load_deals(deals_file, logger)
    if not deals_map:
        logger.error("No active deals found. Cannot proceed.")
        return

    # Determine checkpoint path
    checkpoint_path = args.checkpoint or (output_dir / "checkpoint.parquet")

    # Handle refresh mode
    if args.refresh and checkpoint_path.exists():
        backup_checkpoint(checkpoint_path, logger)
        checkpoint_path.unlink()
        logger.info("Starting fresh (removed existing checkpoint)")

    # Load existing checkpoint
    checkpoint_df = load_checkpoint(checkpoint_path, logger)

    # Find CSV files
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        return

    logger.info(f"Found {len(csv_files)} CSV files to process")
    for csv_file in csv_files:
        logger.info(f"  - {csv_file.name}")

    # Get retrieval defaults: CLI override > config value
    retrieval_defaults = get_retrieval_defaults(config)
    batch_size = args.batch_size or retrieval_defaults.get("batch_size", DEFAULT_BATCH_SIZE)
    concurrency = args.concurrency or retrieval_defaults.get("concurrency", DEFAULT_CONCURRENCY)
    request_timeout = retrieval_defaults.get("request_timeout", DEFAULT_REQUEST_TIMEOUT)

    logger.info(
        f"Settings: batch_size={batch_size}, concurrency={concurrency}, "
        f"timeout={request_timeout}s"
    )

    # Run retrieval checks
    async with RetrievalChecker(
        storage_providers=storage_providers,
        deals_map=deals_map,
        output_dir=output_dir,
        checkpoint_path=checkpoint_path,
        concurrency=concurrency,
        request_timeout=request_timeout,
        logger=logger,
    ) as checker:
        await checker.check_all_retrievals(
            csv_files=csv_files,
            batch_size=batch_size,
            prep_ids=args.prep_ids,
            check_no_deals_only=args.check_no_deals,
            checkpoint_df=checkpoint_df,
        )

        # Save final results
        checker.save_final_results()

        # Generate and save summary
        summary = checker.generate_summary()
        summary_path = output_dir / "retrieval_summary.json"
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info("=" * 60)
        logger.info("Retrieval check complete. Summary:")
        logger.info(f"  Total checks: {summary.get('total_checks', 0)}")

        avail = summary.get("availability_rates", {})
        pieces_avail = avail.get("pieces", {})
        cids_avail = avail.get("cids", {})

        logger.info(
            f"  Pieces: {pieces_avail.get('available', 0)}/"
            f"{pieces_avail.get('with_deals_total', 0)} "
            f"available ({pieces_avail.get('rate_percent', 0):.1f}%)"
        )
        logger.info(
            f"  CIDs: {cids_avail.get('available', 0)}/"
            f"{cids_avail.get('with_deals_total', 0)} "
            f"available ({cids_avail.get('rate_percent', 0):.1f}%)"
        )

        no_deal = summary.get("no_active_deal_counts", {})
        logger.info(
            f"  No active deal: {no_deal.get('pieces', 0)} pieces, "
            f"{no_deal.get('cids', 0)} CIDs"
        )
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
