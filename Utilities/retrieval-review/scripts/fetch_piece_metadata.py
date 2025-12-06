#!/usr/bin/env python3
"""
Fetch Piece Metadata Script

A CLI tool to fetch piece metadata from the Singularity API and export to JSON.
Retrieves all piece data for specified preparation IDs in a single API call per preparation.

Usage:
    python fetch_piece_metadata.py                                    # Uses config.json defaults
    python fetch_piece_metadata.py --endpoint "http://212.6.53.5:9090"  # Override endpoint
    python fetch_piece_metadata.py --prep-ids 1 2 3                   # Specific preparations
    python fetch_piece_metadata.py --output ./my_output.json          # Override output
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import requests

from config import get_api_endpoint, get_path, load_config, normalize_api_endpoint

# Log directory and file configuration
LOG_DIR = Path("./output/logs")
LOG_FILE = LOG_DIR / "fetch_piece_metadata.log"


def setup_logging() -> logging.Logger:
    """
    Configure logging to write to both console and log file.

    Returns:
        Configured logger instance.
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("fetch_piece_metadata")
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


def get_piece_metadata(base_url: str, prep_id: int) -> tuple[Any, str | None]:
    """
    Fetch all piece metadata for a preparation in a single API call.

    Args:
        base_url: The base API URL.
        prep_id: The preparation ID.

    Returns:
        Tuple of (piece metadata response, source name or None).
    """
    piece_response = make_get_request(base_url, f"/preparation/{prep_id}/piece")
    source_name = None

    if piece_response and isinstance(piece_response, list) and len(piece_response) > 0:
        # Extract source name from the first item's source object
        source_obj = piece_response[0].get("source", {})
        source_name = source_obj.get("path", "").split("/")[-1] if source_obj.get("path") else None
        # Fallback to source name if path extraction fails
        if not source_name:
            source_name = source_obj.get("name")

    return piece_response, source_name


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
    return f"{clean_name}_prep{prep_id}_details.json"


def main() -> None:
    # Load configuration
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Fetch piece metadata from Singularity API and export to JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all preparations using config.json defaults
  python fetch_piece_metadata.py

  # Override endpoint from config
  python fetch_piece_metadata.py --endpoint "http://212.6.53.5:9090"

  # Fetch specific preparations by ID
  python fetch_piece_metadata.py --prep-ids 1 2 3

  # Save to custom output path
  python fetch_piece_metadata.py --prep-ids 1 --output ./custom_output.json
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
        help="Output file path. Defaults to config.json piece_metadata_dir."
    )

    args = parser.parse_args()

    # Log session start
    logger.info("=" * 60)
    logger.info("Starting fetch_piece_metadata session")
    logger.info("=" * 60)

    # Determine API endpoint: CLI override > config
    if args.endpoint:
        base_url = normalize_api_endpoint(args.endpoint)
        logger.info(f"Using CLI-specified endpoint: {base_url}")
    else:
        base_url = get_api_endpoint(config)
        logger.info(f"Using config endpoint: {base_url}")

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

        logger.info(f"Fetching piece metadata for preparation '{prep_name}' (ID: {prep_id})...")
        piece_metadata, source_name = get_piece_metadata(base_url, prep_id)

        if not piece_metadata:
            logger.warning(f"  No piece metadata found for preparation {prep_id}. Skipping...")
            continue

        # Count pieces
        total_pieces = sum(len(item.get("pieces", [])) for item in piece_metadata)
        logger.info(f"  Found {total_pieces} pieces in {len(piece_metadata)} source(s).")

        # Determine output path
        if args.output:
            output_path = Path(args.output)
            # If processing multiple preparations and output is a directory, use auto-naming
            if len(preparations) > 1 and output_path.suffix != ".json":
                output_path.mkdir(parents=True, exist_ok=True)
                filename = generate_output_filename(source_name or prep_name, prep_id)
                output_path = output_path / filename
        else:
            # Default output directory from config
            output_dir = get_path(config, "piece_metadata_dir")
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = generate_output_filename(source_name or prep_name, prep_id)
            output_path = output_dir / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to JSON
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(piece_metadata, f, indent=2)
        logger.info(f"  Saved piece metadata to: {output_path}")

    logger.info("\nDone!")
    logger.info(f"Log file saved to: {LOG_FILE.resolve()}")


if __name__ == "__main__":
    main()
