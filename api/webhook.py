"""
api/webhook.py — Vercel Serverless Function (حالت Webhook)

تلگرام مستقیم هر پیام رو POST می‌کنه به این endpoint.
چون فایل‌سیستم Vercel موقتیه (ephemeral)، حافظه روی Redis ذخیره میشه
(Vercel KV یا Upstash مستقیم) — نه SQLite.

نکته: این فایل عمداً خودکفاست (تماس‌های sync با requests) چون
BaseHTTPRequestHandler به‌صورت پیش‌فرض sync کار می‌کنه و این از پیچیدگی
event-loop داخل یه تابع serverless جلوگیری می‌کنه.
"""

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler

# Vercel اجرای این فایل رو از داخل api/ شروع می‌کنه؛ این خط مسیر ریشه‌ی
# پروژه رو به sys.path اضافه می‌کنه تا import های sibling (config.py و...) کار کنن.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from anthropic import Anthropic

from config import (
    TELEGRAM_TOKEN, BOT_USERNAME, WEBHOOK_SECRET,
    OPENMODEL_API_KEY, OPENMODEL_BASE_URL, AI_MODEL,
    MAX_TOKENS, TEMPERATURE, BOT_NAME, PERSONALITY_FILE,
    MAX_HISTORY, MAX_FACTS,
    KV_REST_API_URL, KV_REST_API_TOKEN,
)
from personality_loader import load_personality
from fact_patterns import extract_facts
from group_utils import should_respond_in_group, strip_mention

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
PERSONALITY  = load_personality(PERSONALITY_FILE, BOT_NAME)

_ai_client = (
    Anthropic(api_key=OPENMODEL_API_KEY, base_url=OPENMODEL_BASE_URL)
    if OPENMODEL_API_KEY else None
)
_bot_cache: dict = {}  # کش سطح process — ممکنه بین invocationهای گرم Vercel بمونه


# ── Redis (Upstash REST) ──────────────────────────────────────────────────────

def _kv_call(command: list) -> dict:
    if not KV_REST_API_URL or not KV_REST_API_TOKEN:
        return {}
    try:
        r = requests.post(
            KV_REST_API_URL,
            headers={"Authorization": f"Bearer {KV_REST_API_TOKEN}"},
            json=command,
            timeout=6,
        )
        return r.json()
    except Exception as e:
        logger.warning(f"KV error {command[0] if command else '?'}: {e}")
        return {}


def kv_get_json(key: str, default):
    val = _kv_call(["GET", key]).get("result")
    if val is None:
        return default
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return default


def kv_set_json(key: str, value):
    _kv_call(["SET", key, json.dumps(value, ensure_ascii=False)])


def kv_del(key: str):
    _kv_call(["DEL", key])


# ── Telegram helpers ───────────────────────────────────────────────────────────

def tg_send_message(chat_id, text: str):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"sendMessage error: {e}")


def tg_send_typing(chat_id):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass


def _get_bot_username() -> str:
    if BOT_USERNAME:
        return BOT_USERNAME
    if "username" in _bot_cache:
        return _bot_cache["username"]
    try:
        r = requests.get(f"{TELEGRAM_API}/getMe", timeout=5)
        username = (r.json().get("result", {}).get("username") or "").lower()
        _bot_cache["username"] = username
        return username
    except Exception:
        return ""


# ── AI ────────────────────────────────────────────────────────────────────────

def build_system_prompt(user_name: str, facts: list[str]) -> str:
    prompt = PERSONALITY
    if user_name:
        prompt += f"\n\n---\n**اسم کاربر:** {user_name}"
    if facts:
        prompt += "\n\n**چیزایی که از این کاربر میدونی:**\n"
        prompt += "\n".join(f"- {f}" for f in facts)
        prompt += "\n\nاز این اطلاعات طبیعی استفاده کن — اعلام نکن که یادته."
    return prompt


