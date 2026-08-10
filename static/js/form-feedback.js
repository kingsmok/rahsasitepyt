/* اعتبارسنجی inline فرم‌ها — هایلایت فیلدهای ناقص کنار خود فیلد + اسکرول خودکار
   با رویداد invalid (قبل از مسدود شدن submit توسط مرورگر) کار میکند */
(function () {
  'use strict';

  function msgFor(el) {
    var custom = el.dataset.invalidMsg;
    if (custom) return custom;
    var type = el.type || '';
    if (type === 'email') return 'ایمیل معتبر وارد کنید.';
    if (type === 'tel') return 'شماره تماس معتبر (۰۹...) وارد کنید.';
    if (el.tagName === 'SELECT') return 'یکی از گزینه‌ها را انتخاب کنید.';
    if (el.tagName === 'TEXTAREA') return 'این بخش را پر کنید.';
    return 'این فیلد الزامی است.';
  }

  function mark(el) {
    el.classList.add('field-invalid');
    el.setAttribute('aria-invalid', 'true');
    var wrap = el.closest('.form-group, .pb-field') || el.parentElement;
    if (wrap && !wrap.querySelector('.field-msg')) {
      var msg = document.createElement('small');
      msg.className = 'field-msg';
      msg.style.cssText = 'display:block;color:#dc2626;font-size:11.5px;margin-top:4px;font-weight:600';
      msg.textContent = msgFor(el);
      wrap.appendChild(msg);
    }
  }

  function clear(el) {
    el.classList.remove('field-invalid');
    el.removeAttribute('aria-invalid');
    var wrap = el.closest('.form-group, .pb-field') || el.parentElement;
    if (wrap) {
      var msg = wrap.querySelector('.field-msg');
      if (msg) msg.remove();
    }
  }

  // رویداد invalid — قبل از اینکه مرورگر submit را مسدود کند
  document.addEventListener('invalid', function (e) {
    var el = e.target;
    if (!el || !el.form) return;
    e.preventDefault();  // حذف حباب بومی مرورگر
    mark(el);
    // اسکرول به اولین فیلد خطادار
    var form = el.form;
    if (!form.dataset.fbScrolled) {
      form.dataset.fbScrolled = '1';
      setTimeout(function () {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.focus({ preventScroll: true });
      }, 50);
    }
  }, true);

  // پاک‌سازی هنگام ورود دوباره
  document.addEventListener('input', function (e) {
    var el = e.target;
    if (el && (el.value || '').trim()) clear(el);
  }, true);
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el && (el.value || '').trim()) clear(el);
  }, true);
  document.addEventListener('reset', function (e) {
    e.target.querySelectorAll('.field-invalid').forEach(clear);
  }, true);
})();
