#!/usr/bin/env python3
"""EL DESTAPE en formato visual: carrusel de tarjetas + PDF membretado.

Lee la edición APROBADA en texto de WhatsApp (el mismo .txt que pasa por
roast_lint y el editor) y la convierte, sin reescribir una sola palabra, en:

  1. Un CARRUSEL de tarjetas 1080 de ancho (mín. 1350 de alto, 4:5) — portada
     con Miroslava + una tarjeta por sección; el ranking se parte en varias
     para que la letra se lea en un teléfono. Es lo que se manda al grupo.
  2. Un PDF en formato PERIÓDICO (cabezal gótico, fechario, primera plana con
     la Putiza de nota principal, tres columnas, fotos de Miroslava como
     fotoperiodismo; el alto de página se ajusta para no dejar media plana en
     blanco) para quien la quiera leer de corrido.
  3. Un PDF CARRUSEL (las tarjetas en orden, una por página): un solo archivo
     que se manda a WhatsApp de un toque. Y las tarjetas llevan fecha EXIF
     consecutiva, así que guardadas en el teléfono quedan en orden.

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

# Etiquetas del Penthouse (user 2026-10-06: además de 🐎/📉, "tags chistosos
# como de salada o de mojón, y de mal coach").
ETIQUETAS = {
    "🐎": ("caballo", "caballo negro"),
    "📉": ("decep", "decepción"),
    "🧂": ("salado", "salado"),
    "💩": ("mojon", "mojón"),
    "🤡": ("malcoach", "mal coach"),
}


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
            # Etiquetas del ranking: la primera que aparezca en la línea.
            tag = ""
            for emo, (cls, etq) in ETIQUETAS.items():
                if emo in txt:
                    if not tag:
                        tag = f"<span class='tag {cls}'>{emo} {etq}</span>"
                    txt = txt.replace(emo, "").strip()
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
.tag.caballo{background:#1F6F43}.tag.decep{background:#7A1E1E}.tag.salado{background:#4A5A73}.tag.mojon{background:#6B4423}.tag.malcoach{background:#B4511E}
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
.tag.caballo{background:#1F6F43}.tag.decep{background:#9B2222}.tag.salado{background:#4A5A73}.tag.mojon{background:#6B4423}.tag.malcoach{background:#B4511E}
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
# (% vertical) y, si no está centrada, su posición horizontal (%), para
# encuadrar la banda de cada tarjeta sin cortarle la cabeza.
VESTUARIO = {
    "jersey":         ("miroslava-jersey.png", 18, 42),         # tailgate con el micrófono GM
    "gala":           ("miroslava-gala.jpg", 24),           # vestido rojo con el Lombardi
    "noticiero":      ("miroslava-noticiero.jpg", 26),      # conductora en el set GM
    "exclusiva":      ("miroslava-exclusiva.jpg", 28),      # gabardina, CONFIDENTIAL, flashes
    "exclusiva-news": ("miroslava-exclusiva-news.jpg", 28), # misma escena, micrófono GM News
    "navidad":        ("miroslava-navidad.jpg", 30),        # suéter navideño (solo diciembre)
    # Vestuario POR SECCIÓN (prompts en brand/miroslava-vestuario-prompts.md).
    # Entran solos en cuanto el archivo existe; mientras no, se usa el genérico.
    "boxeo":          ("miroslava-boxeo.jpg", 28, 52),          # La Putiza
    "regadera":       ("miroslava-regadera.jpg", 30, 64),       # Se dice en la Regadera
    "podio":          ("miroslava-podio.jpg", 22, 50),          # Medallas y Vergazos
    "salado":         ("miroslava-salado.jpg", 36, 50),         # El Salado (periódico)
    "muerto":         ("miroslava-muerto.jpg", 32, 56),         # El Muerto (periódico)
    "guerra":         ("miroslava-guerra.jpg", 30, 50),         # Marcador de la Guerra
    "elevador":       ("miroslava-elevador.jpg", 23, 45),       # Del Penthouse al Sótano
    "palpitote":      ("miroslava-palpitote.jpg", 30, 50),      # El Palpitote del Escote
    "despedida":      ("miroslava-despedida.jpg", 27, 52),      # Cierre, pero no de patas
    "retrato":        ("miroslava-retrato.jpg", 30),        # retrato de estudio (base nueva)
    "redaccion":      ("miroslava-redaccion.jpg", 24, 50),      # Fe de erratas / nota de la redacción
    # Variantes de rotación (2026-09-29): encuadre medido en cada foto.
    "portada-estadio":       ("miroslava-portada-estadio.jpg", 23, 50),
    "portada-camara":        ("miroslava-portada-camara.jpg", 28, 62),
    "portada-voceadora":     ("miroslava-portada-voceadora.jpg", 30, 53),
    "final-sofa":            ("miroslava-final-sofa.jpg", 30, 37),
    "final-gradas":          ("miroslava-final-gradas.jpg", 22, 50),
    "final-beso":            ("miroslava-final-beso.jpg", 40, 51),
    "boxeo-arbitra":         ("miroslava-boxeo-arbitra.jpg", 24, 50),
    "regadera-cortina":      ("miroslava-regadera-cortina.jpg", 27, 47),
    "medallas-oscar":        ("miroslava-medallas-oscar.jpg", 25, 53),
    "guerra-trinchera":      ("miroslava-guerra-trinchera.jpg", 30, 50),
    "palpitote-tarot":       ("miroslava-palpitote-tarot.jpg", 30, 50),
    "elevador-terraza":      ("miroslava-elevador-terraza.jpg", 27, 50),
    "despedida-convertible": ("miroslava-despedida-convertible.jpg", 23, 50),
}
GENERICAS = ["noticiero", "gala", "exclusiva", "exclusiva-news"]
# Encuadre horizontal en la PORTADILLA (4:5 a cuadro completo): en el
# elevador el chiste es el dedo en "SÓTANO", así que se corre a la izquierda
# para que entren el panel y la cara.
PORTADILLA_X = {"elevador": 34, "elevador-terraza": 62}
# Qué Miroslava va con qué sección (por palabra del título). La primera que
# no repita la de la tarjeta anterior gana; así el carrusel no se ve clonado.
# POOLS de rotación por sección (user 2026-09-29: "más imágenes que ir
# alternando cada semana"). "x-*" = toda variante miroslava-x-<algo>.jpg que
# exista en brand/: se descubren solas, no hay que registrarlas. Cada semana
# la sección toma la siguiente del pool (número de jornada; la Dinastía va un
# paso adelante). RESPALDO = genéricas por si el pool está vacío.
POOLS = {
    "portada":   ["jersey", "portada-*"],
    "regadera":  ["regadera", "regadera-*"],
    "putiza":    ["boxeo", "boxeo-*"],
    "medallas":  ["salado", "podio", "muerto", "podio-*", "medallas-*"],
    "guerra":    ["guerra", "guerra-*"],
    "penthouse": ["elevador", "elevador-*"],
    "palpitote": ["palpitote", "palpitote-*"],
    "cierre":    ["despedida", "despedida-*"],
    "final":     ["final-*"],
    "redaccion": ["redaccion", "redaccion-*"],
}
RESPALDO = {
    "portada": ["jersey"], "regadera": ["exclusiva", "exclusiva-news"],
    "putiza": ["exclusiva-news", "exclusiva"], "medallas": ["gala", "noticiero"],
    "guerra": ["noticiero", "gala"], "penthouse": ["noticiero", "gala", "exclusiva"],
    "palpitote": ["gala", "noticiero"], "cierre": ["gala", "noticiero"],
    "final": ["jersey"], "redaccion": [],
}
ROT = {"n": 0}
FOTOS = {}


def foto_uri(nombre="jersey"):
    """Copias de 1400px en JPG: los originales metían 10 MB al PDF."""
    return FOTOS.get(nombre) or (BRAND / VESTUARIO[nombre][0]).resolve().as_uri()


def encuadre(nombre):
    """background-position CSS de una foto del vestuario ("x% y%")."""
    d = VESTUARIO.get(nombre, ("", 26))
    return f"{(tuple(d) + (50,))[2]}% {d[1]}%"


def descubrir_vestuario():
    """Toda miroslava-<nombre>.jpg de brand/ entra al vestuario aunque no esté
    en la tabla (encuadre por defecto: cara al 26% de alto, centrada)."""
    for f in sorted(BRAND.glob("miroslava-*.jpg")):
        nombre = f.stem[len("miroslava-"):]
        VESTUARIO.setdefault(nombre, (f.name, 26, 50))


def preparar_fotos(tmp):
    descubrir_vestuario()
    for nombre, (archivo, *_) in VESTUARIO.items():
        if not (BRAND / archivo).exists():
            continue
        im = Image.open(BRAND / archivo).convert("RGB")
        im.thumbnail((1400, 1400))
        out = tmp / f"m-{nombre}.jpg"
        im.save(out, quality=86, optimize=True)
        FOTOS[nombre] = out.resolve().as_uri()


def rotada(clave, rot=None):
    """Lista de fotos de la sección para ESTA semana: el pool girado por jornada
    y detrás el respaldo. Solo nombres que existen de verdad."""
    rot = ROT["n"] if rot is None else rot
    pool = []
    for pat in POOLS.get(clave, []):
        if pat.endswith("*"):
            pool += sorted(n for n in FOTOS if n.startswith(pat[:-1]))
        elif pat in FOTOS:
            pool.append(pat)
    pool = list(dict.fromkeys(pool))
    if pool:
        k = rot % len(pool)
        pool = pool[k:] + pool[:k]
    return pool + [n for n in RESPALDO.get(clave, []) if n in FOTOS and n not in pool]


def clave_de(titulo):
    t = titulo.lower()
    return next((k for k in POOLS if k in t), None)


def elegir_foto(titulo, anterior, semana=None):
    prefs = rotada(clave_de(titulo), semana) + [g for g in GENERICAS if g in FOTOS]
    return next((f for f in prefs if f != anterior), prefs[0] if prefs else None)


def primera(*nombres):
    """La primera foto de la lista que ya exista en el vestuario."""
    return next((n for n in nombres if n in FOTOS), None)


def fecha_legible(nombre):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", nombre)
    if not m:
        return date.today().isoformat()
    return f"{int(m.group(3))} {MESES[int(m.group(2)) - 1]} {m.group(1)}"


def tarjeta(cuerpo_html, jornada, fecha, pag, total, titulo=None, emoji="", sub="",
            foto=None, foto_final="jersey", zoom_min=0.8):
    cab = (f"<h1><span class='e'>{emoji}</span>{html.escape(titulo)}</h1>"
           + (f"<div class='sub'>{html.escape(sub)}</div>" if sub else "")
           + "<div class='rule'></div>") if titulo else ""
    banda = (f"<div class='banda' style=\"background-image:url('{foto_uri(foto)}');"
             f"background-position:{(VESTUARIO[foto] + (50,))[2]}% {VESTUARIO[foto][1]}%\"></div>") if foto else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_CARD.replace("ESCUDO", escudo_uri())}.relleno{{background-image:url('{foto_uri(foto_final)}');background-position:{encuadre(foto_final)}}}</style></head><body data-ultima="{int(pag == total)}" data-zmin="{zoom_min}"><div class="card{' con-foto' if foto else ''}">
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
  if (card && z < parseFloat(document.body.dataset.zmin || "0.8")) {{
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


def portadilla_html(s, foto, jornada, fecha, pag, total):
    """Tarjeta separadora de una sección larga: Miroslava a cuadro completo,
    el título grande y el aviso de cuántas tarjetas vienen. Sin texto nuevo:
    solo el título y el subtítulo de la sección."""
    x, y = PORTADILLA_X.get(foto, (VESTUARIO[foto] + (50,))[2]), VESTUARIO[foto][1]
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_CARD}
.portadilla .foto{{position:absolute;inset:0;background-size:cover;background-position:{x}% {y}%}}
.portadilla .foto::after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,
  rgba(10,20,40,.55) 0%,rgba(10,20,40,0) 22%,rgba(10,20,40,0) 48%,rgba(10,20,40,.85) 72%,#0A1428 100%)}}
.portadilla .pie-t{{position:absolute;left:60px;right:60px;bottom:150px}}
.portadilla .pie-t .e{{font-family:'Apple Color Emoji';font-size:74px}}
.portadilla .pie-t .t{{font-family:Anton,'Arial Black',sans-serif;font-size:112px;line-height:.98;
  text-transform:uppercase;text-shadow:0 6px 24px rgba(0,0,0,.6)}}
.portadilla .pie-t .s{{margin-top:14px;font-size:30px;color:#D6DDE8;font-weight:600}}
.portadilla footer{{position:absolute;left:0;right:0;bottom:0}}
</style></head><body><div class="card portadilla">
<div class="foto" style="background-image:url('{foto_uri(foto)}')"></div>
<div class="top"><img src="{escudo_uri()}"><div><div class="kick">EL DESTAPE DE <b>MIROSLAVA</b></div>
<div class="meta">{html.escape(jornada)}</div></div></div>
<div class="pie-t"><div class="e">{s['emoji']}</div><div class="t">{html.escape(s['titulo'])}</div>
<div class="s">{html.escape(cap(s['sub'])) if s['sub'] else ''}</div></div>
<footer><span>💋 Miroslava</span><span>{pag} / {total}</span><span>{fecha}</span></footer>
</div></body></html>"""


