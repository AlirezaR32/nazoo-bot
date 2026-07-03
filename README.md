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
│   ├── webhook.py          # تابع Serverless تلگرام برای Vercel
│   └── admin.py             # داشبورد وب ادمین برای Vercel
├── bot.py                    # ربات حالت polling — برای لپ‌تاپ/VPS
├── config.py                  # تنظیمات مشترک از .env
├── memory.py                  # حافظه SQLite (فقط polling)
├── ai_client.py                # کلاینت async OpenModel (فقط polling)
├── kv_store.py                  # کلاینت مینیمال Upstash Redis (webhook + admin)
├── fact_patterns.py              # regexهای استخراج فکت (مشترک)
├── group_utils.py                 # تشخیص منشن/ریپلای در گروه (مشترک)
├── personality_loader.py           # بارگذاری فایل شخصیت (مشترک)
├── personality.txt                  # شخصیت Nazoo — هرجور خواستی ویرایشش کن
├── set_webhook.py                    # ابزار کمکی برای ثبت webhook تلگرام
├── requirements.txt                   # فقط برای حالت polling محلی
├── vercel.json
├── .env.example
└── .gitignore
```

**نکته‌ی مهم:** `api/webhook.py` و `api/admin.py` عمداً هیچ پکیج خارجی
استفاده نمی‌کنن (فقط stdlib پایتون). این تصمیمیه، نه محدودیت — چون Vercel
وقتی توی `requirements.txt` پکیج‌های شناخته‌شده‌ای مثل `flask`/`fastapi`/`django`
ببینه، فرض می‌کنه پروژه یه اپ وب با اون فریمورکه و دنبال یه آبجکت `app`
می‌گرده، نه کلاس `handler` که این فایل‌ها واقعاً دارن — و همین باعث خطای
`could not import` میشه. با zero-dependency بودن این دو فایل، کل این کلاس
مشکلات از اساس حذف میشه.

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
OPENMODEL_BASE_URL=https://api.openmodel.ai
AI_MODEL=deepseek-v4-flash
```

اگه تلگرام در شبکه‌ت مستقیم در دسترس نیست (مثلاً در ایران)، یه پروکسی هم
می‌تونی تنظیم کنی:

```env
TELEGRAM_PROXY_URL=http://127.0.0.1:10808
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
git add -A
git commit -m "your message"
git push
```

### مرحله ۲ — وصل کردن به Vercel

