import asyncio
import logging
import os
import threading

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import db

log = logging.getLogger(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "yamac_iranland").lstrip("@")
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "https://family.merikogames.ir").rstrip("/")


def is_admin(uid):
    user = db.get_user(uid)
    return bool(user and (user["is_admin"] or user["is_super_admin"]))


def keyboard(uid):
    dashboard_button = KeyboardButton("📊 داشبورد", web_app=WebAppInfo(url=WEB_BASE_URL))
    rows = [
        [KeyboardButton("⛽ ثبت منابع"), KeyboardButton("👤 پروفایل من")],
        [KeyboardButton("🏆 رتبه‌بندی"), KeyboardButton("🆘 پشتیبانی")],
        [dashboard_button],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def dashboard_inline_keyboard():
    """Inline Mini App launcher, shown on /start and /dashboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 باز کردن داشبورد", web_app=WebAppInfo(url=WEB_BASE_URL))]
    ])


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "برای ورود مستقیم، دکمهٔ زیر را بزنید:",
        reply_markup=dashboard_inline_keyboard(),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    await update.effective_message.reply_text(
        "✅ خوش آمدی!\nبرای باز کردن داشبورد، دکمهٔ زیر را بزن:",
        reply_markup=dashboard_inline_keyboard(),
    )
    await update.effective_message.reply_text(
        "از دکمه‌های پایین برای استفاده از ربات استفاده کن 👇",
        reply_markup=keyboard(user.id),
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await update.effective_message.reply_text("ابتدا /start را بفرست.")
        return
    balance = db.get_user_balance(uid)
    balance_text = f"🔵 اعتبار: +{balance}" if balance > 0 else f"🔴 بدهی: {balance}" if balance < 0 else "🟢 تسویه"
    leave = f"🏖 مرخصی تا: {user['leave_until']}\n" if user["leave_until"] else ""
    await update.effective_message.reply_text(
        f"👤 {user['first_name']}\n\n⛽ کل سوخت معادل: {user['total_fuel'] or 0}\n"
        f"🟡 گوگرد: {user['total_sulfur'] or 0}\n🚀 راکت: {user['total_rocket'] or 0}\n"
        f"💣 سی‌فور: {user['total_c4'] or 0}\n💰 {balance_text}\n"
        f"⚠️ جریمه: {user['penalty'] or 0}\n{leave}🆔 {uid}"
    )


async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_leaderboard()
    text = "🏆 برترین‌ها\n\n" + "\n".join(
        f"{index}. {user['first_name'] or user['user_id']} : {user['total']}"
        for index, user in enumerate(users, 1)
    )
    await update.effective_message.reply_text(text if users else "هنوز آماری ثبت نشده است.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("روش استفاده: /broadcast متن پیام")
        return
    sent = 0
    for user in db.get_all_users():
        if user["is_clan_member"] and not user["is_banned"]:
            try:
                await context.bot.send_message(user["user_id"], text)
                sent += 1
            except Exception:
                log.exception("Could not send broadcast to user %s", user["user_id"])
    await update.effective_message.reply_text(f"✅ پیام برای {sent} نفر ارسال شد.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return
    uid, text = update.effective_user.id, message.text.strip()
    state = context.user_data.get("delivery_step")
    if text == "👤 پروفایل من":
        await profile_command(update, context)
    elif text == "🏆 رتبه‌بندی":
        await rank_command(update, context)
    elif text == "🆘 پشتیبانی":
        await message.reply_text("برای ارتباط با پشتیبانی:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 پیام به پشتیبانی", url=f"https://t.me/{SUPPORT_USERNAME}")]]))
    elif text == "📊 داشبورد":
        await dashboard_command(update, context)
    elif text == "🎛 پنل مدیریت":
        if is_admin(uid):
            await dashboard_command(update, context)
    elif text == "⛽ ثبت منابع":
        if not db.get_user(uid):
            db.add_user(uid, update.effective_user.username, update.effective_user.first_name)
        if db.get_user(uid)["is_banned"]:
            await message.reply_text("حساب شما مسدود است.")
            return
        context.user_data["delivery"] = {}
        context.user_data["delivery_step"] = "fuel"
        await message.reply_text("چند سوخت آوردی؟ (اگر صفر بود 0 بزن)")
    elif state:
        try:
            value = int(text)
            if value < 0:
                raise ValueError
        except ValueError:
            await message.reply_text("❌ فقط عدد صحیح صفر یا بزرگ‌تر وارد کن.")
            return
        delivery = context.user_data.setdefault("delivery", {})
        steps = [("fuel", "sulfur", "چند گوگرد آوردی؟ (اگر نداری 0 بزن)"),
                 ("sulfur", "rocket", "چند راکت آوردی؟ (اگر نداری 0 بزن)"),
                 ("rocket", "c4", "چند سی‌فور آوردی؟ (اگر نداری 0 بزن)")]
        if state != "c4":
            delivery[state] = value
            _, next_step, prompt = next(item for item in steps if item[0] == state)
            context.user_data["delivery_step"] = next_step
            await message.reply_text(prompt)
            return
        delivery["c4"] = value
        fuel, sulfur, rocket, c4 = (delivery.get(key, 0) for key in ("fuel", "sulfur", "rocket", "c4"))
        if not any((fuel, sulfur, rocket, c4)):
            context.user_data.pop("delivery_step", None)
            context.user_data.pop("delivery", None)
            await message.reply_text("❌ حداقل یکی از منابع باید بیشتر از صفر باشد.")
            return
        total = db.submit_delivery(uid, fuel, sulfur, rocket, c4)
        context.user_data.pop("delivery_step", None)
        context.user_data.pop("delivery", None)
        await message.reply_text(
            f"✅ منابع ثبت شد:\n⛽ سوخت خام: {fuel}\n🟡 گوگرد: {sulfur} (معادل {sulfur // 2} سوخت)\n"
            f"🚀 راکت: {rocket} (معادل {rocket * 50} سوخت)\n💣 سی‌فور: {c4} (معادل {c4 * 75} سوخت)\n\n"
            f"📊 مجموع معادل: {total} سوخت\n⏳ در انتظار تایید ادمین..."
        )


def _run_polling():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("dashboard", dashboard_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("rank", rank_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)
    finally:
        asyncio.set_event_loop(None)
        if not loop.is_closed():
            loop.close()


def start():
    if not TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN is not set; bot is disabled")
        return
    if getattr(start, "started", False):
        return
    start.started = True
    threading.Thread(target=_run_polling, name="telegram-bot", daemon=True).start()
