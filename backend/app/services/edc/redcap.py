"""
Integris Clinical Platform — REDCap EDC Connector
==================================================
Implements ``EDCConnector`` for REDCap using the REDCap API.

REDCap API reference:
  https://YOUR_REDCAP_URL/api/help/  (available on every REDCap instance)

Authentication:
  REDCap uses simple token-based authentication.  The API token is passed
  as a POST parameter ``token`` on every request.  There is no OAuth2 flow;
  ``authenticate()`` verifies the token by calling the ``version`` endpoint.

Implemented methods:
  authenticate()   — fully implemented (token validation)
  list_studies()   — fully implemented (export_projects API call)
  pull_dataset()   — fully implemented (export_records + export_metadata,
                     converts to Dataset-JSON v1.1)

Stubbed methods (see TODO-EDC-* comments):
  get_study_metadata()  — TODO-EDC-009
  list_domains()        — TODO-EDC-009
  get_subjects()        — TODO-EDC-009

NOTE: The REDCap API is synchronous HTTP.  ``requests`` is used as specified.
      This means the calls block the event loop; in a high-throughput
      deployment, wrap calls in ``asyncio.get_event_loop().run_in_executor()``
      (see TODO-EDC-001 in base.py for the connection-pooling work item).

TODO-EDC-009: Map REDCap field types to CDISC SDTM domains automatically.
              REDCap has no native SDTM concept; implement a configurable
              field-to-domain mapping table (stored per tenant/project) so
              the platform can route records to the correct SDTM domain
              (DM, VS, AE, etc.) based on form name or variable prefix.

TODO-EDC-010: Add REDCap longitudinal study support (events/arms).
              REDCap longitudinal projects have events and arms.  Extend
              pull_dataset() to accept an optional ``event_name`` parameter
              and filter export_records by event.  Use export_events and
              export_arms API calls to enumerate available events.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.edc.base import EDCConnectionConfig, EDCConnector

log = logging.getLogger(__name__)

# REDCap API returns/accepts these content types
_REDCAP_JSON = "json"
_REDCAP_CSV  = "csv"

# Request timeout (seconds) for all REDCap API calls
_TIMEOUT = 30


class REDCapConnector(EDCConnector):
    """
    Connector for REDCap using the REDCap API (token-based).

    Configuration:
        config.base_url  — Base URL of the REDCap instance,
                           e.g. ``"https://redcap.example.org"``
        config.api_key   — REDCap API token (project-level or super-token)
        config.tenant_id — Platform tenant UUID

    The API endpoint is ``{base_url}/api/``.
    """

    def __init__(self, config: EDCConnectionConfig) -> None:
        super().__init__(config)
        self._api_endpoint = config.base_url.rstrip("/") + "/api/"
        self._session = requests.Session()
        self._redcap_version: str | None = None

    # ── Internal helper ────────────────────────────────────────────────────

    def _post(self, **payload: Any) -> requests.Response:
        """
        POST to the REDCap API endpoint with the configured token.
        Injects ``token`` and ``format=json`` automatically.
        Raises ``requests.HTTPError`` on non-2xx responses.
        """
        data = {
            "token":  self.config.api_key,
            "format": _REDCAP_JSON,
            **payload,
        }
        resp = self._session.post(self._api_endpoint, data=data, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp

    # ── Authentication ─────────────────────────────────────────────────────

    async def authenticate(self) -> bool:
        """
        Validate the REDCap API token by fetching the REDCap version number.

        REDCap API call:
            POST {base_url}/api/
            content=version

        Returns:
            ``True`` if the token is valid and the server responds.

        Raises:
            ``requests.HTTPError`` if authentication fails (401/403).
            ``ConnectionError`` if the server is unreachable.
        """
        try:
            resp = self._post(content="version")
            self._redcap_version = resp.text.strip()
            self._authenticated = True
            log.info(
                "REDCapConnector authenticated against %s (REDCap v%s)",
                self.config.base_url,
                self._redcap_version,
            )
            return True
        except requests.HTTPError as exc:
            log.error("REDCap authentication failed: %s", exc)
            self._authenticated = False
            raise
        except requests.ConnectionError as exc:
            log.error("REDCap server unreachable at %s: %s", self.config.base_url, exc)
            self._authenticated = False
            raise

    # ── Study / project listing ────────────────────────────────────────────

    async def list_studies(self) -> list[dict[str, Any]]:
        """
        Return metadata for all REDCap projects the token can access.

        REDCap API call:
            POST {base_url}/api/
            content=project

        Each returned dict contains:
            ``study_id``   (str)  — REDCap project_id
            ``title``      (str)  — project_title
            ``status``     (str)  — "active" | "completed" | "inactive"
            ``purpose``    (str)  — project purpose description
            ``created``    (str)  — creation_time

        Note: A standard REDCap token is scoped to a single project.
              This method returns a one-element list unless a super-token
              with cross-project access is provided.
        """
        self._require_auth()
        try:
            resp = self._post(content="project")
            project = resp.json()
            if isinstance(project, dict):
                projects = [project]
            else:
                projects = project  # super-token may return a list

            return [
                {
                    "study_id": str(p.get("project_id", "")),
                    "title":    p.get("project_title", ""),
                    "status":   "active" if p.get("is_longitudinal") is not None else "unknown",
                    "purpose":  p.get("purpose_other", p.get("purpose", "")),
                    "created":  p.get("creation_time", ""),
                    "raw":      p,
                }
                for p in projects
            ]
        except requests.HTTPError as exc:
            log.error("REDCap list_studies failed: %s", exc)
            raise

    async def get_study_metadata(self, study_id: str) -> dict[str, Any]:
        """
        Return project-level metadata for the given REDCap project ID.

        REDCap API call:
            POST {base_url}/api/
            content=project

        TODO-EDC-009: Extend to include arm/event structure for longitudinal
                      projects (export_arms + export_events API calls).
        """
        self._require_auth()
        try:
            resp = self._post(content="project")
            project = resp.json()
            if isinstance(project, list):
                # Super-token: filter by project_id
                matches = [p for p in project if str(p.get("project_id")) == str(study_id)]
                project = matches[0] if matches else {}

            return {
                "study_id":         str(project.get("project_id", study_id)),
                "title":            project.get("project_title", ""),
                "phase":            None,  # Not a CDISC concept in REDCap
                "sponsor":          project.get("project_pi_firstname", "") + " " +
                                    project.get("project_pi_lastname", ""),
                "protocol_id":      project.get("secondary_unique_field", ""),
                "therapeutic_area": None,
                "start_date":       project.get("creation_time", ""),
                "end_date":         None,
                "status":           "active",
                "raw":              project,
            }
        except requests.HTTPError as exc:
            log.error("REDCap get_study_metadata failed: %s", exc)
            raise

    async def list_domains(self, study_id: str) -> list[str]:
        """
        Infer SDTM domain names from REDCap form names.

        REDCap has no native SDTM domain concept; this method returns
        distinct form names from the project metadata as proxy domain names.

        REDCap API call:
            POST {base_url}/api/
            content=metadata

        TODO-EDC-009: Replace form-name heuristic with a configurable
                      field-to-domain mapping table.
        """
        self._require_auth()
        try:
            resp = self._post(content="metadata")
            fields: list[dict] = resp.json()
            forms = sorted({f.get("form_name", "UNKNOWN").upper() for f in fields})
            return forms
        except requests.HTTPError as exc:
            log.error("REDCap list_domains failed: %s", exc)
            raise

    async def get_subjects(self, study_id: str) -> list[dict[str, Any]]:
        """
        Return a list of REDCap record IDs (subject proxies).

        REDCap API call:
            POST {base_url}/api/
            content=record, fields=record_id

        Returns dicts with ``usubjid`` set to the REDCap record ID.

        TODO-EDC-009: Map REDCap record_id to USUBJID using the project's
                      USUBJID field if configured.
        """
        self._require_auth()
        try:
            resp = self._post(content="record", fields="record_id")
            records: list[dict] = resp.json()
            return [
                {"usubjid": str(r.get("record_id", "")), "siteid": "", "raw": r}
                for r in records
            ]
        except requests.HTTPError as exc:
            log.error("REDCap get_subjects failed: %s", exc)
            raise

    # ── Dataset extraction + Dataset-JSON conversion ───────────────────────

    async def pull_dataset(self, study_id: str, domain: str) -> dict[str, Any]:
        """
        Export REDCap records and metadata, then convert to CDISC Dataset-JSON
        v1.1 format.

        Steps:
        1. Export field metadata (``content=metadata``) to build column
           definitions.
        2. Export all records for the project (``content=record``).
        3. Filter records to the form matching ``domain`` (case-insensitive).
        4. Build the Dataset-JSON v1.1 envelope.

        REDCap API calls:
            POST {base_url}/api/ content=metadata
            POST {base_url}/api/ content=record  form=<domain_lower>

        TODO-EDC-009: Map REDCap field types to CDISC SDTM variables.
                      REDCap uses "text", "radio", "checkbox", "dropdown", etc.
                      Map these to CDISC datatypes: Char, Num, ISOdatetime.
        TODO-EDC-010: Add event/arm filtering for longitudinal studies.
        """
        self._require_auth()

        domain_lower = domain.lower()

        # ── Step 1: export metadata to build column definitions ──────────
        try:
            meta_resp = self._post(content="metadata")
            all_fields: list[dict] = meta_resp.json()
        except requests.HTTPError as exc:
            log.error("REDCap pull_dataset metadata export failed: %s", exc)
            raise

        # Filter to fields belonging to the requested form / domain
        domain_fields = [
            f for f in all_fields
            if f.get("form_name", "").lower() == domain_lower
        ]
        if not domain_fields:
            log.warning(
                "REDCap: no fields found for form %r in project %s",
                domain, study_id,
            )
            domain_fields = all_fields  # fall back to all fields

        columns = [
            {
                "itemOID":  f"IT.{domain.upper()}.{fld['field_name'].upper()}",
                "name":     fld["field_name"].upper(),
                "dataType": _redcap_type_to_cdisc(fld.get("field_type", "text")),
                "label":    fld.get("field_label", ""),
                "length":   _redcap_field_length(fld),
            }
            for fld in domain_fields
        ]

        col_names = [c["name"] for c in columns]

        # ── Step 2: export records ────────────────────────────────────────
        try:
            records_resp = self._post(
                content="record",
                forms=domain_lower,
                exportDataAccessGroups="false",
            )
            records: list[dict] = records_resp.json()
        except requests.HTTPError as exc:
            log.error("REDCap pull_dataset record export failed: %s", exc)
            raise

        # ── Step 3: convert to Dataset-JSON v1.1 row arrays ──────────────
        rows = [
            [str(rec.get(col_name.lower(), "")) for col_name in col_names]
            for rec in records
        ]

        # ── Step 4: assemble Dataset-JSON v1.1 envelope ──────────────────
        return {
            "datasetJSONCreationDateTime": self._iso_now(),
            "datasetJSONVersion": "1.0",
            "fileOID":            f"REDCap.{study_id}.{domain.upper()}",
            "originator":         "Integris Clinical Platform",
            "sourceSystem":       "REDCap",
            "sourceSystemVersion": self._redcap_version or "unknown",
            "studyOID":           study_id,
            "metaDataVersionOID": "1",
            "itemGroupOID":       f"IG.{domain.upper()}",
            "records":            len(rows),
            "columns":            columns,
            "rows":               rows,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _redcap_type_to_cdisc(field_type: str) -> str:
    """
    Map a REDCap field_type to a CDISC Dataset-JSON dataType string.

    TODO-EDC-009: Expand this mapping to cover all REDCap field types and
                  to inspect field_validation for date/datetime subtypes.
    """
    _MAPPING = {
        "text":        "string",
        "notes":       "string",
        "calc":        "float",
        "radio":       "string",
        "dropdown":    "string",
        "checkbox":    "string",
        "yesno":       "string",
        "truefalse":   "string",
        "slider":      "integer",
        "file":        "string",
        "descriptive": "string",
    }
    return _MAPPING.get(field_type.lower(), "string")


def _redcap_field_length(field_def: dict) -> int:
    """Return a sensible Dataset-JSON column length for a REDCap field."""
    ftype = field_def.get("field_type", "text")
    if ftype == "notes":
        return 4000
    if ftype == "calc":
        return 20
    return 200
