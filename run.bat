@echo off
REM รัน Microbial Result Interpretation web app บน Windows
REM วิธีใช้: ดับเบิลคลิกไฟล์นี้ หรือพิมพ์  run.bat  ใน cmd
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py

echo ==^> ตรวจ/ติดตั้ง library ที่จำเป็น
%PY% -m pip install -q -r requirements.txt

echo ==^> เปิดเว็บที่ http://127.0.0.1:5001  (กด Ctrl+C เพื่อหยุด)
%PY% webapp\app.py

pause
