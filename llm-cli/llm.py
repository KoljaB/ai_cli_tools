import argparse
import asyncio
import websockets
import sys
import os

class LLMClient:
    def __init__(self, server_url, debug=False, file_output=None):
        self.server_url = server_url
        self.debug = debug
        self.file_output = file_output

    def debug_print(self, message):
        if self.debug:
                print(message, file=sys.stderr)

    async def send_and_receive(self, websocket, text):
        await websocket.send(text)
        self.debug_print(f"Sent: {text}")

        while True:
            token = await websocket.recv()
            if token == "":  # Empty string marks end of response
                break
            self.handle_text(token)
        
        self.debug_print("End of response")

    async def process_input(self, input_text=None):
        async with websockets.connect(self.server_url) as websocket:
            self.debug_print(f"Connected to {self.server_url}")
            try:
                if input_text:
                    # If input_text is provided, use it directly
                    await self.send_and_receive(websocket, input_text)
                else:
                    # Otherwise, read from stdin
                    while True:
                        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                        if not line:
                            break
                        await self.send_and_receive(websocket, line.strip())
                
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


def main():
    parser = argparse.ArgumentParser(description="LLM Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--server", default="ws://localhost:5000/ws", help="WebSocket server URL")
    parser.add_argument("input", nargs="*", help="Input text (optional)")
    args = parser.parse_args()

    # Check if output is being redirected
    if not os.isatty(sys.stdout.fileno()):
        file_output = sys.stdout
    else:
        file_output = None
    
    client = LLMClient(args.server, args.debug, file_output)
    
    try:
        if args.input:
            input_text = " ".join(args.input)
            asyncio.get_event_loop().run_until_complete(client.process_input(input_text))
        else:
            asyncio.get_event_loop().run_until_complete(client.process_input())
    except KeyboardInterrupt:
        client.debug_print("\nStopping client...")

if __name__ == "__main__":
    main()
