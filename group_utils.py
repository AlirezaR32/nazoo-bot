"""
group_utils.py — منطق مشترک تشخیص اینکه ربات باید در گروه جواب بده یا نه
استفاده میشه هم در bot.py (polling) هم در api/webhook.py (serverless)

این توابع کاملاً primitive-based هستن (string/bool/list) تا هم با
آبجکت‌های python-telegram-bot و هم با dict خام Telegram API کار کنن.
"""
import re


def should_respond_in_group(
    text: str,
    mentions: list[str],
    reply_to_bot: bool,
    bot_username: str,
    bot_name: str,
    extra_aliases: tuple[str, ...] = (),
) -> bool:
    """
    Args:
        text:          متن پیام
        mentions:      لیست usernameهای منشن‌شده در پیام (بدون @)
        reply_to_bot:  آیا این پیام ریپلای به خودِ رباته؟
        bot_username:  یوزرنیم ربات (بدون @)
        bot_name:      اسم نمایشی ربات (مثلاً Nazoo)
        extra_aliases: مستعارهای اضافه (مثلاً نام فارسی)
    """
    if not text:
        return False

    if reply_to_bot:
        return True

    bu = (bot_username or "").lower()
    if bu and bu in [m.lower() for m in mentions]:
        return True

    text_lower = text.lower().strip()
    aliases = (bot_name.lower(),) + tuple(a.lower() for a in extra_aliases if a)
    return any(text_lower.startswith(a) for a in aliases if a)


def strip_mention(
    text: str,
    bot_username: str,
    bot_name: str,
    extra_aliases: tuple[str, ...] = (),
) -> str:
    """منشن یا اسم ربات رو از ابتدای پیام حذف می‌کنه."""
    if bot_username:
        text = re.sub(rf"^@{re.escape(bot_username)}\s*", "", text, flags=re.IGNORECASE)

    for alias in (bot_name,) + tuple(extra_aliases):
        if alias:
            text = re.sub(rf"^{re.escape(alias)}\s*[,،:؟]?\s*", "", text, flags=re.IGNORECASE)

    return text.strip()
