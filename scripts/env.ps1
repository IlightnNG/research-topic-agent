# Local environment for this project.  Usage:  . .\scripts\env.ps1
#
# Why: C: drive is nearly full. Every fast-growing store (package caches, models,
# temp files, run data) is centralised on D:\lit-agent-store; the repo itself
# (code / docs / .venv) stays on its original drive.
#
# User-level persistence is already set via [Environment]::SetEnvironmentVariable(...,'User'),
# so new shells inherit these values; the current shell needs this file or a restart.
# NOTE: kept ASCII-only on purpose -- non-BOM UTF-8 .ps1 files are mis-decoded
# by Windows PowerShell (ANSI/GBK) and break parsing.

$LitAgentScriptDir = $PSScriptRoot
if (-not $LitAgentScriptDir) {
    $LitAgentScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $LitAgentScriptDir) {
    $LitAgentScriptDir = (Get-Location).Path
}

$LitAgentRepo  = (Resolve-Path (Join-Path $LitAgentScriptDir '..')).Path
$LitAgentStore = 'D:\lit-agent-store'

$env:UV_CACHE_DIR     = Join-Path $LitAgentStore 'uv-cache'
$env:PIP_CACHE_DIR    = Join-Path $LitAgentStore 'pip-cache'
$env:HF_HOME          = Join-Path $LitAgentStore 'hf'
$env:TORCH_HOME       = Join-Path $LitAgentStore 'torch'
$env:TEMP             = Join-Path $LitAgentStore 'temp'
$env:TMP              = Join-Path $LitAgentStore 'temp'
$env:npm_config_cache = Join-Path $LitAgentStore 'npm'

foreach ($dir in @($env:UV_CACHE_DIR, $env:PIP_CACHE_DIR, $env:HF_HOME, $env:TORCH_HOME, $env:TEMP, $env:npm_config_cache)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

# Allow `python -m lit_agent` from the repo root (no editable install, see pyproject.toml).
$env:PYTHONPATH = Join-Path $LitAgentRepo 'src'

Write-Host "lit-agent env: store=$LitAgentStore  PYTHONPATH=$env:PYTHONPATH" -ForegroundColor DarkGray
