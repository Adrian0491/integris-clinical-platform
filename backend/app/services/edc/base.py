"""
Integris Clinical Platform — EDC Connector Abstraction Layer
=============================================================
Defines the abstract interface that every Electronic Data Capture (EDC)
connector must implement, plus shared configuration data structures.

Supported system types (see EDCSystemType):
  - MEDIDATA_RAVE        — Medidata Rave EDC (OAuth2, REST v1)
  - REDCAP               — REDCap (token-based API)
  - VEEVA_VAULT          — Veeva Vault Clinical Data Management
  - ORACLE_CLINICAL_ONE  — Oracle Clinical One (planned)
  - GENERIC_FHIR         — Any FHIR R4-compatible EDC (planned)

All methods are ``async`` so connectors can be awaited in FastAPI request
handlers without blocking the event loop.

TODO-EDC-001: Add connection pooling and session reuse across requests.
              Implement a connector registry keyed by (tenant_id, system_type)
              that caches authenticated connector instances for a configurable
              TTL (default 30 minutes), refreshing tokens before expiry.

TODO-EDC-002: Add webhook/push support so EDC systems can notify the platform
              of new or changed data in real time.  Define a POST
              /api/v1/edc/webhook/{tenant_id} endpoint protected by an HMAC
              signature, and route payloads to the appropriate connector's
              ``handle_push()`` method.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enum — supported EDC system types
# ---------------------------------------------------------------------------

class EDCSystemType(str, Enum):
    MEDIDATA_RAVE       = "medidata_rave"
    REDCAP              = "redcap"
    VEEVA_VAULT         = "veeva_vault"
    ORACLE_CLINICAL_ONE = "oracle_clinical_one"   # TODO-EDC-016
    GENERIC_FHIR        = "generic_fhir"           # TODO-EDC-017


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class EDCConnectionConfig:
    """
    Holds all parameters needed to connect to an EDC system.

    Attributes:
        system_type:  Which EDC system this config targets.
        base_url:     Root URL of the EDC instance (no trailing slash).
                      e.g. ``"https://your-org.mdsol.com"``
        api_key:      API key / token (used by REDCap and similar systems).
        username:     Username for systems using basic auth or OAuth2 ROPC.
        password:     Password (stored encrypted at rest — see TODO-EDC-018).
        tenant_id:    Platform tenant UUID (str) that owns this connection.
        extra:        Connector-specific overrides (e.g. OAuth2 client_id/secret
                      for Medidata Rave, or Veeva Vault domain name).
    """
    system_type: EDCSystemType
    base_url:    str
    tenant_id:   str
    api_key:     str                   = ""
    username:    str                   = ""
    password:    str                   = ""
    extra:       dict[str, Any]        = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract connector base class
# ---------------------------------------------------------------------------

class EDCConnector(abc.ABC):
    """
    Abstract base class for all EDC system connectors.

    Each concrete subclass must implement every abstract method.
    Implementations should be async-safe (no blocking I/O on the event loop)
    unless explicitly noted otherwise.

    Usage:
        config = EDCConnectionConfig(
            system_type=EDCSystemType.REDCAP,
            base_url="https://redcap.example.org",
            api_key="ABCDEF12345...",
            tenant_id="<uuid>",
        )
        connector = EDCConnectorFactory.create(config)
        await connector.authenticate()
        studies = await connector.list_studies()
    """

    def __init__(self, config: EDCConnectionConfig) -> None:
        self.config = config
        self._authenticated: bool = False

    # ── Authentication ─────────────────────────────────────────────────────

    @abc.abstractmethod
    async def authenticate(self) -> bool:
        """
        Perform the system-specific authentication handshake.

        Returns:
            ``True`` on success; raises on failure.

        After a successful call, the connector should store any session
        tokens internally and re-use them for subsequent method calls.
        """

    # ── Study / project listing ────────────────────────────────────────────

    @abc.abstractmethod
    async def list_studies(self) -> list[dict[str, Any]]:
        """
        Return a list of studies / projects available to the authenticated user.

        Each dict should contain at minimum:
            ``study_id`` (str), ``title`` (str), ``status`` (str).
        """

    @abc.abstractmethod
    async def get_study_metadata(self, study_id: str) -> dict[str, Any]:
        """
        Return full metadata for a single study.

        Returns a dict with study-level attributes:
            ``study_id``, ``title``, ``phase``, ``sponsor``, ``protocol_id``,
            ``therapeutic_area``, ``start_date``, ``end_date``, ``status``.
        """

    # ── Data extraction ────────────────────────────────────────────────────

    @abc.abstractmethod
    async def list_domains(self, study_id: str) -> list[str]:
        """
        Return the SDTM domain abbreviations available for a study.

        e.g. ``["DM", "VS", "AE", "CM", "LB"]``
        """

    @abc.abstractmethod
    async def get_subjects(self, study_id: str) -> list[dict[str, Any]]:
        """
        Return a list of subjects enrolled in the study.

        Each dict: ``{"usubjid": str, "siteid": str, "arm": str, ...}``.
        """

    @abc.abstractmethod
    async def pull_dataset(self, study_id: str, domain: str) -> dict[str, Any]:
        """
        Pull one SDTM domain dataset and return it in CDISC Dataset-JSON v1.1
        format.

        Dataset-JSON v1.1 envelope:
            {
              "datasetJSONCreationDateTime": "<ISO-8601>",
              "datasetJSONVersion": "1.0",
              "fileOID": "<oid>",
              "originator": "<system>",
              "sourceSystem": "<edc_name>",
              "studyOID": "<study_id>",
              "metaDataVersionOID": "1",
              "itemGroupOID": "<domain>",
              "records": <int>,
              "columns": [{"itemOID": ..., "name": ..., "dataType": ..., "length": ...}],
              "rows": [[val, val, ...], ...]
            }

        Args:
            study_id: EDC-native study / project identifier.
            domain:   SDTM domain abbreviation (e.g. ``"DM"``).

        Returns:
            Dataset-JSON v1.1 dict.
        """

    # ── Convenience ────────────────────────────────────────────────────────

    def _require_auth(self) -> None:
        """Raise RuntimeError if authenticate() has not been called."""
        if not self._authenticated:
            raise RuntimeError(
                f"{self.__class__.__name__}.authenticate() must be called before "
                "making data requests."
            )

    @staticmethod
    def _iso_now() -> str:
        """Return the current UTC datetime in ISO-8601 format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
