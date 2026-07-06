"""
I/O layer (prototype) — อ่าน raw data (CSV/XLSX wide worksheet) → เรียก interpretation engine
→ เขียนผลกลับใน Calculated count / Results / Remark โดยคงเลย์เอาต์เดิม

Canonical schema (แก้ตำแหน่งคอลัมน์ผ่าน COLUMN_MAP ต่อ template ได้):
    lab_code | analyte | dilution | count | calculated | result | remark
Duplicate: lab_code ลงท้าย "No.1"/"No.2" ของ base เดียวกัน
"""
from __future__ import annotations
import re
import pandas as pd

from interpretation_engine import (
    Reading, PlateSet, TNTC,
    interpret_iso, interpret_fda, interpret_general, format_report,
)

# ---- standard configs (ตรงกับ method_config.yaml) ----
STANDARDS = {
    "ISO7218": {"label": "ISO 7218:2024", "countable_range": [10, 150], "report_sig_figs": 2,
                "rounding": "half_up", "report_format": "auto"},
    "FDA_BAM": {"label": "FDA BAM Chapter 3 (2026)", "countable_range": [15, 300], "report_sig_figs": 2,
                "rounding": "bankers", "report_format": "plain_grouped"},
    "General": {"label": "General (in-house)", "countable_range": [15, 150], "report_sig_figs": 2,
                "rounding": "bankers", "report_format": "scientific",
                "ratio_threshold": 2.0},
}

CANONICAL_COLS = ["lab_code", "analyte", "dilution", "count",
                  "calculated", "result", "remark"]


# ---------------------------------------------------------------- parsing
def parse_dilution(s) -> float | None:
    """รองรับ 0.1 / '1:10' / '10^-2' / '10-2' / 'x10' (multiplier→d=1/N)"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace(" ", "").lower()
    if not t:
        return None
    m = re.fullmatch(r"1:(\d+)", t)
    if m:
        return 1 / int(m.group(1))
    m = re.fullmatch(r"x(\d+)", t)
    if m:
        return 1 / int(m.group(1))
    m = re.fullmatch(r"10\^?-(\d+)", t)
    if m:
        return 10 ** (-int(m.group(1)))
    try:
        return float(t)
    except ValueError:
        return None


def parse_count(s):
    """คืน int, 'TNTC', หรือ None ; '<1'/'<N' = ไม่พบ → 0"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    if isinstance(s, (int, float)):
        return int(s)
    t = str(s).strip().upper()
    if t in ("", "-", "NAN"):
        return None
    if t in ("TNTC", "N", "ND"):
        return TNTC if t == "TNTC" else 0
    if t.startswith("<"):          # <1 = ไม่พบโคโลนี
        return 0
    try:
        return int(float(t))
    except ValueError:
        return None


# duplicate suffix: "No.1", "N0.1"(พิมพ์ผิด), "no 2", ติดกับเลข lab ก็ได้ ("11N0.1"), ไม่สนตัวพิมพ์
# ไม่ใช้ \b หน้า N เพื่อให้ match แม้ไม่มีเว้นวรรค; ยึด suffix ตัวท้ายสุด
_REP_RE = re.compile(r"N[o0]\.?\s*(\d+)\s*$", re.IGNORECASE)


def _base_lab(lab: str) -> tuple[str, int]:
    """แยก base lab_code กับหมายเลข replicate จาก suffix No.X / N0.X (case-insensitive, มี/ไม่มีเว้นวรรค)"""
    s = str(lab).strip()
    m = _REP_RE.search(s)
    if m:
        base = _REP_RE.sub("", s).strip(" -")
        return base, int(m.group(1))
    return s, 1


