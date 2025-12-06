# Glossary

> **Purpose:** Domain terminology with context for LLMs and humans.
>
> **Usage:** Reference this when encountering unfamiliar terms in metrics or reports.

---

## Core Concepts

### CID (Content Identifier)

**Definition:** A self-describing content address used throughout the IPFS ecosystem. CIDs are used in Filecoin to identify files submitted to the decentralized storage network.

**Context for LLMs:**

- CIDs are immutable—same content always produces same CID
- CIDs are derived from the content itself (content-addressed)
- Used to identify individual files within the Filecoin network
- Format: Starts with `baf...` (e.g., `bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oczesq`)

**In metrics:** `total_unique_cids`, `cid_metrics`, `unique_cids`

**Reference:** [Filecoin Spec: CID](https://spec.filecoin.io/glossary/#section-glossary.cid) | [IPLD CID Docs](https://github.com/ipld/cid)

---

### File

**Definition:** Files are what clients bring to the Filecoin system to store. A file is converted to a UnixFS DAG and placed into a Piece for storage.

**Context for LLMs:**

- Files are the original user data (e.g., `.h5`, `.tif`, `.png` files)
- Each file is converted to a DAG structure and assigned a CID
- Files are grouped into Pieces for storage deals
- The Piece is the actual unit stored by the network, not the file directly

**Relationship to CIDs and Pieces:**

- File → converted to UnixFS DAG → assigned a CID
- Multiple files are bundled into a Piece
- The CID identifies the file content; the Piece CID identifies the storage unit

**In metrics:** `total_files`, `by_filetype`, `by_filesize_bucket`

**Reference:** [Filecoin Spec: File](https://spec.filecoin.io/glossary/#section-glossary.file)

---

### Piece / PieceCID

**Definition:** The main unit of negotiation for data stored on the Filecoin network. A Piece represents a whole or part of a file used in storage deals between clients and miners.

**Context for LLMs:**

- A Piece is **not** a fixed unit of storage—it can be any size up to the sector limit (32GB or 64GB)
- If data exceeds sector size, it must be split into multiple pieces
- Created by serializing an IPLD DAG into a CAR file, then padding it to form a binary Merkle tree
- The **Piece CID (CommP)** is calculated from the padded data and is critical for deal verification
- Format: Piece CIDs start with `baga6ea4seaq...`

**Relationship to CIDs and Sectors:**

- One piece contains many file CIDs (the IPLD DAG)
- Same CID can exist in multiple pieces (across preparations)
- Pieces are placed into **sectors** for sealing and proof generation
- Multiple pieces can be packed into a single sector

**In metrics:** `total_unique_pieces`, `piece_metrics`, `pieceCid`

**Reference:** [Filecoin Spec: Piece](https://spec.filecoin.io/glossary/#section-glossary.piece)

---

### CAR File (Content Addressable aRchive)

**Definition:** The file format used to serialize IPLD DAGs for Filecoin storage. A CAR file is the serialized form of a Piece before padding.

**Context for LLMs:**

- CAR files are the actual files stored with storage providers
- Each CAR file corresponds to one piece
- Contains the raw bytes that get sealed on Filecoin

**Usage in reports:** Rarely referenced directly; pieces are the abstraction layer.

---

### Preparation

**Definition:** A batch of files processed together, using [Singularity](https://data-programs.gitbook.io/singularity/), into pieces for Filecoin storage.

**Context for LLMs:**

- Preparations are identified by numeric IDs (1, 2, 3, etc.)
- Each preparation may contain different datasets or processing runs
- Files from different preparations may have overlapping CIDs
- Preparation metadata comes from source CSV/JSON files

**In metrics:** `by_preparation`, `preparation` field in records

**Example:** "Prep 1 contains GEDI02_B data, Prep 7 contains GEDI_L4A data"

---

### Storage Provider (SP)

**Definition:** Storage providers are responsible for storing files and data for clients on the network. They also provide cryptographic proofs to verify that data is stored securely.

**Context for LLMs:**

- Commonly abbreviated as **SP** in Filecoin documentation
- Providers are identified by IDs like `f02639429`
- May have human-readable names (e.g., "Milad", "Decent")
- Different providers may have different retrieval performance
- Same piece can be stored with multiple providers (redundancy)
- Not all SPs support unsealed retrieval (some only have sealed copies)

**In metrics:** `by_storage_provider`, `providerid`, `providername`

**Reference:** [Filecoin Docs: Storage Providers](https://docs.filecoin.io/basics/what-is-filecoin/storage-model#storage-providers)

---

### Deal

**Definition:** An agreement between two participants in the Filecoin network where one party contracts the services of the other for an agreed price. The Filecoin specification defines two types:

- **Storage Deal:** One party agrees to store data for the other for a specified length of time
- **Retrieval Deal:** One party agrees to transmit specified data to the other

**Context for LLMs:**

- Deals are on-chain agreements with specific durations
- Deals track the relationship: (pieceCID, providerID) → state
- Deal states: `active`, `expired`, `slashed`, etc.
- **Only active deals are considered for primary metrics**
- This project focuses on **storage deals** and whether the stored data is **retrievable**
- A piece can have deals with multiple providers simultaneously

**In metrics:** `active_deals`, `hasactivedeal`, `activedealproviders`

**Reference:** [Filecoin Spec: Deal](https://spec.filecoin.io/glossary/#section-glossary.deal)

---

## Retrieval Concepts

### Retrieval Check

**Definition:** An attempt to fetch data from a storage provider to verify availability.

**Context for LLMs:**

- Checks are performed at both piece-level and CID-level
- Each (item, provider) combination is a separate check
- Results include HTTP status codes and response metadata

**In metrics:** `total_piece_retrieval_checks`, `total_cid_retrieval_checks`

---

### Retrieval Status

**Definition:** The outcome of a retrieval check.

**Values:**

| Status | Meaning |
|--------|---------|
| `available` | Content successfully retrieved |
| `unavailable` | Content not found or inaccessible |
| `error` | Retrieval attempt failed with error |

**Success classification:** `status == "available" AND statuscode in 200-299`

---

### HTTP Status Codes (Common)

| Code | Meaning | Classification |
|------|---------|----------------|
| 200 | Success | ✅ Success |
| 206 | Partial Content | ✅ Success |
| 404 | Not Found | ❌ Failure |
| 500 | Internal Server Error | ❌ Failure (analyzed in error_analysis) |
| 502 | Bad Gateway | ❌ Failure |
| 504 | Gateway Timeout | ❌ Failure |

---

## Metric Terminology

### Success Rate

**Definition:** Proportion of retrieval checks that succeeded.

**Formula:** `success_count / (success_count + failure_count)`

**Range:** 0.0 to 1.0 (multiply by 100 for percentage)

---

### "Any Provider" vs "All Providers"

**Any provider success:** At least one active-deal provider retrieved the item successfully.

**All providers success:** Every active-deal provider retrieved the item successfully.

**Context for LLMs:**

- "All providers" does NOT mean all providers in the network
- It means all providers **that have active deals for that specific item**
- A CID with one provider that succeeds counts as "all providers success"

⚠️ **Common confusion:** See [07-caveats-and-pitfalls.md](07-caveats-and-pitfalls.md) for detailed explanation.

---

### Retrievable vs Not Retrievable

**Retrievable:** At least one successful retrieval from an active-deal provider.

**Not retrievable by any provider:** All active-deal providers failed to retrieve.

**Not in any active deals:** No active deals exist for this item (can't be retrieved via Filecoin deals).

---

## Error Categories

| Category | Description | Typical Cause |
|----------|-------------|---------------|
| `multihash_not_found` | Content hash cannot be located | Index corruption, unsealed data |
| `root_load_failure` | Cannot load root CID/node | DAG structure issues |
| `piece_not_found` | Piece not found on provider | Missing sealed data |
| `cid_not_found` | CID not found on provider | Content not indexed |
| `timeout` | Request exceeded time limit | Network or load issues |
| `connection_error` | Connection to provider failed | Provider down or unreachable |
| `ipld_error` | IPLD processing failed | Data format issues |
| `node_not_found` | DAG node missing | Partial or corrupted piece |
| `other` | Unclassified error | Various |

---

## File Size Terminology

### Buckets

| Bucket Name | Size Range | Typical Content |
|-------------|------------|-----------------|
| 0-1MB | 0 - 1 MiB | Tiny/small files, metadata, configs |
| 1-10MB | 1 MiB - 10 MiB | Small-medium files |
| 10-100MB | 10 MiB - 100 MiB | Medium files |
| 100MB-1GB | 100 MiB - 1 GiB | Large files |
| 1GB+ | ≥ 1 GiB | Very large files |

### "1GB+ Cliff"

**Definition:** A pattern where retrieval success rate drops dramatically for files over 1GB.

**Context for LLMs:**

- Often the most significant finding in reports
- May indicate infrastructure limitations
- Should always be highlighted if present

---

## Acronyms

| Acronym | Full Form | Description |
|---------|-----------|-------------|
| CID | Content Identifier | Unique hash for content |
| CAR | Content Addressable aRchive | File format for pieces |
| IPFS | InterPlanetary File System | Distributed file system |
| IPLD | InterPlanetary Linked Data | Data model used by IPFS |
| DAG | Directed Acyclic Graph | Structure of linked CIDs |
| SP | Storage Provider | Filecoin storage operator |

---

## Data Sources

| Term | Description |
|------|-------------|
| `deals.json` | Authoritative deal state database |
| `file-metadata/*.csv` | Per-preparation file inventories |
| `piece-metadata/*.json` | Per-preparation piece inventories |
| `*_postprocessed.json` | Retrieval results after enrichment |

---

## Report Sections

| Section Name | Content | Scope |
|--------------|---------|-------|
| `overall_retrieval` | Aggregate metrics | Active deals only |
| `by_preparation` | Per-prep breakdown | Active deals only |
| `by_storage_provider` | Per-provider breakdown | Active deals only |
| `prepared_content` | All prepared content | All prepared (not just active) |
| `error_analysis` | HTTP 500 analysis | Active deals only |
