"""
Shared Pytest Fixtures and Mocks for SahayaVaani Test Suite.
Enables fast, isolated execution for CI/CD without external API dependencies.
"""
import pytest
import pytest_asyncio
import asyncio
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database import Base, Appointment, HumanHandoff
from langgraph_agent.state import AgentState
from langgraph_agent.nodes import inject_dependencies


@pytest_asyncio.fixture
async def async_test_db():
    """In-memory SQLite database for high-speed, isolated test runs."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_maker
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(async_test_db):
    """Test fixture alias for LangGraph workflow tests."""
    import database
    try:
        await database.init_db()
    except Exception:
        pass
    yield async_test_db


class MockLLMService:
    """Fast, deterministic mock for LLM brain testing."""

    def __init__(self):
        self.default_intent = "book_appointment"
        self.default_slots = {
            "patient_name": "Ramesh",
            "department": "Cardiology",
            "date": "2026-11-10",
            "time": "10:00",
            "phone": "9876543210",
            "question_kannada": "Nimma hesaru heli?",
        }

    async def classify_intent(self, transcript: str, history: Optional[list] = None) -> str:
        t = transcript.lower().strip()
        if any(w in t for w in ("namaskara", "namaskar", "ನಮಸ್ಕಾರ", "ನಮಸ್ತೆ", "namaste", "hello", "hi", "hey")):
            return "greeting"
        if any(w in t for w in ("bye", "thank", "ashte", "illa ashte", "disconnect")):
            return "farewell"
        if any(w in t for w in ("which tablet", "what medicine", "prescribe", "dosage", "cure", "tablet", "mathre", "aushadhi", "dose")):
            return "medical_question"
        if any(w in t for w in ("reschedule", "change time", "postpone")):
            return "reschedule"
        if any(w in t for w in ("where is", "hospital located", "timing", "visiting hour", "yavaga open", "open irutte", "timings")):
            return "other"
        return "book_appointment"

    async def extract_slots(self, transcript: str, today: str, history=None, current_slots=None) -> Dict[str, Any]:
        slots = dict(current_slots or {})
        t = transcript.lower()

        # Department mapping
        if "cardio" in t or "heart" in t or "chest pain" in t:
            slots["department"] = "Cardiology"
        elif "ortho" in t or "bone" in t or "fracture" in t or "joint" in t:
            slots["department"] = "Orthopedics"
        elif "derma" in t or "skin" in t:
            slots["department"] = "Dermatology"
        elif "neuro" in t or "brain" in t:
            slots["department"] = "Neurology"
        elif "fever" in t or "cough" in t or "general" in t:
            slots["department"] = "General Medicine"
        elif "ct scan" in t or "mri" in t or "x-ray" in t:
            slots["department"] = "Radiology"

        # Name extraction
        if "ramesh kumar" in t:
            slots["patient_name"] = "Ramesh Kumar"
        elif "ananya sharma" in t:
            slots["patient_name"] = "Ananya Sharma"
        else:
            for name in ["ramesh", "suresh", "rekha", "kavitha", "vijay", "daniyal", "ananya"]:
                if name in t:
                    slots["patient_name"] = name.capitalize()
                    break

        # Date & Time
        if "tomorrow" in t or "naale" in t:
            slots["date"] = "2026-11-07"
        elif "monday" in t:
            slots["date"] = "2026-11-09"
        elif "2026" in t:
            slots["date"] = "2026-11-10"

        if "10" in t:
            slots["time"] = "10:00"
        elif "11" in t:
            slots["time"] = "11:00"
        elif "2" in t or "14" in t:
            slots["time"] = "14:00"

        if "9876543210" in t:
            slots["phone"] = "9876543210"

        # Missing questions
        missing = [f for f in ["patient_name", "department", "date", "time"] if not slots.get(f)]
        if missing:
            if missing[0] == "patient_name":
                slots["question_kannada"] = "Nimma hesaru heli?"
            elif missing[0] == "department":
                slots["question_kannada"] = "Yava department beku?"
            elif missing[0] == "date":
                slots["question_kannada"] = "Yava dina barthira?"
            elif missing[0] == "time":
                slots["question_kannada"] = "Yava samaya anukoola?"
            else:
                slots["question_kannada"] = f"Dayavittu {missing[0]} heli."
        else:
            slots["question_kannada"] = None

        return slots

    async def safety_check(self, transcript: str, intent: str) -> str:
        t = transcript.lower()
        if any(w in t for w in ("medicine", "tablet", "dosage", "prescribe", "cure")):
            return "YES"
        return "NO"

    async def generate_response(self, prompt: str, context: Optional[Dict] = None, history=None) -> str:
        if "where" in prompt.lower() or "location" in prompt.lower():
            return "Bangalore General Hospital MG Road hattira ide."
        if "farewell" in prompt.lower() or "bye" in prompt.lower():
            return "Dhanyavadagalu! Have a good day!"
        return "Kandita, nimma appointment na confirm madiddini. Innu bere enadru help beka?"


@pytest.fixture
def mock_llm():
    return MockLLMService()
