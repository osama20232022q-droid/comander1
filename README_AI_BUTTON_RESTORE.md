# AI Button Restore Patch

هذا الباتش يرجّع زر **🤖 دردشة AI** للقائمة الرئيسية ويدمج handler الدردشة مع البوت.

## الملفات التي تستبدلها في GitHub

```
app/bot.py
app/keyboards.py
app/services/buttons.py
app/handlers/ai_chat.py
app/services/ai_chat.py
```

بعد الرفع:

1. Commit changes
2. Railway -> Redeploy

## متغيرات Railway المطلوبة

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
AI_CHAT_ENABLED=true
AI_DAILY_LIMIT=30
AI_CONTEXT_MESSAGES=10
AI_MAX_INPUT_CHARS=3500
AI_MAX_OUTPUT_TOKENS=1800
AI_MAX_FILE_CHARS=12000
AI_REQUEST_TIMEOUT=45
```

## ملاحظات

- يظهر الزر باسم: 🤖 دردشة AI
- يوجد أمر جانبي: /ai
- الدردشة تعمل فقط داخل وضع AI حتى لا تبطّئ باقي البوت.
- إذا كان زر AI مخفيًا بسبب إعدادات الأزرار من قاعدة البيانات، افتح: لوحة الأدمن -> الأزرار -> استرجاع الأزرار الافتراضية، أو أضف زر باسم 🤖 دردشة AI مربوط بـ action_key: ai_chat.
