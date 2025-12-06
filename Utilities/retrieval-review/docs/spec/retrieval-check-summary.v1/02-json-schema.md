# JSON Schema Reference

> **Purpose:** Complete schema documentation for `summary_report.json` with field descriptions.

---

## Top-Level Structure

```json
{
  "metadata": { ... },
  "overall_retrieval": { ... },
  "by_preparation": { ... },
  "by_storage_provider": { ... },
  "prepared_content": { ... },
  "error_analysis": { ... }
}
```

---

## 0. metadata

Report generation metadata.

```json
{
  "metadata": {
    "generated_at": "2025-12-05T17:58:22.845201+00:00",
    "input_files": {
      "piece_status": "output\\retrieval-status\\final_retrieval_piece_status_postprocessed.json",
      "cid_status": "output\\retrieval-status\\final_retrieval_cid_status_postprocessed.json",
      "deals": "output\\deals.json",
      "file_metadata_dir": "output\\file-metadata",
      "piece_metadata_dir": "output\\piece-metadata"
    },
    "active_deals_count": 16056
  }
}
```

### metadata Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 timestamp of report generation |
| `input_files.piece_status` | string | Path to piece-level retrieval status file |
| `input_files.cid_status` | string | Path to CID-level retrieval status file |
| `input_files.deals` | string | Path to deals database file |
| `input_files.file_metadata_dir` | string | Path to file-metadata directory |
| `input_files.piece_metadata_dir` | string | Path to piece-metadata directory |
| `active_deals_count` | int | Total number of active deals in the deals database |
| `input_files.piece_status` | string | Path to piece-level retrieval status file |
| `input_files.cid_status` | string | Path to CID-level retrieval status file |
| `input_files.deals` | string | Path to deals database file |
| `input_files.file_metadata_dir` | string | Path to file-metadata directory |
| `input_files.piece_metadata_dir` | string | Path to piece-metadata directory |
| `active_deals_count` | int | Total number of active deals in the deals database |

---

## 1. overall_retrieval

Aggregate retrieval metrics across all active deals.

