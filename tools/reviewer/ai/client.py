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
from typing import Any, Callable, Dict, List, Optional, Protocol

DEFAULT_MODEL = "gemini-3.8-flash"   # stable Flash model with a free tier; Google retires old names for new users, override with the GEMINI_MODEL secret
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Temporary overload or server errors are retried; 404 (model retired) and 429 (no quota) are not, waiting does not fix them.
TRANSIENT_HTTP = (500, 502, 503, 504)
RETRY_DELAYS = (5, 15)   # seconds to wait before the second and the third attempt
# When these still happen after the retries, the fallback model (if one is set) answers instead. Quotas are per model, so a 429 on one
# model does not stop the other.
FALLBACK_HTTP = (429,) + TRANSIENT_HTTP


class AIError(RuntimeError):
    """Any failure of the AI step. The reviewer treats it as 'AI not executed' and keeps the deterministic result.

    `status` is the HTTP status when the failure came from the API (429, 503...), else None."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


class AIClient(Protocol):
    """What the AI layer needs from a model: a JSON answer for the review, and a plain-text answer for the chat."""
    def generate(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        """Send the system prompt and the user text, and return the model's raw JSON answer."""
        ...

    def chat(self, system: str, messages: List[Dict[str, str]]) -> str:  # pragma: no cover - protocol
        """Continue a conversation (oldest message first) and return the model's plain-text answer."""
        ...


class GeminiClient:
    """Calls the Gemini REST API with no SDK. The HTTP opener is injectable so the call can be faked."""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout: int = 180,
        opener: Optional[Callable[..., Any]] = None,
        fallback_model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.fallback_model = fallback_model or os.environ.get("GEMINI_FALLBACK_MODEL") or None
        self.model_used = self.model            # the model that answered the last request (the fallback, when it had to step in)
        self.notify: Optional[Callable[[str], None]] = None     # told what is happening while waiting (the chat shows it)
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def generate(self, system: str, user: str) -> str:
        """Ask Gemini for a JSON answer and return its text. Raises AIError on any HTTP or response problem."""
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},   # deterministic, JSON only
        }
        return self._text_of(self._post(body))

    def chat(self, system: str, messages: List[Dict[str, str]]) -> str:
        """Continue a conversation and return the answer as plain text.

        `messages` is the history so far, oldest first: [{"role": "user" or "assistant", "text": "..."}], ending with the user's turn."""
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "user" if message["role"] == "user" else "model", "parts": [{"text": message["text"]}]} for message in messages
            ],
            "generationConfig": {"temperature": 0.2},
        }
        return self._text_of(self._post(body))

    def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Send one request and return the parsed response. If the model is overloaded or out of quota even after the retries,
        the fallback model (GEMINI_FALLBACK_MODEL) is tried once."""
        try:
            response = self._post_to(self.model, body)
            self.model_used = self.model
            return response
        except AIError as error:
            if not self.fallback_model or error.status not in FALLBACK_HTTP:
                raise
        if self.notify:
            self.notify("{} is unavailable; trying {}...".format(self.model, self.fallback_model))
        response = self._post_to(self.fallback_model, body)
        self.model_used = self.fallback_model
        return response

    def _post_to(self, model: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Send one request to a model, retrying temporary overload errors, and return the parsed response."""
        request = urllib.request.Request(
            ENDPOINT.format(model=model),
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
                    if self.notify:
                        self.notify("Gemini answered {} ({}). Retrying in {}s...".format(error.code, model, delay))
                    time.sleep(delay)                 # a "high demand" spike: wait and try again
                    continue
                raise AIError("Gemini HTTP {}: {}".format(error.code, error.read().decode(errors="replace")[:300]), error.code) from error
            except urllib.error.URLError as error:
                raise AIError("Gemini request failed: {}".format(error.reason)) from error
            except (OSError, ValueError) as error:
                raise AIError("Gemini request failed: {}".format(error)) from error
        return response

    @staticmethod
    def _text_of(response: Dict[str, Any]) -> str:
        """The text of the first candidate of a response."""
        try:
            return str(response["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError) as error:
            raise AIError("Unexpected Gemini response: {}".format(json.dumps(response)[:300])) from error


def client_from_env(model: Optional[str] = None) -> Optional[GeminiClient]:
    """The configured client, or None when there is no API key (the AI step is then simply skipped)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    return GeminiClient(api_key, model) if api_key else None
