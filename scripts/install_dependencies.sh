#!/usr/bin/env bash
# نصب قابل‌اعتماد وابستگی‌ها برای هاست هدف CPython 3.11 / cPanel.
# استفاده:
#   source /home/USER/virtualenv/APP/3.11/bin/activate
#   bash scripts/install_dependencies.sh
# یا:
#   bash scripts/install_dependencies.sh ./venv/bin/python
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -gt 1 ]; then
    echo "Usage: bash scripts/install_dependencies.sh [path/to/python3.11]" >&2
    exit 2
fi
PYTHON_BIN="${1:-${PYTHON_BIN:-python}}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 && [ ! -x "$PYTHON_BIN" ]; then
    echo "خطا: مفسر پایتون پیدا نشد: $PYTHON_BIN" >&2
    exit 2
fi

# اگر بدون آرگومان اجرا شد، مطمئن شو pip داخل همان virtualenv اپ است؛ نصب
# تصادفی در Python سراسری معمولاً علت 500 پس از ری‌استارت Passenger است.
if [ "$#" -eq 0 ] && [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "خطا: ابتدا محیط مجازی Python 3.11 اپ را فعال کنید، یا مسیر مفسر را بدهید:" >&2
    echo "  bash scripts/install_dependencies.sh ./venv/bin/python" >&2
    exit 2
fi

if ! "$PYTHON_BIN" - <<'PY'
import platform
import sys
ok = platform.python_implementation() == "CPython" and sys.version_info[:2] == (3, 11)
if not ok:
    print(
        "خطا: این نسخه فقط برای CPython 3.11 پیکربندی و آزموده شده است؛ "
        "مفسر فعلی {} {}.{}.".format(
            platform.python_implementation(), sys.version_info.major, sys.version_info.minor
        ),
        file=sys.stderr,
    )
raise SystemExit(0 if ok else 3)
PY
then
    exit 3
fi

# مسیر مطلق را پیش از cd نگه دار تا آرگومان‌های نسبی از هر دایرکتوری معتبر بمانند.
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "خطا: pip در محیط انتخاب‌شده موجود نیست." >&2
    exit 2
fi

# فقط عدد مثبت بپذیر تا خطای پیکربندی قبل از اجرای pip واضح باشد.
PIP_REQUEST_TIMEOUT="${PIP_REQUEST_TIMEOUT:-${PIP_DEFAULT_TIMEOUT:-120}}"
PIP_RETRY_COUNT="${PIP_RETRY_COUNT:-${PIP_RETRIES:-10}}"
if ! [[ "$PIP_REQUEST_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    echo "خطا: PIP_REQUEST_TIMEOUT/PIP_DEFAULT_TIMEOUT باید عدد مثبت باشد." >&2
    exit 2
fi
if ! [[ "$PIP_RETRY_COUNT" =~ ^[0-9]+$ ]]; then
    echo "خطا: PIP_RETRY_COUNT/PIP_RETRIES باید عدد نامنفی باشد." >&2
    exit 2
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_DEFAULT_TIMEOUT="$PIP_REQUEST_TIMEOUT"
export PIP_RETRIES="$PIP_RETRY_COUNT"
export PIP_PREFER_BINARY=1
export PIP_ONLY_BINARY=:all:

PIP_ARGS=(
    --timeout "$PIP_REQUEST_TIMEOUT"
    --retries "$PIP_RETRY_COUNT"
    --prefer-binary
    --only-binary=:all:
)

cd "$ROOT_DIR"
echo "مفسر نصب: $($PYTHON_BIN -c 'import sys; print(sys.executable)')"
echo "نسخه هدف: $($PYTHON_BIN -c 'import platform; print(platform.python_implementation(), platform.python_version())')"
echo "مهلت هر درخواست PyPI: ${PIP_REQUEST_TIMEOUT}s | تلاش مجدد: ${PIP_RETRY_COUNT}"

# pip قدیمی ممکن است wheelهای manylinux جدید یا markerها را درست تشخیص ندهد.
echo "[1/3] ارتقای ابزارهای نصب (فقط wheel باینری)..."
"$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" --upgrade pip setuptools wheel

echo "[2/3] نصب requirements.txt قفل‌شده (فقط wheel باینری)..."
"$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" -r requirements.txt

echo "[3/3] بررسی سازگاری همه وابستگی‌های نصب‌شده..."
"$PYTHON_BIN" -m pip check

echo "وابستگی‌های Python 3.11 با موفقیت نصب و بررسی شدند."
