# -*- coding: utf-8 -*-
"""لایسنس تجاری: امضا، دامنه، انقضا، ذخیره و گارد Flask."""
import base64
import hashlib
import json
import re
from datetime import date

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing import LicenseManager, get_license_manager, issue_token


def _keys():
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    raw = public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    public_b64 = base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')
    return private, public, public_b64


def _token(private, **overrides):
    payload = {
        'license_id': 'CUSTOMER-2026-001',
        'customer': 'مشتری تست',
        'domains': ['academy.example.com', '*.customer.example'],
        'expires_at': '2027-12-31',
        'plan': 'business',
        'features': ['lms', 'shop'],
    }
    payload.update(overrides)
    return issue_token(private, payload)


def test_signed_license_domain_wildcard_and_tamper(tmp_path):
    private, public, _ = _keys()
    manager = LicenseManager(public_key=public,
                             license_file=tmp_path / 'license.json',
                             enforcement=True)
    token = _token(private)
    assert manager.decode_and_verify(token, 'academy.example.com').valid
    assert manager.decode_and_verify(token, 'panel.customer.example').valid
    mismatch = manager.decode_and_verify(token, 'evil.example.com')
    assert mismatch.valid is False and mismatch.code == 'domain_mismatch'

    head, body, signature = token.split('.')
    replacement = ('A' if signature[0] != 'A' else 'B')
    tampered = '.'.join((head, body, replacement + signature[1:]))
    assert manager.decode_and_verify(tampered, 'academy.example.com').valid is False


def test_license_expiry_and_atomic_activation(tmp_path):
    private, public, _ = _keys()
    license_file = tmp_path / 'license.json'
    manager = LicenseManager(public_key=public, license_file=license_file,
                             enforcement=True)
    token = _token(private, expires_at='2025-01-01')
    expired = manager.decode_and_verify(
        token, 'academy.example.com', today=date(2026, 8, 17))
    assert expired.code == 'expired' and not expired.valid

    valid_token = _token(private, expires_at='2027-12-31')
    state = manager.activate(valid_token, 'academy.example.com')
    assert state.valid and license_file.is_file()
    assert manager.status('academy.example.com').valid
    assert not manager.status('other.example.com').valid


def test_enforcement_without_public_key_fails_closed(tmp_path):
    manager = LicenseManager(public_key=None,
                             license_file=tmp_path / 'license.json',
                             enforcement=True)
    state = manager.status('academy.example.com')
    assert not state.valid
    assert state.code == 'configuration_error'


def test_commercial_manifest_enforces_and_pins_public_key(monkeypatch, tmp_path):
    _private, public, _public_b64 = _keys()
    raw = public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    manifest = tmp_path / 'COMMERCIAL-BUILD.json'
    manifest.write_text(json.dumps({
        'public_key_fingerprint_sha256': hashlib.sha256(raw).hexdigest(),
    }), encoding='utf-8')
    monkeypatch.setenv('COMMERCIAL_BUILD_MANIFEST', str(manifest))

    matching = LicenseManager(public_key=public,
                              license_file=tmp_path / 'license.json')
    assert matching.enforced and matching.configured

    _other_private, other_public, _other_b64 = _keys()
    replaced = LicenseManager(public_key=other_public,
                              license_file=tmp_path / 'other-license.json')
    state = replaced.status('academy.example.com')
    assert replaced.enforced and not replaced.configured
    assert state.code == 'configuration_error'


def test_cached_manager_loads_env_and_recovers_when_public_key_file_appears(
        monkeypatch, tmp_path):
    _private, public, public_b64 = _keys()
    raw = public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    public_pem = public.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    public_file = tmp_path / 'license_public_key.pem'
    manifest = tmp_path / 'COMMERCIAL-BUILD.json'
    manifest.write_text(json.dumps({
        'public_key_fingerprint_sha256': hashlib.sha256(raw).hexdigest(),
    }), encoding='utf-8')
    monkeypatch.delenv('LICENSE_PUBLIC_KEY', raising=False)
    monkeypatch.setenv('LICENSE_PUBLIC_KEY_FILE', str(public_file))
    monkeypatch.setenv('COMMERCIAL_BUILD_MANIFEST', str(manifest))
    monkeypatch.setenv('LICENSE_FILE', str(tmp_path / 'license.json'))

    missing = get_license_manager()
    assert missing.enforced and not missing.configured
    public_file.write_bytes(public_pem)
    recovered = get_license_manager()
    assert recovered is not missing
    assert recovered.enforced and recovered.configured

    public_file.unlink()
    monkeypatch.setenv('LICENSE_PUBLIC_KEY', public_b64)
    loaded_from_env = get_license_manager()
    assert loaded_from_env.configured


