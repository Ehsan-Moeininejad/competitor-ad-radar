"""Self-contained dark HTML report (Vazirmatn embedded, screenshots inlined) — same file is published and emailed."""
import base64
import json
import html

from classify import CAMPAIGN_FA, FORMAT_FA, PLACEMENT_FA
from util import DATA, ROOT, now, settings

NET_FA = {}
DEV_FA = {"mobile": "موبایل", "desktop": "دسکتاپ"}
LEVEL_FA = {"own": "گروه دیجی‌کالا", "core": "رقیب مستقیم", "vertical": "رقیب ورتیکالی", "none": "غیررقیب", "unknown": "نامشخص"}
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
SEQ = ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef"]


def e(x):
    return html.escape(str(x if x is not None else ""))


def pct(x, d=0):
    return f"{round((x or 0) * 100, d)}%" if d else f"{round((x or 0) * 100)}%"


def _font_css():
    css = []
    for sub, rng in (("arabic", "U+0600-06FF,U+0750-077F,U+200C-200E,U+2010-2011,U+204F,U+2E41,U+FB50-FDFF,U+FE70-FEFC"),
                     ("latin", "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215")):
        for w in (400, 700):
            p = ROOT / "assets" / f"vz-{sub}-{w}.woff2"
            if p.exists():
                b = base64.b64encode(p.read_bytes()).decode()
                css.append(f"@font-face{{font-family:Vazirmatn;font-weight:{w};font-display:swap;src:url(data:font/woff2;base64,{b}) format('woff2');unicode-range:{rng}}}")
    return "\n".join(css)


IMGS = {}   # each screenshot is embedded once and referenced by key (keeps the file small)


def _img(shot):
    """Returns an attribute string for <img>, or '' if the screenshot is gone."""
    if not shot:
        return ""
    k = shot.split("/")[-1].split(".")[0]
    if k not in IMGS:
        p = DATA / "shots" / shot
        if not p.exists():
            return ""
        IMGS[k] = base64.b64encode(p.read_bytes()).decode()
    return f'data-i="{k}" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'



def status_color(v, inverse=False):
    v = 100 - v if inverse else v
    return STATUS["critical"] if v >= 70 else STATUS["serious"] if v >= 50 else STATUS["warning"] if v >= 30 else STATUS["good"]


def meter(v, inverse=False, label=""):
    c = status_color(v, inverse)
    return (f'<div class="meter" title="{e(label)} {v}/100"><div class="mbar"><i style="width:{max(2, v)}%;background:{c}"></i></div>'
            f'<b>{v}</b></div>')


def chips(d: dict, fa=None, n=4):
    fa = fa or {}
    return " ".join(f'<span class="chip">{e(fa.get(k, NET_FA.get(k, k)))} <small>{v}</small></span>' for k, v in list(d.items())[:n])


def hbar_rows(items, color_of=None, fmt=lambda v: pct(v, 1)):
    if not items:
        return '<p class="muted">داده‌ای نیست.</p>'
    mx = max(v for _, v in items) or 1
    rows = []
    for i, (k, v) in enumerate(items):
        c = color_of(k, i) if color_of else SERIES[0]
        rows.append(f'<div class="hrow" title="{e(k)}: {fmt(v)}"><span class="hl">{e(k)}</span>'
                    f'<span class="ht"><i style="width:{max(1.5, 100 * v / mx):.1f}%;background:{c}"></i></span><span class="hv">{fmt(v)}</span></div>')
    return '<div class="hbars">' + "".join(rows) + "</div>"


def spark(series, color, w=180, h=36):
    if len(series) < 2:
        return '<span class="muted">—</span>'
    ys = [v for _, v in series]
    mx = max(ys) or 1
    pts = " ".join(f"{i * (w - 6) / (len(ys) - 1) + 3:.1f},{h - 4 - (v / mx) * (h - 8):.1f}" for i, v in enumerate(ys))
    last = pts.split(" ")[-1].split(",")
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="روند ۳۰ روزه">'
            f'<title>{e(series[0][0])} تا {e(series[-1][0])}: {pct(ys[0], 1)} → {pct(ys[-1], 1)}</title>'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" points="{pts}"/>'
            f'<circle cx="{last[0]}" cy="{last[1]}" r="3.5" fill="{color}" stroke="#1a1a19" stroke-width="2"/></svg>')


def _brand_colors(comps, M):
    """Color follows the brand, not its rank: a persistent brand→slot map (own group = Digikala red)."""
    from util import read_json, write_json
    path = DATA / "brand_colors.json"
    cmap = read_json(path, {}) or {}
    levels = {b: c["level"] for b, c in comps.items()}
    levels.update({b: c["level"] for b, c in (M or {}).get("competitors", {}).items() if b not in levels})
    for b, lv in levels.items():
        if lv != "own" and b not in cmap:
            cmap[b] = len(cmap) % len(SERIES)
    write_json(path, cmap)
    return {b: ("#ef4056" if lv == "own" else SERIES[cmap[b]]) for b, lv in levels.items()}


