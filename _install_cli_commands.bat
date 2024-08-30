echo Installing CLI commands
cd llm-cli
pip uninstall -y llm-cli
pip install -e .
cd ..
cd stt-cli
pip uninstall -y stt-cli
pip install -e .
cd ..
cd tts-cli
pip uninstall -y tts-cli
pip install -e .
cd ..

echo Installation of CLI commands finished