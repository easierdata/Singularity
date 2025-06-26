#!/bin/bash

# This script prepares the generated sample data using Singularity

set -e  # Exit on any error

echo "Starting Singularity content preparation..."
echo "Singularity version: $(singularity v)"

# Check if singularity is available
if ! command -v singularity &> /dev/null; then
    echo "Error: Singularity command not found"
    exit 1
fi

# Operations to perform:
# 1. run the command `singularity admin init` to initialize a SQLite database
echo "Step 1: Initializing Singularity SQLite database..."
singularity admin init
if [ $? -eq 0 ]; then
    echo "✓ Singularity database initialized successfully"
else
    echo "✗ Failed to initialize Singularity database"
    exit 1
fi

# 2. run the command `singularity storage create local --name sample-data-source --path /data/sample_data` to create a storage directory that points to the data directory where the sample data is stored
echo "Step 2: Creating Singularity storage for sample data..."
singularity storage create local --name sample-data-source --path /data/sample_data
if [ $? -eq 0 ]; then
    echo "✓ Storage 'sample-data-source' created successfully"
else
    echo "✗ Failed to create storage 'sample-data-source'"
    exit 1
fi

# 3. run the command `singularity prep create --name sample-data-prep --source sample-data-source`
echo "Step 3: Creating Singularity preparation job..."
singularity prep create --name sample-data-prep --source sample-data-source
if [ $? -eq 0 ]; then
    echo "✓ Preparation job 'sample-data-prep' created successfully"
else
    echo "✗ Failed to create preparation job 'sample-data-prep'"
    exit 1
fi

# 4. run the command `singularity prep start-scan 1 1`
echo "Step 4: Starting scan process..."
singularity prep start-scan 1 1
if [ $? -eq 0 ]; then
    echo "✓ Scan process started successfully"
else
    echo "✗ Failed to start scan process"
    exit 1
fi

# 5. run the command `singularity run dataset-worker --exit-on-error --exit-on-complete`
echo "Step 5: Running dataset worker for scanning..."
singularity run dataset-worker --exit-on-error --exit-on-complete
if [ $? -eq 0 ]; then
    echo "✓ Dataset worker completed scanning successfully"
else
    echo "✗ Dataset worker failed during scanning"
    exit 1
fi

# 6. run the command `singularity prep start-daggen 1 1`
echo "Step 6: Starting DAG generation..."
singularity prep start-daggen 1 1
if [ $? -eq 0 ]; then
    echo "✓ DAG generation started successfully"
else
    echo "✗ Failed to start DAG generation"
    exit 1
fi

# 7. run the command `singularity run dataset-worker --exit-on-error --exit-on-complete`
echo "Step 7: Running dataset worker for DAG generation..."
singularity run dataset-worker --exit-on-error --exit-on-complete
if [ $? -eq 0 ]; then
    echo "✓ Dataset worker completed DAG generation successfully"
else
    echo "✗ Dataset worker failed during DAG generation"
    exit 1
fi

echo "Singularity content preparation completed successfully!"
echo "You can now start the Singularity API server using: singularity run api"

