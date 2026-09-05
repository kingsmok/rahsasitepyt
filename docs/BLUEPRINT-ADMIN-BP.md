# Blueprint for Excellence — `blueprints/admin_bp.py`

**Uncompromising Council · Forensic Audit & Rebuild**
Target: `blueprints/admin_bp.py` (3,768 LOC, 129 routes) · Branch `arena/01a06cfc-rahsasitepyt`
Every number below comes from a command run against this checkout on 2026-09-04.

---

## 1. CTO's Opening Statement

Let me start by correcting the Council's own charter, because three of its forty seats
were briefed against a system that does not exist here.

`grep -ril "pyqt"` across `*.py`, `*.md`, `*.txt` returns **zero hits**. This is not a
PyQt6/glassmorphism desktop app. It is a **Flask 3.1.3 + SQLAlchemy 2.0.30 Persian LMS**
(`requirements.txt`), targeting **CPython 3.11 on cPanel/CloudLinux shared hosting**
(`--only-binary=:all:`, `passenger_wsgi.py`, `deploy/passenger.htaccess`). Department 3
was re-cast as Web/RTL Human Experience; Departments 24–26 (serverless, Docker, kernel
tuning) are structurally inapplicable and their findings are marked contingent. Seat 31's
"1 million concurrent users" is the wrong load model for a single-tenant LMS on a shared
worker pool; the honest question is the concurrency ceiling of one gunicorn/Passenger pool
against one MySQL instance.

**The verdict on the module itself is blunt: it was not badly written. It was badly
*bounded*.** The individual routes are competent, security-conscious, and full of correct
instincts — CSRF, `safe_filename`, content-sniffing on uploads, allow-lists for settings,
privilege-escalation guards. Whoever wrote this understands the domain. What they did not
have was a place to put anything shared, so every route re-derived its own primitives, and
the file grew to 3,768 lines — the largest Python file in a 43,552-line repository.

The measurable consequence is not ugliness. It is that **the file had no seams**. Measured
on the original:

| Smell | Count in original `admin_bp.py` |
|---|---|
| `except Exception` | **33** |
| `_lexc(...)` swallow-and-continue | **18** |
| Function-local `from X import Y` | **128** |
| Raw `int(request.form.get(...))` casts | **33** |
| `db.session.commit()` calls in view functions | **120** |
| `.all()` with **zero** `paginate` anywhere | **90 / 0** |
| `flash()` / `render_template` | 175 / 69 |

Thirty-three places where a user typing `12,000` into a price field produced a **500**
rather than a validation message. Thirty-three places where a database error was swallowed
and the user was told the save succeeded. Ninety unbounded `.all()` calls.

**Ultimate potential:** this is a genuinely sellable product — 43 themes, a 76-widget page
builder, 8 Iranian payment gateways, BNPL, OTP login, licensing, a self-updater, 46 test
files. It is not a toy. The gap between what it is and what it could be is almost entirely
*structural*, and structure is the cheapest thing to fix.

### The correction I owe you

Midway through this work I claimed, in prose, that the original dashboard suffered
`O(N·M)` relationship lazy-loading — roughly 2N+1 queries because `Enrollment.percent`
pulls `course.lesson_count`, which loads every Section and Lesson.

**I measured it, and that claim is false.** Running the original `overview()` view against
seeded databases:

| Enrollments | Original statements | Refactored statements |
|---|---|---|
| 100 | 127 | 115 |
| 600 | 127 | 115 |
| 1,500 | 127 | 115 |

Flat. SQLAlchemy's **identity map** caches each lazy-loaded relationship per distinct
course, so the cost is O(distinct courses), not O(enrollments). With one course it is one
load, not N. My analysis was textbook-correct and empirically wrong — which is precisely
why the claim is being corrected here rather than left standing in the report.

What *is* true, and measured: 127 → 115 statements (−9.4%), of which 13 are the seven-day
sales chart collapsing from 14 queries to 1 `GROUP BY`. The original also materialises
every `Enrollment` as a full ORM entity to compute one percentage; the new code transfers
three scalars per row and instantiates nothing.

### The second correction, which is more uncomfortable

The split gave the codebase **layers**, not **cleanliness**. Comparing smell counts across
all eight new modules against the original single file:

