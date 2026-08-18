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

1. URL مخزن و نام شاخه اعتبارسنجی و فقط همان شاخه fetch می‌شود. روی git قدیمی
   cPanel، تشخیص default branch از `main`/`master` یا API GitHub fallback دارد.
2. وجود `app.py`، `models.py`، `passenger_wsgi.py` و `requirements.txt` در commit
   مقصد بررسی می‌شود. مخزن ناقص قبل از هر تغییری رد می‌شود.
3. اگر lock وابستگی تغییر کرده باشد، **پیش از جایگزینی کد** با همان
   `sys.executable` مربوط به Passenger این مراحل اجرا می‌شود:
   - ارتقای wheel-only برای `pip`, `setuptools`, `wheel`؛
   - نصب wheel-only فایل requirements مقصد با timeout/retry تنظیم‌شده؛
   - اجرای الزامی `pip check`.
4. پس از موفقیت preflight، کد با commit تأییدشده جایگزین می‌شود. در نصب ZIP،
   اگر git قابل استفاده نباشد آرشیو همان شاخه دریافت می‌شود و پیش از overlay از
   فایل‌های مقصد snapshot rollback گرفته می‌شود.
5. `.env`، `.htaccess`، `instance/`، آپلودها، لاگ‌ها و virtualenv بازنویسی
   نمی‌شوند.
6. پیش از migration، SQLite با API داخلی SQLite و سازگار با WAL بکاپ موقت
   می‌شود؛ اسکریپت migration یک بکاپ پایدار دیگر در `instance/backups/` نگه
   می‌دارد. سپس migration در یک process تازه اجرا می‌شود تا مدل‌های کد جدید
   خوانده شوند.
7. بعد از موفقیت کامل، cache پایتون پاک، نتیجه در
   `instance/update_history.json` ثبت و Passenger با لمس فایل WSGI reload می‌شود.

## rollback در خطا

- خطای دانلود، اعتبارسنجی یا نصب dependency پیش از تعویض کد متوقف می‌شود.
- اگر pip بخشی از بسته‌ها را تغییر داده و سپس شکست بخورد، lock نسخهٔ قبلی دوباره
  نصب و `pip check` می‌شود.
- خطای reset/overlay باعث بازیابی فایل‌های قبلی و وابستگی‌های قبلی می‌شود.
- خطای migration باعث بازیابی کد، وابستگی‌ها و—در SQLite—دیتابیس قبل از
  migration می‌شود؛ سپس Passenger روی نسخهٔ بازیابی‌شده reload می‌شود.
- migrationهای MySQL این پروژه افزایشی و بدون حذف جدول/رکورد هستند. برای rollback
  کامل دادهٔ MySQL همچنان بکاپ سرویس هاست یا `mysqldump` پیش از انتشارهای بزرگ
  توصیه می‌شود.

پیام خطا نام مرحلهٔ شکست‌خورده، انتهای خروجی امن ابزار و نتیجهٔ rollback را در
پنل/تاریخچه نشان می‌دهد؛ credential داخل URL مخزن ماسک می‌شود.

## رفتار migration

migration عمومی دادهٔ موجود را حذف نمی‌کند:

- جدول‌های جدید از metadata ساخته می‌شوند؛
- ستون‌های جدید با نوع درست SQLite/MySQL اضافه می‌شوند؛
- default مدل برای رکوردهای قدیمی backfill می‌شود؛
- indexهای تعریف‌شده برای جدول‌های قدیمی ساخته می‌شوند.

تغییر پیچیدهٔ معنای داده یا ادغام ستون‌ها باید migration اختصاصی، idempotent و
قابل بازبینی داشته باشد؛ updater هیچ تبدیل مخربی را حدس نمی‌زند.

## عیب‌یابی سریع

- `فقط برای CPython 3.11`: نسخهٔ Setup Python App و مسیر `sys.executable` را اصلاح کنید.
- `No matching distribution found`: هاست/معماری wheel سازگار ندارد یا از mirror
  ناقص استفاده می‌کند؛ `PIP_INDEX_URL` را حذف یا mirror معتبر انتخاب کنید.
- `ReadTimeout/ConnectTimeout`: دسترسی هاست به PyPI را بررسی کنید؛ timeout و retry
  بالا هستند ولی فایروال مسدودشده را دور نمی‌زنند.
- `pip check`: متن همان بستهٔ ناسازگار در گزارش می‌آید؛ بروزرسانی deploy نمی‌شود.
- عدم reload در Gunicorn: `UPDATE_TOUCH_RESTART` مخصوص Passenger است؛ سرویس
  Gunicorn باید توسط systemd/supervisor جداگانه restart شود.
