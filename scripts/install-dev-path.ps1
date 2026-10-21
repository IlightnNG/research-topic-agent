# Make `import lit_agent` work in this venv WITHOUT PYTHONPATH.
#
# Why: the repo path contains non-ASCII characters (E:\大学\NUS\EE5003\agent), which breaks
# editable installs, and .pth files are read with the *locale* codec (GBK here), so a UTF-8
# path inside a .pth file crashes site.py at interpreter start.
# Therefore: expose src through an ASCII junction on D:, then point a .pth at that junction.
#
# Idempotent: safe to re-run after recreating .venv or moving the repo.

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo 'src'
$link = 'D:\lit-agent-store\src'
$pth = Join-Path $repo '.venv\Lib\site-packages\_lit_agent_src.pth'

if (-not (Test-Path $src)) { throw "src not found: $src" }

New-Item -ItemType Directory -Force -Path 'D:\lit-agent-store' | Out-Null
if (Test-Path $link) {
    $target = (Get-Item $link).Target
    if ($target -and ($target -ne $src)) {
        cmd /c rmdir "$link" | Out-Null
        cmd /c mklink /J "$link" "$src" | Out-Null
    }
} else {
    cmd /c mklink /J "$link" "$src" | Out-Null
}

if (-not (Test-Path $pth)) {
    New-Item -ItemType File -Force -Path $pth | Out-Null
}
Set-Content -Path $pth -Value $link -Encoding ascii

$python = Join-Path $repo '.venv\Scripts\python.exe'
& $python -c "import lit_agent, pathlib; print('import ok:', pathlib.Path(lit_agent.__file__).parent)"
