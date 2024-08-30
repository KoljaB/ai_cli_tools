import websocket
import pyaudio
import argparse
import json
import threading
import time
import struct
import os
import sys
import shutil
from colorama import init, Fore, Style
from tqdm import tqdm

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
DEFAULT_SERVER_URL = "ws://localhost:8011"

class STTWebSocketClient:
    def __init__(self, server_url, debug=False, file_output=None, realtime=False):
        self.server_url = server_url
        self.ws = None
        self.is_running = False
        self.debug = debug
        self.file_output = file_output
        self.last_text = ""
        self.pbar = None
        self.console_width = shutil.get_terminal_size().columns
        self.recording_indicator = "🔴"
        self.realtime = realtime

    def debug_print(self, message):
        if self.debug:
            print(message)

    def connect(self):
        self.ws = websocket.WebSocketApp(self.server_url,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.ws.on_open = self.on_open
        self.ws.run_forever()

    def show_initial_indicator(self):
        if not self.realtime:
            return

        initial_text = f"{self.recording_indicator}"
        if self.pbar is None:
            self.pbar = tqdm(total=1, bar_format='{desc}', desc=initial_text, leave=False)
        else:
            self.pbar.set_description_str(initial_text)
        self.pbar.refresh()
        
        # Move cursor one position back
        sys.stdout.write('\b\b')
        sys.stdout.flush()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data['type'] == 'realtime':
                if data['text'] != self.last_text:
                    self.last_text = data['text']
                    if not self.file_output and self.realtime:
                        self.update_progress_bar(self.last_text) 
            elif data['type'] == 'fullSentence':
                if self.file_output:
                    print(data['text'], file=self.file_output)
                    self.file_output.flush()  # Ensure it's written immediately
                else:
                    self.finish_progress_bar()
                    print(f"{data['text']}")
                self.stop()
        except json.JSONDecodeError:
            self.debug_print(f"\nReceived non-JSON message: {message}")


    def update_progress_bar(self, text):
        # Reserve some space for the progress bar decorations
        available_width = self.console_width - 10
        
        # Clear the current line
        sys.stdout.write('\r\033[K')  # Move to the beginning of the line and clear it

        # Get the last 'available_width' characters, but don't cut words
        words = text.split()
        last_chars = ""
        for word in reversed(words):
            if len(last_chars) + len(word) + 1 > available_width:
                break
            last_chars = word + " " + last_chars

        last_chars = last_chars.strip()

        # Color the text yellow and add recording indicator
        colored_text = f"{Fore.YELLOW}{last_chars}{Style.RESET_ALL}{self.recording_indicator}\b\b"

        if self.pbar is None:
            self.pbar = tqdm(total=1, bar_format='{desc}', desc=colored_text, leave=False)
        else:
            self.pbar.set_description_str(colored_text)
        self.pbar.refresh()

    def finish_progress_bar(self):
        if self.pbar:
            self.pbar.close()
            self.pbar = None

    def stop(self):
        self.finish_progress_bar()
        self.is_running = False
        if self.ws:
            self.ws.close()

    def on_error(self, ws, error):
        self.debug_print(f"\nError: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.debug_print("\nConnection closed")
        self.is_running = False

    def on_open(self, ws):
        self.debug_print(f"Connected to {self.server_url}")
        self.is_running = True
        self.start_recording()

    def start_recording(self):
        self.show_initial_indicator()
        threading.Thread(target=self.record_and_send_audio).start()

    def record_and_send_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        input_device_index=3,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        self.debug_print("Recording and sending audio...")

        while self.is_running:
            try:
                audio_data = stream.read(CHUNK)
                
                # Prepare metadata
                metadata = {
                    "sampleRate": RATE
                }
                metadata_json = json.dumps(metadata)
                metadata_length = len(metadata_json)
                
                # Construct the message
                message = struct.pack('<I', metadata_length) + metadata_json.encode('utf-8') + audio_data
                
                self.ws.send(message, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                self.debug_print(f"\nError sending audio data: {e}")
                break

        self.debug_print("Stopped recording.")
        stream.stop_stream()
        stream.close()
        p.terminate()

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()

def main():
    parser = argparse.ArgumentParser(description="STT Client")
    parser.add_argument("--server", default=DEFAULT_SERVER_URL, help="STT WebSocket server URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-rt", "--realtime", action="store_true", help="Enable real-time output")    
    args = parser.parse_args()

    # Check if output is being redirected
    if not os.isatty(sys.stdout.fileno()):
        file_output = sys.stdout
    else:
        file_output = None
    
    client = STTWebSocketClient(args.server, args.debug, file_output, args.realtime)
    
    try:
        client.connect()
    except KeyboardInterrupt:
        client.debug_print("\nStopping client...")
        client.stop()

if __name__ == "__main__":
    main()