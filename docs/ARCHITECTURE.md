# 🏗 معماری فنی — پلتفرم چندمنظوره آکادمی آنلاین (Flask)

> تاریخ: ۱۴۰۵/۰۵/۱۶ · هدف: مقیاس‌پذیری و اتصال به اکوسیستم‌های بزرگ ایران (اسنپ، دیجی‌کالا، ترب، باسلام)

---

## ۱) نمای کلی معماری

```
┌─────────────────────────────────────────────────────────────────┐
│                      کاربران (وب/موبایل)                        │
└───────────────┬───────────────────────────────┬─────────────────┘
                │                               │
        ┌───────▼────────┐             ┌────────▼─────────┐
        │   Flask App    │             │  وب‌هوک‌های ورودی  │
        │  (MVC, Blueprint)│            │  (باسلام و...)    │
        └───────┬────────┘             └────────┬─────────┘
                │                               │
   ┌────────────┼───────────────┬───────────────┼──────────────┐
   ▼            ▼               ▼               ▼              ▼
┌────────┐ ┌─────────┐   ┌──────────┐   ┌────────────┐  ┌─────────────┐
│ SQLite │ │  Redis  │   │  درگاه‌ها  │   │  مارکت‌پلیس  │  │  سرویس‌های  │
│ (MySQL   │ │(کش/صف/ │   │ زرین‌پال، │   │  ترب/ایمالز │  │ Google Maps │
│  در prod)│ │RateLimit│   │ اسنپ‌پی، │   │ دیجی‌کالا، │  │ Groq/Bing   │
│         │ │        │   │ دیجی‌پی  │   │  باسلام    │  │ Clarity     │
└────────┘ └─────────┘   └──────────┘   └────────────┘  └─────────────┘
```

### ماژول‌های جدید (این سند)
| ماژول | فایل | مسیرها |
|---|---|---|
| **BNPL + Cashback** | `bnpl.py` | `/bnpl/<code>` · `/bnpl/<code>/start` · `/api/bnpl/status/<code>` |
| **مارکت‌پلیس** | `marketplace.py` | `/api/feed/torob.json` · `/api/feed/torob.xml` · `/api/feed/emalls.json` · `/api/marketplace/basalam/webhook` · `/admin/marketplace` |
| **تعامل کاربران** | `engagement.py` | `/spin` · `/api/spin` · `/api/address/*` · `/address` · `/affiliate` |
| **مدل‌های زیرساخت** | `ext_models.py` | CashbackLog · MarketSyncLog · MarketOrder · PriceHistory · SpinResult |

---

## ۲) Database Models (جداول جدید)

### `cashback_logs` — برگشت وجه پس از خرید موفق
| ستون | نوع | توضیح |
|---|---|---|
| id | Integer PK | |
| user_id | FK users | گیرنده |
| order_id | FK orders | سفارش مبدأ |
| amount | Integer | مبلغ برگشتی (تومان) |
| percent | Integer | درصد بازگشت (پیش‌فرض ۲) |
| base_amount | Integer | مبلغ مبنای محاسبه |
| note | String(200) | توضیح |
| created_at | DateTime | |

### `market_sync_logs` — لاگ همگام‌سازی مارکت‌پلیس
`channel` (torob/emalls/digikala/basalam) · `action` (feed/sync_inventory/webhook) · `status` (ok/error) · `item_type/item_id` · `detail` · `created_at`

### `market_orders` — سفارش‌های خارجی (باسلام)
`channel` · `external_id` (یکتا per channel) · `customer_name/phone/address` · `items` (JSON) · `total` · `status` (new/accepted/shipped/done/canceled) · `raw` (payload خام) · `created_at`

### `price_history` — تاریخچه قیمت (نمودار دیجی‌کالایی)
`item_type` (course/product) · `item_id` · `price` · `final_price` · `recorded_at` — ایندکس مرکب

### `spin_results` — گردونه شانس
`user_id` · `prize_type` (coupon/wallet/none) · `prize_value` · `coupon_code` · `spin_date` (شمسی) — یک چرخش در روز

### ستون‌های ارتقایافته
`reviews`: +`pros` · `cons` · `buyer_verified` (نظرات دیجی‌کالایی)

---

## ۳) سیستم BNPL و Cashback (جریان)

```
کاربر → صفحه دوره → «خرید اقساطی» → /bnpl/<code> (لندینگ ۴ قسط ماهانه شمسی)
     → انتخاب اسنپ‌پی/دیجی‌پی/ترب → /bnpl/<code>/start → پرداخت قسط اول
     → درگاه (اسنپ‌پی/دیجی‌پی/آزمایشی) → تأیید → _mark_paid
          ├─ فعال‌سازی Enrollment
          ├─ پاداش معرف ۱۰٪ (اگر اولین خرید)
          ├─ 💰 Cashback 2% → کیف پول + CashbackLog + اعلان
          └─ ثبت نقطه PriceHistory
```

**نکات امنیتی:** قسط اول همیشه پیش‌پرداخت · تاریخ‌های سررسید شمسی · تأخیر قسط → توقف دسترسی · حداکثر قسط از تنظیمات `bnpl_max_installments`

