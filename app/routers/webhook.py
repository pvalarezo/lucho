"""Telegram webhook — production-ready endpoint using the Lucho Agent.

Flow:
1. Receive update from Telegram
2. Resolve/create user
3. Upload files/documents to MinIO
4. Persist raw message
5. Send typing indicator
6. Call the Lucho Agent → response
7. Send files (if any) + text response via Telegram
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import minio as minio_svc
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
    document = msg.get("document")

    if photo:
        message_type = MessageType.photo
    elif audio:
        message_type = MessageType.audio
    elif document:
        message_type = MessageType.photo  # treat documents like files (store in MinIO)
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

    # ---- 3. Photo: upload to MinIO, let agent handle analysis ----
    file_object_key = None
    if photo:
        try:
            # Pick largest photo (last in array)
            largest_photo = photo[-1]
            photo_bytes = await telegram_svc.download_file(largest_photo["file_id"])
            if photo_bytes:
                file_object_key = await minio_svc.upload_file(
                    user_id=str(user.id),
                    file_bytes=photo_bytes,
                    filename=f"photo_{msg.get('message_id', 'unknown')}.jpg",
                    content_type="image/jpeg",
                )
        except Exception as exc:
            logger.exception("Webhook photo upload failed: %s", exc)

        # Include file_key context for the agent (always, with or without caption)
        if not text and file_object_key:
            text = f"[foto: {file_object_key}]"
        elif text and file_object_key:
            text = f"[foto: {file_object_key}] {text}"

    # ---- 4. Document (PDF, DOC, etc.): upload to MinIO ----
    doc_object_key = None
    if document and not photo:
        doc_name = document.get("file_name", "documento")
        try:
            doc_bytes = await telegram_svc.download_file(document["file_id"])
            if doc_bytes:
                doc_object_key = await minio_svc.upload_file(
                    user_id=str(user.id),
                    file_bytes=doc_bytes,
                    filename=f"doc_{msg.get('message_id', 'unknown')}_{doc_name}",
                    content_type=document.get("mime_type", "application/octet-stream"),
                )
                if not text:
                    text = f"[documento: {doc_name} → {doc_object_key}]"
                else:
                    text = f"{text}\n[documento adjunto: {doc_name} → {doc_object_key}]"
        except Exception as exc:
            logger.exception("Webhook document upload failed: %s", exc)

    file_path = file_object_key or doc_object_key or f"telegram://{chat_id}/{msg.get('message_id', 0)}"

    # ---- 5. Persist raw message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.telegram,
        message_type=message_type,
        text=text,
        file_path=file_path,
    )
    await session.flush()

    # ---- 6. Send typing indicator ----
    if settings.TELEGRAM_BOT_TOKEN:
        await telegram_svc.send_typing(chat_id)
        await message_svc.update_message_status(session, db_message, MessageStatus.acked)

    # ---- 7. Call the Lucho Agent ----
    content = text or "[audio/photo message]"
    response = await process_message(
        session=session,
        user_id=str(user.id),
        user_message=content,
    )

    response_text = response.get("text", "") if isinstance(response, dict) else response
    files = response.get("files", []) if isinstance(response, dict) else []

    # ---- 8. Send files first (if any) ----
    for file_info in files:
        file_key = file_info.get("file_key", "")
        caption = file_info.get("caption", "")
        if not file_key:
            continue
        try:
            file_bytes = await minio_svc.download_file(file_key)
            if file_bytes:
                filename = file_info.get("filename", file_key.split("/")[-1])
                await telegram_svc.send_photo(
                    chat_id=chat_id,
                    photo_bytes=file_bytes,
                    caption=caption if caption else None,
                    filename=filename,
                )
        except Exception as exc:
            logger.exception("Webhook photo send failed '%s': %s", file_key, exc)

    # ---- 9. Send text response ----
    if settings.TELEGRAM_BOT_TOKEN and response_text:
        skip_text = (
            files
            and len(response_text) < 80
            and any(phrase in response_text.lower() for phrase in [
                "aquí está", "aquí tenés", "listo", "acá está"
            ])
        )
        if not skip_text:
            await telegram_svc.send_message(chat_id, response_text)

    await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
    await session.commit()

    return {
        "status": "processed",
        "chat_id": chat_id,
    }
