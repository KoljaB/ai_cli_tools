import asyncio
import websockets
import json
import argparse
import sys
import os
import socket
import subprocess
from datetime import datetime
from urllib.parse import urlparse

class LLMClient:
    def __init__(self, server_url, debug=False, file_output=None):
        self.server_url = server_url
        self.debug = debug
        self.file_output = file_output
        parsed_url = urlparse(self.server_url)
        self.host = parsed_url.hostname
        self.port = parsed_url.port or 80

    def debug_print(self, message, force=False):
        if self.debug or force:
            print(f"{self.current_timestamp()} - {message}", file=sys.stderr)

    def current_timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def is_server_running(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((self.host, self.port)) == 0

    async def ensure_server_running(self):
        if not self.is_server_running():
            self.debug_print("LLM server is not running.", force=True)
            if self.ask_to_start_server():
                self.start_server()
                self.debug_print("Waiting for LLM server to start...", force=True)
                for _ in range(30):  # Wait up to 30 seconds
                    if self.is_server_running():
                        self.debug_print("LLM server started successfully.", force=True)
                        return True
                    await asyncio.sleep(1)
                self.debug_print("Failed to start LLM server.", force=True)
                return False
            else:
                self.debug_print("LLM server is required. Please start it manually.", force=True)
                return False
        return True


    async def send_and_receive(self, websocket, system_message, user_message):
        self.websocket = websocket
        data = {
            "system": system_message,
            "user": user_message
        }
        self.debug_print(f"Sending: {json.dumps(data)}")
        await websocket.send(json.dumps(data))

        try:
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    if response == "":  # Empty string marks end of response
                        break
                    self.handle_text(response)
                except asyncio.TimeoutError:
                    self.debug_print("Timeout waiting for response")
                    break
                except websockets.exceptions.ConnectionClosed:
                    self.debug_print("WebSocket connection closed")
                    break
        except asyncio.CancelledError:
            raise

    async def process_input(self, system_message, user_message):
        self.debug_print(f"Connecting to {self.server_url}")
        if not await self.ensure_server_running():
            return        
        try:
            async with websockets.connect(self.server_url, timeout=5) as websocket:
                self.debug_print("Connected")
                await self.send_and_receive(websocket, system_message, user_message)
        except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
            print(f"Error: Unable to connect to the LLM server at {self.server_url}", file=sys.stderr)
            print("The server might not be running.", file=sys.stderr)
            self.debug_print(f"Connection error details: {str(e)}")
            
            if self.ask_to_start_server():
                self.start_server()
                print("Retrying connection...", file=sys.stderr)
                await asyncio.sleep(2)  # Give the server a moment to start
                await self.process_input(system_message, user_message)  # Retry
            else:
                print("Please start the server manually and try again.", file=sys.stderr)
        except asyncio.TimeoutError:
            print(f"Error: Connection attempt to the LLM server at {self.server_url} timed out.", file=sys.stderr)
            print("Please check your network connection and server status.", file=sys.stderr)

    def ask_to_start_server(self):
        response = input("Would you like to start the server now? (y/n): ").strip().lower()
        return response == 'y' or response == 'yes'

    def start_server(self):
        if os.name == 'nt':  # Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE
            subprocess.Popen('llm-server', startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix-like systems
            subprocess.Popen(['llm-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print("Server start command issued. Please wait a moment for it to initialize.", file=sys.stderr)

    def handle_text(self, text):
        if self.file_output:
            try:
                print(text, end="", flush=True, file=self.file_output)
            except UnicodeEncodeError:
                encoded_text = text.encode('utf-8', errors='replace').decode('utf-8')
                print(encoded_text, end="", flush=True, file=self.file_output)
        else:
            print(text, end="", flush=True)

def get_user_input():
    return input().strip()

def parse_arguments():
    parser = argparse.ArgumentParser(description="LLM Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--server", default="ws://localhost:5000", help="WebSocket server URL")
    parser.add_argument("--system", help="System message")
    parser.add_argument("input", nargs="*", help="User message")
    return parser.parse_args()

async def run_client(args):
    file_output = sys.stdout if not os.isatty(sys.stdout.fileno()) else None
    
    client = LLMClient(args.server, args.debug, file_output)
    
    try:
        if not sys.stdin.isatty():
            user_message = sys.stdin.read().strip()
            system_message = args.system or " ".join(args.input) or ""
        else:
            system_message = args.system or ""
            user_message = " ".join(args.input)

        if not user_message:
            user_message = get_user_input()

        await client.process_input(system_message, user_message)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        client.debug_print(f"An error occurred: {str(e)}", force=True)
    finally:
        pass

def main():
    args = parse_arguments()
    try:
        asyncio.run(run_client(args))
    except KeyboardInterrupt:
        pass
    finally:
        pass

if __name__ == "__main__":
    main()