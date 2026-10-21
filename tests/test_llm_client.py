"""
Tests for Ollama LLM Client (src/generation/llm_client.py).
Validates X-LLM-Token header handling, message.content extraction (ignoring thinking),
and security redaction of URLs, tokens, and headers.
Does NOT import or read .env.
"""

import json
import pytest
import httpx
from src.generation.llm_client import OllamaClient, complete_json


def test_token_header_sent_when_token_is_set(monkeypatch):
    """Checks that X-LLM-Token header is sent when OLLAMA_API_TOKEN is set, and thinking is ignored."""
    test_token = "secret_verification_token_789xyz"
    monkeypatch.setenv("OLLAMA_API_TOKEN", test_token)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://fake-ollama-host:11434")

    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        response_data = {
            "model": "gpt-oss:20b",
            "message": {
                "role": "assistant",
                "content": '{"bar_dia_mm": 16, "bar_count": 4}',
                "thinking": "Internal reasoning process that must be ignored.",
            },
            "done": True,
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as fake_http_client:
        client = OllamaClient(client=fake_http_client)
        result = client.generate("test prompt")

    # 1. Assert header was sent
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert "x-llm-token" in req.headers
    assert req.headers["x-llm-token"] == test_token

    # 2. Assert answer is strictly from message.content (thinking field ignored)
    assert result == '{"bar_dia_mm": 16, "bar_count": 4}'
    assert "Internal reasoning" not in result


def test_token_header_absent_when_token_is_not_set(monkeypatch):
    """Checks that X-LLM-Token header is completely absent when OLLAMA_API_TOKEN is not set."""
    monkeypatch.delenv("OLLAMA_API_TOKEN", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://fake-ollama-host:11434")

    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        response_data = {
            "model": "gpt-oss:20b",
            "message": {
                "role": "assistant",
                "content": "output without token",
            },
            "done": True,
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as fake_http_client:
        client = OllamaClient(client=fake_http_client)
        result = client.generate("test prompt")

    # Assert header was NOT sent
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert "x-llm-token" not in req.headers
    assert result == "output without token"


def test_error_never_logs_or_exposes_url_token_or_headers(monkeypatch):
    """Checks that error messages never leak the URL, token, or any headers."""
    secret_token = "ultra_sensitive_token_999"
    sensitive_url = "https://sensitive-endpoint.example.com"
    monkeypatch.setenv("OLLAMA_API_TOKEN", secret_token)
    monkeypatch.setenv("OLLAMA_BASE_URL", sensitive_url)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway Error from proxy")

    transport = httpx.MockTransport(failing_handler)
    with httpx.Client(transport=transport) as fake_http_client:
        client = OllamaClient(client=fake_http_client)
        with pytest.raises(RuntimeError) as exc_info:
            client.generate("test prompt")

    error_msg = str(exc_info.value)
    # Critical security checks: zero leakage in error
    assert secret_token not in error_msg
    assert sensitive_url not in error_msg
    assert "X-LLM-Token" not in error_msg
    assert "Authorization" not in error_msg


def test_complete_json_returns_content():
    """Checks that complete_json sends format='json', temperature=0, and returns message.content."""
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        response_data = {
            "model": "gpt-oss:20b",
            "message": {
                "role": "assistant",
                "content": '{"bar_dia_mm": 16, "bar_count": 4}',
                "thinking": "Reasoning steps here that should be ignored.",
            },
            "done": True,
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as fake_http_client:
        content = complete_json(
            system="Return only JSON.",
            user="Return JSON with keys bar_dia_mm and bar_count for 4 bars of 16 mm.",
            client=fake_http_client,
        )

    assert content == '{"bar_dia_mm": 16, "bar_count": 4}'
    assert len(captured_requests) == 1
    req = captured_requests[0]
    payload = json.loads(req.content)
    assert payload["format"] == "json"
    assert payload["options"]["temperature"] == 0.0
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "Return only JSON."
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "Return JSON with keys bar_dia_mm and bar_count for 4 bars of 16 mm."


def test_non_secret_response_facts_tracked(monkeypatch):
    """Checks that Ollama client keeps done_reason, eval_count, prompt_eval_count, and thinking_present (bool)."""
    monkeypatch.setenv("OLLAMA_API_TOKEN", "token_test_123")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://fake-test-host:11434")

    def mock_handler_with_thinking(request: httpx.Request) -> httpx.Response:
        response_data = {
            "model": "gpt-oss:20b",
            "message": {
                "role": "assistant",
                "content": '{"ok": true}',
                "thinking": "Deep secret internal thoughts.",
            },
            "done_reason": "stop",
            "done": True,
            "eval_count": 120,
            "prompt_eval_count": 35,
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(mock_handler_with_thinking)
    with httpx.Client(transport=transport) as fake_http_client:
        client = OllamaClient(client=fake_http_client)
        result = client.generate("test with thinking")

        # Check attributes
        assert client.done_reason == "stop"
        assert client.eval_count == 120
        assert client.prompt_eval_count == 35
        assert client.thinking_present is True

        # Check last_response_info dict
        info = client.last_response_info
        assert info["done_reason"] == "stop"
        assert info["eval_count"] == 120
        assert info["prompt_eval_count"] == 35
        assert info["thinking_present"] is True

        # Ensure thinking content is NEVER kept or present
        assert "Deep secret" not in str(info)
        assert "Deep secret" not in result

    def mock_handler_without_thinking(request: httpx.Request) -> httpx.Response:
        response_data = {
            "model": "gpt-oss:20b",
            "message": {
                "role": "assistant",
                "content": '{"ok": true}',
            },
            "done_reason": "length",
            "done": True,
            "eval_count": 256,
            "prompt_eval_count": 50,
        }
        return httpx.Response(200, json=response_data)

    transport2 = httpx.MockTransport(mock_handler_without_thinking)
    with httpx.Client(transport=transport2) as fake_http_client:
        client2 = OllamaClient(client=fake_http_client)
        client2.generate("test without thinking")

        assert client2.done_reason == "length"
        assert client2.eval_count == 256
        assert client2.prompt_eval_count == 50
        assert client2.thinking_present is False
        assert client2.last_response_info["thinking_present"] is False


