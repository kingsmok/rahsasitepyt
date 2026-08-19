# -*- coding: utf-8 -*-
"""Flask-Admin — مدیریت کامل همه مدل‌ها با امنیت"""
from flask import redirect, url_for, request, session
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from models import (db, User, Category, Course, Section, Lesson, Review, Order,
                    OrderItem, Coupon, Enrollment, BlogPost, BlogComment, Ticket,
                    NewsletterEmail, ContactMessage, SeoMeta, Page)


# ============================================================
# امنیت: فقط ادمین
# ============================================================
class SecureIndexView(AdminIndexView):
    def __init__(self, **kwargs):
        kwargs.setdefault('endpoint', 'fa_index')  # endpoint یکتا (جلوگیری از تداخل با admin)
        super().__init__(**kwargs)

    @expose('/')
    def index(self):
        if not _is_admin():
            return redirect(url_for('auth.login'))
        return super().index()

    def is_accessible(self):
        return _is_admin()


def _is_admin():
    uid = session.get('uid')
    if not uid:
        return False
    u = db.session.get(User, uid)
    return bool(u and u.is_admin)


class SecureModelView(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    page_size = 25
    column_display_pk = False

    def is_accessible(self):
        return _is_admin()

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))


# ============================================================
# ویوهای اختصاصی
# ============================================================
class UserView(SecureModelView):
    column_list = ['id', 'name', 'email', 'phone', 'national_code', 'role', 'is_active', 'created_at']
    column_searchable_list = ['name', 'email', 'phone', 'national_code']
    column_filters = ['role', 'is_active', 'created_at']
    column_sortable_list = ['id', 'name', 'created_at']
    form_excluded_columns = ['password_hash', 'enrollments', 'courses_taught', 'reviews', 'tickets']
    column_labels = dict(id='شناسه', name='نام', email='ایمیل', phone='موبایل',
                         national_code='کد ملی', role='نقش', is_active='فعال',
                         created_at='تاریخ عضویت')

    # ⚠️ امنیت: فرم Flask-Admin شامل فیلد role است؛ اگر مدیر عادی (نه سوپرادمین)
    # به این ویو دسترسی داشت، می‌توانست نقش خود یا دیگری را به super_admin ارتقا
    # دهد (ارتقای سطح دسترسی). مدیریت کاربران از پنل اصلی (/admin/users) با
    # کنترل‌های سخت‌گیرانهٔ نقش انجام می‌شود؛ اینجا فقط سوپرادمین مجاز است.
    def is_accessible(self):
        uid = session.get('uid')
        if not uid:
            return False
        u = db.session.get(User, uid)
        return bool(u and u.role == 'super_admin')


class CourseView(SecureModelView):
    column_list = ['id', 'title', 'category', 'teacher', 'price', 'discount_price',
                   'level', 'status', 'featured', 'views', 'created_at']
    column_searchable_list = ['title', 'subtitle', 'tags']
    column_filters = ['category', 'level', 'status', 'featured', 'price']
    column_sortable_list = ['id', 'title', 'price', 'views', 'created_at']
    form_excluded_columns = ['sections', 'reviews', 'enrollments', 'views']
    column_labels = dict(id='شناسه', title='عنوان', category='دسته', teacher='مدرس',
                         price='قیمت', discount_price='تخفیف', level='سطح',
                         status='وضعیت', featured='ویژه', views='بازدید', created_at='تاریخ')


class OrderView(SecureModelView):
    column_list = ['id', 'code', 'user', 'total', 'discount', 'final_total',
                   'status', 'gateway', 'created_at', 'paid_at']
    column_searchable_list = ['code', 'user.name']
    column_filters = ['status', 'gateway', 'created_at']
    column_sortable_list = ['id', 'final_total', 'created_at']
    can_create = False
    column_labels = dict(id='شناسه', code='کد', user='کاربر', total='جمع',
                         discount='تخفیف', final_total='نهایی', status='وضعیت',
                         gateway='درگاه', created_at='تاریخ', paid_at='پرداخت')


class CouponView(SecureModelView):
    column_list = ['id', 'code', 'type', 'value', 'used_count', 'max_uses', 'min_amount', 'expires_at', 'is_active']
    column_searchable_list = ['code']
    column_filters = ['type', 'is_active', 'expires_at']
    column_sortable_list = ['id', 'used_count', 'expires_at']
    column_labels = dict(id='شناسه', code='کد', type='نوع', value='مقدار',
                         used_count='استفاده', max_uses='سقف', min_amount='حداقل خرید',
                         expires_at='انقضا', is_active='فعال')


