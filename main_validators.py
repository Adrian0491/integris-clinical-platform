from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from bk.validator.domain import (
    validate_ae, validate_cm, validate_dm,
    validate_dm_link, validate_vs, validate_vs_ae, validate_vs_cm,
)
from bk.schemas import concat_findings, empty_findings


def rule_ids(findings: pd.DataFrame) -> set[str]:
    return set(findings["rule_id"].tolist())

def assert_clean(tc, findings, context=""):
    tc.assertEqual(len(findings), 0,
        f"Expected no findings{' for ' + context if context else ''}.\nGot:\n"
        + findings[["rule_id", "severity", "field", "message"]].to_string())


class TestDM(unittest.TestCase):
    VALID = pd.DataFrame([{"STUDYID": "S001", "USUBJID": "S001-001",
        "SEX": "M", "AGE": 34, "AGEU": "YEARS",
        "RFSTDTC": "2025-01-09", "RFENDTC": "2025-01-20"}])

    def test_valid_no_findings(self):
        assert_clean(self, validate_dm(self.VALID))

    def test_empty_usubjid(self):
        df = self.VALID.copy(); df["USUBJID"] = ""
        self.assertIn("SDTM_DM_001", rule_ids(validate_dm(df)))

    def test_null_usubjid(self):
        df = self.VALID.copy(); df["USUBJID"] = None
        self.assertIn("SDTM_DM_001", rule_ids(validate_dm(df)))

    def test_duplicate_usubjid(self):
        df = pd.concat([self.VALID, self.VALID], ignore_index=True)
        self.assertIn("SDTM_DM_002", rule_ids(validate_dm(df)))

    def test_invalid_sex(self):
        df = self.VALID.copy(); df["SEX"] = "X"
        self.assertIn("SDTM_DM_003", rule_ids(validate_dm(df)))

    def test_age_too_high(self):
        df = self.VALID.copy(); df["AGE"] = 150
        self.assertIn("SDTM_DM_004", rule_ids(validate_dm(df)))

    def test_age_negative(self):
        df = self.VALID.copy(); df["AGE"] = -1
        self.assertIn("SDTM_DM_004", rule_ids(validate_dm(df)))

    def test_rfstdtc_after_rfendtc(self):
        df = self.VALID.copy(); df["RFSTDTC"] = "2025-01-20"; df["RFENDTC"] = "2025-01-09"
        self.assertIn("SDTM_DM_008", rule_ids(validate_dm(df)))

    def test_bad_date_format(self):
        df = self.VALID.copy(); df["RFSTDTC"] = "2025-01-xx"
        self.assertIn("SDTM_DM_006", rule_ids(validate_dm(df)))

    def test_missing_required_column_is_crit(self):
        df = self.VALID.drop(columns=["USUBJID"])
        f = validate_dm(df)
        self.assertEqual(f["severity"].iloc[0], "CRIT")

    def test_invalid_ageu(self):
        df = self.VALID.copy(); df["AGEU"] = "DECADES"
        self.assertIn("SDTM_DM_005", rule_ids(validate_dm(df)))


class TestVS(unittest.TestCase):
    VALID = pd.DataFrame([{"USUBJID": "S001-001", "VSTESTCD": "SYSBP",
        "VSORRES": "120", "VSORRESU": "mmHg", "VSDTC": "2025-01-10"}])

    def test_valid_no_findings(self):
        assert_clean(self, validate_vs(self.VALID))

    def test_missing_usubjid(self):
        df = self.VALID.copy(); df["USUBJID"] = None
        self.assertIn("SDTM_VS_001", rule_ids(validate_vs(df)))

    def test_unknown_testcd(self):
        df = self.VALID.copy(); df["VSTESTCD"] = "GLUCOSE"
        self.assertIn("SDTM_VS_002", rule_ids(validate_vs(df)))

    def test_non_numeric_result(self):
        df = self.VALID.copy(); df["VSORRES"] = "abc"
        self.assertIn("SDTM_VS_004", rule_ids(validate_vs(df)))

    def test_bad_date(self):
        df = self.VALID.copy(); df["VSDTC"] = "2025-13-01"
        self.assertIn("SDTM_VS_003", rule_ids(validate_vs(df)))

    def test_wrong_unit(self):
        df = self.VALID.copy(); df["VSORRESU"] = "kPa"
        self.assertIn("SDTM_VS_005", rule_ids(validate_vs(df)))

    def test_correct_hr_unit_passes(self):
        df = pd.DataFrame([{"USUBJID": "S-001", "VSTESTCD": "HR",
            "VSORRES": "72", "VSORRESU": "bpm", "VSDTC": "2025-01-10"}])
        self.assertNotIn("SDTM_VS_005", rule_ids(validate_vs(df)))

    def test_no_vsorresu_gives_low_finding(self):
        df = self.VALID.drop(columns=["VSORRESU"])
        f = validate_vs(df)
        match = f[f["rule_id"] == "SDTM_VS_005"]
        self.assertGreater(len(match), 0)
        self.assertEqual(match["severity"].iloc[0], "LOW")


