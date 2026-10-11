"""Daily email via Gmail SMTP (App Password). Inline summary + full HTML report attached."""
import html
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from util import settings

log = logging.getLogger("radar")
F = "Vazirmatn,Tahoma,'Segoe UI',Arial,sans-serif"


def t(x):
    return html.escape(str(x or ""))


def send(D: dict, I: dict, report_path, page_url: str = ""):
    user, pwd = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = [x.strip() for x in os.environ["MAIL_TO"].replace(";", ",").split(",") if x.strip()]
    cfg = settings()
    rivals = [(b, c) for b, c in D["competitors"].items() if c["level"] != "own"][:6]
    top_sites = [(d, s) for d, s in D["sites"].items() if s["recommendation"] in ("خرید مستقیم", "بید پایین در شبکه", "شکاف حضور")][:6]
    td = f'style="padding:6px 8px;border-bottom:1px solid #2c2c2a;font-family:{F};font-size:13px;color:#f0efec;text-align:right"'
    th = f'style="padding:6px 8px;border-bottom:1px solid #383835;font-family:{F};font-size:12px;color:#c3c2b7;text-align:right"'

    def sec(title, inner):
        return (f'<tr><td style="padding:18px 0 6px"><div style="border-right:4px solid #ef4056;padding-right:10px;font-family:{F};'
                f'font-size:16px;font-weight:bold;color:#f0efec">{t(title)}</div></td></tr><tr><td>{inner}</td></tr>')
    bullets = "".join(f'<li style="margin:4px 0">{t(s)}</li>' for s in I.get("summary", []))
    alerts = "".join(f'<li style="margin:4px 0">{t(a["text"])}</li>' for a in D["alerts"][:6])
    comp_rows = "".join(f'<tr><td {td}>{t(b)}</td><td {td}>{round(c["sov"] * 100, 1)}%</td><td {td}>{len(c["sites"])}</td><td {td}>{c["threat"]}</td></tr>' for b, c in rivals)
    site_rows = "".join(f'<tr><td {td} dir="ltr">{t(d)}</td><td {td}>{s["opportunity"]}</td><td {td}>{s["pressure"]}</td><td {td}>{t(s["recommendation"])}</td></tr>' for d, s in top_sites)
    acts = "".join(f'<li style="margin:4px 0"><b>{t(a.get("action"))}</b> — {t(a.get("where"))}: {t(a.get("why"))}</li>' for a in I.get("actions", [])[:5])
    btn = (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0"><tr><td style="background:#ef4056;border-radius:8px">'
           f'<a href="{t(page_url)}" style="display:inline-block;padding:10px 20px;font-family:{F};font-size:14px;font-weight:bold;color:#fff;text-decoration:none">'
           f'مشاهدهٔ گزارش کامل</a></td></tr></table>') if page_url else ""
    body = f"""<!doctype html><html dir="rtl"><body style="margin:0;background:#0d0d0d">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d0d"><tr><td align="center" style="padding:20px 12px">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" dir="rtl" style="max-width:640px;width:100%;background:#1a1a19;border-radius:14px;padding:20px">
<tr><td style="font-family:{F};color:#ef4056;font-weight:bold;font-size:13px;text-align:right">{t(cfg['report']['brand'])}</td></tr>
<tr><td style="font-family:{F};color:#f0efec;font-size:20px;font-weight:bold;text-align:right;padding:4px 0">{t(cfg['report']['title'])} · {t(D['date'])}</td></tr>
<tr><td style="font-family:{F};color:#f0efec;font-size:15px;line-height:1.8;text-align:right;background:#2a1a1d;border-radius:10px;padding:12px">{t(I.get('headline'))}</td></tr>
<tr><td style="font-family:{F};color:#898781;font-size:12px;text-align:right;padding-top:8px">{len(D['sites'])} سایت · {D['n_obs']} تبلیغ · {D['runs']} اجرا · پوشش {D['coverage_pct']}%</td></tr>
{sec('جمع‌بندی', f'<ul dir="rtl" style="font-family:{F};font-size:13.5px;color:#f0efec;line-height:1.8;padding-right:18px;margin:0">{bullets}</ul>')}
{sec('هشدارها', f'<ul dir="rtl" style="font-family:{F};font-size:13.5px;color:#f0efec;line-height:1.8;padding-right:18px;margin:0">{alerts or "<li>—</li>"}</ul>')}
{sec('رقبای پرحضور', f'<table width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr><th {th}>برند</th><th {th}>SOV</th><th {th}>سایت</th><th {th}>تهدید</th></tr>{comp_rows}</table>') if comp_rows else ''}
{sec('فرصت‌های کم‌تراکم', f'<table width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr><th {th}>سایت</th><th {th}>فرصت</th><th {th}>فشار</th><th {th}>پیشنهاد</th></tr>{site_rows}</table>') if site_rows else ''}
{sec('اقدام‌ها', f'<ul dir="rtl" style="font-family:{F};font-size:13.5px;color:#f0efec;line-height:1.8;padding-right:18px;margin:0">{acts}</ul>') if acts else ''}
<tr><td align="right">{btn}<div style="font-family:{F};font-size:12px;color:#898781;text-align:right">گزارش کامل (همهٔ تب‌ها، گالری کریتیو و روند ماهانه) به این ایمیل پیوست شده است.</div></td></tr>
</table></td></tr></table></body></html>"""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"{cfg['email']['subject_prefix']} · {D['date']}" + (f" · {len([a for a in D['alerts'] if a['level'] == 'high'])} هشدار فوری" if any(a["level"] == "high" for a in D["alerts"]) else "")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("\n".join(I.get("summary", [])), "plain", "utf-8"))
    alt.attach(MIMEText(body, "html", "utf-8"))
    msg.attach(alt)
    if cfg["email"].get("attach_html", True) and report_path:
        data = open(report_path, "rb").read()
        # Gmail caps the ENCODED message at 25 MB (base64 adds ~37%)
        if len(data) * 1.37 + len(body) * 1.37 < 23_000_000:
            part = MIMEApplication(data, _subtype="html")
            part.add_header("Content-Disposition", "attachment", filename=f"ad-radar-{D['date']}.html")
            msg.attach(part)
        else:
            log.warning("report too large to attach (%.1f MB) — link only", len(data) / 1e6)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pwd)
        s.sendmail(user, to, msg.as_string())
    log.info("email sent to %d recipients", len(to))
