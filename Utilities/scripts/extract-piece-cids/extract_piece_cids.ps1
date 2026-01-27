<#
.SYNOPSIS
    Extracts pieceCIDs for a specific preparation and joins with deal metadata.

.DESCRIPTION
    This script fetches preparation pieces and deal metadata from the Singularity API
    and joins them into a CSV file.

.PARAMETER PreparationID
    The ID of the preparation to query.

.PARAMETER ProviderID
    (Optional) Filter by Storage Provider ID.

.PARAMETER ClientID
    (Optional) Filter by Client ID.

.PARAMETER ApiEndpoint
    The Singularity API endpoint (Default: http://212.6.53.5:9090).

.PARAMETER DealState
    Filter by deal state (Default: active).

.PARAMETER Identify
    List available IDs and Names, then exit.

.PARAMETER OutputFile
    (Optional) Specify output CSV filename.

.EXAMPLE
    .\extract_piece_cids.ps1 -PreparationID 1
#>

param (
    [Parameter(Mandatory=$false)]
    [Alias("prep-id")]
    [int]$PreparationID,

    [Parameter(Mandatory=$false)]
    [Alias("provider")]
    [string]$ProviderID,

    [Parameter(Mandatory=$false)]
    [Alias("client")]
    [string]$ClientID,

    [Parameter(Mandatory=$false)]
    [Alias("api")]
    [string]$ApiEndpoint = "http://212.6.53.5:9090",

    [Parameter(Mandatory=$false)]
    [Alias("state")]
    [string]$DealState = "active",

    [Parameter(Mandatory=$false)]
    [Alias("i")]
    [switch]$Identify,

    [Parameter(Mandatory=$false)]
    [Alias("h")]
    [switch]$Help,

    [Parameter(Mandatory=$false)]
    [string]$OutputFile
)

if ($Help) {
    Get-Help $PSCommandPath
    return
}

# Normalize API Endpoint
$ApiEndpoint = $ApiEndpoint.TrimEnd('/')

if ($Identify) {
    Write-Host "Fetching available IDs and Names..." -ForegroundColor Cyan
    
    try {
        $Preps = Invoke-RestMethod -Method Get -Uri "$ApiEndpoint/api/preparation" -ErrorAction Stop
        $Deals = Invoke-RestMethod -Method Post -Uri "$ApiEndpoint/api/deal" -ErrorAction Stop

        Write-Host "`nAvailable Preparations:" -ForegroundColor White -FontWeight Bold
        $Preps | Select-Object id, name | Format-Table -AutoSize

        Write-Host "`nAvailable Monitoring Entities (from deals):" -ForegroundColor White -FontWeight Bold
        $ClientIds = $Deals.clientId | Select-Object -Unique | Sort-Object
        $ProviderIds = $Deals.provider | Select-Object -Unique | Sort-Object

        Write-Host "Client IDs:"
        $ClientIds | ForEach-Object { Write-Host "  - $_" }

        Write-Host "`nStorage Provider IDs:"
        $ProviderIds | ForEach-Object { Write-Host "  - $_" }
    }
    catch {
        Write-Error "Failed to fetch data from API: $_"
    }
    return
}

if (-not $PreparationID) {
    Write-Error "PreparationID is required unless using -Identify."
    return
}

Write-Host "Fetching piece and deal data for Preparation $PreparationID..." -ForegroundColor Cyan

try {
    # 1. Fetch data
    $PieceResponse = Invoke-RestMethod -Method Get -Uri "$ApiEndpoint/api/preparation/$PreparationID/piece" -ErrorAction Stop
    $DealResponse = Invoke-RestMethod -Method Post -Uri "$ApiEndpoint/api/deal" -ErrorAction Stop

    if (-not $PieceResponse) {
        Write-Warning "No piece data found for Preparation $PreparationID."
        return
    }

    # 2. Extract Preparation Metadata
    # Fetch the full list to find the name/createdAt for this ID
    $PrepList = Invoke-RestMethod -Method Get -Uri "$ApiEndpoint/api/preparation" -ErrorAction Stop
    $PrepMetadata = $PrepList | Where-Object { $_.id -eq $PreparationID }

    if ($null -eq $PrepMetadata) {
        Write-Warning "Preparation ID $PreparationID not found in preparation list. Using defaults."
        $PrepName = "unknown"
        $PrepCreated = "unknown"
    } else {
        $PrepName = $PrepMetadata.name
        $PrepCreated = $PrepMetadata.createdAt
    }

    # 3. Dynamic Filename
    if ([string]::IsNullOrWhiteSpace($OutputFile)) {
        $FileSuffix = ""
        if (-not [string]::IsNullOrWhiteSpace($ProviderID)) { $FileSuffix += "-$ProviderID" }
        if (-not [string]::IsNullOrWhiteSpace($ClientID)) { $FileSuffix += "-$ClientID" }
        if (-not [string]::IsNullOrWhiteSpace($DealState) -and $DealState -ne "active") { $FileSuffix += "-$DealState" }
        $OutputFile = "prep-$PreparationID-piece-cids$FileSuffix.csv"
    }

    Write-Host "Processing data and generating CSV: $OutputFile" -ForegroundColor Cyan

    # 4. Filter and Join
    # Index deals by pieceCid for fast lookup
    $Genesis = [datetimeoffset]::FromUnixTimeSeconds(1598306400)
    $DealLookup = @{}
    $DealResponse | Where-Object {
        ([string]::IsNullOrWhiteSpace($DealState) -or $_.state -eq $DealState) -and
        ([string]::IsNullOrWhiteSpace($ProviderID) -or $_.provider -eq $ProviderID) -and
        ([string]::IsNullOrWhiteSpace($ClientID) -or $_.clientId -eq $ClientID)
    } | ForEach-Object {
        if (-not $DealLookup.ContainsKey($_.pieceCid)) {
            $DealLookup[$_.pieceCid] = New-Object System.Collections.Generic.List[PSObject]
        }
        $DealLookup[$_.pieceCid].Add($_)
    }

    $Results = New-Object System.Collections.Generic.List[PSObject]

    foreach ($Source in $PieceResponse) {
        foreach ($Piece in $Source.pieces) {
            $PieceCid = $Piece.pieceCid
            
            if ($DealLookup.ContainsKey($PieceCid)) {
                foreach ($Deal in $DealLookup[$PieceCid]) {
                    # Convert Epochs to human-readable (UTC)
                    $StartDate = if ($Deal.startEpoch) { $Genesis.AddSeconds($Deal.startEpoch * 30).DateTime.ToString("yyyy-MM-dd HH:mm:ss UTC") } else { "" }
                    $EndDate = if ($Deal.endEpoch) { $Genesis.AddSeconds($Deal.endEpoch * 30).DateTime.ToString("yyyy-MM-dd HH:mm:ss UTC") } else { "" }

                    $Results.Add([PSCustomObject]@{
                        PreparationName  = $PrepName
                        PreparationID    = $PreparationID
                        PrepCreatedAt    = $PrepCreated
                        PieceCID         = $PieceCid
                        PieceSize        = $Piece.pieceSize
                        FileSize         = $Piece.fileSize
                        NumOfFiles       = $Piece.numOfFiles
                        RootCID          = $Piece.rootCid
                        PieceType        = $Piece.pieceType
                        DealID           = $Deal.dealId
                        ProposalID       = $Deal.proposalId
                        StorageProvider  = $Deal.provider
                        ClientID         = $Deal.clientId
                        State            = $Deal.state
                        StartEpoch       = $Deal.startEpoch
                        StartDateTime    = $StartDate
                        EndEpoch         = $Deal.endEpoch
                        EndDateTime      = $EndDate
                    })
                }
            }
        }
    }

    # 5. Export to CSV
    $Results | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding utf8
    Write-Host "Done! CSV saved to $OutputFile" -ForegroundColor Green
    
    $TotalPiecesPrep = ($PieceResponse.pieces | Measure-Object).Count
    $TotalPieceSize = ($Results | Measure-Object -Property PieceSize -Sum).Sum
    $TotalFileSize = ($Results | Measure-Object -Property FileSize -Sum).Sum
    $TotalPieceTiB = [Math]::Round($TotalPieceSize / 1TB, 3)
    $TotalFileTiB = [Math]::Round($TotalFileSize / 1TB, 3)
    $MatchedDeals = ($Results | Where-Object { -not [string]::IsNullOrWhiteSpace($_.DealID) }).Count
    Write-Host "Total Rows: $($Results.Count) (Matched Deals: $MatchedDeals | Total Pieces in Prep: $TotalPiecesPrep | Matched Piece Size: $TotalPieceTiB TiB | Matched File Size: $TotalFileTiB TiB)" -ForegroundColor Yellow
}
catch {
    Write-Error "An error occurred: $_"
}
