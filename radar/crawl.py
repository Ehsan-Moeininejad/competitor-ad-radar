"""
Headless crawl of publisher pages. Never clicks an ad.
For every site × session (mobile cold / desktop cold / mobile warm) it records:
  - ad slots (network, format, geometry, sticky/popup, creative text/image/landing link)
  - ad-network API payloads (landing URLs + titles of served ads)
  - which ad-tech loaded on the page (to tell "no ads" apart from "ads blocked for this IP")
  - unknown third-party hosts that behave like ad servers (new networks)
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import time
from pathlib import Path

from util import DATA, domain_of, load_yaml, root_domain, settings, today

log = logging.getLogger("radar")
DETECT_JS = (Path(__file__).parent / "detect.js").read_text(encoding="utf-8")
URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")
ADPATH_RE = re.compile(r"/(ads?|adserver|adserve|banner|banners|serve|creative|impression|imp|vast|vpaid|delivery|bid|rtb|click)(/|\?|\.|$)", re.I)
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".js", ".css", ".woff", ".woff2", ".ico", ".json")

MOBILE_UA = ("Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/131.0.0.0 Mobile Safari/537.36")
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")


def _match(host, lst):
    return any(host == d or host.endswith("." + d) for d in lst)


class Crawler:
    def __init__(self, run_id: str):
        s = settings()["crawl"]
        self.s = s
        self.run_id = run_id
        self.nets = load_yaml("ad_networks.yaml")
        self.net_hosts = {k: v.get("hosts", []) for k, v in self.nets["networks"].items()}
        self.all_net_hosts = [h for v in self.net_hosts.values() for h in v]
        self.not_ads = self.nets.get("not_ads", [])
        self.js_cfg = {"networks": {k: {"hosts": v.get("hosts", []), "selectors": v.get("selectors", [])}
                                    for k, v in self.nets["networks"].items()},
                       "labels": self.nets.get("labels", []), "notAds": self.not_ads,
                       "maxSlots": s.get("max_screens_per_page", 25) + 15}
        self.shot_dir = DATA / "shots" / today()
        self.shot_dir.mkdir(parents=True, exist_ok=True)

    def net_of(self, host):
        for k, hs in self.net_hosts.items():
            if _match(host, hs):
                return k
        return None

    # ------------------------------------------------------------------
    async def run(self, sites: list, warm_urls: list) -> dict:
        from playwright.async_api import async_playwright
        proxy = os.getenv("PROXY_URL", "").strip()
        launch = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
        if proxy:
            launch["proxy"] = {"server": proxy}
            log.info("using proxy for crawl")
        results = {"run_id": self.run_id, "started": time.time(), "pages": [], "proxy": bool(proxy), "skipped_sites": []}
        deadline = time.time() + float(self.s.get("max_minutes", 100)) * 60
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**launch)
            common = {"locale": "fa-IR", "timezone_id": "Asia/Tehran", "ignore_https_errors": True,
                      "extra_http_headers": {"Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"}}
            fx = os.getenv("RADAR_FIXTURES")
            ctxs = {}

            async def make_ctx(sess):
                nonlocal browser
                if not browser.is_connected():
                    browser = await pw.chromium.launch(**launch)
                if sess.startswith("mobile"):
                    c = await browser.new_context(user_agent=MOBILE_UA, viewport={"width": 390, "height": 844},
                                                  device_scale_factor=2, is_mobile=True, has_touch=True, **common)
                else:
                    c = await browser.new_context(user_agent=DESKTOP_UA, viewport={"width": 1366, "height": 900}, **common)
                await c.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
                # close pop-under / window.open tabs opened by ads so they don't pile up
                c.on("page", lambda pg: asyncio.ensure_future(_close_popup(pg)))
                if fx:  # offline test mode: serve pages from fixtures/<host>/<path>
                    await c.route("**/*", lambda route: _fixture(route, fx))
                ctxs[sess] = c
                return c

            for sess in self.s.get("sessions", ["mobile_cold"]):
                await make_ctx(sess)
            if "mobile_warm" in ctxs and warm_urls:
                try:
                    await asyncio.wait_for(self._warm(ctxs["mobile_warm"], warm_urls), timeout=300)
                except Exception as e:  # noqa: BLE001
                    log.warning("warm-up incomplete: %s", str(e)[:120])
            sem = asyncio.Semaphore(int(self.s.get("concurrency", 4)))
            per_page = int(self.s.get("page_timeout_sec", 35)) + 120

            async def safe_page(sess, site, url, kind):
                try:
                    return await asyncio.wait_for(self._page(ctxs[sess], sess, site, url, kind), timeout=per_page)
                except Exception as e:  # noqa: BLE001
                    msg = str(e).split("\n")[0][:160] or type(e).__name__
                    log.warning("page failed %s %s %s: %s", site["domain"], sess, kind, msg)
                    if "closed" in msg.lower() or "crash" in msg.lower():
                        try:
                            await make_ctx(sess)
                        except Exception as e2:  # noqa: BLE001
                            log.error("could not recreate context %s: %s", sess, e2)
                    return {"domain": site["domain"], "session": sess, "kind": kind, "url": url, "ok": False, "status": None,
                            "slots": [], "api_ads": [], "adtech": [], "unknown_ad_hosts": [], "error": msg}

            async def one_site(site):
                async with sem:
                    if time.time() > deadline:
                        results["skipped_sites"].append(site["domain"])
                        return
                    try:
                        for sess in list(ctxs):
                            urls = ["https://" + site["domain"] + "/"] + list(site.get("pages") or [])[:2]
                            home = await safe_page(sess, site, urls[0], "home")
                            results["pages"].append(home)
                            n_inner = int(self.s.get("inner_pages", 1))
                            inner = urls[1:]
                            if len(inner) < n_inner and home.get("article_links"):
                                inner += home["article_links"][: n_inner - len(inner)]
                            for u in inner[: max(n_inner, len(urls) - 1)]:
                                results["pages"].append(await safe_page(sess, site, u, "inner"))
                    except Exception as e:  # noqa: BLE001
                        log.error("site %s aborted: %s", site["domain"], e)
            await asyncio.gather(*[one_site(s) for s in sites], return_exceptions=True)
            if results["skipped_sites"]:
                log.warning("time budget reached — %d sites skipped this run", len(results["skipped_sites"]))
            if self.s.get("landing_pages", {}).get("enabled", True) and time.time() < deadline + 600:
                try:
                    ctx = ctxs.get("mobile_cold") or next(iter(ctxs.values()))
                    results["landings"] = await asyncio.wait_for(self._landings(ctx, results["pages"]), timeout=900)
                except Exception as e:  # noqa: BLE001
                    log.warning("landing analysis incomplete: %s", str(e)[:120])
            try:
                await browser.close()
            except Exception:  # noqa: BLE001
                pass
        results["finished"] = time.time()
        return results

    # ------------------------------------------------------------------
    async def _warm(self, ctx, urls):
        """Retargeting persona: browse competitor sites (and a product page) so their pixels tag this browser."""
        page = await ctx.new_page()
        for u in urls:
            try:
                await page.goto(u, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3500)
                link = await page.evaluate("""() => { const a=[...document.querySelectorAll('a[href]')].map(a=>a.href)
                    .find(h=>/\\/(product|p|dkp-|pd|item)[\\/-]/i.test(h) && h.startsWith(location.origin)); return a||null }""")
                if link:
                    await page.goto(link, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(4000)
                log.info("warm: %s%s", u, " + product" if link else "")
            except Exception as e:  # noqa: BLE001
                log.info("warm failed %s: %s", u, str(e)[:100])
        await page.close()

    # ------------------------------------------------------------------
    async def _page(self, ctx, sess, site, url, kind) -> dict:
        rec = {"domain": site["domain"], "session": sess, "kind": kind, "url": url, "ok": False, "status": None,
               "slots": [], "api_ads": [], "adtech": [], "unknown_ad_hosts": [], "error": None}
        page = None
        api_payloads, hosts, adlike = [], {}, set()
        site_root = root_domain(site["domain"])

        async def on_response(resp):
            try:
                h = domain_of(resp.url)
                if not h or root_domain(h) == site_root:
                    return
                hosts[h] = hosts.get(h, 0) + 1
                net = self.net_of(h)
                if not net and not _match(h, self.not_ads) and ADPATH_RE.search(resp.url.split("?")[0] + "?"):
                    adlike.add(h)
                if net and resp.request.resource_type in ("xhr", "fetch") and len(api_payloads) < 30:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct or "javascript" in ct or "text" in ct:
                        body = await resp.body()
                        if len(body) < 600_000:
                            api_payloads.append((net, resp.url, body.decode("utf-8", "ignore")))
            except Exception:  # noqa: BLE001
                pass
        try:
            page = await ctx.new_page()
            page.on("response", on_response)
            resp = await page.goto(url, timeout=int(self.s.get("page_timeout_sec", 35)) * 1000, wait_until="domcontentloaded")
            rec["status"] = resp.status if resp else None
            await page.wait_for_timeout(2500)
            # scroll the whole page in viewport-sized hops so lazy ad slots (Yektanet/Mediaad) actually load
            ph = await page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            vh = 844 if sess.startswith("mobile") else 900
            steps = max(int(self.s.get("scroll_steps", 6)), min(28, int(ph / (vh * 1.6)) + 1))
            for i in range(steps):
                await page.evaluate(f"window.scrollTo(0, {int((i + 1) * ph / steps)})")
                await page.wait_for_timeout(450)
            await page.evaluate("window.scrollTo(0,0)")
            await page.wait_for_timeout(int(self.s.get("settle_sec", 6)) * 1000)
            out = await asyncio.wait_for(page.evaluate(DETECT_JS, self.js_cfg), timeout=40)
            rec["ok"] = (rec["status"] or 200) < 400
            pg = out["page"]
            rec.update({"title": pg["title"], "vw": pg["vw"], "vh": pg["vh"], "page_h": pg["pageH"],
                        "reportage": pg["reportage"], "push_prompt": pg["pushPrompt"],
                        "article_links": pg["articleLinks"], "ext_domains": pg.get("extDomains", [])})
            if re.search(r"access denied|403 forbidden|cloudflare|attention required|دسترسی.*(محدود|غیرمجاز)", pg["title"], re.I):
                rec["ok"], rec["error"] = False, "blocked: " + pg["title"][:80]
            await self._frame_creatives(page, out["slots"])
            shots, cap = 0, int(self.s.get("max_screens_per_page", 25))
            # floating ads first (each isolated from other overlays), then hide every overlay for in-page shots
            ordered = sorted(out["slots"], key=lambda x: not x.get("fixed"))
            hidden = False
            for sl in ordered:
                if not sl.get("fixed") and not hidden:
                    await page.evaluate(HIDE_FIXED_JS)
                    hidden = True
                if not sl.get("empty") and self.s.get("screenshots", True) and shots < cap:
                    if sl.get("fixed"):
                        await page.evaluate(ISOLATE_JS, sl["id"])
                    crs = [c for c in sl.get("creatives", []) if c.get("cr")]
                    if crs:   # native widget → one screenshot per recommended item
                        for c in crs[:6]:
                            c["shot"] = await self._shot(page, c["cr"], attr="data-radar-cr")
                            shots += c["shot"] is not None
                    sl["shot"] = await self._shot(page, sl["id"])
                    shots += sl["shot"] is not None
                    if sl.get("fixed"):
                        await page.evaluate(UNISOLATE_JS)
                rec["slots"].append(sl)
        except Exception as e:  # noqa: BLE001
            rec["error"] = str(e).split("\n")[0][:200]
        finally:
            if page:
                await _close_quietly(page)
        rec["adtech"] = sorted({self.net_of(h) for h in hosts if self.net_of(h)})
        rec["unknown_ad_hosts"] = sorted(h for h in adlike if not self.net_of(h))[:15]
        rec["api_ads"] = self._parse_api(api_payloads)
        log.info("%-22s %-12s %-5s %s slots=%d api=%d tech=%s%s", site["domain"], sess, kind, rec["status"],
                 len([s for s in rec["slots"] if not s.get("empty")]), len(rec["api_ads"]), ",".join(rec["adtech"]) or "-",
                 f" ERR {rec['error']}" if rec["error"] else "")
        return rec

    async def _frame_creatives(self, page, slots):
        """Ad iframes hide the landing link from the parent page; read it from inside the frame (no click)."""
        want = {u: sl for sl in slots for u in sl.get("iframes", [])}
        if not want:
            return
        for fr in page.frames[1:40]:
            sl = want.get(fr.url) or next((s for u, s in want.items() if u and fr.url.startswith(u.split("?")[0])), None)
            if not sl:
                continue
            try:
                info = await asyncio.wait_for(fr.evaluate("""() => { const a=[...document.querySelectorAll('a[href]')].find(a=>/^http/.test(a.href));
                    const img=document.querySelector('img'); return {href:a?a.href:'', img:img?(img.currentSrc||img.src):'',
                    title:((a&&(a.getAttribute('aria-label')||a.innerText))||img?.alt||document.body.innerText||'').replace(/\\s+/g,' ').trim().slice(0,200)} }"""), timeout=8)
            except Exception:  # noqa: BLE001
                continue
            if info.get("href") or info.get("title"):
                crs = sl.get("creatives") or []
                if crs and not crs[0].get("href"):
                    crs[0].update({k: v for k, v in info.items() if v and not crs[0].get(k)})
                else:
                    crs.insert(0, {"title": info.get("title", ""), "img": info.get("img", ""), "href": info.get("href", ""), "cta": "", "price": "", "discount": ""})
                sl["creatives"] = crs

    async def _shot(self, page, rid, attr="data-radar-id"):
        """Screenshot exactly the creative: native item → the item card; banner/iframe slot → the union of its media
        (containers are often full-width with the real banner in the middle)."""
        try:
            loc = page.locator(f'[{attr}="{rid}"]').first
            await loc.scroll_into_view_if_needed(timeout=3000)
            await page.wait_for_timeout(250)
            box = await page.evaluate(CLIP_JS, [attr, rid])
            if not box or box["w"] < 30 or box["h"] < 20:
                return None
            vp = page.viewport_size or {"width": 1366, "height": 900}
            inside = box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["w"] <= vp["width"] + 1 and box["y"] + box["h"] <= vp["height"] + 1
            if inside:
                png = await page.screenshot(clip={"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]}, type="png", timeout=5000)
            else:   # creative overflows the viewport → let Playwright screenshot the media element itself
                target = page.locator('[data-radar-shotel="1"]')
                png = await (target.first if await target.count() else loc).screenshot(timeout=5000, type="png")
            return _save_thumb(png, self.shot_dir)
        except Exception:  # noqa: BLE001
            return None

    def _parse_api(self, payloads):
        """Pull landing URLs and ad titles out of ad-network JSON responses."""
        ads, seen = [], set()
        for net, url, text in payloads:
            vals = []
            try:
                _walk(json.loads(text), vals)
            except json.JSONDecodeError:
                vals = [("", u) for u in URL_RE.findall(text.replace("\\/", "/"))]
            title_buf = ""
            for k, v in vals:
                kl = (k or "").lower()
                if isinstance(v, str) and v.startswith("http"):
                    h = domain_of(v)
                    low = v.lower().split("?")[0]
                    if not h or _match(h, self.all_net_hosts) or _match(h, self.not_ads) or low.endswith(IMG_EXT):
                        continue
                    if any(x in kl for x in ("icon", "image", "img", "logo", "pixel", "track", "impression", "video", "thumb")):
                        continue
                    key = (net, v.split("#")[0])
                    if key in seen:
                        continue
                    seen.add(key)
                    ads.append({"network": net, "landing": v[:600], "title": title_buf[:200]})
                    title_buf = ""
                elif isinstance(v, str) and kl in ("title", "text", "headline", "description", "name", "body", "subtitle") and 5 < len(v) < 220:
                    title_buf = v
        return ads[:40]

    # ------------------------------------------------------------------
    async def _landings(self, ctx, pages):
        """Open landing pages DIRECTLY (not through the ad click), tracking params stripped."""
        from util import strip_tracking, unwrap_redirect
        cfg = self.s.get("landing_pages", {})
        params = self.nets.get("tracking_params", [])
        cache_path = DATA / "landing_cache.json"
        from util import read_json, write_json
        cache = read_json(cache_path, {}) or {}
        todo = []
        for p in pages:
            links = [c.get("href") for s in p["slots"] for c in s.get("creatives", []) if c.get("href")] + \
                    [a["landing"] for a in p.get("api_ads", [])]
            for l in links:
                real = unwrap_redirect(l)
                h = domain_of(real)
                if not h or _match(h, self.all_net_hosts) or root_domain(h) == root_domain(p["domain"]):
                    continue
                clean = strip_tracking(real, params) if cfg.get("strip_tracking", True) else real
                if clean not in cache and clean not in todo:
                    todo.append(clean)
        todo = todo[: int(cfg.get("max_per_run", 45))]
        page = await ctx.new_page()
        for u in todo:
            info = {"url": u, "seen": today()}
            try:
                r = await page.goto(u, timeout=25000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                info.update(await page.evaluate(LANDING_JS))
                info["status"] = r.status if r else None
                info["final_domain"] = domain_of(page.url)
            except Exception as e:  # noqa: BLE001
                info["error"] = str(e).split("\n")[0][:150]
            cache[u] = info
        await page.close()
        # keep cache small: drop entries older than retention
        from util import days_ago
        keep_from = days_ago(int(settings().get("retention", {}).get("daily_days", 31)))
        cache = {k: v for k, v in cache.items() if v.get("seen", "") >= keep_from}
        write_json(cache_path, cache)
        log.info("landing pages analysed: %d new (cache %d)", len(todo), len(cache))
        return todo


CLIP_JS = """([attr, id]) => { document.querySelectorAll('[data-radar-shotel]').forEach(e => e.removeAttribute('data-radar-shotel'));
  const el = document.querySelector('[' + attr + '="' + id + '"]'); if (!el) return null;
  const r0 = el.getBoundingClientRect(); if (attr === 'data-radar-cr') return {x: r0.left, y: r0.top, w: r0.width, h: r0.height};
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  let big = null, area = 0;
  (el.matches('iframe,img,video,canvas') ? [el] : [...el.querySelectorAll('iframe,img,video,canvas')]).forEach(c => { const q = c.getBoundingClientRect();
    if (q.width * q.height > 600) { x1 = Math.min(x1, q.left); y1 = Math.min(y1, q.top); x2 = Math.max(x2, q.right); y2 = Math.max(y2, q.bottom);
      if (q.width * q.height > area) { area = q.width * q.height; big = c; } } });
  (big || el).setAttribute('data-radar-shotel', '1');
  if (!isFinite(x1)) return {x: r0.left, y: r0.top, w: r0.width, h: r0.height};
  return {x: x1, y: y1, w: x2 - x1, h: y2 - y1}; }"""
ISOLATE_JS = """(id) => { const t = document.querySelector('[data-radar-id="' + id + '"]');
  for (const el of document.querySelectorAll('body *')) { const s = getComputedStyle(el);
    if ((s.position === 'fixed' || s.position === 'sticky') && t && !el.contains(t) && !t.contains(el)) { el.setAttribute('data-radar-hid', '1'); el.style.setProperty('visibility', 'hidden', 'important'); } } }"""
UNISOLATE_JS = """() => { for (const el of document.querySelectorAll('[data-radar-hid]')) { el.style.removeProperty('visibility'); el.removeAttribute('data-radar-hid'); } }"""
HIDE_FIXED_JS = """() => { for (const el of document.querySelectorAll('body *')) { const s = getComputedStyle(el);
  if (s.position === 'fixed' || (s.position === 'sticky' && parseInt(s.zIndex) > 10)) el.style.setProperty('visibility', 'hidden', 'important'); } }"""


LANDING_JS = r"""() => {
  const t = (document.body.innerText || '').replace(/\s+/g, ' ');
  const pick = (re) => (t.match(re) || [''])[0];
  const meta = (n) => (document.querySelector(`meta[property="${n}"],meta[name="${n}"]`) || {}).content || '';
  const path = location.pathname;
  let type = 'other';
  if (/\/(product|p|dkp-|item|pd)[\/-]/i.test(path) || document.querySelector('[itemtype*="Product"],script[type="application/ld+json"]')?.textContent?.includes('"Product"')) type = 'product';
  else if (/\/(category|cat|search|list|c|brand)[\/-]/i.test(path)) type = 'category';
  else if (/\/(landing|campaign|lp|event|promo|offer|festival|sale)/i.test(path) || /جشنواره|کمپین|حراج|بلک.?فرایدی|یلدا|نوروز/.test(document.title)) type = 'campaign';
  else if (/play\.google|apps\.apple|cafebazaar|myket|sibapp|\.apk/.test(location.href) || /دانلود اپ|نصب اپلیکیشن/.test(t.slice(0, 3000))) type = 'app';
  else if (path === '/' || path === '') type = 'home';
  if (document.querySelector('form input[type="tel"], form input[name*="phone"], form input[name*="mobile"]')) type = type === 'other' ? 'lead_form' : type;
  return {
    title: document.title.slice(0, 160),
    og_title: meta('og:title').slice(0, 160),
    description: meta('description').slice(0, 240),
    type,
    price: pick(/[\d۰-۹٬,]{4,}\s*(تومان|ریال)/),
    discount: pick(/[\d۰-۹]{1,2}\s*[%٪]\s*(تخفیف)?/),
    installment: /اقساط|قسطی|اسنپ ?پی|بدون پیش ?پرداخت|خرید اعتباری|BNPL|دیجی ?پی/i.test(t),
    free_shipping: /ارسال رایگان/.test(t),
    countdown: !!document.querySelector('[class*="countdown"],[class*="timer"]') || /\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2}/.test(t.slice(0, 4000)),
    voucher: pick(/(کد تخفیف|کد هدیه)\s*[:：]?\s*[A-Za-z0-9\-]{3,20}/),
    gamified: /گردونه|قرعه.?کشی|جایزه|شانس/.test(t.slice(0, 6000)),
    months: (t.match(/([\d۰-۹]{1,2})\s*(ماهه|ماه|قسط)/) || [])[1] || '',
    no_prepay: /بدون\s*پیش.?پرداخت/.test(t),
    min_buy: (t.match(/(از|حداقل)\s*[\d۰-۹٬,]{3,}\s*(هزار)?\s*(تومان|ریال)/) || [''])[0],
    lead_form: !!document.querySelector('form input[type="tel"], form input[name*="phone"], form input[name*="mobile"]'),
    h1: (document.querySelector('h1')?.innerText || '').trim().slice(0, 140),
  };
}"""


async def _close_popup(pg):
    try:
        if await pg.opener():
            await pg.close()
    except Exception:  # noqa: BLE001
        pass


async def _close_quietly(pg):
    try:
        await pg.close()
    except Exception:  # noqa: BLE001
        pass


async def _fixture(route, fx):
    from urllib.parse import urlparse
    u = urlparse(route.request.url)
    host = (u.hostname or "").removeprefix("www.")
    path = u.path if u.path not in ("", "/") else "/index.html"
    f = Path(fx) / host / path.lstrip("/")
    if f.is_dir():
        f = f / "index.html"
    if f.exists():
        ct = "application/json" if f.suffix == ".json" else "image/png" if f.suffix == ".png" else "text/html; charset=utf-8"
        await route.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ct, "access-control-allow-origin": "*"})
    else:
        await route.fulfill(status=404, body=b"")


def _walk(o, out, key=""):
    if isinstance(o, dict):
        for k, v in o.items():
            _walk(v, out, k)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out, key)
    elif isinstance(o, str):
        out.append((key, o))


def _save_thumb(png: bytes, folder: Path):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width < 30 or im.height < 20:
        return None
    small = im.resize((12, 12)).convert("L")
    h = hashlib.md5(small.tobytes()).hexdigest()[:14]   # near-duplicate creatives share a hash
    path = folder / f"{h}.jpg"
    if not path.exists():
        im.thumbnail((420, 420))
        im.save(path, "JPEG", quality=62, optimize=True)
    return f"{folder.name}/{h}.jpg"
