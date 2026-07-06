#!/usr/bin/env bash
# sync-preview.sh — คัดลอก webapp/ + prototype/ ไปยัง mirror นอก OneDrive
# เหตุผล: preview harness (Claude Code) โดน macOS TCC block อ่านไฟล์ใน CloudStorage/OneDrive ไม่ได้
# source of truth ยังอยู่ในโปรเจกต์นี้เสมอ — mirror ใช้แค่รัน preview
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="${MICROBIAL_PREVIEW_DIR:-$HOME/.microbial-preview}"

mkdir -p "$DST"
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' --exclude 'uploads/*' \
  "$SRC/webapp/"    "$DST/webapp/"
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/prototype/" "$DST/prototype/"

echo "✓ synced → $DST"
echo "  preview: launch.json ชี้ไป $DST/webapp/app.py แล้ว (Claude Code → preview_start)"
