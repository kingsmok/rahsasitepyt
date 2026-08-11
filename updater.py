# -*- coding: utf-8 -*-
"""
بروزرسانی خودکار نرم‌افزار از گیت — دکمه «بروزرسانی» در تنظیمات

فلوی کار:
  1) git fetch از ریموت (آدرس از Setting: git_repo_url یا .env: GIT_REPO_URL)
  2) git reset --hard به آخرین کامیت ریموت (جایگزینی کامل کدها)
  3) مایگریشن دیتابیس: ساخت جدول‌های جدید + ستون‌های جدید (سبک)
  4) گزارش نتیجه

ایمنی:
  - فقط super_admin (در بلوپرینت چک می‌شود)
  - فایل‌های محلی (instance/, .env, logs/) هرگز دست نمی‌خورند (در .gitignore)
  - اجرا در پس‌زمینه با state فایلی (مثل نصب‌کننده) — ضد Request Timeout
"""
import json
import os
import subprocess
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, 'instance', '.update_progress.json')
STALE_SECONDS = 300  # ۵ دقیقه بدون پیشرفت = قطع شد

_state = {
    'status': 'idle',   # idle | running | done | error
    'step': 0,
    'steps': 4,
    'msg': '',
    'ok': False,
    '_updated': 0,
}
_lock = threading.Lock()


def _save():
    global _state
    _state['_updated'] = time.time()
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_state, f, ensure_ascii=False)
    except Exception:
        pass


def _load():
    global _state
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            data = json.load(f)
        with _lock:
            _state.update(data)
    except Exception:
        pass


def get_repo_url():
    """آدرس ریموت گیت: اول تنظیم دیتابیس، بعد .env"""
    try:
        from models import Setting
        st = Setting.query.filter_by(key='git_repo_url').first()
        if st and st.value:
            return st.value.strip()
    except Exception:
        pass
    return os.environ.get('GIT_REPO_URL', '').strip()


def update_progress():
    _load()
    with _lock:
        st = dict(_state)
    st.pop('_updated', None)
    st['stale'] = False
    if st.get('status') == 'running' and time.time() - _state.get('_updated', 0) > STALE_SECONDS:
        st['status'] = 'error'
        st['stale'] = True
        st['msg'] = 'بروزرسانی قطع شد (سرور درخواست را متوقف کرد) — دوباره تلاش کنید.'
    return st


def _run(cmd, cwd=BASE_DIR, timeout=120):
    """اجرای دستور و برگرداندن (returncode, stdout)"""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return -1, 'timeout'
    except Exception as e:
        return -2, str(e)


def _git_remote():
    """آدرس ریموت فعلی git — یا از تنظیمات"""
    url = get_repo_url()
    if url:
        return url
    code, out = _run(['git', 'remote', 'get-url', 'origin'])
    return out.strip() if code == 0 else ''


def get_git_info():
    """اطلاعات کامل گیت مخزن فعلی برای پنل مدیریت نصب و اتصال"""
    branch = _current_branch()
    remote = _git_remote()
    code, out = _run(['git', 'log', '-1', '--pretty=format:%h|%s|%ci'])
    commit_hash, commit_msg, commit_date = '', '', ''
    if code == 0 and '|' in out:
        parts = out.strip().split('|', 2)
        commit_hash = parts[0] if len(parts) > 0 else ''
        commit_msg = parts[1] if len(parts) > 1 else ''
        commit_date = parts[2] if len(parts) > 2 else ''
    return {
        'branch': branch,
        'remote': remote,
        'commit_hash': commit_hash,
        'commit_msg': commit_msg,
        'commit_date': commit_date,
    }




def test_git_repo(url):
    """تست اتصال به مخزن گیت (عمومی یا خصوصی) از طریق git ls-remote"""
    if not url:
        return False, 'آدرس مخزن گیت خالی است'
    code, out = _run(['git', 'ls-remote', url, 'HEAD'], timeout=15)
    if code == 0:
        return True, 'اتصال به مخزن گیت موفقیت‌آمیز بود ✅ (دسترسی برقرار است)'
    msg = out.strip()[-200:]
    if 'Authentication failed' in msg or 'could not read Username' in msg or 'Permission denied' in msg:
        return False, ('خطای دسترسی/احراز هویت: برای مخازن خصوصی (Private) باید از آدرس همراه با توکن '
                       '(https://TOKEN@github.com/user/repo.git) یا کلید SSH استفاده کنید.')
    return False, 'خطا در اتصال به مخزن: ' + msg


