# -*- coding: utf-8 -*-
"""سیستم امن و قابل‌اعتماد بروزرسانی برنامه از Git/GitHub.

این ماژول دو کار جدا را انجام می‌دهد:

* دریافت نسخهٔ جدید کد از GitHub (به‌صورت دستی از پنل یا خودکار از Webhook).
* همگام‌سازی ساختار دیتابیس با مدل‌های نسخهٔ جدید، بدون حذف داده‌های قبلی.

استراتژی دو مسیره:

* سایت نصب‌شده از ZIP سی‌پنل (بدون پوشهٔ ``.git``) → **مسیر آرشیو**: آرشیو ZIP
  شاخهٔ مقصد از GitHub دانلود و فایل‌هایش روی سایت overlay می‌شود؛ اصلاً به git
  وابسته نیست و روی هاست‌های اشتراکی که git ندارند یا شبکهٔ git آن‌ها بسته است
  هم کار می‌کند. فایل‌های محلی (.env، آپلودها، بکاپ‌ها، .htaccess) هرگز لمس
  نمی‌شوند.
* پوشه‌ای که واقعاً مخزن git است (توسعه/CI) → **مسیر Git** (fetch + reset).

نسخهٔ محلی در نصب‌های ZIP از ``version.txt`` و ``instance/.update_commit``
خوانده می‌شود، بنابراین «نسخهٔ محلی پیدا نشد» دیگر اتفاق نمی‌افتد.

نکتهٔ مهم: مایگریشن در یک پردازش جدا اجرا می‌شود. چون بعد از جایگزینی کدها
ماژول‌های پایتونِ پردازش وب هنوز نسخهٔ قدیمی را در حافظه دارند، اجرای مایگریشن
در همان Thread باعث می‌شد ستون‌های نسخهٔ جدید اصلاً دیده نشوند.
"""
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _timezone
    UTC = _timezone.utc

try:  # فقط روی لینوکس لازم است؛ روی ویندوز قفل درون‌پردازشی استفاده می‌شود.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - مخصوص ویندوز
    _fcntl = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(BASE_DIR, '.env'))
except Exception:
    pass
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
STATE_FILE = os.path.join(INSTANCE_DIR, '.update_progress.json')
HISTORY_FILE = os.path.join(INSTANCE_DIR, 'update_history.json')
LOCK_FILE = os.path.join(INSTANCE_DIR, '.update.lock')
APPLIED_COMMIT_FILE = os.path.join(INSTANCE_DIR, '.update_commit')
MANIFEST_FILE = os.path.join(INSTANCE_DIR, '.update_manifest.json')
VERSION_FILE = os.path.join(BASE_DIR, 'version.txt')
MIGRATIONS_DIR = os.environ.get(
    'MIGRATIONS_DIR', os.path.join(BASE_DIR, 'migrations'))


def _env_int(name, default, minimum=None, maximum=None):
    """خواندن عدد صحیح از محیط با fallback امن؛ خطای مقدار فقط برای کاربری که
    خودش متغیر را دستی تنظیم کرده است معنی دارد، پس silently به default برمی‌گردد."""
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def _env_flag(name, default='1'):
    return str(os.environ.get(name, str(default))).strip().lower() \
        not in ('0', 'false', 'no', 'off')


# اگر heartbeat (به‌روزرسانی زمان ``_updated``) بیش از این مدت قطع بماند و قفلِ
# زنده‌ای هم دیده نشود، بروزرسانی «متوقف‌شده» اعلام می‌شود. مایگریشن دیتابیس‌های
# بزرگ ممکن است چند دقیقه طول بکشد؛ مقدار پیش‌فرض ۳۰ دقیقه و قابل تنظیم است.
STALE_SECONDS = _env_int('UPDATE_STALE_SECONDS', 1800, 60, 86400)
HEARTBEAT_SECONDS = _env_int('UPDATE_HEARTBEAT_SECONDS', 10, 2, 120)
UPDATE_REF_PREFIX = 'refs/remotes/academy-update'
_REQUIRED_FILES = ('app.py', 'models.py', 'passenger_wsgi.py', 'requirements.txt')
_PRESERVE_FILES = ('instance/.update_progress.json', 'instance/update_history.json',
                   'instance/.update_commit', 'instance/.update_manifest.json')
_BRANCH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')
# فایل‌ها/پوشه‌هایی که هرگز از آرشیو بروزرسانی روی سایت کپی نمی‌شوند و
# هرگز حذف هم نمی‌شوند: .env، آپلودها، بکاپ‌ها، .htaccess، venv و لاگ‌ها.
_OVERLAY_SKIP = {
    '.env', '.env.local', '.htaccess', '.git', '.gitignore',
    'instance', 'uploads', 'backups', 'backup', 'venv', '.venv', 'env', 'logs',
    '__pycache__', 'node_modules', 'releases',
}
# مانیفست فایل‌هایی که خودِ بروزرسان روی سایت نوشته است؛ برای حذف امن
# فایل‌های حذف‌شده در نسخهٔ جدید و هرگز دست‌نزدن به فایل‌های دستی کاربر.
_MANIFEST_MAX_FILES = 50000
_GIT_CANDIDATES = (
    '/usr/bin/git',
    '/usr/local/bin/git',
    '/usr/local/cpanel/3rdparty/bin/git',
    '/opt/cpanel/ea-git/bin/git',
    '/opt/git/bin/git',
)
_git_path = None

_state = {
    'status': 'idle',   # idle | running | done | error
    'step': 0,
    'steps': 4,
    'msg': '',
    'ok': False,
    '_updated': 0,
}
_state_lock = threading.RLock()
_fallback_process_lock = threading.Lock()


class UpdateError(RuntimeError):
    """خطای قابل‌نمایش در پنل بروزرسانی."""


def _save():
    """ذخیرهٔ اتمیک وضعیت؛ polling در Worker دیگری JSON نیمه‌نوشته نمی‌خواند."""
    with _state_lock:
        _state['_updated'] = time.time()
        snapshot = dict(_state)
    tmp = None
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        tmp = '{}.{}.{}.tmp'.format(STATE_FILE, os.getpid(), threading.get_ident())
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, STATE_FILE)
    except Exception:
        # خراب شدن فایل گزارش نباید خود عملیات بروزرسانی را متوقف کند.
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _load():
    global _state
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            with _state_lock:
                _state.update(data)
    except (OSError, ValueError, TypeError):
        pass


def _set_state(**values):
    with _state_lock:
        _state.update(values)
    _save()


def _lock_pid():
    """PID فرایندی که قفل بروزرسانی را نگه داشته؛ اگر قفل آزاد باشد None."""
    try:
        with open(LOCK_FILE, encoding='utf-8') as f:
            raw = (f.read() or '').strip()
        return int(raw)
    except (OSError, ValueError, TypeError):
        return None


def _pid_alive(pid):
    """آیا فرایند با این PID هنوز زنده است؟ (بدون وابستگی به ps)"""
    if not pid or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:  # pragma: no cover - دفاعی
        return False


def update_progress():
    """وضعیت فعلی بروزرسانی را از فایل مشترک برمی‌گرداند.
    
    این تابع توسط polling فرانت‌اند فراخوانی می‌شود. اگر heartbeat مدتی قطع شده
    باشد اما فرایندِ نگه‌دارندهٔ قفل همچنان زنده باشد، بروزرسانی «متوقف‌شده»
    اعلام نمی‌شود — فقط «مرحلهٔ طولانی» گزارش می‌شود. پیام قدیمیِ
    «بروزرسانی متوقف شده است» فقط وقتی می‌آید که واقعاً هیچ فرایند زنده‌ای
    قفل را نگه نداشته باشد.
    """
    _load()
    with _state_lock:
        st = dict(_state)
    st.pop('_updated', None)
    st['stale'] = False
    updated = float(st.get('_updated') or 0)
    if st.get('status') == 'running' and time.time() - updated > STALE_SECONDS:
        pid = _lock_pid()
        if _pid_alive(pid):
            # heartbeat قطع شده اما خود فرایند زنده است (pip/دانلود طولانی).
            # زمان را تمدید می‌کنیم تا polling‌های بعدی دوباره خطا ندهند.
            st['long_running'] = True
            st['msg'] = ('بروزرسانی همچنان در حال اجراست؛ مرحلهٔ فعلی طولانی است '
                         '(PID {}). صبر کنید...').format(pid)
            _set_state(msg=st['msg'])
        else:
            st['status'] = 'error'
            st['ok'] = False
            st['stale'] = True
            st['msg'] = 'بروزرسانی متوقف شده است — دوباره تلاش کنید.'
            _set_state(status='error', ok=False, msg=st['msg'])
    
    # اگر وضعیت idle است، آخرین نتیجه را برگردان
    if st.get('status') == 'idle':
        report = st.get('report', {})
        if report:
            st['msg'] = report.get('migration', '') or 'آماده برای بروزرسانی'
    
    return st


def _heartbeat():
    """به‌روزرسانی زمان آخرین فعالیت در state مشترک — بدون تغییر پیام.

    در گام‌های طولانی (دانلود، pip، مایگریشن) هر چند ثانیه صدا زده می‌شود تا
    تشخیص «توقف» هرگز false positive ندهد.
    """
    try:
        _save()
    except Exception:
        pass


def _git_env():
    env = os.environ.copy()
    # روی هاست، git نباید وسط درخواست منتظر Username/Password بماند.
    env['GIT_TERMINAL_PROMPT'] = '0'
    env.setdefault('LC_ALL', 'C')
    # ویندوز cp1252 و بعضی هاست‌ها locale ASCII دارند؛ چاپ فارسی در
    # migrate_database / pip نباید UnicodeEncodeError بدهد.
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    return env


def _find_git():
    """مسیر واقعی git؛ روی سی‌پنل گاهی در PATH اپ Passenger نیست."""
    global _git_path
    if _git_path:
        return _git_path
    candidates = []
    which = shutil.which('git')
    if which:
        candidates.append(which)
    candidates.extend(_GIT_CANDIDATES)
    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        try:
            r = subprocess.run([path, '--version'], capture_output=True, text=True,
                               timeout=8, env=_git_env())
            text = ((r.stdout or '') + (r.stderr or '')).lower()
            if r.returncode == 0 and 'git' in text:
                _git_path = path
                return path
        except Exception:
            continue
    _git_path = 'git'
    return _git_path


def _git(args, timeout=120):
    """اجرای git با safe.directory تا مالکیت مشکوک روی هاست جلوی دستور را نگیرد."""
    cmd = [_find_git(), '-c', 'safe.directory=' + BASE_DIR]
    cmd.extend(args)
    return _run(cmd, timeout=timeout)


def _is_git_worktree():
    code, out = _git(['rev-parse', '--is-inside-work-tree'], timeout=15)
    return code == 0 and out.strip() == 'true'


def _ensure_local_git():
    """اگر سایت از ZIP سی‌پنل نصب شده باشد، مخزن محلی را می‌سازد تا fetch ممکن شود."""
    if _is_git_worktree():
        return True
    code, _out = _git(['init'], timeout=30)
    if code != 0:
        return False
    _git(['config', 'user.email', 'update@localhost'], timeout=10)
    _git(['config', 'user.name', 'Academy Updater'], timeout=10)
    return _is_git_worktree()


def _read_applied_commit():
    try:
        with open(APPLIED_COMMIT_FILE, encoding='utf-8') as f:
            raw = (f.read() or '').strip()
        value = raw.split()[0] if raw else ''
    except OSError:
        return ''
    if value and re.fullmatch(r'[0-9a-fA-F]{7,40}', value):
        return value.lower()
    return ''


def _read_version_txt():
    """نسخهٔ انتشار از ``version.txt`` — در نصب‌های ZIP تنها مرجع نسخه است."""
    try:
        with open(VERSION_FILE, encoding='utf-8') as f:
            value = (f.read() or '').strip().splitlines()
        value = value[0].strip() if value else ''
    except OSError:
        return ''
    if value and len(value) <= 64:
        return value
    return ''


def _version_label(version_txt, commit=''):
    """برچسب قابل‌نمایش نسخه: شماره انتشار، وگرنه هش کوتاه کامیت."""
    version_txt = (version_txt or '').strip()
    if version_txt:
        return version_txt
    commit = (commit or '').strip()
    return commit[:10] if commit else ''


