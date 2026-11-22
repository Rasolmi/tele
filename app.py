from flask import Flask, redirect, render_template, request, url_for

import bot
import db

app = Flask(__name__)
db.init()
bot.start()


@app.get("/")
def index():
    return render_template(
        "index.html",
        rows=db.list_all(),
        counts=db.counts(),
        statuses=db.STATUSES,
        bot_on=bool(bot.TOKEN),
    )


@app.post("/add")
def add():
    c = request.form.get("customer", "").strip()
    a = request.form.get("address", "").strip()
    if c and a:
        db.add(c, a)
    return redirect(url_for("index"))


@app.post("/status/<int:did>")
def status(did):
    db.set_status(did, request.form.get("status", ""))
    return redirect(url_for("index"))


@app.get("/health")
def health():
    return {"ok": True}
