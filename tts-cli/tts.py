import argparse
import asyncio
import sys
import os
import websockets
import signal
import pyaudio
import json
import logging
import time

class TTSClient:
    def __init__(self, debug=False, file_output=None, control_url="ws://localhost:8000", audio_url="ws://localhost:8001"):
        self.debug = debug
        self.file_output = file_output
        self.running = True
        self.control_url = control_url
        self.audio_url = audio_url
        self.control_websocket = None
        self.audio_websocket = None
        self.audio_queue = asyncio.Queue()
        self.p = pyaudio.PyAudio()
        self.audio_complete = False
        self.input_complete = asyncio.Event()
        self.synthesis_complete = asyncio.Event()
        self.playback_complete = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.synthesis_timeout = 1  # seconds
        self.first_chunk_timeout = 7  # seconds
        self.overall_timeout = 30  # seconds
        self.receive_task = None
        self.start_time = None
        self.stream = None
        self.stream_active = False
        self.first_chunk_received = False

    def initialize_stream(self):
        if self.stream is None or not self.stream.is_active():
            self.stream = self.p.open(format=pyaudio.paFloat32,
                                      channels=1,
                                      rate=40000,
                                      output=True)
            self.stream_active = True

    async def process_input(self):
        self.debug_print("Starting to process input")
        if sys.stdin.isatty():
            # Interactive mode
            while self.running:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                    print(f"line: {line}")
                    if not line:
                        break
                    await self.handle_text(line)
                except Exception as e:
                    self.debug_print(f"Error processing input: {e}")
                    break
        else:
            while self.running:
                try:
                    chunk = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.read, 20)
                    if not chunk:
                        break
                    await self.handle_text(chunk)
                except Exception as e:
                    self.debug_print(f"Error processing input: {e}")
                    break            
        
        self.debug_print("Finished processing input")
        await self.handle_end_of_input()

    async def handle_text(self, text):
        if self.file_output:
            print(text, end="", flush=True, file=self.file_output)
        else:
            print(f"{text}", end="", flush=True)
        self.debug_print(f"Processed text: {text}")
        
        # Send the text to the TTS server immediately
        if self.control_websocket:
            await self.control_websocket.send(json.dumps({"type": "text", "content": text}))
            self.debug_print("Sent text to server, waiting for response...")
            response = await self.control_websocket.recv()
            self.debug_print(f"Server response: {response}")

    async def handle_end_of_input(self):
        self.debug_print("Handling end of input")
        await self.trigger_synthesis()
        self.input_complete.set()

    async def trigger_synthesis(self):
        if self.control_websocket:
            self.debug_print("Triggering synthesis...")
            await self.control_websocket.send(json.dumps({"type": "synthesize"}))
            self.debug_print("Synthesis triggered, waiting for audio...")


    async def play_audio(self):
        self.initialize_stream()
        while self.running:
            try:
                if self.audio_queue.empty() and self.audio_complete:
                    self.debug_print("No more audio chunks to play")
                    break

                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                if isinstance(chunk, str) and chunk == "AUDIO_COMPLETE":
                    self.debug_print("Received AUDIO_COMPLETE signal")
                    self.audio_complete = True
                    continue
                
                if self.stream_active:
                    self.stream.write(chunk)
            except asyncio.TimeoutError:
                if self.synthesis_complete.is_set():
                    self.debug_print("Synthesis complete, but no more audio chunks. Ending playback.")
                    break
                continue
        
        self.close_audio_stream()
        self.debug_print("Finished playing audio")
        self.playback_complete.set()
        await self.initiate_shutdown()

    def close_audio_stream(self):
        if self.stream_active:
            self.debug_print("Closing audio stream")
            self.stream.stop_stream()
            self.stream.close()
            self.stream_active = False
        self.p.terminate()

    async def initiate_shutdown(self):
        self.debug_print("Initiating shutdown")
        self.running = False
        self.shutdown_event.set()

    async def receive_audio(self):
        self.receive_task = asyncio.create_task(self._receive_audio_loop())
        try:
            await self.receive_task
        except asyncio.CancelledError:
            self.debug_print("Receive audio task was cancelled")

    async def _receive_audio_loop(self):
        self.debug_print("Starting audio reception loop")
        try:
            while True:
                try:
                    self.debug_print("Waiting for audio message...")
                    timeout = self.first_chunk_timeout if not self.first_chunk_received else self.synthesis_timeout
                    message = await asyncio.wait_for(self.audio_websocket.recv(), timeout=timeout)                    
                    self.debug_print(f"Received message type: {type(message)}")
                    if isinstance(message, bytes):
                        self.debug_print(f"Received audio chunk of size: {len(message)}")
                        await self.audio_queue.put(message)
                        if not self.first_chunk_received:
                            self.first_chunk_received = True
                    elif isinstance(message, str):
                        data = json.loads(message)
                        self.debug_print(f"Received JSON message: {data}")
                        if data.get("type") == "synthesis_complete":
                            self.debug_print("Received synthesis_complete message")
                            self.synthesis_complete.set()
                            await self.audio_queue.put("AUDIO_COMPLETE")
                            break
                except asyncio.TimeoutError:
                    if not self.first_chunk_received:
                        self.debug_print(f"No message received for {self.first_chunk_timeout} seconds on first chunk. Assuming synthesis is complete.")
                    else:
                        self.debug_print(f"No message received for {self.synthesis_timeout} seconds. Assuming synthesis is complete.")
                    break
                except websockets.exceptions.ConnectionClosed:
                    self.debug_print("Audio WebSocket connection closed")
                    break
        finally:
            if not self.synthesis_complete.is_set():
                self.debug_print("Synthesis complete (inferred from connection close or timeout)")
                self.synthesis_complete.set()
            await self.audio_queue.put("AUDIO_COMPLETE")

    def debug_print(self, message):
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        logging.debug(f"[{elapsed_time:.2f}s] {message}")
        if self.debug:
            print(f"DEBUG [{elapsed_time:.2f}s]: {message}", flush=True)

    async def run(self, input_text):
        self.debug_print("TTS Client connecting to server...")
        self.start_time = time.time()
        try:
            async with websockets.connect(self.control_url) as control_websocket, \
                       websockets.connect(self.audio_url) as audio_websocket:
                self.control_websocket = control_websocket
                self.audio_websocket = audio_websocket
                self.debug_print("TTS Client connected")

                if input_text:
                    await self.handle_text(input_text)
                    await self.handle_end_of_input()

                    await asyncio.wait_for(
                        asyncio.gather(
                            self.receive_audio(),
                            self.play_audio(),
                            self.wait_for_shutdown(),
                            return_exceptions=True
                        ),
                        timeout=self.overall_timeout
                    )

                else:
                    await asyncio.wait_for(
                        asyncio.gather(
                            self.process_input(),
                            self.receive_audio(),
                            self.play_audio(),
                            self.wait_for_shutdown(),
                            return_exceptions=True
                        ),
                        timeout=self.overall_timeout
                    )
        except asyncio.TimeoutError:
            self.debug_print(f"Operation timed out after {self.overall_timeout} seconds")
        except Exception as e:
            self.debug_print(f"Error connecting to server: {e}")
        finally:
            await self.stop()

    async def wait_for_shutdown(self):
        await self.shutdown_event.wait()
        self.debug_print("Shutdown signal received, closing connections")
        if self.control_websocket:
            await self.control_websocket.close()
        if self.audio_websocket:
            await self.audio_websocket.close()

    async def stop(self):
        self.debug_print("Stopping TTS Client")
        self.running = False
        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
        
        self.close_audio_stream()
        
        if self.control_websocket:
            await self.control_websocket.close()
        if self.audio_websocket:
            await self.audio_websocket.close()
        self.debug_print("TTS Client stopped")