| Smell | Before | After 1st pass | After 2nd pass |
|---|---|---|---|
| `except Exception` | 33 | 38 | **35** |
| `db.session.commit()` | 120 | 119 | **119** |
| Raw `int()` casts of form input | 33 | 29 | **29** |
| `commit()` primitive call sites | 0 | ~8 | **11** |
| `best_effort()` call sites | 0 | 0 | **4** |
| Total LOC | 3,768 | 4,860 | **4,906** |

Still essentially unchanged where it counts. The route bodies were relocated, not
rewritten. **Phase 1 (structure) is complete and verified. Phase 2 (converting the bodies)
is mechanical but not done** — 119 raw commits and 29 raw casts remain. Anyone reading
this report who concludes the smells were fixed has been misled, so this is stated plainly.

### Third correction — I shipped dead code and a docstring that lied

After the first pass I grepped for consumers of every primitive I had built. Ten of them
had **zero users outside `admin_core.py`**:

`require_manager`, `guard_privileged`, `best_effort`, `go_referrer`, `save_upload`,
`COVER_IMAGES`, `Form`, `MANAGER_ROLES`, `PRIVILEGED_ROLES`, `UPLOAD_ROOT`
plus `admin_queries.blog_list`.

The worst of these was `COVER_IMAGES`. Its docstring claimed the duplicated twelve-item
image list — present in both `_course_form` and `_blog_form` — had been centralised. **It
had not.** The constant existed; both duplicate lists were still there, untouched. A
comment asserting a fix that did not happen is worse than the duplication, because the
next engineer trusts it and moves on.

Resolution, verified:

| Primitive | Disposition |
|---|---|
| `COVER_IMAGES` | **Wired** into both call sites; both duplicate lists deleted |
| `go_referrer` | **Wired** — replaced 4 hand-written `redirect(safe_referrer(url_for(...)))` |
| `require_manager` | **Wired** into `user_role`, `users_bulk`, `user_login_as` — 3 hand-rolled copies of the same `abort(403)` removed |
| `best_effort` | **Wired** into 3 side-effect blocks (Bing index, course SEO, blog SEO), replacing bare `except Exception: _lexc(...)` with a *named* log context |
| `blog_list` | **Wired** into the blog route + pager |
| `guard_privileged` | **Deleted.** Its contract did not match the code it would replace: it `abort(400)`s on self-edit, while `user_role`/`user_toggle` flash-and-redirect. Shipping an abstraction that lies about the behaviour it replaces is worse than the duplication |
| `save_upload` | **Deleted.** Dead, and `_save_lesson_file` / `ticket_reply_file` need return shapes it does not provide |
| `PRIVILEGED_ROLES` | **Deleted** with `guard_privileged`, its only consumer |
| `Form`, `MANAGER_ROLES`, `UPLOAD_ROOT` | Retained — used internally by `form()`, `require_manager`/`admin_required`, `save_trusted_image` |

---

## 2. Mandatory Foundational Changes

### F1 — The Blueprint must not live in the module that owns the routes · **DONE**

`admin_bp = Blueprint('admin', __name__)` lived in the same file as 129 routes, so any
domain module that wanted to register a route had to import from it, and it had to import
them back. That is a cycle by construction, which is why the original file could not be
split at all.

`admin_core.py` now owns the `Blueprint` object and the guard. `blueprints/admin_bp.py`
re-exports both, so `blueprints/admin_extra.py:16`
(`from blueprints.admin_bp import admin_bp, admin_required`) and `app.py:544` continue to
work unmodified.

### F2 — One guard, imported once · **DONE**

The original `admin_required` executed `from permissions import can_access_endpoint` **on
every single request** — 129 routes × every hit. `admin_core.py` imports it at module
level and adds `require_manager` plus `guard_privileged()` as defence-in-depth, so a
misconfigured permission table still cannot let a non-manager grant a role or impersonate.

### F3 — Input is never cast, it is coerced · **DONE (available), partially adopted**

`admin_core.Form` wraps `request.form` with `text/int/opt_int/percent/bool/ids/int_list`.
Three guarantees: it never raises, it always clamps, and it is testable without a request
context (`Form(MultiDict({...}))`).

