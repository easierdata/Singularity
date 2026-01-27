#!/bin/bash
#
# SYNOPSIS
#     Extracts pieceCIDs for a specific preparation and joins with deal metadata.
#
# USAGE
#     ./extract_piece_cids.sh -p <PrepID> [-s <ProviderID>] [-c <ClientID>] [-e <Endpoint>] [-d <State>] [-o <OutputFile>]
#     ./extract_piece_cids.sh --identify
#

# Sourcing Protection - Prevent killing the shell if sourced
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    echo -e "\033[31mError: Do not source this script (e.g. '. ./script.sh').\033[0m"
    echo -e "Run it as a command: bash ./extract_piece_cids.sh [options]"
    return 1 2>/dev/null
fi

# Defaults
API_ENDPOINT="http://212.6.53.5:9090"
FILECOIN_GENESIS=1598306400 # 2020-08-24 22:00:00 UTC
DEAL_STATE="active"
PREP_ID=""
PROVIDER_ID=""
CLIENT_ID=""
OUTPUT_FILE=""
IDENTIFY=false

# Dependency Check
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to run this script."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "Error: 'curl' is not installed."
    exit 1
fi

# Helper: Show Help
show_help() {
    echo "pieceCID Extraction Utility"
    echo "Extracts pieceCIDs for a specific preparation and joins with deal metadata."
    echo
    echo "Usage:"
    echo "  ./extract_piece_cids.sh -p <PrepID> [options]"
    echo "  ./extract_piece_cids.sh --identify"
    echo
    echo "Options:"
    echo "  -p, --prep-id        Preparation ID (Required for extraction)"
    echo "  -s, --provider-id    Filter by Storage Provider ID"
    echo "  -c, --client-id      Filter by Client ID"
    echo "  -e, --api-endpoint   Singularity API endpoint (Default: $API_ENDPOINT)"
    echo "  -d, --deal-state     Filter by deal state (Default: $DEAL_STATE)"
    echo "  -i, --identify       List available IDs and Names, then exit"
    echo "  -o, --output         Output CSV filename"
    echo "  -h, --help           Show this help"
    exit 0
}

# Argument Parsing
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--prep-id) PREP_ID="$2"; shift 2 ;;
        -s|--provider-id) PROVIDER_ID="$2"; shift 2 ;;
        -c|--client-id) CLIENT_ID="$2"; shift 2 ;;
        -e|--api-endpoint) API_ENDPOINT="$2"; shift 2 ;;
        -d|--deal-state) DEAL_STATE="$2"; shift 2 ;;
        -i|--identify) IDENTIFY=true; shift ;;
        -o|--output) OUTPUT_FILE="$2"; shift 2 ;;
        -h|--help) show_help ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ "$IDENTIFY" = false ] && [ -z "$PREP_ID" ]; then
    echo "Error: Preparation ID (-p) is required unless using --identify."
    exit 1
fi

# Normalize API Endpoint (remove trailing slash)
API_ENDPOINT="${API_ENDPOINT%/}"

if [ "$IDENTIFY" = true ]; then
    echo -e "\033[36mStep 1/2: Fetching available IDs and Names...\033[0m"
    
    PREPS_JSON=$(curl -s "$API_ENDPOINT/api/preparation")
    DEALS_JSON=$(curl -s -X POST "$API_ENDPOINT/api/deal")

    echo -e "\033[36mStep 2/2: Formatting output...\033[0m"
    echo -e "\n\033[1mAvailable Preparations:\033[0m"
    echo "ID    | Name"
    echo "------|--------------------------------"
    echo "$PREPS_JSON" | jq -r '.[] | "\(.id) |   \(.name)"' | column -t -s '|' || echo "$PREPS_JSON" | jq -r '.[] | "\(.id) | \(.name)"'
    
    echo -e "\n\033[1mAvailable Monitoring Entities (from deals):\033[0m"
    echo -e "Client IDs:"
    echo "$DEALS_JSON" | jq -r '[.[] | .clientId] | unique | .[]' | sed 's/^/  - /'
    
    echo -e "\nStorage Provider IDs:"
    echo "$DEALS_JSON" | jq -r '[.[] | .provider] | unique | .[]' | sed 's/^/  - /'
    
    exit 0
fi

echo -e "\033[36mFetching piece and deal data...\033[0m"

# 1. Fetch data directly to temporary files for efficiency
# Use local directory to avoid cross-environment path issues
PIECE_FILE=$(mktemp ./.tmp_piece_XXXXXX)
DEAL_FILE=$(mktemp ./.tmp_deal_XXXXXX)

# Cleanup on exit
cleanup() {
    rm -f "$DEAL_FILE" "$PIECE_FILE"
}
trap cleanup EXIT INT TERM

# Extract preparation metadata and pieces in one go
if ! curl -s -o "$PIECE_FILE" "$API_ENDPOINT/api/preparation/$PREP_ID/piece"; then
    echo "Error: Failed to fetch piece data from $API_ENDPOINT/api/preparation/$PREP_ID/piece"
    rm "$PIECE_FILE" "$DEAL_FILE"
    exit 1
