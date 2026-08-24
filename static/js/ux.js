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

  /* جستجوی سریع در منوی طولانی مدیریت (ساختار گروهی جدید) */
  var menuSearch = qs('[data-admin-menu-search]');
  if (menuSearch && adminSidebar) {
    var links = qsa('[data-admin-link]', adminSidebar);
    var groupHeads = qsa('[data-admin-group-head]', adminSidebar);
    var noResult = qs('[data-admin-no-result]', adminSidebar);
    menuSearch.addEventListener('input', function () {
      var query = menuSearch.value.trim().toLocaleLowerCase('fa-IR');
      var visible = 0;
      links.forEach(function (link) {
        var show = !query || link.textContent.toLocaleLowerCase('fa-IR').indexOf(query) !== -1;
        link.hidden = !show;
        if (show) visible += 1;
      });
      groupHeads.forEach(function (head) {
        var body = head.nextElementSibling;
        var hasVisible = false;
        if (body && body.hasAttribute('data-admin-group-body')) {
          qsa('[data-admin-link]', body).forEach(function (l) {
            if (!l.hidden) hasVisible = true;
          });
          body.classList.toggle('is-collapsed', !hasVisible);
        }
        head.hidden = !hasVisible;
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

  /* دسته‌های جمع‌شونده منوی مدیریت */
  qsa('[data-admin-group-toggle]', adminSidebar).forEach(function (btn) {
    btn.addEventListener('click', function () {
      var head = btn.closest('[data-admin-group-head]');
      var body = head ? head.nextElementSibling : null;
      if (!body || !body.hasAttribute('data-admin-group-body')) return;
      var collapsed = body.classList.toggle('is-collapsed');
      btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });
  });

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

  /* ---------- اعلان‌های شناور سراسری (Global Toast Notifications) ---------- */
  window.showToast = function (message, type, duration) {
    type = type || 'info';
    duration = duration || 3500;
    var container = document.getElementById('global-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'global-toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    var icons = {
      success: '✓',
      danger: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    var toast = document.createElement('div');
    toast.className = 'toast-msg toast-' + type;
    var iconSpan = document.createElement('span');
    iconSpan.style.fontSize = '17px';
    iconSpan.textContent = icons[type] || 'ℹ';
    var textSpan = document.createElement('span');
    textSpan.style.flex = '1';
    textSpan.textContent = message;

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = 'background:none;border:none;cursor:pointer;opacity:.6;font-size:14px;padding:2px 6px';
    closeBtn.addEventListener('click', function () {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(function () { toast.remove(); }, 300);
    });

    toast.appendChild(iconSpan);
    toast.appendChild(textSpan);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    setTimeout(function () {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(function () { toast.remove(); }, 300);
      }
    }, duration);
  };

  /* ---------- مدیریت عملیات گروهی جدول‌های پنل (Bulk Actions) ---------- */
  var selectAllBoxes = qsa('input[data-bulk-select-all]');
  selectAllBoxes.forEach(function (selectAll) {
    var table = selectAll.closest('table') || document;
    var bulkBar = qs('[data-bulk-bar]');
    var countEl = qs('[data-bulk-count]');
    
    function updateBulkBar() {
      var itemBoxes = qsa('input[data-bulk-checkbox]', table);
      var checkedBoxes = qsa('input[data-bulk-checkbox]:checked', table);
      var checkedCount = checkedBoxes.length;

      if (bulkBar) {
        bulkBar.classList.toggle('is-active', checkedCount > 0);
      }
      if (countEl) {
        countEl.textContent = checkedCount + ' مورد انتخاب شده';
      }
      if (selectAll) {
        selectAll.checked = (checkedCount > 0 && checkedCount === itemBoxes.length);
        selectAll.indeterminate = (checkedCount > 0 && checkedCount < itemBoxes.length);
      }
    }

    selectAll.addEventListener('change', function () {
      var itemBoxes = qsa('input[data-bulk-checkbox]', table);
      itemBoxes.forEach(function (box) {
        box.checked = selectAll.checked;
      });
      updateBulkBar();
    });

    table.addEventListener('change', function (e) {
      if (e.target && e.target.hasAttribute('data-bulk-checkbox')) {
        updateBulkBar();
      }
    });

    // Handle bulk action buttons
    qsa('[data-bulk-action]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var action = btn.getAttribute('data-bulk-action');
        var formAction = btn.getAttribute('data-bulk-url');
        var checkedBoxes = qsa('input[data-bulk-checkbox]:checked', table);
        if (!checkedBoxes.length) {
          window.showToast('هیچ موردی انتخاب نشده است', 'warning');
          return;
        }

        var confirmMsg = btn.getAttribute('data-confirm') || 'آیا از اجرای این عملیات گروهی اطمینان دارید؟';
        if (!window.confirm(confirmMsg)) return;

        var ids = checkedBoxes.map(function (b) { return b.value; });
        var csrfToken = (qs('meta[name="csrf-token"]') || {}).content || (qs('input[name="_csrf_token"]') || {}).value || '';

        var form = document.createElement('form');
        form.method = 'POST';
        form.action = formAction;
        
        var csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = '_csrf_token';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        var actionInput = document.createElement('input');
        actionInput.type = 'hidden';
        actionInput.name = 'bulk_action';
        actionInput.value = action;
        form.appendChild(actionInput);

        ids.forEach(function (id) {
          var idInput = document.createElement('input');
          idInput.type = 'hidden';
          idInput.name = 'item_ids[]';
          idInput.value = id;
          form.appendChild(idInput);
        });

        document.body.appendChild(form);
        form.submit();
      });
    });
  });

  /* ---------- وضعیت لودینگ دکمه‌های فرم‌ها ---------- */
  qsa('form:not([data-no-loading])').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (form.checkValidity && !form.checkValidity()) return;
      var submitBtn = qs('button[type="submit"], input[type="submit"]', form);
      if (submitBtn && !submitBtn.classList.contains('is-loading')) {
        submitBtn.classList.add('is-loading');
        // Fallback safety timeout in case page navigation is slow
        setTimeout(function () {
          submitBtn.classList.remove('is-loading');
        }, 12000);
      }
    });
  });

})();
