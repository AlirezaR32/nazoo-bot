"""
api/index.py — تنها entrypoint واقعی پروژه روی Vercel.

Vercel's Python runtime (نسخه‌ی فعلی) فقط یک entrypoint واحد برای کل
پروژه قبول می‌کنه — نه یه فایل جدا زیر api/ برای هر تابع، مثل قبل.
وقتی api/webhook.py و api/admin.py هر دو کلاس handler داشتن، Vercel
نمی‌دونست کدوم رو انتخاب کنه (همون خطای "No python entrypoint found،
but found potential entrypoints... variable: handler" که دیدیم).

راه‌حل: فقط همین فایل کلاس handler داره. منطق واقعی webhook و admin در
webhook_logic.py و admin_logic.py هستن (بدون کلاس handler، فقط توابع).
این فایل بر اساس query param ?route= (که در vercel.json با rewrite
تنظیم شده) تصمیم می‌گیره کدوم منطق رو صدا بزنه — و آدرس‌های خارجی
/api/webhook و /api/admin دقیقاً همونی که قبلاً بودن باقی می‌مونن.
"""

import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import webhook_logic
import admin_logic


def _route(path: str) -> str:
    query = parse_qs(urlparse(path).query)
    return query.get("route", ["webhook"])[0]


class handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # لاگ‌های پیش‌فرض BaseHTTPRequestHandler رو خاموش می‌کنیم

    def do_GET(self):
        if _route(self.path) == "admin":
            admin_logic.handle_get(self)
        else:
            webhook_logic.handle_get(self)

    def do_POST(self):
        if _route(self.path) == "admin":
            admin_logic.handle_post(self)
        else:
            webhook_logic.handle_post(self)
