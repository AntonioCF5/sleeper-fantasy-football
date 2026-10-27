#!/usr/bin/env python3
"""Texto de la CINTA de marcadores para el video del Destape (modo --vertical
de destape_montaje.py), leído de la hoja de hechos — nunca escrito a mano.

Uso: python3 scripts/destape_cinta.py reports/<season>/roast/facts-<liga>-<fecha>.md
"""
import re
import sys

txt = open(sys.argv[1]).read()
equipos = {u: n.strip() for u, n in re.findall(r'^### (\S+) — "([^"]+)"', txt, re.M)}
sec = txt.split("## Resultados de la semana", 1)[1].split("\n## ", 1)[0]
partes = []
for g, pg, pp, p in re.findall(r"\*\*(\S+)\*\* ([\d.]+) vs ([\d.]+) (\S+)", sec):
    partes.append(f"{equipos.get(g, g)} {pg} – {pp} {equipos.get(p, p)}")
print("   ●   ".join(partes))
