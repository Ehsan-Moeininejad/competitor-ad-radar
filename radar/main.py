"""
Entry point.
  python radar/main.py            → auto: scan (if the last scan is old enough), then report if it's the evening run
  python radar/main.py scan       → scan only
  python radar/main.py report     → build today's report (and email) from today's scans
Env: FORCE_REPORT=true to build/email the report now; FORCE_SCAN=true to ignore the min-gap guard.
"""
import asyncio
import collections
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import classify  # noqa: E402
import crawl  # noqa: E402
import enrich  # noqa: E402
import insights  # noqa: E402
import metrics  # noqa: E402
import publishers  # noqa: E402
import report  # noqa: E402
import store  # noqa: E402
from llm import LLM  # noqa: E402
from util import DATA, domain_of, load_yaml, now, read_json, settings, setup_logging, today, write_json  # noqa: E402

log = logging.getLogger("radar")
truthy = lambda v: str(v or "").lower() in ("1", "true", "yes", "on")


def warm_urls(brands) -> list:
    cfg = brands.auto
    levels = set(cfg.get("warm_from_levels", ["core", "vertical"]))
    urls = [f"https://{b['domains'][0]}/" for b in brands.brands if b.get("level") in levels and b.get("domains")]
    return urls[: int(cfg.get("warm_max_sites", 8))]


def scan(llm):
    t0 = time.time()
    run_id = now().strftime("%H%M")
    rows = publishers.read_sheet()
    reg = publishers.sync_registry(rows)
    sites = publishers.select_for_run(reg)
    if not sites:
        log.error("no publishers to scan")
        return
    brands = classify.Brands()
    nets = load_yaml("ad_networks.yaml")
    cr = crawl.Crawler(run_id)
    res = asyncio.run(cr.run(sites, warm_urls(brands)))
    landings = read_json(DATA / "landing_cache.json", {}) or {}
    obs = classify.observations(res["pages"], brands, nets.get("tracking_params", []), run_id, landings)
    enrich.enrich(obs, brands, llm)
    meta = {"sites": len(sites), "pages": len(res["pages"]), "obs": len(obs), "secs": round(time.time() - t0),
            "proxy": res.get("proxy"), "llm": llm.summary}
    store.save_run(run_id, res["pages"], obs, meta)
    per = collections.defaultdict(lambda: {"ok": False, "ads": 0})
    for p in res["pages"]:
        per[p["domain"]]["ok"] |= bool(p.get("ok"))
    for o in obs:
        per[o["domain"]]["ads"] += 1
    publishers.update_after_scan(reg, dict(per))
    # links between publishers feed weekly discovery
    ext = read_json(DATA / "ext_domains.json", {}) or {}
    for p in res["pages"]:
        for d in p.get("ext_domains", []):
            d = domain_of(d)
            ext.setdefault(d, [])
            if p["domain"] not in ext[d]:
                ext[d].append(p["domain"])
    write_json(DATA / "ext_domains.json", ext)
    store.set_state(last_scan_ts=t0, last_scan=now().isoformat(timespec="minutes"),
                    skipped_sites=res.get("skipped_sites", []))
    log.info("scan done: %s", meta)


def build_report(llm, send_mail=True):
    runs = store.runs_for(today())
    if not runs:
        log.warning("no scans today — report skipped")
        return
    reg = publishers.load_registry()
    ext = read_json(DATA / "ext_domains.json", {}) or {}
    try:
        added = publishers.discover(reg, llm, {d: len(v) for d, v in ext.items()})
        if added is not None:  # discovery ran this week → start collecting afresh
            write_json(DATA / "ext_domains.json", {})
    except Exception as e:  # noqa: BLE001
        log.warning("publisher discovery failed: %s", e)
    adv = read_json(DATA / "advertisers.json", {}) or {}
    D = metrics.build(runs, publishers.load_registry(), adv)
    metrics.save_daily(D)
    M = metrics.monthly()
    I = insights.write(D, M, llm)
    used = sorted({r.get("meta", {}).get("llm", "") for r in runs} | {llm.summary})
    html = report.build(D, M, I, publishers.load_registry(), " | ".join(u for u in used if u), load_yaml("ad_networks.yaml"))
    path = report.write(html, D["date"])
    log.info("report written: %s (%.1f MB)", path, path.stat().st_size / 1e6)
    page = os.getenv("PAGE_URL", "").strip()
    if not page and os.getenv("GITHUB_REPOSITORY") and truthy(os.getenv("PUBLISH_PAGES", "true")):
        o, r = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        page = f"https://{o.lower()}.github.io/{r}/"
    st = store.state()
    if send_mail and os.getenv("SMTP_USER") and os.getenv("MAIL_TO"):
        if st.get("last_email") == today() and not truthy(os.getenv("FORCE_REPORT")):
            log.info("email already sent today")
        else:
            try:
                import notify
                notify.send(D, I, path, page)
                store.set_state(last_email=today())
            except Exception as e:  # noqa: BLE001
                log.error("email failed: %s", e)
    else:
        log.info("SMTP not configured — email skipped")
    store.set_state(last_report=now().isoformat(timespec="minutes"))


def main():
    setup_logging()
    mode = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("MODE", "auto")).lower()
    cfg = settings()
    llm = LLM()
    try:
        if mode in ("auto", "scan"):
            last = store.last_run_time()
            gap = int(cfg["schedule"].get("min_gap_minutes", 90)) * 60
            if last and time.time() - last < gap and not truthy(os.getenv("FORCE_SCAN")):
                log.info("last scan started %.0f min ago — skipping duplicate scan", (time.time() - last) / 60)
            else:
                try:
                    scan(llm)
                except Exception:  # noqa: BLE001
                    log.exception("scan failed — continuing with what is already stored")
        evening = now().hour >= int(cfg["schedule"].get("report_after_hour", 19))
        if mode == "report" or (mode == "auto" and (evening or truthy(os.getenv("FORCE_REPORT")))):
            st = store.state()
            already = (st.get("last_report_date") == today() and (st.get("last_report_ts") or 0) > (st.get("last_scan_ts") or 0))
            if already and mode == "auto" and not truthy(os.getenv("FORCE_REPORT")):
                log.info("today's report is already up to date — skipped")
            else:
                try:
                    build_report(llm)
                    store.set_state(last_report_date=today(), last_report_ts=time.time())
                except Exception:  # noqa: BLE001
                    log.exception("report failed")
    finally:
        store.prune()


if __name__ == "__main__":
    main()
