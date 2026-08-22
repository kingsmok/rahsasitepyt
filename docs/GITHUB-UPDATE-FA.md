# بروزرسانی امن کد، وابستگی‌ها و دیتابیس از GitHub

## پیش‌نیاز قطعی هاست

این نسخه برای **CPython 3.11** قفل و آزموده شده است. در cPanel، نسخهٔ برنامه را در
`Setup Python App` روی `3.11` بگذارید. نصب دستی و نصب خودکار وابستگی‌ها، نسخهٔ
دیگری را با پیام روشن رد می‌کنند تا محیط نیمه‌نصب‌شده ایجاد نشود.

برای نصب/تعمیر اولیهٔ وابستگی‌ها در virtualenv همان برنامه:

```bash
bash scripts/install_dependencies.sh
# یا با مسیر صریح مفسر:
bash scripts/install_dependencies.sh ./venv/bin/python
```

این اسکریپت فقط wheel باینری نصب می‌کند، ابزارهای pip را ارتقا می‌دهد و در پایان
`pip check` اجرا می‌کند. بنابراین greenlet، Pillow، cryptography و سایر بسته‌های
باینری روی هاست وارد build سورس نمی‌شوند.

## روش‌های اجرا

- **دستی از پنل:** `/admin/update` یا `پنل مدیریت ← مدیریت نصب و اتصالات`؛ ابتدا
  «بررسی نسخه» و سپس «بروزرسانی» را بزنید.
- **Webhook خودکار:** `POST /admin/update/webhook` برای رویداد `push` گیت‌هاب.
- **خط فرمان/cron:** `python updater.py --check` و `python updater.py --run`.

اجرای پنل در Thread پس‌زمینه و اجرای CLI همگام است. قفل بین‌پردازشی اجازه نمی‌دهد
دو worker هم‌زمان بروزرسانی را اجرا کنند.

## تنظیمات پیشنهادی `.env`

```env
GIT_REPO_URL=https://github.com/OWNER/REPOSITORY.git
GIT_BRANCH=main
GITHUB_WEBHOOK_SECRET=یک-رشته-تصادفی-طولانی

UPDATE_INSTALL_DEPENDENCIES=1
UPDATE_TOUCH_RESTART=1
GIT_FETCH_TIMEOUT=300
DB_MIGRATION_TIMEOUT=900
PIP_INSTALL_TIMEOUT=900
PIP_DEFAULT_TIMEOUT=120
PIP_RETRIES=10
# فقط mirror مورد اعتماد شرکت هاست:
# PIP_INDEX_URL=https://mirror.example/simple/
```

نصب‌کنندهٔ وب هنگام نصب یا تعمیر، این متغیرها و سایر متغیرهای سفارشی موجود در
`.env` را حفظ می‌کند. پس از ویرایش `.env`، برنامه را از cPanel restart کنید.

## تنظیم Webhook گیت‌هاب

در `Settings → Webhooks → Add webhook` مخزن:

- Payload URL: `https://DOMAIN.example/admin/update/webhook`
- Content type: `application/json`
- Secret: دقیقاً مقدار `GITHUB_WEBHOOK_SECRET`
- Events: فقط `Push`

Webhook بدون Secret با کد 503 غیرفعال است و امضای نامعتبر با 401 رد می‌شود.
`GIT_BRANCH` در اولویت است. اگر عمداً خالی باشد، فقط
`repository.default_branch` داخل payload رسمی GitHub پذیرفته می‌شود؛ push شاخهٔ
feature، ref نامعتبر و رویداد حذف شاخه هرگز deploy نمی‌شوند.

## ترتیب واقعی بروزرسانی

### نصب از ZIP سی‌پنل (بدون پوشهٔ .git) — روش پیش‌فرض جدید

اگر سایت با ZIP سی‌پنل نصب شده باشد، بروزرسانی **اصلاً به git نیاز ندارد** و
هیچ پوشهٔ .git در پوشهٔ تولید ساخته نمی‌شود:

