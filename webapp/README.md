# Web UI (prototype)

Flask app แปลผลเชื้อจุลินทรีย์ — reuse `prototype/interpretation_engine.py` + `io_layer.py`

## รัน
```bash
cd /Users/Work/Downloads/MicrobialCalcuation
python3 webapp/app.py
# เปิด http://127.0.0.1:5001
```

## Flow
1. **Upload** (`/`) — เลือกไฟล์ CSV/XLSX + มาตรฐาน (ISO / FDA / General) + กรอก V, n, ช่วงนับ
   (ช่วงนับ default ตามมาตรฐาน เปลี่ยน auto เมื่อเลือก dropdown)
2. **Review** (`/batch/<id>`) — ตารางผล เติม calculated/result/remark, ไฮไลต์ special case (est./TNTC/&lt;/&gt;)
3. **Approve / Reject** — เปลี่ยนสถานะ Submitted → Approved/Rejected, บันทึก audit trail; Approved = ล็อกไม่ให้แก้
4. **Download** — ไฟล์ผล XLSX (scientific notation เก็บเป็น text cell)

ไฟล์ตัวอย่าง: `sample_iso.xlsx`, `sample_general.xlsx`

## ยืนยันการทำงาน (curl end-to-end)
- General: `GEN-8` → `1.4E+03` + `Ratio = 1.2`; duplicate `GEN-9 No.1/No.2` → `1.6E+02` + `duplicate=max`
- ISO: `1.4E+04`, `1.2E+05 est.`, `<10` ✓
- Approve → status `Approved`; download → 200, ผลตรงกับหน้า review

## ข้อจำกัด prototype
- Batch store เป็น in-memory (`BATCHES` dict) — full build ใช้ DB (ดู ER ใน `Requirement/diagrams.md`)
- Auth จำลอง (`CURRENT_USER`) — full build ต่อ role/login จริง
- **หมายเหตุ preview:** โปรเจกต์อยู่ใน `~/Downloads` ซึ่ง macOS TCC บล็อก preview launcher (python ของ Xcode)
  ทำให้ Launch preview panel รันไม่ได้ — ให้รันด้วย `python3 webapp/app.py` ผ่าน terminal ปกติแทน
  (ถ้าย้ายโปรเจกต์ออกนอก Downloads preview จะทำงานได้)
