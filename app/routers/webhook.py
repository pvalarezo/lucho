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

    # ---- 4. Send immediate ack ----
    if settings.TELEGRAM_BOT_TOKEN:
        await telegram_svc.send_message(chat_id, "Recibido, dame un segundo ✋")
        await message_svc.update_message_status(session, db_message, MessageStatus.acked)

    # ---- 5. Route intent (Haiku) ----
    content_for_routing = text or "[audio/photo message]"
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

    # ---- 7. Build confirmation message (editable) ----
    confirmation_text = _build_confirmation(target_table, extraction, text)
    if settings.TELEGRAM_BOT_TOKEN and confirmation_text:
        await telegram_svc.send_message(chat_id, confirmation_text)

    # ---- 8. Commit everything ----
    await session.commit()

    return {
        "status": "processed",
        "chat_id": chat_id,
        "target_table": target_table,
    }


def _build_confirmation(target_table: str, extraction: dict, original_text: str | None) -> str:
    """Build a human-readable confirmation message based on extraction results."""
    if not extraction:
        return ""

    match target_table:
        case "asset":
            asset_type = extraction.get("asset_type", "otro")
            name = extraction.get("name", original_text or "nuevo registro")
            return (
                f"📋 Entendido, voy a guardar:\n"
                f"*{name}* ({asset_type})\n\n"
                f"¿Está bien? Responde *sí* para confirmar o dime qué corregir."
            )

        case "event":
            title = extraction.get("title", original_text or "evento")
            target_date = extraction.get("target_date", "")
            date_str = f" — {target_date}" if target_date else ""
            return (
                f"📅 Voy a recordarte:\n"
                f"*{title}*{date_str}\n\n"
                f"¿Está bien? Responde *sí* o dime qué ajustar."
            )

        case "list_item":
            list_name = extraction.get("list_name", "general")
            items = extraction.get("items", [])
            items_str = "\n".join(f"  • {item}" for item in items)
            return (
                f"📝 Agregado a *{list_name}*:\n"
                f"{items_str}\n\n"
                f"¿Falta algo? Dime y lo agrego."
            )

        case "note":
            topic = extraction.get("topic_name", "general")
            content = extraction.get("content", original_text or "")
            preview = content[:100] + "..." if len(content) > 100 else content
            return (
                f"💡 Nota en *{topic}*:\n"
                f"{preview}\n\n"
                f"¿OK? Responde *sí* o dime qué cambiar."
            )

        case "shared_expense":
            desc = extraction.get("description", original_text or "gasto")
            amount = extraction.get("amount", 0)
            participants = extraction.get("participants", [])
            per_person = amount / len(participants) if participants else amount
            return (
                f"💰 *{desc}*\n"
                f"Monto: ${amount:.2f} entre {len(participants)} personas\n"
                f"≈ ${per_person:.2f} por persona\n\n"
                f"¿Confirmas? Responde *sí* o ajusta los datos."
            )

        case _:
            return ""
