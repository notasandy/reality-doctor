"""LLM client — provider-swappable between Groq (free tier, default) and Claude.

Both clients expose the same `generate` / `stream` async surface, so the rest of
the pipeline doesn't care which provider is active. Select via
`settings.llm_provider` ("groq" | "claude"). Default is "groq" (free).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from src.core.config import settings


class GroqClient:
    """Groq async client (OpenAI-compatible). Free tier — the default."""

    def __init__(self) -> None:
        from groq import AsyncGroq

        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def stream(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.2
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content


class ClaudeClient:
    """Optional Anthropic Claude client (off by default — costs money).

    Default model Haiku 4.5 is cheap and disciplined at structured output, which
    helps against config hallucination. Enable only via llm_provider="claude"."""

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.llm_max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    async def stream(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.2
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=settings.llm_max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


def LLMClient():
    """Factory: return the client for the configured provider (default Groq, free)."""
    if settings.llm_provider == "claude":
        return ClaudeClient()
    return GroqClient()
