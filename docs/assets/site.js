(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // theme toggle (light <-> dark; remembered when storage is available)
  const themeBtn = $('.theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', () => {
    const root = document.documentElement;
    const cur = root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('hb-theme', next); } catch (_) {}
  });

  // language switch: remember the choice, keep the reader's place on the page
  $$('a[data-lang-to]').forEach(a => a.addEventListener('click', () => {
    try { localStorage.setItem('hb-lang', a.dataset.langTo); } catch (_) {}
    if (location.hash) a.href = a.href.split('#')[0] + location.hash;
  }));

  // mobile nav
  const navBtn = $('.nav-toggle'), nav = $('#site-nav');
  if (navBtn) navBtn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    navBtn.setAttribute('aria-expanded', open);
  });

  // sortable tables
  $$('table.lb').forEach(table => {
    const heads = $$('th', table.tHead);
    heads.forEach((th, i) => {
      if (!th.dataset.sort) return;
      th.tabIndex = 0;
      const go = () => {
        const asc = th.getAttribute('aria-sort') === 'descending';
        heads.forEach(h => h.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
        const rows = $$('tbody tr', table);
        const val = r => r.children[i].dataset.v;
        rows.sort((a, b) => {
          let x = val(a), y = val(b);
          if (th.dataset.sort === 'num') { x = +x; y = +y; return asc ? x - y : y - x; }
          return asc ? String(y).localeCompare(x) : String(x).localeCompare(y);
        });
        // rank and text columns read naturally ascending first
        if ((th.dataset.sort === 'text' || th.textContent.trim() === '#') && !asc) rows.reverse();
        rows.forEach(r => table.tBodies[0].appendChild(r));
      };
      th.addEventListener('click', go);
      th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
  });

  // leaderboard filters
  $$('.controls[data-for]').forEach(ctl => {
    const table = document.getElementById(ctl.dataset.for);
    let kind = 'all', lab = '';
    const apply = () => $$('tbody tr', table).forEach(r => {
      r.hidden = (kind !== 'all' && r.dataset.kind !== kind) || (lab && r.dataset.lab !== lab);
    });
    $$('button[data-kind]', ctl).forEach(b => b.addEventListener('click', () => {
      kind = b.dataset.kind;
      $$('button[data-kind]', ctl).forEach(x => x.setAttribute('aria-pressed', x === b));
      apply();
    }));
    const sel = $('select[data-lab-filter]', ctl);
    if (sel) sel.addEventListener('change', () => { lab = sel.value; apply(); });
  });

  // findings filter
  const grid = $('#findings');
  if (grid) $$('button[data-study]').forEach(b => b.addEventListener('click', () => {
    $$('button[data-study]').forEach(x => x.setAttribute('aria-pressed', x === b));
    $$('.f-row', grid).forEach(c => {
      c.hidden = !!b.dataset.study && c.dataset.study !== b.dataset.study;
    });
  }));

  // radar: toggle lab shapes, overlay one model
  const radar = $('svg.radar');
  if (radar) {
    $$('.key-btn').forEach(b => b.addEventListener('click', () => {
      const on = b.getAttribute('aria-pressed') !== 'true';
      b.setAttribute('aria-pressed', on);
      const g = radar.querySelector(`g.shape[data-series="${b.dataset.series}"]`);
      if (g) g.hidden = !on;
    }));
    const pick = $('select[data-overlay]');
    if (pick) pick.addEventListener('change', () => {
      $$('g.overlay', radar).forEach(g => { g.hidden = g.dataset.model !== pick.value; });
      radar.classList.toggle('dim', !!pick.value);
    });
  }

  // tooltips on [data-tip]
  const tip = $('.tip');
  const show = (el, x, y) => {
    tip.textContent = el.dataset.tip;
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, x + 14)) + 'px';
    tip.style.top = Math.max(8, y - h - 12) + 'px';
  };
  document.addEventListener('mousemove', e => {
    const el = e.target.closest('[data-tip]');
    if (el) show(el, e.clientX, e.clientY); else tip.hidden = true;
  });
  document.addEventListener('focusin', e => {
    const el = e.target.closest('[data-tip]');
    if (!el) return;
    const r = el.getBoundingClientRect();
    show(el, r.left + r.width / 2, r.top);
  });
  document.addEventListener('focusout', () => { tip.hidden = true; });
  addEventListener('scroll', () => { tip.hidden = true; }, { passive: true });

  // copy buttons
  $$('button[data-copy]').forEach(b => b.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(document.getElementById(b.dataset.copy).textContent);
      b.textContent = 'Copied';
      setTimeout(() => { b.textContent = 'Copy'; }, 1500);
    } catch (_) { b.textContent = 'Select and copy'; }
  }));
})();
