"""Telegram Bot API client — send messages, download files."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def send_message(chat_id: int, text: str) -> dict | None:
    """Send a text message to a Telegram chat."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping send_message")
        return None

    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("Sent message to chat_id=%s", chat_id)
            return data
        except httpx.HTTPError as exc:
            logger.error("Failed to send Telegram message: %s", exc)
            return None


async def send_typing(chat_id: int) -> None:
    """Show 'typing...' indicator in Telegram chat. Non-blocking, best-effort."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    url = f"{BASE_URL}/sendChatAction"
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(url, json={"chat_id": chat_id, "action": "typing"})
        except httpx.HTTPError:
            pass  # best-effort, never fail on typing indicator


async def send_photo(
    chat_id: int,
    photo_bytes: bytes,
    caption: str | None = None,
    filename: str = "photo.jpg",
) -> dict | None:
    """
    Send a photo or document to a Telegram chat.
    Automatically detects if it's an image (sendPhoto, inline preview)
    or a document (sendDocument, downloadable attachment) by MIME type.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping send_photo")
        return None

    # Detect file type from extension
    is_image = filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
    is_document = not is_image

    if is_image:
        # sendPhoto: inline preview
        url = f"{BASE_URL}/sendPhoto"
        files = {"photo": (filename, photo_bytes)}
    else:
        # sendDocument: downloadable file
        url = f"{BASE_URL}/sendDocument"
        files = {"document": (filename, photo_bytes)}

    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]  # Telegram caption limit

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
            result = response.json()
            logger.info("Sent %s to chat_id=%s: %s", "photo" if is_image else "document", chat_id, filename)
            return result
        except httpx.HTTPError as exc:
            logger.error("Failed to send %s to %s: %s", "photo" if is_image else "document", chat_id, exc)
            return None


async def set_webhook(url: str, drop_pending_updates: bool = True) -> dict | None:
    """
    Set the Telegram bot webhook URL.

    After calling this, Telegram will push updates to this URL instead of
    requiring polling. The URL must be HTTPS (self-signed not allowed).

    Args:
        url: Public HTTPS URL for the webhook (e.g. https://lucho-dev.apx5.com/telegram/webhook)
        drop_pending_updates: Discard updates that arrived while no webhook was set
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping set_webhook")
        return None

    webhook_url = f"{BASE_URL}/setWebhook"
    payload = {"url": url}
    if drop_pending_updates:
        payload["drop_pending_updates"] = True

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                logger.info("Telegram webhook set to: %s", url)
            else:
                logger.error("Telegram webhook setup failed: %s", data)
            return data
        except httpx.HTTPError as exc:
            logger.error("Failed to set Telegram webhook: %s", exc)
            return None


async def get_webhook_info() -> dict | None:
    """Get current webhook configuration from Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return None

    url = f"{BASE_URL}/getWebhookInfo"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to get webhook info: %s", exc)
            return None


async def delete_webhook(drop_pending_updates: bool = False) -> dict | None:
    """Delete the webhook and return to polling mode."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return None

    url = f"{BASE_URL}/deleteWebhook"
    payload = {}
    if drop_pending_updates:
        payload["drop_pending_updates"] = True

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("Telegram webhook deleted")
            return data
        except httpx.HTTPError as exc:
            logger.error("Failed to delete Telegram webhook: %s", exc)
            return None


async def download_file(file_id: str) -> bytes | None:
    """Download a file (photo, audio, voice) from Telegram servers."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping download_file")
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # 1. Get file path
            url = f"{BASE_URL}/getFile"
            resp = await client.post(url, json={"file_id": file_id})
            resp.raise_for_status()
            file_path = resp.json()["result"]["file_path"]

            # 2. Download file
            download_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
            resp = await client.get(download_url)
            resp.raise_for_status()
            logger.info("Downloaded file_id=%s (%d bytes)", file_id, len(resp.content))
            return resp.content

        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Failed to download Telegram file_id=%s: %s", file_id, exc)
            return None
