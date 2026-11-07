"""
SahayaVaani — LangGraph Node Implementations

Each function maps to one node in the state machine DAG:

  greeting → intent_classifier → safety_check
                                       │
                     ┌─────────────────┴──────────────────┐
                     ▼                                     ▼
               slot_filling                        escalate_human
                     │
               confirm_booking

All nodes receive and return AgentState dicts (partial updates only).
"""
import json
import logging
from datetime import date, timedelta
from typing import Dict, Any

from langgraph_agent.state import AgentState
from langgraph_agent.prompts import (
    SYSTEM_PROMPT, INTENT_CLASSIFIER_PROMPT, SLOT_FILLING_PROMPT,
    SAFETY_CHECK_PROMPT, CONFIRMATION_PROMPT, SLOT_REPROMPT_PROMPT,
    GREETING_TEXT, REPEAT_REQUEST_TEXT, ESCALATION_TEXT, FAREWELL_TEXT,
    SLOT_QUESTIONS, SLOT_QUESTION_PROMPT, CONFIRMATION_LLM_PROMPT, SMALL_TALK_PROMPT,
)

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependency; services are injected at runtime.
_llm_service = None
_db_create = None
_db_flag = None


def inject_dependencies(llm_service, db_create_fn, db_flag_fn):
    """Call once from main.py after all services are initialised."""
    global _llm_service, _db_create, _db_flag
    _llm_service = llm_service
    _db_create = db_create_fn
    _db_flag = db_flag_fn


# ── 1. Greeting ────────────────────────────────────────────────────────────────

def greeting_node(state: AgentState) -> Dict[str, Any]:
    """
    Entry node. Sets the greeting text.
    """
    logger.info("[greeting_node] session=%s", state["session_id"])
    return {
        "response_text": GREETING_TEXT,
        "current_node":  "greeting",
        "is_complete":   False,
        "needs_repeat":  False,
        "full_transcript": [f"Agent: {GREETING_TEXT}"],
        "messages": [{"role": "assistant", "content": GREETING_TEXT}],
    }


# ── 2. Intent Classifier ───────────────────────────────────────────────────────

