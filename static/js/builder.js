/* ============================================================
   صفحه‌ساز بصری — بازنویسی به سبک المنتور
   بوم داخل iframe (پیش‌نمایش واقعی دستگاه‌ها) + پنل تب‌دار + درگ‌انددراپ
   ============================================================ */
(function () {
'use strict';

/* ---------- داده و تاریخچه ---------- */
var data = JSON.parse(JSON.stringify(window.PB_DATA || { settings: {}, rows: [] }));
if (!data.settings) data.settings = {};
if (!data.rows) data.rows = [];
var history = [], historyIdx = -1, historyLock = false;
function snapshot() { return JSON.stringify(data); }
function pushHistory() {
  if (historyLock) return;
  history = history.slice(0, historyIdx + 1);
  history.push(snapshot());
  if (history.length > 60) history.shift();
  historyIdx = history.length - 1;
}
function undo() {
  if (historyIdx <= 0) return;
  historyIdx--; historyLock = true;
  data = JSON.parse(history[historyIdx]); historyLock = false;
  render(true); showPagePanel(); toast('↩️ واگردانی شد');
}
function redo() {
  if (historyIdx >= history.length - 1) return;
  historyIdx++; historyLock = true;
  data = JSON.parse(history[historyIdx]); historyLock = false;
  render(true); showPagePanel(); toast('↪️ از نو انجام شد');
}
pushHistory();

/* ---------- ارجاع‌ها ---------- */
var ASSET_V = window.PB_ASSET_V || '';
var THEME = window.PB_THEME || 'theme-23';
var WIDGETS = window.PB_WIDGETS || {};
var IMAGES = window.PB_IMAGES || [];
var CAT_OPTS = window.PB_CAT_OPTS || [];
var COURSE_OPTS = window.PB_COURSE_OPTS || [];
var SECTION_TPLS = window.PB_SECTION_TEMPLATES || {};
var PAGE_TPLS = window.PB_PAGE_TEMPLATES || {};
var PREVIEW_URL = window.PB_PREVIEW_URL || '/';
var canvasWrap = document.getElementById('pb-canvas-wrap');
var shell = document.getElementById('pb-frame-shell');
var iframeEl = document.getElementById('pb-frame');
var panelBody = document.getElementById('pb-panel-body');
var panelTitle = document.getElementById('pb-panel-title');
var panelIc = document.getElementById('pb-panel-ic');
var panelSub = document.getElementById('pb-panel-sub');
var saveBtn = document.getElementById('pb-save');
var saveState = document.getElementById('pb-save-state');
var dirty = false, renderTimer = null, sel = null, clipboard = null;
var currentDev = 'desktop', panelTab = 'content', armedType = null;
var pendingScroll = 0;

function uid(p) { return (p || 'w') + '_' + Math.random().toString(36).slice(2, 9); }
function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function toast(msg, type) {
  var box = document.getElementById('pb-toasts');
  var t = document.createElement('div');
  t.className = 'pb-toast ' + (type || '');
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; setTimeout(function () { t.remove(); }, 400); }, 2600);
}
function markDirty() { dirty = true; saveState.textContent = '…در حال ویرایش'; updateStatus(); }
function updateStatus() {
  var rowsN = data.rows.length, wN = 0;
  data.rows.forEach(function (r) { (r.cols || []).forEach(function (c) { wN += c.length; }); });
  document.getElementById('pb-st-rows').textContent = rowsN;
  document.getElementById('pb-st-widgets').textContent = wN;
  var dot = document.getElementById('pb-st-dot');
  dot.className = 'dot ' + (dirty ? 'dirty' : 'ok');
  document.getElementById('pb-st-state').textContent = dirty ? 'تغییرات ذخیره نشده' : 'آماده';
}

/* ---------- جستجوی ویجت‌ها در داده ---------- */
function findWidget(id) {
  function scan(cols, info) {
    for (var ci = 0; ci < cols.length; ci++) {
      for (var wi = 0; wi < cols[ci].length; wi++) {
        var w = cols[ci][wi];
        if (w.id === id) return { cols: cols, ci: ci, wi: wi, w: w, info: info };
        if (w.type === 'inner_section' && w.data && Array.isArray(w.data.cols)) {
          var r = scan(w.data.cols, { inner: true, widget: w });
          if (r) return r;
        }
      }
    }
    return null;
  }
  for (var ri = 0; ri < data.rows.length; ri++) {
    var r = scan(data.rows[ri].cols || [], { inner: false, row: data.rows[ri] });
    if (r) return Object.assign(r, { ri: ri, row: data.rows[ri] });
  }
  return null;
}
function containerOf(f) { return f.info.inner ? f.info.widget.data.cols : f.row.cols; }
function findRow(id) {
  for (var ri = 0; ri < data.rows.length; ri++) if (data.rows[ri].id === id) return { row: data.rows[ri], ri: ri };
  return null;
}
function defaults(type) {
  var d = {};
  var w = WIDGETS[type];
  if (w) (w.fields || []).forEach(function (f) {
    if (f.type === 'repeater') d[f.key] = [];
    else if (f.type === 'checkbox') d[f.key] = false;
    else d[f.key] = '';
  });
  /* اسلایدر: سه اسلاید نمونه پیش‌فرض */
  if (type === 'slider') {
    var imgs = IMAGES.filter(function (i) { return i.indexOf('cover-') === 0; });
    imgs = imgs.length ? imgs : IMAGES;
    d.slides = [
      { img: imgs[0] || '', title: 'دوره‌های حرفه‌ای را همین حالا شروع کنید', sub: 'با بیش از ۲۲۰ درس عملی و مدرسین مجرب، مهارت آینده خود را بسازید.', btn_text: 'مشاهده دوره‌ها', btn_url: '/courses', align: 'right' },
      { img: imgs[1] || imgs[0] || '', title: 'یادگیری با ضمانت بازگشت وجه', sub: 'تا ۷ روز ضمانت بازگشت کامل وجه دارید؛ اگر راضی نبودید پولتان برمی‌گردد.', btn_text: 'ثبت‌نام رایگان', btn_url: '/register', align: 'center' },
      { img: imgs[2] || imgs[0] || '', title: 'همراه با پشتیبانی مدرس', sub: 'در مسیر یادگیری تنها نیستید؛ هر سوالی دارید از مدرس بپرسید.', btn_text: 'دوره‌ها', btn_url: '/courses', align: 'right' }
    ];
    d.height = '420'; d.overlay = '60'; d.autoplay = true; d.interval = '5';
    d.dots = true; d.arrows = true; d.swipe = true;
  }
  return d;
}

/* ============================================================
   رندر بوم (iframe)
   ============================================================ */
var FRAME_CSS = [
  'body.pb-edit-frame{background:#fff}',
  '.pb-edit-frame a:not([contenteditable]){pointer-events:none}',
  '.pb-edit-frame form{pointer-events:none}',
  '.pb-edit-frame [contenteditable]{pointer-events:auto!important;cursor:text}',
  '.pb-edit-frame .pb-slide-arrow,.pb-edit-frame .pb-slide-dots i{pointer-events:auto}',
  /* ردیف */
  '.pb-edit-frame .pb-row{position:relative;transition:outline-color .15s}',
  '.pb-edit-frame .pb-row:hover{outline:1.5px dashed rgba(15,118,110,.55);outline-offset:3px}',
  '.pb-edit-frame .pb-row.pb-row-selected{outline:2px solid #0f766e;outline-offset:3px}',
  '.pb-edit-frame .pb-row.pb-row-locked .pb-container{opacity:.72}',
  '.pb-edit-frame .pb-row-tools{display:none;position:absolute;top:8px;right:12px;z-index:90;background:#0f766e;color:#fff;border-radius:9px;padding:3px;gap:2px;align-items:center;box-shadow:0 6px 18px rgba(15,118,110,.35);height:27px;direction:rtl}',
  '.pb-edit-frame .pb-row:hover .pb-row-tools,.pb-edit-frame .pb-row.pb-row-selected .pb-row-tools{display:flex}',
  '.pb-edit-frame .pb-row-tools .pb-tool{width:23px;height:23px;border-radius:6px;font-size:11px;color:#d7f2ef;display:flex;align-items:center;justify-content:center;background:transparent;border:none}',
  '.pb-edit-frame .pb-row-tools .pb-tool:hover{background:rgba(255,255,255,.22);color:#fff}',
  '.pb-edit-frame .pb-row-tools .pb-tool-del:hover{background:#dc2626}',
  '.pb-edit-frame .pb-row-tools .pb-grip{cursor:grab;padding:0 6px;font-size:13px;color:#d7f2ef}',
  '.pb-edit-frame .pb-row-label{font-size:10px;padding:0 7px;color:#d7f2ef;font-weight:700}',
  '.pb-edit-frame .pb-hidden-badge{font-size:9.5px;background:#f59e0b;color:#fff;border-radius:6px;padding:2px 7px;margin-right:4px}',
  '.pb-edit-frame .pb-tool-lock{background:#f59e0b!important;color:#fff!important}',
  /* ستون */
  '.pb-edit-frame .pb-col{position:relative;min-height:26px}',
  '.pb-edit-frame .pb-col-empty{min-height:110px;background:rgba(15,118,110,.045);border:2px dashed rgba(15,118,110,.4);border-radius:14px;justify-content:center;align-items:center}',
  '.pb-edit-frame .pb-col-empty .pb-col-drop{display:flex}',
  '.pb-edit-frame .pb-col-drop{display:none;align-items:center;justify-content:center;gap:6px;font-size:11px;color:#0f766e;font-weight:700;padding:14px;text-align:center;user-select:none}',
  /* ویجت */
  '.pb-edit-frame .pb-widget{position:relative;border-radius:10px;transition:outline-color .15s;margin:2px 0}',
  '.pb-edit-frame .pb-widget:hover{outline:1.5px dashed rgba(15,118,110,.6);outline-offset:2px}',
  '.pb-edit-frame .pb-widget.pb-widget-selected{outline:2px solid #0f766e;outline-offset:3px}',
  '.pb-edit-frame .pb-widget-tools{display:none;position:absolute;top:6px;right:8px;z-index:95;background:#0d9488;color:#fff;border-radius:8px;padding:3px;gap:2px;align-items:center;box-shadow:0 6px 16px rgba(13,148,136,.4);height:27px;direction:rtl}',
  '.pb-edit-frame .pb-widget:hover .pb-widget-tools,.pb-edit-frame .pb-widget.pb-widget-selected .pb-widget-tools{display:flex}',
  '.pb-edit-frame .pb-widget-tools .pb-tool{width:23px;height:23px;border-radius:6px;font-size:11px;color:#e7f7f5;display:flex;align-items:center;justify-content:center;border:none;background:transparent}',
  '.pb-edit-frame .pb-widget-tools .pb-tool:hover{background:rgba(255,255,255,.22);color:#fff}',
  '.pb-edit-frame .pb-widget-tools .pb-tool-del:hover{background:#dc2626}',
  '.pb-edit-frame .pb-widget-tools .pb-grip{cursor:grab;padding:0 5px;font-size:12px;color:#e7f7f5}',
  '.pb-edit-frame .pb-widget-name{font-size:9.5px;padding:0 6px;color:#e7f7f5;white-space:nowrap;font-weight:700}',
  /* انتخاب و ویرایش درون‌خطی */
  '.pb-edit-frame .pb-widget.pb-widget-selected .pb-widget-body{pointer-events:none}',
  '.pb-edit-frame .pb-widget.pb-widget-selected [contenteditable]{pointer-events:auto!important}',
  '.pb-edit-frame [contenteditable="true"]{outline:1.5px dashed rgba(15,118,110,.0);border-radius:6px;min-width:24px;display:inline-block;transition:outline-color .15s,background .15s}',
  '.pb-edit-frame [contenteditable="true"]:hover{outline-color:rgba(15,118,110,.45);background:rgba(15,118,110,.04)}',
  '.pb-edit-frame [contenteditable="true"]:focus{outline:2px solid #0f766e;background:rgba(15,118,110,.06)}',
  /* حالت مسلح (کلیک برای افزودن) */
  '.pb-edit-frame body.pb-armed .pb-col{outline:1.5px dashed rgba(15,118,110,.4);outline-offset:2px;cursor:copy}',
  '.pb-edit-frame body.pb-armed .pb-col:hover{background:rgba(15,118,110,.07);outline-color:#0f766e}',
  '.pb-edit-frame body.pb-armed .pb-col-empty{background:rgba(15,118,110,.14);border-color:#0f766e}',
  /* نوار افزودن سکشن */
  '.pb-add-section{display:flex;align-items:center;gap:10px;padding:9px 0;position:relative;direction:rtl}',
  '.pb-add-section::before{content:"";position:absolute;right:0;left:0;top:50%;height:2px;background:transparent;transition:background .2s}',
  '.pb-add-section:hover::before{background:rgba(15,118,110,.3)}',
  '.pb-add-section button{position:relative;z-index:2;margin:0 auto;display:flex;align-items:center;gap:6px;padding:5px 18px;border-radius:99px;border:1.5px dashed rgba(15,118,110,.55);background:rgba(255,255,255,.94);color:#0f766e;font-size:11.5px;font-weight:800;transition:all .18s;cursor:pointer}',
  '.pb-add-section button:hover{background:#0f766e;color:#fff;border-style:solid;transform:scale(1.05)}',
  /* نشانگر رها کردن */
  '.pb-drop-line{position:absolute;right:0;left:0;height:3px;border-radius:3px;background:#0d9488;z-index:120;pointer-events:none;box-shadow:0 0 0 2px rgba(13,148,136,.25)}',
  '.pb-col.pb-col-drop-target{background:rgba(15,118,110,.09);outline:2px dashed #0f766e;outline-offset:2px;border-radius:12px}',
  '.pb-row.pb-row-drop-target{outline:2px dashed #0d9488!important;outline-offset:3px}',
  /* حاشیه درگ */
  '.pb-edit-frame body.pb-dragging *{cursor:grabbing!important}',
  '.pb-slider-empty-edit{display:none}'
].join('\n');

