"""Prepared content metrics computation helpers.

This module provides helper functions for computing metrics from prepared
file-metadata and piece-metadata, tracing retrievability through to storage providers.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from .constants import SIZE_BUCKETS
from .utils import bucket_filesize, is_success


@dataclass
class RetrievalLookups:
    """Container for retrieval lookup structures built from check data."""

    # cid -> provider_id -> bool (success/failure)
    cid_retrieval_results: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    # cid -> set of provider_ids that have active deals
    cid_active_providers: Dict[str, Set[str]] = field(default_factory=dict)
    # pieceCid -> provider_id -> bool (success/failure)
    piece_retrieval_results: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    # pieceCid -> set of provider_ids that have active deals
    piece_active_providers: Dict[str, Set[str]] = field(default_factory=dict)
    # provider_id -> provider_name
    provider_names: Dict[str, str] = field(default_factory=dict)
    # All provider IDs seen
    all_providers: Set[str] = field(default_factory=set)

    @property
    def sorted_providers(self) -> List[str]:
        """Return sorted list of all provider IDs."""
        return sorted(self.all_providers)


def build_retrieval_lookups(
    cid_active: List[Dict],
    cid_non_active: List[Dict],
    piece_active: List[Dict],
    piece_non_active: List[Dict],
) -> RetrievalLookups:
    """Build lookup structures from retrieval check data.

    Args:
        cid_active: CID retrieval checks for active deals
        cid_non_active: CID retrieval checks for non-active deals
        piece_active: Piece retrieval checks for active deals
        piece_non_active: Piece retrieval checks for non-active deals

    Returns:
        RetrievalLookups containing all lookup structures
    """
    lookups = RetrievalLookups(
        cid_retrieval_results=defaultdict(dict),
        cid_active_providers=defaultdict(set),
        piece_retrieval_results=defaultdict(dict),
        piece_active_providers=defaultdict(set),
        provider_names={},
        all_providers=set(),
    )

    # Build CID lookup structures
    for check in cid_active:
        cid = check.get("cid")
        provider_id = check.get("provider_id")
        if cid and provider_id:
            success = is_success(check.get("status"), check.get("status_code"))
            lookups.cid_retrieval_results[cid][provider_id] = success
            lookups.cid_active_providers[cid].add(provider_id)
            lookups.all_providers.add(provider_id)

    # Build piece lookup structures
    for check in piece_active:
        piece_cid = check.get("pieceCid")
        provider_id = check.get("provider_id")
        if piece_cid and provider_id:
            success = is_success(check.get("status"), check.get("status_code"))
            lookups.piece_retrieval_results[piece_cid][provider_id] = success
            lookups.piece_active_providers[piece_cid].add(provider_id)
            lookups.all_providers.add(provider_id)

    # Collect provider names from all sources
    for check in cid_active + cid_non_active + piece_active + piece_non_active:
        provider_id = check.get("provider_id")
        provider_name = check.get("provider_name")
        if provider_id and provider_name and provider_id not in lookups.provider_names:
            lookups.provider_names[provider_id] = provider_name
        if provider_id:
            lookups.all_providers.add(provider_id)

    return lookups


@dataclass
class RetrievabilityCounts:
    """Counts for retrievability metrics."""

    retrievable_by_any: int = 0
    retrievable_by_all: int = 0
    not_retrievable_by_any: int = 0
    not_in_any_active_deals: int = 0


def compute_retrievability_counts(
    unique_ids: Set[str],
    retrievability_info: Dict[str, Dict[str, Any]],
) -> RetrievabilityCounts:
    """Compute retrievability counts for a set of CIDs or piece CIDs.

    This is a reusable function for computing how many items are:
    - Retrievable by at least one provider
    - Retrievable by all providers with active deals
    - Not retrievable by any provider
    - Not in any active deals

    Args:
        unique_ids: Set of CIDs or piece CIDs to analyze
        retrievability_info: Dict mapping id -> {providers_with_active_deals, provider_results}

    Returns:
        RetrievabilityCounts with the computed metrics
    """
    counts = RetrievabilityCounts()

    for item_id in unique_ids:
        info = retrievability_info.get(item_id, {})
        providers_with_deals = info.get("providers_with_active_deals", set())
        results = info.get("provider_results", {})

        if not providers_with_deals:
            counts.not_in_any_active_deals += 1
            continue

        successes = [results.get(p, False) for p in providers_with_deals]
        if any(successes):
            counts.retrievable_by_any += 1
        if all(successes) and successes:
            counts.retrievable_by_all += 1
        if not any(successes) and successes:
            counts.not_retrievable_by_any += 1

    return counts


def compute_per_provider_counts(
    unique_ids: Set[str],
    retrievability_info: Dict[str, Dict[str, Any]],
    provider_names: Dict[str, str],
    sorted_providers: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Compute per-provider retrievability counts for a set of CIDs or piece CIDs.

    Args:
        unique_ids: Set of CIDs or piece CIDs to analyze
        retrievability_info: Dict mapping id -> {providers_with_active_deals, provider_results}
        provider_names: Dict mapping provider_id -> provider_name
        sorted_providers: Sorted list of all provider IDs

    Returns:
        Dict mapping provider_id -> {provider_name, retrievable, not_retrievable, not_in_deals}
    """
    result = {}

    for provider_id in sorted_providers:
        prov_name = provider_names.get(provider_id, "")
        retrievable = 0
        not_retrievable = 0
        not_in_deals = 0

        for item_id in unique_ids:
            info = retrievability_info.get(item_id, {})
            providers_with_deals = info.get("providers_with_active_deals", set())
            results = info.get("provider_results", {})

            if provider_id not in providers_with_deals:
                not_in_deals += 1
            elif results.get(provider_id, False):
                retrievable += 1
            else:
                not_retrievable += 1

        result[provider_id] = {
            "provider_name": prov_name,
            "retrievable": retrievable,
            "not_retrievable": not_retrievable,
            "not_in_deals": not_in_deals,
        }

    return result