class TicketView(SecureModelView):
    column_list = ['id', 'user', 'subject', 'status', 'created_at', 'answered_at']
    column_searchable_list = ['subject', 'body', 'user.name']
    column_filters = ['status', 'created_at']
    column_sortable_list = ['id', 'created_at']
    column_labels = dict(id='شناسه', user='کاربر', subject='موضوع', status='وضعیت',
                         created_at='تاریخ', answered_at='پاسخ')


class BlogPostView(SecureModelView):
    column_list = ['id', 'title', 'category', 'author', 'views', 'published', 'created_at']
    column_searchable_list = ['title', 'excerpt']
    column_filters = ['category', 'published']
    column_sortable_list = ['id', 'views', 'created_at']
    column_labels = dict(id='شناسه', title='عنوان', category='دسته', author='نویسنده',
                         views='بازدید', published='منتشر', created_at='تاریخ')


class LessonView(SecureModelView):
    column_list = ['id', 'title', 'section', 'video_type', 'duration', 'is_free', 'sort']
    column_searchable_list = ['title']
    column_filters = ['video_type', 'is_free']
    column_labels = dict(id='شناسه', title='عنوان', section='سکشن', video_type='نوع ویدیو',
                         duration='مدت', is_free='رایگان', sort='ترتیب')


class PageView(SecureModelView):
    column_list = ['id', 'title', 'slug', 'ptype', 'is_published', 'updated_at']
    column_searchable_list = ['title', 'slug']
    column_filters = ['ptype', 'is_published']
    column_sortable_list = ['id', 'updated_at']
    column_labels = dict(id='شناسه', title='عنوان', slug='اسلاگ', ptype='نوع',
                         is_published='منتشر', updated_at='آخرین ویرایش')


def init_admin(app):
    # ── قالب پایهٔ اختصاصی برای Flask-Admin ──
    # Flask-Admin به‌صورت پیش‌فرض ``master.html`` خود را از ``admin/base.html``
    # extend می‌کند؛ چون ما هم قالب ``templates/admin/base.html`` (پوستهٔ پنل
    # مدیریت خودمان) را داریم، Jinja قالبِ ما را به‌جای قالب Flask-Admin انتخاب
    # می‌کرد و رابط کاربری Flask-Admin به‌طور کامل سایه می‌افتاد (صفحهٔ
    # /admin-extra به‌جای UI مدل‌ها، سایدبار پنل ما را رندر می‌کرد). با theme
    # سفارشی، base_template به مسیر غیرمتداخل ``fa_admin_base.html`` اشاره
    # می‌کند تا هر دو پنل مستقل از هم کار کنند.
    from flask_admin.theme import Bootstrap4Theme
    admin = Admin(app, name='fa_admin', url='/admin-extra',
                  index_view=SecureIndexView(url='/admin-extra/'),
                  theme=Bootstrap4Theme(base_template='fa_admin_base.html'))
    admin.add_view(UserView(User, db, name='کاربران', category='مدیریت'))
    admin.add_view(CourseView(Course, db, name='دوره‌ها', category='مدیریت'))
    admin.add_view(LessonView(Lesson, db, name='جلسات', category='مدیریت'))
    admin.add_view(OrderView(Order, db, name='سفارش‌ها', category='مدیریت'))
    admin.add_view(CouponView(Coupon, db, name='کوپن‌ها', category='مدیریت'))
    admin.add_view(TicketView(Ticket, db, name='تیکت‌ها', category='مدیریت'))
    admin.add_view(BlogPostView(BlogPost, db, name='وبلاگ', category='محتوا'))
    admin.add_view(SecureModelView(Category, db, name='دسته‌بندی‌ها', category='محتوا'))
    admin.add_view(SecureModelView(Section, db, name='سکشن‌ها', category='محتوا'))
    admin.add_view(SecureModelView(Review, db, name='نظرات', category='محتوا'))
    admin.add_view(SecureModelView(BlogComment, db, name='دیدگاه‌ها', category='محتوا'))
    admin.add_view(SecureModelView(NewsletterEmail, db, name='خبرنامه', category='محتوا'))
    admin.add_view(SecureModelView(ContactMessage, db, name='پیام‌ها', category='محتوا'))
    admin.add_view(SecureModelView(Enrollment, db, name='ثبت‌نام‌ها', category='مدیریت'))
    admin.add_view(PageView(Page, db, name='صفحات صفحه‌ساز', category='محتوا'))
    admin.add_view(SecureModelView(SeoMeta, db, name='متاهای سئو', category='سئو'))
    return admin
