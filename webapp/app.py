"""
Web app — แปลผลการทดสอบเชื้อจุลินทรีย์ (DB-backed + auth, พร้อม deploy Vercel serverless)
Flow: login → upload → เลือกมาตรฐาน/กรอก V,n,ช่วงนับ → review → approve/reject → download
State อยู่ใน DB (stateless serverless): เก็บไฟล์ต้นฉบับ+ผลใน Batch, session ผ่าน signed cookie
Reuse: prototype/interpretation_engine.py + io_layer.py (ไม่แตะ logic)
"""
from __future__ import annotations
import io
import json
import os
import re
import sys
import tempfile
import uuid

import pandas as pd
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user, login_required

try:
    from dotenv import load_dotenv       # โหลด .env ตอน dev (บน Vercel ใช้ env จริง)
    load_dotenv()
except ImportError:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "prototype"))
sys.path.insert(0, _HERE)
from io_layer import (read_input, process, STANDARDS,  # noqa: E402
                      can_write_back, write_back_template)
from models import Batch, db                            # noqa: E402
from auth import bp as auth_bp, init_auth               # noqa: E402

TEMPLATE_FORM = os.path.join(_HERE, "static", "LF07-05-22_template.xlsx")
TEMPLATE_FORM_NAME = "LF07-05-22 Plate count template.xlsx"
SPECIAL_TOKENS = ("est.", "TNTC", "<", ">")


def _database_url() -> str:
    # รับได้ทั้ง DATABASE_URL (ตั้งเอง/Neon) และ POSTGRES_URL (Vercel Storage ตั้งให้อัตโนมัติ)
    url = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()
    if not url:
        # ไม่มี DATABASE_URL → SQLite ใน temp dir (Vercel filesystem read-only ยกเว้น /tmp)
        # หมายเหตุ: บน serverless นี่คือ ephemeral (ข้อมูลหายทุก cold start) — production ต้องตั้ง DATABASE_URL
        return "sqlite:///" + os.path.join(tempfile.gettempdir(), "microbial_local.db")
    if url.startswith("postgres://"):                    # Neon/Heroku ใช้ postgres:// → SQLAlchemy ต้อง postgresql://
        url = "postgresql://" + url[len("postgres://"):]
    return url


def create_app() -> Flask:
    # instance_path/root_path ระบุชัด — กัน Flask เรียก os.getcwd() (ล้มใน sandbox/serverless)
    app = Flask(__name__, instance_path=_HERE, root_path=_HERE)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
    db_url = _database_url()
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if db_url.startswith("postgresql"):                  # serverless: อย่า pool ค้าง connection
        from sqlalchemy.pool import NullPool
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"poolclass": NullPool, "pool_pre_ping": True}

    init_auth(app)
    app.register_blueprint(auth_bp)
    # ห่อทั้ง db.init_app + create_all + seed ด้วย try/except กัน import ล้มทั้งฟังก์ชัน
    # (Flask-SQLAlchemy 3.x สร้าง engine ตั้งแต่ init_app → URL ผิด/driver พังจะ crash ที่นี่)
    # ถ้า DB มีปัญหา → log ใน Vercel logs แล้วปล่อยแอปขึ้น (เห็น error ชัดกว่า FUNCTION_INVOCATION_FAILED)
    try:
        db.init_app(app)
        with app.app_context():
            db.create_all()
            _seed_user()
    except Exception as e:  # noqa: BLE001
        scheme = db_url.split(":", 1)[0]
        print(f"[startup] DB init failed (scheme={scheme}): {e}", file=sys.stderr)
    return app


def _seed_user():
    """สร้าง user เริ่มต้นจาก env (idempotent, ข้ามถ้ามีอยู่แล้ว) — password เก็บใน env ไม่ commit ลง repo
    - SEED_USERNAME (ดีฟอลต์ cpffoodlab) + SEED_PASSWORD : user เดี่ยว
    - SEED_USERS : JSON list เพิ่มหลาย user เช่น [{"username":"x","password":"y"}, ...]"""
    from models import User
    wanted = [(os.environ.get("SEED_USERNAME", "cpffoodlab"),
               os.environ.get("SEED_PASSWORD"), os.environ.get("SEED_EMAIL"))]
    raw = os.environ.get("SEED_USERS")
    if raw:
        try:
            for it in json.loads(raw):
                wanted.append((it.get("username"), it.get("password"), it.get("email")))
        except Exception as e:  # noqa: BLE001
            print(f"[seed] SEED_USERS parse failed: {e}", file=sys.stderr)

    added = 0
    for uname, pw, email in wanted:
        if not uname or not pw:
            continue
        if db.session.query(User).filter_by(username=uname).first():
            continue
        u = User(username=uname, email=email)
        u.set_password(pw)
        db.session.add(u)
        added += 1
    if added:
        db.session.commit()


