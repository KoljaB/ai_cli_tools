@echo off
echo Starting TTS Server
call venv\Scripts\activate.bat
cd tts-cli
python server.py
cmd
