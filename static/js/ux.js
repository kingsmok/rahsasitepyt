/* تجربه کاربری سراسری: منوهای واکنش‌گرا، فرم‌ها و دسترس‌پذیری */
(function () {
  'use strict';

  function qs(selector, root) { return (root || document).querySelector(selector); }
  function qsa(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  /* ---------- پنل مدیریت موبایل ---------- */
  var adminSidebar = qs('#admin-sidebar');
  var adminToggle = qs('[data-admin-nav-toggle]');
  function setAdminNav(open) {
    document.body.classList.toggle('admin-nav-open', !!open);
    if (adminToggle) adminToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open && adminSidebar) {
      var first = qs('input, a, button', adminSidebar);
      if (first) window.setTimeout(function () { first.focus(); }, 80);
    } else if (!open && adminToggle) {
      adminToggle.focus({preventScroll: true});
    }
  }
  if (adminToggle && adminSidebar) {
    adminToggle.addEventListener('click', function () {
      setAdminNav(!document.body.classList.contains('admin-nav-open'));
    });
    qsa('[data-admin-nav-close]').forEach(function (button) {
      button.addEventListener('click', function () { setAdminNav(false); });
    });
    qsa('a', adminSidebar).forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.matchMedia('(max-width: 900px)').matches) setAdminNav(false);
      });
    });
  }

  /* جستجوی سریع در منوی طولانی مدیریت */
  var menuSearch = qs('[data-admin-menu-search]');
  if (menuSearch && adminSidebar) {
    var links = qsa('[data-admin-link]', adminSidebar);
    var groups = qsa('[data-admin-group]', adminSidebar);
    var noResult = qs('[data-admin-no-result]', adminSidebar);
    menuSearch.addEventListener('input', function () {
      var query = menuSearch.value.trim().toLocaleLowerCase('fa-IR');
      var visible = 0;
      links.forEach(function (link) {
        var show = !query || link.textContent.toLocaleLowerCase('fa-IR').indexOf(query) !== -1;
        link.hidden = !show;
        if (show) visible += 1;
      });
      groups.forEach(function (group) {
        if (!query) { group.hidden = false; return; }
        var next = group.nextElementSibling;
        var hasVisible = false;
        while (next && !next.hasAttribute('data-admin-group')) {
          if (next.hasAttribute('data-admin-link') && !next.hidden) { hasVisible = true; break; }
          next = next.nextElementSibling;
        }
        group.hidden = !hasVisible;
      });
      if (noResult) noResult.hidden = visible !== 0;
    });
    menuSearch.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menuSearch.value) {
        menuSearch.value = '';
        menuSearch.dispatchEvent(new Event('input'));
      }
    });
  }

  /* ---------- منوهای حساب دانشجو و مدرس ---------- */
  qsa('[data-panel-nav-toggle]').forEach(function (button) {
    var panel = document.getElementById(button.getAttribute('aria-controls'));
    if (!panel) return;
    button.addEventListener('click', function () {
      var open = panel.classList.toggle('panel-nav-open');
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });

  /* ---------- نمایش/پنهان‌کردن رمز ---------- */
  qsa('input[type="password"]').forEach(function (input, index) {
    if (input.closest('.password-field')) return;
    var wrap = document.createElement('div');
    wrap.className = 'password-field';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'password-toggle';
    toggle.setAttribute('aria-label', 'نمایش رمز عبور');
    toggle.setAttribute('aria-pressed', 'false');
    toggle.textContent = '👁';
    toggle.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.setAttribute('aria-label', show ? 'پنهان کردن رمز عبور' : 'نمایش رمز عبور');
      toggle.setAttribute('aria-pressed', show ? 'true' : 'false');
      toggle.textContent = show ? '🙈' : '👁';
      input.focus({preventScroll: true});
    });
    wrap.appendChild(toggle);

    var form = input.form;
    var isNewPassword = input.autocomplete === 'new-password' ||
      (form && qs('input[name="confirm"]', form) && input.name === 'password');
    if (isNewPassword) {
      var meter = document.createElement('div');
      meter.className = 'password-strength';
      meter.setAttribute('aria-hidden', 'true');
      meter.innerHTML = '<i></i>';
      wrap.appendChild(meter);
      input.addEventListener('input', function () {
        var value = input.value;
        var score = 0;
        if (value.length >= 8) score++;
        if (value.length >= 12) score++;
        if (/[a-zA-Z]/.test(value) && /[0-9]/.test(value)) score++;
        if (/[^a-zA-Z0-9\u0600-\u06ff]/.test(value)) score++;
        var bar = qs('i', meter);
        bar.style.width = (score * 25) + '%';
        bar.style.background = score < 2 ? 'var(--danger)' : score < 4 ? 'var(--warning)' : 'var(--success)';
      });
    }
  });

  /* فیلدهای رایج روی موبایل کیبورد درست باز کنند */
  qsa('input[name="phone"],input[name*="mobile"],input[name="national_code"],input[name="code"]').forEach(function (input) {
    if (!input.inputMode) input.inputMode = 'numeric';
  });
  qsa('input[type="email"]').forEach(function (input) {
    input.autocomplete = input.autocomplete || 'email';
    input.dir = 'ltr';
  });

  /* ---------- آکاردئون و تب‌های قابل استفاده با صفحه‌خوان ---------- */
  qsa('.faq-item .fq-q, .accordion .acc-head').forEach(function (button, index) {
    var item = button.closest('.faq-item, .accordion');
    var panel = item && item.querySelector('.fq-a, .acc-body');
    if (!item || !panel) return;
    var id = panel.id || ('accordion-panel-' + index);
    panel.id = id;
    button.type = 'button';
    button.setAttribute('aria-controls', id);
    button.setAttribute('aria-expanded', item.classList.contains('open') ? 'true' : 'false');
    button.addEventListener('click', function () {
      window.requestAnimationFrame(function () {
        button.setAttribute('aria-expanded', item.classList.contains('open') ? 'true' : 'false');
      });
    });
  });
  qsa('.course-tabs button[data-tab]').forEach(function (button) {
    var panel = document.getElementById(button.dataset.tab);
    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', button.dataset.tab);
    button.setAttribute('aria-selected', button.classList.contains('active') ? 'true' : 'false');
    if (panel) panel.setAttribute('role', 'tabpanel');
    button.addEventListener('click', function () {
      qsa('.course-tabs button[data-tab]').forEach(function (item) {
        item.setAttribute('aria-selected', item === button ? 'true' : 'false');
      });
    });
  });

  /* ---------- دسترس‌پذیری جدول‌ها و پنجره‌ها ---------- */
  qsa('.table-wrap').forEach(function (wrap) {
    if (!wrap.hasAttribute('tabindex')) wrap.tabIndex = 0;
    if (!wrap.hasAttribute('role')) wrap.setAttribute('role', 'region');
    if (!wrap.hasAttribute('aria-label')) wrap.setAttribute('aria-label', 'جدول اطلاعات؛ در موبایل قابل پیمایش افقی');
  });

  /* منوی موبایل: aria و قفل اسکرول */
  var mobileMenu = qs('#mobile-menu');
  var mobileButtons = qsa('.hamburger, #mobile-menu-fab');
  if (mobileMenu) {
    mobileButtons.forEach(function (button) {
      button.setAttribute('aria-controls', 'mobile-menu');
      button.setAttribute('aria-expanded', 'false');
      button.addEventListener('click', function () {
        button.setAttribute('aria-expanded', 'true');
        document.body.classList.add('mobile-nav-open');
      });
    });
    qsa('[data-close-mm]', mobileMenu).forEach(function (button) {
      button.addEventListener('click', function () {
        mobileButtons.forEach(function (item) { item.setAttribute('aria-expanded', 'false'); });
        document.body.classList.remove('mobile-nav-open');
      });
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    if (document.body.classList.contains('admin-nav-open')) setAdminNav(false);
    document.body.classList.remove('mobile-nav-open');
  });

  /* فوکوس اولین خطای سرور که با aria-invalid برگشته است */
  var invalid = qs('[aria-invalid="true"]');
  if (invalid) window.setTimeout(function () { invalid.focus(); }, 100);
})();
