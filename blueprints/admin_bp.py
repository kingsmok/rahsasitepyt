# -*- coding: utf-8 -*-
"""پنل مدیریت — ریشهٔ ترکیب (Composition Root) و سطح تنظیمات.

این فایل دیگر «پنل مدیریت» نیست؛ **نقطهٔ ترکیب** آن است.

چرا؟ نسخهٔ قبلی ۳٬۷۶۸ خط و ۱۳۰ route در یک فایل بود — بزرگ‌ترین فایل پایتون
کل مخزن. در چنین ماژولی هیچ‌کس نمی‌تواند بگوید «دامنهٔ پرداخت کجاست؟»، diff
بازبینی بی‌معنا می‌شود، و هر تغییر کوچک ریسک برخورد merge با هر تغییر دیگری
را دارد. اکنون:

=========================================  ====================================
لایه                                        فایل
=========================================  ====================================
primitve های مشترک (گارد/فرم/commit)          ``admin_core.py``
read model (همهٔ اعداد و فهرست‌ها)            ``admin_queries.py``
دامنهٔ آموزش (دوره/آزمون/تمرین/باندل)        ``admin_catalog.py``
دامنهٔ تجارت (سفارش/پرداخت/کوپن/درگاه)       ``admin_commerce.py``
دامنهٔ افراد (کاربر/نقش/کیف‌پول/چت)          ``admin_people.py``
دامنهٔ محتوا (بلاگ/تیکت/صفحه/فرم/گواهی)      ``admin_content.py``
دامنهٔ عملیات (بکاپ/طراحی/پیام‌رسان)          ``admin_ops.py``
سطح تنظیمات + ریشهٔ ترکیب                     همین فایل
=========================================  ====================================

دو چیز عمداً اینجا مانده‌اند:

۱. **allow-list تنظیمات.** فهرست کلیدهای مجازِ نوشتن، *سیاستِ سطح مدیریت* است
   نه یک primitve؛ پس کنار route هایی زندگی می‌کند که از آن استفاده می‌کنند.
   افزودن یک فیلد به قالب HTML بدون افزودن کلید به این فهرست، هیچ اثری ندارد —
   این همان چیزی است که «تنظیمات بی‌صدا ذخیره نشد» را غیرممکن می‌کند.
۲. **import ماژول‌های دامنه در انتهای فایل.** این کار ثبت route ها را کامل
   می‌کند. پایین بودنش تصادفی نیست: ``admin_bp`` باید *قبل* از import شدن
   ماژول‌های دامنه تعریف شده باشد، وگرنه import چرخه‌ای می‌شود.

سازگاری عقب‌رو: ``admin_bp``، ``admin_required`` و ``_SECRET_SETTING_KEYS`` از
همین ماژول re-export می‌شوند، پس ``blueprints/admin_extra.py`` و ``app.py``
بدون هیچ تغییری کار می‌کنند.
"""
from __future__ import annotations

import os
from typing import Callable

from flask import (current_app, flash, g, redirect, render_template, request,
                   url_for)
from sqlalchemy import inspect as sa_inspect

from admin_core import (SECRET_SETTING_KEYS, STAFF_ROLES, admin_bp, audit,
                        admin_required, apply_allow_list, commit, form, go,
                        save_trusted_image, staff_menu_links,
                        staff_overview_cards, upsert_setting)
from admin_queries import dashboard_metrics
from models import RedirectRule, Setting, db
from validators import safe_int

# --- سازگاری عقب‌رو -------------------------------------------------------
# نام‌های زیر بخشی از قرارداد عمومی این ماژول‌اند؛ import کنندگان قدیمی به آن‌ها
# تکیه دارند. حذف یا تغییر نامشان یک تغییر شکننده (breaking) است.
from admin_core import slugify  # noqa: F401  (re-export عمومی)
from blueprints.admin_catalog import (  # noqa: F401  (re-export عمومی)
    _save_lesson_captions, _save_lesson_file)

