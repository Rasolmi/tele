import hmac
import os
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import safe_join

import bot
import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
WEB_ADMIN_PASSWORD = os.environ.get("WEB_ADMIN_PASSWORD", "")
db.init()
bot.start()


def web_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not WEB_ADMIN_PASSWORD:
            abort(503, description="برای دسترسی به پنل، متغیر WEB_ADMIN_PASSWORD را تنظیم کنید.")
        auth = request.authorization
        if not auth or not hmac.compare_digest(auth.password or "", WEB_ADMIN_PASSWORD):
            return "برای ورود به پنل، نام کاربری دلخواه و رمز WEB_ADMIN_PASSWORD را وارد کنید.", 401, {
                "WWW-Authenticate": 'Basic realm="Fuel dashboard"'
            }
        return view(*args, **kwargs)
    return wrapped


def form_int(name, default=None):
    raw = request.form.get(name)
    if raw is None and default is not None:
        return default
    value = int(raw)
    if value < 0:
        raise ValueError(f"مقدار {name} نمی‌تواند منفی باشد")
    return value


@app.get("/")
@web_admin_required
def dashboard():
    return render_template(
        "index.html",
        users=db.get_all_users(),
        pending=db.get_pending(),
        approved=db.get_approved(),
        leaderboard=db.get_leaderboard(),
        daily_required=db.DAILY_REQUIRED,
    )


@app.get("/user/<int:uid>")
@web_admin_required
def user_detail(uid):
    user = db.get_user(uid)
    if not user:
        abort(404)
    return render_template("user_detail.html", user=user,
                           history=db.get_user_history(uid),
                           balance=db.get_user_balance(uid),
                           daily_required=db.DAILY_REQUIRED)


@app.post("/approve/<int:delivery_id>")
@web_admin_required
def approve(delivery_id):
    if not db.approve_delivery(delivery_id):
        flash("این مورد وجود ندارد یا قبلاً تایید شده است.", "error")
    else:
        flash("تحویل با موفقیت تایید شد.", "success")
    return redirect(url_for("dashboard"))


@app.post("/make_admin/<int:uid>")
@web_admin_required
def make_admin(uid):
    db.update_user(uid, is_admin=1)
    return redirect(url_for("dashboard"))


@app.post("/remove_admin/<int:uid>")
@web_admin_required
def remove_admin(uid):
    user = db.get_user(uid)
    if user and not user["is_super_admin"]:
        db.update_user(uid, is_admin=0)
    return redirect(url_for("dashboard"))


@app.post("/leave/<int:uid>")
@web_admin_required
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
@web_admin_required
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
@web_admin_required
def kick(uid):
    db.update_user(uid, is_clan_member=0)
    return redirect(url_for("dashboard"))


@app.post("/ban/<int:uid>")
@web_admin_required
def ban(uid):
    db.update_user(uid, is_banned=1, is_clan_member=0)
    return redirect(url_for("dashboard"))


@app.post("/unban/<int:uid>")
@web_admin_required
def unban(uid):
    db.update_user(uid, is_banned=0)
    return redirect(url_for("dashboard"))


@app.post("/manual_delivery")
@web_admin_required
def manual_delivery():
    try:
        uid = form_int("user_id")
        fuel = form_int("fuel", 0)
        sulfur = form_int("sulfur", 0)
        rocket = form_int("rocket", 0)
        c4 = form_int("c4", 0)
        if not any((fuel, sulfur, rocket, c4)):
            raise ValueError("حداقل یکی از منابع باید بیشتر از صفر باشد")
        total = db.add_manual_delivery(uid, fuel, sulfur, rocket, c4)
        flash(f"منابع دستی ثبت شد؛ معادل {total} سوخت.", "success")
    except (ValueError, TypeError) as exc:
        flash(f"خطا در ثبت منابع: {exc}", "error")
    return redirect(url_for("dashboard"))


@app.get("/health")
def health():
    return {"ok": True}


# jdatetime is used for Jalali dates in the panel routes.
import jdatetime
