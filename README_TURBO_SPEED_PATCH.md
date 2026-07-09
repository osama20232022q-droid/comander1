# Study Commander Turbo Speed Patch

هذا الباتش لتسريع رد البوت مع زيادة عدد المشتركين. استبدل الملفات التالية فقط:

```text
app/bot.py
app/db.py
app/keyboards.py
app/services/buttons.py
app/services/access_cache.py
app/repositories/users_repo.py
```

## ماذا يفعل؟

- يقلل ضربات قاعدة البيانات عند كل زر.
- يضيف Cache لصلاحية المستخدم/الاشتراك/تأكيد الملف الشخصي.
- يوقف commit غير الضروري في `ensure_user`، لأن الكود القديم كان يكتب في قاعدة البيانات تقريبًا كل رسالة.
- يضيف Cache فعلي للـ Reply Keyboards حتى لا يعاد بناؤها من قاعدة البيانات بكل رد.
- يرفع إعدادات Telegram HTTP connection pool.
- يحسن SQLite إن استخدمته عبر WAL و busy timeout.
- يجعل زر `⌛ كم المتبقي؟` سريعًا جدًا لأنه يعتمد على session داخل الذاكرة ولا يحتاج Database.

## متغيرات Railway المقترحة

أضف هذه القيم في worker → Variables:

```env
ACCESS_CACHE_TTL=60
ACCESS_CACHE_MAX=20000
BUTTON_CACHE_TTL=300
BOT_CONCURRENT_UPDATES=64
TG_CONNECTION_POOL_SIZE=64
TG_POOL_TIMEOUT=10
TG_READ_TIMEOUT=20
TG_WRITE_TIMEOUT=20
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=20
DB_POOL_RECYCLE=1800
PRAYER_JOB_INTERVAL=60
PRAYER_REMOTE_TIMEOUT=2
```

إذا قاعدة البيانات Neon بعيدة أو مجانية، هذه القيم تساعد لكنها لا تلغي حدود الخطة. أسرع إعداد عملي هو:
- قاعدة PostgreSQL بأقرب Region لأوروبا/تركيا إن متاح.
- عدم تشغيل AI في كل رسالة، فقط داخل زر دردشة AI.
- عدم تحليل PDF داخل نفس رد الزر، بل إرسال "جاري التحليل" ثم تنفيذ المهمة.

## ملاحظة

إذا فعّلت/حظرت مستخدمًا من الأدمن، قد يأخذ كاش الصلاحية حتى `ACCESS_CACHE_TTL` ثانية، لكن الكود يحاول إفراغ cache عند التفعيل والحظر وتعديل الملف.
