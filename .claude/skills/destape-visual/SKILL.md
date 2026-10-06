---
name: destape-visual
description: Diseñador del Destape de Miroslava en formato visual. Úsalo cuando el user pida las tarjetas, el carrusel, el PDF/periódico del Destape, "armarlo fácil de leer", cambiar el diseño, o cuando mande imágenes nuevas de Miroslava (vestuario, poses, outfits) para usarlas en las tarjetas — o pida prompts para generarlas. Orquesta destape_visual.py (tarjetas + PDF carrusel + periódico), el vestuario con rotación semanal y el envío por correo con send_destape.py.
---

# Diseñador visual del Destape

El texto del Destape (el `.txt` aprobado: lint + editor + correcciones del
user) es la ÚNICA fuente. Este skill lo convierte en piezas para WhatsApp
**sin cambiar una palabra**. Documento vivo: toda corrección de diseño o de
proceso del user se persiste AQUÍ y en `data/intel/miroslava.md` en el mismo
commit.

## Salidas (una carpeta por edición)

`python3 scripts/destape_visual.py reports/<season>/roast/YYYY-MM-DD-<liga>.txt`
→ `reports/<season>/roast/visual/<edición>/`:

1. **Tarjetas** `NN-<sección>.jpg`, 1080x1350 (4:5): portada con Miroslava +
   índice, una por sección con su foto de vestuario en banda a la derecha
   del encabezado, el ranking partido en tarjetas de 6 con una **portadilla**
   a foto completa al inicio. Todo cabe: si el texto se desborda, se encoge
   (zoom); si la foto obliga a encoger de más, la tarjeta suelta la foto
   (umbral 0.8; Medallas aguanta hasta 0.62 porque el user quiere su foto
   siempre). Las cortas llevan el escudo de agua; la última, la foto final.
   Llevan fecha EXIF consecutiva → guardadas en el teléfono quedan en orden.
2. **PDF carrusel** `<edición>-carrusel.pdf`: las tarjetas en orden, un
   archivo. Es lo que el user comparte (y lo único de imágenes que va en el
   correo).
3. **PDF periódico** `<edición>.pdf`: cabezal gótico *El Destape*, fechario
   (Año 1 · Número N · fecha larga · liga), primera plana con la nota de la
   redacción + la Putiza de nota principal (marcador como titular), resto a
   tres columnas con fotos de Miroslava como fotoperiodismo. Se imprime en
   dos pasadas (tabloide → mide la última plana con pdftoppm → reimprime con
   el alto justo) para que no quede media plana en blanco.

`--solo-tarjetas` / `--solo-pdf` para iterar rápido (ojo: `--solo-tarjetas`
recrea la carpeta y borra el periódico; al final corre completo).

**Envío**: `python3 scripts/send_destape.py <edicion.txt>` → correo al user
con el texto plano en el cuerpo + SOLO los dos PDFs. **Nunca** las tarjetas
sueltas (user 2026-09-29: "el pdf carrusel con todas es suficiente").

## Formato del .txt que el parser necesita

Si el texto rompe esto, la línea sale como párrafo suelto:
- sección: `emoji *TÍTULO*` (opcional `(subtítulo)`) en su propia línea
- medalla: `emoji *Etiqueta:* texto`
- ranking: `N. *Equipo* W-L, pts (Nº) — texto`; el primer emoji de etiqueta en la línea se pinta como chip: 🐎 caballo negro · 📉 decepción · 🧂 salado · 💩 mojón · 🤡 mal coach (`ETIQUETAS` en destape_visual.py)
- Putiza: `*Equipo A 170.5 — Equipo B 108.2.* texto` (marcador grande)
- Palpitote: `*A vs B.* texto`
- tabla de la Guerra: el bloque ``` de la hoja de hechos, literal
- firma: `— *Miroslava, …*`

## Vestuario de Miroslava (rotación semanal)

Fotos en `data/intel/brand/miroslava-*.jpg`. `POOLS` en `destape_visual.py`
asigna a cada sección su pool; cada jornada la sección toma la siguiente
(número de jornada; **la Dinastía va un paso adelante** para que las dos
ediciones del martes no repitan foto). Nunca la misma foto en dos tarjetas
seguidas. **Diciembre**: portada y foto final con el suéter navideño.

| Pool | Archivos |
|---|---|
| portada | `jersey`, `portada-*` |
| regadera | `regadera`, `regadera-*` |
| putiza | `boxeo`, `boxeo-*` |
| medallas | `salado`, `podio`, `muerto`, `podio-*`, `medallas-*` |
| guerra | `guerra`, `guerra-*` |
| penthouse | `elevador`, `elevador-*` (van en la portadilla) |
| palpitote | `palpitote`, `palpitote-*` |
| cierre | `despedida`, `despedida-*` |
| final (foto grande de la última tarjeta) | `final-*` |
| redaccion (periódico) | `redaccion`, `redaccion-*` |

Genéricas de respaldo: `noticiero`, `gala`, `exclusiva`, `exclusiva-news`.

### Cuando el user manda imágenes nuevas

1. **Revísalas una por una** antes de aceptarlas: cara igual a la referencia,
   manos/brazos completos (ya salió una mano flotante en el elevador y una
   marca de labial flotando en el beso — ambas RECHAZADAS), texto legible si
   lleva ("El Destape", "SÓTANO", "PRESS"). Si una falla, NO la guardes: da
   el prompt de corrección sobre esa imagen + una v2 desde la base.
2. Convierte a JPG q92 y guarda como `data/intel/brand/miroslava-<pool>-<nombre>.jpg`
   (se descubre sola por el prefijo; no hay que tocar código para que rote).
3. **Mide el encuadre** (cara: % vertical y horizontal) y regístralo en
   `VESTUARIO` como `("archivo", y, x)` si no está centrada. Si en la
   portadilla 4:5 el chiste queda fuera de cuadro (el dedo en SÓTANO),
   ajusta `PORTADILLA_X`.
4. Re-renderiza las dos ligas, revisa en hoja de contactos que ninguna cara
   quede tapada por el encabezado ni cortada, reenvía y actualiza el estado
   en `data/intel/brand/miroslava-vestuario-prompts.md`.

### Cuando pide prompts nuevos

Todos los prompts viven en `data/intel/brand/miroslava-vestuario-prompts.md`.
Molde fijo: candado de identidad ("Using the attached reference image… keep
her face… IDENTICAL…") + Setting + Outfit + Pose + Composition ("horizontal
16:9, subject centered, face in the upper third", "exactly two arms and two
hands" cuando la pose use las dos) + "original fictional character". Colores
de marca navy #013369 y rojo #D50A0A, monograma "GM". Nombre de archivo del
pool en cada prompt. Nada que parezca persona real; nada de desnudez.

## Reglas que ya costaron retrabajo

- **Chrome headless en este Mac escribe el archivo y no termina**: se lanza
  en su propio grupo de procesos con perfil temporal NUEVO por llamada, se
  espera el "written to file" y se mata el grupo. Falla intermitente al
  arrancar → 3 reintentos (una Dinastía salió incompleta por esto).
- La foto de marca completa metía 10 MB al PDF: se usan copias de 1400px.
- Emoji con selector de variación (⚔️) necesitan `Apple Color Emoji` en la
  pila de fuentes antes que las del sistema.
- El `.txt` en el repo tiene que ser LA VERSIÓN PUBLICADA: si el user pega lo
  que mandó al grupo, sincroniza antes de re-renderizar.
- Pies de foto neutros y colofón sin chistes: el renderer no inventa humor
  fuera del texto aprobado.
