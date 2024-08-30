if __name__ == '__main__':
    print("Starting server, please wait...")

    from RealtimeSTT import AudioToTextRecorder
    import asyncio
    import websockets
    import threading
    import numpy as np
    from scipy.signal import resample
    import json

    recorder = None
    recorder_ready = threading.Event()
    client_websocket = None

    async def send_to_client(message):
        if client_websocket:
            await client_websocket.send(message)

    def text_detected(text):
        asyncio.new_event_loop().run_until_complete(
            send_to_client(
                json.dumps({
                    'type': 'realtime',
                    'text': text
                })
            )
        )
        print(f"\r{text}", flush=True, end='')

    recorder_config = {
        'spinner': False,
        'use_microphone': False,
        'model': 'large-v2',
        'language': 'en',
        'silero_sensitivity': 0.4,
        'webrtc_sensitivity': 3,
        'post_speech_silence_duration': 0.7,
        'min_length_of_recording': 0,
        'min_gap_between_recordings': 0,
        'enable_realtime_transcription': True,
        'realtime_processing_pause': 0,
        'realtime_model_type': 'medium.en',
        'on_realtime_transcription_stabilized': text_detected,
    }

    def recorder_thread():
        global recorder
        print("Initializing RealtimeSTT...")
        recorder = AudioToTextRecorder(**recorder_config)
        print("RealtimeSTT initialized")
        recorder_ready.set()
        while True:
            full_sentence = recorder.text()
            asyncio.new_event_loop().run_until_complete(
                send_to_client(
                    json.dumps({
                        'type': 'fullSentence',
                        'text': full_sentence
                    })
                )
            )
            print(f"\rSentence: {full_sentence}")

    def decode_and_resample(
            audio_data,
            original_sample_rate,
            target_sample_rate):

        # Decode 16-bit PCM data to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate the number of samples after resampling
        num_original_samples = len(audio_np)
        num_target_samples = int(num_original_samples * target_sample_rate /
                                 original_sample_rate)

        # Resample the audio
        resampled_audio = resample(audio_np, num_target_samples)

        return resampled_audio.astype(np.int16).tobytes()

    async def echo(websocket, path):
        print("Client connected")
        global client_websocket
        client_websocket = websocket
        async for message in websocket:

            if not recorder_ready.is_set():
                print("Recorder not ready")
                continue

            metadata_length = int.from_bytes(message[:4], byteorder='little')
            metadata_json = message[4:4+metadata_length].decode('utf-8')
            metadata = json.loads(metadata_json)
            sample_rate = metadata['sampleRate']
            chunk = message[4+metadata_length:]
            resampled_chunk = decode_and_resample(chunk, sample_rate, 16000)
            recorder.feed_audio(resampled_chunk)

    # start_server = websockets.serve(echo, "0.0.0.0", 9001)
    start_server = websockets.serve(echo, "localhost", 8011)

    recorder_thread = threading.Thread(target=recorder_thread)
    recorder_thread.start()
    recorder_ready.wait()

    print("Server started. Press Ctrl+C to stop the server.")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()




# WAIT_FOR_START_COMMAND = False

# if __name__ == '__main__':
#     server = "0.0.0.0"
#     port = 5025

#     print(f"STT speech to text server")
#     print(f"runs on http://{server}:{port}")
#     print()
#     print("starting")
#     print("└─ ... ", end='', flush=True)

#     from RealtimeSTT import AudioToTextRecorder
#     from colorama import Fore, Back, Style
#     import websockets
#     import threading
#     import colorama
#     import asyncio
#     import shutil
#     import queue
#     import json
#     import time
#     import os

#     colorama.init()

#     first_chunk = True
#     full_sentences = []
#     displayed_text = ""
#     message_queue = queue.Queue()
#     start_recording_event = threading.Event()
#     start_transcription_event = threading.Event()
#     connected_clients = set()

#     def clear_console():
#         os.system('clear' if os.name == 'posix' else 'cls')

#     async def handler(websocket, path):
#         print("\r└─ OK")
#         if WAIT_FOR_START_COMMAND:
#             print("waiting for start command")
#             print("└─ ... ", end='', flush=True)

