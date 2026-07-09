# V4 Fix Specification

## Keyboard System
All user-facing buttons are ReplyKeyboardMarkup. Inline callbacks are retained only for backward compatibility with old messages.

## Deep Study Plan
The plan generator now uses:
- page/lecture count provided by student
- study level
- target grade
- exam type
- question pattern
- days left
- material attachment count and past-question count
- medical-study multiplier

Raw student request JSON is removed from final HTML.

## Pomodoro
- Reply keyboard only
- presets + custom time
- active session saved in database
- `/remaining` and `⌛ كم المتبقي؟` show seconds and progress bar
- automatic finish job sends break recommendation

## Certificates
Certificates are earned, not freely generated.
- Daily certificate: at least 3 focused study hours today or a day stronger than recent average.
- Weekly certificate: 5 active days + 10 hours in last 7 days, or 20 sessions.
- Heat stamp removed; replaced by English bot signature.

## Admin
Admin-only features:
- pending users
- manual activation by Telegram ID / username
- ban user
- unban user
- backup export
- backup file check
- DB status

No admin button is shown to subscribers.

## Motivation
- 25 quotes in JSON.
- Avoids repeating last 20 quote keys when possible.
- Includes Quranic-style short motivation inspired by the uploaded PDF asset.
