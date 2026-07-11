"""
Auth — สมัคร/ล็อกอินด้วย username+password และล็อกอินด้วย Google (OAuth)
ใช้ Flask-Login (session ผ่าน signed cookie → ทำงานบน serverless ได้) + Authlib
Google จะเปิดใช้เฉพาะเมื่อมี GOOGLE_CLIENT_ID/SECRET ใน env
"""
from __future__ import annotations
import os
import re

from authlib.integrations.flask_client import OAuth
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import LoginManager, current_user, login_user, logout_user

from models import User, db

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
oauth = OAuth()

GOOGLE_CONF = "https://accounts.google.com/.well-known/openid-configuration"


def google_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def init_auth(app):
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "กรุณาเข้าสู่ระบบก่อนใช้งาน"
    oauth.init_app(app)
    if google_enabled():
        oauth.register(
            name="google",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            server_metadata_url=GOOGLE_CONF,
            client_kwargs={"scope": "openid email profile"},
        )


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def _unique_username(base: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "", base) or "user"
    name, i = base, 1
    while db.session.query(User).filter_by(username=name).first():
        i += 1
        name = f"{base}{i}"
    return name


# ---------------------------------------------------------------- username/password
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip() or None
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""
        if len(username) < 3:
            flash("username ต้องยาวอย่างน้อย 3 ตัวอักษร")
        elif len(pw) < 6:
            flash("password ต้องยาวอย่างน้อย 6 ตัวอักษร")
        elif pw != pw2:
            flash("password ยืนยันไม่ตรงกัน")
        elif db.session.query(User).filter_by(username=username).first():
            flash("username นี้ถูกใช้แล้ว")
        elif email and db.session.query(User).filter_by(email=email).first():
            flash("email นี้ถูกใช้แล้ว")
        else:
            u = User(username=username, email=email)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for("index"))
    return render_template("register.html", google=google_enabled())


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        ident = (request.form.get("username") or "").strip()
        pw = request.form.get("password") or ""
        u = (db.session.query(User).filter_by(username=ident).first()
             or db.session.query(User).filter_by(email=ident).first())
        if u and u.check_password(pw):
            login_user(u, remember=True)
            nxt = request.args.get("next")
            return redirect(nxt if nxt and nxt.startswith("/") else url_for("index"))
        flash("username หรือ password ไม่ถูกต้อง")
    return render_template("login.html", google=google_enabled())


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------- Google OAuth
@bp.route("/auth/google")
def google_login():
    if not google_enabled():
        flash("ยังไม่ได้ตั้งค่า Google login")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/auth/google/callback")
def google_callback():
    if not google_enabled():
        return redirect(url_for("auth.login"))
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:  # noqa: BLE001
        flash(f"Google login ไม่สำเร็จ: {e}")
        return redirect(url_for("auth.login"))
    info = token.get("userinfo") or {}
    sub, email = info.get("sub"), info.get("email")
    if not sub:
        flash("Google ไม่ส่งข้อมูลผู้ใช้")
        return redirect(url_for("auth.login"))

    u = db.session.query(User).filter_by(google_sub=sub).first()
    if not u and email:
        u = db.session.query(User).filter_by(email=email).first()
        if u:
            u.google_sub = sub                       # ผูก Google กับบัญชีเดิมที่ email ตรงกัน
    if not u:
        u = User(username=_unique_username((email or "user").split("@")[0]),
                 email=email, google_sub=sub)
        db.session.add(u)
    db.session.commit()
    login_user(u, remember=True)
    return redirect(url_for("index"))
