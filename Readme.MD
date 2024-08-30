# AI CLI Tools

A command-line interface for access to core AI services: speech-to-text, large language models, and text-to-speech. This toolkit offers advanced AI capabilities directly from their terminal.

## Key Features

- **Speech-to-Text (STT)**: Transcribe speech from your microphone to text.
- **Large Language Model (LLM)**: Interact with powerful language models for various tasks.
- **Text-to-Speech (TTS)**: Convert text to natural-sounding speech.

## Highlights

- **Remote Server Support**: All AI services can be installed on remote servers for enhanced performance and flexibility.
- **Modular Design**: Each tool functions independently and can be combined for complex workflows.
- **Real-time Processing**: Supports real-time transcription and speech synthesis.

## Project Status

This project is in early alpha stage. The current implementation offers a working prototype with opinionated, streamlined commands. While customization options are limited at this phase, the foundation is set for potential expansion into a comprehensive CLI Swiss Army knife for STT, LLM, and TTS applications.

## Roadmap

- Enhance customization options for each tool
- Expand API parameter accessibility
- Improve documentation and usage examples
- Gather user feedback for prioritizing new features

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

## Prerequisites

- Python 3.10.9
- CUDA 12.1

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/KoljaB/ai_cli_tools.git
   cd ai_cli_tools
   ```

2. **Create a Virtual Environment**

   For Windows:

   ```bash
   _create_venv.bat
   ```

3. **Activate the Virtual Environment**

   For Windows:

   ```bash
   _start_venv.bat
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

7. **Start the servers**

   For Windows:

   ```bash
   _start_llm_server.bat
   _start_stt_server.bat
   _start_tts_server.bat
   ```

8. **Install CLI commands**

   Execute this on your clients main environment, NOT in the venv.

   For Windows:

   ```bash
   pip install -r requirements_client.txt
   _install_cli_commands.bat
   ```
