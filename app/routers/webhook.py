"""Telegram webhook — full message processing pipeline.

Flow:
1. Receive update from Telegram
2. Resolve/create user
3. Save raw message to `messages`
4. Send ack: "Recibido, dame un segundo"
5. Route intent with Haiku
6. Extract fields with Sonnet
7. Return confirmation to user (editable)
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import telegram as telegram_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import router as router_svc
from app.services import extractor as extractor_svc
from app.services import persistence as persist_svc

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram"], prefix="/telegram")


@router.post("/webhook")
async def telegram_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    """
    Process incoming Telegram update through the full pipeline.
    """
    body = await request.json()
    logger.debug("Webhook payload: %s", json.dumps(body, indent=2)[:500])

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

    # Determine message type
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
    await session.flush()  # ensure user.id is available

    # ---- 3. Persist raw message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.telegram,
        message_type=message_type,
        text=text,
        file_path=None,  # TODO: download photo/audio to MinIO
    )
    await session.flush()

    # ---- 4. Send typing indicator ----
    if settings.TELEGRAM_BOT_TOKEN:
        await telegram_svc.send_typing(chat_id)
        await message_svc.update_message_status(session, db_message, MessageStatus.acked)

    # ---- 5. Route intent ----
    content_for_routing = text or "[audio/photo message]"

    # Ultra-short messages ("ok", "sí", "no" → 1-3 chars) default to note
    if text and len(text.strip()) <= 3:
        target_table = "note"
        routing = {"target_table": "note", "reasoning": "short_message"}
    else:
        routing = await router_svc.route_intent(content_for_routing)
        target_table = routing.get("target_table", "note")

    # ---- 6. Extract fields (Sonnet) ----
    # Only extract for content-bearing messages, not corrections
    extraction = {}
    if target_table != "search" and text:
        extraction = await extractor_svc.extract_fields(text, target_table)

    # Store extraction result on the message
    db_message.extraction_result = {
        "routing": routing,
        "target_table": target_table,
        "extraction": extraction,
    }
    await message_svc.update_message_status(session, db_message, MessageStatus.extracted)

    # ---- 7. Persist to target table (deterministic write) ----
    persisted_id = await _persist_extraction(
        session=session,
        user_id=user.id,
        target_table=target_table,
        extraction=extraction,
        text=text,
        source_message_id=db_message.id,
    )

    # ---- 8. Build confirmation message (editable) ----
    confirmation_text = _build_confirmation(target_table, extraction, text)
    if settings.TELEGRAM_BOT_TOKEN and confirmation_text:
        await telegram_svc.send_message(chat_id, confirmation_text)
    await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)

    # ---- 9. Commit everything ----
    await session.commit()

    return {
        "status": "processed",
        "chat_id": chat_id,
        "target_table": target_table,
    }


def _build_confirmation(target_table: str, extraction: dict, original_text: str | None) -> str:
    """Build a human-readable confirmation message. None-safe on all fields."""
    if not extraction:
        return ""

    match target_table:
        case "asset":
            asset_type = extraction.get("asset_type") or "otro"
            name = extraction.get("name") or original_text or "nuevo registro"
            return (
                f"📋 Entendido, voy a guardar:\n"
                f"*{name}* ({asset_type})\n\n"
                f"¿Está bien? Responde *sí* para confirmar o dime qué corregir."
            )

        case "event":
            title = extraction.get("title") or original_text or "evento"
            target_date = extraction.get("target_date") or ""
            date_str = f" — {target_date}" if target_date else ""
            return (
                f"📅 Voy a recordarte:\n"
                f"*{title}*{date_str}\n\n"
                f"¿Está bien? Responde *sí* o dime qué ajustar."
            )

        case "list_item":
            list_name = extraction.get("list_name") or "general"
            items = extraction.get("items") or []
            items_str = "\n".join(f"  • {item}" for item in items) if items else "  • (sin ítems)"
            return (
                f"📝 Agregado a *{list_name}*:\n"
                f"{items_str}\n\n"
                f"¿Falta algo? Dime y lo agrego."
            )

        case "note":
            topic = extraction.get("topic_name") or "general"
            content = extraction.get("content") or original_text or ""
            preview = content[:100] + "..." if len(content) > 100 else content
            return (
                f"💡 Nota en *{topic}*:\n"
                f"{preview}\n\n"
                f"¿OK? Responde *sí* o dime qué cambiar."
            )

        case "shared_expense":
            desc = extraction.get("description") or original_text or "gasto"
            amount = extraction.get("amount") or 0
            participants = extraction.get("participants") or []
            per_person = amount / len(participants) if participants else amount
            return (
                f"💰 *{desc}*\n"
                f"Monto: ${amount:.2f} entre {len(participants)} personas\n"
                f"≈ ${per_person:.2f} por persona\n\n"
                f"¿Confirmas? Responde *sí* o ajusta los datos."
            )

        case _:
            return ""


async def _persist_extraction(
    session: AsyncSession,
    user_id,
    target_table: str,
    extraction: dict,
    text: str | None,
    source_message_id,
) -> str | None:
    """
    Persist extracted data to the correct target table.
    Returns the ID of the created entity as a string, or None.
    """
    if not extraction:
        return None

    match target_table:
        case "asset":
            asset = await persist_svc.persist_asset(
                session=session,
                user_id=user_id,
                asset_type=extraction.get("asset_type", "other"),
                name=extraction.get("name", text or "sin nombre"),
                attributes=extraction.get("attributes", {}),
                notes=extraction.get("notes"),
                source_message_id=source_message_id,
            )
            return str(asset.id)

        case "event":
            event = await persist_svc.persist_event(
                session=session,
                user_id=user_id,
                title=extraction.get("title", text or "evento"),
                target_date=extraction.get("target_date", ""),
                description=extraction.get("description"),
                certainty=extraction.get("certainty", "certain"),
                recurrence_rule=extraction.get("recurrence_rule"),
            )
            return str(event.id)

        case "list_item":
            items = await persist_svc.persist_list_items(
                session=session,
                user_id=user_id,
                list_name=extraction.get("list_name", "general"),
                items=extraction.get("items", [text] if text else []),
                quantity=extraction.get("quantity"),
            )
            return items[0].list_id if items else None

        case "note":
            note = await persist_svc.persist_note(
                session=session,
                user_id=user_id,
                topic_name=extraction.get("topic_name", "general"),
                content=extraction.get("content", text or ""),
                source_message_id=source_message_id,
            )
            return str(note.id)

        case _:
            return None
