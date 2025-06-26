#!/bin/bash

# -----------------------------------------------------------------------------------------
# Generate sample data files with specific sizes in MB for testing purposes
# Accepts a list of file sizes in MB and creates files for each size
# -----------------------------------------------------------------------------------------

# Default file sizes in MB if none provided
DEFAULT_FILE_SIZES="0.5 1 2 5 10 25 50 75 125 173 174 175 200 250 500 1000 1023 1024 1025 1500 2000"

# Check if minimum required argument is provided
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <output_directory> [file_sizes...]"
    echo ""
    echo "Parameters:"
    echo "  output_directory - Required: Directory where sample data will be created"
    echo "  file_sizes...    - Optional: Space-separated list of file sizes in MB"
    echo "                     Default: $DEFAULT_FILE_SIZES"
    echo ""
    echo "Examples:"
    echo "  $0 /data/sample_data/dataset2"
    echo "  $0 /data/sample_data/dataset2 0.5 1 2 5 10 25 50"
    echo "  $0 /data/sample_data/dataset2 100 200 500 1000"
    exit 1
fi

# Parse arguments
BASE_DIR="$1"
shift  # Remove the first argument (base directory)

# Use provided file sizes or default ones
if [ "$#" -gt 0 ]; then
    file_sizes=("$@")
else
    # Convert default string to array
    read -ra file_sizes <<< "$DEFAULT_FILE_SIZES"
fi

# Function to create a file of specific size in MB
create_file_mb() {
    local target_file="$1"
    local file_size_mb="$2"
    
    echo "Creating file: $target_file (${file_size_mb} MB)"
    
    # Convert MB to bytes using bc for floating-point arithmetic
    local bytes=$(echo "$file_size_mb * 1024 * 1024" | bc | cut -d. -f1)
    
    # Validate that we got a valid number
    if ! [[ "$bytes" =~ ^[0-9]+$ ]]; then
        echo "Error: Invalid file size '$file_size_mb' MB - could not convert to bytes"
        return 1
    fi
    
    # Create the file
    head -c "$bytes" /dev/urandom > "$target_file"
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Created: $target_file ($bytes bytes)"
    else
        echo "  ✗ Failed to create: $target_file"
        return 1
    fi
}

# Create the base directory
mkdir -p "$BASE_DIR"

echo "Creating sample data files with specific sizes..."
echo "Output directory: $BASE_DIR"
echo "File sizes: ${file_sizes[*]} MB"
echo ""

# Create files for each specified size
success_count=0
total_count=${#file_sizes[@]}

for size in "${file_sizes[@]}"; do
    # Create filename with size in the name for easy identification
    filename="file_${size}MB"
    # Replace decimal point with underscore for valid filename
    filename=$(echo "$filename" | sed 's/\./_/g')
    
    # Create the file
    if create_file_mb "${BASE_DIR}/${filename}" "$size"; then
        success_count=$((success_count + 1))
    else
        echo "Warning: Failed to create file for size ${size} MB"
    fi
done

echo ""
echo "Sample data files created in ${BASE_DIR}!"
echo "Successfully created $success_count out of $total_count files"

if [ $success_count -eq $total_count ]; then
    echo "✓ All files created successfully"
    exit 0
else
    echo "⚠ Some files failed to create"
    exit 1
fi