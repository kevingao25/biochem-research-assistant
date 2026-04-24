import json
import re
from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

from src.schemas.ollama import RAGResponse


class RAGPromptBuilder:

    def __init__(self):
        self.prompts_dir = Path(__file__).parent / "prompts"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_file = self.prompts_dir / "rag_system.txt"
        if not prompt_file.exists():
            return "You are a research assistant. Answer based ONLY on the provided paper excerpts."
        return prompt_file.read_text().strip()

    def create_rag_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        prompt = f"{self.system_prompt}\n\n"
        prompt += "### Context from Papers:\n\n"
        for i, chunk in enumerate(chunks, 1):
            prompt += f"[{i}. arXiv:{chunk.get('arxiv_id', '')}]\n"
            prompt += f"{chunk.get('chunk_text', '')}\n\n"
        prompt += f"### Question:\n{query}\n\n"
        prompt += "### Answer:\nProvide a natural response and cite sources using [arXiv:id] format.\n\n"
        return prompt

    def create_structured_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return prompt + Ollama format schema for structured JSON output."""
        return {
            "prompt": self.create_rag_prompt(query, chunks),
            "format": RAGResponse.model_json_schema(),
        }


class ResponseParser:

    @staticmethod
    def parse_structured_response(response: str) -> Dict[str, Any]:
        try:
            validated = RAGResponse(**json.loads(response))
            return validated.model_dump()
        except (json.JSONDecodeError, ValidationError):
            return ResponseParser._extract_json_fallback(response)

    @staticmethod
    def _extract_json_fallback(response: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            try:
                validated = RAGResponse(**json.loads(match.group()))
                return validated.model_dump()
            except (json.JSONDecodeError, ValidationError):
                pass
        return {"answer": response, "sources": [], "confidence": "low", "citations": []}
