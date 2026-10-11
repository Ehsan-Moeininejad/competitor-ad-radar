"""Turn raw page records into normalized ad observations (rule-based, no LLM needed)."""
import re

from util import domain_of, load_yaml, norm_text, root_domain, strip_tracking, unwrap_redirect, utm_of

IAB = {(300, 250): "MPU 300x250", (336, 280): "Large rect 336x280", (728, 90): "Leaderboard 728x90",
       (970, 90): "Super leaderboard 970x90", (970, 250): "Billboard 970x250", (160, 600): "Skyscraper 160x600",
       (300, 600): "Half page 300x600", (320, 50): "Mobile banner 320x50", (320, 100): "Large mobile 320x100",
       (468, 60): "Banner 468x60", (250, 250): "Square 250x250", (300, 100): "300x100", (120, 600): "Skyscraper 120x600"}
PLACEMENT_FA = {"popup": "پاپ‌آپ / اینترستیشال", "sticky": "استیکی (چسبان)", "header": "هدر", "above_fold": "بالای صفحه",
                "in_content": "داخل متن", "in_feed": "بین فید/لیست", "sidebar": "سایدبار", "below_fold": "پایین صفحه", "footer": "فوتر"}
FORMAT_FA = {"native": "نیتیو / پیشنهاد محتوا", "display": "بنر نمایشی", "sticky_banner": "بنر استیکی", "interstitial": "اینترستیشال/پاپ‌آپ",
             "video": "ویدیو", "text": "متنی", "reportage": "رپورتاژ", "push": "پوش نوتیفیکیشن"}
CAMPAIGN_FA = {"retargeting": "ریتارگتینگ", "promo": "پروموشن/تخفیف", "gamified": "گیمیفیکیشن (گردونه/قرعه‌کشی)",
               "app_install": "نصب اپ", "lead_gen": "لیدجن (فرم)", "installment": "اقساط/BNPL", "product": "محصول‌محور",
               "brand": "برندینگ/آگاهی", "campaign_landing": "لندینگ کمپین", "native_content": "محتوای نیتیو", "seasonal": "مناسبتی", "unknown": "نامشخص"}
APP_HOSTS = ("play.google.com", "apps.apple.com", "cafebazaar.ir", "myket.ir", "sibapp.com", "adtrace.io", "metrix.ir",
             "adjust.com", "app.adjust.com", "onelink.me", "appsflyer.com", "sibche.com")
SEASONAL = re.compile(r"نوروز|یلدا|بلک.?فرایدی|black.?friday|جمعه.?سیاه|شب.?یلدا|مهر|بازگشایی.?مدارس|رمضان|عید|فصل|پاییز|زمستان|تابستان|بهار|حراج.?(فصل|پایان)", re.I)
PROMO = re.compile(r"تخفیف|حراج|ارزان|off|sale|٪|%|رایگان|هدیه|کش.?بک|cashback", re.I)
GAMI = re.compile(r"گردونه|قرعه.?کشی|شانس|برنده.?شو|جایزه|بچرخون", re.I)
INSTALL = re.compile(r"اقساط|قسطی|اعتباری|بدون.?پیش.?پرداخت|bnpl|اسنپ.?پی|پرداخت.?بعد", re.I)


LABELS = set(load_yaml("ad_networks.yaml").get("labels", []))


class Brands:
    def __init__(self):
        cfg = load_yaml("competitors.yaml")
        self.verticals = cfg.get("verticals", {})
        self.brands = cfg.get("brands", [])
        self.by_domain, self.names = {}, []
        for b in self.brands:
            for d in b.get("domains") or []:
                self.by_domain[root_domain(domain_of(d))] = b
            for n in (b.get("names") or []) + [b["name"]]:
                if len(n) >= 3:
                    self.names.append((norm_text(n).lower(), b))
        self.names.sort(key=lambda x: -len(x[0]))
        self.auto = cfg.get("auto_detect", {})

    def by_dom(self, dom):
        return self.by_domain.get(root_domain(dom)) if dom else None

    def by_text(self, text):
        t = norm_text(text).lower()
        for n, b in self.names:
            if len(n) <= 4:
                if re.search(rf"(^|\s){re.escape(n)}($|\s)", t):
                    return b
            elif n in t:
                return b
        return None


def placement_of(sl, page):
    r, vw, vh = sl["rect"], page.get("vw") or 390, page.get("vh") or 844
    ph = page.get("page_h") or 5000
    if sl.get("fixed"):
        floating = sl.get("vtop", 0) > 40 and sl.get("vbottom", vh) < vh - 40
        if r["w"] * r["h"] > 0.35 * vw * vh or (floating and r["h"] > 120):
            return "popup"
    if sl.get("fixed") or sl.get("sticky"):
        return "sticky"
    if sl.get("inHeader") or r["y"] < 170:
        return "header"
    if sl.get("inArticle"):
        return "in_content"
    if sl.get("inAside") or (vw > 900 and r["w"] <= 0.35 * vw and (r["x"] > 0.62 * vw or r["x"] + r["w"] < 0.38 * vw)):
        return "sidebar"
    if sl.get("inFooter") or r["y"] > ph - 900:
        return "footer"
    if r["y"] < vh:
        return "above_fold"
    if sl.get("inList"):
        return "in_feed"
    return "below_fold"


def format_of(sl, placement):
    if placement == "popup":
        return "interstitial"
    if sl.get("hasVideo"):
        return "video"
    if placement == "sticky":
        return "sticky_banner"
    crs = sl.get("creatives") or []
    titled = [c for c in crs if len((c.get("title") or "")) > 12]
    if sl.get("kind") == "network_widget" and (len(crs) >= 2 or titled):
        return "native"
    if crs and not any(c.get("img") for c in crs) and titled and not sl.get("iframeHost"):
        return "text"
    return "display"


