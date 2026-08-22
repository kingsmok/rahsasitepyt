# -*- coding: utf-8 -*-
"""ثبت بخش‌های عمومی سایت برای صفحه‌ساز (یک کلیک: ساخت / ویرایش / نمایش زنده).

صفحات تراکنشی (سبد، تسویه، داشبورد، آزمون) اینجا نیستند.
"""
import json


def _sec(key, title, slug, url, template='', group='site', ptype='page',
         icon='📄', publish=False, hint=''):
    return dict(key=key, title=title, slug=slug, url=url, template=template,
                group=group, ptype=ptype, icon=icon, publish=publish, hint=hint)


SITE_SECTIONS = {
    'home': _sec(
        'home', 'صفحه اصلی', 'home', '/', 'landing', 'site', 'home', '🏠', True,
        'عناصر صفحه اصلی بعد از ذخیره روی نشانی / دیده می‌شود.'),
    'courses': _sec(
        'courses', 'دوره‌ها', 'courses', '/courses', 'courses_page',
        icon='📚', hint='فهرست دوره‌ها. جستجو و فیلتر همان قالب ثابت را نشان می‌دهد.'),
    'blog': _sec(
        'blog', 'وبلاگ', 'blog', '/blog', 'blog_page',
        icon='📰', hint='فهرست مقالات. فیلتر دسته همان قالب ثابت را نشان می‌دهد.'),
    'products': _sec(
        'products', 'فروشگاه', 'products', '/products', 'products_page',
        icon='🛍', hint='فهرست کالاهای فیزیکی. جستجو و فیلتر همان قالب ثابت را نشان می‌دهد.'),
    'bundles': _sec(
        'bundles', 'بسته‌های آموزشی', 'bundles', '/bundles', 'bundles_page',
        icon='📦'),
    'success-stories': _sec(
        'success-stories', 'داستان‌های موفقیت', 'success-stories',
        '/success-stories', 'stories_page', icon='🌟'),
    'verify-certificate': _sec(
        'verify-certificate', 'استعلام گواهینامه', 'verify-certificate',
        '/verify-certificate', 'verify_page', icon='🛡',
        hint='فرم استعلام. نتیجهٔ ارسال همان صفحه با ویجت استعلام نشان داده می‌شود.'),
    'about': _sec('about', 'درباره ما', 'about', '/about', 'about_page', icon='🏛'),
    'contact': _sec('contact', 'تماس با ما', 'contact', '/contact', 'contact_page', icon='📨'),
    'faq': _sec('faq', 'سوالات متداول', 'faq', '/faq', 'faq_page', icon='❓'),
    'terms': _sec('terms', 'قوانین و مقررات', 'terms', '/terms', 'terms_page', icon='📜'),
    'privacy': _sec('privacy', 'حریم خصوصی', 'privacy', '/privacy', 'privacy_page', icon='🔒'),
    'learning-paths': _sec(
        'learning-paths', 'مسیرهای یادگیری', 'learning-paths', '/learning-paths',
        'paths_page', icon='🗺'),
    'become-teacher': _sec(
        'become-teacher', 'مدرس شو', 'become-teacher', '/become-teacher',
        'teacher_landing', icon='🎓'),
    'consultation': _sec(
        'consultation', 'درخواست مشاوره', 'consultation', '/consultation',
        'consult_page', icon='🎯'),
    'teachers': _sec(
        'teachers', 'اساتید', 'teachers', '/teachers', 'teacher_landing', icon='👨‍🏫'),
    'header': _sec(
        'header', 'هدر سایت', 'site-header', '/', 'header_chrome',
        'chrome', 'header', '☰', True,
        'هدر روی همه صفحات سایت تکرار می‌شود.'),
    'footer': _sec(
        'footer', 'فوتر سایت', 'site-footer', '/', 'footer_chrome',
        'chrome', 'footer', '🦶', True,
        'فوتر روی همه صفحات سایت تکرار می‌شود.'),
    'mobile_menu': _sec(
        'mobile_menu', 'منوی موبایل', 'site-mobile-menu', '/', 'mobile_menu_chrome',
        'chrome', 'mobile_menu', '📱', True,
        'منوی کشویی موبایل روی همه صفحات تکرار می‌شود.'),
    'footer_mobile': _sec(
        'footer_mobile', 'فوتر موبایل', 'site-footer-mobile', '/',
        'footer_mobile_chrome', 'chrome', 'footer_mobile', '📲', True,
        'نوار پایین موبایل روی همه صفحات تکرار می‌شود.'),
    'course': _sec(
        'course', 'قالب صفحه دوره', 'theme-course', '/courses', 'course_template',
        'theme', 'course', '📖', True,
        'این قالب روی صفحهٔ هر دورهٔ منتشرشده اعمال می‌شود.'),
    'teacher': _sec(
        'teacher', 'قالب صفحه مدرس', 'theme-teacher', '/teachers', 'teacher_template',
        'theme', 'teacher', '👨‍🏫', True,
        'این قالب روی صفحهٔ هر مدرس اعمال می‌شود.'),
    'post': _sec(
        'post', 'قالب مقاله', 'theme-post', '/blog', 'post_template',
        'theme', 'post', '📝', True,
        'این قالب روی صفحهٔ هر مقاله اعمال می‌شود.'),
    '404': _sec(
        '404', 'صفحه خطای ۴۰۴', 'theme-404', '/this-page-does-not-exist',
        'error_404', 'theme', '404', '🚫', True,
        'این صفحه وقتی آدرس پیدا نشود نمایش داده می‌شود.'),
}


