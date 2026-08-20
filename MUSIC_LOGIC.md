# MUSIC_LOGIC.md

Cómo está implementado el sistema musical y de contrapunto de ChordWeaver.
Describe el estado actual del código, no un diseño deseado.

Archivos involucrados: `engine/theory.py`, `engine/style.py`, `engine/fitness.py`,
`engine/voicing.py`, `engine/passing.py`, `engine/flourish.py`, `engine/harmony.py`,
y la construcción del espacio de búsqueda en `engine/ga.py`.

---

## 1. Representación de notas

**Una nota es un entero MIDI.** No hay clase `Note`. C4 = 60 (`engine/theory.py:8-12`).

| Concepto | Implementación |
|---|---|
| Altura | `int` MIDI |
| Pitch class | `midi % 12` (`pitch_class()`, `theory.py:39`) |
| Octava | `midi // 12 - 1` (`octave_of()`, `theory.py:44`) |
| Nombre | `note_name()` `theory.py:49` — usa `SHARP_NAMES` o `FLAT_NAMES` |
| Parseo | `parse_note_name()` `theory.py:55`, `parse_pitch_class()` `theory.py:71` |

Un acorde en un instante es una **lista de enteros ordenada de grave a agudo**:
`chords[i][v]` = altura de la voz `v` en el acorde `i`. Ese es el tipo que atraviesa todo
el motor; `fitness.evaluate` recibe exactamente eso.

### La escritura (spelling) está separada de la altura

`spell_pitch()` (`theory.py:82`) decide letra + alteración + octava para MusicXML.
No se puede inferir del semitono solo: 3 semitonos sobre C es Eb como tercera menor pero
D# como novena aumentada. Por eso lee el **tamaño diatónico del grado del acorde**
(`_DEGREE_DIATONIC_STEPS`, `theory.py:134`) y solo cae al intervalo cuando no hay grado
disponible (notas elegidas a mano en el piano).

Detalle: la octava sigue a la *letra*, no al sonido — B#3 suena como C4 pero se escribe en
la octava 3 (`theory.py:114-120`).

### Acordes

`Chord` (`theory.py:266`) = símbolo + `root_pc` + `root_letter` + lista de `ChordTone` +
bajo opcional (acordes con barra, `C/G`).

`ChordTone` (`theory.py:252`) = `semitones` sobre la fundamental (0-11, las compuestas se
reducen) + `role` + `degree` impreso. Los roles son cinco: `ROLE_ROOT`, `ROLE_THIRD`,
`ROLE_FIFTH`, `ROLE_SEVENTH`, `ROLE_EXTENSION` (`theory.py:245-249`). **La tercera y la
séptima son `is_essential`** y nunca se omiten (`theory.py:261`).

El parser (`parse_chord`, `theory.py:499`) resuelve: fundamental con alteraciones, ~60
calidades (`QUALITY_TEMPLATES`, `theory.py:322`), alias (`QUALITY_ALIASES`), alteraciones
sufijas (`ALTERATION_TONES`) y bajo con barra. Una alteración **reemplaza** al grado que
ocupa la misma ranura, no se apila: `C7b5` pierde la quinta justa (`_SLOT_GROUPS`,
`theory.py:583`).

Particularidad del parser: la mayúscula importa en exactamente un lugar. Una `m` sola es
menor y una `M` sola es mayor, así que `CM7` ≠ `Cm7`; pero `maj7`, `Maj7` y `MAJ7` son lo
mismo. La regla implementada es "la letra es sensible a mayúsculas mientras no la siga otra
letra" (`_is_case_sensitive_token`, `theory.py:463`).

---

## 2. Representación de voces

Dos tipos, deliberadamente distintos:

- **`VoiceType`** (`theory.py:150`, congelado) — entrada del catálogo con su tesitura
  cómoda. El catálogo tiene seis: B, Bar, T, A, MS, S (`VOICE_CATALOG`, `theory.py:172`).
  Los rangos son los "cómodos" y no los extremos profesionales, a propósito: el AG trata
  salirse de rango como falla dura, y un rango demasiado ancho vuelve la restricción
  decorativa.
- **`VoicePart`** (`theory.py:190`, mutable) — la voz concreta de *esta* pieza: un tipo del
  catálogo más un rango efectivo que el usuario puede ensanchar o angostar.

`build_voice_parts()` (`theory.py:217`) **ordena por la nota grave del catálogo**, y de ahí
sale un invariante del que depende todo el motor:

> **`voices[0]` y `chord[0]` son siempre el bajo.**

Lo usan la clave de Fa en el exportado, `_spacing_excess` (que exime al bajo),
`bass_contrary_reward`, `bass_consonance_violations`, `perfect_consonance_reward`,
`direct_perfect_violation` y el pineado de acordes con barra. Romper el orden rompe todo
eso en silencio.

Las voces duplicadas se desambiguan a "Soprano 1" / "Soprano 2" (`theory.py:227-237`).

`VoicePart.candidates_for_pitch_class()` (`theory.py:212`) es lo que genera el espacio de
búsqueda: todas las alturas MIDI de una pitch class dentro del rango de esa voz.

---

## 3. Representación de intervalos

**No existe un tipo intervalo.** Todo es aritmética entera de semitonos, en dos idiomas que
conviene no confundir:

| Forma | Significado | Dónde |
|---|---|---|
| `b - a` (con signo) | movimiento melódico, dirección incluida | saltos, movimiento, tendencia |
| `(b - a) % 12` | intervalo armónico reducido a una octava | paralelas, consonancia, disonancia |
| `abs(b - a)` | tamaño melódico sin dirección | tritono melódico, salto máximo |

Consecuencia de reducir módulo 12: una **doceava cuenta como quinta** y una **octava como
unísono** en todos los chequeos armónicos. Es intencional para las paralelas, pero significa
que ningún chequeo armónico distingue simple de compuesto.

