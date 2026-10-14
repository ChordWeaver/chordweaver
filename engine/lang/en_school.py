# -*- coding: utf-8 -*-
"""
La escuelita en inglés: las lecciones, los ejercicios, la corrección, la
pantalla, la entrada del libro que la escuelita necesitaba y la graduación.

Las claves son las cadenas castellanas tal cual están en el código. No se
editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    'El 3º': 'The 3rd',
    'El 5º': 'The 5th',
    'El 7º': 'The 7th',
    'El 8º': 'The 8th',
    # -- la tarjeta y la pantalla --------------------------------------------
    'Escuelita': 'Schoolhouse',
    'ejercicios de escritura corregidos por el analizador':
        'writing exercises checked by the analyzer',
    '{voice}: {note}': '{voice}: {note}',
    'Corregir': 'Check',
    'Click escribe una redonda en la voz elegida, click derecho borra y Tab cambia de voz.':
        'Click writes a whole note in the chosen voice, right-click erases '
        'and Tab switches voice.',
    'Graduación': 'Graduation',
    '{title} · se abre al aprobar las anteriores':
        '{title} · opens once you pass the ones before it',
    '✓  Aprobado': '✓  Passed',
    'c. {bar}→{until}': 'm. {bar}→{until}',
    'UNIDAD {numeral} · {title}': 'UNIT {numeral} · {title}',
    'EJERCICIO {n} DE {total}': 'EXERCISE {n} OF {total}',
    '{voice} del compás {bar} ya viene dado. Escribí en las otras voces.':
        'The {voice} in measure {bar} is given. Write in the other voices.',
    'Este fragmento es para mirar. La respuesta se elige abajo.':
        'This passage is just for looking. Pick the answer below.',
    'Empezar de nuevo': 'Start over',
    'Todavía no hay nada escrito para escuchar.':
        'Nothing is written yet to listen to.',
    'La partitura aparece cuando contestes.':
        'The score appears once you answer.',
    'Abrir el experimentador  →': 'Open the workbench  →',
    'DEL LIBRO · CAPÍTULO {numeral}': 'FROM THE BOOK · CHAPTER {numeral}',
    '✓  Bien': '✓  Right',
    '✗  Todavía no': '✗  Not yet',
    'y {count} más.': 'and {count} more.',
    'Abrir en el libro  →': 'Open in the book  →',
    'corregí y volvé a apretar «Corregir»':
        'fix it and press “Check” again',

    # -- el logro ------------------------------------------------------------
    'Nace una leyenda': 'A Legend Is Born',
    'Aprobá las ocho unidades de la **escuelita**.':
        'Pass all eight units of the **schoolhouse**.',

    # -- la entrada del libro sobre las inversiones --------------------------
    'Qué nota va en el bajo': 'Which note goes in the bass',
    'Un acorde no cambia de nombre por cómo se reparten sus notas: do-mi-sol es do mayor esté donde esté cada una. Lo que sí cambia, y mucho, es cuál de las tres queda abajo de todo, en el bajo.':
        'A chord does not change its name because of how its notes are '
        'spread out: C-E-G is C major wherever each one sits. What does '
        'change, and a lot, is which of the three ends up at the very '
        'bottom, in the bass.',
    'Con la fundamental en el bajo, el acorde está en estado fundamental: es la forma más firme, la de los finales. Con la tercera en el bajo está en primera inversión, y suena más liviano, de paso. Con la quinta en el bajo está en segunda inversión, y es tan inestable que casi siempre aparece de una sola manera: el cadencial 6/4.':
        'With the root in the bass the chord is in root position: the '
        'firmest form, the one endings use. With the third in the bass it '
        'is in first inversion, and sounds lighter, passing. With the fifth '
        'in the bass it is in second inversion, and it is so unstable that '
        'it almost always shows up in just one way: the cadential 6/4.',
    'El bajo cifrado del barroco las anota con números que dicen qué intervalos van encima del bajo: nada para el estado fundamental, un 6 para la primera inversión y 6/4 para la segunda. Son los números que el analizador escribe debajo del pentagrama. En cifrado americano la inversión va con una barra: G/B es sol mayor con si en el bajo.':
        'Baroque figured bass writes them down with numbers that say which '
        'intervals go above the bass: nothing for root position, a 6 for '
        'first inversion and 6/4 for second. They are the numbers the '
        'analyzer writes under the staff. In chord symbols the inversion '
        'takes a slash: G/B is G major with B in the bass.',
    'Do mayor tres veces: con do, con mi y con sol abajo de todo. Las tres notas son las mismas; lo que cambia es cuál sostiene a las otras dos.':
        'C major three times: with C, with E and with G at the bottom. The '
        'three notes are the same; what changes is which one holds up the '
        'other two.',

    # -- palabras sueltas ----------------------------------------------------
    'Movimientos': 'Motion',
    'Cadencias': 'Cadences',
    'Estilos': 'Styles',
    'segunda menor': 'minor second',
    'segunda mayor': 'major second',
    'tercera menor': 'minor third',
    'tercera mayor': 'major third',
    'cuarta justa': 'perfect fourth',
    'quinta justa': 'perfect fifth',
    'sexta menor': 'minor sixth',
    'sexta mayor': 'major sixth',
    # 'Bajo' no va acá: es un nombre de `theory.VOICE_CATALOG` y su
    # traducción vive en `en_engine.py`, que es de donde lo toma todo el
    # programa.
    'contrario': 'contrary',
    'oblicuo': 'oblique',
    'directo': 'similar',
    'paralelo': 'parallel',
    'quieto': 'static',
    'semicadencia': 'half cadence',
    'cadencia rota': 'deceptive cadence',
    'cadencia plagal': 'plagal cadence',
    'Quintas paralelas': 'Parallel fifths',
    'Octavas paralelas': 'Parallel octaves',
    'Quinta oculta': 'Hidden fifth',
    'Octava oculta': 'Hidden octave',
    'subdominante': 'subdominant',
    'dominante': 'dominant',
    'Barroco': 'Baroque',
    'Gregoriano': 'Gregorian',
    'Contrario': 'Contrary',
    'Oblicuo': 'Oblique',
    'Directo': 'Similar',
    'Paralelo': 'Parallel',
    'Subdominante': 'Subdominant',
    'Dominante': 'Dominant',
    'Rota': 'Deceptive',
    'Semicadencia': 'Half cadence',
    'Cadencia plagal: IV - I': 'Plagal cadence: IV - I',
    'Cadencia rota': 'Deceptive cadence',
    'Mayor': 'Major',
    'Menor': 'Minor',
    'Estado fundamental': 'Root position',
    'Tónica': 'Tonic',
    'Auténtica': 'Authentic',
    'Bajo y Tenor': 'Bass and Tenor',
    'Bajo y Alto': 'Bass and Alto',
    'Tenor y Alto': 'Tenor and Alto',
    'Alto y Soprano': 'Alto and Soprano',
    'Salto de tritono en una voz': 'Tritone leap in one voice',
    'Tritono entre dos voces': 'Tritone between two voices',
    'Salto de más de una cuarta': 'Leap larger than a fourth',
    'Novena menor sobre una nota que no es la fundamental':
        'Minor ninth above a note that is not the root',
    'unísono u octava': 'unison or octave',
    'séptima menor': 'minor seventh',
    'séptima mayor': 'major seventh',
    'primera inversión': 'first inversion',
    'segunda inversión': 'second inversion',
    'tercera inversión': 'third inversion',
    'la tonalidad de la consigna': 'the key the exercise asks for',
    'ninguno': 'none',
    'otra cosa': 'something else',
    'sin número': 'no number',
    'un acorde que no se pudo nombrar': 'a chord that could not be named',

    # -- unidades y lecciones ------------------------------------------------
    'Movimientos de contrapunto': 'Contrapuntal motion',
    'Armonías': 'Harmony',
    'Particularidades por género': 'What each style asks for',
    'Serie armónica': 'Harmonic series',
    'El acorde y su tercera': 'The chord and its third',
    'Reconocer una cadencia': 'Recognising a cadence',
    'Gregoriano y organum': 'Gregorian and organum',
    'De los armónicos a los intervalos': 'From harmonics to intervals',
    'Entre un acorde y el siguiente, dos voces cualesquiera sólo pueden hacer cuatro cosas: ir en direcciones contrarias, que una se quede quieta y la otra se mueva, ir para el mismo lado cambiando de distancia, o ir para el mismo lado conservándola.':
        'Between one chord and the next, any two voices can only do four '
        'things: go in opposite directions, have one stay put while the '
        'other moves, go the same way while changing their distance, or go '
        'the same way keeping it.',
    'Contrario, oblicuo, directo y paralelo. El analizador mide cada paso contra la nota anterior de cada voz y lo nombra con esas cuatro palabras: son las mismas con las que te va a corregir.':
        'Contrary, oblique, similar and parallel. The analyzer measures '
        'every step against each voice’s previous note and names it with '
        'those four words: they are the same ones it will mark you with.',
    'Si dos voces están a una quinta y se mueven para el mismo lado la misma distancia, siguen a una quinta: eso es una quinta paralela. Con la octava pasa lo mismo.':
        'If two voices are a fifth apart and move the same way by the same '
        'distance, they are still a fifth apart: that is a parallel fifth. '
        'The same goes for the octave.',
    'El oído deja de escuchar dos voces y escucha una sola con un timbre raro. Por eso el barroco las prohíbe de plano, y por eso el analizador las marca en rojo. La salida es la del libro: mover una de las dos al revés, o dejarla quieta si el acorde siguiente comparte esa nota.':
        'The ear stops hearing two voices and hears a single one with an '
        'odd timbre. That is why the baroque forbids them outright, and why '
        'the analyzer marks them in red. The way out is the book’s: move one '
        'of the two the other way, or keep it still if the next chord shares '
        'that note.',
    'Dos voces se cruzan cuando la de abajo pasa a estar por encima de la de arriba. Se escucha confuso, y por eso los tres estilos lo prohíben de entrada.':
        'Two voices cross when the lower one ends up above the upper one. It '
        'sounds confusing, which is why all three styles forbid it from the '
        'start.',
    'Lo mismo con los saltos: una voz que salta mucho es difícil de cantar y de seguir. Lo normal es que las voces de arriba vayan juntas y el bajo más separado, como la mano derecha y la izquierda de un pianista.':
        'Same with leaps: a voice that leaps a lot is hard to sing and to '
        'follow. The usual thing is for the upper voices to stay together '
        'and the bass further away, like a pianist’s right and left hands.',
    'Una tríada es una fundamental, la nota que está una tercera más arriba y la que está una quinta más arriba: do-mi-sol es do mayor, C.':
        'A triad is a root, the note a third above it and the note a fifth '
        'above it: C-E-G is C major, C.',
    'Si la tercera está un semitono más abajo el acorde es menor y suena más oscuro. Toda la diferencia entre mayor y menor está en esa única nota, y por eso es la que nunca se omite.':
        'If the third is a semitone lower the chord is minor and sounds '
        'darker. The whole difference between major and minor lies in that '
        'one note, which is why it is never left out.',
    'Sobre cada nota de la escala se arma un acorde con notas de la escala, y se numeran con números romanos: I, ii, iii, IV, V, vi, vii°. Mayúscula es mayor y minúscula es menor.':
        'On each note of the scale a chord is built from notes of the scale, '
        'and they are numbered with Roman numerals: I, ii, iii, IV, V, vi, '
        'vii°. Upper case is major and lower case is minor.',
    'El número romano no dice cómo se llama el acorde sino qué papel cumple, y es el mismo en cualquier tonalidad.':
        'The Roman numeral does not say what the chord is called but what '
        'role it plays, and it is the same in any key.',
    'Un acorde puede cantarse con cualquiera de sus notas abajo. Con la fundamental en el bajo está en estado fundamental; con la tercera, en primera inversión; con la quinta, en segunda.':
        'A chord can be sung with any of its notes at the bottom. With the '
        'root in the bass it is in root position; with the third, in first '
        'inversion; with the fifth, in second.',
    'El bajo cifrado las anota con números: nada para el estado fundamental, 6 para la primera inversión y 6/4 para la segunda. Son los números que el analizador escribe debajo del pentagrama.':
        'Figured bass writes them down with numbers: nothing for root '
        'position, 6 for first inversion and 6/4 for second. They are the '
        'numbers the analyzer writes under the staff.',
    'Tónica es la casa: I, y de refilón vi y iii. Subdominante es salir de casa: IV y ii. Dominante es la tensión máxima: V y vii°, con la sensible tirando hacia la tónica.':
        'Tonic is home: I, and by extension vi and iii. Subdominant is '
        'leaving home: IV and ii. Dominant is maximum tension: V and vii°, '
        'with the leading tone pulling towards the tonic.',
    'El recorrido típico es casa, salgo, tensión, vuelvo. Lo que importa de un acorde no es su nombre: es en cuál de las tres casillas cae.':
        'The typical journey is home, leave, tension, return. What matters '
        'about a chord is not its name: it is which of the three boxes it '
        'falls in.',
    'A una tríada se le puede apilar una nota más, la séptima. G se convierte en G7 y deja de ser un lugar donde quedarse: la séptima es un intervalo tenso y pide resolver.':
        'One more note can be stacked on a triad: the seventh. G becomes G7 '
        'and stops being a place to stay: the seventh is a tense interval '
        'and asks to resolve.',
    'Resuelve bajando un grado. Y el V7 trae además la sensible, que sube a la tónica: en G7 a C, el fa baja a mi y el si sube a do.':
        'It resolves by stepping down. And the V7 also carries the leading '
        'tone, which rises to the tonic: in G7 to C, the F falls to E and '
        'the B rises to C.',
    'La más común de todas y la que define la tonalidad: el quinto grado, con la sensible adentro, resuelve en la tónica.':
        'The most common of all and the one that defines the key: the fifth '
        'degree, with the leading tone inside it, resolves onto the tonic.',
    'Si los dos acordes tienen la fundamental en el bajo, el analizador la llama perfecta; si alguno está invertido, imperfecta.':
        'If both chords have the root in the bass, the analyzer calls it '
        'perfect; if either is inverted, imperfect.',
    'La subdominante cierra directamente sobre la tónica, sin pasar por la dominante. Es el «amén» de los himnos.':
        'The subdominant closes straight onto the tonic, without going '
        'through the dominant. It is the “amen” of hymns.',
    'Suena más blanda y más antigua que la auténtica, justamente porque le falta la sensible tirando.':
        'It sounds softer and older than the authentic one, precisely '
        'because it lacks the pull of the leading tone.',
    'El V prepara la tónica y en el último momento cae en el sexto grado: en Do mayor, G va a Am en vez de a C.':
        'The V sets up the tonic and at the last moment lands on the sixth '
        'degree: in C major, G goes to Am instead of C.',
    'La resolución se posterga y la frase, que parecía terminada, sigue. Es un recurso de continuidad.':
        'The resolution is put off and the phrase, which seemed finished, '
        'carries on. It is a device for continuity.',
    'No toda frase cierra. Terminar en el V deja la música colgada: es la semicadencia.':
        'Not every phrase closes. Ending on V leaves the music hanging: that '
        'is the half cadence.',
    'Sirve para partir una idea larga en dos mitades, la primera de las cuales queda abierta: pregunta y respuesta.':
        'It splits a long idea into two halves, the first of which is left '
        'open: question and answer.',
    'Una cadencia es la manera de terminar una frase: el gesto que dice «hasta acá». Se reconoce por los dos últimos acordes y por lo que hacen con la tónica.':
        'A cadence is the way a phrase ends: the gesture that says “this '
        'far”. You recognise it by the last two chords and what they do '
        'with the tonic.',
    'La auténtica llega desde el V; la plagal, desde el IV; la rota promete la tónica y entrega el sexto grado; la semicadencia ni siquiera llega.':
        'The authentic one arrives from V; the plagal, from IV; the '
        'deceptive promises the tonic and delivers the sixth degree; the '
        'half cadence never even arrives.',
    'El contrapunto de la práctica común, el más reglado de los tres. Prohíbe quintas y octavas paralelas, premia el movimiento contrario, castiga los saltos de tritono y de séptima, y vigila que las voces no se crucen.':
        'Common-practice counterpoint, the most rule-bound of the three. It '
        'forbids parallel fifths and octaves, rewards contrary motion, '
        'penalises tritone and seventh leaps, and watches that voices do '
        'not cross.',
    'Prohibir y castigar no son lo mismo: una solución con quintas paralelas se descarta entera; un salto de tritono sólo cuesta más.':
        'Forbidding and penalising are not the same: a solution with '
        'parallel fifths is thrown out whole; a tritone leap only costs '
        'more.',
    'Escritura modal, anterior a la tonalidad: líneas casi siempre por grado conjunto y el tritono evitado con insistencia, ni saltado por una voz ni sonando entre dos.':
        'Modal writing, older than tonality: lines almost always moving by '
        'step and the tritone stubbornly avoided, neither leapt by one '
        'voice nor sounding between two.',
    'En cambio tolera las quintas y octavas paralelas, porque el organum —la forma más antigua de cantar a varias voces— consiste en doblar la melodía en paralelo: la vox principalis lleva el canto y la organalis la acompaña debajo.':
        'It does, however, tolerate parallel fifths and octaves, because '
        'organum —the oldest way of singing in several voices— consists of '
        'doubling the melody in parallel: the vox principalis carries the '
        'chant and the organalis goes along below it.',
    'Acá lo que manda es cómo se encadenan la tercera y la séptima de cada acorde: las guide tones. Son las que dicen si un acorde es mayor, menor o dominante; el resto es relleno.':
        'Here what rules is how the third and the seventh of each chord '
        'link up: the guide tones. They are what tell you whether a chord is '
        'major, minor or dominant; the rest is filler.',
    'Se conectan por grado conjunto, se mantienen las notas que dos acordes comparten y se evitan las novenas menores. Las paralelas y los tritonos, en cambio, pasan sin problema.':
        'They connect by step, notes shared by two chords are held, and '
        'minor ninths are avoided. Parallels and tritones, on the other '
        'hand, go through without trouble.',
    'Nada vibra de una sola manera. Una cuerda vibra entera y, al mismo tiempo, en mitades, en tercios, en cuartos: cada división suena al doble, al triple, al cuádruple de la frecuencia.':
        'Nothing vibrates in just one way. A string vibrates as a whole and, '
        'at the same time, in halves, in thirds, in quarters: each division '
        'sounds at double, triple, four times the frequency.',
    'Si la cuerda entera da 110 hercios, arriba suenan 220, 330, 440, 550: los múltiplos enteros, sin excepción y sin hueco. Lo que llamamos «la nota» es el primero de la lista.':
        'If the whole string gives 110 hertz, above it sound 220, 330, 440, '
        '550: the whole-number multiples, without exception and without '
        'gaps. What we call “the note” is the first on the list.',
    'El segundo armónico es la octava. El tercero es la quinta. El quinto es la tercera mayor.':
        'The second harmonic is the octave. The third is the fifth. The '
        'fifth is the major third.',
    'No es casualidad que la música haya empezado por octavas y quintas y haya tardado siglos en aceptar la tercera: es el orden en que aparecen.':
        'It is no accident that music started with octaves and fifths and '
        'took centuries to accept the third: that is the order in which '
        'they appear.',
    'Los armónicos caen donde la física los pone, y la física no sabe nada de teclas. El tercero cae dos centésimas de semitono por encima de la quinta del piano; el quinto, catorce por debajo de la tercera.':
        'Harmonics fall where physics puts them, and physics knows nothing '
        'about keys. The third lands two hundredths of a semitone above the '
        'piano’s fifth; the fifth, fourteen below its third.',
    'El séptimo es el caso serio: no hay ninguna tecla ahí. El temperamento igual reparte el error parejo entre las doce notas, y es un acuerdo, no una verdad.':
        'The seventh is the serious case: there is no key there at all. '
        'Equal temperament spreads the error evenly over the twelve notes, '
        'and it is an agreement, not a truth.',

    # -- las consignas -------------------------------------------------------
    'Mirá el bajo y la soprano entre el compás 2 y el 3. ¿Qué movimiento hacen?':
        'Look at the bass and the soprano between measures 2 and 3. What '
        'motion do they make?',
    'El bajo sube por grados: do, re, mi, fa. Escribí la soprano, una redonda por compás, de manera que cada paso sea movimiento contrario.':
        'The bass climbs by step: C, D, E, F. Write the soprano, one whole '
        'note per measure, so that every step is contrary motion.',
    'Ahora un movimiento distinto en cada paso: escribí la soprano para que con el bajo haga contrario, después oblicuo y al final directo. Ojo: directo no es paralelo.':
        'Now a different motion at each step: write the soprano so that with '
        'the bass it makes contrary, then oblique and finally similar '
        'motion. Careful: similar is not parallel.',
    'En este fragmento hay quintas paralelas, una sola vez. ¿Entre qué dos voces?':
        'This passage has parallel fifths, just once. Between which two '
        'voices?',
    'Del compás 1 al 2 hay quintas y octavas paralelas. Corregilas moviendo el tenor, el alto o la soprano: el bajo no se toca y cada compás tiene que seguir siendo el mismo acorde.':
        'From measure 1 to 2 there are parallel fifths and octaves. Fix them '
        'by moving the tenor, alto or soprano: the bass stays as it is and '
        'every measure has to remain the same chord.',
    'El bajo y la soprano llegan a una quinta moviéndose para el mismo lado, y la soprano llega saltando. ¿Qué es?':
        'The bass and the soprano reach a fifth moving the same way, and the '
        'soprano arrives by leap. What is it?',
    'En el compás 2 el alto canta por encima de la soprano. Corregilo sin tocar el bajo y sin cambiar los acordes, y sin que aparezcan paralelas nuevas.':
        'In measure 2 the alto sings above the soprano. Fix it without '
        'touching the bass or changing the chords, and without new '
        'parallels appearing.',
    'Escribí La menor (Am) a cuatro voces, en La menor, con la fundamental en el bajo.':
        'Write A minor (Am) in four voices, in A minor, with the root in the '
        'bass.',
    'Escuchá el acorde sin mirarlo. ¿Es mayor o menor?':
        'Listen to the chord without looking at it. Is it major or minor?',
    'Esto está en Sol mayor. ¿Qué grado es el acorde del compás 2?':
        'This is in G major. Which degree is the chord in measure 2?',
    'En Do mayor: escribí Sol mayor (G) en primera inversión, con la tercera (si) en el bajo.':
        'In C major: write G major (G) in first inversion, with the third '
        '(B) in the bass.',
    'Este acorde es Fa mayor. ¿Cómo está cantado?':
        'This chord is F major. How is it voiced?',
    'En Do mayor. ¿Qué función cumple el acorde del compás 2?':
        'In C major. What function does the chord in measure 2 have?',
    'Escribí G7 a cuatro voces, una nota por voz (sol, si, re y fa), con el sol en el bajo.':
        'Write G7 in four voices, one note per voice (G, B, D and F), with G '
        'in the bass.',
    'El compás 1 es G7, con la séptima (fa) en el tenor y la sensible (si) en el alto. Escribí el C del compás 2 de manera que la séptima baje un grado y la sensible suba a la tónica.':
        'Measure 1 is G7, with the seventh (F) in the tenor and the leading '
        'tone (B) in the alto. Write the C of measure 2 so that the seventh '
        'steps down and the leading tone rises to the tonic.',
    'En Sol mayor. Están escritos el I y el IV: completá los compases 3 y 4 para cerrar con una cadencia auténtica perfecta, sin paralelas.':
        'In G major. The I and the IV are written: complete measures 3 and 4 '
        'to close with a perfect authentic cadence, without parallels.',
    'En Fa mayor. Completá los compases 3 y 4 con una cadencia plagal: el IV y después el I.':
        'In F major. Complete measures 3 and 4 with a plagal cadence: the IV '
        'and then the I.',
    'En Do mayor. El compás 3 es la dominante: escribí el compás 4 para que la cadencia sea rota.':
        'In C major. Measure 3 is the dominant: write measure 4 so that the '
        'cadence is deceptive.',
    'En Re mayor. Completá los compases 3 y 4 de manera que la frase quede colgada sobre el V.':
        'In D major. Complete measures 3 and 4 so that the phrase is left '
        'hanging on the V.',
    'En La menor. ¿Con qué cadencia termina?':
        'In A minor. Which cadence does it end with?',
    'En Do mayor, sin partitura: escuchá cómo termina. ¿Qué cadencia es?':
        'In C major, without the score: listen to how it ends. Which cadence '
        'is it?',
    'Este fragmento está escrito para el estilo Barroco. ¿Qué regla del estilo rompe?':
        'This passage is written for the Baroque style. Which of the style’s '
        'rules does it break?',
    'Estas son las quintas paralelas de la unidad 1. ¿En qué estilo hacen que la solución se descarte entera?':
        'These are the parallel fifths from unit 1. In which style do they '
        'get the whole solution thrown out?',
    'Este fragmento está escrito para el estilo Gregoriano. ¿Qué regla del estilo rompe?':
        'This passage is written for the Gregorian style. Which of the '
        'style’s rules does it break?',
    'La soprano es la vox principalis. Escribí debajo, en el alto, la vox organalis: la misma melodía, nota por nota, una quinta justa más abajo.':
        'The soprano is the vox principalis. Write the vox organalis below '
        'it, in the alto: the same melody, note by note, a perfect fifth '
        'lower.',
    'Un ii-V-I escrito para el estilo Jazz, con quintas paralelas y un tritono a la vista. ¿Qué regla del estilo rompe?':
        'A ii-V-I written for the Jazz style, with parallel fifths and a '
        'tritone in plain sight. Which of the style’s rules does it break?',
    'Dm7 - G7 - Cmaj7 en jazz. El bajo y la soprano están escritos: completá el tenor y el alto con las guide tones de cada acorde, moviéndose por grado o quedándose quietas.':
        'Dm7 - G7 - Cmaj7 in jazz. The bass and the soprano are written: '
        'fill in the tenor and the alto with each chord’s guide tones, '
        'moving by step or staying put.',
    'Una cuerda da 110 hercios: es un la2. ¿Cuántos hercios da su quinto armónico?':
        'A string gives 110 hertz: it is an A2. How many hertz does its '
        'fifth harmonic give?',
    'Suenan juntos la fundamental, un la2, y uno solo de sus armónicos. Escuchalo. ¿Cuál es?':
        'The fundamental, an A2, and just one of its harmonics sound '
        'together. Listen. Which one is it?',
    'La fundamental es do3. Escribí en la soprano, con una redonda, la nota del piano más cercana a su tercer armónico.':
        'The fundamental is C3. Write in the soprano, as a whole note, the '
        'piano note closest to its third harmonic.',
    'Mirá la serie de do3. ¿En qué armónico aparece por primera vez la tercera mayor?':
        'Look at the series of C3. In which harmonic does the major third '
        'appear for the first time?',
    'El séptimo armónico de la2 cae cerca del sol del piano. ¿Cuánto se aparta de la tecla?':
        'The seventh harmonic of A2 lands near the piano’s G. How far is it '
        'from the key?',
    'De estos cuatro armónicos de la2, ¿cuál cae más lejos de cualquier tecla del piano?':
        'Of these four harmonics of A2, which one lands furthest from any '
        'piano key?',

    # -- las opciones --------------------------------------------------------
    'Quintas paralelas: se prohíben': 'Parallel fifths: forbidden',
    'Una quinta directa: se penaliza, no se prohíbe':
        'A direct fifth: penalised, not forbidden',
    'Nada: llegaron por movimiento contrario':
        'Nothing: they got there by contrary motion',
    'Primera inversión (6)': 'First inversion (6)',
    'Segunda inversión (6/4)': 'Second inversion (6/4)',
    'El 2º: la octava': 'The 2nd: the octave',
    'El 3º: la quinta, una octava más arriba':
        'The 3rd: the fifth, an octave higher',
    'El 4º: dos octavas': 'The 4th: two octaves',
    'El 5º: la tercera mayor, dos octavas más arriba':
        'The 5th: the major third, two octaves higher',
    'En el 3º': 'In the 3rd',
    'En el 4º': 'In the 4th',
    'En el 5º': 'In the 5th',
    'En el 6º': 'In the 6th',
    'Dos centésimas por encima': 'Two hundredths above',
    'Catorce centésimas por debajo': 'Fourteen hundredths below',
    'Treinta y una centésimas por debajo': 'Thirty-one hundredths below',
    'Nada: cae justo en la tecla': 'Not at all: it lands right on the key',

    # -- la corrección -------------------------------------------------------
    '{names}, del compás {bar} al {until}':
        '{names}, from measure {bar} to {until}',
    '{label} entre {pair}, del compás {before} al {bar}.':
        '{label} between {pair}, from measure {before} to {bar}.',
    '{voice} y {voice2}': '{voice} and {voice2}',
    '{names}, en el compás {bar}': '{names}, in measure {bar}',
    'Del compás {bar} al {next}: {moves}. {reason}: movimiento {kind}.':
        'From measure {bar} to {next}: {moves}. {reason}: {kind} motion.',
    '{voice} y {voice2} están a una quinta justa en el compás {before} y siguen a una quinta en el {bar}, moviéndose para el mismo lado.':
        '{voice} and {voice2} are a perfect fifth apart in measure {before} '
        'and still a fifth apart in {bar}, moving the same way.',
    'Es {symbol}: la tercera, {third}, está a tres semitonos de la fundamental.':
        'It is {symbol}: the third, {third}, is three semitones above the '
        'root.',
    'Es {symbol}: la tercera, {third}, está a cuatro semitonos de la fundamental.':
        'It is {symbol}: the third, {third}, is four semitones above the '
        'root.',
    'El compás {bar} es {symbol}: sobre el {degree}º grado de la escala, y por eso {numeral}.':
        'Measure {bar} is {symbol}: built on scale degree {degree}, and so '
        '{numeral}.',
    'El bajo canta {note}, que es {role} de {symbol}: el analizador lo cifra {figure}.':
        'The bass sings {note}, which is {role} of {symbol}: the analyzer '
        'figures it {figure}.',
    'El compás {bar} es {symbol}, el {numeral}: función de {function}.':
        'Measure {bar} is {symbol}, the {numeral}: {function} function.',
    'Termina {pair}: {kind}. {detail}.': 'It ends {pair}: {kind}. {detail}.',
    '{rule}: {where}. El {genre} lo prohíbe.':
        '{rule}: {where}. The {genre} style forbids it.',
    '{rule}: {where}. El {genre} lo castiga.':
        '{rule}: {where}. The {genre} style penalises it.',
    'Sólo el {genre} las prohíbe de plano: una solución que las tenga se descarta entera, no importa lo bien que esté todo lo demás.':
        'Only the {genre} style forbids them outright: a solution that has '
        'them is thrown out whole, however good everything else is.',
    '{number} veces {base} hercios: {hz}. Los armónicos son los múltiplos enteros de la fundamental.':
        '{number} times {base} hertz: {hz}. Harmonics are the whole-number '
        'multiples of the fundamental.',
    'Era el {number}º: {hz} hercios, que cae en {note}.':
        'It was harmonic {number}: {hz} hertz, which lands on {note}.',
    'El {number}º armónico da {hz} hercios; el {note} del piano está a {cents} centésimas de semitono.':
        'Harmonic {number} gives {hz} hertz; the piano’s {note} is {cents} '
        'hundredths of a semitone away.',
    'En centésimas de semitono respecto de la tecla más cercana: {listed}. El {worst}º no tiene ninguna tecla cerca.':
        'In hundredths of a semitone from the nearest key: {listed}. Harmonic '
        '{worst} has no key anywhere near it.',
    'Cruce de voces en el compás {bar}: {voice} canta por encima de {voice2}.':
        'Voice crossing in measure {bar}: {voice} sings above {voice2}.',
    'El analizador lee {symbol}, cifrado {figure}: justo lo que se pidió.':
        'The analyzer reads {symbol}, figured {figure}: just what was asked.',
    'El analizador lee {symbol}, en estado fundamental: justo lo que se pidió.':
        'The analyzer reads {symbol}, in root position: just what was asked.',
    'Los dos últimos acordes se leen {pair}, y el último es {function}: la frase no cierra con una {wanted}.':
        'The last two chords read {pair}, and the last one is {function}: '
        'the phrase does not close with a {wanted}.',
    'En el compás {bar} la organalis ({note}) no está debajo de la principalis: va una quinta justa más abajo.':
        'In measure {bar} the organalis ({note}) is not below the '
        'principalis: it goes a perfect fifth lower.',
    'En el compás {bar} la organalis está a una {name} de la principalis ({semitones} semitonos): va a la quinta justa, siete semitonos más abajo, que sería {target}.':
        'In measure {bar} the organalis is a {name} from the principalis '
        '({semitones} semitones): it goes at the perfect fifth, seven '
        'semitones lower, which would be {target}.',
    'Escribiste {note}. El armónico {number} de {base} da {hz} hercios, y eso cae en {target}.':
        'You wrote {note}. Harmonic {number} of {base} gives {hz} hertz, and '
        'that lands on {target}.',
    'Antes no estaban a una quinta y llegan a una moviéndose para el mismo lado, con la soprano saltando: el analizador la marca como «{label}», un aviso y no una falta. El libro la llama quinta directa: se penaliza, no se prohíbe.':
        'They were not a fifth apart before and they reach one moving the '
        'same way, with the soprano leaping: the analyzer flags it as '
        '“{label}”, a warning and not a fault. The book calls it a direct '
        'fifth: penalised, not forbidden.',
    'El {genre} lo prohíbe, pero en este fragmento no pasa.':
        'The {genre} style forbids it, but it does not happen in this '
        'passage.',
    'El {genre} lo castiga, pero en este fragmento no pasa.':
        'The {genre} style penalises it, but it does not happen in this '
        'passage.',
    '«{label}» no es.': '“{label}” is not it.',
    'Del compás {bar} al {next}, {pair} hacen movimiento {heard}, porque {reason}. Acá se pedía {kind}.':
        'From measure {bar} to {next}, {pair} move in {heard} motion, '
        'because {reason}. The exercise asked for {kind}.',
    'El analizador no encuentra un acorde en lo que escribiste: hacen falta al menos tres voces sonando juntas.':
        'The analyzer finds no chord in what you wrote: it needs at least '
        'three voices sounding together.',
    'Lo que escribiste se lee {symbol}, no {wanted}.':
        'What you wrote reads {symbol}, not {wanted}.',
    'El bajo canta {note}, {role}: eso es {state}. Se pidió {wanted_state}, con {wanted_role} ({target}) en el bajo.':
        'The bass sings {note}, {role}: that is {state}. The exercise asked '
        'for {wanted_state}, with {wanted_role} ({target}) in the bass.',
    'El bajo canta {note}, que no es nota de {chord}: así no es ninguna inversión. Se pidió {wanted_state}, con {wanted_role} ({target}) en el bajo.':
        'The bass sings {note}, which is not a note of {chord}: that is no '
        'inversion at all. The exercise asked for {wanted_state}, with '
        '{wanted_role} ({target}) in the bass.',
    'otra nota': 'another note',
    'En el compás {bar}, {chord} no tiene tercera: falta {note}, que es la nota que dice si el acorde es mayor o menor.':
        'In measure {bar}, {chord} has no third: {note} is missing, and it is '
        'the note that tells whether the chord is major or minor.',
    'El compás {bar} se lee {chord}: tiene que ser la tónica ({tonic}).':
        'Measure {bar} reads {chord}: it has to be the tonic ({tonic}).',
    'Hacen falta al menos dos acordes para que haya cadencia.':
        'It takes at least two chords to make a cadence.',
    '{pair}: {kind}. {detail}.': '{pair}: {kind}. {detail}.',
    'Los dos últimos acordes se leen {pair}: eso es una {kind}, no una {wanted}.':
        'The last two chords read {pair}: that is a {kind}, not a {wanted}.',
    'Cada nota de la organalis está una quinta justa debajo de la principalis, y las dos se mueven en paralelo: es el organum más antiguo que hay.':
        'Every note of the organalis is a perfect fifth below the '
        'principalis, and the two move in parallel: it is the oldest '
        'organum there is.',
    'La séptima de cada acorde pasa a ser la tercera del siguiente y la tercera queda quieta como séptima: dos notas llevan toda la progresión.':
        'Each chord’s seventh becomes the third of the next, and the third '
        'stays put as the seventh: two notes carry the whole progression.',
    'Falta escribir la nota.': 'The note is still missing.',
    'El armónico {number} de {base} da {hz} hercios: la tecla más cercana es {note}, a {cents} centésimas.':
        'Harmonic {number} of {base} gives {hz} hertz: the nearest key is '
        '{note}, {cents} hundredths away.',
    'Es la nota correcta, pero en otra octava: cada armónico tiene una altura exacta, no sólo un nombre.':
        'It is the right note, but in another octave: each harmonic has an '
        'exact pitch, not just a name.',
    '{voice} en el compás {bar} venía escrito y cambió.':
        'The {voice} in measure {bar} was given and it changed.',
    'Los acordes son los mismos y el analizador ya no encuentra paralelas ni cruces.':
        'The chords are the same and the analyzer no longer finds parallels '
        'or crossings.',
    '{voice} sube de {a} a {b}': '{voice} rises from {a} to {b}',
    '{voice} baja de {a} a {b}': '{voice} falls from {a} to {b}',
    '{voice} se queda en {a}': '{voice} stays on {a}',
    'En un movimiento {kind}, {definition}. Mirá otra vez hacia dónde va cada voz del compás {bar} al {next}.':
        'In {kind} motion, {definition}. Look again at where each voice goes '
        'from measure {bar} to {next}.',
    'Entre {pair} no hay quintas paralelas.':
        'There are no parallel fifths between {pair}.',
    'En el {genre} eso no se castiga: {why}.':
        'The {genre} style does not penalise that: {why}.',
    'En el {genre} eso no se castiga.':
        'The {genre} style does not penalise that.',
    'El {number}º armónico de {base} cae en {note}, {cents} centésimas de la tecla: es la tercera mayor, y antes no aparece.':
        'Harmonic {number} of {base} lands on {note}, {cents} hundredths '
        'from the key: it is the major third, and it does not appear '
        'earlier.',
    'el {n}º, {cents}': 'harmonic {n}, {cents}',
    '{voice} tiene notas después del compás {bar}, que es donde termina el ejercicio.':
        'The {voice} has notes after measure {bar}, which is where the '
        'exercise ends.',
    'Del compás {bar} al {next}: {pair}, movimiento {kind}.':
        'From measure {bar} to {next}: {pair}, {kind} motion.',
    'En el compás {bar} el acorde cambió: era {was} y ahora se lee {now}. Se corrige moviendo las voces, no cambiando la armonía.':
        'In measure {bar} the chord changed: it was {was} and now reads '
        '{now}. You fix it by moving the voices, not by changing the '
        'harmony.',
    'Le falta la séptima ({note}): sin ella es una tríada.':
        'It is missing the seventh ({note}): without it, it is a triad.',
    'Falta {role}: es la nota que define el acorde.':
        '{role} is missing: it is the note that defines the chord.',
    'En el compás {bar}, {voice} canta {note}, que es {role} de {chord}: las guide tones son la tercera y la séptima.':
        'In measure {bar}, the {voice} sings {note}, which is {role} of '
        '{chord}: the guide tones are the third and the seventh.',
    'En el {genre} se toleran: {why}.':
        'The {genre} style tolerates them: {why}.',
    'Falta escribir {voice} en el compás {bar}.':
        'The {voice} in measure {bar} is still missing.',
    'La séptima ({note}, en {voice}) baja un grado a {target}.':
        'The seventh ({note}, in the {voice}) steps down to {target}.',
    'La séptima ({note}, en {voice}) va a {target}: tiene que bajar un grado.':
        'The seventh ({note}, in the {voice}) goes to {target}: it has to '
        'step down.',
    'La sensible ({note}, en {voice}) sube a la tónica.':
        'The leading tone ({note}, in the {voice}) rises to the tonic.',
    'La sensible ({note}, en {voice}) va a {target}: tiene que subir un semitono, a la tónica.':
        'The leading tone ({note}, in the {voice}) goes to {target}: it has '
        'to rise a semitone, to the tonic.',
    'En el compás {bar} falta {notes} en el tenor o el alto.':
        'In measure {bar}, {notes} is missing from the tenor or the alto.',
    'Del compás {before} al {bar}, {voice} salta de {a} a {b}: las guide tones se conectan por grado o se quedan quietas.':
        'From measure {before} to {bar}, the {voice} leaps from {a} to {b}: '
        'guide tones connect by step or stay put.',
    'Lo que escribiste es el armónico {other}.':
        'What you wrote is harmonic {other}.',

    # -- las razones y las pistas --------------------------------------------
    'una sube y la otra baja': 'one rises and the other falls',
    'las dos van para el mismo lado y la distancia entre ellas cambia':
        'both go the same way and the distance between them changes',
    'las dos van para el mismo lado y conservan el intervalo':
        'both go the same way and keep the interval',
    'ninguna de las dos se mueve': 'neither of them moves',
    'el organum consiste justamente en doblar la melodía en paralelo':
        'organum consists precisely of doubling the melody in parallel',
    'con acordes tan densos el efecto no llega a escucharse':
        'with chords this dense the effect cannot be heard',
    'está adentro de cada acorde de séptima de dominante, y es lo que lo hace tirar':
        'it sits inside every dominant seventh chord, and it is what makes '
        'it pull',
    'los tritonos pasan sin problema': 'tritones go through without trouble',
    'Buscá dos voces que estén a una quinta justa y sigan a una quinta en el acorde siguiente, moviéndose para el mismo lado.':
        'Look for two voices a perfect fifth apart that are still a fifth '
        'apart in the next chord, moving the same way.',
    'Fijate qué intervalo hay entre el bajo y la soprano en el compás 1, y hacia dónde va cada una.':
        'Check what interval there is between the bass and the soprano in '
        'measure 1, and where each one goes.',
    'Escuchá la tercera: en el acorde menor está un semitono más abajo, y el acorde suena más oscuro.':
        'Listen to the third: in a minor chord it is a semitone lower, and '
        'the chord sounds darker.',
    'Contá desde la tónica: el I es el acorde que se arma sobre la primera nota de la escala.':
        'Count from the tonic: I is the chord built on the first note of the '
        'scale.',
    'Mirá qué nota está abajo de todo, en el bajo, y qué papel cumple en el acorde.':
        'Look at which note is at the very bottom, in the bass, and what '
        'role it plays in the chord.',
    'Tónica es el I, y de refilón el vi y el iii; subdominante, el IV y el ii; dominante, el V y el vii°.':
        'Tonic is I, and by extension vi and iii; subdominant, IV and ii; '
        'dominant, V and vii°.',
    'Mirá los dos últimos acordes: de qué grado sale el penúltimo y si el último es la tónica.':
        'Look at the last two chords: which degree the second-to-last comes '
        'from, and whether the last one is the tonic.',
    'Un armónico es la fundamental multiplicada por su número.':
        'A harmonic is the fundamental multiplied by its number.',
    'La octava suena como la misma nota más aguda; la quinta, como otra nota que encaja con la fundamental.':
        'The octave sounds like the same note, higher; the fifth, like a '
        'different note that fits with the fundamental.',
    'Mirá los nombres de las notas debajo de cada barra: la tercera mayor de do es mi.':
        'Look at the note names under each bar: the major third of C is E.',
    'El libro lo cuenta en el capítulo de física: el séptimo es «el caso serio».':
        'The book tells it in the physics chapter: the seventh is “the '
        'serious case”.',
    'El libro lo cuenta en el capítulo de física: hay uno que no tiene ninguna tecla cerca.':
        'The book tells it in the physics chapter: there is one with no key '
        'anywhere near it.',

    # -- la graduación -------------------------------------------------------
    '—  fin de curso  —': '—  end of term  —',
    '—  el último ejercicio, corregido  —':
        '—  the last exercise, marked  —',
    'El último ejercicio queda corregido. Nadie lo marca en rojo.':
        'The last exercise is marked. Nobody marks it in red.',
    'Muy lejos, alguien sostiene una nota sola. Otra voz se le pone debajo, a una quinta, y la sigue.':
        'Far away, someone holds a single note. Another voice settles in '
        'below it, a fifth down, and follows it.',
    'Así empezó todo. Una voz y su sombra.':
        'That is how it all began. A voice and its shadow.',
    'Vos empezaste por donde nosotros terminamos: por la sombra que se suelta y camina por su cuenta.':
        'You started where we finished: with the shadow that lets go and '
        'walks on its own.',
    'Contrario, oblicuo, directo, paralelo. Cuatro palabras. A nosotros nos llevó cuatrocientos años poder decirlas.':
        'Contrary, oblique, similar, parallel. Four words. It took us four '
        'hundred years to be able to say them.',
    'Yo no firmo nada: lo único que me atribuyen no lo escribí. Pero puedo hacer lo que sé hacer.':
        'I sign nothing: the one thing they credit me with, I did not write. '
        'But I can do what I know how to do.',
    'Que se cante el primer renglón.': 'Let the first line be sung.',
    'La nota sola sube un grado. La de abajo la sigue, sin soltarla.':
        'The lone note rises a step. The one below follows it, without '
        'letting go.',
    'Un golpe seco sobre la mesa, como quien pide que se presten los cuadernos.':
        'A sharp knock on the table, like someone asking for the exercise '
        'books to be handed in.',
    'En Leipzig enseñaba en la escuela de Santo Tomás. Los alumnos me traían un bajo y yo les devolvía el cuaderno con los errores señalados en el margen.':
        'In Leipzig I taught at the St. Thomas School. The pupils brought me '
        'a bass line and I handed the book back with the mistakes marked in '
        'the margin.',
    'Todos tenían quintas paralelas la primera vez. Todos. Los que después escribieron bien no son los que no las tuvieron: son los que volvieron a traer el cuaderno.':
        'They all had parallel fifths the first time. All of them. The ones '
        'who later wrote well are not the ones who never had them: they are '
        'the ones who brought the book back.',
    'Aprendiste qué es cada acorde, adónde quiere ir y cómo se termina una frase: llegando, descansando, engañando o dejándola en el aire.':
        'You learned what each chord is, where it wants to go and how a '
        'phrase ends: arriving, resting, deceiving or leaving it in the air.',
    'Al principio de mis partituras escribía dos letras: J. J., «Jesús, ayudame». Al final, otras tres: S. D. G.':
        'At the top of my scores I wrote two letters: J. J., “Jesus, help '
        'me”. At the end, three more: S. D. G.',
    'Lo que va en el medio es trabajo. El tuyo está completo.':
        'What goes in between is work. Yours is complete.',
    'Se va sin despedirse. El clave sigue sonando un compás más.':
        'He leaves without a goodbye. The harpsichord keeps sounding for one '
        'more measure.',
    'El ventilador de la máquina se calla. Otra vez.':
        'The machine’s fan goes quiet. Again.',
    'Llegaste al final de lo que este programa sabe enseñar.':
        'You have reached the end of what this program knows how to teach.',
    'Te debo una aclaración: ninguna corrección la escribí yo. Las escribió el analizador, el mismo que lee a Bach.':
        'I owe you something: I did not write a single correction. The '
        'analyzer wrote them, the same one that reads Bach.',
    'No hubo ninguna trampa ni ninguna tabla de respuestas. Te midió con la misma vara con la que mide todo lo demás.':
        'There was no trick and no answer key. It measured you with the same '
        'yardstick it uses for everything else.',
    'Y lo último que estudiaste es lo primero que existió: una cuerda vibrando en mitades, en tercios, en cuartos. Las quintas, las cadencias, los estilos: todo sale de esa escalera.':
        'And the last thing you studied is the first thing that existed: a '
        'string vibrating in halves, in thirds, in quarters. The fifths, the '
        'cadences, the styles: all of it comes from that ladder.',
    'Hay una costumbre vieja. Al que termina se le da un papel con su nombre.':
        'There is an old custom. Whoever finishes is given a paper with '
        'their name on it.',
    'Yo no tengo tu nombre. Nunca me lo dijiste.':
        'I do not have your name. You never told me.',
    'Donde iría el nombre hay un pentagrama vacío.':
        'Where the name would go there is an empty staff.',
    'Escribí ahí lo que quieras. Ya sabés cómo.':
        'Write whatever you like there. You know how now.',
    'Dicen que las leyendas nacen. No es cierto: se escriben de a una nota, y alguien las corrige.':
        'They say legends are born. Not true: they are written one note at a '
        'time, and someone marks them.',
    'En algún lugar, alguien anota algo en una lista muy corta.':
        'Somewhere, someone writes something down on a very short list.',
    # -- el timbre de muestra (`engine/timbre.py`) ---------------------------
    # Sus hermanas están en `en_engine.py`; ésta llegó con los arreglos de
    # la escuelita y quedó acá. El catálogo se junta entero al cargarse, así
    # que da lo mismo en qué pedazo esté.
    '{name} trae valores que no son sonido (infinitos o indefinidos). Volvé a exportarlo desde el programa que lo hizo.':
        '{name} contains values that are not sound (infinite or undefined). '
        'Export it again from the program that made it.',

    # -- unidad 1 · leer la partitura ---------------------------------------
    'Leer la partitura': 'Reading the score',
    'Lectura': 'Reading',
    'La clave de sol': 'The treble clef',
    'La clave de fa': 'The bass clef',
    'El do central y las líneas adicionales': 'Middle C and ledger lines',
    'La clave de sol se dibuja enroscada en la segunda línea del pentagrama, contando desde abajo, y esa línea pasa a ser sol. Es el sol que está justo arriba del do central.':
        'The treble clef curls around the second line of the staff, counting '
        'from the bottom, and that line becomes G. It is the G just above '
        'middle C.',
    'Desde ahí se cuenta para arriba y para abajo, una nota por línea y otra por espacio. Las líneas son mi, sol, si, re y fa, y los espacios fa, la, do y mi. Con encontrar el sol y contar alcanza.':
        'From there you count up and down, one note per line and one per '
        'space. The lines are E, G, B, D and F, and the spaces F, A, C and E. '
        'Finding the G and counting is enough.',
    'Las voces graves se escriben en la clave de fa. Sus dos puntos van uno arriba y otro abajo de la cuarta línea, y esa línea es fa, el que está debajo del do central.':
        'Low voices are written in the bass clef. Its two dots sit one above '
        'and one below the fourth line, and that line is F, the one below '
        'middle C.',
    'Se lee igual que la de sol, contando desde la línea de la clave. Las líneas son sol, si, re, fa y la, y los espacios la, do, mi y sol. En el sistema de dos pentagramas el bajo se escribe acá.':
        "It is read the same way as the treble clef, counting from the "
        "clef's line. The lines are G, B, D, F and A, and the spaces A, C, E "
        "and G. In the two-staff system the bass is written here.",
    'Entre los dos pentagramas cabe una nota más, el do central. Se escribe con una rayita propia, la línea adicional, debajo del pentagrama de sol o encima del de fa, y en los dos lugares es la misma tecla del piano.':
        'One more note fits between the two staves: middle C. It gets a short '
        'line of its own, a ledger line, below the treble staff or above the '
        'bass staff, and in both places it is the same piano key.',
    'Cualquier nota que se salga del pentagrama lleva una línea adicional por cada línea que le falta, y se sigue contando igual. Subir una octava es subir siete lugares, así que lo que estaba en una línea vuelve a aparecer en un espacio.':
        'Any note that leaves the staff gets one ledger line for each line it '
        'is missing, and you keep counting the same way. Going up an octave '
        'is going up seven places, so what was on a line shows up again in a '
        'space.',
    'La soprano canta una nota por compás. ¿Cuál es la del compás 3?':
        'The soprano sings one note per bar. Which one is in bar 3?',
    'El bajo canta una nota por compás. ¿Cuál es la del compás 3?':
        'The bass sings one note per bar. Which one is in bar 3?',
    'Escribí en la soprano las notas de los cuatro espacios, de abajo para arriba y una por compás: fa, la, do y mi.':
        'Write the notes of the four spaces in the soprano, bottom to top '
        'and one per bar: F, A, C and E.',
    'Escribí en el bajo las notas de las cuatro primeras líneas, de abajo para arriba y una por compás: sol, si, re y fa.':
        'Write the notes of the first four lines in the bass, bottom to top '
        'and one per bar: G, B, D and F.',
    'En los cuatro compases el bajo y la soprano cantan una nota con el mismo nombre. ¿En cuál cantan exactamente la misma nota?':
        'In all four bars the bass and the soprano sing a note with the same '
        'name. In which one do they sing exactly the same note?',
    'Leé el bajo y escribí en la soprano las mismas notas una octava más arriba, compás por compás.':
        'Read the bass and write the same notes an octave higher in the '
        'soprano, bar by bar.',
    'Compás {bar}': 'Bar {bar}',
    'la clave de sol': 'the treble clef',
    'la clave de fa': 'the bass clef',
    'en la línea {n}': 'on line {n}',
    'en el espacio {n}': 'in space {n}',
    'justo debajo del pentagrama': 'just below the staff',
    'justo encima del pentagrama': 'just above the staff',
    'en la primera línea adicional de abajo': 'on the first ledger line below',
    'en la línea adicional {n} de abajo': 'on ledger line {n} below',
    'debajo de la primera línea adicional': 'below the first ledger line',
    'debajo de la línea adicional {n}': 'below ledger line {n}',
    'en la primera línea adicional de arriba': 'on the first ledger line above',
    'en la línea adicional {n} de arriba': 'on ledger line {n} above',
    'encima de la primera línea adicional': 'above the first ledger line',
    'encima de la línea adicional {n}': 'above ledger line {n}',
    'Es {note}, que en {clef} está {place}.':
        'It is {note}, which in {clef} sits {place}.',
    'En el compás {bar} escribiste {note}, que en {clef} está {place}.':
        'In bar {bar} you wrote {note}, which in {clef} sits {place}.',
    'Es la nota que se pide, pero en otra octava.':
        'It is the note asked for, but in another octave.',
    'Cada nota está donde tiene que estar.': 'Every note is where it belongs.',
    'En {clef}, {note} está {place}, y la nota del compás {bar} no.':
        'In {clef}, {note} sits {place}, and the note in bar {bar} does not.',
    'En {clef}, {note} está {place} y {place2}, y la nota del compás {bar} no.':
        'In {clef}, {note} sits {place} and {place2}, and the note in bar '
        '{bar} does not.',
    'En el compás {bar} las dos cantan {note}. El bajo lo escribe en la clave de fa, {low_place}, y la soprano en la de sol, {high_place}.':
        'In bar {bar} both sing {note}. The bass writes it in the bass clef, '
        '{low_place}, and the soprano in the treble clef, {high_place}.',
    'En el compás {bar} las dos cantan {note}, pero la soprano lo canta una octava más arriba.':
        'In bar {bar} both sing {note}, but the soprano sings it an octave '
        'higher.',
    'En el compás {bar} las dos cantan {note}, pero la soprano lo canta {octaves} octavas más arriba.':
        'In bar {bar} both sing {note}, but the soprano sings it {octaves} '
        'octaves higher.',
    'Buscá la línea de la clave, sol en la de sol y fa en la de fa, y contá desde ahí: una nota por línea y otra por espacio.':
        "Find the clef's line, G in the treble clef and F in the bass clef, "
        "and count from there: one note per line and one per space.",
    'El mismo nombre no alcanza. La misma nota es la misma tecla del piano, y entre las dos claves hay una sola que se puede escribir en las dos.':
        'The same name is not enough. The same note is the same piano key, '
        'and between the two clefs there is only one that can be written in '
        'both.',
    # -- lectura, ritmo, oído y práctica libre
    'Ahora con saltos. La primera nota, sol4, ya está escrita: escribí las otras tres.':
        'Now with leaps. The first note, G4, is already written: write the other three.',
    'Cada compás de 4/4 suma cuatro negras, y a los de la soprano les falta el final. Completalos con las figuras que hagan falta.':
        "Every 4/4 bar adds up to four quarter notes, and the soprano's bars are missing their ending. Complete them with the note values they need.",
    'Cada compás suma cuatro negras.':
        'Every bar adds up to four quarter notes.',
    'Cada compás tiene las figuras que se piden.':
        'Every bar has the note values asked for.',
    'Cantá las dos notas por dentro y contá los nombres que hay entre una y otra, contando las dos.':
        'Sing both notes in your head and count the note names from one to the other, counting both.',
    'Cincuenta y tres ejercicios.':
        'Fifty-three exercises.',
    'Contá las notas de la soprano que empiezan mientras suena la nota larga del bajo.':
        "Count the soprano notes that start while the bass's long note is sounding.",
    'Conviene escucharlo varias veces y escribir de a una nota. Si se mueve por grados, cada nota cae en la línea o el espacio de al lado; si salta, hay que contar los lugares.':
        'It helps to listen several times and write one note at a time. If it moves by step, each note lands on the next line or space; if it leaps, count the places.',
    'De {a} a {b} pasan {count} nombres, {names}: es {interval}.':
        'From {a} to {b} there are {count} note names, {names}: it is {interval}.',
    'El compás':
        'The bar',
    'El dictado':
        'Dictation',
    'El signo vale hasta la barra de compás para ese mismo lugar del pentagrama, así que si la nota se repite en el compás sigue alterada aunque no lo lleve. El becuadro anula la alteración y la nota vuelve a ser natural.':
        'The sign holds until the bar line for that same place on the staff, so if the note comes back in the same bar it is still altered without carrying it. The natural sign cancels the alteration and the note becomes natural again.',
    'En Fa mayor. ¿Qué nota canta el bajo en el compás 2?':
        'In F major. Which note does the bass sing in bar 2?',
    'En Sol mayor. ¿Qué nota canta la soprano en el compás 3?':
        'In G major. Which note does the soprano sing in bar 3?',
    'En el compás {bar} hay tantas notas como se piden, pero no de la figura que se pide.':
        'Bar {bar} has as many notes as asked for, but not the note values asked for.',
    'En el compás {bar} queda un tiempo sin nota.':
        'Bar {bar} has one beat without a note.',
    'En el compás {bar} quedan {beats} tiempos sin nota.':
        'Bar {bar} has {beats} beats without a note.',
    'En el compás {bar} quedó un silencio.':
        'Bar {bar} still has a rest.',
    'En el compás {bar} se pide una sola nota y hay {count}.':
        'Bar {bar} asks for a single note and has {count}.',
    'En el compás {bar} se piden {wanted} notas y hay {count}.':
        'Bar {bar} asks for {wanted} notes and has {count}.',
    'En {clef}, {note} está {place} y {place2}, y la nota resaltada no.':
        'In {clef}, {note} sits {place} and {place2}, and the highlighted note does not.',
    'En {clef}, {note} está {place}, y la nota resaltada no.':
        'In {clef}, {note} sits {place}, and the highlighted note does not.',
    'Es una {figure}, que dura {length}.':
        'It is a {figure}, which lasts {length}.',
    'Escribí en la soprano, con la nota que quieras: una redonda en el compás 1, dos blancas en el 2, y en el 3 dos negras y cuatro corcheas.':
        'Write in the soprano, on any note you like: a whole note in bar 1, two half notes in bar 2, and in bar 3 two quarter notes and four eighth notes.',
    'Escribí en la soprano, una redonda por compás: fa sostenido, si bemol, do sostenido y mi bemol. Elegí el signo antes de hacer click.':
        'Write in the soprano, one whole note per bar: F sharp, B flat, C sharp and E flat. Pick the sign before clicking.',
    'Escuchar y escribir':
        'Listening and writing',
    'Escuchá el dictado. La primera nota, do4, ya está escrita: escribí las otras tres en la soprano, una redonda por compás.':
        'Listen to the dictation. The first note, C4, is already written: write the other three in the soprano, one whole note per bar.',
    'Está a un semitono de la que se pide: fijate el signo.':
        'It is a semitone away from the one asked for: check the sign.',
    'Está escrita en el lugar de {note}, pero algo la altera.':
        'It is written in the place of {note}, but something alters it.',
    'Figuras y compás':
        'Note values and bars',
    'Fijate si la nota lleva un signo, si antes en el mismo compás hay uno en ese mismo lugar, o si la armadura la altera.':
        'Check whether the note carries a sign, whether there is one earlier in the same bar on that same place, or whether the key signature alters it.',
    'La armadura':
        'The key signature',
    'La barra de compás corta la música en tramos iguales. El 4/4 del principio dice que en cada compás entran cuatro negras: una redonda, dos blancas, cuatro negras o cualquier mezcla que sume lo mismo.':
        'The bar line cuts the music into equal stretches. The 4/4 at the start says that each bar holds four quarter notes: a whole note, two half notes, four quarter notes or any mix that adds up the same.',
    'La blanca es una cabeza hueca con plica.':
        'The half note is a hollow head with a stem.',
    'La negra tiene la cabeza llena y plica, sin gancho.':
        'The quarter note has a filled head and a stem, with no flag.',
    'La redonda es una cabeza hueca, sin plica.':
        'The whole note is a hollow head, with no stem.',
    'La soprano canta negras. ¿Qué nota suena en el tercer tiempo del compás 1, la que está resaltada?':
        'The soprano sings quarter notes. Which note sounds on the third beat of bar 1, the highlighted one?',
    'Las figuras':
        'Note values',
    'Lleva un becuadro, que le saca la alteración.':
        'It carries a natural sign, which takes the alteration away.',
    'Lleva un bemol, que la baja un semitono.':
        'It carries a flat, which lowers it a semitone.',
    'Lleva un sostenido, que la sube un semitono.':
        'It carries a sharp, which raises it a semitone.',
    'Lo que dice cuánto dura una nota es su figura. La redonda dura cuatro negras, la blanca dos, la negra una y la corchea media: cada figura vale el doble que la siguiente.':
        'What says how long a note lasts is its note value. The whole note lasts four quarter notes, the half note two, the quarter note one and the eighth note half of one: each value is worth twice the next.',
    'Los intervalos de oído':
        'Intervals by ear',
    'Los sostenidos o bemoles que van al lado de la clave son la armadura. Valen para toda la pieza y en todas las octavas: con un sostenido en la línea del fa, cada fa que aparezca se canta fa sostenido sin que nadie lo vuelva a escribir.':
        'The sharps or flats next to the clef are the key signature. They hold for the whole piece and in every octave: with a sharp on the F line, every F that shows up is sung F sharp without anyone writing it again.',
    'Mientras dura la {long} del {voice}, la {other} canta {count}: cada {short} dura {short_length} y la {long} dura {long_length}.':
        "While the {voice}'s {long} lasts, the {other} sings {count}: each {short} lasts {short_length} and the {long} lasts {long_length}.",
    'Mientras el bajo sostiene la primera blanca, ¿cuántas corcheas canta la soprano?':
        'While the bass holds the first half note, how many eighth notes does the soprano sing?',
    'Mirá la cabeza, hueca o llena, y después si tiene plica y si tiene gancho.':
        'Look at the head, hollow or filled, and then whether it has a stem and whether it has a flag.',
    'No lleva signo, pero antes en el mismo compás hay un {sign} en ese lugar, y vale hasta la barra.':
        'It carries no sign, but earlier in the same bar there is a {sign} on that place, and it holds until the bar line.',
    'No lleva signo, pero la armadura baja un semitono cada {letter} de la pieza.':
        'It carries no sign, but the key signature lowers every {letter} in the piece by a semitone.',
    'No lleva signo, pero la armadura sube un semitono cada {letter} de la pieza.':
        'It carries no sign, but the key signature raises every {letter} in the piece by a semitone.',
    'Octava':
        'Octave',
    'Otras dos, ahora en el bajo. ¿Qué intervalo es?':
        'Two more, now in the bass. Which interval is it?',
    'Oído':
        'Ear',
    'Para reconocerlos sirve cantarlos por dentro y contar los nombres que hay entre una nota y otra: de do a mi pasan do, re y mi, así que es una tercera.':
        'To recognise them it helps to sing them in your head and count the note names from one note to the other: from C to E you pass C, D and E, so it is a third.',
    'Por eso Sol mayor lleva un sostenido y Fa mayor un bemol: son las notas de su escala que no están en la de Do. Para cantar un fa natural en Sol mayor hace falta un becuadro.':
        "That is why G major has one sharp and F major one flat: they are the notes of their scale that are not in C's. To sing an F natural in G major you need a natural sign.",
    'Quinta':
        'Fifth',
    'Re mayor lleva dos sostenidos, fa y do. Escribí en la soprano re, mi, fa y sol, de abajo para arriba y una por compás, sin poner ningún signo: de eso se encarga la armadura.':
        'D major has two sharps, F and C. Write D, E, F and G in the soprano, bottom to top and one per bar, without any sign: the key signature takes care of that.',
    'Ritmo':
        'Rhythm',
    'Segunda':
        'Second',
    'Sostenidos, bemoles y becuadros':
        'Sharps, flats and naturals',
    'Suenan dos notas, una después de la otra. ¿Qué intervalo hay entre ellas?':
        'Two notes sound, one after the other. Which interval is between them?',
    'Tercera':
        'Third',
    'Un compás no puede quedar corto ni pasarse. Lo que falta se llena con notas, o con silencios, que son figuras que se callan lo que duran.':
        'A bar can be neither short nor over. What is missing is filled with notes, or with rests, which are note values that stay silent for as long as they last.',
    'Un dictado es escuchar una melodía y escribirla. La primera nota viene dada, y para cada una de las siguientes se decide si sube o baja y cuánto.':
        'A dictation is hearing a melody and writing it down. The first note is given, and for each of the following ones you decide whether it goes up or down and by how much.',
    'Un intervalo se reconoce de oído antes que de vista. La segunda es el paso de una nota a la de al lado, la tercera suena a acorde, la quinta suena hueca y firme, y la octava es la misma nota más aguda.':
        'An interval is recognised by ear before it is by sight. The second is the step from one note to the next, the third sounds like a chord, the fifth sounds hollow and firm, and the octave is the same note higher.',
    'Un sostenido delante de una nota la sube un semitono, a la tecla de al lado, y un bemol la baja un semitono. Fa sostenido es la tecla negra entre fa y sol, y si bemol la que está entre la y si.':
        'A sharp before a note raises it a semitone, to the next key, and a flat lowers it a semitone. F sharp is the black key between F and G, and B flat the one between A and B.',
    'becuadro':
        'natural',
    'bemol':
        'flat',
    'blanca':
        'half note',
    'corchea':
        'eighth note',
    'cuatro tiempos':
        'four beats',
    'dos tiempos':
        'two beats',
    'medio tiempo':
        'half a beat',
    'negra':
        'quarter note',
    'redonda':
        'whole note',
    'sostenido':
        'sharp',
    'un tiempo':
        'one beat',
    'una octava':
        'an octave',
    'una quinta':
        'a fifth',
    'una segunda':
        'a second',
    'una tercera':
        'a third',
    '¿Qué figura es la segunda nota del compás 1, la que está resaltada?':
        'Which note value is the second note of bar 1, the highlighted one?',
    '¿Qué nota es?':
        'Which note is it?',
    '¿Y acá? ¿Qué nota suena en el tercer tiempo del compás 1?':
        'And here? Which note sounds on the third beat of bar 1?',
    'Clave de fa':
        'Bass clef',
    'Clave de sol':
        'Treble clef',
    'Elegí el signo antes de hacer click: vale para esa nota sola. Click derecho borra.':
        'Pick the sign before clicking: it holds for that note alone. Right-click erases.',
    'Elegí la figura y hacé click para escribirla. Click derecho borra.':
        'Pick the note value and click to write it. Right-click erases.',
    'Escuchá el dictado las veces que haga falta. Click escribe una redonda y click derecho borra.':
        'Listen to the dictation as many times as you need. Click writes a whole note and right-click erases.',
    'Figura':
        'Note value',
    'Las dos':
        'Both',
    'PRÁCTICA LIBRE · NO CUENTA PARA LA GRADUACIÓN':
        'FREE PRACTICE · DOES NOT COUNT TOWARD GRADUATION',
    'Práctica libre de lectura  →':
        'Free reading practice  →',
    'Racha {streak}  ·  mejor {best}':
        'Streak {streak}  ·  best {best}',
    'Racha {streak}  ·  mejor {best}  ·  {seconds} s por nota':
        'Streak {streak}  ·  best {best}  ·  {seconds} s per note',
    'Signo':
        'Sign',
    '←  Volver a la lección':
        '←  Back to the lesson',
    '▶  Dictado':
        '▶  Dictation',
    'En {clef}, {note} está {place} y {place2}, y esta nota no.':
        'In {clef}, {note} sits {place} and {place2}, and this note does not.',
    'En {clef}, {note} está {place}, y esta nota no.':
        'In {clef}, {note} sits {place}, and this note does not.',
    'La corchea tiene la cabeza llena, plica y un gancho, o una barra que la une a las de al lado.':
        'The eighth note has a filled head, a stem and a flag, or a beam that '
        'joins it to its neighbours.',
    'Se distinguen por la forma. La redonda es una cabeza hueca sola, la blanca le agrega la plica, la negra tiene la cabeza llena y la corchea suma un gancho. Varias corcheas seguidas se unen con una barra en vez de llevar cada una el suyo.':
        'You tell them apart by their shape. The whole note is a hollow head '
        'alone, the half note adds the stem, the quarter note has a filled '
        'head and the eighth note adds a flag. Several eighth notes in a row '
        'are joined by a beam instead of each carrying its own flag.',
}
