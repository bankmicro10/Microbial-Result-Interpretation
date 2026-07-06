# คู่มือการติดตั้งและรัน — Microbial Result Interpretation

เว็บแอปแปลผลการนับโคโลนีตาม ISO 7218 / FDA BAM Ch.3 / General
ใช้ได้ทั้ง **macOS**, **Linux** และ **Windows** (เป็น Python ล้วน)

---

## 1. สิ่งที่ต้องมีก่อน (Prerequisites)

- **Python 3.9 ขึ้นไป**
  - macOS: มักมีอยู่แล้ว (`python3 --version`) หรือติดตั้งผ่าน [python.org](https://www.python.org/downloads/) / `brew install python`
  - Windows: โหลดจาก [python.org](https://www.python.org/downloads/) → ตอนติดตั้ง **ติ๊ก ☑ "Add Python to PATH"**
- เชื่อมต่ออินเทอร์เน็ต (สำหรับติดตั้ง library ครั้งแรก)

ตรวจว่ามี Python:
```
python3 --version      # mac/linux
python --version       # windows
```

---

## 2. คัดลอกโปรเจกต์

คัดลอกโฟลเดอร์ `MicrobialCalcuation` ทั้งโฟลเดอร์ไปเครื่องเป้าหมาย ต้องมีโครงสร้างครบ:

```
MicrobialCalcuation/
├── requirements.txt        รายชื่อ library
├── run.sh                  สคริปต์รัน (mac/linux)
├── run.bat                 สคริปต์รัน (windows)
├── SETUP.md                ไฟล์นี้
├── prototype/              engine + I/O layer + tests
│   ├── interpretation_engine.py
│   ├── io_layer.py
│   ├── method_config.yaml
│   └── test_*.py
└── webapp/                 เว็บแอป (Flask)
    ├── app.py
    ├── templates/
    └── sample_*.xlsx       ไฟล์ตัวอย่างสำหรับทดสอบ
```
> ⚠️ ต้องมีทั้ง `prototype/` และ `webapp/` เพราะ `webapp/app.py` เรียกใช้โค้ดใน `prototype/`

---

## 3. วิธีรัน

### วิธี A — ใช้สคริปต์สำเร็จรูป (ง่ายสุด, ติดตั้ง+รันให้เลย)

**macOS / Linux** — เปิด Terminal:
```bash
cd /path/to/MicrobialCalcuation
bash run.sh
```

**Windows** — ดับเบิลคลิก `run.bat`  (หรือพิมพ์ `run.bat` ใน cmd)

### วิธี B — พิมพ์คำสั่งเอง

**macOS / Linux:**
```bash
cd /path/to/MicrobialCalcuation
pip3 install -r requirements.txt      # ครั้งแรกครั้งเดียว
python3 webapp/app.py
```

**Windows (cmd / PowerShell):**
```cmd
cd C:\path\to\MicrobialCalcuation
pip install -r requirements.txt        :: ครั้งแรกครั้งเดียว
python webapp\app.py
```

---

## 4. เปิดใช้งาน

เมื่อขึ้นข้อความ `Running on http://127.0.0.1:5001` ให้เปิดเบราว์เซอร์ไปที่:

**http://127.0.0.1:5001**

ขั้นตอนในเว็บ:
1. **Upload** ไฟล์ raw data (CSV/XLSX) — คอลัมน์: `lab_code, analyte, dilution, count`
   (หรือฟอร์ม LF07-05-22 โดยตรง — ระบบหาหัวตารางเองอัตโนมัติ)
2. เลือก **มาตรฐาน** (ISO / FDA / General) + กรอก V, n, ช่วงนับ → กด **แปลผล**
3. **Review** ตรวจผล (แถว special case จะไฮไลต์)
4. **อนุมัติ / ปฏิเสธ** (บันทึก audit trail)
5. **ดาวน์โหลดไฟล์ผล** — ถ้าเป็นฟอร์ม LF07 จะได้ไฟล์หน้าตาเดิมที่เติมผลให้แล้ว

**หยุดการทำงาน:** กด `Ctrl + C` ใน Terminal/cmd

---

## 5. รันชุดทดสอบ (ตรวจว่า engine ถูกต้อง)

```bash
# mac/linux
cd /path/to/MicrobialCalcuation/prototype
python3 -m pytest -q

# windows
cd C:\path\to\MicrobialCalcuation\prototype
python -m pytest -q
```
ผลที่ควรได้: `37 passed`

ทดสอบ engine แบบเห็นผลลัพธ์ (ไม่ต้องเปิดเว็บ):
```
python3 run_demo.py        # mac    (windows: python run_demo.py)
```

---

## 6. แก้ปัญหาที่พบบ่อย (Troubleshooting)

| อาการ | วิธีแก้ |
|---|---|
| `python3`/`pip3` ไม่เจอ (mac) | ลองใช้ `python` / `pip` |
| `python`/`pip` ไม่เจอ (windows) | ลองใช้ `py` เช่น `py webapp\app.py` |
| `ModuleNotFoundError: No module named 'flask'` | ยังไม่ได้ติดตั้ง library → รัน `pip install -r requirements.txt` |
| `Address already in use` / port 5001 ถูกใช้ | แก้เลขพอร์ตท้ายไฟล์ `webapp/app.py` บรรทัด `app.run(... port=5001)` เป็นเลขอื่น เช่น 5002 |
| เปิดเว็บไม่ได้ | ตรวจว่า Terminal ยังรันอยู่ + ใช้ URL `http://127.0.0.1:5001` (ไม่ใช่ https) |
| อ่านไฟล์ `.xls` เก่าไม่ได้ | ต้องมี `xlrd` (อยู่ใน requirements แล้ว); หรือ Save As เป็น `.xlsx` |

> 📌 หมายเหตุ macOS: ถ้ารันแล้วเจอ `Operation not permitted` ให้ย้ายโปรเจกต์ออกจากโฟลเดอร์ `~/Downloads`, `~/Desktop`, `~/Documents` (โฟลเดอร์ที่ macOS ป้องกันสิทธิ์) ไปไว้ที่อื่น เช่น `~/MicrobialCalcuation` — บน Windows ไม่มีปัญหานี้

---

## 7. รูปแบบไฟล์ input

**คอลัมน์:** `lab_code | analyte | dilution | count` (calculated/result/remark เว้นว่าง ระบบเติมให้)

- `dilution` รองรับ: `0.1`, `1:10`, `10^-2`, `10-3`, `x10`
- `count` รองรับ: ตัวเลข, `TNTC`, `<1` (=ไม่พบ), `0`
- **Duplicate:** ใส่ `No.1` / `No.2` (หรือ `N0.1`) ต่อท้าย lab_code — มี/ไม่มีเว้นวรรค และตัวพิมพ์เล็ก-ใหญ่ได้หมด

รองรับฟอร์ม **LF07-05-22** (header อยู่แถวลึก, Lab Code เว้นว่างในแถว dilution ถัดไป) โดยตรง — ไม่ต้องจัดรูปใหม่
