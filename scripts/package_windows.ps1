$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ProjectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot.Path)
$ProjectRootWithSlash = $ProjectRootPath.TrimEnd("\") + "\"

function Resolve-InProject {
    param([Parameter(Mandatory = $true)][string]$PathToCheck)

    $FullPath = [System.IO.Path]::GetFullPath($PathToCheck)
    $IsRoot = $FullPath.Equals($ProjectRootPath, [System.StringComparison]::OrdinalIgnoreCase)
    $IsChild = $FullPath.StartsWith($ProjectRootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)
    if (-not ($IsRoot -or $IsChild)) {
        throw "Refusing to operate outside project root: $FullPath"
    }
    return $FullPath
}

Set-Location $ProjectRootPath

$PythonExe = Join-Path $ProjectRootPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Missing virtual environment Python: $PythonExe"
}

$BuildDir = Resolve-InProject (Join-Path $ProjectRootPath "build")
$DistDir = Resolve-InProject (Join-Path $ProjectRootPath "dist")

foreach ($Target in @($BuildDir, $DistDir)) {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}

& $PythonExe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed with exit code $LASTEXITCODE"
}

$EntryScript = Resolve-InProject (Join-Path $ProjectRootPath "scripts\pixelator_gui_entry.py")
$WorkPath = Resolve-InProject (Join-Path $ProjectRootPath "build\pyinstaller")
$SpecPath = Resolve-InProject (Join-Path $ProjectRootPath "build\spec")
$SourcePath = Resolve-InProject (Join-Path $ProjectRootPath "src")
$PresetsPath = Resolve-InProject (Join-Path $ProjectRootPath "presets")

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name Pixelator `
    --distpath $DistDir `
    --workpath $WorkPath `
    --specpath $SpecPath `
    --paths $SourcePath `
    --collect-all PySide6 `
    --collect-all imageio_ffmpeg `
    --add-data "$PresetsPath;presets" `
    $EntryScript
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$PackageExe = Join-Path $DistDir "Pixelator\Pixelator.exe"
if (-not (Test-Path -LiteralPath $PackageExe)) {
    throw "Expected package executable was not created: $PackageExe"
}

Write-Host "Portable package ready: $PackageExe"