__all__ = [
    'admin_bp', 'admin_required', 'slugify', '_save_lesson_file',
    '_save_lesson_captions', '_SECRET_SETTING_KEYS', 'SECRET_SETTING_KEYS',
    'SUPER_SETTINGS_KEYS', 'LEGACY_SETTINGS_KEYS', 'GO_LIVE_KEYS',
]

#: نام قدیمی؛ نام جدید ``admin_core.SECRET_SETTING_KEYS`` است.
_SECRET_SETTING_KEYS = SECRET_SETTING_KEYS


# ==========================================================================
# allow-list تنظیمات — تنها کلیدهایی که پنل اجازهٔ نوشتنشان را دارد
# ==========================================================================
#: تنظیمات «راه‌اندازی و انتشار» — هویت عمومی، درگاه‌ها، پیامک و ایمیل.
GO_LIVE_KEYS: tuple[str, ...] = (
    'site_name', 'site_desc', 'phone', 'email', 'address', 'support_hours',
    'about_text', 'base_url', 'currency', 'refund_days',
    'shipping_flat_rate', 'shipping_note',
    'c2c_card', 'c2c_name', 'zarinpal_merchant', 'idpay_api_key',
    'zibal_merchant', 'parsian_login_account', 'melli_terminal',
    'melli_username', 'melli_password', 'sepah_terminal',
    'sadad_merchant', 'sadad_terminal', 'sadad_key',
    'sms_provider', 'sms_test_phone', 'sms_kavenegar_key',
    'sms_kavenegar_sender', 'sms_kavenegar_template',
    'sms_melli_username', 'sms_melli_password', 'sms_melli_sender',
    'sms_faraz_token', 'sms_faraz_sender',
    'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls',
)

#: فرم قدیمی تنظیمات (مسیر ``/admin/settings-old``) — نگه داشته شده تا لینک‌های
#: بوکمارک‌شده نشکنند؛ فرم اصلی ``super_settings`` است.
LEGACY_SETTINGS_KEYS: tuple[str, ...] = (
    'site_name', 'site_desc', 'phone', 'email', 'address', 'telegram',
    'instagram', 'brand_color', 'brand_color2', 'custom_logo',
    'certificate_text', 'certificate_sign', 'invoice_prefix',
    'base_url', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass',
    'smtp_from', 'smtp_tls',
    'whatsapp', 'bale', 'eitaa', 'rubika', 'soroush', 'shad', 'aparat',
    'twitter', 'linkedin', 'youtube', 'github',
    'support_hours', 'about_text', 'zarinpal_merchant', 'sandbox_mode',
    'kit_container', 'kit_radius', 'watermark_enabled',
    'maintenance', 'allow_register', 'allow_phone_login',
    'site_design', 'home_design', 'about_design', 'contact_design',
)

