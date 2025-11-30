@echo off
REM SmartStoreDB Quick Start Script
REM Run this to install dependencies and start the application

echo.
echo ============================================================
echo  SmartStoreDB - Quick Start
echo ============================================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from python.org
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version

echo.
echo [2/3] Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [WARNING] Some packages failed to install
    echo Trying to install individually...
    pip install numpy
    pip install scikit-learn
    pip install colorama
)

echo.
echo [3/3] Starting SmartStoreDB...
echo.
echo ============================================================
echo.

python -m smartstoredb.main

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start SmartStoreDB
    echo.
    echo Trying alternative method...
    python smartstoredb\main.py
)

pause
