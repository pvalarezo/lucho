"""Lucho Telegram Bot — polling-based bot for development.

Uses python-telegram-bot with polling (no webhook, no SSL, no public IP needed).
Handles text, photo, and voice messages through the full Lucho pipeline.

Run: python run_bot.py
"""

import asyncio
import logging
import uuid

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.config import settings
from app.database import async_session
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import telegram as telegram_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import router as router_svc
from app.services import extractor as extractor_svc
from app.services import persistence as persist_svc
from app.services import whisper as whisper_svc
from app.config import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


# ---- Command handlers ----

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — welcome and onboarding."""
    user = update.effective_user
    welcome = (
        f"👋 ¡Hola {user.first_name}! Soy *Lucho*, tu asistente personal.\n\n"
        f"Podés hablarme sin estructura. Te ayudo a recordar, organizar y encontrar:\n"
        f"• 🚗 *Matriculación y pico y placa* — decime tu placa\n"
        f"• 📅 *Recordatorios* — \"cita dentista el lunes\"\n"
        f"• 📝 *Listas* — \"comprar leche, pan y huevos\"\n"
        f"• 💡 *Notas* — \"idea de negocio: vender empanadas\"\n"
        f"• 💰 *Gastos* — \"pagué la cena $40 entre 4\"\n\n"
        f"Mandame un mensaje y empecemos 🚀"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help."""
    help_text = (
        "🤖 *Lucho — Ayuda*\n\n"
        "Podés pedirme cosas como:\n"
        "• \"Mi carro es PBC-1234, recordame la matriculación\"\n"
        "• \"Cita con el doctor el 20 de agosto a las 3pm\"\n"
        "• \"Comprar arroz, atún y huevos\"\n"
        "• \"El SOAT de mi carro vence en diciembre\"\n"
        "• \"¿Cuándo es mi pico y placa?\"\n"
        "• \"¿Qué tengo pendiente esta semana?\"\n\n"
        "También podés mandarme *fotos* de facturas y *notas de voz*.\n\n"
        "Enviame lo que quieras, yo lo organizo. 😊"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ---- Message handler (core pipeline) ----

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Process any incoming message through the full Lucho pipeline:
    1. Resolve/create user
    2. Persist raw message
    3. Route intent (DeepSeek)
    4. Extract fields (DeepSeek)
    5. Persist to target table
    6. Send confirmation
    """
    msg = update.message
    if not msg:
        return

    chat = update.effective_chat
    chat_id = chat.id
    user_tg = update.effective_user

    # Determine message type
    text = msg.text or msg.caption
    has_photo = bool(msg.photo)
    has_voice = bool(msg.voice)
    has_audio = bool(msg.audio)

    if has_photo:
        message_type = MessageType.photo
    elif has_voice or has_audio:
        message_type = MessageType.audio
    else:
        message_type = MessageType.text

    # ---- 1. Show typing indicator ----
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # ---- 2. Process through pipeline ----
    async with async_session() as session:
        try:
            # Dedup: skip if this message was already processed
            if await _is_duplicate(session, chat_id, msg.message_id):
                logger.debug("Skipping duplicate msg %s from chat %s", msg.message_id, chat_id)
                return

            # Resolve/create user
            user = await user_svc.resolve_user_by_telegram(
                session=session,
                telegram_id=str(chat_id),
                first_name=user_tg.first_name or "",
                last_name=user_tg.last_name,
            )
            await session.flush()

            # Handle voice/audio: transcribe
            transcription = None
            if has_voice or has_audio:
                await msg.reply_text("🎙️ Transcribiendo tu audio...")
                file_obj = msg.voice or msg.audio
                file = await context.bot.get_file(file_obj.file_id)
                audio_bytes = await file.download_as_bytearray()
                transcription = await whisper_svc.transcribe_audio(
                    bytes(audio_bytes),
                    filename=f"voice_{chat_id}.ogg",
                )
                if transcription:
                    text = transcription
                    await msg.reply_text(f"📝 Entendido: _{transcription[:200]}_", parse_mode="Markdown")
                else:
                    await msg.reply_text("❌ No pude transcribir el audio. ¿Podés escribirlo?")
                    await session.rollback()
                    return

            # Handle photo: save to MinIO, ask user if no caption
            photo_object_key = None
            if has_photo:
                # Upload to MinIO always
                try:
                    largest_photo = msg.photo[-1]
                    file = await context.bot.get_file(largest_photo.file_id)
                    photo_bytes = await file.download_as_bytearray()
                    from app.services import minio as minio_svc
                    photo_object_key = await minio_svc.upload_file(
                        user_id=str(user.id),
                        file_bytes=bytes(photo_bytes),
                        filename=f"photo_{msg.message_id}.jpg",
                        content_type="image/jpeg",
                    )
                except Exception as exc:
                    logger.exception("Photo upload failed: %s", exc)

                # No caption → analyze with AI vision, then ask user
                if not text and not has_voice and photo_object_key:
                    # Try vision analysis
                    from app.services import vision as vision_svc
                    analysis = await vision_svc.analyze_image(bytes(photo_bytes))

                    if analysis and analysis.get("suggested_action") == "guardar":
                        doc_type = analysis.get("document_type", "documento")
                        desc = analysis.get("description", "imagen")
                        await msg.reply_text(
                            f"📸 *Parece {desc}*\n\n"
                            f"¿Querés que la guarde como *{doc_type}* en tus documentos?\n"
                            f"Respondé _\"sí\"_ para guardar o decime qué es.",
                            parse_mode="Markdown",
                        )
                    elif analysis and analysis.get("suggested_action") == "ignorar":
                        await msg.reply_text(
                            f"📸 *{analysis.get('description', 'Esta imagen')}*\n\n"
                            f"No parece un documento. Si querés guardarla igual, "
                            f"decime de qué se trata.",
                            parse_mode="Markdown",
                        )
                    else:
                        # Fallback: ask generically
                        await msg.reply_text(
                            "📸 *Guardé tu imagen.*\n\n"
                            "¿De qué se trata? Por ejemplo:\n"
                            "• _\"Mi cédula de identidad\"_\n"
                            "• _\"Factura del supermaxi\"_\n"
                            "• _\"SOAT de mi carro\"_\n"
                            "• _\"Garantía de la lavadora\"_\n\n"
                            "Respondeme con una descripción y la catalogo.",
                            parse_mode="Markdown",
                        )
                    # Save raw message and return — wait for user's text response
                    db_message = await message_svc.create_message(
                        session=session, user_id=user.id,
                        channel=MessageChannel.telegram,
                        message_type=MessageType.photo,
                        text="[foto sin descripción]",
                        file_path=photo_object_key,
                    )
                    await session.commit()
                    return
            db_message = await message_svc.create_message(
                session=session,
                user_id=user.id,
                channel=MessageChannel.telegram,
                message_type=message_type,
                text=text,
                file_path=photo_object_key or f"telegram://{chat_id}/{msg.message_id}",
                transcription=transcription,
            )
            await session.flush()

            # Route intent
            content = text or "[audio/photo message]"
            # Route intent
            content = text or "[audio/photo message]"

            # If previous message was a photo without description, link this text to it
            extra_attrs = {}
            if message_type == MessageType.text and not has_photo:
                from sqlalchemy import select, desc
                from app.models.message import Message
                last_msg = await session.execute(
                    select(Message).where(
                        Message.user_id == user.id,
                        Message.message_type == MessageType.photo,
                        Message.text == "[foto sin descripción]",
                    ).order_by(desc(Message.received_at)).limit(1)
                )
                last_photo = last_msg.scalar_one_or_none()
                if last_photo and last_photo.file_path:
                    extra_attrs["photo_key"] = last_photo.file_path
                    # Update the old photo message with the new description
                    last_photo.text = text
                    logger.info("Linked text response to photo: %s", last_photo.file_path)

            routing = await router_svc.route_intent(content)
            target_table = routing.get("target_table", "note")

            # Meta: user asking about Lucho himself → contextual answer via LLM
            if target_table == "meta":
                meta_reply = await _respond_meta(content, HELP_TEXT)
                await msg.reply_text(meta_reply, parse_mode="Markdown")
                db_message.extraction_result = {
                    "routing": routing, "target_table": "meta",
                    "telegram_message_id": msg.message_id,
                }
                await session.commit()
                return

            # Extract fields
            extraction = {}
            if target_table != "search" and text:
                extraction = await extractor_svc.extract_fields(text, target_table)

            # Store extraction + telegram_message_id for dedup
            db_message.extraction_result = {
                "routing": routing,
                "target_table": target_table,
                "extraction": extraction,
                "telegram_message_id": msg.message_id,
            }
            await message_svc.update_message_status(session, db_message, MessageStatus.extracted)

            # Persist to target table
            await _persist(session, user.id, target_table, extraction, text, db_message.id, photo_object_key, extra_attrs)

            # Handle corrections — update the last entity the user created
            if target_table == "correction":
                correction_reply = await _handle_correction(session, user.id, extraction, text)
                if correction_reply:
                    await msg.reply_text(correction_reply, parse_mode="Markdown")
                await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
                await session.commit()
                return

            # Handle search queries — actually search user data
            if target_table == "search":
                search_reply = await _handle_search(session, user.id, text)
                if search_reply:
                    await msg.reply_text(search_reply, parse_mode="Markdown")
                await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
                await session.commit()
                return

            # Handle tool execution — call external API
            if target_table == "tool":
                tool_reply = await _execute_tool(extraction, user.id)
                if tool_reply:
                    await msg.reply_text(tool_reply, parse_mode="Markdown")
                await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
                await session.commit()
                return

            # Build and send confirmation
            confirmation = _build_confirmation(target_table, extraction, text)
            if confirmation:
                await msg.reply_text(confirmation, parse_mode="Markdown")

            await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
            await session.commit()

        except Exception as exc:
            logger.exception("Pipeline error for chat_id=%s: %s", chat_id, exc)
            await session.rollback()
            await msg.reply_text("❌ Tuvimos un error. ¿Podés intentar de nuevo?")


# ---- Persistence helper ----

async def _persist(session, user_id, target_table, extraction, text, source_message_id, photo_key=None, extra_attrs=None):
    """Write extracted data to the correct target table."""
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
            # Link MinIO photo key to asset attributes
            if photo_key and "minio://" not in str(photo_key):
                asset.attributes = {**asset.attributes, "photo_key": photo_key}
            if extra_attrs:
                asset.attributes = {**asset.attributes, **extra_attrs}
            return asset
        case "event":
            return await persist_svc.persist_event(
                session=session,
                user_id=user_id,
                title=extraction.get("title", text or "evento"),
                target_date=extraction.get("target_date", ""),
                description=extraction.get("description"),
                certainty=extraction.get("certainty", "certain"),
                recurrence_rule=extraction.get("recurrence_rule"),
            )
        case "list_item":
            return await persist_svc.persist_list_items(
                session=session,
                user_id=user_id,
                list_name=extraction.get("list_name", "general"),
                items=extraction.get("items", [text] if text else []),
                quantity=extraction.get("quantity"),
            )
        case "note":
            return await persist_svc.persist_note(
                session=session,
                user_id=user_id,
                topic_name=extraction.get("topic_name", "general"),
                content=extraction.get("content", text or ""),
                source_message_id=source_message_id,
            )
        case _:
            return None


# ---- Deduplication ----

async def _is_duplicate(session, chat_id: int, telegram_message_id: int) -> bool:
    """Check if a Telegram message was already processed (by message_id + chat_id)."""
    from sqlalchemy import select
    from app.models.message import Message
    from app.models.user import User

    result = await session.execute(
        select(Message.id).join(User).where(
            User.telegram_id == str(chat_id),
            Message.extraction_result.contains({"telegram_message_id": telegram_message_id}),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ---- Meta-question detection ----

HELP_TEXT = (
    "🤖 *Lucho — ¿Qué puedo hacer por vos?*\n\n"
    "Soy tu asistente personal. Me hablás sin estructura y yo organizo:\n\n"
    "🚗 *Vehículos*\n"
    "_\"Mi carro es PBC-1234\"_ → Calculo matriculación, pico y placa, SOAT\n\n"
    "📅 *Recordatorios*\n"
    "_\"Cita dentista el lunes a las 3pm\"_ → Te aviso con anticipación\n\n"
    "📝 *Listas*\n"
    "_\"Comprar leche, pan y huevos\"_ → Creo tu lista de compras\n\n"
    "💡 *Notas*\n"
    "_\"Idea de negocio: exportar rosas\"_ → Guardo tus ideas por tema\n\n"
    "💰 *Gastos compartidos*\n"
    "_\"Cena $60 entre 4 personas\"_ → Calculo cuánto toca por persona\n\n"
    "🔍 *Buscar*\n"
    "_\"¿Cuándo vence mi SOAT?\"_ → Encuentro lo que guardaste\n\n"
    "Mandame *fotos* de facturas y *notas de voz*.\n"
    "Escribime lo que necesites, sin comandos. 😊"
)


# ---- Smart search: extract params first, then search ----

# Document keywords for photo retrieval
DOCUMENT_PHOTO_KEYWORDS = [
    "pásame", "pasame", "envíame", "mándame", "mandame",
    "mostrame", "mostrame", "dame", "enseñame", "enseniame",
    "muéstrame", "muestrame", "quiero ver", "foto", "imagen",
]

async def _handle_search(session, user_id, text: str) -> str | None:
    """
    Smart search: extract search parameters from the user's question,
    then run the appropriate deterministic query.
    """
    from app.services import search as search_svc
    from app.services.extractor import extract_fields

    # 1. Extract search intent from the question
    search_params = await _extract_search_params(text)
    search_type = search_params.get("search_type", "general")

    # 2. Route to the right query based on search_type
    if search_type in ("vehicle", "vehículo", "carro", "placa", "documento", "cédula", "cedula", "pasaporte", "licencia"):
        raw = await _search_vehicles_and_documents(session, user_id)
        # If user asked for the actual file, send it
        if any(kw in text.lower() for kw in ("pásame", "pasame", "envíame", "mándame", "mandame", "dame", "mostrame", "mostrame")):
            await _send_document_photos(user_id, session, msg, context)
        return await _respond_conversationally(raw, text) if (raw and settings.CONTEXTUAL_RESPONSES) else raw

    elif search_type in ("list", "lista", "compras", "pendientes", "pending"):
        raw = await _search_pending(session, user_id)
        return await _respond_conversationally(raw, text) if (raw and settings.CONTEXTUAL_RESPONSES) else raw

    elif search_type in ("deadline", "vencimiento", "cuándo", "próximo", "fechas"):
        raw = await _search_deadlines(session, user_id)
        return await _respond_conversationally(raw, text) if (raw and settings.CONTEXTUAL_RESPONSES) else raw

    elif search_type in ("note", "nota", "idea", "tema"):
        raw = await _search_notes(session, user_id)
        return await _respond_conversationally(raw, text) if (raw and settings.CONTEXTUAL_RESPONSES) else raw

    # 3. Fallback: search everything and return best match
    return await _search_all(session, user_id, text)


async def _respond_conversationally(raw_data: str, question: str) -> str:
    """Use LLM to turn raw search results into a natural, contextual response.
    
    Falls back to raw data if:
    - CONTEXTUAL_RESPONSES feature flag is off (checked before calling)
    - LLM provider is not available
    - LLM call fails
    """
    from app.services.llm import get_llm_provider

    # For simple queries, use safe templates (no LLM, no hallucination risk)
    simple = _try_simple_template(raw_data, question)
    if simple:
        return simple

    provider = get_llm_provider()
    if not provider:
        return raw_data

    prompt = f"""Eres Lucho, un asistente personal ecuatoriano. El usuario preguntó: "{question}"

Tienes estos datos del usuario:
{raw_data}

Responde de forma NATURAL y conversacional, como si estuvieras chateando. 
- Sé breve y útil
- No repitas los datos en crudo, explícalos
- Usa emojis con moderación
- Si no hay datos relevantes, dilo honestamente
- NUNCA inventes información que no está en los datos

Respuesta:"""

    try:
        response = await provider.chat(
            system_prompt="Eres Lucho, un asistente personal cálido y eficiente. Respondes en español ecuatoriano natural.",
            user_message=prompt,
            model=provider.router_model,  # use cheap model for formatting
            max_tokens=300,
        )
        return response.strip()
    except Exception:
        return raw_data


def _try_simple_template(raw_data: str, question: str) -> str | None:
    """
    Try to answer with a safe template for common questions.
    Returns None if no template matches — caller falls back to LLM.
    
    This eliminates hallucination risk for predictable queries.
    """
    lower = question.lower()

    # Vehicle questions → deterministic template
    if any(kw in lower for kw in ("vehículo", "carro", "placa", "vehiculo")):
        if "No tenés vehículos" in raw_data or "No tenés" in raw_data:
            return "No tengo vehículos registrados. Mandame tu placa y lo guardo. 🚗"
        return raw_data  # the raw vehicle list is already well-formatted

    # Pending items → deterministic template
    if any(kw in lower for kw in ("pendiente", "compras", "comprar", "lista", "tareas")):
        if "No tenés nada pendiente" in raw_data:
            return "No tenés nada pendiente. ¡Bien ahí! ✅"
        return raw_data  # already well-formatted

    # Deadlines → deterministic template
    if any(kw in lower for kw in ("vence", "vencimiento", "fecha", "próximo", "proximo", "cuándo")):
        if "No tenés vencimientos" in raw_data:
            return "No tenés vencimientos próximos. ✅"
        return raw_data

    # Notes → deterministic template
    if any(kw in lower for kw in ("nota", "idea", "tema")):
        if "No tenés notas" in raw_data:
            return "No tenés notas guardadas. Mandame una idea y la guardo. 💡"
        return raw_data

    # No template match → let LLM handle it
    return None


async def _extract_search_params(text: str) -> dict:
    """Use the extractor to understand what the user is searching for."""
    extraction = await extractor_svc.extract_fields(text, "search")
    if not extraction:
        return {"search_type": "general"}
    return extraction


async def _search_vehicles_and_documents(session, user_id) -> str:
    """List all user vehicles AND documents with details."""
    from sqlalchemy import select
    from app.models.asset import Asset, AssetType

    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.asset_type.in_([AssetType.vehicle, AssetType.document]),
            Asset.deleted_at.is_(None),
        )
    )
    items = result.scalars().all()

    if not items:
        return "No tenés vehículos ni documentos registrados."

    lines = ["📋 *Tus vehículos y documentos:*"]
    for v in items:
        attrs = v.attributes or {}
        if v.asset_type == AssetType.vehicle:
            plate = attrs.get("plate", "Sin placa")
            brand = attrs.get("brand", "")
            model = attrs.get("model", "")
            pyp = attrs.get("pico_y_placa_days", "")
            desc = f"{brand} {model}".strip() or v.name
            lines.append(f"  🚗 *{plate}* — {desc}")
            if pyp:
                lines.append(f"    Pico y placa: {pyp}")
        elif v.asset_type == AssetType.document:
            doc_type = attrs.get("document_type", "documento")
            expiry = attrs.get("expiry_date", attrs.get("expiration_date", ""))
            has_photo = "📸" if attrs.get("photo_key") else ""
            lines.append(f"  📄 *{v.name}* ({doc_type}){has_photo}")
            if expiry:
                lines.append(f"    Vence: {expiry}")

    return "\n".join(lines)


async def _send_document_photos(user_id, session, msg, context):
    """Send actual document photos from MinIO back to the user."""
    from sqlalchemy import select
    from app.models.asset import Asset, AssetType
    from app.services import minio as minio_svc

    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.asset_type == AssetType.document,
            Asset.deleted_at.is_(None),
        )
    )
    documents = result.scalars().all()

    for doc in documents:
        attrs = doc.attributes or {}
        photo_key = attrs.get("photo_key")
        if not photo_key:
            continue

        # Download from MinIO
        photo_bytes = await minio_svc.download_file(photo_key)
        if photo_bytes:
            caption = f"📄 {doc.name}"
            expiry = attrs.get("expiry_date", attrs.get("expiration_date", ""))
            if expiry:
                caption += f"\nVence: {expiry}"
            await msg.reply_photo(
                photo=photo_bytes,
                caption=caption,
            )
            logger.info("Sent document photo: %s", doc.name)
    """List all user vehicles with details."""
    from sqlalchemy import select
    from app.models.asset import Asset, AssetType

    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.asset_type == AssetType.vehicle,
            Asset.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    if not vehicles:
        return "No tenés vehículos registrados. Mandame tu placa y lo guardo. 🚗"

    lines = ["🚗 *Tus vehículos:*"]
    for v in vehicles:
        attrs = v.attributes or {}
        plate = attrs.get("plate", "Sin placa")
        brand = attrs.get("brand", "")
        model = attrs.get("model", "")
        pyp = attrs.get("pico_y_placa_days", "")
        matric = attrs.get("next_matriculation", "")

        desc = f"{brand} {model}".strip() or v.name
        lines.append(f"  • *{plate}* — {desc}")
        if pyp:
            lines.append(f"    Pico y placa: {pyp}")
        if matric:
            lines.append(f"    Matriculación: {matric}")

    return "\n".join(lines)


async def _search_pending(session, user_id) -> str | None:
    """List pending items across all lists."""
    from app.services import search as search_svc

    pending = await search_svc.list_pending_items(session, user_id)
    if not pending:
        return "No tenés nada pendiente. ¡Bien ahí! ✅"

    lines = ["📝 *Pendientes:*"]
    for item in pending[:10]:
        lines.append(f"  • [{item['list']}] {item['content']}")
    return "\n".join(lines)


async def _search_deadlines(session, user_id) -> str | None:
    """List upcoming deadlines."""
    from app.services import search as search_svc

    deadlines = await search_svc.upcoming_deadlines(session, user_id, days_ahead=90)
    if not deadlines:
        return "No tenés vencimientos próximos. ✅"

    lines = ["📅 *Próximos vencimientos:*"]
    for d in deadlines[:8]:
        emoji = "🔴" if d["days_left"] <= 7 else "🟡" if d["days_left"] <= 30 else "🟢"
        lines.append(f"{emoji} {d['title']}: {d['target_date']} ({d['days_left']} días)")
    return "\n".join(lines)


async def _search_notes(session, user_id) -> str | None:
    """List user's note topics."""
    from sqlalchemy import select, func
    from app.models.topic import Topic, Note

    result = await session.execute(
        select(Topic.name, func.count(Note.id))
        .join(Note, Note.topic_id == Topic.id)
        .where(Topic.user_id == user_id)
        .group_by(Topic.name)
        .order_by(func.count(Note.id).desc())
    )
    topics = [(row[0], row[1]) for row in result.fetchall()]

    if not topics:
        return "No tenés notas guardadas. Mandame una idea y la guardo. 💡"

    lines = ["💡 *Tus notas por tema:*"]
    for name, count in topics:
        lines.append(f"  • {name} ({count} nota{'s' if count != 1 else ''})")
    return "\n".join(lines)


async def _search_all(session, user_id, text: str) -> str | None:
    """Fallback: search everything."""
    # Give a summary of everything the user has
    parts = []

    v = await _search_vehicles(session, user_id)
    if v and "No tenés" not in v:
        parts.append(v)

    p = await _search_pending(session, user_id)
    if p and "No tenés" not in p:
        parts.append(p)

    d = await _search_deadlines(session, user_id)
    if d and "No tenés" not in d:
        parts.append(d)

    if parts:
        return "\n\n".join(parts)

    return "Todavía no tengo nada guardado. Mandame algo y empiezo a organizar. 🚀"


# ---- Confirmation builder ----

def _build_confirmation(target_table: str, extraction: dict, original_text: str | None) -> str:
    """Build a human-readable confirmation. None-safe on all fields."""
    if not extraction:
        return ""

    match target_table:
        case "asset":
            at = extraction.get("asset_type") or "otro"
            name = extraction.get("name") or original_text or "nuevo"
            return (
                f"📋 Guardado: *{name}* ({at})\n"
                f"¿Está bien? Podés corregirme en cualquier momento."
            )
        case "event":
            title = extraction.get("title") or original_text or "evento"
            td = extraction.get("target_date") or ""
            ds = f" — {td}" if td else ""
            return f"📅 Agendado: *{title}*{ds}"
        case "list_item":
            ln = extraction.get("list_name") or "general"
            items = extraction.get("items") or []
            its = "\n".join(f"  ✓ {i}" for i in items) if items else "  ✓ (lista vacía)"
            return f"📝 Agregado a *{ln}*:\n{its}"
        case "note":
            topic = extraction.get("topic_name") or "general"
            content = extraction.get("content") or original_text or ""
            preview = content[:100] + "..." if len(content) > 100 else content
            return f"💡 Nota en *{topic}*:\n{preview}"
        case "shared_expense":
            desc = extraction.get("description") or original_text or "gasto"
            amt = extraction.get("amount") or 0
            parts = extraction.get("participants") or []
            pp = amt / len(parts) if parts else amt
            return f"💰 *{desc}*\n${amt:.2f} ÷ {len(parts)} = ${pp:.2f} c/u"
        case _:
            return ""


# ---- Correction handler ----

async def _handle_correction(session, user_id, extraction: dict, text: str) -> str | None:
    """
    Handle user corrections. Updates the last entity the user interacted with.
    Example: "no, la cita es el 20" → updates the last event's date.
    """
    if not extraction:
        return "No entendí bien qué querés corregir. ¿Podés ser más específico?"

    original = extraction.get("original_target", "")
    corrected = extraction.get("corrected_fields", {})

    if not corrected:
        return "No detecté qué campos corregir. Decime qué dato querés cambiar."

    # Find the user's most recent entity (check events, notes, lists, assets)
    from sqlalchemy import select, desc
    from app.models.event import Event
    from app.models.topic import Note
    from app.models.list import ListItem
    from app.models.asset import Asset

    updated = []

    # Try last event
    result = await session.execute(
        select(Event).where(Event.user_id == user_id).order_by(desc(Event.created_at)).limit(1)
    )
    event = result.scalar_one_or_none()
    if event:
        for field, value in corrected.items():
            if hasattr(event, field):
                old = getattr(event, field)
                setattr(event, field, value)
                updated.append(f"{field}: {old} → {value}")
        if updated:
            return f"✅ Corregido en *{event.title}*:\n" + "\n".join(f"  • {u}" for u in updated)

    # Try last note
    result = await session.execute(
        select(Note).join(Note.topic).where(Note.topic.has(user_id=user_id)).order_by(desc(Note.created_at)).limit(1)
    )
    note = result.scalar_one_or_none()
    if note and "content" in corrected:
        old = note.content[:50]
        note.content = corrected["content"]
        return f"✅ Nota actualizada:\n  • contenido: _{old}..._ → _{corrected['content'][:50]}..._"

    return "No encontré algo reciente para corregir. ¿Querés ser más específico sobre qué dato modificar?"


# ---- Tool execution ----

async def _respond_meta(question: str, help_text: str) -> str:
    """
    Generate a contextual, natural response to a meta question.
    """
    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    if not provider:
        return help_text

    prompt = f"""El usuario preguntó: "{question}"

Eres Lucho, un asistente personal ecuatoriano por WhatsApp/Telegram. Tus capacidades reales:
{help_text}

Responde de forma NATURAL, conversacional y BREVE (máximo 4 líneas). 
- Contestá ESPECÍFICAMENTE lo que el usuario preguntó
- No repitas toda la lista de capacidades
- Usá un tono cálido y ecuatoriano
- Si preguntan si podés hacer algo que SÍ podés, contestá que sí y cómo
- Si preguntan si podés hacer algo que NO podés, sé honesto y ofrecé alternativas

Respuesta:"""

    try:
        response = await provider.chat(
            system_prompt="Eres Lucho, un asistente personal ecuatoriano cálido, útil y conversacional. Respondés en español natural, como si chatearas con un amigo.",
            user_message=prompt,
            model=provider.router_model,
            max_tokens=250,
        )
        return response.strip()
    except Exception:
        return help_text


# ---- Tool execution ----

async def _execute_tool(extraction: dict, user_id) -> str | None:
    """Execute a registered tool with extracted parameters. Auto-retries once."""
    from app.tools import get_tool, list_tools

    tool_name = extraction.get("tool_name", "")
    params = extraction.get("params", {})

    if not tool_name:
        return "No entendí qué querés consultar. ¿Podés ser más específico?"

    tool = get_tool(tool_name)
    if not tool:
        return (
            f"La herramienta *{tool_name}* no está disponible todavía.\n"
            f"Por ahora puedo consultar: {', '.join(list_tools())}."
        )

    logger.info("Executing tool: %s with params: %s", tool_name, params)
    result = await tool.execute(params, user_id=str(user_id))

    # Auto-retry once on failure
    if not result.success:
        logger.warning("Tool %s failed, retrying...", tool_name)
        import asyncio
        await asyncio.sleep(2)
        result = await tool.execute(params, user_id=str(user_id))

    if result.success and result.rendered:
        return result.rendered
    elif result.success:
        return f"✅ Consulta a *{tool_name}* completada."
    else:
        return (
            f"❌ El servicio de *{tool_name}* no está disponible ahora.\n"
            f"¿Querés que lo intente de nuevo en un rato?"
        )


# ---- Application factory ----

def build_app() -> Application:
    """Build and configure the Telegram bot application."""
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Messages (text, photo, voice, audio)
    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO,
            handle_message,
        )
    )

    return app


async def main():
    """Entry point: start the bot with polling."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather "
            "and add the token to .env"
        )
        return

    logger.info("Starting Lucho bot in polling mode...")
    app = build_app()

    # Start polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("✅ Bot is running. Press Ctrl+C to stop.")
    logger.info("   Open Telegram and send a message to your bot!")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