#: پنل تنظیمات سوپر — شش تب: عمومی/برند · سئو+ریدایرکت · فروش/درگاه ·
#: پیامک/اعلان · مارکت‌پلیس/سرویس · امنیت/نگهداری.
SUPER_SETTINGS_KEYS: tuple[str, ...] = (
    'site_name', 'site_desc', 'phone', 'email', 'address', 'support_hours',
    'about_text', 'contact_intro', 'custom_logo', 'brand_color', 'brand_color2',
    'custom_font_url',
    'telegram', 'instagram', 'whatsapp', 'bale', 'eitaa', 'rubika', 'soroush',
    'shad', 'aparat', 'twitter', 'linkedin', 'youtube', 'github',
    'seo_title', 'seo_desc', 'seo_keywords', 'seo_author', 'seo_og_image',
    'seo_robots_main', 'seo_twitter', 'ga_code',
    'currency', 'sandbox_mode', 'c2c_card', 'c2c_name',
    'zarinpal_merchant', 'idpay_api_key',
    'zibal_merchant', 'parsian_login_account',
    'melli_terminal', 'melli_username', 'melli_password',
    'sepah_terminal',
    'sadad_merchant', 'sadad_terminal', 'sadad_key',
    'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
    'digipay_api_key', 'digipay_merchant', 'tarb_api_url', 'tarb_api_key',
    'tarb_merchant',
    'invoice_prefix', 'certificate_text', 'certificate_sign',
    'certificate_logo', 'certificate_stamp', 'certificate_sign_image',
    'watermark_enabled', 'bnpl_enabled', 'bnpl_max_installments',
    'cashback_percent', 'teacher_default_share',
    'loyalty_discount_percent', 'referral_bonus_percent', 'refund_days',
    'sms_provider', 'sms_test_phone', 'sms_kavenegar_key',
    'sms_kavenegar_sender', 'sms_kavenegar_template', 'sms_melli_username',
    'sms_melli_password', 'sms_melli_sender', 'sms_faraz_token',
    'sms_faraz_sender',
    'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls',
    'dk_api_base', 'dk_access_token', 'basalam_webhook_secret',
    'emalls_seller_id', 'competitive_prices', 'shipping_flat_rate',
    'shipping_note', 'kit_container', 'kit_radius', 'site_design',
    'home_design', 'about_design', 'contact_design', 'home_page_slug',
    'maintenance', 'allow_register', 'allow_phone_login',
    'admin_2fa_enabled', 'exam_enabled', 'spin_enabled',
    'talent_enabled', 'leaderboard_enabled', 'challenge_enabled',
    'compare_enabled', 'placement_enabled', 'study_plan_enabled',
    'success_stories_enabled',
    'blog_comment_moderation',
)


# ---------------------------------------------------------------- اعتبارسنج‌ها
def _clamped(lo: int, hi: int, on_error: int, on_empty: int = 0) -> Callable[[str], str]:
    """سازندهٔ تابع clamp برای یک کلید تنظیمات.

    ``on_empty`` و ``on_error`` عمداً جدا هستند: «کاربر فیلد را خالی گذاشت» با
    «کاربر چیز بی‌معنا نوشت» یکی نیست. نگاشت هر دو به یک مقدار، ورودی خراب را
    بی‌صدا می‌پذیرد.
    """
    def _transform(value: str) -> str:
        try:
            return str(max(lo, min(hi, int(value or on_empty))))
        except (TypeError, ValueError):
            return str(on_error)
    return _transform


def _font_url(value: str) -> str:
    """فونت سفارشی فقط از ``/static/fonts/`` و فقط ``.woff2``.

    این یک allow-list مسیر است، نه فیلتر: بدون آن، ``custom_font_url`` یک بردار
    باز برای بارگذاری فونت از دامنهٔ دلخواه (و در نتیجه tracker) بود.
    """
    if (value.startswith('/static/fonts/') and value.endswith('.woff2')
            and '..' not in value and ' ' not in value and len(value) < 180):
        return value
    return ''


#: clamp هر کلید عددی، کنار همان allow-list — نه پراکنده در بدنهٔ route.
_SUPER_TRANSFORMS: dict[str, Callable[[str], str]] = {
    'sandbox_mode': lambda _v: '0',          # هرگز از پنل روشن نمی‌شود
    'custom_font_url': _font_url,
    'refund_days': _clamped(0, 90, 0),
    'teacher_default_share': _clamped(0, 100, 50),
    'cashback_percent': _clamped(0, 50, 0),
    'loyalty_discount_percent': _clamped(0, 50, 0),
    'referral_bonus_percent': _clamped(0, 50, 0),
    'bnpl_max_installments': _clamped(2, 4, 4, on_empty=4),
    'shipping_flat_rate': _clamped(0, 10 ** 12, 0),
}
_GO_LIVE_TRANSFORMS: dict[str, Callable[[str], str]] = {
    'refund_days': _clamped(0, 90, 0),
    'shipping_flat_rate': _clamped(0, 10 ** 12, 0),
}
_LEGACY_TRANSFORMS: dict[str, Callable[[str], str]] = {
    'sandbox_mode': lambda _v: '0',
}


