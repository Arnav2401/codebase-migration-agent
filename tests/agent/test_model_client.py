from unittest.mock import MagicMock, patch

import pytest

from pmigrate.agent.model_client import GeminiEmptyResponseError, GeminiModelClient


def _response(status_code: int = 200, **json_body) -> MagicMock:  # type: ignore[no-untyped-def]
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def test_complete_returns_text_and_cost_from_real_response_shape() -> None:
    # the exact shape returned by a real generateContent call (verified live against
    # gemini-3.6-flash before wiring this in — docs/decisions.md D24)
    body = {
        "candidates": [
            {"content": {"parts": [{"text": "OK"}]}, "finishReason": "STOP", "index": 0}
        ],
        "usageMetadata": {
            "promptTokenCount": 7,
            "candidatesTokenCount": 2,
            "thoughtsTokenCount": 5,
            "totalTokenCount": 14,
        },
    }
    client = GeminiModelClient(api_key="test-key")
    with patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    assert result.tokens_in == 7
    assert result.tokens_out == 7  # candidates + thoughts, billed at the same rate
    assert result.usd_cost == pytest.approx(7 * 0.75e-6 + 7 * 3.75e-6)


def test_complete_raises_on_empty_response_from_thinking_only_budget() -> None:
    # the exact real failure this session hit: max_output_tokens fully consumed by
    # thinking tokens before any visible text, HTTP 200, content is just `{}`
    body = {
        "candidates": [{"content": {}, "finishReason": "MAX_TOKENS", "index": 0}],
        "usageMetadata": {"promptTokenCount": 7, "totalTokenCount": 14, "thoughtsTokenCount": 7},
    }
    client = GeminiModelClient(api_key="test-key", max_output_tokens=10)
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(GeminiEmptyResponseError),
    ):
        client.complete(system="sys", prompt="prompt")


def test_complete_raises_for_model_with_no_pricing_entry() -> None:
    body = {
        "candidates": [{"content": {"parts": [{"text": "hi"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }
    client = GeminiModelClient(api_key="test-key", model="some-future-model")
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(ValueError, match="no pricing entry"),
    ):
        client.complete(system="sys", prompt="prompt")


def test_from_env_reads_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    client = GeminiModelClient.from_env()
    assert client.api_key == "env-key"


def test_from_env_raises_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiModelClient.from_env()
