"""WhatsApp webhook — receive messages from WhatsApp Cloud API.

Architecture:
- Messages are immediately saved with ⏳ reaction + typing indicator.
- A 3-second debounce timer waits for the user to finish typing.
- When silence is detected, all pending messages are processed together.
- The agent sees the full burst as conversation context.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.models.message import Message as MessageModel
from app.services import minio as minio_svc
from app.services import whatsapp as whatsapp_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import whisper as whisper_svc
from app.agent import process_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"], prefix="/whatsapp")

# =============================================================================
# DEBOUNCE SYSTEM — waits 3s of silence before calling the agent
# =============================================================================

_DEBOUNCE_SECONDS = 3.0
_debounce_timers: dict[str, asyncio.Task] = {}
_processing_locks: dict[str, bool] = {}


def _cancel_debounce(phone: str) -> None:
    """Cancel any pending debounce timer for this user."""
    task = _debounce_timers.pop(phone, None)
    if task and not task.done():
        task.cancel()


async def _debounce_agent_call(phone: str):
    """Wait for silence, then call the agent with all pending messages."""
    try:
        await asyncio.sleep(_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return  # new message arrived, timer reset

    # Remove from timers
    _debounce_timers.pop(phone, None)

    # Process pending messages
    if _processing_locks.get(phone):
        return  # already processing (shouldn't happen)

    _processing_locks[phone] = True
    try:
        from app.database import async_session
        async with async_session() as session:
            await _process_pending_messages(session, phone)
    except Exception:
        logger.exception("Debounce agent call failed for %s", phone)
    finally:
        _processing_locks.pop(phone, None)


def _schedule_debounce(phone: str) -> None:
    """Schedule/reset the debounce timer for a user."""
    _cancel_debounce(phone)
    _debounce_timers[phone] = asyncio.create_task(_debounce_agent_call(phone))


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================


@router.get("/webhook")
async def whatsapp_webhook_verify(
    mode: str = Query(default="", alias="hub.mode"),
    token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
):
    """Verify WhatsApp webhook subscription."""
    is_valid, response_challenge = whatsapp_svc.verify_webhook(mode, token, challenge)
    if is_valid and response_challenge:
        return Response(content=str(response_challenge), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook")
async def whatsapp_webhook_receive(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Receive and process incoming WhatsApp messages."""
    body = await request.json()
    logger.info("WhatsApp webhook payload: object=%s entries=%s", body.get("object"), len(body.get("entry", [])))

    if body.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])

            if not messages and statuses:
                continue  # skip status updates

            if not messages:
                continue

            for msg in messages:
                await _handle_incoming_message(session, msg)

    return {"status": "processed"}


# =============================================================================
# MESSAGE HANDLING — immediate ack, debounced agent call
# =============================================================================


