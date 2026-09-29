#!/usr/bin/env python3
"""EL DESTAPE en formato visual: carrusel de tarjetas + PDF membretado.

Lee la edición APROBADA en texto de WhatsApp (el mismo .txt que pasa por
roast_lint y el editor) y la convierte, sin reescribir una sola palabra, en:

  1. Un CARRUSEL de tarjetas 1080 de ancho (mín. 1350 de alto, 4:5) — portada
     con Miroslava + una tarjeta por sección; el ranking se parte en varias
     para que la letra se lea en un teléfono. Es lo que se manda al grupo.
  2. Un PDF MEMBRETADO (carta, papel blanco, franja #013369 con el escudo en
     cada página) con la edición completa, para archivo o para quien la quiera
     leer de corrido.

Motor: HTML + CSS renderizado con Chrome headless (emoji a color, tipografía
real y ajuste de línea automático — lo que SVG+sips no hace). Chrome corre
con un perfil temporal propio, nunca con el del user.

Uso: python3 scripts/destape_visual.py <edicion.txt> [--solo-tarjetas|--solo-pdf]
Salida: reports/<season>/roast/visual/<nombre-edición>/{NN-*.jpg, <nombre>.pdf}
"""
import html
import os
import signal
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "data" / "intel" / "brand"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SENTINELA = (1, 2, 3)          # color fuera de la tarjeta, para recortar
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
POR_TARJETA_RANKING = 6        # 18 franquicias → 3 tarjetas; 12 → 2

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:'
           'wght@400;600;800&display=swap" rel="stylesheet">')


# ───────────────────────────── parseo ─────────────────────────────

ENCABEZADO = re.compile(r"^(?!—)(\S+)\s+\*([^*:]+)\*\s*(\(.*\))?\s*$")  # "— *firma*" no es sección
RANK = re.compile(r"^\s*(\d+)\.\s+\*(.+?)\*\s+(\d+-\d+),\s*([\d.]+)\s*\((\d+)º\)\s*—\s*(.*)$")
MEDALLA = re.compile(r"^(\S+)\s+\*([^*]+?):\*\s*(.*)$")
MARCADOR = re.compile(r"^\*(.+?)\s+([\d.]+)\s+—\s+(.+?)\s+([\d.]+)\.\*\s*(.*)$")
DUELO = re.compile(r"^\*(.+?)\s+vs\s+(.+?)\.\*\s*(.*)$")


def leer(path):
    """Edición → (cabecera, portada, secciones). No toca el texto."""
    lineas = Path(path).read_text().rstrip("\n").split("\n")
    jornada = re.sub(r"^_|_$", "", lineas[1].strip()) if len(lineas) > 1 else ""
    portada, secciones, actual = [], [], None
    en_tabla = False
    for ln in lineas[2:]:
        if ln.strip().startswith("```"):
            en_tabla = not en_tabla
            (actual["lineas"] if actual else portada).append(ln)
            continue
        m = None if en_tabla else ENCABEZADO.match(ln.strip())
        if m:
            actual = {"emoji": m.group(1), "titulo": m.group(2).strip(),
                      "sub": (m.group(3) or "").strip("() "), "lineas": []}
            secciones.append(actual)
        else:
            (actual["lineas"] if actual else portada).append(ln)
    return jornada, portada, secciones


def bloques(lineas):
    """Agrupa las líneas de una sección en bloques tipados."""
    out, i = [], 0
    while i < len(lineas):
        ln = lineas[i].rstrip()
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            filas = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                filas.append(lineas[i])
                i += 1
            i += 1
            out.append(("tabla", filas))
            continue
        if s.startswith("•"):
            out.append(("bullet", s.lstrip("• ").strip()))
        elif RANK.match(s):
            out.append(("rank", RANK.match(s).groups()))
        elif MARCADOR.match(s):
            out.append(("marcador", MARCADOR.match(s).groups()))
        elif DUELO.match(s):
            out.append(("duelo", DUELO.match(s).groups()))
        elif s.startswith("— *") or s.startswith("—*"):
            out.append(("firma", s.lstrip("— ").strip()))
        elif MEDALLA.match(s) and not s.startswith("*"):
            out.append(("medalla", MEDALLA.match(s).groups()))
        else:
            out.append(("parrafo", s))
        i += 1
    return out


def cap(t):
    """Primera letra en mayúscula (las líneas del .txt arrancan tras un guion)."""
    return t[:1].upper() + t[1:] if t else t


