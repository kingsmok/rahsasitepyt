/* زنگ هشدار پنل مدیریت — تیکت‌ها، سفارش‌ها و فیش‌های در انتظار
 *
 * هر ۳۰ ثانیه /admin/api/alerts را می‌خواند. اگر مورد جدیدی نسبت به آخرین
 * بررسی وجود داشته باشد، بج قرمز می‌تپد و (در صورت فعال بودن) صدای کوتاه
 * پخش می‌شود. وقتی تب پنهان است polling متوقف می‌شود تا منابع هدر نرود.
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-admin-alarm]');
  if (!root) return;

  var POLL_MS = 30000;
  var API = '/admin/api/alerts';
  var LS_TICKET = 'adminAlarm.lastTicketId';
  var LS_ORDER = 'adminAlarm.lastOrderId';
  var LS_SOUND = 'adminAlarm.sound';

  var btn = root.querySelector('[data-alarm-toggle]');
  var panel = root.querySelector('[data-alarm-panel]');
  var badge = root.querySelector('[data-alarm-count]');
  var elTickets = root.querySelector('[data-alarm-tickets]');
  var elOrders = root.querySelector('[data-alarm-orders]');
  var elProofs = root.querySelector('[data-alarm-proofs]');
  var elEmpty = root.querySelector('[data-alarm-empty]');
  var soundBox = root.querySelector('[data-alarm-sound]');
  var timer = null;

  var FA = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[+d]; }); }

  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  if (soundBox) {
    soundBox.checked = read(LS_SOUND) !== '0';
    soundBox.addEventListener('change', function () {
      store(LS_SOUND, soundBox.checked ? '1' : '0');
    });
  }

  /* بوق کوتاه با WebAudio — بدون نیاز به فایل صوتی */
  function beep() {
    if (soundBox && !soundBox.checked) return;
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      var ctx = new Ctx();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.setValueAtTime(1180, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.16, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.32);
      osc.start(); osc.stop(ctx.currentTime + 0.34);
      setTimeout(function () { try { ctx.close(); } catch (e) {} }, 700);
    } catch (e) { /* صدا اختیاری است */ }
  }

  function setRow(el, n) {
    if (!el) return;
    el.textContent = fa(n);
    var row = el.closest('.admin-alarm__row');
    if (row) row.classList.toggle('is-zero', !n);
  }

  function render(d) {
    root.hidden = false;
    var total = d.total || 0;
    setRow(elTickets, d.tickets || 0);
    setRow(elOrders, d.orders || 0);
    setRow(elProofs, d.proofs || 0);
    if (elEmpty) elEmpty.hidden = total > 0;
    if (badge) {
      badge.hidden = !total;
      badge.textContent = fa(total > 99 ? 99 : total);
    }
    root.classList.toggle('has-alerts', total > 0);
    if (total > 0) {
      document.title = '(' + total + ') ' + document.title.replace(/^\(\d+\)\s*/, '');
    } else {
      document.title = document.title.replace(/^\(\d+\)\s*/, '');
    }
  }

  function ring() {
    root.classList.add('is-ringing');
    setTimeout(function () { root.classList.remove('is-ringing'); }, 2200);
    beep();
  }

  function poll(first) {
    fetch(API, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.ok) return;
        render(d);
        var lastT = parseInt(read(LS_TICKET) || '0', 10);
        var lastO = parseInt(read(LS_ORDER) || '0', 10);
        var freshT = (d.latest_ticket_id || 0) > lastT;
        var freshO = (d.latest_order_id || 0) > lastO;
        if (!first && (freshT || freshO)) ring();
        store(LS_TICKET, d.latest_ticket_id || 0);
        store(LS_ORDER, d.latest_order_id || 0);
      })
      .catch(function () { /* شبکه قطع — دفعه بعد دوباره تلاش می‌شود */ });
  }

  function start() {
    if (timer) return;
    timer = setInterval(poll, POLL_MS);
  }
  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
  }

  if (btn && panel) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = !panel.hidden;
      panel.hidden = open;
      btn.setAttribute('aria-expanded', String(!open));
    });
    document.addEventListener('click', function (e) {
      if (!panel.hidden && !root.contains(e.target)) {
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) {
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { stop(); } else { poll(); start(); }
  });

  poll(true);
  start();
})();
