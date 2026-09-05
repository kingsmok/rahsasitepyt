# -*- coding: utf-8 -*-
"""لایهٔ بنیادین پنل مدیریت (Admin Foundation Layer).

این ماژول **هیچ مسیری تعریف نمی‌کند**. تنها چیزی که اینجا زندگی می‌کند،
پنج primitve مشترک بین ۱۳۰ route پنل است:

۱. ``admin_bp``      — شیء Blueprint (اینجا ساخته می‌شود تا ماژول‌های دامنه
                        بتوانند بدون import چرخه‌ای روی آن route ثبت کنند).
۲. ``admin_required`` — تنها گارد پنل؛ یک‌بار import، بدون import داخل حلقهٔ درخواست.
۳. ``Form``           — پوشش type-safe روی ``request.form``. جانشین ۳۳ کست خام
                        ``int(...)`` که هرکدام می‌توانست با ورودی «abc» صفحه را ۵۰۰ کند.
۴. ``commit``         — واحد کار (Unit of Work): commit یا rollback+لاگ+flash.
                        جانشین ۱۲۰ فراخوانی پراکندهٔ ``db.session.commit()`` که
                        ۳۳ تای آن‌ها داخل ``except Exception`` بی‌صدا بلعیده می‌شد.
۵. ``paginate``       — صفحه‌بندی واقعی با سقف سخت. جانشین ``.all()`` روی جدول کامل.

قاعدهٔ معماری: هیچ route ای حق ندارد مستقیم ``db.session.commit()`` صدا بزند،
ورودی خام فرم را کست کند، یا ``except Exception`` بدون لاگ داشته باشد. هر سه
کار از طریق این ماژول انجام می‌شود تا یک‌جا قابل ممیزی، تست و تغییر باشند.
"""
from __future__ import annotations

import functools
import math
import os
import uuid
from typing import Any, Iterable, Sequence

from flask import (Blueprint, abort, flash, g, redirect, request, url_for)
from werkzeug.datastructures import FileStorage, MultiDict

from models import ActivityLog, db
from permissions import can_access_endpoint, has_permission, menu_for
from validators import log_exc, safe_filename, safe_referrer

__all__ = [
    'admin_bp', 'admin_required', 'require_manager', 'Form', 'commit',
    'paginate', 'go', 'go_referrer', 'audit',
    'save_trusted_image', 'apply_allow_list', 'upsert_setting', 'best_effort',
    'staff_overview_cards', 'staff_menu_links',
    'SECRET_SETTING_KEYS', 'MANAGER_ROLES', 'STAFF_ROLES',
    'COVER_IMAGES', 'UPLOAD_ROOT', 'form', 'slugify',
]

# Blueprint در این ماژول ساخته می‌شود، نه در blueprints/admin_bp.py؛ چون ماژول‌های
# دامنه (admin_catalog و ...) باید آن را import کنند و خودشان از admin_bp.py
# import می‌شوند. ساختن آن اینجا، چرخهٔ import را به‌طور کامل حذف می‌کند.
admin_bp = Blueprint('admin', __name__)

# ------------------------------------------------------------------ نقش‌ها
#: نقش‌هایی که کل پنل را می‌بینند.
MANAGER_ROLES: frozenset[str] = frozenset({'admin', 'super_admin'})
#: نقش‌هایی که فقط endpointهای مجاز خود را می‌بینند.
STAFF_ROLES: frozenset[str] = frozenset({'secretary', 'support', 'operator'})
#: کلیدهای محرمانه هرگز به HTML برنمی‌گردند. خالی‌بودن فیلد در فرم یعنی
#: «مقدار فعلی را نگه دار»، نه «پاک کن» — وگرنه یک ذخیرهٔ بی‌دقت، درگاه پرداخت
#: فعال را از کار می‌اندازد.
SECRET_SETTING_KEYS: frozenset[str] = frozenset({
    'idpay_api_key', 'parsian_login_account', 'melli_password', 'sadad_key',
    'snapp_client_secret', 'digipay_api_key', 'tarb_api_key',
    'sms_kavenegar_key', 'sms_melli_password', 'sms_faraz_token',
    'smtp_pass', 'dk_access_token', 'basalam_webhook_secret',
})

#: ریشهٔ پوشهٔ آپلودها — یک‌بار محاسبه، نه در هر درخواست.
UPLOAD_ROOT: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')


