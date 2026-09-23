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

## Escenario completo: baja = la que cada quien ejecutó DE VERDAD hoy

**Dato duro del API:** Sleeper NO guarda la baja de un claim perdido (53 de 53
fallidos vienen sin `drops`), así que la baja de un claim hipotético no existe.
Solución del user: usar **la baja que cada equipo sí ejecutó hoy**. Y como los
18 equipos están **17/17**, eso impone el tope honesto: *nadie puede ganar más
jugadores que bajas hizo*. Ese cupo cambia el resultado — hay equipos que
ganarían un claim pero no tendrían con qué pagarlo.

| Equipo | Lugar | Cupo | Se queda con | Tirando a |
|---|---|---|---|---|
| hectordavid1989TRC | 18 | 1 | Keon Coleman | Chamarri Conner |
| davidcruz77 | 17 | 2 | Devin Lloyd · **Dax Hill** | Patrick Queen · Donovan Ezeiruaku |
| aledlg | 16 | 2 | Derrick Barnes | Danielle Hunter |
| ElGeneral4 | 14 | 3 | **Jonah Coleman** · Jameis Winston · **IND** | LAC DEF · Demarcus Robinson · Kamari Lassiter |
| FilledUpRivers | 13 | 1 | **Adonai Mitchell** | Darnell Mooney |
| Jro91 | 11 | 1 | **Emanuel Wilson** | Jaxson Dart |
| elmijo | 9 | 1 | **Oronde Gadsden** | Terrel Bernard |
| rodrigodiaz | 8 | 1 | Dexter Lawrence | Montez Sweat |
| drw25 | 7 | 2 | **Quentin Lake** | Jaylin Noel |
| canogutierrez | 6 | 1 | **nada** | — |
| alealvarez7 | 5 | 2 | **solo Zach Ertz** | DeMario Douglas |
| Gallaghers4 | 3 | 2 | Cade Otton | Arvell Reese |
| Tibu23 | 2 | 2 | **LV** · Kaleb Johnson | Ray Davis · Jared Verse |

**charlyae17 desaparece del reparto**: ganaría Emanuel Wilson por prioridad
(lugar 12), pero no ejecutó ninguna baja hoy y está 17/17 — sin cupo, el claim
muere y Emanuel Wilson baja hasta Jro91.

### Los 12 cambios

- **Jonah Coleman**: alealvarez7 (5º) → **ElGeneral4** (14º)
- **Adonai Mitchell**: canogutierrez (6º) → **FilledUpRivers** (13º)
- **Emanuel Wilson**: drw25 (7º) → **Jro91** (11º)
- **Oronde Gadsden**: Gallaghers4 (3º) → **elmijo** (9º)
- **Dax Hill**: drw25 (7º) → **davidcruz77** (17º)
- **Quentin Lake**: aledlg (16º) → **drw25** (7º)
- **LV (DEF)**: ElGeneral4 (14º) → **Tibu23** (2º)
- Se quedan sin dueño (el que los ganó ya gastó su cupo): Brian Burns,
  Lukas Van Ness, Roman Wilson, Ted Hurst
- Aparece **IND (DEF)** para ElGeneral4, que en la realidad no alcanzó

**Los dos punteros pagan la factura**: alealvarez7 (2-0) pierde a Jonah
Coleman y se queda solo con Ertz; canogutierrez se va en blanco. El que más
gana es Rul, último en victorias pero séptimo en puntos, que se llevaría
tres piezas incluyendo al corredor más disputado de la semana.