_ENV_LINE_RE = re.compile(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')


def _read_env_file_value(name, env_path=None):
    """خواندن یک کلید از ``.env`` بدون وابستگی به python-dotenv.

    اگر dotenv لود نشده باشد (ویندوز/هاست ناقص)، ``DATABASE_URL`` نباید
    گم شود و مایگریشن اشتباهاً روی SQLite پیش‌فرض برود.
    """
    path = env_path or os.path.join(BASE_DIR, '.env')
    try:
        with open(path, encoding='utf-8') as handle:
            lines = handle.readlines()
    except OSError:
        return ''
    found = ''
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match or match.group(1) != name:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        found = value
    return found


def _database_url():
    """آدرس دیتابیس: محیط، سپس ``.env`` — همان منبعی که Flask استفاده می‌کند."""
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if url:
        return url
    return (_read_env_file_value('DATABASE_URL') or '').strip()


def _database_kind(url=None):
    value = (url if url is not None else _database_url()).strip().lower()
    if value.startswith('mysql'):
        return 'mysql'
    if value.startswith('postgres'):
        return 'postgresql'
    if value.startswith('sqlite') or not value:
        return 'sqlite'
    return 'other'


def _python_child_env():
    """محیط پردازش‌های پایتونِ بروزرسانی (مایگریشن / تست سلامت)."""
    env = _git_env()
    env['PYTHONPATH'] = BASE_DIR + os.pathsep + env.get('PYTHONPATH', '')
    db_url = _database_url()
    if db_url:
        env['DATABASE_URL'] = db_url
    return env


def _local_version():
    """هش نسخهٔ فعلی: HEAD گیت یا آخرین commit اعمال‌شده از بروزرسانی ZIP."""
    return _current_commit('HEAD') or _read_applied_commit()


def _local_version_info():
    """اطلاعات کامل نسخهٔ محلی برای صفحهٔ پنل و «بررسی نسخهٔ جدید».

    در نصب ZIP (بدون .git) commit خالی است ولی ``version.txt`` همیشه هست؛
    بنابراین تشخیص قدیمی‌بودن نسخه بدون مخزن محلی هم ممکن می‌شود.
    """
    commit = _local_version()
    version_txt = _read_version_txt()
    kind = 'git' if commit and _is_git_worktree() else (
        'zip' if version_txt or commit else 'unknown')
    return {
        'kind': kind,
        'commit': commit,
        'commit_short': commit[:10] if commit else '',
        'version_txt': version_txt,
        'label': version_txt or (commit[:10] if commit else ''),
    }


def _write_applied_commit(commit):
    commit = (commit or '').strip()
    if not commit:
        return
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        with open(APPLIED_COMMIT_FILE, 'w', encoding='utf-8') as f:
            f.write(commit + '\n')
    except OSError:
        pass


def _redact_text(value, repo=''):
    """حذف توکن/رمز از خروجی git و پیام‌های ذخیره‌شده."""
    text = str(value or '')
    if repo:
        text = text.replace(repo, _display_repo(repo))
    # پوشش URLهای HTTPS مثل https://TOKEN@github.com/owner/repo.git
    text = re.sub(r'(?i)(https?://)([^/@\s]+)@', r'\1***@', text)
    # بعضی پیام‌های git آدرس SSH را کامل نشان می‌دهند؛ SSH معمولاً رمز داخل URL ندارد.
    return text


def _display_repo(url):
    """نسخهٔ قابل نمایش آدرس مخزن؛ اطلاعات احراز هویت هرگز به مرورگر/تاریخچه نمی‌رود."""
    url = str(url or '').strip()
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme in ('http', 'https') and parsed.netloc:
            host = parsed.hostname or parsed.netloc
            if parsed.port:
                host += ':' + str(parsed.port)
            auth = '***@' if parsed.username or parsed.password else ''
            return urllib.parse.urlunsplit((parsed.scheme, auth + host,
                                            parsed.path, parsed.query, parsed.fragment))
    except Exception:
        # حتی URL خراب هم نباید credential خام را برگرداند.
        return re.sub(r'(?i)(https?://)([^/@\s]+)@', r'\1***@', url)
    return re.sub(r'(?i)(https?://)([^/@\s]+)@', r'\1***@', url)


def _setting_value(key):
    """خواندن تنظیم دیتابیس، با fallback امن برای Thread/CLI بدون app context."""
    try:
        from models import Setting
        st = Setting.query.filter_by(key=key).first()
        if st and st.value:
            return st.value.strip()
    except Exception:
        # در Thread پس‌زمینه Flask application context منتقل نمی‌شود.
        pass
    return ''


def get_repo_url():
    """آدرس مخزن: تنظیم پنل، سپس متغیر محیطی؛ fallback origin در _git_remote است."""
    return (_setting_value('git_repo_url') or
            os.environ.get('GIT_REPO_URL', '').strip())


def get_update_branch():
    """شاخهٔ هدف؛ اگر خالی باشد از default branch خود GitHub تشخیص داده می‌شود."""
    return (_setting_value('git_branch') or
            os.environ.get('GIT_BRANCH', '').strip()).strip()


def _run(cmd, cwd=BASE_DIR, timeout=120, env=None):
    """اجرای دستور و برگرداندن ``(returncode, stdout+stderr)``.

    فرمان‌ها همیشه به‌صورت list اجرا می‌شوند تا URL مخزن یا نام شاخه امکان
    shell injection نداشته باشد.
    """
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           timeout=timeout, env=env or _git_env())
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return -1, 'timeout'
    except Exception as e:
        return -2, str(e)


def _run_streaming(cmd, cwd=BASE_DIR, timeout=900, env=None, progress_cb=None):
    """اجرای فرمان با heartbeat دوره‌ای و جمع‌آوری خروجی — برای گام‌های طولانی.

    خروجی در یک Thread جدا خوانده می‌شود و هر ``HEARTBEAT_SECONDS`` ثانیه
    ``progress_cb`` صدا زده می‌شود تا تشخیص «توقف بروزرسانی» false positive
    ندهد. در صورت timeout فرایند kill می‌شود.
    """
    try:
        process = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace',
            env=env or _git_env(),
        )
    except Exception as e:
        return -2, str(e)

    chunks = []
    done = threading.Event()

    def _reader():
        try:
            for line in process.stdout:
                chunks.append(line)
                # خروجی خیلی بلند حافظه را نمی‌ترکاند.
                if len(chunks) > 400:
                    del chunks[:200]
        except Exception:
            pass
        finally:
            done.set()

    reader = threading.Thread(target=_reader, name='updater-stream-reader',
                              daemon=True)
    reader.start()
    deadline = time.time() + timeout
    try:
        while True:
            code = process.poll()
            if code is not None:
                break
            if time.time() > deadline:
                try:
                    process.kill()
                except OSError:
                    pass
                done.wait(timeout=10)
                return -1, 'timeout: ' + ''.join(chunks)[-400:]
            if progress_cb:
                try:
                    progress_cb()
                except Exception:
                    pass
            time.sleep(min(HEARTBEAT_SECONDS, 5))
    finally:
        try:
            done.wait(timeout=15)
        finally:
            try:
                reader.join(timeout=5)
            except Exception:
                pass
    output = ''.join(chunks)
    return process.returncode, output


def _validate_repo_url(url):
    url = (url or '').strip()
    if not url:
        raise UpdateError('آدرس مخزن گیت خالی است.')
    if any(ch in url for ch in ('\x00', '\r', '\n')) or url.startswith('-'):
        raise UpdateError('آدرس مخزن گیت نامعتبر است.')
    if url.startswith(('http://', 'https://', 'ssh://', 'git://')):
        parsed = urllib.parse.urlsplit(url)
        if not parsed.netloc:
            raise UpdateError('آدرس مخزن گیت نامعتبر است.')
    elif url.startswith('git@'):
        if ':' not in url:
            raise UpdateError('آدرس SSH مخزن گیت نامعتبر است.')
    return url


def _git_remote():
    """آدرس ریموت فعلی؛ تنظیم پنل برای مخزن جایگزین بر origin اولویت دارد."""
    url = get_repo_url()
    if url:
        return url
    code, out = _git(['remote', 'get-url', 'origin'], timeout=15)
    return out.strip() if code == 0 else ''


def _current_branch():
    code, out = _git(['rev-parse', '--abbrev-ref', 'HEAD'], timeout=15)
    value = out.strip() if code == 0 else ''
    return value if value and value != 'HEAD' else ''


def _current_commit(revision='HEAD'):
    code, out = _git(['rev-parse', '--verify', revision], timeout=15)
    return out.strip() if code == 0 else ''


def _commit_info(revision='HEAD'):
    code, out = _git(['show', '-s', '--format=%H|%h|%s|%cI', revision], timeout=15)
    if code != 0:
        applied = _read_applied_commit() if revision == 'HEAD' else ''
        if applied:
            return {'hash': applied, 'short': applied[:10],
                    'message': 'نسخهٔ اعمال‌شده از بروزرسانی قبلی', 'date': ''}
        return {'hash': '', 'short': '', 'message': '', 'date': ''}
    parts = out.strip().split('|', 3)
    return {
        'hash': parts[0] if len(parts) > 0 else '',
        'short': parts[1] if len(parts) > 1 else '',
        'message': parts[2] if len(parts) > 2 else '',
        'date': parts[3] if len(parts) > 3 else '',
    }


def get_git_info():
    """اطلاعات Git برای صفحهٔ مدیریت، بدون لو دادن توکن مخزن."""
    remote = _git_remote()
    info = _commit_info('HEAD')
    branch = _current_branch()
    if not branch:
        branch = 'بدون مخزن محلی' if not _is_git_worktree() else 'detached'
    local = _local_version_info()
    return {
        'branch': branch,
        'target_branch': get_update_branch() or 'تشخیص خودکار',
        'remote': _display_repo(remote),
        'commit_hash': info['short'],
        'commit_msg': info['message'],
        'commit_date': info['date'],
        'install_kind': local['kind'],
        'version': local['version_txt'],
        'applied_commit': _read_applied_commit(),
    }


def _parse_github(url):
    """استخراج owner/name/token از URL گیت‌هاب (HTTPS یا SSH)."""
    url = (url or '').strip()
    if not url:
        return None
    token = ''
    url_no_auth = url
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme in ('http', 'https'):
            if parsed.username:
                token = parsed.password or parsed.username
            host = parsed.hostname or ''
            url_no_auth = urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, '', ''))
    except Exception:
        url_no_auth = url
    match = re.search(
        r'(?i)(?:^|://|@)github\.com[:/]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)',
        url_no_auth or url,
    )
    if not match:
        return None
    name = match.group(2)
    if name.endswith('.git'):
        name = name[:-4]
    return {'host': 'github.com', 'owner': match.group(1), 'name': name, 'token': token}


def _http_json(url, token='', timeout=30):
    """دریافت JSON از API گیت‌هاب با خطایابی بهتر."""
    import socket
    req = urllib.request.Request(url, headers={
        'User-Agent': 'rahsasitepyt-updater',
        'Accept': 'application/vnd.github+json',
    })
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
        data = json.loads(raw)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise UpdateError('محدودیت نرخ درخواست GitHub (Rate Limit). لطفاً کمی صبر کنید یا از Token احراز هویت استفاده کنید.')
        elif e.code == 404:
            raise UpdateError('مخزن یا شاخه در GitHub پیدا نشد (404). آدرس مخزن را بررسی کنید.')
        elif e.code == 401:
            raise UpdateError('احراز هویت GitHub ناموفق بود. لطفاً Token را بررسی کنید.')
        else:
            raise UpdateError('خطای HTTP ' + str(e.code) + ' از GitHub: ' + str(e.reason))
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if 'timed out' in reason.lower():
            raise UpdateError('زمان اتصال به GitHub تمام شد. اتصال اینترنت را بررسی کنید.')
        elif 'Name or service not known' in reason or 'No address associated' in reason:
            raise UpdateError('DNS خطا: امکان اتصال به github.com نیست. نام دامنه حل نمی‌شود.')
        elif 'Connection refused' in reason:
            raise UpdateError('اتصال به GitHub رد شد. ممکن است فایروال یا پروکسی مسدود کرده باشد.')
        elif 'Connection timed out' in reason:
            raise UpdateError('زمان اتصال به GitHub تمام شد. سرور به اینترنت دسترسی محدود دارد.')
        else:
            raise UpdateError('خطا در اتصال به GitHub: ' + reason[:200])
    except socket.timeout:
        raise UpdateError('زمان اتصال به GitHub تمام شد. لطفاً دوباره تلاش کنید.')
    except Exception as e:
        raise UpdateError('خطا در اتصال به GitHub: ' + str(e)[:200])


