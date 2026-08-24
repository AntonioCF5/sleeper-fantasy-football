#!/usr/bin/env python3
"""Render the daily expert newsletter as a styled HTML email and send it.

Zero dependencies: a purpose-built converter for the newsletter's markdown
subset (h1-h3, bold, italic, links, tables, lists, hr) + smtplib over Gmail.

Credentials: the Gmail App Password lives in the macOS login Keychain, not
in any repo file. Store it yourself, in your own terminal:
    security add-generic-password -a "<gmail address>" \
      -s sleeper-newsletter-gmail -w
(prompts with echo off; get the app password first at
https://myaccount.google.com/apppasswords — requires 2-Step Verification).
Sender/recipient addresses are not secret and default to the user's own
address; override with data/secrets/email.json (gitignored):
    {"from": "you@gmail.com", "to": "you@gmail.com"}

Usage:
    python3 scripts/send_newsletter.py                # today's edition
    python3 scripts/send_newsletter.py 2026-08-22     # specific date
    python3 scripts/send_newsletter.py --html-only    # write HTML, no send
"""

import html
import json
import re
import smtplib
import ssl
import subprocess
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYCHAIN_SERVICE = "sleeper-newsletter-gmail"
DEFAULT_EMAIL = "antonio.contreras.fa@gmail.com"


def _keychain_password(account: str) -> str:
    """Fetch the Gmail app password from the macOS login Keychain.

    The password is never stored in a repo file — `security` decrypts it
    from the encrypted Keychain only for this lookup. Store it yourself
    (not via this script) with:
        security add-generic-password -a "<gmail address>" \\
          -s sleeper-newsletter-gmail -w
    which prompts for the password with terminal echo off.
    """
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", account,
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit(
            f"No Keychain entry for account={account!r} service={KEYCHAIN_SERVICE!r}.\n"
            "Store the Gmail App Password yourself, in your own terminal (not through me), with:\n\n"
            f'  security add-generic-password -a "{account}" -s {KEYCHAIN_SERVICE} -w\n\n'
            "It will prompt for the password with the terminal not echoing what you type.\n"
            "Get the app password first at https://myaccount.google.com/apppasswords\n"
            "(requires 2-Step Verification enabled).")

# ---------------------------------------------------------------- palette
INK = "#1a1f2e"
INK2 = "#4a5268"
ACCENT = "#1e6fd9"      # links
GOOD = "#0e7a3d"
BAD = "#b3261e"
BG = "#f4f5f7"
CARD = "#ffffff"
BORDER = "#e3e6ec"
HEAD_BG = "#0f2145"     # header band


