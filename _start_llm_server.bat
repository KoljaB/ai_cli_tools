@echo off
echo Starting LLM Server
call venv\Scripts\activate.bat
cd llm-cli
python server.py
cmd