def _github_heads(repo_url):
    info = _parse_github(repo_url)
    if not info:
        return {}
    data = _http_json(
        'https://api.github.com/repos/{}/{}/branches?per_page=100'.format(
            info['owner'], info['name']),
        token=info['token'],
    )
    refs = {}
    if isinstance(data, list):
        for row in data:
            name = (row or {}).get('name') or ''
            sha = ((row or {}).get('commit') or {}).get('sha') or ''
            if name and sha:
                refs[name] = sha
    return refs


def _github_default_branch(repo_url):
    info = _parse_github(repo_url)
    if not info:
        return ''
    data = _http_json(
        'https://api.github.com/repos/{}/{}'.format(info['owner'], info['name']),
        token=info['token'],
    )
    if not isinstance(data, dict):
        return ''
    branch = (data.get('default_branch') or '').strip()
    if branch and _BRANCH_RE.match(branch) and '..' not in branch and '//' not in branch:
        return branch
    return ''


def _remote_version_txt(repo, branch):
    """نسخهٔ ``version.txt`` شاخهٔ مقصد در GitHub — برای مقایسه در نصب‌های ZIP.

    اول raw.githubusercontent (سریع)، بعد API contents (با پشتیبانی Token).
    اگر هیچ‌کدام در دسترس نبود None برمی‌گردد؛ این یعنی «نامشخص» و هرگز
    نباید جلوی بروزرسانی را بگیرد.
    """
    info = _parse_github(repo)
    if not info:
        return None
    quoted = urllib.parse.quote(branch, safe='')
    urls = [
        ('raw', 'https://raw.githubusercontent.com/{}/{}/{}/version.txt'.format(
            info['owner'], info['name'], quoted)),
    ]
    for _kind, url in urls:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'rahsasitepyt-updater',
            })
            if info['token']:
                req.add_header('Authorization', 'Bearer ' + info['token'])
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', 'replace').strip()
            value = raw.splitlines()[0].strip() if raw else ''
            if value and len(value) <= 64:
                return value
            return None
        except Exception:
            continue
    # fallback: API contents (base64)
    try:
        data = _http_json(
            'https://api.github.com/repos/{}/{}/contents/version.txt?ref={}'.format(
                info['owner'], info['name'], quoted),
            token=info['token'], timeout=30,
        )
        if isinstance(data, dict) and data.get('content'):
            import base64
            raw = base64.b64decode(data['content']).decode('utf-8', 'replace').strip()
            value = raw.splitlines()[0].strip() if raw else ''
            if value and len(value) <= 64:
                return value
    except Exception:
        pass
    return None


def _remote_refs(repo, heads=False):
    """دریافت لیست شاخه‌ها از مخزن ریموت."""
    args = ['ls-remote']
    if heads:
        args.append('--heads')
    args.append(repo)
    code, out = _git(args, timeout=30)
    refs = {}
    if code == 0:
        for line in out.splitlines():
            bits = line.split()
            if len(bits) >= 2 and bits[1].startswith('refs/heads/'):
                refs[bits[1][len('refs/heads/'):]] = bits[0]
        if refs:
            return refs, out
    # اگر git ls-remote کار نکرد، از API گیت‌هاب استفاده می‌کنیم
    try:
        gh = _github_heads(repo)
        if gh:
            return gh, out
    except UpdateError:
        pass  # خطا در ادامه هندل می‌شود
    if code != 0:
        error_msg = out.strip() if out else 'خروجی خالی'
        if 'Authentication' in error_msg or 'permission denied' in error_msg.lower():
            raise UpdateError('دسترسی به مخزن گیت ممکن نیست. برای مخزن خصوصی از SSH Key یا Token استفاده کنید.')
        elif 'Could not read from remote repository' in error_msg:
            raise UpdateError('مخزن گیت قابل خواندن نیست. آدرس مخزن را بررسی کنید.')
        else:
            raise UpdateError('خطا در اتصال به مخزن گیت: ' + _redact_text(error_msg[-300:], repo))
    return refs, out


def _remote_default_branch(repo):
    """تشخیص default branch؛ روی گیت قدیمی بدون --symref (مثل cPanel) هم کار می‌کند."""
    code, raw = _git(['ls-remote', '--symref', repo, 'HEAD'], timeout=30)
    default = ''
    if code == 0:
        for line in raw.splitlines():
            stripped = line.rstrip()
            if stripped.startswith('ref: refs/heads/') and stripped.endswith(' HEAD'):
                default = stripped[len('ref: refs/heads/'):].rsplit(' HEAD', 1)[0].strip()
                break
    if default and _BRANCH_RE.match(default) and '..' not in default and '//' not in default:
        return default
    # گیت 1.8 سی‌پنل --symref ندارد و فقط usage چاپ می‌کند؛ نباید خطا بدهیم.
    try:
        heads, _ = _remote_refs(repo, heads=True)
    except UpdateError:
        heads = {}
    for candidate in ('main', 'master'):
        if candidate in heads:
            return candidate
    if heads:
        return next(iter(heads))
    gh = _github_default_branch(repo)
    if gh:
        return gh
    raise UpdateError(
        'تشخیص شاخهٔ پیش‌فرض گیت ممکن نشد. نام شاخه را در تنظیمات مخزن بنویسید (مثلاً main).'
    )


def _select_branch(repo, branch=''):
    configured = (branch or get_update_branch() or '').strip()
    if configured.startswith('refs/heads/'):
        configured = configured[len('refs/heads/'):]
    if configured:
        if not _BRANCH_RE.match(configured) or '..' in configured or '//' in configured:
            raise UpdateError('نام شاخهٔ گیت نامعتبر است.')
        return configured

    # اگر شاخهٔ جاری روی ریموت هم وجود دارد، همان را نگه می‌داریم.
    current = _current_branch()
    heads, _ = _remote_refs(repo, heads=True)
    if current and current in heads:
        return current
    for candidate in ('main', 'master'):
        if candidate in heads:
            return candidate
    if heads and len(heads) == 1:
        return next(iter(heads))
    default = _remote_default_branch(repo)
    if default:
        return default
    raise UpdateError('هیچ شاخه‌ای در مخزن گیت پیدا نشد.')


def _target_ref(branch):
    return UPDATE_REF_PREFIX + '/' + branch


def _fetch_target(repo, branch):
    """فقط شاخهٔ هدف را از URL می‌گیرد و origin پروژه را دستکاری نمی‌کند."""
    target = _target_ref(branch)
    refspec = '+refs/heads/{}:{}'.format(branch, target)
    code, out = _git(['fetch', '--no-tags', '--force', repo, refspec],
                     timeout=int(os.environ.get('GIT_FETCH_TIMEOUT', '300')))
    if code != 0:
        raise UpdateError('دریافت نسخهٔ جدید از گیت شکست خورد: ' +
                          _redact_text(out[-400:], repo))
    commit = _current_commit(target)
    if not commit:
        raise UpdateError('شاخهٔ هدف گیت پس از fetch قابل خواندن نیست.')
    return target, commit


def _verify_target(target):
    code, out = _git(['ls-tree', '-r', '--name-only', target], timeout=60)
    if code != 0:
        raise UpdateError('امکان بررسی فایل‌های نسخهٔ جدید نیست: ' + out[-250:])
    files = set(out.splitlines())
    missing = [name for name in _REQUIRED_FILES if name not in files]
    if missing:
        raise UpdateError(
            'مخزن انتخاب‌شده پروژهٔ معتبر نیست؛ فایل‌های ضروری پیدا نشد: ' +
            '، '.join(missing))
    return files


def _git_file(revision, path):
    if not revision:
        return None
    code, out = _git(['show', '{}:{}'.format(revision, path)], timeout=30)
    return out if code == 0 else None


