# MUSIC_LOGIC.md — contexto compacto

Este documento resume el **estado actual implementado** de ChordWeaver. Describe el código real, no un diseño ideal. Su objetivo es conservar los invariantes que no deben romperse al modificar el motor musical/contrapuntístico.

## 1. Modelo de datos e invariantes

### Notas y acordes
- Una nota es un **entero MIDI**. No existe `Note`. C4 = 60.
- `pitch_class(midi) = midi % 12`; `octave = midi // 12 - 1`.
- `spell_pitch()` separa **altura** de **spelling** (letra/alteración/octava). El spelling usa el grado diatónico del acorde cuando existe. La octava escrita sigue a la **letra**, no al sonido; por ejemplo B#3 se escribe en octava 3 aunque suene como C4.
- Un acorde en un instante es una **lista ordenada de alturas MIDI, grave→agudo**: `chords[i][v]`.
- `Chord = símbolo + root_pc + root_letter + ChordTone[] + bass_pc opcional`.
- `ChordTone` guarda semitonos sobre la raíz, `role` y `degree`. Tercera y séptima son `is_essential` y no se omiten.
- Roles: root, third, fifth, seventh, extension.
- El parser resuelve raíz, ~60 calidades, alias, alteraciones y slash bass. Una alteración **reemplaza** el grado que ocupa la misma ranura; no se apila. Ej.: `C7b5` reemplaza la quinta justa.
- Caso de mayúsculas: una `m` sola significa menor y `M` sola mayor; `maj7/Maj7/MAJ7` son equivalentes.

### Voces
- Hay dos conceptos:
  - `VoiceType`: entrada congelada del catálogo, con tesitura cómoda. Catálogo: B, Bar, T, A, MS, S.
  - `VoicePart`: voz concreta, con tipo + rango efectivo configurable.
- `build_voice_parts()` ordena por la nota grave del catálogo.
- **Invariante crítico:** `voices[0]` y `chord[0]` son siempre el **bajo**.
- Muchísimas reglas dependen de ese orden: clave de Fa, spacing, bass contrary, bass consonance, perfect consonance, direct perfect y slash chords.
- Si dos voces son del mismo tipo se desambiguan como “Soprano 1/2”.
- `candidates_for_pitch_class()` genera todas las alturas MIDI de una pitch class dentro del rango de la voz; esto define gran parte del espacio de búsqueda.

### Intervalos
No existe un tipo `Interval`.
- `b-a`: movimiento melódico con dirección.
- `(b-a)%12`: intervalo armónico reducido a una octava.
- `abs(b-a)`: tamaño melódico sin dirección.
- Consecuencia: en chequeos armónicos una octava cuenta como unísono y una doceava como quinta.
- Las funciones de bajo cifrado sí usan grados diatónicos; **no participan en la evaluación contrapuntística**.

## 2. Consonancia: hay varias definiciones y NO deben unificarse

### Consonancia contra el bajo
`CONSONANT_ABOVE_BASS = {0,3,4,7,8,9,10,11}`.
- Incluye 1/8, 3ª menor/mayor, 5ª, 6ª menor/mayor y **séptimas**.
- Deja fuera 2ªs, tritono y **4ª justa**.
- Solo mira el bajo, no voces vecinas.
- Solo se aplica al **primer y último acorde** cuando `cadence_consonance_required=True`.
- Por debajo de 4 voces, `root_position_penalty` se apaga.
- `root_position_penalty` castiga inversiones en puntos de reposo, salvo slash chords y casos donde la fundamental está omitida.

### Disonancia entre cualquier par
`harmonic_dissonance_penalty()` penaliza `{1,2,10,11}` entre cualquier par de voces.
- Solo tiene peso real en gregoriano.
- Aquí las séptimas **sí son disonancias**, aunque arriba las séptimas se consideran consonantes.
- Esto es deliberado: son reglas para propósitos distintos.

### Semitono entre voces vecinas
`adjacent_semitone_clashes()` cuenta pares de voces **vecinas** a un semitono real (sin `%12`).
- Peso `weight_semitone_clash`: 80 en todos los estilos, 50 en jazz.
- Se cobra en **todos** los acordes, no solo en los de reposo (`repose_dissonances` sigue usándolo aparte para el primero y el último).
- Solo entre vecinas: una séptima entre bajo y soprano es el acorde, no un choque.
- Intervalo real y no clase: la novena menor son las mismas dos notas a una octava, y es justamente la disposición que arregla el roce; la mira `weight_minor_ninth`.
- **Se apaga cuando hay melodía dada** (`RunSettings.melody_voice is not None`): ahí el roce contra la línea ya lo cobra `weight_melody_clash`, con su propio factor en los extremos.

### Novena menor
`minor_ninth_penalty()` busca el intervalo exacto de **13 semitonos**, sin `%12`.
- Exime cuando la nota inferior es la fundamental (b9 como color característico).
- Solo jazz.

### Consonancias perfectas / organum
- `perfect_consonance_reward()` en gregoriano premia `{0,5,7}` sobre el bajo; incluye cuarta.
- `organum_interval_reward()` premia un par declarado principalis/organalis en `{0,5,7}`.
- El premio de organum paralelo solo paga si al final aterriza en intervalo perfecto.

**Importante:** hay tensiones deliberadas entre estas listas. No asumir que existe una única definición de “consonante”.