def build(D: dict, M: dict, I: dict, publishers: dict, llm_summary: str, nets_cfg: dict) -> str:
    global NET_FA
    IMGS.clear()
    NET_FA = {k: v.get("fa", k) for k, v in nets_cfg["networks"].items()}
    NET_FA["direct"] = "خرید مستقیم"
    cfg = settings()
    comps = D["competitors"]
    brand_color = _brand_colors(comps, M)
    rivals = [(b, c) for b, c in comps.items() if c["level"] != "own"]
    own = [(b, c) for b, c in comps.items() if c["level"] == "own"]
    stamp = now().strftime("%Y-%m-%d %H:%M")

    # ---------------- tab 1: summary
    kpis = [("سایت اسکن‌شده", len([1 for c in D["coverage"].values() if c["ok"]]), f"پوشش صفحات {D['coverage_pct']}%"),
            ("تبلیغ ثبت‌شده", D["n_obs"], f"{D['runs']} اجرا امروز"),
            ("تبلیغ‌دهنده", D["advertisers_total"], f"{D['unknown_advertisers']} شناسایی‌نشده"),
            ("رقیب فعال", len(rivals), f"{sum(1 for _, c in rivals if c['level'] == 'core')} مستقیم"),
            ("سهم دیجی‌کالا", pct(sum(c["sov"] for _, c in own), 1), "از کل حضور برندهای ای‌کامرس"),
            ("جایگاه تازه", len(D["discovery"]["new_units"]), "نسبت به روزهای قبل")]
    kpi_html = "".join(f'<div class="kpi"><span>{e(a)}</span><b>{e(b)}</b><small>{e(c)}</small></div>' for a, b, c in kpis)
    lvl_ic = {"high": "▲", "mid": "●", "low": "○"}
    lvl_c = {"high": STATUS["critical"], "mid": STATUS["serious"], "low": STATUS["warning"]}
    alerts = "".join(f'<li><span class="ic" style="color:{lvl_c[a["level"]]}">{lvl_ic[a["level"]]}</span>{e(a["text"])}</li>' for a in D["alerts"]) or '<li class="muted">هشداری نیست.</li>'
    summary = "".join(f"<li>{e(s)}</li>" for s in I.get("summary", []))
    pr_fa = {"high": "فوری", "mid": "متوسط", "low": "کم"}
    actions = "".join(f'<tr><td><span class="pill p-{e(a.get("priority", "mid"))}">{e(pr_fa.get(a.get("priority"), a.get("priority", "")))}</span></td>'
                      f'<td>{e(a.get("action"))}</td><td class="ltr">{e(a.get("where"))}</td><td>{e(a.get("why"))}</td></tr>' for a in I.get("actions", []))
    moves = "".join(f'<div class="move"><b>{e(m.get("brand"))}</b><p>{e(m.get("move"))}</p><small>{e(m.get("implication"))}</small></div>'
                    for m in I.get("competitor_moves", []))
    t1 = f"""
<section class="hero"><h2>{e(I.get('headline', ''))}</h2></section>
<div class="kpis">{kpi_html}</div>
<div class="grid2">
  <div class="card"><h3>جمع‌بندی امروز</h3><ul class="bul">{summary}</ul></div>
  <div class="card"><h3>هشدارها</h3><ul class="alerts">{alerts}</ul></div>
</div>
<div class="card"><h3>اقدام‌های پیشنهادی</h3><div class="tw"><table><thead><tr><th>اولویت</th><th>اقدام</th><th>کجا</th><th>چرا</th></tr></thead><tbody>{actions or '<tr><td colspan=4 class="muted">—</td></tr>'}</tbody></table></div></div>
<div class="card"><h3>حرکت رقبا</h3><div class="moves">{moves or '<p class="muted">—</p>'}</div></div>
"""
    # ---------------- tab 2: competitors
    sov_items = [(b, c["sov"]) for b, c in comps.items()][:12]
    vert_cards = "".join(
        f'<div class="vcard"><div class="vh"><b>{e(v["fa"])}</b>{"<span class=core>Core</span>" if v["core"] else ""}</div>'
        f'{meter(v["risk"], label="ریسک رقابت")}<small>سهم دیجی‌کالا {pct(v["own_sov"])} · {v["rivals"]} رقیب</small>'
        f'<small class="muted">{e("، ".join(v["leaders"][:4]))}</small></div>' for v in D["verticals"].values())
    vnotes = "".join(f'<li><b>{e(n.get("vertical"))}</b>: {e(n.get("note"))}</li>' for n in I.get("vertical_notes", []))
    comp_rows = []
    for b, c in comps.items():
        g = c.get("growth")
        gtxt = "جدید" if g is None and c.get("sov_7d") is None else (f'<span style="color:{STATUS["good"] if g < 0 else STATUS["critical"]}">{"+" if g > 0 else ""}{round(g * 100)}%</span>' if g is not None else "—")
        comp_rows.append(
            f'<tr data-v="{e(c["vertical"])}"><td><i class="dot" style="background:{brand_color.get(b, "#898781")}"></i>{e(b)}</td>'
            f'<td>{e(LEVEL_FA.get(c["level"], c["level"]))}</td><td>{e(D["verticals"].get(c["vertical"], {}).get("fa", c["vertical"]))}</td>'
            f'<td data-s="{c["sov"]}">{pct(c["sov"], 1)}</td><td data-s="{c["sov_vertical"]}">{pct(c["sov_vertical"])}</td><td>{gtxt}</td>'
            f'<td data-s="{len(c["sites"])}">{len(c["sites"])}</td><td data-s="{c["threat"]}">{meter(c["threat"], label="تهدید") if c["level"] != "own" else "—"}</td>'
            f'<td>{chips(c["networks"], n=3)}</td><td>{chips(c["campaign_types"], CAMPAIGN_FA, 3)}</td></tr>')
    vopts = "".join(f'<option value="{e(k)}">{e(v["fa"])}</option>' for k, v in D["verticals"].items())
    cards = []
    for b, c in list(comps.items())[:14]:
        shots = "".join(f'<figure><img {_img(s["shot"])} alt="{e(s["title"])}"><figcaption>{e(s["site"])} · {e(PLACEMENT_FA.get(s["placement"], s["placement"]))}</figcaption></figure>'
                        for s in c["shots"][:4] if _img(s["shot"]))
        cards.append(f"""<div class="ccard"><div class="ch"><i class="dot" style="background:{brand_color.get(b, '#898781')}"></i><b>{e(b)}</b>
<span class="muted">{e(LEVEL_FA.get(c['level']))} · {e(D['verticals'].get(c['vertical'], {}).get('fa', c['vertical']))}</span></div>
<dl><dt>سایت‌ها</dt><dd class="ltr">{e(', '.join(c['sites'][:10]))}</dd>
<dt>فرمت</dt><dd>{chips(c['formats'], FORMAT_FA)}</dd><dt>جایگاه</dt><dd>{chips(c['placements'], PLACEMENT_FA)}</dd>
<dt>نوع کمپین</dt><dd>{chips(c['campaign_types'], CAMPAIGN_FA, 5)}</dd><dt>دستگاه</dt><dd>{chips(c['devices'], DEV_FA)}</dd>
{f"<dt>ریتارگتینگ</dt><dd class='ltr'>{e(', '.join(c['retargeting_sites']))}</dd>" if c['retargeting_sites'] else ''}
{f"<dt>آفرها</dt><dd>{chips(c['offers'], CAMPAIGN_FA, 5)}</dd>" if c['offers'] else ''}
{f"<dt>کمپین‌ها (UTM)</dt><dd class='ltr'>{e(' · '.join(c['utm_campaigns']))}</dd>" if c['utm_campaigns'] else ''}
<dt>پیام‌ها</dt><dd><ul class="titles">{''.join(f'<li>{e(t)}</li>' for t in c['top_titles'][:4])}</ul></dd></dl>
<div class="shots">{shots}</div></div>""")
    t2 = f"""
<div class="grid2">
  <div class="card"><h3>سهم دیده‌شدن (Share of Voice)</h3><p class="muted">وزن‌دار با ارزش جایگاه؛ بین برندهای ای‌کامرس شناسایی‌شده</p>
  {hbar_rows(sov_items, lambda k, i: brand_color.get(k, '#898781'))}</div>
  <div class="card"><h3>ریسک رقابت در هر ورتیکال</h3><div class="vcards">{vert_cards or '<p class="muted">—</p>'}</div><ul class="bul">{vnotes}</ul></div>
</div>
<div class="card"><div class="th"><h3>جدول رقبا</h3><select id="vf" onchange="fv(this.value)"><option value="">همهٔ ورتیکال‌ها</option>{vopts}</select></div>
<div class="tw"><table class="sortable" id="ct"><thead><tr><th>برند</th><th>سطح</th><th>ورتیکال</th><th>SOV کل</th><th>SOV ورتیکال</th><th>تغییر ۷ روز</th><th>سایت</th><th>تهدید</th><th>شبکه‌ها</th><th>نوع کمپین</th></tr></thead>
<tbody>{''.join(comp_rows) or '<tr><td colspan=10 class="muted">رقیبی شناسایی نشد.</td></tr>'}</tbody></table></div></div>
<div class="ccards">{''.join(cards)}</div>
"""
    # ---------------- tab 3: pressure & opportunity
    rec_c = {"خرید مستقیم": STATUS["good"], "بید پایین در شبکه": STATUS["good"], "شکاف حضور": STATUS["warning"], "تست": STATUS["warning"],
             "اجتناب/متمایز": STATUS["critical"], "پایش": "#898781", "—": "#898781"}
    src_fa = {"sheet": "شیت", "seed": "سیستم", "discovered": "کشف‌شده"}
    srows = []
    for d, s in D["sites"].items():
        cu = " · ".join(f'{PLACEMENT_FA.get(u["placement"], u["placement"])} ({DEV_FA.get(u["device"], u["device"])})' for u in s["cheapest_units"][:2])
        srows.append(f'<tr><td class="ltr">{e(d)}</td><td><span class="src">{e(src_fa.get(s["source"], s["source"]))}</span></td>'
                     f'<td data-s="{s["opportunity"]}">{meter(s["opportunity"], inverse=True, label="فرصت")}</td>'
                     f'<td data-s="{s["pressure"]}">{meter(s["pressure"], label="فشار")}</td>'
                     f'<td data-s="{s["slots_per_page"]}">{s["slots_per_page"]}</td><td data-s="{s["advertisers"]}">{s["advertisers"]}</td>'
                     f'<td data-s="{s["competitor_share"]}">{pct(s["competitor_share"])}</td><td>{"✓" if s["own_present"] else "✗"}</td>'
                     f'<td><span class="rec" style="border-color:{rec_c.get(s["recommendation"], "#898781")}">{e(s["recommendation"])}</span><small class="why">{e(s["why"])}</small></td>'
                     f'<td>{e(cu)}</td><td>{chips({n: "" for n in s["networks"]}, n=4)}</td></tr>')
    plc_keys = list(PLACEMENT_FA.keys())
    heat_sites = list(D["sites"].items())[:30]
    mxh = max([v for _, s in heat_sites for v in s["placements"].values()] or [1])
    heat = "".join(
        f'<tr><td class="ltr">{e(d)}</td>' + "".join(
            (lambda v: f'<td class="hc" title="{e(d)} · {e(PLACEMENT_FA[p])}: {v} تبلیغ" style="background:{SEQ[min(7, int(7 * v / mxh))] if v else "transparent"}">{v or ""}</td>')(s["placements"].get(p, 0))
            for p in plc_keys) + "</tr>" for d, s in heat_sites)
    gaps = "، ".join(D["gaps"]) or "—"
    t3 = f"""
<div class="card"><h3>کجا با فشار کمتر و بید کمتر وارد شویم؟</h3>
<p class="muted">فرصت = دسترسی سایت × فشار پایین × حضور رقبا (اثبات مخاطب) × قابل خرید بودن. فشار = تعداد اسلات، تبلیغ‌دهنده، تراکم رقبا، سهم جایگاه‌های ممتاز و چرخش کریتیو.</p>
<div class="tw"><table class="sortable"><thead><tr><th>سایت</th><th>منبع</th><th>فرصت</th><th>فشار</th><th>اسلات/صفحه</th><th>تبلیغ‌دهنده</th><th>سهم رقبا</th><th>دیجی‌کالا</th><th>پیشنهاد</th><th>کم‌تراکم‌ترین جایگاه</th><th>شبکه‌ها</th></tr></thead>
<tbody>{''.join(srows) or '<tr><td colspan=11 class="muted">—</td></tr>'}</tbody></table></div></div>
<div class="card"><h3>شکاف حضور</h3><p>سایت‌هایی که حداقل دو رقیب هست و دیجی‌کالا نیست: <span class="ltr">{e(gaps)}</span></p></div>
<div class="card"><h3>نقشهٔ حرارتی جایگاه‌ها</h3><p class="muted">تعداد تبلیغ ثبت‌شده در هر جایگاه (رنگ تیره‌تر = کمتر، روشن‌تر = شلوغ‌تر)</p>
<div class="tw"><table class="heat"><thead><tr><th>سایت</th>{''.join(f'<th>{e(PLACEMENT_FA[p])}</th>' for p in plc_keys)}</tr></thead><tbody>{heat}</tbody></table></div></div>
"""
    # ---------------- tab 4: discovery
    disc = D["discovery"]

    def table(rows, cols, empty="موردی نیست."):
        if not rows:
            return f'<p class="muted">{empty}</p>'
        head = "".join(f"<th>{e(c[1])}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f'<td class="{c[2] if len(c) > 2 else ""}">{e(c[3](r[c[0]]) if len(c) > 3 else r.get(c[0], ""))}</td>' for c in cols) + "</tr>" for r in rows)
        return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    pfa = lambda x: PLACEMENT_FA.get(x, x)
    ffa = lambda x: FORMAT_FA.get(x, x)
    nfa = lambda x: NET_FA.get(x, x)
    disc_pubs = sorted([p for p in publishers.values() if p.get("source") == "discovered"], key=lambda p: p.get("added", ""), reverse=True)[:25]
    catalog = "".join(f'<details><summary class="ltr">{e(d)}</summary><ul class="bul">{"".join(f"<li>{e(k)} <small>×{v}</small></li>" for k, v in c.items())}</ul></details>'
                      for d, c in sorted(disc["catalog"].items()))
    inv_notes = "".join(f"<li>{e(x)}</li>" for x in I.get("inventory_notes", []))
    t4 = f"""
<div class="card"><h3>جمع‌بندی کشف</h3><ul class="bul">{inv_notes or '<li class="muted">—</li>'}</ul>
<p class="muted">سایت‌هایی که امروز برای اولین بار اسکن شده‌اند، «خط پایه» هستند و جایگاه‌هایشان «تازه» حساب نمی‌شود: <span class="ltr">{e(', '.join(disc['baseline_sites'][:20]) or '—')}</span></p></div>
<div class="grid2">
<div class="card"><h3>جایگاه / فرمت تازه</h3>{table(disc['new_units'], [('site', 'سایت', 'ltr'), ('placement', 'جایگاه', '', pfa), ('format', 'فرمت', '', ffa), ('device', 'دستگاه', '', lambda x: DEV_FA.get(x, x)), ('size', 'سایز', 'ltr'), ('network', 'شبکه', '', nfa), ('brand', 'اولین تبلیغ‌دهنده')])}</div>
<div class="card"><h3>ورود رقیب به سایت تازه</h3>{table(disc['competitor_new_sites'], [('brand', 'برند'), ('site', 'سایت', 'ltr'), ('placement', 'جایگاه', '', pfa), ('format', 'فرمت', '', ffa)])}</div>
<div class="card"><h3>تبلیغ‌دهندهٔ تازه</h3>{table(disc['new_advertisers'], [('name', 'برند'), ('level', 'سطح', '', lambda x: LEVEL_FA.get(x, x)), ('vertical', 'ورتیکال')])}</div>
<div class="card"><h3>شبکهٔ تبلیغاتی تازه روی سایت</h3>{table(disc['new_networks'], [('site', 'سایت', 'ltr'), ('network', 'شبکه', '', nfa)])}
<h3>دامنه‌های ناشناختهٔ شبیه ادسرور</h3><p class="muted">اگر شبکهٔ تبلیغاتی هستند به config/ad_networks.yaml اضافه شوند.</p>{table(disc['candidate_networks'], [('host', 'دامنه', 'ltr'), ('sites', 'تعداد صفحه')])}</div>
</div>
<div class="grid2">
<div class="card"><h3>فرمت‌های خاص</h3><p>پوش نوتیفیکیشن: <span class="ltr">{e(', '.join(disc['push_sites']) or '—')}</span></p><p>رپورتاژ: <span class="ltr">{e(', '.join(disc['reportage_sites']) or '—')}</span></p>
<h3>میکس فرمت و شبکه (کل بازار)</h3>{hbar_rows([(FORMAT_FA.get(k, k), v) for k, v in D['format_share'].items()], fmt=str)}{hbar_rows([(NET_FA.get(k, k), v) for k, v in list(D['network_share'].items())[:8]], lambda k, i: SERIES[1], fmt=str)}</div>
<div class="card"><h3>پابلیشرهای کشف‌شده توسط سیستم</h3>{table(disc_pubs, [('domain', 'سایت', 'ltr'), ('category', 'دسته'), ('status', 'وضعیت', '', lambda x: {'active': 'فعال', 'probation': 'در حال تست', 'dormant': 'بدون تبلیغ'}.get(x, x)), ('added', 'تاریخ کشف', 'ltr')], 'هنوز سایتی کشف نشده (کشف هفتگی).')}</div>
</div>
<div class="card"><h3>کاتالوگ اینونتوری هر سایت</h3><p class="muted">جایگاه · فرمت · سایز · دستگاه</p>{catalog or '<p class="muted">—</p>'}</div>
"""
    # ---------------- tab 5: creatives
    gal = []
    for b, c in comps.items():
        for s in c["shots"]:
            src = _img(s["shot"])
            if src and len(gal) < 120:
                gal.append(f'<figure data-b="{e(b)}"><img {src} alt="{e(s["title"])}"><figcaption><b>{e(b)}</b> · <span class="ltr">{e(s["site"])}</span><br>'
                           f'{e(PLACEMENT_FA.get(s["placement"], s["placement"]))}{(" · " + e(s["title"][:70])) if s["title"] else ""}</figcaption></figure>')
    thumb = lambda sh: (f'<img class="thumb" {_img(sh)} alt="">' if _img(sh) else "")
    lr = "".join(f'<tr><td>{e(x["brand"])}</td><td>{thumb(x.get("shot"))}{e(x["title"][:90]) or ("" if x.get("shot") and _img(x["shot"]) else "—")}</td><td data-s="{x["days"]}">{x["days"]}</td><td class="ltr">{e(x["first_seen"])}</td><td>{x["sites"]}</td></tr>' for x in D["long_running"])
    t5 = f"""
<div class="card"><h3>کریتیوهای پرعمر</h3><p class="muted">کریتیوی که روزهای بیشتری اجرا شده احتمالاً عملکرد خوبی دارد (تا ۳۰ روز سابقه)</p>
<div class="tw"><table class="sortable"><thead><tr><th>برند</th><th>متن</th><th>روزهای اجرا</th><th>اولین مشاهده</th><th>سایت</th></tr></thead><tbody>{lr or '<tr><td colspan=5 class="muted">—</td></tr>'}</tbody></table></div></div>
<div class="card"><h3>گالری کریتیو رقبا (امروز)</h3><div class="gallery">{''.join(gal) or '<p class="muted">اسکرین‌شاتی نیست.</p>'}</div></div>
"""
    # ---------------- tab 6: monthly
    if M and M.get("days", 0) >= 2:
        mrows = "".join(
            f'<tr><td><i class="dot" style="background:{brand_color.get(b, "#898781")}"></i>{e(b)}</td><td>{e(LEVEL_FA.get(c["level"], c["level"]))}</td>'
            f'<td data-s="{c["avg_sov"]}">{pct(c["avg_sov"], 1)}</td><td>{spark(c["series"], brand_color.get(b, SERIES[0]))}</td>'
            f'<td data-s="{c["trend"] or 0}">{(("+" if (c["trend"] or 0) > 0 else "") + str(round((c["trend"] or 0) * 100, 1))) if c["trend"] is not None else "—"}</td>'
            f'<td data-s="{c["avg_threat"]}">{c["avg_threat"]}</td><td>{c["active_days"]}</td><td>{c["sites"]}</td></tr>' for b, c in M["competitors"].items())
        msites = sorted(M["sites"].items(), key=lambda x: -x[1]["avg_opportunity"])[:25]
        msrows = "".join(f'<tr><td class="ltr">{e(d)}</td><td data-s="{s["avg_opportunity"]}">{meter(s["avg_opportunity"], True)}</td><td data-s="{s["avg_pressure"]}">{meter(s["avg_pressure"])}</td><td>±{s["pressure_std"]}</td><td>{s["days"]}</td></tr>' for d, s in msites)
        mb = "".join(f"<li>{e(x)}</li>" for x in I.get("monthly", []))
        t6 = f"""<div class="card"><h3>تصویر ۳۰ روزه</h3><p class="muted">{e(M['from'])} تا {e(M['to'])} · {M['days']} روز داده</p><ul class="bul">{mb}</ul></div>
<div class="card"><h3>روند سهم رقبا</h3><div class="tw"><table class="sortable"><thead><tr><th>برند</th><th>سطح</th><th>میانگین SOV</th><th>روند</th><th>تغییر (هفتهٔ آخر − اول)</th><th>میانگین تهدید</th><th>روز فعال</th><th>سایت</th></tr></thead><tbody>{mrows}</tbody></table></div></div>
<div class="grid2"><div class="card"><h3>پایدارترین فرصت‌ها (میانگین ماه)</h3><div class="tw"><table class="sortable"><thead><tr><th>سایت</th><th>فرصت</th><th>فشار</th><th>نوسان فشار</th><th>روز</th></tr></thead><tbody>{msrows}</tbody></table></div></div>
<div class="card"><h3>میکس نوع کمپین رقبا (ماه)</h3>{hbar_rows([(CAMPAIGN_FA.get(k, k), v) for k, v in list(M['campaign_mix'].items())[:10]], lambda k, i: SERIES[2], fmt=str)}</div></div>"""
    else:
        t6 = '<div class="card"><p class="muted">روند ماهانه از روز دوم به بعد ساخته می‌شود. دادهٔ خام ۳ روز و خلاصهٔ روزانه ۳۱ روز نگه داشته می‌شود.</p></div>'
    # ---------------- tab 7: coverage & method
    cov_rows = "".join(
        f'<tr><td class="ltr">{e(d)}</td><td>{c["ok"]}/{c["pages"]}</td><td>{c["slots"]}</td><td>{chips({n: "" for n in c["adtech"]}, n=5)}</td>'
        f'<td>{"⚠ ادتک بدون تبلیغ" if d in D["geo_suspect"] else ""}</td><td class="ltr err">{e("; ".join(c["errors"]))}</td></tr>'
        for d, c in sorted(D["coverage"].items(), key=lambda x: (x[1]["ok"] > 0, x[1]["slots"])))
    t7 = f"""
<div class="card"><h3>پوشش اسکن</h3><p class="muted">سایت‌های «ادتک بدون تبلیغ» احتمالاً به IP خارجی تبلیغ نشان نمی‌دهند. با تنظیم PROXY_URL (پراکسی ایران) پوشش کامل می‌شود.</p>
<div class="tw"><table class="sortable"><thead><tr><th>سایت</th><th>صفحهٔ موفق</th><th>اسلات</th><th>ادتک</th><th>هشدار</th><th>خطا</th></tr></thead><tbody>{cov_rows}</tbody></table></div></div>
<div class="card"><h3>روش کار</h3><ul class="bul">
<li>هر سایت در هر اجرا با سه پروفایل دیده می‌شود: موبایل بدون سابقه، دسکتاپ بدون سابقه، موبایل «گرم» (بعد از بازدید از سایت رقبا). تبلیغ رقیبی که فقط در پروفایل گرم دیده شود ریتارگتینگ حساب می‌شود.</li>
<li>ربات هیچ‌وقت روی تبلیغ کلیک نمی‌کند. لندینگ از لینک خود تبلیغ یا پاسخ API شبکه استخراج و مستقیم (بدون UTM) باز می‌شود.</li>
<li>سهم دیده‌شدن با وزن جایگاه محاسبه می‌شود (پاپ‌آپ، استیکی، هدر و بالای صفحه وزن بیشتری دارند).</li>
<li>دادهٔ خام ۳ روز، خلاصهٔ روزانه و اینسایت ماهانه ۳۱ روز نگه داشته می‌شود.</li>
<li>مدل‌های زبانی استفاده‌شده در این گزارش: <span class="ltr">{e(llm_summary)}</span> · متن تحلیل: {'مدل زبانی' if I.get('by') == 'llm' else 'قاعده‌محور'}</li>
<li>تخمین‌ها جهت‌دار هستند، نه عدد دقیق بازار. هر اجرا یک نمونه از تبلیغات چرخشی است و دقت با تعداد اجراها بالا می‌رود.</li></ul></div>
"""
    tabs = [("sum", "خلاصه", t1), ("comp", "رقبا", t2), ("opp", "فشار و فرصت", t3), ("disc", "کشف جایگاه و فرمت", t4),
            ("cre", "کریتیوها", t5), ("mon", "روند ماهانه", t6), ("cov", "پوشش و روش", t7)]
    nav = "".join(f'<button role="tab" data-t="{k}" class="{"on" if i == 0 else ""}">{e(n)}</button>' for i, (k, n, _) in enumerate(tabs))
    body = "".join(f'<section id="t-{k}" class="tab{" on" if i == 0 else ""}">{h}</section>' for i, (k, _, h) in enumerate(tabs))
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(cfg['report']['title'])} · {e(D['date'])}</title><style>{_font_css()}{CSS}</style></head><body>
<header class="top"><div><h1>{e(cfg['report']['title'])}</h1><span class="muted">{e(D['date'])} · ساخته‌شده {e(stamp)} به وقت تهران</span></div><span class="brand">{e(cfg['report']['brand'])}</span></header>
<nav role="tablist">{nav}</nav><main>{body}</main>
<footer class="muted">Competitor Ad Radar · داده‌ها از تبلیغات عمومی سایت‌ها جمع‌آوری شده است.</footer>
<script>const IMG={json.dumps(IMGS)};document.querySelectorAll('img[data-i]').forEach(i=>{{if(IMG[i.dataset.i])i.src='data:image/jpeg;base64,'+IMG[i.dataset.i]}});{JS}</script></body></html>"""


CSS = """
:root{--bg:#0d0d0d;--s1:#1a1a19;--s2:#222220;--ink:#f0efec;--ink2:#c3c2b7;--mute:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--acc:#ef4056}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font-family:Vazirmatn,system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;font-size:14px;line-height:1.75}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:20px 24px 8px;flex-wrap:wrap}
h1{font-size:22px;margin:0}h2{font-size:18px;margin:0;line-height:1.7}h3{font-size:15px;margin:0 0 10px}.brand{color:var(--acc);font-weight:700}
nav{display:flex;gap:4px;padding:8px 20px;position:sticky;top:0;background:var(--bg);z-index:5;overflow-x:auto;border-bottom:1px solid var(--grid)}
nav button{font:inherit;color:var(--ink2);background:none;border:0;padding:8px 14px;border-radius:8px;cursor:pointer;white-space:nowrap}
nav button.on{background:var(--s2);color:var(--ink);box-shadow:inset 0 -2px 0 var(--acc)}nav button:hover{background:var(--s1)}
main{padding:16px 20px;max-width:1400px;margin:0 auto}.tab{display:none}.tab.on{display:block}
.card{background:var(--s1);border:1px solid var(--ring);border-radius:14px;padding:16px 18px;margin-bottom:16px;min-width:0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}.grid2>.card{margin-bottom:0}.grid2{margin-bottom:16px}
.hero{background:linear-gradient(135deg,#2a1a1d,#1a1a19);border:1px solid var(--ring);border-radius:14px;padding:18px 20px;margin-bottom:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--s1);border:1px solid var(--ring);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column}
.kpi span{color:var(--ink2);font-size:12.5px}.kpi b{font-size:26px;line-height:1.4}.kpi small{color:var(--mute);font-size:12px}
.muted{color:var(--mute)}.ltr{direction:ltr;unicode-bidi:isolate;text-align:right}.bul{margin:0;padding-inline-start:18px}.bul li{margin:4px 0}
.alerts{list-style:none;margin:0;padding:0}.alerts li{padding:6px 0;border-bottom:1px solid var(--grid)}.alerts .ic{display:inline-block;width:20px}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:700;white-space:nowrap;position:sticky;top:0;background:var(--s1)}table.sortable th{cursor:pointer}table.sortable th:hover{color:var(--ink)}
td{font-variant-numeric:tabular-nums}tr:hover td{background:rgba(255,255,255,.025)}
.meter{display:flex;align-items:center;gap:6px;min-width:110px}.mbar{flex:1;height:8px;background:var(--axis);border-radius:4px;overflow:hidden}.mbar i{display:block;height:100%;border-radius:4px}.meter b{min-width:24px;font-size:12.5px}
.chip{display:inline-block;background:var(--s2);border:1px solid var(--ring);border-radius:10px;padding:0 8px;margin:1px 0;font-size:12px;color:var(--ink2);white-space:nowrap}.chip small{color:var(--mute)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:6px;vertical-align:middle}
.pill{padding:1px 10px;border-radius:10px;font-size:12px;border:1px solid}.p-high{color:#d03b3b;border-color:#d03b3b}.p-mid{color:#ec835a;border-color:#ec835a}.p-low{color:#fab219;border-color:#fab219}
.hbars{display:flex;flex-direction:column;gap:6px;margin:6px 0 10px}.hrow{display:grid;grid-template-columns:minmax(90px,150px) 1fr 56px;align-items:center;gap:8px}
.hl{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ht{height:14px;background:transparent;border-radius:4px;position:relative}.ht i{display:block;height:100%;border-radius:4px}.hv{font-size:12.5px;color:var(--ink2);font-variant-numeric:tabular-nums}
.vcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;margin-bottom:10px}.vcard{background:var(--s2);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:4px}
.vh{display:flex;justify-content:space-between}.core{font-size:11px;color:var(--acc);border:1px solid var(--acc);border-radius:8px;padding:0 6px}
.th{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}select{font:inherit;background:var(--s2);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:4px 8px}
.ccards{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}.ccard{background:var(--s1);border:1px solid var(--ring);border-radius:14px;padding:14px}
.ch{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:8px}.ch b{font-size:15px}dl{margin:0;display:grid;grid-template-columns:96px 1fr;gap:4px 8px;font-size:13px}dt{color:var(--mute)}dd{margin:0;min-width:0;overflow-wrap:anywhere}
.titles{margin:0;padding-inline-start:16px}.shots{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:10px}
figure{margin:0;background:var(--s2);border-radius:10px;overflow:hidden}figure img{width:100%;display:block;max-height:220px;object-fit:contain;background:#fff}figcaption{font-size:11.5px;color:var(--ink2);padding:6px 8px}
.thumb{height:44px;max-width:160px;object-fit:contain;background:#fff;border-radius:6px;margin-inline-end:8px;vertical-align:middle}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.src{font-size:11.5px;color:var(--ink2)}.rec{display:inline-block;border:1px solid;border-radius:8px;padding:0 8px;font-size:12.5px;white-space:nowrap}.why{display:block;color:var(--mute);font-size:11.5px;max-width:320px}
.heat td.hc{text-align:center;color:var(--ink);min-width:54px;border:2px solid var(--s1)}.heat th{font-size:12px}
.moves{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}.move{background:var(--s2);border-radius:10px;padding:10px 12px}.move p{margin:4px 0}.move small{color:var(--ink2)}
details{border-bottom:1px solid var(--grid);padding:6px 0}summary{cursor:pointer}.err{color:var(--mute);font-size:12px;max-width:320px}
footer{padding:20px;text-align:center;font-size:12px}
@media (max-width:640px){main{padding:12px 16px}.grid2{grid-template-columns:1fr}.ccards{grid-template-columns:1fr}.top{padding:16px}nav{padding:8px 12px}.hrow{grid-template-columns:90px 1fr 48px}}
"""

JS = """
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button,.tab').forEach(x=>x.classList.remove('on'));b.classList.add('on');document.getElementById('t-'+b.dataset.t).classList.add('on');try{history.replaceState(null,'','#'+b.dataset.t)}catch(e){}});
if(location.hash){const b=document.querySelector('nav button[data-t="'+location.hash.slice(1)+'"]');if(b)b.click();}
function fv(v){document.querySelectorAll('#ct tbody tr').forEach(r=>r.style.display=(!v||r.dataset.v===v)?'':'none')}
document.querySelectorAll('table.sortable').forEach(t=>{t.querySelectorAll('th').forEach((th,i)=>{let asc=false;th.onclick=()=>{asc=!asc;const rows=[...t.tBodies[0].rows];rows.sort((a,b)=>{const x=a.cells[i],y=b.cells[i];if(!x||!y)return 0;const xa=x.dataset.s??x.innerText,ya=y.dataset.s??y.innerText;const nx=parseFloat(xa),ny=parseFloat(ya);const r=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(xa).localeCompare(String(ya),'fa');return asc?r:-r});rows.forEach(r=>t.tBodies[0].appendChild(r))}})});
"""


def write(html_str: str, date: str):
    from util import DOCS
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(html_str, encoding="utf-8")
    arch = DOCS / "archive"
    arch.mkdir(exist_ok=True)
    (arch / f"{date}.html").write_text(html_str, encoding="utf-8")
    # archive index (keep 31 days)
    files = sorted(arch.glob("*.html"), reverse=True)
    for f in files[31:]:
        f.unlink()
    links = "".join(f'<li><a href="archive/{f.name}">{f.stem}</a></li>' for f in sorted(arch.glob("*.html"), reverse=True))
    (DOCS / "archive.html").write_text(
        f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آرشیو رادار</title>'
        f'<style>body{{background:#0d0d0d;color:#f0efec;font-family:Vazirmatn,Tahoma,sans-serif;padding:24px}}a{{color:#86b6ef}}</style></head>'
        f'<body><h1>آرشیو گزارش‌ها</h1><ul>{links}</ul><p><a href="index.html">گزارش امروز</a></p></body></html>', encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    (DOCS / ".built").write_text(date)   # tells the workflow to (re)deploy GitHub Pages
    return DOCS / "index.html"
