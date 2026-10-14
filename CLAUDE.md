# CLAUDE.md — contexto operativo compacto

## Regla de documentación

Este archivo se carga entero en cada sesión. Sólo documentar aquí:
- cosas que se rompen si se ignoran;
- decisiones que un cambio razonable podría revertir accidentalmente;
- trampas que no se deducen rápido leyendo/grepando el código.

No repetir lo que ya expresa el código. No guardar crónicas, benchmarks ni justificaciones históricas salvo que el dato numérico sea la razón de una restricción. Al cambiar una regla documentada, actualizar/remover la anterior en vez de sumar texto.

Para la lógica musical detallada, leer `MUSIC_LOGIC.md`. Solo leer si se requiere algo musical, sino ignorar

## Proyecto

ChordWeaver es una app de escritorio que optimiza voice leading con un algoritmo genético. El usuario fija acordes/voces/reglas; el AG decide registro y reparto de notas, nunca cambia la progresión.

Además del motor generativo hay dos herramientas que **no componen nada**: el experimentador de armónicos y el analizador. El analizador va en la dirección contraria a todo lo demás --- recibe una partitura escrita y le pone nombres.

Modos internos:
- `manual` = Organizador
- `random` = Generador
- `harmonise` = Armonizador

La GUI visible llama a `engine.session` como fachada. `engine/` no debe importar GUI.

### Dependencias / restricciones

- Python 3.9+.
- GUI: `customtkinter` + `tkinter`.
- MusicXML/MIDI/WAV se escriben a mano; no introducir `music21`, `mido`, `numpy`, etc.
- Cython es opcional y acelera el motor; los `.py` deben seguir funcionando sin él.
- No es un repositorio git.

## Comandos útiles

```bash
pip install customtkinter
python app.py
python tests.py
python tests.py TestClase.test_x
python audit.py
python cli.py --chords "Cmaj7 Am7 Dm7 G7" --genre jazz
python build_engine.py
python build_engine.py --clean
pyinstaller ChordWeaver.spec
```

`cli.py` debe ejecutarse desde la carpeta que contiene `cli.py`.

## Arquitectura que no hay que romper

Dependencia principal:

```text
app.py / cli.py
  → engine.session
    → ga
      → fitness
        → style
          → theory
```

`session.py` es la fachada: `generate()`, `generate_random()`, `harmonise_melody()`, `export_outcome()`, `apply_flourishes()`.

`theory.py` está en la base y no importa módulos del proyecto.

Distribución:
- búsqueda / AG: `engine/ga.py`
- evaluación: `engine/fitness.py`
- reglas por género: `engine/style.py`
- teoría, notas, voces, parser: `engine/theory.py`
- voicing: `engine/voicing.py`
- armonía: `engine/harmony.py`
- armonización: `engine/harmonize.py`
- passing: `engine/passing.py`
- flourishes: `engine/flourish.py`
- exportación: `engine/export.py`
- audio: `engine/audio.py` (cuándo suena cada nota) + `engine/timbre.py` (cómo suena: timbres y lector de WAV)
- persistencia: `engine/history.py`
- logros: `engine/achievements.py`
- libro: `engine/book.py`
- historia: `engine/story.py`
- huevos: `engine/eggs.py`
- visitas: `engine/visitors.py`
- ambiente: `engine/ambience.py`
- armónicos (síntesis): `engine/harmonics.py`
- análisis de partituras: `engine/analysis.py`
- cinemáticas: `cinematic.py`
- pentagrama (una línea y sistema de dos): `staff.py`
- experimentador de armónicos: `spectrum.py`
- analizador (pantalla): `analyzer.py`
- escuelita: `engine/school.py` (lecciones, corrección, progreso, graduación) + `school.py` (pantalla)
- aviso de version nueva: `engine/updates.py` (consulta) + `updater.py` (cartel)
- idiomas: `engine/i18n.py` (motor) + `engine/lang/` (catálogos) + `chooser.py` (cartel de la primera vez)

`staff.py`, `spectrum.py`, `analyzer.py`, `school.py`, `updater.py`, `chooser.py` y `homeart.py` no importan `app.py`: reciben la paleta por parámetro (`colours=...`). No agregarles un import de la aplicación.

### Contrapunto

`fitness.py` contiene la mecánica de evaluación; `style.py` contiene reglas idiomáticas. Los perfiles de género cambian pesos/defaults, no la mecánica. Si una regla nueva necesita comportamiento distinto por género, mantener la diferencia como peso/configuración antes que duplicar el evaluador.

Para detalles de reglas, excepciones y orden de chequeos: `MUSIC_LOGIC.md`, secciones 6–7.

## Particularidades del AG

- El cromosoma es armónicamente correcto por construcción: cada gen sale de candidatos válidos para ese acorde.
- Las restricciones duras pueden anular la mayoría de los hijos; cualquier relleno de población debe reutilizar el costo ya conocido cuando sea posible y no volver a evaluar clones idénticos.
- Los hijos deben despacharse al pool progresivamente, no acumular toda la generación antes de puntuar. No cambiar el orden de cría/azar si se pretende preservar reproducibilidad por semilla.
- El paralelismo es con procesos, no hilos: el trabajo es CPU-bound.
- `main()` debe llamar `multiprocessing.freeze_support()` para PyInstaller/Windows.
- Tk no se toca desde workers. Los workers comunican resultados mediante cola y el main loop los consume por timer.
- Un worker no puede usar `tk.after()` para agendar UI. Las acciones de finalización deben ser observadas desde el hilo principal.
- `setswitchinterval` se ajusta temporalmente en trabajos CPU/sonido muy largos y debe restaurarse.
- `app.py` desactiva finalizadores de ciertos objetos Tk para evitar que GC termine ejecutando Tk desde el hilo de búsqueda. No revertir sin entender el problema.
- `harmonize.py` trabaja hacia atrás (desde el final hacia el inicio) porque el siguiente reposo condiciona la función del acorde actual.
- Los silencios se omiten en la búsqueda. **`solution.slots` NO está alineado con `spec.slots`.** Cuando haga falta alinear solución con partitura, usar `session.voiced_slots(spec, solution)`.
- **`outcome.spec.slots` no son los acordes de todas las opciones**: en el Armonizador cada una tiene su progresión (`alternate_slots`, y `spec.slots` es la del primer intento, no la que quedó primera) y en el Generador la cita lleva los suyos. Para exportar, rotular o marcar una opción: `session.solution_slots(outcome, i)`.
- Los adornos se manejan aparte de los acordes porque tienen duraciones parciales y voces individuales. La duración total del compás debe seguir sumando lo mismo.
- `flourish.py` corre después de la búsqueda, sobre el ganador; no meterlo en el fitness salvo que se rediseñe explícitamente la función objetivo.
- En armonización, la partitura exportada usa la línea real del usuario (`MelodyLine`), no la versión muestreada que vio el AG.

## Armonización / slots