# ------------------------------------------------------------------ گارد
def admin_required(view):
    """گارد مرکزی پنل.

    سه لایه، به همین ترتیب:
      ۱. احراز هویت — کاربر ناشناس به لاگین با ``next`` برمی‌گردد.
      ۲. مجوز endpoint — از همان جدولی خوانده می‌شود که منوی کناری را می‌سازد،
         پس «دیدن لینک» و «توانستن ورود» هرگز از هم واگرا نمی‌شوند.
      ۳. تفکیک نقش — دانشجو/مدرس به صفحهٔ عمومی redirect می‌شود (تا وجود پنل
         را کشف نکند)، ولی کارمندی که صرفاً این بخش را ندارد ۴۰۳ صریح می‌گیرد.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        actor = getattr(g, 'user', None)
        if not actor:
            flash('برای ورود به پنل ابتدا وارد حساب خود شوید.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        if not can_access_endpoint(actor, request.endpoint):
            if actor.role not in MANAGER_ROLES and actor.role not in STAFF_ROLES:
                flash('دسترسی غیرمجاز — این بخش در نقش شما فعال نیست.', 'error')
                return redirect(url_for('site.index'))
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def require_manager(view):
    """برای route هایی که ذاتاً مدیریتی‌اند (تغییر نقش، ورود به حساب دیگران).

    این یک لایهٔ دوم *دفاع در عمق* است: حتی اگر جدول مجوزها اشتباه پیکربندی شود،
    اعطای نقش یا impersonation هرگز از دست یک نقش غیرمدیر خارج نمی‌شود.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, 'user', None) is None or g.user.role not in MANAGER_ROLES:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ فرم type-safe
class Form:
    """پوشش type-safe روی ``MultiDict`` فرم.

    چرا این کلاس وجود دارد؟ در نسخهٔ قبلی، ۳۳ بار ورودی فرم مستقیم کست می‌شد::

        course.price = int(f.get('price') or 0)

    یک کاربر که در فیلد قیمت «۱۲٬۰۰۰» یا «abc» بنویسد، ``ValueError`` می‌گیرد و
    پاسخ **۵۰۰** است — یعنی ورودی نامعتبر کاربر به خطای سرور تبدیل می‌شود.
    این کلاس سه تضمین می‌دهد:

    * **هرگز استثنا نمی‌دهد** — ورودی خراب به ``default`` برمی‌گردد.
    * **همیشه در دامنه است** — ``lo``/``hi`` مقدار را clamp می‌کند، پس درصد سهم
      مدرس هرگز ۴۰۰ یا ‎-۱ نمی‌شود.
    * **بدون request context قابل تست است** — می‌توان ``Form(MultiDict({...}))``
      ساخت و مستقیم unit test نوشت.
    """

    __slots__ = ('_src',)

    def __init__(self, source: MultiDict | None = None) -> None:
        self._src = source if source is not None else request.form

    # -- دسترسی خام -------------------------------------------------------
    def has(self, name: str) -> bool:
        """آیا کلید اصلاً در فرم بود؟ (تفاوت «خالی» و «ارسال‌نشده»)"""
        return name in self._src

    def raw(self, name: str, default: str = '') -> Any:
        return self._src.get(name, default)

    def all(self, name: str) -> list[str]:
        return self._src.getlist(name)

    def file(self, name: str) -> FileStorage | None:
        return request.files.get(name)

    # -- متن ---------------------------------------------------------------
    def text(self, name: str, default: str = '', *, maxlen: int | None = None) -> str:
        value = (self._src.get(name, default) or '').strip()
        if maxlen is not None and len(value) > maxlen:
            value = value[:maxlen]
        return value

    def text_or(self, name: str, fallback: str) -> str:
        """متن strip‌شده؛ اگر خالی بود ``fallback`` (برای «مقدار قبلی را نگه دار»)."""
        return self.text(name) or fallback

    def opt_text(self, name: str, *, maxlen: int | None = None) -> str | None:
        """متن یا ``None`` — برای ستون‌های nullable که خالی‌بودنشان معنا دارد."""
        return self.text(name, maxlen=maxlen) or None

    # -- عدد ---------------------------------------------------------------
    def int(self, name: str, default: int = 0, *,
            lo: int | None = None, hi: int | None = None) -> int:
        """کست امن به int با clamp. هرگز استثنا نمی‌دهد."""
        value = self._src.get(name, None)
        if value is None or str(value).strip() == '':
            result = default
        else:
            try:
                result = int(str(value).strip())
            except (TypeError, ValueError):
                result = default
        if lo is not None:
            result = max(lo, result)
        if hi is not None:
            result = min(hi, result)
        return result

    def opt_int(self, name: str, *, lo: int | None = None, hi: int | None = None) -> int | None:
        """مثل :meth:`int` ولی «خالی» را به ``None`` نگاشت می‌کند نه به صفر.

        این تفاوت حیاتی است: «سهم درآمد مدرس خالی» یعنی *ارث از تنظیمات سایت*،
        در حالی که «صفر» یعنی *مدرس هیچ سهمی ندارد*. نگاشت هر دو به ``0`` یک
        باگ مالی خاموش بود.
        """
        value = self._src.get(name, None)
        if value is None or str(value).strip() == '':
            return None
        try:
            result = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        if lo is not None:
            result = max(lo, result)
        if hi is not None:
            result = min(hi, result)
        return result

    def percent(self, name: str, default: int = 0) -> int:
        """درصد — همیشه در بازهٔ ۰ تا ۱۰۰."""
        return self.int(name, default, lo=0, hi=100)

    # -- بولین -------------------------------------------------------------
    @staticmethod
    def _truthy(value: Any) -> bool:
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'y'}

    def bool(self, name: str) -> bool:
        """checkbox: نبودِ کلید یعنی ``False`` (رفتار استاندارد HTML)."""
        return self._truthy(self._src.get(name, False))

    def bool_str(self, name: str) -> str:
        """بولین را به ``'1'``/``'0'`` نگاشت می‌کند — برای جدول ``Setting``."""
        return '1' if self.bool(name) else '0'

    # -- شناسه‌ها ----------------------------------------------------------
    def ids(self, *names: str) -> list[int]:
        """فهرست شناسه‌های صحیح و یکتا از هر تعداد فیلد (``ids`` یا ``item_ids[]``).

        خروجی همیشه ``list[int]`` معتبر است؛ رشتهٔ خالی، «abc» و منفی دور ریخته
        می‌شوند. این تنها نقطهٔ ورود شناسه‌های bulk است، پس SQL-injection از طریق
        ``IN (...)`` ساختاراً غیرممکن می‌شود.
        """
        source: list[str] = []
        for name in names or ('ids', 'item_ids[]'):
            source.extend(self._src.getlist(name))
        seen: dict[int, None] = {}
        for chunk in source:
            for piece in str(chunk).split(','):
                piece = piece.strip()
                if not piece.isdigit():
                    continue
                seen.setdefault(int(piece), None)
        return list(seen)

    def int_list(self, name: str, *, lo: int | None = None,
                 hi: int | None = None) -> list[int]:
        """فهرست اعداد از یک فیلد چندمقداری، با clamp اختیاری."""
        out: list[int] = []
        for chunk in self._src.getlist(name):
            for piece in str(chunk).split(','):
                piece = piece.strip()
                if not piece.lstrip('-').isdigit():
                    continue
                value = int(piece)
                if lo is not None:
                    value = max(lo, value)
                if hi is not None:
                    value = min(hi, value)
                if value not in out:
                    out.append(value)
        return out