---

## ۴) مارکت‌پلیس‌ها

### فید ترب (JSON + XML) و ایمالز (JSON)
- آدرس ثابت → در پنل ترب/ایمالز ثبت می‌شود → آن‌ها هر چند ساعت می‌خوانند
- هدر `Cache-Control: no-store` → همیشه لحظه‌ای
- شامل: قیمت نهایی، قیمت قبلی، درصد تخفیف، موجودی، لینک عمیق، تصویر، دسته

### دیجی‌کالا (Seller Center)
- `sync_digikala_inventory()` — ارسال موجودی به `seller.digikala.com/api/v1/inventory`
- در production با Celery هر ۳۰ دقیقه (نمونه در بخش ۶)
- تنظیمات: `dk_api_base` · `dk_access_token`

### باسلام (وب‌هوک)
- `POST /api/marketplace/basalam/webhook` با امضای HMAC-SHA256 (`basalam_webhook_secret`)
- دریافت/به‌روزرسانی سفارش → `MarketOrder` → مدیریت در `/admin/marketplace`

---

## ۵) امنیت

| لایه | پیاده‌سازی |
|---|---|
| Rate Limit پرداخت/API | سیستم موجود (`rate_limit_protect`) — Redis-ready · API 120/min · لاگین 20/5min |
| امضای وب‌هوک | HMAC-SHA256 + `hmac.compare_digest` |
| CSRF | همه فرم‌ها (۳۹+ فرم) + APIهای JSON معاف |
| Race پرداخت | `UPDATE ... WHERE status='pending'` اتمیک |
| کش | static `immutable` ۷ روز · HTML بدون کش |
| حجم درخواست | MAX_CONTENT_LENGTH 50MB · محدودیت JSON صفحه‌ساز 500KB |

---

## ۶) Background Tasks (Celery/Redis)

```python
# celery_app.py — نمونه production
from celery import Celery
celery_app = Celery('academy', broker='redis://localhost:6379/0',
                    backend='redis://localhost:6379/1')

@celery_app.task
def sync_digikala_task():
    from marketplace import sync_digikala_inventory
    return sync_digikala_inventory()

@celery_app.task
def record_daily_prices():
    """ثبت روزانه قیمت همه دوره‌ها/محصولات برای نمودار"""
    from blueprints.builder import record_price
    from models import Course, Product
    for c in Course.query.all():
        record_price('course', c.id, c.price or 0, c.final_price or 0)
    for p in Product.query.all():
        record_price('product', p.id, p.price or 0, p.final_price or 0)

# schedule (beat):
#   sync_digikala_task: هر ۳۰ دقیقه
#   record_daily_prices: هر شب ساعت ۲۳:۳۰
```

---

## ۷) ویجت‌های جدید صفحه‌ساز

| ویجت | داده | توضیح |
|---|---|---|
| `price_history` | PriceHistory + `competitive_prices` (تنظیمات JSON) | نمودار میل‌های ۱۴ نقطه آخر + مقایسه ترب/دیجی‌کالا/فرادرس |
| `amazing_offer` | اولین آیتم با بیشترین تخفیف | باکس نئون + تایمر معکوس (data-countdown) |
| `review_pro` | Review با pros/cons/buyer_verified | نقاط قوت/ضعف + نشان «خرید تأییدشده» |

---

## ۸) نقشه راه اتصال واقعی

| سرویس | وضعیت | اقدام برای production |
|---|---|---|
| اسنپ‌پی | ✅ متدها + لندینگ | ثبت `snapp_client_id/secret` در تنظیمات + قرارداد کارمزد |
| دیجی‌پی | ✅ متد + لندینگ | ثبت `digipay_api_key/merchant` |
| ترب/ایمالز | ✅ فید آماده | ثبت آدرس فید در پنل آن‌ها |
| دیجی‌کالا | ✅ کلاینت + لاگ | توکن Seller Center + Celery |
| باسلام | ✅ وب‌هوک + پنل | ثبت آدرس وبهوک + secret |
| Google Maps | ✅ پیش‌نمایش واقعی نشانی + برآورد ارسال | بدون کلید؛ هزینه ثابت/هماهنگی از تنظیمات فروشگاه |

---

## ۹) تست‌ها (سبز)
- فیدها: torob.json/xml + emalls → 200 + no-store ✅
- وب‌هوک باسلام: دریافت سفارش → MarketOrder ✅
- گردونه: یک بار در روز (دومین → 429) ✅
- برآورد ارسال: استان/شهر معتبر → هزینه و توضیح واقعی ثبت‌شده مدیر ✅
- Cashback: فقط درصد صریح مدیر، پس از callback موفق → کیف پول + لاگ ✅
- PriceHistory: ثبت خودکار قیمت اقلام در خریدهای تاییدشده ✅
- ویجت‌ها: price_history/amazing_offer/review_pro رندر بدون خطا ✅
- آمار جاری regression و خزش نقش‌ها در `docs/COMMERCIAL_READINESS_FA.md` نگهداری می‌شود.