## 3. Movimiento contrapuntístico

No hay un clasificador general de “paralelo/contrario/oblicuo/directo”. Cada regla implementa su propia condición.

### Paralelas
`parallel_interval_violation()`:
1. intervalo reducido anterior = 7 o 0,
2. intervalo reducido posterior = el mismo,
3. ambas voces se mueven,
4. ambas se mueven en la misma dirección.

Se revisan **todos los pares de voces**, no solo adyacentes.

### Contrario
- `_contrary_pairs()`: `mov_i * mov_j < 0`.
- Una voz quieta da 0, por lo que **oblicuo no cuenta como contrario**.
- `bass_contrary_reward()` premia voces superiores que van contra el bajo; si el bajo no se mueve, devuelve 0.

### Oblicuo
No se detecta ni se nombra como categoría general. Una voz con movimiento 0 simplemente queda exenta de varias reglas.

### Directo/oculto
`direct_perfect_violation()`:
- quinta/octava perfecta alcanzada entre **voces extremas**,
- movimiento similar,
- voz superior llega por **salto > 2 semitonos**.
- Es una penalización ponderada, no una restricción dura.

### Cruce vs solapamiento
- **Cruce:** dentro de un mismo acorde, pares adyacentes fuera de orden. Por defecto es **duro**.
- **Solapamiento:** entre acordes contiguos, una voz pasa por el lugar donde estaba su vecina. Siempre ponderado.

## 4. `fitness.evaluate()` y jerarquía de restricciones

Firma: `evaluate(chords, settings, explain=False) -> FitnessBreakdown`.
- El fitness es un **coste**: menor = mejor.
- **Restricciones duras:** `valid=False`, `total=INFINITE_COST` y retorno inmediato.
- **Ponderadas:** se acumulan y el AG las negocia.
- El retorno temprano implica que para un candidato inválido el desglose es **incompleto** y `violation` muestra solo la primera infracción encontrada.

Orden de duras:
1. rango vocal (siempre duro),
2. tritono armónico si está prohibido,
3. cobertura de pitch classes requeridas,
4. cruce si está prohibido,
5. tritono melódico si está prohibido,
6. quintas paralelas si están prohibidas,
7. octavas paralelas si están prohibidas,
8. consonancia de cadencia si está activada.

### Multiplicadores
Al final:
- `motion_emphasis * (motion + leaps + static_repeat)`
- `style_emphasis * (style + crossing + spacing + contrary + stepwise + span + tessitura + direct_perfect + cadence)`
- Ambos valen 1.0 por defecto.

`harmony` y `passing` quedan fuera de estos grupos y se suman después sin multiplicador.

## 5. Catálogo de reglas ponderadas

### Voice leading base
- `weight_motion`: movimiento total; es el término dominante.
- `weight_leap`: exceso sobre `max_leap`.
- `weight_stepwise`: voces que se mueven >2 semitonos.
- `weight_crossing`: cruce si se desactiva la dura.
- `weight_spacing`: exceso de spacing entre voces superiores.
- `weight_static_repeat`: dos acordes idénticos consecutivos, pero **solo si cambió la armonía**; repetir E7→E7 no se castiga como reescritura.
- `weight_contrary_bonus`: recompensa movimiento contrario (peso negativo).
- `weight_span`: exceso del ámbito total.
- `weight_tessitura`: cercanía al borde del rango.
- `weight_direct_fifths`: directas entre extremos.
- `weight_unison`: alturas idénticas; unísono no es duplicación.
- `weight_six_four`: 6/4 no cadencial.
- `weight_cadential_six_four`: premio al 6/4 cadencial.
- `weight_colour_tone`: recompensa/preferencia por tonos de color.
- Convención: **peso negativo = recompensa**.

### Idiomáticas de estilo
Incluyen duplicación de tercera/sensible/séptima, resolución de sensible y séptima, overlap, common tones, bass contrary, guide tones, compensación de saltos, intervalos melódicos prohibidos, disonancias armónicas, b9, ambitus, consonancias perfectas, organum, cadencia, root position y melody clash.

## 6. Géneros

Un único evaluador sirve a todos: los perfiles cambian **pesos y defaults**, no la mecánica.
- `classical` se muestra como **Barroco**.
- `chorale` sigue en perfiles pero no es seleccionable como tarjeta; se activa como “Modo coral” desde classical.
- El historial guarda la clave elegida (`genre_key`), no el perfil efectivo.

Resumen:
- **Barroco/classical:** paralelas prohibidas; `max_leap=4`; pesa especialmente movimiento contrario/tendencia.
- **Coral/chorale:** aún más estricto; `max_leap=3`.
- **Gregorian:** paralelas permitidas, ambos tritonos prohibidos, sin voicings especiales, `max_leap=2`, preferencia por grado conjunto/ámbito y recompensas tipo organum.
- **Jazz:** paralelas permitidas, tritonos libres, voicings especiales sí, `max_leap=5`, guide tones muy favorecidos.

## 7. Organum (solo gregoriano)

