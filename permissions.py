# -*- coding: utf-8 -*-
"""سیستم مرکزی نقش‌ها و دسترسی‌ها.

اصل امنیتی این ماژول «پیش‌فرض ممنوع» است: مسیر مدیریتی‌ای که برای نقش‌های
عملیاتی نگاشت نشده باشد فقط برای admin/super_admin قابل استفاده است. دسترسی‌های
سفارشی ذخیره‌شده در پنل نقش‌ها نیز واقعاً در گاردها و منو اعمال می‌شوند.
"""
import functools
import json

from flask import abort, g, redirect, request, url_for

from models import ROLES


# نگاشت endpointهای پنل به Permission. مقدار tuple یعنی داشتن یکی از مجوزها کافی است.
_ADMIN_ENDPOINT_PERMISSIONS = {}


def _map(permission, *endpoints):
    for endpoint in endpoints:
        _ADMIN_ENDPOINT_PERMISSIONS[endpoint] = permission


_map('dashboard', 'admin.overview')
_map('manage_settings',
     'admin.go_live', 'admin.settings', 'admin.settings_legacy',
     'admin.super_settings', 'admin.themes', 'admin.optimizer',
     'admin.optimizer_bulk', 'admin.backup', 'admin.backup_list',
     'admin.backup_create', 'admin.backup_restore', 'admin.update_page',
     'admin.update_save_repo', 'admin.update_check', 'admin.update_run',
     'admin.update_status', 'admin.update_log', 'admin.install_manager',
     'admin.install_test_xampp', 'admin.install_connect_xampp',
     'admin.install_test_git', 'admin.install_inspect_db',
     'admin.install_attach_db', 'admin.install_use_sqlite',
     'admin.install_migrate_db', 'admin.icons_browser', 'admin.system_restart')
_map('view_users', 'admin.users', 'admin.user_profile')
_map(('edit_users', 'register_students'), 'admin.user_add')
_map('edit_users', 'admin.user_role', 'admin.user_toggle',
     'admin.user_reset_password', 'admin.user_wallet', 'admin.user_login_as')
_map('manage_courses',
     'admin.courses', 'admin.course_new', 'admin.course_edit',
     'admin.course_delete', 'admin.course_lessons', 'admin.categories',
     'admin.quizzes', 'admin.quiz_new', 'admin.quiz_edit', 'admin.quiz_delete',
     'admin.question_bank', 'admin.question_bank_add_to_quiz',
     'admin.assignments', 'admin.assignment_new', 'admin.assignment_delete',
     'admin.submissions', 'admin.submission_grade', 'admin.lesson_questions',
     'admin.lesson_question_answer', 'admin.certificates',
     'admin.certificate_revoke', 'admin.products_admin',
     'admin.product_admin_edit', 'admin.product_admin_delete',
     'admin.course_students_export')
_map(('manage_courses', 'manage_bundles'),
     'admin.bundles', 'admin.bundle_new', 'admin.bundle_edit', 'admin.bundle_delete')
_map('manage_blog',
     'admin.blog', 'admin.blog_new', 'admin.blog_edit', 'admin.reviews',
     'admin.success_stories', 'admin.success_story_delete',
     'admin.success_story_toggle')
_map(('manage_builder', 'manage_pages'),
     'admin.pages', 'admin.page_copy', 'admin.page_toggle', 'admin.page_delete',
     'admin.pages_trash', 'admin.page_restore', 'admin.page_custom_theme',
     'admin.page_schedule', 'admin.page_seo', 'admin.page_revisions',
     'admin.page_revision_restore', 'admin.forms', 'admin.form_new',
     'admin.form_edit', 'admin.form_entries', 'admin.form_entries_export',
     'admin.form_toggle', 'admin.menus', 'admin.menu_new', 'admin.menu_edit',
     'admin.menu_toggle', 'admin.menu_delete', 'admin.designs',
     'admin.design_variant_preview', 'admin.design_variant_json',
     'admin.media_library', 'admin.media_delete',
     'admin.faq_manage', 'admin.pages_content')