async def _handle_incoming_message(session: AsyncSession, msg: dict) -> None:
    """
    Handle an incoming WhatsApp message:
    1. Dedup
    2. Send ⏳ reaction + typing indicator
    3. Save message to DB immediately
    4. Schedule debounced agent call
    """
    from_number = msg.get("from")
    msg_id = msg.get("id", "unknown")

    if not from_number:
        logger.warning("WhatsApp message without 'from' field: %s", msg_id)
        return

    # ---- Dedup ----
    result = await session.execute(
        select(MessageModel.id).where(
            MessageModel.extraction_result.contains({"whatsapp_message_id": msg_id})
        ).limit(1)
    )
    if result.scalar_one_or_none():
        logger.info("Skipping duplicate WhatsApp message: %s", msg_id)
        return

    # ---- Immediate ack: typing indicator only ----
    await whatsapp_svc.send_typing(from_number, msg_id)

    # ---- Resolve user early (needed for MinIO uploads) ----
    user = await user_svc.resolve_user_by_phone(
        session=session,
        phone_number=from_number,
    )
    await session.flush()

    # ---- Process message by type ----
    text = None
    file_path = None
    transcription = None
    msg_type = msg.get("type", "text")

    match msg_type:
        case "text":
            text = msg.get("text", {}).get("body", "")
            message_type = MessageType.text
            file_path = f"whatsapp://{from_number}/{msg_id}"

        case "image" | "document":
            text, file_path = await _download_and_store_media(
                msg, msg_type, str(user.id), from_number, msg_id
            )
            message_type = MessageType.photo

        case "audio" | "voice":
            text, file_path, transcription = await _download_and_transcribe_audio(
                msg, msg_type, str(user.id), from_number, msg_id
            )
            message_type = MessageType.audio

        case "sticker":
            await whatsapp_svc.send_message(
                from_number,
                "Todavía no puedo ver stickers 😅. Mandame texto, foto o audio y con gusto te ayudo.",
            )
            return

        case "button" | "interactive":
            interactive = msg.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            list_reply = interactive.get("list_reply", {})
            text = button_reply.get("title") or button_reply.get("id") or list_reply.get("title") or ""
            message_type = MessageType.text
            file_path = f"whatsapp://{from_number}/{msg_id}"
            if not text:
                return

        case _:
            logger.info("Unsupported message type '%s' from %s", msg_type, from_number)
            await whatsapp_svc.send_message(
                from_number,
                f"Recibí tu mensaje pero todavía no sé procesar contenido tipo '{msg_type}'. ¿Me lo contás con texto o foto?",
            )
            return

    if not text:
        logger.warning("WhatsApp message %s without extractable text", msg_id)
        return

    # ---- Persist message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.whatsapp,
        message_type=message_type,
        text=text,
        file_path=file_path or f"whatsapp://{from_number}/{msg_id}",
    )
    if transcription:
        db_message.transcription = transcription
    db_message.extraction_result = {"whatsapp_message_id": msg_id, "pending": True}
    await session.commit()

    logger.info("Saved WhatsApp msg %s from %s: %s", msg_id, from_number, text[:80])

    # ---- Schedule debounced agent call ----
    _schedule_debounce(from_number)


# =============================================================================
# MEDIA HELPERS — download from WhatsApp, upload to MinIO, transcribe audio
# =============================================================================


async def _download_and_store_media(
    msg: dict,
    msg_type: str,
    user_id: str,
    from_number: str,
    msg_id: str,
) -> tuple[str | None, str | None]:
    """
    Download image/document from WhatsApp and upload to MinIO.
    Returns (text, file_key) tuple.
    """
    media_obj = msg.get(msg_type, {})
    media_id = media_obj.get("id")
    if not media_id:
        logger.warning("WhatsApp %s without media_id from %s", msg_type, from_number)
        return f"[{msg_type}: error al recibir]", None

    caption = media_obj.get("caption", "")
    mime_type = media_obj.get("mime_type", "")

    # Download from WhatsApp servers
    file_bytes = await whatsapp_svc.download_media(media_id)
    if not file_bytes:
        logger.error("Failed to download %s %s from %s", msg_type, media_id, from_number)
        return f"[{msg_type}: no se pudo descargar]", None

    # Determine filename
    filename = _media_filename(msg_type, media_id, mime_type, media_obj)

    # Upload to MinIO
    file_key = await minio_svc.upload_file(
        user_id=user_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=mime_type or "application/octet-stream",
    )
    if not file_key:
        return f"[{msg_type}: error al guardar]", None

    # Format according to system prompt conventions (match Telegram format):
    # [foto: user_id/photo.jpg] — without instruction, agent asks what to do
    # [foto: user_id/photo.jpg] Guardar como X — with instruction inline
    if msg_type == "document":
        text = f"[documento: {filename} \u2192 {file_key}]"
    else:
        text = f"[foto: {file_key}]"
    if caption:
        # Telegram-style: file_key FIRST, then the user's caption/instruction
        text = f"[foto: {file_key}] {caption}"

    logger.info("Stored %s from %s: %s (%d bytes)", msg_type, from_number, file_key, len(file_bytes))
    return text, file_key


