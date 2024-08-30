REM call _start_venv.bat
echo Installating basic dependencies
pip install -r requirements.txt

echo Upgrading torch to use GPU
pip install torch==2.3.1+cu121 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121

echo Installation of dependencies finished