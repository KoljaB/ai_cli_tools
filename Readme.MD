# AI CLI Tools

A set of command-line tools providing quick access to central AI services.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/KoljaB/ai_cli_tools.git
   ```

2. **Create a Virtual Environment**

   For Windows:

   ```bash
   start _create_venv.bat
   ```

3. **Activate the Virtual Environment**

   For Windows:

   ```bash
   start _start_venv.bat
   ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Upgrade PyTorch to Use GPU**

   ```bash
   pip install torch==2.3.1+cu121 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
   ```
   *(Adjust the CUDA version according to your system.)*

6. **Install models for TTS and RVC**

   For Windows:

   ```bash
   _install_models.bat
   ```

7. **Install CLI commands**

   For Windows:

   ```bash
   pip install -r requirements_client.txt
   _install_cli_commands.bat
   ```

8. **Start the servers**

   For Windows:

   ```bash
   _start_llm_server.bat
   _start_stt_server.bat
   _start_tts_server.bat
   ```
