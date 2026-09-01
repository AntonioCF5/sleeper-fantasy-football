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
   pausas. Dos modos: `--completo` (toda la columna, ~3-4 min) y
   `--resumen` (60-90 seg: cagada de la semana + top/fondo del ranking +
   cierre). Para WhatsApp el resumen es el default: nadie ve 4 minutos.
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

## Proveedor de video (por decidir — la única pieza abierta)

| Opción | Cómo funciona | Pro | Contra |
|---|---|---|---|
| **HeyGen** (recomendada) | photo avatar + audio propio → lip-sync | API madura, acepta NUESTRO mp3 (la voz de ElevenLabs manda), estable semana a semana | suscripción aparte |
| Hedra Character | igual: imagen + audio → personaje hablando | expresividad facial alta | API más joven |
| Veo 3.1 (Gemini) | referencia + prompt, audio generado por el modelo | un solo proveedor con Nano Banana | NO acepta guion exacto ni voz fija: la voz cambiaría cada semana — mata la consistencia del personaje |

Veo se descarta para el reportaje por la voz; sirve solo para b-roll/intro.

## Implementación (cuando haya proveedor + llaves)

`scripts/destape_video.py <texto.txt> [--resumen|--completo]` — stdlib +
curl como el resto del repo; ffmpeg ya presente en macOS vía brew o se pide.
Estado incremental en `data/intel/video_state.json` (no regenerar audio si
el texto no cambió). Costos por edición: ElevenLabs ~centavos; HeyGen
~1 crédito/min.
