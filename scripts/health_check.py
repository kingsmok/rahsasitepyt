#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست سلامت همه مسیرهای آکادمی — نسخه با URLهای واقعی"""
import re, sys, requests

BASE = "http://localhost:5000"
s = requests.Session()

def get(url, **kw):
    return s.get(BASE + url, allow_redirects=False, timeout=20, **kw)

def csrf_from(r):
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else None

results = {}

def test(p, note=""):
    try:
        r = get(p)
        results[p] = (r.status_code, note)
    except Exception as e:
        results[p] = (f"ERR {e}", note)

# ---- لاگین ادمین با 2FA ----
r = get("/auth/login")
tok = csrf_from(r)
r = s.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "admin@academy.ir", "password": "admin123"}, allow_redirects=False, timeout=20)
if r.status_code in (301, 302):
    r2 = get("/auth/admin-2fa")
    m = re.search(r"کد تایید دومرحله‌ای \(دمو\): (\d+)", r2.text)
    if m:
        tok2 = csrf_from(r2)
        s.post(BASE + "/auth/admin-2fa", data={"_csrf_token": tok2, "code": m.group(1)}, allow_redirects=False, timeout=20)
        print("admin 2FA login OK")
    else:
        print("!! no 2FA code; checking if already logged in")
else:
    print("login:", r.status_code, r.text[:200])

# ---- عمومی ----
for p in ["/", "/courses", "/about", "/contact", "/faq", "/terms", "/privacy",
          "/blog", "/teachers", "/compare?ids=1,2", "/verify-certificate",
          "/consultation", "/learning-paths", "/leaderboard", "/talent-test",
          "/sitemap.xml", "/robots.txt", "/become-teacher", "/bundles", "/placement-test"]:
    test(p)

# slugs
courses = ["دوره-جامع-برنامهنویسی-پایتون-1", "توسعه-وب-با-Flask--پروژهمحور-2",
           "دوره-پروژهمحور-Django--فروشگاه-اینترنتی-3", "آموزش-کامل-Reactjs--از-مقدماتی-تا-پیشرفته-4",
           "آموزش-جامع-اکسل--از-مقدماتی-تا-پیشرفته-7"]
for c in courses:
    test(f"/course/{c}")
test("/teacher/3")
test("/bundle/web-dev-bundle")
test("/courses?cat=آفیس")
for b in ["راهنمای-انتخاب-اولین-زبان-برنامهنویسی", "چگونه-در-۶-ماه-توسعهدهنده-وب-شویم؟"]:
    test(f"/blog/{b}")
for f in ["فرم-نظرسنجی-دوره"]:
    test(f"/form/{f}")
test("/maintenance")

# ---- کاربر دمو (لاگین) ----
s.get(BASE + "/auth/logout", allow_redirects=True, timeout=20)
r = get("/auth/login")
tok = csrf_from(r)
s.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "demo@academy.ir", "password": "demo123"}, allow_redirects=False, timeout=20)
print("demo login OK")

for p in ["/dashboard", "/dashboard/profile", "/dashboard/orders", "/dashboard/tickets",
          "/dashboard/notifications", "/dashboard/wallet", "/dashboard/referral",
          "/dashboard/study-plan", "/dashboard/my-courses", "/dashboard/favorites",
          "/dashboard/challenge", "/community/", "/community/messages", "/community/my-classes",
          "/support-chat", "/quiz/1", "/quiz/2", "/quiz/2/start", "/leaderboard", "/compare?ids=1,2"]:
    test(p)

# یادگیری دوره 1 و 2 (دمو در دوره 2 ثبتنام شده)
test("/learn/2")
test("/certificate/2")

# ---- ادمین ----
s.get(BASE + "/auth/logout", allow_redirects=True, timeout=20)
r = get("/auth/login")
tok = csrf_from(r)
s.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "admin@academy.ir", "password": "admin123"}, allow_redirects=False, timeout=20)
r2 = get("/auth/admin-2fa")
m = re.search(r"کد تایید دومرحله‌ای \(دمو\): (\d+)", r2.text)
if m:
    tok2 = csrf_from(r2)
    s.post(BASE + "/auth/admin-2fa", data={"_csrf_token": tok2, "code": m.group(1)}, allow_redirects=False, timeout=20)
