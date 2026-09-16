[CmdletBinding()]
param(
    [ValidateSet('check', 'start', 'stop', 'fixture', 'status')]
    [string]$Action = 'check',
    [string]$ProjectName = 'hx-local-test',
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env'),
    [string]$LocalFile = (Join-Path $PSScriptRoot '.env.local-codex'),
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
# Windows Python needs python-dotenv (already in the backend environment).
# No shell command strings, runtime installation or implicit service startup.
& $Python (Join-Path $PSScriptRoot 'local_codex_control.py') $Action `
    --project $ProjectName --env-file $EnvFile --local-file $LocalFile
exit $LASTEXITCODE