def inline(t):
    """Formato WhatsApp → HTML: *negrita*, _cursiva_. Escapa todo lo demás."""
    t = html.escape(t, quote=False)
    t = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w])_([^_]+)_(?![\w])", r"<em>\1</em>", t)
    return t


def tabla_guerra(filas):
    """Bloque monoespaciado del Marcador → filas (bando, G, P, pct)."""
    res = []
    for f in filas:
        m = re.match(r"\s*(.+?)\s+(\d+)\s*-\s*(\d+)\s+(\.\d+)\s*$", f)
        if m:
            res.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
    return res


# ───────────────────────────── HTML ─────────────────────────────

def html_bloques(bs, tema):
    """Render común a tarjeta (tema 'card') y PDF (tema 'pdf')."""
    partes, lista = [], []

    def cerrar_lista():
        if lista:
            partes.append("<ul class='bullets'>" + "".join(f"<li>{x}</li>" for x in lista) + "</ul>")
            lista.clear()

    for tipo, v in bs:
        if tipo != "bullet":
            cerrar_lista()
        if tipo == "bullet":
            lista.append(inline(v))
        elif tipo == "parrafo":
            partes.append(f"<p>{inline(v)}</p>")
        elif tipo == "firma":
            partes.append(f"<p class='firma'>— {inline(v)}</p>")
        elif tipo == "medalla":
            emo, etq, txt = v
            partes.append(f"<div class='medalla'><div class='med-emo'>{emo}</div>"
                          f"<div><div class='med-etq'>{html.escape(etq)}</div>"
                          f"<div class='med-txt'>{inline(cap(txt))}</div></div></div>")
        elif tipo == "marcador":
            a, pa, b, pb, txt = v
            partes.append(
                "<div class='score'>"
                f"<div class='sc-eq gana'><span>{html.escape(a)}</span><b>{pa}</b></div>"
                f"<div class='sc-eq'><span>{html.escape(b)}</span><b>{pb}</b></div></div>"
                f"<p>{inline(txt)}</p>")
        elif tipo == "duelo":
            a, b, txt = v
            partes.append(f"<div class='duelo'><div class='du-vs'>{html.escape(a)} "
                          f"<i>vs</i> {html.escape(b)}</div><div>{inline(txt)}</div></div>")
        elif tipo == "rank":
            n, eq, rec, pts, proy, txt = v
            tag = ""
            if "🐎" in txt:
                tag, txt = "<span class='tag caballo'>🐎 caballo negro</span>", txt.replace("🐎", "").strip()
            elif "📉" in txt:
                tag, txt = "<span class='tag decep'>📉 decepción</span>", txt.replace("📉", "").strip()
            partes.append(
                f"<div class='rank'><div class='rk-n'>{n}</div><div class='rk-body'>"
                f"<div class='rk-top'><span class='rk-eq'>{html.escape(eq)}</span>"
                f"<span class='rk-rec'>{rec} · {pts} pts · proy {proy}º</span></div>"
                f"{tag}<div class='rk-txt'>{inline(cap(txt))}</div></div></div>")
        elif tipo == "tabla":
            filas = tabla_guerra(v)
            pcts = [g / max(1, g + p) for _, g, p, _ in filas]
            top, bot = (max(pcts), min(pcts)) if pcts else (0, 0)
            trs = []
            for (bando, g, p, pct), x in zip(filas, pcts):
                cls = "lider" if x == top else ("sotano" if x == bot and top != bot else "")
                med = "👑 " if cls == "lider" else ("💩 " if cls == "sotano" else "")
                trs.append(f"<tr class='{cls}'><td>{med}{html.escape(bando)}</td>"
                           f"<td class='num'>{g}-{p}</td><td class='num pct'>{pct}</td></tr>")
            partes.append("<table class='guerra'><tr><th>Bando</th><th>G-P</th><th>%</th></tr>"
                          + "".join(trs) + "</table>")
    cerrar_lista()
    return "\n".join(partes)


CSS_CARD = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:rgb(1,2,3);width:1080px}
.card{width:1080px;height:1350px;background:#0A1428;color:#fff;
  font-family:Inter,'Apple Color Emoji',Helvetica,Arial,sans-serif;display:flex;flex-direction:column;
  position:relative;overflow:hidden}
.card::before{content:"";position:absolute;inset:0;
  background:radial-gradient(1200px 500px at 110% -10%,rgba(213,10,10,.18),transparent 60%),
             radial-gradient(900px 600px at -20% 110%,rgba(1,51,105,.55),transparent 60%);}
