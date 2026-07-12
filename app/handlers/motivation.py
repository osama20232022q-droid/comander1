from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.models import MotivationLog, User
from app.services.motivation import quote_for_user


async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        recent = []
        if user:
            rows = db.scalars(
                select(MotivationLog)
                .where(MotivationLog.user_id == user.id)
                .order_by(MotivationLog.created_at.desc())
                .limit(20)
            ).all()
            recent = [r.message_key for r in rows]
        quote = quote_for_user(recent)
        if user:
            db.add(MotivationLog(user_id=user.id, message_key=quote.get("key", "unknown")))
            db.commit()
    await update.effective_message.reply_text(f"🔥 حفزني\n\n{quote['text']}")