# ---------------------------------------------------------------- read / template adapter
# alias ชื่อคอลัมน์ → canonical
_ALIAS = {
    "lab_code": "lab_code", "lab code": "lab_code", "labcode": "lab_code",
    "lab no": "lab_code", "lab no.": "lab_code", "lab number": "lab_code",
    "analyte": "analyte", "test": "analyte", "organism": "analyte",
    "dilution": "dilution", "dilution factor": "dilution", "dilution_factor": "dilution",
    "count": "count", "counting": "count", "colony": "count", "count_raw": "count",
    "calculated": "calculated", "calculated count": "calculated",
    "result": "result", "results": "result",
    "remark": "remark", "remarks": "remark",
}
_CANON_COLS = ["lab_code", "analyte", "dilution", "count", "calculated", "result", "remark"]


def _canon(name) -> str | None:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    t = re.sub(r"\s+", " ", str(name).strip().lower())
    return _ALIAS.get(t)


def _find_header(raw: pd.DataFrame) -> int | None:
    """หาแถว header — แถวที่มีทั้ง lab_code และ (count หรือ dilution)"""
    for i in range(min(25, len(raw))):
        cells = {_canon(v) for v in raw.iloc[i].tolist()}
        if "lab_code" in cells and ({"count", "dilution"} & cells):
            return i
    return None


def read_input(path: str) -> pd.DataFrame:
    # dtype=str + header=None: อ่านดิบก่อน แล้วหา header เอง (รองรับ worksheet ที่ header ไม่ใช่แถวแรก)
    raw = (pd.read_excel(path, dtype=str, header=None) if path.lower().endswith((".xlsx", ".xls"))
           else pd.read_csv(path, dtype=str, header=None))
    hr = _find_header(raw)
    if hr is None:
        cols = ", ".join(str(v) for v in raw.iloc[0].tolist() if pd.notna(v))
        raise ValueError(f"ไม่พบหัวตาราง (ต้องมีคอลัมน์ Lab Code/Lab No. + Counting/Dilution) — พบ: {cols[:120]}")

    pos: dict[str, int] = {}
    for idx, name in enumerate(raw.iloc[hr].tolist()):
        c = _canon(name)
        if c and c not in pos:
            pos[c] = idx

    body = raw.iloc[hr + 1:].reset_index(drop=True)
    out = pd.DataFrame({
        col: (body.iloc[:, pos[col]] if col in pos else "") for col in _CANON_COLS
    })
    # worksheet เว้น Lab Code ว่างในแถว dilution ถัดไป → forward-fill
    out["lab_code"] = out["lab_code"].replace(r"^\s*$", pd.NA, regex=True).ffill()
    # เก็บเฉพาะแถวข้อมูลจริง (count parse ได้) — ตัดแถว unit/หัวท้ายฟอร์มออก
    mask = out["count"].map(lambda v: parse_count(v) is not None)
    src_rows = [hr + 1 + p for p in out.index[mask]]     # แถวจริงในไฟล์ต้นฉบับ (0-based) ต่อแต่ละแถวข้อมูล
    out = out[mask].reset_index(drop=True)
    out["analyte"] = out["analyte"].fillna("")
    # metadata สำหรับเขียนผลกลับลงฟอร์มเดิม (คงเลย์เอาต์)
    out.attrs["template"] = {"path": path, "header_row": hr, "pos": pos, "src_rows": src_rows}
    return out