- La armonización coloca acordes en los tiempos fuertes y puede abrir nuevos lugares para última nota, sensible o nota marcada.
- `spot_for_note()` debe conservar la suma exacta de duración del compás: si no hay lugar suficiente para crear un nuevo slot, el sobrante vuelve al slot anterior.
- Una nota marcada lleva `MelodyNote.must_harmonise` y `required_note`; no permitir que el selector la ignore.
- La sensible final puede forzar dominante mediante `harmonize.pin_leading_tone`.
- No crear acordes después de que terminó la melodía: los tiempos sobrantes del último compás pertenecen al último segmento que realmente ocupa la melodía.
- **Nota fuera de la escala** (`harmonize.pin_chromatic_approaches`): si sube un semitono a la siguiente se marca sola y su lugar queda limitado a `approach_options` (V/x; en barroco y jazz también vii°/x con `LEADING_APPROACH_CHANCE`); en jazz la que baja lleva subV/x. La nota de llegada se abre **antes** que la cromática (al revés, una cromática corta podía quedar corrida sobre la llegada). `harmonise`, `planned_notes` y `drop_skipped_spots` eligen la nota del lugar con el mismo `_spot_pool`: si uno no lo usa, el pentagrama marca una cosa y suena otra. Los acordes cromáticos (`chromatic_options`) no pasan por el sorteo de `_borrowed_allowed` y sólo entran cuando la nota del lugar es cromática.
- **La armadura del Armonizador es mayor o menor según la nota final** (`harmonize.key_of_ending`, desde `_build_melody`), y el menor es el **natural**: es el que tiene la escala de la armadura, así que lo que el pentagrama pinta de naranja sigue siendo lo que el motor trata como cromático. Con el armónico se separan.
- La nota final lleva un acorde solo (`harmony_spots`) y el último acorde va con la fundamental en el bajo (`session._close_on_the_root`). Sin lo segundo, a tres voces con la melodía en la tónica, casi toda armonización terminaba invertida.
- La melodía del Armonizador guarda los accidentes **aparte** de `staff.notes`: `StaffEditor.accidentals` (posición → alteración), y la app los guarda en `_melody_accidentals` y los pasa a `_build_melody(alterations=...)`. `notes` sigue siendo de pares porque media aplicación los desempaca así; meterles un tercer elemento rompe en silencio cada uno de esos lugares.

## Silencios, reproducción y adornos

- Los silencios no entran al AG, pero sí deben conservarse al mapear a la partitura/reproducción.
- `build_settings` puede usar un pitch de relleno para mantener la alineación interna; visualmente manda `is_rest`, nunca ese pitch.
- Los adornos vacían el slot de acorde durante su duración y se reproducen como voces parciales con tiempos propios.
- Los adornos se indexan por slot de búsqueda, por lo que cualquier acceso contra `spec.slots` debe reubicar primero con la misma lógica que `voiced_slots`.
- La sexta de Bach (`apply_flourishes` → `flourish.apply_sixth`) reescribe `best.slots`, así que cuenta candados y voces fijas (`pinned_voices`, la melodía del armonizador) **sobre los slots que suenan**, y `FlourishResult.sixth_slot`/`forced_slot` vuelven en columnas de la partitura. Contados sobre `spec.slots`, un silencio corría los candados y la sexta reescribía un acorde con candado.
- `export.DIVISIONS_PER_QUARTER` es 48 y la cola de una figura se reparte en divisiones enteras: con 8, un tercio de negra se redondeaba, la voz sumaba de más que el `<backup>` y las voces siguientes salían corridas. No bajarlo. Lo vigila `TestExportRoundTrip`.

## Cython: filo importante

Si existen `engine/*.pyd`, el `.pyd` gana al `.py` en importación.

**Después de modificar cualquiera de los seis ---`theory`, `fitness`,
`style`, `ga`, `voicing`, `harmony`---, recompilar o limpiar.** Vale también
para un cambio de traducción: envolver una cadena con `trf()` en
`voicing.py` no se ve hasta recompilar, porque el `.pyd` viejo sigue
ganando.
```bash
python build_engine.py
# o durante desarrollo:
python build_engine.py --clean
```

Comprobar rápido:
```bash
ls engine/*.pyd
```

Con Cython:
- `fitness.pxd` y `style.pxd` son fuente mantenida a mano; las firmas deben coincidir con los `.py`.
- Los `.pxd` no son generados y Python los ignora.
- `cdef` hace una función invisible desde Python; `cpdef` mantiene wrapper Python.
- No reescribir funciones sólo para satisfacer limitaciones de Cython si la separación actual ya funciona.
- `wraparound` no se puede apagar.
- Instrumentar/parchear desde Python una función llamada internamente dentro de un módulo compilado puede no interceptar la llamada: Cython puede resolverla a nivel C. Para instrumentación interna usar `python build_engine.py --clean`.
- Los tests sobre la API pública pueden correr con o sin `.pyd`.

## PyInstaller

El build es de carpeta, no `--onefile`: el programa necesita persistencia junto al ejecutable.

`ChordWeaver.spec` mantiene `hiddenimports` manualmente. Si se agrega un módulo que necesita empaquetarse, revisar esa lista.

`export.ScoreSpec.fifths` existe para el analizador --- los tres modos que generan escriben en Do y lo dejan en cero. `_note_xml` escribe `<accidental>` sólo cuando la alteración **difiere** de la armadura; con `fifths=0` eso es exactamente lo de siempre.

**Sin consola, `sys.stdout` y `sys.stderr` son `None`** y cualquier `write` mata el ejecutable al arrancar («Failed to execute script 'app'»). customtkinter escribe un aviso al importarse cuando Windows no le carga la fuente de formas, y eso pasa con rutas de más de 260 caracteres. `app.py` llama a `console.guard_streams()` **antes** del primer import de customtkinter (lo vigila `TestConsoleless`) y después `_rescue_widget_fonts()` vuelve a cargar las fuentes desde la carpeta temporal. Desde el fuente nunca se ve: hay consola. Para probar un build, abrir el `.exe` sin consola desde una carpeta profunda.

Los assets del programa deben resolverse desde `program_directory()`. En modo congelado los assets de PyInstaller están bajo `_internal/`; `base_directory()` es para datos del usuario y no debe usarse para localizar `assets/`.

## Persistencia

Los datos de usuario incluyen:
- `history.json`
- `achievements.json`
- `story.json`
- `eggs.json`
- `visitors.json`
- `school.json`
- preferencias/settings
- `output/`
- `chordweaver.log` (lo que se escribe a consola cuando no hay consola; ver `engine.console`)

`DEFAULT_SETTINGS` es una **lista blanca**: si se agrega una preferencia nueva y no se suma allí, se guarda y luego desaparece al recargar.

`engine.__version__` es la única fuente de versión de la app, y es contra lo que compara el aviso de versión nueva.

`CHORDWEAVER_DATA_DIR` redirige todos los datos del usuario y `output/`. No repartir rutas manualmente.

### Tests / UI tests

`tests.py` también puede escribir historial porque algunas rutas llaman `export_outcome`. Por eso la suite debe ejecutarse con aislamiento de datos.

`uitest.Session` debe usarse para tests de GUI: redirige historial, logros, historia, huevos, visitas, escuelita y preferencias a descartables. No abrir `ChordWeaverApp` directamente desde un script de test que pueda persistir datos.

`uitest` fija `CHORDWEAVER_DATA_DIR` al importarse (con `setdefault`), así que las preferencias también se leen del descartable. Para probar una configuración real, copiar su `settings.json` ahí; las escrituras del test nunca van al archivo real.

`uitest.Session` abre la ventana **fuera de la pantalla principal** (`_placed`: `CHORDWEAVER_TEST_ORIGIN`, o la primera pantalla secundaria que haya): una suite abre decenas de ventanas y se le ponían encima a quien estaba trabajando. Pasarle sólo el tamaño. Un script que use `uitest` y genere con el AG tiene que ir debajo de `if __name__ == "__main__":` --- los procesos del pool se lanzan con `spawn`, vuelven a correr el script y cada uno abría su propia ventana.

## UI / Tk