def size_of(sl):
    m = sl.get("media") or {}
    w, h = (m["w"], m["h"]) if m.get("w") and m["w"] < sl["rect"]["w"] * 0.9 else (sl["rect"]["w"], sl["rect"]["h"])
    for (iw, ih), name in IAB.items():
        if abs(w - iw) <= 8 and abs(h - ih) <= 8:
            return name
    if w >= 340 and h <= 130:
        return f"Wide banner ~{round(w, -1)}x{round(h, -1)}"
    return f"Custom ~{round(w, -1)}x{round(h, -1)}"


def observations(pages: list, brands: Brands, tracking_params: list, run_id: str, landings: dict) -> list:
    obs = []
    for p in pages:
        if not p.get("ok"):
            continue
        api_by_title = {norm_text(a.get("title", ""))[:40]: a for a in p.get("api_ads", []) if a.get("title")}
        for sl in p["slots"]:
            if sl.get("empty"):
                continue
            plc = placement_of(sl, p)
            fmt = format_of(sl, plc)
            crs = sl.get("creatives") or [{}]
            size = f"Native widget ×{len(crs)}" if fmt == "native" else size_of(sl)
            for ci, c in enumerate(crs[:6]):
                title = norm_text(c.get("title", ""))
                if title in LABELS or len(title) < 3:
                    title = ""
                for lb in ("تبلیغات ", "آگهی ", "Advertisement "):
                    if title.startswith(lb):
                        title = title[len(lb):]
                href = c.get("href") or ""
                if not href and title:
                    a = api_by_title.get(title[:40])
                    if a:
                        href = a["landing"]
                real = unwrap_redirect(href) if href else ""
                if real and root_domain(domain_of(real)) == root_domain(p["domain"]):
                    continue  # house ad / internal promo
                adv_dom = root_domain(domain_of(real)) if real else ""
                brand = brands.by_dom(adv_dom) or brands.by_text(title)
                clean = strip_tracking(real, tracking_params) if real else ""
                land = landings.get(clean) or {}
                o = {
                    "run": run_id, "domain": p["domain"], "session": p["session"], "page": p["kind"],
                    "network": sl.get("network") or "direct", "source": sl.get("kind"), "placement": plc, "format": fmt,
                    "size": size, "x": sl["rect"]["x"], "y": sl["rect"]["y"], "w": sl["rect"]["w"], "h": sl["rect"]["h"],
                    "title": title[:200], "cta": c.get("cta", ""), "price": c.get("price", ""), "discount": c.get("discount", ""),
                    "landing": clean[:400], "adv_domain": adv_dom, "utm": utm_of(real) if real else {},
                    "brand": brand["name"] if brand else "", "level": brand.get("level") if brand else "",
                    "vertical": brand.get("vertical") if brand else "", "shot": sl.get("shot") if ci == 0 else None,
                    "label": sl.get("label", ""), "unit": f"{p['domain']}|{p['kind']}|{plc}|{fmt}|{p['session'].split('_')[0]}",
                    "landing_type": land.get("type", ""), "landing_title": land.get("og_title") or land.get("title", ""),
                }
                o["campaign_types"] = campaign_types(o, land)
                obs.append(o)
        # reportage + push as page-level observations
        for rp in p.get("reportage", [])[:5]:
            obs.append({"run": run_id, "domain": p["domain"], "session": p["session"], "page": p["kind"], "network": "direct",
                        "source": "reportage", "placement": "in_content", "format": "reportage", "size": "-", "x": 0, "y": 0,
                        "w": 0, "h": 0, "title": norm_text(rp.get("title", ""))[:200], "landing": rp.get("href", ""),
                        "adv_domain": "", "utm": {}, "brand": (brands.by_text(rp.get("title", "")) or {}).get("name", ""),
                        "level": "", "vertical": "", "shot": None, "label": "رپورتاژ", "cta": "", "price": "", "discount": "",
                        "unit": f"{p['domain']}|{p['kind']}|in_content|reportage|{p['session'].split('_')[0]}",
                        "campaign_types": ["native_content"], "landing_type": "", "landing_title": ""})
    return obs


def campaign_types(o, land):
    t = " ".join([o["title"], o.get("landing_title", ""), " ".join(o["utm"].values())])
    out = []
    if o["landing"] and any(h in o["landing"] for h in APP_HOSTS) or land.get("type") == "app":
        out.append("app_install")
    if GAMI.search(t) or land.get("gamified"):
        out.append("gamified")
    if INSTALL.search(t) or land.get("installment"):
        out.append("installment")
    if PROMO.search(t) or o["discount"] or land.get("discount"):
        out.append("promo")
    if SEASONAL.search(t):
        out.append("seasonal")
    if land.get("type") == "lead_form" or land.get("lead_form"):
        out.append("lead_gen")
    if re.search(r"retarget|rtg|remarketing|dynamic|dpa", " ".join(o["utm"].values()), re.I):
        out.append("retargeting")
    if (o["price"] or land.get("type") == "product") and "retargeting" not in out:
        out.append("product")
    if land.get("type") == "campaign" and not out:
        out.append("campaign_landing")
    if o["format"] in ("native", "reportage") and not out:
        out.append("native_content")
    if not out and o["landing"] and land.get("type") in ("home", "") and not o["discount"]:
        out.append("brand")
    return out or ["unknown"]
