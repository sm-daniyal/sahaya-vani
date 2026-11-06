"""
SahayaVaani — LLM Service (Gemini Fallback)
Uses Gemini Flash via the OpenAI-compatible endpoint for fast testing.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, APITimeoutError, APIError

from config import settings
from langgraph_agent.prompts import (
    SYSTEM_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    SLOT_FILLING_PROMPT,
    SAFETY_CHECK_PROMPT,
)

logger = logging.getLogger(__name__)


class EvonLLMService:  # Name kept the same so the rest of your code doesn't break
    def __init__(self):
        # Point to Google's OpenAI-compatible endpoint
        self._client = AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.gemini_api_key,
            timeout=20.0,
        )
        self._model = "models/gemini-flash-lite-latest"  # Verified working on Google OpenAI endpoint

    async def _chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 256,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model":       self._model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        models_to_try = [self._model, "models/gemini-flash-latest"]
        last_exc = None
        for m in models_to_try:
            kwargs["model"] = m
            try:
                response = await self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                result = content.strip()
                if result:
                    logger.info(f"[LLM Brain] Response: {result}")
                    return result
            except Exception as exc:
                last_exc = exc
                logger.warning("[LLM] Model %s error: %s. Trying fallback...", m, exc)

        logger.error("[LLM] All Gemini models failed: %s", last_exc)
        raise last_exc

    def _format_history_messages(self, history: Optional[list]) -> list[dict]:
        """Convert conversation history (list of dicts or list of strings) into OpenAI messages."""
        if not history:
            return []
        msgs = []
        for item in history:
            if isinstance(item, dict):
                role = "assistant" if item.get("role") in ("assistant", "agent") else "user"
                content = item.get("content", "")
                if content:
                    msgs.append({"role": role, "content": content})
            elif isinstance(item, str):
                if item.lower().startswith("agent:"):
                    msgs.append({"role": "assistant", "content": item.split(":", 1)[1].strip()})
                elif item.lower().startswith("patient:"):
                    msgs.append({"role": "user", "content": item.split(":", 1)[1].strip()})
                else:
                    msgs.append({"role": "user", "content": item})
        return msgs

    async def classify_intent(self, transcript: str, history: Optional[list] = None) -> str:
        prompt = INTENT_CLASSIFIER_PROMPT.format(transcript=transcript)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        result = await self._chat(messages, max_tokens=64, temperature=0.1)
        label = result.strip().split()[0].lower() if result.strip() else "other"
        logger.info(f"[LLM Brain] classify_intent: {label}")
        return label

    async def extract_slots(
        self,
        transcript: str,
        today: str,
        history: Optional[list] = None,
        current_slots: Optional[dict] = None,
    ) -> Dict[str, Optional[str]]:
        history_msgs = self._format_history_messages(history)
        history_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history_msgs]) if history_msgs else "None"
        current_slots_str = json.dumps(current_slots or {})

        prompt = SLOT_FILLING_PROMPT.format(
            transcript=transcript,
            today=today,
            history=history_text,
            current_slots=current_slots_str,
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history_msgs)
        messages.append({"role": "user", "content": prompt})

        raw = await self._chat(messages, max_tokens=256, temperature=0.1, json_mode=True)
        logger.info(f"[LLM Brain] extract_slots raw: {raw}")

        try:
            slots = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    slots = json.loads(match.group())
                except json.JSONDecodeError:
                    slots = {}
            else:
                slots = {}

        return {
            "patient_name":     slots.get("patient_name"),
            "department":       slots.get("department"),
            "date":             slots.get("date"),
            "time":             slots.get("time"),
            "phone":            slots.get("phone"),
            "question_kannada": slots.get("question_kannada"),
        }

    async def safety_check(self, transcript: str, intent: str) -> str:
        prompt = SAFETY_CHECK_PROMPT.format(transcript=transcript, intent=intent)
        messages = [
            {"role": "system", "content": "You are a strict medical safety filter. Answer only YES or NO."},
            {"role": "user",   "content": prompt},
        ]
        result = await self._chat(messages, max_tokens=32, temperature=0.0)
        answer = result.strip().upper()
        return answer

    async def generate_response(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        history: Optional[list] = None,
    ) -> str:
        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nCurrent state context: {json.dumps(context)}"

        messages = [{"role": "system", "content": system}]
        messages.extend(self._format_history_messages(history))
        messages.append({"role": "user", "content": prompt})

        result = await self._chat(messages, max_tokens=256, temperature=0.3)
        logger.info(f"[LLM Brain] generate_response: {result}")
        return result
