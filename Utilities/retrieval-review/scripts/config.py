"""
Shared Configuration Module

Provides centralized configuration loading for all scripts in the project.
Configuration is loaded from config.json in the project root directory.

Usage:
    from config import load_config, get_storage_providers, get_api_endpoint

    config = load_config()
    providers = get_storage_providers(config)
    api_url = get_api_endpoint(config)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# Default config file location (project root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# Default configuration values (used when config file doesn't exist or values are missing)
DEFAULT_CONFIG: dict[str, Any] = {
    "singularity_api": {"base_url": ""},
    "storage_providers": {},
    "paths": {
        "output_dir": "./output",
        "deals_file": "./output/deals.json",
        "file_metadata_dir": "./output/file-metadata",
        "piece_metadata_dir": "./output/piece-metadata",
        "retrieval_status_dir": "./output/retrieval-status",
        "error_analysis_dir": "./output/error-analysis",
        "logs_dir": "./output/logs",
        "summary_reports_dir": "./output/summary-reports",
        # Filenames (combined with directories at runtime)
        "piece_status_filename": "final_retrieval_piece_status.json",
        "cid_status_filename": "final_retrieval_cid_status.json",
        "piece_status_postprocessed_filename": "final_retrieval_piece_status_postprocessed.json",
        "cid_status_postprocessed_filename": "final_retrieval_cid_status_postprocessed.json",
        "deals_filename": "deals.json",
        "summary_report_filename": "summary_report.json",
        "cid_errors_filename": "cid_status_errors.json",
        "cid_all_failed_filename": "cid_all_providers_failed.json",
        "error_patterns_filename": "error_patterns_analysis.json",
        "cid_errors_summary_filename": "cid_errors_summary.json",
    },
    "retrieval_defaults": {
        "batch_size": 100,
        "concurrency": 10,
        "request_timeout": 30,
    },
    "fetch_defaults": {
        "concurrency": 20,
    },
}


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """
    Load configuration from JSON file.

    Merges file config with defaults, so missing keys fall back to defaults.

    Args:
        config_path: Path to config file. Defaults to config.json in project root.

    Returns:
        Configuration dictionary with all settings.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    elif isinstance(config_path, str):
        config_path = Path(config_path)

    config = _deep_copy_dict(DEFAULT_CONFIG)

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                file_config = json.load(f)
            # Deep merge file config into defaults
            config = _deep_merge(config, file_config)
        except (json.JSONDecodeError, OSError) as e:
            logging.warning(f"Failed to load config from {config_path}: {e}")
            logging.warning("Using default configuration.")

    return config


def _deep_copy_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Create a deep copy of a dictionary."""
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = _deep_copy_dict(value)
        elif isinstance(value, list):
            result[key] = value.copy()
        else:
            result[key] = value
    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge override into base dictionary.

    Args:
        base: Base dictionary with defaults.
        override: Dictionary with override values.

    Returns:
        Merged dictionary.
    """
    result = _deep_copy_dict(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get_storage_providers(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """
    Get storage provider configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary mapping provider_id to provider config (name, retrieval_endpoint).
    """
    return config.get("storage_providers", DEFAULT_CONFIG["storage_providers"])


def get_api_endpoint(config: dict[str, Any]) -> str:
    """
    Get Singularity API base URL.

    Args:
        config: Configuration dictionary.

    Returns:
        API base URL string.
    """
    api_config = config.get("singularity_api", {})
    return api_config.get("base_url", DEFAULT_CONFIG["singularity_api"]["base_url"])


def get_path(config: dict[str, Any], key: str) -> Path:
    """
    Get a path from configuration.

    Args:
        config: Configuration dictionary.
        key: Path key (e.g., "deals_file", "output_dir").

    Returns:
        Path object for the specified key.
    """
    paths = config.get("paths", {})
    default_paths = DEFAULT_CONFIG["paths"]
    path_str = paths.get(key, default_paths.get(key, "."))
    return Path(path_str)


# Mapping from file keys to their parent directory keys
_FILE_TO_DIR_MAP = {
    "piece_status_filename": "retrieval_status_dir",
    "cid_status_filename": "retrieval_status_dir",
    "piece_status_postprocessed_filename": "retrieval_status_dir",
    "cid_status_postprocessed_filename": "retrieval_status_dir",
    "summary_report_filename": "summary_reports_dir",
    "cid_errors_filename": "error_analysis_dir",
    "cid_all_failed_filename": "error_analysis_dir",
    "error_patterns_filename": "error_analysis_dir",
    "cid_errors_summary_filename": "error_analysis_dir",
    "deals_filename": "output_dir",
}


def get_file_path(config: dict[str, Any], filename_key: str) -> Path:
    """
    Get a full file path by combining directory and filename from configuration.

    Args:
        config: Configuration dictionary.
        filename_key: Filename key (e.g., "piece_status_filename", "summary_report_filename").

    Returns:
        Full Path object combining directory and filename.

    Raises:
        ValueError: If filename_key is not a known filename configuration key.
    """
    if filename_key not in _FILE_TO_DIR_MAP:
        raise ValueError(
            f"Unknown filename key: {filename_key}. "
            f"Valid keys: {list(_FILE_TO_DIR_MAP.keys())}"
        )

    dir_key = _FILE_TO_DIR_MAP[filename_key]
    directory = get_path(config, dir_key)
    filename = get_path(config, filename_key)
    return directory / filename


def get_retrieval_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get retrieval script defaults.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with batch_size, concurrency, request_timeout.
    """
    return config.get("retrieval_defaults", DEFAULT_CONFIG["retrieval_defaults"])


def get_fetch_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get fetch script defaults.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with concurrency settings.
    """
    return config.get("fetch_defaults", DEFAULT_CONFIG["fetch_defaults"])


def normalize_api_endpoint(endpoint: str) -> str:
    """
    Normalize the API endpoint URL to ensure it ends with '/api'.

    Args:
        endpoint: The base URL provided by the user.

    Returns:
        The normalized URL ending with '/api'.
    """
    # Remove trailing slashes
    endpoint = endpoint.rstrip("/")

    # Check if endpoint already ends with '/api'
    if endpoint.endswith("/api"):
        return endpoint

    # Append '/api' if not present
    return f"{endpoint}/api"
