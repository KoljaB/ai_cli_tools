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
- Real-time mode: `stt -rt`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>stt
This is detected speech.

C:\Dev\Test\ai-cli-tools>stt -rt
[Real-time transcription output]

C:\Dev\Test\ai-cli-tools>stt > transcription.txt
[Transcription saved to file]
```

### Large Language Model (LLM)

The **LLM** command sends queries to a Large Language Model (using LM Studio on our server).

#### Usage:

- Inline query: `llm "your question here"`
- Piped input: `echo "your question" | llm`
- Speech input: `stt | llm`
- File output: `llm "your question" > answer.txt`
- Styled output: `echo hey there | llm "answer bold"`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>llm "When was Barack Obama born?"
Barack Obama, the 44th President of the United States, was born on August 4, 1961.

C:\Dev\Test\ai-cli-tools>echo "List 5 reputable sources for information on climate change:" | llm > sources.txt

C:\Dev\Test\ai-cli-tools>echo hey there | llm "answer short"
[Short answer]

C:\Dev\Test\ai-cli-tools>echo "Write a hello world in python, only return python code" | llm > helloworld.py && python helloworld.py
[Executes the generated Python script]

C:\Dev\Test\ai-cli-tools>echo "Write Python code that: 1. Imports the necessary modules (time) 2. Defines a function to get the current time in MM:SS Format 3. Uses a loop to continuously print the time 4. Updates the display every 5 seconds using time.sleep() 5. Runs indefinitely until manually stopped." | llm "Your entire response must be only the improved Python code, with no explanations, comments, or formatting. Start your response with 'import' and end it with the last line of code. Do not include triple backticks, 'python', or any other text outside the Python code itself." > simple_clock.py && python simple_clock.py
[Generates and runs a Python clock script]

C:\Dev\Test\ai-cli-tools>type simple_clock.py | llm "Improve this Python code. Your entire response must be only the improved Python code, with no explanations, comments, or formatting. Start your response with 'import' and end it with the last line of code. Do not include triple backticks, 'python', or any other text outside the Python code itself."
[Returns improved Python code]
```

### Text-to-Speech (TTS)

The **RVC** command synthesizes text into speech in real-time.

#### Usage:

- Inline text: `rvc "text to speak"`
- Piped input: `echo "text to speak" | rvc`
- Full pipeline: `stt | llm | rvc`

#### Examples:

```bash
C:\Dev\Test\ai-cli-tools>rvc "Let me hear this"
Let me hear this

C:\Dev\Test\ai-cli-tools>echo hey there | llm "answer bold" | rvc
[Speaks the bold-formatted answer]

C:\Dev\Test\ai-cli-tools>llm "give me a short tip for learning french" | rvc
[Speaks a French learning tip]

C:\Dev\Test\ai-cli-tools>stt | llm "translate to english, only return the translation" | rvc
[Speaks the English translation of the transcribed speech]
```

## Advanced Usage

You can combine these tools in various ways to create powerful workflows:

```bash
stt | llm | rvc
[Transcribes speech, processes it with LLM, and speaks the result]

echo hey there | llm "answer bold" | rvc
[Processes text with LLM using a style instruction, then speaks the result]

stt | llm "translate to english, only return the translation" | rvc
[Transcribes speech, translates it to English, and speaks the translation]
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