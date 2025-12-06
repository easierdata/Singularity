# QA: Validate summary_report.py Against Spec

> **Use Case:** Verify that `summary_report.py` correctly implements the specification after modifications or spec updates

---

## Role

### Software Quality Assurance Engineer

You are an experienced QA engineer specializing in data pipeline validation and specification compliance. Your strengths include:

- Systematically comparing implementation against specification
- Identifying discrepancies between documented behavior and actual code
- Tracing data flow from input to output
- Validating field names, types, and calculation logic
- Writing clear defect reports with reproduction steps
- Distinguishing between spec issues vs implementation issues

Your QA approach prioritizes:

1. **Specification fidelity** — Code must match documented behavior exactly
2. **Field-level accuracy** — Every field name, type, and path must be correct
3. **Calculation correctness** — Formulas must match spec definitions
4. **Edge case handling** — Zero-division, null values, empty inputs
5. **Completeness** — All documented features must be implemented

---

## Task

Perform a comprehensive QA review comparing `scripts/summary_report.py` (and its `summary_report/` package) against the retrieval-check-summary specification.

---

## Required Context Files

You MUST read these files for the review:

### Specification Documents

| File | QA Focus |
|------|----------|
| `docs/spec/retrieval-check-summary.v1/01-data-sources.md` | Input file schemas, field names |
| `docs/spec/retrieval-check-summary.v1/02-json-schema.md` | Output JSON structure, all field paths |
| `docs/spec/retrieval-check-summary.v1/03-metric-calculations.md` | Formulas, thresholds, edge cases |
| `docs/spec/retrieval-check-summary.v1/07-caveats-and-pitfalls.md` | Known edge cases, null handling |

### Implementation Files

| File | QA Focus |
|------|----------|
| `scripts/summary_report.py` | Main generator, output structure |
| `scripts/summary_report/metrics.py` | Metric calculations |
| `scripts/summary_report/aggregations.py` | Aggregation logic |
| `scripts/summary_report/error_analysis.py` | Error analysis logic |
| `scripts/summary_report/loaders.py` | Input file parsing |
| `scripts/summary_report/constants.py` | Size buckets, thresholds |

### Reference Output

| File | QA Focus |
|------|----------|
| `output/summary-reports/summary_report.json` | Actual output to validate |

---

## QA Checklist

### 1. Output Structure Validation

Compare the actual `summary_report.json` structure against `02-json-schema.md`:

- [ ] All top-level keys present: `metadata`, `overall_retrieval`, `by_preparation`, `by_storage_provider`, `prepared_content`, `error_analysis`
- [ ] All nested field paths match spec exactly
- [ ] Field naming convention is consistent (snake_case)
- [ ] No undocumented fields in output
- [ ] No documented fields missing from output

### 2. Field Name Accuracy

Verify field names match between spec and implementation:

| Spec Field | Implementation Location | Status |
|------------|------------------------|--------|
| `success_rate` | `metrics.py` | ☐ |
| `all_providers_success` | `metrics.py` | ☐ |
| `all_providers_failed` | `metrics.py` | ☐ |
| `retrievable_by_any_provider` | `aggregations.py` | ☐ |
| `not_in_any_active_deals` | `aggregations.py` | ☐ |

### 3. Metric Calculation Validation

Compare formulas in `03-metric-calculations.md` to implementation:

| Metric | Spec Formula | Implementation |
|--------|-------------|----------------|
| `success_rate` | `success_count / (success_count + failure_count)` | Check `metrics.py` |
| `all_providers_success` | All active-deal providers returned success | Check grouping logic |
| Zero-division handling | Return `null` | Check null/None handling |

### 4. File Size Bucket Validation

Verify buckets in `constants.py` match spec:

| Spec Bucket | Expected |
|-------------|----------|
| `0-1MB` | 0 - 1 MiB |
| `1-10MB` | 1 MiB - 10 MiB |
| `10-100MB` | 10 MiB - 100 MiB |
| `100MB-1GB` | 100 MiB - 1 GiB |
| `1GB+` | ≥ 1 GiB |

### 5. Input Parsing Validation

Verify `loaders.py` correctly parses input files per `01-data-sources.md`:

- [ ] Deals JSON: `pieceCid`, `provider`, `state` fields
- [ ] Piece status: `storage_provider_retrieval_check` array
- [ ] CID status: `storage_provider_retrieval_check` array
- [ ] File metadata CSV: `cid`, `file_size`, `file_path` columns
- [ ] Piece metadata JSON: `pieceCid`, `files` array

### 6. Edge Case Handling

Per `07-caveats-and-pitfalls.md`:

