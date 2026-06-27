# Nazoo 🦋 — Telegram AI Chatbot

یه ربات تلگرام جذاب، باهوش، و دوزبانه (فارسی/انگلیسی) با حافظه‌ی واقعی،
شخصیت قابل‌تنظیم، و موتور **DeepSeek V4 Flash** از طریق **OpenModel.ai**.

دو حالت اجرا داره:

| حالت | فایل | کجا اجرا میشه | حافظه |
|---|---|---|---|
| **Polling** | `bot.py` | لپ‌تاپ یا VPS (همیشه روشن) | SQLite محلی |
| **Webhook** | `api/webhook.py` | Vercel (Serverless) | Redis (Upstash/Vercel KV) |

---

## ساختار پروژه

```
nazoo-bot/
├── api/
│   └── webhook.py        # تابع Serverless برای Vercel (حالت webhook)
├── bot.py                 # ربات حالت polling — برای لپ‌تاپ/VPS
├── config.py              # تنظیمات مشترک از .env
├── memory.py              # حافظه SQLite (فقط polling)
├── ai_client.py           # کلاینت async OpenModel (فقط polling)
├── fact_patterns.py       # regexهای استخراج فکت (مشترک)
├── group_utils.py         # تشخیص منشن/ریپلای در گروه (مشترک)
├── personality_loader.py  # بارگذاری فایل شخصیت (مشترک)
├── personality.txt        # شخصیت Nazoo — هرجور خواستی ویرایشش کن
├── set_webhook.py         # ابزار کمکی برای ثبت webhook تلگرام
├── requirements.txt
├── vercel.json
├── .env.example
└── .gitignore
```

---

## ۱) راه‌اندازی محلی (تست سریع)

```bash
git clone <your-repo-url>
cd nazoo-bot
python -m venv venv && source venv/bin/activate   # یا venv\Scripts\activate در ویندوز
pip install -r requirements.txt
cp .env.example .env
```

فایل `.env` رو پر کن:

```env
TELEGRAM_TOKEN=توکن_از_BotFather
OPENMODEL_API_KEY=کلید_OpenModel
OPENMODEL_BASE_URL=https://api.openmodel.ai/v1
AI_MODEL=deepseek-v4-flash
```

اجرا:

```bash
python bot.py
```

این حالت از SQLite محلی استفاده می‌کنه — برای تست عالیه، ولی برای اجرای
دائمی نیاز به یه سرور همیشه‌روشن (VPS) داره.

---

## ۲) دیپلوی روی Vercel (Serverless)

### مرحله ۱ — پوش به GitHub

```bash
git remote add origin https://github.com/<your-username>/nazoo-bot.git
git branch -M main
git push -u origin main
```

### مرحله ۲ — وصل کردن به Vercel

1. به [vercel.com/new](https://vercel.com/new) برو
2. ریپوی `nazoo-bot` رو از GitHub انتخاب کن و Import بزن
3. Vercel خودش Python runtime رو تشخیص میده (به‌خاطر `requirements.txt`)

### مرحله ۳ — یه دیتابیس Redis وصل کن (برای حافظه)

چون فایل‌سیستم Vercel موقتیه (هر اجرا ممکنه روی یه instance جدید باشه)،
حافظه باید روی یه دیتابیس خارجی ذخیره شه. ساده‌ترین راه:

- در پنل پروژه‌ی Vercel: **Storage → Marketplace Database Providers → Upstash**
- یه دیتابیس Redis رایگان بساز و به پروژه وصلش کن
- Vercel خودش متغیرهای `KV_REST_API_URL` و `KV_REST_API_TOKEN` رو ست می‌کنه

(یا مستقیم در [upstash.com](https://upstash.com) یه دیتابیس رایگان بساز و
`UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` رو دستی در Vercel
Environment Variables اضافه کن.)

### مرحله ۴ — بقیه‌ی Environment Variables رو ست کن

در **Project Settings → Environment Variables**، همون مقادیر `.env.example`
رو وارد کن:

```
TELEGRAM_TOKEN
TELEGRAM_WEBHOOK_SECRET   (یه رشته‌ی تصادفی خودت بساز)
OPENMODEL_API_KEY
OPENMODEL_BASE_URL
AI_MODEL
BOT_NAME
```

### مرحله ۵ — دیپلوی و گرفتن آدرس

بعد از دیپلوی، آدرس پروژه‌ت چیزی شبیه این میشه:
```
https://nazoo-bot.vercel.app
```

endpoint وبهوک:
```
https://nazoo-bot.vercel.app/api/webhook
```

### مرحله ۶ — ثبت webhook در تلگرام

از همون `.env` لوکالت (یا با env vars واقعی) این رو اجرا کن:

```bash
python set_webhook.py set https://nazoo-bot.vercel.app/api/webhook
```

چک کن درست ثبت شده:

```bash
python set_webhook.py info
```

تمام! حالا ربات روی Vercel به‌صورت serverless و رایگان کار می‌کنه 🎉

---

## دستورات ربات

| دستور | کار |
|---|---|
| `/start` | شروع |
| `/help` | راهنما |
| `/reset` | پاک کردن تاریخچه گفتگو |
| `/forget` | فراموش کردن فکت‌های ذخیره‌شده |
| `/memory` | نمایش چیزایی که ربات یادشه |
| `/stats` | آمار گفتگو |

---

## گروه‌ها

ربات در گروه فقط جواب میده وقتی:
- با `@username` منشن بشه
- کسی ریپلای به پیام ربات بزنه
- پیام با `Nazoo` یا `نازو` شروع بشه

---

## تغییر شخصیت

فایل `personality.txt` رو هر جور خواستی ویرایش کن — کاملاً بدون نیاز به
تغییر کد. در حالت polling با ریستارت اعمال میشه؛ در Vercel با هر دیپلوی
جدید (چون فایل بخشی از بیلده).

---

## نکات فنی

- **مدل:** `deepseek-v4-flash` از طریق [OpenModel.ai](https://www.openmodel.ai/model-pricing/deepseek-v4-flash) — یه gateway چندمدلیه که با فرمت Anthropic Messages API سازگاره.
- **امنیت webhook:** اگه `TELEGRAM_WEBHOOK_SECRET` رو ست کنی، تلگرام هر
  درخواست رو با یه هدر مخصوص امضا می‌کنه و `api/webhook.py` قبل از پردازش
  چکش می‌کنه — بدون این، هر کسی می‌تونه آدرس وبهوکت رو پیدا کنه و درخواست
  جعلی بفرسته.
- **Cold start:** اولین پیام بعد از مدت بی‌فعالیت ممکنه یه‌کم کندتر باشه
  چون Vercel باید function رو دوباره گرم کنه — طبیعیه.
- **محدودیت زمان اجرا:** `vercel.json` روی ۳۰ ثانیه ست شده. اگه پلن Hobby
  داری و خطای timeout گرفتی، `maxDuration` رو پایین‌تر بیار (پلن Hobby حداکثر
  معمولاً محدودتره) یا به پلن بالاتر برو.

---

## اجرا به‌عنوان سرویس (روش جایگزین — VPS بجای Vercel)

```bash
sudo nano /etc/systemd/system/nazoo.service
```
```ini
[Unit]
Description=Nazoo Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/nazoo-bot
ExecStart=/path/to/nazoo-bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable nazoo && sudo systemctl start nazoo
```
