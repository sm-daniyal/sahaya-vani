"""
SahayaVaani — FastAPI Application Entry Point

Endpoints:
  GET  /                          Health check
  GET  /api/appointments          List all EMR appointments (JSON)
  GET  /api/appointments/{id}     Get single appointment
  GET  /api/handoffs              List all human-handoff flags
  POST /api/test-call             Trigger a test call with a WAV file path
  WS   /ws/call/{session_id}      Main voice call WebSocket
  WS   /ws/emr                    Live EMR update feed for the React dashboard
"""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bolna_layer.audio_utils import wav_to_pcm, split_into_frames
from bolna_layer.orchestrator import BolnaOrchestrator
from config import settings
from database import (
    init_db,
    get_appointments,
    get_appointment,
    get_handoffs,
    create_appointment,
    flag_for_handoff,
)
from langgraph_agent.nodes import inject_dependencies
from services.llm_service import EvonLLMService

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Global state ───────────────────────────────────────────────────────────────

# Set of active /ws/emr subscribers (dashboard WebSockets)
emr_subscribers: Set[WebSocket] = set()

# Shared LLM service (stateless — safe to share across sessions)
llm_service: EvonLLMService = None  # type: ignore


# ── EMR broadcast helper ───────────────────────────────────────────────────────

async def broadcast_emr_update(data: dict) -> None:
    """
    Push a JSON event to all connected /ws/emr dashboard clients.
    Dead connections are removed automatically.
    """
    if not emr_subscribers:
        return
    payload = json.dumps(data)
    dead = set()
    for ws in list(emr_subscribers):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    emr_subscribers.difference_update(dead)


def sync_broadcast(data: dict) -> None:
    """
    Synchronous wrapper — called from BolnaOrchestrator which runs inside
    an asyncio event loop.  Schedules broadcast_emr_update as a coroutine.
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(broadcast_emr_update(data))


# ── App lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("SahayaVaani %s starting up...", settings.app_version)
    await init_db()
    logger.info("SQLite EMR database initialised at %s", settings.db_path)

    global llm_service
    llm_service = EvonLLMService()

    # Wire LLM service and DB helpers into the LangGraph nodes
    inject_dependencies(
        llm_service=llm_service,
        db_create_fn=create_appointment,
        db_flag_fn=flag_for_handoff,
    )
    logger.info("LangGraph dependencies injected")

    yield

    # Shutdown
    logger.info("SahayaVaani shutting down...")


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SahayaVaani",
    version=settings.app_version,
    description="Kannada/Kanglish hospital front-desk voice agent API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST endpoints ─────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def health_check():
    return {
        "status":  "ok",
        "app":     settings.app_name,
        "version": settings.app_version,
    }


@app.get("/api/appointments", tags=["emr"])
async def list_appointments(limit: int = 100):
    appointments = await get_appointments(limit=limit)
    return [a.to_dict() for a in appointments]


@app.get("/api/appointments/{appointment_id}", tags=["emr"])
async def get_one_appointment(appointment_id: int):
    appt = await get_appointment(appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt.to_dict()


@app.get("/api/handoffs", tags=["emr"])
async def list_handoffs(limit: int = 50):
    handoffs = await get_handoffs(limit=limit)
    return [h.to_dict() for h in handoffs]


class TestCallRequest(BaseModel):
    wav_path: str
    patient_name: str = "Demo Patient"


@app.post("/api/test-call", tags=["testing"])
async def test_call(req: TestCallRequest):
    """
    Trigger a demo call by reading a local WAV file and running it through
    the full pipeline. Useful for CI/CD demos without a real microphone.
    """
    wav_file = Path(req.wav_path)
    if not wav_file.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {req.wav_path}")

    session_id = f"test-{uuid.uuid4().hex[:8]}"
    pcm_bytes   = wav_to_pcm(wav_file.read_bytes())

    # Run STT directly
    from services.stt_service import GnaniSTTService
    stt = GnaniSTTService()
    result = await stt.transcribe_once(pcm_bytes)

    return {
        "session_id":  session_id,
        "transcript":  result.transcript,
        "confidence":  result.confidence,
        "wav_path":    str(wav_file),
        "pcm_bytes":   len(pcm_bytes),
    }


# ── WebSocket: Main voice call ─────────────────────────────────────────────────

@app.websocket("/ws/call/{session_id}")
async def call_websocket(websocket: WebSocket, session_id: str):
    """
    Main voice call WebSocket.

    Binary messages in  → PCM 16-bit 16kHz audio frames from patient
    Text messages out   → JSON events (transcript, state, etc.)
    Binary messages out → PCM audio frames from TTS (agent voice)
    """
    await websocket.accept()
    logger.info("[WS/call] New session: %s", session_id)

    orchestrator = BolnaOrchestrator(
        session_id=session_id,
        websocket=websocket,
        emr_broadcast=sync_broadcast,
    )

    try:
        await orchestrator.run_session()
    except WebSocketDisconnect:
        logger.info("[WS/call] Client disconnected: %s", session_id)
    except Exception as exc:
        logger.error("[WS/call] Unhandled error in session %s: %s", session_id, exc, exc_info=True)
    finally:
        logger.info("[WS/call] Session closed: %s", session_id)


# ── WebSocket: EMR live feed ───────────────────────────────────────────────────

@app.websocket("/ws/emr")
async def emr_websocket(websocket: WebSocket):
    """
    Live EMR update feed.
    Dashboard connects here and receives JSON events when appointments change.
    """
    await websocket.accept()
    emr_subscribers.add(websocket)
    logger.info("[WS/emr] Dashboard connected. Total subscribers: %d", len(emr_subscribers))

    # Send current appointments immediately on connect
    appointments = await get_appointments()
    await websocket.send_text(json.dumps({
        "type":         "initial_load",
        "appointments": [a.to_dict() for a in appointments],
    }))

    try:
        while True:
            # Keep-alive: wait for any message from client (e.g. ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        logger.info("[WS/emr] Dashboard disconnected")
    finally:
        emr_subscribers.discard(websocket)


# ── Entry point for direct execution ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