- [ ] Zero retrieval checks → `success_rate` is `null`, not `0.0`
- [ ] Zero-division in all rate calculations → returns `null`
- [ ] Empty preparations → handled gracefully
- [ ] Missing providers → error or skip (document behavior)

### 7. Error Analysis Validation

Verify `error_analysis.py` matches spec:

- [ ] Only analyzes HTTP 500 errors
- [ ] Scope limited to active deals
- [ ] Cross-provider analysis uses generalized logic (not hardcoded providers)
- [ ] `all_providers_fail` = all active-deal providers returned 500
- [ ] `some_providers_fail` = at least one 500, at least one non-500

---

## Defect Report Template

For each discrepancy found, document:

```markdown
### [DEFECT-XXX] Brief Description

**Severity:** Critical / Major / Minor / Cosmetic

**Location:**
- Spec: `docs/spec/retrieval-check-summary.v1/XX-file.md`, section Y
- Code: `scripts/summary_report/file.py`, line Z

**Expected (per spec):**
[Quote or describe the expected behavior]

**Actual (in code):**
[Describe what the code actually does]

**Evidence:**
- Spec quote: "..."
- Code snippet: `...`
- Output example: `...`

**Recommendation:**
[Fix spec / Fix code / Clarify behavior]
```

---

## Severity Definitions

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical** | Output is incorrect or misleading | Wrong formula, missing required field |
| **Major** | Significant deviation from spec | Wrong field name, incorrect edge case handling |
| **Minor** | Cosmetic or low-impact issue | Formatting difference, optional field missing |
| **Cosmetic** | Documentation-only issue | Typo in spec, unclear wording |

---

## Example Defects

### Example 1: Field Name Mismatch

```markdown
### [DEFECT-001] Field name uses camelCase instead of snake_case

**Severity:** Major

**Location:**
- Spec: `02-json-schema.md`, section "overall_retrieval"
- Code: `scripts/summary_report.py`, line 245

**Expected (per spec):**
Field should be named `all_providers_failed`

**Actual (in code):**
Field is named `allProvidersFailed`

**Evidence:**
- Output JSON: `"allProvidersFailed": 179942`
- Spec: "unique_metrics.cids.all_providers_failed"

**Recommendation:**
Fix code to use snake_case field name
```

### Example 2: Missing Null Handling

```markdown
### [DEFECT-002] Zero-division returns 0.0 instead of null

**Severity:** Critical

**Location:**
- Spec: `07-caveats-and-pitfalls.md`, section "Zero-Division Edge Cases"
- Code: `scripts/summary_report/metrics.py`, line 42

**Expected (per spec):**
When dividing by zero, return `null` (Python `None`)

**Actual (in code):**
Returns `0.0` when denominator is zero

**Evidence:**
- Code: `return success / total if total > 0 else 0.0`
- Spec: "Return null for success_rate when there are no retrieval checks"

**Recommendation:**
Change `else 0.0` to `else None`
```

---

## Output Format

Produce a QA report with:

1. **Summary** — Overall compliance status
2. **Defect List** — All issues found, by severity
3. **Compliance Matrix** — Checklist results
4. **Recommendations** — Prioritized fix list

---

## Example Invocation

```text
Please perform a QA review of summary_report.py against the spec in 
docs/spec/retrieval-check-summary.v1/

Focus on:
1. Output JSON structure matching 02-json-schema.md
2. Metric calculations matching 03-metric-calculations.md
3. Edge case handling per 07-caveats-and-pitfalls.md

Produce a defect report for any discrepancies found.
```

---

## Post-QA Actions

After the QA review:

1. **If spec is wrong:** Update spec files to match intended behavior
2. **If code is wrong:** Fix implementation to match spec
3. **If unclear:** Add clarification to `07-caveats-and-pitfalls.md`
4. **Regenerate output:** Run `summary_report.py` and validate fix

---

## Attached Files

> **Note:** If using VS Code Copilot, the `#file:` references below will auto-attach the files.
> For other LLMs, manually attach or paste these files after copying this prompt.

**Spec files:**

- #file:docs/spec/retrieval-check-summary.v1/01-data-sources.md
- #file:docs/spec/retrieval-check-summary.v1/02-json-schema.md
- #file:docs/spec/retrieval-check-summary.v1/03-metric-calculations.md
- #file:docs/spec/retrieval-check-summary.v1/07-caveats-and-pitfalls.md

**Code files:**

- #file:scripts/summary_report.py
- #file:scripts/summary_report/metrics.py
- #file:scripts/summary_report/aggregations.py
- #file:scripts/summary_report/error_analysis.py
- #file:scripts/summary_report/loaders.py
- #file:scripts/summary_report/constants.py

**Output file:**

- #file:output/summary-reports/summary_report.json