def _changed_files(old_commit, new_ref):
    """لیست فایل‌های تغییرکرده بین دو commit.
    
    اگر old_commit خالی باشد (نصب اولیه از ZIP)، همه فایل‌های پروژه
    به‌عنوان «جدید» برگردانده می‌شوند — به‌جز محتوای کاربر
    (آپلودها، .env، بکاپ‌ها، instance و ...) که با ``_overlay_skip`` حذف می‌شود.
    """
    if not new_ref:
        return []
    
    if not old_commit:
        # نصب اولیه: همه فایل‌های پروژه رو لیست کن
        files = []
        for root, dirs, filenames in os.walk(BASE_DIR):
            # حذف پوشه‌هایی که نباید تغییر کنند
            dirs[:] = [d for d in dirs if not _overlay_skip(d) and d not in ('.git',)]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
                rel = rel.replace('\\', '/')
                if rel and not _overlay_skip(rel) and not rel.startswith('.'):
                    files.append(rel)
        return files
    
    code, out = _git(['diff', '--name-only', old_commit, new_ref], timeout=60)
    return [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []


def _preserve_local_files():
    """فایل‌های گزارش که در نسخه‌های قدیمی tracked بودند با reset حذف نشوند."""
    saved = {}
    for rel in _PRESERVE_FILES:
        path = os.path.join(BASE_DIR, rel)
        try:
            with open(path, 'rb') as f:
                saved[rel] = f.read()
        except OSError:
            pass
    return saved


def _restore_local_files(saved):
    for rel, content in saved.items():
        path = os.path.join(BASE_DIR, rel)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(content)
        except OSError:
            pass


def _read_local_requirements():
    try:
        with open(os.path.join(BASE_DIR, 'requirements.txt'), 'r', encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


def _requirements_changed(old_commit, old_requirements=None, new_requirements=None):
    old = old_requirements
    if old is None and old_commit:
        old = _git_file(old_commit, 'requirements.txt')
    new = new_requirements if new_requirements is not None else _read_local_requirements()
    return old is not None and new is not None and old != new


def _bounded_env_int(name, default, minimum, maximum):
    """خواندن عدد تنظیمات updater با خطای واضح و جلوگیری از timeout نامحدود."""
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise UpdateError('تنظیم {} باید عدد صحیح باشد (مقدار فعلی: {!r}).'.format(name, raw))
    if not minimum <= value <= maximum:
        raise UpdateError(
            'تنظیم {} باید بین {} و {} باشد (مقدار فعلی: {}).'.format(
                name, minimum, maximum, value
            )
        )
    return value


def _validate_update_runtime():
    """وابستگی‌های قفل‌شده فقط با همان runtime هاست نصب شوند."""
    implementation = getattr(sys, 'implementation', None)
    implementation_name = getattr(implementation, 'name', '')
    if implementation_name != 'cpython' or sys.version_info[:2] != (3, 11):
        raise UpdateError(
            'نصب خودکار وابستگی‌ها فقط برای CPython 3.11 پشتیبانی می‌شود؛ '
            'مفسر فعلی {} {}.{} است. Python App هاست را روی 3.11 تنظیم کنید.'.format(
                implementation_name or 'unknown', sys.version_info.major, sys.version_info.minor
            )
        )


def _pip_settings():
    process_timeout = _bounded_env_int('PIP_INSTALL_TIMEOUT', 900, 60, 3600)
    request_timeout = _bounded_env_int('PIP_DEFAULT_TIMEOUT', 120, 15, 600)
    retries = _bounded_env_int('PIP_RETRIES', 10, 0, 50)
    env = {
        **_git_env(),
        'PIP_DISABLE_PIP_VERSION_CHECK': '1',
        'PIP_DEFAULT_TIMEOUT': str(request_timeout),
        'PIP_RETRIES': str(retries),
        'PIP_PREFER_BINARY': '1',
        'PIP_ONLY_BINARY': ':all:',
    }
    common = [
        '--disable-pip-version-check',
        '--timeout', str(request_timeout),
        '--retries', str(retries),
        '--prefer-binary',
        '--only-binary=:all:',
    ]
    return process_timeout, env, common


def _pip_failure(stage, output):
    detail = _redact_text((output or '').strip()[-1200:]) or 'pip خروجی بیشتری ثبت نکرد.'
    return UpdateError('{} شکست خورد:\n{}'.format(stage, detail))


def _install_requirements_file(requirements_path, upgrade_tools=True):
    """نصب wheel-only و سپس ``pip check`` با همان مفسر Passenger."""
    _validate_update_runtime()
    process_timeout, pip_env, common = _pip_settings()
    pip = [sys.executable, '-m', 'pip']

    if upgrade_tools:
        code, out = _run(
            pip + ['install'] + common + ['--upgrade', 'pip', 'setuptools', 'wheel'],
            timeout=process_timeout, env=pip_env,
        )
        if code != 0:
            raise _pip_failure('ارتقای pip/setuptools/wheel', out)

    code, out = _run(
        pip + ['install'] + common + ['-r', requirements_path],
        timeout=process_timeout, env=pip_env,
    )
    if code != 0:
        raise _pip_failure('نصب requirements.txt جدید', out)

    code, out = _run(pip + ['check'], timeout=min(process_timeout, 300), env=pip_env)
    if code != 0:
        raise _pip_failure('بررسی نهایی pip check', out)


def _temporary_requirements(content):
    """requirements نسخهٔ مقصد را پیش از جایگزینی کد در ریشه پروژه بساز."""
    handle = tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', prefix='.requirements-update-', suffix='.txt',
        dir=BASE_DIR, delete=False,
    )
    try:
        handle.write(content)
        handle.flush()
        return handle.name
    finally:
        handle.close()


def _install_changed_dependencies(old_commit, old_requirements=None,
                                  new_requirements=None):
    if not _requirements_changed(
            old_commit, old_requirements=old_requirements,
            new_requirements=new_requirements):
        return 'وابستگی‌ها تغییری نکرده‌اند.'
    flag = os.environ.get('UPDATE_INSTALL_DEPENDENCIES', '1').strip().lower()
    if flag in ('0', 'false', 'no', 'off'):
        return 'نصب وابستگی‌ها طبق تنظیم UPDATE_INSTALL_DEPENDENCIES غیرفعال است.'

    requirements_path = os.path.join(BASE_DIR, 'requirements.txt')
    temporary_path = ''
    if new_requirements is not None:
        temporary_path = _temporary_requirements(new_requirements)
        requirements_path = temporary_path
    try:
        _install_requirements_file(requirements_path, upgrade_tools=True)
    except Exception as exc:
        rollback = ''
        if old_requirements is not None:
            try:
                rollback = ' ' + _restore_dependencies(old_requirements)
            except Exception as rollback_exc:
                rollback = ' بازیابی وابستگی‌های قبلی نیز شکست خورد: {}'.format(rollback_exc)
        if isinstance(exc, UpdateError):
            raise UpdateError(str(exc) + rollback) from exc
        raise
    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
    return 'وابستگی‌های جدید از wheel باینری نصب شدند و pip check موفق بود.'


def _restore_dependencies(requirements_content):
    """در rollback، مجموعهٔ دقیق وابستگی‌های نسخهٔ قبلی را برگردان."""
    if requirements_content is None:
        return 'requirements نسخهٔ قبلی در دسترس نبود.'
    path = _temporary_requirements(requirements_content)
    try:
        _install_requirements_file(path, upgrade_tools=False)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return 'وابستگی‌های نسخهٔ قبلی بازیابی و بررسی شدند.'


def _run_fresh_migration():
    """مایگریشن را با import تازهٔ مدل‌ها در یک پردازش جدا اجرا می‌کند.
    
    این تابع مهم است چون بعد از جایگزینی کدها، پردازش وب هنوز نسخهٔ قدیمی کد
    را در حافظه دارد. اجرای مایگریشن در همان پردازش باعث می‌شود ستون‌های جدید
    دیده نشوند. در طول اجرا heartbeat زنده نگه داشته می‌شود.
    """
    # پاک‌سازی pyc cache قبل از اجرا برای اطمینان از استفاده از کد جدید
    _clear_python_cache()
    
    script = os.path.join(BASE_DIR, 'scripts', 'migrate_database.py')
    if os.path.exists(script):
        cmd = [sys.executable, '-u', script]
    else:  # سازگاری با نسخه‌ای که هنوز اسکریپت را دریافت نکرده است.
        code = (
            'from app import app; from updater import _migrate_db; '
            'ctx=app.app_context(); ctx.push(); '
            'print(_migrate_db())'
        )
        cmd = [sys.executable, '-u', '-c', code]
    
    env = _python_child_env()

    # اجرا با timeout بلندتر برای دیتابیس‌های بزرگ + heartbeat دوره‌ای
    timeout = _bounded_env_int('DB_MIGRATION_TIMEOUT', 900, 60, 3600)

    code, out = _run_streaming(cmd, timeout=timeout, env=env,
                               progress_cb=_heartbeat)
    
    if code != 0:
        # اگر خطای پایتون است، جزئیات بیشتری برگردان
        error_lines = out.strip().split('\n')
        error_msg = '\n'.join(error_lines[-10:]) if len(error_lines) > 10 else out
        raise UpdateError('مایگریشن دیتابیس شکست خورد:\n' + _redact_text(error_msg[-1200:]))
    
    return out.strip()[-1200:] or 'مایگریشن انجام شد.'


def _smoke_enabled():
    return os.environ.get('UPDATE_SMOKE_TEST', '1').strip().lower() \
        not in ('0', 'false', 'no', 'off')


def _smoke_test_after_update():
    """تست سلامت بلافاصله بعد از بروزرسانی در یک پردازش تازه.

    اگر سایت بعد از جایگزینی کدها بالا نیاید، بروزرسانی ناموفق اعلام و
    rollback خودکار انجام می‌شود — سایت هرگز روی کد خراب نمی‌ماند.
    (روی هاست‌هایی که subprocess بسیار محدود است، با UPDATE_SMOKE_TEST=0
    قابل غیرفعال‌کردن است.)
    """
    if not _smoke_enabled():
        return 'تست سلامت غیرفعال است (UPDATE_SMOKE_TEST).'
    code = (
        'from app import app; '
        'c = app.test_client(); '
        'r = c.get("/health"); '
        'raise SystemExit(0 if r.status_code in (200, 301, 302, 303, 307, 308) else 1)'
    )
    cmd = [sys.executable, '-u', '-c', code]
    env = _python_child_env()
    timeout = _bounded_env_int('UPDATE_SMOKE_TIMEOUT', 180, 30, 600)
    rc, out = _run_streaming(cmd, timeout=timeout, env=env,
                             progress_cb=_heartbeat)
    if rc != 0:
        raise UpdateError(
            'تست سلامت سایت پس از بروزرسانی شکست خورد:\n' +
            _redact_text((out or '').strip()[-600:]))
    return 'تست سلامت سایت پس از بروزرسانی موفق بود ✅'


def _rebuild_assets():
    """بازتولید فایل‌های .min.css/.min.js پس از به‌روزرسانی کد.

    اگر شکست بخورد چیزی خراب نمی‌شود: تابع asset() در app.py وقتی نسخهٔ فشرده
    کهنه یا موجود نباشد، خودکار به فایل اصلی برمی‌گردد.
    """
    try:
        script = os.path.join(BASE_DIR, 'scripts', 'build_assets.py')
        if not os.path.exists(script):
            return False
        import subprocess as _sp
        _sp.run([sys.executable, '-u', script], cwd=BASE_DIR,
                capture_output=True, timeout=120)
        return True
    except Exception:
        return False


def _clear_python_cache():
    """پاک‌سازی cache کد پروژه، بدون دست‌زدن به virtualenv و فایل‌های کاربر."""
    skip = {'.git', '.venv', 'venv', 'env', 'instance', 'uploads'}
    for root, dirs, _files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in skip]
        if '__pycache__' in dirs:
            path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(path)
            except OSError:
                pass


def _restart_enabled():
    return os.environ.get('UPDATE_TOUCH_RESTART', '1').strip().lower() not in ('0', 'false', 'no')


def _touch_restart():
    """Passenger را وادار به reload می‌کند؛ برای Gunicorn supervisor جدا لازم است."""
    if not _restart_enabled():
        return False
    for name in ('passenger_wsgi.py', 'wsgi.py'):
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path):
            try:
                os.utime(path, None)
                return True
            except OSError:
                return False
    return False


def _acquire_update_lock():
    """قفل بین چند worker/process؛ از اجرای همزمان دو reset جلوگیری می‌کند."""
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    try:
        handle = open(LOCK_FILE, 'a+', encoding='utf-8')
        if _fcntl is not None:
            try:
                _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                handle.close()
                return None
        elif not _fallback_process_lock.acquire(blocking=False):  # pragma: no cover
            handle.close()
            return None
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        return handle
    except OSError:
        return None


def _release_update_lock(handle):
    if not handle:
        return
    try:
        if _fcntl is not None:
            _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
        else:  # pragma: no cover
            _fallback_process_lock.release()
    except (OSError, RuntimeError):
        pass
    try:
        handle.close()
    except OSError:
        pass


def _log_history(repo, migration, **extra):
    """ثبت گزارش بدون ذخیرهٔ توکن؛ حداکثر ۲۰ بروزرسانی."""
    try:
        rows = []
        try:
            with open(HISTORY_FILE, encoding='utf-8') as f:
                old = json.load(f)
                if isinstance(old, list):
                    rows = old
        except (OSError, ValueError, TypeError):
            pass
        entry = {
            'at': datetime.now(UTC).isoformat(),
            'repo': _display_repo(repo),
            'migration': str(migration or '')[-1200:],
        }
        entry.update(extra)
        rows.insert(0, entry)
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        tmp = HISTORY_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(rows[:20], f, ensure_ascii=False, indent=1)
            f.flush()
        os.replace(tmp, HISTORY_FILE)
    except Exception:
        pass


def _download_file(url, dest, token='', timeout=180, progress_cb=None):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'rahsasitepyt-updater',
        'Accept': 'application/zip, */*',
    })
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, 'wb') as handle:
        total = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            total += len(chunk)
            if progress_cb:
                try:
                    progress_cb(total)
                except Exception:
                    pass
    if not os.path.exists(dest) or os.path.getsize(dest) < 64:
        raise UpdateError('آرشیو دانلودشده خالی یا نامعتبر است.')


def _archive_root(extract_dir):
    try:
        entries = [name for name in os.listdir(extract_dir) if name not in ('.', '..')]
    except OSError:
        return extract_dir
    if len(entries) == 1:
        only = os.path.join(extract_dir, entries[0])
        if os.path.isdir(only):
            return only
    return extract_dir


def _overlay_skip(rel):
    rel = (rel or '').replace('\\', '/').lstrip('/')
    if not rel:
        return False
    top = rel.split('/', 1)[0]
    if top in _OVERLAY_SKIP:
        return True
    # استثناء: فایل .htaccess محافظ پوشهٔ آپلود باید روی سایت‌هایی که هنوز آن
    # را ندارند ساخته شود؛ اما اگر سایت آن را دارد، _overlay_tree هرگز
    # بازنویسی‌اش نمی‌کند (تنظیمات دستی هاست حفظ می‌شود).
    if rel.endswith('/.htaccess'):
        return False
    return rel == 'static/uploads' or rel.startswith('static/uploads/')


def _is_htaccess(rel):
    rel = (rel or '').replace('\\', '/').lstrip('/')
    return rel == '.htaccess' or rel.endswith('/.htaccess')


