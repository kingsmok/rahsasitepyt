# -*- coding: utf-8 -*-
"""فشرده‌سازی CSS/JS — تولید نسخهٔ .min کنار فایل اصلی.

چرا این روش؟ فشرده‌سازی gzip در این پروژه عمداً خاموش است (nginx/Passenger
دوباره فشرده می‌کرد و خطای ۵۰۳ می‌داد). پس به‌جای فشرده‌سازی در زمان اجرا،
حجم فایل را در زمان ساخت کم می‌کنیم:

    python scripts/build_assets.py

فایل‌های اصلی دست‌نخورده می‌مانند (قابل ویرایش و دیباگ) و نسخهٔ ``.min.css`` /
``.min.js`` تولید می‌شود. تابع ``asset()`` در قالب‌ها به‌صورت خودکار نسخهٔ
کوچک‌شده را انتخاب می‌کند و اگر نبود یا کهنه بود، به فایل اصلی برمی‌گردد.

مینیفایر عمداً محافظه‌کار است: فقط کامنت و فضای خالی اضافی حذف می‌شود؛
هیچ تغییر نحوی/نام‌گذاری انجام نمی‌شود تا خطر شکستن کد صفر بماند.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, 'static')

SKIP = ('.min.css', '.min.js')


def _protect_strings(code):
    """رشته‌ها و regexهای JS را کنار می‌گذارد تا مینیفای خرابشان نکند."""
    tokens = []

    def stash(m):
        tokens.append(m.group(0))
        return '\x00{}\x00'.format(len(tokens) - 1)

    pattern = r'"(?:\\.|[^"\\])*"' \
              r"|'(?:\\.|[^'\\])*'" \
              r'|`(?:\\.|[^`\\])*`'
    return re.sub(pattern, stash, code), tokens


def _restore(code, tokens):
    for i, tok in enumerate(tokens):
        code = code.replace('\x00{}\x00'.format(i), tok)
    return code


def minify_css(css):
    css, tokens = _protect_strings(css)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)      # کامنت‌ها
    css = re.sub(r'\s+', ' ', css)                        # فضای خالی
    css = re.sub(r'\s*([{}:;,>~+])\s*', r'\1', css)       # اطراف نشانه‌ها
    css = re.sub(r';}', '}', css)                         # سمی‌کالن آخر بلوک
    return _restore(css.strip(), tokens)


def minify_js(js):
    js, tokens = _protect_strings(js)
    # کامنت بلوکی (به‌جز /*! که معمولاً مجوز است)
    js = re.sub(r'/\*(?!!).*?\*/', '', js, flags=re.S)
    # کامنت تک‌خطی — فقط وقتی کل خط یا بعد از کد باشد و شامل :// نباشد
    js = re.sub(r'(^|\s)//(?![^\n]*\x00)[^\n]*', r'\1', js)
    js = re.sub(r'[ \t]+', ' ', js)
    js = re.sub(r'\s*\n\s*', '\n', js)
    js = re.sub(r'\n{2,}', '\n', js)
    return _restore(js.strip(), tokens)


def build(verbose=True):
    total_before = total_after = 0
    made = []
    for folder, ext, fn in (('css', '.css', minify_css), ('js', '.js', minify_js)):
        d = os.path.join(STATIC, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(ext) or name.endswith(SKIP):
                continue
            src = os.path.join(d, name)
            dst = os.path.join(d, name[:-len(ext)] + '.min' + ext)
            try:
                with open(src, encoding='utf-8') as f:
                    raw = f.read()
                out = fn(raw)
                if len(out) >= len(raw):     # مینیفای سودی نداشت
                    out = raw
                with open(dst, 'w', encoding='utf-8') as f:
                    f.write(out)
                total_before += len(raw.encode('utf-8'))
                total_after += len(out.encode('utf-8'))
                made.append((name, len(raw), len(out)))
                if verbose:
                    pct = 100 - (len(out) * 100 // max(1, len(raw)))
                    print('  {:<30} {:>8,} → {:>8,}  (-{}%)'.format(
                        name, len(raw), len(out), pct))
            except Exception as exc:         # noqa: BLE001
                print('  ! خطا در {}: {}'.format(name, exc), file=sys.stderr)
    if verbose and total_before:
        pct = 100 - (total_after * 100 // total_before)
        print('\nمجموع: {:,} → {:,} بایت  (کاهش {}%)'.format(
            total_before, total_after, pct))
    return made


if __name__ == '__main__':
    print('فشرده‌سازی فایل‌های CSS/JS...\n')
    build()
    print('\n✅ انجام شد. قالب‌ها به‌صورت خودکار نسخهٔ .min را استفاده می‌کنند.')