async def main_async():
    parser = argparse.ArgumentParser(description="TTS Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--control-server", default="ws://localhost:8000", help="Control WebSocket server URL")
    parser.add_argument("--audio-server", default="ws://localhost:8001", help="Audio WebSocket server URL")
    parser.add_argument("input", nargs="*", help="Input text (optional)")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    if args.debug:
        websockets_logger = logging.getLogger('websockets')
        websockets_logger.setLevel(logging.DEBUG)
        websockets_logger.addHandler(logging.StreamHandler())
        
        asyncio_logger = logging.getLogger('asyncio')
        asyncio_logger.setLevel(logging.DEBUG)
        asyncio_logger.addHandler(logging.StreamHandler())

    # Check if output is being redirected
    if not os.isatty(sys.stdout.fileno()):
        file_output = sys.stdout
    else:
        file_output = None

    input_text = None
    if args.input:
        input_text = " ".join(args.input)

    client = TTSClient(args.debug, file_output, args.control_server, args.audio_server)
    
    try:
        await client.run(input_text)
    except KeyboardInterrupt:
        logging.info("\nStopping client...")
    except Exception as e:
        logging.exception("An unexpected error occurred")
    finally:
        # Wait for all processes to complete
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    client.input_complete.wait(),
                    client.synthesis_complete.wait(),
                    client.playback_complete.wait(),
                    client.shutdown_event.wait()
                ),
                timeout=10  # Wait for a maximum of 10 seconds
            )
        except asyncio.TimeoutError:
            logging.warning("Timed out waiting for client to complete all processes")
        
        # Ensure the client is fully stopped
        await client.stop()

    logging.debug("Main async function completed")

def main():
    if sys.platform.startswith('win'):
        # On Windows, use ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    loop = asyncio.get_event_loop()
    main_task = asyncio.ensure_future(main_async())

    def signal_handler(sig, frame):
        logging.info(f"Received exit signal {sig}, cancelling tasks...")
        main_task.cancel()

    if sys.platform.startswith('win'):
        # On Windows, use signal.signal directly
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        # On Unix-based systems, use loop.add_signal_handler
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s, None))

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        logging.debug("Closing event loop...")
        pending = asyncio.all_tasks(loop=loop)
        for task in pending:
            task.cancel()
        group = asyncio.gather(*pending, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()
        logging.debug("Event loop closed")

if __name__ == "__main__":
    main()