def _overlay_tree(src_root, dest_root, progress_cb=None):
    """کپی فایل‌های آرشیو روی سایت، بدون دست‌زدن به .env / instance / آپلود / venv.

    قوانین حفاظتی:
      * فایل‌های ``_OVERLAY_SKIP`` و ``static/uploads`` هرگز کپی نمی‌شوند.
      * ``.htaccess`` موجود روی سایت هرگز بازنویسی نمی‌شود (تنظیمات دستی هاست
        کاربر حفظ می‌شود)؛ فقط اگر سایت هنوز آن را ندارد، نسخهٔ محافظِ آرشیو
        (مثلاً جلوگیری از اجرای فایل‌های آپلودی) ساخته می‌شود.
    """
    changed = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel_dir = os.path.relpath(dirpath, src_root)
        if rel_dir == '.':
            rel_dir = ''
        kept = []
        for name in dirnames:
            rel = (rel_dir + '/' + name).replace('\\', '/').lstrip('/') if rel_dir else name
            if _overlay_skip(rel):
                # فقط برای رسیدن به .htaccess محافظ داخل پوشهٔ آپلود، وارد
                # static/uploads می‌شویم؛ خود فایل‌های داخل آن در حلقهٔ
                # filenames باز هم skip می‌شوند.
                if not (rel == 'static/uploads' or rel.startswith('static/uploads/')):
                    continue
            kept.append(name)
        dirnames[:] = kept
        for filename in filenames:
            rel = (rel_dir + '/' + filename).replace('\\', '/').lstrip('/') if rel_dir else filename
            if _overlay_skip(rel):
                continue
            count += 1
            if progress_cb and count % 100 == 0:
                try:
                    progress_cb(count)
                except Exception:
                    pass
            source = os.path.join(dirpath, filename)
            dest = os.path.join(dest_root, *rel.split('/'))
            # .htaccess موجود روی سایت دست نمی‌خورد (خواستهٔ صاحب سایت)؛
            # فقط وقتی وجود ندارد از آرشیو ساخته می‌شود تا محافظت آپلود برقرار شود.
            if _is_htaccess(rel) and os.path.isfile(dest):
                continue
            # فایل یکسان را دوباره ننویس؛ به‌ویژه تغییر بی‌دلیل mtime فایل WSGI
            # می‌تواند Passenger را وسط migration زودتر از موعد restart کند.
            try:
                if os.path.isfile(dest) and filecmp.cmp(source, dest, shallow=False):
                    continue
            except OSError:
                pass
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(source, dest)
            changed.append(rel)
    return changed


def _archive_files(root):
    files = set()
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == '.':
            rel_dir = ''
        kept = []
        for dirname in dirnames:
            rel = (rel_dir + '/' + dirname).replace('\\', '/').lstrip('/') \
                if rel_dir else dirname
            if not _overlay_skip(rel):
                kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            rel = os.path.relpath(os.path.join(dirpath, filename), root)
            rel = rel.replace('\\', '/')
            if not _overlay_skip(rel):
                files.add(rel)
    return files


def _safe_project_path(relative_path):
    rel = (relative_path or '').replace('\\', '/').lstrip('/')
    normalized = os.path.normpath(rel).replace('\\', '/')
    if not rel or normalized in ('.', '..') or normalized.startswith('../'):
        raise UpdateError('مسیر نامعتبر در آرشیو بروزرسانی: {}'.format(relative_path))
    candidate = os.path.join(BASE_DIR, *normalized.split('/'))
    try:
        if os.path.commonpath((os.path.realpath(BASE_DIR), os.path.realpath(candidate))) != \
                os.path.realpath(BASE_DIR):
            raise UpdateError('مسیر آرشیو از ریشهٔ پروژه خارج می‌شود: {}'.format(relative_path))
    except ValueError:
        raise UpdateError('مسیر نامعتبر در آرشیو بروزرسانی: {}'.format(relative_path))
    return candidate, normalized


def _snapshot_code_files(files):
    """از فایل‌هایی که ZIP بازنویسی می‌کند snapshot موقت بگیر."""
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    root = tempfile.mkdtemp(prefix='.code-rollback-', dir=INSTANCE_DIR)
    entries = []
    try:
        for rel in sorted(set(files)):
            if _overlay_skip(rel):
                continue
            dest, normalized = _safe_project_path(rel)
            if os.path.isdir(dest):
                raise UpdateError('فایل بروزرسانی با پوشهٔ موجود تداخل دارد: {}'.format(rel))
            existed = os.path.isfile(dest)
            entries.append((normalized, existed))
            if existed:
                backup = os.path.join(root, *normalized.split('/'))
                os.makedirs(os.path.dirname(backup), exist_ok=True)
                shutil.copy2(dest, backup)
        return {'root': root, 'entries': entries}
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def _restore_code_snapshot(snapshot):
    if not snapshot:
        return
    root = snapshot['root']
    for rel, existed in snapshot['entries']:
        dest, normalized = _safe_project_path(rel)
        backup = os.path.join(root, *normalized.split('/'))
        if existed:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(backup, dest)
        elif os.path.isfile(dest) or os.path.islink(dest):
            os.remove(dest)


