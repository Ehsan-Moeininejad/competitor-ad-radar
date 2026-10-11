"""Run storage with retention: raw data 3 days, daily summaries 31 days, registries pruned to 31 days."""
import logging
import shutil

from util import DATA, days_ago, read_json, settings, today, write_json

log = logging.getLogger("radar")


def save_run(run_id: str, pages: list, obs: list, meta: dict):
    slim = []
    for p in pages:
        q = {k: v for k, v in p.items() if k not in ("article_links",)}
        slim.append(q)
    write_json(DATA / "raw" / today() / f"{run_id}.json", {"run_id": run_id, "meta": meta, "pages": slim, "obs": obs})


def runs_for(date: str) -> list:
    d = DATA / "raw" / date
    if not d.exists():
        return []
    return [read_json(f, {}) for f in sorted(d.glob("*.json"))]


def last_run_time():
    m = read_json(DATA / "state.json", {}) or {}
    return m.get("last_scan_ts")


def set_state(**kw):
    m = read_json(DATA / "state.json", {}) or {}
    m.update(kw)
    write_json(DATA / "state.json", m)


def state():
    return read_json(DATA / "state.json", {}) or {}


def prune():
    ret = settings().get("retention", {})
    raw_from = days_ago(int(ret.get("raw_days", 3)) - 1)
    daily_from = days_ago(int(ret.get("daily_days", 31)))
    for base in ("raw", "shots"):
        root = DATA / base
        if root.exists():
            for d in root.iterdir():
                if d.is_dir() and d.name < raw_from:
                    shutil.rmtree(d, ignore_errors=True)
                    log.info("pruned %s/%s", base, d.name)
    daily = DATA / "daily"
    if daily.exists():
        for f in daily.glob("*.json"):
            if f.stem < daily_from:
                f.unlink()
    for name in ("creatives.json", "inventory.json", "pairs.json"):
        reg = read_json(DATA / name, {}) or {}
        reg2 = {k: v for k, v in reg.items() if (v.get("last_seen") or today()) >= daily_from}
        if len(reg2) != len(reg):
            write_json(DATA / name, reg2)
    adv = read_json(DATA / "advertisers.json", {}) or {}
    adv2 = {k: v for k, v in adv.items() if v.get("source") == "config" or (v.get("last_seen") or today()) >= days_ago(90)}
    if len(adv2) != len(adv):
        write_json(DATA / "advertisers.json", adv2)
