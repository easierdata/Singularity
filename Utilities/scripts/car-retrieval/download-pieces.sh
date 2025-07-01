#!/bin/bash

# Script to download pieces from Singularity preparation
# Usage: ./download-pieces.sh <preparation_id> [max_concurrent_downloads] [output_directory] [--force-redownload] [--verify-existing] [--curl-config <file>] [--api-host <host>] [--download-host <host>] [--config <file>]

set -e

# Configuration file path (can be overridden by --config parameter)
CONFIG_FILE="configs/singularity-config.json"

# Default hosts (fallback if no config file, env vars, or CLI args)
DEFAULT_API_HOST="http://212.6.53.5:9090"
DEFAULT_DOWNLOAD_HOST="http://212.6.53.5:7777"

# Function to read config file
read_config() {
    local config_file="$1"
    if [ -f "$config_file" ]; then
        echo "Reading configuration from: $config_file" >&2
        if command -v jq &> /dev/null; then
            # Validate JSON and extract values
            if jq empty "$config_file" 2>/dev/null; then
                CONFIG_API_HOST=$(jq -r '.endpoints.api_host // empty' "$config_file" 2>/dev/null)
                CONFIG_DOWNLOAD_HOST=$(jq -r '.endpoints.download_host // empty' "$config_file" 2>/dev/null)
                CONFIG_MAX_CONCURRENT=$(jq -r '.defaults.max_concurrent_downloads // empty' "$config_file" 2>/dev/null)
                CONFIG_CURL_CONFIG=$(jq -r '.curl.config_file // empty' "$config_file" 2>/dev/null)
                return 0
            else
                echo "Warning: Invalid JSON in config file: $config_file" >&2
                return 1
            fi
        else
            echo "Warning: jq not found, cannot read config file" >&2
            return 1
        fi
    fi
    return 1
}

