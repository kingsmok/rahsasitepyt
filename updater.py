# -*- coding: utf-8 -*-
"""سیستم امن و قابل‌اعتماد بروزرسانی برنامه از Git/GitHub.

این ماژول دو کار جدا را انجام می‌دهد:

* دریافت نسخهٔ جدید کد از GitHub (به‌صورت دستی از پنل یا خودکار از Webhook).
* همگام‌سازی ساختار دیتابیس با مدل‌های نسخهٔ جدید، بدون حذف داده‌های قبلی.

نکتهٔ مهم: مایگریشن در یک پردازش جدا اجرا می‌شود. چون بعد از ``git reset``
ماژول‌های پایتونِ پردازش وب هنوز نسخهٔ قدیمی را در حافظه دارند، اجرای مایگریشن
در همان Thread باعث می‌شد ستون‌های نسخهٔ جدید اصلاً دیده نشوند.
"""
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
STALE_SECONDS = 1800  # مایگریشن دیتابیس‌های بزرگ ممکن است چند دقیقه طول بکشد.
UPDATE_REF_PREFIX = 'refs/remotes/academy-update'
_REQUIRED_FILES = ('app.py', 'models.py', 'passenger_wsgi.py')
_PRESERVE_FILES = ('instance/.update_progress.json', 'instance/update_history.json',
                   'instance/.update_commit')
_BRANCH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')
_OVERLAY_SKIP = {
    '.env', '.env.local', '.htaccess', '.git',
    'instance', 'uploads', 'venv', '.venv', 'env', 'logs',
    '__pycache__', 'node_modules',
}
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


def update_progress():
    """وضعیت فعلی بروزرسانی را از فایل مشترک برمی‌گرداند.
    
    این تابع توسط polling فرانت‌اند فراخوانی می‌شود.
    """
    _load()
    with _state_lock:
        st = dict(_state)
    st.pop('_updated', None)
    st['stale'] = False
    updated = float(st.get('_updated') or 0)
    if st.get('status') == 'running' and time.time() - updated > STALE_SECONDS:
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


def _git_env():
    env = os.environ.copy()
    # روی هاست، git نباید وسط درخواست منتظر Username/Password بماند.
    env['GIT_TERMINAL_PROMPT'] = '0'
    env.setdefault('LC_ALL', 'C')
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


def _local_version():
    """هش نسخهٔ فعلی: HEAD گیت یا آخرین commit اعمال‌شده از بروزرسانی ZIP."""
    return _current_commit('HEAD') or _read_applied_commit()


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
                           timeout=timeout, env=env or _git_env())
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return -1, 'timeout'
    except Exception as e:
        return -2, str(e)


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
    return {
        'branch': branch,
        'target_branch': get_update_branch() or 'تشخیص خودکار',
        'remote': _display_repo(remote),
        'commit_hash': info['short'],
        'commit_msg': info['message'],
        'commit_date': info['date'],
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
    import errno
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
    به‌عنوان «جدید» برگردانده می‌شوند.
    """
    if not new_ref:
        return []
    
    if not old_commit:
        # نصب اولیه: همه فایل‌های پروژه رو لیست کن
        files = []
        for root, dirs, filenames in os.walk(BASE_DIR):
            # حذف پوشه‌های که نباید تغییر کنند
            dirs[:] = [d for d in dirs if d not in _OVERLAY_SKIP and d not in ('.git',)]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
                if rel and rel not in _OVERLAY_SKIP and not rel.startswith('.'):
                    files.append(rel.replace('\\', '/'))
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


def _requirements_changed(old_commit, old_requirements=None):
    old = old_requirements
    if old is None and old_commit:
        old = _git_file(old_commit, 'requirements.txt')
    new = _read_local_requirements()
    return old is not None and new is not None and old != new


def _install_changed_dependencies(old_commit, old_requirements=None):
    if not _requirements_changed(old_commit, old_requirements=old_requirements):
        return 'وابستگی‌ها تغییری نکرده‌اند.'
    flag = os.environ.get('UPDATE_INSTALL_DEPENDENCIES', '1').strip().lower()
    if flag in ('0', 'false', 'no', 'off'):
        return 'نصب وابستگی‌ها طبق تنظیم UPDATE_INSTALL_DEPENDENCIES غیرفعال است.'
    pip_timeout = int(os.environ.get('PIP_INSTALL_TIMEOUT', '900'))
    code, out = _run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                     timeout=pip_timeout, env={**_git_env(), 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    if code != 0:
        raise UpdateError('نصب وابستگی‌های جدید شکست خورد: ' + _redact_text(out[-500:]))
    return 'وابستگی‌های جدید نصب شدند.'


def _run_fresh_migration():
    """مایگریشن را با import تازهٔ مدل‌ها در یک پردازش جدا اجرا می‌کند.
    
    این تابع مهم است چون بعد از git reset، پردازش وب هنوز نسخهٔ قدیمی کد را
    در حافظه دارد. اجرای مایگریشن در همان پردازش باعث می‌شود ستون‌های جدید
    دیده نشوند.
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
    
    env = _git_env()
    env['PYTHONPATH'] = BASE_DIR + os.pathsep + env.get('PYTHONPATH', '')
    
    # اجرا با timeout بلندتر برای دیتابیس‌های بزرگ
    timeout = int(os.environ.get('DB_MIGRATION_TIMEOUT', '900'))
    
    code, out = _run(cmd, timeout=timeout, env=env)
    
    if code != 0:
        # اگر خطای پایتون است، جزئیات بیشتری برگردان
        error_lines = out.strip().split('\n')
        error_msg = '\n'.join(error_lines[-10:]) if len(error_lines) > 10 else out
        raise UpdateError('مایگریشن دیتابیس شکست خورد:\n' + _redact_text(error_msg[-1200:]))
    
    return out.strip()[-1200:] or 'مایگریشن انجام شد.'


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


def _download_file(url, dest, token='', timeout=180):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'rahsasitepyt-updater',
        'Accept': 'application/zip, */*',
    })
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, 'wb') as handle:
        shutil.copyfileobj(resp, handle)
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
    # استثناء امنیتی: فایل .htaccess محافظ پوشهٔ آپلود باید همیشه به‌روزرسانی شود.
    # بدون آن، روی هاست آپاچی فایل‌های آپلودی (php/html/svg) اجرا می‌شوند و
    # دامنه توسط Google Safe Browsing با «Dangerous site» مسدود می‌گردد.
    if rel.endswith('/.htaccess'):
        return False
    return rel == 'static/uploads' or rel.startswith('static/uploads/')