async def _download_and_transcribe_audio(
    msg: dict,
    msg_type: str,
    user_id: str,
    from_number: str,
    msg_id: str,
) -> tuple[str | None, str | None, str | None]:
    """
    Download audio/voice note from WhatsApp, upload to MinIO, and transcribe.
    Returns (text, file_key, transcription) tuple.
    """
    media_obj = msg.get(msg_type, {})
    media_id = media_obj.get("id")
    if not media_id:
        logger.warning("WhatsApp %s without media_id from %s", msg_type, from_number)
        return f"[{msg_type}: error al recibir]", None, None

    mime_type = media_obj.get("mime_type", "")

    # Download from WhatsApp servers
    file_bytes = await whatsapp_svc.download_media(media_id)
    if not file_bytes:
        logger.error("Failed to download %s %s from %s", msg_type, media_id, from_number)
        return f"[{msg_type}: no se pudo descargar]", None, None

    # Determine filename
    filename = _media_filename(msg_type, media_id, mime_type, media_obj)

    # Upload to MinIO
    file_key = await minio_svc.upload_file(
        user_id=user_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=mime_type or "audio/ogg",
    )
    if not file_key:
        return f"[{msg_type}: error al guardar]", None, None

    # Transcribe with Whisper
    transcription = await whisper_svc.transcribe_audio(file_bytes, filename)
    if transcription:
        logger.info("Audio transcribed from %s: %s", from_number, transcription[:120])
        return transcription, file_key, transcription
    else:
        return f"[{msg_type}: recibido - no se pudo transcribir]", file_key, None


def _media_filename(
    msg_type: str,
    media_id: str,
    mime_type: str,
    media_obj: dict,
) -> str:
    """Generate a filename for a WhatsApp media file."""
    short_id = media_id[-12:] if len(media_id) >= 12 else media_id

    # Use original filename for documents
    if msg_type == "document":
        original = media_obj.get("filename", "")
        if original:
            return f"doc_{short_id}_{original}"

    # Map mime types to extensions
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
        "audio/mpeg": ".mp3",
        "audio/webm": ".webm",
        "application/pdf": ".pdf",
    }
    ext = ".bin"
    for mime, extension in ext_map.items():
        if mime_type.startswith(mime.split("/")[0] + "/") and mime in ext_map:
            ext = ext_map[mime]
            break
    else:
        # Fallback by type
        if msg_type in ("audio", "voice"):
            ext = ".ogg"
        elif msg_type == "image":
            ext = ".jpg"

    return f"{msg_type}_{short_id}{ext}"


# =============================================================================
# AGENT PROCESSING — called after debounce silence
# =============================================================================


