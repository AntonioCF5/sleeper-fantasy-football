# MIROSLAVA — identidad visual (para Nano Banana Pro)

> **REFERENCIA APROBADA (2026-08-31): `miroslava-ref.png`** en esta carpeta —
> "así queda", palabras del user. Es LA cara del personaje: toda imagen
> futura se genera adjuntándola, nunca desde el prompt maestro solo (ese
> queda como documentación del casting). Detalles tal como quedaron: cabello
> rubio dorado con reflejos cobrizos, pecas en nariz y mejillas, lunar sobre
> la comisura derecha y un segundo lunar abajo a la izquierda, aros dorados,
> collar fino, gafete "GM SPORTS PRESSE" (así se aprobó, con todo y el
> PRESSE — no "corregirlo" sin que lo pida el user).

Personaje FICTICIO. Regla dura: no debe parecerse a ninguna reportera real —
si una generación recuerda a una persona real, se descarta.

## Rasgos canónicos (fijos en TODA imagen, para consistencia)

- Reportera de sideline ex-Liga MX, **finales de los 20** (rejuvenecida por
  el user 2026-08-31; antes ~35). Rostro dulce, natural y coqueto — cute con
  un dejo de travesura, no femme fatale dura. **Aspecto nórdico/europeo**
  (decisión del user 2026-08-31): piel clara porcelana, ojos azul claro,
  rubia natural — la güera del sideline. El personaje sigue siendo mexicano
  en voz y acento; el look es escandinavo.
- Cabello rubio dorado con reflejos cobrizos (strawberry blonde), voluminoso,
  ondulado, con movimiento. (Evolución del casting 2026-08-31: castaña →
  rubia → nórdica → esbelta → joven/natural → APROBADA.)
- Ojos azul claro con mirada cómplice/burlona directo a cámara; una ceja
  ligeramente levantada, media sonrisa de "yo sé algo que tú no".
- **Labios rojos intensos** (el 💋 es su emblema; sobreviven al look natural
  por decisión editorial) + **lunar pequeño sobre la comisura derecha** +
  **pecas sutiles en nariz y mejillas** (anclas de consistencia entre
  generaciones). Maquillaje ligero, piel fresca.
- Aretes de aro dorados.
- Figura esbelta —cintura fina, rostro afilado— pero con el busto prominente
  del running gag intacto; vestido azul marino **#013369** entallado con
  escote pronunciado pero elegante; gafete de prensa con cordón rojo
  **#D50A0A** (los colores del escudo de la liga).
- Micrófono de broadcast con banderín azul marino y monograma **GM** rojo.
- Tacones (cuando el encuadre los muestra): "vengo del sideline con tacones".

## PROMPT MAESTRO (retrato editorial — la imagen de marca)

```
Photorealistic editorial portrait of Miroslava, a fictional sideline
sports reporter in her late 20s with a Northern European / Scandinavian
look — fair porcelain skin with subtle freckles across the nose and cheeks,
large expressive light blue eyes, a sweet natural cute face with light
fresh makeup, waist-up, standing on the sideline
of a packed American football stadium at golden hour. She holds a
professional broadcast microphone with a navy-blue mic flag bearing a red
"GM" monogram. Glamorous and self-assured: voluminous naturally light
golden-blonde hair with movement, looking straight into the camera with a
knowing, mischievous expression, one eyebrow slightly raised, a half-smile
that says she knows something you don't. Bold red lipstick, a small beauty
mark above the right corner of her lip, gold hoop earrings. Slender,
confident figure — slim waist, defined cheekbones — with a generous bust,
in an elegant form-fitting navy blue (#013369) dress with
a low but tasteful neckline, and a red (#D50A0A) press-credential lanyard.
Shallow depth of field, stadium-light bokeh, 85mm lens, crisp broadcast
photography, professional color grade. She looks like the most feared
gossip columnist in Mexican sports television. She is an original fictional
character and must not resemble any real celebrity or journalist.
```

## VARIACIÓN B — foto para avatar de video (la que consume el pipeline)

Las herramientas de avatar (HeyGen/Hedra) piden: frente a cámara, luz
pareja, boca cerrada, fondo limpio, hombros arriba. Esta es la foto
CANÓNICA del pipeline, no el retrato de estadio:

```
Front-facing head-and-shoulders portrait of the same fictional character
Miroslava (use the attached reference image; keep her face IDENTICAL):
looking directly at the camera, mouth closed with a subtle confident smile,
even soft studio lighting, plain dark navy seamless background, sharp
focus on the face, no motion blur, no microphone, hair tidy over the
shoulders, broadcast-TV promotional headshot style, 4k detail.
```

## VARIACIÓN C — set de noticiero (para thumbnails / intro del video)

```
The same fictional character Miroslava (use the attached reference image;
keep her face IDENTICAL) seated at a sleek sports-news anchor desk, navy
and red studio lighting, a large screen behind her showing a navy shield
logo with a red "GM" monogram and eight white stars, papers in hand,
mid-report expression, broadcast television still frame, 16:9.
```

## Receta de consistencia

1. ~~Generar el PROMPT MAESTRO hasta aprobar UNA imagen.~~ HECHO — la
   referencia eterna ya vive en `data/intel/brand/miroslava-ref.png`.
2. Toda imagen futura se genera ADJUNTANDO esa referencia + "keep her face
   identical to the reference". Nunca redescribirla de cero: cada
   redescripción es una cara nueva.
3. La variación B aprobada se guarda como
   `data/intel/brand/miroslava-avatar.png` — es la que consume el pipeline
   de video y NO se regenera (regenerarla = otra "actriz" cada semana).
