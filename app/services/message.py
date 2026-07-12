"""Message service — persist and track incoming messages through the pipeline."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageChannel, MessageType, MessageStatus

logger = logging.getLogger(__name__)


async def create_message(
    session: AsyncSession,
    user_id: uuid.UUID,
    channel: MessageChannel,
    message_type: MessageType,
    text: str | None = None,
    file_path: str | None = None,
    transcription: str | None = None,
) -> Message:
    """Create a new message record with status 'received'."""
    message = Message(
        user_id=user_id,
        channel=channel,
        message_type=message_type,
        text=text,
        file_path=file_path,
        transcription=transcription,
        status=MessageStatus.received,
        received_at=datetime.now(timezone.utc),
    )
    session.add(message)
    logger.info(
        "Created message id=%s type=%s channel=%s",
        message.id,
        message_type.value,
        channel.value,
    )
    return message


async def update_message_status(
    session: AsyncSession,
    message: Message,
    status: MessageStatus,
) -> None:
    """Update message status and corresponding timestamp."""
    message.status = status

    now = datetime.now(timezone.utc)
    match status:
        case MessageStatus.acked:
            message.acked_at = now
        case MessageStatus.extracted:
            message.extracted_at = now
        case MessageStatus.confirmed:
            message.confirmed_at = now
        case MessageStatus.persisted:
            message.persisted_at = now

    await session.flush()
    logger.debug("Message %s status → %s", message.id, status.value)