- Tk no es thread-safe.
- Ningún worker toca widgets.
- El worker tampoco debe llamar métodos de Tk indirectamente.
- `Ctrl+Z` debe activar el mismo botón/acción de deshacer que la UI (`invoke`), no duplicar la lógica llamando directamente a `staff.undo`.
- `bind_deeply()` debe evitar duplicar eventos de `customtkinter`: varios widgets CTk envuelven canvas/labels internos.
- `CTkFrame` puede dibujar fondos incluso con apariencia transparente; no crear cientos de frames CTk para contenido plano si basta un `tk.Frame`/`tk.Label`.
- **Un `CTkFrame` sin hijos mide 200×200.** No dejar uno vacío dentro de una franja de un renglón: la franja de la tonalidad del analizador pasaba a medir cuatro veces lo suyo cuando la pieza no tenía cadencias ni acordes ajenos que poner en él.
- Las filas masivas de listas (p. ej. logros) usan widgets Tk simples por rendimiento.
- `_render()` tiene **doble búfer**: cada pantalla es un marco nuevo `place`-ado dentro de `self.stage`, se arma y se dibuja **debajo** de la vieja (`lower`, que Windows recorta) y recién ahí se sube. `self.body` se reasigna en cada render: no guardar referencias al marco viejo. customtkinter dibuja sus esquinas al recibir tamaño, así que armarlo desmapeado no alcanzaba: aparecía por tramos.
- La pantalla inicial **no se rearma** al volver: queda puesta debajo de la actual y `_refresh_home` rehace sólo logros, libro y sendero. Lo que obligue a rearmarla entera va en `_home_signature` (idioma, escala, cantidad de tarjetas); una tarjeta nueva con estado propio tiene que refrescarse ahí o entrar en la firma.
- Un `_render` pedido mientras otro dibuja (un click o un timer atendido en el `update()` interno) **sólo marca `_render_again`**, y el redibujado se agenda una vez al terminar. No agendarlo con `after_idle` desde la rama de reentrada: el mismo `update()` lo vuelve a correr, se reagenda y el programa se cuelga para siempre. Por lo mismo `_drain_queue` no consume la cola mientras `_rendering`: la pantalla vieja sigue viva y un resultado dibujado ahí se pierde.
- **El resultado se ve como partitura** (`_option_staff`: un `GrandStaff(editable=False)` por opción) y la tabla de nombres de nota queda a un click (`_set_results_view`); con más de cuatro voces sólo hay tabla, porque el sistema tiene cuatro carriles (`STAFF_LANES` reparte las voces por tipo). Las dos vistas leen las mismas columnas de `_option_columns`: lo nuevo que se quiera mostrar de un acorde va ahí, o una vista lo dice y la otra no. En la partitura el tinte de la tabla es el color del cifrado (`GrandStaff.symbol_colours`), y `uitest.chord_headers`/`tinted` leen las dos.
- Volver al resultado desde un desvío (analizador, libro, logros) rearma la pantalla y `_screen_results` la redibuja con `_draw_outcome` si `_results_ready`. **`_draw_outcome` sólo dibuja**: lo que pasa una vez por búsqueda ---adornos, historial, logros, visitas, sendero--- va en `_on_finished`, o se repite cada vez que se vuelve. Antes no se redibujaba y quedaba «Buscando soluciones» para siempre.
- Los avisos de logro son **dos a la vista** (`MAX_TOASTS`); el resto espera en `_toast_backlog` y entra cuando se va uno. Cerrar el más viejo para hacer lugar perdía avisos que nadie llegaba a leer.
- Animar preferentemente color y coordenadas de widgets `place`-ados; evitar animar geometría de layouts empaquetados.
- `ACCENT` y `ACCENT_HOVER` son variables: `_apply_accent()` las cambia según el modo. Elementos creados una sola vez pueden necesitar actualización manual.
- El tutorial se inicia sólo la primera vez; `uitest` debe desactivarlo en memoria, no persistiendo ese cambio en los datos reales.

Además del recorrido de bienvenida hay **guías de pantalla** (`SCREEN_GUIDES`): la misma clase `Tutorial` con otra lista de pasos, que se abre sola la primera vez que se llega a los acordes, al pentagrama o a las reglas. Reglas que importan:
- Un paso con `screen` navega el carrusel; una guía no lleva ninguno y por eso no mueve nada (`Tutorial.navigates`). No agregarle `screen` a una guía.
- La guía se da por vista **al abrirse**, no al terminar: la pantalla se rearma sola por varios motivos y marcándola al final volvía a aparecer sin que se la pudiera sacar de encima.
- `_render()` cierra la guía abierta antes de armar nada. Sus velos están puestos en píxeles sobre la ventana y no sobre `body`, así que sin eso sobreviven al rearmado; por lo mismo el recorrido se redibuja solo cuando la ventana cambia de tamaño (`Tutorial._on_configure`, agrupado con un `after` y sólo si el tamaño cambió). Cerrarlo del todo es `close()`, que desata sus enlaces con `unbind_one`; `_clear()` sólo borra el dibujo entre un paso y otro. No usar `unbind(secuencia, funcid)` sobre la ventana: hasta Python 3.12 borra también el `<Configure>` de customtkinter.
- La dispara cada pantalla al final de armarse, no el carrusel: el blanco de un paso puede ser un widget que la pantalla crea sola.
- «Ver el tutorial otra vez» vacía `guides_seen`. Es la única manera de volver a verlas.
- `uitest` las apaga con `guides_enabled = False`, en memoria.

## Interfaz y nomenclatura

Las claves internas no cambian al renombrar tarjetas visibles:
- `manual` → Organizador
- `random` → Generador
- `harmonise` → Armonizador

`TUTORIAL_STEPS` sigue el orden visible de las tarjetas. Si se mueve una tarjeta, revisar también los pasos del tutorial.

La pantalla inicial va **3 + 3 + 2**: los tres modos arriba; debajo, con su título, las tres herramientas (`TOOL_CARDS`), del mismo tamaño que los modos y cada una debajo de uno; debajo logros y libro, mitad y mitad; y al final, en **un solo renglón**, el cartel del sendero o la llamada a la puerta. Cada tarjeta lleva un dibujo de `homeart.py` (`Card(picture=...)`) y no icono: el de un modo es lo que ponés vos, una flecha y lo que escribe el programa, y lo de la izquierda es distinto en cada uno, que es lo que los distingue sin leer. El título de la pantalla va sin bajada. **Medido contra la ventana mínima (1180×880), entra todo con el cartel del sendero de un renglón y poco más**: un renglón de más en cualquier tarjeta, o el cartel en dos, lo deja afuera. Se probó el cartel en el estante (logros a un cuarto de ancho no entran) y al lado del título (feo).

El dibujo se rehace en el `<Configure>` de su lienzo con el ancho real: el de `wraplength` es el del momento de armar la pantalla, y maximizar después lo dejaba corto.

Las dos tarjetas del estante ---logros y libro--- van con `sticky="nsew"` y la fila con peso: los logros llevan cinco estrellas de cuerpo 26 y el libro no, así que sin eso quedaban de distinto alto.

En la cabecera van tres atajos y en este orden: **libro, logros e historial**. Se empaquetan con `side="right"`, así que en el código están al revés --- el primero que se crea es el que queda más a la derecha. El libro (`self.book_button`) funciona desde cualquier pantalla: se consulta justo cuando aparece una palabra que no se entiende, y eso pasa en cualquier punto del programa.

`MODE_FLAGS` es el cartelito que va **dentro** de la tarjeta, al lado del nombre (`Card(flag=...)`), y vale para los tres modos y para las herramientas: es lo que hay que saber antes de elegir. Hoy lo lleva el analizador.

El límite de compases de la interfaz (`MAX_BARS`) es sólo de UI; el motor/CLI no debe asumir ese límite.

La pantalla de voces muestra los registros de `range_overrides` (por posición en el orden del motor), no los del catálogo: con los del catálogo, volver a la pantalla y apretar «Siguiente» borraba en silencio un atajo (`VOICE_PRESETS`) o un registro tocado a mano. El botón del atajo encendido se decide **comparando lo que está en las casillas** (`_voice_preset_matching`), no recordando el último click.

`_mode_accent` mira **primero** `TOOL_CARDS` y después `MODE_CARDS`: las tres herramientas tiñen la interfaz con su color igual que los tres modos.

El cartel de donación tiene dos maneras y cada una en su recuadro (`_donation_card`): `DONATION_ALIAS` sirve sólo dentro de Argentina y `DONATION_LINK` es la de afuera. Poner sólo el alias dejaba a media humanidad mirando un dato que no puede usar.

## Historia, visitas y huevos

Estos sistemas son funcionalmente secundarios al motor musical. Mantener separados sus estados:
- `story.json`: progreso del sendero.
- `eggs.json`: huevos.
- `visitors.json`: visitas.
- `school.json`: escuelita (ejercicios aprobados y si la graduación se vio).
- `achievements.json`: logros.

