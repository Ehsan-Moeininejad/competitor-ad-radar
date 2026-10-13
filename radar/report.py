"""Builds the self-contained report app: one HTML file (dark, Vazirmatn embedded, data + screenshots inlined).
The same file is published on GitHub Pages and attached to the daily email."""
import base64
import json

from classify import CAMPAIGN_FA, DAYPART_FA, FORMAT_FA, PLACEMENT_FA, Brands
from metrics import ANGLE, THEME_FA
from util import DATA, DOCS, ROOT, days_ago, load_yaml, now, read_json, settings

SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
OWN = "#ef4056"
LEVEL_FA = {"own": "گروه دیجی‌کالا", "core": "رقیب مستقیم", "vertical": "رقیب ورتیکالی", "none": "غیررقیب", "unknown": "نامشخص"}
DEV_FA = {"mobile": "موبایل", "desktop": "دسکتاپ"}
LANDING_FA = {"product": "صفحهٔ محصول", "category": "دسته‌بندی", "campaign": "لندینگ کمپین", "app": "دانلود اپ", "home": "صفحهٔ اصلی",
              "lead_form": "فرم ثبت‌نام", "other": "سایر"}


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


def _brand_colors(names_levels: dict):
    """Color follows the brand, never its rank: a persistent brand→slot map (Digikala group = Digikala red)."""
    from util import write_json
    path = DATA / "brand_colors.json"
    cmap = read_json(path, {}) or {}
    for b, lv in names_levels.items():
        if lv != "own" and b not in cmap:
            cmap[b] = len(cmap) % len(SERIES)
    write_json(path, cmap)
    return {b: (OWN if lv == "own" else SERIES[cmap[b]]) for b, lv in names_levels.items()}


def _images(D, cap=220):
    """Embed each screenshot once (deduplicated), competitors/own first."""
    keys, out = [], {}
    pri = sorted(D["rows"], key=lambda r: r["l"] not in ("own", "core", "vertical"))
    for r in pri:
        if r["sh"] and r["sh"] not in keys:
            keys.append(r["sh"])
    for c in D.get("campaigns", []):
        for k in c.get("shots", [])[:1]:
            if k and k not in keys:
                keys.append(k)
    for x in D.get("long_running", []):
        k = (x.get("shot") or "").split("/")[-1].split(".")[0]
        x["shot_key"] = k
        if k and k not in keys:
            keys.append(k)
    shot_dirs = sorted((DATA / "shots").glob("*"), reverse=True) if (DATA / "shots").exists() else []
    for k in keys[:cap]:
        for d in shot_dirs:
            p = d / f"{k}.jpg"
            if p.exists():
                out[k] = base64.b64encode(p.read_bytes()).decode()
                break
    return out


