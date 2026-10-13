"""UTM / campaign intelligence: aggregates every utm_* seen on competitor ads into campaigns,
decodes what each campaign name means, and keeps a 31-day lifetime registry (first/last seen)."""
import collections
import re

from util import DATA, days_ago, read_json, today, write_json

LEVELS = ("own", "core", "vertical")

# campaign-name decoder: tag -> regex (matched on the lowercased campaign+id+content+term+medium)
TAGS = {
    "retargeting": r"retarget|rtg|remarket|\bdpa\b|dynamic|cart[-_]?abandon|recall",
    "audience": r"targeted|audience|lookalike|\blal\b|segment|custom[-_]?aud|interest",
    "awareness": r"brand(ing)?\b|awareness|reach|instaview|video|teaser|launch",
    "conversion": r"perf|conv|sale\b|purchase|\bcpa\b|roas|order|buy",
    "app": r"\bapp\b|app[-_]?install|\binstall(?!ment)|download|\bpwa\b",
    "installment": r"installment|instalment|aghsat|ghest|bnpl|credit|etebar|vam\b|loan|pay[-_]?later",
    "discount": r"\boff\b|discount|takhfif|\bdeal|amazing|shegeft|flash|clearance|hot[-_]?sale|\d{1,2}(off|%)",
    "free_shipping": r"free[-_]?ship|freeship|ersal[-_]?rayegan|free[-_]?delivery",
    "seasonal": r"yalda|nowr?o+z|norooz|mehr|aban|azar|dey\b|bahman|esfand|farvardin|ordibehesht|khordad|tir\b|mordad|shahrivar|"
                r"black[-_]?friday|\bbf\b|11[-_.]11|ramad?h?an|ramazan|eid|valentine|sepandarmazgan|birthday|anniversary|tavallod|"
                r"autumn|fall\b|paeiz|winter|zemestan|summer|tabestan|spring|bahar|back[-_]?to[-_]?school|school",
    "gold": r"gold|tala\b|zar\b|coin|sekke|silver|noghre",
    "acquisition": r"new[-_]?user|first[-_]?(order|buy)|welcome|signup|sign[-_]?up|register|acq|onboard",
}
TAG_FA = {"retargeting": "ریتارگتینگ", "audience": "هدف‌گیری مخاطب", "awareness": "آگاهی از برند", "conversion": "فروش/تبدیل",
          "app": "نصب اپ", "installment": "اقساط/اعتبار", "discount": "تخفیف/حراج", "free_shipping": "ارسال رایگان",
          "seasonal": "فصلی/مناسبتی", "gold": "طلا", "acquisition": "جذب کاربر جدید",
          "network_id": "شناسهٔ تبلیغ‌دهنده در شبکه"}
MEDIUM = {"cpc": r"cpc|ppc|click", "cpm": r"cpm|impression", "display": r"display|banner|desktopbanner|mobilebanner|gdn",
          "native": r"native|recommend|widget|article", "popup": r"popup|pop[-_]?up|interstitial", "sticky": r"sticky|float",
          "push": r"push|notif", "video": r"video|preroll|instream", "affiliate": r"affiliate|aff\b|partner|cps",
          "reportage": r"reportage|advertorial|sponsored|pr\b", "social": r"social|insta|telegram|rubika|bale|eitaa",
          "crm": r"sms|email|newsletter|crm"}
MEDIUM_FA = {"cpc": "کلیکی (CPC)", "cpm": "نمایشی (CPM)", "display": "بنر نمایشی", "native": "همسان (نیتیو)", "popup": "پاپ‌آپ",
             "sticky": "استیکی", "push": "پوش", "video": "ویدیو", "affiliate": "همکاری در فروش", "reportage": "رپورتاژ",
             "social": "شبکهٔ اجتماعی", "crm": "پیامک/ایمیل", "other": "سایر"}


def decode(u: dict) -> list:
    s = " ".join(str(u.get(k, "")) for k in ("utm_campaign", "utm_id", "utm_content", "utm_term", "utm_medium")).lower()
    tags = [t for t, rx in TAGS.items() if re.search(rx, s)]
    if re.search(r"(^|[^a-z])adv_\d+", (u.get("utm_campaign") or "").lower()):
        tags.append("network_id")
    return tags


def medium_of(m: str) -> str:
    m = (m or "").lower()
    if not m:
        return ""
    return next((k for k, rx in MEDIUM.items() if re.search(rx, m)), "other")