```json
{
  "overall_retrieval": {
    "counts": {
      "total_unique_pieces_in_active_deals": 1234,
      "total_unique_cids_in_active_deals": 56789,
      "total_piece_retrieval_checks": 2468,
      "total_cid_retrieval_checks": 113578
    },

    "piece_outcomes": {
      "success_count": 2000,
      "failure_count": 468,
      "success_rate": 0.81
    },

    "cid_outcomes": {
      "success_count": 90000,
      "failure_count": 23578,
      "success_rate": 0.79
    },

    "unique_metrics": {
      "pieces": {
        "with_any_provider_success": 1100,
        "all_providers_success": 900,
        "all_providers_failed": 134
      },
      "cids": {
        "with_any_provider_success": 50000,
        "all_providers_success": 40000,
        "all_providers_failed": 6789
      }
    },

    "by_filetype": {
      "h5": {
        "total_files_in_active_deals": 10000,
        "success_count": 7500,
        "failure_count": 2500,
        "success_rate": 0.75
      }
    },

    "by_filesize_bucket": {
      "0-1MB": {
        "total_files_in_active_deals": 5000,
        "success_count": 4800,
        "failure_count": 200,
        "success_rate": 0.96
      },
      "1GB+": {
        "total_files_in_active_deals": 500,
        "success_count": 50,
        "failure_count": 450,
        "success_rate": 0.10
      }
    },

    "non_active_deals": {
      "unique_pieces_not_in_active_deals": 7033,
      "unique_cids_not_in_active_deals": 45000,
      "piece_retrieval_checks_not_in_active_deals": 7109,
      "cid_retrieval_checks_not_in_active_deals": 475600
    }
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `counts.total_unique_pieces_in_active_deals` | int | Distinct piece CIDs with active deals |
| `counts.total_unique_cids_in_active_deals` | int | Distinct file CIDs with active deals |
| `counts.total_piece_retrieval_checks` | int | Total piece-level checks (piece × provider) |
| `counts.total_cid_retrieval_checks` | int | Total CID-level checks (CID × provider) |
| `piece_outcomes.success_count` | int | Piece retrievals with status "available" and HTTP 2xx |
| `piece_outcomes.failure_count` | int | Piece retrievals that failed |
| `piece_outcomes.success_rate` | float | success_count / (success_count + failure_count) |
| `cid_outcomes.*` | — | Same pattern as piece_outcomes |
| `unique_metrics.pieces.with_any_provider_success` | int | Pieces where ≥1 provider succeeded |
| `unique_metrics.pieces.all_providers_success` | int | Pieces where ALL active-deal providers succeeded |
| `unique_metrics.pieces.all_providers_failed` | int | Pieces where ALL active-deal providers failed |
| `unique_metrics.cids.*` | — | Same pattern for CID-level |
| `by_filetype.<ext>` | object | Breakdown by file extension |
| `by_filesize_bucket.<bucket>` | object | Breakdown by size range |
| `non_active_deals.*` | — | Diagnostic counts for items without active deals |

---

## 2. by_preparation

Metrics grouped by preparation ID.

```json
{
  "by_preparation": {
    "1": {
      "piece_metrics": {
        "pieces_in_active_deals": 100,
        "piece_retrieval_checks": 200,
        "success_count": 180,
        "failure_count": 20,
        "success_rate": 0.90,
        "unique_pieces_with_any_provider_success": 95,
        "unique_pieces_all_providers_success": 85,
        "unique_pieces_all_providers_failed": 5
      },
      "cid_metrics": {
        "cids_in_active_deals": 5000,
        "cid_retrieval_checks": 10000,
        "success_count": 9000,
        "failure_count": 1000,
        "success_rate": 0.90,
        "unique_cids_with_any_provider_success": 4500,
        "unique_cids_all_providers_success": 4000,
        "unique_cids_all_providers_failed": 500
      },
      "by_filetype": {
        "h5": {
          "total_files_in_active_deals": 2000,
          "success_count": 1800,
          "failure_count": 200,
          "success_rate": 0.90
        }
      },
      "by_filesize_bucket": {
        "0-1MB": {
          "total_files_in_active_deals": 3000,
          "success_count": 2900,
          "failure_count": 100,
          "success_rate": 0.97
        }
      },
      "non_active_deals": {
        "unique_pieces_not_in_active_deals": 1,
        "unique_cids_not_in_active_deals": 61,
        "piece_retrieval_checks_not_in_active_deals": 1,
        "cid_retrieval_checks_not_in_active_deals": 61
      }
    }
  }
}
```

### by_preparation Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `<prep_id>` | string | Preparation identifier (e.g., "1", "2") |
| `piece_metrics.pieces_in_active_deals` | int | Unique pieces in this prep with active deals |
| `piece_metrics.piece_retrieval_checks` | int | Total piece checks for this prep |
| `piece_metrics.success_count` | int | Successful piece retrievals |
| `piece_metrics.failure_count` | int | Failed piece retrievals |
| `piece_metrics.success_rate` | float | Success ratio |
| `piece_metrics.unique_pieces_with_any_provider_success` | int | Pieces with ≥1 successful provider |
| `piece_metrics.unique_pieces_all_providers_success` | int | Pieces with ALL providers successful |
| `piece_metrics.unique_pieces_all_providers_failed` | int | Pieces with ALL providers failed |
| `cid_metrics.*` | — | Same pattern for CID-level |
| `by_filetype.<ext>` | object | Breakdown by file extension for this prep |
| `by_filesize_bucket.<bucket>` | object | Breakdown by size range for this prep |
| `non_active_deals.*` | — | Diagnostic counts for items without active deals in this prep |

---

## 3. by_storage_provider

Metrics grouped by storage provider.

```json
{
  "by_storage_provider": {
    "f02639429": {
      "providerid": "f02639429",
      "providername": "Milad",
      "piece_metrics": {
        "pieces_in_active_deals": 500,
        "piece_retrieval_checks": 500,
        "success_count": 400,
        "failure_count": 100,
        "success_rate": 0.80,
        "unique_pieces_with_success": 400,
        "unique_pieces_all_checks_failed": 100
      },
      "cid_metrics": {
        "cids_in_active_deals": 25000,
        "cid_retrieval_checks": 25000,
        "success_count": 20000,
        "failure_count": 5000,
        "success_rate": 0.80,
        "unique_cids_with_success": 20000,
        "unique_cids_all_checks_failed": 5000
      },
      "by_filetype": {
        "h5": {
          "total_files_in_active_deals": 10000,
          "success_count": 7500,
          "failure_count": 2500,
          "success_rate": 0.75
        }
      },
      "by_filesize_bucket": {
        "0-1MB": {
          "total_files_in_active_deals": 15000,
          "success_count": 14500,
          "failure_count": 500,
          "success_rate": 0.97
        }
      },
      "non_active_deals": {
        "unique_pieces_not_in_active_deals": 7022,
        "unique_cids_not_in_active_deals": 471412,
        "piece_retrieval_checks_not_in_active_deals": 7022,
        "cid_retrieval_checks_not_in_active_deals": 471412
      }
    }
  }
}
```

### by_storage_provider Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `<provider_id>` | string | Provider ID key (e.g., "f02639429") |
| `providerid` | string | Provider ID |
| `providername` | string | Provider name (human-readable) |
| `piece_metrics.pieces_in_active_deals` | int | Unique pieces this provider has active deals for |
| `piece_metrics.unique_pieces_with_success` | int | Pieces successfully retrieved from this provider |
| `piece_metrics.unique_pieces_all_checks_failed` | int | Pieces that failed all retrieval attempts |
| `cid_metrics.*` | — | Same pattern for CID-level |
| `by_filetype.<ext>` | object | Breakdown by file extension for this provider |
| `by_filesize_bucket.<bucket>` | object | Breakdown by size range for this provider |
| `non_active_deals.*` | — | Diagnostic counts for items without active deals for this provider |

---

## 4. prepared_content

Comprehensive view of all prepared content, not filtered by active deals.

```json
{
  "prepared_content": {
    "overall": {
      "cid_metrics": {
        "total_files": 100000,
        "unique_cids": 75000,
        "retrievable_by_any_provider": 50000,
        "retrievable_by_all_providers": 40000,
        "not_retrievable_by_any_provider": 5000,
        "not_in_any_active_deals": 20000,
        "by_provider": {
          "f02639429": {
            "provider_name": "Milad",
            "retrievable": 45000,
            "not_retrievable": 5000,
            "not_in_deals": 25000
          }
        }
      },
      "piece_metrics": {
        "total_pieces": 2000,
        "unique_piece_cids": 1800,
        "retrievable_by_any_provider": 1500,
        "retrievable_by_all_providers": 1200,
        "not_retrievable_by_any_provider": 100,
        "not_in_any_active_deals": 200,
        "by_provider": { ... }
      }
    },

    "by_preparation": {
      "1": {
        "cid_metrics": {
          "source_file": "GEDI02_B_prep1_details.csv",
          "total_files": 15000,
          "unique_cids": 12000,
          "retrievable_by_any_provider": 10000,
          "retrievable_by_all_providers": 8000,
          "not_retrievable_by_any_provider": 500,
          "not_in_any_active_deals": 1500,
          "by_provider": { ... }
        },
        "piece_metrics": {
          "source_file": "GEDI02_B_prep1_details.json",
          ...
        },
        "by_filetype": {
          "h5": {
            "unique_cids": 5000,
            "by_provider": {
              "f02639429": {
                "provider_name": "Milad",
                "retrievable": 4000,
                "not_retrievable": 500,
                "not_in_deals": 500
              }
            }
          }
        },
        "by_filesize_bucket": {
          "1GB+": {
            "unique_cids": 200,
            "by_provider": { ... }
          }
        }
      }
    },

    "providers": {
      "f02639429": "Milad",
      "f03493414": "Decent"
    }
  }
}
```

### Field Descriptions: Overall

| Field | Type | Description |
|-------|------|-------------|
| `cid_metrics.total_files` | int | Total file entries (may include duplicates) |
| `cid_metrics.unique_cids` | int | Distinct CIDs |
| `cid_metrics.retrievable_by_any_provider` | int | CIDs where ≥1 active-deal provider succeeded |
| `cid_metrics.retrievable_by_all_providers` | int | CIDs where ALL active-deal providers succeeded |
| `cid_metrics.not_retrievable_by_any_provider` | int | CIDs where all active-deal providers failed |
| `cid_metrics.not_in_any_active_deals` | int | CIDs with no active deals |
| `by_provider.<id>.retrievable` | int | CIDs this provider retrieved successfully |
| `by_provider.<id>.not_retrievable` | int | CIDs this provider failed to retrieve |
| `by_provider.<id>.not_in_deals` | int | CIDs not in deals with this provider |

### Field Descriptions: By Preparation

| Field | Type | Description |
|-------|------|-------------|
| `source_file` | string | Source metadata filename |
| `by_filetype.<ext>` | object | Breakdown by file extension |
| `by_filesize_bucket.<bucket>` | object | Breakdown by size range |

---

## 5. error_analysis

Detailed analysis of HTTP 500 errors and retrieval failures.

```json
{
  "error_analysis": {
    "scope": "active_deals_only",

    "overview": {
      "total_500_errors": 5000,
      "cids_with_any_500_error": 4500,
      "cids_all_providers_failed": 3000,
      "percentage_of_active_deal_cids": 8.5
    },

    "by_provider": {
      "f02639429": {
        "provider_name": "Milad",
        "total_500_errors": 2500,
        "categories": {
          "multihash_not_found": 1500,
          "root_load_failure": 800,
          "other": 200
        },
        "top_patterns": [
          {
            "pattern": "failed to find multihash <hash>",
            "count": 1500,
            "percentage": 60.0
          }
        ]
      }
    },

    "by_preparation": {
      "1": {
        "total_500_errors": 1000,
        "categories": {
          "multihash_not_found": 600,
          "root_load_failure": 400
        }
      }
    },

    "cross_provider_analysis": {
      "cids_with_multiple_providers_and_errors": 30000,
      "all_providers_fail": 2000,
      "some_providers_fail": 500,
      "all_fail_characteristics": {
        "top_category_combinations": [
          {
            "categories": {
              "Milad": "multihash_not_found",
              "Decent": "root_load_failure"
            },
            "count": 800,
            "percentage": 40.0
          }
        ],
        "by_preparation": { "1": 500, "2": 300 },
        "by_filetype": { "h5": 1200, "tif": 400 },
        "by_filesize_bucket": { "1GB+": 1800, "100MB-1GB": 200 }
      },
      "some_fail_characteristics": {
        "by_preparation": { "1": 300, "2": 200 },
        "by_filetype": { "png": 250, "xml": 200 },
        "by_filesize_bucket": { "0-1MB": 400, "1-10MB": 100 }
      }
    },

    "file_characteristics_by_category": {
      "multihash_not_found": {
        "total_errors": 3000,
        "by_filetype": { "h5": 2000, "tif": 500 },
        "by_filesize_bucket": { "1GB+": 2500, "100MB-1GB": 500 }
      }
    }
  }
}
```

### Error Categories

| Category | Detection Pattern |
|----------|-------------------|
| `multihash_not_found` | Error contains "multihash" and "not found" |
| `root_load_failure` | Error contains "failed to load root" |
| `piece_not_found` | Error contains "piece" and "not found" |
| `cid_not_found` | Error contains "cid" and "not found" |
| `timeout` | Error indicates timeout |
| `connection_error` | Error indicates connection problem |
| `ipld_error` | Error relates to IPLD processing |
| `node_not_found` | Error contains "could not find node" |
| `other` | Does not match above patterns |

### Cross-Provider Analysis Fields

| Field | Type | Description |
|-------|------|-------------|
| `cids_with_multiple_providers` | int | CIDs with active deals on multiple providers |
| `all_providers_fail` | int | CIDs where all providers returned errors |
| `some_providers_fail` | int | CIDs where some (but not all) providers failed |
| `all_fail_characteristics` | object | Breakdown of shared failures |
| `all_fail_characteristics.top_category_combinations` | array | Most common error category combinations across providers |
| `some_fail_characteristics` | object | Breakdown of partial failures |

---

## File Size Buckets

Standard size bucket boundaries used throughout:

| Bucket | Range |
|--------|-------|
| `0-1MB` | 0 to < 1 MiB |
| `1-10MB` | 1 MiB to < 10 MiB |
| `10-100MB` | 10 MiB to < 100 MiB |
| `100MB-1GB` | 100 MiB to < 1 GiB |
| `1GB+` | ≥ 1 GiB |

> **Note:** Some buckets may have `null` for `success_rate` when `total_files_in_active_deals` is 0.

---

## Type Definitions Summary

| Type | Description |
|------|-------------|
| `int` | Integer (counts, sizes) |
| `float` | Decimal (rates, percentages as 0.0-1.0 or 0.0-100.0) |
| `string` | Text (IDs, names, patterns) |
| `object` | Nested structure |
| `null` | Missing/unavailable data |
