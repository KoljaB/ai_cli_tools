import websocket
import pyaudio
import argparse
import json
import threading
import time
import struct
import os
import sys
import socket
import subprocess
import shutil
from urllib.parse import urlparse
from colorama import init, Fore, Style
from queue import Queue

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
DEFAULT_SERVER_URL = "ws://localhost:8011"

class STTWebSocketClient:
    def __init__(self, server_url, debug=False, file_output=None, norealtime=False):
        self.server_url = server_url
        self.ws = None
        self.is_running = False
        self.debug = debug
        self.file_output = file_output
        self.last_text = ""
        self.pbar = None
        self.console_width = shutil.get_terminal_size().columns
        self.recording_indicator = "🔴"
        self.norealtime = norealtime
        self.connection_established = threading.Event()
        self.message_queue = Queue()

    def debug_print(self, message):
        if self.debug:
            print(message, file=sys.stderr)



    # def connect(self):
    #     if not self.ensure_server_running():
    #         print("Cannot start STT server. Exiting.", file=sys.stderr)
    #         return

    #     self.ws = websocket.WebSocketApp(self.server_url,
    #                                      on_message=self.on_message,
    #                                      on_error=self.on_error,
    #                                      on_close=self.on_close)
    #     self.ws.on_open = self.on_open
    #     self.ws.run_forever()

    def connect(self):
        if not self.ensure_server_running():
            self.debug_print("Cannot start STT server. Exiting.")
            return False

        websocket.enableTrace(self.debug)
        try:
            
            self.ws = websocket.WebSocketApp(self.server_url,
                                             on_message=self.on_message,
                                             on_error=self.on_error,
                                             on_close=self.on_close,
                                             on_open=self.on_open)
            
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()

            # Wait for the connection to be established
            if not self.connection_established.wait(timeout=10):
                self.debug_print("Timeout while connecting to the server.")
                return False
            
            self.debug_print("WebSocket connection established successfully.")
            return True
        except Exception as e:
            self.debug_print(f"Error while connecting to the server: {e}")
            return False


    def on_open(self, ws):
        self.debug_print("WebSocket connection opened.")
        self.is_running = True
        self.connection_established.set()
        self.start_recording()

    def on_error(self, ws, error):
        self.debug_print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.debug_print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.is_running = False

    def is_server_running(self):
        parsed_url = urlparse(self.server_url)
        host = parsed_url.hostname
        port = parsed_url.port or 80
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0

    def ask_to_start_server(self):
        response = input("Would you like to start the STT server now? (y/n): ").strip().lower()
        return response == 'y' or response == 'yes'

    def start_server(self):
        if os.name == 'nt':  # Windows
            subprocess.Popen('start /min cmd /c stt-server', shell=True)
        else:  # Unix-like systems
            subprocess.Popen(['stt-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print("STT server start command issued. Please wait a moment for it to initialize.", file=sys.stderr)


    def ensure_server_running(self):
        if not self.is_server_running():
            print("STT server is not running.", file=sys.stderr)
            if self.ask_to_start_server():
                self.start_server()
                print("Waiting for STT server to start...", file=sys.stderr)
                for _ in range(20):  # Wait up to 20 seconds
                    if self.is_server_running():
                        print("STT server started successfully.", file=sys.stderr)
                        time.sleep(2)  # Give the server a moment to fully initialize
                        return True
                    time.sleep(1)
                print("Failed to start STT server.", file=sys.stderr)
                return False
            else:
                print("STT server is required. Please start it manually.", file=sys.stderr)
                return False
        return True

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data['type'] == 'realtime':
                if data['text'] != self.last_text:
                    self.last_text = data['text']
                    if not self.norealtime:
                        self.update_progress_bar(self.last_text) 
            elif data['type'] == 'fullSentence':
                if self.file_output:
                    sys.stderr.write('\r\033[K')
                    sys.stderr.write(data['text'])
                    sys.stderr.write('\n')
                    sys.stderr.flush()
                    print(data['text'], file=self.file_output)
                    self.file_output.flush()  # Ensure it's written immediately
                else:
                    self.finish_progress_bar()
                    print(f"{data['text']}")
                self.stop()
        except json.JSONDecodeError:
            self.debug_print(f"\nReceived non-JSON message: {message}")

    def show_initial_indicator(self):
        if self.norealtime:
            return

        initial_text = f"{self.recording_indicator}\b\b"
        sys.stderr.write(initial_text)
        sys.stderr.flush()

    def update_progress_bar(self, text):
        # Reserve some space for the progress bar decorations
        available_width = self.console_width - 5
        
        # Clear the current line
        sys.stderr.write('\r\033[K')  # Move to the beginning of the line and clear it

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

        sys.stderr.write(colored_text)
        sys.stderr.flush()

    def finish_progress_bar(self):
        # Clear the current line
        sys.stderr.write('\r\033[K')
        sys.stderr.flush()

    def stop(self):
        self.finish_progress_bar()
        self.is_running = False
        if self.ws:
            self.ws.close()
        if hasattr(self, 'ws_thread'):
            self.ws_thread.join(timeout=2)


    def process_messages(self):
        while not self.message_queue.empty():
            message = self.message_queue.get()
            try:
                data = json.loads(message)
                if data['type'] == 'realtime':
                    if data['text'] != self.last_text:
                        self.last_text = data['text']
                        if not self.norealtime:
                            self.update_progress_bar(self.last_text)
                elif data['type'] == 'fullSentence':
                    if self.file_output:
                        sys.stderr.write('\r\033[K')
                        sys.stderr.write(data['text'])
                        sys.stderr.write('\n')
                        sys.stderr.flush()
                        print(data['text'], file=self.file_output)
                        self.file_output.flush()
                    else:
                        self.finish_progress_bar()
                        print(f"\r{data['text']}")
                    self.last_text = ""  # Reset last_text after full sentence
            except json.JSONDecodeError:
                self.debug_print(f"\nReceived non-JSON message: {message}")

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

def main():
    parser = argparse.ArgumentParser(description="STT Client")
    parser.add_argument("--server", default=DEFAULT_SERVER_URL, help="STT WebSocket server URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-nort", "--norealtime", action="store_true", help="Disable real-time output")    
    args = parser.parse_args()

    # Check if output is being redirected
    if not os.isatty(sys.stdout.fileno()):
        file_output = sys.stdout
    else:
        file_output = None
    
    client = STTWebSocketClient(args.server, args.debug, file_output, args.norealtime)
  
    def signal_handler(sig, frame):
        # print("\nInterrupted by user, shutting down...")
        client.stop()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        if client.connect():
            # print("Connection established. Recording... (Press Ctrl+C to stop)", file=sys.stderr)
            while client.is_running:
                client.process_messages()
                time.sleep(0.1)
        else:
            print("Failed to connect to the server.", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    main()
