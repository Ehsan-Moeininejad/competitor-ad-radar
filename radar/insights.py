"""Persian analyst narrative from the day's metrics (free LLM), with a rule-based fallback."""
import json
import logging

log = logging.getLogger("radar")

SYSTEM = (
    "You are a senior performance-marketing analyst at Digikala (Iran's largest e-commerce marketplace). "
    "You read a daily competitive ad-monitoring digest collected from Iranian publisher websites and write a sharp, "
    "data-grounded brief in Persian for the performance team (ads, affiliate, eCRM). Rules: use only facts in the data; "
    "every claim must cite a number, site, or brand from it; no generic marketing advice; report-style tone, no "
    "addressing the reader; Latin digits; concise. 'SOV' = weighted share of ad presence among e-commerce brands; "
    "'pressure' 0-100 = ad crowding on a site; 'opportunity' 0-100 = reach × low pressure × audience proof."
)

SCHEMA = (
    "Return JSON: {\"headline\": one Persian sentence, \"summary\": [4-6 Persian bullets], "
    "\"competitor_moves\": [{\"brand\":..., \"move\": what they are doing (sites, formats, offers, retargeting), \"implication\": what it means for Digikala}], "
    "\"vertical_notes\": [{\"vertical\": Persian name, \"risk\": 0-100, \"note\": ...}], "
    "\"actions\": [{\"priority\": \"high|mid|low\", \"action\": concrete media action for Digikala (which category, ad type, placement, buying route, bid stance, message), \"where\": site/placement/network, \"why\": data reason}], "
    "\"inventory_notes\": [Persian bullets about new placements/formats/networks worth testing], "
    "\"monthly\": [2-4 Persian bullets about the 30-day picture, empty if no history]}"
)


def digest_for_llm(D: dict, M: dict) -> str:
    comps = {b: {k: c[k] for k in ("level", "vertical", "sov", "sov_vertical", "growth", "sites", "networks", "formats",
                                   "placements", "campaign_types", "top_titles", "utm_campaigns", "retargeting_sites",
                                   "threat", "offers", "new_sites", "landing_types")}
             for b, c in list(D["competitors"].items())[:14]}
    for c in comps.values():
        c["sites"] = c["sites"][:8]
    sites = {d: {k: s[k] for k in ("pressure", "opportunity", "competitors", "own_present", "networks", "recommendation", "cheapest_units", "direct_sold")}
             for d, s in list(D["sites"].items())[:25]}
    disc = {k: D["discovery"][k][:12] for k in ("new_units", "new_networks", "competitor_new_sites", "new_advertisers", "candidate_networks")}
    mon = {}
    if M and M.get("days", 0) >= 3:
        mon = {"days": M["days"], "competitors": {b: {k: c[k] for k in ("avg_sov", "avg_threat", "trend", "active_days", "sites")}
                                                  for b, c in list(M["competitors"].items())[:10]},
               "campaign_mix": M["campaign_mix"]}
    extra = {"categories": {k: {x: v[x] for x in ("fa", "share", "own_share", "risk", "rivals")} for k, v in list(D.get("categories", {}).items())[:12]},
             "media_plan_top": [{k: p[k] for k in ("site", "category", "format", "placement", "device", "route", "bid", "angle", "objective", "competitors")}
                                for p in D.get("media_plan", [])[:8]],
             "messaging": {k: D.get("messaging", {}).get(k) for k in ("market", "own", "gaps")},
             "networks": {k: {x: v[x] for x in ("ads", "competitor_share", "bid_climate", "top_competitors")} for k, v in D.get("networks", {}).items()}}
    return json.dumps({**extra, "date": D["date"], "runs": D["runs"], "coverage_pct": D["coverage_pct"], "competitors": comps,
                       "sites_top_opportunity": sites, "presence_gaps": D["gaps"],
                       "discovery": disc, "campaign_mix": D["campaign_mix"], "network_share": D["network_share"],
                       "format_share": D["format_share"], "alerts": D["alerts"], "monthly": mon}, ensure_ascii=False)


def write(D: dict, M: dict, llm) -> dict:
    if llm and llm.available:
        try:
            out = _clean(llm.json(SYSTEM, SCHEMA + "\n\nDATA:\n" + digest_for_llm(D, M), max_tokens=4000))
            if out:
                out["by"] = "llm"
                return out
            log.warning("insights LLM answer had the wrong shape — rule-based brief used")
        except Exception as e:  # noqa: BLE001
            log.warning("insights LLM failed, using rule-based brief: %s", e)
    return fallback(D, M)


def _clean(o):
    """Accept only the expected shape; anything odd → None (caller uses the rule-based brief)."""
    if not isinstance(o, dict) or not isinstance(o.get("summary"), list):
        return None
    strs = lambda xs: [str(x) for x in xs if isinstance(x, (str, int, float))] if isinstance(xs, list) else []
    dicts = lambda xs: [x for x in xs if isinstance(x, dict)] if isinstance(xs, list) else []
    out = {"headline": str(o.get("headline") or ""), "summary": strs(o["summary"]),
           "competitor_moves": dicts(o.get("competitor_moves")), "vertical_notes": dicts(o.get("vertical_notes")),
           "actions": dicts(o.get("actions")), "inventory_notes": strs(o.get("inventory_notes")), "monthly": strs(o.get("monthly"))}
    if not out["summary"]:
        return None
    out["headline"] = out["headline"] or out["summary"][0]
    return out