var FRAME_JS = [
  'document.addEventListener("click",function(e){',
  '  var t=e.target.closest("a,button");',
  '  if(t&&!t.closest(".pb-slider")&&!t.closest(".pb-widget-tools")&&!t.closest(".pb-row-tools")&&!t.closest(".pb-add-section")){e.preventDefault();}',
  '},true);',
  'document.addEventListener("submit",function(e){e.preventDefault();},true);'
].join('\n');

function frameDoc(rowsHtml) {
  return '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">'
    + '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    + '<link rel="stylesheet" href="/static/css/base.css?v=' + ASSET_V + '">'
    + '<link rel="stylesheet" href="/static/css/themes/' + THEME + '.css?v=' + ASSET_V + '">'
    + '<link rel="stylesheet" href="/static/css/builder.css?v=' + ASSET_V + '">'
    + '<style>' + FRAME_CSS + '</style></head>'
    + '<body class="pb-edit-frame"><div id="pb-f-canvas">'
    + rowsHtml
    + '</div>'
    + '<script src="/static/js/app.js?v=' + ASSET_V + '"><\/script>'
    + '<script>' + FRAME_JS + '<\/script>'
    + '</body></html>';
}

/* بین ردیف‌ها نوار «افزودن سکشن» می‌گذارد */
function addSectionBars(html) {
  var parts = [];
  var reRow = /<div class="pb-row[^"]*"[^>]*>[\s\S]*?<\/div>\n<\/div>/g;
  var mm, prev = 0;
  while ((mm = reRow.exec(html)) !== null) {
    parts.push(html.slice(prev, mm.index));
    parts.push('@@ROW@@' + mm[0]);
    prev = mm.index + mm[0].length;
  }
  parts.push(html.slice(prev));
  var res = '';
  var ri = 0;
  parts.forEach(function (p) {
    if (p.indexOf('@@ROW@@') === 0) {
      res += p.slice(7);
      ri++;
      res += '<div class="pb-add-section" data-pos="' + ri + '"><button type="button">+ افزودن سکشن</button></div>';
    } else {
      res += p;
    }
  });
  if (!res.trim()) res = '<div class="pb-add-section" data-pos="0"><button type="button">+ افزودن سکشن</button></div>';
  return res;
}

function render(silent) {
  buildNavigator();
  if (!silent && sel) { /* پنل باز بماند */ }
  return fetch('/builder/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: data.rows, settings: data.settings, edit: true })
  }).then(function (r) { return r.json(); }).then(function (res) {
    if (!res.ok) { toast('خطا در رندر صفحه', 'err'); return; }
    var prevScroll = 0;
    try { prevScroll = iframeEl.contentWindow ? iframeEl.contentWindow.scrollY : 0; } catch (e) { }
    pendingScroll = prevScroll;
    var empty = document.getElementById('pb-empty');
    if (!data.rows.length) {
      empty.style.display = 'flex';
      iframeEl.srcdoc = '';
    } else {
      empty.style.display = 'none';
      iframeEl.srcdoc = frameDoc(addSectionBars(res.html));
      iframeEl.onload = function () {
        bindFrame();
        restoreSelection();
        applyArmedFrame();
        try { iframeEl.contentWindow.scrollTo(0, pendingScroll); } catch (e) { }
      };
    }
  }).catch(function () { toast('خطا در ارتباط با سرور', 'err'); });
}
function scheduleRender() { markDirty(); clearTimeout(renderTimer); renderTimer = setTimeout(function () { render(); }, 350); }
function immediateRender() { clearTimeout(renderTimer); render(); }

/* ============================================================
   اتصال رویدادهای داخل iframe
   ============================================================ */
function bindFrame() {
  var doc = iframeEl.contentDocument;
  if (!doc) return;
  doc.addEventListener('click', function (e) {
    var t = e.target;
    /* دکمه‌های ابزار ویجت */
    var wt = t.closest('[data-wid-up],[data-wid-down],[data-wid-copy],[data-wid-del]');
    if (wt) {
      e.preventDefault(); e.stopPropagation();
      var wid = wt.closest('.pb-widget').dataset.wid;
      var f = findWidget(wid); if (!f) return;
      if (wt.hasAttribute('data-wid-up')) moveWidget(f, -1);
      else if (wt.hasAttribute('data-wid-down')) moveWidget(f, 1);
      else if (wt.hasAttribute('data-wid-copy')) copyWidget(f);
      else if (wt.hasAttribute('data-wid-del')) delWidget(f);
      return;
    }
    /* دکمه‌های ابزار ردیف */
    var rt = t.closest('[data-row-up],[data-row-down],[data-row-copy],[data-row-del],[data-row-save],[data-row-lock]');
    if (rt) {
      e.preventDefault(); e.stopPropagation();
      var rid = rt.closest('.pb-row').dataset.row;
      var fr = findRow(rid); if (!fr) return;
      if (rt.hasAttribute('data-row-up')) moveRow(fr, -1);
      else if (rt.hasAttribute('data-row-down')) moveRow(fr, 1);
      else if (rt.hasAttribute('data-row-copy')) copyRow(fr);
      else if (rt.hasAttribute('data-row-del')) delRow(fr);
      else if (rt.hasAttribute('data-row-save')) saveRowTemplate(fr);
      else if (rt.hasAttribute('data-row-lock')) toggleRowLock(fr);
      return;
    }
    /* نوار افزودن سکشن */
    var ab = t.closest('.pb-add-section');
    if (ab) { e.preventDefault(); e.stopPropagation(); openAddSection(ab); return; }
    /* حالت مسلح: کلیک روی هر جای ستون = افزودن ویجت (مثل المنتور)؛
       خروج از حالت مسلح با Esc یا کلیک دوباره روی همان ویجت در پالت */
    if (armedType) {
      var col0 = t.closest('.pb-col');
      if (col0) { e.preventDefault(); e.stopPropagation(); insertWidgetInCol(col0); return; }
    }
    /* انتخاب ویجت */
    var w = t.closest('.pb-widget');
    if (w && w.dataset.wid) { e.stopPropagation(); selectWidget(w.dataset.wid); return; }
    /* انتخاب ردیف */
    var r = t.closest('.pb-row');
    if (r && r.dataset.row) { e.stopPropagation(); selectRow(r.dataset.row); return; }
    /* کلیک روی بوم خالی */
    if (t.id === 'pb-f-canvas' || t.closest('#pb-f-canvas')) { if (!sel) return; deselect(); }
  });

  /* شروع درگ با دستگیره */
  doc.addEventListener('pointerdown', function (e) {
    var grip = e.target.closest('.pb-grip');
    if (!grip) return;
    e.preventDefault(); e.stopPropagation();
    var frRect = iframeEl.getBoundingClientRect();
    var kind = grip.closest('.pb-widget') ? 'widget' : 'row';
    var el = grip.closest(kind === 'widget' ? '.pb-widget' : '.pb-row');
    if (!el) return;
    var id = kind === 'widget' ? el.dataset.wid : el.dataset.row;
    /* preventDefault در pointerdown مانع implicit capture می‌شود؛ با pointer-events:none
       روی iframe، رویدادهای بعدی به سند والد می‌رسند */
    startDrag({ kind: kind, id: id }, frRect.left + e.clientX, frRect.top + e.clientY);
  });

  /* Escape داخل بوم: به سند والد فوروارد شود (لغو حالت مسلح/درگ) */
  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    }
  });

  /* اگر pointermove/up به‌جای سند والد در سند فریم تحویل شود (رفتار برخی مرورگرها)
     آن‌ها را به منطق درگ والد فوروارد کن */
  doc.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var frRect = iframeEl.getBoundingClientRect();
    onDragMove({ clientX: frRect.left + e.clientX, clientY: frRect.top + e.clientY });
  });
  doc.addEventListener('pointerup', function (e) {
    if (!drag) return;
    var frRect = iframeEl.getBoundingClientRect();
    onDragUp({ clientX: frRect.left + e.clientX, clientY: frRect.top + e.clientY });
  });
  doc.addEventListener('pointercancel', function () {
    if (!drag) return;
    onDragCancel();
  });

  /* ویرایش درون‌خطی */
  doc.addEventListener('input', function (e) {
    var el = e.target.closest('[contenteditable="true"]');
    if (!el) return;
    var w = el.closest('.pb-widget'); if (!w) return;
    var f = findWidget(w.dataset.wid); if (!f) return;
    f.w.data[el.dataset.inline || 'text'] = el.innerText;
    markDirty();
  });
  doc.addEventListener('focusout', function (e) {
    if (e.target.closest('[contenteditable="true"]')) render(true);
  }, true);

  /* دابل‌کلیک = ویرایش درون‌خطی */
  doc.addEventListener('dblclick', function (e) {
    var w = e.target.closest('.pb-widget');
    if (!w) return;
    var ce = w.querySelector('[contenteditable="true"]');
    if (ce) { e.preventDefault(); e.stopPropagation(); selectWidget(w.dataset.wid); ce.focus(); }
  });
}

/* ============================================================
   انتخاب
   ============================================================ */
function doc() { try { return iframeEl.contentDocument; } catch (e) { return null; } }
function selectWidget(id) {
  var f = findWidget(id); if (!f) return;
  sel = { type: 'widget', id: id };
  var d = doc();
  if (d) {
    d.querySelectorAll('.pb-widget').forEach(function (el) { el.classList.toggle('pb-widget-selected', el.dataset.wid === id); });
    d.querySelectorAll('.pb-row').forEach(function (el) { el.classList.remove('pb-row-selected'); });
  }
  var w = WIDGETS[f.w.type];
  panelTitle.textContent = w ? w.name : 'ویجت';
  panelIc.textContent = w ? (w.icon || '🧩') : '🧩';
  panelSub.textContent = 'ویجت';
  buildWidgetPanel(f);
}
function selectRow(id) {
  sel = { type: 'row', id: id };
  var d = doc();
  if (d) {
    d.querySelectorAll('.pb-row').forEach(function (el) { el.classList.toggle('pb-row-selected', el.dataset.row === id); });
    d.querySelectorAll('.pb-widget').forEach(function (el) { el.classList.remove('pb-widget-selected'); });
  }
  panelTitle.textContent = 'سکشن';
  panelIc.textContent = '▤';
  panelSub.textContent = 'ردیف';
  buildRowPanel(findRow(id));
}
function deselect() { sel = null; showPagePanel(); }
function restoreSelection() {
  var d = doc(); if (!d) return;
  if (!sel) { buildNavigator(); return; }
  if (sel.type === 'widget') {
    var el = d.querySelector('[data-wid="' + sel.id + '"]');
    if (el) el.classList.add('pb-widget-selected');
    else { sel = null; showPagePanel(); }
  } else {
    var el2 = d.querySelector('[data-row="' + sel.id + '"]');
    if (el2) el2.classList.add('pb-row-selected');
    else { sel = null; showPagePanel(); }
  }
  buildNavigator();
}
function scrollToElInFrame(q) {
  var d = doc(); if (!d) return;
  var el = d.querySelector(q);
  if (el) { try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) { } }
}

/* ============================================================
   عملیات داده
   ============================================================ */