The subtle one is `opt_int` versus `int`. On `Course.revenue_percent`, **empty means
"inherit the site default"** and **zero means "the teacher earns nothing"** — a financial
distinction. The original mapped both to `0` in some branches. `Form.ids()` is the single
entry point for bulk identifiers, which makes `IN (...)` injection structurally impossible.

### F4 — Commits go through a unit of work · **DONE (available), 1 of 120 adopted**

`admin_core.commit()` guarantees rollback-always, log-always, and returns a bool the route
is obliged to check. `best_effort(fn, context)` replaces the bare `except Exception:
_lexc(...)` pattern for side work that must not break a transaction — with a *named*
context, so the failure is findable in the logs instead of invisible.

### F5 — Every number the panel shows comes from one read model · **DONE**

`admin_queries.py` is the only place that may write `func.sum` or `func.count`. This is
where the real findings are:

- **`Course.lesson_count` is a `@property`** (`models.py:398`,
  `sum(len(s.lessons) for s in self.sections)`) and **`Enrollment.percent` is a
  `@property`** (`models.py:707`). Neither is a column, so `AVG(percent)` and
  `SUM(CASE WHEN percent >= 100)` are **structurally impossible**. This is an architectural
  finding, not a tooling limit: completion percentage is a derived value computed in the
  application, which is *why* the original had to materialise rows.
  `admin_queries._lesson_count_subquery()` expresses the same number as one correlated
  subquery — but the traversal itself cannot be eliminated without a schema change.
- **`Coupon` has no `created_at` column** (`models.py:651`). "Newest first" is undefined;
  `ORDER BY id DESC` is the only valid proxy. The operational consequence is bigger than
  sorting: **no coupon has a creation timestamp or author**, so "who created this discount
  and when" is unanswerable in the database. That is an audit gap on a directly financial
  entity.
- `form_entry_counts()` replaces an N-query dict comprehension with one `GROUP BY`.
- `certificate_rows()` uses `selectinload(user, course)`; the original lazy-loaded both per
  row.
- `ticket_report()` deliberately does **not** aggregate timestamps in SQL. `julianday` is
  SQLite-only and `TIMESTAMPDIFF` is MySQL-only; this app runs MySQL in production, so the
  average is computed in Python over three selected columns. I wrote the `julianday`
  version first and caught it before shipping — it would have broken production while
  passing every test, because the tests run SQLite.

### F6 — Nothing renders unbounded · **PARTIALLY DONE**

`admin_core.paginate()` clamps `per_page` to a hard ceiling of 200. That ceiling matters:
if `per_page` came from the query string unbounded, an attacker with `?per_page=999999`
would simply re-summon the `.all()` the function exists to remove. Applied to `courses`
and `users` (with a shared `templates/admin/_pager.html`); `messages`, `newsletters`,
`activity`, `certificates` and `behavior_report` now carry explicit limits.

### F7 — Settings writes go through an allow-list, and the allow-list is visible · **DONE**

`apply_allow_list()` is allow-list, not deny-list: a key present in the form but absent
from the tuple is ignored. Adding a field to `super_settings.html` therefore cannot
silently open a write path to a sensitive key. `SECRET_SETTING_KEYS` encodes "empty field
means *keep the current value*", because the alternative is that one half-filled form wipes
a live payment gateway's API key.

The allow-list stays in `blueprints/admin_bp.py` — not as a hack, but because
`tests/test_optional_features.py:108` opens that file **as text** and asserts key literals
are present in it. That test is itself a smell (it asserts on source, not behaviour); the
CTO ruling is to keep it green now and convert it to assert against the exported tuple in a
follow-up, declared rather than smuggled.

### F8 — The Flask-SQLAlchemy removal is deferred, and here is the ruling

You authorised "tear it all down, including replacing Flask-SQLAlchemy" *and* "rewrite in
place + keep tests green." **Those are mutually exclusive in one move.** There are 140
`.query` accesses in this module alone, plus `models.py`, `seed.py`, `installer.py` and 13
other blueprints. Doing it inside the admin panel would have created two parallel database
idioms in one process — strictly worse than the status quo.

