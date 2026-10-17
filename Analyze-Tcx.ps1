# Offline Garmin TCX runner: file -> one JSON, folder -> one combined JSON.
# Requires Python 3.10+. No installation or additional Python dependencies.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [Alias('TcxPath','Directory')]
    [string]$Path,
    [string]$Output,
    [switch]$Recursive,
    [Nullable[double]]$TreadmillKm,
    [Nullable[double]]$RunSpeedKmh,
    [ValidateSet('polar_h10', 'wrist_optical', 'other_chest', 'unknown')]
    [string]$HeartRateSource = 'unknown',
    [string]$UtcOffset = '+00:00',
    [string]$Metadata,
    [string]$ExpectedManifest,
    [ValidateRange(1, 36500)]
    [int]$DateGapDays = 7,
    [string]$RunWindows,
    [double]$CadenceThreshold = 145,
    [string]$Python
)

$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'src'
if (-not (Test-Path -LiteralPath (Join-Path $src 'garmin_tcx_running_analyzer\__main__.py'))) {
    throw "Python package not found under $src"
}
if ($Python) {
    $exe = $Python
    $prefix = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $exe = (Get-Command py).Source
    $prefix = @('-3')
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { throw 'Python 3.10+ not found. Install Python and try again.' }
    $exe = $pythonCmd.Source
    $prefix = @()
}
$argsList = @('-m', 'garmin_tcx_running_analyzer', $Path, '--tz-offset', $UtcOffset, '--hr-source', $HeartRateSource,
              '--run-cadence-threshold', $CadenceThreshold.ToString([cultureinfo]::InvariantCulture))
if ($Output) { $argsList += @('--output', $Output) }
if ($Recursive) { $argsList += '--recursive' }
if ($null -ne $TreadmillKm) {
    $argsList += @('--treadmill-km', $TreadmillKm.Value.ToString([cultureinfo]::InvariantCulture))
}
if ($null -ne $RunSpeedKmh) {
    $argsList += @('--run-speed-kmh', $RunSpeedKmh.Value.ToString([cultureinfo]::InvariantCulture))
}
if ($Metadata) { $argsList += @('--metadata', $Metadata) }
if ($ExpectedManifest) { $argsList += @('--expected-manifest', $ExpectedManifest) }
$argsList += @('--date-gap-days', $DateGapDays.ToString([cultureinfo]::InvariantCulture))
if ($RunWindows) { $argsList += @('--run-windows', $RunWindows) }
$previousPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($previousPath) { "$src$([IO.Path]::PathSeparator)$previousPath" } else { $src }
    & $exe @prefix @argsList
    if ($LASTEXITCODE -ne 0) { throw "Garmin TCX Running Analyzer failed (exit code $LASTEXITCODE)." }
} finally {
    $env:PYTHONPATH = $previousPath
}
