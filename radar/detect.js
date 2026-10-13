// Runs inside the publisher page (Playwright page.evaluate). Finds ad slots WITHOUT clicking anything.
// Input: cfg = {networks: {key: {hosts, selectors}}, labels: [...], notAds: [...], maxSlots}
// Output: {page: {...}, slots: [...]}
(cfg) => {
  const host = location.hostname.replace(/^www\./, '');
  const parts = host.split('.');
  const root = (parts.length > 2 && parts[parts.length - 1] === 'ir' && ['co', 'ac', 'org', 'gov', 'com', 'net', 'id', 'sch'].includes(parts[parts.length - 2]))
    ? parts.slice(-3).join('.') : parts.slice(-2).join('.');
  const vw = window.innerWidth, vh = window.innerHeight;
  const pageH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
  const sameSite = (h) => { if (!h) return true; h = h.replace(/^www\./, ''); return h === root || h.endsWith('.' + root); };
  const hostOf = (u) => { try { return new URL(u, location.href).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
  const matchHost = (h, list) => list.some(d => h === d || h.endsWith('.' + d));
  const netOfHost = (h) => {
    for (const [k, n] of Object.entries(cfg.networks)) if (matchHost(h, n.hosts || [])) return k;
    return null;
  };
  const isNotAd = (h) => matchHost(h, cfg.notAds || []);
  const labelRe = new RegExp('^\\s*(' + cfg.labels.map(l => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\s*[:：]?\\s*$', 'i');

  const visRect = (el) => {
    // union of the element and its media children (anchors are often thin inline wrappers around a bigger image)
    const r = el.getBoundingClientRect();
    let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
    if (r.width >= 5 && r.height >= 5) { x1 = r.left; y1 = r.top; x2 = r.right; y2 = r.bottom; }
    el.querySelectorAll('img,video,iframe,picture,canvas').forEach(c => {
      const q = c.getBoundingClientRect();
      if (q.width > 5 && q.height > 5) { x1 = Math.min(x1, q.left); y1 = Math.min(y1, q.top); x2 = Math.max(x2, q.right); y2 = Math.max(y2, q.bottom); }
    });
    if (!isFinite(x1)) return { x: Math.round(r.left), y: Math.round(r.top + scrollY), w: 0, h: 0 };
    return { x: Math.round(x1), y: Math.round(y1 + scrollY), w: Math.round(x2 - x1), h: Math.round(y2 - y1) };
  };
  const posInfo = (el) => {
    let fixed = false, sticky = false, z = 0;
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.position === 'fixed') fixed = true;
      if (s.position === 'sticky') sticky = true;
      const zi = parseInt(s.zIndex); if (!isNaN(zi)) z = Math.max(z, zi);
    }
    return { fixed, sticky, z };
  };
  const ctx = (el) => ({
    inArticle: !!el.closest('article p, .post-content, .article-body, .entry-content, [itemprop="articleBody"], .content-body, .news-body, .story-body') || !!(el.previousElementSibling && el.previousElementSibling.tagName === 'P' && el.nextElementSibling && el.nextElementSibling.tagName === 'P'),
    inAside: !!el.closest('aside, .sidebar, [class*="sidebar"], [id*="sidebar"]'),
    inHeader: !!el.closest('header, [class*="header"]'),
    inFooter: !!el.closest('footer, [class*="footer"]'),
    inList: !!el.closest('ul li, ol li, [class*="feed"], [class*="list"]'),
  });
  const textOf = (el) => (el.getAttribute('aria-label') || el.querySelector('[aria-label]')?.getAttribute('aria-label') || el.querySelector('img[alt]')?.alt || el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 220);
  const nearLabel = (el) => {
    const scope = el.parentElement?.parentElement || el.parentElement;
    if (!scope) return '';
    for (const n of scope.querySelectorAll('span,div,small,p,b,strong,i,em')) {
      if (n.children.length === 0 && labelRe.test(n.textContent || '')) return n.textContent.trim();
    }
    return '';
  };
  const creativesOf = (el, sid) => {
    const out = [];
    // native widgets: each recommended item is its own creative (outermost item nodes only)
    let items = [...el.querySelectorAll('article, [class*="item"]:not([class*="item_"]):not([class*="item-"]), [class*="card"], li')]
      .filter(x => x.getBoundingClientRect().width > 40 && x.getBoundingClientRect().height > 30);
    items = items.filter(x => !items.some(y => y !== x && y.contains(x)));
    const units = items.length >= 2 ? items.slice(0, 8) : [el];
    let n = 0;
    for (const u of units) {
      if (units.length >= 2) u.setAttribute('data-radar-cr', sid + '-c' + (n++));
      const a = u.matches('a[href]') ? u : u.querySelector('a[href]');
      const href = a ? a.href : '';
      const img = u.querySelector('img');
      out.push({
        title: textOf(u),
        img: img ? (img.currentSrc || img.src || '').slice(0, 300) : '',
        href: (href && !href.endsWith('#') && !href.startsWith('javascript')) ? href.slice(0, 600) : '',
        cta: (u.querySelector('button, [class*="cta"]')?.innerText || '').trim().slice(0, 40),
        price: ((u.innerText || '').match(/[\d۰-۹٬,\.]{4,}\s*(تومان|ریال)/) || [''])[0],
        discount: ((u.innerText || '').match(/[\d۰-۹]{1,2}\s*[%٪]/) || [''])[0],
        cr: units.length >= 2 ? u.getAttribute('data-radar-cr') : '',
      });
    }
    return out.filter(c => c.title || c.img || c.href);
  };

  const found = new Map();  // element -> slot
  const add = (el, kind, network, extra = {}) => {
    if (!el || found.has(el) || /^(STYLE|SCRIPT|LINK|META|NOSCRIPT|TEMPLATE)$/.test(el.tagName)) return;
    if (/-style$/.test(el.id || '')) return;
    // keep the outermost ad container only
    for (const [other] of found) { if (other.contains(el)) return; }
    for (const [other] of [...found]) { if (el.contains(other)) found.delete(other); }
    found.set(el, { kind, network, ...extra });
  };

  // A) network containers
  for (const [k, n] of Object.entries(cfg.networks)) {
    for (const sel of (n.selectors || [])) {
      try { document.querySelectorAll(sel).forEach(el => add(el, 'network_widget', k)); } catch (e) { }
    }
  }
  // B) third-party iframes of meaningful size
  document.querySelectorAll('iframe').forEach(f => {
    const h = hostOf(f.src || '');
    const r = f.getBoundingClientRect();
    if (r.width < 60 || r.height < 40) return;
    if (!h || sameSite(h) || isNotAd(h)) return;
    if (/youtube|aparat|google\.com\/maps|player|embed/.test(f.src) && !netOfHost(h)) return;
    add(f.parentElement && f.parentElement.children.length === 1 ? f.parentElement : f, 'iframe', netOfHost(h) || ('unknown:' + h), { iframeHost: h });
  });
  // C) direct-sold banners: sponsored links / external links with tracking params around an image
  document.querySelectorAll('a[href]').forEach(a => {
    const h = hostOf(a.href);
    if (!h || sameSite(h) || isNotAd(h)) return;
    const rel = (a.rel || '').toLowerCase();
    const hasMedia = !!a.querySelector('img,video,picture,canvas') || /background-image/.test(a.getAttribute('style') || '');
    let tracked = false;
    try { const u = new URL(a.href); tracked = [...u.searchParams.keys()].some(k => /^(utm_|mtm_)/.test(k)); } catch (e) { }
    const sponsored = rel.includes('sponsored');
    const net = netOfHost(h);
    if (sponsored || net || (hasMedia && tracked) || (hasMedia && nearLabel(a))) {
      add(a, sponsored ? 'sponsored_link' : (net ? 'network_link' : 'direct_banner'), net || 'direct', { linkHost: h, tracked });
    }
  });
  // D) explicit "تبلیغات" labels next to a container with media
  document.querySelectorAll('span,div,small,p,b,strong').forEach(n => {
    if (n.children.length || !labelRe.test(n.textContent || '')) return;
    const box = n.closest('section, aside, div');
    if (!box || box === document.body) return;
    const media = box.querySelector('img,iframe,video');
    const r = box.getBoundingClientRect();
    if (!media || r.height > vh * 1.5 || r.width < 50) return;
    add(box, 'labelled_box', 'direct', { label: n.textContent.trim() });
  });
  // E) reportage / sponsored content markers
  const reportage = [...document.querySelectorAll('a[href]')].filter(a => /رپورتاژ|رپرتاژ|reportage|sponsored-content|advertorial/i.test(a.href + ' ' + (a.className || ''))).slice(0, 10).map(a => ({ href: a.href.slice(0, 300), title: (a.innerText || '').trim().slice(0, 150) }));
  // F) push-notification / popups
  const pushPrompt = !!document.querySelector('[id*="najva"],[class*="najva"],[id*="pushe"],[class*="push-prompt"],[class*="onesignal"]');

  // build slots
  const slots = [];
  let i = 0;
  for (const [el, meta] of found) {
    if (slots.length >= (cfg.maxSlots || 60)) break;
    const r = visRect(el);
    const p = posInfo(el);
    // creative size: union of media children (container divs are often full-width)
    let mx1 = Infinity, my1 = Infinity, mx2 = -Infinity, my2 = -Infinity;
    (el.matches('iframe,img,video') ? [el] : [...el.querySelectorAll('iframe,img,video,canvas')]).forEach(c => {
      const q = c.getBoundingClientRect(); if (q.width > 20 && q.height > 15) { mx1 = Math.min(mx1, q.left); my1 = Math.min(my1, q.top); mx2 = Math.max(mx2, q.right); my2 = Math.max(my2, q.bottom); }
    });
    const media = isFinite(mx1) ? { w: Math.round(mx2 - mx1), h: Math.round(my2 - my1) } : null;
    const vr = el.getBoundingClientRect();
    if (media && media.w < vr.width * 0.8) {
      const kids = [...el.querySelectorAll('iframe,img,video,canvas')].filter(c => c.getBoundingClientRect().width > 20);
      if (kids.length === 1) kids[0].setAttribute('data-radar-media', 'radar-' + i);
    }
    const iframes = [...(el.matches('iframe') ? [el] : el.querySelectorAll('iframe'))].map(f => f.src).filter(Boolean).slice(0, 3);
    const empty = r.w < 20 || r.h < 20;
    const id = 'radar-' + (i++);
    el.setAttribute('data-radar-id', id);
    slots.push({
      id, ...meta, rect: r, media, vtop: Math.round(vr.top), vbottom: Math.round(vr.bottom), iframes, ...p, ...ctx(el), empty,
      label: meta.label || nearLabel(el),
      creatives: creativesOf(el, id),
      domId: (el.id || '').slice(0, 60), domClass: ((el.className && el.className.baseVal === undefined ? el.className : '') + '').slice(0, 80),
      hasVideo: !!el.querySelector('video') || /video|tvp/.test(el.innerHTML.slice(0, 3000)),
    });
  }
  return {
    page: { url: location.href, title: document.title.slice(0, 200), vw, vh, pageH, host, reportage, pushPrompt,
            extDomains: [...new Set([...document.querySelectorAll('a[href]:not([rel*="sponsored"])')].map(a => hostOf(a.href)).filter(h => h && !sameSite(h) && !isNotAd(h) && !netOfHost(h)))].slice(0, 60),
            articleLinks: [...document.querySelectorAll('a[href]')].map(a => a.href).filter(u => sameSite(hostOf(u)) && /\/(news|article|post|blog|mag|\d{3,})/i.test(u) && u.split('/').length > 4).slice(0, 15) },
    slots,
  };
}
