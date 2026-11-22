# Telegram Fuel Delivery Bot and Admin Dashboard

ربات تلگرام و پنل فارسی برای ثبت منابع، تایید تحویل‌ها و مدیریت کاربران.

## تنظیمات ضروری

- `TELEGRAM_BOT_TOKEN`: توکن ربات از BotFather؛ بدون آن پنل وب اجرا می‌شود ولی ربات خاموش است.
- `SUPER_ADMIN_ID`: شناسه عددی تلگرام مدیر کل.
- `WEB_ADMIN_PASSWORD`: رمز الزامی پنل وب. تا زمانی که تنظیم نشود، پنل مدیریت با خطای 503 بسته می‌ماند.
- `FLASK_SECRET_KEY`: کلید تصادفی برای Flask (برای نمونه با `python -c "import secrets; print(secrets.token_hex(32))"` بسازید).
- `DB_PATH`: مسیر فایل SQLite؛ پیش‌فرض `fuel_bot.db` است. این نام جدا از دیتابیس تحویل قدیمی است تا داده‌های قبلی دست‌نخورده بمانند.
- `DAILY_REQUIRED`: حد نصاب روزانه سوخت معادل، پیش��فرض `300`.
- `SUPPORT_USERNAME`: نام کاربری پشتیبانی بدون @.
- `WEB_BASE_URL`: آدرس عمومی پنل که به ادمین در ربات نمایش داده می‌شود.

پنل از HTTP Basic Authentication استفاده می‌کند. در پنجره ورود مرورگر، نام کاربری دلخواه و مقدار `WEB_ADMIN_PASSWORD` را وارد کنید. رمز را در کد یا مخزن قرار ندهید؛ آن را به‌عنوان secret در سرویس میزبانی تنظیم کنید.

## اجرا

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="..."
export SUPER_ADMIN_ID="123456789"
export WEB_ADMIN_PASSWORD="یک-رمز-قوی"
export FLASK_SECRET_KEY="یک-کلید-تصادفی-طولانی"
gunicorn app:app
```

برای شروع ربات، کاربر باید در تلگرام `/start` را بفرستد. ادمین کل از طریق `SUPER_ADMIN_ID` مشخص می‌شود و می‌تواند از پنل، تحویل‌ها را تایید و اعضا را مدیریت کند. فایل `Procfile` برای استقرار با Gunicorn استفاده می‌شود.
