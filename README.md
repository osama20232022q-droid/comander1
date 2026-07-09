# Study Commander Bot V5 — Admin Buttons & Stats

نسخة محسنة من بوت Study Commander مع إصلاحات لوحة الأدمن وإدارة الأزرار.

## أهم إضافات V5

- إصلاح خيار **📊 إحصائيات النظام** داخل لوحة الأدمن.
- عرض عدد المستخدمين، المشتركين، بانتظار التفعيل، المحظورين، المنتهية اشتراكاتهم، المواد، الملفات، الخطط، الجلسات، الشهادات، والأزرار.
- إضافة **🧩 الأزرار** داخل لوحة الأدمن فقط.
- إدارة الأزرار من داخل البوت:
  - حذف/إخفاء زر معين مع شاشة تأكيد منفصلة.
  - خانة **🗑️ الأزرار المحذوفة** لاسترجاع الأزرار المحذوفة.
  - إضافة زر جديد في لوحة الكيبورد.
  - إضافة زر شفاف Inline يظهر تحت زر **🔘 الأزرار الشفافة**.
  - إعادة تسمية زر موجود.
  - تعديل نمط الزر: عادي/أزرق/أخضر/أحمر.
  - استرجاع الأزرار الافتراضية.
- الأزرار الحساسة مثل لوحة الأدمن وإدارة الأزرار محمية من الحذف حتى لا تفقد الوصول للإدارة.

> ملاحظة: Telegram قد لا يلوّن أزرار Reply Keyboard فعليًا في كل التطبيقات، لذلك يخزن البوت النمط ويعرض رمز اللون عند الحاجة.

## Railway Variables

```env
BOT_TOKEN=توكن_البوت
ADMIN_IDS=ايديك_الرقمي
TIMEZONE=Asia/Baghdad
BOT_SIGNATURE=Study Commander Bot
```

للـ PostgreSQL الخارجي:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
```

إذا لم تضع `DATABASE_URL` سيعمل SQLite:

```env
DATABASE_PATH=/data/study_commander.sqlite3
```

## الرفع إلى GitHub

ارفع محتويات الملف إلى جذر المستودع بحيث تظهر:

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