Un personaje nuevo va en `cinematic.STAGING`, `SPEAKERS` y `POSES`. `staging_for()` **no falla** si falta: devuelve otra puesta y la escena se dibuja igual, con el cielo y los ruidos de quien no es. Lo vigila `TestVisitors.test_every_visitor_has_a_staging_of_its_own`.

Una visita se marca al terminar la escena, no al decidirla. Una visita normalmente se abre sobre la pantalla que la disparó y no devuelve al home. La visión inicial/pacto es la excepción porque se dispara desde el arranque.

`visitors.AWARDS` dice qué logro deja cada escena. Las dos primeras visiones no dejan ninguno ---no se pueden provocar, y un logro que depende de una tirada de una en cinco no es un logro--- y la tercera sí (`echoes_past`): es el final de lo único que el programa cuenta de punta a punta, y quien la ve es porque vio las tres. Se entrega al terminar la escena, junto con la marca.

Una línea de diálogo puede pedir que la digan más despacio (`story.Line.drag`, que `cinematic` divide sobre la velocidad del personaje y multiplica en las pausas). Es del renglón y no del personaje: la velocidad es actuación, no timbre.

`uitest` debe desactivar estas escenas para que una suite masiva no cambie el estado real.

No agregar huevos al sistema de logros: que sean secretos forma parte de su función.

**El modo profesional** (`settings["professional"]`, apagado de fábrica) apaga visitas, visiones, sendero y las escenas de la graduación. Se corta en lo que **abre** algo y no en lo que anota: los métodos que abren escenas o carteles llevan `@unless_professional`, las pantallas le preguntan al sendero por `_story_awaiting` (nunca `self.story.awaiting` directo) y la graduación se da sin ceremonia. Así lo que el usuario hace se sigue contando y al apagarlo lo que le tocaba lo está esperando. Un enganche nuevo del relato o de las visitas que abra algo tiene que pasar por uno de los dos. Los huevos no entran: son secretos que el usuario provoca, no interrupciones.

La descripción de un logro puede llevar un tramo entre `**` en negrita: `achievements.runs()` la parte en tramos y `plain()` la devuelve sin marcas. La lista de logros dibuja los tramos ---una etiqueta cada uno, en fila y sin envolver, así que la negrita es para señalar una palabra y no un párrafo--- y el aviso y el cartel del legendario usan `plain()`.

Las variables de entorno de depuración/fuerza (`CHORDWEAVER_VISIT`, `CHORDWEAVER_VISION`, `CHORDWEAVER_PACT`, `CHORDWEAVER_TOMB`, `CHORDWEAVER_GRADUATION`, etc.) existen para reproducir escenas difíciles de alcanzar manualmente.

## Analizador

`engine/analysis.py` (motor, puro) + `analyzer.Analyzer` (pantalla, desvío `"analysis"`) + `staff.GrandStaff` (sistema de dos pentagramas).

Reglas que se rompen solas si se las ignora:

- **El compás no es uno solo.** `Score.metres` lleva los cambios ---`(compás, tiempos, figura)`--- y de ahí salen `metre_at`, `metrics_at` y `bar_grid`. Todo lo que mida un tiempo fuerte tiene que preguntar por el compás de **esa** barra: `quarters_per_bar` y `beat_quarters` son sólo el compás de arranque. Forzar la pieza al primero corre la grilla desde el cambio hasta el final.
- **Un compás partido en la repetición son dos mitades de un mismo compás** (`importer._plan_bars`): el 7 de dos tiempos y el 7a de uno suman uno, con el mismo número, y un cambio de compás que llega en la segunda mitad rige desde el siguiente. Estirando cada mitad a un compás entero, seis de ocho corales de Bach quedaban corridos desde la repetición hasta el final.
- La anacrusa es el compás 0 en el análisis (`Score.bar_grid`) y en el sistema (`GrandStaff.pickup`, que el analizador fija al importar). Sin la del sistema, las barras dibujadas quedaban corridas respecto de lo que el análisis decía de cada compás.
- **Se lee un acorde por tiempo, no por vertical.** Cada nota de paso cambia la vertical sin cambiar la armonía; leer vertical por vertical devuelve una progresión de fantasía. Ver `harmonic_segments`.
- **Hay dos pisos.** El de la pieza: con menos de tres voces escritas (`MIN_VOICES_FOR_CHORD`) no hay análisis. Y el del tramo (`_too_thin`): un tiempo con una sola línea, o con dos notas que no recorren tres clases de altura, no abre un acorde propio; se suma al de antes o al de después si cabe entero en él (una nota tenida que las otras voces completan), una racha de tiempos flacos se lee junta (`_thin_run`) y si nada cabe queda sin nombre. Tres notas juntas alcanzan siempre aunque se doblen: no medir el piso en alturas distintas, o el coral que dobla la fundamental se queda sin acordes. Al decidir si un tramo cabe se descuentan las notas con forma de adorno (`_heard(real=True)`).
- **Antes de leer acordes se descuentan las notas con forma de adorno** (`_ornament_shaped` + `Sonority.ornamental`, factor `ORNAMENT_WEIGHT`). Sin ese paso, un si de paso convierte un Do en Do maj7 --- la lectura falsa explica el 100% del material y gana.
- Una nota con forma de adorno **sólo** cuenta como tal si alguna otra voz sostiene. Cuatro voces moviéndose a la vez es un cambio de acorde.
- El descuento por nota floja (`SUPPORT_SHARE`) se aplica **sólo a la séptima**. Se probó con las cuatro notas y convertía un V6/5 en vii°: en una textura arpegiada la fundamental de un acorde invertido suena poco por definición.
- `_same_harmony` (unión de segmentos) exige **mismo bajo**. Sin eso, los seis acordes del bajo cromático descendente se leían como uno.
- **Las paralelas y las quintas ocultas se importan de `engine.fitness`.** No escribir una segunda copia: se desincroniza en el primer cambio y el analizador pasaría a aprobar lo que el generador prohíbe. Lo vigila `TestAnalysisCounterpoint.test_the_rules_come_from_the_evaluator`.
- **El movimiento se mide contra la nota anterior de cada voz, no contra la vertical de al lado** (`_previous_notes`, que devuelve `(nota anterior, cuándo empezó, cuándo empezó la de ahora)`). En un coral las dos cosas coinciden; en una textura arpegiada las voces entran por turno, y mirando la vertical vecina la que todavía no atacó sale «quieta»: las terceras paralelas del bajo y el alto del preludio de Bach se leían «oblicuo» y sus quintas paralelas no las veía nadie. Las paralelas y octavas se buscan sobre **esas mismas** notas, así que se marcan también cuando las dos voces se mueven una tras otra **dentro de un mismo tiempo** (`_beat_of`). En tiempos distintos no son paralelas: la que se movió antes ya está quieta y cada paso es oblicuo (mi-si, mi-la, re-la tiene una cuarta en el medio). Decisión del autor; no volver a la regla vieja.
- **El estilo decide si una paralela es falta** (`analyse(score, genre=...)`, que lee `forbid_parallel_*` de `GENRE_PROFILES`; en la pantalla, `analyzer.STYLES` en la cabecera del panel de contrapunto). Sin estilo se juzga como barroco, que es lo que usa la escuelita.
- Volver a atacar la misma nota **empieza una nota nueva**: repetir es quedarse quieto, y de ahí salen «quieto» y «oblicuo». Un silencio de menos de una negra (`QUIET_ENOUGH`) no corta la voz --- así se escriben los arpegios, con cada nota un pelo más corta que su figura --- y sin ese margen ninguna nota del preludio venía de ningún lado.
- Las dos notas de partida tienen que haber **sonado juntas**. Cuando no se cruzaron, la que viene sosteniendo desde mucho antes ---una pedal, una redonda debajo de un arpegio--- cuenta como quieta y el paso es oblicuo. El mismo paso no se anota dos veces (`registered`), o el paralelo de dos voces largas aparecía una vez por cada corchea de arriba.
- Las cadencias de cita (frigia, Vivaldi, bajo cromático) se leen de `harmony.SET_PIECES`, que es de donde el generador las saca para citarlas. Lo vigila `TestAnalysisCadences.test_the_quotations_come_from_the_generator`.
- El cifrado barroco sale **del acorde** (`baroque_figure` con `reading.tones`), no de una vertical suelta: en una textura arpegiada la primera vertical no es el acorde. Por lo mismo, lo que decide si hay algo que cifrar es **lo que suena en todo el tramo** (`sounding_pcs`) y no la vertical que se dibuja: con una sola clase de altura no se cifra ---un 6 suelto encima de una nota sola es una cifra que no existe--- pero midiendo la vertical media pieza arpegiada se quedaba sin cifrar.
- El accidente de una cifra es el que se **escribe**, no la diferencia con la armadura (`_alteration` devuelve la alteración escrita o nada, y `_sign` elige el signo). En una armadura de bemoles una nota natural está subida respecto de la armadura y se cifra igual con becuadro: leyendo el preludio con cuatro bemoles salía todo con sostenidos.
- Sólo se deduplican los hallazgos de vertical (`PER_SONORITY_KINDS`). Cinco quintas paralelas seguidas son cinco faltas.
- La tercera y la quinta **se dan por sabidas** en el cifrado: cuando la combinación exacta no está en `FIGURE_ABBREVIATIONS` se reintenta sin ellas antes de apilar números, o una séptima sin quinta salía cifrada `7/3`. Y el estado fundamental no lleva número: `(3,)` y `(5,)` cifran vacío.
- Todo adorno que aparezca en `ORNAMENT_LABELS` tiene que estar en `ORNAMENT_DEFINITIONS`.
- **La armadura se deduce cuando el archivo no la trae** (`implied_fifths`), y de ella sale **cómo se escribe cada nota**: los tres modos que generan exportan en Do con los accidentes puestos a mano, así que una armonización en Fa leída con la armadura escrita salía llena de sostenidos. La deducida decide la escritura y el desempate de `SIGNATURE_FIT`; la **escrita** sigue armando los candidatos de tonalidad --- usándola también para eso, dos préstamos del menor mudaban la pieza a otro modo.
- Un acorde que se llama `bVI` se escribe con bemol y uno que se llama `#iv` con sostenido (`_spell_like_its_degree`), y el bajo de una inversión se escribe **por su papel en el acorde** (`ChordReading.bass_name`): la quinta de un Si7 es fa sostenido aunque la pieza vaya en bemoles.
- Un acorde disminuido **no puede ser la tónica**: no recibe el premio del acorde final. Sin eso, una armonización que se detenía en el vii° se analizaba entera en locrio.
- El cifrado suma la nota que suena y no es del acorde (`figured_extras`), pero **sólo una y sólo la de la vertical con la que el acorde entra**: con dos o más lo que falla es la lectura del acorde, y cifrarlas todas devolvía cifras de cuatro números.

