"""Telegram webhook — production-ready endpoint using the Lucho Agent.

Flow:
1. Receive update from Telegram
2. Resolve/create user
3. Persist raw message
4. Call the Lucho Agent → response
5. Send response via Telegram
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import telegram as telegram_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.agent import process_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram"], prefix="/telegram")


@router.post("/webhook")
async def telegram_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    """
    Process incoming Telegram update through the Lucho Agent.
    """
    body = await request.json()
    logger.debug("Webhook payload received")

    # ---- 1. Extract message from Telegram update ----
    msg = body.get("message") or body.get("edited_message")
    if not msg:
        return {"status": "no_message"}

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return {"status": "no_chat_id"}

    text = msg.get("text") or msg.get("caption")
    photo = msg.get("photo")
    audio = msg.get("audio") or msg.get("voice")

    if photo:
        message_type = MessageType.photo
    elif audio:
        message_type = MessageType.audio
    else:
        message_type = MessageType.text

    # ---- 2. Resolve or create user ----
    user = await user_svc.resolve_user_by_telegram(
        session=session,
        telegram_id=str(chat_id),
        first_name=chat.get("first_name", ""),
        last_name=chat.get("last_name"),
    )
    await session.flush()

    # ---- 3. Persist raw message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.telegram,
        message_type=message_type,
        text=text,
    )
    await session.flush()

    # ---- 4. Send typing indicator ----
    if settings.TELEGRAM_BOT_TOKEN:
        await telegram_svc.send_typing(chat_id)
        await message_svc.update_message_status(session, db_message, MessageStatus.acked)

    # ---- 5. Call the Lucho Agent ----
    content = text or "[audio/photo message]"
    response_text = await process_message(
        session=session,
        user_id=str(user.id),
        user_message=content,
    )

    # ---- 6. Send response ----
    if settings.TELEGRAM_BOT_TOKEN and response_text:
        await telegram_svc.send_message(chat_id, response_text)

    await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
    await session.commit()

    return {
        "status": "processed",
        "chat_id": chat_id,
    }
