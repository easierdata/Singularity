# Example Outputs

This directory contains outputs from running the complete data-retrieval check analysis pipeline, demonstrating what the toolkit produces. See the [scripts overview quick-start section](../SCRIPTS_OVERVIEW.md#quick-start) for more details.

## Summary Reports

The `summary-reports/` folder contains a complete set of outputs from a real analysis run:

| File | Description |
|------|-------------|
| [summary_report.json](summary-reports/summary_report.json) | Machine-readable metrics (input for LLM report generation) |
| [RETRIEVAL_SUMMARY_REPORT.md](summary-reports/RETRIEVAL_SUMMARY_REPORT.md) | **LLM-generated executive summary** with narrative analysis |
| [retrieval_charts.md](summary-reports/retrieval_charts.md) | Mermaid chart gallery for visualizations |

## About the Example Data

This example analyzes **GEDI satellite observation data** stored across two Filecoin storage providers:

- **10,399 unique pieces** and **847,390 unique CIDs** in active deals
- **7 preparation batches** covering different GEDI data products
- **2 storage providers** (Milad and Dcent)

The LLM-generated report demonstrates how raw JSON metrics are transformed into actionable insights, including:

- Executive summary with key findings
- Success rate breakdowns by filetype, filesize, preparation, and provider
- Error analysis with root cause identification
- Mermaid charts for visual analysis

## Generating Your Own Reports

1. Run the pipeline to generate `summary_report.json`
2. Use the prompts in [docs/prompts/](../prompts/) with your preferred LLM
3. The LLM will generate the narrative report and charts
