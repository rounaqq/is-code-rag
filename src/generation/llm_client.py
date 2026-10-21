"""
Ollama LLM Client for IS 456 Structural RAG.
Sends requests to Ollama API and extracts clean output strictly from message.content.
Protects sensitive URLs, tokens, and headers from being logged or exposed.
Does not import or read .env.
"""

import os
from typing import List, Dict, Any, Optional
import httpx


# Module-level store for the last response info
_last_response_info: Dict[str, Any] = {
    "done_reason": None,
    "eval_count": None,
    "prompt_eval_count": None,
    "thinking_present": False,
}


def get_last_response_info() -> Dict[str, Any]:
    """Returns non-secret metadata from the last Ollama response."""
    return dict(_last_response_info)


class OllamaClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        token: Optional[str] = None,
        client: Optional[httpx.Client] = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
        self.token = token if token is not None else os.getenv("OLLAMA_API_TOKEN")
        self.client = client
        self.timeout = timeout
        self.done_reason: Optional[str] = None
        self.eval_count: Optional[int] = None
        self.prompt_eval_count: Optional[int] = None
        self.thinking_present: bool = False
        self.last_response_info: Dict[str, Any] = {
            "done_reason": None,
            "eval_count": None,
            "prompt_eval_count": None,
            "thinking_present": False,
        }

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # If OLLAMA_API_TOKEN is set, send it as the header "X-LLM-Token"
        active_token = self.token if self.token is not None else os.getenv("OLLAMA_API_TOKEN")
        if active_token and active_token.strip():
            headers["X-LLM-Token"] = active_token.strip()
        return headers

    def chat(
        self,
        messages: List[Dict[str, str]],
        format: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        """
        Sends messages to Ollama /api/chat endpoint.
        Returns message.content only (ignores the 'thinking' field).
        Keeps non-secret response metadata: done_reason, eval_count, prompt_eval_count, thinking_present.
        Never prints or logs the URL, token, or any headers.
        """
        headers = self._get_headers()
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format:
            payload["format"] = format

        endpoint = f"{self.base_url}/api/chat"

        try:
            if self.client:
                response = self.client.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, json=payload, headers=headers)

            if response.status_code != 200:
                # Never include URL, token, or headers in error message
                raise RuntimeError(f"HTTP {response.status_code}")

            data = response.json()
            message = data.get("message", {})

            # Keep non-secret facts from response (never thinking content)
            thinking_present = bool(("thinking" in message) or ("thinking" in data))
            self.done_reason = data.get("done_reason")
            self.eval_count = data.get("eval_count")
            self.prompt_eval_count = data.get("prompt_eval_count")
            self.thinking_present = thinking_present

            self.last_response_info = {
                "done_reason": self.done_reason,
                "eval_count": self.eval_count,
                "prompt_eval_count": self.prompt_eval_count,
                "thinking_present": self.thinking_present,
            }
            global _last_response_info
            _last_response_info = dict(self.last_response_info)
            if hasattr(complete_json, "last_response_info"):
                complete_json.last_response_info = dict(self.last_response_info)

            # Read answer strictly from message.content (ignore thinking field)
            content = message.get("content", "")
            return content

        except RuntimeError:
            raise
        except httpx.TimeoutException:
            raise RuntimeError("timeout") from None
        except httpx.ConnectError:
            raise RuntimeError("connection error") from None
        except Exception as exc:
            # Mask any internal exception details that might leak URLs, tokens, or headers
            exc_name = type(exc).__name__
            raise RuntimeError(f"other: {exc_name}") from None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        format: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages=messages, format=format)

    def complete_json(self, system: str, user: str) -> str:
        return self.generate(prompt=user, system_prompt=system, format="json")


def generate(
    prompt: str,
    system_prompt: Optional[str] = None,
    format: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> str:
    return OllamaClient(client=client).generate(prompt, system_prompt=system_prompt, format=format)


def complete_json(
    system: str,
    user: str,
    client: Optional[httpx.Client] = None,
) -> str:
    """
    Completes a prompt requiring JSON output with temperature 0.
    Returns the answer text strictly from message.content.
    """
    res = generate(prompt=user, system_prompt=system, format="json", client=client)
    complete_json.last_response_info = get_last_response_info()
    return res


complete_json.last_response_info = {
    "done_reason": None,
    "eval_count": None,
    "prompt_eval_count": None,
    "thinking_present": False,
}

