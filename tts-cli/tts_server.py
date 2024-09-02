import json
import logging
import threading
import asyncio
import argparse
from queue import Queue, Empty
import websockets
from xtts_rvc_synthesizer import XTTSRVCSynthesizer
from concurrent.futures import ThreadPoolExecutor

# Use thread-safe Queues for audio chunks and control messages
audio_queue = Queue()
control_queue = Queue()

# Set to store audio WebSocket connections
audio_connections = set()

# Event to signal the threads to stop
stop_event = threading.Event()

class TTSThread(threading.Thread):
    def __init__(self, xtts_model, xtts_voice, rvc_model, use_logging):
        super().__init__()
        self.xtts_model = xtts_model
        self.xtts_voice = xtts_voice
        self.rvc_model = rvc_model
        self.use_logging = use_logging
        self.tts = None
        self.rvc = True
        self.ready = threading.Event()
        self.logger = logging.getLogger('TTSThread')
        self.current_synthesis_task = None
        self.synthesis_executor = ThreadPoolExecutor(max_workers=1)

    def run(self):
        self.logger.info("Initializing TTS...")
        self.tts = XTTSRVCSynthesizer(
            xtts_model=self.xtts_model,
            xtts_voice=self.xtts_voice,
            rvc_model=self.rvc_model,
            rvc_sample_rate=40000,
            use_logging=self.use_logging,
            on_audio_chunk=self.on_audio_chunk
        )

        self.logger.info("TTS Server ready")
        print("TTS Server ready...")
        self.ready.set()  # Signal that TTS is ready
       
        while not stop_event.is_set():
            try:
                data = control_queue.get(timeout=0.1)
                self.logger.debug(f"Received control data: {data}")
                if data["type"] == "text":
                    if data["rvc"] and not self.rvc:
                        self.logger.info("Enabling RVC")
                        self.rvc = True
                        self.tts.enable_rvc(True)
                    elif not data["rvc"] and self.rvc:
                        self.logger.info("Disabling RVC")
                        self.rvc = False
                        self.tts.enable_rvc(False)

                    self.logger.info(f"Pushing text to TTS: {data['content'][:50]}")
                    self.tts.push_text(data["content"])
                elif data["type"] == "synthesize":
                    self.logger.info("Starting synthesis")
                    self.current_synthesis_task = self.synthesis_executor.submit(self.tts.synthesize)
                    # self.tts.synthesize()
                elif data["type"] == "cancel":
                    if self.current_synthesis_task:
                        self.current_synthesis_task.cancel()                    
                    self.logger.info("Cancelling synthesis")
                    self.tts.stop()
                    self.clear_audio_queue()
                elif data["type"] == "new_connection":
                    self.logger.info("New connection detected, stopping synthesis and clearing audio queue")
                    if self.current_synthesis_task:
                        self.current_synthesis_task.cancel()                    
                    self.tts.stop()
                    self.clear_audio_queue()                    
            except Empty:
                continue

    def stop(self):
        self.synthesis_executor.shutdown(wait=False)                

    def on_audio_chunk(self, chunk):
        self.logger.debug(f"Received audio chunk of size {len(chunk)}")
        audio_queue.put(chunk)

    def clear_audio_queue(self):
        self.logger.info("Clearing audio queue")
        # while not audio_queue.empty():
        while audio_queue.qsize() > 0:
            audio_queue.get_nowait()
        self.logger.info("Audio queue cleared after cancel")

async def process_audio_queue():
    logger = logging.getLogger('AudioProcessor')
    while True:
        try:
            chunk = audio_queue.get_nowait()
            logger.debug(f"Processing audio chunk of size {len(chunk)}")
            await broadcast_audio_chunk(chunk)
        except Empty:
            await asyncio.sleep(0.01)

async def broadcast_audio_chunk(chunk):
    logger = logging.getLogger('AudioBroadcaster')
    logger.debug(f"Broadcasting audio chunk to {len(audio_connections)} connections")
    for conn in list(audio_connections):
        try:
            await conn.send(chunk)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Removing closed connection {conn}")
            audio_connections.remove(conn)

async def control_handler(websocket, path):
    logger = logging.getLogger('ControlHandler')
    try:
        logger.info(f"New control connection from {websocket.remote_address}")
        # Signal new connection to stop synthesis and clear audio queue
        control_queue.put({"type": "new_connection"})
        async for message in websocket:
            data = json.loads(message)
            logger.debug(f"Received control message: {data}")
            control_queue.put(data)
            await websocket.send(json.dumps({"type": f"{data['type']}_received"}))
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Control WebSocket connection closed from {websocket.remote_address}")


# async def control_handler(websocket, path):
#     logger = logging.getLogger('ControlHandler')
#     try:
#         logger.info(f"New control connection from {websocket.remote_address}")
#         async for message in websocket:
#             data = json.loads(message)
#             logger.debug(f"Received control message: {data}")
#             control_queue.put(data)
#             await websocket.send(json.dumps({"type": f"{data['type']}_received"}))
#     except websockets.exceptions.ConnectionClosed:
#         logger.info(f"Control WebSocket connection closed from {websocket.remote_address}")

async def audio_handler(websocket, path):
    logger = logging.getLogger('AudioHandler')
    try:
        logger.info(f"New audio connection from {websocket.remote_address}")
        audio_connections.add(websocket)
        await websocket.wait_closed()
    finally:
        logger.info(f"Audio WebSocket connection closed from {websocket.remote_address}")
        audio_connections.remove(websocket)

async def main_async(args):
    logger = logging.getLogger('Main')
    logger.info("Starting TTS Server")

    # Start the TTS thread
    tts_thread = TTSThread(args.xtts_model, args.xtts_voice, args.rvc_model, args.use_logging)
    tts_thread.start()

    # Wait for TTS to be ready
    logger.info("Waiting for TTS to be ready")
    await asyncio.get_event_loop().run_in_executor(None, tts_thread.ready.wait)

    # Start the audio processing task
    logger.info("Starting audio processing task")
    audio_task = asyncio.create_task(process_audio_queue())

    logger.info(f"Starting control server on {args.host}:{args.control_port}")
    control_server = await websockets.serve(control_handler, args.host, args.control_port)
    
    logger.info(f"Starting audio server on {args.host}:{args.audio_port}")
    audio_server = await websockets.serve(audio_handler, args.host, args.audio_port)
    
    print(f"Server CONTROL listening on ws://{args.host}:{args.control_port}")
    print(f"Server AUDIO listening on ws://{args.host}:{args.audio_port}")
    
    try:
        await asyncio.gather(control_server.wait_closed(), audio_server.wait_closed(), audio_task)
    finally:
        logger.info("Shutting down TTS Server")
        stop_event.set()
        tts_thread.join()

def main():
    parser = argparse.ArgumentParser(description="TTS Server with WebSocket interface")
    parser.add_argument("--xtts-model", default="D:/Data/Models/xtts/v2.0.2", help="Path to XTTS model")
    parser.add_argument("--xtts-voice", default="vanessa.wav", help="XTTS voice file")
    parser.add_argument("--rvc-model", default="models/rvc/Lasinya", help="Path to RVC model")
    parser.add_argument("--host", default="localhost", help="Host to bind the server to")
    parser.add_argument("--control-port", type=int, default=8000, help="Port for control WebSocket")
    parser.add_argument("--audio-port", type=int, default=8001, help="Port for audio WebSocket")
    parser.add_argument("--use-logging", action="store_true", help="Enable detailed logging")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()