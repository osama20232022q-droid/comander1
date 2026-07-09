from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, MotivationLog
from app.services.motivation import random_quote


async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    quote = random_quote()
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if user:
            db.add(MotivationLog(user_id=user.id, message_key=quote.get("key", "unknown")))
            db.commit()
    await update.effective_message.reply_text(f"🔥 حفزني\n\n{quote['text']}")
