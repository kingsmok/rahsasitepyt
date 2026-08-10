# -*- coding: utf-8 -*-
"""پیکربندی pytest — دیتابیس تست جدا + کلاینت تست"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Course, Category


@pytest.fixture()
def app():
    """اپ با دیتابیس موقت — هر تست دیتابیس تمیز می‌گیرد"""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    os.environ['DATABASE_URL'] = f"sqlite:///{tmp.name}"
    app = create_app()
    app.config['TESTING'] = True
    app.config['INSTALL_GUARD'] = False
    with app.app_context():
        db.create_all()
        # داده پایه: دسته + دوره + کاربر دمو
        cat = Category(name='برنامه‌نویسی', slug='programming', sort=1)
        db.session.add(cat)
        db.session.flush()
        teacher = User(name='مدرس تست', email='t@test.ir', phone='09120000999',
                       role='teacher', is_active=True)
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.flush()
        course = Course(title='دوره تست', slug='test-course', price=100000,
                        discount_price=50000, category_id=cat.id,
                        teacher_id=teacher.id, status='published')
        db.session.add(course)
        demo = User(name='کاربر دمو', email='demo@test.ir', phone='09120000888',
                    role='student', is_active=True)
        demo.set_password('demo123')
        db.session.add(demo)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()
    os.unlink(tmp.name)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password):
    """لاگین کمکی — توکن CSRF را از فرم می‌گیرد"""
    import re
    r = client.get('/auth/login')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    assert m, 'فرم لاگین توکن CSRF ندارد'
    return client.post('/auth/login', data={
        '_csrf_token': m.group(1), 'email': email, 'password': password
    }, follow_redirects=False)
