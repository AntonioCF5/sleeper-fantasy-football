# WAIVERS DEL 23-SEP-2026 — Gallamijos League (redraft)

Waivers **por prioridad rodante** (`waiver_type: 0`), no FAAB. 72 claims de 14 equipos
sobre 22 jugadores; el API devuelve también los FALLIDOS, que la app solo cuenta.

## Orden de prioridad que estuvo vigente hoy
*(reconstruido del orden de proceso; los 4 equipos sin claims no aparecen)*

1. rodrigodiaz — lugar 8 de la tabla (1-1)
2. canogutierrez — lugar 6 de la tabla (1-1)
3. alealvarez7 — lugar 5 de la tabla (2-0)
4. aledlg — lugar 16 de la tabla (0-2)
5. drw25 — lugar 7 de la tabla (1-1)
6. hectordavid1989TRC — lugar 18 de la tabla (0-2)
7. davidcruz77 — lugar 17 de la tabla (0-2)
8. Gallaghers4 — lugar 3 de la tabla (2-0)
9. ElGeneral4 — lugar 14 de la tabla (0-2)
10. Jro91 — lugar 11 de la tabla (1-1)
11. elmijo — lugar 9 de la tabla (1-1)
12. FilledUpRivers — lugar 13 de la tabla (1-1)
13. Tibu23 — lugar 2 de la tabla (2-0)
14. charlyae17 — lugar 12 de la tabla (1-1)

## Si la prioridad se reseteara por TABLA (último elige primero)

1. hectordavid1989TRC — lugar 18 (0-2)
2. davidcruz77 — lugar 17 (0-2)
3. aledlg — lugar 16 (0-2)
4. tbarg91 — lugar 15 (0-2)
5. ElGeneral4 — lugar 14 (0-2)
6. FilledUpRivers — lugar 13 (1-1)
7. charlyae17 — lugar 12 (1-1)
8. Jro91 — lugar 11 (1-1)
9. Jebusf — lugar 10 (1-1)
10. elmijo — lugar 9 (1-1)
11. rodrigodiaz — lugar 8 (1-1)
12. drw25 — lugar 7 (1-1)
13. canogutierrez — lugar 6 (1-1)
14. alealvarez7 — lugar 5 (2-0)
15. maudlgarza — lugar 4 (2-0)
16. Gallaghers4 — lugar 3 (2-0)
17. Tibu23 — lugar 2 (2-0)
18. jffaya — lugar 1 (2-0)

## Resultado comparado — solo jugadores disputados

| Jugador | Se lo llevó | Con prioridad por tabla | |
|---|---|---|---|
| **Adonai Mitchell** (8 claims) | canogutierrez (lugar 6) | FilledUpRivers (lugar 13) | 🔄 |
| **Jonah Coleman** (8 claims) | alealvarez7 (lugar 5) | ElGeneral4 (lugar 14) | 🔄 |
| **Emanuel Wilson** (7 claims) | drw25 (lugar 7) | charlyae17 (lugar 12) | 🔄 |
| **Keon Coleman** (5 claims) | hectordavid1989TRC (lugar 18) | hectordavid1989TRC (lugar 18) | = |
| **Oronde Gadsden** (4 claims) | Gallaghers4 (lugar 3) | Jro91 (lugar 11) | 🔄 |
| **Devin Lloyd** (4 claims) | davidcruz77 (lugar 17) | davidcruz77 (lugar 17) | = |
| **LV** (2 claims) | ElGeneral4 (lugar 14) | Tibu23 (lugar 2) | 🔄 |
| **Ted Hurst** (2 claims) | Jro91 (lugar 11) | Jro91 (lugar 11) | = |
| **Roman Wilson** (2 claims) | elmijo (lugar 9) | elmijo (lugar 9) | = |
| **Quentin Lake** (2 claims) | aledlg (lugar 16) | drw25 (lugar 7) | 🔄 |
| **Dax Hill** (2 claims) | drw25 (lugar 7) | davidcruz77 (lugar 17) | 🔄 |

**7 de 11 disputados cambiarían de dueño.**

Nota de método: la simulación respeta la regla de waivers rodadas — el que gana
un claim se va al final de la fila dentro de la misma corrida, así que un equipo
con prioridad alta no se lleva todo. El orden interno de cada equipo (a cuál
jugador le tiene más ganas) se toma del `seq` real de sus claims.

## A QUIÉN LE TOCABA CADA JUGADOR (sin tope de bajas)

Decisión del user: la baja de un claim perdido **no existe en el API** (53 de 53
fallidos vienen sin `drops`), así que no se estima — se le pregunta a cada
manager a quién habría tirado. Aquí va el reparto puro por prioridad de tabla,
respetando solo la regla de rodada (el que gana pasa al final de la fila).

