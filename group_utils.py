"""
group_utils.py — منطق مشترک تشخیص اینکه ربات باید در گروه جواب بده یا نه
استفاده میشه هم در bot.py (polling) هم در api/webhook.py (serverless)

این توابع کاملاً primitive-based هستن (string/bool/list) تا هم با
آبجکت‌های python-telegram-bot و هم با dict خام Telegram API کار کنن.
"""
import re


def is_reply_to_bot(reply_to_message, bot_id: int | None = None, bot_username: str = "") -> bool:
    """آیا این پیام به ربات ریپلای شده؟"""
    if not reply_to_message:
        return False

    if isinstance(reply_to_message, dict):
        from_user = reply_to_message.get("from") or reply_to_message.get("from_user") or {}
    else:
        from_user = getattr(reply_to_message, "from_user", None)

    if isinstance(from_user, dict):
        user_id = from_user.get("id")
        username = (from_user.get("username") or "").lower()
        is_bot = from_user.get("is_bot", False)
    elif from_user is not None:
        user_id = getattr(from_user, "id", None)
        username = (getattr(from_user, "username", "") or "").lower()
        is_bot = getattr(from_user, "is_bot", False)
    else:
        return False

    if bot_id is not None and user_id == bot_id:
        return True

    if bot_username:
        return username == bot_username.lower()

    return bool(is_bot)


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