def test_license_page_community_and_expired_states(client, monkeypatch, tmp_path):
    monkeypatch.delenv('LICENSE_PUBLIC_KEY', raising=False)
    monkeypatch.setenv('LICENSE_PUBLIC_KEY_FILE', str(tmp_path / 'no-public-key.pem'))
    monkeypatch.setenv('LICENSE_ENFORCEMENT', '0')
    monkeypatch.setenv('LICENSE_FILE', str(tmp_path / 'community-license.json'))
    community = client.get('/license')
    assert community.status_code == 200
    assert 'حالت Community / بدون قفل فروش' in community.text
    community_api = client.get('/api/license/status')
    assert community_api.status_code == 200
    assert community_api.get_json()['configured'] is False
    assert community_api.get_json()['valid'] is False

    private, _public, public_b64 = _keys()
    expired_token = _token(private, domains=['localhost'], expires_at='2025-01-01')
    monkeypatch.setenv('LICENSE_PUBLIC_KEY', public_b64)
    monkeypatch.setenv('LICENSE_ENFORCEMENT', '1')
    page = client.get('/license')
    assert page.status_code == 200
    assert 'نیاز به فعال‌سازی' in page.text
    csrf = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    expired = client.post('/license', data={
        '_csrf_token': csrf, 'action': 'activate', 'license_key': expired_token,
    })
    assert expired.status_code == 200
    assert 'اعتبار لایسنس به پایان رسیده است' in expired.text


def test_license_activation_is_rate_limited_per_endpoint(client, monkeypatch, tmp_path):
    _private, _public, public_b64 = _keys()
    monkeypatch.setenv('LICENSE_PUBLIC_KEY', public_b64)
    monkeypatch.setenv('LICENSE_ENFORCEMENT', '1')
    monkeypatch.setenv('LICENSE_FILE', str(tmp_path / 'rate-limit-license.json'))
    page = client.get('/license', environ_overrides={'REMOTE_ADDR': '10.20.30.40'})
    csrf = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    payload = {
        '_csrf_token': csrf, 'action': 'activate',
        'license_key': 'AC1.invalid.invalid',
    }
    for _attempt in range(10):
        response = client.post('/license', data=payload,
                               environ_overrides={'REMOTE_ADDR': '10.20.30.40'})
        assert response.status_code == 200
    blocked = client.post('/license', data=payload,
                          environ_overrides={'REMOTE_ADDR': '10.20.30.40'})
    assert blocked.status_code == 429
    assert 'بیش از حد' in blocked.text


def test_flask_license_activation_flow(client, app, monkeypatch, tmp_path):
    private, _public, public_b64 = _keys()
    token = _token(private, domains=['localhost'], expires_at='2027-12-31')
    monkeypatch.setenv('LICENSE_PUBLIC_KEY', public_b64)
    monkeypatch.setenv('LICENSE_ENFORCEMENT', '1')
    monkeypatch.setenv('LICENSE_FILE', str(tmp_path / 'active-license.json'))

    blocked = client.get('/', follow_redirects=False)
    assert blocked.status_code == 302
    assert '/license' in blocked.headers['Location']
    api = client.get('/api/cart/count')
    assert api.status_code == 402
    assert api.get_json()['code'] == 'license_required'

    page = client.get('/license')
    assert page.status_code == 200
    csrf = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    activated = client.post('/license', data={
        '_csrf_token': csrf, 'action': 'activate', 'license_key': token,
    })
    assert activated.status_code == 200
    assert 'لایسنس معتبر و فعال است' in activated.text
    assert client.get('/').status_code == 200