- El usuario elige `principalis`; la `organalis` es siempre la voz inmediatamente inferior (`principalis - 1`).
- Si `principalis=None`, las reglas de organum devuelven 0.
- No puede elegirse la voz más grave porque no tiene una voz debajo.
- `organum_interval_reward`: premia 0/5/7.
- `organum_parallel_reward`: premio máximo si ambas voces se mueven la misma cantidad, 0.55 si misma dirección pero distinto tamaño, 0.5 si ambas quietas.
- No premia paralelismo si el destino no es perfecto.

## 8. Especies de contrapunto

**No existe implementación explícita de “species”.**
- El motor principal produce algo equivalente a **primera especie**: acordes en bloque, una altura por voz y posición.
- `passing.py` puede insertar una nota de paso en una transición si está habilitado; es la única subdivisión rítmica.
- No hay cuarta especie ni quinta especie.
- No hay `cantus firmus`.
- En el armonizador, la melodía fijada con `pinned_voices` es lo más cercano funcionalmente a una línea dada.

## 9. Voicing y espacio de búsqueda

- `ChordRequirement` proporciona un **pool de pitch classes permitidas + requeridas**, no una asignación fija voz↔nota.
- Esto permite que el AG encuentre asignaciones que eviten paralelas inevitables.
- `CandidateTable` precomputa para cada `(slot, option, voice)` todas las alturas posibles.
- Por construcción, un cromosoma es armónicamente correcto; puede ser musicalmente malo.
- Si alguna celda queda vacía, la progresión es incantable con esa configuración.

### Omisión / duplicación
Prioridad fija de omisión:
1. quinta,
2. fundamental,
3. 9/11/13/6.
Nunca se omiten 3ª ni 7ª.
Duplicación típica:
`root → fifth → root → third`, y después principalmente root/fifth.

Una quinta alterada (`b5/#5`) cuenta como **color**, no como descarte libre.

### Voicings especiales
- `allow_special_voicings=False` reduce antes de todo a tríada o séptima.
- Excepción: sus no se reducen a una quinta pelada.
- Al apagar voicings especiales también se apaga el relleno de color.
- Los colores agregados para rellenar voces sobrantes entran en `required_pitch_classes`, no solo en `allowed`; si fueran solo permitidos, el AG preferiría duplicar por menor movimiento.
- Cuando no entra todo, el color se descarta antes que quinta y fundamental.
- Acordes disminuidos no reciben color extra.

## 10. Passing / adornos

- Un adorno es una **figura de una a tres notas** (`passing.MAX_FIGURE`), no una nota suelta. Se arma como un camino de `from_pitch` a `to_pitch` (`passing._figures`): cada tramo tiene que entrar en `max_leg` y a lo sumo **uno** puede ser salto (`MAX_LEAPS`). De esas dos reglas salen solas el relleno (una nota llena una tercera, dos una cuarta, tres una quinta), la bordadura, la bordadura doble, el grupeto y el escape.
- La grilla `Chromosome.passing[slot][voz]` guarda `None`, un entero o una tupla. **Todo el que la lea tiene que pasar por `passing.figure()`**, que normaliza las tres formas: el entero suelto sigue llegando desde los historiales ya guardados.
- El largo se sortea **antes** que la figura (`passing.pick_figure`): parejo entre todas salían casi siempre las de tres notas, porque hay muchas más combinaciones de tres.
- La cola del acorde se parte en tantos pedazos iguales como notas tenga la figura. La suma del compás no cambia nunca: se reparte la misma cola.
- El premio por tramo decae (`PassingRules.decay = 0.62`): la corrida de tres tiene que valer más que la nota suelta y bastante menos que tres notas sueltas, o la búsqueda cambia todos los adornos por corridas.
- Una nota de paso **no tiene que quedar entre** las dos notas del acorde; basta que ambos movimientos sean cantables.
- `max_leg = 4`.
- Solo **una voz** adorna por transición; `rules.simultaneous = 200.0`.
- Densidad por defecto `0.45`. La barra de la interfaz decide tres cosas: el sorteo de siembra/mutación, el tope (`passing.max_for_density`, de 1 a 12) **y** cuánto pesan las figuras largas en el sorteo (`FIGURE_WEIGHTS`). Fijando solo el sorteo, moverla no cambiaba cuántos adornos se escuchaban.
- Tope duro `HARD_MAX_PASSING = 12` por pieza, aplicado en `ga._prune_stale_passing`, y se cuentan **transiciones adornadas, no notas**: una figura de tres notas es un adorno. `crowding` (140) desalienta pasarse del tope de la barra, pero es un costo comprable; el tope duro no.
- **No hay adorno saliendo de una dominante aplicada ni de un intercambio modal.** El acorde ya es el efecto y el adorno lo tapa con notas que contradicen la alteración por la que se lo eligió. Una modulación no cuenta: viaja en el mismo `is_borrowed` pero su acorde es diatónico de otra tonalidad.
- Durante una modulación el adorno diatónico se elige contra la escala del **área visitada** (`harmony.modulation_scales`), no contra la de casa. Manda el área del acorde del que **sale** el adorno, porque suena en su cola.
- `flourish.py` corre **después** de la búsqueda, sobre el ganador; no participa del fitness.
- `apply_sixth()` puede reescribir notas para esquivar paralelas.
- Las cadencias/ii-V-I/plagal/rota/6-4 normalmente solo se **etiquetan**, no reescriben notas.
- El 6/4 cadencial es especial: se etiqueta y además se favorece desde el fitness.
- Las marcas se reconocen por **grado literal**, no por función.

