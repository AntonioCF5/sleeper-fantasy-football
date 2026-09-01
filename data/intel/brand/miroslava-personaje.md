# MIROSLAVA — identidad visual (para Nano Banana Pro)

Personaje FICTICIO. Regla dura: no debe parecerse a ninguna reportera real —
si una generación recuerda a una persona real, se descarta.

## Rasgos canónicos (fijos en TODA imagen, para consistencia)

- Mexicana, ~35 años, reportera de sideline ex-Liga MX.
- Cabello castaño oscuro chocolate, voluminoso, con movimiento.
- Ojos cafés con mirada cómplice/burlona directo a cámara; una ceja
  ligeramente levantada, media sonrisa de "yo sé algo que tú no".
- **Labios rojos intensos** (el 💋 es su emblema) + **lunar pequeño sobre la
  comisura derecha** (la marca que ancla la consistencia entre generaciones).
- Aretes de aro dorados.
- Figura curvilínea y segura; vestido azul marino **#013369** entallado con
  escote pronunciado pero elegante; gafete de prensa con cordón rojo
  **#D50A0A** (los colores del escudo de la liga).
- Micrófono de broadcast con banderín azul marino y monograma **GM** rojo.
- Tacones (cuando el encuadre los muestra): "vengo del sideline con tacones".

## PROMPT MAESTRO (retrato editorial — la imagen de marca)

```
Photorealistic editorial portrait of Miroslava, a fictional Mexican
sideline sports reporter in her mid-30s, waist-up, standing on the sideline
of a packed American football stadium at golden hour. She holds a
professional broadcast microphone with a navy-blue mic flag bearing a red
"GM" monogram. Glamorous and self-assured: voluminous dark chocolate-brown
hair with movement, warm brown eyes looking straight into the camera with a
knowing, mischievous expression, one eyebrow slightly raised, a half-smile
that says she knows something you don't. Bold red lipstick, a small beauty
mark above the right corner of her lip, gold hoop earrings. Curvaceous,
confident figure in an elegant form-fitting navy blue (#013369) dress with
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

1. Generar el PROMPT MAESTRO hasta aprobar UNA imagen. Esa se guarda como
   `data/intel/brand/miroslava-ref.png` — la referencia eterna.
2. Toda imagen futura se genera ADJUNTANDO esa referencia + "keep her face
   identical to the reference". Nunca redescribirla de cero: cada
   redescripción es una cara nueva.
3. La variación B aprobada se guarda como
   `data/intel/brand/miroslava-avatar.png` — es la que consume el pipeline
   de video y NO se regenera (regenerarla = otra "actriz" cada semana).
