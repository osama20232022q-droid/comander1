# نشر Study Commander V8 على Railway

## 1. GitHub

فك ضغط الحزمة، وارفع **محتويات المجلد** إلى جذر المستودع. لا ترفع ZIP وحده.

## 2. إنشاء الخدمة

في Railway:

1. New Project.
2. Deploy from GitHub Repo.
3. اختر المستودع.
4. أضف PostgreSQL من New → Database → PostgreSQL.
5. اربط خدمة PostgreSQL بخدمة البوت حتى يتوفر `DATABASE_URL`.

## 3. Variables

أضف:

```env
BOT_TOKEN=...
ADMIN_IDS=...
ENVIRONMENT=production
TIMEZONE=Asia/Baghdad
BOT_CONCURRENT_UPDATES=1
```

لـ Gemini:

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
AI_CHAT_ENABLED=true
```

للنسخ المشفرة:

```env
BACKUP_ENCRYPTION_KEY=...
REQUIRE_ENCRYPTED_BACKUPS=true
```

## 4. النشر

Railway يبني `Dockerfile` ثم يشغّل:

```text
python run.py
```

داخل التشغيل، Alembic يطبق Migrations تلقائيًا. إذا فشل Migration، يتوقف البوت بدل تشغيل نسخة غير متوافقة مع قاعدة البيانات.

## 5. التحقق

افتح Deploy Logs وابحث عن:

```text
Study Commander Bot v8.0.0 — Professional Hardened started
```

ثم أرسل `/start` للبوت.

## تنبيه

لا تضع الأسرار داخل ملفات GitHub. ضعها في Railway Variables فقط.
