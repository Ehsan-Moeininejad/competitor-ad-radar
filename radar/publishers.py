"""
Publisher list = owner's Google Sheet (always kept, always scanned first)
               + system list (seed file + weekly auto-discovery), kept in data/publishers.json.
"""
import csv
import io
import logging
import re
import zipfile

import requests

from util import DATA, domain_of, load_yaml, read_json, settings, today, write_json, days_ago

log = logging.getLogger("radar")
REG = DATA / "publishers.json"
DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9\-]+(?:\.[a-z0-9\-]+)+)(/[^\s]*)?$", re.I)
PUBLISHER_HINTS = ("news", "khabar", "akhbar", "mag", "varzesh", "sport", "football", "download", "dl", "soft", "film",
                   "cinema", "game", "tech", "online", "press", "times", "daily", "rooz", "media", "tv", "radio",
                   "blog", "zoom", "digi", "beytoote", "namnak", "setare", "ninisite", "eghtesad", "bourse", "arz")
NOT_PUBLISHER_HINTS = ("bank", "gov", "post", "shop", "store", "market", "pay", "insurance", "bimeh", "university", "ac.ir")


# ---------------------------------------------------------------- sheet
def read_sheet() -> list:
    cfg = settings()["publishers_sheet"]
    url = f"https://docs.google.com/spreadsheets/d/{cfg['id']}/export?format=csv&gid={cfg.get('gid', '0')}"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code != 200 or "<html" in r.text[:300].lower():
            raise RuntimeError(f"HTTP {r.status_code} — شیت باید Anyone with the link → Viewer باشد")
        r.encoding = "utf-8"
        rows = list(csv.reader(io.StringIO(r.text)))
    except Exception as e:  # noqa: BLE001
        log.error("publishers sheet unreadable: %s — using last known sheet list", e)
        return [p for p in (read_json(REG, {}) or {}).values() if p.get("source") == "sheet"]
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    # find the column that looks most like domains/urls
    best, best_hits = None, 0
    for ci in range(len(header)):
        hits = sum(1 for row in rows[1:] if ci < len(row) and DOMAIN_RE.match(row[ci].strip()))
        if hits > best_hits:
            best, best_hits = ci, hits
    has_header = best is not None and not DOMAIN_RE.match((rows[0][best] if best < len(rows[0]) else "").strip())
    data_rows = rows[1:] if has_header else rows
    if best is None:
        log.error("no domain column found in sheet")
        return []

    def col(names):
        for i, h in enumerate(header):
            if any(n.lower() == h or n.lower() in h for n in names):
                return i
        return None
    oc = cfg.get("optional_columns", {})
    c_cat, c_tier, c_pages = col(oc.get("category", [])), col(oc.get("tier", [])), col(oc.get("pages", []))
    out, seen = [], set()
    for row in data_rows:
        if best >= len(row):
            continue
        cell = row[best].strip()
        m = DOMAIN_RE.match(cell)
        if not m:
            continue
        dom = domain_of(cell)
        if not dom or dom in seen:
            continue
        seen.add(dom)
        pages = []
        if m.group(2) and len(m.group(2)) > 1:
            pages.append(cell if cell.startswith("http") else "https://" + cell)
        if c_pages is not None and c_pages < len(row):
            pages += [u.strip() for u in re.split(r"[\s,]+", row[c_pages]) if u.strip().startswith("http")]
        tier = None
        if c_tier is not None and c_tier < len(row):
            try:
                tier = float(re.sub(r"[^\d.]", "", row[c_tier].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))) or "x")
            except ValueError:
                tier = None
        out.append({"domain": dom, "source": "sheet", "category": (row[c_cat].strip() if c_cat is not None and c_cat < len(row) else ""),
                    "sheet_tier": tier, "pages": pages[:3]})
    log.info("sheet: %d publishers", len(out))
    return out


# ---------------------------------------------------------------- registry
def load_registry() -> dict:
    return read_json(REG, {}) or {}


def sync_registry(sheet_rows: list) -> dict:
    reg = load_registry()
    seed = load_yaml("seed_publishers.yaml")
    exclude = set(seed.get("exclude") or [])
    sheet_doms = {r["domain"] for r in sheet_rows}
    # sheet rows: always present, always source=sheet (owner list wins)
    for r in sheet_rows:
        e = reg.get(r["domain"], {"added": today(), "scans": 0, "ad_scans": 0, "zero_streak": 0, "status": "active"})
        e.update({"domain": r["domain"], "source": "sheet", "status": "active", "pages": r.get("pages", [])})
        if r.get("category"):
            e["category"] = r["category"]
        if r.get("sheet_tier") is not None:
            e["sheet_tier"] = r["sheet_tier"]
        reg[r["domain"]] = e
    # rows removed from the sheet go back to the system list (not deleted)
    for d, e in reg.items():
        if e.get("source") == "sheet" and d not in sheet_doms:
            e["source"] = "seed"
    for cat, doms in (seed.get("sites") or {}).items():
        for d in doms or []:
            d = domain_of(d)
            if d and d not in reg:
                reg[d] = {"domain": d, "source": "seed", "category": cat, "added": today(), "scans": 0,
                          "ad_scans": 0, "zero_streak": 0, "status": "probation"}
    for d in exclude:
        reg.pop(domain_of(d), None)
    write_json(REG, reg)
    return reg


