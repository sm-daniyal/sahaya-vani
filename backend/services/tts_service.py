import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

logger = logging.getLogger(__name__)


class GnaniTTSService:
    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    @property
    def _headers(self) -> dict:
        return {
            "X-API-Key-ID": settings.gnani_api_key,
            "Content-Type": "application/json",
        }

    async def _connect(self) -> None:
        url = "wss://api.vachana.ai/api/v1/tts"
        logger.info("[TTS] Connecting to %s", url)
        self._ws = await websockets.connect(
            url,
            additional_headers=self._headers,
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=10,
        )
        logger.info("[TTS] Connected")

    async def _disconnect(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        logger.info("[TTS] Disconnected")

    async def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        await self._connect()

        payload = json.dumps({
            "text": text,
            "voice": "Kaveri",
            "model": "timbre-v2.5",
            "audio_config": {
                "sample_rate": 16000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        })

        try:
            await self._ws.send(payload)
            logger.debug("[TTS] Sent synthesis request for %d chars", len(text))

            while True:
                try:
                    msg = await asyncio.wait_for(self._ws.recv(), timeout=15.0)
                except asyncio.TimeoutError:
                    logger.warning("[TTS] Timeout waiting for audio chunk")
                    break

                if isinstance(msg, bytes):
                    if msg:
                        yield msg
                elif isinstance(msg, str):
                    try:
                        ctrl = json.loads(msg)
                        msg_type = ctrl.get("type") or ctrl.get("event")
                        if msg_type == "audio":
                            b64 = ctrl.get("data", {}).get("audio", "")
                            if b64:
                                yield base64.b64decode(b64)
                        elif msg_type in ("completed", "complete"):
                            logger.debug("[TTS] Synthesis complete")
                            break
                        elif msg_type == "error" or ctrl.get("error"):
                            logger.error("[TTS] Server error: %s", ctrl.get("message") or ctrl.get("error"))
                            break
                    except json.JSONDecodeError:
                        pass
        except ConnectionClosed as exc:
            logger.warning("[TTS] Connection closed: %s", exc)
        finally:
            await self._disconnect()
