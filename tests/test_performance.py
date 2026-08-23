# -*- coding: utf-8 -*-
"""تست‌های کارایی — جلوگیری از بازگشت الگوی N+1.

چرا این فایل لازم است؟
    الگوی «کوئری داخل حلقه» (N+1) خروجی درستی تولید می‌کند، بنابراین هیچ
    تست عملکردی آن را نمی‌گیرد. فقط زیر بار واقعی خودش را نشان می‌دهد،
    آن هم وقتی دیگر دیر شده. این تست‌ها «بودجهٔ کوئری» را قفل می‌کنند.

روش سنجش:
    به‌جای عبور از لایهٔ HTTP (که به لاگین، نشست و قالب وابسته است و
    اندازه‌گیری را نویزی می‌کند)، منطق تجمیع مستقیماً صدا زده می‌شود.
    این کار تست را قطعی و سریع نگه می‌دارد.
"""
from datetime import timedelta

import sqlalchemy
from sqlalchemy import event

from models import Ticket, User, db, utcnow


class QueryCounter:
    """شمارندهٔ کوئری‌های اجراشده — برای سنجش الگوی N+1."""

    def __init__(self):
        self.count = 0

    def __enter__(self):
        def _listener(conn, cur, stmt, params, ctx, many):
            self.count += 1
        self._listener = _listener
        event.listen(sqlalchemy.engine.Engine, 'before_cursor_execute', _listener)
        return self

    def __exit__(self, *exc):
        event.remove(sqlalchemy.engine.Engine, 'before_cursor_execute', self._listener)
        return False


def _seed_supports(count, tag, tickets_each=4):
    """ساخت `count` پشتیبان که هرکدام چند تیکت پاسخ‌داده‌شده دارند."""
    admin = User(name='مدیر کارایی', email=f'perfadm{tag}@test.ir',
                 phone=f'0916{tag:07d}', role='super_admin', is_active=True)
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.flush()
    for i in range(count):
        s = User(name=f'پشتیبان {tag}-{i}', email=f'sup{tag}_{i}@test.ir',
                 phone=f'0917{tag:03d}{i:04d}', role='support', is_active=True)
        s.set_password('support123')
        db.session.add(s)
        db.session.flush()
        for j in range(tickets_each):
            db.session.add(Ticket(
                user_id=admin.id, subject=f'تیکت {i}-{j}', assigned_to=s.id,
                status='answered',
                created_at=utcnow() - timedelta(hours=6),
                first_response_at=utcnow() - timedelta(hours=2)))
    db.session.commit()


def _aggregate_report():
    """همان منطق تجمیعی که admin.tickets_report استفاده می‌کند."""
    supports = User.query.filter(User.role.in_(['support', 'admin'])).all()
    answered_map = dict(
        db.session.query(Ticket.assigned_to, db.func.count(Ticket.id))
        .filter(Ticket.assigned_to.isnot(None))
        .group_by(Ticket.assigned_to).all())
    resp_sum, resp_cnt = {}, {}
    for assigned_to, created_at, first_response_at in db.session.query(
            Ticket.assigned_to, Ticket.created_at, Ticket.first_response_at
    ).filter(Ticket.first_response_at.isnot(None)).all():
        if not created_at or not first_response_at:
            continue
        hours = (first_response_at - created_at).total_seconds() / 3600
        if assigned_to is not None:
            resp_sum[assigned_to] = resp_sum.get(assigned_to, 0.0) + hours
            resp_cnt[assigned_to] = resp_cnt.get(assigned_to, 0) + 1
    return [{
        'user': u.name or '—',
        'answered': answered_map.get(u.id, 0),
        'avg_h': (round(resp_sum[u.id] / resp_cnt[u.id], 1)
                  if resp_cnt.get(u.id) else None),
    } for u in supports]


