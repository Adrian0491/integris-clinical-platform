"""
Integris Clinical Platform — EDC Connector Factory
===================================================
Returns the appropriate ``EDCConnector`` subclass based on the
``system_type`` field in an ``EDCConnectionConfig``.

Usage:
    config = EDCConnectionConfig(
        system_type=EDCSystemType.MEDIDATA_RAVE,
        base_url="https://your-org.mdsol.com",
        tenant_id="<uuid>",
        extra={"client_id": "...", "client_secret": "..."},
    )
    connector = EDCConnectorFactory.create(config)
    await connector.authenticate()

TODO-EDC-016: Add OracleClinicalOneConnector when implemented.
TODO-EDC-017: Add GenericFHIRConnector for FHIR R4-compatible EDC systems.
"""
from __future__ import annotations

from app.services.edc.base import EDCConnectionConfig, EDCConnector, EDCSystemType


class EDCConnectorFactory:
    """
    Static factory that maps ``EDCSystemType`` to the corresponding connector.
    """

    @staticmethod
    def create(config: EDCConnectionConfig) -> EDCConnector:
        """
        Instantiate and return the correct ``EDCConnector`` subclass.

        Args:
            config: Connection parameters, including ``system_type``.

        Returns:
            An uninitialised connector (``authenticate()`` not yet called).

        Raises:
            ValueError: If the ``system_type`` is not supported.
        """
        # Import connectors lazily to avoid circular imports and to keep
        # startup time low when a particular connector is not in use.
        if config.system_type == EDCSystemType.MEDIDATA_RAVE:
            from app.services.edc.medidata_rave import MedidataRaveConnector
            return MedidataRaveConnector(config)

        if config.system_type == EDCSystemType.REDCAP:
            from app.services.edc.redcap import REDCapConnector
            return REDCapConnector(config)

        if config.system_type == EDCSystemType.VEEVA_VAULT:
            from app.services.edc.veeva_vault import VeevaVaultConnector
            return VeevaVaultConnector(config)

        # TODO-EDC-016: Oracle Clinical One
        if config.system_type == EDCSystemType.ORACLE_CLINICAL_ONE:
            raise NotImplementedError(
                "Oracle Clinical One connector is not yet implemented.  "
                "See TODO-EDC-016."
            )

        # TODO-EDC-017: Generic FHIR R4
        if config.system_type == EDCSystemType.GENERIC_FHIR:
            raise NotImplementedError(
                "Generic FHIR R4 connector is not yet implemented.  "
                "See TODO-EDC-017."
            )

        raise ValueError(
            f"Unsupported EDC system type: {config.system_type!r}.  "
            f"Supported types: {[t.value for t in EDCSystemType]}"
        )