app = create_app()


# ---------------------------------------------------------------- helpers
def _run_pipeline(orig_bytes: bytes, filename: str, standard: str, V, n_per, rng):
    """เขียน bytes ลงไฟล์ชั่วคราว (/tmp) แล้ว read_input+process — คืน (result_df, meta)"""
    suffix = os.path.splitext(filename)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tf.write(orig_bytes)
        path = tf.name
    try:
        df = read_input(path)
        meta = df.attrs.get("template")
        result_df = process(df, standard, V=V, n_per=n_per, range_override=rng)
        return result_df, meta
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _owned_batch(bid: str) -> Batch:
    b = db.session.get(Batch, bid)
    if not b or b.user_id != current_user.id:
        abort(404)
    return b


# ---------------------------------------------------------------- routes
@app.route("/")
@login_required
def index():
    batches = (db.session.query(Batch)
               .filter_by(user_id=current_user.id)
               .order_by(Batch.created_at.desc()).all())
    return render_template("upload.html", standards=STANDARDS, batches=batches)


@app.route("/form/template")
@login_required
def form_template():
    return send_file(TEMPLATE_FORM, as_attachment=True, download_name=TEMPLATE_FORM_NAME,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("กรุณาเลือกไฟล์ CSV หรือ XLSX")
        return redirect(url_for("index"))

    standard = request.form.get("standard", "ISO7218")
    V = float(request.form.get("V") or 1)
    n_per = int(request.form.get("n_per") or 1)
    lo, hi = request.form.get("range_lo"), request.form.get("range_hi")
    rng = (int(lo), int(hi)) if lo and hi else None

    orig_bytes = f.read()
    try:
        result_df, _ = _run_pipeline(orig_bytes, f.filename, standard, V, n_per, rng)
    except Exception as e:  # noqa: BLE001
        flash(f"ประมวลผลไม่สำเร็จ: {e}")
        return redirect(url_for("index"))

    cols = list(result_df.columns)
    rows = result_df.fillna("").to_dict("records")
    final_rng = rng or STANDARDS[standard]["countable_range"]
    b = Batch(
        id=uuid.uuid4().hex[:8], user_id=current_user.id, filename=f.filename,
        standard=standard, v=V, n_per=n_per, range_lo=final_rng[0], range_hi=final_rng[1],
        status="Submitted", orig_bytes=orig_bytes,
        result_json=json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False),
    )
    b.add_audit("Upload & interpret", current_user.username,
                f"{standard}, V={V}, n={n_per}, {len(rows)} rows")
    db.session.add(b)
    db.session.commit()
    return redirect(url_for("review", bid=b.id))


@app.route("/batch/<bid>")
@login_required
def review(bid):
    b = _owned_batch(bid)
    data = json.loads(b.result_json)
    rows = data["rows"]
    # เส้นแบ่งระหว่าง Lab No. ที่ต่างกัน (base ตัด suffix No.X) → True = แถวสุดท้ายของ Lab No. นั้น
    def _lab_base(lc):
        return re.sub(r"\s*N[o0]\.?\s*\d+\s*$", "", str(lc), flags=re.I).strip()
    dividers = [(i + 1 >= len(rows)) or (_lab_base(r.get("lab_code", "")) != _lab_base(rows[i + 1].get("lab_code", "")))
                for i, r in enumerate(rows)]
    return render_template("review.html", b=b, rows=rows, dividers=dividers,
                           columns=data["columns"], special=SPECIAL_TOKENS,
                           editable=(b.status != "Approved"))


@app.route("/batch/<bid>/<action>", methods=["POST"])
@login_required
def decide(bid, action):
    b = _owned_batch(bid)
    if action == "approve":
        b.status = "Approved"
        b.add_audit("Approve", current_user.username, request.form.get("note", ""))
    elif action == "reject":
        b.status = "Rejected"
        b.add_audit("Reject", current_user.username, request.form.get("note", ""))
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("review", bid=bid))


