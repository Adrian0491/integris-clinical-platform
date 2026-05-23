# EDC Connector Layer — Integris Clinical Platform

Abstract connector layer for importing clinical trial datasets from
Electronic Data Capture (EDC) systems into the Integris validation platform.

All connectors convert source data to **CDISC Dataset-JSON v1.1** format
before handing off to the validation pipeline.

## Supported Systems

| System | Class | Status | Auth Method |
|---|---|---|---|
| REDCap | `REDCapConnector` | Implemented | API token |
| Medidata Rave | `MedidataRaveConnector` | Stubbed | OAuth2 client credentials |
| Veeva Vault CDM | `VeevaVaultConnector` | Stubbed | Session (username/password) |
| Oracle Clinical One | — | Planned (TODO-EDC-016) | OAuth2 |
| Generic FHIR R4 | — | Planned (TODO-EDC-017) | Bearer token |

**Implemented** = authenticate + list_studies + pull_dataset fully working  
**Stubbed** = class skeleton + docstrings; all methods raise `NotImplementedError`  
**Planned** = not yet started

## Architecture

```
EDCConnectionConfig  ──►  EDCConnectorFactory.create()  ──►  EDCConnector
                                                                   │
                          ┌────────────────────────────────────────┤
                          │                                        │
                   REDCapConnector               MedidataRaveConnector
                   VeevaVaultConnector           (future: OracleC1, FHIR)
```

Each connector implements the abstract `EDCConnector` interface:

```python
async def authenticate()                         -> bool
async def list_studies()                         -> list[dict]
async def get_study_metadata(study_id)           -> dict
async def pull_dataset(study_id, domain)         -> dict  # Dataset-JSON v1.1
async def list_domains(study_id)                 -> list[str]
async def get_subjects(study_id)                 -> list[dict]
```

## Adding a New Connector

1. Create `backend/app/services/edc/<system_name>.py`
2. Subclass `EDCConnector` from `base.py`
3. Implement all six abstract methods
4. Add the new `EDCSystemType` enum value in `base.py`
5. Register the connector in `factory.py` (`EDCConnectorFactory.create`)
6. Add unit tests in `tests/test_edc.py`
7. Update the supported systems table above

Minimum skeleton:

```python
from app.services.edc.base import EDCConnectionConfig, EDCConnector

class MyEDCConnector(EDCConnector):
    def __init__(self, config: EDCConnectionConfig) -> None:
        super().__init__(config)

    async def authenticate(self) -> bool:
        # ... call remote auth endpoint ...
        self._authenticated = True
        return True

    async def pull_dataset(self, study_id: str, domain: str) -> dict:
        self._require_auth()
        # ... fetch + convert to Dataset-JSON v1.1 ...
        return {
            "datasetJSONVersion": "1.0",
            "sourceSystem": "MyEDC",
            "studyOID": study_id,
            "itemGroupOID": f"IG.{domain.upper()}",
            "records": 0,
            "columns": [],
            "rows": [],
            # ... other required fields ...
        }
```

## API Endpoints

All endpoints require `ROLE_TENANT_ADMIN`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/edc/connect` | Configure + test EDC connection |
| `GET` | `/api/v1/edc/studies` | List studies from connected EDC |
| `POST` | `/api/v1/edc/import/{study_id}` | Import datasets + trigger validation |
| `GET` | `/api/v1/edc/status` | Connection status for current tenant |

## Example Import Workflow

```bash
# 1. Connect to REDCap
curl -X POST /api/v1/edc/connect \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "system_type": "redcap",
    "base_url": "https://redcap.yourorg.org",
    "api_key": "YOUR_REDCAP_API_TOKEN"
  }'

# 2. List available studies/projects
curl -X GET /api/v1/edc/studies \
  -H "Authorization: Bearer $TOKEN"

# 3. Import datasets for a study (triggers CDISC validation automatically)
curl -X POST /api/v1/edc/import/STUDY-001 \
  -H "Authorization: Bearer $TOKEN"

# 4. Poll validation job status
curl -X GET /api/v1/validation/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"
```

## Outstanding TODOs

| ID | Description |
|---|---|
| TODO-EDC-001 | Connection pooling and session reuse |
| TODO-EDC-002 | Webhook support for real-time EDC push |
| TODO-EDC-003 | Medidata Rave: complete OAuth2 token exchange |
| TODO-EDC-004 | Medidata Rave: implement list_studies() |
| TODO-EDC-005 | Medidata Rave: implement get_study_metadata() |
| TODO-EDC-006 | Medidata Rave: implement list_domains() |
| TODO-EDC-007 | Medidata Rave: implement get_subjects() |
| TODO-EDC-008 | Medidata Rave: implement pull_dataset() |
| TODO-EDC-009 | REDCap: SDTM field-type mapping table |
| TODO-EDC-010 | REDCap: longitudinal study (events/arms) support |
| TODO-EDC-011 | Veeva Vault: implement authenticate() |
| TODO-EDC-012 | Veeva Vault: implement list_studies() via VQL |
| TODO-EDC-013 | Veeva Vault: implement get_study_metadata() |
| TODO-EDC-014 | Veeva Vault: implement list_domains() + get_subjects() |
| TODO-EDC-015 | Veeva Vault: implement pull_dataset() |
| TODO-EDC-016 | Oracle Clinical One connector |
| TODO-EDC-017 | Generic FHIR R4 connector |
| TODO-EDC-018 | Encrypt EDC credentials at rest with GCP KMS |
| TODO-EDC-019 | Scheduled EDC sync via Celery |
| TODO-EDC-020 | EDC connection audit trail |
| TODO-EDC-021 | Integration tests against REDCap sandbox |