def select_for_run(reg: dict) -> list:
    cfg = settings()["publishers_sheet"]
    cap = int(cfg.get("max_sites", 120))
    sheet = sorted([e for e in reg.values() if e.get("source") == "sheet"], key=lambda e: e.get("last_scan") or "")
    rest = [e for e in reg.values() if e.get("source") != "sheet"]

    def density(e):
        return (e.get("avg_ads") or 0) * 10 + (1e6 - (e.get("tranco") or 1e6)) / 1e5
    # least-recently scanned first (sites cut by the time budget come first next run), then densest
    active = sorted([e for e in rest if e.get("status") == "active"], key=lambda e: (e.get("last_scan") or "", -density(e)))
    probation = sorted([e for e in rest if e.get("status") == "probation"], key=lambda e: e.get("tranco") or 1e6)
    dormant = [e for e in rest if e.get("status") == "dormant" and (e.get("last_scan") or "") < days_ago(30)]
    explore = max(8, cap // 8)
    picked = sheet[:cap]
    room = cap - len(picked)
    picked += probation[:min(explore, room)]
    room = cap - len(picked)
    picked += dormant[:min(3, room)]
    room = cap - len(picked)
    picked += active[:room]
    log.info("run selection: %d sites (%d sheet, %d system)", len(picked), min(len(sheet), cap), len(picked) - min(len(sheet), cap))
    return picked


def update_after_scan(reg: dict, per_site: dict):
    """per_site: domain -> {'ok': bool, 'ads': int}"""
    for d, s in per_site.items():
        e = reg.get(d)
        if not e:
            continue
        e["last_scan"] = today()
        if not s.get("ok"):
            e["fail_streak"] = e.get("fail_streak", 0) + 1
            continue
        e["fail_streak"] = 0
        e["scans"] = e.get("scans", 0) + 1
        ads = s.get("ads", 0)
        e["avg_ads"] = round(((e.get("avg_ads") or 0) * 0.7 + ads * 0.3), 2) if e.get("scans", 0) > 1 else ads
        if ads > 0:
            e["ad_scans"] = e.get("ad_scans", 0) + 1
            e["zero_streak"] = 0
            if e.get("source") != "sheet":
                e["status"] = "active"
        else:
            e["zero_streak"] = e.get("zero_streak", 0) + 1
            if e.get("source") != "sheet" and e["zero_streak"] >= 3:
                e["status"] = "dormant"
    write_json(REG, reg)


# ---------------------------------------------------------------- weekly discovery
def discover(reg: dict, llm, ext_domains: dict) -> list:
    """Find new publisher candidates from the Tranco ranking (.ir) and from links between publishers.
    ext_domains: domain -> number of distinct publishers linking to it (non-ad links)."""
    meta = read_json(DATA / "discovery_meta.json", {}) or {}
    if meta.get("last") and meta["last"] > days_ago(7):
        return None  # not due this week
    ranks, known = _tranco_ir(set(reg))
    for d, rk in known.items():
        reg[d]["tranco"] = rk
    cands = {}
    for d, rk in sorted(ranks.items(), key=lambda x: x[1])[:3000]:
        if d not in reg and not any(h in d for h in NOT_PUBLISHER_HINTS):
            cands[d] = {"tranco": rk}
    for d, n in ext_domains.items():
        if n >= 2 and d not in reg:
            cands.setdefault(d, {})["linked_by"] = n
    cand_list = sorted(cands.items(), key=lambda x: (-(x[1].get("linked_by") or 0), x[1].get("tranco") or 1e7))[:60]
    added = []
    verdicts = {}
    if llm and llm.available and cand_list:
        try:
            out = llm.json(
                "You classify Iranian websites. For each domain decide if it is an ad-supported CONTENT PUBLISHER "
                "(news, magazine, sports, tech, download, entertainment, lifestyle, forum, education content) that sells "
                "display/native ad space. Shops, banks, government, apps' own sites, payment, universities = false.",
                "Return {\"items\":[{\"domain\":..., \"publisher\":true|false, \"category\":\"news|tech|sports|lifestyle|download|economy|entertainment|education|other\"}]}\n"
                + "\n".join(d for d, _ in cand_list), max_tokens=3000)
            for it in out.get("items", []) if isinstance(out.get("items"), list) else []:
                if isinstance(it, dict):
                    verdicts[domain_of(str(it.get("domain", "")))] = it
        except Exception as e:  # noqa: BLE001
            log.warning("discovery classification failed: %s", e)
    for d, info in cand_list:
        v = verdicts.get(d)
        ok = (v.get("publisher") is True or str(v.get("publisher")).lower() == "true") if v else any(h in d for h in PUBLISHER_HINTS)
        if not ok:
            continue
        reg[d] = {"domain": d, "source": "discovered", "category": (v or {}).get("category", "other"), "added": today(),
                  "tranco": info.get("tranco"), "linked_by": info.get("linked_by"), "scans": 0, "ad_scans": 0,
                  "zero_streak": 0, "status": "probation"}
        added.append(d)
        if len(added) >= 25:
            break
    write_json(REG, reg)
    write_json(DATA / "discovery_meta.json", {"last": today(), "added": added, "checked": len(cand_list)})
    log.info("discovery: %d new candidate publishers", len(added))
    return added


def _tranco_ir(known_set: set):
    try:
        r = requests.get("https://tranco-list.eu/top-1m.csv.zip", timeout=120)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        txt = z.read(z.namelist()[0]).decode()
    except Exception as e:  # noqa: BLE001
        log.warning("Tranco download failed: %s", e)
        return {}, {}
    out, known = {}, {}
    for line in txt.splitlines():
        try:
            rk, d = line.split(",", 1)
        except ValueError:
            continue
        d = d.strip().lower()
        dd = domain_of(d)
        if dd in known_set:
            known[dd] = int(rk)
        if d.endswith(".ir") or d.endswith(".com.ir"):
            out[domain_of(d)] = int(rk)
    log.info("Tranco: %d Iranian domains ranked, %d known publishers ranked", len(out), len(known))
    return out, known
