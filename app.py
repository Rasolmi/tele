import hashlib
import hmac
import json
import os
import time
from functools import wraps
from urllib.parse import parse_qsl

import jdatetime
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

import bot
import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24,
)
MINI_APP_URL = os.environ.get("WEB_BASE_URL", "https://family.merikogames.ir").rstrip("/")
db.init()
bot.start()


def telegram_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("telegram_user_id")
        if not user_id:
            abort(401, description="لطفاً داشبورد را از داخل تلگرام باز کنید.")
        user = db.get_user(user_id)
        if not user:
            session.clear()
            abort(401)
        if not (user["is_admin"] or user["is_super_admin"]):
            abort(403, description="این بخش فقط برای مدیران است.")
        return view(*args, **kwargs)
    return wrapped


def telegram_user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("telegram_user_id")
        if not user_id or not db.get_user(user_id):
            abort(401, description="لطفاً داشبورد را از داخل تلگرام باز کنید.")
        return view(*args, **kwargs)
    return wrapped


def validate_telegram_init_data(init_data):
    """Validate Telegram Mini App initData using the bot token; never trust client user IDs."""
    if not bot.TOKEN or not init_data:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        received_hash = data.pop("hash", "")
        if not received_hash:
            return None
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret_key = hmac.new(b"WebAppData", bot.TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        auth_date = int(data.get("auth_date", "0"))
        now = time.time()
        if auth_date > now + 30 or now - auth_date > 86400:
            return None
        user = json.loads(data.get("user", "{}"))
        if not isinstance(user.get("id"), int):
            return None
        return user
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


@app.post("/telegram-auth")
def telegram_auth():
    payload = request.get_json(silent=True) or {}
    telegram_user = validate_telegram_init_data(payload.get("initData", ""))
    if not telegram_user:
        return jsonify({"ok": False, "error": "اطلاعات ورود تلگرام معتبر نیست؛ داشبورد را از داخل ربات باز کنید."}), 401
    db.add_user(telegram_user["id"], telegram_user.get("username", ""),
                telegram_user.get("first_name", ""))
    user = db.get_user(telegram_user["id"])
    if user["is_banned"]:
        return jsonify({"ok": False, "error": "حساب شما مسدود است."}), 403
    session.clear()
    session.permanent = True
    session["telegram_user_id"] = telegram_user["id"]
    return jsonify({"ok": True, "is_admin": bool(user["is_admin"] or user["is_super_admin"])})


def form_int(name, default=None):
    raw = request.form.get(name)
    if raw is None and default is not None:
        return default
    value = int(raw)
    if value < 0:
        raise ValueError(f"مقدار {name} نمی‌تواند منفی باشد")
    return value


@app.get("/")
@telegram_user_required
def dashboard():
    uid = session["telegram_user_id"]
    current_user = db.get_user(uid)
    is_admin = bool(current_user["is_admin"] or current_user["is_super_admin"])
    common = {"current_user": current_user, "is_admin": is_admin, "mini_app_url": MINI_APP_URL}
    if not is_admin:
        return render_template("index.html", **common,
                               pending=[], approved=[], leaderboard=[], users=[], daily_required=db.DAILY_REQUIRED,
                               profile_balance=db.get_user_balance(uid), profile_history=db.get_user_history(uid))
    return render_template("index.html", **common,
                           users=db.get_all_users(), pending=db.get_pending(),
                           approved=db.get_approved(), leaderboard=db.get_leaderboard(),
                           daily_required=db.DAILY_REQUIRED)


@app.get("/user/<int:uid>")
@telegram_user_required
def user_detail(uid):
    if uid != session["telegram_user_id"]:
        user = db.get_user(session["telegram_user_id"])
        if not (user and (user["is_admin"] or user["is_super_admin"])):
            abort(403)
    user = db.get_user(uid)
    if not user:
        abort(404)
    return render_template("user_detail.html", user=user,
                           history=db.get_user_history(uid), balance=db.get_user_balance(uid),
                           daily_required=db.DAILY_REQUIRED)


@app.post("/approve/<int:delivery_id>")
@telegram_admin_required
def approve(delivery_id):
    if not db.approve_delivery(delivery_id):
        flash("این مورد وجود ندارد یا قبلاً تایید شده است.", "error")
    else:
        flash("تحویل با موفقیت تایید شد.", "success")
    return redirect(url_for("dashboard"))


@app.post("/make_admin/<int:uid>")
@telegram_admin_required
def make_admin(uid):
    db.update_user(uid, is_admin=1)
    return redirect(url_for("dashboard"))


@app.post("/remove_admin/<int:uid>")
@telegram_admin_required
def remove_admin(uid):
    user = db.get_user(uid)
    if user and not user["is_super_admin"]:
        db.update_user(uid, is_admin=0)
    return redirect(url_for("dashboard"))


@app.post("/leave/<int:uid>")
@telegram_admin_required
def leave(uid):
    try:
        days = form_int("days")
        until = (jdatetime.date.today() + jdatetime.timedelta(days=days)).strftime("%Y/%m/%d")
        db.update_user(uid, leave_until=until)
        flash("مرخصی ثبت شد.", "success")
    except (ValueError, TypeError) as exc:
        flash(f"مقدار روز معتبر نیست: {exc}", "error")
    return redirect(url_for("dashboard"))


@app.post("/penalty/<int:uid>")
@telegram_admin_required
def penalty(uid):
    try:
        amount = form_int("amount")
        user = db.get_user(uid)
        if user:
            db.update_user(uid, penalty=(user["penalty"] or 0) + amount)
            flash("جریمه ثبت شد.", "success")
    except (ValueError, TypeError) as exc:
        flash(f"مقدار جریمه معتبر نیست: {exc}", "error")
    return redirect(url_for("dashboard"))


@app.post("/kick/<int:uid>")
@telegram_admin_required
def kick(uid):
    db.update_user(uid, is_clan_member=0)
    return redirect(url_for("dashboard"))


@app.post("/ban/<int:uid>")
@telegram_admin_required
def ban(uid):
    db.update_user(uid, is_banned=1, is_clan_member=0)
    return redirect(url_for("dashboard"))


@app.post("/unban/<int:uid>")
@telegram_admin_required
def unban(uid):
    db.update_user(uid, is_banned=0)
    return redirect(url_for("dashboard"))


@app.post("/manual_delivery")
@telegram_admin_required
def manual_delivery():
    try:
        uid = form_int("user_id")
        values = [form_int(name, 0) for name in ("fuel", "sulfur", "rocket", "c4")]
        if not any(values):
            raise ValueError("حداقل یکی از منابع باید بیشتر از صفر باشد")
        total = db.add_manual_delivery(uid, *values)
        flash(f"منابع دستی ثبت شد؛ معادل {total} سوخت.", "success")
    except (ValueError, TypeError) as exc:
        flash(f"خطا در ثبت منابع: {exc}", "error")
    return redirect(url_for("dashboard"))


@app.get("/health")
def health():
    return {"ok": True, "bot_enabled": bool(bot.TOKEN)}