def _all_settings() -> dict[str, str]:
    return {row.key: row.value for row in Setting.query.all()}


def _clear_cache() -> None:
    """پاک‌سازی کش اپ اگر موجود باشد — نبودنش خطا نیست."""
    clear = getattr(current_app, 'clear_cache', None)
    if callable(clear):
        clear()


# ==========================================================================
# داشبورد
# ==========================================================================
@admin_bp.route('/')
@admin_required
def overview():
    """داشبورد.

    قبلاً این تابع ~۹۰ خط بود و ~۲۹ round-trip به دیتابیس می‌زد، از جمله یک
    حلقهٔ ۷ روزه با ۱۴ کوئری و یک ``Enrollment...all()`` که کل جدول ثبت‌نام‌ها
    را در حافظه materialize می‌کرد. اکنون تمام اعداد از
    :func:`admin_queries.dashboard_metrics` می‌آیند: ۱۱ round-trip ثابت،
    مستقل از حجم داده.

    نقش‌های عملیاتی کارت‌های خود را از همان جدول مجوزها می‌گیرند که مسیرها را
    می‌بندد — پس «دیدن لینک» و «دیدن عدد» هرگز واگرا نمی‌شوند.
    """
    if g.user.role in STAFF_ROLES:
        return render_template('admin/staff_overview.html',
                               cards=staff_overview_cards(g.user),
                               links=staff_menu_links(g.user))
    return render_template('admin/overview.html',
                           **dashboard_metrics().as_template_kwargs())


# ==========================================================================
# راه‌اندازی و انتشار کنترل‌شده
# ==========================================================================
def _launch_readiness(values: dict[str, str]):
    """محاسبهٔ آمادگی انتشار — تابع خالص، بدون side effect.

    بیرون آوردنش از دل route دو سود دارد: قابل unit test شدن، و تضمین اینکه
    شاخهٔ GET و شاخهٔ POST **دقیقاً یک** معیار را می‌سنجند. قبلاً هر دو یک
    closure داخلی مشترک داشتند؛ حالا یک تابع سطح‌ماژول است.
    """
    from gateways import GATEWAYS, gateway_ready
    from licensing import get_license_manager
    from models import Course, Product
    from sms import provider_ready

    published = Course.query.filter_by(status='published').all()
    active_products = Product.query.filter_by(is_active=True).all()
    public_ready = bool(values.get('site_name') and values.get('site_desc')
                        and (values.get('phone') or values.get('email')))
    payment_ready = any(gateway_ready(item['id'], values)
                        for item in GATEWAYS if item.get('kind') != 'test')
    paid_content = any((item.final_price or 0) > 0
                       for item in published + active_products)
    license_state = get_license_manager().status(request.host)
    checks = {
        'public': public_ready,
        # اگر کل محتوای منتشرشده رایگان است، درگاه شرط انتشار نیست.
        'payment': payment_ready or not paid_content,
        'sms': provider_ready(values),
        'smtp': bool(values.get('smtp_host') and values.get('smtp_from')),
        'content': bool(published or active_products),
        # بستهٔ community قفل ندارد؛ بستهٔ تجاری لایسنس معتبر می‌خواهد.
        'license': license_state.valid or not license_state.enforced,
    }
    launch_ready = (checks['public'] and checks['content']
                    and checks['payment'] and checks['license'])
    return (checks, launch_ready, len(published), len(active_products),
            paid_content, license_state)


