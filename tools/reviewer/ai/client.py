"""Gemini client (REST, standard library only). It sends text and returns text: no tools, no files, no execution.

The rest of the AI layer depends only on the tiny `AIClient` interface below, so a fake can be injected and no test needs
the network.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Protocol

DEFAULT_MODEL = "gemini-3.8-flash"   # stable Flash model with a free tier; Google retires old names for new users, override with the GEMINI_MODEL secret
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Temporary overload or server errors are retried; 404 (model retired) and 429 (no quota) are not, waiting does not fix them.
TRANSIENT_HTTP = (500, 502, 503, 504)
RETRY_DELAYS = (5, 15)   # seconds to wait before the second and the third attempt


class AIError(RuntimeError):
    """Any failure of the AI step. The reviewer treats it as 'AI not executed' and keeps the deterministic result."""


class AIClient(Protocol):
    """What the AI step needs from a model: one method, text in and text out."""
    def generate(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        """Send the system prompt and the user text, and return the model's raw text answer."""
        ...


class GeminiClient:
    """Calls the Gemini REST API with no SDK. The HTTP opener is injectable so the call can be faked."""

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
        self._open = opener or urllib.request.urlopen

    def generate(self, system: str, user: str) -> str:
        """Ask Gemini for a JSON answer and return its text. Raises AIError on any HTTP or response problem."""
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},   # deterministic, JSON only
        }
        request = urllib.request.Request(
            ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )

        response: Dict[str, Any] = {}
        # One attempt per delay, plus a last one with no delay after it (None).
        for delay in RETRY_DELAYS + (None,):
            try:
                with self._open(request, timeout=self.timeout) as http_response:
                    response = json.load(http_response)
                break
            except urllib.error.HTTPError as error:
                if error.code in TRANSIENT_HTTP and delay is not None:
                    time.sleep(delay)                 # a "high demand" spike: wait and try again
                    continue
                raise AIError("Gemini HTTP {}: {}".format(error.code, error.read().decode(errors="replace")[:300]))
            except urllib.error.URLError as error:
                raise AIError("Gemini request failed: {}".format(error.reason))
            except (OSError, ValueError) as error:
                raise AIError("Gemini request failed: {}".format(error))

        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise AIError("Unexpected Gemini response: {}".format(json.dumps(response)[:300]))


def client_from_env(model: Optional[str] = None) -> Optional[GeminiClient]:
    """The configured client, or None when there is no API key (the AI step is then simply skipped)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    return GeminiClient(api_key, model) if api_key else None