#         connected_clients.add(websocket)

#         try:
#             while True:
#                 async for message in websocket:
#                     try:
#                         data = json.loads(message)
#                         if data.get("type") == "command" and data.get("content") == "start-recording":
#                             print("\r└─ OK")
#                             start_recording_event.set()
#                     except json.JSONDecodeError:
#                         # If it's not JSON, assume it's audio data
#                         await process_audio(message)
#         except websockets.ConnectionClosedError:
#             print(Fore.RED + "connection closed unexpectedly by the client" + Style.RESET_ALL)
#         except websockets.exceptions.ConnectionClosedOK:
#             print("connection closed.")
#         finally:
#             print("client disconnected")
#             connected_clients.remove(websocket)
#             print("waiting for clients")
#             print("└─ ... ", end='', flush=True)

#     def add_message_to_queue(type: str, content):
#         message = {
#             "type": type,
#             "content": content
#         }
#         message_queue.put(message)

#     def fill_cli_line(text):
#         columns, _ = shutil.get_terminal_size()
#         return text.ljust(columns)[-columns:]

#     def text_detected(text):
#         global displayed_text, first_chunk

#         if text != displayed_text:
#             first_chunk = False
#             displayed_text = text
#             add_message_to_queue("realtime", text)

#             message = fill_cli_line(text)

#             message = "└─ " + Fore.CYAN + message[:-3] + Style.RESET_ALL
#             print(f"\r{message}", end='', flush=True)

#     async def broadcast(message_obj):
#         if connected_clients:
#             for client in connected_clients:
#                 await client.send(json.dumps(message_obj))

#     async def send_handler():
#         while True:
#             while not message_queue.empty():
#                 message = message_queue.get()
#                 await broadcast(message)
#             await asyncio.sleep(0.02)

#     def recording_started():
#         add_message_to_queue("record_start", "")

#     def vad_detect_started():
#         add_message_to_queue("vad_start", "")

#     def wakeword_detect_started():
#         add_message_to_queue("wakeword_start", "")

#     def transcription_started():
#         add_message_to_queue("transcript_start", "")

#     recorder_config = {
#         'spinner': False,
#         'model': 'small.en',
#         'language': 'en',
#         'silero_sensitivity': 0.01,
#         'webrtc_sensitivity': 3,
#         'silero_use_onnx': False,
#         'post_speech_silence_duration': 1.2,
#         'min_length_of_recording': 0.2,
#         'min_gap_between_recordings': 0,
#         'enable_realtime_transcription': True,
#         'realtime_processing_pause': 0,
#         'realtime_model_type': 'tiny.en',
#         'on_realtime_transcription_stabilized': text_detected,
#         'on_recording_start': recording_started,
#         'on_vad_detect_start': vad_detect_started,
#         'on_wakeword_detection_start': wakeword_detect_started,
#         'on_transcription_start': transcription_started,
#     }

#     recorder = AudioToTextRecorder(**recorder_config)

#     async def process_audio(audio_data):
#         sentence = await asyncio.to_thread(recorder.transcribe, audio_data)
#         print(Style.RESET_ALL + "\r└─ " + Fore.YELLOW + sentence + Style.RESET_ALL)
#         add_message_to_queue("full", sentence)

#     def recorder_thread():
#         global first_chunk
#         while True:
#             if not len(connected_clients) > 0:
#                 time.sleep(0.1)
#                 continue
#             first_chunk = True
#             if WAIT_FOR_START_COMMAND:
#                 start_recording_event.wait()
#             print("waiting for sentence")
#             print("└─ ... ", end='', flush=True)
#             recorder.wait_audio()
#             start_transcription_event.set()
#             start_recording_event.clear()

#     threading.Thread(target=recorder_thread, daemon=True).start()

#     start_server = websockets.serve(handler, server, port)
#     loop = asyncio.get_event_loop()

#     print("\r└─ OK")
#     print("waiting for clients")
#     print("└─ ... ", end='', flush=True)

#     loop.run_until_complete(start_server)
#     loop.create_task(send_handler())
#     loop.run_forever()

