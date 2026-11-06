"""
Unit tests for Slot Filling and Normalization.
Validates extraction of patient name, department, date, time, phone number,
and single-question multi-turn reprompting.
"""
import pytest
from langgraph_agent.nodes import slot_filling_node, inject_dependencies


class TestSlotFilling:
    @pytest.mark.asyncio
    async def test_extract_cardiology(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-1",
            "transcript": "I need to book Cardiology department",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["department"] == "Cardiology"
        assert "patient_name" in res["missing_slots"]

    @pytest.mark.asyncio
    async def test_extract_orthopedics_from_fracture(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-2",
            "transcript": "Hand fracture aagide, bone doctor nodbeku",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["department"] == "Orthopedics"

    @pytest.mark.asyncio
    async def test_extract_radiology_from_ct_scan(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-3",
            "transcript": "Doctor suggested a CT scan",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["department"] == "Radiology"

    @pytest.mark.asyncio
    async def test_extract_general_medicine_from_fever(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-4",
            "transcript": "Severe fever and cough for two days",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["department"] == "General Medicine"

    @pytest.mark.asyncio
    async def test_extract_patient_name(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-5",
            "transcript": "Patient name Ramesh Kumar",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["patient_name"] == "Ramesh Kumar"

    @pytest.mark.asyncio
    async def test_extract_tomorrow_date(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-6",
            "transcript": "Naale beligge appointment beku",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["appointment_date"] == "2026-11-07"

    @pytest.mark.asyncio
    async def test_extract_time_10am(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-7",
            "transcript": "Morning 10 o clock",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["appointment_time"] == "10:00"

    @pytest.mark.asyncio
    async def test_extract_phone_number(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-8",
            "transcript": "My mobile number is 9876543210",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["phone_number"] == "9876543210"

    @pytest.mark.asyncio
    async def test_multiturn_state_retention_name_and_dept(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        # Prior state already had department
        prior_state = {
            "session_id": "test-sf-9",
            "department": "Cardiology",
            "transcript": "Patient hesaru Ramesh Kumar",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(prior_state)
        # Should keep department and add patient_name
        assert res["department"] == "Cardiology"
        assert res["patient_name"] == "Ramesh Kumar"

    @pytest.mark.asyncio
    async def test_multiturn_state_retention_date_and_time(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        # Prior state already had name & dept
        prior_state = {
            "session_id": "test-sf-10",
            "department": "Cardiology",
            "patient_name": "Ramesh Kumar",
            "transcript": "Naale 10 am ge confirm madi",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(prior_state)
        assert res["department"] == "Cardiology"
        assert res["patient_name"] == "Ramesh Kumar"
        assert res["appointment_date"] == "2026-11-07"
        assert res["appointment_time"] == "10:00"

    @pytest.mark.asyncio
    async def test_all_slots_filled_clears_missing_slots(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-11",
            "department": "Cardiology",
            "patient_name": "Ramesh Kumar",
            "appointment_date": "2026-11-07",
            "transcript": "10 am time",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["missing_slots"] == []
        assert res["response_text"] == ""

    @pytest.mark.asyncio
    async def test_missing_slots_order_priority(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        # Completely empty state
        state = {
            "session_id": "test-sf-12",
            "transcript": "Hello",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        # Missing should follow strict priority: name, dept, date, time
        assert res["missing_slots"] == [
            "patient_name",
            "department",
            "appointment_date",
            "appointment_time",
        ]

    @pytest.mark.asyncio
    async def test_single_pass_question_generation(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-13",
            "department": "Cardiology",
            "transcript": "Cardiology",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert res["response_text"] != ""
        assert "hesaru" in res["response_text"].lower()

    @pytest.mark.asyncio
    async def test_fallback_question_for_missing_name(self, mock_llm):
        # Force mock to return empty question_kannada
        mock_llm.extract_slots = lambda *args, **kwargs: {"department": "Neurology", "question_kannada": None}
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-14",
            "transcript": "Neurology",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert "hesaru" in res["response_text"].lower()

    @pytest.mark.asyncio
    async def test_fallback_question_for_missing_date(self, mock_llm):
        mock_llm.extract_slots = lambda *args, **kwargs: {
            "patient_name": "Ramesh",
            "department": "Cardiology",
            "question_kannada": None,
        }
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-15",
            "patient_name": "Ramesh",
            "department": "Cardiology",
            "transcript": "Ramesh",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert "date" in res["response_text"].lower()

    @pytest.mark.asyncio
    async def test_fallback_question_for_missing_time(self, mock_llm):
        mock_llm.extract_slots = lambda *args, **kwargs: {
            "patient_name": "Ramesh",
            "department": "Cardiology",
            "date": "2026-11-07",
            "question_kannada": None,
        }
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-16",
            "patient_name": "Ramesh",
            "department": "Cardiology",
            "appointment_date": "2026-11-07",
            "transcript": "Tomorrow",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert "time" in res["response_text"].lower()

    @pytest.mark.asyncio
    async def test_empty_string_values_treated_as_missing(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-17",
            "patient_name": "",
            "department": "",
            "transcript": "Hello",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert "patient_name" in res["missing_slots"]
        assert "department" in res["missing_slots"]

    @pytest.mark.asyncio
    async def test_slot_node_logs_assistant_message(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-sf-18",
            "transcript": "Cardiology",
            "full_transcript": [],
            "messages": [],
        }
        res = await slot_filling_node(state)
        assert any(m["role"] == "assistant" for m in res.get("messages", []))
