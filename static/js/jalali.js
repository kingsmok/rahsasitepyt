/* تاریخ‌شمار شمسی سبک — بدون وابستگی خارجی
   تبدیل خودکار input[type=date] به تقویم شمسی + مقداردهی با فرمت ۱۴۰۵/۰۵/۱۵ */
(function () {
  'use strict';

  var MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  var WEEKDAYS = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];

  // ---- تبدیل میلادی → شمسی ----
  function g2j(gy, gm, gd) {
    var g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var gy2 = (gm > 2) ? (gy + 1) : gy;
    var days = 355666 + (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) + gd + g_d_m[gm - 1];
    var jy = -1595 + (33 * Math.floor(days / 12053));
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
    var jm, jd;
    if (days < 186) { jm = 1 + Math.floor(days / 31); jd = 1 + (days % 31); }
    else { jm = 7 + Math.floor((days - 186) / 30); jd = 1 + ((days - 186) % 30); }
    return [jy, jm, jd];
  }

  // ---- تبدیل شمسی → میلادی ----
  function j2g(jy, jm, jd) {
    jy += 1595;
    var days = -355668 + (365 * jy) + (Math.floor(jy / 33) * 8) + Math.floor(((jy % 33) + 3) / 4) + jd;
    if (jm < 7) { days += (jm - 1) * 31; } else { days += 186 + ((jm - 7) * 30); }
    var gy = 400 * Math.floor(days / 146097);
    days %= 146097;
    if (days > 36524) { days--; gy += 100 * Math.floor(days / 36524); days %= 36524; if (days >= 365) days++; }
    gy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) { gy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
    var gd = days + 1;
    var leap = (gy % 4 === 0 && (gy % 100 !== 0 || gy % 400 === 0));
    var g_d_m = leap ? [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
                     : [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var gm = 0;
    for (var i = 0; i < 12; i++) { if (gd <= g_d_m[i + 1]) { gm = i + 1; break; } }
    gd -= g_d_m[gm - 1];
    return [gy, gm, gd];
  }

  // ---- طول ماه شمسی ----
  function jmonthLen(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    // اسفند — کبیسه
    var leap = ((jy + 1) % 33) % 4 === 0 || ((jy + 1) % 33) === 0;
    // الگوریتم دقیقتر کبیسه
    var a = (jy - 1395) % 33;
    if (a < 0) a += 33;
    var leap2 = (a === 1 || a === 5 || a === 9 || a === 13 || a === 17 || a === 22 || a === 26 || a === 30);
    return leap2 ? 30 : 29;
  }

  function faNum(n) {
    return String(n).replace(/[0-9]/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[+d]; });
  }

  function pad2(n) { return n < 10 ? '0' + n : '' + n; }

  // ---- مقدار اولیه input: اگر میلادی بود → شمسی ----
  function toJalaliStr(iso) {
    if (!iso) return '';
    var m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    var j = g2j(+m[1], +m[2], +m[3]);
    return j[0] + '/' + pad2(j[1]) + '/' + pad2(j[2]);
  }

  function jalaliToIso(str) {
    var m = String(str || '').replace(/-/g, '/').match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);
    if (!m) return '';
    var g = j2g(+m[1], +m[2], +m[3]);
    return g[0] + '-' + pad2(g[1]) + '-' + pad2(g[2]);
  }

  // ---- ساخت پاپ‌آپ تقویم ----
  var picker = null;
  function openPicker(input, anchor) {
    closePicker();
    picker = document.createElement('div');
    picker.className = 'jalali-picker';
    picker.style.cssText = 'position:absolute;z-index:99999;background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 16px 48px rgba(15,23,42,.18);padding:14px;width:280px;direction:rtl;font-family:inherit';
    var rect = anchor.getBoundingClientRect();
    picker.style.top = (rect.bottom + window.scrollY + 6) + 'px';
    picker.style.left = Math.max(8, rect.left + window.scrollX) + 'px';

    // تاریخ نمایشی
    var now = new Date();
    var cur = g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
    var shown = { jy: cur[0], jm: cur[1] };
    var selected = null;

    function render() {
      // اولین روز ماه — محاسبه روز هفته
      var gFirst = j2g(shown.jy, shown.jm, 1);
      var firstDow = new Date(gFirst[0], gFirst[1] - 1, 1).getDay(); // 0=یکشنبه
      var dowShift = (firstDow + 1) % 7; // تبدیل به شمسی: شنبه=0
      var len = jmonthLen(shown.jy, shown.jm);

      var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
        + '<button type="button" data-nav="-1" style="border:none;background:none;cursor:pointer;font-size:15px;color:#64748b">›</button>'
        + '<strong style="font-size:13.5px">' + MONTHS[shown.jm - 1] + ' ' + faNum(shown.jy) + '</strong>'
        + '<button type="button" data-nav="1" style="border:none;background:none;cursor:pointer;font-size:15px;color:#64748b">‹</button></div>'
        + '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;margin-bottom:6px">';
      for (var w = 0; w < 7; w++) {
        html += '<div style="font-size:10.5px;color:#94a3b8;padding:3px 0">' + WEEKDAYS[w] + '</div>';
      }
      html += '</div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center">';
      for (var b = 0; b < dowShift; b++) html += '<div></div>';
      for (var d = 1; d <= len; d++) {
        var isSel = selected && selected[1] === shown.jm && selected[2] === d && selected[0] === shown.jy;
        var isToday = cur[1] === shown.jm && cur[2] === d && cur[0] === shown.jy;
        html += '<button type="button" data-day="' + d + '" style="border:none;border-radius:8px;padding:6px 0;cursor:pointer;font-size:12.5px;'
          + (isSel ? 'background:var(--primary,#f2640c);color:#fff;font-weight:800'
             : isToday ? 'background:#fef3c7;color:#92400e;font-weight:700'
             : 'background:transparent;color:#334155') + '">' + faNum(d) + '</button>';
      }
      html += '</div>'
        + '<div style="display:flex;justify-content:space-between;margin-top:10px">'
        + '<button type="button" data-today style="border:none;background:#f1f5f9;border-radius:8px;padding:5px 12px;font-size:11.5px;cursor:pointer;color:#475569">امروز</button>'
        + '<button type="button" data-clear style="border:none;background:none;font-size:11.5px;cursor:pointer;color:#dc2626">پاک کردن</button></div>';
      picker.innerHTML = html;

      picker.querySelectorAll('[data-nav]').forEach(function (b) {
        b.addEventListener('click', function () {
          shown.jm += +b.dataset.nav;
          if (shown.jm < 1) { shown.jm = 12; shown.jy--; }
          if (shown.jm > 12) { shown.jm = 1; shown.jy++; }
          render();
        });
      });
      picker.querySelectorAll('[data-day]').forEach(function (b) {
        b.addEventListener('click', function () {
          selected = [shown.jy, shown.jm, +b.dataset.day];
          input.value = selected[0] + '/' + pad2(selected[1]) + '/' + pad2(selected[2]);
          input.dataset.value = jalaliToIso(input.value);
          input.dispatchEvent(new Event('change', { bubbles: true }));
          closePicker();
        });
      });
      var todayBtn = picker.querySelector('[data-today]');
      if (todayBtn) todayBtn.addEventListener('click', function () {
        selected = [cur[0], cur[1], cur[2]];
        input.value = selected[0] + '/' + pad2(selected[1]) + '/' + pad2(selected[2]);
        input.dataset.value = jalaliToIso(input.value);
        input.dispatchEvent(new Event('change', { bubbles: true }));
        closePicker();
      });
      var clearBtn = picker.querySelector('[data-clear]');
      if (clearBtn) clearBtn.addEventListener('click', function () {
        input.value = '';
        delete input.dataset.value;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        closePicker();
      });
    }
    render();
    document.body.appendChild(picker);
  }

  function closePicker() {
    if (picker) { picker.remove(); picker = null; }
  }
  document.addEventListener('click', function (e) {
    if (picker && !picker.contains(e.target) && !e.target.closest('[data-jalali]')) closePicker();
  });
  window.addEventListener('scroll', closePicker, true);

  // ---- فعال‌سازی روی input ها ----
  function init() {
    document.querySelectorAll('input[type="date"], input[data-jalali]').forEach(function (input) {
      if (input.dataset.jalaliInit) return;
      input.dataset.jalaliInit = '1';
      // مقدار اولیه
      if (input.value) {
        var iso = input.value.match(/^\d{4}-\d{2}-\d{2}/) ? input.value : jalaliToIso(input.value);
        if (iso) { input.dataset.value = iso; input.value = toJalaliStr(iso); }
      }
      input.type = 'text';
      input.placeholder = input.placeholder || '۱۴۰۵/۰۵/۱۵';
      input.dir = 'ltr';
      input.style.textAlign = 'center';
      input.addEventListener('focus', function () { openPicker(input, input); });
      input.addEventListener('input', function () {
        input.dataset.value = jalaliToIso(input.value);
      });
    });
  }

  // قبل از submit: مقدار میلادی جایگزین مقدار شمسی نمایشی می‌شود
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    form.querySelectorAll('input[data-jalali-init]').forEach(function (inp) {
      if (inp.dataset.value) inp.value = inp.dataset.value;
      else if (inp.value) inp.value = jalaliToIso(inp.value);
    });
  }, true);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  // برای محتوای داینامیک (صفحه‌ساز)
  setTimeout(init, 600);
})();