def portada_html(portada_lineas, secciones, jornada, fecha, total, foto="jersey"):
    cuerpo = html_bloques(bloques(portada_lineas), "card")
    indice = "".join(f"<span><b>{s['emoji']}</b>{html.escape(cap(s['titulo'].split(' — ')[0].lower()).replace('miroslava', 'Miroslava'))}</span>"
                     for s in secciones)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FUENTES}
<style>{CSS_CARD}</style></head><body><div class="card cover">
<div class="foto" style="background-image:url('{foto_uri(foto)}');background-position:{encuadre(foto)}"></div>
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


FUENTES_PERIODICO = ('<link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&'
                     'family=Playfair+Display:ital,wght@0,700;0,900;1,400;1,700&'
                     'family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">')
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_L = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"]

CSS_PERIODICO = """
@page{size:11in ALTOin;margin:.55in .6in}
*{box-sizing:border-box}
html{background:#F3EEE2}
body{margin:0;background:#F3EEE2;color:#161412;font-family:'Libre Baskerville',Georgia,serif;
  font-size:10.3pt;line-height:1.46;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.mast{text-align:center;border-bottom:4px double #161412;padding-bottom:6px;margin-bottom:10px}
.mast-top{display:flex;align-items:center;justify-content:space-between;gap:18px}
.oreja{width:2.05in;border:1.5px solid #161412;padding:7px 9px;font-size:8.2pt;line-height:1.35;
  text-align:left;font-family:'Playfair Display',serif}
.oreja.der{text-align:right}
.oreja img{height:.62in;float:left;margin-right:8px}
.oreja b{font-weight:900;color:#B3121B;text-transform:uppercase;letter-spacing:.5pt}
.mast-top>div:nth-child(2){flex:1}
.nombre{white-space:nowrap;font-family:'UnifrakturMaguntia','Old English Text MT',serif;font-weight:400;font-size:84pt;
  line-height:.95;margin:0;letter-spacing:.5pt}
.de{font-family:'Playfair Display',serif;font-style:italic;font-size:17pt;margin-top:-4px}
.de b{color:#B3121B;font-style:normal;font-weight:900;letter-spacing:2pt;text-transform:uppercase}
.fechas{display:flex;justify-content:space-between;border-top:1.5px solid #161412;
  border-bottom:1.5px solid #161412;margin-top:8px;padding:4px 2px;font-family:'Playfair Display',serif;
  font-size:8.6pt;text-transform:uppercase;letter-spacing:1.4pt;font-weight:700}
.primera{display:grid;grid-template-columns:2.3in 1fr;gap:0 18px;border-bottom:1.5px solid #161412;
  padding-bottom:12px;margin-bottom:12px}
.nota{border-right:1px solid #161412;padding-right:16px}
.nota p{text-align:left;hyphens:auto}
.nota .kick,.art .kick,.lead .kick{font-family:'Playfair Display',serif;font-weight:900;font-size:8.4pt;
  letter-spacing:1.6pt;text-transform:uppercase;color:#B3121B;margin-bottom:3px;break-after:avoid}
.nota .foto{width:100%;height:2.3in;background-size:cover;background-position:46% 20%;
  filter:grayscale(.15) contrast(1.05);margin:4px 0 3px}
.pie{font-size:7.4pt;font-style:italic;color:#4A4640;margin-bottom:8px;line-height:1.3}
.lead h2{font-family:'Playfair Display',serif;font-weight:900;font-size:40pt;line-height:1.02;
  margin:0 0 6px;letter-spacing:-.5pt}
.lead .dek{font-family:'Playfair Display',serif;font-style:italic;font-size:14pt;margin:0 0 8px;color:#3A3631}
.lead .foto{height:3.7in;background-size:cover;background-position:50% 24%;margin:4px 0 3px}
.lead .texto{column-count:2;column-gap:18px;column-rule:1px solid #9C958A;text-align:justify;
  hyphens:auto;font-size:11pt}
.columnas{column-count:3;column-gap:20px;column-rule:1px solid #9C958A}
.art{break-inside:auto;margin:0 0 14px;padding-bottom:10px;border-bottom:1px solid #161412}
.art h3{font-family:'Playfair Display',serif;font-weight:900;font-size:19pt;line-height:1.05;
  margin:0 0 4px;break-after:avoid}
.art .dek{font-family:'Playfair Display',serif;font-style:italic;font-size:9.6pt;color:#4A4640;
  margin:0 0 6px;break-after:avoid}
.art .foto{height:2.2in;background-size:cover;background-position:50% 24%;margin:4px 0 3px;
  break-inside:avoid}
p{margin:0 0 6px;text-align:justify;hyphens:auto}
strong{font-weight:700}
.e{font-family:'Apple Color Emoji';font-style:normal}
.bullets{list-style:none;margin:0 0 6px;padding:0}
.bullets li{padding:0 0 6px 13px;position:relative;text-align:justify;hyphens:auto;break-inside:avoid}
.bullets li::before{content:"■";position:absolute;left:0;top:0;color:#B3121B;font-size:7pt}
.medalla{display:block;margin:0 0 7px;break-inside:avoid;text-align:justify;hyphens:auto}
.medalla>div{display:inline}
.med-emo{font-family:'Apple Color Emoji';margin-right:4px}
.med-etq{font-family:'Playfair Display',serif;font-weight:900;text-transform:uppercase;
  letter-spacing:.8pt;font-size:9.4pt;display:inline}
.med-etq::after{content:". "}
.med-txt,.med-txt *{display:inline}
.score{display:flex;justify-content:space-between;gap:10px;font-family:'Playfair Display',serif;
  font-weight:900;font-size:13pt;border-top:2px solid #161412;border-bottom:2px solid #161412;
  padding:4px 0;margin:2px 0 8px;break-inside:avoid}
.sc-eq{display:flex;gap:8px;align-items:baseline}
.sc-eq.gana b{color:#B3121B}
.duelo{margin:0 0 7px;break-inside:avoid;text-align:justify}
.du-vs{font-family:'Playfair Display',serif;font-weight:900;font-size:10.4pt;display:inline}
.du-vs i{font-style:italic;font-weight:400;color:#B3121B;margin:0 3px}
.duelo>div:last-child{display:inline;margin-left:4px}
.rank{display:grid;grid-template-columns:22px 1fr;gap:0 6px;padding:4px 0;border-bottom:1px dotted #9C958A;
  break-inside:avoid}
.rk-n{font-family:'Playfair Display',serif;font-weight:900;font-size:14pt;color:#B3121B;line-height:1.1}
.rk-top{font-size:9.6pt}
.rk-eq{font-weight:700}
.rk-rec{font-size:7.8pt;color:#4A4640;margin-left:4px}
.rk-txt{font-size:9.4pt;text-align:justify;hyphens:auto}
.tag{font-family:'Playfair Display',serif;font-size:6.8pt;font-weight:900;text-transform:uppercase;
  letter-spacing:.8pt;padding:0 4px;border:1px solid currentColor;margin-right:4px}
.tag.caballo{color:#1F6F43}.tag.decep{color:#B3121B}.tag.salado{color:#4A5A73}.tag.mojon{color:#6B4423}.tag.malcoach{color:#B4511E}
table.guerra{width:100%;border-collapse:collapse;font-size:9.6pt;margin:2px 0 8px;break-inside:avoid}
table.guerra th{font-family:'Playfair Display',serif;text-transform:uppercase;font-size:7.6pt;
  letter-spacing:1pt;text-align:left;border-bottom:1.5px solid #161412;padding:2px 3px}
table.guerra td{padding:4px 3px;border-bottom:1px dotted #9C958A;font-weight:700}
table.guerra td.num{text-align:right;font-variant-numeric:tabular-nums}
table.guerra tr.lider td{background:#E4DCCB}
.firma{text-align:right;font-style:italic}
.par-fotos{display:flex;gap:6px;break-inside:avoid;margin-top:6px}
.par-fotos .foto{flex:1;height:1.5in;background-size:cover;background-position:50% 24%}
.cierre-foto{height:1.9in;background-size:cover;background-position:46% 22%;margin:6px 0 3px}
.colofon{column-span:all;text-align:center;font-family:'Playfair Display',serif;font-size:8pt;
  letter-spacing:1.4pt;text-transform:uppercase;border-top:4px double #161412;padding-top:5px;margin-top:6px}
"""

