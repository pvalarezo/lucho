"""DeepSeek LLM provider implementation (OpenAI-compatible API).

Supports:
- Standard chat completions
- Function calling / tool use (for the Lucho agent)
"""

import json
import logging
from typing import Any

import httpx

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    """LLM provider backed by DeepSeek models (OpenAI-compatible API)."""

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

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
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """
        Chat completion with function calling (tool use).

        Args:
            messages: Full message history including system, user, assistant, tool roles.
            tools: Tool schemas in OpenAI function-calling format.
            model: Model to use.
            max_tokens: Maximum response tokens.

        Returns:
            Dict with either:
            - {"type": "text", "content": "response text"}
            - {"type": "tool_calls", "tool_calls": [...]}
        """
        async with httpx.AsyncClient(timeout=45) as client:
            payload: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "messages": messages,
                "tools": tools,
            }

            logger.debug(
                "chat_with_tools: %d messages, %d tools → %s",
                len(messages),
                len(tools),
                model,
            )

            response = await client.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice.get("message", {})

            # ---- LLM wants to call tool(s) ----
            tool_calls = message.get("tool_calls")
            if tool_calls:
                logger.info("LLM requested %d tool call(s)", len(tool_calls))
                return {
                    "type": "tool_calls",
                    "tool_calls": tool_calls,
                }

            # ---- LLM responded with text ----
            content = message.get("content") or ""
            finish_reason = choice.get("finish_reason", "")

            logger.info(
                "LLM responded with text (%d chars, finish=%s)",
                len(content),
                finish_reason,
            )
            return {
                "type": "text",
                "content": content.strip(),
                "finish_reason": finish_reason,
            }
