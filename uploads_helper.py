# -*- coding: utf-8 -*-
"""مدیریت مرکزی آپلودها — پوشه‌های خصوصی در instance/uploads (خارج از static)"""
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.join(_ROOT, 'instance', 'uploads')
# پوشه‌های عمومی که در static می‌مانند (عمدی — تصاویر سایت)
PUBLIC_FOLDERS = ('media', 'opt')

# ⚠️ محافظ پوشهٔ آپلود روی آپاچی/سی‌پنل.
# روی هاست اشتراکی، فایل‌های داخل static/uploads مستقیماً توسط وب‌سرور سرو
# می‌شوند و از کد پایتون عبور نمی‌کنند. اگر فایل php/html/svg آپلود شود، زیر
# دامنهٔ سایت اجرا می‌شود (وب‌شل / صفحهٔ فیشینگ / XSS) و Google Safe Browsing
# کل دامنه را با پیام «Dangerous site» مسدود می‌کند.
_HTACCESS_SRC = os.path.join(_ROOT, 'deploy', 'uploads.htaccess')

# پوشه‌های عمومی‌ای که همیشه باید .htaccess محافظ داشته باشند
_PROTECTED_DIRS = (
    os.path.join(_ROOT, 'static', 'uploads'),
    os.path.join(_ROOT, 'static', 'img', 'uploads'),
)


def ensure_upload_guards():
    """ساخت خودکار .htaccess محافظ در پوشه‌های آپلود عمومی — فقط وقتی وجود ندارد.

    هنگام استارت اپ اجرا می‌شود تا نصب‌های قدیمی (که این فایل را ندارند)
    هم به‌صورت خودکار امن شوند — بدون نیاز به کار دستی مدیر سایت.

    ⚠️ فایل .htaccess موجود هرگز بازنویسی نمی‌شود: تنظیمات دستیِ صاحب سایت
    روی هاست (یا فایل سفارشی که خودش گذاشته) همیشه حفظ می‌شود؛ هم‌چنین
    بروزرسانی نرم‌افزار هیچ‌وقت این فایل را لمس نمی‌کند.
    """
    try:
        if not os.path.exists(_HTACCESS_SRC):
            return
        with open(_HTACCESS_SRC, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return
    for d in _PROTECTED_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
            target = os.path.join(d, '.htaccess')
            # فقط وقتی بنویس که وجود ندارد؛ موجود = متعلق به صاحب سایت.
            if os.path.exists(target):
                continue
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError:
            continue


def uploads_dir(folder):
    """مسیر دایرکتوری یک پوشه آپلود خصوصی"""
    d = os.path.join(_BASE, folder)
    os.makedirs(d, exist_ok=True)
    return d


def uploads_url(folder, filename):
    """URL عمومی برای فایل آپلودی خصوصی — از route محافظت‌شده /uploads سرو می‌شود"""
    return f'/uploads/{folder}/{filename}'


def compress_image_file(fpath, max_side=1600, quality=82):
    """فشرده‌سازی خودکار تصویر آپلودشده (بدون UI بهینه‌ساز).

    JPEG/PNG/WebP را درجا کوچک می‌کند. SVG و GIF متحرک دست نخورده می‌مانند.
    خروجی: (width, height, size) یا None.
    """
    ext = os.path.splitext(fpath or '')[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        return None
    try:
        from PIL import Image, ImageOps
        with Image.open(fpath) as im:
            im = ImageOps.exif_transpose(im)
            if ext in ('.jpg', '.jpeg'):
                if im.mode not in ('RGB', 'L'):
                    im = im.convert('RGB')
            elif ext == '.png':
                if im.mode not in ('RGB', 'L', 'RGBA', 'LA', 'P'):
                    im = im.convert('RGBA')
            elif im.mode not in ('RGB', 'L', 'RGBA'):
                im = im.convert('RGB')
            w, h = im.size
            if max(w, h) > max_side:
                im.thumbnail((max_side, max_side), Image.LANCZOS)
                w, h = im.size
            save_kw = {'optimize': True}
            if ext in ('.jpg', '.jpeg'):
                save_kw.update(quality=quality, progressive=True)
                im.save(fpath, 'JPEG', **save_kw)
            elif ext == '.png':
                im.save(fpath, 'PNG', optimize=True)
            else:
                save_kw.update(quality=quality, method=6)
                im.save(fpath, 'WEBP', **save_kw)
        return w, h, os.path.getsize(fpath)
    except Exception:
        return None
