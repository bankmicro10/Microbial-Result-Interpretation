"""Demo end-to-end: สร้างไฟล์ input → read → process → write output → อ่านกลับมาแสดง"""
import pandas as pd
from io_layer import read_input, process, write_output

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)


def build(rows):
    return pd.DataFrame(rows, columns=["lab_code", "analyte", "dilution", "count"])


# ---- ISO batch (10^-n / decimal ปนกัน เพื่อทดสอบ parser) ----
iso = build([
    ("ISO-1/1", "APC", "10^-2", "135"), ("ISO-1/1", "APC", "10^-3", "14"),
    ("ISO-2/1", "APC", "10^-1", "8"),   ("ISO-2/1", "APC", "10^-2", "1"),
    ("ISO-3/1", "APC", "10^-1", "2"),   ("ISO-3/1", "APC", "10^-2", "0"),
    ("ISO-4/1", "APC", "0.1", "0"),     ("ISO-4/1", "APC", "0.01", "0"),
    ("ISO-5/1", "APC", "10^-2", "TNTC"),("ISO-5/1", "APC", "10^-3", "TNTC"),
    ("ISO-6/1", "APC", "10^-2", "TNTC"),("ISO-6/1", "APC", "10^-3", "120"),
])

# ---- General batch (มี duplicate No.1/No.2) ----
gen = build([
    ("GEN-8/1", "E_coli", "0.1", "125"),   ("GEN-8/1", "E_coli", "0.01", "15"),
    ("GEN-9/1 No.1", "E_coli", "0.1", "15"), ("GEN-9/1 No.1", "E_coli", "0.01", "4"),
    ("GEN-9/1 No.2", "E_coli", "0.1", "16"), ("GEN-9/1 No.2", "E_coli", "0.01", "4"),
])

for name, df, std, V, n in [("ISO 7218", iso, "ISO7218", 1.0, 1),
                            ("General (3.General)", gen, "General", 1.0, 1)]:
    df.to_excel(f"in_{std}.xlsx", index=False)          # จำลองไฟล์ที่พนักงาน upload
    loaded = read_input(f"in_{std}.xlsx")
    out = process(loaded, std, V=V, n_per=n)
    write_output(out, f"out_{std}.xlsx")
    back = read_input(f"out_{std}.xlsx")                 # อ่านไฟล์ผลกลับมายืนยัน round-trip
    print(f"\n===== {name} =====")
    print(back[["lab_code", "dilution", "count", "calculated", "result", "remark"]]
          .fillna("").to_string(index=False))
