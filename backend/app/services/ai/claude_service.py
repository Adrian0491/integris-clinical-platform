"""
Integris Clinical Platform — Claude AI Service
===============================================
Thin async wrapper around the Anthropic Claude API providing four
high-level operations used throughout the validation platform:

  * generate_report_narrative  — plain-English summary for PDF reports
  * explain_anomaly            — clinical explanation of an Isolation Forest anomaly
  * nl_query                   — natural-language query over validation results
  * suggest_rule_profile       — CDISC rule-profile recommendation from a dataset sample

All functions raise ``ClaudeServiceError`` on API or configuration failures
so callers can catch a single exception type.

TODO-AI-001: Add streaming support for long narrative generation using
             client.messages.stream() and SSE response type in the API layer.

TODO-AI-002: Add a prompt versioning and Redis caching layer.  Cache key =
             SHA-256(model + system_prompt_version + user_message).  TTL = 24 h.
             Store versioned system prompts in a separate prompts.py module so
             prompt changes are tracked alongside code changes.

TODO-AI-003: Add per-tenant token usage tracking.  After each API call, write
             {tenant_id, model, input_tokens, output_tokens, endpoint, ts} to a
             dedicated usage table (or Cloud Billing BigQuery export) so quotas
             and per-tenant billing can be enforced.

TODO-AI-004: Implement conversation history for multi-turn nl_query sessions.
             Store message history in Redis keyed by (tenant_id, session_id).
             Pass the full history as the ``messages`` list to the API.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 1024

# Clinical data system prompt — establishes context for all calls.
# Every function may augment this with task-specific instructions.
_SYSTEM_PROMPT = """\
You are a clinical data specialist embedded in a regulatory-grade clinical \
data validation platform used by Contract Research Organisations (CROs) and \
pharmaceutical sponsors.

Context you must always respect:
- All data and findings relate to clinical trials governed by FDA 21 CFR Part 11 \
  (electronic records and signatures) and ICH E6(R2) Good Clinical Practice.
- Dataset structures conform to CDISC SDTM (Study Data Tabulation Model) and, \
  where relevant, CDISC ADaM (Analysis Data Model).
- Dataset exchange files use CDISC Dataset-JSON v1.1 format.
- Validation findings are classified by severity: CRIT (critical), HIGH, MED, LOW.
- Your audience is professional clinical data managers, biometrics leads, and \
  regulatory affairs specialists — use precise, unambiguous language.
- Never speculate beyond the data provided; flag uncertainty explicitly.
- Do not include personally identifiable information (PII) or Protected Health \
  Information (PHI) in any response.
- Responses will appear verbatim in FDA-facing compliance reports, so accuracy \
  is paramount.
