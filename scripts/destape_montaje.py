#!/usr/bin/env python3
"""Paso 4 del pipeline de video del Destape: montaje de marca con ffmpeg.

Toma el mp4 crudo de HeyGen Avatar 4 (que llega letterboxed: banda 16:9 con
barras blancas dentro de un lienzo 9:16) y produce el video final 1080x1920:

  intro (3s: escudo + título) → cuerpo (banda recortada y reescalada sobre
  lienzo de marca, escudo arriba, barra roja, pie) → outro ("Los observo.")

Sin drawtext (el ffmpeg de brew no trae libfreetype): los textos se generan
como SVG y se rasterizan con `sips`, que sí usa las fuentes del sistema.
La banda de contenido se detecta con negate+cropdetect (las barras son
blancas; cropdetect pelón solo ve bordes negros).

Uso: python3 scripts/destape_montaje.py <heygen.mp4> <salida.mp4>
         [--subtitulo "Edición post-draft · La Gallamijos"]
         [--escaleta cues.json]

La ESCALETA hace el video "de noticiero": un cintillo rojo que nombra la
sección en curso y una zona de datos bajo el video (estadística + emoji de
lo que Miroslava está diciendo). Formato del JSON: lista de
  {"t0": seg, "t1": seg, "tipo": "seccion"|"dato",
   "grande": "…", "chico": "…"}   (tiempos relativos al CUERPO del video)
Los tiempos los estima el pase editorial semanal por proporción de palabras
del guion — ver la escaleta del piloto como ejemplo.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ESCUDO_SVG = ROOT / "data" / "intel" / "brand" / "gallamijos-escudo.svg"
NAVY, ROJO, GRIS, GRISOSC = "#0A1428", "#D50A0A", "#AFBBD0", "#5B6B85"
FF = 'font-family="Arial Black, Arial" font-weight="900"'
FR = 'font-family="Arial" font-weight="bold"'
ENC = ("-c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -r 25 "
       "-c:a aac -b:a 128k -ar 48000 -ac 2").split()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FALLÓ: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r


def rasterizar(svg, png, alto=None):
    cmd = ["sips", "-s", "format", "png"]
    if alto:
        cmd += ["-Z", str(alto)]
    run(cmd + [str(svg), "--out", str(png)])


def texto_png(tmp, nombre, cuerpo):
    svg = tmp / f"{nombre}.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">'
                   + cuerpo + "</svg>")
    png = tmp / f"{nombre}.png"
    rasterizar(svg, png)
    return png


def detectar_banda(video):
    r = subprocess.run(["ffmpeg", "-ss", "30", "-t", "4", "-i", str(video), "-vf",
                        "negate,cropdetect=limit=24:round=2", "-f", "null", "-"],
                       capture_output=True, text=True)
    votos = {}
    for m in re.finditer(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr):
        votos[m.group(0)] = votos.get(m.group(0), 0) + 1
    if not votos:
        sys.exit("No pude detectar la banda de contenido (¿video sin barras?)")
    return max(votos, key=votos.get).split("=")[1]


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ancho(base, texto, tope):
    """Tamaño de fuente que cabe en ~980px (Arial Black ≈ 0.75em/char)."""
    return min(tope, max(34, int(1306 / max(1, len(texto)))))


def cue_pngs(tmp, cues):
    """Un PNG 1080x1920 transparente por cue, para overlay con enable."""
    out = []
    for i, c in enumerate(cues):
        g, ch = _esc(c.get("grande", "")), _esc(c.get("chico", ""))
        if c["tipo"] == "seccion":
            fs = _ancho(46, c.get("grande", ""), 46)
            cuerpo = (f'<rect x="0" y="575" width="1080" height="76" fill="{ROJO}"/>'
                      f'<text x="540" y="628" text-anchor="middle" {FF} '
                      f'font-size="{fs}" fill="#FFF">{g}</text>')
        else:
            fs = _ancho(68, c.get("grande", ""), 68)
            cuerpo = (f'<text x="540" y="1500" text-anchor="middle" {FF} '
                      f'font-size="{fs}" fill="#FFF">{g}</text>')
            if ch:
                cuerpo += (f'<text x="540" y="1600" text-anchor="middle" {FR} '
                           f'font-size="42" fill="{GRIS}">{ch}</text>')
        out.append(texto_png(tmp, f"cue{i}", cuerpo))
    return out


def main():
    argv = sys.argv[1:]
    sub = "El Destape · La Gallamijos"
    escaleta = None
    if "--escaleta" in argv:
        i = argv.index("--escaleta")
        escaleta = json.load(open(argv[i + 1]))
        del argv[i:i + 2]
    if "--subtitulo" in argv:
        i = argv.index("--subtitulo")
        sub = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 2:
        sys.exit(__doc__)
    video, salida = Path(argv[0]), Path(argv[1])
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(video)]).stdout.strip())
    crop = detectar_banda(video)
    print(f"[montaje] banda {crop}, duración {dur:.1f}s")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        escudo = tmp / "escudo.png"
        rasterizar(ESCUDO_SVG, escudo, 1440)

        t_intro = texto_png(tmp, "intro", f'''
<text x="540" y="1330" text-anchor="middle" {FF} font-size="104" fill="#FFF">EL DESTAPE</text>
<text x="540" y="1460" text-anchor="middle" {FF} font-size="104" fill="{ROJO}">DE MIROSLAVA</text>
<text x="540" y="1590" text-anchor="middle" {FR} font-size="42" fill="{GRIS}">{sub}</text>''')
        sub_estatico = "" if escaleta else (f'<text x="540" y="640" text-anchor="middle" '
                                            f'{FR} font-size="38" fill="{GRIS}">{_esc(sub)}</text>')
        t_body = texto_png(tmp, "body", f'''
<text x="540" y="545" text-anchor="middle" {FF} font-size="58" fill="#FFF">EL DESTAPE DE MIROSLAVA</text>
{sub_estatico}
<rect x="0" y="1290" width="1080" height="8" fill="{ROJO}"/>
<text x="540" y="1790" text-anchor="middle" {FR} font-size="34" fill="{GRISOSC}">GALLAMIJOS · EST. 2015</text>''')
        cues_png = cue_pngs(tmp, escaleta) if escaleta else []
        t_outro = texto_png(tmp, "outro", f'''
<text x="540" y="1200" text-anchor="middle" {FF} font-size="96" fill="#FFF">Los observo.</text>
<text x="540" y="1350" text-anchor="middle" {FR} font-size="48" fill="{ROJO}">— Miroslava</text>''')

        base = f"color=c=0x{NAVY[1:]}:s=1080x1920:r=25"
        segs = []
        for n, (d, ins, fc) in enumerate([
            (3, ["-f", "lavfi", "-i", f"{base}:d=3", "-f", "lavfi", "-t", "3", "-i",
                 "anullsrc=r=48000:cl=stereo", "-i", str(escudo), "-i", str(t_intro)],
             "[2:v]scale=-1:760[e];[0:v][e]overlay=(W-w)/2:330[v1];[v1][3:v]overlay,"
             "fade=t=in:st=0:d=0.5,fade=t=out:st=2.5:d=0.5[v]"),
            (dur, ["-i", str(video), "-i", str(escudo), "-i", str(t_body),
                   *sum([["-i", str(p)] for p in cues_png], [])],
             f"{base}:d={dur}[bg];[1:v]scale=-1:300[e];"
             f"[0:v]crop={crop},scale=1080:600:flags=lanczos[band];"
             "[bg][e]overlay=(W-w)/2:130[b1];[b1][band]overlay=0:690[b2];"
             "[b2][2:v]overlay[c0];" + "".join(
                 f"[c{j}][{3 + j}:v]overlay=0:0:enable='between(t,{c['t0']},{c['t1']})'[c{j + 1}];"
                 for j, c in enumerate(escaleta or [])) +
             f"[c{len(escaleta or [])}]fade=t=in:st=0:d=0.3[v]"),
            (3.5, ["-f", "lavfi", "-i", f"{base}:d=3.5", "-f", "lavfi", "-t", "3.5",
                   "-i", "anullsrc=r=48000:cl=stereo", "-i", str(escudo), "-i", str(t_outro)],
             "[2:v]scale=-1:520[e];[0:v][e]overlay=(W-w)/2:400[v1];[v1][3:v]overlay,"
             "fade=t=in:st=0:d=0.4,fade=t=out:st=3:d=0.5[v]"),
        ]):
            seg = tmp / f"seg{n}.mp4"
            amap = "0:a" if n == 1 else "1:a"
            run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc,
                 "-map", "[v]", "-map", amap, *ENC, str(seg)])
            segs.append(seg)

        lista = tmp / "lista.txt"
        lista.write_text("".join(f"file '{s}'\n" for s in segs))
        salida.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(lista), "-c", "copy", str(salida)])
    mb = salida.stat().st_size / 1e6
    print(f"[montaje] {salida} listo ({mb:.1f} MB, {dur + 6.5:.0f}s)")


if __name__ == "__main__":
    main()