@admin_bp.route('/go-live', methods=['GET', 'POST'])
@admin_required
def go_live():
    """مرکز راه‌اندازی و انتشار کنترل‌شدهٔ سایت.

    نصب تازه عمداً غیرفعال است. انتشار فقط زمانی انجام می‌شود که هویت عمومی،
    محتوای واقعی و — در صورت وجود کالای پولی — یک درگاه واقعی آماده باشند.
    """
    f = form()

    if request.method == 'POST':
        action = f.text('action', 'save')

        if action in ('activate', 'deactivate'):
            checks, launch_ready, *_rest = _launch_readiness(_all_settings())
            force = f.text('force') == '1'
            is_super = g.user.role == 'super_admin'
            if action == 'activate' and not launch_ready and not (force and is_super):
                missing = [label for key, label in
                           (('public', 'برند و تماس'), ('content', 'محتوا'),
                            ('payment', 'پرداخت'), ('license', 'لایسنس'))
                           if key in checks and not checks[key]]
                flash('انتشار انجام نشد؛ این موارد هنوز کامل نیست: '
                      + ('، '.join(missing) if missing else 'موارد الزامی')
                      + '. (سوپر ادمین می‌تواند با گزینهٔ «فعال‌سازی اجباری» '
                        'انتشار دهد.)', 'error')
                return go('admin.go_live')

            value = '1' if action == 'activate' else '0'
            upsert_setting('site_active', value)
            if not commit(context='admin.go_live'):
                return go('admin.go_live')
            _clear_cache()
            # عبور از گیت readiness یک تصمیم مدیریتی است، پس ممیزی می‌شود.
            if value == '1' and force and not launch_ready:
                audit('force_go_live', 'فعال‌سازی اجباری بدون آمادگی کامل')
                commit(context='admin.go_live')
                flash('سایت به‌صورت اجباری برای عموم فعال شد؛ موارد ناقص را در '
                      'اولین فرصت تکمیل کنید. ⚠️', 'warning')
            else:
                flash('سایت برای عموم فعال شد. ✅' if value == '1' else
                      'سایت از دسترس عموم خارج شد؛ مدیر همچنان پیش‌نمایش کامل '
                      'دارد.', 'success' if value == '1' else 'info')
            return go('admin.go_live')

        apply_allow_list(GO_LIVE_KEYS, f, transforms=_GO_LIVE_TRANSFORMS)
        if not commit(success='اطلاعات راه‌اندازی ذخیره شد. وضعیت بخش‌ها '
                                'دوباره محاسبه شد.', context='admin.go_live'):
            return go('admin.go_live')
        _clear_cache()
        return go('admin.go_live')

    values = _all_settings()
    (checks, launch_ready, courses_count, products_count,
     paid_content, current_license) = _launch_readiness(values)
    return render_template(
        'admin/go_live.html', vals=values, checks=checks,
        score=round(sum(1 for ready in checks.values() if ready) * 100 / len(checks)),
        courses_count=courses_count, products_count=products_count,
        launch_ready=launch_ready, paid_content=paid_content,
        current_license=current_license,
        is_super=g.user.role == 'super_admin',
        site_active=values.get('site_active', '1') == '1')


# ==========================================================================
# تنظیمات
# ==========================================================================
@admin_bp.route('/settings')
@admin_required
def settings_legacy():
    """مسیر قدیمی — به پنل تنظیمات سوپر منتقل شد."""
    return go('admin.super_settings')


@admin_bp.route('/settings-old', methods=['GET', 'POST'])
@admin_required
def settings():
    """فرم قدیمی تنظیمات. فقط برای سازگاری لینک‌های بوکمارک‌شده نگه داشته شده."""
    if request.method == 'POST':
        f = form()
        apply_allow_list(LEGACY_SETTINGS_KEYS, f, transforms=_LEGACY_TRANSFORMS)
        logo = save_trusted_image('custom_logo_file', 'brand', 'logo', label='فایل لوگو')
        if logo:
            upsert_setting('custom_logo', logo)
        if not commit(success='تنظیمات با موفقیت ذخیره شد.',
                      context='admin.settings'):
            return go('admin.settings')
        if f.text('home_design') == 'builder':
            from blueprints.builder import ensure_home_page
            ensure_home_page(seed=True)
        return go('admin.settings')
    return render_template('admin/settings.html')


