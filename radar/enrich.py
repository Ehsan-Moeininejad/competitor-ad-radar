"""Advertiser identification & competitor classification (rules first, free LLM second, vision for image-only ads)."""
import logging

from llm import b64_file
from util import DATA, read_json, sha, today, write_json

log = logging.getLogger("radar")
ADV = DATA / "advertisers.json"
from util import load_yaml as _ly
VERT_KEYS = list(_ly("competitors.yaml").get("verticals", {}).keys()) or ["other"]


def adv_key(o):
    if o.get("adv_domain"):
        return o["adv_domain"]
    if o.get("brand"):
        return "brand:" + o["brand"]
    if o.get("adv_hint"):
        return o["adv_hint"]
    if o.get("title"):
        return "t:" + sha(o["title"][:60], 10)
    if o.get("shot"):
        return "img:" + o["shot"].split("/")[-1][:14]
    return ""


def enrich(obs: list, brands, llm, max_llm_batches: int = 3, max_vision: int = 12) -> dict:
    reg = read_json(ADV, {}) or {}
    # 1) seed from config (config always wins)
    for b in brands.brands:
        for d in b.get("domains") or []:
            reg[d] = {**reg.get(d, {}), "name": b["name"], "vertical": b["vertical"], "level": b["level"], "source": "config"}
    # 2) collect unknowns
    unknown = {}
    for o in obs:
        k = adv_key(o)
        if not k:
            continue
        o["adv"] = k
        e = reg.get(k)
        if e:
            e["last_seen"] = today()
            continue
        u = unknown.setdefault(k, {"key": k, "titles": set(), "landing_titles": set(), "shot": None, "brand_hint": o.get("brand")})
        if o.get("title"):
            u["titles"].add(o["title"][:90])
        if o.get("landing_title"):
            u["landing_titles"].add(o["landing_title"][:90])
        if o.get("shot") and not u["shot"]:
            u["shot"] = o["shot"]
    # brand-hit by text → no LLM needed
    for k, u in list(unknown.items()):
        if u["brand_hint"]:
            b = next((b for b in brands.brands if b["name"] == u["brand_hint"]), None)
            if b:
                reg[k] = {"name": b["name"], "vertical": b["vertical"], "level": b["level"], "source": "name-match",
                          "first_seen": today(), "last_seen": today()}
                unknown.pop(k)
    # 3) LLM text classification in batches
    items = [u for u in unknown.values() if u["titles"] or u["landing_titles"] or not u["key"].startswith(("t:", "img:"))]
    if llm and llm.available and items:
        for i in range(0, min(len(items), 40 * max_llm_batches), 40):
            batch = items[i:i + 40]
            lines = [f'{j}. key={u["key"]} | ad texts: {" / ".join(list(u["titles"])[:3])} | landing: {" / ".join(list(u["landing_titles"])[:2])}'
                     for j, u in enumerate(batch)]
            try:
                out = llm.json(
                    "You are an Iranian digital-advertising analyst working for Digikala (Iran's largest e-commerce marketplace). "
                    "Identify each ADVERTISER from its domain/ad text and classify it.\n"
                    f"vertical must be one of: {', '.join(VERT_KEYS)}.\n"
                    "level: 'own' = Digikala group (Digikala, Digistyle, Digipay, Digikala Jet, Fidibo, DigiAd); 'core' = direct general "
                    "e-commerce competitor (marketplaces, multi-category online shops); 'vertical' = sells online in one "
                    "category that Digikala also sells (mobile shops, gold apps, BNPL/fintech, grocery delivery, fashion, beauty, "
                    "appliances, books); 'none' = not a competitor (telecom, crypto exchange, education, services, news...).",
                    "Return {\"items\":[{\"key\":...,\"brand_fa\":\"Persian brand name\",\"brand_en\":...,\"vertical\":...,"
                    "\"level\":\"own|core|vertical|none\",\"confidence\":0-1}]}\n" + "\n".join(lines), max_tokens=3500)
                for it in (out.get("items") if isinstance(out.get("items"), list) else []):
                    if not isinstance(it, dict):
                        continue
                    k = it.get("key")
                    if k in unknown:
                        reg[k] = {"name": it.get("brand_fa") or it.get("brand_en") or k, "name_en": it.get("brand_en", ""),
                                  "vertical": it.get("vertical") if it.get("vertical") in VERT_KEYS else "other",
                                  "level": it.get("level") if it.get("level") in ("own", "core", "vertical", "none") else "none",
                                  "confidence": it.get("confidence"), "source": "llm", "first_seen": today(), "last_seen": today()}
            except Exception as e:  # noqa: BLE001
                log.warning("advertiser classification batch failed: %s", e)
    # 4) vision for image-only creatives still unknown
    vis = [u for u in unknown.values() if u["key"] not in reg and u["shot"]][:max_vision]
    for u in vis:
        if not (llm and llm.available):
            break
        try:
            out = llm.json(
                "You look at a screenshot of an online ad shown on an Iranian website. Identify the advertiser brand and what it promotes.",
                "Return {\"brand_fa\":...,\"brand_en\":...,\"domain_guess\":...,\"vertical\":one of " + "|".join(VERT_KEYS)
                + ",\"level\":\"own|core|vertical|none\" (relative to Digikala e-commerce),\"message_fa\":\"one-line Persian summary of the offer\","
                "\"confidence\":0-1}. If unreadable, brand_fa=\"نامشخص\".",
                max_tokens=600, image_b64=b64_file(DATA / "shots" / u["shot"]))
            if out.get("brand_fa") and out.get("brand_fa") not in ("نامشخص", "ناشناخته", "unknown"):
                reg[u["key"]] = {"name": str(out["brand_fa"])[:60], "name_en": out.get("brand_en", ""),
                                 "vertical": out.get("vertical") if out.get("vertical") in VERT_KEYS else "other",
                                 "level": out.get("level") if out.get("level") in ("own", "core", "vertical", "none") else "none", "message": out.get("message_fa", ""), "domain_guess": out.get("domain_guess", ""),
                                 "confidence": out.get("confidence"), "source": "vision", "first_seen": today(), "last_seen": today()}
        except Exception as e:  # noqa: BLE001
            log.info("vision failed: %s", str(e)[:120])
    # 5) fallback for whatever is left
    for k, u in unknown.items():
        if k not in reg:
            reg[k] = {"name": k if not k.startswith(("t:", "img:")) else "نامشخص", "vertical": "other", "level": "unknown",
                      "source": "none", "first_seen": today(), "last_seen": today(), "sample": next(iter(u["titles"]), "")}
    # unidentified entries are retried on the next run (they're cheap to re-ask), identified ones are kept
    write_json(ADV, {k: v for k, v in reg.items() if v.get("source") != "none"})
    # 6) stamp observations
    for o in obs:
        e = reg.get(o.get("adv", ""), {})
        o["brand"] = e.get("name") or o.get("brand") or "نامشخص"
        if o["brand"] in ("نامشخص", "ناشناخته", "unknown") or o["brand"].startswith(("t:", "img:")):
            o["brand"], e = "نامشخص", {}
            o["level"] = "unknown"
        o["level"] = e.get("level") or o.get("level") or "unknown"
        o["vertical"] = e.get("vertical") or o.get("vertical") or "other"
        if o.get("category") in (None, "", "other"):
            o["category"] = o["vertical"]
    return reg
