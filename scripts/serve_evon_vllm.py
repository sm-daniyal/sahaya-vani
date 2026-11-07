#!/usr/bin/env python3
"""
SahayaVaani — Gnani Evon v3.3 vLLM Serving Launcher
Provides an OpenAI-compatible /v1/chat/completions endpoint for gnani/evon-v3.3.
Suitable for local GPU nodes (RTX 3090/4090, A100) or cloud instances (Colab, RunPod, Lambda).
"""

import argparse
import subprocess
import sys
import shutil


def check_prerequisites():
    """Verify vLLM is installed in current Python environment."""
    try:
        import vllm  # noqa: F401
    except ImportError:
        print("[ERROR] vLLM is not installed.")
        print("Please install vLLM using:")
        print("    pip install vllm")
        print("For GPU Colab instances:")
        print("    pip install vllm pyngrok")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Serve Gnani Evon v3.3 via vLLM with an OpenAI-compatible API"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gnani/evon-v3.3",
        help="Hugging Face model ID or local directory (default: gnani/evon-v3.3)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host interface to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=4096,
        help="Max context window length in tokens (default: 4096)",
    )
    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=0.92,
        help="Fraction of GPU memory for model weights and KV cache (default: 0.92)",
    )
    parser.add_argument(
        "--quantization",
        type=str,
        default=None,
        choices=["bitsandbytes", "awq", "gptq", "fp8", None],
        help="Quantization method for low-VRAM GPUs (optional)",
    )
    parser.add_argument(
        "--ngrok-token",
        type=str,
        default=None,
        help="Optional ngrok authtoken to expose public tunnel URL automatically",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    check_prerequisites()

    cmd = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        args.model,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--max-model-len",
        str(args.max_model_len),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--trust-remote-code",
        "--dtype",
        "bfloat16",
    ]

    if args.quantization:
        cmd.extend(["--quantization", args.quantization])

    print("=" * 70)
    print(" SahayaVaani — Gnani Evon v3.3 vLLM Inference Server")
    print(f" Model:       {args.model}")
    print(f" Local URL:   http://{args.host}:{args.port}/v1")
    print(f" Context:     {args.max_model_len} tokens")
    print("=" * 70)

    tunnel_url = None
    if args.ngrok_token:
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(args.ngrok_token)
            tunnel = ngrok.connect(args.port)
            tunnel_url = f"{tunnel.public_url}/v1"
            print(f"[TUNNEL] Public ngrok Endpoint: {tunnel_url}")
            print(f"[TUNNEL] Configure your SahayaVaani backend/.env:")
            print(f"         VLLM_BASE_URL={tunnel_url}")
            print(f"         EVON_MODEL_NAME={args.model}")
            print(f"         EVON_ENABLED=true")
            print("=" * 70)
        except Exception as err:
            print(f"[WARNING] Could not start ngrok tunnel: {err}")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[INFO] Evon vLLM server stopped by user.")


if __name__ == "__main__":
    main()
