#!/usr/bin/env python3
"""
Fetch File Metadata Script

A CLI tool to fetch file metadata from the Singularity API and export to CSV.
Retrieves preparation data, pieces, and file details for specified preparation IDs.

Usage:
    python fetch_file_metadata.py                                    # Uses config.json defaults
    python fetch_file_metadata.py --endpoint "http://212.6.53.5:9090"  # Override endpoint
    python fetch_file_metadata.py --prep-ids 1 2 3                   # Specific preparations
    python fetch_file_metadata.py --output ./my_output.csv           # Override output
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd
import requests

from config import get_api_endpoint, get_path, load_config, normalize_api_endpoint, get_fetch_defaults

# Default concurrency limit for async requests
DEFAULT_CONCURRENCY = 20

# Log directory and file configuration
LOG_DIR = Path("./output/logs")
LOG_FILE = LOG_DIR / "fetch_file_metadata.log"


def setup_logging() -> logging.Logger:
    """
    Configure logging to write to both console and log file.

    Returns:
        Configured logger instance.
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("fetch_file_metadata")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter("%(message)s")

    # File handler - append mode
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()


def make_get_request(base_url: str, endpoint: str) -> Any:
    """
    Make a GET request to a specified endpoint.

    Args:
        base_url: The base API URL.
        endpoint: The API endpoint path.

    Returns:
        JSON response data or None if the request fails.
    """
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json; charset=UTF-8",
    }
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {endpoint}: {e}")
        return None


def get_preparations(base_url: str) -> list[dict[str, Any]]:
    """
    Fetch all preparations from the API.

    Args:
        base_url: The base API URL.

    Returns:
        List of preparation objects.
    """
    preparations_response = make_get_request(base_url, "/preparation")
    if preparations_response and isinstance(preparations_response, list):
        return preparations_response
    return []


def get_pieces_for_preparation(base_url: str, prep_id: int) -> tuple[list[dict], str | None]:
    """
    Fetch pieces for a specific preparation and extract source name.

    Args:
        base_url: The base API URL.
        prep_id: The preparation ID.

    Returns:
        Tuple of (list of pieces, source name or None).
    """
    pieces_response = make_get_request(base_url, f"/preparation/{prep_id}/piece")
    source_name = None

    if pieces_response and isinstance(pieces_response, list):
        # Extract source name from the first item's source object
        if len(pieces_response) > 0:
            source_obj = pieces_response[0].get("source", {})
            source_name = source_obj.get("path", "").split("/")[-1] if source_obj.get("path") else None
            # Fallback to source name if path extraction fails
            if not source_name:
                source_name = source_obj.get("name")

        # Flatten pieces from all sources
        just_the_pieces: list[dict] = []
        for item in pieces_response:
            pieces = item.get("pieces", [])
            for piece in pieces:
                piece["preparationId"] = prep_id
            just_the_pieces.extend(pieces)

        return just_the_pieces, source_name

    return [], None


async def fetch_piece_metadata(
    session: aiohttp.ClientSession,
    base_url: str,
    piece_cid: str,
    root_cid: str,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """
    Fetch metadata for a single piece asynchronously.

    Args:
        session: The aiohttp client session.
        base_url: The base API URL.
        piece_cid: The piece CID to fetch metadata for.
        root_cid: The root CID associated with the piece.
        semaphore: Semaphore to limit concurrent requests.

    Returns:
        List of file detail dictionaries.
    """
    url = f"{base_url}/piece/{piece_cid}/metadata"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json; charset=UTF-8",
    }

    async with semaphore:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                metadata_response = await response.json()
        except Exception as e:
            logger.error(f"  Failed to fetch metadata for piece {piece_cid}: {e}")
            return []

    file_details: list[dict] = []
    if metadata_response and isinstance(metadata_response, dict):
        file_metadata = metadata_response.get("files", [])

        for file in file_metadata:
            file_details_dict: dict = {}
            file_details_dict.update(file)

            # Split the path to extract file name
            file_path = file.get("path", "")
            file_parts = file_path.rsplit("/", 1)
            if len(file_parts) == 2:
                path, file_name = file_parts
            else:
                path, file_name = "", file_parts[0] if file_parts else ""

            file_details_dict["path"] = path
            file_details_dict["fileName"] = file_name
            file_details_dict["rootCid"] = root_cid
            file_details_dict["pieceCid"] = piece_cid
            file_details.append(file_details_dict)

    return file_details


async def get_file_details_from_pieces_async(
    base_url: str,
    pieces_df: pd.DataFrame,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> pd.DataFrame:
    """
    Fetch file details for all pieces concurrently.

    Args:
        base_url: The base API URL.
        pieces_df: DataFrame containing piece information.
        concurrency: Maximum number of concurrent requests.

    Returns:
        DataFrame with file details.
    """
    semaphore = asyncio.Semaphore(concurrency)
    total_pieces = len(pieces_df)
    completed = 0

    async def fetch_with_progress(
        session: aiohttp.ClientSession,
        piece_cid: str,
        root_cid: str,
    ) -> list[dict]:
        nonlocal completed
        result = await fetch_piece_metadata(session, base_url, piece_cid, root_cid, semaphore)
        completed += 1
        if completed % 10 == 0 or completed == total_pieces:
            logger.info(f"  Processing piece {completed}/{total_pieces}...")
        return result

    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_with_progress(session, row["pieceCid"], row["rootCid"])
            for _, row in pieces_df.iterrows()
        ]
        results = await asyncio.gather(*tasks)

    # Flatten results
    all_file_details: list[dict] = []
    for file_list in results:
        all_file_details.extend(file_list)

    return pd.DataFrame(all_file_details)


