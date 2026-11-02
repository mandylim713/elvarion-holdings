/* Elvarion Holdings — Admin Console */
(function () {
  'use strict';
  var d = document, body = d.body;
  function $(s, c) { return (c || d).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); }

  /* ---------- boot loader ---------- */
  var boot = $('#boot');
  function hideBoot() { if (boot) { boot.classList.add('done'); var b = boot; boot = null; setTimeout(function () { b.remove(); }, 600); } }
  var seen = false; try { seen = sessionStorage.getItem('eh_adm') === '1'; sessionStorage.setItem('eh_adm', '1'); } catch (e) {}
  if (seen) hideBoot(); else window.addEventListener('load', function () { setTimeout(hideBoot, 450); });
  setTimeout(hideBoot, 3500);

  /* ---------- top progress bar ---------- */
  var bar = $('#admLoad'), tk;
  function barStart() { if (!bar) return; bar.style.opacity = 1; bar.style.width = '12%'; var w = 12; clearInterval(tk); tk = setInterval(function () { w += (90 - w) * .12; bar.style.width = w + '%'; }, 250); }
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || e.metaKey || e.ctrlKey) return;
    var h = a.getAttribute('href'); if (h && h.charAt(0) !== '#' && !/^(javascript|mailto|tel)/.test(h)) barStart();
  });

  /* ---------- view routing (hash) ---------- */
  var views = $$('.adm-view'), navs = $$('[data-view]'), titleEl = $('#admTitle'), search = $('#admSearch');
  var current = 'overview';
  function show(name, push) {
    if (!$('#v-' + name)) name = 'overview';
    current = name;
    views.forEach(function (v) { v.classList.toggle('active', v.id === 'v-' + name); });
    navs.forEach(function (n) { n.classList.toggle('active', n.getAttribute('data-view') === name); });
    var v = $('#v-' + name);
    titleEl.innerHTML = v.getAttribute('data-title') || 'Overview';
    d.title = (v.getAttribute('data-title') || 'Admin').replace(/&amp;/g, '&') + ' | Elvarion Admin';
    if (search) { search.value = ''; search.placeholder = v.getAttribute('data-search') || 'Search this page…'; }
    applyFilters();
    closeSide();
    body.classList.remove('search-open');
    if (push !== false) { try { history.replaceState(null, '', '#' + name); } catch (e) { location.hash = name; } }
    window.scrollTo(0, 0);
  }
  d.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-view],[data-go]');
    if (!t) return;
    var name = t.getAttribute('data-view') || t.getAttribute('data-go');
    show(name);
  });
  window.addEventListener('hashchange', function () { show(location.hash.replace('#', '') || 'overview', false); });

  /* ---------- filters + search ---------- */
  function applyFilters() {
    var v = $('#v-' + current); if (!v) return;
    var chip = $('[data-chips] .chip.active', v), f = chip ? chip.getAttribute('data-f') : 'all';
    var q = (search && search.value || '').trim().toLowerCase();
    $$('table.tbl', v).forEach(function (t) {
      var shown = 0, rows = $$('tbody tr', t);
      rows.forEach(function (tr) {
        var st = (tr.getAttribute('data-status') || '').split(' ');
        var okF = f === 'all' || !tr.hasAttribute('data-status') || st.indexOf(f) > -1;
        var okQ = !q || tr.textContent.toLowerCase().indexOf(q) > -1;
        var show = okF && okQ; tr.classList.toggle('hide', !show); if (show) shown++;
      });
      var nm = t.parentNode.querySelector('.no-match');
      if (nm) nm.style.display = (rows.length && !shown) ? 'block' : 'none';
    });
  }
  d.addEventListener('click', function (e) {
    var c = e.target.closest && e.target.closest('[data-chips] .chip'); if (!c) return;
    $$('.chip', c.parentNode).forEach(function (x) { x.classList.toggle('active', x === c); });
    applyFilters();
  });
  if (search) search.addEventListener('input', applyFilters);
  var st = $('#searchToggle');
  if (st) st.addEventListener('click', function () { body.classList.toggle('search-open'); if (body.classList.contains('search-open')) setTimeout(function () { search.focus(); }, 50); });

  /* ---------- side drawer (mobile) ---------- */
  function openSide() { body.classList.add('side-open'); }
  function closeSide() { body.classList.remove('side-open'); }
  d.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-open-side],[data-close-side]'); if (!t) return;
    if (t.hasAttribute('data-open-side')) openSide(); else closeSide();
  });
  var sx = null, side = $('#admSide');
  side.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
  side.addEventListener('touchend', function (e) { if (sx !== null && e.changedTouches[0].clientX - sx < -60) closeSide(); sx = null; }, { passive: true });
  // swipe from left edge opens it
  var ex = null;
  d.addEventListener('touchstart', function (e) { var x = e.touches[0].clientX; ex = x < 18 ? x : null; }, { passive: true });
  d.addEventListener('touchend', function (e) { if (ex !== null && e.changedTouches[0].clientX - ex > 70 && window.innerWidth <= 960) openSide(); ex = null; }, { passive: true });

  /* ---------- modals ---------- */
  function openM(id) { var m = $('#' + id); if (!m) return; m.classList.add('open'); body.classList.add('modal-open'); var f = $('input:not([type=hidden]),select,textarea', m); if (f && window.innerWidth > 960) setTimeout(function () { f.focus(); }, 60); }
  function closeM(m) { if (m) m.classList.remove('open'); if (!$('.modal.open')) body.classList.remove('modal-open'); }
  d.addEventListener('click', function (e) {
    var c = e.target.closest && e.target.closest('[data-close]');
    if (c) { closeM(c.closest('.modal')); return; }
    if (e.target.classList && e.target.classList.contains('modal')) closeM(e.target);
  });
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape') { $$('.modal.open').forEach(closeM); closeSide(); } });

  // drag-to-dismiss on sheets (mobile)
  $$('.sheet').forEach(function (sh) {
    var y0 = null, dy = 0;
    sh.addEventListener('touchstart', function (e) { if (sh.scrollTop <= 0 && e.target.closest('.grabber,.sheet-head')) { y0 = e.touches[0].clientY; dy = 0; sh.style.transition = 'none'; } }, { passive: true });
    sh.addEventListener('touchmove', function (e) { if (y0 === null) return; dy = Math.max(0, e.touches[0].clientY - y0); sh.style.transform = 'translateY(' + dy + 'px)'; }, { passive: true });
    sh.addEventListener('touchend', function () {
      if (y0 === null) return; sh.style.transition = 'transform .25s ease';
      if (dy > 110) { sh.style.transform = 'translateY(100%)'; setTimeout(function () { closeM(sh.closest('.modal')); sh.style.transform = ''; sh.style.transition = ''; }, 220); }
      else { sh.style.transform = ''; setTimeout(function () { sh.style.transition = ''; }, 260); }
      y0 = null;
    });
  });

  /* ---------- confirm dialog for forms ---------- */
  var cfForm = null;
  d.addEventListener('submit', function (e) {
    var f = e.target;
    if (f.hasAttribute('data-confirm') && !f.__ok) {
      e.preventDefault(); cfForm = f;
      $('#cf-title').textContent = f.hasAttribute('data-danger') ? 'Please confirm' : 'Confirm action';
      $('#cf-msg').textContent = f.getAttribute('data-confirm');
      var ok = $('#cf-ok'); ok.innerHTML = f.getAttribute('data-ok') || 'Confirm';
      ok.className = 'btn btn-lg ' + (f.hasAttribute('data-danger') ? 'btn-bad' : 'btn-ok');
      var nn = f.getAttribute('data-note'), wrap = $('#cf-note-wrap');
      wrap.style.display = nn ? 'block' : 'none'; $('#cf-note').value = ''; $('#cf-note').placeholder = f.getAttribute('data-note-ph') || '';
      openM('m-confirm'); return;
    }
    var b = $('button[type=submit],button:not([type])', f);
    if (b) { b.classList.add('is-loading'); }
    barStart();
  });
  $('#cf-ok').addEventListener('click', function () {
    if (!cfForm) return;
    var nn = cfForm.getAttribute('data-note');
    if (nn) { var i = cfForm.querySelector('input[name="' + nn + '"]'); if (!i) { i = d.createElement('input'); i.type = 'hidden'; i.name = nn; cfForm.appendChild(i); } i.value = $('#cf-note').value; }
    this.classList.add('is-loading'); cfForm.__ok = true;
    if (cfForm.requestSubmit) cfForm.requestSubmit(); else cfForm.submit();
  });

  /* ---------- plan / tier / wallet modals ---------- */
  function set(id, v) { var e = $('#' + id); if (e) e.value = v; }
  d.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-plan-new],[data-plan-edit],[data-asset-new],[data-asset-edit],[data-tier-new],[data-tier-edit],[data-adjust]'); if (!t) return;
    if (t.hasAttribute('data-plan-new')) { $('#pl-h').textContent = 'New plan'; set('pl-id', ''); set('pl-title', ''); set('pl-roi', ''); set('pl-unit', 'monthly'); set('pl-count', 6); set('pl-min', 5000); set('pl-max', 250000); openM('m-plan'); }
    else if (t.hasAttribute('data-plan-edit')) { $('#pl-h').textContent = 'Edit plan'; set('pl-id', t.dataset.id); set('pl-title', t.dataset.title); set('pl-area', t.dataset.area); set('pl-roi', t.dataset.roi); set('pl-unit', t.dataset.unit); set('pl-count', t.dataset.count); set('pl-min', t.dataset.min); set('pl-max', t.dataset.max); openM('m-plan'); }
    else if (t.hasAttribute('data-asset-new')) { $('#as-h').textContent = 'Add asset'; set('as-id', ''); set('as-symbol', ''); $('#as-symbol').readOnly = false; set('as-name', ''); set('as-cat', 'crypto'); set('as-price', ''); set('as-vol', 1); set('as-on', '1'); openM('m-asset'); }
    else if (t.hasAttribute('data-asset-edit')) { $('#as-h').textContent = 'Edit ' + t.dataset.symbol; set('as-id', t.dataset.id); set('as-symbol', t.dataset.symbol); $('#as-symbol').readOnly = true; set('as-name', t.dataset.name); set('as-cat', t.dataset.cat); set('as-price', t.dataset.price); set('as-vol', t.dataset.vol); set('as-on', t.dataset.on); openM('m-asset'); }
    else if (t.hasAttribute('data-tier-new')) { $('#ti-h').textContent = 'New loan tier'; set('ti-id', ''); set('ti-name', ''); set('ti-badge', 'TIER'); set('ti-dep', ''); set('ti-lmin', ''); set('ti-lmax', ''); openM('m-tier'); }
    else if (t.hasAttribute('data-tier-edit')) { $('#ti-h').textContent = 'Edit loan tier'; set('ti-id', t.dataset.id); set('ti-name', t.dataset.name); set('ti-badge', t.dataset.badge); set('ti-dep', t.dataset.dep); set('ti-lmin', t.dataset.lmin); set('ti-lmax', t.dataset.lmax); openM('m-tier'); }
    else if (t.hasAttribute('data-adjust')) { $('#adj-h').textContent = 'Adjust wallet'; $('#adj-p').textContent = t.dataset.name + ' · balance $' + t.dataset.bal; $('#adj-form').setAttribute('data-uid', t.dataset.uid); set('adj-amt', ''); openM('m-adjust'); }
  });
  $$('#adj-form button[data-act]').forEach(function (b) {
    b.addEventListener('click', function () { var f = $('#adj-form'); f.action = '/management/user/' + f.getAttribute('data-uid') + '/' + b.getAttribute('data-act') + '/'; });
  });

  /* ---------- toasts ---------- */
  $$('.toast').forEach(function (t, i) { setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 320); }, 5200 + i * 600); t.addEventListener('click', function () { t.remove(); }); });

  /* ---------- keyboard: hide tab bar while typing ---------- */
  d.addEventListener('focusin', function (e) { if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && window.innerWidth <= 960) body.classList.add('kb-open'); });
  d.addEventListener('focusout', function () { setTimeout(function () { var a = d.activeElement; if (!a || !/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) body.classList.remove('kb-open'); }, 80); });

  /* ---------- go ---------- */
  show((location.hash || '#overview').replace('#', ''), false);
  window.addEventListener('pageshow', function () { if (bar) { bar.style.width = '0'; bar.style.opacity = 0; clearInterval(tk); } $$('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); }); });
})();
