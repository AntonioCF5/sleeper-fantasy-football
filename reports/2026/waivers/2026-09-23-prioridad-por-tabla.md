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

## A QUIÉN LE TOCABA CADA JUGADOR

Decisión del user: la baja de un claim perdido **no existe en el API** (53 de 53
fallidos vienen sin `drops`), así que no se estima — se le pregunta a cada
manager a quién habría tirado.

⚠️ **Corrección (la cachó el user):** en una versión previa repartí a **Bobby
Okereke, Ryan Flournoy e IND (DEF)** como si hubieran quedado libres. No es
cierto. Esos tres claims **fallaron por roster lleno, no por prioridad**:
nadie más los pidió, y el equipo que los pidió ya había gastado todas sus
bajas del día (davidcruz77 2 de 2, Jro91 1 de 1, ElGeneral4 2 de 2). Ese
claim muere igual en cualquier orden de prioridad, así que salen del análisis.
Regla general verificada hoy: **ningún equipo ganó más claims que bajas tenía
disponibles.**

### Los 7 que cambian de manos

| Jugador | Hoy se lo llevó | Le tocaba |
|---|---|---|
| **Jonah Coleman** (RB DEN) | alealvarez7 (5º, 2-0) | **ElGeneral4** (14º) |
| **Adonai Mitchell** (WR NYJ) | canogutierrez (6º) | **FilledUpRivers** (13º) |
| **Emanuel Wilson** (RB SEA) | drw25 (7º) | **charlyae17** (12º) |
| **Oronde Gadsden** (TE LAC) | Gallaghers4 (3º, 2-0) | **Jro91** (11º) |
| **Dax Hill** (DB CIN) | drw25 (7º) | **davidcruz77** (17º) |
| **Quentin Lake** (DB LAR) | aledlg (16º) | **drw25** (7º) |
| **LV** (DEF) | ElGeneral4 (14º) | **Tibu23** (2º) |

Los otros 12 jugadores repartidos hoy no cambian de dueño.

### Para consultar

| Manager | Lugar | Se quedaría con | A quién tiraría |
|---|---|---|---|
| davidcruz77 | 17 | Dax Hill | *preguntar* |
| ElGeneral4 | 14 | Jonah Coleman | *preguntar* |
| FilledUpRivers | 13 | Adonai Mitchell | *preguntar* |
| charlyae17 | 12 | Emanuel Wilson | *preguntar* |
| Jro91 | 11 | Oronde Gadsden | *preguntar* |
| drw25 | 7 | Quentin Lake | *preguntar* |
| Tibu23 | 2 | LV (DEF) | *preguntar* |

Todos están 17/17, así que cada alta exige su baja.
