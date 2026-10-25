"""Daily email (Gmail SMTP, App Password): a self-contained decision brief with links into the full report.

Same visual language as the Research Digest email (light page, white cards, Digikala red, Jalali date).
Layout (table-based, inline styles — safe for Gmail, Apple Mail and Outlook):
  header → date, headline, first action, chips, report/tab buttons → KPIs → today's decisions (attack / defend / test)
  → what changed → media plan cards → competitors → new UTM campaigns → offer benchmark → creatives (inline images)
  → category risk → analyst summary → big CTA + archive / runs / recipients links.
"""
import html
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from util import DATA, settings

log = logging.getLogger("radar")

FONT = "Vazirmatn,Vazir,'Vazir Matn',Tahoma,'Segoe UI',Arial,sans-serif"
FA_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# same visual language as the Research Digest email: light page, white cards, Digikala red accent
RED, INK, SOFT, MUTE, LINE, BG, TINT = "#EF4056", "#232933", "#4F545C", "#81858B", "#E4E4E7", "#F0F0F1", "#FFF2F4"
GREEN, AMBER, ORANGE, BLUE = "#1E8A43", "#B7791F", "#D2691E", "#2F6FD6"
GOOD_REC = ("خرید مستقیم", "بید پایین در شبکه", "شکاف حضور")
TD = f'dir="rtl" style="text-align:right;font-family:{FONT};'
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def t(x):
    return html.escape(str(x if x is not None else "").translate(FA_DIG))


def pct(x, d=0):
    return "—" if x is None else f"{round((x or 0) * 100, d) if d else round((x or 0) * 100)}%"


def ltr(x):
    return f'<span dir="ltr" style="unicode-bidi:isolate">{t(x)}</span>'


def jalali(iso: str):
    """'2026-10-18' → ('یکشنبه 26 مهر 1405', '26 مهر')."""
    import datetime as _dt
    gy, gm, gd = (int(x) for x in iso[:10].split("-"))
    wd = WEEKDAYS[_dt.date(gy, gm, gd).weekday()]
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = 1 + days // 31 if days < 186 else 7 + (days - 186) // 30
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return f"{wd} {jd} {MONTHS[jm - 1]} {jy}", f"{jd} {MONTHS[jm - 1]}"


def tint(hexcolor, a=0.10):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


def pill(text, color):
    return (f'<span style="display:inline-block;background:{tint(color)};color:{color};font-family:{FONT};font-size:12px;'
            f'font-weight:bold;padding:2px 10px;border-radius:12px;white-space:nowrap">{t(text)}</span>')


def section(title, sub="", link=None):
    more = (f'<td dir="ltr" style="text-align:left;vertical-align:bottom;padding-bottom:2px"><a href="{t(link)}" style="font-family:{FONT};font-size:12.5px;'
            f'color:{RED};text-decoration:none;white-space:nowrap">← جزئیات در گزارش</a></td>') if link else ""
    return (f'<tr><td style="padding:28px 0 8px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td {TD}"><div style="border-right:4px solid {RED};padding-right:10px">'
            f'<div style="font-size:18px;font-weight:bold;color:{INK};line-height:1.6">{t(title)}</div>'
            + (f'<div style="font-size:13px;color:{MUTE};line-height:1.6">{t(sub)}</div>' if sub else "")
            + f'</div></td>{more}</tr></table></td></tr>')


def card(inner, pad="16px 18px"):
    return (f'<tr><td style="padding:4px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:#ffffff;border:1px solid {LINE};border-radius:12px"><tr><td {TD}padding:{pad}">{inner}</td></tr></table></td></tr>')


