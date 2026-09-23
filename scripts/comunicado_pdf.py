#!/usr/bin/env python3
"""Comunicado oficial de La Gallamijos en PDF membretado.

Toma un archivo de texto con el formato de secciones del comunicado y produce
un PDF carta con el membrete de la liga: escudo, franja azul marino #013369,
filete rojo #D50A0A y pie con fecha y firma. Pensado para los avisos de
comisionado (cambios de reglas, ajustes, calendario), no para el Destape.

Formato del archivo de entrada — una sección por bloque:
    # TÍTULO DEL COMUNICADO
    > párrafo de entrada
    ## NOMBRE DE SECCIÓN
    texto normal
    - viñeta
    | Jugador | Va para | Antes |     (tabla: primera fila = encabezados)
    ! caja de advertencia

Uso: python3 scripts/comunicado_pdf.py <entrada.txt> <salida.pdf>
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, Image)

ROOT = Path(__file__).resolve().parent.parent
ESCUDO_SVG = ROOT / "data" / "intel" / "brand" / "gallamijos-escudo.svg"
NAVY = colors.HexColor("#013369")      # azul del escudo
ROJO = colors.HexColor("#D50A0A")
GRIS = colors.HexColor("#4A5568")
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def escudo_png():
    out = Path("/tmp/_gm_escudo.png")
    subprocess.run(["sips", "-s", "format", "png", "-Z", "900",
                    str(ESCUDO_SVG), "--out", str(out)],
                   capture_output=True, check=True)
    return out


def membrete(canvas, doc):
    """Franja superior con escudo + nombre de liga, y pie de página."""
    w, h = letter
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 34 * mm, w, 34 * mm, stroke=0, fill=1)
    canvas.setFillColor(ROJO)
    canvas.rect(0, h - 36 * mm, w, 2 * mm, stroke=0, fill=1)
    try:
        canvas.drawImage(str(escudo_png()), 18 * mm, h - 31 * mm,
                         width=22 * mm, height=28 * mm, mask="auto")
    except Exception:
        pass
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(46 * mm, h - 17 * mm, "LA GALLAMIJOS")
    canvas.setFont("Helvetica", 9.5)
    canvas.setFillColor(colors.HexColor("#AFBBD0"))
    canvas.drawString(46 * mm, h - 23 * mm, "FANTASY FOOTBALL LEAGUE  ·  EST. 2015")
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.setFillColor(colors.white)
    canvas.drawRightString(w - 18 * mm, h - 23 * mm, "COMUNICADO OFICIAL")
    # pie
    canvas.setStrokeColor(colors.HexColor("#D5DBE5"))
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 16 * mm, w - 18 * mm, 16 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    hoy = date.today()
    canvas.drawString(18 * mm, 11 * mm,
                      f"Torreón, Coahuila · {hoy.day} de {MESES[hoy.month]} de {hoy.year}")
    canvas.drawRightString(w - 18 * mm, 11 * mm, f"Página {doc.page}")
    canvas.restoreState()


def construir(entrada, salida):
    P = {
        "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=19,
                                 textColor=NAVY, spaceAfter=2, leading=23),
        "intro": ParagraphStyle("i", fontName="Helvetica-Oblique", fontSize=10.5,
                                textColor=GRIS, spaceAfter=11, leading=15),
        "sec": ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=11.5,
                              textColor=ROJO, spaceBefore=13, spaceAfter=5),
        "txt": ParagraphStyle("p", fontName="Helvetica", fontSize=10.3,
                              leading=15.5, spaceAfter=7,
                              textColor=colors.HexColor("#1A202C")),
        "vin": ParagraphStyle("v", fontName="Helvetica", fontSize=10.3, leading=15,
                              leftIndent=10, bulletIndent=2, spaceAfter=3,
                              textColor=colors.HexColor("#1A202C")),
    }
    flow, tabla = [], []

    def cerrar_tabla():
        if not tabla:
            return
        t = Table(tabla, colWidths=[62 * mm, 52 * mm, 48 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F2F5F9")]),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#D5DBE5")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C3CCDA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flow.append(t)
        flow.append(Spacer(1, 8))
        tabla.clear()

    for raw in Path(entrada).read_text(encoding="utf-8").split("\n"):
        ln = raw.rstrip()
        if not ln.strip():
            cerrar_tabla()
            continue
        if ln.startswith("|"):
            tabla.append([c.strip() for c in ln.strip("|").split("|")])
            continue
        cerrar_tabla()
        if ln.startswith("# "):
            flow.append(Paragraph(ln[2:], P["titulo"]))
            flow.append(Spacer(1, 7))
        elif ln.startswith("> "):
            flow.append(Paragraph(ln[2:], P["intro"]))
        elif ln.startswith("## "):
            flow.append(Paragraph(ln[3:].upper(), P["sec"]))
        elif ln.startswith("- "):
            flow.append(Paragraph(ln[2:], P["vin"], bulletText="•"))
        elif ln.startswith("! "):
            caja = Table([[Paragraph(ln[2:], P["txt"])]], colWidths=[162 * mm], hAlign="LEFT")
            caja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4F4")),
                ("BOX", (0, 0), (-1, -1), 0.8, ROJO),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]))
            flow.append(caja)
            flow.append(Spacer(1, 6))
        else:
            flow.append(Paragraph(ln, P["txt"]))
    cerrar_tabla()

    doc = BaseDocTemplate(str(salida), pagesize=letter,
                          leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=44 * mm, bottomMargin=22 * mm,
                          title="Comunicado oficial — La Gallamijos",
                          author="Comisionado, La Gallamijos")
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[marco], onPage=membrete)])
    doc.build(flow)
    print(f"[pdf] {salida}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    construir(sys.argv[1], sys.argv[2])
