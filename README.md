# Study Commander Bot

Telegram study-command bot for medical students: planning, lecture analysis, Pomodoro, food/water, sleep routine, discipline reports, weekly certificates, admin subscriptions, and fast demo testing.

## Main features

- Telegram reply-keyboard UX with Arabic/Iraqi strict command style.
- Private multi-user data isolation.
- Subscription gate: students cannot use the bot until the admin activates a paid plan.
- Admin panel only for `ADMIN_IDS`.
- Plans supported from admin panel:
  - 7-day trial
  - monthly
  - 3 months
  - 6 months
  - yearly
- Block/unblock users.
- Add subjects and lectures.
- Upload PDF lectures and analyze:
  - pages
  - word density
  - image/list score
  - difficulty
  - expected study time
  - exam-risk notes
- Pomodoro presets: 25/5, 50/10, 90/15.
- Timer notifications.
- Focus score after sessions.
- Food and water logging with approximate Iraqi-food calories.
- Sleep logging and routine experiments.
- Rescue-day mode.
- Daily reports and Discipline Score.
- Weekly one-page HTML certificates.
- Student evaluation table after demo/certificate usage.
- `🧪 تجربة الخدمات`: instantly creates safe demo data so you can test all bot services without waiting a week.
- Iraq timezone support: `Asia/Baghdad`.

## Railway deployment

1. Create a Telegram bot with `@BotFather` and copy the token.
2. Push this project to GitHub.
3. In Railway:
   - New Project -> Deploy from GitHub repo.
   - Add environment variables:
     - `BOT_TOKEN`
     - `ADMIN_IDS` = your Telegram numeric ID
     - `TIMEZONE=Asia/Baghdad`
     - Optional: `OPENAI_API_KEY`
4. Recommended for persistent SQLite:
   - Add a Railway Volume mounted at `/data`
   - Set:
     - `DATABASE_PATH=/data/study_commander.sqlite3`
     - `UPLOADS_DIR=/data/uploads`
     - `CERTIFICATES_DIR=/data/certificates`
5. Deploy.

This bot uses Telegram long polling, so it does not need a public webhook or HTTP port.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
python run.py
```

## Admin flow

1. Start the bot from your Telegram account.
2. Open `🧑‍✈️ الأدمن`.
3. Click `🔐 تفعيل اشتراك`.
4. Enter student Telegram numeric ID or username.
5. Select plan.
6. Confirm `✅ دفع`.
7. The student gets full access until the subscription expires.

If the student has not opened the bot yet, you can activate by numeric ID. When they later press `/start`, their subscription will be recognized.

## Test all services immediately

From your admin account:
1. Press `🧪 تجربة الخدمات`.
2. Press `🧪 تشغيل تجربة كاملة`.

The bot creates demo-only data under your account:
- subject
- lecture analysis
- study sessions
- food and water
- discipline event
- routine experiment
- report
- certificate
- student evaluation

Then inspect the regular sections.

## Important safety notes

- Food calories are approximate estimates, not medical or nutrition advice.
- Penalties are non-harmful: no sleep deprivation, no food restriction, no unsafe behavior.
- The bot records execution and habits; it does not diagnose mental or physical health conditions.
- SQLite is fine for a first production version. For large paid use, migrate to PostgreSQL.

## Suggested next upgrades

- PostgreSQL adapter.
- Exact prayer-time API by city.
- PDF certificate export in addition to HTML.
- Web admin dashboard.
- Practical-slide image analysis.
- Spaced repetition calendar.
