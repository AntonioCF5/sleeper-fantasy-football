#!/usr/bin/env python3
"""Paso 1 del pipeline de video del Destape: WhatsApp → guion hablado.

Convierte el texto APROBADO de una edición (formato WhatsApp: *negritas*,
_cursivas_, emojis, rankings numerados) en el guion que se pega en la voz
de Miroslava en Artlist (ElevenLabs). Reglas:

- Fuera asteriscos, guiones bajos, emojis y URLs — el TTS los lee o los
  tropieza; ninguna de las dos cosas es aceptable.
- Los encabezados de sección se vuelven transiciones habladas cortas.
- "*N. Equipo* — chiste" del ranking se vuelve "Número N: Equipo. Chiste."
  (el TTS lee "1." como "uno punto" — inaceptable al aire).
- Rayas/guiones largos → coma o punto (pausa natural del TTS).
- `--resumen` (default, ~2-2.5 min) recorta a: gancho + primera sección
  COMPLETA (partir la historia mata el chiste) + top 3 y fondo 3 del
  ranking + arranque y remate del cierre. `--completo` lo lee todo.
- Estima duración a ~155 palabras/min (ritmo crónica) para saber en qué
  modo cabe la edición en los 3 min de HeyGen Avatar 4.

Uso: python3 scripts/destape_guion.py <destape.txt> [--completo]
Escribe <destape>-guion.txt junto al original y lo imprime.
"""
import re
import sys
from pathlib import Path

WPM = 155  # palabras/minuto, ritmo de reportera

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF\U0000FE0F\U00002B00-\U00002BFF\U00002190-\U000021FF]+")


def _habla(linea):
    """Una línea WhatsApp → una línea hablada."""
    s = EMOJI.sub("", linea)
    s = re.sub(r"https?://\S+", "", s)
    s = s.replace("*", "").replace("_", "")
    s = re.sub(r"\s*\b(LOL|XD|JAJA[JA]*)\b\.?", "", s, flags=re.I)  # risa escrita: el TTS la lee literal
    # ranking: "N. Equipo — chiste" → "Número N: Equipo. Chiste."
    m = re.match(r"\s*(\d+)\.\s*([^—-]+?)\s*[—-]\s*(.+)$", s)
    if m:
        n, equipo, chiste = m.group(1), m.group(2).strip(), m.group(3).strip()
        chiste = chiste[0].upper() + chiste[1:] if chiste else chiste
        return f"Número {n}: {equipo}. {chiste}"
    s = s.replace(" — ", ", ").replace("—", ", ").replace(" ,", ",")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s.lstrip(",").strip()  # la firma "— Miroslava" no debe abrir con coma


def convertir(texto, resumen=True):
    lineas = [l for l in texto.split("\n")]
    # secciones: bloques separados por encabezados (línea corta toda en
    # negritas tras emoji — ya sin formato, la detectamos por MAYÚSCULAS)
    bloques, actual = [], []
    for l in lineas:
        h = _habla(l)
        if not h:
            continue
        es_titulo = bool(EMOJI.match(l.strip())) and "*" in l or h.isupper()
        if es_titulo:
            if actual:
                bloques.append(actual)
            actual = [("titulo", h)]
        else:
            actual.append(("linea", h))
    if actual:
        bloques.append(actual)

    if resumen:
        # gancho (bloque 0) + primera sección + ranking recortado + último bloque
        elegidos = []
        rank_idx = next((i for i, b in enumerate(bloques)
                         if sum(1 for k, v in b if v.startswith("Número ")) >= 6), None)
        ult = len(bloques) - 1
        for i, b in enumerate(bloques):
            if i == rank_idx:
                nums = [(k, v) for k, v in b if v.startswith("Número ")]
                titulo = [(k, v) for k, v in b if k == "titulo"]
                b = titulo + nums[:3] + [("linea", "Y saltándonos a los del montón...")] + nums[-3:]
            elif i == ult and i != rank_idx:   # cierre: entrada + últimas dos líneas
                b = b[:2] + b[-2:] if len(b) > 4 else b
            if i in (0, 1, rank_idx, ult):
                elegidos.append(b)
        bloques = elegidos

    partes = []
    for b in bloques:
        partes.append("\n".join(v for _, v in b))
    return "\n\n".join(partes)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    completo = "--completo" in sys.argv
    src = Path(args[0])
    guion = convertir(src.read_text(), resumen=not completo)
    n = len(guion.split())
    dur = n / WPM * 60
    out = src.with_name(src.stem + "-guion.txt")
    out.write_text(guion + "\n")
    print(guion)
    print(f"\n--- {n} palabras ≈ {int(dur // 60)}:{int(dur % 60):02d} "
          f"({'completo' if completo else 'resumen'}) → {out.name}")
    if dur > 175:
        print("⚠ Más de ~3 min: HeyGen Avatar 4 corta ahí. Usa --resumen o recorta.")


if __name__ == "__main__":
    main()
