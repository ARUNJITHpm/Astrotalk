"""In-process runtime metrics — lightweight operational counters.

The admin analytics dashboard needs numbers that Postgres/Mongo don't hold:
LLM token spend and call volume. The LLM client (chat/llm_client.py) records
every completion here; the admin module reads a snapshot.

Scope + caveats (surfaced honestly in the dashboard):
  - PROCESS-LOCAL: counters live in memory, reset on restart, and are NOT
    shared across workers. Good enough for the current single-worker deploy;
    move to Redis/StatsD when the app scales out.
  - No secrets, no user content — only aggregate counts and token totals.

Kept dependency-free and side-effect-safe: recording never raises into the
chat path (a metrics bug must never break a reply).
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import UTC, datetime

_lock = threading.Lock()
_started_at = datetime.now(UTC)

# Totals across all LLM calls.
_totals = {
    "calls": 0,          # completion calls that reached a provider (incl. mock)
    "live_calls": 0,     # calls that hit a real provider (billable)
    "mock_calls": 0,     # calls served by the canned offline reply
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}

# Per-provider and per-model breakdowns: name -> {calls, prompt, completion, total}.
_by_provider: dict[str, dict[str, int]] = defaultdict(
    lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
)
_by_model: dict[str, dict[str, int]] = defaultdict(
    lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
)


def record_llm_usage(
    provider: str,
    model: str | None,
    usage: dict | None,
    *,
    mock: bool = False,
) -> None:
    """Record one LLM completion. ``usage`` is the provider's token dict
    (``prompt_tokens`` / ``completion_tokens`` / ``total_tokens``), or None
    (mock calls, or a provider that returned no usage). Never raises."""
    try:
        prompt = int((usage or {}).get("prompt_tokens") or 0)
        completion = int((usage or {}).get("completion_tokens") or 0)
        total = int((usage or {}).get("total_tokens") or (prompt + completion))
        with _lock:
            _totals["calls"] += 1
            _totals["mock_calls" if mock else "live_calls"] += 1
            _totals["prompt_tokens"] += prompt
            _totals["completion_tokens"] += completion
            _totals["total_tokens"] += total
            for bucket, key in ((_by_provider, provider or "unknown"),
                                (_by_model, model or "—")):
                row = bucket[key]
                row["calls"] += 1
                row["prompt_tokens"] += prompt
                row["completion_tokens"] += completion
                row["total_tokens"] += total
    except Exception:  # pragma: no cover - metrics must never break the caller
        pass


def estimate_price(
    provider: str,
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
) -> tuple[float, float]:
    """Calculate the cost of the LLM call in INR and USD.

    Returns (price_inr, price_usd).
    """
    usd_rate = 84.0  # exchange rate USD to INR
    provider = (provider or "").lower()
    model = (model or "").lower()

    if provider == "openai" or "gpt" in model:
        # gpt-4o-mini pricing: $0.15/1M input, $0.60/1M output
        in_usd = (prompt_tokens * 0.15) / 1_000_000
        out_usd = (completion_tokens * 0.60) / 1_000_000
        total_usd = in_usd + out_usd
        total_inr = total_usd * usd_rate
        return round(total_inr, 6), round(total_usd, 6)
    elif provider.startswith("sarvam") or "sarvam" in model:
        # sarvam-30b: input ₹2.5/1M, output ₹10.0/1M
        # sarvam-105b: input ₹4.0/1M, output ₹16.0/1M
        if "30b" in model:
            in_inr = (prompt_tokens * 2.5) / 1_000_000
            out_inr = (completion_tokens * 10.0) / 1_000_000
        else:
            in_inr = (prompt_tokens * 4.0) / 1_000_000
            out_inr = (completion_tokens * 16.0) / 1_000_000
        total_inr = in_inr + out_inr
        total_usd = total_inr / usd_rate
        return round(total_inr, 6), round(total_usd, 6)
    return 0.0, 0.0


def snapshot() -> dict:
    """A JSON-serialisable copy of the current counters for the admin dashboard."""
    with _lock:
        by_provider_priced = {}
        for prov, data in _by_provider.items():
            price_inr, price_usd = estimate_price(prov, None, data["prompt_tokens"], data["completion_tokens"])
            by_provider_priced[prov] = {
                **data,
                "price_inr": price_inr,
                "price_usd": price_usd,
            }

        by_model_priced = {}
        for model, data in _by_model.items():
            # Guess provider from model name
            prov = "openai" if "gpt" in model.lower() else ("sarvam" if "sarvam" in model.lower() else "unknown")
            price_inr, price_usd = estimate_price(prov, model, data["prompt_tokens"], data["completion_tokens"])
            by_model_priced[model] = {
                **data,
                "price_inr": price_inr,
                "price_usd": price_usd,
            }

        totals_priced = dict(_totals)
        totals_priced["price_inr"] = sum(p["price_inr"] for p in by_provider_priced.values())
        totals_priced["price_usd"] = sum(p["price_usd"] for p in by_provider_priced.values())

        return {
            "since": _started_at.isoformat(),
            "uptime_seconds": int((datetime.now(UTC) - _started_at).total_seconds()),
            "totals": totals_priced,
            "by_provider": by_provider_priced,
            "by_model": by_model_priced,
        }
