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
- audio: `engine/audio.py`
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
- aviso de version nueva: `engine/updates.py` (consulta) + `updater.py` (cartel)

`staff.py`, `spectrum.py`, `analyzer.py` y `updater.py` no importan `app.py`: reciben la paleta por parámetro (`colours=...`). No agregarles un import de la aplicación.

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
- Los adornos se manejan aparte de los acordes porque tienen duraciones parciales y voces individuales. La duración total del compás debe seguir sumando lo mismo.
- `flourish.py` corre después de la búsqueda, sobre el ganador; no meterlo en el fitness salvo que se rediseñe explícitamente la función objetivo.
- En armonización, la partitura exportada usa la línea real del usuario (`MelodyLine`), no la versión muestreada que vio el AG.

## Armonización / slots

- La armonización coloca acordes en los tiempos fuertes y puede abrir nuevos lugares para última nota, sensible o nota marcada.
- `spot_for_note()` debe conservar la suma exacta de duración del compás: si no hay lugar suficiente para crear un nuevo slot, el sobrante vuelve al slot anterior.
- Una nota marcada lleva `MelodyNote.must_harmonise` y `required_note`; no permitir que el selector la ignore.
- La sensible final puede forzar dominante mediante `harmonize.pin_leading_tone`.
- No crear acordes después de que terminó la melodía: los tiempos sobrantes del último compás pertenecen al último segmento que realmente ocupa la melodía.

## Silencios, reproducción y adornos

- Los silencios no entran al AG, pero sí deben conservarse al mapear a la partitura/reproducción.
- `build_settings` puede usar un pitch de relleno para mantener la alineación interna; visualmente manda `is_rest`, nunca ese pitch.
- Los adornos vacían el slot de acorde durante su duración y se reproducen como voces parciales con tiempos propios.
- Los adornos se indexan por slot de búsqueda, por lo que cualquier acceso contra `spec.slots` debe reubicar primero con la misma lógica que `voiced_slots`.

## Cython: filo importante

Si existen `engine/*.pyd`, el `.pyd` gana al `.py` en importación.

**Después de modificar `engine/theory.py`, `engine/fitness.py` o `engine/style.py`, recompilar o limpiar:**
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

Los assets del programa deben resolverse desde `program_directory()`. En modo congelado los assets de PyInstaller están bajo `_internal/`; `base_directory()` es para datos del usuario y no debe usarse para localizar `assets/`.

## Persistencia

Los datos de usuario incluyen:
- `history.json`
- `achievements.json`
- `story.json`
- `eggs.json`
- `visitors.json`
- preferencias/settings
- `output/`

`DEFAULT_SETTINGS` es una **lista blanca**: si se agrega una preferencia nueva y no se suma allí, se guarda y luego desaparece al recargar.

`engine.__version__` es la única fuente de versión de la app, y es contra lo que compara el aviso de versión nueva.

`CHORDWEAVER_DATA_DIR` redirige todos los datos del usuario y `output/`. No repartir rutas manualmente.

### Tests / UI tests

`tests.py` también puede escribir historial porque algunas rutas llaman `export_outcome`. Por eso la suite debe ejecutarse con aislamiento de datos.

`uitest.Session` debe usarse para tests de GUI: redirige historial, logros, historia, huevos, visitas y preferencias a descartables. No abrir `ChordWeaverApp` directamente desde un script de test que pueda persistir datos.

Las preferencias pueden leerse del archivo real para probar una configuración real, pero las escrituras del test deben ir al archivo descartable.

## UI / Tk

- Tk no es thread-safe.
- Ningún worker toca widgets.
- El worker tampoco debe llamar métodos de Tk indirectamente.
- `Ctrl+Z` debe activar el mismo botón/acción de deshacer que la UI (`invoke`), no duplicar la lógica llamando directamente a `staff.undo`.
- `bind_deeply()` debe evitar duplicar eventos de `customtkinter`: varios widgets CTk envuelven canvas/labels internos.
- `CTkFrame` puede dibujar fondos incluso con apariencia transparente; no crear cientos de frames CTk para contenido plano si basta un `tk.Frame`/`tk.Label`.
- **Un `CTkFrame` sin hijos mide 200×200.** No dejar uno vacío dentro de una franja de un renglón: la franja de la tonalidad del analizador pasaba a medir cuatro veces lo suyo cuando la pieza no tenía cadencias ni acordes ajenos que poner en él.
- Las filas masivas de listas (p. ej. logros) usan widgets Tk simples por rendimiento.
- `_render()` desmonta temporalmente `self.body` mientras reconstruye la pantalla para evitar repaints parciales.
- Animar preferentemente color y coordenadas de widgets `place`-ados; evitar animar geometría de layouts empaquetados.
- `ACCENT` y `ACCENT_HOVER` son variables: `_apply_accent()` las cambia según el modo. Elementos creados una sola vez pueden necesitar actualización manual.
- El tutorial se inicia sólo la primera vez; `uitest` debe desactivarlo en memoria, no persistiendo ese cambio en los datos reales.

