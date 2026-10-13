"""Daily analytics: share of voice, threat, ad pressure, opportunity, discovery, 30-day trends."""
import collections
import logging
import statistics

from util import DATA, days_ago, read_json, settings, sha, today, write_json

log = logging.getLogger("radar")
COMP_LEVELS = ("own", "core", "vertical")
PREMIUM = ("popup", "sticky", "header", "above_fold")


def _norm(vals: dict, cap_pct: float = 0.9) -> dict:
    if not vals:
        return {}
    xs = sorted(vals.values())
    cap = xs[min(len(xs) - 1, int(len(xs) * cap_pct))] or max(xs) or 1
    return {k: min(1.0, v / cap) if cap else 0 for k, v in vals.items()}


def build(runs: list, publishers: dict, adv_reg: dict) -> dict:
    cfg = settings()
    pw = cfg["scoring"]["placement_weight"]
    pages = [p for r in runs for p in r.get("pages", [])]
    obs = [o for r in runs for o in r.get("obs", [])]
    n_runs = len(runs)
    D = {"date": today(), "runs": n_runs, "n_obs": len(obs),
         "planned": max([int((r.get("meta") or {}).get("sites") or 0) for r in runs] or [0]),
         "skipped": sorted({s for r in runs for s in ((r.get("meta") or {}).get("skipped_sites") or [])})}

    # ---------------- coverage
    cov = collections.defaultdict(lambda: {"pages": 0, "ok": 0, "slots": 0, "adtech": set(), "errors": set(), "empty_with_tech": 0, "sessions": set()})
    for p in pages:
        c = cov[p["domain"]]
        c["pages"] += 1
        c["sessions"].add(p["session"])
        c["ok"] += 1 if p.get("ok") else 0
        ns = len([s for s in p.get("slots", []) if not s.get("empty")])
        c["slots"] += ns
        c["adtech"].update(p.get("adtech", []))
        if p.get("error"):
            c["errors"].add(p["error"][:70])
        if p.get("ok") and ns == 0 and p.get("adtech"):
            c["empty_with_tech"] += 1
    D["coverage"] = {d: {**{k: v for k, v in c.items() if k not in ("adtech", "errors", "sessions")},
                         "adtech": sorted(c["adtech"]), "errors": sorted(c["errors"])[:2], "sessions": sorted(c["sessions"])}
                     for d, c in cov.items()}
    ok_pages = sum(c["ok"] for c in cov.values())
    D["coverage_pct"] = round(100 * ok_pages / max(1, len(pages)))
    D["geo_suspect"] = sorted(d for d, c in cov.items() if c["empty_with_tech"] >= max(1, c["ok"] // 2) and c["slots"] == 0)

    # ---------------- weights
    for o in obs:
        o["wt"] = pw.get(o["placement"], 1.0)
    ident = [o for o in obs if o.get("level") in COMP_LEVELS]

    # ---------------- competitors
    comp = collections.defaultdict(lambda: collections.defaultdict(float))
    meta = collections.defaultdict(lambda: {"sites": set(), "networks": collections.Counter(), "formats": collections.Counter(),
                                            "placements": collections.Counter(), "ctypes": collections.Counter(), "titles": collections.Counter(),
                                            "utm": collections.Counter(), "landing_types": collections.Counter(), "shots": [],
                                            "creatives": set(), "warm_sites": set(), "cold_sites": set(), "devices": collections.Counter(),
                                            "offers": collections.Counter()})
    for o in ident:
        b = o["brand"]
        comp[b]["w"] += o["wt"]
        comp[b]["n"] += 1
        m = meta[b]
        m["level"], m["vertical"] = o["level"], o["vertical"]
        m["sites"].add(o["domain"])
        m["networks"][o["network"]] += 1
        m["formats"][o["format"]] += 1
        m["placements"][o["placement"]] += 1
        m["devices"][o["session"].split("_")[0]] += 1
        for t in o.get("campaign_types", []):
            m["ctypes"][t] += 1
        if o.get("title"):
            m["titles"][o["title"][:110]] += 1
        if o.get("utm", {}).get("utm_campaign"):
            m["utm"][o["utm"]["utm_campaign"]] += 1
        if o.get("landing_type"):
            m["landing_types"][o["landing_type"]] += 1
        if o.get("shot") and o["shot"] not in [s["shot"] for s in m["shots"]] and len(m["shots"]) < 8:
            m["shots"].append({"shot": o["shot"], "site": o["domain"], "placement": o["placement"], "title": o.get("title", "")})
        m["creatives"].add(o.get("shot") or o.get("title") or o.get("landing"))
        (m["warm_sites"] if o["session"] == "mobile_warm" else m["cold_sites"]).add(o["domain"])
        if o.get("discount"):
            m["offers"]["تخفیف " + o["discount"]] += 1
        for t in o.get("campaign_types", []):
            if t in ("installment", "gamified", "app_install", "seasonal"):
                m["offers"][t] += 1
    total_w = sum(v["w"] for v in comp.values()) or 1
    vert_w = collections.defaultdict(float)
    for b, v in comp.items():
        vert_w[meta[b]["vertical"]] += v["w"]

    # 7-day baseline
    hist = [read_json(f, {}) for f in sorted((DATA / "daily").glob("*.json")) if days_ago(7) <= f.stem < today()] if (DATA / "daily").exists() else []
    base = collections.defaultdict(list)
    for h in hist:
        for b, c in (h.get("competitors") or {}).items():
            base[b].append(c.get("sov", 0))
    yesterday_sites = {}
    if hist:
        for b, c in (hist[-1].get("competitors") or {}).items():
            yesterday_sites[b] = set(c.get("sites", []))

    comps = {}
    n_sites = max(1, len([d for d, c in cov.items() if c["ok"]]))
    for b, v in comp.items():
        m = meta[b]
        sov = v["w"] / total_w
        sov_v = v["w"] / (vert_w[m["vertical"]] or 1)
        b7 = statistics.mean(base[b]) if base[b] else None
        growth = (sov - b7) / b7 if b7 else (1.0 if hist else 0.0)
        reach = len(m["sites"]) / n_sites
        premium = sum(m["placements"][p] for p in PREMIUM) / max(1, v["n"])
        rt_sites = sorted(m["warm_sites"] - m["cold_sites"])
        rt_share = (m["ctypes"]["retargeting"] + len(rt_sites) * 2) / max(1, v["n"])
        promo = (m["ctypes"]["promo"] + m["ctypes"]["gamified"] + m["ctypes"]["installment"]) / max(1, v["n"])
        aggress = min(1.0, 0.45 * min(1, rt_share) + 0.35 * premium + 0.2 * min(1, promo))
        threat = 0 if m["level"] == "own" else round(100 * (0.35 * min(1, sov_v * 1.5) + 0.20 * max(0, min(1, growth)) + 0.20 * min(1, reach * 2) + 0.25 * aggress))
        comps[b] = {
            "level": m["level"], "vertical": m["vertical"], "weight": round(v["w"], 1), "ads": int(v["n"]),
            "sov": round(sov, 4), "sov_vertical": round(sov_v, 4), "sov_7d": round(b7, 4) if b7 is not None else None,
            "growth": round(growth, 2) if b7 else None, "sites": sorted(m["sites"]), "reach": round(reach, 3),
            "new_sites": sorted(m["sites"] - yesterday_sites.get(b, m["sites"])) if b in yesterday_sites else [],
            "networks": dict(m["networks"].most_common()), "formats": dict(m["formats"].most_common()),
            "placements": dict(m["placements"].most_common()), "campaign_types": dict(m["ctypes"].most_common()),
            "devices": dict(m["devices"]), "top_titles": [t for t, _ in m["titles"].most_common(6)],
            "utm_campaigns": [t for t, _ in m["utm"].most_common(8)], "landing_types": dict(m["landing_types"]),
            "retargeting_sites": rt_sites, "premium_share": round(premium, 2), "aggressiveness": round(aggress, 2),
            "threat": threat, "creatives": len(m["creatives"]), "shots": m["shots"], "offers": dict(m["offers"].most_common(6)),
            "surge": bool(b7 and growth >= cfg["scoring"].get("surge_threshold", 0.5) and m["level"] != "own"),
        }
    D["competitors"] = dict(sorted(comps.items(), key=lambda x: -x[1]["weight"]))

    # ---------------- verticals
    from classify import Brands
    vdefs = Brands().verticals
    verts = {}
    for vk, vw in vert_w.items():
        members = {b: c for b, c in comps.items() if c["vertical"] == vk}
        rivals = {b: c for b, c in members.items() if c["level"] != "own"}
        own = sum(c["sov_vertical"] for c in members.values() if c["level"] == "own")
        top_threat = max([c["threat"] for c in rivals.values()] or [0])
        risk = round(min(100, 0.6 * top_threat + 0.4 * 100 * (1 - own)) if rivals else 0)
        verts[vk] = {"fa": vdefs.get(vk, {}).get("fa", vk), "core": vdefs.get(vk, {}).get("core", False), "weight": round(vw, 1),
                     "share_of_total": round(vw / total_w, 3), "own_sov": round(own, 3), "risk": risk,
                     "leaders": [b for b, _ in sorted(members.items(), key=lambda x: -x[1]["weight"])][:5],
                     "rivals": len(rivals)}
    D["verticals"] = dict(sorted(verts.items(), key=lambda x: -x[1]["risk"]))

    # ---------------- sites: pressure & opportunity
    by_site = collections.defaultdict(list)
    for o in obs:
        by_site[o["domain"]].append(o)
    units_runs = collections.defaultdict(set)
    for o in obs:
        units_runs[o["unit"]].add(o.get("shot") or o.get("title") or o.get("landing"))
    s_slots, s_adv, s_comp, s_prem, s_rot = {}, {}, {}, {}, {}
    for d, os_ in by_site.items():
        pg = max(1, cov[d]["ok"])
        s_slots[d] = len({(o["run"], o["session"], o["page"], o["x"], o["y"]) for o in os_}) / pg
        s_adv[d] = len({o["brand"] for o in os_ if o["brand"] != "نامشخص"}) + 0.3 * len({o.get("adv") for o in os_ if o["brand"] == "نامشخص"})
        s_comp[d] = sum(o["wt"] for o in os_ if o["level"] in ("core", "vertical")) / max(1, sum(o["wt"] for o in os_))
        s_prem[d] = sum(1 for o in os_ if o["placement"] in PREMIUM) / max(1, len(os_))
        units = {o["unit"] for o in os_}
        s_rot[d] = statistics.mean([len(units_runs[u]) for u in units]) if units else 0
    n_slots, n_adv, n_rot = _norm(s_slots), _norm(s_adv), _norm(s_rot)
    reach = {}
    for d in cov:
        e = publishers.get(d, {})
        if e.get("sheet_tier"):
            reach[d] = e["sheet_tier"]
        elif e.get("tranco"):
            reach[d] = 1_000_000 / (e["tranco"] + 1000)
        else:
            reach[d] = None
    known = {d: v for d, v in reach.items() if v}
    n_reach = _norm(known, 0.95) if known else {}
    sites = {}
    for d, c in cov.items():
        if not c["ok"]:
            continue
        os_ = by_site.get(d, [])
        pressure = round(100 * (0.30 * n_slots.get(d, 0) + 0.20 * n_adv.get(d, 0) + 0.25 * s_comp.get(d, 0) + 0.10 * s_prem.get(d, 0) + 0.15 * n_rot.get(d, 0)))
        r = n_reach.get(d, 0.45)
        comps_here = sorted({o["brand"] for o in os_ if o["level"] in ("core", "vertical")})
        own_here = any(o["level"] == "own" for o in os_)
        nets = sorted({o["network"] for o in os_} | set(c["adtech"]))
        buyable = bool(set(nets) - {"direct"}) or any(o["network"] == "direct" for o in os_)
        fit = min(1.0, len(comps_here) / 3)
        opp = round(100 * (0.35 * r + 0.35 * (1 - pressure / 100) + 0.15 * fit + 0.15 * (1 if buyable else 0.3))) if os_ or c["adtech"] else round(100 * 0.35 * r)
        direct = any(o["network"] == "direct" for o in os_)
        rec, why = _recommend(pressure, opp, direct, nets, comps_here, own_here, len(os_))
        cheapest = _cheapest_units(os_)
        sites[d] = {"pressure": pressure, "opportunity": opp, "slots_per_page": round(s_slots.get(d, 0), 1),
                    "advertisers": round(s_adv.get(d, 0)), "competitor_share": round(s_comp.get(d, 0), 2),
                    "premium_share": round(s_prem.get(d, 0), 2), "rotation": round(s_rot.get(d, 0), 1),
                    "competitors": comps_here, "own_present": own_here, "networks": nets, "direct_sold": direct,
                    "recommendation": rec, "why": why, "cheapest_units": cheapest,
                    "source": publishers.get(d, {}).get("source", "?"), "category": publishers.get(d, {}).get("category", ""),
                    "reach_known": d in known, "placements": dict(collections.Counter(o["placement"] for o in os_).most_common()),
                    "formats": dict(collections.Counter(o["format"] for o in os_).most_common())}
    D["sites"] = dict(sorted(sites.items(), key=lambda x: -x[1]["opportunity"]))
    D["gaps"] = sorted([d for d, s in sites.items() if len(s["competitors"]) >= 2 and not s["own_present"]],
                       key=lambda d: -len(sites[d]["competitors"]))[:15]

    # ---------------- discovery vs registries
    D["discovery"] = _discovery(obs, pages, cov, adv_reg)

    # ---------------- creatives registry (lifetime)
    vel = {}
    D["long_running"] = _creatives(obs, vel)
    for b, c in D["competitors"].items():
        c["cr_active"], c["cr_new"] = vel.get(b, {}).get("active", 0), vel.get(b, {}).get("new", 0)

    # ---------------- messages / offers / campaigns
    D["campaign_mix"] = dict(collections.Counter(t for o in ident if o["level"] != "own" for t in o.get("campaign_types", [])).most_common())
    D["network_share"] = dict(collections.Counter(o["network"] for o in obs).most_common())
    D["format_share"] = dict(collections.Counter(o["format"] for o in obs).most_common())
    D["placement_share"] = dict(collections.Counter(o["placement"] for o in obs).most_common())
    D["unknown_advertisers"] = len({o.get("adv") for o in obs if o["brand"] == "نامشخص"})
    D["advertisers_total"] = len({o.get("adv") for o in obs})
    D["presence"] = _presence(ident, pages)
    for b, c in D["competitors"].items():
        c["presence"] = D["presence"].get(b, 0)
    D["categories"] = _categories(obs, D["competitors"])
    D["networks"] = _networks(obs, D["sites"], pages)
    D["dayparts"] = _dayparts(ident)
    D["messaging"] = _messaging(ident)
    D["media_plan"] = _media_plan(D, publishers, obs)
    import campaigns as _cp
    D.update(_cp.build(obs))
    D["offer_bench"] = _cp.offer_bench(obs)
    D["rows"] = _rows(obs)
    D["alerts"] = _alerts(D)
    return D


# ---------------------------------------------------------------- ads-decision analytics
THEMES = {
    "price": r"قیمت|ارزان|کمترین|بهترین قیمت|تومان",
    "discount": r"تخفیف|حراج|٪|%|off|آف",
    "installment": r"اقساط|قسطی|اعتبار|بدون پیش|پرداخت بعد|bnpl",
    "delivery": r"ارسال رایگان|ارسال سریع|تحویل|فوری|همان روز|۳۰ دقیقه|30 دقیقه",
    "trust": r"ضمانت|گارانتی|اصل|اورجینال|بازگشت|مرجوعی",
    "gamified": r"گردونه|قرعه|شانس|جایزه|برنده",
    "new": r"جدید|جدیدترین|رونمایی|عرضه|پیش.?فروش",
    "invest": r"سرمایه|سود|صندوق|پس.?انداز",
}
THEME_FA = {"price": "قیمت", "discount": "تخفیف/حراج", "installment": "اقساط/اعتبار", "delivery": "ارسال/سرعت",
            "trust": "اصالت/گارانتی", "gamified": "گیمیفیکیشن", "new": "محصول جدید", "invest": "سرمایه‌گذاری/سود"}


def _presence(ident, pages):
    """Share of scanned pages where the brand showed up at least once (proxy for impression share)."""
    ok_pages = [p for p in pages if p.get("ok")]
    n = max(1, len(ok_pages))
    seen = collections.defaultdict(set)
    for o in ident:
        seen[o["brand"]].add((o["run"], o["domain"], o["session"], o["page"]))
    return {b: round(len(v) / n, 4) for b, v in seen.items()}


def _categories(obs, comps):
    from classify import Brands
    vdefs = Brands().verticals
    cat = collections.defaultdict(lambda: {"w": 0.0, "brands": collections.Counter(), "own": 0.0, "sites": set(), "ads": 0})
    for o in obs:
        if o.get("level") not in ("own", "core", "vertical"):
            continue
        c = cat[o.get("category") or o["vertical"]]
        c["w"] += o["wt"]
        c["ads"] += 1
        c["brands"][o["brand"]] += o["wt"]
        c["sites"].add(o["domain"])
        if o["level"] == "own":
            c["own"] += o["wt"]
    total = sum(c["w"] for c in cat.values()) or 1
    out = {}
    for k, c in cat.items():
        rivals = [(b, w) for b, w in c["brands"].most_common() if comps.get(b, {}).get("level") != "own"]
        own_share = c["own"] / (c["w"] or 1)
        top_share = rivals[0][1] / (c["w"] or 1) if rivals else 0
        out[k] = {"fa": vdefs.get(k, {}).get("fa", k), "core": vdefs.get(k, {}).get("core", False), "group": vdefs.get(k, {}).get("group", "other"),
                  "share": round(c["w"] / total, 3), "ads": c["ads"], "own_share": round(own_share, 3),
                  "rivals": [{"brand": b, "share": round(w / (c["w"] or 1), 3)} for b, w in rivals[:6]],
                  "sites": sorted(c["sites"])[:15], "n_sites": len(c["sites"]),
                  "risk": round(min(100, 100 * (0.5 * (1 - own_share) + 0.3 * top_share + 0.2 * min(1, len(rivals) / 5)))) if rivals else 0}
    return dict(sorted(out.items(), key=lambda x: -x[1]["share"]))


def _networks(obs, sites, pages):
    net = collections.defaultdict(lambda: {"ads": 0, "adv": set(), "comp": 0, "sites": set(), "comp_brands": collections.Counter()})
    for o in obs:
        n = net[o["network"]]
        n["ads"] += 1
        n["adv"].add(o.get("adv") or o["brand"])
        n["sites"].add(o["domain"])
        if o.get("level") in ("core", "vertical"):
            n["comp"] += 1
            n["comp_brands"][o["brand"]] += 1
    tech_sites = collections.Counter(t for p in pages for t in set(p.get("adtech", [])))
    out = {}
    for k, n in net.items():
        ps = [sites[d]["pressure"] for d in n["sites"] if d in sites]
        cs = n["comp"] / max(1, n["ads"])
        out[k] = {"ads": n["ads"], "advertisers": len(n["adv"]), "sites": len(n["sites"]), "tech_sites": tech_sites.get(k, 0),
                  "competitor_share": round(cs, 2), "top_competitors": [b for b, _ in n["comp_brands"].most_common(4)],
                  "avg_pressure": round(statistics.mean(ps)) if ps else None,
                  "bid_climate": "داغ" if cs >= 0.4 else "متوسط" if cs >= 0.2 else "آرام"}
    return dict(sorted(out.items(), key=lambda x: -x[1]["ads"]))


def _dayparts(ident):
    d = collections.defaultdict(collections.Counter)
    for o in ident:
        d[o["brand"]][o.get("daypart", "other")] += 1
    return {b: dict(c) for b, c in d.items()}


def _messaging(ident):
    import re as _re
    per = collections.defaultdict(collections.Counter)
    cta = collections.Counter()
    for o in ident:
        t = " ".join([o.get("title", ""), o.get("landing_title", ""), o.get("discount", "")])
        for th, rx in THEMES.items():
            if _re.search(rx, t, _re.I):
                per[o["brand"]][th] += 1
        for k, v in (o.get("offer") or {}).items():
            if k in ("months", "min_buy", "discount", "voucher"):
                per[o["brand"]]["offer:" + {"months": "اقساط " + str(v) + " ماهه", "min_buy": str(v), "discount": "تخفیف " + str(v), "voucher": str(v)}[k]] += 1
            else:
                per[o["brand"]]["offer:" + k] += 1
        if o.get("cta"):
            cta[o["cta"][:24]] += 1
    market = collections.Counter()
    for c in per.values():
        market.update({k: v for k, v in c.items() if not k.startswith("offer:")})
    own = collections.Counter()
    for o in ident:
        if o["level"] == "own":
            t = " ".join([o.get("title", ""), o.get("landing_title", "")])
            for th, rx in THEMES.items():
                if _re.search(rx, t, _re.I):
                    own[th] += 1
    gaps = [th for th, _ in market.most_common() if own.get(th, 0) == 0][:4]
    return {"by_brand": {b: dict(c.most_common(8)) for b, c in per.items()}, "market": dict(market.most_common()),
            "own": dict(own), "gaps": gaps, "ctas": [c for c, _ in cta.most_common(10)], "themes_fa": THEME_FA}


ANGLE = {
    "installment": "اقساط با دیجی‌پی و «خرید الان، پرداخت بعد»",
    "discount": "شگفت‌انگیزهای روز با درصد تخفیف واقعی روی کریتیو",
    "price": "تضمین بهترین قیمت + مقایسهٔ قیمت",
    "gamified": "کد تخفیف/وچر شانسی کاربران جدید (بدون گردونه شلوغ)",
    "delivery": "ارسال سریع دیجی‌کالا جت / ارسال رایگان پلاس",
    "trust": "ضمانت اصالت و ۷ روز بازگشت",
    "new": "پیش‌فروش و عرضهٔ اول محصولات جدید",
    "invest": "طلای دیجیتال/اقساط با بازگشت سرمایه",
}


def _media_plan(D, publishers, obs):
    """Where should Digikala run which ad type? One concrete recommendation per promising site."""
    from util import load_yaml
    seed = load_yaml("seed_publishers.yaml")
    cats = seed.get("categories") or {}
    sells = set(load_yaml("competitors.yaml").get("digikala_sells") or [])
    net_fa = {k: v.get("fa", k) for k, v in load_yaml("ad_networks.yaml")["networks"].items()}
    by_site = collections.defaultdict(list)
    for o in obs:
        by_site[o["domain"]].append(o)
    long_run = {x.get("title") for x in D.get("long_running", []) if x.get("days", 0) >= 3}
    plan = []
    for d, s in D["sites"].items():
        os_ = by_site.get(d, [])
        if not os_ and not s["networks"]:
            continue
        if s["recommendation"] == "اجتناب/متمایز":
            continue          # too crowded: shown in the sites tab, not proposed as a buy
        pub = publishers.get(d, {})
        ck = pub.get("cat_key") or "news"
        affinity = (cats.get(ck) or {}).get("affinity", ["marketplace", "digital"])
        # 1) category to push: competitors already prove demand here; else the site's audience affinity
        comp_cats = collections.Counter(o.get("category") for o in os_ if o.get("level") in ("core", "vertical"))
        own_cats = {o.get("category") for o in os_ if o.get("level") == "own"}
        cand = [c for c, _ in comp_cats.most_common() if c not in own_cats] + [c for c in affinity if c not in own_cats]
        cand = [c for c in cand if not sells or c in sells]
        push = next((c for c in cand if c), affinity[0] if affinity else "marketplace")
        # 2) unit: least crowded unit; prefer a format where competitor creatives run long (proven), else native
        units = s["cheapest_units"]
        proven = collections.Counter(o["format"] for o in os_ if o.get("title") in long_run and o.get("level") in ("core", "vertical"))
        unit = units[0] if units else None
        fmt = (proven.most_common(1)[0][0] if proven else (unit["format"] if unit else ("native" if "yektanet" in s["networks"] or "mediaad_tapsell" in s["networks"] else "display")))
        placement = unit["placement"] if unit else ("in_feed" if fmt == "native" else "above_fold")
        device = unit["device"] if unit else "mobile"
        # 3) buying route & bid stance
        nets = [n for n in s["networks"] if n != "direct" and not n.startswith("unknown")]
        route = "خرید مستقیم از سایت" if s["direct_sold"] and (not nets or s["pressure"] >= 55) else (f"شبکهٔ {net_fa.get(nets[0], nets[0])} (وایت‌لیست سایت)" if nets else "خرید مستقیم از سایت")
        stance = "بید پایین‌تر از میانگین" if s["pressure"] < 35 else "بید در حد بازار" if s["pressure"] < 65 else "بید رقابتی/پریمیوم (فقط اگر استراتژیک است)"
        # 4) creative angle: counter the dominant competitor message on this site
        themes = collections.Counter()
        import re as _re
        for o in os_:
            if o.get("level") in ("core", "vertical"):
                t = " ".join([o.get("title", ""), o.get("landing_title", "")])
                for th, rx in THEMES.items():
                    if _re.search(rx, t, _re.I):
                        themes[th] += 1
        top_theme = themes.most_common(1)[0][0] if themes else None
        angle = ANGLE.get(top_theme, "قیمت و تنوع دیجی‌کالا + شگفت‌انگیز روز")
        objective = "ریتارگتینگ" if any("retargeting" in o.get("campaign_types", []) or "targeted" in o.get("campaign_types", []) for o in os_ if o.get("level") in ("core", "vertical")) else "جذب کاربر جدید (Prospecting)"
        fit = 1.0 if push in affinity else 0.6
        score = round(s["opportunity"] * fit + (8 if not s["own_present"] and s["competitors"] else 0))
        conf = "بالا" if pub.get("scans", 0) >= 9 else "متوسط" if pub.get("scans", 0) >= 3 else "اولیه"
        offers = []
        for o in os_:
            if o.get("level") in ("core", "vertical"):
                of = o.get("offer") or {}
                bits = [x for x in (o.get("discount") or of.get("discount"), of.get("months") and f"{of['months']} ماه اقساط",
                                    "ارسال رایگان" if of.get("free_shipping") else "", "بدون پیش‌پرداخت" if of.get("no_prepay") else "") if x]
                if bits:
                    offers.append(f"{o['brand']}: {'، '.join(dict.fromkeys(bits))}")
        plan.append({"site": d, "score": min(100, score), "recommendation": s["recommendation"], "why": s["why"],
                     "reach_known": s.get("reach_known", False), "rival_offers": list(dict.fromkeys(offers))[:3], "category": push, "format": fmt, "placement": placement, "device": device,
                     "route": route, "bid": stance, "angle": angle, "counter_theme": top_theme, "objective": objective,
                     "competitors": s["competitors"][:4], "pressure": s["pressure"], "opportunity": s["opportunity"],
                     "own_present": s["own_present"], "confidence": conf, "site_category": ck})
    return sorted(plan, key=lambda x: -x["score"])[:40]


def _offer_text(of: dict) -> str:
    bits = []
    if of.get("discount"):
        bits.append(f"تخفیف {of['discount']}")
    if of.get("months"):
        bits.append(f"اقساط {of['months']} ماهه")
    elif of.get("installment"):
        bits.append("اقساط")
    if of.get("no_prepay"):
        bits.append("بدون پیش‌پرداخت")
    if of.get("free_shipping"):
        bits.append("ارسال رایگان")
    if of.get("min_buy"):
        bits.append(str(of["min_buy"]))
    if of.get("gamified"):
        bits.append("گیمیفیکیشن")
    return "، ".join(bits)[:90]


def _rows(obs):
    """Compact observation rows for client-side filtering in the report (one row per creative sighting)."""
    reg = read_json(DATA / "creatives.json", {}) or {}
    out = []
    for o in obs:
        ck = o.get("shot", "").split("/")[-1] if o.get("shot") else ("t" + sha(o.get("title", ""), 10) if o.get("title") else None)
        life = reg.get(ck) or {}
        out.append({"b": o["brand"], "l": o.get("level", ""), "v": o.get("vertical", ""), "c": o.get("category", ""), "s": o["domain"],
                    "n": o["network"], "f": o["format"], "p": o["placement"], "d": o["session"].split("_")[0], "w": o["session"].endswith("warm"),
                    "dp": o.get("daypart", ""), "t": (o.get("title") or "")[:110], "sh": (o.get("shot") or "").split("/")[-1].split(".")[0],
                    "ct": o.get("campaign_types", []), "lt": o.get("landing_type", ""), "u": (o.get("utm") or {}).get("utm_campaign", "")[:60],
                    "ut": {k2: v[:60] for k, v in (o.get("utm") or {}).items() if (k2 := {"utm_source": "s", "utm_medium": "m", "utm_campaign": "c", "utm_content": "ct", "utm_term": "tm", "utm_id": "id"}.get(k)) and v},
                    "sz": o.get("size", ""), "ld": (o.get("adv_domain") or ""), "wt": o.get("wt", 1),
                    "fs": life.get("first_seen", ""), "ls": life.get("last_seen", ""), "dy": len(life.get("days", [])) or 1,
                    "of": _offer_text(o.get("offer") or {})})
    return out


def _recommend(pressure, opp, direct, nets, comps, own, n):
    net_names = [x for x in nets if x not in ("direct",) and not x.startswith("unknown")]
    if n == 0 and net_names:
        return "تست", "اسلات شبکه هست ولی در این اسکن تبلیغی پر نشده بود. احتمال اینونتوری خالی یا محدودیت IP را با یک تست کم‌هزینه بسنجید."
    if n == 0:
        return "—", "تبلیغی دیده نشد."
    if pressure >= 70:
        return "اجتناب/متمایز", f"فشار بالا ({pressure}). رقابت روی این سایت گران است و فقط با کریتیو متمایز یا جایگاه خاص ارزش دارد."
    if opp >= 62 and direct:
        return "خرید مستقیم", "فشار متوسط/پایین و سایت جایگاه مستقیم می‌فروشد. مذاکرهٔ مستقیم روی جایگاه‌های کم‌تراکم پیشنهاد می‌شود."
    if net_names and pressure < 45:
        return "بید پایین در شبکه", f"فشار پایین. این سایت را در {('، '.join(net_names[:2]))} وایت‌لیست کنید و با بید پایین‌تر از میانگین تست کنید."
    if comps and not own:
        return "شکاف حضور", f"رقبا ({'، '.join(comps[:3])}) حاضرند و دیجی‌کالا نیست."
    return "پایش", "وضعیت متعادل. تغییرات روزهای بعد را دنبال کنید."


def _cheapest_units(os_):
    units = collections.defaultdict(lambda: {"n": 0, "adv": set(), "comp": 0})
    for o in os_:
        k = (o["placement"], o["format"], o["session"].split("_")[0])
        units[k]["n"] += 1
        units[k]["adv"].add(o["brand"])
        units[k]["comp"] += o["level"] in ("core", "vertical")
    ranked = sorted(units.items(), key=lambda x: (x[1]["comp"], len(x[1]["adv"]), x[1]["n"], x[0][2] != "mobile"))  # mobile wins ties
    return [{"placement": k[0], "format": k[1], "device": k[2], "ads": v["n"], "advertisers": len(v["adv"]), "competitor_ads": v["comp"]}
            for k, v in ranked[:3]]


def _discovery(obs, pages, cov, adv_reg):
    """'New' = first seen today on a site that already had history before today.
    Idempotent: re-building the report later the same day gives the same answer."""
    inv = read_json(DATA / "inventory.json", {}) or {}
    pairs = read_json(DATA / "pairs.json", {}) or {}
    t = today()
    site_first = {}
    for k, v in inv.items():
        d = k.split("|")[0]
        site_first[d] = min(site_first.get(d, v["first_seen"]), v["first_seen"])
    old_site = lambda d: site_first.get(d, t) < t
    new_units, new_nets, new_pairs = [], [], []
    for o in obs:
        k = o["unit"]
        e = inv.setdefault(k, {"first_seen": t, "size": o["size"], "network": o["network"]})
        e["last_seen"] = t
        if e["first_seen"] == t and old_site(o["domain"]):
            new_units.append({"site": o["domain"], "page": o["page"], "placement": o["placement"], "format": o["format"],
                              "device": o["session"].split("_")[0], "size": o["size"], "network": o["network"], "brand": o["brand"]})
        if o.get("level") in ("core", "vertical", "own"):
            pe = pairs.setdefault(f"{o['brand']}|{o['domain']}", {"first_seen": t})
            pe["last_seen"] = t
            if pe["first_seen"] == t and old_site(o["domain"]):
                new_pairs.append({"brand": o["brand"], "site": o["domain"], "placement": o["placement"], "format": o["format"]})
    for p in pages:
        for n in p.get("adtech", []):
            e = inv.setdefault(f"{p['domain']}|net|{n}", {"first_seen": t})
            e["last_seen"] = t
            if e["first_seen"] == t and old_site(p["domain"]):
                new_nets.append({"site": p["domain"], "network": n})
    write_json(DATA / "inventory.json", inv)
    write_json(DATA / "pairs.json", pairs)
    dedup = lambda xs: [dict(t_) for t_ in {tuple(sorted(x.items())) for x in xs}]
    unknown_hosts = collections.Counter(h for p in pages for h in p.get("unknown_ad_hosts", []))
    new_adv = [{"name": v.get("name"), "level": v.get("level"), "vertical": v.get("vertical"), "key": k}
               for k, v in adv_reg.items() if v.get("first_seen") == t and v.get("source") != "config"]
    catalog = collections.defaultdict(lambda: collections.Counter())
    for o in obs:
        catalog[o["domain"]][f"{o['placement']} · {o['format']} · {o['size']} · {o['session'].split('_')[0]}"] += 1
    return {"new_units": dedup(new_units)[:60], "new_networks": dedup(new_nets)[:30], "competitor_new_sites": dedup(new_pairs)[:40],
            "new_advertisers": sorted(new_adv, key=lambda x: (x["level"] not in ("core", "vertical"), x["name"] or ""))[:40],
            "candidate_networks": [{"host": h, "sites": n} for h, n in unknown_hosts.most_common(15)],
            "push_sites": sorted({p["domain"] for p in pages if p.get("push_prompt")}),
            "reportage_sites": sorted({o["domain"] for o in obs if o["format"] == "reportage"}),
            "baseline_sites": sorted(d for d in cov if not old_site(d)),
            "catalog": {d: dict(c.most_common(12)) for d, c in catalog.items()}}


def _creatives(obs, velocity=None):
    reg = read_json(DATA / "creatives.json", {}) or {}
    baseline = not reg
    t = today()
    for o in obs:
        if o.get("level") not in ("own", "core", "vertical"):
            continue
        k = o.get("shot", "").split("/")[-1] if o.get("shot") else ("t" + sha(o.get("title", ""), 10) if o.get("title") else None)
        if not k:
            continue
        e = reg.setdefault(k, {"first_seen": t, "days": [], "brand": o["brand"], "title": o.get("title", ""), "sites": []})
        e["last_seen"] = t
        if t not in e["days"]:
            e["days"].append(t)
        if o["domain"] not in e["sites"]:
            e["sites"] = (e["sites"] + [o["domain"]])[-10:]
        if o.get("shot"):
            e["shot"] = o["shot"]
    cutoff = days_ago(31)
    reg = {k: e for k, e in reg.items() if e.get("last_seen", t) >= cutoff}
    write_json(DATA / "creatives.json", reg)
    if velocity is not None:   # creative refresh per brand: active today vs first seen today
        for e in reg.values():
            if e["last_seen"] == t:
                v = velocity.setdefault(e["brand"], {"active": 0, "new": 0})
                v["active"] += 1
                v["new"] += (e["first_seen"] == t) and not baseline
    out = []
    for k, e in reg.items():
        if e["last_seen"] == t:
            out.append({"brand": e["brand"], "title": e["title"], "days": len(e["days"]), "first_seen": e["first_seen"],
                        "sites": len(e["sites"]), "shot": e.get("shot")})
    return sorted(out, key=lambda x: (-x["days"], -x["sites"]))[:20]


def _TAGFA():
    from campaigns import TAG_FA
    return TAG_FA


def _alerts(D):
    al = []
    for b, c in D["competitors"].items():
        if c["surge"]:
            al.append({"level": "high", "text": f"جهش {b}: سهم دیده‌شدن {round(c['sov'] * 100, 1)}٪ در برابر میانگین ۷ روز {round((c['sov_7d'] or 0) * 100, 1)}٪"})
        if c["new_sites"] and c["level"] != "own":
            al.append({"level": "mid", "text": f"{b} وارد سایت‌های جدید شد: {'، '.join(c['new_sites'][:4])}"})
        if c["retargeting_sites"] and c["level"] != "own":
            al.append({"level": "mid", "text": f"{b} در {len(c['retargeting_sites'])} سایت ریتارگتینگ فعال دارد"})
    for a in D["discovery"]["new_advertisers"]:
        if a["level"] in ("core", "vertical"):
            al.append({"level": "mid", "text": f"رقیب تازه در تبلیغات: {a['name']} ({a['vertical']})"})
    newc = [c for c in D.get("campaigns", []) if c["new"] and c["level"] in ("core", "vertical")]
    for c in newc[:4]:
        tg = "، ".join(_TAGFA().get(x, x) for x in c["tags"][:3])
        al.append({"level": "high" if len(c["sites"]) >= 3 or c["ads"] >= 6 else "mid",
                   "text": f"کمپین تازهٔ {c['brand']}: «{c['campaign']}»" + (f" ({tg})" if tg else "") + f" در {len(c['sites'])} سایت"})
    for b, c in D["competitors"].items():
        if c["level"] in ("core", "vertical") and c.get("cr_new", 0) >= 4 and c["cr_new"] >= 0.5 * max(1, c.get("cr_active", 0)):
            al.append({"level": "mid", "text": f"{b} امروز {c['cr_new']} کریتیو تازه آورد (از {c['cr_active']} کریتیو فعال)؛ احتمال شروع موج کمپین"})
    if D["discovery"]["new_networks"]:
        al.append({"level": "low", "text": f"{len(D['discovery']['new_networks'])} شبکهٔ تبلیغاتی تازه روی سایت‌ها دیده شد"})
    if D.get("geo_suspect"):
        al.append({"level": "low", "text": f"{len(D['geo_suspect'])} سایت ادتک داشتند ولی تبلیغی پر نشد (اسلات خالی، SPA یا محدودیت IP)"})
    order = {"high": 0, "mid": 1, "low": 2}
    return sorted(al, key=lambda a: order[a["level"]])[:20]


def save_daily(D):
    slim = {"date": D["date"], "competitors": {b: {k: c[k] for k in ("sov", "sov_vertical", "weight", "sites", "threat", "level", "vertical", "ads")}
                                               for b, c in D["competitors"].items()},
            "sites": {d: {k: s[k] for k in ("pressure", "opportunity", "advertisers", "competitors", "own_present")} for d, s in D["sites"].items()},
            "verticals": {v: {k: x[k] for k in ("risk", "own_sov", "weight", "leaders")} for v, x in D["verticals"].items()},
            "campaign_mix": D["campaign_mix"], "network_share": D["network_share"], "format_share": D["format_share"],
            "coverage_pct": D["coverage_pct"], "n_obs": D["n_obs"]}
    write_json(DATA / "daily" / f"{D['date']}.json", slim)


def monthly():
    """Rolling 30-day view built from daily summaries."""
    files = sorted((DATA / "daily").glob("*.json")) if (DATA / "daily").exists() else []
    days = [read_json(f, {}) for f in files if f.stem >= days_ago(30)]
    if not days:
        return {}
    comp = collections.defaultdict(lambda: {"sov": [], "threat": [], "days": 0, "sites": set(), "level": "", "vertical": ""})
    for d in days:
        for b, c in d.get("competitors", {}).items():
            e = comp[b]
            e["sov"].append((d["date"], c["sov"]))
            e["threat"].append(c["threat"])
            e["days"] += 1
            e["sites"].update(c.get("sites", []))
            e["level"], e["vertical"] = c["level"], c["vertical"]
    sites = collections.defaultdict(lambda: {"pressure": [], "opportunity": []})
    for d in days:
        for s, v in d.get("sites", {}).items():
            sites[s]["pressure"].append(v["pressure"])
            sites[s]["opportunity"].append(v["opportunity"])
    mix = collections.Counter()
    for d in days:
        mix.update(d.get("campaign_mix", {}))
    dates = [d["date"] for d in days]
    out = {"days": len(days), "from": dates[0], "to": dates[-1], "dates": dates,
           "competitors": {b: {"avg_sov": round(statistics.mean(x for _, x in e["sov"]), 4), "series": e["sov"],
                               "avg_threat": round(statistics.mean(e["threat"])), "active_days": e["days"],
                               "sites": len(e["sites"]), "level": e["level"], "vertical": e["vertical"],
                               "trend": round(statistics.mean(x for _, x in e["sov"][-7:]) - statistics.mean(x for _, x in e["sov"][:7]), 4) if len(e["sov"]) >= 8 else None}
                           for b, e in sorted(comp.items(), key=lambda x: -sum(v for _, v in x[1]["sov"]))[:20]},
           "sites": {s: {"avg_pressure": round(statistics.mean(v["pressure"])), "avg_opportunity": round(statistics.mean(v["opportunity"])),
                         "days": len(v["pressure"]), "pressure_std": round(statistics.pstdev(v["pressure"])) if len(v["pressure"]) > 1 else 0}
                     for s, v in sites.items()},
           "campaign_mix": dict(mix.most_common())}
    write_json(DATA / "monthly.json", out)
    return out