### Lista para consultar, manager por manager

| Manager | Lugar | Le tocaba | Hoy se lo llevó |
|---|---|---|---|
| hectordavid1989TRC | 18 | Keon Coleman | *(ya era suyo)* |
| **davidcruz77** | 17 | Devin Lloyd *(suyo)* · **Dax Hill** · **Bobby Okereke** · Lukas Van Ness *(suyo)* | drw25 · nadie |
| aledlg | 16 | Derrick Barnes | *(ya era suyo)* |
| **ElGeneral4** | 14 | **Jonah Coleman** · Jameis Winston *(suyo)* · **IND DEF** | alealvarez7 · nadie |
| **FilledUpRivers** | 13 | **Adonai Mitchell** | canogutierrez |
| **charlyae17** | 12 | **Emanuel Wilson** | drw25 |
| **Jro91** | 11 | **Oronde Gadsden** · Ted Hurst *(suyo)* · **Ryan Flournoy** | Gallaghers4 · nadie |
| elmijo | 9 | Roman Wilson | *(ya era suyo)* |
| rodrigodiaz | 8 | Dexter Lawrence | *(ya era suyo)* |
| **drw25** | 7 | **Quentin Lake** | aledlg |
| canogutierrez | 6 | **nada** | pierde a Adonai Mitchell |
| alealvarez7 | 5 | Zach Ertz *(suyo)* | pierde a Jonah Coleman |
| Gallaghers4 | 3 | Cade Otton *(suyo)* | pierde a Oronde Gadsden |
| **Tibu23** | 2 | **LV DEF** · Kaleb Johnson *(suyo)* · Brian Burns *(suyo)* | ElGeneral4 |

### Los 7 que cambian de manos

1. **Jonah Coleman** → ElGeneral4 (era de alealvarez7)
2. **Adonai Mitchell** → FilledUpRivers (era de canogutierrez)
3. **Emanuel Wilson** → charlyae17 (era de drw25)
4. **Oronde Gadsden** → Jro91 (era de Gallaghers4)
5. **Dax Hill** → davidcruz77 (era de drw25)
6. **Quentin Lake** → drw25 (era de aledlg)
7. **LV (DEF)** → Tibu23 (era de ElGeneral4)

Más dos que hoy nadie alcanzó y sí se repartirían: **Bobby Okereke** a
davidcruz77, **Ryan Flournoy** a Jro91, e **IND (DEF)** a ElGeneral4.

**Pendiente de consultar a cada manager:** a quién habría tirado por cada
jugador nuevo. Todos están 17/17, así que cada alta exige una baja.

## Validación del motor (y el caso Dax Hill)

Objeción del user: *"¿por qué le tocaba Dax Hill a david si él ya tenía a
Devin Lloyd reclamado? El que reclama pasa a ser la última prioridad y va
avanzando conforme otros reclaman."*

**La regla es exactamente esa, y así está implementada.** Para probarlo, corrí
el motor con la prioridad REAL de hoy y comparé contra los ganadores reales:

| Modelo | Reproduce |
|---|---|
| **Uno por turno, el que gana se va al final** | **19 de 19** ✅ |
| Cada equipo resuelve todos sus claims de un jale | 17 de 19 ❌ |

El modelo bueno acierta el 100%. El otro falla justo en Emanuel Wilson y
Devin Lloyd. Así que la mecánica de rotación está bien.

### Por qué Dax Hill termina en davidcruz77

| Paso | Qué pasa | davidcruz77 | drw25 |
|---|---|---|---|
| 2 | davidcruz77 (#1) toma **Devin Lloyd** → al final | #1 → **#18** | #11 |
| 10 | drw25 (#3) toma **Quentin Lake** → al final | #11 | #3 → **#18** |
| 14 | davidcruz77 (#7) toma **Dax Hill** | **#7** | #15 |

La clave está en el paso 10: **drw25 sí tuvo el turno antes que davidcruz77**
(iba #3 contra #11), pero lo gastó en Quentin Lake, no en Dax Hill. ¿Por qué?
Porque en su propio orden de claims drw25 puso Quentin Lake (`seq` 48) por
delante de Dax Hill (`seq` 49) — es la preferencia que él mismo mandó. Al
ganar se fue al final, y para cuando Dax Hill volvió a estar en juego,
davidcruz77 ya había subido de #18 a #7 (doce equipos ganaron detrás de él) y
drw25 había caído a #15.

O sea: davidcruz77 no se "saltó" la fila — drw25 eligió otro jugador con su
turno y quedó detrás. El orden interno de cada manager (qué jugador quiere
más) sale del `seq` real de sus claims, no de mi criterio.
