# -*- coding: utf-8 -*-
"""
La ventana principal en inglés: el carrusel, la configuración, el tutorial,
el libro, los logros y el sendero.

Las claves son las cadenas castellanas tal cual están escritas en `app.py`.
No se editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    # -- los títulos del carrusel --------------------------------------------
    #
    # El castellano de estos siete es además la clave con la que el programa
    # sabe qué pantalla está cerrando, así que se traducen sólo al dibujarse.
    'Modo': 'Mode',
    'Voces': 'Voices',
    'Acordes': 'Chords',
    'Resultado': 'Result',

    # -- diálogos del sistema ------------------------------------------------
    'Borrar todo': 'Clear all',
    'Compás': 'Metre',
    'Do mayor / La menor': 'C major / A minor',
    'Elegí dónde guardar la partitura': 'Choose where to save the score',
    'Elegí una partitura': 'Choose a score',
    'Error': 'Error',
    'Listo': 'Done',
    'No se pudo escribir ningún archivo.': 'No file could be written.',
    'No se pudo importar': 'Could not import',
    'Partitura importada': 'Score imported',
    'Se guardaron {written} archivos en:\n{dirname}':
        'Saved {written} files in:\n{dirname}',
    'Todos los archivos': 'All files',
    '▶  Escuchar': '▶  Play',
    '♪  Sonando…': '♪  Playing…',
    '\n\nLa lectura es aproximada: los cifrados se deducen de las notas, así que puede haber inversiones de más o algún acorde con otro nombre. Revisalos antes de generar.':
        '\n\nThe reading is approximate: the chord symbols are deduced from the '
        'notes, so there may be extra inversions or a chord under another '
        'name. Look them over before you generate.',
    '  ·  el último compás quedó incompleto':
        '  ·  the last measure came out incomplete',
    ' Hay {empty} casilla vacía que igual ocupa su duración: escribí un acorde o borrala con la ✕.':
        ' There is {empty} empty cell still taking up its duration: write a '
        'chord in it or clear it with the ✕.',
    ' Hay {empty} casillas vacías que igual ocupan su duración: escribí un acorde o borralas con la ✕.':
        ' There are {empty} empty cells still taking up their duration: write '
        'chords in them or clear them with the ✕.',
    ' · falta la estrella anterior': ' · the previous star is still open',
    '(tocá para cerrar)': '(click to dismiss)',
    '? ? ?': '? ? ?',
    'A otra tonalidad': 'To another key',
    'Abrir en el navegador': 'Open in the browser',
    'Abrí el libro de teoría desde la pantalla inicial y leé el capítulo «La música de los reprimidos». Con abrirlo y verlo alcanza.':
        'Open the theory book from the home screen and read the chapter “The '
        'music of the oppressed”. Opening it and looking at it is enough.',
    'Accesibilidad': 'Accessibility',
    'Aceptar': 'OK',
    'Acorde inicial y final': 'First and last chord',
    'Acordes con color añadido': 'Chords with added color',
    'Acordes de séptima': 'Seventh chords',
    'Acordes prestados del modo paralelo. Pasá el mouse por cada uno para ver qué aporta.':
        'Chords borrowed from the parallel mode. Hover over each one to see '
        'what it brings.',
    'Acá dice cuánto llevás puesto y cuánto entra. Si sobra o falta, el programa no puede escribir la partitura: un compás que no suma lo que dice su cifra lo rechaza cualquier editor de música.\n\nCon «+ acorde» agregás otro a ese compás, y con la ✕ sacás el que no querés.':
        'This tells you how much you have put in and how much fits. If there '
        'is too much or too little, the program cannot write the score: any '
        'music editor rejects a measure that does not add up to its time '
        'signature.\n\n“+ chord” adds another one to that measure, and the ✕ '
        'removes the one you do not want.',
    'Acá lo que manda es cómo se encadenan dos notas concretas de cada acorde, las que definen su color. El programa las conecta por el camino más corto y deja pasar cosas que el barroco prohíbe. Los acordes son más densos y suenan más modernos.':
        'What rules here is how two particular notes of each chord — the ones '
        'that define its color — link to the next. The program connects them '
        'by the shortest path and lets through things the baroque forbids. '
        'The chords are denser and sound more modern.',
    'Acá se define el material: la tonalidad, el modo, qué acordes prestados de fuera de la escala se permiten y con qué empieza y termina. El programa arma la progresión con eso y nada más, y después la juzga con las reglas del estilo.':
        'This is where the material is set: the key, the mode, which borrowed '
        'chords from outside the scale are allowed, and what it starts and '
        'ends with. The program builds the progression from that and nothing '
        'else, and then judges it by the rules of the style.',
    'Acá se dibuja la melodía': 'This is where you draw the melody',
    'Acá se elige el material': 'This is where the material is chosen',
    'Acá se escribe la progresión': 'This is where the progression is written',
    'Al lado de cada acorde va su duración. Y también los silencios: cualquier duración con «Silencio» adelante deja ese lugar sonando a nada, y el programa lo respeta —no lo rellena ni lo saltea.':
        'Each chord has its duration next to it. Rests too: any duration with '
        '“Rest” in front of it leaves that spot sounding like nothing, and the '
        'program respects it — it neither fills it in nor skips over it.',
    'Al pie de los logros están ahora los seis, con los pasos exactos para volver a provocarlos.':
        'All six are now at the foot of the achievements, with the exact steps '
        'to set them off again.',
    'Al tocar «Generar» arrancan doscientas soluciones al azar que se van cruzando y mejorando trescientas veces. Tarda unos segundos y se puede cancelar.\n\nAl final te muestra las tres mejores: como el azar interviene, dos corridas con la misma entrada dan resultados parecidos pero no idénticos.':
        'Pressing “Generate” starts two hundred random solutions that cross '
        'and improve three hundred times over. It takes a few seconds and can '
        'be cancelled.\n\nAt the end it shows you the best three: because '
        'chance is involved, two runs from the same input give similar but not '
        'identical results.',
    'Algo te está esperando en el {value}.':
        'Something is waiting for you in the {value}.',
    'Algoritmo genético': 'Genetic algorithm',
    'Algún valor no es un número válido.': 'Some value is not a valid number.',
    'Alias para transferir': 'Alias for bank transfer',
    'Analizador': 'Analyzer',
    'Anotaste lo que te dijeron': 'You wrote down what you were told',
    'Anotaste lo que viste': 'You wrote down what you saw',
    'Antes de hacer click, elegí acá cuánto dura la nota. Redonda es la más larga y corchea la más corta; las que dicen «c/punto» duran una vez y media.\n\n«Deshacer» borra la última —también con Ctrl+Z— y «Borrar todo» empieza de cero. «Escuchar» reproduce lo que llevás escrito, sin acordes todavía.':
        'Before clicking, choose how long the note lasts here. A whole note is '
        'the longest and an eighth note the shortest; the ones marked “dotted” '
        'last one and a half times as long.\n\n“Undo” erases the last one — '
        'Ctrl+Z works too — and “Clear all” starts from scratch. “Play” plays '
        'back what you have written so far, with no chords yet.',
    'Aplicar': 'Apply',
    'Armadura': 'Key signature',
    'Armadura, compás y qué voz sos':
        'Key signature, metre and which voice you are',
    'Armonización': 'Harmonization',
    'Armonía extendida. Lo que manda no es el bajo sino cómo se encadenan la tercera y la séptima de un acorde al siguiente.':
        'Extended harmony. What rules is not the bass but how the third and '
        'the seventh link from one chord to the next.',
    'Armonía y contrapunto, desde cero.': 'Harmony and counterpoint, from scratch.',
    'Arranca con {voices} · {mode} · {sevenths}. Todo esto se puede cambiar en las pantallas siguientes.':
        'Starts with {voices} · {mode} · {sevenths}. All of it can be changed '
        'on the next screens.',
    'Arrepentirse': 'Think better of it',
    'Atender': 'Answer',
    'Avanzar, volver y configurar': 'Forward, back and settings',
    'Ayuda': 'Help',
    'Bach · el modo coral': 'Bach · chorale mode',
    'Bach · las cinco barrocas': 'Bach · the five baroque ones',
    'Bloquear': 'Lock',
    'Bloquear {symbol}': 'Lock {symbol}',
    'Borra la última nota escrita.  (Ctrl+Z)':
        'Erases the last note written.  (Ctrl+Z)',
    'Buscando soluciones': 'Searching for solutions',
    'CAPÍTULO {numeral}': 'CHAPTER {numeral}',
    'Cada click pone una nota donde apuntaste. El pentagrama está en clave de sol: la línea de abajo es mi, y cuanto más arriba escribís, más agudo suena.\n\nLa nota que aparece sale de la armadura: en una armadura con fa sostenido, un click en la posición del fa escribe fa sostenido y no fa natural.':
        'Each click puts a note where you aimed. The staff is in treble clef: '
        'the bottom line is E, and the higher you write, the higher it '
        'sounds.\n\nThe note that appears comes from the key signature: in a '
        'signature with F sharp, a click on the F position writes F sharp and '
        'not F natural.',
    'Cada corrida que termina se anota sola. Generá una partitura y volvé acá.':
        'Every run that finishes writes itself down. Generate a score and come '
        'back here.',
    'Cambia el color sin cambiar el centro: la misma tónica pasa a {listed}.':
        'Changes the color without changing the centre: the same tonic becomes '
        '{listed}.',
    'Cancelar': 'Cancel',
    'Cantidad de voces distinta': 'Different number of voices',
    'Castiga saltos de tritono y de séptima':
        'Penalizes tritone and seventh leaps',
    'Cerrar': 'Close',
    'Chord': 'Chord',
    'ChordWeaver es gratis, y va a seguir siéndolo. No me parece prudente cobrar por esto: la música es de todos, y una herramienta para estudiar cómo se mueven las voces no debería tener un precio en la puerta.':
        'ChordWeaver is free, and it is going to stay that way. Charging for '
        'this does not seem right to me: music belongs to everyone, and a tool '
        'for studying how voices move should not have a price at the door.',
    'ChordWeaver {APP_VERSION}': 'ChordWeaver {APP_VERSION}',
    'Cifrado americano: Cmaj7, F#m7b5, Bb13, C/G. Cada compás tiene que llenarse exacto con las duraciones elegidas. El candado fija el orden de las voces de un acorde, y el piano sirve para armar a mano uno que el cifrado no sepa nombrar.':
        'Chord symbols: Cmaj7, F#m7b5, Bb13, C/G. Each measure has to fill up '
        'exactly with the durations you choose. The padlock fixes the order of '
        'a chord’s voices, and the piano is there to build by hand one that '
        'chord symbols cannot name.',
    'Cifrado barroco: los intervalos se cuentan desde el bajo. Un 6/5 es una séptima en primera inversión, o sea con la tercera abajo.':
        'Figured bass: the intervals are counted from the bass. A 6/5 is a '
        'seventh chord in first inversion, that is, with the third at the '
        'bottom.',
    'Cifrado, grado y área funcional': 'Chord symbol, degree and function',
    'Click en el pentagrama': 'Click on the staff',
    'Click en el pentagrama para poner cada nota, o usá el piano de abajo. El programa busca los acordes que la sostienen —respetando la armadura— y escribe las otras voces alrededor de la tuya, sin tocarla.':
        'Click on the staff to place each note, or use the piano below. The '
        'program looks for the chords that hold it up — respecting the key '
        'signature — and writes the other voices around yours, without '
        'touching it.',
    'Cmaj7': 'Cmaj7',
    'Comenzarás tu camino otra vez.\n\nLo que ya conseguiste no se pierde: los logros, los títulos y lo que quedó escrito en el libro siguen siendo tuyos. Lo que vuelve a cero es el sendero.':
        'You will begin your road again.\n\nWhat you have already earned is not '
        'lost: the achievements, the titles and whatever was written down in '
        'the book are still yours. What goes back to zero is the path.',
    'Compases': 'Measures',
    'Completaste los {total} logros de la {ordinal} estrella.':
        'You completed all {total} achievements of the {ordinal} star.',
    'Compás {bar_index}  ·  {signature}': 'Measure {bar_index}  ·  {signature}',
    'Compás {index}': 'Measure {index}',
    'Con Siguiente avanzás y con Atrás volvés sin perder nada de lo que hayas cargado: podés ir y venir todas las veces que quieras.\n\nEl engranaje guarda la configuración, el tamaño de letra — y ahí mismo está el botón para volver a ver este tutorial cuando lo necesites.':
        'Next moves you forward and Back returns without losing anything you '
        'have entered: you can go back and forth as many times as you '
        'like.\n\nThe gear holds the settings and the text size — and right '
        'there is the button to see this tutorial again whenever you need it.',
    'Con los voicings especiales prendidos, cuánto busca agregar novenas, oncenas o sextas en vez de duplicar una nota.':
        'With special voicings on, how hard it tries to add ninths, elevenths '
        'or sixths instead of doubling a note.',
    'Con qué empieza y con qué termina': 'What it starts and ends with',
    'Con qué frecuencia aparecen': 'How often they show up',
    'Con tarjeta, en el navegador': 'By card, in the browser',
    'Conecta las guide tones por grado conjunto':
        'Connects the guide tones by step',
    'Configuración y accesibilidad': 'Settings and accessibility',
    'Consonancia en los acordes de reposo': 'Consonance on resting chords',
    'Construye los acordes con cuatro notas en vez de tres: Cmaj7 en lugar de C. Es lo normal en jazz y la excepción en los otros estilos.':
        'Builds chords with four notes instead of three: Cmaj7 rather than C. '
        'It is the norm in jazz and the exception in the other styles.',
    'Copiado ✓': 'Copied ✓',
    'Copiar el alias': 'Copy the alias',
    'Copiar el enlace': 'Copy the link',
    'Coral al estilo Bach. Como el barroco pero más estricto: nunca duplica la sensible, exige que las séptimas resuelvan hacia abajo y vigila el espaciado entre voces.':
        'Bach-style chorale. Like the baroque but stricter: it never doubles '
        'the leading tone, requires sevenths to resolve downward and watches '
        'the spacing between voices.',
    'Cuando a un acorde le sobran voces, en vez de repetir una nota puede agregar una novena, una oncena o una sexta.':
        'When a chord has voices to spare, instead of repeating a note it can '
        'add a ninth, an eleventh or a sixth.',
    'Cuando una voz salta una tercera, queda un escalón vacío en el medio. Una nota de paso lo rellena: en vez de saltar de do a mi, la voz camina do-re-mi.\n\nElegí qué voces pueden usarlas y cuántas querés. Se agregan **después** de que el programa resolvió el reparto, sobre la solución ya elegida: son un adorno encima de algo que ya está bien escrito.':
        'When a voice leaps a third, an empty step is left in the middle. A '
        'passing note fills it in: instead of jumping from C to E, the voice '
        'walks C-D-E.\n\nChoose which voices may use them and how many you '
        'want. They are added **after** the program has settled the voicing, on '
        'top of the chosen solution: they are an ornament over something that '
        'is already well written.',
    'Cuántas de las mejores soluciones pasan intactas a la generación siguiente, sin riesgo de perderse.':
        'How many of the best solutions pass untouched to the next generation, '
        'with no risk of being lost.',
    'Cuántas soluciones conviven en cada generación. Más población explora mejor pero tarda más.':
        'How many solutions live together in each generation. A larger '
        'population explores better but takes longer.',
    'Cuántas veces se repite el ciclo de selección, cruza y mutación.':
        'How many times the cycle of selection, crossover and mutation repeats.',
    'Cuánto cierra el final': 'How firmly it closes',
    'Cuánto color': 'How much color',
    'Cuánto dura cada uno': 'How long each one lasts',
    'Cuánto se aleja': 'How far it travels',
    'Cuánto usarlos': 'How much to use them',
    'Cuántos candidatos compiten para ser padres. Más alto = más presión hacia los mejores, pero menos diversidad.':
        'How many candidates compete to become parents. Higher = more pressure '
        'toward the best, but less diversity.',
    'CÓMO CONSEGUIRLO': 'HOW TO EARN IT',
    'Cómo se hace cada uno': 'How each one is done',
    'De esas cruzas, qué fracción mezcla voz por voz (permite juntar un buen bajo con una buena soprano) en vez de cortar la progresión en un punto.':
        'Of those crossings, what fraction mixes voice by voice (letting a good '
        'bass join a good soprano) instead of cutting the progression at one '
        'point.',
    'De modo (misma tónica)': 'Of mode (same tonic)',
    'De qué está hecha una nota': 'What a note is made of',
    'Decís qué voz escribiste': 'You say which voice you wrote',
    'Deja pasar paralelas y tritonos': 'Lets parallels and tritones through',
    'Deja que la melodía se apoye también en sextas, séptimas o novenas, y que los acordes agreguen color en vez de duplicar notas.':
        'Lets the melody lean on sixths, sevenths or ninths as well, and lets '
        'the chords add color instead of doubling notes.',
    'Deja que los adornos usen notas de fuera de la escala. Da resultados más ricos, pero es muy probable que haya que retocarlos a mano: el programa no juzga si la cromática encaja en el contexto, sólo que sea alcanzable.':
        'Lets the ornaments use notes from outside the scale. It gives richer '
        'results, but you will very likely have to touch them up by hand: the '
        'program does not judge whether the chromatic note fits the context, '
        'only that it can be reached.',
    'Deja usar el cuarto menor en lugar del IV o del V, y el séptimo rebajado justo antes del cierre.':
        'Allows the minor fourth in place of IV or V, and the flat seventh '
        'right before the close.',
    'Descarta cualquier disposición donde dos voces suenen a distancia de tritono. Ojo: prenderlo hace imposible cualquier acorde de séptima de dominante, porque ese tritono es justamente lo que lo define.':
        'Discards any voicing where two voices sound a tritone apart. Careful: '
        'turning it on makes any dominant seventh chord impossible, because '
        'that tritone is exactly what defines it.',
    'Descarta cualquier disposición donde dos voces suenen a distancia de tritono. Sirve sobre todo para que las notas de color añadidas no formen uno.':
        'Discards any voicing where two voices sound a tritone apart. It is '
        'mostly there to keep the added color notes from forming one.',
    'Desde Argentina': 'From Argentina',
    'Desde cualquier otro lado': 'From anywhere else',
    'Deshacer': 'Undo',
    'Dibujá la melodía': 'Draw the melody',
    'Dibujás la melodía y su armadura':
        'You draw the melody and its key signature',
    'Dibujás una línea en el pentagrama o la traés de una partitura, y el programa busca los acordes que la sostienen. Elegís qué voz escribiste y él arma las demás alrededor.':
        'You draw a line on the staff or bring it in from a score, and the '
        'program looks for the chords that hold it up. You say which voice you '
        'wrote and it builds the rest around it.',
    'Donar': 'Donate',
    'Dos voces que están a distancia de quinta y se mueven juntas en la misma dirección manteniendo esa quinta. Es la prohibición más conocida del contrapunto: destruye la independencia de las líneas, porque se escuchan como una sola voz engrosada.':
        'Two voices a fifth apart moving together in the same direction and '
        'keeping that fifth. It is the best known prohibition in counterpoint: '
        'it destroys the independence of the lines, because they are heard as '
        'a single thickened voice.',
    'Dos voces que van a distancia de quinta y se mueven juntas en la misma dirección manteniendo esa distancia. Es la prohibición más famosa del contrapunto, y el motivo es concreto: cuando pasa, las dos líneas dejan de escucharse como dos y se funden en una sola engrosada.\n\nApagarla no rompe nada. Hay estilos enteros construidos sobre eso —el gregoriano, sin ir más lejos.':
        'Two voices a fifth apart moving together in the same direction and '
        'keeping that distance. It is the most famous prohibition in '
        'counterpoint, and the reason is concrete: when it happens, the two '
        'lines stop being heard as two and melt into a single thickened '
        'one.\n\nTurning it off breaks nothing. There are whole styles built on '
        'it — Gregorian chant, to look no further.',
    'El acorde {label} «{roman}» no existe en esta tonalidad. Disponibles: {value}':
        'The {label} chord “{roman}” does not exist in this key. Available: '
        '{value}',
    'El algoritmo prueba miles de repartos de voces y se queda con los tres más baratos.':
        'The algorithm tries thousands of voice layouts and keeps the three '
        'cheapest.',
    'El alias se copia mientras el programa esté abierto: en Windows el portapapeles lo sostiene la aplicación que copió.':
        'The alias stays copied while the program is open: on Windows the '
        'clipboard is held by the application that copied.',
    'El botón «piano» de cada casilla abre un teclado donde armás el acorde nota por nota. Es la salida para los que el cifrado no sabe nombrar: un acorde de cuartas, un cluster, cualquier cosa que se te ocurra.\n\nY arriba a la izquierda, «Importar partitura» lee un MusicXML y carga sus acordes con su ritmo.':
        'The “piano” button on each cell opens a keyboard where you build the '
        'chord note by note. It is the way out for the ones chord symbols '
        'cannot name: a quartal chord, a cluster, whatever occurs to '
        'you.\n\nAnd at the top left, “Import score” reads a MusicXML file and '
        'loads its chords with their rhythm.',
    'El camino se ha liberado': 'The road has been opened',
    'El candado fija las voces': 'The padlock fixes the voices',
    'El cifrado va acá': 'The chord symbol goes here',
    'El compás tiene que cerrar exacto': 'The measure has to add up exactly',
    'El compás {bar_index} suma {total:g} tiempos y necesita {quarters_per_bar:g}.{extra}':
        'Measure {bar_index} adds up to {total:g} beats and needs '
        '{quarters_per_bar:g}.{extra}',
    'El contrapunto de la práctica común: el de los corales y las invenciones. Es el más reglado de los tres, y el único que se puede apretar todavía más.':
        'Common practice counterpoint: the one of the chorales and the '
        'inventions. It is the most rule-bound of the three, and the only one '
        'that can be tightened further still.',
    'El cruce de caminos, años después': 'The crossroads, years later',
    'El cruce de caminos, otra vez': 'The crossroads, again',
    'El dibujo y el sonido leen la misma lista':
        'The drawing and the sound read the same list',
    'El elitismo no puede ser negativo.': 'Elitism cannot be negative.',
    'El elitismo tiene que ser menor que la población.':
        'Elitism has to be smaller than the population.',
    'El estilo no cambia los acordes: cambia cómo se pasa de uno al siguiente.\n\nEl barroco es el más reglado de los tres — el lenguaje de Bach. Prohíbe que dos voces se muevan en paralelo a ciertas distancias y premia que vayan en direcciones contrarias. Si estás empezando, es el que más se nota cuando algo sale mal.':
        'The style does not change the chords: it changes how you get from one '
        'to the next.\n\nBaroque is the most rule-bound of the three — Bach’s '
        'language. It forbids two voices moving in parallel at certain '
        'distances and rewards them for going in opposite directions. If you '
        'are starting out, it is the one where a mistake shows up most.',
    'El estilo no toca los acordes: decide cómo se conducen las voces de uno al siguiente — qué se prohíbe, qué se premia y con cuánta fuerza. En la pantalla de reglas podés prender y apagar cada una por separado; acá elegís de dónde parte todo.':
        'The style does not touch the chords: it decides how the voices are '
        'led from one to the next — what is forbidden, what is rewarded and '
        'how strongly. On the rules screen you can switch each one on and off '
        'separately; here you choose where it all starts from.',
    'El programa arma progresión y voces':
        'The program builds progression and voices',
    'El programa elige acordes y voces':
        'The program chooses chords and voices',
    'El programa es gratis. Esto es por si querés bancarlo igual.':
        'The program is free. This is in case you want to chip in anyway.',
    'El programa es gratis. Si querés bancarlo, acá está cómo.':
        'The program is free. If you want to chip in, here is how.',
    'El programa pone los acordes en los tiempos fuertes, y dora las notas que caen ahí. Lo que queda entre dos doradas se escucha contra el acorde que ya está sonando: así es como suena una melodía de verdad.\n\nSi querés un acorde en otra nota, prendé «Marcar notas» y tocala —o hacele click derecho. Y si hay uno que te sobra, el mismo gesto se lo saca.':
        'The program puts the chords on the strong beats and gilds the notes '
        'that land there. Whatever sits between two gilded notes is heard '
        'against the chord already sounding: that is how a real melody '
        'sounds.\n\nIf you want a chord on another note, switch on “Mark '
        'notes” and click it — or right-click it. And if there is one too '
        'many, the same gesture takes it away.',
    'El programa reparte las voces': 'The program lays out the voices',
    'El rango de {label} no se entiende. Usá nombres tipo C4, Bb3, F#5.':
        'The range for {label} cannot be read. Use names like C4, Bb3, F#5.',
    'El recorrido son siete pantallas: modo, estilo, voces, compases, los acordes, las reglas y el resultado. La barra se va llenando a medida que avanzás, y toma el color del modo que elegiste.':
        'The walkthrough is seven screens: mode, style, voices, measures, the '
        'chords, the rules and the result. The bar fills up as you go, and '
        'takes the color of the mode you chose.',
    'El resultado se juzga por dos cosas: cuánto se mueven las voces y cuánto respeta el estilo. Acá decidís cuál pesa más.':
        'The result is judged by two things: how much the voices move and how '
        'closely it follows the style. Here you decide which weighs more.',
    'El sendero avanza': 'The path moves on',
    'El torneo tiene que ser de al menos 2: con menos no hay a quién comparar.':
        'The tournament has to be at least 2: with fewer there is nobody to '
        'compare against.',
    'Elegilo si lo que tenés es una melodía. La dibujás en un pentagrama, decís qué voz la canta, y el programa busca los acordes que la sostienen y escribe las demás voces alrededor.':
        'Pick this one if what you have is a melody. You draw it on a staff, '
        'say which voice sings it, and the program looks for the chords that '
        'hold it up and writes the other voices around it.',
    'Elegilo si no tenés nada todavía. Vos ponés la tonalidad y cuánto querés que se anime; el programa inventa la progresión entera y después la escribe. Es por donde conviene empezar si nunca escribiste armonía.':
        'Pick this one if you have nothing yet. You set the key and how far you '
        'want it to venture; the program invents the whole progression and '
        'then writes it out. It is where to start if you have never written '
        'harmony before.',
    'Elegilo si ya tenés la progresión escrita: esos símbolos como C, Am, F, G. El programa no los toca ni los reordena — sólo decide qué nota canta cada voz.':
        'Pick this one if you already have the progression written: those '
        'symbols like C, Am, F, G. The program neither touches nor reorders '
        'them — it only decides which note each voice sings.',
    'Elegiste {chosen} voces. Tienen que ser entre 3 y 6.':
        'You chose {chosen} voices. There have to be between 3 and 6.',
    'Elegí la métrica base y cuántos compases. Cada compás puede después llevar la suya propia: el cambio de métrica en el medio de la pieza es legítimo y el programa lo escribe en la partitura.':
        'Choose the base metre and how many measures. Each measure can then '
        'carry its own: a change of metre in the middle of the piece is '
        'legitimate and the program writes it into the score.',
    'Elegís tonalidad, modo y largo': 'You choose key, mode and length',
    'Elegís tonalidad, modo y qué acordes prestados permitís. El programa arma la progresión entera y después la escribe a varias voces. Puede agregar notas de paso y gestos de época.':
        'You choose the key, the mode and which borrowed chords you allow. The '
        'program builds the whole progression and then writes it out in several '
        'voices. It can add passing notes and period gestures.',
    'Elevar probabilidad de cadencias especiales':
        'Raise the odds of special cadences',
    'Empieza en': 'Starts on',
    'En cifrado americano, que es el que usan los músicos para escribir acordes rápido: la letra es la nota de base —C es do, D re, E mi, F fa, G sol, A la, B si— y lo que sigue dice de qué tipo es.\n\nC es do mayor, Cm do menor, C7 con séptima, Cmaj7 con séptima mayor, C/G do mayor pero con el sol abajo de todo. Se valida mientras escribís: al costado aparece qué notas tiene o qué está mal.':
        'In chord symbols, which is what musicians use to write chords '
        'quickly: the letter is the root note and what follows says what kind '
        'of chord it is.\n\nC is C major, Cm is C minor, C7 has a seventh, '
        'Cmaj7 a major seventh, C/G is C major but with G at the bottom. It is '
        'checked as you type: off to the side you see which notes it has, or '
        'what is wrong.',
    'En números romanos: I es el acorde de la tónica, V el quinto grado, vi el sexto. Las minúsculas son los acordes menores de la escala.\n\nEmpezar y terminar en I es lo que hace que una pieza suene cerrada. Terminar en V la deja colgada a propósito, como una pregunta. «Obligatorio» no se negocia; «preferirlo» lo pesa contra todo lo demás, y «libre» deja elegir al programa.':
        'In roman numerals: I is the tonic chord, V the fifth degree, vi the '
        'sixth. Lowercase means the minor chords of the scale.\n\nStarting and '
        'ending on I is what makes a piece sound closed. Ending on V leaves it '
        'hanging on purpose, like a question. “Required” is not negotiable; '
        '“preferred” weighs it against everything else, and “free” lets the '
        'program choose.',
    'En {label} la nota grave tiene que ser menor que la aguda.':
        'In {label} the low note has to be lower than the high one.',
    'Entre 3 y 6 voces. Los rangos que ves son los estándar de cada cuerda y son una regla dura: ninguna solución va a poner una nota fuera de ellos. Si tu grupo llega a más o a menos, cambialos acá.':
        'Between 3 and 6 voices. The ranges you see are the standard ones for '
        'each part and they are a hard rule: no solution will put a note '
        'outside them. If your group reaches further, or less far, change them '
        'here.',
    'Equipo modesto': 'Modest machine',
    'Es anterior a la armonía como la conocemos. Las voces se mueven casi siempre a la nota de al lado, evitan el intervalo más tenso que existe, y en cambio sí se permiten los paralelos: el canto medieval se basaba justamente en eso.':
        'It comes before harmony as we know it. The voices almost always move '
        'to the next note over, they avoid the most tense interval there is, '
        'and parallels on the other hand are allowed: medieval chant was built '
        'on exactly that.',
    'Escribí al menos una nota antes de seguir.':
        'Write at least one note before going on.',
    'Escribí el acorde antes de bloquearlo.':
        'Write the chord before locking it.',
    'Escribí la progresión': 'Write the progression',
    'Escribí qué nota canta cada voz. El programa no va a tocar este acorde, pero sí lo usa para decidir cómo se mueven los acordes de al lado.':
        'Write which note each voice sings. The program will not touch this '
        'chord, but it does use it to decide how the chords beside it move.',
    'Escribís el cifrado, compás por compás':
        'You write the chord symbols, measure by measure',
    'Escribís la música en un sistema de dos pentagramas o la traés de un archivo, y el programa dice qué es cada acorde, qué hace en la tonalidad y qué está pasando entre las voces.':
        'You write the music on a grand staff or bring it in from a file, and '
        'the program says what each chord is, what it does in the key and what '
        'is going on between the voices.',
    'Escribís la progresión en cifrado americano —o importás una partitura— y el programa decide qué nota canta cada voz y en qué octava. No toca ni los acordes ni su orden: reparte y registra.':
        'You write the progression in chord symbols — or import a score — and '
        'the program decides which note each voice sings and in which octave. '
        'It touches neither the chords nor their order: it lays them out and '
        'places them in register.',
    'Escritura modal, anterior a la tonalidad. Casi todo el movimiento es por grado conjunto y el resultado suena a canto llano más que a armonía.':
        'Modal writing, older than tonality. Almost all the motion is stepwise '
        'and the result sounds like plainchant more than like harmony.',
    'Escuchá lo que salió. Recién ahí se puede seguir.':
        'Listen to what came out. Only then can you go on.',
    'Eso es todo lo que hace falta para empezar. Te llevo a la pantalla de logros: acabás de ganarte el primero.':
        'That is everything you need to get started. Let me take you to the '
        'achievements screen: you have just earned your first one.',
    'Esta barra dice cuánto falta': 'This bar says how far you have to go',
    'Esta máquina tiene {cpu_count} núcleos; la búsqueda va a usar {workers} proceso(s) y deja uno libre para que la ventana siga respondiendo.':
        'This machine has {cpu_count} cores; the search will use {workers} '
        'process(es) and leaves one free so the window keeps responding.',
    'Este estilo no ofrece ningún cambio de modo sobre la tónica que elegiste.':
        'This style offers no change of mode over the tonic you chose.',
    'Este estilo no viaja a otra tonalidad.':
        'This style does not travel to another key.',
    'Esto escribe música a varias voces':
        'This writes music in several voices',
    'Evita el tritono, saltado y entre voces':
        'Avoids the tritone, leapt and between voices',
    'Evita las novenas menores': 'Avoids minor ninths',
    'Evitar tritonos entre voces': 'Avoid tritones between voices',
    'Exigir (regla dura)': 'Require (hard rule)',
    'Experimentador de armónicos': 'Harmonics workbench',
    'Falta el acorde': 'Chord missing',
    'Falta un acorde en el compás {bar_index}.':
        'A chord is missing in measure {bar_index}.',
    'Fijar el orden exacto de las voces de este acorde. El programa no va a poder cambiarlo, pero lo sigue teniendo en cuenta al acomodar los acordes vecinos.':
        'Fix the exact order of this chord’s voices. The program will not be '
        'able to change it, but it still takes it into account when arranging '
        'the neighbouring chords.',
    'Generación {generation} de {total}   ·   mejor costo {best:.0f}':
        'Generation {generation} of {total}   ·   best cost {best:.0f}',
    'Generar': 'Generate',
    'Gracias por usarlo.': 'Thanks for using it.',
    'Gregorio · el organum': 'Gregory · the organum',
    'Guardar como…': 'Save as…',
    'Guardar en la carpeta del programa': 'Save in the program folder',
    'Género': 'Style',
    'Hace exactamente lo mismo que el click: agrega una nota al final de la línea, con la figura que tengas elegida arriba. Sirve sobre todo para las notas alteradas y para las que caen lejos de las cinco líneas.':
        'It does exactly what clicking does: it adds a note at the end of the '
        'line, with the note value you have chosen above. It is mostly there '
        'for accidentals and for notes that fall far from the five lines.',
    'Hasta un tercio de la barra sólo agrega sextas, que es el color más suave. Más allá entran también novenas y oncenas.':
        'Up to a third of the way along it only adds sixths, which are the '
        'gentlest color. Beyond that ninths and elevenths come in too.',
    'Hay alguien esperando': 'Somebody is waiting',
    'Hay cosas que el programa hace y no cuenta.':
        'There are things the program does and does not mention.',
    'Hay una entrada nueva en el capítulo de las visitas, en el libro de teoría.':
        'There is a new entry in the chapter on the visitors, in the theory '
        'book.',
    'Hay una entrada nueva en el capítulo del sendero, en el libro de teoría.':
        'There is a new entry in the chapter on the path, in the theory book.',
    'Hay {fresh} entradas nuevas en el capítulo del sendero, en el libro de teoría.':
        'There are {fresh} new entries in the chapter on the path, in the '
        'theory book.',
    'Hay {voice_keys} voces: más notas que ésas se escriben dando algunas por sobreentendidas.':
        'There are {voice_keys} voices: more notes than that get written by '
        'leaving some understood.',
    'Historial': 'History',
    'Huevos de pascua': 'Easter eggs',
    'Idioma': 'Language',
    'Ignorar': 'Ignore',
    'Importar partitura…': 'Import score…',
    'Importar…': 'Import…',
    'Intercambio modal: un acorde prestado del modo paralelo. Sigue en la misma tonalidad, con una nota de la escala cambiada.':
        'Modal interchange: a chord borrowed from the parallel mode. It stays '
        'in the same key, with one note of the scale changed.',
    'Intercambios modales': 'Modal interchange',
    'Ir a los logros': 'Go to the achievements',
    'LOGRO LEGENDARIO': 'LEGENDARY ACHIEVEMENT',
    'La armadura decide en qué tonalidad estás y qué notas van alteradas. El compás agrupa los tiempos, y es lo que decide dónde caen los acordes.\n\n«Mi voz es» dice cuál de las voces escribiste: normalmente la más aguda, pero si la melodía va por abajo elegí el bajo y el programa escribe las otras por encima.':
        'The key signature decides which key you are in and which notes are '
        'altered. The metre groups the beats, and that is what decides where '
        'the chords land.\n\n“My voice is” says which of the voices you wrote: '
        'normally the highest, but if the melody runs underneath choose the '
        'bass and the program writes the others above it.',
    'La entidad': 'The entity',
    'La mayor / Fa# menor': 'A major / F# minor',
    'La melodía baja hasta {note_name}':
        'The melody goes down to {note_name}',
    'La melodía baja hasta {note_name} y sube hasta {note_name2}':
        'The melody goes down to {note_name} and up to {note_name2}',
    'La melodía sube hasta {note_name}': 'The melody goes up to {note_name}',
    'La nota más grave se toma como fundamental.':
        'The lowest note is taken as the root.',
    'La partitura tiene {voice_count} voces y vos elegiste {voice_keys}. Se van a cargar los acordes igual, repartidos entre las voces que elegiste. ¿Seguimos?':
        'The score has {voice_count} voices and you chose {voice_keys}. The '
        'chords will be loaded anyway, spread across the voices you chose. '
        'Shall we go on?',
    'La pieza puede irse a otra tonalidad, o cambiar de modo sobre la misma tónica, y siempre vuelve al punto de partida antes de terminar. Se pueden usar las dos a la vez.':
        'The piece can travel to another key, or change mode over the same '
        'tonic, and it always returns to where it started before it ends. Both '
        'can be used at once.',
    'La población tiene que ser al menos 10 y las generaciones al menos 1.':
        'The population has to be at least 10 and the generations at least 1.',
    'La primera es la que el programa eligió; las otras mueven menos bien las voces o negocian algo más con las reglas del estilo.':
        'The first is the one the program chose; the others move the voices '
        'less well or bargain a little harder with the rules of the style.',
    'La progresión se arma pesando dos cosas: lo que el estilo pide y lo que le conviene al movimiento de las voces. Este dial dice cuánto manda el estilo.\n\nHacia «estricto» sale una progresión más de manual, con las funciones en su lugar. Hacia «flexible» el programa se permite giros que el estilo no usaría, y aparecen cosas más raras.':
        'The progression is built by weighing two things: what the style asks '
        'for and what suits the movement of the voices. This dial says how '
        'much the style rules.\n\nToward “strict” you get a more textbook '
        'progression, with the functions in their places. Toward “flexible” '
        'the program allows itself turns the style would not use, and odder '
        'things show up.',
    'La proporción de cruce uniforme': 'The uniform crossover share',
    'La tasa de cruce': 'The crossover rate',
    'La tasa de mutación': 'The mutation rate',
    'La tonalidad es la nota que manda: la que suena a casa, la que el oído espera al final. El modo dice qué escala se arma sobre ella, y de la escala salen los siete acordes que el programa tiene permitido usar.\n\nJónico es el mayor de toda la vida y eólico el menor. Los otros cinco cambian una o dos notas de la escala y suenan a otra cosa: el dórico a folk, el frigio a español, el lidio a banda de sonido.':
        'The key is the note in charge: the one that sounds like home, the one '
        'the ear expects at the end. The mode says which scale is built on it, '
        'and from the scale come the seven chords the program is allowed to '
        'use.\n\nIonian is plain old major and aeolian is minor. The other five '
        'change one or two notes of the scale and sound like something else: '
        'dorian like folk, phrygian like Spain, lydian like a film score.',
    'La visión del cruce de caminos': 'The vision of the crossroads',
    'Las apariciones que ya te ocurrieron. Se juegan enteras, igual que la primera vez.':
        'The apparitions that have already happened to you. They play in full, '
        'just like the first time.',
    'Las cadencias completas — la frigia, el ciclo de Vivaldi y el bajo cromático — aparecen del 10% al 20% de las veces cuando se dan las condiciones.':
        'The complete cadences — the phrygian, the Vivaldi cycle and the '
        'chromatic bass — turn up 10% to 20% of the time when the conditions '
        'are right.',
    'Las de la izquierda son duras': 'The ones on the left are hard rules',
    'Las diez más recientes, guardadas al lado del programa. Se anota cada corrida que termina, se haya exportado o no. El color del recuadro es el del modo con el que se hizo.':
        'The ten most recent, kept next to the program. Every run that '
        'finishes is written down, exported or not. The color of the box is '
        'that of the mode it was made with.',
    'Las doradas son las notas que van a llevar acorde. El click derecho ---o «Marcar notas» prendido--- prende y apaga el dorado de una nota: sirve tanto para pedir un acorde donde no lo había como para sacar el que puso el programa.':
        'The gilded ones are the notes that will carry a chord. Right-clicking '
        '— or “Mark notes” switched on — turns a note’s gilding on and off: it '
        'works both for asking for a chord where there was none and for taking '
        'away the one the program put there.',
    'Las mejores soluciones': 'The best solutions',
    'Las mismas reglas, pero pesando mucho más: salta menos (3 semitonos en vez de 4), castiga el doble duplicar la sensible, exige la resolución de las séptimas y no tolera el solapamiento de voces. Escribe más ceñido y se mueve menos libremente.':
        'The same rules, but weighing far more: it leaps less (3 semitones '
        'instead of 4), penalizes doubling the leading tone twice as hard, '
        'requires sevenths to resolve and does not tolerate overlapping '
        'voices. It writes tighter and moves less freely.',
    'Las mismas tres opciones, tal como quedaron guardadas.':
        'The same three options, exactly as they were saved.',
    'Las notas de paso': 'Passing notes',
    'Las notas doradas llevan acorde': 'The gilded notes carry a chord',
    'Las recetas clásicas, para desarmarlas':
        'The classic recipes, there to be taken apart',
    'Las tres terminan en lo mismo: una progresión escrita a varias voces. Cambia cuánto ponés vos.':
        'All three end in the same place: a progression written out in several '
        'voices. What changes is how much of it you put in.',
    'Las voces quedan cruzadas: cada una tiene que estar por encima de la anterior.':
        'The voices end up crossed: each one has to be above the previous one.',
    'Le pediste todo, a la vez, al máximo.':
        'You asked it for everything, at once, at the maximum.',
    'Lee un archivo MusicXML y carga sus acordes con su ritmo. El orden de las voces queda como punto de partida: el programa puede reacomodarlo, salvo en los acordes que fijes con el candado.':
        'Reads a MusicXML file and loads its chords with their rhythm. The '
        'order of the voices is left as a starting point: the program may '
        'rearrange it, except in the chords you pin with the padlock.',
    'Lee una melodía de un archivo MusicXML. Toma la nota más aguda de cada momento, así que sirve aunque la partitura traiga más de una voz.':
        'Reads a melody from a MusicXML file. It takes the highest note at '
        'each moment, so it works even if the score comes with more than one '
        'voice.',
    'Legendarios': 'Legendary',
    'Libro de teoría': 'Theory book',
    'Listo: la búsqueda va a tardar alrededor de la mitad. A cambio afina menos, así que vas a oír algo más de movimiento entre acordes.':
        'Done: the search will take about half as long. In exchange it polishes '
        'less, so you will hear a little more movement between chords.',
    'Lo mismo que las quintas paralelas pero a distancia de octava o unísono. Suena todavía más fusionado, así que en la práctica común está igual de prohibido.':
        'The same as parallel fifths but at the octave or the unison. It sounds '
        'even more fused, so in common practice it is just as forbidden.',
    'Logros': 'Achievements',
    'Los acordes prestados': 'Borrowed chords',
    'Los encontraste todos. Tocá el huevo.': 'You found them all. Touch the egg.',
    'Los logros se ganan solos': 'Achievements earn themselves',
    'Los siete grados de la escala son el material de base. Un intercambio modal es traer un acorde del modo paralelo —el menor de la misma tónica, o al revés— sin cambiar de tonalidad.\n\nEs de donde sale casi todo lo que suena a moderno: un cuarto menor en medio de una pieza mayor, un séptimo bemol antes del cierre. El deslizador de abajo dice con cuánta ganas los busca.':
        'The seven degrees of the scale are the base material. Modal '
        'interchange is bringing in a chord from the parallel mode — the minor '
        'on the same tonic, or the other way round — without changing '
        'key.\n\nIt is where almost everything that sounds modern comes from: a '
        'minor fourth in the middle of a major piece, a flat seventh before the '
        'close. The slider below says how eagerly it looks for them.',
    'Los valores arrancan como los deja el estilo {label}, pero desde acá mandás vos: las de la izquierda son duras —lo que las rompe se descarta— y la de la derecha decide qué pesa más al comparar dos soluciones válidas. Pasá el mouse por cada una para ver qué significa.':
        'The values start out as the {label} style leaves them, but from here '
        'on you are in charge: the ones on the left are hard — anything that '
        'breaks them is discarded — and the one on the right decides what '
        'weighs more when comparing two valid solutions. Hover over each one to '
        'see what it means.',
    'Los valores por defecto andan bien para casi todo. Pasá el mouse por cada uno para ver qué hace.':
        'The defaults work well for almost everything. Hover over each one to '
        'see what it does.',
    'Mantiene las notas comunes entre acordes':
        'Keeps the common tones between chords',
    'Marcando…': 'Marking…',
    'Marcar notas': 'Mark notes',
    'Marcaste {label} como vox principalis, pero esa voz no está en el conjunto.':
        'You marked {label} as vox principalis, but that voice is not in the '
        'ensemble.',
    'Marcás qué préstamos y adornos permitís':
        'You mark which borrowings and ornaments you allow',
    'Medida desde el bajo, como en el bajo cifrado: en un 3-5-1 el bajo canta la tercera, así que los intervalos son de 3ra y 6ta, ambos consonantes. Elegí cuánto pesa: la última opción la vuelve regla dura y anula cualquier solución que no la cumpla.':
        'Measured from the bass, as in figured bass: in a 3-5-1 the bass sings '
        'the third, so the intervals are a 3rd and a 6th, both consonant. '
        'Choose how much it weighs: the last option makes it a hard rule and '
        'voids any solution that does not meet it.',
    'Melodía': 'Melody',
    'Melodía importada': 'Melody imported',
    'Mi voz es': 'My voice is',
    'Mientras está encendido, cada click del pentagrama prende o apaga el acorde de una nota en vez de escribirla. Apaga también las que doró el programa.':
        'While this is on, each click on the staff turns a note’s chord on or '
        'off instead of writing it. It also turns off the ones the program '
        'gilded.',
    'Mirá qué te falta': 'See what you are missing',
    'Modo coral': 'Chorale mode',
    'Modulaciones': 'Modulations',
    'Modular es irse a otra tonalidad en el medio de la pieza y volver antes del final. No es un préstamo: la pieza pasa a girar de verdad alrededor de otra nota, y después regresa.\n\nHace falta lugar para irse y volver, así que con menos de ocho compases queda apagado y dice por qué. El deslizador de abajo dice cuánto se aleja.':
        'To modulate is to leave for another key in the middle of the piece and '
        'come back before the end. It is not a borrowing: the piece really does '
        'start turning around another note, and then it returns.\n\nIt takes '
        'room to leave and come back, so with fewer than eight measures it '
        'stays off and says why. The slider below says how far it travels.',
    'MusicXML y MIDI': 'MusicXML and MIDI',
    'Métrica base': 'Base metre',
    'Necesitás al menos 8 compases: la pieza tiene que asentar la tonalidad, viajar y volver, y con {bar_count} no hay lugar para eso.':
        'You need at least 8 measures: the piece has to settle the key, travel '
        'and come back, and with {bar_count} there is no room for that.',
    'Ninguna nota seleccionada': 'No note selected',
    'No entiendo ese acorde: {exc}': 'I do not understand that chord: {exc}',
    'No golpeó la puerta, no hizo ruido y no se fue. Vas a tener que atender vos.':
        'It did not knock, it made no noise and it did not leave. You are going '
        'to have to answer.',
    'No hace falta, y no cambia nada: el programa es exactamente el mismo con donación y sin ella. No hay nada cerrado detrás de esto.':
        'It is not required, and it changes nothing: the program is exactly the '
        'same with a donation and without one. There is nothing locked behind '
        'this.',
    'No hay que buscarlos: se desbloquean mientras trabajás, y cada uno señala algo que acabás de hacer sin darte cuenta. Son cuarenta y tres, repartidos en tres estrellas.':
        'There is no need to hunt for them: they unlock while you work, and '
        'each one points at something you have just done without noticing. '
        'There are forty-three, spread across three stars.',
    'No se encontró solución': 'No solution found',
    'No se llega a leer de quién es, ni de qué.':
        'You cannot quite read whose it is, or what it is about.',
    'No se pudo': 'Could not',
    'No se pudo escribir la pieza': 'The piece could not be written',
    'Normalmente el programa elige el reparto de cada acorde. Con el candado le decís exactamente qué nota canta cada voz en ése, y ya no lo cambia.\n\nSirve cuando querés un acorde puntual sonando de una manera concreta. Los acordes de al lado se siguen acomodando alrededor del que fijaste.':
        'Normally the program chooses the layout of each chord. With the '
        'padlock you tell it exactly which note each voice sings in that one, '
        'and it stops changing it.\n\nIt is useful when you want one particular '
        'chord sounding a particular way. The chords beside it still arrange '
        'themselves around the one you pinned.',
    'Notas de paso': 'Passing notes',
    'Nuevo': 'New',
    'O el piano, si el pentagrama te cuesta':
        'Or the piano, if the staff is hard going',
    'Omitir': 'Skip',
    'Opción {position}': 'Option {position}',
    'Opción {position}  ·  {label}': 'Option {position}  ·  {label}',
    'Organum: marcá la voz que lleva el canto (vox principalis). La voz inmediata inferior será la vox organalis y buscará moverse en paralelo con ella, a la cuarta, la quinta o la octava. No puede ser la voz más grave: necesita una voz debajo para acompañarla.':
        'Organum: mark the voice that carries the chant (vox principalis). The '
        'voice immediately below will be the vox organalis and will try to move '
        'in parallel with it, at the fourth, the fifth or the octave. It cannot '
        'be the lowest voice: it needs a voice underneath to accompany it.',
    'Paralelas, cruces y notas de adorno':
        'Parallels, crossings and ornamental notes',
    'Parámetros': 'Rules',
    'Paso {index} de {screens} · {screen_titles}':
        'Step {index} of {screens} · {screen_titles}',
    'Pediste {asked}: el máximo son {MAX_BARS} compases.':
        'You asked for {asked}: the maximum is {MAX_BARS} measures.',
    'Permite organum a la 4ta, la 5ta y la 8va':
        'Allows organum at the 4th, the 5th and the 8ve',
    'Permitir cromáticas': 'Allow chromatic notes',
    'Permitir intercambios modales': 'Allow modal interchange',
    'Permitir voicings especiales': 'Allow special voicings',
    'Pero el proyecto lleva tiempo, y sostenerlo cuesta. Si te sirvió y querés bancarlo, una donación ayuda a financiarlo y se agradece muchísimo.':
        'But the project takes time, and keeping it going costs. If it was '
        'useful to you and you want to support it, a donation helps fund it and '
        'is enormously appreciated.',
    'Peso de la armonía frente al voice leading':
        'Weight of harmony against voice leading',
    'Población': 'Population',
    'Podés dejarlos libres, preferirlos con peso, o exigirlos. Obligatorio no se negocia: ese lugar queda con un solo acorde posible.':
        'You can leave them free, prefer them with some weight, or require '
        'them. Required is not negotiable: that spot is left with a single '
        'possible chord.',
    'Podés fijar un acorde con el candado':
        'You can pin a chord with the padlock',
    'Pone todo el programa': 'The program puts in everything',
    'Por ejemplo, las quintas paralelas': 'Parallel fifths, for example',
    'Premia el movimiento contrario': 'Rewards contrary motion',
    'Premiar apenas': 'Reward slightly',
    'Premiar fuerte': 'Reward strongly',
    'Prendida, una regla de éstas no se negocia: cualquier reparto que la rompa se descarta entero, por bueno que sea en todo lo demás. Por eso una regla prendida nunca aparece violada en el resultado.\n\nPasá el mouse por cada una para ver qué significa.':
        'Switched on, a rule like these is not negotiable: any layout that '
        'breaks it is thrown out entirely, however good it may be at everything '
        'else. That is why a rule that is on never shows up broken in the '
        'result.\n\nHover over each one to see what it means.',
    'Preparando…': 'Getting ready…',
    'Prob. de cruza': 'Crossover prob.',
    'Probabilidad de combinar dos padres. Es el motor principal de la búsqueda: recombina tramos enteros de buen voice leading, así que va bastante más alta que la mutación.':
        'Probability of combining two parents. It is the main engine of the '
        'search: it recombines whole stretches of good voice leading, so it '
        'runs quite a bit higher than mutation.',
    'Probabilidad de que una nota suelta cambie de octava o de nota del acorde. Aporta variación fina, no estructura.':
        'Probability that a single note changes octave or chord tone. It '
        'contributes fine variation, not structure.',
    'Probá aflojando alguna regla en la pantalla anterior o ampliando los rangos vocales.':
        'Try loosening a rule on the previous screen or widening the vocal '
        'ranges.',
    'Producción': 'Production',
    'Prohibir cruce de voces': 'Forbid voice crossing',
    'Prohibir tritono melódico': 'Forbid the melodic tritone',
    'Que una voz cante más agudo que la voz que tiene arriba (por ejemplo el tenor por encima del alto). Confunde al oído sobre qué línea es cuál. Conviene dejarlo prendido salvo en texturas muy densas de 5 o 6 voces.':
        'A voice singing higher than the voice above it (the tenor above the '
        'alto, for instance). It confuses the ear about which line is which. '
        'Best left on except in very dense textures of 5 or 6 voices.',
    'Que una voz salte un tritono (tres tonos, por ejemplo de Fa a Si). Que una voz salte tres tonos de una vez. Es un intervalo áspero y difícil de cantar, y los estilos antiguos lo evitan.':
        'A voice leaping a tritone (three whole tones, from F to B for '
        'instance). A voice leaping three whole tones at once. It is a harsh '
        'interval and hard to sing, and the older styles avoid it.',
    'Quitar candado': 'Remove padlock',
    'Qué es un acorde, qué es una voz, qué es una cadencia y por qué unas suenan a final y otras no. Está escrito desde cero, y se va llenando solo: cada cosa que descubrís usando el programa queda anotada ahí.':
        'What a chord is, what a voice is, what a cadence is and why some sound '
        'like an ending and others do not. It is written from scratch, and it '
        'fills itself in: everything you discover using the program gets '
        'written down there.',
    'Qué figura estás escribiendo': 'Which note value you are writing',
    'Re mayor / Si menor': 'D major / B minor',
    'Recorrido hasta el final.': 'Walkthrough seen all the way through.',
    'Recorta la búsqueda para una máquina que sufre: la mitad de generaciones, la mitad de tiempo. Los resultados siguen siendo válidos —ninguna regla dura se afloja— pero el programa tiene menos vueltas para pulir la conducción de voces. La población no se toca: es de donde sale el arranque válido de la búsqueda, y bajándola las piezas largas dejan de generarse del todo.':
        'Trims the search for a machine that is struggling: half the '
        'generations, half the time. The results are still valid — no hard rule '
        'is loosened — but the program has fewer passes to polish the voice '
        'leading. The population is left alone: it is where the valid starting '
        'point of the search comes from, and lowering it stops long pieces from '
        'generating at all.',
    'Recuerdo de {lower}.': 'A memento of {lower}.',
    'Reglas duras': 'Hard rules',
    'Reglas y balance': 'Rules and balance',
    'Rellenan un salto de tercera con movimiento por grado conjunto. Elegí qué voces pueden usarlas.':
        'They fill a leap of a third with stepwise motion. Choose which voices '
        'may use them.',
    'Reproduce la melodía sola, para escuchar lo que estás escribiendo antes de armonizarla.':
        'Plays the melody on its own, so you can hear what you are writing '
        'before harmonizing it.',
    'Reproduce la primera opción tal como quedó guardada, con sus duraciones.':
        'Plays the first option exactly as it was saved, with its durations.',
    'Reproduce los acordes en orden con un sonido simple, respetando sus duraciones. Las notas de adorno no se incluyen.':
        'Plays the chords in order with a plain sound, respecting their '
        'durations. Ornamental notes are not included.',
    'Restaurar valores por defecto': 'Restore defaults',
    'Se abrió la lista de los huevos': 'The list of eggs has opened',
    'Se aplica al momento. Lo que ya generaste no cambia: los acordes se llaman igual en los dos idiomas.':
        'It takes effect right away. What you have already generated does not '
        'change: chords are called the same in both languages.',
    'Se aplica al reabrir el programa. La configuración queda guardada junto al ejecutable.':
        'It takes effect when you reopen the program. The settings are saved '
        'next to the executable.',
    'Se cargaron {chords} acordes.': 'Loaded {chords} chords.',
    'Se cargaron {notes} notas.': 'Loaded {notes} notes.',
    'Se cortó la búsqueda: {error}': 'The search was cut short: {error}',
    'Se enciende el oro': 'The gold lights up',
    'Se hace en el Organizador.': 'It is done in the Organizer.',
    'Seguir': 'Go on',
    'Siguiente': 'Next',
    'Siguiente  →': 'Next  →',
    'Silencio: acá no suena nada.': 'Rest: nothing sounds here.',
    'Sin quintas ni octavas paralelas': 'No parallel fifths or octaves',
    'Sólo MIDI': 'MIDI only',
    'Sólo MusicXML': 'MusicXML only',
    'Tamaño de letra': 'Text size',
    'Tamaño de torneo': 'Tournament size',
    'Tasa de mutación': 'Mutation rate',
    'Te pasaste por {extra}: hay {voice_keys} voces, así que {extra2} de estas notas no se van a escribir.':
        'You are over by {extra}: there are {voice_keys} voices, so {extra2} of '
        'these notes will not be written.',
    'Termina en': 'Ends on',
    'Tocá la tecla dorada del piano para seguir.':
        'Play the gilded key on the piano to go on.',
    'Tocá las teclas que forman el acorde':
        'Play the keys that make up the chord',
    'Todavía ninguno.': 'None yet.',
    'Todavía no cargaste ningún acorde.': 'You have not entered any chord yet.',
    'Todavía no hay nada guardado': 'Nothing has been saved yet',
    'Todo lo que no es una regla dura se pesa entre sí, y este dial decide el balance.\n\nHacia la izquierda importa que las voces se muevan lo menos posible: sale suave y previsible. Hacia la derecha importa el estilo —espaciado, movimiento contrario, tesitura— y el programa acepta mover más las voces a cambio de escribir más idiomático. En el medio pesan igual.':
        'Everything that is not a hard rule is weighed against everything else, '
        'and this dial decides the balance.\n\nToward the left what matters is '
        'that the voices move as little as possible: the result is smooth and '
        'predictable. Toward the right what matters is the style — spacing, '
        'contrary motion, tessitura — and the program accepts moving the voices '
        'more in exchange for writing more idiomatically. In the middle they '
        'weigh the same.',
    'Tolera las paralelas perfectas': 'Tolerates perfect parallels',
    'Tonalidad': 'Key',
    'Tonalidad y modo': 'Key and mode',
    'Trae adentro el modo coral, más severo':
        'Brings chorale mode with it, stricter still',
    'Tramo {step} de {total_steps}  ·  {title}  ·  en el {value}':
        'Stage {step} of {total_steps}  ·  {title}  ·  in the {value}',
    'TÍTULO SECRETO': 'SECRET TITLE',
    'Título obtenido: {SECRET_TITLE}.': 'Title earned: {SECRET_TITLE}.',
    'Título obtenido: {TRIUMPH_TITLE}': 'Title earned: {TRIUMPH_TITLE}',
    'Título obtenido: {title}': 'Title earned: {title}',
    'Títulos': 'Titles',
    'Un acorde de reposo suena cerrado cuando los intervalos contra el bajo son consonantes. Acá elegís cuánto le importa eso al programa: desde ignorarlo hasta exigirlo, que lo convierte en una regla dura más.\n\nSi las piezas te terminan sonando abiertas, subilo.':
        'A resting chord sounds closed when the intervals against the bass are '
        'consonant. Here you choose how much that matters to the program: from '
        'ignoring it to requiring it, which turns it into one more hard '
        'rule.\n\nIf your pieces end up sounding open, turn it up.',
    'Una nota no es una frecuencia sola: es la suya y además múltiplos enteros de la suya. Acá se los apaga, se los amplifica y se los corre de lugar, de a uno, para escuchar qué queda.':
        'A note is not a single frequency: it is its own and, on top of that, '
        'whole-number multiples of its own. Here you switch them off, amplify '
        'them and shift them out of place, one at a time, to hear what is left.',
    'Una progresión de acordes dice qué notas suenan juntas, pero no dice quién canta cuál. ChordWeaver se ocupa de eso: reparte las notas de cada acorde entre las voces de manera que cada una se mueva lo menos posible y que ninguna choque con las otras.\n\nEste recorrido dura un minuto y te muestra dónde está cada cosa. Podés saltearlo cuando quieras.':
        'A chord progression says which notes sound together, but it does not '
        'say who sings which. ChordWeaver takes care of that: it hands out the '
        'notes of each chord among the voices so that each one moves as little '
        'as possible and none of them collide.\n\nThis walkthrough takes a '
        'minute and shows you where everything is. You can skip it whenever you '
        'like.',
    'Una solución que rompa una regla prendida se descarta.':
        'A solution that breaks a rule that is switched on is discarded.',
    'Usar estas notas': 'Use these notes',
    'Ver detalle': 'See details',
    'Ver el tutorial otra vez': 'See the tutorial again',
    'Viaja a otra tonalidad — {listed} — y regresa.':
        'Travels to another key — {listed} — and comes back.',
    'Voicing fijo para {symbol}': 'Fixed voicing for {symbol}',
    'Volver a ver': 'See it again',
    'Volver al principio': 'Back to the start',
    'Vos ponés la melodía': 'You bring the melody',
    'Vos ponés los acordes': 'You bring the chords',
    'Vos traés la partitura': 'You bring the score',
    'Vuelve a correr el recorrido de bienvenida y devuelve las explicaciones de cada pantalla: la de los acordes, la del pentagrama y la de las reglas se abren de nuevo la próxima vez que pases por ellas.':
        'Runs the welcome walkthrough again and brings back the explanations '
        'for each screen: the chords one, the staff one and the rules one will '
        'open again the next time you pass through them.',
    'Vuelve esta pantalla a la configuración con la que arranca el estilo elegido.':
        'Returns this screen to the settings the chosen style starts out with.',
    'Weaver': 'Weaver',
    'Y acá se decide cómo suena': 'And this is where how it sounds is decided',
    'Y con eso ya se puede buscar': 'And with that it can start searching',
    'Y cuánto se le hace caso al estilo':
        'And how much the style gets listened to',
    'Y el generador te lo dio.': 'And the generator gave it to you.',
    'Y el piano, para lo que no tiene nombre':
        'And the piano, for what has no name',
    'Y esto es lo único que se negocia':
        'And this is the only thing that is negotiable',
    'Y modular es cambiarse de casa': 'And modulating is moving house',
    'Y si algo no se entiende, está en el libro':
        'And if something is not clear, it is in the book',
    'acordes de séptima por defecto': 'seventh chords by default',
    'amplitud': 'amplitude',
    'bajo → soprano:   {names}      ({value} sobre el bajo)':
        'bass → soprano:   {names}      ({value} over the bass)',
    'casi nunca': 'almost never',
    'distancia ×{motion:.2f}   ·   estilo ×{style:.2f}':
        'distance ×{motion:.2f}   ·   style ×{style:.2f}',
    'escribí o traé una partitura, y mirá qué está haciendo':
        'write or bring in a score, and see what it is doing',
    'fundamental: {reference:.0f} Hz': 'fundamental: {reference:.0f} Hz',
    'lo dejó quien estuvo mirando': 'left by whoever was watching',
    'mirá de qué está hecha una nota, y desarmala':
        'see what a note is made of, and take it apart',
    'máx. {MAX_BARS}': 'max. {MAX_BARS}',
    'no lo reconozco — probá el piano':
        'I do not recognize it — try the piano',
    'notas propias: {record}': 'custom notes: {record}',
    'omitiendo {value}': 'omitting {value}',
    'rango': 'range',
    'rango {note_name}–{note_name2}': 'range {note_name}–{note_name2}',
    'recién completado': 'just completed',
    'silencio — el AG no interviene': 'rest — the GA stays out of it',
    'sin color': 'no color',
    'sólo distancia': 'distance only',
    'sólo estilo': 'style only',
    'tríadas por defecto': 'triads by default',
    'título dorado': 'gilded title',
    'título: {title}': 'title: {title}',
    'vox principalis': 'vox principalis',
    '{count} nota(s) · {bars:.2g} compás(es)':
        '{count} note(s) · {bars:.2g} measure(s)',
    '{detail}, y {lower} sólo canta de {note_name} a {note_name2}. Elegí otra voz en «Mi voz es» o movela de octava.':
        '{detail}, and {lower} only sings from {note_name} to {note_name2}. '
        'Choose another voice in “My voice is” or move it an octave.',
    '{done} de {needed} tonalidades': '{done} of {needed} keys',
    '{done} de {total}': '{done} of {total}',
    '{done} de {total} conseguidos': '{done} of {total} earned',
    '{got} de {needed}': '{got} of {needed}',
    '{label} es la voz más grave del conjunto, así que no queda ninguna debajo para hacer de vox organalis. Elegí una voz más aguda.':
        '{label} is the lowest voice of the ensemble, so there is none left '
        'below to act as vox organalis. Choose a higher voice.',
    '{label} lleva el canto. La voz que quede inmediatamente debajo lo dobla en paralelo.':
        '{label} carries the chant. Whichever voice sits immediately below '
        'doubles it in parallel.',
    '{label} tiene que estar entre 0 y 1.':
        '{label} has to be between 0 and 1.',
    '{locked_text} ({done} de {needed}) y el piano se enciende.':
        '{locked_text} ({done} of {needed}) and the piano lights up.',
    '{name} no llega a {note_name}.': '{name} does not reach {note_name}.',
    '{n} de {total}': '{n} of {total}',
    '{record} notas y sólo {voice_keys} voces — {extra} no se va a escribir':
        '{record} notes and only {voice_keys} voices — {extra} will not be '
        'written',
    '{record} notas y sólo {voice_keys} voces — {extra} no se van a escribir':
        '{record} notes and only {voice_keys} voices — {extra} will not be '
        'written',
    '{selected} notas: {names}': '{selected} notes: {names}',
    '{tones} notas — entra': '{tones} notes — it fits',
    '{total:g}/{target:g} tiempos': '{total:g}/{target:g} beats',
    '{voice_keys} voces  ·  {voices}  ·  {time_signature}  ·  {bar_count} compases':
        '{voice_keys} voices  ·  {voices}  ·  {time_signature}  ·  {bar_count} '
        'measures',
    '{written} de {total} apartados escritos':
        '{written} of {total} sections written',
    '¡Agradecé que Bach está muerto!': 'Be glad Bach is dead!',
    '¡Ganaste la {ordinal} estrella!': 'You earned the {ordinal} star!',
    '¡Logro completado!': 'Achievement unlocked!',
    '¡Logro legendario!': 'Legendary achievement!',
    '«{value}» no es una nota válida. Usá C4, Bb3, F#5.':
        '“{value}” is not a valid note. Use C4, Bb3, F#5.',
    '·  {genre}': '·  {genre}',
    '¿Con qué reglas se escribe?': 'By what rules is it written?',
    '¿Cuánto dura y en qué compás?': 'How long is it and in what metre?',
    '¿De dónde saca los acordes?': 'Where does it get the chords from?',
    '¿Estás seguro?': 'Are you sure?',
    '¿Mejor así?': 'Better this way?',
    '¿Para qué diantres me necesitás entonces?':
        'What on earth do you need me for, then?',
    '¿Quién canta?': 'Who is singing?',
    '¿Quién elige los acordes?': 'Who chooses the chords?',
    '¿Qué te importa más?': 'What matters more to you?',
    'Ésta es la pantalla del Armonizador, y funciona al revés que las otras dos: no partís de acordes sino de una línea. Vos escribís la melodía y el programa busca qué acordes pueden sostenerla, sin tocarle ni una nota.\n\nTe muestro en medio minuto qué hace cada cosa. Podés omitirlo.':
        'This is the Harmonizer screen, and it works the other way round from '
        'the other two: you do not start from chords but from a line. You write '
        'the melody and the program looks for chords that can hold it up, '
        'without touching a single note of it.\n\nLet me show you in half a '
        'minute what everything does. You can skip it.',
    'Ésta es la pantalla del Generador, y es donde vos hacés tu trabajo: no escribís acordes, decidís de qué caja los puede sacar el programa.\n\nTodo viene con lo que suele usar el estilo que elegiste, así que si tocás sólo la tonalidad ya sale algo que suena. Te muestro qué hace cada cosa. Podés omitirlo.':
        'This is the Generator screen, and it is where you do your work: you do '
        'not write chords, you decide which box the program may take them '
        'from.\n\nEverything comes set to what the style you chose usually '
        'uses, so if you only touch the key you will already get something that '
        'sounds. Let me show you what everything does. You can skip it.',
    'Ésta es la pantalla del Organizador: vos ponés los acordes y el programa no los toca ni los reordena. Lo único que decide es qué nota de cada acorde canta cada voz y en qué octava.\n\nTe muestro en medio minuto qué hace cada cosa. Podés omitirlo.':
        'This is the Organizer screen: you bring the chords and the program '
        'neither touches nor reorders them. All it decides is which note of '
        'each chord each voice sings, and in which octave.\n\nLet me show you '
        'in half a minute what everything does. You can skip it.',
    'Ésta es la última pantalla antes de que el programa se ponga a buscar. Los acordes ya están; lo que se elige acá es con qué criterio se reparten entre las voces.\n\nTodo viene con los valores que deja el estilo que elegiste, así que si no tocás nada igual sale bien. Te muestro qué hace cada cosa.':
        'This is the last screen before the program starts searching. The '
        'chords are already there; what you choose here is by what criteria '
        'they are handed out among the voices.\n\nEverything comes set to the '
        'values the style you chose leaves behind, so if you touch nothing it '
        'still comes out well. Let me show you what everything does.',
    'Índice': 'Contents',
    'Últimas producciones': 'Latest productions',
    '— sin anotar todavía —': '— not written down yet —',
    '←  Atrás': '←  Back',
    '←  Volver': '←  Return',
    '→  {name}': '→  {name}',
    '★  Seguir': '★  Go on',
    '★  {label}': '★  {label}',
    '★  {label}{where} — {detail}': '★  {label}{where} — {detail}',
    '★  {title}': '★  {title}',
    '♥  Donar': '♥  Donate',
    '♪  Escuchá la línea…': '♪  Listen to the line…',
    '⟳  Resetear': '⟳  Reset',
    '📖  {locked}': '📖  {locked}',
    '🔒  Escuchá primero': '🔒  Listen first',
    '🔒  {locked}': '🔒  {locked}',
    '🖋  1 anotación nueva': '🖋  1 new note',
    '🖋  Se escribe solo': '🖋  It writes itself',
    '🖋  {fresh} anotaciones nuevas': '🖋  {fresh} new notes',
    '🖋  {fresh} anotación nueva': '🖋  {fresh} new note',
    '🖋  {pending} anotaciones nuevas': '🖋  {pending} new notes',
    '🥚  Ya no hay nada que esconder': '🥚  There is nothing left to hide',
    '🧟  GRAAAH…': '🧟  GRAAAH…',
}
