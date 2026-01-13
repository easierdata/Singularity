#!/bin/bash
#
# SYNOPSIS
#     Calculates the total size of active deals for a specific provider up to a cutoff epoch/date.
#
# DESCRIPTION
#     This script automates the invoice checking process by:
#     1. Fetching all deal data from the Singularity API.
#     2. Filtering by Provider ID and Deal State (default: active).
#     3. Filtering deals that started BEFORE a specific Cutoff Date or Epoch.
#     4. Summing the PieceSize of matching deals.
#     5. Converting the bytes to TiB (2^40) and rounding to 3 decimal places.
#
# USAGE
#     ./get_deal_size.sh -p <ProviderID> [-d <CutoffDate> | -e <CutoffEpoch>] [-s <State>]
#
# EXAMPLES
#     ./get_deal_size.sh -p "f02639429" -d "2026-01-01"
#     ./get_deal_size.sh -p "f02639429" -e 5630640
#

# Constants
FILECOIN_GENESIS=1598306400 # 2020-08-24 22:00:00 UTC
TiB=1099511627776

# Defaults
STATE="active"
PROVIDER=""
CUTOFF_DATE=""
CUTOFF_EPOCH=""
CLIENT_ID=""

# Dependency Check
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to run this script."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "Error: 'curl' is not installed."
    exit 1
fi

# Argument Parsing
while getopts "p:d:e:s:c:h" opt; do
  case $opt in
    p) PROVIDER="$OPTARG" ;;
    d) CUTOFF_DATE="$OPTARG" ;;
    e) CUTOFF_EPOCH="$OPTARG" ;;
    s) STATE="$OPTARG" ;;
    c) CLIENT_ID="$OPTARG" ;;
    h) 
       grep "^#" "$0" | cut -c 2-
       exit 0
       ;;
    *) 
    echo "Usage: $0 -p <ProviderID> [-d <CutoffDate> | -e <CutoffEpoch>] [-s <State>] [-c <ClientID>]"
       exit 1
       ;;
  esac
done

# Validation
if [ -z "$PROVIDER" ]; then
    echo "Error: Provider ID (-p) is required."
    exit 1
fi

# Validation & Default Calculation
if [ -z "$CUTOFF_DATE" ] && [ -z "$CUTOFF_EPOCH" ]; then
    # Default to current time
    CURRENT_TS=$(date +%s)
    DIFF_SECS=$(( CURRENT_TS - FILECOIN_GENESIS ))
    TARGET_EPOCH=$(( DIFF_SECS / 30 ))
    
    if date --version >/dev/null 2>&1; then
        EPOCH_DATE=$(date -u -d "@$CURRENT_TS" "+%Y-%m-%d %H:%M:%S UTC")
    else
        EPOCH_DATE=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
    fi
    echo "No cutoff specified. Defaulting to NOW ($EPOCH_DATE)."

elif [ -n "$CUTOFF_EPOCH" ]; then
    TARGET_EPOCH="$CUTOFF_EPOCH"
    
    # Calculate Date from Epoch for display (Linux/GNU date)
    # Note: MacOS `date` commands behave differently, this assumes GNU date (standard on most Linux/Bash)
    if date --version >/dev/null 2>&1; then
        # GNU date
        EPOCH_SECS=$(( FILECOIN_GENESIS + (TARGET_EPOCH * 30) ))
        EPOCH_DATE=$(date -u -d "@$EPOCH_SECS" "+%Y-%m-%d %H:%M:%S UTC")
    else
        # Fallback/BSD date check could go here, but keeping simple for now
        EPOCH_DATE="Epoch $TARGET_EPOCH"
    fi
else
    # Parse Date to Epoch
    # Assumes input date string is UTC-intent or handles standard ISO
    if date --version >/dev/null 2>&1; then
        # GNU date
        TARGET_TS=$(date -u -d "$CUTOFF_DATE" +%s)
    else
        # BSD/Mac date
        TARGET_TS=$(date -j -f "%Y-%m-%d" "$CUTOFF_DATE" +%s 2>/dev/null || date -u -d "$CUTOFF_DATE" +%s)
    fi

    if [ -z "$TARGET_TS" ]; then
         echo "Error: Could not parse date '$CUTOFF_DATE'."
         exit 1
    fi

    DIFF_SECS=$(( TARGET_TS - FILECOIN_GENESIS ))
    TARGET_EPOCH=$(( DIFF_SECS / 30 ))
    
    # Format the parsed date back for display
    if date --version >/dev/null 2>&1; then
        EPOCH_DATE=$(date -u -d "@$TARGET_TS" "+%Y-%m-%d %H:%M:%S UTC")
    else
        EPOCH_DATE="$CUTOFF_DATE UTC"
    fi
fi

echo -e "\033[36mFetching deal data from Singularity API...\033[0m"

JSON_RESPONSE=$(curl -s -X POST "http://212.6.53.5:9090/api/deal")

if [ -z "$JSON_RESPONSE" ]; then
    echo "Error: No response from API."
    exit 1
fi

CLIENT_MSG=""
if [ -n "$CLIENT_ID" ]; then
    CLIENT_MSG="| Client: $CLIENT_ID"
fi
echo -e "\033[36mFiltering deals for Provider: $PROVIDER | State: $STATE $CLIENT_MSG | Epoch < $TARGET_EPOCH ($EPOCH_DATE)\033[0m"

# Use jq to filter and sum
# 1. Select matching items (optionally checking clientId if set)
# 2. Extract pieceSize
# 3. Sum them up (using awk for safety if jq sum isn't sufficient, but jq reduce is powerful)
TOTAL_BYTES=$(echo "$JSON_RESPONSE" | jq -r --arg provider "$PROVIDER" --arg state "$STATE" --argjson limit "$TARGET_EPOCH" --arg client "$CLIENT_ID" '
    [.[] | select(.provider == $provider and .state == $state and .startEpoch < $limit and ($client == "" or .clientId == $client)) | .pieceSize] | add // 0
')

DEAL_COUNT=$(echo "$JSON_RESPONSE" | jq -r --arg provider "$PROVIDER" --arg state "$STATE" --argjson limit "$TARGET_EPOCH" --arg client "$CLIENT_ID" '
    [.[] | select(.provider == $provider and .state == $state and .startEpoch < $limit and ($client == "" or .clientId == $client))] | length
')

if [ "$DEAL_COUNT" -eq 0 ]; then
    TOTAL_TiB="0"
else
    # Calculate TiB with 3 decimal places using awk
    TOTAL_TiB=$(awk "BEGIN {printf \"%.3f\", $TOTAL_BYTES / $TiB}")
fi

echo
echo "--------------------------------------------------"
echo "Snapshot Report"
echo "--------------------------------------------------"
echo "Provider    : $PROVIDER"
if [ -n "$CLIENT_ID" ]; then
    echo "Client      : $CLIENT_ID"
fi
echo "Cutoff Epoch: $TARGET_EPOCH ($EPOCH_DATE)"
echo "Deal Count  : $DEAL_COUNT"
echo -e "Total Size  : \033[33m$TOTAL_TiB TiB\033[0m"
echo "--------------------------------------------------"
echo