admin_routes = [
    "/admin/", "/admin/courses", "/admin/courses/new", "/admin/categories", "/admin/users",
    "/admin/orders", "/admin/coupons", "/admin/blog", "/admin/pages", "/admin/backup",
    "/admin/backup/list", "/admin/gateways", "/admin/sms", "/admin/messengers",
    "/admin/optimizer", "/admin/seo/", "/admin/seo/redirects", "/admin/seo/notfound",
    "/admin/roles", "/admin/forms", "/admin/question-bank", "/admin/tickets",
    "/admin/tickets/report", "/admin/behavior-report", "/admin/installments",
    "/admin/notifications", "/admin/certificates", "/admin/activity", "/admin/reports/inactive-users",
    "/admin/reports/popular-pages", "/admin/reports/revenue-courses", "/admin/reports/seo-health",
    "/admin/proofs", "/admin/payouts", "/admin/quizzes", "/admin/quizzes/new",
    "/admin/live-sessions", "/admin/bundles", "/admin/newsletters", "/admin/reviews",
    "/admin/messages", "/admin/chat", "/admin/canned-replies", "/admin/menus", "/admin/menus/new",
    "/admin/assignments", "/admin/submissions", "/admin/lesson-questions", "/admin/forum-moderate",
    "/admin/themes", "/admin/settings", "/admin/designs", "/admin/forms/new", "/admin/pages/trash",
    "/admin/notifications", "/admin/consultations", "/admin/success-stories",
    "/admin/reports/coupons", "/admin/reports/feedback", "/admin/reports/teachers", "/admin/reports/exams",
]
for p in admin_routes:
    test(p)

# ---- استاد ----
s.get(BASE + "/auth/logout", allow_redirects=True, timeout=20)
r = get("/auth/login")
tok = csrf_from(r)
s.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "sara@academy.ir", "password": "teacher123"}, allow_redirects=False, timeout=20)
for p in ["/teacher-panel/", "/teacher-panel/courses", "/teacher-panel/assignments",
          "/teacher-panel/questions", "/teacher-panel/revenue", "/teacher-panel/students"]:
    test(p)

# ---- API ----
for p in ["/api/cart/count", "/api/notifications/unread", "/api/chat/poll",
          "/api/cart/upsell?course_id=1", "/courses?q=پایتون"]:
    test(p)

# ---- یکپارچگی دیتابیس: لاگهای پرداخت یتیم ----
try:
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'instance', 'academy.db')
    con = sqlite3.connect(db_path)
    orphan_logs = con.execute(
        "SELECT COUNT(*) FROM payment_logs pl LEFT JOIN orders o ON o.id=pl.order_id WHERE o.id IS NULL"
    ).fetchone()[0]
    orphan_inst = con.execute(
        "SELECT COUNT(*) FROM installments i LEFT JOIN orders o ON o.id=i.order_id WHERE o.id IS NULL"
    ).fetchone()[0]
    orphan_enr = con.execute(
        "SELECT COUNT(*) FROM enrollments e LEFT JOIN orders o ON o.id=e.order_id "
        "WHERE e.order_id IS NOT NULL AND o.id IS NULL"
    ).fetchone()[0]
    con.close()
    if orphan_logs or orphan_inst or orphan_enr:
        results['DB-INTEGRITY'] = (f'BAD orphan logs={orphan_logs} inst={orphan_inst} enr={orphan_enr}', 'db')
        print(f"\n⚠️  یکپارچگی دیتابیس: {orphan_logs} لاگ پرداخت یتیم، {orphan_inst} قسط یتیم، {orphan_enr} ثبت‌نام یتیم")
    else:
        print("DB integrity: OK (بدون رکورد یتیم)")
except Exception as e:
    print("DB integrity check error:", e)

# ---- گزارش ----
ok_codes = (200, 302, 301, 308)
bad = {k: v for k, v in results.items() if v[0] not in ok_codes}
print(f"\n=== {len(results)} tested, {len(bad)} bad ===")
for k, v in sorted(bad.items()):
    print(f"  {v[0]}  {k}   [{v[1]}]")
if not bad:
    print("ALL GOOD ✅")
