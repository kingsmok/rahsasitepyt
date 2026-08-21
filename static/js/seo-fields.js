/* پنل سئوی فرم‌های محتوا — شمارندهٔ طول + پیش‌نمایش زندهٔ نتیجهٔ گوگل */
(function () {
  'use strict';

  var FA = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  function fa(n) {
    return String(n).replace(/\d/g, function (d) { return FA[+d]; });
  }

  function initCounter(el) {
    var limit = parseInt(el.getAttribute('data-seo-count'), 10) || 60;
    var group = el.closest('.form-group');
    var out = group && group.querySelector('.seo-count');
    if (!out) return;
    function upd() {
      var n = (el.value || '').length;
      out.textContent = fa(n);
      out.classList.toggle('over', n > limit);
      out.classList.toggle('good', n > 0 && n <= limit);
    }
    el.addEventListener('input', upd);
    upd();
  }

  function initPreview(panel) {
    var pT = panel.querySelector('[data-seo-preview="title"]');
    var pD = panel.querySelector('[data-seo-preview="desc"]');
    var pU = panel.querySelector('[data-seo-preview="url"]');
    if (!pT || !pD) return;

    var seoTitle = panel.querySelector('[name="seo_title"]');
    var seoDesc = panel.querySelector('[name="seo_description"]');
    var form = panel.closest('form');
    var mainTitle = form && form.querySelector('[name="title"]');
    var slugField = form && form.querySelector('[name="slug"]');
    var baseUrl = pU ? (pU.textContent || '').replace(/…\s*$/, '') : '';

    function upd() {
      var t = (seoTitle && seoTitle.value.trim()) ||
              (mainTitle && mainTitle.value.trim()) || 'عنوان مطلب';
      var d = (seoDesc && seoDesc.value.trim()) ||
              'توضیحات متا اینجا نمایش داده می‌شود.';
      pT.textContent = t.length > 60 ? t.slice(0, 60) + '…' : t;
      pD.textContent = d.length > 158 ? d.slice(0, 158) + '…' : d;
      if (pU) {
        var s = (slugField && slugField.value.trim()) || '';
        pU.textContent = baseUrl + (s || '…');
      }
    }
    [seoTitle, seoDesc, mainTitle, slugField].forEach(function (el) {
      if (el) el.addEventListener('input', upd);
    });
    upd();
  }

  function boot() {
    var panels = document.querySelectorAll('.seo-panel');
    if (!panels.length) return;
    Array.prototype.forEach.call(
      document.querySelectorAll('.seo-panel [data-seo-count]'), initCounter);
    Array.prototype.forEach.call(panels, initPreview);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
