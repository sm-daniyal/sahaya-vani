import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

logger = logging.getLogger(__name__)


class GnaniSTTService:
    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = asyncio.Event()

    @property
    def _headers(self) -> dict:
        return {
            "x-api-key-id": settings.gnani_api_key,
            "language_code": settings.stt_lang_code,  # e.g. "kn-IN"
            "x-sample-rate": "16000",
            "format": "verbatim",
        }

    async def connect(self) -> None:
        logger.info("[STT] Connecting to %s", settings.stt_ws_url)
        self._ws = await websockets.connect(
            settings.stt_ws_url,
            additional_headers=self._headers,
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=10,
        )
        self._connected.set()
        logger.info("[STT] Connected")

    async def disconnect(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._connected.clear()
        logger.info("[STT] Disconnected")

    async def send_frame(self, pcm_bytes: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("STT WebSocket not connected.")
        await self._ws.send(pcm_bytes)

    async def send_end_of_stream(self) -> None:
        # Send 400ms of silence (12800 bytes at 16kHz) to promptly trigger final transcript without lag
        silence = bytes(12800)
        if self._ws is not None:
            await self._ws.send(silence)
            logger.debug("[STT] End-of-stream silence sent")

    async def receive_one(self) -> Optional[dict]:
        if self._ws is None:
            return None
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            data = json.loads(raw)
            return data
        except asyncio.TimeoutError:
            return None
        except (ConnectionClosed, json.JSONDecodeError) as exc:
            logger.warning("[STT] receive_one error: %s", exc)
            return None

    async def transcribe_once(self, pcm_bytes: bytes):
        """Transcribe a complete PCM buffer in one shot (used by /api/test-call)."""
        from bolna_layer.audio_utils import split_into_frames
        q: asyncio.Queue = asyncio.Queue()
        for frame in split_into_frames(pcm_bytes, settings.frame_size):
            await q.put(frame)
        await q.put(None)  # end sentinel

        transcript = ""
        confidence = 0.0
        async for result in self.transcribe_stream(q):
            if isinstance(result, dict):
                transcript = result.get("text", "") or result.get("transcript", "")
                confidence = float(result.get("confidence", 0.0))

        class _Result:
            pass
        r = _Result()
        r.transcript = transcript
        r.confidence = confidence
        return r

    async def transcribe_stream(
        self,
        audio_queue: asyncio.Queue,
        *,
        end_sentinel: object = None,
    ) -> AsyncGenerator[dict, None]:
        await self.connect()

        async def _sender():
            while True:
                frame = await audio_queue.get()
                if frame is end_sentinel:
                    await self.send_end_of_stream()
                    break
                await self.send_frame(frame)

        sender_task = asyncio.create_task(_sender())

        try:
            while True:
                event = await self.receive_one()
                if event is None:
                    if sender_task.done():
                        break
                    continue

                # Gnani returns {"type": "transcript", "text": "...", ...}
                if event.get("type") == "transcript":
                    yield event
                elif event.get("type") == "error":
                    logger.error("[STT] Server error: %s", event)
                    break
                elif event.get("type") == "completed":
                    break
        finally:
            sender_task.cancel()
            await self.disconnect()
