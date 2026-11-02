/* Elvarion Holdings — app shell: loaders, side drawer, bottom tab bar, gestures */
(function () {
    'use strict';
    var d = document, root = d.documentElement;
    var mq = window.matchMedia ? window.matchMedia('(max-width: 960px)') : { matches: false };

    function ready(fn) { if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', fn); else fn(); }

    /* ---------------------------------------------------------------
       1. Splash loader (once per session) + route progress bar
       --------------------------------------------------------------- */
    var loader = d.getElementById('appLoader');
    function hideSplash() {
        if (!loader) return;
        var el = loader; loader = null;
        if (!root.classList.contains('has-splash')) { el.remove(); return; }
        var wait = Math.max(0, 750 - (window.performance ? performance.now() : 750));
        setTimeout(function () {
            el.classList.add('done');
            try { sessionStorage.setItem('eh_splash', '1'); } catch (e) {}
            setTimeout(function () { el.remove(); }, 650);
        }, wait);
    }
    if (d.readyState === 'complete') hideSplash(); else window.addEventListener('load', hideSplash);
    setTimeout(hideSplash, 4500); // never trap the user behind the splash

    var bar = d.getElementById('navProgress');
    var barFill = bar ? bar.firstElementChild : null;
    var trickle = null;
    function progressStart() {
        if (!bar) return;
        clearInterval(trickle);
        bar.classList.add('on');
        barFill.style.transition = 'none';
        barFill.style.width = '0%';
        void barFill.offsetWidth;
        barFill.style.transition = '';
        var w = 14; barFill.style.width = w + '%';
        trickle = setInterval(function () { w += (92 - w) * 0.1; barFill.style.width = w + '%'; }, 260);
    }
    function progressDone() {
        if (!bar) return;
        clearInterval(trickle);
        barFill.style.width = '100%';
        setTimeout(function () { bar.classList.remove('on'); }, 260);
    }
    window.EHProgress = { start: progressStart, done: progressDone };

    // Internal link clicks start the progress bar
    d.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target.closest ? e.target.closest('a[href]') : null;
        if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
        var href = a.getAttribute('href');
        if (!href || href.charAt(0) === '#' || /^(javascript|mailto|tel):/i.test(href)) return;
        var u; try { u = new URL(a.href, location.href); } catch (err) { return; }
        if (u.origin !== location.origin) return;
        if (u.pathname === location.pathname && u.search === location.search) return; // same page / anchor
        progressStart();
    });

    // Form submissions: spinner on the button + progress bar + double-submit guard
    d.addEventListener('submit', function (e) {
        var f = e.target;
        if (e.defaultPrevented || !f || f.hasAttribute('data-no-loader') || f.target === '_blank') return;
        if (f.__ehBusy) { e.preventDefault(); return; }
        f.__ehBusy = true;
        var b = e.submitter || f.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
        if (b && b.classList) b.classList.add('is-loading');
        progressStart();
        setTimeout(function () { // failsafe if the response never navigates away
            f.__ehBusy = false; if (b && b.classList) b.classList.remove('is-loading'); progressDone();
        }, 20000);
    });

    window.addEventListener('pageshow', function (e) {
        progressDone();
        if (e.persisted) {
            d.querySelectorAll('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); });
            d.querySelectorAll('form').forEach(function (f) { f.__ehBusy = false; });
        }
    });

    /* ---------------------------------------------------------------
       2. Image skeletons — shimmer until each photo has loaded
       --------------------------------------------------------------- */
    ready(function () {
        d.querySelectorAll('.pillar-media, .feature-media, .tc-media, .intro-figure').forEach(function (box) {
            var img = box.querySelector('img');
            if (!img || (img.complete && img.naturalWidth)) return;
            box.classList.add('skel');
            var clear = function () { box.classList.remove('skel'); };
            img.addEventListener('load', clear, { once: true });
            img.addEventListener('error', clear, { once: true });
        });
        // Header shadow + scroll reveal
        var nav = d.getElementById('siteNav');
        window.addEventListener('scroll', function () { if (nav) nav.classList.toggle('scrolled', window.scrollY > 6); }, { passive: true });
        var els = d.querySelectorAll('.reveal');
        if (!('IntersectionObserver' in window)) { els.forEach(function (x) { x.classList.add('in'); }); }
        else {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
            }, { threshold: 0.12 });
            els.forEach(function (x) { io.observe(x); });
        }
    });

    /* ---------------------------------------------------------------
       3. Side drawer
       --------------------------------------------------------------- */
    var drawer = d.getElementById('drawer');
    var backdrop = d.getElementById('drawerBackdrop');
    function openDrawer() {
        if (!drawer) return;
        drawer.classList.add('open'); backdrop.classList.add('open');
        drawer.setAttribute('aria-hidden', 'false'); d.body.classList.add('drawer-lock');
    }
    function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove('open'); backdrop.classList.remove('open');
        drawer.setAttribute('aria-hidden', 'true'); d.body.classList.remove('drawer-lock');
        drawer.style.transform = ''; drawer.style.transition = '';
    }
    d.addEventListener('click', function (e) {
        var t = e.target;
        if (!t.closest) return;
        if (t.closest('[data-open-drawer]')) { openDrawer(); return; }
        if (t.closest('[data-close-drawer]') || t === backdrop) { closeDrawer(); return; }
        if (t.closest('#drawer a[href]')) closeDrawer();
    });
    d.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });
    if (mq.addEventListener) mq.addEventListener('change', function (m) { if (!m.matches) closeDrawer(); });

    // swipe left to dismiss
    (function () {
        if (!drawer) return;
        var sx = 0, sy = 0, dx = 0, tracking = false;
        drawer.addEventListener('touchstart', function (e) {
            var t = e.touches[0]; sx = t.clientX; sy = t.clientY; dx = 0; tracking = true;
        }, { passive: true });
        drawer.addEventListener('touchmove', function (e) {
            if (!tracking) return;
            var t = e.touches[0]; dx = t.clientX - sx;
            if (Math.abs(t.clientY - sy) > Math.abs(dx) && dx > -10) { tracking = false; return; }
            if (dx < 0) { drawer.style.transition = 'none'; drawer.style.transform = 'translateX(' + dx + 'px)'; }
        }, { passive: true });
        drawer.addEventListener('touchend', function () {
            if (!tracking) return; tracking = false;
            drawer.style.transition = '';
            if (dx < -70) closeDrawer(); else drawer.style.transform = '';
        });
    })();

    /* ---------------------------------------------------------------
       4. Bottom tab bar — tab switching (dashboard / admin) + scroll-spy (home)
       --------------------------------------------------------------- */
    ready(function () {
        var tabbar = d.querySelector('.tabbar');
        if (tabbar) d.body.classList.add('has-tabbar');
        if (d.querySelector('.tabs-container')) d.body.classList.add('has-tabs');

        var titleEl = d.getElementById('appTitle');
        function syncTabs(id) {
            d.querySelectorAll('[data-tab]').forEach(function (el) { el.classList.toggle('active', el.getAttribute('data-tab') === id); });
            var inBar = !!(tabbar && tabbar.querySelector('[data-tab="' + id + '"]'));
            var more = tabbar && tabbar.querySelector('[data-more]');
            if (more) more.classList.toggle('active', !inBar);
            var src = d.querySelector('[data-tab-target="' + id + '"]');
            if (titleEl && src) titleEl.textContent = (src.getAttribute('data-title') || src.textContent).replace(/\s+/g, ' ').trim();
        }
        d.addEventListener('click', function (e) {
            var t = e.target.closest ? e.target.closest('[data-tab]') : null;
            if (t) {
                var id = t.getAttribute('data-tab');
                var btn = d.querySelector('[data-tab-target="' + id + '"]');
                if (btn) btn.click();
                closeDrawer();
                window.scrollTo({ top: 0, behavior: 'smooth' });
                return;
            }
            var src = e.target.closest ? e.target.closest('[data-tab-target]') : null;
            if (src) syncTabs(src.getAttribute('data-tab-target'));
        });
        var activePane = d.querySelector('.tab-pane.active') || d.querySelector('.tab-pane');
        if (activePane) syncTabs(activePane.id);

        // home page scroll-spy
        var spy = tabbar ? [].slice.call(tabbar.querySelectorAll('[data-spy]')) : [];
        if (spy.length && location.pathname === '/') {
            var secs = { areas: d.getElementById('areas'), loans: d.getElementById('loans') };
            var ticking = false;
            var paint = function () {
                ticking = false;
                var y = window.scrollY + window.innerHeight * 0.35, cur = 'home';
                ['areas', 'loans'].forEach(function (k) {
                    var el = secs[k]; if (el && el.getBoundingClientRect().top + window.scrollY <= y) cur = k;
                });
                spy.forEach(function (a) { a.classList.toggle('active', a.getAttribute('data-spy') === cur); });
            };
            window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(paint); } }, { passive: true });
            paint();
        } else if (spy.length) {
            spy.forEach(function (a) {
                try { if (new URL(a.href).pathname === location.pathname && !new URL(a.href).hash) a.classList.add('active'); } catch (e) {}
            });
        }

        // hide the tab bar while the on-screen keyboard is open
        var kbTimer;
        d.addEventListener('focusin', function (e) {
            if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && e.target.type !== 'checkbox' && e.target.type !== 'radio' && e.target.type !== 'range') {
                clearTimeout(kbTimer); d.body.classList.add('kb-open');
            }
        });
        d.addEventListener('focusout', function () {
            kbTimer = setTimeout(function () {
                var a = d.activeElement;
                if (!a || !/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) d.body.classList.remove('kb-open');
            }, 120);
        });
    });

    /* ---------------------------------------------------------------
       5. Bottom-sheet modals: drag the handle down to dismiss
       --------------------------------------------------------------- */
    (function () {
        var sy = 0, dy = 0, sheet = null;
        d.addEventListener('touchstart', function (e) {
            if (!mq.matches) return;
            var c = e.target.closest ? e.target.closest('.modal-content') : null;
            if (!c) return;
            var r = c.getBoundingClientRect(), y = e.touches[0].clientY;
            if (y - r.top > 44) return; // only the grab-handle area
            sheet = c; sy = y; dy = 0;
        }, { passive: true });
        d.addEventListener('touchmove', function (e) {
            if (!sheet) return;
            dy = Math.max(0, e.touches[0].clientY - sy);
            sheet.style.transition = 'none'; sheet.style.transform = 'translateY(' + dy + 'px)';
        }, { passive: true });
        d.addEventListener('touchend', function () {
            if (!sheet) return;
            var s = sheet; sheet = null;
            s.style.transition = 'transform .3s cubic-bezier(.2,.7,.2,1)';
            if (dy > 110) {
                s.style.transform = 'translateY(100%)';
                setTimeout(function () {
                    var bd = s.closest('.modal-backdrop');
                    if (bd) bd.classList.remove('open', 'active');
                    s.style.transform = ''; s.style.transition = '';
                }, 280);
            } else { s.style.transform = ''; }
        });
    })();

    /* ---------------------------------------------------------------
       6. Swipeable card rails get position dots
       --------------------------------------------------------------- */
    ready(function () {
        d.querySelectorAll('.carousel-m').forEach(function (rail) {
            var kids = [].slice.call(rail.children);
            if (kids.length < 2) return;
            var dots = d.createElement('div'); dots.className = 'rail-dots';
            kids.forEach(function (_, i) { var s = d.createElement('span'); if (i === 0) s.className = 'on'; dots.appendChild(s); });
            rail.parentNode.insertBefore(dots, rail.nextSibling);
            var raf = false;
            rail.addEventListener('scroll', function () {
                if (raf) return; raf = true;
                requestAnimationFrame(function () {
                    raf = false;
                    var step = kids[1].offsetLeft - kids[0].offsetLeft || 1;
                    var i = Math.max(0, Math.min(kids.length - 1, Math.round(rail.scrollLeft / step)));
                    [].forEach.call(dots.children, function (s, k) { s.className = k === i ? 'on' : ''; });
                });
            }, { passive: true });
        });
    });
})();
