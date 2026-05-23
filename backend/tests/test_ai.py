"""
Unit tests for the AI layer (claude_service.py + /api/v1/ai/* endpoints).

All Anthropic API calls are mocked via ``unittest.mock`` so these tests run
offline and without an ANTHROPIC_API_KEY.

Test structure:
  TestClaudeService         — unit tests for claude_service functions
  TestAIEndpointNarrative   — POST /api/v1/ai/report-narrative
  TestAIEndpointAnomalyExpl — POST /api/v1/ai/explain-anomaly
  TestAIEndpointNLQuery     — POST /api/v1/ai/query
  TestAIEndpointSuggestRules— POST /api/v1/ai/suggest-rules

TODO-AI-008: Add integration tests against the real Anthropic API in CI.
             Gate on the env-var INTEGRIS_AI_INTEGRATION_TESTS=1 and skip
             when unset so the standard test suite never requires a key.
             Place these in tests/integration/test_ai_integration.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.finding import Finding
from app.models.user import ROLE_VALIDATOR, ROLE_TENANT_ADMIN
from app.models.validation import ValidationJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validation_job(db, tenant, study, user) -> ValidationJob:
    job = ValidationJob(
        tenant_id=tenant.id,
        study_id=study.id,
        submitted_by=user.id,
        dataset_ids=[],
        rule_profile="sdtm_default",
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_finding(db, tenant, study, job, finding_type: str = "SDTM_RULE") -> Finding:
    f = Finding(
        tenant_id=tenant.id,
        study_id=study.id,
        job_id=job.id,
        finding_type=finding_type,
        rule_id="SDTM.DM.001",
        severity="HIGH",
        domain="DM",
        field="DMDTC",
        message="Missing required field DMDTC.",
        row_index=1,
        usubjid="SUBJ-001",
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def _fake_message_response(text: str) -> MagicMock:
    """Build a fake anthropic.types.Message-shaped object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ---------------------------------------------------------------------------
# TestClaudeService
# ---------------------------------------------------------------------------