1. آرشیو ZIP شاخهٔ مقصد از GitHub دانلود می‌شود (codeload + fallback).
2. وجود فایل‌های ضروری (`app.py`، `models.py`، `passenger_wsgi.py`،
   `requirements.txt`) در آرشیو بررسی می‌شود.
3. اگر `requirements.txt` تغییر کرده باشد، وابستگی‌های جدید با همان
   `sys.executable` Passenger نصب و `pip check` می‌شود.
4. از فایل‌هایی که قرار است تغییر کنند snapshot rollback + بکاپ zip پایدار در
   `instance/backups/update-pre-*.zip` گرفته می‌شود.
5. فایل‌های آرشیو با overlay امن روی سایت کپی می‌شوند؛ فایل‌های حذف‌شده در
   نسخهٔ جدید فقط طبق مانیفستِ خودِ بروزرسان (`instance/.update_manifest.json`)
   پاک می‌شوند — هرگز به فایل‌های دستی کاربر کاری ندارند.
6. **هرگز دست نمی‌خورد:** `.env`، `.htaccess` موجود (ریشه و پوشه‌های آپلود)،
   `static/uploads`، `instance/`، بکاپ‌ها، لاگ‌ها و virtualenv. فایل محافظ
   `.htaccess` پوشهٔ آپلود فقط وقتی ساخته می‌شود که سایت آن را نداشته باشد.
7. مایگریشن دیتابیس در یک پردازش جدا اجرا می‌شود (ساختار + مایگریشن‌های
   داده‌ای نسخه‌بندی‌شده در `migrations/`).
8. **تست سلامت:** اپ با کد جدید import و `GET /health` زده می‌شود؛ اگر بالا
   نیاید، کل بروزرسانی به‌صورت خودکار rollback می‌شود و سایت روی کد قبلی
   می‌ماند (با `UPDATE_SMOKE_TEST=0` قابل غیرفعال‌کردن است).
9. commit جدید در `instance/.update_commit` و `version.txt` آرشیو در ریشهٔ سایت
   ذخیره می‌شوند؛ cache پاک و Passenger با لمس فایل WSGI reload می‌شود.

### نصب با مخزن git واقعی (توسعه/CI)

URL مخزن و شاخه اعتبارسنجی و فقط همان شاخه fetch می‌شود؛ سپس همان مراحل
وابستگی، snapshot، reset، مایگریشن و تست سلامت اجرا می‌شوند. اگر fetch شکست
بخورد و مخزن GitHub باشد، به‌صورت خودکار به روش آرشیو fallback می‌شود.

### نسخهٔ محلی در نصب ZIP

نسخهٔ سایت از `version.txt` ریشهٔ پروژه و `instance/.update_commit` خوانده
می‌شود. «بررسی نسخهٔ جدید» در نصب‌های ZIP مقدار `version.txt` محلی را با
شاخهٔ مقصد GitHub مقایسه می‌کند؛ بنابراین خطای «نسخهٔ محلی پیدا نشد» دیگر
وجود ندارد. اگر مقایسه ممکن نباشد، بروزرسانی مسدود نمی‌شود (ایمن‌تر است
همیشه اجازه بدهیم).

### پیام «بروزرسانی متوقف شده است»

این پیام فقط وقتی می‌آید که heartbeat بروزرسانی بیش از
`UPDATE_STALE_SECONDS` (پیش‌فرض ۳۰ دقیقه) قطع مانده باشد **و** فرایندِ
نگه‌دارندهٔ قفل (`instance/.update.lock`) دیگر زنده نباشد. گام‌های طولانی
(دانلود، pip، مایگریشن) heartbeat خودکار دارند؛ اگر فرایند زنده باشد فقط
«مرحلهٔ طولانی» نمایش داده می‌شود و false positive رخ نمی‌دهد.

## rollback در خطا

