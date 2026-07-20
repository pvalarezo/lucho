"""Anthropic (Claude) LLM provider implementation.

Supports:
- Standard chat completions
- Function calling / tool use (for the Lucho agent)
- Translates between OpenAI-compatible tool format (used by agent loop)
  and Anthropic's native tool_use format.
"""

import json
import logging
from typing import Any

import httpx

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude models."""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int = 500,
    ) -> str:
        """Standard chat completion. Returns text response."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.BASE_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """
        Chat completion with function calling (tool use).

        Translates between OpenAI-compatible message/tool format (used by the
        agent loop) and Anthropic's native tool_use format.

        Args:
            messages: Full message history with roles: system, user, assistant, tool.
                      Assistant messages may contain 'tool_calls' array (OpenAI format).
            tools: Tool schemas in OpenAI function-calling format:
                   [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]
            model: Anthropic model to use.
            max_tokens: Maximum response tokens.

        Returns:
            Dict with either:
            - {"type": "text", "content": "response text"}
            - {"type": "tool_calls", "tool_calls": [{"id": ..., "function": {"name": ..., "arguments": "..."}}]}
        """
        # ---- Convert OpenAI-format tools → Anthropic format ----
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]

        # ---- Convert OpenAI-format messages → Anthropic format ----
        system_prompt = ""
        anthropic_messages: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []  # tool results go in next user turn

        for msg in messages:
            role = msg.get("role", "")

            if role == "system":
                system_prompt = msg.get("content", "")

            elif role == "user":
                user_content: Any = msg.get("content", "")

                # If we have pending tool results, wrap them with this user message
                if pending_tool_results:
                    if isinstance(user_content, str) and user_content:
                        # User text + tool results in one block
                        blocks: list[dict[str, Any]] = [
                            {"type": "text", "text": user_content}
                        ]
                        blocks.extend(pending_tool_results)
                        anthropic_messages.append({"role": "user", "content": blocks})
                    else:
                        # Just tool results
                        anthropic_messages.append({"role": "user", "content": pending_tool_results})
                    pending_tool_results = []
                elif user_content:
                    anthropic_messages.append({"role": "user", "content": user_content})

            elif role == "assistant":
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")

                if tool_calls:
                    # Assistant requested tools → convert to Anthropic tool_use blocks
                    blocks = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tc in tool_calls:
                        try:
                            tool_input = json.loads(tc["function"]["arguments"])
                        except (json.JSONDecodeError, KeyError):
                            tool_input = {}
                        blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": tool_input,
                        })
                    anthropic_messages.append({"role": "assistant", "content": blocks})
                elif content:
                    anthropic_messages.append({"role": "assistant", "content": content})

            elif role == "tool":
                # Tool result → collect for next user turn (Anthropic requires user message)
                tool_call_id = msg.get("tool_call_id", "")
                tool_content = msg.get("content", "")
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": tool_content,
                })

        # Flush any remaining tool results
        if pending_tool_results:
            anthropic_messages.append({"role": "user", "content": pending_tool_results})

        # ---- Call Anthropic API ----
        logger.debug(
            "Anthropic chat_with_tools: %d messages, %d tools → %s",
            len(anthropic_messages),
            len(anthropic_tools),
            model,
        )

        async with httpx.AsyncClient(timeout=60) as client:
            payload: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
            }
            if system_prompt:
                payload["system"] = system_prompt

            response = await client.post(
                self.BASE_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # ---- Parse Anthropic response → OpenAI-compatible format ----
        content_blocks = data.get("content", [])
        stop_reason = data.get("stop_reason", "")

        # Collect tool_use blocks and text blocks
        tool_uses = []
        text_parts = []

        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_uses.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"], ensure_ascii=False),
                    },
                })
            elif block.get("type") == "text":
                text_parts.append(block["text"])

        # Return in OpenAI-compatible format
        if tool_uses:
            logger.info("LLM requested %d tool call(s)", len(tool_uses))
            return {
                "type": "tool_calls",
                "tool_calls": tool_uses,
            }

        text = "\n".join(text_parts).strip()
        logger.info("LLM responded with text (%d chars, finish=%s)", len(text), stop_reason)
        return {
            "type": "text",
            "content": text,
            "finish_reason": stop_reason,
        }
