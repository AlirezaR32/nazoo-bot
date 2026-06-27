"""
Nazoo — Telegram AI Chatbot (حالت Polling)
برای اجرا روی لپ‌تاپ یا VPS — برای Vercel از api/webhook.py استفاده کن
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from telegram.constants import ChatAction
from telegram.error import TelegramError

from config import TELEGRAM_TOKEN, BOT_NAME
from memory import MemoryManager
from ai_client import AIClient
from group_utils import should_respond_in_group, strip_mention

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

memory = MemoryManager()
ai     = AIClient()


# ── Startup ───────────────────────────────────────────────────────────────────

async def on_startup(app: Application):
    await memory.init()
    me = await app.bot.get_me()
    app.bot_data["username"] = (me.username or "").lower()
    app.bot_data["bot_id"]   = me.id
    logger.info(f"✨ {BOT_NAME} (@{me.username}) آماده‌ست!")


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await memory.ensure_user(user.id, user.first_name, user.username)
    await update.message.reply_text(
        f"سلام {user.first_name}! 👋\n"
        f"من {BOT_NAME} ام — یه AI که فارسی و انگلیسی بلده، حافظه داره،\n"
        f"و امیدوارم یه‌کم بامزه هم باشه 😊\n\n"
        f"فقط حرف بزن. /help رو هم بزن اگه خواستی دستورات رو ببینی."
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 دستورات:\n\n"
        "/start    — شروع\n"
        "/reset    — پاک کردن تاریخچه گفتگو\n"
        "/forget   — فراموش کردن اطلاعاتت\n"
        "/memory   — نمایش چیزایی که ازت یادمه\n"
        "/stats    — آمار گفتگو\n\n"
        "📌 در گروه‌ها: منشن کن یا ریپلای بزن."
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await memory.clear_history(user.id)
    await update.message.reply_text("تاریخچه پاک شد! 🔄 از صفر شروع می‌کنیم.")


async def cmd_forget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await memory.clear_facts(user.id)
    await update.message.reply_text("همه چیزی که ازت یاد داشتم رو فراموش کردم 🧹")


async def cmd_memory_show(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    facts = await memory.get_facts(user.id)
    if not facts:
        await update.message.reply_text("هنوز چیزی ازت یاد نگرفتم 🤷 بیشتر حرف بزن!")
        return
    lines = "\n".join(f"• {f}" for f in facts)
    await update.message.reply_text(f"🧠 چیزایی که ازت یادمه:\n\n{lines}")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    stats = await memory.get_stats(user.id)
    if stats:
        since = (stats["since"] or "")[:10]
        await update.message.reply_text(
            f"📊 آمار {stats['name']}:\n"
            f"• پیام‌ها: {stats['messages']}\n"
            f"• از: {since or 'نامشخص'}"
        )
    else:
        await update.message.reply_text("هنوز اطلاعاتی ندارم ازت! /start بزن اول.")


# ── Message Handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not msg.text or not user:
        return

    bot_username = ctx.bot_data.get("username", "")
    bot_id       = ctx.bot_data.get("bot_id", 0)

    if chat.type in ("group", "supergroup"):
        mentions = []
        if msg.entities:
            for ent in msg.entities:
                if ent.type == "mention":
                    mentions.append(
                        msg.text[ent.offset: ent.offset + ent.length].lstrip("@")
                    )
        reply_to_bot = bool(
            msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == bot_id
        )
        if not should_respond_in_group(
            msg.text, mentions, reply_to_bot, bot_username, BOT_NAME, extra_aliases=("نازو",)
        ):
            return
        user_text = strip_mention(msg.text, bot_username, BOT_NAME, extra_aliases=("نازو",))
    else:
        user_text = msg.text.strip()

    if not user_text:
        return

    try:
        await ctx.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass

    await memory.ensure_user(user.id, user.first_name, user.username)

    history = await memory.get_history(user.id)
    facts   = await memory.get_facts(user.id)

    try:
        response = await ai.chat(
            user_name=user.first_name,
            user_text=user_text,
            history=history,
            facts=facts,
        )
    except Exception as e:
        logger.error(f"AI error (uid={user.id}): {e}")
        response = "یه مشکل فنی پیش اومد 😅 یه لحظه صبر کن و دوباره امتحان کن!"

    await msg.reply_text(response)

    await memory.add_message(user.id, "user",      user_text)
    await memory.add_message(user.id, "assistant", response)

    asyncio.create_task(_safe_extract(user.id, user_text))


async def _safe_extract(user_id: int, text: str):
    try:
        await memory.extract_and_save_facts(user_id, text)
    except Exception as e:
        logger.warning(f"Fact extraction error (uid={user_id}): {e}")


async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled exception: {ctx.error}", exc_info=ctx.error)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN تنظیم نشده! فایل .env رو چک کن.")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("forget",  cmd_forget))
    app.add_handler(CommandHandler("memory",  cmd_memory_show))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info(f"🚀 Starting {BOT_NAME} (polling mode)...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