## 11. 6/4 cadencial

Definición actual:
- tercera mayor,
- el acorde resuelve al acorde objetivo,
- disposición **5-1-3 desde el bajo**.
- Sección de resolución puede usar grado diatónico cuando está disponible; si no, cae al intervalo.
- En modo manual no hay tonalidad declarada, así que solo puede inferirse un mayor descendiendo una quinta al siguiente acorde.
- La disposición importa: 5-1-3 y 5-3-1 no son equivalentes aunque compartan intervalos.
- Duplicaciones no lo invalidan si el orden de alturas distintas cumple la forma.
- Solo quitar el castigo no bastaba: el premio explícito al 6/4 es lo que hizo que apareciera mucho más.

## 12. Reglas/excepciones que conviene recordar al tocar el código

- Sostener una nota (`motion==0`) no resuelve la tendencia y no recibe castigo de `tendency_tone_penalty`.
- El spacing ignora el hueco **bajo→voz siguiente**; empieza entre voces superiores.
- Unísono (misma altura) no es duplicación a la octava y tiene una penalización muy alta.
- `root_position_penalty` solo importa en extremos, con exenciones para slash chords y fundamentales omitidas.
- `melody_clash_penalty` mide **alturas reales**, no pitch classes; solo existe en armonizador y pondera más los extremos.
- `ambitus_penalty` se mide sobre **toda la pieza**, no acorde por acorde. En gregoriano el umbral actual es 5 semitonos.
- Los silencios se eliminan antes de la búsqueda: el voice leading se calcula a través del silencio. Los silencios reaparecen en el exportado.
- Lo “diatónico” se deriva de los acordes que ya aparecen; no se declara una tonalidad para los adornos.
- `V/x` se distingue de acorde prestado: las dominantes aplicadas (`is_applied_dominant`) no usan el dial de borrowed.
- El eólico no es un modo separado: se representa como `minor`.
- Los adornos se aplican al ganador, no al cromosoma.

## 13. Armonía vs contrapunto

`engine/harmony.py` es un módulo separado:
- decide qué acordes existen en una tonalidad y el coste de las sucesiones;
- el modo manual **no lo usa** para decidir la armonía, porque el usuario ya la dio.
- La frontera principal es `ChordContext.from_chord()`.
- `progression_cost` entra al total fuera de los grupos de emphasis.
- `flourish.py` usa funciones armónicas para reconocer/etiquetar cadencias.

## 13 bis. Modulación: las tres soluciones tienen que viajar distinto

El plan de viaje (`Chromosome.mod_plan`: destino, compás de entrada, compás de
salida) se sortea en el sembrado, se hereda entero de un padre en el cruce y
**no muta nunca**. Sin nada que lo contrarreste, el plan más barato gana todos
los torneos desde la primera generación y pasa lo siguiente:

- el relleno de población clona del plantel de elite y se lleva ~2 de cada 3
  plazas por generación, así que un plantel todo del mismo plan inunda la
  población con ese plan;
- los demás planes siguen en el salón de la fama pero **no vuelven a
  cruzarse**: quedan con el costo del cromosoma con el que se los sembró.

Medido, 16 compases, `classical`, misma semilla: el ganador bajaba de 2312 a
1324 entre 150 y 600 generaciones mientras los otros dos planes se quedaban
clavados en 10436 y 11127 **sin moverse un punto**. Y no eran peores: dándole
a cada destino la búsqueda entera llegan a la misma altura (V 2983, vi 1165,
IV 2708).

Lo que lo sostiene son tres piezas que van juntas; sacar cualquiera devuelve
las tres soluciones modulando igual:

1. `ga._plan_floor` — el mejor costo de cada uno de los mejores `solutions_wanted`
   planes. Los que quedan afuera compiten con su costo pelado y se apagan.
2. `ga._tournament(..., floor)` — cada cromosoma compite contra el mejor **de
   su propio plan**, así ningún plan monopoliza la selección.
3. `ga._elites` — el plantel de elite lleva al mejor de cada plan, no a los
   mejores en bruto. Es lo que hace que el relleno clone de todos los planes.
4. `ga._pick_diverse` separa **primero por plan** y recién después por acordes
   y por alturas: adónde viaja la pieza es la decisión más audible y ofrecerla
   una sola vez es no ofrecerla.

Sin modulación (`mod_plan` en `None` en todos) `_plan_floor` devuelve vacío y
las cuatro se comportan como antes.

Los destinos no son los de `GENRE_MODULATION` tal cual: `harmony.available_targets`
los recorta por los dos interruptores y **por el modo en el que está la pieza**,
y `session.generate_random` los deja ya recortados en `ModulationSettings.targets`
antes de armar el pool. Tiene que estar recortado ahí y no más abajo porque
`choose_modulation_plan` sortea sobre esa lista antes de que se elija un solo
acorde: un destino sin acordes en el pool ---uno modal cuando el usuario sólo
pidió tonalidades--- se lleva el plan y la pieza se queda en casa con la
modulación pedida. El recorte por modo es lo que hace que en menor el cambio de
modo sea a mayor: ofrecer «a menor» a una pieza que ya está en menor no es
ningún viaje. La menor armónica cuenta como menor.

## 14. Armonizador y exportación

