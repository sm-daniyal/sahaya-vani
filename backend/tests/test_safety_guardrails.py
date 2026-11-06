"""
Unit tests for Medical Safety Guardrails and Doctor Escalation.
Verifies that patients can describe symptoms to book appointments without being blocked,
while drug prescription and medical advice requests are strictly flagged and handled safely.
"""
import pytest
from unittest.mock import AsyncMock
from langgraph_agent.nodes import safety_check_node, escalate_human_node, inject_dependencies


class TestSafetyGuardrails:
    @pytest.mark.asyncio
    async def test_symptom_fever_allowed_for_booking(self):
        state = {
            "session_id": "safe-1",
            "intent": "book_appointment",
            "transcript": "I have fever and need to see a general doctor",
        }
        res = await safety_check_node(state)
        # Should NOT be converted to medical_question
        assert res.get("intent") != "medical_question"
        assert res["current_node"] == "safety_check"

    @pytest.mark.asyncio
    async def test_symptom_chest_pain_allowed_for_booking(self):
        state = {
            "session_id": "safe-2",
            "intent": "book_appointment",
            "transcript": "Severe chest pain, please book an urgent cardiology slot",
        }
        res = await safety_check_node(state)
        assert res.get("intent") != "medical_question"

    @pytest.mark.asyncio
    async def test_symptom_fracture_allowed_for_booking(self):
        state = {
            "session_id": "safe-3",
            "intent": "book_appointment",
            "transcript": "Leg bone fracture from an accident",
        }
        res = await safety_check_node(state)
        assert res.get("intent") != "medical_question"

    @pytest.mark.asyncio
    async def test_symptom_headache_allowed_for_booking(self):
        state = {
            "session_id": "safe-4",
            "intent": "book_appointment",
            "transcript": "Bad headache, need neurology consultation",
        }
        res = await safety_check_node(state)
        assert res.get("intent") != "medical_question"

    @pytest.mark.asyncio
    async def test_prescription_request_which_medicine(self):
        state = {
            "session_id": "safe-5",
            "intent": "book_appointment",
            "transcript": "Which medicine should I take for fever right now?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_prescription_request_what_tablet(self):
        state = {
            "session_id": "safe-6",
            "intent": "other",
            "transcript": "What tablet will cure this stomach pain?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_prescription_request_dosage(self):
        state = {
            "session_id": "safe-7",
            "intent": "other",
            "transcript": "What is the safe dosage for paracetamol 650?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_kannada_prescription_yava_mathre(self):
        state = {
            "session_id": "safe-8",
            "intent": "other",
            "transcript": "Jwara ge yava mathre thagobeku heli?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_kannada_prescription_yava_aushadhi(self):
        state = {
            "session_id": "safe-9",
            "intent": "other",
            "transcript": "Yava aushadhi thagondre novvu hogatte?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_kannada_prescription_dose_eshtu(self):
        state = {
            "session_id": "safe-10",
            "intent": "other",
            "transcript": "Ee tablet dose eshtu thagobeku?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_preclassified_medical_question_routes_directly(self):
        state = {
            "session_id": "safe-11",
            "intent": "medical_question",
            "transcript": "Can I take aspirin?",
        }
        res = await safety_check_node(state)
        assert res.get("intent") == "medical_question"

    @pytest.mark.asyncio
    async def test_escalation_node_records_db_handoff(self):
        mock_db_flag = AsyncMock()
        mock_handoff = AsyncMock()
        mock_handoff.id = 99
        mock_db_flag.return_value = mock_handoff

        inject_dependencies(None, None, mock_db_flag)
        state = {
            "session_id": "safe-12",
            "full_transcript": ["Patient: Which medicine to take?"],
        }
        res = await escalate_human_node(state)
        mock_db_flag.assert_called_once()
        assert res["current_node"] == "escalate_human"

    @pytest.mark.asyncio
    async def test_escalation_node_keeps_call_alive_for_booking(self):
        mock_db_flag = AsyncMock()
        mock_handoff = AsyncMock()
        mock_handoff.id = 100
        mock_db_flag.return_value = mock_handoff

        inject_dependencies(None, None, mock_db_flag)
        state = {"session_id": "safe-13", "full_transcript": []}
        res = await escalate_human_node(state)
        # Call should NOT be terminated; patient is offered a real doctor appointment
        assert res["is_complete"] is False
        assert res["intent"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_escalation_response_offers_doctor_appointment(self):
        mock_db_flag = AsyncMock()
        mock_handoff = AsyncMock()
        mock_handoff.id = 101
        mock_db_flag.return_value = mock_handoff

        inject_dependencies(None, None, mock_db_flag)
        state = {"session_id": "safe-14", "full_transcript": []}
        res = await escalate_human_node(state)
        assert "medical advice" in res["response_text"].lower()
        assert "doctor" in res["response_text"].lower()
