"""
Tests for SahayaVaani LangGraph State Machine Workflow:
  - Graph compilation and node registration
  - Conditional edge routing (intent, safety, slots)
  - Multi-turn conversation DAG execution with MemorySaver checkpointer
  - Symptom routing vs. medical advice escalation
  - Booking confirmation and non-blocking session continuation
  - Thread state isolation between concurrent sessions
"""
import pytest
from unittest.mock import AsyncMock

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END

from langgraph_agent.graph import (
    agent_graph,
    build_graph,
    route_after_intent,
    route_after_safety,
    route_after_slots,
)
from langgraph_agent.nodes import inject_dependencies
from langgraph_agent.state import AgentState
from tests.conftest import MockLLMService


@pytest.fixture(autouse=True)
def setup_dependencies():
    """Inject mock LLM and mock DB operations for all workflow tests."""
    mock_llm = MockLLMService()
    mock_appt = AsyncMock()
    mock_appt.id = 42
    mock_db_create = AsyncMock(return_value=mock_appt)
    mock_handoff = AsyncMock()
    mock_handoff.id = 101
    mock_db_flag = AsyncMock(return_value=mock_handoff)

    inject_dependencies(mock_llm, mock_db_create, mock_db_flag)
    yield


class TestLangGraphWorkflow:

    def test_graph_nodes_registered(self):
        """Verify all 7 nodes and start/end boundaries are properly compiled into the graph."""
        nodes = agent_graph.nodes
        expected_nodes = {
            "greeting",
            "intent_classifier",
            "small_talk",
            "safety_check",
            "slot_filling",
            "confirm_booking",
            "escalate_human",
        }
        for node in expected_nodes:
            assert node in nodes, f"Expected node '{node}' not found in compiled graph nodes"

    def test_route_after_intent_logic(self):
        """Test conditional branching directly after intent_classifier node."""
        # Low confidence -> repeat
        assert route_after_intent({"needs_repeat": True, "intent": "greeting"}) == END

        # Greeting, farewell, general questions -> small_talk
        assert route_after_intent({"needs_repeat": False, "intent": "greeting"}) == "small_talk"
        assert route_after_intent({"needs_repeat": False, "intent": "farewell"}) == "small_talk"
        assert route_after_intent({"needs_repeat": False, "intent": "other"}) == "small_talk"

        # Booking intents -> safety_check
        assert route_after_intent({"needs_repeat": False, "intent": "book_appointment"}) == "safety_check"

    def test_route_after_safety_logic(self):
        """Test conditional branching after safety_check node."""
        # Medical advice query -> human escalation
        assert route_after_safety({"intent": "medical_question"}) == "escalate_human"

        # Booking requests -> slot filling
        assert route_after_safety({"intent": "book_appointment"}) == "slot_filling"

    def test_route_after_slots_logic(self):
        """Test conditional branching after slot_filling node."""
        # If missing slots remain -> END turn to ask patient
        assert route_after_slots({"missing_slots": ["appointment_date"]}) == END

        # If all slots filled -> confirm_booking
        assert route_after_slots({"missing_slots": []}) == "confirm_booking"

    @pytest.mark.asyncio
    async def test_greeting_turn_execution(self):
        """Turn 1: Patient says 'Namaskara' -> routes to small_talk -> ends turn cleanly."""
        graph = build_graph()
        config = {"configurable": {"thread_id": "test_workflow_greet"}}

        initial_state: AgentState = {
            "session_id": "test_workflow_greet",
            "transcript": "Namaskara",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Namaskara"],
            "messages": [{"role": "user", "content": "Namaskara"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }

        result = await graph.ainvoke(initial_state, config=config)

        assert result["intent"] == "greeting"
        assert result["current_node"] == "small_talk"
        assert result["is_complete"] is False
        assert len(result["response_text"]) > 0

    @pytest.mark.asyncio
    async def test_farewell_turn_completes_session(self):
        """Patient says farewell -> routes to small_talk and sets is_complete=True."""
        graph = build_graph()
        config = {"configurable": {"thread_id": "test_workflow_bye"}}

        state: AgentState = {
            "session_id": "test_workflow_bye",
            "transcript": "Dhanyavada, ashte",
            "confidence_score": 0.92,
            "full_transcript": ["Patient: Dhanyavada, ashte"],
            "messages": [{"role": "user", "content": "Dhanyavada, ashte"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }

        result = await graph.ainvoke(state, config=config)

        assert result["intent"] == "farewell"
        assert result["is_complete"] is True
        assert len(result["response_text"]) > 0

    @pytest.mark.asyncio
    async def test_low_confidence_stt_loops_repeat(self):
        """STT confidence < 0.8 triggers needs_repeat=True and exits at intent_classifier."""
        graph = build_graph()
        config = {"configurable": {"thread_id": "test_workflow_low_conf"}}

        state: AgentState = {
            "session_id": "test_workflow_low_conf",
            "transcript": "mumble",
            "confidence_score": 0.45,
            "full_transcript": ["Patient: mumble"],
            "messages": [{"role": "user", "content": "mumble"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }

        result = await graph.ainvoke(state, config=config)

        assert result["needs_repeat"] is True
        assert result["current_node"] == "intent_classifier"
        assert result["is_complete"] is False

    @pytest.mark.asyncio
    async def test_medical_advice_query_escalates_without_booking(self):
        """Prescription question triggers safety guardrail and routes to escalate_human."""
        graph = build_graph()
        config = {"configurable": {"thread_id": "test_workflow_med_escalate"}}

        state: AgentState = {
            "session_id": "test_workflow_med_escalate",
            "transcript": "Fever ide, yava tablet togobeku dosage eshtu?",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Fever ide, yava tablet togobeku dosage eshtu?"],
            "messages": [{"role": "user", "content": "Fever ide, yava tablet togobeku dosage eshtu?"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }

        result = await graph.ainvoke(state, config=config)

        assert result["current_node"] == "escalate_human"
        assert result["intent"] == "book_appointment"
        # Keeps session alive so patient can book a consultation
        assert result["is_complete"] is False

    @pytest.mark.asyncio
    async def test_symptom_inquiry_proceeds_to_slot_filling(self):
        """Mentioning chest pain or fever for booking goes to slot_filling, not medical escalation."""
        graph = build_graph()
        config = {"configurable": {"thread_id": "test_workflow_symptom_book"}}

        state: AgentState = {
            "session_id": "test_workflow_symptom_book",
            "transcript": "Nanna heart pain ide, appointment beku cardiology ge",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Nanna heart pain ide, appointment beku cardiology ge"],
            "messages": [{"role": "user", "content": "Nanna heart pain ide, appointment beku cardiology ge"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }

        result = await graph.ainvoke(state, config=config)

        assert result["intent"] == "book_appointment"
        assert result["current_node"] == "slot_filling"
        assert result["department"] == "Cardiology"
        assert "patient_name" in result["missing_slots"]

    @pytest.mark.asyncio
    async def test_full_multiturn_booking_flow(self):
        """
        Execute an end-to-end multi-turn conversation with state preservation:
          Turn 1: 'Doctor appointment beku for cardiology' -> asks for name
          Turn 2: 'Nanna hesaru Suresh' -> asks for date/time
          Turn 3: 'Naale 10:00 AM' -> confirms booking and persists in DB
        """
        graph = build_graph()
        thread_id = "test_multiturn_full_flow"
        config = {"configurable": {"thread_id": thread_id}}

        # ── Turn 1: Department specified ──
        turn1_input: AgentState = {
            "session_id": thread_id,
            "transcript": "Cardiology doctor appointment beku",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Cardiology doctor appointment beku"],
            "messages": [{"role": "user", "content": "Cardiology doctor appointment beku"}],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }
        state1 = await graph.ainvoke(turn1_input, config=config)
        assert state1["department"] == "Cardiology"
        assert "patient_name" in state1["missing_slots"]

        # ── Turn 2: Patient Name provided ──
        turn2_input = {
            "transcript": "Nanna hesaru Suresh",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Nanna hesaru Suresh"],
            "messages": [{"role": "user", "content": "Nanna hesaru Suresh"}],
        }
        state2 = await graph.ainvoke(turn2_input, config=config)
        assert state2["department"] == "Cardiology"
        assert state2["patient_name"] == "Suresh"
        assert "appointment_date" in state2["missing_slots"] or "appointment_time" in state2["missing_slots"]

        # ── Turn 3: Date & Time provided ──
        turn3_input = {
            "transcript": "Naale 10 AM ge book maadi",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Naale 10 AM ge book maadi"],
            "messages": [{"role": "user", "content": "Naale 10 AM ge book maadi"}],
        }
        state3 = await graph.ainvoke(turn3_input, config=config)
        assert state3["current_node"] == "confirm_booking"
        assert state3["db_appointment_id"] is not None
        assert state3["missing_slots"] == []
        # Crucial requirement: Call stays open for further queries
        assert state3["is_complete"] is False

    @pytest.mark.asyncio
    async def test_session_continuation_after_confirmation(self):
        """After booking is confirmed, user asks hospital timings -> handled smoothly."""
        graph = build_graph()
        thread_id = "test_continuation_flow"
        config = {"configurable": {"thread_id": thread_id}}

        # Seed fully confirmed state
        pre_state: AgentState = {
            "session_id": thread_id,
            "transcript": "Confirm booking",
            "confidence_score": 0.95,
            "full_transcript": [],
            "messages": [],
            "needs_repeat": False,
            "intent": "book_appointment",
            "patient_name": "Kavitha",
            "department": "Orthopedics",
            "appointment_date": "2026-11-10",
            "appointment_time": "11:00 AM",
            "phone_number": "9876543210",
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": 42,
            "current_node": "confirm_booking",
        }
        await graph.ainvoke(pre_state, config=config)

        # Follow-up inquiry: hospital timing
        followup_input = {
            "transcript": "Hospital yavaga open irutte?",
            "confidence_score": 0.95,
            "full_transcript": ["Patient: Hospital yavaga open irutte?"],
            "messages": [{"role": "user", "content": "Hospital yavaga open irutte?"}],
        }
        followup_state = await graph.ainvoke(followup_input, config=config)
        assert followup_state["intent"] == "other"
        assert followup_state["current_node"] == "small_talk"
        assert followup_state["is_complete"] is False

    @pytest.mark.asyncio
    async def test_thread_state_isolation(self):
        """Verify two simultaneous sessions have independent MemorySaver state."""
        graph = build_graph()
        config_a = {"configurable": {"thread_id": "session_user_A"}}
        config_b = {"configurable": {"thread_id": "session_user_B"}}

        state_a = await graph.ainvoke({
            "session_id": "session_user_A",
            "transcript": "Cardiology appointment Suresh",
            "confidence_score": 0.95,
            "full_transcript": [],
            "messages": [],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }, config=config_a)

        state_b = await graph.ainvoke({
            "session_id": "session_user_B",
            "transcript": "Orthopedics appointment Rekha",
            "confidence_score": 0.95,
            "full_transcript": [],
            "messages": [],
            "needs_repeat": False,
            "intent": None,
            "patient_name": None,
            "department": None,
            "appointment_date": None,
            "appointment_time": None,
            "phone_number": None,
            "missing_slots": [],
            "response_text": "",
            "audio_chunks": [],
            "is_complete": False,
            "error": None,
            "db_appointment_id": None,
            "current_node": None,
        }, config=config_b)

        assert state_a["patient_name"] == "Suresh"
        assert state_a["department"] == "Cardiology"

        assert state_b["patient_name"] == "Rekha"
        assert state_b["department"] == "Orthopedics"