_map('view_orders', 'admin.orders', 'admin.order_detail', 'admin.installments')
_map('approve_payments', 'admin.order_fulfillment', 'admin.proofs',
     'admin.proof_verify')
_map('manage_coupons', 'admin.coupons')
_map('manage_gateways', 'admin.gateways', 'admin.gateway_test')
_map('manage_messengers', 'admin.messengers', 'admin.messenger_test',
     'admin.newsletters', 'admin.newsletter_send', 'admin.admin_notifications')
_map(('manage_sms', 'send_sms'), 'admin.sms_settings', 'admin.users_send_sms')
_map('reply_tickets', 'admin.tickets', 'admin.ticket_detail',
     'admin.ticket_reply_file', 'admin.tickets_report')
_map(('reply_tickets', 'use_canned_replies'), 'admin.canned_replies',
     'admin.canned_reply_delete')
_map(('contact_users', 'reply_tickets'), 'admin.chat', 'admin.chat_user',
     'admin.chat_poll', 'admin.chat_send', 'admin.user_notify')
_map(('view_consultations', 'track_leads'), 'admin.consultations', 'admin.messages')
_map('view_daily_classes', 'admin.live_sessions', 'admin.live_session_delete')
_map('reply_tickets', 'admin.forum_moderate', 'admin.forum_topic_delete',
     'admin.forum_topic_pin', 'admin.forum_topic_approve', 'admin.forum_post_approve')
_map(('view_reports', 'view_user_courses'), 'admin.behavior_report')
_map('view_reports',
     'admin.activity', 'admin.reports_index', 'admin.reports_export',
     'admin.report_revenue_courses', 'admin.report_coupons',
     'admin.report_feedback', 'admin.report_teachers', 'admin.report_exams',
     'admin.report_popular_pages', 'admin.report_inactive_users',
     'admin.report_seo_health')
_map('view_all_revenue', 'admin.payouts', 'admin.payout_action')
_map('manage_settings', 'admin.email_test')
_map('manage_roles', 'admin.roles_manage')


# endpointهای بلوپرینت‌های مدیریتی خارج از admin_bp
_PREFIX_PERMISSIONS = {
    'builder.': 'manage_builder',
    'seo_admin.': 'manage_seo',
    'market.': 'manage_settings',
    'license.': 'manage_settings',
    'services.admin_': 'manage_settings',
}


def endpoint_permissions(endpoint):
    """مجوز لازم برای endpoint یا None برای مسیرهای نگاشت‌نشده."""
    endpoint = endpoint or ''
    if endpoint in _ADMIN_ENDPOINT_PERMISSIONS:
        return _ADMIN_ENDPOINT_PERMISSIONS[endpoint]
    for prefix, permission in _PREFIX_PERMISSIONS.items():
        if endpoint.startswith(prefix):
            return permission
    return None


def _effective_permissions(user):
    if not user or user.role not in ROLES:
        return []
    if user.role == 'super_admin':
        return ['*']

    defaults = list(ROLES[user.role].get('permissions') or [])
    # load_globals تنظیمات را پیش از اجرای view بارگذاری می‌کند. fallback دیتابیس
    # برای استفاده در CLI/تست یا کانتکست‌هایی است که g.settings وجود ندارد.
    raw = None
    try:
        raw = (getattr(g, 'settings', {}) or {}).get('role_permissions')
    except RuntimeError:
        pass
    if raw is None:
        try:
            from models import db, Setting
            row = db.session.get(Setting, 'role_permissions')
            raw = row.value if row else None
        except Exception:
            raw = None
    if not raw:
        return defaults
    try:
        custom = json.loads(raw)
        selected = custom.get(user.role)
        if isinstance(selected, list):
            known = set(ROLES['super_admin'].get('permissions') or [])
            # فهرست معتبر واقعی در PERMISSION_FA نگهداری می‌شود.
            from models import PERMISSION_FA
            known.update(PERMISSION_FA)
            return [item for item in selected if item in known or item == '*']
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return defaults