Los nombres diatónicos de intervalo aparecen en un solo lugar, para el bajo cifrado:
`_GENERIC_INTERVAL` (`theory.py:673`), `figured_bass()` (`theory.py:679`) e
`intervals_above_bass()` (`theory.py:748`). Es presentación, no evaluación — **el
contrapunto nunca consulta estas funciones.**

`figured_bass` sí distingue cuarta aumentada de quinta disminuida, leyendo los grados del
acorde en vez de los semitonos (`_sizes_from_degrees`, `theory.py:713`), y devuelve `None`
—cayendo al conteo por semitonos— cuando los grados no son confiables, que es el caso de un
acorde armado nota por nota en el piano.

Constantes con nombre: `PERFECT_FIFTH = 7`, `OCTAVE = 12`, `TRITONE = 6`
(`fitness.py:53-55`), `MINOR_NINTH = 13` (`style.py:51`).

---

## 4. Consonancia y disonancia

**No hay una definición única.** Hay tres criterios distintos, cada uno para su propósito, y
no coinciden entre sí. Esto es lo más fácil de malinterpretar del módulo.

### a) Consonancia sobre el bajo — `CONSONANT_ABOVE_BASS` (`style.py:375`)

```
{0, 3, 4, 7, 8, 9, 10, 11}
```

Consonantes: unísono/octava, 3ª menor y mayor, 5ª justa, 6ª menor y mayor, **y ambas
séptimas**. Disonantes por ausencia: 2ª menor (1), 2ª mayor (2), **4ª justa (5)** y
tritono (6).

Dos decisiones explícitas y documentadas:

- **La cuarta justa está ausente a propósito.** Contra el bajo se trata como disonancia que
  necesita preparación — que es exactamente por qué un 6/4 no puede cerrar una frase.
- **Las séptimas cuentan como consonantes**, contra la práctica estricta del bajo cifrado.
  La razón está en `style.py:369-374`: la regla juzga *cómo se dispone* el acorde, y la
  séptima es parte del acorde que el usuario pidió. Cerrar en Cmaj7 pone una séptima sobre
  el bajo en toda disposición salvo inversión, así que cobrarla medía la elección de acorde
  del usuario, no el trabajo del algoritmo.

Se mide **solo desde el bajo hacia arriba**, no entre voces vecinas: en una disposición
3-5-1 el bajo canta la tercera, y desde ahí a la quinta hay una tercera y a la fundamental
una sexta, ambas consonantes (`bass_consonance_violations`, `style.py:378`).

Y se aplica **solo al primer y último acorde** (`cadence_consonance_penalty`,
`style.py:472`). Todo lo del medio es libre.

**Este criterio no distingue inversiones, y por eso hay una regla aparte.** Sobre la tercera
de un Cmaj7 las voces superiores forman tercera, quinta y sexta: todas consonantes. O sea
que 3-5-7-1 empataba con 1-3-5-7 en cero disonancias y después ganaba por ser más compacto.
`root_position_penalty` (`style.py:402`) cobra cuando el bajo de un acorde de reposo no canta
la fundamental, con su propio peso `weight_root_position` — separado porque el jazz mantiene
su peso de consonancia deliberadamente bajo por las séptimas, y reusar ese número dejaba las
inversiones costando demasiado poco.

**Y solo desde 4 voces.** En una textura a 3 la mejor disposición es 3-5-1, con la quinta y la
octava sobre la tercera, no la tercera y la quinta apretadas sobre la fundamental. No hay voz
sobrante ahí, así que la regla se apaga entera por debajo de 4 (`style.py:415`).

### b) Disonancia entre cualquier par de voces — `harmonic_dissonance_penalty` (`style.py:167`)

Penaliza intervalos reducidos en `(1, 2, 10, 11)`: segundas y séptimas, entre **cualquier**
par de voces. Solo lo usa el perfil gregoriano (`weight_harmonic_dissonance=26.0`).

**Contradice al criterio (a) sobre las séptimas**: acá son disonancias, allá son consonantes.
No es un bug — son reglas con propósitos distintos (una juzga la disposición en los puntos
de reposo, otra aproxima la preparación/resolución modal que el motor no modela porque
escribe acordes en bloque, `style.py:172-174`). Pero conviene saberlo antes de "unificar"
las dos listas.

### c) Novena menor — `minor_ninth_penalty` (`style.py:147`)

El test de *avoid note* del jazz. Busca el intervalo **exacto 13** sin reducir (no `% 12`),
y **exime el caso en que la nota inferior es la fundamental**, donde ese intervalo es el
color característico b9. Solo lo usa el perfil de jazz (`weight_minor_ninth=45.0`).

### d) Recompensa de consonancias perfectas — `perfect_consonance_reward` (`style.py:440`)

Premia `(0, 5, 7)` sobre el bajo — octava, **cuarta** y quinta. Peso negativo. Solo
gregoriano (`-22.0`), y es lo que le da el sonido de organum.

Notar que **incluye la cuarta, que el criterio (a) considera disonante**, y ambas reglas
están activas a la vez en el perfil gregoriano. La tensión es deliberada en el sentido de
que responden a tradiciones distintas, pero es un punto real de fricción entre términos.

---

## 5. Movimiento: paralelo, contrario, oblicuo, directo

**No existe un clasificador general de los cuatro tipos de movimiento.** No hay función que
reciba dos transiciones y devuelva "contrario"/"oblicuo"/"similar". Cada regla implementa la
condición que necesita, inline.

### Paralelo — `parallel_interval_violation()` (`fitness.py:398`)

Devuelve `(quinta_paralela, octava_paralela)` para **un par de voces**. Exige tres cosas
simultáneas:

