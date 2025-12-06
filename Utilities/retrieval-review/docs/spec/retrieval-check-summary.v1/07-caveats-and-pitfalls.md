# Caveats and Pitfalls

> **Purpose:** Edge cases, scope limitations, and common mistakes to avoid when interpreting metrics or generating reports.

---

## Critical Semantic Clarifications

### ⚠️ "Retrievable by All Providers" Does NOT Mean Network-Wide

**The phrase "retrievable by all providers" is easily misunderstood.**

**What it MEANS:**

- Retrievable by all providers **that have active deals for that specific CID/piece**

**What it does NOT mean:**

- ❌ Retrievable from all providers in the Filecoin network
- ❌ Retrievable from all providers in this dataset
- ❌ Cross-provider redundancy guarantee

**Example:**

| Scenario | "All Providers Success"? |
|----------|--------------------------|
| CID has deal with Provider A only; Provider A succeeds | ✅ Yes |
| CID has deals with A and B; both succeed | ✅ Yes |
| CID has deals with A and B; A succeeds, B fails | ❌ No |
| CID has deal with A only; A fails | ❌ No |

**Recommendation for reports:**

Always include clarifying footnote:

> *"Retrievable by all providers" means retrievable by all providers that have active deals for that specific CID/piece, not all providers in the network.*

---

### ⚠️ Data Scope Differs Between Sections

**Different sections use different data scopes:**

| Section | Scope | What's Included |
|---------|-------|-----------------|
| `overall_retrieval` | Active deals only | Items with `state == "active"` |
| `by_preparation` | Active deals only | Same filter |
| `by_storage_provider` | Active deals only | Same filter |
| `prepared_content` | **All prepared content** | Everything from source CSVs/JSONs |
| `error_analysis` | Active deals only | HTTP 500 errors |

**Why this matters:**

- `prepared_content` includes items with NO active deals
- Comparing `prepared_content.unique_cids` to `overall_retrieval.unique_cids` shows deal coverage gap
- Preps 4 and 5 may show mostly "not in any active deals" in `prepared_content`

**Common mistake:**

> ❌ "The report shows 75,000 unique CIDs but only 55,000 are retrievable..."
>
> ✅ "Of 75,000 prepared CIDs, 55,000 have active deals. Of those with active deals, X% are retrievable..."

---

### ⚠️ Retrieval Checks ≠ Unique Items

**The difference between check counts and unique item counts:**

| Metric | What It Counts |
|--------|----------------|
| `total_piece_retrieval_checks` | Number of (piece, provider) checks |
| `total_unique_pieces_in_active_deals` | Distinct piece CIDs |

**Example:**

- 1,000 unique pieces
- Each piece has deals with 2 providers
- Total retrieval checks = 2,000

**When they differ:**

- `checks > unique_items`: Item has deals with multiple providers
- `checks == unique_items`: Each item has exactly one provider

---

## Calculation Edge Cases

### Zero-Division Handling

**When `success_count + failure_count = 0`:**

```python
success_rate = null  # Not 0.0, indicates no data
```

**Implication:** A `null` success rate means no checks were performed. A `0.0` success rate means all checks failed.

**Recommendation:** Always show absolute counts alongside rates.

---

### Empty Preparations

**Some preparations may have zero active deals.**

**In metrics:**

```json
{
  "by_preparation": {
    "4": {
      "piece_metrics": {
        "pieces_in_active_deals": 0,
        "success_rate": 0.0
      }
    }
  }
}
```

**In `prepared_content`:**

```json
{
  "prepared_content": {
    "by_preparation": {
      "4": {
        "cid_metrics": {
          "unique_cids": 5000,
          "not_in_any_active_deals": 5000
        }
      }
    }
  }
}
```

**Interpretation:** Prep 4 has 5,000 prepared CIDs but none have active deals yet.

---

### Duplicate Piece CIDs

**If `total_pieces > unique_piece_cids`:**

Same pieceCID appears in multiple preparations.

**Causes:**

- Same data sealed multiple times
- Overlapping preparations
- Data replication strategy

