from RealtimeTTS import TextToAudioStream, CoquiEngine
from rvc.realtimervc import RealtimeRVC
from bufferstream import BufferStream
from pathlib import Path
import logging
import time
import os
import pyaudio
import numpy as np
import queue
import threading

class XTTSRVCSynthesizer:
    def __init__(
        self,
        xtts_model: str = None,
        xtts_voice: str = None,
        rvc_model: str = None,
        rvc_sample_rate: int = 40000,
        use_logging=False,
        on_audio_chunk = None):
        """
        Initializes the realtime RVC synthesizer.

        Args:
            xtts_model (str): Path to the folder containing the xtts files
                (model.pth, config.json, vocab.json, speakers_xtts.pth)
            xtts_voice (str): Path to the file with the ~5-10 second mono 22050 Hz
                referecence voice wave file 
            rvc_model (str): Path to the .pth file with the rvc reference.
                The .index file should be in the same folder and have the same 
                name like this .pth file it belongs to.
            rvc_sample_rate (int): Mostly 40000 or 48000. The sample rate
                the rvc model was trained against.
            use_logging (bool): Usage of extended debug logging.
        """        

        level = logging.DEBUG if use_logging else logging.WARNING
        # logging.basicConfig(level=level)

        self.xtts_model_loaded = False
        self.buffer = BufferStream()
        self.use_logging = use_logging
        self.xtts_voice = xtts_voice
        self.engine = None
        self.rvc_sample_rate = rvc_sample_rate
        self.on_chunk = on_audio_chunk

        if self.use_logging:
            print("Extended logging")

        self.rvc = None
        if rvc_model is not None:
            self.load_rvc_model(rvc_model, rvc_sample_rate)

        if self.use_logging:
            print("Loading XTTS model")
        self.load_xtts_model(xtts_model)

        # Initialize PyAudio
        self.pyaudio_instance = None
        self.audio_stream = None
        self.audio_queue = queue.Queue()
        self.playback_thread = None
        self.stop_playback = threading.Event()

        if not self.on_chunk:
            self.pyaudio_instance = pyaudio.PyAudio()

    def push_text(self, text: str):
        self.buffer.add(text)
        if not self.xtts_model_loaded:
            self.load_xtts_model()
        
        self.ensure_playing()
        
        
    def ensure_playing(self):
        def on_audio_chunk(chunk):
            _, _, sample_rate = self.engine.get_stream_info()
            if self.rvc is not None:
                self.rvc.feed(chunk, sample_rate)

        if not self.stream.is_playing():
            self.stream.feed(self.buffer.gen())
            play_params = {
                "fast_sentence_fragment": True,
                "log_synthesized_text": True,
                "minimum_sentence_length": 10,
                "minimum_first_fragment_length": 10,
                "context_size": 4,
                "sentence_fragment_delimiters": ".?!;:,\n()[]{}。-""„—…/|《》¡¿\"",
                "force_first_fragment_after_words": 9999999,
                "on_audio_chunk": on_audio_chunk,
                "muted": True
            }

            self.stream.play_async(**play_params)

        if not self.playback_thread or not self.playback_thread.is_alive():
            self.start_playback_thread()

    def start_playback_thread(self):
        self.stop_playback.clear()
        self.playback_thread = threading.Thread(target=self.playback_worker)
        self.playback_thread.start()

    def playback_worker(self):
        while not self.stop_playback.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                self.play_audio(chunk)
            except queue.Empty:
                continue

    def play_audio(self, audio_chunk):
        if self.on_chunk:
            print("Callback CHUNK")
            self.on_chunk(audio_chunk)
            return

        if self.audio_queue.qsize() == 0:
            print("====FINISHED====")

        if self.audio_stream is None:
                self.audio_stream = self.pyaudio_instance.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.rvc_sample_rate,
                    output=True
                )

        print(f"Writing {len(audio_chunk)} into {self.rvc_sample_rate} stream")
        self.audio_stream.write(audio_chunk)

    def synthesize(self):
        self.ensure_playing()
        self.buffer.stop()

        while self.stream.is_playing() or not self.audio_queue.empty():
            time.sleep(0.01)
        
        self.buffer = BufferStream()
        
    def load_xtts_model(self, local_path: str = None):

        if self.use_logging:
            if not local_path:
                print("loading default xtts model")
            else:
                print(f"loading xtts model {local_path}")

        level = logging.DEBUG if self.use_logging else logging.WARNING
        voice = self.xtts_voice if self.xtts_voice else ""

        if not self.engine:
            engine_params = {
                "language": "en",
                "level": level,
                "voice": voice,
                "speed": 1.0,
                "temperature": 0.9,
                "repetition_penalty": 10,
                "top_k": 70,
                "top_p": 0.9,
                "add_sentence_filter": True,
                "comma_silence_duration": 0.1,
                "sentence_silence_duration": 0.3,
                "default_silence_duration": 0.1,
            }

            if local_path is not None:
                if not os.path.isdir(local_path):
                    raise ValueError(f"local_path must be a valid directory: {local_path}")
                xtts_model_name = os.path.basename(local_path)
                xtts_model_path = os.path.dirname(local_path)

                engine_params["specific_model"] = xtts_model_name
                engine_params["local_models_path"] = xtts_model_path

            self.engine = CoquiEngine(**engine_params)

            def on_audio_stream_stop():
                print("FINISHED")

            self.stream = TextToAudioStream(self.engine, on_audio_stream_stop=on_audio_stream_stop)

            print("Performing warmup")
            self.stream.feed("warmup")
            self.stream.play(muted=True)
            print("Warmup performed")

        else:
            if voice and len(voice) > 0:
                self.engine.set_voice(voice)

            if local_path is not None:                    
                if not os.path.isdir(local_path):
                    raise ValueError(f"local_path must be a valid directory: {local_path}")
                xtts_model_name = os.path.basename(local_path)
                xtts_model_path = os.path.dirname(local_path)

                self.engine.local_models_path = xtts_model_path
                self.engine.set_model(xtts_model_name)
            
        self.xtts_model_loaded = True

    def wait_playing(self):
        while self.stream.is_playing() or self.audio_queue.qsize() > 0:
            time.sleep(0.02)
    
    def clear_queue(self):
        while self.audio_queue.qsize() > 0:
            try:
                self.audio_queue.get()
            except Empty:
                break

    def stop(self):
        self.buffer.stop()

        if self.stream.is_playing():
            print("Stopping stream")
            self.stream.stop()

        if self.rvc:
            print("Stopping rvc")
            self.rvc.stop()
        

        self.stop_playback.set()
        if self.playback_thread:
            self.playback_thread.join()

        self.clear_queue()
        self.wait_playing()
        self.buffer = BufferStream()

        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None

    def load_rvc_model(self, rvc_model: str = None, rvc_sample_rate = 40000):
        rvc_model_name = os.path.basename(rvc_model)
        rvc_model_name = str(Path(rvc_model_name).with_suffix(''))
        rvc_model_path = os.path.dirname(rvc_model)

        def yield_chunk_callback(chunk):
            self.audio_queue.put(chunk)

        if self.rvc is None:
            self.rvc = RealtimeRVC(rvc_model_path, yield_chunk_callback=yield_chunk_callback, sample_rate=rvc_sample_rate) 
            self.rvc.start(rvc_model_name)
        else:
            self.rvc.rvc_model_path = rvc_model_path
            self.rvc.set_model(rvc_model_name)

    def shutdown(self):
        if self.rvc:
            self.rvc.shutdown()
        if self.stream is not None and self.stream.is_playing():
            self.stream.stop()
        if self.engine is not None:
            self.engine.shutdown()
        
        self.stop_playback.set()
        if self.playback_thread:
            self.playback_thread.join()
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
