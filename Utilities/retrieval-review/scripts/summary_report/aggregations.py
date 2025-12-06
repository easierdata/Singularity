"""
Aggregation Functions for Summary Report Generation

Functions for computing aggregated metrics grouped by preparation ID
or storage provider. These functions build on the base metrics functions
to provide higher-level summaries.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple

from .metrics import (
    compute_filesize_breakdown,
    compute_filetype_breakdown,
    compute_outcome_metrics,
    compute_unique_metrics,
)
from .utils import is_success


def compute_preparation_metrics(
    piece_checks: List[Dict],
    cid_checks: List[Dict],
    active_deals: Set[Tuple[str, str]],
    piece_non_active: List[Dict],
    cid_non_active: List[Dict],
) -> Dict[str, Dict[str, Any]]:
    """Compute metrics grouped by preparation ID.

    Groups all check data by preparation and computes piece/CID metrics,
    file type breakdowns, file size breakdowns, and non-active deal counts
    for each preparation.

    Args:
        piece_checks: List of piece check records for active deals
        cid_checks: List of CID check records for active deals
        active_deals: Set of (pieceCid, provider_id) tuples for active deals
        piece_non_active: List of piece check records not in active deals
        cid_non_active: List of CID check records not in active deals

    Returns:
        Dict mapping preparation ID to metrics dict containing:
        - piece_metrics: success/failure counts for pieces
        - cid_metrics: success/failure counts for CIDs
        - by_filetype: metrics broken down by file type
        - by_filesize_bucket: metrics broken down by file size
        - non_active_deals: counts of items not in active deals
    """
    # Group by preparation
    piece_by_prep: Dict[str, List[Dict]] = defaultdict(list)
    cid_by_prep: Dict[str, List[Dict]] = defaultdict(list)
    piece_non_active_by_prep: Dict[str, List[Dict]] = defaultdict(list)
    cid_non_active_by_prep: Dict[str, List[Dict]] = defaultdict(list)

    for check in piece_checks:
        prep = check.get("preparation", "unknown")
        piece_by_prep[prep].append(check)

    for check in cid_checks:
        prep = check.get("preparation", "unknown")
        cid_by_prep[prep].append(check)

    for check in piece_non_active:
        prep = check.get("preparation", "unknown")
        piece_non_active_by_prep[prep].append(check)

    for check in cid_non_active:
        prep = check.get("preparation", "unknown")
        cid_non_active_by_prep[prep].append(check)

    # Get all preparation IDs
    all_preps = (
        set(piece_by_prep.keys())
        | set(cid_by_prep.keys())
        | set(piece_non_active_by_prep.keys())
        | set(cid_non_active_by_prep.keys())
    )

    result = {}
    for prep in sorted(all_preps, key=lambda x: (x.isdigit(), x)):
        p_checks = piece_by_prep.get(prep, [])
        c_checks = cid_by_prep.get(prep, [])
        p_non_active = piece_non_active_by_prep.get(prep, [])
        c_non_active = cid_non_active_by_prep.get(prep, [])

        # Piece metrics
        p_outcomes = compute_outcome_metrics(p_checks)
        p_unique = compute_unique_metrics(p_checks, "pieceCid", active_deals)
        unique_pieces = len({c.get("pieceCid") for c in p_checks if c.get("pieceCid")})

        piece_metrics = {
            "pieces_in_active_deals": unique_pieces,
            "piece_retrieval_checks": len(p_checks),
            **p_outcomes,
            "unique_pieces_with_any_provider_success": p_unique.get(
                "unique_piececids_with_any_provider_success", 0
            ),
            "unique_pieces_all_providers_success": p_unique.get(
                "unique_piececids_all_providers_success", 0
            ),
            "unique_pieces_all_providers_failed": p_unique.get(
                "unique_piececids_all_providers_failed", 0
            ),
        }

        # CID metrics
        c_outcomes = compute_outcome_metrics(c_checks)
        c_unique = compute_unique_metrics(c_checks, "cid", active_deals)
        unique_cids = len({c.get("cid") for c in c_checks if c.get("cid")})

        cid_metrics = {
            "cids_in_active_deals": unique_cids,
            "cid_retrieval_checks": len(c_checks),
            **c_outcomes,
            "unique_cids_with_any_provider_success": c_unique.get(
                "unique_cids_with_any_provider_success", 0
            ),
            "unique_cids_all_providers_success": c_unique.get(
                "unique_cids_all_providers_success", 0
            ),
            "unique_cids_all_providers_failed": c_unique.get(
                "unique_cids_all_providers_failed", 0
            ),
        }

        # Non-active deals metrics for this preparation
        non_active_pieces = {c.get("pieceCid") for c in p_non_active if c.get("pieceCid")}
        non_active_cids = {c.get("cid") for c in c_non_active if c.get("cid")}
        non_active_metrics = {
            "unique_pieces_not_in_active_deals": len(non_active_pieces),
            "unique_cids_not_in_active_deals": len(non_active_cids),
            "piece_retrieval_checks_not_in_active_deals": len(p_non_active),
            "cid_retrieval_checks_not_in_active_deals": len(c_non_active),
        }

        result[prep] = {
            "piece_metrics": piece_metrics,
            "cid_metrics": cid_metrics,
            "by_filetype": compute_filetype_breakdown(c_checks),
            "by_filesize_bucket": compute_filesize_breakdown(c_checks),
            "non_active_deals": non_active_metrics,
        }

    return result


def compute_provider_metrics(
    piece_checks: List[Dict],
    cid_checks: List[Dict],
    piece_non_active: List[Dict],
    cid_non_active: List[Dict],
) -> Dict[str, Dict[str, Any]]:
    """Compute metrics grouped by storage provider.

    Groups all check data by provider ID and computes piece/CID metrics,
    file type breakdowns, file size breakdowns, and non-active deal counts
    for each provider.

    Args:
        piece_checks: List of piece check records for active deals
        cid_checks: List of CID check records for active deals
        piece_non_active: List of piece check records not in active deals
        cid_non_active: List of CID check records not in active deals

    Returns:
        Dict mapping provider ID to metrics dict containing:
        - providerid: the provider ID
        - providername: most common name seen for this provider
        - piece_metrics: success/failure counts for pieces
        - cid_metrics: success/failure counts for CIDs
        - by_filetype: metrics broken down by file type
        - by_filesize_bucket: metrics broken down by file size
        - non_active_deals: counts of items not in active deals
    """
    # Group by provider
    piece_by_prov: Dict[str, List[Dict]] = defaultdict(list)
    cid_by_prov: Dict[str, List[Dict]] = defaultdict(list)
    piece_non_active_by_prov: Dict[str, List[Dict]] = defaultdict(list)
    cid_non_active_by_prov: Dict[str, List[Dict]] = defaultdict(list)
    provider_names: Dict[str, Counter] = defaultdict(Counter)

    for check in piece_checks:
        prov = check.get("provider_id", "unknown")
        piece_by_prov[prov].append(check)
        if check.get("provider_name"):
            provider_names[prov][check["provider_name"]] += 1

    for check in cid_checks:
        prov = check.get("provider_id", "unknown")
        cid_by_prov[prov].append(check)
        if check.get("provider_name"):
            provider_names[prov][check["provider_name"]] += 1

    for check in piece_non_active:
        prov = check.get("provider_id", "unknown")
        piece_non_active_by_prov[prov].append(check)

    for check in cid_non_active:
        prov = check.get("provider_id", "unknown")
        cid_non_active_by_prov[prov].append(check)

    all_providers = (
        set(piece_by_prov.keys())
        | set(cid_by_prov.keys())
        | set(piece_non_active_by_prov.keys())
        | set(cid_non_active_by_prov.keys())
    )

    result = {}
    for prov in sorted(all_providers):
        p_checks = piece_by_prov.get(prov, [])
        c_checks = cid_by_prov.get(prov, [])
        p_non_active = piece_non_active_by_prov.get(prov, [])
        c_non_active = cid_non_active_by_prov.get(prov, [])

        # Get most common provider name
        name_counter = provider_names.get(prov, Counter())
        prov_name = name_counter.most_common(1)[0][0] if name_counter else ""

        # Piece metrics
        p_outcomes = compute_outcome_metrics(p_checks)
        unique_pieces = {c.get("pieceCid") for c in p_checks if c.get("pieceCid")}
        pieces_with_success = set()
        pieces_all_failed = set()

        # Group piece checks by pieceCid for this provider
        piece_by_cid: Dict[str, List[Dict]] = defaultdict(list)
        for c in p_checks:
            if c.get("pieceCid"):
                piece_by_cid[c["pieceCid"]].append(c)

        for pcid, pcid_checks in piece_by_cid.items():
            successes = [
                is_success(c.get("status"), c.get("status_code")) for c in pcid_checks
            ]
            if any(successes):
                pieces_with_success.add(pcid)
            if not any(successes) and successes:
                pieces_all_failed.add(pcid)

        piece_metrics = {
            "pieces_in_active_deals": len(unique_pieces),
            "piece_retrieval_checks": len(p_checks),
            **p_outcomes,
            "unique_pieces_with_success": len(pieces_with_success),
            "unique_pieces_all_checks_failed": len(pieces_all_failed),
        }

        # CID metrics
        c_outcomes = compute_outcome_metrics(c_checks)
        unique_cids = {c.get("cid") for c in c_checks if c.get("cid")}
        cids_with_success = set()
        cids_all_failed = set()

        cid_by_cid: Dict[str, List[Dict]] = defaultdict(list)
        for c in c_checks:
            if c.get("cid"):
                cid_by_cid[c["cid"]].append(c)

        for cid, cid_checks_list in cid_by_cid.items():
            successes = [
                is_success(c.get("status"), c.get("status_code")) for c in cid_checks_list
            ]
            if any(successes):
                cids_with_success.add(cid)
            if not any(successes) and successes:
                cids_all_failed.add(cid)

        cid_metrics = {
            "cids_in_active_deals": len(unique_cids),
            "cid_retrieval_checks": len(c_checks),
            **c_outcomes,
            "unique_cids_with_success": len(cids_with_success),
            "unique_cids_all_checks_failed": len(cids_all_failed),
        }

        # Non-active deals metrics for this provider
        non_active_pieces = {c.get("pieceCid") for c in p_non_active if c.get("pieceCid")}
        non_active_cids = {c.get("cid") for c in c_non_active if c.get("cid")}
        non_active_metrics = {
            "unique_pieces_not_in_active_deals": len(non_active_pieces),
            "unique_cids_not_in_active_deals": len(non_active_cids),
            "piece_retrieval_checks_not_in_active_deals": len(p_non_active),
            "cid_retrieval_checks_not_in_active_deals": len(c_non_active),
        }

        result[prov] = {
            "providerid": prov,
            "providername": prov_name,
            "piece_metrics": piece_metrics,
            "cid_metrics": cid_metrics,
            "by_filetype": compute_filetype_breakdown(c_checks),
            "by_filesize_bucket": compute_filesize_breakdown(c_checks),
            "non_active_deals": non_active_metrics,
        }

    return result
