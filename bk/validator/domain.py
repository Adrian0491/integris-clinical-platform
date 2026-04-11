from __future__ import annotations

import pandas as pd

from bk.schemas import (
    VS_ALLOWED_TESTCD,
    VS_UNITS_BY_TESTCD,
    AE_ALLOWED_SER,
    AE_ALLOWED_SEV,
    DM_ALLOWED_SEX,
    DM_ALLOWED_AGEU,
    FINDINGS_COLUMNS,
    FINDINGS_DTYPES,
    concat_findings,
    dataset_finding,
    empty_findings,
)



# ============================================================================
# Demographics (DM)
# ============================================================================

def validate_dm(dm: pd.DataFrame) -> pd.DataFrame:
    findings: list[pd.DataFrame] = []

    crit = require_columns(dm, ["USUBJID", "STUDYID"], "DM", "SDTM_DM")
    if crit:
        return concat_findings(crit)

    dm_i = ensure_row_index(dm)
    dm_i["_USUBJID_S"] = dm_i["USUBJID"].fillna("").astype(str).str.strip()

    if "SEX"     in dm_i.columns: dm_i["_SEX_S"]    = dm_i["SEX"].fillna("").astype(str).str.strip()
    if "AGE"     in dm_i.columns: dm_i["_AGE_N"]    = pd.to_numeric(dm_i["AGE"], errors="coerce")
    if "AGEU"    in dm_i.columns: dm_i["_AGEU_S"]   = dm_i["AGEU"].fillna("").astype(str).str.strip()
    if "RFSTDTC" in dm_i.columns: dm_i["_RFSTDTC_D"] = parse_iso_date(dm_i["RFSTDTC"])
    if "RFENDTC" in dm_i.columns: dm_i["_RFENDTC_D"] = parse_iso_date(dm_i["RFENDTC"])

    # DM_001: USUBJID required non-empty
    findings.append(mk_findings(
        dm_i,
        dm_i["_USUBJID_S"].isin(["", "nan"]) | dm_i["USUBJID"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_DM_001", severity="HIGH", domain="DM",
        field="USUBJID", message="USUBJID is required and must be non-empty.",
        evidence_col="USUBJID",
    ))

    # DM_002: USUBJID must be unique in DM
    valid = dm_i[~(dm_i["_USUBJID_S"].isin(["", "nan"]) | dm_i["USUBJID"].isna())]
    dupes = valid[valid["_USUBJID_S"].duplicated(keep=False)]
    if len(dupes):
        findings.append(mk_findings(
            dupes, pd.Series(True, index=dupes.index),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_002", severity="HIGH", domain="DM",
            field="USUBJID", message="USUBJID must be unique in DM.",
            evidence_col="_USUBJID_S",
        ))

    # DM_003: SEX controlled terminology
    if "SEX" in dm_i.columns:
        findings.append(mk_findings(
            dm_i,
            dm_i["SEX"].notna() & ~dm_i["_SEX_S"].isin(DM_ALLOWED_SEX),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_003", severity="MED", domain="DM",
            field="SEX", message=f"SEX must be one of: {DM_ALLOWED_SEX}.",
            evidence_col="_SEX_S",
        ))

    # DM_004: AGE reasonable bounds
    if "AGE" in dm_i.columns:
        findings.append(mk_findings(
            dm_i,
            dm_i["_AGE_N"].notna() & ((dm_i["_AGE_N"] < 0) | (dm_i["_AGE_N"] > 120)),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_004", severity="MED", domain="DM",
            field="AGE", message="AGE should be between 0 and 120.",
            evidence_col="AGE",
        ))

    # DM_005: AGEU valid when AGE present
    if "AGE" in dm_i.columns and "AGEU" in dm_i.columns:
        findings.append(mk_findings(
            dm_i,
            dm_i["_AGE_N"].notna() & ~dm_i["_AGEU_S"].isin(DM_ALLOWED_AGEU),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_005", severity="LOW", domain="DM",
            field="AGEU", message=f"AGEU should be one of: {DM_ALLOWED_AGEU} when AGE is present.",
            evidence_col="_AGEU_S",
        ))

    # DM_006 / DM_007: date fields parseable
    if "RFSTDTC" in dm_i.columns:
        findings.append(mk_findings(
            dm_i, dm_i["RFSTDTC"].notna() & dm_i["_RFSTDTC_D"].isna(),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_006", severity="LOW", domain="DM",
            field="RFSTDTC", message="RFSTDTC should be ISO date YYYY-MM-DD.",
            evidence_col="RFSTDTC",
        ))
    if "RFENDTC" in dm_i.columns:
        findings.append(mk_findings(
            dm_i, dm_i["RFENDTC"].notna() & dm_i["_RFENDTC_D"].isna(),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_007", severity="LOW", domain="DM",
            field="RFENDTC", message="RFENDTC should be ISO date YYYY-MM-DD.",
            evidence_col="RFENDTC",
        ))

    # DM_008: RFSTDTC <= RFENDTC
    if "RFSTDTC" in dm_i.columns and "RFENDTC" in dm_i.columns:
        both = dm_i["_RFSTDTC_D"].notna() & dm_i["_RFENDTC_D"].notna()
        findings.append(mk_findings(
            dm_i,
            both & (dm_i["_RFSTDTC_D"] > dm_i["_RFENDTC_D"]),
            finding_type="SDTM_RULE", rule_id="SDTM_DM_008", severity="HIGH", domain="DM",
            field="RFSTDTC/RFENDTC", message="RFSTDTC must be on or before RFENDTC.",
            evidence_fn=lambda r: f"{r.get('RFSTDTC','')} > {r.get('RFENDTC','')}",
        ))

    return concat_findings(findings)


# ============================================================================
# Vital Signs (VS)
# ============================================================================

def validate_vs(vs: pd.DataFrame) -> pd.DataFrame:
    findings: list[pd.DataFrame] = []

    crit = require_columns(vs, ["USUBJID", "VSTESTCD", "VSORRES", "VSDTC"], "VS", "SDTM_VS")
    if crit:
        return concat_findings(crit)

    vs_i = ensure_row_index(vs)
    vs_i["_USUBJID_S"]  = vs_i["USUBJID"].fillna("").astype(str).str.strip()
    vs_i["_VSTESTCD_S"] = vs_i["VSTESTCD"].fillna("").astype(str).str.strip()
    vs_i["_VSORRES_S"]  = vs_i["VSORRES"].fillna("").astype(str)
    vs_i["_VSDTC_D"]   = parse_iso_date(vs_i["VSDTC"])
    vs_i["_VSORRES_N"]  = pd.to_numeric(
        vs_i["_VSORRES_S"].str.replace(",", ".", regex=False), errors="coerce"
    )

    # VS_001: USUBJID required
    findings.append(mk_findings(
        vs_i,
        vs_i["_USUBJID_S"].isin(["", "nan"]) | vs_i["USUBJID"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_VS_001", severity="HIGH", domain="VS",
        field="USUBJID", message="USUBJID is required and must be non-empty.",
        evidence_col="USUBJID",
    ))

    # VS_002: VSTESTCD allowed set
    findings.append(mk_findings(
        vs_i,
        vs_i["VSTESTCD"].notna() & ~vs_i["_VSTESTCD_S"].isin(VS_ALLOWED_TESTCD),
        finding_type="SDTM_RULE", rule_id="SDTM_VS_002", severity="MED", domain="VS",
        field="VSTESTCD", message=f"VSTESTCD should be one of: {VS_ALLOWED_TESTCD}.",
        evidence_col="_VSTESTCD_S",
    ))

    # VS_003: VSDTC parseable
    findings.append(mk_findings(
        vs_i,
        vs_i["VSDTC"].notna() & vs_i["_VSDTC_D"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_VS_003", severity="LOW", domain="VS",
        field="VSDTC", message="VSDTC should be ISO date YYYY-MM-DD.",
        evidence_col="VSDTC",
    ))

    # VS_004: Numeric result for numeric tests
    findings.append(mk_findings(
        vs_i,
        vs_i["_VSTESTCD_S"].isin(VS_ALLOWED_TESTCD)
        & vs_i["VSORRES"].notna()
        & vs_i["_VSORRES_N"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_VS_004", severity="HIGH", domain="VS",
        field="VSORRES", message="VSORRES should be numeric for this VSTESTCD.",
        evidence_col="_VSORRES_S",
    ))

    # VS_005: Units consistency
    if "VSORRESU" in vs_i.columns:
        vs_i["_VSORRESU_S"] = vs_i["VSORRESU"].fillna("").astype(str).str.strip()
        valid_pairs: set[tuple] = {
            (tc, u) for tc, units in VS_UNITS_BY_TESTCD.items() for u in units
        }
        known_testcds = set(VS_UNITS_BY_TESTCD.keys())
        bad_mask = (
            vs_i["_VSTESTCD_S"].isin(known_testcds)
            & vs_i["VSORRESU"].notna()
            & vs_i.apply(
                lambda r: (r["_VSTESTCD_S"], r["_VSORRESU_S"]) not in valid_pairs, axis=1
            )
        )
        findings.append(mk_findings(
            vs_i, bad_mask,
            finding_type="SDTM_RULE", rule_id="SDTM_VS_005", severity="MED", domain="VS",
            field="VSORRESU", message="VSORRESU unit is not consistent with VSTESTCD.",
            evidence_fn=lambda r: f"{r['_VSTESTCD_S']} / {r['_VSORRESU_S']}",
        ))
    else:
        findings.append(dataset_finding(
            rule_id="SDTM_VS_005", severity="LOW", domain="VS", field="VSORRESU",
            message="Column VSORRESU not present; unit consistency checks skipped.",
        ))

    return concat_findings(findings)


# ============================================================================
# Adverse Events (AE)
# ============================================================================

def validate_ae(ae: pd.DataFrame) -> pd.DataFrame:
    findings: list[pd.DataFrame] = []

    crit = require_columns(ae, ["USUBJID", "AETERM", "AESTDTC"], "AE", "SDTM_AE")
    if crit:
        return concat_findings(crit)

    ae_i = ensure_row_index(ae)
    ae_i["_USUBJID_S"] = ae_i["USUBJID"].fillna("").astype(str).str.strip()
    ae_i["_AETERM_S"]  = ae_i["AETERM"].fillna("").astype(str).str.strip()
    ae_i["_AESTDTC_D"] = parse_iso_date(ae_i["AESTDTC"])
    if "AEENDTC" in ae_i.columns:
        ae_i["_AEENDTC_D"] = parse_iso_date(ae_i["AEENDTC"])

    # AE_001: AETERM required
    findings.append(mk_findings(
        ae_i,
        ae_i["_AETERM_S"].isin(["", "nan"]) | ae_i["AETERM"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_AE_001", severity="HIGH", domain="AE",
        field="AETERM", message="AETERM is required and must be non-empty.",
        evidence_col="AETERM",
    ))

    # AE_002: AESTDTC parseable
    findings.append(mk_findings(
        ae_i,
        ae_i["AESTDTC"].notna() & ae_i["_AESTDTC_D"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_AE_002", severity="MED", domain="AE",
        field="AESTDTC", message="AESTDTC should be ISO date YYYY-MM-DD.",
        evidence_col="AESTDTC",
    ))

    if "AEENDTC" in ae_i.columns:
        # AE_003: AEENDTC parseable
        findings.append(mk_findings(
            ae_i,
            ae_i["AEENDTC"].notna() & ae_i["_AEENDTC_D"].isna(),
            finding_type="SDTM_RULE", rule_id="SDTM_AE_003", severity="LOW", domain="AE",
            field="AEENDTC", message="AEENDTC should be ISO date YYYY-MM-DD.",
            evidence_col="AEENDTC",
        ))

        # AE_004: AESTDTC <= AEENDTC
        both = ae_i["_AESTDTC_D"].notna() & ae_i["_AEENDTC_D"].notna()
        findings.append(mk_findings(
            ae_i,
            both & (ae_i["_AESTDTC_D"] > ae_i["_AEENDTC_D"]),
            finding_type="SDTM_RULE", rule_id="SDTM_AE_004", severity="HIGH", domain="AE",
            field="AESTDTC/AEENDTC", message="AESTDTC must be on or before AEENDTC.",
            evidence_fn=lambda r: f"{r.get('AESTDTC','')} > {r.get('AEENDTC','')}",
        ))

    # AE_005: AESER controlled terminology
    if "AESER" in ae_i.columns:
        findings.append(mk_findings(
            ae_i,
            ae_i["AESER"].notna() & ~ae_i["AESER"].astype(str).isin(AE_ALLOWED_SER),
            finding_type="SDTM_RULE", rule_id="SDTM_AE_005", severity="MED", domain="AE",
            field="AESER", message=f"AESER should be one of: {AE_ALLOWED_SER}.",
            evidence_col="AESER",
        ))

    # AE_006: AESEV controlled terminology
    if "AESEV" in ae_i.columns:
        findings.append(mk_findings(
            ae_i,
            ae_i["AESEV"].notna() & ~ae_i["AESEV"].astype(str).isin(AE_ALLOWED_SEV),
            finding_type="SDTM_RULE", rule_id="SDTM_AE_006", severity="MED", domain="AE",
            field="AESEV", message=f"AESEV should be one of: {AE_ALLOWED_SEV}.",
            evidence_col="AESEV",
        ))

    return concat_findings(findings)


# ============================================================================
# Concomitant Medications (CM)
# ============================================================================

def validate_cm(cm: pd.DataFrame) -> pd.DataFrame:
    findings: list[pd.DataFrame] = []

    crit = require_columns(cm, ["USUBJID", "CMTRT", "CMSTDTC"], "CM", "SDTM_CM")
    if crit:
        return concat_findings(crit)

    cm_i = ensure_row_index(cm)
    cm_i["_USUBJID_S"] = cm_i["USUBJID"].fillna("").astype(str).str.strip()
    cm_i["_CMTRT_S"]   = cm_i["CMTRT"].fillna("").astype(str).str.strip()
    cm_i["_CMSTDTC_D"] = parse_iso_date(cm_i["CMSTDTC"])
    if "CMENDTC" in cm_i.columns:
        cm_i["_CMENDTC_D"] = parse_iso_date(cm_i["CMENDTC"])

    # CM_001: CMTRT required
    findings.append(mk_findings(
        cm_i,
        cm_i["_CMTRT_S"].isin(["", "nan"]) | cm_i["CMTRT"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_CM_001", severity="HIGH", domain="CM",
        field="CMTRT", message="CMTRT is required and must be non-empty.",
        evidence_col="CMTRT",
    ))

    # CM_002: CMSTDTC parseable
    findings.append(mk_findings(
        cm_i,
        cm_i["CMSTDTC"].notna() & cm_i["_CMSTDTC_D"].isna(),
        finding_type="SDTM_RULE", rule_id="SDTM_CM_002", severity="MED", domain="CM",
        field="CMSTDTC", message="CMSTDTC should be ISO date YYYY-MM-DD.",
        evidence_col="CMSTDTC",
    ))

    if "CMENDTC" in cm_i.columns:
        # CM_003: CMENDTC parseable
        findings.append(mk_findings(
            cm_i,
            cm_i["CMENDTC"].notna() & cm_i["_CMENDTC_D"].isna(),
            finding_type="SDTM_RULE", rule_id="SDTM_CM_003", severity="LOW", domain="CM",
            field="CMENDTC", message="CMENDTC should be ISO date YYYY-MM-DD.",
            evidence_col="CMENDTC",
        ))

        # CM_004: CMSTDTC <= CMENDTC
        both = cm_i["_CMSTDTC_D"].notna() & cm_i["_CMENDTC_D"].notna()
        findings.append(mk_findings(
            cm_i,
            both & (cm_i["_CMSTDTC_D"] > cm_i["_CMENDTC_D"]),
            finding_type="SDTM_RULE", rule_id="SDTM_CM_004", severity="HIGH", domain="CM",
            field="CMSTDTC/CMENDTC", message="CMSTDTC must be on or before CMENDTC.",
            evidence_fn=lambda r: f"{r.get('CMSTDTC','')} > {r.get('CMENDTC','')}",
        ))

    return concat_findings(findings)


# ============================================================================
# Cross-domain rules
# ============================================================================

def validate_dm_link(dm: pd.DataFrame, other: pd.DataFrame, other_domain: str) -> pd.DataFrame:
    """
    X_DMLINK_<DOMAIN>_001 (HIGH): every USUBJID in `other` must exist in DM.
    """
    if "USUBJID" not in dm.columns or "USUBJID" not in other.columns:
        return dataset_finding(
            rule_id=f"X_DMLINK_{other_domain}_000", severity="CRIT",
            domain="CROSS", field="USUBJID", finding_type="CROSS_DOMAIN",
            message=f"Missing USUBJID for DM/{other_domain} link check.",
        )

    dm_subjects = set(dm["USUBJID"].dropna().astype(str).str.strip())
    other_i = ensure_row_index(other)
    other_i["_USUBJID_S"] = other_i["USUBJID"].fillna("").astype(str).str.strip()
    orphans = other_i[~other_i["_USUBJID_S"].isin(dm_subjects) & (other_i["_USUBJID_S"] != "")]

    if len(orphans) == 0:
        return empty_findings()

    return mk_findings(
        orphans, pd.Series(True, index=orphans.index),
        finding_type="CROSS_DOMAIN", rule_id=f"X_DMLINK_{other_domain}_001",
        severity="HIGH", domain="CROSS", field="USUBJID",
        message=f"{other_domain} subject not found in DM (orphan USUBJID).",
        evidence_col="_USUBJID_S",
    )


def validate_vs_ae(vs: pd.DataFrame, ae: pd.DataFrame) -> pd.DataFrame:
    """
    VS ↔ AE cross-domain heuristics:
      X_VSAE_001: AE subjects must exist in VS
      X_VSAE_002: AE start date should not be outside the subject's VS date range
    """
    findings: list[pd.DataFrame] = []

    if any(c not in vs.columns for c in ["USUBJID", "VSDTC"]) or \
       any(c not in ae.columns for c in ["USUBJID", "AESTDTC"]):
        return dataset_finding(
            rule_id="X_VSAE_000", severity="CRIT", domain="CROSS",
            field="USUBJID/--DTC", finding_type="CROSS_DOMAIN",
            message="Missing required columns for VS/AE cross checks.",
        )

    vs_i = ensure_row_index(vs)
    vs_i["_USUBJID_S"] = vs_i["USUBJID"].fillna("").astype(str).str.strip()
    vs_i["_VSDTC_D"]   = parse_iso_date(vs_i["VSDTC"])

    ae_i = ensure_row_index(ae)
    ae_i["_USUBJID_S"]  = ae_i["USUBJID"].fillna("").astype(str).str.strip()
    ae_i["_AESTDTC_D"]  = parse_iso_date(ae_i["AESTDTC"])

    # X_VSAE_001: orphan AE subjects
    vs_subjects = set(vs_i["_USUBJID_S"].unique())
    orphans = ae_i[~ae_i["_USUBJID_S"].isin(vs_subjects) & (ae_i["_USUBJID_S"] != "")]
    if len(orphans):
        findings.append(mk_findings(
            orphans, pd.Series(True, index=orphans.index),
            finding_type="CROSS_DOMAIN", rule_id="X_VSAE_001",
            severity="HIGH", domain="CROSS", field="USUBJID",
            message="AE subject not found in VS (orphan USUBJID).",
            evidence_col="_USUBJID_S",
        ))

    # X_VSAE_002: AE start date outside VS date range per subject
    vs_range = (
        vs_i[vs_i["_VSDTC_D"].notna()]
        .groupby("_USUBJID_S")["_VSDTC_D"]
        .agg(VS_MIN="min", VS_MAX="max")
        .reset_index()
    )
    ae_dated = ae_i[ae_i["_AESTDTC_D"].notna()].merge(vs_range, on="_USUBJID_S", how="inner")
    out_of_range = ae_dated[
        (ae_dated["_AESTDTC_D"] < ae_dated["VS_MIN"]) |
        (ae_dated["_AESTDTC_D"] > ae_dated["VS_MAX"])
    ]
    if len(out_of_range):
        findings.append(mk_findings(
            out_of_range, pd.Series(True, index=out_of_range.index),
            finding_type="CROSS_DOMAIN", rule_id="X_VSAE_002",
            severity="MED", domain="CROSS", field="AESTDTC",
            message="AE start date is outside the subject's VS date range.",
            evidence_fn=lambda r: f"{r.get('AESTDTC','')} vs [{r['VS_MIN']}, {r['VS_MAX']}]",
        ))

    return concat_findings(findings)


def validate_vs_cm(vs: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    """
    VS ↔ CM cross-domain heuristics:
      X_VSCM_001: CM subjects must exist in VS
      X_VSCM_002: VS dates outside the subject's CM medication window
    """
    findings: list[pd.DataFrame] = []

    if any(c not in vs.columns for c in ["USUBJID", "VSDTC"]) or \
       any(c not in cm.columns for c in ["USUBJID", "CMSTDTC"]):
        return dataset_finding(
            rule_id="X_VSCM_000", severity="CRIT", domain="CROSS",
            field="USUBJID/--DTC", finding_type="CROSS_DOMAIN",
            message="Missing required columns for VS/CM cross checks.",
        )

    vs_i = ensure_row_index(vs)
    vs_i["_USUBJID_S"] = vs_i["USUBJID"].fillna("").astype(str).str.strip()
    vs_i["_VSDTC_D"]   = parse_iso_date(vs_i["VSDTC"])

    cm_i = ensure_row_index(cm)
    cm_i["_USUBJID_S"]  = cm_i["USUBJID"].fillna("").astype(str).str.strip()
    cm_i["_CMSTDTC_D"]  = parse_iso_date(cm_i["CMSTDTC"])
    if "CMENDTC" in cm_i.columns:
        cm_i["_CMENDTC_D"] = parse_iso_date(cm_i["CMENDTC"])

    # X_VSCM_001: orphan CM subjects
    vs_subjects = set(vs_i["_USUBJID_S"].unique())
    orphans = cm_i[~cm_i["_USUBJID_S"].isin(vs_subjects) & (cm_i["_USUBJID_S"] != "")]
    if len(orphans):
        findings.append(mk_findings(
            orphans, pd.Series(True, index=orphans.index),
            finding_type="CROSS_DOMAIN", rule_id="X_VSCM_001",
            severity="HIGH", domain="CROSS", field="USUBJID",
            message="CM subject not found in VS (orphan USUBJID).",
            evidence_col="_USUBJID_S",
        ))

    # X_VSCM_002: VS dates outside CM window
    if "CMENDTC" in cm_i.columns:
        cm_windows = (
            cm_i[cm_i["_CMSTDTC_D"].notna()]
            .groupby("_USUBJID_S")
            .agg(CM_MIN=("_CMSTDTC_D", "min"), CM_MAX=("_CMENDTC_D", "max"))
            .reset_index()
        )
        vs_dated = vs_i[vs_i["_VSDTC_D"].notna()].merge(cm_windows, on="_USUBJID_S", how="inner")
        out = vs_dated[
            vs_dated["CM_MAX"].notna() & (
                (vs_dated["_VSDTC_D"] < vs_dated["CM_MIN"]) |
                (vs_dated["_VSDTC_D"] > vs_dated["CM_MAX"])
            )
        ]
        if len(out):
            findings.append(mk_findings(
                out, pd.Series(True, index=out.index),
                finding_type="CROSS_DOMAIN", rule_id="X_VSCM_002",
                severity="LOW", domain="CROSS", field="VSDTC",
                message="VS date is outside the subject's CM medication window.",
                evidence_fn=lambda r: f"{r.get('VSDTC','')} vs [{r['CM_MIN']}, {r['CM_MAX']}]",
            ))

    return concat_findings(findings)