def compute_prep_filetype_breakdown(
    unique_cids: Set[str],
    cid_attributes: Dict[str, Dict[str, Any]],
    retrievability_info: Dict[str, Dict[str, Any]],
    provider_names: Dict[str, str],
    sorted_providers: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Compute filetype breakdown for a preparation.

    Args:
        unique_cids: Set of unique CIDs in this preparation
        cid_attributes: Dict mapping cid -> {filetype, size}
        retrievability_info: Dict mapping cid -> {providers_with_active_deals, provider_results}
        provider_names: Dict mapping provider_id -> provider_name
        sorted_providers: Sorted list of all provider IDs

    Returns:
        Dict mapping filetype -> {unique_cids, by_provider: {provider_id: {...}}}
    """
    by_filetype: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "unique_cids": 0,
        "by_provider": {p: {"retrievable": 0, "not_retrievable": 0, "not_in_deals": 0}
                        for p in sorted_providers}
    })

    for cid in unique_cids:
        attrs = cid_attributes.get(cid, {})
        filetype = attrs.get("filetype", "unknown")

        by_filetype[filetype]["unique_cids"] += 1

        # Per-provider breakdown for this filetype
        info = retrievability_info.get(cid, {})
        providers_with_deals = info.get("providers_with_active_deals", set())
        results = info.get("provider_results", {})

        for provider_id in sorted_providers:
            if provider_id not in providers_with_deals:
                by_filetype[filetype]["by_provider"][provider_id]["not_in_deals"] += 1
            elif results.get(provider_id, False):
                by_filetype[filetype]["by_provider"][provider_id]["retrievable"] += 1
            else:
                by_filetype[filetype]["by_provider"][provider_id]["not_retrievable"] += 1

    # Convert defaultdict to regular dict and add provider names
    result = {}
    for ft, data in sorted(by_filetype.items()):
        result[ft] = {
            "unique_cids": data["unique_cids"],
            "by_provider": {
                p: {
                    "provider_name": provider_names.get(p, ""),
                    **data["by_provider"][p]
                }
                for p in sorted_providers
            }
        }

    return result


def compute_prep_filesize_breakdown(
    unique_cids: Set[str],
    cid_attributes: Dict[str, Dict[str, Any]],
    retrievability_info: Dict[str, Dict[str, Any]],
    provider_names: Dict[str, str],
    sorted_providers: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Compute filesize bucket breakdown for a preparation.

    Args:
        unique_cids: Set of unique CIDs in this preparation
        cid_attributes: Dict mapping cid -> {filetype, size}
        retrievability_info: Dict mapping cid -> {providers_with_active_deals, provider_results}
        provider_names: Dict mapping provider_id -> provider_name
        sorted_providers: Sorted list of all provider IDs

    Returns:
        Dict mapping bucket -> {unique_cids, by_provider: {provider_id: {...}}}
    """
    by_filesize: Dict[str, Dict[str, Any]] = {}

    # Initialize all standard buckets
    for bucket_label, _, _ in SIZE_BUCKETS:
        by_filesize[bucket_label] = {
            "unique_cids": 0,
            "by_provider": {p: {"retrievable": 0, "not_retrievable": 0, "not_in_deals": 0}
                            for p in sorted_providers}
        }

    for cid in unique_cids:
        attrs = cid_attributes.get(cid, {})
        size = attrs.get("size")
        bucket = bucket_filesize(size)

        if bucket not in by_filesize:
            by_filesize[bucket] = {
                "unique_cids": 0,
                "by_provider": {p: {"retrievable": 0, "not_retrievable": 0, "not_in_deals": 0}
                                for p in sorted_providers}
            }

        by_filesize[bucket]["unique_cids"] += 1

        # Per-provider breakdown for this size bucket
        info = retrievability_info.get(cid, {})
        providers_with_deals = info.get("providers_with_active_deals", set())
        results = info.get("provider_results", {})

        for provider_id in sorted_providers:
            if provider_id not in providers_with_deals:
                by_filesize[bucket]["by_provider"][provider_id]["not_in_deals"] += 1
            elif results.get(provider_id, False):
                by_filesize[bucket]["by_provider"][provider_id]["retrievable"] += 1
            else:
                by_filesize[bucket]["by_provider"][provider_id]["not_retrievable"] += 1

    # Convert to final format with provider names
    result = {}
    for bucket, data in by_filesize.items():
        result[bucket] = {
            "unique_cids": data["unique_cids"],
            "by_provider": {
                p: {
                    "provider_name": provider_names.get(p, ""),
                    **data["by_provider"][p]
                }
                for p in sorted_providers
            }
        }

    return result


def collect_cid_info_from_metadata(
    file_metadata: Dict[str, Dict[str, Any]],
    cid_active_providers: Dict[str, Set[str]],
    cid_retrieval_results: Dict[str, Dict[str, bool]],
) -> Tuple[int, Set[str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Collect CID info from file-metadata.

    Args:
        file_metadata: Dict mapping prep_id -> {files: [...], cid_attributes: {...}, ...}
        cid_active_providers: Dict mapping cid -> set of provider_ids with active deals
        cid_retrieval_results: Dict mapping cid -> provider_id -> success bool

    Returns:
        Tuple of:
        - total_files: Total file count across all preps
        - unique_cids: Set of all unique CIDs
        - cids_retrievability: Dict mapping cid -> retrieval info
        - cids_attributes: Dict mapping cid -> {filetype, size}
    """
    total_files = 0
    unique_cids: Set[str] = set()
    cids_retrievability: Dict[str, Dict[str, Any]] = {}
    cids_attributes: Dict[str, Dict[str, Any]] = {}

    for prep_data in file_metadata.values():
        prep_cid_attributes = prep_data.get("cid_attributes", {})

        for f in prep_data["files"]:
            total_files += 1
            cid = f.get("cid")
            if cid:
                unique_cids.add(cid)
                if cid not in cids_retrievability:
                    cids_retrievability[cid] = {
                        "providers_with_active_deals": cid_active_providers.get(cid, set()),
                        "provider_results": cid_retrieval_results.get(cid, {}),
                    }
                # "First one in" globally: use attributes from first prep that has this CID
                if cid not in cids_attributes and cid in prep_cid_attributes:
                    cids_attributes[cid] = prep_cid_attributes[cid]

    return total_files, unique_cids, cids_retrievability, cids_attributes


def collect_piece_info_from_metadata(
    piece_metadata: Dict[str, Dict[str, Any]],
    piece_active_providers: Dict[str, Set[str]],
    piece_retrieval_results: Dict[str, Dict[str, bool]],
) -> Tuple[int, Set[str], Dict[str, Dict[str, Any]]]:
    """Collect piece info from piece-metadata.

    Args:
        piece_metadata: Dict mapping prep_id -> {pieces: [...], ...}
        piece_active_providers: Dict mapping pieceCid -> set of provider_ids with active deals
        piece_retrieval_results: Dict mapping pieceCid -> provider_id -> success bool

    Returns:
        Tuple of:
        - total_pieces: Total piece count across all preps
        - unique_piece_cids: Set of all unique piece CIDs
        - pieces_retrievability: Dict mapping pieceCid -> retrieval info
    """
    total_pieces = 0
    unique_piece_cids: Set[str] = set()
    pieces_retrievability: Dict[str, Dict[str, Any]] = {}

    for prep_data in piece_metadata.values():
        for p in prep_data["pieces"]:
            total_pieces += 1
            piece_cid = p.get("pieceCid")
            if piece_cid:
                unique_piece_cids.add(piece_cid)
                if piece_cid not in pieces_retrievability:
                    pieces_retrievability[piece_cid] = {
                        "providers_with_active_deals": piece_active_providers.get(piece_cid, set()),
                        "provider_results": piece_retrieval_results.get(piece_cid, {}),
                    }

    return total_pieces, unique_piece_cids, pieces_retrievability
