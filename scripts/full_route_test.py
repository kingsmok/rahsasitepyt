#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست جامع همه مسیرها — با مقادیر واقعی از دیتابیس، در ۳ حالت (مهمان/دانشجو/ادمین)"""
import re, json, sys, requests

BASE = "http://localhost:5000"
IDS = json.load(open('/tmp/real_ids.json'))
OK = (200, 302, 301, 308)
results = []

def csrf(r):
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else None

def check(sess, path, note=""):
    try:
        r = sess.get(BASE + path, allow_redirects=False, timeout=25)
        if r.status_code not in OK:
            results.append((r.status_code, path, note))
            return False
        return True
    except Exception as e:
        results.append((f"ERR:{type(e).__name__}", path, note))
        return False

# ---------------- لاگین‌ها ----------------
guest = requests.Session()

stu = requests.Session()
r = stu.get(BASE + "/auth/login")
tok = csrf(r)
r = stu.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "demo@academy.ir", "password": "demo123"}, allow_redirects=False)
assert r.status_code in (301, 302), "demo login failed"

adm = requests.Session()
r = adm.get(BASE + "/auth/login")
tok = csrf(r)
r = adm.post(BASE + "/auth/login", data={"_csrf_token": tok, "email": "admin@academy.ir", "password": "admin123"}, allow_redirects=False)
r2 = adm.get(BASE + "/auth/admin-2fa")
m = re.search(r"کد تایید دومرحله‌ای \(دمو\): (\d+)", r2.text)
if m:
    adm.post(BASE + "/auth/admin-2fa", data={"_csrf_token": csrf(r2), "code": m.group(1)}, allow_redirects=False)
print("sessions ready")

# ---------------- ساخت لیست تست‌ها ----------------
T = []  # (session, path, note)
def add(sess, path, note=""):
    T.append((sess, path, note))

# === مسیرهای بدون پارامتر (مهمان) ===
guest_routes = [
    "/", "/courses", "/about", "/contact", "/faq", "/terms", "/privacy",
    "/blog", "/teachers", "/compare", "/verify-certificate", "/consultation",
    "/learning-paths", "/leaderboard", "/talent-test", "/sitemap.xml",
    "/robots.txt", "/become-teacher", "/bundles", "/maintenance",
    "/auth/login", "/auth/register", "/auth/forgot",
    "/success-stories", "/cart",
]
for p in guest_routes:
    add(guest, p)

# === مسیرهای پارامتری با مقادیر واقعی ===
pairs = [
    ("/course/{v}", IDS['courses'][:3]),
    ("/teacher/{v}", IDS['teachers']),
    ("/blog/{v}", IDS['blogs'][:2]),
    ("/bundle/{v}", IDS['bundles']),
    ("/form/{v}", IDS['forms'][:1]),
    ("/r/{v}", IDS['refs'][:1]),
]
for fmt, vals in pairs:
    for v in vals:
        add(guest, fmt.format(v=v))

# === دانشجو ===
for c in IDS['courses_all'][:5]:
    add(stu, f"/course/{IDS['courses'][c-1] if c-1 < len(IDS['courses']) else IDS['courses'][0]}")
stu_paths = [
    "/dashboard", "/dashboard/profile", "/dashboard/orders", "/dashboard/tickets",
    "/dashboard/tickets/new", "/dashboard/notifications", "/dashboard/wallet",
    "/dashboard/referral", "/dashboard/study-plan", "/dashboard/my-courses",
    "/dashboard/favorites", "/dashboard/challenge", "/community/",
    "/community/messages", "/community/my-classes", "/community/live",
    "/support-chat", "/leaderboard", "/compare?ids=1,3", "/exam/practice",
    "/exam/practice/history", "/success-stories", "/placement-test",
]
for p in stu_paths:
    add(stu, p)
for q in IDS['quizzes']:
    add(stu, f"/quiz/{q}")
    add(stu, f"/quiz/{q}/start")
add(stu, f"/quiz/{IDS['quizzes'][0]}/start")
# یادگیری — دوره‌های ثبت‌نام‌شده دمو
add(stu, "/learn/1"); add(stu, "/learn/2")
add(stu, "/certificate/2")
for a in IDS['assignments']:
    add(stu, f"/assignment/{a}")
for c in IDS['courses_all'][:3]:
    add(stu, f"/feedback/{c}")
for l in IDS['lessons'][:2]:
    add(stu, f"/lesson/{l}/ask")
for oc in IDS['orders_paid'][:1]:
    add(stu, f"/invoice/{oc}")
    add(stu, f"/invoice/{oc}/pdf")
    add(stu, f"/pay/result/{oc}")
for oc in IDS['orders_pending'][:1]:
    add(stu, f"/pay/{oc}")
    add(stu, f"/pay/bank/{oc}")
    add(stu, f"/pay/card2card/{oc}")
    add(stu, f"/pay/result/{oc}")
for a in IDS['attempts']:
    add(stu, f"/exam/practice/result/{a}")
add(stu, "/dashboard/logout-all")