def _overlay_tree(src_root, dest_root):
    """کپی فایل‌های آرشیو روی سایت، بدون دست‌زدن به .env / instance / آپلود / venv."""
    changed = []
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel_dir = os.path.relpath(dirpath, src_root)
        if rel_dir == '.':
            rel_dir = ''
        kept = []
        for name in dirnames:
            rel = (rel_dir + '/' + name).replace('\\', '/').lstrip('/') if rel_dir else name
            if not _overlay_skip(rel):
                kept.append(name)
        dirnames[:] = kept
        for filename in filenames:
            rel = (rel_dir + '/' + filename).replace('\\', '/').lstrip('/') if rel_dir else filename
            if _overlay_skip(rel):
                continue
            source = os.path.join(dirpath, filename)
            dest = os.path.join(dest_root, *rel.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(source, dest)
            changed.append(rel)
    return changed


def _apply_github_archive(repo, branch):
    """جایگزینی کد از ZIP گیت‌هاب — برای نصب‌های سی‌پنل بدون پوشهٔ .git."""
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
                _download_file(url, zip_path, token=info['token'])
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
        missing = [name for name in _REQUIRED_FILES
                   if not os.path.isfile(os.path.join(root, name))]
        if missing:
            raise UpdateError('آرشیو مخزن فایل‌های ضروری را ندارد: ' + '، '.join(missing))
        changed = _overlay_tree(root, BASE_DIR)
        files = set()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _OVERLAY_SKIP]
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), root)
                files.add(rel.replace('\\', '/'))
        commit = ''
        try:
            refs, _ = _remote_refs(repo, heads=True)
            commit = refs.get(branch, '')
        except Exception:
            commit = ''
        return commit, files, changed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_for_update(repo_url=None, branch=None):
    """بررسی نسخهٔ GitHub بدون تغییر کد یا دیتابیس (برای دکمهٔ «بررسی»)."""
    repo = _validate_repo_url(repo_url or _git_remote())
    chosen = _select_branch(repo, branch)
    refs, _ = _remote_refs(repo, heads=True)
    remote_commit = refs.get(chosen, '')
    if not remote_commit:
        raise UpdateError('شاخهٔ «{}» در مخزن پیدا نشد.'.format(chosen))
    local_commit = _local_version()
    available = bool(remote_commit and remote_commit != local_commit)
    if not local_commit:
        msg = 'نسخهٔ محلی ثبت نشده (نصب ZIP). نسخهٔ مخزن آمادهٔ نصب است.'
        available = True
    elif available:
        msg = 'نسخهٔ جدید موجود است.'
    else:
        msg = 'کد سایت با آخرین نسخهٔ مخزن یکسان است.'
    return {
        'ok': True,
        'available': available,
        'branch': chosen,
        'local_commit': local_commit,
        'remote_commit': remote_commit,
        'local_short': local_commit[:10] if local_commit else '',
        'remote_short': remote_commit[:10],
        'repo': _display_repo(repo),
        'git_worktree': _is_git_worktree(),
        'msg': msg,
    }


