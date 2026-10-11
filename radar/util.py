"""Shared helpers: config, paths, json io, time, url normalisation."""
import datetime as dt
import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, unquote

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

log = logging.getLogger("radar")

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Tehran")
except Exception:  # noqa: BLE001
    TZ = dt.timezone(dt.timedelta(hours=3, minutes=30))

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return load_yaml("settings.yaml")


def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def today() -> str:
    return now().strftime("%Y-%m-%d")


def read_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    tmp.replace(path)


def sha(s: str, n: int = 12) -> str:
    return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()[:n]


def domain_of(url: str) -> str:
    try:
        h = urlparse(url if "://" in url else "https://" + url).hostname or ""
    except ValueError:
        return ""
    return h.lower().removeprefix("www.").removeprefix("m.")


def root_domain(host: str) -> str:
    """digikala.com from www.digikala.com, but keep 'snapp.market', 'milli.gold' as they are."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in ("co", "ac", "org", "gov", "com", "net") and parts[-1] == "ir":
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def unwrap_redirect(url: str) -> str:
    """Click trackers often carry the real landing in a query param (url=, u=, dest=, redirect=...)."""
    for _ in range(3):
        try:
            p = urlparse(url)
        except ValueError:
            return url
        nxt = None
        for k, v in parse_qsl(p.query, keep_blank_values=False):
            if k.lower() in ("url", "u", "dest", "destination", "redirect", "redirect_url", "target", "to", "link", "r", "lp", "landing", "adurl", "ad_url", "clickurl", "click_url", "q"):
                v = unquote(v)
                if v.startswith("http"):
                    nxt = v
                    break
        if not nxt:
            return url
        url = nxt
    return url


def strip_tracking(url: str, params: list) -> str:
    try:
        p = urlparse(url)
    except ValueError:
        return url
    keep = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in params and not k.lower().startswith("utm_")]
    return urlunparse(p._replace(query=urlencode(keep), fragment=""))


def utm_of(url: str) -> dict:
    try:
        q = dict(parse_qsl(urlparse(url).query))
    except ValueError:
        return {}
    out = {}
    for k, v in q.items():
        kl = k.lower()
        if kl.startswith("utm_") or kl.startswith("mtm_"):
            out[kl.replace("mtm_", "utm_").replace("utm_kwd", "utm_term")] = v[:120]
    return out


def norm_text(s: str) -> str:
    s = (s or "").translate(FA_DIGITS)
    s = s.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return re.sub(r"\s+", " ", s).strip()


def days_ago(n: int) -> str:
    return (now() - dt.timedelta(days=n)).strftime("%Y-%m-%d")