def has_permission(user, permission):
    """آیا کاربر مجوز مشخص را دارد؟"""
    if not user:
        return False
    permissions = _effective_permissions(user)
    return '*' in permissions or permission in permissions


def has_any_permission(user, permissions):
    if not permissions:
        return False
    if isinstance(permissions, str):
        permissions = (permissions,)
    return any(has_permission(user, permission) for permission in permissions)


def can_access_endpoint(user, endpoint):
    """کنترل مرکزی لینک و route؛ endpoint ناشناخته برای کارکنان بسته است."""
    if not user:
        return False
    if user.role == 'super_admin':
        return True
    endpoint = endpoint or ''
    management_roles = {'admin', 'secretary', 'support', 'operator'}
    if (endpoint.startswith(('admin.', 'builder.', 'seo_admin.', 'market.', 'license.')) or
            endpoint.startswith('services.admin_')) and user.role not in management_roles:
        return False
    required = endpoint_permissions(endpoint)
    if required:
        return has_any_permission(user, required)
    # مسیر مدیریتی ناشناخته برای نقش‌های عملیاتی باز نشود. admin برای سازگاری
    # افزونه‌های ثالث و Flask-Admin مجاز می‌ماند.
    return user.role == 'admin'


def require_perm(permission):
    """دکوراتور محدودیت دسترسی — مانند require_perm('manage_courses')."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*args, **kwargs):
            if not getattr(g, 'user', None):
                return redirect(url_for('auth.login', next=request.path))
            if not has_any_permission(g.user, permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrap
    return deco


_ADMIN_MENU = [
    ('sep', '📊 مدیریت کلی'),
    ('admin.overview', '📊 داشبورد'), ('admin.go_live', '🚀 راه‌اندازی نهایی'),
    ('license.activate', '🔐 لایسنس نسخه'), ('admin.users', '👥 کاربران'), ('admin.roles_manage', '👥 نقش‌ها و دسترسی‌ها'),
    ('admin.activity', '📋 لاگ فعالیت'),
    ('sep', '📚 محتوا و آموزش'),
    ('admin.courses', '📚 دوره‌ها'), ('admin.quizzes', '📝 آزمون‌ها'),
    ('admin.question_bank', '🗃 بانک سوال'), ('admin.assignments', '📌 تمرین‌ها'),
    ('admin.bundles', '📦 باندل‌ها'), ('admin.blog', '📝 وبلاگ'),
    ('admin.categories', '🗂 دسته‌بندی‌ها'),
    ('admin.success_stories', '🌟 داستان موفقیت'),
    ('sep', '🧩 صفحات و طراحی'),
    ('admin.pages', '📄 صفحات'), ('admin.pages_content', '📄 درباره و تماس'),
    ('admin.faq_manage', '❓ سوالات متداول'), ('builder.index', '🧩 صفحه‌ساز'),
    ('admin.forms', '🛠 فرم‌ساز'), ('admin.menus', '🧭 منوساز'),
    ('admin.designs', '🖼 طراحی‌های سایت'),
    ('sep', '💳 فروش و مالی'),
    ('admin.orders', '🧾 سفارش‌ها'), ('admin.coupons', '🎟 تخفیف‌ها'),
    ('admin.installments', '💳 اقساط'), ('admin.proofs', '💳 فیش‌ها'),
    ('admin.products_admin', '🛍 محصولات فروشگاه'),
    ('market.admin_marketplace', '🏪 مارکت‌پلیس‌ها'),
    ('services.admin_ai_writer_page', '🤖 نویسنده هوشمند'),
    ('admin.payouts', '💰 تسویه مدرس‌ها'), ('admin.gateways', '💳 درگاه‌ها'),
    ('admin.super_settings', '⚙️ تنظیمات سوپر'),
    ('sep', '🎫 پشتیبانی و ارتباط'),
    ('admin.tickets', '🎫 تیکت‌ها'), ('admin.chat', '💬 چت آنلاین'),
    ('admin.canned_replies', '💬 پاسخ‌های آماده'),
    ('admin.newsletters', '📧 خبرنامه'), ('admin.admin_notifications', '🔔 اعلان گروهی'),
    ('admin.consultations', '🎯 لیدهای مشاوره'),
    ('sep', '🎥 کلاس و انجمن'),
    ('admin.live_sessions', '🎥 کلاس آنلاین'),
    ('admin.forum_moderate', '💬 انجمن'), ('admin.certificates', '🏅 گواهی‌ها'),
    ('admin.behavior_report', '📊 رفتار دانشجو'),
    ('sep', '📈 گزارش‌ها'),
    ('admin.reports_export', '📊 خروجی اکسل'),
    ('admin.report_revenue_courses', '💰 درآمد هر دوره'),
    ('admin.report_popular_pages', '👁 صفحات پربازدید'),
    ('admin.report_inactive_users', '😴 کاربران غیرفعال'),
    ('admin.report_seo_health', '🔍 سلامت سئو'),
    ('admin.tickets_report', '📊 گزارش پشتیبانی'),
    ('admin.report_coupons', '🎟 گزارش تخفیف‌ها'),
    ('admin.report_feedback', '⭐ گزارش رضایت‌سنجی'),
    ('admin.report_teachers', '💰 گزارش درآمد مدرس‌ها'),
    ('admin.report_exams', '🎯 گزارش آزمون‌ها'),
    ('sep', '⚙️ فنی'),
    ('admin.media_library', '📁 کتابخانه رسانه'),
    ('admin.sms_settings', '📱 پیامک'), ('admin.messengers', '📨 پیام‌رسان‌ها'),
    ('admin.backup_list', '🗄 بکاپ‌ها'),
    ('admin.icons_browser', '🎨 آیکون‌ها'), ('admin.update_page', '🔄 بروزرسانی'),
    ('admin.install_manager', '🛠 مدیریت نصب و اتصالات'),
]

_STAFF_MENU = [
    ('admin.overview', '📊 داشبورد'),
    ('admin.users', '👥 کاربران'), ('admin.user_add', '➕ ثبت کاربر'),
    ('admin.consultations', '🎯 مشاوره‌ها'), ('admin.orders', '🧾 سفارش‌ها'),
    ('admin.proofs', '💳 بررسی فیش‌ها'), ('admin.tickets', '🎫 تیکت‌ها'),
    ('admin.canned_replies', '💬 پاسخ‌های آماده'), ('admin.chat', '💬 چت آنلاین'),
    ('admin.live_sessions', '🎥 کلاس‌های روزانه'),
    ('admin.sms_settings', '📱 پیامک'), ('admin.behavior_report', '📊 رفتار دانشجو'),
    ('admin.reports_export', '📈 گزارش‌ها'),
]

_TEACHER_MENU = [
    ('teacher.dashboard', '📊 داشبورد استاد'),
    ('teacher.my_courses', '📚 دوره‌های من'),
    ('teacher.students', '👥 دانشجویان من'),
    ('teacher.assignments', '📌 تکالیف'),
    ('teacher.questions', '💬 پرسش‌ها'),
    ('teacher.revenue', '💰 درآمد من'),
]


def _clean_separators(items):
    cleaned = []
    for item in items:
        if item[0] == 'sep' and (not cleaned or cleaned[-1][0] == 'sep'):
            continue
        cleaned.append(item)
    if cleaned and cleaned[-1][0] == 'sep':
        cleaned.pop()
    return cleaned


def menu_for(user):
    """منوی واقعی هر نقش؛ لینکی که مجوز ندارد اصلاً نمایش داده نمی‌شود."""
    if not user:
        return []
    if user.role == 'teacher':
        return list(_TEACHER_MENU)
    source = _ADMIN_MENU if user.role in ('admin', 'super_admin') else _STAFF_MENU
    items = []
    for endpoint, label in source:
        if endpoint == 'sep' or can_access_endpoint(user, endpoint):
            items.append((endpoint, label))
    return _clean_separators(items)


# ═══════════════════════════════════════════════════════════════════════════
# منوی گروه‌بندی‌شده (دسته ۶: UI/UX) — سایدبار تمیز با دسته‌های جمع‌شونده
# ═══════════════════════════════════════════════════════════════════════════
_ADMIN_GROUPS = [
    {'label': 'داشبورد و وضعیت', 'icon': '🏠', 'items': [
        ('admin.overview', 'داشبورد'),
        ('admin.go_live', 'راه‌اندازی نهایی'),
        ('license.activate', 'لایسنس نسخه'),
        ('admin.activity', 'لاگ فعالیت'),
    ]},
    {'label': 'فروش و مالی', 'icon': '💳', 'items': [
        ('admin.orders', 'سفارش‌ها'),
        ('admin.installments', 'اقساط'),
        ('admin.proofs', 'فیش‌های واریزی'),
        ('admin.payouts', 'تسویه مدرس‌ها'),
        ('admin.gateways', 'درگاه‌های پرداخت'),
        ('admin.products_admin', 'محصولات فروشگاه'),
        ('admin.coupons', 'کدهای تخفیف'),
        ('market.admin_marketplace', 'مارکت‌پلیس‌ها'),
    ]},
    {'label': 'محتوا و آموزش', 'icon': '📚', 'items': [
        ('admin.courses', 'دوره‌ها'),
        ('admin.blog', 'وبلاگ'),
        ('admin.categories', 'دسته‌بندی‌ها'),
        ('admin.quizzes', 'آزمون‌ها'),
        ('admin.question_bank', 'بانک سوال'),
        ('admin.assignments', 'تمرین‌ها'),
        ('admin.bundles', 'باندل‌ها'),
        ('admin.success_stories', 'داستان‌های موفقیت'),
        ('admin.certificates', 'گواهی‌ها'),
    ]},
    {'label': 'دانشجویان و کلاس', 'icon': '🎓', 'items': [
        ('admin.users', 'کاربران'),
        ('admin.roles_manage', 'نقش‌ها و دسترسی‌ها'),
        ('admin.consultations', 'لیدهای مشاوره'),
        ('admin.live_sessions', 'کلاس آنلاین'),
        ('admin.forum_moderate', 'انجمن'),
        ('admin.behavior_report', 'رفتار دانشجو'),
    ]},
    {'label': 'پشتیبانی و ارتباط', 'icon': '🎫', 'items': [
        ('admin.tickets', 'تیکت‌ها'),
        ('admin.chat', 'چت آنلاین'),
        ('admin.canned_replies', 'پاسخ‌های آماده'),
        ('admin.newsletters', 'خبرنامه'),
        ('admin.admin_notifications', 'اعلان گروهی'),
    ]},
    {'label': 'طراحی و صفحات', 'icon': '🧩', 'items': [
        ('admin.pages', 'صفحات'),
        ('admin.faq_manage', 'سوالات متداول'),
        ('admin.pages_content', 'درباره و تماس'),
        ('builder.index', 'صفحه‌ساز'),
        ('admin.forms', 'فرم‌ساز'),
        ('admin.menus', 'منوساز'),
        ('admin.designs', 'طراحی‌های سایت'),
        ('admin.media_library', 'کتابخانه رسانه'),
        ('admin.icons_browser', 'آیکون‌ها'),
    ]},
    {'label': 'سئو و بازاریابی', 'icon': '📈', 'items': [
        ('seo_admin.dashboard', 'داشبورد سئو'),
        ('seo_admin.redirects', 'ریدایرکت‌های ۳۰۱'),
        ('services.admin_ai_writer_page', 'نویسنده هوشمند'),
        ('admin.sms_settings', 'پیامک'),
        ('admin.messengers', 'پیام‌رسان‌ها'),
    ]},
    {'label': 'گزارش‌ها', 'icon': '📊', 'items': [
        ('admin.reports_export', 'خروجی اکسل'),
        ('admin.report_revenue_courses', 'درآمد هر دوره'),
        ('admin.report_teachers', 'درآمد مدرس‌ها'),
        ('admin.report_popular_pages', 'صفحات پربازدید'),
        ('admin.report_inactive_users', 'کاربران غیرفعال'),
        ('admin.report_seo_health', 'سلامت سئو'),
        ('admin.tickets_report', 'گزارش پشتیبانی'),
        ('admin.report_coupons', 'گزارش تخفیف‌ها'),
        ('admin.report_feedback', 'رضایت‌سنجی'),
        ('admin.report_exams', 'گزارش آزمون‌ها'),
    ]},
    {'label': 'سیستم', 'icon': '⚙️', 'items': [
        ('admin.super_settings', 'تنظیمات سوپر'),
        ('admin.backup_list', 'بکاپ‌ها'),
        ('admin.update_page', 'بروزرسانی نرم‌افزار'),
        ('admin.install_manager', 'نصب و اتصالات'),
    ]},
]

_STAFF_GROUPS = [
    {'label': 'عملیات', 'icon': '📋', 'items': [
        ('admin.overview', 'داشبورد'),
        ('admin.users', 'کاربران'),
        ('admin.user_add', 'ثبت کاربر'),
        ('admin.consultations', 'مشاوره‌ها'),
    ]},
    {'label': 'فروش', 'icon': '💳', 'items': [
        ('admin.orders', 'سفارش‌ها'),
        ('admin.proofs', 'بررسی فیش‌ها'),
    ]},
    {'label': 'پشتیبانی', 'icon': '🎫', 'items': [
        ('admin.tickets', 'تیکت‌ها'),
        ('admin.canned_replies', 'پاسخ‌های آماده'),
        ('admin.chat', 'چت آنلاین'),
        ('admin.sms_settings', 'پیامک'),
    ]},
    {'label': 'کلاس و گزارش', 'icon': '📊', 'items': [
        ('admin.live_sessions', 'کلاس‌های روزانه'),
        ('admin.behavior_report', 'رفتار دانشجو'),
        ('admin.reports_export', 'گزارش‌ها'),
    ]},
]

_TEACHER_GROUPS = [
    {'label': 'آموزش', 'icon': '📚', 'items': [
        ('teacher.dashboard', 'داشبورد'),
        ('teacher.my_courses', 'دوره‌های من'),
        ('teacher.students', 'دانشجویان من'),
    ]},
    {'label': 'فعالیت‌ها', 'icon': '✍️', 'items': [
        ('teacher.assignments', 'تکالیف'),
        ('teacher.questions', 'پرسش‌ها'),
    ]},
    {'label': 'مالی', 'icon': '💰', 'items': [
        ('teacher.revenue', 'درآمد من'),
    ]},
]


def menu_groups_for(user):
    """منوی گروه‌بندی‌شده برای سایدبار جدید — فقط آیتم‌های مجاز هر نقش."""
    if not user:
        return []
    if user.role == 'teacher':
        # پنل استاد کنترل دسترسی خودش را دارد (teacher_required)؛ همهٔ گروه‌ها
        # برای او قابل نمایش‌اند — مثل menu_for قبلی.
        return [{'label': g['label'], 'icon': g['icon'],
                 'items': list(g['items'])} for g in _TEACHER_GROUPS]
    if user.role in ('admin', 'super_admin'):
        source = _ADMIN_GROUPS
    else:
        source = _STAFF_GROUPS
    groups = []
    for group in source:
        items = [(ep, label) for ep, label in group['items']
                 if ep == 'sep' or can_access_endpoint(user, ep)]
        if items:
            groups.append({'label': group['label'], 'icon': group['icon'],
                           'items': items})
    return groups