1. el intervalo reducido **antes** es 7 (quinta) o 0 (octava/unísono),
2. el intervalo reducido **después** es el mismo,
3. **ambas voces se mueven, y en la misma dirección**.

Dos voces sosteniendo una quinta sin moverse no es quinta paralela, y una quinta alcanzada
por movimiento contrario tampoco (`fitness.py:406-413`).

Se evalúa sobre **todos los pares de voces**, no solo los adyacentes
(`fitness.py:642-654`), así que en 6 voces son 15 pares por transición.

Unísono y octava son el mismo caso (ambos dan `% 12 == 0`).

### Contrario — `_contrary_pairs()` (`fitness.py:858`)

`movements[i] * movements[j] < 0` sobre todos los pares. Una voz quieta da producto 0, así
que **el movimiento oblicuo no cuenta como contrario**. Peso `weight_contrary_bonus`,
negativo (recompensa).

Variante contra el bajo: `bass_contrary_reward()` (`style.py:305`) — premia cada voz
superior que se mueve en dirección opuesta al bajo. Si el bajo no se mueve, devuelve 0 sin
más; si una voz superior no se mueve, se la saltea.

### Oblicuo — **no se detecta ni se nombra en ninguna parte**

Existe solo por omisión: una voz con `motion == 0` queda exenta de las paralelas, del premio
contrario, de la penalización de tendencia y de la compensación de salto. El único lugar
donde se lo menciona es un comentario en `harmony.py:1310` describiendo una cadencia
prefabricada donde las voces superiores se sostienen.

### Directo / oculto — `direct_perfect_violation()` (`fitness.py:433`)

Quinta u octava alcanzada por movimiento similar **entre las voces extremas**
(`0` y `voice_count - 1`), y **solo cuando la voz superior llega por salto** (`> 2`
semitonos). Es penalización ponderada, nunca dura — "hasta Bach la rompe"
(`fitness.py:444`). Clásico 25.0, coral 35.0, gregoriano y jazz 0.

### Cruce vs. solapamiento

Dos cosas distintas, en archivos distintos:

- **Cruce** (`_crossing_count`, `fitness.py:823`) — *dentro* de un acorde: pares
  **adyacentes** fuera de orden. Restricción **dura** por defecto en los cuatro géneros
  (`forbid_voice_crossing=True`, `fitness.py:83`). El comentario explica por qué no es una
  preferencia: como penalización ponderada el optimizador compra un cruce cada vez que le
  ahorra unos semitonos.
- **Solapamiento** (`voice_overlap_count`, `style.py:190`) — *entre* acordes contiguos:
  ningún acorde está desordenado por sí mismo, pero una voz pasa por donde su vecina acababa
  de estar. Siempre ponderado, nunca duro.

---

## 6. Cómo se validan las reglas

Todo pasa por **`fitness.evaluate()`** (`fitness.py:530`). Firma:
`evaluate(chords, settings, explain=False) -> FitnessBreakdown`.

**El fitness es un coste: menor es mejor, el AG minimiza.**

### Dos niveles

**Duras** — anulan el cromosoma: `valid = False`, `total = INFINITE_COST`, y **`return`
inmediato**. Nunca aparecen en un resultado.

**Ponderadas** — se acumulan en los campos de `FitnessBreakdown` y el AG las negocia.

Consecuencia del `return` temprano: cuando un candidato es inválido **el desglose queda
incompleto** y `violation` reporta solo la *primera* infracción encontrada, en el orden en
que están escritos los chequeos. No es un informe exhaustivo de todo lo que está mal.

### Orden de los chequeos duros

Por acorde (`fitness.py:551-584`):
1. rango vocal (`range_violations`) — **siempre dura, no es opcional**
2. tritono armónico, si `forbid_harmonic_tritone`
3. cobertura: las pitch classes de `required_pitch_classes` deben sonar
4. cruce de voces, si `forbid_voice_crossing`

Por transición (`fitness.py:636-654`):
5. tritono melódico, si `forbid_melodic_tritone`
6. quintas paralelas, si `forbid_parallel_fifths`
7. octavas paralelas, si `forbid_parallel_octaves`

Al final (`fitness.py:729-738`):
8. consonancia sobre el bajo en primer y último acorde, **solo si**
   `cadence_consonance_required` (por defecto `False` en los cuatro géneros)

La cobertura (3) es dura por una razón concreta explicada en `fitness.py:366-369`: como el
AG puede darle cualquier nota del acorde a cualquier voz, nada más le impide dejar caer la
tercera de todos los acordes para ahorrar movimiento.

### Los dos multiplicadores finales

Al cierre (`fitness.py:747-764`) los términos se agrupan y se multiplican:

- **`motion_emphasis`** × (`motion` + `leaps` + `static_repeat`)
- **`style_emphasis`** × (`style` + `crossing` + `spacing` + `contrary_bonus` + `stepwise` +
  `span` + `tessitura` + `direct_perfect` + `cadence`)

`total = motion_group + style_group`. Ambos multiplicadores valen 1.0 por defecto; el
usuario desliza el balance sin tener que entender ningún peso individual.

**`harmony` y `passing` no están en ninguno de los dos grupos.** `evaluate` los deja en 0 y
se suman después, sin multiplicar, en `ga.py:1129` y `ga.py:1136`. Un cambio en las
emphases no los afecta.

### Dónde se arma `RunSettings`

`session.build_settings()` (`session.py:142`) toma el perfil del género y le aplica los
overrides del usuario vía `dataclasses.replace` — solo los campos que existen en
`GenreProfile`, el resto se descarta silenciosamente.

`required_pitch_classes`, `chord_contexts` y `colour_pitch_classes` **no** se arman ahí: se
reconstruyen por candidato en `ga.py:1077-1092` (`settings_for`), porque dependen de *qué*
acorde eligió ese cromosoma en el modo generativo.

