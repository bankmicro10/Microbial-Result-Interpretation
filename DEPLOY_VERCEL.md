# Deploy บน Vercel (public + login)

แอปนี้ถูกแปลงเป็น **stateless serverless** แล้ว: state อยู่ใน Postgres, ไฟล์เก็บใน DB,
session ผ่าน signed cookie, login = username/password + Google OAuth. เอนจินแปลผล (Python) รันเหมือนเดิม

สิ่งที่คุณต้องทำ (ครั้งเดียว) มี 4 ขั้น — ใช้เวลา ~15 นาที

---

## 1) Push โค้ดขึ้น GitHub
```bash
git add -A && git commit -m "Add auth + DB + Vercel serverless"
git push       # ถ้ายังไม่มี remote: สร้าง repo ใน github.com แล้ว git remote add origin <url> && git push -u origin main
```

## 2) สร้าง Postgres ฟรี (Neon)
1. ไป https://neon.tech → sign up (ใช้ GitHub ได้) → New Project
2. คัดลอก **Connection string** (ขึ้นต้น `postgresql://...`) — เลือกแบบ **Pooled connection** (มีคำว่า `-pooler`) เพื่อ serverless
3. เก็บไว้ใช้เป็น `DATABASE_URL`

> หรือใช้ **Vercel Postgres**: ในหน้า Vercel project → Storage → Create Database → Postgres → มันจะ set `DATABASE_URL` ให้อัตโนมัติ

## 3) สร้าง Google OAuth credentials
1. https://console.cloud.google.com → สร้าง/เลือก Project
2. **APIs & Services → OAuth consent screen** → External → กรอกชื่อแอป + email → Save (เพิ่มตัวเองใน Test users ถ้ายังไม่ publish)
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - **Authorized redirect URIs** ใส่: `https://<your-app>.vercel.app/auth/google/callback`
     (ค่อยกลับมาแก้ให้ตรง domain จริงหลัง deploy รอบแรกก็ได้)
4. คัดลอก **Client ID** และ **Client secret** → ใช้เป็น `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

## 4) Deploy บน Vercel
1. https://vercel.com → **Add New → Project** → Import GitHub repo นี้
2. Framework Preset: **Other** (มี `vercel.json` อยู่แล้ว ไม่ต้องตั้ง build command)
3. **Environment Variables** (Settings → Environment Variables) ใส่:
   | Key | Value |
   |---|---|
   | `SECRET_KEY` | สตริงสุ่มยาว ๆ (เช่น `python -c "import secrets;print(secrets.token_hex(32))"`) |
   | `DATABASE_URL` | connection string จาก Neon (ขั้น 2) |
   | `GOOGLE_CLIENT_ID` | จากขั้น 3 |
   | `GOOGLE_CLIENT_SECRET` | จากขั้น 3 |
   | `SEED_USERNAME` | `cpffoodlab` (user เริ่มต้น — สร้างอัตโนมัติครั้งแรก) |
   | `SEED_PASSWORD` | รหัสผ่านที่คุณกำหนด (ตั้งใน env เท่านั้น อย่าเขียนลงไฟล์ใน repo) |
4. กด **Deploy** → ได้ URL `https://<your-app>.vercel.app`
5. กลับไปขั้น 3 ข้อ 3 แก้ **redirect URI** ให้ตรง domain จริง (ถ้ายังไม่ได้ใส่) → Save

เสร็จ! เปิด URL → สมัคร/ล็อกอิน → ใช้งานได้ คนอื่นสมัครเองได้เลย

---

## หมายเหตุ
- **ไม่ตั้ง `GOOGLE_CLIENT_ID/SECRET`** → ปุ่ม Google จะซ่อน ใช้ username/password อย่างเดียวได้
- ตารางใน DB ถูกสร้างอัตโนมัติครั้งแรกที่แอปรัน (`db.create_all()`)
- ขนาด dependency (pandas/numpy/openpyxl) อยู่ในลิมิต Vercel (250 MB) — ถ้าชนลิมิต ตัด `xlrd` ออกได้ (ใช้เฉพาะอ่าน .xls เก่า)
- Dev ในเครื่อง: ไม่ตั้ง `DATABASE_URL` → ใช้ SQLite (`webapp/local.db`) อัตโนมัติ; คัดลอก `.env.example` เป็น `.env` เพื่อใส่ค่าทดสอบ
