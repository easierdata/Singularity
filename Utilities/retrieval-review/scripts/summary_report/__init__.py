"""
Summary Report Package for Filecoin Retrieval Checks

This package provides utilities for generating summary reports from
Filecoin retrieval check results.
"""

from .aggregations import compute_preparation_metrics, compute_provider_metrics
from .constants import GIB, MIB, SIZE_BUCKETS
from .error_analysis import compute_error_analysis
from .loaders import (
    build_active_deals_set,
    extract_retrieval_checks,
    load_file_metadata_csvs,
    load_json_file,
    load_piece_metadata_jsons,
)
from .metrics import (
    compute_filesize_breakdown,
    compute_filetype_breakdown,
    compute_outcome_metrics,
    compute_unique_metrics,
)
from .prepared_content import (
    RetrievabilityCounts,
    RetrievalLookups,
    build_retrieval_lookups,
    collect_cid_info_from_metadata,
    collect_piece_info_from_metadata,
    compute_per_provider_counts,
    compute_prep_filesize_breakdown,
    compute_prep_filetype_breakdown,
    compute_retrievability_counts,
)
from .utils import bucket_filesize, extract_filetype, is_success, safe_rate

__all__ = [
    "GIB",
    "MIB",
    "SIZE_BUCKETS",
    "RetrievabilityCounts",
    "RetrievalLookups",
    "bucket_filesize",
    "build_active_deals_set",
    "build_retrieval_lookups",
    "collect_cid_info_from_metadata",
    "collect_piece_info_from_metadata",
    "compute_error_analysis",
    "compute_filesize_breakdown",
    "compute_filetype_breakdown",
    "compute_outcome_metrics",
    "compute_per_provider_counts",
    "compute_prep_filesize_breakdown",
    "compute_prep_filetype_breakdown",
    "compute_preparation_metrics",
    "compute_provider_metrics",
    "compute_retrievability_counts",
    "compute_unique_metrics",
    "extract_filetype",
    "extract_retrieval_checks",
    "is_success",
    "load_file_metadata_csvs",
    "load_json_file",
    "load_piece_metadata_jsons",
    "safe_rate",
]
