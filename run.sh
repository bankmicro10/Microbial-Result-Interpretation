#!/usr/bin/env bash
# รัน Microbial Result Interpretation web app บน macOS / Linux
# วิธีใช้:  bash run.sh   (หรือ  chmod +x run.sh ครั้งเดียว แล้ว ./run.sh)
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

echo "==> ตรวจ/ติดตั้ง library ที่จำเป็น"
$PY -m pip install -q -r requirements.txt

echo "==> เปิดเว็บที่ http://127.0.0.1:5001  (กด Ctrl+C เพื่อหยุด)"
$PY webapp/app.py
