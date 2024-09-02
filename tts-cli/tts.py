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
import wave
import io
import numpy as np
import socket
import subprocess


class TTSClient:
    def __init__(self, debug=False, file_output=None, control_url="ws://localhost:8000", audio_url="ws://localhost:8001", rvc=False):
        self.debug = debug
        self.file_output = file_output
        self.running = True
        self.control_url = control_url
        self.audio_url = audio_url
        self.rvc = rvc        
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
        self.first_chunk_timeout = 6  # seconds
        self.overall_timeout = 30  # seconds
        self.receive_task = None
        self.start_time = None
        self.stream = None
        self.stream_active = False
        self.first_chunk_received = False
        self.cancellation_sent = False
        self.wav_buffer = io.BytesIO()
        self.wav_writer = None
        self.control_port = int(control_url.split(':')[-1])
        self.audio_port = int(audio_url.split(':')[-1])

    async def ensure_server_running(self):
        if not self.is_server_running(self.control_port) or not self.is_server_running(self.audio_port):
            self.debug_print("TTS server is not running.", True)
            if self.ask_to_start_server():
                self.start_server()
                self.debug_print("Waiting for TTS server to start...", True)
                for _ in range(30):  # Wait up to 30 seconds
                    if self.is_server_running(self.control_port) and self.is_server_running(self.audio_port):
                        self.debug_print("TTS server started successfully.", True)
                        return True
                    await asyncio.sleep(1)
                self.debug_print("Failed to start TTS server.", True)
                return False
            else:
                self.debug_print("TTS server is required. Please start it manually.", True)
                return False
        return True

    def is_server_running(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def ask_to_start_server(self):
        response = input("Would you like to start the TTS server now? (y/n): ").strip().lower()
        return response == 'y' or response == 'yes'

    def start_server(self):
        if os.name == 'nt':  # Windows
            subprocess.Popen('start /min cmd /c tts-server', shell=True)
        else:  # Unix-like systems
            subprocess.Popen(['tts-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.debug_print("TTS server start command issued. Please wait a moment for it to initialize.")


    def log(self, message, force=False):
        """Write log messages to stderr."""
        if self.debug or force:
            print(message, file=sys.stderr)

    def initialize_stream(self):
        if self.stream is None or not self.stream.is_active():
            # Determine the parameters based on the value of rvc
            format_type = pyaudio.paFloat32 if self.rvc else pyaudio.paInt16
            rate = 40000 if self.rvc else 24000
            
            # Open the audio stream
            self.stream = self.p.open(format=format_type,
                                    channels=1,
                                    rate=rate,
                                    output=True)

            # If file output is enabled, configure the WAV writer
            if self.file_output:
                self.wav_writer = wave.open(self.wav_buffer, 'wb')
                self.wav_writer.setnchannels(1)
                self.wav_writer.setsampwidth(2)
                self.wav_writer.setframerate(rate)
                # self.wav_writer.setcomptype('NONE', 'Not Compressed')

            self.stream_active = True            

    async def send_cancellation(self):
        if self.control_websocket and not self.cancellation_sent:
            try:
                await self.control_websocket.send(json.dumps({"type": "cancel"}))
                self.cancellation_sent = True
                self.debug_print("Cancellation message sent to server")
            except:
                self.debug_print("Failed to send cancellation message")

    async def process_input(self):
        self.debug_print("Starting to process input")
        if sys.stdin.isatty():
            while self.running:
                try:
                    self.debug_print("line")
                    line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                    if not line:
                        break
                    await self.handle_text(line)
                except Exception as e:
                    self.debug_print(f"Error processing input: {e}")
                    break
        else:
            while self.running:
                try:
                    self.debug_print("chunk")
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
        text = text.rstrip('\n')  # Remove trailing newlines        
        #text = text.rstrip(' ')  # Remove trailing newlines        
        print(f"{text}", end='', flush=True, file=sys.stderr)
        # if not self.file_output:
        #     print(f"{text}", end="", flush=True)
        self.debug_print(f"Processed text: {text}")
        
        # Send the text to the TTS server immediately
        if self.control_websocket:
            await self.control_websocket.send(json.dumps({
                "type": "text", 
                "content": text,
                "rvc": self.rvc
            }))
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

    def float32_to_int16(self, float_audio):
        float_audio = np.clip(float_audio, -1.0, 1.0)
        int16_audio = np.int16(float_audio * 32767)
        return int16_audio.tobytes()

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
                    if self.wav_writer:
                        if self.rvc:
                            chunk = self.float32_to_int16(
                                 np.frombuffer(chunk, dtype=np.float32))

                        self.wav_writer.writeframes(chunk)
                        self.debug_print(f"Wrote {len(chunk)} bytes to WAV")

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
            self.debug_print("Starting receive_audio task")
            await self.receive_task
        except asyncio.CancelledError:
            self.debug_print("Receive audio task was cancelled in receive_audio method")
        except Exception as e:
            self.debug_print(f"Exception in receive_audio method: {type(e).__name__}: {str(e)}")
        finally:
            self.debug_print("Exiting receive_audio method")
    
    async def _receive_audio_loop(self):
        self.debug_print("Starting audio reception loop")
        try:
            while True:
                try:
                    timeout = self.first_chunk_timeout if not self.first_chunk_received else self.synthesis_timeout
                    self.debug_print(f"Waiting for audio message with timeout: {timeout}")
                    message = await asyncio.wait_for(self.audio_websocket.recv(), timeout=timeout)                    
                    self.debug_print(f"Received message of type: {type(message)}")
                    if isinstance(message, bytes):
                        self.debug_print(f"Received audio chunk of size: {len(message)}")
                        if not self.first_chunk_received:
                            self.first_chunk_received = True
                        await self.audio_queue.put(message)
                    elif isinstance(message, str):
                        data = json.loads(message)
                        self.debug_print(f"Received JSON message: {data}")
                        if data.get("type") == "synthesis_complete":
                            self.debug_print("Received synthesis_complete message")
                            self.synthesis_complete.set()
                            await self.audio_queue.put("AUDIO_COMPLETE")
                            break
                except asyncio.TimeoutError:
                    self.debug_print(f"Timeout occurred while waiting for message")
                    if not self.first_chunk_received:
                        self.debug_print(f"No message received for {self.first_chunk_timeout} seconds on first chunk. Assuming synthesis is complete.")
                    else:
                        self.debug_print(f"No message received for {self.synthesis_timeout} seconds. Assuming synthesis is complete.")
                    break
                except websockets.exceptions.ConnectionClosed as e:
                    self.debug_print(f"Audio WebSocket connection closed: {e}")
                    break
                except Exception as e:
                    self.debug_print(f"Unknown exception in _receive_audio_loop: {type(e).__name__}: {str(e)}")
                    break
        except asyncio.CancelledError:
            self.debug_print("_receive_audio_loop task was cancelled")
        except Exception as e:
            self.debug_print(f"Unexpected exception in _receive_audio_loop outer try block: {type(e).__name__}: {str(e)}")
        finally:
            if not self.synthesis_complete.is_set():
                self.debug_print("Synthesis complete (inferred from loop exit)")
                self.synthesis_complete.set()
            await self.audio_queue.put("AUDIO_COMPLETE")
            self.debug_print("Exiting _receive_audio_loop")

    def debug_print(self, message, force=False):
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        log_message = f"DEBUG [{elapsed_time:.2f}s]: {message}"
        self.log(message, force)

    async def run(self, input_text):
        self.debug_print("TTS Client connecting to server...")
        self.start_time = time.time()
        # if not await self.ensure_server_running():
        #     self.debug_print("Cannot start TTS server. Exiting.")
        #     return
        try:
            async with websockets.connect(self.control_url) as control_websocket, \
                    websockets.connect(self.audio_url) as audio_websocket:
                self.control_websocket = control_websocket
                self.audio_websocket = audio_websocket
                self.debug_print("TTS Client connected")

                tasks = [
                    asyncio.create_task(self.receive_audio()),
                    asyncio.create_task(self.play_audio()),
                    asyncio.create_task(self.wait_for_shutdown())
                ]
                self.debug_print(f"Created {len(tasks)} tasks")

                if input_text:
                    await self.handle_text(input_text)
                    await self.handle_end_of_input()
                elif not sys.stdin.isatty():
                    await self.process_input()
                else:
                    tasks.append(asyncio.create_task(self.process_input()))

                try:
                    self.debug_print("Waiting for tasks to complete")
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    self.debug_print(f"{len(done)} tasks completed, {len(pending)} tasks pending")
                    for task in done:
                        if task.exception():
                            self.debug_print(f"Task raised an exception: {task.exception()}")
                except asyncio.CancelledError:
                    self.debug_print("Main task cancelled")
                finally:
                    self.debug_print("Cancelling remaining tasks")
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.debug_print(f"Error in run: {e}")
        finally:
            if self.wav_writer:
                self.debug_print("Closing wav_writer")
                self.wav_writer.close()
                self.wav_writer = None
            
            # Write WAV data to stdout
            if not sys.stdout.isatty():
                wav_data = self.wav_buffer.getvalue()
                self.debug_print(f"Writing {len(wav_data)} bytes of WAV data to stdout")
                sys.stdout.buffer.write(wav_data)
                sys.stdout.buffer.flush()
            
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
        await self.send_cancellation()
        
        if self.receive_task:
            self.receive_task.cancel()
        
        self.close_audio_stream()
        
        if self.control_websocket:
            await self.control_websocket.close()
        if self.audio_websocket:
            await self.audio_websocket.close()
        self.debug_print("TTS Client stopped")


async def main_async():
    parser = argparse.ArgumentParser(description="TTS Client")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--debugclean", action="store_true", help="Enable debug mode")
    parser.add_argument("--control-server", default="ws://localhost:8000", help="Control WebSocket server URL")
    parser.add_argument("--audio-server", default="ws://localhost:8001", help="Audio WebSocket server URL")
    parser.add_argument("--rvc", action="store_true", help="Use RVC audio settings")    
    parser.add_argument("input", nargs="*", help="Input text (optional)")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    # Check if no arguments were provided and no input is being piped
    if len(sys.argv) == 1 and sys.stdin.isatty():
        return  # Exit the function immediately

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

    client = TTSClient(args.debug or args.debugclean, file_output, args.control_server, args.audio_server, args.rvc)
    
    if not await client.ensure_server_running():
        logging.info("Exiting due to server not running.")
        return  # Exit immediately if the server is not running and user chose not to start it

    loop = asyncio.get_running_loop()

    def signal_handler(sig, frame):
        loop.create_task(client.stop())

    if sys.platform.startswith('win'):
        # On Windows, use signal.signal
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        # On Unix-based systems, use loop.add_signal_handler
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s, None))

    try:
        await client.run(input_text)
    except KeyboardInterrupt:
        logging.info("\nStopping client...")
    except Exception as e:
        logging.exception("An unexpected error occurred")
    finally:
        try:
        # Wait for all processes to complete
            await asyncio.wait_for(
                asyncio.gather(
                    client.input_complete.wait(),
                    client.synthesis_complete.wait(),
                    client.playback_complete.wait(),
                    client.shutdown_event.wait(),
                    return_exceptions=True
                ),
                timeout=10
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
