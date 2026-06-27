"""
set_webhook.py — اسکریپت کمکی برای ثبت/حذف/چک‌کردن webhook تلگرام

استفاده:
    python set_webhook.py set    https://your-project.vercel.app/api/webhook
    python set_webhook.py info
    python set_webhook.py delete
"""
import sys
import requests

from config import TELEGRAM_TOKEN, WEBHOOK_SECRET

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def set_webhook(url: str):
    payload = {"url": url}
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET
    r = requests.post(f"{API}/setWebhook", json=payload, timeout=15)
    print(r.json())


def get_info():
    r = requests.get(f"{API}/getWebhookInfo", timeout=15)
    print(r.json())


def delete_webhook():
    r = requests.post(f"{API}/deleteWebhook", timeout=15)
    print(r.json())


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN تنظیم نشده! فایل .env رو چک کن.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("استفاده: python set_webhook.py [set <url> | info | delete]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "set":
        if len(sys.argv) < 3:
            print("❌ URL رو هم بده: python set_webhook.py set https://your-app.vercel.app/api/webhook")
            sys.exit(1)
        set_webhook(sys.argv[2])
    elif action == "info":
        get_info()
    elif action == "delete":
        delete_webhook()
    else:
        print(f"دستور ناشناخته: {action}")
