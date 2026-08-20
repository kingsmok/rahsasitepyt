/* ============================================================
   کتابخانه رسانه (شبیه وردپرس) — انتخابگر سراسری فایل
   ============================================================
   استفاده:
     <button type="button" onclick="MediaLibrary.open({
        target: 'image',            // name یا id ورودی مخفی/متنی مقصد
        preview: 'preview-id',      // (اختیاری) id تصویر پیش‌نمایش
        filter: 'image',            // image | video | audio | file | ''
        multiple: false,            // انتخاب چندتایی
        csrf: document.getElementById('global-csrf-token').value
     })">کتابخانه رسانه</button>

   بعد از انتخاب، مقدار URL فایل (مثل /static/uploads/media/x.jpg)
   داخل ورودی مقصد نوشته و رویداد change صادر می‌شود.
   ============================================================ */
(function () {
  'use strict';

  var modal = null;
  var state = null;
  var page = 1;
  var hasMore = false;
  var items = [];
  var selected = [];

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === 'class') { node.className = attrs[k]; }
      else if (k === 'text') { node.textContent = attrs[k]; }
      else if (k === 'html') { node.innerHTML = attrs[k]; }
      else { node.setAttribute(k, attrs[k]); }
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function csrfToken() {
    var t = document.getElementById('global-csrf-token');
    if (t && t.value) return t.value;
    var m = document.querySelector('meta[name="csrf-token"]');
    if (m && m.getAttribute('content')) return m.getAttribute('content');
    var h = document.querySelector('input[name="_csrf_token"]');
    return h ? h.value : '';
  }

  function toast(msg, ok) {
    var box = document.getElementById('mm-toast');
    if (!box) return;
    box.textContent = msg;
    box.style.display = 'block';
    box.className = 'mm-toast ' + (ok ? 'ok' : 'err');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { box.style.display = 'none'; }, 3200);
  }

  function kindLabel(kind) {
    return { image: 'تصویر', video: 'ویدیو', audio: 'صدا', file: 'فایل' }[kind] || 'فایل';
  }

  function kindIcon(kind) {
    return { image: '🖼', video: '🎥', audio: '🎵', file: '📄' }[kind] || '📄';
  }

  function renderGrid(container) {
    container.innerHTML = '';
    if (!items.length) {
      container.appendChild(el('div', { class: 'mm-empty', text: 'فایلی یافت نشد — فایل جدید آپلود کنید.' }));
      return;
    }
    items.forEach(function (m) {
      var isSel = selected.indexOf(m.url) !== -1;
      var card = el('div', { class: 'mm-item' + (isSel ? ' selected' : ''), 'data-url': m.url });
      var thumb = el('div', { class: 'mm-thumb' });
      if (m.kind === 'image') {
        thumb.appendChild(el('img', { src: m.url, alt: m.name, loading: 'lazy' }));
      } else {
        thumb.appendChild(el('span', { class: 'mm-kind-ic', text: kindIcon(m.kind) }));
      }
      var meta = el('div', { class: 'mm-meta' });
      meta.appendChild(el('div', { class: 'mm-name', text: m.name, title: m.name }));
      meta.appendChild(el('div', { class: 'mm-sub', text: (m.size || '') + (m.width ? (' · ' + m.width + '×' + m.height) : '') + ' · ' + kindLabel(m.kind) }));
      card.appendChild(thumb);
      card.appendChild(meta);
      if (state.canDelete) {
        var del = el('button', { type: 'button', class: 'mm-del', title: 'حذف', text: '🗑' });
        del.addEventListener('click', function (e) {
          e.stopPropagation();
          deleteMedia(m.id, card);
        });
        card.appendChild(del);
      }
      card.addEventListener('click', function () { choose(m); });
      container.appendChild(card);
    });
    var more = document.getElementById('mm-more');
    if (more) {
      more.style.display = hasMore ? 'block' : 'none';
    }
  }

  function choose(m) {
    if (state.multiple) {
      var idx = selected.indexOf(m.url);
      if (idx === -1) { selected.push(m.url); } else { selected.splice(idx, 1); }
      var grid = document.getElementById('mm-grid');
      if (grid) renderGrid(grid);
      syncTarget();
      return;
    }
    setTarget(m.url);
    close();
  }

  function setTarget(url) {
    var input = document.querySelector('[name="' + state.target + '"], #' + state.target);
    if (!input) return;
    if (input.tagName === 'SELECT') {
      var opt = Array.prototype.slice.call(input.options).filter(function (o) { return o.value === url; })[0];
      if (!opt) {
        opt = document.createElement('option');
        opt.value = url;
        opt.textContent = '📁 از کتابخانه: ' + url;
        input.appendChild(opt);
      }
      input.value = url;
    } else {
      input.value = url;
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('input', { bubbles: true }));
    if (state.preview) {
      var img = document.getElementById(state.preview);
      if (img && img.tagName === 'IMG') { img.src = url; img.style.display = 'block'; }
    }
  }

  function syncTarget() {
    var input = document.querySelector('[name="' + state.target + '"], #' + state.target);
    if (!input) return;
    if (state.multiple) {
      input.value = selected.join(',');
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
    if (state.preview && selected.length) {
      var img = document.getElementById(state.preview);
      if (img && img.tagName === 'IMG') { img.src = selected[selected.length - 1]; img.style.display = 'block'; }
    }
  }

  function loadList(reset) {
    if (reset) { page = 1; items = []; }
    var kind = document.getElementById('mm-kind') ? document.getElementById('mm-kind').value : '';
    var q = document.getElementById('mm-search') ? document.getElementById('mm-search').value : '';
    var grid = document.getElementById('mm-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="mm-empty">در حال بارگذاری...</div>';
    var url = '/api/media/list?kind=' + encodeURIComponent(kind) +
      '&q=' + encodeURIComponent(q) + '&page=' + page + '&per_page=40';
    fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { grid.innerHTML = '<div class="mm-empty">' + (d.msg || 'خطا در دریافت فایل‌ها') + '</div>'; return; }
        items = items.concat(d.items || []);
        hasMore = !!d.has_more;
        renderGrid(grid);
      })
      .catch(function () {
        grid.innerHTML = '<div class="mm-empty">خطای شبکه — دوباره تلاش کنید.</div>';
      });
  }

  function uploadFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;
    var form = new FormData();
    files.forEach(function (f) { form.append('files', f, f.name); });
    var bar = document.getElementById('mm-progress');
    if (bar) {
      bar.style.display = 'block';
      bar.textContent = 'در حال آپلود ' + files.length + ' فایل...';
    }
    fetch('/api/media/upload', {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': csrfToken(), 'Accept': 'application/json' }
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (bar) bar.style.display = 'none';
        if (d.ok) {
          toast((d.items || []).length + ' فایل به کتابخانه اضافه شد ✓', true);
          if (d.errors && d.errors.length) toast(d.errors[0], false);
          loadList(true);
          // انتخاب خودکار آخرین فایل آپلودشده (رفتار وردپرس)
          if (d.items && d.items.length && !state.multiple) {
            setTarget(d.items[d.items.length - 1].url);
            close();
          } else if (d.items && d.items.length && state.multiple) {
            d.items.forEach(function (it) { if (selected.indexOf(it.url) === -1) selected.push(it.url); });
            syncTarget();
            loadList(true);
          }
        } else {
          toast(d.msg || 'آپلود ناموفق بود', false);
        }
      })
      .catch(function () { if (bar) bar.style.display = 'none'; toast('خطای شبکه در آپلود', false); });
  }

  function deleteMedia(id, card) {
    if (!confirm('این فایل از کتابخانه و از دیسک حذف شود؟')) return;
    fetch('/api/media/delete', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken(), 'Accept': 'application/json' },
      body: JSON.stringify({ id: id })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) { toast('فایل حذف شد 🗑', true); loadList(true); }
        else { toast(d.msg || 'حذف ممکن نشد', false); }
      })
      .catch(function () { toast('خطای شبکه', false); });
  }

  function buildModal() {
    if (modal) return modal;
    var overlay = el('div', { id: 'media-library-modal', class: 'mm-overlay' });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

    var panel = el('div', { class: 'mm-panel' });
    var head = el('div', { class: 'mm-head' });
    head.appendChild(el('div', { class: 'mm-title', text: '📁 کتابخانه رسانه' }));
    var closeBtn = el('button', { type: 'button', class: 'mm-close', text: '✕', 'aria-label': 'بستن' });
    closeBtn.addEventListener('click', close);
    head.appendChild(closeBtn);
    panel.appendChild(head);

    var tabs = el('div', { class: 'mm-tabs' });
    var tabLib = el('button', { type: 'button', class: 'mm-tab active', text: '🖼 کتابخانه' });
    var tabUp = el('button', { type: 'button', class: 'mm-tab', text: '⬆ آپلود جدید' });
    tabs.appendChild(tabLib);
    tabs.appendChild(tabUp);
    panel.appendChild(tabs);

    // ── زبانهٔ کتابخانه ──
    var lib = el('div', { class: 'mm-tabpane', id: 'mm-lib' });
    var bar = el('div', { class: 'mm-bar' });
    var search = el('input', { type: 'search', id: 'mm-search', class: 'mm-search', placeholder: 'جستجوی نام فایل...' });
    search.addEventListener('input', function () { clearTimeout(search._t); search._t = setTimeout(function () { loadList(true); }, 350); });
    var kindSel = el('select', { id: 'mm-kind', class: 'mm-kind' });
    [['', 'همه انواع'], ['image', '🖼 تصویر'], ['video', '🎥 ویدیو'], ['audio', '🎵 صدا'], ['file', '📄 فایل']].forEach(function (kv) {
      var o = el('option', { value: kv[0], text: kv[1] });
      kindSel.appendChild(o);
    });
    kindSel.addEventListener('change', function () { loadList(true); });
    bar.appendChild(search);
    bar.appendChild(kindSel);
    lib.appendChild(bar);
    var grid = el('div', { class: 'mm-grid', id: 'mm-grid' });
    lib.appendChild(grid);
    var more = el('button', { type: 'button', class: 'mm-more', id: 'mm-more', text: 'نمایش بیشتر ↓' });
    more.addEventListener('click', function () { page += 1; loadList(false); });
    lib.appendChild(more);
    panel.appendChild(lib);

    // ── زبانهٔ آپلود ──
    var up = el('div', { class: 'mm-tabpane', id: 'mm-up', style: 'display:none' });
    var drop = el('div', { class: 'mm-drop', id: 'mm-drop' });
    drop.appendChild(el('div', { class: 'mm-drop-ic', text: '☁️' }));
    drop.appendChild(el('div', { text: 'فایل‌ها را اینجا بکشید یا کلیک کنید' }));
    drop.appendChild(el('div', { class: 'mm-drop-hint', text: 'JPG / PNG / WebP / GIF / MP4 / MP3 / PDF — حداکثر ۲۰ فایل در هر بار' }));
    var fileInput = el('input', { type: 'file', id: 'mm-file', multiple: 'multiple', style: 'display:none' });
    fileInput.addEventListener('change', function () { uploadFiles(fileInput.files); fileInput.value = ''; });
    drop.addEventListener('click', function () { fileInput.click(); });
    ['dragover', 'dragenter'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('drag'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('drag'); });
    });
    drop.addEventListener('drop', function (e) { uploadFiles(e.dataTransfer.files); });
    up.appendChild(drop);
    up.appendChild(fileInput);
    var progress = el('div', { class: 'mm-progress', id: 'mm-progress', style: 'display:none' });
    up.appendChild(progress);
    panel.appendChild(up);

    var toastBox = el('div', { id: 'mm-toast', class: 'mm-toast', style: 'display:none' });
    panel.appendChild(toastBox);

    tabLib.addEventListener('click', function () {
      tabLib.classList.add('active'); tabUp.classList.remove('active');
      lib.style.display = 'block'; up.style.display = 'none';
      loadList(true);
    });
    tabUp.addEventListener('click', function () {
      tabUp.classList.add('active'); tabLib.classList.remove('active');
      up.style.display = 'block'; lib.style.display = 'none';
    });

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    modal = overlay;
    return overlay;
  }

  function open(opts) {
    state = {
      target: (opts && opts.target) || '',
      preview: (opts && opts.preview) || '',
      multiple: !!(opts && opts.multiple),
      canDelete: !(opts && opts.canDelete === false),
      filter: (opts && opts.filter) || ''
    };
    selected = [];
    buildModal();
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    var kindSel = document.getElementById('mm-kind');
    if (kindSel) {
      kindSel.value = ['image', 'video', 'audio', 'file'].indexOf(state.filter) !== -1 ? state.filter : '';
    }
    var search = document.getElementById('mm-search');
    if (search) search.value = '';
    // پیش‌انتخاب مقدار فعلی ورودی مقصد
    var input = document.querySelector('[name="' + state.target + '"], #' + state.target);
    if (input && input.value) {
      selected = input.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    }
    var tabLib = modal.querySelector('.mm-tab.active');
    loadList(true);
  }

  function close() {
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });

  window.MediaLibrary = {
    open: open,
    close: close
  };
})();