def _name(u: dict) -> str:
    return (u.get("utm_campaign") or u.get("utm_id") or "").strip()[:80]


def build(obs: list) -> dict:
    """D['campaigns'] (one row per brand+campaign), D['utm'] summary, new-campaign list for alerts."""
    t = today()
    ident = [o for o in obs if o.get("level") in LEVELS]
    reg_path = DATA / "utm_registry.json"
    reg = read_json(reg_path, {}) or {}
    baseline = not reg
    camps = {}
    tagged = collections.Counter()
    total = collections.Counter()
    src_mix, med_mix = collections.Counter(), collections.Counter()
    brand_src = collections.defaultdict(collections.Counter)
    brand_med = collections.defaultdict(collections.Counter)
    for o in ident:
        b = o["brand"]
        total[b] += 1
        u = o.get("utm") or {}
        name = _name(u)
        if not u:
            continue
        tagged[b] += 1
        src = (u.get("utm_source") or "").lower()[:40]
        med = medium_of(u.get("utm_medium"))
        if src:
            src_mix[src] += 1
            brand_src[b][src] += 1
        if med:
            med_mix[med] += 1
            brand_med[b][med] += 1
        if not name:
            name = "(بدون نام کمپین)"
        k = b + "|" + name
        c = camps.setdefault(k, {"brand": b, "level": o["level"], "vertical": o.get("vertical", ""), "campaign": name, "n": 0,
                                 "sources": collections.Counter(), "mediums": collections.Counter(), "raw_mediums": collections.Counter(),
                                 "contents": collections.Counter(), "terms": collections.Counter(), "sites": collections.Counter(),
                                 "networks": collections.Counter(), "formats": collections.Counter(), "placements": collections.Counter(),
                                 "devices": collections.Counter(), "categories": collections.Counter(), "landings": collections.Counter(),
                                 "tags": set(), "warm": 0, "shots": [], "titles": collections.Counter(), "offers": collections.Counter()})
        c["n"] += 1
        if src:
            c["sources"][src] += 1
        if med:
            c["mediums"][med] += 1
        if u.get("utm_medium"):
            c["raw_mediums"][u["utm_medium"][:30]] += 1
        if u.get("utm_content"):
            c["contents"][u["utm_content"][:50]] += 1
        if u.get("utm_term"):
            c["terms"][u["utm_term"][:50]] += 1
        c["sites"][o["domain"]] += 1
        c["networks"][o["network"]] += 1
        c["formats"][o["format"]] += 1
        c["placements"][o["placement"]] += 1
        c["devices"][o["session"].split("_")[0]] += 1
        if o.get("category"):
            c["categories"][o["category"]] += 1
        if o.get("adv_domain"):
            c["landings"][o["adv_domain"]] += 1
        if o.get("title"):
            c["titles"][o["title"][:90]] += 1
        c["warm"] += o["session"].endswith("warm")
        c["tags"].update(decode(u))
        if "retargeting" in o.get("campaign_types", []):
            c["tags"].add("retargeting")
        sk = (o.get("shot") or "").split("/")[-1].split(".")[0]
        if sk and sk not in c["shots"] and len(c["shots"]) < 4:
            c["shots"].append(sk)
        for kk in ("discount", "months"):
            if (o.get("offer") or {}).get(kk):
                c["offers"][("تخفیف " if kk == "discount" else "اقساط ") + str(o["offer"][kk]) + ("" if kk == "discount" else " ماهه")] += 1

    # lifetime registry (31 days)
    for k, c in camps.items():
        e = reg.setdefault(k, {"first_seen": t, "days": []})
        e["last_seen"] = t
        if t not in e["days"]:
            e["days"].append(t)
        e["sites"] = sorted(set(e.get("sites", [])) | set(c["sites"]))[-30:]
    cutoff = days_ago(31)
    reg = {k: e for k, e in reg.items() if e.get("last_seen", t) >= cutoff}
    for e in reg.values():
        e["days"] = [d for d in e["days"] if d >= cutoff]
    write_json(reg_path, reg)

    rows = []
    for k, c in camps.items():
        e = reg.get(k, {})
        new = (e.get("first_seen") == t) and not baseline
        rows.append({"brand": c["brand"], "level": c["level"], "vertical": c["vertical"], "campaign": c["campaign"], "ads": c["n"],
                     "sources": dict(c["sources"].most_common(4)), "mediums": dict(c["mediums"].most_common(4)),
                     "raw_mediums": [m for m, _ in c["raw_mediums"].most_common(4)],
                     "contents": [x for x, _ in c["contents"].most_common(8)], "terms": [x for x, _ in c["terms"].most_common(8)],
                     "sites": [s for s, _ in c["sites"].most_common()], "networks": dict(c["networks"].most_common(4)),
                     "formats": dict(c["formats"].most_common(3)), "placements": dict(c["placements"].most_common(3)),
                     "devices": dict(c["devices"]), "categories": dict(c["categories"].most_common(3)),
                     "landings": [x for x, _ in c["landings"].most_common(3)], "titles": [x for x, _ in c["titles"].most_common(3)],
                     "offers": [x for x, _ in c["offers"].most_common(3)],
                     "tags": sorted(c["tags"]), "warm_only": c["warm"] == c["n"], "shots": c["shots"],
                     "first_seen": e.get("first_seen", t), "last_seen": e.get("last_seen", t), "days": len(e.get("days", [])) or 1,
                     "sites_30d": len(e.get("sites", [])), "new": new})
    rows.sort(key=lambda r: (r["level"] == "own", not r["new"], -r["ads"]))
    brands = sorted(total, key=lambda b: -total[b])
    summary = {"coverage": round(sum(tagged.values()) / max(1, sum(total.values())), 3),
               "by_brand": {b: {"ads": total[b], "tagged": tagged[b], "share": round(tagged[b] / max(1, total[b]), 2),
                                "campaigns": sum(1 for r in rows if r["brand"] == b),
                                "sources": dict(brand_src[b].most_common(4)), "mediums": dict(brand_med[b].most_common(5))} for b in brands},
               "sources": dict(src_mix.most_common(12)), "mediums": dict(med_mix.most_common()),
               "active": len(rows), "new": sum(1 for r in rows if r["new"]), "baseline": baseline,
               "tags_fa": TAG_FA, "medium_fa": MEDIUM_FA}
    return {"campaigns": rows[:300], "utm": summary}


