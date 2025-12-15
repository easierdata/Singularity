# Retrieval Review

A toolkit for analyzing Filecoin storage deal retrieval performance. Fetches deal metadata from a Singularity API, checks unsealed data retrieval status against storage providers, and generates comprehensive reports on data availability.

## Overview

This project helps you:

- **Fetch** deal and metadata from a Singularity instance
- **Check** piece-level and CID-level retrievability against configured storage providers
- **Analyze** error patterns and retrieval failures
- **Report** on overall retrieval health with detailed breakdowns

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Access to a running Singularity API instance
- Storage provider retrieval endpoints

### 2. Setup Environment

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### 3. Configure

Copy the example config and customize:

```bash
cp config.example.json config.json
```

Edit `config.json` to set:

- **`singularity_api.base_url`** — Your Singularity API endpoint
- **`storage_providers`** — Provider IDs, names, and retrieval endpoints

```json
{
  "singularity_api": {
    "base_url": "http://your-singularity-api:9090"
  },
  "storage_providers": {
    "f01234567": {
      "name": "MyProvider",
      "retrieval_endpoint": "https://provider.example.com"
    }
  }
}
```

### 4. Run the Pipeline

Execute scripts in order:

```bash
# Fetch data from Singularity API
python scripts/fetch_deals.py
python scripts/fetch_file_metadata.py
python scripts/fetch_piece_metadata.py

# Run retrieval checks
python scripts/check_retrieval_status.py

# Enrich with deal information
python scripts/check_retrieval_status_piece_postprocessing.py
python scripts/check_retrieval_status_cid_postprocessing.py

# Generate summary report
python scripts/summary_report.py
```

Results are written to `output/summary-reports/`.

### 5. Generate Executive Summary (AI-Assisted)

A standout feature of this toolkit is its **LLM-powered executive summary generation**. After running `summary_report.py`, use the included prompts with your preferred LLM (GitHub Copilot, Claude, GPT-4, etc.) to transform the raw JSON metrics into a polished, human-readable narrative report.

```bash
# 1. Generate the machine-readable summary
python scripts/summary_report.py

# 2. Use docs/prompts/01-generate-summary-report.md with your LLM
#    to create RETRIEVAL_SUMMARY_REPORT.md and retrieval_charts.md
```

📄 **[See an example generated report →](docs/examples/summary-reports/RETRIEVAL_SUMMARY_REPORT.md)**

See [docs/prompts/](docs/prompts/README.md) for the full workflow and prompt library.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/SCRIPTS_OVERVIEW.md](docs/SCRIPTS_OVERVIEW.md) | Detailed reference for all scripts, CLI options, and workflows |
| [docs/spec/retrieval-check-summary.v1/](docs/spec/retrieval-check-summary.v1/README.md) | Specification for metrics, JSON schemas, and report generation |
| [docs/prompts/](docs/prompts/README.md) | LLM prompt library for generating executive summaries, updating reports, and QA validation |
| [docs/examples/](docs/examples/README.md) | Example outputs including an LLM-generated executive summary report |

## Output Structure

```text
output/
├── deals.json                    # Raw deal data
├── file-metadata/                # Per-preparation file metadata (CSV)
├── piece-metadata/               # Per-preparation piece metadata (JSON)
├── retrieval-status/             # Retrieval check results
├── error-analysis/               # Error investigation outputs
├── summary-reports/              # Final reports
│   ├── summary_report.json       # Machine-readable metrics
│   └── RETRIEVAL_SUMMARY_REPORT.md  # Human-readable narrative
└── logs/                         # Script execution logs
```

## Optional Analysis Scripts

After running the main pipeline, you can dive deeper:

```bash
# Analyze error patterns across providers
python scripts/analyze_error_patterns.py

# Extract CIDs with retrieval errors
python scripts/extract_cids_with_status_errors.py

# Find pieces without deals for a specific provider
python scripts/pieces_without_deals.py --storage-provider f01234567
```

## License

MIT
