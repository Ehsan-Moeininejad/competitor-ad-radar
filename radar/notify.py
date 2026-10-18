"""Daily email (Gmail SMTP, App Password): a self-contained decision brief with links into the full report.

Layout (table-based, inline styles — safe for Gmail, Apple Mail and Outlook):
  header + buttons → headline & first action → KPI tiles → today's decisions (attack / defend / test)
  → what changed → media plan → competitors → new UTM campaigns → offer benchmark → creatives (inline images)
  → category risk → analyst summary → coverage & useful links.
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

FONT = "Vazirmatn,Tahoma,'Segoe UI',Arial,sans-serif"
C = {"bg": "#0d0d0d", "card": "#1a1a19", "inner": "#232321", "line": "#2f2f2c", "ink": "#f0efec", "ink2": "#c9c7bf",
     "mute": "#9a988f", "acc": "#ef4056", "good": "#2fb35a", "warn": "#f0b429", "bad": "#e5484d", "link": "#86b6ef"}
GOOD_REC = ("خرید مستقیم", "بید پایین در شبکه", "شکاف حضور")


def t(x):
    return html.escape(str(x if x is not None else ""))


def pct(x, d=0):
    return "—" if x is None else f"{round((x or 0) * 100, d) if d else round((x or 0) * 100)}%"


def ltr(x):
    return f'<span dir="ltr" style="unicode-bidi:isolate">{t(x)}</span>'


# ---------------------------------------------------------------- building blocks
def _p(text, size=14, color=None, weight="normal", pad="0"):
    return (f'<div style="font-family:{FONT};font-size:{size}px;line-height:1.9;color:{color or C["ink"]};font-weight:{weight};'
            f'text-align:right;direction:rtl;padding:{pad}">{text}</div>')


def _section(title, inner, link=None, hint=""):
    more = (f'<a href="{t(link)}" style="font-family:{FONT};font-size:12px;color:{C["link"]};text-decoration:none;white-space:nowrap">جزئیات در گزارش ←</a>'
            if link else "")
    return (f'<tr><td style="padding:22px 24px 0">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr>'
            f'<td style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["ink"]};text-align:right;border-right:4px solid {C["acc"]};padding-right:10px">{t(title)}</td>'
            f'<td style="text-align:left">{more}</td></tr></table>'
            + (_p(t(hint), 12, C["mute"], pad="4px 0 0") if hint else "")
            + f'<div style="padding-top:10px">{inner}</div></td></tr>')


def _table(head, rows, widths=None):
    th = "".join(f'<th style="font-family:{FONT};font-size:12px;font-weight:bold;color:{C["mute"]};text-align:right;padding:8px 10px;'
                 f'border-bottom:1px solid {C["line"]};white-space:nowrap"{f" width={w}" if widths and (w := widths[i]) else ""}>{t(h)}</th>'
                 for i, h in enumerate(head))
    trs = "".join("<tr>" + "".join(f'<td style="font-family:{FONT};font-size:13px;line-height:1.7;color:{C["ink"]};text-align:right;padding:8px 10px;'
                                   f'border-bottom:1px solid {C["line"]};vertical-align:top">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl" '
            f'style="background:{C["inner"]};border-radius:10px;border-collapse:separate">{"<tr>" + th + "</tr>"}{trs}</table>')


def _pill(text, color):
    return (f'<span style="display:inline-block;font-family:{FONT};font-size:11px;font-weight:bold;color:{color};border:1px solid {color};'
            f'border-radius:9px;padding:0 7px;line-height:1.8;white-space:nowrap">{t(text)}</span>')


def _button(label, url, primary=True):
    bg, fg, bd = (C["acc"], "#ffffff", C["acc"]) if primary else (C["inner"], C["ink"], C["line"])
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-table;margin:4px 0 4px 6px"><tr>'
            f'<td style="background:{bg};border:1px solid {bd};border-radius:9px">'
            f'<a href="{t(url)}" style="display:inline-block;padding:9px 16px;font-family:{FONT};font-size:13px;font-weight:bold;color:{fg};text-decoration:none">{t(label)}</a>'
            f'</td></tr></table>')


def _meter(v):
    v = int(v or 0)
    col = C["bad"] if v >= 70 else ("#ec835a" if v >= 50 else (C["warn"] if v >= 30 else C["good"]))
    return f'<b style="color:{col};font-family:{FONT}">{v}</b><span style="color:{C["mute"]};font-size:11px"> /100</span>'


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
    """Returns (html, inline_images[(cid, path)], plain_text)."""
    cfg = settings()
    F = _fa()
    from report import _kpis
    base = (page_url or "").rstrip("/") + "/" if page_url else ""
    tab = (lambda k: f"{base}#{k}") if base else (lambda k: None)
    ok_sites = len([1 for c in D["coverage"].values() if c.get("ok")])
    planned = D.get("planned") or ok_sites
    cov_pct = round(100 * ok_sites / max(1, planned))
    plan = D.get("media_plan") or []
    p0 = plan[0] if plan else None
    first_action = (f'{t(F["cat"].get(p0["category"], p0["category"]))} روی {ltr(p0["site"])} با {t(F["fmt"].get(p0["format"], p0["format"]))} — {t(p0["bid"])}'
                    if p0 else "")
    change = next((a["text"] for a in D.get("alerts", []) if a["level"] == "high"), None) or next((a["text"] for a in D.get("alerts", []) if a["level"] == "mid"), None)
    rows = []

    # ---- header
    btns = (_button("باز کردن گزارش کامل", base) + _button("پیشنهاد رسانه", tab("plan"), False) + _button("رقبا", tab("comp"), False)
            + _button("کریتیوها", tab("cre"), False) + _button("کمپین‌ها و UTM", tab("camp"), False)) if base else ""
    rows.append(
        f'<tr><td style="padding:22px 24px 0">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr>'
        f'<td style="font-family:{FONT};font-size:12px;font-weight:bold;color:{C["acc"]};text-align:right">{t(cfg["report"]["brand"])}</td>'
        f'<td style="font-family:{FONT};font-size:12px;color:{C["mute"]};text-align:left" dir="ltr">{t(D["date"])}</td></tr></table>'
        + _p(t(cfg["report"]["title"]), 22, weight="bold", pad="2px 0 0")
        + _p(f'{ok_sites} از {planned} سایت · {D["n_obs"]:,} تبلیغ · {D["runs"]} اسکن امروز', 12, C["mute"])
        + (f'<div style="padding-top:10px;text-align:right" dir="rtl">{btns}</div>' if btns else "")
        + "</td></tr>")

    # ---- headline + first action
    hl = t(change or I.get("headline") or "")
    rows.append(
        f'<tr><td style="padding:16px 24px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl" '
        f'style="background:#2a171b;border:1px solid #4a2128;border-radius:12px"><tr><td style="padding:14px 16px">'
        + _p(hl, 16, weight="bold")
        + (_p(f'<span style="color:{C["acc"]};font-weight:bold">اقدام اول:</span> {first_action}', 14, pad="6px 0 0") if first_action else "")
        + (_p(t(I.get("headline")), 13, C["ink2"], pad="6px 0 0") if change and I.get("headline") else "")
        + "</td></tr></table></td></tr>")
    if cov_pct < 80:
        rows.append(f'<tr><td style="padding:10px 24px 0">' + _p(
            f'<b style="color:{C["warn"]}">پوشش کامل نیست:</b> فقط {cov_pct}% سایت‌های برنامه‌ریزی‌شده با موفقیت اسکن شدند؛ اعداد امروز را با احتیاط بخوانید.', 13, C["ink2"]) + "</td></tr>")

    # ---- KPI tiles (3 x 2)
    k = _kpis(D)
    cells = []
    for x in k:
        dl = x.get("delta") or ""
        dcol = C["bad"] if x.get("delta_cls") == "delta-up" else (C["good"] if x.get("delta_cls") == "delta-dn" else C["mute"])
        cells.append(f'<td width="33%" style="padding:4px" valign="top"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                     f'style="background:{C["inner"]};border-radius:10px"><tr><td style="padding:10px 12px;text-align:right" dir="rtl">'
                     + _p(t(x["label"]), 12, C["ink2"]) + _p(t(x["value"]), 20, weight="bold")
                     + _p((f'<span style="color:{dcol}" dir="ltr">{t(dl)}</span> · ' if dl else "") + t(x.get("sub", "")), 11, C["mute"])
                     + "</td></tr></table></td>")
    grid = "".join("<tr>" + "".join(cells[i:i + 3]) + "</tr>" for i in range(0, len(cells), 3))
    rows.append(f'<tr><td style="padding:14px 20px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{grid}</table></td></tr>')

    # ---- decisions
    atk, dfn, tst = decisions(D, F)

    def col(title, color, items, empty):
        li = "".join(f'<tr><td style="padding:6px 0;border-bottom:1px solid {C["line"]}">'
                     + _p((f'<a href="{t(tab(go))}" style="color:{C["ink"]};text-decoration:none">{h}</a>' if base else h), 13) + "</td></tr>"
                     for h, go in items) or f'<tr><td>{_p(t(empty), 12, C["mute"])}</td></tr>'
        return (f'<td class="stack" width="33%" valign="top" style="padding:4px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:{C["inner"]};border-radius:10px;border-top:3px solid {color}"><tr><td style="padding:10px 12px" dir="rtl">'
                + _p(t(title), 13, weight="bold") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{li}</table></td></tr></table></td>')
    rows.append(_section("تصمیم‌های امروز",
                         f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr>'
                         + col("حمله: کجا وارد شویم", C["good"], atk, "فرصت کم‌تراکم تازه‌ای نیست.")
                         + col("دفاع: به چه واکنش نشان دهیم", C["bad"], dfn, "تهدید فوری دیده نشد.")
                         + col("تست: چه چیز تازه‌ای امتحان کنیم", "#3987e5", tst, "جایگاه یا شبکهٔ تازه‌ای دیده نشد.")
                         + "</tr></table>", base or None))

    # ---- what changed
    lv = {"high": ("▲", C["bad"]), "mid": ("●", "#ec835a"), "low": ("○", C["warn"])}
    al = "".join(f'<tr><td width="18" valign="top" style="font-family:{FONT};color:{lv[a["level"]][1]};padding:5px 0;font-size:13px">{lv[a["level"]][0]}</td>'
                 f'<td style="padding:5px 0">{_p(t(a["text"]), 13)}</td></tr>' for a in D.get("alerts", [])[:7])
    rows.append(_section("چه چیزی تغییر کرد",
                         f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{al}</table>' if al else _p("تغییر مهمی نسبت به دیروز دیده نشد.", 13, C["mute"]),
                         tab("ov")))

    # ---- media plan
    if plan:
        rec_col = {"خرید مستقیم": C["good"], "بید پایین در شبکه": C["good"], "شکاف حضور": C["warn"], "تست": C["warn"]}
        pr = [[f'{ltr(p["site"])}<br>{_pill(p["recommendation"], rec_col.get(p["recommendation"], C["mute"]))}',
               t(F["cat"].get(p["category"], p["category"])),
               f'{t(F["fmt"].get(p["format"], p["format"]))}<br><span style="color:{C["mute"]};font-size:12px">{t(F["plc"].get(p["placement"], p["placement"]))} · {t(F["dev"].get(p["device"], p["device"]))}</span>',
               f'{t(p["route"])}<br><span style="color:{C["mute"]};font-size:12px">{t(p["bid"])}</span>',
               t(p["angle"]), _meter(p["score"])] for p in plan[:5]]
        rows.append(_section("پیشنهاد رسانه: دیجی‌کالا کجا و با چه تبلیغی برود",
                             _table(["سایت", "چه بفروشیم", "فرمت / جایگاه", "مسیر خرید / بید", "زاویهٔ پیام", "امتیاز"], pr), tab("plan"),
                             "۵ پیشنهاد برتر؛ بریف خرید هر کدام در گزارش قابل کپی است"))

    # ---- competitors
    comps = [(b, c) for b, c in D["competitors"].items() if c["level"] in ("core", "vertical")][:8]
    if comps:
        def gr(c):
            g = c.get("growth")
            if c.get("sov_7d") is None:
                return f'<span style="color:{C["mute"]}">جدید</span>'
            if g is None:
                return "—"
            return f'<span dir="ltr" style="color:{C["bad"] if g > 0 else C["good"]}">{"+" if g > 0 else ""}{round(g * 100)}%</span>'
        cr = [[f'<b>{t(b)}</b><br><span style="color:{C["mute"]};font-size:12px">{t(F["lvl"].get(c["level"], c["level"]))} · {t(F["cat"].get(c["vertical"], c["vertical"]))}</span>',
               pct(c["sov"], 1), gr(c), str(len(c["sites"])), f'{c.get("cr_new", 0)}/{c.get("cr_active", 0)}', _meter(c["threat"])] for b, c in comps]
        rows.append(_section("رقبا", _table(["برند", "SOV", "تغییر ۷ روز", "سایت", "کریتیو تازه/فعال", "تهدید"], cr), tab("comp"),
                             "SOV = سهم وزن‌دار دیده‌شدن بین برندهای ای‌کامرس"))

    # ---- new UTM campaigns
    newc = [c for c in D.get("campaigns", []) if c.get("new") and c["level"] != "own"][:6]
    tfa = (D.get("utm") or {}).get("tags_fa") or {}
    mfa = (D.get("utm") or {}).get("medium_fa") or {}
    if newc:
        ur = [[f'<b>{t(c["brand"])}</b>', ltr(c["campaign"]), t("، ".join(tfa.get(x, x) for x in c["tags"][:3]) or "—"),
               t("، ".join(mfa.get(m, m) for m in c["mediums"]) or "—"), str(len(c["sites"]))] for c in newc]
        rows.append(_section("کمپین‌های تازهٔ رقبا (UTM)", _table(["برند", "کمپین", "معنا", "مدیوم", "سایت"], ur), tab("camp"),
                             "نام کمپین‌هایی که امروز اولین بار در لینک تبلیغات دیده شدند"))

    # ---- offer benchmark
    ob = []
    for kk, e in list(D.get("offer_bench", {}).items())[:6]:
        own = e.get("own") or {}
        d, m = e.get("discount"), e.get("months")
        behind = (d and d["v"] > (own.get("discount") or 0)) or (m and m["v"] > (own.get("months") or 0))
        ob.append([t(F["cat"].get(kk, kk)), f'{d["v"]}% <span style="color:{C["mute"]};font-size:12px">{t(d["brand"])}</span>' if d else "—",
                   f'{m["v"]} ماه <span style="color:{C["mute"]};font-size:12px">{t(m["brand"])}</span>' if m else "—",
                   "، ".join(x for x in [f'تخفیف {own["discount"]}%' if own.get("discount") else "", f'اقساط {own["months"]} ماهه' if own.get("months") else ""] if x) or f'<span style="color:{C["mute"]}">دیده نشد</span>',
                   _pill("آفر رقبا قوی‌تر", C["bad"]) if behind else _pill("رقابتی", C["good"])])
    if ob:
        rows.append(_section("بنچمارک آفر", _table(["دسته", "بیشترین تخفیف رقبا", "طولانی‌ترین اقساط", "دیجی‌کالا", "وضعیت"], ob), tab("msg"),
                             "آفری که پیش از افزایش بید باید از آن بهتر بود"))

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
                f'style="background:{C["inner"]};border-radius:10px"><tr><td align="center" valign="middle" height="180" style="background:#141413;border-radius:10px 10px 0 0;padding:10px;height:180px">'
                f'<img src="cid:{cid}" alt="" width="270" style="display:block;max-width:100%;height:auto;max-height:170px;width:auto;border-radius:6px"></td></tr>'
                f'<tr><td style="padding:8px 10px 10px" dir="rtl">'
                + _p(f'<b>{t(r["b"])}</b> ' + (_pill("جدید امروز", C["good"]) if new else _pill(f'{r.get("dy") or 1} روز اجرا', C["warn"])), 13)
                + _p(t((r.get("t") or "بدون متن · فقط تصویر")[:90]), 12, C["ink2"])
                + _p(f'{g["n"]} بار دیده‌شده · {len(g["sites"])} سایت · {t(F["fmt"].get(r["f"], r["f"]))}', 11, C["mute"])
                + "</td></tr></table></td>")
        grid = "".join("<tr>" + "".join(cells[i:i + 2]) + ("<td></td>" if len(cells[i:i + 2]) == 1 else "") + "</tr>" for i in range(0, len(cells), 2))
        rows.append(_section("کریتیوهای رقبا", f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl">{grid}</table>', tab("cre"),
                             "اول کریتیوهای تازهٔ امروز، بعد پرتکرارترین‌ها"))

    # ---- category risk
    cats = [c for c in (D.get("categories") or {}).values() if c.get("rivals")][:6]
    if cats:
        rr = [[t(c["fa"]), _meter(c["risk"]), pct(c["own_share"]), t(c["rivals"][0]["brand"]), pct(c["share"])] for c in cats]
        rows.append(_section("ریسک رقابت در دسته‌ها", _table(["دسته", "ریسک", "سهم دیجی‌کالا", "رقیب اول", "سهم از کل تبلیغات"], rr), tab("comp")))

    # ---- analyst summary
    summ = "".join(f'<li style="margin:4px 0">{t(s)}</li>' for s in (I.get("summary") or [])[:6])
    if summ:
        rows.append(_section("جمع‌بندی تحلیلی", f'<ul dir="rtl" style="font-family:{FONT};font-size:13.5px;line-height:1.9;color:{C["ink"]};padding-right:18px;margin:0">{summ}</ul>',
                             None, "تحلیل " + ("مدل زبانی" if I.get("by") == "llm" else "قاعده‌محور") + f' روی {D["runs"]} اسکن امروز'))

    # ---- footer
    repo = os.getenv("GITHUB_REPOSITORY", "")
    links = []
    if base:
        links += [f'<a href="{t(base)}" style="color:{C["link"]}">گزارش کامل</a>', f'<a href="{t(base)}archive.html" style="color:{C["link"]}">آرشیو ۳۱ روز</a>']
    if repo:
        links += [f'<a href="https://github.com/{t(repo)}/actions" style="color:{C["link"]}">وضعیت اجراها</a>',
                  f'<a href="https://github.com/{t(repo)}/settings/secrets/actions" style="color:{C["link"]}">تغییر گیرنده‌ها</a>']
    rows.append(f'<tr><td style="padding:24px 24px 22px">'
                + _p(" · ".join(links), 12, C["mute"])
                + _p("گزارش کامل (نسخهٔ آفلاین) پیوست همین ایمیل است. داده‌ها از تبلیغات عمومی سایت‌ها جمع‌آوری شده و روی هیچ تبلیغی کلیک نشده است.", 11, C["mute"], pad="6px 0 0")
                + "</td></tr>")

    body = f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
<style>@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
body,table,td,div,a,span,li{{font-family:{FONT}}}
@media (max-width:620px){{.wrap{{width:100%!important}} .stack{{display:block!important;width:100%!important;box-sizing:border-box}}}}</style></head>
<body style="margin:0;padding:0;background:{C["bg"]}" bgcolor="{C["bg"]}">
<div style="display:none;max-height:0;overflow:hidden">{hl}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{C["bg"]}" style="background:{C["bg"]}"><tr><td align="center" style="padding:20px 8px">
<table role="presentation" class="wrap" width="680" cellpadding="0" cellspacing="0" dir="rtl" bgcolor="{C["card"]}" style="width:680px;max-width:680px;background:{C["card"]};border-radius:16px">
{''.join(rows)}
</table></td></tr></table></body></html>"""

    text = "\n".join([f'{cfg["report"]["title"]} · {D["date"]}', change or I.get("headline") or "",
                      ("اقدام اول: " + html.unescape(first_action.replace('<span dir="ltr" style="unicode-bidi:isolate">', "").replace("</span>", ""))) if p0 else "",
                      "", *[f"- {s}" for s in (I.get("summary") or [])[:5]], "", f"گزارش کامل: {base}" if base else ""])
    return body, images, text


def send(D: dict, I: dict, report_path, page_url: str = ""):
    user, pwd = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = [x.strip() for x in os.environ["MAIL_TO"].replace(";", ",").split(",") if x.strip()]
    cfg = settings()
    body, images, text = render(D, I, page_url)
    msg = MIMEMultipart("mixed")
    n_high = len([a for a in D.get("alerts", []) if a["level"] == "high"])
    msg["Subject"] = f"{cfg['email']['subject_prefix']} · {D['date']}" + (f" · {n_high} هشدار فوری" if n_high else "")
    msg["From"] = user
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
    if cfg["email"].get("attach_html", True) and report_path:
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
