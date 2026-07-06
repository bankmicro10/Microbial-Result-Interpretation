"""Tests สำหรับ I/O layer — parser + end-to-end round-trip"""
import pandas as pd
import pytest
from io_layer import parse_dilution, parse_count, _base_lab, read_input, process, write_output, TNTC


@pytest.mark.parametrize("s,expected", [
    ("0.1", 0.1), ("1:10", 0.1), ("1:100", 0.01),
    ("10^-2", 0.01), ("10-3", 0.001), ("x10", 0.1), ("x100", 0.01),
])
def test_parse_dilution(s, expected):
    assert parse_dilution(s) == pytest.approx(expected)


@pytest.mark.parametrize("s,expected", [
    ("135", 135), ("0", 0), ("TNTC", TNTC), ("-", None), ("N", 0), ("", None),
])
def test_parse_count(s, expected):
    assert parse_count(s) == expected


@pytest.mark.parametrize("lab,base,rep", [
    ("GEN-9/1 No.1", "GEN-9/1", 1),
    ("GEN-9/1 No.2", "GEN-9/1", 2),
    ("EL26-001234/11N0.1", "EL26-001234/11", 1),   # ไม่มีเว้นวรรค
    ("EL26-001234/11 N0.2", "EL26-001234/11", 2),  # มีเว้นวรรค → base เดียวกัน
    ("EL26-001234/1 no1", "EL26-001234/1", 1),     # case-insensitive
    ("EL26-001234/1 NO.2", "EL26-001234/1", 2),
    ("EL26-00123/1", "EL26-00123/1", 1),           # ไม่มี suffix
])
def test_base_lab(lab, base, rep):
    assert _base_lab(lab) == (base, rep)


def test_end_to_end_roundtrip(tmp_path):
    inp = pd.DataFrame([
        ("ISO-1/1", "APC", "10^-2", "135"), ("ISO-1/1", "APC", "10^-3", "14"),
        ("GEN-9/1 No.1", "E_coli", "0.1", "15"), ("GEN-9/1 No.1", "E_coli", "0.01", "4"),
        ("GEN-9/1 No.2", "E_coli", "0.1", "16"), ("GEN-9/1 No.2", "E_coli", "0.01", "4"),
    ], columns=["lab_code", "analyte", "dilution", "count"])

    f_iso = tmp_path / "in_iso.xlsx"
    inp.iloc[:2].to_excel(f_iso, index=False)
    out = process(read_input(str(f_iso)), "ISO7218")
    f_out = tmp_path / "out_iso.xlsx"
    write_output(out, str(f_out))
    back = read_input(str(f_out))
    # scientific string ต้องไม่ถูกแปลงเป็น float ตอน round-trip
    assert back.loc[0, "result"] == "1.4E+04"
    assert str(back.loc[0, "calculated"]) == "13500"

    f_gen = tmp_path / "in_gen.xlsx"
    inp.iloc[2:].to_excel(f_gen, index=False)
    outg = process(read_input(str(f_gen)), "General")
    assert outg.iloc[0]["result"] == "1.6E+02"          # duplicate → max
    assert "duplicate=max" in outg.iloc[0]["remark"]
