"""
SahayaVaani — LangGraph Agent State
Typed dictionary that flows through every node of the state machine.
"""
from typing import TypedDict, Optional, List, Dict, Literal, Annotated
import operator


IntentType = Literal["book_appointment", "medical_question", "reschedule", "greeting", "other", "unknown"]


class AgentState(TypedDict):
    # ── Session ───────────────────────────────────────────────────────────────
    session_id: str

    # ── Transcript & Chat History ─────────────────────────────────────────────
    transcript: str                                         # latest STT result
    messages: Annotated[List[Dict[str, str]], operator.add]  # chat history [{"role": "user"|"assistant", "content": "..."}]
    full_transcript: Annotated[List[str], operator.add]     # accumulated text turns ["Patient: ...", "Agent: ..."]
    confidence_score: float                                 # STT confidence [0.0, 1.0]
    needs_repeat: bool                                      # True → agent asks patient to repeat

    # ── Intent & Slots ────────────────────────────────────────────────────────
    intent: Optional[IntentType]
    patient_name: Optional[str]
    department: Optional[str]
    appointment_date: Optional[str]                         # ISO date, e.g. "2026-11-10"
    appointment_time: Optional[str]                         # HH:MM, e.g. "10:30"
    phone_number: Optional[str]

    # ── Missing slots (for multi-turn slot filling) ────────────────────────────
    # Overwritten per turn with currently missing slots (NOT operator.add)
    missing_slots: List[str]

    # ── Agent Output ──────────────────────────────────────────────────────────
    response_text: str                                      # text to synthesise via TTS
    audio_chunks: Annotated[List[bytes], operator.add]      # TTS audio

    # ── Control Flow ──────────────────────────────────────────────────────────
    is_complete: bool                                       # session done
    error: Optional[str]

    # ── Database ──────────────────────────────────────────────────────────────
    db_appointment_id: Optional[int]

    # ── Current node label (for frontend stepper) ─────────────────────────────
    current_node: Optional[str]