def _set_step(step, msg):
    """ثبت مرحله فعلی بروزرسانی برای نمایش در فرانت‌اند.
    
    step: 1=دریافت کد، 2=جایگزینی، 3=مایگریشن، 4=پاک‌سازی
    """
    _set_state(step=step, msg=msg, status='running')


def _perform_update(repo, branch=None):
    """اجرای synchronous عملیات؛ هم Thread وب و هم cron/CLI از همین استفاده می‌کنند."""
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

    method = 'git'
    files = set()
    changed = []
    target_commit = ''
    git_error = None
    try:
        if not _ensure_local_git():
            raise UpdateError('دستور git روی این هاست در دسترس نیست.')
        target_ref, target_commit = _fetch_target(repo, chosen)
        files = _verify_target(target_ref)
        changed = _changed_files(old_commit, target_ref)
        _set_step(2, 'جایگزینی فایل‌های برنامه با نسخهٔ تاییدشده...')
        code, out = _git(['reset', '--hard', target_ref], timeout=120)
        if code != 0:
            raise UpdateError('جایگزینی کدها شکست خورد: ' + _redact_text(out[-400:], repo))
    except Exception as exc:
        git_error = exc
        if not _parse_github(repo):
            if isinstance(exc, UpdateError):
                raise
            raise UpdateError(str(exc)) from exc
        _set_step(2, 'دریافت آرشیو GitHub و جایگزینی کدها (بدون مخزن محلی)...')
        try:
            target_commit, files, changed = _apply_github_archive(repo, chosen)
        except Exception as archive_exc:
            git_msg = _redact_text(str(git_error), repo)[:280]
            arch_msg = _redact_text(str(archive_exc), repo)[:280]
            raise UpdateError(
                'بروزرسانی شکست خورد. گیت: {} | آرشیو: {}'.format(git_msg, arch_msg)
            ) from archive_exc
        method = 'archive'
    _restore_local_files(preserved)
    _write_applied_commit(target_commit)

    dependency_msg = _install_changed_dependencies(
        old_commit, old_requirements=old_requirements)

    _set_step(3, 'اجرای مایگریشن ساختار و داده‌های دیتابیس...')
    migration_msg = _run_fresh_migration()

    _set_step(4, 'پاک‌سازی cache و آماده‌سازی ری‌استارت...')
    _clear_python_cache()
    # Passenger فقط بعد از ذخیرهٔ state/history لمس می‌شود تا reload وسط گزارش
    # باعث ناپدیدشدن نتیجهٔ موفقیت نشود.
    restarted = _restart_enabled() and any(
        os.path.exists(os.path.join(BASE_DIR, name))
        for name in ('passenger_wsgi.py', 'wsgi.py'))
    new_info = _commit_info('HEAD')
    
    # اگه فایل‌ها تغییری نکرده، همه فایل‌ها رو لیست کن
    if not changed and target_commit:
        try:
            changed = _changed_files('', target_ref) if '_git' in dir() and old_commit else []
            if not changed:
                # همه فایل‌های پروژه رو لیست کن
                for root, dirs, filenames in os.walk(BASE_DIR):
                    dirs[:] = [d for d in dirs if d not in _OVERLAY_SKIP and d not in ('.git',)]
                    for f in filenames:
                        rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
                        if rel not in _OVERLAY_SKIP:
                            changed.append(rel.replace('\\', '/'))
        except Exception:
            pass
    
    result = {
        'repo': _display_repo(repo),
        'branch': chosen,
        'method': method,
        'old_commit': old_commit,
        'new_commit': target_commit,
        'new_short': new_info['short'] or target_commit[:10],
        'changed_files': changed,
        'changed_count': len(changed) if changed else 0,
        'required_files': sorted(set(_REQUIRED_FILES).intersection(files)),
        'migration': migration_msg,
        'dependencies': dependency_msg,
        'restart_requested': restarted,
        'backup_ref': backup_ref,
    }
    return result


