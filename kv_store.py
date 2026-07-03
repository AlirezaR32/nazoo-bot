"""
kv_store.py — کلاینت مینیمال Upstash Redis (فقط stdlib، بدون هیچ پکیج خارجی)

استفاده‌ی مشترک در api/webhook.py و api/admin.py برای خوندن/نوشتن روی
Upstash Redis از طریق REST API — بدون نیاز به پکیج redis یا httpx.

نکته: این فایل عمداً هیچ import خارجی نداره تا Vercel هیچ‌وقت به‌خاطرش
سعی نکنه framework auto-detection انجام بده یا پکیجی نصب کنه.
"""
import json
import os
import urllib.request

KV_URL   = os.environ.get("KV_REST_API_URL")   or os.environ.get("UPSTASH_REDIS_REST_URL", "")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")


def is_configured() -> bool:
    return bool(KV_URL and KV_TOKEN)


def command(cmd: list, timeout: int = 8) -> dict:
    """یه دستور خام Redis رو از طریق Upstash REST اجرا می‌کنه."""
    if not is_configured():
        return {}
    body = json.dumps(cmd).encode("utf-8")
    req = urllib.request.Request(KV_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {KV_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


# ── مقادیر JSON (تاریخچه، فکت‌ها) ────────────────────────────────────────────

def get_json(key: str, default=None):
    val = command(["GET", key]).get("result")
    if val is None:
        return default
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return default


def set_json(key: str, value):
    command(["SET", key, json.dumps(value, ensure_ascii=False)])


def delete(*keys: str):
    if keys:
        command(["DEL", *keys])


# ── ست‌ها (برای ایندکس کاربرها) ──────────────────────────────────────────────

def sadd(key: str, member: str):
    command(["SADD", key, str(member)])


def srem(key: str, member: str):
    command(["SREM", key, str(member)])


def smembers(key: str) -> list:
    return command(["SMEMBERS", key]).get("result") or []


# ── شمارنده (تعداد کل پیام‌های هر کاربر) ─────────────────────────────────────

def incr(key: str) -> int:
    return command(["INCR", key]).get("result", 0) or 0


def get_int(key: str, default: int = 0) -> int:
    val = command(["GET", key]).get("result")
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ── هش (اطلاعات پروفایل کاربر) ──────────────────────────────────────────────

def hset(key: str, mapping: dict):
    flat = ["HSET", key]
    for k, v in mapping.items():
        flat.extend([k, "" if v is None else str(v)])
    command(flat)


def hgetall(key: str) -> dict:
    result = command(["HGETALL", key]).get("result")
    if not result:
        return {}
    return dict(zip(result[0::2], result[1::2]))
