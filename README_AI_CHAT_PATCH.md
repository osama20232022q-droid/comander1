# Study Commander Bot - AI Chat Patch

هذا الباتش يضيف زر **🤖 دردشة AI** للبوت، مع فهم قوي للنصوص والملازم والأسئلة.

## الملفات الجديدة
انسخ هذين الملفين إلى مشروعك:

```text
app/services/ai_chat.py
app/handlers/ai_chat.py
```

## تعديل requirements.txt
أضف السطر التالي إذا تريد قراءة PDF داخل دردشة AI:

```text
pypdf==5.1.0
```

## متغيرات Railway المطلوبة

```env
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

## تعديل app/services/buttons.py
داخل قائمة `DEFAULT_BUTTONS` أضف هذا الزر ضمن أزرار القائمة الرئيسية:

```python
{"action_key": "ai_chat", "label": "🤖 دردشة AI", "scope": "main", "button_type": "reply", "row_order": 6, "col_order": 1, "style": "primary"},
```

ضعه قبل زر `help` أو قبل زر `admin_panel`.

## تعديل app/bot.py

### 1) أضف import:

```python
from app.handlers.ai_chat import show_ai_chat, handle_ai_chat_text, handle_ai_chat_file
```

### 2) داخل `handle_text` بعد فحص onboarding و `_require_ready`، وقبل بقية الأزرار، أضف:

```python
if await handle_ai_chat_text(update, context, text):
    return
```

### 3) داخل قسم القائمة الرئيسية أضف:

```python
elif main_action == "ai_chat" or text == "🤖 دردشة AI":
    await show_ai_chat(update, context)
```

ملاحظة: إذا أضفت السطر العام `handle_ai_chat_text` فوق، فهو يكفي غالبًا.

### 4) داخل `handle_files`، في البداية بعد `flow = ...` أضف:

```python
if flow == "ai_chat":
    if not await _require_ready(update, context):
        return
    if await handle_ai_chat_file(update, context):
        return
```

### 5) داخل `configure_bot_profile` أضف أمر:

```python
BotCommand("ai", "دردشة AI للفهم والشرح")
```

### 6) داخل `main()` أضف handler للأمر:

```python
app.add_handler(CommandHandler("ai", show_ai_chat))
```

## طريقة الاستخدام
- الطالب يضغط: **🤖 دردشة AI**
- يرسل سؤال أو نص ملزمة.
- يختار: شرح / MCQ / Short essay / فهم طبي.
- يقدر يرسل PDF نصي واضح ويقوم البوت بتلخيصه وشرحه.

## ملاحظات مهمة
- لا تشغل AI على كل رسالة خارج وضع الدردشة حتى لا يصير البوت بطيء ومكلف.
- إذا لا توجد `OPENAI_API_KEY`، الزر سيشرح لك ماذا تضيف في Railway.
- قراءة الصور والصوت والفيديو غير مفعلة في هذا الباتش؛ أرسل النص أو PDF.