def table(head, rows):
    th = "".join(f'<th style="padding:7px 8px;font-family:{FONT};font-size:12px;color:{MUTE};text-align:right;border-bottom:1px solid {LINE};'
                 f'font-weight:bold">{t(h)}</th>' for h in head)
    body = "".join("<tr>" + "".join(f'<td class="tc" style="padding:8px 6px;font-family:{FONT};font-size:13px;line-height:1.7;color:{INK};'
                                    f'border-bottom:1px solid {LINE};vertical-align:top;text-align:right">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<tr><td style="padding:4px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;'
            f'border:1px solid {LINE};border-radius:12px"><tr><td style="padding:6px 8px"><table role="presentation" dir="rtl" width="100%" '
            f'cellpadding="0" cellspacing="0"><tr>{th}</tr>{body}</table></td></tr></table></td></tr>')


def button(label, url, primary=True, big=False):
    pad = "12px 28px" if big else ("9px 18px" if primary else "8px 14px")
    size = "15px" if big else ("13.5px" if primary else "13px")
    if primary:
        return (f'<td style="background:{RED};border-radius:{10 if big else 8}px"><a href="{t(url)}" style="display:inline-block;padding:{pad};'
                f'font-family:{FONT};font-size:{size};font-weight:bold;color:#ffffff;text-decoration:none">{t(label)}</a></td>')
    return (f'<td style="border:1px solid {LINE};border-radius:8px;background:#ffffff"><a href="{t(url)}" style="display:inline-block;padding:{pad};'
            f'font-family:{FONT};font-size:{size};color:{SOFT};text-decoration:none">{t(label)}</a></td>')


def score(v):
    v = int(v or 0)
    col = RED if v >= 70 else (ORANGE if v >= 50 else (AMBER if v >= 30 else GREEN))
    return f'<b style="color:{col}">{v}</b><span style="color:{MUTE};font-size:11px">/100</span>'


# ---------------------------------------------------------------- content helpers
def _fa():
    from classify import CAMPAIGN_FA, FORMAT_FA, PLACEMENT_FA
    from report import LEVEL_FA
    from util import load_yaml
    vfa = {k: v.get("fa", k) for k, v in load_yaml("competitors.yaml").get("verticals", {}).items()}
    nfa = {k: v.get("fa", k) for k, v in load_yaml("ad_networks.yaml")["networks"].items()}
    nfa["direct"] = "خرید مستقیم"
    return {"cat": vfa, "fmt": FORMAT_FA, "plc": PLACEMENT_FA, "lvl": LEVEL_FA, "net": nfa, "camp": CAMPAIGN_FA,
            "dev": {"mobile": "موبایل", "desktop": "دسکتاپ"}}


def decisions(D, F):
    """Attack / defend / test lists, each item = (html text, report tab)."""
    atk = [(f'<b>{t(F["cat"].get(p["category"], p["category"]))}</b> روی {ltr(p["site"])} با {t(F["fmt"].get(p["format"], p["format"]))} · {t(p["bid"])}', "plan")
           for p in D.get("media_plan", []) if p.get("recommendation") in GOOD_REC][:3]
    dfn = []
    for b, c in D["competitors"].items():
        if c.get("surge") and c["level"] != "own":
            dfn.append((f'جهش <b>{t(b)}</b>: سهم {pct(c["sov"], 1)} در برابر میانگین ۷ روز {pct(c.get("sov_7d"), 1)}؛ بید دسته‌های مشترک را حفظ کنید', "comp"))
    for c in [c for c in D.get("campaigns", []) if c.get("new") and c["level"] == "core"][:2]:
        dfn.append((f'کمپین تازهٔ <b>{t(c["brand"])}</b>: {ltr(c["campaign"])} در {len(c["sites"])} سایت', "camp"))
    for k, e in list(D.get("offer_bench", {}).items()):
        own = e.get("own") or {}
        d, m = e.get("discount"), e.get("months")
        if (d and d["v"] > (own.get("discount") or 0)) or (m and m["v"] > (own.get("months") or 0)):
            bits = ([f'تا {d["v"]}% ({t(d["brand"])})'] if d else []) + ([f'اقساط {m["v"]} ماهه ({t(m["brand"])})'] if m else [])
            dfn.append((f'آفر رقبا در <b>{t(F["cat"].get(k, k))}</b> قوی‌تر است: {"، ".join(bits)}', "msg"))
            if len(dfn) >= 5:
                break
    rt = [b for b, c in D["competitors"].items() if c["level"] == "core" and c.get("retargeting_sites")]
    if rt:
        dfn.append((f'ریتارگتینگ {t("، ".join(rt[:3]))}: بازدیدکنندگان را با ریتارگتینگ دیجی‌کالا روی همان شبکه‌ها پس بگیرید', "comp"))
    tst = [(f'جایگاه تازه: {t(F["plc"].get(u["placement"], u["placement"]))} / {t(F["fmt"].get(u["format"], u["format"]))} روی {ltr(u["site"])} ({t(F["dev"].get(u["device"], u["device"]))})', "sites")
           for u in (D.get("discovery") or {}).get("new_units", [])[:2]]
    for n in (D.get("discovery") or {}).get("new_networks", [])[:1]:
        tst.append((f'شبکهٔ تازه {t(F["net"].get(n["network"], n["network"]))} روی {ltr(n["site"])}: قیمت و اینونتوری را استعلام کنید', "sites"))
    for x in [x for x in D.get("long_running", []) if (D["competitors"].get(x["brand"]) or {}).get("level") != "own" and x.get("days", 0) >= 3][:1]:
        tst.append((f'ایدهٔ کریتیو: «{t((x.get("title") or "")[:60])}» از {t(x["brand"])} {x["days"]} روز است اجرا می‌شود', "cre"))
    return atk, dfn[:4], tst[:4]


def _shot_path(k):
    root = DATA / "shots"
    if not k or not root.exists():
        return None
    for d in sorted(root.glob("*"), reverse=True):
        p = d / f"{k}.jpg"
        if p.exists():
            return p
    return None


def top_creatives(D, n=6):
    groups = {}
    for r in D.get("rows", []):
        if r.get("l") not in ("core", "vertical") or not r.get("sh"):
            continue
        k = r["b"] + "|" + (r.get("t") or r["sh"])
        g = groups.setdefault(k, {"r": r, "n": 0, "sites": set()})
        g["n"] += 1
        g["sites"].add(r["s"])
        if r.get("d") == "mobile" and g["r"].get("d") != "mobile":
            g["r"] = r
    out = []
    for g in sorted(groups.values(), key=lambda g: (g["r"].get("fs") != D["date"] and (g["r"].get("dy") or 1) > 1, -g["n"], -len(g["sites"]))):
        p = _shot_path(g["r"]["sh"])
        if p and p.stat().st_size < 400_000:
            out.append((g, p))
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- render
def render(D: dict, I: dict, page_url: str = ""):
    """Returns (html, inline_images[(cid, path)], plain_text, subject)."""
    cfg = settings()
    F = _fa()
    from report import _kpis
    base = (page_url or "").rstrip("/") + "/" if page_url else ""
    tab = (lambda k: f"{base}#{k}") if base else (lambda k: None)
    long_d, short_d = jalali(D["date"])
    ok_sites = len([1 for c in D["coverage"].values() if c.get("ok")])
    planned = D.get("planned") or ok_sites
    cov_pct = round(100 * ok_sites / max(1, planned))
    rivals = [c for c in D["competitors"].values() if c["level"] in ("core", "vertical")]
    own_sov = sum(c["sov"] for c in D["competitors"].values() if c["level"] == "own")
    plan = D.get("media_plan") or []
    p0 = plan[0] if plan else None
    first_action = (f'{t(F["cat"].get(p0["category"], p0["category"]))} روی {ltr(p0["site"])} با {t(F["fmt"].get(p0["format"], p0["format"]))} — {t(p0["bid"])}'
                    if p0 else "")
    change = next((a["text"] for a in D.get("alerts", []) if a["level"] == "high"), None) or next((a["text"] for a in D.get("alerts", []) if a["level"] == "mid"), None)
    n_high = len([a for a in D.get("alerts", []) if a["level"] == "high"])
    n_obs_txt = f"{D['n_obs']:,}"
    rows = []

    # ---- KPIs
    k = _kpis(D)
    cells = []
    for x in k:
        dl = x.get("delta") or ""
        dcol = RED if x.get("delta_cls") == "delta-up" else (GREEN if x.get("delta_cls") == "delta-dn" else MUTE)
        cells.append(f'<td class="kc" width="33%" valign="top" style="padding:4px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                     f'style="background:{BG};border-radius:10px"><tr><td {TD}padding:10px 12px">'
                     f'<div style="font-size:12px;color:{SOFT}">{t(x["label"])}</div>'
                     f'<div style="font-size:19px;font-weight:800;color:{INK};line-height:1.5">{t(x["value"])}</div>'
                     f'<div style="font-size:11.5px;color:{MUTE}">' + (f'<span style="color:{dcol}">' + __import__("re").sub(r"([+\-]?[\d.,]+%?)", r'<span dir="ltr" style="unicode-bidi:isolate">\1</span>', t(dl)) + '</span> · ' if dl else "") + f'{t(x.get("sub", ""))}</div>'
                     f'</td></tr></table></td>')
    grid = "".join("<tr>" + "".join(cells[i:i + 3]) + "</tr>" for i in range(0, len(cells), 3))
    rows.append(section("شاخص‌های امروز", f"{ok_sites} از {planned} سایت · {D['runs']} اسکن"))
    rows.append(card(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{grid}</table>', "8px"))
    if cov_pct < 80:
        rows.append(f'<tr><td {TD}padding:6px 4px 0;font-size:12.5px;color:{AMBER}">پوشش کامل نیست: فقط {cov_pct}% سایت‌های برنامه‌ریزی‌شده با موفقیت اسکن شدند؛ اعداد امروز را با احتیاط بخوانید.</td></tr>')

    # ---- decisions (stacked blocks: reads well on phones)
    atk, dfn, tst = decisions(D, F)
    blocks = ""
    for title, color, items, empty in (("حمله · کجا وارد شویم", GREEN, atk, "فرصت کم‌تراکم تازه‌ای نیست."),
                                       ("دفاع · به چه واکنش نشان دهیم", RED, dfn, "تهدید فوری دیده نشد."),
                                       ("تست · چه چیز تازه‌ای امتحان کنیم", BLUE, tst, "جایگاه یا شبکهٔ تازه‌ای دیده نشد.")):
        li = "".join(f'<li style="margin:3px 0">' + (f'<a href="{t(tab(go))}" style="color:{INK};text-decoration:none">{h} <span style="color:{RED}">←</span></a>' if base else h) + "</li>"
                     for h, go in items) or f'<li style="color:{MUTE}">{t(empty)}</li>'
        blocks += (f'<div style="margin:2px 0 12px"><div>{pill(title, color)}</div>'
                   f'<ul style="margin:6px 0 0;padding-right:18px;font-size:13.5px;line-height:1.95;color:{INK}">{li}</ul></div>')
    rows.append(section("تصمیم‌های امروز", "خلاصهٔ اقدام برای تیم پرفورمنس", base or None))
    rows.append(card(blocks, "14px 18px 4px"))

    # ---- what changed
    lv = {"high": ("فوری", RED), "mid": ("مهم", ORANGE), "low": ("اطلاع", AMBER)}
    al = "".join(f'<tr><td width="54" valign="top" style="padding:6px 0">{pill(lv[a["level"]][0], lv[a["level"]][1])}</td>'
                 f'<td {TD}padding:6px 8px 6px 0;font-size:13.5px;line-height:1.85;color:{INK}">{t(a["text"])}</td></tr>' for a in D.get("alerts", [])[:7])
    rows.append(section("چه چیزی تغییر کرد", "نسبت به روزهای قبل"))
    rows.append(card(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{al}</table>' if al
                     else f'<div style="font-size:13.5px;color:{MUTE}">تغییر مهمی نسبت به دیروز دیده نشد.</div>'))

    # ---- media plan as cards (like digest articles)
    if plan:
        rec_col = {"خرید مستقیم": GREEN, "بید پایین در شبکه": GREEN, "شکاف حضور": AMBER, "تست": AMBER}
        rows.append(section("پیشنهاد رسانه", "دیجی‌کالا کجا و با چه تبلیغی برود؛ ۳ پیشنهاد برتر", tab("plan")))
        for i, p in enumerate(plan[:3], 1):
            offers = "؛ ".join(p.get("rival_offers") or [])[:160]
            rows.append(card(
                f'<div>{pill(p["recommendation"], rec_col.get(p["recommendation"], MUTE))} <span style="color:{MUTE};font-size:12.5px">&nbsp;امتیاز {score(p["score"])} · اطمینان {t(p["confidence"])}</span></div>'
                f'<div style="margin:8px 0 4px;font-size:16.5px;line-height:1.75;font-weight:bold;color:{INK}">{i}. {t(F["cat"].get(p["category"], p["category"]))} روی {ltr(p["site"])}</div>'
                f'<div style="font-size:13.5px;line-height:1.95;color:{SOFT}"><b style="color:{INK}">فرمت</b> · {t(F["fmt"].get(p["format"], p["format"]))} · {t(F["plc"].get(p["placement"], p["placement"]))} · {t(F["dev"].get(p["device"], p["device"]))}</div>'
                f'<div style="font-size:13.5px;line-height:1.95;color:{SOFT}"><b style="color:{INK}">خرید و بید</b> · {t(p["route"])} · {t(p["bid"])}</div>'
                + (f'<div style="font-size:13.5px;line-height:1.95;color:{SOFT}"><b style="color:{INK}">آفر رقبا</b> · {t(offers)}</div>' if offers else "")
                + f'<div style="margin-top:10px;background:{TINT};border-right:3px solid {RED};border-radius:6px;padding:8px 12px;font-size:13.5px;line-height:1.9;color:{INK}">'
                  f'<b style="color:{RED}">زاویهٔ پیام</b> · {t(p["angle"])}</div>'
                + f'<div style="margin-top:8px;font-size:12px;color:{MUTE}">{t(p["why"])} · فشار {p["pressure"]} · فرصت {p["opportunity"]}</div>'))

    # ---- competitors
    comps = [(b, c) for b, c in D["competitors"].items() if c["level"] in ("core", "vertical")][:8]
    if comps:
        def gr(c):
            g = c.get("growth")
            if c.get("sov_7d") is None:
                return f'<span style="color:{MUTE}">جدید</span>'
            if g is None:
                return "—"
            return f'<span dir="ltr" style="color:{RED if g > 0 else GREEN}">{"+" if g > 0 else ""}{round(g * 100)}%</span>'
        cr = [[f'<b>{t(b)}</b><div style="color:{MUTE};font-size:11.5px">{t(F["lvl"].get(c["level"], c["level"]))} · {t(F["cat"].get(c["vertical"], c["vertical"]))}</div>',
               pct(c["sov"], 1), gr(c), str(len(c["sites"])), f'{c.get("cr_new", 0)}/{c.get("cr_active", 0)}', score(c["threat"])] for b, c in comps]
        rows.append(section("رقبا", "SOV = سهم وزن‌دار دیده‌شدن بین برندهای ای‌کامرس", tab("comp")))
        rows.append(table(["برند", "SOV", "تغییر ۷ روز", "سایت", "کریتیو تازه/فعال", "تهدید"], cr))

    # ---- new UTM campaigns
    newc = [c for c in D.get("campaigns", []) if c.get("new") and c["level"] != "own"][:6]
    tfa = (D.get("utm") or {}).get("tags_fa") or {}
    mfa = (D.get("utm") or {}).get("medium_fa") or {}
    if newc:
        ur = [[f'<b>{t(c["brand"])}</b>', ltr(c["campaign"]), " ".join(pill(tfa.get(x, x), BLUE) for x in c["tags"][:2]) or "—",
               t("، ".join(mfa.get(m, m) for m in c["mediums"]) or "—"), str(len(c["sites"]))] for c in newc]
        rows.append(section("کمپین‌های تازهٔ رقبا", "نام کمپین‌هایی که امروز اولین بار در UTM لینک تبلیغات دیده شدند", tab("camp")))
        rows.append(table(["برند", "کمپین", "معنا", "مدیوم", "سایت"], ur))

    # ---- offer benchmark
    ob = []
    for kk, e in list(D.get("offer_bench", {}).items())[:6]:
        own = e.get("own") or {}
        d, m = e.get("discount"), e.get("months")
        behind = (d and d["v"] > (own.get("discount") or 0)) or (m and m["v"] > (own.get("months") or 0))
        ob.append([t(F["cat"].get(kk, kk)), f'{d["v"]}% <span style="color:{MUTE};font-size:11.5px">{t(d["brand"])}</span>' if d else "—",
                   f'{m["v"]} ماه <span style="color:{MUTE};font-size:11.5px">{t(m["brand"])}</span>' if m else "—",
                   t("، ".join(x for x in [f'تخفیف {own["discount"]}%' if own.get("discount") else "", f'اقساط {own["months"]} ماهه' if own.get("months") else ""] if x)) or f'<span style="color:{MUTE}">دیده نشد</span>',
                   pill("رقبا قوی‌ترند", RED) if behind else pill("رقابتی", GREEN)])
    if ob:
        rows.append(section("بنچمارک آفر", "آفری که پیش از افزایش بید باید از آن بهتر بود", tab("msg")))
        rows.append(table(["دسته", "بیشترین تخفیف رقبا", "طولانی‌ترین اقساط", "دیجی‌کالا", "وضعیت"], ob))

    # ---- creatives with inline images
    images = []
    crs = top_creatives(D)
    if crs:
        cells = []
        for i, (g, p) in enumerate(crs):
            r = g["r"]
            cid = f"cr{i}"
            images.append((cid, p))
            new = r.get("fs") == D["date"] or (r.get("dy") or 1) <= 1
            cells.append(
                f'<td class="stack" width="50%" valign="top" style="padding:4px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:#ffffff;border:1px solid {LINE};border-radius:12px"><tr><td align="center" valign="middle" height="170" '
                f'style="background:{BG};border-radius:12px 12px 0 0;padding:10px;height:170px">'
                f'<img src="cid:{cid}" alt="" width="260" style="display:block;max-width:100%;width:auto;height:auto;max-height:160px;border-radius:6px"></td></tr>'
                f'<tr><td {TD}padding:10px 12px 12px">'
                f'<div><b style="font-size:14px;color:{INK}">{t(r["b"])}</b> ' + (pill("جدید امروز", GREEN) if new else pill(f'{r.get("dy") or 1} روز اجرا', AMBER)) + "</div>"
                f'<div style="margin-top:4px;font-size:13px;line-height:1.8;color:{SOFT}">{t((r.get("t") or "بدون متن · فقط تصویر")[:90])}</div>'
                f'<div style="margin-top:4px;font-size:11.5px;color:{MUTE}">{g["n"]} بار دیده‌شده · {len(g["sites"])} سایت · {t(F["fmt"].get(r["f"], r["f"]))}</div>'
                f'</td></tr></table></td>')
        grid = "".join("<tr>" + "".join(cells[i:i + 2]) + ("<td></td>" if len(cells[i:i + 2]) == 1 else "") + "</tr>" for i in range(0, len(cells), 2))
        rows.append(section("کریتیوهای رقبا", "اول کریتیوهای تازهٔ امروز، بعد پرتکرارترین‌ها", tab("cre")))
        rows.append(f'<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{grid}</table></td></tr>')

    # ---- category risk
    cats = [c for c in (D.get("categories") or {}).values() if c.get("rivals")][:6]
    if cats:
        rr = [[t(c["fa"]), score(c["risk"]), pct(c["own_share"]), t(c["rivals"][0]["brand"]), pct(c["share"])] for c in cats]
        rows.append(section("ریسک رقابت در دسته‌ها", "ریسک = سهم پایین دیجی‌کالا + قدرت رقیب اول + تعداد رقبا", tab("comp")))
        rows.append(table(["دسته", "ریسک", "سهم دیجی‌کالا", "رقیب اول", "سهم از تبلیغات"], rr))

    # ---- analyst summary
    summ = "".join(f'<li style="margin:3px 0">{t(s)}</li>' for s in (I.get("summary") or [])[:6])
    if summ:
        rows.append(section("جمع‌بندی تحلیلی", "تحلیل " + ("مدل زبانی" if I.get("by") == "llm" else "قاعده‌محور") + f" روی {D['runs']} اسکن امروز"))
        rows.append(card(f'<ul style="margin:0;padding-right:18px;font-size:13.5px;line-height:1.95;color:{INK}">{summ}</ul>'))

    # ---- header + hero
    def chip(txt, hot=False):
        return (f'<span style="display:inline-block;margin:3px 0 3px 6px;background:{TINT if hot else BG};border-radius:8px;padding:6px 12px;'
                f'font-family:{FONT};font-size:13px;color:{RED if hot else SOFT};{"font-weight:bold;" if hot else ""}white-space:nowrap">{txt}</span>')

    def abtn(label, url, primary=False):
        st = (f"background:{RED};color:#ffffff;font-weight:bold;border:1px solid {RED}" if primary else f"background:#ffffff;color:{SOFT};border:1px solid {LINE}")
        return (f'<a href="{t(url)}" style="display:inline-block;margin:3px 0 3px 6px;padding:8px 16px;border-radius:8px;font-family:{FONT};'
                f'font-size:13.5px;text-decoration:none;white-space:nowrap;{st}">{t(label)}</a>')
    chips = (chip(f"{len(rivals)} رقیب فعال", True) + chip(f"سهم دیجی‌کالا {pct(own_sov, 1)}") + chip(f"{n_obs_txt} تبلیغ")
             + chip(f"{ok_sites} سایت") + (chip(f"{n_high} هشدار فوری", True) if n_high else ""))
    btn_row = (abtn("مشاهدهٔ گزارش کامل", base, True) + "".join(abtn(lbl, tab(k)) for lbl, k in
               (("پیشنهاد رسانه", "plan"), ("رقبا", "comp"), ("کریتیوها", "cre"), ("کمپین‌ها", "camp")))) if base else ""
    hero = (f'<tr><td style="background:#ffffff;border-radius:12px 12px 0 0;border-bottom:3px solid {RED}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td class="stack" {TD}padding:16px 22px;font-size:19px;font-weight:800;color:{RED}">{t(cfg["report"]["title"])}</td>'
            f'<td class="hide-sm" dir="ltr" style="padding:16px 22px;text-align:left;font-family:{FONT};font-size:12.5px;color:{MUTE}">Competitor Ad Radar</td>'
            f'</tr></table></td></tr>'
            f'<tr><td {TD}background:#ffffff;padding:20px 22px 22px;border-radius:0 0 12px 12px">'
            f'<div style="font-size:24px;font-weight:800;color:{INK};line-height:1.5">{t(long_d)}</div>'
            f'<div style="margin-top:10px;font-size:15px;line-height:1.95;color:{INK};font-weight:bold">{t(change or I.get("headline") or "")}</div>'
            + (f'<div style="margin-top:6px;font-size:14px;line-height:1.95;color:{SOFT}">{t(I.get("headline"))}</div>' if change and I.get("headline") else "")
            + (f'<div style="margin-top:12px;background:{TINT};border-right:3px solid {RED};border-radius:6px;padding:9px 12px;font-size:14px;line-height:1.9;color:{INK}">'
               f'<b style="color:{RED}">اقدام اول</b> · {first_action}</div>' if first_action else "")
            + f'<div style="margin-top:12px">{chips}</div>'
            + (f'<div style="margin-top:8px">{btn_row}</div>' if btn_row else "")
            + "</td></tr>")

    # ---- bottom CTA + footer
    repo = os.getenv("GITHUB_REPOSITORY", "")
    small = []
    if base:
        small.append(f'<a href="{t(base)}archive.html" style="color:{MUTE}">آرشیو گزارش‌های ۳۱ روز</a>')
    if repo:
        small += [f'<a href="https://github.com/{t(repo)}/actions" style="color:{MUTE}">وضعیت اجراها</a>',
                  f'<a href="https://github.com/{t(repo)}/settings/secrets/actions" style="color:{MUTE}">تغییر گیرنده‌ها</a>']
    cta = ((f'<tr><td align="center" style="padding:26px 0 8px"><table role="presentation" cellpadding="0" cellspacing="0"><tr>'
            f'{button("مشاهدهٔ گزارش کامل رادار", base, big=True)}</tr></table>' if base else '<tr><td align="center" style="padding:20px 0 8px">')
           + f'<div style="margin-top:12px;font-family:{FONT};font-size:12.5px">{" · ".join(small)}</div></td></tr>')
    foot = (f'<tr><td {TD}padding:14px 0 6px;text-align:center;font-size:11.5px;line-height:1.9;color:{MUTE}">'
            f'گزارش کامل از لینک بالا در دسترس است. داده‌ها از تبلیغات عمومی سایت‌ها جمع‌آوری شده و روی هیچ تبلیغی کلیک نشده است.</td></tr>')

    body = f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;800&display=swap" rel="stylesheet">
<style>@media (max-width:560px){{.stack{{display:block!important;width:100%!important;box-sizing:border-box}} .kc{{display:inline-block!important;width:50%!important;box-sizing:border-box}} .hide-sm{{display:none!important}} .outer{{padding:12px 4px!important}} .tc{{padding:7px 4px!important;font-size:12.5px!important}}}}</style></head>
<body style="margin:0;padding:0;background:{BG}">
<div style="display:none;max-height:0;overflow:hidden">{t(change or I.get("headline") or "")}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td class="outer" align="center" style="padding:20px 10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px">
{hero}
<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{''.join(rows)}</table></td></tr>
{cta}{foot}
</table></td></tr></table></body></html>"""

    subject = f"رادار رقبا {short_d} | {len(rivals)} رقیب فعال | سهم دیجی‌کالا {pct(own_sov, 1)}" + (f" | {n_high} هشدار فوری" if n_high else "")
    strip = lambda h: html.unescape(__import__("re").sub(r"<[^>]+>", "", h))
    text = "\n".join([f'{cfg["report"]["title"]} · {long_d}', strip(t(change or I.get("headline") or "")),
                      ("اقدام اول: " + strip(first_action)) if first_action else "", "",
                      *[f"- {s}" for s in (I.get("summary") or [])[:5]], "", f"گزارش کامل: {base}" if base else ""]).translate(FA_DIG)
    return body, images, text, subject


def send(D: dict, I: dict, report_path, page_url: str = ""):
    user, pwd = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = [x.strip() for x in os.environ["MAIL_TO"].replace(";", ",").split(",") if x.strip()]
    cfg = settings()
    body, images, text, subject = render(D, I, page_url)
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject.translate(FA_DIG)
    msg["From"] = f"Competitor Ad Radar <{user}>"
    msg["To"] = ", ".join(to)
    related = MIMEMultipart("related")
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text, "plain", "utf-8"))
    alt.attach(MIMEText(body, "html", "utf-8"))
    related.attach(alt)
    size = len(body)
    for cid, path in images:
        data = path.read_bytes()
        size += len(data)
        img = MIMEImage(data, _subtype="jpeg")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=f"{cid}.jpg")
        related.attach(img)
    msg.attach(related)
    if cfg["email"].get("attach_html", False) and report_path:
        data = open(report_path, "rb").read()
        # Gmail caps the ENCODED message at 25 MB (base64 adds ~37%)
        if (len(data) + size) * 1.37 < 23_000_000:
            part = MIMEApplication(data, _subtype="html")
            part.add_header("Content-Disposition", "attachment", filename=f"ad-radar-{D['date']}.html")
            msg.attach(part)
        else:
            log.warning("report too large to attach (%.1f MB) — link only", len(data) / 1e6)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pwd)
        s.sendmail(user, to, msg.as_string())
    log.info("email sent to %d recipients", len(to))
