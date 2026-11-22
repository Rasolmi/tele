# Telegram Fuel Delivery Bot and Admin Dashboard

ربات تلگرام و پنل فارسی برای ثبت منابع، تایید تحویل‌ها و مدیریت کاربران.

## تنظیمات الزامی و اختیاری

- `TELEGRAM_BOT_TOKEN`: توکن ربات از BotFather؛ **بدون آن ربات خاموش است**.
- `SUPER_ADMIN_ID`: شناسه عددی تلگرام مدیر کل. مقدار را در environment تنظیم کنید، نه در کد.
- `FLASK_SECRET_KEY`: کلید تصادفی برای Flask؛ اگر تنظیم نشود هر اجرا کلید جدیدی خواهد داشت.
- `DB_PATH`: مسیر SQLite؛ پیش‌فرض `fuel_bot.db` است.
- `DAILY_REQUIRED`: حد نصاب روزانه سوخت معادل؛ پیش‌فرض `300`.
- `SUPPORT_USERNAME`: نام کاربری پشتیبانی بدون @.
- `WEB_BASE_URL`: آدرس عمومی پنل.

## روشن کردن ربات

در سرویس میزبانی این متغیرها را تنظیم کنید:

```text
TELEGRAM_BOT_TOKEN=<توکن BotFather>
SUPER_ADMIN_ID=<شناسه عددی تلگرام>
FLASK_SECRET_KEY=<کلید تصادفی>
```

سپس سرویس را rebuild/redeploy کنید. ربات در `gunicorn` با یک thread جداگانه شروع می‌شود، اما نگهدارنده polling توکن معتبر لازم دارد.

## اجرا

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="توکن"
export SUPER_ADMIN_ID="123456789"
gunicorn app:app
```

پنل برای محلی‌سازی و مدیریت کاربران بدون رمز و از مسیر `/` قابل دسترس است.