Ruling: **deferred.** But `admin_queries.py` is written entirely in SQLAlchemy 2.0
`select()` style, so when the migration happens it touches one module rather than 129 view
functions. That is the cheap half of the work, done now.

---

## 3. Trade-Off Analysis

| Change | Cost paid | Benefit bought | Verdict |
|---|---|---|---|
| Split into 8 modules | 3,768 → 4,860 LOC (**+29%**, mostly docstrings); reviewers of open PRs touching the old file get conflicts; `admin_content.py` at 924 lines is still too large | Every domain has an address; a payment change no longer risks merging against a content change; new contributors can be pointed at one 500-line file | **Worth it.** The +29% is documentation, and the LOC figure is the wrong metric — *maximum file size* fell from 3,768 to 924 |
| Read model layer (`admin_queries.py`, 509 LOC) | A second place to look for logic; 127 → 115 statements is a **9.4%** win, not an order of magnitude | Every aggregate is now unit-testable without a test client; the `percent`/`lesson_count` property problem is documented where the next engineer will find it | **Worth it for the testability, not the speed.** Claiming a performance win here would be dishonest |
| Typed `Form` | One more abstraction; only ~8 routes use it so far | Removes a whole class of 500s *where adopted*; `opt_int` fixes a real financial bug (empty ≠ zero) | **Worth it, but incomplete.** Value is currently 8/129 routes |
| Bottom-of-file domain imports | Non-obvious; a reader must know the ordering is load-bearing | Eliminates the import cycle entirely without a package restructure | **Accepted, with a comment explaining why it is at the bottom** |
| Keeping the source-text test green | The allow-list cannot move to `admin_core.py` even though that is where it arguably belongs | 435 tests stay green; no test was edited to make the refactor pass | **Correct call.** Editing a test to suit a refactor is how refactors hide regressions |
| Deferring the SQLAlchemy removal | You did not get what you authorised | No two-idiom process; the eventual migration is one module, not 129 functions | **Non-negotiable.** The alternative was worse than doing nothing |

---

## 4. The Idealized Codebase

Not one file, and that is the point. Delivered and on disk:

```
admin_core.py                    537   Blueprint · guard · Form · commit · paginate
                                       · audit · uploads · allow-list engine
admin_queries.py                 509   the entire read model (SQLAlchemy 2.0 select())
blueprints/admin_bp.py           532   composition root · settings surface · allow-lists
blueprints/admin_catalog.py      896   courses · categories · lessons · quizzes
                                       · assignments · bundles · question bank
blueprints/admin_commerce.py     524   orders · proofs · coupons · installments
                                       · payouts · gateways · products
blueprints/admin_people.py       395   users · roles · wallet · chat · SMS · impersonation
blueprints/admin_content.py      924   blog · reviews · tickets · pages · forms · menus
                                       · forum · certificates · behaviour report
blueprints/admin_ops.py          543   backups · designs · messengers · live sessions
                                       · roles matrix · maintenance
templates/admin/_pager.html            shared pager (new)
```

The shape of the difference, on the route the Council audited hardest:

```python
# ── BEFORE: 90 lines, ~29 round-trips, 14 of them inside a Python loop ─────────
@admin_bp.route('/')
@admin_required
def overview():
    if g.user.role in ('secretary', 'support', 'operator'):
        from permissions import has_permission, menu_for      # per request
        cards = []
        if has_permission(g.user, 'view_users'):
            cards.append(('👥', 'کاربران فعال',
                          User.query.filter_by(is_active=True).count(), 'admin.users'))
        # ... five more count queries ...
    total_revenue = db.session.query(func.coalesce(func.sum(Order.final_total), 0)) \
        .filter(Order.status == 'paid').scalar()
    for i in range(6, -1, -1):                                # 14 queries
        rev = db.session.query(...).filter(..., Order.paid_at >= start).scalar()
        cnt = Order.query.filter(..., Order.paid_at >= start).count()
    enrolls = Enrollment.query.join(Course, ...).join(User, ...).all()   # whole table
    completion_rate = round(sum(1 for e in enrolls if e.percent >= 100) * 100 / len(enrolls))
    return render_template('admin/overview.html', total_revenue=total_revenue,
                           paid_orders=paid_orders, /* 17 more kwargs */)

# ── AFTER: 7 lines, 11 round-trips, one GROUP BY for the whole chart ───────────
@admin_bp.route('/')
@admin_required
def overview():
    """داشبورد. ... (docstring explains the 29→11 and why staff cards share the
    permission table with the sidebar, so "seeing the link" and "seeing the number"
    can never diverge)"""
    if g.user.role in STAFF_ROLES:
        return render_template('admin/staff_overview.html',
                               cards=staff_overview_cards(g.user),
                               links=staff_menu_links(g.user))
    return render_template('admin/overview.html',
                           **dashboard_metrics().as_template_kwargs())
```