def form() -> Form:
    """``Form`` روی ``request.form`` فعلی — میان‌بر خوانا در route ها."""
    return Form()


# ------------------------------------------------------------------ واحد کار
def commit(*, success: str | None = None, category: str = 'success',
           context: str = 'admin') -> bool:
    """Commit اتمیک با rollback و گزارش قطعی.

    الگوی قبلی این بود::

        try:
            ...
            db.session.commit()
        except Exception:
            _lexc('blueprints/admin_bp.py')   # بلعیده شد، کاربر «موفق» دید

    یعنی خطای پایگاه‌داده به‌صداقت گزارش نمی‌شد و session در وضعیت نیمه‌commit
    می‌ماند. این تابع سه تضمین می‌دهد: rollback همیشه، لاگ همیشه، و مقدار
    بازگشتی که route *مجبور* است بررسی کند.
    """
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log_exc(context)
        flash('ذخیره‌سازی ناموفق بود؛ دوباره تلاش کنید.', 'error')
        return False
    if success:
        flash(success, category)
    return True


def best_effort(fn, context: str) -> Any:
    """اجرای کار جانبی که **هرگز نباید** تراکنش اصلی را بشکند.

    برای اعلان، ایندکس Bing، ارسال ایمیل و SEO. تفاوتش با ``except Exception``
    خام این است که خطا حتماً لاگ می‌شود و نام context دقیق است — پس مشکل در
    لاگ‌ها پیدا شدنی است، نه نامرئی.
    """
    try:
        return fn()
    except Exception:
        log_exc(context)
        return None


# ------------------------------------------------------------------ ناوبری
def go(endpoint: str, **values: Any):
    """redirect به endpoint داخلی. تنها راه مجاز خروج از یک POST."""
    return redirect(url_for(endpoint, **values))


