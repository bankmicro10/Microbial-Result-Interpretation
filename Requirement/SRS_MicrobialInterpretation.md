# SRS — Application แปลผลการทดสอบเชื้อจุลินทรีย์ (Microbial Result Interpretation)

เอกสาร Software Requirements Specification (ฉบับร่าง v0.1)
วันที่: 2026-07-05 · ผู้จัดทำ: System Analyst
แหล่งอ้างอิง: `มาตรฐานการคำนวณ.docx`, `LM 7.2-04 ... Petrifilm.xls`, `LF07-05-22 Plate count worksheet.xls`

---

## 1. ภาพรวมและวัตถุประสงค์ (Overview)

Application รับ **raw data การนับโคโลนี** ต่อ Lab No. แล้ว **คำนวณและแปลผล** ตามมาตรฐานที่ผู้ใช้เลือก
(ISO 7218:2024 หรือ FDA BAM Chapter 3 เวอร์ชันล่าสุด) โดยสัมพันธ์กับ Dilution factor ของแต่ละ Lab No.
จากนั้น **เติมผลลงในคอลัมน์ Calculated count / Results / Remark** และคืนไฟล์ผลให้ผู้ใช้

เป้าหมาย: ลดการคำนวณ/แปลผลด้วยมือ ลด human error และรับประกันความสม่ำเสมอตามมาตรฐาน (traceable, auditable)

## 2. ขอบเขต (Scope) — ตามการตัดสินใจที่ยืนยันแล้ว

| หัวข้อ | การตัดสินใจ |
|---|---|
| รูปแบบ input v1 | **CSV / XLSX** ก่อน — JPG (OCR) เลื่อนไป phase ถัดไป |
| ระดับข้อมูล input | **จำนวนโคโลนีดิบ (raw count)** — app คำนวณ Calculated count + Results + Remark ทั้งหมด |
| การเลือกมาตรฐาน/ช่วงนับ | **ผู้ใช้เลือกตอน upload** (เลือกมาตรฐาน + ช่วงนับที่ใช้กับ batch นั้น) |
| รูปแบบระบบ | **Web application** + คืนไฟล์ผล (Excel/CSV) ให้ download |

**Out of scope (v1):** OCR จากภาพ .jpg, การเชื่อม LIMS อัตโนมัติ, การจัดการตัวอย่าง/รับ-ส่งงานเต็มรูปแบบ

## 3. ผู้เกี่ยวข้อง (Actors)

- **พนักงานห้องปฏิบัติการ (Lab staff)** — upload raw data, เลือกมาตรฐาน, ตรวจ/ดาวน์โหลดผล
- **ผู้ตรวจสอบ/หัวหน้า (Reviewer/Approver)** — ทวนสอบและอนุมัติผลก่อนออกรายงาน (workflow อนุมัติ = required — ดูข้อ 6.2)
- **ผู้ดูแลระบบ (Admin)** — จัดการ config table (method ↔ standard ↔ ช่วงนับ ↔ V/n₁/n₂)

## 4. Requirement การนำเข้าข้อมูล (Input)

### 4.1 รูปแบบไฟล์ input — **คงเลย์เอาต์ worksheet เดิม (wide format)** ✅ ข้อ 4
รองรับ 2 ฟอร์มมาตรฐานที่ใช้อยู่ โดยไม่บังคับให้พนักงานเปลี่ยน template:
- **`LF07-05-22 Plate count worksheet`** (ฟอร์มกลาง APC/Coliforms/E.coli/S.aureus/Yeast&Molds ฯลฯ)
  คอลัมน์: `Lab Code | Dilution Factor (10ⁿ) | Counting | Calculated count | Results | Remark`
  มี check-box เลือกชนิดการทดสอบ + หน่วย (cfu/g, cfu/100ml, MPN/100ml, cfu/cm², cfu/swab)
- **`LM 7.2-04 Petrifilm`** (E.coli + Coliform แยกบล็อกคอลัมน์ในไฟล์เดียว, มี Count/Edit/Confirm/Total/Calculated/Result/Report ต่อ analyte)

App ต้องมี **template adapter/mapper** ระบุตำแหน่ง header row + คอลัมน์ของแต่ละฟอร์ม (เพิ่มฟอร์มใหม่ได้โดย config)

คอลัมน์ที่ต้องมี (สกัดจากฟอร์ม): Lab Code, Dilution factor, Counting (โคโลนีดิบ รวม `TNTC`/`0`), และช่องที่ app จะเติม = **Calculated count, Results, Remark**

