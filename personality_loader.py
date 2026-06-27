"""
personality_loader.py — بارگذاری فایل شخصیت ربات
استفاده مشترک در ai_client.py (حالت polling) و api/webhook.py (حالت Vercel)
"""
import logging

logger = logging.getLogger(__name__)


def load_personality(path: str, bot_name: str) -> str:
    """
    محتوای فایل شخصیت رو می‌خونه. اگه پیدا نشد، یه پیش‌فرض مینیمال برمی‌گردونه.

    نکته: روی Vercel، working directory ریشه‌ی پروژه‌ست (نه پوشه‌ی api/)
    پس مسیر نسبی مثل "personality.txt" به درستی resolve میشه.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                logger.info(f"✅ Personality '{path}' loaded.")
                return content
    except FileNotFoundError:
        logger.warning(f"⚠️ '{path}' پیدا نشد — از پیش‌فرض استفاده میشه.")
    return (
        f"تو {bot_name} هستی — یه دستیار هوش مصنوعی بامزه، گرم و دوست‌داشتنی. "
        f"جواب‌هات کوتاه و فارسی عامیانه باشه. هیچوقت با 'البته!' یا 'حتماً!' شروع نکن."
    )
