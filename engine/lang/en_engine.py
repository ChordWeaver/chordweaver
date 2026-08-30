# -*- coding: utf-8 -*-
"""
El motor en inglés: la armonía, el análisis, los avisos de la búsqueda, la
importación y los huevos de pascua.

Las claves son las cadenas castellanas tal cual están en el código. No se
editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    # -- armonía: modos, préstamos, modulaciones y citas ---------------------
    'dórico': 'dorian',
    'Bajo cromático descendente': 'Descending chromatic bass',
    'Ciclo de Vivaldi': 'Vivaldi cycle',
    '7mo bemol mayor (bVII, eólico)': 'Flat seventh major (bVII, aeolian)',
    'Baja una quinta. Suena más relajada que ir al dominante, y es el camino habitual cuando la pieza quiere ensancharse en vez de tensar.':
        'Down a fifth. It sounds more relaxed than going to the dominant, and '
        'it is the usual road when the piece wants to widen out rather than '
        'tighten up.',
    'Desde un centro menor, el salto al relativo mayor. En modo menor es la modulación más habitual junto con el dominante menor.':
        'From a minor centre, the jump to the relative major. In minor it is '
        'the most common modulation along with the minor dominant.',
    'Dominante menor. Al no tener sensible pierde la tensión de resolver, lo que le da un color modal en vez de funcional.':
        'Minor dominant. Having no leading tone it loses the pull to resolve, '
        'which gives it a modal rather than a functional color.',
    'Dórico': 'Dorian',
    'El acorde de tónica se sostiene mientras el bajo baja paso a paso por debajo. Las voces de arriba no se mueven: todo el interés está en esa línea que desciende hasta la dominante.':
        'The tonic chord is held while the bass walks down step by step '
        'underneath. The upper voices do not move: all the interest is in that '
        'line descending to the dominant.',
    'El dominante que reemplaza al V, construido un semitono por encima de la tónica. Comparte con el V su tercera y su séptima -- las dos notas que definen la tensión -- y por eso puede ocupar su lugar y resolver bajando un semitono.':
        'The dominant that replaces V, built a semitone above the tonic. It '
        'shares its third and its seventh with V — the two notes that define '
        'the tension — and that is why it can take its place and resolve down '
        'by a semitone.',
    'El ii del modo menor. Va de la mano del iv prestado y prepara la dominante con un color más oscuro.':
        'The ii of the minor mode. It goes hand in hand with the borrowed iv '
        'and prepares the dominant with a darker color.',
    'El relativo de la subdominante. Cercana, aunque menos frecuente que el dominante o el relativo.':
        'The relative of the subdominant. Close by, though less frequent than '
        'the dominant or the relative.',
    'El relativo del dominante. La más lejana de las cercanas.':
        'The relative of the dominant. The most distant of the close ones.',
    'La modulación más común en modo mayor. Sube una quinta y sólo cambia una nota de la escala, así que el oído la sigue sin esfuerzo.':
        'The most common modulation in major. It goes up a fifth and changes '
        'only one note of the scale, so the ear follows it effortlessly.',
    "La napolitana con su tercera en el bajo, que es como se escribe casi siempre. De ahí el nombre 'de sexta': el bajo queda a una sexta de la fundamental.":
        'The Neapolitan with its third in the bass, which is how it is almost '
        'always written. Hence the name “sixth”: the bass sits a sixth away '
        'from the root.',
    "La subdominante menor prestada del modo menor. El préstamo más común de todos: suaviza la cadencia y es el sonido del 'plagal triste'.":
        'The minor subdominant borrowed from the minor mode. The most common '
        'borrowing of all: it softens the cadence and it is the sound of the '
        '“sad plagal”.',
    'Mayor (jónico)': 'Major (ionian)',
    'Mediante mayor prestada. Da un giro brillante e inesperado hacia el modo menor.':
        'Borrowed major mediant. It gives a bright, unexpected turn toward the '
        'minor mode.',
    'Menor armónica': 'Harmonic minor',
    'Misma tónica, modo dórico: menor pero con la sexta mayor.':
        'Same tonic, dorian mode: minor but with a major sixth.',
    'Misma tónica, modo mayor.': 'Same tonic, major mode.',
    'Misma tónica, modo menor. No es un viaje a otra tonalidad sino un cambio de color sobre el mismo centro.':
        'Same tonic, minor mode. It is not a trip to another key but a change '
        'of color over the same centre.',
    'Misma tónica, modo mixolidio: mayor con la séptima rebajada.':
        'Same tonic, mixolydian mode: major with a flat seventh.',
    'Mismo grupo de notas, otro centro. Al no cambiar ninguna alteración es la modulación más suave que existe.':
        'Same group of notes, different centre. Since no accidental changes, it '
        'is the gentlest modulation there is.',
    'Modal: a dórico': 'Modal: to dorian',
    'Napolitana en estado fundamental: un acorde mayor construido sobre el segundo grado rebajado.':
        'Neapolitan in root position: a major chord built on the flat second '
        'degree.',
    'Submediante mayor prestada. Suele encadenarse con el bVII para volver a la tónica.':
        'Borrowed major submediant. It usually links to the bVII to get back to '
        'the tonic.',
    'Subtónica mayor. Reemplaza a la dominante sin sensible, y es la marca del rock y del modo mixolidio.':
        'Major subtonic. It replaces the dominant without a leading tone, and '
        'it is the mark of rock and of the mixolydian mode.',
    'Supertónica menor (ii)': 'Minor supertonic (ii)',
    'Una cadena de quintas descendentes con los acordes mayorizados, como una hilera de dominantes que se resuelven una en otra hasta llegar a la dominante y volver a casa.':
        'A chain of descending fifths with the chords made major, like a row of '
        'dominants resolving into one another until they reach the dominant and '
        'come home.',
    'i - bVII - bVI - V. El nombre viene del modo frigio: entre el bVI y el V hay sólo un semitono, y esa sensible descendente es la que le da el color.':
        'i - bVII - bVI - V. The name comes from the phrygian mode: between bVI '
        'and V there is only a semitone, and that descending leading tone is '
        'what gives it its color.',

    # -- la fachada: avisos y errores de una corrida -------------------------
    'Acorde {position}: el candado fija {locked} notas pero hay {voice_count} voces, así que se ignoró.':
        'Chord {position}: the padlock fixes {locked} notes but there are '
        '{voice_count} voices, so it was ignored.',
    'Acorde {position}: {reason}': 'Chord {position}: {reason}',
    'La melodía está vacía.': 'The melody is empty.',
    'La pieza no tiene más que silencios.':
        'The piece has nothing but rests in it.',
    'Las dos voces se mueven en paralelo, pero una quinta se escribe como sexta: el recurso con que Bach esquiva las quintas paralelas sin reordenar las voces.':
        'The two voices move in parallel, but one fifth is written as a sixth: '
        'the trick Bach uses to dodge parallel fifths without reordering the '
        'voices.',
    'No cargaste ningún acorde.': 'You have not entered any chord.',
    'No hay acordes disponibles en esta tonalidad.':
        'There are no chords available in this key.',
    'No se encontró ninguna solución válida.': 'No valid solution was found.',
    'No se encontró una solución.': 'No solution was found.',
    'No se pudo armonizar esta melodía.':
        'This melody could not be harmonized.',
    'Sexta en lugar de quinta': 'Sixth in place of a fifth',

    # -- la importación de partituras ---------------------------------------
    'Barítono': 'Baritone',
    'El archivo comprimido no contiene una partitura.':
        'The compressed file does not contain a score.',
    'La partitura no tiene la misma cantidad de voces en todos los acordes (van de {value} a {value2}). Se completará o recortará según las voces que elijas.':
        'The score does not have the same number of voices in every chord (they '
        'run from {value} to {value2}). It will be filled out or trimmed '
        'according to the voices you choose.',
    'La partitura no tiene notas que leer.':
        'The score has no notes to read.',
    'No se encontró ningún acorde: la partitura tiene menos de tres voces sonando a la vez.':
        'No chord was found: the score has fewer than three voices sounding at '
        'once.',
    'No se pudo leer el archivo: {exc}': 'The file could not be read: {exc}',
    'Se ignoraron {skipped} momento(s) con menos de tres notas: son notas de adorno, no acordes, y se descartan para no deformar la progresión.':
        '{skipped} moment(s) with fewer than three notes were ignored: those '
        'are ornamental notes, not chords, and they are dropped so as not to '
        'distort the progression.',
    '{unmatched} acorde(s) no coinciden con ningún cifrado conocido; quedan cargados como notas sueltas.':
        '{unmatched} chord(s) do not match any known chord symbol; they are '
        'loaded as loose notes.',

    # -- el reparto de voces -------------------------------------------------
    '{symbol} tiene {tone_count} notas y hay sólo {voice_count} voces. Ni sacando todo lo prescindible entra: usá más voces o un acorde más simple.':
        '{symbol} has {tone_count} notes and there are only {voice_count} '
        'voices. Even dropping everything expendable it will not fit: use more '
        'voices or a simpler chord.',
    '{symbol} tiene {tone_count} notas y hay {voice_count} voces. Igual se puede escribir dando por sobreentendido: {value}.':
        '{symbol} has {tone_count} notes and there are {voice_count} voices. It '
        'can still be written by leaving these understood: {value}.',

    # -- por qué la búsqueda no encontró nada --------------------------------
    'Con las reglas prendidas no hay ninguna forma de escribir esta progresión. Probá aflojando alguna regla o ampliando el registro de las voces.':
        'With the rules switched on there is no way at all to write this '
        'progression. Try loosening a rule or widening the voices’ ranges.',
    'acordes {numbers} y {numbers2}': 'chords {numbers} and {numbers2}',
    'acordes {value} y {numbers}': 'chords {value} and {numbers}',
    'el acorde fijado {symbol}': 'the pinned chord {symbol}',
    'ninguno de los {requirements} acordes que el generador puede poner acá':
        'none of the {requirements} chords the generator may put here',
    '{name} no llega a ninguna nota de {symbol} (acorde {slot_index}) dentro de su registro':
        '{name} cannot reach any note of {symbol} (chord {slot_index}) within '
        'its range',
    '{subject} es un acorde de reposo y ninguna de sus inversiones queda del todo consonante sobre el bajo. Poné la consonancia como preferencia en vez de exigencia, o cerrá con un acorde más simple.':
        '{subject} is a resting chord and none of its inversions comes out '
        'entirely consonant over the bass. Set consonance as a preference '
        'instead of a requirement, or close with a simpler chord.',
    '{subject} no tiene tritono entre sus notas, pero sí con las de color que le agrega el dial. Bajá el color, o apagá la regla del tritono.':
        '{subject} has no tritone among its own notes, but it does with the '
        'color notes the dial adds to it. Turn the color down, or switch off '
        'the tritone rule.',
    '{subject} tiene un tritono entre sus propias notas, así que no hay manera de escribirlo sin que suene. Apagá esa regla o usá otro acorde.':
        '{subject} has a tritone among its own notes, so there is no way to '
        'write it without that sounding. Switch off that rule or use another '
        'chord.',
    '{subject} tiene una disonancia sobre su propio bajo, y está en un punto de reposo donde se exige consonancia. Cambiá el orden de las voces fijadas, o poné la consonancia como preferencia.':
        '{subject} has a dissonance over its own bass, and it sits at a resting '
        'point where consonance is required. Change the order of the pinned '
        'voices, or set consonance as a preference.',
    '{{subject}} deja a {name} fuera de su registro.':
        '{{subject}} leaves {name} outside its range.',

    # -- las citas de época --------------------------------------------------
    'El V con su quinta en el bajo, la fundamental encima y la tercera arriba: la fórmula que anuncia la cadencia y retrasa un momento la resolución.':
        'The V with its fifth in the bass, the root above it and the third on '
        'top: the formula that announces the cadence and delays the resolution '
        'for a moment.',
    'El V prepara la tónica y cae en el sexto grado: la resolución se posterga y la frase sigue.':
        'The V prepares the tonic and lands on the sixth degree: the resolution '
        'is put off and the phrase goes on.',
    'El giro que sostiene casi todo el repertorio: la subdominante prepara la dominante y ésta resuelve.':
        'The turn that holds up almost the whole repertoire: the subdominant '
        'prepares the dominant and the dominant resolves.',
    'El mismo giro de siempre, pero apuntado a otro grado: toma prestada la dominante de donde va y aterriza ahí.':
        'The same old turn, but aimed at another degree: it borrows the '
        'dominant of where it is going and lands there.',
    'La subdominante cierra directamente sobre la tónica, sin pasar por la dominante.':
        'The subdominant closes straight onto the tonic, without passing '
        'through the dominant.',
    'La subdominante menor cierra sobre la tónica: el mismo gesto que el plagal mayor, más oscuro.':
        'The minor subdominant closes onto the tonic: the same gesture as the '
        'major plagal, darker.',
    'Un dominante a un semitono por encima reemplaza al V y resuelve deslizándose hacia abajo.':
        'A dominant a semitone above replaces the V and resolves by sliding '
        'downward.',

    # -- los timbres del experimentador --------------------------------------
    'Diente de sierra': 'Sawtooth',
    'Órgano': 'Organ',

    # -- los huevos de pascua ------------------------------------------------
    'Adepto del azar': 'Adept of chance',
    'Agradecé que Bach está muerto': 'Be glad Bach is dead',
    'Armonizador. Dibujá exactamente tres notas en el pentagrama: la tónica, la tónica otra vez y la quinta, las tres redondas y sin ninguna más. Tocá «Escuchar».':
        'Harmonizer. Draw exactly three notes on the staff: the tonic, the '
        'tonic again and the fifth, all three whole notes and nothing else. '
        'Press “Play”.',
    'Barroco, con «Modo coral» encendido y las quintas paralelas permitidas al mismo tiempo. Generá.':
        'Baroque, with “Chorale mode” switched on and parallel fifths allowed '
        'at the same time. Generate.',
    'El cerrajero': 'The locksmith',
    'El hongo': 'The mushroom',
    'El rugido': 'The roar',
    'El zorro': 'The fox',
    'Engranaje de configuración. Escribí 1, 9, 8 y 7 en los cuatro primeros campos del algoritmo genético, de arriba hacia abajo, y dale a «Aceptar».':
        'Settings gear. Type 1, 9, 8 and 7 into the first four fields of the '
        'genetic algorithm, from top to bottom, and hit “OK”.',
    'Engranaje de configuración. Llevá el dial del tamaño de letra hasta el tope y soltalo.':
        'Settings gear. Take the text size dial all the way to the top and let '
        'go.',
    'Generador. En la pantalla de armonía, las cinco barras al máximo y absolutamente todos los tildes puestos --- los intercambios modales uno por uno, las séptimas, las dos modulaciones, las cromáticas y las notas de paso de cada voz --- y generá.':
        'Generator. On the harmony screen, all five bars at maximum and '
        'absolutely every box ticked — the modal interchanges one by one, the '
        'sevenths, both modulations, the chromatics and the passing notes for '
        'every voice — and generate.',
    'Los anteojos': 'The glasses',
    'No sé si hiciste trampa o genuinamente lograste todo, pero tu lealtad no ha pasado desapercibida. Gracias por usar mi aplicación.':
        'I do not know whether you cheated or genuinely earned everything, but '
        'your loyalty has not gone unnoticed. Thank you for using my '
        'application.',
    'Organizador. Escribí al menos dos acordes y ponéles el candado a todos, sin dejar ninguno libre. Seguí a la pantalla siguiente.':
        'Organizer. Write at least two chords and put the padlock on every one '
        'of them, leaving none free. Go on to the next screen.',
    'firma: El creador': 'signed: The creator',

    # -- el analizador: adornos ----------------------------------------------
    'Anticipación': 'Anticipation',
    'Baja por grado conjunto, salta una tercera hacia abajo y vuelve a subir por grado conjunto.':
        'It steps down, leaps down a third and steps back up.',
    'Como el retardo, pero resuelve subiendo.':
        'Like a suspension, but it resolves upward.',
    'Llega antes de tiempo a una nota del acorde siguiente.':
        'It arrives early at a note of the next chord.',
    'Llega por salto a una nota ajena en parte fuerte y resuelve por grado conjunto en dirección contraria.':
        'It leaps to a non-chord tone on a strong beat and resolves by step in '
        'the opposite direction.',
    'Nota de paso': 'Passing note',
    'Nota de paso acentuada': 'Accented passing note',
    'Retardo (suspensión)': 'Suspension',
    'Rodea la nota del acorde por arriba y por abajo antes de volver a ella.':
        'It circles the chord tone above and below before returning to it.',
    'Rodea la nota principal por arriba y por abajo y termina en ella: cuatro o cinco notas rápidas.':
        'It circles the main note above and below and ends on it: four or five '
        'quick notes.',
    'Se aparta de una nota del acorde por grado conjunto y vuelve a ella.':
        'It steps away from a chord tone and comes back to it.',
    'Se va de la nota del acorde por grado conjunto y salta en dirección contraria.':
        'It leaves the chord tone by step and leaps in the opposite direction.',
    'Un golpe rapidísimo a la nota vecina y vuelta inmediata.':
        'A very quick strike at the neighbouring note and an immediate return.',
    'Una nota de paso que cae en parte fuerte, sonando contra el acorde antes de resolver.':
        'A passing note landing on a strong beat, sounding against the chord '
        'before it resolves.',
    'Una nota del acorde anterior se queda sonando sobre el acorde nuevo y baja después por grado conjunto.':
        'A note of the previous chord stays sounding over the new chord and '
        'then steps down.',
    'Una nota que se sostiene mientras la armonía cambia por encima o por debajo.':
        'A note held while the harmony changes above or below it.',
    'Una o más notas que preceden al primer tiempo fuerte de una frase.':
        'One or more notes preceding the first strong beat of a phrase.',
    'Une dos notas del acorde por grados conjuntos, en la misma dirección. Cae en parte débil.':
        'It joins two chord tones by step, in the same direction. It falls on a '
        'weak beat.',

    # -- el analizador: contrapunto ------------------------------------------
    'Cruce de voces': 'Voice crossing',
    'Salto de trítono': 'Tritone leap',
    'Unísono entre voces vecinas': 'Unison between neighbouring voices',
    '{voice_name} baja por debajo de donde estaba {voice_name2}':
        '{voice_name} drops below where {voice_name2} was',
    '{voice_name} canta por encima de {voice_name2}':
        '{voice_name} sings above {voice_name2}',
    '{voice_name} salta un trítono: es el salto más difícil de cantar y la escritura vocal lo evita':
        '{voice_name} leaps a tritone: it is the hardest leap to sing and vocal '
        'writing avoids it',
    '{voice_name} sube por encima de donde estaba {voice_name2}':
        '{voice_name} rises above where {voice_name2} was',
    '{voice_name} y {voice_name2} caen en la misma nota: la textura pierde una voz':
        '{voice_name} and {voice_name2} land on the same note: the texture '
        'loses a voice',
    '{voice_name} y {voice_name2} se mueven en la misma dirección conservando ':
        '{voice_name} and {voice_name2} move in the same direction, keeping ',
    'la octava': 'the octave',
    'la quinta justa': 'the perfect fifth',
    'las voces extremas llegan por movimiento directo a una consonancia perfecta, y la superior llega por salto':
        'the outer voices arrive at a perfect consonance by direct motion, and '
        'the upper one arrives by leap',
    'las dos en la misma dirección pero cambiando de intervalo; es por acá que se hacen las quintas ocultas':
        'both in the same direction but changing interval; this is where hidden '
        'fifths come from',
    'misma fundamental': 'same root',

    # -- el analizador: movimiento -------------------------------------------
    'ascenso de cuarta (descenso de quinta)': 'up a fourth (down a fifth)',
    'ascenso de quinta (descenso de cuarta)': 'up a fifth (down a fourth)',
    'ascenso de segunda': 'up a second',
    'ascenso de semitono': 'up a semitone',
    'ascenso de tercera mayor': 'up a major third',
    'ascenso de tercera menor': 'up a minor third',
    'descenso de segunda': 'down a second',
    'descenso de semitono': 'down a semitone',
    'descenso de tercera mayor': 'down a major third',
    'descenso de tercera menor': 'down a minor third',

    # -- el analizador: tonalidad y cadencias --------------------------------
    ' Acá aparece sobre {spanish_note}, que no es la tónica de la pieza.':
        ' Here it appears over {spanish_note}, which is not the tonic of the '
        'piece.',
    ', pero alguno de los dos está invertido':
        ', but one of the two is inverted',
    ', pero entre notas de adorno y no entre acordes':
        ', but between ornamental notes and not between chords',
    ', y la pieza vuelve enseguida': ', and the piece comes straight back',
    ': la pieza se instala ahí': ': the piece settles in there',
    'La partitura no tiene notas que analizar.':
        'The score has no notes to analyse.',
    'La tonalidad no está clara: {label} es la lectura más probable, pero hay otras cerca.':
        'The key is not clear: {label} is the most likely reading, but there '
        'are others close behind.',
    'arranca desde la tónica en el bajo':
        'it starts from the tonic in the bass',
    'arranca en la tónica': 'it starts on the tonic',
    'arranca en la tónica y se detiene sobre su dominante: la frase queda en semicadencia':
        'it starts on the tonic and stops on its dominant: the phrase is left '
        'on a half cadence',
    'baja por grado conjunto, salta una tercera hacia abajo y vuelve subiendo':
        'it steps down, leaps down a third and comes back up',
    'cada acorde es la dominante del que le sigue: la pieza no se fue de la tonalidad, viene cayendo por quintas hasta volver a ella':
        'each chord is the dominant of the next: the piece has not left the '
        'key, it is falling by fifths on its way back to it',
    'cadena de {end} dominantes': 'chain of {end} dominants',
    'cadencia auténtica imperfecta': 'imperfect authentic cadence',
    'cadencia auténtica perfecta': 'perfect authentic cadence',
    'cierra con una cadencia sobre la dominante':
        'it closes with a cadence on the dominant',
    'cromático': 'chromatic',
    'cuarta suspendida sin resolver': 'unresolved suspended fourth',
    'diatónico': 'diatonic',
    'el bajo baja un semitono desde el cuarto grado hasta la dominante':
        'the bass falls a semitone from the fourth degree to the dominant',
    'el último acorde es {symbol}': 'the last chord is {symbol}',
    'empieza y termina en el mismo acorde':
        'it starts and ends on the same chord',
    'entra y sale por grado conjunto en la misma dirección':
        'it enters and leaves by step in the same direction',
    'estos acordes son todos diatónicos de ':
        'these chords are all diatonic to ',
    'está antes del primer compás completo: es la anacrusa de la pieza':
        'it comes before the first complete measure: it is the pickup of the '
        'piece',
    'final de la pieza': 'end of the piece',
    'golpe a la nota vecina y vuelta inmediata':
        'a strike at the neighbouring note and an immediate return',
    'interdominante: es la dominante de {target_name} ({numeral}), y ':
        'secondary dominant: it is the dominant of {target_name} ({numeral}), '
        'and ',
    'la cuarta baja a la tercera sobre la misma fundamental: es una suspensión resuelta':
        'the fourth falls to the third over the same root: it is a resolved '
        'suspension',
    'la cuarta ocupa el lugar de la tercera y no se corrige: queda como sonoridad suspendida':
        'the fourth takes the place of the third and is never corrected: it '
        'stays a suspended sonority',
    'la dominante promete la tónica y entrega el sexto grado':
        'the dominant promises the tonic and delivers the sixth degree',
    'la dominante resuelve en la tónica':
        'the dominant resolves onto the tonic',
    'la frase se detiene sobre la dominante':
        'the phrase comes to rest on the dominant',
    'la pieza reposa sobre la tónica en el bajo':
        'the piece comes to rest on the tonic in the bass',
    'la subdominante llega a la tónica sin pasar por la dominante':
        'the subdominant reaches the tonic without passing through the dominant',
    'la voz vuelve a entrar sobre el final del compás y sigue en el tiempo fuerte: entra en anacrusa':
        'the voice comes back in at the end of the measure and carries on '
        'through the strong beat: it enters as a pickup',
    'llega antes de tiempo a una nota del acorde siguiente':
        'it arrives early at a note of the next chord',
    'llega por salto a una nota ajena en parte fuerte y resuelve por grado conjunto':
        'it leaps to a non-chord tone on a strong beat and resolves by step',
    'llega por salto y resuelve por grado conjunto':
        'it arrives by leap and resolves by step',
    'mayor (jónico)': 'major (ionian)',
    'menor armónica': 'harmonic minor',
    'menor melódica': 'melodic minor',
    'menor natural (eólico)': 'natural minor (aeolian)',
    'modulación a ': 'modulation to ',
    'movimiento cromático': 'chromatic motion',
    'no comparten una tonalidad: son colores sueltos, no una visita a otra parte':
        'they do not share a key: they are loose colors, not a visit somewhere '
        'else',
    'no llega a resolver': 'it never resolves',
    'no pertenece a la escala ni se explica como dominante aplicada o préstamo: es un acorde cromático':
        'it does not belong to the scale and cannot be explained as a secondary '
        'dominant or a borrowing: it is a chromatic chord',
    'no se pudo nombrar el acorde': 'the chord could not be named',
    'préstamo del {mode_label} de {spanish_note}: ahí es el {degree}º grado':
        'borrowed from the {mode_label} of {spanish_note}: there it is the '
        'degree {degree} chord',
    'queda sonando del acorde anterior y no resuelve':
        'it is left sounding from the previous chord and never resolves',
    'reemplaza a la dominante de {spanish_note}: comparte con ella la tercera y la séptima y resuelve bajando un semitono':
        'it replaces the dominant of {spanish_note}: it shares its third and '
        'its seventh and resolves down by a semitone',
    'resuelve en él': 'it resolves onto it',
    'rodea la nota del acorde por arriba y por abajo y vuelve a ella':
        'it circles the chord tone above and below and returns to it',
    'se aparta por grado conjunto hacia arriba y vuelve a la misma nota':
        'it steps away upward and comes back to the same note',
    'se aparta por grado conjunto hacia abajo y vuelve a la misma nota':
        'it steps away downward and comes back to the same note',
    'se sostiene durante {covered} acordes y no pertenece a {foreign} de ellos':
        'it is held across {covered} chords and does not belong to {foreign} of '
        'them',
    'se va por grado conjunto y salta en dirección contraria':
        'it leaves by step and leaps in the opposite direction',
    'sensible aplicada: está un semitono debajo de {spanish_note} y ':
        'applied leading tone: it sits a semitone below {spanish_note} and ',
    'termina con tercera de Picardía': 'it ends with a Picardy third',
    'tonicización de ': 'tonicization of ',
    'tónica': 'tonic',
    'usa exactamente las notas de la armadura':
        'it uses exactly the notes of the key signature',
    'viene sonando del acorde anterior y baja por grado conjunto a una nota del acorde':
        'it carries over from the previous chord and steps down to a chord tone',
    'viene sonando del acorde anterior y sube por grado conjunto':
        'it carries over from the previous chord and steps up',
    '{degree}º grado de {label}': 'degree {degree} of {label}',
    '{symbol} resuelve en {symbol2}': '{symbol} resolves onto {symbol2}',
    'las dos en la misma dirección y con el intervalo del mismo tamaño: es lo que funde dos voces en una':
        'both in the same direction and keeping the interval the same size: it '
        'is what melts two voices into one',
}
