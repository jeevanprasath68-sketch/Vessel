# Launch the Multi-AI Agent Dashboard in VS Code
Write-Host "Starting Autonomous Multi-AI Agent Dashboard..." -ForegroundColor Cyan

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
}

.\.venv\Scripts\streamlit run streamlit_app.py
