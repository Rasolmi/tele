# telegram-delivery-dashboard
Telegram bot and Flask dashboard for delivery tracking.

- `TELEGRAM_BOT_TOKEN` (optional): from @BotFather; without it only the dashboard runs.
- `DB_PATH` (optional): SQLite file path. Attach a volume and point this at it to keep data across deploys.

Run: `pip install -r requirements.txt && gunicorn app:app`
