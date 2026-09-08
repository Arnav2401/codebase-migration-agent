from unittest.mock import MagicMock, patch

import pytest

from pmigrate.agent.model_client import (
    GeminiModelClient,
    GroqModelClient,
    ModelEmptyResponseError,
    NvidiaModelClient,
)


def _response(status_code: int = 200, headers: dict | None = None, **json_body) -> MagicMock:  # type: ignore[no-untyped-def]
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
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
        pytest.raises(ModelEmptyResponseError),
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


def test_gemini_retries_a_transient_5xx_and_succeeds() -> None:
    # docs/decisions.md D54: the exact real shape observed live -- a 503 Service
    # Unavailable with no quota implication at all, distinct from a 429.
    body = {
        "candidates": [{"content": {"parts": [{"text": "OK"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1},
    }
    responses = [_response(503), _response(**body)]
    client = GeminiModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
    ):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    mock_sleep.assert_called_once_with(GeminiModelClient._RETRY_DELAY_S)


def test_gemini_does_not_retry_a_429_quota_error() -> None:
    # docs/decisions.md D48: Gemini's free-tier 429 is a persistent daily-quota wall, not
    # a transient burst -- retrying it wastes time instead of fixing anything, so this
    # must raise on the FIRST attempt, unlike the 503 case above.
    responses = [_response(429)]
    client = GeminiModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses) as mock_post,
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
        pytest.raises(Exception, match="HTTP 429"),
    ):
        client.complete(system="sys", prompt="prompt")

    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()


def test_gemini_gives_up_after_max_retries_on_persistent_5xx() -> None:
    responses = [_response(503) for _ in range(10)]  # more than _MAX_RETRIES + 1
    client = GeminiModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep"),
        pytest.raises(Exception, match="HTTP 503"),
    ):
        client.complete(system="sys", prompt="prompt")


def test_groq_complete_returns_text_and_cost_from_real_response_shape() -> None:
    # the exact shape returned by a real chat/completions call (verified live against
    # openai/gpt-oss-120b before wiring this in — docs/decisions.md D48)
    body = {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }
    client = GroqModelClient(api_key="test-key")
    with patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    assert result.tokens_in == 7
    assert result.tokens_out == 2
    assert result.usd_cost == pytest.approx(7 * 0.15e-6 + 2 * 0.60e-6)


def test_groq_complete_raises_on_empty_response() -> None:
    body = {
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 10},
    }
    client = GroqModelClient(api_key="test-key", max_output_tokens=10)
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(ModelEmptyResponseError),
    ):
        client.complete(system="sys", prompt="prompt")


def test_groq_complete_raises_for_model_with_no_pricing_entry() -> None:
    body = {
        "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    client = GroqModelClient(api_key="test-key", model="some-future-model")
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(ValueError, match="no pricing entry"),
    ):
        client.complete(system="sys", prompt="prompt")


def test_groq_from_env_reads_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    client = GroqModelClient.from_env()
    assert client.api_key == "env-key"


def test_groq_from_env_raises_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqModelClient.from_env()


def test_groq_retries_a_transient_429_and_succeeds() -> None:
    # docs/decisions.md D49: the exact real shape observed live — a 429 that resolves
    # within seconds, unlike Gemini's persistent daily-quota exhaustion (D48).
    ok_body = {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1},
    }
    responses = [_response(429, headers={"Retry-After": "1"}), _response(**ok_body)]
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
    ):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    mock_sleep.assert_called_once_with(1.0)  # respected the server's Retry-After


def test_groq_falls_back_to_a_short_delay_without_retry_after_header() -> None:
    ok_body = {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1},
    }
    responses = [_response(429), _response(**ok_body)]
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
    ):
        client.complete(system="sys", prompt="prompt")

    assert mock_sleep.call_count == 1
    assert mock_sleep.call_args[0][0] > 0  # some positive fallback delay


def test_groq_caps_an_oversized_retry_after_delay() -> None:
    # docs/decisions.md D53: found live -- an uncapped Retry-After turned three separate
    # 429s (across three unrelated repos) into multi-minute silent hangs, indistinguishable
    # from a real network stall from the outside. The header value here (600s) must be
    # capped, not honored verbatim.
    ok_body = {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1},
    }
    responses = [_response(429, headers={"Retry-After": "600"}), _response(**ok_body)]
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
    ):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    mock_sleep.assert_called_once_with(GroqModelClient._MAX_RETRY_DELAY_S)


