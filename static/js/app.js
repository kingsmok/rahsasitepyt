(function(){'use strict';function toast(msg,type){var box=document.querySelector('.toasts');if(!box){box=document.createElement('div');box.className='toasts';document.body.appendChild(box);}
var icons={success:'✅',error:'⚠️',info:'💡'};var t=document.createElement('div');t.className='toast '+(type||'info');t.innerHTML='<span class="t-ic">'+(icons[type]||icons.info)+'</span><span>'+msg+'</span>'+'<button class="close" onclick="this.parentElement.remove()">✕</button>';box.appendChild(t);setTimeout(function(){t.style.opacity='0';t.style.transition='opacity .4s';setTimeout(function(){t.remove();},450);},4200);}
window.toast=toast;document.querySelectorAll('.flash-data').forEach(function(el){setTimeout(function(){toast(el.dataset.msg,el.dataset.type);},350);});var header=document.querySelector('.site-header');if(header){window.addEventListener('scroll',function(){header.classList.toggle('scrolled',window.scrollY>10);});}
var hamburger=document.querySelector('.hamburger')||document.getElementById('mobile-menu-fab');var mm=document.querySelector('.mobile-menu');if(hamburger&&mm){hamburger.addEventListener('click',function(){mm.classList.add('open');});mm.querySelectorAll('[data-close-mm]').forEach(function(b){b.addEventListener('click',function(){mm.classList.remove('open');});});}
function updateCartBadge(count){document.querySelectorAll('.cart-count').forEach(function(el){el.textContent=count;el.style.display=count>0?'flex':'none';});}
document.querySelectorAll('[data-add-cart]').forEach(function(btn){btn.addEventListener('click',function(e){e.preventDefault();var id=btn.dataset.addCart;var original=btn.innerHTML;btn.innerHTML='<span class="spinner"></span>';btn.classList.add('disabled');fetch('/api/cart/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:parseInt(id,10)})}).then(function(r){return r.json();}).then(function(d){btn.innerHTML=original;btn.classList.remove('disabled');if(d.ok){updateCartBadge(d.count);toast(d.msg,'success');btn.innerHTML='✓ اضافه شد';setTimeout(function(){btn.innerHTML=original;},1600);maybeShowUpsell(id);}else if(d.login){window.location='/auth/login';}}).catch(function(){btn.innerHTML=original;btn.classList.remove('disabled');toast('خطا در ارتباط با سرور','error');});});});document.querySelectorAll('[data-remove-cart]').forEach(function(btn){btn.addEventListener('click',function(){var id=btn.dataset.removeCart;fetch('/api/cart/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:parseInt(id,10)})}).then(function(r){return r.json();}).then(function(d){if(d.ok){updateCartBadge(d.count);location.reload();}});});});function updateFavBadges(n){document.querySelectorAll('.fav-count').forEach(function(el){el.textContent=n;el.style.display=n>0?'flex':'none';});}
document.querySelectorAll('[data-fav]').forEach(function(btn){btn.addEventListener('click',function(){var id=btn.dataset.fav;fetch('/api/favorite/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:parseInt(id,10)})}).then(function(r){return r.json();}).then(function(d){if(d.login){window.location='/auth/login';return;}
if(d.ok){if(d.fav){btn.classList.add('active');toast(d.msg,'success');}
else{btn.classList.remove('active');toast(d.msg,'info');}
if(typeof d.count!=='undefined')updateFavBadges(d.count);}});});});var siteHeader=document.querySelector('.builder-site-header');if(siteHeader){var headerScroll=function(){if(window.scrollY>40)siteHeader.classList.add('scrolled');else siteHeader.classList.remove('scrolled');};window.addEventListener('scroll',headerScroll,{passive:true});headerScroll();}
/* انتخاب تم از طریق «طراحی‌های سایت» در پنل مدیریت انجام می‌شود */

