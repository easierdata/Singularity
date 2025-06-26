# CID Comparison Tool

A containerized environment for comparing Content Identifier (CID) generation between Singularity and Kubo CLI (IPFS). Features configurable dataset generation, automated testing workflows, and comprehensive CID analysis with detailed reporting.

## Features

- 🐳 **Containerized Environment**: Pre-configured with Singularity and Kubo CLI
- 📊 **Configuration-Driven**: JSON-based dataset configuration for flexible testing scenarios
- 🚀 **Interactive Menu System**: User-friendly entrypoint with guided workflows
- 📋 **Generate Multiple test collections**: Support for creating fixed or variable file sizes for sample data.
- 🔍 **Comprehensive CID Analysis**: Detailed comparison reports with mismatch detection
- 💾 **Persistent Storage**: Volume mounting for data persistence across container restarts

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the container
docker-compose up -d

# Access the interactive menu
docker-compose exec cid-comparison menu|open-menu|start
```

### Direct Docker Usage

```bash
# Build the container
docker build -t cid-comparison .

# Run with volume mounts
docker run -it --rm \
  -v $(pwd)/data:/data \
  -v $(pwd)/config:/home/appuser/config \
  -p 9090:9090 \
  -p 5001:5001 \
  cid-comparison
```

## Configuration

### Dataset Configuration

Edit `config/dataset_config.json` to customize your testing scenarios:

```json
{
  "datasetCollections": [
    {
      "name": "dataset1",
      "type": "standard",
      "small_file_count": 10,
      "small_file_size": 60,
      "large_file_size": 5
    },
    {
      "name": "dataset2",
      "type": "size_specific",
      "file_sizes": [0.5, 1, 5, 10, 100, 1000]
    }
  ]
}
```

**Collection Types:**

**standard**: Traditional approach with small files (in MB) + one large file (in GB)

- **small_file_count**: Number of small files in the collection
- **small_file_size**: Size of each small file in MB (e.g., 60 = 60MB)
- **large_file_size**: Size of the large file in GB (e.g., 5 = 5GB)

**size_specific**: Custom file sizes for edge case testing

- **file_sizes**: Array of file sizes in MB (e.g., [0.5, 1, 5, 10, 100, 1000])

### Environment Variables

```bash
# Auto-run commands on container start
CID_AUTO_RUN=prepare-data    # Available: prepare-data, setup-singularity, setup-ipfs, compare-cids, full-pipeline

# Logging configuration
GOLOG_LOG_LEVEL=info         # Available: debug, info, warn, error
GOLOG_LOG_FMT=color          # Available: color, json
```

## Usage Workflows

### Interactive Menu System

The container provides an interactive menu with these options:

1. **prepare-data** - Generate sample testing data based on configuration
2. **setup-singularity** - Initialize Singularity and process data
3. **setup-ipfs** - Initialize IPFS datastore and add content
4. **compare-cids** - Extract and compare CIDs between systems
5. **full-pipeline** - Run complete workflow automatically
6. **shell** - Open interactive bash shell
7. **status** - Check system status and available data

### Command Line Usage

You can also run commands directly:

```bash
# Generate sample data
docker-compose exec cid-comparison /home/appuser/entrypoint.sh prepare-data

# Run full comparison pipeline
docker-compose exec cid-comparison /home/appuser/entrypoint.sh full-pipeline

# Check status
docker-compose exec cid-comparison /home/appuser/entrypoint.sh status
```

### Auto-Run Mode

Set environment variable for automatic execution:

```yaml
# docker-compose.yml
environment:
  - CID_AUTO_RUN=full-pipeline
```

## Detailed Workflow

### 1. Data Preparation (`prepare-data`)

Generates sample datasets based on your configuration:

```bash
./scripts/prepare_testing_data.sh
```

**Creates:**

- `/data/sample_data/<collection_name>/` - Sample files per collection
- `/data/output/<collection_name>/` - Output directories for results
- Configurable file sizes and counts per collection

### 2. Singularity Setup (`setup-singularity`)

Initializes Singularity with your sample data:

```bash
./scripts/singularity-prepare-content.sh
```

**Process:**

- Creates SQLite database at `/home/appuser/singularity.db`
- Configures storage pointing to sample data
- Creates preparation jobs for each dataset
- Scans content and generates DAGs

### 3. IPFS Setup (`setup-ipfs`)

Initializes IPFS and adds content:

```bash
./scripts/ipfs-prepare-content.sh
```

**Process:**

- Initializes IPFS with [test-cid-v1-wide profile](https://github.com/ipfs/kubo/blob/master/docs/config.md#test-cid-v1-wide-profile)
- Adds all sample data to IPFS datastore.
  > Files are not added to the the local datastore as we pass in the `--only-hash` parameter.
- Saves resulting CIDs for each file to `/data/comparison_output/ipfs_cids.json`

### 4. CID Comparison (`compare-cids`)

Analyzes CID differences between systems:

```bash
./scripts/compare-cids.sh
```

**Analysis:**

- Extracts CIDs from both systems
- Matches files by path and compares CIDs
- Identifies mismatches and generates reports
- Provides statistics and recommendations

## Output Structure

```
/data/
├── sample_data/           # Generated test datasets
│   ├── dataset1/         # Standard collection
│   ├── dataset2/         # Size-specific collection
│   └── dataset3/         # Additional collections...
├── output/               # Processing outputs
│   ├── dataset1/         # Singularity CAR files
│   └── dataset2/
├── comparison_output/    # Comparison results
│   ├── ipfs_cids.json           # IPFS CID mappings
│   ├── singularity_cids.json    # Singularity CID mappings
│   └── comparison_report.txt    # Detailed analysis report
└── singularity.db       # Singularity database
```

## Volume Mounts

- **`/data`**: Persistent storage for datasets, outputs, and databases
- **`/home/appuser/config`**: Configuration files (dataset_config.json)

## Troubleshooting

### Common Issues

**Configuration not loading:**

```bash
# Verify config file exists and is valid JSON
docker-compose exec cid-comparison cat /home/appuser/config/dataset_config.json
docker-compose exec cid-comparison jq . /home/appuser/config/dataset_config.json
```

**Permission issues:**

```bash
# Fix ownership on host
sudo chown -R $USER:$USER ./data ./config
```

### Debugging

**Enable debug logging:**

```yaml
# docker-compose.yml
environment:
  - GOLOG_LOG_LEVEL=debug
```

**Access container logs:**

```bash
docker-compose logs -f cid-comparison
```

**Interactive debugging:**

```bash
docker-compose exec cid-comparison /home/appuser/entrypoint.sh shell
```

## Development

### Adding New Dataset Collections

1. Edit `config/dataset_config.json`
2. Add new collection with desired parameters
3. Restart container: `docker-compose restart`

### Custom Scripts

1. Add scripts to `scripts/` directory
2. Make executable: `chmod +x scripts/your-script.sh`
3. Rebuild container: `docker-compose build`

## License

This project is provided as-is for research and comparison purposes.