def fallback(D, M):
    comps = [(b, c) for b, c in D["competitors"].items() if c["level"] != "own"]
    top = comps[:3]
    summary = []
    if top:
        summary.append("پرحضورترین رقبا امروز: " + "، ".join(f"{b} ({round(c['sov'] * 100)}٪ سهم، {len(c['sites'])} سایت)" for b, c in top))
    from classify import FORMAT_FA as _F
    from metrics import THEME_FA as _T
    cats = [c for c in D.get("categories", {}).values() if c["rivals"]][:2]
    for c in cats:
        summary.append(f"دستهٔ {c['fa']}: ریسک {c['risk']} از 100؛ {round(c['share'] * 100)}٪ از تبلیغات؛ سهم دیجی‌کالا {round(c['own_share'] * 100)}٪؛ رقیب اول {c['rivals'][0]['brand']}")
    gaps = (D.get("messaging") or {}).get("gaps") or []
    if gaps:
        summary.append("پیام‌هایی که رقبا استفاده می‌کنند و دیجی‌کالا ندارد: " + "، ".join(_T.get(g, g) for g in gaps[:3]))
    best = [d for d, s in D["sites"].items() if s["recommendation"] in ("خرید مستقیم", "بید پایین در شبکه")][:4]
    if best:
        summary.append("کم‌تراکم‌ترین فرصت‌ها: " + "، ".join(f"{d} (فشار {D['sites'][d]['pressure']})" for d in best))
    if D["gaps"]:
        summary.append("شکاف حضور (رقبا هستند، دیجی‌کالا نیست): " + "، ".join(D["gaps"][:5]))
    n_new = len(D["discovery"]["new_units"])
    if n_new:
        summary.append(f"{n_new} جایگاه/فرمت تازه نسبت به روزهای قبل دیده شد")
    from classify import FORMAT_FA
    from util import load_yaml
    nfa = {k: v.get("fa", k) for k, v in load_yaml("ad_networks.yaml")["networks"].items()}
    nfa["direct"] = "خرید مستقیم"
    moves = [{"brand": b, "move": f"حضور در {len(c['sites'])} سایت؛ فرمت غالب {FORMAT_FA.get(next(iter(c['formats']), '-'), '-')}؛ شبکهٔ غالب {nfa.get(next(iter(c['networks']), '-'), '-')}"
              + (f"؛ ریتارگتینگ در {len(c['retargeting_sites'])} سایت" if c["retargeting_sites"] else ""),
              "implication": f"امتیاز تهدید {c['threat']}"} for b, c in comps[:6]]
    from util import load_yaml
    vfa = {k: v.get("fa", k) for k, v in load_yaml("competitors.yaml").get("verticals", {}).items()}
    actions = [{"priority": "high" if p["score"] >= 70 else "mid",
                "action": f"تبلیغ {vfa.get(p['category'], p['category'])} با فرمت {_F.get(p['format'], p['format'])}، {p['bid']}، پیام: {p['angle']}",
                "where": f"{p['site']} · {p['route']}", "why": f"فشار {p['pressure']}، فرصت {p['opportunity']}" + (f"، رقبا: {'، '.join(p['competitors'][:3])}" if p["competitors"] else "")}
               for p in D.get("media_plan", [])[:6]]
    from classify import PLACEMENT_FA as _P
    _dv = {"mobile": "موبایل", "desktop": "دسکتاپ"}
    inv = [f"{u['site']}: {_P.get(u['placement'], u['placement'])} / {_F.get(u['format'], u['format'])} ({_dv.get(u['device'], u['device'])}، {u['size']})"
           for u in D["discovery"]["new_units"][:8]]
    mon = []
    if M and M.get("days", 0) >= 3:
        for b, c in list(M["competitors"].items())[:4]:
            if c["level"] != "own":
                tr = c.get("trend")
                mon.append(f"{b}: میانگین سهم {round(c['avg_sov'] * 100, 1)}٪ در {c['active_days']} روز" + (f"، روند {'+' if tr > 0 else ''}{round(tr * 100, 1)} واحد" if tr is not None else ""))
    headline = summary[0] if summary else "داده کافی برای جمع‌بندی امروز نبود."
    return {"headline": headline, "summary": summary[1:] if len(summary) > 1 else summary, "competitor_moves": moves,
            "vertical_notes": [{"vertical": c["fa"], "risk": c["risk"], "note": f"پیشتازها: {'، '.join(r['brand'] for r in c['rivals'][:3])}"} for c in D.get("categories", {}).values() if c["rivals"]][:6],
            "actions": actions, "inventory_notes": inv, "monthly": mon, "by": "rules"}
