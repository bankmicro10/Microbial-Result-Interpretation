"""
Interpretation Engine (prototype) — แปลผลการนับโคโลนีตาม ISO 7218 / FDA BAM Ch.3 / General(3.General)

หมายเหตุ: เป็น prototype ระดับ requirement — logic ยึดตามตัวอย่างในเอกสาร `มาตรฐานการคำนวณ.docx`
V, n1, n2 = พารามิเตอร์ที่ผู้ใช้กรอกตอน upload (default V=1, n=1/plate ต่อ dilution)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from math import floor, log10
from typing import Union

TNTC = "TNTC"
Count = Union[int, str]  # int หรือ "TNTC"


# ---------------------------------------------------------------- rounding / format
def round_sig(value: float, sig: int = 2, tie: str = "up") -> float:
    if value == 0:
        return 0.0
    d = Decimal(str(value))
    exp = d.adjusted()                       # เลขชี้กำลังของหลักนัยสำคัญตัวแรก
    quant = Decimal(1).scaleb(exp - (sig - 1))
    rounding = ROUND_HALF_UP if tie == "up" else ROUND_HALF_EVEN
    return float(d.quantize(quant, rounding=rounding))


def to_scientific(value: float, sig: int = 2, tie: str = "up") -> str:
    v = round_sig(value, sig, tie)
    if v == 0:
        return "0"
    exp = floor(log10(abs(v)))
    mant = v / (10 ** exp)
    return f"{mant:.{sig-1}f}E{exp:+03d}"


def to_plain_grouped(value: float, sig: int = 2, tie: str = "even") -> str:
    return f"{int(round_sig(value, sig, tie)):,}"


def format_report(value: float, std: dict) -> str:
    sig = std["report_sig_figs"]
    tie = "up" if std["rounding"] == "half_up" else "even"
    fmt = std["report_format"]
    if fmt == "plain_grouped":
        return to_plain_grouped(value, sig, tie)
    # ค่า 1–99 รายงานเป็นจำนวนเต็มธรรมดา (ไม่ใช้ scientific) ทั้ง scientific/auto
    rounded = round_sig(value, sig, tie)
    if 1 <= rounded < 100:
        return str(int(rounded))
    return to_scientific(value, sig, tie)


# ---------------------------------------------------------------- helpers
def is_tntc(c: Count) -> bool:
    return c == TNTC or (isinstance(c, (int, float)) and c > 150)


@dataclass
class Reading:
    d: float          # dilution factor เช่น 0.1, 0.01
    count: Count      # จำนวนโคโลนีดิบ หรือ "TNTC"


@dataclass
class Result:
    result: str
    calculated: list = field(default_factory=list)   # ค่า Calculated count ต่อแถวที่นำมาแปล
    remark: str = ""


# ---------------------------------------------------------------- ISO 7218
def interpret_iso(readings: list[Reading], std: dict, V=1.0, n_per=1) -> Result:
    lo, hi = std["countable_range"]                  # 10..150
    lowest_d = max(r.d for r in readings)            # dilution ต่ำสุด (เจือจางน้อยสุด)
    highest_d = min(r.d for r in readings)
    nums = [r for r in readings if isinstance(r.count, int)]
    countable = [r for r in nums if lo <= r.count <= hi]
    est = [r for r in nums if 4 <= r.count <= 9]
    low = [r for r in nums if 1 <= r.count <= 3]
    all_tntc = all(is_tntc(r.count) for r in readings)
    all_zero = bool(nums) and all(r.count == 0 for r in nums)

    if countable:
        lowest_is_tntc = any(is_tntc(r.count) for r in readings if r.d == lowest_d)
        C = sum(r.count for r in countable)
        if lowest_is_tntc:  # TNTC ชั้นต่ำสุด แล้วชั้นถัดไปนับได้ → estimate
            val = C / (V * (0 + 0.1 * n_per) * lowest_d)
            return Result(format_report(val, std) + " est.", [round(val)])
        d_first = max(r.d for r in countable)
        n1, n2 = n_per, (n_per if len(countable) > 1 else 0)
        val = C / (V * (n1 + 0.1 * n2) * d_first)
        return Result(format_report(val, std), [round(val)])

    if est:                                          # 4–9 → estimate
        C = sum(r.count for r in nums)
        n1, n2 = n_per, (n_per if len(nums) > 1 else 0)
        val = C / (V * (n1 + 0.1 * n2) * lowest_d)
        return Result(format_report(val, std) + " est.", [round(val)])

    if low:                                          # 1–3 → < 4/(V·d)
        val = 4 / (V * lowest_d)
        return Result("<" + format_report(val, std))

    if all_tntc:                                     # > 150/(V·d_last)
        val = 150 / (V * highest_d)
        return Result(">" + format_report(val, std))

    if all_zero:                                     # ไม่พบ → < 1/(V·d)
        val = 1 / (V * lowest_d)
        return Result("<" + format_report(val, std))

    return Result("N/A")


# ---------------------------------------------------------------- FDA BAM Ch.3
@dataclass
class PlateSet:
    d: float
    counts: list[int]     # จานซ้ำในแต่ละ dilution


def interpret_fda(platesets: list[PlateSet], std: dict) -> Result:
    lo, hi = std["countable_range"]                  # 15..300
    counted = [ps for ps in platesets if any(lo <= c <= hi for c in ps.counts)]
    if not counted:
        return Result("N/A (out of range → EAPC)")   # prototype: special cases ย่อ
    counted.sort(key=lambda ps: ps.d, reverse=True)  # dilution ต่ำสุดก่อน
    C = sum(c for ps in counted for c in ps.counts if lo <= c <= hi)
    n1 = len([c for c in counted[0].counts if lo <= c <= hi])
    n2 = len([c for c in counted[1].counts if lo <= c <= hi]) if len(counted) > 1 else 0
    d = counted[0].d
    val = C / ((n1 + 0.1 * n2) * d)
    return Result(format_report(val, std))


# ---------------------------------------------------------------- General (3.General)
def _calc(readings, lo, hi):
    """คืน list ของ (reading, calculated=count/d) เฉพาะแถวที่อยู่ในช่วงนับ"""
    out = []
    for r in readings:
        if isinstance(r.count, int) and lo <= r.count <= hi:
            out.append((r, r.count / r.d))
    return out


def _interpret_general_single(readings: list[Reading], std: dict) -> Result:
    lo, hi = std["countable_range"]
    thr = std.get("ratio_threshold", 2.0)
    in_range = _calc(readings, lo, hi)
    calcs = [round(v) for _, v in in_range]

    if len(in_range) == 1:
        val = in_range[0][1]
        return Result(format_report(val, std), calcs)

    if len(in_range) >= 2:
        in_range.sort(key=lambda x: x[0].d, reverse=True)   # dilution ต่ำสุดก่อน
        calc1, calc2 = in_range[0][1], in_range[1][1]
        ratio = calc2 / calc1
        if ratio < thr:
            val = (calc1 + calc2) / 2
            return Result(format_report(val, std), calcs, f"Ratio = {ratio:.1f}")
        return Result(format_report(calc1, std), calcs, f"Ratio = {round(ratio)}")

    # ไม่มีแถวในช่วง → est. / TNTC / not-detected
    nums = [r for r in readings if isinstance(r.count, int)]
    lowest_d = max(r.d for r in readings)
    # TNTC เฉพาะ token จริงเท่านั้น — เลขนับ >hi ถือเป็น "นอกช่วง" ไม่ใช่ TNTC
    if all(r.count == TNTC for r in readings):
        return Result("TNTC", ["TNTC"])
    non_zero = [r for r in nums if r.count > 0]            # int ทุกค่า (รวม >hi), ตัด TNTC/0 ออก
    if non_zero:                                           # นอกช่วงทุก dilution → est.
        r = max(non_zero, key=lambda x: x.count)
        val = r.count / r.d
        return Result(format_report(val, std) + " est.", [round(val)])
    val = 1 / lowest_d                                     # ไม่พบตั้งแต่แรก
    return Result("<" + str(int(val)) + " est.", ["<" + str(int(val))])


def interpret_general(replicates: list[list[Reading]], std: dict) -> Result:
    """replicates = [readings_No1, readings_No2, ...]; ถ้าไม่ duplicate ส่ง 1 รายการ"""
    if len(replicates) == 1:
        return _interpret_general_single(replicates[0], std)

    lo, hi = std["countable_range"]
    thr = std.get("ratio_threshold", 2.0)

    # ในช่วงนับของแต่ละ duplicate (เรียง dilution ต่ำสุดก่อน)
    reps_in_range = [
        sorted(_calc(rep, lo, hi), key=lambda x: x[0].d, reverse=True)
        for rep in replicates
    ]

    # เคสผสม: บาง duplicate อยู่ในช่วง บางตัวเป็น est./นอกช่วง → ยึดเฉพาะตัวที่อยู่ในช่วง
    valid = [i for i, ir in enumerate(reps_in_range) if len(ir) >= 1]
    if valid and len(valid) < len(replicates):
        replicates = [replicates[i] for i in valid]
        reps_in_range = [reps_in_range[i] for i in valid]
        if len(replicates) == 1:
            res = _interpret_general_single(replicates[0], std)
            res.remark = (res.remark + " | duplicate=in-range").strip(" |")
            return res

    # กรณีทุก duplicate มี 2 dilution อยู่ในช่วง → คิด ratio รายตัวแล้ว aggregate
    if all(len(ir) >= 2 for ir in reps_in_range):
        info = []
        for ir in reps_in_range:
            calc1, calc2 = ir[0][1], ir[1][1]
            info.append({"ratio": calc2 / calc1, "avg": (calc1 + calc2) / 2,
                         "calcs": [c for _, c in ir]})
        ratios_txt = ", ".join(f"{x['ratio']:.1f}" for x in info)
        lt2 = [x for x in info if x["ratio"] < thr]
        if lt2:                                    # มี ratio < 2 → ค่าเฉลี่ย (ถ้า <2 หลายตัว เอาเฉลี่ยมากสุด)
            val = max(x["avg"] for x in lt2)
            mode = "avg"
        else:                                      # ratio ≥ 2 ทั้งคู่ → calculated มากสุด
            val = max(c for x in info for c in x["calcs"])
            mode = "max"
        return Result(format_report(val, std), remark=f"Ratio = {ratios_txt} | duplicate={mode}")

    # กรณีอื่น (ไม่ครบ 2 dilution ในช่วงทุกตัว) → แปลแต่ละ duplicate แล้วเอาค่ามากสุด
    results = [_interpret_general_single(rep, std) for rep in replicates]

    def magnitude(res: Result) -> float:
        try:
            return float(res.result.replace(",", "").replace("est.", "").replace("E", "e").strip() or 0)
        except ValueError:
            return -1
    best = max(results, key=magnitude)
    best.remark = (best.remark + " | duplicate=max").strip(" |")
    return best
