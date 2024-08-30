@echo off

:: Set Python path (adjust this if needed)
set PYTHON_EXE=python.exe


echo Installing AI CLI Tools...
setlocal enabledelayedexpansion

:: Set current directory
cd /d %~dp0

echo Starting installation process...

:: Create and activate virtual environment
echo Creating and activating virtual environment...
%PYTHON_EXE% -m venv venv
call venv\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install pip==23.3.1