def _kpis(D):
    prev = None
    for i in range(1, 4):
        prev = read_json(DATA / "daily" / f"{days_ago(i)}.json")
        if prev:
            break
    rivals = [c for c in D["competitors"].values() if c["level"] in ("core", "vertical")]
    own_sov = sum(c["sov"] for c in D["competitors"].values() if c["level"] == "own")
    sites_ok = len([1 for c in D["coverage"].values() if c["ok"]])

    def delta(cur, old, pct=False, invert=False):
        if old is None:
            return None, ""
        d = cur - old
        if abs(d) < (0.001 if pct else 1):
            return "بدون تغییر", ""
        txt = (f"{'+' if d > 0 else ''}{round(d * 100, 1)} واحد" if pct else f"{'+' if d > 0 else ''}{round(d)}")
        bad = d < 0 if invert else d > 0
        return txt, "delta-up" if bad else "delta-dn"
    p_comp = len([1 for c in (prev or {}).get("competitors", {}).values() if c.get("level") in ("core", "vertical")]) if prev else None
    p_own = sum(c.get("sov", 0) for c in (prev or {}).get("competitors", {}).values() if c.get("level") == "own") if prev else None
    k = []
    d1 = delta(len(rivals), p_comp)
    d2 = delta(own_sov, p_own, pct=True, invert=True)
    d3 = delta(D["n_obs"], (prev or {}).get("n_obs"))
    k.append({"label": "رقیب فعال امروز", "value": len(rivals), "sub": f"{sum(1 for c in rivals if c['level'] == 'core')} مستقیم", "delta": d1[0], "delta_cls": d1[1],
              "help": "برندهای ای‌کامرس رقیب که حداقل یک تبلیغ از آن‌ها دیده شد"})
    k.append({"label": "سهم دیجی‌کالا (SOV)", "value": f"{round(own_sov * 100, 1)}%", "sub": "از حضور برندهای ای‌کامرس", "delta": d2[0], "delta_cls": d2[1]})
    top = max(rivals, key=lambda c: c["threat"], default=None)
    top_name = next((b for b, c in D["competitors"].items() if c is top), "—")
    k.append({"label": "بیشترین تهدید", "value": top_name, "sub": f"امتیاز {top['threat']}" if top else ""})
    k.append({"label": "تبلیغ ثبت‌شده", "value": f"{D['n_obs']:,}", "sub": f"{D['runs']} اسکن امروز", "delta": d3[0], "delta_cls": ""})
    planned = D.get("planned") or sites_ok
    k.append({"label": "سایت اسکن‌شده", "value": f"{sites_ok} از {planned}", "sub": f"{len(D.get('skipped') or [])} سایت به دور بعد رفت" if D.get("skipped") else f"صفحات موفق {D['coverage_pct']}%",
              "help": "سایت‌های اسکن‌شدهٔ موفق نسبت به سایت‌های برنامه‌ریزی‌شده برای امروز"})
    k.append({"label": "جایگاه/فرمت تازه", "value": len(D["discovery"]["new_units"]), "sub": f"{len(D['discovery']['competitor_new_sites'])} ورود رقیب به سایت تازه"})
    return k


