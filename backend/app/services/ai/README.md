# AI Layer — Integris Clinical Platform

Thin async wrapper around the Anthropic Claude API providing four
clinical-data-specific AI operations.  All calls are authenticated with
JWT and gated to ROLE_VALIDATOR or above.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (in prod) | `""` | Anthropic API key — set in `.env` or GCP Secret Manager (see TODO-AI-007) |

## Model

All functions use **`claude-sonnet-4-20250514`**, `max_tokens=1024`.  
The system prompt establishes FDA 21 CFR Part 11 / CDISC / CRO context and is
applied to every request.

## Endpoints

### `POST /api/v1/ai/report-narrative`

Generate a plain-English validation report narrative for a completed validation job.

**Auth:** `ROLE_VALIDATOR` minimum  
**Request:**
```json
{
  "validation_result_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Response:**
```json
{
  "narrative": "The validation run for study CDTOOL-001 identified 14 findings across three SDTM domains..."
}
```

---

### `POST /api/v1/ai/explain-anomaly`

Get a clinical explanation for an Isolation Forest anomaly finding (finding_type = ANOMALY).

**Auth:** `ROLE_VALIDATOR` minimum  
**Request:**
```json
{
  "anomaly_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Response:**
```json
{
  "explanation": "The VSSTRESN value of 340 mmHg for subject SUBJ-003 is approximately 4.2 standard deviations above the mean systolic BP for this cohort..."
}
```

---

### `POST /api/v1/ai/query`

Ask a natural-language question about the most recent completed validation run for a study.

**Auth:** `ROLE_VALIDATOR` minimum  
**Request:**
```json
{
  "question": "Which subjects are missing AESTDTC in the AE domain?",
  "study_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Response:**
```json
{
  "answer": "Based on the validation findings, subjects SUBJ-002 and SUBJ-007 have missing AESTDTC values in the AE domain (findings SDTM.AE.004)."
}
```

---

### `POST /api/v1/ai/suggest-rules`

Analyse the most recently uploaded dataset for a study and recommend a CDISC validation rule profile.

**Auth:** `ROLE_VALIDATOR` minimum  
**Request:**
```json
{
  "study_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Response:**
```json
{
  "suggested_profile": {
    "recommended_profile": "sdtm_default",
    "confidence": "high",
    "rationale": "All required SDTM DM variables (USUBJID, AGE, SEX, RACE) are present and correctly typed.",
    "missing_variables": ["DMDTC"],
    "extra_variables": ["DMSITE"]
  }
}
```

## Outstanding TODOs

| ID | Description |
|---|---|
| TODO-AI-001 | Streaming support for long narratives (SSE) |
| TODO-AI-002 | Prompt versioning + Redis cache (24h TTL, SHA-256 key) |
| TODO-AI-003 | Per-tenant token usage tracking for billing/quota |
| TODO-AI-004 | Multi-turn NL query sessions via Redis conversation history |
| TODO-AI-005 | Per-tenant rate limiting (sliding window, Redis) |
| TODO-AI-006 | Audit trail entry for every AI call |
| TODO-AI-007 | ANTHROPIC_API_KEY in GCP Secret Manager + Terraform |
| TODO-AI-008 | Integration tests against real API (CI feature flag) |
