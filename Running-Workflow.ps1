# Optional local workflow for AI agents: ingest TCX, safely record user feedback, rebuild history.
# Python 3.10+; all content stays on the user's computer.
[CmdletBinding(DefaultParameterSetName = 'Ingest')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Ingest')]
    [switch]$Ingest,
    [Parameter(Mandatory = $true, ParameterSetName = 'Rebuild')]
    [switch]$Rebuild,
    [Parameter(Mandatory = $true, ParameterSetName = 'Record')]
    [switch]$Record,
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [Parameter(Mandatory = $true, ParameterSetName = 'Ingest')]
    [string[]]$Paths,
    [Parameter(ParameterSetName = 'Ingest')]
    [string]$UtcOffset,
    [Parameter(Mandatory = $true, ParameterSetName = 'Record')]
    [string]$File,
    [Parameter(Mandatory = $true, ParameterSetName = 'Record')]
    [string]$Patch,
    [string]$Python
)

$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'src'
if (-not (Test-Path -LiteralPath (Join-Path $src 'tcx_running_analyzer\workflow_cli.py'))) {
    throw "Workflow package not found under $src"
}
if ($Python) {
    $exe = $Python; $prefix = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $exe = (Get-Command py).Source; $prefix = @('-3')
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { throw 'Python 3.10+ not found.' }
    $exe = $pythonCmd.Source; $prefix = @()
}
$previousPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($previousPath) { "$src$([IO.Path]::PathSeparator)$previousPath" } else { $src }
    if ($Ingest) {
        $command = 'tcx_running_analyzer.workflow_cli'
        $argsList = @('ingest', '--workspace', $Workspace)
        if ($UtcOffset) { $argsList += @('--tz-offset', $UtcOffset) }
        $argsList += $Paths
    } elseif ($Record) {
        $command = 'tcx_running_analyzer.metadata_cli'
        $argsList = @('--report', (Join-Path $Workspace 'running-activities.json'),
                      '--metadata', (Join-Path $Workspace 'running-metadata.json'),
                      '--file', $File, '--patch', $Patch)
    } else {
        $command = 'tcx_running_analyzer.workflow_cli'
        $argsList = @('rebuild', '--workspace', $Workspace)
    }
    & $exe @prefix '-m' $command @argsList
    if ($LASTEXITCODE -ne 0) { throw "Workflow failed (exit code $LASTEXITCODE)." }
    if ($Record) {
        & $exe @prefix '-m' 'tcx_running_analyzer.workflow_cli' 'rebuild' '--workspace' $Workspace
        if ($LASTEXITCODE -ne 0) { throw "Metadata saved, but history rebuild failed (exit code $LASTEXITCODE); retry -Rebuild." }
    }
} finally {
    $env:PYTHONPATH = $previousPath
}
