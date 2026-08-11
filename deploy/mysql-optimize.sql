-- ============================================================================
-- ⚡ بهینه‌سازی دیتابیس MySQL آکادمی آنلاین — مخصوص phpMyAdmin
-- ============================================================================
-- ✅ طرز استفاده:
--    ۱) ابتدا بکاپ بگیرید: تب «Export» در phpMyAdmin → روش Quick → Go
--    ۲) تب «SQL» را باز کنید → کل این متن را بچسبانید → دکمه «Go» / «اجرا»
--    ۳) اجرای مجدد کاملاً بی‌خطر است (خودش ایندکس‌های موجود را رد می‌کند)
--
-- این اسکریپت سه کار می‌کند:
--   A) ایندکس‌های جاافتاده را می‌سازد (دلیل اصلی کندی کوئری‌ها)
--   B) آمار جدول‌ها را به‌روز می‌کند (ANALYZE) تا MySQL از ایندکس‌ها استفاده کند
--   C) جدول‌های داغ را یکپارچه/فشرده می‌کند (OPTIMIZE) — بهتر است در ترافیک کم
-- ============================================================================

-- ----------------------------------------------------------------------------
-- A) ساخت ایندکس‌های جاافتاده (فقط آن‌هایی که وجود ندارند)
-- ----------------------------------------------------------------------------
DELIMITER $$

DROP PROCEDURE IF EXISTS academy_ensure_index$$

CREATE PROCEDURE academy_ensure_index(IN tbl VARCHAR(64), IN idx VARCHAR(64), IN cols VARCHAR(255))
BEGIN
    -- اگر یک ایندکس خراب شود (مثلاً محدودیت طول در MySQL قدیمی)، بقیه ادامه پیدا کنند
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION BEGIN END;
    -- نرمال‌سازی: 'a, b(191)' ← 'a,b(191)' تا با GROUP_CONCAT مقایسه شود
    SET @cols_clean = REPLACE(cols, ', ', ',');
    -- اگر ایندکسی با همین نام یا دقیقاً همین ستون‌ها (با پیشوند) وجود داشته باشد، رد می‌شود
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = tbl AND index_name = idx
    ) AND NOT EXISTS (
        SELECT 1 FROM (
            SELECT index_name,
                   GROUP_CONCAT(
                       IF(sub_part IS NULL, column_name,
                          CONCAT(column_name, '(', sub_part, ')'))
                       ORDER BY seq_in_index) AS idx_cols
            FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = tbl
            GROUP BY index_name
        ) AS existing
        WHERE existing.idx_cols = @cols_clean
    ) THEN
        SET @sql = CONCAT('CREATE INDEX `', idx, '` ON `', tbl, '` (', cols, ')');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

-- کاربران: جستجو/شمارش بر اساس نقش (دانشجو/مدرس/ادمین)
CALL academy_ensure_index('users',         'idx_users_role',            'role');

-- دوره‌ها: فیلتر وضعیت / دسته / مدرس / محبوبیت (لیست دوره‌ها و ویجت‌ها)
CALL academy_ensure_index('courses',       'idx_courses_status',        'status');
CALL academy_ensure_index('courses',       'idx_courses_cat',           'category_id');
CALL academy_ensure_index('courses',       'idx_courses_teacher',       'teacher_id');
CALL academy_ensure_index('courses',       'idx_courses_views',         'views');

-- ثبت‌نام‌ها: شمارش دانشجویان هر دوره (کارت دوره و داشبورد)
CALL academy_ensure_index('enrollments',   'idx_enroll_course',         'course_id');

-- نظرات: نظرات تاییدشده هر دوره + جدیدترین نظرات صفحه اصلی
CALL academy_ensure_index('reviews',       'idx_reviews_user',          'user_id');
CALL academy_ensure_index('reviews',       'idx_reviews_created',       'is_approved, created_at');

-- سفارش‌ها: سفارش‌های هر کاربر (مرتب‌شده با تاریخ) — داشبورد دانشجو
CALL academy_ensure_index('orders',        'idx_orders_user_created',   'user_id, created_at');

-- علاقه‌مندی‌ها: لیست علاقه‌مندی هر کاربر
CALL academy_ensure_index('favorites',     'idx_fav_user',              'user_id');

-- تیکت‌ها: تیکت‌های باز هر کاربر (بدون ایندکس = اسکن کامل جدول!)
CALL academy_ensure_index('tickets',       'idx_tickets_user_status',   'user_id, status');

-- اعلان‌ها: جلوگیری از اعلان تکراری یادآورها (title + link)
CALL academy_ensure_index('notifications', 'idx_notif_title_link',      'title, link(191)');

-- کلاس‌های آنلاین: کلاس‌های ۲۴ ساعت آینده
CALL academy_ensure_index('live_sessions', 'idx_live_starts',           'starts_at');

-- دیدگاه‌های وبلاگ: دیدگاه‌های هر نوشته
CALL academy_ensure_index('blog_comments', 'idx_bc_post',               'post_id');