---

## 7. Catálogo de reglas

`ChordContext` (`style.py:54`) precomputa por acorde: `root_pc`, `third_pc`, `fifth_pc`,
`seventh_pc`, `tension_pcs` e `is_dominant`. Todas las reglas de estilo trabajan sobre
pitch classes, así que cada chequeo es un test de pertenencia o una resta chica.

`is_dominant` = tercera mayor (4) **y** séptima menor (10) (`style.py:99`). De ahí sale
`leading_tone_pc`, que es la tercera **solo si el acorde es dominante** (`style.py:78-80`):
la sensible se define funcionalmente, no por posición en la escala.

### Reglas duras (conmutables)

| Regla | Función | Ubicación |
|---|---|---|
| Rango vocal | `range_violations` | `fitness.py:475` |
| Cobertura del acorde | inline | `fitness.py:568-577` |
| Cruce de voces | `_crossing_count` | `fitness.py:823` |
| Tritono melódico | `has_melodic_tritone` | `fitness.py:460` |
| Tritono armónico | `has_harmonic_tritone` | `fitness.py:465` |
| Quintas paralelas | `parallel_interval_violation` | `fitness.py:398` |
| Octavas paralelas | idem | `fitness.py:398` |
| Consonancia de cadencia | `bass_consonance_violations` | `style.py:378` |

### Reglas ponderadas — voice leading base (`fitness.py`)

| Peso | Qué mide | Dónde |
|---|---|---|
| `weight_motion` | semitonos de movimiento total — **el término dominante** | `fitness.py:658` |
| `weight_leap` | exceso sobre `max_leap`, por voz | `fitness.py:661-664` |
| `weight_stepwise` | voces que se mueven más de 2 semitonos | `fitness.py:665-668` |
| `weight_crossing` | pares cruzados (si el switch duro está apagado) | `fitness.py:585` |
| `weight_spacing` | exceso sobre `max_upper_spacing` entre voces superiores | `_spacing_excess`, `fitness.py:828` |
| `weight_static_repeat` | dos acordes consecutivos idénticos | `fitness.py:678` |
| `weight_contrary_bonus` | pares en movimiento contrario (negativo) | `fitness.py:681` |
| `weight_span` | exceso del ámbito total sobre `ideal_span` | `fitness.py:625` |
| `weight_tessitura` | voces a menos de `edge_margin` del borde de su rango | `_tessitura_strain`, `fitness.py:844` |
| `weight_direct_fifths` | quinta/octava directa entre extremos | `fitness.py:684` |
| `weight_unison` | pares en la altura idéntica (≠ octava) | `_unison_pairs`, `fitness.py:815` |
| `weight_six_four` | tríada simple con la quinta en el bajo, salvo el 6/4 cadencial | `fitness.py:746-758` |
| `weight_cadential_six_four` | dominante mayor cantada 5-1-3 que resuelve (negativo = buscarla) | `fitness.py:746-751`, `style.py:255` |
| `weight_colour_tone` | voces cantando un color agregado (negativo = buscarlo) | `fitness.py:615` |

### Reglas ponderadas — idiomáticas por género (`style.py`)

| Peso | Regla | Función |
|---|---|---|
| `weight_double_third` | duplicar la tercera | `doubling_penalty` `style.py:114` |
| `weight_double_leading_tone` | duplicar la sensible | idem |
| `weight_double_seventh` | duplicar la séptima | idem |
| `weight_unresolved_seventh` | la 7ª no baja por grado | `tendency_tone_penalty` `style.py:207` |
| `weight_unresolved_leading_tone` | la sensible no sube un semitono | idem |
| `weight_overlap` | solapamiento entre acordes contiguos | `voice_overlap_count` `style.py:190` |
| `weight_common_tone` | notas comunes sostenidas (negativo) | `common_tone_reward` `style.py:269` |
| `weight_bass_contrary` | voces superiores contra el bajo (negativo) | `bass_contrary_reward` `style.py:305` |
| `weight_guide_tone` | guide tones conectando por grado (negativo) | `guide_tone_reward` `style.py:240` |
| `weight_leap_compensation` | salto no respondido en dirección opuesta | `leap_compensation_penalty` `style.py:276` |
| `weight_forbidden_melodic` | intervalos melódicos que el estilo no canta | `melodic_interval_penalty` `style.py:329` |
| `weight_harmonic_dissonance` | 2ªs y 7ªs entre voces | `harmonic_dissonance_penalty` `style.py:167` |
| `weight_minor_ninth` | avoid note del jazz | `minor_ninth_penalty` `style.py:147` |
| `weight_ambitus` | ámbito de una línea en toda la pieza | `ambitus_penalty` `style.py:415` |
| `weight_perfect_consonance` | consonancias perfectas sobre el bajo (negativo) | `perfect_consonance_reward` `style.py:440` |
| `weight_organum_interval` | organalis a intervalo perfecto bajo la principalis (negativo) | `organum_interval_reward` `style.py:477` |
| `weight_organum_parallel` | el par moviéndose en paralelo (negativo) | `organum_parallel_reward` `style.py:499` |
| `weight_cadence_consonance` | disonancia contra el bajo en los extremos | `cadence_consonance_penalty` `style.py:472` |
| `weight_root_position` | acorde de reposo cantado invertido | `root_position_penalty` `style.py:402` |
| `weight_melody_clash` | voz a un semitono de la melodía dada (solo armonizador) | `melody_clash_penalty` `style.py:435` |

**Convención: peso negativo = recompensa.** `guide_tone_reward`, `common_tone_reward`,
`bass_contrary_reward`, `perfect_consonance_reward` y `weight_contrary_bonus` devuelven el
peso tal cual; son los perfiles los que lo ponen en negativo.

### Los cuatro perfiles