function addRow(colsCount, pos) {
  var cols = [];
  for (var i = 0; i < colsCount; i++) cols.push([]);
  var row = { id: uid('r'), settings: { gap: 24, py: 50 }, cols: cols };
  if (pos === undefined || pos === null) data.rows.push(row);
  else data.rows.splice(Math.max(0, Math.min(pos, data.rows.length)), 0, row);
  pushHistory();
  return row.id;
}
function moveWidget(f, dir) {
  var cols = containerOf(f);
  if (dir === -1 && f.wi > 0) {
    var w = cols[f.ci].splice(f.wi, 1)[0];
    cols[f.ci].splice(f.wi - 1, 0, w); pushHistory();
  }
  if (dir === 1 && f.wi < cols[f.ci].length - 1) {
    var w2 = cols[f.ci].splice(f.wi, 1)[0];
    cols[f.ci].splice(f.wi + 1, 0, w2); pushHistory();
  }
  scheduleRender();
}
function copyWidget(f) {
  var copy = JSON.parse(JSON.stringify(f.w));
  copy.id = uid();
  var cols = containerOf(f);
  cols[f.ci].splice(f.wi + 1, 0, copy);
  pushHistory(); scheduleRender();
  toast('ویجت کپی شد ⧉');
}
function delWidget(f) {
  var cols = containerOf(f);
  cols[f.ci].splice(f.wi, 1);
  pushHistory(); sel = null; showPagePanel(); scheduleRender();
}
function moveRow(f, dir) {
  var to = f.ri + dir;
  if (to < 0 || to >= data.rows.length) return;
  var item = data.rows.splice(f.ri, 1)[0];
  data.rows.splice(to, 0, item);
  pushHistory(); scheduleRender();
}
function copyRow(f) {
  var copy = JSON.parse(JSON.stringify(f.row));
  copy.id = uid('r');
  copy.cols.forEach(function (col) { col.forEach(function (w) { w.id = uid(); }); });
  data.rows.splice(f.ri + 1, 0, copy);
  pushHistory(); scheduleRender();
  toast('سکشن کپی شد ⧉');
}
function delRow(f) {
  data.rows.splice(f.ri, 1);
  pushHistory(); sel = null; showPagePanel(); scheduleRender();
}
function toggleRowLock(f) {
  f.row.settings = f.row.settings || {};
  f.row.settings.locked = !f.row.settings.locked;
  pushHistory(); render(true);
  toast(f.row.settings.locked ? '🔒 سکشن قفل شد' : '🔓 سکشن باز شد', 'ok');
}
function saveRowTemplate(f) {
  var name = prompt('نام این قالب سکشن:', 'سکشن ' + (f.row.id || ''));
  if (!name) return;
  fetch('/builder/api/section-template', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, row: f.row })
  }).then(function (r) { return r.json(); }).then(function (d2) {
    if (d2.ok) { toast('⭐ سکشن به کتابخانه اضافه شد', 'ok'); } else { toast(d2.msg || 'خطا', 'err'); }
  }).catch(function () { toast('خطا در ارتباط', 'err'); });
}

/* ============================================================
   درگ‌انددراپ (با مختصات والد + iframe)
   ============================================================ */
var drag = null;
function startDrag(payload, px, py) {
  if (drag) cancelDrag();
  drag = { payload: payload, ghost: null, src: null, srcRow: null };
  if (payload.kind === 'widget') {
    var f = findWidget(payload.id);
    if (f) drag.src = { inner: !!f.info.inner, cid: f.info.inner ? f.info.widget.id : f.row.id, ci: f.ci, wi: f.wi };
  }
  if (payload.kind === 'row') {
    var fr = findRow(payload.id);
    if (fr) drag.srcRow = fr.ri;
  }
  iframeEl.style.pointerEvents = 'none';
  document.body.classList.add('pb-dragging');
  var g = document.createElement('div');
  g.className = 'pb-drag-ghost';
  var label = '', ic = '🧩';
  if (payload.kind === 'new') { var wd = WIDGETS[payload.type]; label = wd ? wd.name : payload.type; ic = wd ? (wd.icon || '🧩') : '🧩'; }
  else if (payload.kind === 'widget') { var f2 = findWidget(payload.id); var wd2 = f2 ? WIDGETS[f2.w.type] : null; label = wd2 ? wd2.name : 'ویجت'; ic = wd2 ? (wd2.icon || '🧩') : '🧩'; }
  else { var frr = findRow(payload.id); label = 'سکشن ' + (frr ? frr.row.cols.length : 1) + ' ستونه'; ic = '▤'; }
  g.innerHTML = '<span class="pb-drag-ic">' + ic + '</span><span>' + label + '</span>';
  g.style.left = (px - 10) + 'px';
  g.style.top = (py - 12) + 'px';
  document.body.appendChild(g);
  drag.ghost = g;
  document.addEventListener('pointermove', onDragMove);
  document.addEventListener('pointerup', onDragUp);
  document.addEventListener('pointercancel', onDragCancel);
  onDragMove({ clientX: px, clientY: py });
}
function onDragMove(e) {
  if (!drag || !drag.ghost) return;
  drag.ghost.style.left = (e.clientX - 10) + 'px';
  drag.ghost.style.top = (e.clientY - 12) + 'px';
  updateIndicators(e.clientX, e.clientY);
}
function onDragUp(e) { if (drag) dropAt(e.clientX, e.clientY); }
function onDragCancel() { cancelDrag(); }
function cancelDrag() {
  if (!drag) return;
  if (drag.ghost) drag.ghost.remove();
  drag = null;
  document.removeEventListener('pointermove', onDragMove);
  document.removeEventListener('pointerup', onDragUp);
  document.removeEventListener('pointercancel', onDragCancel);
  iframeEl.style.pointerEvents = '';
  document.body.classList.remove('pb-dragging');
  clearIndicators();
}
function localPoint(px, py) {
  var fr = iframeEl.getBoundingClientRect();
  return { x: px - fr.left, y: py - fr.top, fr: fr };
}
function clearIndicators() {
  var d = doc(); if (!d) return;
  d.querySelectorAll('.pb-drop-line, .pb-col-drop-target, .pb-row-drop-target').forEach(function (el) {
    if (el.classList.contains('pb-drop-line')) el.remove();
    else el.classList.remove('pb-col-drop-target', 'pb-row-drop-target');
  });
  /* ایندکس درج را نگه می‌داریم */
  if (d.body) d.body.dataset.dropIdx = '';
  if (d.body) d.body.dataset.dropCol = '';
}
function updateIndicators(px, py) {
  clearIndicators();
  var d = doc(); if (!d) return;
  var lp = localPoint(px, py);
  if (lp.x < 0 || lp.y < 0 || lp.x > lp.fr.width || lp.y > lp.fr.height) return;
  var el = d.elementFromPoint(lp.x, lp.y);
  if (!el) return;
  if (drag.payload.kind === 'row') {
    var rowEl = el.closest('.pb-row');
    if (rowEl) {
      var r = rowEl.getBoundingClientRect();
      var line = d.createElement('div');
      line.className = 'pb-drop-line';
      if (lp.y < r.top + r.height / 2) rowEl.parentNode.insertBefore(line, rowEl);
      else rowEl.parentNode.insertBefore(line, rowEl.nextSibling);
      rowEl.classList.add('pb-row-drop-target');
    }
    return;
  }
  var colEl = el.closest('.pb-col');
  if (colEl) {
    colEl.classList.add('pb-col-drop-target');
    var widgets = colEl.querySelectorAll(':scope > .pb-widget');
    var idx = widgets.length;
    widgets.forEach(function (w, i) {
      var wr = w.getBoundingClientRect();
      if (lp.y > wr.top + wr.height / 2) idx = i + 1;
    });
    var line2 = d.createElement('div');
    line2.className = 'pb-drop-line';
    if (idx === 0) colEl.insertBefore(line2, colEl.firstChild);
    else if (widgets[idx - 1]) widgets[idx - 1].parentNode.insertBefore(line2, widgets[idx - 1].nextSibling);
    else colEl.appendChild(line2);
    if (d.body) { d.body.dataset.dropIdx = idx; d.body.dataset.dropCol = colEl.dataset.col; }
    return;
  }
  if (el.closest('#pb-f-canvas') && drag.payload.kind === 'new') {
    var rows = d.querySelectorAll('#pb-f-canvas > .pb-row');
    var lastR = rows[rows.length - 1];
    if (lastR) {
      var line3 = d.createElement('div');
      line3.className = 'pb-drop-line';
      lastR.parentNode.insertBefore(line3, lastR.nextSibling);
    }
  }
}
function dropAt(px, py) {
  if (!drag) return;
  var d = doc();
  var lp = localPoint(px, py);
  var el = (d && lp.x >= 0 && lp.y >= 0) ? d.elementFromPoint(lp.x, lp.y) : null;
  var did = false;
  var kind = drag.payload.kind;

  if (el && kind === 'row') {
    var rowEl = el.closest('.pb-row');
    if (rowEl) {
      var fr = findRow(rowEl.dataset.row);
      var from = findRow(drag.payload.id);
      if (fr && from && from.ri !== fr.ri) {
        var r = rowEl.getBoundingClientRect();
        var before = lp.y < r.top + r.height / 2;
        var item = data.rows.splice(from.ri, 1)[0];
        var toIdx = fr.ri;
        if (from.ri < fr.ri) toIdx = fr.ri - 1;
        data.rows.splice(before ? toIdx : toIdx + 1, 0, item);
        pushHistory();
        toast('سکشن جابه‌جا شد ✅', 'ok');
        did = true;
      }
    }
  } else if (el && kind === 'widget') {
    var colEl = el.closest('.pb-col');
    if (colEl) {
      var tgt = targetContainerFor(colEl);
      var ci = parseInt(colEl.dataset.col, 10);
      if (tgt && tgt.cols[ci]) {
        var idx = parseInt((d && d.body ? d.body.dataset.dropIdx : '') || tgt.cols[ci].length, 10);
        var f = findWidget(drag.payload.id);
        if (f) {
          var same = (!!f.info.inner === !!tgt.inner) && (f.info.inner ? f.info.widget.id === tgt.widgetId : f.row.id === tgt.rowId);
          var wobj = containerOf(f)[f.ci].splice(f.wi, 1)[0];
          if (same && f.ci === ci && f.wi < idx) idx -= 1;
          tgt.cols[ci].splice(Math.max(0, idx), 0, wobj);
          pushHistory();
          toast('ویجت جابه‌جا شد ✅', 'ok');
          did = true;
        }
      }
    }
  } else if (el && kind === 'new') {
    var colEl2 = el.closest('.pb-col');
    if (colEl2) {
      var tgt2 = targetContainerFor(colEl2);
      var ci2 = parseInt(colEl2.dataset.col, 10);
      if (tgt2 && tgt2.cols[ci2]) {
        var idx2 = parseInt((d && d.body ? d.body.dataset.dropIdx : '') || tgt2.cols[ci2].length, 10);
        tgt2.cols[ci2].splice(Math.max(0, idx2), 0, { id: uid(), type: drag.payload.type, data: defaults(drag.payload.type) });
        pushHistory();
        toast('ویجت اضافه شد ✅', 'ok');
        did = true;
      }
    } else {
      var r2 = el.closest('.pb-row');
      if (r2) {
        var fr2 = findRow(r2.dataset.row);
        if (fr2) {
          fr2.row.cols[fr2.row.cols.length - 1].push({ id: uid(), type: drag.payload.type, data: defaults(drag.payload.type) });
          pushHistory();
          toast('ویجت اضافه شد ✅', 'ok');
          did = true;
        }
      }
    }
  }
  /* رها کردن روی بوم خالی/پایین صفحه */
  if (!did && el && el.closest && el.closest('#pb-f-canvas')) {
    var nid = addRow(1);
    var nr = findRow(nid);
    if (kind === 'new' && nr) {
      nr.row.cols[0].push({ id: uid(), type: drag.payload.type, data: defaults(drag.payload.type) });
      pushHistory();
    }
    toast('سکشن جدید اضافه شد ✅', 'ok');
    did = true;
    scrollToElInFrame('[data-row="' + nid + '"]');
  }
  if (!did && kind === 'new' && iframeEl.contentDocument) {
    if (!data.rows.length) addRow(1);
    var last = data.rows[data.rows.length - 1];
    last.cols[0].push({ id: uid(), type: drag.payload.type, data: defaults(drag.payload.type) });
    pushHistory();
    toast('ویجت به انتهای صفحه اضافه شد ✅', 'ok');
    did = true;
  }
  cancelDrag();
  if (did) immediateRender();
}
function targetContainerFor(colEl) {
  var inner = colEl.closest('.pb-inner');
  if (inner) {
    var wid = inner.closest('.pb-widget[data-type="inner_section"]').dataset.wid;
    var f = findWidget(wid);
    if (f && f.w.type === 'inner_section') {
      if (!f.w.data.cols) f.w.data.cols = [];
      return { cols: f.w.data.cols, inner: true, widgetId: f.w.id };
    }
  }
  var rowEl = colEl.closest('.pb-row');
  var fr = rowEl ? findRow(rowEl.dataset.row) : null;
  if (fr) return { cols: fr.row.cols, inner: false, rowId: fr.row.id };
  return null;
}