def _success_message(result):
    """ساخت پیام موفقیت با جزئیات کامل."""
    restart = 'ری‌استارت Passenger درخواست شد.' if result.get('restart_requested') else 'ری‌استارت خودکار فعال نبود.'
    method = result.get('method', 'git')
    method_text = ' (روش: Git)' if method == 'git' else ' (روش: آرشیو GitHub)'
    return (
        'بروزرسانی کامل شد ✅ نسخهٔ {} از شاخهٔ {} نصب شد؛ '
        '{} فایل تغییر کرد. {}{}'
    ).format(
        result.get('new_short', '—'),
        result.get('branch', '—'),
        result.get('changed_count', 0),
        restart,
        result.get('migration', '')
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
                     dependencies=result.get('dependencies', ''))
        if result.get('restart_requested'):
            _touch_restart()
        return True, _success_message(result), result
    except Exception as exc:
        message = 'خطا در بروزرسانی: ' + _redact_text(str(exc), repo or '')[:900]
        _set_state(status='error', ok=False, report=result, msg=message)
        _log_history(repo or '', '', success=False, error=message,
                     branch=branch or get_update_branch())
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
            message = 'خطا در بروزرسانی: ' + _redact_text(str(exc), resolved_repo or '')[:900]
            _set_state(status='error', ok=False, report=result, msg=message)
            _log_history(resolved_repo or '', '', success=False, error=message,
                         branch=resolved_branch or '')
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
        from sqlalchemy import literal
        default = column.server_default
        if default is not None:
            arg = default.arg
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


def _column_ddl(column, dialect):
    preparer = dialect.identifier_preparer
    name = preparer.quote(column.name)
    coltype = column.type.compile(dialect=dialect)
    default_sql = _literal_default(column, dialect)
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


def _migrate_db():
    """همگام‌سازی idempotent ساختار دیتابیس با ``db.metadata``.

    ویژگی‌ها:
      * جدول جدید: با ``create_all`` ساخته می‌شود.
      * ستون جدید: با نوع واقعی dialect اضافه و مقدار پیش‌فرض امن برای رکوردهای
        قبلی backfill می‌شود.
      * index جدید: برای جدول‌های قدیمی نیز ساخته می‌شود.
      * هیچ DROP/DELETE/UPDATE روی دادهٔ موجود انجام نمی‌شود؛ فقط NULL ستون
        تازه‌اضافه‌شده با default مدل پر می‌شود.
      * خطا دیگر به شکل «موفق» پنهان نمی‌شود و exception به caller می‌رسد.
    """
    from sqlalchemy import inspect, text
    from models import db

    try:
        db.session.remove()
    except Exception:
        pass
    engine = db.engine
    metadata = db.metadata
    try:
        before = set(inspect(engine).get_table_names())
        metadata.create_all(bind=engine)
        after = set(inspect(engine).get_table_names())
        created_tables = sorted(after - before)

        added_columns = []
        backfilled = 0
        warnings = []
        for table in metadata.sorted_tables:
            if table.name not in after:
                continue
            existing = {c['name'] for c in inspect(engine).get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or column.primary_key:
                    continue
                ddl, default_sql = _column_ddl(column, engine.dialect)
                table_sql = _quote_table(table, engine.dialect)
                sql = 'ALTER TABLE {} ADD COLUMN {}'.format(table_sql, ddl)
                try:
                    with engine.begin() as conn:
                        conn.execute(text(sql))
                except Exception as exc:
                    raise UpdateError('افزودن ستون {}.{} شکست خورد: {}'.format(
                        table.name, column.name, str(exc)[:240])) from exc
                added_columns.append('{}.{}'.format(table.name, column.name))
                # اگر dialect مقدار پیش‌فرض را برای Text نپذیرفت، مقدار bind شده را
                # برای رکوردهای قبلی تکمیل می‌کنیم؛ هرگز رشته را وارد SQL نمی‌کنیم.
                value = _column_default_value(column)
                if value is not _NO_DEFAULT and value is not None:
                    try:
                        col_sql = engine.dialect.identifier_preparer.quote(column.name)
                        with engine.begin() as conn:
                            result = conn.execute(text(
                                'UPDATE {} SET {} = :migration_default WHERE {} IS NULL'.format(
                                    table_sql, col_sql, col_sql)),
                                {'migration_default': value})
                            if result.rowcount and result.rowcount > 0:
                                backfilled += result.rowcount
                    except Exception as exc:
                        raise UpdateError('تکمیل دادهٔ ستون {}.{} شکست خورد: {}'.format(
                            table.name, column.name, str(exc)[:240])) from exc
                existing.add(column.name)

        added_indexes, index_warnings = _migration_indexes(engine, metadata)
        warnings.extend(index_warnings)
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
        if warnings:
            report.append('{} هشدار ایندکس'.format(len(warnings)))
        if not report:
            report.append('ساختار و داده‌ها به‌روز بودند')
        result = '(' + '، '.join(report) + ')'
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
