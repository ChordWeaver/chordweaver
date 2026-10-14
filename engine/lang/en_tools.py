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
    'Jazz': 'Jazz',
    'juzgado como': 'judged as',
    ', algo que este estilo permite': ', which this style allows',
    'La partitura tiene {voices} voces y el sistema admite cuatro. En cada momento quedan la nota más grave, la más aguda y las dos del medio que más le agregan al acorde.':
        'The score has {voices} voices and the staff holds four. At each '
        'moment it keeps the lowest note, the highest, and the two inner '
        'notes that add the most to the chord.',
    ' · compás {bar}, tiempo {beat:g}': ' · measure {bar}, beat {beat:g}',
    ' · es {value} de {symbol}': ' · it is {value} of {symbol}',
    ' · no pertenece a {symbol}': ' · it does not belong to {symbol}',
    ', {graves} grave(s)': ', {graves} serious',
    'Acordes, uno por uno': 'Chords, one by one',
    'Acá aparecen los movimientos entre voces y lo que conviene revisar, como paralelas, saltos difíciles o cruces.':
        'This is where the motion between voices shows up, along with '
        'anything worth checking, like parallels, awkward leaps or crossings.',
    'Adornos melódicos': 'Melodic ornaments',
    'lectura dudosa': 'uncertain reading',
    'lectura probable': 'likely reading',
    'lectura clara': 'clear reading',
    'Exportar…': 'Export…',
    'Contrapunto': 'Counterpoint',
    'Análisis': 'Analysis',
    'El archivo no se pudo leer: {exc}': 'The file could not be read: {exc}',
    'Escribo la': 'I am writing the',
    'Escribí las voces en el sistema o importá una partitura. Con tres voces escritas, acá aparecen la tonalidad y los acordes.\n\n«Importar…» abre la carpeta de ejemplos, donde está el Preludio en Do mayor de Bach.':
        'Write the voices on the staff or import a score. Once three voices '
        'are written, the key and the chords show up here.\n\n'
        '“Import…” opens the examples folder, which has Bach’s Prelude in C '
        'major.',
    'Escribí o importá una partitura primero.':
        'Write or import a score first.',
    'Se borra todo lo escrito. ¿Seguimos?':
        'Everything written will be erased. Continue?',
    'Falta {missing} voz. Para nombrar acordes hacen falta al menos tres voces escritas.':
        '{missing} voice missing. Naming chords takes at least three written '
        'voices.',
    'Faltan {missing} voces. Para nombrar acordes hacen falta al menos tres voces escritas.':
        '{missing} voices missing. Naming chords takes at least three written '
        'voices.',
    'Movimiento entre voces': 'Motion between voices',
    'Nada que escuchar': 'Nothing to listen to',
    'Nada que exportar': 'Nothing to export',
    'No hay paralelas, cruces ni saltos difíciles.':
        'No parallels, crossings or awkward leaps.',
    'Todas las notas pertenecen a su acorde.':
        'Every note belongs to its chord.',
    'No se pudo exportar': 'Could not export',
    'Pasá el mouse por una nota para ver cuál es. Click escribe, click derecho borra, Tab cambia de voz y Ctrl+Z deshace.':
        'Hover over a note to see which one it is. Click writes, right-click '
        'erases, Tab switches voice and Ctrl+Z undoes.',
    'Pasá el mouse por uno para ver qué es, y tocalo para marcarlo en el sistema.':
        'Hover over one to see what it is, and click it to mark it on the '
        'staff.',
    'Se leyeron {parts} voces: {lower}.': 'Read {parts} voices: {lower}.',
    'Silencio': 'Rest',
    'Sin partitura todavía': 'No score yet',
    'También se puede leer {symbol}. ': 'It can also be read as {symbol}. ',
    'Tocá uno para ver dónde cae en la partitura.':
        'Click one to see where it falls in the score.',
    'Tocá uno para marcarlo en el sistema. Un trazo une las dos voces y una flecha muestra adónde va cada una.':
        'Click one to mark it on the staff. A line joins the two voices and '
        'an arrow shows where each one goes.',
    'Todavía no hay notas. Escribí algunas en el sistema o importá una partitura.':
        'There are no notes yet. Write some on the staff or import a score.',
    'Y acá, las notas que no pertenecen al acorde, cada una con su nombre.':
        'And here, the notes that don’t belong to the chord, each with its '
        'name.',
    'blanca con puntillo': 'dotted half note',
    'c. {bar}': 'm. {bar}',
    'c.{bar}': 'm.{bar}',
    'c. {bar}  ·  {kind}': 'm. {bar}  ·  {kind}',
    'c.{bar} · t.{beat:g}': 'm.{bar} · b.{beat:g}',
    'corchea con puntillo': 'dotted eighth note',
    'desde el c.': 'from m.',
    'la fundamental': 'the root',
    'la quinta': 'the fifth',
    'la séptima': 'the seventh',
    'la tercera': 'the third',
    'las dos en la misma dirección pero con otro intervalo. De acá salen las quintas ocultas':
        'both in the same direction but changing interval. This is where '
        'hidden fifths come from',
    'las dos en la misma dirección y con el mismo intervalo, lo que funde dos voces en una':
        'both in the same direction with the same interval, which blends two '
        'voices into one',
    'las dos voces van en direcciones opuestas, lo que las mantiene independientes':
        'the two voices go in opposite directions, which keeps them '
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
    '↶  Deshacer': '↶  Undo',

    # -- el experimentador de armónicos --------------------------------------
    '{frequency}  y sus múltiplos': '{frequency}  and its multiples',
    'Aislado': 'Soloed',
    'Aislado, es lo único que suena. ':
        'Soloed, it’s the only thing playing. ',
    'Aislar': 'Solo',
    'Armónico {number:>2}   {hz_label:>10}   ≈ {note_label} {cents_label}   ·   {interval_label}':
        'Harmonic {number:>2}   {hz_label:>10}   ≈ {note_label} {cents_label}'
        '   ·   {interval_label}',
    'Arrastrá una barra hacia arriba para subirla, o hacia el costado para desafinarla.':
        'Drag a bar up to boost it, or sideways to detune it.',
    'ChordWeaver {preset_name} {name}.wav':
        'ChordWeaver {preset_name} {name}.wav',
    'Corrido {cents_label} de su múltiplo exacto. Contra los demás produce pulsaciones, porque dos frecuencias casi iguales se suman y se restan por turnos.':
        'Shifted {cents_label} from its exact multiple. Against the others it '
        'produces beating, because two nearly equal frequencies add up and '
        'cancel out in turn.',
    'Dos octavas y una quinta.': 'Two octaves and a fifth.',
    'Dos octavas.': 'Two octaves.',
    'Dos octavas y una tercera mayor. Cae catorce cents por debajo de la tercera del piano, y por eso un acorde afinado de oído no suena igual que uno afinado en un teclado.':
        'Two octaves and a major third. It falls fourteen cents below the '
        'piano’s third, which is why a chord tuned by ear doesn’t sound the '
        'same as one tuned on a keyboard.',
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
    'Queda justo entre la cuarta y el tritono. Las trompas naturales lo tenían, y sonaba desafinado a propósito.':
        'It falls right between the fourth and the tritone. Natural horns had '
        'it, and it sounded out of tune on purpose.',
    'Todo sonido tiene una frecuencia de base y además sus múltiplos enteros. Cada barra es uno de esos múltiplos.':
        'Every sound has a base frequency plus its whole-number multiples. '
        'Each bar is one of those multiples.',
    'No se pudo guardar': 'Could not save',
    'Reiniciar': 'Reset',
    'Se guardó {basename}.\n\nEl archivo indica que la muestra es un {name} y que el bucle dura {seconds:.1f} s. Cualquier sampler que lea WAV (TX16Wx, Kontakt, el AudioFileProcessor de LMMS, el Simpler de Live o Polyphone para armar un SoundFont) lo va a tocar afinado en todo el teclado y sostenido mientras la tecla esté apretada.':
        '{basename} saved.\n\n'
        'The file marks the sample as a {name} with a {seconds:.1f} s loop. '
        'Any sampler that reads WAV (TX16Wx, Kontakt, LMMS’s '
        'AudioFileProcessor, Live’s Simpler, or Polyphone to build a '
        'SoundFont) will play it in tune across the keyboard and sustain it '
        'while the key is held.',
    'Silenciado': 'Muted',
    'Silenciar': 'Mute',
    'Timbre guardado': 'Timbre saved',
    'Todos a la vez': 'All at once',
    'Centrar': 'Center',
    'Tres octavas y una quinta.': 'Three octaves and a fifth.',
    'Tres octavas.': 'Three octaves.',
    'Tres octavas y una segunda mayor, la novena de los acordes.':
        'Three octaves and a major second, the ninth in chords.',
    'Tres octavas y una tercera mayor.': 'Three octaves and a major third.',
    'Trémolo': 'Tremolo',
    'Una nota, desarmada': 'One note, taken apart',
    'Una octava justa arriba. Duplicar la frecuencia es la única operación que el oído no escucha como otra nota.':
        'A perfect octave above. Doubling the frequency is the only operation '
        'the ear does not hear as a different note.',
    'Una octava y una quinta. De acá sale la quinta, el intervalo sobre el que se apoya la armonía.':
        'An octave and a fifth. This is where the fifth comes from, the '
        'interval harmony rests on.',
    'Una séptima que no está en ninguna escala, treinta y un cents más baja que la del piano. Es el sonido del blues, y un instrumento temperado no la puede tocar.':
        'A seventh that isn’t in any scale, thirty-one cents lower than the '
        'piano’s. It’s the sound of the blues, and a tempered instrument '
        'can’t play it.',
    'el volumen oscila': 'the volume wavers',
    'frecuencia →': 'frequency →',
    'la afinación oscila': 'the pitch wavers',
    'unísono': 'unison',
    '{frequency:.0f} Hz': '{frequency:.0f} Hz',
    '{octaves} octavas': '{octaves} octaves',
    '♪  Sonando': '♪  Playing',

    # -- los intervalos de la serie armónica ---------------------------------
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
    'Siguiente  ▸': 'Next  ▸',
    'Terminar  ▸': 'Finish  ▸',
    '—  algo interrumpe el trabajo  —': '—  something interrupts the work  —',

    # -- el cartel de versión nueva ------------------------------------------
    'Actualizar': 'Update',
    'Ahora no': 'Not now',
    'ChordWeaver {nueva}  ·  la tuya es la {actual}':
        'ChordWeaver {nueva}  ·  yours is {actual}',
    'Hay una versión nueva': 'There is a new version',
    'No perdés tu progreso. Los logros, el libro, el sendero y el historial se pasan a la carpeta nueva, y la página explica cómo.':
        'You won’t lose your progress. Your achievements, book, path and '
        'history carry over to the new folder, and the page explains how.',

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

    # -- el experimentador: usar el timbre recién guardado --------------------
    '¿Querés que el programa use este timbre para todo lo que toca? Lo podés cambiar cuando quieras desde el engranaje.':
        'Do you want the program to use this timbre for everything it plays? '
        'You can change it any time from the gear.',
}
