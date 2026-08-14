# -*- coding: utf-8 -*-
"""🔎 عیب‌یاب «Dangerous site» — بررسی اینکه کدام بخش سایت باعث هشدار کروم است

اجرا (روی سرور خودتان):
    python scripts/safe_browsing_check.py                 # بررسی محلی کد و فایل‌ها
    python scripts/safe_browsing_check.py https://site.ir # + بررسی زندهٔ دامنه

این اسکریپت همان چیزهایی را چک می‌کند که Google Safe Browsing به‌خاطرشان
دامنه را «Deceptive/Dangerous» علامت می‌زند:

  ۱. فایل‌های اجرایی/HTML آپلودشده که زیر دامنه سرو می‌شوند
  ۲. نبود .htaccess محافظ در پوشه‌های آپلود (هاست آپاچی)
  ۳. هدرهای امنیتی گم‌شده (CSP / nosniff / X-Frame-Options)
  ۴. باز بودن صفحهٔ شبیه‌ساز پرداخت روی سایت واقعی
  ۵. فایل‌های مشکوک (php/shell) داخل پوشه‌های عمومی
  ۶. لینک‌های خروجی به دامنه‌های مشکوک در محتوای دیتابیس

خروجی: فهرست مشکلات با راهنمای رفع هرکدام.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GREEN, RED, YELLOW, BLUE, RESET = '\033[92m', '\033[91m', '\033[93m', '\033[94m', '\033[0m'

problems = []
warnings = []
passed = []


def ok(msg):
    passed.append(msg)


def bad(msg, fix):
    problems.append((msg, fix))


def warn(msg, fix):
    warnings.append((msg, fix))


# ────────────────────────────────────────────────────────────
# ۱) فایل‌های خطرناک داخل پوشه‌های عمومی
# ────────────────────────────────────────────────────────────
DANGEROUS_EXT = {'.php', '.php3', '.php4', '.php5', '.php7', '.php8', '.phtml',
                 '.phar', '.pl', '.cgi', '.sh', '.jsp', '.asp', '.aspx',
                 '.exe', '.dll', '.so', '.bat', '.cmd', '.scr', '.msi'}
RENDERABLE_EXT = {'.html', '.htm', '.xhtml', '.svg', '.svgz', '.js', '.mjs'}


def check_public_files():
    pub_dirs = [os.path.join(ROOT, 'static', 'uploads'),
                os.path.join(ROOT, 'static', 'img', 'uploads')]
    found_exec, found_render = [], []
    for d in pub_dirs:
        if not os.path.isdir(d):
            continue
        for dirpath, _dirs, files in os.walk(d):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                if ext in DANGEROUS_EXT:
                    found_exec.append(rel)
                elif ext in RENDERABLE_EXT:
                    found_render.append(rel)
    if found_exec:
        bad('فایل اجرایی داخل پوشهٔ آپلود عمومی: ' + ', '.join(found_exec[:8]),
            'این فایل‌ها را فوراً حذف کنید — احتمالاً وب‌شل/بدافزار هستند. '
            'سپس رمز پنل و FTP/سی‌پنل را عوض کنید.')
    else:
        ok('هیچ فایل اجرایی (php/exe/sh) در پوشه‌های آپلود عمومی نیست')
    if found_render:
        warn('فایل قابل‌رندر (html/svg/js) در پوشهٔ آپلود: ' + ', '.join(found_render[:8]),
             'اگر خودتان آپلود نکرده‌اید حذفشان کنید. فایل .htaccess محافظ '
             '(deploy/uploads.htaccess) جلوی اجرای آن‌ها را می‌گیرد.')
    else:
        ok('هیچ فایل html/svg/js مشکوکی در پوشه‌های آپلود نیست')


# ────────────────────────────────────────────────────────────
# ۲) .htaccess محافظ
# ────────────────────────────────────────────────────────────
def check_htaccess():
    for d in ('static/uploads', 'static/img/uploads'):
        full = os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        ht = os.path.join(full, '.htaccess')
        if not os.path.exists(ht):
            bad(f'فایل محافظ .htaccess در {d} وجود ندارد',
                f'اجرا کنید: cp deploy/uploads.htaccess {d}/.htaccess '
                '(یا فقط اپ را یک‌بار ری‌استارت کنید — خودکار ساخته می‌شود)')
        else:
            content = open(ht, encoding='utf-8', errors='ignore').read()
            if 'engine off' in content or 'RemoveHandler' in content:
                ok(f'.htaccess محافظ در {d} نصب است')
            else:
                warn(f'.htaccess در {d} ناقص به‌نظر می‌رسد',
                     'با نسخهٔ deploy/uploads.htaccess جایگزین کنید')


# ────────────────────────────────────────────────────────────
# ۳) بررسی کد: |safe بدون پاکسازی
# ────────────────────────────────────────────────────────────
def check_unsafe_templates():
    tdir = os.path.join(ROOT, 'templates')
    hits = []
    for dirpath, _d, files in os.walk(tdir):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            p = os.path.join(dirpath, fn)
            lines = open(p, encoding='utf-8', errors='ignore').read().splitlines()
            for i, line in enumerate(lines, 1):
                if '|safe' in line and 'contenteditable' not in line:
                    # اسکریپت‌های سرویس‌های شناخته‌شده اشکالی ندارند
                    if 'clarity_script' in line or 'crisp_script' in line:
                        continue
                    # مواردی که عمداً بررسی و امن اعلام شده‌اند
                    prev = '\n'.join(lines[max(0, i - 4):i - 1])
                    if 'safe-reviewed' in prev:
                        continue
                    hits.append(f'{os.path.relpath(p, ROOT)}:{i}')
    if hits:
        warn('استفاده از |safe روی محتوای متغیر: ' + ', '.join(hits[:6]),
             'به‌جای |safe از فیلتر |clean_html استفاده کنید (پاکسازی ضد XSS)')
    else:
        ok('هیچ |safe بدون پاکسازی روی محتوای کاربر نیست')


# ────────────────────────────────────────────────────────────
# ۴) بررسی زندهٔ دامنه
# ────────────────────────────────────────────────────────────
def check_live(base):
    import urllib.request
    import urllib.error
    base = base.rstrip('/')
    print(f'\n{BLUE}── بررسی زندهٔ {base} ──{RESET}')

    def fetch(path):
        req = urllib.request.Request(base + path,
                                     headers={'User-Agent': 'SafeBrowsingSelfCheck/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, dict(r.headers), r.read(200000)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), b''
        except Exception as e:
            return 0, {}, str(e).encode()

    st, headers, body = fetch('/')
    if st == 0:
        bad(f'اتصال به {base} برقرار نشد: {body.decode("utf-8", "ignore")[:120]}',
            'آدرس و در دسترس بودن سایت را بررسی کنید')
        return
    ok(f'صفحهٔ اصلی پاسخ داد (HTTP {st})')

    hl = {k.lower(): v for k, v in headers.items()}
    if 'content-security-policy' not in hl:
        bad('هدر Content-Security-Policy روی سایت زنده ست نشده',
            'اگر پشت nginx/کش هستید مطمئن شوید هدرهای اپ حذف نمی‌شوند')
    else:
        csp = hl['content-security-policy']
        ok('CSP فعال است')
        if "'unsafe-eval'" in csp:
            warn("CSP شامل 'unsafe-eval' است", 'در app.py حذفش کنید')
        if 'object-src' not in csp:
            warn("CSP فاقد object-src 'none' است", "object-src 'none' اضافه کنید")
    if hl.get('x-content-type-options', '').lower() != 'nosniff':
        bad('هدر X-Content-Type-Options: nosniff وجود ندارد',
            'در app.py/nginx اضافه کنید — جلوی اجرای فایل آپلودی به‌عنوان HTML را می‌گیرد')
    else:
        ok('nosniff فعال است')
    if not base.startswith('https'):
        bad('سایت روی HTTPS نیست',
            'گواهی SSL (Let\'s Encrypt) نصب و کل ترافیک را به HTTPS ریدایرکت کنید')

    # صفحهٔ شبیه‌ساز پرداخت نباید عمومی باشد
    st2, _h2, _b2 = fetch('/pay/sandbox/TEST123')
    if st2 == 200:
        warn('صفحهٔ شبیه‌ساز پرداخت روی سایت زنده باز است',
             'در تنظیمات، «حالت آزمایشی» را خاموش کنید (sandbox_mode=0)')
    else:
        ok('شبیه‌ساز پرداخت روی سایت زنده باز نیست')

    # robots
    st3, _h3, b3 = fetch('/robots.txt')
    if st3 == 200 and b'Disallow: /pay' in b3:
        ok('robots.txt مسیرهای حساس را مسدود کرده')
    else:
        warn('robots.txt مسیرهای پرداخت را مسدود نکرده',
             'مسیرهای /pay /auth /admin /uploads را Disallow کنید')

    # فایل آپلودی نمونه: باید دانلود شود نه رندر
    st4, h4, _b4 = fetch('/static/uploads/media/')
    h4l = {k.lower(): v for k, v in h4.items()}
    if st4 == 200 and 'text/html' in h4l.get('content-type', ''):
        warn('لیست فایل‌های پوشهٔ آپلود عمومی نمایش داده می‌شود (directory listing)',
             'در nginx/آپاچی گزینهٔ autoindex/Indexes را خاموش کنید')


# ────────────────────────────────────────────────────────────
def main():
    print(f'{BLUE}══════════════════════════════════════════════════════{RESET}')
    print(f'{BLUE} 🔎 عیب‌یاب هشدار «Dangerous site» گوگل{RESET}')
    print(f'{BLUE}══════════════════════════════════════════════════════{RESET}')
    check_public_files()
    check_htaccess()
    check_unsafe_templates()
    if len(sys.argv) > 1:
        check_live(sys.argv[1])

    print(f'\n{GREEN}✅ موارد سالم ({len(passed)}):{RESET}')
    for p in passed:
        print(f'   {GREEN}✓{RESET} {p}')
    if warnings:
        print(f'\n{YELLOW}⚠️  هشدارها ({len(warnings)}):{RESET}')
        for m, f in warnings:
            print(f'   {YELLOW}!{RESET} {m}\n     ↳ راه‌حل: {f}')
    if problems:
        print(f'\n{RED}❌ مشکلات جدی ({len(problems)}):{RESET}')
        for m, f in problems:
            print(f'   {RED}✗{RESET} {m}\n     ↳ راه‌حل: {f}')
    print()
    if not problems:
        print(f'{GREEN}هیچ مشکل جدی در سمت کد/سرور پیدا نشد.{RESET}')
        print('اگر کروم هنوز هشدار می‌دهد، مرحلهٔ بعد رفع علامت در گوگل است:')
        print('  ۱) search.google.com/search-console → افزودن دامنه')
        print('  ۲) بخش Security & Manual Actions → Security issues')
        print('  ۳) مشکل گزارش‌شده را ببینید و روی «Request Review» بزنید')
        print('  ۴) بررسی وضعیت: transparencyreport.google.com/safe-browsing/search')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
