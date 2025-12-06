# Metric Calculations

> **Purpose:** Explicit formulas, thresholds, and aggregation logic for all derived metrics.

---

## Success/Failure Classification

### is_success(status, statuscode)

A retrieval is classified as **successful** if:

```python
def is_success(status: str, statuscode: int) -> bool:
    return status == "available" and 200 <= statuscode < 300
```

All other outcomes are classified as **failures**, including:

- `status = "unavailable"`
- `status = "error"`
- `statuscode >= 400` (even if status = "available")
- `statuscode` in 3xx range (redirects without content)

---

## Rate Calculations

### Success Rate

```python
success_rate = success_count / (success_count + failure_count)
```

**Edge cases:**

- If `success_count + failure_count = 0`: Return `null` (not `0.0`)
- Result is a float in range `[0.0, 1.0]` when defined

### Percentage of Active Deal CIDs

```python
percentage = (cids_with_any_500_error / total_unique_cids_in_active_deals) * 100
```

**Result:** Float in range `[0.0, 100.0]`

---

## Unique Item Metrics

### unique_*_with_any_provider_success

Count of items where **at least one** provider with an active deal succeeded.

```python
# For each unique pieceCid/cid:
any_success = any(
    is_success(check["status"], check["status_code"])
    for provider_id, check in item["storage_provider_retrieval_check"].items()
    if (item["pieceCid"], provider_id) in active_deals
)
```

### unique_*_all_providers_success

Count of items where **all** providers with active deals succeeded.

```python
# For each unique pieceCid/cid:
active_checks = [
    is_success(check["status"], check["status_code"])
    for provider_id, check in item["storage_provider_retrieval_check"].items()
    if (item["pieceCid"], provider_id) in active_deals
]
all_success = len(active_checks) > 0 and all(active_checks)
```

**Important:** Item must have at least one active deal provider to be counted.

### unique_*_all_providers_failed

Count of items where **all** providers with active deals failed.

```python
active_checks = [
    is_success(check["status"], check["status_code"])
    for provider_id, check in item["storage_provider_retrieval_check"].items()
    if (item["pieceCid"], provider_id) in active_deals
]
all_failed = len(active_checks) > 0 and not any(active_checks)
```

---

## Aggregation Patterns

### Per-Provider Aggregation

Each (pieceCid, provider) combination is treated independently:

```python
for item in retrieval_data:
    for provider_id, check in item["storage_provider_retrieval_check"].items():
        if (item["pieceCid"], provider_id) in active_deals:
            # Count this as a separate retrieval check
            provider_stats[provider_id].total_checks += 1
            if is_success(check["status"], check["status_code"]):
                provider_stats[provider_id].success_count += 1
            else:
                provider_stats[provider_id].failure_count += 1
```

### Per-Preparation Aggregation

Group by the `preparation` field before applying per-provider logic:

```python
for item in retrieval_data:
    prep_id = str(item["preparation"])
    for provider_id, check in item["storage_provider_retrieval_check"].items():
        if (item["pieceCid"], provider_id) in active_deals:
            prep_stats[prep_id].total_checks += 1
            # ... same success/failure logic
```

### Overall Aggregation

Sum across all providers and preparations:

```python
overall.total_checks = sum(p.total_checks for p in provider_stats.values())
overall.success_count = sum(p.success_count for p in provider_stats.values())
overall.failure_count = sum(p.failure_count for p in provider_stats.values())
```

---

## File Size Bucket Classification

### bucket_filesize(size_bytes)

```python
def bucket_filesize(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "unknown"
    
    MB = 1024 * 1024
    GB = 1024 * 1024 * 1024
    
    if size_bytes < MB:
        return "0-1MB"
    elif size_bytes < 10 * MB:
        return "1-10MB"
    elif size_bytes < 100 * MB:
        return "10-100MB"
    elif size_bytes < GB:
        return "100MB-1GB"
    else:
        return "1GB+"
```

### Bucket Boundaries (Exact)

| Bucket | Min (bytes) | Max (bytes) |
|--------|-------------|-------------|
| 0-1MB | 0 | 1,048,575 |
| 1-10MB | 1,048,576 | 10,485,759 |
| 10-100MB | 10,485,760 | 104,857,599 |
| 100MB-1GB | 104,857,600 | 1,073,741,823 |
| 1GB+ | 1,073,741,824 | ∞ |

---

## File Type Extraction

```python
def extract_filetype(filename: str) -> str:
    if not filename or '.' not in filename:
        return "unknown"
    return filename.rsplit('.', 1)[-1].lower()
```

**Examples:**

