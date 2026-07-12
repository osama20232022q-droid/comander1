from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from app.config import settings


@dataclass
class _UserWindow:
    events: deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0
    last_notice_at: float = 0.0


class InboundRateLimiter:
    """Small in-memory inbound limiter.

    It protects a single bot process from accidental button spam and basic floods.
    It intentionally does not claim to be a distributed anti-DDoS system.
    """

    def __init__(self) -> None:
        self._windows: dict[int, _UserWindow] = defaultdict(_UserWindow)
        self._lock = asyncio.Lock()

    async def check(self, user_id: int) -> tuple[bool, int]:
        now = time.monotonic()
        window_seconds = settings.inbound_limit_window_seconds
        async with self._lock:
            state = self._windows[user_id]
            while state.events and now - state.events[0] > window_seconds:
                state.events.popleft()

            if state.blocked_until > now:
                return False, max(1, int(state.blocked_until - now))

            state.events.append(now)
            if len(state.events) > settings.inbound_limit_count:
                state.blocked_until = now + settings.inbound_block_seconds
                state.events.clear()
                return False, settings.inbound_block_seconds

            # Opportunistic pruning so the dictionary does not grow forever.
            if len(self._windows) > 50_000:
                stale = [uid for uid, item in self._windows.items() if not item.events and item.blocked_until <= now]
                for uid in stale[:10_000]:
                    self._windows.pop(uid, None)
            return True, 0

    async def should_notify(self, user_id: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            state = self._windows[user_id]
            if now - state.last_notice_at < 8:
                return False
            state.last_notice_at = now
            return True


_limiter = InboundRateLimiter()


async def inbound_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    allowed, wait_seconds = await _limiter.check(user.id)
    if allowed:
        return

    if await _limiter.should_notify(user.id):
        text = f"⚠️ ضغطت أو أرسلت بسرعة كبيرة. انتظر {wait_seconds} ثانية ثم حاول مرة ثانية."
        try:
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text(text)
        except Exception:
            pass
    raise ApplicationHandlerStop