Del lado de la pantalla:

- **El sistema lleva siempre cuatro carriles.** Dos claves reparten cuatro voces y ése es el reparto del coral; cuántas están escritas se cuenta mirando (`GrandStaff.written_voices`), y `Analyzer.score()` deja afuera los carriles vacíos. `_lanes` guarda la correspondencia entre las voces del análisis y los carriles: sin ella las flechas del contrapunto señalan la voz de al lado.
- **Un click dentro de una nota la parte en tres** (`_write`): lo que sobra antes, la nota nueva y lo que sobra después, las dos puntas con la altura que tenía. Reemplazando la nota entera, escribir una corchea de paso encima de una redonda dejaba a esa voz muda el resto del compás y la corchea pasaba a ser un acorde ella sola.
- El momento se redondea **contra el comienzo de su compás** (`_snap`) y una nota no puede cruzar la barra. Redondeando contra el cero de la pieza, un cambio de compás dejaba todo a contratiempo de sus propias barras. Y se redondea contra el **centro** de cada lugar, no contra su comienzo: la nota se dibuja en el medio del tramo que ocupa, así que apuntándole a la cabeza se apuntaba media figura más allá y la nota nueva caía en el lugar siguiente.
- La altura se lee con la clave **del pentagrama donde se hizo el click** (`_clef_at`) y se recorta a lo que esa voz alcanza (`writable_range`). Los dos pentagramas no son una escalera continua: una altura leída con la del sol y dibujada con la del fa cae a cinco líneas del cursor.
- Botón derecho borra ---dejando un silencio de la misma duración, para no correr la voz---, `Ctrl+Z` deshace sobre una pila de estados y `Tab` cambia de voz. Leer una nota es **pasarle el mouse por encima** (`on_hover`), no tocarla: el click escribe. El deshacer viejo sacaba la última nota de la voz activa, que no es lo mismo.
- Cada voz descansa en **su propio renglón** y con su color: con todas en la misma línea, el silencio de una voz se dibujaba encima de la nota de la otra.
- Los rótulos van sobre la **cabeza de la nota** (`_onset_x`) y no sobre el borde izquierdo del tramo: la nota se dibuja en su centro, así que con una redonda el cifrado quedaba sesenta píxeles a la izquierda de lo que describe.
- Un movimiento se dibuja como **una sola marca entre las dos voces del par** (`GrandStaff.motions`): el trazo las une y cada una lleva su flecha. Con una flecha por voz de la nota que deja a la que toma, se leía como una voz moviéndose consigo misma.
- Elegir un acorde de la lista **no rearma la lista** (`_select`): cambia el fondo de dos renglones y mueve el de cómo sigue (`_show_relation`). Lo que lleve sólo el acorde elegido va ahí; rearmándola entera, cada click costaba medio segundo con un coral.
- `analysis.read_chord` recuerda lo que ya leyó y devuelve **copias**: quien llama les cambia `prefer_flats`. Devolviendo las guardadas, eso cambiaba la escritura de otro tiempo con las mismas notas.
- `Analyzer._lanes` se rehace **después** de analizar, por nombre: `analyse()` reordena las voces por registro y la correspondencia hecha antes señalaba la voz de al lado.
- Los silencios, como todos los signos, salen de la fuente musical propia (ver «Pentagrama: la fuente musical») y **nunca** de los caracteres musicales de Unicode en una fuente de sistema: no están en todas y el de negra salía como un rectángulo vacío.
- Debajo del sistema va el cifrado del bajo **en columna** (`FIGURE_ROWS`, tres renglones) y el grado no va: escritos los dos al lado del cifrado americano no se leía ninguno.
- El sistema usa su propia escala (`GRAND_LINE_GAP`, `GRAND_STEP`) y no la del pentagrama de una línea: acá hay dos pentagramas, el hueco, y arriba y abajo los rótulos, y todo eso comparte la ventana con los tres paneles. `GRAND_TOP_MARGIN` tiene que dejar entrar la nota más aguda --- con el margen viejo, una nota sobre la quinta línea se dibujaba encima del cifrado y una bien aguda se dibujaba fuera del lienzo.
- El alto del lienzo se recalcula en cada dibujo contra la nota más grave; el margen de arriba es fijo porque de él salen las cuentas del click.
- **El sistema tiene que poder escribir silencios.** Sin ellos, una voz que entra tarde queda pegada al principio y las voces salen corridas entre sí: lo que se analiza deja de ser lo que dice la partitura. `importer.written_line()` es lo que convierte una voz leída en una voz escribible.
- `staff.index_for_pitch()` + `staff.accidental_for()` + `staff.pitch_at()` forman un ida y vuelta **exacto** en toda armadura. Es lo que permite importar, escribir en el pentagrama y analizar sin que cambie una nota. Lo vigila `TestAnalysisWriting`.
- El sistema **no** es una escalera continua: cada clave tiene su propia geometría (`_y_for(index, treble)`) y la voz decide en cuál se escribe (`staff_of`, mitad grave al fa). Se probó con la escalera corrida entera --- que es lo exacto --- y los dos pentagramas se leen como una sola grilla de diez líneas.
- **El tenor (`GrandStaff.SPLIT_VOICE`) se reparte nota por nota**: del do central (`MIDDLE_C`) para arriba se escribe en la clave de sol y para abajo en la de fa, que es lo que hace falta para escribir piano. Por eso `staff_of` recibe la altura y hay que preguntarle **por cada nota** --- dibujo, blanco del mouse, marca de la voz activa y cifrado ---; sin la altura contesta el pentagrama de siempre.
- El editor llega hasta **cuatro voces**. Una partitura con más se reduce **momento a momento** (`importer.kept_voices`): la nota más grave, la más aguda y las dos del medio que más clases de altura agregan, y se avisa. Quedándose con las cuatro líneas más graves, una partitura de piano perdía la melodía.
- Se reanaliza solo, con espera (`REANALYSE_MS`); el hilo del sonido no toca Tk (`_watch_sound`, igual que `_when_done`).