Definidos en `fitness.py:197-347`. **Solo cambian pesos y valores por defecto, nunca la
mecánica** (`fitness.py:20-23`) — el evaluador es uno solo para los cuatro.

**`chorale` ya no es un género elegible.** Sigue en `GENRE_PROFILES` porque todas las
búsquedas son por clave, pero lleva `selectable=False` y no recibe tarjeta en la pantalla de
estilos. Se llega a él por el switch *Modo coral*, que aparece en la pantalla de parámetros solo
cuando el estilo es `classical`: `ChordWeaverApp._search_genre()` devuelve `"chorale"`
cuando está prendido, así que el motor corre exactamente el perfil de siempre. `classical`
se muestra como **Barroco**. El historial registra `self.genre_key`, nunca el efectivo, así
que una corrida con el switch prendido queda archivada como barroca.

| | classical (**Barroco**) | chorale (switch) | gregorian | jazz |
|---|---|---|---|---|
| paralelas 5ª/8ª | prohibidas | prohibidas | permitidas | permitidas |
| tritono mel./arm. | libre | libre | **ambos prohibidos** | libre |
| voicings especiales | sí | sí | **no** | sí |
| `max_leap` | 4 | 3 | 2 | 5 |
| `weight_motion` | 10 | 12 | 14 | 10 |
| rasgo dominante | contrario + tendencia | lo mismo, más estricto | grado conjunto, ámbito 5 | guide tones (-34) |

El gregoriano prohíbe **los dos** tritonos por defecto porque *"mi contra fa est diabolus in
musica"* veta el intervalo en sí, no solo el salto: sonando entre dos voces estaba tan
prohibido como cantado (`fitness.py:279-282`).

---

### Organum (solo gregoriano)

La **vox principalis** la elige el usuario; la **vox organalis es siempre la voz inmediata
inferior**, así que un solo índice describe el par: `RunSettings.principalis_voice`
(`fitness.py:436`), y el organalis es `principalis - 1`. En `None` las dos reglas devuelven
0, que es como quedan los otros tres géneros y cualquier corrida sin par declarado.

- **`organum_interval_reward`** (`style.py:477`) — premia que el par suene a un intervalo de
  `PERFECT_ORGANUM_INTERVALS = {0, 5, 7}`: octava/unísono, cuarta o quinta justa.
- **`organum_parallel_reward`** (`style.py:499`) — premia el movimiento paralelo, graduado:
  el premio entero si ambas voces se mueven **la misma cantidad de semitonos** (la sombra
  real), 0.55 si van en la misma dirección por distinto tamaño, y 0.5 si las dos se quedan
  quietas. **No paga nada si el par no aterriza en un intervalo perfecto**, así que el premio
  nunca puede convencer a la búsqueda de hacer segundas paralelas.

La gradación existe porque la armonía no siempre permite la sombra exacta: las dos voces solo
pueden cantar notas del acorde en que están, y a veces la transposición literal simplemente
no está disponible. Pagar también los casos cercanos es lo que hace que la búsqueda persiga
el gesto en vez de abandonarlo donde no puede ser perfecto.

Un escalón intermedio anterior exigía además que el intervalo se conservara. Es inalcanzable
por aritmética —si el intervalo reducido sobrevive y ambas voces se mueven, sus pasos solo
pueden diferir en una octava— y no se activó nunca.

Por dónde entra en cada modo: `JobRequest.principalis_voice` y
`GenerativeRequest.principalis_voice` lo traen de la casilla de la pantalla de voces (radio,
uno solo a la vez, alto por defecto). En el armonizador **no se elige**: es la voz que
escribió el usuario, fijada en `harmonise_melody`. `build_settings` rechaza la voz más grave,
que no tiene ninguna debajo para acompañarla.

---

## 8. Especies de contrapunto

**No hay implementación explícita de las especies.** No existen `species`, `cantus firmus`,
ni ningún módulo o parámetro que las nombre. El contrapunto de especies aparece únicamente
como **fuente citada** en el docstring de `style.py:13-16` y en un comentario en
`fitness.py:215`.

Mapeo honesto de lo que el motor sí hace:

- **Lo que escribe es contrapunto de primera especie**: acordes en bloque, nota contra nota,
  una altura por voz por posición rítmica. No hay independencia rítmica entre voces.
- **`engine/passing.py` acerca algo parecido a la segunda/tercera especie**, pero solo por
  transición y solo si el usuario lo habilita: parte la duración del acorde que se va e
  inserta una nota de paso (`expand_with_passing`, `passing.py:162`). Es la única
  subdivisión rítmica que el motor produce.
- **Nada corresponde a la cuarta especie** (síncopas y retardos) ni a la quinta (florida).
- **No hay cantus firmus.** Ninguna voz tiene estatus especial de línea dada — salvo en el
  modo armonizador, donde la melodía se fija con `pinned_voices` (`ga.py:98-102`), que es
  funcionalmente lo más cerca que el código llega a un cantus firmus.

Las reglas *derivadas* de las especies sí están implementadas, dispersas por `style.py`:
grado conjunto preferido, tritonos y séptimas melódicas vetadas, salto respondido por
movimiento contrario, perfectas paralelas prohibidas.

---

## 9. Comportamientos particulares y excepciones

Ordenados por probabilidad de que alguien los rompa sin querer.

**El repetido estático solo se cobra si la armonía cambió.**
`weight_static_repeat` se aplica únicamente cuando dos acordes suenan idénticos **y**
`_same_harmony()` da falso (`fitness.py:678`, `fitness.py:786`). El usuario elige los
acordes: escribir E7 dos veces es pedir escuchar E7 dos veces, y sostener todas las voces es
la respuesta correcta, no una evasión. Cobrarlo forzaba redisposiciones sin sentido.