@admin_bp.route('/super-settings', methods=['GET', 'POST'])
@admin_required
def super_settings():
    """⚙️ پنل تنظیمات سوپر.

    نوشتن تنظیمات از :func:`admin_core.apply_allow_list` عبور می‌کند: هر کلیدی
    که در فرم باشد ولی در ``SUPER_SETTINGS_KEYS`` نباشد، نادیده گرفته می‌شود.
    این allow-list (نه deny-list) است، پس افزودن فیلد به قالب HTML هرگز به‌خودی‌خود
    راه نوشتن روی یک کلید حساس را باز نمی‌کند.
    """
    f = form()

    if request.method == 'POST':
        action = f.text('action', 'save')

        if action == 'save':
            apply_allow_list(SUPER_SETTINGS_KEYS, f, transforms=_SUPER_TRANSFORMS)

            # ۲FA مدیر یک پیش‌شرط بیرونی دارد: شمارهٔ مدیر و یک سرویس پیامک
            # واقعیِ تست‌شده. بدون آن، فعال‌کردنش یعنی قفل‌کردن دائمی پنل.
            if f.text('admin_2fa_enabled') == '1':
                from sms import provider_ready
                if not g.user.phone or not provider_ready(_all_settings()):
                    upsert_setting('admin_2fa_enabled', '0')
                    flash('تایید دومرحله‌ای فعال نشد؛ ابتدا شماره مدیر و سرویس '
                          'پیامک واقعی را تکمیل و تست کنید.', 'error')

            logo = save_trusted_image('custom_logo_file', 'brand', 'logo',
                                      label='فایل لوگو')
            if logo:
                # مسیر کانونی یکسان با فرم قدیمی — دو فرم نباید دو قرارداد
                # مسیر متفاوت برای یک فایل تولید کنند.
                upsert_setting('custom_logo', logo)
            for file_field, setting_key, stem in (
                ('certificate_logo_file', 'certificate_logo', 'cert-logo'),
                ('certificate_stamp_file', 'certificate_stamp', 'cert-stamp'),
                ('certificate_sign_file', 'certificate_sign_image', 'cert-sign'),
            ):
                url = save_trusted_image(file_field, 'brand', stem,
                                         label='فایل گواهینامه')
                if url:
                    upsert_setting(setting_key, url)

            if not commit(success='تنظیمات با موفقیت ذخیره شد ✅',
                          context='admin.super_settings'):
                return go('admin.super_settings', tab=f.text('tab'))
            if f.text('home_design') == 'builder':
                from blueprints.builder import ensure_home_page
                ensure_home_page(seed=True)
            return go('admin.super_settings', tab=f.text('tab'))

        return _redirect_action(action, f)

    from models import NotFoundLog
    vals = _all_settings()
    rules = RedirectRule.query.order_by(RedirectRule.source).all()
    notfound = (NotFoundLog.query.order_by(NotFoundLog.count.desc()).limit(15).all()
                if hasattr(NotFoundLog, 'count')
                else NotFoundLog.query.order_by(NotFoundLog.id.desc()).limit(15).all())
    try:
        inspector = sa_inspect(db.engine)
        db_engine_name = db.engine.dialect.name
        index_count = sum(len(inspector.get_indexes(table))
                          for table in inspector.get_table_names())
    except Exception:  # pragma: no cover - دیتابیس در دسترس نیست
        db_engine_name, index_count = 'نامشخص', 0
    return render_template(
        'admin/super_settings.html', vals=vals, rules=rules, notfound=notfound,
        tab=request.args.get('tab', 'general'),
        redirect_count=RedirectRule.query.count(),
        settings_count=Setting.query.count(),
        db_engine_name=db_engine_name, index_count=index_count)


def _normalize_path(value: str) -> str:
    """مسیر داخلی همیشه با ``/`` شروع می‌شود — ورودی کاربر را یکدست می‌کند."""
    value = (value or '').strip()
    return value if value.startswith('/') else '/' + value


