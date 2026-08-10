# -*- coding: utf-8 -*-
"""بهینه‌سازی تصاویر سایت — تبدیل PNGهای سنگین به WebP فشرده
استفاده: python3 scripts/optimize_images.py
"""
import os
from PIL import Image

BASE = os.path.join(os.path.dirname(__file__), '..', 'static', 'img')

# (نام فایل, عرض هدف, کیفیت)
TARGETS = {
    'hero.png': (1280, 78),          # هیرو تمام‌عرض
    'cover-python.png': (800, 80),
    'cover-flask.png': (800, 80),
    'cover-django.png': (800, 80),
    'cover-react.png': (800, 80),
    'cover-ml.png': (800, 80),
    'cover-uiux.png': (800, 80),
    'cover-excel.png': (800, 80),
    'cover-marketing.png': (800, 80),
    'cover-android.png': (800, 80),
}

total_before = total_after = 0
for src, (width, quality) in TARGETS.items():
    path = os.path.join(BASE, src)
    if not os.path.exists(path):
        print(f'⚠️  {src} وجود ندارد')
        continue
    out = src.replace('.png', '.webp')
    out_path = os.path.join(BASE, out)
    before = os.path.getsize(path)
    im = Image.open(path).convert('RGB')
    if im.width > width:
        h = round(im.height * width / im.width)
        im = im.resize((width, h), Image.LANCZOS)
    im.save(out_path, 'WEBP', quality=quality, method=6)
    after = os.path.getsize(out_path)
    total_before += before
    total_after += after
    print(f'✅ {src} ({im.width}x{im.height})  {before/1024:.0f}KB → {out} {after/1024:.0f}KB  (کاهش {round((1-after/before)*100)}٪)')

print(f'\nمجموع: {total_before/1024/1024:.1f}MB → {total_after/1024/1024:.1f}MB (کاهش {round((1-total_after/total_before)*100)}٪)')