async def intent_classifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Calls Evon LLM to classify the patient's intent using full conversation history.
    """
    logger.info("[intent_classifier_node] session=%s transcript=%r",
                state["session_id"], state.get("transcript", ""))

    transcript = state.get("transcript", "").strip()
    if not transcript:
        return {
            "needs_repeat":  True,
            "response_text": REPEAT_REQUEST_TEXT,
            "current_node":  "intent_classifier",
        }

    confidence = float(state.get("confidence_score", 1.0))
    words = transcript.split()
    tx_lower = transcript.lower().strip()

    # Check if an appointment booking is actively in progress
    is_booking_active = (
        state.get("intent") == "book_appointment"
        or bool(state.get("department"))
        or bool(state.get("patient_name"))
        or bool(state.get("missing_slots"))
    ) and state.get("intent") != "appointment_confirmed"

    cancel_words = ("bye", "exit", "stop", "cancel", "bedi", "beda", "disconnect", "call cut")

    if is_booking_active:
        if any(w in tx_lower for w in cancel_words):
            logger.info("[intent_classifier_node] User cancelled active booking")
            intent = "farewell"
        elif confidence < 0.35 and len(words) < 2:
            logger.info("[intent_classifier_node] Very low confidence (%.2f) on active booking turn", confidence)
            return {
                "needs_repeat":  True,
                "response_text": REPEAT_REQUEST_TEXT,
                "current_node":  "intent_classifier",
            }
        else:
            logger.info("[intent_classifier_node] Active booking in progress — retaining book_appointment intent")
            intent = "book_appointment"
    else:
        # Initial turn or new intent: reject low confidence / garbled noise unless clear clinical/booking keywords are present
        booking_keywords = (
            "appointment", "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್", "doctor", "ಡಾಕ್ಟರ್", "book", "ಬೇಕು",
            "beku", "cardio", "fever", "pain", "hospital", "ನಾಳೆ", "today", "naale",
            "ಯಾವಾಗ", "timing", "slot", "ಹೌದು", "yes"
        )
        has_keywords = any(k in tx_lower for k in booking_keywords)

        if len(words) < 2 and confidence >= 0.70:
            logger.info("[intent_classifier_node] Short utterance (%d words) with confidence (%.2f)", len(words), confidence)
        elif not has_keywords and confidence < 0.50:
            logger.info("[intent_classifier_node] Rejecting low confidence utterance without clinical keywords (%.2f): %r", confidence, transcript)
            return {
                "needs_repeat":  True,
                "response_text": REPEAT_REQUEST_TEXT,
                "current_node":  "intent_classifier",
            }

        # Fast path for common greetings
        if tx_lower in ("namaskara", "namaskar", "ನಮಸ್ಕಾರ", "ನಮಸ್ತೆ", "namaste", "hello", "hi", "hey", "good morning", "good evening"):
            intent = "greeting"
        # Pure farewell when NOT in booking flow, or after appointment is confirmed
        elif any(tx_lower == w for w in ("dhanyavada", "thank you", "thanks", "bye", "goodbye", "exit", "disconnect")) or (
            state.get("intent") == "appointment_confirmed"
            and any(w in tx_lower for w in ("bye", "thank you", "thanks", "dhanyavada", "ashte", "illa ashte", "no thanks"))
        ):
            intent = "farewell"
        else:
            history = state.get("messages") or state.get("full_transcript") or []
            try:
                raw = await _llm_service.classify_intent(transcript, history=history)
                intent = raw.strip().lower()
            except Exception as exc:
                logger.error("[intent_classifier_node] LLM error: %s", exc)
                intent = "other"

    # Validate intent value
    valid_intents = {"book_appointment", "reschedule", "medical_question", "greeting", "farewell", "other", "side_conversation"}
    if intent not in valid_intents:
        if any(w in intent for w in ("greet", "namaskara", "ನಮಸ್ಕಾರ", "hello", "hi")):
            intent = "greeting"
        elif any(w in intent for w in ("bye", "thank", "farewell")):
            intent = "farewell"
        elif "appoint" in intent or "book" in intent:
            intent = "book_appointment"
        elif any(w in intent for w in ("side", "background", "chatter", "noise")):
            intent = "side_conversation"
        else:
            intent = "other"

    logger.info("[intent_classifier_node] intent=%s", intent)
    return {
        "intent":          intent,
        "current_node":    "intent_classifier",
        "response_text":   "" if intent == "side_conversation" else state.get("response_text", ""),
        "needs_repeat":    False,
    }


# ── 2b. Small Talk / Greeting / Farewell ──────────────────────────────────────

async def small_talk_node(state: AgentState) -> Dict[str, Any]:
    """
    Replies to greetings, farewells, and general hospital queries in natural Kanglish (ChatGPT Voice style).
    """
    logger.info("[small_talk_node] session=%s intent=%s", state["session_id"], state.get("intent"))
    transcript = state.get("transcript", "")
    intent = state.get("intent", "greeting")
    tx_lower = transcript.lower().strip()

    # Farewell check: only conclude call if intent is farewell, or if appointment is already confirmed
    is_confirmed = (state.get("intent") == "appointment_confirmed") or bool(state.get("db_appointment_id"))
    pure_farewells = ("bye", "goodbye", "exit", "disconnect")

    is_farewell_trigger = (
        intent == "farewell"
        or any(tx_lower == w or tx_lower.startswith(w + " ") or tx_lower.endswith(" " + w) for w in pure_farewells)
        or (is_confirmed and any(w in tx_lower for w in ("ashte", "illa ashte", "thanks", "thank you", "dhanyavada", "no thanks", "nothing else")))
    )

    if is_farewell_trigger:
        reply = "Dhanyavadagalu! Bangalore General Hospital ge call madiddakke. Have a wonderful day!"
        return {
            "response_text":   reply,
            "current_node":    "small_talk",
            "is_complete":     True,
            "needs_repeat":    False,
            "full_transcript": [f"Agent: {reply}"],
            "messages":        [{"role": "assistant", "content": reply}],
        }

    history = state.get("messages") or state.get("full_transcript") or []
    history_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" if isinstance(m, dict) else str(m) for m in history]) or "None"

    try:
        prompt = SMALL_TALK_PROMPT.format(transcript=transcript, history=history_str)
        reply = await _llm_service.generate_response(prompt, context={"node": "small_talk"}, history=history)
        reply = reply.strip().strip('"')
    except Exception as exc:
        logger.warning("[small_talk_node] LLM generation failed, using fallback: %s", exc)
        reply = "Namaskara! How can I help you today? Doctor appointment schedule maadbeka?"

    return {
        "response_text":   reply,
        "current_node":    "small_talk",
        "is_complete":     False,
        "needs_repeat":    False,
        "full_transcript": [f"Agent: {reply}"],
        "messages":        [{"role": "assistant", "content": reply}],
    }


# ── 3. Safety Check ────────────────────────────────────────────────────────────

async def safety_check_node(state: AgentState) -> Dict[str, Any]:
    """
    Hard safety guardrail for medical advice/prescription requests.
    Standard appointments (even with patient describing symptoms) pass through in 0ms!
    """
    logger.info("[safety_check_node] session=%s intent=%s",
                state["session_id"], state.get("intent"))

    intent = state.get("intent", "other")

    # If already classified as medical advice request, escalate immediately
    if intent == "medical_question":
        return {"current_node": "safety_check", "intent": "medical_question"}

    # Keyword check specifically for prescription or home treatment requests
    tx_lower = state.get("transcript", "").lower()
    advice_triggers = (
        "which medicine", "what medicine", "what tablet", "prescribe", "dosage",
        "what dose", "how to cure", "treatment advice", "home remedy",
        "yava mathre", "yava aushadhi", "dose eshtu"
    )
    if any(trigger in tx_lower for trigger in advice_triggers):
        logger.warning("[safety_check_node] Prescription/medical advice request detected: %s", tx_lower)
        return {"current_node": "safety_check", "intent": "medical_question"}

    return {"current_node": "safety_check"}


# ── 4. Slot Filling ────────────────────────────────────────────────────────────

async def slot_filling_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts appointment slots and dynamic Kanglish question in a single fast LLM pass.
    Checks what slots are already filled (patient_name, department, date, time).
    If patient_name is missing, asks for it.
    If patient_name is present but department is missing, asks for department.
    If all slots are filled, completes slot filling.
    """
    logger.info("[slot_filling_node] session=%s", state["session_id"])

    transcript = state.get("transcript", "")
    today_str = date.today().isoformat()
    history = state.get("messages") or state.get("full_transcript") or []

    current_slots = {
        "patient_name":     state.get("patient_name"),
        "department":       state.get("department"),
        "appointment_date": state.get("appointment_date"),
        "appointment_time": state.get("appointment_time"),
        "phone_number":     state.get("phone_number"),
    }

    try:
        slots = await _llm_service.extract_slots(
            transcript,
            today_str,
            history=history,
            current_slots=current_slots,
        )
    except Exception as exc:
        logger.error("[slot_filling_node] LLM error: %s", exc)
        slots = {}

    def _clean_slot(val):
        if not val:
            return None
        if isinstance(val, str) and val.strip().lower() in ("null", "none", "undefined", "n/a", "unknown", ""):
            return None
        return val.strip() if isinstance(val, str) else val

    # Merge with existing state (keep values already captured in prior turns)
    merged = {
        "patient_name":       _clean_slot(slots.get("patient_name"))   or state.get("patient_name"),
        "department":         _clean_slot(slots.get("department"))      or state.get("department"),
        "appointment_date":   _clean_slot(slots.get("date"))            or state.get("appointment_date"),
        "appointment_time":   _clean_slot(slots.get("time"))            or state.get("appointment_time"),
        "phone_number":       _clean_slot(slots.get("phone"))           or state.get("phone_number"),
    }

    # Determine what's still missing in strict priority order:
    # 1. patient_name
    # 2. department
    # 3. appointment_date
    # 4. appointment_time
    required = ["patient_name", "department", "appointment_date", "appointment_time"]
    missing = [f for f in required if not merged.get(f)]

    if missing:
        next_field = missing[0]
        # Fast path: Use question_kannada generated in the single LLM pass if present
        raw_question = slots.get("question_kannada")
        question = _clean_slot(raw_question)
        if question and isinstance(question, str) and len(question.strip()) > 3:
            question = question.strip().strip('"')
            logger.info("[slot_filling_node] Using single-pass generated question: %r", question)
        else:
            fallback_questions = {
                "patient_name":     "Dayavittu nimage hesaru heli.",
                "department":       "Yavaru department ge hogabeku? Heli.",
                "appointment_date": "Yavaga appointment beeku? Date heli.",
                "appointment_time": "Yavaga time convenient aagutte? Time heli.",
            }
            question = fallback_questions.get(next_field, f"Dayavittu {next_field} heli.")

        return {
            **merged,
            "missing_slots":   missing,
            "response_text":   question,
            "current_node":    "slot_filling",
            "full_transcript": [f"Agent: {question}"],
            "messages":        [{"role": "assistant", "content": question}],
        }

    # All slots collected → pass to confirm_booking
    return {
        **merged,
        "missing_slots": [],
        "response_text": "",
        "current_node":  "slot_filling",
    }