FOTO_PERIODICO = {"regadera": ("regadera", "exclusiva"), "medallas": ("podio", "gala"),
                  "guerra": ("guerra", "noticiero"), "penthouse": ("elevador",),
                  "palpitote": ("palpitote",)}


def fecha_larga(nombre):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", nombre)
    if not m:
        return ""
    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return f"{DIAS[d.weekday()]} {d.day} de {MESES_L[d.month - 1]} de {d.year}"


def pdf_html(portada_lineas, secciones, jornada, fecha, foto="jersey", nombre="", alto=17):
    """El PDF como PERIÓDICO (user 2026-09-29): cabezal gótico, fechario,
    nota de la redacción + nota principal a dos columnas en primera plana, y el
    resto de la edición a tres columnas con fotos de Miroslava como fotoperiodismo.
    El texto es el mismo del .txt; solo se agrega la 'tripa' del diario (cabezal,
    fechario, pies de foto sin chiste)."""
    liga = jornada.split("—")[-1].strip() or "La Gallamijos"
    num = re.search(r"(\d+)", jornada)
    num = num.group(1) if num else "—"
    # Nota principal: la Putiza (el marcador es el titular natural).
    lead = next((s for s in secciones if "putiza" in s["titulo"].lower()), secciones[0])
    lb = bloques(lead["lineas"])
    marc = next((b[1] for b in lb if b[0] == "marcador"), None)
    if marc:
        a, pa, b_, pb, txt = marc
        titular = f"{html.escape(a)} {pa}, {html.escape(b_)} {pb}"
        resto = [("parrafo", txt)] + [x for x in lb if x[0] != "marcador"]
    else:
        titular = html.escape(lead["titulo"].capitalize())
        resto = lb
    lead_html = f"""<div class="lead"><div class="kick"><span class="e">{lead['emoji']}</span> {html.escape(lead['titulo'])}</div>
<h2>{titular}</h2>
<div class="foto" style="background-image:url('{foto_uri((rotada('putiza') or [foto])[0])}')"></div>
<div class="pie">Miroslava, en el lugar de los hechos. Foto: El Destape.</div>
<div class="texto">{html_bloques(resto, "pdf")}</div></div>"""
    arts = []
    for s in secciones:
        if s is lead:
            continue
        t = s["titulo"].lower()
        clave = next((k for k in FOTO_PERIODICO if k in t), None)
        fotohtml = ""
        elegida = primera(*FOTO_PERIODICO[clave]) if clave else None
        if elegida:
            fotohtml = (f"<div class='foto' style=\"background-image:url('{foto_uri(elegida)}')\"></div>"
                        "<div class='pie'>Miroslava. Foto: El Destape.</div>")
        cuerpo = html_bloques(bloques(s["lineas"]), "pdf")
        if "medallas" in t and primera("salado", "muerto"):
            # El Salado y El Muerto, como fotos a dos columnas bajo las medallas.
            pares = "".join(f"<div class='foto' style=\"background-image:url('{foto_uri(n)}')\"></div>"
                            for n in ("salado", "muerto") if n in FOTOS)
            cuerpo += f"<div class='par-fotos'>{pares}</div><div class='pie'>Miroslava. Foto: El Destape.</div>"
        if "cierre" in t:
            cuerpo += f"<div class='cierre-foto' style=\"background-image:url('{foto_uri((rotada('cierre') or [foto])[0])}')\"></div>"
        arts.append(f"<div class='art'><div class='kick'><span class='e'>{s['emoji']}</span> "
                    f"{html.escape(s['titulo'].split(' — ')[0])}</div>"
                    f"<h3>{html.escape(cap(s['titulo'].lower()).replace('miroslava', 'Miroslava'))}</h3>"
                    + (f"<div class='dek'>{html.escape(cap(s['sub']))}</div>" if s["sub"] else "")
                    + fotohtml + cuerpo + "</div>")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{FUENTES_PERIODICO}
