# Retrieval Check Summary Specification v1

> **Purpose:** Specification for analyzing Filecoin storage deal retrieval performance. Defines how raw retrieval check results are transformed into structured metrics (`summary_report.json`), then rendered as human-readable reports.
>
> **Scope:** Data collections prepared with Singularity and stored across multiple storage providers on Filecoin.

---

## Quick Navigation

| If you need to... | Read this file |
|-------------------|----------------|
| Understand where data comes from | [01-data-sources.md](01-data-sources.md) |
| Look up JSON schema/field definitions | [02-json-schema.md](02-json-schema.md) |
| See how metrics are calculated | [03-metric-calculations.md](03-metric-calculations.md) |
| **Generate a narrative report from JSON** | [04-narrative-generation.md](04-narrative-generation.md) |
| Find output file locations | [05-output-artifacts.md](05-output-artifacts.md) |
| Look up domain terminology | [06-glossary.md](06-glossary.md) |
| Understand edge cases and limitations | [07-caveats-and-pitfalls.md](07-caveats-and-pitfalls.md) |

---

## LLM Task Routing

Use this table to determine which files to load for specific tasks:

| Task | Required Files | Optional Files |
|------|----------------|----------------|
| Generate narrative report from `summary_report.json` | `04-narrative-generation.md`, `06-glossary.md` | `07-caveats-and-pitfalls.md` |
| Validate JSON structure | `02-json-schema.md` | — |
| Debug unexpected metric values | `03-metric-calculations.md`, `07-caveats-and-pitfalls.md` | `02-json-schema.md` |
| Understand data pipeline | `01-data-sources.md` | `02-json-schema.md` |
| Find output files | `05-output-artifacts.md` | — |
| Explain terminology to users | `06-glossary.md` | `07-caveats-and-pitfalls.md` |

---

## Specification Files

### [01-data-sources.md](01-data-sources.md)

Input files and their schemas:

- `final_retrieval_piece_status_postprocessed.json`
- `final_retrieval_cid_status_postprocessed.json`
- `deals.json`
- File-metadata CSVs and piece-metadata JSONs

### [02-json-schema.md](02-json-schema.md)

Complete `summary_report.json` structure with all 5 sections:

- `overall_retrieval`
- `by_preparation`
- `by_storage_provider`
- `prepared_content`
- `error_analysis`

### [03-metric-calculations.md](03-metric-calculations.md)

Explicit formulas for all derived metrics:

- Success rate calculations
- Aggregation logic (per-provider, per-preparation)
- File size bucket boundaries
- Threshold definitions

### [04-narrative-generation.md](04-narrative-generation.md) ⭐

**Primary guide for LLMs generating reports.** Includes:

- Interpretation rules and thresholds
- Example JSON → prose translations
- Report section templates
- Tone and emphasis guidance

### [05-output-artifacts.md](05-output-artifacts.md)

Output file locations and formats:

- `summary_report.json` (machine-readable)
- `RETRIEVAL_SUMMARY_REPORT.md` (narrative report)
- `retrieval_charts.md` (visualization gallery)

### [06-glossary.md](06-glossary.md)

Domain terminology with context:

- Piece, CID, CAR file definitions
- Storage provider terminology
- Retrieval status meanings
- Preparation context

### [07-caveats-and-pitfalls.md](07-caveats-and-pitfalls.md)

Edge cases, scope limits, and common mistakes:

- "Retrievable by all providers" semantics
- Data scope differences between sections
- Non-active deals interpretation
- Duplicate piece CID handling

---

## Outputs

| Artifact | Location | Purpose |
|----------|----------|---------|
| `summary_report.json` | `output/summary-reports/` | Machine-readable metrics |
| `RETRIEVAL_SUMMARY_REPORT.md` | `output/summary-reports/` | Human-readable narrative |
| `retrieval_charts.md` | `output/summary-reports/` | Mermaid visualization gallery |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024-12 | Initial structured specification (split from monolithic doc) |
