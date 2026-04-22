"""
Neuron — Speech Recognition Service (WASAPI + Vosk)
=====================================================
Offline real-time speech-to-text using Vosk.

Key design decisions:
- WASAPI loopback: captures system audio OUTPUT (interviewer's voice)
- Does NOT capture microphone (candidate's voice)
- Vosk: offline, lightweight, ~50MB model
- Background thread: non-blocking, emits signals

Architecture (from Parrot.ai analysis):
  WASAPI Loopback → Audio Buffer → Vosk STT → Sentence Detection → Callback
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional, Callable

from app.logger import logger


class SpeechService:
    """Real-time offline speech-to-text via Vosk + WASAPI loopback.
    
    Captures ONLY system audio output (what the speakers/headphones play).
    This means it hears the INTERVIEWER's voice from Zoom/Meet/Teams,
    but NOT the candidate's own voice.
    
    Callbacks:
    - on_partial(text): fired as words are recognized (unstable)
    - on_final(text): fired when a complete sentence is detected
    """
    
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._recognizer = None
        self._audio_stream = None
        self._pyaudio = None
        
        # Callbacks
        self.on_partial: Optional[Callable[[str], None]] = None
        self.on_final: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def start(self) -> bool:
        """Start listening to system audio.
        
        Returns True if started successfully, False if dependencies missing.
        """
        if self._running:
            return True
        
        try:
            self._setup_vosk()
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info("SpeechService: Started listening (WASAPI loopback)")
            if self.on_status:
                self.on_status("🎙 Listening...")
            return True
            
        except ImportError as e:
            error_msg = f"Speech recognition unavailable: {e}"
            logger.warning(f"SpeechService: {error_msg}")
            if self.on_error:
                self.on_error(error_msg)
            return False
            
        except Exception as e:
            error_msg = f"Failed to start speech service: {e}"
            logger.error(f"SpeechService: {error_msg}")
            if self.on_error:
                self.on_error(error_msg)
            return False
    
    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        
        if self._audio_stream:
            try:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None
        
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None
        
        self._recognizer = None
        logger.info("SpeechService: Stopped")
        if self.on_status:
            self.on_status("🔴 Stopped")
    
    def _setup_vosk(self):
        """Initialize Vosk model and recognizer."""
        from vosk import Model, KaldiRecognizer
        
        # Find model path
        from services.model_manager import get_vosk_model_path, download_vosk_model
        
        model_path = get_vosk_model_path()
        if model_path is None:
            logger.info("SpeechService: Vosk model not found, downloading...")
            if self.on_status:
                self.on_status("Downloading speech model...")
            model_path = download_vosk_model()
        
        logger.info(f"SpeechService: Loading Vosk model from {model_path}")
        model = Model(str(model_path))
        self._recognizer = KaldiRecognizer(model, 16000)
        self._recognizer.SetWords(True)
    
    def _listen_loop(self):
        """Main audio capture and recognition loop.
        
        Uses WASAPI loopback to capture system audio output.
        Falls back to microphone if WASAPI loopback is not available.
        """
        try:
            # Try WASAPI loopback first (captures interviewer voice)
            try:
                import pyaudiowpatch as pyaudio
                use_loopback = True
                logger.info("SpeechService: Using WASAPI loopback (system audio capture)")
            except ImportError:
                import pyaudio
                use_loopback = False
                logger.info("SpeechService: pyaudiowpatch not available, falling back to microphone")
            
            self._pyaudio = pyaudio.PyAudio()
            
            if use_loopback:
                # Get WASAPI loopback device (captures what speakers play)
                try:
                    wasapi_info = self._pyaudio.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = self._pyaudio.get_device_info_by_index(
                        wasapi_info["defaultOutputDevice"]
                    )
                    
                    # WASAPI loopback stream
                    sample_rate = int(default_speakers["defaultSampleRate"])
                    channels = default_speakers["maxInputChannels"]
                    
                    self._audio_stream = self._pyaudio.open(
                        format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        input_device_index=default_speakers["index"],
                        frames_per_buffer=8192,
                        stream_callback=None,  # We'll use blocking reads
                    )
                    
                    if self.on_status:
                        self.on_status("🎙 Listening to system audio...")
                    
                except Exception as e:
                    logger.warning(f"SpeechService: WASAPI loopback failed: {e}, falling back to mic")
                    use_loopback = False
            
            if not use_loopback:
                # Fallback to microphone
                self._audio_stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=8192,
                )
                if self.on_status:
                    self.on_status("🎙 Listening (microphone)...")
            
            # Recognition loop
            while self._running:
                try:
                    data = self._audio_stream.read(4096, exception_on_overflow=False)
                    
                    if self._recognizer.AcceptWaveform(data):
                        # Complete sentence detected
                        result = json.loads(self._recognizer.Result())
                        text = result.get("text", "").strip()
                        if text and len(text) > 2:  # Ignore very short fragments
                            logger.info(f"SpeechService: Final → '{text}'")
                            if self.on_final:
                                self.on_final(text)
                    else:
                        # Partial result (in progress)
                        partial = json.loads(self._recognizer.PartialResult())
                        text = partial.get("partial", "").strip()
                        if text:
                            if self.on_partial:
                                self.on_partial(text)
                                
                except OSError:
                    # Audio stream error (device disconnected, etc.)
                    time.sleep(0.1)
                    continue
                    
        except Exception as e:
            logger.error(f"SpeechService: Listen loop error: {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            self._running = False


# ── Singleton ────────────────────────────────────────────────
_service: Optional[SpeechService] = None

def get_speech_service() -> SpeechService:
    global _service
    if _service is None:
        _service = SpeechService()
    return _service
