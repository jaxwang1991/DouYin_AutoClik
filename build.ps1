# -*- coding: utf-8 -*-
# DouYin_AutoClik Build Script
# PowerShell script for building and packaging

param(
    [switch]$SkipPyInstaller = $false
)

# Set error action
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Load version info
$versionFile = Join-Path $ScriptDir "version.py"
$versionContent = Get-Content $versionFile -Raw
$versionContent -match '__version__\s*=\s*["'']([^"'']+)["'']' | Out-Null
$Version = $matches[1]
$versionContent -match '__app_name__\s*=\s*["'']([^"'']+)["'']' | Out-Null
$AppName = $matches[1]
$ZipName = "$AppName-v$Version-win64.zip"

$DistDir = Join-Path $ScriptDir "dist"
$BuildDir = Join-Path $ScriptDir "build"
$AppDistDir = Join-Path $DistDir $AppName
$InternalDir = Join-Path $AppDistDir "_internal"
$PlaywrightDir = Join-Path $InternalDir "playwright\driver"

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  $AppName - Build Script v$Version" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check and install PyInstaller
if (-not $SkipPyInstaller) {
    Write-Host "[1/7] Checking PyInstaller..." -ForegroundColor Yellow
    $pyinstallerInstalled = pip show pyinstaller 2>$null
    if (-not $pyinstallerInstalled) {
        Write-Host "  Installing PyInstaller..." -ForegroundColor Green
        pip install pyinstaller
    } else {
        Write-Host "  PyInstaller is already installed." -ForegroundColor Green
    }
}

# Step 2: Clean previous build
Write-Host ""
Write-Host "[2/7] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path $BuildDir) {
    Remove-Item -Path $BuildDir -Recurse -Force
    Write-Host "  Removed build/ directory." -ForegroundColor Gray
}
if (Test-Path $AppDistDir) {
    Remove-Item -Path $AppDistDir -Recurse -Force
    Write-Host "  Removed dist/$AppName directory." -ForegroundColor Gray
}

# Step 3: Run PyInstaller
if (-not $SkipPyInstaller) {
    Write-Host ""
    Write-Host "[3/7] Running PyInstaller..." -ForegroundColor Yellow
    pyinstaller --clean DouYin_AutoClik.spec
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Build failed! Please check errors above." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  PyInstaller completed successfully." -ForegroundColor Green
}

# Step 4: Copy optimized Playwright browsers
Write-Host ""
Write-Host "[4/7] Copying Playwright browsers (optimized)..." -ForegroundColor Yellow

$PlaywrightSource = Join-Path $env:LOCALAPPDATA "ms-playwright"

if (-not (Test-Path $PlaywrightSource)) {
    Write-Host "  WARNING: Playwright browsers not found at $PlaywrightSource" -ForegroundColor Red
    Write-Host "  Please run: python -m playwright install chromium" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Continuing build without Playwright browsers..." -ForegroundColor Yellow
} else {
    # Create destination directory
    if (-not (Test-Path $PlaywrightDir)) {
        New-Item -ItemType Directory -Path $PlaywrightDir -Force | Out-Null
    }

    # Copy only chromium and ffmpeg (skip firefox, webkit, etc.)
    $browsersToCopy = @("chromium", "ffmpeg")
    $copiedCount = 0

    foreach ($browser in $browsersToCopy) {
        $browserDirs = Get-ChildItem -Path $PlaywrightSource -Directory | Where-Object { $_.Name -like "$browser-*" }
        foreach ($browserDir in $browserDirs) {
            $destPath = Join-Path $PlaywrightDir $browserDir.Name
            Write-Host "  Copying $($browserDir.Name)..." -ForegroundColor Gray
            Copy-Item -Path $browserDir.FullName -Destination $destPath -Recurse -Force
            $copiedCount++
        }
    }

    if ($copiedCount -gt 0) {
        Write-Host "  Copied $copiedCount Playwright components." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: No Playwright browsers found to copy." -ForegroundColor Yellow
    }
}

# Step 5: Create data directory structure
Write-Host ""
Write-Host "[5/7] Creating data directory structure..." -ForegroundColor Yellow
$DataDir = Join-Path $AppDistDir "data"
$LogsDir = Join-Path $DataDir "logs"
$AudioDir = Join-Path $LogsDir "audio"
$TranscriptsDir = Join-Path $LogsDir "transcripts"

New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
New-Item -ItemType Directory -Path $AudioDir -Force | Out-Null
New-Item -ItemType Directory -Path $TranscriptsDir -Force | Out-Null
Write-Host "  Created data directories." -ForegroundColor Green

# Step 6: Update and copy README.txt
Write-Host ""
Write-Host "[6/7] Updating and copying README.txt..." -ForegroundColor Yellow
$ReadmeSource = Join-Path $ScriptDir "README.txt"

if (Test-Path $ReadmeSource) {
    $readmeContent = Get-Content $ReadmeSource -Raw -Encoding UTF8

    # Replace version and date placeholders
    $readmeContent = $readmeContent -replace '版本:\s*\d+\.\d+\.\d+', "版本: $Version"
    $readmeContent = $readmeContent -replace '更新:\s*\d{4}-\d{2}-\d{2}', "更新: $((Get-Date).ToString('yyyy-MM-dd'))"

    # Save to dist directory
    $ReadmeDest = Join-Path $AppDistDir "README.txt"
    [System.IO.File]::WriteAllText($ReadmeDest, $readmeContent, [System.Text.Encoding]::UTF8)
    Write-Host "  README.txt updated with version $Version." -ForegroundColor Green
} else {
    Write-Host "  WARNING: README.txt not found." -ForegroundColor Yellow
}

# Step 7: Create Zip package
Write-Host ""
Write-Host "[7/7] Creating Zip package..." -ForegroundColor Yellow
$ZipPath = Join-Path $DistDir $ZipName

if (Test-Path $ZipPath) {
    try {
        Remove-Item -Path $ZipPath -Force
    } catch {
        Write-Host "  WARNING: Cannot remove old zip file (in use). Using timestamped name." -ForegroundColor Yellow
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $ZipName = "$AppName-v$Version-$timestamp-win64.zip"
        $ZipPath = Join-Path $DistDir $ZipName
    }
}

# Use Compress-Archive (PowerShell 5.1+)
try {
    Compress-Archive -Path "$AppDistDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal

    # Get file sizes
    $dirSize = (Get-ChildItem -Path $AppDistDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
    $zipSize = (Get-Item $ZipPath).Length / 1MB

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "  Build completed successfully!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Package location: $ZipPath" -ForegroundColor Cyan
    Write-Host "  Unpacked size:     $([math]::Round($dirSize, 2)) MB" -ForegroundColor Gray
    Write-Host "  Compressed size:  $([math]::Round($zipSize, 2)) MB" -ForegroundColor Gray
    Write-Host "  Compression ratio: $([math]::Round(($dirSize - $zipSize) / $dirSize * 100, 1))%" -ForegroundColor Gray
    Write-Host ""

} catch {
    Write-Host "  ERROR: Failed to create zip file." -ForegroundColor Red
    Write-Host "  $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Build folder is available at: $AppDistDir" -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
