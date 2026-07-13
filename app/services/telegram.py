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
        "parse_mode": "Markdown",
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