async def _process_pending_messages(session: AsyncSession, phone: str) -> None:
    """
    Process all pending messages for a user.
    Called by the debounce timer after 3s of silence.
    """
    # Find user
    result = await session.execute(
        select(user_svc.User).where(
            (user_svc.User.whatsapp_id == phone) | (user_svc.User.telegram_id == phone)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("Debounce: user not found for %s", phone)
        return

    # Find all pending messages (not yet processed)
    result = await session.execute(
        select(MessageModel)
        .where(
            MessageModel.user_id == user.id,
            MessageModel.extraction_result.contains({"pending": True}),
        )
        .order_by(MessageModel.received_at.asc())
        .limit(10)
    )
    pending = result.scalars().all()

    if not pending:
        return

    # Build combined text from all pending messages
    texts = [m.text for m in pending if m.text]
    combined_text = "\n".join(texts)

    # ---- Inject recent photo file_key if user references a photo ----
    photo_keywords = ("foto", "imagen", "imágenes", "captura", "guardar", "guarda",
                      "guardame", "guardala", "guardalo", "esa foto", "la foto",
                      "esa imagen", "analiza", "analizala", "analízala")
    has_text_only = all(
        m.message_type == MessageType.text for m in pending
    )
    if has_text_only and any(kw in combined_text.lower() for kw in photo_keywords):
        recent_photo_key = await _find_recent_photo_key(session, user.id)
        if recent_photo_key:
            combined_text = f"[foto: {recent_photo_key}] {combined_text}"
            logger.info("Injected recent photo file_key into context: %s", recent_photo_key)

    logger.info(
        "Debounce agent call: user=%s, %d pending msgs: %s",
        user.id, len(pending), combined_text[:120],
    )

    # ---- Photo-only: quick confirmation, skip agent ----
    has_photo_only = all(
        m.message_type == MessageType.photo for m in pending
    )
    is_photo_placeholder = all(
        (m.text or "").startswith("[foto:") and (m.text or "").count(" ") == 0
        for m in pending
    )
    if has_photo_only and is_photo_placeholder:
        await whatsapp_svc.send_message(
            phone,
            "📷 Recibí tu foto. ¿Querés que la analice, la guarde, o qué hacemos?",
        )
        await _mark_all_processed(session, pending)
        await session.commit()
        logger.info("Photo-only debounce: quick confirmation sent to %s", phone)
        return

    # ---- Onboarding check ----
    if not user.onboarding_complete:
        if user.onboarding_step == 0:
            await _send_onboarding_step0(phone, user)
            user.onboarding_step = 1
            await _mark_all_processed(session, pending)
            await session.commit()
            return
        elif user.onboarding_step == 1:
            name = combined_text.strip().split("\n")[0][:128]  # first line as name
            user.preferred_name = name
            await _send_onboarding_step1(phone, name)
            user.onboarding_step = 2
            await _mark_all_processed(session, pending)
            await session.commit()
            return
        elif user.onboarding_step == 2:
            # Parse accent choice
            accent_map = {
                "1": "costeno", "costeño": "costeno", "costeno": "costeno", "costa": "costeno",
                "2": "serrano", "serrano": "serrano", "sierra": "serrano", "quiteño": "serrano", "quitena": "serrano",
                "3": "amazonico", "amazónico": "amazonico", "amazonico": "amazonico", "amazonía": "amazonico", "amazonia": "amazonico",
                "4": "neutral", "neutral": "neutral", "neutro": "neutral", "normal": "neutral",
            }
            raw = combined_text.strip().lower().split("\n")[0]
            accent = accent_map.get(raw, "neutral")

            # Save accent to user profile
            from app.models.user_profile import UserProfile
            profile_result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.accent = accent
            else:
                profile = UserProfile(user_id=user.id, accent=accent)
                session.add(profile)

            await _send_onboarding_step2(phone, user.preferred_name or name, accent)
            user.onboarding_step = 0
            user.onboarding_complete = True
            await _mark_all_processed(session, pending)
            await session.commit()
            return

    # ---- Post-pago flow (steps 3-6, trial expired data collection) ----
    if not user.onboarding_complete and 3 <= user.onboarding_step <= 6:
        result = await user_svc.advance_post_pago_step(
            session, str(user.id), user.onboarding_step, combined_text
        )
        await whatsapp_svc.send_message(phone, result["message"])
        await _mark_all_processed(session, pending)
        await session.commit()
        return

    # ---- Access check ----
    access = await user_svc.check_access(session, str(user.id))
    if not access.allowed:
        # Post-pago start: trial just expired, kick off the flow
        if access.post_pago_step is not None:
            msg = await user_svc.get_post_pago_start_message(session, str(user.id))
            user.onboarding_step = 3  # advance to first post-pago step
            await whatsapp_svc.send_message(phone, msg)
            await _mark_all_processed(session, pending)
            await session.commit()
            return
        # Regular denial (expired with data collected, cancelled, etc.)
        await whatsapp_svc.send_message(phone, access.reason)
        await _mark_all_processed(session, pending)
        await session.commit()
        return

    # ---- Call the agent ----
    response = await process_message(
        session=session,
        user_id=str(user.id),
        user_message=combined_text,
    )

    response_text = response.get("text", "") if isinstance(response, dict) else response
    files = response.get("files", []) if isinstance(response, dict) else []

    # ---- Send files ----
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
                    phone=phone,
                    photo_bytes=file_bytes,
                    caption=caption if caption else None,
                    filename=filename,
                )
        except Exception as exc:
            logger.exception("WhatsApp photo send failed '%s': %s", file_key, exc)

    # ---- Send text response ----
    if response_text:
        skip_text = (
            files
            and len(response_text) < 80
            and any(phrase in response_text.lower() for phrase in [
                "aquí está", "aquí tenés", "listo", "acá está"
            ])
        )
        if not skip_text:
            await whatsapp_svc.send_message(phone, response_text)

    # ---- Mark all as processed ----
    await _mark_all_processed(session, pending, response_text)

    # Mark onboarding complete
    if not user.onboarding_complete:
        user.onboarding_complete = True

    await session.commit()
    logger.info("Debounce complete for %s: %d msgs processed", phone, len(pending))


async def _mark_all_processed(
    session: AsyncSession,
    messages: list,
    agent_response: str | None = None,
) -> None:
    """Mark pending messages as processed."""
    for m in messages:
        m.extraction_result = {"acknowledged": True}
        m.status = MessageStatus.confirmed
        if agent_response and m == messages[0]:
            m.extraction_result = {
                "agent_response": agent_response,
                "batch_size": len(messages),
            }
    await session.flush()


async def _find_recent_photo_key(session: AsyncSession, user_id) -> str | None:
    """
    Find the most recent photo message with a MinIO file_key for a user.
    Looks back up to 2 minutes to find the last image the user sent.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(minutes=2)
    result = await session.execute(
        select(MessageModel)
        .where(
            MessageModel.user_id == user_id,
            MessageModel.message_type == MessageType.photo,
            MessageModel.received_at >= cutoff,
            MessageModel.file_path.isnot(None),
            MessageModel.file_path.not_like("whatsapp://%"),
        )
        .order_by(MessageModel.received_at.desc())
        .limit(1)
    )
    msg = result.scalar_one_or_none()
    if msg and msg.file_path:
        return msg.file_path
    return None


# =============================================================================
# ONBOARDING MESSAGES
# =============================================================================


async def _send_onboarding_step0(phone: str, user) -> None:
    """Step 0: Send welcome messages 1 (presentation) + 2 (ask name)."""
    msg1 = (
        "👋 ¡Hola!\n\n"
        "Soy Lucho, tu asistente personal ecuatoriano 🇪🇨\n\n"
        "Estoy aquí para ser tu segundo cerebro: "
        "recordar, organizar y encontrar tu información del día a día.\n\n"
        "¿Qué puedo hacer por vos?\n\n"
        "🚗 Vehículos — Guardar tu placa, alertas de pico y placa, "
        "fechas de matriculación\n\n"
        "📄 Documentos — Guardar cédula, facturas, garantías "
        "con fecha de vencimiento\n\n"
        "📅 Recordatorios — Citas, eventos, fechas importantes "
        "con anticipación\n\n"
        "📝 Listas y notas — Compras, tareas, ideas organizadas por tema\n\n"
        "📋 Proyectos — Tareas agrupadas con fechas de entrega\n\n"
        "💰 Finanzas personales — Registrar gastos e ingresos, "
        "consultar tu balance, crear presupuestos por categoría "
        "y recibir alertas cuando te pasás\n\n"
        "🔍 Búsqueda — Encontrar todo lo que guardaste "
        "y también buscar en internet\n\n"
        "Mandame lo que necesités sin estructura, "
        "yo lo organizo. ¡Hablame como a un amigo!"
    )
    await whatsapp_svc.send_message(phone, msg1)

    msg2 = (
        "⚡ Para iniciar a trabajar, "
        "¿Cómo quieres que te llame?\n\n"
        "Dime tu nombre y empezamos...."
    )
    await whatsapp_svc.send_message(phone, msg2)


async def _send_onboarding_step1(phone: str, name: str) -> None:
    """Step 1: User gave their name. Ask for accent preference."""
    msg = (
        f"👏 Perfecto *{name}*!\n\n"
        "Ahora dime, ¿con qué acento quieres que te hable?\n\n"
        "1️⃣ *Costeño* 🏖️ — \"¡Habla mijo!\" (costa/peninsular)\n"
        "2️⃣ *Serrano* 🏔️ — \"¡De ley veci!\" (sierra/quiteño)\n"
        "3️⃣ *Amazónico* 🌿 — \"¡De ley pana!\" (amazonía)\n"
        "4️⃣ *Neutral* 🇪🇨 — Ecuatoriano estándar\n\n"
        "Responde con el número o el nombre del acento. "
        "Lo puedes cambiar en cualquier momento diciendo \"cambia a costeño\"."
    )
    await whatsapp_svc.send_message(phone, msg)


async def _send_onboarding_step2(phone: str, name: str, accent: str) -> None:
    """Step 2: Accent confirmed. Start trial with regional greeting."""
    greetings = {
        "costeno": "¡Habla mijo! Qué bueno tenerte por aquí.",
        "serrano": "¡De ley veci! Qué bueno tenerte por aquí.",
        "amazonico": "¡De ley pana! Qué bueno tenerte por aquí.",
        "neutral": "¡Perfecto! Qué bueno tenerte por aquí.",
    }
    greeting = greetings.get(accent, greetings["neutral"])

    msg = (
        f"{greeting}\n\n"
        f"🎉 Tienes *7 días de prueba GRATIS* con acceso a "
        "todas las funcionalidades. Sin datos de pago.\n\n"
        "Al finalizar, si quieres continuar, eliges tu plan. "
        "Por ahora, ¡disfruta Lucho! 🚀"
    )
    await whatsapp_svc.send_message(phone, msg)
