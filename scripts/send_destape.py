#!/usr/bin/env python3
"""Manda al user el kit del Destape por correo, listo para pasarlo a WhatsApp.

Cuerpo: el texto de la edición en texto plano (los *asteriscos* de WhatsApp
sobreviven). Adjuntos, en orden: las tarjetas 01..N, el PDF carrusel y el PDF
periódico de reports/<season>/roast/visual/<edición>/. En el iPhone: abrir el
correo → "Guardar N imágenes" → quedan en Fotos en orden (fecha EXIF
consecutiva) → en WhatsApp se tocan de la 1 a la N y se mandan como álbum.

Mismo mecanismo que send_newsletter.py: la contraseña de app vive SOLO en el
Llavero de macOS (servicio sleeper-newsletter-gmail); este script nunca la ve
escrita en ningún archivo.

Uso: python3 scripts/send_destape.py <edicion.txt> [--sin-imagenes]
"""
import json
import smtplib
import ssl
import sys
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import send_newsletter as sn  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    edicion = Path(args[0]).resolve()
    texto = edicion.read_text()
    jornada = texto.split("\n")[1].strip("_ ") if "\n" in texto else edicion.stem
    visual = ROOT / "reports" / edicion.stem[:4] / "roast" / "visual" / edicion.stem

    msg = MIMEMultipart()
    msg["Subject"] = f"💋 El Destape de Miroslava — {jornada}"
    addr_path = ROOT / "data" / "secrets" / "email.json"
    addrs = json.loads(addr_path.read_text()) if addr_path.exists() else {}
    msg["From"] = sender = addrs.get("from", sn.DEFAULT_EMAIL)
    msg["To"] = recipient = addrs.get("to", sn.DEFAULT_EMAIL)
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    adjuntos = []
    if "--sin-imagenes" not in sys.argv and visual.exists():
        for f in sorted(visual.glob("[0-9][0-9]-*.jpg")):
            part = MIMEImage(f.read_bytes(), _subtype="jpeg")
            part.add_header("Content-Disposition", "attachment", filename=f.name)
            msg.attach(part)
            adjuntos.append(f.name)
        for f in sorted(visual.glob("*.pdf")):
            part = MIMEApplication(f.read_bytes(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=f.name)
            msg.attach(part)
            adjuntos.append(f.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, sn._keychain_password(sender))
        s.sendmail(sender, [recipient], msg.as_string())
    print(f"enviado a {recipient}: texto + {len(adjuntos)} adjuntos")


if __name__ == "__main__":
    main()
