import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.config import Settings
from src.exceptions import OllamaConnectionError, OllamaException, OllamaTimeoutError
from src.services.ollama.prompts import RAGPromptBuilder, ResponseParser

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_host
        self.timeout = httpx.Timeout(float(settings.ollama_timeout))
        self.prompt_builder = RAGPromptBuilder()
        self.response_parser = ResponseParser()

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/version")
                if response.status_code == 200:
                    version = response.json().get("version", "unknown")
                    return {"status": "healthy", "message": "Ollama service is running", "version": version}
                raise OllamaException(f"Ollama returned status {response.status_code}")
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama: {e}")
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Ollama timeout: {e}")

    async def generate(self, model: str, prompt: str, **kwargs) -> dict[str, Any] | None:
        """Low-level generation via /api/generate."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False, **kwargs},
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama: {e}")
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Ollama timeout: {e}")
        except Exception as e:
            raise OllamaException(f"Ollama generation failed: {e}")

    async def generate_stream(self, model: str, prompt: str, **kwargs) -> AsyncIterator[dict[str, Any]]:
        """Low-level streaming via /api/generate."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": True, **kwargs},
                ) as response:
                    if response.status_code != 200:
                        raise OllamaException(f"Streaming failed: {response.status_code}")
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama: {e}")
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Ollama timeout: {e}")

    async def generate_rag_answer(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        model: str = "llama3.2:1b",
        use_structured_output: bool = False,
    ) -> dict[str, Any]:
        """Build prompt from chunks and generate a grounded answer."""
        try:
            if use_structured_output:
                prompt_data = self.prompt_builder.create_structured_prompt(query, chunks)
                response = await self.generate(
                    model=model, prompt=prompt_data["prompt"], temperature=0.7, format=prompt_data["format"]
                )
            else:
                prompt = self.prompt_builder.create_rag_prompt(query, chunks)
                response = await self.generate(model=model, prompt=prompt, temperature=0.7)

            if not response or "response" not in response:
                raise OllamaException("No response from Ollama")

            answer_text = response["response"]

            if use_structured_output:
                return self.response_parser.parse_structured_response(answer_text)

            seen_urls: set = set()
            sources = []
            for chunk in chunks:
                arxiv_id = chunk.get("arxiv_id", "")
                if arxiv_id:
                    clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
                    url = f"https://arxiv.org/pdf/{clean_id}.pdf"
                    if url not in seen_urls:
                        sources.append(url)
                        seen_urls.add(url)

            return {
                "answer": answer_text,
                "sources": sources,
                "confidence": "medium",
                "citations": list({c.get("arxiv_id") for c in chunks if c.get("arxiv_id")})[:5],
            }

        except OllamaException:
            raise
        except Exception as e:
            raise OllamaException(f"RAG answer generation failed: {e}")

    async def generate_rag_answer_stream(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        model: str = "llama3.2:1b",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a RAG answer token-by-token."""
        prompt = self.prompt_builder.create_rag_prompt(query, chunks)
        async for chunk in self.generate_stream(model=model, prompt=prompt, temperature=0.7):
            yield chunk