# ── 5. Confirm Booking ────────────────────────────────────────────────────────

async def confirm_booking_node(state: AgentState) -> Dict[str, Any]:
    """
    Writes the confirmed appointment to SQLite EMR and uses Gemini LLM to generate
    a warm, natural Kanglish confirmation message.
    """
    logger.info("[confirm_booking_node] session=%s", state["session_id"])

    full_tx = "\n".join(state.get("full_transcript", []))

    try:
        appt = await _db_create(
            patient_name=state.get("patient_name", "Unknown"),
            phone=state.get("phone_number"),
            department=state.get("department", "General"),
            date=state.get("appointment_date"),
            time=state.get("appointment_time"),
            status="confirmed",
            transcript=full_tx,
            session_id=state["session_id"],
        )
        appt_id = appt.id
        logger.info("[confirm_booking_node] appointment id=%d created", appt_id)
    except Exception as exc:
        logger.error("[confirm_booking_node] DB error: %s", exc)
        appt_id = None

    history = state.get("messages") or state.get("full_transcript") or []
    prompt = CONFIRMATION_LLM_PROMPT.format(
        patient_name=state.get("patient_name", "Patient"),
        department=state.get("department", "General"),
        date=state.get("appointment_date", "scheduled date"),
        time=state.get("appointment_time", "scheduled time"),
    )

    try:
        confirm_text = await _llm_service.generate_response(prompt, context={"appointment_id": appt_id}, history=history)
        confirm_text = confirm_text.strip().strip('"')
    except Exception as exc:
        logger.warning("[confirm_booking_node] LLM confirmation failed: %s", exc)
        confirm_text = (
            f"Dhanyavadagalu {state.get('patient_name')} avare! "
            f"Nimage {state.get('department')} ge {state.get('appointment_date')} dina "
            f"{state.get('appointment_time')} ge appointment confirm aagide. Innu bere enadru help beka?"
        )

    return {
        "db_appointment_id": appt_id,
        "response_text":     confirm_text,
        "is_complete":       False,  # Keep call alive for full natural conversation!
        "intent":            "appointment_confirmed",
        "current_node":      "confirm_booking",
        "missing_slots":     [],
        "full_transcript":   [f"Agent: {confirm_text}"],
        "messages":          [{"role": "assistant", "content": confirm_text}],
    }


