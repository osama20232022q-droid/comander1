# Study Commander Bot - Full Merged Build

هذه نسخة كاملة مدموجة تضم آخر الإضافات:

- لوحة كيبورد موحدة.
- لوحة أدمن مع الإحصائيات وإدارة الأزرار.
- ترتيب/حذف/إعادة تسمية/إضافة أزرار.
- الأزرار المحذوفة واسترجاعها.
- أذكار الصلاة مع تفعيل/إلغاء تفعيل ومحافظات العراق.
- تعديل أوقات الصلاة يدويًا.
- البومودورو يتوقف قبل الصلاة بدقيقة.
- زر حفزني بصيغة قرآنية.
- ضبط يدوي، تعديل المعلومات، تغيير النظام، وإضافة عادات.
- دردشة AI مستقلة قوية للفهم والشرح و MCQ و Short essay.
- Turbo speed cache لتحسين سرعة الرد.
- دعم PostgreSQL خارجي عبر DATABASE_URL أو SQLite كبديل.

## أهم متغيرات Railway

```env
BOT_TOKEN=
ADMIN_IDS=
TIMEZONE=Asia/Baghdad
BOT_SIGNATURE=Study Commander Bot
DATABASE_URL=
DATABASE_PATH=/data/study_commander.sqlite3
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
AI_CHAT_ENABLED=true
AI_DAILY_LIMIT=30
ACCESS_CACHE_TTL=60
BUTTON_CACHE_TTL=300
BOT_CONCURRENT_UPDATES=64
TG_CONNECTION_POOL_SIZE=64
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
PRAYER_REMOTE_TIMEOUT=2
```

## الرفع على GitHub

ارفع محتويات هذا المجلد مباشرة إلى جذر المستودع بحيث تظهر:

```text
app/
assets/
docs/
run.py
requirements.txt
Dockerfile
Procfile
railway.json
README.md
.env.example
```

ثم اعمل Redeploy من Railway.

## ملاحظة

إذا كانت الأزرار عندك مخربطة بعد التحديث، افتح:

لوحة الأدمن -> الأزرار -> استرجاع الأزرار الافتراضية

ثم جرّب زر دردشة AI من القائمة الرئيسية.