def _cleanup_code_snapshot(snapshot):
    if snapshot:
        shutil.rmtree(snapshot.get('root', ''), ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# مانیفست فایل‌های مدیریت‌شده + بکاپ کد پیش از جایگزینی
# ═══════════════════════════════════════════════════════════════════════════
def _read_manifest():
    """لیست فایل‌هایی که خودِ بروزرسان قبلاً روی سایت نوشته است."""
    try:
        with open(MANIFEST_FILE, encoding='utf-8') as f:
            data = json.load(f)
        files = data.get('files') if isinstance(data, dict) else None
        if isinstance(files, list):
            return files[: _MANIFEST_MAX_FILES]
    except (OSError, ValueError, TypeError):
        pass
    return []


def _write_manifest(files, commit=''):
    """ثبت اتمیک فایل‌های مدیریت‌شده — برای پاک‌سازی امن در بروزرسانی بعدی."""
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        tmp = MANIFEST_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({
                'updated_at': datetime.now(UTC).isoformat(),
                'commit': (commit or '')[:40],
                'files': sorted(set(files))[:_MANIFEST_MAX_FILES],
            }, f, ensure_ascii=False)
            f.flush()
        os.replace(tmp, MANIFEST_FILE)
    except OSError:
        pass


def _cleanup_stale_files(new_files):
    """حذف فایل‌هایی که بروزرسان قبلاً نوشته ولی در نسخهٔ جدید نیستند.

    فقط فایل‌های داخل مانیفست قبلی حذف می‌شوند؛ فایل‌های دستی کاربر و
    فایل‌های محافظت‌شده (.env، آپلود، بکاپ، .htaccess) هرگز لمس نمی‌شوند.
    """
    previous = set(_read_manifest())
    current = set(new_files or [])
    removed = []
    for rel in sorted(previous - current):
        if _overlay_skip(rel) or _is_htaccess(rel):
            continue
        path, _normalized = _safe_project_path(rel)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                removed.append(rel)
        except OSError:
            continue
        # پوشهٔ والدِ خالی‌شده را هم (فقط اگر خالی است) جمع می‌کنیم.
        parent = os.path.dirname(path)
        try:
            while parent and parent != BASE_DIR and os.path.isdir(parent):
                if os.listdir(parent):
                    break
                os.rmdir(parent)
                parent = os.path.dirname(parent)
        except OSError:
            break
    return removed


def _write_code_backup(snapshot, commit=''):
    """بکاپ zip از فایل‌های پیش از جایگزینی در ``instance/backups``.

    snapshot فقط شامل فایل‌هایی است که بروزرسان قرار است بازنویسی کند؛
    آپلود/instance/.env داخل آن نیست. حداکثر ۵ بکاپ نگه داشته می‌شود.
    """
    if not snapshot:
        return ''
    try:
        root = snapshot.get('root', '')
        if not root or not os.path.isdir(root):
            return ''
        backup_dir = os.path.join(INSTANCE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')
        short = (commit or 'code')[:10]
        zip_path = os.path.join(backup_dir, 'update-pre-{}-{}.zip'.format(stamp, short))
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    full = os.path.join(dirpath, filename)
                    rel = os.path.relpath(full, root).replace('\\', '/')
                    zf.write(full, arcname=rel)
        # جلوگیری از رشد نامحدود پوشهٔ بکاپ (فقط بکاپ‌های خودِ بروزرسان).
        existing = sorted(
            [p for p in os.listdir(backup_dir) if p.startswith('update-pre-')],
            key=lambda p: os.path.getmtime(os.path.join(backup_dir, p)),
            reverse=True,
        )
        for old in existing[5:]:
            try:
                os.remove(os.path.join(backup_dir, old))
            except OSError:
                pass
        return os.path.basename(zip_path)
    except Exception:
        return ''


def _sqlite_database_path():
    url = _database_url()
    if not url:
        return os.path.join(INSTANCE_DIR, 'academy.db')
    match = re.match(r'^sqlite(?:\+pysqlite)?:///(.*)$', url, re.I)
    if not match:
        return None
    value = urllib.parse.unquote(match.group(1).split('?', 1)[0])
    if value in ('', ':memory:'):
        return None
    if value.startswith('/'):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(BASE_DIR, value))


def _backup_sqlite_database():
    """قبل از migration از SQLite با API سازگار با WAL بکاپ بگیر."""
    database_path = _sqlite_database_path()
    if not database_path or not os.path.isfile(database_path):
        return None
    import sqlite3
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    fd, backup_path = tempfile.mkstemp(prefix='.database-rollback-', suffix='.db',
                                       dir=INSTANCE_DIR)
    os.close(fd)
    source = target = None
    try:
        source = sqlite3.connect(database_path, timeout=30)
        target = sqlite3.connect(backup_path, timeout=30)
        source.backup(target)
        return {'database': database_path, 'backup': backup_path}
    except Exception:
        try:
            os.remove(backup_path)
        except OSError:
            pass
        raise UpdateError('تهیهٔ بکاپ SQLite پیش از مایگریشن شکست خورد.')
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.close()


def _restore_sqlite_database(backup):
    if not backup:
        return
    import sqlite3
    source = target = None
    try:
        source = sqlite3.connect(backup['backup'], timeout=30)
        target = sqlite3.connect(backup['database'], timeout=30)
        source.backup(target)
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.close()


def _cleanup_sqlite_backup(backup):
    if backup:
        try:
            os.remove(backup.get('backup', ''))
        except OSError:
            pass


def _apply_extracted_archive(root, repo='', branch='', old_commit='',
                             old_requirements=None, commit='', progress_cb=None,
                             skip_dependencies=False):
    """اعمال یک آرشیوِ از قبل extract شده روی سایت — بخش اصلی مسیر ZIP.

    ترتیب امن:
      1. نصب وابستگی‌های جدید (قبل از لمس کدها).
      2. snapshot از فایل‌هایی که قرار است تغییر کنند یا حذف شوند (برای rollback).
      3. بکاپ zip از همان snapshot در ``instance/backups``.
      4. overlay آرشیو روی سایت (بدون .env / آپلود / بکاپ / .htaccess موجود).
      5. حذف فایل‌های منسوخ فقط طبق مانیفست قبلی (هرگز فایل دستی کاربر).
      6. ثبت مانیفست جدید.
    """
    missing = [name for name in _REQUIRED_FILES
               if not os.path.isfile(os.path.join(root, name))]
    if missing:
        raise UpdateError('آرشیو مخزن فایل‌های ضروری را ندارد: ' + '، '.join(missing))
    files = _archive_files(root)
    with open(os.path.join(root, 'requirements.txt'), encoding='utf-8') as handle:
        target_requirements = handle.read()
    dependencies_changed = _requirements_changed(
        old_commit, old_requirements=old_requirements,
        new_requirements=target_requirements,
    )
    if skip_dependencies:
        dependency_msg = 'وابستگی‌ها قبلاً در مسیر گیت نصب شده بودند.'
    else:
        dependency_msg = _install_changed_dependencies(
            old_commit, old_requirements=old_requirements,
            new_requirements=target_requirements,
        )

    # فایل‌های منسوخ (در مانیفست قبلی، خارج از آرشیو جدید) هم داخل snapshot
    # می‌روند تا rollback بتواند آن‌ها را برگرداند.
    stale = []
    for rel in sorted(set(_read_manifest()) - set(files)):
        if _overlay_skip(rel) or _is_htaccess(rel):
            continue
        try:
            path, _normalized = _safe_project_path(rel)
            if os.path.isfile(path):
                stale.append(rel)
        except UpdateError:
            continue

    snapshot = _snapshot_code_files(set(files) | set(stale))
    try:
        _write_code_backup(snapshot, commit or old_commit)
        def _progress(done):
            _heartbeat()
            if progress_cb:
                try:
                    progress_cb(done)
                except Exception:
                    pass
        try:
            changed = _overlay_tree(root, BASE_DIR, progress_cb=_progress)
            removed = _cleanup_stale_files(files)
        except Exception as exc:
            rollback_messages = []
            try:
                _restore_code_snapshot(snapshot)
                rollback_messages.append('فایل‌های قبلی بازیابی شدند.')
            except Exception as rollback_exc:
                rollback_messages.append('بازیابی فایل‌ها شکست خورد: ' + str(rollback_exc))
            if (dependencies_changed and _dependency_install_enabled() and
                    old_requirements is not None):
                try:
                    rollback_messages.append(_restore_dependencies(old_requirements))
                except Exception as rollback_exc:
                    rollback_messages.append('بازیابی وابستگی‌ها شکست خورد: ' + str(rollback_exc))
            _cleanup_code_snapshot(snapshot)
            raise UpdateError(
                'جایگزینی فایل‌های آرشیو شکست خورد: {} | {}'.format(
                    _redact_text(str(exc), repo)[:500],
                    _redact_text(' '.join(rollback_messages), repo)[:700],
                )
            ) from exc
    except Exception:
        _cleanup_code_snapshot(snapshot)
        raise
    _write_manifest(files, commit or old_commit)
    return commit, files, changed, removed, dependency_msg, dependencies_changed, snapshot


def _apply_github_archive(repo, branch, old_commit='', old_requirements=None,
                          progress_cb=None, skip_dependencies=False):
    """دانلود و جایگزینی کد از ZIP گیت‌هاب — برای نصب‌های سی‌پنل بدون .git.

    بدون هیچ وابستگی به git: با urllib دانلود، با zipfile استخراج و با
    overlay امن جایگزین می‌شود. این مسیر روی هاست‌های اشتراکی که اصلاً git
    ندارند یا دسترسی شبکهٔ git آن‌ها بسته است هم کار می‌کند.
    """
    info = _parse_github(repo)
    if not info:
        raise UpdateError(
            'این پوشه مخزن گیت نیست و آدرس هم GitHub نیست؛ '
            'نمی‌توان آرشیو را دانلود کرد.'
        )
    quoted = urllib.parse.quote(branch, safe='')
    urls = [
        'https://codeload.github.com/{}/{}/zip/refs/heads/{}'.format(
            info['owner'], info['name'], quoted),
        'https://github.com/{}/{}/archive/refs/heads/{}.zip'.format(
            info['owner'], info['name'], quoted),
    ]
    tmp = tempfile.mkdtemp(prefix='academy-upd-')
    try:
        zip_path = os.path.join(tmp, 'src.zip')
        last_err = 'دانلود انجام نشد.'
        downloaded = False
        for url in urls:
            try:
                _download_file(url, zip_path, token=info['token'],
                               progress_cb=lambda *a: _heartbeat())
                downloaded = True
                break
            except Exception as exc:
                last_err = str(exc)
        if not downloaded:
            raise UpdateError('دانلود آرشیو GitHub شکست خورد: ' +
                              _redact_text(last_err, repo)[:300])
        extract_dir = os.path.join(tmp, 'src')
        os.makedirs(extract_dir, exist_ok=True)
        shutil.unpack_archive(zip_path, extract_dir)
        root = _archive_root(extract_dir)
        # commit شاخه برای ثبت در .update_commit و گزارش (اختیاری است).
        commit = ''
        try:
            refs, _ = _remote_refs(repo, heads=True)
            commit = refs.get(branch, '')
        except Exception:
            commit = ''
        return _apply_extracted_archive(
            root, repo=repo, branch=branch, old_commit=old_commit,
            old_requirements=old_requirements, commit=commit,
            progress_cb=progress_cb, skip_dependencies=skip_dependencies,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_for_update(repo_url=None, branch=None):
    """بررسی نسخهٔ GitHub بدون تغییر کد یا دیتابیس (برای دکمهٔ «بررسی»).

    در نصب‌های ZIP (بدون .git) مقایسه با ``version.txt`` انجام می‌شود، پس
    «نسخهٔ محلی پیدا نشد» دیگر مانع بررسی/بروزرسانی نیست.
    """
    repo = _validate_repo_url(repo_url or _git_remote())
    chosen = _select_branch(repo, branch)
    refs, _ = _remote_refs(repo, heads=True)
    remote_commit = refs.get(chosen, '')
    if not remote_commit:
        raise UpdateError('شاخهٔ «{}» در مخزن پیدا نشد.'.format(chosen))
    local = _local_version_info()
    local_commit = local['commit']
    # همیشه version.txt ریموت را هم می‌گیریم تا پنل «نسخه فعلی / نسخه مخزن»
    # در نصب ZIP خالی نماند (قبلاً فقط هش گیت نشان داده می‌شد).
    remote_version = _remote_version_txt(repo, chosen) or ''

    available = False
    if local_commit and remote_commit == local_commit:
        msg = 'کد سایت با آخرین نسخهٔ مخزن یکسان است.'
        if local['version_txt']:
            msg += ' (نسخهٔ {}).'.format(local['version_txt'])
    elif local_commit:
        available = True
        if local['version_txt'] and remote_version and local['version_txt'] != remote_version:
            msg = 'نسخهٔ جدید موجود است (محلی {} ← مخزن {}).'.format(
                local['version_txt'], remote_version)
        else:
            msg = 'نسخهٔ جدید موجود است.'
    else:
        # نصب ZIP: commit محلی نداریم؛ version.txt را مقایسه می‌کنیم.
        if remote_version and local['version_txt'] == remote_version:
            msg = ('کد سایت با آخرین نسخهٔ مخزن یکسان است '
                   '(نسخهٔ {} — نصب ZIP).'.format(local['version_txt']))
        elif remote_version and local['version_txt']:
            available = True
            msg = ('نسخهٔ جدید موجود است (محلی {} ← مخزن {}).'.format(
                local['version_txt'], remote_version))
        else:
            # نسخهٔ محلی/ریموت قابل مقایسه نیست؛ بروزرسانی را مسدود نمی‌کنیم.
            available = True
            msg = 'نسخهٔ محلی ثبت نشده (نصب ZIP). نسخهٔ مخزن آمادهٔ نصب است.'
    local_label = _version_label(local['version_txt'], local_commit)
    remote_label = _version_label(remote_version, remote_commit)
    return {
        'ok': True,
        'available': available,
        'branch': chosen,
        'local_commit': local_commit,
        'remote_commit': remote_commit,
        'local_short': local_label,
        'remote_short': remote_label,
        'local_commit_short': local_commit[:10] if local_commit else '',
        'remote_commit_short': remote_commit[:10] if remote_commit else '',
        'repo': _display_repo(repo),
        'git_worktree': _is_git_worktree(),
        'install_kind': local['kind'],
        'local_version': local['version_txt'] or local_label,
        'remote_version': remote_version or remote_label,
        'msg': msg,
    }


def _set_step(step, msg):
    """ثبت مرحله فعلی بروزرسانی برای نمایش در فرانت‌اند.
    
    step: 1=دریافت کد، 2=جایگزینی، 3=مایگریشن، 4=پاک‌سازی
    """
    _set_state(step=step, msg=msg, status='running')


def _dependency_install_enabled():
    return os.environ.get('UPDATE_INSTALL_DEPENDENCIES', '1').strip().lower() \
        not in ('0', 'false', 'no', 'off')


def _perform_update(repo, branch=None):
    """اجرای همگام بروزرسانی با preflight وابستگی و rollback مرحله‌ای.

    استراتژی دو مسیره (unbreakable):

    * پوشه بدون ``.git`` (نصب ZIP سی‌پنل) → مستقیم مسیر آرشیو: دانلود ZIP از
      GitHub + overlay امن + مانیفست + بکاپ. هیچ ``git init`` در پوشهٔ تولید
      انجام نمی‌شود (روی هاست‌های اشتراکی با git قدیمی/بدون شبکه این کار
      قبلاً به «بروزرسانی متوقف شده» ختم می‌شد).
    * پوشهٔ واقعاً مخزن git → fetch + reset؛ اگر شکست خورد و مخزن GitHub
      است، آرشیو fallback می‌شود.

    در همهٔ مسیرها: وابستگی‌های جدید نصب، مایگریشن دیتابیس در پردازش جدا،
    تست سلامت سایت و rollback خودکار در صورت هر شکستی انجام می‌شود.
    """
    repo = _validate_repo_url(repo)
    old_commit = _current_commit('HEAD')
    old_requirements = _read_local_requirements()
    preserved = _preserve_local_files()
    backup_ref = ''
    if old_commit:
        backup_ref = 'refs/academy-update-backup/{}'.format(int(time.time()))
        _git(['update-ref', backup_ref, old_commit], timeout=15)

    _set_step(1, 'اتصال به GitHub و دریافت آخرین نسخه...')
    chosen = _select_branch(repo, branch)

    method = 'git' if _is_git_worktree() else 'archive'
    files = set()
    changed = []
    removed = []
    target_commit = ''
    dependency_msg = 'وابستگی‌ها تغییری نکرده‌اند.'
    dependencies_changed = False
    dependencies_installed = False
    code_snapshot = None
    database_backup = None
    deps_attempted = False
    git_error_msg = ''

    if method == 'git':
        # ── مسیر Git: فقط وقتی پوشه واقعاً مخزن است (توسعه/CI) ──
        # مرحلهٔ ۱: فقط دریافت و اعتبارسنجی نسخهٔ مقصد. خطای این مرحله
        # (fetch/network) می‌تواند از مسیر آرشیو fallback شود؛ اما خطای
        # نصب وابستگی یا reset نباید با دانلود دوباره پنهان شود.
        target_ref = ''
        try:
            target_ref, target_commit = _fetch_target(repo, chosen)
            files = _verify_target(target_ref)
            changed = _changed_files(old_commit, target_ref)
            target_requirements = _git_file(target_ref, 'requirements.txt')
            if target_requirements is None:
                raise UpdateError('خواندن requirements.txt نسخهٔ مقصد ممکن نیست.')
        except Exception as exc:
            git_error_msg = _redact_text(str(exc), repo)[:500]
            # git شکست خورد؛ اگر مخزن GitHub است با مسیر آرشیو ادامه می‌دهیم.
            if not _parse_github(repo):
                if isinstance(exc, UpdateError):
                    raise
                raise UpdateError(git_error_msg) from exc
            method = 'archive'
        else:
            # مرحلهٔ ۲: وابستگی‌ها و جایگزینی کدها — بدون fallback آرشیو.
            dependencies_changed = _requirements_changed(
                old_commit, old_requirements=old_requirements,
                new_requirements=target_requirements,
            )
            dependency_msg = _install_changed_dependencies(
                old_commit, old_requirements=old_requirements,
                new_requirements=target_requirements,
            )
            dependencies_installed = dependencies_changed and _dependency_install_enabled()
            deps_attempted = True
            if not old_commit:
                code_snapshot = _snapshot_code_files(files)
            _set_step(2, 'جایگزینی فایل‌های برنامه با نسخهٔ تاییدشده...')
            code, out = _git(['reset', '--hard', target_ref], timeout=120)
            if code != 0:
                rollback = []
                try:
                    if old_commit:
                        restore_code, restore_out = _git(
                            ['reset', '--hard', old_commit], timeout=120)
                        if restore_code != 0:
                            raise UpdateError(restore_out[-400:])
                    else:
                        _restore_code_snapshot(code_snapshot)
                    _restore_local_files(preserved)
                    rollback.append('فایل‌های نسخهٔ قبلی بازیابی شدند.')
                except Exception as rollback_exc:
                    rollback.append('بازیابی فایل‌ها شکست خورد: {}'.format(rollback_exc))
                if dependencies_installed and old_requirements is not None:
                    try:
                        rollback.append(_restore_dependencies(old_requirements))
                    except Exception as rollback_exc:
                        rollback.append('بازیابی وابستگی‌ها شکست خورد: {}'.format(rollback_exc))
                _cleanup_code_snapshot(code_snapshot)
                raise UpdateError(
                    'جایگزینی کدها شکست خورد: {} | {}'.format(
                        _redact_text(out[-500:], repo),
                        _redact_text(' '.join(rollback), repo)[:800],
                    )
                )

    if method == 'archive':
        # ── مسیر آرشیو: بدون هیچ وابستگی به git — مخصوص نصب‌های ZIP ──
        _set_step(2, 'دانلود آرشیو GitHub و جایگزینی کدها (روش ZIP — بدون مخزن محلی)...')
        try:
            (target_commit, files, changed, removed, dependency_msg,
             dependencies_changed, code_snapshot) = _apply_github_archive(
                repo, chosen, old_commit=old_commit,
                old_requirements=old_requirements,
                progress_cb=_heartbeat,
                skip_dependencies=deps_attempted,
            )
        except Exception as archive_exc:
            arch_msg = _redact_text(str(archive_exc), repo)[:900]
            if git_error_msg:
                raise UpdateError(
                    'بروزرسانی شکست خورد. گیت: {} | آرشیو: {}'.format(
                        git_error_msg, arch_msg)
                ) from archive_exc
            raise UpdateError('بروزرسانی از آرشیو GitHub شکست خورد: ' + arch_msg) \
                from archive_exc
        dependencies_installed = dependencies_changed and _dependency_install_enabled()

    _restore_local_files(preserved)

    # SQLite پیش از migration با API backup (سازگار با WAL) ذخیره می‌شود.
    # migrationهای MySQL این پروژه افزایشی‌اند؛ rollback کد همچنان انجام می‌شود.
    # تست سلامت هم داخل همین بلوک است تا سایت هیچ‌وقت روی کد خراب نماند.
    try:
        database_backup = _backup_sqlite_database()
        _set_step(3, 'اجرای مایگریشن ساختار و داده‌های دیتابیس...')
        migration_msg = _run_fresh_migration()
        smoke_msg = _smoke_test_after_update()
    except Exception as exc:
        rollback = []
        if database_backup:
            try:
                _restore_sqlite_database(database_backup)
                rollback.append('دیتابیس SQLite بازیابی شد.')
            except Exception as rollback_exc:
                rollback.append('بازیابی SQLite شکست خورد: {}'.format(rollback_exc))
        try:
            if method == 'git' and old_commit:
                code, out = _git(['reset', '--hard', old_commit], timeout=120)
                if code != 0:
                    raise UpdateError(out[-500:])
            else:
                _restore_code_snapshot(code_snapshot)
            _restore_local_files(preserved)
            rollback.append('کد نسخهٔ قبلی بازیابی شد.')
        except Exception as rollback_exc:
            rollback.append('بازیابی کد شکست خورد: {}'.format(rollback_exc))
        if dependencies_installed and old_requirements is not None:
            try:
                rollback.append(_restore_dependencies(old_requirements))
            except Exception as rollback_exc:
                rollback.append('بازیابی وابستگی‌ها شکست خورد: {}'.format(rollback_exc))
        _clear_python_cache()
        _cleanup_code_snapshot(code_snapshot)
        _cleanup_sqlite_backup(database_backup)
        detail = _redact_text(str(exc), repo)[:1200]
        rollback_detail = _redact_text(' '.join(rollback), repo)[:1200]
        error = UpdateError('{}\nRollback: {}'.format(detail, rollback_detail))
        # state/history باید پیش از لمس Passenger ذخیره شود؛ catch سطح بالا پس
        # از ثبت گزارش، نسخهٔ بازیابی‌شده را reload می‌کند.
        error.restart_required = True
        raise error from exc

    _cleanup_code_snapshot(code_snapshot)
    _cleanup_sqlite_backup(database_backup)
    _write_applied_commit(target_commit)

    _set_step(4, 'پاک‌سازی cache و آماده‌سازی ری‌استارت...')
    _clear_python_cache()
    _rebuild_assets()
    # Passenger فقط بعد از ذخیرهٔ state/history لمس می‌شود تا reload وسط گزارش
    # باعث ناپدیدشدن نتیجهٔ موفقیت نشود.
    restarted = _restart_enabled() and any(
        os.path.exists(os.path.join(BASE_DIR, name))
        for name in ('passenger_wsgi.py', 'wsgi.py'))
    new_info = _commit_info('HEAD') if method == 'git' else {
        'short': target_commit[:10], 'hash': target_commit,
        'message': '', 'date': '',
    }

    result = {
        'repo': _display_repo(repo),
        'branch': chosen,
        'method': method,
        'old_commit': old_commit,
        'new_commit': target_commit,
        'new_short': new_info['short'] or target_commit[:10],
        'changed_files': changed,
        'changed_count': len(changed) if changed else 0,
        'removed_files': removed,
        'removed_count': len(removed) if removed else 0,
        'required_files': sorted(set(_REQUIRED_FILES).intersection(files)),
        'migration': migration_msg,
        'smoke_test': smoke_msg,
        'dependencies': dependency_msg,
        'restart_requested': restarted,
        'backup_ref': backup_ref,
        'version': _read_version_txt(),
        'database': _database_kind(),
    }
    return result



def _success_message(result):
    """ساخت پیام موفقیت با جزئیات کامل."""
    restart = ('ری‌استارت Passenger درخواست شد.' if result.get('restart_requested')
               else 'ری‌استارت خودکار فعال نبود.')
    removed_count = result.get('removed_count', 0)
    removed_text = (' و {} فایل منسوخ حذف شد'.format(removed_count)
                    if removed_count else '')
    smoke = result.get('smoke_test', '')
    smoke_text = ' تست سلامت: {}'.format(smoke) if smoke else ''
    version = result.get('version') or _read_version_txt() or result.get('new_short') or '—'
    db_kind = result.get('database') or _database_kind()
    return (
        'بروزرسانی کامل شد ✅ نسخهٔ {} از شاخهٔ {} نصب شد؛ '
        '{} فایل تغییر کرد{}. {} وابستگی: {} مایگریشن [{}]: {}{}'
    ).format(
        version,
        result.get('branch', '—'),
        result.get('changed_count', 0),
        removed_text,
        restart,
        result.get('dependencies', '—'),
        db_kind,
        result.get('migration', '—'),
        smoke_text,
    )


def run_update(repo=None, branch=None):
    """اجرای مستقیم برای cron/CLI — خروجی ``(ok, message, report)``."""
    handle = _acquire_update_lock()
    if handle is None:
        return False, 'بروزرسانی دیگری در حال اجراست — کمی صبر کنید.', {}
    _load()
    _set_state(status='running', step=0, steps=4, msg='شروع بروزرسانی...', ok=False,
               report={})
    repo = repo or _git_remote()
    result = {}
    try:
        result = _perform_update(repo, branch)
        _set_state(status='done', step=4, ok=True, report=result,
                   msg=_success_message(result))
        _log_history(repo, result.get('migration'), success=True,
                     branch=result.get('branch'), old_commit=result.get('old_commit'),
                     new_commit=result.get('new_commit'),
                     changed_count=result.get('changed_count', 0),
                     dependencies=result.get('dependencies', ''),
                     method=result.get('method', ''))
        if result.get('restart_requested'):
            _touch_restart()
        return True, _success_message(result), result
    except Exception as exc:
        message = 'خطا در بروزرسانی: ' + _redact_text(str(exc), repo or '')[:2400]
        _set_state(status='error', ok=False, report=result, msg=message)
        _log_history(repo or '', '', success=False, error=message,
                     branch=branch or get_update_branch())
        if getattr(exc, 'restart_required', False):
            _touch_restart()
        return False, message, result
    finally:
        _release_update_lock(handle)


def start_update(repo=None, branch=None):
    """شروع بروزرسانی در پس‌زمینه — خروجی ``(started, message)`` برای پنل."""
    _load()
    with _state_lock:
        if (_state.get('status') == 'running' and
                time.time() - float(_state.get('_updated') or 0) < STALE_SECONDS):
            return False, 'بروزرسانی دیگری در حال اجراست — کمی صبر کنید.'

    # repo/branch در همان درخواست Flask resolve می‌شوند؛ Thread context ندارد.
    resolved_repo = repo or _git_remote()
    resolved_branch = branch or get_update_branch() or None
    handle = _acquire_update_lock()
    if handle is None:
        return False, 'بروزرسانی دیگری در حال اجراست — کمی صبر کنید.'
    _set_state(status='running', step=0, steps=4, msg='شروع بروزرسانی...', ok=False,
               report={})

    def _work():
        result = {}
        try:
            result = _perform_update(resolved_repo, resolved_branch)
            _set_state(status='done', step=4, ok=True, report=result,
                       msg=_success_message(result))
            _log_history(resolved_repo, result.get('migration'), success=True,
                         branch=result.get('branch'), old_commit=result.get('old_commit'),
                         new_commit=result.get('new_commit'),
                         changed_count=result.get('changed_count', 0),
                         dependencies=result.get('dependencies', ''),
                         method=result.get('method', ''))
            if result.get('restart_requested'):
                _touch_restart()
        except Exception as exc:
            message = 'خطا در بروزرسانی: ' + _redact_text(str(exc), resolved_repo or '')[:2400]
            _set_state(status='error', ok=False, report=result, msg=message)
            _log_history(resolved_repo or '', '', success=False, error=message,
                         branch=resolved_branch or '')
            if getattr(exc, 'restart_required', False):
                _touch_restart()
        finally:
            _release_update_lock(handle)

    try:
        threading.Thread(target=_work, name='academy-git-update', daemon=True).start()
    except Exception:
        _release_update_lock(handle)
        _set_state(status='error', ok=False, msg='شروع Thread بروزرسانی ممکن نشد.')
        return False, 'شروع بروزرسانی ممکن نشد.'
    return True, 'بروزرسانی در پس‌زمینه شروع شد.'


# ═══════════════════════════════════════════════════════════════════════════
# مایگریشن دیتابیس
# ═══════════════════════════════════════════════════════════════════════════
_NO_DEFAULT = object()


def _column_default_value(column):
    """مقدار قابل backfill برای ستون جدید؛ callableهای مدل را هم پشتیبانی می‌کند."""
    default = column.default
    if default is not None:
        value = getattr(default, 'arg', default)
        if callable(value):
            try:
                value = value()
            except TypeError:
                value = _NO_DEFAULT
            except Exception:
                value = _NO_DEFAULT
        if value is not _NO_DEFAULT and not hasattr(value, 'compile'):
            return value
    # server_default به‌صورت SQL در ALTER استفاده می‌شود و نیاز به bind ندارد.
    if column.server_default is not None:
        return _NO_DEFAULT
    # برای ستون nullable بدون default، NULL معنای معتبر دارد و نباید به‌صورت
    # حدسی با رشتهٔ خالی/صفر جایگزین شود.
    if column.nullable:
        return _NO_DEFAULT
    try:
        from sqlalchemy import (Boolean, Date, DateTime, Float, Integer, LargeBinary,
                                Numeric, String, Text)
        ctype = column.type
        if isinstance(ctype, Boolean):
            return False
        if isinstance(ctype, (Integer, Float, Numeric)):
            return 0
        if isinstance(ctype, (String, Text)):
            return ''
        if isinstance(ctype, DateTime):
            from models import utcnow
            return utcnow()
        if isinstance(ctype, Date):
            return datetime.now(UTC).date()
        if isinstance(ctype, LargeBinary):
            return b''
    except Exception:
        pass
    return _NO_DEFAULT


def _literal_default(column, dialect):
    """تبدیل default مدل به literal امن برای ALTER TABLE."""
    try:
        from sqlalchemy import literal, text as sa_text
        default = column.server_default
        if default is not None:
            arg = default.arg
            # server_default متنیِ امن (مثل CURRENT_TIMESTAMP) عیناً منتقل می‌شود؛
            # literal_binds آن را به رشتهٔ اشتباه تبدیل می‌کرد.
            if isinstance(arg, sa_text) and arg.text:
                raw = arg.text.strip()
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_()' .:+-]*", raw):
                    return raw
            if hasattr(arg, 'compile'):
                return str(arg.compile(dialect=dialect,
                                       compile_kwargs={'literal_binds': True}))
            return str(arg)
        value = _column_default_value(column)
        if value is _NO_DEFAULT:
            return None
        return str(literal(value).compile(
            dialect=dialect, compile_kwargs={'literal_binds': True}))
    except Exception:
        return None


def _column_ddl(column, dialect, with_default=True):
    preparer = dialect.identifier_preparer
    name = preparer.quote(column.name)
    coltype = column.type.compile(dialect=dialect)
    default_sql = _literal_default(column, dialect) if with_default else None
    # MySQL/MariaDB روی Text/Blob در نسخه‌های قدیمی DEFAULT را قبول نمی‌کنند.
    try:
        from sqlalchemy import LargeBinary, Text
        supports_default = not isinstance(column.type, (Text, LargeBinary))
    except Exception:
        supports_default = True
    pieces = [name, coltype]
    if default_sql and supports_default:
        pieces.append('DEFAULT ' + default_sql)
    # ستون non-null جدید بدون مقدار پیش‌فرض در جدول پر داده قابل ADD نیست.
    # default مدل یا fallback بالا این مشکل را حل می‌کند؛ اگر نشد، nullable می‌ماند
    # تا دادهٔ قبلی هرگز از بین نرود و درج‌های جدید توسط ORM کنترل شود.
    if not column.nullable and (default_sql and supports_default):
        pieces.append('NOT NULL')
    return ' '.join(pieces), default_sql if supports_default else None


def _quote_table(table, dialect):
    return dialect.identifier_preparer.quote(table.name)


def _migration_indexes(engine, metadata):
    """افزودن indexهای مدل به جدول‌های قدیمی؛ create_all این کار را نمی‌کند."""
    from sqlalchemy import inspect
    added = []
    warnings = []
    for table in metadata.sorted_tables:
        try:
            inspector = inspect(engine)
            existing = inspector.get_indexes(table.name)
            names = {i.get('name') for i in existing}
            signatures = {tuple(i.get('column_names') or []) for i in existing}
        except Exception:
            continue
        for index in sorted(table.indexes, key=lambda x: x.name or ''):
            if not index.name:
                continue
            signature = tuple(col.name for col in index.columns)
            if index.name in names or signature in signatures:
                continue
            try:
                index.create(bind=engine, checkfirst=True)
                added.append(index.name)
                names.add(index.name)
                signatures.add(signature)
            except Exception as exc:
                # شکست index نباید داده یا جدول را خراب کند؛ در گزارش شفاف می‌آید.
                warnings.append('{}: {}'.format(index.name, str(exc)[:140]))
    return added, warnings


def _column_exists(engine, table_name, column_name):
    """آیا ستون در جدول هست؟ (استعلام تازه — برای تحمل race بین workerها)"""
    from sqlalchemy import inspect
    return column_name in {
        c['name'] for c in inspect(engine).get_columns(table_name)}


def _safe_add_column(engine, table, column):
    """افزودن یک ستون با تحمل race و محدودیت‌های SQLite/MySQL.

    خروجی: ``'added'`` | ``'exists'`` | ``'added_nullable'``
    * اگر worker دیگری همان ستون را افزوده باشد → 'exists' (خطا نیست).
    * اگر SQLite «default غیرثابت» را رد کند → ستون nullable اضافه و backfill
      جدا انجام می‌شود؛ هیچ‌وقت داده از بین نمی‌رود.
    """
    from sqlalchemy import text
    ddl, _default_sql = _column_ddl(column, engine.dialect)
    table_sql = _quote_table(table, engine.dialect)
    sql = 'ALTER TABLE {} ADD COLUMN {}'.format(table_sql, ddl)
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        return 'added'
    except Exception as exc:
        # race: شاید worker دیگر (یا retry قبلی) همین ستون را افزوده است.
        try:
            if _column_exists(engine, table.name, column.name):
                return 'exists'
        except Exception:
            pass
        error_text = str(exc).lower()
        # SQLite: DEFAULT غیرثابت (مثلاً utcnow پایتون) در ADD COLUMN مجاز نیست؛
        # fallback: ستون nullable بدون default + backfill.
        if engine.dialect.name == 'sqlite' and (
                'non-constant default' in error_text or
                'cannot add a column with non-constant default' in error_text):
            ddl_nullable, _ = _column_ddl(column, engine.dialect, with_default=False)
            sql_nullable = 'ALTER TABLE {} ADD COLUMN {}'.format(table_sql, ddl_nullable)
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql_nullable))
                return 'added_nullable'
            except Exception as retry_exc:
                try:
                    if _column_exists(engine, table.name, column.name):
                        return 'exists'
                except Exception:
                    pass
                raise UpdateError('افزودن ستون {}.{} شکست خورد: {}'.format(
                    table.name, column.name, str(retry_exc)[:240])) from retry_exc
        raise UpdateError('افزودن ستون {}.{} شکست خورد: {}'.format(
            table.name, column.name, error_text[:240])) from exc


