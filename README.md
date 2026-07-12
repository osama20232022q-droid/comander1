# Study Commander Bot V8 — Professional Hardened

بوت تيليغرام عربي لتنظيم الدراسة والانضباط، مع المواد، الخطط، البومودورو، غرفة العمليات، تقارير HTML، Gemini، لوحة أدمن، النسخ الاحتياطية، ومواقيت الصلاة.

## أهم تحسينات V8

- Alembic Migrations بدل الاعتماد على `create_all` وحده.
- معالجة متسلسلة افتراضيًا حتى لا تختلط خطوات التسجيل والتقارير.
- حماية من ضغط الأزرار والإرسال السريع.
- حد لحجم ملفات AI قبل تنزيلها.
- حذف الملفات المؤقتة بعد إرسال التقارير والخطط والشهادات.
- عداد Gemini يومي محفوظ في قاعدة البيانات ولا يرجع للصفر عند إعادة تشغيل السيرفر.
- نسخ احتياطية مشفرة اختياريًا بمفتاح Fernet.
- إخفاء التفاصيل التقنية عن المستخدم وإبقاؤها في Railway Logs.
- إعدادات Telegram الموجودة في `.env` أصبحت مرتبطة فعليًا بالكود.
- GitHub Actions: اختبارات، Ruff، Bandit، pip-audit، CodeQL، Dependabot.
- تنظيف ملفات الشروحات القديمة ونقلها إلى `docs/legacy/`.

## التشغيل السريع

1. انسخ `.env.example` إلى `.env` محليًا فقط.
2. أضف:

```env
BOT_TOKEN=...
ADMIN_IDS=رقم_معرفك
ENVIRONMENT=production
```

3. شغّل:

```bash
pip install -r requirements.txt
python run.py
```

عند التشغيل، يطبق Alembic آخر تحديثات قاعدة البيانات تلقائيًا.

## Railway

- ارفع محتويات المجلد إلى جذر مستودع GitHub، وليس ملف ZIP.
- أنشئ مشروع Railway من المستودع.
- أضف PostgreSQL واربط `DATABASE_URL`.
- أضف متغيرات Telegram وGemini.
- Railway يستخدم `Dockerfile` و`railway.json` تلقائيًا.

راجع: `docs/RAILWAY_DEPLOY.md`

## Gemini

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
AI_CHAT_ENABLED=true
```

Gemini للمساعدة الدراسية فقط. لا يغيّر الدرجات أو التقارير أو صلاحيات المستخدمين.

## نسخ احتياطية مشفرة

ولّد المفتاح مرة واحدة:

```bash
python -m app.tools.generate_backup_key
```

ضع الناتج في Railway Variables:

```env
BACKUP_ENCRYPTION_KEY=...
REQUIRE_ENCRYPTED_BACKUPS=true
```

لا ترفع هذا المفتاح إلى GitHub. فقدانه يعني عدم القدرة على فتح النسخ المشفرة القديمة.

## الفحوص المحلية

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
bandit -q -r app -ll
```

## ملاحظة توسع

هذه النسخة مناسبة جدًا للاستعمال الشخصي والمجموعات الصغيرة والمتوسطة. قاعدة البيانات ما زالت تستخدم SQLAlchemy المتزامن داخل handlers؛ عند تحويل المشروع إلى منصة عامة ضخمة جدًا، تكون الخطوة التالية فصل الأعمال الثقيلة وتحويل طبقة البيانات إلى Async SQLAlchemy أو خدمة مستقلة.
