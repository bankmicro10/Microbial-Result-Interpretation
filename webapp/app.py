"""
Web UI (prototype) — Application แปลผลการทดสอบเชื้อจุลินทรีย์
Flow: upload → เลือกมาตรฐาน/กรอก V,n + ช่วงนับ → review → approve/reject → download
Reuse: prototype/interpretation_engine.py + io_layer.py
"""
from __future__ import annotations
import io
import os
import sys
import uuid
from datetime import datetime

import pandas as pd
from flask import (Flask, request, redirect, url_for, render_template,
                   send_file, abort, flash)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "prototype"))
from io_layer import (read_input, process, STANDARDS,  # noqa: E402
                      can_write_back, write_back_template)

# preview อาจ spawn ด้วย cwd เดิม (โฟลเดอร์ TCC) — chdir เข้าที่ตัวเองกัน os.getcwd() ล้ม
os.chdir(_HERE)
app = Flask(__name__, instance_path=_HERE)
app.secret_key = "prototype-microbial"

UPLOAD_DIR = os.path.join(_HERE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ฟอร์มมาตรฐานให้ผู้ใช้โหลดไปกรอก แล้วอัปกลับ (write-back คง checkbox/เลย์เอาต์)
TEMPLATE_FORM = os.path.join(_HERE, "static", "LF07-05-22_template.xlsx")
TEMPLATE_FORM_NAME = "LF07-05-22 Plate count template.xlsx"

# in-memory batch store (prototype) — full build ใช้ DB
BATCHES: dict[str, dict] = {}
CURRENT_USER = "lab.staff"          # prototype: จำลอง login
SPECIAL_TOKENS = ("est.", "TNTC", "<", ">")


def audit(batch, action, note=""):
    batch["log"].append({
        "action": action, "actor": CURRENT_USER,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "note": note,
    })


@app.route("/")
def index():
    return render_template("upload.html", standards=STANDARDS,
                           batches=sorted(BATCHES.values(),
                                          key=lambda b: b["created"], reverse=True))


@app.route("/form/template")
def form_template():
    """ดาวน์โหลดฟอร์มมาตรฐาน LF07-05-22 (เปล่า) ไปกรอก"""
    return send_file(TEMPLATE_FORM, as_attachment=True,
                     download_name=TEMPLATE_FORM_NAME,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("กรุณาเลือกไฟล์ CSV หรือ XLSX")
        return redirect(url_for("index"))

    standard = request.form.get("standard", "ISO7218")
    V = float(request.form.get("V") or 1)
    n_per = int(request.form.get("n_per") or 1)
    rng = None
    lo, hi = request.form.get("range_lo"), request.form.get("range_hi")
    if lo and hi:
        rng = (int(lo), int(hi))

    bid = uuid.uuid4().hex[:8]
    src = os.path.join(UPLOAD_DIR, f"{bid}_{f.filename}")
    f.save(src)

    try:
        df = read_input(src)
        meta = df.attrs.get("template")            # ตำแหน่ง cell เดิม สำหรับเขียนกลับ
        result_df = process(df, standard, V=V, n_per=n_per, range_override=rng)
    except Exception as e:  # noqa: BLE001
        flash(f"ประมวลผลไม่สำเร็จ: {e}")
        return redirect(url_for("index"))

    BATCHES[bid] = {
        "id": bid, "filename": f.filename, "standard": standard,
        "V": V, "n_per": n_per, "range": rng or STANDARDS[standard]["countable_range"],
        "status": "Submitted", "df": result_df, "meta": meta, "log": [],
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    audit(BATCHES[bid], "Upload & interpret",
          f"{standard}, V={V}, n={n_per}, {len(result_df)} rows")
    return redirect(url_for("review", bid=bid))


@app.route("/batch/<bid>")
def review(bid):
    b = BATCHES.get(bid) or abort(404)
    rows = b["df"].fillna("").to_dict("records")
    return render_template("review.html", b=b, rows=rows,
                           columns=[c for c in b["df"].columns],
                           special=SPECIAL_TOKENS)


@app.route("/batch/<bid>/<action>", methods=["POST"])
def decide(bid, action):
    b = BATCHES.get(bid) or abort(404)
    if action == "approve":
        b["status"] = "Approved"
        audit(b, "Approve", request.form.get("note", ""))
    elif action == "reject":
        b["status"] = "Rejected"
        audit(b, "Reject", request.form.get("note", ""))
    else:
        abort(400)
    return redirect(url_for("review", bid=bid))


@app.route("/batch/<bid>/download")
def download(bid):
    b = BATCHES.get(bid) or abort(404)
    buf = io.BytesIO()
    meta = b.get("meta")
    if can_write_back(meta):                       # เขียนกลับลงฟอร์มเดิม คงเลย์เอาต์
        write_back_template(b["df"], meta, buf)
    else:                                          # fallback: คอลัมน์ canonical
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            b["df"].to_excel(w, index=False)
    buf.seek(0)
    name = os.path.splitext(b["filename"])[0] + "_result.xlsx"
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    # use_reloader=False: กัน reloader restart ซ้ำ (จะไปต่อ path กับ cwd ที่ chdir แล้ว → webapp/webapp/app.py)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