# === ادمین ===
admin_paths = [
    "/admin/", "/admin/courses", "/admin/courses/new", "/admin/categories",
    "/admin/users", "/admin/users/add", "/admin/orders", "/admin/coupons",
    "/admin/blog", "/admin/blog/new", "/admin/pages", "/admin/pages/trash",
    "/admin/backup", "/admin/backup/list", "/admin/gateways", "/admin/sms",
    "/admin/messengers", "/admin/optimizer", "/admin/seo/", "/admin/seo/redirects",
    "/admin/seo/notfound", "/admin/roles", "/admin/forms", "/admin/forms/new",
    "/admin/question-bank", "/admin/tickets", "/admin/tickets/report",
    "/admin/behavior-report", "/admin/installments", "/admin/notifications",
    "/admin/certificates", "/admin/activity", "/admin/reports/inactive-users",
    "/admin/reports/popular-pages", "/admin/reports/revenue-courses",
    "/admin/reports/seo-health", "/admin/reports/coupons", "/admin/reports/feedback",
    "/admin/reports/teachers", "/admin/reports/exams", "/admin/proofs",
    "/admin/payouts", "/admin/quizzes", "/admin/quizzes/new", "/admin/live-sessions",
    "/admin/bundles", "/admin/bundles/new", "/admin/newsletters", "/admin/reviews",
    "/admin/messages", "/admin/chat", "/admin/canned-replies", "/admin/menus",
    "/admin/menus/new", "/admin/assignments", "/admin/assignments/new",
    "/admin/submissions", "/admin/lesson-questions", "/admin/forum-moderate",
    "/admin/themes", "/admin/settings", "/admin/designs", "/admin/consultations",
    "/admin/success-stories", "/builder", "/builder/new",
]
for p in admin_paths:
    add(adm, p)
# مسیرهای پارامتری ادمین
for c in IDS['courses_all'][:2]:
    add(adm, f"/admin/courses/{c}/edit")
    add(adm, f"/admin/courses/{c}/lessons")
for u in IDS['users']:
    add(adm, f"/admin/users/{u}/profile")
for t in IDS['tickets']:
    add(adm, f"/admin/tickets/{t}")
for q in IDS['quizzes']:
    add(adm, f"/admin/quizzes/{q}/edit")
page_ids = {'home': 4, 'mobile-menu': 3, 'site-footer': 2, 'site-header': 1}
for p in IDS['pages']:
    pid = page_ids.get(p)
    if pid:
        add(adm, f"/admin/pages/{pid}/revisions")
        add(adm, f"/admin/pages/{pid}/seo")
for m in IDS['menus']:
    add(adm, f"/admin/menus/{m}")
for s in IDS['submissions']:
    add(adm, f"/admin/submissions/{s}/grade")
for q in IDS['lquestions']:
    add(adm, f"/admin/lesson-questions/{q}/answer")
for f in [1]:
    add(adm, f"/admin/forms/{f}/edit")
    add(adm, f"/admin/forms/{f}/entries")
for b in [1]:
    add(adm, f"/admin/bundles/{b}/edit")
for b in [2, 3, 1]:
    add(adm, f"/admin/blog/{b}/edit")
# builder editor برای صفحات موجود
for p in IDS['pages']:
    add(adm, f"/builder/{p}")
for gw in IDS['gws']:
    add(adm, f"/admin/gateways/test/{gw}")
for mid in ['telegram', 'bale', 'eitaa']:
    add(adm, f"/admin/messengers/test/{mid}")

# === مسیرهای POST-only — فقط بررسی کنیم 405/500 ندهند (با id ناموجود → 404 یعنی درست کار می‌کند) ===
post_routes = [
    (adm, "/admin/menus/new"), (stu, "/dashboard/logout-all"),
    (stu, "/talent-test/result"), (stu, "/community/topic/new"),
    (stu, "/wallet/confirm"), (stu, "/lesson/1/ask"),
    (stu, "/feedback/1"), (adm, "/admin/users/send-sms"),
    (adm, "/admin/newsletters/send"), (adm, "/admin/backup/restore/x"),
    (stu, "/course/1/review"), (guest, "/newsletter"),
]
for sess, p in post_routes:
    try:
        r = sess.post(BASE + p, data={}, allow_redirects=False, timeout=25)
        if r.status_code in (404, 302, 200, 400, 422, 500):
            # 500 را هم به عنوان مشکل ثبت می‌کنیم
            if r.status_code == 500:
                results.append((500, f"POST {p}", "post"))
        else:
            results.append((r.status_code, f"POST {p}", "post"))
    except Exception as e:
        results.append((f"ERR:{type(e).__name__}", f"POST {p}", "post"))

# === اجرا ===
for sess, p, note in T:
    check(sess, p, note)

print(f"\n=== {len(T)} GET تست + {len(post_routes)} POST تست ===")
print(f"=== {len(results)} مشکل ===")
for code, path, note in sorted(set(results), key=lambda x: str(x[0])):
    print(f"  {code}  {path}  [{note}]")
if not results:
    print("ALL GOOD ✅")