**El 6/4 exime a los acordes de séptima de dominante.**
`weight_six_four` requiere `not context.is_dominant` (`fitness.py:756`). Una tríada mayor con
séptima menor sobre su quinta es escritura estándar en la práctica común y en el jazz: es la
segunda inversión ordinaria de un V7, no el 6/4 disonante del que trata la regla.

**Y exime —además premia— al 6/4 cadencial.**
`cadential_six_four` (`style.py:255`) es la única definición que hay del gesto, y la usan las
dos puntas: el evaluador para preferirlo (`fitness.py:746-758`) y el post-proceso para
marcarlo (`flourish.py:357`). Pide tres cosas: tercera mayor, que el acorde resuelva a donde
apunta, y la disposición **5-1-3** desde el bajo.

* **La resolución se lee por grado cuando lo hay y por intervalo cuando no**
  (`is_cadential_dominant`, `style.py:228`). El Generador y el Armonizador eligen los acordes,
  así que la cifra romana viaja en el `ChordContext` (`ga.py:1314`); el Organizador no declara
  ninguna tonalidad —el usuario escribe cifrados sueltos— y ahí lo único afirmable es que un
  acorde mayor cae de quinta sobre el siguiente. Sin ese segundo camino el 6/4 no existía en
  el modo que se llama, justamente, «escribir acordes».
* **La disposición es la mitad de la regla, y era la mitad que faltaba**
  (`six_four_arrangement`, `style.py:206`). Sobre el bajo, 5-1-3 y 5-3-1 dan los mismos dos
  intervalos —una cuarta y una sexta—, así que el chequeo viejo, que comparaba el conjunto de
  intervalos, daba las dos por buenas y la mitad de lo que salía marcado como 6/4 era la otra.
  Se mira el orden de las clases de altura distintas de abajo hacia arriba, así que las
  duplicaciones no molestan: a cuatro voces un re-sol-re-si sigue siendo un 6/4.
* **No alcanza con levantar el castigo: hace falta un premio.** El bajo en la fundamental está
  casi siempre más cerca del acorde de al lado, así que en movimiento puro la disposición
  llana gana siempre. Medido sobre diez progresiones de ocho acordes en barroco a cuatro
  voces: sin premio, el 6/4 aparecía en el 25% de las dominantes que resuelven; con premio, en
  el 65%, y el movimiento medio sube un 1%.

**Sostener una nota nunca penaliza la resolución de tendencia.**
`tendency_tone_penalty` exige `motion != 0` antes de cobrar (`style.py:230`, `style.py:236`).
Un retardo sobre una armonía repetida es normal.

**El espaciado exime el hueco bajo→siguiente voz.**
`_spacing_excess` arranca en `i = 1` (`fitness.py:837`). Un hueco grande sobre el bajo es
normal; entre dos voces superiores deja un agujero en la textura.

**El unísono no es una duplicación.**
`weight_unison = 250.0` por defecto **en los cuatro géneros** (`fitness.py:97`). Dos partes
en la altura idéntica dejan de ser independientes y en la página colapsan en una sola
cabeza. La duplicación a la octava está intacta.

**La fundamental en el bajo se pide solo en los extremos, y tiene dos exenciones.**
`root_position_penalty` (`style.py:402`) no cobra cuando el acorde trae barra —el usuario ya
nombró su bajo y cobrarle sería pelearle— ni cuando la fundamental fue omitida, porque
entonces no hay nada que poner abajo. La primera exención sale de `ChordContext.bass_pc`,
que `from_chord` lee de `chord.bass_pc`; la segunda se resuelve mirando si la fundamental
suena en alguna voz. Una inversión en medio de la frase es escritura ordinaria y no se cobra.

**El semitono contra la melodía se mide en alturas, no en pitch classes.**
`melody_clash_penalty` (`style.py:435`) cobra cada voz que suena a un semitono exacto de la
nota que escribió el usuario, ×4 en el primer y último acorde
(`melody_clash_repose_factor`). La distinción es el punto entero de la regla: un B en la
melodía sobre un Cmaj7 **tiene** que encontrarse con un C, porque el acorde lo exige, así
que cobrar la pitch class sería cobrar la armonía que el usuario ya aceptó. Lo que la
búsqueda sí controla es el registro — bajar ese C una octava convierte el semitono en
séptima, y esa es la disposición que la regla pide. Las novenas menores quedan para
`minor_ninth_penalty`.

Solo se enciende cuando `RunSettings.melody_voice` no es `None` (`fitness.py:411`), y eso
solo pasa en el armonizador, que es el único modo con una línea dada. Los otros dos modos
nunca ven el término, aunque `weight_melody_clash` tenga un valor por defecto compartido.
Cuidado al tocar `ga.settings_for()`: rearma `RunSettings` por candidato y si no propaga
`melody_voice` apaga la regla en silencio.

**El ámbito se mide una vez sobre la pieza entera**, no acorde por acorde
(`ambitus_penalty` se llama fuera del bucle, `fitness.py:723`). Y el umbral gregoriano es
**5 semitonos, no 9**: la auditoría descubrió que con 9 la regla no se activaba nunca porque
los ámbitos reales rondan 5 (`fitness.py:301-305`). Subirlo la desactiva otra vez.

**Los silencios se eliminan antes de buscar.**
`session.generate()` filtra los slots con `is_rest` (`session.py:264`) y el AG solo ve los
acordes que suenan. El voice leading se mide **a través** del silencio como si los dos
acordes fueran contiguos, que es lo que oye un oyente. Los silencios vuelven a aparecer
recién en el exportado (`export.py:212`, `export.py:439`).

