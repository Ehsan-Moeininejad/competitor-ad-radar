/* Competitor Ad Radar — report app (vanilla JS, data embedded as window.DATA / window.IMG) */
(function () {
  const D = window.DATA, FA = D.fa, IMG = window.IMG || {};
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pct = (x, d = 0) => (x == null ? '—' : (Math.round((x || 0) * 100 * 10 ** d) / 10 ** d) + '%');
  const fa = (map, k) => (FA[map] && FA[map][k]) || k || '—';
  const color = b => (D.colors && D.colors[b]) || '#898781';
  const img = k => (k && IMG[k]) ? 'data:image/jpeg;base64,' + IMG[k] : '';
  const ST = { good: '#0ca30c', warn: '#fab219', serious: '#ec835a', crit: '#d03b3b' };
  const stClass = (v, inv) => { v = inv ? 100 - v : v; return v >= 70 ? 'crit' : v >= 50 ? 'serious' : v >= 30 ? 'warn' : 'good'; };
  const meter = (v, inv, label) => v == null ? '—' : `<div class="meter" title="${esc(label || '')}: ${v} از 100"><div class="mbar"><i style="width:${Math.max(2, v)}%;background:${ST[stClass(v, inv)]}"></i></div><b>${v}</b></div>`;
  const chip = (t, n) => `<span class="chip">${esc(t)}${n != null ? ` <small>${n}</small>` : ''}</span>`;
  const chips = (obj, map, k = 4) => Object.entries(obj || {}).slice(0, k).map(([a, n]) => chip(fa(map, a), n)).join('') || '<span class="muted">—</span>';
  const brandCell = b => `<span style="display:inline-flex;align-items:center"><i class="dot" style="background:${color(b)}"></i>${esc(b)}</span>`;
  const empty = t => `<div class="empty">${esc(t)}</div>`;

  // ---------------- global filters
  const F = { cat: '', dev: '', lvl: 'rivals', q: '' };
  const rowsF = () => D.rows.filter(r => (!F.cat || r.c === F.cat) && (!F.dev || r.d === F.dev) &&
    (F.lvl === 'all' || (F.lvl === 'rivals' ? ['core', 'vertical', 'own'].includes(r.l) : r.l === F.lvl)));

  function renderFilters() {
    const cats = Object.entries(D.categories || {});
    $('#filters').innerHTML = `
      <label>دسته <select id="f-cat"><option value="">همهٔ دسته‌ها</option>${cats.map(([k, c]) => `<option value="${k}">${esc(c.fa)}</option>`).join('')}</select></label>
      <label>دستگاه <select id="f-dev"><option value="">موبایل و دسکتاپ</option><option value="mobile">موبایل</option><option value="desktop">دسکتاپ</option></select></label>
      <label>تبلیغ‌دهنده <select id="f-lvl"><option value="rivals">رقبا + دیجی‌کالا</option><option value="core">فقط رقبای مستقیم</option><option value="vertical">فقط رقبای ورتیکالی</option><option value="own">فقط گروه دیجی‌کالا</option><option value="all">همهٔ تبلیغ‌دهنده‌ها</option></select></label>
      <span class="muted small" id="f-count"></span>`;
    $('#f-cat').value = F.cat; $('#f-dev').value = F.dev; $('#f-lvl').value = F.lvl;
    ['cat', 'dev', 'lvl'].forEach(k => $('#f-' + k).onchange = e => { F[k] = e.target.value; renderAll(); });
  }

  // ---------------- small charts
  function hbars(items, colorOf, fmt = v => pct(v, 1)) {
    if (!items.length) return empty('داده‌ای برای این فیلتر نیست.');
    const mx = Math.max(...items.map(x => x[1])) || 1;
    return `<div class="hbars">${items.map(([k, v], i) => `<div class="hrow" title="${esc(k)}: ${fmt(v)}"><span class="hl">${esc(k)}</span><span class="ht"><i style="width:${Math.max(1.5, 100 * v / mx)}%;background:${colorOf ? colorOf(k, i) : '#3987e5'}"></i></span><span class="hv">${fmt(v)}</span></div>`).join('')}</div>`;
  }
  function sovFromRows(rows) {
    const w = {}; let tot = 0;
    rows.forEach(r => { if (!['core', 'vertical', 'own'].includes(r.l)) return; w[r.b] = (w[r.b] || 0) + r.wt; tot += r.wt; });
    return Object.entries(w).map(([b, v]) => [b, v / (tot || 1)]).sort((a, b) => b[1] - a[1]);
  }

  // ---------------- 1. overview
  function tabOverview() {
    const I = D.I || {}, k = D.kpis;
    const rows = rowsF();
    const sov = sovFromRows(rows).slice(0, 10);
    const tiles = k.map(t => `<div class="kpi" title="${esc(t.help || '')}"><span>${esc(t.label)}</span><b>${esc(t.value)}</b><small>${t.delta ? `<bdi class="${t.delta_cls}" dir="ltr">${esc(t.delta)}</bdi> · ` : ''}${esc(t.sub || '')}</small></div>`).join('');
    const lv = { high: ['▲', 'crit'], mid: ['●', 'serious'], low: ['○', 'warn'] };
    const alerts = (D.alerts || []).map(a => `<li><span class="ic" style="color:${ST[lv[a.level][1]]}" aria-label="${a.level}">${lv[a.level][0]}</span><span>${esc(a.text)}</span></li>`).join('') || '<li class="muted">هشداری نیست.</li>';
    const plan = (D.media_plan || []).slice(0, 4).map((p, i) => planCard(p, i)).join('');
    const cats = Object.entries(D.categories || {}).filter(([, c]) => c.group === 'ecommerce' || c.core).slice(0, 8);
    return `
      <div class="hero"><h2>${esc(D.meta.change || I.headline || '')}</h2>${D.meta.action ? `<p style="color:var(--ink);font-weight:700">${esc(D.meta.action)}</p>` : ''}<p>${esc(D.meta.change ? (I.headline || '') : '')}</p></div>
      ${D.meta.coverage_pct_sites < 80 ? `<div class="card" style="border-color:var(--warn)"><b style="color:var(--warn)">⚠ پوشش کامل نیست:</b> فقط ${D.meta.coverage_pct_sites}% سایت‌های برنامه‌ریزی‌شده با موفقیت اسکن شدند؛ اعداد امروز را با احتیاط بخوانید (جزئیات در «راهنما و پوشش»).</div>` : ''}
      <div class="kpis">${tiles}</div>
      <div class="row c32">
        <div class="card"><h3>جمع‌بندی امروز</h3><p class="hint">تحلیل ${I.by === 'llm' ? 'مدل زبانی' : 'قاعده‌محور'} روی ${D.meta.runs} اسکن امروز</p><ul class="bul">${(I.summary || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>
        <div class="card"><h3>هشدارها</h3><p class="hint">جهش رقیب، ورود به سایت جدید، رقیب تازه، ریتارگتینگ</p><ul class="alerts">${alerts}</ul></div>
      </div>
      <div class="card"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"><div><h3>پیشنهاد امروز: دیجی‌کالا کجا و با چه تبلیغی برود؟</h3><p class="hint">۴ پیشنهاد برتر؛ فهرست کامل در تب «پیشنهاد رسانه»</p></div><button class="btn" data-go="plan">همهٔ پیشنهادها ←</button></div>
        <div class="plans">${plan || empty('هنوز دادهٔ کافی برای پیشنهاد نیست.')}</div></div>
      <div class="row c2">
        <div class="card"><h3>سهم دیده‌شدن (Share of Voice)</h3><p class="hint">وزن‌دار با ارزش جایگاه · طبق فیلترهای بالا</p>${hbars(sov, b => color(b))}</div>
        <div class="card"><h3>ریسک رقابت در دسته‌های ای‌کامرس</h3><p class="hint">ریسک = سهم پایین دیجی‌کالا + قدرت رقیب اول + تعداد رقبا</p>
          <div class="cats">${cats.map(([key, c]) => `<div class="cat"><div class="ch"><b>${esc(c.fa)}</b>${c.core ? '<span class="tag-core">Core</span>' : ''}</div>${meter(c.risk, false, 'ریسک')}<span class="small ink2">سهم دیجی‌کالا ${pct(c.own_share)} · ${c.rivals.length} رقیب</span></div>`).join('') || empty('—')}</div></div>
      </div>`;
  }

  // ---------------- 2. media plan
  const REC = { 'خرید مستقیم': 'good', 'بید پایین در شبکه': 'good', 'شکاف حضور': 'warn', 'تست': 'warn', 'اجتناب/متمایز': 'crit', 'پایش': 'mute', '—': 'mute' };
  const CONF = { 'بالا': 'good', 'متوسط': 'warn', 'اولیه': 'mute' };
  const briefText = p => [`سایت: ${p.site}`, `دسته: ${fa('category', p.category)}`, `فرمت/جایگاه: ${fa('format', p.format)} · ${fa('placement', p.placement)} · ${fa('device', p.device)}`,
    `مسیر خرید: ${p.route}`, `بید: ${p.bid}`, `پیام: ${p.angle}`, `هدف: ${p.objective}`, `رقبای حاضر: ${p.competitors.join('، ') || '—'}`,
    p.rival_offers.length ? `آفر رقبا: ${p.rival_offers.join(' | ')}` : '', `دلیل: ${p.why}`, `فشار ${p.pressure} · فرصت ${p.opportunity} · اطمینان ${p.confidence}`].filter(Boolean).join('\n');
  function planCard(p, i) {
    return `<div class="plan"><div class="ph"><b class="ltr">${esc(p.site)}</b><span style="display:flex;gap:6px;align-items:center"><span class="pill st-${CONF[p.confidence] || 'mute'}" title="اطمینان بر اساس تعداد اسکن‌های این سایت">اطمینان ${esc(p.confidence)}</span><span class="score" title="امتیاز پیشنهاد (0 تا 100)" style="color:${ST[stClass(p.score, true)]}">${p.score}</span></span></div>
      <div><span class="pill st-${REC[p.recommendation] || 'mute'}">${esc(p.recommendation)}</span> <span class="small muted">${esc(p.why)}</span></div>
      <dl><dt>چه بفروشیم</dt><dd>${esc(fa('category', p.category))}</dd>
      <dt>فرمت</dt><dd>${esc(fa('format', p.format))} · ${esc(fa('placement', p.placement))} · ${esc(fa('device', p.device))}</dd>
      <dt>مسیر خرید</dt><dd>${esc(p.route)}</dd><dt>بید</dt><dd>${esc(p.bid)}</dd>
      <dt>زاویهٔ پیام</dt><dd>${esc(p.angle)}${p.counter_theme ? ` <span class="muted small">(در برابر «${esc(fa('theme', p.counter_theme))}» رقبا)</span>` : ''}</dd>
      ${p.rival_offers.length ? `<dt>آفر رقبا</dt><dd class="small">${p.rival_offers.map(esc).join('<br>')}</dd>` : ''}
      <dt>هدف</dt><dd>${esc(p.objective)}</dd>
      <dt>رقبای حاضر</dt><dd>${p.competitors.length ? p.competitors.map(esc).join('، ') : '—'}</dd></dl>
      <div class="small muted">فشار ${p.pressure} · فرصت ${p.opportunity}${p.reach_known ? '' : ' (بدون دادهٔ دسترسی)'} · ${p.own_present ? 'دیجی‌کالا حاضر است' : 'دیجی‌کالا حاضر نیست'}</div>
      <div><button class="btn" data-brief="${i}">کپی بریف برای خرید</button></div></div>`;
  }
  function tabPlan() {
    const list = (D.media_plan || []).map((p, i) => [p, i]).filter(([p]) => (!F.cat || p.category === F.cat) && (!F.dev || p.device === F.dev));
    return `<div class="card"><h3>پیشنهاد رسانه برای دیجی‌کالا</h3>
      <p class="hint">برای هر سایت: کدام دسته را تبلیغ کنیم (جایی که رقبا تقاضا را ثابت کرده‌اند یا مخاطب سایت به آن نزدیک است)، در کم‌تراکم‌ترین جایگاه، با کدام مسیر خرید و چه سطح بید، و با چه پیامی که پیام غالب رقبا را خنثی کند.</p>
      <p><button class="btn" id="plan-csv">خروجی پلن برای وایت‌لیست شبکه‌ها (CSV)</button> <span class="small muted">سایت‌هایی که «اجتناب» خورده‌اند در پلن نیستند؛ در تب «سایت‌ها و شبکه‌ها» دیده می‌شوند.</span></p>
      <div class="plans">${list.map(([p, i]) => planCard(p, i)).join('') || empty('برای این فیلتر پیشنهادی نیست.')}</div></div>`;
  }

  // ---------------- 3. competitors
  function tabCompetitors() {
    const rows = rowsF();
    const ads = {}, sites = {};
    rows.forEach(r => { ads[r.b] = (ads[r.b] || 0) + 1; (sites[r.b] = sites[r.b] || new Set()).add(r.s); });
    const sov = Object.fromEntries(sovFromRows(rows));
    const list = Object.entries(D.competitors).filter(([b, c]) => ads[b] && (F.lvl === 'all' || F.lvl === 'rivals' || c.level === F.lvl));
    const body = list.map(([b, c]) => {
      const g = c.growth;
      const gt = c.sov_7d == null ? '<span class="muted">جدید</span>' : g == null ? '—' : `<span class="${g > 0 ? 'delta-up' : 'delta-dn'}">${g > 0 ? '+' : ''}${Math.round(g * 100)}%</span>`;
      return `<tr class="click" data-brand="${esc(b)}"><td>${brandCell(b)}</td><td>${esc(fa('level', c.level))}</td><td>${esc(fa('category', c.vertical))}</td>
        <td class="num" data-s="${sov[b] || 0}">${pct(sov[b], 1)}</td><td class="num" data-s="${c.sov_vertical}">${pct(c.sov_vertical)}</td><td class="num">${gt}</td>
        <td class="num" data-s="${c.presence}">${pct(c.presence, 1)}</td><td class="num" data-s="${sites[b].size}">${sites[b].size}</td><td class="num" data-s="${ads[b]}">${ads[b]}</td>
        <td data-s="${c.threat}">${c.level === 'own' ? '—' : meter(c.threat, false, 'تهدید')}</td><td>${chips(c.networks, 'network', 2)}</td><td>${chips(c.campaign_types, 'campaign', 2)}</td></tr>`;
    }).join('');
    return `<div class="card"><h3>رقبا</h3><p class="hint">روی هر ردیف بزنید تا جزئیات کامل (سایت‌ها، فرمت‌ها، پیام‌ها، کریتیوها، روند ۳۰ روزه) باز شود. «حضور» = درصد صفحه‌های اسکن‌شده که این برند در آن دیده شده (نزدیک به Impression Share).</p>
      <div class="tw"><table class="sortable"><thead><tr><th class="sort">برند</th><th class="sort">سطح</th><th class="sort">ورتیکال</th><th class="sort" title="سهم وزن‌دار دیده‌شدن بین برندهای ای‌کامرس؛ تعداد مشاهده است، نه هزینه">SOV ⓘ</th><th class="sort">SOV ورتیکال</th><th>تغییر ۷ روز</th><th class="sort" title="درصد صفحه‌های اسکن‌شده‌ای که برند در آن دیده شد (≈ Impression Share)">حضور ⓘ</th><th class="sort">سایت</th><th class="sort">تبلیغ</th><th class="sort" title="SOV ورتیکال 35٪ + رشد 20٪ + پوشش سایت 20٪ + تهاجمی بودن 25٪">تهدید ⓘ</th><th>شبکه</th><th>نوع کمپین</th></tr></thead>
      <tbody>${body || `<tr><td colspan="12">${empty('رقیبی برای این فیلتر دیده نشد.')}</td></tr>`}</tbody></table></div></div>`;
  }
  function openBrand(b) {
    const c = D.competitors[b]; if (!c) return;
    const rows = D.rows.filter(r => r.b === b);
    const shots = [...new Map(rows.filter(r => img(r.sh)).map(r => [r.sh, r])).values()].slice(0, 8);
    const series = D.M && D.M.competitors && D.M.competitors[b] ? D.M.competitors[b].series : [];
    const dp = D.dayparts[b] || {};
    const th = (D.messaging.by_brand || {})[b] || {};
    $('#drawer').innerHTML = `<button class="x" data-close>✕ بستن</button><h3 style="margin:0 0 4px">${brandCell(b)}</h3>
      <div class="muted small">${esc(fa('level', c.level))} · ${esc(fa('category', c.vertical))}</div>
      <dl class="kv"><dt>SOV کل / ورتیکال</dt><dd>${pct(c.sov, 1)} / ${pct(c.sov_vertical)}</dd><dt>تهدید</dt><dd>${c.level === 'own' ? '—' : meter(c.threat)}</dd>
      <dt>حضور در صفحات</dt><dd>${pct(c.presence, 1)}</dd><dt>سایت‌ها</dt><dd class="ltr">${esc(c.sites.join(', '))}</dd>
      ${c.new_sites.length ? `<dt>سایت‌های تازه</dt><dd class="ltr">${esc(c.new_sites.join(', '))}</dd>` : ''}
      <dt>شبکه‌ها</dt><dd>${chips(c.networks, 'network', 6)}</dd><dt>فرمت</dt><dd>${chips(c.formats, 'format', 6)}</dd><dt>جایگاه</dt><dd>${chips(c.placements, 'placement', 6)}</dd>
      <dt>دستگاه</dt><dd>${chips(c.devices, 'device')}</dd><dt>زمان روز</dt><dd>${chips(dp, 'daypart')}</dd>
      <dt>نوع کمپین</dt><dd>${chips(c.campaign_types, 'campaign', 8)}</dd><dt>پیام‌ها</dt><dd>${chips(Object.fromEntries(Object.entries(th).filter(([k]) => !k.startsWith('offer:'))), 'theme', 8)}</dd>
      ${c.retargeting_sites.length ? `<dt>ریتارگتینگ</dt><dd class="ltr">${esc(c.retargeting_sites.join(', '))}</dd>` : ''}
      ${c.utm_campaigns.length ? `<dt>کمپین‌ها (UTM)</dt><dd class="ltr small">${esc(c.utm_campaigns.join(' · '))}</dd>` : ''}
      ${c.landing_types && Object.keys(c.landing_types).length ? `<dt>نوع لندینگ</dt><dd>${chips(c.landing_types, 'landing')}</dd>` : ''}
      <dt>روند ۳۰ روز</dt><dd>${series.length > 1 ? spark(series, color(b)) : '<span class="muted">از روز دوم ساخته می‌شود</span>'}</dd></dl>
      ${respond(b, c)}
      <h3 style="font-size:14px">زمان و دستگاه</h3>${dpGrid(rows)}
      <h3 style="font-size:14px">متن‌های تبلیغ</h3><ul class="bul small">${c.top_titles.map(t => `<li>${esc(t)}</li>`).join('') || '<li class="muted">—</li>'}</ul>
      <h3 style="font-size:14px;margin-top:12px">کریتیوها</h3><div class="shots">${shots.map(r => `<div class="cr" data-shot="${r.sh}"><div class="frame"><img src="${img(r.sh)}" alt=""></div><div class="meta small"><span class="ltr">${esc(r.s)}</span>${esc(fa('placement', r.p))}</div></div>`).join('') || empty('اسکرین‌شاتی نیست.')}</div>`;
    $('#drawer').classList.add('on'); $('#scrim').classList.add('on');
  }

  function respond(b, c) {
    if (c.level === 'own') return '';
    const ownSites = new Set(D.rows.filter(r => r.l === 'own').map(r => r.s));
    const gap = c.sites.filter(s => !ownSites.has(s));
    const th = Object.entries((D.messaging.by_brand || {})[b] || {}).filter(([k]) => !k.startsWith('offer:')).sort((a, b2) => b2[1] - a[1])[0];
    return `<div class="card" style="background:var(--s2);margin:10px 0"><h3 style="font-size:14px">پاسخ پیشنهادی دیجی‌کالا</h3><ul class="bul small">
      ${gap.length ? `<li>حضور در سایت‌هایی که ${esc(b)} هست و دیجی‌کالا نیست: <span class="ltr">${esc(gap.slice(0, 6).join(', '))}</span></li>` : '<li>در همهٔ سایت‌های این رقیب، دیجی‌کالا هم حاضر است.</li>'}
      ${th ? `<li>پیام غالب رقیب «${esc(fa('theme', th[0]))}» است؛ زاویهٔ پیشنهادی: ${esc((D.angles || {})[th[0]] || '')}</li>` : ''}
      ${c.retargeting_sites.length ? `<li>ریتارگتینگ رقیب در <span class="ltr">${esc(c.retargeting_sites.join(', '))}</span>: کمپین ریتارگتینگ دیجی‌کالا روی همین سایت‌ها/شبکه فعال شود.</li>` : ''}
      ${c.surge ? '<li>جهش امروز: بید روی دسته‌های مشترک موقتاً بالاتر برود تا سهم حفظ شود.</li>' : ''}</ul></div>`;
  }
  function dpGrid(rows) {
    const dps = ['morning', 'noon', 'evening'], devs = ['mobile', 'desktop'];
    const m = {}; rows.forEach(r => { const k = r.dp + '|' + r.d; m[k] = (m[k] || 0) + 1; });
    const mx = Math.max(1, ...Object.values(m));
    return `<table class="heat small"><thead><tr><th></th>${dps.map(d => `<th>${esc(fa('daypart', d))}</th>`).join('')}</tr></thead><tbody>${devs.map(v => `<tr><td>${esc(fa('device', v))}</td>${dps.map(d => { const n = m[d + '|' + v] || 0; return `<td class="hc" style="${heatStyle(n, mx)}">${n || ''}</td>`; }).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function heatStyle(v, mx) { return v ? `background:rgba(57,135,229,${(0.18 + 0.82 * v / mx).toFixed(2)});color:${v / mx > .55 ? '#0d0d0d' : '#f0efec'}` : 'background:transparent;box-shadow:inset 0 0 0 1px #2c2c2a'; }
  const heatLegend = mx => `<div class="legend"><span>کم</span><span style="display:inline-block;width:120px;height:10px;border-radius:5px;background:linear-gradient(to left,rgba(57,135,229,1),rgba(57,135,229,.18))"></span><span>زیاد (${mx})</span></div>`;

  // ---------------- 4. categories
  function tabCategories() {
    const rows = rowsF();
    // all e-commerce categories are always listed (also those with no competitor ads today)
    const cats = Object.entries(D.categories || {}).concat(Object.entries(D.catmeta || {}).filter(([k, c]) => c.group === 'ecommerce' && !(D.categories || {})[k])
      .map(([k, c]) => [k, { ...c, share: 0, ads: 0, n_sites: 0, own_share: 0, risk: 0, rivals: [], quiet: true }]));
    const brands = sovFromRows(rows).filter(([b]) => (D.competitors[b] || {}).level !== 'own').slice(0, 8).map(x => x[0]);
    const m = {}; rows.forEach(r => { if (!brands.includes(r.b)) return; (m[r.c] = m[r.c] || {})[r.b] = ((m[r.c] || {})[r.b] || 0) + 1; });
    const mx = Math.max(1, ...Object.values(m).flatMap(o => Object.values(o)));
    const SEQ = ['#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef'];
    const heat = cats.filter(([k]) => m[k]).map(([k, c]) => `<tr><td>${esc(c.fa)}</td>${brands.map(b => { const v = (m[k] || {})[b] || 0; return `<td class="hc" title="${esc(c.fa)} · ${esc(b)}: ${v} تبلیغ" style="${heatStyle(v, mx)}">${v || ''}</td>`; }).join('')}</tr>`).join('');
    return `<div class="card"><h3>دسته‌های کالایی</h3><p class="hint">دستهٔ هر تبلیغ از متن کریتیو و لندینگ تشخیص داده می‌شود؛ مثلاً اسنپ‌شاپ وقتی آیفون تبلیغ می‌کند در «دیجیتال و موبایل» حساب می‌شود.</p>
      <div class="cats">${cats.map(([k, c]) => `<div class="cat" ${c.quiet ? 'style="opacity:.55"' : ''}><div class="ch"><b>${esc(c.fa)}</b>${c.core ? '<span class="tag-core">Core</span>' : ''}</div>
        ${c.quiet ? '<span class="small muted">امروز تبلیغی از رقبا دیده نشد</span>' : meter(c.risk, false, 'ریسک')}<div class="small ink2">${pct(c.share)} از کل تبلیغات · ${c.ads} تبلیغ · ${c.n_sites} سایت · سهم دیجی‌کالا ${pct(c.own_share)}</div>
        <div class="mini">${c.rivals.slice(0, 4).map(r => `<div class="hrow"><span class="hl">${esc(r.brand)}</span><span class="ht"><i style="width:${Math.max(3, r.share * 100)}%;background:${color(r.brand)}"></i></span><span class="hv">${pct(r.share)}</span></div>`).join('') || '<span class="muted small">رقیبی دیده نشد</span>'}</div></div>`).join('') || empty('—')}</div></div>
      <div class="card"><h3>کدام رقیب روی کدام دسته تبلیغ می‌کند؟</h3><p class="hint">تعداد تبلیغ · ۸ رقیب پرحضور طبق فیلتر (ستون‌ها به ترتیب حجم)</p>${heatLegend(mx)}
      ${heat ? `<div class="tw"><table class="heat"><thead><tr><th>دسته</th>${brands.map(b => `<th>${esc(b)}</th>`).join('')}</tr></thead><tbody>${heat}</tbody></table></div>` : empty('—')}</div>`;
  }

  // ---------------- 5. sites & opportunity
  function tabSites() {
    const rows = rowsF();
    const catSites = F.cat ? new Set(rows.map(r => r.s)) : null;
    const src = { sheet: 'شیت', seed: 'سیستم', discovered: 'کشف‌شده' };
    const recC = { 'خرید مستقیم': 'good', 'بید پایین در شبکه': 'good', 'شکاف حضور': 'warn', 'تست': 'warn', 'اجتناب/متمایز': 'crit', 'پایش': 'mute', '—': 'mute' };
    const list = Object.entries(D.sites).filter(([d]) => !catSites || catSites.has(d));
    const body = list.map(([d, s]) => `<tr><td class="ltr">${esc(d)}</td><td>${esc(src[s.source] || s.source)}</td><td>${esc(fa('sitecat', s.cat_key || s.category))}</td>
      <td data-s="${s.opportunity}">${meter(s.opportunity, true, 'فرصت')}</td><td data-s="${s.pressure}">${meter(s.pressure, false, 'فشار')}</td>
      <td class="num" data-s="${s.slots_per_page}">${s.slots_per_page}</td><td class="num" data-s="${s.advertisers}">${s.advertisers}</td><td class="num" data-s="${s.competitor_share}">${pct(s.competitor_share)}</td>
      <td>${s.own_present ? '✓' : '<span class="muted">✗</span>'}</td><td><span class="pill st-${recC[s.recommendation] || 'mute'}">${esc(s.recommendation)}</span><div class="small muted" style="max-width:300px">${esc(s.why)}</div></td>
      <td class="small">${(s.cheapest_units || []).slice(0, 2).map(u => esc(fa('placement', u.placement) + ' (' + fa('device', u.device) + ')')).join('<br>') || '—'}</td><td>${(s.networks || []).slice(0, 3).map(n => chip(fa('network', n))).join('')}</td></tr>`).join('');
    const plc = Object.keys(FA.placement);
    const top = list.slice(0, 30); const mx = Math.max(1, ...top.flatMap(([, s]) => Object.values(s.placements || {})));
    const SEQ = ['#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef'];
    const heat = top.map(([d, s]) => `<tr><td class="ltr">${esc(d)}</td>${plc.map(p => { const v = (s.placements || {})[p] || 0; return `<td class="hc" title="${esc(d)} · ${esc(FA.placement[p])}: ${v}" style="${heatStyle(v, mx)}">${v || ''}</td>`; }).join('')}</tr>`).join('');
    return `<div class="card"><h3>کجا با فشار کمتر و بید کمتر وارد شویم؟</h3>
      <p class="hint">فرصت = دسترسی سایت × فشار پایین × حضور رقبا (اثبات مخاطب) × قابل خرید بودن. فشار = اسلات در صفحه، تعداد تبلیغ‌دهنده، تراکم رقبا، سهم جایگاه‌های ممتاز و چرخش کریتیو.${F.cat ? ' (فقط سایت‌هایی که دستهٔ انتخابی در آن‌ها تبلیغ شده)' : ''}</p>
      <div class="tw"><table class="sortable"><thead><tr><th class="sort">سایت</th><th class="sort">منبع</th><th class="sort">دسته</th><th class="sort" title="دسترسی 35٪ + فشار پایین 35٪ + اثبات مخاطب 15٪ + قابل خرید 15٪">فرصت ⓘ</th><th class="sort" title="اسلات 30٪ + تبلیغ‌دهنده 20٪ + تراکم رقبا 25٪ + جایگاه ممتاز 10٪ + چرخش 15٪">فشار ⓘ</th><th class="sort">اسلات/صفحه</th><th class="sort">تبلیغ‌دهنده</th><th class="sort">سهم رقبا</th><th>دیجی‌کالا</th><th>پیشنهاد</th><th>کم‌تراکم‌ترین جایگاه</th><th>شبکه</th></tr></thead><tbody>${body || `<tr><td colspan="12">${empty('—')}</td></tr>`}</tbody></table></div></div>
      <div class="card"><h3>شکاف حضور</h3><p class="hint">سایت‌هایی که حداقل دو رقیب دارند و دیجی‌کالا ندارد</p>${(D.gaps || []).length ? `<div class="ltr" style="text-align:right">${D.gaps.map(g => chip(g)).join('')}</div>` : empty('شکافی دیده نشد.')}</div>
      <div class="card"><h3>نقشهٔ حرارتی جایگاه‌ها</h3><p class="hint">تعداد تبلیغ در هر جایگاه · ۳۰ سایت اول</p>${heatLegend(mx)}<div class="tw"><table class="heat"><thead><tr><th>سایت</th>${plc.map(p => `<th>${esc(FA.placement[p])}</th>`).join('')}</tr></thead><tbody>${heat}</tbody></table></div></div>`;
  }
  function networkTable(compact) {
    const n = Object.entries(D.networks || {});
    if (!n.length) return empty('—');
    const cl = { 'داغ': 'crit', 'متوسط': 'warn', 'آرام': 'good' };
    return `<div class="tw"><table class="sortable"><thead><tr><th class="sort">شبکه</th><th class="sort">تبلیغ</th><th class="sort">تبلیغ‌دهنده</th><th class="sort">سایت</th><th class="sort">سهم رقبا</th><th>دمای بید</th>${compact ? '' : '<th>رقبای اصلی</th><th class="sort">میانگین فشار سایت‌ها</th>'}</tr></thead><tbody>
      ${n.map(([k, v]) => `<tr><td>${esc(fa('network', k))}</td><td class="num">${v.ads}</td><td class="num">${v.advertisers}</td><td class="num">${v.sites}</td><td class="num" data-s="${v.competitor_share}">${pct(v.competitor_share)}</td><td><span class="pill st-${cl[v.bid_climate]}">${esc(v.bid_climate)}</span></td>${compact ? '' : `<td class="small">${esc(v.top_competitors.join('، ') || '—')}</td><td class="num">${v.avg_pressure ?? '—'}</td>`}</tr>`).join('')}</tbody></table></div>`;
  }

  // ---------------- 6. discovery
  function tabDiscovery() {
    const d = D.discovery || {};
    const tbl = (rows, cols, em) => rows && rows.length ? `<div class="tw"><table><thead><tr>${cols.map(c => `<th>${c[1]}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${c[2] || ''}">${esc(c[3] ? c[3](r[c[0]]) : r[c[0]])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : empty(em || 'موردی نیست.');
    const P = x => fa('placement', x), Fm = x => fa('format', x), N = x => fa('network', x), Dv = x => fa('device', x), L = x => fa('level', x), C = x => fa('category', x);
    const catalog = Object.entries(d.catalog || {}).sort().map(([s, c]) => `<details><summary class="ltr">${esc(s)} <span class="muted small">(${Object.keys(c).length} جایگاه)</span></summary><ul class="bul small">${Object.entries(c).map(([k, v]) => `<li>${esc(k)} <span class="muted">×${v}</span></li>`).join('')}</ul></details>`).join('');
    return `<div class="card"><h3>جمع‌بندی کشف</h3><ul class="bul">${((D.I || {}).inventory_notes || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li class="muted">—</li>'}</ul>
      <p class="small muted">سایت‌هایی که امروز اولین بار اسکن شده‌اند «خط پایه» هستند و جایگاه‌هایشان «تازه» حساب نمی‌شود: <span class="ltr">${esc((d.baseline_sites || []).slice(0, 25).join(', ') || '—')}</span></p></div>
      <div class="row c2">
        <div class="card"><h3>جایگاه / فرمت تازه</h3>${tbl(d.new_units, [['site', 'سایت', 'ltr'], ['placement', 'جایگاه', '', P], ['format', 'فرمت', '', Fm], ['device', 'دستگاه', '', Dv], ['size', 'سایز', 'ltr'], ['network', 'شبکه', '', N], ['brand', 'اولین تبلیغ‌دهنده']])}</div>
        <div class="card"><h3>ورود رقیب به سایت تازه</h3>${tbl(d.competitor_new_sites, [['brand', 'برند'], ['site', 'سایت', 'ltr'], ['placement', 'جایگاه', '', P], ['format', 'فرمت', '', Fm]])}</div>
        <div class="card"><h3>تبلیغ‌دهندهٔ تازه</h3>${tbl(d.new_advertisers, [['name', 'برند'], ['level', 'سطح', '', L], ['vertical', 'ورتیکال', '', C]])}</div>
        <div class="card"><h3>شبکهٔ تازه روی سایت</h3>${tbl(d.new_networks, [['site', 'سایت', 'ltr'], ['network', 'شبکه', '', N]])}
          <h3 style="margin-top:14px">دامنه‌های ناشناختهٔ شبیه ادسرور</h3><p class="hint">اگر شبکهٔ تبلیغاتی هستند، به config/ad_networks.yaml اضافه شوند.</p>${tbl(d.candidate_networks, [['host', 'دامنه', 'ltr'], ['sites', 'صفحه']])}</div>
      </div>
      <div class="card"><h3>شبکه‌ها: دمای رقابت</h3><p class="hint">سهم رقبا از تبلیغات هر شبکه ≈ فشار بید در مزایدهٔ آن شبکه</p>${networkTable(false)}</div>
      <div class="row c2"><div class="card"><h3>فرمت‌های خاص</h3><p>پوش نوتیفیکیشن: <span class="ltr">${esc((d.push_sites || []).join(', ') || '—')}</span></p><p>رپورتاژ: <span class="ltr">${esc((d.reportage_sites || []).join(', ') || '—')}</span></p>
        <h3>میکس فرمت بازار</h3>${hbars(Object.entries(D.format_share || {}).map(([k, v]) => [fa('format', k), v]), null, v => v)}</div>
        <div class="card"><h3>کاتالوگ اینونتوری هر سایت</h3><p class="hint">جایگاه · فرمت · سایز · دستگاه</p>${catalog || empty('—')}</div></div>`;
  }

  // ---------------- 7. messaging & offers
  function tabMessaging() {
    const m = D.messaging || {}, T = m.themes_fa || {};
    const mk = Object.entries(m.market || {}).map(([k, v]) => [T[k] || k, v]);
    const brands = Object.entries(m.by_brand || {}).filter(([b]) => D.competitors[b]).slice(0, 14);
    const themes = Object.keys(T);
    const utm = Object.entries(D.competitors).filter(([, c]) => c.utm_campaigns.length).map(([b, c]) => `<tr><td>${brandCell(b)}</td><td class="ltr small">${esc(c.utm_campaigns.join(' · '))}</td></tr>`).join('');
    const offers = Object.entries(D.competitors).filter(([, c]) => Object.keys(c.offers || {}).length).map(([b, c]) => `<tr><td>${brandCell(b)}</td><td>${chips(c.offers, 'campaign', 6)}</td></tr>`).join('');
    return `<div class="row c2"><div class="card"><h3>پیام غالب بازار</h3><p class="hint">تعداد کریتیوهای رقبا با هر مضمون</p>${hbars(mk, () => '#d95926', v => v)}</div>
      <div class="card"><h3>شکاف پیام دیجی‌کالا</h3><p class="hint">مضمون‌هایی که رقبا استفاده می‌کنند و در کریتیوهای دیجی‌کالا امروز دیده نشد</p>
        ${(m.gaps || []).length ? `<ul class="bul">${m.gaps.map(g => `<li><b>${esc(T[g] || g)}</b>: پیشنهاد زاویه — ${esc((D.angles || {})[g] || '')}</li>`).join('')}</ul>` : empty('شکافی دیده نشد.')}
        <h3 style="margin-top:12px">CTAهای پرتکرار</h3><div>${(m.ctas || []).map(c => chip(c)).join('') || '<span class="muted">—</span>'}</div></div></div>
      <div class="card"><h3>مضمون پیام هر رقیب</h3><div class="tw"><table><thead><tr><th>برند</th>${themes.map(t => `<th>${esc(T[t])}</th>`).join('')}</tr></thead><tbody>
        ${brands.map(([b, c]) => `<tr><td>${brandCell(b)}</td>${themes.map(t => `<td class="num">${c[t] || ''}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="9">${empty('—')}</td></tr>`}</tbody></table></div></div>
      <div class="row c2"><div class="card"><h3>آفرهای لندینگ</h3><p class="hint">از صفحهٔ مقصد تبلیغ (اقساط، ارسال رایگان، تایمر، کد تخفیف، گیمیفیکیشن)</p>${offers ? `<div class="tw"><table><tbody>${offers}</tbody></table></div>` : empty('—')}</div>
      <div class="card"><h3>تقویم کمپین رقبا (UTM)</h3><p class="hint">نام کمپین‌ها از پارامتر utm_campaign لینک تبلیغ</p>${utm ? `<div class="tw"><table><tbody>${utm}</tbody></table></div>` : empty('—')}</div></div>`;
  }

  // ---------------- 8. creatives
  const G = { brand: '', fmt: '', net: '', sort: 'new', q: '' };
  function tabCreatives() {
    const rows = rowsF().filter(r => (!G.brand || r.b === G.brand) && (!G.fmt || r.f === G.fmt) && (!G.net || r.n === G.net) && (!G.q || (r.t + ' ' + r.b + ' ' + r.s).includes(G.q)));
    const groups = new Map();
    // one card per creative: same brand + same text (or same landing/format/placement for image-only banners); prefer a mobile screenshot
    rows.forEach(r => { if (!r.sh && !r.t) return; const k = r.b + '|' + (r.t || (r.ld + '|' + r.f + '|' + r.p));
      const g = groups.get(k) || { r, n: 0, sites: new Set() }; g.n++; g.sites.add(r.s);
      if ((!img(g.r.sh) && img(r.sh)) || (img(r.sh) && r.d === 'mobile' && g.r.d !== 'mobile')) g.r = r; groups.set(k, g); });
    const isNew = r => r.fs === D.meta.date || (r.dy || 1) <= 1;
    const sorter = { new: (a, b) => (isNew(b.r) ? 1 : 0) - (isNew(a.r) ? 1 : 0) || b.n - a.n, freq: (a, b) => b.n - a.n, long: (a, b) => (b.r.dy || 1) - (a.r.dy || 1) || b.n - a.n }[G.sort];
    const cards = [...groups.values()].sort((a, b) => (img(b.r.sh) ? 1 : 0) - (img(a.r.sh) ? 1 : 0) || sorter(a, b)).slice(0, 180);
    const nets = [...new Set(D.rows.map(r => r.n))];
    const brands = [...new Set(D.rows.filter(r => ['core', 'vertical', 'own'].includes(r.l)).map(r => r.b))].sort();
    const fmts = [...new Set(D.rows.map(r => r.f))];
    const lr = (D.long_running || []).map(x => `<tr><td>${brandCell(x.brand)}</td><td>${x.shot_key && img(x.shot_key) ? `<img class="thumb" src="${img(x.shot_key)}" alt="">` : ''}${esc(x.title || '')}</td><td class="num" data-s="${x.days}">${x.days}</td><td class="ltr num">${esc(x.first_seen)}</td><td class="num">${x.sites}</td></tr>`).join('');
    return `<div class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;flex:1 1 200px">گالری کریتیو</h3>
        <select id="g-brand"><option value="">همهٔ برندها</option>${brands.map(b => `<option ${G.brand === b ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select>
        <select id="g-fmt"><option value="">همهٔ فرمت‌ها</option>${fmts.map(f => `<option value="${f}" ${G.fmt === f ? 'selected' : ''}>${esc(fa('format', f))}</option>`).join('')}</select>
        <select id="g-net"><option value="">همهٔ شبکه‌ها</option>${nets.map(n => `<option value="${n}" ${G.net === n ? 'selected' : ''}>${esc(fa('network', n))}</option>`).join('')}</select>
        <select id="g-sort"><option value="new" ${G.sort === 'new' ? 'selected' : ''}>اول جدیدها</option><option value="freq" ${G.sort === 'freq' ? 'selected' : ''}>پرتکرارترین</option><option value="long" ${G.sort === 'long' ? 'selected' : ''}>طولانی‌ترین اجرا</option></select>
        <input type="search" id="g-q" placeholder="جست‌وجو در متن، برند یا سایت" value="${esc(G.q)}"></div>
      <p class="hint">هر کارت یک کریتیو یکتاست (تکراری‌ها ادغام شده‌اند). تصویر با اندازهٔ واقعی و بدون کشیدگی نمایش داده می‌شود؛ برای بزرگ‌نمایی روی کارت بزنید.</p>
      <div class="gallery">${cards.map(g => { const r = g.r, s = img(r.sh); return `<div class="cr" data-shot="${r.sh}" data-k="${esc(r.b)}|${esc(r.t)}"><div class="frame">${s ? `<img src="${s}" alt="${esc(r.t)}" loading="lazy">` : `<div class="noimg">${esc(r.t || 'بدون تصویر')}</div>`}</div>
        <div class="meta"><div class="b"><span style="display:inline-flex;align-items:center"><i class="dot" style="background:${color(r.b)}"></i>${esc(r.b)}</span><span class="small">${isNew(r) ? '<span class="pill st-good">جدید امروز</span>' : `<span class="muted">${r.dy || 1} روز اجرا</span>`} <span class="muted">×${g.n}</span></span></div>
        <div class="t">${esc(r.t || '')}</div><div>${chip(fa('format', r.f))}${chip(fa('placement', r.p))}${chip(fa('device', r.d))}${chip(fa('network', r.n))}</div>${r.of ? `<div class="small" style="color:var(--warn)">${esc(r.of)}</div>` : ''}
        <div class="muted small ltr" style="text-align:right">${esc([...g.sites].slice(0, 3).join(', '))}${g.sites.size > 3 ? ' +' + (g.sites.size - 3) : ''}</div></div></div>`; }).join('') || empty('کریتیوی برای این فیلتر نیست.')}</div></div>
      <div class="card"><h3>کریتیوهای پرعمر</h3><p class="hint">کریتیوی که روزهای بیشتری اجرا شده احتمالاً بازده خوبی دارد (سابقهٔ ۳۰ روز)</p>
      ${lr ? `<div class="tw"><table class="sortable"><thead><tr><th>برند</th><th>کریتیو</th><th class="sort">روز اجرا</th><th>اولین مشاهده</th><th>سایت</th></tr></thead><tbody>${lr}</tbody></table></div>` : empty('—')}</div>`;
  }
  function openShot(el) {
    const k = el.dataset.shot; const r = D.rows.find(x => x.sh === k && k) || D.rows.find(x => (x.b + '|' + x.t) === el.dataset.k);
    if (!r) return;
    const all = D.rows.filter(x => x.b === r.b && (r.t ? x.t === r.t : (x.ld === r.ld && x.f === r.f && x.p === r.p)));
    const s = img(r.sh);
    $('#lb').innerHTML = `<button class="x" data-close>✕</button><h3 style="margin:0 0 10px">${brandCell(r.b)}</h3>${s ? `<div class="big"><img src="${s}" alt=""></div>` : ''}
      <dl class="kv"><dt>متن</dt><dd>${esc(r.t || '—')}</dd><dt>سایت‌ها</dt><dd class="ltr">${esc([...new Set(all.map(x => x.s))].join(', '))}</dd>
      <dt>جایگاه / فرمت</dt><dd>${esc(fa('placement', r.p))} · ${esc(fa('format', r.f))} · <span class="ltr">${esc(r.sz)}</span></dd><dt>شبکه</dt><dd>${esc(fa('network', r.n))}</dd>
      <dt>دستگاه / زمان</dt><dd>${[...new Set(all.map(x => fa('device', x.d)))].join('، ')} · ${[...new Set(all.map(x => fa('daypart', x.dp)))].join('، ')}</dd>
      <dt>نوع کمپین</dt><dd>${(r.ct || []).map(c => chip(fa('campaign', c))).join('')}</dd><dt>دستهٔ کالا</dt><dd>${esc(fa('category', r.c))}</dd>
      <dt>اولین / آخرین مشاهده</dt><dd class="ltr">${esc(r.fs || D.meta.date)} → ${esc(r.ls || D.meta.date)} (${r.dy || 1} روز)</dd>${r.of ? `<dt>آفر</dt><dd>${esc(r.of)}</dd>` : ''}
      ${r.ld ? `<dt>لندینگ</dt><dd class="ltr">${esc(r.ld)}${r.lt ? ' · ' + esc(fa('landing', r.lt)) : ''}</dd>` : ''}${r.u ? `<dt>کمپین (UTM)</dt><dd class="ltr">${esc(r.u)}</dd>` : ''}
      <dt>دفعات دیده‌شدن</dt><dd>${all.length}${all.some(x => x.w) && !all.some(x => !x.w) ? ' · فقط در پروفایل گرم (ریتارگتینگ)' : ''}</dd></dl>`;
    $('#ov').classList.add('on');
  }

  // ---------------- 9. trends
  function tabTrends() {
    const M = D.M;
    if (!M || (M.days || 0) < 2) return `<div class="card">${empty('روند ۳۰ روزه از روز دوم اجرا ساخته می‌شود. دادهٔ خام ۳ روز و خلاصهٔ روزانه ۳۱ روز نگه داشته می‌شود.')}</div>`;
    const comps = Object.entries(M.competitors).slice(0, 7);
    const ms = Object.entries(M.sites || {}).sort((a, b) => b[1].avg_opportunity - a[1].avg_opportunity).slice(0, 25);
    const mb = (D.I || {}).monthly || [];
    return `${M.days < 7 ? `<div class="card" style="border-color:var(--warn)"><b style="color:var(--warn)">سابقهٔ کافی نیست (${M.days} روز).</b> <span class="small ink2">روندها از ۷ روز به بعد قابل اتکا هستند؛ تا آن موقع نقطه‌ها را مقایسه کنید، نه شیب خط‌ها را.</span></div>` : ''}
      ${mb.length ? `<div class="card"><h3>تصویر ۳۰ روزه</h3><p class="hint">${esc(M.from)} تا ${esc(M.to)} · ${M.days} روز</p><ul class="bul">${mb.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      <div class="card"><h3>روند سهم دیده‌شدن</h3><p class="hint">۷ برند پرحضور ماه · برای دیدن مقدار هر روز، نشانگر را روی نمودار ببرید</p>${lineChart(comps, M.dates)}</div>
      <div class="row c2"><div class="card"><h3>جدول ماهانهٔ رقبا</h3><div class="tw"><table class="sortable"><thead><tr><th>برند</th><th class="sort">میانگین SOV</th><th class="sort">تغییر</th><th class="sort">میانگین تهدید</th><th class="sort">روز فعال</th><th class="sort">سایت</th></tr></thead><tbody>
        ${Object.entries(M.competitors).map(([b, c]) => `<tr><td>${brandCell(b)}</td><td class="num" data-s="${c.avg_sov}">${pct(c.avg_sov, 1)}</td><td class="num" data-s="${c.trend || 0}">${c.trend == null ? '—' : `<span class="${c.trend > 0 ? 'delta-up' : 'delta-dn'}">${c.trend > 0 ? '+' : ''}${(c.trend * 100).toFixed(1)}</span>`}</td><td class="num">${c.avg_threat}</td><td class="num">${c.active_days}</td><td class="num">${c.sites}</td></tr>`).join('')}</tbody></table></div></div>
      <div class="card"><h3>پایدارترین فرصت‌ها</h3><div class="tw"><table class="sortable"><thead><tr><th>سایت</th><th class="sort">فرصت</th><th class="sort">فشار</th><th>نوسان فشار</th><th>روز</th></tr></thead><tbody>
        ${ms.map(([d, s]) => `<tr><td class="ltr">${esc(d)}</td><td data-s="${s.avg_opportunity}">${meter(s.avg_opportunity, true)}</td><td data-s="${s.avg_pressure}">${meter(s.avg_pressure)}</td><td class="num">±${s.pressure_std}</td><td class="num">${s.days}</td></tr>`).join('')}</tbody></table></div></div></div>`;
  }
  function spark(series, c) {
    const w = 200, h = 38, ys = series.map(x => x[1]), mx = Math.max(...ys) || 1;
    const pts = ys.map((v, i) => `${(i * (w - 8) / (ys.length - 1) + 4).toFixed(1)},${(h - 5 - v / mx * (h - 10)).toFixed(1)}`);
    const last = pts[pts.length - 1].split(',');
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img"><title>${esc(series[0][0])} → ${esc(series[series.length - 1][0])}: ${pct(ys[0], 1)} → ${pct(ys[ys.length - 1], 1)}</title><polyline fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" points="${pts.join(' ')}"/><circle cx="${last[0]}" cy="${last[1]}" r="4" fill="${c}" stroke="#1a1a19" stroke-width="2"/></svg>`;
  }
  function lineChart(comps, dates) {
    const W = 900, H = 300, L = 58, R = 16, T = 14, B = 30;
    const idx = Object.fromEntries(dates.map((d, i) => [d, i]));
    const mx = Math.max(0.01, ...comps.flatMap(([, c]) => c.series.map(s => s[1])));
    const x = i => L + (dates.length > 1 ? i * (W - L - R) / (dates.length - 1) : 0), y = v => T + (H - T - B) * (1 - v / mx);
    const ticks = [0, .25, .5, .75, 1].map(t => t * mx);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="روند SOV">${ticks.map(t => `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" stroke="#2c2c2a"/><text x="${L - 8}" y="${y(t) + 4}" fill="#898781" font-size="11" text-anchor="end" direction="ltr">${pct(t, 1)}</text>`).join('')}`;
    const step = Math.ceil(dates.length / 8);
    dates.forEach((d, i) => { if (i % step === 0 || i === dates.length - 1) svg += `<text x="${x(i)}" y="${H - 8}" fill="#898781" font-size="11" text-anchor="middle">${d.slice(5)}</text>`; });
    comps.forEach(([b, c]) => {
      const pts = c.series.filter(s => s[0] in idx).map(s => `${x(idx[s[0]]).toFixed(1)},${y(s[1]).toFixed(1)}`);
      if (pts.length) svg += `<polyline fill="none" stroke="${color(b)}" stroke-width="2" stroke-linejoin="round" points="${pts.join(' ')}"/>`;
      if (dates.length < 14) pts.forEach(pt => { const [cx, cy] = pt.split(','); svg += `<circle cx="${cx}" cy="${cy}" r="4.5" fill="${color(b)}" stroke="#1a1a19" stroke-width="2"/>`; });
    });
    svg += `<line id="xh" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="#c3c2b7" stroke-dasharray="3 3" style="display:none"/><rect id="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg>`;
    const legend = `<div class="legend">${comps.map(([b]) => `<span><i class="dot" style="background:${color(b)}"></i>${esc(b)}</span>`).join('')}</div>`;
    setTimeout(() => {
      const box = $('#lc'), tip = $('#lc .tip'), s = $('#lc svg'); if (!s) return;
      s.querySelector('#hit').onmousemove = e => {
        const r = s.getBoundingClientRect(), px = (e.clientX - r.left) * W / r.width;
        const i = Math.max(0, Math.min(dates.length - 1, Math.round((px - L) / ((W - L - R) / Math.max(1, dates.length - 1)))));
        const xh = s.querySelector('#xh'); xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i)); xh.style.display = '';
        const vals = comps.map(([b, c]) => [b, (c.series.find(z => z[0] === dates[i]) || [0, null])[1]]).filter(v => v[1] != null).sort((a, b) => b[1] - a[1]);
        tip.innerHTML = `<b>${dates[i]}</b><br>${vals.map(([b, v]) => `<i class="dot" style="background:${color(b)}"></i>${esc(b)}: ${pct(v, 1)}`).join('<br>')}`;
        tip.style.display = 'block'; const bx = box.getBoundingClientRect();
        tip.style.left = Math.min(bx.width - tip.offsetWidth - 4, Math.max(4, e.clientX - bx.left + 12)) + 'px'; tip.style.top = (e.clientY - bx.top + 12) + 'px';
      };
      s.querySelector('#hit').onmouseleave = () => { tip.style.display = 'none'; s.querySelector('#xh').style.display = 'none'; };
    });
    return `${legend}<div class="chart" id="lc">${svg}<div class="tip"></div></div>`;
  }

  // ---------------- 10. publishers
  function tabPublishers() {
    const P = D.pubs || [];
    const st = { active: ['فعال', 'good'], probation: ['در حال تست', 'warn'], dormant: ['بدون تبلیغ', 'mute'] };
    const src = { sheet: 'شیت شما', seed: 'لیست سیستم', discovered: 'کشف خودکار' };
    const cnt = P.reduce((a, p) => (a[p.source] = (a[p.source] || 0) + 1, a), {});
    return `<div class="card"><h3>پابلیشرها</h3><p class="hint">لیست شیت شما همیشه کامل اسکن می‌شود؛ لیست سیستم هر هفته از رنکینگ Tranco و لینک‌های بین پابلیشرها به‌روز می‌شود. سایتی که ۳ اسکن پیاپی تبلیغ نداشته باشد موقتاً کنار می‌رود و ماه بعد دوباره امتحان می‌شود.</p>
      <div style="margin-bottom:10px">${Object.entries(cnt).map(([k, v]) => chip(src[k] || k, v)).join('')} ${chip('کل', P.length)}</div>
      <input type="search" id="p-q" placeholder="جست‌وجوی سایت" style="margin-bottom:10px">
      <div class="tw"><table class="sortable" id="pt"><thead><tr><th class="sort">سایت</th><th class="sort">منبع</th><th class="sort">دسته</th><th class="sort">وضعیت</th><th class="sort">رتبهٔ Tranco</th><th class="sort">میانگین تبلیغ</th><th class="sort">اسکن</th><th class="sort">آخرین اسکن</th><th class="sort">امروز</th></tr></thead><tbody>
      ${P.map(p => `<tr><td class="ltr">${esc(p.domain)}</td><td>${esc(src[p.source] || p.source)}</td><td>${esc(fa('sitecat', p.cat_key || p.category))}</td><td><span class="pill st-${(st[p.status] || ['', 'mute'])[1]}">${esc((st[p.status] || [p.status])[0])}</span></td>
        <td class="num" data-s="${p.tranco || 9e9}">${p.tranco ? p.tranco.toLocaleString('en') : '—'}</td><td class="num" data-s="${p.avg_ads || 0}">${p.avg_ads ?? '—'}</td><td class="num">${p.scans || 0}</td><td class="ltr num">${esc(p.last_scan || '—')}</td>
        <td class="small">${p.today ? (p.today.ok ? `${p.today.slots} اسلات` : '<span class="muted">ناموفق</span>') : '<span class="muted">در صف دور بعد</span>'}</td></tr>`).join('')}</tbody></table></div></div>`;
  }

  // ---------------- 11. help & method
  function tabHelp() {
    const cov = Object.entries(D.coverage || {}).sort((a, b) => a[1].slots - b[1].slots).slice(0, 400);
    const G = [['SOV (سهم دیده‌شدن)', 'سهم وزن‌دار هر برند از حضور تبلیغاتی برندهای ای‌کامرس. جایگاه‌های پاپ‌آپ، استیکی، هدر و بالای صفحه وزن بیشتری دارند.'],
      ['حضور (Presence)', 'درصد صفحه‌های اسکن‌شده‌ای که برند حداقل یک بار در آن‌ها دیده شده؛ نزدیک‌ترین تخمین به Impression Share.'],
      ['فشار (0 تا 100)', 'شلوغی تبلیغاتی یک سایت: اسلات در صفحه 30٪، تعداد تبلیغ‌دهنده 20٪، تراکم رقبا 25٪، جایگاه ممتاز 10٪، چرخش کریتیو 15٪.'],
      ['فرصت (0 تا 100)', 'دسترسی سایت 35٪ + فشار پایین 35٪ + حضور رقبا به‌عنوان اثبات مخاطب 15٪ + قابل خرید بودن 15٪.'],
      ['تهدید رقیب (0 تا 100)', 'SOV ورتیکال 35٪ + رشد نسبت به ۷ روز 20٪ + پوشش سایت‌ها 20٪ + تهاجمی بودن (ریتارگتینگ، جایگاه ممتاز، پروموشن) 25٪.'],
      ['ریسک دسته', 'سهم پایین دیجی‌کالا 50٪ + قدرت رقیب اول 30٪ + تعداد رقبا 20٪.'],
      ['ریتارگتینگ', 'تبلیغ رقیبی که فقط در پروفایل «گرم» (بعد از بازدید از سایت رقبا) دیده شود، یا UTMهایی مثل retarget/dpa داشته باشد.'],
      ['هدف‌گیری مخاطب', 'UTMهایی مثل targeted/audience (مثلاً recommender_targeted یکتانت).'],
      ['دمای بید شبکه', 'سهم رقبا از تبلیغات یک شبکه؛ «داغ» یعنی رقابت سنگین در مزایده.']];
    return `<div class="row c2"><div class="card"><h3>واژه‌نامه</h3><dl class="kv">${G.map(([a, b]) => `<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join('')}</dl></div>
      <div class="card"><h3>روش کار</h3><ul class="bul small">
        <li>هر سایت در هر اجرا با سه پروفایل دیده می‌شود: موبایل بدون سابقه، دسکتاپ بدون سابقه و موبایل «گرم». فقط صفحهٔ اصلی بررسی می‌شود و کل صفحه اسکرول می‌شود تا اسلات‌های lazy لود شوند.</li>
        <li>ربات هیچ‌وقت روی تبلیغ کلیک نمی‌کند. لندینگ از لینک تبلیغ، داخل iframe یا پاسخ API شبکه خوانده و مستقیم و بدون UTM باز می‌شود.</li>
        <li>تبلیغ‌دهنده از دامنهٔ لندینگ، متن کریتیو یا تصویر آن (مدل vision رایگان) شناسایی می‌شود. فایل config/competitors.yaml همیشه حرف آخر را می‌زند.</li>
        <li>دادهٔ خام و اسکرین‌شات‌ها ۳ روز، و خلاصهٔ روزانه و اینسایت ماهانه ۳۱ روز نگه داشته می‌شوند.</li>
        <li>مدل‌های استفاده‌شده: <span class="ltr">${esc(D.meta.llm)}</span></li>
        <li>اعداد جهت‌دار هستند، نه سهم دقیق بازار. هر اسکن نمونه‌ای از تبلیغات چرخشی است و دقت با گذشت روزها بالا می‌رود.</li></ul>
        <p style="margin-top:12px"><button class="btn" id="csv">خروجی دادهٔ امروز (CSV)</button> ${D.meta.archive === false ? '' : '<a class="btn" href="archive.html" style="text-decoration:none;color:inherit">آرشیو گزارش‌ها</a>'}</p></div></div>
      <div class="card"><h3>پوشش اسکن</h3><p class="hint">«ادتک بدون تبلیغ» یعنی کد شبکه لود شده ولی اسلاتی پر نشده است. ممکن است اسلات خالی باشد، سایت SPA باشد یا تبلیغ به IP خارجی نمایش داده نشود. اگر تعداد این سایت‌ها زیاد است، PROXY_URL (پراکسی ایران) را تنظیم کنید.</p>
      <div class="tw"><table class="sortable"><thead><tr><th class="sort">سایت</th><th class="sort">صفحهٔ موفق</th><th class="sort">اسلات</th><th>ادتک</th><th>وضعیت</th><th>خطا</th></tr></thead><tbody>
      ${cov.map(([d, c]) => `<tr><td class="ltr">${esc(d)}</td><td class="num">${c.ok}/${c.pages}</td><td class="num">${c.slots}</td><td>${(c.adtech || []).map(n => chip(fa('network', n))).join('')}</td><td>${(D.geo_suspect || []).includes(d) ? '<span class="pill st-warn">ادتک بدون تبلیغ</span>' : ''}</td><td class="ltr small muted">${esc((c.errors || []).join('; '))}</td></tr>`).join('')}</tbody></table></div></div>`;
  }

  // ---------------- shell
  const TABS = [['ov', 'نمای کلی', tabOverview], ['plan', 'پیشنهاد رسانه', tabPlan], ['comp', 'رقبا و دسته‌ها', () => tabCompetitors() + tabCategories()],
    ['sites', 'سایت‌ها و شبکه‌ها', () => tabSites() + tabDiscovery()], ['cre', 'پیام و کریتیو', () => tabMessaging() + tabCreatives()],
    ['trend', 'روند ۳۰ روزه', tabTrends], ['help', 'پابلیشرها و راهنما', () => tabPublishers() + tabHelp()]];
  let cur = (location.hash || '#ov').slice(1); if (!TABS.some(t => t[0] === cur)) cur = 'ov';
  function renderAll() {
    $('#tabs').innerHTML = TABS.map(([k, n]) => `<button role="tab" data-t="${k}" class="${k === cur ? 'on' : ''}">${n}</button>`).join('');
    const t = TABS.find(t => t[0] === cur);
    $('#main').innerHTML = `<section class="tab on">${t[2]()}</section>`;
    $('#f-count').textContent = `${rowsF().length.toLocaleString('en')} از ${D.rows.length.toLocaleString('en')} مشاهدهٔ تبلیغ مطابق فیلتر`;
    bind();
  }
  function bind() {
    $$('#tabs button').forEach(b => b.onclick = () => { cur = b.dataset.t; try { history.replaceState(null, '', '#' + cur); } catch (e) { } renderAll(); window.scrollTo(0, 0); });
    $$('[data-go]').forEach(b => b.onclick = () => { cur = b.dataset.go; renderAll(); window.scrollTo(0, 0); });
    $$('tr[data-brand]').forEach(tr => { tr.tabIndex = 0; tr.onclick = () => openBrand(tr.dataset.brand); tr.onkeydown = e => { if (e.key === 'Enter') openBrand(tr.dataset.brand); }; });
    $$('.cr').forEach(c => c.onclick = () => openShot(c));
    const gb = $('#g-brand'); if (gb) { gb.onchange = e => { G.brand = e.target.value; renderAll(); }; $('#g-fmt').onchange = e => { G.fmt = e.target.value; renderAll(); };
      $('#g-net').onchange = e => { G.net = e.target.value; renderAll(); }; $('#g-sort').onchange = e => { G.sort = e.target.value; renderAll(); }; $('#g-q').onchange = e => { G.q = e.target.value.trim(); renderAll(); }; }
    $$('[data-brief]').forEach(b => b.onclick = e => { e.stopPropagation(); const t = briefText(D.media_plan[+b.dataset.brief]);
      copyOrShow(t, b, '✓ بریف کپی شد'); });
    const pc = $('#plan-csv'); if (pc) pc.onclick = () => csvDownload(['site', 'category', 'format', 'placement', 'device', 'route', 'bid', 'angle', 'objective', 'score', 'pressure', 'opportunity', 'confidence'],
      D.media_plan.map(p => [p.site, fa('category', p.category), fa('format', p.format), fa('placement', p.placement), fa('device', p.device), p.route, p.bid, p.angle, p.objective, p.score, p.pressure, p.opportunity, p.confidence]), `media-plan-${D.meta.date}.csv`, pc);
    const pq = $('#p-q'); if (pq) pq.oninput = e => { const q = e.target.value.trim(); $$('#pt tbody tr').forEach(r => r.style.display = r.innerText.includes(q) ? '' : 'none'); };
    const csv = $('#csv'); if (csv) csv.onclick = downloadCsv;
    $$('table.sortable').forEach(t => $$('th.sort', t).forEach(th => { let asc = false; th.onclick = () => {
      asc = !asc; const i = [...th.parentNode.children].indexOf(th); const rows = [...t.tBodies[0].rows];
      rows.sort((a, b) => { const x = a.cells[i], y = b.cells[i]; if (!x || !y) return 0; const xa = x.dataset.s ?? x.innerText, ya = y.dataset.s ?? y.innerText; const nx = parseFloat(xa), ny = parseFloat(ya);
        const r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : String(xa).localeCompare(String(ya), 'fa'); return asc ? r : -r; });
      rows.forEach(r => t.tBodies[0].appendChild(r)); }; }));
  }
  // copy to clipboard (works everywhere); if refused, show the text selected in a box so it can be copied by hand
  function copyOrShow(text, btn, okLabel) {
    const fallback = () => { $('#lb').innerHTML = `<button class="x" data-close>✕</button><p class="small muted">کپی خودکار مجاز نبود؛ متن انتخاب شده است، با Ctrl/Cmd+C کپی کنید.</p><textarea id="copybox" style="width:100%;height:50vh;background:var(--s2);color:var(--ink);border:1px solid var(--ring);border-radius:9px;padding:10px;direction:rtl">${esc(text)}</textarea>`;
      $('#ov').classList.add('on'); const t = $('#copybox'); t.focus(); t.select(); };
    try { (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => { const o = btn.textContent; btn.textContent = okLabel; setTimeout(() => btn.textContent = o, 2200); }, fallback); } catch (e) { fallback(); }
  }
  function csvDownload(head, rows, name, btn) {
    const q = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const csv = [head.join(',')].concat(rows.map(r => r.map(q).join(','))).join('\n');
    try { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv' })); a.download = name; a.click(); } catch (e) { }
    if (btn) copyOrShow(csv, btn, '✓ CSV کپی شد (در اکسل/شیت Paste کنید)');
  }
  function downloadCsv(e) {
    const cols = [['b', 'brand'], ['l', 'level'], ['v', 'vertical'], ['c', 'category'], ['s', 'site'], ['n', 'network'], ['f', 'format'], ['p', 'placement'], ['d', 'device'], ['dp', 'daypart'], ['t', 'title'], ['ld', 'landing_domain'], ['u', 'utm_campaign'], ['sz', 'size']];
    const q = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const body = [cols.map(c => c[1]).join(',')].concat(rowsF().map(r => cols.map(c => q(r[c[0]])).join(','))).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + body], { type: 'text/csv' })); a.download = `ad-radar-${D.meta.date}.csv`; a.click();
  }
  document.addEventListener('click', e => { if (e.target.closest('[data-close]') || e.target.id === 'scrim' || e.target.id === 'ov') { $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); $('#ov').classList.remove('on'); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); $('#ov').classList.remove('on'); } });
  renderFilters(); renderAll();
})();
