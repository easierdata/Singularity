#!/bin/bash

# Debug script to test concurrent downloads with a smaller sample
# Usage: ./debug-concurrency.sh [max_concurrent] [test_pieces]

MAX_CONCURRENT="${1:-4}"
TEST_PIECES="${2:-8}"
OUTPUT_DIR="./downloads/debug-test"
LOGS_DIR="./downloads/logs"

echo "=== Concurrency Debug Test ==="
echo "Testing $MAX_CONCURRENT concurrent downloads with $TEST_PIECES test pieces"
echo "Output directory: $OUTPUT_DIR"
echo

# Create directories
mkdir -p "$OUTPUT_DIR" "$LOGS_DIR"

# Clean up any previous test
rm -f "$LOGS_DIR"/debug-*.log "$LOGS_DIR"/debug-*.result
rm -f "$OUTPUT_DIR"/debug-*.txt

# Test URLs - using httpbin.org delay endpoint for testing
BASE_URL="https://httpbin.org/delay"

# Track running jobs
declare -A RUNNING_JOBS
JOB_COUNTER=0

# Function to download a test piece
download_test_piece() {
    local piece_id="$1"
    local delay="$2"
    local output_file="$OUTPUT_DIR/debug-piece-${piece_id}.txt"
    local download_url="${BASE_URL}/${delay}"
    local start_time=$(date +%s)
    local pid=$$
    
    echo "[PID:$pid] Starting test download: piece-$piece_id (${delay}s delay) at $(date)"
    
    # Download with debugging - removed unsupported --fresh-connect option
    if curl --silent --show-error --fail --no-keepalive \
           "$download_url" --output "$output_file" 2>"$LOGS_DIR/debug-piece-${piece_id}.log"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "[PID:$pid] Completed test download: piece-$piece_id (took ${duration} seconds)"
        echo "SUCCESS:piece-$piece_id:$duration" > "$LOGS_DIR/debug-piece-${piece_id}.result"
    else
        local exit_code=$?
        echo "[PID:$pid] Failed test download: piece-$piece_id (curl exit code: $exit_code)"
        echo "FAILED:piece-$piece_id:$exit_code" > "$LOGS_DIR/debug-piece-${piece_id}.result"
    fi
}

echo "Starting concurrent test downloads..."

# Start test downloads
for i in $(seq 1 $TEST_PIECES); do
    # Clean up completed jobs
    for pid in "${!RUNNING_JOBS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            unset RUNNING_JOBS[$pid]
        fi
    done
    
    # Wait if at max capacity
    while [ ${#RUNNING_JOBS[@]} -ge $MAX_CONCURRENT ]; do
        sleep 0.1
        for pid in "${!RUNNING_JOBS[@]}"; do
            if ! kill -0 "$pid" 2>/dev/null; then
                unset RUNNING_JOBS[$pid]
            fi
        done
        echo "Waiting... Active downloads: ${#RUNNING_JOBS[@]}/$MAX_CONCURRENT"
    done
    
    # Start new download (3 second delay for testing)
    download_test_piece "$i" "3" &
    job_pid=$!
    RUNNING_JOBS[$job_pid]="piece-$i"
    
    ((JOB_COUNTER++))
    echo "Started test job $JOB_COUNTER/$TEST_PIECES for piece-$i (PID: $job_pid) - Active: ${#RUNNING_JOBS[@]}"
    
    sleep 0.1
done

echo "All test downloads started. Waiting for completion..."

# Wait for all jobs to complete
while [ ${#RUNNING_JOBS[@]} -gt 0 ]; do
    for pid in "${!RUNNING_JOBS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            unset RUNNING_JOBS[$pid]
        fi
    done
    sleep 0.5
    echo "Waiting for ${#RUNNING_JOBS[@]} downloads to complete..."
done

echo
echo "=== Test Results ==="

# Count results
success_count=0
failed_count=0

for i in $(seq 1 $TEST_PIECES); do
    result_file="$LOGS_DIR/debug-piece-${i}.result"
    if [ -f "$result_file" ]; then
        result=$(cat "$result_file")
        if [[ "$result" =~ ^SUCCESS ]]; then
            ((success_count++))
            duration=$(echo "$result" | cut -d: -f3)
            echo "✓ Piece-$i: Success (${duration}s)"
        else
            ((failed_count++))
            echo "✗ Piece-$i: Failed"
        fi
    else
        echo "? Piece-$i: No result file"
        ((failed_count++))
    fi
done

echo
echo "Summary: $success_count successful, $failed_count failed"

if [ $success_count -eq $TEST_PIECES ]; then
    echo "✓ All test downloads completed successfully!"
    echo "This confirms concurrent downloads are working."
else
    echo "⚠ Some downloads failed. Check the logs in $LOGS_DIR"
fi

echo
echo "To test your actual Singularity downloads, run:"
echo "docker-compose up -d"
echo "docker exec -it singularity-downloader ./download-pieces.sh 1 32 /downloads"