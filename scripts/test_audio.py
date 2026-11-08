"""
SahayaVaani — Test a WAV file against the full pipeline
Loads a WAV file, resamples to 16kHz mono PCM if needed, and streams it
to the backend WebSocket, printing transcript and agent responses.

Usage:
    python scripts/test_audio.py path/to/sample.wav
    python scripts/test_audio.py path/to/sample.wav --session-id my-test-01
"""
import argparse
import asyncio
import json
import sys
import os

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import struct
import wave
from pathlib import Path

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    sys.exit(1)


BACKEND_WS   = "ws://localhost:8080"
FRAME_SIZE   = 1024   # bytes


def load_wav_as_pcm(wav_path: Path) -> bytes:
    """
    Load a WAV file and return raw PCM 16-bit mono 16kHz bytes.
    Handles common format conversions:
      - Stereo → mono (average channels)
      - 8-bit → 16-bit
      - Other sample rates (naive linear resampling)
    """
    with wave.open(str(wav_path), "rb") as wf:
        channels     = wf.getnchannels()
        sampwidth    = wf.getsampwidth()
        framerate    = wf.getframerate()
        nframes      = wf.getnframes()
        raw          = wf.readframes(nframes)

    print(f"WAV info: {channels}ch, {sampwidth*8}-bit, {framerate}Hz, {nframes} frames")

    # Decode samples
    if sampwidth == 2:
        fmt = f"<{nframes * channels}h"
        samples = list(struct.unpack(fmt, raw))
    elif sampwidth == 1:
        # 8-bit unsigned → 16-bit signed
        samples = [(b - 128) * 256 for b in raw]
        channels_count = channels
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # Stereo → mono
    if channels == 2:
        mono = [(samples[i] + samples[i+1]) // 2 for i in range(0, len(samples), 2)]
    else:
        mono = samples

    # Resample to 16kHz (naive: drop or repeat samples)
    if framerate != 16000:
        ratio    = 16000 / framerate
        new_len  = int(len(mono) * ratio)
        resampled = []
        for i in range(new_len):
            src_idx = int(i / ratio)
            resampled.append(mono[min(src_idx, len(mono) - 1)])
        mono = resampled
        print(f"Resampled {framerate}Hz → 16000Hz ({len(mono)} samples)")

    # Pack back to bytes
    pcm = struct.pack(f"<{len(mono)}h", *[max(-32768, min(32767, s)) for s in mono])
    print(f"PCM bytes: {len(pcm)} ({len(pcm)/16000/2:.2f}s)")
    return pcm


async def run_test(wav_path: Path, session_id: str, backend_ws: str):
    pcm = load_wav_as_pcm(wav_path)

    # Split into 1024-byte frames
    frames = [pcm[i:i+FRAME_SIZE] for i in range(0, len(pcm), FRAME_SIZE)]
    if frames and len(frames[-1]) < FRAME_SIZE:
        frames[-1] = frames[-1] + b"\x00" * (FRAME_SIZE - len(frames[-1]))

    print(f"\nConnecting to {backend_ws}/ws/call/{session_id} ...")
    async with websockets.connect(f"{backend_ws}/ws/call/{session_id}") as ws:
        print(f"Connected! Sending {len(frames)} frames ({len(pcm)} bytes)\n")

        # Sender task
        async def send_audio():
            for frame in frames:
                await ws.send(frame)
                await asyncio.sleep(FRAME_SIZE / 2 / 16000)  # real-time pacing
            # Signal end of stream (empty frame)
            await ws.send(b"\x00" * FRAME_SIZE)
            print("[Sender] All frames sent")

        # Receiver task
        async def receive_events():
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    if isinstance(msg, bytes):
                        print(f"[Audio] Received {len(msg)} bytes of TTS audio")
                    else:
                        data = json.loads(msg)
                        event_type = data.get("type", "unknown")
                        if event_type == "transcript":
                            status = "FINAL" if data.get("is_final") else "partial"
                            print(f"[STT/{status}] {data.get('text', '')} (conf={data.get('confidence', 0):.2f})")
                        elif event_type == "agent_response":
                            print(f"[AGENT] {data.get('text', '')}")
                        elif event_type == "state_change":
                            print(f"[NODE]  → {data.get('node', '?')} | intent={data.get('intent', '?')}")
                        elif event_type in ("session_end", "session_start"):
                            print(f"[{event_type.upper()}] {data}")
                            if event_type == "session_end":
                                return
                        else:
                            print(f"[{event_type}] {data}")
                except asyncio.TimeoutError:
                    print("[Receiver] Timeout — no more events")
                    return
                except Exception as exc:
                    print(f"[Receiver] Closed: {exc}")
                    return

        await asyncio.gather(send_audio(), receive_events())

    print("\n[SUCCESS] Test complete")


def main():
    parser = argparse.ArgumentParser(description="SahayaVaani WAV test client")
    parser.add_argument("wav_path", help="Path to input WAV file")
    parser.add_argument("--session-id", default="test-audio-001", help="Session ID")
    parser.add_argument("--backend", default=BACKEND_WS, help="Backend WebSocket URL")
    args = parser.parse_args()

    wav = Path(args.wav_path)
    if not wav.exists():
        print(f"ERROR: File not found: {wav}")
        sys.exit(1)

    asyncio.run(run_test(wav, args.session_id, args.backend))


if __name__ == "__main__":
    main()