def go_referrer(endpoint: str, **values: Any):
    """redirect به صفحهٔ مبدأ اگر امن باشد، وگرنه به fallback.

    همیشه از ``safe_referrer`` عبور می‌کند — ``request.referrer`` خام، یک بردار
    open-redirect است.
    """
    return redirect(safe_referrer(url_for(endpoint, **values)))


def audit(action: str, detail: str = '', *, user_id: int | None = None) -> None:
    """ثبت لاگ ممیزی با IP. Commit نمی‌کند — بخشی از تراکنش route است.

    هر عملیات برگشت‌ناپذیر پنل (تغییر نقش، ورود به حساب دیگران، ریست رمز،
    ابطال گواهی، بازیابی بکاپ) باید از اینجا عبور کند تا پاسخ «چه‌کسی، کی،
    از کدام IP» همیشه موجود باشد.
    """
    ip = request.headers.get('X-Forwarded-For') or request.remote_addr or ''
    db.session.add(ActivityLog(
        user_id=user_id if user_id is not None else g.user.id,
        action=action, detail=(detail or '')[:255], ip=ip[:60],
    ))


# ------------------------------------------------------------------ صفحه‌بندی
def paginate(stmt, order_by, *, per_page: int = 50,
             max_per_page: int = 200, filters=None) -> tuple[list, int, int, int]:
    """صفحه‌بندی روی یک ``select()`` با سقف سخت.

    ورودی یک statement سبک SQLAlchemy 2.0 است (نه ``Model.query`` میراثی) و
    خروجی ``(items, page, pages, total)``.

    چرا سقف سخت؟ اگر ``per_page`` از کوئری‌استرینگ خوانده شود، بدون سقف مهاجم با
    ``?per_page=999999`` عملاً همان ``.all()`` را که این تابع آمده حذف کند
    دوباره احضار می‌کند. ``max_per_page`` این را ساختاراً می‌بندد.

    صفحهٔ بزرگ‌تر از آخرین صفحه به آخرین صفحه clamp می‌شود (نه ۴۰۴)، تا لینک
    بوکمارک‌شدهٔ کاربر بعد از حذف چند ردیف نشکند.
    """
    from sqlalchemy import func, select

    per_page = max(1, min(int(per_page or 50), max_per_page))
    try:
        page = max(1, request.args.get('page', 1, type=int))
    except (TypeError, ValueError):
        page = 1
    for clause in filters or ():
        if clause is not None:
            stmt = stmt.where(clause)
    total = db.session.execute(
        select(func.count()).select_from(stmt.subquery())).scalar() or 0
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    items = db.session.execute(
        stmt.order_by(order_by).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    return items, page, pages, int(total)


# ------------------------------------------------------------------ آپلود
def save_trusted_image(field_name: str, subdir: str, stem: str,
                       label: str = 'فایل') -> str | None:
    """آپلود تصویر برند/گواهی + بررسی محتوایی در برابر جاسازی کد اجرایی.

    بازگرداندن ``/static/...`` آمادهٔ ذخیره در ``Setting``، یا ``None``.
    اگر محتوا خطرناک باشد، صریحاً flash می‌زند و ``None`` می‌دهد — فایل بی‌صدا
    دور ریخته نمی‌شود، چون کاربر باید بداند لوگویش ذخیره نشد.
    """
    storage = request.files.get(field_name)
    if storage is None or not storage.filename:
        return None
    from validators import ALLOWED_IMAGE_EXT_TRUSTED, file_content_is_safe
    safe = safe_filename(storage.filename or '', ALLOWED_IMAGE_EXT_TRUSTED)
    if safe and not file_content_is_safe(storage.stream,
                                         os.path.splitext(safe)[1].lower()):
        flash(f'{label} حاوی کد اجرایی است و پذیرفته نشد.', 'error')
        safe = None
    if not safe:
        return None
    target_dir = os.path.join(UPLOAD_ROOT, 'img', 'uploads', subdir)
    os.makedirs(target_dir, exist_ok=True)
    name = f'{stem}{os.path.splitext(safe)[1].lower()}'
    storage.save(os.path.join(target_dir, name))
    return f'/static/img/uploads/{subdir}/{name}'


# ------------------------------------------------------------------ تنظیمات
def upsert_setting(key: str, value: str) -> None:
    """درج/به‌روزرسانی یک ردیف ``Setting`` بدون commit."""
    from models import Setting
    row = db.session.get(Setting, key)
    if row is not None:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def apply_allow_list(allow: Iterable[str], f: Form, *,
                     secret_keys: frozenset[str] = SECRET_SETTING_KEYS,
                     transforms: dict[str, Any] | None = None) -> int:
    """ذخیرهٔ فرم تنظیمات از روی یک allow-list صریح.

    سه قاعده، هر سه امنیتی:

    ۱. **allow-list، نه deny-list** — کلیدی که در فرم باشد ولی در ``allow`` نباشد
       *نادیده گرفته می‌شود*. این یعنی افزودن یک فیلد جدید به قالب HTML هرگز
       به‌خودی‌خود راه نوشتن روی یک کلید حساس را باز نمی‌کند.
    ۲. **مقدار خالی روی کلید محرمانه = «نگه دار»** — وگرنه یک فرم نیمه‌پر،
       API key درگاه فعال را پاک می‌کند.
    ۳. **``transforms``** برای اعتبارسنجی/clamp هر کلید، کنار همان allow-list.

    بازگشت: تعداد کلیدهایی که نوشته شدند (برای تله‌متری، نه منطق).
    """
    written = 0
    transforms = transforms or {}
    for key in allow:
        if not f.has(key):
            continue
        value = f.text(key)
        if key in secret_keys and not value:
            continue
        transform = transforms.get(key)
        if callable(transform):
            value = transform(value)
        upsert_setting(key, value)
        written += 1
    return written


def staff_overview_cards(actor) -> list[tuple[str, str, int, str]]:
    """کارت‌های داشبورد کارکنان — دقیقاً همان مجوزهایی که مسیرها را می‌بندند.

    این تابع اینجا است (نه در route) چون اصل «منو و مجوز از یک منبع» باید در
    یک جا قابل اثبات باشد: همان ``has_permission`` که لینک را نشان می‌دهد،
    عدد کارت را هم تولید می‌کند.
    """
    from models import (ContactMessage, LiveSession, Order, PaymentProof,
                        Ticket, User)
    from models import utcnow
    cards: list[tuple[str, str, int, str]] = []
    if has_permission(actor, 'view_users'):
        cards.append(('👥', 'کاربران فعال',
                      User.query.filter_by(is_active=True).count(), 'admin.users'))
    if has_permission(actor, 'view_orders'):
        cards.append(('🧾', 'سفارش‌های در انتظار',
                      Order.query.filter_by(status='pending').count(), 'admin.orders'))
    if has_permission(actor, 'approve_payments'):
        cards.append(('💳', 'فیش‌های در انتظار',
                      PaymentProof.query.filter_by(status='pending').count(), 'admin.proofs'))
    if has_permission(actor, 'reply_tickets'):
        cards.append(('🎫', 'تیکت‌های باز',
                      Ticket.query.filter(Ticket.status.in_(['open', 'answered'])).count(),
                      'admin.tickets'))
    if has_permission(actor, 'view_consultations'):
        cards.append(('🎯', 'مشاوره‌های خوانده‌نشده',
                      ContactMessage.query.filter(
                          ContactMessage.subject.like('%مشاوره%'),
                          ContactMessage.is_read.is_(False)).count(),
                      'admin.consultations'))
    if has_permission(actor, 'view_daily_classes'):
        cards.append(('🎥', 'کلاس‌های پیش رو',
                      LiveSession.query.filter(LiveSession.starts_at >= utcnow()).count(),
                      'admin.live_sessions'))
    return cards


def staff_menu_links(actor) -> list[tuple[str, str]]:
    return [(endpoint, label) for endpoint, label in menu_for(actor)
            if endpoint not in ('sep', 'admin.overview')]


def slugify(text: str) -> str:
    """اسلاگ فارسی‌آگاه — تنها نقطهٔ تولید اسلاگ در پنل.

    قبلاً هر دامنه اسلاگ را جور دیگری می‌ساخت (یکی ``while ... slug += '-2'``،
    یکی ``unique_slug_for``). یک قرارداد، یک تابع.
    """
    from models import make_slug
    return make_slug(text, fallback='')


#: تصاویر پیش‌فرض پوشش دوره/مقاله. قبلاً این لیست در دو تابع جدا (``_course_form``
#: و ``_blog_form``) کپی شده بود؛ یک تغییر، یکی را به‌روز می‌کرد و دیگری را نه.
COVER_IMAGES: tuple[str, ...] = (
    'cover-python.webp', 'cover-flask.webp', 'cover-django.webp',
    'cover-react.webp', 'cover-ml.webp', 'cover-uiux.webp',
    'cover-excel.webp', 'cover-marketing.webp', 'cover-android.webp',
    'cover-wordpress.svg', 'cover-english.svg', 'cover-security.svg',
)