def _backfill_column(engine, table, column):
    """پرکردن NULLهای ستون تازه‌اضافه‌شده با default مدل — همیشه bind پارامتر."""
    from sqlalchemy import text
    value = _column_default_value(column)
    if value is _NO_DEFAULT or value is None:
        return 0
    table_sql = _quote_table(table, engine.dialect)
    col_sql = engine.dialect.identifier_preparer.quote(column.name)
    with engine.begin() as conn:
        result = conn.execute(text(
            'UPDATE {} SET {} = :migration_default WHERE {} IS NULL'.format(
                table_sql, col_sql, col_sql)),
            {'migration_default': value})
        return int(result.rowcount or 0)


def _run_data_migrations(engine, progress_cb=None):
    """اجرای مایگریشن‌های داده‌ای نسخه‌بندی‌شده از پوشهٔ ``migrations/``.

    هر فایل ``NNNN_*.py`` باید تابع ``up(conn)`` داشته باشد که روی اتصالِ
    داخل تراکنش اجرا می‌شود. نسخه‌های
    اعمال‌شده در جدول ``schema_migrations`` ثبت می‌شوند و هر نسخه فقط یک بار
    اجرا می‌شود (idempotent حتی با چند worker). شکست هر مایگریشن، کل
    بروزرسانی را متوقف می‌کند تا دادهٔ سایت سالم بماند.
    """
    from sqlalchemy import text
    applied_versions = []
    try:
        with engine.begin() as conn:
            conn.execute(text(
                'CREATE TABLE IF NOT EXISTS schema_migrations ('
                'version VARCHAR(120) NOT NULL, '
                'applied_at DATETIME NOT NULL, '
                'PRIMARY KEY (version))'
            ))
        with engine.connect() as conn:
            for row in conn.execute(text('SELECT version FROM schema_migrations')):
                applied_versions.append(row[0])
    except Exception as exc:
        raise UpdateError('ساخت/خواندن جدول schema_migrations شکست خورد: {}'.format(
            str(exc)[:240])) from exc

    if not os.path.isdir(MIGRATIONS_DIR):
        return []

    ran = []
    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        if not name.endswith('.py') or name.startswith('_'):
            continue
        match = re.match(r'^(\d{4})[_-]', name)
        if not match:
            continue
        version = match.group(1)
        if version in applied_versions:
            continue
        path = os.path.join(MIGRATIONS_DIR, name)
        namespace = {'__file__': path, '__name__': 'migration_' + version}
        try:
            with open(path, encoding='utf-8') as f:
                code = f.read()
            exec(compile(code, path, 'exec'), namespace)
            up = namespace.get('up')
            if not callable(up):
                continue
            with engine.begin() as conn:
                up(conn)
                conn.execute(
                    text('INSERT INTO schema_migrations (version, applied_at) '
                         'VALUES (:v, :at)'),
                    {'v': version, 'at': datetime.now(UTC).isoformat()})
        except Exception as exc:
            raise UpdateError('مایگریشن داده‌ای {} شکست خورد: {}'.format(
                name, str(exc)[:240])) from exc
        ran.append(name)
        applied_versions.append(version)
        if progress_cb:
            try:
                progress_cb(name)
            except Exception:
                pass
    return ran