- La búsqueda ve la melodía del usuario **muestreada a una nota por acorde** para decidir la armonía/contrapunto.
- La partitura NO se genera desde el cromosoma: `export.MelodyLine` conserva la melodía real, con su ritmo.
- `build_musicxml` y `build_midi` escriben la melodía desde `MelodyLine`.
- `harmony_spots()` coloca acordes por tiempos fuertes, con puntos adicionales para última nota, sensible penúltima o nota marcada por el usuario.
- `spot_for_note()` debe mantener la suma exacta del compás; si el fragmento previo es demasiado corto, el lugar se desplaza y el sobrante se asigna al lugar anterior.
- `planned_notes()` hace la misma distribución sin elegir acordes y por eso es determinista.
- `MelodyNote.skip_harmonise` es el pedido contrario a `must_harmonise`: el usuario apagó el dorado que el programa había puesto. `drop_skipped_spots()` saca ese lugar y le da su duración a un vecino **del mismo compás** —el anterior, o el siguiente estirado hacia atrás—; un lugar sin vecino en su compás se queda, y su nota sigue dorada.
- Las dos marcas son excluyentes en la interfaz: el click rota entre dorado y apagado, no entre tres estados.
- **Notas fuera de la escala** (`out_of_scale`: fuera de `bar.mode` sobre `bar.tonic`). Regla, en **alturas reales** y sólo para notas de al menos `MIN_DURATION`:
  - sube un semitono a la siguiente → la nota se marca sola y su acorde es V/x de la nota de llegada (V7/x con `with_sevenths`; V a secas si la llegada es la tónica). En `LEADING_APPROACH_GENRES` (barroco, jazz) sale en cambio vii°/x (vii°7 en jazz) con `LEADING_APPROACH_CHANCE`;
  - baja un semitono → sólo en jazz (`TRITONE_APPROACH_GENRES`): subV7/x. En los demás estilos no hay dominante de la nota de llegada que contenga un semitono arriba de ella, así que no cumple la regla;
  - la nota de llegada recibe su propio lugar y `RESOLUTION_REWARD` para el acorde con esa fundamental (con -140 la ventana de azar de 55 dejaba pasar la resolución engañosa una de cada tres).