.top{position:relative;display:flex;align-items:center;gap:22px;padding:44px 60px 0}
.top img{height:92px}
.kick{font-family:Anton,'Arial Black',sans-serif;font-size:34px;letter-spacing:2px}
.kick b{color:#D50A0A;font-weight:400}
.meta{font-size:22px;color:#AFBBD0;font-weight:600;letter-spacing:1.5px;text-transform:uppercase}
.pag{margin-left:auto;font-size:22px;color:#5B6B85;font-weight:800}
h1{position:relative;font-family:Anton,'Arial Black',sans-serif;font-weight:400;
  font-size:78px;line-height:1.02;padding:40px 60px 0;letter-spacing:.5px;text-transform:uppercase}
h1 .e{font-size:66px;margin-right:14px;font-family:'Apple Color Emoji'}
.sub{position:relative;padding:10px 60px 0;color:#AFBBD0;font-size:24px;font-weight:600}
.rule{position:relative;height:6px;width:140px;background:#D50A0A;margin:26px 60px 0}
main{position:relative;flex:1;min-height:0;padding:34px 60px 30px;font-size:34px;line-height:1.38}
main p{margin:0 0 22px}
main strong{font-weight:800;color:#fff}
main em{color:#F2C14E;font-style:italic}
.bullets{list-style:none}
.bullets li{background:rgba(255,255,255,.06);border-left:6px solid #D50A0A;border-radius:14px;
  padding:22px 26px;margin:0 0 20px}
.medalla{display:flex;gap:22px;background:rgba(255,255,255,.06);border-radius:18px;
  padding:24px 26px;margin:0 0 20px;align-items:flex-start}
.med-emo{font-size:62px;line-height:1}
.med-etq{font-family:Anton,'Arial Black',sans-serif;font-size:34px;color:#F2C14E;
  text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.med-txt{font-size:31px;line-height:1.36}
.score{display:flex;flex-direction:column;gap:10px;margin:0 0 26px}
.sc-eq{display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,.06);
  border-radius:14px;padding:18px 28px;font-weight:800;font-size:38px;color:#AFBBD0}
.sc-eq b{font-family:Anton,'Arial Black',sans-serif;font-weight:400;font-size:62px}
.sc-eq.gana{background:#D50A0A;color:#fff}
.duelo{background:rgba(255,255,255,.06);border-radius:18px;padding:24px 28px;margin:0 0 22px}
.du-vs{font-family:Anton,'Arial Black',sans-serif;font-size:40px;margin-bottom:8px}
.du-vs i{color:#D50A0A;font-style:normal;margin:0 8px}
.rank{display:flex;gap:22px;padding:20px 0;border-bottom:2px solid rgba(255,255,255,.09)}
.rk-n{font-family:Anton,'Arial Black',sans-serif;font-size:66px;line-height:1;color:#D50A0A;
  width:84px;text-align:right;flex:none}
.rk-body{flex:1}
.rk-top{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px}
.rk-eq{font-weight:800;font-size:36px}
.rk-rec{font-size:24px;color:#AFBBD0;font-weight:600}
.rk-txt{font-size:29px;line-height:1.36;margin-top:6px;color:#E6EBF3}
.tag{display:inline-block;font-size:21px;font-weight:800;border-radius:999px;padding:4px 14px;
  margin-top:8px;text-transform:uppercase;letter-spacing:1px}
.tag.caballo{background:#1F6F43}.tag.decep{background:#7A1E1E}
table.guerra{width:100%;border-collapse:separate;border-spacing:0 14px;margin:0 0 20px}
table.guerra th{text-align:left;font-size:22px;color:#AFBBD0;font-weight:600;padding:0 26px}
table.guerra td{background:rgba(255,255,255,.06);padding:26px;font-size:44px;font-weight:800}
table.guerra td:first-child{border-radius:16px 0 0 16px}
table.guerra td:last-child{border-radius:0 16px 16px 0}
table.guerra td.num{font-family:Anton,'Arial Black',sans-serif;font-weight:400;font-size:52px}
table.guerra td.pct{color:#AFBBD0;font-size:40px}
table.guerra tr.lider td{background:#16294A}
table.guerra tr.lider td.pct{color:#D50A0A}
table.guerra tr.sotano td{background:#2A1418}
.firma{color:#AFBBD0;font-style:italic;font-size:30px}
.marca{margin-top:10px;background:url('ESCUDO') center/contain no-repeat;opacity:.07}
.relleno{margin-top:10px;border-radius:22px;background-size:cover;background-position:46% 22%;box-shadow:inset 0 0 0 2px rgba(255,255,255,.08)}
footer{position:relative;display:flex;justify-content:space-between;align-items:center;
  padding:22px 60px 34px;border-top:5px solid #D50A0A;margin:0 60px;color:#5B6B85;
  font-size:22px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase}
/* portada */
.banda{position:absolute;top:0;right:0;width:620px;height:470px;background-size:cover}
.banda::after{content:"";position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(10,20,40,0) 50%,#0A1428 100%),
  linear-gradient(90deg,#0A1428 0%,rgba(10,20,40,.55) 22%,rgba(10,20,40,0) 50%)}
.card.con-foto .top{max-width:none}
.kick,.meta{white-space:nowrap;text-shadow:0 2px 10px rgba(0,0,0,.7)}
.card.con-foto h1{padding-top:250px;text-shadow:0 4px 18px rgba(0,0,0,.6)}
.card.con-foto .sub{text-shadow:0 2px 10px rgba(0,0,0,.8)}
.cover .foto{position:relative;height:640px;background-size:cover;background-position:42% 18%}
.cover .foto::after{content:"";position:absolute;inset:0;
  background:linear-gradient(180deg,rgba(10,20,40,0) 45%,#0A1428 98%)}
.cover .escudo{position:absolute;top:40px;right:48px;height:150px;z-index:2}
.cover .titulo{position:relative;margin-top:-170px;padding:0 60px;z-index:2}
.cover .t1{font-family:Anton,'Arial Black',sans-serif;font-size:118px;line-height:.95}
.cover .t2{font-family:Anton,'Arial Black',sans-serif;font-size:118px;line-height:.95;color:#D50A0A}
.cover .jor{margin-top:18px;font-size:28px;font-weight:800;color:#AFBBD0;letter-spacing:2px;
  text-transform:uppercase}
.cover main{font-size:33px}
.cover .indice{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
.cover .indice span b{font-family:'Apple Color Emoji';font-weight:400;margin-right:6px}
.cover .indice span{background:rgba(255,255,255,.08);border-radius:999px;padding:8px 18px;
  font-size:22px;font-weight:600;color:#D6DDE8}
"""

CSS_PDF = """
@page{size:Letter;margin:0}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,'Apple Color Emoji',Helvetica,Arial,sans-serif;color:#0A1428;font-size:11.2pt;
  line-height:1.45;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.hdr{position:fixed;top:0;left:0;right:0;height:26mm;background:#013369;color:#fff;
  display:flex;align-items:center;gap:5mm;padding:0 16mm}
.hdr img{height:17mm}
.hdr .k{font-family:Anton,'Arial Black',sans-serif;font-size:19pt;letter-spacing:.6pt}
.hdr .k b{color:#FF3B3B;font-weight:400}
.hdr .m{font-size:8.5pt;letter-spacing:1.2pt;text-transform:uppercase;color:#C9D4E6;font-weight:600}
.hdr::after{content:"";position:absolute;left:0;right:0;bottom:-1.6mm;height:1.6mm;background:#D50A0A}
.ftr{position:fixed;bottom:0;left:0;right:0;height:13mm;display:flex;align-items:center;
  justify-content:space-between;padding:0 16mm;font-size:8pt;color:#5B6B85;letter-spacing:1pt;
  text-transform:uppercase;font-weight:600;border-top:.6mm solid #D50A0A;margin:0 16mm;padding:0}
table.pagina{width:100%;border-collapse:collapse}
.sp-top{height:34mm}.sp-bot{height:18mm}
.cuerpo{padding:0 16mm}
.portada{display:flex;gap:6mm;align-items:stretch;margin-bottom:6mm}
.portada .foto{width:62mm;min-height:70mm;border-radius:3mm;background-size:cover;
  background-position:42% 18%;flex:none}
.portada .t1{font-family:Anton,'Arial Black',sans-serif;font-size:30pt;line-height:1}
.portada .t1 b{color:#D50A0A;font-weight:400}
.portada .jor{font-weight:800;font-size:9pt;letter-spacing:1.4pt;text-transform:uppercase;
  color:#5B6B85;margin:2mm 0 3mm}
.portada p{margin:0 0 2.4mm}
h2{font-family:Anton,'Arial Black',sans-serif;font-weight:400;font-size:17pt;letter-spacing:.4pt;
  text-transform:uppercase;margin:7mm 0 1mm;padding-bottom:1.2mm;border-bottom:.7mm solid #D50A0A;
  break-after:avoid}
h2 .e{margin-right:2mm;font-family:'Apple Color Emoji'}
.sub{font-size:8.5pt;color:#5B6B85;margin:0 0 2.5mm;font-weight:600}
p{margin:0 0 2.6mm}
strong{font-weight:800}
em{font-style:italic;color:#013369}
.bullets{margin:0 0 2mm;padding:0;list-style:none}
.bullets li{border-left:1.2mm solid #D50A0A;background:#F2F5FA;padding:2mm 3mm;margin:0 0 2mm;
  border-radius:1.5mm;break-inside:avoid}
.medalla{display:flex;gap:3mm;background:#F2F5FA;border-radius:2mm;padding:2.6mm 3.2mm;
  margin:0 0 2.2mm;break-inside:avoid}
.med-emo{font-size:18pt;line-height:1}
.med-etq{font-family:Anton,'Arial Black',sans-serif;font-size:11.5pt;color:#013369;
  text-transform:uppercase;letter-spacing:.4pt}
.score{display:flex;gap:2mm;margin:1mm 0 2.6mm;break-inside:avoid}
.sc-eq{flex:1;display:flex;justify-content:space-between;align-items:center;background:#F2F5FA;
  border-radius:2mm;padding:2mm 3.4mm;font-weight:800}
.sc-eq b{font-family:Anton,'Arial Black',sans-serif;font-weight:400;font-size:17pt}
.sc-eq.gana{background:#013369;color:#fff}
.duelo{background:#F2F5FA;border-radius:2mm;padding:2.4mm 3.2mm;margin:0 0 2.2mm;break-inside:avoid}
.du-vs{font-family:Anton,'Arial Black',sans-serif;font-size:12pt}
.du-vs i{color:#D50A0A;font-style:normal;margin:0 1.4mm}
.rank{display:flex;gap:3mm;padding:1.8mm 0;border-bottom:.3mm solid #DCE3EE;break-inside:avoid}
.rk-n{font-family:Anton,'Arial Black',sans-serif;font-size:16pt;color:#D50A0A;width:9mm;
  text-align:right;flex:none;line-height:1.1}
.rk-top{display:flex;flex-wrap:wrap;gap:0 3mm;align-items:baseline}
.rk-eq{font-weight:800}
.rk-rec{font-size:8.5pt;color:#5B6B85;font-weight:600}
.tag{display:inline-block;font-size:7pt;font-weight:800;border-radius:9pt;padding:.4mm 2mm;
  text-transform:uppercase;letter-spacing:.6pt;color:#fff;margin:.6mm 0}
.tag.caballo{background:#1F6F43}.tag.decep{background:#9B2222}
table.guerra{border-collapse:separate;border-spacing:0 1.4mm;width:110mm;margin:1mm 0 2.6mm}
table.guerra th{text-align:left;font-size:8pt;color:#5B6B85;padding:0 3mm}
table.guerra td{background:#F2F5FA;padding:2mm 3mm;font-weight:800;font-size:12pt}
table.guerra td.num{font-family:Anton,'Arial Black',sans-serif;font-weight:400}
table.guerra tr.lider td{background:#013369;color:#fff}
table.guerra tr.sotano td{background:#FBE9E9}
.firma{font-style:italic;color:#5B6B85}
"""


def escudo_uri():
    return (BRAND / "gallamijos-escudo.svg").resolve().as_uri()


# Vestuario de Miroslava (data/intel/brand/): archivo + altura de la cara
# (% vertical) para encuadrar la banda de cada tarjeta sin cortarle la cabeza.
VESTUARIO = {
    "jersey":         ("miroslava-jersey.png", 20),         # tailgate con el micrófono GM
    "gala":           ("miroslava-gala.jpg", 24),           # vestido rojo con el Lombardi
    "noticiero":      ("miroslava-noticiero.jpg", 26),      # conductora en el set GM
    "exclusiva":      ("miroslava-exclusiva.jpg", 28),      # gabardina, CONFIDENTIAL, flashes
    "exclusiva-news": ("miroslava-exclusiva-news.jpg", 28), # misma escena, micrófono GM News
    "navidad":        ("miroslava-navidad.jpg", 30),        # suéter navideño (solo diciembre)
}
# Qué Miroslava va con qué sección (por palabra del título). La primera que
# no repita la de la tarjeta anterior gana; así el carrusel no se ve clonado.
FOTO_SECCION = [
    ("regadera", ["exclusiva", "exclusiva-news"]),     # el chisme: la de los expedientes
    ("putiza", ["exclusiva-news", "exclusiva"]),       # nota roja de estadio
    ("medallas", ["gala", "noticiero"]),               # la premiación
    ("guerra", ["noticiero", "gala"]),                 # parte oficial desde el set
    ("penthouse", ["noticiero", "gala", "exclusiva"]), # la tabla, rotando por tarjeta
    ("palpitote", ["gala", "noticiero"]),
    ("cierre", ["gala", "noticiero"]),
]
FOTOS = {}


def foto_uri(nombre="jersey"):
    """Copias de 1400px en JPG: los originales metían 10 MB al PDF."""
    return FOTOS.get(nombre) or (BRAND / VESTUARIO[nombre][0]).resolve().as_uri()


def preparar_fotos(tmp):
    for nombre, (archivo, _) in VESTUARIO.items():
        if not (BRAND / archivo).exists():
            continue
        im = Image.open(BRAND / archivo).convert("RGB")
        im.thumbnail((1400, 1400))
        out = tmp / f"m-{nombre}.jpg"
        im.save(out, quality=86, optimize=True)
        FOTOS[nombre] = out.resolve().as_uri()


def elegir_foto(titulo, anterior):
    t = titulo.lower()
    prefs = next((f for clave, f in FOTO_SECCION if clave in t), ["noticiero", "gala"])
    prefs = [f for f in prefs if f in VESTUARIO] + [f for f in VESTUARIO if f not in ("navidad", "jersey")]
    return next((f for f in prefs if f != anterior), prefs[0])


def fecha_legible(nombre):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", nombre)
    if not m:
        return date.today().isoformat()
    return f"{int(m.group(3))} {MESES[int(m.group(2)) - 1]} {m.group(1)}"


def tarjeta(cuerpo_html, jornada, fecha, pag, total, titulo=None, emoji="", sub="",
            foto=None, foto_final="jersey"):
    cab = (f"<h1><span class='e'>{emoji}</span>{html.escape(titulo)}</h1>"
           + (f"<div class='sub'>{html.escape(sub)}</div>" if sub else "")
           + "<div class='rule'></div>") if titulo else ""
    banda = (f"<div class='banda' style=\"background-image:url('{foto_uri(foto)}');"
             f"background-position:50% {VESTUARIO[foto][1]}%\"></div>") if foto else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_CARD.replace("ESCUDO", escudo_uri())}.relleno{{background-image:url('{foto_uri(foto_final)}')}}</style></head><body data-ultima="{int(pag == total)}"><div class="card{' con-foto' if foto else ''}">
{banda}
<div class="top"><img src="{escudo_uri()}"><div><div class="kick">EL DESTAPE DE <b>MIROSLAVA</b></div>
<div class="meta">{html.escape(jornada)}</div></div></div>
{cab}<main>{cuerpo_html}</main>
<footer><span>💋 Miroslava</span><span>{pag} / {total}</span><span>{fecha}</span></footer></div><script>
/* Todo cabe en 1080x1350: si el cuerpo se desborda, se encoge (zoom) hasta
   que entra. Así el carrusel sale parejo 4:5 sin cortar texto. */
document.fonts.ready.then(() => {{
  const m = document.querySelector("main"); let z = 1;
  const ajustar = () => {{ z = 1; m.style.zoom = 1;
    while (m.scrollHeight > m.clientHeight + 1 && z > 0.55) {{ z -= 0.02; m.style.zoom = z; }} }};
  ajustar();
  /* Si la foto obliga a encoger la letra de más, gana la letra: fuera foto. */
  const card = document.querySelector(".card.con-foto");
  if (card && z < 0.8) {{
    card.classList.remove("con-foto"); document.querySelector(".banda").remove(); ajustar();
  }}
  /* Tarjeta corta: el hueco lo llena Miroslava, no el vacío. */
  const ult = m.lastElementChild;
  const libre = ult ? m.getBoundingClientRect().bottom - ult.getBoundingClientRect().bottom - 30 : 0;
  if (libre > 330 && !document.querySelector(".cover")) {{
    /* Miroslava solo en la última tarjeta; en las demás, el escudo de agua
       (la misma foto en cinco tarjetas se vuelve papel tapiz). */
    const ultima = document.body.dataset.ultima === "1";
    const f = document.createElement("div"); f.className = ultima ? "relleno" : "marca";
    f.style.height = (libre - 40) + "px"; m.appendChild(f);
  }}
}});
</script></body></html>"""


def portada_html(portada_lineas, secciones, jornada, fecha, total, foto="jersey"):
    cuerpo = html_bloques(bloques(portada_lineas), "card")
    indice = "".join(f"<span><b>{s['emoji']}</b>{html.escape(cap(s['titulo'].split(' — ')[0].lower()).replace('miroslava', 'Miroslava'))}</span>"
                     for s in secciones)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_CARD}</style></head><body><div class="card cover">
<div class="foto" style="background-image:url('{foto_uri(foto)}')"></div>
<img class="escudo" src="{escudo_uri()}">
<div class="titulo"><div class="t1">EL DESTAPE</div><div class="t2">DE MIROSLAVA</div>
<div class="jor">{html.escape(jornada)} · {fecha}</div></div>
<main>{cuerpo}<div class="indice">{indice}</div></main>
<footer><span>💋 Desliza →</span><span>1/{total}</span></footer></div><script>
/* Todo cabe en 1080x1350: si el cuerpo se desborda, se encoge (zoom) hasta
   que entra. Así el carrusel sale parejo 4:5 sin cortar texto. */
document.fonts.ready.then(() => {{
  const m = document.querySelector("main"); let z = 1;
  const ajustar = () => {{ z = 1; m.style.zoom = 1;
    while (m.scrollHeight > m.clientHeight + 1 && z > 0.55) {{ z -= 0.02; m.style.zoom = z; }} }};
  ajustar();
  /* Si la foto obliga a encoger la letra de más, gana la letra: fuera foto. */
  const card = document.querySelector(".card.con-foto");
  if (card && z < 0.8) {{
    card.classList.remove("con-foto"); document.querySelector(".banda").remove(); ajustar();
  }}
}});
</script></body></html>"""


def pdf_html(portada_lineas, secciones, jornada, fecha, foto="jersey"):
    liga = jornada.split("—")[-1].strip() or "La Gallamijos"
    cuerpo = []
    for s in secciones:
        cuerpo.append(f"<h2><span class='e'>{s['emoji']}</span>{html.escape(s['titulo'])}</h2>"
                      + (f"<div class='sub'>{html.escape(s['sub'])}</div>" if s["sub"] else "")
                      + html_bloques(bloques(s["lineas"]), "pdf"))
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_PDF}</style></head><body>
<div class="hdr"><img src="{escudo_uri()}"><div><div class="k">EL DESTAPE DE <b>MIROSLAVA</b></div>
<div class="m">Órgano oficial de chisme · {html.escape(liga)} · est. 2015</div></div></div>
<div class="ftr"><span>{html.escape(jornada)}</span><span>{fecha}</span><span>💋 Miroslava</span></div>
<table class="pagina"><thead><tr><td><div class="sp-top"></div></td></tr></thead>
<tfoot><tr><td><div class="sp-bot"></div></td></tr></tfoot><tbody><tr><td><div class="cuerpo">
<div class="portada"><div class="foto" style="background-image:url('{foto_uri(foto)}')"></div>
<div><div class="t1">EL DESTAPE DE <b>MIROSLAVA</b></div><div class="jor">{html.escape(jornada)} · {fecha}</div>
{html_bloques(bloques(portada_lineas), "pdf")}</div></div>
{"".join(cuerpo)}
</div></td></tr></tbody></table></body></html>"""


# ───────────────────────────── render ─────────────────────────────

def chrome(args, perfil, salida):
    """Chrome headless en este Mac escribe el archivo y luego NO termina el
    proceso (se queda colgado tras el 'bytes written'). Así que se lanza en
    segundo plano, se espera a que el log confirme la escritura y se mata."""
    # Perfil NUEVO por llamada: un Chrome matado deja el candado del perfil y
    # el siguiente se cuelga esperándolo.
    perfil = Path(tempfile.mkdtemp(dir=Path(perfil).parent, prefix="perfil-"))
    log = perfil / "chrome.log"
    with open(log, "w") as fh:
        p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                              "--no-first-run", "--no-default-browser-check",
                              f"--user-data-dir={perfil}", "--allow-file-access-from-files",
                              "--virtual-time-budget=9000"] + args,
                             stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(240):                       # hasta 120 s
            time.sleep(0.5)
            if Path(salida).exists() and "written to file" in log.read_text(errors="ignore"):
                return
            if p.poll() is not None:
                break
        sys.exit(f"Chrome no produjo {salida}:\n{log.read_text(errors='ignore')[-800:]}")
    finally:
        # Mata al grupo entero: Chrome deja procesos hijos (GPU, renderer).
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()


def captura(html_txt, out_png, tmp, perfil):
    src = tmp / (out_png.stem + ".html")
    src.write_text(html_txt)
    crudo = tmp / (out_png.stem + "-raw.png")
    chrome(["--force-device-scale-factor=1", "--window-size=1080,4200",
            f"--screenshot={crudo}", src.as_uri()], perfil, crudo)
    im = Image.open(crudo).convert("RGB")
    w, h = im.size
    alto = h
    for y in range(h - 1, 0, -1):          # recorta lo que quedó fuera de la tarjeta
        if im.getpixel((4, y)) != SENTINELA:
            alto = y + 1
            break
    if alto >= h - 2:
        print(f"  ⚠️ {out_png.name}: la tarjeta llena la ventana — revisar que no se corte")
    im.crop((0, 0, w, alto)).save(out_png, quality=90, optimize=True, progressive=True)
    return alto


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    edicion = Path(args[0]).resolve()
    jornada, portada, secciones = leer(edicion)
    if not secciones:
        sys.exit("No encontré secciones (líneas tipo '🥊 *TÍTULO*').")
    fecha = fecha_legible(edicion.stem)
    temporada = edicion.stem[:4]
    destino = ROOT / "reports" / temporada / "roast" / "visual" / edicion.stem
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    # Plan de tarjetas: portada + una por sección; el ranking se parte.
    plan = []
    for s in secciones:
        bs = bloques(s["lineas"])
        ranks = [b for b in bs if b[0] == "rank"]
        if len(ranks) > POR_TARJETA_RANKING:
            resto = [b for b in bs if b[0] != "rank"]
            trozos = [ranks[i:i + POR_TARJETA_RANKING]
                      for i in range(0, len(ranks), POR_TARJETA_RANKING)]
            for k, tr in enumerate(trozos):
                sub = (s["sub"] + " · " if s["sub"] else "") + f"{tr[0][1][0]}–{tr[-1][1][0]}"
                # Solo la primera tarjeta de una sección partida lleva foto:
                # en las de continuación el espacio es para la letra.
                plan.append((s, tr + (resto if k == len(trozos) - 1 else []), sub, k == 0))
        else:
            plan.append((s, bs, s["sub"], True))
    total = len(plan) + 1

    with tempfile.TemporaryDirectory() as t:
        tmp, perfil = Path(t), Path(t) / "perfil"
        preparar_fotos(tmp)
        # Diciembre = playoffs del fantasy: portada y despedida con suéter navideño.
        principal = "navidad" if edicion.stem[5:7] == "12" and "navidad" in FOTOS else "jersey"
        if "--solo-pdf" not in sys.argv:
            out = destino / "01-portada.jpg"
            captura(portada_html(portada, secciones, jornada, fecha, total, principal), out, tmp, perfil)
            anterior = principal
            print(f"  {out.relative_to(ROOT)}")
            for i, (s, bs, sub, con_foto) in enumerate(plan, start=2):
                slug = re.sub(r"[^a-z0-9]+", "-", s["titulo"].lower().split(" — ")[0]
                              .translate(str.maketrans("áéíóúñ", "aeioun"))).strip("-")[:28]
                out = destino / f"{i:02d}-{slug}.jpg"
                foto = elegir_foto(s["titulo"], anterior) if con_foto else None
                anterior = foto or anterior
                captura(tarjeta(html_bloques(bs, "card"), jornada, fecha, i, total,
                                s["titulo"], s["emoji"], sub, foto, principal), out, tmp, perfil)
                print(f"  {out.relative_to(ROOT)}")
        if "--solo-tarjetas" not in sys.argv:
            src = tmp / "edicion.html"
            src.write_text(pdf_html(portada, secciones, jornada, fecha, principal))
            pdf = destino / f"{edicion.stem}.pdf"
            chrome(["--no-pdf-header-footer", f"--print-to-pdf={pdf}", src.as_uri()], perfil, pdf)
            print(f"  {pdf.relative_to(ROOT)}")
    print(f"[visual] {destino.relative_to(ROOT)} listo")


if __name__ == "__main__":
    main()