1. به [vercel.com/new](https://vercel.com/new) برو
2. ریپوی `nazoo-bot` رو از GitHub انتخاب کن و Import بزن
3. Vercel خودش Python runtime رو تشخیص میده و `api/webhook.py` +
   `api/admin.py` رو به‌عنوان دو تابع سرورless جدا می‌سازه

### مرحله ۳ — یه دیتابیس Redis وصل کن (برای حافظه)

چون فایل‌سیستم Vercel موقتیه (هر اجرا ممکنه روی یه instance جدید باشه)،
حافظه باید روی یه دیتابیس خارجی ذخیره شه:

- در پنل پروژه‌ی Vercel: **Storage → Marketplace Database Providers → Upstash for Redis**
  (نه Vector، نه QStash، نه Search — همون گزینه‌ی ساده‌ی Redis)
- یه دیتابیس رایگان بساز و به پروژه وصلش کن
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
OPENMODEL_BASE_URL        (بدون /v1 در انتها!)
AI_MODEL
BOT_NAME
ADMIN_USER_IDS            (آیدی عددی تلگرامت — از @userinfobot بگیر)
ADMIN_SECRET              (رمز داشبورد وب — یه رشته‌ی تصادفی و قوی)
```

⚠️ **فقط همین‌ها رو ست کن.** به `requirements.txt` هیچ‌وقت `flask`،
`fastapi`، یا `django` اضافه نکن — دلیلش بالاتر توضیح داده شد.

### مرحله ۵ — دیپلوی و گرفتن آدرس

بعد از دیپلوی، آدرس پروژه‌ت چیزی شبیه این میشه:
```
https://nazoo-bot.vercel.app
```

endpoint وبهوک تلگرام:
```
https://nazoo-bot.vercel.app/api/webhook
```

داشبورد ادمین:
```
https://nazoo-bot.vercel.app/api/admin
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

## پنل ادمین 🛠️

دو راه برای دیدن پیام‌های همه‌ی کاربرها و جواب‌های AI وجود داره:

### ۱) داشبورد وب کامل (`api/admin.py`)

به این آدرس برو:
```
https://your-project.vercel.app/api/admin
```

با رمزی که در `ADMIN_SECRET` گذاشتی وارد شو. امکانات:
- لیست همه‌ی کاربرها با آخرین فعالیت (نقطه‌ی سبز = آنلاین در ۵ دقیقه‌ی اخیر)
- جستجوی سریع بین کاربرها
- مشاهده‌ی کامل تاریخچه‌ی گفتگو (حباب‌های کاربر/AI جدا از هم)
- مشاهده‌ی فکت‌های یادگرفته‌شده از هر کاربر
- پاک‌کردن تاریخچه / فراموشی فکت‌ها / حذف کامل یه کاربر — هرکدوم جدا
- ریسپانسیو کامل، از موبایل هم قابل استفاده‌ست

**نکته‌ی امنیتی:** `ADMIN_SECRET` رو یه رشته‌ی تصادفی و بلند بذار (مثلاً با
`openssl rand -hex 24` بسازش). بدون این متغیر، داشبورد هیچ داده‌ای نشون نمیده.

### ۲) دستورات مستقیم در تلگرام (سریع، موبایلی)

اگه آیدی عددی تلگرامت رو در `ADMIN_USER_IDS` بذاری، این دستورات فقط برای تو
فعال میشن (بقیه‌ی کاربرها حتی وجودشون رو نمی‌بینن):

| دستور | کار |
|---|---|
| `/admin` | آمار کلی — تعداد کاربرها و پیام‌ها |
| `/users` | لیست همه‌ی کاربرها با آیدی و تعداد پیام |
| `/chatlog <user_id>` | کل تاریخچه‌ی گفتگو + فکت‌های اون کاربر، مستقیم توی چت |

آیدی عددی خودت رو از [@userinfobot](https://t.me/userinfobot) بگیر.

این دستورات هم در `bot.py` (polling) و هم در `api/webhook.py` (Vercel) کار
می‌کنن — هرجا ربات رو اجرا کنی، دسترسی ادمین همراهته.

---

## گروه‌ها

ربات در گروه فقط جواب میده وقتی:
- با `@username` منشن بشه
- کسی ریپلای به پیام ربات بزنه (تشخیص هم با آیدی عددی هم یوزرنیم)
- پیام با `Nazoo` یا `نازو` شروع بشه

---

## تغییر شخصیت

فایل `personality.txt` رو هر جور خواستی ویرایش کن — کاملاً بدون نیاز به
تغییر کد. در حالت polling با ریستارت اعمال میشه؛ در Vercel با هر دیپلوی
جدید (چون فایل بخشی از بیلده).

---

## پروکسی (برای شبکه‌های محدود)

اگه در حالت polling اجرا می‌کنی و دسترسی مستقیم به `api.telegram.org` نداری،
`TELEGRAM_PROXY_URL` رو در `.env` ست کن:

```env
TELEGRAM_PROXY_URL=http://127.0.0.1:10808
```

این فقط برای حالت polling (`bot.py`) کاربرد داره — حالت Vercel از سرورهای
خود Vercel به تلگرام وصل میشه و معمولاً نیازی به پروکسی نداره.

---

## نکات فنی

- **مدل:** `deepseek-v4-flash` از طریق [OpenModel.ai](https://www.openmodel.ai/model-pricing/deepseek-v4-flash) — یه gateway چندمدلیه که با فرمت Anthropic Messages API سازگاره.
- **OPENMODEL_BASE_URL بدون `/v1`:** کلاینت‌های سازگار با Anthropic خودشون
  `/v1/messages` رو به انتهای base_url اضافه می‌کنن. اگه خودت هم `/v1` بذاری،
  مسیر نهایی `/v1/v1/messages` میشه و خطای 404 می‌گیری.
- **امنیت webhook:** اگه `TELEGRAM_WEBHOOK_SECRET` رو ست کنی، تلگرام هر
  درخواست رو با یه هدر مخصوص امضا می‌کنه و `api/webhook.py` قبل از پردازش
  چکش می‌کنه.
- **Cold start:** اولین پیام بعد از مدت بی‌فعالیت ممکنه یه‌کم کندتر باشه
  چون Vercel باید function رو دوباره گرم کنه — طبیعیه.
- **محدودیت زمان اجرا:** `vercel.json` روی ۳۰ ثانیه (webhook) و ۱۵ ثانیه
  (admin) ست شده. اگه پلن Hobby داری و خطای timeout گرفتی، `maxDuration`
  رو پایین‌تر بیار یا به پلن بالاتر برو.
- **بدون dependency در api/:** هیچ‌وقت `import requests` یا `import anthropic`
  به `api/webhook.py` یا `api/admin.py` اضافه نکن — این باعث برمی‌گرده همون
  خطای `ModuleNotFoundError` که قبلاً حل شد. اگه چیز جدیدی لازم شد، از
  `urllib.request` (که همین الان استفاده میشه) استفاده کن.

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
