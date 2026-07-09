# Study Commander Bot V3 — Technical Spec

## Architecture

```text
Telegram Bot on Railway
        |
        | SQLAlchemy
        v
External PostgreSQL preferred / SQLite fallback
        |
        | Telegram file_id references
        v
Telegram cloud media retrieval
```

## Roles

- `admin`: IDs defined in `ADMIN_IDS`.
- `student`: normal user.

Admin-only features are hidden by Telegram ID check.

## Main Tables

- users
- student_profiles
- subjects
- attachments
- study_plans
- pomodoro_sessions
- food_logs
- certificates
- motivation_logs
- admin_actions
- backup_records

## File Strategy

The bot stores Telegram file IDs instead of hosting files. This gives large practical capacity without paid object storage. The database keeps metadata and file references.

## Safety

- Admin backups export JSON.
- Restore auto-write is disabled by default; restore file is only validated to prevent accidental overwrite.
- To enable full restore later, add double confirmation and transaction rollback.

## Upgrade points

- Connect prayer times API or manual city-based prayer settings.
- Add OCR/AI content analysis for uploaded PDFs.
- Add full OpenAI plan generation if `OPENAI_API_KEY` is supplied.
- Add external object storage if you later need independent file storage outside Telegram.
