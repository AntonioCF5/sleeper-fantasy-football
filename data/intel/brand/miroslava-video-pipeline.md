# EL DESTAPE EN VIDEO — diseño del pipeline (2026-08-31)

Meta: una vez APROBADO el texto del Destape, un solo comando produce el
video-reportaje (Miroslava hablando a cámara) listo para que el user lo
mande al grupo. El user sigue enviando manualmente — igual que el texto.

## Flujo

```
texto aprobado (.txt)
  └─ 1. GUION      guion_video(): WhatsApp → guion hablado
  └─ 2. AUDIO      ElevenLabs TTS (voz fija de Miroslava) → .mp3
  └─ 3. VIDEO      avatar API (miroslava-avatar.png + audio) → talking head
  └─ 4. MONTAJE    ffmpeg: intro (logo + 💋), rótulos por sección,
                   outro con el himno → .mp4 final
  └─ 5. ENTREGA    reports/<season>/roast/video/ + SendUserFile
                   (el user lo manda al grupo; nunca envío directo)
```

## Decisiones de diseño

1. **El gate de aprobación es humano y manual.** El video se genera solo
   cuando el user dice "apruébalo / haz el video" sobre un texto que ya pasó
   linter + editor. Nada se auto-publica.
2. **Guion ≠ texto de WhatsApp.** El paso 1 quita asteriscos/emojis/URLs,
   convierte listas (el power ranking se lee, no se deletrea), y marca
   pausas. Dos modos: `--completo` (toda la columna, ~3-4 min — puede
   exceder los 3 min de HeyGen; el script avisa) y `--resumen` (~2-2.5 min:
   gancho + primera sección completa + top/fondo del ranking + remate del
   cierre). El resumen es el default. `scripts/destape_guion.py` YA EXISTE
   y está probado con la columna post-draft.
3. **Voz fija.** Se diseña UNA voz en ElevenLabs (Voice Design: español
   mexicano, mujer ~35, entrega de crónica deportiva, sarcasmo seco, ritmo
   de reportera de sideline) y se congela el `voice_id`. La voz es parte del
   personaje: no se regenera.
4. **Imagen fija.** El avatar consume siempre `miroslava-avatar.png`
   (variación B aprobada). Regenerarla cada semana = otra actriz.
5. **Llaves en el Keychain de macOS**, mismo patrón que el Gmail del
   newsletter: el user las registra en SU terminal con
   `security add-generic-password`; Claude nunca las ve ni las imprime.
   Servicios: `miroslava-elevenlabs`, `miroslava-video` (avatar API),
   `miroslava-gemini` (imágenes, opcional).

## Proveedor: ARTLIST (decidido por el user, 2026-08-31)

El user ya paga Artlist, y su AI Toolkit trae exactamente las piezas:
**HeyGen Avatar 4** (imagen + audio propio → avatar hablando, hasta 3 min
— cabe el resumen y casi cualquier columna), con OmniHuman 1.5 / Lip Sync
V2 como alternativas si HeyGen decepciona, y **voces ElevenLabs** para el
voiceover. Costo extra: $0.

**Limitación que redefine el pipeline: Artlist es web, sin API.** Los pasos
2 y 3 no se automatizan por script — se hacen en el navegador. Dos modos:

- **Modo asistido (default):** Claude genera el guion (paso 1
  automatizable), y con la sesión de Artlist del user abierta en Chrome,
  Claude conduce el navegador: pega el guion en la voz fija, descarga el
  mp3, lo sube a HeyGen Avatar 4 con `miroslava-avatar.png`, descarga el
  video y corre el montaje ffmpeg (paso 4, automatizable). Un solo "haz el
  video" del user dispara todo; él solo aprueba y envía.
- **Modo manual (fallback):** Claude entrega guion + instrucciones y el
  user hace los 3 clics en Artlist.

**La voz igual se congela:** se elige UNA voz ElevenLabs dentro de Artlist
(mujer, español mexicano, entrega de crónica, sarcasmo seco), se prueba con
un párrafo del Destape, y su nombre queda registrado AQUÍ para usar siempre
la misma. La voz es parte del personaje.

**Receta de audio (calibrada 2026-09-03, tras el primer intento robótico):**

- **Modelo: Eleven v3** — NUNCA Multilingual v2: v2 lee, v3 actúa. v3 acepta
  etiquetas de actuación en el guion: `[sarcastic]`, `[laughs]`, `[giggles]`,
  `[sighs]`, `[whispers]`, `[mischievously]` (solo esas seis, en inglés,
  con moderación: 1 por párrafo máximo — de más degradan la voz).
- El pase de etiquetas es EDITORIAL (dónde va el sarcasmo lo decide quien
  conoce el chiste): Claude lo hace cada semana sobre el guion mecánico y
  entrega `*-guion-v3.txt`. Convenciones: MAYÚSCULAS en la palabra de
  énfasis, puntos suspensivos como pausa, números en letra ("Número
  dieciséis"), párrafos separados = respiraciones.
- Sliders: Speed un punto ABAJO del centro (lo "muy seguido" se arregla más
  con las pausas del guion que con el slider); Stability bajo (~30%,
  "Creative" si v3 lo nombra así); Similarity alto (~75-80%); Style
  Exaggeration medio (~35%) — en cero suena leído.
- **Del pase final del user al guion piloto (2026-09-03):** (a) los títulos
  de sección se convierten en TRANSICIONES habladas con conector ("Y AHORA
  VEMOS CÓMO ESTAMOS DEL PENTHOUSE AL SÓTANO", "POR ÚLTIMO, CIERRE…") — un
  título seco leído en voz suena a robot cambiando de archivo; (b) cuando el
  chiste revela el nombre al final, NO adelantarlo en la entrada del ranking
  ("Número dieciséis: El actual campeón… llamado… RodrigoDiaz" — no
  "Número dieciséis: RodrigoDiaz. El actual campeón…"); (c) la ortografía
  fonética del himno aplica a TODO guion de TTS: Galamijos/Gala con una L
  ("Gallaghers" se queda — el user lo dejó tal cual). destape_guion.py ya
  aplica (c) mecánicamente; (a) y (b) son parte del pase editorial semanal.
- v3 no es determinista: generar 2-3 tomas y elegir. La toma buena se nota
  en "pasearse como las perras que son" y en el [whispers] del cierre.

> Voz elegida (user, 2026-09-03): **"Dani - Podcast Host"** (ElevenLabs
> dentro de Artlist). CONGELADA: es la voz de Miroslava para siempre —
> misma regla que la cara. Siempre seleccionarla por ese nombre exacto;
> si Artlist la renombra o la retira, avisar al user antes de tocar nada.

## Implementación (cuando haya proveedor + llaves)

Lo que sí es script: `scripts/destape_guion.py <texto.txt>
[--resumen|--completo]` (paso 1: WhatsApp → guion hablado) y el montaje
ffmpeg del paso 4. Los pasos 2-3 viven en Artlist vía navegador. Sin llaves
que registrar: la sesión de Artlist del user en Chrome es la credencial.
