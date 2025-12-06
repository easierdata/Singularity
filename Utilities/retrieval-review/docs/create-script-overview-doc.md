# Create Scripts Overview Documentation

## Task

Create a detailed `SCRIPTS_OVERVIEW.md` file in the docs folder that documents all scripts in this project. The documentation should serve as a quick reference for understanding what each script does, how to run it, and how they relate to each other.

### Project Context

This is a **Filecoin retrieval check analysis** project that:

1. Fetches deal and metadata from a Singularity API
2. Checks retrieval status of pieces and CIDs against storage providers
3. Analyzes errors and generates summary reports

### Configuration System

All scripts use a centralized configuration system in config.py:

- **Config loading**: `load_config()` loads from config.json in project root, with defaults defined in `DEFAULT_CONFIG`
- **Deep merge behavior**: Config file values are merged ON TOP of defaults (additive, not replacing). This means storage providers in config.json are ADDED to the default Milad provider.
- **Key functions**:
  - `get_storage_providers(config)` - Returns dict of `provider_id -> {name, retrieval_endpoint}`
  - `get_path(config, key)` - Returns a Path for directory keys like `output_dir`, `piece_metadata_dir`
  - `get_file_path(config, filename_key)` - Combines directory + filename for file keys (uses `_FILE_TO_DIR_MAP`)
  - `get_api_endpoint(config)` - Returns Singularity API base URL

### Scripts to Document

#### 1. `fetch_deals.py`

- Fetches deal information from Singularity API
- Outputs to deals.json
- Uses config for API endpoint

#### 2. `fetch_file_metadata.py`

- Fetches file-level metadata from Singularity API
- Outputs CSV files to file-metadata (one per preparation)
- Filename pattern: `{dataset_name}_prep{id}_details.csv`

#### 3. `fetch_piece_metadata.py`

- Fetches piece-level metadata from Singularity API
- Outputs JSON files to piece-metadata (one per preparation)
- Filename pattern: `{dataset_name}_prep{id}_details.json`

#### 4. `check_retrieval_status.py`

- Main retrieval checking script
- Checks both piece-level and CID-level retrievability against configured storage providers
- Outputs to retrieval-status:
  - `final_retrieval_piece_status.json`
  - `final_retrieval_cid_status.json`

#### 5. `check_retrieval_status-piece_postprocessing.py`

- Post-processes piece retrieval status
- Adds `active_deal_providers` field based on deals.json
- Outputs `final_retrieval_piece_status_postprocessed.json`

#### 6. `check_retrieval_status-cid_postprocessing.py`

- Post-processes CID retrieval status
- Adds `active_deal_providers` field based on deals.json
- Outputs `final_retrieval_cid_status_postprocessed.json`

#### 7. summary_report.py

- **Main summary report generator**
- Reads postprocessed status files, deals, file-metadata, piece-metadata
- Computes comprehensive metrics including:
  - Overall retrieval success rates
  - Per-preparation breakdowns
  - Per-storage-provider breakdowns
  - Prepared content metrics (from source metadata)
  - Error analysis (HTTP 500 patterns)
- Outputs to summary_report.json
- Uses `config` parameter (optional) passed to `generate_summary_report()`
- Provider names for error analysis come from config via `get_storage_providers()`

#### 8. analyze_error_patterns.py

- Analyzes error patterns from retrieval failures
- **Provider-agnostic**: Uses `provider_ids` from config, but tracks ALL providers found in data
- **Unknown provider detection**: If data contains providers not in config, prints a notice with their IDs
- **Cross-provider analysis**:
  - `all_fail` = every active provider returned HTTP 500
  - `some_fail` = at least one failed, at least one succeeded
- **Sample CID lists**: Limited to 100 samples per category (for debugging/spot-checking/sharing/correlation)
- **CLI options**:
  - `--provider <id>` - Filter to single provider
  - `--summary-only` - Print analysis without saving to file (renamed from `--no-save`)
- Outputs to error_patterns_analysis.json

