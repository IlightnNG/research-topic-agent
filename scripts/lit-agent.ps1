param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CliArgs
)

# Local launcher for `lit-agent`.
# The project is NOT installed editable: the repo path contains non-ASCII characters and a
# *.pth entry with that path makes CPython's site.py raise UnicodeDecodeError on zh-CN Windows.
# Usage: .\scripts\lit-agent.ps1 doctor --strict

$ErrorActionPreference = 'Stop'

$LitAgentScriptDir = $PSScriptRoot
if (-not $LitAgentScriptDir) {
    $LitAgentScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $LitAgentScriptDir) {
    $LitAgentScriptDir = (Get-Location).Path
}

. (Join-Path $LitAgentScriptDir 'env.ps1')

$venvPython = Join-Path $LitAgentScriptDir '..\.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    & (Resolve-Path $venvPython).Path -m lit_agent @CliArgs
}
else {
    & python -m lit_agent @CliArgs
}
exit $LASTEXITCODE