def ai_chat(user_name: str, user_text: str, history: list, facts: list) -> str:
    if not _ai_client:
        return "هنوز API وصل نشده 😅 متغیرهای محیطی رو چک کن."
    messages = list(history) + [{"role": "user", "content": user_text}]
    try:
        resp = _ai_client.messages.create(
            model=AI_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=build_system_prompt(user_name, facts),
            messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "یه مشکل فنی پیش اومد 😅 یه لحظه دیگه دوباره امتحان کن!"


# ── Command handlers ───────────────────────────────────────────────────────────

def handle_command(cmd: str, chat_id, user_id, first_name: str):
    if cmd == "/start":
        tg_send_message(chat_id,
            f"سلام {first_name}! 👋 من {BOT_NAME} ام.\n"
            f"یه AI بامزه که فارسی-انگلیسی بلده و حافظه هم داره.\n"
            f"فقط حرف بزن — بقیه‌اش با من 😉"
        )
    elif cmd == "/help":
        tg_send_message(chat_id,
            "📖 دستورات:\n"
            "/reset   — پاک کردن تاریخچه چت\n"
            "/forget  — فراموش کردن اطلاعاتت\n"
            "/memory  — چیزایی که ازت یادمه\n"
            "/stats   — آمار گفتگو\n\n"
            "یا فقط پیام بده 😊"
        )
    elif cmd == "/reset":
        kv_del(f"nazoo:history:{user_id}")
        tg_send_message(chat_id, "تاریخچه پاک شد! 🔄 از اول شروع می‌کنیم.")
    elif cmd == "/forget":
        kv_del(f"nazoo:facts:{user_id}")
        tg_send_message(chat_id, "همه چیزی که یادم بود رو فراموش کردم 🧠❌")
    elif cmd == "/memory":
        facts = kv_get_json(f"nazoo:facts:{user_id}", [])
        if not facts:
            tg_send_message(chat_id, "هنوز چیزی ازت نمیدونم 🤷 بیشتر حرف بزن!")
        else:
            tg_send_message(chat_id, "🧠 اینایی که یادمه:\n\n" + "\n".join(f"• {f}" for f in facts))
    elif cmd == "/stats":
        history = kv_get_json(f"nazoo:history:{user_id}", [])
        tg_send_message(chat_id, f"📊 پیام‌های ذخیره‌شده: {len(history)}")
    else:
        tg_send_message(chat_id, "این دستور رو نمی‌شناسم 🤔 /help رو بزن.")


# ── Core update handling ───────────────────────────────────────────────────────

def process_update(update: dict):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return

    chat       = msg["chat"]
    chat_id    = chat["id"]
    chat_type  = chat.get("type", "private")
    from_user  = msg.get("from", {})
    user_id    = from_user.get("id")
    first_name = from_user.get("first_name", "دوست")
    text       = msg["text"].strip()

    if not user_id:
        return

    # دستورات
    if text.startswith("/"):
        cmd = text.split()[0].split("@")[0]
        handle_command(cmd, chat_id, user_id, first_name)
        return

    # منطق گروه — فقط وقتی منشن/ریپلای بشه جواب بده
    if chat_type in ("group", "supergroup"):
        entities = msg.get("entities", [])
        mentions = [
            text[e["offset"]: e["offset"] + e["length"]].lstrip("@")
            for e in entities if e.get("type") == "mention"
        ]
        reply_msg   = msg.get("reply_to_message") or {}
        reply_user  = reply_msg.get("from", {}) or {}
        reply_to_bot = (reply_user.get("username", "") or "").lower() == _get_bot_username()

        if not should_respond_in_group(
            text, mentions, reply_to_bot, _get_bot_username(), BOT_NAME, extra_aliases=("نازو",)
        ):
            return
        text = strip_mention(text, _get_bot_username(), BOT_NAME, extra_aliases=("نازو",))

    if not text:
        return

    tg_send_typing(chat_id)

    hist_key  = f"nazoo:history:{user_id}"
    facts_key = f"nazoo:facts:{user_id}"

    history = kv_get_json(hist_key, [])
    facts   = kv_get_json(facts_key, [])

    response = ai_chat(first_name, text, history, facts)
    tg_send_message(chat_id, response)

    # آپدیت تاریخچه با محدودیت طول
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    history = history[-(MAX_HISTORY * 2):]
    kv_set_json(hist_key, history)

    # استخراج و ذخیره‌ی فکت‌های جدید
    new_facts = extract_facts(text)
    if new_facts:
        merged = list(dict.fromkeys(facts + new_facts))[-MAX_FACTS:]
        kv_set_json(facts_key, merged)


# ── Vercel entrypoint ───────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"🤖 {BOT_NAME} webhook is alive!".encode("utf-8"))

    def do_POST(self):
        if WEBHOOK_SECRET:
            sent = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if sent != WEBHOOK_SECRET:
                self.send_response(401)
                self.end_headers()
                return

        length = int(self.headers.get("Content-Length", 0) or 0)
        body   = self.rfile.read(length) if length else b"{}"

        try:
            update = json.loads(body or b"{}")
            process_update(update)
        except Exception as e:
            logger.error(f"webhook error: {e}", exc_info=True)

        # همیشه ۲۰۰ برگردون تا تلگرام دوباره retry نکنه
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')