Además del recorrido de bienvenida hay **guías de pantalla** (`SCREEN_GUIDES`): la misma clase `Tutorial` con otra lista de pasos, que se abre sola la primera vez que se llega a los acordes, al pentagrama o a las reglas. Reglas que importan:
- Un paso con `screen` navega el carrusel; una guía no lleva ninguno y por eso no mueve nada (`Tutorial.navigates`). No agregarle `screen` a una guía.
- La guía se da por vista **al abrirse**, no al terminar: la pantalla se rearma sola por varios motivos y marcándola al final volvía a aparecer sin que se la pudiera sacar de encima.
- `_render()` cierra la guía abierta antes de armar nada. Sus velos están puestos sobre la ventana y no sobre `body`, así que sin eso sobreviven al rearmado.
- La dispara cada pantalla al final de armarse, no el carrusel: el blanco de un paso puede ser un widget que la pantalla crea sola.
- «Ver el tutorial otra vez» vacía `guides_seen`. Es la única manera de volver a verlas.
- `uitest` las apaga con `guides_enabled = False`, en memoria.

## Interfaz y nomenclatura

Las claves internas no cambian al renombrar tarjetas visibles:
- `manual` → Organizador
- `random` → Generador
- `harmonise` → Armonizador

`TUTORIAL_STEPS` sigue el orden visible de las tarjetas. Si se mueve una tarjeta, revisar también los pasos del tutorial.

La pantalla inicial va **3 + 2 + 2**: los tres modos arriba; debajo las dos herramientas (`TOOL_CARDS`: experimentador y analizador) tan anchas entre las dos como las tres de arriba; debajo logros y libro, mitad y mitad; y al final el cartel del sendero. Las dos herramientas usan la misma clase `Card` que los modos pero con dos viñetas en vez de tres pasos: quedan en cuatro quintos del alto, que es lo que hace que el cartel del sendero siga entrando.

Las dos tarjetas del estante ---logros y libro--- van con `sticky="nsew"` y la fila con peso: los logros llevan cinco estrellas de cuerpo 26 y el libro no, así que sin eso quedaban de distinto alto.

En la cabecera van tres atajos y en este orden: **libro, logros e historial**. Se empaquetan con `side="right"`, así que en el código están al revés --- el primero que se crea es el que queda más a la derecha. El libro (`self.book_button`) funciona desde cualquier pantalla: se consulta justo cuando aparece una palabra que no se entiende, y eso pasa en cualquier punto del programa.

`MODE_FLAGS` es el cartelito que va **dentro** de la tarjeta, al lado del nombre (`Card(flag=...)`), y vale para los tres modos y para las dos herramientas: es lo que hay que saber antes de elegir. Hoy lo lleva el analizador.

El límite de compases de la interfaz (`MAX_BARS`) es sólo de UI; el motor/CLI no debe asumir ese límite.

`_mode_accent` mira **primero** `TOOL_CARDS` y después `MODE_CARDS`: el experimentador y el analizador tiñen la interfaz con su color igual que los tres modos.

El cartel de donación tiene dos maneras y cada una en su recuadro (`_donation_card`): `DONATION_ALIAS` sirve sólo dentro de Argentina y `DONATION_LINK` es la de afuera. Poner sólo el alias dejaba a media humanidad mirando un dato que no puede usar.

## Historia, visitas y huevos

Estos sistemas son funcionalmente secundarios al motor musical. Mantener separados sus estados:
- `story.json`: progreso del sendero.
- `eggs.json`: huevos.
- `visitors.json`: visitas.
- `achievements.json`: logros.

Un personaje nuevo va en `cinematic.STAGING`, `SPEAKERS` y `POSES`. `staging_for()` **no falla** si falta: devuelve otra puesta y la escena se dibuja igual, con el cielo y los ruidos de quien no es. Lo vigila `TestVisitors.test_every_visitor_has_a_staging_of_its_own`.

