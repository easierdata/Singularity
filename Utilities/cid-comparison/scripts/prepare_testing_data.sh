#!/bin/bash

### Shell script to prepare and create a singularity testing environment with sample data
# The following script prepares the testing environment by creating a testing directory with sample data.
#
# 1. Create the root directory for the testing environment at the root of the repository. i.e. `./test-env.
# 2. Create the `sample_data` and `output` directories within the root directory.
# 3. Create subdirectories within `sample_data` based on configuration file dataset collections.
# 4. Generate sample data in each subdirectory using either the `sample_data_gen.sh` or `size_specific_data_gen.sh` script.
# 5. Create corresponding subdirectories within `output` for each dataset collection to store the CAR files.

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

### DEFAULT VARIABLES
# Define the root directory for the testing environment
root_dir="/data"
# Define the sample data directory
sample_data_dir="$root_dir/sample_data"
# Define the output directory for the generated CAR files
output_dir="$root_dir/output"
# Define the configuration file path
config_file="/home/appuser/config/dataset_config.json"

# Check if configuration file exists
if [ ! -f "$config_file" ]; then
    echo "Error: Configuration file not found at $config_file"
    echo "Please ensure the configuration file exists and is properly mounted."
    exit 1
fi

# Validate JSON configuration file
if ! jq empty "$config_file" 2>/dev/null; then
    echo "Error: Invalid JSON in configuration file $config_file"
    exit 1
fi

echo "Preparing testing environment..."
echo "Using configuration file: $config_file"

# Create the root directory for the testing environment
mkdir -p "$root_dir"
echo "Created root directory: $root_dir"

# Create the sample data directory
mkdir -p "$sample_data_dir"
echo "Created sample data directory: $sample_data_dir"

# Create the output directory for the generated CAR files
mkdir -p "$output_dir"
echo "Created output directory: $output_dir"

# Read dataset collections from configuration file
collections=$(jq -r '.datasetCollections[] | @base64' "$config_file")

collection_count=0
for collection_data in $collections; do
    # Decode base64 and extract collection properties
    collection_json=$(echo "$collection_data" | base64 --decode)
    collection_name=$(echo "$collection_json" | jq -r '.name')
    collection_type=$(echo "$collection_json" | jq -r '.type')
    
    collection_count=$((collection_count + 1))
    
    echo "Creating dataset collection: $collection_name (type: $collection_type)"
    
    collection_dir="$sample_data_dir/$collection_name"
    output_collection_dir="$output_dir/$collection_name"
    
    # Create the collection directory
    mkdir -p "$collection_dir"
    echo "  Created collection directory: $collection_dir"
    
    # Create the output collection directory
    mkdir -p "$output_collection_dir"
    echo "  Created output collection directory: $output_collection_dir"
    
    # Generate sample data based on collection type
    echo "  Generating sample data for $collection_name..."
    
    if [ "$collection_type" = "standard" ]; then
        # Extract parameters for standard data generation
        small_file_count=$(echo "$collection_json" | jq -r '.small_file_count')
        small_file_size=$(echo "$collection_json" | jq -r '.small_file_size')
        large_file_size=$(echo "$collection_json" | jq -r '.large_file_size')
        
        # Call sample_data_gen.sh with parameters
        "$SCRIPT_DIR/sample_data_gen.sh" "$collection_dir" "$small_file_count" "$small_file_size" "$large_file_size"
        
    elif [ "$collection_type" = "size_specific" ]; then
        # Check if file_sizes array is provided
        file_sizes_array=$(echo "$collection_json" | jq -r '.file_sizes[]?' 2>/dev/null)
        
        if [ -n "$file_sizes_array" ]; then
            # Convert jq output to bash array
            file_sizes=()
            while IFS= read -r size; do
                file_sizes+=("$size")
            done <<< "$file_sizes_array"
            
            # Call size_specific_data_gen.sh with custom file sizes
            "$SCRIPT_DIR/size_specific_data_gen.sh" "$collection_dir" "${file_sizes[@]}"
        else
            # Call size_specific_data_gen.sh with default sizes (no additional parameters)
            "$SCRIPT_DIR/size_specific_data_gen.sh" "$collection_dir"
        fi
        
    else
        echo "  ✗ Unknown collection type: $collection_type"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Sample data generated successfully for $collection_name"
    else
        echo "  ✗ Failed to generate sample data for $collection_name"
        exit 1
    fi
done

echo "Testing environment preparation completed successfully!"
echo "Processed $collection_count dataset collections"
echo "Sample data location: $sample_data_dir"
echo "Output directory: $output_dir"