Exportación: `session.export_analysis()` --- **un hueco por compás** y una línea escrita por voz (`ScoreSpec.voice_lines`, `line_for`), no un hueco por sonoridad: cortando en cada vertical, una redonda del bajo salía partida en semicorcheas ligadas. Cada voz se escribe con sus propias figuras (`_writable_pieces`, con ligaduras), la armadura decide cómo se escribe cada nota (`spell_by_key` → `theory.spell_in_key`), `pickup` marca el primer compás incompleto y `bar_time_signatures` los cambios de compás. Una nota que cruza la barra viaja como `(altura, duración, True)` (`session._written_bar`) y el exportador la liga en MusicXML y la sostiene en MIDI; sin la marca, una síncopa volvía reatacada. **No** anota en el historial: un análisis no es una corrida del motor.

El botón «Analizar» de cada opción del resultado la manda sin archivo (`_analyse_option` → desvío `"analysis"` con la pieza de carga → `Analyzer.load_piece`), juzgada con el `genre_key` del pedido. Las voces salen de `session.analysis_lines`, que copia paso a paso a `export.build_musicxml`: un cambio en cómo se escribe una opción va en los dos lados, o el analizador juzga otra pieza que la que se exporta. Lo vigila `TestSendToAnalyser`.

`assets/partituras/` trae el Preludio BWV 846 (ocho compases) para que haya algo que importar el primer día; `Analyzer.examples_directory()` es lo que abre ahí el diálogo. Lo vigila `TestAnalysisExample`, y `TestAnalysisReadsWhatWeWrite` comprueba que lo que exportan los tres modos vuelva a entrar por acá.

## Pentagrama: la fuente musical

`staff.py` dibuja con Bravura (SMuFL, SIL OFL 1.1) a través de `staff.Engraver`, y con trazos si la fuente no está. Lo vigila `TestMusicFontStaff`.

- Vive en `assets/fonts/Bravura.otf` (con `OFL.txt`) y se resuelve con `program_directory()`. Se carga **en privado y una vez** (`load_music_font`: `AddFontResourceExW` + `FR_PRIVATE`). Con una ruta de más de 259 caracteres Windows la rechaza: se carga una copia de `%TEMP%/ChordWeaver-fonts/`. Si igual falla, o fuera de Windows, `Engraver.engraved` es False y todo sale por trazos; ningún camino puede levantar una excepción.
- **Calibración:** en SMuFL un cuerpo son cuatro espacios, así que la fuente se pide a `-(4 × espacio)` (negativo = píxeles en Tk) y la cabeza cae justa entre dos líneas. Tk no ancla un texto en su línea de base: cada signo se ancla `nw` en `y - ascenso` (`Engraver.glyph`). Los anchos (`WIDTHS`) y anclas salen de `Bravura.json`.
- Se pasa como descripción `("Bravura", -px)`, nunca como `tkfont.Font` (se borra solo desde `__del__`, en cualquier hilo). `music_font` comprueba que Tk encontró **esa** familia: si no, Windows contesta Arial sin quejarse.
- Las notas empiezan en `left_margin()` ---clave + armadura + compás medidos---, no en `LEFT_MARGIN`/`GRAND_LEFT_MARGIN`, que son sólo el mínimo. Dibujo y click leen el mismo valor; usar la constante corre los clicks.
- `GrandStaff.redraw` rehace sólo lo de encima (capas con `OVERLAY_TAG`) si `_score_signature` no cambió, y `StaffEditor.redraw` no redibuja si `_signature` no cambió. Lo nuevo que dependa de las notas va en la firma; lo nuevo dibujado encima, en una capa con su marca. Si no, queda viejo en pantalla. Mover el resaltado bajó de ~15 a ~3 ms.
- El accidente que se **dibuja** sigue la regla del compás (`displayed_accidentals`; en el sistema, por pentagrama): un sol después de un sol sostenido lleva becuadro aunque no tenga accidente propio. Lo que **suena** es la altura de cada nota, que no cambia.
- Colores de la melodía del Armonizador, un canal por pregunta (`note_look`): **naranja = fuera de la escala**, **halo dorado = lleva acorde** (la de la escala con acorde, además, dorada), anillo = la marcó el usuario. La leyenda la dibuja `legend_swatch` con la misma función. No codificar «lleva acorde» sólo con un color: naranja y dorado tienen que poder estar en la misma nota.

## Escuelita

`engine/school.py` (lecciones, corrección, `Progress`, guion de la graduación; puro) + `school.School` (pantalla, desvío `"school"`). Ocho unidades en orden ---lectura, ritmo, oído, movimientos, armonías, cadencias, estilos, serie armónica---. **El orden es una recomendación, no una cerradura**: el recorrido de arriba abre cualquier lección (`_trail_click`, a pedido del autor) y «Siguiente» pasa a la lección que sigue aunque falte algo atrás. El recorrido dibuja **dos estados**, aprobada entera o pendiente, y todas las pendientes iguales: con un tercero («abierta», pintada con el color) aprobar un ejercicio adelante encendía todas las de atrás y no se sabía cuáles faltaban. `Progress._reached` sólo decide dónde se retoma (`current`), porque las tres primeras unidades se agregaron adelante.

- **El juez es el analizador.** Los ejercicios de escritura se le pasan enteros a `analysis.analyse`; las reglas de estilo salen de `GENRE_PROFILES` y se detectan con las funciones de `fitness`/`style`; la serie armónica, de `engine/harmonics`. No escribir una corrección propia: aprobaría lo que el analizador marca en rojo.
- **La tonalidad la pone la consigna** (`school.read`): el analizador lee los acordes y el contrapunto como siempre, y la función y la cadencia se vuelven a pedir con la tonalidad del ejercicio. Sola, una frase de cuatro acordes que termina en una rota se lee en la tonalidad del sexto grado.
- Cada ejercicio trae `solution` y `mistake`, que no ve nadie: `TestSchool` exige que la primera apruebe, que la segunda falle **diciendo el compás**, y que el fragmento de partida no esté ya resuelto. Cambiar un fragmento obliga a revisar los tres.
- Una respuesta elegida mal **no dice cuál era la buena** (`_wrong_choice`, `HINTS`): dice qué tiene de malo la elegida y dónde mirar. Diciéndola, el segundo intento era copiar.
- Cada lección cita una entrada del libro (`cite`, `quote`); `book.find` la ubica y `_screen_book(payload=clave)` abre el libro ahí. Si la entrada está cerrada se muestra la pista y no el texto: casi siempre la abre el ejercicio de esa lección, porque lo que el alumno **entrega** pasa por `_analysed` y gana los logros que gana en el analizador. El fragmento de partida no pasa nunca por ahí.
- Lo dado no se toca: el pentagrama no sabe de voces fijas, así que `School._guard` deshace en el próximo respiro (`after_idle`, nunca adentro del aviso de cambio) lo que cambie una casilla de `school.locked()`.
- Las palabras sueltas que llegan a `tr()` desde una variable ---movimientos, cadencias--- están marcadas en `school.GLOSSARY` con `N()`: sin acento la cosecha del catálogo no las ve. Los nombres de las voces salen de `theory.VOICE_CATALOG` (`school.VOICE_NAMES`) y se traducen en `en_engine`.
- La graduación son tres escenas encoladas juntas (Gregorio, Bach, el creador; nunca los del sendero, que cada usuario conoce uno). Se marca y entrega `legend_born` en `_graduated`, al terminar la **última**. Bach dice «Cincuenta y tres ejercicios»: lo vigila un test.
- Lectura, ritmo y oído no pasan por el analizador: nombrar una nota o medir una figura no es analizar. Las reglas de elegir están en `READING_RULES` (`_reading_answer`, `_wrong_reading`) y las de escribir son `notes`, `rhythm` y `fill`. Cómo se escribe cada nota (`spelled`) es la cuenta de `staff.index_for_pitch` corrida una octava, y qué signo se dibuja (`written_signs`) es la de `staff.displayed_accidentals`: `engine/` no puede importar `staff`, y dos tests comparan las dos copias en todas las armaduras. Una respuesta que es una nota o un compás se muestra con `option_label` y no con `tr(label)`: un nombre de nota no se traduce, se dice con `i18n.note_name`.
- Un ejercicio con `lines` va voz por voz y con duraciones (`Exercise.by_lines`), y manda sobre `chords`. Lo dado son sus **notas**: `tampered` exige que cada una siga entera, así que escribir dentro de una nota dada ---que la parte en tres--- se deshace igual que cambiarla, y los silencios dados son lo que se puede llenar. Sus respuestas modelo van en `solution_lines` y `mistake_lines`; los tests las piden con `model_lines`.
- Figuras, signos y dictado aparecen sólo en los ejercicios que los piden (`durations`, `accidentals`, `dictation` en `params`), en un renglón aparte de los mandos. El pentagrama de la escuelita se aprieta más que el del analizador (`GrandStaff.quarter_floor`), y aun así un ejercicio con corcheas va en tres compases: cuatro no entran al lado de la lección en la ventana mínima.
- La práctica libre (`practice_exercise`, `PRACTICE_KEY`) no es un ejercicio del curso: no está en `exercises()`, `mark_passed` la ignora y lo único que guarda es `practice_best` en `school.json`.