# Parse arguments first to get potential --config parameter
TEMP_ARGS=("$@")
for ((i=0; i<${#TEMP_ARGS[@]}; i++)); do
    if [[ "${TEMP_ARGS[i]}" == "--config" && $((i+1)) -lt ${#TEMP_ARGS[@]} ]]; then
        CONFIG_FILE="${TEMP_ARGS[$((i+1))]}"
        break
    fi
done

# Read configuration file
CONFIG_API_HOST=""
CONFIG_DOWNLOAD_HOST=""
CONFIG_MAX_CONCURRENT=""
CONFIG_CURL_CONFIG=""
read_config "$CONFIG_FILE" || true

# Determine hosts using priority: CLI args > env vars > config file > defaults
# (CLI args will be processed later, for now get config file and env var values)
if [ -n "$CONFIG_API_HOST" ]; then
    API_HOST="${SINGULARITY_API_HOST:-$CONFIG_API_HOST}"
else
    API_HOST="${SINGULARITY_API_HOST:-$DEFAULT_API_HOST}"
fi

if [ -n "$CONFIG_DOWNLOAD_HOST" ]; then
    DOWNLOAD_HOST="${SINGULARITY_DOWNLOAD_HOST:-$CONFIG_DOWNLOAD_HOST}"
else
    DOWNLOAD_HOST="${SINGULARITY_DOWNLOAD_HOST:-$DEFAULT_DOWNLOAD_HOST}"
fi

# Check if the API_HOST and DOWNLOAD_HOST are reachable via curl commands. Getting a `HTTP/1.1 404 Not Found` response is acceptable
check_host_accessibility() {
    local host="$1"
    if ! curl -s --head "$host" | grep -q "200 OK\|404 Not Found"; then
        echo "Error: Host $host is not accessible or does not respond with 200 OK or 404 Not Found"
        exit 1
    fi
}

check_host_accessibility "$API_HOST"
check_host_accessibility "$DOWNLOAD_HOST"

# Parse arguments
PREPARATION_ID="$1"
MAX_CONCURRENT_DOWNLOADS="${2:-${CONFIG_MAX_CONCURRENT:-8}}"
OUTPUT_ROOT_DIRECTORY="${3:-.}"
FORCE_REDOWNLOAD=false
VERIFY_EXISTING=false
CURL_CONFIG_FILE="${CONFIG_CURL_CONFIG:-}"

# Parse optional flags
shift 3 2>/dev/null || true  # Shift past the first 3 args, ignore error if < 3 args
while [[ $# -gt 0 ]]; do
    case $1 in
        --force-redownload)
            FORCE_REDOWNLOAD=true
            shift
            ;;
        --verify-existing)
            VERIFY_EXISTING=true
            shift
            ;;
        --curl-config)
            CURL_CONFIG_FILE="$2"
            shift 2
            ;;
        --api-host)
            API_HOST="$2"
            shift 2
            ;;
        --download-host)
            DOWNLOAD_HOST="$2"
            shift 2
            ;;
        --config)
            # Already processed above, just skip
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 <preparation_id> [max_concurrent] [output_directory] [--force-redownload] [--verify-existing] [--curl-config <file>] [--api-host <host>] [--download-host <host>] [--config <file>]"
            exit 1
            ;;
    esac
done

# Reset positional parameters for backward compatibility
set -- "$PREPARATION_ID" "$MAX_CONCURRENT_DOWNLOADS" "$OUTPUT_ROOT_DIRECTORY"

# Validate required arguments
if [ -z "$PREPARATION_ID" ]; then
    echo "Error: Preparation ID is required"
    echo "Usage: $0 <preparation_id> [max_concurrent_downloads] [output_directory]"
    exit 1
fi

# Validate preparation ID is numeric
if ! [[ "$PREPARATION_ID" =~ ^[0-9]+$ ]]; then
    echo "Error: Preparation ID must be a number"
    exit 1
fi

# Validate max concurrent downloads is numeric
if ! [[ "$MAX_CONCURRENT_DOWNLOADS" =~ ^[0-9]+$ ]]; then
    echo "Error: Max concurrent downloads must be a number"
    exit 1
fi

OUTPUT_DIRECTORY="$OUTPUT_ROOT_DIRECTORY/preparation-$PREPARATION_ID"
# Create logs directory for tracking downloads
LOGS_DIR="${OUTPUT_ROOT_DIRECTORY}/logs"

echo "Starting download process for preparation ID: $PREPARATION_ID"
echo "Max concurrent downloads: $MAX_CONCURRENT_DOWNLOADS"
echo "Output directory: $OUTPUT_DIRECTORY"
echo "Logs directory: $LOGS_DIR"
echo "API Host: $API_HOST"
echo "Download Host: $DOWNLOAD_HOST"

# Validate curl config file if provided
if [ -n "$CURL_CONFIG_FILE" ]; then
    if [ -f "$CURL_CONFIG_FILE" ]; then
        echo "Using curl config file: $CURL_CONFIG_FILE"
    else
        echo "Error: Curl config file not found: $CURL_CONFIG_FILE"
        exit 1
    fi
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIRECTORY"
mkdir -p "$LOGS_DIR"
# echo "export LOGS_DIR=\"$LOGS_DIR\"" > ~/.bashrc

# Step 1: Download or use existing JSON file
JSON_FILENAME="preparation-${PREPARATION_ID}-piece.json"
JSON_FILEPATH="$OUTPUT_DIRECTORY/$JSON_FILENAME"
API_URL="$API_HOST/api/preparation/$PREPARATION_ID/piece"

# Check if JSON file already exists
if [ -f "$JSON_FILEPATH" ] && [ "$FORCE_REDOWNLOAD" = false ]; then
    echo "Using existing JSON file: $JSON_FILEPATH"
    
    # Validate that the existing JSON is valid
    if ! jq empty "$JSON_FILEPATH" 2>/dev/null; then
        echo "Warning: Existing JSON file is empty, downloading fresh copy..."
        rm "$JSON_FILEPATH" || true
    else
        echo "Existing JSON file is valid, skipping API call"
    fi
fi

# Download JSON file only if it doesn't exist or is invalid
if [ ! -f "$JSON_FILEPATH" ]; then
    echo "Fetching data from: $API_URL"
    
    if ! curl -s -o "$JSON_FILEPATH" "$API_URL"; then
        echo "Error: Failed to fetch data from API"
        exit 1
    fi
    
    echo "JSON saved to: $JSON_FILEPATH"
fi

# Step 2: Parse pieces and validate JSON
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq to parse JSON."
    exit 1
fi

# Check if pieces array exists and has content
PIECES_COUNT=$(jq -r '.[0].pieces | length' "$JSON_FILEPATH" 2>/dev/null || echo "0")

if [ "$PIECES_COUNT" -eq 0 ]; then
    echo "Warning: No pieces found in the response"
    exit 0
fi

echo "Found $PIECES_COUNT pieces to download"

# Extract piece CIDs for filtering
PIECE_CIDS=$(jq -r '.[0].pieces[].pieceCid' "$JSON_FILEPATH")

# Check if PIECE_CIDS was extracted properly
if [ -z "$PIECE_CIDS" ]; then
    echo "Error: Failed to extract piece CIDs from JSON"
    exit 1
fi

# Step 2.5: Check for existing downloads and filter pieces
echo "Checking for existing downloads..."

EXISTING_COUNT=0
SKIPPED_COUNT=0
INVALID_COUNT=0

# Get list of existing .car files
if [ -d "$OUTPUT_DIRECTORY" ]; then
    EXISTING_COUNT=$(find "$OUTPUT_DIRECTORY" -name "*.car" -type f | wc -l)
    echo "Found $EXISTING_COUNT existing .car files"
fi

# Create array of pieces that need to be downloaded
PIECES_TO_DOWNLOAD=()
PROCESSED_COUNT=0

# Process each piece CID
while IFS= read -r piece_cid; do
    # Skip empty lines
    if [ -z "$piece_cid" ]; then
        continue
    fi
    
    PROCESSED_COUNT=$((PROCESSED_COUNT + 1))
    output_file="$OUTPUT_DIRECTORY/${piece_cid}.car"
    
    if [ -f "$output_file" ] && [ "$FORCE_REDOWNLOAD" = false ]; then
        if [ "$VERIFY_EXISTING" = true ]; then
            # Check if file has content (not empty)
            if [ -s "$output_file" ]; then
                echo "Skipping existing valid file: $piece_cid"
                SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
                continue
            else
                echo "Found empty file, will redownload: $piece_cid"
                rm "$output_file" || true
                INVALID_COUNT=$((INVALID_COUNT + 1))
            fi
        else
            echo "Skipping existing file: $piece_cid"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi
    fi
    
    PIECES_TO_DOWNLOAD+=("$piece_cid")
done <<< "$PIECE_CIDS"

if [ $SKIPPED_COUNT -gt 0 ]; then
    echo "Skipped $SKIPPED_COUNT existing files"
fi

if [ $INVALID_COUNT -gt 0 ]; then
    echo "Found $INVALID_COUNT invalid files that will be redownloaded"
fi

if [ ${#PIECES_TO_DOWNLOAD[@]} -eq 0 ]; then
    echo "All pieces already downloaded! Use --force-redownload to download again."
    exit 0
fi

echo "Need to download ${#PIECES_TO_DOWNLOAD[@]} pieces"

# Step 3: Download pieces with xargs concurrency control
PIECE_DOWNLOAD_URL="$DOWNLOAD_HOST/piece/"
TOTAL_PIECES=${#PIECES_TO_DOWNLOAD[@]}
START_TIME=$(date +%s)

# Function to download a single piece (will be called by xargs)
download_piece() {
    local piece_cid="$1"
    local output_file="$OUTPUT_DIRECTORY/${piece_cid}.car"
    local download_url="${PIECE_DOWNLOAD_URL}${piece_cid}"
    local start_time=$(date +%s)
    
    echo "Starting download: $piece_cid"
    
    if [ -n "$CURL_CONFIG_FILE" ] && [ -f "$CURL_CONFIG_FILE" ]; then
        curl --config "$CURL_CONFIG_FILE" -v "$download_url" --output "$output_file" 2>"$LOGS_DIR/${piece_cid}.log"
    else
        curl -v "$download_url" --output "$output_file" 2>"$LOGS_DIR/${piece_cid}.log"
    fi

    if [ $? -eq 0 ]; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "Completed download: $piece_cid (took ${duration} seconds)"
        echo "SUCCESS:$piece_cid | $((duration / 60)) minutes" > "$LOGS_DIR/${piece_cid}.result"
    else
        local exit_code=$?
        echo "Failed to download: $piece_cid (curl exit code: $exit_code)"
        echo "FAILED:$piece_cid:$exit_code" > "$LOGS_DIR/${piece_cid}.result"
        # Remove partial file if it exists
        [ -f "$output_file" ] && rm "$output_file"
    fi
}

# Export function and variables so they're available to xargs subprocesses
export -f download_piece
export OUTPUT_DIRECTORY
export LOGS_DIR
export PIECE_DOWNLOAD_URL
export CURL_CONFIG_FILE

echo "Starting concurrent downloads..."

# Use printf to output each piece CID on a separate line, then pipe to xargs
printf '%s\n' "${PIECES_TO_DOWNLOAD[@]}" | xargs -P"$MAX_CONCURRENT_DOWNLOADS" -I{} bash -c 'download_piece "{}"'

echo "All downloads completed!"

# Final count of results
COMPLETED_PIECES=0
FAILED_PIECES=0
FAILED_CIDS=()

for result_file in "$LOGS_DIR"/*.result; do
    if [ -f "$result_file" ]; then
        result_content=$(cat "$result_file")
        if [[ "$result_content" =~ ^SUCCESS: ]]; then
            ((COMPLETED_PIECES++))
        elif [[ "$result_content" =~ ^FAILED: ]]; then
            ((FAILED_PIECES++))
            failed_cid=$(echo "$result_content" | cut -d: -f2)
            FAILED_CIDS+=("$failed_cid")
        fi
    fi
done

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
TOTAL_MINUTES=$((TOTAL_DURATION / 60))
REMAINING_SECONDS=$((TOTAL_DURATION % 60))

echo
echo "=== Download Summary ==="
echo "Total pieces: $TOTAL_PIECES"
echo "Successful downloads: $COMPLETED_PIECES"
echo "Failed downloads: $FAILED_PIECES"
echo "Total time: ${TOTAL_MINUTES}m ${REMAINING_SECONDS}s"

if [ $FAILED_PIECES -gt 0 ]; then
    echo
    echo "Failed downloads:"
    for failed_cid in "${FAILED_CIDS[@]}"; do
        if [ -f "$LOGS_DIR/${failed_cid}.result" ]; then
            local error_info=$(cat "$LOGS_DIR/${failed_cid}.result" | cut -d: -f3)
            echo "  - $failed_cid: curl exit code $error_info"
        fi
    done
fi

echo
echo "Download process completed!"

# Exit with error code if any downloads failed
if [ $FAILED_PIECES -gt 0 ]; then
    exit 1
fi