**Lo que es diatónico se lee de la música, no de una tonalidad declarada.**
Para las notas de paso, `importer.scale_from_chords()` deriva la escala de los acordes que
la pieza ya usó (`session.py:274`). Una progresión tipeada o importada no tiene tonalidad
declarada, e inferir una y errarle es peor que dejar que los adornos pasen por notas que la
pieza ya sonó.

**Los flourishes corren después de la búsqueda, sobre el ganador.**
`engine/flourish.py` no participa del fitness. La razón está en `flourish.py:6-13`: la
disposición llana siempre es más barata en movimiento puro, así que un flourish solo podía
ganar pagándose, y pagarlo distorsionaba todo lo demás.

Dentro de `flourish.py` hay una asimetría importante: la sexta que esquiva una quinta
paralela **reescribe** notas (`apply_sixth`, `flourish.py:126`), mientras que las cadencias
—ii-V-I, plagal, rota, 6/4 cadencial— **solo se etiquetan**: se reconocen en lo que la
búsqueda ya produjo y no cambian ni una nota (`find_marks`, `flourish.py:240`). El 6/4 es la
excepción parcial: se etiqueta acá como las demás, pero además el evaluador lo premia, porque
no es un adorno agregado sino cuál de las disposiciones del mismo acorde se elige.

Las marcas se identifican **por nombre de grado, no por función**: `ii-V-I` exige literalmente
ii, V y I, porque hacerlo por función contaba iv-bVII-I como lo mismo, que no es lo que el
nombre significa (`flourish.py:239-243`). Igual la plagal, que exige el cuarto grado
(`flourish.py:277-280`), y la cadencia rota, que exige V→vi (`flourish.py:293-296`).

**Las dominantes aplicadas se cobran aparte, y no son acordes prestados.**
Un `V/x` viaja con `is_borrowed=True` porque no es diatónico, pero `is_applied_dominant`
(`harmony.py:702`) lo separa: la prestada trae el color del modo paralelo, la aplicada es una
tónica pasajera. Por eso el dial de intercambios modales (`weights.borrowed`) no la toca, y el
logro «Después te lo devuelvo» no la cuenta.

Qué grados se ofrecen depende del estilo (`session.py:613-624`): el jazz apunta a todos, el
barroco y el coral **solo al V del V**, y el gregoriano a ninguno. Cuánto aparece no es una
probabilidad sino tres pesos de la gramática: `applied_dominant` se cobra **al entrar**
—llegar al V/V sale más caro que llegar al ii, y eso es lo que lo vuelve ocasional—,
`applied_resolution` premia que baje una quinta, y `applied_escape` castiga que no lo haga.
Medido sobre 24 corridas de ocho acordes: aparece en ~35% de las piezas y resuelve al V en el
100% de los casos. Un V/V en el último acorde no resuelve por definición, así que
`progression_cost` lo cobra fuera del bucle de pares (`harmony.py:584-590`).

**El eólico no existe como modo aparte.** Es nota por nota la menor natural, y ofrecer los dos
era ofrecer la misma escala dos veces con nombres distintos: quedó `"minor"` solo
(`harmony.py:48-59`).

**El AG puede darle cualquier nota del acorde a cualquier voz.**
`ChordRequirement` (`voicing.py:85`) entrega un *pool* de pitch classes permitidas más las
requeridas, no una asignación rígida voz-por-voz. `voicing.py:91-94` explica por qué es
imprescindible: fijar la asignación obliga a las notas duplicadas a quedar encadenadas en
octavas entre sí, lo que vuelve inevitables las octavas paralelas entre acordes consecutivos
y deja a los perfiles clásico y coral **sin ninguna solución legal**.

**El cromosoma es siempre armónicamente correcto por construcción.**
`CandidateTable` (`ga.py:208`) precomputa, por cada (slot, opción, voz), todas las alturas
alcanzables. Una solución puede ser musicalmente mala, nunca equivocada sobre qué notas
pertenecen al acorde. Si una celda queda vacía la progresión es incantable como está
configurada, y el error dice qué voz no llega a qué acorde (`describe_problems`,
`ga.py:292`).