#### 9. `extract_cids_with_status_errors.py`

- Extracts CIDs that have retrieval errors
- Outputs error summaries to error-analysis

#### 10. pieces_without_deals.py

- **Reports pieces without active deals** for a specific storage provider
- **Validates provider ID**: Checks if provider exists in deals.json, errors if not found with list of valid providers
- **Uses config**: `get_file_path(config, "deals_filename")`, `get_path(config, "piece_metadata_dir")`, `get_path(config, "output_dir")`
- **Dynamic output filename**: `output/pieces_without_deals_{provider_id}.json`
- **CLI options**:
  - `--storage-provider <id>` (required)
  - `--preparation <ids>` - Filter to specific preparations
  - `--list-only` - Simplified output with just pieceCid arrays
  - `--deals`, `--piece-metadata`, `--output` - Override default paths

### Package: summary_report

A package containing modular components used by summary_report.py:

- error_analysis.py - Error analysis logic (recently made provider-agnostic)
- prepared_content.py - Metrics from source metadata
- `loaders.py` - File loading utilities
- `metrics.py` - Metric computation functions
- `aggregations.py` - Aggregation logic
- `constants.py` - Shared constants (size buckets, etc.)
- `utils.py` - Helper functions

### Key Design Decisions

#### Provider-Agnostic Design

Both analyze_error_patterns.py and error_analysis.py were refactored to be provider-agnostic:

- No hardcoded provider IDs (removed `f02639429`/Milad and `f03493414`/Decent constants)
- Provider names come from config
- Cross-provider analysis uses generic `all_fail`/`some_fail` semantics instead of provider-specific buckets
- Unknown providers (in data but not in config) are detected and reported

#### Path Resolution

- **Directories**: Use `get_path(config, "key")` for paths like `output_dir`, `piece_metadata_dir`
- **Files with known directories**: Use `get_file_path(config, "filename_key")` which combines directory + filename via `_FILE_TO_DIR_MAP`
- **Dynamic filenames**: Use `get_path(config, "output_dir")` for directory, construct filename in script

#### Error Handling

- Scripts validate input file existence before processing
- Invalid storage provider IDs are caught with helpful error messages showing valid options
- JSON loading errors are caught and reported

### Output Directory Structure

```text
output/
├── deals.json
├── pieces_without_deals_{provider}.json  # Ad-hoc reports
├── file-metadata/
│   └── {dataset}_prep{id}_details.csv
├── piece-metadata/
│   └── {dataset}_prep{id}_details.json
├── retrieval-status/
│   ├── final_retrieval_piece_status.json
│   ├── final_retrieval_piece_status_postprocessed.json
│   ├── final_retrieval_cid_status.json
│   └── final_retrieval_cid_status_postprocessed.json
├── error-analysis/
│   ├── error_patterns_analysis.json
│   ├── cid_status_errors.json
│   ├── cid_all_providers_failed.json
│   └── cid_errors_summary.json
└── summary-reports/
    ├── summary_report.json
    ├── retrieval_charts.md
    └── RETRIEVAL_SUMMARY_REPORT.md
```

### Typical Workflow

1. `fetch_deals.py` - Get deal data
2. `fetch_file_metadata.py` - Get file metadata per preparation
3. `fetch_piece_metadata.py` - Get piece metadata per preparation
4. `check_retrieval_status.py` - Run retrieval checks
5. `check_retrieval_status-piece_postprocessing.py` - Enrich piece data
6. `check_retrieval_status-cid_postprocessing.py` - Enrich CID data
7. summary_report.py - Generate comprehensive report
8. analyze_error_patterns.py - Deep-dive into errors (optional)
9. pieces_without_deals.py - Check missing deals (ad-hoc)

### Documentation Format Suggestions

- Include usage examples for each script
- Show sample CLI invocations
- Document required vs optional arguments
- Note which scripts depend on outputs from other scripts
- Include a "Quick Start" section with the typical workflow
- Add a configuration section explaining config.json structure
