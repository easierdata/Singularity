<#
.SYNOPSIS
    Calculates the total size of active deals for a specific provider up to a cutoff epoch/date.

.DESCRIPTION
    This script automates the invoice checking process by:
    1. Fetching all deal data from the Singularity API.
    2. Filtering by Provider ID and Deal State (default: active).
    3. Filtering deals that started BEFORE a specific Cutoff Date or Epoch.
    4. Summing the PieceSize of matching deals.
    5. converting the bytes to TiB (2^40) and rounding to 3 decimal places.

    It replaces the manual workflow of CLI export -> CSV -> Spreadsheet formulas.

.PARAMETER ProviderID
    The ID of the storage provider to filter by (e.g., "f02639429").

.PARAMETER CutoffDate
    The date (YYYY-MM-DD) to use as the cutoff. Deals starting on or after this date are excluded.
    Example: "2026-01-01" will include deals up to 2025-12-31 23:59:59.

.PARAMETER CutoffEpoch
    (Optional) Manually specify the Filecoin epoch. If provided, overrides CutoffDate.

.PARAMETER State
    The state of the deals to verify. Default is "active".

.EXAMPLE
    .\get_deal_size.ps1 -ProviderID "f02639429" -CutoffDate "2026-01-01"
    
    Fetch deals for provider f02639429 valid before Jan 1st, 2026.

.EXAMPLE
    .\get_deal_size.ps1 -ProviderID "f02639429" -CutoffEpoch 5630640
    
    Fetch deals using a specific epoch number.
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$ProviderID,

    [Parameter(Mandatory=$false)]
    [string]$CutoffDate,

    [Parameter(Mandatory=$false)]
    [long]$CutoffEpoch,

    [Parameter(Mandatory=$false)]
    [string]$State = "active",

    [Parameter(Mandatory=$false)]
    [string]$ClientID
)

# Constants
$FilecoinGenesis = [DateTime]::Parse("2020-08-24T22:00:00Z").ToUniversalTime()
$SecondsPerEpoch = 30
$TiB = [Math]::Pow(2, 40)

# Helper: Convert Date to Epoch
function Get-EpochFromDate {
    param([DateTime]$TargetDate)
    $TargetUtc = $TargetDate.ToUniversalTime()
    $DiffSeconds = ($TargetUtc - $FilecoinGenesis).TotalSeconds
    return [Math]::Floor($DiffSeconds / $SecondsPerEpoch)
}

# Determine Target Epoch
if ($CutoffEpoch -gt 0) {
    $TargetEpoch = $CutoffEpoch
    $FilterDescription = "Epoch < $TargetEpoch"
}
elseif (-not [string]::IsNullOrWhiteSpace($CutoffDate)) {
    try {
        # Parse as UTC (AssumeUniversal) to ensure we match Filecoin/Blockchain epochs which are always UTC
        $DateObj = [DateTime]::Parse($CutoffDate, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal)
        $TargetEpoch = Get-EpochFromDate -TargetDate $DateObj
        $FilterDescription = "Date < $($DateObj.ToString("yyyy-MM-dd")) UTC (Epoch $TargetEpoch)"
    }
    catch {
        Write-Error "Invalid Date Format: $CutoffDate. Please use YYYY-MM-DD."
        exit 1
    }
}
else {
    # Default to Now (UTC) if no parameters provided
    $DateObj = [DateTime]::UtcNow
    $TargetEpoch = Get-EpochFromDate -TargetDate $DateObj
    $FilterDescription = "Date < Now ($($DateObj.ToString("yyyy-MM-dd HH:mm:ss")) UTC) (Epoch $TargetEpoch)"
}

Write-Host "Fetching deal data from Singularity API..." -ForegroundColor Cyan

try {
    # 1. Fetch Data
    # Using POST as discovered in testing
    $Response = Invoke-RestMethod -Method Post -Uri "http://212.6.53.5:9090/api/deal" -ErrorAction Stop
}
catch {
    Write-Error "Failed to fetch data from API: $_"
    exit 1
}

if (-not $Response) {
    Write-Warning "No data returned from API."
    exit
}

# Build filter description
$DisplayClient = if (-not [string]::IsNullOrWhiteSpace($ClientID)) { " | Client: $ClientID" } else { "" }
Write-Host "Filtering deals for Provider: $ProviderID | State: $State$DisplayClient | $FilterDescription" -ForegroundColor Cyan

# 2. Filter Data
$FilteredDeals = $Response | Where-Object { 
    $_.provider -eq $ProviderID -and 
    $_.state -eq $State -and 
    $_.startEpoch -lt $TargetEpoch -and
    ([string]::IsNullOrWhiteSpace($ClientID) -or $_.clientId -eq $ClientID)
}

$Count = ($FilteredDeals | Measure-Object).Count
Write-Host "Found $Count matching deals." -ForegroundColor Green

if ($Count -eq 0) {
    Write-Host "Total Size: 0 TiB"
    return
}

# 3. Calculate Sum
# Ensure we treat pieceSize as Int64/long to avoid overflow if it were 32-bit (though PowerShell handles usually)
$TotalBytes = ($FilteredDeals | Measure-Object -Property pieceSize -Sum).Sum

# 4. Conversion and Formatting
# Formula: ROUND(SUM / 2^40, 3)
$TotalTiB = [Math]::Round($TotalBytes / $TiB, 3)

# Calculate Date from Epoch for display
$EpochDate = $FilecoinGenesis.AddSeconds($TargetEpoch * $SecondsPerEpoch)
$EpochDateString = $EpochDate.ToString("yyyy-MM-dd HH:mm:ss") + " UTC"

Write-Host "`n--------------------------------------------------"
Write-Host "Snapshot Report"
Write-Host "--------------------------------------------------"
Write-Host "Provider    : $ProviderID"
if (-not [string]::IsNullOrWhiteSpace($ClientID)) {
    Write-Host "Client      : $ClientID"
}
Write-Host "Cutoff Epoch: $TargetEpoch ($EpochDateString)"
Write-Host "Deal Count  : $Count"
Write-Host "Total Size  : $TotalTiB TiB" -ForegroundColor Yellow
Write-Host "--------------------------------------------------`n"
