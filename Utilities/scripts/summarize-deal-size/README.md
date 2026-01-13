# Summarize total Size of Deals

Scripts to automate the process of summarizing the total size of sealed deals on Filecoin. Details about deals are fetched from the Singularity API via the `/deals` endpoint.

## PowerShell (Windows)

**Usage:**

```powershell
.\get_deal_size.ps1 -ProviderID "f02639429" -CutoffDate "2026-01-01"
```

## Shell Script (Linux/Mac)

**Dependencies:**
Requires `curl`, `awk`, and `jq`.

> **Note:** You must install [`jq`](https://jqlang.github.io/jq/) to run this script.
>
> * Ubuntu/Debian: `sudo apt install jq`
> * MacOS: `brew install jq`

**Usage:**

```bash
chmod +x get_deal_size.sh
./get_deal_size.sh -p "f02639429" -d "2026-01-01"
```

## Parameters

| Parameter | Flag (sh) | Description |
| :--- | :--- | :--- |
| `ProviderID` | `-p` | **Required.** Target Storage Provider ID. |
| `CutoffDate` | `-d` | Filter deals *strictly before* this date. Defaults to **Now** if omitted. |
| `CutoffEpoch` | `-e` | Optional override to specify Epoch directly. |
| `State` | `-s` | Deal state (Default: "active"). |
| `ClientID` | `-c` | Optional. Filter by Client ID (e.g., `f0123`). |
