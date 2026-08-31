"""Module 4: AI-augmented anomaly narratives.

Groq is the primary provider. OpenRouter's stealth/ox-alpha is used only as
an automatic fallback when the Groq request fails. The module batches all
anomalies from one polling cycle into one request, validates the model's JSON
response, and persists provider/latency/token metadata with each narrative.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import groq
import openai
from openai import OpenAI

from pipeline import config
from pipeline.src import db

log = logging.getLogger("narrative")

# Primary and fallback clients. pipeline_runner.py loads .env before importing
# this module, so both clients see the environment variables at import time.
_groq_client = groq.Groq()
_openrouter_client: OpenAI | None = None
if os.getenv("OPENROUTER_API_KEY"):
    _openrouter_client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )

OPENROUTER_MODEL = "stealth/ox-alpha"
HISTORY_WINDOW = 20
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Provider calls and retry behavior
# ---------------------------------------------------------------------------


def _call_groq_with_retry(fn, *args, **kwargs) -> Any:
    """Call Groq with retries for transient failures."""
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (groq.APIConnectionError, groq.RateLimitError) as exc:
            last_exc = exc
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "Groq API transient error (attempt %d/%d): %s; retrying in %.1fs",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
        except groq.APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                log.warning(
                    "Groq API server error %d (attempt %d/%d); retrying in %.1fs",
                    exc.status_code,
                    attempt,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                log.error("Groq API non-retryable error %d: %s", exc.status_code, exc)
                raise

    assert last_exc is not None
    raise last_exc


def _call_openrouter_with_retry(fn, *args, **kwargs) -> Any:
    """Call OpenRouter with retries for transient failures."""
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
        ) as exc:
            last_exc = exc
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "OpenRouter API transient error (attempt %d/%d): %s; retrying in %.1fs",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                log.warning(
                    "OpenRouter API server error %d (attempt %d/%d); retrying in %.1fs",
                    exc.status_code,
                    attempt,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                log.error(
                    "OpenRouter API non-retryable error %d: %s",
                    exc.status_code,
                    exc,
                )
                raise

    assert last_exc is not None
    raise last_exc


def _call_llm_with_fallback(
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[Any, str, str, bool]:
    """Call Groq first and OpenRouter only after Groq fails.

    Returns the provider response, provider name, model name, and a boolean
    indicating whether the fallback path was used.
    """
    try:
        log.info("Narrative provider: Groq primary")
        response = _call_groq_with_retry(
            _groq_client.chat.completions.create,
            model=config.NARRATIVE_MODEL,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response, "groq", config.NARRATIVE_MODEL, False
    except Exception as primary_error:
        if _openrouter_client is None:
            log.error("Groq failed and OPENROUTER_API_KEY is not configured")
            raise

        log.warning(
            "Groq narrative call failed; using OpenRouter fallback: %s",
            primary_error,
        )
        response = _call_openrouter_with_retry(
            _openrouter_client.chat.completions.create,
            model=OPENROUTER_MODEL,
            max_tokens=4000,
            extra_body={"reasoning": {"effort": "low"}},
            messages=messages,
        )

        log.info("Narrative provider: OpenRouter fallback (%s)", OPENROUTER_MODEL)
        return response, "openrouter", OPENROUTER_MODEL, True


# ---------------------------------------------------------------------------
# Context and prompt construction
# ---------------------------------------------------------------------------


def _fetch_recent_history(
    db_path: str,
    asset_id: str,
    before: str,
    limit: int = HISTORY_WINDOW,
) -> list[dict[str, Any]]:
    """Fetch the same canonical history used by anomaly detection."""
    rows = db.price_history(
        db_path,
        asset_id,
        config.ANOMALY_SOURCE,
        before,
        limit,
    )
    return [
        {"ts": row[0], "price": row[1], "volume": row[2]}
        for row in reversed(rows)
    ]


_TYPE_GUIDANCE = {
    "zscore_price": (
        "This is a statistical price-move anomaly: a return moved further from "
        "its recent rolling mean than the z-score threshold allows. Explain "
        "whether the move looks like a sharp single-step jump or a sustained "
        "drift, using only the price history given."
    ),
    "iqr_price": (
        "This is an IQR-based outlier: a return fell outside the interquartile "
        "range of its recent window. Explain how far outside the normal range "
        "it fell and whether the surrounding points show a trend or a single spike."
    ),
    "peg_deviation": (
        "This is a stablecoin peg-deviation anomaly: the asset is expected to "
        "trade at a fixed reference such as $1.00 and drifted beyond the allowed "
        "band. Explain the size and direction of the deviation and whether it "
        "has been holding or reverting across the given window."
    ),
    "reconciliation": (
        "This is a cross-source reconciliation anomaly: two data sources for "
        "the same asset disagree beyond the allowed tolerance. Explain which "
        "sources disagree, by how much, and whether this looks like genuine "
        "market divergence or a likely data-quality issue on one source."
    ),
}

_DEFAULT_GUIDANCE = (
    "Explain this anomaly using only the numeric window given, noting what "
    "makes it unusual relative to the recent history."
)

_SYSTEM_PROMPT = """You are a triage assistant embedded in a crypto market-data anomaly pipeline.
You are given one or more anomalies detected in a single polling cycle, each
with recent price history for context.

For EACH anomaly, produce a structured explanation. Hard constraints:
- Reason ONLY from the numeric data provided. Do not invent news events,
  regulatory actions, exchange outages, or other external causes.
- If the data does not make the cause clear, say exactly "cause unclear from data"
  rather than guessing confidently.
- Do not state certainty the data does not support. Prefer "consistent with"
  and "suggests" over "this was caused by".
- If multiple anomalies share a timestamp or overlap in time, note whether they
  look like a correlated market-wide move only when the data supports it.

