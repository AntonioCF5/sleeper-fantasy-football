#!/usr/bin/env python3
"""Validador mecánico del Destape de Miroslava — capa 1 del control editorial.

Atrapa en milisegundos TODO lo que es determinístico, para que el pase de
criterio (el subagente editor) solo tenga que pensar en humor y no en datos:

  1. Formato WhatsApp (nada de markdown: ** , ## , [texto](url))
  2. Presupuesto de palabras según tipo (boletín ~250 / columna ~550)
  3. Saludo y cierre NO repetidos (contra las bitácoras de miroslava.md)
  4. Conteos de bando correctos (contra el canon, no inferidos)
  5. elmijo mencionado máximo 2 veces (regla de balance)
  6. Temas prohibidos (Drácula/vampiros sobre el Bebé)
  7. Jugadores NFL mencionados que NO aparecen en la hoja de hechos de esa
     liga — el error que atribuye un jugador al roster equivocado

Uso:
    python3 scripts/roast_lint.py <archivo.txt> --liga gallamijos|dynasty
                                  [--tipo boletin|columna]

Sale con código 1 si hay errores duros, 0 si solo hay avisos.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CANON = ROOT / "data" / "intel" / "miroslava.md"
# Presupuestos por tipo. "columna-ranking" es más alto a propósito: un power
# ranking de 18 equipos son 18 líneas obligatorias (~180 palabras) que son
# CONTENIDO, no relleno. No usar este tipo para justificar prosa de más.
PRESUPUESTO = {"boletin": 300, "columna": 600, "columna-ranking": 780}

# Conteos de bando en la REDRAFT, leídos del canon (no inferir jamás)
BANDOS_REDRAFT = {"mijos": 4, "gallaghers": 9, "gallas": 9, "sin bandera": 5}

# Palabras vacías: una frase repetida solo cuenta si trae contenido real
COMUNES = {"que", "de", "la", "el", "los", "las", "un", "una", "y", "a", "en",
           "por", "con", "para", "su", "sus", "se", "no", "es", "son", "del",
           "al", "lo", "le", "les", "mas", "pero", "como", "ya", "esta", "este",
           "esa", "ese", "hay", "va", "van", "ni", "si", "tu", "yo", "mi"}
# Frases estructurales del formato — no son reciclaje
CABECERA = {"destape de", "destape de miroslava", "de miroslava", "el destape",
            "el destape de", "edicion post", "post draft", "de la liga",
            "la gallamijos", "de la gallamijos", "los observo", "miroslava que"}

NUMEROS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
           "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
           "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
           "dieciseis": 16, "diecisiete": 17, "dieciocho": 18}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _bitacora(nombre, saltar_fecha=None):
    """Frases ya usadas, extraídas de una tabla markdown del canon.

    `saltar_fecha` omite las filas de esa fecha: al revisar una edición se
    ignoran sus propias entradas, para poder re-validar un borrador que ya
    quedó anotado (pasa al corregir una nota el mismo día)."""
    if not CANON.exists():
        return []
    txt = CANON.read_text()
    m = re.search(rf"## Bitácora de {nombre}.*?\n\n(.*?)(?:\n\n|\Z)", txt, re.S)
    if not m:
        return []
    frases = []
    for linea in m.group(1).split("\n"):
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) >= 3 and not set(celdas[0]) <= set("-: "):
            if saltar_fecha and saltar_fecha in celdas[0]:
                continue
            frases.append(celdas[-1].strip('"').strip())
    return [f for f in frases if len(f) > 15]


def _descansando(saltar_fecha=None):
    """Términos, apodos y chistes marcados 'descansar' en la bitácora del
    canon — se usaron en la edición anterior y no se repiten.
    `saltar_fecha` omite las filas de la propia edición (igual que en las
    bitácoras de saludos): sus términos son los que ESTÁ estrenando."""
    if not CANON.exists():
        return []
    txt = CANON.read_text()
    m = re.search(r"## Bitácora de chistes.*?\n\n(.*?)(?:\n\n##|\Z)", txt, re.S)
    if not m:
        return []
    fuera = []
    for linea in m.group(1).split("\n"):
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) >= 3 and "descansar" in celdas[-1].lower():
            if saltar_fecha and saltar_fecha in celdas[0]:
                continue
            fuera.append(_norm(celdas[1]))
    return [f for f in fuera if f]


def _solapamiento(a, b, n=6):
    """¿Comparten una secuencia de n palabras? (detecta reciclaje real)."""
    pa, pb = _norm(a).split(), _norm(b).split()
    if len(pa) < n or len(pb) < n:
        return _norm(a) == _norm(b)
    grams = {" ".join(pb[i:i + n]) for i in range(len(pb) - n + 1)}
    return any(" ".join(pa[i:i + n]) in grams for i in range(len(pa) - n + 1))


def revisar(path, liga, tipo, ya_publicado=False):
    texto = Path(path).read_text()
    errores, avisos = [], []
    cuerpo = [l for l in texto.split("\n") if l.strip()]

    # 1 · formato WhatsApp
    if "**" in texto:
        errores.append("Markdown `**` — WhatsApp usa UN solo asterisco para negritas.")
    if re.search(r"^#{1,6} ", texto, re.M):
        errores.append("Encabezado markdown `#` — no se renderiza en WhatsApp.")
    if re.search(r"\[[^\]]+\]\([^)]+\)", texto):
        errores.append("Link markdown `[texto](url)` — pega la URL desnuda.")

    # 2 · presupuesto
    n = len(texto.split())
    tope = PRESUPUESTO[tipo]
    if n > tope:
        errores.append(f"Largo: {n} palabras, tope {tope} para '{tipo}'. "
                       "Recorta relleno, no contenido de decisión.")

    # 3 · saludo y cierre nuevos
    # OJO al orden del flujo: se valida ANTES de anotar en las bitácoras.
    # Con --ya-publicado se salta, para poder re-revisar una edición enviada
    # cuyo saludo ya quedó registrado.
    if ya_publicado:
        avisos.append("--ya-publicado: me salto la revisión de saludo/cierre "
                      "(ya están en la bitácora por diseño).")
    else:
        saludo = next((l for l in cuerpo[1:] if not l.startswith(("💋", "_", "*"))), "")
        cierre = next((l for l in reversed(cuerpo) if not l.startswith("—")), "")
        m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
        propia = m.group(1) if m else None
        for etiqueta, frase, bit in (("saludo", saludo, _bitacora("saludos", propia)),
                                     ("cierre", cierre, _bitacora("despedidas", propia))):
            for usada in bit:
                if _solapamiento(frase, usada):
                    errores.append(f"El {etiqueta} recicla uno ya publicado: «{usada[:60]}…» (regla 7).")
                    break

    # 4 · conteos de bando
    for bando, real in BANDOS_REDRAFT.items():
        for m in re.finditer(rf"\b(\w+)\s+{bando}\b", _norm(texto)):
            dicho = NUMEROS.get(m.group(1))
            if dicho and dicho != real:
                errores.append(f"Dice «{m.group(1)} {bando}» y en la redraft son {real} "
                               "(canon). Los conteos se leen, no se infieren.")

    # 5 · balance
    menciones = len(re.findall(r"\bel mijo\b|\belmijo\b", texto, re.I))
    if menciones > 2:
        errores.append(f"elmijo mencionado {menciones} veces; el máximo es 2 (regla 3).")

    # 6 · prohibiciones
    if re.search(r"dr[áa]cula|vampir", texto, re.I):
        errores.append("Prohibido el ángulo Drácula/vampiros sobre el Bebé Roiz.")

    # 7 · términos y chistes marcados "descansar" en el canon
    # Un detector genérico de n-gramas daba ruido (el español repite frases
    # comunes) y fallaba en lo distintivo. La lista curada del canon —igual
    # que las bitácoras de saludos y cierres, que sí funcionan— es precisa.
    _m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    for termino in _descansando(_m.group(1) if _m else None):
        if re.search(rf"\b{re.escape(termino)}\b", _norm(texto)):
            errores.append(f"«{termino}» está marcado DESCANSAR en el canon "
                           "(se usó en la edición anterior). Busca otro.")

    # 8 · jugadores contra la hoja de hechos    # 8 · jugadores contra la hoja de hechos
    hojas = sorted((ROOT / "reports").glob(f"*/roast/facts-{liga}-*.md"))
    if not hojas:
        avisos.append(f"No hay hoja de hechos para '{liga}' — corre roast_facts.py primero.")
    else:
        hoja = hojas[-1].read_text()
        try:
            from sleeper import api
            nfl = {p.get("full_name") for p in api.get_players().values() if p.get("full_name")}
        except Exception:
            nfl = set()
            avisos.append("No se pudo cargar la lista de jugadores NFL; salto esa revisión.")
        for cand in set(re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ']+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ']+\b", texto)):
            if cand in nfl and cand not in hoja:
                errores.append(f"«{cand}» es jugador NFL pero NO está en la hoja de hechos "
                               f"de {liga} — verifica de quién es antes de mencionarlo.")

    return errores, avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archivo")
    ap.add_argument("--liga", required=True, choices=["gallamijos", "dynasty"])
    ap.add_argument("--tipo", default="columna", choices=["boletin", "columna", "columna-ranking"])
    ap.add_argument("--ya-publicado", action="store_true",
                    help="re-revisar una edición ya enviada (salta saludo/cierre)")
    a = ap.parse_args()

    errores, avisos = revisar(a.archivo, a.liga, a.tipo, a.ya_publicado)
    for x in avisos:
        print(f"  aviso: {x}")
    if errores:
        print(f"\n✗ {len(errores)} problema(s) que hay que corregir ANTES del pase editorial:\n")
        for e in errores:
            print(f"  • {e}")
        sys.exit(1)
    print("✓ Capa mecánica limpia. Pasa al editor (subagente) para el criterio de humor.")


if __name__ == "__main__":
    main()