def site_page_specs():
    return [s for s in SITE_SECTIONS.values()
            if s['group'] == 'site' and s['key'] != 'home']


def chrome_specs():
    return [s for s in SITE_SECTIONS.values() if s['group'] == 'chrome']


def theme_specs():
    return [s for s in SITE_SECTIONS.values() if s['group'] == 'theme']


def section_spec_for_page(page):
    """مشخصات بخش ثبت‌شده برای یک صفحهٔ صفحه‌ساز (یا None)."""
    ptype = getattr(page, 'ptype', '') or ''
    slug = getattr(page, 'slug', '') or ''
    if ptype and ptype != 'page':
        for spec in SITE_SECTIONS.values():
            if spec['ptype'] == ptype:
                return spec
    for spec in SITE_SECTIONS.values():
        if spec['ptype'] == 'page' and spec['slug'] == slug:
            return spec
    return None


def listing_filters_active(*keys, ignore_defaults=None):
    """اگر بازدیدکننده جستجو/فیلتر/صفحهٔ بعد دارد، قالب ثابت باید بماند."""
    from flask import request
    ignore_defaults = ignore_defaults or {}
    for key in keys:
        val = (request.args.get(key) or '').strip()
        if not val:
            continue
        if key in ignore_defaults and val == str(ignore_defaults[key]):
            continue
        return True
    try:
        page = request.args.get('page', 1, type=int) or 1
    except (TypeError, ValueError):
        page = 1
    return page > 1


def find_builder_page(slug, allow_preview=True):
    """صفحهٔ منتشرشدهٔ صفحه‌ساز با همین اسلاگ (یا پیش‌نمایش مدیر)."""
    from flask import g, request
    from models import Page
    page = Page.query.filter_by(slug=slug, ptype='page').first()
    if page is None or not page.rows():
        return None
    is_preview = allow_preview and request.args.get('preview') is not None
    is_admin = bool(getattr(g, 'user', None) and getattr(g.user, 'is_admin', False))
    if page.is_published or (is_preview and is_admin):
        return page
    return None


def render_builder_page(page):
    from flask import g, render_template
    g.page_settings = page.settings()
    g.page_custom_header = page.custom_header
    g.page_custom_footer = page.custom_footer
    return render_template('builder/public.html', page=page)


def _unique_page_slug(base):
    from models import Page
    slug = base or 'page'
    n = 2
    while Page.query.filter_by(slug=slug).first():
        slug = '%s-%s' % (base, n)
        n += 1
    return slug


def _seed_rows(spec):
    tpl = spec.get('template') or ''
    if tpl:
        try:
            from blueprints.builder import PAGE_TEMPLATES
            if tpl in PAGE_TEMPLATES:
                return PAGE_TEMPLATES[tpl]['rows']
        except Exception:
            pass
        extra = EXTRA_PAGE_TEMPLATES.get(tpl)
        if extra:
            return extra['rows']
    title = spec.get('title') or 'صفحه'
    slug = spec.get('slug') or 'page'
    return [{
        'id': 'st_%s' % slug,
        'settings': {'gap': 24, 'py': 60},
        'cols': [[
            {'id': 'st_%s_h' % slug, 'type': 'heading',
             'data': {'text': title, 'tag': 'h1', 'align': 'right'}},
            {'id': 'st_%s_t' % slug, 'type': 'text',
             'data': {'content': 'این صفحه را با صفحه‌ساز ویرایش کنید.',
                      'align': 'right'}},
        ]],
    }]


