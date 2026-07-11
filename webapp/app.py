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
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:                                          # dev fallback: SQLite ในเครื่อง
        return "sqlite:///" + os.path.join(_HERE, "local.db")
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

    db.init_app(app)
    init_auth(app)
    app.register_blueprint(auth_bp)
    with app.app_context():
        db.create_all()
    return app


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
    return render_template("review.html", b=b, rows=data["rows"],
                           columns=data["columns"], special=SPECIAL_TOKENS)


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


@app.route("/batch/<bid>/download")
@login_required
def download(bid):
    b = _owned_batch(bid)
    result_df, meta = _run_pipeline(b.orig_bytes, b.filename, b.standard, b.v, b.n_per, b.rng)
    buf = io.BytesIO()
    if can_write_back(meta):                             # เขียนกลับลงฟอร์มเดิม คงเลย์เอาต์/checkbox
        write_back_template(result_df, meta, buf)
    else:                                                # fallback: คอลัมน์ canonical
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            result_df.to_excel(w, index=False)
    buf.seek(0)
    name = os.path.splitext(b.filename)[0] + "_result.xlsx"
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    # load_dotenv=False: กัน Flask CLI เรียก os.getcwd() (ล้มใน sandbox preview)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False, load_dotenv=False)
