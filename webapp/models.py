"""
DB models (SQLAlchemy) — แทน in-memory store เดิม เพื่อให้ทำงานบน serverless (stateless) ได้
- User: สมัคร username/password + login ด้วย Google (google_sub)
- Batch: เก็บไฟล์ต้นฉบับ (bytes) + พารามิเตอร์ + ผลลัพธ์ (JSON) + สถานะ + audit log
ไฟล์เก็บใน DB เลย (xlsx เล็ก ~20-50KB) จึงไม่ต้องใช้ blob service แยก
"""
from __future__ import annotations
import json
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)      # null = login ผ่าน Google อย่างเดียว
    google_sub = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw: str):
        # pbkdf2:sha256 พกพาได้ทุกที่ (scrypt ต้องการ OpenSSL 1.1+ ซึ่งบาง build ไม่มี)
        self.password_hash = generate_password_hash(pw, method="pbkdf2:sha256")

    def check_password(self, pw: str) -> bool:
        return bool(self.password_hash) and check_password_hash(self.password_hash, pw)


class Batch(db.Model):
    __tablename__ = "batches"
    id = db.Column(db.String(12), primary_key=True)              # uuid8
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    standard = db.Column(db.String(40), nullable=False)
    v = db.Column(db.Float, default=1.0)
    n_per = db.Column(db.Integer, default=1)
    range_lo = db.Column(db.Integer)
    range_hi = db.Column(db.Integer)
    status = db.Column(db.String(20), default="Submitted")       # Submitted/Approved/Rejected
    orig_bytes = db.Column(db.LargeBinary, nullable=False)        # ไฟล์ต้นฉบับ (ใช้ตอน write-back)
    result_json = db.Column(db.Text, nullable=False)             # ผลลัพธ์สำหรับแสดงหน้า review
    audit_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="batches")

    # ----- helpers -----
    @property
    def rng(self):
        return (self.range_lo, self.range_hi)

    @property
    def result_rows(self) -> list[dict]:
        return json.loads(self.result_json)

    @property
    def log(self) -> list[dict]:
        return json.loads(self.audit_json or "[]")

    def add_audit(self, action: str, actor: str, note: str = ""):
        entries = self.log
        entries.append({"action": action, "actor": actor, "note": note,
                        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")})
        self.audit_json = json.dumps(entries, ensure_ascii=False)

    @property
    def created(self) -> str:
        return (self.created_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
