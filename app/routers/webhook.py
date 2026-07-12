"""Telegram webhook — receive messages and send ack."""

import json
import logging

from fastapi import APIRouter, Request

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram"], prefix="/telegram")


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive incoming Telegram messages (text, photo, audio).
    Sends immediate ack: "Recibido, dame un segundo".
    """
    body = await request.json()
    logger.debug("Telegram webhook payload: %s", json.dumps(body, indent=2))

    # Extract message from Telegram update
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"status": "no_message"}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")
    photo = message.get("photo")
    audio = message.get("audio") or message.get("voice")

    if not chat_id:
        return {"status": "no_chat_id"}

    # TODO: resolve/create user from chat_id
    # TODO: persist raw message to `messages` table
    # TODO: send ack: "Recibido, dame un segundo"

    logger.info(
        "Message from chat_id=%s | type=%s | text=%s",
        chat_id,
        "photo" if photo else "audio" if audio else "text",
        text[:80] if text else None,
    )

    return {
        "status": "received",
        "chat_id": chat_id,
    }
