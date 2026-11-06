"""
SahayaVaani — Audio Utilities
PCM manipulation helpers used by the Bolna orchestration layer.

All audio in SahayaVaani is:
  - PCM 16-bit little-endian
  - Mono (1 channel)
  - 16 kHz sample rate
"""
import io
import logging
import struct
import wave
from typing import List

logger = logging.getLogger(__name__)


def split_into_frames(audio_bytes: bytes, frame_size: int = 1024) -> List[bytes]:
    """
    Split a PCM byte string into equal-sized frames.
    The last frame is zero-padded if necessary.

    Args:
        audio_bytes: Raw PCM bytes.
        frame_size:  Bytes per frame (default 1024 = 512 int16 samples).

    Returns:
        List of byte frames, each exactly `frame_size` bytes.
    """
    frames = []
    offset = 0
    while offset < len(audio_bytes):
        chunk = audio_bytes[offset : offset + frame_size]
        if len(chunk) < frame_size:
            chunk = chunk + b"\x00" * (frame_size - len(chunk))
        frames.append(chunk)
        offset += frame_size
    return frames


def pcm_to_wav(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """
    Wrap raw PCM bytes into a valid WAV container.

    Args:
        pcm_bytes:    Raw PCM data.
        sample_rate:  Hz (default 16000).
        channels:     1 = mono.
        sample_width: Bytes per sample (2 = 16-bit).

    Returns:
        WAV file bytes (with RIFF header).
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def wav_to_pcm(wav_bytes: bytes) -> bytes:
    """
    Extract raw PCM samples from a WAV file bytes object.
    Assumes 16-bit mono 16 kHz (or resamples naively).
    """
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            logger.warning(
                "[audio_utils] WAV format mismatch (ch=%d, sw=%d) — reading raw frames anyway",
                wf.getnchannels(), wf.getsampwidth(),
            )
        return wf.readframes(wf.getnframes())


def apply_noise_gate(pcm_bytes: bytes, threshold: int = 500) -> bytes:
    """
    Frame-based amplitude noise gate.
    Evaluates audio in 512-sample (32ms) blocks. If the peak amplitude within
    a block is below `threshold`, the block is silenced (zeroed out).
    If peak amplitude is at or above `threshold`, the block is preserved
    intact without sample-level zero-crossing distortion.

    Args:
        pcm_bytes: PCM 16-bit little-endian bytes.
        threshold: Amplitude floor [0, 32767].

    Returns:
        Processed PCM bytes, same length as input.
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return pcm_bytes

    samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])

    block_size = 512
    out_samples = []
    for i in range(0, num_samples, block_size):
        block = samples[i : i + block_size]
        peak = max((abs(s) for s in block), default=0)
        if peak < threshold:
            out_samples.extend([0] * len(block))
        else:
            out_samples.extend(block)

    result = struct.pack(f"<{num_samples}h", *out_samples)
    if len(pcm_bytes) % 2:
        result += pcm_bytes[-1:]
    return result


def normalize_audio(pcm_bytes: bytes, target_peak: int = 24000) -> bytes:
    """
    Normalize audio amplitude so the peak sample equals `target_peak`.
    Protects against over-amplification when the signal is very quiet.

    Args:
        pcm_bytes:   PCM 16-bit little-endian.
        target_peak: Desired peak absolute value [1, 32767].

    Returns:
        Normalized PCM bytes.
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return pcm_bytes

    samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])
    peak = max((abs(s) for s in samples), default=0)

    if peak == 0:
        return pcm_bytes  # silence — nothing to do

    gain = target_peak / peak
    # Cap gain at 4× to avoid catastrophic amplification of near-silent frames
    gain = min(gain, 4.0)

    normalised = tuple(max(-32768, min(32767, int(s * gain))) for s in samples)
    result = struct.pack(f"<{num_samples}h", *normalised)
    if len(pcm_bytes) % 2:
        result += pcm_bytes[-1:]
    return result


def calculate_rms(pcm_bytes: bytes) -> float:
    """
    Calculate Root Mean Square energy of a PCM frame.
    Returns 0.0 for empty input.
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])
    rms = (sum(s * s for s in samples) / num_samples) ** 0.5
    return rms
