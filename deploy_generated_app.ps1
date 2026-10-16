param (
    [string]$RepoUrl
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Sync & Deploy Generated App to GitHub" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$AppDir = Join-Path $PSScriptRoot "generated_app"

if (-not (Test-Path (Join-Path $AppDir "app.py"))) {
    Write-Host "[Error] No generated app found in 'generated_app/'. Please run the 5-agent pipeline first!" -ForegroundColor Red
    exit 1
}

Push-Location $AppDir
try {
    # Check if git is already initialized
    if (-not (Test-Path ".git")) {
        git init -b main
        git config user.name "Developer"
        git config user.email "developer@example.com"
    }

    # Check for existing remote
    $CurrentRemote = (git remote get-url origin 2>$null)

    if ($RepoUrl) {
        if ($CurrentRemote) {
            git remote set-url origin $RepoUrl
        } else {
            git remote add origin $RepoUrl
        }
        $TargetUrl = $RepoUrl
    } elseif ($CurrentRemote) {
        $TargetUrl = $CurrentRemote
        Write-Host "Using existing remote repository: $TargetUrl" -ForegroundColor Cyan
    } else {
        Write-Host "`nPaste your GitHub repository URL (e.g., https://github.com/user/generated.git):" -ForegroundColor Yellow
        $TargetUrl = Read-Host "URL"
        if (-not $TargetUrl) {
            Write-Host "[Error] Repository URL cannot be empty." -ForegroundColor Red
            exit 1
        }
        git remote add origin $TargetUrl
    }

    Write-Host "`nCommitting and pushing latest generated app..." -ForegroundColor Green
    git add .
    git commit -m "Update generated app: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    git push -u origin main

    Write-Host "`n==================================================" -ForegroundColor Green
    Write-Host "  SUCCESS! Pushed to $TargetUrl" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "Streamlit Community Cloud will automatically detect the push and reload your live app!" -ForegroundColor Yellow
}
finally {
    Pop-Location
}
