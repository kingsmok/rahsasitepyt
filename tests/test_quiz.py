# -*- coding: utf-8 -*-
"""تست آزمون‌ها (کوئیز) — ثبت‌نام، شرکت در آزمون، ثبت پاسخ و نتیجه."""
import json
import re
from conftest import login
from models import db, User, Quiz, QuizQuestion, QuizAttempt, Enrollment


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    assert m, f'CSRF not found on {path}'
    return m.group(1)


def _make_quiz(app, n=3):
    """ساخت یک آزمون واقعی با n سوال برای دورهٔ تست (course 1)."""
    with app.app_context():
        q = Quiz(course_id=1, title='آزمون تستی', passing_score=50, description='توضیح آزمون')
        db.session.add(q)
        db.session.flush()
        for i in range(n):
            db.session.add(QuizQuestion(
                quiz_id=q.id, text=f'سوال {i+1}؟',
                choices=json.dumps(['گزینه یک', 'گزینه دو', 'گزینه سه'], ensure_ascii=False),
                correct_index=1, explanation='توضیح سوال', sort=i))
        db.session.commit()
        return q.id


def _demo_id(app):
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        return u.id


def _enroll(app):
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        db.session.add(Enrollment(user_id=u.id, course_id=1))
        db.session.commit()
        return u.id


def test_quiz_requires_enrollment(app, client):
    """بدون ثبت‌نام، دسترسی به آزمون باید رد شود."""
    qid = _make_quiz(app)
    login(client, 'demo@test.ir', 'demo123')
    r = client.get(f'/quiz/{qid}')
    # کاربر ثبت‌نام نکرده → به صفحهٔ دوره برمی‌گردد
    assert r.status_code in (302, 403)


def test_quiz_requires_login_for_guest(client):
    r = client.get('/quiz/9999')
    assert r.status_code == 404


def test_quiz_full_flow_pass(app, client):
    """جریان کامل: ثبت‌نام → شروع → پاسخ درست → قبولی و ذخیرهٔ نمره."""
    qid = _make_quiz(app, n=3)
    _enroll(app)
    login(client, 'demo@test.ir', 'demo123')

    # صفحهٔ آزمون
    r = client.get(f'/quiz/{qid}')
    assert r.status_code == 200
    assert 'آزمون تستی' in r.get_data(as_text=True)
    assert 'شروع آزمون' in r.get_data(as_text=True)

    # شروع آزمون
    r = client.get(f'/quiz/{qid}/start')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'سوال 1' in body and 'گزینه دو' in body

    # ثبت پاسخ — همه درست (گزینهٔ درست = شاخص 1)
    answers = {f'q_{i}': '1' for i in range(1, qid + 1)}
    # شناسه واقعی سوالات را پیدا کن
    with app.app_context():
        qs = QuizQuestion.query.filter_by(quiz_id=qid).order_by(QuizQuestion.sort).all()
        answers = {f'q_{q.id}': '1' for q in qs}
    tok = _csrf(client, f'/quiz/{qid}')
    r = client.post(f'/quiz/{qid}/submit', data={'_csrf_token': tok, **answers},
                    follow_redirects=False)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'آفرین، قبول شدی' in body  # نمره ۱۰۰ → قبول
    assert '100' in body

    # نمره ذخیره شده است
    with app.app_context():
        att = QuizAttempt.query.filter_by(quiz_id=qid, user_id=_demo_id(app)).first()
        assert att is not None and att.passed is True
        assert att.score == 100


def test_quiz_fail_stored(app, client):
    """پاسخ اشتباه → مردودی و ذخیرهٔ نمرهٔ پایین."""
    qid = _make_quiz(app, n=3)
    _enroll(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        qs = QuizQuestion.query.filter_by(quiz_id=qid).order_by(QuizQuestion.sort).all()
        answers = {f'q_{q.id}': '0' for q in qs}  # همه غلط (درست = 1)
    tok = _csrf(client, f'/quiz/{qid}/start')
    r = client.post(f'/quiz/{qid}/submit', data={'_csrf_token': tok, **answers},
                    follow_redirects=False)
    body = r.get_data(as_text=True)
    assert 'تلاش دوباره' in body
    with app.app_context():
        att = QuizAttempt.query.filter_by(quiz_id=qid, user_id=_demo_id(app)).first()
        assert att is not None and att.passed is False
        assert att.score == 0


def test_quiz_no_duplicate_points_on_retry(app, client):
    """امتیاز گیمیفیکیشن فقط برای قبولی تعلق می‌گیرد و ثبت تکرار امن است."""
    qid = _make_quiz(app, n=3)
    _enroll(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        from models import User
        u = User.query.filter_by(email="demo@test.ir").first()
        before = u.points or 0
    with app.app_context():
        qs = QuizQuestion.query.filter_by(quiz_id=qid).order_by(QuizQuestion.sort).all()
        answers = {f'q_{q.id}': '1' for q in qs}
    tok = _csrf(client, f'/quiz/{qid}/start')
    client.post(f'/quiz/{qid}/submit', data={'_csrf_token': tok, **answers})
    with app.app_context():
        from models import User
        after = User.query.filter_by(email="demo@test.ir").first().points
        assert after >= before + 20  # جایزهٔ قبولی آزمون