Una visita se marca al terminar la escena, no al decidirla. Una visita normalmente se abre sobre la pantalla que la disparó y no devuelve al home. La visión inicial/pacto es la excepción porque se dispara desde el arranque.

`visitors.AWARDS` dice qué logro deja cada escena. Las dos primeras visiones no dejan ninguno ---no se pueden provocar, y un logro que depende de una tirada de una en cinco no es un logro--- y la tercera sí (`echoes_past`): es el final de lo único que el programa cuenta de punta a punta, y quien la ve es porque vio las tres. Se entrega al terminar la escena, junto con la marca.

Una línea de diálogo puede pedir que la digan más despacio (`story.Line.drag`, que `cinematic` divide sobre la velocidad del personaje y multiplica en las pausas). Es del renglón y no del personaje: la velocidad es actuación, no timbre.

`uitest` debe desactivar estas escenas para que una suite masiva no cambie el estado real.

No agregar huevos al sistema de logros: que sean secretos forma parte de su función.

La descripción de un logro puede llevar un tramo entre `**` en negrita: `achievements.runs()` la parte en tramos y `plain()` la devuelve sin marcas. La lista de logros dibuja los tramos ---una etiqueta cada uno, en fila y sin envolver, así que la negrita es para señalar una palabra y no un párrafo--- y el aviso y el cartel del legendario usan `plain()`.

Las variables de entorno de depuración/fuerza (`CHORDWEAVER_VISIT`, `CHORDWEAVER_VISION`, `CHORDWEAVER_PACT`, `CHORDWEAVER_TOMB`, etc.) existen para reproducir escenas difíciles de alcanzar manualmente.

## Analizador

`engine/analysis.py` (motor, puro) + `analyzer.Analyzer` (pantalla, desvío `"analysis"`) + `staff.GrandStaff` (sistema de dos pentagramas).

Reglas que se rompen solas si se las ignora:

- **El compás no es uno solo.** `Score.metres` lleva los cambios ---`(compás, tiempos, figura)`--- y de ahí salen `metre_at`, `metrics_at` y `bar_grid`. Todo lo que mida un tiempo fuerte tiene que preguntar por el compás de **esa** barra: `quarters_per_bar` y `beat_quarters` son sólo el compás de arranque. Forzar la pieza al primero corre la grilla desde el cambio hasta el final.
- **Se lee un acorde por tiempo, no por vertical.** Cada nota de paso cambia la vertical sin cambiar la armonía; leer vertical por vertical devuelve una progresión de fantasía. Ver `harmonic_segments`.
- **El piso de tres es de voces escritas y de la pieza entera** (`MIN_VOICES_FOR_CHORD`). Medido en alturas distintas, un coral que dobla la fundamental y omite la quinta no llega a tres en ninguna vertical y se quedaba sin análisis; aplicado tiempo por tiempo, un compás con tres acordes salía cifrado una sola vez.
- **Antes de leer acordes se descuentan las notas con forma de adorno** (`_ornament_shaped` + `Sonority.ornamental`, factor `ORNAMENT_WEIGHT`). Sin ese paso, un si de paso convierte un Do en Do maj7 --- la lectura falsa explica el 100% del material y gana.
- Una nota con forma de adorno **sólo** cuenta como tal si alguna otra voz sostiene. Cuatro voces moviéndose a la vez es un cambio de acorde.
- El descuento por nota floja (`SUPPORT_SHARE`) se aplica **sólo a la séptima**. Se probó con las cuatro notas y convertía un V6/5 en vii°: en una textura arpegiada la fundamental de un acorde invertido suena poco por definición.
- `_same_harmony` (unión de segmentos) exige **mismo bajo**. Sin eso, los seis acordes del bajo cromático descendente se leían como uno.
- **Las paralelas y las quintas ocultas se importan de `engine.fitness`.** No escribir una segunda copia: se desincroniza en el primer cambio y el analizador pasaría a aprobar lo que el generador prohíbe. Lo vigila `TestAnalysisCounterpoint.test_the_rules_come_from_the_evaluator`.
- **El movimiento se mide contra la nota anterior de cada voz, no contra la vertical de al lado** (`_previous_notes`, que devuelve `(nota anterior, cuándo empezó, cuándo empezó la de ahora)`). En un coral las dos cosas coinciden; en una textura arpegiada las voces entran por turno, y mirando la vertical vecina la que todavía no atacó sale «quieta»: las terceras paralelas del bajo y el alto del preludio de Bach se leían «oblicuo» y sus quintas paralelas no las veía nadie. Las paralelas y octavas se buscan sobre **esas mismas** notas, así que se marcan también cuando las dos voces se mueven una tras otra.
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
- `Analyzer._lanes` se rehace **después** de analizar, por nombre: `analyse()` reordena las voces por registro y la correspondencia hecha antes señalaba la voz de al lado.
- Los silencios se **dibujan** con trazos y no con signos de Unicode: los caracteres musicales no están en todas las fuentes de sistema y el de negra salía como un rectángulo vacío.
- Debajo del sistema va el cifrado del bajo **en columna** (`FIGURE_ROWS`, tres renglones) y el grado no va: escritos los dos al lado del cifrado americano no se leía ninguno.
- El sistema usa su propia escala (`GRAND_LINE_GAP`, `GRAND_STEP`) y no la del pentagrama de una línea: acá hay dos pentagramas, el hueco, y arriba y abajo los rótulos, y todo eso comparte la ventana con los tres paneles. `GRAND_TOP_MARGIN` tiene que dejar entrar la nota más aguda --- con el margen viejo, una nota sobre la quinta línea se dibujaba encima del cifrado y una bien aguda se dibujaba fuera del lienzo.
- El alto del lienzo se recalcula en cada dibujo contra la nota más grave; el margen de arriba es fijo porque de él salen las cuentas del click.
- **El sistema tiene que poder escribir silencios.** Sin ellos, una voz que entra tarde queda pegada al principio y las voces salen corridas entre sí: lo que se analiza deja de ser lo que dice la partitura. `importer.written_line()` es lo que convierte una voz leída en una voz escribible.
- `staff.index_for_pitch()` + `staff.accidental_for()` + `staff.pitch_at()` forman un ida y vuelta **exacto** en toda armadura. Es lo que permite importar, escribir en el pentagrama y analizar sin que cambie una nota. Lo vigila `TestAnalysisWriting`.
- El sistema **no** es una escalera continua: cada clave tiene su propia geometría (`_y_for(index, treble)`) y la voz decide en cuál se escribe (`staff_of`, mitad grave al fa). Se probó con la escalera corrida entera --- que es lo exacto --- y los dos pentagramas se leen como una sola grilla de diez líneas.
- **El tenor (`GrandStaff.SPLIT_VOICE`) se reparte nota por nota**: del do central (`MIDDLE_C`) para arriba se escribe en la clave de sol y para abajo en la de fa, que es lo que hace falta para escribir piano. Por eso `staff_of` recibe la altura y hay que preguntarle **por cada nota** --- dibujo, blanco del mouse, marca de la voz activa y cifrado ---; sin la altura contesta el pentagrama de siempre.
- El editor llega hasta **cuatro voces**. Una partitura con más se recorta a las cuatro más graves y se avisa.
- Se reanaliza solo, con espera (`REANALYSE_MS`); el hilo del sonido no toca Tk (`_watch_sound`, igual que `_when_done`).

Exportación: `session.export_analysis()` --- **un hueco por compás** y una línea escrita por voz (`ScoreSpec.voice_lines`, `line_for`), no un hueco por sonoridad: cortando en cada vertical, una redonda del bajo salía partida en semicorcheas ligadas. Cada voz se escribe con sus propias figuras (`_writable_pieces`, con ligaduras), la armadura decide cómo se escribe cada nota (`spell_by_key` → `theory.spell_in_key`), `pickup` marca el primer compás incompleto y `bar_time_signatures` los cambios de compás. **No** anota en el historial: un análisis no es una corrida del motor.

`assets/partituras/` trae el Preludio BWV 846 (ocho compases) para que haya algo que importar el primer día; `Analyzer.examples_directory()` es lo que abre ahí el diálogo. Lo vigila `TestAnalysisExample`, y `TestAnalysisReadsWhatWeWrite` comprueba que lo que exportan los tres modos vuelva a entrar por acá.

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
- `uitest.py`: aislamiento de datos y tutorial/visitas.

## Regla final

Antes de tocar algo de lógica musical: leer `MUSIC_LOGIC.md`.

Antes de tocar Cython: comprobar si hay `.pyd`.

Antes de tocar tests/UI: asegurar aislamiento mediante `uitest.Session` o rutas de datos descartables.

Antes de agregar una preferencia persistente: agregarla a `DEFAULT_SETTINGS`.

Antes de agregar un módulo al build: revisar `ChordWeaver.spec`.

No introducir documentación aquí para hechos que el código ya hace obvios.