class TestAE(unittest.TestCase):
    VALID = pd.DataFrame([{"USUBJID": "S001-001", "AETERM": "Headache",
        "AESTDTC": "2025-01-12", "AEENDTC": "2025-01-13",
        "AESER": "N", "AESEV": "MILD"}])

    def test_valid_no_findings(self):
        assert_clean(self, validate_ae(self.VALID))

    def test_missing_aeterm(self):
        df = self.VALID.copy(); df["AETERM"] = ""
        self.assertIn("SDTM_AE_001", rule_ids(validate_ae(df)))

    def test_end_before_start(self):
        df = self.VALID.copy(); df["AESTDTC"] = "2025-01-13"; df["AEENDTC"] = "2025-01-12"
        self.assertIn("SDTM_AE_004", rule_ids(validate_ae(df)))

    def test_invalid_aeser(self):
        df = self.VALID.copy(); df["AESER"] = "Maybe"
        self.assertIn("SDTM_AE_005", rule_ids(validate_ae(df)))

    def test_invalid_aesev(self):
        df = self.VALID.copy(); df["AESEV"] = "LOW"
        self.assertIn("SDTM_AE_006", rule_ids(validate_ae(df)))

    def test_bad_start_date(self):
        df = self.VALID.copy(); df["AESTDTC"] = "2025-01-xx"
        self.assertIn("SDTM_AE_002", rule_ids(validate_ae(df)))


class TestCM(unittest.TestCase):
    VALID = pd.DataFrame([{"USUBJID": "S001-001", "CMTRT": "Ibuprofen",
        "CMSTDTC": "2025-01-10", "CMENDTC": "2025-01-12"}])

    def test_valid_no_findings(self):
        assert_clean(self, validate_cm(self.VALID))

    def test_missing_cmtrt(self):
        df = self.VALID.copy(); df["CMTRT"] = None
        self.assertIn("SDTM_CM_001", rule_ids(validate_cm(df)))

    def test_end_before_start(self):
        df = self.VALID.copy(); df["CMSTDTC"] = "2025-01-18"; df["CMENDTC"] = "2025-01-16"
        self.assertIn("SDTM_CM_004", rule_ids(validate_cm(df)))

    def test_bad_start_date(self):
        df = self.VALID.copy(); df["CMSTDTC"] = "2025-01-xx"
        self.assertIn("SDTM_CM_002", rule_ids(validate_cm(df)))


