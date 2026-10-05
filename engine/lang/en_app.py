# -*- coding: utf-8 -*-
"""
La ventana principal en inglés: el carrusel, la configuración, el tutorial,
el libro, los logros y el sendero.

Las claves son las cadenas castellanas tal cual están escritas en `app.py`.
No se editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    # -- la pantalla inicial: herramientas y dibujos (homeart) ---------------
    'Herramientas': 'Tools',
    'Aprender escribiendo': 'Learning by writing',
    'Encendé, apagá y mové los armónicos de una nota y escuchá cómo cambia.':
        'Switch the harmonics of a note on and off, move them and hear what '
        'changes.',
    'Traés una partitura y te dice qué acorde es cada uno, qué función cumple y qué hacen las voces.':
        'Bring a score and it tells you each chord, what it does in the key '
        'and what the voices are doing.',
    'Cinco unidades con ejercicios de escritura que corrige el analizador.':
        'Five units of writing exercises, marked by the Analyzer.',
    'Tres lugares que no componen nada. El experimentador desarma una nota en sus armónicos, el analizador lee una partitura que traés y la escuelita te enseña con ejercicios que corrige el analizador.':
        'Three places that do not compose anything. The Workbench takes a '
        'note apart into its harmonics, the Analyzer reads a score you bring, '
        'and the Schoolhouse teaches you with exercises the Analyzer marks.',
    'VOS': 'YOU',
    'EL PROGRAMA': 'THE PROGRAM',
    'Do mayor': 'C major',
    '8 compases': '8 bars',
    'con préstamos': 'with borrowing',
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
    'Compás': 'Meter',
    'Obligatorio': 'Required',
    'Preferido': 'Preferred',
    'Libre': 'Free',
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
    'Partituras': 'Scores',
    'hoy {clock}': 'today {clock}',
    'ayer {clock}': 'yesterday {clock}',
    '{day} {month} {clock}': '{month} {day} {clock}',
    'ene': 'Jan',
    'feb': 'Feb',
    'mar': 'Mar',
    'abr': 'Apr',
    'may': 'May',
    'jun': 'Jun',
    'jul': 'Jul',
    'ago': 'Aug',
    'sep': 'Sep',
    'oct': 'Oct',
    'nov': 'Nov',
    'dic': 'Dec',
    'Organizador': 'Organizer',
    'Generador': 'Generator',
    'Armonizador': 'Harmonizer',
    'Experimentador': 'Workbench',
    'Coral': 'Chorale',
    'Historial · detalle': 'History · details',
    'Redonda': 'Whole',
    'Blanca': 'Half',
    'Negra c/punto': 'Dotted quarter',
    'Negra': 'Quarter',
    'Corchea c/punto': 'Dotted eighth',
    'Corchea': 'Eighth',
    'Redonda (4)': 'Whole (4)',
    'Blanca (2)': 'Half (2)',
    'Negra c/punto (1½)': 'Dotted quarter (1½)',
    'Negra (1)': 'Quarter (1)',
    'Corchea (1/2)': 'Eighth (1/2)',
    'Silencio Redonda (4)': 'Whole rest (4)',
    'Silencio Blanca (2)': 'Half rest (2)',
    'Silencio Negra c/punto (1½)': 'Dotted quarter rest (1½)',
    'Silencio Negra (1)': 'Quarter rest (1)',
    'Silencio Corchea (1/2)': 'Eighth rest (1/2)',
    'Partitura': 'Score',
    'Tabla': 'Table',
    '+ acorde': '+ chord',
    '♪  Sonando…': '♪  Playing…',
    'Los cifrados se deducen de las notas, así que puede haber inversiones de más o algún acorde con otro nombre. Revisalos antes de generar.':
        'The chord symbols are worked out from the notes, so there may be '
        'extra inversions or a chord under another name. Check them before '
        'generating.',
    '  ·  el último compás quedó incompleto':
        '  ·  the last measure came out incomplete',
    ' Hay {empty} casilla vacía que igual ocupa su duración. Escribí un acorde o borrala con la ✕.':
        ' There’s {empty} empty cell still taking up its duration. Write a '
        'chord in it or remove it with the ✕.',
    ' Hay {empty} casillas vacías que igual ocupan su duración. Escribí acordes o borralas con la ✕.':
        ' There are {empty} empty cells still taking up their duration. Write '
        'chords in them or remove them with the ✕.',
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
    'Acá ves cuánto llevás puesto y cuánto entra. Si sobra o falta, no se puede escribir la partitura, porque ningún editor de música acepta un compás que no suma lo que dice su cifra.\n\n«+ acorde» agrega otro acorde al compás y la ✕ lo saca.':
        'This shows how much you’ve filled and how much fits. If there’s too '
        'much or too little, the score can’t be written, since no music '
        'editor accepts a measure that doesn’t add up to its time signature.\n'
        '\n“+ chord” adds another chord to the measure and the ✕ removes one.',
    'Lo que importa es cómo pasan al acorde siguiente las dos notas que definen el color de cada acorde. El programa las conecta por el camino más corto y permite cosas que el barroco prohíbe. Los acordes son más densos y suenan más modernos.':
        'What matters is how the two notes that give each chord its color '
        'move into the next chord. The program connects them by the shortest '
        'path and allows things baroque forbids. The chords are denser and '
        'sound more modern.',
    'El programa arma la progresión sólo con lo que permitas acá.':
        'The program builds the progression only from what you allow here.',
    'Acá se dibuja la melodía': 'This is where you draw the melody',
    'Acá se elige el material': 'This is where the material is chosen',
    'Acá se escribe la progresión': 'This is where the progression is written',
    'Al lado de cada acorde va su duración. Las opciones que empiezan con «Silencio» dejan ese lugar sin sonar, y el programa lo respeta.':
        'Each chord’s duration goes next to it. The options that start with '
        '“Rest” leave that spot silent, and the program keeps it that way.',
    'Al pie de los logros están ahora los seis, con los pasos exactos para volver a provocarlos.':
        'All six are now at the foot of the achievements, with the exact steps '
        'to set them off again.',
    'Al apretar «Generar» arrancan doscientas soluciones al azar que se cruzan y mejoran durante trescientas generaciones. Tarda unos segundos y se puede cancelar.\n\nAl final ves las mejores. Como interviene el azar, dos corridas iguales dan resultados parecidos pero no idénticos.':
        'When you press “Generate”, two hundred random solutions start '
        'crossing and improving over three hundred generations. It takes a '
        'few seconds and can be canceled.\n\n'
        'At the end you see the best ones. Since chance is involved, two '
        'identical runs give similar but not identical results.',
    'Algo te está esperando en el {value}.':
        'Something is waiting for you in the {value}.',
    'Algoritmo genético': 'Genetic algorithm',
    'Algún valor no es un número válido.':
        'One of the values isn’t a valid number.',
    'Alias para transferir': 'Alias for bank transfer',
    'Analizador': 'Analyzer',
    'Anotaste lo que te dijeron': 'You wrote down what you were told',
    'Anotaste lo que viste': 'You wrote down what you saw',
    'Antes de hacer click, elegí acá cuánto dura la nota. La redonda es la más larga y la corchea la más corta. Las que dicen «c/punto» duran una vez y media.\n\n«Deshacer» (o Ctrl+Z) borra la última nota y «Borrar todo» empieza de cero. «Escuchar» toca lo que llevás escrito, todavía sin acordes.':
        'Before you click, choose how long the note lasts here. The whole '
        'note is the longest and the eighth note the shortest. The dotted '
        'ones last one and a half times as long.\n\n'
        '“Undo” (or Ctrl+Z) removes the last note and “Clear all” starts '
        'over. “Play” plays what you’ve written so far, still without chords.',
    'Aplicar': 'Apply',
    'Armadura': 'Key signature',
    'Armadura, compás y voz': 'Key signature, meter and voice',
    'Armonización': 'Harmonization',
    'Armonía extendida. Lo que importa es cómo pasan la tercera y la séptima de cada acorde al siguiente.':
        'Extended harmony. What matters is how the third and seventh of each '
        'chord move into the next.',
    'Armonía y contrapunto, desde cero.': 'Harmony and counterpoint, from scratch.',
    'Arranca con {voices} · {mode} · {sevenths}. Se puede cambiar en las pantallas siguientes.':
        'Starts with {voices} · {mode} · {sevenths}. You can change this on '
        'the next screens.',
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
    'Cada click pone una nota donde apuntaste. El pentagrama está en clave de sol, así que la línea de abajo es mi y cuanto más arriba, más agudo.\n\nLa nota respeta la armadura. Si la armadura tiene fa sostenido, un click en el fa escribe fa sostenido.':
        'Each click places a note where you point. The staff is in treble '
        'clef, so the bottom line is E, and the higher you go, the higher it '
        'sounds.\n\n'
        'Notes follow the key signature. If the signature has F sharp, '
        'clicking on F writes F sharp.',
    'Cuando generes una partitura, va a aparecer acá.':
        'Once you generate a score, it will show up here.',
    'La tónica se queda y el modo cambia a {listed}.':
        'The tonic stays and the mode changes to {listed}.',
    'Cancelar': 'Cancel',
    'Cantidad de voces distinta': 'Different number of voices',
    'Castiga saltos de tritono y de séptima':
        'Penalizes tritone and seventh leaps',
    'Cerrar': 'Close',
    'Chord': 'Chord',
    'ChordWeaver es gratis y va a seguir siéndolo. La música es de todos, y no me parece bien cobrar por una herramienta para estudiarla.':
        'ChordWeaver is free and will stay that way. Music belongs to '
        'everyone, and charging for a tool to study it doesn’t feel right to '
        'me.',
    'ChordWeaver {APP_VERSION}': 'ChordWeaver {APP_VERSION}',
    'En cifrado americano, por ejemplo Cmaj7, F#m7b5, Bb13 o C/G. Las duraciones de cada compás tienen que sumar exacto. Para un acorde sin nombre, usá el piano.':
        'In chord symbols, for example Cmaj7, F#m7b5, Bb13 or C/G. The '
        'durations in each measure have to add up exactly. For a chord '
        'without a name, use the piano.',
    'Cifrado barroco: los intervalos se cuentan desde el bajo. Un 6/5 es una séptima en primera inversión, o sea con la tercera abajo.':
        'Figured bass: the intervals are counted from the bass. A 6/5 is a '
        'seventh chord in first inversion, that is, with the third at the '
        'bottom.',
    'Click en el pentagrama': 'Click on the staff',
    'Hacé click en el pentagrama para poner cada nota, o usá el piano de abajo. El programa no cambia ninguna nota de tu melodía.':
        'Click on the staff to place each note, or use the piano below. The '
        'program won’t change any note of your melody.',
    'Cmaj7': 'Cmaj7',
    'Comenzarás tu camino otra vez.\n\nLo que ya conseguiste no se pierde: los logros, los títulos y lo que quedó escrito en el libro siguen siendo tuyos. Lo que vuelve a cero es el sendero.':
        'You will begin your road again.\n\nWhat you have already earned is not '
        'lost: the achievements, the titles and whatever was written down in '
        'the book are still yours. What goes back to zero is the path.',
    'Compases': 'Measures',
    'Completaste los {total} logros de la {ordinal} estrella.':
        'You completed all {total} achievements of the {ordinal} star.',
    'compás': 'measure',
    'bloqueado: {notes}': 'locked: {notes}',
    '«Siguiente» avanza y «Atrás» vuelve sin perder nada de lo que cargaste.\n\nEn el engranaje están la configuración, el tamaño de letra y el botón para volver a ver este tutorial.':
        '“Next” moves forward and “Back” goes back without losing anything '
        'you’ve entered.\n\n'
        'The gear has the settings, the text size and a button to see this '
        'tour again.',
    'Cuánto busca agregar novenas, oncenas o sextas en lugar de duplicar una nota.':
        'How hard it tries to add ninths, elevenths or sixths instead of '
        'doubling a note.',
    'Con qué empieza y con qué termina': 'What it starts and ends with',
    'Con qué frecuencia aparecen': 'How often they show up',
    'Con tarjeta, en el navegador': 'By card, in the browser',
    'Conecta las guide tones por grado conjunto':
        'Connects the guide tones by step',
    'Configuración y accesibilidad': 'Settings and accessibility',
    'Consonancia en los acordes de reposo': 'Consonance on resting chords',
    'Arma los acordes con cuatro notas en vez de tres, por ejemplo Cmaj7 en lugar de C. Es lo normal en jazz y la excepción en los otros estilos.':
        'Builds chords with four notes instead of three, for example Cmaj7 '
        'instead of C. Standard in jazz, the exception in the other styles.',
    'Copiado ✓': 'Copied ✓',
    'Copiar el alias': 'Copy the alias',
    'Copiar el enlace': 'Copy the link',
    'Coral al estilo de Bach. Es más estricto que el barroco, nunca duplica la sensible, resuelve las séptimas hacia abajo y cuida el espaciado entre voces.':
        'Bach-style chorale. It’s stricter than baroque, never doubles the '
        'leading tone, resolves sevenths downward and watches the spacing '
        'between voices.',
    'Cuando a un acorde le sobran voces, en vez de repetir una nota puede agregar una novena, una oncena o una sexta.':
        'When a chord has voices to spare, instead of repeating a note it can '
        'add a ninth, an eleventh or a sixth.',
    'Cuando una voz salta una tercera, queda una nota libre en el medio. La nota de paso la ocupa, y en vez de saltar de do a mi la voz hace do-re-mi.\n\nElegí qué voces pueden usarlas y cuántas. Se agregan **después** de repartir las voces, sobre la solución ya elegida.':
        'When a voice leaps a third, there’s a free note in between. A '
        'passing note fills it, so instead of jumping from C to E the voice '
        'goes C-D-E.\n\n'
        'Choose which voices can use them and how many. They’re added '
        '**after** the voices are laid out, on top of the chosen solution.',
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
    'Cuánto usarlos': 'How often to use them',
    'Cuántos candidatos compiten para ser padres. Más alto = más presión hacia los mejores, pero menos diversidad.':
        'How many candidates compete to become parents. Higher = more pressure '
        'toward the best, but less diversity.',
    'CÓMO CONSEGUIRLO': 'HOW TO EARN IT',
    'Cómo se hace cada uno': 'How each one is done',
    'De esas cruzas, qué fracción mezcla voz por voz (permite juntar un buen bajo con una buena soprano) en vez de cortar la progresión en un punto.':
        'Of those crossings, what fraction mixes voice by voice (letting a good '
        'bass join a good soprano) instead of cutting the progression at one '
        'point.',
    'De modo (misma tónica)': 'To another mode (same tonic)',
    'De qué está hecha una nota': 'What a note is made of',
    'Deja pasar paralelas y tritonos': 'Lets parallels and tritones through',
    'Deja que la melodía se apoye también en sextas, séptimas o novenas, y que los acordes agreguen color en vez de duplicar notas.':
        'Lets the melody lean on sixths, sevenths or ninths as well, and lets '
        'the chords add color instead of doubling notes.',
    'Deja que los adornos usen notas fuera de la escala. Suena más rico, pero probablemente haya que retocar alguno a mano, porque el programa no juzga si la nota cromática encaja.':
        'Lets ornaments use notes outside the scale. It sounds richer, but '
        'you’ll probably need to fix some by hand, since the program doesn’t '
        'judge whether a chromatic note fits.',
    'Deja usar el cuarto menor en lugar del IV o del V, y el séptimo rebajado justo antes del cierre.':
        'Allows the minor fourth in place of IV or V, and the flat seventh '
        'right before the close.',
    'Descarta cualquier disposición donde dos voces suenen a distancia de tritono. Prendido, no puede haber acordes de séptima de dominante, porque ese tritono es lo que los define.':
        'Discards any voicing where two voices sound a tritone apart. With it '
        'on, there can be no dominant seventh chords, since that tritone is '
        'what defines them.',
    'Descarta cualquier disposición donde dos voces suenen a distancia de tritono. Sirve sobre todo para que las notas de color añadidas no formen uno.':
        'Discards any voicing where two voices sound a tritone apart. It is '
        'mostly there to keep the added color notes from forming one.',
    'Desde Argentina': 'From Argentina',
    'Desde cualquier otro lado': 'From anywhere else',
    'Deshacer': 'Undo',
    'Dibujá la melodía': 'Draw the melody',
    'Donar': 'Donate',
    'Dos voces a distancia de quinta que se mueven juntas en la misma dirección y mantienen la quinta. Es la prohibición más conocida del contrapunto, porque las dos líneas se oyen como una sola.':
        'Two voices a fifth apart moving together in the same direction and '
        'keeping the fifth. It’s the best-known rule in counterpoint, because '
        'the two lines get heard as one.',
    'Son dos voces a distancia de quinta que se mueven juntas en la misma dirección y mantienen esa distancia. Es la prohibición más famosa del contrapunto, porque las dos líneas dejan de oírse como dos y se funden en una.\n\nApagarla no rompe nada. Hay estilos enteros que se basan en eso, como el gregoriano.':
        'Two voices a fifth apart moving together in the same direction and '
        'keeping that distance. It’s the most famous rule in counterpoint, '
        'because the two lines stop sounding like two and blend into one.\n\n'
        'Turning it off doesn’t break anything. Whole styles are built on it, '
        'like Gregorian chant.',
    'El acorde {label} «{roman}» no existe en esta tonalidad. Disponibles: {value}':
        'The {label} chord “{roman}” does not exist in this key. Available: '
        '{value}',
    'Prueba miles de repartos de voces y se queda con los mejores.':
        'It tries thousands of voicings and keeps the best ones.',
    'El alias queda copiado mientras el programa esté abierto. En Windows, el portapapeles depende de la aplicación que copió.':
        'The alias stays copied while the program is open. On Windows, the '
        'clipboard depends on the app that copied it.',
    'El botón «piano» de cada casilla abre un teclado para armar el acorde nota por nota. Sirve para los que el cifrado no puede nombrar, como un acorde por cuartas o un cluster.\n\nArriba a la izquierda, «Importar partitura» carga los acordes de un MusicXML con su ritmo.':
        'The “piano” button in each cell opens a keyboard to build the chord '
        'note by note. Use it for chords that symbols can’t name, like a '
        'quartal chord or a cluster.\n\n'
        'At the top left, “Import score” loads the chords from a MusicXML '
        'file, rhythm included.',
    'El camino se ha liberado': 'The road has been opened',
    'El candado fija las voces': 'The padlock fixes the voices',
    'El cifrado va acá': 'The chord symbol goes here',
    'El compás tiene que cerrar exacto': 'The measure has to add up exactly',
    'El compás {bar_index} suma {total:g} tiempos y necesita {quarters_per_bar:g}.{extra}':
        'Measure {bar_index} adds up to {total:g} beats and needs '
        '{quarters_per_bar:g}.{extra}',
    'El contrapunto de los corales y las invenciones de Bach. Es el más estricto de los tres, y con el modo coral se endurece todavía más.':
        'The counterpoint of Bach’s chorales and inventions. It’s the '
        'strictest of the three, and chorale mode makes it stricter still.',
    'El cruce de caminos, años después': 'The crossroads, years later',
    'El cruce de caminos, otra vez': 'The crossroads, again',
    'El elitismo no puede ser negativo.': 'Elitism cannot be negative.',
    'El elitismo tiene que ser menor que la población.':
        'Elitism has to be smaller than the population.',
    'El estilo decide cómo se pasa de un acorde al siguiente. Los acordes no cambian.\n\nEl barroco es el lenguaje de Bach y el más estricto de los tres. Prohíbe que dos voces se muevan en paralelo a ciertas distancias y premia que vayan en direcciones contrarias. Si estás empezando, es donde mejor se oye cuando algo sale mal.':
        'The style decides how you get from one chord to the next. The chords '
        'themselves don’t change.\n\n'
        'Baroque is Bach’s language and the strictest of the three. It '
        'forbids two voices from moving in parallel at certain intervals and '
        'rewards contrary motion. If you’re just starting out, it’s where '
        'mistakes are easiest to hear.',
    'El estilo decide cómo se mueven las voces de un acorde al siguiente. Cada regla se puede ajustar después, en la pantalla de reglas.':
        'The style decides how the voices move from one chord to the next. '
        'You can adjust each rule later on the rules screen.',
    'El programa es gratis. Esto es por si querés bancarlo igual.':
        'The program is free. This is in case you want to chip in anyway.',
    'El programa es gratis. Si querés bancarlo, acá te digo cómo.':
        'The program is free. If you’d like to support it, here’s how.',
    'El programa pone los acordes en los tiempos fuertes y dora las notas que caen ahí. Las notas que quedan en el medio suenan sobre el acorde anterior.\n\nPara poner un acorde en otra nota, prendé «Marcar notas» y tocala, o hacele click derecho. Lo mismo sirve para sacar uno que sobra.':
        'The program puts chords on the strong beats and gilds the notes that '
        'fall there. The notes in between sound over the previous chord.\n\n'
        'To put a chord on another note, switch on “Mark notes” and click it, '
        'or right-click it. The same works to remove a chord you don’t want.',
    'El rango de {label} no se entiende. Usá nombres tipo C4, Bb3, F#5.':
        'Can’t read the range for {label}. Use names like C4, Bb3, F#5.',
    'Son siete pantallas: modo, estilo, voces, compases, acordes, reglas y resultado. La barra se llena a medida que avanzás y toma el color del modo que elegiste.':
        'There are seven screens: mode, style, voices, measures, chords, '
        'rules and result. The bar fills up as you go and takes on the color '
        'of the mode you picked.',
    'Al comparar dos soluciones cuenta cuánto se mueven las voces y cuánto respetan el estilo. Acá decidís qué pesa más.':
        'When two solutions are compared, what counts is how much the voices '
        'move and how well they follow the style. Here you decide which '
        'weighs more.',
    'El sendero avanza': 'The path moves on',
    'El torneo tiene que ser de al menos 2.':
        'The tournament size has to be at least 2.',
    'Para cuando tenés una melodía. La escribís en el pentagrama, decís qué voz la canta y el programa busca los acordes y escribe las otras voces.':
        'For when you have a melody. You write it on the staff, say which '
        'voice sings it, and the program finds the chords and writes the '
        'other voices.',
    'Para cuando no tenés nada todavía. Elegís la tonalidad y cuánto se puede arriesgar, y el programa inventa la progresión y la escribe. Si nunca escribiste armonía, conviene empezar por acá.':
        'For when you have nothing yet. You pick the key and how adventurous '
        'it can get, and the program invents the progression and writes it '
        'out. If you’ve never written harmony, start here.',
    'Para cuando ya tenés la progresión escrita en cifrado, como C, Am, F, G. El programa no cambia los acordes ni su orden. Sólo decide qué nota canta cada voz.':
        'For when you already have the progression written in chord symbols, '
        'like C, Am, F, G. The program doesn’t change the chords or their '
        'order. It only decides which note each voice sings.',
    'Elegiste {chosen} voces. Tienen que ser entre 3 y 6.':
        'You picked {chosen} voices. It has to be between 3 and 6.',
    'Cada compás puede tener su propia métrica, y el cambio queda escrito en la partitura.':
        'Each measure can have its own time signature, and the change is '
        'written into the score.',
    'Elevar probabilidad de cadencias especiales':
        'Raise the odds of special cadences',
    'Empieza en': 'Starts on',
    'Se escribe en cifrado americano. La letra es la nota de base (C es do, D re, E mi, F fa, G sol, A la, B si) y lo que sigue dice de qué tipo es el acorde.\n\nC es do mayor, Cm do menor, C7 lleva séptima, Cmaj7 séptima mayor y C/G es do mayor con el sol en el bajo. Mientras escribís, debajo aparecen las notas del acorde o qué está mal.':
        'It’s written in chord symbols. The letter is the root and what '
        'follows says what kind of chord it is.\n\n'
        'C is C major, Cm is C minor, C7 adds a seventh, Cmaj7 a major '
        'seventh, and C/G is C major with G in the bass. As you type, the '
        'chord’s notes show up underneath, or what’s wrong with it.',
    'Se escriben en números romanos. I es el acorde de la tónica, V el del quinto grado y vi el del sexto. Las minúsculas son acordes menores.\n\nEmpezar y terminar en I hace que la pieza suene cerrada. Terminar en V la deja abierta, como una pregunta. «Obligatorio» se cumple siempre, «Preferido» se pesa contra todo lo demás y «Libre» deja elegir al programa.':
        'They’re written in roman numerals. I is the tonic chord, V the chord '
        'on the fifth degree and vi the one on the sixth. Lowercase means '
        'minor.\n\n'
        'Starting and ending on I makes the piece sound closed. Ending on V '
        'leaves it open, like a question. “Required” always holds, '
        '“Preferred” is weighed against everything else and “Free” lets the '
        'program choose.',
    'En {label} la nota grave tiene que ser menor que la aguda.':
        'In {label} the low note has to be lower than the high one.',
    'Entre 3 y 6 voces. Ninguna nota va a salir del rango de su voz. Si tus cantantes llegan más arriba o más abajo, cambiá los rangos.':
        'Between 3 and 6 voices. No note will go outside its voice’s range. '
        'If your singers reach higher or lower, change the ranges.',
    'Equipo modesto': 'Low-end computer',
    'Es anterior a la armonía tal como la conocemos. Las voces se mueven casi siempre a la nota vecina y evitan el tritono, el intervalo más tenso. Las paralelas sí se permiten, porque el canto medieval se basaba en ellas.':
        'It predates harmony as we know it. The voices almost always move to '
        'the neighboring note and avoid the tritone, the harshest interval. '
        'Parallels are allowed, since medieval chant was built on them.',
    'Escribí al menos una nota antes de seguir.':
        'Write at least one note before moving on.',
    'Escribí el acorde antes de bloquearlo.':
        'Write the chord before locking it.',
    'Escribí la progresión': 'Write the progression',
    'Escribí qué nota canta cada voz. El programa no va a cambiar este acorde, pero lo usa para mover los acordes vecinos.':
        'Write which note each voice sings. The program won’t change this '
        'chord, but it uses it to move the neighboring chords.',
    'Escritura modal, anterior a la tonalidad. Casi todo el movimiento es por grado conjunto y el resultado suena a canto llano más que a armonía.':
        'Modal writing, older than tonality. Almost all the motion is stepwise '
        'and the result sounds like plainchant more than like harmony.',
    'Escuchá lo que salió. Recién ahí se puede seguir.':
        'Listen to what came out. Only then can you go on.',
    'Eso es todo para empezar. Ahora vamos a los logros, porque acabás de ganar el primero.':
        'That’s all you need to get started. Now let’s go to the '
        'achievements, because you just earned your first one.',
    'La barra de progreso': 'The progress bar',
    'Esta máquina tiene {cpu_count} núcleos. La búsqueda usa {workers} proceso(s) y deja uno libre para que la ventana siga respondiendo.':
        'This computer has {cpu_count} cores. The search uses {workers} '
        'process(es) and leaves one free so the window stays responsive.',
    'Este estilo no ofrece ningún cambio de modo sobre la tónica que elegiste.':
        'This style offers no change of mode over the tonic you chose.',
    'Este estilo no viaja a otra tonalidad.':
        'This style does not travel to another key.',
    'Qué hace ChordWeaver': 'What ChordWeaver does',
    'Evita el tritono, saltado y entre voces':
        'Avoids the tritone, leapt and between voices',
    'Evita las novenas menores': 'Avoids minor ninths',
    'Evitar tritonos entre voces': 'Avoid tritones between voices',
    'Exigir (regla dura)': 'Require (hard rule)',
    'Experimentador de armónicos': 'Harmonics workbench',
    'Falta el acorde': 'Chord missing',
    'Falta un acorde en el compás {bar_index}.':
        'A chord is missing in measure {bar_index}.',
    'Fija qué nota canta cada voz en este acorde. El programa no lo cambia, pero lo tiene en cuenta para los acordes vecinos.':
        'Sets which note each voice sings in this chord. The program won’t '
        'change it, but it takes it into account for the neighboring chords.',
    'Generación {generation} de {total}   ·   mejor costo {best:.0f}':
        'Generation {generation} of {total}   ·   best cost {best:.0f}',
    'Generar': 'Generate',
    'Gracias por usarlo.': 'Thanks for using it.',
    'Gregorio · el organum': 'Gregory · the organum',
    'Guardar como…': 'Save as…',
    'Guardar en la carpeta del programa': 'Save in the program folder',
    'Género': 'Style',
    'Hace lo mismo que el click y agrega una nota al final de la línea, con la figura elegida arriba. Es más cómodo para las notas alteradas y las que quedan lejos del pentagrama.':
        'It does the same as clicking and adds a note at the end of the line, '
        'with the note value chosen above. It’s handier for accidentals and '
        'for notes far above or below the staff.',
    'Hasta un tercio de la barra sólo agrega sextas, el color más suave. Más arriba suma novenas y oncenas.':
        'Up to a third of the way it only adds sixths, the mildest color. '
        'Beyond that it adds ninths and elevenths too.',
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
    'Hay {voice_keys} voces. Si marcás más notas, algunas se omiten al escribir.':
        'There are {voice_keys} voices. If you pick more notes, some get left '
        'out when writing.',
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
    'Ir a los logros': 'Go to achievements',
    'LOGRO LEGENDARIO': 'LEGENDARY ACHIEVEMENT',
    'La armadura fija la tonalidad y qué notas van alteradas. El compás agrupa los tiempos y decide dónde caen los acordes.\n\nEn «Mi voz es» elegís qué voz escribiste. Suele ser la más aguda, pero si la melodía va abajo elegí el bajo y el programa escribe las otras encima.':
        'The key signature sets the key and which notes are altered. The '
        'meter groups the beats and decides where the chords land.\n\n'
        'In “My voice is” you pick which voice you wrote. It’s usually the '
        'highest, but if the melody is in the bass, pick bass and the program '
        'writes the others above it.',
    'La entidad': 'The entity',
    'La mayor / Fa# menor': 'A major / F# minor',
    'La melodía baja hasta {note_name}':
        'The melody goes down to {note_name}',
    'La melodía baja hasta {note_name} y sube hasta {note_name2}':
        'The melody goes down to {note_name} and up to {note_name2}',
    'La melodía sube hasta {note_name}': 'The melody goes up to {note_name}',
    'La nota más grave se toma como fundamental.':
        'The lowest note is taken as the root.',
    'La partitura tiene {voice_count} voces y elegiste {voice_keys}. Los acordes se cargan igual, repartidos entre tus voces. ¿Seguimos?':
        'The score has {voice_count} voices and you chose {voice_keys}. The '
        'chords will load anyway, spread across your voices. Continue?',
    'La pieza puede pasar a otra tonalidad o cambiar de modo sobre la misma tónica. Siempre vuelve al punto de partida antes de terminar.':
        'The piece can move to another key or change mode over the same '
        'tonic. It always comes back home before it ends.',
    'La población tiene que ser al menos 10 y las generaciones al menos 1.':
        'The population has to be at least 10 and the generations at least 1.',
    'La primera es la que eligió el programa. Las otras mueven peor las voces o ceden más en las reglas del estilo.':
        'The first is the program’s pick. The others move the voices less '
        'smoothly or give more ground on the style’s rules.',
    'La progresión se arma pesando lo que pide el estilo y lo que le conviene al movimiento de las voces. Este deslizador decide cuánto pesa el estilo.\n\nHacia «estricto» sale una progresión de manual, con cada función en su lugar. Hacia «flexible» aparecen giros que el estilo no usaría.':
        'The progression is built by weighing what the style asks for against '
        'what suits the voice leading. This slider sets how much the style '
        'counts.\n\n'
        'Toward “strict” you get a textbook progression, with every function '
        'in place. Toward “flexible” you get turns the style wouldn’t '
        'normally use.',
    'La proporción de cruce uniforme': 'The uniform crossover share',
    'La tasa de cruce': 'The crossover rate',
    'La tasa de mutación': 'The mutation rate',
    'La tónica es la nota que suena a casa, la que el oído espera al final. El modo dice qué escala se arma sobre ella, y de esa escala salen los siete acordes que puede usar el programa.\n\nJónico es el mayor de siempre y eólico el menor. Los otros cinco cambian una o dos notas de la escala. El dórico suena a folk, el frigio a música española y el lidio a banda de sonido.':
        'The tonic is the note that sounds like home, the one your ear '
        'expects at the end. The mode says which scale is built on it, and '
        'that scale gives the seven chords the program can use.\n\n'
        'Ionian is plain major and Aeolian is minor. The other five change '
        'one or two notes of the scale. Dorian sounds folky, Phrygian sounds '
        'Spanish and Lydian sounds like a film score.',
    'La visión del cruce de caminos': 'The vision of the crossroads',
    'Las apariciones que ya viste. Se repiten enteras, como la primera vez.':
        'The apparitions you’ve already seen. They play in full, like the '
        'first time.',
    'Las cadencias completas (la frigia, el ciclo de Vivaldi y el bajo cromático) aparecen casi la mitad de las veces que se dan las condiciones, en vez de una de cada diez.':
        'The full cadences (the Phrygian, the Vivaldi cycle and the chromatic '
        'bass) show up almost half the time the conditions are right, instead '
        'of one time in ten.',
    'Las diez últimas corridas, exportadas o no. El color de cada recuadro es el del modo que se usó.':
        'The last ten runs, exported or not. Each box is colored by the mode '
        'it was made with.',
    'Accidente': 'Accidental',
    'Con click derecho, o con «Marcar notas» prendido, ponés o sacás el acorde de una nota. Una nota naranja que sube un semitono lleva sola el dominante de la siguiente, y una que baja, el sustituto tritonal.':
        'Right-click, or switch on “Mark notes”, to add or remove a note’s '
        'chord. An orange note that rises a semitone automatically gets the '
        'dominant of the next note, and one that falls gets the tritone '
        'substitute.',
    'Con click derecho, o con «Marcar notas» prendido, ponés o sacás el acorde de una nota. Una nota naranja que sube un semitono lleva sola el dominante de la siguiente.':
        'Right-click, or switch on “Mark notes”, to add or remove a note’s '
        'chord. An orange note that rises a semitone automatically gets the '
        'dominant of the next note.',
    'La próxima nota que escribas con el mouse lleva este accidente. Vale para una sola nota. Tocalo otra vez para quitarlo.':
        'The next note you write with the mouse gets this accidental. It '
        'applies to one note only. Click it again to clear it.',
    'fuera de la escala': 'outside the scale',
    'fuera de la escala, con acorde': 'outside the scale, with a chord',
    'lleva acorde': 'carries a chord',
    'Las mejores soluciones': 'The best solutions',
    'Las mismas reglas, con mucho más peso. Salta menos (3 semitonos en vez de 4), castiga el doble duplicar la sensible, exige que resuelvan las séptimas y no tolera voces solapadas.':
        'The same rules, weighted much more heavily. It leaps less (3 '
        'semitones instead of 4), penalizes doubling the leading tone twice '
        'as hard, requires sevenths to resolve and doesn’t allow overlapping '
        'voices.',
    'Las mismas tres opciones, tal como quedaron guardadas.':
        'The same three options, exactly as they were saved.',
    'Las notas de paso': 'Passing notes',
    'Las notas doradas llevan acorde': 'The gilded notes carry a chord',
    'Las voces quedan cruzadas. Cada una tiene que estar por encima de la anterior.':
        'The voices cross. Each one has to be above the previous one.',
    'Le pediste todo, a la vez, al máximo.':
        'You asked it for everything, at once, at the maximum.',
    'Carga los acordes de un MusicXML con su ritmo. El programa puede reacomodar las voces, salvo en los acordes con candado.':
        'Loads the chords from a MusicXML file, rhythm included. The program '
        'may rearrange the voices, except in padlocked chords.',
    'Carga una melodía de un MusicXML. Toma la nota más aguda de cada momento, así que sirve aunque la partitura tenga varias voces.':
        'Loads a melody from a MusicXML file. It takes the highest note at '
        'each moment, so it works even if the score has several voices.',
    'Legendarios': 'Legendary',
    'Libro de teoría': 'Theory book',
    'Listo. La búsqueda va a tardar más o menos la mitad, pero afina menos y vas a oír un poco más de movimiento entre acordes.':
        'Done. The search will take about half as long, but it refines less, '
        'so you’ll hear a bit more movement between chords.',
    'Lo mismo que las quintas paralelas pero a distancia de octava o unísono. Suena todavía más fusionado, así que en la práctica común está igual de prohibido.':
        'The same as parallel fifths but at the octave or the unison. It sounds '
        'even more fused, so in common practice it is just as forbidden.',
    'Logros': 'Achievements',
    'Los acordes prestados': 'Borrowed chords',
    'Los encontraste todos. Tocá el huevo.': 'You found them all. Touch the egg.',
    'Los siete grados de la escala son el material básico. Un intercambio modal trae un acorde del modo paralelo (el menor sobre la misma tónica, o al revés) sin cambiar de tonalidad.\n\nDe ahí salen muchos colores modernos, como un cuarto grado menor en una pieza mayor o un séptimo bemol antes del final. El deslizador de abajo regula cuánto los usa.':
        'The seven degrees of the scale are the basic material. Modal '
        'interchange brings in a chord from the parallel mode (minor on the '
        'same tonic, or the other way around) without changing key.\n\n'
        'That’s where a lot of modern color comes from, like a minor iv in a '
        'major piece or a flat VII right before the end. The slider below '
        'sets how often it uses them.',
    'Arranca con los valores del estilo {label}. Pasá el mouse por cada opción para ver qué hace.':
        'It starts with the {label} style’s values. Hover over each option to '
        'see what it does.',
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
    'Se mide desde el bajo, como en el bajo cifrado. En un 3-5-1 el bajo canta la tercera y los intervalos son de 3ra y 6ta, los dos consonantes. La última opción la vuelve regla dura.':
        'Measured from the bass, as in figured bass. In a 3-5-1 the bass '
        'sings the third, and the intervals are a 3rd and a 6th, both '
        'consonant. The last option makes it a hard rule.',
    'Melodía': 'Melody',
    'Melodía importada': 'Melody imported',
    'Mi voz es': 'My voice is',
    'Encendido, cada click en el pentagrama pone o saca el acorde de una nota en vez de escribirla. También sirve para las que doró el programa.':
        'While it’s on, each click on the staff adds or removes a note’s '
        'chord instead of writing a note. It also works on the notes the '
        'program gilded.',
    'Mirá qué te falta': 'See what’s left',
    'Modo coral': 'Chorale mode',
    'Modulaciones': 'Modulations',
    'Modular es pasar a otra tonalidad en el medio de la pieza y volver antes del final. A diferencia de un préstamo, por un rato la pieza gira alrededor de otra nota.\n\nPara ir y volver hace falta espacio, así que con menos de ocho compases queda desactivado. El deslizador de abajo regula cuánto se aleja.':
        'Modulating means moving to another key in the middle of the piece '
        'and coming back before the end. Unlike a borrowed chord, the piece '
        'actually centers on another note for a while.\n\n'
        'Going and coming back takes room, so with fewer than eight measures '
        'it’s turned off. The slider below sets how far it goes.',
    'MusicXML y MIDI': 'MusicXML and MIDI',
    'Métrica base': 'Base meter',
    'Hacen falta al menos 8 compases para asentar la tonalidad, irse y volver. Ahora hay {bar_count}.':
        'It takes at least 8 measures to establish the key, leave and come '
        'back. Right now there are {bar_count}.',
    'Ninguna nota seleccionada': 'No note selected',
    'No entiendo ese acorde: {exc}': 'I do not understand that chord: {exc}',
    'No golpeó la puerta, no hizo ruido y no se fue. Vas a tener que atender vos.':
        'It did not knock, it made no noise and it did not leave. You are going '
        'to have to answer.',
    'Donar no cambia nada en el programa. No hay funciones bloqueadas.':
        'Donating doesn’t change anything in the program. Nothing is locked '
        'behind it.',
    'Se desbloquean solos mientras trabajás, muchas veces por algo que hiciste sin darte cuenta. Valen de una a tres estrellas según la dificultad.':
        'They unlock on their own as you work, often for something you did '
        'without noticing. They’re worth one to three stars depending on '
        'difficulty.',
    'No se encontró solución': 'No solution found',
    'No se llega a leer de quién es, ni de qué.':
        'You cannot quite read whose it is, or what it is about.',
    'No se pudo': 'Could not',
    'No se pudo escribir la pieza': 'The piece could not be written',
    'Con el candado le decís qué nota canta cada voz en ese acorde, y el programa ya no lo cambia. Los acordes vecinos se acomodan alrededor del que fijaste.':
        'With the padlock you set which note each voice sings in that chord, '
        'and the program won’t change it. The neighboring chords arrange '
        'themselves around the one you fixed.',
    'Notas de paso': 'Passing notes',
    'Nuevo': 'New',
    'O el piano, si el pentagrama te cuesta':
        'Or the piano, if the staff is hard going',
    'Omitir': 'Skip',
    'Opción {position}': 'Option {position}',
    'Opción {position}  ·  {label}': 'Option {position}  ·  {label}',
    'Organum. Marcá la voz que lleva el canto (vox principalis). La de abajo va a ser la vox organalis y la va a seguir en paralelo, a la cuarta, la quinta o la octava. No puede ser la más grave, porque necesita una voz debajo.':
        'Organum. Mark the voice that carries the chant (vox principalis). '
        'The one below becomes the vox organalis and follows it in parallel '
        'at the fourth, fifth or octave. It can’t be the lowest voice, since '
        'it needs one underneath.',
    'Parámetros': 'Rules',
    'Paso {index} de {screens} · {screen_titles}':
        'Step {index} of {screens} · {screen_titles}',
    'Pediste {asked}, pero el máximo son {MAX_BARS} compases.':
        'You asked for {asked}, but the maximum is {MAX_BARS} measures.',
    'Permite organum a la 4ta, la 5ta y la 8va':
        'Allows organum at the 4th, the 5th and the 8ve',
    'Permitir cromáticas': 'Allow chromatic notes',
    'Permitir intercambios modales': 'Allow modal interchange',
    'Permitir voicings especiales': 'Allow special voicings',
    'Pero el proyecto lleva tiempo y mantenerlo cuesta. Si te sirvió y querés ayudar, una donación se agradece mucho.':
        'But the project takes time and keeping it going costs money. If it’s '
        'been useful to you and you’d like to help, a donation is much '
        'appreciated.',
    'Peso de la armonía frente a la conducción de voces':
        'Harmony versus voice leading',
    'Población': 'Population',
    'Cruza uniforme': 'Uniform crossover',
    'Elitismo': 'Elitism',
    'Generaciones': 'Generations',
    'Cada uno puede ser libre, preferido u obligatorio. Obligatorio deja un solo acorde posible en ese lugar.':
        'Each one can be free, preferred or required. Required leaves only '
        'one possible chord in that spot.',
    'El programa pone los acordes': 'The program brings the chords',
    'Por ejemplo, las quintas paralelas': 'Parallel fifths, for example',
    'Premia el movimiento contrario': 'Rewards contrary motion',
    'Premiar apenas': 'Reward slightly',
    'Premiar fuerte': 'Reward strongly',
    'Las reglas de la izquierda son duras. Si una está prendida, se descarta cualquier reparto que la rompa, aunque sea bueno en todo lo demás. Por eso una regla prendida nunca aparece rota en el resultado.\n\nPasá el mouse por cada una para ver qué significa.':
        'The rules on the left are hard rules. If one is on, any voicing that '
        'breaks it is thrown out, however good it is otherwise. That’s why a '
        'rule that’s on never shows up broken in the result.\n\n'
        'Hover over each one to see what it means.',
    'Preparando…': 'Getting ready…',
    'Prob. de cruza': 'Crossover prob.',
    'Probabilidad de combinar dos padres. Es lo que más mueve la búsqueda, porque junta tramos enteros de buena conducción de voces, y por eso va bastante más alta que la mutación.':
        'Probability of combining two parents. It drives most of the search, '
        'since it joins whole stretches of good voice leading, which is why '
        'it’s set much higher than mutation.',
    'Probabilidad de que una nota cambie de octava o pase a otra nota del acorde. Sirve para ajustes finos.':
        'Probability that a single note changes octave or moves to another '
        'chord tone. It’s for fine adjustments.',
    'Probá aflojar alguna regla en la pantalla anterior o ampliar los rangos de las voces.':
        'Try loosening a rule on the previous screen or widening the voice '
        'ranges.',
    'Producción': 'Production',
    'Prohibir cruce de voces': 'Forbid voice crossing',
    'Prohibir octavas paralelas': 'Forbid parallel octaves',
    'Prohibir quintas paralelas': 'Forbid parallel fifths',
    'Prohibir tritono melódico': 'Forbid the melodic tritone',
    'Que una voz cante más agudo que la voz que tiene arriba (por ejemplo el tenor por encima del alto). Confunde al oído sobre qué línea es cuál. Conviene dejarlo prendido salvo en texturas muy densas de 5 o 6 voces.':
        'A voice singing higher than the voice above it (the tenor above the '
        'alto, for instance). It confuses the ear about which line is which. '
        'Best left on except in very dense textures of 5 or 6 voices.',
    'Que una voz salte un tritono, es decir tres tonos de una vez (por ejemplo de fa a si). Es un intervalo áspero y difícil de cantar, y los estilos antiguos lo evitan.':
        'A voice leaping a tritone, that is, three whole steps at once (from '
        'F to B, for example). It’s a harsh interval, hard to sing, and older '
        'styles avoid it.',
    'Quitar candado': 'Unlock',
    'Si algo no se entiende, ahí está explicado desde cero, desde qué es un acorde hasta por qué una cadencia suena a final. Se va completando a medida que usás el programa.':
        'If something isn’t clear, it’s explained there from scratch, from '
        'what a chord is to why a cadence sounds final. It fills in as you '
        'use the program.',
    'Qué figura estás escribiendo': 'Which note value you are writing',
    'Re mayor / Si menor': 'D major / B minor',
    'Recorrido hasta el final.': 'Walkthrough seen all the way through.',
    'Recorta las generaciones para una máquina lenta, y la búsqueda tarda la mitad. Se siguen cumpliendo todas las reglas duras, pero queda menos tiempo para pulir la conducción de voces. La población no cambia, porque bajándola las piezas largas dejan de generarse.':
        'Cuts the generations for a slow computer, so the search takes half '
        'as long. All the hard rules still hold, but there’s less time to '
        'polish the voice leading. The population stays the same, because '
        'lowering it stops long pieces from generating at all.',
    'Recuerdo de {lower}.': 'A memento of {lower}.',
    'Reglas duras': 'Hard rules',
    'Ajustá las reglas': 'Adjust the rules',
    'Rellenan un salto de tercera con movimiento por grado conjunto. Elegí qué voces pueden usarlas.':
        'They fill a leap of a third with stepwise motion. Choose which voices '
        'may use them.',
    'Toca la melodía sola, antes de armonizarla.':
        'Plays the melody alone, before harmonizing it.',
    'Toca la primera opción tal como quedó guardada.':
        'Plays the first option as it was saved.',
    'Reproduce los acordes en orden con un sonido simple, respetando sus duraciones. Las notas de adorno no se incluyen.':
        'Plays the chords in order with a plain sound, respecting their '
        'durations. Ornamental notes are not included.',
    'Restaurar valores por defecto': 'Restore defaults',
    'Se abrió la lista de los huevos': 'The list of eggs has opened',
    'Se aplica al instante. Lo que ya generaste no cambia, porque los acordes se escriben igual en los dos idiomas.':
        'Takes effect right away. What you’ve already generated stays the '
        'same, since chords are written the same in both languages.',
    'Se aplica al reabrir el programa. La configuración se guarda junto al ejecutable.':
        'Takes effect when you restart the program. Settings are saved next '
        'to the executable.',
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
    'Sobran {extra}. Hay {voice_keys} voces, así que {extra2} de estas notas no se van a escribir.':
        '{extra} too many. There are {voice_keys} voices, so {extra2} of '
        'these notes won’t be written.',
    'Termina en': 'Ends on',
    'Tocá la tecla dorada del piano para seguir.':
        'Play the gilded key on the piano to go on.',
    'Tocá las teclas que forman el acorde':
        'Play the keys that make up the chord',
    'Todavía ninguno.': 'None yet.',
    'Todavía no cargaste ningún acorde.':
        'You haven’t entered any chords yet.',
    'Todavía no hay nada guardado': 'Nothing has been saved yet',
    'Todo lo que no es una regla dura se compara entre sí, y este deslizador decide el balance.\n\nHacia la izquierda pesa que las voces se muevan lo menos posible, y el resultado sale suave y previsible. Hacia la derecha pesa el estilo (espaciado, movimiento contrario, tesitura), y las voces se mueven más a cambio de sonar más idiomáticas. En el medio pesan igual.':
        'Everything that isn’t a hard rule gets weighed against everything '
        'else, and this slider sets the balance.\n\n'
        'Toward the left, what counts is moving the voices as little as '
        'possible, and the result is smooth and predictable. Toward the '
        'right, what counts is the style (spacing, contrary motion, range), '
        'and the voices move more in exchange for sounding more idiomatic. In '
        'the middle they weigh the same.',
    'Tolera las paralelas perfectas': 'Tolerates perfect parallels',
    'Tonalidad': 'Key',
    'Tonalidad y modo': 'Key and mode',
    'Incluye el modo coral, más estricto':
        'Includes the stricter chorale mode',
    'Tramo {step} de {total}  ·  en el {where}':
        'Stage {step} of {total}  ·  in the {where}',
    'TÍTULO SECRETO': 'SECRET TITLE',
    'Título obtenido: {SECRET_TITLE}.': 'Title earned: {SECRET_TITLE}.',
    'Título obtenido: {TRIUMPH_TITLE}': 'Title earned: {TRIUMPH_TITLE}',
    'Título obtenido: {title}': 'Title earned: {title}',
    'Títulos': 'Titles',
    'Un acorde de reposo suena cerrado cuando sus intervalos con el bajo son consonantes. Acá elegís cuánto le importa eso al programa, desde ignorarlo hasta exigirlo como regla dura.\n\nSi los finales te suenan abiertos, subilo.':
        'A resting chord sounds closed when its intervals over the bass are '
        'consonant. Here you choose how much the program cares about that, '
        'from ignoring it to requiring it as a hard rule.\n\n'
        'If your endings sound open, turn it up.',
    'Una progresión de acordes dice qué notas suenan juntas, pero no qué voz canta cada una. ChordWeaver reparte las notas de cada acorde entre las voces para que se muevan lo menos posible y no choquen entre sí.\n\nEste recorrido dura un minuto. Podés saltearlo cuando quieras.':
        'A chord progression tells you which notes sound together, but not '
        'which voice sings each one. ChordWeaver hands out the notes of each '
        'chord among the voices so they move as little as possible and don’t '
        'collide.\n\n'
        'This tour takes a minute. You can skip it at any time.',
    'Una solución que rompa una regla prendida se descarta.':
        'A solution that breaks a rule that is switched on is discarded.',
    'Usar estas notas': 'Use these notes',
    'Ver detalle': 'See details',
    'Ver el tutorial otra vez': 'See the tutorial again',
    'Pasa a otra tonalidad ({listed}) y vuelve.':
        'Moves to another key ({listed}) and comes back.',
    'Voicing fijo para {symbol}': 'Fixed voicing for {symbol}',
    'Volver a ver': 'See it again',
    'Volver al principio': 'Back to the start',
    'Vos ponés la melodía': 'You bring the melody',
    'Vos ponés los acordes': 'You bring the chords',
    'Vos traés la partitura': 'You bring the score',
    'Repite el recorrido de bienvenida. Las guías de los acordes, del pentagrama y de las reglas vuelven a abrirse la próxima vez que llegues a esas pantallas.':
        'Replays the welcome tour. The guides for the chords, the staff and '
        'the rules will open again the next time you reach those screens.',
    'Vuelve esta pantalla a los valores del estilo elegido.':
        'Resets this screen to the chosen style’s values.',
    'Weaver': 'Weaver',
    'La última pantalla antes de buscar': 'The last screen before searching',
    'Cuánto manda el estilo': 'How much the style counts',
    'Y el generador te lo dio.': 'And the generator gave it to you.',
    'El piano, para acordes sin nombre':
        'The piano, for chords without a name',
    'Balance': 'Balance',
    'acordes de séptima por defecto': 'seventh chords by default',
    'amplitud': 'amplitude',
    'bajo → soprano:   {names}      ({value} sobre el bajo)':
        'bass → soprano:   {names}      ({value} over the bass)',
    'casi nunca': 'almost never',
    'estilo estricto': 'strict style',
    'estilo flexible': 'flexible style',
    'muchas': 'many',
    'pocas': 'few',
    'muy seguido': 'very often',
    'distancia ×{motion:.2f}   ·   estilo ×{style:.2f}':
        'distance ×{motion:.2f}   ·   style ×{style:.2f}',
    'escribí o importá una partitura para analizarla':
        'write or import a score to analyze it',
    'fundamental: {reference:.0f} Hz': 'fundamental: {reference:.0f} Hz',
    'lo dejó quien estuvo mirando': 'left by whoever was watching',
    'apagá, subí o desafiná los armónicos de una nota':
        'mute, boost or detune the harmonics of a note',
    'máx. {MAX_BARS}': 'max. {MAX_BARS}',
    'no lo reconozco, probá con el piano': 'not recognized, try the piano',
    'notas propias: {record}': 'custom notes: {record}',
    'omitiendo {value}': 'omitting {value}',
    'rango': 'range',
    'rango {note_name}–{note_name2}': 'range {note_name}–{note_name2}',
    'recién completado': 'just completed',
    'silencio, no suena nada': 'rest, nothing plays',
    'sin color': 'no color',
    'mucho': 'a lot',
    'mucho color': 'lots of color',
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
    '{label} lleva el canto. La voz de abajo lo dobla en paralelo.':
        '{label} carries the chant. The voice below doubles it in parallel.',
    '{label} tiene que estar entre 0 y 1.':
        '{label} has to be between 0 and 1.',
    '{locked_text} ({done} de {needed}) y el piano se enciende.':
        '{locked_text} ({done} of {needed}) and the piano lights up.',
    '{name} no llega a {note_name}.': '{name} can’t reach {note_name}.',
    '{n} de {total}': '{n} of {total}',
    '{record} notas para {voice_keys} voces · {extra} no se va a escribir':
        '{record} notes for {voice_keys} voices · {extra} won’t be written',
    '{record} notas para {voice_keys} voces · {extra} no se van a escribir':
        '{record} notes for {voice_keys} voices · {extra} won’t be written',
    '{selected} notas: {names}': '{selected} notes: {names}',
    '{tones} notas · entra': '{tones} notes · fits',
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
    'Elegí un estilo': 'Choose a style',
    'Elegí el compás y el largo': 'Choose the meter and length',
    'Elegí la tonalidad y los acordes': 'Choose the key and the chords',
    '¿Estás seguro?': 'Are you sure?',
    '¿Mejor así?': 'Better this way?',
    '¿Para qué diantres me necesitás entonces?':
        'What on earth do you need me for, then?',
    'Elegí las voces': 'Choose the voices',
    'Elegí un modo': 'Choose a mode',
    'En el Armonizador se parte de una melodía y no de acordes. Vos la escribís y el programa busca acordes que le queden, sin cambiarle ninguna nota.\n\nTe muestro qué hace cada cosa en medio minuto. Podés omitirlo.':
        'In the Harmonizer you start from a melody instead of chords. You '
        'write it, and the program looks for chords that fit without changing '
        'a single note.\n\n'
        'I’ll show you what everything does in half a minute. You can skip '
        'it.',
    'En el Generador no escribís acordes. Elegís de dónde los puede sacar el programa.\n\nTodo arranca con lo que suele usar el estilo elegido, así que cambiando sólo la tonalidad ya sale algo que suena bien. Te muestro qué hace cada cosa. Podés omitirlo.':
        'In the Generator you don’t write chords. You choose where the '
        'program can take them from.\n\n'
        'Everything starts with what the chosen style usually uses, so '
        'changing just the key already gives you something that sounds good. '
        'I’ll show you what everything does. You can skip it.',
    'Vos ponés los acordes y el programa decide qué nota canta cada voz y en qué octava. Los acordes y su orden no se tocan.\n\nTe muestro qué hace cada cosa en medio minuto. Podés omitirlo.':
        'You bring the chords, and the program decides which note each voice '
        'sings and in which octave. The chords and their order stay as they '
        'are.\n\n'
        'I’ll show you what everything does in half a minute. You can skip '
        'it.',
    'Los acordes ya están. Acá elegís con qué criterio se reparten entre las voces.\n\nTodo arranca con los valores del estilo elegido, así que si no tocás nada igual sale bien. Te muestro qué hace cada cosa.':
        'The chords are set. Here you choose the criteria for spreading them '
        'among the voices.\n\n'
        'Everything starts with the chosen style’s values, so it works fine '
        'even if you don’t touch anything. I’ll show you what everything '
        'does.',
    'Índice': 'Contents',
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

    # -- configuración: el timbre de las reproducciones -----------------------
    'Sonido': 'Sound',
    'Timbre': 'Timbre',
    '▶  Probar': '▶  Try it',
    'Cargar un WAV…': 'Load a WAV…',
    'Elegí el timbre': 'Choose the timbre',
    'Sonido WAV': 'WAV sound',
    'No se pudo usar el timbre': 'Couldn’t use the timbre',
    'El timbre de todo lo que toca el programa, desde los resultados hasta el analizador. Todos suenan igual de fuerte y sólo cambia el color.':
        'The timbre for everything the program plays, from the results to the '
        'analyzer. They all play at the same volume. Only the color changes.',
    'No se pudo usar el timbre guardado y suena el de siempre.\n{reason}':
        'The saved timbre could not be used, so the usual one is playing.\n'
        '{reason}',
    'Un timbre guardado con «Guardar timbre…» en el experimentador ya sabe qué nota es y qué tramo repetir, y suena afinado en todo el teclado. Cualquier otro WAV también sirve. En ese caso el programa deduce la nota escuchándolo y repite su segunda mitad.':
        'A timbre saved with “Save timbre…” in the harmonics workbench '
        'already knows its note and which stretch to loop, so it plays in '
        'tune across the keyboard. Any other WAV works too. In that case the '
        'program works out the note by ear and loops its second half.',
    '{name} · es un {note} · repite {seconds:.1f} s':
        '{name} · it is a {note} · loops {seconds:.1f} s',
    '{name} · suena como un {note} (deducido oyéndolo) · repite su segunda mitad':
        '{name} · sounds like a {note} (worked out by ear) · loops its second '
        'half',

    # -- la pantalla de voces: los atajos ------------------------------------
    'Atajos': 'Presets',
    'Canto (SATB)': 'Choir (SATB)',
    'Piano': 'Piano',
    'Cuarteto de cuerdas': 'String quartet',
    'Coro a cuatro voces con los ámbitos de manual: soprano do4–sol5, contralto sol3–re5, tenor do3–sol4, bajo mi2–do4.':
        'Four-part choir with the textbook ranges: soprano C4–G5, alto '
        'G3–D5, tenor C3–G4, bass E2–C4.',
    'Cuatro voces de teclado, con más registro que un coro. Bajo do2–do4, tenor sol2–sol4, contralto re3–re5, soprano sol3–do6.':
        'Four keyboard voices, with a wider range than a choir. Bass C2–C4, '
        'tenor G2–G4, alto D3–D5, soprano G3–C6.',
    'Violonchelo do2–mi4, viola do3–do5, segundo violín sol3–mi5 y primer violín sol3–la5: cada uno desde su cuerda más grave.':
        'Cello C2–E4, viola C3–C5, second violin G3–E5 and first violin '
        'G3–A5: each one from its lowest string.',
}
