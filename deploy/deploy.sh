#!/usr/bin/env bash
# ============================================================
# اسکریپت استقرار آکادمی آنلاین روی Ubuntu/Linux (اولین بار)
# اجرا: sudo bash deploy/deploy.sh
# ============================================================
set -euo pipefail

APP_NAME="academy"
APP_DIR="/var/www/$APP_NAME"
DOMAIN="${DOMAIN:-academy.example.com}"   # دامنه واقعی را قبل از اجرا بگذارید

echo "🚀 شروع استقرار $APP_NAME روی $DOMAIN"

# ۱) پیش‌نیازها
apt update -y
apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git

# ۲) انتقال پروژه (در صورت دستی بودن، پوشه از قبل اینجاست)
if [ ! -d "$APP_DIR" ]; then
    echo "📦 پروژه در $APP_DIR پیدا نشد — آن را به این مسیر منتقل کنید و دوباره اجرا کنید."
    exit 1
fi
cd "$APP_DIR"

# ۳) محیط پایتون
# pip/setuptools/wheel جدید لازم است تا wheel آماده درست شناسایی شود
# (نسخهٔ قدیمی pip گاهی wheel را نمی‌بیند و می‌رود سراغ کامپایل از سورس).
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
# مهلت/تلاش مجدد بیشتر برای شبکه‌های کند به pypi
PIP_TIMEOUT="${PIP_TIMEOUT:-60}" PIP_RETRIES="${PIP_RETRIES:-5}" \
    ./venv/bin/pip install -r requirements.txt

# ۴) مجوزها (www-data برای instance و logs)
chown -R www-data:www-data "$APP_DIR/instance" "$APP_DIR/logs" "$APP_DIR/static/uploads" 2>/dev/null || true
chmod -R g+w "$APP_DIR/instance" "$APP_DIR/logs" 2>/dev/null || true

# ۵) فایل .env — اگر نیست از نمونه بساز
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  فایل .env ساخته شد — SECRET_KEY و کلیدها را ویرایش کنید!"
fi
# تولید SECRET_KEY امن اگر هنوز پیش‌فرض است
if grep -q "changeme\|dev-only" .env; then
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env
    echo "🔑 SECRET_KEY امن تولید شد"
fi

# ۶) سرویس systemd
cp deploy/academy.service /etc/systemd/system/$APP_NAME.service
sed -i "s|/var/www/academy|$APP_DIR|g" /etc/systemd/system/$APP_NAME.service
systemctl daemon-reload
systemctl enable --now $APP_NAME
sleep 3
systemctl status $APP_NAME --no-pager | head -8

# ۷) Nginx
cp deploy/nginx-academy.conf /etc/nginx/sites-available/$APP_NAME
sed -i "s/academy\.example\.com/$DOMAIN/g" /etc/nginx/sites-available/$APP_NAME
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# ۸) SSL (Let's Encrypt)
echo "🔐 دریافت گواهی SSL برای $DOMAIN ..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" --redirect || \
    echo "⚠️  گواهی SSL نگرفت — بعداً دستی: certbot --nginx -d $DOMAIN"

# ۹) ربات‌ها و نقشه سایت
echo "🕷 ساخت robots.txt و sitemap.xml ..."
cat > "$APP_DIR/robots.txt" <<EOF
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /dashboard/
Disallow: /builder
Disallow: /cart
Sitemap: https://$DOMAIN/sitemap.xml
EOF
chown www-data:www-data "$APP_DIR/robots.txt"

echo ""
echo "✅ استقرار کامل شد!"
echo "   سایت:   https://$DOMAIN"
echo "   پنل:    https://$DOMAIN/admin"
echo "   لاگ:    journalctl -u $APP_NAME -f"
echo "   بکاپ:   sqlite3 $APP_DIR/instance/academy.db '.backup backups/manual-$(date +%Y%m%d).db'"