@app.route("/batch/<bid>/edit", methods=["POST"])
@login_required
def edit_cell(bid):
    """แก้ค่า dilution/count/remark แบบ manual (double-click) — บันทึกลง result_json
    - แก้ dilution/count → คำนวณ + แปลผลใหม่ทั้ง batch ตามค่าใหม่
      และบันทึกประวัติการแก้ไข (จาก→เป็น) ลงช่องหมายเหตุ (remark) ของแถวที่แก้อัตโนมัติ
    - แก้ remark → แก้ข้อความหมายเหตุตรง ๆ (ไม่คำนวณใหม่)"""
    b = _owned_batch(bid)
    if b.status == "Approved":                           # อนุมัติแล้ว ล็อกไม่ให้แก้
        return {"ok": False, "error": "อนุมัติแล้ว แก้ไม่ได้"}, 403
    p = request.get_json(silent=True) or {}
    row, col = p.get("row"), p.get("col")
    val = "" if p.get("value") is None else str(p.get("value")).strip()
    if col not in ("dilution", "count", "remark") or not isinstance(row, int):
        return {"ok": False, "error": "bad request"}, 400
    data = json.loads(b.result_json)
    rows = data["rows"]
    if not (0 <= row < len(rows)):
        return {"ok": False, "error": "row out of range"}, 400
    old = str(rows[row].get(col, "") or "")
    rows[row][col] = val

    recalced = False
    if col in ("dilution", "count"):                     # แก้ dilution/count → คำนวณ/แปลผลใหม่ทั้ง batch
        # เก็บประวัติการแก้ไขเดิม (segment ที่ขึ้นต้น "แก้ไข") ต่อแถว ก่อน recalc จะเขียนทับ remark
        hist = {}
        for i, r in enumerate(rows):
            segs = [s.strip() for s in str(r.get("remark", "") or "").split("|")
                    if s.strip().startswith("แก้ไข")]
            if segs:
                hist[i] = segs
        indf = pd.DataFrame(rows)[["lab_code", "analyte", "dilution", "count"]].copy()
        for _c in ("calculated", "result", "remark"):
            indf[_c] = ""
        newdf = process(indf, b.standard, V=b.v, n_per=b.n_per, range_override=b.rng)
        rows = newdf.fillna("").to_dict("records")
        data["columns"] = list(newdf.columns)
        recalced = True
        # เพิ่มประวัติใหม่ของแถวที่แก้ แล้วนำประวัติทั้งหมด (เดิม+ใหม่) กลับไปต่อท้าย remark
        label = "Dilution" if col == "dilution" else "count"
        hist.setdefault(row, []).append(f"แก้ไข {label} จาก {old or '-'} เป็น {val or '-'}")
        for i, segs in hist.items():
            cur = str(rows[i].get("remark", "") or "").strip()
            joined = " | ".join(segs)
            rows[i]["remark"] = f"{cur} | {joined}" if cur else joined
    data["rows"] = rows
    b.result_json = json.dumps(data, ensure_ascii=False)
    b.add_audit("Manual edit", current_user.username, f"{col}[{row}]: {old!r} → {val!r}")
    db.session.commit()
    return {"ok": True, "value": val, "reload": recalced}


@app.route("/batch/<bid>/download")
@login_required
def download(bid):
    b = _owned_batch(bid)
    data = json.loads(b.result_json)                     # ใช้ค่าที่อาจถูกแก้มือ (ไม่ใช่คำนวณใหม่)
    edited_df = pd.DataFrame(data["rows"]).reindex(columns=data["columns"]).fillna("")

    # เขียน orig_bytes ลงไฟล์ชั่วคราว แล้วคงไว้จน write-back เสร็จ (write_back เปิด meta["path"] ซ้ำ)
    suffix = os.path.splitext(b.filename)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tf.write(b.orig_bytes)
        path = tf.name
    buf = io.BytesIO()
    try:
        meta = read_input(path).attrs.get("template")    # meta["path"] = path (ยังไม่ถูกลบ)
        if can_write_back(meta):                          # เขียนกลับลงฟอร์มเดิม คงเลย์เอาต์/checkbox
            write_back_template(edited_df, meta, buf)
        else:                                             # fallback: คอลัมน์ canonical
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                edited_df.to_excel(w, index=False)
                ws = next(iter(w.sheets.values()))
                ws.print_title_rows = "1:1"               # ทำซ้ำหัวตารางทุกหน้าเมื่อพิมพ์หลายหน้า
                _name = os.path.splitext(b.filename)[0]
                for _f in (ws.oddFooter, ws.evenFooter):  # footer ทุกหน้า: ชื่อไฟล์ + เลขหน้า
                    _f.left.text = _name
                    _f.right.text = "หน้า &P/&N"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    buf.seek(0)
    name = os.path.splitext(b.filename)[0] + "_result.xlsx"
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    # load_dotenv=False: กัน Flask CLI เรียก os.getcwd() (ล้มใน sandbox preview)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False, load_dotenv=False)