# # import asyncio
# # import websockets
# # import json
# # from RealtimeSTT import AudioToTextRecorder
# # from colorama import Fore, Style
# # import colorama
# # import shutil
# # import queue
# # import os
# # import io

# # # Constants
# # SERVER = "0.0.0.0"
# # PORT = 5025
# # WAIT_FOR_START_COMMAND = False

# # # Global variables
# # connected_clients = set()
# # message_queue = queue.Queue()
# # start_recording_event = asyncio.Event()
# # colorama.init()

# # def clear_console():
# #     os.system('clear' if os.name == 'posix' else 'cls')

# # def fill_cli_line(text):
# #     columns, _ = shutil.get_terminal_size()
# #     return text.ljust(columns)[-columns:]

# # def add_message_to_queue(type: str, content):
# #     message = {
# #         "type": type,
# #         "content": content
# #     }
# #     message_queue.put(message)

# # def text_detected(text):
# #     add_message_to_queue("realtime", text)
# #     message = fill_cli_line(text)
# #     message = "└─ " + Fore.CYAN + message[:-3] + Style.RESET_ALL
# #     print(f"\r{message}", end='', flush=True)

# # def recording_started():
# #     add_message_to_queue("record_start", "")

# # def transcription_started():
# #     add_message_to_queue("transcript_start", "")

# # async def handler(websocket, path):
# #     print("\r└─ Client connected")
# #     if WAIT_FOR_START_COMMAND:
# #         print("Waiting for start command")
# #         print("└─ ... ", end='', flush=True)

# #     connected_clients.add(websocket)

# #     try:
# #         async for message in websocket:
# #             try:
# #                 data = json.loads(message)
# #                 if data.get("type") == "command" and data.get("content") == "start-recording":
# #                     print("\r└─ Starting recording")
# #                     start_recording_event.set()
# #             except json.JSONDecodeError:
# #                 # If it's not JSON, assume it's audio data
# #                 audio_data = message
# #                 # Process the audio data here (e.g., pass it to the transcriber)
# #                 # For now, we'll just print the length of the data
# #                 print(f"Received audio data: {len(audio_data)} bytes")

# #     except websockets.ConnectionClosedError:
# #         print(Fore.RED + "Connection closed unexpectedly by the client" + Style.RESET_ALL)
# #     except websockets.exceptions.ConnectionClosedOK:
# #         print("Connection closed.")
# #     finally:
# #         print("Client disconnected")
# #         connected_clients.remove(websocket)
# #         print("Waiting for clients")
# #         print("└─ ... ", end='', flush=True)

# # async def broadcast(message_obj):
# #     if connected_clients:
# #         await asyncio.gather(*[client.send(json.dumps(message_obj)) for client in connected_clients])

# # async def send_handler():
# #     while True:
# #         while not message_queue.empty():
# #             message = message_queue.get()
# #             await broadcast(message)
# #         await asyncio.sleep(0.02)

# # class AudioBuffer(io.BytesIO):
# #     def __init__(self):
# #         super().__init__()
# #         self.audio_data = b''

# #     def write(self, data):
# #         self.audio_data += data

# #     def read(self, size=-1):
# #         if size == -1:
# #             ret = self.audio_data
# #             self.audio_data = b''
# #         else:
# #             ret = self.audio_data[:size]
# #             self.audio_data = self.audio_data[size:]
# #         return ret

# #     def readable(self):
# #         return True

# # async def transcriber_task(recorder):
# #     audio_buffer = AudioBuffer()
# #     while True:
# #         await start_recording_event.wait()
# #         text = "└─ Transcribing ... "
# #         text = fill_cli_line(text)
# #         print(f"\r{text}", end='', flush=True)
        
# #         # Pass the audio buffer to the transcribe method
# #         sentence = await asyncio.to_thread(recorder.transcribe, audio_buffer)
        
# #         print(Style.RESET_ALL + "\r└─ " + Fore.YELLOW + sentence + Style.RESET_ALL)
# #         add_message_to_queue("full", sentence)
# #         start_recording_event.clear()
# #         if WAIT_FOR_START_COMMAND:
# #             print("Waiting for start command")
# #             print("└─ ... ", end='', flush=True)