### 4.2 เมตาดาต้าที่ผู้ใช้กรอก/เลือกตอน upload
- มาตรฐาน: `ISO 7218:2024` | `FDA BAM Ch.3` | `General` (วิธีในองค์กร) — เลือกต่อ batch/ต่อ analyte
- ช่วงนับ (countable range): default ตามมาตรฐาน (ISO 10–150, FDA 15–300, ตั้งค่าเองได้ เช่น 15–150) แก้ได้
- **พารามิเตอร์การคำนวณ `V`, `n₁`, `n₂` — ผู้ใช้กรอกเองเมื่อเลือก ISO หรือ BAM** ✅ ข้อ 2 (ไม่ hard-code)
- โหมด Duplicate: มี/ไม่มี — **จับคู่จาก `No.1`, `No.2` ของ Lab No. เดียวกัน** ✅ ข้อ 3

### 4.3 Data validation ก่อนคำนวณ
- Lab No. ต้องมีอย่างน้อย 1 dilution; Dilution factor ต้อง parse เป็นตัวเลขได้
- Count เป็นจำนวนเต็ม ≥ 0 หรือ token พิเศษ (`TNTC`)
- แจ้ง error รายแถว (highlight) หากข้อมูลไม่ครบ/ผิดรูปแบบ ก่อนแปลผล

## 5. Requirement เครื่องมือแปลผล (Interpretation Engine) — หัวใจของระบบ

Engine ต้องรองรับกฎทุกมาตรฐานแบบ pluggable (เลือกจากเมตาดาต้าข้อ 4.2)

**กฎเลขนัยสำคัญในการรายงาน (ผูกกับมาตรฐานที่เลือก)** ✅ ข้อ 1
| โหมด | เลขนัยสำคัญ | การปัดเศษ |
|---|---|---|
| ISO 7218:2024 | **2 หลัก** | หลักที่ 3: <5 ปัดทิ้ง, ≥5 ปัดหลักที่ 2 ขึ้น |
| FDA BAM Ch.3 | **2 หลัก** | banker's rounding (เลข 5 ดูหลักที่ 2 คู่/คี่) |
| General | **1 หลัก** | ดูหลักที่ 2: 6–9 ขึ้น, 1–4 ลง, =5 ดูหลักที่ 1 คู่/คี่ |

### 5.1 กฎ ISO 7218

สูตรหลัก (General): `N = ΣC / (V × [n₁ + 0.1·n₂] × d)` โดย d = dilution factor ชั้นแรกที่นับ

| กรณี | จำนวนโคโลนี | การรายงาน |
|---|---|---|
| General | 10–150 | คำนวณตามสูตร แล้วรายงาน scientific notation |
| Estimate (est.) | 4–9 | `Nₑ` ตามสูตรเดียวกัน + ต่อท้าย `est.` |
| ต่ำ (low) | 1–3 | `N < 4/(V·d)` (d = dilution ต่ำสุด) |
| ไม่พบ | 0 ทุก dilution | `N < 1/(V·d)` เช่น `<10` |
| TNTC ทั้งหมด | >150 ทุก dilution | `N > 150/(V·d)` (d = dilution สุดท้าย) |
| TNTC + ชั้นถัดไปอ่านได้ | >150 → 10–150 | คำนวณด้วยสูตร Nₑ + `est.` |

**การปัดเศษ ISO:** ปัดเป็นจำนวนเต็ม แล้วรายงานด้วยเลขนัยสำคัญ (ตัวอย่างในเอกสารใช้ 2 หลัก → `1.4E+04`);
พิจารณาเลขหลักที่ 3: <5 ปัดทิ้ง, ≥5 ปัดหลักที่ 2 ขึ้น 1

### 5.2 กฎ FDA BAM Chapter 3 (2026)

- ช่วงจานที่เหมาะสม (pour plate): **15–300** CFU; นอกช่วง → รายงานเป็น **EAPC (Estimated APC)**
- สูตร weighted average: `N = ΣC / ([n₁ + 0.1·n₂] × d)`
- **การปัดเศษ: เลขนัยสำคัญ 2 ตำแหน่ง** + **banker's rounding** ที่เลข 5
  (หลักที่ 3 = 6–9 ปัดขึ้น; 1–4 ปัดลง; = 5 ให้ดูหลักที่ 2: คี่→ขึ้น, คู่→ลง เช่น 14,500 → 14,000)
- Special cases: ไม่มีโคโลนี → `<10 EAPC/g` (มีดอกจันกำกับ); ทุกจาน <15 → บันทึกค่าจริง แต่รายงานเป็น EAPC