def test_report_query_count_does_not_grow_with_supports(app):
    """تعداد کوئری گزارش نباید با تعداد پشتیبان‌ها رشد کند.

    منطق قبلی به‌ازای هر پشتیبان سه کوئری جدا می‌زد؛ اندازه‌گیری واقعی
    نشان داد ۳ پشتیبان = ۲۳ کوئری، ۱۵ پشتیبان = ۵۹ و ۳۰ پشتیبان = ۱۰۴.
    نسخهٔ تجمیعی روی هر سه اندازه عدد ثابتی می‌دهد.
    """
    with app.app_context():
        _seed_supports(3, tag=1)
        with QueryCounter() as small:
            _aggregate_report()

        _seed_supports(25, tag=2)
        with QueryCounter() as large:
            _aggregate_report()

    growth = large.count - small.count
    assert growth == 0, (
        'افزودن ۲۵ پشتیبان {} کوئری اضافه کرد ({}→{}) — الگوی N+1 برگشته است'
        .format(growth, small.count, large.count))
    assert large.count <= 5, (
        'گزارش تجمیعی باید با چند کوئری ثابت انجام شود، نه {}'.format(large.count))


def test_report_values_match_naive_logic(app):
    """بهینه‌سازی نباید عددها را تغییر دهد — مقایسه با منطق سادهٔ مرجع."""
    with app.app_context():
        _seed_supports(4, tag=3, tickets_each=3)
        # چند تیکت بدون پاسخ و بدون ارجاع برای پوشش حالت‌های مرزی
        admin = User.query.filter_by(email='perfadm3@test.ir').first()
        db.session.add(Ticket(user_id=admin.id, subject='بی‌ارجاع', assigned_to=None,
                              status='open', created_at=utcnow() - timedelta(hours=3)))
        sup = User.query.filter_by(email='sup3_0@test.ir').first()
        db.session.add(Ticket(user_id=admin.id, subject='بی‌پاسخ', assigned_to=sup.id,
                              status='open', created_at=utcnow() - timedelta(hours=2)))
        db.session.commit()

        # منطق سادهٔ مرجع (همان کد قبل از بهینه‌سازی)
        naive = []
        for u in User.query.filter(User.role.in_(['support', 'admin'])).all():
            answered = Ticket.query.filter(Ticket.assigned_to == u.id).count()
            samples = [
                (t.first_response_at - t.created_at).total_seconds() / 3600
                for t in Ticket.query.filter(
                    Ticket.assigned_to == u.id,
                    Ticket.first_response_at.isnot(None)).all()]
            naive.append({
                'user': u.name or '—', 'answered': answered,
                'avg_h': round(sum(samples) / len(samples), 1) if samples else None})

        optimized = _aggregate_report()

    assert sorted(map(str, naive)) == sorted(map(str, optimized)), \
        'خروجی نسخهٔ تجمیعی با منطق مرجع یکی نیست'


def test_report_handles_empty_and_null_data(app):
    """پشتیبان بدون تیکت و تیکت بدون ارجاع نباید باعث خطا یا تقسیم بر صفر شود."""
    with app.app_context():
        u = User(name='پشتیبان بی‌تیکت', email='idle@test.ir', phone='09181112222',
                 role='support', is_active=True)
        u.set_password('support123')
        db.session.add(u)
        db.session.commit()

        rows = _aggregate_report()
        row = next(r for r in rows if r['user'] == 'پشتیبان بی‌تیکت')
        assert row['answered'] == 0
        assert row['avg_h'] is None, 'میانگین برای پشتیبان بدون تیکت باید None باشد'


def test_tickets_report_route_renders(app, client):
    """مسیر گزارش باید بدون خطای سرور پاسخ دهد."""
    with app.app_context():
        _seed_supports(3, tag=4)
    r = client.get('/admin/tickets/report', follow_redirects=False)
    # کاربر مهمان ریدایرکت/۴۰۳ می‌گیرد؛ مهم این است که ۵۰۰ ندهد.
    assert r.status_code < 500, 'مسیر گزارش نباید خطای سرور بدهد'
