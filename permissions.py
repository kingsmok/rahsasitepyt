# -*- coding: utf-8 -*-
"""سیستم نقش‌ها و دسترسی‌ها (Permission-Based)"""
import functools
from flask import g, abort, redirect, url_for, flash, request
from models import ROLES


def has_permission(user, perm):
    """آیا کاربر به این دسترسی مجاز است؟"""
    if not user:
        return False
    role = ROLES.get(user.role)
    if not role:
        return False
    perms = role['permissions']
    return '*' in perms or perm in perms


def require_perm(perm):
    """دکوراتور محدودیت دسترسی — مثل require_permission('manage_courses')"""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            if not g.user:
                return redirect(url_for('auth.login', next=request.path))
            if not has_permission(g.user, perm):
                abort(403)
            return fn(*a, **kw)
        return wrap
    return deco


def menu_for(user):
    """منوی پنل مدیریت بر اساس نقش — هر نقش فقط منوی خودش را می‌بیند"""
    if not user:
        return []
    role = user.role
    items = []
    if role in ('super_admin', 'admin'):
        items = [
            ('sep', '📊 مدیریت کلی'),
            ('admin.overview', '📊 داشبورد'),
            ('admin.go_live', '🚀 راه‌اندازی نهایی'),
            ('admin.users', '👥 کاربران'),
            ('admin.roles_manage', '👥 نقش‌ها و دسترسی‌ها'),
            ('admin.activity', '📋 لاگ فعالیت'),
            ('sep', '📚 محتوا و آموزش'),
            ('admin.courses', '📚 دوره‌ها'),
            ('admin.quizzes', '📝 آزمون‌ها'),
            ('admin.question_bank', '🗃 بانک سوال'),
            ('admin.assignments', '📌 تمرین‌ها'),
            ('admin.bundles', '📦 باندل‌ها'),
            ('admin.blog', '📝 وبلاگ'),
            ('admin.categories', '🗂 دسته‌بندی‌ها'),
            ('admin.success_stories', '🌟 داستان موفقیت'),
            ('sep', '🧩 صفحات و طراحی'),
            ('admin.pages', '📄 صفحات'),
            ('builder.index', '🧩 صفحه‌ساز'),
            ('admin.forms', '🛠 فرم‌ساز'),
            ('admin.menus', '🧭 منوساز'),
            ('admin.designs', '🖼 طراحی‌های سایت'),
            ('sep', '💳 فروش و مالی'),
            ('admin.orders', '🧾 سفارش‌ها'),
            ('admin.coupons', '🎟 تخفیف‌ها'),
            ('admin.installments', '💳 اقساط'),
            ('admin.proofs', '💳 فیش‌ها'),
            ('admin.products_admin', '🛍 محصولات فروشگاه'),
            ('market.admin_marketplace', '🏪 مارکت‌پلیس‌ها'),
            ('services.admin_ai_writer_page', '🤖 نویسنده هوشمند'),
            ('admin.payouts', '💰 تسویه مدرس‌ها'),
            ('admin.gateways', '💳 درگاه‌ها'),
            ('admin.super_settings', '⚙️ تنظیمات سوپر'),
            ('sep', '🎫 پشتیبانی و ارتباط'),
            ('admin.tickets', '🎫 تیکت‌ها'),
            ('admin.chat', '💬 چت آنلاین'),
            ('admin.canned_replies', '💬 پاسخ‌های آماده'),
            ('admin.newsletters', '📧 خبرنامه'),
            ('admin.admin_notifications', '🔔 اعلان گروهی'),
            ('admin.consultations', '🎯 لیدهای مشاوره'),
            ('sep', '🎥 کلاس و انجمن'),
            ('admin.live_sessions', '🎥 کلاس آنلاین'),
            ('admin.forum_moderate', '💬 انجمن'),
            ('admin.certificates', '🏅 گواهی‌ها'),
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
            ('admin.sms_settings', '📱 پیامک'),
            ('admin.messengers', '📨 پیام‌رسان‌ها'),
            ('admin.optimizer', '🖼 بهینه‌ساز'),
            ('admin.backup_list', '🗄 بکاپ‌ها'),
            ('admin.icons_browser', '🎨 آیکون‌ها'),
            ('admin.update_page', '🔄 بروزرسانی'),
            ('admin.install_manager', '🛠 مدیریت نصب و اتصالات'),
        ]
    elif role == 'teacher':
        items = [
            ('teacher.dashboard', '📊 داشبورد استاد'),
            ('teacher.my_courses', '📚 دوره‌های من'),
            ('teacher.students', '👥 دانشجویان من'),
            ('teacher.assignments', '📌 تکالیف'),
            ('teacher.questions', '💬 پرسش‌ها'),
            ('teacher.revenue', '💰 درآمد من'),
        ]
    elif role == 'secretary':
        items = [
            ('admin.overview', '📊 داشبورد'),
            ('admin.users', '👥 کاربران'),
            ('admin.menus', '🧭 منوساز'),
            ('admin.payouts', '💰 تسویه مدرس‌ها'),
            ('admin.chat', '💬 چت آنلاین'),
            ('admin.live_sessions', '🎥 کلاس آنلاین'),
            ('admin.forum_moderate', '💬 انجمن'),
            ('admin.certificates', '🏅 گواهی‌ها'),
            ('admin.behavior_report', '📊 رفتار دانشجو'),
            ('admin.consultations', '🎯 مشاوره‌ها'),
            ('admin.orders', '🧾 سفارش‌ها'),
            ('admin.reports_export', '📊 خروجی اکسل'),
            ('admin.report_revenue_courses', '💰 درآمد هر دوره'),
            ('admin.report_popular_pages', '👁 صفحات پربازدید'),
            ('admin.report_inactive_users', '😴 کاربران غیرفعال'),
            ('admin.report_seo_health', '🔍 سلامت سئو'),
            ('admin.tickets_report', '📊 گزارش پشتیبانی'),
            ('admin.installments', '💳 اقساط'),
            ('admin.roles_manage', '👥 نقش‌ها و دسترسی‌ها'),
            ('admin.sms_settings', '📱 پیامک'),
        ]
    elif role == 'support':
        items = [
            ('admin.overview', '📊 داشبورد'),
            ('admin.tickets', '🎫 تیکت‌ها'),
            ('admin.users', '👥 کاربران'),
            ('admin.menus', '🧭 منوساز'),
            ('admin.payouts', '💰 تسویه مدرس‌ها'),
            ('admin.chat', '💬 چت آنلاین'),
            ('admin.live_sessions', '🎥 کلاس آنلاین'),
            ('admin.forum_moderate', '💬 انجمن'),
            ('admin.certificates', '🏅 گواهی‌ها'),
            ('admin.behavior_report', '📊 رفتار دانشجو'),
        ]
    elif role == 'operator':
        items = [
            ('admin.overview', '📊 داشبورد'),
            ('admin.orders', '🧾 سفارش‌ها'),
            ('admin.reports_export', '📊 خروجی اکسل'),
            ('admin.report_revenue_courses', '💰 درآمد هر دوره'),
            ('admin.report_popular_pages', '👁 صفحات پربازدید'),
            ('admin.report_inactive_users', '😴 کاربران غیرفعال'),
            ('admin.report_seo_health', '🔍 سلامت سئو'),
            ('admin.tickets_report', '📊 گزارش پشتیبانی'),
            ('admin.installments', '💳 اقساط'),
            ('admin.roles_manage', '👥 نقش‌ها و دسترسی‌ها'),
            ('admin.proofs', '💳 فیش‌ها'),
            ('admin.sms_settings', '📱 پیامک'),
        ]
    else:
        return []
    return items
