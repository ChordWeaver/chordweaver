# -*- coding: utf-8 -*-
"""
Las herramientas en inglés: el analizador, el experimentador de armónicos,
el pentagrama, las cinemáticas, el cartel de versión nueva, el de idioma y
la línea de comandos.

Las claves son las cadenas castellanas tal cual están en el código. No se
editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    # -- el analizador -------------------------------------------------------
    '\n\nLa partitura traía {trimmed} voz/voces más. El sistema de dos pentagramas escribe hasta cuatro, así que se conservaron las cuatro más graves.':
        '\n\nThe score carried {trimmed} more voice(s). The grand staff writes '
        'up to four, so the four lowest were kept.',
    ' · compás {bar}, tiempo {beat:g}': ' · measure {bar}, beat {beat:g}',
    ' · es {value} de {symbol}': ' · it is {value} of {symbol}',
    ' · no pertenece a {symbol}': ' · it does not belong to {symbol}',
    ', {graves} grave(s)': ', {graves} serious',
    'Acordes, uno por uno': 'Chords, one by one',
    'Acá van los movimientos entre voces y lo que convenga mirar: paralelas, saltos difíciles, cruces.':
        'Here go the motions between voices and whatever is worth a look: '
        'parallels, difficult leaps, crossings.',
    'Adornos melódicos': 'Melodic ornaments',
    'Análisis': 'Analysis',
    'El archivo no se pudo leer: {exc}': 'The file could not be read: {exc}',
    'Escribo la': 'I am writing the',
    'Escribí las voces en el sistema o importá una partitura. Con tres voces escritas aparece acá la tonalidad, los acordes y lo que hace cada uno.\n\nSi no tenés ninguna a mano, «Importar…» abre en la carpeta de ejemplos: ahí está el Preludio en Do mayor de Bach.':
        'Write the voices on the staff or import a score. With three voices '
        'written, the key, the chords and what each one does appear '
        'here.\n\nIf you have none at hand, “Import…” opens in the examples '
        'folder: Bach’s Prelude in C major is in there.',
    'Escribí o importá una partitura primero.':
        'Write or import a score first.',
    'Esto saca del pentagrama todo lo que hay escrito. ¿Seguimos?':
        'This clears everything written on the staff. Shall we go on?',
    'Falta {missing} voz: un acorde son tres notas sonando, así que hasta que no haya tres voces escritas no hay nada que nombrar.':
        '{missing} voice still missing: a chord is three notes sounding, so '
        'until there are three voices written there is nothing to name.',
    'Faltan {missing} voces: un acorde son tres notas sonando, así que hasta que no haya tres voces escritas no hay nada que nombrar.':
        '{missing} voices still missing: a chord is three notes sounding, so '
        'until there are three voices written there is nothing to name.',
    'Movimiento entre voces': 'Motion between voices',
    'Nada que escuchar': 'Nothing to listen to',
    'Nada que exportar': 'Nothing to export',
    'Ni paralelas, ni cruces, ni saltos difíciles: el contrapunto está limpio.':
        'No parallels, no crossings, no difficult leaps: the counterpoint is '
        'clean.',
    'Ninguna nota se sale del acorde: toda la escritura es de notas reales.':
        'No note steps outside its chord: the whole texture is chord tones.',
    'No se pudo exportar': 'Could not export',
    'Pasá el mouse por una nota y acá dice cuál es. Click escribe, botón derecho borra; Tab cambia de voz y Ctrl+Z deshace.':
        'Hover over a note and it says which one it is here. Click writes, '
        'right-click erases; Tab changes voice and Ctrl+Z undoes.',
    'Pasá el mouse por uno y abajo dice qué es; tocalo y se marca en el sistema.':
        'Hover over one and it says what it is below; click it and it is marked '
        'on the staff.',
    'Se leyeron {parts} voces: {lower}.': 'Read {parts} voices: {lower}.',
    'Silencio': 'Rest',
    'Sin partitura todavía': 'No score yet',
    'También se puede leer {symbol}. ': 'It can also be read as {symbol}. ',
    'Tocá uno para ver dónde cae en la partitura.':
        'Click one to see where it falls in the score.',
    'Tocá uno y se marcan sobre el sistema: un trazo une las dos voces del par y una flecha dice adónde va cada una.':
        'Click one and they are marked on the staff: a stroke joins the two '
        'voices of the pair and an arrow says where each one goes.',
    'Todavía no hay ninguna nota escrita. Poné algunas en el sistema o importá una partitura.':
        'No note has been written yet. Put some on the staff or import a score.',
    'Y acá, los adornos melódicos: las notas que no pertenecen al acorde, con el nombre que les corresponde.':
        'And here, the melodic ornaments: the notes that do not belong to the '
        'chord, each under its proper name.',
    'blanca con puntillo': 'dotted half note',
    'c. {bar}': 'm. {bar}',
    'c.{bar}': 'm.{bar}',
    'c.{bar} · t.{beat:g}': 'm.{bar} · b.{beat:g}',
    'corchea con puntillo': 'dotted eighth note',
    'desde el c.': 'from m.',
    'la fundamental': 'the root',
    'la quinta': 'the fifth',
    'la séptima': 'the seventh',
    'la tercera': 'the third',
    'las dos en la misma dirección pero cambiando de intervalo; es por acá que se hacen las quintas ocultas':
        'both in the same direction but changing interval; this is where hidden '
        'fifths come from',
    'las dos en la misma dirección y con el intervalo del mismo tamaño: es lo que funde dos voces en una':
        'both in the same direction and keeping the interval the same size: it '
        'is what melts two voices into one',
    'las dos voces se mueven en direcciones opuestas: es lo que las mantiene independientes':
        'the two voices move in opposite directions: it is what keeps them '
        'independent',
    'negra con puntillo': 'dotted quarter note',
    'ninguna de las dos se movió': 'neither of the two moved',
    'no hay mucho en qué apoyarse': 'there is not much to go on',
    'sólo ese': 'that one only',
    'una se queda quieta y la otra se mueve': 'one stays put and the other moves',
    '{b}/{t} desde el c.{bar}': '{b}/{t} from m.{bar}',
    '{duration:g} negras': '{duration:g} quarter notes',
    '{findings} cosa(s) para mirar': '{findings} thing(s) to look at',
    '{ornaments} adorno(s) melódico(s)': '{ornaments} melodic ornament(s)',
    '{written} de {MIN_VOICES} voces escritas':
        '{written} of {MIN_VOICES} voices written',
    '↓  ': '↓  ',
    '↶  Deshacer': '↶  Undo',

    # -- el experimentador de armónicos --------------------------------------
    '  y sus múltiplos': '  and its multiples',
    'Aislado': 'Soloed',
    'Aislado: es lo único que estás oyendo. ':
        'Soloed: it is the only thing you are hearing. ',
    'Aislar': 'Solo',
    'Armónico {number:>2}   {hz_label:>10}   ≈ {note_label} {cents_label}   ·   {interval_label}':
        'Harmonic {number:>2}   {hz_label:>10}   ≈ {note_label} {cents_label}'
        '   ·   {interval_label}',
    'Arrastrala para arriba y la amplificás; para el costado, la corrés de su lugar exacto y la desafinás.':
        'Drag it up and you amplify it; drag it sideways and you shift it off '
        'its exact place and detune it.',
    'ChordWeaver {preset_name} {name}.wav':
        'ChordWeaver {preset_name} {name}.wav',
    'Corrido {cents_label} de su múltiplo exacto. Contra los demás produce pulsaciones: dos frecuencias casi iguales se suman y se restan por turno.':
        'Shifted {cents_label} from its exact multiple. Against the others it '
        'produces beats: two nearly equal frequencies add up and cancel out by '
        'turns.',
    'Dos octavas y una quinta.': 'Two octaves and a fifth.',
    'Dos octavas y una tercera mayor. Cae catorce cents por debajo de la tercera del piano: por eso un acorde afinado a oído no es el mismo que uno afinado a teclado.':
        'Two octaves and a major third. It falls fourteen cents below the '
        'piano’s third: that is why a chord tuned by ear is not the same as one '
        'tuned to a keyboard.',
    'El armónico elegido': 'The chosen harmonic',
    'Forma de onda': 'Waveform',
    'Fundamental: {note_label} · {hz_label}':
        'Fundamental: {note_label} · {hz_label}',
    'Guardando…': 'Saving…',
    'Guardar el timbre como muestra': 'Save the timbre as a sample',
    'Guardar timbre…': 'Save timbre…',
    'La nota de la que salen': 'The note they come from',
    'La nota que creés estar oyendo. Casi nunca es la más fuerte.':
        'The note you think you are hearing. It is almost never the loudest.',
    'Muestra de sampler': 'Sampler instrument',
    'Ni cuarta ni tritono: queda justo en el medio de los dos. Las trompas naturales lo tenían y sonaba desafinado a propósito.':
        'Neither a fourth nor a tritone: it sits right between the two. Natural '
        'horns had it and it sounded out of tune on purpose.',
    'Ninguna cosa que suena da una frecuencia sola: da la suya y además sus múltiplos enteros. Cada barra es uno de esos múltiplos.':
        'Nothing that sounds gives off a single frequency: it gives off its own '
        'and, on top of that, whole-number multiples of it. Each bar is one of '
        'those multiples.',
    'No se pudo guardar': 'Could not save',
    'Reiniciar': 'Reset',
    'Se guardó {basename}.\n\nEl archivo dice adentro que la muestra es un {name} y que el tramo que se repite dura {seconds:.1f} s, así que cualquier sampler que lea WAV —TX16Wx, Kontakt, el AudioFileProcessor de LMMS, el Simpler de Live, Polyphone para armar un SoundFont— lo toma afinado en todo el teclado y lo sostiene mientras la tecla siga apretada.':
        '{basename} saved.\n\nThe file says inside that the sample is a {name} '
        'and that the looping stretch lasts {seconds:.1f} s, so any sampler '
        'that reads WAV — TX16Wx, Kontakt, LMMS’s AudioFileProcessor, Live’s '
        'Simpler, Polyphone for building a SoundFont — will take it in tune '
        'across the whole keyboard and sustain it as long as the key is held.',
    'Silenciado': 'Muted',
    'Silenciar': 'Mute',
    'Timbre guardado': 'Timbre saved',
    'Todos a la vez': 'All at once',
    'Tres octavas y una quinta.': 'Three octaves and a fifth.',
    'Tres octavas y una segunda mayor: la novena de los acordes.':
        'Three octaves and a major second: the ninth of the chords.',
    'Tres octavas y una tercera mayor.': 'Three octaves and a major third.',
    'Trémolo': 'Tremolo',
    'Una nota, desarmada': 'One note, taken apart',
    'Una octava justa arriba. Duplicar la frecuencia es la única operación que el oído no escucha como otra nota.':
        'A perfect octave above. Doubling the frequency is the only operation '
        'the ear does not hear as a different note.',
    'Una octava y una quinta. De acá sale la quinta, que es el intervalo del que cuelga toda la armonía.':
        'An octave and a fifth. This is where the fifth comes from, the '
        'interval all of harmony hangs off.',
    'Una séptima que **no existe** en ninguna escala: cae treinta y un cents por debajo de la del piano. Es el sonido del blues, y es lo que un instrumento temperado no puede tocar.':
        'A seventh that **does not exist** in any scale: it falls thirty-one '
        'cents below the piano’s. It is the sound of the blues, and it is what '
        'a tempered instrument cannot play.',
    'el volumen oscila': 'the volume wavers',
    'frecuencia →': 'frequency →',
    'la afinación oscila': 'the pitch wavers',
    'unísono': 'unison',
    '{frequency:.0f} Hz': '{frequency:.0f} Hz',
    '{octaves} octavas': '{octaves} octaves',
    '♪  Sonando': '♪  Playing',

    # -- los intervalos de la serie armónica ---------------------------------
    'unísono': 'unison',
    '2ª menor': 'minor 2nd',
    '2ª mayor': 'major 2nd',
    '3ª menor': 'minor 3rd',
    '3ª mayor': 'major 3rd',
    '4ª justa': 'perfect 4th',
    'tritono': 'tritone',
    '5ª justa': 'perfect 5th',
    '6ª menor': 'minor 6th',
    '6ª mayor': 'major 6th',
    '7ª menor': 'minor 7th',
    '7ª mayor': 'major 7th',
    '1 octava': '1 octave',
    'justo': 'exact',

    # -- el pentagrama -------------------------------------------------------
    'Elegí una voz y hacé click donde va cada nota, o importá una partitura.':
        'Choose a voice and click where each note goes, or import a score.',
    'Hacé click en el pentagrama para escribir la melodía':
        'Click on the staff to write the melody',

    # -- las cinemáticas -----------------------------------------------------
    'Has recibido': 'You have received',
    '—  algo interrumpe el trabajo  —': '—  something interrupts the work  —',

    # -- el cartel de versión nueva ------------------------------------------
    'Actualizar': 'Update',
    'Ahora no': 'Not now',
    'ChordWeaver %s  ·  la tuya es la %s': 'ChordWeaver %s  ·  yours is %s',
    'Hay una versión nueva': 'There is a new version',
    'Tu progreso no se pierde: los logros, el libro, el sendero y el historial se copian a la carpeta nueva. La página explica cómo.':
        'Your progress is not lost: the achievements, the book, the path and '
        'the history are copied over to the new folder. The page explains how.',

    # -- el cartel del idioma ------------------------------------------------
    #
    # Estas tres no se usan nunca: el cartel del idioma se dibuja antes de que
    # haya un idioma elegido y está escrito en los dos a la vez, así que no
    # pasa por `tr()`. Están acá para que el catálogo no tenga un agujero.
    'Castellano rioplatense, el idioma en el que está escrito el programa. Las notas se dicen Do, Re, Mi.':
        'River Plate Spanish, the language the program is written in. Notes are '
        'called Do, Re, Mi.',
    'Elegí tu idioma': 'Choose your language',
    'Se puede cambiar cuando quieras desde el engranaje.':
        'You can change it any time from the gear.',

    # -- la línea de comandos ------------------------------------------------
    '\nSearched {generations_run} generations, {evaluated} evaluations.\n':
        '\nSearched {generations_run} generations, {evaluated} evaluations.\n',
    '  error: {error}': '  error: {error}',
    '  warning: {warning}': '  warning: {warning}',
    'Comma-separated voice keys from: {value}':
        'Comma-separated voice keys from: {value}',
    'Genre: {genre} | voices: {voices} | {signature} | {entries} chords':
        'Genre: {genre} | voices: {voices} | {signature} | {entries} chords',
    'Option {index}  (cost {cost:.0f})': 'Option {index}  (cost {cost:.0f})',
    'compás inválido: {value!r}. Los dos números tienen que ser mayores que cero.':
        'invalid metre: {value!r}. Both numbers have to be greater than zero.',
    'compás inválido: {value!r}. Se escribe como 4/4 o 6/8.':
        'invalid metre: {value!r}. It is written like 4/4 or 6/8.',
    'duración inválida: {value!r}': 'invalid duration: {value!r}',
    'la duración tiene que ser mayor que cero: con 0 la partitura sale con notas de duración nula y no la abre ningún editor.':
        'the duration has to be greater than zero: with 0 the score comes out '
        'with zero-length notes and no editor will open it.',
}