# # async def main():
# #     recorder_config = {
# #         'spinner': False,
# #         'model': 'small.en',
# #         'language': 'en',
# #         'silero_sensitivity': 0.01,
# #         'webrtc_sensitivity': 3,
# #         'silero_use_onnx': False,
# #         'post_speech_silence_duration': 1.2,
# #         'min_length_of_recording': 0.2,
# #         'min_gap_between_recordings': 0,
# #         'enable_realtime_transcription': True,
# #         'realtime_processing_pause': 0,
# #         'realtime_model_type': 'tiny.en',
# #         'on_realtime_transcription_stabilized': text_detected,
# #         'on_recording_start': recording_started,
# #         'on_transcription_start': transcription_started,
# #     }

# #     recorder = AudioToTextRecorder(**recorder_config)

# #     server = await websockets.serve(handler, SERVER, PORT)
# #     print(f"STT WebSocket server running on ws://{SERVER}:{PORT}")
# #     print("Waiting for clients")
# #     print("└─ ... ", end='', flush=True)

# #     await asyncio.gather(
# #         server.wait_closed(),
# #         send_handler(),
# #         transcriber_task(recorder)
# #     )

# # if __name__ == '__main__':
# #     asyncio.run(main())

# # import asyncio
# # import websockets
# # import json
# # from RealtimeSTT import AudioToTextRecorder
# # from colorama import Fore, Style
# # import colorama
# # import shutil
# # import queue
# # import os

# # # Constants
# # SERVER = "0.0.0.0"
# # PORT = 5025
# # WAIT_FOR_START_COMMAND = False

# # # Global variables
# # connected_clients = set()
# # message_queue = queue.Queue()
# # start_recording_event = asyncio.Event()
# # colorama.init()

# # def clear_console():
# #     os.system('clear' if os.name == 'posix' else 'cls')

# # def fill_cli_line(text):
# #     columns, _ = shutil.get_terminal_size()
# #     return text.ljust(columns)[-columns:]

# # def add_message_to_queue(type: str, content):
# #     message = {
# #         "type": type,
# #         "content": content
# #     }
# #     message_queue.put(message)

# # def text_detected(text):
# #     add_message_to_queue("realtime", text)
# #     message = fill_cli_line(text)
# #     message = "└─ " + Fore.CYAN + message[:-3] + Style.RESET_ALL
# #     print(f"\r{message}", end='', flush=True)

# # def recording_started():
# #     add_message_to_queue("record_start", "")

# # def transcription_started():
# #     add_message_to_queue("transcript_start", "")

# # async def handler(websocket, path):
# #     print("\r└─ Client connected")
# #     if WAIT_FOR_START_COMMAND:
# #         print("Waiting for start command")
# #         print("└─ ... ", end='', flush=True)

# #     connected_clients.add(websocket)

# #     try:
# #         async for message in websocket:
# #             data = json.loads(message)
# #             if data.get("type") == "command" and data.get("content") == "start-recording":
# #                 print("\r└─ Starting recording")
# #                 start_recording_event.set()

# #     except json.JSONDecodeError:
# #         print(Fore.RED + "Received an invalid JSON message." + Style.RESET_ALL)
# #     except websockets.ConnectionClosedError:
# #         print(Fore.RED + "Connection closed unexpectedly by the client" + Style.RESET_ALL)
# #     except websockets.exceptions.ConnectionClosedOK:
# #         print("Connection closed.")
# #     finally:
# #         print("Client disconnected")
# #         connected_clients.remove(websocket)
# #         print("Waiting for clients")
# #         print("└─ ... ", end='', flush=True)

# # async def broadcast(message_obj):
# #     if connected_clients:
# #         await asyncio.gather(*[client.send(json.dumps(message_obj)) for client in connected_clients])

# # async def send_handler():
# #     while True:
# #         while not message_queue.empty():
# #             message = message_queue.get()
# #             await broadcast(message)
# #         await asyncio.sleep(0.02)

