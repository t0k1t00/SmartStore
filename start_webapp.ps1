# SmartStoreDB Web Application Startup Script
# PowerShell script for Windows

Write-Host "🚀 Starting SmartStoreDB Web Application..." -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Python found: $(python --version)" -ForegroundColor Green

# Check if in virtual environment
if ($env:VIRTUAL_ENV) {
    Write-Host "✅ Virtual environment active: $env:VIRTUAL_ENV" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: No virtual environment active" -ForegroundColor Yellow
    Write-Host "   Consider creating one: python -m venv venv" -ForegroundColor Yellow
    Write-Host "   Then activate it: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host ""
}

# Check if requirements are installed
Write-Host "📦 Checking dependencies..." -ForegroundColor Cyan
$requiredPackages = @("fastapi", "uvicorn", "portalocker", "redis", "pydantic")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $installed = python -c "import $package" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "⚠️  Missing packages: $($missingPackages -join ', ')" -ForegroundColor Yellow
    Write-Host "   Install with: pip install -r webapp/requirements.txt" -ForegroundColor Yellow
    Write-Host ""
    
    $response = Read-Host "Install dependencies now? (y/n)"
    if ($response -eq 'y') {
        Write-Host "📥 Installing dependencies..." -ForegroundColor Cyan
        pip install -r webapp/requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
        Write-Host "✅ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "❌ Cannot start without dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ All required packages installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "🌐 Starting Uvicorn server..." -ForegroundColor Cyan
Write-Host "   URL: http://localhost:8000" -ForegroundColor White
Write-Host "   Docs: http://localhost:8000/api/v1/docs" -ForegroundColor White
Write-Host "   Health: http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
python -m uvicorn webapp.main:app --reload --host 0.0.0.0 --port 8000