## Experimentador de armónicos

`spectrum.Experimenter` --- pantalla propia (desvío `"lab"`, tarjeta al lado de la de logros) --- sobre `engine/harmonics.py`.

- El gráfico y el sintetizador leen **la misma** lista: `harmonics.sounding()`. Cualquier regla nueva sobre qué suena va ahí y en ningún otro lado, o el dibujo deja de coincidir con lo que se escucha.
- El hilo del sonido no toca Tk. El botón se devuelve preguntando desde el hilo principal (`_watch_sound`), igual que `_when_done` en `app.py`.
- `play()` sintetiza sobre una **copia** del espectro: el usuario puede mover un deslizador mientras suena.
- Los párrafos del panel no llevan `wraplength` fijo: un `wraplength` es un ancho **pedido**, y una descripción larga estiraba el panel --- y con él el gráfico, corriendo todas las barras debajo del mouse. Los registra `_wrapping` y los mide `_redraw` contra el lienzo. **No atarlos a su propio `<Configure>`**: cambiar el `wraplength` cambia el alto, el alto reacomoda el panel, y eso dispara otro `<Configure>` --- la ventana se cuelga.
- El arrastre sobre una barra fija un eje (`AXIS_LOCK`) y se queda con él hasta soltar: mover el mouse en línea recta es imposible, así que sin eso un arrastre horizontal siempre cambiaba la amplitud de paso.
- La cuenta que trae al creador avanza sólo con configuraciones distintas (`_signature`). Apretar «Escuchar» tres veces sin mover nada es un experimento, no tres.
- `write_instrument()` guarda el timbre como **muestra de sampler**: un WAV con el trozo `smpl`, que es lo que dice qué nota representa y qué tramo se repite. Para que el bucle no chasque, cada componente se acomoda al múltiplo más cercano de `1/duración del bucle` y el vibrato se escribe como **modulación de fase**: estirando la frecuencia, la fase acumulada al terminar la vuelta no es la de la salida. El desvío que introduce ese acomodamiento es de centésimas de cent. Lo vigila `TestInstrumentSample`.
- Los números del capítulo de física del libro (110 Hz y sus múltiplos, −13,7 cents del quinto, −31,2 del séptimo) están escritos a mano en `book.py` --- ese módulo no importa nada del proyecto --- y los vigila `TestPhysicsChapter`.
- El capítulo de armonización afirma el orden de preferencias de `harmonize.ROLE_COST`. Cambiar esos pesos obliga a revisar el capítulo: `TestHarmonisingChapter` falla si dejan de coincidir.

## Aviso de version nueva

`engine/updates.py` (la consulta, pura) + `updater.py` (el cartel). `main()` en
`app.py` los llama en ese orden.

- **El cartel sale ANTES de construir `ChordWeaverApp`, y en su propia raiz de
  Tk.** No es estetica: armar la aplicacion deja timers puestos ---tutorial de
  la primera vez, vision del arranque, visitas--- y cualquier bucle de eventos
  posterior los dispara. Con la ventana ya construida y tapada, el usuario se
  encuentra una cinematica empezada y un velo de tutorial detras del cartel.
  Por eso `updater.greet()` **no recibe la aplicacion**: contesta si hay que
  crearla. No convertirlo en un `CTkToplevel` sobre la ventana ya abierta.
- **Al compilar para publicar hay que dejarlo prendido y comprobarlo.**
  `updates.enabled()` pregunta solo cuando `sys.frozen`, asi que desde el
  fuente no aparece nunca ---que es lo que se quiere mientras se desarrolla---
  y en el `.exe` si. Antes de subir una version: `pyinstaller ChordWeaver.spec`
  y abrir el ejecutable con `version.json` ya publicado, para ver el cartel una
  vez de verdad. Para probarlo sin compilar: `CHORDWEAVER_UPDATE_CHECK=1`, y
  `CHORDWEAVER_UPDATE_FEED=file:///...` para apuntarlo a un archivo puesto a
  mano.
- La version publicada sale de `https://chordweaver.github.io/version.json`, no
  de la API de GitHub: no tiene limite de pedidos por hora y lo controla quien
  publica, asi que una release puede existir sin estar anunciada todavia. **El
  aviso no sale hasta que ese archivo se toca**, y es el ultimo paso del
  release --- tocarlo antes manda a todos a un enlace roto.
- La consulta corre en un hilo demonio y arranca antes que la ventana; la
  respuesta se espera con presupuesto (`updates.answer`). Sin red, con un
  proxy, con el archivo a medio publicar o con la pagina caida, todo termina en
  `None` y el programa abre sin decir nada y sin esperar. Ninguna de las dos
  funciones publicas levanta excepciones: `greet()` devuelve `True` ---abrir
  igual--- ante cualquier problema.
- `notice()` cancela los `after` pendientes antes de destruir su ventana y
  despues llama a `_hand_back_the_scaling_loop()`. Lo primero evita que Tcl
  escriba errores de una ventana que ya no esta; lo segundo devuelve la bandera
  del vigilante de escala de customtkinter, que es una sola para todas las
  ventanas: cerrando la unica que hay queda arriba sin nadie que la corra, y la
  ventana de la aplicacion ---que se abre despues--- no lo reanuda.
- `updates.py` vive en `engine/` y no importa nada de la interfaz; `updater.py`
  no importa `app` y recibe la paleta por parametro, igual que `spectrum` y
  `analyzer`. Los dos estan en los `hiddenimports` de `ChordWeaver.spec`.
- El parametro `on_ready` de `notice()` es el enganche del arnes de pruebas: no
  puede dispararse en `after(0)` porque `CTk.mainloop` llama a `update()` antes
  de entrar al bucle, y el cartel se destruiria abajo de sus propios pies.
