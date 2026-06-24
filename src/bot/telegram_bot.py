"""Reality Doctor — Telegram front-end.

Flow per message: scrub (inside Doctor) -> FAQ router (free) -> rate-limited RAG.
Adds a privacy notice when secrets were removed, 👍/👎 feedback buttons, and the
@ExtenVPNBot footer. Run with:  python -m src.bot.telegram_bot
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.core.config import settings
from src.core.log import configure_logging, get_logger
from src.bot.feedback import FeedbackStore
from src.bot.rate_limit import DailyRateLimiter
from src.doctor import Doctor
from src.safety import scrub

configure_logging(settings.log_level)
logger = get_logger(__name__)

START_TEXT = (
    "🩺 *Reality Doctor*\n\n"
    "Пришли свою ошибку, лог `journalctl -u xray`, вывод `blockcheck` или просто "
    "опиши проблему — подскажу, что чинить, по гайдам Anti-Censorship Handbook.\n\n"
    "🔒 *Приватность:* секреты (`vless://`, ключи, UUID) я вырезаю из сообщения "
    "до обработки. Но лучше присылай с плейсхолдерами, не реальные ключи."
)

_VOTE_KB = InlineKeyboardMarkup(
    [[InlineKeyboardButton("👍", callback_data="fb:up"),
      InlineKeyboardButton("👎", callback_data="fb:down")]]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        START_TEXT + settings.bot_footer, parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doctor: Doctor = context.application.bot_data["doctor"]
    limiter: DailyRateLimiter = context.application.bot_data["limiter"]

    text = update.message.text or ""
    chat_id = update.effective_chat.id

    # FAQ fast-path first (free, no rate limit).
    reply = await doctor.diagnose(text, allow_llm=False)
    if reply.route is None:
        # Needs the LLM — apply the daily budget.
        if limiter.allow(chat_id):
            reply = await doctor.diagnose(text, allow_llm=True)
        else:
            await update.message.reply_text(
                "⏳ На сегодня лимит бесплатных разборов исчерпан — возвращайся завтра."
                + settings.bot_footer
            )
            return

    parts = []
    if reply.notice:
        parts.append(reply.notice)
    parts.append(reply.answer)
    parts.append(settings.bot_footer)
    body = "\n\n".join(p for p in parts if p)

    sent = await update.message.reply_text(body, disable_web_page_preview=True)
    # Stash context for the 👍/👎 callback, keyed by the answer's message id.
    # Store the SCRUBBED question so the feedback log never holds secrets.
    context.chat_data[sent.message_id] = {
        "question": scrub(text).text,
        "answer": reply.answer,
        "route": reply.route,
    }
    await sent.edit_reply_markup(reply_markup=_VOTE_KB)


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    feedback: FeedbackStore = context.application.bot_data["feedback"]
    query = update.callback_query
    vote = "up" if query.data == "fb:up" else "down"

    ctx = context.chat_data.get(query.message.message_id)
    if ctx is not None:
        feedback.record(
            chat_id=update.effective_chat.id,
            question=ctx["question"],
            answer=ctx["answer"],
            route=ctx["route"],
            vote=vote,
        )
    await query.answer("Спасибо за отзыв!")
    await query.edit_message_reply_markup(reply_markup=None)


def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["doctor"] = Doctor()
    app.bot_data["limiter"] = DailyRateLimiter(settings.rate_limit_per_day)
    app.bot_data["feedback"] = FeedbackStore(settings.feedback_log)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern=r"^fb:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (get one from @BotFather).")
    logger.info("Starting Reality Doctor bot (provider=%s)...", settings.llm_provider)
    build_application().run_polling()


if __name__ == "__main__":
    main()