def _redirect_action(action: str, f) -> redirect:
    """مدیریت ریدایرکت‌های سئو — جداسازی‌شده از بدنهٔ route تنظیمات.

    بیرون آوردن این شاخه، ``super_settings`` را از یک تابع ۲۰۰ خطی با هفت
    ``return`` به دو تابع تک‌مسئولیتی تبدیل می‌کند.
    """
    tab = 'seo'
    if action == 'redirect_add':
        source = _normalize_path(f.text('source'))
        target = _normalize_path(f.text('target'))
        code = f.int('code', 301)
        if source == '/' or target == '/':
            flash('مسیر مبدأ و مقصد الزامی است.', 'error')
        elif source == target:
            flash('مبدأ و مقصد نمی‌توانند یکسان باشند (حلقه ریدایرکت).', 'error')
        elif RedirectRule.query.filter_by(source=source).first():
            flash('این مسیر قبلاً ثبت شده است.', 'error')
        else:
            db.session.add(RedirectRule(source=source[:300], target=target[:300],
                                        code=code))
            if commit(context='admin.redirect_add'):
                flash(f'ریدایرکت {source} → {target} اضافه شد ✅', 'success')
        return go('admin.super_settings', tab=tab)

    if action == 'redirect_edit':
        rule = db.session.get(RedirectRule, safe_int(f.text('rid')))
        if rule:
            source = _normalize_path(f.text('source'))
            target = _normalize_path(f.text('target'))
            if source == target:
                flash('حلقه ریدایرکت مجاز نیست.', 'error')
            else:
                rule.source = source[:300]
                rule.target = target[:300]
                rule.code = f.int('code', 301)
                if commit(context='admin.redirect_edit'):
                    flash('ریدایرکت ویرایش شد ✅', 'success')
        return go('admin.super_settings', tab=tab)

    if action == 'redirect_delete':
        rule = db.session.get(RedirectRule, safe_int(f.text('rid')))
        if rule:
            db.session.delete(rule)
            commit(success='ریدایرکت حذف شد.', category='info',
                   context='admin.redirect_delete')
        return go('admin.super_settings', tab=tab)

    if action == 'redirect_toggle':
        rule = db.session.get(RedirectRule, safe_int(f.text('rid')))
        if rule:
            rule.is_active = not rule.is_active
            commit(context='admin.redirect_toggle')
        return go('admin.super_settings', tab=tab)

    if action == 'notfound_to_redirect':
        path = _normalize_path(f.text('path'))
        target = _normalize_path(f.text('target'))
        if (path != '/' and target != '/' and path != target
                and not RedirectRule.query.filter_by(source=path).first()):
            db.session.add(RedirectRule(source=path[:300], target=target[:300],
                                        code=301))
            if commit(context='admin.notfound_redirect'):
                flash(f'ریدایرکت از {path} ساخته شد ✅', 'success')
        return go('admin.super_settings', tab=tab)

    if action == 'notfound_clear':
        from models import NotFoundLog
        db.session.query(NotFoundLog).delete()
        commit(success='لاگ ۴۰۴ پاک شد.', category='info',
               context='admin.notfound_clear')
        return go('admin.super_settings', tab=tab)

    return go('admin.super_settings', tab=f.text('tab'))


# ==========================================================================
# ثبت route های دامنه‌ها — باید پایین‌ترین بخش فایل باشد
# ==========================================================================
# این import ها برای side effect (ثبت route روی ``admin_bp``) انجام می‌شوند.
# پایین بودنشان ضروری است: ``admin_bp`` باید پیش از import این ماژول‌ها تعریف
# شده باشد. ``noqa`` روی هر خط، اعلام صریح است که این یک import بی‌استفاده نیست.
from blueprints import (  # noqa: E402,F401  isort:skip
    admin_catalog, admin_commerce, admin_content, admin_ops, admin_pages,
    admin_people, admin_support,
)
