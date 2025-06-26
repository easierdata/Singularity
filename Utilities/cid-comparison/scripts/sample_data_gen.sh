#!/bin/bash

# -----------------------------------------------------------------------------------------
# Script based on this gist: https://gist.github.com/jcace/f811078f5cc110425cb317b3b87da654
# Generate a directory of sample data at a provided output folder of the following
#    - A folder containing N number of "small" files at defined size in MB
#    - A folder with an empty folder inside
#    - A single "large" file at a defined size in GB
# -----------------------------------------------------------------------------------------

# Default values (used if parameters are not provided)
DEFAULT_SMALL_FILE_COUNT=25
DEFAULT_SMALL_FILE_SIZE=25        # 25MB
DEFAULT_LARGE_FILE_SIZE=3         # 3GB

# Check if minimum required argument is provided
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <output_directory> [small_file_count] [small_file_size_mb] [large_file_size_gb]"
    echo ""
    echo "Parameters:"
    echo "  output_directory     - Required: Directory where sample data will be created"
    echo "  small_file_count     - Optional: Number of small files to create (default: $DEFAULT_SMALL_FILE_COUNT)"
    echo "  small_file_size_mb   - Optional: Size of each small file in MB (default: $DEFAULT_SMALL_FILE_SIZE)"
    echo "  large_file_size_gb   - Optional: Size of large file in GB (default: $DEFAULT_LARGE_FILE_SIZE)"
    echo ""
    echo "Examples:"
    echo "  $0 /data/sample_data/dataset1"
    echo "  $0 /data/sample_data/dataset1 20 100 10"
    exit 1
fi

# Parse arguments with defaults
BASE_DIR="$1"
small_file_count="${2:-$DEFAULT_SMALL_FILE_COUNT}"
small_file_size_mb="${3:-$DEFAULT_SMALL_FILE_SIZE}"
large_file_size="${4:-$DEFAULT_LARGE_FILE_SIZE}"

# Validate numeric parameters
if ! [[ "$small_file_count" =~ ^[0-9]+$ ]]; then
    echo "Error: small_file_count must be a positive integer"
    exit 1
fi

# if ! [[ "$small_file_size_mb" =~ ^[0-9]+$ ]]; then
#     echo "Error: small_file_size_mb must be a positive integer"
#     exit 1
# fi

# if ! [[ "$large_file_size" =~ ^[0-9]+$ ]]; then
#     echo "Error: large_file_size_gb must be a positive integer"
#     exit 1
# fi

# Convert MB to bytes for internal use
small_file_size_bytes=$((small_file_size_mb * 1024 * 1024))
# Convert MB to bytes using bc for floating-point arithmetic
small_file_size_bytes=$(echo "$small_file_size_mb * 1024 * 1024" | bc | cut -d. -f1)

echo "Generating sample data with parameters:"
echo "  Output directory: $BASE_DIR"
echo "  Small file count: $small_file_count"
echo "  Small file size: $small_file_size_mb MB ($small_file_size_bytes bytes)"
echo "  Large file size: $large_file_size GB"

# Function to create a large number of small files
create_small_files() {
    local target_dir="$1"
    local count="$2"
    local file_size="$3"

    echo "Creating $count small files of $file_size bytes each..."
    for i in $(seq 1 $count); do
        head -c $file_size /dev/urandom > "${target_dir}/file_${i}"
    done
}

# Function to create a large file
create_large_file() {
    local target_file="$1"
    local file_size_gb="$2"

    echo "Creating large file of $file_size_gb GB..."
    #
    file_size_bytes=$(echo "$file_size_gb * 1024 * 1024 * 1024" | bc | cut -d. -f1)
    head -c $(($file_size_bytes)) /dev/urandom > "$target_file"
}

# Create the base directory
mkdir -p "$BASE_DIR"

# Create a large number of small files
mkdir -p "${BASE_DIR}/small_files"
create_small_files "${BASE_DIR}/small_files" $small_file_count $small_file_size_bytes

# Create nested folders
mkdir -p "${BASE_DIR}/nested/empty_folder"

# Create a large file
create_large_file "${BASE_DIR}/large_file" $large_file_size

echo "Directory structure created in ${BASE_DIR}!"
