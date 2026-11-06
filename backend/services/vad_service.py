"""
SahayaVaani — Voice Activity Detection Service
Wraps webrtcvad to detect speech boundaries in a PCM 16kHz stream.

The VAD is tuned for Indian phone audio:
  - Aggressiveness level 2 (medium — avoids cutting off aspirated consonants)
  - 400 ms of silence marks end-of-utterance (VAD_MIN_SILENCE_MS)
  - 30 ms frames (webrtcvad requirement)
"""
import logging
import struct
from collections import deque
from typing import List, Optional

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None   # type: ignore

from config import settings

logger = logging.getLogger(__name__)


class VADService:
    """
    Frame-level VAD using WebRTC VAD.

    Usage:
        vad = VADService()
        vad.reset()
        for pcm_frame in audio_frames:
            is_speech = vad.process_frame(pcm_frame)
            if vad.end_of_utterance_detected():
                speech_audio = vad.get_speech_buffer()
                break
    """

    # webrtcvad requires frames of exactly 10, 20, or 30 ms at 8/16/32/48 kHz.
    # At 16 kHz with 16-bit mono: 30 ms = 960 bytes
    VAD_FRAME_BYTES: int = int(
        settings.sample_rate * settings.sample_width * settings.vad_frame_duration_ms / 1000
    )   # 960 bytes for 30 ms @ 16kHz 16-bit mono

    def __init__(self):
        if WEBRTCVAD_AVAILABLE:
            self._vad = webrtcvad.Vad(settings.vad_aggressiveness)
        else:
            self._vad = None
            logger.warning("[VAD] webrtcvad not installed — using amplitude-based fallback")

        self._frame_duration_ms = settings.vad_frame_duration_ms
        self._min_silence_ms    = settings.vad_min_silence_ms
        self._silence_frames_threshold = int(
            self._min_silence_ms / self._frame_duration_ms
        )   # e.g. 600ms / 30ms = 20 frames
        self._speech_frames_count: int = 0
        self._min_speech_frames: int = int(150 / self._frame_duration_ms)  # Require at least 150ms of real speech (5 frames)

        # State
        self._speech_buffer: List[bytes] = []
        self._silence_counter: int = 0
        self._is_speaking: bool = False
        self._leftover: bytes = b""

    def reset(self) -> None:
        """Reset state between utterances."""
        self._speech_buffer = []
        self._silence_counter = 0
        self._speech_frames_count = 0
        self._is_speaking = False
        self._leftover = b""

    def _is_speech_webrtcvad(self, frame: bytes) -> bool:
        """Use webrtcvad to determine if frame contains speech."""
        try:
            return self._vad.is_speech(frame, settings.sample_rate)
        except Exception as exc:
            logger.debug("[VAD] webrtcvad error on frame: %s", exc)
            return False

    def _calculate_rms(self, frame: bytes) -> float:
        """Calculate Root Mean Square energy of a PCM frame."""
        if len(frame) < 2:
            return 0.0
        samples = struct.unpack(f"<{len(frame)//2}h", frame[: (len(frame)//2)*2])
        return (sum(s * s for s in samples) / len(samples)) ** 0.5

    def _is_speech_amplitude(self, frame: bytes) -> bool:
        """
        Amplitude-based fallback VAD.
        Treats the frame as speech if RMS energy exceeds conversational threshold.
        """
        rms = self._calculate_rms(frame)
        return rms > settings.noise_gate_threshold

    def process_frame(self, pcm_bytes: bytes) -> bool:
        """
        Process a single PCM frame (must be exactly VAD_FRAME_BYTES bytes).
        Returns True if the frame is classified as speech.

        Uses calibrated dual-stage VAD:
          1. Ambient noise gate: frames with RMS < 180 are treated as room silence/hiss.
          2. WebRTC acoustic classification: detects natural human speech formants down to 180 RMS.
          3. Strong energy fallback: high amplitude (> 600 RMS) guarantees speech detection even
             if WebRTC VAD adapts to stationary vowels.
        """
        if len(pcm_bytes) != self.VAD_FRAME_BYTES:
            # Pad or truncate to expected size
            pcm_bytes = (pcm_bytes + b"\x00" * self.VAD_FRAME_BYTES)[: self.VAD_FRAME_BYTES]

        rms = self._calculate_rms(pcm_bytes)

        # Stage 1: Ambient floor rejection — filters out background hiss, fans, and faint room noise
        if rms < 180.0:
            is_speech = False
        elif WEBRTCVAD_AVAILABLE and self._vad is not None:
            # Stage 2: WebRTC speech classification, with strong vocal energy override (> 600 RMS)
            is_speech = self._is_speech_webrtcvad(pcm_bytes) or (rms > 600.0)
        else:
            is_speech = rms > settings.noise_gate_threshold

        if is_speech:
            self._is_speaking = True
            self._speech_frames_count += 1
            self._silence_counter = 0
            self._speech_buffer.append(pcm_bytes)
        else:
            if self._is_speaking:
                self._silence_counter += 1
                # Keep a small trailing silence so the final word isn't cut off
                self._speech_buffer.append(pcm_bytes)

        return is_speech

    def process_bytes(self, raw_pcm: bytes) -> List[bool]:
        """
        Process a raw PCM byte string of arbitrary length.
        Internally splits into VAD_FRAME_BYTES frames (with leftover handling).
        Returns a list of booleans (one per frame).
        """
        data = self._leftover + raw_pcm
        results = []
        offset = 0
        while offset + self.VAD_FRAME_BYTES <= len(data):
            frame = data[offset : offset + self.VAD_FRAME_BYTES]
            results.append(self.process_frame(frame))
            offset += self.VAD_FRAME_BYTES
        self._leftover = data[offset:]
        return results

    def end_of_utterance_detected(self) -> bool:
        """
        Returns True when enough silence has been accumulated after speech
        to signal end-of-utterance.
        """
        return (
            self._is_speaking
            and self._speech_frames_count >= self._min_speech_frames
            and self._silence_counter >= self._silence_frames_threshold
        )

    def get_speech_buffer(self) -> bytes:
        """Return all accumulated speech frames as a single bytes object."""
        return b"".join(self._speech_buffer)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