def _log_history(repo, mig_msg):
    """ثبت گزارش بروزرسانی در instance/update_history.json (حداکثر ۲۰ مورد)"""
    try:
        logf = os.path.join(BASE_DIR, 'instance', 'update_history.json')
        rows = []
        try:
            with open(logf, encoding='utf-8') as f:
                rows = json.load(f)
        except Exception:
            rows = []
        from datetime import datetime, UTC as _UTC
        rows.insert(0, {
            'at': datetime.now(_UTC).isoformat(),
            'repo': repo,
            'migration': mig_msg,
        })
        rows = rows[:20]
        os.makedirs(os.path.dirname(logf), exist_ok=True)
        with open(logf, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def start_update():
    """شروع بروزرسانی در پس‌زمینه — خروجی (started, msg)"""
    global _state
    _load()
    with _lock:
        if _state.get('status') == 'running' and \
                time.time() - _state.get('_updated', 0) < STALE_SECONDS:
            return False, 'بروزرسانی دیگری در حال اجراست — کمی صبر کنید.'
        _state = {'status': 'running', 'step': 0, 'steps': 4,
                  'msg': 'شروع بروزرسانی...', 'ok': False, '_updated': time.time()}
    _save()

    def _work():
        try:
            repo = _git_remote()
            if not repo:
                with _lock:
                    _state['status'] = 'error'
                    _state['msg'] = ('آدرس مخزن گیت تنظیم نشده است! '
                                     'از «تنظیمات سوپر → گیت» آدرس را وارد کنید.')
                _save()
                return

            # ۱) fetch
            _set_step(1, 'دریافت آخرین نسخه از گیت...')
            code, out = _run(['git', 'fetch', 'origin'])
            if code != 0:
                raise RuntimeError('git fetch شکست خورد: ' + out[-300:])

            # ── گارد ایمنی: مطمئن شو ریموت واقعاً همین پروژه است ──
            # اگر ریموت اشتباه/خالی باشد، reset --hard کل پروژه را نابود می‌کند
            branch = _current_branch()
            _set_step(2, 'بررسی صحت مخزن...')
            code, out = _run(['git', 'ls-tree', '-r', '--name-only', f'origin/{branch}'])
            if code != 0:
                raise RuntimeError('امکان بررسی مخزن ریموت نیست: ' + out[-200:])
            remote_files = set(out.splitlines())
            required = ('app.py', 'models.py', 'passenger_wsgi.py')
            missing = [f for f in required if f not in remote_files]
            if missing:
                raise RuntimeError(
                    '⚠️ مخزن ریموت این پروژه نیست! فایل‌های ضروری '
                    f'({"، ".join(missing)}) در آن وجود ندارد. '
                    'بروزرسانی متوقف شد تا پروژه نابود نشود. '
                    'آدرس مخزن را در «تنظیم مخزن» اصلاح کنید.')

            # ۲) جایگزینی کامل کدها (reset --hard به آخرین کامیت ریموت)
            _set_step(2, 'جایگزینی کدها با آخرین نسخه...')
            code, out = _run(['git', 'reset', '--hard', f'origin/{branch}'])
            if code != 0:
                raise RuntimeError('git reset شکست خورد: ' + out[-300:])

            # ۳) مایگریشن دیتابیس
            _set_step(3, 'مایگریشن دیتابیس...')
            mig_msg = _migrate_db()

            # ۴) پاک‌سازی کش پایتون
            _set_step(4, 'پاک‌سازی کش‌ها...')
            _run(['find', BASE_DIR, '-name', '__pycache__', '-type', 'd',
                  '-exec', 'rm', '-rf', '{}', '+'], timeout=60)

            with _lock:
                _state['status'] = 'done'
                _state['ok'] = True
                _state['step'] = 4
                _state['msg'] = ('بروزرسانی کامل شد ✅ — کدها به آخرین نسخه گیت '
                                 'جایگزین شدند. برای اعمال کامل، ری‌استارت سرور '
                                 'پیشنهاد می‌شود (touch passenger_wsgi.py). ' + mig_msg)
            _save()
            _log_history(repo, mig_msg)
        except Exception as e:
            with _lock:
                _state['status'] = 'error'
                _state['ok'] = False
                _state['msg'] = 'خطا در بروزرسانی: ' + str(e)[:300]
            _save()

    threading.Thread(target=_work, daemon=True).start()
    return True, 'بروزرسانی در پس‌زمینه شروع شد'


def _set_step(step, msg):
    with _lock:
        _state['step'] = step
        _state['msg'] = msg
    _save()


def _current_branch():
    code, out = _run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    return out.strip() if code == 0 else 'main'


def _migrate_db():
    """مایگریشن سبک: ساخت جدول‌های جدید + ستون‌های جدید در جدول‌های موجود
    (مناسب SQLite و MySQL — ALTER فقط برای ستون‌های ازدست‌رفته)
    """
    from models import db
    try:
        db.create_all()  # جدول‌های جدید
        # ستون‌های جدید در جدول‌های موجود
        from sqlalchemy import inspect as _insp
        insp = _insp(db.engine)
        added = 0
        for table in db.metadata.sorted_tables:
            existing = {c['name'] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing and not col.primary_key:
                    try:
                        from sqlalchemy import text as _t
                        coltype = col.type.compile(dialect=db.engine.dialect)
                        db.session.execute(_t(
                            f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'
                            if db.engine.dialect.name == 'sqlite' else
                            f'ALTER TABLE `{table.name}` ADD COLUMN `{col.name}` {coltype}'
                        ))
                        db.session.commit()
                        added += 1
                    except Exception:
                        db.session.rollback()
        return f'({added} ستون جدید اضافه شد)' if added else '(جدول‌ها به‌روز هستند)'
    except Exception as e:
        return '(خطا در مایگریشن: ' + str(e)[:150] + ')'
