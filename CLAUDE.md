# MicrobialCalcuation — โปรเจกต์แปลผลการทดสอบเชื้อจุลินทรีย์

Web app ที่รับ raw data การนับโคโลนี แล้วคำนวณ + แปลผลตาม ISO 7218 / FDA BAM Ch.3 / General
เติมผลใน Calculated / Results / Remark และคืนไฟล์ (เขียนกลับลงฟอร์มเดิมได้)

## โครงสร้าง
- `prototype/interpretation_engine.py` — engine 3 mode: `interpret_iso`, `interpret_fda`, `interpret_general` + การปัดเศษ/format
- `prototype/io_layer.py` — read_input (template adapter), process (orchestrator), write_back_template, parser
- `prototype/method_config.yaml` — mapping method ↔ standard ↔ ช่วงนับ ↔ หน่วย
- `prototype/test_*.py` — pytest (ปัจจุบัน 37 ผ่าน) · `run_demo.py` — เดโม engine
- `webapp/app.py` + `templates/` — Flask web UI (upload → review → approve → download)
- `Requirement/` — SRS, diagrams (mermaid), เอกสารมาตรฐาน (docx), ฟอร์มจริง LF07-05-22 / Petrifilm
- `SETUP.md` — คู่มือติดตั้ง/รัน (Mac + Windows) · `run.sh` / `run.bat` · `requirements.txt`

## วิธีรัน
```bash
pip install -r requirements.txt
python webapp/app.py        # → http://127.0.0.1:5001   (mac: python3)
cd prototype && python -m pytest -q     # 37 passed
```
เว็บ: upload CSV/XLSX (คอลัมน์ lab_code, analyte, dilution, count) → เลือกมาตรฐาน + V/n/ช่วงนับ → review → approve → download

## การตัดสินใจ & กฎที่ยืนยันแล้ว (อย่าย้อนโดยไม่ถาม)
- Input v1 = CSV/XLSX (JPG/OCR เลื่อน phase หลัง); ผู้ใช้กรอก V, n1, n2 + เลือกมาตรฐานตอน upload
- คงเลย์เอาต์ worksheet เดิม (wide); download เขียนผลกลับลงฟอร์ม LF07-05-22 (write_back_template)
- เลขนัยสำคัญ: ISO & FDA = 2 หลัก, General = mantissa 1 ทศนิยม; ISO ปัด half-up, FDA/General banker's
- **ค่า 1–99 รายงานเป็นจำนวนเต็ม** (เช่น `90 est.` ไม่ใช่ `9.0E+01`); ≥100 = scientific
- Duplicate = suffix `No.1`/`N0.1` (case-insensitive, มี/ไม่มีเว้นวรรค), regex `N[o0]\.?\s*(\d+)\s*$`
  - ทั้งคู่ in-range 2 dilution: มี ratio<2 → เฉลี่ยของตัวนั้น (ถ้า<2 ทั้งคู่→เฉลี่ยมากสุด); >2 ทั้งคู่ → calculated มากสุด
  - เคสผสม (ตัวหนึ่ง in-range, อีกตัว est./นอกช่วง) → **ยึดตัว in-range**
  - แต่ละตัวมี in-range 1 dilution → ค่าเดี่ยวมากสุด (max)
- `<1` = ไม่พบ (นับเป็น 0); TNTC = เฉพาะ token จริง (เลข >150 = นอกช่วง ไม่ใช่ TNTC)
- Workflow อนุมัติ required (Draft→Submitted→Approved/Rejected + audit trail)

## สถานะปัจจุบัน / งานที่เหลือ
เสร็จ: engine, I/O + template adapter (LF07-05-22), web UI ครบ flow, write-back ลงฟอร์ม, 37 tests
เหลือ: **UI redesign** (กำลังเลือกดีไซน์ — โทนเขียว CPF, Variant A card/stepper vs B enterprise/แท็บ),
Petrifilm (LM 7.2-04, 2 บล็อก analyte), FDA out-of-range→EAPC เต็ม, DB + auth/role แทน in-memory store

## หมายเหตุ
- macOS: อย่าวางโปรเจกต์ใน ~/Downloads, ~/Desktop, ~/Documents (TCC block preview) — ใช้ที่อื่น เช่น ~/MicrobialCalcuation
- โปรเจกต์อยู่ใน OneDrive/CloudStorage → preview harness (Claude Code) โดน TCC block อ่านไฟล์ไม่ได้ (EPERM). แก้ด้วย `./sync-preview.sh` copy `webapp/`+`prototype/` ไป mirror `~/.microbial-preview` (override ด้วย env `MICROBIAL_PREVIEW_DIR`); launch.json ชี้ไป mirror + `autoPort`. **ต้อง sync ทุกครั้งหลังแก้ template/py ก่อน preview_start**. source of truth ยังอยู่ในโปรเจกต์นี้
- อ่าน .xls เก่าใช้ xlrd; openpyxl เขียน .xlsx; scientific string ต้องเก็บเป็น text cell กัน Excel แปลงเป็นเลข
