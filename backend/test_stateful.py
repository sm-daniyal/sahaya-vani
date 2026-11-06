import sys
import asyncio

sys.path.insert(0, ".")

from langgraph_agent.state import AgentState
from langgraph_agent.nodes import inject_dependencies
from langgraph_agent.graph import agent_graph

class MockLLM:
    async def extract_slots(self, transcript, today, history=None, current_slots=None):
        print(f"  [MockLLM.extract_slots] tx={transcript}", flush=True)
        slots = {}
        t = transcript.lower()
        if "cardiology" in t:
            slots["department"] = "Cardiology"
        if "daniyal" in t:
            slots["patient_name"] = "Daniyal"
        if "tomorrow" in t or "naale" in t:
            slots["date"] = "2026-11-06"
        if "10" in t:
            slots["time"] = "10:00"
        return slots

    async def generate_response(self, prompt, context=None, history=None):
        print(f"  [MockLLM.generate_response] context={context}", flush=True)
        return "Dynamic question based on context"

    async def classify_intent(self, transcript, history=None):
        print(f"  [MockLLM.classify_intent] tx={transcript}", flush=True)
        return "book_appointment"

    async def safety_check(self, transcript, intent):
        return "NO"

async def mock_db_create(**kwargs):
    class Appt:
        id = 42
    return Appt()

async def test_multi_turn():
    print("Initializing test...", flush=True)
    mock_llm = MockLLM()
    inject_dependencies(mock_llm, mock_db_create, None)

    session_id = "test-session-stateful"
    config = {"configurable": {"thread_id": session_id}}

    print("--- Starting Turn 1 ---", flush=True)
    state_turn1 = await agent_graph.ainvoke({
        "session_id": session_id,
        "transcript": "I need an appointment for Cardiology",
        "confidence_score": 0.95,
        "messages": [{"role": "user", "content": "I need an appointment for Cardiology"}],
        "full_transcript": ["Patient: I need an appointment for Cardiology"],
    }, config=config)

    print("Turn 1 department:", state_turn1.get("department"), flush=True)
    print("Turn 1 missing_slots:", state_turn1.get("missing_slots"), flush=True)
    assert state_turn1.get("department") == "Cardiology"
    assert "patient_name" in state_turn1.get("missing_slots")
    assert state_turn1.get("missing_slots")[0] == "patient_name"
    assert state_turn1.get("is_complete") is False

    print("--- Starting Turn 2 ---", flush=True)
    state_turn2 = await agent_graph.ainvoke({
        "transcript": "My name is Daniyal",
        "confidence_score": 0.95,
        "messages": [{"role": "user", "content": "My name is Daniyal"}],
        "full_transcript": ["Patient: My name is Daniyal"],
    }, config=config)

    print("Turn 2 patient_name:", state_turn2.get("patient_name"), flush=True)
    print("Turn 2 department preserved:", state_turn2.get("department"), flush=True)
    print("Turn 2 missing_slots:", state_turn2.get("missing_slots"), flush=True)
    assert state_turn2.get("patient_name") == "Daniyal"
    assert state_turn2.get("department") == "Cardiology"
    assert "patient_name" not in state_turn2.get("missing_slots")
    assert state_turn2.get("missing_slots")[0] == "appointment_date"

    print("--- Starting Turn 3 ---", flush=True)
    state_turn3 = await agent_graph.ainvoke({
        "transcript": "Tomorrow",
        "confidence_score": 0.95,
        "messages": [{"role": "user", "content": "Tomorrow"}],
        "full_transcript": ["Patient: Tomorrow"],
    }, config=config)

    print("Turn 3 date:", state_turn3.get("appointment_date"), flush=True)
    print("Turn 3 missing_slots:", state_turn3.get("missing_slots"), flush=True)
    assert state_turn3.get("appointment_date") == "2026-11-06"
    assert state_turn3.get("missing_slots")[0] == "appointment_time"

    print("--- Starting Turn 4 ---", flush=True)
    state_turn4 = await agent_graph.ainvoke({
        "transcript": "10 AM",
        "confidence_score": 0.95,
        "messages": [{"role": "user", "content": "10 AM"}],
        "full_transcript": ["Patient: 10 AM"],
    }, config=config)

    print("Turn 4 time:", state_turn4.get("appointment_time"), flush=True)
    print("Turn 4 is_complete:", state_turn4.get("is_complete"), flush=True)
    print("Turn 4 db_appointment_id:", state_turn4.get("db_appointment_id"), flush=True)
    assert state_turn4.get("appointment_time") == "10:00"
    assert state_turn4.get("is_complete") is True
    assert state_turn4.get("db_appointment_id") == 42
    assert state_turn4.get("current_node") == "confirm_booking"

    print("STATEFUL MULTI-TURN TEST PASSED WITH FLYING COLORS!", flush=True)

asyncio.run(test_multi_turn())
