"""Acceptance tests — 9 ตัวอย่างจากเอกสาร มาตรฐานการคำนวณ.docx"""
from interpretation_engine import (
    Reading, PlateSet, TNTC,
    interpret_iso, interpret_fda, interpret_general,
)

ISO = {"countable_range": [10, 150], "report_sig_figs": 2,
       "rounding": "half_up", "report_format": "auto"}
FDA = {"countable_range": [15, 300], "report_sig_figs": 2,
       "rounding": "bankers", "report_format": "plain_grouped"}
GEN = {"countable_range": [15, 150], "report_sig_figs": 2,
       "rounding": "bankers", "report_format": "scientific", "ratio_threshold": 2.0}


# ---- ISO 7218 ----
def test_case1_general():
    r = interpret_iso([Reading(0.01, 135), Reading(0.001, 14)], ISO)
    assert r.result == "1.4E+04"

def test_case2_estimate():
    r = interpret_iso([Reading(0.1, 8), Reading(0.01, 1)], ISO)
    assert r.result == "82 est."

def test_case3_low_1_3():
    r = interpret_iso([Reading(0.1, 2), Reading(0.01, 0)], ISO)
    assert r.result == "<40"

def test_case4_not_detected():
    r = interpret_iso([Reading(0.1, 0), Reading(0.01, 0)], ISO)
    assert r.result == "<10"

def test_case5_all_tntc():
    r = interpret_iso([Reading(0.01, TNTC), Reading(0.001, TNTC)], ISO)
    assert r.result == ">1.5E+05"

def test_case6_tntc_then_countable():
    r = interpret_iso([Reading(0.01, TNTC), Reading(0.001, 120)], ISO)
    assert r.result == "1.2E+05 est."


# ---- FDA BAM ----
def test_case7_fda_weighted_average():
    r = interpret_fda([PlateSet(0.01, [232, 244]), PlateSet(0.001, [33, 28])], FDA)
    assert r.result == "24,000"


# ---- General (3.General) ----
def test_case8_calculated_two_dilutions():
    r = interpret_general([[Reading(0.1, 125), Reading(0.01, 15)]], GEN)
    assert sorted(r.calculated) == [1250, 1500]
    assert r.result == "1.4E+03"
    assert r.remark == "Ratio = 1.2"

def test_case9_duplicate_max():
    no1 = [Reading(0.1, 15), Reading(0.01, 4)]
    no2 = [Reading(0.1, 16), Reading(0.01, 4)]
    r = interpret_general([no1, no2], GEN)
    assert r.result == "1.6E+02"


def test_general_tntc_then_out_of_range_est():
    # 0.1=TNTC, 0.01=450 → 450 นอกช่วง (ไม่ใช่ TNTC token) → est.
    r = interpret_general([[Reading(0.1, TNTC), Reading(0.01, 450)]], GEN)
    assert r.result == "4.5E+04 est."


def test_general_all_literal_tntc():
    # ทุก dilution TNTC → > (hi ÷ dilution ที่ dilute สุด) est. : 150/0.01 = 1.5E+04
    r = interpret_general([[Reading(0.1, TNTC), Reading(0.01, TNTC)]], GEN)
    assert r.result == ">1.5E+04 est."


def test_general_all_tntc_uses_most_dilute():
    # dilute สุด = 1e-05 → 150/1e-05 = 1.5E+07
    r = interpret_general([[Reading(0.001, TNTC), Reading(0.0001, TNTC), Reading(1e-05, TNTC)]], GEN)
    assert r.result == ">1.5E+07 est."


def test_general_all_tntc_range_300():
    # ขอบบน 300, dilute สุด 0.01 → 300/0.01 = 3.0E+04 (ตัวอย่างจาก requirement)
    std = dict(GEN); std["countable_range"] = [15, 300]
    r = interpret_general([[Reading(0.1, TNTC), Reading(0.01, TNTC)]], std)
    assert r.result == ">3.0E+04 est."


def test_general_not_found_ge100_scientific():
    # ไม่พบ, dilute สุดที่ทำ 0.01 → detection limit 1/0.01 = 100 ≥100 → scientific
    r = interpret_general([[Reading(0.01, 0), Reading(0.001, 0)]], GEN)
    assert r.result == "<1.0E+02 est."


def test_general_not_found_lt100_plain():
    # ไม่พบ, dilute สุด 0.1 → 1/0.1 = 10 (<100) → คงจำนวนเต็ม
    r = interpret_general([[Reading(0.1, 0), Reading(0.01, 0)]], GEN)
    assert r.result == "<10 est."


def test_general_value_1_to_99_plain():
    # 9,1 นอกช่วง → est. calc 90 → รายงานเป็นจำนวนเต็ม "90 est." ไม่ใช่ 9.0E+01
    r = interpret_general([[Reading(0.1, 9), Reading(0.01, 1)]], GEN)
    assert r.result == "90 est."


# ---- Duplicate ที่ทั้งคู่มี 2 dilution ในช่วง → คิด ratio รายตัว ----
def test_dup_both_ratio_lt2_max_avg():
    # N0.1 avg=1250 (ratio1.5), N0.2 avg=1400 (ratio1.33) → เอาเฉลี่ยมากสุด = 1400
    no1 = [Reading(0.1, 100), Reading(0.01, 15)]
    no2 = [Reading(0.1, 120), Reading(0.01, 16)]
    r = interpret_general([no1, no2], GEN)
    assert r.result == "1.4E+03"
    assert "duplicate=avg" in r.remark


def test_dup_both_ratio_gt2_max_calc():
    # N0.1 ratio2.5, N0.2 ratio2.08 (>2 ทั้งคู่) → calculated มากสุด = 2500
    no1 = [Reading(0.1, 100), Reading(0.01, 25)]
    no2 = [Reading(0.1, 120), Reading(0.01, 25)]
    r = interpret_general([no1, no2], GEN)
    assert r.result == "2.5E+03"
    assert "duplicate=max" in r.remark


def test_dup_one_ratio_lt2_uses_that_avg():
    # N0.1 ratio1.5(<2) avg1250, N0.2 ratio2.08(>2) → รายงานเฉลี่ยของ N0.1
    no1 = [Reading(0.1, 100), Reading(0.01, 15)]
    no2 = [Reading(0.1, 120), Reading(0.01, 25)]
    r = interpret_general([no1, no2], GEN)
    assert r.result == "1.2E+03"
    assert "duplicate=avg" in r.remark


def test_dup_mixed_uses_in_range_replicate():
    # N0.1 นอกช่วงทั้งคู่ (est.), N0.2 อยู่ในช่วงทั้งคู่ ratio1.0 → ยึด N0.2 = ค่าเฉลี่ย 1500
    no1 = [Reading(0.1, 151), Reading(0.01, 10)]   # ไม่มีในช่วง → est.
    no2 = [Reading(0.1, 150), Reading(0.01, 15)]   # ในช่วงทั้งคู่ ratio=1.0
    r = interpret_general([no1, no2], GEN)
    assert r.result == "1.5E+03"
    assert "duplicate=in-range" in r.remark
