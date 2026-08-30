# -*- coding: utf-8 -*-
"""
El libro de teoría en inglés.

Es la mitad del texto del programa: los capítulos, sus apartados, las
figuras y los gráficos. Los tramos entre `**` son negritas y **tienen que
quedar en el mismo lugar**: `app._split_lead` parte el párrafo por ahí para
escribir la entradilla en su propio renglón.

Las claves son las cadenas castellanas tal cual están en `engine/book.py`.
No se editan a mano: las saca `python -m engine.lang.audit --missing`.
"""

CATALOG = {
    '**Bebop (1945–1955).** La reacción. Tempos imposibles, melodías de corcheas sin respiro, armonía cargada de tensiones. Deliberadamente difícil de bailar: era música para escuchar, hecha por músicos que estaban cansados de ser la orquesta de un salón.':
        '**Bebop (1945–1955).** The reaction. Impossible tempos, melodies of '
        'eighth notes with no room to breathe, harmony loaded with tensions. '
        'Deliberately hard to dance to: it was music for listening, made by '
        'musicians who were tired of being a ballroom’s orchestra.',
    '**Cada voz tiene que poder cantarse sola.** Si una línea sólo tiene sentido cuando suenan las otras tres, está mal escrita por más que el acorde cierre. Es el criterio con el que este programa castiga los saltos: una voz que salta todo el tiempo no es una voz, es un relleno.':
        '**Every voice has to stand on its own when sung alone.** If a line only '
        'makes sense when the other three are sounding, it is badly written '
        'however well the chord adds up. It is the criterion by which this '
        'program penalizes leaps: a voice that leaps all the time is not a '
        'voice, it is filler.',
    '**Con una duda que todavía no se resolvió: la velocidad.** Varios investigadores sostienen que los discos originales se grabaron o se copiaron un poco rápido, y que bajándolos un diez o quince por ciento la voz se vuelve más grave, el tempo más lento y las posiciones de la guitarra caen exactamente donde un guitarrista las tocaría. Otros lo niegan. Lo que está en juego no es un detalle técnico: si tienen razón, nadie escuchó nunca a Robert Johnson --- todos escuchamos una versión suya acelerada, y hasta la parte imposible de su leyenda sería un error de fábrica.':
        '**With one doubt still unresolved: the speed.** Several researchers hold '
        'that the original records were cut or copied slightly fast, and that '
        'pitching them down ten or fifteen per cent makes the voice deeper, the '
        'tempo slower, and the guitar positions fall exactly where a guitarist '
        'would play them. Others deny it. What is at stake is not a technical '
        'detail: if they are right, nobody has ever heard Robert Johnson — we '
        'have all heard a sped-up version of him, and even the impossible part '
        'of his legend would be a manufacturing error.',
    '**Contrario** — una sube y la otra baja. Es el mejor de los cuatro: las dos líneas se escuchan como líneas independientes, que es de lo que se trata escribir a varias voces.':
        '**Contrary** — one goes up and the other goes down. It is the best of '
        'the four: the two lines are heard as independent lines, which is the '
        'whole point of writing in several voices.',
    '**Cool, modal, free (1955–).** Después el jazz se abrió en abanico y ya no volvió a juntarse. El modal cambió los acordes por escalas; el free tiró la armonía entera por la ventana.':
        '**Cool, modal, free (1955–).** After that jazz fanned out and never came '
        'back together. Modal traded chords for scales; free threw the whole of '
        'harmony out the window.',
    '**Cuán preciso es cada número** se mide en bits. Con 16 bits hay 65.536 alturas posibles y ni una más, así que ninguna curva es realmente una curva: es una escalera muy fina. Lo que sobra de cada escalón se pierde, y esa pérdida es un ruido de fondo unos 96 decibeles por debajo de la música. Está ahí y no lo escuchás.':
        '**How precise each number is** is measured in bits. With 16 bits there '
        'are 65,536 possible heights and not one more, so no curve is really a '
        'curve: it is a very fine staircase. Whatever is left over from each '
        'step is lost, and that loss is a background hiss some 96 decibels below '
        'the music. It is there and you do not hear it.',
    '**Cuán preciso es cada número: 16 bits.** 65.536 alturas posibles, ni una más. Ninguna curva es una curva: es una escalera muy fina, y lo que sobra de cada escalón se pierde en un ruido de fondo 96 decibeles por debajo de la música. Está ahí. No se escucha.':
        '**How precise each number is: 16 bits.** 65,536 possible heights, not '
        'one more. No curve is a curve: it is a very fine staircase, and '
        'whatever is left over from each step is lost in a background hiss 96 '
        'decibels below the music. It is there. You do not hear it.',
    '**Cuántos números por segundo** se llama frecuencia de muestreo. Este programa usa 44.100, que es lo que usa un CD. No es un número redondo por casualidad: para reconstruir una onda hay que medirla más de dos veces por ciclo, y por debajo de eso lo que sale es otra onda, más grave, que nunca existió. Como el oído llega a unos 20.000 hercios, hacen falta más de 40.000 mediciones por segundo. El resto es margen.':
        '**How many numbers per second** is called the sample rate. This program '
        'uses 44,100, which is what a CD uses. It is not a round number by '
        'accident: to rebuild a wave you have to measure it more than twice per '
        'cycle, and below that what comes out is another wave, lower, that never '
        'existed. Since the ear reaches about 20,000 hertz, more than 40,000 '
        'measurements a second are needed. The rest is margin.',
    '**Cuántos números por segundo: 44.100.** No es redondo por casualidad. Para reconstruir una onda hay que medirla más de dos veces por ciclo, y por debajo de eso lo que sale es otra onda más grave que nunca existió. El oído llega a unos 20.000 hercios; el doble es 40.000, y el resto es margen.':
        '**How many numbers per second: 44,100.** Not a round number by accident. '
        'To rebuild a wave you have to measure it more than twice per cycle, and '
        'below that what comes out is another, lower wave that never existed. '
        'The ear reaches about 20,000 hertz; twice that is 40,000, and the rest '
        'is margin.',
    '**Cómo está hecha.** Con cinco notas: es pentatónica, la escala sin semitonos que existe en casi todas las culturas del mundo. Por eso se puede cantar sin haberla aprendido y por eso no suena de ningún país en particular.':
        '**How it is built.** Out of five notes: it is pentatonic, the scale with '
        'no semitones that exists in almost every culture in the world. That is '
        'why you can sing it without having learned it and why it does not sound '
        'like any country in particular.',
    '**Cómo grabó.** De cara a la pared, en un rincón, dándole la espalda al técnico. Se dijo durante décadas que era para que nadie le viera las manos. Un ingeniero explicó después que el rincón devuelve el sonido y que era, sencillamente, el mejor lugar del cuarto. Las dos cosas pueden ser ciertas.':
        '**How he recorded.** Facing the wall, in a corner, with his back to the '
        'engineer. For decades it was said this was so nobody could see his '
        'hands. An engineer later explained that the corner reflects the sound '
        'and that it was, quite simply, the best spot in the room. Both things '
        'can be true.',
    '**Cómo llegó al góspel.** No llegó: se reinventó. Un bajo que baja por grados y arrastra la armonía es una idea a la que se llega sola en cuanto uno se sienta al piano y quiere que algo suene inevitable.':
        '**How it reached gospel.** It did not: it was reinvented. A bass walking '
        'down by step and dragging the harmony with it is an idea you arrive at '
        'on your own the moment you sit at a piano and want something to sound '
        'inevitable.',
    '**Cómo murió: nadie lo sabe con certeza.** La versión que se repite es que aceptó una botella de whisky ya abierta en un baile de campo y que estaba envenenada. Sonny Boy Williamson, que tocaba con él esa noche, contó que le había volteado de la mano una primera botella abierta advirtiéndole que nunca tomara de una así, y que él aceptó la siguiente igual. Después estuvo días agonizando. Se contó que al final andaba en cuatro patas y aullando, y eso puede ser cierto o puede ser la leyenda tapando el hueco: no lo vio ningún médico.':
        '**How he died: nobody knows for certain.** The version that gets repeated '
        'is that he accepted an already-opened bottle of whiskey at a country '
        'dance and that it was poisoned. Sonny Boy Williamson, who was playing '
        'with him that night, said he had knocked a first opened bottle out of '
        'his hand warning him never to drink from one like that, and that he '
        'took the next one anyway. He then spent days dying. It was said that at '
        'the end he was on all fours and howling, and that may be true or it may '
        'be the legend filling in the gap: no doctor ever saw him.',
    '**Cómo se anotaba.** Al principio no se anotaba: se aprendía de oído, y un cantor tardaba diez años en saberse el repertorio. Los primeros signos eran garabatos encima de la letra que sólo recordaban si la melodía subía o bajaba --- no servían para aprender nada que no supieras ya. Recién alrededor de 1030 a un monje se le ocurrió tirar líneas horizontales y poner cada signo a una altura fija. Ese monje se llamaba Guido, y lo que inventó es el pentagrama que usás en el Armonizador. De paso les puso nombre a las notas, sacándolas de las primeras sílabas de un himno: *ut, re, mi, fa, sol, la*.':
        '**How it was written down.** At first it was not: it was learned by ear, '
        'and a singer took ten years to know the repertoire. The first signs were '
        'scratches above the text that only reminded you whether the melody went '
        'up or down — they were no use for learning anything you did not already '
        'know. Only around 1030 did it occur to a monk to draw horizontal lines '
        'and put each sign at a fixed height. That monk was called Guido, and '
        'what he invented is the staff you use in the Harmonizer. While he was at '
        'it he named the notes, taking them from the first syllables of a hymn: '
        '*ut, re, mi, fa, sol, la*.',
    '**Cómo se usa.** De paso, nunca apoyada. Se pisa y se sigue: es una nota que duele, y lo que la hace funcionar es que no se queda.':
        '**How it is used.** In passing, never leaned on. You step on it and move '
        'on: it is a note that hurts, and what makes it work is that it does not '
        'stay.',
    '**Cómo sobrevivieron.** Él no los publicó. Los juntó su hijo después de su muerte, sueltos, arrancados de las cantatas a las que pertenecían. Lo que llegó hasta hoy es una colección de fragmentos que nadie pensó como colección.':
        '**How they survived.** He did not publish them. His son gathered them '
        'after his death, loose, torn out of the cantatas they belonged to. What '
        'has reached us is a collection of fragments nobody ever conceived of as '
        'a collection.',
    '**Cómo suena.** Llamada y respuesta —uno canta una frase y el coro contesta—, armonías densas de cuatro y cinco voces, y una manera de cantar donde la nota escrita es apenas el punto de partida. Nada se canta exactamente como está anotado.':
        '**How it sounds.** Call and response — one sings a phrase and the choir '
        'answers — dense harmonies of four and five voices, and a way of singing '
        'in which the written note is barely a starting point. Nothing is sung '
        'exactly as it is notated.',
    '**De ahí salen los intervalos, en orden.** La octava es el segundo escalón, la quinta el tercero, la tercera mayor el quinto. La historia entera de la armonía occidental es esa escalera subida de a un peldaño por siglo, y por eso Gregorio cantaba en cuartas y quintas seiscientos años antes de que la tercera dejara de sonar mal.':
        '**The intervals come out of that, in order.** The octave is the second '
        'rung, the fifth the third, the major third the fifth. The whole history '
        'of Western harmony is that staircase climbed one rung per century, and '
        'that is why Gregory sang in fourths and fifths six hundred years before '
        'the third stopped sounding wrong.',
    '**De dónde salió.** De los campos de algodón del delta del Misisipi, a fines del siglo diecinueve, cantada por personas que habían sido esclavizadas y por sus hijos. No la escribió nadie: se pasaba de boca en boca, sin partitura, y cuando alguien la anotó por primera vez ya tenía cincuenta años.':
        '**Where it came from.** From the cotton fields of the Mississippi delta, '
        'at the end of the nineteenth century, sung by people who had been '
        'enslaved and by their children. Nobody wrote it: it was passed from '
        'mouth to mouth, without a score, and by the time somebody first wrote it '
        'down it was already fifty years old.',
    "**De dónde viene el nombre.** Del siglo dieciocho, y de un contexto muy distinto: era un ejercicio que se les daba a los chicos de los conservatorios de Nápoles para que aprendieran a armonizar cualquier bajo de memoria. Lo llamaban *regola dell'ottava*.":
        '**Where the name comes from.** From the eighteenth century, and from a '
        'very different setting: it was an exercise given to the boys of the '
        'Naples conservatories so they would learn to harmonize any bass from '
        'memory. They called it the *regola dell’ottava*.',
    '**De él quedó, entonces, esto:** veintinueve canciones, dos fotografías, un certificado con la causa en blanco y tres tumbas de las cuales dos están vacías. Todo lo demás --- el cruce, el hombre alto, el precio, el club --- se lo pusimos encima nosotros.':
        '**What is left of him, then, is this:** twenty-nine songs, two '
        'photographs, a certificate with the cause left blank and three graves of '
        'which two are empty. Everything else — the crossroads, the tall man, the '
        'price, the club — we laid on top of him ourselves.',
    '**Decibeles.** El oído no suma, multiplica. Duplicar la energía no suena al doble de fuerte: suena apenas un poco más. Por eso el volumen se mide en una escala logarítmica, donde cada 10 decibeles es diez veces más energía y se oye como «el doble». De ahí que un pianísimo y un fortísimo, que en la partitura son dos palabras, en energía sean una diferencia de miles de veces.':
        '**Decibels.** The ear does not add, it multiplies. Doubling the energy '
        'does not sound twice as loud: it sounds barely a little louder. That is '
        'why volume is measured on a logarithmic scale, where every 10 decibels '
        'is ten times the energy and is heard as “twice as loud”. Hence a '
        'pianissimo and a fortissimo, which on the page are two words, are a '
        'difference of thousands of times in energy.',
    '**Directo** — las dos se mueven para el mismo lado, pero distinta distancia. Aceptable.':
        '**Direct** — both move the same way, but by different distances. '
        'Acceptable.',
    '**Dominante (V, y vii°).** Es la tensión máxima. El V contiene la nota que está un semitono por debajo de la tónica —la sensible— y esa nota tira hacia arriba con una fuerza que se escucha físicamente. Por eso V casi siempre va a I.':
        '**Dominant (V, and vii°).** It is maximum tension. The V contains the '
        'note a semitone below the tonic — the leading tone — and that note pulls '
        'upward with a force you can physically hear. That is why V almost always '
        'goes to I.',
    '**El bajo continuo.** Abajo de todo iba una línea sola con números escritos debajo, y de esos números salía toda la armonía. Un teclista los leía y completaba los acordes en el momento, sin que nadie se los escribiera: en el barroco se improvisaba muchísimo más de lo que se cree, y la partitura era menos una orden que un plano.':
        '**The continuo.** At the very bottom ran a single line with numbers '
        'written under it, and out of those numbers came the whole harmony. A '
        'keyboard player read them and filled in the chords on the spot, with '
        'nobody having written them out: there was far more improvising in the '
        'baroque than people think, and the score was less an order than a '
        'blueprint.',
    '**El cruce de caminos no era del diablo.** Venía de África occidental y llegó al Misisipi con la gente esclavizada: el que espera en la encrucijada es Eshu, o Legba según quién cuente, el que abre y cierra el paso entre un mundo y el otro, y al que hay que pedirle permiso antes que a nadie. En el hoodoo del Delta eso sobrevivió como un rito de aprendizaje: se iba al cruce varias noches seguidas con el instrumento y se esperaba. Los misioneros tradujeron a Eshu por Satanás, que es la única palabra que tenían, y el rito quedó convertido en un contrato.':
        '**The crossroads did not belong to the devil.** It came from West Africa '
        'and reached Mississippi with enslaved people: the one who waits at the '
        'crossroads is Eshu, or Legba depending on who is telling it, the one who '
        'opens and closes the way between one world and the other, and whose '
        'permission must be asked before anyone else’s. In Delta hoodoo that '
        'survived as a rite of apprenticeship: you went to the crossroads several '
        'nights running with your instrument and waited. The missionaries '
        'translated Eshu as Satan, which was the only word they had, and the rite '
        'was turned into a contract.',
    '**El organum.** Alrededor del año 900, en un tratado llamado *Musica enchiriadis*, aparece por primera vez algo que nadie había puesto por escrito: dos voces sonando a la vez, a propósito. Uno canta el canto llano de siempre --- la *vox principalis*, la voz principal --- y otro canta lo mismo, nota por nota, cuatro o cinco escalones más abajo: la *vox organalis*. No es una segunda melodía. Es la misma melodía corriendo en paralelo, como una sombra.':
        '**Organum.** Around the year 900, in a treatise called *Musica '
        'enchiriadis*, something nobody had put in writing appears for the first '
        'time: two voices sounding at once, on purpose. One sings the usual '
        'plainchant — the *vox principalis*, the principal voice — and another '
        'sings the same thing, note for note, four or five steps lower: the *vox '
        'organalis*. It is not a second melody. It is the same melody running in '
        'parallel, like a shadow.',
    '**El origen.** Los *spirituals*: canciones que las personas esclavizadas cantaban trabajando, con letras bíblicas que a veces eran instrucciones para escapar. «Wade in the water» también quería decir metete en el agua, que el agua no deja rastro para los perros.':
        '**The origin.** The *spirituals*: songs enslaved people sang while '
        'working, with biblical words that were sometimes instructions for '
        'escaping. “Wade in the water” also meant get into the water, because '
        'water leaves no trail for the dogs.',
    '**El pacto no lo inventó él, y probablemente no lo contó nunca.** Cuando Robert Johnson volvió del año que estuvo afuera, la historia ya estaba escrita y esperando a alguien: se la habían colgado antes a Tommy Johnson, otro guitarrista de Misisipi sin ningún parentesco, cuyo hermano la contó tal cual --- el cruce, la medianoche, el hombre alto --- muchos años después. Es un molde. Al que aparece tocando de una manera que nadie puede explicar se le aplica el molde.':
        '**He did not invent the bargain, and probably never told it.** By the '
        'time Robert Johnson came back from the year he was away, the story was '
        'already written and waiting for somebody: it had been hung earlier on '
        'Tommy Johnson, another Mississippi guitarist and no relation, whose '
        'brother told it word for word — the crossroads, midnight, the tall man — '
        'many years later. It is a mould. Anyone who turns up playing in a way '
        'nobody can explain gets the mould applied to them.',
    '**El papel no dice nada.** El certificado de defunción apareció recién en 1968, treinta años después, y tiene la casilla de la causa vacía. Al dorso, una nota del dueño de la plantación aclara que no lo atendió ningún doctor. La palabra «sífilis» que a veces se cita la agregó después un funcionario a partir de lo que le contaron. Los candidatos que se discuten hoy son tres: estricnina --- que tiene el problema de que mata en horas y no en días ---, una sífilis de nacimiento que le habría reventado la aorta, y una neumonía. No hay autopsia, no hay historia clínica y no hay cuerpo que revisar.':
        '**The paper says nothing.** The death certificate only surfaced in 1968, '
        'thirty years later, and the box for the cause is empty. On the back, a '
        'note from the plantation owner states that no doctor attended him. The '
        'word “syphilis” that is sometimes quoted was added afterwards by a clerk '
        'from what he was told. Three candidates are argued over today: strychnine '
        '— which has the problem of killing in hours, not days — a congenital '
        'syphilis that would have burst his aorta, and pneumonia. There is no '
        'autopsy, no medical record and no body to examine.',
    '**El último.** Ya ciego, dictó de memoria un coral desde la cama. Le cambió el título por *Ante tu trono me presento*. No llegó a escuchar cómo sonaba.':
        '**The last one.** Already blind, he dictated a chorale from memory from '
        'his bed. He changed its title to *Before thy throne I now appear*. He '
        'never heard how it sounded.',
    '**Enmascaramiento.** Un sonido fuerte tapa a uno más débil que esté cerca en frecuencia. Es por lo que una orquestación amontonada suena a barro aunque cada línea esté bien escrita, y es la razón física de la regla de espaciado que este programa aplica: voces demasiado juntas en el grave se esconden entre ellas.':
        '**Masking.** A loud sound covers a weaker one nearby in frequency. It is '
        'why a crowded orchestration sounds like mud even when every line is well '
        'written, and it is the physical reason for the spacing rule this program '
        'applies: voices too close together in the low register hide inside each '
        'other.',
    '**Gypsy jazz (1930–).** Sin batería y sin vientos: dos o tres guitarras y un contrabajo. Una guitarra marca el pulso golpeando las cuerdas —«la pompe»— y la otra hace la melodía. Lo inventaron músicos gitanos en Francia; su nombre propio es Django Reinhardt, que se quemó la mano izquierda en un incendio a los dieciocho años y volvió a aprender a tocar usando dos dedos.':
        '**Gypsy jazz (1930–).** No drums and no horns: two or three guitars and '
        'a double bass. One guitar marks the pulse by striking the strings — “la '
        'pompe” — and the other plays the melody. It was invented by Romani '
        'musicians in France; its proper name is Django Reinhardt, who burned his '
        'left hand in a fire at eighteen and learned to play again using two '
        'fingers.',
    '**La acusación se heredó entera.** Cada vez que una música hecha por gente de abajo se volvió popular, alguien dijo que la había escrito el diablo: las caderas de Elvis, los discos que había que escuchar al revés, las audiencias del Senado de 1985 y las etiquetas de advertencia, los juicios al heavy metal. Siempre el mismo argumento y siempre contra la misma clase de gente. El capítulo entero de este libro es una lista de músicas que empezaron prohibidas y terminaron enseñándose en el conservatorio.':
        '**The accusation was inherited whole.** Every time music made by people '
        'at the bottom became popular, somebody said the devil had written it: '
        'Elvis’s hips, the records you had to play backwards, the 1985 Senate '
        'hearings and the warning labels, the heavy metal trials. Always the same '
        'argument and always against the same kind of people. This whole chapter '
        'of the book is a list of musics that started out banned and ended up '
        'taught in the conservatory.',
    '**La cita.** *El fin último de toda música no debe ser otro que la gloria de Dios y la recreación del espíritu.* Lo escribió en el margen de un cuaderno de ejercicios, al lado de un ejercicio. No en una carta importante.':
        '**The quotation.** *The final aim of all music should be nothing other '
        'than the glory of God and the refreshment of the spirit.* He wrote it in '
        'the margin of an exercise book, beside an exercise. Not in some '
        'important letter.',
    '**La cita.** *No hay nada notable en ello. Sólo hay que tocar la tecla correcta en el momento adecuado, y el instrumento se toca solo.* Se repite siempre como una modestia. No lo es: es la instrucción entera, y es lo más difícil que se ha dicho nunca sobre tocar un instrumento.':
        '**The quotation.** *There is nothing remarkable about it. One only has to '
        'hit the right key at the right time, and the instrument plays itself.* It '
        'is always repeated as modesty. It is not: it is the whole instruction, '
        'and it is the hardest thing anyone has ever said about playing an '
        'instrument.',
    '**La cita.** De él se recuerda una frase, y es sobre las Escrituras: *es como un río llano y profundo, donde el cordero camina y el elefante nada*. Sirve igual para el canto: un chico canta una línea sola el primer día, y llevamos mil cuatrocientos años discutiendo cómo se anota.':
        '**The quotation.** One phrase of his is remembered, and it is about the '
        'Scriptures: *it is like a river, shallow and deep, where the lamb may '
        'walk and the elephant swim*. It serves just as well for chant: a child '
        'sings a single line on the first day, and we have spent fourteen hundred '
        'years arguing about how to notate it.',
    '**La forma.** Treinta y dos compases repartidos en cuatro frases de ocho, con el esquema A A B A: se dice una frase, se repite, se dice otra distinta —el puente— y se vuelve a la primera. Ese esquema es tan común que se lo reconoce sin contar.':
        '**The form.** Thirty-two bars split into four phrases of eight, in the '
        'pattern A A B A: you say a phrase, repeat it, say a different one — the '
        'bridge — and come back to the first. That pattern is so common you '
        'recognize it without counting.',
    '**La fundamental, al final.** Es la más plana de las tres: la melodía y el bajo cantan la misma nota y el acorde suena hueco. Pero en los puntos de reposo se abarata de golpe: deja muy atrás a la quinta y queda a la par de la tercera. El final de una frase quiere sonar cerrado, y nada cierra como la fundamental arriba y abajo.':
        '**The root, last.** It is the flattest of the three: melody and bass sing '
        'the same note and the chord sounds hollow. But at resting points it '
        'suddenly gets cheap: it leaves the fifth far behind and draws level with '
        'the third. The end of a phrase wants to sound closed, and nothing closes '
        'like the root above and below.',
    '**La ironía.** La cantaron, y la siguen cantando, sobre todo los descendientes de las personas que Newton transportó. Se canta en entierros y en casamientos, en las dos cosas, y funciona en las dos.':
        '**The irony.** It has been sung, and is still sung, above all by the '
        'descendants of the people Newton transported. It is sung at funerals and '
        'at weddings, at both, and it works at both.',
    '**La leyenda.** Se cuenta que Robert Johnson, que tocaba mal, desapareció un tiempo y volvió tocando como nadie. La explicación que circuló fue que había ido a un cruce de caminos a medianoche y le había entregado la guitarra a alguien que se la devolvió afinada. Murió a los veintisiete años. Nadie sabe dónde está enterrado.':
        '**The legend.** The story goes that Robert Johnson, who played badly, '
        'disappeared for a while and came back playing like nobody else. The '
        'explanation that circulated was that he had gone to a crossroads at '
        'midnight and handed his guitar to somebody who gave it back to him '
        'tuned. He died at twenty-seven. Nobody knows where he is buried.',
    '**La leyenda.** Tocaba mal. Los que lo vieron de joven contaron que era insoportable con la guitarra: Son House recordaba haberle dicho que se fuera a molestar a otro lado. Se fue un tiempo, y cuando volvió tocaba de una manera que nadie podía explicar. La historia que circuló entre los músicos fue que había ido a un cruce de caminos a medianoche, que un hombre alto le había afinado la guitarra y se la había devuelto, y que el precio se arreglaba después.':
        '**The legend.** He played badly. Those who saw him young said he was '
        'unbearable with a guitar: Son House remembered telling him to go and '
        'bother somebody else. He went away for a while, and when he came back he '
        'played in a way nobody could explain. The story that went round among '
        'musicians was that he had gone to a crossroads at midnight, that a tall '
        'man had tuned his guitar and given it back, and that the price would be '
        'settled later.',
    '**La melodía no es de él.** La línea de arriba es un himno que la congregación ya se sabía de memoria; algunos son anteriores a Lutero y varios eran canciones de taberna a las que alguien les cambió la letra. Lo que se compone es lo que va debajo: tres voces sosteniendo una melodía ajena. Es el mismo trabajo que hace el Armonizador de este programa.':
        '**The melody is not his.** The top line is a hymn the congregation '
        'already knew by heart; some are older than Luther and several were '
        'tavern songs somebody wrote new words for. What gets composed is what '
        'goes underneath: three voices holding up somebody else’s melody. It is '
        'the same job this program’s Harmonizer does.',
    '**La música se escribía en voces, no en acordes.** Cuatro personas, cuatro líneas, cada una con su propio sentido de arriba abajo. El acorde es lo que se oye cuando las cuatro pasan por el mismo punto: una consecuencia, no un ingrediente. Es exactamente lo que hace este programa, y es de acá de donde lo sacó.':
        '**Music was written in voices, not in chords.** Four people, four lines, '
        'each with its own sense of up and down. The chord is what you hear when '
        'the four pass through the same point: a consequence, not an ingredient. '
        'It is exactly what this program does, and this is where it got it from.',
    '**La quinta, después.** Neutra y segura. No compromete nada: suena bien y no dice mucho, que a veces es justo lo que hace falta en el medio de una frase.':
        '**The fifth, next.** Neutral and safe. It commits to nothing: it sounds '
        'good and says little, which is sometimes exactly what is needed in the '
        'middle of a phrase.',
    '**La repercusión llegó veintitrés años después de enterrarlo.** En 1961 Columbia juntó dieciséis de sus grabaciones en un disco, *King of the Delta Blues Singers*. Vendió unos pocos miles de copias, y entre esos pocos miles estaban prácticamente todos los que iban a hacer la música de la década siguiente: los Rolling Stones, Clapton, Dylan. Es uno de los pocos casos en los que se puede señalar un objeto concreto y decir que de ahí salió lo que vino después.':
        '**The impact arrived twenty-three years after they buried him.** In 1961 '
        'Columbia gathered sixteen of his recordings onto one record, *King of the '
        'Delta Blues Singers*. It sold a few thousand copies, and among those few '
        'thousand were practically everyone who would make the music of the next '
        'decade: the Rolling Stones, Clapton, Dylan. It is one of the few cases '
        'where you can point at a concrete object and say that what came '
        'afterwards came out of it.',
    '**La tercera, primero.** Es el lugar más característico. La tercera es la nota que dice si el acorde es mayor o menor, así que tenerla arriba de todo hace que se oiga de qué acorde se trata. Es la respuesta por defecto.':
        '**The third, first.** It is the most characteristic place. The third is '
        'the note that says whether the chord is major or minor, so having it on '
        'top makes it clear which chord you are hearing. It is the default answer.',
    '**Las cuatro voces se mueven juntas.** Una sílaba, un acorde. En el resto del barroco cada voz corre por su lado; en un coral van todas al mismo paso, porque atrás hay gente cantando y hay que dejarla entrar.':
        '**The four voices move together.** One syllable, one chord. In the rest '
        'of the baroque each voice runs its own way; in a chorale they all go at '
        'the same pace, because there are people singing behind them and you have '
        'to let them in.',
    '**Las frases se cortan.** Al final de cada verso hay un calderón --- ese puntito con el arco encima --- y ahí se arma una cadencia de verdad. En el papel dice «alargá esta nota»; en la práctica dice «acá respira todo el mundo». Un coral son ocho frases chiquitas, no una frase larga.':
        '**The phrases are cut off.** At the end of each verse there is a fermata '
        '— that little dot with an arc over it — and that is where a real cadence '
        'is built. On paper it says “hold this note”; in practice it says '
        '“everybody breathes here”. A chorale is eight little phrases, not one '
        'long one.',
    '**Las reglas se aprietan.** Nada de quintas ni octavas paralelas, nada de voces cruzadas, nada de huecos enormes entre una voz y la de al lado. No es rigor por el rigor: es que cuatro personas que no son músicos tienen que poder sostener eso de memoria un domingo a la mañana, sin ensayar.':
        '**The rules tighten.** No parallel fifths or octaves, no crossed voices, '
        'no enormous gaps between one voice and the next. It is not strictness '
        'for its own sake: it is that four people who are not musicians have to '
        'be able to hold that from memory on a Sunday morning, with no rehearsal.',
    '**Lo que hizo para aprender.** A los veinte años caminó cuatrocientos kilómetros para escuchar tocar a Buxtehude. Había pedido cuatro semanas de licencia; volvió a los cuatro meses. Años más tarde, cuando otro patrón no lo dejó irse, insistió tanto que lo metieron preso un mes. Salió con veintitantos preludios corales escritos en la celda.':
        '**What he did in order to learn.** At twenty he walked four hundred '
        'kilometres to hear Buxtehude play. He had asked for four weeks’ leave; '
        'he came back four months later. Years afterwards, when another employer '
        'would not let him go, he pressed so hard they jailed him for a month. He '
        'came out with twenty-odd chorale preludes written in the cell.',
    '**Lo que la canción dice de verdad es peor que un demonio.** *Cross Road Blues* --- la que le puso nombre a todo el asunto --- no habla de ningún pacto. Habla de un hombre negro parado en un cruce de rutas tratando de que alguien lo levante, y del sol que se está por meter. Quedarse a pie después del anochecer, en el Misisipi de 1936, en un condado equivocado, era jugarse la vida. Lo que se oye en esa grabación es miedo, y no es miedo del infierno.':
        '**What the song actually says is worse than a demon.** *Cross Road Blues* '
        '— the one that gave the whole business its name — is not about any '
        'bargain. It is about a Black man standing at a road junction trying to '
        'get a ride, and about the sun going down. Being stranded on foot after '
        'nightfall, in 1936 Mississippi, in the wrong county, meant risking your '
        'life. What you hear in that recording is fear, and it is not fear of '
        'hell.',
    '**Lo que probablemente pasó.** Se fue a estudiar con Ike Zimmerman, un guitarrista que ensayaba de noche en un cementerio porque era el único lugar donde nadie se quejaba del ruido. Volvió sabiendo tocar porque había practicado un año entero, solo, de noche, sentado sobre las lápidas. La versión aburrida casi siempre es la verdadera, y casi siempre también es un cruce de caminos y un precio.':
        '**What probably happened.** He went off to study with Ike Zimmerman, a '
        'guitarist who practised at night in a cemetery because it was the only '
        'place nobody complained about the noise. He came back able to play '
        'because he had practised a whole year, alone, at night, sitting on the '
        'headstones. The boring version is almost always the true one, and it is '
        'almost always a crossroads and a price too.',
    '**Lo que salió de acá.** El rhythm and blues, el rock and roll entero, buena parte del jazz, el soul. Chuck Berry, Elvis, los Beatles, los Rolling Stones: todos empezaron tocando doce compases. Ninguna de esas fortunas volvió al delta del Misisipi.':
        '**What came out of this.** Rhythm and blues, the whole of rock and roll, '
        'a good part of jazz, soul. Chuck Berry, Elvis, the Beatles, the Rolling '
        'Stones: they all started out playing twelve bars. None of those fortunes '
        'ever went back to the Mississippi delta.',
    '**Lo que salió de acá.** El soul entero. Aretha Franklin, Ray Charles, Sam Cooke: los tres cantaban en la iglesia antes de grabar un disco, y a los tres los acusaron de traición por usar la voz de Dios para cantar otras cosas.':
        '**What came out of this.** The whole of soul. Aretha Franklin, Ray '
        'Charles, Sam Cooke: all three sang in church before they cut a record, '
        'and all three were accused of betrayal for using God’s voice to sing '
        'other things.',
    '**Lo que tienen en común.** El ii-V. Ese par de acordes que aprendiste está en todos, del primero al último.':
        '**What they have in common.** The ii-V. That pair of chords you learned '
        'is in all of them, from the first to the last.',
    '**Lo que vino después.** Cuando la sombra empezó a moverse por su cuenta en vez de seguir a la voz, nació el contrapunto. En París, hacia 1200, dos hombres llamados Léonin y Pérotin escribieron organa de tres y cuatro voces: son los primeros compositores de la historia occidental de los que se conserva el nombre. De ahí a Bach hay ochocientos años, y de Bach a acá otros trescientos.':
        '**What came next.** When the shadow began to move on its own instead of '
        'following the voice, counterpoint was born. In Paris, around 1200, two '
        'men called Léonin and Pérotin wrote organa in three and four voices: they '
        'are the first composers in Western history whose names survive. From '
        'there to Bach is eight hundred years, and from Bach to now another three '
        'hundred.',
    '**Nueva Orleans (1900–1920).** El primero. Varios instrumentos de viento improvisando a la vez, cada uno su línea, sobre una base de marcha. Es contrapunto puro, hecho por gente que no sabía la palabra contrapunto.':
        '**New Orleans (1900–1920).** The first. Several wind instruments '
        'improvising at once, each with its own line, over a march bass. It is '
        'pure counterpoint, made by people who did not know the word counterpoint.',
    '**Oblicuo** — una se queda quieta y la otra se mueve. Casi tan bueno como el contrario, y gratis: la que no se mueve no gasta nada.':
        '**Oblique** — one stays put and the other moves. Almost as good as '
        'contrary, and free: the one that does not move costs nothing.',
    '**Para qué sirven.** Son un idioma común. Dos músicos que no se conocen se sientan, uno dice un título y una tonalidad, y pueden tocar media hora sin haber ensayado nunca. Eso no existe en casi ninguna otra música.':
        '**What they are for.** They are a common language. Two musicians who have '
        'never met sit down, one says a title and a key, and they can play for '
        'half an hour without ever having rehearsed. That does not exist in '
        'almost any other music.',
    '**Paralelo** — las dos se mueven para el mismo lado la misma distancia, manteniendo el intervalo. Acá empiezan los problemas.':
        '**Parallel** — both move the same way by the same distance, keeping the '
        'interval. This is where the trouble starts.',
    '**Penalizaciones ponderadas.** Movimiento total —el peso más grande de todos—, saltos, espaciado, tesitura, quintas directas, falta de movimiento contrario. Éstas el algoritmo las negocia entre sí: acepta un espaciado peor si a cambio las voces se mueven mucho menos.':
        '**Weighted penalties.** Total motion — the largest weight of all — leaps, '
        'spacing, tessitura, direct fifths, lack of contrary motion. These the '
        'algorithm bargains among themselves: it accepts worse spacing if in '
        'exchange the voices move a great deal less.',
    '**Por eso el temperamento igual es un acuerdo y no una verdad.** Se repartió el error parejo entre las doce notas para que se pudiera tocar en cualquier tonalidad con el mismo instrumento. Se perdió pureza y se ganó libertad, y esa transacción es la que hace posible que este programa module cuando quiere.':
        '**That is why equal temperament is an agreement and not a truth.** The '
        'error was spread evenly across the twelve notes so that you could play '
        'in any key on the same instrument. Purity was lost and freedom was '
        'gained, and that trade is what makes it possible for this program to '
        'modulate whenever it likes.',
    '**Por qué a esa distancia.** Porque la cuarta y la quinta eran los únicos intervalos considerados perfectos. Las terceras --- lo que hoy suena dulce --- se oían como disonancias, y el tritono tenía nombre propio: *diabolus in musica*. El modo gregoriano de este programa usa ese mismo criterio de consonancia, y por eso suena hueco: está bien que suene así.':
        '**Why at that distance.** Because the fourth and the fifth were the only '
        'intervals considered perfect. Thirds — what sounds sweet today — were '
        'heard as dissonances, and the tritone had a name of its own: *diabolus '
        'in musica*. This program’s Gregorian mode uses that same standard of '
        'consonance, and that is why it sounds hollow: it is right that it should.',
    '**Por qué es un chiste.** De tan usada se volvió un lugar común, y los músicos empezaron a citarla a propósito para burlarse de sí mismos. Hay recopilaciones enteras de gente tocándola sin darse cuenta.':
        '**Why it is a joke.** From sheer overuse it became a cliché, and '
        'musicians started quoting it on purpose to make fun of themselves. There '
        'are whole compilations of people playing it without realizing.',
    '**Por qué existe.** Las escalas de África occidental no dividen la octava igual que el piano. Cuando esa manera de cantar se encontró con un instrumento afinado a la europea, las notas que no existían en el teclado se buscaron doblando la cuerda o resbalando la voz. La nota azul es la cicatriz de ese encuentro.':
        '**Why it exists.** West African scales do not divide the octave the way '
        'the piano does. When that way of singing met an instrument tuned the '
        'European way, the notes that did not exist on the keyboard were reached '
        'by bending the string or sliding the voice. The blue note is the scar of '
        'that meeting.',
    '**Por qué funciona.** Es una escala menor recorrida de la forma más eficiente posible: sube por grado conjunto —lo que el capítulo de contrapunto llama el movimiento más barato— y vuelve con un solo salto. Es lo que le sale a una mano que conoce la escala.':
        '**Why it works.** It is a minor scale travelled in the most efficient way '
        'possible: it goes up by step — what the counterpoint chapter calls the '
        'cheapest motion — and comes back with a single leap. It is what comes '
        'out of a hand that knows the scale.',
    '**Por qué la leyenda ganó igual.** Porque explica algo que la otra no: la sensación, al escucharlo, de que hay más de una guitarra sonando. Toca el bajo, el acompañamiento y la melodía a la vez, en un instrumento solo, con una mano que además canta por encima. Eso es contrapunto --- tres voces independientes --- y no lo estudió en ningún lado. Cuando Keith Richards lo escuchó por primera vez preguntó quién era el otro que tocaba con él.':
        '**Why the legend won anyway.** Because it explains something the other '
        'story does not: the feeling, when you listen to him, that more than one '
        'guitar is playing. He plays the bass, the accompaniment and the melody '
        'at once, on a single instrument, with a hand that is also singing on '
        'top. That is counterpoint — three independent voices — and he studied it '
        'nowhere. When Keith Richards first heard him he asked who the other '
        'player was.',
    '**Por qué no termina.** El compás doce no cierra: prepara. Ese último acorde —el quinto grado— empuja de vuelta al compás uno. Por eso se puede tocar toda la noche sin cortar: la forma está diseñada para no tener final, sólo un lugar donde alguien decide parar.':
        '**Why it does not end.** Bar twelve does not close: it prepares. That '
        'last chord — the fifth degree — pushes back to bar one. That is why you '
        'can play all night without stopping: the form is designed to have no '
        'ending, only a place where somebody decides to stop.',
    '**Porque tampoco se sabe dónde está.** Lo enterró la parroquia y nadie anotó en cuál. Hoy hay tres piedras con su nombre en tres cementerios del condado de Leflore, puestas por sellos discográficos y por admiradores. La más aceptada es la de una iglesia en las afueras de Greenwood, y se aceptó por el testimonio de una señora que se acordaba de que su marido había cavado ese pozo. En las tres hay púas, monedas y botellas que dejan los que van.':
        '**Because nobody knows where he is, either.** The parish buried him and '
        'nobody wrote down which one. Today there are three stones with his name '
        'in three cemeteries in Leflore County, put there by record labels and by '
        'admirers. The most accepted is the one at a church outside Greenwood, '
        'and it was accepted on the testimony of a woman who remembered her '
        'husband digging that hole. On all three there are picks, coins and '
        'bottles left by visitors.',
    '**Pulsaciones.** Dos frecuencias casi iguales se suman y se restan por turno, y lo que se oye no son dos notas sino una sola que late. La velocidad del latido es exactamente la diferencia: 440 contra 444 dan cuatro latidos por segundo. Así se afina una guitarra sin aparato —se toca el par y se ajusta hasta que el latido se detiene— y es lo que oís en el experimentador cuando corrés un armónico un par de cents.':
        '**Beats.** Two nearly equal frequencies add and cancel by turns, and what '
        'you hear is not two notes but a single one throbbing. The speed of the '
        'throb is exactly the difference: 440 against 444 gives four beats a '
        'second. That is how you tune a guitar without a device — you play the '
        'pair and adjust until the beating stops — and it is what you hear in the '
        'workbench when you shift a harmonic by a couple of cents.',
    '**Qué la hace sonar así.** Cada acorde comparte notas con el siguiente y el bajo se mueve lo mínimo posible. Es la definición literal de buena conducción de voces, que es todo lo que este programa hace. La emoción no está en ningún acorde particular: está en que ninguno se mueve de más.':
        '**What makes it sound like that.** Each chord shares notes with the next '
        'and the bass moves as little as possible. It is the literal definition '
        'of good voice leading, which is all this program does. The emotion is '
        'not in any particular chord: it is in none of them moving more than they '
        'have to.',
    '**Qué se toca de verdad.** La melodía se toca una vez al principio y una vez al final. En el medio nadie la toca: lo que queda es el esquema de acordes, dando vueltas, y encima de él se inventa. La canción es la excusa.':
        '**What actually gets played.** The melody is played once at the start and '
        'once at the end. In between nobody plays it: what is left is the chord '
        'scheme, going round, and you invent on top of it. The song is the '
        'excuse.',
    '**Rango.** Un oído joven va de unos 20 hercios a unos 20.000, y el techo baja con los años. Un piano entero entra entre 27 y 4.186 hercios; todo lo que hay por encima de eso son armónicos, no notas. Es decir: la mitad de lo que escuchás de un instrumento está en una zona donde ninguna nota podría escribirse.':
        '**Range.** A young ear runs from about 20 hertz to about 20,000, and the '
        'ceiling drops with the years. A whole piano fits between 27 and 4,186 '
        'hertz; everything above that is harmonics, not notes. Which is to say: '
        'half of what you hear from an instrument is in a region where no note '
        'could be written at all.',
    '**Resonancia.** Todo objeto tiene frecuencias en las que le sale fácil vibrar. Si le llega justo ésa, se prende sin que nadie lo toque. Es la caja de una guitarra, es la tapa de un piano, es por qué una sala amplifica unas notas más que otras. Un instrumento es un resonador con algo que lo excita.':
        '**Resonance.** Every object has frequencies at which it vibrates easily. '
        'If exactly that one reaches it, it lights up without anyone touching it. '
        'It is a guitar’s body, it is a piano’s soundboard, it is why a hall '
        'amplifies some notes more than others. An instrument is a resonator with '
        'something to excite it.',
    '**Restricciones duras.** Rango vocal, cobertura del acorde, cruce de voces, y las paralelas o el tritono que hayas prendido. Romper una de éstas no suma costo: anula el cromosoma entero, que deja de competir. Por eso una regla dura nunca aparece violada en el resultado.':
        '**Hard constraints.** Vocal range, chord coverage, voice crossing, and '
        'whichever parallels or tritone rule you have switched on. Breaking one '
        'of these does not add cost: it voids the whole chromosome, which stops '
        'competing. That is why a hard rule never shows up broken in the result.',
    '**Se canta, no se toca.** Nada de saltos imposibles, nada de notas fuera del alcance de una garganta común, y una respiración donde termina cada frase. Por eso el modo coral de este programa recorta los rangos y aprieta los saltos.':
        '**It is sung, not played.** No impossible leaps, no notes beyond the '
        'reach of an ordinary throat, and a breath where each phrase ends. That '
        'is why this program’s chorale mode trims the ranges and tightens the '
        'leaps.',
    '**Se llamaba Johann Sebastian Bach.** Murió en 1750, y con esa fecha se cierra el barroco entero: para cuando murió, sus propios hijos escribían de otra manera y lo consideraban un viejo pasado de moda. Durante ochenta años casi nadie lo tocó. Lo desenterró un chico de veinte, Mendelssohn, en 1829, dirigiendo una Pasión que llevaba un siglo sin sonar.':
        '**His name was Johann Sebastian Bach.** He died in 1750, and that date '
        'closes the whole baroque: by the time he died his own sons were writing '
        'differently and considered him an old man behind the times. For eighty '
        'years almost nobody played him. He was dug up by a twenty-year-old, '
        'Mendelssohn, in 1829, conducting a Passion that had gone unheard for a '
        'century.',
    '**Su cadencia.** El góspel se apoya en la cadencia plagal, el amén del capítulo anterior: el cuarto grado cayendo sobre el primero. No empuja como la cadencia auténtica. Llega y se queda.':
        '**Its cadence.** Gospel leans on the plagal cadence, the amen from the '
        'previous chapter: the fourth degree falling onto the first. It does not '
        'push the way the authentic cadence does. It arrives and it stays.',
    '**Su firma.** En alemán, las notas si bemol, la, do y si natural se escriben B, A, C, H: su apellido es una melodía. La usó como tema en lo último que estaba escribiendo, y esa fuga se corta en la mitad de un compás. Lo que sigue después del corte no existe.':
        '**His signature.** In German, the notes B flat, A, C and B natural are '
        'written B, A, C, H: his surname is a melody. He used it as a theme in '
        'the last thing he was writing, and that fugue breaks off in the middle '
        'of a bar. What comes after the break does not exist.',
    '**Subdominante (IV y ii).** Es salir de casa. No hay tensión todavía, pero ya no estás en reposo.':
        '**Subdominant (IV and ii).** It is leaving the house. There is no tension '
        'yet, but you are no longer at rest.',
    '**Swing (1930–1945).** Orquestas grandes, arreglos escritos, música para bailar. Es el jazz que fue música popular masiva, el único que lo fue.':
        '**Swing (1930–1945).** Big bands, written arrangements, music to dance '
        'to. It is the jazz that was mass popular music, the only one that was.',
    '**Todo lo que suena en este programa está escrito así.** El clavecín, la lluvia, el tren, los pasos, cada nota del botón «Escuchar»: 44.100 números por segundo, calculados uno por uno, sin ninguna librería de audio en el medio.':
        '**Everything that sounds in this program is written this way.** The '
        'harpsichord, the rain, the train, the footsteps, every note of the '
        '“Play” button: 44,100 numbers a second, calculated one at a time, with '
        'no audio library in between.',
    '**Tónica (I, y de refilón vi y iii).** Es la casa. Cuando la música llega ahí, descansa.':
        '**Tonic (I, and in passing vi and iii).** It is home. When the music gets '
        'there, it rests.',
    '**Un parlante no sabe nada de cuerdas.** Empuja aire y vuelve, y alguien tiene que decirle cuánto empujar en cada instante. Eso es una lista de números y nada más.':
        '**A speaker knows nothing about strings.** It pushes air and comes back, '
        'and somebody has to tell it how hard to push at each instant. That is a '
        'list of numbers and nothing more.',
    '**Una cuerda no vibra de una sola manera.** Vibra entera, y a la vez en dos mitades, en tres tercios, en cuatro cuartos, hasta donde el material dé. Cada división suena, y todas suenan juntas desde el primer instante. Eso es la serie armónica, y no la inventó nadie: es lo que le pasa a un cuerpo que se estira.':
        '**A string does not vibrate in one way only.** It vibrates whole, and at '
        'the same time in two halves, in three thirds, in four quarters, as far '
        'as the material will take it. Every division sounds, and they all sound '
        'together from the first instant. That is the harmonic series, and nobody '
        'invented it: it is what happens to a body under tension.',
    '**Y de acá salen los intervalos.** El segundo armónico es la octava. El tercero es la quinta. El quinto es la tercera mayor. No es casualidad que la música haya empezado por octavas y quintas y haya tardado seiscientos años en aceptar la tercera: es el orden en que aparecen. Gregorio cantaba en cuartas y quintas porque eran los primeros escalones de una escalera que nadie había terminado de subir.':
        '**And the intervals come out of this.** The second harmonic is the '
        'octave. The third is the fifth. The fifth is the major third. It is no '
        'accident that music started with octaves and fifths and took six hundred '
        'years to accept the third: that is the order in which they appear. '
        'Gregory sang in fourths and fifths because they were the first rungs of '
        'a staircase nobody had finished climbing.',
    '**Y el molde le quedó para siempre.** De acá en adelante, cualquier cosa que se cuente de él va a estar contada contra esta historia: la del que tocaba mal, se fue una noche y volvió sabiendo. Lo que se puede averiguar es de dónde salió esa historia y qué le hizo --- pero eso es otra noche.':
        '**And the mould stuck to him forever.** From here on, anything told about '
        'him will be told against this story: the one about the man who played '
        'badly, went away one night and came back knowing how. What can be found '
        'out is where that story came from and what it did to him — but that is '
        'another night.',
    '**Y el segundo molde: los veintisiete años.** Murió a esa edad, y cuando décadas más tarde varios músicos famosos murieron a la misma, alguien hizo la lista y la llamó un club. Los estudios que la miraron en serio no encuentran ninguna anomalía: los músicos se mueren jóvenes a los veintiséis y a los veintiocho con la misma frecuencia, y nadie escribe sobre eso. Es el mismo mecanismo que el pacto --- un patrón dibujado después, sobre muertes que ya estaban --- y a él le tocaron los dos.':
        '**And the second mould: the age of twenty-seven.** He died at that age, '
        'and when decades later several famous musicians died at the same one, '
        'somebody made the list and called it a club. The studies that looked at '
        'it seriously find no anomaly: musicians die young at twenty-six and at '
        'twenty-eight just as often, and nobody writes about that. It is the same '
        'mechanism as the bargain — a pattern drawn afterwards over deaths that '
        'were already there — and he got both.',
    '**Y el séptimo escalón no tiene tecla.** Cae treinta y una centésimas de semitono por debajo de la séptima menor del piano. Cuando en un blues se oye una nota que parece estar en un lugar que el instrumento no tiene, está: es ésa.':
        '**And the seventh rung has no key.** It falls thirty-one hundredths of a '
        'semitone below the piano’s minor seventh. When you hear a note in a '
        'blues that seems to be in a place the instrument does not have, it is: '
        'that is the one.',
    '**Y la leyenda le sirvió a todo el mundo menos a él.** A los que decían que esa música era peligrosa les confirmaba que lo era. A los sellos que lo reeditaron en los años sesenta les daba una tapa. A los músicos blancos que lo descubrieron entonces les daba un santo. Al muerto no le dio nada: se murió a los veintisiete en 1938, cobrando por noche, y el disco que lo hizo famoso salió veintitrés años después.':
        '**And the legend served everybody except him.** To those who said that '
        'music was dangerous it confirmed that it was. To the labels that '
        'reissued him in the sixties it gave a cover. To the white musicians who '
        'discovered him then it gave a saint. To the dead man it gave nothing: he '
        'died at twenty-seven in 1938, paid by the night, and the record that '
        'made him famous came out twenty-three years later.',
    '**Y la nota que no está en el acorde, nunca.** No es una preferencia sino un rechazo: armonizar una nota de paso como si fuera estructural es la manera principal en que esto sale mal, y el programa la castiga tanto que sólo la elige cuando no le quedó absolutamente nada.':
        '**And the note that is not in the chord, never.** It is not a preference '
        'but a refusal: harmonizing a passing note as though it were structural '
        'is the main way this goes wrong, and the program penalizes it so heavily '
        'that it only picks it when it has absolutely nothing else left.',
    '**Y siguió creciendo sin él.** En 1986 lo metieron en el Salón de la Fama del rock como influencia temprana. En 1990 salió la caja con sus grabaciones completas y vendió más de un millón de copias: un disco de un hombre muerto hacía medio siglo, que en vida cobraba por noche, vendiendo más que cualquier cosa que él haya visto cobrar.':
        '**And it went on growing without him.** In 1986 he was put into the rock '
        'hall of fame as an early influence. In 1990 the box set of his complete '
        'recordings came out and sold over a million copies: a record by a man '
        'dead half a century, who in life was paid by the night, outselling '
        'anything he ever saw anyone paid for.',
    '**Y sin embargo.** Sigue funcionando. Un lugar común lo es porque durante mucho tiempo fue verdad.':
        '**And even so.** It still works. A cliché is one because for a long time '
        'it was true.',
    '**«La música del diablo» era una acusación en serio.** En el Sur segregado, la iglesia negra y el juke joint se repartían la semana y no se hablaban: el sábado a la noche era del blues y el domingo a la mañana del góspel, y quien cruzaba esa línea la pagaba. Son House pasó la vida yendo y viniendo entre predicar y tocar, sin poder quedarse de ningún lado. Thomas A. Dorsey, que había grabado blues subidos de tono como *Georgia Tom*, inventó después la canción de góspel moderna y al principio lo echaron de las iglesias por meter el ritmo del pecado adentro del templo. Hoy se canta en todas.':
        '**“The devil’s music” was a serious accusation.** In the segregated '
        'South, the Black church and the juke joint divided the week between them '
        'and did not speak: Saturday night belonged to the blues and Sunday '
        'morning to gospel, and whoever crossed that line paid for it. Son House '
        'spent his life going back and forth between preaching and playing, '
        'unable to settle on either side. Thomas A. Dorsey, who had recorded '
        'risqué blues as *Georgia Tom*, later invented the modern gospel song and '
        'at first was thrown out of churches for bringing the rhythm of sin into '
        'the temple. Today it is sung in all of them.',
    '**Él nunca la desmintió, y encima cantó como si fuera cierta.** Grabó *Cross Road Blues*, *Me and the Devil Blues* y *Hellhound on My Trail* --- un perro del infierno siguiéndole el rastro --- y en las tres canta en primera persona. Un músico que se dedica a tocar de noche en lugares donde hay que llamar la atención no tiene ningún motivo para desmentir una historia así.':
        '**He never denied it, and on top of that he sang as though it were '
        'true.** He recorded *Cross Road Blues*, *Me and the Devil Blues* and '
        '*Hellhound on My Trail* — a hellhound on his trail — and in all three he '
        'sings in the first person. A musician who makes his living playing at '
        'night in places where you have to draw attention has no reason at all to '
        'deny a story like that.',
    '5º armónico': '5th harmonic',
    '7º armónico': '7th harmonic',
    'A una tríada se le puede apilar una nota más, la séptima. G se convierte en G7, y el acorde deja de ser un lugar donde quedarse: la séptima es un intervalo tenso y pide resolver.':
        'One more note can be stacked on a triad: the seventh. G becomes G7, and '
        'the chord stops being a place to stay: the seventh is a tense interval '
        'and it asks to resolve.',
    'Acá está el corazón del programa. Todas las reglas que podés prender y apagar en la pantalla de reglas son formas de contestar una sola pregunta: ¿cómo pasan las voces de un acorde al siguiente?':
        'Here is the heart of the program. Every rule you can switch on and off on '
        'the rules screen is a way of answering a single question: how do the '
        'voices get from one chord to the next?',
    'Acá está el hecho del que cuelga todo lo demás, y es un hecho físico, no una convención: **nada vibra de una sola manera.**':
        'Here is the fact everything else hangs off, and it is a physical fact, '
        'not a convention: **nothing vibrates in one way only.**',
    'Acá lo que manda no es el bajo sino cómo se encadenan dos notas de cada acorde: la tercera y la séptima, que en la jerga son las guide tones. Son las que definen si un acorde es mayor, menor o dominante; el resto es relleno.':
        'What rules here is not the bass but how two notes of each chord link up: '
        'the third and the seventh, which in the jargon are the guide tones. They '
        'are the ones that define whether a chord is major, minor or dominant; '
        'the rest is filler.',
    'Acústica: lo que le pasa al sonido en el camino':
        'Acoustics: what happens to sound along the way',
    'Adentro del barroco hay un interruptor, «Modo coral», que lo aprieta todavía más. Es el estilo de los corales de Bach: nunca duplica la sensible, exige que las séptimas resuelvan hacia abajo, salta menos y no tolera el solapamiento de voces. Escribe más ceñido y se mueve menos libremente.':
        'Inside the baroque there is a switch, “Chorale mode”, that tightens it '
        'further still. It is the style of Bach’s chorales: it never doubles the '
        'leading tone, it requires sevenths to resolve downward, it leaps less '
        'and it does not tolerate overlapping voices. It writes tighter and moves '
        'less freely.',
    'Ahí es donde trabaja este programa. Los acordes los ponés vos (o los inventa él, según el modo); lo que decide el algoritmo es qué nota del acorde canta cada voz y en qué octava, de manera que cada línea se mueva lo menos posible y que las líneas no choquen entre sí. Eso es la conducción de voces, y es el oficio entero de este programa.':
        'That is where this program works. You bring the chords (or it invents '
        'them, depending on the mode); what the algorithm decides is which note '
        'of the chord each voice sings and in which octave, so that each line '
        'moves as little as possible and the lines do not collide. That is voice '
        'leading, and it is this program’s whole craft.',
    'Aire que se comprime y se descomprime. Algo se mueve —una cuerda, una lengüeta, unas cuerdas vocales—, empuja el aire que tiene alrededor, ese aire empuja al de al lado, y así hasta tu oído. No viaja aire: viaja el empujón.':
        'Air compressing and decompressing. Something moves — a string, a reed, a '
        'pair of vocal cords — and pushes the air around it, that air pushes the '
        'air next to it, and so on to your ear. Air does not travel: the push '
        'travels.',
    'Al lado de la clave puede haber sostenidos o bemoles: es la armadura, y dice qué notas van alteradas en toda la pieza. Y después van dos números, uno sobre otro: el compás, que dice cómo se agrupan los tiempos. En 4/4 hay cuatro negras por compás.':
        'Next to the clef there may be sharps or flats: that is the key '
        'signature, and it says which notes are altered throughout the piece. And '
        'then come two numbers, one over the other: the time signature, which '
        'says how the beats are grouped. In 4/4 there are four quarter notes to '
        'the bar.',
    'Alrededor del año 800 la iglesia de occidente unificó su repertorio de cantos en un cuerpo único, que la leyenda le atribuyó al papa Gregorio Magno aunque él llevara dos siglos muerto. De ahí el nombre. Era música de una sola línea, sin acompañamiento y sin ritmo medido: la palabra manda, y la melodía la sigue.':
        'Around the year 800 the Western church unified its repertoire of chants '
        'into a single body, which legend attributed to Pope Gregory the Great '
        'although he had been dead two centuries. Hence the name. It was music of '
        'a single line, without accompaniment and without measured rhythm: the '
        'word rules, and the melody follows it.',
    'Ampliado, para que se vea. Las barras son los armónicos quinto y séptimo de la2; las marcas de abajo son dónde el piano pone esas mismas notas. El séptimo se va casi un tercio de semitono.':
        'Blown up so it can be seen. The bars are the fifth and seventh harmonics '
        'of A2; the marks below are where the piano puts those same notes. The '
        'seventh strays by almost a third of a semitone.',
    'Antes de que existiera la tonalidad como la conocemos, la música se escribía así. Por eso el estilo gregoriano de este programa trabaja en modos y no en mayor/menor.':
        'Before tonality as we know it existed, music was written this way. That '
        'is why this program’s Gregorian style works in modes and not in '
        'major/minor.',
    'Apagar la regla y escuchar el resultado es la mejor manera de entender por qué existe. Buscá el momento donde dos voces suben juntas: vas a oír cómo por un instante se funden en un solo sonido y la textura se aplana.':
        'Switching the rule off and listening to the result is the best way to '
        'understand why it exists. Look for the moment where two voices rise '
        'together: you will hear how for an instant they melt into a single sound '
        'and the texture flattens out.',
    'Apareció con la quinta partitura a una sola voz. Traía una paloma en el hombro y no la nombró en ningún momento, como si fuera parte de la ropa.':
        'He appeared with the fifth single-voice score. He had a dove on his '
        'shoulder and never once mentioned it, as though it were part of his '
        'clothing.',
    'Armonizar es contestar una pregunta por vez: **debajo de esta nota, ¿qué acorde va?** La nota no se toca. Lo único que se elige es qué la acompaña.':
        'Harmonizing is answering one question at a time: **under this note, '
        'which chord goes?** The note is not touched. The only thing chosen is '
        'what accompanies it.',
    'Armonizar una melodía': 'Harmonizing a melody',
    'Bach es el final del período y su resumen. Sus corales —las armonizaciones a cuatro voces de melodías luteranas— son desde hace dos siglos el material con el que se enseña armonía, porque en cuatro compases hay más decisiones bien tomadas que en piezas veinte veces más largas. El «Modo coral» del programa es el intento de escribir como ellos.':
        'Bach is the end of the period and its summary. His chorales — the '
        'four-voice harmonizations of Lutheran melodies — have for two centuries '
        'been the material harmony is taught with, because four bars of them '
        'contain more well-made decisions than pieces twenty times longer. The '
        'program’s “Chorale mode” is the attempt to write like them.',
    'Barroco o Modo coral. Aparece por azar, así que puede hacer falta generar varias veces.':
        'Baroque or Chorale mode. It turns up by chance, so you may have to '
        'generate several times.',
    'Cadencias y giros': 'Cadences and turns',
    'Cambiarla cambia por completo la textura: la voz elegida se vuelve el centro y todo lo demás se acomoda alrededor.':
        'Changing it changes the texture completely: the chosen voice becomes the '
        'centre and everything else arranges itself around it.',
    'Casi todo lo demás de este capítulo son maneras de retrasar, adornar o esquivar este gesto.':
        'Almost everything else in this chapter is a way of delaying, decorating '
        'or dodging this gesture.',
    'Casi todo lo que suena hoy lo inventó gente a la que no le permitían tocar. Este capítulo no se llena estudiando: se llena caminando.':
        'Almost everything that sounds today was invented by people who were not '
        'allowed to play. This chapter does not fill up by studying: it fills up '
        'by walking.',
    'Cinco líneas y los cuatro espacios entre ellas. Cada línea y cada espacio es una nota, y se van alternando: si mi está en una línea, fa está en el espacio de arriba, sol en la línea siguiente, y así. Cuanto más arriba se escribe, más agudo suena.':
        'Five lines and the four spaces between them. Every line and every space '
        'is a note, and they alternate: if E is on a line, F is in the space '
        'above, G on the next line, and so on. The higher you write, the higher '
        'it sounds.',
    'Cinco palabras. Con estas cinco alcanza para leer todo lo demás y para entender qué está haciendo el programa cuando trabaja.':
        'Five words. These five are enough to read everything else and to '
        'understand what the program is doing while it works.',
    'Con cinco o seis voces empiezan a sobrar: alguna nota se duplica, o el programa agrega color en vez de duplicar, según cómo tengas el dial. Duplicar la fundamental o la quinta es seguro; duplicar la sensible es lo único que nunca conviene, porque son dos voces tirando al mismo lugar y una de las dos va a llegar mal.':
        'With five or six voices there start to be too many: some note gets '
        'doubled, or the program adds color instead of doubling, depending on '
        'where you have the dial. Doubling the root or the fifth is safe; '
        'doubling the leading tone is the one thing that is never a good idea, '
        'because that is two voices pulling to the same place and one of them '
        'will arrive badly.',
    'Contrario: una sube, la otra baja.': 'Contrary: one rises, the other falls.',
    'Cuando dos voces amenazan con caer en quintas paralelas hay dos salidas: reordenar las voces, o escribir una de esas quintas como sexta. La segunda es más barata y no toca el resto de la textura.':
        'When two voices threaten to fall into parallel fifths there are two ways '
        'out: reorder the voices, or write one of those fifths as a sixth. The '
        'second is cheaper and leaves the rest of the texture alone.',
    'Cuando el ciclo vuelve a empezar, la nota suena «la misma pero más aguda». A esa distancia se le dice octava. Por eso las notas llevan un número al lado: C4 es el do central de un piano, C5 es el do de arriba, C3 el de abajo. En los resultados vas a ver siempre notas escritas así.':
        'When the cycle starts over, the note sounds “the same but higher”. That '
        'distance is called an octave. That is why notes carry a number beside '
        'them: C4 is middle C on a piano, C5 is the C above, C3 the one below. In '
        'the results you will always see notes written this way.',
    'Cuando el programa arma un acorde de séptima, se ocupa además de que esa séptima resuelva bajando un grado. Es la regla que hace que el acorde suene resuelto y no abandonado.':
        'When the program builds a seventh chord, it also sees to it that the '
        'seventh resolves down by a step. It is the rule that makes the chord '
        'sound resolved rather than abandoned.',
    'Cuando la dejás pasar': 'When you let it through',
    'Cuando una nota se va del pentagrama se le dibuja su propia rayita, la línea adicional. El do central —el do del medio del piano— cae justo una línea adicional por debajo de la clave de sol, y por eso es la referencia con la que todo el mundo se ubica.':
        'When a note goes off the staff it gets its own little line, the ledger '
        'line. Middle C — the C in the middle of the piano — falls exactly one '
        'ledger line below the treble clef, and that is why it is the landmark '
        'everyone finds their bearings by.',
    'Cuatro notas en un compás de cuatro por cuatro. El acorde cambia en el uno y en el tres; la segunda y la cuarta se escuchan contra el que ya está.':
        'Four notes in a four-four bar. The chord changes on one and on three; '
        'the second and the fourth are heard against the one already sounding.',
    'Cuatro voces —bajo, tenor, alto, soprano— es el estándar porque un acorde de séptima tiene exactamente cuatro notas y cada voz puede llevar una.':
        'Four voices — bass, tenor, alto, soprano — is the standard because a '
        'seventh chord has exactly four notes and each voice can carry one.',
    'Cómo elige los acordes': 'How it chooses the chords',
    'Cómo funciona el programa por dentro, en resumen. No hace falta leer esto para usarlo, pero explica por qué a veces da resultados distintos con la misma entrada.':
        'How the program works inside, in summary. You do not need to read this '
        'to use it, but it explains why it sometimes gives different results from '
        'the same input.',
    'Cómo se escribe un sonido en una máquina':
        'How a sound gets written down in a machine',
    'Cómo se mueven las voces': 'How the voices move',
    'Cómo se puntúa una solución': 'How a solution is scored',
    'De ahí salen las dos cosas que se pueden medir. **Cuántas veces por segundo** se repite el empujón es la frecuencia, y se mide en hercios: eso es lo que oís como altura, grave o agudo. **Cuánto** empuja es la amplitud, y eso es lo que oís como volumen.':
        'Out of that come the two things that can be measured. **How many times a '
        'second** the push repeats is the frequency, measured in hertz: that is '
        'what you hear as pitch, low or high. **How hard** it pushes is the '
        'amplitude, and that is what you hear as volume.',
    'De dónde viene cada estilo': 'Where each style comes from',
    'De los siete grados, tres papeles alcanzan para entender casi todo:':
        'Of the seven degrees, three roles are enough to understand almost '
        'everything:',
    'De qué está hecho un sonido, por qué unas notas se llevan bien con otras antes de que ninguna cultura lo decidiera, y por qué el piano está afinado mal a propósito. Este capítulo se escribe solo cuando abrís el experimentador de armónicos y movés algo.':
        'What a sound is made of, why some notes get along with others before any '
        'culture decided it, and why the piano is deliberately tuned wrong. This '
        'chapter writes itself when you open the harmonics workbench and move '
        'something.',
    'Después de la séptima se puede seguir apilando: novena, oncena, trecena. Esas notas ya no cambian la función del acorde —un C9 sigue siendo la tónica— pero le cambian el color, lo vuelven más denso y más moderno.':
        'After the seventh you can go on stacking: ninth, eleventh, thirteenth. '
        'Those notes no longer change the chord’s function — a C9 is still the '
        'tonic — but they change its color, make it denser and more modern.',
    'Directo: las dos para el mismo lado, distinta distancia.':
        'Direct: both the same way, by different distances.',
    'Do y la llevan acorde. El si del medio es de paso: se escucha contra el acorde de do y no pide nada.':
        'C and A carry a chord. The B in between is passing: it is heard against '
        'the C chord and asks for nothing.',
    'Doce compases, siempre los mismos, siempre en el mismo orden: cuatro sobre el primer grado, dos sobre el cuarto, dos sobre el primero otra vez, y los últimos cuatro bajando desde el quinto hasta el giro que devuelve todo al principio.':
        'Twelve bars, always the same, always in the same order: four on the first '
        'degree, two on the fourth, two on the first again, and the last four '
        'coming down from the fifth to the turnaround that sends it all back to '
        'the start.',
    'Dos acordes de dominante que están a distancia de tritono comparten el mismo tritono adentro: G7 y Db7 tienen los dos el si y el fa. Como el tritono es lo que define la tensión, uno puede reemplazar al otro.':
        'Two dominant chords a tritone apart share the same tritone inside them: '
        'G7 and Db7 both have B and F. Since the tritone is what defines the '
        'tension, either can replace the other.',
    'Dos frecuencias a cuatro hercios de distancia. No se oyen como dos notas: se oye una que sube y baja de volumen cuatro veces por segundo.':
        'Two frequencies four hertz apart. They are not heard as two notes: you '
        'hear one going up and down in volume four times a second.',
    'Dos voces se cruzan cuando la de abajo pasa a estar por encima de la de arriba. Se escucha confuso y por eso está prohibido por defecto, aunque lo podés permitir.':
        'Two voices cross when the lower one ends up above the upper one. It '
        'sounds confusing and that is why it is forbidden by default, though you '
        'can allow it.',
    'Dónde va cada acorde': 'Where each chord goes',
    'El Armonizador hace lo mismo pero al revés: recorre la melodía **de atrás para adelante**. Suena raro hasta que se piensa un segundo: saber que el acorde siguiente es un punto de reposo es exactamente lo que te dice que el actual quiere ser dominante. Hacia adelante esa información todavía no existe.':
        'The Harmonizer does the same thing but backwards: it walks the melody '
        '**from the end to the beginning**. It sounds odd until you think about '
        'it for a second: knowing that the next chord is a resting point is '
        'exactly what tells you the current one wants to be a dominant. Going '
        'forwards, that information does not exist yet.',
    'El V prepara la tónica y en el último momento cae en el sexto grado: en do mayor, G va a Am en vez de a C. La resolución se posterga y la frase, que parecía terminada, sigue.':
        'The V prepares the tonic and at the last moment lands on the sixth '
        'degree: in C major, G goes to Am instead of C. The resolution is put off '
        'and the phrase, which seemed finished, goes on.',
    'El acorde de tónica se sostiene mientras el bajo baja paso a paso por debajo. Las voces de arriba no se mueven: todo es movimiento oblicuo, y por eso la línea del bajo se escucha con una claridad que no tendría de otra manera.':
        'The tonic chord is held while the bass walks down step by step '
        'underneath. The upper voices do not move: it is all oblique motion, and '
        'that is why the bass line is heard with a clarity it would not otherwise '
        'have.',
    'El acorde disminuido': 'The diminished chord',
    'El algoritmo genético': 'The genetic algorithm',
    'El bajo baja de a un escalón, sin saltarse ninguno, desde la tónica hasta la tónica de la octava de abajo. Sobre cada escalón se pone el acorde que le corresponde, y varios de ellos quedan invertidos: con la tercera o la quinta en el bajo, que es lo que permite que la línea camine sin baches.':
        'The bass walks down one step at a time, skipping none, from the tonic to '
        'the tonic an octave below. On each step goes the chord that belongs '
        'there, and several of them come out inverted: with the third or the '
        'fifth in the bass, which is what lets the line walk without potholes.',
    'El bajo queda fuera a propósito: un adorno ahí abajo enturbia la armonía en vez de decorarla.':
        'The bass is left out on purpose: an ornament down there muddies the '
        'harmony instead of decorating it.',
    'El barroco escribe sobre bajo cifrado: se anota la línea del bajo con números debajo que dicen qué intervalos van encima, y el intérprete completa. Esa taquigrafía es la abuela directa del cifrado americano que usás en el Organizador, y la razón por la que el programa habla de intervalos «medidos desde el bajo».':
        'The baroque writes over figured bass: the bass line is notated with '
        'numbers under it saying which intervals go above, and the player fills '
        'in the rest. That shorthand is the direct grandmother of the chord '
        'symbols you use in the Organizer, and the reason the program talks about '
        'intervals “measured from the bass”.',
    'El barroco y la práctica común': 'The baroque and common practice',
    'El canto llano y el organum': 'Plainchant and organum',
    'El cifrado americano es taquigrafía para esto. C es do mayor, Am es la menor, G7 es sol con una séptima agregada, F#m7b5 es fa sostenido menor con séptima y la quinta rebajada. Lo que va antes del paréntesis mental es la fundamental; todo lo que sigue describe qué se le apila encima.':
        'Chord symbols are shorthand for this. C is C major, Am is A minor, G7 is '
        'G with a seventh added, F#m7b5 is F sharp minor with a seventh and a '
        'flattened fifth. What comes before the mental bracket is the root; '
        'everything after it describes what gets stacked on top.',
    'El color se prende en la pantalla de reglas del Armonizador. Sin él, las únicas notas donde la melodía se para son la tercera, la quinta y la fundamental.':
        'Color is switched on in the Harmonizer’s rules screen. Without it, the '
        'only notes the melody comes to rest on are the third, the fifth and the '
        'root.',
    'El coral': 'The chorale',
    'El costo es una suma, y menos es mejor. Se divide en dos clases muy distintas.':
        'The cost is a sum, and less is better. It splits into two very different '
        'kinds.',
    'El cálculo es impecable y el problema es que **no la produce nada**. Una cuerda que vibra genera sus múltiplos porque puede partirse en pedazos iguales; no hay ninguna manera de que además genere sus divisores, porque eso exigiría que la cuerda fuera más larga de lo que es. Es una simetría matemática sin cuerpo que la sostenga.':
        'The arithmetic is impeccable and the problem is that **nothing produces '
        'it**. A vibrating string generates its multiples because it can split '
        'into equal pieces; there is no way for it to also generate its divisors, '
        'because that would require the string to be longer than it is. It is a '
        'mathematical symmetry with no body to hold it up.',
    'El del cruce de caminos': 'The one at the crossroads',
    'El dial «¿Qué te importa más?» de la pantalla de reglas mueve el balance entre el grupo de movimiento y el grupo de estilo. Todo lo demás son valores por defecto que el estilo elegido fija y que podés tocar de a uno.':
        'The “What matters more to you?” dial on the rules screen shifts the '
        'balance between the motion group and the style group. Everything else is '
        'defaults that the chosen style sets and that you can change one at a '
        'time.',
    'El dórico es un menor con la sexta alta: suena menos triste, más abierto. El frigio tiene la segunda baja y suena español. El lidio tiene la cuarta alta y suena flotante. El mixolidio es un mayor con la séptima baja, y es el modo del blues y del rock.':
        'Dorian is a minor with a raised sixth: it sounds less sad, more open. '
        'Phrygian has a lowered second and sounds Spanish. Lydian has a raised '
        'fourth and sounds like it is floating. Mixolydian is a major with a '
        'lowered seventh, and it is the mode of blues and rock.',
    'El efecto es que el bajo, en vez de saltar una quinta, baja un semitono: Dm7 - Db7 - Cmaj7. Es uno de los sonidos más reconocibles del jazz moderno.':
        'The effect is that the bass, instead of leaping a fifth, falls a '
        'semitone: Dm7 - Db7 - Cmaj7. It is one of the most recognizable sounds '
        'of modern jazz.',
    'El espaciado es la distancia entre voces vecinas. Lo normal es que las voces agudas estén juntas y el bajo más separado, como en un acorde de piano: la mano derecha cerrada y la izquierda lejos. Si se abren todas por igual, el acorde suena hueco.':
        'Spacing is the distance between neighbouring voices. The norm is for the '
        'upper voices to sit close together and the bass further away, as in a '
        'piano chord: the right hand closed and the left hand far off. If they '
        'all open out equally, the chord sounds hollow.',
    'El estilo no toca los acordes. Lo que cambia es qué se prohíbe, qué se premia y con cuánta fuerza: la misma progresión escrita en dos estilos distintos da dos piezas distintas.':
        'The style does not touch the chords. What changes is what is forbidden, '
        'what is rewarded and how strongly: the same progression written in two '
        'different styles gives two different pieces.',
    'El experimentador está al lado de los logros. Cada barra es uno de estos armónicos: arrastrala para arriba y la amplificás, hacé doble clic y la escuchás sola.':
        'The workbench is next to the achievements. Each bar is one of these '
        'harmonics: drag it up and you amplify it, double-click and you hear it '
        'on its own.',
    'El giro que sostiene casi todo el repertorio de jazz. La subdominante prepara la dominante y ésta resuelve: en do, Dm7 - G7 - Cmaj7.':
        'The turn that holds up almost the whole jazz repertoire. The subdominant '
        'prepares the dominant and the dominant resolves: in C, Dm7 - G7 - Cmaj7.',
    'El góspel': 'Gospel',
    'El ii - V - I': 'The ii - V - I',
    'El ii-V-I se vuelve la célula básica del lenguaje, hasta el punto de que un músico de jazz lee una progresión entera como una cadena de ii-V encadenados. De ahí también sale la obsesión con las guide tones: cuando los acordes tienen cinco o seis notas, lo único que hay que cuidar de verdad es cómo se encadenan la tercera y la séptima.':
        'The ii-V-I becomes the basic cell of the language, to the point where a '
        'jazz musician reads a whole progression as a chain of linked ii-Vs. The '
        'obsession with guide tones comes from there too: when chords have five '
        'or six notes, the only thing that really needs looking after is how the '
        'third and the seventh link up.',
    'El jazz': 'Jazz',
    'El mismo camino una tercera vez, y esta vez sin tren y sin nadie parado en él. Se largó una tormenta encima, y en el medio del camino había una piedra con una cruz. Decía «acá yace un bluesero», sin nombre. Después, sobre el negro, la misma voz de la vez anterior saludó a alguien por su apellido, como quien se encuentra con un conocido.':
        'The same road a third time, and this time no train and nobody standing '
        'on it. A storm broke overhead, and in the middle of the road there was a '
        'stone with a cross. It said “here lies a bluesman”, with no name. Then, '
        'over the black, the same voice as last time greeted somebody by their '
        'surname, the way you greet an acquaintance.',
    'El mismo do5 sostenido por tres acordes distintos. A la izquierda es la tercera, en el medio la quinta, a la derecha la fundamental.':
        'The same C5 held up by three different chords. On the left it is the '
        'third, in the middle the fifth, on the right the root.',
    'El mismo giro se puede apuntar a cualquier grado, no sólo a la tónica: se toma prestada la dominante de donde se quiere ir y se aterriza ahí. Eso es un ii-V secundario, y es la manera de encadenar tonalidades sin modular del todo.':
        'The same turn can be aimed at any degree, not just the tonic: you borrow '
        'the dominant of where you want to go and land there. That is a secondary '
        'ii-V, and it is the way to chain keys together without fully modulating.',
    'El motivo es acústico, no moral. La quinta y la octava son los intervalos más «vacíos», los que más se funden. Cuando dos voces se mueven en paralelo a esa distancia, el oído deja de escuchar dos voces y escucha una sola con un timbre raro. Se pierde justo lo que se estaba tratando de construir.':
        'The reason is acoustic, not moral. The fifth and the octave are the '
        '“emptiest” intervals, the ones that blend most. When two voices move in '
        'parallel at that distance, the ear stops hearing two voices and hears '
        'one with an odd timbre. You lose exactly what you were trying to build.',
    'El motivo es que el costo premia el mínimo movimiento, y un adorno siempre agrega movimiento. Dentro del fitness, un adorno sólo podía ganar si se le pagaba con una recompensa, y esa recompensa distorsionaba todo lo demás: la búsqueda empezaba a elegir voicings raros con tal de cobrarla.':
        'The reason is that the cost rewards minimum motion, and an ornament '
        'always adds motion. Inside the fitness function, an ornament could only '
        'win if it were paid for with a reward, and that reward distorted '
        'everything else: the search would start choosing strange voicings just '
        'to collect it.',
    'El motivo es que la armonía se escucha como acercamiento y no como partida. Lo que te dice que acá va un dominante no es lo que pasó antes: es que lo que viene después es un punto de reposo. Y esa información, yendo hacia adelante, todavía no existe.':
        'The reason is that harmony is heard as an approach and not as a '
        'departure. What tells you a dominant goes here is not what came before: '
        'it is that what comes after is a resting point. And going forwards, that '
        'information does not exist yet.',
    'El motor no usa ninguna librería externa: es Python estándar puro. El MusicXML, el MIDI y el audio que escuchás con el botón «Escuchar» están escritos byte a byte por el programa.':
        'The engine uses no external library: it is plain standard Python. The '
        'MusicXML, the MIDI and the audio you hear from the “Play” button are '
        'written byte by byte by the program.',
    'El oficio': 'The craft',
    'El organum': 'Organum',
    'El organum y la vox principalis': 'Organum and the vox principalis',
    'El pentagrama': 'The staff',
    'El precio': 'The price',
    'El primer paso hacia varias voces fue mecánico. Alguien cantaba la melodía y otro la doblaba, nota por nota, una cuarta o una quinta por debajo. Eso es el organum paralelo, y está documentado en el siglo IX. No hay independencia: la segunda voz es una sombra de la primera.':
        'The first step toward several voices was mechanical. Somebody sang the '
        'melody and somebody else doubled it, note for note, a fourth or a fifth '
        'below. That is parallel organum, and it is documented in the ninth '
        'century. There is no independence: the second voice is a shadow of the '
        'first.',
    'El programa arranca con una población de doscientos cromosomas al azar. A cada uno le calcula un costo —cuánto se mueven las voces, cuántas reglas rompe— y después arma la generación siguiente: los mejores pasan intactos (elitismo), el resto sale de cruzar pares de padres elegidos por torneo, y una fracción de los genes muta al azar para que la búsqueda no se estanque.':
        'The program starts with a population of two hundred random chromosomes. '
        'It works out a cost for each one — how much the voices move, how many '
        'rules it breaks — and then builds the next generation: the best pass '
        'through untouched (elitism), the rest come from crossing pairs of '
        'parents chosen by tournament, and a fraction of the genes mutate at '
        'random so the search does not get stuck.',
    'El programa cuenta cuánto movimiento contrario hay y lo premia. No es un capricho estético: es lo que hace que cuatro voces suenen como cuatro personas y no como un acordeón.':
        'The program counts how much contrary motion there is and rewards it. It '
        'is not an aesthetic whim: it is what makes four voices sound like four '
        'people and not like an accordion.',
    'El programa la trata como una cita: no la construye gradualmente sino que la pone entera, tal cual, cuando se dan las condiciones.':
        'The program treats it as a quotation: it does not build it up gradually '
        'but drops it in whole, exactly as it is, when the conditions are right.',
    'El programa las conecta por grado conjunto de un acorde al siguiente, mantiene las notas que dos acordes comparten y evita las novenas menores, que es el único choque que el estilo no perdona. Las paralelas y los tritonos, en cambio, pasan sin problema.':
        'The program connects them by step from one chord to the next, keeps the '
        'notes two chords share and avoids minor ninths, which is the one clash '
        'the style does not forgive. Parallels and tritones, on the other hand, '
        'go through without trouble.',
    'El programa las ofrece sólo cuando le pediste color, y siempre por detrás de las tres primeras: una melodía armonizada entera con novenas deja de tener puntos de reposo. El orden dentro del grupo es sexta, séptima, novena, de la más suave a la más picante.':
        'The program only offers them when you have asked for color, and always '
        'behind the first three: a melody harmonized entirely with ninths stops '
        'having any resting points. The order within the group is sixth, seventh, '
        'ninth, from the gentlest to the sharpest.',
    'El programa lo llama «intercambio modal» y lo tenés como casilla en el Armonizador y como dial en el Generador.':
        'The program calls it “modal interchange” and you have it as a checkbox '
        'in the Harmonizer and as a dial in the Generator.',
    'El programa lo trata como una excepción con nombre propio: en ese lugar exige el quinto grado, que es el acorde del que la sensible es la tercera. Y si en ese punto no caía ningún acorde, le abre uno propio partiendo el que la cubría.':
        'The program treats it as an exception with a name of its own: at that '
        'spot it requires the fifth degree, which is the chord the leading tone '
        'is the third of. And if no chord landed at that point, it opens one for '
        'it by splitting the chord that covered it.',
    'El programa no las armoniza, y ésa es la mitad del oficio. Ponerle un acorde a cada nota es el error clásico de quien recién empieza: sale una progresión que cambia demasiado rápido y en la que ninguna nota suena de paso porque todas son estructurales.':
        'The program does not harmonize them, and that is half the craft. Putting '
        'a chord under every note is the classic beginner’s mistake: you get a '
        'progression that changes too fast and in which no note sounds like a '
        'passing note because they are all structural.',
    'El programa recorre la melodía **desde el final hacia el principio**. Suena raro y es la decisión más importante de todo el modo.':
        'The program walks the melody **from the end to the beginning**. It '
        'sounds odd and it is the most important decision in the whole mode.',
    'El préstamo más común es el cuarto grado menor: en do mayor, usar Fm en lugar de F. Es un acorde que suena inmediatamente melancólico y aparece en muchísima música popular justo antes del final. Otro es el séptimo rebajado (bVII), que suena a rock antes que a clásico.':
        'The most common borrowing is the minor fourth degree: in C major, using '
        'Fm instead of F. It is a chord that sounds immediately melancholy and '
        'turns up in a great deal of popular music right before the end. Another '
        'is the flat seventh (bVII), which sounds like rock rather than like '
        'classical.',
    'El que lo escribió': 'The one who wrote it',
    'El recorrido típico es ese: casa → salgo → tensión → vuelvo. I - IV - V - I, o con más vuelta, I - vi - ii - V - I. Si escuchás cualquier canción popular vas a encontrar ese esqueleto abajo de casi todo.':
        'The typical journey is that one: home → I leave → tension → I come back. '
        'I - IV - V - I, or with more of a detour, I - vi - ii - V - I. If you '
        'listen to any popular song you will find that skeleton under almost '
        'everything.',
    'El signo del principio es la clave, y es lo que decide qué nota es cada línea. La clave de sol —la que se ve en el dibujo, y la que usa el pentagrama del Armonizador— pone el sol en la segunda línea desde abajo. De ahí sale todo lo demás: la línea de abajo es mi, el primer espacio fa, y así hacia arriba.':
        'The sign at the start is the clef, and it is what decides which note '
        'each line is. The treble clef — the one in the drawing, and the one the '
        'Harmonizer’s staff uses — puts G on the second line from the bottom. '
        'Everything else follows: the bottom line is E, the first space F, and so '
        'on upward.',
    'El séptimo es el caso serio. Cae treinta y una centésimas por debajo de la séptima menor del piano: casi un tercio de semitono. No hay ninguna tecla ahí. Es la nota del blues, la que un guitarrista consigue estirando la cuerda y un pianista no consigue nunca —de ahí que en el piano el blues se toque haciendo sonar dos teclas vecinas, que es una manera de señalar un lugar al que no se llega.':
        'The seventh is the serious case. It falls thirty-one hundredths below '
        'the piano’s minor seventh: almost a third of a semitone. There is no key '
        'there. It is the note of the blues, the one a guitarist gets by bending '
        'the string and a pianist never gets at all — hence the blues on piano '
        'being played by sounding two neighbouring keys, which is a way of '
        'pointing at a place you cannot reach.',
    'El tercer armónico —la quinta— cae dos centésimas de semitono por encima de la quinta del piano. Dos centésimas no las oye nadie. El quinto armónico —la tercera mayor— cae **catorce** por debajo, y ésas sí: un acorde afinado a oído por un coro no es el mismo acorde que sale de un teclado, y quien canta en un coro lo sabe aunque no sepa por qué.':
        'The third harmonic — the fifth — falls two hundredths of a semitone '
        'above the piano’s fifth. Nobody hears two hundredths. The fifth harmonic '
        '— the major third — falls **fourteen** below, and those you do hear: a '
        'chord tuned by ear by a choir is not the same chord that comes out of a '
        'keyboard, and anyone who sings in a choir knows it even without knowing '
        'why.',
    'El tritono se ganó en esta época el apodo de «diabolus in musica». No era superstición: en un lenguaje sin dominantes ni resoluciones, un intervalo tan inestable no tiene adónde ir, y simplemente suena mal. Cuando la tonalidad le dio un destino, dejó de ser un problema y pasó a ser el motor.':
        'The tritone earned its nickname “diabolus in musica” in this period. It '
        'was not superstition: in a language with no dominants and no '
        'resolutions, an interval that unstable has nowhere to go, and it simply '
        'sounds bad. When tonality gave it a destination, it stopped being a '
        'problem and became the engine.',
    'El truco de retrasar. Antes del V de verdad, se pone el mismo acorde pero con la quinta en el bajo. El oído escucha el bajo de la dominante y espera la resolución, pero arriba todavía están las notas de la tónica: la tensión se estira un tiempo más y después resuelve.':
        'The trick of delaying. Before the real V, you put the same chord but '
        'with the fifth in the bass. The ear hears the dominant’s bass and '
        'expects the resolution, but up above the tonic’s notes are still there: '
        'the tension stretches out one beat longer and then resolves.',
    'El truco que usa el programa es el mismo que usaría una persona: cuando dos voces amenazan con caer en paralelo, mover una de las dos en dirección contraria, o dejarla quieta si el acorde siguiente comparte esa nota. La diferencia es que el algoritmo puede probar miles de repartos por segundo y quedarse con el que menos cuesta.':
        'The trick the program uses is the same one a person would use: when two '
        'voices threaten to fall into parallel, move one of them in the opposite '
        'direction, or leave it where it is if the next chord shares that note. '
        'The difference is that the algorithm can try thousands of layouts a '
        'second and keep the one that costs least.',
    'El undécimo ya no cae cerca de nada: queda justo en el medio entre la cuarta y el tritono. Las trompas naturales, que no tenían llaves y sólo podían tocar la serie, lo tenían, y sonaba raro a propósito.':
        'The eleventh no longer falls near anything: it sits right between the '
        'fourth and the tritone. Natural horns, which had no valves and could '
        'only play the series, had it, and it sounded odd on purpose.',
    'El vii° cumple la misma función que el V y suele reemplazarlo o precederlo. En el jazz aparece además el medio disminuido (m7b5), que es el ii de las tonalidades menores: el «F#m7b5» que aparece a veces en los resultados es exactamente eso.':
        'The vii° serves the same function as the V and usually replaces or '
        'precedes it. In jazz the half-diminished (m7b5) also turns up, which is '
        'the ii of minor keys: the “F#m7b5” that sometimes appears in the results '
        'is exactly that.',
    'El «Modo coral» está en la pantalla de reglas, abajo a la derecha, y sólo aparece con el estilo Barroco elegido.':
        '“Chorale mode” is on the rules screen, bottom right, and only appears '
        'with the Baroque style chosen.',
    'En do mayor es G - C. Si le agregás la séptima al G, el efecto es más fuerte todavía: el G7 tiene adentro un tritono que sólo se resuelve de una manera.':
        'In C major it is G - C. If you add the seventh to the G the effect is '
        'stronger still: the G7 has a tritone inside it that resolves in only one '
        'way.',
    'En el Generador, antes de repartir voces hay que decidir qué acordes van. El programa arma para cada lugar la lista de acordes posibles en la tonalidad —los siete grados, más los préstamos y las dominantes secundarias que hayas habilitado— y le pone un peso a cada uno según su función y según cuál vino antes.':
        'In the Generator, before laying out voices you have to decide which '
        'chords go where. For each spot the program builds the list of chords '
        'possible in the key — the seven degrees, plus whatever borrowings and '
        'secondary dominants you have enabled — and gives each one a weight '
        'according to its function and to which one came before.',
    'En el engranaje, abajo de la configuración del algoritmo, dice cuántos núcleos tiene tu máquina y cuántos procesos va a usar la búsqueda. Siempre deja uno libre para que la ventana siga respondiendo mientras busca.':
        'Under the gear, below the algorithm settings, it says how many cores '
        'your machine has and how many processes the search will use. It always '
        'leaves one free so the window keeps responding while it searches.',
    'En el experimentador, el menú «Forma de onda» cambia todas las alturas de golpe y deja lo demás como estaba. Escuchá la misma nota como seno, como cuadrada y como diente de sierra.':
        'In the workbench, the “Waveform” menu changes all the heights at once '
        'and leaves everything else as it was. Listen to the same note as a sine, '
        'as a square and as a sawtooth.',
    'En el menor natural esto no se hace, y no por gusto: ese modo tiene el séptimo grado rebajado, así que no hay sensible, y el acorde que se forzaría no contiene la nota que vino a sostener.':
        'In the natural minor this is not done, and not by choice: that mode has '
        'a lowered seventh degree, so there is no leading tone, and the chord '
        'that would be forced does not contain the note it came to support.',
    'En el organum medieval hay una voz que lleva el canto —la vox principalis— y otra que la acompaña doblándola en paralelo a la cuarta, la quinta o la octava: la vox organalis.':
        'In medieval organum there is a voice that carries the chant — the vox '
        'principalis — and another that accompanies it by doubling it in parallel '
        'at the fourth, the fifth or the octave: the vox organalis.',
    'En este programa eso se controla con el dial «Cuánto color». Abajo del todo, el programa duplica notas del acorde cuando le sobran voces. A medida que subís, en vez de duplicar prefiere agregar una sexta, y más arriba también novenas y oncenas.':
        'In this program that is controlled with the “How much color” dial. At '
        'the very bottom, the program doubles chord tones when it has voices to '
        'spare. As you turn it up, instead of doubling it prefers to add a sixth, '
        'and higher up ninths and elevenths as well.',
    'En este programa marcás cuál es la principalis en la pantalla de voces, y la voz que quede inmediatamente debajo se convierte en la organalis. No puede ser la voz más grave, justamente porque necesita a alguien debajo para acompañarla.':
        'In this program you mark which one is the principalis on the voices '
        'screen, and whichever voice sits immediately below becomes the '
        'organalis. It cannot be the lowest voice, precisely because it needs '
        'somebody underneath to accompany it.',
    'En jazz esto se da vuelta. Que la melodía caiga en la fundamental es lo plano y caer en la novena o en la trece es lo normal, así que el estilo mueve el balance sin cambiar ninguna de las reglas.':
        'In jazz this is turned around. The melody landing on the root is the '
        'flat option and landing on the ninth or the thirteenth is the norm, so '
        'the style shifts the balance without changing any of the rules.',
    'En jazz se agrega el séptimo grado a los permitidos. Es el mismo tritono sin la fundamental —un Bm7♭5 sobre un si es lo que ese idioma escribe donde el coral escribe un sol—, y por eso vale ahí y no en los otros estilos.':
        'In jazz the seventh degree is added to the permitted ones. It is the '
        'same tritone without the root — a Bm7♭5 over a B is what that language '
        'writes where the chorale writes a G — and that is why it counts there '
        'and not in the other styles.',
    'En la práctica común eso era un error. Un tratado del mil ochocientos te lo hubiera marcado en rojo. En el blues es la definición del género: nada resuelve del todo, nunca, y esa insatisfacción permanente es exactamente lo que la música quiere decir.':
        'In common practice that was a mistake. An 1800s treatise would have '
        'marked it in red. In the blues it is the definition of the genre: '
        'nothing ever fully resolves, and that permanent dissatisfaction is '
        'exactly what the music means to say.',
    'En los años treinta el swing lo vuelve música de baile y de orquesta grande. En los cuarenta, el bebop lo da vuelta: tempos imposibles, melodías de una densidad nueva, y sobre todo una armonía mucho más rica. Charlie Parker y Dizzy Gillespie empiezan a apilar novenas y oncenas sobre los acordes, y a reemplazar dominantes por otros a distancia de tritono.':
        'In the thirties swing turns it into dance music for big bands. In the '
        'forties, bebop turns it upside down: impossible tempos, melodies of a '
        'new density, and above all a much richer harmony. Charlie Parker and '
        'Dizzy Gillespie start stacking ninths and elevenths on the chords, and '
        'replacing dominants with others a tritone away.',
    'En qué intervalo suele caer la nota':
        'Which interval the note usually lands on',
    'Entre 1600 y 1750 la música de occidente se ordena alrededor de una idea nueva: la tonalidad. Ya no hay ocho modos equivalentes, hay mayor y menor, y adentro de cada uno los acordes tienen jerarquía. Uno es la casa, otro es la tensión, y la música es el viaje entre los dos.':
        'Between 1600 and 1750 Western music arranges itself around a new idea: '
        'tonality. There are no longer eight equivalent modes, there is major and '
        'minor, and inside each one the chords have a hierarchy. One is home, '
        'another is tension, and the music is the journey between the two.',
    'Entre dos notas del acorde suele haber notas que no lo son. Sirven para llegar de una a la otra: se pasa por ellas y no se descansa ahí.':
        'Between two chord tones there are usually notes that are not chord '
        'tones. They serve to get from one to the other: you pass through them '
        'and do not rest there.',
    'Entre dos notas vecinas hay un semitono, que es la distancia más chica que usa esta música: de una tecla del piano a la de al lado, contando las negras. Dos semitonos son un tono.':
        'Between two neighbouring notes there is a semitone, which is the '
        'smallest distance this music uses: from one piano key to the next one '
        'over, counting the black ones. Two semitones make a whole tone.',
    'Entre la cuerda y el oído hay un rato, y en ese rato pasan cosas que la música aprendió a usar.':
        'Between the string and the ear there is a moment, and in that moment '
        'things happen that music has learned to use.',
    'Es el acorde más oscuro del catálogo y el que más rápido cansa si se abusa. Sirve para pasar, no para quedarse.':
        'It is the darkest chord in the catalogue and the one that tires fastest '
        'if overused. It is for passing through, not for staying.',
    'Es el contrapunto de la práctica común: el lenguaje de Bach, Haendel y todo lo que vino después hasta bien entrado el siglo XIX. Es el más reglado de los tres.':
        'It is common practice counterpoint: the language of Bach, Handel and '
        'everything that came after, well into the nineteenth century. It is the '
        'most rule-bound of the three.',
    'Es el final del sendero, y es la única pieza de este libro que no hace falta explicar para que se entienda.':
        'It is the end of the road, and it is the only piece in this book that '
        'needs no explaining to be understood.',
    'Es el lamento barroco por excelencia —el bajo de la «Dido» de Purcell, el «Crucifixus» de Bach— y sobrevivió intacto hasta el jazz y el rock. Si alguna vez escuchaste una balada donde el bajo baja de a un semitono mientras el acorde parece el mismo, era esto.':
        'It is the baroque lament par excellence — the bass of Purcell’s “Dido”, '
        'Bach’s “Crucifixus” — and it survived intact into jazz and rock. If you '
        'have ever heard a ballad where the bass drops a semitone at a time while '
        'the chord seems to stay the same, that was this.',
    'Es el mismo intervalo que el capítulo de contrapunto llama tritono y que el canto llano tenía prohibido: *diabolus in musica*, el diablo en la música. Mil años más tarde, la misma nota que la Iglesia había desterrado se volvió el centro de todo un género. Nadie hizo ese chiste a propósito.':
        'It is the same interval the counterpoint chapter calls a tritone and '
        'that plainchant forbade: *diabolus in musica*, the devil in music. A '
        'thousand years later, the very note the Church had banished became the '
        'centre of a whole genre. Nobody made that joke on purpose.',
    'Es el mismo principio del ciclo de Vivaldi, pero suelto, sin la forma fija de la cita.':
        'It is the same principle as the Vivaldi cycle, but loose, without the '
        'fixed shape of the quotation.',
    'Es el motor de medio barroco italiano y de una cantidad absurda de música posterior. La sensación es de caída continua, como una escalera que no termina.':
        'It is the engine of half the Italian baroque and of an absurd amount of '
        'later music. The feeling is of a continuous fall, like a staircase that '
        'does not end.',
    'Es la forma más repetida de la historia de la música popular. No es una canción: es un recipiente. Adentro entra cualquier cosa, y lo que cambia entre una versión y otra es todo menos el esqueleto.':
        'It is the most repeated form in the history of popular music. It is not '
        'a song: it is a container. Anything fits inside it, and what changes '
        'between one version and another is everything except the skeleton.',
    'Es la fórmula con la que se anuncian casi todos los finales grandes del repertorio clásico, y la que usa un concierto para avisar que viene la cadenza del solista.':
        'It is the formula that announces almost every big ending in the '
        'classical repertoire, and the one a concerto uses to signal that the '
        'soloist’s cadenza is coming.',
    'Es la quinta disminuida: la nota que queda justo en el medio de la octava, a seis semitonos de la tónica. En la menor es el mi bemol.':
        'It is the diminished fifth: the note that sits exactly in the middle of '
        'the octave, six semitones from the tonic. In A minor it is E flat.',
    'Es la única visita que sabe que esto es un programa, y por eso es la única que puede contar las dos mitades del mismo asunto sin cambiar de tema. Lo que sigue es lo que quedó anotado.':
        'It is the only visitor who knows this is a program, and that is why it '
        'is the only one who can tell both halves of the same business without '
        'changing the subject. What follows is what was written down.',
    'Es lo que hace que una melodía de ocho compases se sienta como pregunta y respuesta.':
        'It is what makes an eight-bar melody feel like question and answer.',
    'Es también la razón por la que cambiar la última nota de tu melodía cambia acordes que están cuatro compases antes. No es un error: es que ahí empieza la cuenta.':
        'It is also the reason why changing the last note of your melody changes '
        'chords four bars earlier. It is not a bug: it is that the reckoning '
        'starts there.',
    'Es un buen ejemplo de que las reglas del contrapunto no son una jaula: son un problema, y la historia de la música está llena de maneras elegantes de resolverlo.':
        'It is a good example of the rules of counterpoint not being a cage: they '
        'are a problem, and the history of music is full of elegant ways of '
        'solving it.',
    'Es un recurso de continuidad: sirve para alargar una sección cuando ya estaba por cerrar. En la pantalla de resultados aparece marcada como «Cadencia rota».':
        'It is a device for continuity: it serves to stretch a section out when '
        'it was about to close. On the results screen it appears marked as '
        '“Deceptive cadence”.',
    'Es un recurso que Bach usa constantemente. El acorde pasa a llamarse «6omit5» —sexta con la quinta omitida— y en la pantalla de resultados aparece marcado.':
        'It is a device Bach uses constantly. The chord comes to be called '
        '“6omit5” — sixth with the fifth omitted — and it appears marked on the '
        'results screen.',
    'Escritura modal, anterior a la tonalidad. No hay acordes de séptima, no hay dominantes tirando hacia la tónica: hay líneas que se mueven casi siempre por grado conjunto, de una nota a la de al lado.':
        'Modal writing, older than tonality. There are no seventh chords, no '
        'dominants pulling toward the tonic: there are lines that almost always '
        'move by step, from one note to the next one over.',
    'Ese orden es deliberado y es el que decide todos los empates: **dónde cae la nota de la melodía importa más que cualquier otra cosa**. Un encadenamiento que se lee precioso en el papel, con la nota escrita afuera del acorde, no sirve para nada: nadie escucha una progresión, se escucha una melodía con algo abajo.':
        'That order is deliberate and it is what settles every tie: **where the '
        'melody note lands matters more than anything else**. A chain of chords '
        'that reads beautifully on paper, with the written note outside the '
        'chord, is worth nothing: nobody hears a progression, you hear a melody '
        'with something underneath it.',
    'Eso es el timbre, y no es nada más que eso: la receta de alturas de la serie. Una flauta es casi pura fundamental, con los armónicos apenas insinuados, y por eso suena redonda y sin filo. Un clarinete es un tubo tapado y refuerza los impares dejando los pares casi mudos, y ese hueco es lo que se oye como «sonido de clarinete». Un violín los tiene todos y por eso corta.':
        'That is timbre, and it is nothing more than that: the recipe of heights '
        'in the series. A flute is almost pure fundamental, with the harmonics '
        'barely hinted at, and that is why it sounds round and without an edge. A '
        'clarinet is a stopped pipe and reinforces the odd ones while leaving the '
        'even ones almost mute, and that gap is what you hear as “clarinet '
        'sound”. A violin has them all and that is why it cuts.',
    'Eso es la serie armónica. Lo que llamamos «la nota» es el primero de la lista, y casi nunca es el más fuerte: lo que hace que oigamos una sola nota y no doce es que el oído agrupa lo que está en relación entera y lo escucha como una cosa sola.':
        'That is the harmonic series. What we call “the note” is the first on the '
        'list, and it is almost never the loudest: what makes us hear one note '
        'and not twelve is that the ear groups whatever is in whole-number '
        'relation and hears it as a single thing.',
    'Eso es una nota de paso, y es el adorno más elemental que existe. No cambia la armonía: es puro tránsito, y por eso el programa las agrega después de la búsqueda y no durante.':
        'That is a passing note, and it is the most elementary ornament there is. '
        'It does not change the harmony: it is pure transit, and that is why the '
        'program adds them after the search and not during it.',
    'Estilo Gregoriano + Organizador o Generador · pantalla de Voces · el botón «vox principalis» de cada voz.':
        'Gregorian style + Organizer or Generator · Voices screen · the “vox '
        'principalis” button on each voice.',
    'Estilo Gregoriano: es su cadencia natural y aparece sola. El Generador con Gregoriano las produce en casi todas las corridas.':
        'Gregorian style: it is its natural cadence and it turns up on its own. '
        'The Generator with Gregorian produces them on almost every run.',
    'Estilo Jazz + Generador. Aparece cuando el programa elige un subV en lugar del V.':
        'Jazz style + Generator. It turns up when the program picks a subV '
        'instead of the V.',
    'Estilo Jazz + Generador. Con cuatro compases o más aparece en casi todas las corridas.':
        'Jazz style + Generator. With four measures or more it turns up on almost '
        'every run.',
    'Esto no lo contó nadie. Apareció una noche, parado en el medio de un camino de tierra, y no dijo una sola palabra: se quedó mirando, se dio vuelta y se fue. Lo que sigue es la historia que se cuenta de él, que es lo primero que aparece cuando uno va a buscar quién era.':
        'Nobody told this one. He appeared one night, standing in the middle of a '
        'dirt road, and did not say a single word: he stood looking, turned round '
        'and left. What follows is the story people tell about him, which is the '
        'first thing that comes up when you go looking for who he was.',
    'Evaluar un cromosoma es contar semitonos: restas, restos de doce y comparaciones. Cada una cuesta poquísimo, pero una corrida corriente hace **sesenta mil** evaluaciones y cada una recorre todos los acordes y todos los pares de voces. Son decenas de millones de operaciones diminutas, y ahí Python —que revisa el tipo de cada número antes de sumarlo— trabaja mucho más de lo que la cuenta necesita.':
        'Evaluating a chromosome is counting semitones: subtractions, remainders '
        'of twelve and comparisons. Each one costs next to nothing, but an '
        'ordinary run does **sixty thousand** evaluations and each one walks '
        'every chord and every pair of voices. That is tens of millions of tiny '
        'operations, and there Python — which checks the type of every number '
        'before adding it — does far more work than the arithmetic needs.',
    'Evita el tritono con una insistencia que a los medievales les valió el apodo de «diabolus in musica»: ni saltado por una voz ni sonando entre dos. En cambio tolera las quintas y octavas paralelas, porque el organum —la forma más antigua de cantar a varias voces— consiste literalmente en doblar la melodía en paralelo.':
        'It avoids the tritone with an insistence that earned the medievals the '
        'nickname “diabolus in musica”: neither leapt by one voice nor sounding '
        'between two. It does, on the other hand, tolerate parallel fifths and '
        'octaves, because organum — the oldest way of singing in several voices — '
        'consists literally of doubling the melody in parallel.',
    'Funciona tan bien porque las guide tones se mueven mínimo: la séptima de un acorde se vuelve la tercera del siguiente, y la tercera se vuelve la séptima. Dos notas alcanzan para llevar toda la progresión, y las voces casi no se mueven.':
        'It works so well because the guide tones barely move: the seventh of one '
        'chord becomes the third of the next, and the third becomes the seventh. '
        'Two notes are enough to carry the whole progression, and the voices '
        'hardly move at all.',
    'Generador · estilo Barroco (o Modo coral) · tonalidad MENOR · exactamente 2 compases en 4/4, que dan los 4 acordes que la cadencia necesita. Aparece el 10% de las veces; con «Elevar probabilidad de cadencias especiales» en el engranaje de configuración, el 45%.':
        'Generator · Baroque style (or Chorale mode) · MINOR key · exactly 2 '
        'measures in 4/4, which give the 4 chords the cadence needs. It turns up '
        '10% of the time; with “Raise the odds of special cadences” under the '
        'settings gear, 45%.',
    'Generador · estilo Barroco (o Modo coral) · tonalidad MENOR · exactamente 4 compases en 4/4, que dan los 8 acordes. Mismas probabilidades que la frigia.':
        'Generator · Baroque style (or Chorale mode) · MINOR key · exactly 4 '
        'measures in 4/4, which give the 8 chords. Same odds as the phrygian.',
    'Generador · estilo Barroco o Jazz · tonalidad MENOR · exactamente 3 compases en 4/4, que dan los 6 acordes. No aparece en Modo coral.':
        'Generator · Baroque or Jazz style · MINOR key · exactly 3 measures in '
        '4/4, which give the 6 chords. It does not turn up in Chorale mode.',
    'Generador · pantalla de Tonalidad · activá la modulación y usá al menos ocho compases. Con pocos compases no entra, por más que esté activada.':
        'Generator · Key screen · switch on modulation and use at least eight '
        'measures. With few measures it does not fit, however switched on it is.',
    'Generador · pantalla de Tonalidad · el menú de modo, al lado de la tónica.':
        'Generator · Key screen · the mode menu, next to the tonic.',
    'Generador · pantalla de Tonalidad · en «Termina en» escribí V y ponelo en Obligatorio.':
        'Generator · Key screen · in “Ends on” write V and set it to Required.',
    'Generador · pantalla de Tonalidad · sección «Notas de paso», elegí qué voces pueden usarlas. En el Organizador es la casilla «Agregar notas de adorno».':
        'Generator · Key screen · “Passing notes” section, choose which voices may '
        'use them. In the Organizer it is the “Add ornamental notes” checkbox.',
    'Generador · pantalla de Tonalidad · subí «acordes prestados». En el Armonizador es la casilla «Permitir intercambios modales».':
        'Generator · Key screen · turn up “borrowed chords”. In the Harmonizer it '
        'is the “Allow modal interchange” checkbox.',
    'Hacia atrás sí. Cuando le toca decidir el anteúltimo acorde, el último ya está puesto, así que puede preguntarse si conviene prepararlo. Un dominante parado justo antes de un reposo es lo que más premia el programa en todo este modo.':
        'Backwards it does. When it comes to decide the second-to-last chord, the '
        'last one is already in place, so it can ask itself whether preparing it '
        'is worthwhile. A dominant standing right before a resting point is what '
        'this program rewards most in the whole mode.',
    'Hay cosas que no se consiguen. Se te aparecen.':
        'Some things are not earned. They appear to you.',
    'Hay dos excepciones, y las dos son tuyas. Podés marcar una nota para pedir un acorde justo ahí aunque no caiga en tiempo fuerte, y podés apagar uno que el programa puso. Cuando sacás uno, el tiempo que ocupaba se lo queda un acorde vecino **del mismo compás**: el compás tiene que seguir sumando lo que dice su cifra.':
        'There are two exceptions, and both are yours. You can mark a note to ask '
        'for a chord right there even if it does not fall on a strong beat, and '
        'you can turn off one the program put in. When you take one out, the time '
        'it occupied is taken over by a neighbouring chord **in the same '
        'measure**: the measure has to go on adding up to its time signature.',
    'Hay intervalos que suenan estables y redondos —la octava, la quinta, la tercera, la sexta— y otros que suenan tensos y piden movimiento —la segunda, la séptima, y sobre todo el tritono, que son tres tonos justos, de fa a si. Casi todas las reglas de este programa se reducen a administrar esa tensión: dónde se permite, cuánto dura y hacia dónde resuelve.':
        'There are intervals that sound stable and round — the octave, the fifth, '
        'the third, the sixth — and others that sound tense and ask for movement '
        '— the second, the seventh, and above all the tritone, which is exactly '
        'three whole tones, from F to B. Almost every rule in this program comes '
        'down to managing that tension: where it is allowed, how long it lasts '
        'and where it resolves to.',
    'Hay un caso que sí mira aparte. Cuando la nota que cae en el tiempo fuerte entra mucho peor en los acordes disponibles que la que viene enseguida después, el programa toma **la siguiente** como la nota que hay que sostener. Es lo que pasa con un retardo: la nota del tiempo llega tarde a su acorde y recién resuelve un momento después, así que el acorde es de la resolución y no del retardo.':
        'There is one case it does look at separately. When the note falling on '
        'the strong beat fits the available chords far worse than the one that '
        'comes immediately after, the program takes **the next one** as the note '
        'to be supported. That is what happens with a suspension: the note on the '
        'beat arrives at its chord late and only resolves a moment later, so the '
        'chord belongs to the resolution and not to the suspension.',
    'Hay un motivo para no ponerlo al máximo siempre: si todos los acordes llevan color, el color deja de escucharse. Funciona por contraste.':
        'There is a reason not to put it at maximum all the time: if every chord '
        'carries color, the color stops being heard. It works by contrast.',
    'Igual se la usó, y por una razón entendible. Hugo Riemann, a fines del siglo XIX, quiso explicar el acorde menor: el mayor sale solito de los armónicos 4, 5 y 6, que dan la fundamental, la tercera mayor y la quinta. El menor no sale de ninguna parte. Riemann propuso que era la serie subarmónica leída al revés, y con eso el menor quedaba tan natural como el mayor.':
        'It was used anyway, and for an understandable reason. Hugo Riemann, at '
        'the end of the nineteenth century, wanted to explain the minor chord: '
        'the major one falls out by itself from harmonics 4, 5 and 6, which give '
        'the root, the major third and the fifth. The minor comes from nowhere. '
        'Riemann proposed it was the subharmonic series read backwards, and with '
        'that the minor came out as natural as the major.',
    'Ingeniería': 'Engineering',
    'La cadencia auténtica: V - I': 'The authentic cadence: V - I',
    'La cadencia característica no es V-I sino la plagal, IV-I: el «amén» de los himnos.':
        'The characteristic cadence is not V-I but the plagal, IV-I: the “amen” '
        'of the hymns.',
    'La cadencia del pacto': 'The cadence of the bargain',
    'La clave de sol y las notas de las cinco líneas y los cuatro espacios. La primera, con su línea adicional, es el do central.':
        'The treble clef and the notes of the five lines and four spaces. The '
        'first, with its ledger line, is middle C.',
    'La distancia entre dos notas. Se cuenta en nombres, no en semitonos: de do a mi hay una tercera (do, re, mi: tres nombres), de do a sol una quinta, de do a do una octava.':
        'The distance between two notes. It is counted in names, not in '
        'semitones: from C to E is a third (C, D, E: three names), from C to G a '
        'fifth, from C to C an octave.',
    'La escala y los grados': 'The scale and the degrees',
    'La escribió John Newton en 1772. Newton había sido capitán de un barco negrero. La letra es lo que escribió cuando entendió lo que había hecho: *salvó a un desgraciado como yo*.':
        'It was written by John Newton in 1772. Newton had been the captain of a '
        'slave ship. The words are what he wrote when he understood what he had '
        'done: *saved a wretch like me*.',
    'La excepción es la séptima que le pertenece al acorde de verdad —la de un G7, la de un Dm7—. Ésa no es color: es una nota del acorde, y ahí la melodía puede pararse tengas o no el color prendido.':
        'The exception is the seventh that genuinely belongs to the chord — the '
        'one in a G7, the one in a Dm7. That is not color: it is a chord tone, '
        'and the melody may rest on it whether or not you have color switched on.',
    'La física en la música': 'Physics in music',
    'La idea es imitar la selección natural. Cada solución candidata es un «cromosoma»: una lista que dice, para cada acorde, cuál de sus repartos posibles se usó.':
        'The idea is to imitate natural selection. Each candidate solution is a '
        '“chromosome”: a list saying, for each chord, which of its possible '
        'layouts was used.',
    'La idea se llama dualismo armónico, tuvo cien años de discusión y hoy nadie la sostiene como física: el menor no está en la naturaleza de la misma manera que el mayor, y probablemente sea una construcción cultural, que no lo hace peor.':
        'The idea is called harmonic dualism, it was argued over for a hundred '
        'years and today nobody holds it as physics: the minor is not in nature '
        'the way the major is, and it is probably a cultural construction, which '
        'does not make it any worse.',
    'La lápida': 'The headstone',
    'La melodía que se canta hoy no es la suya: es una tonada popular llamada «New Britain», que alguien le acopló en 1835 en Estados Unidos. La canción tal como existe es un accidente entre un texto y una melodía que nunca se conocieron.':
        'The melody sung today is not his: it is a folk tune called “New '
        'Britain”, which somebody grafted onto it in 1835 in the United States. '
        'The song as it exists is an accident between a text and a melody that '
        'never met.',
    'La misma noche otra vez, un minuto más tarde. Esta vez, delante de él y de espaldas, había una silueta con sombrero que antes no estaba: negra entera, sin una sola cara. Y esta vez alguien habló. Tres palabras.':
        'The same night again, a minute later. This time, in front of him and '
        'with its back turned, there was a silhouette in a hat that had not been '
        'there before: entirely black, with no face at all. And this time '
        'somebody spoke. Three words.',
    'La misma nota admite muchas respuestas, y todas correctas. Un do puede ser la fundamental de do mayor, la tercera de la menor, la quinta de fa mayor, la séptima de re menor séptima. Las cuatro suenan bien y las cuatro dicen cosas distintas: el do se queda quieto y abajo cambia el sentido de la frase.':
        'The same note admits many answers, and all of them are right. A C can be '
        'the root of C major, the third of A minor, the fifth of F major, the '
        'seventh of D minor seventh. All four sound good and all four say '
        'different things: the C stays where it is and underneath it the sense of '
        'the phrase changes.',
    'La misma subida con la voz de arriba yendo al revés: el intervalo cambia y el problema desaparece.':
        'The same rise with the upper voice going the other way: the interval '
        'changes and the problem disappears.',
    'La mitad vibra al doble de velocidad, así que suena al doble de frecuencia. El tercio, al triple. El cuarto, al cuádruple. De ahí sale la lista: si la cuerda entera da 110 hercios, arriba de ella hay 220, 330, 440, 550, 660, y sigue. Son los múltiplos enteros, sin excepción y sin hueco.':
        'The half vibrates twice as fast, so it sounds at twice the frequency. '
        'The third, three times. The quarter, four times. That is where the list '
        'comes from: if the whole string gives 110 hertz, above it there are 220, '
        '330, 440, 550, 660, and on it goes. They are the whole-number multiples, '
        'without exception and without a gap.',
    'La más común de todas y la que define la tonalidad. El quinto grado contiene la sensible, esa nota a un semitono de la tónica, y cuando resuelve el oído siente que la frase cerró.':
        'The most common of all and the one that defines the key. The fifth '
        'degree contains the leading tone, that note a semitone from the tonic, '
        'and when it resolves the ear feels the phrase has closed.',
    'La música de los reprimidos': 'The music of the oppressed',
    'La música que se canta en las iglesias negras de Estados Unidos. Empieza donde empieza el blues —las mismas personas, los mismos años— y las dos ramas nunca se separaron del todo.':
        'The music sung in the Black churches of the United States. It begins '
        'where the blues begins — the same people, the same years — and the two '
        'branches never fully separated.',
    'La nota azul': 'The blue note',
    'La razón es práctica. Sin dependencias el ejecutable queda chico, arranca rápido y no se rompe cuando una librería de terceros cambia de versión. La única dependencia real de todo el proyecto es la que dibuja la ventana.':
        'The reason is practical. With no dependencies the executable stays '
        'small, starts fast and does not break when a third-party library changes '
        'version. The only real dependency in the whole project is the one that '
        'draws the window.',
    'La regla de oro es sencilla: cuanto menos se mueve cada voz, mejor. Si dos acordes seguidos comparten una nota, lo natural es que la voz que la tenía se quede quieta. Todo lo demás son matices sobre esa idea.':
        'The golden rule is simple: the less each voice moves, the better. If two '
        'chords in a row share a note, the natural thing is for the voice that '
        'had it to stay put. Everything else is shading on that idea.',
    'La sensible y el final': 'The leading tone and the ending',
    'La serie armónica': 'The harmonic series',
    'La serie armónica de un la2 de 110 hercios. Las barras están igualmente espaciadas porque son múltiplos enteros, y caen de altura como uno sobre ene, que es más o menos lo que hace una cuerda de verdad. El número de abajo es qué armónico es.':
        'The harmonic series of a 110-hertz A2. The bars are evenly spaced '
        'because they are whole-number multiples, and their heights fall off as '
        'one over n, which is roughly what a real string does. The number below '
        'is which harmonic it is.',
    'La serie subarmónica': 'The subharmonic series',
    'La serie subarmónica de un la5 de 880 hercios: la misma división, hacia abajo. Se amontonan hacia los graves porque dividir por números cada vez más grandes da saltos cada vez más chicos. Las barras van todas iguales porque no hay amplitudes que dibujar: nada las produce.':
        'The subharmonic series of an 880-hertz A5: the same division, going '
        'down. They crowd toward the bass because dividing by ever larger numbers '
        'gives ever smaller steps. The bars are all the same height because there '
        'are no amplitudes to draw: nothing produces them.',
    'La sexta en lugar de la quinta': 'The sixth in place of the fifth',
    'La subdominante cierra directamente sobre la tónica, sin pasar por la dominante. Es el «amén» de los himnos, y suena más blando y más antiguo que la auténtica, justamente porque le falta la sensible tirando.':
        'The subdominant closes straight onto the tonic, without passing through '
        'the dominant. It is the “amen” of the hymns, and it sounds softer and '
        'older than the authentic one, precisely because it lacks the leading '
        'tone pulling.',
    'La tonalidad: por qué unos acordes siguen a otros':
        'Tonality: why some chords follow others',
    'La voz humana agrega una vuelta más. La garganta no atenúa parejo: refuerza siempre las mismas bandas de frecuencia, estén donde estén los armónicos. Esas bandas se llaman formantes, y son la razón de que una «a» y una «i» cantadas en la misma nota sean la misma serie con otras barras levantadas. Cambiás de vocal sin cambiar de nota.':
        'The human voice adds one more turn. The throat does not attenuate '
        'evenly: it always reinforces the same frequency bands, wherever the '
        'harmonics happen to be. Those bands are called formants, and they are '
        'why an “ah” and an “ee” sung on the same note are the same series with '
        'different bars raised. You change vowel without changing note.',
    'Las cadencias famosas del capítulo anterior no se construyen por peso: son citas guardadas enteras, que el programa propone cuando la tonalidad, el estilo y la cantidad de acordes coinciden exactamente con las que la cita necesita.':
        'The famous cadences of the previous chapter are not built by weight: '
        'they are quotations stored whole, which the program offers when the key, '
        'the style and the number of chords match exactly what the quotation '
        'needs.',
    'Las dos cifras juntas explican el tamaño de un archivo de audio: 44.100 números por segundo, dos bytes cada uno, son 88.200 bytes por segundo de sonido en mono. Un minuto son cinco megabytes.':
        'The two figures together explain the size of an audio file: 44,100 '
        'numbers a second, two bytes each, is 88,200 bytes per second of mono '
        'sound. One minute is five megabytes.',
    'Las dos cosas juntas dejaron la búsqueda unas seis veces más rápida, y el resultado es **exactamente el mismo**: se verificó nota por nota que la misma semilla sigue dando la misma partitura. Una optimización que cambie lo que suena no es una optimización, es otro programa.':
        'The two things together left the search about six times faster, and the '
        'result is **exactly the same**: it was verified note by note that the '
        'same seed still gives the same score. An optimization that changes what '
        'you hear is not an optimization, it is a different program.',
    'Las notas de paso, la sexta de Bach y los gestos de época se aplican **después** de la búsqueda, sobre la solución ganadora, y no dentro del cálculo de costo.':
        'Passing notes, Bach’s sixth and the period gestures are applied '
        '**after** the search, on the winning solution, and not inside the cost '
        'calculation.',
    'Las notas que no llevan acorde': 'The notes that carry no chord',
    'Las otras dos veces la visión terminó con alguien yéndose. Ésta termina con alguien llegando, y no a buscar una guitarra.':
        'The other two times the vision ended with somebody leaving. This one '
        'ends with somebody arriving, and not for a guitar.',
    'Las quintas directas —cuando las dos voces llegan a una quinta moviéndose para el mismo lado, aunque antes no lo estuvieran— son un caso más leve: el programa las penaliza en vez de prohibirlas.':
        'Direct fifths — when both voices arrive at a fifth moving the same way, '
        'even if they were not at one before — are a milder case: the program '
        'penalizes them rather than forbidding them.',
    'Las reglas que hoy se enseñan como leyes —no a quintas paralelas, la sensible sube, la séptima baja— no fueron inventadas por nadie: se destilaron después, mirando qué hacían estos compositores. Son una descripción, no un reglamento.':
        'The rules taught today as laws — no parallel fifths, the leading tone '
        'rises, the seventh falls — were not invented by anyone: they were '
        'distilled afterwards, by looking at what these composers did. They are a '
        'description, not a rulebook.',
    'Las séptimas': 'Sevenths',
    'Las tres de arriba son las que suenan a acorde. Después hay otro grupo: la sexta, la séptima y la novena, que ponen la melodía en un lugar más tenso del acorde.':
        'The three above are the ones that sound like the chord. Then there is '
        'another group: the sixth, the seventh and the ninth, which put the '
        'melody in a tenser place in the chord.',
    'Las tres funciones': 'The three functions',
    'Las tríadas casi no existen: el acorde base del jazz es el de séptima, y de ahí para arriba.':
        'Triads barely exist: the base chord of jazz is the seventh chord, and up '
        'from there.',
    'Las visitas': 'The visitors',
    'Las «formas de onda» de los sintetizadores son la misma idea escrita como fórmula. Una onda diente de sierra son todos los armónicos con amplitud uno sobre ene; una onda cuadrada son sólo los impares; una triangular, los impares cayendo con el cuadrado. No son maneras distintas de vibrar: son la misma serie con distintas alturas de barra.':
        'The “waveforms” of synthesizers are the same idea written as a formula. '
        'A sawtooth wave is all the harmonics with amplitude one over n; a square '
        'wave is only the odd ones; a triangle, the odd ones falling off with the '
        'square. They are not different ways of vibrating: they are the same '
        'series with different bar heights.',
    'Lo mismo con los préstamos —el cuarto grado menor, el séptimo bemol— y con las citas famosas: se ofrecen, pero pierden contra la nota que hay que sostener.':
        'The same goes for the borrowings — the minor fourth degree, the flat '
        'seventh — and for the famous quotations: they are offered, but they lose '
        'against the note that has to be supported.',
    'Lo mínimo para entender el resto': 'The least you need for the rest',
    'Lo primero fue dejar de hacer trabajo al pedo. Cuando las reglas duras anulan a la mayoría de los hijos de una generación, el programa completa la población clonando a los mejores; durante mucho tiempo volvía a puntuar cada clon, aunque su costo ya estuviera calculado. Eran cuatro de cada diez evaluaciones de la corrida, y un mismo cromosoma llegó a puntuarse siete mil veces. Sacarlas hizo además que valiera la pena repartir el trabajo entre los procesadores de la máquina, cosa que antes casi no rendía: los otros núcleos esperaban mientras el principal recalculaba lo que ya sabía.':
        'The first thing was to stop doing pointless work. When the hard rules '
        'void most of a generation’s children, the program fills the population '
        'back up by cloning the best; for a long time it re-scored every clone, '
        'even though its cost was already known. That was four in every ten '
        'evaluations of the run, and one and the same chromosome was scored seven '
        'thousand times. Removing them also made it worth splitting the work '
        'across the machine’s processors, which had barely paid off before: the '
        'other cores sat waiting while the main one recalculated what it already '
        'knew.',
    'Lo primero que aclaró es que el canto que lleva su nombre no lo escribió él. Se lo pusieron trescientos años después de muerto, para que la colección tuviera un autor: los cantos eran de todos y de nadie. La paloma viene de ahí --- se contó durante siglos que el Espíritu Santo se le posaba en el hombro y le dictaba las melodías al oído, y así se lo pintó desde entonces. Es la manera más elegante que encontró la Edad Media de decir que no sabía quién los había compuesto.':
        'The first thing he made clear is that he did not write the chant that '
        'bears his name. They put it on him three hundred years after he died, so '
        'the collection would have an author: the chants belonged to everyone and '
        'to no one. The dove comes from there — for centuries it was said that '
        'the Holy Spirit perched on his shoulder and dictated the melodies into '
        'his ear, and that is how he has been painted ever since. It is the most '
        'elegant way the Middle Ages found of saying it did not know who had '
        'composed them.',
    'Lo que este programa hace es la parte técnica de esa historia: dadas unas notas que tienen que sonar juntas, decidir qué canta cada voz. Es exactamente el problema que se estudiaron todos los que aparecen en las páginas que siguen.':
        'What this program does is the technical part of that story: given some '
        'notes that have to sound together, decide what each voice sings. It is '
        'exactly the problem studied by everyone who appears in the pages that '
        'follow.',
    'Lo que quedó anotado de las veces que alguien se apareció a explicar algo. Este capítulo no se llena leyendo: se llena trabajando hasta que alguien venga a mirar lo que hiciste.':
        'What was written down from the times somebody appeared to explain '
        'something. This chapter does not fill up by reading: it fills up by '
        'working until somebody comes to look at what you made.',
    'Lo que sigue es lo que quedó anotado. Parte lo dijo él; el resto se averiguó después, buscando quién había sido.':
        'What follows is what was written down. Part of it he said himself; the '
        'rest was found out afterwards, by looking into who he had been.',
    'Lo que sí existe de verdad son los **subarmónicos producidos**: un cuerpo forzado a vibrar con mucha energía puede empezar a saltar de a dos ciclos y dar la mitad de la frecuencia. Se oye en el canto difónico, en un platillo mal golpeado y en la voz de un cantante que la está forzando. Es un fenómeno real, pero es un accidente del cuerpo, no una serie que esté ahí desde el principio.':
        'What does genuinely exist are **produced subharmonics**: a body forced '
        'to vibrate with a great deal of energy can start skipping every other '
        'cycle and give half the frequency. You hear it in overtone singing, in a '
        'badly struck cymbal and in the voice of a singer pushing too hard. It is '
        'a real phenomenon, but it is an accident of the body, not a series that '
        'is there from the start.',
    'Lo raro es justamente eso: los tres llevan séptima. Ya sabemos, del capítulo de armonía, que un acorde con séptima menor pide resolver —está incómodo, tira hacia otro lado—. Que el acorde de reposo, el primer grado, también la lleve es una contradicción: la casa a la que se vuelve tampoco es un lugar donde quedarse.':
        'That is precisely the odd part: all three carry a seventh. We already '
        'know, from the harmony chapter, that a chord with a minor seventh asks '
        'to resolve — it is uncomfortable, it pulls elsewhere. That the resting '
        'chord, the first degree, should carry one too is a contradiction: the '
        'home you come back to is not a place to stay either.',
    'Lo segundo fue traducir a C las tres partes que la búsqueda pisa millones de veces —el evaluador, las reglas de estilo y la representación de las notas— con una herramienta que se llama Cython. No es una reescritura: son los mismos archivos de Python, sin una línea cambiada, con una hoja de tipos al lado que dice «este número siempre es un entero». Con eso alcanza para que la suma se compile a una suma de verdad.':
        'The second was translating into C the three parts the search treads on '
        'millions of times — the evaluator, the style rules and the '
        'representation of the notes — with a tool called Cython. It is not a '
        'rewrite: they are the same Python files, without a line changed, with a '
        'type sheet alongside saying “this number is always an integer”. That is '
        'enough for the addition to compile into a real addition.',
    'Los acordes están dados. Lo que no está dado es qué nota de cada acorde canta cada voz y en qué octava. Ese reparto tiene muchísimas combinaciones posibles: con cuatro voces y una docena de acordes, la cantidad de repartos válidos se cuenta en miles de millones.':
        'The chords are given. What is not given is which note of each chord each '
        'voice sings and in which octave. That layout has an enormous number of '
        'possible combinations: with four voices and a dozen chords, the number '
        'of valid layouts runs into the billions.',
    'Los armónicos caen donde la física los pone, y la física no sabe nada de teclas. Cuando se comparan las dos listas, no coinciden.':
        'The harmonics fall where physics puts them, and physics knows nothing '
        'about keys. When the two lists are compared, they do not match.',
    'Los cuatro movimientos': 'The four motions',
    'Los destinos naturales son los parientes cercanos: la dominante (subir una quinta), la subdominante (bajar una quinta) y el relativo menor. El programa marca en violeta los acordes que están de visita en otra tonalidad, así se ve de un vistazo por dónde viajó la pieza.':
        'The natural destinations are the close relatives: the dominant (up a '
        'fifth), the subdominant (down a fifth) and the relative minor. The '
        'program marks in violet the chords that are visiting another key, so you '
        'can see at a glance where the piece travelled.',
    'Los dos ejes del experimentador son exactamente ésos, y no hay un tercero: cualquier sonido que exista se puede describir diciendo qué frecuencias tiene y con cuánta amplitud cada una.':
        'The workbench’s two axes are exactly those, and there is no third: any '
        'sound that exists can be described by saying which frequencies it has '
        'and with how much amplitude each one.',
    'Los jazzes': 'The jazzes',
    'Los modos': 'The modes',
    'Los números romanos son útiles porque son los mismos en cualquier tonalidad. Un «V - I» es lo mismo en do que en fa sostenido; sólo cambian las letras. En la pantalla de resultados vas a ver el número romano debajo de cada acorde: eso te dice qué papel cumple, no sólo cómo se llama.':
        'Roman numerals are useful because they are the same in any key. A “V - '
        'I” is the same in C as in F sharp; only the letters change. On the '
        'results screen you will see the roman numeral under each chord: that '
        'tells you what role it plays, not just what it is called.',
    'Los otros dos modos arrancan de los acordes. Éste arranca de una línea y busca qué puede sostenerla, que es un problema al revés: la melodía está decidida y cada acorde tiene que hacerle lugar a una nota que no se puede mover.':
        'The other two modes start from the chords. This one starts from a line '
        'and looks for what can hold it up, which is the problem in reverse: the '
        'melody is decided and every chord has to make room for a note that '
        'cannot be moved.',
    'Los otros tres que vinieron de visita explicaron algo. Éste no explicó nada: dijo tres palabras y se fue. Queda anotado igual, porque la historia que empezó esa noche es la que todavía se sigue contando.':
        'The other three who came to visit explained something. This one '
        'explained nothing: he said three words and left. It is written down '
        'anyway, because the story that began that night is the one still being '
        'told.',
    'Los tres estilos': 'The three styles',
    'Los tres estilos que el programa conoce están separados por unos mil años. Cada uno se escribe acá la primera vez que lo usás, en cualquiera de los tres modos.':
        'The three styles the program knows are about a thousand years apart. '
        'Each one writes itself here the first time you use it, in any of the '
        'three modes.',
    'Mil años en un párrafo': 'A thousand years in one paragraph',
    'Mi–si es una quinta. Las dos voces suben un grado y fa–do vuelve a ser una quinta: eso es una quinta paralela.':
        'E–B is a fifth. Both voices go up a step and F–C is a fifth again: that '
        'is a parallel fifth.',
    'Modulación': 'Modulation',
    'Modular es cambiar de tonalidad en el medio de la pieza: la gravedad se muda a otra nota y el oído la sigue. No es lo mismo que un préstamo, que era una visita corta sin cambiar de casa.':
        'To modulate is to change key in the middle of the piece: gravity moves '
        'to another note and the ear follows it. It is not the same as a '
        'borrowing, which was a short visit without moving house.',
    'Murió el 16 de agosto de 1938, cerca de Greenwood, a los veintisiete años. Lo que sigue es lo que se sabe de esa muerte --- que es menos de lo que parece --- y lo que pasó con su música después, que es muchísimo más de lo que pasó mientras vivía.':
        'He died on 16 August 1938, near Greenwood, at the age of twenty-seven. '
        'What follows is what is known about that death — which is less than it '
        'seems — and what happened to his music afterwards, which is a great deal '
        'more than happened while he was alive.',
    'Más de cuatro voces': 'More than four voices',
    'Nace en Nueva Orleans alrededor de 1900, del cruce entre el blues —que traía las notas «dobladas» de la música afroamericana—, el ragtime y las bandas de metales que la ciudad tenía por todas partes. Al principio la armonía era sencilla; lo nuevo era el ritmo y que se improvisara.':
        'It is born in New Orleans around 1900, out of the crossing of the blues '
        '— which brought the “bent” notes of African American music — ragtime and '
        'the brass bands the city had everywhere. At first the harmony was '
        'simple; what was new was the rhythm and the improvising.',
    'Nada de esto es ilegal. Debussy escribió quintas paralelas a propósito durante toda su vida, y el rock vive de ellas. La regla describe un estilo, no una ley de la física.':
        'None of this is illegal. Debussy wrote parallel fifths on purpose all '
        'his life, and rock lives off them. The rule describes a style, not a law '
        'of physics.',
    'No hace falta saber qué se acordó ahí. Lo que sigue es el pacto puesto bajo sospecha: quién lo contó, de dónde salió realmente, a quién le convenía que se contara y qué le hizo a la música durante los ochenta años que estuvo circulando. Ninguna de las cuatro respuestas señala a Robert Johnson.':
        'You do not need to know what was agreed there. What follows is the '
        'bargain put under suspicion: who told it, where it really came from, who '
        'benefited from its being told and what it did to the music over the '
        'eighty years it was in circulation. None of the four answers points at '
        'Robert Johnson.',
    'No hay un acorde por nota. La armonía se escucha cambiar en los tiempos fuertes, y ahí es donde el programa pone los acordes: en un cuatro por cuatro, en el uno y en el tres.':
        'There is not one chord per note. Harmony is heard changing on the strong '
        'beats, and that is where the program puts the chords: in four-four, on '
        'one and on three.',
    'No pertenece a ninguna de las dos escalas grandes. No es de la mayor ni de la menor: cae entre la tercera y la quinta, en un lugar donde la teoría europea no había puesto nada.':
        'It belongs to neither of the two big scales. It is not of the major nor '
        'of the minor: it falls between the third and the fifth, in a place where '
        'European theory had put nothing.',
    'No repetir, y qué gana cuando hay que elegir':
        'Not repeating, and what wins when a choice has to be made',
    'No tiene autor. Aparece en grabaciones de los años cincuenta, está en Charlie Parker, está en Coltrane, está en bandas de sonido, está en canciones pop que no tienen nada que ver con el jazz.':
        'It has no author. It turns up in recordings from the fifties, it is in '
        'Charlie Parker, it is in Coltrane, it is in film scores, it is in pop '
        'songs that have nothing to do with jazz.',
    'No toda frase cierra. Terminar en el V deja la música colgada: es la semicadencia, y sirve para partir una idea larga en dos mitades, la primera de las cuales queda abierta.':
        'Not every phrase closes. Ending on the V leaves the music hanging: that '
        'is the half cadence, and it serves to split a long idea into two halves, '
        'the first of which is left open.',
    'Novenas, oncenas y el color': 'Ninths, elevenths and color',
    'Oblicuo: una se queda, la otra se mueve.':
        'Oblique: one stays, the other moves.',
    'Organizador o Generador · pantalla de reglas · dial «Cuánto color». Hasta un tercio de la barra sólo agrega sextas, que es el color más suave.':
        'Organizer or Generator · rules screen · the “How much color” dial. Up to '
        'a third of the way along it only adds sixths, which are the gentlest '
        'color.',
    'Pantalla de Voces · marcá hasta seis. Los rangos de cada cuerda son editables si tu grupo llega a más o a menos.':
        'Voices screen · tick up to six. The range of each part can be edited if '
        'your group reaches further, or less far.',
    'Pantalla de reglas · «Prohibir quintas paralelas» y «Prohibir octavas paralelas». Vienen prendidas en Barroco y apagadas en Gregoriano.':
        'Rules screen · “Forbid parallel fifths” and “Forbid parallel octaves”. '
        'They come switched on in Baroque and off in Gregorian.',
    'Paralelo: las dos para el mismo lado, la misma distancia. El intervalo no cambia.':
        'Parallel: both the same way, the same distance. The interval does not '
        'change.',
    'Población, generaciones, elitismo, torneo y mutación se tocan en el engranaje de abajo a la izquierda. Más población y más generaciones dan mejores resultados y tardan más.':
        'Population, generations, elitism, tournament and mutation are changed '
        'under the gear at the bottom left. More population and more generations '
        'give better results and take longer.',
    'Por eso armonizar no es «encontrar el acorde». Es elegir cuál de los que sirven es el que querés.':
        'That is why harmonizing is not “finding the chord”. It is choosing which '
        'of the ones that work is the one you want.',
    'Por eso en el estilo barroco están prohibidas de plano: una solución que las tenga se descarta entera, no importa lo bien que esté todo lo demás. En el gregoriano, en cambio, están permitidas, porque el organum medieval se basa justamente en ellas. Y en el jazz se toleran porque los acordes son tan densos que el efecto no llega a escucharse.':
        'That is why in the baroque style they are forbidden outright: a solution '
        'that has them is thrown out entirely, no matter how good everything else '
        'is. In Gregorian, on the other hand, they are allowed, because medieval '
        'organum is built on precisely them. And in jazz they are tolerated '
        'because the chords are so dense the effect never quite gets heard.',
    'Por qué el piano está afinado mal': 'Why the piano is tuned wrong',
    'Por qué la búsqueda es rápida': 'Why the search is fast',
    'Por qué los adornos van al final': 'Why the ornaments come last',
    'Por qué se trabaja de atrás para adelante':
        'Why the work goes from the end backwards',
    'Por qué un violín no es una flauta': 'Why a violin is not a flute',
    'Primero fue una sola línea cantada al unísono. Después alguien la dobló en paralelo y aparecieron dos voces. De ahí a que las voces se independizaran pasaron siglos, y de ahí a que la armonía —los acordes como entidad propia, con una gravedad que empuja de uno a otro— pasaron otros tantos.':
        'First it was a single line sung in unison. Then somebody doubled it in '
        'parallel and two voices appeared. Centuries passed before the voices '
        'became independent, and as many again before harmony — chords as '
        'entities of their own, with a gravity pushing from one to the next — '
        'came about.',
    'Probarlos todos es imposible. Elegir siempre el más cercano acorde por acorde tampoco sirve, porque la mejor decisión en el acorde 3 puede dejarte sin salida en el 7. Hace falta algo que busque en grande y que mejore de a poco.':
        'Trying them all is impossible. Always choosing the nearest one chord by '
        'chord does not work either, because the best decision at chord 3 can '
        'leave you with no way out at chord 7. You need something that searches '
        'broadly and improves little by little.',
    'Prohíbe quintas y octavas paralelas, premia el movimiento contrario, castiga los saltos de tritono y de séptima, y vigila que las voces no se crucen. Si nunca escribiste armonía, empezá acá: es el estilo donde las reglas están más claras y donde más se nota cuando algo está mal.':
        'It forbids parallel fifths and octaves, rewards contrary motion, '
        'penalizes tritone and seventh leaps, and watches that the voices do not '
        'cross. If you have never written harmony, start here: it is the style '
        'where the rules are clearest and where a mistake shows up most.',
    'Préstamos e intercambio modal': 'Borrowings and modal interchange',
    'Quintas y octavas paralelas': 'Parallel fifths and octaves',
    'Qué es un sonido': 'What a sound is',
    'Qué problema resuelve': 'What problem it solves',
    'Qué se está eligiendo': 'What is being chosen',
    'Recién en los siglos XI y XII las dos voces empezaron a moverse por su cuenta, y en Notre Dame de París —con Léonin y Pérotin— aparecieron tres y cuatro voces con ritmo escrito. Ese es el momento en que nace el contrapunto.':
        'Only in the eleventh and twelfth centuries did the two voices begin to '
        'move on their own, and at Notre Dame in Paris — with Léonin and Pérotin '
        '— three and four voices with written rhythm appeared. That is the moment '
        'counterpoint is born.',
    'Repetido trescientas veces, ese proceso converge a soluciones muy buenas sin haber mirado ni una milésima del espacio. Como el azar interviene, dos corridas con la misma entrada dan resultados parecidos pero no idénticos: por eso el programa te muestra las tres mejores y no una sola.':
        'Repeated three hundred times, that process converges on very good '
        'solutions without having looked at a thousandth of the space. Because '
        'chance is involved, two runs from the same input give similar but not '
        'identical results: that is why the program shows you the best three and '
        'not just one.',
    'Repetir el mismo acorde en dos tiempos fuertes seguidos cuesta, porque una armonía que no se mueve deja la melodía sola. Pero cuesta bastante menos que poner la melodía en un mal lugar.':
        'Repeating the same chord on two strong beats in a row costs something, '
        'because a harmony that does not move leaves the melody on its own. But '
        'it costs a good deal less than putting the melody in a bad place.',
    'Robert Johnson nació en Misisipi en 1911. Grabó veintinueve canciones en dos sesiones --- un cuarto de hotel en San Antonio, un depósito en Dallas --- y de él quedaron esas canciones, dos fotografías y muy poco más. Todo lo demás es relato.':
        'Robert Johnson was born in Mississippi in 1911. He recorded twenty-nine '
        'songs in two sessions — a hotel room in San Antonio, a warehouse in '
        'Dallas — and what is left of him is those songs, two photographs and '
        'very little else. Everything else is story.',
    'Saltos, cruces y espaciado': 'Leaps, crossings and spacing',
    'Se escribe cuando alguien te enseñe a escribirla.':
        'It writes itself when somebody teaches you to write it.',
    'Se escribe cuando alguien te muestre que no hay un solo jazz.':
        'It writes itself when somebody shows you there is not one single jazz.',
    'Se escribe cuando alguien venga a escuchar el canto.':
        'It writes itself when somebody comes to hear the chant.',
    'Se escribe cuando alguien venga a leer lo que escribiste.':
        'It writes itself when somebody comes to read what you wrote.',
    'Se escribe cuando alguien venga a mirar lo que estás haciendo con los armónicos.':
        'It writes itself when somebody comes to look at what you are doing with '
        'the harmonics.',
    'Se escribe cuando bajes toda la escalera.':
        'It writes itself when you walk all the way down the staircase.',
    'Se escribe cuando cantes con tus hermanos.':
        'It writes itself when you sing with your brothers.',
    'Se escribe cuando la gracia te alcance.':
        'It writes itself when grace reaches you.',
    'Se escribe cuando la rueda dé la vuelta entera.':
        'It writes itself when the wheel goes all the way round.',
    'Se escribe cuando pruebes el modo coral.':
        'It writes itself when you try chorale mode.',
    'Se escribe cuando te salga sin pensarla.':
        'It writes itself when it comes out without your thinking about it.',
    'Se escribe cuando toques la que no existe.':
        'It writes itself when you play the one that does not exist.',
    'Se escribe cuando toques la que sabe todo el mundo.':
        'It writes itself when you play the one everybody knows.',
    'Se escribe cuando uses el experimentador de armónicos, al lado de los logros.':
        'It writes itself when you use the harmonics workbench, next to the '
        'achievements.',
    'Se escribe la primera vez que uses el Armonizador.':
        'It writes itself the first time you use the Harmonizer.',
    'Se escribe sola con tu primer ii-V.':
        'It writes itself with your first ii-V.',
    'Se escribe sola con tu primera cadencia plagal.':
        'It writes itself with your first plagal cadence.',
    'Se escribe sola con tu primera modulación en el Generador.':
        'It writes itself with your first modulation in the Generator.',
    'Se escribe sola cuando armes un acorde con séptima, novena y oncena a la vez.':
        'It writes itself when you build a chord with a seventh, a ninth and an '
        'eleventh all at once.',
    'Se escribe sola cuando cambies la vox principalis en el estilo gregoriano.':
        'It writes itself when you change the vox principalis in the Gregorian '
        'style.',
    'Se escribe sola cuando completes una pieza sin quintas paralelas.':
        'It writes itself when you complete a piece with no parallel fifths.',
    'Se escribe sola cuando descubras el acorde de sexta con la quinta omitida.':
        'It writes itself when you discover the sixth chord with the fifth '
        'omitted.',
    'Se escribe sola cuando encadenes tres dominantes.':
        'It writes itself when you chain three dominants together.',
    'Se escribe sola cuando escribas tu primer dominante 6/4.':
        'It writes itself when you write your first cadential 6/4.',
    'Se escribe sola cuando escribas un acorde disminuido.':
        'It writes itself when you write a diminished chord.',
    'Se escribe sola cuando escribas una pieza a seis voces.':
        'It writes itself when you write a piece in six voices.',
    'Se escribe sola cuando generes tus primeras notas de paso.':
        'It writes itself when you generate your first passing notes.',
    'Se escribe sola cuando hagas tu primera pieza barroca.':
        'It writes itself when you make your first baroque piece.',
    'Se escribe sola cuando hagas tu primera pieza de jazz.':
        'It writes itself when you make your first jazz piece.',
    'Se escribe sola cuando hagas tu primera pieza gregoriana.':
        'It writes itself when you make your first Gregorian piece.',
    'Se escribe sola cuando hagas una pieza en un modo que no sea el jónico ni el eólico.':
        'It writes itself when you make a piece in a mode other than ionian or '
        'aeolian.',
    'Se escribe sola cuando hagas una pieza que termine en un dominante.':
        'It writes itself when you make a piece that ends on a dominant.',
    'Se escribe sola cuando la descubras.':
        'It writes itself when you discover it.',
    'Se escribe sola cuando uses tu primer acorde prestado.':
        'It writes itself when you use your first borrowed chord.',
    'Se escribe sola cuando uses un acorde de séptima.':
        'It writes itself when you use a seventh chord.',
    'Se escribe sola la primera vez que dejes pasar una quinta paralela.':
        'It writes itself the first time you let a parallel fifth through.',
    'Se reconoce sobre un V mayor que resuelve a la tónica, cantado con la quinta en el bajo, la fundamental encima y la tercera arriba. Cualquier cantidad de voces y cualquiera de los tres modos; el barroco es el estilo que lo busca.':
        'It is recognized over a major V resolving to the tonic, voiced with the '
        'fifth in the bass, the root above it and the third on top. Any number of '
        'voices and any of the three modes; the baroque is the style that looks '
        'for it.',
    'Separarlos deja las dos cosas limpias. Primero se resuelve el problema de conducción; después se decora lo que ya está bien resuelto.':
        'Keeping them apart leaves both things clean. First the voice-leading '
        'problem is solved; then what is already well solved gets decorated.',
    'Sextas, séptimas y novenas': 'Sixths, sevenths and ninths',
    'Si dos voces están a una quinta de distancia y las dos suben un tono, siguen estando a una quinta. Eso es una quinta paralela, y es la prohibición más famosa de toda la música occidental.':
        'If two voices are a fifth apart and both go up a whole tone, they are '
        'still a fifth apart. That is a parallel fifth, and it is the most famous '
        'prohibition in all of Western music.',
    'Si el cuarto grado se usa menor —iv en vez de IV— la cadencia se vuelve plagal menor y suena mucho más oscura. Es un recurso muy usado en música popular para el último acorde antes del final.':
        'If the fourth degree is used minor — iv instead of IV — the cadence '
        'becomes a minor plagal and sounds much darker. It is a device much used '
        'in popular music for the last chord before the ending.',
    'Si la anteúltima nota de la melodía es la sensible —el séptimo grado, el que está a un semitono de la tónica— la pieza está pidiendo una cadencia y no otra cosa.':
        'If the second-to-last note of the melody is the leading tone — the '
        'seventh degree, the one a semitone from the tonic — the piece is asking '
        'for a cadence and nothing else.',
    'Si la tercera está un semitono más abajo el acorde es menor y suena más oscuro: do-mi bemol-sol es do menor, Cm. Toda la diferencia entre «alegre» y «triste» en esta música está en esa única nota.':
        'If the third is a semitone lower the chord is minor and sounds darker: '
        'C-E flat-G is C minor, Cm. The whole difference between “happy” and '
        '“sad” in this music is in that one note.',
    'Si multiplicar da una serie, dividir tendría que dar otra. Ésa es la serie subarmónica: la mitad de la frecuencia, el tercio, el cuarto, el quinto. El espejo exacto de la otra, hacia abajo.':
        'If multiplying gives a series, dividing ought to give another. That is '
        'the subharmonic series: half the frequency, a third, a quarter, a fifth. '
        'The exact mirror of the other one, downward.',
    'Si tomás las siete notas de do mayor pero hacés que mande el re en vez del do, la escala es la misma y el resultado suena distinto. Eso es un modo. El jónico es el mayor de toda la vida y el eólico es el menor; los otros —dórico, frigio, lidio, mixolidio— tienen colores propios.':
        'If you take the seven notes of C major but put D in charge instead of C, '
        'the scale is the same and the result sounds different. That is a mode. '
        'Ionian is plain old major and aeolian is minor; the others — dorian, '
        'phrygian, lydian, mixolydian — have colors of their own.',
    'Si una voz salta una tercera —de do a mi— queda un hueco: el re. Meter ese re en el medio, breve, convierte el salto en tres notas seguidas por grado conjunto y suaviza la línea.':
        'If a voice leaps a third — from C to E — a gap is left: the D. Putting '
        'that D in the middle, briefly, turns the leap into three notes in a row '
        'by step and smooths the line out.',
    'Si va sobre sol, do va sobre do. El semitono de arriba subiendo y el salto de abajo cayendo: eso es toda la cadencia.':
        'If B goes over G, C goes over C. The semitone above rising and the leap '
        'below falling: that is the whole cadence.',
    'Siete notas: sube por grados desde el segundo grado hasta el quinto, baja al tercero, salta al primero y sube al segundo. En re menor son re, mi, fa, sol, mi, do, re.':
        'Seven notes: it rises by step from the second degree to the fifth, drops '
        'to the third, leaps to the first and rises to the second. In D minor '
        'they are D, E, F, G, E, C, D.',
    'Sin eso pasaba lo peor que le puede pasar a un final: la dominante sonaba un tiempo antes, sobre otra nota, y la sensible pasaba como si fuera de adorno. La pieza terminaba sin haber terminado.':
        'Without that, the worst thing that can happen to an ending happened: the '
        'dominant sounded a beat earlier, over another note, and the leading tone '
        'went by as though it were an ornament. The piece ended without having '
        'ended.',
    'Sobre cada nota de la escala se puede armar un acorde usando sólo notas de la escala. Salen siete acordes, y se numeran con números romanos: I, ii, iii, IV, V, vi, vii°. En do mayor eso es C, Dm, Em, F, G, Am y Bdim. Mayúscula significa mayor y minúscula menor; el «°» es disminuido.':
        'On every note of the scale a chord can be built using only notes of the '
        'scale. Seven chords come out, numbered with roman numerals: I, ii, iii, '
        'IV, V, vi, vii°. In C major that is C, Dm, Em, F, G, Am and Bdim. '
        'Uppercase means major and lowercase minor; the “°” is diminished.',
    'Su apellido quiere decir *arroyo*. Beethoven dijo que no debería llamarse arroyo sino mar.':
        'His surname means *brook*. Beethoven said he should not be called brook '
        'but sea.',
    'Suena antigua y española a la vez. Es el esqueleto de la cadencia andaluza, la que se escucha en el flamenco y en media música popular del Mediterráneo.':
        'It sounds ancient and Spanish at once. It is the skeleton of the '
        'Andalusian cadence, the one you hear in flamenco and in half the popular '
        'music of the Mediterranean.',
    'Terminar en la dominante': 'Ending on the dominant',
    'Terminar una pieza a cuatro voces sin una sola quinta paralela parece poca cosa cuando lo hace una computadora en dos segundos. A mano es el ejercicio con el que se pasan meses los estudiantes de armonía.':
        'Finishing a four-voice piece without a single parallel fifth looks like '
        'nothing much when a computer does it in two seconds. By hand it is the '
        'exercise harmony students spend months on.',
    'Todo escrito a mano': 'All written by hand',
    'Todo lo que cae entre un acorde y el siguiente se escucha contra el acorde que ya está sonando. Eso no es un problema: es la mitad de lo que hace que una melodía se mueva.':
        'Everything falling between one chord and the next is heard against the '
        'chord already sounding. That is not a problem: it is half of what makes '
        'a melody move.',
    'Tomá dos voces cualesquiera y mirá qué hacen entre un acorde y el siguiente. Sólo hay cuatro posibilidades:':
        'Take any two voices and look at what they do between one chord and the '
        'next. There are only four possibilities:',
    'Tres acordes: el primero, el cuarto y el quinto grado de la escala, y los tres con séptima menor. En do se escriben C7, F7 y G7.':
        'Three chords: the first, the fourth and the fifth degree of the scale, '
        'and all three with a minor seventh. In C they are written C7, F7 and G7.',
    'Tres o más acordes de dominante seguidos, cada uno resolviendo en el siguiente que a su vez es dominante de otro. Cada resolución promete descanso y entrega una tensión nueva.':
        'Three or more dominant chords in a row, each resolving onto the next '
        'which is itself the dominant of another. Every resolution promises rest '
        'and delivers a new tension.',
    'Un G7 quiere ir a C mucho más que un G a secas. Por eso el acorde de séptima es la herramienta principal para empujar la música hacia adelante, y por eso el jazz los usa prácticamente en todos lados: en ese estilo lo raro es la tríada, no la séptima.':
        'A G7 wants to go to C far more than a plain G does. That is why the '
        'seventh chord is the main tool for pushing music forward, and why jazz '
        'uses them practically everywhere: in that style the odd thing is the '
        'triad, not the seventh.',
    'Un acorde disminuido apila dos terceras menores: si-re-fa. Adentro tiene un tritono —esa distancia inestable de tres tonos— y por eso no se sostiene solo: es puro tránsito.':
        'A diminished chord stacks two minor thirds: B-D-F. It has a tritone '
        'inside it — that unstable distance of three whole tones — and that is '
        'why it does not stand on its own: it is pure transit.',
    'Un clarinete en el mismo la3: los impares fuertes y los pares casi ausentes. Es el mismo gráfico de arriba con otras alturas, y suena a otro instrumento.':
        'A clarinet on the same A3: the odd ones strong and the even ones almost '
        'absent. It is the same graph as above with different heights, and it '
        'sounds like another instrument.',
    'Un compás de dos o de tres lleva uno solo, en el uno. Los compases de amalgama —el seis por ocho, el nueve por ocho— se acentúan cada tres corcheas, y por eso un seis por ocho son dos tiempos y no seis.':
        'A bar of two or three carries only one, on the one. Compound metres — '
        'six-eight, nine-eight — are accented every three eighth notes, and that '
        'is why a six-eight is two beats and not six.',
    'Un coral es un himno luterano armonizado a cuatro voces. Escribió más de trescientos, y son el material con el que se sigue enseñando armonía hoy, casi trescientos años después: media carrera de música es, literalmente, ingeniería inversa de estos trescientos setenta y un ejercicios.':
        'A chorale is a Lutheran hymn harmonized in four voices. He wrote more '
        'than three hundred, and they are still the material harmony is taught '
        'with today, almost three hundred years later: half a music degree is, '
        'literally, reverse engineering these three hundred and seventy-one '
        'exercises.',
    'Un estándar es una canción que todos los músicos de jazz saben de memoria y que ninguno toca igual. No son canciones de jazz: casi todas venían de comedias musicales y de películas de los años veinte y treinta.':
        'A standard is a song every jazz musician knows by heart and no two play '
        'the same. They are not jazz songs: almost all of them came from musicals '
        'and films of the twenties and thirties.',
    'Un la de orquesta son 440 empujones por segundo. La octava de arriba, 880: el doble, exacto. Ésa es la única relación que el oído humano no escucha como otra nota sino como la misma más arriba, y no hay ninguna cultura conocida que no la use.':
        'An orchestral A is 440 pushes a second. The octave above, 880: exactly '
        'double. That is the only relation the human ear hears not as another '
        'note but as the same one higher up, and there is no known culture that '
        'does not use it.',
    'Un parlante no sabe nada de cuerdas. Lo único que hace es empujar y volver, y alguien tiene que decirle cuánto empujar en cada instante. Eso es una lista de números.':
        'A speaker knows nothing about strings. All it does is push and come '
        'back, and somebody has to tell it how hard to push at each instant. That '
        'is a list of numbers.',
    'Un sonido con una altura definida. Las notas se llaman con siete nombres que se repiten en ciclo: do re mi fa sol la si, y de vuelta do. En cifrado americano —el que usa este programa— esos siete nombres son letras: C D E F G A B, empezando por do = C.':
        'A sound with a definite pitch. Notes go by seven names that repeat in a '
        'cycle: C D E F G A B, and back to C. In this program those seven names '
        'are the letters themselves, starting from C.',
    'Un violín y una flauta tocando el mismo la dan la misma frecuencia fundamental —440 hercios los dos— y sin embargo no se confunden ni por un instante. Lo único que los separa es **con cuánta fuerza suena cada armónico**.':
        'A violin and a flute playing the same A give the same fundamental '
        'frequency — 440 hertz, both of them — and yet they are not confused for '
        'an instant. The only thing that separates them is **how loudly each '
        'harmonic sounds**.',
    'Una cadena de quintas descendentes con todos los acordes mayorizados: cada uno se vuelve la dominante del siguiente y resuelve en él, ocho acordes seguidos hasta volver a casa. En la menor: Am - D - G - C - F - B - E - Am.':
        'A chain of descending fifths with all the chords made major: each one '
        'becomes the dominant of the next and resolves onto it, eight chords in a '
        'row until it comes home. In A minor: Am - D - G - C - F - B - E - Am.',
    'Una cadencia es la manera de terminar una frase: el gesto que dice «hasta acá». Todas las que el programa sabe reconocer están acá, con la receta para que aparezcan. Cuando encuentra una en tu pieza, la marca con una estrella en la pantalla de resultados.':
        'A cadence is the way of ending a phrase: the gesture that says “this '
        'far”. Every one the program can recognize is here, with the recipe for '
        'making it turn up. When it finds one in your piece, it marks it with a '
        'star on the results screen.',
    'Una cuerda pulsada vibra entera, sí. Pero al mismo tiempo vibra en dos mitades, y en tres tercios, y en cuatro cuartos, y así hasta donde el material aguante. Cada una de esas divisiones produce su propio sonido, y todos suenan juntos desde el primer instante.':
        'A plucked string vibrates whole, yes. But at the same time it vibrates '
        'in two halves, and in three thirds, and in four quarters, and so on as '
        'far as the material will bear. Each of those divisions produces its own '
        'sound, and they all sound together from the first instant.',
    'Una flauta en el la3: casi toda la energía en la fundamental. Aproximado, pero la forma es ésa.':
        'A flute on A3: almost all the energy in the fundamental. Approximate, '
        'but that is the shape of it.',
    'Una modulación necesita espacio: hace falta tiempo para instalar la tonalidad nueva y volver. Por eso el programa la pide a partir de cierta cantidad de compases y no la intenta en piezas cortas.':
        'A modulation needs room: it takes time to settle the new key and come '
        'back. That is why the program only asks for it above a certain number of '
        'measures and does not attempt it in short pieces.',
    'Una pieza limpia': 'A clean piece',
    'Una progresión no es una lista cualquiera de acordes. Hay una gravedad: algunos acordes son reposo, otros son tensión, y la música es el viaje entre unos y otros.':
        'A progression is not just any list of chords. There is a gravity: some '
        'chords are rest, others are tension, and the music is the journey '
        'between them.',
    'Una tonalidad es un conjunto de siete notas —la escala— y una de ellas manda: la tónica. En do mayor la escala es do re mi fa sol la si, y la tónica es do. Todo lo que pase se escucha en relación a ese do.':
        'A key is a set of seven notes — the scale — and one of them is in '
        'charge: the tonic. In C major the scale is C D E F G A B, and the tonic '
        'is C. Everything that happens is heard in relation to that C.',
    'Una tonalidad mayor y la menor que comparte su tónica son vecinas: do mayor y do menor. Se pueden pedir acordes prestados de una a la otra sin cambiar de tonalidad.':
        'A major key and the minor that shares its tonic are neighbours: C major '
        'and C minor. Chords can be borrowed from one to the other without '
        'changing key.',
    'Una voz es una línea: una sola nota por vez, de principio a fin, como la cantaría una persona. Cuando escribís «C Am F G» estás diciendo qué notas suenan juntas, pero no estás diciendo quién canta cuál.':
        'A voice is a line: one note at a time, from beginning to end, the way a '
        'person would sing it. When you write “C Am F G” you are saying which '
        'notes sound together, but you are not saying who sings which.',
    'Una voz que salta mucho es difícil de cantar y difícil de seguir. El programa castiga los saltos grandes y, cuando aparece uno, prefiere que la nota siguiente vuelva en dirección contraria: es la manera de que un salto suene intencional y no como un error.':
        'A voice that leaps a lot is hard to sing and hard to follow. The program '
        'penalizes big leaps and, when one appears, prefers the next note to come '
        'back in the opposite direction: that is how a leap comes to sound '
        'intentional rather than like a mistake.',
    'Varias notas sonando juntas. El acorde básico es la tríada: una nota de base —la fundamental—, la que está una tercera más arriba, y la que está una quinta más arriba. Do-mi-sol es el acorde de do mayor, y se escribe C.':
        'Several notes sounding together. The basic chord is the triad: a base '
        'note — the root — the one a third above it, and the one a fifth above '
        'it. C-E-G is the C major chord, and it is written C.',
    'Vino cuando el experimentador ya llevaba tres sonidos distintos armados. No se lo vio entrar y no se presentó: estaba, de espaldas a una pantalla que no se veía, y de él no se distinguía más que el contorno.':
        'He came when the workbench had already built three different sounds. '
        'Nobody saw him come in and he did not introduce himself: he was there, '
        'with his back to a screen that could not be seen, and nothing of him '
        'could be made out but the outline.',
    'Vino cuando el quinto trabajo estuvo terminado, y no dijo cómo había entrado. Aplaudió tres veces, despacio, como quien corrige un examen y encuentra algo que no esperaba.':
        'He came when the fifth work was finished, and did not say how he had got '
        'in. He clapped three times, slowly, like someone marking an exam and '
        'finding something they did not expect.',
    'Vivaldi lo usó tanto que se le quedó pegado el nombre, pero el recurso es anterior a él y le sobrevivió por siglos.':
        'Vivaldi used it so much that the name stuck to him, but the device is '
        'older than he is and outlived him by centuries.',
    'Volvió apenas se encendió el modo coral, y esta vez no aplaudió nadie: golpeó una vez la mesa, como quien pide silencio antes de que entre el coro.':
        'He came back the moment chorale mode was switched on, and this time '
        'nobody clapped: he knocked once on the table, like someone calling for '
        'silence before the choir comes in.',
    'Voz y conducción de voces': 'Voice and voice leading',
    'Y a veces se te aparecen dos veces.':
        'And sometimes they appear to you twice.',
    'Y cada voz tiene un rango: el bajo no llega a las notas del soprano ni al revés. Eso no se negocia nunca: una solución que se salga del rango se descarta entera.':
        'And every voice has a range: the bass cannot reach the soprano’s notes '
        'or the other way round. That is never negotiable: a solution that goes '
        'outside the range is thrown out entirely.',
    'Y explican también algo de este programa. Todo lo que suena acá —el botón «Escuchar», la lluvia, el clavecín, los pasos— son listas de números escritas a mano, sin ninguna librería de audio en el medio. Cuando el experimentador te deja aislar un armónico y oírlo solo, lo que está haciendo es exactamente lo que hace un sintetizador: calcular un seno, sumarlo a los otros y entregar la lista.':
        'And they also explain something about this program. Everything that '
        'sounds here — the “Play” button, the rain, the harpsichord, the '
        'footsteps — is lists of numbers written by hand, with no audio library '
        'in between. When the workbench lets you solo a harmonic and hear it on '
        'its own, what it is doing is exactly what a synthesizer does: work out a '
        'sine, add it to the others and hand over the list.',
    'Y las paralelas dejaron de importar, no por rebeldía sino por acústica: con acordes tan densos el efecto que la regla trataba de evitar ya no se escucha.':
        'And parallels stopped mattering, not out of rebellion but out of '
        'acoustics: with chords that dense, the effect the rule was trying to '
        'avoid can no longer be heard.',
    'Y lo último que dijo, que es lo único que no era información: **la música es física, la física es aritmética, y la aritmética la puede hacer cualquiera que tenga ganas de sentarse un rato.**':
        'And the last thing he said, which is the only part that was not '
        'information: **music is physics, physics is arithmetic, and the '
        'arithmetic can be done by anyone willing to sit down for a while.**',
    'Y sigue sin haber dependencias: los archivos compilados son opcionales. Si no están, el programa levanta los de Python y hace lo mismo, más despacio. Nada de lo que leíste en los otros capítulos depende de que existan.':
        'And there are still no dependencies: the compiled files are optional. If '
        'they are not there, the program picks up the Python ones and does the '
        'same thing, more slowly. Nothing you have read in the other chapters '
        'depends on their existing.',
    'Y una tercera, que es la que termina de contarlo.':
        'And a third, which is the one that finishes telling it.',
    'de paso': 'passing',
    'do♯ del piano': 'the piano’s C♯',
    'i - bVII - bVI - V. El bajo baja por la escala menor natural y llega a la dominante desde un semitono por encima. Ese descenso de semitono al final es lo que le da el nombre y el color: es la marca del modo frigio.':
        'i - bVII - bVI - V. The bass walks down the natural minor scale and '
        'reaches the dominant from a semitone above. That semitone descent at the '
        'end is what gives it its name and its color: it is the mark of the '
        'phrygian mode.',
    'sol del piano': 'the piano’s G',
    '«Jazz» no es un género: es una familia de géneros que se llevan mal entre sí. Vale la pena saber cuál es cuál, porque suenan a cosas distintas.':
        '“Jazz” is not a genre: it is a family of genres that do not get along '
        'with each other. It is worth knowing which is which, because they sound '
        'like different things.',
    'Ésta es la decisión central, y el programa la toma con un orden de preferencias muy corto. Lo que importa es **qué lugar ocupa la nota de la melodía dentro del acorde**.':
        'This is the central decision, and the program makes it with a very short '
        'order of preference. What matters is **what place the melody note '
        'occupies inside the chord**.',
}
