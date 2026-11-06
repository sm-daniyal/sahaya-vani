"""
Unit tests for Kanglish Intent Classification and Greeting/Farewell Fast Paths.
Tests both Kannada script and Kanglish medical vocabulary.
"""
import pytest
from langgraph_agent.nodes import intent_classifier_node, inject_dependencies
from langgraph_agent.prompts import REPEAT_REQUEST_TEXT


class TestIntentClassifier:
    @pytest.mark.asyncio
    async def test_kannada_script_greeting(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-1",
            "transcript": "ನಮಸ್ಕಾರ",
            "confidence_score": 0.95,
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "greeting"
        assert not res["needs_repeat"]

    @pytest.mark.asyncio
    async def test_kannada_script_namaste(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-2", "transcript": "ನಮಸ್ತೆ", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_kanglish_greeting_namaskara(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-3", "transcript": "Namaskara", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_english_greeting_hello(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-4", "transcript": "Hello", "confidence_score": 0.92}
        res = await intent_classifier_node(state)
        assert res["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_english_greeting_good_morning(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-5", "transcript": "Good morning", "confidence_score": 0.90}
        res = await intent_classifier_node(state)
        assert res["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_farewell_bye(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-6", "transcript": "Bye", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_farewell_thank_you(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-7", "transcript": "Thank you so much", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_farewell_kannada_ashte(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-8", "transcript": "Illa ashte", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_farewell_kannada_dhanyavada(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-9", "transcript": "Dhanyavada", "confidence_score": 0.95}
        res = await intent_classifier_node(state)
        assert res["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_booking_intent_cardiology(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-10",
            "transcript": "Nange Cardiology doctor ge appointment beku",
            "confidence_score": 0.95,
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_booking_intent_orthopedics(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-11",
            "transcript": "Kaalu novvu ide, bone specialist consult maadbeku",
            "confidence_score": 0.95,
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_booking_intent_reschedule(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-12",
            "transcript": "Nanna appointment change maadbeku, reschedule madi",
            "confidence_score": 0.95,
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "reschedule"

    @pytest.mark.asyncio
    async def test_fast_path_booking_continuation(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        # Booking in progress with missing slots
        state = {
            "session_id": "test-13",
            "transcript": "Ramesh",
            "confidence_score": 0.95,
            "intent": "book_appointment",
            "missing_slots": ["department", "date", "time"],
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "book_appointment"

    @pytest.mark.asyncio
    async def test_cancellation_during_booking_routes_farewell(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-14",
            "transcript": "Beda, cancel madi",
            "confidence_score": 0.95,
            "intent": "book_appointment",
            "missing_slots": ["department", "date"],
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_repeat(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-15",
            "transcript": "muffled garbled noise",
            "confidence_score": 0.45,  # Below 0.60
        }
        res = await intent_classifier_node(state)
        assert res["needs_repeat"] is True
        assert res["response_text"] == REPEAT_REQUEST_TEXT

    @pytest.mark.asyncio
    async def test_short_high_confidence_allowed(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-16",
            "transcript": "Cardiology",
            "confidence_score": 0.95,  # 1 word but > 0.80
        }
        res = await intent_classifier_node(state)
        assert not res.get("needs_repeat")

    @pytest.mark.asyncio
    async def test_empty_transcript_triggers_repeat(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {"session_id": "test-17", "transcript": "   ", "confidence_score": 0.90}
        res = await intent_classifier_node(state)
        assert res["needs_repeat"] is True

    @pytest.mark.asyncio
    async def test_general_inquiry_intent_other(self, mock_llm):
        inject_dependencies(mock_llm, None, None)
        state = {
            "session_id": "test-18",
            "transcript": "Where is the hospital located?",
            "confidence_score": 0.95,
        }
        res = await intent_classifier_node(state)
        assert res["intent"] == "other"