def ensure_section(key, seed=True, publish=None):
    """صفحهٔ بخش را بساز یا برگردان؛ در صورت خالی بودن قالب آماده بگذار."""
    spec = SITE_SECTIONS.get(key)
    if spec is None:
        return None, False
    if key == 'home':
        from blueprints.builder import ensure_home_page
        return ensure_home_page(seed=seed)

    from models import Page, db

    ptype = spec['ptype']
    if ptype != 'page':
        page = Page.query.filter_by(ptype=ptype).first()
    else:
        page = Page.query.filter_by(slug=spec['slug']).first()

    created = False
    if page is None:
        slug = _unique_page_slug(spec['slug'])
        rows = _seed_rows(spec) if seed else []
        is_pub = spec.get('publish', False) if publish is None else bool(publish)
        page = Page(
            title=spec['title'], slug=slug, ptype=ptype,
            is_published=is_pub,
            content=json.dumps({'settings': {}, 'rows': rows}, ensure_ascii=False))
        db.session.add(page)
        created = True
    else:
        if seed and not page.rows():
            parsed = page.parsed()
            parsed['rows'] = _seed_rows(spec)
            page.content = json.dumps(parsed, ensure_ascii=False)
        if publish is True:
            page.is_published = True

    db.session.commit()
    try:
        from blueprints.builder import _clear_app_cache
        _clear_app_cache()
    except Exception:
        pass
    return page, created


def _w(wid, wtype, data):
    return {'id': wid, 'type': wtype, 'data': data}


def _row(rid, widgets, settings=None, cols=None):
    if cols is None:
        cols = [widgets]
    return {'id': rid, 'settings': settings or {'gap': 24, 'py': 56}, 'cols': cols}


def _header_rows():
    return [
        _row('hdr_top', [
            _w('hdr_tb', 'topbar', {
                'right': [{'text': 'درباره ما', 'url': '/about'},
                          {'text': 'تماس با ما', 'url': '/contact'}],
                'left': [{'text': 'ورود / ثبت‌نام', 'url': '/auth/login', 'cls': 'accent'}],
            }),
        ], {'gap': 0, 'py': 0, 'hide_mobile': True}),
        _row('hdr_main', [], {'gap': 16, 'py': 12, 'widths': 'auto 1fr auto'}, cols=[
            [_w('hdr_logo', 'logo', {'text': 'آکادمی آنلاین', 'icon': '🎓',
                                     'sub': 'یادگیری مهارت‌محور'})],
            [_w('hdr_search', 'search', {'placeholder': 'جستجو در دوره‌ها...',
                                         'show_cat': True})],
            [_w('hdr_icons', 'icon_link', {'icon': '♡', 'label': 'علاقه‌مندی',
                                           'url': '/favorites', 'badge': 'fav'}),
             _w('hdr_cart', 'icon_link', {'icon': '🛒', 'label': 'سبد خرید',
                                          'url': '/cart', 'badge': 'cart'}),
             _w('hdr_user', 'user_menu', {})],
        ]),
        _row('hdr_nav', [], {'gap': 12, 'py': 0, 'widths': 'auto 1fr'}, cols=[
            [_w('hdr_mega', 'category_mega', {'button': 'دسته‌بندی دوره‌ها',
                                              'columns': '4'})],
            [_w('hdr_menu', 'nav_menu', {'align': 'right', 'links': [
                {'text': 'خانه', 'url': '/'},
                {'text': 'دوره‌ها', 'url': '/courses'},
                {'text': 'اساتید', 'url': '/teachers'},
                {'text': 'وبلاگ', 'url': '/blog'},
                {'text': 'درباره ما', 'url': '/about'},
            ]})],
        ]),
        _row('hdr_cats', [
            _w('hdr_strip', 'category_strip', {'limit': 8}),
        ], {'gap': 0, 'py': 0, 'hide_mobile': True}),
    ]


def _footer_rows():
    from footer_template import FOOTER_ROWS
    return FOOTER_ROWS


def _mobile_menu_rows():
    return [_row('mm1', [
        _w('mm_home', 'mobile_link', {'icon': '🏠', 'label': 'خانه', 'url': '/'}),
        _w('mm_c', 'mobile_link', {'icon': '📚', 'label': 'دوره‌ها', 'url': '/courses'}),
        _w('mm_t', 'mobile_link', {'icon': '👨‍🏫', 'label': 'اساتید', 'url': '/teachers'}),
        _w('mm_b', 'mobile_link', {'icon': '📰', 'label': 'وبلاگ', 'url': '/blog'}),
        _w('mm_a', 'mobile_link', {'icon': 'ℹ️', 'label': 'درباره ما', 'url': '/about'}),
        _w('mm_ct', 'mobile_link', {'icon': '✉️', 'label': 'تماس با ما', 'url': '/contact'}),
    ], {'gap': 0, 'py': 0})]