def test_groq_gives_up_after_max_retries_and_raises() -> None:
    responses = [_response(429) for _ in range(10)]  # more than _MAX_RETRIES + 1
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses),
        patch("pmigrate.agent.model_client.time.sleep"),
        pytest.raises(Exception, match="HTTP 429"),
    ):
        client.complete(system="sys", prompt="prompt")


def test_groq_does_not_retry_on_a_non_429_error() -> None:
    # a real, fatal error (e.g. bad auth) must surface immediately, not be masked by retry
    responses = [_response(401)]
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=responses) as mock_post,
        patch("pmigrate.agent.model_client.time.sleep") as mock_sleep,
        pytest.raises(Exception, match="HTTP 401"),
    ):
        client.complete(system="sys", prompt="prompt")

    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()


# --- NvidiaModelClient (docs/decisions.md D76) ---------------------------------------


def test_nvidia_complete_returns_text_and_zero_cost_from_real_response_shape() -> None:
    # the exact shape returned by a real call (verified live against moonshotai/kimi-k3
    # before wiring this in). usd_cost is 0.0 because NVIDIA's build catalog is
    # free-credit development access, not per-token billing -- see D76 on why that makes
    # cost unusable as the "did repair run" tell for these arms.
    body = {
        "choices": [
            {
                "message": {"content": "ok", "reasoning_content": "thinking..."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 91, "completion_tokens": 37},
    }
    client = NvidiaModelClient(api_key="test-key")
    with patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "ok"
    assert result.tokens_in == 91
    assert result.tokens_out == 37
    assert result.usd_cost == 0.0


def test_nvidia_complete_raises_on_null_content_from_a_reasoning_model() -> None:
    """The real quirk this client exists to survive (verified live at max_tokens=16):
    kimi-k3 returns finish_reason="stop" with content explicitly NULL, having spent the
    whole budget on reasoning_content. A `.get("content", "")` default does not fire for a
    present-but-null key, so this must raise cleanly rather than pass None downstream."""
    body = {
        "choices": [
            {
                "message": {"content": None, "reasoning_content": "spent it all thinking"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 91, "completion_tokens": 37},
    }
    client = NvidiaModelClient(api_key="test-key", max_output_tokens=16)
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(ModelEmptyResponseError),
    ):
        client.complete(system="sys", prompt="prompt")


def test_nvidia_complete_raises_for_model_with_no_pricing_entry() -> None:
    body = {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    client = NvidiaModelClient(api_key="test-key", model="nvidia/not-priced")
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=_response(**body)),
        pytest.raises(ValueError, match="no pricing entry"),
    ):
        client.complete(system="sys", prompt="prompt")


def test_nvidia_from_env_reads_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "env-key")
    assert NvidiaModelClient.from_env().api_key == "env-key"


def test_nvidia_from_env_raises_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NVIDIA_API_KEY not set"):
        NvidiaModelClient.from_env()


# --- Groq reports TPM overage as 413, not 429 (docs/decisions.md D86) -----------------


def test_groq_retries_a_413_that_is_really_a_rate_limit() -> None:
    """Measured live: `413 Payload Too Large` with code `rate_limit_exceeded` and the
    message `on tokens per minute (TPM): Limit 8000, Requested 8162`. D75 read the HTTP
    status literally and built a size cap for what is actually a pacing problem; treating
    it as fatal threw away half of one run's repair attempts."""
    limited = _response(
        status_code=413,
        error={"code": "rate_limit_exceeded", "message": "tokens per minute (TPM): Limit 8000"},
    )
    ok = _response(
        choices=[{"message": {"content": "OK"}, "finish_reason": "stop"}],
        usage={"prompt_tokens": 1, "completion_tokens": 1},
    )
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", side_effect=[limited, ok]) as post,
        patch("pmigrate.agent.model_client.time.sleep"),
    ):
        result = client.complete(system="sys", prompt="prompt")

    assert result.text == "OK"
    assert post.call_count == 2


def test_groq_does_not_retry_a_genuine_413() -> None:
    """A real oversize request is refused earlier by `target_exceeds_budget`; if one still
    reaches the API it must fail fast rather than burn the retry budget."""
    oversize = _response(status_code=413, error={"code": "request_too_large"})
    oversize.raise_for_status.side_effect = RuntimeError("HTTP 413")
    client = GroqModelClient(api_key="test-key")
    with (
        patch("pmigrate.agent.model_client.requests.post", return_value=oversize) as post,
        patch("pmigrate.agent.model_client.time.sleep"),
        pytest.raises(RuntimeError, match="413"),
    ):
        client.complete(system="sys", prompt="prompt")

    assert post.call_count == 1
