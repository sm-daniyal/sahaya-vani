"""
Unit tests for Audio Utilities and Voice Activity Detection (VAD).
Validates PCM framing, noise gating, WAV wrapping, and speech boundary detection.
"""
import struct
import pytest
from bolna_layer.audio_utils import (
    split_into_frames,
    apply_noise_gate,
    normalize_audio,
    pcm_to_wav,
    wav_to_pcm,
)
from services.vad_service import VADService


class TestAudioUtils:
    def test_split_into_frames_exact_multiple(self):
        pcm = b"\x00\x01" * 1024  # 2048 bytes
        frames = split_into_frames(pcm, frame_size=1024)
        assert len(frames) == 2
        assert len(frames[0]) == 1024
        assert len(frames[1]) == 1024

    def test_split_into_frames_zero_padding(self):
        pcm = b"\x00\x01" * 500  # 1000 bytes (< 1024)
        frames = split_into_frames(pcm, frame_size=1024)
        assert len(frames) == 1
        assert len(frames[0]) == 1024
        assert frames[0].endswith(b"\x00" * 24)

    def test_split_into_frames_empty(self):
        frames = split_into_frames(b"", frame_size=1024)
        assert frames == []

    def test_apply_noise_gate_silences_quiet_audio(self):
        # Samples with amplitude 100 (< 500 threshold)
        samples = [100] * 512
        raw = struct.pack(f"<{len(samples)}h", *samples)
        gated = apply_noise_gate(raw, threshold=500)
        unpacked = struct.unpack(f"<{len(samples)}h", gated)
        assert all(s == 0 for s in unpacked)

    def test_apply_noise_gate_passes_loud_audio(self):
        # Samples with amplitude 2000 (> 500 threshold)
        samples = [2000] * 512
        raw = struct.pack(f"<{len(samples)}h", *samples)
        gated = apply_noise_gate(raw, threshold=500)
        assert gated == raw

    def test_normalize_audio_scales_peak(self):
        samples = [0, 8000, -8000, 16000]
        raw = struct.pack(f"<{len(samples)}h", *samples)
        normalized = normalize_audio(raw, target_peak=32000)
        unpacked = struct.unpack(f"<{len(samples)}h", normalized)
        assert max(unpacked) == 32000

    def test_normalize_audio_zero_energy(self):
        raw = b"\x00" * 1024
        assert normalize_audio(raw) == raw

    def test_pcm_to_wav_riff_header(self):
        pcm = b"\x00" * 1600
        wav = pcm_to_wav(pcm, sample_rate=16000)
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert wav[12:16] == b"fmt "

    def test_wav_to_pcm_roundtrip(self):
        samples = [1000, 2000, -3000, 4000]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        wav = pcm_to_wav(pcm, sample_rate=16000)
        extracted_pcm = wav_to_pcm(wav)
        assert extracted_pcm == pcm


class TestVADService:
    def test_vad_initial_state(self):
        vad = VADService()
        vad.reset()
        assert not vad.is_speaking
        assert not vad.end_of_utterance_detected()
        assert vad.get_speech_buffer() == b""

    def test_vad_speech_detection_amplitude(self):
        vad = VADService()
        vad.reset()
        loud_samples = [2500] * (vad.VAD_FRAME_BYTES // 2)
        loud_frame = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
        is_speech = vad.process_frame(loud_frame)
        assert is_speech is True
        assert vad.is_speaking is True

    def test_vad_speech_buffer_accumulation(self):
        vad = VADService()
        vad.reset()
        frame = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([3000] * (vad.VAD_FRAME_BYTES // 2)))
        for _ in range(6):
            vad.process_frame(frame)
        assert len(vad.get_speech_buffer()) == vad.VAD_FRAME_BYTES * 6

    def test_vad_short_click_rejected(self):
        vad = VADService()
        vad.reset()
        # Single 30ms loud frame followed by silence should NOT trigger end-of-utterance
        # because min_speech_frames requires >= 150ms (5 frames)
        loud = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([3000] * (vad.VAD_FRAME_BYTES // 2)))
        silence = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([0] * (vad.VAD_FRAME_BYTES // 2)))

        vad.process_frame(loud)
        for _ in range(30):
            vad.process_frame(silence)

        assert not vad.end_of_utterance_detected()

    def test_vad_end_of_utterance_trigger(self):
        vad = VADService()
        vad.reset()
        loud = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([3000] * (vad.VAD_FRAME_BYTES // 2)))
        silence = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([0] * (vad.VAD_FRAME_BYTES // 2)))

        # 6 frames speech = 180ms (> 150ms min threshold)
        for _ in range(6):
            vad.process_frame(loud)

        # 30 frames silence = 900ms (> 850ms silence threshold)
        for _ in range(30):
            vad.process_frame(silence)

        assert vad.end_of_utterance_detected() is True

    def test_vad_process_bytes_leftover_handling(self):
        vad = VADService()
        vad.reset()
        chunk1 = b"\x00" * 500
        chunk2 = b"\x00" * 600
        # Total 1100 bytes (> 960 bytes frame size)
        res1 = vad.process_bytes(chunk1)
        res2 = vad.process_bytes(chunk2)
        assert len(res1) == 0
        assert len(res2) == 1

    def test_vad_reset_clears_all(self):
        vad = VADService()
        vad.reset()
        loud = struct.pack(f"<{vad.VAD_FRAME_BYTES//2}h", *([3000] * (vad.VAD_FRAME_BYTES // 2)))
        vad.process_frame(loud)
        vad.reset()
        assert vad.get_speech_buffer() == b""
        assert not vad.is_speaking
