if __name__ == "__main__":
    import json
    import logging
    import threading
    import asyncio
    from queue import Queue, Empty
    import websockets
    from xtts_rvc_synthesizer import XTTSRVCSynthesizer

    # Initialize parameters
    xtts_model = "models/xtts/Lasinya"
    xtts_voice = "Lasinya_Reference.json"
    rvc_model = "models/rvc/Lasinya"
    use_logging = True

    # Use thread-safe Queues for audio chunks and control messages
    audio_queue = Queue()
    control_queue = Queue()

    # Set to store audio WebSocket connections
    audio_connections = set()

    # Event to signal the threads to stop
    stop_event = threading.Event()

    class TTSThread(threading.Thread):
        def __init__(self):
            super().__init__()
            self.tts = None

        def run(self):
            self.tts = XTTSRVCSynthesizer(
                xtts_model=xtts_model,
                xtts_voice=xtts_voice,
                rvc_model=rvc_model,
                rvc_sample_rate=40000,
                use_logging=use_logging,
                on_audio_chunk=self.on_audio_chunk
            )
            while not stop_event.is_set():
                try:
                    data = control_queue.get(timeout=0.1)
                    if data["type"] == "text":
                        self.tts.push_text(data["content"])
                    elif data["type"] == "synthesize":
                        self.tts.synthesize()
                except Empty:
                    continue

        def on_audio_chunk(self, chunk):
            print("received chunk")
            audio_queue.put(chunk)

    async def process_audio_queue():
        while True:
            try:
                chunk = audio_queue.get_nowait()
                print("Processing chunk from queue")
                await broadcast_audio_chunk(chunk)
            except Empty:
                await asyncio.sleep(0.01)

    async def broadcast_audio_chunk(chunk):
        print("broadcast_audio_chunk was called")
        for conn in list(audio_connections):
            try:
                await conn.send(chunk)
            except websockets.exceptions.ConnectionClosed:
                audio_connections.remove(conn)

    async def control_handler(websocket, path):
        try:
            async for message in websocket:
                data = json.loads(message)
                control_queue.put(data)
                await websocket.send(json.dumps({"type": f"{data['type']}_received"}))
        except websockets.exceptions.ConnectionClosed:
            logging.info("Control WebSocket connection closed")

    async def audio_handler(websocket, path):
        try:
            audio_connections.add(websocket)
            await websocket.wait_closed()
        finally:
            audio_connections.remove(websocket)

    async def main():
        # Start the TTS thread
        tts_thread = TTSThread()
        tts_thread.start()

        # Start the audio processing task
        audio_task = asyncio.create_task(process_audio_queue())
        
        control_server = await websockets.serve(control_handler, "localhost", 8000)
        audio_server = await websockets.serve(audio_handler, "localhost", 8001)
        
        print("Server CONTROL listening on ws://localhost:8000")
        print("Server AUDIO listening on ws://localhost:8001")
        
        try:
            await asyncio.gather(control_server.wait_closed(), audio_server.wait_closed(), audio_task)
        finally:
            stop_event.set()
            tts_thread.join()

    logging.basicConfig(level=logging.DEBUG if use_logging else logging.WARNING)
    asyncio.run(main())