fi

# Fetch all deals
if ! curl -s -X POST -o "$DEAL_FILE" "$API_ENDPOINT/api/deal"; then
    echo "Error: Failed to fetch deal data from $API_ENDPOINT/api/deal"
    rm "$PIECE_FILE" "$DEAL_FILE"
    exit 1
fi

# 2. Extract Preparation Metadata
# Fetch the full list to find the name/createdAt for this ID
PREP_METADATA=$(curl -s "$API_ENDPOINT/api/preparation" | jq -r --arg id "$PREP_ID" '.[] | select(.id == ($id|tonumber))')
if [ -z "$PREP_METADATA" ]; then
    echo "Warning: Preparation ID $PREP_ID not found in preparation list. Using defaults."
    PREP_NAME="unknown"
    PREP_CREATED="unknown"
else
    PREP_NAME=$(echo "$PREP_METADATA" | jq -r '.name // "unknown"')
    PREP_CREATED=$(echo "$PREP_METADATA" | jq -r '.createdAt // "unknown"')
fi

# 3. Dynamic Filename
if [ -z "$OUTPUT_FILE" ]; then
    FILE_SUFFIX=""
    [ -n "$PROVIDER_ID" ] && FILE_SUFFIX="$FILE_SUFFIX-$PROVIDER_ID"
    [ -n "$CLIENT_ID" ] && FILE_SUFFIX="$FILE_SUFFIX-$CLIENT_ID"
    [ -n "$DEAL_STATE" ] && [ "$DEAL_STATE" != "active" ] && FILE_SUFFIX="$FILE_SUFFIX-$DEAL_STATE"
    OUTPUT_FILE="prep-$PREP_ID-piece-cids${FILE_SUFFIX}.csv"
fi

echo -e "\033[36mProcessing data and generating CSV: $OUTPUT_FILE\033[0m"

# 4. Join and Generate CSV
# Use jq with --slurpfile for deals but pipe the pieces to reduce memory overhead
HEADER="PreparationName,PreparationID,PrepCreatedAt,PieceCID,FileSize,NumOfFiles,RootCID,PieceType,DealID,ProposalID,StorageProvider,ClientID,State,StartEpoch,StartDateTime,EndEpoch,EndDateTime"
echo "$HEADER" > "$OUTPUT_FILE"

echo -e "\033[36mStep 2/3: Processing JSON data (this may take a minute for large datasets)...\033[0m"

# Build the CSV using JQ
# Optimization: Building the lookup table in one pass, then streaming the pieces
jq -r --slurpfile deals "$DEAL_FILE" \
    --arg prepName "$PREP_NAME" --arg prepId "$PREP_ID" --arg prepCreated "$PREP_CREATED" \
    --arg provider "$PROVIDER_ID" --arg client "$CLIENT_ID" --arg state "$DEAL_STATE" \
    --argjson genesis "$FILECOIN_GENESIS" '
    # Create lookup map of filtered deals: pieceCid -> Array of deals
    ($deals[0] | reduce .[] as $d ({}; 
        if (($state == "" or $d.state == $state) and
            ($provider == "" or $d.provider == $provider) and
            ($client == "" or $d.clientId == $client)) then
            .[$d.pieceCid] += [$d]
        else
            .
        end
    )) as $lookup |

    .[] | .pieces[] | . as $piece |
    $lookup[$piece.pieceCid] | select(. != null) | .[] | . as $deal |
    [
        $prepName,
        $prepId,
        $prepCreated,
        $piece.pieceCid,
        $piece.fileSize,
        $piece.numOfFiles,
        $piece.rootCid,
        $piece.pieceType,
        ($deal.dealId // ""),
        ($deal.proposalId // ""),
        ($deal.provider // ""),
        ($deal.clientId // ""),
        ($deal.state // ""),
        ($deal.startEpoch // ""),
        (if $deal.startEpoch then ($deal.startEpoch * 30 + $genesis | strftime("%Y-%m-%d %H:%M:%S UTC")) else "" end),
        ($deal.endEpoch // ""),
        (if $deal.endEpoch then ($deal.endEpoch * 30 + $genesis | strftime("%Y-%m-%d %H:%M:%S UTC")) else "" end)
    ] | @csv
' "$PIECE_FILE" >> "$OUTPUT_FILE"

echo -e "\033[32mDone! CSV saved to $OUTPUT_FILE\033[0m"
TOTAL_PIECES_PREP=$(jq '[.[] | .pieces[]] | length' "$PIECE_FILE")
DEAL_COUNT=$(tail -n +2 "$OUTPUT_FILE" | grep -v ',"",$\|,"",$*' | wc -l)
PIECE_COUNT=$(tail -n +2 "$OUTPUT_FILE" | wc -l)
echo "Total Rows: $PIECE_COUNT (Matched Deals: $DEAL_COUNT | Total Pieces in Preparation: $TOTAL_PIECES_PREP)"
