#!/bin/bash

# This script prepares the generated sample data using Kubo CLI

set -e  # Exit on any error

echo "Starting IPFS content preparation..."

# Check if ipfs is available
if ! command -v ipfs &> /dev/null; then
    echo "Error: IPFS command not found"
    exit 1
fi

# Setup output directory and files
OUTPUT_DIR="/data/comparison_output"
IPFS_OUTPUT_FILE="$OUTPUT_DIR/ipfs_cids.json"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Initialize JSON file
echo "[" > "$IPFS_OUTPUT_FILE"

# Operations to perform:
# 1. Run the command `ipfs init --profile test-cid-v1-wide` to initialize a new IPFS datastore
echo "Step 1: Initializing IPFS datastore with CID v1 profile..."
export IPFS_PATH="/home/appuser/.ipfs"

# Check if IPFS is already initialized
if [ -d "/home/appuser/.ipfs" ]; then
    echo "IPFS already initialized, skipping init..."
else
    ipfs init --profile test-cid-v1-wide
    if [ $? -eq 0 ]; then
        echo "✓ IPFS datastore initialized successfully"
    else
        echo "✗ Failed to initialize IPFS datastore"
        exit 1
    fi
fi

# 2. Add all sample data to IPFS and capture CIDs (no daemon needed)
echo "Step 2: Adding sample data to IPFS and capturing CIDs..."
sample_data_dir="/data/sample_data"

if [ ! -d "$sample_data_dir" ]; then
    echo "✗ Sample data directory not found: $sample_data_dir"
    echo "Please run prepare_testing_data.sh first to generate sample data"
    exit 1
fi

# Add all content recursively in one command and capture output
echo "Adding content recursively from: $sample_data_dir"

# Track if we need comma separators for JSON
first_entry=true

# Add content recursively and parse output
ipfs add -r --only-hash --pin=true --progress=false --cid-version=1 "$sample_data_dir" | while IFS= read -r line; do
    # Parse the output line: "added <CID> <filename>"
    if [[ $line =~ ^added[[:space:]]+([[:alnum:]]+)[[:space:]]+(.+)$ ]]; then
        cid="${BASH_REMATCH[1]}"
        full_path="${BASH_REMATCH[2]}"
        
        # Extract filename (everything after the last '/')
        if [[ "$full_path" == *"/"* ]]; then
            filename="${full_path##*/}"  # Extract everything after the last '/'
        else
            filename="$full_path"
        fi
        
        # Skip if this is just a directory (no actual file)
        # We want individual files, not the directory containers
        if [[ "$full_path" != *"/"*"/"* ]] && [[ "$full_path" == *"/"* ]]; then
            # This is likely a top-level directory, skip it
            continue
        fi
        
        # Add comma separator for JSON array (except for first entry)
        if [ "$first_entry" = true ]; then
            first_entry=false
        else
            echo "," >> "$IPFS_OUTPUT_FILE"
        fi
        
        # Create JSON entry
        echo "  {" >> "$IPFS_OUTPUT_FILE"
        echo "    \"cid\": \"$cid\"," >> "$IPFS_OUTPUT_FILE"
        echo "    \"filename\": \"$filename\"," >> "$IPFS_OUTPUT_FILE"
        echo "    \"full_path\": \"$full_path\"" >> "$IPFS_OUTPUT_FILE"
        echo -n "  }" >> "$IPFS_OUTPUT_FILE"
        
        echo "  Captured: $cid -> $filename (from $full_path)"
    fi
done

# Close JSON array
echo "" >> "$IPFS_OUTPUT_FILE"
echo "]" >> "$IPFS_OUTPUT_FILE"

echo "Step 3: Verifying added content..."
echo "Total pinned objects:"
ipfs pin ls --type=recursive | wc -l

echo "Step 4: Saving IPFS CID information..."
echo "✓ IPFS CIDs saved to: $IPFS_OUTPUT_FILE"

# Display summary
cid_count=$(grep -c '"cid"' "$IPFS_OUTPUT_FILE" 2>/dev/null || echo "0")
echo "✓ Captured $cid_count CIDs from IPFS"

echo ""
echo "IPFS content preparation completed successfully!"
echo "CID information saved to: $IPFS_OUTPUT_FILE"
echo ""
echo "Sample JSON entries:"
head -20 "$IPFS_OUTPUT_FILE"
echo "..."
echo ""
echo "You can now run the CID comparison script."