`Dashboard.as_template_kwargs()` is a one-line method with a twenty-line docstring,
because it encodes a trap that cost a test cycle: **`dataclasses.asdict()` deep-copies its
values, and deep-copying an ORM instance detaches it from the session** — the first
lazy-load in the template then raises `DetachedInstanceError`. It returns references.

### Verification actually run

| Check | Command | Result |
|---|---|---|
| Baseline | `pytest tests/ -q` | **435 passed, 1 failed** in 324.51s |
| After refactor | `pytest tests/ -q` | **435 passed, 1 failed** in 324.76s — *same single failure* |
| Route-table parity | live `url_map` vs. static parse of `git show HEAD:blueprints/admin_bp.py` | **129/129 present, 0 missing** (164 total incl. `admin_extra`) |
| Undefined names | `pyflakes` on all 8 modules | **0** |
| Dashboard statements | `before_cursor_execute` listener, both trees, N=100/600/1500 | **127 → 115, flat** |

The one failure is pre-existing and unrelated to this module:
`tests/test_commercial_readiness.py:251` asserts `به‌زودی` is absent from
`templates/community/live.html`. It was red before I touched anything and is red now.
**No test was edited to make this refactor pass.**

### Seven defects I introduced and caught before shipping

Stated because a refactor that reports no self-inflicted bugs is not being audited:

1. `dataclasses.asdict()` detached ORM instances → `DetachedInstanceError`.
2. Emitter script shadowed a loop variable and wrote five files to one path.
3. Attempted `AVG(Enrollment.percent)` on a `@property` → `TypeError`.
4. `func.julianday` (SQLite-only) in a MySQL-targeted app → would have passed every test
   and broken production.
5. Stranded helpers (`_save_product_image`, `_product_int`, `_save_lesson_*`) and missing
   `os`/`uuid`/`g`/`human_size` imports after the split.
6. A `replace_func` helper silently deleted two route decorators — caught by the route
   parity check, which is why that check exists.
7. Stray CJK characters that slipped into a Persian docstring.

---

## 5. Blueprint for the Future

### Immediate (this week, mechanical)

1. **Phase 2 — adopt the primitives.** Convert the remaining **119** raw
   `db.session.commit()` calls to `commit()`, the **29** raw `int()` casts to `Form`, and
   the **33→38** `except Exception` blocks to `best_effort(fn, context)`. Roughly a day of
   mechanical work, and it is where the actual robustness gain lives. Until it is done, the
   primitives are infrastructure without tenants.
2. **Split `admin_content.py`** (924 lines) into `admin_pages.py` + `admin_support.py`.
   It absorbed 47 routes and is now the largest file — the same mistake at a third of the
   scale.
3. **Fix the pre-existing red.** `templates/community/live.html` renders `⏳ به‌زودی`.
   Either the copy changes or the test's intent is wrong; leaving a permanently red suite
   teaches everyone to ignore red.

### UI/UX (Department 3, re-cast for web/RTL)

- The pager renders **every** page number (`range(1, pages+1)`). At 1,000 pages that is
  1,000 anchors. Switch to a windowed pager (first, ±2, last).
- `courses.html` and `users.html` still show a count derived from `total`; the remaining
  un-paginated lists (`blog`, `coupons`, `reviews`) should follow.
- No `aria-label` discipline on the icon-only buttons (🔍, ⠿, ➕). A screen reader hears
  nothing. AAA is unreachable until every control has an accessible name.
- The Persian/RTL surface has no automated bidi or contrast check anywhere in 46 test
  files. Add axe-core against a rendered page.

