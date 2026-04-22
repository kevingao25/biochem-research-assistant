import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# LLM generation is slow — give it up to 2 minutes before timing out.
OLLAMA_TIMEOUT = 120.0

# Instructs the model how to behave — separated from the user message so the
# model treats it as a persistent rule rather than part of the question.
SYSTEM_PROMPT = """You are a research assistant specialized in biochemistry and molecular biology.
Answer questions based ONLY on the paper excerpts provided. Do not use outside knowledge.

Rules:
- Cite papers using [arXiv:id] format when referencing specific findings
- If the excerpts don't contain enough information, say so clearly
- Be concise: 150-250 words maximum
- Do not fabricate information not present in the excerpts"""


class OllamaClient:
    """HTTP client for the Ollama local LLM server."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.timeout = httpx.Timeout(OLLAMA_TIMEOUT)

    async def generate(self, user_message: str, model: str, temperature: float = 0.7) -> str:
        """Send a single-turn message and return the complete generated text.

        Uses /api/chat so the system prompt is a first-class field, not text
        prepended to the prompt. This is the foundation for multi-turn later.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def generate_stream(self, user_message: str, model: str, temperature: float = 0.7) -> AsyncIterator[str]:
        """Stream generated text token-by-token. Yields text chunks as they arrive."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        chunk = json.loads(line)
                        if chunk.get("message", {}).get("content"):
                            yield chunk["message"]["content"]
                        if chunk.get("done"):
                            break
