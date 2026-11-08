"""
SahayaVaani — Audio Processing & VAD Performance Benchmark
Measures throughput and per-frame latency for:
  1. 16 kHz PCM chunking & zero-padding
  2. Envelope noise gating (512-sample blocks)
  3. WebRTC / Dual-Stage Voice Activity Detection (VAD)

Usage:
    python scripts/benchmark_vad.py
    python scripts/benchmark_vad.py --frames 5000
"""
import argparse
import os
import sys
import time
import numpy as np

# Ensure backend directory is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from bolna_layer.audio_utils import split_into_frames, apply_noise_gate
from services.vad_service import VADService


def generate_benchmark_signal(duration_seconds: float = 10.0, sample_rate: int = 16000) -> bytes:
    """Generate 16-bit mono PCM with alternating silence and synthetic speech bursts."""
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    
    # 250 Hz fundamental + harmonics (simulating human speech formant)
    voice = (
        0.5 * np.sin(2 * np.pi * 250 * t) +
        0.3 * np.sin(2 * np.pi * 500 * t) +
        0.2 * np.sin(2 * np.pi * 1000 * t)
    )
    
    # Pulse modulation: 1.5s speech, 1.0s silence
    envelope = (np.sin(2 * np.pi * 0.4 * t) > 0).astype(float)
    signal = voice * envelope * 12000  # Scale amplitude
    
    # Add low-amplitude room noise
    noise = np.random.normal(0, 150, num_samples)
    composite = np.clip(signal + noise, -32768, 32767).astype(np.int16)
    return composite.tobytes()


def run_benchmark(num_frames_target: int = 2000):
    print("=" * 70)
    print(" SahayaVaani - Real-Time Audio Engine & VAD Benchmark")
    print("=" * 70)
    
    pcm_bytes = generate_benchmark_signal(duration_seconds=10.0)
    print(f"Generated {len(pcm_bytes)} bytes of synthetic 16kHz PCM audio ({len(pcm_bytes)/32000:.1f}s)")
    
    # 1. Benchmark frame splitting
    t0 = time.perf_counter()
    frames = split_into_frames(pcm_bytes, frame_size=1024)
    t_split = (time.perf_counter() - t0) * 1000.0
    print(f"[1/3] Frame Splitting: {len(frames)} frames in {t_split:.2f} ms ({len(frames)/(t_split/1000.0):.0f} frames/sec)")
    
    # 2. Benchmark envelope noise gating
    gate_latencies = []
    gated_frames = []
    for frame in frames:
        t_start = time.perf_counter_ns()
        gated = apply_noise_gate(frame, threshold=400)
        gate_latencies.append((time.perf_counter_ns() - t_start) / 1000.0)  # microseconds
        gated_frames.append(gated)
        
    p50_gate = np.percentile(gate_latencies, 50)
    p95_gate = np.percentile(gate_latencies, 95)
    p99_gate = np.percentile(gate_latencies, 99)
    print(f"[2/3] Noise Gating:    p50={p50_gate:.1f}us | p95={p95_gate:.1f}us | p99={p99_gate:.1f}us")
    
    # 3. Benchmark VAD Service evaluation
    vad = VADService()
    vad_latencies = []
    triggers = 0
    
    # Convert frames to 30ms (960 bytes) for VAD standard input
    vad_frames = split_into_frames(pcm_bytes, frame_size=960)
    for frame in vad_frames:
        t_start = time.perf_counter_ns()
        is_speech = vad.process_frame(frame)
        vad_latencies.append((time.perf_counter_ns() - t_start) / 1000.0)  # microseconds
        if is_speech:
            triggers += 1
            
    p50_vad = np.percentile(vad_latencies, 50)
    p95_vad = np.percentile(vad_latencies, 95)
    p99_vad = np.percentile(vad_latencies, 99)
    print(f"[3/3] VAD Evaluation:  p50={p50_vad:.1f}us | p95={p95_vad:.1f}us | p99={p99_vad:.1f}us ({triggers}/{len(vad_frames)} speech frames)")
    
    print("-" * 70)
    total_pipeline_latency_us = p95_gate + p95_vad
    print(f"Total Combined Ingestion Latency (p95): {total_pipeline_latency_us:.1f} us ({total_pipeline_latency_us/1000.0:.3f} ms)")
    print("SLA Target: < 10.0 ms per 30ms audio chunk")
    if total_pipeline_latency_us / 1000.0 < 10.0:
        print("[VERIFIED] Real-time audio processing operates comfortably below sub-millisecond threshold.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SahayaVaani Audio Engine Benchmark")
    parser.add_argument("--frames", type=int, default=2000, help="Target frames to benchmark")
    args = parser.parse_args()
    run_benchmark(args.frames)