def _migrate_db(engine=None, progress_cb=None):
    """همگام‌سازی idempotent ساختار دیتابیس با ``db.metadata``.

    ویژگی‌ها:
      * جدول جدید: با ``create_all`` ساخته می‌شود (هرگز DROP نمی‌شود).
      * ستون جدید: با نوع واقعی dialect اضافه و مقدار پیش‌فرض امن برای رکوردهای
        قبلی backfill می‌شود؛ race بین workerها و محدودیت‌های SQLite
        (default غیرثابت) مدیریت می‌شود.
      * index جدید: برای جدول‌های قدیمی نیز ساخته می‌شود.
      * مایگریشن‌های داده‌ای نسخه‌بندی‌شده (migrations/) بعد از ساختار اجرا
        می‌شوند؛ هر نسخه فقط یک بار.
      * هیچ DROP/DELETE روی دادهٔ موجود انجام نمی‌شود؛ فقط NULL ستون
        تازه‌اضافه‌شده با default مدل پر می‌شود.
      * خطا دیگر به شکل «موفق» پنهان نمی‌شود و exception به caller می‌رسد.
    """
    from sqlalchemy import inspect
    from models import db

    try:
        db.session.remove()
    except Exception:
        pass
    engine = engine or db.engine
    metadata = db.metadata
    try:
        before = set(inspect(engine).get_table_names())
        metadata.create_all(bind=engine)
        after = set(inspect(engine).get_table_names())
        created_tables = sorted(after - before)

        added_columns = []
        backfilled = 0
        warnings = []
        done = 0
        for table in metadata.sorted_tables:
            if table.name not in after:
                continue
            existing = {c['name'] for c in inspect(engine).get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or column.primary_key:
                    continue
                result = _safe_add_column(engine, table, column)
                if result == 'exists':
                    existing.add(column.name)
                    continue
                added_columns.append('{}.{}'.format(table.name, column.name))
                # اگر dialect مقدار پیش‌فرض را نپذیرفت (Text یا SQLite nullable
                # fallback)، مقدار bind شده را برای رکوردهای قبلی تکمیل می‌کنیم؛
                # هرگز رشته را وارد SQL نمی‌کنیم.
                try:
                    backfilled += _backfill_column(engine, table, column)
                except Exception as exc:
                    raise UpdateError('تکمیل دادهٔ ستون {}.{} شکست خورد: {}'.format(
                        table.name, column.name, str(exc)[:240])) from exc
                existing.add(column.name)
                done += 1
                if progress_cb and done % 5 == 0:
                    try:
                        progress_cb(done)
                    except Exception:
                        pass

        added_indexes, index_warnings = _migration_indexes(engine, metadata)
        warnings.extend(index_warnings)

        # مایگریشن‌های داده‌ای نسخه‌بندی‌شده — بعد از ساختار، در تراکنش‌های جدا.
        data_migrations = _run_data_migrations(engine, progress_cb=progress_cb)
        try:
            db.session.remove()
        except Exception:
            pass
        report = []
        if created_tables:
            report.append('{} جدول جدید'.format(len(created_tables)))
        if added_columns:
            report.append('{} ستون جدید'.format(len(added_columns)))
        if backfilled:
            report.append('{} مقدار داده تکمیل شد'.format(backfilled))
        if added_indexes:
            report.append('{} ایندکس جدید'.format(len(added_indexes)))
        if data_migrations:
            report.append('{} مایگریشن داده‌ای'.format(len(data_migrations)))
        if warnings:
            report.append('{} هشدار ایندکس'.format(len(warnings)))
        if not report:
            report.append('ساختار و داده‌ها به‌روز بودند')
        result = '[{}] ('.format(engine.dialect.name) + '، '.join(report) + ')'
        if warnings:
            result += ' هشدار: ' + ' | '.join(warnings[:3])
        return result
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError('مایگریشن دیتابیس شکست خورد: ' + str(exc)[:300]) from exc
    finally:
        try:
            db.session.remove()
        except Exception:
            pass


def test_git_repo(url):
    """تست اتصال عمومی/خصوصی به مخزن Git، بدون ذخیره یا نمایش توکن."""
    try:
        repo = _validate_repo_url(url)
        _remote_refs(repo, heads=False)
        return True, 'اتصال به مخزن گیت موفقیت‌آمیز بود ✅ (دسترسی برقرار است)'
    except Exception as exc:
        msg = _redact_text(str(exc), url or '')
        low = msg.lower()
        if any(x in low for x in ('authentication', 'could not read username',
                                  'permission denied', 'access denied', 'terminal prompts disabled')):
            return False, ('احراز هویت مخزن ناموفق بود. برای مخزن خصوصی از SSH Deploy Key '
                           'یا متغیر محیطی امن استفاده کنید؛ توکن را داخل تاریخچه ذخیره نکنید.')
        return False, 'خطا در اتصال به مخزن: ' + msg[-300:]


if __name__ == '__main__':  # برای cron: python updater.py [--check|--run]
    import argparse
    parser = argparse.ArgumentParser(description='Academy Git updater')
    parser.add_argument('--check', action='store_true', help='فقط بررسی نسخه')
    parser.add_argument('--run', action='store_true', help='اجرای synchronous بروزرسانی')
    parser.add_argument('--branch', default='', help='شاخهٔ هدف')
    args = parser.parse_args()
    if args.check:
        try:
            print(json.dumps(check_for_update(branch=args.branch), ensure_ascii=False))
            raise SystemExit(0)
        except Exception as exc:
            print(json.dumps({'ok': False, 'msg': str(exc)}, ensure_ascii=False))
            raise SystemExit(1)
    ok, msg, _report = run_update(branch=args.branch or None)
    print(msg)
    raise SystemExit(0 if ok else 1)
