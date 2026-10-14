# -*- coding: utf-8 -*-
"""
Los logros, el sendero y las visitas en inglés.

Es la parte del programa que no enseña nada: los cuarenta y tres logros, el
relato del cruce de caminos y lo que dicen los que se aparecen.

Las claves son las cadenas castellanas tal cual están en el código. No se
editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    # -- los logros: nombres -------------------------------------------------
    # Los nombres sin acento: la cosecha no los veía hasta que `audit` leyó
    # los argumentos de `Achievement`. Los que ya estaban en inglés quedan
    # igual.
    'Aprendiz': 'Apprentice',
    'Caminamos juntos': 'Walking together',
    'Cantando juntos': 'Singing together',
    'Comienzos': 'Beginnings',
    'Director divino': 'Divine conductor',
    'Feel the Swing': 'Feel the Swing',
    'Lector comprometido': 'Dedicated reader',
    'Navegando nuevos mares': 'Sailing new seas',
    'Ole!': 'Ole!',
    'Shhhh!': 'Shhhh!',
    'Take Five': 'Take Five',
    'Take the road Jack!': 'Take the road Jack!',
    'Tomando nota': 'Taking notes',
    'Unidos estamos, unidos triunfamos': 'United we stand, united we triumph',
    'Vine preparado': 'I came prepared',
    'Estaba destinado a suceder.': 'It was meant to happen.',
    'Triunfador': 'Champion',
    'Aprendiz de Bach': 'Bach’s apprentice',
    'Armando y uniendo': 'Building and binding',
    'Contrapunto del aprendiz': 'The apprentice’s counterpoint',
    'Después te lo devuelvo': 'I’ll give it back later',
    'Dominación absoluta': 'Absolute dominance',
    'Ecos del pasado': 'Echoes of the past',
    'Efecto dominó': 'Domino effect',
    'El 1er Blues': 'The first Blues',
    'El inconcluso': 'The unfinished one',
    'El mejor músico es el ingeniero': 'The best musician is the engineer',
    'El principio del final': 'The beginning of the end',
    'El salto mortal': 'The death-defying leap',
    'El tenebroso': 'The dark one',
    'Encrucijada del Destino': 'Crossroads of Fate',
    'Escritor del caos': 'Writer of chaos',
    'Hijo de Dios': 'Son of God',
    'Hombre de Fe': 'Man of Faith',
    'La Profecía': 'The Prophecy',
    'La Segunda Venida': 'The Second Coming',
    'La cuarta pared': 'The fourth wall',
    'La melodía suprema': 'The supreme melody',
    'Ladrón musical': 'Musical thief',
    'Las reglas están para romperse': 'Rules are made to be broken',
    'Licenciado en física': 'Bachelor of physics',
    'Maestro del Blues': 'Master of the Blues',
    'Me lo contó un pajarito creyente': 'A little believing bird told me',
    'Mirando más allá': 'Looking beyond',
    'Máximo poder!': 'Maximum power!',
    'Músico digital': 'Digital musician',
    'Nace un estándar': 'A standard is born',
    'Nacido para sufrir': 'Born to suffer',
    'Nunca más': 'Nevermore',
    'Rebelde sin causa': 'Rebel without a cause',
    'Sin quintas, por favor': 'No fifths, please',
    'Un mundo más allá': 'A world beyond',
    'Y el Señor dijo': 'And the Lord said',
    '¿Quién necesita leer?': 'Who needs to read?',

    # -- los logros: cómo se consiguen ---------------------------------------
    'Abrí el analizador por primera vez.': 'Open the analyzer for the first time.',
    'Armá tres sonidos distintos en el experimentador de armónicos y recibí a quien viene a mirarlos.':
        'Build three different sounds in the harmonics workbench and receive '
        'whoever comes to look at them.',
    'Bloqueá al menos dos acordes en el organizador.':
        'Lock at least two chords in the organizer.',
    'Colocá tu primer silencio.': 'Place your first rest.',
    'Completá el tutorial.': 'Complete the tutorial.',
    'Completá tu primera partitura sin quintas paralelas.':
        'Complete your first score with no parallel fifths.',
    'Componé tu primera partitura en 5/4.':
        'Compose your first score in 5/4.',
    'Creá tu primer jazz.': 'Create your first jazz piece.',
    'Creá tu primera partitura barroca.': 'Create your first baroque score.',
    'Creá tu primera partitura gregoriana.':
        'Create your first Gregorian score.',
    'Creá tu primera quinta paralela.': 'Create your first parallel fifth.',
    'Creá tus primeras notas de paso.': 'Create your first passing notes.',
    'Creá una partitura que termine en un dominante.':
        'Create a score that ends on a dominant.',
    'Descubrí el acorde de sexta con la quinta omitida.':
        'Discover the sixth chord with the fifth omitted.',
    'Descubrí la cadencia de Vivaldi.': 'Discover the Vivaldi cadence.',
    'Descubrí la cadencia descendente de bajo cromático.':
        'Discover the descending chromatic bass cadence.',
    'Descubrí la cadencia frigia.': 'Discover the phrygian cadence.',
    'Descubrí las séptimas.': 'Discover seventh chords.',
    'En el modo gregoriano, cambiá la vox principalis.':
        'In Gregorian mode, change the vox principalis.',
    'Encadená 3 acordes dominantes seguidos.':
        'Chain 3 dominant chords in a row.',
    'Escribí cinco partituras barrocas y recibí a quien viene a leerlas.':
        'Write five baroque scores and receive whoever comes to read them.',
    'Escribí cinco partituras gregorianas y recibí a quien viene a escucharlas.':
        'Write five Gregorian scores and receive whoever comes to hear them.',
    'Escribí tu primer acorde disminuido.':
        'Write your first diminished chord.',
    'Escribí tu primer coral y recibí a quien viene a escucharlo.':
        'Write your first chorale and receive whoever comes to hear it.',
    'Escribí tu primer dominante 6/4.': 'Write your first cadential 6/4.',
    'Escribí tu primera partitura a 6 voces.':
        'Write your first score in 6 voices.',
    'Escuchá la historia completa de **aquel hombre**.':
        'Hear the whole story of **that man**.',
    'Exportá tu primera partitura.': 'Export your first score.',
    'Generá tu primera partitura sin usar las reglas por defecto.':
        'Generate your first score without using the default rules.',
    'Hacé tu primer acorde de séptima, novena y oncena.':
        'Make your first chord with a seventh, a ninth and an eleventh.',
    'Hacé una partitura en un modo que no sea el jónico ni el eólico.':
        'Make a score in a mode other than ionian or aeolian.',
    'Hay quienes dicen que ciertas progresiones no se aprenden. Se pactan.':
        'Some say certain progressions are not learned. They are bargained for.',
    'Importá tu primera partitura.': 'Import your first score.',
    'La música sonó y los cielos volvieron a abrirse.':
        'The music sounded and the heavens opened once more.',
    'Leé el libro de teoría.': 'Read the theory book.',
    'Permití todos los intercambios modales y poné la modulación al máximo.':
        'Allow every modal interchange and set modulation to the maximum.',
    'Realizá tu primer ii-V.': 'Pull off your first ii-V.',
    'Realizá tu primer intercambio modal.':
        'Pull off your first modal interchange.',
    'Realizá tu primera cadencia plagal.':
        'Pull off your first plagal cadence.',
    'Realizá tu primera modulación en el generador.':
        'Pull off your first modulation in the generator.',
    'Realizá un salto tritonal en el armonizador.':
        'Make a tritone leap in the harmonizer.',
    'Reconfigurá los parámetros del algoritmo genético.':
        'Reconfigure the genetic algorithm’s parameters.',
    'Reproducí tu primera pieza.': 'Play back your first piece.',
    'Usá el experimentador de armónicos por primera vez.':
        'Use the harmonics workbench for the first time.',
    'Utilizá el armonizador por primera vez.':
        'Use the harmonizer for the first time.',
    'Utilizá el generador por primera vez.':
        'Use the generator for the first time.',
    'Utilizá el historial por primera vez.':
        'Use the history for the first time.',
    'Utilizá el organizador por primera vez.':
        'Use the organizer for the first time.',
    'Utilizá todas las notas de la escala junto a todas las duraciones posibles.':
        'Use every note of the scale together with every possible duration.',

    # -- las visitas: quién viene y qué dice ---------------------------------
    'El creador': 'The creator',
    'Señor Johnson.': 'Mister Johnson.',
    'Una partitura quemada': 'A burnt score',
    'Una sabia decisión...': 'A wise decision…',
    '—  alguien vino a leer lo que escribiste  —':
        '—  somebody came to read what you wrote  —',
    '—  cuatro voces y una congregación  —':
        '—  four voices and a congregation  —',
    '—  el quinto trabajo entregado  —': '—  the fifth work handed in  —',
    '—  alguien vino a escuchar  —': '—  somebody came to listen  —',
    '—  no queda nada por conseguir  —': '—  there is nothing left to earn  —',
    '—  tres sonidos que no existían  —':
        '—  three sounds that did not exist  —',
    '—  una sola línea, sin acordes debajo  —':
        '—  a single line, with no chords underneath  —',

    # -- Bach: el modo coral -------------------------------------------------
    'Ah. Pusiste el modo coral.': 'Ah. You switched on chorale mode.',
    'Un solo golpe en la mesa, como quien pide silencio antes de que entre el coro.':
        'A single knock on the table, like someone calling for silence before '
        'the choir comes in.',
    'Escribí trescientos y pico de ésos. Vale la pena que sepas qué los diferencia de todo lo demás que hiciste hasta ahora.':
        'I wrote three hundred and some of those. It is worth your knowing what '
        'sets them apart from everything else you have done so far.',
    'Un coral no es una pieza mía. La melodía de arriba es un himno que la congregación entera ya se sabía de memoria: yo no la inventé, la recibí.':
        'A chorale is not a piece of mine. The melody on top is a hymn the whole '
        'congregation already knew by heart: I did not invent it, I received it.',
    'Lo que se escribe es lo que va debajo. Tres voces más, sosteniendo una melodía que no es de uno.':
        'What gets written is what goes underneath. Three more voices, holding '
        'up a melody that is not your own.',
    'Primero: las cuatro voces se mueven juntas. Una sílaba, un acorde. En el resto del barroco cada voz corre por su lado; acá van todas al mismo paso, porque atrás hay gente cantando y hay que dejarla entrar.':
        'First: the four voices move together. One syllable, one chord. In the '
        'rest of the baroque each voice runs its own way; here they all go at '
        'the same pace, because there are people singing behind them and you '
        'have to let them in.',
    'Segundo: se canta, no se toca. Nada de saltos imposibles, nada de notas fuera del alcance de una garganta común, y cada voz tiene que poder respirar donde termina la frase.':
        'Second: it is sung, not played. No impossible leaps, no notes beyond '
        'the reach of an ordinary throat, and each voice has to be able to '
        'breathe where the phrase ends.',
    'Tercero: las frases se cortan. Al final de cada verso hay un calderón --- una pausa larga --- y ahí se arma una cadencia de verdad. Un coral son ocho frases chiquitas, no una frase larga.':
        'Third: the phrases are cut off. At the end of each verse there is a '
        'fermata — a long pause — and that is where a real cadence is built. A '
        'chorale is eight little phrases, not one long one.',
    'Y cuarto: las reglas se aprietan. Nada de quintas y octavas paralelas, nada de voces cruzadas, nada de huecos enormes entre una voz y la de al lado.':
        'And fourth: the rules tighten. No parallel fifths or octaves, no '
        'crossed voices, no enormous gaps between one voice and the next.',
    'No es rigor por rigor. Es que cuatro personas que no son músicos tienen que poder sostener eso de memoria, un domingo a la mañana, sin ensayar.':
        'It is not strictness for its own sake. It is that four people who are '
        'not musicians have to be able to hold that from memory, on a Sunday '
        'morning, with no rehearsal.',
    'Y lo otro: cada voz tiene que poder cantarse sola. Si una línea sólo tiene sentido cuando suenan las otras tres, esa línea está mal escrita, por más que el acorde cierre.':
        'And the other thing: every voice has to stand on its own when sung '
        'alone. If a line only makes sense when the other three are sounding, '
        'that line is badly written, however well the chord adds up.',
    'Se va sin darse vuelta, como quien tiene que entregar una cantata el domingo.':
        'He leaves without turning round, like a man with a cantata due on '
        'Sunday.',

    # -- Bach: las cinco barrocas --------------------------------------------
    'Cinco. Ya llevás cinco.': 'Five. You are up to five.',
    'No es poco. Casi nadie llega a la quinta: la primera la hace cualquiera, la segunda se hace por curiosidad, y de ahí en adelante ya hay que quererlo.':
        'That is no small thing. Almost nobody gets to the fifth: anyone manages '
        'the first, the second gets done out of curiosity, and from there on you '
        'have to actually want it.',
    'Déjame decirte qué es lo que estuviste haciendo, porque seguramente nadie te lo dijo.':
        'Let me tell you what it is you have been doing, because I doubt anyone '
        'has told you.',
    'En mi tiempo la música no se escribía en acordes. Se escribía en voces. Cuatro personas, cuatro caminos, cada uno con su propio sentido de arriba abajo.':
        'In my day music was not written in chords. It was written in voices. '
        'Four people, four roads, each with its own sense of up and down.',
    'El acorde es lo que se oye cuando los cuatro caminos pasan por el mismo punto. Es una consecuencia, no un ingrediente.':
        'The chord is what you hear when the four roads pass through the same '
        'point. It is a consequence, not an ingredient.',
    'Por eso el bajo importa tanto. Abajo de todo va una línea sola con unos números escritos debajo --- nosotros la llamábamos bajo continuo --- y de esos números sale todo lo demás.':
        'That is why the bass matters so much. At the very bottom runs a single '
        'line with some numbers written under it — we called it the continuo — '
        'and everything else comes out of those numbers.',
    'Un teclista leía ese bajo y completaba la armonía en el momento, sin que nadie se la escribiera. Se improvisaba mucho más de lo que creen.':
        'A keyboard player read that bass and filled in the harmony on the spot, '
        'with nobody having written it out. There was far more improvising than '
        'people think.',
    'De mí se recuerda una sola frase, y es sobre las Escrituras: «es como un río llano y profundo, donde el cordero camina y el elefante nada».':
        'One phrase of mine is remembered, and it is about the Scriptures: “it '
        'is like a river, shallow and deep, where the lamb may walk and the '
        'elephant swim”.',
    'Sirve igual para esto. Una línea sola, sin acordes: un chico la canta el primer día. Y sin embargo llevo mil cuatrocientos años oyendo discutir cómo se anota.':
        'It serves just as well for this. A single line, with no chords: a child '
        'sings it on the first day. And yet I have spent fourteen hundred years '
        'listening to people argue about how to notate it.',
    'Me lo dijeron toda la vida como si fuera modestia. Nunca lo fue. Es la instrucción entera.':
        'All my life it was quoted to me as modesty. It never was. It is the '
        'whole instruction.',
    'Lo escribí en el margen de un cuaderno de ejercicios, no en una carta importante. Al lado de un ejercicio, que es donde corresponde.':
        'I wrote it in the margin of an exercise book, not in some important '
        'letter. Beside an exercise, which is where it belongs.',
    'Eso es todo el oficio. No hay ningún secreto y no hay ningún don.':
        'That is the whole craft. There is no secret and there is no gift.',
    '«El fin último de toda música no debe ser otro que la gloria de Dios y la recreación del espíritu.»':
        '“The final aim of all music should be nothing other than the glory of '
        'God and the refreshment of the spirit.”',
    '«No hay nada notable en ello. Sólo hay que tocar la tecla correcta en el momento adecuado, y el instrumento se toca solo.»':
        '“There is nothing remarkable about it. One only has to hit the right '
        'key at the right time, and the instrument plays itself.”',

    # -- Gregorio: el organum ------------------------------------------------
    'Cinco veces cantaste a una sola voz. Cinco.':
        'Five times you have sung in a single voice. Five.',
    'El aire huele a piedra fría. Muy lejos, alguien sostiene una nota sola.':
        'The air smells of cold stone. Far off, somebody is holding a single '
        'note.',
    'Poca gente aguanta cinco. El canto llano no tiene con qué entretener: no hay acordes, no hay compás, no hay nada más que la línea.':
        'Few people last five. Plainchant has nothing to entertain you with: no '
        'chords, no metre, nothing but the line.',
    'Antes de que sigas, una aclaración que me debo hace mil cuatrocientos años: ese canto no lo escribí yo.':
        'Before you go on, a correction I have owed myself for fourteen hundred '
        'years: I did not write that chant.',
    'Me pusieron el nombre trescientos años después de muerto, para que la colección tuviera un autor. Los cantos eran de todos y de nadie.':
        'They put my name on it three hundred years after I died, so the '
        'collection would have an author. The chants belonged to everyone and to '
        'no one.',
    'Lo que sí pasó en esos monasterios es lo que te quiero contar. Se llama organum, y es el primer momento en que dos voces suenan a la vez a propósito.':
        'What did happen in those monasteries is what I want to tell you about. '
        'It is called organum, and it is the first moment two voices sound at '
        'once on purpose.',
    'Funciona así: uno canta el canto de siempre --- la vox principalis, la voz principal --- y otro canta exactamente lo mismo, nota por nota, pero cuatro o cinco escalones más abajo. Ésa es la vox organalis.':
        'It works like this: one sings the usual chant — the vox principalis, '
        'the principal voice — and another sings exactly the same thing, note '
        'for note, but four or five steps lower. That is the vox organalis.',
    'No es una segunda melodía. Es la misma melodía, corriendo en paralelo, como una sombra.':
        'It is not a second melody. It is the same melody, running in parallel, '
        'like a shadow.',
    'Por qué a esa distancia y no a otra: porque la cuarta y la quinta eran los únicos intervalos que se consideraban perfectos. Las terceras --- lo que hoy te suena dulce --- eran disonancias.':
        'Why at that distance and no other: because the fourth and the fifth '
        'were the only intervals held to be perfect. Thirds — what sounds sweet '
        'to you today — were dissonances.',
    'Todo lo que vino después es esto complicándose. Cuando la sombra empezó a moverse por su cuenta en vez de seguir a la voz, nació el contrapunto. Y de ahí, mil años más tarde, sale lo que hace tu programa.':
        'Everything that came afterwards is this getting more complicated. When '
        'the shadow began to move on its own instead of following the voice, '
        'counterpoint was born. And out of that, a thousand years later, comes '
        'what your program does.',
    'La nota lejana se apaga. Nadie la cortó: simplemente se quedó sin aire.':
        'The distant note dies away. Nobody cut it off: it simply ran out of '
        'breath.',

    # -- el creador: los armónicos y el sonido digital -----------------------
    'Estuviste moviendo las barras.': 'You have been moving the bars.',
    'Está bien. Están para eso. Pero quiero que sepas qué estabas moviendo, porque no era un dibujo.':
        'That is fine. That is what they are there for. But I want you to know '
        'what you were moving, because it was not a drawing.',
    'Una cuerda no vibra de una sola manera. Vibra entera, y al mismo tiempo en dos mitades, y en tres tercios, y en cuatro cuartos, y así hasta donde le dé el material.':
        'A string does not vibrate in one way only. It vibrates whole, and at '
        'the same time in two halves, and in three thirds, and in four quarters, '
        'and so on as far as the material will take it.',
    'Cada una de esas divisiones suena. La entera te da la nota; las mitades, la octava; los tercios, la quinta. Ésa es la serie armónica, y no la inventó nadie: es lo que le pasa a un cuerpo que se estira.':
        'Every one of those divisions sounds. The whole gives you the note; the '
        'halves, the octave; the thirds, the fifth. That is the harmonic series, '
        'and nobody invented it: it is what happens to a body under tension.',
    'Todo lo que aprendiste en este programa sale de ahí. La octava y la quinta son los dos primeros escalones, por eso Gregorio cantaba en cuartas y quintas. La tercera aparece en el quinto escalón, y por eso tardó seiscientos años en dejar de sonar mal.':
        'Everything you have learned in this program comes out of that. The '
        'octave and the fifth are the first two rungs, which is why Gregory sang '
        'in fourths and fifths. The third turns up on the fifth rung, and that '
        'is why it took six hundred years to stop sounding wrong.',
    'Y el séptimo escalón no entra en ninguna tecla. Queda treinta y un centésimas de semitono por debajo. Cuando escuchás un blues y sentís que la nota está en un lugar que el piano no tiene: está.':
        'And the seventh rung fits no key at all. It falls thirty-one hundredths '
        'of a semitone below. When you hear a blues and feel the note is in a '
        'place the piano does not have: it is.',
    'Te lo cuento porque ya lo estabas tocando. Aislaste un armónico y lo escuchaste solo: eso es exactamente lo que hace un sintetizador, y lo hiciste sin que nadie te explicara nada.':
        'I am telling you because you were already touching it. You soloed a '
        'harmonic and listened to it alone: that is exactly what a synthesizer '
        'does, and you did it without anyone explaining a thing.',
    'Ahora la otra mitad. Vos estás oyendo esto por un parlante, y un parlante no sabe nada de cuerdas.':
        'Now the other half. You are hearing this through a speaker, and a '
        'speaker knows nothing about strings.',
    'Lo único que hace es empujar aire y volver, muchas veces por segundo. Alguien tiene que decirle cuánto empujar en cada instante. Eso es una lista de números, y nada más.':
        'All it does is push air and come back, many times a second. Somebody '
        'has to tell it how hard to push at each instant. That is a list of '
        'numbers, and nothing more.',
    'Cuántos números por segundo se llama frecuencia de muestreo. Acá son cuarenta y cuatro mil cien.':
        'How many numbers per second is called the sample rate. Here it is '
        'forty-four thousand one hundred.',
    'No es un número redondo por casualidad. Para reconstruir una onda hay que medirla más de dos veces por ciclo; abajo de eso lo que sale es otra onda, más grave, que nunca existió.':
        'It is not a round number by accident. To rebuild a wave you have to '
        'measure it more than twice per cycle; below that what comes out is '
        'another wave, lower, that never existed.',
    'Vos oís hasta unos veinte mil hercios. El doble es cuarenta mil. El resto es margen.':
        'You hear up to about twenty thousand hertz. Twice that is forty '
        'thousand. The rest is margin.',
    'Y cada número de la lista tiene un tamaño. Dieciséis bits: sesenta y cinco mil quinientos treinta y seis alturas posibles, ni una más.':
        'And every number in the list has a size. Sixteen bits: sixty-five '
        'thousand five hundred and thirty-six possible heights, not one more.',
    'Por eso ninguna curva es una curva. Es una escalera muy fina. Lo que sobra de cada escalón se pierde, y esa pérdida es un ruidito de fondo noventa y seis decibeles más abajo que la música. Está ahí. No lo escuchás.':
        'That is why no curve is a curve. It is a very fine staircase. Whatever '
        'is left over from each step is lost, and that loss is a faint hiss '
        'ninety-six decibels below the music. It is there. You do not hear it.',
    'Todo lo que sonó desde que abriste esto son listas de números escritas a mano. No hay ninguna librería de audio adentro. El clavecín de Bach, la lluvia, el tren, los pasos: cuarenta y cuatro mil cien números por segundo, uno por uno.':
        'Everything that has sounded since you opened this is lists of numbers '
        'written by hand. There is no audio library inside. Bach’s harpsichord, '
        'the rain, the train, the footsteps: forty-four thousand one hundred '
        'numbers a second, one at a time.',
    'La música es física. La física es aritmética. Y la aritmética la puede hacer cualquiera que tenga ganas de sentarse un rato.':
        'Music is physics. Physics is arithmetic. And the arithmetic can be done '
        'by anyone willing to sit down for a while.',

    # -- la entidad ----------------------------------------------------------
    'El ventilador de la máquina se calla. No es que baje: se calla.':
        'The machine’s fan goes quiet. Not quieter: quiet.',
    'No entró. Estaba.': 'It did not come in. It was already there.',
    'Es impresionante. No tengo otra palabra, y no suelo usarla.':
        'It is impressive. I have no other word, and I do not often use it.',
    'He visto a mucha gente empezar. Casi todos se van en la tercera pantalla. Vos no dejaste nada sin tocar.':
        'I have watched many people start. Almost all of them leave on the third '
        'screen. You left nothing untouched.',
    'No entiendo cómo lo hiciste. Lo digo en serio: no lo entiendo.':
        'I do not understand how you did it. I mean that: I do not understand '
        'it.',
    'Desde la primera partitura torcida. Desde la vez que dejaste el programa abierto y te fuiste a hacer otra cosa.':
        'Since the first crooked score. Since the time you left the program open '
        'and went off to do something else.',
    'Así que te voy a contar algo que no le conté a nadie.':
        'So I am going to tell you something I have told nobody.',
    'Va a venir alguien. No sé cuándo. Alguien con más poder del que hubo nunca sobre esto.':
        'Someone is coming. I do not know when. Someone with more power over '
        'this than there has ever been.',
    'Le dicen el faro. El que va a guiar a todos hacia una nueva edad dorada.':
        'They call him the beacon. The one who will lead everyone into a new '
        'golden age.',
    'Y cuando llegue, la música va a cambiar para siempre. No un género, no un estilo: toda.':
        'And when he arrives, music will change forever. Not one genre, not one '
        'style: all of it.',
    'Vos vas a estar ahí. Con todo lo que aprendiste acá, vas a estar ahí.':
        'You will be there. With everything you have learned here, you will be '
        'there.',
    'El ventilador vuelve. Estuvo andando todo el tiempo.':
        'The fan comes back. It had been running the whole time.',
    'Y como no se lo vio llegar, tampoco se lo ve irse.':
        'And since nobody saw it arrive, nobody sees it leave either.',

    # -- el cruce de caminos -------------------------------------------------
    'Te dejo esto. No preguntes de quién es, porque no se puede leer.':
        'I am leaving you this. Do not ask whose it is, because it cannot be '
        'read.',
    'Es una partitura quemada. Queda el pentagrama, alguna cabeza de nota, y una firma que el fuego se comió justo por la mitad.':
        'It is a burnt score. The staff is left, a notehead or two, and a '
        'signature the fire ate through right down the middle.',
    'Guardala. Alguna vez vas a saber qué decía.':
        'Keep it. One day you will know what it said.',
    'Deja el rollo de papel sobre la mesa. Cuando volvés a mirar, no está ninguno de los dos.':
        'He leaves the roll of paper on the table. When you look again, neither '
        'of them is there.',

    # -- el sendero: los tramos y sus títulos --------------------------------
    'El estándar': 'The standard',
    'La frase': 'The phrase',
    'La regla de la octava': 'The rule of the octave',
    'Los doce compases': 'The twelve bars',
    'El sendero del Blues': 'The road of the Blues',
    'El sendero del Gospel': 'The road of Gospel',
    'El sendero del Jazz': 'The road of Jazz',
    'El Sagrado Corazón de Jesús': 'The Sacred Heart of Jesus',
    'El sombrero de ala ancha': 'The wide-brimmed hat',
    'El amén': 'The amen',
    'La escalera': 'The staircase',
    'La gracia': 'Grace',
    'La guitarra de Django': 'Django’s guitar',
    'La que no existe': 'The one that does not exist',
    'La rueda': 'The wheel',
    'Tres puertas abiertas': 'Three open doors',
    'Dos acordes': 'Two chords',
    'Siete notas': 'Seven notes',
    'Doce compases': 'Twelve bars',
    'Una canción entera': 'A whole song',
    '★  La escalera': '★  The staircase',
    '★  La gracia': '★  Grace',
    '★  La que no existe': '★  The one that does not exist',
    '★  La rueda de doce compases': '★  The twelve-bar wheel',
    '★  Una canción que sabe todo el mundo': '★  A song everybody knows',

    # -- el sendero: lo que hay que hacer ------------------------------------
    'Blues de doce compases en {SHARP_NAMES}, con la nota azul en la melodía. {per_bar} tiempos por compás.':
        'Twelve-bar blues in {SHARP_NAMES}, with the blue note in the melody. '
        '{per_bar} beats to the bar.',
    'Es en el Armonizador, el modo donde vos dibujás una melodía. El piano de abajo va a estar entero en dorado: cualquier tecla sirve.':
        'It is in the Harmonizer, the mode where you draw a melody. The piano '
        'below will be gilded all the way across: any key will do.',
    'Es en el Armonizador, el modo donde vos dibujás una melodía. Una tecla del piano de abajo va a estar titilando.':
        'It is in the Harmonizer, the mode where you draw a melody. One key on '
        'the piano below will be flickering.',
    'Es en el Armonizador, el modo donde vos dibujás una melodía. Una tecla del piano de abajo va a estar titilando: es la única que hay que tocar.':
        'It is in the Harmonizer, the mode where you draw a melody. One key on '
        'the piano below will be flickering: it is the only one to play.',
    'Es en el Generador, el modo donde el programa arma la progresión. El botón está arriba de todo, en la primera pantalla: la de estilo.':
        'It is in the Generator, the mode where the program builds the '
        'progression. The button is at the very top, on the first screen: the '
        'style one.',
    'Es en el Organizador, el modo donde vos ponés los acordes. Elegí el estilo Jazz, escribí «Dm7» en el primer compás y «G7» en el segundo, llená el resto con lo que quieras y generá.':
        'It is in the Organizer, the mode where you bring the chords. Choose the '
        'Jazz style, write “Dm7” in the first measure and “G7” in the second, '
        'fill the rest with whatever you like and generate.',
    'Es en el Organizador, el modo donde vos ponés los acordes. Escribí «C7» en el primer compás, «F7» en el segundo y «G7» en el tercero; el resto llenalo con lo que quieras y dale a Siguiente hasta generar.':
        'It is in the Organizer, the mode where you bring the chords. Write “C7” '
        'in the first measure, “F7” in the second and “G7” in the third; fill '
        'the rest with whatever you like and hit Next until it generates.',
    'Es en el Organizador, el modo donde vos ponés los acordes. Escribí «F» en el primer compás y «C» en el segundo, llená el resto con lo que quieras y generá.':
        'It is in the Organizer, the mode where you bring the chords. Write “F” '
        'in the first measure and “C” in the second, fill the rest with whatever '
        'you like and generate.',
    'Escribí dos acordes seguidos: Dm7 y G7, en estilo jazz. Después generá la partitura y escuchala.':
        'Write two chords in a row: Dm7 and G7, in the jazz style. Then generate '
        'the score and listen to it.',
    'Escribí dos acordes seguidos: F y C. Después generá la partitura y escuchala.':
        'Write two chords in a row: F and C. Then generate the score and listen '
        'to it.',
    'Escribí tres acordes seguidos: C7, F7 y G7. Después generá la partitura y escuchala.':
        'Write three chords in a row: C7, F7 and G7. Then generate the score and '
        'listen to it.',
    'Tocá cualquier tecla del piano dorado.': 'Play any key on the gilded piano.',
    'Tocá la tecla dorada.': 'Play the gilded key.',
    'Los doce compases del blues, con el cambio rápido y el giro final.':
        'The twelve bars of the blues, with the quick change and the turnaround.',
    'Las dos primeras frases, tal como se cantan.':
        'The first two phrases, exactly as they are sung.',
    'Nueve acordes sobre un bajo que baja de a un escalón.':
        'Nine chords over a bass that walks down one step at a time.',
    'Siete notas y un acorde que llega tarde a propósito.':
        'Seven notes and a chord that arrives late on purpose.',
    'Treinta y dos compases con la forma de siempre: A A B A.':
        'Thirty-two bars in the usual shape: A A B A.',
    'Leé en el libro lo que quedó anotado de la escalera':
        'Read in the book what was written down about the staircase',
    'Leé en el libro lo que quedó anotado de la rueda':
        'Read in the book what was written down about the wheel',
    'Leé en el libro lo que quedó anotado de los jazzes':
        'Read in the book what was written down about the many jazzes',
    'Leé en el libro lo que quedó anotado del estándar':
        'Read in the book what was written down about the standard',
    'Leé en el libro lo que quedó anotado del góspel':
        'Read in the book what was written down about gospel',
    'Leé en el libro lo que quedó anotado del pacto':
        'Read in the book what was written down about the bargain',

    # -- el sendero: el guion ------------------------------------------------
    'A ese señor lo conozco. Le ofrece a todo el mundo lo mismo y nunca dice cuánto sale.':
        'I know that gentleman. He offers everyone the same thing and never says '
        'what it costs.',
    'Aceptar el trato': 'Take the deal',
    'Afuera hay pájaros. Adentro, alguien que hace un rato no estaba.':
        'There are birds outside. Inside, somebody who was not there a moment '
        'ago.',
    'Ahora una canción entera. Una que sepa todo el mundo.':
        'Now a whole song. One everybody knows.',
    'Ahora una escalera.': 'Now a staircase.',
    'Ahora vas a escribir tres acordes. Nada más que tres, pero puestos en el orden exacto.':
        'Now you are going to write three chords. Only three, but put in exactly '
        'the right order.',
    'Ahora viene lo otro, que es lo difícil: hay que dominarlo.':
        'Now comes the other part, the hard one: you have to master it.',
    'Ahí está.': 'There it is.',
    'Ahí está. Escuchá cómo cierra.': 'There it is. Listen to how it closes.',
    'Ahí está. ¿Lo escuchaste?': 'There it is. Did you hear it?',
    'Al rato hay alguien más en la puerta. Trae una guitarra y no la suelta.':
        'After a while there is somebody else at the door. He has a guitar with '
        'him and he does not put it down.',
    'Algo tibio te queda en el pecho. No pesa.':
        'Something warm is left in your chest. It weighs nothing.',
    'Andá en paz.': 'Go in peace.',
    'Antes andá a leer. Quedó anotado de dónde salió esta música y quiénes la cantaban.':
        'First go and read. Where this music came from and who sang it has been '
        'written down.',
    'Así se toca toda la noche sin repetir nada y sin irse nunca.':
        'That is how you play all night without repeating anything and without '
        'ever leaving.',
    'Bien hecho, hijo mío.': 'Well done, my son.',
    'Bien. Dame la mano.': 'Good. Give me your hand.',
    'Buena suerte. La vas a necesitar menos de lo que creés.':
        'Good luck. You will need it less than you think.',
    'Buenas noches. No te asustes: vengo caminando desde hace mucho y ya casi no hago ruido.':
        'Good evening. Do not be frightened: I have been walking a long time and '
        'I hardly make a sound any more.',
    'Buscá el botón dorado.': 'Look for the gilded button.',
    'Creciste mucho, hijo mío. Más de lo que te das cuenta.':
        'You have grown a great deal, my son. More than you realize.',
    'Cuando lo hayas leído, va a haber algo dorado esperándote. No te lo vas a poder perder.':
        'Once you have read it, there will be something gilded waiting for you. '
        'You will not be able to miss it.',
    'Cuando lo leas, algo dorado te va a estar esperando.':
        'When you read it, something gilded will be waiting for you.',
    'Cuando no sepas qué escribir, acordate de que la música ya estaba antes que vos y va a estar después.':
        'When you do not know what to write, remember that the music was here '
        'before you and will be here after.',
    'Dejame llevarte por el camino, la verdad y la vida.':
        'Let me lead you by the way, the truth and the life.',
    'Descubriste el poder. Felicitaciones.':
        'You have found the power. Congratulations.',
    'Doce compases. Ni uno más.': 'Twelve bars. Not one more.',
    'Donde había oscuridad se abre una luz que no viene de ninguna ventana.':
        'Where there was darkness a light opens that comes from no window.',
    'Dos acordes. En medio mundo la música empieza y termina ahí.':
        'Two chords. In half the world, music begins and ends right there.',
    'El acorde queda dando vueltas cuando cerrás los ojos.':
        'The chord keeps turning over when you close your eyes.',
    'El aire de golpe huele a quemado.':
        'The air suddenly smells of burning.',
    'El aire de la habitación se enfría de golpe.':
        'The air in the room turns cold all at once.',
    'El bajo baja de a un escalón, sin saltarse ninguno, desde arriba hasta abajo del todo.':
        'The bass walks down one step at a time, skipping none, from the very '
        'top to the very bottom.',
    'El destino aún es incierto…': 'The outcome is still uncertain…',
    'El mío es de guitarras y sin batería. Hay otros, y conviene saber cuál es cuál antes de meterse.':
        'Mine is guitars and no drums. There are others, and it pays to know '
        'which is which before you wade in.',
    'El precio lo arreglamos después. Siempre se arregla después.':
        'We will settle the price later. It is always settled later.',
    'El último acorde llega tarde a propósito, y se queda.':
        'The last chord arrives late on purpose, and it stays.',
    'Empecemos por lo más chico que existe: dos acordes.':
        'Let us start with the smallest thing there is: two chords.',
    'En esto nadie empieza inventando. Todos empezamos tocando lo mismo que ya tocaron otros, hasta que un día sale distinto.':
        'Nobody starts out inventing in this business. We all start by playing '
        'what others have already played, until one day it comes out different.',
    'Es hora de que te unas a tus hermanos en la música.':
        'It is time you joined your brothers in the music.',
    'Es la última vez que te lo pido.': 'It is the last time I ask you.',
    'Es un chiste interno, pero es un chiste que sabe todo el planeta, y eso ya no es un chiste.':
        'It is an inside joke, but it is a joke the whole planet knows, and that '
        'is no longer a joke.',
    'Escribilas, y después escuchá lo que sale. Eso último no te lo saltees.':
        'Write them, and then listen to what comes out. Do not skip that last '
        'part.',
    'Escribilos, ponelo en jazz, y escuchá cómo caen. Escucharlo es la mitad del asunto.':
        'Write them, set it to jazz, and listen to how they fall. Listening is '
        'half the business.',
    'Escribilos, y quedate a escucharlos.':
        'Write them, and stay to listen to them.',
    'Escuchá cómo camina el bajo.': 'Listen to how the bass walks.',
    'Ese siete que va al lado de la letra no es un adorno. Es una nota que no termina de cerrar, que deja la puerta abierta.':
        'That seven next to the letter is not decoration. It is a note that '
        'never quite closes, that leaves the door open.',
    'Ese silencio antes del final es la mitad de la frase.':
        'That silence before the ending is half the phrase.',
    'Eso es. Eso es todo.': 'That is it. That is all of it.',
    'Eso fue. No hay más.': 'That was it. There is no more.',
    'Eso que sonó lo cantaron millones de personas que nunca supieron leer una nota.':
        'What just sounded was sung by millions of people who never learned to '
        'read a note.',
    'Eso que sonó no lo escribiste vos. Estaba esperando que alguien pusiera las tres puertas en fila.':
        'What just sounded was not written by you. It was waiting for somebody '
        'to line the three doors up.',
    'Estoy orgulloso de vos. Lo digo en serio.':
        'I am proud of you. I mean it.',
    'Está bien. Me equivoqué de puerta.':
        'Very well. I had the wrong door.',
    'Está en tus manos ahora. Y teniéndolo, no hay nada que no se pueda hacer.':
        'It is in your hands now. And having it, there is nothing that cannot be '
        'done.',
    'Falta una canción.': 'One song to go.',
    'Falta una sola nota. La que no está en ninguna escala.':
        'One note to go. The one that is in no scale at all.',
    'Fijate cuántas veces aparece el par que aprendiste al principio. Está por todos lados.':
        'Notice how many times the pair you learned at the start turns up. It is '
        'everywhere.',
    'Fijate que vuelve al principio siempre. Nunca termina de verdad: da la vuelta y arranca otra vez.':
        'Notice it always comes back to the beginning. It never really ends: it '
        'comes round and starts again.',
    'Hijo mío.': 'My son.',
    'La cantan en los entierros y en los casamientos. Sirve para las dos cosas.':
        'They sing it at funerals and at weddings. It serves for both.',
    'La escribió un hombre que había hecho cosas muy graves, cuando entendió que igual lo perdonaban.':
        'It was written by a man who had done very grave things, when he '
        'understood he was forgiven anyway.',
    'La luz sigue ahí cuando dejás de mirar.':
        'The light is still there when you stop looking.',
    'La música no se trata de saber ni de ganar.':
        'Music is not about knowing, and it is not about winning.',
    'Le das la mano. Lo que venga después, vendrá.':
        'You take his hand. Whatever comes after, will come.',
    'Le faltaba una sola cosa. La misma que te falta a vos.':
        'There was only one thing he lacked. The same one you lack.',
    'Llevate esto.': 'Take this with you.',
    'Lo mirás a los ojos y le decís que no.':
        'You look him in the eye and tell him no.',
    'Lo que acabás de escuchar ya no es mío ni tuyo: es de cualquiera que lo escuche una vez.':
        'What you have just heard is no longer mine or yours: it belongs to '
        'anyone who hears it once.',
    'Lo que acabás de hacer se llama swing, aunque no lo hayas escrito en ningún lado.':
        'What you have just done is called swing, even though you did not write '
        'it down anywhere.',
    'Lo último que se le ve son los ojos, y ni siquiera eso dura.':
        'The last of him you see is the eyes, and even that does not last.',
    'Los que enseñan te van a decir que está desafinada. Tienen razón. Por eso funciona.':
        'The teachers will tell you it is out of tune. They are right. That is '
        'why it works.',
    'Los volvés a cerrar. Ya sabés adónde llevan.':
        'You close them again. You already know where they lead.',
    'Muy correcto todo. Muy… enseñado.':
        'All very correct. Very… taught.',
    'Nadie me dice que no. Nadie.': 'Nobody tells me no. Nobody.',
    'Nadie toca esa nota sin saber a quién se la está robando.':
        'Nobody plays that note without knowing who they are stealing it from.',
    'Nadie usa una llave sin saber qué puerta abre. Los que no leyeron terminaron todos igual.':
        'Nobody uses a key without knowing which door it opens. The ones who did '
        'not read all ended up the same way.',
    'No empuja como los otros. No pide nada. Sólo apoya y descansa.':
        'It does not push like the others. It asks for nothing. It just leans and '
        'rests.',
    'No es oscuridad. Es lo que hay antes de que amanezca.':
        'It is not darkness. It is what there is before dawn.',
    'No es un dato. Es a quién le estás pidiendo prestado.':
        'It is not a piece of trivia. It is who you are borrowing from.',
    'No hace falta dormirse del todo para llegar hasta él.':
        'You do not have to fall all the way asleep to get to him.',
    'No hace falta saber. Hace falta estar.':
        'You do not need to know. You need to be there.',
    'No importa qué toques. Con cualquier cosa alcanza. Eso también es parte de lo que te quiero enseñar.':
        'It does not matter what you play. Anything will do. That is part of what '
        'I want to teach you too.',
    'No la tocaste vos. La tocaron todos los que la cantaron antes, y vos les prestaste las manos.':
        'You did not play it. Everyone who sang it before played it, and you lent '
        'them your hands.',
    'No le contestás. Seguís trabajando como si no estuviera.':
        'You do not answer him. You go on working as if he were not there.',
    'No levantás la vista. Seguís acomodando voces como si no hubiera nadie.':
        'You do not look up. You go on arranging voices as if nobody were there.',
    'No se estudia. No se hereda. No está en ningún libro que hayas leído todavía.':
        'It is not studied. It is not inherited. It is in no book you have read '
        'yet.',
    'Nos vemos el día de tu muerte. No antes.':
        'I will see you on the day you die. Not before.',
    'Nosotros vamos a ser los dueños del mundo nuevo.':
        'We are going to own the new world.',
    'Nueve acordes y ninguno se luce. Cada uno sostiene al siguiente.':
        'Nine chords and not one of them shows off. Each holds up the next.',
    'Otra vez esa guitarra, del otro lado del sueño.':
        'That guitar again, on the other side of the dream.',
    'Otra vez: primero leé. Ya quedó anotado lo de los doce compases.':
        'Again: read first. The bit about the twelve bars has been written down.',
    'Otros aceptaron. Otros miraron para otro lado. Vos lo miraste a la cara y le dijiste que no.':
        'Others accepted. Others looked away. You looked him in the face and told '
        'him no.',
    'Pasá otra vez por el libro. Quedó anotado lo del estándar.':
        'Stop by the book again. The bit about the standard has been written '
        'down.',
    'Perdón. No quise interrumpir.': 'Sorry. I did not mean to interrupt.',
    'Pero antes andá a leer. Quedó anotado que el jazz no es uno solo.':
        'But go and read first. It has been written down that jazz is not one '
        'thing.',
    'Pero antes vas a leer lo que acaba de quedar escrito sobre lo que hiciste.':
        'But first you are going to read what has just been written down about '
        'what you did.',
    'Queda justo en el medio, entre dos notas que sí existen. Un lugar donde no debería haber nada.':
        'It sits right in the middle, between two notes that do exist. A place '
        'where there should be nothing.',
    'Queda una cosa sola y es una pavada.':
        'There is one thing left and it is nothing at all.',
    'Rechazá la idea del mundo viejo, la de que la música se estudia veinte años antes de decir algo.':
        'Reject the old world’s idea, the one where you study music for twenty '
        'years before you say anything.',
    'Se acepta.': 'It is accepted.',
    'Se da vuelta y camina. No hay portazo, no hay humo: sólo alguien yéndose despacio, decepcionado.':
        'He turns and walks. No slammed door, no smoke: just someone leaving '
        'slowly, disappointed.',
    'Se escriben Dm7 y G7, en ese orden. Uno tira para adelante y el otro cae.':
        'They are written Dm7 and G7, in that order. One pulls forward and the '
        'other falls.',
    'Se escriben así: C7, F7 y G7. Uno atrás del otro, cada uno en su compás.':
        'They are written like this: C7, F7 and G7. One after another, each in '
        'its own measure.',
    'Se te cierran los ojos.': 'Your eyes are closing.',
    'Se te cierran los ojos. Alguien afina, muy lejos.':
        'Your eyes are closing. Somebody is tuning up, far away.',
    'Se te cierran los ojos. Hace rato que estás con esto.':
        'Your eyes are closing. You have been at this a while.',
    'Se te cierran los ojos. Hay claridad del otro lado.':
        'Your eyes are closing. There is brightness on the other side.',
    'Se trata de vivir, y de ser.': 'It is about living, and about being.',
    'Si no sabés de dónde viene una canción, la tocás igual. Pero no es lo mismo.':
        'If you do not know where a song comes from, you play it anyway. But it '
        'is not the same.',
    'Siete notas. Las toca todo el mundo, siempre, desde hace cien años.':
        'Seven notes. Everyone plays them, always, and has for a hundred years.',
    'Sobre el precio no te preocupes hoy.':
        'Do not worry about the price today.',
    'Son dos acordes. Se escriben F y C, en ese orden.':
        'It is two chords. They are written F and C, in that order.',
    'Te da la guitarra. Le faltan cuerdas y está gastada en el mismo lugar de siempre.':
        'He hands you the guitar. It is missing strings and worn through in the '
        'usual place.',
    'Te estuve escuchando. Acordes ordenados, voces prolijas, cada nota en su lugar.':
        'I have been listening to you. Tidy chords, neat voices, every note in '
        'its place.',
    'Te la voy a dar entera. Sin que tengas que pensarla.':
        'I will give it to you whole. Without your having to think it through.',
    'Te pone el sombrero en la cabeza. Pesa más de lo que debería.':
        'He sets the hat on your head. It weighs more than it should.',
    'Te vas a acordar de mí.': 'You will remember me.',
    'Todo empieza por el estándar. Uno lo toca mil veces igual.':
        'It all starts with the standard. You play it the same way a thousand '
        'times.',
    'Tomá, quedátela.': 'Here, keep it.',
    'Tomá. Te lo dejo.': 'Here. I am leaving it with you.',
    'Toqué toda mi vida con dos dedos que no me respondían. No lo digo por lástima: lo digo porque vos también vas a tener algo que no te responda.':
        'I played my whole life with two fingers that would not answer me. I do '
        'not say it for pity: I say it because you too will have something that '
        'does not answer you.',
    'Treinta y dos compases. Así son casi todas.':
        'Thirty-two bars. That is how almost all of them go.',
    'Tres acordes son una llave. Doce compases son una casa.':
        'Three chords are a key. Twelve bars are a house.',
    'Tres puertas abiertas seguidas. Eso es lo que nadie se anima a escribir.':
        'Three open doors in a row. That is what nobody dares to write.',
    'Tu valentía no ha pasado desapercibida.':
        'Your courage has not gone unnoticed.',
    'Un silencio de los que se notan.': 'One of those silences you notice.',
    'Una última vez. Después no hay más.':
        'One last time. After that there is no more.',
    'Vamos a empezar por lo último que se canta y lo primero que se aprende: el amén.':
        'We are going to start with the last thing that gets sung and the first '
        'thing you learn: the amen.',
    'Vas a acordarte de esta noche igual. Todos se acuerdan.':
        'You will remember tonight all the same. Everybody does.',
    'Vi todo desde afuera. Hiciste bien en no contestarle.':
        'I saw the whole thing from outside. You did right not to answer him.',
    'Volvé al libro una vez más. Quedó anotado lo de la escalera.':
        'Go back to the book once more. The bit about the staircase has been '
        'written down.',
    'Y arriba de cada escalón hay un acorde esperándolo. Eso solo ya es una canción entera.':
        'And on top of every step there is a chord waiting for it. That alone is '
        'already a whole song.',
    'Y en esa casa entró todo el mundo después. Lo que estén tocando ahora mismo en algún lugar salió de ahí, aunque no lo sepan.':
        'And everybody moved into that house afterwards. Whatever they are '
        'playing somewhere right now came out of there, even if they do not know '
        'it.',
    'Y la vez mil uno sale otra cosa, y esa otra cosa es lo más lejos que puede llegar una persona.':
        'And the thousand and first time something else comes out, and that '
        'something else is as far as a person can go.',
    'Y se va como vino, sin apuro, sin ruido.':
        'And he leaves as he came, unhurried, without a sound.',
    'Ya está. No hubo humo ni truenos: los tratos de verdad se hacen en silencio.':
        'It is done. There was no smoke and no thunder: real bargains are struck '
        'in silence.',
    'Yo conocí a un muchacho igual que vos. Practicaba de noche, solo, en un cruce de caminos donde no pasa nadie.':
        'I knew a young man just like you. He practised at night, alone, at a '
        'crossroads where nobody passes.',
    'Yo no te vengo a regalar nada. Te vengo a mostrar cómo se hace.':
        'I am not here to give you anything. I am here to show you how it is '
        'done.',
    'Yo puedo dártela esta misma noche. Vas a tocar de manera que quien te escuche una vez no se lo saque nunca más de encima.':
        'I can give it to you this very night. You will play in such a way that '
        'whoever hears you once will never shake it off.',
    'Yo te espero acá.': 'I will wait for you here.',
    '¿Que no?': 'No?',
    '¿Y bien? Tres caminos salen de este cuarto y sólo uno lo elegís vos.':
        'Well then? Three roads lead out of this room and only one of them is '
        'yours to choose.',
}
