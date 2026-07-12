"""Audio transcription service using OpenAI Whisper API.

Handles voice notes sent by users via Telegram. The user sends an audio/voice
message, we download the file, transcribe it, and feed the text into the
normal message pipeline.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str | None:
    """
    Transcribe audio bytes to text using OpenAI Whisper API.
    Returns the transcribed text or None on failure.

    Supports formats: ogg, mp3, wav, m4a (Telegram voice notes are typically OGG).
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — cannot transcribe audio")
        return None

    logger.info("Transcribing audio file: %s (%d bytes)", filename, len(audio_bytes))

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                WHISPER_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                },
                files={
                    "file": (filename, audio_bytes, "audio/ogg"),
                },
                data={
                    "model": "whisper-1",
                    "language": "es",  # Spanish by default for Ecuador
                    "response_format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            transcribed = data.get("text", "").strip()
            logger.info("Transcription complete: %s", transcribed[:120])
            return transcribed

        except httpx.HTTPError as exc:
            logger.error("Whisper transcription failed: %s", exc)
            return None