- Los dos carteles del arranque se cierran con `updater.dismiss`: esconder, cancelar los `after` pendientes y después `quit()` y `destroy()`, cada uno en su `try`, y al salir del bucle se destruye igual (`finally`). Los `after` se cancelan con el `after cancel` de Tcl y **no** con `after_cancel`: ése borra el comando desde la ventana aunque lo haya registrado el botón apretado, el botón lo sigue anotando, `destroy()` falla con «can't delete Tcl command» y el cartel queda vivo al lado del programa. Y como `quit()` es uno solo para todo el proceso, cerrarlo con la cruz cerraba el programa. Y `main()` llama `bring_to_front` al abrir la ventana del programa: es la segunda del proceso, y Windows le daba el foco a otra cosa al cerrarse la primera, así que aparecía detrás de todo o minimizada y parecía que el programa se había cerrado al apretar «Ahora no».

## Los dos idiomas

`engine/i18n.py` (el motor, puro) + `engine/lang/` (los catálogos) +
`chooser.py` (el cartel de la primera vez). El original está en castellano y
**el castellano es la clave**: cada cadena se busca tal cual está escrita en
el código y, si no está en el catálogo, se devuelve igual. Una pantalla
nueva sin traducir sale en castellano, no vacía.

- **La traducción ocurre al dibujar, no al importar.** Las tablas de prosa
  ---`MODE_CARDS`, `TUTORIAL_STEPS`, el libro, el guion--- siguen guardando
  el castellano; quien lo convierte es el `tr()` del lugar donde el texto
  entra a un widget. Es lo que permite cambiar de idioma sin reabrir el
  programa: alcanza con volver a dibujar.
- `tr(texto)` traduce, `trf(plantilla, hueco=…)` traduce y rellena, `trs()`
  traduce una lista y `N()` **marca sin traducir** --- es para la prosa que
  vive en una constante de módulo y se traduce lejos.
- **Los huecos van con nombre** (`{compás}`) y nunca por posición: traducir
  es reordenar. `TestLanguages` falla si un hueco se pierde o se inventa.
- **Un desplegable se muestra traducido y se lee en castellano**: se arma
  con `trs(...)` y se lee con `i18n.untr(menu.get())`. Así ninguna de las
  comparaciones del programa ---que están escritas contra el castellano---
  cambia. Traducir un menú sin poner el `untr()` del otro lado rompe en
  silencio: la comparación deja de dar y no falla nada.
- **No traducir a mitad de frase.** Pegar `«va»`/`«van»` o `«voz»`/`«voces»`
  con un hueco es una concordancia del castellano y no existe como pedazo en
  ningún otro idioma: van las dos frases enteras. Lo mismo con cualquier
  renglón armado con `+` o `join`: se traducen los pedazos y se pega después,
  nunca al revés --- `tr()` sobre la frase ya armada no acierta nunca, porque
  la clave llevaría el dato adentro.
- `_switch_language` destruye y rearma **los cuatro marcos** de
  `_build_chrome` además de `_render()`: la cabecera y el pie se arman una
  sola vez y no pasan por el render.
- El cartel del idioma sale **antes** que el de versión nueva y antes de
  construir `ChordWeaverApp`, por lo mismo que aquél (ver más abajo) y para
  que el de versión nueva salga ya en el idioma elegido. Está escrito en los
  dos idiomas a la vez y **no** pasa por `tr()`: se dibuja cuando todavía no
  hay ninguno elegido.
- `DEFAULT_SETTINGS["language"]` arranca **vacío**, no en `"es"`: vacío es
  «no lo eligió nadie todavía», que es lo que hace que se pregunte una sola
  vez en la vida de la instalación.
- Los nombres de voz de `theory.VOICE_CATALOG` están en castellano (son la clave). Se muestran y se exportan con `i18n.tr_name`, que traduce «Bajo 2» como nombre más número y entiende los nombres en inglés que guardaba el historial viejo.
- Los nombres de nota los decide el idioma (`i18n.note_name`, `say_letter`):
  solfeo en castellano, letras en inglés. `analysis.spanish_note` y
  `analyzer.spanish_pitch` bajan ahí.
- `uitest` clava el idioma en el original: lo que el arnés lee son los
  rótulos de la ventana viva, y una corrida en inglés fallaría entera sin que
  nada esté mal.

Mantenimiento:

```bash
python -m engine.lang.audit            # qué falta y qué sobra
python -m engine.lang.audit --missing  # las que faltan, listas para pegar
```

**Las claves no se copian a mano**: varias se arman pegando renglones y un
espacio de más deja la entrada muerta sin que se note. Las saca el audit
leyendo el árbol de sintaxis, y `TestLanguages.test_the_catalogue_has_no_holes`
falla cuando se agrega una pantalla sin traducir.

## Audio

El audio se sintetiza en `engine/ambience.py`, sin archivos ni librerías externas.

Restricciones que importan para mantenimiento:
- mantener 44100 Hz;
- normalizar por loudness/percepción, no sólo por pico;
- aplicar reverb antes de `_seamless` cuando el sonido es en bucle;
- extender buffers para que la cola de reverb no se corte;
- no cerrar/cortar bruscamente sonidos que aún tienen cola;
- los loops necesitan `tail=0` al cerrar/encadenar si el principio y final son el mismo punto;
- la cama de ambiente debe mantenerse por debajo de las voces.

No hace falta documentar aquí la receta acústica concreta de cada sonido salvo que una implementación posterior rompa un contrato de mezcla.

### Timbres de reproducción

Toda nota musical que el programa toca ---resultados, melodía, historial, analizador, sendero--- pasa por `audio.render_chords` → `timbre.mix`. Un sonido nuevo de la pieza no se sintetiza en otro lado: así lo alcanza el timbre elegido en el engranaje (`settings["timbre"]`, `settings["timbre_path"]`). Quedan afuera a propósito `ambience` (la habitación, no la pieza) y `harmonics.play` (ahí el timbre es el experimento).

- `timbre.SAMPLE_RATE` es la fuente y `audio` lo reexporta: `audio` importa `timbre`, al revés sería circular.
- El volumen de cada timbre se **mide** (LUFS con compuerta, `timbre.loudness`) contra la cuerda pulsada, que vale 1 por definición; no se anota a mano. Retocar una receta no obliga a recalibrar nada. `audio.encode` baja la pieza entera si pasa del techo, nunca recorta.
- `timbre.use()` que falla deja el timbre **de siempre**, no el anterior. Al arrancar, un WAV que ya no está no cambia la preferencia guardada: suena el de siempre y el engranaje dice por qué.
- En el trozo `smpl` el final del bucle es **inclusivo** (lo escribe así `harmonics.write_instrument` y lo lee así `timbre.read_sample`).
- `play_chords` lee el timbre en el hilo que llama: el hilo del sonido no consulta preferencias.

## Archivos sensibles

Revisar especialmente antes de cambios estructurales:

- `engine/theory.py`: base de representación/parser.
- `engine/fitness.py`, `engine/style.py`: cambiar un peso cambia silenciosamente toda la música.
- `engine/fitness.pxd`, `engine/style.pxd`: firmas Cython.
- `engine/ga.py`: reproducibilidad, siembra y evaluación.
- `engine/harmonize.py`: planificación de spots/duración. Sus pesos los cita el capítulo VII del libro.
- `engine/session.py`: alineación de slots, persistencia y fachada.
- `engine/history.py`: rutas/lista blanca de settings.
- `ChordWeaver.spec`: empaquetado.
- `app.py`: threading/Tk, persistencia de UI y estado global.
- `uitest.py`: aislamiento de datos, idioma y tutorial/visitas.
- `engine/lang/`: los catálogos. Las claves son castellano exacto.

## Regla final

Antes de tocar algo de lógica musical: leer `MUSIC_LOGIC.md`.

Antes de tocar Cython: comprobar si hay `.pyd`.

Antes de tocar tests/UI: asegurar aislamiento mediante `uitest.Session` o rutas de datos descartables.

Antes de agregar una preferencia persistente: agregarla a `DEFAULT_SETTINGS`.

Antes de agregar un módulo al build: revisar `ChordWeaver.spec`.

Antes de agregar texto visible: envolverlo con `tr()` y correr `python -m engine.lang.audit`.

No introducir documentación aquí para hechos que el código ya hace obvios.
