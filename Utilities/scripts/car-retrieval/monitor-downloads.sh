#!/bin/bash

# Monitor script to show active downloads
LOGS_DIR="${1:-./downloads/logs}"
ROOT_DOWNLOAD_DIR="${2:-./downloads}"
PREPARATION_ID="${3:-1}"

# Build the preparation download directory path
PREPARATION_DOWNLOAD_DIR="$ROOT_DOWNLOAD_DIR/preparation-$PREPARATION_ID"

echo "Monitoring downloads in: $LOGS_DIR"
echo "Root download directory: $ROOT_DOWNLOAD_DIR"
echo "Preparation download directory: $PREPARATION_DOWNLOAD_DIR"
echo "Press Ctrl+C to stop monitoring"
echo

while true; do
    clear
    echo "=== Download Monitor - $(date) ==="
    echo
    
    # Count active curl processes
    active_curl=$(pgrep curl | wc -l)
    echo "Active curl processes: $active_curl"
    
    # Count result files
    if [ -d "$LOGS_DIR" ]; then
        total_results=$(find "$LOGS_DIR" -name "*.result" -type f 2>/dev/null | wc -l)
        
        # Count success and failed results more reliably
        success_count=0
        failed_count=0
        if [ "$total_results" -gt 0 ]; then
            # Use find to get result files and then grep each one
            success_count=$(find "$LOGS_DIR" -name "*.result" -type f -exec grep -l "^SUCCESS:" {} \; 2>/dev/null | wc -l)
            failed_count=$(find "$LOGS_DIR" -name "*.result" -type f -exec grep -l "^FAILED:" {} \; 2>/dev/null | wc -l)
        fi
        
        echo "Completed downloads: $total_results"
        echo "  - Successful: $success_count"
        echo "  - Failed: $failed_count"
        echo
        
        # Show recent activity (last 10 results)
        echo "Recent activity:"
        # Fix the file existence check - use a glob that works properly
        result_files=$(find "$LOGS_DIR" -name "*.result" 2>/dev/null)
        if [ -n "$result_files" ]; then
            echo "$result_files" | head -10 | while read result_file; do
                if [ -f "$result_file" ]; then
                    result_content=$(cat "$result_file")
                    filename=$(basename "$result_file" .result)
                    echo "  $filename: $result_content"
                fi
            done
        else
            echo "  No result files found yet"
        fi
        
        # Show active download file sizes
        echo
        echo "Active download file sizes:"
        active_size_total=0
        active_file_count=0
        
        # Look for .car files that might be actively downloading
        # We'll check for files that have corresponding .log files but no .result files
        if ls "$LOGS_DIR"/*.log >/dev/null 2>&1; then
            for log_file in "$LOGS_DIR"/*.log; do
                piece_cid=$(basename "$log_file" .log)
                result_file="$LOGS_DIR/$piece_cid.result"
                
                # If there's a log file but no result file, it's likely still downloading
                if [ ! -f "$result_file" ]; then
                    # Look for the corresponding .car file in the specific preparation directory
                    if [ -d "$PREPARATION_DOWNLOAD_DIR" ]; then
                        car_file="$PREPARATION_DOWNLOAD_DIR/$piece_cid.car"
                        if [ -f "$car_file" ]; then
                            file_size=$(stat -c%s "$car_file" 2>/dev/null || echo "0")
                            if [ "$file_size" -gt 0 ]; then
                                active_size_total=$((active_size_total + file_size))
                                active_file_count=$((active_file_count + 1))
                                # Convert bytes to human readable format using shell arithmetic
                                if [ "$file_size" -gt 1073741824 ]; then
                                    # Convert to GB (bytes / 1024^3)
                                    size_gb=$((file_size / 1073741824))
                                    size_remainder=$((file_size % 1073741824))
                                    size_decimal=$((size_remainder * 100 / 1073741824))
                                    size_display="${size_gb}.$(printf "%02d" $size_decimal)"
                                    size_unit="GB"
                                elif [ "$file_size" -gt 1048576 ]; then
                                    # Convert to MB (bytes / 1024^2)
                                    size_mb=$((file_size / 1048576))
                                    size_remainder=$((file_size % 1048576))
                                    size_decimal=$((size_remainder * 100 / 1048576))
                                    size_display="${size_mb}.$(printf "%02d" $size_decimal)"
                                    size_unit="MB"
                                elif [ "$file_size" -gt 1024 ]; then
                                    # Convert to KB (bytes / 1024)
                                    size_kb=$((file_size / 1024))
                                    size_remainder=$((file_size % 1024))
                                    size_decimal=$((size_remainder * 100 / 1024))
                                    size_display="${size_kb}.$(printf "%02d" $size_decimal)"
                                    size_unit="KB"
                                else
                                    size_display=$file_size
                                    size_unit="bytes"
                                fi
                                echo "  $piece_cid: ${size_display} ${size_unit}"
                            fi
                        fi
                    fi
                fi
            done
        fi
        
        # Display total active download size
        if [ "$active_file_count" -gt 0 ]; then
            if [ "$active_size_total" -gt 1073741824 ]; then
                # Convert to GB using shell arithmetic
                total_gb=$((active_size_total / 1073741824))
                total_remainder=$((active_size_total % 1073741824))
                total_decimal=$((total_remainder * 100 / 1073741824))
                total_display="${total_gb}.$(printf "%02d" $total_decimal)"
                total_unit="GB"
            elif [ "$active_size_total" -gt 1048576 ]; then
                # Convert to MB using shell arithmetic
                total_mb=$((active_size_total / 1048576))
                total_remainder=$((active_size_total % 1048576))
                total_decimal=$((total_remainder * 100 / 1048576))
                total_display="${total_mb}.$(printf "%02d" $total_decimal)"
                total_unit="MB"
            elif [ "$active_size_total" -gt 1024 ]; then
                # Convert to KB using shell arithmetic
                total_kb=$((active_size_total / 1024))
                total_remainder=$((active_size_total % 1024))
                total_decimal=$((total_remainder * 100 / 1024))
                total_display="${total_kb}.$(printf "%02d" $total_decimal)"
                total_unit="KB"
            else
                total_display=$active_size_total
                total_unit="bytes"
            fi
            echo "  TOTAL: $active_file_count files, ${total_display} ${total_unit}"
        else
            echo "  No active downloads with file data found"
        fi
        
        # Show log files to verify concurrent starts
        echo
        echo "Log files (should show concurrent downloads):"
        log_files=$(find "$LOGS_DIR" -name "*.log" 2>/dev/null | wc -l)
        echo "  Total log files: $log_files"
        if [ $log_files -gt 0 ]; then
            echo "  Recent log files:"
            find "$LOGS_DIR" -name "*.log" 2>/dev/null | head -5 | while read log_file; do
                filename=$(basename "$log_file" .log)
                file_size=$(stat -c%s "$log_file" 2>/dev/null || echo "0")
                echo "    $filename (${file_size} bytes)"
            done
        fi
        
        echo
        echo "Active downloads (showing curl processes):"
        ps aux | grep curl | grep -v grep | while read line; do
            echo "  $line"
        done
    else
        echo "Logs directory not found: $LOGS_DIR"
    fi
    
    sleep 2
done
