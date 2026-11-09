/* Elvarion Holdings — client app shell */
(function () {
  'use strict';
  var d = document, body = d.body;
  function $(s, c) { return (c || d).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); }

  // boot loader (once per session)
  var boot = $('#shBoot'), seen = false;
  try { seen = sessionStorage.getItem('eh_shell') === '1'; sessionStorage.setItem('eh_shell', '1'); } catch (e) {}
  function hideBoot() { if (!boot) return; var b = boot; boot = null; b.classList.add('done'); setTimeout(function () { b.remove(); }, 600); }
  if (seen) hideBoot(); else window.addEventListener('load', function () { setTimeout(hideBoot, 450); });
  setTimeout(hideBoot, 3500);

  // progress bar
  var bar = $('#shLoad'), tk;
  function start() { if (!bar) return; bar.style.opacity = 1; bar.style.width = '12%'; var w = 12; clearInterval(tk); tk = setInterval(function () { w += (90 - w) * .12; bar.style.width = w + '%'; }, 250); }
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || e.metaKey || e.ctrlKey) return;
    var h = a.getAttribute('href'); if (h && h.charAt(0) !== '#' && !/^(javascript|mailto|tel)/.test(h)) start();
  });
  d.addEventListener('submit', function (e) {
    var b = e.target.querySelector && e.target.querySelector('button[type=submit],button:not([type])');
    if (b) b.classList.add('is-loading'); start();
  });
  window.addEventListener('pageshow', function () { if (bar) { bar.style.width = '0'; bar.style.opacity = 0; clearInterval(tk); } $$('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); }); });

  // sidebar open/close (mobile)
  function openSide() { body.classList.add('sh-open'); }
  function closeSide() { body.classList.remove('sh-open'); }
  d.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-open-side],[data-close-side]'); if (!t) return;
    if (t.hasAttribute('data-open-side')) openSide(); else closeSide();
  });
  var side = $('#shSide'), sx = null, ex = null;
  side.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
  side.addEventListener('touchend', function (e) { if (sx !== null && e.changedTouches[0].clientX - sx < -60) closeSide(); sx = null; }, { passive: true });
  d.addEventListener('touchstart', function (e) { var x = e.touches[0].clientX; ex = x < 18 ? x : null; }, { passive: true });
  d.addEventListener('touchend', function (e) { if (ex !== null && e.changedTouches[0].clientX - ex > 70 && window.innerWidth <= 960) openSide(); ex = null; }, { passive: true });
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSide(); });

  // sidebar <-> dashboard tabs
  var titleEl = $('#shTitle');
  function sync(tabId) {
    body.setAttribute('data-tab', tabId);
    var item = null;
    $$('.sh-item[data-tab], .sh-b[data-tab]').forEach(function (b) { var on = b.getAttribute('data-tab') === tabId; b.classList.toggle('active', on); if (on && b.classList.contains('sh-item')) item = b; });
    if (item && titleEl) { titleEl.textContent = item.getAttribute('data-title') || item.textContent.trim(); d.title = titleEl.textContent + ' | Elvarion'; }
  }
  d.addEventListener('click', function (e) {
    var s = e.target.closest && e.target.closest('.sh-item[data-tab], .sh-b[data-tab]');
    if (s) { if (typeof window.switchDashboardTab === 'function') window.switchDashboardTab(s.getAttribute('data-tab')); closeSide(); window.scrollTo(0, 0); return; }
    var t = e.target.closest && e.target.closest('[data-tab-target]');
    if (t) sync(t.getAttribute('data-tab-target'));
  });
  var first = $('.tab-pane.active'); if (first) sync(first.id);
  window.addEventListener('load', function () { var h = location.hash; if (h && $(h) && $(h).classList.contains('tab-pane') && typeof window.switchDashboardTab === 'function') window.switchDashboardTab(h.slice(1)); });
})();