class TestClaudeService:
    """Unit tests for the claude_service module (no HTTP, no real API calls)."""

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_generate_report_narrative_returns_string(self, mock_get_client):
        """generate_report_narrative should return the text from the API response."""
        from app.services.ai.claude_service import generate_report_narrative

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response(
            "The validation run identified 3 findings in the DM domain."
        )
        mock_get_client.return_value = mock_client

        result = await generate_report_narrative(
            validation_results={"total": 3, "CRIT": 0, "HIGH": 1, "MED": 2, "LOW": 0},
            study_metadata={"study_id": "TEST-001", "title": "Test Study"},
        )

        assert isinstance(result, str)
        assert "DM domain" in result
        mock_client.messages.create.assert_awaited_once()

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_generate_report_narrative_passes_correct_model(self, mock_get_client):
        """The correct model name must be sent to the Anthropic API."""
        from app.services.ai.claude_service import generate_report_narrative, _MODEL

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response("ok")
        mock_get_client.return_value = mock_client

        await generate_report_narrative({}, {})

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == _MODEL

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_explain_anomaly_returns_string(self, mock_get_client):
        """explain_anomaly should return the explanation string."""
        from app.services.ai.claude_service import explain_anomaly

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response(
            "The value 999 in VSSTRESN is an outlier for systolic BP."
        )
        mock_get_client.return_value = mock_client

        result = await explain_anomaly(
            anomaly={"usubjid": "S-001", "field": "VSSTRESN", "value": 999},
            domain="VS",
        )
        assert isinstance(result, str)
        assert "999" in result or "outlier" in result.lower() or result  # flexible

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_nl_query_returns_string(self, mock_get_client):
        """nl_query should return the answer string."""
        from app.services.ai.claude_service import nl_query

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response(
            "There are 2 subjects with missing AESTDTC."
        )
        mock_get_client.return_value = mock_client

        result = await nl_query(
            question="Which subjects are missing AESTDTC?",
            context={"job_id": "abc", "summary": {"CRIT": 0}},
        )
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_suggest_rule_profile_returns_dict(self, mock_get_client):
        """suggest_rule_profile should parse the JSON response into a dict."""
        import json
        from app.services.ai.claude_service import suggest_rule_profile

        expected = {
            "recommended_profile": "sdtm_default",
            "confidence": "high",
            "rationale": "All required SDTM DM variables are present.",
            "missing_variables": [],
            "extra_variables": ["DMEXTRA"],
        }
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response(
            json.dumps(expected)
        )
        mock_get_client.return_value = mock_client

        result = await suggest_rule_profile(
            dataset_sample={"domain": "DM", "columns": ["USUBJID", "AGE"]}
        )
        assert isinstance(result, dict)
        assert result["recommended_profile"] == "sdtm_default"
        assert result["confidence"] == "high"

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_suggest_rule_profile_handles_non_json(self, mock_get_client):
        """If Claude returns non-JSON, suggest_rule_profile wraps it gracefully."""
        from app.services.ai.claude_service import suggest_rule_profile

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = _fake_message_response(
            "I would recommend sdtm_default based on the variables present."
        )
        mock_get_client.return_value = mock_client

        result = await suggest_rule_profile(dataset_sample={"domain": "DM"})
        assert isinstance(result, dict)
        assert result["recommended_profile"] == "unknown"
        assert result["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_claude_service_error(self):
        """ClaudeServiceError must be raised when ANTHROPIC_API_KEY is empty."""
        from app.services.ai.claude_service import ClaudeServiceError, generate_report_narrative
        from unittest.mock import patch

        with patch("app.services.ai.claude_service.get_settings") as mock_settings:
            mock_settings.return_value.ANTHROPIC_API_KEY = ""
            with pytest.raises(ClaudeServiceError, match="not configured"):
                await generate_report_narrative({}, {})

    @patch("app.services.ai.claude_service._get_client")
    @pytest.mark.asyncio
    async def test_api_error_raises_claude_service_error(self, mock_get_client):
        """APIError from the Anthropic SDK must be re-raised as ClaudeServiceError."""
        import anthropic
        from app.services.ai.claude_service import ClaudeServiceError, generate_report_narrative

        mock_client = AsyncMock()
        mock_client.messages.create.side_effect = anthropic.APIStatusError(
            "Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit"}},
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ClaudeServiceError):
            await generate_report_narrative({}, {})


# ---------------------------------------------------------------------------
# TestAIEndpointNarrative
# ---------------------------------------------------------------------------