def offer_bench(obs: list) -> dict:
    """Per product category: the strongest competitor offer seen today (what Digikala's offer must beat)."""
    num = lambda s: int(re.sub(r"\D", "", str(s).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))) or 0)
    out = {}
    for o in obs:
        if o.get("level") not in LEVELS:
            continue
        cat = o.get("category") or "other"
        of = dict(o.get("offer") or {})
        if o.get("discount") and not of.get("discount"):
            of["discount"] = o["discount"]
        e = out.setdefault(cat, {"discount": None, "months": None, "no_prepay": set(), "free_shipping": set(), "voucher": set(),
                                 "countdown": set(), "gamified": set(), "installment": set(), "own": {"discount": 0, "months": 0, "flags": set()},
                                 "ads_with_offer": 0, "ads": 0})
        e["ads"] += 1
        if not of:
            continue
        e["ads_with_offer"] += 1
        b = o["brand"]
        own = o["level"] == "own"
        d, m = num(of.get("discount", "")), num(of.get("months", ""))
        d = d if 0 < d < 100 else 0
        m = m if 0 < m <= 60 else 0
        if own:
            e["own"]["discount"] = max(e["own"]["discount"], d)
            e["own"]["months"] = max(e["own"]["months"], m)
            e["own"]["flags"].update(k for k in ("no_prepay", "free_shipping", "voucher", "countdown", "gamified", "installment") if of.get(k))
            continue
        if d and (not e["discount"] or d > e["discount"]["v"]):
            e["discount"] = {"v": d, "brand": b, "site": o["domain"]}
        if m and (not e["months"] or m > e["months"]["v"]):
            e["months"] = {"v": m, "brand": b, "site": o["domain"]}
        for k in ("no_prepay", "free_shipping", "voucher", "countdown", "gamified", "installment"):
            if of.get(k):
                e[k].add(b)
    res = {}
    for cat, e in out.items():
        if not e["ads_with_offer"]:
            continue
        res[cat] = {**{k: sorted(v) if isinstance(v, set) else v for k, v in e.items() if k != "own"},
                    "own": {**{k: v for k, v in e["own"].items() if k != "flags"}, "flags": sorted(e["own"]["flags"])}}
    return dict(sorted(res.items(), key=lambda x: -x[1]["ads_with_offer"]))