def _footer_mobile_rows():
    return [_row('fm1', [], {'gap': 0, 'py': 0}, cols=[
        [_w('fm_h', 'mobile_item', {'icon': '🏠', 'label': 'خانه', 'url': '/'})],
        [_w('fm_c', 'mobile_item', {'icon': '📚', 'label': 'دوره‌ها', 'url': '/courses'})],
        [_w('fm_k', 'mobile_item', {'icon': '🛒', 'label': 'سبد', 'url': '/cart'})],
        [_w('fm_u', 'mobile_item', {'icon': '👤', 'label': 'حساب', 'url': '/dashboard'})],
    ])]


EXTRA_PAGE_TEMPLATES = {
    'courses_page': dict(
        name='صفحه دوره‌ها', icon='📚', desc='جستجو + گرید دوره‌ها',
        rows=[_row('crs1', [
            _w('crs_h', 'heading', {'text': 'دوره‌های آموزشی', 'tag': 'h1',
                                    'align': 'right', 'mb': '10'}),
            _w('crs_t', 'text', {
                'content': 'سرفصل، مدرس و قیمت هر دوره را پیش از ثبت‌نام ببینید.',
                'align': 'right', 'size': '15'}),
            _w('crs_s', 'course_search', {
                'placeholder': 'جستجو در دوره‌ها...', 'show_cat': True,
                'button': 'جستجو'}),
            _w('crs_g', 'courses', {
                'title': '', 'limit': '12', 'columns': '3', 'sort': 'newest',
                'show_price': True}),
        ])]),
    'blog_page': dict(
        name='صفحه وبلاگ', icon='📰', desc='گرید مقالات',
        rows=[_row('blg1', [
            _w('blg_h', 'heading', {'text': 'وبلاگ', 'tag': 'h1',
                                    'align': 'right', 'mb': '10'}),
            _w('blg_t', 'text', {
                'content': 'مقاله‌ها و راهنماهای آموزشی آکادمی.',
                'align': 'right', 'size': '15'}),
            _w('blg_g', 'posts', {
                'title': '', 'limit': '6', 'columns': '3',
                'link_text': '', 'link_url': '/blog'}),
        ])]),
    'products_page': dict(
        name='صفحه فروشگاه', icon='🛍', desc='کارت‌های کالای فیزیکی',
        rows=[_row('prd1', [
            _w('prd_h', 'heading', {'text': 'فروشگاه محصولات', 'tag': 'h1',
                                    'align': 'right', 'mb': '10'}),
            _w('prd_t', 'text', {
                'content': 'کالاهای آموزشی موجود در فروشگاه.',
                'align': 'right', 'size': '15'}),
            _w('prd_g', 'shop_products', {
                'title': '', 'limit': '8', 'columns': '4', 'show_price': True,
                'link_text': 'همه محصولات', 'link_url': '/products'}),
        ])]),
    'bundles_page': dict(
        name='صفحه بسته‌ها', icon='📦', desc='بسته‌های چند دوره',
        rows=[_row('bnd1', [
            _w('bnd_h', 'heading', {'text': 'بسته‌های آموزشی', 'tag': 'h1',
                                    'align': 'right', 'mb': '10'}),
            _w('bnd_g', 'bundles', {
                'title': '', 'limit': '6', 'columns': '3', 'show_price': True}),
        ])]),
    'stories_page': dict(
        name='صفحه داستان موفقیت', icon='🌟', desc='داستان‌های دانشجویان',
        rows=[_row('sty1', [
            _w('sty_h', 'heading', {'text': 'داستان‌های موفقیت', 'tag': 'h1',
                                    'align': 'center', 'mb': '10'}),
            _w('sty_g', 'success_stories', {'title': '', 'limit': '6'}),
        ])]),
    'verify_page': dict(
        name='صفحه استعلام گواهی', icon='🛡', desc='فرم استعلام کد رهگیری',
        rows=[_row('vrf1', [
            _w('vrf_w', 'cert_verify', {
                'title': 'استعلام گواهینامه',
                'text': 'کد رهگیری درج‌شده روی گواهی را وارد کنید.'}),
        ])]),
    'terms_page': dict(
        name='صفحه قوانین', icon='📜', desc='تیتر و متن قوانین',
        rows=[_row('trm1', [
            _w('trm_h', 'heading', {'text': 'قوانین و مقررات', 'tag': 'h1',
                                    'align': 'right', 'mb': '12'}),
            _w('trm_t', 'text', {
                'content': 'قوانین استفاده از خدمات را اینجا بنویسید. این متن را در صفحه‌ساز ویرایش کنید.',
                'align': 'right', 'size': '15'}),
        ])]),
    'privacy_page': dict(
        name='صفحه حریم خصوصی', icon='🔒', desc='تیتر و متن حریم خصوصی',
        rows=[_row('prv1', [
            _w('prv_h', 'heading', {'text': 'حریم خصوصی', 'tag': 'h1',
                                    'align': 'right', 'mb': '12'}),
            _w('prv_t', 'text', {
                'content': 'خط‌مشی حفظ اطلاعات کاربران را اینجا بنویسید.',
                'align': 'right', 'size': '15'}),
        ])]),
    'paths_page': dict(
        name='صفحه مسیر یادگیری', icon='🗺', desc='تیتر + دوره‌ها',
        rows=[_row('pth1', [
            _w('pth_h', 'heading', {'text': 'مسیرهای یادگیری', 'tag': 'h1',
                                    'align': 'right', 'mb': '10'}),
            _w('pth_t', 'text', {
                'content': 'نقشه راه پیشنهادی دوره‌ها را اینجا بچینید.',
                'align': 'right', 'size': '15'}),
            _w('pth_g', 'courses', {
                'title': 'دوره‌های مسیر', 'limit': '8', 'columns': '4',
                'sort': 'newest', 'show_price': True}),
        ])]),
    'header_chrome': dict(
        name='هدر سایت', icon='☰', desc='نوار بالا + لوگو + منو',
        rows=_header_rows()),
    'footer_chrome': dict(
        name='فوتر سایت', icon='🦶', desc='فوتر کلاسیک آکادمیک',
        rows=_footer_rows()),
    'mobile_menu_chrome': dict(
        name='منوی موبایل', icon='📱', desc='لینک‌های منوی کشویی',
        rows=_mobile_menu_rows()),
    'footer_mobile_chrome': dict(
        name='فوتر موبایل', icon='📲', desc='نوار پایین موبایل',
        rows=_footer_mobile_rows()),
    'course_template': dict(
        name='قالب دوره', icon='📖', desc='دوره فعلی + دوره‌های مرتبط',
        rows=[
            _row('ct1', [
                _w('ct_cur', 'current_course', {
                    'title': True, 'image': True, 'price': True, 'button': True}),
            ]),
            _row('ct2', [
                _w('ct_rel', 'courses', {
                    'title': 'دوره‌های مرتبط', 'limit': '4', 'columns': '4',
                    'sort': 'popular', 'show_price': True}),
            ]),
        ]),
    'teacher_template': dict(
        name='قالب مدرس', icon='👨‍🏫', desc='مدرس فعلی',
        rows=[_row('tt1', [
            _w('tt_cur', 'current_teacher', {
                'name': True, 'avatar': True, 'courses': True}),
        ])]),
    'post_template': dict(
        name='قالب مقاله', icon='📝', desc='عنوان، تصویر، محتوا و دیدگاه',
        rows=[_row('pt1', [
            _w('pt_title', 'post_title', {'tag': 'h1', 'align': 'right',
                                          'fallback': 'عنوان مقاله'}),
            _w('pt_info', 'post_info', {
                'show_date': True, 'show_author': True,
                'show_readtime': True, 'show_views': True}),
            _w('pt_img', 'featured_image', {'radius': '16'}),
            _w('pt_body', 'post_content', {'excerpt': False}),
            _w('pt_cm', 'post_comments', {'show_form': True}),
        ])]),
    'error_404': dict(
        name='صفحه ۴۰۴', icon='🚫', desc='پیام صفحه پیدا نشد',
        rows=[_row('e404', [
            _w('e404_h', 'heading', {'text': 'صفحه پیدا نشد', 'tag': 'h1',
                                     'align': 'center', 'mb': '12'}),
            _w('e404_t', 'text', {
                'content': 'آدرس واردشده اشتباه است یا حذف شده است.',
                'align': 'center', 'size': '16'}),
            _w('e404_b', 'button', {
                'text': 'بازگشت به خانه', 'url': '/', 'btn_style': 'primary',
                'size': 'lg', 'align': 'center'}),
        ], {'gap': 0, 'py': 80})]),
}
