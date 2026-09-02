from unittest.mock import MagicMock, patch

import pytest
import requests

from pmigrate.corpus.github_client import GitHubClient, GitHubRateLimited


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    return resp


def test_get_retries_after_a_transient_connection_error() -> None:
    # the exact real failure (docs/decisions.md): a multi-page discovery run crashed
    # outright on a plain ConnectionResetError mid-run, even though the very next attempt,
    # seconds later, succeeded — nothing caught the transport-level exception before this.
    client = GitHubClient(token="x")
    ok = _ok_response()
    with (
        patch.object(
            client.session, "get", side_effect=[requests.ConnectionError("reset by peer"), ok]
        ) as mock_get,
        patch("pmigrate.corpus.github_client.time.sleep") as mock_sleep,
    ):
        resp = client._get("https://api.github.com/x")

    assert resp is ok
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


def test_get_reraises_after_exhausting_retries_on_persistent_connection_error() -> None:
    client = GitHubClient(token="x")
    with (
        patch.object(client.session, "get", side_effect=requests.ConnectionError("still down")),
        patch("pmigrate.corpus.github_client.time.sleep"),
        pytest.raises(requests.ConnectionError),
    ):
        client._get("https://api.github.com/x")


def test_get_still_handles_rate_limit_after_the_connection_error_path() -> None:
    # the new transport-level except must not swallow or interfere with the existing
    # status-code-based rate-limit handling below it.
    client = GitHubClient(token="x")
    rate_limited = MagicMock()
    rate_limited.status_code = 403
    rate_limited.text = "API rate limit exceeded"
    rate_limited.headers = {}
    ok = _ok_response()
    with (
        patch.object(
            client.session,
            "get",
            side_effect=[requests.ConnectionError("reset"), rate_limited, ok],
        ),
        patch("pmigrate.corpus.github_client.time.sleep"),
        patch("pmigrate.corpus.github_client.time.time", return_value=1000.0),
    ):
        resp = client._get("https://api.github.com/x")

    assert resp is ok


def test_get_raises_rate_limited_when_wait_exceeds_max_wait_s() -> None:
    client = GitHubClient(token="x", max_wait_s=10)
    rate_limited = MagicMock()
    rate_limited.status_code = 403
    rate_limited.text = "API rate limit exceeded"
    rate_limited.headers = {"X-RateLimit-Reset": "2000"}
    with (
        patch.object(client.session, "get", return_value=rate_limited),
        patch("pmigrate.corpus.github_client.time.time", return_value=1000.0),
        pytest.raises(GitHubRateLimited),
    ):
        client._get("https://api.github.com/x")