/* ============================================================
   حالت مسلح (کلیک برای افزودن — سازگار با موبایل)
   ============================================================ */
function arm(type) {
  armedType = type;
  document.querySelectorAll('.pb-palette-item').forEach(function (it) { it.classList.toggle('armed', it.dataset.type === type); });
  applyArmedFrame();
  toast('حالا روی یک ستون در بوم کلیک کنید تا «' + (WIDGETS[type] ? WIDGETS[type].name : type) + '» اضافه شود — Esc برای لغو');
}
function disarm() {
  armedType = null;
  document.querySelectorAll('.pb-palette-item').forEach(function (it) { it.classList.remove('armed'); });
  applyArmedFrame();
}
function applyArmedFrame() {
  var d = doc();
  if (d && d.body) d.body.classList.toggle('pb-armed', !!armedType);
}
function insertWidgetInCol(colEl) {
  var tgt = targetContainerFor(colEl);
  if (!tgt) return;
  var ci = parseInt(colEl.dataset.col, 10);
  if (!tgt.cols[ci]) return;
  tgt.cols[ci].push({ id: uid(), type: armedType, data: defaults(armedType) });
  pushHistory();
  immediateRender();
  toast('«' + (WIDGETS[armedType] ? WIDGETS[armedType].name : armedType) + '» اضافه شد ✅ — می‌توانید دوباره کلیک کنید', 'ok');
}

/* ============================================================
   افزودن سکشن (نوار بین ردیف‌ها + مدال)
   ============================================================ */
function openAddSection(barEl) {
  var fr = iframeEl.getBoundingClientRect();
  var r = barEl.getBoundingClientRect();
  var pos = parseInt(barEl.dataset.pos, 10) || 0;
  showAddSectionModal(pos);
}
function closeModal(id) {
  var m = document.getElementById(id);
  if (m) m.remove();
}
function showAddSectionModal(pos) {
  var old = document.getElementById('pb-modal-add');
  if (old) old.remove();
  var m = document.createElement('div');
  m.id = 'pb-modal-add';
  m.className = 'pb-modal-overlay';
  var tplHtml = '';
  Object.keys(SECTION_TPLS).forEach(function (k) {
    var t = SECTION_TPLS[k];
    tplHtml += '<div class="pb-section-tpl" data-tpl="' + k + '"><span class="t-ic">' + (t.icon || '▤') + '</span><span class="t-name">' + esc(t.name || k) + '</span><span class="t-desc">' + esc(t.desc || '') + '</span></div>';
  });
  var colsHtml = '';
  for (var n = 1; n <= 7; n++) {
    var cells = '';
    for (var j = 0; j < n; j++) cells += '<i></i>';
    colsHtml += '<div class="pb-add-cols" data-cols="' + n + '"><div class="pb-mini">' + cells + '</div><small>' + n + ' ستون</small></div>';
  }
  m.innerHTML = '<div class="pb-modal">'
    + '<div class="pb-modal-head"><span>➕ افزودن سکشن</span><button type="button" data-close>✕</button></div>'
    + '<div class="pb-modal-body">'
    + '<div class="pb-add-title">🧱 چیدمان ستون‌ها</div>'
    + '<div class="pb-add-grid">' + colsHtml + '</div>'
    + (tplHtml ? '<div class="pb-add-title">⭐ سکشن‌های آماده</div><div class="pb-section-grid">' + tplHtml + '</div>' : '')
    + '</div></div>';
  document.body.appendChild(m);
  m.addEventListener('click', function (e) {
    if (e.target === m || e.target.closest('[data-close]')) { m.remove(); return; }
    var cc = e.target.closest('.pb-add-cols');
    if (cc) {
      var nid = addRow(parseInt(cc.dataset.cols, 10), pos);
      m.remove();
      toast('سکشن ' + cc.dataset.cols + ' ستونه اضافه شد ✅', 'ok');
      immediateRender();
      scrollToElInFrame('[data-row="' + nid + '"]');
      selectRow(nid);
      return;
    }
    var st = e.target.closest('.pb-section-tpl');
    if (st) {
      var tpl = SECTION_TPLS[st.dataset.tpl];
      if (tpl && tpl.rows) {
        var copy = JSON.parse(JSON.stringify(tpl.rows));
        copy.forEach(function (row) {
          row.id = uid('r');
          row.cols.forEach(function (col) { col.forEach(function (w) { w.id = uid(); }); });
        });
        data.rows.splice.apply(data.rows, [Math.max(0, Math.min(pos, data.rows.length)), 0].concat(copy));
        pushHistory();
        m.remove();
        toast('سکشن «' + (tpl.name || '') + '» اضافه شد ✅', 'ok');
        immediateRender();
        scrollToElInFrame('[data-row="' + copy[0].id + '"]');
      }
    }
  });
}

/* ============================================================
   پنل راست — تب‌ها و کنترل‌ها
   ============================================================ */
function setPanelTab(tab) {
  panelTab = tab;
  document.querySelectorAll('.pb-tab').forEach(function (b) { b.classList.toggle('active', b.dataset.tab === tab); });
  if (sel && sel.type === 'widget') { var f = findWidget(sel.id); if (f) buildWidgetPanel(f); }
  else if (sel && sel.type === 'row') { var fr = findRow(sel.id); if (fr) buildRowPanel(fr); }
  else showPagePanel();
}
function groupHead(title, count, open) {
  return '<div class="pb-panel-group ' + (open ? 'open' : '') + '">'
    + '<button type="button" class="pb-panel-group-head" data-toggle-group><span class="pb-g-arrow">◀</span>'
    + '<span>' + esc(title) + '</span>' + (count !== null && count !== undefined ? '<span class="pb-g-count">' + count + '</span>' : '')
    + '</button><div class="pb-panel-group-body">';
}

/* --- کنترل‌های فرم --- */
function fieldHtml(f, v, repKey, repIdx) {
  var val = v === undefined || v === null ? '' : v;
  var drep = repKey !== undefined ? ' data-repkey="' + repKey + '" data-repidx="' + repIdx + '"' : '';
  var html = '<div class="pb-control">';
  if (f.type === 'checkbox') {
    /* چک‌باکس: کل کنترل یک لیبل است */
    html = '<div class="pb-control" style="margin-bottom:9px"><label class="pb-check"><input type="checkbox" data-field="' + f.key + '"' + drep + ' ' + (val ? 'checked' : '') + '><span class="pb-checkbox">✓</span> ' + esc(f.label) + '</label></div>';
    return html;
  }
  html += '<label>' + esc(f.label) + '</label>';
  if (f.type === 'text') {
    html += '<input type="text" data-field="' + f.key + '"' + drep + ' value="' + esc(val) + '">';
  } else if (f.type === 'textarea') {
    html += '<textarea data-field="' + f.key + '"' + drep + '>' + esc(val) + '</textarea>';
  } else if (f.type === 'number') {
    html += '<input type="number" data-field="' + f.key + '"' + drep + ' value="' + esc(val) + '">';
  } else if (f.type === 'select') {
    html += '<select data-field="' + f.key + '"' + drep + '>';
    (f.options || []).forEach(function (o) {
      var ov = Array.isArray(o) ? o[0] : o;
      var ol = Array.isArray(o) ? o[1] : o;
      html += '<option value="' + esc(ov) + '" ' + (String(val) === String(ov) ? 'selected' : '') + '>' + esc(ol) + '</option>';
    });
    html += '</select>';
  } else if (f.type === 'color') {
    html += '<div class="pb-color-row"><input type="color" data-field="' + f.key + '"' + drep + ' value="' + (val || '#0f172a') + '">'
      + '<input type="text" data-field="' + f.key + '"' + drep + ' value="' + esc(val || '') + '" placeholder="#0f172a"></div>';
  } else if (f.type === 'category') {
    html += '<select data-field="' + f.key + '"' + drep + '><option value="">همه دسته‌ها</option>';
    CAT_OPTS.forEach(function (o) { html += '<option value="' + o[0] + '" ' + (String(val) === String(o[0]) ? 'selected' : '') + '>' + esc(o[1]) + '</option>'; });
    html += '</select>';
  } else if (f.type === 'course') {
    html += '<select data-field="' + f.key + '"' + drep + '><option value="">— انتخاب دوره —</option>';
    COURSE_OPTS.forEach(function (o) { html += '<option value="' + o[0] + '" ' + (String(val) === String(o[0]) ? 'selected' : '') + '>' + esc(o[1]) + '</option>'; });
    html += '</select>';
  } else if (f.type === 'image') {
    html += imageControlHtml(f.key, val, drep);
  } else if (f.type === 'richtext') {
    html += '<div class="pb-richtext">'
      + '<div class="pb-rt-toolbar" style="display:flex;gap:3px;margin-bottom:6px;flex-wrap:wrap">'
      + '<button type="button" data-rt="bold" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px;font-weight:900">B</button>'
      + '<button type="button" data-rt="italic" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px;font-style:italic">I</button>'
      + '<button type="button" data-rt="underline" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px;text-decoration:underline">U</button>'
      + '<button type="button" data-rt="insertUnorderedList" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px">•≡</button>'
      + '<button type="button" data-rt="insertOrderedList" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px">1≡</button>'
      + '<button type="button" data-rt="createLink" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px">🔗</button>'
      + '<button type="button" data-rt="removeFormat" style="flex:1;min-width:30px;padding:5px;border:1px solid var(--pb-border);border-radius:7px">∅</button>'
      + '</div>'
      + '<div class="pb-rt-area" contenteditable="true" data-field="' + f.key + '"' + drep + '>' + val + '</div></div>';
  }
  html += '</div>';
  return html;
}
function imageControlHtml(key, val, drep) {
  var src = '';
  if (val) src = (String(val).indexOf('/') === 0 ? val : (String(val).indexOf('/') >= 0 ? '/static/' + val : '/static/img/' + val));
  return '<div class="pb-img-picker">'
    + '<div class="pb-img-preview" data-img-preview>' + (src ? '<img src="' + esc(src) + '" alt="">' : '<span style="font-size:11px;color:#8b95a3">بدون تصویر</span>') + '</div>'
    + '<div class="pb-img-actions">'
    + '<button type="button" data-img-pick="' + key + '"' + drep + '>📁 کتابخانه</button>'
    + '<button type="button" data-img-upload="' + key + '"' + drep + '>⬆ آپلود</button>'
    + (val ? '<button type="button" class="pb-del-img" data-img-clear="' + key + '"' + drep + '>✕</button>' : '')
    + '</div></div>'
    + '<input type="hidden" data-field="' + key + '"' + drep + ' value="' + esc(val || '') + '">';
}

/* --- ریپیتر (اسلایدها و ...) --- */
function repeaterHtml(f, fl, items) {
  var html = '<div class="pb-repeater" data-repeater="' + fl.key + '">';
  items.forEach(function (it, idx) {
    var thumb = '', title = 'مورد ' + (idx + 1);
    (fl.item_fields || []).forEach(function (sf) {
      if (sf.type === 'image' && it[sf.key]) {
        var v = String(it[sf.key]);
        thumb = '<img src="' + esc(v.indexOf('/') === 0 ? v : (v.indexOf('/') >= 0 ? '/static/' + v : '/static/img/' + v)) + '" alt="">';
      }
      if (sf.type === 'text' && it[sf.key] && title === 'مورد ' + (idx + 1)) title = String(it[sf.key]).slice(0, 26);
    });
    html += '<div class="pb-rep-card' + (idx === 0 || idx === items.length - 1 ? ' open' : '') + '" data-idx="' + idx + '">'
      + '<div class="pb-rep-head">'
      + '<span class="pb-rep-handle" title="جابه‌جایی">⠿</span>'
      + '<span class="pb-rep-thumb">' + (thumb || '🖼') + '</span>'
      + '<span class="pb-rep-title">' + esc(title) + '</span>'
      + '<span class="pb-rep-btns">'
      + '<button type="button" data-rep-up title="بالا">↑</button>'
      + '<button type="button" data-rep-down title="پایین">↓</button>'
      + '<button type="button" data-rep-copy title="کپی">⧉</button>'
      + '<button type="button" class="pb-rep-del" data-rep-del title="حذف">🗑</button>'
      + '</span></div>'
      + '<div class="pb-rep-body">';
    (fl.item_fields || []).forEach(function (sf) {
      html += fieldHtml(sf, it[sf.key], fl.key, idx);
    });
    html += '</div></div>';
  });
  html += '</div>';
  return html;
}

