# Singularity Piece Downloader

This directory contains scripts and tools for downloading CAR (Content Addressable aRchive) files from a [Singularity](https://data-programs.gitbook.io/singularity) preparation. The scripts support concurrent downloads with basic error handling and monitoring capabilities.

## Overview

Singularity enables the distribution of CAR (Content Addressable Archive) files utilizing the built-in [Download Server](https://data-programs.gitbook.io/singularity/content-distribution/distribute-car-files#singularity-download-server). Behind the scenes, a user requests a particular **Piece** by the `PieceCid` and the server responds by either:

1. Streaming the already prepared CAR file.
2. Assemble the CAR file on the fly from the source data.

In either case, the resulting download is a CAR file, representing the prepared source data in content-addressable form.

This toolset allows you to:

- Download pieces from a specific preparation ID
- Run multiple concurrent downloads for faster completion
- Monitor download progress in real-time with file size tracking
- Configure custom API and download endpoints
- Run in persistent Docker containers for long-running downloads

The updated Docker setup provides several advantages:

## Configuration Options

The scripts support multiple ways to configure the Singularity API and download endpoints:

- **[Configuration File](#1-configuration-file-recommended-for-persistent-setups)**
- **[Environment Variables](#2-environment-variables-good-for-dockerci-environments)**
- **[Command Line Parameters](#3-command-line-parameters-for-one-time-usage)**
- **[Default Values](#4-default-values-fallback)**

**Configuration setting priority call order:** Command Line Parameters > Environment Variables > Configuration File > Default Values

### 1. Configuration File (Recommended for persistent setups)

The provided Shell and PowerShell scripts will automatically reference the configuration file [./configs/singularity-config.json](./configs/singularity-config.json) if no command line parameters are provided. This allows for easy customization of API endpoints, download hosts, and other settings without requiring direct modification of the scripts.

The Docker container automatically includes default configuration files in the `configs/` directory. When you mount a volume to `/app/configs`, the container's entrypoint script will populate it with default configurations if it's empty.

Create or modify `configs/singularity-config.json`:

```json
{
  "endpoints": {
    "api_host": "http://your-api-server:9090",
    "download_host": "http://your-download-server:7777"
  },
  "defaults": {
    "max_concurrent_downloads": 32,
    "verify_existing": false,
    "force_redownload": false
  },
  "curl": {
    "config_file": "./configs/curl-config.txt",
    "timeout": 300,
    "retry_attempts": 3
  },
  "description": "Singularity download configuration file. Modify endpoints and defaults as needed."
}
```

> **Note**: The `curl-config.txt` file can be used to specify additional curl options for advanced users. This allows you to customize the curl behavior without modifying the main scripts. For example, you can set timeouts, retries, or other curl options.

### 2. Environment Variables (Good for Docker/CI environments)

You can also set the environment variables `SINGULARITY_API_HOST` and `SINGULARITY_DOWNLOAD_HOST` to override the default API and download endpoints.

```bash
# Set environment variables (Linux/WSL)
export SINGULARITY_API_HOST="http://your-api-server:9090"
export SINGULARITY_DOWNLOAD_HOST="http://your-download-server:7777"

# Set environment variables (Windows PowerShell)
$env:SINGULARITY_API_HOST="http://your-api-server:9090"
$env:SINGULARITY_DOWNLOAD_HOST="http://your-download-server:7777"
```

### 3. Command Line Parameters (For one-time usage)

You can also specify the API and download hosts directly in the command line when running the scripts.

```bash
# Bash
./download-pieces.sh 1 32 ./downloads --api-host "http://custom-api:9090" --download-host "http://custom-download:7777"

# PowerShell
.\download-pieces.ps1 -PreparationId 1 -ApiHost "http://custom-api:9090" -DownloadHost "http://custom-download:7777"
```

### 4. Default Values (Fallback)

If no configuration file, environment variables, or command line parameters are provided, the scripts use these defaults:

- **API Host:** `http://localhost:9090`
- **Download Host:** `http://localhost:7777`

**Priority Order:** Command Line Parameters > Environment Variables > Configuration File > Default Values

## Files Description

### Main Scripts

- **`download-pieces.sh`** - Main bash script for Linux/Docker environments
- **`download-pieces.ps1`** - PowerShell script for Windows environments
- **`monitor-downloads.sh`** - Real-time monitoring script with file size tracking (Linux/WSL)

### Docker Support

- **`Dockerfile`** - Container definition with all dependencies and entrypoint script
- **`docker-compose.yml`** - Easy deployment configuration for persistent containers
- **`entrypoint.sh`** - Container initialization script that populates configuration files

### Configuration & Debugging

- **`configs/singularity-config.json`** - Main configuration file for endpoints and defaults
- **`configs/curl-config.txt`** - Curl configuration for advanced options
- **`tests/debug-concurrency.sh`** - Test script to verify concurrent downloads work

## Quick Start

### Option 1: Using Docker (Recommended)

The Docker container now runs persistently and automatically sets up configuration files:

```bash
# Build and start the persistent container
docker-compose up -d

# Check container status
docker-compose ps

# Access the running container for downloads
docker exec -it singularity-downloader bash

# Inside the container, run downloads
./download-pieces.sh 1 32 /downloads

# Monitor progress in another terminal
docker exec -it singularity-downloader ./monitor-downloads.sh
```

#### Docker with Custom Configuration

```bash
# Method 1: Use environment variables
docker exec -it singularity-downloader sh -c 'export SINGULARITY_API_HOST="http://custom-api:9090" && export SINGULARITY_DOWNLOAD_HOST="http://custom-download:7777" && ./download-pieces.sh 1 32 /downloads'

# Method 2: Use command line parameters
docker exec -it singularity-downloader ./download-pieces.sh 1 32 /downloads --api-host "http://custom-api:9090" --download-host "http://custom-download:7777"

# Method 3: Modify the config file on the host, and it will be reflected in the container
# Edit ./configs/singularity-config.json on your host machine
# Then run downloads normally in the container
docker exec -it singularity-downloader ./download-pieces.sh 1
```

Additionally, you can modify the `docker-compose.yml` file to set environment variables and a custom command to run when the container starts:

```yaml
services:
  singularity-downloader:
      command: ["./download-pieces.sh", "1", "8", "/downloads"]
      ...
```

The above command will run the download script with preparation ID 1, 8 concurrent downloads, and store files in the `/downloads` directory inside the container.

#### Docker Container Management

```bash
# Stop the container
docker-compose down

# View container logs
docker-compose logs singularity-downloader

# Restart the container
docker-compose up -d

# Access the container shell
docker exec -it singularity-downloader bash
```

### Option 2: Direct Script Usage

#### Linux/WSL (Bash)

```bash
# Make scripts executable
chmod +x download-pieces.sh monitor-downloads.sh

# Download with default endpoints
./download-pieces.sh 1 32 ./downloads

# Download with custom endpoints
./download-pieces.sh 1 32 ./downloads --api-host "http://your-api:9090" --download-host "http://your-download:7777"

# Monitor in another terminal
./monitor-downloads.sh ./downloads/logs
```

#### Windows (PowerShell)

```powershell
# Download with default endpoints
.\download-pieces.ps1 -PreparationId 1 -MaxConcurrentDownloads 32

# Download with custom endpoints
.\download-pieces.ps1 -PreparationId 1 -MaxConcurrentDownloads 32 -ApiHost "http://your-api:9090" -DownloadHost "http://your-download:7777"

# Use built-in progress monitoring (automatic)
```

## Script Parameters

### Bash Script (`download-pieces.sh`)

```bash
./download-pieces.sh <preparation_id> [max_concurrent] [output_directory] [options]
```

**Parameters:**

- `preparation_id` (required) - The Singularity preparation ID to download
- `max_concurrent` (optional, default: 8) - Number of concurrent downloads
- `output_directory` (optional, default: current dir) - Root directory for downloads

**Options:**

- `--force-redownload` - Re-download existing files
- `--verify-existing` - Check existing files and re-download if empty
- `--curl-config <file>` - Use custom curl configuration
- `--api-host <host>` - Override API endpoint (e.g., "<http://api-server:9090>")
- `--download-host <host>` - Override download endpoint (e.g., "<http://download-server:7777>")

### PowerShell Script (`download-pieces.ps1`)

```powershell
.\download-pieces.ps1 -PreparationId <id> [parameters]
```

**Parameters:**

- `-PreparationId` (required) - The Singularity preparation ID
- `-MaxConcurrentDownloads` (optional, default: 8) - Concurrent download limit
- `-OutputDirectoryRoot` (optional, default: current dir) - Root output directory
- `-ForceRedownload` (switch) - Re-download existing files
- `-VerifyExisting` (switch) - Verify and re-download empty files
- `-CurlConfigFile` (optional) - Path to curl configuration file
- `-ApiHost` (optional) - Override API endpoint (e.g., "<http://api-server:9090>")
- `-DownloadHost` (optional) - Override download endpoint (e.g., "<http://download-server:7777>")

## Directory Structure

When you run the scripts, they create the following structure by default:

```text
output_directory/
├── logs/                           # Download logs and status files
│   ├── piece_cid.log              # Individual download logs
│   ├── piece_cid.result           # Success/failure status
│   └── stop_downloads             # Signal file for graceful stop
└── preparation-{id}/              # Files for specific preparation
    ├── preparation-{id}-piece.json # API response metadata
    └── piece_cid.car              # Downloaded CAR files
```

## Examples

Below are some examples of how to use the scripts effectively, including both basic and advanced usage scenarios.

### Basic Usage

```bash
# Download preparation 1 with default settings
./download-pieces.sh 1

# Download with 16 concurrent downloads to a specific directory
./download-pieces.sh 1 16 /mnt/storage/singularity
```

### Advanced Usage

```bash
# Force re-download with custom curl config
./download-pieces.sh 1 32 ./downloads --force-redownload --curl-config curl-config.txt

# Verify existing files and only re-download corrupted ones
./download-pieces.sh 1 32 ./downloads --verify-existing

# Use custom endpoints
./download-pieces.sh 1 32 ./downloads --api-host "http://staging-api:9090" --download-host "http://staging-download:7777"
```

### PowerShell Examples

```powershell
# Basic download
.\download-pieces.ps1 -PreparationId 1

# Advanced download with verification and custom endpoints
.\download-pieces.ps1 -PreparationId 1 -MaxConcurrentDownloads 16 -VerifyExisting -CurlConfigFile "curl-config.txt" -ApiHost "http://staging-api:9090" -DownloadHost "http://staging-download:7777"
```

### Environment Variable Examples

```bash
# Linux/WSL - Set for current session
export SINGULARITY_API_HOST="http://production-api:9090"
export SINGULARITY_DOWNLOAD_HOST="http://production-download:7777"
./download-pieces.sh 1 32 ./downloads

# Linux/WSL - Set permanently (add to ~/.bashrc)
echo 'export SINGULARITY_API_HOST="http://production-api:9090"' >> ~/.bashrc
echo 'export SINGULARITY_DOWNLOAD_HOST="http://production-download:7777"' >> ~/.bashrc
```

```powershell
# PowerShell - Set for current session
$env:SINGULARITY_API_HOST="http://production-api:9090"
$env:SINGULARITY_DOWNLOAD_HOST="http://production-download:7777"
.\download-pieces.ps1 -PreparationId 1

# PowerShell - Set permanently (requires admin)
[Environment]::SetEnvironmentVariable("SINGULARITY_API_HOST", "http://production-api:9090", "Machine")
[Environment]::SetEnvironmentVariable("SINGULARITY_DOWNLOAD_HOST", "http://production-download:7777", "Machine")
```

## Monitoring Downloads

### Real-time Monitoring with File Size Tracking

The monitoring script now shows detailed information about active downloads, including file sizes:

```bash
# Monitor active downloads
./monitor-downloads.sh /path/to/logs

# In Docker (recommended)
docker exec -it singularity-downloader ./monitor-downloads.sh
```

The enhanced monitor displays:

- **Active curl processes count**
- **Completed/successful/failed download counts**
- **Recent download activity**
- **Active download file sizes** - Shows current size of each downloading piece
- **Total active download size** - Combined size of all actively downloading files
- **Human-readable format** - Automatically converts bytes to KB/MB/GB

**Example Monitor Output:**

```
=== Download Monitor - Tue Jun 24 18:58:43 UTC 2025 ===

Active curl processes: 4
Completed downloads: 156
  - Successful: 154
  - Failed: 2

Recent activity:
  baga6ea4seaqdjmxotuv36ybe724tmkz5rclwovw64d6d7ok2kglvod66oswmmny: SUCCESS: Downloaded successfully
  baga6ea4seaqal7snly3lypfiojun2y7xvx245enlb5wwdlctyfvzwhhocdpbcca: SUCCESS: Downloaded successfully

Active download file sizes:
  baga6ea4seaqk3d2ntweri5ohw2opwexm7q67rndewt7e5ohjjgnp6j74j7wh6ey: 2.66 GB
  baga6ea4seaqo5xhmivsfqh634qyogytmtbxhidftrpcoqka2dt5nbc74h4qpanq: 10.74 GB
  baga6ea4seaqoq7yqcv6wiwzjuld5q57mfjpfe2bchxjfpiodtcbbtmfz6g3uqlq: 1.37 GB
  baga6ea4seaqafhc3cdnrcsq22pvpbf5ps6pq2os2slyo5eyk52ganxrjeuonckq: 15.23 GB
  TOTAL: 4 files, 30.00 GB

Log files (should show concurrent downloads):
  Total log files: 160
```

### Manual Monitoring (Linux/WSL)

```bash
# Check active downloads
ps aux | grep curl

# Count log files (should equal concurrent downloads initially)
ls -1 logs/*.log | wc -l

# Check completed downloads
ls -1 logs/*.result | wc -l
```

## Stopping Downloads

### Graceful Stop (Bash)

Press `Ctrl+C` in the terminal running the script. It will:

1. Stop starting new downloads
2. Wait for current downloads to complete
3. Show final summary

### Force Stop (Docker)

```bash
# Stop the container
docker-compose down

# Or kill all downloads
docker exec -it singularity-downloader pkill curl
```

## Troubleshooting

### Docker-Specific Issues

**Container exits immediately**

- The container now stays running persistently
- Use `docker-compose ps` to check status
- Use `docker-compose logs singularity-downloader` to view logs

**Configuration files not appearing in the container**

- Ensure you're using the volume mount: `./configs:/app/configs`
- The `entrypoint` script automatically populates empty volumes
- Check with: `docker exec -it singularity-downloader ls -la /app/configs/`

**Volume mount issues on Windows**

- The `entrypoint` script handles volume mounting issues
- Configuration files are copied from built-in defaults if volumes are empty
- Rebuild container if needed: `docker-compose build --no-cache`

### Downloads Appear Sequential

If downloads seem to run one at a time:

1. **Check log files count:**

   ```bash
   ls -1 logs/*.log | wc -l
   ```

   Should equal your concurrent setting initially.

2. **Monitor active processes:**

   ```bash
   watch 'ps aux | grep curl | grep -v grep'
   ```

3. **Test concurrency:**

   ```bash
   ./tests/debug-concurrency.sh 4 8
   ```

### Common Issues

**"No pieces found"**

By default, the [Singularity API server](https://data-programs.gitbook.io/singularity/cli-reference/run/api/) runs on port 9090. If you encounter any errors, check the following:

- Verify network connectivity to the API endpoint
- Ensure the correct API host is configured
- Check if the preparation ID exists

**Downloads fail with connection errors**

By default, the [Singularity download server](https://data-programs.gitbook.io/singularity/cli-reference/run/download-server) runs on port 7777. If you encounter connection errors, try the following:

- Confirm the download host is accessible
- Verify network stability
- Reduce concurrent downloads (try 8-16 instead of 32)
- Check curl-config.txt for timeout settings

**Out of disk space**

- Each piece is ~33GB, plan accordingly
- Monitor disk usage: `df -h`

**Container networking issues**

- Try using host networking in docker-compose.yml
- Check firewall settings

**Custom endpoint not working**

- Verify the host URLs are correct and accessible
- Check that the endpoints support the expected API format
- Use `curl` manually to test connectivity: `curl http://your-api:9090/api/preparation/1/piece`

## Performance Tips

### Filtering pieces in the JSON files (Linux/WSL)

If you would like to filter out a subset of the preparation pieces from the generated JSON files, you can use the `jq` command-line tool. For example, to extract the last x `pieces` from the `preparation-1-piece.json`, you can run:

```bash
jq '.[0].pieces |= .[-x:]' ./preparation-1-piece.json > filtered-pieces.json
```

This command will take the last `x` pieces from the JSON file, while maintaining the existing structure, and save them to `filtered-pieces.json`. You can then use this filtered file for downloading only the specified pieces.

---

If you would like to filter out CAR files that have already been downloaded, you can use the following command to create a new JSON file that only contains pieces that do not have a corresponding `.car` file in the output directory:

```bash
jq --arg download_dir "preparation-2" '
.[0].pieces |= map(select(
  .pieceCid as $cid |
  ($download_dir + "/" + $cid + ".car" | test(".*\\.car$")) and
  ($download_dir + "/" + $cid + ".car" | test("^" + $download_dir + "/.*\\.car$"))
))' preparation-2/preparation-2-piece.json > filtered-pieces.json
```

### Docker Optimization

- **Use persistent containers** instead of restarting for each download
- **Monitor with the enhanced monitoring script** to track active file sizes
- **Adjust concurrent downloads** based on container resource limits
- **Use volume mounts** for persistent storage across container restarts

### File Size Monitoring

- **Track active download progress** with the monitoring script
- **Plan bandwidth usage** by monitoring the total active download size
- **Identify slow downloads** by comparing file sizes over time

### Optimal Concurrency

- Start with 8-16 concurrent downloads
- Monitor network utilization
- Increase gradually if the network can handle it
- Each piece is ~33GB, so bandwidth is usually the bottleneck

### Network Optimization

- Use `curl-config.txt` for custom settings
- Consider bandwidth limiting if needed
- Ensure a stable internet connection

### Storage Considerations

- Use fast storage (SSD preferred)
- Ensure sufficient free space (280+ pieces × 33GB each)
- Consider using external storage for large downloads

## API Endpoints

The scripts connect to (configurable):

- **List all prepared pieces for a preparation:** `{API_HOST}/api/preparation/{id}/piece` (default: `http://localhost:9090`)
- **Get metadata for a piece:** `{API_HOST}/api/preparation/{id}/piece` (default: `http://localhost:9090`)
- **Download Piece URL:** `http://{DOWNLOAD_HOST}/piece/{piece_cid}` (default: `http://localhost:7777`)

## Dependencies

### Docker Environment (Recommended)

- Docker Engine
- Docker Compose
- All dependencies are included in the container image

### Native Environment

- curl (for downloads)
- jq (for JSON parsing)
- bash 4+ (for associative arrays)
- stat command (for file size monitoring)

## Container Features

### Entrypoint Script Benefits

- **Automatic configuration setup** when container starts
- **Volume-aware initialization** populates empty config volumes
- **Persistent operation** keeps the container running for interactive use
- **Graceful command handling** supports both interactive and scripted usage

### Volume Management

- **Configs volume**: `./configs:/app/configs` - Live configuration editing
- **Downloads volume**: `./downloads:/downloads` - Persistent download storage
- **Auto-population**: Empty volumes are automatically populated with defaults

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Run the debug concurrency test
3. Review log files in the `logs/` directory
4. Monitor system resources during downloads
5. Verify endpoint connectivity if using custom hosts

## File Format

The downloaded files are in CAR (Content Addressable aRchive) format, which is a standard format for storing IPLD data. Each file contains piece data that can be used with IPFS/Filecoin networks. If you would like to extract content from the CAR files, you can use tools like [go-car](https://github.com/ipld/go-car).
