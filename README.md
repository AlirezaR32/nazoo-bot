# Nazoo 🦋

ربات تلگرام هوشمند و دوزبانه با حافظه، شخصیت قابل تنظیم، و پشتیبانی از حالت‌های Polling و Webhook.

Nazoo از مدل DeepSeek V4 Flash از طریق OpenModel.ai استفاده می‌کند و برای چت شخصی، گروه‌ها، و اجرای بر روی Vercel یا VPS مناسب است.

## ✨ ویژگی‌ها

- پاسخ‌های طبیعی و چندزبانه (فارسی/انگلیسی)
- حافظه‌ی کاربر و فکت‌های یادگرفته‌شده
- شخصیت قابل تنظیم از طریق فایل شخصیت
- پشتیبانی از چت شخصی و گروه
- حالت‌های اجرا:
  - Polling برای لپ‌تاپ یا VPS
  - Webhook برای Vercel
- پنل ادمین برای مشاهده‌ی پیام‌ها و مدیریت کاربران

## 🛠️ تکنولوژی‌ها

- Python 3.11+
- python-telegram-bot
- aiosqlite
- python-dotenv
- Anthropic-compatible OpenModel client
- Redis برای حالت Webhook/Vercel

## 📁 ساختار پروژه

```text
nazoo-bot/
├── api/
│   ├── index.py
│   └── webhook.py
├── admin_logic.py
├── ai_client.py
├── bot.py
├── config.py
├── fact_patterns.py
├── group_utils.py
├── kv_store.py
├── memory.py
├── personality_loader.py
├── personality.txt
├── requirements.txt
├── set_webhook.py
├── vercel.json
└── .env.example
```

## 🚀 راه‌اندازی سریع

### 1) کلون و نصب وابستگی‌ها

```bash
git clone <your-repo-url>
cd nazoo-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2) تنظیم متغیرهای محیطی

فایل .env را با مقادیر زیر پر کنید:

```env
TELEGRAM_TOKEN=your_bot_token
OPENMODEL_API_KEY=your_openmodel_key
OPENMODEL_BASE_URL=https://api.openmodel.ai
AI_MODEL=deepseek-v4-flash
```

در صورت نیاز برای پروکسی:

```env
TELEGRAM_PROXY_URL=http://127.0.0.1:10808
```

### 3) اجرای ربات

```bash
python bot.py
```

## ☁️ دیپلوی روی Vercel

برای اجرای وبهوک روی Vercel، این مراحل را دنبال کنید:

1. پروژه را به GitHub Push کنید.
2. در Vercel، ریپوی خود را import کنید.
3. متغیرهای محیطی را در تنظیمات پروژه وارد کنید.
4. برای حافظه، از Redis (مثلاً Upstash) استفاده کنید.
5. وبهوک را با این دستور ثبت کنید:

```bash
python set_webhook.py set https://your-project.vercel.app/api/webhook
```

برای بررسی وضعیت webhook:

```bash
python set_webhook.py info
```

## 🤖 دستورات ربات

| دستور | توضیح |
|---|---|
| /start | شروع گفتگو |
| /help | راهنمای دستورات |
| /reset | پاک‌کردن تاریخچه گفتگو |
| /forget | پاک‌کردن فکت‌های ذخیره‌شده |
| /memory | نمایش حافظه‌ی ربات |
| /stats | نمایش آمار گفتگو |

## 🛡️ ادمین

اگر آیدی عددی خود را در متغیر ADMIN_USER_IDS وارد کنید، دستورات ادمین در تلگرام نیز در دسترس خواهند بود:

- /admin
- /users
- /chatlog <user_id>

## 📝 تغییر شخصیت ربات

فایل personality.txt را ویرایش کنید تا شخصیت ربات تغییر کند. این تغییر بدون نیاز به تغییر کد اعمال می‌شود.

## 📌 نکات مهم

- در حالت Vercel، فایل api/index.py ورودی اصلی پروژه است.
- برای حالت Webhook بهتر است از Redis برای ذخیره‌ی حافظه استفاده شود.
- در صورت استفاده از Vercel، متغیرهای محیطی را دقیقاً در پنل Vercel تعریف کنید.

## 🤝 مشارکت

در صورت تمایل، برای بهبود پروژه می‌توانید Pull Request ارسال کنید یا issue باز کنید.
