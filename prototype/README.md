# Prototype — Interpretation Engine

Prototype ของเครื่องมือแปลผล ตาม `Requirement/SRS_MicrobialInterpretation.md`

## ไฟล์
- `interpretation_engine.py` — engine 3 mode: `interpret_iso`, `interpret_fda`, `interpret_general`
- `io_layer.py` — อ่าน/เขียน CSV·XLSX (wide worksheet) + parser (dilution/count) + orchestrator
- `method_config.yaml` — mapping method ↔ standard ↔ ช่วงนับ ↔ หน่วย ↔ กฎปัดเศษ
- `test_engine.py` — acceptance test 9 เคส (engine)
- `test_io.py` — test parser + end-to-end round-trip
- `run_demo.py` — เดโม end-to-end (สร้างไฟล์ → read → process → write → อ่านกลับ)

## รัน
```bash
cd prototype
python3 -m pytest -q          # 28 passed (engine 11 + io 17)
python3 run_demo.py           # ดูผล end-to-end ISO + General
```

## I/O layer
- **read_input(path)** — อ่าน CSV/XLSX; **หาแถว header อัตโนมัติ** + map ชื่อคอลัมน์ (alias) →
  รองรับฟอร์ม `LF07-05-22` (header แถว 8, Lab Code เว้นว่างในแถว dilution ถัดไป → forward-fill,
  duplicate `No.1`/`N0.1`). แนบ `df.attrs['template']` (header_row, pos, src_rows) ไว้เขียนกลับ
- **process(df, standard, V, n_per)** — group ตาม (base lab_code, analyte), แยก replicate, เรียก engine;
  เติม `calculated` **ทุกเคส**: ในช่วง = count/DF; นอกช่วง(est.) = count/DF ของแถวที่ใช้; TNTC/ไม่พบ = token
- **write_back_template(out_df, meta, dest)** — เขียน calculated/result/remark กลับลง**ฟอร์มเดิม** คงเลย์เอาต์
  (`can_write_back(meta)` เช็คเงื่อนไข: xlsx + มีคอลัมน์ Results); **write_output** = fallback คอลัมน์ canonical
- Canonical schema: `lab_code | analyte | dilution | count | calculated | result | remark`
- Parser dilution: `0.1`, `1:10`, `10^-2`, `10-3`, `x10`; count: ตัวเลข, `TNTC`, `<1`(=ไม่พบ), `0`

## หมายเหตุ / ข้อจำกัดของ prototype
- V, n1, n2 รับเป็นพารามิเตอร์ (ผู้ใช้กรอกตอน upload)
- FDA special cases (out-of-range → EAPC) ยังทำแบบย่อ — ขยายใน phase ถัดไป
- General mode: เอกสารเรียกเลขนัยสำคัญ "1 ตำแหน่ง" = mantissa 1 ทศนิยม (`1.4E+03`) — implement ตามตัวอย่างจริง
- ยังไม่รวม I/O layer (อ่าน CSV/XLSX + เขียนกลับ) และ workflow — เป็นส่วนของ full build