**Las prioridades de omisión y duplicación son tablas fijas** (`voicing.py:40-54`). Se
omite: 5ª, luego 1ª, luego 9/11/13/6. Nunca la 3ª ni la 7ª. Se duplica en ciclo
fundamental → quinta → fundamental → tercera, y de ahí en más solo fundamental y quinta
(`_doubling_sequence`, `voicing.py:399`) — con seis voces sobre una tríada, tres
fundamentales y dos quintas leen mucho mejor que duplicar dos veces la tercera mayor.
Una quinta alterada (b5/#5) **no** es inerte y se trata como color, no como descarte libre.

**Apagar los voicings especiales cambia la armonía, no solo los pesos.**
`strip_special_voicings()` (`voicing.py:125`) reduce el acorde a tríada o séptima *antes* de
todo lo demás, así que un Cmaj9 se escribe como Cmaj7 en modo gregoriano. Excepción: los
acordes sus esconden su tercera en un grado "especial", y se dejan intactos en vez de
reducirlos a una quinta pelada (`voicing.py:138-141`).

Con `allow_special_voicings` apagado también se apaga el relleno de color
(`voicing.py:179`). Sin ese cierre el gregoriano seguía brotando novenas por la otra puerta:
se le quitaban los colores al acorde y después el relleno se los volvía a poner.

**El color agregado es requerido, no meramente permitido.**
Cuando el plan agrega una nota de color para llenar una voz sobrante, su pitch class entra
en `required_pitch_classes`, no solo en `allowed` (`voicing.py:194-200`). Dejarlo como
permitido entregaba la decisión a la búsqueda, y la búsqueda siempre decía que no: una
duplicación se alcanza con menos movimiento que una novena, así que la voz sobrante volvía a
duplicar y prender el color no cambiaba nada audible. `weight_colour_tone` solo no alcanza
para ganarle a `weight_motion`.

Cuando no hay lugar para todo, el color es lo primero que se descarta — es decoración que
eligió el motor, no parte del acorde que pidió el usuario. El descarte ocurre en dos
lugares: `voicing.py:209-216` cuando los grados requeridos superan la cantidad de voces, y
`session._make_room_for_melody()` (`session.py:1005`) cuando la melodía del armonizador
necesita el asiento. Ahí el orden es color → quinta → fundamental.

**Los acordes disminuidos no reciben notas de color** (`_special_fill_tones`,
`voicing.py:366`): ya están construidos enteramente de tensión y apilarles novenas los
convierte en barro. Reciben una duplicación.

**Una nota de paso no tiene que estar *entre* las dos notas del acorde**
(`passing_candidates`, `passing.py:91`). Subir un tono y bajar dos antes de asentarse es
movimiento melódico ordinario; restringir la nota al espacio entre los extremos descartaba
la mayor parte de lo que los cantantes realmente hacen. Lo que importa es que ambos tramos
sean cantables (`max_leg = 4`).

**Solo una voz adorna por transición.** `rules.simultaneous = 200.0` (`passing.py:65`): dos
voces saliendo del acorde a la vez dejan de sonar a decoración y suenan a una segunda
armonía en conflicto.

**Las notas de paso aparecen por densidad, no por mutación.** `density = 0.45`
(`passing.py:56`): dejadas a la mutación eran rarísimas, porque el buen voice leading ya es
por grado conjunto y casi nunca deja un hueco que llenar.

---

**La partitura del armonizador no se escribe desde el cromosoma.**
`export.MelodyLine` (`export.py`) lleva la línea del usuario con su ritmo real, por compás,
y tanto `build_musicxml` como `build_midi` escriben esa voz desde ahí en vez de desde la
solución. La razón: la búsqueda ve la melodía **muestreada a una nota por acorde** —el
tiempo fuerte es donde se decide la armonía, y ese es el ritmo contra el que se juzga el
contrapunto—, pero la partitura no puede heredar ese muestreo. Ocho corcheas salían como
cinco notas tenidas, que es otra melodía.

`harmonize.bar_events()` arma los eventos de cada compás rellenando los huecos con silencios
y recortando lo que se pase del compás: un compás cuyas duraciones no suman lo rechaza
cualquier editor de partituras. `ScoreSpec.melody` queda en `None` en los otros dos modos,
que siguen escribiendo todas las voces desde el cromosoma como siempre.

---

**El acorde cae en el tiempo fuerte, salvo que alguien pida lo contrario.**
`harmony_spots()` (`harmonize.py:202`) reparte cada compás entre sus tiempos fuertes, y hay
tres cosas que pueden abrir un lugar donde el compás no lo puso: la última nota de la
melodía, la sensible de la penúltima (`pin_leading_tone`, `harmonize.py:505`) y **una nota
que el usuario marcó** (`MelodyNote.must_harmonise`). Las tres pasan por la misma maniobra,
`spot_for_note()` (`harmonize.py:279`), y las tres tienen que dejar el compás sumando:

* El lugar que se parte se queda con lo que hay **hasta** la nota y el nuevo con **todo el
  resto**, no con la duración de la nota. Los lugares reparten el compás entre ellos, así
  que el sobrante no puede quedar sin dueño.
* Cuando lo que queda por delante de la nota es más corto que `MIN_DURATION` no se puede
  partir --- sería un acorde más corto que cualquiera que este programa escribe --- así que
  el lugar se corre entero y ese pedazo se lo lleva **el lugar anterior**. Corriéndolo sin
  dárselo a nadie, el compás perdía ese pedazo: en 6/8, con una nota marcada en 1,75, dos
  tiempos y tres cuartos en vez de tres.
* Una nota marcada trae además su `required_note`, así que `choose_note_for_spot` no puede
  preferirle la nota siguiente: ese lugar existe por ella.

`planned_notes()` (`harmonize.py:627`) hace la misma cuenta sin elegir acordes ---los mismos
lugares, la misma nota por lugar--- y por eso es determinista: es lo que el pentagrama pinta
de dorado mientras el usuario escribe.

---

## 10. Armonía vs. contrapunto

`engine/harmony.py` (58 KB) es un módulo **aparte** y responde otra pregunta: qué acordes
existen en una tonalidad y qué tan idiomática es una sucesión. **El modo manual no lo toca**
— ahí el usuario ya decidió la armonía.

Lo relevante para el contrapunto es solo la frontera:

- `ChordContext.from_chord()` (`style.py:82`) es lo único que cruza del mundo armónico al
  contrapuntístico.
- El coste de progresión (`progression_cost`, `harmony.py:487`) entra al total en
  `ga.py:1129`, **fuera** de los grupos de emphasis.
- `flourish.py` importa `function_of`, `TONIC`, `SUBDOMINANT`, `DOMINANT` de `harmony.py`
  para etiquetar cadencias.

Las tablas de movimiento de fundamental están en `harmony.py:393-431`
(`FUNCTIONAL_ROOT_MOTION`, `MODAL_ROOT_MOTION`, `JAZZ_ROOT_MOTION`), y las gramáticas
funcionales por género en `harmony.py:767-845`.

---

## 11. Cómo verificar un cambio en la lógica musical

`python tests.py` (195 tests) cubre parseo de cifrados, detección de restricciones y la
promesa de que una regla encendida nunca aparece violada en un resultado devuelto.

Pero **cambiar un peso no rompe ningún test**: solo cambia el resultado musical de todas las
generaciones, en silencio. La verificación real es `python audit.py`, que corre cada género
contra un control —la misma búsqueda con todos los pesos de estilo apagados— y mide el
output contra reglas que el fitness nunca ve como un solo número. Las cifras de referencia
están tabuladas en `README.md`.
