"""
SahayaVaani — Bolna Orchestration Layer
Handles the messy reality of Indian phone calls:
  • Noise-gating (simulated pre-processing)
  • WebRTC VAD-based end-of-utterance detection
  • Low-confidence fallback ("please repeat")
  • Multi-turn LangGraph session management
  • Real-time TTS audio streaming back to client

This layer sits between the FastAPI WebSocket handler (main.py) and the
LangGraph state machine (langgraph_agent/graph.py).

                 ┌─────────────────────────────────┐
   browser WS   │       BolnaOrchestrator          │   Gnani APIs
  ─────────────►│  VAD → STT → LangGraph → TTS    │──────────────►
  ◄─────────────│  (audio in)         (audio out)  │
                └─────────────────────────────────┘
"""
import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from fastapi import WebSocket

from bolna_layer.audio_utils import apply_noise_gate, normalize_audio, split_into_frames
from config import settings
from langgraph_agent.graph import agent_graph
from langgraph_agent.state import AgentState
from services.stt_service import GnaniSTTService
from services.tts_service import GnaniTTSService
from services.vad_service import VADService

logger = logging.getLogger(__name__)

# Type alias for the EMR broadcast callback
EMRBroadcastFn = Callable[[Dict[str, Any]], None]


class BolnaOrchestrator:
    """
    Per-session orchestrator.  One instance per WebSocket connection.

    Lifecycle:
        1. `__init__`      — Set up services, graph config
        2. `run_session()` — Main async loop (called once per connection)
        3. (cleanup)       — WebSocket closed by client or server
    """

    MAX_REPEAT_ATTEMPTS = 2   # How many times we ask the patient to repeat

    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        emr_broadcast: Optional[EMRBroadcastFn] = None,
    ):
        self.session_id    = session_id
        self.websocket     = websocket
        self.emr_broadcast = emr_broadcast  # callback to push live EMR updates

        # Services (created fresh per session for connection isolation)
        self.stt = GnaniSTTService()
        self.tts = GnaniTTSService()
        self.vad = VADService()

        # LangGraph thread config (enables MemorySaver per-session checkpointing)
        self.graph_config = {"configurable": {"thread_id": session_id}}

        # Session state
        self._repeat_attempts = 0
        self._graph_state: Optional[AgentState] = None

    # ── WebSocket helpers ──────────────────────────────────────────────────────

    async def _send_json(self, event_type: str, data: Dict[str, Any]) -> None:
        """Send a JSON control event to the browser."""
        payload = json.dumps({"type": event_type, **data})
        try:
            await self.websocket.send_text(payload)
        except Exception as exc:
            logger.debug("[Bolna] send_json failed: %s", exc)

    async def _send_audio(self, audio_bytes: bytes) -> None:
        """Send binary PCM audio to the browser for playback."""
        if audio_bytes:
            try:
                await self.websocket.send_bytes(audio_bytes)
            except Exception as exc:
                logger.debug("[Bolna] send_audio failed: %s", exc)

    # ── TTS helper ─────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """
        Synthesise `text` via Gnani Timbre TTS and stream audio chunks back
        to the browser over the WebSocket.
        Also notifies the frontend about the agent's response text.
        """
        if not text:
            return
        logger.info("[Bolna] TTS: %r", text[:80])
        await self._send_json("agent_response", {
            "text":        text,
            "node":        self._graph_state.get("current_node") if self._graph_state else None,
        })
        async for chunk in self.tts.synthesize(text):
            await self._send_audio(chunk)
        # Send end-of-audio marker so frontend knows playback is done
        await self._send_json("tts_done", {"text": text})

    # ── Audio ingestion (from browser) ────────────────────────────────────────

    async def _collect_utterance(self) -> Optional[bytes]:
        """
        Receive PCM frames from the browser WebSocket, apply noise gate,
        and use VAD to detect the end of a patient utterance.

        Returns:
            Raw PCM bytes of the full utterance, or None if the connection closed.
        """
        self.vad.reset()
        accumulated: list[bytes] = []
        logger.info("[Bolna] Listening for patient speech (VAD silence threshold: 800ms)...")
        await self._send_json("listening", {"status": "start"})

        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        self.websocket.receive_bytes(),
                        timeout=120.0,  # 120 s timeout allows full patient conversation without premature hangup
                    )
                except asyncio.TimeoutError:
                    logger.warning("[Bolna] 120 s timeout — no audio received")
                    return None

                if not data:
                    continue

                # ── Pre-processing (Bolna Layer) ───────────────────────────────
                data = apply_noise_gate(data, threshold=settings.noise_gate_threshold)

                # ── VAD ───────────────────────────────────────────────────────
                self.vad.process_bytes(data)
                accumulated.append(data)

                if self.vad.end_of_utterance_detected():
                    logger.info("[Bolna] End-of-utterance detected (800ms silence elapsed)")
                    await self._send_json("listening", {"status": "end"})
                    return self.vad.get_speech_buffer()

        except Exception as exc:
            logger.error("[Bolna] _collect_utterance error: %s", exc)
            return None

    # ── STT ────────────────────────────────────────────────────────────────────

    async def _transcribe(self, pcm_bytes: bytes) -> tuple[str, float]:
        """
        Send PCM to Gnani STT and return (transcript, confidence).
        Streams partial results to the frontend for live display.
        """
        q: asyncio.Queue = asyncio.Queue()
        for frame in split_into_frames(pcm_bytes, settings.frame_size):
            await q.put(frame)
        await q.put(None)  # end sentinel

        transcript = ""
        confidence = 0.0
        sent_final = False

        async for result in self.stt.transcribe_stream(q):
            if isinstance(result, dict):
                transcript = result.get("text", "") or result.get("transcript", "")
                confidence = float(result.get("confidence", 0.95))
                is_final = bool(result.get("is_final", True))
            else:
                transcript = getattr(result, "transcript", "")
                confidence = getattr(result, "confidence", 0.0)
                is_final = getattr(result, "is_final", False)

            if transcript:
                if is_final:
                    sent_final = True
                # Stream partials to frontend
                await self._send_json("transcript", {
                    "text":       transcript,
                    "confidence": confidence,
                    "is_final":   is_final,
                })

        # Ensure final transcript event is dispatched once before LLM processing
        if transcript.strip() and not sent_final:
            await self._send_json("transcript", {
                "text":       transcript.strip(),
                "confidence": confidence,
                "is_final":   True,
            })

        logger.info("[Bolna] Transcript: %r (conf=%.2f)", transcript, confidence)
        return transcript.strip(), confidence

    # ── LangGraph interaction ─────────────────────────────────────────────────

    async def _run_graph(self, transcript: str, confidence: float) -> Optional[AgentState]:
        """
        Feed the latest transcript into the LangGraph state machine and
        return the updated state after the graph finishes executing.
        """
        # Build the input update (delta only).
        # LangGraph's checkpointer (MemorySaver) with operator.add automatically appends
        # this new turn to the accumulated conversation history across turns without duplication.
        graph_input: Dict[str, Any] = {
            "transcript":        transcript,
            "confidence_score":  confidence,
            "full_transcript":   [f"Patient: {transcript}"],
            "messages":          [{"role": "user", "content": transcript}],
            "audio_chunks":      [],
        }

        # On first turn, seed the full initial state including the initial greeting in history
        if self._graph_state is None:
            from langgraph_agent.prompts import GREETING_TEXT
            graph_input = {
                "session_id":       self.session_id,
                "transcript":       transcript,
                "full_transcript":  [f"Agent: {GREETING_TEXT}", f"Patient: {transcript}"],
                "messages":         [
                    {"role": "assistant", "content": GREETING_TEXT},
                    {"role": "user", "content": transcript},
                ],
                "confidence_score": confidence,
                "needs_repeat":     False,
                "intent":           None,
                "patient_name":     None,
                "department":       None,
                "appointment_date": None,
                "appointment_time": None,
                "phone_number":     None,
                "missing_slots":    [],
                "response_text":    "",
                "audio_chunks":     [],
                "is_complete":      False,
                "error":            None,
                "db_appointment_id": None,
                "current_node":     None,
            }

        logger.info("[Bolna] Invoking LangGraph...")
        await self._send_json("state_change", {"node": "processing"})

        try:
            # Use ainvoke so the whole graph runs (not streamed step-by-step here)
            new_state = await agent_graph.ainvoke(graph_input, config=self.graph_config)
            self._graph_state = new_state

            await self._send_json("state_change", {
                "node":   new_state.get("current_node"),
                "intent": new_state.get("intent"),
            })
            return new_state
        except Exception as exc:
            logger.error("[Bolna] LangGraph error: %s", exc)
            await self._send_json("error", {"message": str(exc)})
            # Return graceful fallback state so the conversation stays alive instead of quitting
            fallback_text = "Kshamisi, ondu nimisha kelisalilla. Dayavittu innomme heli."
            return {
                "response_text": fallback_text,
                "current_node":  "intent_classifier",
                "is_complete":   False,
                "needs_repeat":  True,
            }

    # ── Main Session Loop ──────────────────────────────────────────────────────

    async def run_session(self) -> None:
        """
        Main orchestration loop for a single phone/WebSocket session.

        Flow:
          1. Play greeting
          2. Loop:
             a. Collect utterance (VAD-gated)
             b. STT transcribe
             c. Low-confidence? → ask to repeat (up to MAX_REPEAT_ATTEMPTS)
             d. Run LangGraph
             e. TTS the agent response
             f. If complete → break
        """
        logger.info("[Bolna] Session started: %s", self.session_id)
        await self._send_json("session_start", {"session_id": self.session_id})

        # ── Step 1: Greeting ───────────────────────────────────────────────────
        # Run only the greeting node to get the welcome text
        from langgraph_agent.prompts import GREETING_TEXT
        await self._speak(GREETING_TEXT)
        await self._send_json("state_change", {"node": "greeting"})

        # ── Step 2: Conversation loop ──────────────────────────────────────────
        while True:
            # 2a. Collect audio utterance
            pcm = await self._collect_utterance()
            if pcm is None:
                # Connection closed or timeout
                logger.info("[Bolna] Session ended (no audio): %s", self.session_id)
                break

            if len(pcm) < 3200:  # less than 100ms of audio (empty click/pop)
                continue

            # 2b. STT
            transcript, confidence = await self._transcribe(pcm)

            # 2c. Fallback ONLY if transcript is pure silence / empty
            if not transcript:
                self._repeat_attempts += 1
                if self._repeat_attempts <= self.MAX_REPEAT_ATTEMPTS:
                    from langgraph_agent.prompts import REPEAT_REQUEST_TEXT
                    await self._speak(REPEAT_REQUEST_TEXT)
                    continue
                else:
                    logger.warning("[Bolna] Max repeat attempts reached — proceeding anyway")
                    self._repeat_attempts = 0

            # Valid speech received — reset repeat attempts
            self._repeat_attempts = 0

            # 2d. LangGraph
            state = await self._run_graph(transcript, confidence)
            if state is None:
                from langgraph_agent.prompts import REPEAT_REQUEST_TEXT
                await self._speak(REPEAT_REQUEST_TEXT)
                continue

            # 2e. TTS response
            response_text = state.get("response_text", "")
            if response_text:
                await self._speak(response_text)
            elif state.get("intent") == "side_conversation":
                # Background room chatter ignored — continue listening without interruption
                logger.info("[Bolna] Background side conversation ignored: %r", transcript)
                continue
            elif not state.get("is_complete"):
                # Safe prompt fallback if state was returned without text
                fallback = "Heli, nimage yavaru doctor beku?"
                await self._speak(fallback)

            # 2f. Broadcast EMR update if appointment was booked
            if state.get("db_appointment_id") and self.emr_broadcast:
                self.emr_broadcast({
                    "type":           "appointment_created",
                    "appointment_id": state["db_appointment_id"],
                    "session_id":     self.session_id,
                })

            # 2g. Check if session is done
            if state.get("is_complete"):
                # Allow ample time for the browser to finish playing the final farewell audio queue
                farewell_play_time = max(3.5, len(response_text) * 0.08)
                logger.info("[Bolna] Session complete: %s — waiting %.1fs for final playback...",
                            self.session_id, farewell_play_time)
                await asyncio.sleep(farewell_play_time)

                await self._send_json("session_end", {
                    "session_id":    self.session_id,
                    "appointment_id": state.get("db_appointment_id"),
                    "outcome":       state.get("current_node"),
                })
                break

        logger.info("[Bolna] Session loop exited: %s", self.session_id)