# ---------------------------------------------------------------- process
def process(df: pd.DataFrame, standard: str, V=1.0, n_per=1, range_override=None) -> pd.DataFrame:
    std = dict(STANDARDS[standard])
    if range_override:
        std["countable_range"] = list(range_override)
    lo, hi = std["countable_range"]
    df = df.copy()
    df["_base"], df["_rep"] = zip(*df["lab_code"].map(_base_lab))
    df["_d"] = df["dilution"].map(parse_dilution)
    df["_c"] = df["count"].map(parse_count)

    for (base, analyte), grp in df.groupby(["_base", "analyte"], sort=False):
        # เติม calculated: แถวในช่วงนับ = count/DF; ถ้าไม่มีแถวในช่วง → เติมแถวที่นำมาแปล (est./TNTC/ไม่พบ)
        in_range = [(idx, r["_c"], r["_d"]) for idx, r in grp.iterrows()
                    if isinstance(r["_c"], int) and r["_d"] and lo <= r["_c"] <= hi]
        if in_range:
            for idx, c, d in in_range:
                df.at[idx, "calculated"] = round(c / d)
        else:
            ints = [(idx, r["_c"], r["_d"]) for idx, r in grp.iterrows()
                    if isinstance(r["_c"], int) and r["_d"]]
            non_zero = [(idx, c, d) for idx, c, d in ints if c > 0]
            first = grp.index[0]
            if all(r["_c"] == TNTC for _, r in grp.iterrows()):
                df.at[first, "calculated"] = "TNTC"
            elif non_zero:                                   # นอกช่วงทุก dilution → count/DF ของแถวที่ใช้
                idx, c, d = max(non_zero, key=lambda t: t[1])
                df.at[idx, "calculated"] = round(c / d)
            else:                                            # ไม่พบตั้งแต่แรก → <1/d
                lowest_d = max((r["_d"] for _, r in grp.iterrows() if r["_d"]), default=1)
                df.at[first, "calculated"] = "<" + str(int(1 / lowest_d))

        reps = sorted(grp["_rep"].unique())
        if standard == "General":
            replicates = [
                [Reading(r["_d"], r["_c"]) for _, r in grp[grp["_rep"] == rp].iterrows()
                 if r["_d"] is not None and r["_c"] is not None]
                for rp in reps
            ]
            res = interpret_general(replicates, std)
        elif standard == "FDA_BAM":
            platesets = {}
            for _, r in grp.iterrows():
                if r["_d"] is not None and isinstance(r["_c"], int):
                    platesets.setdefault(r["_d"], []).append(r["_c"])
            res = interpret_fda([PlateSet(d, cs) for d, cs in platesets.items()], std)
        else:  # ISO7218
            readings = [Reading(r["_d"], r["_c"]) for _, r in grp.iterrows()
                        if r["_d"] is not None and r["_c"] is not None]
            res = interpret_iso(readings, std, V=V, n_per=n_per)

        first = grp.index[0]
        df.at[first, "result"] = res.result
        if res.remark:
            df.at[first, "remark"] = res.remark

    result = df.drop(columns=["_base", "_rep", "_d", "_c"])
    result.attrs = dict(df.attrs)                 # คง metadata (template) ผ่าน process
    return result


def write_output(df: pd.DataFrame, path: str):
    cols = [c for c in CANONICAL_COLS if c in df.columns]
    out = df[cols]
    if path.lower().endswith(".csv"):
        out.to_csv(path, index=False)
    else:
        out.to_excel(path, index=False)


def can_write_back(meta) -> bool:
    """เขียนกลับฟอร์มเดิมได้เมื่อ: มี template meta + ไฟล์ต้นฉบับเป็น .xlsx + ฟอร์มมีคอลัมน์ Results"""
    return bool(meta) and str(meta.get("path", "")).lower().endswith(".xlsx") \
        and "result" in meta.get("pos", {})


def write_back_template(out_df: pd.DataFrame, meta: dict, dest):
    """เขียน calculated/result/remark กลับลงไฟล์ฟอร์มเดิม (คงเลย์เอาต์ทุกอย่าง).
    dest = path หรือ file-like (BytesIO). out_df ต้องเรียงแถวตรงกับ meta['src_rows']"""
    import openpyxl
    pos, src_rows = meta["pos"], meta["src_rows"]
    wb = openpyxl.load_workbook(meta["path"])
    ws = wb.active
    for i, src in enumerate(src_rows):
        if i >= len(out_df):
            break
        row = out_df.iloc[i]
        for col in ("calculated", "result", "remark"):
            if col in pos:
                val = row.get(col, "")
                if pd.notna(val) and str(val).strip():
                    cell = ws.cell(row=src + 1, column=pos[col] + 1, value=str(val))
                    cell.number_format = "@"          # text — กัน Excel แปลง 1.4E+03 เป็นตัวเลข
    wb.save(dest)
