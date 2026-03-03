param(
    [switch]$DesktopOnly,
    [switch]$StartMenuOnly,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $root "release\windows\ProjectMoonlightEngine\ProjectMoonlightEngine.exe"
$launcherPath = Join-Path $root "launch_game_window.bat"
$exeDir = Split-Path -Parent $exePath

if (-not (Test-Path -LiteralPath $exePath)) {
    Write-Host "Executable not found at: $exePath" -ForegroundColor Yellow
    Write-Host "Build first with: build_game_exe.bat" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $launcherPath)) {
    Write-Host "Launcher not found at: $launcherPath" -ForegroundColor Yellow
    exit 1
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$startMenuPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutName = "Project Moonlight Engine.lnk"

$targets = @()
if ($DesktopOnly -and -not $StartMenuOnly) {
    $targets += (Join-Path $desktopPath $shortcutName)
}
elseif ($StartMenuOnly -and -not $DesktopOnly) {
    $targets += (Join-Path $startMenuPath $shortcutName)
}
else {
    $targets += (Join-Path $desktopPath $shortcutName)
    $targets += (Join-Path $startMenuPath $shortcutName)
}

$shell = New-Object -ComObject WScript.Shell
$created = @()
$skipped = @()

foreach ($target in $targets) {
    $parent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        $skipped += $target
        continue
    }

    $shortcut = $shell.CreateShortcut($target)
    $shortcut.TargetPath = $launcherPath
    $shortcut.Arguments = ""
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = "$exePath,0"
    $shortcut.Description = "Launch Project Moonlight Engine"
    $shortcut.Save()
    $created += $target
}

if ($created.Count -gt 0) {
    Write-Host "Created shortcuts:" -ForegroundColor Green
    $created | ForEach-Object { Write-Host " - $_" }
}

if ($skipped.Count -gt 0) {
    Write-Host "Skipped existing shortcuts (use -Force to overwrite):" -ForegroundColor Yellow
    $skipped | ForEach-Object { Write-Host " - $_" }
}

if ($created.Count -eq 0 -and $skipped.Count -eq 0) {
    Write-Host "No shortcuts were created." -ForegroundColor Yellow
}
