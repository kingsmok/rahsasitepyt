(function() {
  'use strict';

  var v = document.getElementById('pp-video');
  var lessonId = document.body.getAttribute('data-lesson') || '0';
  var lessonKey = 'play_pos_' + lessonId;
  var notesKey = 'play_notes_' + lessonId;

  function fmt(t) {
    t = Math.floor(t || 0);
    var m = Math.floor(t / 60);
    var s = t % 60;
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }

  function faDigits(s) {
    return String(s).replace(/[0-9]/g, function(d) {
      return '۰۱۲۳۴۵۶۷۸۹'[d];
    });
  }

  // --- Notes Management (Cloud Sync + LocalStorage) ---
  var notesEl = document.getElementById('pp-notes');
  var notesHint = document.getElementById('pp-notes-hint');

  if (notesEl && lessonId !== '0') {
    // 1. Initial value from localStorage if present
    var localNote = localStorage.getItem(notesKey);
    if (localNote) {
      notesEl.value = localNote;
    }

    // 2. Fetch from cloud API
    fetch('/api/lesson/' + lessonId + '/note', {
      headers: { 'Accept': 'application/json' }
    })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data && data.ok && data.note) {
          if (!notesEl.value || notesEl.value.trim() === '') {
            notesEl.value = data.note;
            localStorage.setItem(notesKey, data.note);
          }
        }
      })
      .catch(function(err) {
        console.warn('Note fetch error:', err);
      });

    // 3. Auto-save to cloud and localStorage on input
    var noteSaveTimeout = null;
    notesEl.addEventListener('input', function() {
      var val = notesEl.value;
      localStorage.setItem(notesKey, val);

      if (notesHint) {
        notesHint.textContent = 'در حال ذخیره...';
        notesHint.style.opacity = '1';
      }

      clearTimeout(noteSaveTimeout);
      noteSaveTimeout = setTimeout(function() {
        var csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content ||
                        (document.querySelector('input[name="_csrf_token"]') || {}).value || '';
        
        var curTime = v ? (v.currentTime || 0) : 0;
        fetch('/api/lesson/' + lessonId + '/note', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ note: val, playback_time: curTime })
        })
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (notesHint) {
              notesHint.textContent = '✓ ذخیره شد (همگام‌سازی ابری)';
              setTimeout(function() { notesHint.style.opacity = '0'; }, 2000);
            }
          })
          .catch(function() {
            if (notesHint) {
              notesHint.textContent = '✓ ذخیره شد (محلی)';
              setTimeout(function() { notesHint.style.opacity = '0'; }, 2000);
            }
          });
      }, 800);
    });
  }

  // --- Video Player Controls ---
  if (!v) return;

  var play = document.getElementById('pp-play');
  var seek = document.getElementById('pp-seek');
  var timeEl = document.getElementById('pp-time');
  var mute = document.getElementById('pp-mute');
  var vol = document.getElementById('pp-vol');
  var speed = document.getElementById('pp-speed');
  var quality = document.getElementById('pp-quality');
  var fs = document.getElementById('pp-fs');
  var controls = document.getElementById('pp-controls');
  var wrap = document.getElementById('pp-wrap');

  if (play) {
    play.addEventListener('click', function() {
      if (v.paused) { v.play(); } else { v.pause(); }
    });
  }

  v.addEventListener('play', function() {
    if (play) play.textContent = '⏸';
  });

  v.addEventListener('pause', function() {
    if (play) play.textContent = '▶';
  });

  v.addEventListener('ended', function() {
    if (play) play.textContent = '↻';
    localStorage.removeItem(lessonKey);
  });

  v.addEventListener('timeupdate', function() {
    if (v.duration && seek) {
      seek.value = (v.currentTime / v.duration) * 1000;
    }
    if (timeEl && v.duration) {
      timeEl.textContent = faDigits(fmt(v.currentTime) + ' / ' + fmt(v.duration));
    }
  });

  v.addEventListener('loadedmetadata', function() {
    if (timeEl) {
      timeEl.textContent = faDigits('00:00 / ' + fmt(v.duration));
    }
  });

  if (seek) {
    seek.addEventListener('input', function() {
      if (v.duration) {
        v.currentTime = (seek.value / 1000) * v.duration;
      }
    });
  }

  if (vol && mute) {
    vol.addEventListener('input', function() {
      v.volume = vol.value / 100;
      v.muted = vol.value == 0;
      mute.textContent = vol.value == 0 ? '🔇' : '🔊';
    });

    mute.addEventListener('click', function() {
      v.muted = !v.muted;
      mute.textContent = v.muted ? '🔇' : '🔊';
    });
  }

  if (speed) {
    var speeds = [1, 1.25, 1.5, 1.75, 2];
    speed.addEventListener('click', function() {
      var i = speeds.indexOf(v.playbackRate);
      v.playbackRate = speeds[(i + 1) % speeds.length];
      speed.textContent = faDigits(v.playbackRate) + '×';
    });
  }

  if (quality) {
    quality.addEventListener('click', function() {
      var pos = v.currentTime || 0;
      var playing = !v.paused;
      var current = v.src;
      var hd = quality.dataset.hd;
      var sd = quality.dataset.sd || current;
      if (!quality.dataset.sd) quality.dataset.sd = current;
      var useHd = quality.textContent !== 'SD';
      v.src = useHd ? hd : sd;
      quality.textContent = useHd ? 'SD' : 'HD';
      v.addEventListener('loadedmetadata', function restore() {
        v.removeEventListener('loadedmetadata', restore);
        if (pos < v.duration) v.currentTime = pos;
        if (playing) v.play().catch(function() {});
      });
      v.load();
    });
  }

  var errorEl = null;
  function showErr(m) {
    if (errorEl) return;
    errorEl = document.createElement('div');
    errorEl.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.78);color:#fff;z-index:5;text-align:center;padding:24px;font-size:14px;line-height:2';
    errorEl.textContent = m;
    if (wrap) wrap.appendChild(errorEl);
  }

  v.addEventListener('error', function() {
    if (v.currentSrc) {
      showErr('⚠️ پخش ویدیو ممکن نیست. ممکن است لینک ویدیو از سمت میزبان مسدود شده باشد یا فرمت آن پشتیبانی نشود. لطفاً از «لینک مستقیم» معتبر استفاده کنید.');
    }
  });

  if (fs && wrap) {
    fs.addEventListener('click', function() {
      if (!document.fullscreenElement) {
        if (wrap.requestFullscreen) wrap.requestFullscreen();
        else if (wrap.webkitRequestFullscreen) wrap.webkitRequestFullscreen();
      } else {
        if (document.exitFullscreen) document.exitFullscreen();
      }
    });
  }

  if (wrap && controls) {
    var hideTimer;
    function resetHide() {
      controls.classList.add('show');
      clearTimeout(hideTimer);
      hideTimer = setTimeout(function() {
        controls.classList.remove('show');
      }, 2800);
    }
    wrap.addEventListener('mousemove', resetHide);
    wrap.addEventListener('click', resetHide);
    resetHide();
  }

  if (wrap) {
    wrap.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
    wrap.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S' || e.key === 'u' || e.key === 'U')) {
        e.preventDefault();
        return false;
      }
    });
  }
  v.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });

  // --- Resume Playback (Cloud + Local) ---
  var restored = false;
  function applySavedPosition(pos) {
    if (restored || !pos || pos < 5) return;
    if (v.duration && pos < v.duration - 10) {
      v.currentTime = pos;
      restored = true;
      if (window.showToast) {
        window.showToast('ادامه پخش از دقیقه ' + faDigits(fmt(pos)), 'info', 3000);
      }
    }
  }

  // Check localStorage first
  var saved = localStorage.getItem(lessonKey);
  if (saved) {
    var savedPos = parseFloat(saved);
    if (savedPos > 5) {
      v.addEventListener('loadedmetadata', function() {
        applySavedPosition(savedPos);
      });
    }
  }

  // Fetch Cloud Position
  if (lessonId !== '0') {
    fetch('/api/lesson/' + lessonId + '/playback')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d && d.ok && d.playback_time > 5) {
          if (v.readyState >= 1) {
            applySavedPosition(d.playback_time);
          } else {
            v.addEventListener('loadedmetadata', function() {
              applySavedPosition(d.playback_time);
            });
          }
        }
      })
      .catch(function() {});
  }

  // Periodic Save (Every 6 seconds)
  var lastSentTime = 0;
  setInterval(function() {
    if (v.duration && v.currentTime > 5 && !v.paused) {
      localStorage.setItem(lessonKey, String(v.currentTime));
      
      // Send to server every ~10s if position changed significantly
      if (lessonId !== '0' && Math.abs(v.currentTime - lastSentTime) > 8) {
        lastSentTime = v.currentTime;
        var csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content ||
                        (document.querySelector('input[name="_csrf_token"]') || {}).value || '';
        fetch('/api/lesson/' + lessonId + '/playback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ playback_time: v.currentTime })
        }).catch(function() {});
      }
    }
  }, 5000);

  // --- Timestamp Note Insertion ---
  var insertTimeBtn = document.getElementById('pp-insert-time-btn');
  if (insertTimeBtn && notesEl) {
    insertTimeBtn.addEventListener('click', function(e) {
      e.preventDefault();
      var cur = v ? (v.currentTime || 0) : 0;
      var stamp = '[' + fmt(cur) + '] ';
      var start = notesEl.selectionStart || notesEl.value.length;
      var end = notesEl.selectionEnd || notesEl.value.length;
      var text = notesEl.value;
      notesEl.value = text.substring(0, start) + stamp + text.substring(end);
      notesEl.focus();
      notesEl.setSelectionRange(start + stamp.length, start + stamp.length);
      notesEl.dispatchEvent(new Event('input'));
    });
  }

  // --- Keyboard Shortcuts (Space, F, M, Arrow Keys) ---
  document.addEventListener('keydown', function(e) {
    var tag = (document.activeElement && document.activeElement.tagName) ? document.activeElement.tagName.toLowerCase() : '';
    if (tag === 'textarea' || tag === 'input' || tag === 'select' || (document.activeElement && document.activeElement.isContentEditable)) {
      return;
    }

    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      if (v.paused) v.play(); else v.pause();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      v.currentTime = Math.min(v.duration || 0, v.currentTime + 5);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      v.currentTime = Math.max(0, v.currentTime - 5);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      v.volume = Math.min(1, v.volume + 0.1);
      if (vol) vol.value = v.volume * 100;
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      v.volume = Math.max(0, v.volume - 0.1);
      if (vol) vol.value = v.volume * 100;
    } else if (e.key === 'f' || e.key === 'F') {
      if (fs) fs.click();
    } else if (e.key === 'm' || e.key === 'M') {
      if (mute) mute.click();
    }
  });

  // --- Sidebar Lesson Quick Search ---
  var searchInput = document.getElementById('lesson-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      var q = (searchInput.value || '').trim().toLowerCase();
      var items = document.querySelectorAll('.lesson-list-side .lesson-item');
      items.forEach(function(item) {
        var text = (item.textContent || '').toLowerCase();
        item.style.display = (!q || text.indexOf(q) !== -1) ? 'flex' : 'none';
      });
    });
  }

  // --- Close Celebration Modal ---
  var closeCelebration = document.getElementById('close-celebration-modal');
  var celebrationOverlay = document.getElementById('celebration-modal-overlay');
  if (closeCelebration && celebrationOverlay) {
    closeCelebration.addEventListener('click', function() {
      celebrationOverlay.style.display = 'none';
    });
    celebrationOverlay.addEventListener('click', function(e) {
      if (e.target === celebrationOverlay) {
        celebrationOverlay.style.display = 'none';
      }
    });
  }

})();