/* --- تب محتوا --- */
function buildWidgetPanel(f) {
  var w = WIDGETS[f.w.type];
  if (!w) { showPagePanel(); return; }
  var html = '<div class="pb-tabs">'
    + '<button class="pb-tab active" data-tab="content">محتوا</button>'
    + '<button class="pb-tab" data-tab="style">استایل</button>'
    + '<button class="pb-tab" data-tab="advanced">پیشرفته</button></div>';
  if (panelTab === 'style') { html += buildWidgetStyle(f); }
  else if (panelTab === 'advanced') { html += buildWidgetAdvanced(f); }
  else { html += buildWidgetContent(f); }
  panelBody.innerHTML = html;
  bindTabs();
  bindPanelEvents(f);
}
function buildWidgetContent(f) {
  var w = WIDGETS[f.w.type];
  var html = '';
  var general = '', repGroups = '';
  var repOpen = true;
  (w.fields || []).forEach(function (fl) {
    if (fl.type === 'repeater') {
      var items = f.w.data[fl.key] || [];
      repGroups += groupHead(fl.label, items.length, repOpen && items.length > 0)
        + repeaterHtml(f, fl, items)
        + '<button type="button" class="pb-rep-add" data-rep-add="' + fl.key + '"><span class="pb-plus">+</span> افزودن ' + fl.label.replace(/ها$/, '') + '</button>'
        + '</div></div>';
      repOpen = false;
    } else {
      general += fieldHtml(fl, f.w.data[fl.key]);
    }
  });
  if (general) html += groupHead('عمومی', null, true) + general + '</div></div>';
  html += repGroups;
  return html;
}

/* --- تب استایل (کنترل‌های عمومی ویجت) --- */
function buildWidgetStyle(f) {
  /* اگر d.style رشته باشد (داده قدیمی ویجت‌هایی مثل دکمه) به آبجکت تبدیل کن */
  if (!f.w.data.style || typeof f.w.data.style !== 'object') f.w.data.style = {};
  var s = f.w.data.style;
  var alignSel = '<select data-style="align"><option value="" ' + (!s.align ? 'selected' : '') + '>پیش‌فرض</option>'
    + '<option value="right" ' + (s.align === 'right' ? 'selected' : '') + '>راست</option>'
    + '<option value="center" ' + (s.align === 'center' ? 'selected' : '') + '>وسط</option>'
    + '<option value="left" ' + (s.align === 'left' ? 'selected' : '') + '>چپ</option></select>';
  var widthSel = '<select data-style="width"><option value="" ' + (!s.width ? 'selected' : '') + '>تمام عرض</option>'
    + '<option value="50%" ' + (s.width === '50%' ? 'selected' : '') + '>۵۰٪</option>'
    + '<option value="60%" ' + (s.width === '60%' ? 'selected' : '') + '>۶۰٪</option>'
    + '<option value="75%" ' + (s.width === '75%' ? 'selected' : '') + '>۷۵٪</option>'
    + '<option value="400px" ' + (s.width === '400px' ? 'selected' : '') + '>۴۰۰ پیکسل</option>'
    + '<option value="600px" ' + (s.width === '600px' ? 'selected' : '') + '>۶۰۰ پیکسل</option></select>';
  function num4(prefix, label) {
    var v = function (k) { return s[k] || ''; };
    return '<div class="pb-control"><label>' + label + '</label><div class="pb-4in">'
      + ['t', 'r', 'b', 'l'].map(function (k, i) {
        return '<div class="pb-4in-item"><input type="number" data-style="' + prefix + k + '" value="' + esc(v(prefix + k)) + '" placeholder="0"><small>' + ['بالا', 'راست', 'پایین', 'چپ'][i] + '</small></div>';
      }).join('') + '</div></div>';
  }
  return '<div class="pb-tabs-inner">'
    + groupHead('چیدمان', null, true)
    + '<div class="pb-control"><label>تراز محتوا</label>' + alignSel + '</div>'
    + '<div class="pb-control"><label>عرض</label>' + widthSel + '</div>'
    + '</div></div>'
    + groupHead('رنگ‌ها', null, true)
    + '<div class="pb-control"><label>رنگ متن</label><div class="pb-color-row"><input type="color" data-style="color" value="' + (s.color || '#0f172a') + '"><input type="text" data-style="color" value="' + esc(s.color || '') + '" placeholder="#0f172a"></div></div>'
    + '<div class="pb-control"><label>رنگ پس‌زمینه</label><div class="pb-color-row"><input type="color" data-style="bg" value="' + (s.bg || '#ffffff') + '"><input type="text" data-style="bg" value="' + esc(s.bg || '') + '" placeholder="—"></div></div>'
    + '</div></div>'
    + groupHead('فاصله‌گذاری', null, true)
    + '<div class="pb-control"><label>گردی گوشه (px)</label><input type="number" data-style="radius" value="' + esc(s.radius || '') + '" placeholder="0"></div>'
    + num4('m', 'حاشیه بیرونی (Margin — px)')
    + num4('p', 'حاشیه داخلی (Padding — px)')
    + '</div></div>';
}

/* --- تب پیشرفته --- */
function buildWidgetAdvanced(f) {
  var d = f.w.data;
  var anims = [['', 'بدون انیمیشن'], ['fade-up', 'محو از پایین'], ['fade-in', 'محو تدریجی'], ['zoom', 'بزرگ‌شونده'], ['slide-right', 'اسلاید از راست']];
  var animSel = '<select data-field="anim">' + anims.map(function (a) {
    return '<option value="' + a[0] + '" ' + ((d.anim || '') === a[0] ? 'selected' : '') + '>' + a[1] + '</option>';
  }).join('') + '</select>';
  var html = '<div class="pb-tabs-inner">'
    + groupHead('نمایش در دستگاه‌ها', null, true)
    + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-field="hide_mobile" ' + (d.hide_mobile ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی کردن در موبایل</label></div>'
    + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-field="hide_desktop" ' + (d.hide_desktop ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی کردن در دسکتاپ</label></div>'
    + '</div></div>'
    + groupHead('افکت‌ها و شناسه‌ها', null, true)
    + '<div class="pb-control"><label>انیمیشن ورود</label>' + animSel + '</div>'
    + '<div class="pb-control"><label>کلاس CSS سفارشی</label><input type="text" data-field="css_class" value="' + esc(d.css_class || '') + '" placeholder="my-class"></div>'
    + '<div class="pb-control"><label>آیدی (ID)</label><input type="text" data-field="css_id" value="' + esc(d.css_id || '') + '" placeholder="my-section"></div>'
    + '</div></div>'
    + groupHead('عملیات', null, true)
    + '<button type="button" class="pb-panel-btn" data-wid-copy-panel>⧉ کپی ویجت</button>'
    + '<button type="button" class="pb-panel-btn danger" data-wid-del-panel>🗑 حذف ویجت</button>'
    + '</div></div>';
  return html;
}

/* --- پنل ردیف --- */
function buildRowPanel(f) {
  if (!f) { showPagePanel(); return; }
  var rs = f.row.settings = f.row.settings || {};
  var html = '<div class="pb-tabs">'
    + '<button class="pb-tab active" data-tab="content">محتوا</button>'
    + '<button class="pb-tab" data-tab="style">استایل</button>'
    + '<button class="pb-tab" data-tab="advanced">پیشرفته</button></div>';
  if (panelTab === 'style') {
    html += '<div class="pb-tabs-inner">'
      + groupHead('پس‌زمینه', null, true)
      + '<div class="pb-control"><label>رنگ پس‌زمینه</label><div class="pb-color-row"><input type="color" data-rs="bg" value="' + (rs.bg || '#ffffff') + '"><input type="text" data-rs="bg" value="' + esc(rs.bg || '') + '" placeholder="—"></div></div>'
      + '<div class="pb-control"><label>تصویر پس‌زمینه</label>' + imageControlHtml('bg_image', rs.bg_image || '', '') + '</div>'
      + '</div></div>'
      + groupHead('فاصله‌گذاری', null, true)
      + '<div class="pb-control"><label>گردی گوشه (px)</label><input type="number" data-rs="radius" value="' + esc(rs.radius || '') + '"></div>'
      + '<div class="pb-control"><label>پدینگ بالا/پایین (py — px)</label><input type="number" data-rs="py" value="' + esc(rs.py || '') + '"></div>'
      + '<div class="pb-control"><label>حاشیه بیرونی بالا/پایین (px)</label><div class="pb-4in">'
      + '<div class="pb-4in-item"><input type="number" data-rs="mt" value="' + esc(rs.mt || '') + '"><small>بالا</small></div>'
      + '<div class="pb-4in-item"><input type="number" data-rs="mb" value="' + esc(rs.mb || '') + '"><small>پایین</small></div>'
      + '<div class="pb-4in-item"><input type="number" data-rs="pt" value="' + esc(rs.pt || '') + '"><small>پد بالا</small></div>'
      + '<div class="pb-4in-item"><input type="number" data-rs="pb" value="' + esc(rs.pb || '') + '"><small>پد پایین</small></div>'
      + '</div></div></div></div>';
  } else if (panelTab === 'advanced') {
    html += '<div class="pb-tabs-inner">'
      + groupHead('نمایش در دستگاه‌ها', null, true)
      + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-rs="hide_mobile" ' + (rs.hide_mobile ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی کردن در موبایل</label></div>'
      + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-rs="hide_desktop" ' + (rs.hide_desktop ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی کردن در دسکتاپ</label></div>'
      + '</div></div>'
      + groupHead('شناسه‌ها', null, true)
      + '<div class="pb-control"><label>کلاس CSS سفارشی</label><input type="text" data-rs="css_class" value="' + esc(rs.css_class || '') + '" placeholder="my-row"></div>'
      + '<div class="pb-control"><label>آیدی (ID)</label><input type="text" data-rs="css_id" value="' + esc(rs.css_id || '') + '" placeholder="section-1"></div>'
      + '</div></div>'
      + groupHead('عملیات', null, true)
      + '<button type="button" class="pb-panel-btn" data-row-save-panel>⭐ ذخیره به کتابخانه سکشن‌ها</button>'
      + '<button type="button" class="pb-panel-btn" data-row-copy-panel>⧉ کپی سکشن</button>'
      + '<button type="button" class="pb-panel-btn danger" data-row-del-panel>🗑 حذف سکشن</button>'
      + '</div></div>';
  } else {
    var colsBtns = '';
    for (var n = 1; n <= 7; n++) {
      var active = f.row.cols.length === n ? ' sel' : '';
      var cells = '';
      for (var j = 0; j < n; j++) cells += '<i></i>';
      colsBtns += '<button type="button" class="pb-row-tpl' + active + '" data-setcols="' + n + '">' + cells + '</button>';
    }
    html += '<div class="pb-tabs-inner">'
      + groupHead('ساختار ستون‌ها', null, true)
      + '<div class="pb-control"><label>تعداد ستون‌ها (۱ تا ۷)</label><div class="pb-row-templates">' + colsBtns + '</div></div>'
      + '<div class="pb-control"><label>عرض ستون‌ها (مثلا: 2fr 1fr 1fr)</label><input type="text" data-rs="widths" value="' + esc(rs.widths || '') + '" placeholder="خالی = مساوی"></div>'
      + '<div class="pb-control"><label>فاصله بین ستون‌ها (gap — px)</label><input type="number" data-rs="gap" value="' + esc(rs.gap || '') + '"></div>'
      + '</div></div>';
  }
  panelBody.innerHTML = html;
  bindTabs();
  bindRowPanelEvents(f);
}

