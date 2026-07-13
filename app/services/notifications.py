"""
Notification Service — unified notification channels.

Abstraction layer so reminders and alerts can be sent through
any channel without the scheduler knowing the specifics.

Channels: telegram (today), whatsapp, email, sms (future)
"""

import logging
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    email = "email"
    sms = "sms"


async def send_notification(
    user_id: str,
    contact_id: str,  # telegram_id, whatsapp_id, email, phone
    message: str,
    channel: NotificationChannel,
) -> bool:
    """
    Send a notification through the specified channel.
    Returns True if sent successfully, False otherwise.

    Args:
        user_id: UUID of the user
        contact_id: Channel-specific identifier (telegram_id, phone, email)
        message: Markdown-formatted message
        channel: Which channel to use
    """
    match channel:
        case NotificationChannel.telegram:
            return await _send_telegram(contact_id, message)
        case NotificationChannel.whatsapp:
            return await _send_whatsapp(contact_id, message)
        case NotificationChannel.email:
            return await _send_email(contact_id, message)
        case NotificationChannel.sms:
            return await _send_sms(contact_id, message)
        case _:
            logger.warning("Unknown notification channel: %s", channel)
            return False


# ---- Telegram ----

async def _send_telegram(chat_id: str, message: str) -> bool:
    """Send via Telegram Bot API."""
    from app.services import telegram as telegram_svc
    try:
        await telegram_svc.send_message(int(chat_id), message)
        return True
    except Exception as exc:
        logger.error("Telegram notification failed for %s: %s", chat_id, exc)
        return False


# ---- WhatsApp (placeholder for future) ----

async def _send_whatsapp(phone: str, message: str) -> bool:
    """Send via WhatsApp Business API (360dialog or similar). PLACEHOLDER."""
    logger.info("WhatsApp notification not yet implemented for %s", phone)
    # TODO: Integrate with WhatsApp Business API
    # await whatsapp_client.send_message(phone, message)
    return False


# ---- Email (placeholder for future) ----

async def _send_email(email: str, message: str) -> bool:
    """Send via email (SMTP or SendGrid). PLACEHOLDER."""
    logger.info("Email notification not yet implemented for %s", email)
    # TODO: Integrate with email provider
    # await email_client.send(email, subject, body)
    return False


# ---- SMS (placeholder for future) ----

async def _send_sms(phone: str, message: str) -> bool:
    """Send via SMS (Twilio or similar). PLACEHOLDER."""
    logger.info("SMS notification not yet implemented for %s", phone)
    # TODO: Integrate with SMS provider
    # await sms_client.send(phone, message)
    return False


# ---- User contact resolution ----

async def resolve_user_contact(user, preferred_channel: NotificationChannel = NotificationChannel.telegram) -> tuple[str | None, NotificationChannel]:
    """
    Resolve the best contact info for a user based on preferred channel.
    Falls back to available channels.

    Returns (contact_id, channel) or (None, channel) if no contact available.
    """
    # Try preferred channel first
    if preferred_channel == NotificationChannel.telegram and user.telegram_id:
        return user.telegram_id, NotificationChannel.telegram
    if preferred_channel == NotificationChannel.whatsapp and user.whatsapp_id:
        return user.whatsapp_id, NotificationChannel.whatsapp
    if preferred_channel == NotificationChannel.email:
        # TODO: add email field to User model
        pass
    if preferred_channel == NotificationChannel.sms and user.phone_number:
        return user.phone_number, NotificationChannel.sms

    # Fallback order: telegram → whatsapp → sms
    if user.telegram_id:
        return user.telegram_id, NotificationChannel.telegram
    if user.whatsapp_id:
        return user.whatsapp_id, NotificationChannel.whatsapp
    if user.phone_number:
        return user.phone_number, NotificationChannel.sms

    logger.warning("No contact info for user %s", user.id)
    return None, preferred_channel
