#!/usr/bin/env python3
"""
Script to fetch deal information from Singularity API and save to JSON file.

Usage:
    python fetch_deals.py                           # Uses config.json defaults
    python fetch_deals.py --base-url http://...     # Override API endpoint
    python fetch_deals.py --output ./my_deals.json  # Override output path
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests

from config import get_api_endpoint, get_path, load_config


def fetch_deals(base_url: str) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
    """Fetch deals data from the Singularity API."""

    # Construct full API endpoint
    url = urljoin(base_url.rstrip("/") + "/", "api/deal")

    # Headers for the request
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        print(f"Fetching deals data from Singularity API: {url}")
        response = requests.post(url, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching deals data: {e}")
        return None


def save_deals_to_file(deals_data: Union[List[Dict[str, Any]], Dict[str, Any]], output_path: Path) -> None:
    """Save deals data to JSON file."""

    try:
        # Ensure output directory exists
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save to JSON file
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(deals_data, f, indent=2, ensure_ascii=False)

        print(f"Deals data saved to: {output_path}")

        # Print summary information
        if isinstance(deals_data, list):
            print(f"Total deals found: {len(deals_data)}")
        elif isinstance(deals_data, dict) and "deals" in deals_data:
            print(f"Total deals found: {len(deals_data['deals'])}")

    except Exception as e:
        print(f"Error saving deals data: {e}")


def main() -> None:
    """Main function to execute the script."""

    # Load configuration
    config = load_config()

    # Get defaults from config
    default_base_url = get_api_endpoint(config)
    default_output = get_path(config, "deals_file")

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Fetch deal information from Singularity API and save to JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use defaults from config.json
  python fetch_deals.py

  # Override API endpoint
  python fetch_deals.py --base-url http://example.com:9090

  # Override output path
  python fetch_deals.py --output ./my_deals.json
        """,
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help=f"Base URL for the Singularity API (default: {default_base_url})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help=f"Output file path (default: {default_output})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: config.json in project root)",
    )

    args = parser.parse_args()

    # Reload config if custom path specified
    if args.config:
        config = load_config(args.config)
        default_base_url = get_api_endpoint(config)
        default_output = get_path(config, "deals_file")

    # Use CLI args or fall back to config defaults
    base_url = args.base_url or default_base_url
    output_path = args.output or default_output

    print(f"Using API endpoint: {base_url}")
    print(f"Output path: {output_path}")
    print("Starting deal data fetch...")

    # Fetch deals data
    deals_data = fetch_deals(base_url)

    if deals_data is not None:
        # Save to file
        save_deals_to_file(deals_data, output_path)
        print("Script completed successfully!")
    else:
        print("Failed to fetch deals data. Script aborted.")


if __name__ == "__main__":
    main()