/* --- پنل صفحه --- */
function showPagePanel() {
  sel = null;
  panelTitle.textContent = 'تنظیمات صفحه';
  panelIc.textContent = '⚙️';
  panelSub.textContent = 'صفحه';
  var ss = data.settings = data.settings || {};
  var total = 0;
  data.rows.forEach(function (r) { (r.cols || []).forEach(function (c) { total += c.length; }); });
  var html = '<div class="pb-tabs">'
    + '<button class="pb-tab active" data-tab="content">محتوا</button>'
    + '<button class="pb-tab" data-tab="style">استایل</button>'
    + '<button class="pb-tab" data-tab="advanced">پیشرفته</button></div>';
  if (panelTab === 'style') {
    html += '<div class="pb-tabs-inner">' + groupHead('پس‌زمینه صفحه', null, true)
      + '<div class="pb-control"><label>رنگ پس‌زمینه</label><div class="pb-color-row"><input type="color" data-page="page_bg" value="' + (ss.page_bg || '#ffffff') + '"><input type="text" data-page="page_bg" value="' + esc(ss.page_bg || '') + '" placeholder="—"></div></div>'
      + '</div></div></div>';
  } else if (panelTab === 'advanced') {
    html += '<div class="pb-tabs-inner">'
      + groupHead('سئو', null, true)
      + '<div class="pb-control"><label>عنوان سئو (meta title)</label><input type="text" data-page="seo_title" value="' + esc(ss.seo_title || '') + '"></div>'
      + '<div class="pb-control"><label>توضیحات سئو (meta description)</label><textarea data-page="seo_desc">' + esc(ss.seo_desc || '') + '</textarea></div>'
      + '</div></div>'
      + groupHead('قالب صفحه', null, true)
      + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-page="hide_header" ' + (ss.hide_header ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی‌کردن هدر سایت</label></div>'
      + '<div class="pb-control"><label class="pb-check"><input type="checkbox" data-page="hide_footer" ' + (ss.hide_footer ? 'checked' : '') + '><span class="pb-checkbox">✓</span> مخفی‌کردن فوتر سایت</label></div>'
      + '<button type="button" class="pb-panel-btn" data-save-page-tpl>📦 ذخیره این صفحه به عنوان قالب</button>'
      + '</div></div>';
  } else {
    html += '<div class="pb-tabs-inner">'
      + groupHead('آمار صفحه', null, true)
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
      + '<div class="pb-stat-mini">' + data.rows.length + '<small>سکشن</small></div>'
      + '<div class="pb-stat-mini">' + total + '<small>ویجت</small></div>'
      + '</div></div></div>'
      + groupHead('افزودن سکشن', null, true)
      + '<div class="pb-control"><label>چیدمان سریع</label><div class="pb-row-templates">'
      + '<button type="button" class="pb-row-tpl" data-qrow="1"><i></i></button>'
      + '<button type="button" class="pb-row-tpl" data-qrow="2"><i></i><i></i></button>'
      + '<button type="button" class="pb-row-tpl" data-qrow="3"><i></i><i></i><i></i></button>'
      + '</div></div>'
      + '<button type="button" class="pb-panel-btn" data-open-add>➕ افزودن سکشن (انتخاب از قالب‌ها)</button>'
      + '</div></div>';
  }
  panelBody.innerHTML = html;
  bindTabs();
  bindPagePanelEvents();
}

function bindTabs() {
  panelBody.querySelectorAll('.pb-tab').forEach(function (b) {
    b.addEventListener('click', function () { setPanelTab(b.dataset.tab); });
  });
  panelBody.querySelectorAll('[data-toggle-group]').forEach(function (g) {
    g.addEventListener('click', function () { g.closest('.pb-panel-group').classList.toggle('open'); });
  });
}

/* --- اتصال رویدادهای پنل ویجت --- */
function setFieldValue(f, input, key, repKey, repIdx) {
  var val = input.type === 'checkbox' ? input.checked : input.value;
  if (repKey !== undefined) {
    var items = f.w.data[repKey] || [];
    if (!items[repIdx]) items[repIdx] = {};
    items[repIdx][key] = val;
  } else {
    f.w.data[key] = val;
  }
}
function bindFieldInput(input, f) {
  var key = input.dataset.field;
  var repKey = input.dataset.repkey;
  var repIdx = input.dataset.repidx !== undefined ? parseInt(input.dataset.repidx, 10) : undefined;
  var evt = (input.tagName === 'SELECT' || input.type === 'checkbox' || input.type === 'color') ? 'change' : 'input';
  input.addEventListener(evt, function () {
    setFieldValue(f, input, key, repKey, repIdx);
    if (input.type === 'color' && input.tagName === 'INPUT') {
      /* همگام‌سازی جفت color/text */
      var row = input.closest('.pb-color-row');
      if (row) row.querySelectorAll('input[type=text]').forEach(function (tx) { if (tx !== input) tx.value = input.value; });
    }
    scheduleRender();
  });
}
function bindWidgetImgButtons(f, scope) {
  scope.querySelectorAll('[data-img-pick],[data-img-upload],[data-img-clear]').forEach(function (btn) {
    if (btn._bound) return;
    btn._bound = 1;
    btn.addEventListener('click', function () {
      var key = btn.dataset.imgPick || btn.dataset.imgUpload || btn.dataset.imgClear;
      var repKey = btn.dataset.repkey;
      var repIdx = btn.dataset.repidx !== undefined ? parseInt(btn.dataset.repidx, 10) : undefined;
      var picker = btn.closest('.pb-img-picker');
      var apply = function (val) {
        setFieldValue(f, { type: 'text', value: val }, key, repKey, repIdx);
        renderImgControl(picker, val, function () { setFieldValue(f, { type: 'text', value: '' }, key, repKey, repIdx); scheduleRender(); });
        scheduleRender();
      };
      if (btn.hasAttribute('data-img-clear')) apply('');
      else if (btn.hasAttribute('data-img-upload')) uploadImage(apply);
      else openMediaPicker(apply);
    });
  });
}
function bindPanelEvents(f) {
  panelBody.querySelectorAll('[data-field]').forEach(function (input) {
    if (input.closest('.pb-repeater')) return; /* داخل ریپیتر در bindRepeaterEvents بسته می‌شود */
    bindFieldInput(input, f);
  });
  /* تب استایل */
  panelBody.querySelectorAll('[data-style]').forEach(function (input) {
    var key = input.dataset.style;
    var evt = (input.tagName === 'SELECT' || input.type === 'color') ? 'change' : 'input';
    input.addEventListener(evt, function () {
      var s = f.w.data.style = f.w.data.style || {};
      s[key] = input.value;
      if (input.type === 'color' && input.tagName === 'INPUT') {
        var row = input.closest('.pb-color-row');
        if (row) row.querySelectorAll('input[type=text]').forEach(function (tx) { if (tx !== input) tx.value = input.value; });
      }
      scheduleRender();
    });
  });
    /* آپلود/انتخاب/پاک‌کردن تصویر (ویجت) */
  bindWidgetImgButtons(f, panelBody);
  bindRepeaterEvents(f);
  /* ریچ‌تکست */
  panelBody.querySelectorAll('.pb-rt-area').forEach(function (area) {
    var key = area.dataset.field;
    var repKey = area.dataset.repkey;
    var repIdx = area.dataset.repidx !== undefined ? parseInt(area.dataset.repidx, 10) : undefined;
    area.addEventListener('input', function () {
      setFieldValue(f, { type: 'text', value: area.innerHTML }, key, repKey, repIdx);
      scheduleRender();
    });
  });
  panelBody.querySelectorAll('[data-rt]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var area = btn.closest('.pb-richtext').querySelector('.pb-rt-area');
      area.focus();
      var cmd = btn.dataset.rt;
      if (cmd === 'createLink') {
        var url = prompt('آدرس لینک:');
        if (url) document.execCommand('createLink', false, url);
      } else { document.execCommand(cmd, false, null); }
      area.dispatchEvent(new Event('input'));
    });
  });
  /* عملیات */
  var cp = panelBody.querySelector('[data-wid-copy-panel]');
  if (cp) cp.addEventListener('click', function () { copyWidget(f); });
  var dp = panelBody.querySelector('[data-wid-del-panel]');
  if (dp) dp.addEventListener('click', function () { delWidget(f); });
  bindRepeaterEvents(f);
}

function renderImgControl(picker, val, onClear) {
  if (!picker) return;
  var src = val ? (String(val).indexOf('/') === 0 ? val : (String(val).indexOf('/') >= 0 ? '/static/' + val : '/static/img/' + val)) : '';
  var prev = picker.querySelector('[data-img-preview]');
  prev.innerHTML = src ? '<img src="' + esc(src) + '" alt="">' : '<span style="font-size:11px;color:#8b95a3">بدون تصویر</span>';
  var hid = picker.querySelector('input[type=hidden]');
  if (hid) hid.value = val || '';
  var clear = picker.querySelector('[data-img-clear]');
  if (val && !clear) {
    var actions = picker.querySelector('.pb-img-actions');
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'pb-del-img';
    b.textContent = '✕';
    b.addEventListener('click', function (e) { e.stopPropagation(); if (onClear) onClear(); });
    actions.appendChild(b);
  } else if (!val && clear) { clear.remove(); }
}

/* --- ریپیتر --- */
function bindRepeaterEvents(f) {
  var rep = panelBody.querySelectorAll('.pb-repeater');
  rep.forEach(function (box) {
    if (box.dataset.bound) return; /* جلوگیری از اتصال تکراری رویدادها */
    box.dataset.bound = '1';
    var key = box.dataset.repeater;
    var w = WIDGETS[f.w.type];
    var fl = (w.fields || []).find(function (x) { return x.key === key; });
    if (!fl) return;
    /* افزودن (دکمه بیرون از باکس است؛ با مارکر از اتصال تکراری جلوگیری می‌شود) */
    var addBtn = panelBody.querySelector('[data-rep-add="' + key + '"]');
    if (addBtn && !addBtn.dataset.bound) {
      addBtn.dataset.bound = '1';
      addBtn.addEventListener('click', function () {
      if (!f.w.data[key]) f.w.data[key] = [];
      var empty = {};
      (fl.item_fields || []).forEach(function (sf) { empty[sf.key] = sf.type === 'checkbox' ? false : ''; });
      f.w.data[key].push(empty);
      pushHistory();
        rebuildRepeater(f, key);
        scheduleRender();
        toast('مورد جدید اضافه شد ✅', 'ok');
      });
    }
    /* باز و بسته کردن کارت */
    box.querySelectorAll('.pb-rep-head').forEach(function (head) {
      head.addEventListener('click', function (e) {
        if (e.target.closest('.pb-rep-btns') || e.target.closest('.pb-rep-handle')) return;
        head.closest('.pb-rep-card').classList.toggle('open');
      });
    });
    /* دکمه‌های کارت */
    box.querySelectorAll('[data-rep-up],[data-rep-down],[data-rep-copy],[data-rep-del]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var card = b.closest('.pb-rep-card');
        var idx = parseInt(card.dataset.idx, 10);
        var items = f.w.data[key] || [];
        if (b.hasAttribute('data-rep-up') && idx > 0) {
          var it = items.splice(idx, 1)[0]; items.splice(idx - 1, 0, it);
        } else if (b.hasAttribute('data-rep-down') && idx < items.length - 1) {
          var it2 = items.splice(idx, 1)[0]; items.splice(idx + 1, 0, it2);
        } else if (b.hasAttribute('data-rep-copy')) {
          var it3 = JSON.parse(JSON.stringify(items[idx]));
          items.splice(idx + 1, 0, it3);
        } else if (b.hasAttribute('data-rep-del')) {
          items.splice(idx, 1);
        }
        pushHistory();
        rebuildRepeater(f, key);
        scheduleRender();
      });
    });
    /* فیلدها و دکمه‌های تصویر داخل هر کارت */
    box.querySelectorAll('[data-field]').forEach(function (input) { bindFieldInput(input, f); });
    bindWidgetImgButtons(f, box);
    /* درگ کارت‌ها برای جابه‌جایی */
    box.querySelectorAll('.pb-rep-handle').forEach(function (handle) {
      handle.addEventListener('pointerdown', function (e) {
        e.preventDefault(); e.stopPropagation();
        var card = handle.closest('.pb-rep-card');
        var items = f.w.data[key] || [];
        var startY = e.clientY;
        var idx0 = parseInt(card.dataset.idx, 10);
        var moved = false;
        function onMove(ev) {
          if (Math.abs(ev.clientY - startY) < 12) return;
          moved = true;
          var cards = box.querySelectorAll('.pb-rep-card');
          var over = null;
          cards.forEach(function (c) {
            var r = c.getBoundingClientRect();
            if (ev.clientY > r.top && ev.clientY < r.bottom) over = c;
          });
          if (over && over !== card) {
            var overIdx = parseInt(over.dataset.idx, 10);
            var it = items.splice(idx0, 1)[0];
            items.splice(overIdx, 0, it);
            rebuildRepeater(f, key);
            /* بعد از بازسازی، ارجاع جدید بگیر */
            setTimeout(function () {
              var newHandles = box.querySelectorAll('.pb-rep-handle');
              newHandles.forEach(function (h) { h.style.opacity = '1'; });
            }, 0);
          }
        }
        function onUp() {
          document.removeEventListener('pointermove', onMove);
          document.removeEventListener('pointerup', onUp);
          if (moved) { pushHistory(); scheduleRender(); }
        }
        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp);
      });
    });
  });
}
function rebuildRepeater(f, key) {
  var w = WIDGETS[f.w.type];
  var fl = (w.fields || []).find(function (x) { return x.key === key; });
  if (!fl) return;
  var box = panelBody.querySelector('.pb-repeater[data-repeater="' + key + '"]');
  if (!box) return;
  var items = f.w.data[key] || [];
  box.outerHTML = repeaterHtml(f, fl, items);
  bindRepeaterEvents(f);
}

