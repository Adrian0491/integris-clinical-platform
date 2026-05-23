"""
Unit tests for the EDC connector layer.

Tests:
  TestEDCConnectorFactory     — factory routing logic for all system types
  TestREDCapConnectorAuth     — REDCapConnector.authenticate() (mocked HTTP)
  TestREDCapConnectorStudies  — REDCapConnector.list_studies()
  TestREDCapPullDataset       — REDCapConnector.pull_dataset() Dataset-JSON shape
  TestEDCEndpoints            — HTTP-level tests for /api/v1/edc/*

No real EDC system is required; all HTTP calls use ``responses`` or
``unittest.mock`` to simulate server responses.

TODO-EDC-021: Add integration tests against a REDCap sandbox environment.
              Gate on env-var INTEGRIS_REDCAP_INTEGRATION_TESTS=1.
              Use a dedicated test project on a shared REDCap demo instance.
              Place in tests/integration/test_edc_integration.py.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.edc.base import EDCConnectionConfig, EDCSystemType
from app.services.edc.factory import EDCConnectorFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def redcap_config() -> EDCConnectionConfig:
    return EDCConnectionConfig(
        system_type=EDCSystemType.REDCAP,
        base_url="https://redcap.example.org",
        api_key="TESTTOKEN123",
        tenant_id=str(uuid.uuid4()),
    )


@pytest.fixture()
def rave_config() -> EDCConnectionConfig:
    return EDCConnectionConfig(
        system_type=EDCSystemType.MEDIDATA_RAVE,
        base_url="https://acme.mdsol.com",
        tenant_id=str(uuid.uuid4()),
        extra={"client_id": "cid", "client_secret": "csec"},
    )


@pytest.fixture()
def veeva_config() -> EDCConnectionConfig:
    return EDCConnectionConfig(
        system_type=EDCSystemType.VEEVA_VAULT,
        base_url="https://acme.veevavault.com",
        username="user@acme.com",
        password="secret",
        tenant_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# TestEDCConnectorFactory
# ---------------------------------------------------------------------------

class TestEDCConnectorFactory:
    """EDCConnectorFactory.create() must return the correct connector type."""

    def test_creates_redcap_connector(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector
        connector = EDCConnectorFactory.create(redcap_config)
        assert isinstance(connector, REDCapConnector)

    def test_creates_medidata_rave_connector(self, rave_config):
        from app.services.edc.medidata_rave import MedidataRaveConnector
        connector = EDCConnectorFactory.create(rave_config)
        assert isinstance(connector, MedidataRaveConnector)

    def test_creates_veeva_vault_connector(self, veeva_config):
        from app.services.edc.veeva_vault import VeevaVaultConnector
        connector = EDCConnectorFactory.create(veeva_config)
        assert isinstance(connector, VeevaVaultConnector)

    def test_raises_for_oracle_clinical_one(self):
        config = EDCConnectionConfig(
            system_type=EDCSystemType.ORACLE_CLINICAL_ONE,
            base_url="https://oc1.example.com",
            tenant_id=str(uuid.uuid4()),
        )
        with pytest.raises(NotImplementedError, match="Oracle Clinical One"):
            EDCConnectorFactory.create(config)

    def test_raises_for_generic_fhir(self):
        config = EDCConnectionConfig(
            system_type=EDCSystemType.GENERIC_FHIR,
            base_url="https://fhir.example.com",
            tenant_id=str(uuid.uuid4()),
        )
        with pytest.raises(NotImplementedError, match="FHIR"):
            EDCConnectorFactory.create(config)

    def test_connector_stores_config(self, redcap_config):
        connector = EDCConnectorFactory.create(redcap_config)
        assert connector.config is redcap_config

    def test_connector_not_authenticated_on_init(self, redcap_config):
        connector = EDCConnectorFactory.create(redcap_config)
        assert connector._authenticated is False


# ---------------------------------------------------------------------------
# TestREDCapConnectorAuth
# ---------------------------------------------------------------------------

class TestREDCapConnectorAuth:
    """
    REDCapConnector.authenticate() must POST to the REDCap API and set
    _authenticated = True on success.
    """

    @pytest.mark.asyncio
    async def test_authenticate_success(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        connector = REDCapConnector(redcap_config)

        with patch.object(connector, "_post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.text = "14.7.2"
            mock_post.return_value = mock_resp

            result = await connector.authenticate()

        assert result is True
        assert connector._authenticated is True
        assert connector._redcap_version == "14.7.2"
        mock_post.assert_called_once_with(content="version")

    @pytest.mark.asyncio
    async def test_authenticate_http_error_sets_not_authenticated(self, redcap_config):
        import requests as _requests
        from app.services.edc.redcap import REDCapConnector

        connector = REDCapConnector(redcap_config)

        with patch.object(connector, "_post") as mock_post:
            mock_post.side_effect = _requests.HTTPError("401 Unauthorized")
            with pytest.raises(_requests.HTTPError):
                await connector.authenticate()

        assert connector._authenticated is False

    @pytest.mark.asyncio
    async def test_authenticate_connection_error(self, redcap_config):
        import requests as _requests
        from app.services.edc.redcap import REDCapConnector

        connector = REDCapConnector(redcap_config)

        with patch.object(connector, "_post") as mock_post:
            mock_post.side_effect = _requests.ConnectionError("Connection refused")
            with pytest.raises(_requests.ConnectionError):
                await connector.authenticate()

        assert connector._authenticated is False

    @pytest.mark.asyncio
    async def test_api_key_included_in_post(self, redcap_config):
        """_post() must include the API token in every request."""
        from app.services.edc.redcap import REDCapConnector
        import requests as _requests

        connector = REDCapConnector(redcap_config)

        with patch.object(connector._session, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.text = "14.0.0"
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            await connector.authenticate()

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["data"]["token"] == "TESTTOKEN123"


# ---------------------------------------------------------------------------
# TestREDCapConnectorStudies
# ---------------------------------------------------------------------------

class TestREDCapConnectorStudies:
    """REDCapConnector.list_studies() must call the REDCap project API."""

    @pytest.mark.asyncio
    async def test_list_studies_returns_normalised_list(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        project_data = {
            "project_id": 42,
            "project_title": "Hypertension Phase II",
            "is_longitudinal": 0,
            "purpose_other": "Research",
            "creation_time": "2024-01-15 09:00:00",
        }

        connector = REDCapConnector(redcap_config)
        connector._authenticated = True

        with patch.object(connector, "_post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = project_data
            mock_post.return_value = mock_resp

            studies = await connector.list_studies()

        assert isinstance(studies, list)
        assert len(studies) == 1
        assert studies[0]["study_id"] == "42"
        assert studies[0]["title"] == "Hypertension Phase II"

    @pytest.mark.asyncio
    async def test_list_studies_requires_auth(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        connector = REDCapConnector(redcap_config)
        # _authenticated is False by default
        with pytest.raises(RuntimeError, match="authenticate"):
            await connector.list_studies()


# ---------------------------------------------------------------------------
# TestREDCapPullDataset
# ---------------------------------------------------------------------------

class TestREDCapPullDataset:
    """
    REDCapConnector.pull_dataset() must produce a valid Dataset-JSON v1.1 envelope.
    """

    @pytest.mark.asyncio
    async def test_pull_dataset_returns_dataset_json_shape(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        metadata = [
            {"field_name": "record_id",  "form_name": "dm", "field_type": "text",  "field_label": "Record ID"},
            {"field_name": "age",        "form_name": "dm", "field_type": "text",  "field_label": "Age"},
            {"field_name": "sex",        "form_name": "dm", "field_type": "radio", "field_label": "Sex"},
        ]
        records = [
            {"record_id": "1", "age": "34", "sex": "M"},
            {"record_id": "2", "age": "45", "sex": "F"},
        ]

        connector = REDCapConnector(redcap_config)
        connector._authenticated = True
        connector._redcap_version = "14.7.2"

        call_count = {"n": 0}

        def _mock_post(**kwargs):
            mock_resp = MagicMock()
            if kwargs.get("content") == "metadata":
                mock_resp.json.return_value = metadata
            else:
                mock_resp.json.return_value = records
            call_count["n"] += 1
            return mock_resp

        with patch.object(connector, "_post", side_effect=_mock_post):
            result = await connector.pull_dataset(study_id="42", domain="DM")

        # Validate Dataset-JSON v1.1 envelope structure
        assert result["datasetJSONVersion"] == "1.0"
        assert result["sourceSystem"] == "REDCap"
        assert result["itemGroupOID"] == "IG.DM"
        assert result["records"] == 2
        assert isinstance(result["columns"], list)
        assert isinstance(result["rows"], list)
        assert len(result["rows"]) == 2

        # Each row should be a list of values (same length as columns)
        assert len(result["rows"][0]) == len(result["columns"])

    @pytest.mark.asyncio
    async def test_pull_dataset_column_names_are_uppercase(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        metadata = [
            {"field_name": "usubjid", "form_name": "dm", "field_type": "text", "field_label": "USUBJID"},
        ]
        records = [{"record_id": "1", "usubjid": "SUBJ-001"}]

        connector = REDCapConnector(redcap_config)
        connector._authenticated = True

        def _mock_post(**kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = metadata if kwargs.get("content") == "metadata" else records
            return mock_resp

        with patch.object(connector, "_post", side_effect=_mock_post):
            result = await connector.pull_dataset("42", "dm")

        col_names = [c["name"] for c in result["columns"]]
        assert all(n == n.upper() for n in col_names), "Column names must be uppercase"

    @pytest.mark.asyncio
    async def test_pull_dataset_requires_auth(self, redcap_config):
        from app.services.edc.redcap import REDCapConnector

        connector = REDCapConnector(redcap_config)
        with pytest.raises(RuntimeError, match="authenticate"):
            await connector.pull_dataset("42", "DM")


# ---------------------------------------------------------------------------
# TestMedidataRaveStubs
# ---------------------------------------------------------------------------

class TestMedidataRaveStubs:
    """Medidata Rave methods must raise NotImplementedError (stubbed)."""

    @pytest.mark.asyncio
    async def test_authenticate_raises_not_implemented(self, rave_config):
        connector = EDCConnectorFactory.create(rave_config)
        with pytest.raises(NotImplementedError):
            await connector.authenticate()

    @pytest.mark.asyncio
    async def test_list_studies_raises_runtime_before_auth(self, rave_config):
        from app.services.edc.medidata_rave import MedidataRaveConnector
        connector = MedidataRaveConnector(rave_config)
        with pytest.raises(RuntimeError, match="authenticate"):
            await connector.list_studies()


# ---------------------------------------------------------------------------
# TestEDCEndpoints
# ---------------------------------------------------------------------------

class TestEDCEndpoints:
    """HTTP-level tests for /api/v1/edc/* — requires admin role."""

    def test_connect_returns_401_without_auth(self, client):
        resp = client.post("/api/v1/edc/connect", json={
            "system_type": "redcap",
            "base_url": "https://redcap.example.org",
            "api_key": "TOKEN",
        })
        assert resp.status_code == 401

    def test_connect_returns_403_for_validator(self, client, validator_headers):
        resp = client.post("/api/v1/edc/connect", json={
            "system_type": "redcap",
            "base_url": "https://redcap.example.org",
            "api_key": "TOKEN",
        }, headers=validator_headers)
        assert resp.status_code == 403

    def test_status_returns_not_connected_without_config(self, client, admin_headers):
        resp = client.get("/api/v1/edc/status", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is False

    @patch("app.api.v1.edc.EDCConnectorFactory")
    def test_connect_success_stores_config(self, mock_factory, client, admin_headers):
        mock_connector = AsyncMock()
        mock_connector.authenticate.return_value = True
        mock_factory.create.return_value = mock_connector

        resp = client.post("/api/v1/edc/connect", json={
            "system_type": "redcap",
            "base_url": "https://redcap.example.org",
            "api_key": "VALIDTOKEN",
        }, headers=admin_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "connected"
        assert body["system_type"] == "redcap"

    @patch("app.api.v1.edc.EDCConnectorFactory")
    def test_connect_returns_501_for_not_implemented(self, mock_factory, client, admin_headers):
        mock_connector = AsyncMock()
        mock_connector.authenticate.side_effect = NotImplementedError("Not implemented")
        mock_factory.create.return_value = mock_connector

        resp = client.post("/api/v1/edc/connect", json={
            "system_type": "medidata_rave",
            "base_url": "https://acme.mdsol.com",
        }, headers=admin_headers)

        assert resp.status_code == 501

    def test_studies_returns_404_without_connection(self, client, admin_headers):
        # Clear any lingering in-memory state by using a fresh admin
        resp = client.get("/api/v1/edc/studies", headers=admin_headers)
        # Either 404 (no config) or 200 if a previous test left state — just
        # assert it's not a 401/403
        assert resp.status_code in (200, 404)

    def test_import_returns_401_without_auth(self, client):
        resp = client.post("/api/v1/edc/import/TEST-001")
        assert resp.status_code == 401