document.querySelectorAll('.course-tabs button').forEach(function(btn){btn.addEventListener('click',function(){document.querySelectorAll('.course-tabs button').forEach(function(b){b.classList.remove('active');});btn.classList.add('active');var target=btn.dataset.tab;document.querySelectorAll('.tab-pane').forEach(function(p){p.style.display=p.id===target?'block':'none';});});});document.querySelectorAll('.accordion .acc-head, .faq-item .fq-q').forEach(function(head){head.addEventListener('click',function(){var item=head.closest('.accordion, .faq-item');var isOpen=item.classList.contains('open');var scope=head.closest('[data-acc-group]');if(scope){scope.querySelectorAll('.accordion, .faq-item').forEach(function(i){if(i!==item)i.classList.remove('open');});}
item.classList.toggle('open',!isOpen);});});document.querySelectorAll('[data-countdown]').forEach(function(box){var end=Date.now()+parseInt(box.dataset.countdown,10)*1000;function tick(){var diff=Math.max(0,end-Date.now());var h=Math.floor(diff/3600000),m=Math.floor(diff%3600000/60000),s=Math.floor(diff%60000/1000);function pad(n){return String(n).padStart(2,'0');}
box.querySelector('.cd-h').textContent=pad(h);box.querySelector('.cd-m').textContent=pad(m);box.querySelector('.cd-s').textContent=pad(s);}
tick();setInterval(tick,1000);});document.querySelectorAll('.gateway-card').forEach(function(card){card.addEventListener('click',function(){document.querySelectorAll('.gateway-card').forEach(function(c){c.classList.remove('selected');});card.classList.add('selected');var radio=card.querySelector('input[type=radio]');if(radio)radio.checked=true;});});var cardInput=document.getElementById('card-number');if(cardInput){cardInput.addEventListener('input',function(){var v=cardInput.value.replace(/[^\d]/g,'').slice(0,16);cardInput.value=v.replace(/(\d{4})(?=\d)/g,'$1-');});}
document.querySelectorAll('.poster').forEach(function(poster){poster.addEventListener('click',function(){var video=poster.parentElement.querySelector('video');if(video){poster.style.display='none';video.play().catch(function(){});}});});document.querySelectorAll('.img-picker').forEach(function(img){img.addEventListener('click',function(){var input=document.getElementById('image-input');if(input){input.value=img.dataset.src;document.querySelectorAll('.img-picker').forEach(function(i){i.style.outline=i===img?'3px solid var(--primary)':'none';});}});});document.querySelectorAll('[data-copy]').forEach(function(btn){btn.addEventListener('click',function(){var val=btn.dataset.copy;navigator.clipboard.writeText(val).then(function(){toast('کد کپی شد: '+val,'success');});});});var btt=document.getElementById('back-to-top');if(btt){window.addEventListener('scroll',function(){btt.classList.toggle('show',window.scrollY>400);},{passive:true});btt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});}
var sf=document.querySelector('.support-fab .sf-btn');var sp=document.querySelector('.support-pop');if(sf&&sp){sf.addEventListener('click',function(){sp.classList.toggle('open');});document.addEventListener('click',function(e){if(!sp.contains(e.target)&&!sf.contains(e.target)){sp.classList.remove('open');}});}
document.querySelectorAll('.pb-slider').forEach(function(slider){var track=slider.querySelector('.pb-slider-track');var slides=slider.querySelectorAll('.pb-slide');var dotsBox=slider.querySelector('.pb-slide-dots');var idx=0,timer=null;if(!slides.length)return;if(dotsBox){slides.forEach(function(_,i){var d=document.createElement('i');d.addEventListener('click',function(){go(i);});dotsBox.appendChild(d);});}
function dots(){if(!dotsBox)return;dotsBox.querySelectorAll('i').forEach(function(d,i){d.classList.toggle('active',i===idx);});}
function go(i){idx=(i+slides.length)%slides.length;track.style.transform='translateX('+(idx*-100)+'%)';dots();restart();}
function restart(){if(timer)clearInterval(timer);var autoplay=slider.dataset.autoplay;var interval=(parseInt(slider.dataset.interval,10)||5)*1000;if(autoplay&&!document.body.classList.contains('pb-editor-body')&&!document.body.classList.contains('pb-edit-frame'))timer=setInterval(function(){go(idx+1);},interval);}
var prev=slider.querySelector('.pb-arrow-prev');var next=slider.querySelector('.pb-arrow-next');if(prev)prev.addEventListener('click',function(){go(idx-1);});if(next)next.addEventListener('click',function(){go(idx+1);});dots();restart();slider.addEventListener('mouseenter',function(){if(timer)clearInterval(timer);});slider.addEventListener('mouseleave',restart);if(slider.dataset.swipe==='1'){var sx=0,sy=0,st=0;slider.addEventListener('pointerdown',function(e){sx=e.clientX;sy=e.clientY;st=Date.now();},{passive:true});slider.addEventListener('pointerup',function(e){var dx=e.clientX-sx,dy=e.clientY-sy;if(Math.abs(dx)<40||Math.abs(dx)<Math.abs(dy)*1.4||Date.now()-st>900)return;if(dx<0)go(idx+1);else go(idx-1);},{passive:true});}slider.addEventListener('keydown',function(e){if(e.key==='ArrowLeft')go(idx-1);if(e.key==='ArrowRight')go(idx+1);});slider.setAttribute('tabindex','0');});document.querySelectorAll('[data-dk-mega], .dk-mega-trigger').forEach(function(btn){if(btn.hasAttribute('data-dk-mega')){btn.addEventListener('click',function(e){e.preventDefault();var panel=document.getElementById('dk-mega-mobile');if(panel)panel.classList.toggle('open');});}});document.querySelectorAll('.dk-mega').forEach(function(mega){var trigger=mega.querySelector('.dk-mega-trigger');if(!trigger)return;trigger.addEventListener('click',function(e){e.stopPropagation();mega.classList.toggle('open');});document.addEventListener('click',function(e){if(!mega.contains(e.target))mega.classList.remove('open');});});document.addEventListener('click',function(e){var panel=document.getElementById('dk-mega-mobile');if(panel&&!e.target.closest('[data-dk-mega]')&&!panel.contains(e.target))panel.classList.remove('open');});var nav=document.getElementById('mobile-bottom-nav');if(nav){var path=window.location.pathname;nav.querySelectorAll('[data-mb-link]').forEach(function(a){var href=a.getAttribute('data-mb-link')||'';if(!href||href==='#')return;if(path===href||(href!=='/'&&path.indexOf(href)===0))a.classList.add('active');else a.classList.remove('active');});}
if('IntersectionObserver'in window){var obs=new IntersectionObserver(function(entries){entries.forEach(function(en){if(en.isIntersecting){en.target.classList.add('pb-anim-in');obs.unobserve(en.target);}});},{threshold:0.12});document.querySelectorAll('[data-anim]').forEach(function(el){obs.observe(el);});}
document.querySelectorAll('.pb-tabs-head').forEach(function(head){head.addEventListener('click',function(e){var btn=e.target.closest('button[data-tab]');if(!btn)return;var tabs=head.closest('.pb-tabs');head.querySelectorAll('button').forEach(function(b){b.classList.remove('active');});btn.classList.add('active');tabs.querySelectorAll('.pb-tab-pane').forEach(function(p,i){p.classList.toggle('active',i===parseInt(btn.dataset.tab,10));});});});document.querySelectorAll('.pb-accordion, .pb-toggle').forEach(function(acc){var multi=acc.classList.contains('pb-accordion')&&acc.dataset.multi==='1';acc.querySelectorAll('.pb-acc-head').forEach(function(head){head.addEventListener('click',function(){var item=head.closest('.pb-acc-item');if(!multi&&!item.classList.contains('open')){acc.querySelectorAll('.pb-acc-item.open').forEach(function(i){i.classList.remove('open');});}
item.classList.toggle('open');});});});document.querySelectorAll('.pb-alert-close').forEach(function(btn){btn.addEventListener('click',function(){var a=btn.closest('.pb-alert');a.style.transition='opacity .3s, transform .3s';a.style.opacity='0';a.style.transform='translateY(-8px)';setTimeout(function(){a.remove();},300);});});/* میانبرهای کیبورد: / جستجو · h خانه · c دوره‌ها · Esc بستن مودال‌ها */
document.addEventListener('keydown', function(e){
  if(e.target.closest('input,textarea,select,[contenteditable]')) return;
  if(e.ctrlKey || e.metaKey || e.altKey) return;
  var k = e.key.toLowerCase();
  if(k === '/'){ e.preventDefault(); var s=document.querySelector('.dk-search input, .search-box input, header input[type="text"], input[placeholder*="جستجو"]'); if(s){s.focus();} }
  else if(k === 'h'){ window.location='/'; }
  else if(k === 'c'){ window.location='/courses'; }
  else if(k === 'Escape'){ document.querySelectorAll('.modal.open,.mobile-menu.open,.theme-panel.open').forEach(function(m){m.classList.remove('open');}); }
  else if(k === '?'){ e.preventDefault(); toast('⌨️ میانبرها: «/» جستجو · «h» خانه · «c» دوره‌ها · «Esc» بستن پنجره‌ها', 'info'); }
});
/* دکمه‌های state-based: هنگام submit فرم، لودینگ + غیرفعال (ضد ارسال دوباره) */
document.addEventListener('submit', function(e){
  var form = e.target;
  if(form.tagName !== 'FORM') return;
  var btn = form.querySelector('button[type="submit"]');
  if(!btn || btn.disabled) return;
  btn.dataset.orig = btn.innerHTML;
  btn.disabled = true;
  btn.classList.add('btn-loading');
  btn.innerHTML = '<span class="spinner"></span> در حال ارسال...';
  /* اگر فرم خطای سرور برگرداند (مثل ریدایرکت نیست) — فقط در SPA؛ فرمهای معمولی ریدایرکت میشوند */
  setTimeout(function(){
    if(document.body.contains(btn) && btn.disabled && !form.dataset.done){
      btn.disabled = false;
      btn.classList.remove('btn-loading');
      btn.innerHTML = btn.dataset.orig;
    }
  }, 8000);
});
function copyCoupon(){
  var c=document.getElementById('exit-coupon');
  if(!c)return;
  navigator.clipboard.writeText(c.textContent.trim()).then(function(){
    toast('کد تخفیف کپی شد ✅','success');
  }).catch(function(){
    toast('کپی ناموفق بود','error');
  });
}
function faNum(s){return String(s).replace(/[0-9]/g,function(d){return'۰۱۲۳۴۵۶۷۸۹'[d];});}
if('IntersectionObserver'in window){var cObs=new IntersectionObserver(function(entries){entries.forEach(function(en){if(!en.isIntersecting)return;var el=en.target;cObs.unobserve(el);var target=parseFloat(el.dataset.counter||0);var prefix=el.dataset.prefix||'';var suffix=el.dataset.suffix||'';var t0=null;function step(ts){if(!t0)t0=ts;var p=Math.min(1,(ts-t0)/1500);var val=Math.floor(target*(1-Math.pow(1-p,3)));el.textContent=prefix+faNum(val.toLocaleString('en-US'))+suffix;if(p<1)requestAnimationFrame(step);else el.textContent=prefix+faNum(target.toLocaleString('en-US'))+suffix;}
requestAnimationFrame(step);});},{threshold:0.3});document.querySelectorAll('[data-counter]').forEach(function(el){cObs.observe(el);});}
var pObs=new IntersectionObserver(function(entries){entries.forEach(function(en){if(en.isIntersecting){en.target.style.width=en.target.dataset.pct+'%';pObs.unobserve(en.target);}});},{threshold:0.3});document.querySelectorAll('.pb-progress .bar[data-pct]').forEach(function(bar){pObs.observe(bar);});var lb=document.createElement('div');lb.className='pb-lightbox';lb.innerHTML='<img alt="">';lb.addEventListener('click',function(){lb.classList.remove('open');});document.body.appendChild(lb);document.querySelectorAll('.pb-gallery-lb .pb-gal-item img').forEach(function(img){img.addEventListener('click',function(){lb.querySelector('img').src=img.src;lb.classList.add('open');});});document.querySelectorAll('.pb-portfolio-filters').forEach(function(fbox){fbox.addEventListener('click',function(e){var btn=e.target.closest('button[data-pf]');if(!btn)return;var pf=btn.dataset.pf;fbox.querySelectorAll('button').forEach(function(b){b.classList.remove('active');});btn.classList.add('active');var port=fbox.closest('.pb-portfolio');port.querySelectorAll('.pb-pf-item').forEach(function(it){it.style.display=(pf==='all'||it.dataset.cat===pf)?'':'none';});});});function shareLink(net){var u=encodeURIComponent(location.href);var t=encodeURIComponent(document.title);switch(net){case'telegram':return'https://t.me/share/url?url='+u+'&text='+t;case'whatsapp':return'https://wa.me/?text='+t+'%20'+u;case'twitter':return'https://twitter.com/intent/tweet?url='+u+'&text='+t;case'facebook':return'https://www.facebook.com/sharer/sharer.php?u='+u;case'linkedin':return'https://www.linkedin.com/sharing/share-offsite/?url='+u;case'email':return'mailto:?subject='+t+'&body='+u;case'copy':return null;}
return null;}
document.querySelectorAll('.pb-share-btn').forEach(function(btn){btn.addEventListener('click',function(){var net=btn.dataset.share;var url=shareLink(net);if(net==='copy'){navigator.clipboard.writeText(location.href).then(function(){toast('لینک کپی شد ✅','success');});}else if(url){window.open(url,'_blank','width=640,height=520');}});});document.querySelectorAll('.pb-code-num code').forEach(function(code){var lines=(code.textContent||'').split('\n');code.innerHTML=lines.map(function(l){return'<span>'+l+'</span>';}).join('');});document.querySelectorAll('.pb-aw-words').forEach(function(wrap){var words=[];try{words=JSON.parse(wrap.dataset.words||'[]');}catch(e){}
if(!words.length)words=['یادگیری'];var wordEl=wrap.querySelector('.pb-aw-word');var idx=0;function show(){wordEl.textContent=words[idx];wordEl.style.color=wrap.dataset.color||'var(--primary)';wordEl.classList.add('show');setTimeout(function(){wordEl.classList.remove('show');idx=(idx+1)%words.length;setTimeout(show,500);},2600);}
show();});document.querySelectorAll('.pb-form').forEach(function(form){form.addEventListener('submit',function(e){e.preventDefault();if(document.body.classList.contains('pb-editor-body')||document.body.classList.contains('pb-edit-frame'))return;var fields=[];form.querySelectorAll('.pb-form-row').forEach(function(row){var label=(row.querySelector('label')||{}).textContent||'';var input=row.querySelector('input, textarea, select');fields.push({label:label.replace('*','').trim(),value:input?input.value:''});});var btn=form.querySelector('button[type=submit]');var msg=form.querySelector('.pb-form-msg');if(btn){btn.disabled=true;btn.textContent='…در حال ارسال';}
fetch('/api/form',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields:fields,to:form.dataset.to||'contact'})}).then(function(r){return r.json();}).then(function(d){if(btn){btn.disabled=false;btn.textContent=form.querySelector('button[type=submit]').dataset.orig||'ارسال';}
if(msg){msg.className='pb-form-msg '+(d.ok?'ok':'err');msg.textContent=d.ok?(form.dataset.success||d.msg):d.msg;}
if(d.ok)form.reset();}).catch(function(){if(btn)btn.disabled=false;if(msg){msg.className='pb-form-msg err';msg.textContent='خطا در ارتباط با سرور';}});});var btn=form.querySelector('button[type=submit]');if(btn)btn.dataset.orig=btn.textContent;});document.querySelectorAll('a[href^="#"]').forEach(function(a){a.addEventListener('click',function(e){var id=a.getAttribute('href');if(id.length<2)return;var target=document.getElementById(id.slice(1));if(target){e.preventDefault();target.scrollIntoView({behavior:'smooth',block:'start'});}});});})();/* Skeleton loader: هنگام ناوبری داخلی، محتوای اصلی را با اسکلتون جایگزین کن */
(function(){
  var main = document.querySelector('main, .section');
  if(!main) return;
  function showSkeleton(){
    var w = document.createElement('div');
    w.className = 'sk-wrap sk-loading';
    w.id = 'sk-skeleton';
    for(var i=0;i<4;i++){
      w.innerHTML += '<div class="sk-card"><div class="sk sk-thumb"></div><div class="sk sk-line"></div><div class="sk sk-line mid"></div><div class="sk sk-line short"></div><div class="sk sk-btn"></div></div>';
    }
    /* فقط برای صفحات لیستی (دورهها/بلاگ/اساتید) */
    if(!/\/(courses|blog|teachers)(\?|$)/.test(location.pathname)) return;
    main.classList.add('sk-loading');
    var old = main.firstElementChild;
    main.insertBefore(w, main.firstChild);
    window.addEventListener('load', function(){ removeSkeleton(); });
    setTimeout(removeSkeleton, 3000); /* fallback */
    function removeSkeleton(){
      var sk = document.getElementById('sk-skeleton');
      if(sk) sk.remove();
      main.classList.remove('sk-loading');
    }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', showSkeleton);
  else showSkeleton();
})();
if('serviceWorker'in navigator&&location.protocol.startsWith('http')){window.addEventListener('load',function(){navigator.serviceWorker.register('/static/sw.js').catch(function(){});});}
(function(){var shown=sessionStorage.getItem('exit_offer_shown');var modal=document.getElementById('exit-offer');if(!modal||shown)return;var fired=false;var interacted=false;function maybeShow(e){if(fired||!interacted)return;if(e.clientY<=8||(e.relatedTarget&&e.relatedTarget.tagName==='IFRAME')){fired=true;sessionStorage.setItem('exit_offer_shown','1');modal.classList.add('open');}}
document.addEventListener('mousemove',function(){interacted=true;},{passive:true});document.addEventListener('mouseout',maybeShow);document.addEventListener('mouseleave',maybeShow);modal.querySelector('.eo-close').addEventListener('click',function(){modal.classList.remove('open');});modal.addEventListener('click',function(e){if(e.target===modal)modal.classList.remove('open');});})();

function maybeShowUpsell(courseId){fetch('/api/cart/upsell?course_id='+courseId,{headers:{'Accept':'application/json'}}).then(function(r){return r.json();}).then(function(d){if(d.ok){showUpsellModal(d.course);}}).catch(function(){});}
function showUpsellModal(c){var old=document.getElementById('upsell-modal');if(old){old.remove();}
var disc=c.has_discount?'<span style="display:inline-block;background:#dc2626;color:#fff;font-size:11px;font-weight:800;border-radius:99px;padding:3px 10px">'+c.discount_percent+'٪ تخفیف</span>':'';
var price=c.has_discount?'<span style="text-decoration:line-through;color:#9ca3af;font-size:13px;margin-left:8px">'+c.price.toLocaleString('fa-IR')+'</span><span style="color:#dc2626;font-size:19px;font-weight:900">'+c.final_price.toLocaleString('fa-IR')+'</span>':'<span style="color:var(--primary);font-size:19px;font-weight:900">'+(c.final_price?c.final_price.toLocaleString('fa-IR'):'رایگان')+'</span>';
var m=document.createElement('div');m.id='upsell-modal';m.setAttribute('role','dialog');m.setAttribute('aria-modal','true');m.setAttribute('aria-label','پیشنهاد ویژه');
m.style.cssText='position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(10,15,30,.6);backdrop-filter:blur(4px);animation:fadeIn .25s ease';
m.innerHTML='<div style="background:var(--card,#fff);border-radius:20px;max-width:430px;width:100%;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.35);animation:popIn .3s ease;direction:rtl">'
+'<div style="position:relative"><img src="/static/img/'+c.image+'" alt="" style="width:100%;height:170px;object-fit:cover;display:block" onerror="this.style.display=\'none\'"><span style="position:absolute;top:12px;right:12px;background:linear-gradient(90deg,#f59e0b,#dc2626);color:#fff;font-size:12px;font-weight:900;padding:5px 14px;border-radius:99px">🔥 پیشنهاد لحظه‌ای</span><button onclick="closeUpsellModal()" aria-label="بستن" style="position:absolute;top:10px;left:10px;width:32px;height:32px;border-radius:99px;border:none;background:rgba(0,0,0,.45);color:#fff;font-size:15px;cursor:pointer;line-height:1">✕</button></div>'
+'<div style="padding:20px 22px 22px"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">'+disc+'<span style="font-size:11px;color:#6b7280">'+c.category+'</span></div>'
+'<h3 style="font-size:16px;font-weight:900;margin:0 0 4px;line-height:1.7">'+c.title+'</h3>'
+'<div style="margin:12px 0 18px">'+price+'</div>'
+'<div style="display:flex;gap:10px"><a href="/course/'+c.slug+'" class="btn btn-primary" style="flex:1;text-align:center">👀 مشاهده دوره</a><button onclick="closeUpsellModal()" class="btn" style="flex:1;background:var(--bg-2,#f1f5f9)">بعداً</button></div></div></div>';
m.addEventListener('click',function(e){if(e.target===m){closeUpsellModal();}});
document.body.appendChild(m);}
function closeUpsellModal(){var m=document.getElementById('upsell-modal');if(m){m.remove();}}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeUpsellModal();}});
