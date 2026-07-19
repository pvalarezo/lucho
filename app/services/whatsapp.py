"""WhatsApp Cloud API client — send messages, download media, verify webhooks.

Uses Meta's WhatsApp Cloud API (Graph API v22.0+).
No BSP (360dialog) needed — direct to Meta.

Architecture:
- Messages sent via POST graph.facebook.com/{version}/{phone_number_id}/messages
- Media downloaded via GET graph.facebook.com/{version}/{media_id} → retrieve URL → download
- Webhook verified via GET with hub.verify_token matching
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"


def _is_configured() -> bool:
    """Check if WhatsApp credentials are set up."""
    return bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN)


# =============================================================================
# SEND MESSAGES
# =============================================================================


async def send_message(phone: str, text: str) -> dict | None:
    """
    Send a text message to a WhatsApp user.

    Args:
        phone: Recipient phone number in international format (e.g., "593987654321")
        text: Plain text message (can include WhatsApp markdown: *bold*, _italic_)

    Returns:
        API response dict or None on failure.
    """
    if not _is_configured():
        logger.warning("WhatsApp not configured — skipping send_message to %s", phone)
        return None

    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(phone),
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info("WhatsApp message sent to %s: %s", phone, data.get("messages", [{}])[0].get("id", "?"))
            return data
        except httpx.HTTPError as exc:
            logger.error("WhatsApp send_message failed for %s: %s", phone, exc)
            if hasattr(exc, "response") and exc.response is not None:
                logger.error("WhatsApp API response: %s", exc.response.text[:500])
            return None


async def send_photo(
    phone: str,
    photo_bytes: bytes,
    caption: str | None = None,
    filename: str = "photo.jpg",
) -> dict | None:
    """
    Send a photo (image) or document to a WhatsApp user.

    WhatsApp uses the 'image' type for photos with inline preview,
    and 'document' type for PDFs and other files.

    Args:
        phone: Recipient phone number in international format
        photo_bytes: Raw bytes of the file
        caption: Optional caption text
        filename: Used to detect if it's an image or document

    Returns:
        API response dict or None on failure.
    """
    if not _is_configured():
        logger.warning("WhatsApp not configured — skipping send_photo")
        return None

    # ---- Step 1: Upload media to WhatsApp servers ----
    is_image = filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
    media_type = "image/jpeg" if is_image else "application/octet-stream"

    upload_result = await _upload_media(phone, photo_bytes, filename, media_type)
    if not upload_result:
        return None

    media_id = upload_result.get("id")
    if not media_id:
        logger.error("WhatsApp media upload succeeded but no media_id returned")
        return None

    # ---- Step 2: Send media message ----
    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    message_type = "image" if is_image else "document"
    media_payload: dict[str, Any] = {"id": media_id}
    if caption:
        media_payload["caption"] = caption[:1024]
    if not is_image:
        media_payload["filename"] = filename

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(phone),
        "type": message_type,
        message_type: media_payload,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info("WhatsApp %s sent to %s: %s", message_type, phone, filename)
            return data
        except httpx.HTTPError as exc:
            logger.error("WhatsApp send_%s failed for %s: %s", message_type, phone, exc)
            return None


async def send_template_message(phone: str, template_name: str, language_code: str = "es") -> dict | None:
    """
    Send a pre-approved message template (for proactive messages outside 24h window).

    Templates must be created and approved in Meta Business Manager first.
    Used by reminders, daily digest, and other proactive notifications.

    Args:
        phone: Recipient phone number
        template_name: Name of the approved template (e.g., "recordatorio_evento")
        language_code: Language code (default "es" for Spanish)

    Returns:
        API response dict or None on failure.
    """
    if not _is_configured():
        logger.warning("WhatsApp not configured — skipping template message")
        return None

    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(phone),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info("WhatsApp template '%s' sent to %s", template_name, phone)
            return data
        except httpx.HTTPError as exc:
            logger.error("WhatsApp template '%s' failed for %s: %s", template_name, phone, exc)
            return None


async def send_typing(phone: str) -> None:
    """
    Trigger WhatsApp 'typing...' indicator (3 dots).

    WhatsApp Cloud API doesn't have a native typing endpoint like Telegram.
    Workaround: send an invisible zero-width character that triggers
    the typing indicator without showing a visible message.
    """
    if not _is_configured():
        return

    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": str(phone),
        "type": "text",
        "text": {"body": "\u200B"},  # zero-width space — invisible, triggers typing
    }

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError:
            pass  # best-effort


async def send_reaction(phone: str, message_id: str, emoji: str = "⏳") -> dict | None:
    """
    Send a reaction emoji to a WhatsApp message.

    Used to acknowledge receipt (⏳) while Lucho processes.

    Args:
        phone: Recipient phone number
        message_id: The WhatsApp message ID to react to (wamid.xxx)
        emoji: The emoji to send (default: ⏳ hourglass)

    Returns:
        API response dict or None on failure.
    """
    if not _is_configured():
        return None

    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(phone),
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji,
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.debug("WhatsApp reaction %s sent to %s for msg %s", emoji, phone, message_id)
            return data
        except httpx.HTTPError as exc:
            logger.error("WhatsApp reaction failed: %s", exc)
            return None


# =============================================================================
# MEDIA DOWNLOAD
# =============================================================================


async def download_media(media_id: str) -> bytes | None:
    """
    Download a media file (photo, audio, voice, document) from WhatsApp servers.

    Flow:
    1. GET /{media_id} → get the download URL
    2. GET the download URL (with OAuth header) → get bytes

    Args:
        media_id: WhatsApp media ID from the webhook payload

    Returns:
        Raw file bytes or None on failure.
    """
    if not _is_configured():
        logger.warning("WhatsApp not configured — skipping media download")
        return None

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Step 1: Get media URL
            url = f"{BASE_URL}/{media_id}"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            media_data = resp.json()
            download_url = media_data.get("url")
            mime_type = media_data.get("mime_type", "unknown")

            if not download_url:
                logger.error("WhatsApp media %s: no download URL in response", media_id)
                return None

            # Step 2: Download the actual file
            resp = await client.get(download_url, headers=headers)
            resp.raise_for_status()
            logger.info(
                "WhatsApp media downloaded: %s (type=%s, %d bytes)",
                media_id,
                mime_type,
                len(resp.content),
            )
            return resp.content

        except httpx.HTTPError as exc:
            logger.error("WhatsApp media download failed for %s: %s", media_id, exc)
            return None


# =============================================================================
# WEBHOOK VERIFICATION
# =============================================================================


def verify_webhook(mode: str, token: str, challenge: str) -> tuple[bool, str | None]:
    """
    Verify WhatsApp webhook subscription.

    Meta sends a GET request with:
    - hub.mode: should be "subscribe"
    - hub.verify_token: must match WHATSAPP_VERIFY_TOKEN
    - hub.challenge: random string to echo back

    Returns:
        (is_valid, challenge_string_or_None)
    """
    if not settings.WHATSAPP_VERIFY_TOKEN:
        logger.error("WHATSAPP_VERIFY_TOKEN not configured")
        return False, None

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully")
        return True, challenge

    logger.warning("WhatsApp webhook verification failed: mode=%s, token_matches=%s",
                   mode, token == settings.WHATSAPP_VERIFY_TOKEN)
    return False, None


# =============================================================================
# INTERNAL HELPERS
# =============================================================================


async def _upload_media(
    phone: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict | None:
    """
    Upload media to WhatsApp servers (step 1 of 2 for sending media).

    POST to /{phone_number_id}/media with multipart/form-data.
    Returns {"id": "media-id-string"} on success.
    """
    url = f"{BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    # httpx multipart
    files = {
        "file": (filename, file_bytes, content_type),
        "messaging_product": (None, "whatsapp"),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=headers, files=files)
            response.raise_for_status()
            data = response.json()
            logger.info("WhatsApp media uploaded: id=%s, filename=%s", data.get("id", "?"), filename)
            return data
        except httpx.HTTPError as exc:
            logger.error("WhatsApp media upload failed: %s", exc)
            return None
