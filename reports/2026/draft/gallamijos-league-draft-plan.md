# LA GALLAMIJOS — Plan de Draft pick por pick
*Domingo 30 de agosto 2026, 13:00 · slot 2 de 18 · snake · 17 rondas · ADP refrescado el mismo día*

## Formato (leído del API)

- **18 equipos, full PPR, 4 pts por TD de pase**, bonos de yardaje (+1 a las 100 yds recepción/acarreo, +2 a las 200), **sin TE premium**
- Titulares (12): QB · RB · RB · WR · WR · TE · FLEX · K · DEF · **DL · LB · DB**
- Banca: **solo 5** · 17 rondas = 17 lugares exactos
- **Mis picks:** 2 · 35 · 38 · 71 · 74 · 107 · 110 · 143 · 146 · 179 · 182 · 215 · 218 · 251 · 254 · 287 · 290

---

## 🚨 La decisión estructural: Chase en el 2 obliga a RB-RB en el turno

Con **Ja'Marr Chase** en el pick 2 (decisión tomada; está a 8 VORP de Nacua,
ruido a ese nivel, y es el WR1 más probado), quedas fuera de todo el tier
elite de RB. Eso hace que el turno pareado 35/38 sea **el momento que define
la temporada**, y los datos dicen algo contraintuitivo:

| Turno | Mejor RB disponible | Mejor WR disponible |
|---|---|---|
| 35 / 38 | Javonte **72.9** | Flowers **104.8** |
| 71 / 74 | Rhamondre **27.1** | Watson **77.7** |
| 107 / 110 | Jordan Mason **9.4** | Reed **59.4** |

El instinto dice "toma los WR que valen 32 puntos más". **Es la trampa.**
Entre el pick 38 y el 71 el RB se cae **46 puntos** y ya nunca se levanta;
el WR baja apenas 27 y se mantiene útil hasta el pick 143.

**Las dos rutas, con números:**
- **RB-RB en 35/38 → WR-WR en 71/74**: 72.9 + 66.8 + 77.7 + 74.3 = **291.7**
- **WR-WR en 35/38 → RB-RB en 71/74**: 104.8 + 101.5 + 27.1 + ~20 = **253.4**

**RB-RB gana por ~38 VORP.** Es exactamente la advertencia del playbook: en
ligas de 18, Zero RB está muerto porque el pool se evapora y el waiver no
puede arreglarlo. Aquí se ve en la tabla.

---

## El plan

**Pick 2 — JA'MARR CHASE (WR).** Decidido. Si Gibbs sigue en el board cuando
te toque, es la única razón para reconsiderar (T1 solo, 203.9).

**Picks 35 y 38 — RB y RB. Los dos.** Sin excepción salvo que caiga un WR
del tier 8 con +25 de valor o más.
- Objetivos: **Javonte Williams** (72.9, ADP 36), **D'Andre Swift** (66.8,
  ADP 52), **Travis Etienne** (62.4, ADP 45), **Kyren Williams** (73.6, ADP
  30 — solo si se desliza).
- Swift y Etienne tienen ADP posterior a tu turno: deberían llegar al 38.

**Picks 71 y 74 — WR y WR.** Aquí el WR sigue fuerte y es donde recuperas.
- **Christian Watson (+34)**, **Parker Washington (+36)**, Brian Thomas (+16).
- Si prefieres cerrar QB temprano, **Dak Prescott** (43.9, ADP 78, **+15**)
  es el único QB con valor positivo en todo el board — cabe en el 74.

**Picks 107 y 110 — QB + TE.**
- **QB: Brock Purdy** (33.0, ADP 123, **+44**) si no tomaste a Dak.
- **TE: Mark Andrews** (29.5, ADP 128, **+42**). Sin TE premium, esperar es
  correcto — no pagues por Bowers/McBride temprano en esta liga.
- **Jayden Reed (+57)** también vive aquí si quieres un WR más.

**Picks 143 y 146 — WR de valor + DEF.**
- **Khalil Shakir (+70)** es el valor más grande del board en ese rango.
- **DEF: Detroit** (17.7, ADP 155) o **Minnesota**. Ojo con el aprendizaje de
  ayer: si aparece **Denver o Houston**, tómalas — el mercado las tiene 1-2
  en sacks y en menos puntos permitidos.

**Picks 179 y 182 — handcuff + K.** Aquí está el rescate de tu sala de RB:
- **Handcuffs disponibles justo en tu ventana**: Brian Robinson (ADP 166),
  Tank Bigsby (178), Keaton Mitchell (185), Pacheco (187), Kaelon Black (214).
  **Con RB1/RB2 modestos, un handcuff que herede un rol es tu boleto.**
- **K: Evan McPherson** (ADP 182, +41) o Tyler Loop (178).

**Picks 215 · 218 · 251 · 254 — DL · LB · DB + relleno obligatorio.**
Los IDP no están en el board (decisión nuestra: un slot, profundidad
infinita). Se llenan aquí y con waivers.

**Picks 287 y 290 — boletos de lotería.** Nunca un veterano de relleno.

---

## Disparadores en vivo (revisar cada turno, en orden)

1. **Faller elite** — 12+ picks debajo de su ADP → tómalo y re-ramifica.
2. **Corrida de RB antes del 35** — si se van 5+ RBs entre el 2 y el 35, el
   plan RB-RB se vuelve obligatorio, no preferente.
3. **Muerte de tier** — cuenta cuántos quedan en el tier actual vs picks
   hasta tu siguiente turno (el turno pareado 35/38 y 71/74 te da dos tiros
   seguidos: puedes vaciar un tier completo).
4. **Corrida de posición** — adelántate una ronda o ignórala; nunca persigas
   hacia un tier muerto.

**Vetos duros:**
- No QB antes del 74. Con 4 pts por TD de pase, Allen (−5 de valor) y Lamar
  (−25) son trampas de precio; el único QB con valor positivo es Dak.
- No TE antes del 107 — esta liga no tiene TE premium.
- No K ni DEF antes del 143. No IDP antes del 215.
- Con 5 de banca, no acumules profundidad joven que no pueda arrancar.

## Command center

**http://localhost:8787** — Draft Room en Gallamijos (slot 2, 17 rondas),
Rankings con 400 filas, tiers ya corregidos y con color. Se refresca solo
cada 5s durante el draft y suena cuando estés en el reloj.