# # async def transcriber_task(recorder):
# #     while True:
# #         await start_recording_event.wait()
# #         text = "└─ Transcribing ... "
# #         text = fill_cli_line(text)
# #         print(f"\r{text}", end='', flush=True)
# #         sentence = await asyncio.to_thread(recorder.transcribe)
# #         print(Style.RESET_ALL + "\r└─ " + Fore.YELLOW + sentence + Style.RESET_ALL)
# #         add_message_to_queue("full", sentence)
# #         start_recording_event.clear()
# #         if WAIT_FOR_START_COMMAND:
# #             print("Waiting for start command")
# #             print("└─ ... ", end='', flush=True)

# # async def main():
# #     recorder_config = {
# #         'spinner': False,
# #         'model': 'small.en',
# #         'language': 'en',
# #         'silero_sensitivity': 0.01,
# #         'webrtc_sensitivity': 3,
# #         'silero_use_onnx': False,
# #         'post_speech_silence_duration': 1.2,
# #         'min_length_of_recording': 0.2,
# #         'min_gap_between_recordings': 0,
# #         'enable_realtime_transcription': True,
# #         'realtime_processing_pause': 0,
# #         'realtime_model_type': 'tiny.en',
# #         'on_realtime_transcription_stabilized': text_detected,
# #         'on_recording_start': recording_started,
# #         'on_transcription_start': transcription_started,
# #     }

# #     recorder = AudioToTextRecorder(**recorder_config)

# #     server = await websockets.serve(handler, SERVER, PORT)
# #     print(f"STT WebSocket server running on ws://{SERVER}:{PORT}")
# #     print("Waiting for clients")
# #     print("└─ ... ", end='', flush=True)

# #     await asyncio.gather(
# #         server.wait_closed(),
# #         send_handler(),
# #         transcriber_task(recorder)
# #     )

# # if __name__ == '__main__':
# #     asyncio.run(main())


# # from fastapi import FastAPI, Request
# # from fastapi.responses import JSONResponse
# # import wave
# # import time
# # from contextlib import asynccontextmanager

# # WAVE_OUTPUT_FILENAME = "recorded_audio.wav"
# # CHANNELS = 1
# # SAMPLE_WIDTH = 2  # 16-bit audio
# # FRAME_RATE = 16000
# # RECORD_SECONDS = 3
# # CHUNK_SIZE = 2048  # 1024 samples * 2 bytes per sample

# # wf = None
# # start_time = None
# # chunk_count = 0

# # @asynccontextmanager
# # async def lifespan(app: FastAPI):
# #     # Startup
# #     yield
# #     # Shutdown
# #     global wf
# #     if wf:
# #         wf.close()
# #     print(f"Server shutting down. Audio saved to {WAVE_OUTPUT_FILENAME}")

# # app = FastAPI(lifespan=lifespan)

# # @app.post("/audio")
# # async def receive_audio(request: Request):
# #     global start_time, chunk_count, wf
    
# #     if start_time is None:
# #         start_time = time.time()
# #         wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
# #         wf.setnchannels(CHANNELS)
# #         wf.setsampwidth(SAMPLE_WIDTH)
# #         wf.setframerate(FRAME_RATE)

# #     chunk_count += 1
# #     chunk = await request.body()
# #     chunk_size = len(chunk)
# #     print(f"Received chunk {chunk_count} with length {chunk_size} bytes")
    
# #     if chunk_size != CHUNK_SIZE:
# #         print(f"Warning: Expected chunk size {CHUNK_SIZE}, but received {chunk_size}")
    
# #     # Write the chunk to the wave file
# #     wf.writeframes(chunk)
    
# #     elapsed_time = time.time() - start_time
# #     if elapsed_time >= RECORD_SECONDS:
# #         wf.close()
# #         print(f"Audio saved to {WAVE_OUTPUT_FILENAME}")
# #         start_time = None
# #         chunk_count = 0
# #         wf = None
# #         return JSONResponse(content={"command": "stop"})
    
# #     return JSONResponse(content={"status": "ok"})

# # if __name__ == "__main__":
# #     import uvicorn
# #     uvicorn.run(app, host="0.0.0.0", port=8000)