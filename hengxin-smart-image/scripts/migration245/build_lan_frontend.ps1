param([string]$Version = '0.2.67-lan.2')

$ErrorActionPreference = 'Stop'
$frontendRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../frontend')).Path
$buildEnvironment = @{
    VITE_VERSION = $Version
    VITE_ACCESS_MODE = 'frontend'
    VITE_API_URL = '/api/v1'
    VITE_BASE_URL = '/'
}
$previousEnvironment = @{}
foreach ($name in $buildEnvironment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Push-Location $frontendRoot
try {
    foreach ($name in $buildEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $buildEnvironment[$name], 'Process')
    }
    # This controls menu routing, not backend authentication or API availability.
    & pnpm exec vue-tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed' }
    & pnpm exec vite build --mode production --outDir dist-lan-ip
    if ($LASTEXITCODE -ne 0) { throw 'LAN frontend build failed' }
} finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    Pop-Location
}
