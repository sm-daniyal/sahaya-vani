"""
SahayaVaani — LangGraph State Machine

Graph topology:

  [START]
     │
     ▼
  greeting
     │
     ▼
  intent_classifier  ◄──── (loops back on needs_repeat)
     │
     ▼
  safety_check
     │
  ┌──┴──────────────────────┐
  │ medical_question?        │
  ▼                         ▼
escalate_human          slot_filling
  │                         │
  ▼                    (loops until all slots filled)
 [END]                       │
                        confirm_booking
                             │
                            [END]

The graph uses MemorySaver for per-session state persistence across
multi-turn conversations (e.g., multi-round slot filling).
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from langgraph_agent.state import AgentState
from langgraph_agent.nodes import (
    greeting_node,
    intent_classifier_node,
    small_talk_node,
    safety_check_node,
    slot_filling_node,
    confirm_booking_node,
    escalate_human_node,
)

logger = logging.getLogger(__name__)


# ── Conditional edge functions ─────────────────────────────────────────────────

def route_after_intent(state: AgentState):
    """If STT confidence was low or side conversation detected, END turn. If greeting, farewell, or general question, route to small_talk. Otherwise proceed to safety check."""
    if state.get("needs_repeat") or state.get("intent") == "side_conversation":
        return END
    if state.get("intent") in ("greeting", "farewell", "other"):
        return "small_talk"
    return "safety_check"


def route_after_safety(state: AgentState):
    """Hard guardrail: medical questions go to escalation, everything else to slots."""
    if state.get("intent") == "medical_question":
        return "escalate_human"
    return "slot_filling"


def route_after_slots(state: AgentState):
    """If more slots needed, END this turn so agent can ask question. Otherwise confirm_booking."""
    missing = state.get("missing_slots", [])
    if missing:
        return END
    return "confirm_booking"


# ── Graph Construction ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Builds and compiles the SahayaVaani LangGraph state machine.
    Returns a compiled graph ready for `.astream()` / `.ainvoke()`.
    """
    checkpointer = MemorySaver()

    graph = StateGraph(AgentState)

    # ── Add nodes ──────────────────────────────────────────────────────────────
    graph.add_node("greeting",           greeting_node)
    graph.add_node("intent_classifier",  intent_classifier_node)
    graph.add_node("small_talk",         small_talk_node)
    graph.add_node("safety_check",       safety_check_node)
    graph.add_node("slot_filling",       slot_filling_node)
    graph.add_node("confirm_booking",    confirm_booking_node)
    graph.add_node("escalate_human",     escalate_human_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    # Patient utterances enter directly into intent_classifier
    graph.set_entry_point("intent_classifier")

    # ── Edges ──────────────────────────────────────────────────────────────────
    # intent_classifier → safety_check OR small_talk OR END (needs_repeat)
    graph.add_conditional_edges(
        "intent_classifier",
        route_after_intent,
        {
            "safety_check": "safety_check",
            "small_talk":   "small_talk",
            END:            END,
        },
    )

    # safety_check → slot_filling OR escalate_human
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "slot_filling":   "slot_filling",
            "escalate_human": "escalate_human",
        },
    )

    # slot_filling → confirm_booking OR END (more slots needed to ask user)
    graph.add_conditional_edges(
        "slot_filling",
        route_after_slots,
        {
            "confirm_booking": "confirm_booking",
            END:               END,
        },
    )

    # Terminal nodes
    graph.add_edge("small_talk",      END)
    graph.add_edge("confirm_booking", END)
    graph.add_edge("escalate_human",  END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[build_graph] LangGraph compiled successfully")
    return compiled


# Singleton — imported by main.py and bolna orchestrator
agent_graph = build_graph()