### 5.3 กฎการเติมคอลัมน์ (สอดคล้อง section "3.General" ในเอกสาร)

สำหรับแต่ละ Lab No.:
1. **เลือกแถวที่โคโลนีอยู่ในช่วงนับ** → `Calculated count` = Count ÷ Dilution factor ของแถวนั้น
2. **พบในช่วง 1 dilution:** ใส่ค่านั้นใน Results (scientific notation, เลขนัยสำคัญ **1 ตำแหน่ง** ตามตัวอย่างเอกสาร)
3. **พบในช่วง 2 dilution ติดกัน → ใช้ Ratio = Calc(D2) / Calc(D1):**
   - `Ratio < 2` → รายงาน **ค่าเฉลี่ย** ของ 2 ค่า, ใส่ `Ratio = x.x` ใน Remark (แถวแรกของ dilution แรก)
   - `Ratio > 2` → รายงาน **ค่า dilution แรก**, ใส่ `Ratio = x` ใน Remark
4. **นอกช่วงทุก dilution (ไม่ใช่ TNTC):** Count(ที่ไม่ใช่ TNTC) ÷ DF → Results + ต่อท้าย `est.`
5. **ไม่พบตั้งแต่ dilution แรก:** `<1 ÷ DF` เช่น `<10`, Results ต่อท้าย `est.`
6. **TNTC ตั้งแต่ dilution แรก:** Calculated = `TNTC`, Results = `TNTC`
7. **Duplicate (1 Lab No. ทดสอบซ้ำ = `No.1`, `No.2`):** ✅ ข้อ 3 จับคู่จาก suffix `No.1`/`No.2` ของ Lab No. เดียวกัน
   คำนวณแต่ละซ้ำ แล้ว **รายงานค่ามากสุด** ในแถวแรกของ Lab No. นั้น (รวมกรณีผลเป็น 0 หรือเกินช่วง)

### 5.4 รูปแบบผลลัพธ์ (Result format)
- Scientific notation เช่น `1.4E+04`, `<10`, `>1.5E+05`, `4.5E+04 est.`, `TNTC`
- เลขนัยสำคัญตามโหมดที่เลือก (ISO/FDA = 2 หลัก, General = 1 หลัก — ดูตารางข้อ 5)
- แนบหน่วยตามฟอร์ม/ชนิดตัวอย่าง: `cfu/g`, `cfu/100ml`, `MPN/100ml`, `cfu/cm²`, `cfu/swab`
- นิยาม token ตามฟอร์ม: `TNTC` = Too Numerous To Count, `N` = Not detected, `est.` = Estimate count

## 6. Requirement ผลลัพธ์ + Workflow

### 6.1 Output
- คืนไฟล์เดิม (XLSX/CSV) ที่เติม `Calculated count`, `Results`, `Remark` แล้ว — **คงเลย์เอาต์/ลำดับแถวเดิม** (wide format)
- แสดงตารางผลบนหน้าเว็บให้ตรวจก่อน download (highlight แถวที่เป็น special case / est. / นอกช่วง / TNTC)
- ดาวน์โหลดได้ทั้งไฟล์ผลและ (ทางเลือก) รายงานสรุป
- เติมช่อง `Reported by` / `Approved by` + วันที่ ตาม workflow (ฟอร์ม LF07-05-22 มีช่องนี้อยู่แล้ว)

### 6.2 Workflow อนุมัติ (required) ✅ ข้อ 6
สถานะเอกสาร: `Draft → Submitted → Approved → Rejected`
1. Lab staff upload + แปลผล → ระบบสร้างผล สถานะ **Draft/Submitted** (บันทึกผู้ทำ + เวลา)
2. Reviewer/Approver ตรวจ → **Approve** (ล็อกผล, ออกไฟล์รายงานพร้อม Approved by) หรือ **Reject** พร้อมเหตุผลกลับไปแก้
3. ผลที่ Approved แล้วห้ามแก้ ยกเว้นเปิด revision ใหม่ (เก็บประวัติทุกเวอร์ชัน)
4. บันทึก audit trail ทุก action (ใคร/เมื่อไร/มาตรฐาน+พารามิเตอร์ที่ใช้) — รองรับ ISO/IEC 17025

## 7. Non-Functional Requirements

