"""Gemini client (REST, stdlib only). It sends text and returns text: no tools, no files, no execution.

The rest of the AI layer depends on the tiny `AIClient` protocol, so tests inject a fake and never touch the network.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Protocol

DEFAULT_MODEL = "gemini-2.5-pro"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(RuntimeError):
    """Any failure of the AI step. The reviewer treats it as 'AI not executed' and keeps the deterministic result."""


class AIClient(Protocol):
    def generate(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        ...


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout: int = 180,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen  # injectable for tests

    def generate(self, system: str, user: str) -> str:
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        try:
            with self._open(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            raise AIError("Gemini HTTP {}: {}".format(e.code, e.read().decode(errors="replace")[:300]))
        except urllib.error.URLError as e:
            raise AIError("Gemini request failed: {}".format(e.reason))
        except (OSError, ValueError) as e:
            raise AIError("Gemini request failed: {}".format(e))
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise AIError("Unexpected Gemini response: {}".format(json.dumps(data)[:300]))


def client_from_env(model: Optional[str] = None) -> Optional[GeminiClient]:
    """The configured client, or None when there is no API key (the AI step is then simply skipped)."""
    key = os.environ.get("GEMINI_API_KEY")
    return GeminiClient(key, model) if key else None
