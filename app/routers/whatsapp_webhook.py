"""WhatsApp webhook — receive messages from WhatsApp Cloud API.

Flow:
1. GET  → webhook verification (Meta challenge)
2. POST → receive messages:
   a. Resolve/create user by WhatsApp phone number
   b. Upload media to MinIO (photos, audio, documents)
   c. Persist raw message
   d. Call the Lucho Agent → response
   e. Send response back via WhatsApp
"""

import logging

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import minio as minio_svc
from app.services import whatsapp as whatsapp_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.agent import process_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"], prefix="/whatsapp")


# =============================================================================
# WEBHOOK VERIFICATION (GET)
# =============================================================================


@router.get("/webhook")
async def whatsapp_webhook_verify(
    mode: str = Query(default="", alias="hub.mode"),
    token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
):
    """
    Verify WhatsApp webhook subscription.
    Called by Meta when setting up or refreshing the webhook.
    """
    is_valid, response_challenge = whatsapp_svc.verify_webhook(mode, token, challenge)

    if is_valid and response_challenge:
        return Response(content=str(response_challenge), media_type="text/plain")

    return Response(content="Verification failed", status_code=403)


# =============================================================================
# INCOMING MESSAGES (POST)
# =============================================================================


@router.post("/webhook")
async def whatsapp_webhook_receive(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Receive and process incoming WhatsApp messages.

    WhatsApp Cloud API sends a JSON payload with:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "593987654321",
              "id": "wamid.xxx",
              "type": "text" | "image" | "audio" | "voice" | "document",
              "text": {"body": "..."},
              ...
            }]
          }
        }]
      }]
    }
    """
    body = await request.json()
    logger.debug("WhatsApp webhook payload received")

    # ---- 1. Validate payload structure ----
    if body.get("object") != "whatsapp_business_account":
        logger.debug("Non-WABA webhook payload, ignoring")
        return {"status": "ignored"}

    entries = body.get("entry", [])
    if not entries:
        return {"status": "no_entry"}

    # Process all entries/changes/messages
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            # Skip status updates (sent, delivered, read receipts)
            if not messages and value.get("statuses"):
                continue

            for msg in messages:
                await _process_whatsapp_message(session, msg)

    return {"status": "processed"}


# =============================================================================
# MESSAGE PROCESSING
# =============================================================================


async def _process_whatsapp_message(
    session: AsyncSession,
    msg: dict,
) -> None:
    """
    Process a single WhatsApp message through the Lucho Agent.

    Steps:
    1. Extract sender info
    2. Resolve/create user
    3. Download media to MinIO (if photo/audio/document)
    4. Persist raw message
    5. Call the Lucho Agent
    6. Send response back via WhatsApp
    """
    from_number = msg.get("from")  # e.g., "593987654321"
    msg_id = msg.get("id", "unknown")
    msg_type = msg.get("type", "text")

    if not from_number:
        logger.warning("WhatsApp message without 'from' field: %s", msg_id)
        return

    # ---- 1. Determine message type and content ----
    text = None
    file_object_key = None

    match msg_type:
        case "text":
            text = msg.get("text", {}).get("body", "")
            message_type = MessageType.text

        case "image":
            message_type = MessageType.photo
            media_id = msg.get("image", {}).get("id")
            caption = msg.get("image", {}).get("caption")
            if media_id:
                image_bytes = await whatsapp_svc.download_media(media_id)
                if image_bytes:
                    file_object_key = await minio_svc.upload_file(
                        user_id=from_number,  # temporary, will use real user_id after resolve
                        file_bytes=image_bytes,
                        filename=f"whatsapp_{msg_id}.jpg",
                        content_type="image/jpeg",
                    )
                    text = f"[foto: {file_object_key}]"
                    if caption:
                        text = f"{text} {caption}"

        case "audio" | "voice":
            message_type = MessageType.audio
            audio_obj = msg.get("audio") or msg.get("voice", {})
            media_id = audio_obj.get("id")
            if media_id:
                audio_bytes = await whatsapp_svc.download_media(media_id)
                if audio_bytes:
                    from app.services import whisper as whisper_svc

                    file_object_key = await minio_svc.upload_file(
                        user_id=from_number,
                        file_bytes=audio_bytes,
                        filename=f"whatsapp_{msg_id}.ogg",
                        content_type="audio/ogg",
                    )
                    try:
                        text = await whisper_svc.transcribe(audio_bytes)
                    except Exception as exc:
                        logger.exception("WhatsApp audio transcription failed: %s", exc)
                        text = "[audio no transcrito]"

        case "document":
            message_type = MessageType.photo  # store in MinIO like photos
            doc_obj = msg.get("document", {})
            media_id = doc_obj.get("id")
            doc_filename = doc_obj.get("filename", f"doc_{msg_id}")
            doc_caption = doc_obj.get("caption")
            if media_id:
                doc_bytes = await whatsapp_svc.download_media(media_id)
                if doc_bytes:
                    file_object_key = await minio_svc.upload_file(
                        user_id=from_number,
                        file_bytes=doc_bytes,
                        filename=f"whatsapp_{msg_id}_{doc_filename}",
                        content_type=doc_obj.get("mime_type", "application/octet-stream"),
                    )
                    text = f"[documento: {doc_filename} → {file_object_key}]"
                    if doc_caption:
                        text = f"{text} {doc_caption}"

        case "button" | "interactive":
            message_type = MessageType.text
            # Extract text from interactive/button messages
            interactive = msg.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            list_reply = interactive.get("list_reply", {})
            text = button_reply.get("title") or button_reply.get("id") or list_reply.get("title") or ""
            if not text:
                logger.info("WhatsApp interactive message without text: %s", msg_id)
                return

        case _:
            logger.info("Unsupported WhatsApp message type '%s' from %s", msg_type, from_number)
            return

    if not text:
        logger.warning("WhatsApp message %s without extractable text", msg_id)
        return

    # ---- 2. Resolve or create user ----
    user = await user_svc.resolve_user_by_phone(
        session=session,
        phone_number=from_number,
    )
    await session.flush()

    # Update file_object_key with real user_id if needed
    file_path = file_object_key or f"whatsapp://{from_number}/{msg_id}"

    # ---- 3. Persist raw message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.whatsapp,
        message_type=message_type,
        text=text,
        file_path=file_path,
    )
    await session.flush()

    # ---- 4. Call the Lucho Agent ----
    content = text or "[audio/photo message]"
    response = await process_message(
        session=session,
        user_id=str(user.id),
        user_message=content,
    )

    response_text = response.get("text", "") if isinstance(response, dict) else response
    files = response.get("files", []) if isinstance(response, dict) else []

    # ---- 5. Send files first (if any) ----
    for file_info in files:
        file_key = file_info.get("file_key", "")
        caption = file_info.get("caption", "")
        if not file_key:
            continue
        try:
            file_bytes = await minio_svc.download_file(file_key)
            if file_bytes:
                filename = file_info.get("filename", file_key.split("/")[-1])
                await whatsapp_svc.send_photo(
                    phone=from_number,
                    photo_bytes=file_bytes,
                    caption=caption if caption else None,
                    filename=filename,
                )
        except Exception as exc:
            logger.exception("WhatsApp photo send failed '%s': %s", file_key, exc)

    # ---- 6. Send text response ----
    if response_text:
        # Skip text if we already sent files with a caption and text is redundant
        skip_text = (
            files
            and len(response_text) < 80
            and any(phrase in response_text.lower() for phrase in [
                "aquí está", "aquí tenés", "listo", "acá está"
            ])
        )
        if not skip_text:
            await whatsapp_svc.send_message(from_number, response_text)

    # ---- 7. Update message status ----
    await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
    await session.commit()

    logger.info(
        "WhatsApp message %s processed: user=%s, type=%s, response_len=%d",
        msg_id,
        user.id,
        msg_type,
        len(response_text),
    )
