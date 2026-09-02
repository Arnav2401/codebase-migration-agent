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
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests


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


class GeminiEmptyResponseError(Exception):
    """Raised when Gemini returns no usable text. Reproduced live, not hypothetical: with
    too small a `max_output_tokens`, the model spends its entire budget on internal
    'thinking' tokens and returns `content: {}` with `finishReason: "MAX_TOKENS"` — a
    real response, HTTP 200, just with nothing usable in it. Returning `text=""` here
    instead of raising would let `agent/graph.py`'s repair() proceed to build a diff out
    of nothing; better to fail loud at the seam than corrupt a repair attempt silently."""


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
            raise GeminiEmptyResponseError(
                f"Gemini returned no usable text (finishReason={finish_reason!r}, "
                f"thoughts_tokens={usage.get('thoughtsTokenCount', 0)}) — "
                f"max_output_tokens={self.max_output_tokens} was likely consumed entirely "
                "by thinking before any visible output; raise max_output_tokens."
            )

        return ModelResponse(
            text=text, usd_cost=usd_cost, tokens_in=tokens_in, tokens_out=tokens_out
        )