# ── 6. Escalate to Human ───────────────────────────────────────────────────────

async def escalate_human_node(state: AgentState) -> Dict[str, Any]:
    """
    Triggered when medical advice/prescription is asked. Flags the session in the DB
    and politely guides the patient to schedule an appointment with a doctor.
    Keeps session alive so the patient can complete booking!
    """
    logger.info("[escalate_human_node] session=%s", state["session_id"])

    transcript = "\n".join(state.get("full_transcript", []))

    try:
        handoff = await _db_flag(
            session_id=state["session_id"],
            appointment_id=state.get("db_appointment_id"),
            reason="Patient asked for medical advice",
            transcript=transcript,
        )
        logger.info("[escalate_human_node] handoff id=%d flagged", handoff.id)
    except Exception as exc:
        logger.error("[escalate_human_node] DB error: %s", exc)

    escalation_text = (
        "Nanna kshame irali, naanu receptionist AI aagiddini, direct medical advice kodokke agalla. "
        "Namma specialist doctor nodoke appointment schedule maadla? Nimma hesaru heli."
    )

    return {
        "response_text":   escalation_text,
        "is_complete":     False,  # Keep call alive to let patient book!
        "intent":          "book_appointment",
        "current_node":    "escalate_human",
        "full_transcript": [f"Agent: {escalation_text}"],
        "messages":        [{"role": "assistant", "content": escalation_text}],
    }