def get_file_details_from_pieces(
    base_url: str,
    pieces_df: pd.DataFrame,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> pd.DataFrame:
    """
    Fetch file details for each piece from the API (sync wrapper for async function).

    Args:
        base_url: The base API URL.
        pieces_df: DataFrame containing piece information.
        concurrency: Maximum number of concurrent requests.

    Returns:
        DataFrame with file details.
    """
    return asyncio.run(get_file_details_from_pieces_async(base_url, pieces_df, concurrency))


def process_preparation(
    base_url: str,
    prep_id: int,
    prep_name: str,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[pd.DataFrame, str | None]:
    """
    Process a single preparation and return file details.

    Args:
        base_url: The base API URL.
        prep_id: The preparation ID.
        prep_name: The preparation name.
        concurrency: Maximum number of concurrent requests.

    Returns:
        Tuple of (DataFrame with file details, source name).
    """
    logger.info(f"Fetching pieces for preparation '{prep_name}' (ID: {prep_id})...")
    pieces, source_name = get_pieces_for_preparation(base_url, prep_id)

    if not pieces:
        logger.warning(f"  No pieces found for preparation {prep_id}")
        return pd.DataFrame(), source_name

    logger.info(f"  Found {len(pieces)} pieces. Fetching file metadata (concurrency: {concurrency})...")
    pieces_df = pd.DataFrame(pieces)
    file_details_df = get_file_details_from_pieces(base_url, pieces_df, concurrency)

    return file_details_df, source_name


def generate_output_filename(prep_name: str, prep_id: int) -> str:
    """
    Generate output filename based on preparation name and ID.

    Args:
        prep_name: The preparation name.
        prep_id: The preparation ID.

    Returns:
        Formatted filename string.
    """
    # Clean the prep name for use in filename
    clean_name = prep_name.replace(" ", "_").replace("/", "_")
    return f"{clean_name}_prep{prep_id}_details.csv"


def main() -> None:
    # Load configuration
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Fetch file metadata from Singularity API and export to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all preparations using config.json defaults
  python fetch_file_metadata.py

  # Override endpoint from config
  python fetch_file_metadata.py --endpoint "http://212.6.53.5:9090"

  # Fetch specific preparations by ID
  python fetch_file_metadata.py --prep-ids 1 2 3

  # Save to custom output path
  python fetch_file_metadata.py --prep-ids 1 --output ./custom_output.csv
        """
    )

    parser.add_argument(
        "--endpoint", "-e",
        default=None,
        help="Singularity API endpoint URL. Defaults to config.json value."
    )

    parser.add_argument(
        "--prep-ids", "-p",
        type=int,
        nargs="*",
        default=None,
        help="One or more preparation IDs to process. If not provided, all preparations will be processed."
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path. Defaults to config.json file_metadata_dir."
    )

    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Maximum number of concurrent API requests (default: {DEFAULT_CONCURRENCY})"
    )

    args = parser.parse_args()

    # Log session start
    logger.info("=" * 60)
    logger.info("Starting fetch_file_metadata session")
    logger.info("=" * 60)

    # Determine API endpoint: CLI override > config
    if args.endpoint:
        base_url = normalize_api_endpoint(args.endpoint)
        logger.info(f"Using CLI-specified endpoint: {base_url}")
    else:
        # config_endpoint = get_api_endpoint(config)
        base_url = normalize_api_endpoint(get_api_endpoint(config))
        logger.info(f"Using config endpoint: {base_url}")

    # Get fetch defaults: CLI override > config
    fetch_defaults = get_fetch_defaults(config)
    concurrency = args.concurrency or fetch_defaults.get("concurrency", DEFAULT_CONCURRENCY)

    # Fetch all preparations
    logger.info("Fetching preparations list...")
    preparations = get_preparations(base_url)

    if not preparations:
        logger.error("No preparations found or failed to fetch preparations.")
        sys.exit(1)

    logger.info(f"Found {len(preparations)} total preparations.")

    # Filter preparations by ID if specified
    if args.prep_ids:
        prep_id_set = set(args.prep_ids)
        preparations = [p for p in preparations if p.get("id") in prep_id_set]

        if not preparations:
            logger.error(f"No preparations found matching IDs: {args.prep_ids}")
            sys.exit(1)

        logger.info(f"Processing {len(preparations)} preparation(s) matching IDs: {args.prep_ids}")
    else:
        logger.info("Processing all preparations...")

    # Process each preparation
    for prep in preparations:
        prep_id = prep.get("id")
        prep_name = prep.get("name", f"preparation_{prep_id}")

        if prep_id is None:
            logger.warning(f"  Skipping preparation with missing ID: {prep}")
            continue

        file_details_df, source_name = process_preparation(
            base_url, prep_id, prep_name, concurrency
        )

        if file_details_df.empty:
            logger.warning(f"  No file details found for preparation {prep_id}. Skipping...")
            continue

        # Determine output path
        if args.output:
            output_path = Path(args.output)
            # If processing multiple preparations and output is a directory, use auto-naming
            if len(preparations) > 1 and output_path.suffix != ".csv":
                output_path.mkdir(parents=True, exist_ok=True)
                filename = generate_output_filename(source_name or prep_name, prep_id)
                output_path = output_path / filename
        else:
            # Default output directory from config
            output_dir = get_path(config, "file_metadata_dir")
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = generate_output_filename(source_name or prep_name, prep_id)
            output_path = output_dir / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to CSV
        file_details_df.to_csv(output_path, index=False)
        logger.info(f"  Saved {len(file_details_df)} file records to: {output_path}")

    logger.info("\nDone!")
    logger.info(f"Log file saved to: {LOG_FILE.resolve()}")


if __name__ == "__main__":
    main()