/* --- رویدادهای پنل ردیف --- */
function bindRowPanelEvents(f) {
  panelBody.querySelectorAll('[data-rs]').forEach(function (input) {
    var key = input.dataset.rs;
    var evt = (input.tagName === 'SELECT' || input.type === 'checkbox' || input.type === 'color') ? 'change' : 'input';
    input.addEventListener(evt, function () {
      f.row.settings[key] = input.type === 'checkbox' ? input.checked : input.value;
      scheduleRender();
    });
  });
  panelBody.querySelectorAll('[data-img-pick],[data-img-upload],[data-img-clear]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var picker = btn.closest('.pb-img-picker');
      var clearFn = function () { f.row.settings.bg_image = ''; scheduleRender(); };
      if (btn.hasAttribute('data-img-clear')) {
        f.row.settings.bg_image = '';
        renderImgControl(picker, '', clearFn);
        scheduleRender();
        return;
      }
      if (btn.hasAttribute('data-img-upload')) {
        uploadImage(function (rel) {
          f.row.settings.bg_image = rel;
          renderImgControl(picker, rel, clearFn);
          scheduleRender();
        });
        return;
      }
      openMediaPicker(function (rel) {
        f.row.settings.bg_image = rel;
        renderImgControl(picker, rel, clearFn);
        scheduleRender();
      });
    });
  });
  panelBody.querySelectorAll('[data-setcols]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var n = parseInt(btn.dataset.setcols, 10);
      var cur = f.row.cols;
      if (n > cur.length) {
        while (cur.length < n) cur.push([]);
      } else if (n < cur.length) {
        var keep = cur.slice(0, n);
        var rest = cur.slice(n);
        rest.forEach(function (c) { c.forEach(function (w) { keep[n - 1].push(w); }); });
        f.row.cols = keep;
      }
      pushHistory();
      buildRowPanel(f);
      scheduleRender();
      toast('ستون‌ها تغییر کرد: ' + n + ' ستون', 'ok');
    });
  });
  var sp = panelBody.querySelector('[data-row-save-panel]');
  if (sp) sp.addEventListener('click', function () { saveRowTemplate(f); });
  var cp = panelBody.querySelector('[data-row-copy-panel]');
  if (cp) cp.addEventListener('click', function () { copyRow(f); });
  var dp = panelBody.querySelector('[data-row-del-panel]');
  if (dp) dp.addEventListener('click', function () { delRow(f); });
}

/* --- رویدادهای پنل صفحه --- */
function bindPagePanelEvents() {
  panelBody.querySelectorAll('[data-page]').forEach(function (input) {
    var key = input.dataset.page;
    var evt = input.type === 'checkbox' ? 'change' : 'input';
    input.addEventListener(evt, function () {
      data.settings[key] = input.type === 'checkbox' ? input.checked : input.value;
      scheduleRender();
    });
  });
  panelBody.querySelectorAll('[data-qrow]').forEach(function (b) {
    b.addEventListener('click', function () {
      var n = parseInt(b.dataset.qrow, 10);
      var id = addRow(n);
      toast('سکشن ' + n + ' ستونه اضافه شد ✅', 'ok');
      immediateRender();
      scrollToElInFrame('[data-row="' + id + '"]');
      selectRow(id);
    });
  });
  var oa = panelBody.querySelector('[data-open-add]');
  if (oa) oa.addEventListener('click', function () { showAddSectionModal(data.rows.length); });
  var st = panelBody.querySelector('[data-save-page-tpl]');
  if (st) st.addEventListener('click', savePageTemplate);
}

/* ============================================================
   آپلود و کتابخانه رسانه
   ============================================================ */
function uploadImage(cb) {
  var inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/*';
  inp.onchange = function () {
    var fd = new FormData();
    fd.append('file', inp.files[0]);
    fetch('/builder/api/upload', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.ok) { toast('تصویر آپلود شد ✅', 'ok'); cb(res.file); }
        else { toast(res.msg || 'خطا در آپلود', 'err'); }
      })
      .catch(function () { toast('خطا در ارتباط', 'err'); });
  };
  inp.click();
}
function openMediaPicker(cb) {
  var old = document.getElementById('pb-media-modal');
  if (old) old.remove();
  var m = document.createElement('div');
  m.id = 'pb-media-modal';
  m.className = 'pb-modal-overlay';
  m.innerHTML = '<div class="pb-modal wide">'
    + '<div class="pb-modal-head"><span>📁 کتابخانه رسانه</span><button type="button" data-close>✕</button></div>'
    + '<div class="pb-modal-body">'
    + '<div class="pb-upload-drop">⬆ برای آپلود تصویر جدید کلیک کنید<input type="file" accept="image/*"></div>'
    + '<div class="pb-media-grid" data-grid>در حال بارگذاری...</div>'
    + '</div></div>';
  document.body.appendChild(m);
  m.addEventListener('click', function (e) {
    if (e.target === m || e.target.closest('[data-close]')) { m.remove(); }
  });
  var fileInput = m.querySelector('input[type=file]');
  fileInput.addEventListener('change', function () {
    var fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fetch('/api/media/upload', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.ok) {
          toast('آپلود شد ✅', 'ok');
          var rel = String(res.url || '').replace('/static/', '');
          cb(rel); m.remove();
        } else { toast(res.msg || 'خطا در آپلود', 'err'); }
      })
      .catch(function () { toast('خطا در ارتباط', 'err'); });
  });
  fetch('/api/media/list?kind=image')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var grid = m.querySelector('[data-grid]');
      if (!d.ok || !d.items || !d.items.length) {
        grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:#8b95a3;padding:20px;font-size:12.5px">کتابخانه خالی است — تصویر جدیدی آپلود کنید.</p>';
        return;
      }
      grid.innerHTML = '';
      d.items.forEach(function (it) {
        var cell = document.createElement('div');
        cell.className = 'pb-media-cell';
        cell.innerHTML = (it.kind === 'image' ? '<img src="' + esc(it.url) + '" alt="">' : '<div style="height:82px;display:flex;align-items:center;justify-content:center;font-size:22px">📄</div>')
          + '<div class="pb-media-name">' + esc(it.name) + '</div>';
        cell.addEventListener('click', function () {
          cb(String(it.url).replace('/static/', ''));
          m.remove();
        });
        grid.appendChild(cell);
      });
    })
    .catch(function () {
      var grid = m.querySelector('[data-grid]');
      if (grid) grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:#dc2626;padding:20px">خطا در دریافت کتابخانه</p>';
    });
}

/* ============================================================
   ناویگیتور
   ============================================================ */
function buildNavigator() {
  var nav = document.getElementById('pb-nav-body');
  if (!nav) return;
  nav.innerHTML = '';
  if (!data.rows.length) {
    nav.innerHTML = '<div class="pb-nav-empty">صفحه خالی است — از دکمه «➕ افزودن سکشن» شروع کنید</div>';
    return;
  }
  data.rows.forEach(function (row, i) {
    var item = document.createElement('div');
    item.className = 'pb-nav-item nav-row';
    item.innerHTML = '<span class="pb-nav-ic">▤</span><span class="pb-nav-label">سکشن ' + (i + 1) + (row.settings && row.settings.locked ? ' 🔒' : '') + '</span>';
    if (sel && sel.type === 'row' && sel.id === row.id) item.classList.add('active');
    item.addEventListener('click', function () {
      scrollToElInFrame('[data-row="' + row.id + '"]');
      selectRow(row.id);
    });
    nav.appendChild(item);
    row.cols.forEach(function (col, ci) {
      col.forEach(function (w) {
        var wi = document.createElement('div');
        wi.className = 'pb-nav-item nav-widget';
        var wname = WIDGETS[w.type] ? WIDGETS[w.type].name : w.type;
        var wicon = WIDGETS[w.type] ? (WIDGETS[w.type].icon || '🧩') : '🧩';
        wi.innerHTML = '<span class="pb-nav-ic">' + wicon + '</span><span class="pb-nav-label">' + esc(wname) + '</span>';
        wi.style.paddingRight = '26px';
        if (sel && sel.type === 'widget' && sel.id === w.id) wi.classList.add('active');
        wi.addEventListener('click', function () {
          scrollToElInFrame('[data-wid="' + w.id + '"]');
          selectWidget(w.id);
        });
        nav.appendChild(wi);
      });
    });
  });
}

/* ============================================================
   ذخیره
   ============================================================ */
function save() {
  if (saveBtn.disabled) return Promise.resolve();
  saveBtn.disabled = true;
  saveBtn.textContent = '…در حال ذخیره';
  return fetch('/builder/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      slug: window.PB_PAGE.slug,
      settings: data.settings,
      rows: data.rows,
      published: document.getElementById('pb-published').checked
    })
  }).then(function (r) { return r.json(); }).then(function (res) {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '💾 ذخیره';
    if (res.ok) {
      dirty = false; saveState.textContent = '✓ ذخیره شد';
      toast('صفحه با موفقیت ذخیره شد ✅', 'ok');
      updateStatus();
    } else {
      saveState.textContent = 'خطا!';
      toast(res.msg || 'خطا در ذخیره', 'err');
    }
  }).catch(function () {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '💾 ذخیره';
    saveState.textContent = 'خطا!';
    toast('خطا در ارتباط با سرور', 'err');
  });
}
function savePageTemplate() {
  var name = prompt('نام این قالب صفحه:', data.settings && data.settings.template_name ? data.settings.template_name : '');
  if (name === null) return;
  fetch('/builder/api/page-template', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name || '', rows: data.rows, settings: data.settings })
  }).then(function (r) { return r.json(); }).then(function (d) {
    if (d.ok) { toast('📦 صفحه به عنوان قالب ذخیره شد', 'ok'); }
    else { toast(d.msg || 'خطا', 'err'); }
  }).catch(function () { toast('خطا در ارتباط', 'err'); });
}

/* ============================================================
   دستگاه‌ها و پیش‌نمایش
   ============================================================ */
function setDevice(dev) {
  currentDev = dev;
  shell.className = 'pb-frame-shell dev-' + dev;
  document.querySelectorAll('[data-dev]').forEach(function (b) {
    var isPv = b.closest('.pb-preview-bar');
    b.classList.toggle('active', b.dataset.dev === dev);
    if (isPv) { /* preview bar separately */ }
  });
  document.querySelectorAll('.pb-pv-devices [data-dev]').forEach(function (b) {
    b.classList.toggle('active', b.dataset.dev === dev);
  });
  var lbl = document.getElementById('pb-device-label');
  if (lbl) lbl.textContent = dev === 'desktop' ? '🖥 دسکتاپ' : dev === 'tablet' ? '📱 تبلت' : '📲 موبایل';
}
function openPreview() {
  save().then(function () {
    var ov = document.getElementById('pb-preview-overlay');
    ov.classList.add('open');
    var f = document.getElementById('pb-preview-frame');
    var sep = PREVIEW_URL.indexOf('?') >= 0 ? '&' : '?';
    f.src = PREVIEW_URL + sep + 'preview=1&t=' + Date.now();
  }).catch(function () { });
}
function closePreview() {
  document.getElementById('pb-preview-overlay').classList.remove('open');
  document.getElementById('pb-preview-frame').src = 'about:blank';
}

/* ============================================================
   کتابخانه ویجت‌ها (پالت چپ)
   ============================================================ */
