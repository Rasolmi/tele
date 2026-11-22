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
    "Delivery bot\n"
    "/new Customer | Address - create a delivery\n"
    "/list - latest deliveries\n"
    "/status ID - show a delivery\n"
    "/set ID pending|in_transit|delivered|cancelled - update status"
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
            return "Usage: /new Customer | Address"
        cust, addr = [s.strip() for s in arg.split("|", 1)]
        if not cust or not addr:
            return "Usage: /new Customer | Address"
        return f"Created delivery #{db.add(cust, addr)}"
    if cmd == "/list":
        rows = db.list_all(10)
        return "\n".join(fmt(r) for r in rows) or "No deliveries yet"
    if cmd == "/status":
        if not arg.isdigit():
            return "Usage: /status ID"
        r = db.get(int(arg))
        return fmt(r) if r else "Not found"
    if cmd == "/set":
        p = arg.split()
        if len(p) != 2 or not p[0].isdigit():
            return "Usage: /set ID status"
        if p[1] not in db.STATUSES:
            return "Status must be one of: " + ", ".join(db.STATUSES)
        return "Updated" if db.set_status(int(p[0]), p[1]) else "Not found"
    return "Unknown command. Send /help"


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
