# AI CLI Tools

A set of command-line tools providing quick access to central AI services.

## Speech to Text (STT)

The **STT** command transcribes speech from your microphone to text.

#### Usage:

- Basic: `stt` 
  Transcribes a single line of speech.

- File output: `stt > file.txt`
  Saves transcription to a file.

- Real-time mode: `stt -rt`
  Shows transcription in real-time.

#### Example:

```bash
C:\Dev\Test\ai-cli-tools>stt
This is detected speech.
```

## Large Language Model (LLM)

The **LLM** command sends queries to a Large Language Model (using LM Studio on our server).

#### Usage:

- Inline query: `llm "your question here"`
- Piped input: `echo "your question" | llm`
- Speech input: `stt | llm`
- File output: `llm "your question" > answer.txt`

#### Example:

```bash
C:\Dev\Test\ai-cli-tools>llm "When was Barack Obama born?"
Barack Obama, the 44th President of the United States, was born on August 4, 1961.
```

## Text-to-Speech (TTS)

The **RVC** command synthesizes text into speech in real-time.

#### Usage:

- Inline text: `rvc "text to speak"`
- Piped input: `echo "text to speak" | rvc`
- Full pipeline: `stt | llm | rvc`

#### Example:

```bash
C:\Dev\Test\ai-cli-tools>rvc "Let me hear this"
Let me hear this
```

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