def _inline(text: str) -> str:
    """Inline markdown -> HTML (escapes first, then restores markup)."""
    text = html.escape(text, quote=False)
    # links [label](url)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        rf'<a href="\2" style="color:{ACCENT};text-decoration:none;font-weight:600">\1</a>',
        text)
    # bold then italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _table(rows):
    head, sep, body = rows[0], rows[1], rows[2:]
    cells = [c.strip() for c in head.strip().strip("|").split("|")]
    out = [f'<table role="presentation" width="100%" style="border-collapse:collapse;'
           f'margin:14px 0;font-size:14px;background:{CARD}">', "<tr>"]
    for c in cells:
        out.append(f'<th align="left" style="padding:8px 10px;border-bottom:2px solid '
                   f'{HEAD_BG};color:{HEAD_BG};font-size:12px;text-transform:uppercase;'
                   f'letter-spacing:.4px">{_inline(c)}</th>')
    out.append("</tr>")
    for i, r in enumerate(body):
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        bg = CARD if i % 2 == 0 else "#f8f9fb"
        out.append(f'<tr style="background:{bg}">')
        for c in cells:
            out.append(f'<td style="padding:8px 10px;border-bottom:1px solid {BORDER};'
                       f'vertical-align:top;line-height:1.45">{_inline(c)}</td>')
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def md_to_email_html(md: str, edition_date: str) -> str:
    lines = md.splitlines()
    parts = []
    i, in_list, title, subtitle = 0, False, "Expert Daily", ""
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            # wrap tables for phone-width horizontal scroll
            parts.append('<div style="overflow-x:auto;-webkit-overflow-scrolling:touch">'
                         + _table(lines[i:j]) + "</div>")
            i = j
            continue
        if in_list and not line.lstrip().startswith(("- ", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            parts.append("</ul>")
            in_list = False
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            parts.append(f'<h2 style="margin:30px 0 10px;font-size:20px;color:{HEAD_BG};'
                         f'border-bottom:2px solid {BORDER};padding-bottom:6px">'
                         f"{_inline(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            parts.append(f'<h3 style="margin:20px 0 8px;font-size:16px;color:{INK}">'
                         f"{_inline(line[4:].strip())}</h3>")
        elif line.strip() == "---":
            parts.append(f'<hr style="border:none;border-top:1px solid {BORDER};margin:24px 0">')
        elif re.match(r"^\d+\. ", line.lstrip()) or line.lstrip().startswith("- "):
            if not in_list:
                parts.append('<ul style="margin:8px 0 14px;padding-left:22px">')
                in_list = True
            item = re.sub(r"^(\d+\.|-)\s+", "", line.lstrip())
            parts.append(f'<li style="margin:7px 0;line-height:1.55;font-size:14.5px">{_inline(item)}</li>')
        elif line.startswith("*") and line.endswith("*") and not line.startswith("**") and len(line) > 2:
            if not subtitle:
                subtitle = _inline(line.strip("*").strip())
            else:
                parts.append(f'<p style="margin:8px 0;color:{INK2};font-size:13px;'
                             f'font-style:italic;line-height:1.5">{_inline(line.strip("*").strip())}</p>')
        elif line.strip():
            parts.append(f'<p style="margin:10px 0;line-height:1.6;font-size:14.5px">{_inline(line)}</p>')
        i += 1
    if in_list:
        parts.append("</ul>")

    body = "".join(parts)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{INK}">
<table role="presentation" width="100%" style="background:{BG}"><tr><td align="center" style="padding:18px 8px">
<table role="presentation" width="100%" style="max-width:680px">
<tr><td style="background:{HEAD_BG};border-radius:12px 12px 0 0;padding:26px 28px">
  <div style="color:#8fb4f0;font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">🏈 Sleeper Expert System</div>
  <div style="color:#ffffff;font-size:24px;font-weight:800;line-height:1.25">{html.escape(title)}</div>
  <div style="color:#b8c6e4;font-size:13px;margin-top:8px">{subtitle}</div>
</td></tr>
<tr><td style="background:{CARD};border:1px solid {BORDER};border-top:none;border-radius:0 0 12px 12px;padding:10px 28px 26px">
{body}
</td></tr>
<tr><td style="padding:16px 10px;text-align:center;color:{INK2};font-size:12px;line-height:1.6">
Generated by your Sleeper expert pipeline · takes are visibility-only, no projections adjusted<br>
Full history in <span style="font-family:monospace">reports/2026/expert-daily/</span> · pair with the command center for live boards
</td></tr>
</table></td></tr></table></body></html>"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    html_only = "--html-only" in sys.argv
    day = args[0] if args else date.today().isoformat()
    season = day[:4]
    md_path = ROOT / "reports" / season / "expert-daily" / f"{day}.md"
    if not md_path.exists():
        sys.exit(f"no newsletter found at {md_path}")
    doc = md_to_email_html(md_path.read_text(), day)
    out = md_path.with_suffix(".html")
    out.write_text(doc)
    print(f"rendered {out.relative_to(ROOT)}")
    if html_only:
        return

    # From/to addresses are not secret — an optional data/secrets/email.json
    # may override them ({"from": "...", "to": "..."}), else both default
    # to the user's own address. The password never lives in a repo file.
    addr_path = ROOT / "data" / "secrets" / "email.json"
    addrs = json.loads(addr_path.read_text()) if addr_path.exists() else {}
    sender = addrs.get("from", DEFAULT_EMAIL)
    recipient = addrs.get("to", DEFAULT_EMAIL)
    app_password = _keychain_password(sender)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏈 Expert Daily — {day}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(md_path.read_text(), "plain"))
    msg.attach(MIMEText(doc, "html"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(sender, app_password)
        s.sendmail(sender, [recipient], msg.as_string())
    print(f"sent to {recipient}")


if __name__ == "__main__":
    main()
