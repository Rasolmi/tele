import logging
import os
import threading
import time

import requests

import db

log = logging.getLogger("bot")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

HELP = (
    "ربات تحویل\n"
    "/new مشتری | آدرس - ثبت تحویل جدید\n"
    "/list - آخرین تحویل‌ها\n"
    "/status شناسه - نمایش یک تحویل\n"
    "/set شناسه pending|in_transit|delivered|cancelled - تغییر وضعیت"
)


def fmt(r):
    return f"#{r['id']} {r['customer']} - {r['address']} [{r['status']}]"


def handle(text):
    parts = text.strip().split(None, 1)
    if not parts:
        return None
    cmd = parts[0].split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if cmd in ("/start", "/help"):
        return HELP
    if cmd == "/new":
        if "|" not in arg:
            return "استفاده: /new مشتری | آدرس"
        cust, addr = [s.strip() for s in arg.split("|", 1)]
        if not cust or not addr:
            return "استفاده: /new مشتری | آدرس"
        return f"تحویل #{db.add(cust, addr)} ثبت شد"
    if cmd == "/list":
        rows = db.list_all(10)
        return "\n".join(fmt(r) for r in rows) or "هنوز تحویلی ثبت نشده"
    if cmd == "/status":
        if not arg.isdigit():
            return "استفاده: /status شناسه"
        r = db.get(int(arg))
        return fmt(r) if r else "پیدا نشد"
    if cmd == "/set":
        p = arg.split()
        if len(p) != 2 or not p[0].isdigit():
            return "استفاده: /set شناسه وضعیت"
        if p[1] not in db.STATUSES:
            return "وضعیت باید یکی از این‌ها باشد: " + ", ".join(db.STATUSES)
        return "بروزرسانی شد" if db.set_status(int(p[0]), p[1]) else "پیدا نشد"
    return "دستور نامعتبر. /help را بفرستید"


def run():
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"timeout": 30, "offset": offset}, timeout=40)
            for u in r.json().get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message") or {}
                if "text" in m:
                    reply = handle(m["text"])
                    if reply:
                        requests.post(
                            f"{API}/sendMessage",
                            json={"chat_id": m["chat"]["id"], "text": reply},
                            timeout=10,
                        )
        except Exception as e:  # keep polling on any error
            log.warning("poll error: %s", e)
            time.sleep(5)


def start():
    if not TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set; bot disabled, dashboard only")
        return
    threading.Thread(target=run, daemon=True).start()