- خطای دانلود، اعتبارسنجی یا نصب dependency پیش از تعویض کد متوقف می‌شود.
- اگر pip بخشی از بسته‌ها را تغییر داده و سپس شکست بخورد، lock نسخهٔ قبلی دوباره
  نصب و `pip check` می‌شود.
- خطای reset/overlay باعث بازیابی فایل‌های قبلی و وابستگی‌های قبلی می‌شود.
- خطای migration یا تست سلامت باعث بازیابی کد، وابستگی‌ها و—در SQLite—دیتابیس
  قبل از migration می‌شود؛ سپس Passenger روی نسخهٔ بازیابی‌شده reload می‌شود.
- migrationهای MySQL این پروژه افزایشی و بدون حذف جدول/رکورد هستند. برای rollback
  کامل دادهٔ MySQL همچنان بکاپ سرویس هاست یا `mysqldump` پیش از انتشارهای بزرگ
  توصیه می‌شود.

پیام خطا نام مرحلهٔ شکست‌خورده، انتهای خروجی امن ابزار و نتیجهٔ rollback را در
پنل/تاریخچه نشان می‌دهد؛ credential داخل URL مخزن ماسک می‌شود.

## رفتار migration

migration عمومی دادهٔ موجود را حذف نمی‌کند:

- جدول‌های جدید از metadata ساخته می‌شوند؛
- ستون‌های جدید با نوع درست SQLite/MySQL اضافه می‌شوند (تحمل race بین
  workerها و fallback برای محدودیت‌های SQLite)؛
- default مدل برای رکوردهای قدیمی backfill می‌شود؛
- indexهای تعریف‌شده برای جدول‌های قدیمی ساخته می‌شوند؛
- مایگریشن‌های داده‌ای `migrations/NNNN_*.py` به ترتیب و فقط یک بار اجرا
  می‌شوند (ثبت در جدول `schema_migrations`)؛ شکست هرکدام کل بروزرسانی را
  متوقف می‌کند تا دادهٔ سایت سالم بماند.

تغییر پیچیدهٔ معنای داده یا ادغام ستون‌ها باید مایگریشن داده‌ای اختصاصی،
idempotent و قابل بازبینی داشته باشد؛ updater هیچ تبدیل مخربی را حدس نمی‌زند.

## عیب‌یابی سریع

- `فقط برای CPython 3.11`: نسخهٔ Setup Python App و مسیر `sys.executable` را اصلاح کنید.
- `No matching distribution found`: هاست/معماری wheel سازگار ندارد یا از mirror
  ناقص استفاده می‌کند؛ `PIP_INDEX_URL` را حذف یا mirror معتبر انتخاب کنید.
- `ReadTimeout/ConnectTimeout`: دسترسی هاست به PyPI را بررسی کنید؛ timeout و retry
  بالا هستند ولی فایروال مسدودشده را دور نمی‌زنند.
- `pip check`: متن همان بستهٔ ناسازگار در گزارش می‌آید؛ بروزرسانی deploy نمی‌شود.
- عدم reload در Gunicorn: `UPDATE_TOUCH_RESTART` مخصوص Passenger است؛ سرویس
  Gunicorn باید توسط systemd/supervisor جداگانه restart شود.
- `UnicodeEncodeError / charmap / cp1252`: چاپ فارسی مایگریشن روی کنسول ویندوز
  قبلاً بعد از موفقیت مایگریشن کل بروزرسانی را rollback می‌کرد. از نسخهٔ ۱.۵.۱
  خروجی UTF-8 است و شکست چاپ دیگر مایگریشن را خراب نمی‌کند.
- مایگریشن روی phpMyAdmin دیده نمی‌شود: بروزرسان همان `DATABASE_URL` داخل `.env`
  را مایگریت می‌کند. اگر این متغیر خالی باشد سایت روی SQLite
  (`instance/academy.db`) کار می‌کند، نه MySQL هاست. در گزارش مایگریشن موتور
  (`[mysql]` یا `[sqlite]`) نوشته می‌شود.
