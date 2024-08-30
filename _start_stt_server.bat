@echo off
echo Starting STT Server
call venv\Scripts\activate.bat
cd stt-cli
python server.py
cmd
