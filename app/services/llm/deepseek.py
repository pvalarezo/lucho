"""DeepSeek LLM provider implementation (OpenAI-compatible API)."""

import logging

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
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
