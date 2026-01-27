# pieceCID Extraction Utility

This utility provides Bash and PowerShell scripts to extract pieceCIDs for a specific Singularity preparation and join them with filtered deal metadata into a CSV file.

## Features

- **Identification Mode**: Quickly discover available Preparation IDs, Client IDs, and Provider IDs.
- **Dynamic Naming**: Output files are named based on filters if no output path is provided.

## Scripts

- `extract_piece_cids.sh`: Bash version (requires `curl` and `jq`).
- `extract_piece_cids.ps1`: PowerShell version.

## Usage

### Extraction Mode
Extract pieceCIDs and join with deal metadata for a specific preparation.

```bash
# If you are in the script directory:
./extract_piece_cids.sh -p <prep_id> [options]

# If you are in the project root:
bash Utilities/scripts/extract-piece-cids/extract_piece_cids.sh -p <prep_id> [options]
```

```powershell
# If you are in the script directory:
.\extract_piece_cids.ps1 -PreparationID <prep_id> [options]

# If you are in the project root:
.\Utilities\scripts\extract-piece-cids\extract_piece_cids.ps1 -PreparationID <prep_id> [options]
```

### Identification Mode
List available IDs and Names from the API to help construct your query.

```bash
./extract_piece_cids.sh -i
```

```powershell
.\extract_piece_cids.ps1 -Identify
```

## Options

| Bash Option         | PowerShell Option  | Description                                     |
|---------------------|-------------------|-------------------------------------------------|
| `-p, --prep-id`     | `-PreparationID`  | **Required.** The ID of the preparation.       |
| `-s, --provider-id` | `-ProviderID`     | Filter by Storage Provider ID (e.g., f0123).    |
| `-c, --client-id`   | `-ClientID`       | Filter by Client ID.                            |
| `-e, --api-endpoint`| `-ApiEndpoint`    | Custom API URL (Default: http://212.6.53.5:9090)|
| `-d, --deal-state`  | `-DealState`      | Filter by deal state (Default: `active`).       |
| `-i, --identify`    | `-Identify`       | List IDs/Names and exit.                        |
| `-o, --output`      | `-OutputFile`     | Custom output CSV filename.                     |
| `-h, --help`        | `-h, -Help`       | Show help/usage.                                |

## CSV Output Schema

The generated CSV includes the following columns:

- **Preparation**: `PreparationName`, `PreparationID`, `PrepCreatedAt`
- **Piece**: `PieceCID`, `FileSize`, `NumOfFiles`, `RootCID`, `PieceType`
- **Deal**: `DealID`, `ProposalID`, `StorageProvider`, `ClientID`, `State`, `StartEpoch`, `StartDateTime`, `EndEpoch`, `EndDateTime`

*Dates are formatted as `yyyy-MM-dd HH:mm:ss UTC` based on the Filecoin epoch conversion.*

## Important Notes

1.  **Performance**: On Windows, use the PowerShell script for significantly faster processing of large datasets.
2.  **Dependencies**: The Bash script requires `jq`. If `column` is available, the identification output will be formatted; otherwise, it defaults to raw text.