"""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ClaudeServiceError(RuntimeError):
    """Raised when the Claude API call fails or the service is misconfigured."""


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.AsyncAnthropic:
    """
    Return a configured async Anthropic client.
    Raises ``ClaudeServiceError`` if ANTHROPIC_API_KEY is not set.
    """
    api_key = get_settings().ANTHROPIC_API_KEY
    if not api_key:
        raise ClaudeServiceError(
            "ANTHROPIC_API_KEY is not configured.  "
            "Set it in .env or as an environment variable."
        )
    return anthropic.AsyncAnthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Public async functions
# ---------------------------------------------------------------------------

async def generate_report_narrative(
    validation_results: dict[str, Any],
    study_metadata: dict[str, Any],
) -> str:
    """
    Generate a plain-English narrative summary of validation results suitable
    for inclusion in a 21 CFR Part 11 compliant PDF validation report.

    Args:
        validation_results: Dict produced by the validation pipeline, typically
            containing keys: ``job_id``, ``total``, ``CRIT``, ``HIGH``, ``MED``,
            ``LOW``, ``domains`` (dict of domain -> count), ``findings`` (list).
        study_metadata: Study context — ``study_id``, ``title``, ``phase``,
            ``sponsor``, ``therapeutic_area``.

    Returns:
        Narrative string (plain text, paragraph form).

    TODO-AI-001: Replace with streaming implementation for result sets > ~50
                 findings so the UI can render tokens progressively.
    """
    client = _get_client()

    user_message = (
        "Generate a professional validation report narrative based on the following "
        "CDISC/SDTM validation results.\n\n"
        f"Study Metadata:\n{json.dumps(study_metadata, indent=2)}\n\n"
        f"Validation Results Summary:\n{json.dumps(validation_results, indent=2)}\n\n"
        "The narrative should:\n"
        "1. Open with a one-sentence executive summary (overall compliance posture).\n"
        "2. Describe each domain with findings, noting severity distribution.\n"
        "3. Highlight any CRIT or HIGH findings with specific rule references.\n"
        "4. Close with a recommendation paragraph (remediation priority order).\n"
        "Use formal, regulatory-appropriate language.  Plain text only — no markdown."
    )

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.APIError as exc:
        log.error("Claude API error in generate_report_narrative: %s", exc)
        raise ClaudeServiceError(f"Claude API error: {exc}") from exc


async def explain_anomaly(anomaly: dict[str, Any], domain: str) -> str:
    """
    Produce a clinical explanation of an Isolation Forest anomaly finding.

    Args:
        anomaly: Anomaly dict from the validation pipeline.  Expected keys:
            ``usubjid``, ``field``, ``value``, ``anomaly_score``, ``evidence``.
        domain: SDTM domain abbreviation (e.g. ``"VS"``, ``"AE"``).

    Returns:
        Clinical explanation string.
    """
    client = _get_client()

    user_message = (
        f"The following statistical anomaly was detected in the SDTM {domain} domain "
        "by an Isolation Forest model during a CDISC validation run.\n\n"
        f"Anomaly Details:\n{json.dumps(anomaly, indent=2)}\n\n"
        "Please provide:\n"
        "1. A plain-English clinical explanation of why this data point may be anomalous.\n"
        "2. The most plausible clinical or data-entry explanations (list up to three).\n"
        "3. The recommended data management action (query, waiver, correction, or escalation).\n"
        "4. Relevant CDISC SDTM Implementation Guide references if applicable.\n"
        "Keep the response concise — it will be shown inline in a data review grid."
    )

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.APIError as exc:
        log.error("Claude API error in explain_anomaly: %s", exc)
        raise ClaudeServiceError(f"Claude API error: {exc}") from exc


async def nl_query(question: str, context: dict[str, Any]) -> str:
    """
    Answer a natural-language question about validation results.

    Args:
        question: Free-text question from the user (e.g. "Which subjects have
            missing AESTDTC in AE?").
        context: Validation context provided to the model — typically contains
            ``job_id``, ``study_id``, ``summary`` (severity counts), and a
            ``findings`` list (truncated to keep prompt size manageable).

    Returns:
        Answer string.

    TODO-AI-004: Extend to multi-turn by accepting a ``session_id`` parameter,
                 loading prior messages from Redis, and appending them before
                 the current question.
    """
    client = _get_client()

    user_message = (
        "A clinical data analyst is asking a question about the following validation "
        "run context.  Answer based strictly on the provided data.\n\n"
        f"Validation Context:\n{json.dumps(context, indent=2)}\n\n"
        f"Question: {question}\n\n"
        "Answer concisely and precisely.  If the context does not contain enough "
        "information to answer fully, say so explicitly rather than speculating."
    )

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.APIError as exc:
        log.error("Claude API error in nl_query: %s", exc)
        raise ClaudeServiceError(f"Claude API error: {exc}") from exc


async def suggest_rule_profile(dataset_sample: dict[str, Any]) -> dict[str, Any]:
    """
    Analyse a dataset sample and suggest a CDISC validation rule profile.

    The model inspects variable names, value distributions, and domain
    context to recommend which rule-profile best fits the dataset — useful
    for onboarding studies with non-standard configurations.

    Args:
        dataset_sample: Dict with keys ``domain``, ``columns`` (list of
            variable names), ``sample_rows`` (first N rows as list-of-dicts),
            ``row_count``.

    Returns:
        Dict with keys:
            ``recommended_profile`` (str)  — e.g. ``"sdtm_default"``,
                ``"adam_adae"``, ``"custom_oncology"``
            ``confidence``          (str)  — ``"high"`` | ``"medium"`` | ``"low"``
            ``rationale``           (str)  — explanation
            ``missing_variables``   (list) — required SDTM vars absent from sample
            ``extra_variables``     (list) — unrecognised vars that may need mapping
    """
    client = _get_client()

    user_message = (
        "Analyse this CDISC dataset sample and recommend the most appropriate "
        "SDTM validation rule profile.\n\n"
        f"Dataset Sample:\n{json.dumps(dataset_sample, indent=2)}\n\n"
        "Respond with a valid JSON object only (no markdown, no extra text) "
        "with exactly these keys:\n"
        "  recommended_profile (string)\n"
        "  confidence          (string: high | medium | low)\n"
        "  rationale           (string)\n"
        "  missing_variables   (array of strings)\n"
        "  extra_variables     (array of strings)\n"
    )

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Claude returned non-JSON for suggest_rule_profile; wrapping as raw.")
            return {"recommended_profile": "unknown", "confidence": "low",
                    "rationale": raw, "missing_variables": [], "extra_variables": []}
    except anthropic.APIError as exc:
        log.error("Claude API error in suggest_rule_profile: %s", exc)
        raise ClaudeServiceError(f"Claude API error: {exc}") from exc