**Investigation:** Compare across preparations to identify duplicates.

---

## Error Analysis Gotchas

### Error Categories Are Mutually Exclusive

Each error is assigned to exactly one category (first match wins).

**Order matters:**

```python
if "multihash" in msg and "not found" in msg:  # Checked first
    return "multihash_not_found"
if "cid" in msg and "not found" in msg:         # Checked later
    return "cid_not_found"
```

**An error like "multihash cid not found" → `multihash_not_found`** (not `cid_not_found`)

---

### Cross-Provider Analysis Scope

**Only includes CIDs with deals on MULTIPLE providers.**

**Excluded:**

- CIDs with deals on only one provider
- CIDs with no active deals

**Why:** Comparing failure modes requires same conditions.

**Common mistake:**

> ❌ "Of 50,000 CIDs, 3,000 failed on all providers..."
>
> ✅ "Of 30,000 CIDs with deals on multiple providers, 3,000 (10%) failed on all..."

---

### "All Providers Fail" Interpretation

**When all providers fail for the same CID:**

| Likely Cause | Evidence |
|--------------|----------|
| Source data issue | Error categories match |
| Sealing problem | Same piece, same errors |
| Network-wide issue | Timestamps correlate |

**When only some providers fail:**

| Likely Cause | Evidence |
|--------------|----------|
| Provider-specific | Error categories differ |
| Indexing gap | One shows "not found", other succeeds |
| Transient failure | Retry may succeed |

---

## Report Generation Pitfalls

### Don't Conflate Rates Without Context

**Bad:**

> "The success rate is 80%."

**Good:**

> "The success rate is 80% (16,842 of 21,000 retrieval checks)."

**Better:**

> "The success rate is 80% (16,842 of 21,000 retrieval checks), falling in the 'Good' category but below the 95% target for production systems."

---

### Don't Ignore the 1GB+ Cliff

**If 1GB+ success rate < 50%, this is often the most important finding.**

**Bad:**

> "Overall success rate is 82%."

**Good:**

> "Overall success rate is 82%, but files over 1GB show only 12% success—a critical infrastructure limitation affecting 500 large files."

---

### Don't Compare Across Different Scopes

**Bad:**

> "75,000 CIDs were prepared but only 50,000 are retrievable (67%)."

This mixes `prepared_content` scope with `overall_retrieval` scope.

**Good:**

> "75,000 CIDs were prepared. Of these, 55,000 have active deals. Of those with active deals, 50,000 (91%) are retrievable by at least one provider."

---

### Don't Forget Non-Active Deals

**The non-active deals section shows:**

- Items that exist but can't be retrieved via Filecoin deals
- May indicate expired deals or staging content

**Include in reports:**

> "Note: 7,033 pieces and 45,000 CIDs exist but are not in active deals. These are not accessible via the current storage agreements."

---

## Metric Interpretation Limits

### Success Rate Doesn't Measure Data Integrity

Success is defined as HTTP 200 + content returned.

**Doesn't verify:**

- Content matches expected hash
- Content is complete
- Content is usable

---

### Provider Names May Be Inconsistent

**The same provider may have different names across records.**

**Handling:** Use the most common name, or any name if inconsistent.

**Don't rely on:** Name for provider identification—use `providerid`.

---

### Timestamps Are Point-in-Time

**Retrieval check results reflect:**

- State at time of check
- May not reflect current state
- Providers may have since recovered or degraded

**Recommendation:** Note check timestamp in reports.

---

## Summary: Key Rules

1. ✅ Always clarify "all providers" semantics
2. ✅ State scope when presenting metrics
3. ✅ Show absolute numbers AND percentages
4. ✅ Highlight 1GB+ issues prominently
5. ✅ Interpret cross-provider failures (systemic vs provider-specific)
6. ✅ Note non-active deals separately
7. ❌ Don't compare metrics from different scopes
8. ❌ Don't assume success rate = data integrity
9. ❌ Don't ignore empty preparations
10. ❌ Don't present rates without denominators