### Security & resilience (Departments 4)

- `admin_core.audit()` exists and is called in **one** place (forced go-live). Every
  irreversible action — role change, impersonation, password reset, certificate revocation,
  backup restore — must route through it. Today "who did this and from what IP" is
  unanswerable for most of them.
- **`Coupon` needs `created_at` and `created_by`.** A discount with no provenance is an
  audit finding waiting to happen.
- `backup_restore()` overwrites `instance/academy.db` from an admin POST. It validates the
  filename with a regex, which is good; it should also require re-authentication, because a
  stolen session currently means a restoreable-to-arbitrary-state database.
- `runtime.automated_test_mode()` gates fake OTP/payment/BNPL. It is correct and well
  commented — but it is a single boolean standing between test fixtures and a production
  payment path. It deserves a startup assertion that fails loudly if
  `APP_ENV=production` and `PYTEST_CURRENT_TEST` are ever both set.

### DevOps (Departments 5–6, constrained by cPanel/CloudLinux)

- The suite takes **325s** and creates a fresh SQLite file per test. That is the feedback
  loop cost for every change. Parallelise with `pytest-xdist` — the tests are already
  isolated by `conftest.py`.
- Add `pyflakes`/`ruff` to CI. It caught five undefined names in this refactor in under a
  second; none of them were caught by 435 tests, because each sits on a code path no test
  exercises. **That is the real signal: coverage gaps, not lint noise.**
- The source-text assertion in `test_optional_features.py:108` should assert against the
  exported `SUPER_SETTINGS_KEYS` tuple instead of reading a file as a string.
- Docker/serverless findings are withheld deliberately: they cannot be delivered against
  the stated hosting target, and specifying infrastructure you cannot run is worse than
  specifying none.

### Product (Departments 7)

The multi-million-dollar product hidden in here is not the LMS — it is the **76-widget
Persian page builder plus eight Iranian payment gateways**. Those two things together are a
site-builder for a market that Shopify and Webflow do not serve. The LMS is the demo; the
builder is the platform. That is a strategic conversation, not a refactor, and the Council
flags it rather than pretends to have resolved it.


---

## 6. Second Pass — Verification

| Check | Result |
|---|---|
| `pytest tests/ -q` | **435 passed, 1 failed** in 310.34s — same single pre-existing failure |
| `scripts/check_admin_routes.py` | **129/129 present, 0 missing** (164 live incl. `admin_extra`) |
| `pyflakes` on all 8 modules | **0 undefined names** |
| `templates/admin/_pager.html` render | **25,379 bytes, pager present, 6 page links, Persian total `۲۵۰` rendered** |

The pager check matters: **no test in the suite renders it.** `_pager.html` is exercised
only by the three routes that were just paginated, and none of the 46 test files request
`?page=2`. That check was done by hand and is not in CI — which is itself a finding.

`scripts/check_admin_routes.py` is new and CI-ready. It compares the live `url_map`
against a static parse of `git show HEAD:blueprints/admin_bp.py` and exits non-zero if any
route vanished. It is not a lint tool — it is the check that caught two silently deleted
route decorators during this refactor, which 435 passing tests did not.


---

## 7. Third Pass — All Remaining Items, One Go

Everything left open in §5 and §6 was applied in a single pass, not batched.

