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
OPENMODEL_BASE_URL: str   = os.getenv("OPENMODEL_BASE_URL", "https://api.openmodel.ai/v1")
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
