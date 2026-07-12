# ابدأ من هنا

## قبل الرفع

لا ترفع إلى GitHub:

- `.env`
- توكن البوت
- مفتاح Gemini
- `BACKUP_ENCRYPTION_KEY`
- ملفات قواعد البيانات `*.sqlite3`
- النسخ الاحتياطية الحقيقية

## الملفات التي يجب أن تظهر في الصفحة الرئيسية للمستودع

```text
app/
alembic/
assets/
docs/
tests/
.github/
Dockerfile
railway.json
alembic.ini
requirements.txt
requirements-dev.txt
run.py
README.md
```

## أول متغيرات Railway

```env
BOT_TOKEN=توكن_بوت_فاذر
ADMIN_IDS=معرفك_الرقمي
ENVIRONMENT=production
TIMEZONE=Asia/Baghdad
```

ثم اربط PostgreSQL حتى يظهر `DATABASE_URL`.
