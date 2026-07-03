"""
config.py — تنظیمات از .env / متغیرهای محیطی

این فایل توسط هر دو حالت استفاده میشه:
  • bot.py          (polling — لپ‌تاپ/VPS)
  • api/webhook.py  (serverless — Vercel)
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── تلگرام ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
BOT_USERNAME:   str = os.getenv("BOT_USERNAME", "").lstrip("@").lower()
WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_PROXY_URL: str = os.getenv("TELEGRAM_PROXY_URL", "")

# ── OpenModel.ai (DeepSeek V4 Flash) ─────────────────────────────────────────
# مستندات: https://www.openmodel.ai/model-pricing/deepseek-v4-flash
# OpenModel با فرمت Anthropic Messages API سازگاره
OPENMODEL_API_KEY:  str   = os.getenv("OPENMODEL_API_KEY", "")
# توجه: بدون /v1 در انتها! کلاینت Anthropic خودش "/v1/messages" رو اضافه
# می‌کنه — اگه اینجا /v1 بذاری، مسیر نهایی میشه /v1/v1/messages و 404 می‌خوری.
OPENMODEL_BASE_URL: str   = os.getenv("OPENMODEL_BASE_URL", "https://api.openmodel.ai")
AI_MODEL:           str   = os.getenv("AI_MODEL", "deepseek-v4-flash")
MAX_TOKENS:         int   = int(os.getenv("MAX_TOKENS", "1024"))
TEMPERATURE:        float = float(os.getenv("TEMPERATURE", "0.9"))

# ── هویت ربات ─────────────────────────────────────────────────────────────────
BOT_NAME:         str = os.getenv("BOT_NAME", "Nazoo")
PERSONALITY_FILE: str = os.getenv("PERSONALITY_FILE", "personality.txt")

# ── حافظه محلی — SQLite (فقط حالت polling در bot.py) ─────────────────────────
DB_PATH:     str = os.getenv("DB_PATH", "nazoo_memory.db")
MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "30"))
MAX_FACTS:   int = int(os.getenv("MAX_FACTS", "25"))

# ── حافظه ابری — Redis (فقط حالت Vercel در api/webhook.py) ───────────────────
# فایل‌سیستم Vercel موقتیه، پس اونجا از Upstash Redis (یا Vercel KV که خودش
# روی Upstash ساخته شده) استفاده می‌کنیم. هر کدوم از این جفت متغیر رو
# تنظیم کنی کار می‌کنه:
KV_REST_API_URL:   str = os.getenv("KV_REST_API_URL")   or os.getenv("UPSTASH_REDIS_REST_URL", "")
KV_REST_API_TOKEN: str = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

# ── پنل ادمین ─────────────────────────────────────────────────────────────────
# ADMIN_USER_IDS: آیدی عددی تلگرام ادمین‌ها با کاما جدا شده — برای دستورات
#   /admin, /users, /chatlog داخل خودِ تلگرام (هم در bot.py هم در webhook.py)
# ADMIN_SECRET: رمز ورود به داشبورد وب (فقط در api/admin.py — نسخه‌ی Vercel)
_admin_ids_raw = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS: set[int] = {
    int(x) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
}
ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "")