function buildPalette() {
  var scroll = document.getElementById('pb-palette-scroll');
  var html = '';
  /* قالب‌های سکشن */
  html += '<div class="pb-lib-title">🧱 سکشن جدید</div><div class="pb-row-templates">';
  for (var n = 1; n <= 7; n++) {
    var cells = '';
    for (var j = 0; j < n; j++) cells += '<i></i>';
    html += '<button type="button" class="pb-row-tpl" data-addrow="' + n + '" title="سکشن ' + n + ' ستونه">' + cells + '</button>';
  }
  html += '</div>';
  if (Object.keys(SECTION_TPLS).length) {
    html += '<div class="pb-lib-title">⭐ قالب‌های آماده</div><div class="pb-section-grid">';
    Object.keys(SECTION_TPLS).forEach(function (k) {
      var t = SECTION_TPLS[k];
      html += '<div class="pb-section-tpl" data-tpl="' + k + '"><span class="t-ic">' + (t.icon || '▤') + '</span><span class="t-name">' + esc(t.name || k) + '</span><span class="t-desc">' + esc((t.desc || '').slice(0, 40)) + '</span></div>';
    });
    html += '</div>';
  }
  /* طرح‌های آماده سایت (۲۰ طرح ایرانی) */
  var DESIGNS = window.PB_DESIGNS || [];
  if (DESIGNS.length) {
    html += '<div class="pb-lib-title">🖼 طرح‌های آماده سایت (۲۰ طرح)</div>';
    html += '<div class="pb-design-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 4px 10px">';
    DESIGNS.forEach(function (dg) {
      var grad = 'linear-gradient(135deg,' + (dg.colors[0] || '#ccc') + ' 0%,' + (dg.colors[1] || '#aaa') + ' 70%,' + (dg.colors[2] || '#eee') + ' 100%)';
      html += '<div class="pb-section-tpl pb-design-tpl" data-design="' + dg.id + '" title="' + esc(dg.name) + ' — جایگزینی چیدمان صفحه">'
        + '<span style="display:block;height:26px;border-radius:8px;background:' + grad + ';border:1px solid rgba(0,0,0,.08)"></span>'
        + '<span class="t-name">' + esc(dg.name) + (dg.dark ? ' 🌙' : '') + '</span>'
        + '<span class="t-desc">' + esc((dg.category || '').slice(0, 24)) + '</span></div>';
    });
    html += '</div>';
  }
  /* دسته‌بندی ویجت‌ها */
  window.PB_CATS.forEach(function (cat) {
    var cid = cat[0], cname = cat[1];
    var items = [];
    Object.keys(WIDGETS).forEach(function (k) {
      if (WIDGETS[k].cat === cid) items.push(k);
    });
    if (!items.length) return;
    html += '<div class="pb-palette-section open" data-cat="' + cid + '">'
      + '<button type="button" class="pb-palette-cat" data-toggle-cat><span class="pb-cat-arrow">◀</span> ' + cname
      + '<span class="pb-cat-count">' + items.length + '</span></button>'
      + '<div class="pb-palette-items">';
    items.forEach(function (k) {
      var w = WIDGETS[k];
      html += '<div class="pb-palette-item" draggable="false" data-type="' + k + '">'
        + '<span class="pb-pi-icon">' + (w.icon || '🧩') + '</span><span>' + esc(w.name) + '</span></div>';
    });
    html += '</div></div>';
  });
  scroll.innerHTML = html;
  bindPalette();
}
function bindPalette() {
  /* جستجو */
  var search = document.getElementById('pb-widget-search');
  search.addEventListener('input', function () {
    var q = search.value.trim();
    document.querySelectorAll('.pb-palette-section').forEach(function (sec) {
      var any = false;
      sec.querySelectorAll('.pb-palette-item').forEach(function (it) {
        var show = !q || it.textContent.indexOf(q) >= 0;
        it.style.display = show ? '' : 'none';
        if (show) any = true;
      });
      sec.style.display = any || !q ? '' : 'none';
      if (any) sec.classList.add('open');
    });
  });
  /* باز/بسته کردن دسته */
  document.querySelectorAll('[data-toggle-cat]').forEach(function (c) {
    c.addEventListener('click', function () { c.closest('.pb-palette-section').classList.toggle('open'); });
  });
  /* افزودن سکشن از پالت */
  document.querySelectorAll('[data-addrow]').forEach(function (b) {
    b.addEventListener('click', function () {
      var id = addRow(parseInt(b.dataset.addrow, 10));
      toast('سکشن ' + b.dataset.addrow + ' ستونه اضافه شد ✅', 'ok');
      immediateRender();
      scrollToElInFrame('[data-row="' + id + '"]');
      selectRow(id);
    });
  });
  /* طرح آماده سایت — جایگزینی کامل چیدمان صفحه */
  document.querySelectorAll('[data-design]').forEach(function (b) {
    b.addEventListener('click', function () {
      var did = b.dataset.design;
      var meta = (window.PB_DESIGNS || []).find(function (x) { return x.id === did; });
      if (!confirm('چیدمان فعلی صفحه با طرح «' + (meta ? meta.name : did) + '» جایگزین شود؟' + '\n' + 'می‌توانید با Ctrl+Z واگردانی کنید.')) return;
      fetch('/builder/api/design-rows/' + did)
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (!res.ok) { toast(res.msg || 'خطا', 'err'); return; }
          var fresh = res.rows.map(function (row) {
            row.id = uid('r');
            row.cols.forEach(function (col) { col.forEach(function (w) { w.id = uid(); }); });
            return row;
          });
          data.rows = fresh;
          pushHistory();
          immediateRender();
          toast('طرح «' + (meta ? meta.name : did) + '» اعمال شد ✅', 'ok');
        })
        .catch(function () { toast('خطا در ارتباط', 'err'); });
    });
  });
  /* قالب آماده */
  document.querySelectorAll('.pb-section-grid [data-tpl]').forEach(function (b) {
    b.addEventListener('click', function () {
      var tpl = SECTION_TPLS[b.dataset.tpl];
      if (!tpl || !tpl.rows) return;
      var copy = JSON.parse(JSON.stringify(tpl.rows));
      copy.forEach(function (row) {
        row.id = uid('r');
        row.cols.forEach(function (col) { col.forEach(function (w) { w.id = uid(); }); });
      });
      data.rows.push.apply(data.rows, copy);
      pushHistory();
      toast('سکشن «' + (tpl.name || '') + '» اضافه شد ✅', 'ok');
      immediateRender();
      scrollToElInFrame('[data-row="' + copy[0].id + '"]');
      selectRow(copy[0].id);
    });
  });
  /* درگ و کلیک برای افزودن */
  var pending = null;
  document.querySelectorAll('.pb-palette-item').forEach(function (item) {
    item.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      pending = { item: item, type: item.dataset.type, x: e.clientX, y: e.clientY };
      var onMove = function (ev) {
        if (!pending) return;
        var dx = ev.clientX - pending.x, dy = ev.clientY - pending.y;
        if (Math.abs(dx) + Math.abs(dy) > 7) {
          var ptype = pending.type;
          finishPending();
          disarm();
          startDrag({ kind: 'new', type: ptype }, ev.clientX, ev.clientY);
        }
      };
      var onUp = function (ev) {
        if (!pending) return;
        var ptype = pending.type;
        finishPending();
        /* بدون حرکت = حالت مسلح (کلیک برای افزودن) */
        if (armedType === ptype) disarm();
        else { disarm(); arm(ptype); }
      };
      function finishPending() {
        pending = null;
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
      }
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      document.addEventListener('pointercancel', onUp);
    });
  });
}

/* ============================================================
   کلیپ‌بورد و میان‌برها
   ============================================================ */
function pasteClipboard() {
  if (!clipboard) return;
  if (clipboard.kind === 'widget') {
    if (!data.rows.length) addRow(1);
    var last = data.rows[data.rows.length - 1];
    var copy = JSON.parse(JSON.stringify(clipboard.data));
    copy.id = uid();
    last.cols[0].push(copy);
    toast('ویجت پیست شد 📋');
  } else {
    var rcopy = JSON.parse(JSON.stringify(clipboard.data));
    rcopy.id = uid('r');
    rcopy.cols.forEach(function (col) { col.forEach(function (w) { w.id = uid(); }); });
    data.rows.push(rcopy);
    toast('سکشن پیست شد 📋');
  }
  pushHistory();
  immediateRender();
}

/* ============================================================
   اتصالات نهایی
   ============================================================ */
function init() {
  /* مهاجرت داده قدیمی ویجت‌ها: «style» رشته‌ای → کلید جدید (btn_style/line_style/cta_style) */
  var STYLE_MIGRATE = { button: 'btn_style', add_to_cart: 'btn_style', divider: 'line_style', cta: 'cta_style' };
  data.rows.forEach(function (r) {
    (r.cols || []).forEach(function (col) {
      col.forEach(function (w) {
        if (!w.data) return;
        var nk = STYLE_MIGRATE[w.type];
        if (nk && typeof w.data.style === 'string') {
          if (w.data.style && !w.data[nk]) w.data[nk] = w.data.style;
          delete w.data.style;
        }
      });
    });
  });
  buildPalette();
  saveBtn.addEventListener('click', save);
  document.getElementById('pb-undo').addEventListener('click', undo);
  document.getElementById('pb-redo').addEventListener('click', redo);
  document.getElementById('pb-preview-btn').addEventListener('click', openPreview);
  document.getElementById('pb-preview-close').addEventListener('click', closePreview);
  document.getElementById('pb-pv-open').addEventListener('click', function () {
    var sep = PREVIEW_URL.indexOf('?') >= 0 ? '&' : '?';
    window.open(PREVIEW_URL + sep + 'preview=1', '_blank');
  });
  document.querySelectorAll('[data-dev]').forEach(function (b) {
    b.addEventListener('click', function () { setDevice(b.dataset.dev); });
  });
  document.querySelectorAll('.pb-pv-devices [data-dev]').forEach(function (b) {
    b.addEventListener('click', function () {
      var dev = b.dataset.dev;
      var f = document.getElementById('pb-preview-frame');
      f.className = 'pb-preview-frame dev-' + dev;
      document.querySelectorAll('.pb-pv-devices [data-dev]').forEach(function (x) { x.classList.toggle('active', x === b); });
    });
  });
  document.getElementById('pb-panel-close').addEventListener('click', function () { sel = null; showPagePanel(); });
  document.getElementById('pb-nav-toggle').addEventListener('click', function () {
    document.getElementById('pb-navigator-drawer').classList.toggle('open');
  });
  document.getElementById('pb-nav-close').addEventListener('click', function () {
    document.getElementById('pb-navigator-drawer').classList.remove('open');
  });
  document.getElementById('pb-palette-toggle').addEventListener('click', function () {
    document.getElementById('pb-palette').classList.toggle('open');
  });
  document.getElementById('pb-panel-toggle').addEventListener('click', function () {
    document.getElementById('pb-panel').classList.toggle('open');
  });
  document.getElementById('pb-page-switch').addEventListener('change', function (e) {
    window.location = '/builder/' + e.target.value;
  });
  document.getElementById('pb-empty-add').addEventListener('click', function () { showAddSectionModal(0); });
  document.getElementById('pb-tpl').addEventListener('click', savePageTemplate);
  /* صفحه‌ساز فقط برای ویرایش؛ خروجی نهایی با دکمه پیش‌نمایش */
  document.addEventListener('keydown', function (e) {
    var ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && e.key === 's') { e.preventDefault(); save(); }
    if (ctrl && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
    if (ctrl && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) { e.preventDefault(); redo(); }
    if (ctrl && e.key === 'd' && sel) {
      e.preventDefault();
      if (sel.type === 'widget') copyWidget(findWidget(sel.id));
      else copyRow(findRow(sel.id));
    }
    if (ctrl && e.key === 'c' && sel) {
      e.preventDefault();
      if (sel.type === 'widget') {
        var f = findWidget(sel.id);
        if (f) { clipboard = { kind: 'widget', data: JSON.parse(JSON.stringify(f.w)) }; toast('ویجت کپی شد ✂️'); }
      } else {
        var fr = findRow(sel.id);
        if (fr) { clipboard = { kind: 'row', data: JSON.parse(JSON.stringify(fr.row)) }; toast('سکشن کپی شد ✂️'); }
      }
    }
    if (ctrl && e.key === 'v' && clipboard) { e.preventDefault(); pasteClipboard(); }
    if (e.key === 'Delete' && sel && !e.target.closest('input,textarea,[contenteditable]')) {
      if (sel.type === 'widget') delWidget(findWidget(sel.id));
      else delRow(findRow(sel.id));
    }
    if (e.key === 'Escape') {
      if (armedType) { disarm(); toast('افزودن لغو شد'); }
      if (drag) cancelDrag();
      var m = document.querySelector('.pb-modal-overlay');
      if (m) m.remove();
    }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });
  showPagePanel();
  updateStatus();
  render();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();

})();
