# -*- coding: utf-8 -*-
"""لایسنس تجاری آفلاین با امضای Ed25519 و اتصال به دامنه.

کلید خصوصی هرگز نباید همراه محصول توزیع شود. برنامه فقط کلید عمومی را دارد و
توکن امضاشده را اعتبارسنجی می‌کند. نبود کلید عمومی یعنی حالت community/legacy؛
وجود کلید عمومی یا ``LICENSE_ENFORCEMENT=1`` کنترل لایسنس را فعال می‌کند.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
try:
    from datetime import UTC
except ImportError:  # Python 3.8-3.10
    from datetime import timezone as _timezone
    UTC = _timezone.utc
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PUBLIC_KEY_FILE = BASE_DIR / 'license_public_key.pem'
DEFAULT_LICENSE_FILE = BASE_DIR / 'instance' / 'license.json'
_TOKEN_PREFIX = 'AC1'
_LICENSE_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$')


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _b64decode(value: str) -> bytes:
    if not isinstance(value, str) or len(value) > 16_384:
        raise ValueError('بخش لایسنس نامعتبر است.')
    padding = '=' * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise ValueError('کدگذاری لایسنس نامعتبر است.') from exc


def normalize_domain(value: str) -> str:
    """Host/URL را به hostname معتبر، کوچک و بدون پورت تبدیل می‌کند."""
    value = str(value or '').strip().lower()
    try:
        if '://' in value:
            from urllib.parse import urlsplit
            value = urlsplit(value).hostname or ''
        elif value.startswith('[') and ']' in value:
            closing = value.index(']')
            suffix = value[closing + 1:]
            if suffix:
                port = suffix[1:] if suffix.startswith(':') else ''
                if not port.isdigit() or not 0 < int(port) <= 65535:
                    return ''
            value = value[1:closing]
        elif value.count(':') == 1:
            host, port = value.rsplit(':', 1)
            if not port.isdigit() or not 0 < int(port) <= 65535:
                return ''
            value = host
    except (TypeError, ValueError):
        return ''
    value = value.rstrip('.')
    if not value or len(value) > 253 or any(char in value for char in '/\\?#@'):
        return ''
    try:
        # IPv4/IPv6 با فرم canonical؛ localhost برای نصب و توسعه مجاز است.
        return ipaddress.ip_address(value).compressed.lower()
    except ValueError:
        pass
    try:
        ascii_value = value.encode('idna').decode('ascii')
    except UnicodeError:
        return ''
    if ascii_value == 'localhost':
        return ascii_value
    labels = ascii_value.split('.')
    if any(not re.match(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$', label)
           for label in labels):
        return ''
    return ascii_value


def domain_matches(current: str, licensed_domains: List[str]) -> bool:
    current = normalize_domain(current)
    if not current:
        return False
    for raw in licensed_domains or []:
        pattern = normalize_domain(str(raw)[2:] if str(raw).startswith('*.') else str(raw))
        if raw == '*':
            return True
        if not pattern:
            continue
        if str(raw).startswith('*.'):
            if current.endswith('.' + pattern) and current != pattern:
                return True
        elif current == pattern:
            return True
    return False


def _parse_iso_date(value: Any) -> Optional[date]:
    if value in (None, '', 0):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError('تاریخ لایسنس معتبر نیست.')


def _canonical_payload(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def load_public_key(value: Union[str, bytes]) -> Ed25519PublicKey:
    raw = value.encode('utf-8') if isinstance(value, str) else bytes(value)
    raw = raw.strip()
    try:
        if raw.startswith(b'-----BEGIN'):
            key = serialization.load_pem_public_key(raw)
        else:
            key = Ed25519PublicKey.from_public_bytes(_b64decode(raw.decode('ascii')))
    except Exception as exc:
        raise ValueError('کلید عمومی لایسنس معتبر نیست.') from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('کلید عمومی باید از نوع Ed25519 باشد.')
    return key


def load_private_key(value: Union[str, bytes], password: Optional[bytes] = None) -> Ed25519PrivateKey:
    raw = value.encode('utf-8') if isinstance(value, str) else bytes(value)
    try:
        key = serialization.load_pem_private_key(raw, password=password)
    except Exception as exc:
        raise ValueError('کلید خصوصی معتبر نیست.') from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('کلید خصوصی باید از نوع Ed25519 باشد.')
    return key


def issue_token(private_key: Ed25519PrivateKey, payload: Dict[str, Any]) -> str:
    """صدور توکن؛ فقط ابزار فروشنده باید این تابع را با private key صدا بزند."""
    data = dict(payload or {})
    data.setdefault('v', 1)
    data.setdefault('issued_at', datetime.now(UTC).date().isoformat())
    data.setdefault('plan', 'standard')
    data.setdefault('features', ['*'])
    if data.get('v') != 1:
        raise ValueError('نسخه payload پشتیبانی نمی‌شود.')
    if not _LICENSE_ID_RE.match(str(data.get('license_id') or '')):
        raise ValueError('شناسه لایسنس نامعتبر است.')
    domains = data.get('domains')
    if not isinstance(domains, list) or not domains or len(domains) > 20:
        raise ValueError('حداقل یک دامنه معتبر لازم است.')
    normalized = []
    for domain in domains:
        raw = str(domain).strip()
        if raw == '*':
            normalized.append('*')
            continue
        wildcard = raw.startswith('*.')
        clean = normalize_domain(raw[2:] if raw.startswith('*.') else raw)
        if not clean:
            raise ValueError('دامنه لایسنس نامعتبر است.')
        normalized.append(('*.' if wildcard else '') + clean)
    data['domains'] = sorted(set(normalized))
    _parse_iso_date(data.get('expires_at'))
    body = _canonical_payload(data)
    if len(body) > 8 * 1024:
        raise ValueError('اطلاعات لایسنس بیش از حد بزرگ است.')
    signature = private_key.sign(body)
    return f'{_TOKEN_PREFIX}.{_b64encode(body)}.{_b64encode(signature)}'


@dataclass(frozen=True)
class LicenseState:
    configured: bool
    enforced: bool
    valid: bool
    code: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    domain: str = ''

    @property
    def plan(self) -> str:
        return str(self.payload.get('plan') or '')

    @property
    def license_id(self) -> str:
        return str(self.payload.get('license_id') or '')

    @property
    def expires_at(self) -> str:
        return str(self.payload.get('expires_at') or '')

    @property
    def customer(self) -> str:
        return str(self.payload.get('customer') or '')

    def has_feature(self, name: str) -> bool:
        features = self.payload.get('features') or []
        return self.valid and isinstance(features, list) and (
            '*' in features or str(name) in features)

    def as_public_dict(self) -> Dict[str, Any]:
        license_id = self.license_id
        masked_id = (license_id[:4] + '…' + license_id[-4:]
                     if len(license_id) > 10 else license_id)
        return {
            'configured': self.configured, 'enforced': self.enforced,
            'valid': self.valid, 'code': self.code, 'message': self.message,
            'domain': self.domain, 'plan': self.plan,
            'license_id': masked_id, 'expires_at': self.expires_at,
        }


class LicenseManager:
    def __init__(self, public_key: Optional[Union[str, bytes, Ed25519PublicKey]] = None,
                 license_file: Optional[Union[str, os.PathLike]] = None,
                 enforcement: Optional[bool] = None):
        self.license_file = Path(license_file or
                                 os.environ.get('LICENSE_FILE') or
                                 DEFAULT_LICENSE_FILE)
        self._key_error = ''
        manifest_path = Path(os.environ.get('COMMERCIAL_BUILD_MANIFEST') or
                             (BASE_DIR / 'COMMERCIAL-BUILD.json'))
        self._commercial_manifest = manifest_path.is_file()
        self._expected_fingerprint = ''
        if self._commercial_manifest:
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                self._expected_fingerprint = str(
                    manifest.get('public_key_fingerprint_sha256') or '').lower()
            except (OSError, ValueError, TypeError):
                self._key_error = 'فایل COMMERCIAL-BUILD.json معتبر نیست.'
        self.public_key = None
        if isinstance(public_key, Ed25519PublicKey):
            self.public_key = public_key
        else:
            key_value = public_key or os.environ.get('LICENSE_PUBLIC_KEY', '').strip()
            key_file = Path(os.environ.get('LICENSE_PUBLIC_KEY_FILE') or
                            DEFAULT_PUBLIC_KEY_FILE)
            if not key_value and key_file.is_file():
                try:
                    key_value = key_file.read_bytes()
                except OSError as exc:
                    self._key_error = str(exc)
            if key_value:
                try:
                    self.public_key = load_public_key(key_value)
                except ValueError as exc:
                    self._key_error = str(exc)
        if self.public_key and self._commercial_manifest:
            raw_public = self.public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            actual_fingerprint = hashlib.sha256(raw_public).hexdigest()
            if (not self._expected_fingerprint or
                    actual_fingerprint != self._expected_fingerprint):
                self.public_key = None
                self._key_error = 'اثر انگشت کلید عمومی با بسته تجاری مطابقت ندارد.'
        env_mode = os.environ.get('LICENSE_ENFORCEMENT', '').strip().lower()
        if enforcement is not None:
            self.enforced = bool(enforcement)
        elif self._commercial_manifest:
            # در ZIP تجاری، حذف/خراب‌کردن public key نباید برنامه را به حالت
            # community برگرداند؛ بسته تا بازیابی کلید صحیح fail-closed است.
            self.enforced = True
        elif env_mode in ('1', 'true', 'yes', 'on'):
            self.enforced = True
        elif env_mode in ('0', 'false', 'no', 'off'):
            self.enforced = False
        else:
            self.enforced = self.public_key is not None

    @property
    def configured(self) -> bool:
        return self.public_key is not None

    def decode_and_verify(self, token: str, domain: str = '',
                          today: Optional[date] = None) -> LicenseState:
        current_domain = normalize_domain(domain)
        if not self.public_key:
            return LicenseState(
                configured=False, enforced=self.enforced,
                # Community مجاز به اجراست، اما نباید در API «لایسنس معتبر» گزارش شود.
                valid=False,
                code='configuration_error' if self.enforced else 'not_configured',
                message=(self._key_error or 'کلید عمومی لایسنس تنظیم نشده است.')
                if self.enforced else 'کنترل لایسنس برای این بسته فعال نشده است.',
                domain=current_domain,
            )
        try:
            parts = str(token or '').strip().split('.')
            if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
                raise ValueError('ساختار کلید لایسنس معتبر نیست.')
            body = _b64decode(parts[1])
            signature = _b64decode(parts[2])
            if len(body) > 8 * 1024 or len(signature) != 64:
                raise ValueError('اندازه کلید لایسنس معتبر نیست.')
            self.public_key.verify(signature, body)
            payload = json.loads(body.decode('utf-8'))
            if not isinstance(payload, dict) or payload.get('v') != 1:
                raise ValueError('نسخه لایسنس پشتیبانی نمی‌شود.')
            if not _LICENSE_ID_RE.match(str(payload.get('license_id') or '')):
                raise ValueError('شناسه لایسنس نامعتبر است.')
            domains = payload.get('domains')
            if not isinstance(domains, list) or not domains:
                raise ValueError('دامنه‌ای در لایسنس ثبت نشده است.')
            expires = _parse_iso_date(payload.get('expires_at'))
            now_date = today or datetime.now(UTC).date()
            if expires and now_date > expires:
                return LicenseState(True, self.enforced, False, 'expired',
                                    'اعتبار لایسنس به پایان رسیده است.', payload,
                                    current_domain)
            if not current_domain:
                return LicenseState(True, self.enforced, False, 'invalid_domain',
                                    'دامنه فعلی سرور معتبر یا قابل تشخیص نیست.',
                                    payload, current_domain)
            if not domain_matches(current_domain, domains):
                return LicenseState(True, self.enforced, False, 'domain_mismatch',
                                    'این لایسنس برای دامنه فعلی صادر نشده است.',
                                    payload, current_domain)
            return LicenseState(True, self.enforced, True, 'valid',
                                'لایسنس معتبر و فعال است.', payload, current_domain)
        except InvalidSignature:
            return LicenseState(True, self.enforced, False, 'invalid_signature',
                                'امضای لایسنس معتبر نیست.', domain=current_domain)
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            return LicenseState(True, self.enforced, False, 'invalid', str(exc),
                                domain=current_domain)

    def read_token(self) -> str:
        try:
            data = json.loads(self.license_file.read_text(encoding='utf-8'))
            return str(data.get('token') or '') if isinstance(data, dict) else ''
        except (OSError, ValueError, TypeError):
            return ''

    def status(self, domain: str = '', today: Optional[date] = None) -> LicenseState:
        if not self.configured:
            return self.decode_and_verify('', domain, today)
        token = self.read_token()
        if not token:
            return LicenseState(True, self.enforced, False, 'missing',
                                'هنوز لایسنسی روی این نصب فعال نشده است.',
                                domain=normalize_domain(domain))
        return self.decode_and_verify(token, domain, today)

    def activate(self, token: str, domain: str) -> LicenseState:
        state = self.decode_and_verify(token, domain)
        if not state.valid:
            return state
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        content = {
            'token': str(token).strip(),
            'activated_domain': normalize_domain(domain),
            'activated_at': datetime.now(UTC).isoformat(),
        }
        fd, temp_name = tempfile.mkstemp(
            prefix='.license-', suffix='.tmp', dir=str(self.license_file.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(content, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.license_file)
        finally:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        return state

    def deactivate(self):
        try:
            self.license_file.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False


_MANAGER = None
_MANAGER_SIGNATURE = None


def get_license_manager() -> LicenseManager:
    """Manager کش‌شده؛ با تغییر env یا فایل کلید/manifest نوسازی می‌شود."""
    global _MANAGER, _MANAGER_SIGNATURE

    def _file_signature(path):
        try:
            stat = Path(path).stat()
            return (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (0, 0)

    key_file = os.environ.get('LICENSE_PUBLIC_KEY_FILE') or DEFAULT_PUBLIC_KEY_FILE
    manifest_file = (os.environ.get('COMMERCIAL_BUILD_MANIFEST') or
                     (BASE_DIR / 'COMMERCIAL-BUILD.json'))
    signature = (
        os.environ.get('LICENSE_PUBLIC_KEY', ''),
        os.environ.get('LICENSE_PUBLIC_KEY_FILE', ''),
        os.environ.get('LICENSE_FILE', ''),
        os.environ.get('LICENSE_ENFORCEMENT', ''),
        os.environ.get('COMMERCIAL_BUILD_MANIFEST', ''),
        _file_signature(key_file),
        _file_signature(manifest_file),
    )
    if _MANAGER is None or signature != _MANAGER_SIGNATURE:
        _MANAGER = LicenseManager()
        _MANAGER_SIGNATURE = signature
    return _MANAGER
