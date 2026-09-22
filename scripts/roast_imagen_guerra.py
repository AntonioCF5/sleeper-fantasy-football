#!/usr/bin/env python3
"""Imagen compartible del MARCADOR DE LA GUERRA, con Miroslava presente.

Lee el marcador ya calculado por roast_facts.py (nunca lo recalcula a mano)
y compone un 1080x1350 de marca: escudo + título + tabla grande + una banda
con Miroslava + pie de edición. Mismo motor que el montaje de video: los
textos se rasterizan de SVG con `sips` (el ffmpeg de brew no trae drawtext)
y ffmpeg compone las capas.

Uso: python3 scripts/roast_imagen_guerra.py <liga> [--fecha YYYY-MM-DD]
                                            [--foto jersey|ref]
  liga: gallamijos | dynasty
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "data" / "intel" / "brand"
NAVY, ROJO, GRIS, BLANCO = "#0A1428", "#D50A0A", "#AFBBD0", "#FFFFFF"
FF = 'font-family="Arial Black, Arial" font-weight="900"'
FR = 'font-family="Arial" font-weight="bold"'
MONO = 'font-family="Menlo, Courier New, monospace" font-weight="bold"'
W, H = 1080, 1080   # cuadrado: el formato que mejor se ve en WhatsApp


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FALLÓ: {' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r


def rasterizar(svg_text, out, alto=None):
    svg = out.with_suffix(".svg")
    svg.write_text(svg_text)
    cmd = ["sips", "-s", "format", "png"] + (["-Z", str(alto)] if alto else [])
    run(cmd + [str(svg), "--out", str(out)])


def leer_marcador(liga, fecha):
    """Extrae bandos y récords de la hoja de hechos (fuente única)."""
    hojas = sorted(ROOT.glob(f"reports/*/roast/facts-{liga}-{fecha or '*'}.md"))
    if not hojas:
        sys.exit(f"No hay hoja de hechos para {liga} {fecha or ''} — corre roast_facts.py")
    txt = hojas[-1].read_text()
    m = re.search(r"### Tabla para WhatsApp.*?```\n(.*?)```", txt, re.S)
    if not m:
        sys.exit("La hoja no trae la tabla de WhatsApp — regenera con roast_facts.py")
    filas = []
    for linea in m.group(1).strip().split("\n")[2:]:
        mm = re.match(r"(.+?)\s+(\d+) -\s*(\d+)\s+\.?(\d+)", linea.strip())
        if mm:
            filas.append((mm.group(1).strip(), int(mm.group(2)), int(mm.group(3))))
    sem = re.search(r"## ADDENDUM — lineups verificados de la semana (\d+)", txt)
    return filas, (sem.group(1) if sem else "?"), hojas[-1].name[-13:-3]


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(argv) != 1 or argv[0] not in ("gallamijos", "dynasty"):
        sys.exit(__doc__)
    liga = argv[0]
    fecha = sys.argv[sys.argv.index("--fecha") + 1] if "--fecha" in sys.argv else None
    foto = sys.argv[sys.argv.index("--foto") + 1] if "--foto" in sys.argv else "jersey"
    filas, semana, dia = leer_marcador(liga, fecha)
    titulo = "LA GALLAMIJOS" if liga == "gallamijos" else "LA DINASTÍA"

    tmp = ROOT / "data" / "cache" / "_guerra"
    tmp.mkdir(parents=True, exist_ok=True)
    escudo = tmp / "escudo.png"
    rasterizar((BRAND / "gallamijos-escudo.svg").read_text(), escudo, 1440)

    # Capa de texto: título, tabla y pie. La tabla se dibuja con columnas
    # posicionadas (no monoespaciado) para que se vea de póster, no de consola.
    # Layout vertical medido para que NADA se solape: banda de foto 0-300,
    # bloque de título 380-505, encabezados 578, filas desde 660.
    y0 = 660
    filas_svg = []
    # Empate en la cima: la corona va a TODOS los que comparten el mejor
    # porcentaje, no al primero de la lista (error 2026-09-22: Gallaghers y
    # Mijos iban 6-4 y la imagen coronaba solo a los Gallaghers).
    pcts = [g / max(1, g + p) for _, g, p in filas]
    mejor, peor = max(pcts), min(pcts)
    lideres = [i for i, x in enumerate(pcts) if x == mejor]
    # 💩 para el último — y para TODOS si comparten el peor porcentaje, por la
    # misma razón que la corona (un empate abajo tampoco tiene un solo dueño).
    # Si hay un solo bando, o todos empatados, nadie es el último: sin popó.
    sotano = ([i for i, x in enumerate(pcts) if x == peor]
              if mejor != peor else [])
    for i, (bando, g, p) in enumerate(filas):
        y = y0 + i * 118
        pct = pcts[i]
        es_lider, es_sotano = i in lideres, i in sotano
        color = BLANCO if es_lider else GRIS
        medalla = "👑 " if es_lider else ("💩 " if es_sotano else "")
        filas_svg.append(
            f'<rect x="70" y="{y - 62}" width="940" height="96" rx="14" '
            f'fill="{"#16294A" if es_lider else ("#2A1418" if es_sotano else "#0E1A30")}"/>'
            f'<text x="105" y="{y}" {FF} font-size="52" fill="{color}">{medalla}{bando}</text>'
            f'<text x="800" y="{y}" text-anchor="middle" {FF} font-size="52" '
            f'fill="{BLANCO}">{g} - {p}</text>'
            f'<text x="960" y="{y}" text-anchor="middle" {FR} font-size="40" '
            f'fill="{ROJO if es_lider else GRIS}">.{int(round(pct * 1000)):03d}</text>')

    # Dato destacado: el contraste que cuenta la historia de la semana.
    # Respeta el empate — "lideran" en singular sería falso con dos arriba.
    ultimo = filas[-1]
    if len(lideres) > 1:
        nombres = " y ".join(filas[i][0] for i in lideres)
        cab = f"{nombres} empatados arriba con {filas[lideres[0]][1]}-{filas[lideres[0]][2]}"
    else:
        l = filas[lideres[0]]
        cab = f"{l[0]} lideran con {l[1]}-{l[2]}"
    remate = f"{cab}; {ultimo[0]}, {ultimo[1]}-{ultimo[2]}"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">
<text x="540" y="392" text-anchor="middle" {FF} font-size="74" fill="{BLANCO}">MARCADOR</text>
<text x="540" y="470" text-anchor="middle" {FF} font-size="74" fill="{ROJO}">DE LA GUERRA</text>
<text x="540" y="524" text-anchor="middle" {FR} font-size="32" fill="{GRIS}">{titulo} · TRAS LA JORNADA {semana}</text>
<text x="105" y="588" {FR} font-size="28" fill="{GRIS}">BANDO</text>
<text x="800" y="588" text-anchor="middle" {FR} font-size="28" fill="{GRIS}">G - P</text>
<text x="960" y="588" text-anchor="middle" {FR} font-size="28" fill="{GRIS}">%</text>
{"".join(filas_svg)}
<text x="540" y="1012" text-anchor="middle" {FR} font-size="31" fill="{GRIS}">{remate}</text>
<rect x="0" y="{H - 54}" width="{W}" height="5" fill="{ROJO}"/>
<text x="540" y="{H - 16}" text-anchor="middle" {FR} font-size="27" fill="#5B6B85">EL DESTAPE DE MIROSLAVA · {dia}</text>
</svg>'''
    capa = tmp / "capa.png"
    rasterizar(svg, capa)

    retrato = BRAND / (f"miroslava-{foto}.png" if foto != "ref" else "miroslava-ref.png")
    salida = ROOT / "reports" / "2026" / "roast" / "img" / f"guerra-{liga}-{dia}.png"
    salida.parent.mkdir(parents=True, exist_ok=True)
    # Banda con Miroslava arriba (recorte centrado en ella) + capa de texto.
    run(["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=0x{NAVY[1:]}:s={W}x{H}",
         "-i", str(retrato), "-i", str(escudo), "-i", str(capa),
         "-filter_complex",
         "[1:v]crop=in_w:in_h*0.56:0:0,scale=1080:-1,crop=1080:300:0:0[band];"
         "[0:v][band]overlay=0:0[a];"
         "[a]drawbox=x=0:y=294:w=1080:h=7:color=0x" + ROJO[1:] + ":t=fill[b];"
         "[2:v]scale=-1:140[e];[b][e]overlay=W-w-46:54[c];"
         "[c][3:v]overlay=0:0,format=rgb24[v]",
         "-map", "[v]", "-frames:v", "1", str(salida)])
    print(f"[guerra] {salida.relative_to(ROOT)} listo")


if __name__ == "__main__":
    main()