- `data.h5` → `h5`
- `image.tif` → `tif`
- `config.json` → `json`
- `README` → `unknown`
- `.hidden` → `hidden`

---

## Error Categorization

### Category Detection Order

Categories are checked in order; first match wins:

```python
def categorize_error(error_message: str) -> str:
    msg = error_message.lower() if error_message else ""
    
    if "multihash" in msg and "not found" in msg:
        return "multihash_not_found"
    if "failed to load root" in msg:
        return "root_load_failure"
    if "piece" in msg and "not found" in msg:
        return "piece_not_found"
    if "cid" in msg and "not found" in msg:
        return "cid_not_found"
    if "timeout" in msg:
        return "timeout"
    if "connection" in msg:
        return "connection_error"
    if "ipld" in msg:
        return "ipld_error"
    if "could not find node" in msg:
        return "node_not_found"
    return "other"
```

### Error Pattern Normalization

For `top_patterns`, dynamic values are replaced with placeholders:

```python
def normalize_pattern(error_message: str) -> str:
    # Replace CIDs, hashes, and other dynamic values
    pattern = re.sub(r'baf[a-z0-9]{50,}', '<cid>', error_message)
    pattern = re.sub(r'[a-f0-9]{64}', '<hash>', pattern)
    return pattern
```

---

## Prepared Content Calculations

### CID Deduplication (First One In)

When the same CID appears multiple times:

```python
seen_cids = {}
for row in csv_rows:
    cid = row['cid']
    if cid not in seen_cids:
        seen_cids[cid] = {
            'filetype': extract_filetype(row['fileName']),
            'size': int(row['size']),
            'first_occurrence': row
        }
    # Subsequent occurrences are counted but not re-classified
```

### Retrievability Classification

For each unique CID in prepared content:

```python
def classify_cid_retrievability(cid, retrieval_status, active_deals):
    # Find retrieval checks for this CID
    checks = retrieval_status.get(cid, {})
    
    active_provider_results = []
    for provider_id, check in checks.items():
        if (check["pieceCid"], provider_id) in active_deals:
            active_provider_results.append(is_success(check["status"], check["status_code"]))
    
    if len(active_provider_results) == 0:
        return "not_in_any_active_deals"
    elif all(active_provider_results):
        return "retrievable_by_all_providers"
    elif any(active_provider_results):
        return "retrievable_by_any_provider"
    else:
        return "not_retrievable_by_any_provider"
```

---

## Cross-Provider Analysis

### Shared Failure Detection

Only consider CIDs with active deals on **multiple** providers:

```python
cids_with_multiple = {
    cid for cid in all_cids
    if sum(1 for p in providers if (cid_to_piece[cid], p) in active_deals) > 1
}

for cid in cids_with_multiple:
    provider_results = {}
    for provider_id in providers:
        if (cid_to_piece[cid], provider_id) in active_deals:
            provider_results[provider_id] = is_success(checks[cid][provider_id])
    
    if all(not success for success in provider_results.values()):
        cross_provider.all_providers_fail += 1
    elif any(not success for success in provider_results.values()):
        cross_provider.some_providers_fail += 1
```

---

## Thresholds for Interpretation

These thresholds are used for narrative generation (see [04-narrative-generation.md](04-narrative-generation.md)):

| Metric | Excellent | Good | Concerning | Critical |
|--------|-----------|------|------------|----------|
| Overall success rate | ≥ 95% | 80-94% | 60-79% | < 60% |
| Provider success rate | ≥ 95% | 80-94% | 60-79% | < 60% |
| All providers failed (%) | < 1% | 1-5% | 5-15% | > 15% |
| 1GB+ success rate | ≥ 80% | 50-79% | 20-49% | < 20% |

---

## Validation Rules

### Required Field Checks

Before calculation, validate:

```python
required_fields = {
    'piece_status': ['pieceCid', 'storage_provider_retrieval_check'],
    'cid_status': ['cid', 'pieceCid', 'storage_provider_retrieval_check'],
    'deals': ['pieceCid', 'provider', 'state']
}
```

### Empty Input Handling

If input files are empty:

- Return zeroed statistics (not errors)
- All counts = 0
- All rates = 0.0
- Empty objects for breakdowns

```python
if not retrieval_data:
    return {
        "counts": {
            "total_unique_pieces_in_active_deals": 0,
            "total_unique_cids_in_active_deals": 0,
            "total_piece_retrieval_checks": 0,
            "total_cid_retrieval_checks": 0
        },
        "piece_outcomes": {"success_count": 0, "failure_count": 0, "success_rate": null},
        # ...
    }
```