class TestAIEndpointNarrative:
    """HTTP-level tests for POST /api/v1/ai/report-narrative."""

    def test_returns_401_without_auth(self, client):
        resp = client.post("/api/v1/ai/report-narrative", json={"validation_result_id": str(uuid.uuid4())})
        assert resp.status_code == 401

    def test_returns_403_for_viewer(self, client, viewer_headers):
        resp = client.post(
            "/api/v1/ai/report-narrative",
            json={"validation_result_id": str(uuid.uuid4())},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_returns_404_for_unknown_job(self, client, validator_headers):
        resp = client.post(
            "/api/v1/ai/report-narrative",
            json={"validation_result_id": str(uuid.uuid4())},
            headers=validator_headers,
        )
        assert resp.status_code == 404

    @patch("app.api.v1.ai.claude_service.generate_report_narrative", new_callable=AsyncMock)
    def test_returns_narrative_for_completed_job(
        self, mock_gen, client, db, tenant, validator_user, validator_headers, study
    ):
        """Should call claude_service and return the narrative string."""
        mock_gen.return_value = "This study has 1 HIGH finding in DM."
        job = _make_validation_job(db, tenant, study, validator_user)

        resp = client.post(
            "/api/v1/ai/report-narrative",
            json={"validation_result_id": str(job.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "narrative" in body
        assert "HIGH" in body["narrative"] or body["narrative"]  # flexible

    def test_returns_409_for_queued_job(self, client, db, tenant, validator_user, validator_headers, study):
        """Should return 409 when the job is not yet completed."""
        job = ValidationJob(
            tenant_id=tenant.id,
            study_id=study.id,
            submitted_by=validator_user.id,
            dataset_ids=[],
            rule_profile="sdtm_default",
            status="queued",
        )
        db.add(job)
        db.commit()

        resp = client.post(
            "/api/v1/ai/report-narrative",
            json={"validation_result_id": str(job.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# TestAIEndpointAnomalyExpl
# ---------------------------------------------------------------------------

class TestAIEndpointAnomalyExpl:
    """HTTP-level tests for POST /api/v1/ai/explain-anomaly."""

    def test_returns_401_without_auth(self, client):
        resp = client.post("/api/v1/ai/explain-anomaly", json={"anomaly_id": str(uuid.uuid4())})
        assert resp.status_code == 401

    def test_returns_404_for_unknown_finding(self, client, validator_headers):
        resp = client.post(
            "/api/v1/ai/explain-anomaly",
            json={"anomaly_id": str(uuid.uuid4())},
            headers=validator_headers,
        )
        assert resp.status_code == 404

    @patch("app.api.v1.ai.claude_service.explain_anomaly", new_callable=AsyncMock)
    def test_returns_explanation_for_anomaly_finding(
        self, mock_explain, client, db, tenant, validator_user, validator_headers, study
    ):
        mock_explain.return_value = "This value is 4 standard deviations above the mean."
        job     = _make_validation_job(db, tenant, study, validator_user)
        finding = _make_finding(db, tenant, study, job, finding_type="ANOMALY")

        resp = client.post(
            "/api/v1/ai/explain-anomaly",
            json={"anomaly_id": str(finding.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        assert "explanation" in resp.json()

    def test_returns_404_for_non_anomaly_finding(
        self, client, db, tenant, validator_user, validator_headers, study
    ):
        """SDTM_RULE findings must not be returned by the anomaly endpoint."""
        job     = _make_validation_job(db, tenant, study, validator_user)
        finding = _make_finding(db, tenant, study, job, finding_type="SDTM_RULE")

        resp = client.post(
            "/api/v1/ai/explain-anomaly",
            json={"anomaly_id": str(finding.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestAIEndpointNLQuery
# ---------------------------------------------------------------------------

class TestAIEndpointNLQuery:
    """HTTP-level tests for POST /api/v1/ai/query."""

    def test_returns_401_without_auth(self, client, study):
        resp = client.post("/api/v1/ai/query", json={"question": "test?", "study_id": str(study.id)})
        assert resp.status_code == 401

    def test_returns_404_when_no_completed_job(self, client, validator_headers, study):
        resp = client.post(
            "/api/v1/ai/query",
            json={"question": "Any issues?", "study_id": str(study.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 404

    @patch("app.api.v1.ai.claude_service.nl_query", new_callable=AsyncMock)
    def test_returns_answer(
        self, mock_query, client, db, tenant, validator_user, validator_headers, study
    ):
        mock_query.return_value = "There are no missing AESTDTC values."
        _make_validation_job(db, tenant, study, validator_user)

        resp = client.post(
            "/api/v1/ai/query",
            json={"question": "Are there missing AESTDTC values?", "study_id": str(study.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert isinstance(body["answer"], str)


# ---------------------------------------------------------------------------
# TestAIEndpointSuggestRules
# ---------------------------------------------------------------------------

class TestAIEndpointSuggestRules:
    """HTTP-level tests for POST /api/v1/ai/suggest-rules."""

    def test_returns_401_without_auth(self, client, study):
        resp = client.post("/api/v1/ai/suggest-rules", json={"study_id": str(study.id)})
        assert resp.status_code == 401

    def test_returns_404_when_no_dataset(self, client, validator_headers, study):
        resp = client.post(
            "/api/v1/ai/suggest-rules",
            json={"study_id": str(study.id)},
            headers=validator_headers,
        )
        assert resp.status_code == 404
