# رفع النسخة من iPad

1. فك ضغط الملف داخل تطبيق Files.
2. استخدم تطبيق Working Copy لنسخ محتويات المجلد إلى مستودع GitHub.
3. يجب أن يظهر `Dockerfile` و`run.py` و`railway.json` مباشرة في الصفحة الرئيسية للمستودع، وليس داخل ZIP أو مجلد إضافي.
4. لا ترفع ملف `.env`.
5. ارفع `.env.example` عادي.
6. بعد Push، Railway يعيد النشر تلقائيًا.

## متغيرات Railway المهمة

```env
BOT_TOKEN=...
ADMIN_IDS=...
DATABASE_URL=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta/interactions
AI_CHAT_ENABLED=true
```
