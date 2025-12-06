# LLM Prompts

> Standardized prompts for common tasks in the retrieval-check-summary project.

---

## Overview

This directory contains pre-built prompts that can be used with LLMs (like GitHub Copilot, Claude, GPT-4, etc.) to perform common documentation and QA tasks. Each prompt includes:

- A **Role** definition that sets the appropriate persona
- **Required context files** the LLM should read
- **Task details** with specific instructions
- **Validation checklists** to ensure quality output

---

## Available Prompts

| File | Use Case | When to Use |
|------|----------|-------------|
| [01-generate-summary-report.md](01-generate-summary-report.md) | Generate new report | Fresh `summary_report.json`, no existing markdown |
| [02-update-summary-report.md](02-update-summary-report.md) | Update existing report | New data, existing markdown to update |
| [03-qa-summary-report-script.md](03-qa-summary-report-script.md) | QA validation | After spec or code changes |

---

## Quick Start

### Generating a New Report

1. Run `summary_report.py` to produce fresh `summary_report.json`
2. Open your LLM assistant
3. Provide the content of `01-generate-summary-report.md` as context
4. Attach or paste `summary_report.json`
5. Request the LLM generate `RETRIEVAL_SUMMARY_REPORT.md` and `retrieval_charts.md`

### Updating an Existing Report

1. Run `summary_report.py` to produce updated `summary_report.json`
2. Open your LLM assistant
3. Provide the content of `02-update-summary-report.md` as context
4. Attach the new JSON AND the existing markdown files
5. Request the LLM update both files

### Performing QA Validation

1. After modifying spec or code
2. Open your LLM assistant
3. Provide the content of `03-qa-summary-report-script.md` as context
4. Attach relevant spec files and code files
5. Request a compliance review and defect report

---

## Related Documentation

These prompts reference the specification documents in:

```text
docs/spec/retrieval-check-summary.v1/
├── 01-data-sources.md          # Input file schemas
├── 02-json-schema.md           # Output JSON structure  
├── 03-metric-calculations.md   # Formulas and thresholds
├── 04-narrative-generation.md  # Prose templates (key for reports)
├── 05-output-artifacts.md      # Output file locations
├── 06-glossary.md              # Domain terminology
├── 07-caveats-and-pitfalls.md  # Edge cases and gotchas
└── README.md                   # Spec overview
```

---

## Best Practices

### When Using These Prompts

1. **Always provide the spec files as context** — The prompts reference them heavily
2. **Include actual data** — Don't expect the LLM to fabricate realistic numbers
3. **Review output carefully** — LLMs can make mistakes; validate against the JSON
4. **Iterate if needed** — Request corrections for any issues found

### Extending These Prompts

If you need a new prompt:

1. Follow the existing format (Role → Task → Context → Checklist)
2. Reference specific spec files by path
3. Include concrete examples where possible
4. Add a validation checklist

---

## Prompt File Naming Convention

```text
NN-task-description.md

NN = Two-digit sequence number
task-description = Kebab-case description of the task
```

Examples:

- `01-generate-summary-report.md`
- `02-update-summary-report.md`
- `03-qa-summary-report-script.md`
- `04-analyze-error-patterns.md` (future)
