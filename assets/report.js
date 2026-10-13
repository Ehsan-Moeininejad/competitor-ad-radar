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
      ${decisions()}
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

  // decision board: what to attack, defend and test today (each line links to the tab with the evidence)
  function decisions() {
    const atk = (D.media_plan || []).filter(p => ['خرید مستقیم', 'بید پایین در شبکه', 'شکاف حضور'].includes(p.recommendation)).slice(0, 3)
      .map(p => [`<b>${esc(fa('category', p.category))}</b> روی <bdi dir="ltr">${esc(p.site)}</bdi> با ${esc(fa('format', p.format))} · ${esc(p.bid)}`, 'plan']);
    const def = [];
    Object.entries(D.competitors).filter(([, c]) => c.surge && c.level !== 'own').slice(0, 2).forEach(([b, c]) => def.push([`جهش <b>${esc(b)}</b>: سهم ${pct(c.sov, 1)} (میانگین ۷ روز ${pct(c.sov_7d, 1)})؛ بید دسته‌های مشترک را حفظ کنید`, 'comp']));
    (D.campaigns || []).filter(c => c.new && c.level === 'core').slice(0, 2).forEach(c => def.push([`کمپین تازهٔ <b>${esc(c.brand)}</b>: <bdi dir="ltr">${esc(c.campaign)}</bdi> در ${c.sites.length} سایت`, 'camp']));
    Object.entries(D.offer_bench || {}).filter(([, e]) => (e.discount && e.discount.v > ((e.own || {}).discount || 0)) || (e.months && e.months.v > ((e.own || {}).months || 0))).slice(0, 2)
      .forEach(([k, e]) => def.push([`آفر رقبا در <b>${esc(fa('category', k))}</b> قوی‌تر است${e.discount ? `: تا ${e.discount.v}% (${esc(e.discount.brand)})` : ''}${e.months ? `${e.discount ? '،' : ':'} اقساط ${e.months.v} ماهه (${esc(e.months.brand)})` : ''}`, 'msg']));
    const rt = Object.entries(D.competitors).filter(([, c]) => c.level === 'core' && c.retargeting_sites.length);
    if (rt.length) def.push([`ریتارگتینگ ${rt.slice(0, 3).map(([b]) => esc(b)).join('، ')}: کاربران بازدیدکننده را با ریتارگتینگ دیجی‌کالا روی همین شبکه‌ها پس بگیرید`, 'comp']);
    const tst = ((D.discovery || {}).new_units || []).slice(0, 2).map(u => [`جایگاه تازه: ${esc(fa('placement', u.placement))} / ${esc(fa('format', u.format))} روی <bdi dir="ltr">${esc(u.site)}</bdi> (${esc(fa('device', u.device))})`, 'sites']);
    ((D.discovery || {}).new_networks || []).slice(0, 1).forEach(n => tst.push([`شبکهٔ تازه ${esc(fa('network', n.network))} روی <bdi dir="ltr">${esc(n.site)}</bdi>: قیمت و اینونتوری را استعلام کنید`, 'sites']));
    (D.long_running || []).filter(x => (D.competitors[x.brand] || {}).level !== 'own' && x.days >= 3).slice(0, 1).forEach(x => tst.push([`ایدهٔ کریتیو: «${esc((x.title || '').slice(0, 60))}» از ${esc(x.brand)} ${x.days} روز است اجرا می‌شود (احتمالاً برنده)`, 'cre']));
    const col = (t, cls, items, em) => `<div class="dcol d-${cls}"><h4>${t}</h4>${items.length ? `<ul>${items.slice(0, 4).map(([h, go]) => `<li data-go="${go}" tabindex="0">${h}</li>`).join('')}</ul>` : `<p class="muted small">${em}</p>`}</div>`;
    return `<div class="card"><h3>تصمیم‌های امروز</h3><p class="hint">خلاصهٔ اقدام برای تیم پرفورمنس؛ روی هر مورد بزنید تا شواهدش باز شود.</p><div class="dboard">
      ${col('حمله: کجا وارد شویم', 'atk', atk, 'فرصت کم‌تراکم تازه‌ای نیست.')}${col('دفاع: به چه واکنش نشان دهیم', 'def', def, 'تهدید فوری دیده نشد.')}${col('تست: چه چیز تازه‌ای امتحان کنیم', 'tst', tst, 'جایگاه یا شبکهٔ تازه‌ای دیده نشد.')}</div></div>`;
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
        <td class="num" data-s="${c.presence}">${pct(c.presence, 1)}</td><td class="num" data-s="${sites[b].size}">${sites[b].size}</td><td class="num" data-s="${ads[b]}">${ads[b]}</td><td class="num" data-s="${c.cr_new || 0}">${c.cr_new ? `<b style="color:${c.cr_new >= 0.5 * (c.cr_active || 1) ? 'var(--serious)' : 'var(--ink)'}">${c.cr_new}</b>` : '0'}<span class="muted">/${c.cr_active || 0}</span></td>
        <td data-s="${c.threat}">${c.level === 'own' ? '—' : meter(c.threat, false, 'تهدید')}</td><td>${chips(c.networks, 'network', 2)}</td><td>${chips(c.campaign_types, 'campaign', 2)}</td></tr>`;
    }).join('');
    return `<div class="card"><h3>رقبا</h3><p class="hint">روی هر ردیف بزنید تا جزئیات کامل (سایت‌ها، فرمت‌ها، پیام‌ها، کریتیوها، روند ۳۰ روزه) باز شود. «حضور» = درصد صفحه‌های اسکن‌شده که این برند در آن دیده شده (نزدیک به Impression Share).</p>
      <div class="tw"><table class="sortable"><thead><tr><th class="sort">برند</th><th class="sort">سطح</th><th class="sort">ورتیکال</th><th class="sort" title="سهم وزن‌دار دیده‌شدن بین برندهای ای‌کامرس؛ تعداد مشاهده است، نه هزینه">SOV ⓘ</th><th class="sort">SOV ورتیکال</th><th>تغییر ۷ روز</th><th class="sort" title="درصد صفحه‌های اسکن‌شده‌ای که برند در آن دیده شد (≈ Impression Share)">حضور ⓘ</th><th class="sort">سایت</th><th class="sort">تبلیغ</th><th class="sort" title="کریتیوهای تازهٔ امروز / کل کریتیوهای فعال امروز. نسبت بالا = شروع موج کمپین یا تست کریتیو">کریتیو تازه ⓘ</th><th class="sort" title="SOV ورتیکال 35٪ + رشد 20٪ + پوشش سایت 20٪ + تهاجمی بودن 25٪">تهدید ⓘ</th><th>شبکه</th><th>نوع کمپین</th></tr></thead>
      <tbody>${body || `<tr><td colspan="13">${empty('رقیبی برای این فیلتر دیده نشد.')}</td></tr>`}</tbody></table></div></div>`;
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
      ${(() => { const cs = (D.campaigns || []).filter(x => x.brand === b); const T = (D.utm || {}).tags_fa || {}; return cs.length ? `<dt>کمپین‌ها (UTM)</dt><dd>${cs.slice(0, 6).map(x => `<div class="click" data-camp="${esc(x.brand + '|' + x.campaign)}" style="margin-bottom:3px"><bdi dir="ltr" style="color:#86b6ef">${esc(x.campaign)}</bdi>${x.new ? ' <span class="bdg b-new">NEW</span>' : ''} <span class="muted small">${x.tags.slice(0, 2).map(t => T[t] || t).join('، ')}</span></div>`).join('')}<button class="btn" data-gobrand="${esc(b)}">همهٔ کمپین‌های ${esc(b)} ←</button></dd>` : ''; })()}
      <dt>کریتیو</dt><dd>${c.cr_active || 0} فعال · ${c.cr_new || 0} تازهٔ امروز</dd>
      ${c.landing_types && Object.keys(c.landing_types).length ? `<dt>نوع لندینگ</dt><dd>${chips(c.landing_types, 'landing')}</dd>` : ''}
      <dt>روند ۳۰ روز</dt><dd>${series.length > 1 ? spark(series, color(b)) : '<span class="muted">از روز دوم ساخته می‌شود</span>'}</dd></dl>
      ${respond(b, c)}
      <h3 style="font-size:14px">زمان و دستگاه</h3>${dpGrid(rows)}
      <h3 style="font-size:14px">متن‌های تبلیغ</h3><ul class="bul small">${c.top_titles.map(t => `<li>${esc(t)}</li>`).join('') || '<li class="muted">—</li>'}</ul>
      <h3 style="font-size:14px;margin-top:12px">کریتیوها</h3><div class="shots">${shots.map(r => `<figure class="shot"><div class="frame"><img src="${img(r.sh)}" alt=""></div><figcaption class="small"><bdi dir="ltr">${esc(r.s)}</bdi> · ${esc(fa('placement', r.p))}</figcaption></figure>`).join('') || empty('اسکرین‌شاتی نیست.')}</div>`;
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
  function offerBench() {
    const ob = Object.entries(D.offer_bench || {}).filter(([k]) => !F.cat || k === F.cat);
    if (!ob.length) return empty('امروز آفری روی لندینگ رقبا خوانده نشد.');
    const who = x => x ? `<b>${x.v}${x.unit || ''}</b> <span class="muted small">${esc(x.brand)}</span>` : '<span class="muted">—</span>';
    const list = a => a && a.length ? a.slice(0, 3).map(esc).join('، ') + (a.length > 3 ? ` +${a.length - 3}` : '') : '<span class="muted">—</span>';
    return `<div class="tw"><table><thead><tr><th>دسته</th><th title="بیشترین درصد تخفیفی که رقبا روی کریتیو یا لندینگ اعلام کرده‌اند">بیشترین تخفیف رقبا</th><th>طولانی‌ترین اقساط</th><th>بدون پیش‌پرداخت</th><th>ارسال رایگان</th><th>کد تخفیف / تایمر</th><th>دیجی‌کالا امروز</th><th>وضعیت آفر</th></tr></thead><tbody>
      ${ob.map(([k, e]) => {
        const own = e.own || {}, d = e.discount, m = e.months;
        const behind = (d && d.v > (own.discount || 0)) || (m && m.v > (own.months || 0)) || ((e.no_prepay || []).length && !(own.flags || []).includes('no_prepay'));
        const ownTxt = [own.discount ? `تخفیف ${own.discount}%` : '', own.months ? `اقساط ${own.months} ماهه` : '', ...(own.flags || []).map(f => fa('campaign', f))].filter(Boolean).join('، ') || '<span class="muted">آفری دیده نشد</span>';
        return `<tr><td>${esc(fa('category', k))}</td><td>${who(d && { ...d, unit: '%' })}</td><td>${who(m && { ...m, unit: ' ماه' })}</td><td class="small">${list(e.no_prepay)}</td><td class="small">${list(e.free_shipping)}</td>
          <td class="small">${list([...new Set([...(e.voucher || []), ...(e.countdown || [])])])}</td><td class="small">${ownTxt}</td><td>${behind ? '<span class="pill st-crit">آفر رقبا قوی‌تر</span>' : '<span class="pill st-good">رقابتی</span>'}</td></tr>`;
      }).join('')}</tbody></table></div>`;
  }
  function tabMessaging() {
    const m = D.messaging || {}, T = m.themes_fa || {};
    const mk = Object.entries(m.market || {}).map(([k, v]) => [T[k] || k, v]);
    const brands = Object.entries(m.by_brand || {}).filter(([b]) => D.competitors[b]).slice(0, 14);
    const themes = Object.keys(T);
    const offers = Object.entries(D.competitors).filter(([, c]) => Object.keys(c.offers || {}).length).map(([b, c]) => `<tr><td>${brandCell(b)}</td><td>${chips(c.offers, 'campaign', 6)}</td></tr>`).join('');
    return `<div class="card"><h3>بنچمارک آفر: آفری که باید از آن بهتر بود</h3><p class="hint">قوی‌ترین آفر رقبا در هر دسته (از متن کریتیو و صفحهٔ لندینگ) در کنار آفر امروز دیجی‌کالا. «آفر رقبا قوی‌تر» یعنی پیش از افزایش بید، آفر یا پیام را تقویت کنید.</p>${offerBench()}</div>
      <div class="row c2"><div class="card"><h3>پیام غالب بازار</h3><p class="hint">تعداد کریتیوهای رقبا با هر مضمون</p>${hbars(mk, () => '#d95926', v => v)}</div>
      <div class="card"><h3>شکاف پیام دیجی‌کالا</h3><p class="hint">مضمون‌هایی که رقبا استفاده می‌کنند و در کریتیوهای دیجی‌کالا امروز دیده نشد</p>
        ${(m.gaps || []).length ? `<ul class="bul">${m.gaps.map(g => `<li><b>${esc(T[g] || g)}</b>: پیشنهاد زاویه — ${esc((D.angles || {})[g] || '')}</li>`).join('')}</ul>` : empty('شکافی دیده نشد.')}
        <h3 style="margin-top:12px">CTAهای پرتکرار</h3><div>${(m.ctas || []).map(c => chip(c)).join('') || '<span class="muted">—</span>'}</div></div></div>
      <div class="row c32"><div class="card"><h3>مضمون پیام هر رقیب</h3><div class="tw"><table><thead><tr><th>برند</th>${themes.map(t => `<th>${esc(T[t])}</th>`).join('')}</tr></thead><tbody>
        ${brands.map(([b, c]) => `<tr><td>${brandCell(b)}</td>${themes.map(t => `<td class="num">${c[t] || ''}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="9">${empty('—')}</td></tr>`}</tbody></table></div></div>
      <div class="card"><h3>آفرهای لندینگ هر رقیب</h3><p class="hint">اقساط، ارسال رایگان، تایمر، کد تخفیف، گیمیفیکیشن</p>${offers ? `<div class="tw"><table><tbody>${offers}</tbody></table></div>` : empty('—')}
        <p class="small muted" style="margin-top:10px">نام کمپین‌ها و پارامترهای UTM در تب «کمپین‌ها و UTM» جمع شده‌اند. <button class="btn" data-go="camp">رفتن به کمپین‌ها ←</button></p></div></div>`;
  }

  // ---------------- 8. creatives
  const G = { brand: '', fmt: '', net: '', sort: 'new', q: '', quick: '', view: 'grid' };
  let CARDS = [], LB = -1;
  const isNew = r => r.fs === D.meta.date || (r.dy || 1) <= 1;
  const isRt = g => g.rt;
  function creativeGroups() {
    const groups = new Map();
    // one card per creative: same brand + same text (or same landing/format/placement for image-only banners); prefer a mobile screenshot
    rowsF().filter(r => (!G.brand || r.b === G.brand) && (!G.fmt || r.f === G.fmt) && (!G.net || r.n === G.net) && (!G.q || (r.t + ' ' + r.b + ' ' + r.s + ' ' + (r.u || '')).toLowerCase().includes(G.q.toLowerCase())))
      .forEach(r => { if (!r.sh && !r.t) return; const k = r.b + '|' + (r.t || (r.ld + '|' + r.f + '|' + r.p));
        const g = groups.get(k) || { r, n: 0, sites: new Set(), rows: [], rt: false, warmOnly: true }; g.n++; g.sites.add(r.s); g.rows.push(r);
        if ((r.ct || []).includes('retargeting')) g.rt = true; if (!r.w) g.warmOnly = false;
        if ((!img(g.r.sh) && img(r.sh)) || (img(r.sh) && r.d === 'mobile' && g.r.d !== 'mobile')) g.r = r; groups.set(k, g); });
    const all = [...groups.values()];
    all.forEach(g => { if (g.warmOnly && g.rows.length) g.rt = true; g.utm = g.rows.find(x => x.u || (x.ut && x.ut.c)); });
    return all;
  }
  const QUICK = [['', 'همه'], ['new', 'جدید امروز', g => isNew(g.r)], ['long', 'پرعمر (۳+ روز)', g => (g.r.dy || 1) >= 3], ['rt', 'ریتارگتینگ', isRt], ['offer', 'دارای آفر', g => !!g.r.of], ['utm', 'دارای UTM', g => !!g.utm], ['noimg', 'بدون تصویر', g => !img(g.r.sh)]];
  function tabCreatives() {
    const all = creativeGroups();
    const qf = QUICK.find(q => q[0] === G.quick);
    const sorter = { new: (a, b) => (isNew(b.r) ? 1 : 0) - (isNew(a.r) ? 1 : 0) || b.n - a.n, freq: (a, b) => b.n - a.n, sites: (a, b) => b.sites.size - a.sites.size || b.n - a.n, long: (a, b) => (b.r.dy || 1) - (a.r.dy || 1) || b.n - a.n }[G.sort];
    CARDS = all.filter(g => !qf || !qf[2] || qf[2](g)).sort((a, b) => (G.quick === 'noimg' ? 0 : (img(b.r.sh) ? 1 : 0) - (img(a.r.sh) ? 1 : 0)) || sorter(a, b)).slice(0, 240);
    const nets = [...new Set(D.rows.map(r => r.n))];
    const brands = [...new Set(D.rows.filter(r => ['core', 'vertical', 'own'].includes(r.l)).map(r => r.b))].sort();
    const fmts = [...new Set(D.rows.map(r => r.f))];
    const lr = (D.long_running || []).map(x => `<tr><td>${brandCell(x.brand)}</td><td><div style="display:flex;align-items:center;gap:10px">${x.shot_key && img(x.shot_key) ? `<span class="thumbw"><img src="${img(x.shot_key)}" alt=""></span>` : ''}<span>${esc(x.title || '')}</span></div></td><td class="num" data-s="${x.days}">${x.days}</td><td class="ltr num">${esc(x.first_seen)}</td><td class="num">${x.sites}</td></tr>`).join('');
    const quick = QUICK.map(([k, n, f]) => `<button class="qf ${G.quick === k ? 'on' : ''}" data-q="${k}"><bdi>${esc(n)}</bdi> <b>${f ? all.filter(f).length : all.length}</b></button>`).join('');
    const body = !CARDS.length ? empty('کریتیوی برای این فیلتر نیست.') : G.view === 'list' ? creativeList() : `<div class="gallery">${CARDS.map(creativeCard).join('')}</div>`;
    return `<div class="card"><div class="gh">
        <div><h3 style="margin:0">گالری کریتیو</h3><p class="hint" style="margin:2px 0 0">${all.length} کریتیو یکتا (تکراری‌ها ادغام شده) · برای جزئیات، UTM و کریتیو بعدی/قبلی روی کارت بزنید</p></div>
        <div class="seg" role="group" aria-label="نمایش"><button data-view="grid" class="${G.view === 'grid' ? 'on' : ''}">کارتی</button><button data-view="list" class="${G.view === 'list' ? 'on' : ''}">فهرستی</button></div></div>
      <div class="gtools">
        <select id="g-brand" aria-label="برند"><option value="">همهٔ برندها</option>${brands.map(b => `<option ${G.brand === b ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select>
        <select id="g-fmt" aria-label="فرمت"><option value="">همهٔ فرمت‌ها</option>${fmts.map(f => `<option value="${f}" ${G.fmt === f ? 'selected' : ''}>${esc(fa('format', f))}</option>`).join('')}</select>
        <select id="g-net" aria-label="شبکه"><option value="">همهٔ شبکه‌ها</option>${nets.map(n => `<option value="${n}" ${G.net === n ? 'selected' : ''}>${esc(fa('network', n))}</option>`).join('')}</select>
        <select id="g-sort" aria-label="مرتب‌سازی"><option value="new" ${G.sort === 'new' ? 'selected' : ''}>اول جدیدها</option><option value="freq" ${G.sort === 'freq' ? 'selected' : ''}>پرتکرارترین</option><option value="sites" ${G.sort === 'sites' ? 'selected' : ''}>بیشترین سایت</option><option value="long" ${G.sort === 'long' ? 'selected' : ''}>طولانی‌ترین اجرا</option></select>
        <input type="search" id="g-q" placeholder="جست‌وجو در متن، برند، سایت یا UTM" value="${esc(G.q)}">
        <button class="btn" id="g-copy">کپی متن کریتیوها (CSV)</button></div>
      <div class="qfs">${quick}</div>
      ${body}</div>
      <div class="card"><h3>کریتیوهای پرعمر</h3><p class="hint">کریتیوی که روزهای بیشتری اجرا شده احتمالاً بازده خوبی برای رقیب دارد؛ مرجع خوبی برای بریف تیم کریتیو (سابقهٔ ۳۰ روز)</p>
      ${lr ? `<div class="tw"><table class="sortable"><thead><tr><th>برند</th><th>کریتیو</th><th class="sort">روز اجرا</th><th>اولین مشاهده</th><th>سایت</th></tr></thead><tbody>${lr}</tbody></table></div>` : empty('—')}</div>`;
  }
  const stat = (n, label) => `<span class="st"><b>${n}</b><small>${label}</small></span>`;
  function creativeCard(g, i) {
    const r = g.r, s = img(r.sh), lvl = (D.competitors[r.b] || {}).level || r.l;
    const camp = g.utm ? (g.utm.u || g.utm.ut.c) : '';
    return `<article class="cr" tabindex="0" data-i="${i}" aria-label="${esc(r.b)}: ${esc(r.t || 'کریتیو تصویری')}">
      <div class="frame">${s ? `<img src="${s}" alt="" loading="lazy">` : `<div class="noimg">${esc(r.t || 'بدون تصویر')}</div>`}
        <div class="badges">${isNew(r) ? '<span class="bdg b-new">جدید امروز</span>' : ''}${(r.dy || 1) >= 3 ? `<span class="bdg b-long">${r.dy} روز</span>` : ''}${g.rt ? '<span class="bdg b-rt">ریتارگتینگ</span>' : ''}</div>
        <span class="fmt">${esc(fa('format', r.f))}</span></div>
      <div class="meta"><div class="b"><span class="bn"><i class="dot" style="background:${color(r.b)}"></i>${esc(r.b)}</span><span class="lvl">${esc(fa('level', lvl))}</span></div>
        <div class="t">${r.t ? esc(r.t) : '<span class="muted">بدون متن · فقط تصویر</span>'}</div>
        <div class="stats">${stat(g.n, 'بار دیده‌شده')}${stat(g.sites.size, 'سایت')}${stat(r.dy || 1, 'روز اجرا')}</div>
        <div class="where">${esc(fa('placement', r.p))} · ${esc(fa('device', r.d))} · ${esc(fa('network', r.n))}${r.c && r.c !== 'other' ? ' · ' + esc(fa('category', r.c)) : ''}</div>
        ${r.of ? `<div class="offer">${esc(r.of)}</div>` : ''}${camp ? `<div class="utmc"><span>UTM</span><bdi dir="ltr">${esc(camp)}</bdi></div>` : ''}</div></article>`;
  }
  function creativeList() {
    return `<div class="tw" style="max-height:none"><table class="crlist"><thead><tr><th>کریتیو</th><th>برند</th><th>متن</th><th>فرمت / جایگاه</th><th class="num">دیده‌شدن</th><th class="num">سایت</th><th class="num">روز</th><th>UTM</th></tr></thead><tbody>
      ${CARDS.map((g, i) => { const r = g.r, s = img(r.sh); return `<tr class="click cr" data-i="${i}" tabindex="0"><td><span class="thumbw">${s ? `<img src="${s}" alt="" loading="lazy">` : '<span class="muted small">متنی</span>'}</span></td>
        <td>${brandCell(r.b)}${isNew(r) ? ' <span class="bdg b-new">جدید</span>' : ''}${g.rt ? ' <span class="bdg b-rt">RT</span>' : ''}</td><td style="min-width:200px">${esc(r.t || '—')}${r.of ? `<div class="small" style="color:var(--warn)">${esc(r.of)}</div>` : ''}</td>
        <td class="small">${esc(fa('format', r.f))}<br><span class="muted">${esc(fa('placement', r.p))} · ${esc(fa('device', r.d))}</span></td><td class="num">${g.n}</td><td class="num">${g.sites.size}</td><td class="num">${r.dy || 1}</td>
        <td class="ltr small">${esc(g.utm ? (g.utm.u || g.utm.ut.c || '') : '')}</td></tr>`; }).join('')}</tbody></table></div>`;
  }
  const UTMK = [['s', 'source'], ['m', 'medium'], ['c', 'campaign'], ['ct', 'content'], ['tm', 'term'], ['id', 'id']];
  function utmTable(rows) {
    const seen = new Map();
    rows.forEach(x => { const u = x.ut || (x.u ? { c: x.u } : null); if (!u) return; const k = JSON.stringify(u); const e = seen.get(k) || { u, n: 0, sites: new Set() }; e.n++; e.sites.add(x.s); seen.set(k, e); });
    if (!seen.size) return '<span class="muted">این کریتیو UTM نداشت (رقیب احتمالاً با click-id شبکه یا پیکسل می‌سنجد).</span>';
    return `<div class="tw"><table class="small"><thead><tr>${UTMK.map(k => `<th class="ltr">utm_${k[1]}</th>`).join('')}<th>تعداد</th><th>سایت</th></tr></thead><tbody>
      ${[...seen.values()].map(e => `<tr>${UTMK.map(k => `<td class="ltr">${esc(e.u[k[0]] || '—')}</td>`).join('')}<td class="num">${e.n}</td><td class="ltr">${esc([...e.sites].join(', '))}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function openShot(i) {
    const g = CARDS[i]; if (!g) return; LB = i;
    const r = g.r, all = g.rows, s = img(r.sh);
    const sites = Object.entries(all.reduce((a, x) => (a[x.s] = (a[x.s] || 0) + 1, a), {})).sort((a, b) => b[1] - a[1]);
    const camp = all.find(x => x.u || (x.ut && x.ut.c)); const cname = camp ? (camp.u || camp.ut.c) : '';
    const C = cname ? (D.campaigns || []).find(c => c.brand === r.b && c.campaign === cname) : null;
    const T = (D.utm || {}).tags_fa || {};
    $('#lb').innerHTML = `<div class="lbh"><h3 style="margin:0">${brandCell(r.b)} <span class="muted small">· ${esc(fa('level', (D.competitors[r.b] || {}).level || r.l))}</span></h3>
        <div class="lbn"><button class="btn" data-nav="-1" ${i <= 0 ? 'disabled' : ''} aria-label="قبلی">→ قبلی</button><span class="muted small">${i + 1} از ${CARDS.length}</span><button class="btn" data-nav="1" ${i >= CARDS.length - 1 ? 'disabled' : ''} aria-label="بعدی">بعدی ←</button><button class="x" data-close aria-label="بستن">✕</button></div></div>
      <div class="lbg"><div class="big">${s ? `<img src="${s}" alt="">` : `<div class="noimg" style="font-size:15px">${esc(r.t || 'بدون تصویر')}</div>`}</div>
      <div><div class="stats" style="margin-bottom:8px">${stat(all.length, 'بار دیده‌شده')}${stat(g.sites.size, 'سایت')}${stat(r.dy || 1, 'روز اجرا')}</div>
      <dl class="kv"><dt>متن</dt><dd>${esc(r.t || '—')} ${r.t ? `<button class="btn" data-copy="${esc(r.t)}" style="padding:0 8px">کپی</button>` : ''}</dd>
      <dt>فرمت / جایگاه</dt><dd>${esc(fa('format', r.f))} · ${esc(fa('placement', r.p))} · <bdi dir="ltr">${esc(r.sz || '')}</bdi></dd><dt>شبکه</dt><dd>${[...new Set(all.map(x => fa('network', x.n)))].map(esc).join('، ')}</dd>
      <dt>دستگاه / زمان</dt><dd>${[...new Set(all.map(x => fa('device', x.d)))].join('، ')} · ${[...new Set(all.map(x => fa('daypart', x.dp)))].join('، ')}</dd>
      <dt>نوع کمپین</dt><dd>${[...new Set(all.flatMap(x => x.ct || []))].map(c => chip(fa('campaign', c))).join('') || '—'}${g.warmOnly ? ' <span class="pill st-warn">فقط در پروفایل گرم</span>' : ''}</dd>
      <dt>دستهٔ کالا</dt><dd>${esc(fa('category', r.c))}</dd><dt>اولین / آخرین</dt><dd><bdi dir="ltr">${esc(r.fs || D.meta.date)} → ${esc(r.ls || D.meta.date)}</bdi></dd>
      ${r.of ? `<dt>آفر</dt><dd style="color:var(--warn)">${esc(r.of)}</dd>` : ''}
      ${r.ld ? `<dt>لندینگ</dt><dd class="ltr">${esc(r.ld)}${r.lt ? ' · ' + esc(fa('landing', r.lt)) : ''}</dd>` : ''}
      ${C ? `<dt>کمپین</dt><dd><bdi dir="ltr">${esc(C.campaign)}</bdi> ${C.tags.map(t => `<span class="tagp">${esc(T[t] || t)}</span>`).join('')}<div class="small muted">${C.ads} تبلیغ در ${C.sites.length} سایت · ${C.days} روز فعال از ${esc(C.first_seen)}</div></dd>` : ''}
      <dt>سایت‌ها</dt><dd class="small">${sites.map(([d, n]) => `<bdi dir="ltr">${esc(d)}</bdi> <span class="muted">×${n}</span>`).join(' · ')}</dd></dl></div></div>
      <h3 style="font-size:14px;margin:12px 0 6px">پارامترهای UTM این کریتیو</h3>${utmTable(all)}`;
    $('#ov').classList.add('on');
  }

  // ---------------- 8b. campaigns & UTM
  const K = { brand: '', tag: '', med: '', q: '', fresh: false };
  function campsF() {
    return (D.campaigns || []).filter(c => (F.lvl === 'all' || (F.lvl === 'rivals' ? true : c.level === F.lvl)) && (!F.cat || (c.categories || {})[F.cat]) && (!F.dev || (c.devices || {})[F.dev])
      && (!K.brand || c.brand === K.brand) && (!K.tag || c.tags.includes(K.tag)) && (!K.med || (c.mediums || {})[K.med]) && (!K.fresh || c.new)
      && (!K.q || (c.campaign + ' ' + c.brand + ' ' + c.contents.join(' ') + ' ' + Object.keys(c.sources).join(' ')).toLowerCase().includes(K.q.toLowerCase())));
  }
  function tabCampaigns() {
    const U = D.utm || {}, T = U.tags_fa || {}, MF = U.medium_fa || {};
    if (!(D.campaigns || []).length) return `<div class="card">${empty('امروز روی لینک تبلیغات رقبا پارامتر UTM دیده نشد. برخی شبکه‌ها (مثل یکتانت) UTM را فقط بعد از ریدایرکت اضافه می‌کنند؛ رادار آن را از لینک مقصد می‌خواند.')}</div>`;
    const list = campsF();
    const brands = [...new Set((D.campaigns || []).map(c => c.brand))].sort();
    const tags = [...new Set((D.campaigns || []).flatMap(c => c.tags))];
    const meds = [...new Set((D.campaigns || []).flatMap(c => Object.keys(c.mediums || {})))];
    const fresh = (D.campaigns || []).filter(c => c.new && c.level !== 'own');
    const tp = t => `<span class="tagp t-${t}">${esc(T[t] || t)}</span>`;
    const kv = (o, map) => Object.entries(o || {}).map(([k, n]) => `<bdi dir="ltr">${esc(map ? (map[k] || k) : k)}</bdi>${n > 1 ? ` <span class="muted">×${n}</span>` : ''}`).join('<br>') || '<span class="muted">—</span>';
    const tiles = [['کمپین فعال امروز', U.active, 'هر نام utm_campaign یکتا برای هر برند'], ['کمپین تازه', U.baseline ? '—' : U.new, U.baseline ? 'از اجرای دوم محاسبه می‌شود' : 'نام کمپینی که امروز اولین بار دیده شد'],
      ['پوشش UTM', pct(U.coverage), 'سهم تبلیغات رقبا و دیجی‌کالا که UTM داشتند'], ['برند با UTM', Object.values(U.by_brand || {}).filter(b => b.tagged).length, 'از ' + Object.keys(U.by_brand || {}).length + ' برند']]
      .map(([l, v, h]) => `<div class="kpi" title="${esc(h)}"><span>${esc(l)}</span><b>${esc(v)}</b><small>${esc(h)}</small></div>`).join('');
    const freshCards = fresh.slice(0, 8).map(c => `<div class="camp click" data-camp="${esc(c.brand + '|' + c.campaign)}" tabindex="0">${c.shots[0] && img(c.shots[0]) ? `<span class="thumbw lg"><img src="${img(c.shots[0])}" alt=""></span>` : ''}
      <div style="min-width:0"><div>${brandCell(c.brand)}</div><div class="cn"><bdi dir="ltr">${esc(c.campaign)}</bdi></div><div>${c.tags.map(tp).join('')}</div>
      <div class="small muted">${c.ads} تبلیغ · ${c.sites.length} سایت · ${Object.keys(c.mediums || {}).map(m => MF[m] || m).join('، ') || '—'}</div></div></div>`).join('');
    const rows = list.map(c => `<tr class="click" data-camp="${esc(c.brand + '|' + c.campaign)}" tabindex="0"><td>${brandCell(c.brand)}</td><td class="ltr" style="max-width:240px;overflow-wrap:anywhere"><b>${esc(c.campaign)}</b>${c.new ? ' <span class="bdg b-new">NEW</span>' : ''}</td>
      <td>${c.tags.map(tp).join('') || '<span class="muted small">نامشخص</span>'}</td><td class="small">${kv(c.sources)}</td><td class="small">${kv(c.mediums, MF)}</td>
      <td class="small ltr" style="max-width:200px;overflow-wrap:anywhere">${esc(c.contents.slice(0, 3).join(' · ') || '—')}${c.contents.length > 3 ? ` +${c.contents.length - 3}` : ''}</td>
      <td class="num" data-s="${c.sites.length}">${c.sites.length}</td><td class="small">${Object.keys(c.networks).map(n => esc(fa('network', n))).join('، ')}</td><td class="num" data-s="${c.ads}">${c.ads}</td>
      <td class="num" data-s="${c.days}">${c.days}</td><td class="num ltr">${esc(c.first_seen.slice(5))}</td></tr>`).join('');
    const hyg = Object.entries(U.by_brand || {}).filter(([b]) => D.competitors[b]).map(([b, x]) => `<tr><td>${brandCell(b)}</td><td class="num" data-s="${x.share}">${meter(Math.round(x.share * 100), true, 'پوشش UTM')}</td><td class="num">${x.tagged}/${x.ads}</td><td class="num">${x.campaigns}</td>
      <td class="small">${kv(x.sources)}</td><td class="small">${kv(x.mediums, MF)}</td></tr>`).join('');
    return `<div class="kpis k4">${tiles}</div>
      ${fresh.length ? `<div class="card"><h3>کمپین‌های تازهٔ رقبا</h3><p class="hint">نام کمپین‌هایی که امروز برای اولین بار در لینک تبلیغات دیده شدند؛ معمولاً یعنی شروع موج جدید. روی هر کدام بزنید.</p><div class="camps">${freshCards}</div></div>` : ''}
      <div class="card"><div class="gh"><div><h3 style="margin:0">همهٔ کمپین‌ها (UTM)</h3><p class="hint" style="margin:2px 0 0">هر ردیف = یک برند × یک utm_campaign. «معنا» از نام کمپین، medium و content رمزگشایی شده است.</p></div><button class="btn" id="k-csv">کپی جدول (CSV)</button></div>
        <div class="gtools"><select id="k-brand" aria-label="برند"><option value="">همهٔ برندها</option>${brands.map(b => `<option ${K.brand === b ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select>
        <select id="k-tag" aria-label="معنا"><option value="">همهٔ معناها</option>${tags.map(t => `<option value="${t}" ${K.tag === t ? 'selected' : ''}>${esc(T[t] || t)}</option>`).join('')}</select>
        <select id="k-med" aria-label="مدیوم"><option value="">همهٔ مدیوم‌ها</option>${meds.map(m => `<option value="${m}" ${K.med === m ? 'selected' : ''}>${esc(MF[m] || m)}</option>`).join('')}</select>
        <label class="small" style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="k-new" ${K.fresh ? 'checked' : ''}> فقط تازه‌ها</label>
        <input type="search" id="k-q" placeholder="جست‌وجو در نام کمپین، content یا source" value="${esc(K.q)}"></div>
        <div class="tw"><table class="sortable"><thead><tr><th class="sort">برند</th><th class="sort">utm_campaign</th><th>معنا</th><th>source</th><th>medium</th><th title="utm_content: معمولاً نسخهٔ کریتیو یا جایگاه">content ⓘ</th><th class="sort">سایت</th><th>شبکه</th><th class="sort">تبلیغ</th><th class="sort" title="روزهای فعال در ۳۱ روز اخیر">روز ⓘ</th><th class="sort">اولین بار</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="11">${empty('کمپینی با این فیلتر نیست.')}</td></tr>`}</tbody></table></div></div>
      <div class="row c32"><div class="card"><h3>بهداشت ردیابی رقبا</h3><p class="hint">چه سهمی از تبلیغات هر برند UTM دارد و از چه source/medium استفاده می‌کند. پوشش پایین یعنی رقیب با click-id شبکه یا پیکسل می‌سنجد؛ برای مقایسه به متن و لندینگ تکیه کنید.</p>
        <div class="tw"><table class="sortable"><thead><tr><th>برند</th><th class="sort">پوشش UTM</th><th>تبلیغ دارای UTM</th><th>کمپین</th><th>source</th><th>medium</th></tr></thead><tbody>${hyg || `<tr><td colspan="6">${empty('—')}</td></tr>`}</tbody></table></div></div>
      <div class="card"><h3>میکس مدیوم و سورس</h3><p class="hint">از utm_medium و utm_source همهٔ تبلیغات دارای UTM</p>${hbars(Object.entries(U.mediums || {}).map(([k, v]) => [MF[k] || k, v]), () => '#3987e5', v => v)}
        <h3 style="margin-top:14px;font-size:14px">سورس‌ها</h3>${hbars(Object.entries(U.sources || {}).map(([k, v]) => [k, v]), () => '#5598e7', v => v)}</div></div>`;
  }
  function openCampaign(key) {
    const c = (D.campaigns || []).find(x => x.brand + '|' + x.campaign === key); if (!c) return;
    const T = (D.utm || {}).tags_fa || {}, MF = (D.utm || {}).medium_fa || {};
    const rows = D.rows.filter(r => r.b === c.brand && ((r.ut && r.ut.c) || r.u) === c.campaign);
    $('#drawer').innerHTML = `<button class="x" data-close>✕ بستن</button><h3 style="margin:0 0 4px">${brandCell(c.brand)}</h3><div class="cn" style="font-size:16px"><bdi dir="ltr">${esc(c.campaign)}</bdi></div>
      <div style="margin:6px 0">${c.tags.map(t => `<span class="tagp t-${t}">${esc(T[t] || t)}</span>`).join('')}${c.warm_only ? ' <span class="pill st-warn">فقط در پروفایل گرم</span>' : ''}</div>
      <div class="stats">${stat(c.ads, 'تبلیغ امروز')}${stat(c.sites.length, 'سایت امروز')}${stat(c.days, 'روز فعال')}${stat(c.sites_30d, 'سایت در ۳۰ روز')}</div>
      <dl class="kv"><dt>اولین / آخرین</dt><dd><bdi dir="ltr">${esc(c.first_seen)} → ${esc(c.last_seen)}</bdi></dd>
      <dt>source</dt><dd class="ltr">${esc(Object.keys(c.sources).join(', ') || '—')}</dd><dt>medium</dt><dd>${Object.keys(c.mediums).map(m => esc(MF[m] || m)).join('، ') || '—'} <span class="muted small ltr">${esc(c.raw_mediums.join(', '))}</span></dd>
      <dt>content</dt><dd class="ltr small">${esc(c.contents.join(' · ') || '—')}</dd>${c.terms.length ? `<dt>term</dt><dd class="ltr small">${esc(c.terms.join(' · '))}</dd>` : ''}
      <dt>سایت‌ها</dt><dd class="ltr small">${esc(c.sites.join(', '))}</dd><dt>شبکه</dt><dd>${chips(c.networks, 'network', 4)}</dd><dt>فرمت / جایگاه</dt><dd>${chips(c.formats, 'format', 3)}${chips(c.placements, 'placement', 3)}</dd>
      <dt>دستگاه</dt><dd>${chips(c.devices, 'device')}</dd><dt>دسته</dt><dd>${chips(c.categories, 'category', 3)}</dd>${c.landings.length ? `<dt>لندینگ</dt><dd class="ltr">${esc(c.landings.join(', '))}</dd>` : ''}
      ${c.offers.length ? `<dt>آفر</dt><dd style="color:var(--warn)">${esc(c.offers.join('، '))}</dd>` : ''}</dl>
      <h3 style="font-size:14px">متن‌ها</h3><ul class="bul small">${c.titles.map(t => `<li>${esc(t)}</li>`).join('') || '<li class="muted">—</li>'}</ul>
      <h3 style="font-size:14px;margin-top:10px">کریتیوها</h3><div class="shots">${c.shots.filter(k => img(k)).map(k => `<div class="frame"><img src="${img(k)}" alt=""></div>`).join('') || empty('اسکرین‌شاتی نیست.')}</div>
      <h3 style="font-size:14px;margin-top:10px">ترکیب کامل UTM</h3>${utmTable(rows)}`;
    $('#drawer').classList.add('on'); $('#scrim').classList.add('on');
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
      ['کمپین (UTM)', 'هر مقدار یکتای utm_campaign برای یک برند. «تازه» یعنی این نام در ۳۱ روز گذشته دیده نشده بود. معنای کمپین (ریتارگتینگ، اقساط، فصلی و...) از نام کمپین، medium و content رمزگشایی می‌شود.'],
      ['کریتیو تازه', 'کریتیوی که امروز اولین بار دیده شد. اگر بیش از نیمی از کریتیوهای فعال یک رقیب تازه باشند، احتمالاً موج کمپین جدیدی شروع شده است.'],
      ['بنچمارک آفر', 'قوی‌ترین تخفیف و اقساط اعلام‌شدهٔ رقبا در هر دسته، در برابر آفر امروز دیجی‌کالا.'],
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
    ['sites', 'سایت‌ها و شبکه‌ها', () => tabSites() + tabDiscovery()], ['cre', 'کریتیوها', tabCreatives], ['camp', 'کمپین‌ها و UTM', tabCampaigns], ['msg', 'پیام و آفر', tabMessaging],
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
    $$('[data-go]').forEach(b => { b.onclick = () => { cur = b.dataset.go; renderAll(); window.scrollTo(0, 0); }; b.onkeydown = e => { if (e.key === 'Enter') b.onclick(); }; });
    $$('tr[data-brand]').forEach(tr => { tr.tabIndex = 0; tr.onclick = () => openBrand(tr.dataset.brand); tr.onkeydown = e => { if (e.key === 'Enter') openBrand(tr.dataset.brand); }; });
    $$('.cr[data-i]').forEach(c => { c.onclick = () => openShot(+c.dataset.i); c.onkeydown = e => { if (e.key === 'Enter') openShot(+c.dataset.i); }; });
    $$('[data-camp]').forEach(c => { c.onclick = () => openCampaign(c.dataset.camp); c.onkeydown = e => { if (e.key === 'Enter') openCampaign(c.dataset.camp); }; });
    const gb = $('#g-brand'); if (gb) { gb.onchange = e => { G.brand = e.target.value; renderAll(); }; $('#g-fmt').onchange = e => { G.fmt = e.target.value; renderAll(); };
      $('#g-net').onchange = e => { G.net = e.target.value; renderAll(); }; $('#g-sort').onchange = e => { G.sort = e.target.value; renderAll(); }; $('#g-q').onchange = e => { G.q = e.target.value.trim(); renderAll(); };
      $$('[data-q]').forEach(b => b.onclick = () => { G.quick = b.dataset.q; renderAll(); }); $$('[data-view]').forEach(b => b.onclick = () => { G.view = b.dataset.view; renderAll(); });
      $('#g-copy').onclick = e => csvDownload(['brand', 'level', 'text', 'format', 'placement', 'device', 'network', 'category', 'seen', 'sites', 'days', 'first_seen', 'offer', 'utm_campaign', 'landing'],
        CARDS.map(g => { const r = g.r; return [r.b, r.l, r.t, fa('format', r.f), fa('placement', r.p), fa('device', r.d), fa('network', r.n), fa('category', r.c), g.n, [...g.sites].join(' '), r.dy || 1, r.fs, r.of, g.utm ? (g.utm.u || g.utm.ut.c) : '', r.ld]; }), `creatives-${D.meta.date}.csv`, e.target); }
    const kb = $('#k-brand'); if (kb) { kb.onchange = e => { K.brand = e.target.value; renderAll(); }; $('#k-tag').onchange = e => { K.tag = e.target.value; renderAll(); }; $('#k-med').onchange = e => { K.med = e.target.value; renderAll(); };
      $('#k-new').onchange = e => { K.fresh = e.target.checked; renderAll(); }; $('#k-q').onchange = e => { K.q = e.target.value.trim(); renderAll(); };
      $('#k-csv').onclick = e => csvDownload(['brand', 'level', 'utm_campaign', 'meaning', 'sources', 'mediums', 'contents', 'terms', 'sites', 'networks', 'ads', 'days_active', 'first_seen', 'last_seen', 'new'],
        campsF().map(c => [c.brand, c.level, c.campaign, c.tags.map(t => (D.utm.tags_fa || {})[t] || t).join('|'), Object.keys(c.sources).join('|'), c.raw_mediums.join('|'), c.contents.join('|'), c.terms.join('|'), c.sites.join(' '), Object.keys(c.networks).join('|'), c.ads, c.days, c.first_seen, c.last_seen, c.new ? 'yes' : '']), `utm-campaigns-${D.meta.date}.csv`, e.target); }

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
  // overlay/drawer content is rendered after bind(): delegate its buttons
  document.addEventListener('click', e => {
    const nv = e.target.closest('[data-nav]'); if (nv) { e.stopPropagation(); return openShot(LB + +nv.dataset.nav); }
    const cp = e.target.closest('[data-copy]'); if (cp) { e.stopPropagation(); return copyOrShow(cp.dataset.copy, cp, '✓ کپی شد'); }
    const gb = e.target.closest('[data-gobrand]'); if (gb) { K.brand = gb.dataset.gobrand; cur = 'camp'; $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); renderAll(); return window.scrollTo(0, 0); }
    const dc = e.target.closest('#drawer [data-camp]'); if (dc) return openCampaign(dc.dataset.camp);
  });
  document.addEventListener('click', e => { if (e.target.closest('[data-close]') || e.target.id === 'scrim' || e.target.id === 'ov') { $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); $('#ov').classList.remove('on'); LB = -1; } });
  document.addEventListener('keydown', e => { if ($('#ov').classList.contains('on') && LB >= 0 && $('.lbn')) { if (e.key === 'ArrowLeft' && LB < CARDS.length - 1) return openShot(LB + 1); if (e.key === 'ArrowRight' && LB > 0) return openShot(LB - 1); }
    if (e.key === 'Escape') { $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); $('#ov').classList.remove('on'); } });
  renderFilters(); renderAll();
})();
