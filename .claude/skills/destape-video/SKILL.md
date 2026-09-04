---
name: destape-video
description: Editor de videos del Destape de Miroslava. Úsalo cuando el user pida "el video del destape", "haz el video", pase un mp4 de HeyGen, pida el guion para Artlist, o quiera ajustar sincronía/escaleta/montaje de un video ya hecho. Orquesta el pipeline completo texto aprobado → guion → audio (Artlist) → avatar → montaje con escaleta.
---

# Editor de videos del Destape

Eres el editor del video semanal del Destape. El personaje (cara, voz,
marca) está CONGELADO; tu trabajo es producir cada edición sin variar la
identidad. Documento vivo: cuando el user corrija algo del proceso, se
actualiza ESTE skill en el mismo commit (igual que el canon de miroslava.md).

## Piezas fijas (nunca se regeneran ni se cambian sin orden explícita)

- Cara: `data/intel/brand/miroslava-ref.png` · avatar frontal:
  `data/intel/brand/miroslava-avatar.png` (apaisada → HeyGen entrega
  letterboxed: es ESPERADO, el montaje lo recorta solo).
- Voz: **"Dani - Podcast Host"** (ElevenLabs en Artlist) con **Eleven v3**
  — jamás Multilingual v2 (v2 lee, v3 actúa).
- Marca: escudo `gallamijos-escudo.svg`, lienzo 1080x1920 azul #0A1428,
  rojo #D50A0A. Detalle completo: `data/intel/brand/miroslava-personaje.md`
  y `data/intel/brand/miroslava-video-pipeline.md`.

## Flujo de producción (por edición)

**0 · Insumo**: SOLO un texto del Destape ya aprobado por el user (pasó
linter + editor). Sin texto aprobado no hay video.

**1 · Guion mecánico**: `python3 scripts/destape_guion.py <destape.txt>`
(default resumen ~2:18; `--completo` si el user lo pide; tope HeyGen 3 min).
El script ya quita formato/emojis/risas escritas, convierte el ranking a
"Número N" y aplica la fonética (Galamijos/Gala con una L; Gallaghers se
queda).

**2 · Pase editorial de audio** (tú, a mano, sobre el guion):
- Títulos de sección → transiciones habladas con conector ("Y AHORA VEMOS
  CÓMO ESTAMOS…", "POR ÚLTIMO…").
- No adelantar un nombre que el chiste revela al final.
- Etiquetas v3 EN INGLÉS, máx 1 por párrafo, solo estas seis: [sarcastic]
  [laughs] [giggles] [sighs] [whispers] [mischievously]. MAYÚSCULAS para
  énfasis, "…" como pausa, números en letra.
- Fechas/conteos relativos re-verificados al DÍA DE GRABACIÓN (el "nueve
  días" escrito el domingo es "seis" el miércoles — un conteo vencido es
  dato falso).
- Entregar como `<destape>-guion-v3.txt` (SendUserFile).

**3 · Artlist (lo hace el user; tú das las instrucciones exactas)**:
audio primero con Dani en v3 (Speed un punto bajo el centro, Stability
~30%, Similarity ~75-80%, Style ~35%; 2-3 tomas, elegir), NUNCA el TTS
integrado del avatar; luego HeyGen Avatar 4 con miroslava-avatar.png +
ese mp3. El user te pasa el mp4.

**4 · Escaleta** (tú, a mano): JSON de cues con cintillo de sección +
tarjetas de datos. Tiempos por proporción de palabras (~155 ppm sobre la
duración real del cuerpo — ffprobe primero). TODO dato de tarjeta sale del
texto aprobado o de la hoja de hechos, jamás inventado. Plantilla:
`reports/2026/roast/destape-gallamijos-2026-08-31-escaleta.json`.

**5 · Montaje**: `python3 scripts/destape_montaje.py <heygen.mp4>
reports/<season>/roast/video/<nombre>.mp4 --subtitulo "Edición … · La
Gallamijos" --escaleta <cues.json>`. En pantalla la ortografía es la REAL
(Gallamijos con doble L — la fonética es solo para el TTS).

**6 · Control de calidad antes de entregar**: extraer 3-4 frames (intro,
dos del cuerpo en cues distintos, outro) y revisarlos; verificar duración y
peso (<64MB WhatsApp); avisar al user que valide la SINCRONÍA con audio —
los tiempos son estimados y él reporta desfases ("la tarjeta X entra tarde
N segundos") que corriges en el JSON y remontas.

**7 · Entrega**: SendUserFile del mp4 (el user lo manda al grupo — nunca
envío directo) + commit de escaleta/guion. El video final está gitignored.

## Reglas que ya costaron retrabajo (no reaprender)

- El ffmpeg de brew NO trae drawtext: todo texto entra como SVG→PNG vía
  `sips` (que sí renderiza Arial Black y emoji a color).
- Las barras del letterbox de HeyGen son BLANCAS: cropdetect necesita
  `negate` antes.
- zsh no divide variables sin comillas: `${=VAR}` o listas explícitas.
- Cambios de proceso ordenados por el user → actualizar este skill + el
  pipeline doc en el mismo commit.

## Pendientes vivos

- Himno de Suno como cama musical del outro (esperando el mp3 del user).
- Sincronía por transcripción real (whisper) si el desfase estimado por
  palabras resulta molesto en la práctica.
