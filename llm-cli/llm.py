import argparse
import asyncio
import websockets
import sys
import os
import json

class LLMClient:
    def __init__(self, server_url, debug=False, file_output=None):
        self.server_url = server_url
        self.debug = debug
        self.file_output = file_output

    def debug_print(self, message):
        if self.debug:
            print(message, file=sys.stderr)

    async def send_and_receive(self, websocket, system_message, user_message):
        data = {
            "system": system_message,
            "user": user_message
        }
        await websocket.send(json.dumps(data))
        self.debug_print(f"Sent: {data}")

        while True:
            token = await websocket.recv()
            if token == "":  # Empty string marks end of response
                break
            self.handle_text(token)
        
        self.debug_print("End of response")

    async def process_input(self, system_message, user_message):
        async with websockets.connect(self.server_url) as websocket:
            self.debug_print(f"Connected to {self.server_url}")
            try:
                await self.send_and_receive(websocket, system_message, user_message)
                
                # Gracefully close the connection
                await websocket.close()
            except websockets.exceptions.ConnectionClosed:
                self.debug_print("WebSocket connection closed")


    async def process_input(self, system_message, user_message=None):
        async with websockets.connect(self.server_url) as websocket:
            self.debug_print(f"Connected to {self.server_url}")
            try:
                if user_message is None:
                    # If user_message is not provided, read from stdin
                    user_message = sys.stdin.read().strip()
                await self.send_and_receive(websocket, system_message, user_message)
                
                # Gracefully close the connection
                await websocket.close()
            except websockets.exceptions.ConnectionClosed:
                self.debug_print("WebSocket connection closed")

    def handle_text(self, text):
        if self.file_output:
            try:
                print(text, end="", flush=True, file=self.file_output)
            except UnicodeEncodeError:
                # If encoding fails, try to encode as UTF-8 and replace problematic characters
                encoded_text = text.encode('utf-8', errors='replace').decode('utf-8')
                print(encoded_text, end="", flush=True, file=self.file_output)
        else:
            print(text, end="", flush=True)


def get_user_input():
    return input().strip()

def main():
    parser = argparse.ArgumentParser(description="LLM Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--server", default="ws://localhost:5000/ws", help="WebSocket server URL")
    parser.add_argument("--system", help="System message")
    parser.add_argument("input", nargs="*", help="User message")
    args = parser.parse_args()

    # Check if output is being redirected
    if not os.isatty(sys.stdout.fileno()):
        file_output = sys.stdout
    else:
        file_output = None
    
    client = LLMClient(args.server, args.debug, file_output)
    
    try:
        # Check if there's piped input
        if not sys.stdin.isatty():
            user_message = sys.stdin.read().strip()
            system_message = args.system or " ".join(args.input) or ""
        else:
            system_message = args.system or ""
            user_message = " ".join(args.input)

        # If no user message is provided, prompt the user for input
        if not user_message:
            user_message = get_user_input()

        asyncio.get_event_loop().run_until_complete(client.process_input(system_message, user_message))
    except KeyboardInterrupt:
        client.debug_print("\nStopping client...")

if __name__ == "__main__":
    main()