-- لاگ 404: ربات‌ها این جدول را بزرگ می‌کنند — جستجو با مسیر
CALL academy_ensure_index('notfound_logs', 'idx_nf_path',               'path');

-- تاریخچه قیمت: نمودار قیمت هر دوره
CALL academy_ensure_index('price_history', 'idx_price_item',            'item_type, item_id');

DROP PROCEDURE IF EXISTS academy_ensure_index;

-- ----------------------------------------------------------------------------
-- B) به‌روزرسانی آمار ایندکس‌ها (بسیار سریع و بی‌خطر — بعد از هر ایندکس جدید حتماً)
--    هر جدول جداگانه تا اگر جدولی در نسخهٔ قدیمی‌تر وجود نداشت، بقیه متوقف نشوند
-- ----------------------------------------------------------------------------
ANALYZE TABLE users;
ANALYZE TABLE courses;
ANALYZE TABLE sections;
ANALYZE TABLE lessons;
ANALYZE TABLE enrollments;
ANALYZE TABLE reviews;
ANALYZE TABLE favorites;
ANALYZE TABLE orders;
ANALYZE TABLE order_items;
ANALYZE TABLE notifications;
ANALYZE TABLE tickets;
ANALYZE TABLE ticket_replies;
ANALYZE TABLE blog_posts;
ANALYZE TABLE blog_comments;
ANALYZE TABLE live_sessions;
ANALYZE TABLE price_history;
ANALYZE TABLE notfound_logs;
ANALYZE TABLE payment_proofs;
ANALYZE TABLE payment_logs;
ANALYZE TABLE success_stories;
ANALYZE TABLE newsletter_emails;
ANALYZE TABLE wallet_transactions;
ANALYZE TABLE activity_logs;
ANALYZE TABLE products;
ANALYZE TABLE question_bank;
ANALYZE TABLE quiz_attempts;
ANALYZE TABLE quiz_questions;
ANALYZE TABLE quizzes;
ANALYZE TABLE installments;
ANALYZE TABLE payout_requests;
ANALYZE TABLE spin_results;
ANALYZE TABLE study_days;
ANALYZE TABLE study_plans;
ANALYZE TABLE private_messages;
ANALYZE TABLE forum_topics;
ANALYZE TABLE forum_posts;
ANALYZE TABLE forum_polls;
ANALYZE TABLE forum_poll_votes;
ANALYZE TABLE media;
ANALYZE TABLE menus;
ANALYZE TABLE menu_items;
ANALYZE TABLE pages;
ANALYZE TABLE page_revisions;
ANALYZE TABLE seo_metas;
ANALYZE TABLE redirect_rules;
ANALYZE TABLE settings;
ANALYZE TABLE custom_forms;
ANALYZE TABLE custom_form_entries;
ANALYZE TABLE exam_attempts;
ANALYZE TABLE market_orders;
ANALYZE TABLE market_sync_logs;
ANALYZE TABLE point_logs;
ANALYZE TABLE lesson_questions;

-- ----------------------------------------------------------------------------
-- C) خانه‌تکانی جدول‌های داغ (فشرده‌سازی + یکپارچه‌سازی)
--    ⚠️ در ترافیک کم اجرا کنید (جدول‌های خیلی بزرگ ممکن است چند دقیقه طول بکشد)
-- ----------------------------------------------------------------------------
OPTIMIZE TABLE users;
OPTIMIZE TABLE courses;
OPTIMIZE TABLE enrollments;
OPTIMIZE TABLE reviews;
OPTIMIZE TABLE orders;
OPTIMIZE TABLE order_items;
OPTIMIZE TABLE notifications;
OPTIMIZE TABLE tickets;
OPTIMIZE TABLE blog_posts;
OPTIMIZE TABLE blog_comments;
OPTIMIZE TABLE favorites;
OPTIMIZE TABLE live_sessions;
OPTIMIZE TABLE price_history;
OPTIMIZE TABLE notfound_logs;
OPTIMIZE TABLE payment_proofs;
OPTIMIZE TABLE wallet_transactions;
OPTIMIZE TABLE activity_logs;
OPTIMIZE TABLE success_stories;
OPTIMIZE TABLE newsletter_emails;

-- ----------------------------------------------------------------------------
-- D) (اختیاری اما پیشنهادی) حذف لاگ 404های قدیمی‌تر از ۹۰ روز
--    ربات‌ها مدام آدرس‌های بی‌معنی می‌زنند؛ این جدول سریع بزرگ می‌شود و فقط
--    برای پیدا کردن لینک‌های شکسته کاربرد دارد. ۹۰ روز برای این کار کافی است.
-- ----------------------------------------------------------------------------
DELETE FROM notfound_logs WHERE last_seen < NOW() - INTERVAL 90 DAY;

-- ✅ تمام شد! حالا در phpMyAdmin: «Status» هر جدول را ببینید — ایندکس‌های جدید
-- زیر بخش «Indexes» قابل مشاهده‌اند. برای اطمینان از استفادهٔ MySQL از آن‌ها،
-- سند docs/MYSQL-OPTIMIZE-FA.md را ببینید (بخش EXPLAIN).
