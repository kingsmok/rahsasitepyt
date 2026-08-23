# -*- coding: utf-8 -*-
"""دسته ۵: موتور سئو خودکار شبیه RankMath — Course/Article/Person + بازنویسی دستی."""
import json
import re

from models import (BlogPost, Course, SeoMeta, User, db)

from seo_service import (auto_sync, blog_seo, course_seo, ensure_meta,
                         get_meta, teacher_seo)

BASE = 'https://example.ir'


def _teacher(app):
    with app.app_context():
        return User.query.filter_by(email='t@test.ir').first()


def _post(app):
    with app.app_context():
        a = User.query.filter(User.role.in_(('admin', 'super_admin'))).first()
        if a is None:
            a = User(name='نویسنده', email='writer2@test.ir', phone='09120000400',
                     role='admin', is_active=True)
            a.set_password('writer1234')
            db.session.add(a)
            db.session.flush()
        p = BlogPost(title='آموزش پایتون از صفر', slug='seo-python',
                     excerpt='خلاصه آموزش پایتون برای مبتدیان',
                     body='متن کامل آموزش', author_id=a.id, published=True)
        db.session.add(p)
        db.session.commit()
        return p.id


# ═══════════════ تولید خودکار اسکیما ═══════════════

def test_course_seo_generates_full_schema(app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        c.subtitle = 'آموزش کامل'
        c.duration_hours = 12
        db.session.commit()
        seo = course_seo(c, BASE)
        assert 'test-course' in seo['canonical']
        assert seo['title'].startswith(c.title)
        assert seo['description']
        schema = seo['schema']
        assert schema['@type'] == 'Course'
        assert schema['name'] == c.title
        assert schema['offers']['@type'] == 'Offer'
        assert schema['offers']['priceCurrency'] == 'IRR'
        assert schema['provider']['@type'] == 'Organization'
        assert schema['hasCourseInstance']['@type'] == 'CourseInstance'
        assert schema['image'].startswith(BASE)
        assert seo['og_type'] == 'product'


def test_course_seo_coursemode_maps_delivery(app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        c.delivery_type = 'inperson'
        db.session.commit()
        seo = course_seo(c, BASE)
        assert seo['schema']['hasCourseInstance']['courseMode'] == 'Offline'


def test_blog_seo_generates_article_schema(app):
    pid = _post(app)
    with app.app_context():
        post = db.session.get(BlogPost, pid)
        seo = blog_seo(post, BASE)
        schema = seo['schema']
        assert schema['@type'] == 'Article'
        assert schema['headline'] == 'آموزش پایتون از صفر'
        assert schema['author']['@type'] == 'Person'
        assert schema['publisher']['@type'] == 'Organization'
        assert seo['og_type'] == 'article'
        assert seo['canonical'] == BASE + '/blog/seo-python'


def test_teacher_seo_generates_person_schema(app):
    teacher = _teacher(app)
    with app.app_context():
        t = db.session.get(User, teacher.id)
        t.bio = 'مدرس برنامه‌نویسی'
        db.session.commit()
        seo = teacher_seo(t, BASE)
        schema = seo['schema']
        assert schema['@type'] == 'Person'
        assert schema['name'] == t.name
        assert schema['jobTitle'] == 'مدرس'
        assert 'knowsAbout' in schema
        assert schema['worksFor']['@type'] == 'EducationalOrganization'
        assert seo['canonical'] == BASE + '/teacher/' + str(t.id)
        assert seo['og_type'] == 'profile'


# ═══════════════ بازنویسی دستی (Overrides) ═══════════════

def test_apply_overrides_replaces_auto_values(app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        m = SeoMeta(path='/course/' + c.slug, title='عنوان دستی',
                    description='توضیح دستی', noindex=True,
                    schema_json=json.dumps({'@type': 'Course', 'name': 'دستی'},
                                           ensure_ascii=False))
        db.session.add(m)
        db.session.commit()
        seo = course_seo(c, BASE)
        assert seo['title'] == 'عنوان دستی'
        assert seo['description'] == 'توضیح دستی'
        assert seo['noindex'] is True
        assert seo['schema']['name'] == 'دستی'
        db.session.delete(m)
        db.session.commit()


def test_manual_schema_invalid_json_is_ignored(app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        m = SeoMeta(path='/course/' + c.slug, schema_json='not-json{')
        db.session.add(m)
        db.session.commit()
        seo = course_seo(c, BASE)
        assert seo['schema']['@type'] == 'Course'  # اسکیمای خودکار باقی ماند
        db.session.delete(m)
        db.session.commit()


def test_ensure_meta_creates_but_never_overwrites(app):
    with app.app_context():
        ensure_meta('/course/manual-keep')
        m = get_meta('/course/manual-keep')
        assert m is not None
        m.title = 'دستی مدیر'
        db.session.commit()
        ensure_meta('/course/manual-keep')
        assert get_meta('/course/manual-keep').title == 'دستی مدیر'
        db.session.delete(m)
        db.session.commit()


def test_auto_sync_creates_missing_meta_rows(app):
    _post(app)
    with app.app_context():
        SeoMeta.query.delete()
        db.session.commit()
        created, total = auto_sync()
        assert created >= 2
        assert get_meta('/course/test-course') is not None
        assert get_meta('/blog/seo-python') is not None
        assert get_meta('/teacher/' + str(_teacher(app).id)) is not None


# ═══════════════ خروجی واقعی صفحات ═══════════════

def test_course_page_renders_schema_ldjson(client, app):
    r = client.get('/course/test-course')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '"@type": "Course"' in body
    assert 'hasCourseInstance' in body


def test_blog_page_renders_article_schema(client, app):
    _post(app)
    r = client.get('/blog/seo-python')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '"@type": "Article"' in body
    assert 'آموزش پایتون از صفر' in body


def test_teacher_page_renders_person_schema(client, app):
    teacher = _teacher(app)
    r = client.get('/teacher/{}'.format(teacher.id))
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '"@type": "Person"' in body


def test_noindex_override_appears_in_robots_meta(client, app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        m = SeoMeta(path='/course/' + c.slug, noindex=True)
        db.session.add(m)
        db.session.commit()
        r = client.get('/course/test-course')
        assert 'noindex' in r.get_data(as_text=True)
        db.session.delete(m)
        db.session.commit()


# ═══════════════ پنل سئو — ذخیره اسکیمای دستی ═══════════════

def test_seo_edit_saves_manual_schema(client, app):
    with app.app_context():
        a = User(name='Admin SEO', email='seoadmin@test.ir', phone='09120000401',
                 role='super_admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        m = SeoMeta(path='/course/test-course')
        db.session.add(m)
        db.session.commit()
        mid = m.id
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok,
                                     'email': 'seoadmin@test.ir', 'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})
    r = client.get('/admin/seo/edit/{}'.format(mid))
    tok3 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    manual = json.dumps({'@type': 'Course', 'name': 'اسکیمای دستی'}, ensure_ascii=False)
    r = client.post('/admin/seo/edit/{}'.format(mid), data={
        '_csrf_token': tok3, 'title': 'عنوان ذخیره‌شده', 'schema_json': manual,
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        m2 = db.session.get(SeoMeta, mid)
        assert m2.title == 'عنوان ذخیره‌شده'
        assert json.loads(m2.schema_json)['name'] == 'اسکیمای دستی'
        db.session.delete(m2)
        db.session.commit()
