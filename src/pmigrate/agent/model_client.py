"""The seam between the migration loop and an actual LLM (docs/interfaces.md §5's T2/T3
tiers). Originally just a Protocol + a scriptable fake — no ANTHROPIC_API_KEY was available
in this environment, and guessing at a provider SDK's exact request/response shape blind
and calling it "real but unverified" would have been lower-confidence than it was worth.

`GeminiModelClient` below is the first real implementation, added once a live (Gemini, not
Anthropic — docs/decisions.md D24) key made verification possible. It talks to Google's
Generative Language API directly over HTTP (no SDK dependency) since the request/response
shape is simple enough that a provider SDK doesn't earn its keep here, matching the same
call this project already made for `corpus/github_client.py`.

FakeModelClient remains the primary way T2/repair's ROUTING logic (does the loop call the
client, handle its response, spend budget correctly) is tested — a real API call in a unit
test would violate "no network in unit tests" (CLAUDE.md) regardless of which provider is
behind it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests
import structlog

log = structlog.get_logger()


@dataclass(frozen=True)
class ModelResponse:
    text: str
    usd_cost: float
    tokens_in: int
    tokens_out: int


class ModelClient(Protocol):
    def complete(self, system: str, prompt: str) -> ModelResponse:
        """One request/response round trip. Streaming, tool-use, and retries are a real
        client's concern, not this seam's — the loop only needs the final text and what it
        cost, which is all `agent/graph.py`'s budget bookkeeping consumes."""
        ...


@dataclass
class FakeModelClient:
    """Test double: returns pre-scripted responses in order, or `default_response` if the
    script runs out. Records every prompt it was called with, so a test can assert on what
    the loop actually sent without needing a real model to send it to."""

    responses: list[ModelResponse]
    default_response: ModelResponse | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)
    _index: int = field(default=0, repr=False)

    def complete(self, system: str, prompt: str) -> ModelResponse:
        self.calls.append((system, prompt))
        if self._index < len(self.responses):
            response = self.responses[self._index]
            self._index += 1
            return response
        if self.default_response is not None:
            return self.default_response
        raise AssertionError("FakeModelClient ran out of scripted responses")


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Sourced from https://ai.google.dev/gemini-api/docs/pricing on 2026-09-01 (standard tier,
# in effect through 2026-12-31 per that page). The page's own wording is "Output price
# (including thinking tokens)" — thinking tokens are billed at the output rate, not
# separately, which is why `complete()` below folds `thoughtsTokenCount` into tokens_out
# rather than tracking it as a third bucket. A cost metric this project reports on
# (PLAN.md §7) can't silently default to $0 for a model with no entry here — see the
# ValueError below.
_GEMINI_PRICE_PER_TOKEN_USD: dict[str, dict[str, float]] = {
    "gemini-3.6-flash": {"input": 0.75e-6, "output": 3.75e-6},
}


class ModelEmptyResponseError(Exception):
    """Raised when a model returns no usable text. Reproduced live against Gemini, not
    hypothetical: with too small a `max_output_tokens`, the model spends its entire budget
    on internal 'thinking' tokens and returns `content: {}` with `finishReason:
    "MAX_TOKENS"` — a real response, HTTP 200, just with nothing usable in it. Returning
    `text=""` here instead of raising would let `agent/graph.py`'s repair() proceed to
    build a diff out of nothing; better to fail loud at the seam than corrupt a repair
    attempt silently. Shared across providers (docs/decisions.md D48 added GroqModelClient)
    rather than named after the first one that hit it — the failure mode isn't Gemini-
    specific."""


@dataclass
class GeminiModelClient:
    """Talks to Google's Generative Language API directly (docs/decisions.md D24) — not
    Anthropic's own API. Exists to let T2/repair actually run somewhere real when no
    ANTHROPIC_API_KEY is available; the loop only sees the `ModelClient` Protocol, so this
    is a drop-in, not a special case anywhere else in agent/graph.py.
    """

    api_key: str
    model: str = "gemini-3.6-flash"
    # 4096 (the original guess) turned out not to be enough headroom in practice: a
    # 321-line real file (docs/decisions.md D26) produced `repair_no_edit` — the model's
    # thinking, plus a full-file rewrite that size, didn't fit. Repair asks for the WHOLE
    # corrected file (D25), not a diff, so this budget scales with file size, not just
    # "thinking" — 32768 is generous enough for files well beyond what T2 targets in
    # practice (single-file semantic fixes) without materially changing per-call cost for
    # the common case, since cost is billed on actual tokens used, not this ceiling.
    max_output_tokens: int = 32768

    @classmethod
    def from_env(cls, model: str = "gemini-3.6-flash") -> GeminiModelClient:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set")
        return cls(api_key=key, model=model)

    def complete(self, system: str, prompt: str) -> ModelResponse:
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent"
        resp = requests.post(
            url,
            params={"key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": prompt}]}],
                # temperature=0 per PLAN.md invariant I6 ("every scored run is
                # reproducible from its trace: model id, prompt hash, corpus sha, seed,
                # temperature 0") — found missing live (docs/decisions.md D26): two
                # identical repair attempts against the same repo/failure produced
                # different results (one applied a working fix, one produced no usable
                # edit at all), which is exactly the kind of run-to-run variance I6
                # exists to eliminate for anything this project reports a number on.
                "generationConfig": {"maxOutputTokens": self.max_output_tokens, "temperature": 0},
            },
            timeout=120,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        usage = data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", 0)
        tokens_out = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)

        price = _GEMINI_PRICE_PER_TOKEN_USD.get(self.model)
        if price is None:
            raise ValueError(f"no pricing entry for model {self.model!r} — add one before using it")
        usd_cost = tokens_in * price["input"] + tokens_out * price["output"]

        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            finish_reason = candidates[0].get("finishReason") if candidates else "NO_CANDIDATES"
            raise ModelEmptyResponseError(
                f"Gemini returned no usable text (finishReason={finish_reason!r}, "
                f"thoughts_tokens={usage.get('thoughtsTokenCount', 0)}) — "
                f"max_output_tokens={self.max_output_tokens} was likely consumed entirely "
                "by thinking before any visible output; raise max_output_tokens."
            )

        return ModelResponse(
            text=text, usd_cost=usd_cost, tokens_in=tokens_in, tokens_out=tokens_out
        )