<style>{CSS_PERIODICO.replace('ALTO', str(alto))}</style></head><body>
<header class="mast"><div class="mast-top">
<div class="oreja"><img src="{escudo_uri()}"><b>Órgano oficial de chisme</b><br>de {html.escape(liga)}<br>Fundado en 2015</div>
<div><div class="nombre">El Destape</div><div class="de">de <b>Miroslava</b></div></div>
<div class="oreja der"><b>Jornada {num}</b><br>Ejemplar de cortesía<br>Circula en WhatsApp</div></div>
<div class="fechas"><span>Año 1 · Número {num}</span><span>{fecha_larga(nombre)}</span><span>{html.escape(liga)}</span></div>
</header>
<section class="primera"><div class="nota"><div class="kick">Nota de la redacción</div>
<div class="foto" style="background-image:url('{foto_uri((rotada('redaccion') or [foto])[0])}')"></div>
<div class="pie">Nuestra corresponsal, en funciones.</div>
{html_bloques(bloques(portada_lineas), "pdf")}</div>
{lead_html}</section>
<div class="columnas">{"".join(arts)}
<div class="colofon">El Destape de Miroslava · {html.escape(liga)} · {fecha} · Edición digital</div></div>
</body></html>"""


# ───────────────────────────── render ─────────────────────────────

def chrome(args, perfil, salida, intentos=3):
    """Chrome headless a veces no arranca a la primera en este Mac (falla
    intermitente, sin patrón): se reintenta antes de abortar la edición."""
    for n in range(intentos):
        try:
            return _chrome(args, perfil, salida)
        except SystemExit as e:
            if n == intentos - 1:
                raise
            print(f"  ↻ Chrome falló ({str(e)[:60]}…), reintento {n + 2}/{intentos}")


def _chrome(args, perfil, salida):
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
        for _ in range(120):                       # hasta 60 s por intento
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


def llenado_ultima_pagina(pdf):
    """Qué fracción de la última página tiene tinta (0-1), vía pdftoppm."""
    if not shutil.which("pdftoppm"):
        return None, None
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    paginas = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    base = pdf.with_suffix("")
    subprocess.run(["pdftoppm", "-r", "30", "-png", "-f", str(paginas), "-l", str(paginas),
                    str(pdf), str(base) + "-ult"], check=True)
    png = next(pdf.parent.glob(base.name + "-ult*.png"))
    im = Image.open(png).convert("L")
    png.unlink()
    w, h = im.size
    fondo = im.getpixel((w // 2, h - 2))
    ultima_fila = max((y for y in range(h) if any(abs(im.getpixel((x, y)) - fondo) > 25
                                                  for x in range(0, w, 3))), default=0)
    return paginas, ultima_fila / h


def imprimir_periodico(pdf, armar_html, tmp, perfil):
    """Un periódico no deja media plana en blanco: se imprime a tabloide
    (11x17), se mide cuánto llenó la última página y se reimprime con el alto
    justo para que las páginas salgan llenas (entre 12 y 17 pulgadas)."""
    def imprimir(alto):
        src = tmp / "periodico.html"
        src.write_text(armar_html(alto))
        if pdf.exists():
            pdf.unlink()
        chrome(["--no-pdf-header-footer", f"--print-to-pdf={pdf}", src.as_uri()], perfil, pdf)
    imprimir(17)
    paginas, frac = llenado_ultima_pagina(pdf)
    if paginas and paginas > 1 and frac < 0.8:
        util = 17 - 1.1                                     # alto útil sin márgenes
        total = (paginas - 1 + frac) * util
        alto = min(17, max(12, total / paginas * 1.04 + 1.1))
        imprimir(round(alto, 2))


def ordenar_para_whatsapp(destino, nombre):
    """WhatsApp manda un álbum en el orden en que se TOCAN las fotos, y la
    galería del teléfono las ordena por FECHA DE CAPTURA, no por nombre. Así
    que cada tarjeta lleva una fecha EXIF un segundo después de la anterior
    (y el mismo orden en la fecha del archivo): guardadas en Fotos quedan
    1→N en fila, y se seleccionan de corrido. Además se arma un PDF con las
    tarjetas en orden: un solo archivo que se manda de un toque."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", nombre)
    base = (time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 8, 0, 0, 0, 0, -1))
            if m else time.time())
    tarjetas = sorted(destino.glob("[0-9][0-9]-*.jpg"))
    for k, f in enumerate(tarjetas):
        t = base + k
        im = Image.open(f)
        exif = im.getexif()
        sello = time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(t))
        exif[0x0132] = sello                                   # DateTime
        exif.get_ifd(0x8769)[0x9003] = sello                   # DateTimeOriginal
        exif.get_ifd(0x8769)[0x9004] = sello                   # DateTimeDigitized
        im.save(f, quality=90, optimize=True, progressive=True, exif=exif)
        os.utime(f, (t, t))
    if tarjetas:
        pags = [Image.open(f).convert("RGB") for f in tarjetas]
        pdf = destino / f"{nombre}-carrusel.pdf"
        pags[0].save(pdf, save_all=True, append_images=pags[1:], resolution=144)
        print(f"  {pdf.relative_to(ROOT)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    edicion = Path(args[0]).resolve()
    jornada, portada, secciones = leer(edicion)
    semana = int((re.search(r"(\d+)", jornada) or re.search("0", "0")).group(0))
    if not secciones:
        sys.exit("No encontré secciones (líneas tipo '🥊 *TÍTULO*').")
    fecha = fecha_legible(edicion.stem)
    temporada = edicion.stem[:4]
    destino = ROOT / "reports" / temporada / "roast" / "visual" / edicion.stem
    if destino.exists() and "--solo-pdf" not in sys.argv:
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)

    # Plan de tarjetas: portada + una por sección; el ranking se parte.
    plan = []
    for s in secciones:
        bs = bloques(s["lineas"])
        ranks = [b for b in bs if b[0] == "rank"]
        if len(ranks) > POR_TARJETA_RANKING:
            resto = [b for b in bs if b[0] != "rank"]
            trozos = [ranks[i:i + POR_TARJETA_RANKING]
                      for i in range(0, len(ranks), POR_TARJETA_RANKING)]
            # Sección larga: abre con una PORTADILLA a foto completa (su
            # Miroslava de vestuario) y las tarjetas de datos van sin foto,
            # que la letra del ranking no se encoja.
            plan.append((s, None, s["sub"], "portadilla"))
            for k, tr in enumerate(trozos):
                sub = (s["sub"] + " · " if s["sub"] else "") + f"{tr[0][1][0]}–{tr[-1][1][0]}"
                # Solo la primera tarjeta de una sección partida lleva foto:
                # en las de continuación el espacio es para la letra.
                plan.append((s, tr + (resto if k == len(trozos) - 1 else []), sub, False))
        else:
            plan.append((s, bs, s["sub"], True))
    total = len(plan) + 1

    with tempfile.TemporaryDirectory() as t:
        tmp, perfil = Path(t), Path(t) / "perfil"
        preparar_fotos(tmp)
        # Diciembre = playoffs del fantasy: portada y despedida con suéter navideño.
        # Las dos ligas comparten lectores: la Dinastía va un paso adelante en
        # la rotación para no repetir fotos el mismo martes.
        rot = semana + (1 if "dinast" in jornada.lower() else 0)
        ROT["n"] = rot
        diciembre = edicion.stem[5:7] == "12" and "navidad" in FOTOS
        principal = "navidad" if diciembre else (rotada("portada") or ["jersey"])[0]
        final = "navidad" if diciembre else next(
            (f for f in rotada("final") if f != principal), principal)
        if "--solo-pdf" not in sys.argv:
            out = destino / "01-portada.jpg"
            captura(portada_html(portada, secciones, jornada, fecha, total, principal), out, tmp, perfil)
            anterior = principal
            print(f"  {out.relative_to(ROOT)}")
            for i, (s, bs, sub, con_foto) in enumerate(plan, start=2):
                slug = re.sub(r"[^a-z0-9]+", "-", s["titulo"].lower().split(" — ")[0]
                              .translate(str.maketrans("áéíóúñ", "aeioun"))).strip("-")[:28]
                out = destino / f"{i:02d}-{slug}.jpg"
                foto = elegir_foto(s["titulo"], anterior, rot) if con_foto else None
                anterior = foto or anterior
                if con_foto == "portadilla":
                    out = out.with_name(out.stem + "-portadilla.jpg")
                    html_t = portadilla_html(s, foto, jornada, fecha, i, total)
                else:
                    # Medallas SIEMPRE lleva su foto de la semana: aguanta
                    # más zoom antes de soltarla (lo pidió el user).
                    html_t = tarjeta(html_bloques(bs, "card"), jornada, fecha, i, total,
                                     s["titulo"], s["emoji"], sub, foto, final,
                                     0.62 if "medallas" in s["titulo"].lower() else 0.8)
                captura(html_t, out, tmp, perfil)
                print(f"  {out.relative_to(ROOT)}")
            ordenar_para_whatsapp(destino, edicion.stem)
        if "--solo-tarjetas" not in sys.argv:
            pdf = destino / f"{edicion.stem}.pdf"
            imprimir_periodico(pdf, lambda alto: pdf_html(portada, secciones, jornada, fecha,
                                                          principal, edicion.stem, alto), tmp, perfil)
            print(f"  {pdf.relative_to(ROOT)}")
    print(f"[visual] {destino.relative_to(ROOT)} listo")


if __name__ == "__main__":
    main()
