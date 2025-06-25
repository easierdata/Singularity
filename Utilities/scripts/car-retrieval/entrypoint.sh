#!/bin/bash
set -e

# Function to copy default configs if /app/configs is empty
populate_configs() {
    echo "Checking /app/configs directory..."
    
    # Check if /app/configs is empty or doesn't contain our config files
    if [ ! -f "/app/configs/singularity-config.json" ] || [ ! -f "/app/configs/curl-config.txt" ]; then
        echo "Populating /app/configs with default configuration files..."
        
        # Ensure the directory exists and has proper permissions
        mkdir -p /app/configs
        
        # Copy default configs if they exist
        if [ -d "/app/.default_configs" ]; then
            cp -r /app/.default_configs/* /app/configs/ 2>/dev/null || true
            echo "Default configuration files copied to /app/configs/"
        else
            echo "Warning: Default configs directory /app/.default_configs not found"
        fi
        
        # List what was copied
        echo "Configuration files available:"
        ls -la /app/configs/ 2>/dev/null || echo "No files found in /app/configs/"
    else
        echo "/app/configs already contains configuration files. Skipping population."
    fi
}

# Call the function to populate configs
populate_configs

# If no arguments are provided, show usage and keep container running
if [ $# -eq 0 ]; then
    echo "Singularity Piece Downloader Container"
    echo "Usage: docker run --rm -v \$(pwd)/downloads:/downloads -v \$(pwd)/configs:/app/configs singularity-downloader ./download-pieces.sh <preparation_id> [options]"
    echo "Example: docker run --rm -v \$(pwd)/downloads:/downloads -v \$(pwd)/configs:/app/configs singularity-downloader ./download-pieces.sh 1 8 /downloads"
    echo ""
    echo "Configuration files are available in /app/configs/"
    echo "Available scripts: download-pieces.sh, monitor-downloads.sh, debug-concurrency.sh"
    echo ""
    echo "Container is ready. Use 'docker exec -it <container_name> bash' to access the shell."
    
    # Keep the container running with a background process
    # This creates a long-running process that keeps the container alive
    tail -f /dev/null
else
    # Execute the provided command
    exec "$@"
fi