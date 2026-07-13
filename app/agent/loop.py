"""
Lucho Agent Loop — the core orchestrator.

This is the ONLY place where Lucho "thinks". The flow:

1. User sends message
2. LLM receives: system_prompt (Lucho's soul) + user message + tools
3. LLM decides:
   a. Respond directly (conversation, out-of-scope) → return text
   b. Call tool(s) → execute them → send results back → LLM crafts final response
4. Return natural-language response to user

Key design:
- ONE LLM with full context (not fragmented router+extractor)
- Tools are the ONLY way to interact with data
- No hardcoded templates — the LLM generates ALL responses
- Multi-tenant: user_id is passed to every tool call
- The LLM NEVER decides business rules — tools do (deterministic Python)
"""

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.lucho_system_prompt import build_system_prompt
from app.agent.skills import load_skills_for_message
from app.agent.tools import ALL_TOOLS, execute_tool
from app.models.message import Message
from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)

# Maximum tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 3


async def process_message(
    session: AsyncSession,
    user_id: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Process a user message through the Lucho agent.

    Args:
        session: SQLAlchemy async session (one per conversation)
        user_id: UUID string of the user
        user_message: Raw text from the user

    Returns:
        Dict with 'text' (str) and optional 'photos' (list of photo info dicts).
        Photos dicts: {'photo_key': str, 'filename': str, 'caption': str}
    """
    provider = get_llm_provider()
    if not provider:
        return {"text": "Estoy teniendo problemas para pensar. ¿Intentamos en un momento?", "photos": []}

    # Load recent conversation history (last 5 exchanges) for context
    history = await _load_conversation_history(session, user_id)

    # Load Ecuadorian domain skills relevant to this message
    skills_context = load_skills_for_message(user_message)

    # Build the conversation with system prompt + skills
    system_prompt = build_system_prompt()
    model = provider.router_model  # Use the configured model

    logger.info(
        "Agent processing message from user %s (history: %d msgs): %s",
        user_id[:8],
        len(history),
        user_message[:120],
    )

    try:
        return await _agent_loop(
            provider=provider,
            session=session,
            user_id=user_id,
            system_prompt=system_prompt,
            user_message=user_message,
            skills_context=skills_context,
            history=history,
            model=model,
        )
    except Exception as exc:
        logger.exception("Agent loop failed for user %s: %s", user_id[:8], exc)
        return {"text": "Tuve un problema procesando tu mensaje. ¿Lo intentamos de nuevo?", "photos": []}


async def _load_conversation_history(session: AsyncSession, user_id: str, limit: int = 6) -> list[dict[str, Any]]:
    """
    Load the last N messages for a user to provide conversation context.
    Returns a list of {"role": "user"|"assistant", "content": "..."} dicts.
    """
    try:
        uid = uuid.UUID(user_id)
        result = await session.execute(
            select(Message)
            .where(Message.user_id == uid)
            .order_by(desc(Message.received_at))
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # chronological order

        history = []
        for msg in messages:
            if msg.text and msg.text != "[foto sin descripción]":
                history.append({"role": "user", "content": msg.text})
            if msg.extraction_result and isinstance(msg.extraction_result, dict):
                agent_reply = msg.extraction_result.get("agent_response", "")
                if agent_reply:
                    history.append({"role": "assistant", "content": agent_reply})
        return history
    except Exception as exc:
        logger.warning("Failed to load conversation history: %s", exc)
        return []


async def _agent_loop(
    provider: Any,
    session: AsyncSession,
    user_id: str,
    system_prompt: str,
    user_message: str,
    skills_context: str,
    history: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """
    Internal agent loop with tool calling.

    Sends message → gets response → if tool call: execute → repeat → final text.
    Returns {"text": str, "photos": list[dict]}.
    """
    # Build the message history
    # Order: system prompt → skills context → conversation history → current message
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    if skills_context:
        messages.append({"role": "user", "content": skills_context})
    # Inject recent conversation for context (last N exchanges)
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    tool_rounds = 0
    photos_to_send: list[dict[str, str]] = []  # accumulate photo send requests

    while tool_rounds < MAX_TOOL_ROUNDS:
        tool_rounds += 1

        # ---- Call the LLM ----
        try:
            response = await provider.chat_with_tools(
                messages=messages,
                tools=ALL_TOOLS,
                model=model,
                max_tokens=500,
            )
        except Exception as exc:
            logger.exception("LLM call failed in agent loop: %s", exc)
            return {"text": "Se me fue la señal un momento. ¿Me repetís?", "photos": photos_to_send}

        # ---- LLM responded with plain text (no tool call) ----
        if response.get("type") == "text":
            return {"text": response["content"], "photos": photos_to_send}

        # ---- LLM requested tool call(s) ----
        if response.get("type") == "tool_calls":
            tool_calls = response.get("tool_calls", [])

            # Add the assistant's tool_call request to history
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            })

            # Execute each tool and add results
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_call_id = tc["id"]

                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                # Execute the tool
                tool_result = await execute_tool(session, user_id, tool_name, tool_args)

                # If tool requested photo send, collect it
                if tool_result.get("_action") == "send_photo":
                    photos_to_send.append({
                        "photo_key": tool_result["photo_key"],
                        "filename": tool_result.get("filename", "file"),
                        "caption": tool_result.get("caption", ""),
                    })

                # Add tool result to message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

                logger.info(
                    "Tool '%s' executed: success=%s",
                    tool_name,
                    tool_result.get("success"),
                )

            # Loop back — LLM will now see the tool results and generate final response
            continue

    # Should not reach here (max rounds exceeded)
    logger.warning(
        "Agent loop max rounds (%d) exceeded for user %s",
        MAX_TOOL_ROUNDS,
        user_id[:8],
    )
    return {"text": "Me enredé un poco. ¿Podemos empezar de nuevo?", "photos": photos_to_send}