- **Traceability/Audit:** เก็บ log ว่าใครแปลผลไฟล์ไหน ด้วยมาตรฐาน/พารามิเตอร์ใด เวลาใด (สำคัญต่อ ISO 17025)
- **ความถูกต้อง:** ผลการคำนวณต้อง reproducible; มีชุด test cases จากตัวอย่างในเอกสารเป็น regression test
- **ความปลอดภัย:** จำกัดสิทธิ์ผู้ใช้; ไฟล์ผลไม่ควรถูกแก้โดยไม่บันทึก
- **Usability:** ผู้ใช้เป็น lab staff — flow ต้องเรียบง่าย (upload → เลือก config → ตรวจ → download)
- **Performance:** รองรับไฟล์ระดับหลายร้อยแถว/batch ได้ในไม่กี่วินาที

## 8. ตัวอย่าง Test Cases (จากเอกสาร — ใช้เป็น acceptance)

| # | Input | มาตรฐาน | ผลที่คาด |
|---|---|---|---|
| 1 | 10⁻²=135, 10⁻³=14 | ISO | `1.4E+04` |
| 2 | 10⁻¹=8, 10⁻²=1 | ISO | `82 est.` |
| 3 | 10⁻¹=2, 10⁻²=0 | ISO | `<40` |
| 4 | 10⁻¹=0, 10⁻²=0 | ISO | `<10` |
| 5 | 10⁻²>150, 10⁻³>150 | ISO | `>1.5E+05` |
| 6 | 10⁻²=TNTC, 10⁻³=120 | ISO | `1.2E+05 est.` |
| 7 | 1:100=232&244, 1:1000=33&28 | FDA BAM | `24,000` (2 sig fig) |
| 8 | EL26-00124/1: D0.1=125, D0.01=15 | 3.General | Calc 1250 & 1500 |
| 9 | Duplicate D0.1=15/16, D0.01=4/4 | 3.General | `1.6E+02` (ค่ามากสุด) |

## 9. ข้อสรุปการตัดสินใจ (Resolved — ยืนยันแล้ว 2026-07-05)

| # | ประเด็น | ข้อสรุป |
|---|---|---|
| 1 | เลขนัยสำคัญ | ISO 7218 & FDA BAM = **2 หลัก**; โหมด General = **1 หลัก** (ผูกกับมาตรฐานที่เลือก — ดูตารางข้อ 5) |
| 2 | V, n₁, n₂ | **ผู้ใช้กรอกเอง** เมื่อเลือก ISO หรือ BAM (ไม่ hard-code) |
| 3 | จับคู่ Duplicate | ดูจาก suffix **`No.1`, `No.2`** ของ Lab No. เดียวกัน → รายงานค่ามากสุด |
| 4 | หลาย analyte | **คงเลย์เอาต์ worksheet เดิม (wide format)** ไม่แปลงเป็น long |
| 5 | Template ไฟล์ | รองรับ worksheet เดิมโดยตรง (`LF07-05-22`, `LM 7.2-04`) ผ่าน template adapter; ไฟล์ปลดล็อกแล้ว — layout ยืนยันในข้อ 4.1 |
| 6 | Workflow อนุมัติ | **required** — Draft→Submitted→Approved/Rejected + audit trail (ดูข้อ 6.2) |
| 7 | ISO 7218:2024 | ยืนยันเป็นฉบับล่าสุด — ใช้สูตร/ช่วงตาม docx |

## 10. Design artifacts (ทำแล้ว) & ขั้นถัดไป

**ทำแล้ว:**
1. ✅ Flow diagram + ER/data model → `Requirement/diagrams.md` (mermaid)
2. ✅ Prototype interpretation engine + acceptance test **9/9 ผ่าน** → `prototype/` (`interpretation_engine.py`, `test_engine.py`)
3. ✅ Mapping method ↔ standard ↔ ช่วงนับ ↔ หน่วย → `prototype/method_config.yaml`

4. ✅ I/O layer (CSV/XLSX read → process → write คงเลย์เอาต์) → `prototype/io_layer.py` (test 26/26 ผ่าน)
5. ✅ Web UI (upload → config → review → approve/reject → download + audit trail) → `webapp/` (Flask, ยืนยัน end-to-end)

**ขั้นถัดไป (full build):**
- Template adapter ผูกกับ `LF07-05-22` / `LM 7.2-04` layout จริง (column-index mapping)
- FDA special cases (out-of-range → EAPC) แบบเต็ม
- เปลี่ยน batch store in-memory → DB + auth/role/login จริง (ตาม ER ข้อ 10)
- ขยายชุด regression test จากไฟล์งานจริง

---
*SRS v0.3 — ปิด Open Issues 7 ข้อ + prototype engine/IO/Web UI ทำงาน end-to-end*
