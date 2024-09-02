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
- **Multiple LLM Providers**: Switch between different LLM providers (LMStudio, Anthropic, OpenAI, Ollama).
- **Customizable TTS**: Options for different TTS models and voices, including RVC support.

## Project Status

This project is in early alpha stage. Servers aren't stable yet, also this current implementation only offers a working prototype with opinionated, streamlined commands. While customization options are limited at this phase, the foundation is set for potential expansion into a comprehensive CLI Swiss Army knife for STT, LLM, and TTS applications.

## Roadmap

- Enhance customization options for each tool
- Expand API parameter accessibility
- Improve documentation and usage examples
- Gather user feedback for prioritizing new features

## Tool Descriptions

### Speech to Text (STT)

The **STT** command transcribes speech from your microphone to text.

#### Usage:

- Basic: `stt` 
- File output: `stt > file.txt`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>stt
This is detected speech.

C:\Dev\Test\ai-cli-tools>stt > transcription.txt
[Transcription saved to file]
```

### Large Language Model (LLM)

The **LLM** command sends queries to a Large Language Model (using LM Studio on our server).

#### Usage:

- Inline query: `llm your question here`
- Piped input: `echo your question | llm`
- Speech input: `stt | llm`
- File output: `llm your question > answer.txt`
- System message output: `echo hey there | llm answer sassy`
- Provider and model selection: `llm your question --provider [lmstudio|anthropic|openai|ollama] --model [model_name]`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>llm When was Barack Obama born?
Barack Obama, the 44th President of the United States, was born on August 4, 1961.

C:\Dev\Test\ai-cli-tools>echo List 5 reputable sources for information on climate change: | llm > sources.txt

C:\Dev\Test\ai-cli-tools>llm Tell me about AI --anthropic
[Response from Anthropic's Claude model]

C:\Dev\Test\ai-cli-tools>llm Explain quantum computing --openai --model gpt-4
[Response from OpenAI's GPT-4 model]
```

### Text-to-Speech (TTS)

The **TTS** command synthesizes text into speech in real-time.

#### Usage:

- Inline text: `tts text to speak`
- Piped input: `echo text to speak | tts`
- Full pipeline: `stt | llm | tts`
- File output: `tts Hello, world! > output.wav`
- RVC toggle: `tts Hello, world! --rvc`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>tts Let me hear this
Let me hear this

C:\Dev\Test\ai-cli-tools>echo hey there | llm answer short | tts
[Speaks the short answer]

C:\Dev\Test\ai-cli-tools>stt | llm translate to english, only return the translation | tts --rvc > translation.wav
[Transcribes speech, translates it to English, applies RVC, and saves to file]
```

## Advanced Usage

You can combine these tools in various ways to create powerful workflows:

```bash
stt | llm --anthropic | tts --rvc
[Transcribes speech, processes it with Anthropic's LLM, and speaks the result using RVC]

echo Explain relativity | llm --openai --model gpt-4 | tts > explanation.wav
[Processes text with OpenAI's GPT-4, then speaks and saves the result]

stt | llm translate to english, only return the translation | tts --xtts-voice french_voice.wav
[Transcribes speech, translates it to English, and speaks the translation with a French voice]
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

   Execute in that virtual environment:

   ```bash
   pip install -r requirements.txt
   ```

5. **Upgrade PyTorch to Use GPU**

   Execute in venv:

   ```bash
   pip install torch==2.3.1+cu121 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
   ```
   *(Adjust the CUDA version according to your system.)*

6. **Install models for TTS and RVC**

   Execute in venv or main environment:

   For Windows:

   ```bash
   _install_models.bat
   ```

7. **Install CLI commands**

   Execute this on your main python or on your clients environment, NOT in the virtual environment.

   For Windows:

   ```bash
   pip install -r requirements_client.txt
   _install_cli_commands.bat
   ```

8. **Start the servers**

   Execute this on your main python or on your clients environment, NOT in the venv.

   For Windows:

   ```bash
   _start_stt_server.bat
   _start_llm_server.bat
   _start_tts_server.bat
   ```

   or execute

   ```bash
   stt-server
   llm-server
   tts-server
   ```

## Environment Setup

To use certain LLM providers, set the following environment variables on the server machine:

- For OpenAI: `OPENAI_API_KEY`
- For Anthropic: `ANTHROPIC_API_KEY`

## Notes

- You can use CTRL+C to immediately abort any command (stt, llm, tts).
- The system will prompt to start a local server if it's not running when you try to use a command.
- Default models: 
  - OpenAI: gpt-4o-mini
  - Anthropic: claude-3-sonnet-20240229
  - Ollama: llama3.1