Respond with ONLY a JSON array, one object per input anomaly, in the same order,
with exactly these keys:
- "anomaly_id": the integer id passed in
- "severity": one of "low", "medium", "high"
- "likely_cause": one to two sentences
- "recommended_action": one short sentence
- "narrative": a plain-language paragraph of 3-5 sentences

No prose before or after the JSON array. No markdown code fences."""


def _build_user_prompt(anomalies_with_history: list[dict[str, Any]]) -> str:
    blocks: list[str] = []

    for anomaly in anomalies_with_history:
        guidance = _TYPE_GUIDANCE.get(
            anomaly["anomaly_type"],
            _DEFAULT_GUIDANCE,
        )
        history_lines = "\n".join(
            f"  {point['ts']} | price={point['price']} | volume={point['volume']}"
            for point in anomaly["history"]
        ) or "  (no history available)"

        blocks.append(
            f"--- Anomaly id={anomaly['id']} ---\n"
            f"Asset: {anomaly['asset_id']}\n"
            f"Type: {anomaly['anomaly_type']}\n"
            f"Detected at: {anomaly['recorded_at']}\n"
            f"Observed value: {anomaly.get('observed_value')}\n"
            f"Reference value: {anomaly.get('reference_value')}\n"
            f"Score: {anomaly.get('score')}\n"
            f"Threshold: {anomaly.get('threshold_used')}\n"
            f"Guidance for this type: {guidance}\n"
            f"Recent history from {config.ANOMALY_SOURCE} (oldest first):\n"
            f"{history_lines}\n"
        )

    return (
        f"There are {len(anomalies_with_history)} anomaly/anomalies from this "
        f"polling cycle:\n\n" + "\n".join(blocks)
    )


# ---------------------------------------------------------------------------
# Response validation and persistence
# ---------------------------------------------------------------------------

_REQUIRED_NARRATIVE_KEYS = {
    "anomaly_id",
    "severity",
    "likely_cause",
    "recommended_action",
    "narrative",
}
_ALLOWED_SEVERITIES = {"low", "medium", "high"}


def _validate_narrative_response(
    parsed: Any,
    anomalies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reject malformed, incomplete, duplicated, or unexpected model output."""
    if not isinstance(parsed, list):
        raise ValueError("Narrative response must be a JSON array")

    expected_ids = {int(anomaly["id"]) for anomaly in anomalies}
    if len(parsed) != len(expected_ids):
        raise ValueError(
            f"Expected {len(expected_ids)} narratives, received {len(parsed)}"
        )

    validated: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Each narrative result must be a JSON object")

        missing = _REQUIRED_NARRATIVE_KEYS - set(item)
        if missing:
            raise ValueError(f"Narrative result missing keys: {sorted(missing)}")

        try:
            anomaly_id = int(item["anomaly_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("anomaly_id must be an integer") from exc

        if anomaly_id not in expected_ids:
            raise ValueError(f"Unexpected anomaly_id returned: {anomaly_id}")
        if anomaly_id in seen_ids:
            raise ValueError(f"Duplicate anomaly_id returned: {anomaly_id}")

        severity = str(item["severity"]).strip().lower()
        if severity not in _ALLOWED_SEVERITIES:
            raise ValueError(f"Invalid severity: {severity}")

        for field in ("likely_cause", "recommended_action", "narrative"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(f"Narrative field must be non-empty text: {field}")

        seen_ids.add(anomaly_id)
        validated.append(
            {
                "anomaly_id": anomaly_id,
                "severity": severity,
                "likely_cause": item["likely_cause"].strip(),
                "recommended_action": item["recommended_action"].strip(),
                "narrative": item["narrative"].strip(),
            }
        )

    if seen_ids != expected_ids:
        raise ValueError(
            f"Narrative IDs do not match input anomalies: "
            f"expected={expected_ids}, got={seen_ids}"
        )

    return validated


def _extract_response_text(response: Any) -> str:
    """Extract text from an OpenAI-compatible chat completion response."""
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response contained no text content")
    return content.strip()


def _strip_json_fence(text: str) -> str:
    """Remove an accidental markdown JSON fence from model output."""
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def attach_history_and_generate(
    db_path: str,
    anomalies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate, validate, and persist one narrative per anomaly."""
    if not anomalies:
        return []

    enriched: list[dict[str, Any]] = []
    for anomaly in anomalies:
        history = _fetch_recent_history(
            db_path,
            anomaly["asset_id"],
            anomaly["recorded_at"],
        )
        enriched.append({**anomaly, "history": history})

    user_prompt = _build_user_prompt(enriched)
    llm_start = time.perf_counter()
    response, provider_used, model_used, fallback_used = _call_llm_with_fallback(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2000,
    )
    llm_stage_ms = (time.perf_counter() - llm_start) * 1000

    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    log.info(
        "LLM narrative call: %d anomaly(ies) | provider=%s | model=%s | "
        "fallback=%s | llm_stage=%.1fms | prompt_tokens=%d | "
        "completion_tokens=%d",
        len(enriched),
        provider_used,
        model_used,
        fallback_used,
        llm_stage_ms,
        prompt_tokens,
        completion_tokens,
    )

    raw_text = _strip_json_fence(_extract_response_text(response))
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        log.error("Failed to parse LLM narrative JSON: %r", raw_text[:500])
        raise

    validated = _validate_narrative_response(parsed, anomalies)
    written: list[dict[str, Any]] = []

    for item in validated:
        narrative_record = {
            **item,
            "provider_used": provider_used,
            "model_used": model_used,
            "latency_ms": llm_stage_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "fallback_used": int(fallback_used),
        }
        db.insert_narrative(db_path, narrative_record)
        written.append(narrative_record)

    return written