- La nota cromática que no cumple la regla no se marca sola; si cae en tiempo fuerte o el usuario la marca, se le ofrecen `chromatic_options` (dominantes aplicadas, préstamos, subV en jazz) que la **contienen**, sin el sorteo de `_borrowed_allowed`. Un acorde que la deja afuera paga `CHROMATIC_OUTSIDE`, una aplicada que no resuelve donde apunta `UNRESOLVED_APPLIED` (si no, un Si mayor saltaba a Fa por tener al mi bemol de tercera), y en gregoriano la aplicada paga `APPLIED_IN_MODAL` frente al préstamo.
- Los nombres de esos acordes salen de `_root_name`: el que menos altera, con empate a favor de sostenidos en las dominantes y de bemoles en el subV (Ab7, no G#7; Bb, no A#).
- **Mayor o menor lo decide la nota final** (`key_of_ending`): la armadura dice dos tonalidades y, si la melodía termina en la relativa menor, se armoniza en menor **natural**. Natural y no armónico para que naranja (fuera de la armadura) y cromático (fuera de `bar.mode`) sigan siendo lo mismo; el sol sostenido de La menor entra por la regla de arriba, y `chromatic_options` incluye la dominante de la tónica para cuando no sube. En menor `_pool_for_bar` no suma los préstamos `iv`/`bVII`: ya son de la tonalidad.
- **La nota final lleva un solo acorde** (`harmony_spots`): partida en dos, la redonda del final recibía IV y después I, la cadencia caía un lugar antes y la pieza cerraba V, IV, I.
- **El último acorde va con la fundamental en el bajo** (`session._close_on_the_root`, sólo tríadas): con tres voces y la melodía en la tónica no quedaba voz para la fundamental y casi todo terminaba invertido. Se fija el bajo y, si no entra, se suelta la quinta (1-3-1). `root_position_penalty` sigue eximiendo a menos de cuatro voces; esto es aparte.
- Un préstamo se nombra con la armadura del menor paralelo (`harmony._borrowed_root`): el iv de Fa mayor es Bbm, no A#m.

## 15. Construcción de settings

`session.build_settings()` parte del `GenreProfile` y aplica overrides del usuario con `dataclasses.replace()`. Solo se conservan campos existentes en `GenreProfile`; otros overrides se descartan silenciosamente.

En modo generativo, `required_pitch_classes`, `chord_contexts` y `colour_pitch_classes` se reconstruyen **por candidato** en `ga.settings_for()` porque dependen del acorde elegido.

**Cuidado especial:** `ga.settings_for()` vuelve a construir `RunSettings`; si no propaga una propiedad como `melody_voice`, una regla puede quedar desactivada en silencio.

## 16. Verificación

- `python tests.py`: 527 tests; cubre parseo, restricciones y que una regla activada no aparezca violada en un resultado devuelto.
- Cambiar **pesos** puede alterar toda la música sin romper ningún test.
- Para cambios de lógica musical, `python audit.py` compara cada género contra un control con pesos de estilo apagados.
- Las cifras de referencia viven en `README.md`.

## 17. Checklist mental para cambios peligrosos

Antes de tocar una regla, comprobar:
1. ¿Estoy confundiendo altura MIDI con pitch class?
2. ¿Estoy usando `%12` donde importa distinguir compuesto de simple?
3. ¿Estoy suponiendo que `chord[0]` no es el bajo?
4. ¿Estoy mezclando consonancia contra el bajo con disonancia entre pares?
5. ¿Estoy convirtiendo una preferencia ponderada en restricción dura (o al revés)?
6. ¿Estoy olvidando que el fitness minimiza coste y los pesos negativos son recompensas?
7. ¿Estoy aplicando una regla a todos los géneros cuando en realidad solo un perfil la usa?
8. ¿`ga.settings_for()` conserva el campo nuevo?
9. ¿Estoy evaluando antes o después de `flourish.py`?
10. ¿Necesito correr `tests.py` **y** `audit.py` para verificar un cambio de comportamiento?

## 18. Análisis de una partitura ajena (`engine/analysis.py`)

Va al revés que todo lo demás: la música ya está escrita y lo que falta son los nombres. Es un módulo aparte y **no toca ninguna regla de los otros modos**; lo que reusa lo importa.

### Unidades

- **Compás**: puede cambiar en el medio de la pieza (`Score.metres`). Los compases se recorren uno por uno; el tiempo fuerte de cada uno se mide con el compás que rige **ahí**. Es lo primero de todo porque de ahí sale la unidad con la que se lee un acorde, el peso de cada nota y el nombre de cualquier adorno.
- **Sonoridad**: tramo en el que no cambia ninguna voz. Se corta en cada ataque y en cada final de nota, no sobre una grilla fija.
- Con menos de `MIN_VOICES_FOR_CHORD` (3) voces escritas **no se lee ningún acorde**. Un acorde es una tríada, y con una voz o dos no hay forma de saber cuál de las que las contienen suena. Se cuentan voces y no alturas distintas: un coral que dobla la fundamental y omite la quinta ---lo más común que hay--- no llega a tres alturas en ninguna vertical, y contándolas se quedaba sin análisis. Y el piso es de la pieza entera, no de cada tiempo: aplicado tiempo por tiempo, un compás con tres acordes salía cifrado una sola vez.
- **Segmento**: tramo gobernado por un solo acorde. Se lee **un acorde por tiempo del compás**, no uno por sonoridad, y después se unen los tiempos seguidos que dan la misma lectura.
- Un tiempo que lee mal (`SPLIT_THRESHOLD`) se prueba partido en dos, y sólo se parte si las dos mitades mejoran por `SPLIT_GAIN`.
- Se unen dos segmentos si tienen **la misma fundamental y el mismo bajo**, y uno contiene al otro. Lo segundo es lo que hace que un arpegio cuya séptima llega tarde sea un acorde y no dos.

### Lectura del acorde

Peso de cada clase de altura = duración × peso métrico × 1,35 si es el bajo, y × `ORNAMENT_WEIGHT` si la nota **tiene forma de adorno** (entra y sale por grado conjunto, no dura más que sus vecinas; o es una escapada: entra por grado, sale por salto en la dirección contraria, dura a lo sumo una corchea y cae fuera del tiempo) **y** alguna otra voz sostiene mientras tanto.

También pesa como adorno la **cuarta (o segunda) suspendida que resuelve dentro del mismo tiempo** (`_suspension_inside`, `Sonority.resolving`): el tiempo es la tríada con un retardo, no un sus4. La que dura el tiempo entero y resuelve en el siguiente sigue siendo suspendida. El cifrado sí ve la nota retardada.

Un tiempo cuyo acorde de séptima es la suma de **dos tríadas completas en sus dos mitades** (vi y IV6 en corcheas) se parte en dos, siempre que en la mitad cambien dos voces o alguna salte (`_two_triads`, `_changes_harmony`): una sola voz que se mueve por grado es una resolución, no un acorde nuevo.

La séptima disminuida toma por fundamental la sensible del acorde al que resuelve (`_root_diminished_sevenths`), y el acorde con sexta agregada que no está sobre la tónica ni la dominante se nombra como séptima (`_read_added_sixth`: Fa6 en Do es ii6/5; Do6 en Do se queda).

Puntaje de cada candidato:

```
cubierto − EXTRA_COST·(1 − cubierto) − faltantes − séptima_floja + preferencia
        + SIGNATURE_FIT·(notas del acorde que están en la armadura)
        + ROOT_POSITION_BONUS  (si el bajo es la fundamental)
        − SUSPENDED_OFF_BASS   (suspendida cuyo bajo no es su fundamental)
```

- `MISSING_COST`: tercera 0,30 · fundamental 0,28 · séptima 0,22 · quinta 0,05. La quinta se omite todo el tiempo; la tercera decide la calidad.
- El descuento por nota floja (`SUPPORT_SHARE`) se cobra **sólo a la séptima**. Con las cuatro notas rompía las inversiones: en una textura arpegiada la fundamental de un acorde invertido suena poco por definición, y un V con la tercera en el bajo pasaba a leerse como vii°.
- La armadura sólo desempata lo que las notas no deciden: sin la tercera sonando, re-la-do es Rem7 en una pieza sin alteraciones y Re7 en cuanto el fa sostenido aparece.
- Se ofrece una **segunda lectura** cuando la diferencia es menor que `AMBIGUITY_MARGIN`, o cuando el acorde está invertido y existe una lectura razonable sobre el bajo. La alternativa siempre tiene **otra fundamental**: Lam y Ladim con la quinta ausente no son dos lecturas, son la misma con una nota inventada de dos maneras.

### Cómo se escribe cada nota

La misma altura es un la bemol o un sol sostenido según de qué lado del círculo de quintas esté la pieza, y las partituras que este programa exporta no traen armadura: escriben todo en Do y ponen los accidentes nota por nota. Así que la armadura **se deduce** de lo que suena --- se prueban las quince y gana la que deje menos notas afuera --- y de ella sale la escritura.

Encima de eso, dos reglas que la deducción no puede dar:

- Un acorde ajeno se escribe con la alteración con la que se lo nombra: el que se llama `bVI` va con bemol y el que se llama `#iv` con sostenido.
- El bajo de una inversión se escribe **por su papel en el acorde**: la quinta de un Si con séptima es fa sostenido aunque la pieza vaya llena de bemoles, porque una quinta se cuenta de si a fa.
- Un acorde aplicado se escribe **desde la letra de su destino** (`_spell_towards`): la sensible aplicada una letra abajo y la dominante aplicada cuatro arriba. Con la preferencia de la pieza sola, una armonización en Do con un la bemol leía el vii°/V como Solb disminuido con Rebb en el bajo.

### Tonalidad

Tres evidencias, de mayor a menor peso: la **nota de reposo** (bajo final y último acorde), la **armadura** (arma la lista de candidatos) y **lo que suena** (cuánto material cae en la escala). Más dos correcciones que son las que salvan los fragmentos:

- Si el último acorde tiene una nota ajena a la escala candidata, se descuenta fuerte: la tónica de una tonalidad es diatónica por definición.
- Si la pieza **arranca** en un acorde y **se detiene en la dominante de ese acorde**, gana esa tónica: la frase quedó en semicadencia. Sin esto, `Am - G - F - E` se analizaba en Mi.
- La tercera de Picardía descuenta poco en menor y armónica, y mucho en los modos: un frigio que termina mayor no es un frigio con licencia, es que la tónica era otra. Si la pieza arrancó en esa tónica, la tercera de Picardía no paga además el descuento de "acorde final con nota ajena".
- Una pieza que **abre y cierra en el mismo acorde mayor**, cuyo material cae claramente mejor en la menor de una quinta abajo y que por dentro resuelve su dominante en esa tónica más de una vez, está en esa menor (`_framed_by_dominant`): es el final frigio de los corales.
- **El primer acorde pesa casi tanto como el último.** Una pieza puede empezar en cualquiera, pero la enorme mayoría empieza en el suyo: es lo que instala la tonalidad antes de que haya con qué compararla. Y empezar y terminar en el mismo acorde suma aparte.
- **Un acorde disminuido no reposa**, así que no cobra el premio del acorde final: es el más inestable que hay y ninguna pieza termina en él como tónica. Sin esto, una armonización que se detenía en el séptimo grado se analizaba entera en locrio.

Candidatos: mayor, menor, menor armónica, dórico, mixolidio, frigio, lidio, locrio, con preferencia decreciente en ese orden.

### Función y acordes ajenos

Áreas y grados salen de `harmony.DEGREE_FUNCTION` y `harmony.BORROWED_FUNCTION`; no hay una segunda tabla. En modo menor se tolera la sensible, y **sólo** la sensible: la sexta subida es la menor melódica, y el acorde que la trae es un intercambio modal de manual. El vii° y el vii°7 sobre la sensible son diatónicos (séptimo grado), como el V. El último acorde de una pieza en menor, si es la tónica mayor, es la tercera de Picardía (`I`), no un `V/iv`.

Orden de las preguntas para un acorde que no es de la escala:

1. **Suspendido** (`sus4`, `sus2`, `7sus4`) --- y se dice si la cuarta baja a la tercera sobre la misma fundamental, que es la suspensión resuelta.
2. **Dominante aplicada**: mayor o de séptima, una quinta arriba de un grado de la escala que no sea la tónica. Se nombra por su destino (`V7/V`) y se dice si llega a resolver.
3. **Sensible aplicada**: disminuida, semidisminuida o de séptima disminuida un semitono debajo de un grado.
4. **Sustituto tritonal**: séptima de dominante un semitono arriba del acorde que sigue.
5. **Intercambio modal**: se prueban los modos sobre **la misma tónica** y se dice de cuál viene y qué grado es ahí. La menor melódica se agrega sólo acá (`INTERCHANGE_MODES`), no a `harmony.MODES`, que es lo que el generador ofrece en su menú.
6. Lo que no entra en nada de eso queda como cromatismo suelto.

Varios ajenos seguidos se leen juntos: si existe una tonalidad en la que todos ellos --- más el acorde en el que desembocan --- son diatónicos, es tonicización (hasta `TONICISATION_LIMIT`) o modulación. Si no la hay pero cada uno es la dominante del siguiente, es una **cadena de dominantes**, que es lo contrario de irse de la tonalidad.

### Cadencias

De dos acordes: auténtica perfecta e imperfecta (perfecta = los dos en estado fundamental), rota, plagal, semicadencia y frigia (`iv6 → V`, el bajo baja un semitono). Una dominante que resuelve en otro acorde que reposa (no la tónica ni la dominante de la pieza) es una auténtica **en otra tonalidad**, y el detalle lo dice. Una cadencia necesita **el giro y el reposo**: el acorde de llegada tiene que durar más que la media o terminar la pieza. No hay semicadencia si la dominante sigue de largo hasta una tónica que también reposa --- eso es preparación de una auténtica, no una cadencia propia; si la tónica pasa de largo, es la frase siguiente que arranca y la semicadencia queda.

De varios acordes, leídas de `harmony.SET_PIECES` --- las mismas que el generador puede citar: **frigia** (`i - bVII - bVI - V`), **ciclo de Vivaldi** (`i - iv - bVII - bIII - bVI - ii° - V - i`, dentro de la tonalidad y sin séptima: la cita se escribe a tres voces; al citarla el generador pone cada fundamental en el bajo, `SetPiece.roots_in_bass`, pero acá se reconoce también con inversiones) y **bajo cromático descendente**. Se prueban en las doce alturas y se avisa cuando no aparecen sobre la tónica de la pieza. La cita que **es** una línea de bajo se reconoce por el bajo y por lo que suena encima, no por el nombre del acorde: el cuarto acorde del bajo cromático se lee igual de bien como tónica con el sexto bemol debajo o como séptima mayor sobre ese sexto, y sólo una de las dos lecturas coincide con el nombre que le puso el generador.

### Contrapunto

- **Movimiento** entre cada par de voces: paralelo (misma dirección **y** mismo tamaño de intervalo), directo (misma dirección, otro tamaño), contrario, oblicuo, quieto. El directo no es el paralelo: las quintas ocultas se hacen por directo.
- **Paralelas** y **quintas/octavas ocultas** se preguntan a `fitness.parallel_interval_violation` y `fitness.direct_perfect_violation`. Una paralela entre notas de adorno se informa como dato y no como falta, y lo mismo una que el estilo elegido permite (`forbid_parallel_*` del perfil: jazz y gregoriano).
- Dos voces que se mueven en **tiempos distintos** no hacen paralelas: cuando se mueve la segunda, la primera ya está quieta. Dentro de un mismo tiempo sí cuentan juntas, que es como se escribe un arpegio.
- **Cruce** (dentro de una vertical) y **solapamiento** (entre dos), con las mismas definiciones de la sección 3.
- **Salto de trítono**, voz por voz.
- Sólo se deduplican los hallazgos de vertical: cinco quintas seguidas son cinco faltas, no una.

### Notas ajenas al acorde

Se clasifican por **cómo se llega y cómo se sale**, que es lo único que las separa --- una nota de paso y una bordadura pueden ser la misma altura en el mismo lugar, y lo que las distingue es que una sigue de largo y la otra vuelve. Se reconocen: nota de paso y de paso acentuada, bordadura, doble bordadura, mordente (bordadura brevísima, `MORDENT_MAX`), apoyatura, escapada, cambiata, retardo y retardo ascendente, anticipación, nota pedal, grupeto y anacrusa.

"Acentuada" quiere decir primer tiempo o mitad del compás, no cualquier tiempo: una nota de paso en el segundo tiempo de un cuatro por cuatro no es una nota de paso acentuada. La mitad del compás cuenta sólo si cae en un tiempo (el tercero del 4/4, el segundo pulso del 6/8): en un compás de tres es una corchea a contratiempo.

Las definiciones viven en `ORNAMENT_DEFINITIONS` y son las que se muestran en pantalla: si cambia la detección, cambia la definición.

### Cifrado del bajo continuo

Sale **del acorde**, no de una vertical: en una textura arpegiada la primera vertical no es el acorde. Con una salvedad: la nota que suena al entrar el acorde y no le pertenece --- una cuarta suspendida, una novena --- también se cifra, y lo que el acorde tiene y no llega a sonar se cae de la cifra. Una sola nota así, y sólo en la vertical con la que el acorde entra: con dos o más lo que falla es la lectura del acorde. Tamaños de intervalo sobre el bajo, abreviados como se abrevia --- sin cifra el estado fundamental, `6`, `6/4`, y `7 - 6/5 - 4/3 - 4/2` para la séptima. La tercera y la quinta se dan por sabidas: una séptima a la que le falta la quinta se cifra `7` y no `7/3`, y una tríada a la que le falta la quinta sigue sin llevar número. Lo alterado respecto de la armadura lleva su accidente pegado al número, y una tercera alterada sobre un bajo sin cifra se escribe con el accidente solo. El accidente se resuelve por **la letra** (el tamaño escrito del intervalo) y no por vecindad con la escala: la bemol y sol sostenido suenan igual y no se cifran igual.

### Piedra de toque

`TestAnalysisOfBach` corre los primeros cuatro compases del Preludio en Do mayor BWV 846, importados desde MusicXML, y exige `C - Dm7/C - G7/B - C`, grados `I - ii4/2 - V6/5 - I`, cifrados `"" - 4/2 - 6/5 - ""`, áreas tónica-subdominante-dominante-tónica y cadencia auténtica imperfecta. Es el caso que obligó a casi todas las decisiones de arriba.


**Fuente:** resumen del estado descrito en el `MUSIC_LOGIC.md` aportado, especialmente las secciones de representación, fitness, perfiles, voicing, passing, armonizador y verificación.
