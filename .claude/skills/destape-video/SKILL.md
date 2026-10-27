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


## Flujo Artlist MCP (2026-10-27 — el que se usa ahora; reemplaza Artlist web + HeyGen)

Probado de punta a punta con "Miroslava responde a La Dona". Todo desde el
conector Artlist (plan AI Suite, créditos mensuales; renueva el 9 de cada mes).

1. **Voz** — `generate_voiceover`, modelo **ElevenLabs Eleven v3**, voz
   **Norah** (única femenina con acento *Latin American*; el user exige voz
   sudamericana), `language: Spanish`, `accent: Latin American`,
   `voice_stability: 0.3`. Etiquetas v3 en el texto ([mischievously]
   [sarcastic] [whispers] [sighs] [laughs]); números en letra. ~90-150
   créditos por guion. El ID de ElevenLabs tMzxR2W7o3RLIY7zWBbG NO existe en
   Artlist ni en Higgsfield.
2. **Nunca dejar que el modelo de video invente la voz**: Seedance con audio
   nativo pronunció "PALER" por "pesar" y deformó "Matasanos" (prueba en
   Higgsfield, 10-13). La voz sale SIEMPRE de TTS y el video solo sincroniza.
3. **Lip-sync** — `generate_video` con **Wan 2.7 - I2V - 720p**: `input` =
   [foto vertical `data/intel/brand/miroslava-avatar-vertical.jpg`, audio];
   el audio entra como `voice_url`. Máx **15 s por clip**, 3,000 créditos por
   clip de 15 s → partir el audio en silencios (`silencedetect`) en trozos
   ≤15 s (acelerar ≤5% con `atempo` si hace falta). Las variantes Seedance
   R2V de Artlist rechazan imagen+audio juntos (`reference_unsupported_model`).
   Pide confirmación de costo: mostrar créditos al user y esperar su sí.
4. **Ensamble** — unir clips con `trim` + `concat`, y montar encima el MP3
   exacto de la voz (no el audio del clip). Escalar a 1080x1920 antes de
   concatenar con tarjetas propias.
5. **Montaje noticiero** — `destape_montaje.py <cuerpo.mp4> <out.mp4>
   --vertical --subtitulo "…" --pie "LA DINASTÍA" --escaleta cues.json
   --ticker "$(python3 scripts/destape_cinta.py <hoja-de-hechos>)"`.
   Cabezal con escudo + EN VIVO, cintillo rojo de sección, barra de datos,
   cinta MARCADOR con los resultados reales de la hoja, himno en intro/outro.
   Tiempos de la escaleta = silencios del audio + desfase de tarjetas previas.
6. QA: 4-5 frames en hoja de contactos; peso < 64 MB.

Presupuesto: un video de ~30 s a cámara ≈ 6,000 créditos; proponer siempre la
versión de 30 s (más punch y la mitad del costo) antes que la completa.

## Reglas que ya costaron retrabajo (no reaprender)

- El ffmpeg de brew NO trae drawtext: todo texto entra como SVG→PNG vía
  `sips` (que sí renderiza Arial Black y emoji a color).
- Las barras del letterbox de HeyGen son BLANCAS: cropdetect necesita
  `negate` antes.
- zsh no divide variables sin comillas: `${=VAR}` o listas explícitas.
- El mp3 del himno trae CARÁTULA embebida (stream mjpeg): todo filtro o
  medición de audio sobre él necesita `-map 0:a` / selector `[N:a]`, o la
  cadena falla EN SILENCIO (sin error, sin salida).
- El avatar no tiene que ser el frontal de estudio: `brand/miroslava-jersey.png`
  (tailgate) funcionó igual en HeyGen. El guardarropa de
  `miroslava-personaje.md` da variantes por ocasión — la cara no cambia.
- Cambios de proceso ordenados por el user → actualizar este skill + el
  pipeline doc en el mismo commit.
- **El video y las tarjetas salen del MISMO .txt** (2026-09-29): el skill
  `destape-visual` renderiza ese texto a carrusel + periódico. Si el user
  publica con cambios, el .txt se sincroniza con lo publicado ANTES de hacer
  guion o tarjetas — un video que dice algo que la tarjeta no dice es una
  contradicción pública.
- **Vestuario disponible para thumbnails, intro o cortinillas**: las fotos
  por sección en `data/intel/brand/miroslava-*.jpg` (boxeo, regadera, podio,
  guerra, elevador, palpitote, despedida, portada-*, final-*…; tabla completa
  en el skill `destape-visual`). Misma cara; cualquiera sirve como avatar de
  HeyGen si es frontal y con la boca visible.

## Pendientes vivos

- ~~Himno como cama del outro~~ HECHO (2026-09-08/09): el montaje detecta
  `brand/himno-gallamijos.mp3` y lo pone en intro (apertura, 3s) y outro
  (final del track, 10s) — fragmentos distintos a propósito.
- Sincronía por transcripción real (whisper) si el desfase estimado por
  palabras resulta molesto en la práctica.
- Usar las tarjetas del carrusel (`reports/<season>/roast/visual/`) como
  cortinillas de sección en el montaje, en lugar de cintillos generados:
  mismo diseño en video y en imagen.
