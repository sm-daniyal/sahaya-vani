"""
SahayaVaani Configuration
Pydantic BaseSettings — all values can be overridden via environment variables or .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

_ENV_FILE = str(Path(__file__).resolve().parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────────
    app_name: str = "SahayaVaani"
    app_version: str = "1.0.0-mvp"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080

    # ── Gnani API ──────────────────────────────────────────────────────────────
    gnani_api_key: str = "YOUR_GNANI_API_KEY_HERE"
    gemini_api_key: str = ""

    # STT — Gnani Prisma v2.5
    stt_ws_url: str = "wss://api.vachana.ai/stt/v3/stream"
    stt_lang_code: str = "kn-IN"
    stt_confidence_threshold: float = 0.50   # below this → ask patient to repeat

    # TTS — Gnani Timbre v2.5 (lowest-latency realtime endpoint)
    tts_ws_url: str = "wss://api.vachana.ai/tts/v2/stream"
    tts_voice: str = "kannada_female_1"       # Timbre voice ID
    tts_sample_rate: int = 16000

    # ── LLM — Gnani Evon v3.3 (vLLM local) ───────────────────────────────────
    vllm_base_url: str = "http://localhost:8000/v1"
    evon_model_name: str = "gnani/evon-v3.3"
    evon_max_tokens: int = 512
    evon_temperature: float = 0.3
    evon_timeout: float = 30.0

    # ── Audio ─────────────────────────────────────────────────────────────────
    sample_rate: int = 16000              # 16 kHz
    frame_size: int = 1024               # bytes per PCM frame  (512 int16 samples)
    channels: int = 1                    # mono
    sample_width: int = 2               # 16-bit = 2 bytes per sample
    noise_gate_threshold: int = 400     # amplitude threshold for noise gate (blocks low-energy background hiss)

    # ── VAD (Voice Activity Detection) ────────────────────────────────────────
    vad_aggressiveness: int = 2          # webrtcvad 0-3 (2 = balanced background noise rejection without clipping speech)
    vad_min_silence_ms: int = 550       # ms of silence before end-of-utterance (550ms = natural pause without cutoff)
    vad_frame_duration_ms: int = 30     # webrtcvad frame size (10, 20, or 30 ms)

    # ── Database ──────────────────────────────────────────────────────────────
    db_path: str = "emr.db"
    db_url: str = "sqlite+aiosqlite:///emr.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
