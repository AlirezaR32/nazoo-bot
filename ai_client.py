"""
ai_client.py — کلاینت async برای OpenModel.ai (سازگار با Anthropic Messages API)

OpenModel.ai یه multi-model gateway هست — مدل پیش‌فرض اینجا deepseek-v4-flash.
این فایل فقط در حالت polling (bot.py) استفاده میشه. برای Vercel، یه نسخه‌ی
sync مستقیم در api/webhook.py پیاده‌سازی شده (تا importهای اضافه نگیریم).
"""
import logging
from anthropic import AsyncAnthropic, APIError, APITimeoutError, RateLimitError

from config import (
    OPENMODEL_API_KEY, OPENMODEL_BASE_URL, AI_MODEL,
    MAX_TOKENS, TEMPERATURE, PERSONALITY_FILE, BOT_NAME,
)
from personality_loader import load_personality

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self):
        if not OPENMODEL_API_KEY:
            raise ValueError("OPENMODEL_API_KEY تنظیم نشده! فایل .env رو چک کن.")

        self.client = AsyncAnthropic(
            api_key=OPENMODEL_API_KEY,
            base_url=OPENMODEL_BASE_URL,
        )
        self.model       = AI_MODEL
        self.personality = load_personality(PERSONALITY_FILE, BOT_NAME)
        logger.info(f"🤖 AI ready → {OPENMODEL_BASE_URL} | model: {self.model}")

    def _system(self, user_name: str, facts: list[str]) -> str:
        prompt = self.personality
        if user_name:
            prompt += f"\n\n---\n**اسم کاربر:** {user_name}"
        if facts:
            prompt += "\n\n**چیزایی که از این کاربر میدونی:**\n"
            prompt += "\n".join(f"- {f}" for f in facts)
            prompt += "\n\nاز این اطلاعات طبیعی استفاده کن — اعلام نکن که یادته."
        return prompt

    async def chat(
        self,
        user_name: str,
        user_text: str,
        history: list[dict],
        facts: list[str],
    ) -> str:
        messages = list(history) + [{"role": "user", "content": user_text}]
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=self._system(user_name, facts),
                messages=messages,
            )
            return "".join(b.text for b in resp.content if b.type == "text").strip()

        except RateLimitError:
            logger.warning("Rate limit از OpenModel خورد")
            return "داری خیلی سریع پیام میدی 😅 یه لحظه صبر کن!"

        except APITimeoutError:
            logger.warning("OpenModel timeout شد")
            return "سرور جواب نداد 😐 دوباره امتحان کن."

        except APIError as e:
            logger.error(f"APIError: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
