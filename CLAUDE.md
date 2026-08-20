# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

ChordWeaver es una **aplicación de escritorio** que optimiza el *voice leading* (conducción de voces).
El usuario fija los acordes, las voces y las reglas; un **algoritmo genético** decide qué nota del acorde
canta cada voz y en qué octava, para minimizar el movimiento total respetando las reglas de contrapunto
del género elegido. El AG nunca cambia los acordes ni su orden — sólo el registro y el reparto de notas.

Tres modos de entrada: acordes propios (escritos o importados de MusicXML), generación aleatoria en una
tonalidad, y armonización de una melodía dibujada en un pentagrama.

Encima de todo eso hay un **modo historia**: después de un rato de uso aparece un personaje que ofrece
un pacto, y la respuesta abre uno de tres senderos --- blues, jazz o góspel --- que se recorren usando
el programa normalmente. Ver [Modo historia](#modo-historia).

> **Para tocar cualquier cosa musical, leer primero [`MUSIC_LOGIC.md`](MUSIC_LOGIC.md).** Documenta, con
> referencias `archivo:línea`, cómo se representan notas, voces e intervalos; los tres criterios distintos
> de consonancia y por qué no coinciden; cómo se detecta cada tipo de movimiento; el catálogo completo de
> reglas; y las excepciones que parecen bugs y no lo son.

## Tecnología

- **Python 3.9+**. El motor (`engine/`) es librería estándar pura, sin dependencias.
- **GUI**: `customtkinter` sobre `tkinter` — la única dependencia real.
- **PyInstaller** para empaquetar.
- **Cython, opcional y sólo para compilar** (`build_engine.py`). No es una dependencia del motor:
  los `.py` no se tocan, corren igual sin él, y el `.pyd` es un acelerador que puede no estar. Ver
  [Compilar el motor](#compilar-el-motor-opcional).
- MusicXML, MIDI y el audio WAV se escriben **a mano**, sin librerías musicales, para que el
  ejecutable quede chico y sin dependencias. No introducir `music21`, `mido`, `numpy` etc.
- No es un repositorio git.

## Comandos

```bash
pip install customtkinter          # única dependencia para correr la app

python app.py                      # aplicación con interfaz
python tests.py                    # suite completa del motor (369 tests, unittest)
python tests.py TestClase.test_x   # un solo test (unittest.main acepta el selector)
python audit.py                    # auditoría contrapuntística (lento: corre el AG muchas veces)

python cli.py --chords "Cmaj7 Am7 Dm7 G7" --genre jazz
python cli.py --chords "C Am F G" --genre chorale --voices B,T,A,S --time 3/4 --seed 1
#   ^ `chorale` sigue siendo una clave válida del motor aunque la interfaz
#     ya no la ofrezca como tarjeta de estilo: es el switch "Modo coral",
#     que aparece dentro de Barroco (antes "Clásico").
```

`cli.py` acepta además `--duration --tempo --title --out --format --population --generations` y los
switches de reglas (`--no-parallel-fifths` / `--allow-parallel-fifths`, `--no-tritone`,
`--allow-crossing`, …). Es la vía rápida para probar el motor sin display.

Hay que estar parado en la carpeta que contiene `cli.py`; si no, Python tira `No module named engine`.

### Build

```bash
pip install pyinstaller customtkinter
pyinstaller ChordWeaver.spec       # -> dist/ChordWeaver/
```

Es build **de carpeta, no `--onefile`**, deliberadamente: el programa guarda `history.json`, `settings`
y `output/` *al lado del ejecutable*, y con onefile todo viviría en un temporal y se perdería.

### Compilar el motor (opcional)

```bash
pip install cython setuptools      # además de las Build Tools de Visual Studio
python build_engine.py             # -> engine/{fitness,style,theory}.*.pyd
python build_engine.py --clean     # los borra y el motor vuelve a Python puro
```

- **Los `.py` no se tocan, y eso es toda la idea.** Cython los acepta tal como están; los tipos van
  en `engine/fitness.pxd` y `engine/style.pxd`, que **Python ignora por completo** --- no son
  módulos, son una hoja de tipos que sólo lee el compilador. Así `fitness.py` se sigue leyendo,
  editando y corriendo sin tener nada instalado, que es la promesa del motor.
- **El respaldo es el orden de importación de Python, no un `try/except`.** Un `.pyd` al lado de un
  `.py` gana, así que `from .fitness import evaluate` se lleva el compilado si está y el `.py` si
  no. Nadie pregunta y no hay una segunda ruta de código que mantener. Borrar los `.pyd` deja el
  programa andando, más lento. `pyinstaller ChordWeaver.spec` funciona con o sin ellos, y los
  levanta solos por los `hiddenimports` que ya estaban.
- **Una función con un generador adentro no se puede declarar en el `.pxd`.** Un `sum(1 for ...)`
  es un closure y Cython no los soporta dentro de una `cpdef`: la compilación se cae con *closures
  inside cpdef functions not yet supported*. Quedan afuera cuatro de las más calientes que hay
  ---`range_violations`, `has_melodic_tritone`, `_unison_pairs`, `_crossing_count`---, que igual se
  compilan, sólo que sin tipos. **Reescribirlas como bucles explícitos las haría declarables y no
  hay que hacerlo**: sería tocar el `.py` para complacer al compilador, que es exactamente lo que
  esta separación existe para no hacer.
- **`cdef` esconde la función de Python; `cpdef` no.** Los ocho ayudantes privados de `fitness.py`
  van `cdef` porque nadie los importa ---verificado con grep antes de declararlos así--- salvo
  `_context_at`, que `engine/flourish.py` usa. Todo `style.py` va `cpdef`: es la biblioteca de
  reglas y la importan `fitness.py`, `audit.py` y `tests.py` por nombre.
- **Los enteros van en `long` sólo donde el valor sale de una altura MIDI o de contar cosas.** Donde
  la cuenta mezcla un campo del perfil de género (`max_upper_spacing`, `edge_margin`,
  `final_ideal_span`) el acumulador va en `double`: hoy los tres son `int` en los cuatro perfiles y
  no los toca ni la interfaz ni el CLI, pero si alguno pasara a ser fraccionario un acumulador
  entero lo truncaría **en silencio**. Las tres se multiplican por un peso float en el evaluador,
  así que en `double` dan idéntico y no queda filo.
- **`annotation_typing` va apagado.** Las anotaciones de esos archivos están escritas contra
  `typing` y son documentación para quien lee ---`Sequence[int]`, `Optional[ChordContext]`---, no
  tipos de Cython. Dejar que las tome cambiaría la semántica de un archivo que nadie escribió
  pensando en eso.
- **`wraparound` NO se puede apagar**: `pitches[-1]` se usa en el evaluador.
- **Si falla con "Unable to find a compatible Visual Studio installation" teniendo MSVC instalado**,
  es que `vswhere.exe` no está en el PATH, y el mensaje no tiene nada que ver con la causa.
  setuptools arranca `vcvarsall.bat` con `cmd /u` ---salida en UTF-16--- y le lee el entorno de ahí;
  sin `vswhere`, el **shell** escribe su "no se reconoce como un comando" en ANSI antes de que
  empiece el UTF-16, y esos 102 bytes impares corren el flujo medio carácter: **todo** el volcado se
  decodifica como basura, no sobrevive ni una línea `CLAVE=valor` y setuptools concluye que no hay
  Visual Studio. `build_engine._make_vswhere_findable` lo arregla poniéndolo en el PATH. Un error de
  codificación disfrazado de instalación faltante.
- Medido sobre dieciséis acordes con la búsqueda de fábrica (200x300): **17,4 → 8,2 s** en un
  proceso y **8,3 → 5,7 s** con los ocho del pool. Sin los `.pxd`, o sea compilando y nada más, era
  1,3x; los tipos son la mitad de la ganancia. El resultado es **idéntico bit a bit**, verificado
  compilado contra Python puro sobre las mismas 14 corridas que se usaron para el resto.

## Arquitectura

```
app.py          interfaz completa (una sola clase)
staff.py        widget de pentagrama editable
cinematic.py    las escenas del modo historia (el tercer archivo con GUI)
cli.py          front-end de consola
tests.py        suite del motor
audit.py        herramienta de verificación musical, no producto
engine/         el motor: sin GUI, sin I/O más allá de archivos
MUSIC_LOGIC.md  mapa de la lógica musical y de contrapunto
```

Los tres archivos con interfaz están separados por la misma razón: `staff.py` y `cinematic.py` son
widgets enteros y autosuficientes que `app.py` abre y cierra sin saber cómo están hechos por dentro.
Ninguno de los dos importa nada de `app`.

El grafo de dependencias va en una sola dirección y no tiene ciclos:

```
app.py / cli.py  →  engine.session  →  ga → fitness → style → theory
app.py           →  staff.py            ↘  export, history, flourish,
app.py           →  cinematic.py           harmonize, harmony, passing
cinematic.py     →  engine.story, engine.ambience, engine.visitors
uitest.py        →  app.py
```

- **`engine/session.py` es la fachada.** La GUI y el CLI sólo hablan con este módulo:
  `generate()`, `generate_random()`, `harmonise_melody()`, `export_outcome()`, `apply_flourishes()`.
  Nada del motor lo importa a él. Al agregar una capacidad nueva, exponerla acá.
- **`engine/theory.py` está en la base** y no importa nada del proyecto. Pitches son enteros MIDI
  (C4 = 60); una "pitch class" es MIDI mod 12.
- **Ningún módulo de `engine/` importa un toolkit gráfico**, y así debe quedar: es lo que permite
  correr el motor desde tests, CLI o la app indistintamente.

### Dónde está cada cosa

| Área | Archivo |
|---|---|
| Búsqueda (AG: torneo, elitismo, paralelismo) | `engine/ga.py` |
| Evaluación de una solución | `engine/fitness.py` |
| Reglas idiomáticas por género | `engine/style.py` |
| Notas, voces, parser de cifrado americano | `engine/theory.py` |
| Duplicaciones y omisiones de grados | `engine/voicing.py` |
| Qué acordes hay en una tonalidad; calidad de una progresión | `engine/harmony.py` |
| Elegir acordes bajo una melodía dada | `engine/harmonize.py` |
| Notas de paso | `engine/passing.py` |
| Gestos de época (cadencias, sextas) | `engine/flourish.py` |
| MusicXML + MIDI | `engine/export.py` |
| Síntesis WAV para escuchar el resultado | `engine/audio.py` |
| Rutas portables, historial, preferencias | `engine/history.py` |
| Logros: catálogo, estrellas, detectores | `engine/achievements.py` |
| Texto del libro de teoría | `engine/book.py` |
| Modo historia: guion, senderos, piezas fijas, estado | `engine/story.py` |
| Huevos de pascua: condiciones, catálogo y contador | `engine/eggs.py` |
| Visitas: quién aparece, cuándo, qué dice y qué deja | `engine/visitors.py` |
| Ruidos del modo historia, sintetizados | `engine/ambience.py` |
| Cinemáticas: personajes, animación y diálogo | `cinematic.py` |
| La visión del cruce de caminos | `cinematic.py` (`Vision`) |
| Tutorial: pasos y velo con foco | `app.py` (`TUTORIAL_STEPS`, `Tutorial`) |

### Las reglas de contrapunto están partidas en dos, a propósito

- **`engine/fitness.py`** — el evaluador. Fitness es un **coste**: menor es mejor. Separa
  **restricciones duras** (rangos vocales, cobertura del acorde, cruce de voces, y las paralelas /
  tritono que el usuario haya prendido → `INFINITE_COST`, el cromosoma se anula y nunca aparece en el
  resultado) de **penalizaciones ponderadas** que el AG negocia (movimiento total con el peso más
  grande, saltos, espaciado, tesitura, quintas directas, movimiento contrario).
  Acá viven los cuatro perfiles: `CLASSICAL`, `CHORALE`, `GREGORIAN`, `JAZZ`.

- **`engine/style.py`** — las reglas propias de cada tradición, como funciones sueltas: no duplicar la
  sensible, séptimas que resuelven bajando, guide tones por grado conjunto, compensación de saltos,
  movimiento contrario al bajo, ambitus.

**Invariante del diseño: los perfiles de género sólo cambian pesos y valores por defecto, nunca la
mecánica.** Si una regla nueva necesita lógica distinta según el género, va como peso, no como rama.
Todos los switches se pueden prender y apagar por separado; el género sólo define el valor inicial.

Catálogo completo de reglas, orden de los chequeos duros y cómo se agrupan los pesos bajo
`motion_emphasis` / `style_emphasis`: [`MUSIC_LOGIC.md`](MUSIC_LOGIC.md), secciones 6 y 7.

## Particularidades que cuesta descubrir leyendo el código

- **Un cromosoma es siempre armónicamente correcto por construcción.** Cada gen sale de una tabla de
  candidatos precomputada, así que una solución puede ser *musicalmente* mala (saltos, paralelas) pero
  nunca equivocada sobre qué notas pertenecen al acorde.
- **Los flourishes corren después de la búsqueda**, sobre el ganador, no dentro del fitness. Enseñarle
  al fitness a quererlos significaba pelearse con él: el voicing llano siempre es más barato en
  movimiento, así que un flourish sólo podía ganar pagándose, y pagarlo distorsionaba todo lo demás.
- **`engine/harmonize.py` corre hacia atrás**, del último acorde al primero: saber que el próximo es un
  punto de reposo es lo que dice que el actual quiere ser dominante.
- **Paralelismo por procesos, no hilos** (`resolve_worker_count`): es CPU pura y el GIL haría que los
  hilos se turnen. Deja un núcleo libre, topea en 8, y se desactiva en trabajos chicos.
  `main()` en `app.py` llama `multiprocessing.freeze_support()` — es obligatorio bajo PyInstaller en
  Windows; sacarlo hace que el .exe se relance a sí mismo en bucle.
- **El sembrado mira el acorde anterior, y sin eso el Generador fallaba 2 de cada 10 veces a 32
  compases** (`_without_repeating`). La gramática cobra dos cifras romanas iguales seguidas con
  **costo infinito** (`harmony.progression_cost`, `weights.forbid_repeat`), y el sembrado elegía el
  acorde de cada lugar sin mirar el de al lado: con una docena de opciones, la chance de zafar en
  los 63 empalmes de una pieza de 32 compases es (11/12)^63 --- medio por ciento. Medido: **de 2235
  cromosomas sembrados sobrevivían 2**, y dos de cada diez corridas no sobrevivía ninguno. Ahí el
  programa contestaba «con las reglas prendidas no hay ninguna forma de escribir esta progresión»,
  que es **falso**. Y cuando sí había solución era casi igual de malo en silencio: una población de
  doscientos hecha de dos individuos distintos y ciento noventa y ocho copias no tiene con qué
  cruzar. No se aflojó ninguna regla ---se le enseñó al sembrado una que ya existía, como ya sabía
  de rangos, cruces y paralelas---: ahora siembra 200 de 200 en todas las semillas.
- **Y por eso el corte por estancamiento subió de 60 a 100** (`GAConfig.stagnation_limit`). El 60
  estaba calibrado contra la población degenerada de arriba, que mejoraba despacito y sin mesetas.
  Con doscientos individuos distintos la búsqueda converge rápido, se planta un rato largo y
  **después vuelve a mejorar**: cortaba en la generación 187 con costo 16162 contra 13154 llegando a
  las 300. En piezas cortas no cambia nada, porque ahí nunca llegaba a dispararse.
- **El relleno de la población NO vuelve a puntuar, y ahí estaba escondido el 40% de la búsqueda.**
  Cuando las reglas duras anulan a la mayoría de los hijos, el bucle de relleno clona a los elites
  para completar las doscientas plazas. Un clon sin mutar tiene el costo del original —`copy()` ya lo
  trae— pero se lo volvía a calcular: medido sobre dieciséis acordes con la búsqueda de fábrica,
  **40.000 de las 100.720 evaluaciones de una corrida**, un solo cromosoma puntuado 7.654 veces, y
  todas seriales en el proceso padre mientras los ocho del pool esperaban. Por eso el paralelismo
  rendía un 7% (39,6 s en un proceso contra 37,0 s con ocho) y no porque el pool estuviera mal
  dimensionado. Sacando esas evaluaciones: **37,0 → 8,3 s**, con el resultado idéntico bit a bit.
  Cualquier cosa que agregue cromosomas a la población tiene que preguntarse si su costo ya se conoce.
- **Y los hijos se despachan al pool a medida que nacen, no cuando están los doscientos.** Criar
  cuesta más que puntuar —4,8 s de cruce y mutación contra 2,8 s de evaluación con ocho procesos—
  así que juntarlos a todos antes de mandar el primero dejaba a los workers de brazos cruzados media
  generación. `apply_async` por tanda de veinticinco, recogiendo en orden. **El orden de cría no se
  toca**: los mismos torneos y las mismas mutaciones en la misma secuencia, así que el generador de
  azar entrega lo mismo y una semilla sigue dando la misma partitura. Verificado contra la versión
  anterior en 14 corridas —cuatro géneros por tres semillas, más los dos modos generativos— idénticas
  bit a bit. Lo que queda como techo es la cría, que es serial por definición: es el próximo cuello.
- **Un memo de evaluaciones no sirve, y se probó.** Parece la optimización obvia una vez que se ve el
  38% de cromosomas repetidos, pero ese 38% *era* el bucle de relleno: arreglado en su origen, el
  índice de aciertos cae al 0% —86 de 60.000 en el Organizador, 74 de 28.613 en el Generador— y lo
  único que queda es el costo de armar la clave en cada evaluación. Medido, **pérdida neta**.
- **`app.py` anula los `__del__` de `tkinter.font.Font`, `Variable` e `Image`** al importarse
  (`_keep_tk_off_the_worker_thread`). Varios finalizadores de Tk vuelven a llamar a Tk, y Python los
  corre en el hilo que dispare el GC — caían dentro de la búsqueda y la bloqueaban. Medido: la misma
  búsqueda tardaba 0,5 s u 84 s según dónde saltara el colector. **No revertir.**
- **La búsqueda corre con el intervalo de cambio de hilo fino** (`ambience.fine_switching`, que
  `_start_worker` envuelve). Cruzar y mutar son bucles cerrados de Python en el hilo de búsqueda, y
  con el intervalo de fábrica ---5 ms--- se quedan con el GIL en tandas largas: medido sobre una
  generación de 32 compases, la mediana de la pausa del bucle de Tk baja de 47 a 32 ms y el
  percentil 99 de 112 a 47 ms. Es **el mismo mecanismo que la síntesis de sonido y comparte su
  contador**, justamente para que los dos no se pisen al devolver el valor original ---
  `setswitchinterval` es un ajuste del intérprete entero.
- **Lo que eso NO arregla es el arranque del pool**, que en Windows es lanzar ocho intérpretes:
  ~1,9 s en los que la ventana no atiende un solo repintado, con el intervalo fino o sin él. Por eso
  `_start_worker` hace `update_idletasks()` **antes** de arrancar el hilo: no acelera nada, pero se
  asegura de que lo que quede congelado esos dos segundos esté dibujado entero. Sin eso la pantalla
  de progreso se congelaba a medio pintar ---mitad cartel viejo, mitad nuevo---, que es lo que se ve
  como «la pantalla explotada en pedazos». El `update_idletasks` de `_render` no alcanza: entre
  aquello y esto se arma el pedido, que crea widgets y vuelve a ensuciar la cola de dibujo.
- **Tk no es thread-safe**: el AG corre en un hilo de fondo y reporta por una cola que el main loop de
  Tk drena por timer. El worker nunca toca un widget.
- **Y un hilo de fondo tampoco puede agendar nada en Tk.** `after` desde otro hilo no es riesgoso: es
  imposible --- tkinter lo rechaza con `RuntimeError: main thread is not in main loop`. Como la
  llamada estaba envuelta, lo que pasaba era **nada**: el botón de «Escuchar» se quedaba en
  «Sonando…» para siempre y el ruido de un huevo recién sintetizado no llegaba a sonar nunca. Quien
  pregunta es Tk: `ChordWeaverApp._when_done(hilo, acción)` mira si el hilo sigue vivo desde un timer
  del bucle principal, y el ruido de un huevo se espera con `ambience.made(nombre)`. **Un
  `on_finished` que toque un widget, o que toque cualquier cosa de Tk, no sirve.**
- **Los tres modos se llaman Organizador (`manual`), Armonizador (`harmonise`) y Generador
  (`random`).** El nombre visible vive en `MODE_CARDS` (`app.py`); la clave interna es la de siempre y
  no cambia. Cada modo tiene un color propio que tiñe el riel de progreso y el logotipo — sale de
  `_mode_accent()`. **En pantalla van Organizador, Generador y Armonizador**, y el orden de
  `TUTORIAL_STEPS` sigue al de las tarjetas: el velo del tutorial las recorre de izquierda a derecha,
  así que si una se mueve hay que mover también su paso.
- **El dial de intercambios modales llega a 100, y no a 40.** A 40 el premio por prestar un acorde no
  alcanzaba para ganarle a la gramática: medido sobre diez progresiones de ocho acordes en jazz, el
  tope viejo daba 14% de préstamos —o sea que «muy seguido» y «casi nunca» eran casi lo mismo— y el
  nuevo da 60%. El punto de partida (`BORROWED_DEFAULT`, 15) es el mismo sexto de camino que tenía la
  escala vieja, así que quien no toca nada oye lo de siempre.
- **Los acordes prestados llevan la séptima que les toca en el modo paralelo** cuando el usuario
  prendió las séptimas (`_BORROWED_SEVENTH` en `engine/harmony.py`). Salían como tríadas peladas en
  medio de una pieza donde todo lo demás era de séptima, y eso se oye como un acorde que no
  pertenece: no por prestado, sino por delgado. La sexta napolitana es la excepción —se llama así por
  su cifrado de sexta y una séptima encima la convierte en otra cosa.
- **Y por eso el `bVII` prestado es literalmente un acorde de dominante**, así que la regla de «una
  dominante tiene que caer de quinta» se pregunta por la **función** y no por la forma
  (`_borrowed_subdominant`). Sin eso, el préstamo más idiomático del catálogo quedaba prohibido justo
  al darle su séptima: su giro propio, bVII-I, sube un tono. Las dominantes aplicadas no entran en la
  excepción —viajan en el mismo campo `is_borrowed` pero tienen que seguir obligadas a resolver.
- **A cuatro voces y con séptimas, el dial de color sólo puede entrar cambiando la séptima.** Cada
  acorde trae exactamente cuatro notas, no sobra ninguna voz, y el color entra por las voces que
  sobran: todo sonaba a séptima de punta a punta. `voicing.SEVENTH_SWAP_SHARE` (0,30 del dial) cambia
  la séptima por una sexta o una novena —sólo esas dos— y nunca donde la séptima es función y no
  color: `harmony.seventh_is_structural` protege las dominantes, los semidisminuidos, el V y los V/x.
  El nombre del acorde se rehace (`Dm7` con la séptima cambiada es `Dm6`, no `Dm76`).
- **Un solo sorteador para todo el pool de acordes** (`colour_picker`, en `generate_random`). Estaba
  sembrado de nuevo dentro de la comprensión, así que los treinta acordes sacaban el mismo número: o
  todos tomaban color o ninguno.
- **Los intercambios modales salen en naranja en la pantalla de resultados** (`BORROWED_TINT`).
  Naranja y no violeta: el violeta ya dice «esto está en otra tonalidad», y un préstamo no es una
  modulación. Las dominantes aplicadas no se tiñen, por lo mismo que no cobran el dial.
- **El armonizador reporta el progreso de sus tres búsquedas, no de la primera.** Hace una corrida
  principal y una por cada alternativa; sólo la primera reportaba, así que la barra se plantaba donde
  la primera terminara —con el corte por estancamiento, alrededor de un quinto del camino— y ahí se
  quedaba cuatro o cinco segundos en silencio. Medido con 32 notas: el peor silencio pasó de ~5 s a
  1,4 s, y lo que queda es el arranque del pool de procesos. `MAIN_SHARE` reparte la barra.
- **El 6/4 es una disposición, no un conjunto de intervalos** (`style.cadential_six_four`).
  Un 6/4 es **5-1-3** desde el bajo: la quinta abajo, la fundamental encima y la tercera
  arriba. Con la tercera en el medio ---5-3-1--- los intervalos sobre el bajo son los mismos
  ---una cuarta y una sexta--- así que el chequeo viejo, que comparaba el conjunto de
  intervalos, daba las dos por buenas: la mitad de lo que salía marcado como «Cadencial 6/4»
  era la otra disposición. Y aparecía poquísimo por dos motivos más: se reconocía **sólo a
  tres voces** ---el barroco se canta a cuatro--- y el evaluador **cobraba** la quinta en el
  bajo de una tríada simple, que es exactamente la fórmula. Ahora está exento y además
  premiado (`weight_cadential_six_four`): sin premio no alcanza, porque el bajo en la
  fundamental está más cerca del acorde de al lado y en movimiento puro gana siempre.
- **Y el 6/4 se reconoce en los tres modos, pero no por el mismo camino.** El Generador y el
  Armonizador eligen los acordes, así que la cifra romana viaja en el `ChordContext` y la
  regla pregunta por ella; el Organizador no declara ninguna tonalidad ---el usuario escribe
  cifrados sueltos--- y ahí lo único afirmable es que un acorde mayor cae de quinta sobre el
  siguiente. Sin ese segundo camino el gesto no existía justo en el modo de escribir acordes,
  y el logro que pide «escribí tu primer dominante 6/4» era inalcanzable escribiendo.
- **El armonizador dice de antemano qué notas va a sostener, y se le pueden agregar.** Las
  notas que van a recibir acorde salen **doradas** en el pentagrama y se recalculan en cada
  tecla (`harmonize.planned_notes`, `app._refresh_harmony_preview`): es la misma cuenta que
  hace la búsqueda ---los mismos lugares, la misma nota por lugar--- sin elegir acordes, así
  que es determinista y cuesta 5 ms con 128 notas. El usuario puede marcar cualquier otra
  ---botón «Marcar notas» o click derecho--- y ésa recibe el suyo: viaja como
  `MelodyNote.must_harmonise` y le abre un lugar propio. **Marcar es un modo y no un click
  distinto** porque el click de escribir ya hace dos cosas, poner una nota y corregir la que
  hubiera, y una tercera lo volvía impredecible. La marcada lleva además un anillo dorado:
  sin él, marcar una nota que el programa ya iba a armonizar no se veía.
- **Abrir un lugar de acorde donde el compás no lo puso tiene que dejar el compás sumando**
  (`harmonize.spot_for_note`, que ahora usan la sensible y las notas marcadas). El lugar que
  se parte se queda con lo que hay hasta la nota y el nuevo con **todo el resto**, no con la
  duración de la nota; y cuando lo de adelante es más corto que `MIN_DURATION` el lugar se
  corre entero y ese pedazo se lo lleva **el anterior**. Corriéndolo sin dárselo a nadie, en
  6/8 con una nota marcada en 1,75 el compás sumaba dos tiempos y tres cuartos, y un compás
  que no suma lo rechaza cualquier editor de partituras.
- **Ctrl+Z aprieta el botón de deshacer, no llama a `staff.undo`** (`app._undo_shortcut`, con
  `invoke`). Así el atajo y el botón no pueden separarse nunca. Va atado a la ventana y no al
  pentagrama, porque la tecla llega a donde esté el foco ---después de tocar el piano o un
  radio de figura, no es el lienzo--- y lo que decide si hace algo es que el botón todavía
  exista.
- **El armonizador le pone la dominante a la sensible** (`harmonize.pin_leading_tone`). Si la
  anteúltima nota es la sensible de la tónica, ese lugar queda limitado al quinto grado —y al séptimo
  también, en jazz—; y si ahí no caía ningún acorde, se le abre uno con la duración de la nota
  partiendo el que la cubría. Se elige por **grado** y no por cifra romana, porque la cifra cambia con
  el modo. No hace nada cuando el acorde que se forzaría no contiene la nota, que es lo que pasa en el
  menor natural: ahí no hay sensible.
- **Y no escribe acordes después de que la melodía terminó.** Una línea que no llena su último compás
  —nueve negras en 4/4— dejaba tres tiempos vacíos que igual recibían acorde, así que la cadencia caía
  sobre el silencio y la última nota se armonizaba con el anteúltimo acorde. Lo que ocupaban los que
  se van se lo queda el último, así que los compases siguen sumando.
- **El pentagrama se desplaza de costado** (`staff.MIN_SPACING`). Apretar las notas para que entren
  tiene un límite: por debajo de 38 px una cabeza de nota se toca con la vecina y un sol escrito se lee
  como un la. Pasado ese punto la separación se planta y aparece una barra horizontal, que se muestra
  y se esconde sola. Los clics van en coordenadas del lienzo (`canvasx`), no de la ventana.
- **Las estrellas y los huevos suenan** (`ambience._fanfare`, `_egg_found`, `_egg_prize`;
  `STAR_SOUNDS` y `EGGS_WITH_OWN_SOUND` en `app.py`). Las tres fanfarrias son el mismo acorde con más
  notas y más sala: lo que sube no es el premio sino cuánto ocupa. El rugido, el zorro y el estampido
  **no** llevan el ruido de hallazgo: ellos *son* el huevo, y una campanita encima les contestaría el
  chiste. **Y el huevo dorado de la pantalla de logros lleva el suyo** (`egg_prize`, en
  `_celebrate_secret`): es el único premio del programa que hay que ir a tocar y era el único que
  ocurría en silencio — los ruidos se cablearon al *encontrar* un huevo y al ganar una estrella, y ese
  gesto quedó afuera. Suena a lo mismo que el hallazgo y más: la misma caja de música,
  subiendo dos octavas en vez de una, y **todo del mismo acorde de do mayor**. El hallazgo suelto
  cierra con una nota de afuera que no resuelve —la guiñada— y el premio no: aquello es un chiste de un
  segundo y esto es lo último que el programa tiene para dar. Una disonancia colgada al final de un
  premio no se lee como una guiñada sino como algo que quedó sin terminar. Una fanfarria de metal habría sonado a
  estrella, y una estrella se gana estudiando; esto se gana buscando. **Los ruidos van en la
  celebración y no en el gesto que la dispara**, para que suenen cada vez que la escena se juega.
- **El unísono pesa 1000, y no 250** (`weight_unison`). A cuatro voces no se notaba porque a cuatro
  voces no pasaba: los registros apenas se tocan. A seis, las voces del medio comparten media octava y
  el unísono aparecía en uno de cada catorce acordes — seis voces que producen cinco cabezas. Medido
  sobre 160 acordes de barroco y coral a seis voces con la búsqueda de fábrica (200×300): **3,8% / 0,6%
  con el peso viejo, 0,6% / 0,0% con el nuevo**, y el movimiento medio por voz sube de 2,21 a 2,30
  semitonos, o sea nada. Más arriba no mejora — se probó 1500 — y lo único que se consigue es que esta
  regla le gane a las demás por goleada. Es además **peso y no regla dura** a propósito: con seis voces
  y registros angostos puede no haber ninguna solución sin unísono, y una regla dura ahí devuelve
  "no hay solución" en vez de la mejor que había.
- **Un acorde de séptima con una sexta agregada se escribe `Cmaj7(6)`, no `Cmaj76`.** Dos cifras
  pegadas se leen como una sola. `symbol_with_added` pega la sexta al nombre —«C6»— sólo cuando no
  quedó una séptima adelante. Salía a seis voces, que es donde sobran voces para colorear un acorde
  que ya está completo.
- **La búsqueda saltea los silencios, así que `solution.slots` NO está alineado con `spec.slots`.**
  No hay nada que repartir en un silencio y la conducción de voces se mide de un acorde al siguiente
  como si no existiera, que es lo que se oye. La consecuencia es que cualquier cosa que zipee las dos
  listas queda corrida un lugar desde el primer silencio: la pantalla mostraba las notas de un acorde
  debajo del nombre del anterior, y al escuchar, la duración del silencio se la llevaba el acorde
  siguiente — la pieza duraba un compás menos y no tenía ningún silencio adentro. **Siempre
  `session.voiced_slots(spec, solution)`**, que devuelve tantas listas como slots tenga la partitura y
  pone una lista vacía donde hay silencio; el sintetizador entiende un acorde sin notas como tiempo que
  pasa sin sonar. El exportador no lo necesita: lleva su propio cursor.
- **Las notas de adorno suenan, y para eso el acorde adornado sale como voces sueltas**
  (`session.ornaments_of`, `session.playback_events`, y el parámetro `voices` de
  `audio.render_chords`). Un adorno es media voz moviéndose sobre el final del acorde mientras las
  otras sostienen, y eso no se puede decir con una lista de acordes: todas las voces de un acorde
  empiezan y terminan juntas. Así que el slot adornado se vacía ---ocupa su tiempo y no suena por su
  cuenta--- y sus voces salen con comienzo y duración propios. **Las duraciones no cambian nunca**:
  el adorno se lleva la cola del acorde que deja, así que un compás que sumaba cuatro sigue sumando
  cuatro y nada de lo que viene después se corre. Los adornos vienen indexados por slot de la
  búsqueda ---que saltea los silencios---, así que `ornaments_of` los reubica sobre `spec.slots` por
  el mismo motivo que existe `voiced_slots`.
- **Y el historial los guarda aparte** (`ProductionRecord.ornaments`, una lista de
  `[slot, voz, altura, porción]` por solución). Metidos adentro de `solutions` habrían inventado una
  columna de acorde en la pantalla de detalle, que muestra una por acorde escrito; sin guardarlos, la
  misma corrida se volvía a escuchar desde el historial sin ningún adorno. Las entradas viejas no
  traen el campo y suenan como siempre.
- **Y a un silencio el motor le pone un do de relleno** (`build_settings`), para que la lista de slots
  siga alineada con los compases. Ese do se estaba dibujando como si el usuario lo hubiera escrito, así
  que lo que se muestra se decide por `is_rest` y nunca por el símbolo: en pantalla va `𝄽` con la
  fuente de símbolos —la misma con la que el pentagrama dibuja sus claves— y en el historial va
  `history.REST_LABEL`, que es texto para que el archivo se pueda leer en cualquier consola.
- **Una cita no sella sus elecciones sobre los slots del generador.** La cita se voicea aparte, con un
  slot por acorde y **una sola opción en cada uno**, así que sus `choices` son todos cero; aplicados
  sobre los slots del generador —que tienen decenas de opciones— sellaban el acorde número cero de
  punta a punta. Salía una progresión de ocho tónicas seguidas con la repetición prohibida. En pantalla
  no se veía, porque ahí manda `set_piece.symbols`, y en la partitura exportada tampoco, porque
  `export_outcome` cambia los slots por `set_piece.slots`: se veía **en el historial**, que lee los
  slots. Ahora `generate_random` sella con la mejor solución **generada** —la que había antes de meter
  la cita adelante— y `_remember_run` anota los símbolos de la cita cuando hay una. Hay un test que lo
  vigila, y falla contra el código viejo.
- **El historial se pinta con el color del modo** (`_record_accent`, `_record_icon`). El recuadro, el
  signo y el nombre del modo llevan el mismo color que tenía el riel de progreso mientras se hacía esa
  corrida, así que se distinguen sin leer una línea. Las entradas escritas antes de que existiera el
  campo `mode` quedan con el borde neutro: inventarles un color sería peor que no darles ninguno.
  También se puede **volver a escuchar** una corrida guardada (`_play_record`): el archivo ya guarda
  las alturas y las duraciones, que es todo lo que hace falta, y una lista de cosas que uno hizo y no
  puede escuchar es un inventario, no un historial.
- **Y la fecha se escribe como la diría alguien** (`ProductionRecord.when`): «hoy 16:12», «ayer 09:03»,
  «5 mar 14:30». En una lista de diez corridas hechas casi todas el mismo día, un sello ISO no dice
  nada; lo único que se busca ahí es cuál es la de recién. Los costos se sacaron, por lo mismo que se
  sacaron de la pantalla de resultados.
- **«Rebelde sin causa» mira la pantalla de reglas entera**, no sólo los interruptores
  (`achievements.rules_customised`). El balance, la cadencia, el dial de color y los registros también
  son reglas. Dos trampas: el color se compara contra el valor con el que **el estilo** lo deja —el
  jazz arranca con color, y contra cero cualquier corrida de jazz habría contado— y los registros
  contra el catálogo, porque `range_overrides` lleva siempre las cuatro voces, estén tocadas o no.
- **El cartel de donaciones es un panel sobre la ventana, no una `Toplevel`** (`_open_donate`), por
  lo mismo que la configuración: una ventana aparte la ubica el sistema y en dos monitores puede caer
  en el que nadie está mirando. Va en su propio atributo (`donate_panel`) y no reusando
  `config_panel`, porque los dos se abren desde el pie y hay que poder cerrar uno para abrir el otro
  sin que el engranaje termine cerrando un cartel que no es el suyo; cada uno cierra al otro al
  abrirse, y `_story_quiet` los cuenta a los dos. El alias vive en `ChordWeaverApp.DONATION_ALIAS` y
  en ningún otro lado. El botón del pie es dorado de borde y no de relleno: tiene que verse ---si no,
  no está--- pero no puede competir con «Siguiente», que es lo que el usuario vino a apretar.
- **`_render()` desmapea `self.body` mientras arma la pantalla y la vuelve a mapear al final.** Tk
  dibuja cada widget en cuanto se crea; con el contenedor fuera de pantalla no dibuja nada hasta el
  final. Medido, la pantalla de acordes con 8 compases pasa de ~1750 ms a ~960 ms. La lógica de la
  pantalla vive en `_render_screen()`.
- **Lo único que se anima es el color y la `x` de widgets `place`-ados** (`mix()` y `animate()` en
  `app.py`). Animar geometría de widgets empaquetados obliga a Tk a recalcular el layout en cada
  cuadro y se ve peor que no animar. `animate` cancela la animación anterior sobre el mismo widget y
  se apaga sola si el widget deja de existir.
- **`bind_deeply()` ata eventos a un panel entero, y salta los widgets de customtkinter.** Un
  `CTkLabel` no es una ventana: es un marco con un canvas y una etiqueta adentro, y su `bind`
  redirige a esos dos, que el recorrido ya visita por su cuenta. Atar en los dos lados hacía que un
  clic disparara dos veces.
- **`CTkFrame.winfo_children()` esconde su propio canvas de fondo**, que es toda la superficie
  visible del marco. Por eso `descendants()` pide los hijos con `tk.Misc.winfo_children`: con la
  versión filtrada quedaban atados los textos de una tarjeta pero no su fondo, y los clics en el
  aire se perdían.
- **Las filas del listado de logros son `tk.Frame`/`tk.Label` pelados, no `CTk`.** Son más de
  cuarenta y cada widget de customtkinter dibuja su propio rectángulo redondeado en un canvas
  propio: medidas, las mismas cuarenta filas tardan 271 ms con `CTk` y 48 ms con tkinter. Las
  esquinas redondeadas las pone el panel que agrupa cada estrella. `start_shimmer` acepta
  `option="fg"` justamente para poder animar esas etiquetas.
- **La regla vale para todo lo que el usuario multiplica, y `fg_color="transparent"` es el peor
  caso.** Un `CTkFrame` transparente igual dibuja su rectángulo redondeado: del color del padre, o
  sea invisible, y pago. En la pantalla de acordes **128 de los 160 marcos eran transparentes**, y
  dibujar los 708 rectángulos de esa pantalla costaba 497 ms de los 896 que tardaba en armarse. Con
  esos marcos y sus etiquetas en tkinter pelado (`FlatLabel`, hermana de `FlatButton` —habla
  `configure(text_color=)` para que los once lugares que pintan el estado de una casilla no se
  enteren) la pantalla a 32 compases pasa de **1481 a 856 ms**. Lo que se queda en `CTk` es lo que se
  ve: el marco del compás, por su esquina redondeada, y el `CTkEntry` del cifrado, por su borde.
- **«Equipo modesto» recorta las generaciones y NO la población** (`LOW_RESOURCE_PRESET`, en
  `app.py`). La población parece el primer número a bajar ---multiplica todo el trabajo--- y es el
  único que no se puede: el sembrado arranca con `población x 12` intentos, y armar un cromosoma
  válido exige que **todos** los pares consecutivos lo sean, cosa que decae geométricamente con el
  largo. Medido en el Generador a 32 compases, con la población en 140 el programa deja de encontrar
  cualquier solución y contesta "no hay ninguna forma de escribir esta progresión" ---que además es
  mentira---. Con las generaciones a la mitad: **124 s → 69 s** sobre cuatro tareas, con el costo
  entre 15% y 31% peor. El botón **escribe en las casillas** en vez de guardar un modo aparte, así
  que lo que hizo queda a la vista y "Restaurar valores por defecto" lo deshace.
- **El tope de compases de la interfaz es 32** (`MAX_BARS`, en `app.py`), y era 64. Es un límite
  **de la interfaz**: `cli.py` sigue aceptando lo que se le pida y `engine/` no sabe que existe. Lo
  miran el Organizador y el Generador, que son los dos modos que pasan por la pantalla de compases
  ---el Armonizador saca la métrica de la melodía dibujada---. El número tecleado se **corrige** en
  la casilla al recortarse: dejándolo en 50, el próximo "Aplicar" volvería a recortar y parecería
  que el botón no hace nada. El tope va escrito al lado de la casilla porque el aviso de
  `metre_hint` llega cuando el número ya se recortó, que es tarde.
- **La pantalla de compases reusa sus filas, y la caché va atada al marco que las contiene.**
  `_rebuild_bar_rows` corre con cada "Aplicar" y con cada cambio de métrica base, y destruía las
  sesenta y cuatro filas para volver a crearlas idénticas. Reusándolas —y con `DurationPicker` en
  lugar del `CTkOptionMenu`, que construye su propio desplegable por fila— **993 → 155 ms** a 64
  compases la primera vez y **969 → 65 ms** las siguientes. La caché se tira cuando `bars_frame`
  cambia de identidad: `_screen_metre` arma un marco nuevo en cada render y unas filas colgadas del
  anterior serían widgets muertos.
- **El libro se llena solo, y su llave es un logro.** Una entrada de `engine/book.py` con
  `locked_by` no aparece hasta que el usuario consiguió ese logro. Es a propósito que no haya un
  registro propio: el programa ya detecta esos hechos y ya los guarda en `achievements.json`, así
  que agregar contenido nuevo es agregar una `Entry` con la clave del logro que la abre. Lo único
  que se guarda aparte es `settings["book_seen"]`, para poder marcar lo recién escrito con la
  anotación a mano.
- **`DEFAULT_SETTINGS` (`engine/history.py`) es una lista blanca.** `load_settings` descarta
  cualquier clave que no esté ahí, así que una preferencia nueva que no se agregue a ese diccionario
  se guarda bien y se pierde al reabrir. Es lo que hacía que el tutorial arrancara siempre.
- **El tutorial arranca solo la primera vez y `uitest` lo apaga.** El velo taparía todo lo que el
  arnés maneja, así que `uitest.Session` pone `tutorial_seen` en memoria sin tocar el archivo. El
  arranque automático se decide en `_maybe_start_tutorial`, no al programar el `after`, justamente
  para que se pueda desactivar entre medio.
- **`ACCENT` y `ACCENT_HOVER` son variables, no constantes.** `_apply_accent()` las reescribe con el
  color del modo antes de armar cada pantalla, y como todo widget las lee al construirse, switches,
  sliders, menús, casillas y botones toman el color solos. Lo que se crea una sola vez —el pie, el
  encabezado— hay que retocarlo a mano en `_update_rail`.
- **Los logros se detectan una sola vez por corrida y nunca dentro del AG.** `_check_run_achievements`
  corre en el hilo de Tk sobre el resultado ya en memoria, y todo detector recibe primero el conjunto
  de logros que todavía faltan (`Tracker.pending()`): lo conseguido ni se busca, así que el costo
  tiende a cero. El único barrido cuadrático —pares de voces por par de acordes, para las quintas
  paralelas— está detrás de esa comprobación. Los detectores que dependen de un acorde escrito o de
  una melodía dibujada corren en el `_commit_*` de esa pantalla, no por cada tecla.
- **Mientras se sintetiza un ruido, el intérprete cambia de hilo mucho más seguido**
  (`ambience._FINE_SWITCH`). Sintetizar es un bucle de muestras en Python puro y con el intervalo de
  fábrica --- 5 ms --- ese hilo se queda con el GIL en tandas largas: la ventana se clavaba hasta tres
  segundos enteros a los pocos segundos de abrir el programa, que es cuando arranca `prepare`.
  Medido sobre la ventana real: 2909 ms de peor pausa contra 24 ms. Se pone al empezar y se devuelve
  como estaba al terminar el último hilo de síntesis.
- **El diagnóstico de «no hay solución» mira todas las opciones de cada acorde, no la primera**
  (`ga.diagnose_impossible_slots`). En el Organizador el acorde está escrito y hay una sola; en el
  Generador el mismo lugar ofrece decenas y basta con que **una** se pueda escribir para que no haya
  nada que denunciar. Además agrupa: el mismo callejón sin salida suele estar en varios acordes a la
  vez y repetir la frase una vez por acorde llenaba la pantalla con un solo dato.
- **El arte del programa NO cuelga de `base_directory()`, y por eso existe `program_directory()`.**
  `CHORDWEAVER_DATA_DIR` está para mandar los **datos del usuario** a otro lado; los PNG de
  `assets/` vienen con el programa. Buscándolos por `base_directory()`, cualquiera que usara esa
  variable ---`uitest.Session` la usa siempre--- se quedaba **sin un solo personaje**, y sin ningún
  error: `load_pose` devuelve `None` cuando el archivo no está, que es lo correcto para una pose que
  falta y lo peor posible para todas. Las escenas se jugaban enteras, con sus diálogos y su valle
  dibujado, y vacías.
- **Y empaquetado, el arte está en `_internal/` y no al lado del `.exe`.** PyInstaller 6 dejó de
  poner los `datas` junto al ejecutable: van a `_internal/`, que es lo que apunta `sys._MEIPASS`.
  `program_directory()` lo devuelve cuando está congelado y la raíz del repositorio cuando corre
  desde fuente. **Es un bug que no se ve corriendo desde el código**: ahí no hay `_MEIPASS` y las
  dos rutas son la misma, así que sólo aparecía en el entregable. Los datos del usuario siguen
  yendo al lado del `.exe`, que es lo que `base_directory()` hace y hay que dejar como está. Hay un
  test por cada una de las dos cosas.
- Las rutas son **portables**: `history.base_directory()` devuelve la carpeta del .exe cuando está
  congelado y la raíz del proyecto cuando corre desde fuente. Nunca escribir en el home del usuario ni
  en una ubicación de sistema salvo que el usuario la elija en un diálogo.

## El sonido

Todo está sintetizado a mano en `engine/ambience.py` --- sigue sin entrar ninguna librería de audio
y no se empaqueta ningún archivo --- pero el módulo tiene ahora un taller y no sólo osciladores.

- **44100 Hz, no 22050.** Estuvo a la mitad con el argumento de que acá no hay que juzgar una
  conducción de voces sino ambientar. Era falso donde más importa: a 22050 no existe nada por encima
  de los 11 kHz, y ahí es donde vive el brillo de un metal, el filo de un grito y el aire de una
  cuerda pulsada. Todo sonaba **tapado** y ninguna cantidad de volumen arregla eso. Duplicar las
  muestras duplica el tiempo de síntesis y no cambia nada más, porque todo el módulo está escrito en
  segundos y en hertz; las dos únicas cosas que estaban en muestras --- el corte de los filtros de un
  polo y los retardos de la reverberación --- se corrigen solas con `_RATE`.
- **`_loudness()` --- nivelar por volumen *percibido*, no por pico.** El pico no dice nada sobre
  cuánto se escucha algo: un golpe seco y una campana con el mismo pico suenan a volúmenes
  completamente distintos, porque el oído mide energía promedio. Nivelar por pico dejaba el programa
  entero sonando a la mitad, y era exactamente por qué el ruido de la aparición quedaba tapado por
  el viento teniendo los dos el número «correcto». Ahora se lleva la energía a `POWER_BED` /
  `POWER_HIT` / `POWER_JOKE` / `POWER_BLIP`, se sujetan los picos con una curva blanda y **el techo
  sólo baja**: subir lo que quedó por debajo deshace el trabajo --- un bordón tiene los picos apenas
  por encima de su promedio, así que estirarlo al techo lo devuelve al volumen de un golpe.
- **`_band()` --- ruido por un filtro resonante.** Es la diferencia entre un siseo y *algo*. El
  filtro de un polo de `_noise` sólo sabe apagar agudos, y con eso el viento suena a cinta de
  casete; una banda angosta que se pasea de frecuencia suena a aire colándose por un hueco. De acá
  salen el viento, los formantes del rugido, el bufido del tren y el aullido de la visión.
- **`_reverb()` --- cuatro peines y dos pasa-todo (Schroeder).** Es lo que faltaba para que los
  sonidos dejaran de pasar en el vacío: un golpe, un grito o una campana **existen en un lugar**, y
  lo que dice cuál es ese lugar no es el sonido sino lo que vuelve de las paredes. Los retardos son
  primos entre sí a propósito; con divisores comunes los ecos caen encima y se oye el período.
- **En un bucle, la reverberación va ANTES de `_seamless`.** La cola es justo lo que el cruce tiene
  que fundir contra la cabeza; aplicada después, el empalme vuelve a saltar.
- **`_saturate()` y `_ring()`.** Un seno puro no suena a rugido por más grave que sea: lo que el
  oído lee como fuerza son los armónicos de algo que se está rompiendo. El anillo parte cada
  componente en dos y ninguna de las dos guarda relación con lo que había --- es lo que vuelve
  insoportable al zorro.
- **Todos los sonidos salen nivelados** (`_normalise` y las tres constantes `LEVEL_BED`,
  `LEVEL_HIT`, `LEVEL_JOKE`, más `LEVEL_BLIP`). Antes cada uno salía con la ganancia que le hubiera
  quedado de sumar sus capas: el zorro reventaba y el bordón de la entidad no se oía, que eran el
  mismo error visto de los dos lados. Las camas van bajas porque suenan **debajo** de todo y durante
  minutos; los golpes van altos porque duran un segundo y tienen que interrumpir.
- **Una cola de reverberación tiene que entrar en el archivo.** El coro duraba 3,4 s y la cola
  seguía sonando fuerte cuando el archivo se terminaba: el corte se oía como un clic. Al agregar
  reverberación a algo, alargarle el buffer.
- **La cama de ambiente va bien abajo** (`POWER_BED`, un tercio de lo que suena una voz). Suena
  mientras alguien habla, y lo único que hace de voz en una cinemática son los blips, que duran
  cuarenta milésimas cada uno: un colchón de viento parejo los tapa sin esfuerzo. Con la cama al
  nivel que tenía, el señor del sombrero directamente no se escuchaba. La excepción es el viento de
  la visión (`POWER_SOLO`), que suena sin nadie hablando encima: ahí el viento **es** la escena.
- **Ningún sonido puede terminar mientras todavía suena.** Un archivo que se corta en seco se
  escucha como un chasquido, y la reverberación empeoró el problema porque le agrega segundos de
  cola a todo: el canto de Gregorio terminaba al 42% de su volumen máximo. Se arregla en los dos
  extremos --- buffers más largos, para que la cola entre entera, y una bajada suave en los últimos
  450 ms dentro de `_loudness` --- y **los bucles pasan con `tail=0`**, porque ahí el final y el
  principio son el mismo punto y apagarlo rompería el empalme.
- **Al cerrar una escena se calla el bucle, no todo** (`ambience.stop_beds`). Un sonido de una sola
  vez ya sabe cuándo termina, y cortarlo se oye: la figura de luz se va con un coro de cinco
  segundos y su animación de partida dura tres. `stop_all` sigue existiendo para el gesto de
  silencio, que es otra cosa.
- **El limitador aprieta desde 0,55 y con margen largo** (`_KNEE`, `_KNEE_SPAN`). Con el codo en 0,7
  y la curva corta, lo que entraba en ella se doblaba de golpe: el grito del zorro tenía el 8% de
  sus muestras adentro y se escuchaba roto. Un resonador ancho, además, deja pasar casi todo el
  ruido que le entra --- por eso el rugido sonaba detrás de una cascada, y por eso sus formantes
  ahora son angostos y el aire es la quinta parte.
- **MCI no sabe bajarle el volumen a algo que está sonando: toca o no toca.** Así que cuando algo
  tiene que oírse por encima de la cama de ambiente, lo que se hace es **sacar la cama**
  (`Vision._hush`). Suena mejor que bajarla, además: el aire que se corta de golpe es la manera más
  vieja que hay de anunciar que algo va a pasar. En la visión el viento se corta dos veces --- cuando
  aparece la figura y cuando desaparece --- y la segunda no vuelve: la guitarra del final suena sola.
- **Los archivos se guardan entre corridas** (`_cache_folder`, `_adopt_cache`). Son funciones puras
  con semillas fijas: el archivo de hoy es idéntico al de ayer byte por byte, así que sintetizarlos
  en cada arranque era pagar veinte segundos todos los días para obtener siempre lo mismo. Van al
  temporal del sistema ---son derivados, no datos del usuario--- en una carpeta cuyo nombre lleva el
  **resumen del fuente de `ambience.py`**: si se toca una receta, la carpeta es otra y se sintetiza
  de nuevo, así que no hay manera de terminar escuchando la versión vieja de algo. Se escribe con
  `.part` y se renombra al final: un archivo a medio escribir se adoptaría como bueno para siempre.
- **`prepare()` termina escribiendo TODO, también lo de «a pedido».** Antes se dejaban para cuando
  alguien diera con ellos, porque casi ninguna sesión los iba a escuchar. Con la caché el cálculo se
  dio vuelta: se pagan una vez en la vida del programa en vez de una por arranque, y a cambio
  cualquier escena se abre al instante. Va **después** de `_ready.set()`, así que nada de lo que sí
  hace falta espera por eso.
- **Entre tocar un botón y ver la escena hay medio segundo**, y ése es el fundido a negro. Llegó a
  haber ocho o diez: la espera por los sonidos estaba topeada en quince segundos y se sentía como
  que el programa se había colgado. Hoy el tope es de dos segundos y medio y casi nunca se usa.
- **Un sonido que se pide para *ahora* puede no existir todavía** (`cinematic.SoundCues`, que usan las dos clases de
  escena). Los de las apariciones se sintetizan a pedido y una escena puede abrirse antes;
  `ambience.play` de algo que no está no falla ni avisa, así que el momento pasaba en silencio. El
  pedido queda anotado y se reintenta en cada cuadro, con una fecha de vencimiento: llegar tarde es
  peor que no llegar.
- **Y la escena directamente no se abre hasta tener sus ruidos** (`_when_sounds`, `_open_visit`).
  Con un límite de quince segundos: una escena muda es mala, una escena que no ocurre es peor.
- **`ambience.summon_all()` sintetiza de a tandas y en UN hilo.** Sintetizar es CPU pura y en Python
  los hilos no la reparten: se turnan. Cinco hilos no terminan antes, terminan **más tarde**, y acá
  peor todavía porque el intervalo de cambio está bajísimo a propósito (`_FINE_SWITCH`). Medido:
  cinco hilos tardaban 12 s en hacer lo que uno solo hace en 9. El orden de la lista es el orden en
  que la escena los necesita.
- **Un sonido que no está en la lista que se sintetiza NO EXISTE**, por más que su receta esté
  escrita. La guitarra del final de la visión estuvo muda por eso: la receta estaba, el nombre no
  estaba en `VISION_SOUNDS`, y `play` de algo que no existe no hace nada y no se queja. Hay un test
  que lo vigila.
- **`TestSoundWorkshop` (en `tests.py`) no prueba que suene bien** --- eso no se puede probar sin
  orejas --- sino las tres cosas que lo arruinan en silencio: nivel disparejo, bucle que salta al
  repetirse, y receta que se rompe y deja la escena muda.

## Modo historia

Después de cinco minutos de uso --- y sólo con la pantalla inicial a la vista, el tutorial terminado y
ninguna búsqueda corriendo --- **se enciende un botón dorado en la pantalla inicial**
(`_story_knock`), y la figura aparece recién cuando el usuario lo toca. Aparecer de golpe encima de
lo que estuviera mirando era la única cosa del programa que le sacaba el control de las manos. El
botón no dice qué es --- decirlo gastaría la escena en un cartel --- brilla como un legendario
porque es de esa familia, y **se queda**: si no lo toca hoy sigue ahí mañana. Lo único que el relato
ya no hace es empezar solo. La respuesta al ofrecimiento elige el sendero:
**aceptar** abre el del blues, **ignorar** el del jazz y **rechazar** el del góspel. Cada sendero son
tres tramos y siempre en los mismos tres lugares: una progresión escrita a mano en el Organizador, un
botón dorado en el Generador y un gesto dorado en el Armonizador.

- **`engine/story.py` es el guion y el estado**, y no dibuja ni suena nada, igual que el resto de
  `engine/`. Ahí están los diálogos, las trabas, las piezas fijas y `StoryState`.
- **El estado va en `story.json`**, al lado de `history.json` y `achievements.json`. No entra en
  `settings.json` --- que es una lista blanca de preferencias --- ni en `achievements.json`, que es el
  registro de lo conseguido: un sendero a medio andar no es ninguna de las dos cosas.
- **Los dos botones dorados nacen bloqueados, y lo que piden es leer.** Cada cinemática deja una
  anotación nueva en el capítulo VII y el botón del tramo siguiente no se enciende hasta haberla
  leído --- salvo la última, que no pide nada. Hubo una versión que además pedía repetir la cadencia
  en tres tonalidades: se sacó porque era un peaje, no un descubrimiento. La detección sigue en
  `story.KEY_GATES` porque es la que enciende los acordes en dorado mientras se escriben.
- **`story.unlocked_notes` escribe una anotación por cinemática y ni una más** (`max(1, step)`).
  Escribirlas antes las volvía inútiles: se abría el libro una vez, se leían las dos de una y las dos
  trabas quedaban abiertas sin que el usuario volviera a pasar.
- **El botón dorado vive en la pantalla de estilo**, que es la primera de cualquier modo. Lo que
  promete es saltearse la configuración entera, así que hacerlo esperar cinco pantallas era pedir
  justo lo que el botón anula. Y **el botón mismo dice qué hay que hacer** para encenderlo.
- **El aviso de que una traba cedió no dice qué se destrabó**, sólo a qué modo ir: nombrarlo le
  contaría el tramo entero al usuario desde un cartelito.
- **Las piezas del relato traen su propio tempo** (`Piece.quarter_seconds`). El de la casa --- 0,625 s
  por negra --- existe para poder seguir cuatro voces con el oído; a esa velocidad *All of Me* dura un
  minuto y medio de acordes larguísimos. `audio.render_chords` acepta el tempo por parámetro.
- **La cama de ambiente se repone desde el hilo de la interfaz** (`ambience.pump`, que llama la
  cinemática en su bucle). MCI ignora `play alias repeat` para audio, y reponer el `play` desde un
  `threading.Timer` tampoco sirve: MCI le cuelga cada dispositivo al hilo que lo abrió y desde otro
  hilo el comando no falla, simplemente no hace nada.
- **Los tramos automáticos no pasan por el algoritmo genético.** La pieza está escrita en `story.py` y
  `story.voice_piece()` la reparte entre las voces; después va como una corrida normal con **todas las
  alturas fijadas con el candado**, así que el AG no tiene nada que elegir y el resultado es
  instantáneo y siempre el mismo. Se corre con `story.FIXED_PIECE_RULES`, que apaga las paralelas y el
  tritono: un blues de doce compases los tiene, y son la música, no un error.
- **Con melodía, la quinta del acorde se omite** (`story.chord_omissions`). La voz más aguda la ocupa
  la melodía, así que sobre un acorde de séptima las cuatro voces se acaban antes de que la séptima
  encuentre quién la cante, y el motor rechaza el acorde incompleto. La quinta es lo primero que sobra.
- **Los tramos automáticos no reparten logros.** La pieza la escribió el programa de un botón; dar por
  descubierta la séptima o el jazz por algo que el usuario no eligió le sacaría medio juego sin aviso.
  Sí quedan en el historial.
- **El legendario de cada sendero se entrega en el cierre.** Mientras el camino esté a mitad,
  `StoryState.withholds()` lo retiene y `_award` lo filtra: el sendero es justamente el relato de cómo
  se llega a ese logro. Fuera de la historia, nada cambia.
- **El capítulo VII del libro se abre con tramos, no con logros.** `book.py` no distingue: pregunta por
  una llave y `app._lore_unlocked` la contesta contra los logros o contra la historia, según el caso.
- **Las escenas se encolan.** El cierre de un tramo y la apertura del siguiente los dice el mismo
  personaje, así que van en una sola escena; encolar en vez de abrir de una es lo que evita que dos
  cinemáticas disparadas en el mismo instante se dibujen una encima de la otra.
- **Todo el sonido está sintetizado en `engine/ambience.py`**, con el mismo criterio que `audio.py`: no
  entra ninguna librería de audio y no se empaqueta ningún archivo. Se reproduce por **MCI** (la
  interfaz multimedia de Windows, vía `ctypes`) porque `winsound` toca un solo sonido por proceso y acá
  hacen falta dos a la vez --- la cama de ambiente y el blip de cada letra. Si MCI falla se cae a
  `winsound` y después a los reproductores de línea de comandos. **El sonido es decoración: cada
  llamada está envuelta y el peor caso posible es que la escena ocurra en silencio.**
- **El ruido de la llegada suena cuando el personaje llega, no cuando arranca la escena.**
  `Cutscene.start` sólo prende la cama de ambiente; el `enter_sound` lo dispara la entrada que
  corresponda --- el primer salto del que se acerca, el primer cuadro del que baja --- y `_show_box`
  lo cubre para el que ya está en escena. Antes sonaba con la pantalla todavía en negro y los ojos
  cerrados, o sea antes de que hubiera entrado nadie.
- **La figura de luz no tiene cama de ambiente**: lo suyo es el coro, que entra con él y vuelve a
  sonar cuando se va. Con un bordón repitiéndose debajo, el coro quedaba enterrado y la escena entera
  sonaba a una sola nota larga. El guitarrista sí la tiene --- la misma del valle ---, porque sin
  ella su escena quedaba en silencio absoluto entre línea y línea, que no se lee como intimidad sino
  como que se rompió el sonido.
- **El tren de la visión entra desde afuera, y lo justo.** Se dibuja en el origen ---o sea adentro
  de la pantalla--- y hay que correrlo hasta que la punta quede unos píxeles del lado de afuera. Ni
  uno más: en cinco segundos tiene que entrar entero y salir entero, y cada píxel que se lo aleje de
  más es un píxel que después le falta. Con un corrimiento del largo del tren, lo que se veía era la
  locomotora asomando cuando la escena ya se iba a negro; sin ningún corrimiento, un tren quieto
  pegado al borde que después arrancaba, que no se lee como un tren sino como un dibujo que se movió.
- **La entidad llega de un solo salto** (`leap=True` en su puesta en escena). El acercamiento normal
  son dos pestañeos y cuenta a alguien que se viene acercando desde hace rato; ella dice que estuvo
  mirando todo el tiempo, así que aparecer a media distancia y después acercarse la contradecía. El
  ruido de la llegada va con el primer salto, sea el que sea.
- **Las cinemáticas van deliberadamente lentas** (`SLEEP_FRAMES`, `BLINK_CLOSE`/`BLINK_OPEN`,
  `HOLD_FRAMES`, `DESCENT_FRAMES`, `LEAVE_FRAMES`, y la `speed` de cada personaje). La primera
  tanda de números era la mitad y la escena se sentía apurada: el personaje aparecía, saltaba dos
  veces y ya estaba hablando. Una cinemática que no se puede contemplar no es una cinemática, es
  una transición. Entrar entero, desde el negro, lleva unos diez segundos a propósito.
- **El tritono suena cuando el señor cambia de cara** (`cinematic.POSE_SOUNDS`). *Diabolus in
  musica*: la disonancia que el libro explica dos capítulos antes entra con la pose `enojado`, que
  es la que pone cuando se lo rechaza. Sólo al **cambiar** de pose, no en cada línea que la use.
- **El valle está dibujado, no degradado** (`_draw_valley_sky`, `_draw_valley_ridge`,
  `_draw_valley_mist`): estrellas que se apagan hacia el horizonte, una luna con halo, dos cadenas
  de cerros a distinta distancia con pinos encima, y manchones de niebla al pie. Todo se dibuja una
  vez con semilla fija --- el valle vuelve tres veces en el relato y tiene que reconocerse --- y son
  figuras del lienzo, así que quedarse quietas no cuesta nada. **Dos trampas de Tk que valen para
  cualquier cosa que se agregue ahí:** el patrón de un `stipple` se ancla al lienzo y no a la
  figura, así que dos formas tramadas iguales pintan *los mismos* píxeles y superponerlas no
  oscurece nada --- el halo de la luna se hace con óvalos macizos, uno adentro del otro, que es el
  mismo degradado por franjas del cielo pero en redondo; y una franja tramada de lado a lado no se
  lee como niebla sino como un alambrado, así que la niebla son manchones sueltos.
- **El que se acerca viene borroso y con la escena empañada** (`cinematic.BLURS`, `Cutscene.HAZES`).
  Tk no sabe filtrar una imagen, así que el desenfoque es pérdida de resolución: se achica de más y se
  agranda de vuelta (`load_pose(..., blur=)`), y la figura queda hecha de bloques. La bruma es un
  rectángulo tramado --- `stipple`, que pinta uno de cada dos píxeles --- del color del cielo. Las dos
  cosas se levantan de a un salto junto con el acercamiento, así que además se lee como algo que
  entra en foco. Es lo que evita que se sepa quién viene, y dónde, desde el primer cuadro.
- **El botón dorado sale sólo en el modo que el tramo pide, y sólo si el tramo se juega con un
  botón.** Aparecía en la primera pantalla de los tres modos, así que no señalaba nada; y el tramo
  del Armonizador no tiene botón: ése se juega tocando una tecla dorada del piano.
- **El tramo del Armonizador es melodía primero.** La tecla dorada dibuja la línea en el pentagrama,
  la hace sonar sola al tempo de la pieza, y recién cuando se apaga la última nota escribe la pieza y
  salta a la pantalla de resultados. Armonizar en el mismo gesto se saltaba justo lo que el tramo vino
  a mostrar y lo dejaba enterrado debajo de cuatro voces.
- **El relato avisa cuando deja algo escrito en el libro** (`_story_noted`). Las anotaciones se
  escriben solas al cruzar un tramo y son además lo que abre la traba del tramo siguiente: sin
  decirlo, había que adivinar que algo había ido a parar al libro. Se dice **que** se anotó y
  **dónde** leerlo; qué dice, no.
- **El ofrecimiento se puede volver a ofrecer, y por eso `may_offer()` pregunta sólo por el
  sendero** (`story.may_offer`, `story.mark_offered`). Preguntaba además por `seen_offer`, que se
  levanta cuando la figura aparece: cerrar la aplicación ---o que se caiga--- en la mitad de esa
  cinemática dejaba la marca puesta con el sendero todavía vacío, y ahí el modo historia **se
  apagaba para siempre y sin que fallara nada**: sin botón, porque el ofrecimiento ya había
  ocurrido; sin recordatorio ni «Arrepentirse», porque las dos cosas cuelgan de tener un sendero.
  Lo mismo costaba arrepentirse, que deja ese mismo estado a propósito. Ahora `seen_offer` decide
  **cómo** vuelve la figura ---sin la espera de cinco minutos, que ya se pagó, así que el llamado
  reaparece en el primer momento tranquilo--- y nunca **si** vuelve. Se anota al **abrir** la
  escena y no al contestarla, que es lo que hace que el corte se note.
- **Y el arnés apaga el ofrecimiento con `ChordWeaverApp.story_offers`, no con `seen_offer`.**
  Apagar algo con un dato del usuario funciona mientras ese dato signifique lo que a uno le
  conviene; `uitest` lo hacía así y dejó de apagar nada en el mismo momento en que `may_offer`
  cambió de pregunta.
- **Un sendero terminado entrega su legendario aunque la cinemática de cierre no se haya jugado**
  (`_story_settle_awards`). El camino se da por recorrido al avanzar el último tramo ---eso se
  guarda--- pero el logro lo entregaba solamente el `after` de la escena final: cerrar el programa
  ahí dejaba el sendero marcado como terminado y el premio sin dar, y como ya no queda ningún tramo
  por avanzar no había nada que volviera a intentarlo nunca. Se pregunta al arrancar, igual que
  `_check_watcher`.
- **`CHORDWEAVER_STORY_DELAY`** acorta la espera de cinco minutos, para probar la cinemática sin
  esperarla.
- **La tipografía de un personaje tiene que venir con Windows** (`cinematic.SPEAKERS`). Bach hablaba
  en Book Antiqua, que no viene con Windows: viene con Office. Donde no está, Tk no avisa nada ---
  cae en su fuente por defecto, que es una sans mínima --- así que el personaje más formal del
  programa hablaba con la peor letra de todas y no había ningún error en ninguna parte. Cambia,
  Georgia, Constantia, Palatino Linotype, Candara, Consolas y Segoe UI sí vienen.
- **El cartelito del nombre se mide, no se calcula** (`Cutscene._fit_plate`). Era de ancho fijo y
  «Johann Sebastian Bach» se salía por la derecha; con la letra al 180% se salía cualquiera.
- **Los personajes son imágenes**, en `assets/story`: PNG recortados con transparencia, varias poses
  por personaje, que `cinematic.POSES` nombra y cada `story.Line` elige con su campo `pose`. Se leen
  con el `PhotoImage` de Tk, que compone el canal alfa solo; **el programa no necesita ninguna
  librería de imágenes para correr**. Los recortes se prepararon una vez, aparte, y ese script no se
  distribuye. Agregar una pose es dejar el PNG en la carpeta y nombrarlo en `POSES`.
- **Tk sólo escala imágenes por factores enteros** (`subsample`, `zoom`), y eso decidió toda la puesta
  en escena. En vez de un acercamiento continuo, el personaje aparece **lejos y a oscuras** --- una
  silueta, no una persona --- y se acerca de golpe, en dos saltos, aprovechando un **parpadeo** para
  cambiar de lugar sin que se lo vea moverse. Los tres planos son `1/4`, `1/2` y `1/1` del recorte.
- **El mismo parpadeo hace tres cosas**: entrar a la escena, mover al personaje y sacarlo. Que sea
  siempre el mismo gesto es lo que hace que el salto se lea como un pestañeo y no como un corte de
  montaje. Se entra **desde** el negro y no cerrando primero: la pantalla que se taparía es la que el
  usuario está mirando, y cerrarla encima se lee al revés de lo que uno espera.
- **Entre dos escenas encadenadas la pantalla no vuelve al programa.** La que termina deja el negro
  puesto (`blackout`) y la que sigue despierta de ahí (`opening="dark"`): un pestañeo largo en vez de
  dos idas y vueltas. Y dos escenas seguidas del mismo personaje son **una sola**: no se va para
  volver a entrar.
- **`assets/` va en `datas` del `.spec`**, no en `hiddenimports`: son archivos, no módulos.
- **`ambience` abre los alias de MCI en el hilo de la interfaz, no en el de síntesis.** MCI le cuelga
  cada dispositivo al hilo que lo abrió y se los cierra sin avisar cuando ese hilo termina: abrirlos en
  el hilo que sintetiza dejaba doce alias muertos, y `play` no fallaba, no se quejaba y no sonaba nada.
  Se abren solos en la primera reproducción, que siempre ocurre en el hilo de Tk.
- **El bucle de la cama de ambiente se hace a mano, y hay que preguntar en cada cuadro.** MCI acepta
  `play alias repeat` pero lo ignora para audio: el archivo suena una vez. `ambience.pump()` ---
  que la cinemática llama en cada cuadro de su bucle --- pregunta si dejó de sonar y lo repone con
  `play from 0`. **El silencio que se oía en el empalme era esta pregunta llegando tarde**: el
  archivo ya está preparado para repetirse sin costura (`_seamless` cruza la cola dentro de la
  cabeza), así que lo único que se escucha ahí es cuánto tardamos en darnos cuenta de que terminó.
  Preguntando cada doce cuadros eran cuatro décimas de nada; en cada uno, treinta milésimas, y la
  consulta cuesta 0,1 ms.
- **El relato nunca avanza solo después de una partitura.** La escena que cierra un tramo aparecía un
  segundo después del resultado y se comía lo único que ese tramo tenía para dar: escucharlo. Ahora
  aparece un botón dorado «Seguir» y la escena espera a que lo toquen.
- **Los personajes no nombran las pantallas del programa.** Ellos dicen qué quieren escuchar; el
  `Step.goal` y el `Step.hint` --- que son la voz del programa, no la de ellos --- dicen dónde se hace.
- **El nombre del sendero no se muestra hasta terminarlo** (`Path.title(finished)`), y los apartados
  del capítulo VII muestran `? ? ?` en vez de su título mientras siguen cerrados. En un relato de tres
  caminos, saber cuál se está caminando es el final.

## Huevos de pascua

Seis combinaciones exactas que el programa reconoce y que no están escritas en ninguna pantalla: el
rugido en el Armonizador, el zorro en la configuración del algoritmo, la viñeta de los anteojos, la
explosión del Generador al máximo, la frase del cerrajero y la de Bach. Completarlos todos habilita
un título secreto que se cobra tocando el huevo.

- **`engine/eggs.py` son las condiciones, y son funciones puras.** No dibujan ni suenan nada, igual
  que el resto de `engine/`: se prueban sin abrir la ventana. Lo que vive en `app.py` es sólo la
  reacción --- el ruido, el cartel o la animación.
- **No son logros, y por eso no están en `achievements.py`.** Un logro se anuncia, se lista y explica
  cómo se consiguió; un huevo que se anuncia deja de ser un huevo. Lo único visible es un contador
  dorado al pie de la pantalla de logros que dice cuántos van y jamás cuáles faltan.
- **El estado va en `eggs.json`**, al lado de los otros tres. `settings.json` es una lista blanca de
  preferencias y `achievements.json` el registro de lo conseguido: un huevo encontrado no es ninguna
  de las dos cosas.
- **Los tres ruidos no se sintetizan al arrancar** (`ambience.summon`, `ambience._ON_DEMAND`): casi
  ninguna sesión los va a escuchar, y hacer esperar a la historia mientras se calculan sería pagarlos
  todas las veces para usarlos casi ninguna. Se hacen la primera vez que alguien da con la
  combinación.
- **El título secreto se entrega tocando el huevo, no al encontrarlos.** Que el premio haya que ir a
  buscarlo es la última parte del chiste.
- **Los dos carteles van sobre un manto del color del fondo.** Tk no sabe de transparencias: un marco
  redondeado pinta sus esquinas del color de su padre, y encima de un panel claro esas cuatro
  esquinas se veían como un recuadro cuadrado alrededor del borde dorado.

## Las visitas

Cuatro apariciones sueltas que no son el sendero: **Bach** a las cinco partituras
barrocas y otra vez al primer coral, **Gregorio I** a las cinco gregorianas, una
**entidad encapuchada** al conseguir el cien por ciento de los logros, y **la
visión** del cruce de caminos al abrir el programa --- una vez de cada cinco,
con el tutorial ya terminado u omitido, y una sola vez en la vida. Se ponen en escena con la misma maquinaria que el
sendero: la cola de escenas, el fundido a negro y `cinematic.speak`.

- **`engine/visitors.py` es el guion y el registro**, y no dibuja ni suena nada,
  igual que `story.py` y que `eggs.py`. Ahí están los diálogos, la cuenta de
  partituras por género y `Ledger`.
- **El estado va en `visitors.json`**, al lado de los otros cuatro. `settings.json`
  es una lista blanca de preferencias, `achievements.json` el registro de lo
  conseguido y `story.json` el sendero: cuántas partituras barrocas lleva hechas
  el usuario no es ninguna de las tres cosas.
- **Una visita se marca cuando la escena termina, no cuando se decide.** Si se
  marcara al dispararla, cerrar el programa en la mitad le costaría al usuario
  una aparición que no llegó a ver y que no vuelve a ocurrir.
- **Una visita no devuelve al usuario a la pantalla inicial.** Al revés que el
  sendero: la escena se abre encima de la pantalla de resultados de la corrida
  que la disparó, y ésa sigue estando abajo cuando se va. Mandarlo al principio
  le sacaría la partitura por la que vinieron a felicitarlo.
- **La quinta barroca puede ser además la primera coral, y entonces Bach dice
  las dos cosas en una sola escena.** `Ledger.record` devuelve las claves ya
  ordenadas --- primero qué es el barroco, después qué lo distingue del coral ---
  y encolarlas seguidas las une, porque dos escenas del mismo personaje son una.
- **La entidad no deja nada escrito en el libro** (`visitors.WRITES`). Los otros
  tres explican algo; ella mira, avisa de algo que todavía no pasó y se va. Un
  apartado con su profecía adentro sería el único del libro que no enseña nada.
  Lo que sí deja son dos regalos: la partitura quemada --- el cuarto objeto, al
  lado de los tres de los senderos --- y **la lista de los seis huevos de pascua
  con los pasos exactos**, al pie de la pantalla de logros. Es lo único en todo
  el programa que los nombra, y hace falta el cien por ciento para justificarlo:
  a esa altura ya no queda nada que arruinar.
- **Las visitas no se abren encima de una animación de logro.** Completar el
  último logro casi siempre trae además una estrella o un legendario, que son
  velos a pantalla completa; `_watch_watcher` espera a que la pantalla quede
  libre en vez de dibujarse encima.
- **Los dos maestros aparecen y desaparecen de un pestañeo** (`entrance="present"`,
  `departure="vanish"`). No se los ve venir de lejos ni irse caminando: la pantalla se abre y ya
  están, y cuando terminan de hablar uno cierra los ojos y no quedó nadie. El acercamiento --- que
  es la entrada del señor del sombrero --- cuenta otra historia: la de algo que se viene acercando
  hace rato. La entidad sí se acerca, porque de ella eso es exactamente lo que hay que contar.
- **Lo que queda escrito en el libro no es la taquigrafía de lo que se dijo en la escena.** El
  apartado tiene lo que el personaje contó *y* lo que se averiguó después --- los cuatrocientos
  kilómetros que Bach caminó para escuchar a Buxtehude, el mes que estuvo preso, la paloma de
  Gregorio, Guido de Arezzo inventando el pentagrama ---, escrito como lo anotaría alguien que
  acaba de tener una aparición. Copiar el diálogo dejaba el libro sin nada que el usuario no
  hubiera leído dos minutos antes.
- **El fondo de las tres visitas es el negro, y es negro *tramado* sobre el color
  del programa** (`cinematic.VOID_UNDER`, cielo `void`). Tk no tiene
  transparencia: un lienzo tapa lo que hay debajo y no hay forma de que no lo
  tape. Pintar el negro con `stipple` encima del color de la ventana da
  exactamente el efecto de un velo con un poco de transparencia, que es todo lo
  que estas escenas necesitan: no vienen de ningún lugar, así que dibujarles un
  valle las mandaría a un sitio.
- **Los sonidos de las visitas se sintetizan a pedido** (`ambience._ON_DEMAND`),
  por lo mismo que los de los huevos: cada una ocurre una vez en la vida del
  programa. Como pueden no estar listos cuando la escena se abre, `Cutscene`
  reintenta la cama de ambiente en cada cuadro (`_start_bed`) --- antes, la
  escena entera quedaba en silencio por haber preguntado medio segundo antes de
  tiempo.
- **La visión es la única cosa del programa que no se puede provocar.** No hay
  logro, ni sendero, ni combinación que la traiga: es una en cinco al abrir, y
  vista una vez no vuelve. Por eso la anotación que deja --- Robert Johnson ---
  se muestra en dorado y con el título escondido, como un legendario
  (`book.Entry.legendary`), mientras que las tres de los maestros muestran su
  título, que es la pista de qué hay que hacer.
- **Y no ocurre hasta que el tutorial esté terminado u omitido**
  (`visitors.vision_due`, que recibe la condición y no la adivina). La primera
  vez que alguien abre el programa lo que tiene enfrente es el recorrido
  guiado: la visión llegaría antes de que hubiera visto un acorde, sin nada con
  qué leerla, y se gastaría la única vez que ocurre. La condición vive en la
  función pura y no confiada al `_story_quiet()` de la interfaz ---que también
  la contempla, junto con todo lo demás que hace que un momento no sea
  tranquilo--- porque es una condición **de la visión** y no del momento, y
  porque es lo que permite además no sintetizar sus cinco ruidos
  (`_warm_vision`) en el único arranque donde con seguridad no puede pasar. El
  parámetro no lleva valor por defecto a propósito: un default sería la
  condición vieja entrando en silencio si alguien se olvida de pasarlo.
  `CHORDWEAVER_VISION=1` saltea el sorteo, pero no el chequeo de momento
  tranquilo: con el tutorial sin hacer sigue sin aparecer, que es como se
  comportaba desde antes.
- **La visión no habla y no tiene cuadro de diálogo** (`cinematic.Vision`, aparte
  de `Cutscene`). Lo único que comparte con el resto es el pestañeo: cerrar los
  ojos y que al abrirlos la figura esté más lejos, que es el idioma con el que
  este programa mueve gente por la pantalla.
- **Y no dice nada en ninguna parte**: ni una línea sobre el negro del principio, ni un rótulo
  arriba, ni el cartelito de «quedó algo escrito en el libro» al terminar --- que es lo que sí hacen
  todas las demás. Nadie habló, nadie explicó y nadie dijo quién era; un aviso al final convierte
  una aparición en una notificación. La anotación está en el libro para el que vaya a buscarla.
- **La visión termina de golpe.** Después del último pestañeo quedan tres segundos y medio de camino
  vacío --- que es donde suena la guitarra sola, y donde se entiende que lo que se fue no vuelve ---
  y después un pantallazo negro, sin fundido: la visión no termina, se corta.
- **El que se va no vuelve a darse vuelta.** Hubo una versión donde miraba una última vez desde
  lejos; eso lo convertía en alguien que se despide, y éste no se despide. Lo último que se ve de él
  es la espalda.
- **Los pestañeos de la visión son más lentos que los de una escena de diálogo.** Ahí son un recurso
  para mover a alguien; acá son lo único que pasa en pantalla durante diez segundos.
- **El que se aparece está iluminado como de noche, y siempre igual.** Los recortes ya vienen
  apagados y con tinte azul (`robert-frente.png`, `robert-espalda.png`); no hay versiones cada vez
  más oscuras para cuando se aleja, porque oscurecerlo de a poco hacía que la noche pareciera caer
  en veinte segundos. Lo que lo apoya en el piso es la sombra a sus pies, no el color.
- **El decorado del cruce es todo de figuras del lienzo, dibujadas una sola vez**: cielo con
  estrellas, la luna llena con sus mares centrada justo sobre el punto de fuga, un camino de tierra
  en franjas con las dos huellas de las ruedas y piedras que crecen con la distancia, y un tren de
  dieciséis vagones cruzando el horizonte. Lo único que se mueve es el tren, el viento y el pasto
  --- tres puntos por mata y por cuadro, que es lo más barato que se puede animar en un canvas.
  **El tren no lleva humo**: pasa justo por debajo de la luna y las volutas se veían como una
  mancha oscura pegada al halo.
- **El tren y los búhos suenan** (`ambience._train`, `_owls`), y el ruido de la aparición está
  mezclado bien por encima del viento: es lo único que suena en ese momento y tiene que taparlo, no
  acompañarlo.
- **`uitest.Session` apaga las visitas enteras**, no sólo la visión: el arnés
  genera decenas de partituras seguidas, que es exactamente lo que hace aparecer
  a Bach. Se dan por vistas en memoria y el registro se manda a un archivo
  descartable, así que los datos de verdad no los toca nadie.
- **PROVISORIO: hay botones de prueba en la configuración** (`_preview_scene`, y el bloque de
  `_open_config` marcado con `PROVISORIO` de punta a punta). Abren cualquiera de las cuatro
  apariciones sin cumplir lo que cada una pide. Se juegan enteras, con sus recompensas, así que la
  que se mire desde ahí no vuelve a aparecer sola. Sacarlos es borrar ese bloque y el método.
- **`CHORDWEAVER_VISIT`** fuerza una visita al abrir (`watcher`, `bach_baroque`,
  `bach_chorale`, `gregory`) y **`CHORDWEAVER_VISION=1`** fuerza la visión. Es la
  hermana de `CHORDWEAVER_STORY_DELAY` y existe por lo mismo: sin ella no hay
  forma de mirar ninguna de las dos por segunda vez. Forzadas se juegan enteras,
  recompensas incluidas, y se pueden repetir.

## Archivos sensibles

- **`engine/theory.py`** — está debajo de todo. Cambiar la representación de un pitch o el parser de
  cifrado rompe el motor entero, en silencio.
- **`engine/fitness.py` y `engine/style.py`** — tocar un peso cambia el resultado musical de todas las
  generaciones sin que falle ningún test. Los números están calibrados contra `audit.py`; si se
  modifican, correr la auditoría y comparar contra el control.
- **⚠ Y si esos dos —o `theory.py`— están compilados, EDITAR EL `.py` NO HACE NADA.** El `.pyd` gana
  en el orden de importación, así que un cambio en el fuente queda invisible hasta recompilar: se
  edita, se corre, no pasa nada, y lo que se busca es el bug en otro lado. Es el filo de todo esto.
  `python build_engine.py` después de tocar cualquiera de los tres, o `--clean` mientras se trabaja.
  `ls engine/*.pyd` dice en un segundo si el motor está compilado.
- **⚠ Y con el motor compilado, parchear una función de `engine/` desde afuera NO HACE NADA** si
  quien la llama está en el mismo módulo. Cython resuelve esas llamadas a nivel C, así que
  `ga.evaluate = mi_espia` deja el espía puesto en el diccionario del módulo y `_seed_chromosome`
  sigue llamando a la de verdad, **sin error y sin aviso**. Pasó midiendo: una tanda entera de
  diagnóstico dio resultados que parecían decir una cosa y no medían nada. Cualquier herramienta que
  instrumente el motor por dentro ---y `verify_ui.py` y los scripts sueltos lo hacen--- tiene que
  correr con `python build_engine.py --clean`. `tests.py` no lo necesita: prueba por la API pública.
- **`engine/fitness.pxd` y `engine/style.pxd`** — la hoja de tipos, y **son fuente, no generados**.
  Una firma de ahí tiene que coincidir con la del `.py`: si no, la compilación falla ---que es lo
  que uno quiere--- pero el `.py` se queda andando, así que el error aparece recién al compilar y no
  al editar. Cambiar la firma de una función declarada ahí es cambiar dos archivos.
- **`ChordWeaver.spec`** — los `hiddenimports` están listados a mano para que un import faltante rompa
  el build en vez del ejecutable ya entregado. Módulo nuevo en `engine/` → agregarlo a esa lista.
- **`history.json`**, **`achievements.json`**, **`story.json`**, **`eggs.json`** y
  **`visitors.json`** — datos reales del usuario (últimas 10 producciones; logros conseguidos; por
  dónde va el sendero; qué huevos encontró; cuántas partituras lleva hechas de cada género y a quién
  vio), no código. Borrar el segundo le saca los logros al usuario sin aviso; borrar el tercero le
  hace perder el camino que venía recorriendo; borrar el cuarto le borra la búsqueda entera; borrar
  el quinto le devuelve visitas que ya vio y le puede regalar de nuevo la visión, que es lo único
  que ocurre una sola vez.
- **`assets/story/*.png`** — los recortes de los personajes, los tres del sendero y los tres de las
  visitas. **Van ajustados a la figura y con 720 px de alto**, todos igual: el retrato se ancla por los pies, así que un archivo con
  transparencia de sobra abajo deja al personaje flotando, y una figura que no llene el alto se ve
  más chica que las demás. Media docena estaban guardados enteros --- la imagen de 1408x768 de la que
  salieron --- y el personaje se achicaba y subía al cambiar de pose en la mitad de una frase.

La versión del programa es **una sola**: `engine.__version__`. La interfaz la muestra chiquita y
gris al pie de la configuración y la lee de ahí; no hay una segunda copia en ninguna parte.

Generados / descartables: `__pycache__/`, `output/`, `build/` y los `engine/*.pyd`
(`python build_engine.py --clean`). Los `.pxd`, en cambio, **son fuente**: son la hoja de
tipos y se editan a mano.
`verify_ui.py` es un script suelto de verificación manual; `uitest.py` maneja la interfaz a través de
los widgets reales (clics, tipeo) porque es la única forma de cachar los bugs donde el motor está bien
y la interfaz nunca le hace la pregunta correcta.

**`CHORDWEAVER_DATA_DIR` muda TODOS los datos a otra carpeta** (`history.SANDBOX_VARIABLE`). Los seis
archivos del usuario —historial, logros, sendero, huevos, visitas y preferencias— y `output/` cuelgan
de `history.base_directory()`, así que mover la raíz los mueve a todos de una vez. `uitest.py` la pone
**antes de importar `app`**, y ésa es la única protección que no se puede olvidar: reapuntar seis rutas
a mano es una lista que hay que mantener, y alcanza con que un script construya `ChordWeaverApp`
directamente —sin pasar por `Session`— para que una corrida de prueba quede anotada en el historial de
verdad, que guarda las diez últimas. Pasó tres veces antes de que existiera esta variable. Hay un test
que verifica que las seis rutas y `output/` la respetan, y que una carpeta imposible vuelve al lugar de
siempre en vez de impedir que el programa arranque.

**`tests.py` la pone también**, y no por costumbre: varios tests llaman a `session.export_outcome`, que
por defecto anota la corrida en el historial. Correr la suite le metía media docena de entradas al
archivo del usuario —que guarda las diez últimas— cada vez.

**`uitest.Session` además manda los cinco archivos de datos —y las preferencias— a descartables**, uno
por uno. El
arnés genera decenas de partituras seguidas y **cada corrida que termina se anota en el historial**
(`_record_production`), que guarda las diez últimas: diez corridas de prueba bastaban para borrar el
historial de verdad, y los logros que consigue el arnés son logros que el usuario no consiguió. Por eso
`ChordWeaverApp.history_path` existe —`None` es el archivo de al lado del programa— y por eso el arnés
también reapunta `achievements`, `eggs`, `story` y `settings`. Cualquier script que abra la ventana
tiene que pasar por `uitest.Session`; abrir `ChordWeaverApp` a mano escribe sobre los datos del usuario.

Las preferencias son el caso menos obvio y el que más tardó en aparecer: **se leen del archivo de
verdad** —el arnés tiene que correr con la configuración del usuario— **pero se escriben en un
descartable** (`ChordWeaverApp.settings_path`). Escribe cualquier cosa que llame a `save_settings`: el
panel de configuración al cerrarse, el final del tutorial, y `_mark_notes_seen`. Ese último es el que
duele: `book_seen` es lo que decide qué anotaciones del libro le figuran como nuevas al usuario, así
que una corrida de prueba que abriera el libro le daba por leído algo que nunca leyó.

## Desfasajes conocidos

Ninguno conocido. El recuento de tests de `README.md` se actualiza junto con `tests.py`.
