"""
Tests for SahayaVaani Bolna Orchestration Layer:
  - WebSocket event protocol (transcript, agent_response, tts_done, state_change, session_start, session_end)
  - VAD speech buffering and end-of-utterance trigger
  - Instant transcript streaming before LLM invocation
  - Error recovery with Kanglish repeat prompts
  - Session lifecycle and EMR broadcast integration
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bolna_layer.orchestrator import BolnaOrchestrator
from langgraph_agent.state import AgentState
from tests.conftest import MockLLMService


class MockWebSocket:
    """Mock WebSocket for inspecting Bolna JSON messages and binary audio packets."""

    def __init__(self):
        self.sent_text_messages = []
        self.sent_binary_chunks = []
        self._receive_queue = asyncio.Queue()

    async def send_text(self, text: str):
        self.sent_text_messages.append(json.loads(text))

    async def send_bytes(self, data: bytes):
        self.sent_binary_chunks.append(data)

    async def receive_bytes(self) -> bytes:
        return await self._receive_queue.get()

    def get_events_by_type(self, event_type: str):
        return [msg for msg in self.sent_text_messages if msg.get("type") == event_type]


class TestBolnaOrchestrator:

    @pytest.fixture
    def mock_ws(self):
        return MockWebSocket()

    @pytest.fixture
    def orchestrator(self, mock_ws):
        return BolnaOrchestrator(
            session_id="test_session_orch_101",
            websocket=mock_ws,
        )

    @pytest.mark.asyncio
    async def test_send_json_formats_event(self, orchestrator, mock_ws):
        """Verify _send_json constructs valid JSON control payloads with the right event type."""
        await orchestrator._send_json("state_change", {"node": "slot_filling", "intent": "book_appointment"})
        events = mock_ws.get_events_by_type("state_change")
        assert len(events) == 1
        assert events[0]["node"] == "slot_filling"
        assert events[0]["intent"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_send_audio_transmits_non_empty(self, orchestrator, mock_ws):
        """Non-empty PCM binary chunks must be forwarded to the client."""
        sample_audio = b"\x00\x10" * 160
        await orchestrator._send_audio(sample_audio)
        assert len(mock_ws.sent_binary_chunks) == 1
        assert mock_ws.sent_binary_chunks[0] == sample_audio

    @pytest.mark.asyncio
    async def test_send_audio_ignores_empty(self, orchestrator, mock_ws):
        """Zero-byte or empty packets should not be dispatched."""
        await orchestrator._send_audio(b"")
        assert len(mock_ws.sent_binary_chunks) == 0

    @pytest.mark.asyncio
    async def test_speak_protocol_sequence(self, orchestrator, mock_ws):
        """
        _speak() must:
          1. Send 'agent_response' JSON text
          2. Stream binary audio chunks
          3. Send 'tts_done' JSON marker for frontend synchronization
        """
        async def mock_synth(text):
            yield b"PCM_CHUNK_1"
            yield b"PCM_CHUNK_2"

        with patch.object(orchestrator.tts, "synthesize", side_effect=mock_synth):
            await orchestrator._speak("Namaskara! Hegiddira?")

        # 1. agent_response
        agent_events = mock_ws.get_events_by_type("agent_response")
        assert len(agent_events) == 1
        assert agent_events[0]["text"] == "Namaskara! Hegiddira?"

        # 2. binary audio
        assert mock_ws.sent_binary_chunks == [b"PCM_CHUNK_1", b"PCM_CHUNK_2"]

        # 3. tts_done marker
        tts_done_events = mock_ws.get_events_by_type("tts_done")
        assert len(tts_done_events) == 1
        assert tts_done_events[0]["text"] == "Namaskara! Hegiddira?"

    @pytest.mark.asyncio
    async def test_collect_utterance_timeout_returns_none(self, orchestrator, mock_ws):
        """If user sends no audio within timeout, return None cleanly without uncaught exceptions."""
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await orchestrator._collect_utterance()
            assert result is None

    @pytest.mark.asyncio
    async def test_collect_utterance_vad_detection(self, orchestrator, mock_ws):
        """When VAD detects end of utterance, speech buffer is returned and listening:end event sent."""
        # Setup mock VAD behavior
        orchestrator.vad.end_of_utterance_detected = MagicMock(side_effect=[False, True])
        orchestrator.vad.get_speech_buffer = MagicMock(return_value=b"UTTERANCE_PCM_DATA")

        await mock_ws._receive_queue.put(b"\x10\x00" * 320)
        await mock_ws._receive_queue.put(b"\x20\x00" * 320)

        speech = await orchestrator._collect_utterance()
        assert speech == b"UTTERANCE_PCM_DATA"

        listening_events = mock_ws.get_events_by_type("listening")
        assert len(listening_events) >= 2
        assert listening_events[0]["status"] == "start"
        assert listening_events[-1]["status"] == "end"

    @pytest.mark.asyncio
    async def test_transcribe_streams_partial_and_ensures_final(self, orchestrator, mock_ws):
        """STT results must stream partials to UI and dispatch a final event before LLM execution."""
        async def mock_stream(queue):
            yield {"text": "Namaskara", "confidence": 0.85, "is_final": False}
            yield {"text": "Namaskara doctor beku", "confidence": 0.95, "is_final": True}

        with patch.object(orchestrator.stt, "transcribe_stream", side_effect=mock_stream):
            transcript, confidence = await orchestrator._transcribe(b"\x00" * 3200)

        assert transcript == "Namaskara doctor beku"
        assert confidence == 0.95

        transcript_events = mock_ws.get_events_by_type("transcript")
        assert len(transcript_events) == 2
        assert transcript_events[0]["is_final"] is False
        assert transcript_events[1]["is_final"] is True

    @pytest.mark.asyncio
    async def test_run_graph_initial_turn_seeding(self, orchestrator, mock_ws):
        """First turn seeds initial conversation history including the receptionist greeting."""
        mock_return_state: AgentState = {
            "session_id": orchestrator.session_id,
            "transcript": "Cardiology doctor beku",
            "full_transcript": ["Agent: greeting", "Patient: Cardiology doctor beku"],
            "messages": [],
            "confidence_score": 0.95,
            "needs_repeat": False,
            "intent": "book_appointment",
            "patient_name": None,
            "department": "Cardiology",
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": ["patient_name", "appointment_date", "appointment_time"],
            "response_text": "Nimma hesaru enu?",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": "slot_filling",
        }

        with patch("bolna_layer.orchestrator.agent_graph.ainvoke", AsyncMock(return_value=mock_return_state)):
            state = await orchestrator._run_graph("Cardiology doctor beku", 0.95)

        assert state["department"] == "Cardiology"
        assert state["current_node"] == "slot_filling"

        # Check state change messages
        state_events = mock_ws.get_events_by_type("state_change")
        assert any(e.get("node") == "processing" for e in state_events)
        assert any(e.get("node") == "slot_filling" for e in state_events)

    @pytest.mark.asyncio
    async def test_run_graph_exception_fallback(self, orchestrator, mock_ws):
        """If LangGraph throws an unexpected error, orchestrator returns Kanglish fallback without crashing."""
        with patch("bolna_layer.orchestrator.agent_graph.ainvoke", AsyncMock(side_effect=RuntimeError("LLM rate limit"))):
            fallback_state = await orchestrator._run_graph("hello", 0.95)

        assert fallback_state is not None
        assert fallback_state["is_complete"] is False
        assert fallback_state["needs_repeat"] is True
        assert "kelisalilla" in fallback_state["response_text"]

        error_events = mock_ws.get_events_by_type("error")
        assert len(error_events) == 1
        assert "LLM rate limit" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_run_session_greeting_and_clean_exit(self, orchestrator, mock_ws):
        """Session lifecycle: starts with greeting, loops speech, and ends cleanly when is_complete=True."""
        # Mock 1 turn of speech
        fake_audio = b"\x10\x00" * 2000
        orchestrator._collect_utterance = AsyncMock(side_effect=[fake_audio, None])
        orchestrator._transcribe = AsyncMock(return_value=("Dhanyavada, ashte", 0.95))

        mock_final_state = {
            "response_text": "Dhanyavada! Shubhavaagali.",
            "is_complete": True,
            "current_node": "small_talk",
            "db_appointment_id": None,
        }
        orchestrator._run_graph = AsyncMock(return_value=mock_final_state)
        orchestrator._speak = AsyncMock()

        await orchestrator.run_session()

        # Check session start event
        start_events = mock_ws.get_events_by_type("session_start")
        assert len(start_events) == 1
        assert start_events[0]["session_id"] == orchestrator.session_id

        # Check session end event
        end_events = mock_ws.get_events_by_type("session_end")
        assert len(end_events) == 1
        assert end_events[0]["outcome"] == "small_talk"

    @pytest.mark.asyncio
    async def test_run_session_silence_repeat_counter(self, orchestrator, mock_ws):
        """Empty transcript triggers REPEAT_REQUEST_TEXT and increments repeat attempts."""
        fake_audio = b"\x10\x00" * 2000
        orchestrator._collect_utterance = AsyncMock(side_effect=[fake_audio, None])
        orchestrator._transcribe = AsyncMock(return_value=("", 0.0))  # pure silence
        orchestrator._speak = AsyncMock()

        await orchestrator.run_session()

        assert orchestrator._repeat_attempts == 1
        assert orchestrator._speak.call_count >= 2  # greeting + repeat request

    @pytest.mark.asyncio
    async def test_run_session_emr_broadcast_callback(self, mock_ws):
        """When an appointment is confirmed in state, orchestrator invokes emr_broadcast callback."""
        broadcast_mock = MagicMock()
        orch = BolnaOrchestrator(
            session_id="test_session_emr_push",
            websocket=mock_ws,
            emr_broadcast=broadcast_mock,
        )

        fake_audio = b"\x10\x00" * 2000
        orch._collect_utterance = AsyncMock(side_effect=[fake_audio, None])
        orch._transcribe = AsyncMock(return_value=("Confirm naale", 0.95))

        mock_booking_state = {
            "response_text": "Nimma appointment confirm aagide.",
            "is_complete": True,
            "current_node": "confirm_booking",
            "db_appointment_id": 99,
        }
        orch._run_graph = AsyncMock(return_value=mock_booking_state)
        orch._speak = AsyncMock()

        await orch.run_session()

        broadcast_mock.assert_called_once_with({
            "type": "appointment_created",
            "appointment_id": 99,
            "session_id": "test_session_emr_push",
        })