GROQ_API_BASE = "https://api.groq.com/openai/v1"

# Sourced from https://console.groq.com/docs/models on 2026-09-03 ("developer plan" tier,
# the one this project's key is actually on — confirmed live via the same key's own
# x-ratelimit-limit-requests: 1000 response header matching that page's documented
# "1K RPM" for this model exactly). Same non-negotiable-pricing-entry stance as Gemini's
# dict above: a model with no verified number here raises rather than silently reporting
# $0 or a guessed cost.
_GROQ_PRICE_PER_TOKEN_USD: dict[str, dict[str, float]] = {
    "openai/gpt-oss-120b": {"input": 0.15e-6, "output": 0.60e-6},
}


@dataclass
class GroqModelClient:
    """Talks to Groq's OpenAI-compatible chat/completions endpoint (docs/decisions.md D48)
    — a second real `ModelClient`, added once Gemini's free-tier daily quota (20
    requests/day, confirmed live to trickle-refill rather than reset cleanly) turned out
    to make iterative development impractical. Groq's `openai/gpt-oss-120b` on the same
    account's key measured 1000 req/min of headroom — orders of magnitude more usable for
    this project's actual call volume (a handful to a few dozen repair attempts per run).
    """

    api_key: str
    model: str = "openai/gpt-oss-120b"
    # mirrors GeminiModelClient's own reasoning (D26): repair asks for the WHOLE corrected
    # file, not a diff, so this needs to scale with file size, not just "thinking" budget.
    max_output_tokens: int = 32768

    # Found live (docs/decisions.md D49): unlike Gemini's persistent daily-quota 429
    # (D48 — retrying just wastes time hitting the same wall), Groq's 429 recovers within
    # seconds, and every retry observed live succeeded on the very next attempt. Real
    # corpus repos got cut short on one transient rate-limit despite the model going on to
    # make genuine progress moments later (`rohmu` needed exactly 2 calls to go from fully
    # blocked to 173/195 passing in an earlier Gemini run) — retrying belongs at this
    # client's own HTTP layer, not `agent/graph.py`'s repair(), which should keep treating
    # every OTHER failure (auth, malformed response) as the real, fatal error it is.
    _MAX_RETRIES: int = 3
    # docs/decisions.md D53: found live — an UNCAPPED `Retry-After`-driven sleep here was
    # silently masquerading as three separate "infra hangs" across three different repos
    # (opendataeditor, rohmu, madkote), each looking like a stuck network connection from
    # the outside (a live process, near-zero CPU, a stale socket) because this method logs
    # nothing before sleeping. Capping bounds the worst case to a few minutes total across
    # all retries and, more importantly, makes a real long cooldown FAIL FAST and visibly
    # (the next attempt still 429s, `complete()`'s `raise_for_status()` surfaces it,
    # `repair()` already treats that as a clean `status="failed"`) instead of hanging
    # silently for however long Groq's header actually says.
    _MAX_RETRY_DELAY_S: float = 30.0

    @classmethod
    def from_env(cls, model: str = "openai/gpt-oss-120b") -> GroqModelClient:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY not set")
        return cls(api_key=key, model=model)

    def _post_with_retry(self, system: str, prompt: str) -> requests.Response:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            # temperature=0 for the same I6 reproducibility reason as GeminiModelClient.
            "temperature": 0,
            "max_completion_tokens": self.max_output_tokens,
        }
        for attempt in range(self._MAX_RETRIES + 1):
            resp = requests.post(
                f"{GROQ_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=120,
            )
            if resp.status_code != 429 or attempt == self._MAX_RETRIES:
                return resp
            # Groq's own Retry-After (seconds) when present; a short fixed fallback
            # otherwise — observed live 429s recovered within a few seconds, not minutes.
            # Capped (D53): an uncapped header value turned three unrelated 429s into
            # multi-minute silent hangs indistinguishable from a real network stall.
            raw_delay = float(resp.headers.get("Retry-After", 2 * (attempt + 1)))
            delay = min(raw_delay, self._MAX_RETRY_DELAY_S)
            log.warning(
                "model_client.rate_limited",
                attempt=attempt,
                retry_after_s=raw_delay,
                sleeping_s=delay,
            )
            time.sleep(delay)
        return resp  # unreachable — loop always returns on its last iteration

    def complete(self, system: str, prompt: str) -> ModelResponse:
        resp = self._post_with_retry(system, prompt)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        price = _GROQ_PRICE_PER_TOKEN_USD.get(self.model)
        if price is None:
            raise ValueError(f"no pricing entry for model {self.model!r} — add one before using it")
        usd_cost = tokens_in * price["input"] + tokens_out * price["output"]

        choices = data.get("choices", [])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        if not text:
            finish_reason = choices[0].get("finish_reason") if choices else "NO_CHOICES"
            raise ModelEmptyResponseError(
                f"Groq returned no usable text (finish_reason={finish_reason!r}) — "
                f"max_output_tokens={self.max_output_tokens} was likely consumed entirely "
                "by reasoning before any visible output; raise max_output_tokens."
            )

        return ModelResponse(
            text=text, usd_cost=usd_cost, tokens_in=tokens_in, tokens_out=tokens_out
        )
