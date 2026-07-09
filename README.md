# Study Commander Bot V4 Professional

نسخة V4 أصلحت الملاحظات الأساسية:

- كل الأزرار صارت داخل **لوحة الكيبورد** وليس Inline Keyboard.
- تمت إضافة زر `⌛ كم المتبقي؟` للبومودورو مع عرض الثواني ونسبة التقدم.
- تمت إضافة أوامر جانبية للبوت: `/start`, `/menu`, `/help`, `/remaining`, `/profile`, `/admin`.
- تم تحسين الخطة الدراسية المعمقة: لا تعرض بيانات الطالب الخام، ولا تبالغ بالوقت بناءً على عدد الملفات فقط. تعتمد الآن على الصفحات/المحاضرات، المستوى، الهدف، نوع الامتحان، نمط الأسئلة، الأيام، وأسئلة السنوات.
- الشهادات لا تُمنح بالضغط فقط؛ لها شروط واضحة: شهادة يوم مميز أو شهادة أسبوعية.
- الختم الدائري تحول إلى توقيع بوت بالحروف الإنكليزية: `S C B · A D S`.
- لوحة الأدمن أُعيد تنظيمها مع تفعيل مشترك يدويًا عبر Telegram ID أو username، وإعادة أزرار الحظر وإلغاء الحظر.
- زر `حفزني` يستخدم مجموعة أكبر من العبارات ولا يكرر آخر 20 عبارة قدر الإمكان.
- أُضيف ملف `assets/motivation/rsail_min_al_quran.pdf` كمصدر مرجعي للتحفيز، مع استخدام عبارات قصيرة مستوحاة دون عرض الكتاب كاملًا.
- تم تفعيل وصف البوت وقائمة الأوامر تلقائيًا عند التشغيل عبر Telegram Bot API إن سمحت صلاحيات البوت.

## التشغيل على Railway

ضع هذه المتغيرات داخل خدمة `worker`:

```env
BOT_TOKEN=توكن البوت
ADMIN_IDS=ايديك الرقمي
TIMEZONE=Asia/Baghdad
BOT_SIGNATURE=Study Commander Bot
```

قاعدة البيانات الخارجية اختيارية لكن مفضلة:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
```

إذا لا تستخدم قاعدة خارجية، استخدم SQLite على Volume:

```env
DATABASE_PATH=/data/study_commander.sqlite3
```

## ملاحظة BotFather

الكود يضبط قائمة الأوامر والوصف النصي تلقائيًا، لكن صورة البوت/profile picture تُرفع من BotFather يدويًا:

- `/setuserpic` لتغيير صورة البوت.
- `/setabouttext` لنص قصير.
- `/setdescription` لوصف أطول.

## رفع الملفات إلى GitHub

ارفع محتويات ZIP إلى root المستودع بحيث تظهر:

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

لا ترفع ZIP نفسه إلى GitHub كملف وحيد.
