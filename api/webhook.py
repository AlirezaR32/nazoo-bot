"""
api/webhook.py — Vercel Serverless Webhook (zero external dependencies)

فقط از stdlib پایتون استفاده می‌کنه — نه anthropic SDK، نه requests،
نه هیچ پکیج دیگه. این عمداً هست: Vercel روی framework auto-detection
حساسه (اگه یه پکیج شناخته‌شده مثل flask/fastapi ببینه دنبال یه آبجکت
app می‌گرده)، و zero-dependency بودن کاملاً از این کلاس مشکلات جلوگیری
می‌کنه.

حافظه (تاریخچه، فکت‌ها، پروفایل هر کاربر) روی Upstash Redis از طریق
kv_store.py ذخیره میشه.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import kv_store as kv
from fact_patterns import extract_facts
from group_utils import is_reply_to_bot, should_respond_in_group, strip_mention
from personality_loader import load_personality

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── تنظیمات از Environment Variables ─────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
BOT_USERNAME      = os.environ.get("BOT_USERNAME", "").lstrip("@").lower()
WEBHOOK_SECRET    = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
OPENMODEL_API_KEY = os.environ.get("OPENMODEL_API_KEY", "")
# توجه: بدون /v1 در انتها! کلاینت‌های Anthropic-compatible خودشون /v1/messages
# رو اضافه می‌کنن؛ اینجا هم دستی همون مسیر رو می‌سازیم تا یکی نشه.
OPENMODEL_BASE    = os.environ.get("OPENMODEL_BASE_URL", "https://api.openmodel.ai").rstrip("/")
if OPENMODEL_BASE.endswith("/v1"):
    OPENMODEL_BASE = OPENMODEL_BASE[:-3]
AI_MODEL          = os.environ.get("AI_MODEL", "deepseek-v4-flash")
MAX_TOKENS        = int(os.environ.get("MAX_TOKENS", "1024"))
TEMPERATURE       = float(os.environ.get("TEMPERATURE", "0.9"))
BOT_NAME          = os.environ.get("BOT_NAME", "Nazoo")
PERSONALITY_FILE  = os.environ.get("PERSONALITY_FILE", "personality.txt")
MAX_HISTORY       = int(os.environ.get("MAX_HISTORY", "30"))
MAX_FACTS         = int(os.environ.get("MAX_FACTS", "25"))

# آیدی عددی تلگرام ادمین‌ها — با کاما جدا شده، مثلاً "111111,222222"
ADMIN_USER_IDS = {
    int(x) for x in os.environ.get("ADMIN_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
PERSONALITY  = load_personality(os.path.join(_ROOT, PERSONALITY_FILE), BOT_NAME)
_bot_cache: dict = {}


# ── urllib helpers (فقط برای Telegram و OpenModel) ────────────────────────────

def _http_post(url: str, data: dict, headers: dict = {}, timeout: int = 15) -> dict:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code} → {url}\n{e.read().decode('utf-8', errors='replace')}")
        return {}
    except Exception as ex:
        logger.error(f"_http_post error {url}: {ex}")
        return {}


def _http_get(url: str, headers: dict = {}, timeout: int = 8) -> dict:
    req = urllib.request.Request(url)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as ex:
        logger.error(f"_http_get error {url}: {ex}")
        return {}


# ── Telegram helpers ───────────────────────────────────────────────────────────

def tg_send(chat_id, text: str):
    _http_post(f"{TELEGRAM_API}/sendMessage", {"chat_id": chat_id, "text": text})


def _send_long(chat_id, text: str, chunk_size: int = 3500):
    """پیام‌های طولانی (مثلاً /chatlog) رو تکه‌تکه می‌فرسته."""
    if len(text) <= chunk_size:
        tg_send(chat_id, text)
        return
    buf = ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > chunk_size:
            tg_send(chat_id, buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        tg_send(chat_id, buf)


def tg_typing(chat_id):
    _http_post(f"{TELEGRAM_API}/sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=4)


def get_bot_username() -> str:
    if BOT_USERNAME:
        return BOT_USERNAME
    if "username" in _bot_cache:
        return _bot_cache["username"]
    r = _http_get(f"{TELEGRAM_API}/getMe")
    u = (r.get("result", {}).get("username") or "").lower()
    _bot_cache["username"] = u
    return u


# ── AI (OpenModel / Anthropic Messages API — تماس مستقیم HTTP) ────────────────

def build_system(user_name: str, facts: list) -> str:
    prompt = PERSONALITY
    if user_name:
        prompt += f"\n\n---\n**اسم کاربر:** {user_name}"
    if facts:
        prompt += "\n\n**چیزایی که از این کاربر میدونی:**\n"
        prompt += "\n".join(f"- {f}" for f in facts)
        prompt += "\n\nاز این اطلاعات طبیعی استفاده کن — اعلام نکن که یادته."
    return prompt


def ai_chat(user_name: str, user_text: str, history: list, facts: list) -> str:
    if not OPENMODEL_API_KEY:
        return "هنوز API وصل نشده 😅 متغیرهای محیطی رو چک کن."

    payload = {
        "model":       AI_MODEL,
        "max_tokens":  MAX_TOKENS,
        "temperature": TEMPERATURE,
        "system":      build_system(user_name, facts),
        "messages":    list(history) + [{"role": "user", "content": user_text}],
    }
    headers = {"x-api-key": OPENMODEL_API_KEY, "anthropic-version": "2023-06-01"}
    result  = _http_post(f"{OPENMODEL_BASE}/v1/messages", payload, headers, timeout=28)

    if not result:
        return "یه مشکل فنی پیش اومد 😅 یه لحظه دیگه دوباره امتحان کن!"
    try:
        text = "".join(
            b["text"] for b in result["content"] if b.get("type") == "text"
        ).strip()
        # هم‌راستا با ai_client.py (حالت polling): نمادهای مارک‌داون رو حذف کن
        # چون تلگرام به‌صورت پیش‌فرض متن ساده نشون میده، نه مارک‌داون رندرشده.
        text = text.replace("**", "")
        return text or "جواب خالی از AI رسید 🤔"
    except (KeyError, TypeError) as e:
        logger.error(f"AI parse error: {e} | result: {result}")
        return "مشکلی در خوندن جواب AI پیش اومد 😅"


# ── ردیابی کاربر (برای پنل ادمین) ──────────────────────────────────────────────

def track_user(user_id: int, chat_id: int, first_name: str, username: str):
    """هر بار کاربر پیام میده، پروفایلش رو در Redis آپدیت می‌کنیم — پایه‌ی پنل ادمین."""
    now = datetime.now(timezone.utc).isoformat()
    meta_key = f"nazoo:user:{user_id}:meta"
    existing = kv.hgetall(meta_key)

    kv.sadd("nazoo:users:index", str(user_id))
    kv.hset(meta_key, {
        "first_name": first_name or "",
        "username":   username or "",
        "chat_id":    chat_id,
        "last_seen":  now,
        "joined_at":  existing.get("joined_at") or now,
    })


# ── دستورات معمولی ─────────────────────────────────────────────────────────────

def handle_command(cmd: str, chat_id, user_id, first_name: str):
    if cmd == "/start":
        tg_send(chat_id,
            f"سلام {first_name}! 👋 من {BOT_NAME} ام.\n"
            f"یه AI بامزه که فارسی-انگلیسی بلده و حافظه هم داره.\n"
            f"فقط حرف بزن — بقیه‌اش با من 😉\n\n/help رو بزن برای دستورات.")
    elif cmd == "/help":
        tg_send(chat_id,
            "📖 دستورات:\n"
            "/reset   — پاک کردن تاریخچه\n"
            "/forget  — فراموش کردن اطلاعاتت\n"
            "/memory  — چیزایی که ازت یادمه\n"
            "/stats   — آمار گفتگو\n\n"
            "📌 گروه: منشن کن یا ریپلای بزن.")
    elif cmd == "/reset":
        kv.delete(f"nazoo:history:{user_id}")
        tg_send(chat_id, "تاریخچه پاک شد! 🔄 از اول شروع می‌کنیم.")
    elif cmd == "/forget":
        kv.delete(f"nazoo:facts:{user_id}")
        tg_send(chat_id, "همه چیزی که یادم بود رو فراموش کردم 🧠❌")
    elif cmd == "/memory":
        facts = kv.get_json(f"nazoo:facts:{user_id}", [])
        if not facts:
            tg_send(chat_id, "هنوز چیزی ازت نمیدونم 🤷 بیشتر حرف بزن!")
        else:
            tg_send(chat_id, "🧠 اینایی که یادمه:\n\n" + "\n".join(f"• {f}" for f in facts))
    elif cmd == "/stats":
        total = kv.get_int(f"nazoo:msgcount:{user_id}")
        tg_send(chat_id, f"📊 کل پیام‌هایی که فرستادی: {total}")
    else:
        tg_send(chat_id, "این دستور رو نمیشناسم 🤔 /help رو بزن.")


# ── دستورات ادمین (فقط تلگرام آیدی‌های داخل ADMIN_USER_IDS) ───────────────────

def handle_admin_command(cmd: str, args: str, chat_id, user_id: int):
    if cmd == "/admin":
        ids = kv.smembers("nazoo:users:index")
        total_msgs = sum(kv.get_int(f"nazoo:msgcount:{uid}") for uid in ids)
        tg_send(chat_id,
            f"🛠️ پنل ادمین {BOT_NAME}\n\n"
            f"👥 کل کاربرها: {len(ids)}\n"
            f"💬 کل پیام‌ها: {total_msgs}\n\n"
            f"/users — لیست کاربرها\n"
            f"/chatlog <user_id> — تاریخچه‌ی یه کاربر"
        )

    elif cmd == "/users":
        ids = kv.smembers("nazoo:users:index")
        if not ids:
            tg_send(chat_id, "هنوز هیچ کاربری نداریم.")
            return
        rows = []
        for uid in ids:
            meta  = kv.hgetall(f"nazoo:user:{uid}:meta")
            count = kv.get_int(f"nazoo:msgcount:{uid}")
            name  = meta.get("first_name", "?")
            uname = f"@{meta.get('username')}" if meta.get("username") else "—"
            rows.append((meta.get("last_seen", ""), f"• {name} ({uname}) — id:{uid} — {count} پیام"))
        rows.sort(reverse=True)
        text = f"👥 کاربرها ({len(rows)}):\n\n" + "\n".join(r[1] for r in rows[:40])
        _send_long(chat_id, text)

    elif cmd == "/chatlog":
        target = args.strip()
        if not target.isdigit():
            tg_send(chat_id, "استفاده: /chatlog <user_id>\nاز /users آیدی رو بگیر.")
            return
        meta    = kv.hgetall(f"nazoo:user:{target}:meta")
        history = kv.get_json(f"nazoo:history:{target}", [])
        facts   = kv.get_json(f"nazoo:facts:{target}", [])
        if not meta and not history:
            tg_send(chat_id, "همچین کاربری پیدا نشد.")
            return

        name  = meta.get("first_name", "?")
        lines = [f"📜 تاریخچه‌ی {name} (id:{target})\n"]
        if facts:
            lines.append("🧠 فکت‌ها: " + " | ".join(facts))
            lines.append("")
        for m in history:
            speaker = "👤 کاربر" if m.get("role") == "user" else f"🤖 {BOT_NAME}"
            lines.append(f"{speaker}: {m.get('content','')}")
        _send_long(chat_id, "\n".join(lines))


# ── پردازش اصلی هر آپدیت تلگرام ───────────────────────────────────────────────

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
    username   = from_user.get("username", "")
    text       = msg["text"].strip()

    if not user_id or not text:
        return

    is_admin = user_id in ADMIN_USER_IDS

    # دستورات
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd   = parts[0].split("@")[0]
        args  = parts[1] if len(parts) > 1 else ""

        if is_admin and cmd in ("/admin", "/users", "/chatlog"):
            handle_admin_command(cmd, args, chat_id, user_id)
        else:
            handle_command(cmd, chat_id, user_id, first_name)
        return

    # منطق گروه
    if chat_type in ("group", "supergroup"):
        entities = msg.get("entities", [])
        mentions = [
            text[e["offset"]: e["offset"] + e["length"]].lstrip("@")
            for e in entities if e.get("type") == "mention"
        ]
        reply_msg    = msg.get("reply_to_message") or {}
        reply_to_bot = is_reply_to_bot(reply_msg, bot_id=None, bot_username=get_bot_username())

        if not should_respond_in_group(
            text, mentions, reply_to_bot, get_bot_username(), BOT_NAME, extra_aliases=("نازو",)
        ):
            return
        text = strip_mention(text, get_bot_username(), BOT_NAME, extra_aliases=("نازو",))

    if not text:
        return

    tg_typing(chat_id)
    track_user(user_id, chat_id, first_name, username)
    kv.incr(f"nazoo:msgcount:{user_id}")

    hist_key  = f"nazoo:history:{user_id}"
    facts_key = f"nazoo:facts:{user_id}"
    history   = kv.get_json(hist_key, [])
    facts     = kv.get_json(facts_key, [])

    response = ai_chat(first_name, text, history, facts)
    tg_send(chat_id, response)

    history.append({"role": "user",      "content": text})
    history.append({"role": "assistant", "content": response})
    kv.set_json(hist_key, history[-(MAX_HISTORY * 2):])

    new_facts = extract_facts(text)
    if new_facts:
        merged = list(dict.fromkeys(facts + new_facts))[-MAX_FACTS:]
        kv.set_json(facts_key, merged)


# ── Vercel entrypoint ─────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.info(fmt % args)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"🤖 {BOT_NAME} webhook is alive!".encode())

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
            process_update(json.loads(body or b"{}"))
        except Exception as e:
            logger.error(f"webhook error: {e}", exc_info=True)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
