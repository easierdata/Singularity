param(
    [Parameter(Mandatory = $true)]
    [int]$PreparationId,
    
    [Parameter(Mandatory = $false)]
    [int]$MaxConcurrentDownloads = 0, # Will be set from config if 0
    
    [Parameter(Mandatory = $false)]
    [string]$OutputDirectoryRoot = ".",
    
    [Parameter(Mandatory = $false)]
    [switch]$ForceRedownload = $false,
    
    [Parameter(Mandatory = $false)]
    [switch]$VerifyExisting = $false,
    
    [Parameter(Mandatory = $false)]
    [string]$CurlConfigFile = "",
    
    [Parameter(Mandatory = $false)]
    [string]$ApiHost = "",
    
    [Parameter(Mandatory = $false)]
    [string]$DownloadHost = "",
    
    [Parameter(Mandatory = $false)]
    [string]$ConfigFile = "configs/singularity-config.json"
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to read configuration file
function Read-ConfigFile {
    param([string]$ConfigPath)
    
    if (Test-Path $ConfigPath) {
        Write-Host "Reading configuration from: $ConfigPath" -ForegroundColor Blue
        try {
            $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
            return @{
                Success = $true
                Config  = $config
            }
        }
        catch {
            Write-Warning "Failed to parse JSON config file: $ConfigPath - $_"
            return @{ Success = $false }
        }
    }
    else {
        Write-Verbose "Config file not found: $ConfigPath"
        return @{ Success = $false }
    }
}

# Read configuration file
$configResult = Read-ConfigFile -ConfigPath $ConfigFile
$config = $null
if ($configResult.Success) {
    $config = $configResult.Config
}

# Default hosts (fallback if no config file, env vars, or CLI args)
$defaultApiHost = "http://212.6.53.5:9090"
$defaultDownloadHost = "http://212.6.53.5:7777"

# Determine final hosts using precedence: command line > environment variables > config file > defaults
if ($ApiHost -and $ApiHost -ne "") {
    $finalApiHost = $ApiHost
}
elseif ($env:SINGULARITY_API_HOST) {
    $finalApiHost = $env:SINGULARITY_API_HOST
}
elseif ($config -and $config.endpoints -and $config.endpoints.api_host) {
    $finalApiHost = $config.endpoints.api_host
}
else {
    $finalApiHost = $defaultApiHost
}

if ($DownloadHost -and $DownloadHost -ne "") {
    $finalDownloadHost = $DownloadHost
}
elseif ($env:SINGULARITY_DOWNLOAD_HOST) {
    $finalDownloadHost = $env:SINGULARITY_DOWNLOAD_HOST
}
elseif ($config -and $config.endpoints -and $config.endpoints.download_host) {
    $finalDownloadHost = $config.endpoints.download_host
}
else {
    $finalDownloadHost = $defaultDownloadHost
}

# Check if the API and Download servers are reachable via curl commands. Getting a `HTTP/1.1 404 Not Found` response is acceptable
try {
    $apiCheck = curl --silent --head "$finalApiHost/api/health" | Select-String "HTTP/1.1 200 OK|HTTP/1.1 404 Not Found"
    if (-not $apiCheck) {
        Write-Error "API host is not reachable: $finalApiHost"
        exit 1
    }
    else {
        Write-Host "API host is reachable: $finalApiHost" -ForegroundColor Green
    }

    $downloadCheck = curl --silent --head "$finalDownloadHost/ping" | Select-String "HTTP/1.1 200 OK|HTTP/1.1 404 Not Found"
    if (-not $downloadCheck) {
        Write-Error "Download host is not reachable: $finalDownloadHost"
        exit 1
    }
    else {
        Write-Host "Download host is reachable: $finalDownloadHost" -ForegroundColor Green
    }
}
catch {
    Write-Error "Failed to check API or Download host: $_"
    exit 1
}


# Set MaxConcurrentDownloads from config if not specified
if ($MaxConcurrentDownloads -eq 0) {
    if ($config -and $config.defaults -and $config.defaults.max_concurrent_downloads) {
        $MaxConcurrentDownloads = $config.defaults.max_concurrent_downloads
    }
    else {
        $MaxConcurrentDownloads = 8
    }
}

# Set CurlConfigFile from config if not specified
if ((-not $CurlConfigFile -or $CurlConfigFile -eq "") -and $config -and $config.curl -and $config.curl.config_file) {
    $CurlConfigFile = $config.curl.config_file
}

# Cleanup function to handle script interruption
function Cleanup-Downloads {
    Write-Host "`nCleaning up running downloads..." -ForegroundColor Yellow
    
    # Stop all running jobs
    $jobs = Get-Job -ErrorAction SilentlyContinue
    if ($jobs) {
        Write-Host "Stopping $($jobs.Count) background jobs..." -ForegroundColor Yellow
        $jobs | Stop-Job -ErrorAction SilentlyContinue
        $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
    }
    
    # Kill any remaining curl processes
    $curlProcesses = Get-Process curl -ErrorAction SilentlyContinue
    if ($curlProcesses) {
        Write-Host "Terminating $($curlProcesses.Count) curl processes..." -ForegroundColor Yellow
        $curlProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "Cleanup completed." -ForegroundColor Green
}

# Register cleanup function for Ctrl+C
$null = Register-EngineEvent PowerShell.Exiting -Action { Cleanup-Downloads }

# Configure output directory for downloads to be in the preparation ID subdirectory
$OutputDirectory = Join-Path $OutputDirectoryRoot "preparation-$PreparationId"

# Also handle Ctrl+C explicitly
try {
    # Add this at the beginning of the main script logic, right before the existing code
    Write-Host "Press Ctrl+C to stop downloads and cleanup background jobs" -ForegroundColor Cyan

    Write-Host "Starting download process for preparation ID: $PreparationId" -ForegroundColor Green
    Write-Host "Max concurrent downloads: $MaxConcurrentDownloads" -ForegroundColor Yellow
    Write-Host "Output directory: $OutputDirectory" -ForegroundColor Yellow
    Write-Host "API Host: $finalApiHost" -ForegroundColor Yellow
    Write-Host "Download Host: $finalDownloadHost" -ForegroundColor Yellow
    if ($config) {
        Write-Host "Configuration loaded from: $ConfigFile" -ForegroundColor Blue
    }

    # Validate curl config file if provided
    if ($CurlConfigFile -and $CurlConfigFile -ne "") {
        if (Test-Path $CurlConfigFile) {
            Write-Host "Using curl config file: $CurlConfigFile" -ForegroundColor Yellow
        }
        else {
            Write-Error "Curl config file not found: $CurlConfigFile"
            exit 1
        }
    }

    # Create output directory if it doesn't exist
    if (!(Test-Path $OutputDirectory)) {
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
        Write-Host "Created output directory: $OutputDirectory" -ForegroundColor Blue
    }

    # Step 1: Download the JSON file
    $jsonFileName = "preparation-$PreparationId-piece.json"
    $jsonFilePath = Join-Path $OutputDirectory $jsonFileName
    $apiUrl = "$finalApiHost/api/preparation/$PreparationId/piece"

    Write-Host "Fetching data from: $apiUrl" -ForegroundColor Blue

    try {
        $response = Invoke-RestMethod -Uri $apiUrl -Method Get
        $response | ConvertTo-Json -Depth 10 | Out-File -FilePath $jsonFilePath -Encoding UTF8
        Write-Host "JSON saved to: $jsonFilePath" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to fetch data from API: $_"
        exit 1
    }

    # Step 2: Parse pieces and prepare download jobs
    Write-Host "Parsing JSON response..."
    $jsonContent = Get-Content $jsonFilePath -Raw | ConvertFrom-Json
    
    # Handle array response format
    if ($jsonContent -is [Array] -and $jsonContent.Count -gt 0) {
        $pieces = $jsonContent[0].pieces
    }
    else {
        $pieces = $jsonContent.pieces
    }
    
    if (-not $pieces -or $pieces.Count -eq 0) {
        Write-Host "Warning: No pieces found in the response" -ForegroundColor Yellow
        return
    }
    
    Write-Host "Found $($pieces.Count) pieces to download" -ForegroundColor Green

    # Step 2.5: Check for existing downloads and filter pieces
    Write-Host "Checking for existing downloads..." -ForegroundColor Blue
    
    $existingFiles = @{}
    $skippedCount = 0
    $invalidFiles = @()
    
    if (Test-Path $OutputDirectory) {
        $carFiles = Get-ChildItem -Path $OutputDirectory -Filter "*.car" -File
        foreach ($file in $carFiles) {
            $cidFromFilename = $file.BaseName
            $existingFiles[$cidFromFilename] = $file.FullName
        }
        Write-Host "Found $($carFiles.Count) existing .car files" -ForegroundColor Yellow
    }
    
    # Filter pieces based on existing files and parameters
    $piecesToDownload = @()
    foreach ($piece in $pieces) {
        $pieceCid = $piece.pieceCid
        $outputFile = Join-Path $OutputDirectory "$pieceCid.car"
        
        if ($existingFiles.ContainsKey($pieceCid) -and -not $ForceRedownload) {
            if ($VerifyExisting) {
                # Basic file size check (you could add more verification here)
                $fileInfo = Get-Item $existingFiles[$pieceCid]
                if ($fileInfo.Length -gt 0) {
                    Write-Host "Skipping existing valid file: $pieceCid" -ForegroundColor Gray
                    $skippedCount++
                    continue
                }
                else {
                    Write-Host "Found empty file, will redownload: $pieceCid" -ForegroundColor Yellow
                    $invalidFiles += $pieceCid
                    Remove-Item $existingFiles[$pieceCid] -Force
                }
            }
            else {
                Write-Host "Skipping existing file: $pieceCid" -ForegroundColor Gray
                $skippedCount++
                continue
            }
        }
        
        $piecesToDownload += $piece
    }
    
    if ($skippedCount -gt 0) {
        Write-Host "Skipped $skippedCount existing files" -ForegroundColor Green
    }
    
    if ($invalidFiles.Count -gt 0) {
        Write-Host "Found $($invalidFiles.Count) invalid files that will be redownloaded" -ForegroundColor Yellow
    }
    
    if ($piecesToDownload.Count -eq 0) {
        Write-Host "All pieces already downloaded! Use -ForceRedownload to download again." -ForegroundColor Green
        exit 0
    }
    
    Write-Host "Need to download $($piecesToDownload.Count) pieces" -ForegroundColor Green

    # Create script blocks for concurrent downloads
    $downloadJobs = @()
    $pieceDownloadUrl = "$finalDownloadHost/piece/"

    foreach ($piece in $piecesToDownload) {
        $pieceCid = $piece.pieceCid
        $outputFile = Join-Path $OutputDirectory "$pieceCid.car"
        $downloadUrl = "$pieceDownloadUrl$pieceCid"
    
        $scriptBlock = {
            param($url, $output, $cid)
        
            try {
                Write-Host "Starting download: $cid" -ForegroundColor Cyan
                $startTime = Get-Date
            
                # Use curl for the download - use a temp file for stderr redirection
                $tempErrorFile = [System.IO.Path]::GetTempFileName()
                
                $curlArgs = @(
                    "--silent",
                    "--show-error",
                    "--location",
                    "--fail",
                    $url,
                    "--output",
                    $output
                )
                
                if ($using:CurlConfigFile -and $using:CurlConfigFile -ne "") {
                    $curlArgs += "--config"
                    $curlArgs += $using:CurlConfigFile
                }
            
                try {
                    $process = Start-Process -FilePath "curl" -ArgumentList $curlArgs -Wait -PassThru -NoNewWindow -RedirectStandardError $tempErrorFile
                    
                    if ($process.ExitCode -eq 0) {
                        # Verify the file was created and has content
                        if (Test-Path $output -PathType Leaf) {
                            $fileInfo = Get-Item $output
                            if ($fileInfo.Length -gt 0) {
                                $endTime = Get-Date
                                $duration = $endTime - $startTime
                                Write-Host "Completed download: $cid (took $($duration.TotalSeconds.ToString('F2')) seconds, size: $($fileInfo.Length) bytes)" -ForegroundColor Green
                                return @{ Success = $true; CID = $cid; Duration = $duration; FileSize = $fileInfo.Length }
                            }
                            else {
                                Write-Warning "Downloaded file is empty: $cid"
                                Remove-Item $output -Force -ErrorAction SilentlyContinue
                                return @{ Success = $false; CID = $cid; Error = "Downloaded file is empty" }
                            }
                        }
                        else {
                            Write-Warning "Download file not created: $cid"
                            return @{ Success = $false; CID = $cid; Error = "File not created" }
                        }
                    }
                    else {
                        # Read error details from temp file if it exists
                        $errorDetails = ""
                        if (Test-Path $tempErrorFile) {
                            $errorDetails = Get-Content $tempErrorFile -Raw
                        }
                        Write-Warning "Failed to download: $cid (curl exit code: $($process.ExitCode))"
                        if ($errorDetails) {
                            Write-Warning "Error details: $errorDetails"
                        }
                        # Remove partial file if it exists
                        if (Test-Path $output) {
                            Remove-Item $output -Force -ErrorAction SilentlyContinue
                        }
                        return @{ Success = $false; CID = $cid; Error = "Curl exit code: $($process.ExitCode). $errorDetails" }
                    }
                }
                finally {
                    # Clean up temp error file
                    if (Test-Path $tempErrorFile) {
                        Remove-Item $tempErrorFile -Force -ErrorAction SilentlyContinue
                    }
                }
            }
            catch {
                Write-Warning "Error downloading $cid : $_"
                # Remove partial file if it exists
                if (Test-Path $output) {
                    Remove-Item $output -Force -ErrorAction SilentlyContinue
                }
                return @{ Success = $false; CID = $cid; Error = $_.Exception.Message }
            }
        }
    
        $downloadJobs += @{
            ScriptBlock = $scriptBlock
            Arguments   = @($downloadUrl, $outputFile, $pieceCid)
            CID         = $pieceCid
        }
    }

    # Step 3: Execute downloads with concurrency control
    Write-Host "Starting concurrent downloads..." -ForegroundColor Blue

    $totalJobs = $downloadJobs.Count
    $completedJobs = 0
    $failedJobs = 0
    $runningJobs = @()
    $results = @()

    $startTime = Get-Date

    while ($completedJobs + $failedJobs -lt $totalJobs) {
        # Start new jobs if we have capacity
        while ($runningJobs.Count -lt $MaxConcurrentDownloads -and ($completedJobs + $failedJobs + $runningJobs.Count) -lt $totalJobs) {
            $jobIndex = $completedJobs + $failedJobs + $runningJobs.Count
            $job = $downloadJobs[$jobIndex]
        
            $psJob = Start-Job -ScriptBlock $job.ScriptBlock -ArgumentList $job.Arguments
            $runningJobs += @{
                Job       = $psJob
                CID       = $job.CID
                StartTime = Get-Date
            }
        
            Write-Host "Started job $($jobIndex + 1)/$totalJobs for piece: $($job.CID)" -ForegroundColor Cyan
        }
    
        # Check for completed jobs
        $completedIndices = @()
        for ($i = 0; $i -lt $runningJobs.Count; $i++) {
            $jobInfo = $runningJobs[$i]
            if ($jobInfo.Job.State -eq "Completed" -or $jobInfo.Job.State -eq "Failed") {
                $result = Receive-Job -Job $jobInfo.Job
                Remove-Job -Job $jobInfo.Job
            
                $results += $result
            
                if ($result.Success) {
                    $completedJobs++
                }
                else {
                    $failedJobs++
                }
            
                $completedIndices += $i
            }
        }
    
        # Remove completed jobs from running list (in reverse order to maintain indices)
        for ($i = $completedIndices.Count - 1; $i -ge 0; $i--) {
            $runningJobs = $runningJobs[0..($completedIndices[$i] - 1)] + $runningJobs[($completedIndices[$i] + 1)..($runningJobs.Count - 1)]
        }
    
        # Progress update
        $totalProcessed = $completedJobs + $failedJobs
        if ($totalProcessed -gt 0) {
            $percentComplete = [math]::Round(($totalProcessed / $totalJobs) * 100, 1)
            Write-Progress -Activity "Downloading pieces" -Status "$totalProcessed/$totalJobs completed" -PercentComplete $percentComplete
        }
    
        # Brief pause to prevent excessive CPU usage
        Start-Sleep -Milliseconds 100
    }

    # Wait for any remaining jobs
    while ($runningJobs.Count -gt 0) {
        Start-Sleep -Milliseconds 500
    
        $completedIndices = @()
        for ($i = 0; $i -lt $runningJobs.Count; $i++) {
            $jobInfo = $runningJobs[$i]
            if ($jobInfo.Job.State -eq "Completed" -or $jobInfo.Job.State -eq "Failed") {
                $result = Receive-Job -Job $jobInfo.Job
                Remove-Job -Job $jobInfo.Job
            
                $results += $result
            
                if ($result.Success) {
                    $completedJobs++
                }
                else {
                    $failedJobs++
                }
            
                $completedIndices += $i
            }
        }
    
        for ($i = $completedIndices.Count - 1; $i -ge 0; $i--) {
            $runningJobs = $runningJobs[0..($completedIndices[$i] - 1)] + $runningJobs[($completedIndices[$i] + 1)..($runningJobs.Count - 1)]
        }
    }

    $endTime = Get-Date
    $totalDuration = $endTime - $startTime

    Write-Progress -Activity "Downloading pieces" -Completed

    # Summary
    Write-Host "`n=== Download Summary ===" -ForegroundColor Magenta
    Write-Host "Total pieces: $totalJobs" -ForegroundColor White
    Write-Host "Successful downloads: $completedJobs" -ForegroundColor Green
    Write-Host "Failed downloads: $failedJobs" -ForegroundColor Red
    Write-Host "Total time: $($totalDuration.TotalMinutes.ToString('F2')) minutes" -ForegroundColor Yellow

    if ($failedJobs -gt 0) {
        Write-Host "`nFailed downloads:" -ForegroundColor Red
        $results | Where-Object { -not $_.Success } | ForEach-Object {
            Write-Host "  - $($_.CID): $($_.Error)" -ForegroundColor Red
        }
    }

    Write-Host "`nDownload process completed!" -ForegroundColor Green

}
catch {
    # Handle any interruptions or errors
    Write-Host "`nScript interrupted or encountered an error: $_" -ForegroundColor Red
    Cleanup-Downloads
    exit 1
}
finally {
    # Always cleanup on exit
    Cleanup-Downloads
}