def build(D: dict, M: dict, I: dict, publishers: dict, llm_summary: str, nets_cfg: dict) -> str:
    cfg = settings()
    vdefs = Brands().verticals
    seed = load_yaml("seed_publishers.yaml")
    levels = {b: c["level"] for b, c in D["competitors"].items()}
    for b, c in (M or {}).get("competitors", {}).items():
        levels.setdefault(b, c["level"])
    colors = _brand_colors(levels)
    net_fa = {k: v.get("fa", k) for k, v in nets_cfg["networks"].items()}
    net_fa["direct"] = "خرید مستقیم"
    IMGS = _images(D)
    today_cov = {d: {"ok": c["ok"] > 0, "slots": c["slots"]} for d, c in D["coverage"].items()}
    pubs = sorted(({**{k: v for k, v in p.items() if k in ("domain", "source", "category", "cat_key", "status", "tranco", "avg_ads", "scans", "last_scan")},
                    "today": today_cov.get(d)} for d, p in publishers.items()),
                  key=lambda p: ({"sheet": 0, "seed": 1, "discovered": 2}.get(p["source"], 3), p.get("tranco") or 9e9))
    for d, s in D["sites"].items():
        s["cat_key"] = (publishers.get(d) or {}).get("cat_key", "")
    geo = len(D.get("geo_suspect", []))
    planned = D.get("planned") or len(D["coverage"])
    ok_sites = len([1 for c in D["coverage"].values() if c["ok"]])
    # hero: what changed since yesterday + the one action to take
    change = next((a["text"] for a in D.get("alerts", []) if a["level"] == "high"), None) or next((a["text"] for a in D.get("alerts", []) if a["level"] == "mid"), None)
    plan0 = (D.get("media_plan") or [None])[0]
    action = (f"اقدام اول: {vdefs.get(plan0['category'], {}).get('fa', plan0['category'])} روی {plan0['site']} با {FORMAT_FA.get(plan0['format'], plan0['format'])} — {plan0['bid']}") if plan0 else ""
    payload = {
        "meta": {"date": D["date"], "generated": now().strftime("%Y-%m-%d %H:%M"), "runs": D["runs"], "llm": llm_summary,
                 "coverage_pct_sites": round(100 * ok_sites / max(1, planned)), "change": change or "", "action": action,
                 "coverage_note": f"{ok_sites} از {planned} سایت · {D['runs']} اسکن امروز"
                                  + (f" · {geo} سایت ادتک بدون تبلیغ" if geo else "")},
        "fa": {"placement": PLACEMENT_FA, "format": FORMAT_FA, "campaign": {**CAMPAIGN_FA, "installment": "اقساط/BNPL", "free_shipping": "ارسال رایگان",
                                                                              "countdown": "تایمر", "voucher": "کد تخفیف", "discount": "تخفیف"},
               "level": LEVEL_FA, "network": net_fa, "category": {k: v.get("fa", k) for k, v in vdefs.items()}, "device": DEV_FA,
               "daypart": DAYPART_FA, "theme": THEME_FA, "landing": LANDING_FA,
               "sitecat": {k: v.get("fa", k) for k, v in (seed.get("categories") or {}).items()}},
        "catmeta": {k: {"fa": v.get("fa", k), "core": v.get("core", False), "group": v.get("group", "other")} for k, v in vdefs.items()},
        "angles": ANGLE, "colors": colors, "kpis": _kpis(D), "I": I, "M": M or {}, "pubs": pubs,
        **{k: D.get(k) for k in ("competitors", "categories", "sites", "media_plan", "networks", "discovery", "long_running", "messaging",
                                 "dayparts", "alerts", "coverage", "geo_suspect", "gaps", "format_share", "rows",
                                 "campaigns", "utm", "offer_bench")},
    }
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    img_js = json.dumps(IMGS, separators=(",", ":"))
    css = (ROOT / "assets" / "report.css").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "report.js").read_text(encoding="utf-8")
    title = cfg["report"]["title"]
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>{title} · {D['date']}</title><style>{_font_css()}
{css}</style></head><body>
<header class="top"><div><h1>{title}</h1><div class="sub">گزارش {D['date']} · ساخته‌شده {payload['meta']['generated']} به وقت تهران</div></div>
<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px"><span class="brand">{cfg['report']['brand']}</span><span class="fresh"><i></i>{payload['meta']['coverage_note']}</span></div></header>
<nav class="tabs"><div class="in" id="tabs" role="tablist"></div></nav>
<div class="filters" id="filters"></div>
<main id="main"></main>
<div id="scrim" class="ov"></div><aside class="drawer" id="drawer" aria-label="جزئیات رقیب"></aside>
<div id="ov" class="ov"><div class="lb" id="lb"></div></div>
<footer>Competitor Ad Radar · داده‌ها از تبلیغات عمومی سایت‌ها جمع‌آوری شده است · هیچ تبلیغی کلیک نشده است</footer>
<script>window.DATA={data_js};window.IMG={img_js};</script>
<script>{js}</script></body></html>"""


def write(html_str: str, date: str):
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(html_str, encoding="utf-8")
    arch = DOCS / "archive"
    arch.mkdir(exist_ok=True)
    (arch / f"{date}.html").write_text(html_str, encoding="utf-8")
    files = sorted(arch.glob("*.html"), reverse=True)
    for f in files[31:]:
        f.unlink()
    links = "".join(f'<li><a href="archive/{f.name}">{f.stem}</a></li>' for f in sorted(arch.glob("*.html"), reverse=True))
    (DOCS / "archive.html").write_text(
        f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آرشیو رادار</title>'
        f'<style>body{{background:#0d0d0d;color:#f0efec;font-family:Vazirmatn,Tahoma,sans-serif;padding:24px;line-height:2}}a{{color:#86b6ef}}</style></head>'
        f'<body><h1>آرشیو گزارش‌ها (۳۱ روز)</h1><ul>{links}</ul><p><a href="index.html">گزارش امروز</a></p></body></html>', encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    (DOCS / ".built").write_text(date)
    return DOCS / "index.html"