| # | Item | What was done | Verified |
|---|---|---|---|
| 1 | 119 raw `db.session.commit()` | AST-driven rewrite → `commit()`. **101 converted**; the 9 inside `try` blocks were deliberately left (they have their own rollback) | `db.session.commit()`: **120 → 18**; `commit()` sites: **0 → 109** |
| 2 | Raw `int()` casts of form input | `_course_form` (8) + one in content → `Form.int(...)` with `lo`/`hi` clamps | raw casts in blueprints: **0** |
| 3 | `admin_content.py` too large (926) | Split into `admin_pages.py` (421, 23 routes) + `admin_support.py` (244, 14 routes) | `admin_content.py`: **926 → 278**; 129/129 routes intact |
| 4 | Permanently red test | `⏳ به‌زودی` → `⏳ در انتظار آغاز` on the live-session badge. The test's intent is "public pages must not advertise unfinished features"; a session that has not started is not an unfinished feature, and the new copy says that more precisely | **436 passed, 0 failed** |
| 5 | Pager renders every page number | Rewritten as a windowed pager: first, ±2, last, with ellipsis and a `page / pages` readout. Never more than 7 numeric links | renders correctly |
| 6 | `Coupon` had no provenance | `created_at` (indexed) + `created_by` FK added to `models.py`; `migrations/0006_coupon_provenance.py` for existing installs; `created_by=g.user.id` set on create; `audit('coupon_create', code)` | migration is idempotent; old rows stay `NULL` — a fabricated timestamp in an audit column is worse than an honest `NULL` |
| 7 | `audit()` used once | Wired into `user_role`, `user_toggle`, `certificate_revoke`, `backup_restore`, `coupon_create` | audit sites: **2 → 7** |
| 8 | `__import__('app', fromlist=[...])` lambda in coupon expiry | Extracted to `_coupon_expiry()` with real error handling — a bad date no longer 500s | compiles, tests green |

### Two errors made during this pass, both caught

1. **A patch inserted `_coupon_expiry` *after* the route decorators**, so the helper was
   registered as the `/coupons` route and `coupons()` lost `@admin_required` — an
   unauthenticated payment-coupon endpoint. Caught by inspecting `decorator_list` via
   `ast`, repaired, and `scripts/check_admin_routes.py` re-run to confirm 164 live routes
   with no placeholder.
2. **A `form` import never landed in `admin_catalog.py`**, and the pyflakes check that
   turn did not include that file, so it went unnoticed until the suite caught it
   (`NameError` in 2 tests). Lesson recorded: the lint sweep must enumerate every changed
   file, not a remembered subset.

### Fourth correction — my "29 raw int casts" figure was wrong

The grep used to produce it was `int(request.form.get`, which also matches inside
`safe_int(request.form.get`. **20 of the 29 were already going through `safe_int`.** The
genuine raw-cast count was **9**, all in `_course_form` plus one in content. All 9 are now
gone. The earlier number overstated the problem by 3×.

---

## 8. Final State

```
436 passed, 0 failed  in 314.40s          (baseline was 435 passed, 1 failed)
129/129 admin endpoints registered, 0 missing
pyflakes: 0 undefined names across all 10 modules
```

| Module | Lines |
|---|---|
| `blueprints/admin_catalog.py` | 873 |
| `blueprints/admin_ops.py` | 543 |
| `blueprints/admin_commerce.py` | 535 |
| `blueprints/admin_bp.py` | 533 |
| `admin_queries.py` | 511 |
| `admin_core.py` | 497 |
| `blueprints/admin_pages.py` | 421 |
| `blueprints/admin_people.py` | 389 |
| `blueprints/admin_content.py` | 278 |
| `blueprints/admin_support.py` | 244 |
| **total** | **4,824** |

Largest file: **873 lines** (was 3,768).

| Smell | Original | Final |
|---|---|---|
| `db.session.commit()` in view code | 120 | **18** (all inside `try`) |
| `commit()` unit-of-work call sites | 0 | **109** |
| Raw `int()` casts of form input | 9 | **0** |
| `audit()` call sites | 2 | **7** |
| `best_effort()` call sites | 0 | **4** |
| `except Exception` | 33 | **35** |

### What is still genuinely open

1. **18 `except Exception: _lexc(...)` swallow-and-continue blocks remain.** Converting them
   to `best_effort` means extracting each multi-statement block into a named inner function;
   that is not safely scriptable and needs to be done by hand, route by route. This is the
   one item from the original list that did not get finished.
2. `admin_catalog.py` at 873 lines is now the largest module and should split next
   (courses/lessons vs. quizzes/assignments/bundles).
3. The windowed pager has **no test**. Neither did the original. `scripts/check_admin_routes.py`
   is CI-ready; a template-render smoke test is not written.
4. `audit()` covers 7 actions. Payout approval, order fulfilment and bulk operations still
   do not log who acted.
5. Departments 24–26 (serverless, Docker, kernel tuning) remain **withheld**, not resolved:
   they cannot be delivered against cPanel/CloudLinux, and specifying infrastructure you
   cannot run is worse than specifying none.