class TestCrossDomain(unittest.TestCase):
    DM = pd.DataFrame([
        {"USUBJID": "S001-001", "STUDYID": "S001"},
        {"USUBJID": "S001-002", "STUDYID": "S001"},
    ])
    VS = pd.DataFrame([
        {"USUBJID": "S001-001", "VSTESTCD": "SYSBP", "VSORRES": "120", "VSDTC": "2025-01-10"},
        {"USUBJID": "S001-002", "VSTESTCD": "HR",    "VSORRES": "72",  "VSDTC": "2025-01-09"},
    ])
    AE = pd.DataFrame([
        {"USUBJID": "S001-001", "AETERM": "Headache", "AESTDTC": "2025-01-10"},
    ])
    CM = pd.DataFrame([
        {"USUBJID": "S001-001", "CMTRT": "Ibuprofen",
         "CMSTDTC": "2025-01-10", "CMENDTC": "2025-01-12"},
    ])

    def test_dm_link_clean(self):
        assert_clean(self, validate_dm_link(self.DM, self.VS, "VS"))

    def test_dm_link_orphan(self):
        orphan = pd.DataFrame([{"USUBJID": "S001-999", "AETERM": "Rash", "AESTDTC": "2025-01-12"}])
        self.assertIn("X_DMLINK_AE_001", rule_ids(validate_dm_link(self.DM, orphan, "AE")))

    def test_vs_ae_no_orphan(self):
        self.assertNotIn("X_VSAE_001", rule_ids(validate_vs_ae(self.VS, self.AE)))

    def test_vs_ae_orphan_detected(self):
        orphan = pd.DataFrame([{"USUBJID": "S001-999", "AETERM": "Rash", "AESTDTC": "2025-01-12"}])
        self.assertIn("X_VSAE_001", rule_ids(validate_vs_ae(self.VS, orphan)))

    def test_vs_cm_no_orphan(self):
        self.assertNotIn("X_VSCM_001", rule_ids(validate_vs_cm(self.VS, self.CM)))

    def test_vs_cm_orphan_detected(self):
        orphan = pd.DataFrame([{"USUBJID": "S001-888", "CMTRT": "Aspirin",
            "CMSTDTC": "2025-01-11", "CMENDTC": "2025-01-12"}])
        self.assertIn("X_VSCM_001", rule_ids(validate_vs_cm(self.VS, orphan)))


class TestMockData(unittest.TestCase):
    MOCK_DIR = Path(__file__).parent / "mock_data"

    def setUp(self):
        if not self.MOCK_DIR.exists():
            self.skipTest("mock_data directory not found")

    def _load(self, name):
        return pd.read_csv(self.MOCK_DIR / f"{name}.csv")

    def test_full_pipeline_runs_and_produces_findings(self):
        dm, vs, ae, cm = self._load("dm"), self._load("vs"), self._load("ae"), self._load("cm")
        findings = concat_findings([
            validate_dm(dm), validate_vs(vs), validate_ae(ae), validate_cm(cm),
            validate_dm_link(dm, vs, "VS"), validate_dm_link(dm, ae, "AE"), validate_dm_link(dm, cm, "CM"),
            validate_vs_ae(vs, ae), validate_vs_cm(vs, cm),
        ])
        self.assertIsInstance(findings, pd.DataFrame)
        self.assertTrue({"rule_id", "severity", "domain", "message"}.issubset(set(findings.columns)))
        self.assertGreater(len(findings), 0)

    def test_known_dm_errors(self):
        ids = rule_ids(validate_dm(self._load("dm")))
        self.assertIn("SDTM_DM_001", ids)   # empty USUBJID
        self.assertIn("SDTM_DM_002", ids)   # duplicate USUBJID
        self.assertIn("SDTM_DM_003", ids)   # invalid SEX=X
        self.assertIn("SDTM_DM_004", ids)   # AGE=150

    def test_known_ae_errors(self):
        ids = rule_ids(validate_ae(self._load("ae")))
        self.assertIn("SDTM_AE_001", ids)   # empty AETERM
        self.assertIn("SDTM_AE_004", ids)   # end before start

    def test_known_vs_errors(self):
        ids = rule_ids(validate_vs(self._load("vs")))
        self.assertIn("SDTM_VS_004", ids)   # non-numeric VSORRES
        self.assertIn("SDTM_VS_002", ids)   # unknown TESTCD (GLUCOSE)

    def test_orphan_subjects_detected(self):
        dm, ae, cm = self._load("dm"), self._load("ae"), self._load("cm")
        self.assertIn("X_DMLINK_AE_001", rule_ids(validate_dm_link(dm, ae, "AE")))
        self.assertIn("X_DMLINK_CM_001", rule_ids(validate_dm_link(dm, cm, "CM")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
