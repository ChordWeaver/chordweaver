# -*- coding: utf-8 -*-
"""
El libro de teoría: contenido, nada más.

Este módulo es texto. No sabe dibujar y no importa nada --- ni del proyecto
ni de fuera de la biblioteca estándar. La interfaz lo lee y lo pinta; el
resto del motor no lo usa nunca. Las llaves de desbloqueo son claves de
logro, pero acá figuran como cadenas sueltas: preguntar si el usuario las
tiene es trabajo de quien llama.

Cómo se desbloquea
------------------
Una entrada con ``locked_by`` vacío está siempre escrita. Una con
``locked_by`` no aparece hasta que el usuario consiguió ese logro. Es a
propósito que la llave sea un logro y no un contador propio: el programa ya
detecta esos hechos, ya los persiste en ``achievements.json`` y ya los
muestra en su pantalla, así que el libro se llena solo a medida que el
usuario se topa con las cosas, sin ningún registro nuevo que mantener
sincronizado.

El tono
-------
Está escrito para alguien que no estudió música. Nada se da por sabido: la
primera vez que aparece una palabra se explica, y los ejemplos son siempre
concretos y en do mayor o la menor, que son las tonalidades sin alteraciones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class Figure:
    """
    Un pentagrama de ejemplo, descrito en grados y no en píxeles.

    Cada voz es una lista de posiciones sobre el pentagrama de sol: 0 es la
    línea de abajo (mi4), 1 el espacio siguiente (fa4), y así hacia arriba.
    Por debajo de 0 y por encima de 8 la interfaz agrega líneas adicionales
    sola. ``None`` en una posición deja el hueco vacío.

    Se describe así, y no con notas de verdad, porque estas figuras no son
    música: son dibujos de dos o tres notas para señalar una idea. Meter el
    parser de cifrado en el medio sería pedirle al motor que trabaje para
    ilustrar un párrafo.
    """

    caption: str = ""
    #: De grave a agudo, una lista de posiciones por voz.
    voices: Tuple[Tuple[Optional[int], ...], ...] = ()
    #: Un rótulo debajo de cada columna. Puede estar vacío.
    marks: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Entry:
    """Un apartado del libro."""

    key: str
    heading: str
    paragraphs: Tuple[str, ...]
    #: Recuadro de "cómo conseguirlo" al pie del apartado.
    recipe: str = ""
    #: Clave de logro que hay que tener para que esto esté escrito.
    locked_by: str = ""
    #: Qué se ve mientras siga cerrado. No revela el texto, sí el camino.
    hint: str = ""
    #: Pentagramas de ejemplo, después de los párrafos.
    figures: Tuple[Figure, ...] = ()
    #: Un apartado que se escribe con oro: no se estudia, se le aparece a
    #: uno. Se muestra como un legendario --- título en dorado, y ``? ? ?``
    #: en vez del título mientras siga cerrado --- igual que los del
    #: sendero, que lo son por su prefijo y no por esta bandera.
    legendary: bool = False


@dataclass(frozen=True)
class Chapter:
    numeral: str
    title: str
    blurb: str
    entries: Tuple[Entry, ...]


# ---------------------------------------------------------------------------
# I. Lo mínimo para entender el resto
# ---------------------------------------------------------------------------

_BASICS = Chapter(
    "I", "Lo mínimo para entender el resto",
    "Cinco palabras. Con estas cinco alcanza para leer todo lo demás y para "
    "entender qué está haciendo el programa cuando trabaja.",
    (
        Entry(
            "nota", "Nota",
            ("Un sonido con una altura definida. Las notas se llaman con "
             "siete nombres que se repiten en ciclo: do re mi fa sol la si, "
             "y de vuelta do. En cifrado americano —el que usa este "
             "programa— esos siete nombres son letras: C D E F G A B, "
             "empezando por do = C.",
             "Cuando el ciclo vuelve a empezar, la nota suena «la misma pero "
             "más aguda». A esa distancia se le dice octava. Por eso las "
             "notas llevan un número al lado: C4 es el do central de un "
             "piano, C5 es el do de arriba, C3 el de abajo. En los "
             "resultados vas a ver siempre notas escritas así.",
             "Entre dos notas vecinas hay un semitono, que es la distancia "
             "más chica que usa esta música: de una tecla del piano a la de "
             "al lado, contando las negras. Dos semitonos son un tono.")),
        Entry(
            "pentagrama", "El pentagrama",
            ("Cinco líneas y los cuatro espacios entre ellas. Cada línea y "
             "cada espacio es una nota, y se van alternando: si mi está en "
             "una línea, fa está en el espacio de arriba, sol en la línea "
             "siguiente, y así. Cuanto más arriba se escribe, más agudo "
             "suena.",
             "El signo del principio es la clave, y es lo que decide qué "
             "nota es cada línea. La clave de sol —la que se ve en el dibujo, "
             "y la que usa el pentagrama del Armonizador— pone el sol en la "
             "segunda línea desde abajo. De ahí sale todo lo demás: la línea "
             "de abajo es mi, el primer espacio fa, y así hacia arriba.",
             "Cuando una nota se va del pentagrama se le dibuja su propia "
             "rayita, la línea adicional. El do central —el do del medio del "
             "piano— cae justo una línea adicional por debajo de la clave de "
             "sol, y por eso es la referencia con la que todo el mundo se "
             "ubica.",
             "Al lado de la clave puede haber sostenidos o bemoles: es la "
             "armadura, y dice qué notas van alteradas en toda la pieza. Y "
             "después van dos números, uno sobre otro: el compás, que dice "
             "cómo se agrupan los tiempos. En 4/4 hay cuatro negras por "
             "compás."),
            figures=(
                Figure(
                    caption="La clave de sol y las notas de las cinco líneas "
                            "y los cuatro espacios. La primera, con su línea "
                            "adicional, es el do central.",
                    voices=((-2, 0, 1, 2, 3, 4, 5, 6, 7, 8),),
                    marks=("do4", "mi4", "fa4", "sol4", "la4", "si4",
                           "do5", "re5", "mi5", "fa5"),
                ),
            )),
        Entry(
            "intervalo", "Intervalo",
            ("La distancia entre dos notas. Se cuenta en nombres, no en "
             "semitonos: de do a mi hay una tercera (do, re, mi: tres "
             "nombres), de do a sol una quinta, de do a do una octava.",
             "Hay intervalos que suenan estables y redondos —la octava, la "
             "quinta, la tercera, la sexta— y otros que suenan tensos y "
             "piden movimiento —la segunda, la séptima, y sobre todo el "
             "tritono, que son tres tonos justos, de fa a si. Casi todas "
             "las reglas de este programa se reducen a administrar esa "
             "tensión: dónde se permite, cuánto dura y hacia dónde "
             "resuelve.")),
        Entry(
            "acorde", "Acorde",
            ("Varias notas sonando juntas. El acorde básico es la tríada: "
             "una nota de base —la fundamental—, la que está una tercera "
             "más arriba, y la que está una quinta más arriba. Do-mi-sol es "
             "el acorde de do mayor, y se escribe C.",
             "Si la tercera está un semitono más abajo el acorde es menor y "
             "suena más oscuro: do-mi bemol-sol es do menor, Cm. Toda la "
             "diferencia entre «alegre» y «triste» en esta música está en "
             "esa única nota.",
             "El cifrado americano es taquigrafía para esto. C es do mayor, "
             "Am es la menor, G7 es sol con una séptima agregada, F#m7b5 es "
             "fa sostenido menor con séptima y la quinta rebajada. Lo que "
             "va antes del paréntesis mental es la fundamental; todo lo que "
             "sigue describe qué se le apila encima.")),
        Entry(
            "voz", "Voz y conducción de voces",
            ("Una voz es una línea: una sola nota por vez, de principio a "
             "fin, como la cantaría una persona. Cuando escribís «C Am F "
             "G» estás diciendo qué notas suenan juntas, pero no estás "
             "diciendo quién canta cuál.",
             "Ahí es donde trabaja este programa. Los acordes los ponés vos "
             "(o los inventa él, según el modo); lo que decide el algoritmo "
             "es qué nota del acorde canta cada voz y en qué octava, de "
             "manera que cada línea se mueva lo menos posible y que las "
             "líneas no choquen entre sí. Eso es la conducción de voces, y "
             "es el oficio entero de este programa.",
             "La regla de oro es sencilla: cuanto menos se mueve cada voz, "
             "mejor. Si dos acordes seguidos comparten una nota, lo natural "
             "es que la voz que la tenía se quede quieta. Todo lo demás son "
             "matices sobre esa idea.")),
    ),
)


# ---------------------------------------------------------------------------
# II. La tonalidad
# ---------------------------------------------------------------------------

_HARMONY = Chapter(
    "II", "La tonalidad: por qué unos acordes siguen a otros",
    "Una progresión no es una lista cualquiera de acordes. Hay una "
    "gravedad: algunos acordes son reposo, otros son tensión, y la música "
    "es el viaje entre unos y otros.",
    (
        Entry(
            "escala", "La escala y los grados",
            ("Una tonalidad es un conjunto de siete notas —la escala— y una "
             "de ellas manda: la tónica. En do mayor la escala es do re mi "
             "fa sol la si, y la tónica es do. Todo lo que pase se escucha "
             "en relación a ese do.",
             "Sobre cada nota de la escala se puede armar un acorde usando "
             "sólo notas de la escala. Salen siete acordes, y se numeran con "
             "números romanos: I, ii, iii, IV, V, vi, vii°. En do mayor eso "
             "es C, Dm, Em, F, G, Am y Bdim. Mayúscula significa mayor y "
             "minúscula menor; el «°» es disminuido.",
             "Los números romanos son útiles porque son los mismos en "
             "cualquier tonalidad. Un «V - I» es lo mismo en do que en fa "
             "sostenido; sólo cambian las letras. En la pantalla de "
             "resultados vas a ver el número romano debajo de cada acorde: "
             "eso te dice qué papel cumple, no sólo cómo se llama.")),
        Entry(
            "funciones", "Las tres funciones",
            ("De los siete grados, tres papeles alcanzan para entender casi "
             "todo:",
             "**Tónica (I, y de refilón vi y iii).** Es la casa. Cuando la "
             "música llega ahí, descansa.",
             "**Subdominante (IV y ii).** Es salir de casa. No hay tensión "
             "todavía, pero ya no estás en reposo.",
             "**Dominante (V, y vii°).** Es la tensión máxima. El V contiene "
             "la nota que está un semitono por debajo de la tónica —la "
             "sensible— y esa nota tira hacia arriba con una fuerza que se "
             "escucha físicamente. Por eso V casi siempre va a I.",
             "El recorrido típico es ese: casa → salgo → tensión → vuelvo. "
             "I - IV - V - I, o con más vuelta, I - vi - ii - V - I. Si "
             "escuchás cualquier canción popular vas a encontrar ese "
             "esqueleto abajo de casi todo.")),
        Entry(
            "septima", "Las séptimas",
            ("A una tríada se le puede apilar una nota más, la séptima. G "
             "se convierte en G7, y el acorde deja de ser un lugar donde "
             "quedarse: la séptima es un intervalo tenso y pide resolver.",
             "Un G7 quiere ir a C mucho más que un G a secas. Por eso el "
             "acorde de séptima es la herramienta principal para empujar la "
             "música hacia adelante, y por eso el jazz los usa "
             "prácticamente en todos lados: en ese estilo lo raro es la "
             "tríada, no la séptima.",
             "Cuando el programa arma un acorde de séptima, se ocupa además "
             "de que esa séptima resuelva bajando un grado. Es la regla que "
             "hace que el acorde suene resuelto y no abandonado."),
            locked_by="seventh_chord",
            hint="Se escribe sola cuando uses un acorde de séptima."),
        Entry(
            "disminuido", "El acorde disminuido",
            ("Un acorde disminuido apila dos terceras menores: si-re-fa. "
             "Adentro tiene un tritono —esa distancia inestable de tres "
             "tonos— y por eso no se sostiene solo: es puro tránsito.",
             "El vii° cumple la misma función que el V y suele reemplazarlo "
             "o precederlo. En el jazz aparece además el medio disminuido "
             "(m7b5), que es el ii de las tonalidades menores: el «F#m7b5» "
             "que aparece a veces en los resultados es exactamente eso.",
             "Es el acorde más oscuro del catálogo y el que más rápido "
             "cansa si se abusa. Sirve para pasar, no para quedarse."),
            locked_by="diminished_chord",
            hint="Se escribe sola cuando escribas un acorde disminuido."),
        Entry(
            "extendido", "Novenas, oncenas y el color",
            ("Después de la séptima se puede seguir apilando: novena, "
             "oncena, trecena. Esas notas ya no cambian la función del "
             "acorde —un C9 sigue siendo la tónica— pero le cambian el "
             "color, lo vuelven más denso y más moderno.",
             "En este programa eso se controla con el dial «Cuánto color». "
             "Abajo del todo, el programa duplica notas del acorde cuando "
             "le sobran voces. A medida que subís, en vez de duplicar "
             "prefiere agregar una sexta, y más arriba también novenas y "
             "oncenas.",
             "Hay un motivo para no ponerlo al máximo siempre: si todos los "
             "acordes llevan color, el color deja de escucharse. Funciona "
             "por contraste."),
            recipe="Organizador o Generador · pantalla de reglas · dial "
                   "«Cuánto color». Hasta un tercio de la barra sólo agrega "
                   "sextas, que es el color más suave.",
            locked_by="extended_chord",
            hint="Se escribe sola cuando armes un acorde con séptima, novena "
                 "y oncena a la vez."),
        Entry(
            "prestamo", "Préstamos e intercambio modal",
            ("Una tonalidad mayor y la menor que comparte su tónica son "
             "vecinas: do mayor y do menor. Se pueden pedir acordes "
             "prestados de una a la otra sin cambiar de tonalidad.",
             "El préstamo más común es el cuarto grado menor: en do mayor, "
             "usar Fm en lugar de F. Es un acorde que suena "
             "inmediatamente melancólico y aparece en muchísima música "
             "popular justo antes del final. Otro es el séptimo rebajado "
             "(bVII), que suena a rock antes que a clásico.",
             "El programa lo llama «intercambio modal» y lo tenés como "
             "casilla en el Armonizador y como dial en el Generador."),
            recipe="Generador · pantalla de Tonalidad · subí «acordes "
                   "prestados». En el Armonizador es la casilla «Permitir "
                   "intercambios modales».",
            locked_by="modal_interchange",
            hint="Se escribe sola cuando uses tu primer acorde prestado."),
        Entry(
            "modulacion", "Modulación",
            ("Modular es cambiar de tonalidad en el medio de la pieza: la "
             "gravedad se muda a otra nota y el oído la sigue. No es lo "
             "mismo que un préstamo, que era una visita corta sin cambiar "
             "de casa.",
             "Los destinos naturales son los parientes cercanos: la "
             "dominante (subir una quinta), la subdominante (bajar una "
             "quinta) y el relativo menor. El programa marca en violeta los "
             "acordes que están de visita en otra tonalidad, así se ve de "
             "un vistazo por dónde viajó la pieza.",
             "Una modulación necesita espacio: hace falta tiempo para "
             "instalar la tonalidad nueva y volver. Por eso el programa la "
             "pide a partir de cierta cantidad de compases y no la intenta "
             "en piezas cortas."),
            recipe="Generador · pantalla de Tonalidad · activá la modulación "
                   "y usá al menos ocho compases. Con pocos compases no "
                   "entra, por más que esté activada.",
            locked_by="modulation",
            hint="Se escribe sola con tu primera modulación en el Generador."),
        Entry(
            "modos", "Los modos",
            ("Si tomás las siete notas de do mayor pero hacés que mande el "
             "re en vez del do, la escala es la misma y el resultado suena "
             "distinto. Eso es un modo. El jónico es el mayor de toda la "
             "vida y el eólico es el menor; los otros —dórico, frigio, "
             "lidio, mixolidio— tienen colores propios.",
             "El dórico es un menor con la sexta alta: suena menos triste, "
             "más abierto. El frigio tiene la segunda baja y suena español. "
             "El lidio tiene la cuarta alta y suena flotante. El mixolidio "
             "es un mayor con la séptima baja, y es el modo del blues y del "
             "rock.",
             "Antes de que existiera la tonalidad como la conocemos, la "
             "música se escribía así. Por eso el estilo gregoriano de este "
             "programa trabaja en modos y no en mayor/menor."),
            recipe="Generador · pantalla de Tonalidad · el menú de modo, al "
                   "lado de la tónica.",
            locked_by="exotic_mode",
            hint="Se escribe sola cuando hagas una pieza en un modo que no "
                 "sea el jónico ni el eólico."),
    ),
)


# ---------------------------------------------------------------------------
# III. Cómo se mueven las voces
# ---------------------------------------------------------------------------

_COUNTERPOINT = Chapter(
    "III", "Cómo se mueven las voces",
    "Acá está el corazón del programa. Todas las reglas que podés prender "
    "y apagar en la pantalla de reglas son formas de contestar una sola "
    "pregunta: ¿cómo pasan las voces de un acorde al siguiente?",
    (
        Entry(
            "movimientos", "Los cuatro movimientos",
            ("Tomá dos voces cualesquiera y mirá qué hacen entre un acorde "
             "y el siguiente. Sólo hay cuatro posibilidades:",
             "**Contrario** — una sube y la otra baja. Es el mejor de los "
             "cuatro: las dos líneas se escuchan como líneas independientes, "
             "que es de lo que se trata escribir a varias voces.",
             "**Oblicuo** — una se queda quieta y la otra se mueve. Casi tan "
             "bueno como el contrario, y gratis: la que no se mueve no "
             "gasta nada.",
             "**Directo** — las dos se mueven para el mismo lado, pero "
             "distinta distancia. Aceptable.",
             "**Paralelo** — las dos se mueven para el mismo lado la misma "
             "distancia, manteniendo el intervalo. Acá empiezan los "
             "problemas.",
             "El programa cuenta cuánto movimiento contrario hay y lo "
             "premia. No es un capricho estético: es lo que hace que cuatro "
             "voces suenen como cuatro personas y no como un acordeón."),
            figures=(
                Figure(caption="Contrario: una sube, la otra baja.",
                       voices=((0, 2), (7, 5))),
                Figure(caption="Oblicuo: una se queda, la otra se mueve.",
                       voices=((0, 0), (4, 6))),
                Figure(caption="Directo: las dos para el mismo lado, "
                               "distinta distancia.",
                       voices=((0, 1), (4, 7))),
                Figure(caption="Paralelo: las dos para el mismo lado, la "
                               "misma distancia. El intervalo no cambia.",
                       voices=((0, 2), (4, 6))),
            )),
        Entry(
            "paralelas", "Quintas y octavas paralelas",
            ("Si dos voces están a una quinta de distancia y las dos suben "
             "un tono, siguen estando a una quinta. Eso es una quinta "
             "paralela, y es la prohibición más famosa de toda la música "
             "occidental.",
             "El motivo es acústico, no moral. La quinta y la octava son "
             "los intervalos más «vacíos», los que más se funden. Cuando dos "
             "voces se mueven en paralelo a esa distancia, el oído deja de "
             "escuchar dos voces y escucha una sola con un timbre raro. Se "
             "pierde justo lo que se estaba tratando de construir.",
             "Por eso en el estilo barroco están prohibidas de plano: una "
             "solución que las tenga se descarta entera, no importa lo bien "
             "que esté todo lo demás. En el gregoriano, en cambio, están "
             "permitidas, porque el organum medieval se basa justamente en "
             "ellas. Y en el jazz se toleran porque los acordes son tan "
             "densos que el efecto no llega a escucharse.",
             "Las quintas directas —cuando las dos voces llegan a una "
             "quinta moviéndose para el mismo lado, aunque antes no lo "
             "estuvieran— son un caso más leve: el programa las penaliza en "
             "vez de prohibirlas."),
            recipe="Pantalla de reglas · «Prohibir quintas paralelas» y "
                   "«Prohibir octavas paralelas». Vienen prendidas en "
                   "Barroco y apagadas en Gregoriano.",
            figures=(
                Figure(caption="Mi–si es una quinta. Las dos voces suben un "
                               "grado y fa–do vuelve a ser una quinta: eso "
                               "es una quinta paralela.",
                       voices=((0, 1), (4, 5)),
                       marks=("5ª", "5ª")),
                Figure(caption="La misma subida con la voz de arriba yendo "
                               "al revés: el intervalo cambia y el problema "
                               "desaparece.",
                       voices=((0, 1), (4, 2)),
                       marks=("5ª", "2ª")),
            )),
        Entry(
            "sin_paralelas", "Una pieza limpia",
            ("Terminar una pieza a cuatro voces sin una sola quinta "
             "paralela parece poca cosa cuando lo hace una computadora en "
             "dos segundos. A mano es el ejercicio con el que se pasan "
             "meses los estudiantes de armonía.",
             "El truco que usa el programa es el mismo que usaría una "
             "persona: cuando dos voces amenazan con caer en paralelo, "
             "mover una de las dos en dirección contraria, o dejarla quieta "
             "si el acorde siguiente comparte esa nota. La diferencia es "
             "que el algoritmo puede probar miles de repartos por segundo y "
             "quedarse con el que menos cuesta."),
            locked_by="no_parallel_fifths",
            hint="Se escribe sola cuando completes una pieza sin quintas "
                 "paralelas."),
        Entry(
            "quinta_paralela", "Cuando la dejás pasar",
            ("Apagar la regla y escuchar el resultado es la mejor manera de "
             "entender por qué existe. Buscá el momento donde dos voces "
             "suben juntas: vas a oír cómo por un instante se funden en un "
             "solo sonido y la textura se aplana.",
             "Nada de esto es ilegal. Debussy escribió quintas paralelas a "
             "propósito durante toda su vida, y el rock vive de ellas. La "
             "regla describe un estilo, no una ley de la física."),
            locked_by="parallel_fifth",
            hint="Se escribe sola la primera vez que dejes pasar una quinta "
                 "paralela."),
        Entry(
            "saltos", "Saltos, cruces y espaciado",
            ("Una voz que salta mucho es difícil de cantar y difícil de "
             "seguir. El programa castiga los saltos grandes y, cuando "
             "aparece uno, prefiere que la nota siguiente vuelva en "
             "dirección contraria: es la manera de que un salto suene "
             "intencional y no como un error.",
             "Dos voces se cruzan cuando la de abajo pasa a estar por "
             "encima de la de arriba. Se escucha confuso y por eso está "
             "prohibido por defecto, aunque lo podés permitir.",
             "El espaciado es la distancia entre voces vecinas. Lo normal "
             "es que las voces agudas estén juntas y el bajo más separado, "
             "como en un acorde de piano: la mano derecha cerrada y la "
             "izquierda lejos. Si se abren todas por igual, el acorde suena "
             "hueco.",
             "Y cada voz tiene un rango: el bajo no llega a las notas del "
             "soprano ni al revés. Eso no se negocia nunca: una solución "
             "que se salga del rango se descarta entera.")),
        Entry(
            "paso", "Notas de paso",
            ("Si una voz salta una tercera —de do a mi— queda un hueco: el "
             "re. Meter ese re en el medio, breve, convierte el salto en "
             "tres notas seguidas por grado conjunto y suaviza la línea.",
             "Eso es una nota de paso, y es el adorno más elemental que "
             "existe. No cambia la armonía: es puro tránsito, y por eso el "
             "programa las agrega después de la búsqueda y no durante.",
             "El bajo queda fuera a propósito: un adorno ahí abajo enturbia "
             "la armonía en vez de decorarla."),
            recipe="Generador · pantalla de Tonalidad · sección «Notas de "
                   "paso», elegí qué voces pueden usarlas. En el "
                   "Organizador es la casilla «Agregar notas de adorno».",
            locked_by="passing_notes",
            hint="Se escribe sola cuando generes tus primeras notas de "
                 "paso."),
    ),
)


# ---------------------------------------------------------------------------
# IV. Los estilos
# ---------------------------------------------------------------------------

_STYLES = Chapter(
    "IV", "Los tres estilos",
    "El estilo no toca los acordes. Lo que cambia es qué se prohíbe, qué "
    "se premia y con cuánta fuerza: la misma progresión escrita en dos "
    "estilos distintos da dos piezas distintas.",
    (
        Entry(
            "barroco", "Barroco",
            ("Es el contrapunto de la práctica común: el lenguaje de Bach, "
             "Haendel y todo lo que vino después hasta bien entrado el siglo "
             "XIX. Es el más reglado de los tres.",
             "Prohíbe quintas y octavas paralelas, premia el movimiento "
             "contrario, castiga los saltos de tritono y de séptima, y "
             "vigila que las voces no se crucen. Si nunca escribiste "
             "armonía, empezá acá: es el estilo donde las reglas están más "
             "claras y donde más se nota cuando algo está mal.",
             "Adentro del barroco hay un interruptor, «Modo coral», que lo "
             "aprieta todavía más. Es el estilo de los corales de Bach: "
             "nunca duplica la sensible, exige que las séptimas resuelvan "
             "hacia abajo, salta menos y no tolera el solapamiento de "
             "voces. Escribe más ceñido y se mueve menos libremente."),
            recipe="El «Modo coral» está en la pantalla de reglas, abajo a "
                   "la derecha, y sólo aparece con el estilo Barroco "
                   "elegido."),
        Entry(
            "gregoriano", "Gregoriano",
            ("Escritura modal, anterior a la tonalidad. No hay acordes de "
             "séptima, no hay dominantes tirando hacia la tónica: hay "
             "líneas que se mueven casi siempre por grado conjunto, de una "
             "nota a la de al lado.",
             "Evita el tritono con una insistencia que a los medievales les "
             "valió el apodo de «diabolus in musica»: ni saltado por una "
             "voz ni sonando entre dos. En cambio tolera las quintas y "
             "octavas paralelas, porque el organum —la forma más antigua de "
             "cantar a varias voces— consiste literalmente en doblar la "
             "melodía en paralelo.",
             "La cadencia característica no es V-I sino la plagal, IV-I: "
             "el «amén» de los himnos.")),
        Entry(
            "organum", "El organum y la vox principalis",
            ("En el organum medieval hay una voz que lleva el canto —la vox "
             "principalis— y otra que la acompaña doblándola en paralelo a "
             "la cuarta, la quinta o la octava: la vox organalis.",
             "En este programa marcás cuál es la principalis en la pantalla "
             "de voces, y la voz que quede inmediatamente debajo se "
             "convierte en la organalis. No puede ser la voz más grave, "
             "justamente porque necesita a alguien debajo para acompañarla.",
             "Cambiarla cambia por completo la textura: la voz elegida se "
             "vuelve el centro y todo lo demás se acomoda alrededor."),
            recipe="Estilo Gregoriano + Organizador o Generador · pantalla "
                   "de Voces · el botón «vox principalis» de cada voz.",
            locked_by="principalis_changed",
            hint="Se escribe sola cuando cambies la vox principalis en el "
                 "estilo gregoriano."),
        Entry(
            "jazz", "Jazz",
            ("Acá lo que manda no es el bajo sino cómo se encadenan dos "
             "notas de cada acorde: la tercera y la séptima, que en la "
             "jerga son las guide tones. Son las que definen si un acorde "
             "es mayor, menor o dominante; el resto es relleno.",
             "El programa las conecta por grado conjunto de un acorde al "
             "siguiente, mantiene las notas que dos acordes comparten y "
             "evita las novenas menores, que es el único choque que el "
             "estilo no perdona. Las paralelas y los tritonos, en cambio, "
             "pasan sin problema.",
             "Las tríadas casi no existen: el acorde base del jazz es el de "
             "séptima, y de ahí para arriba.")),
        Entry(
            "seis_voces", "Más de cuatro voces",
            ("Cuatro voces —bajo, tenor, alto, soprano— es el estándar "
             "porque un acorde de séptima tiene exactamente cuatro notas y "
             "cada voz puede llevar una.",
             "Con cinco o seis voces empiezan a sobrar: alguna nota se "
             "duplica, o el programa agrega color en vez de duplicar, según "
             "cómo tengas el dial. Duplicar la fundamental o la quinta es "
             "seguro; duplicar la sensible es lo único que nunca conviene, "
             "porque son dos voces tirando al mismo lugar y una de las dos "
             "va a llegar mal."),
            recipe="Pantalla de Voces · marcá hasta seis. Los rangos de cada "
                   "cuerda son editables si tu grupo llega a más o a menos.",
            locked_by="six_voices",
            hint="Se escribe sola cuando escribas una pieza a seis voces."),
    ),
)


# ---------------------------------------------------------------------------
# V. Historia
# ---------------------------------------------------------------------------

_HISTORY = Chapter(
    "V", "De dónde viene cada estilo",
    "Los tres estilos que el programa conoce están separados por unos mil "
    "años. Cada uno se escribe acá la primera vez que lo usás, en cualquiera "
    "de los tres modos.",
    (
        Entry(
            "linea", "Mil años en un párrafo",
            ("Primero fue una sola línea cantada al unísono. Después alguien "
             "la dobló en paralelo y aparecieron dos voces. De ahí a que las "
             "voces se independizaran pasaron siglos, y de ahí a que la "
             "armonía —los acordes como entidad propia, con una gravedad "
             "que empuja de uno a otro— pasaron otros tantos.",
             "Lo que este programa hace es la parte técnica de esa historia: "
             "dadas unas notas que tienen que sonar juntas, decidir qué canta "
             "cada voz. Es exactamente el problema que se estudiaron todos "
             "los que aparecen en las páginas que siguen.")),
        Entry(
            "hist_gregorian", "El canto llano y el organum",
            ("Alrededor del año 800 la iglesia de occidente unificó su "
             "repertorio de cantos en un cuerpo único, que la leyenda le "
             "atribuyó al papa Gregorio Magno aunque él llevara dos siglos "
             "muerto. De ahí el nombre. Era música de una sola línea, sin "
             "acompañamiento y sin ritmo medido: la palabra manda, y la "
             "melodía la sigue.",
             "El primer paso hacia varias voces fue mecánico. Alguien "
             "cantaba la melodía y otro la doblaba, nota por nota, una "
             "cuarta o una quinta por debajo. Eso es el organum paralelo, y "
             "está documentado en el siglo IX. No hay independencia: la "
             "segunda voz es una sombra de la primera.",
             "Recién en los siglos XI y XII las dos voces empezaron a "
             "moverse por su cuenta, y en Notre Dame de París —con Léonin y "
             "Pérotin— aparecieron tres y cuatro voces con ritmo escrito. "
             "Ese es el momento en que nace el contrapunto.",
             "El tritono se ganó en esta época el apodo de «diabolus in "
             "musica». No era superstición: en un lenguaje sin dominantes ni "
             "resoluciones, un intervalo tan inestable no tiene adónde ir, y "
             "simplemente suena mal. Cuando la tonalidad le dio un destino, "
             "dejó de ser un problema y pasó a ser el motor."),
            locked_by="genre_gregorian",
            hint="Se escribe sola cuando hagas tu primera pieza gregoriana."),
        Entry(
            "hist_baroque", "El barroco y la práctica común",
            ("Entre 1600 y 1750 la música de occidente se ordena alrededor "
             "de una idea nueva: la tonalidad. Ya no hay ocho modos "
             "equivalentes, hay mayor y menor, y adentro de cada uno los "
             "acordes tienen jerarquía. Uno es la casa, otro es la tensión, "
             "y la música es el viaje entre los dos.",
             "El barroco escribe sobre bajo cifrado: se anota la línea del "
             "bajo con números debajo que dicen qué intervalos van encima, y "
             "el intérprete completa. Esa taquigrafía es la abuela directa "
             "del cifrado americano que usás en el Organizador, y la razón "
             "por la que el programa habla de intervalos «medidos desde el "
             "bajo».",
             "Bach es el final del período y su resumen. Sus corales —las "
             "armonizaciones a cuatro voces de melodías luteranas— son desde "
             "hace dos siglos el material con el que se enseña armonía, "
             "porque en cuatro compases hay más decisiones bien tomadas que "
             "en piezas veinte veces más largas. El «Modo coral» del programa "
             "es el intento de escribir como ellos.",
             "Las reglas que hoy se enseñan como leyes —no a quintas "
             "paralelas, la sensible sube, la séptima baja— no fueron "
             "inventadas por nadie: se destilaron después, mirando qué hacían "
             "estos compositores. Son una descripción, no un reglamento."),
            locked_by="genre_baroque",
            hint="Se escribe sola cuando hagas tu primera pieza barroca."),
        Entry(
            "hist_jazz", "El jazz",
            ("Nace en Nueva Orleans alrededor de 1900, del cruce entre el "
             "blues —que traía las notas «dobladas» de la música "
             "afroamericana—, el ragtime y las bandas de metales que la "
             "ciudad tenía por todas partes. Al principio la armonía era "
             "sencilla; lo nuevo era el ritmo y que se improvisara.",
             "En los años treinta el swing lo vuelve música de baile y de "
             "orquesta grande. En los cuarenta, el bebop lo da vuelta: "
             "tempos imposibles, melodías de una densidad nueva, y sobre "
             "todo una armonía mucho más rica. Charlie Parker y Dizzy "
             "Gillespie empiezan a apilar novenas y oncenas sobre los "
             "acordes, y a reemplazar dominantes por otros a distancia de "
             "tritono.",
             "El ii-V-I se vuelve la célula básica del lenguaje, hasta el "
             "punto de que un músico de jazz lee una progresión entera como "
             "una cadena de ii-V encadenados. De ahí también sale la "
             "obsesión con las guide tones: cuando los acordes tienen cinco "
             "o seis notas, lo único que hay que cuidar de verdad es cómo se "
             "encadenan la tercera y la séptima.",
             "Y las paralelas dejaron de importar, no por rebeldía sino por "
             "acústica: con acordes tan densos el efecto que la regla trataba "
             "de evitar ya no se escucha."),
            locked_by="genre_jazz",
            hint="Se escribe sola cuando hagas tu primera pieza de jazz."),
    ),
)


# ---------------------------------------------------------------------------
# VI. Cadencias y giros
# ---------------------------------------------------------------------------

_CADENCES = Chapter(
    "VI", "Cadencias y giros",
    "Una cadencia es la manera de terminar una frase: el gesto que dice "
    "«hasta acá». Todas las que el programa sabe reconocer están acá, con "
    "la receta para que aparezcan. Cuando encuentra una en tu pieza, la "
    "marca con una estrella en la pantalla de resultados.",
    (
        Entry(
            "autentica", "La cadencia auténtica: V - I",
            ("La más común de todas y la que define la tonalidad. El quinto "
             "grado contiene la sensible, esa nota a un semitono de la "
             "tónica, y cuando resuelve el oído siente que la frase cerró.",
             "En do mayor es G - C. Si le agregás la séptima al G, el "
             "efecto es más fuerte todavía: el G7 tiene adentro un tritono "
             "que sólo se resuelve de una manera.",
             "Casi todo lo demás de este capítulo son maneras de retrasar, "
             "adornar o esquivar este gesto.")),
        Entry(
            "six_four", "Cadencial 6/4",
            ("El truco de retrasar. Antes del V de verdad, se pone el mismo "
             "acorde pero con la quinta en el bajo. El oído escucha el bajo "
             "de la dominante y espera la resolución, pero arriba todavía "
             "están las notas de la tónica: la tensión se estira un tiempo "
             "más y después resuelve.",
             "Es la fórmula con la que se anuncian casi todos los finales "
             "grandes del repertorio clásico, y la que usa un concierto "
             "para avisar que viene la cadenza del solista."),
            recipe="Se reconoce sobre un V mayor que resuelve a la tónica, "
                   "cantado con la quinta en el bajo, la fundamental encima "
                   "y la tercera arriba. Cualquier cantidad de voces y "
                   "cualquiera de los tres modos; el barroco es el estilo "
                   "que lo busca.",
            locked_by="cadential_six_four",
            hint="Se escribe sola cuando escribas tu primer dominante 6/4."),
        Entry(
            "deceptive", "Cadencia rota",
            ("El V prepara la tónica y en el último momento cae en el sexto "
             "grado: en do mayor, G va a Am en vez de a C. La resolución se "
             "posterga y la frase, que parecía terminada, sigue.",
             "Es un recurso de continuidad: sirve para alargar una sección "
             "cuando ya estaba por cerrar. En la pantalla de resultados "
             "aparece marcada como «Cadencia rota».")),
        Entry(
            "plagal", "Cadencia plagal: IV - I",
            ("La subdominante cierra directamente sobre la tónica, sin "
             "pasar por la dominante. Es el «amén» de los himnos, y suena "
             "más blando y más antiguo que la auténtica, justamente porque "
             "le falta la sensible tirando.",
             "Si el cuarto grado se usa menor —iv en vez de IV— la cadencia "
             "se vuelve plagal menor y suena mucho más oscura. Es un "
             "recurso muy usado en música popular para el último acorde "
             "antes del final."),
            recipe="Estilo Gregoriano: es su cadencia natural y aparece "
                   "sola. El Generador con Gregoriano las produce en casi "
                   "todas las corridas.",
            locked_by="plagal",
            hint="Se escribe sola con tu primera cadencia plagal."),
        Entry(
            "two_five", "El ii - V - I",
            ("El giro que sostiene casi todo el repertorio de jazz. La "
             "subdominante prepara la dominante y ésta resuelve: en do, Dm7 "
             "- G7 - Cmaj7.",
             "Funciona tan bien porque las guide tones se mueven mínimo: la "
             "séptima de un acorde se vuelve la tercera del siguiente, y la "
             "tercera se vuelve la séptima. Dos notas alcanzan para llevar "
             "toda la progresión, y las voces casi no se mueven.",
             "El mismo giro se puede apuntar a cualquier grado, no sólo a "
             "la tónica: se toma prestada la dominante de donde se quiere "
             "ir y se aterriza ahí. Eso es un ii-V secundario, y es la "
             "manera de encadenar tonalidades sin modular del todo."),
            recipe="Estilo Jazz + Generador. Con cuatro compases o más "
                   "aparece en casi todas las corridas.",
            locked_by="two_five",
            hint="Se escribe sola con tu primer ii-V."),
        Entry(
            "tritone_sub", "Sustituto tritonal",
            ("Dos acordes de dominante que están a distancia de tritono "
             "comparten el mismo tritono adentro: G7 y Db7 tienen los dos "
             "el si y el fa. Como el tritono es lo que define la tensión, "
             "uno puede reemplazar al otro.",
             "El efecto es que el bajo, en vez de saltar una quinta, baja "
             "un semitono: Dm7 - Db7 - Cmaj7. Es uno de los sonidos más "
             "reconocibles del jazz moderno."),
            recipe="Estilo Jazz + Generador. Aparece cuando el programa "
                   "elige un subV en lugar del V.",
            locked_by=""),
        Entry(
            "bach_sixth", "La sexta en lugar de la quinta",
            ("Cuando dos voces amenazan con caer en quintas paralelas hay "
             "dos salidas: reordenar las voces, o escribir una de esas "
             "quintas como sexta. La segunda es más barata y no toca el "
             "resto de la textura.",
             "Es un recurso que Bach usa constantemente. El acorde pasa a "
             "llamarse «6omit5» —sexta con la quinta omitida— y en la "
             "pantalla de resultados aparece marcado.",
             "Es un buen ejemplo de que las reglas del contrapunto no son "
             "una jaula: son un problema, y la historia de la música está "
             "llena de maneras elegantes de resolverlo."),
            recipe="Barroco o Modo coral. Aparece por azar, así que puede "
                   "hacer falta generar varias veces.",
            locked_by="sixth_omit_five",
            hint="Se escribe sola cuando descubras el acorde de sexta con la "
                 "quinta omitida."),
        Entry(
            "phrygian", "Cadencia frigia",
            ("i - bVII - bVI - V. El bajo baja por la escala menor natural "
             "y llega a la dominante desde un semitono por encima. Ese "
             "descenso de semitono al final es lo que le da el nombre y el "
             "color: es la marca del modo frigio.",
             "Suena antigua y española a la vez. Es el esqueleto de la "
             "cadencia andaluza, la que se escucha en el flamenco y en "
             "media música popular del Mediterráneo.",
             "El programa la trata como una cita: no la construye "
             "gradualmente sino que la pone entera, tal cual, cuando se dan "
             "las condiciones."),
            recipe="Generador · estilo Barroco (o Modo coral) · tonalidad "
                   "MENOR · exactamente 2 compases en 4/4, que dan los 4 "
                   "acordes que la cadencia necesita. Aparece el 10% de las "
                   "veces; con «Elevar probabilidad de cadencias "
                   "especiales» en el engranaje de configuración, el 45%.",
            locked_by="set_piece_phrygian",
            hint="Se escribe sola cuando la descubras."),
        Entry(
            "vivaldi", "Ciclo de Vivaldi",
            ("Una cadena de quintas descendentes con todos los acordes "
             "mayorizados: cada uno se vuelve la dominante del siguiente y "
             "resuelve en él, ocho acordes seguidos hasta volver a casa. En "
             "la menor: Am - D - G - C - F - B - E - Am.",
             "Es el motor de medio barroco italiano y de una cantidad "
             "absurda de música posterior. La sensación es de caída "
             "continua, como una escalera que no termina.",
             "Vivaldi lo usó tanto que se le quedó pegado el nombre, pero "
             "el recurso es anterior a él y le sobrevivió por siglos."),
            recipe="Generador · estilo Barroco (o Modo coral) · tonalidad "
                   "MENOR · exactamente 4 compases en 4/4, que dan los 8 "
                   "acordes. Mismas probabilidades que la frigia.",
            locked_by="set_piece_vivaldi",
            hint="Se escribe sola cuando la descubras."),
        Entry(
            "chromatic", "Bajo cromático descendente",
            ("El acorde de tónica se sostiene mientras el bajo baja paso a "
             "paso por debajo. Las voces de arriba no se mueven: todo es "
             "movimiento oblicuo, y por eso la línea del bajo se escucha "
             "con una claridad que no tendría de otra manera.",
             "Es el lamento barroco por excelencia —el bajo de la «Dido» de "
             "Purcell, el «Crucifixus» de Bach— y sobrevivió intacto hasta "
             "el jazz y el rock. Si alguna vez escuchaste una balada donde "
             "el bajo baja de a un semitono mientras el acorde parece el "
             "mismo, era esto."),
            recipe="Generador · estilo Barroco o Jazz · tonalidad MENOR · "
                   "exactamente 3 compases en 4/4, que dan los 6 acordes. "
                   "No aparece en Modo coral.",
            locked_by="set_piece_chromatic",
            hint="Se escribe sola cuando la descubras."),
        Entry(
            "dominante_final", "Terminar en la dominante",
            ("No toda frase cierra. Terminar en el V deja la música "
             "colgada: es la semicadencia, y sirve para partir una idea "
             "larga en dos mitades, la primera de las cuales queda abierta.",
             "Es lo que hace que una melodía de ocho compases se sienta "
             "como pregunta y respuesta."),
            recipe="Generador · pantalla de Tonalidad · en «Termina en» "
                   "escribí V y ponelo en Obligatorio.",
            locked_by="ends_on_dominant",
            hint="Se escribe sola cuando hagas una pieza que termine en un "
                 "dominante."),
        Entry(
            "dominos", "Dominantes encadenados",
            ("Tres o más acordes de dominante seguidos, cada uno "
             "resolviendo en el siguiente que a su vez es dominante de otro. "
             "Cada resolución promete descanso y entrega una tensión nueva.",
             "Es el mismo principio del ciclo de Vivaldi, pero suelto, sin "
             "la forma fija de la cita."),
            locked_by="three_dominants",
            hint="Se escribe sola cuando encadenes tres dominantes."),
    ),
)


# ---------------------------------------------------------------------------
# VIII. Ingeniería
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# VIII. Las visitas
#
# El segundo capítulo que no se llena con logros. Sus llaves son claves de
# visita (``visit_<clave>``) y las contesta ``app.py`` contra el registro de
# ``engine/visitors.py``, igual que contesta las del capítulo anterior contra
# el sendero. Desde acá adentro no hay ninguna diferencia.
#
# El tono es el de alguien anotando lo que le acaban de decir: son apuntes de
# una conversación, no una explicación armada desde cero.
# ---------------------------------------------------------------------------

_VISITS = Chapter(
    "VIII", "Las visitas",
    "Lo que quedó anotado de las veces que alguien se apareció a explicar "
    "algo. Este capítulo no se llena leyendo: se llena trabajando hasta que "
    "alguien venga a mirar lo que hiciste.",
    (
        Entry(
            "oficio", "El oficio",
            ("Vino cuando el quinto trabajo estuvo terminado, y no dijo cómo "
             "había entrado. Aplaudió tres veces, despacio, como quien "
             "corrige un examen y encuentra algo que no esperaba.",
             "Lo que sigue es lo que quedó anotado. Parte lo dijo él; el "
             "resto se averiguó después, buscando quién había sido.",
             "**Se llamaba Johann Sebastian Bach.** Murió en 1750, y con esa "
             "fecha se cierra el barroco entero: para cuando murió, sus "
             "propios hijos escribían de otra manera y lo consideraban un "
             "viejo pasado de moda. Durante ochenta años casi nadie lo tocó. "
             "Lo desenterró un chico de veinte, Mendelssohn, en 1829, "
             "dirigiendo una Pasión que llevaba un siglo sin sonar.",
             "**La música se escribía en voces, no en acordes.** Cuatro "
             "personas, cuatro líneas, cada una con su propio sentido de "
             "arriba abajo. El acorde es lo que se oye cuando las cuatro "
             "pasan por el mismo punto: una consecuencia, no un ingrediente. "
             "Es exactamente lo que hace este programa, y es de acá de donde "
             "lo sacó.",
             "**El bajo continuo.** Abajo de todo iba una línea sola con "
             "números escritos debajo, y de esos números salía toda la "
             "armonía. Un teclista los leía y completaba los acordes en el "
             "momento, sin que nadie se los escribiera: en el barroco se "
             "improvisaba muchísimo más de lo que se cree, y la partitura "
             "era menos una orden que un plano.",
             "**Cada voz tiene que poder cantarse sola.** Si una línea sólo "
             "tiene sentido cuando suenan las otras tres, está mal escrita "
             "por más que el acorde cierre. Es el criterio con el que este "
             "programa castiga los saltos: una voz que salta todo el tiempo "
             "no es una voz, es un relleno.",
             "**Lo que hizo para aprender.** A los veinte años caminó "
             "cuatrocientos kilómetros para escuchar tocar a Buxtehude. "
             "Había pedido cuatro semanas de licencia; volvió a los cuatro "
             "meses. Años más tarde, cuando otro patrón no lo dejó irse, "
             "insistió tanto que lo metieron preso un mes. Salió con "
             "veintitantos preludios corales escritos en la celda.",
             "**Su firma.** En alemán, las notas si bemol, la, do y si "
             "natural se escriben B, A, C, H: su apellido es una melodía. La "
             "usó como tema en lo último que estaba escribiendo, y esa fuga "
             "se corta en la mitad de un compás. Lo que sigue después del "
             "corte no existe.",
             "**La cita.** *No hay nada notable en ello. Sólo hay que tocar "
             "la tecla correcta en el momento adecuado, y el instrumento se "
             "toca solo.* Se repite siempre como una modestia. No lo es: es "
             "la instrucción entera, y es lo más difícil que se ha dicho "
             "nunca sobre tocar un instrumento.",
             "Su apellido quiere decir *arroyo*. Beethoven dijo que no "
             "debería llamarse arroyo sino mar."),
            locked_by="visit_bach_baroque",
            hint="Se escribe cuando alguien venga a leer lo que escribiste."),
        Entry(
            "coral", "El coral",
            ("Volvió apenas se encendió el modo coral, y esta vez no aplaudió "
             "nadie: golpeó una vez la mesa, como quien pide silencio antes "
             "de que entre el coro.",
             "Un coral es un himno luterano armonizado a cuatro voces. "
             "Escribió más de trescientos, y son el material con el que se "
             "sigue enseñando armonía hoy, casi trescientos años después: "
             "media carrera de música es, literalmente, ingeniería inversa "
             "de estos trescientos setenta y un ejercicios.",
             "**La melodía no es de él.** La línea de arriba es un himno que "
             "la congregación ya se sabía de memoria; algunos son anteriores "
             "a Lutero y varios eran canciones de taberna a las que "
             "alguien les cambió la letra. Lo que se compone es lo que va "
             "debajo: tres voces sosteniendo una melodía ajena. Es el mismo "
             "trabajo que hace el Armonizador de este programa.",
             "**Las cuatro voces se mueven juntas.** Una sílaba, un acorde. "
             "En el resto del barroco cada voz corre por su lado; en un "
             "coral van todas al mismo paso, porque atrás hay gente cantando "
             "y hay que dejarla entrar.",
             "**Se canta, no se toca.** Nada de saltos imposibles, nada de "
             "notas fuera del alcance de una garganta común, y una "
             "respiración donde termina cada frase. Por eso el modo coral de "
             "este programa recorta los rangos y aprieta los saltos.",
             "**Las frases se cortan.** Al final de cada verso hay un "
             "calderón --- ese puntito con el arco encima --- y ahí se arma "
             "una cadencia de verdad. En el papel dice «alargá esta nota»; "
             "en la práctica dice «acá respira todo el mundo». Un coral son "
             "ocho frases chiquitas, no una frase larga.",
             "**Las reglas se aprietan.** Nada de quintas ni octavas "
             "paralelas, nada de voces cruzadas, nada de huecos enormes "
             "entre una voz y la de al lado. No es rigor por el rigor: es "
             "que cuatro personas que no son músicos tienen que poder "
             "sostener eso de memoria un domingo a la mañana, sin ensayar.",
             "**Cómo sobrevivieron.** Él no los publicó. Los juntó su hijo "
             "después de su muerte, sueltos, arrancados de las cantatas a "
             "las que pertenecían. Lo que llegó hasta hoy es una colección "
             "de fragmentos que nadie pensó como colección.",
             "**El último.** Ya ciego, dictó de memoria un coral desde la "
             "cama. Le cambió el título por *Ante tu trono me presento*. No "
             "llegó a escuchar cómo sonaba.",
             "**La cita.** *El fin último de toda música no debe ser otro "
             "que la gloria de Dios y la recreación del espíritu.* Lo "
             "escribió en el margen de un cuaderno de ejercicios, al lado de "
             "un ejercicio. No en una carta importante."),
            locked_by="visit_bach_chorale",
            hint="Se escribe cuando pruebes el modo coral."),
        Entry(
            "organum", "El organum",
            ("Apareció con la quinta partitura a una sola voz. Traía una "
             "paloma en el hombro y no la nombró en ningún momento, como si "
             "fuera parte de la ropa.",
             "Lo primero que aclaró es que el canto que lleva su nombre no "
             "lo escribió él. Se lo pusieron trescientos años después de "
             "muerto, para que la colección tuviera un autor: los cantos "
             "eran de todos y de nadie. La paloma viene de ahí --- se contó "
             "durante siglos que el Espíritu Santo se le posaba en el hombro "
             "y le dictaba las melodías al oído, y así se lo pintó desde "
             "entonces. Es la manera más elegante que encontró la Edad Media "
             "de decir que no sabía quién los había compuesto.",
             "**El organum.** Alrededor del año 900, en un tratado llamado "
             "*Musica enchiriadis*, aparece por primera vez algo que nadie "
             "había puesto por escrito: dos voces sonando a la vez, a "
             "propósito. Uno canta el canto llano de siempre --- la *vox "
             "principalis*, la voz principal --- y otro canta lo mismo, nota "
             "por nota, cuatro o cinco escalones más abajo: la *vox "
             "organalis*. No es una segunda melodía. Es la misma melodía "
             "corriendo en paralelo, como una sombra.",
             "**Por qué a esa distancia.** Porque la cuarta y la quinta eran "
             "los únicos intervalos considerados perfectos. Las terceras "
             "--- lo que hoy suena dulce --- se oían como disonancias, y el "
             "tritono tenía nombre propio: *diabolus in musica*. El modo "
             "gregoriano de este programa usa ese mismo criterio de "
             "consonancia, y por eso suena hueco: está bien que suene así.",
             "**Cómo se anotaba.** Al principio no se anotaba: se aprendía "
             "de oído, y un cantor tardaba diez años en saberse el "
             "repertorio. Los primeros signos eran garabatos encima de la "
             "letra que sólo recordaban si la melodía subía o bajaba --- no "
             "servían para aprender nada que no supieras ya. Recién "
             "alrededor de 1030 a un monje se le ocurrió tirar líneas "
             "horizontales y poner cada signo a una altura fija. Ese monje "
             "se llamaba Guido, y lo que inventó es el pentagrama que usás "
             "en el Armonizador. De paso les puso nombre a las notas, "
             "sacándolas de las primeras sílabas de un himno: *ut, re, mi, "
             "fa, sol, la*.",
             "**Lo que vino después.** Cuando la sombra empezó a moverse por "
             "su cuenta en vez de seguir a la voz, nació el contrapunto. En "
             "París, hacia 1200, dos hombres llamados Léonin y Pérotin "
             "escribieron organa de tres y cuatro voces: son los primeros "
             "compositores de la historia occidental de los que se conserva "
             "el nombre. De ahí a Bach hay ochocientos años, y de Bach a acá "
             "otros trescientos.",
             "**La cita.** De él se recuerda una frase, y es sobre las "
             "Escrituras: *es como un río llano y profundo, donde el cordero "
             "camina y el elefante nada*. Sirve igual para el canto: un "
             "chico canta una línea sola el primer día, y llevamos mil "
             "cuatrocientos años discutiendo cómo se anota."),
            locked_by="visit_gregory",
            hint="Se escribe cuando alguien venga a escuchar el canto."),
        Entry(
            "robert_johnson", "El del cruce de caminos",
            ("Esto no lo contó nadie. Apareció una noche, parado en el medio "
             "de un camino de tierra, y no dijo una sola palabra: se quedó "
             "mirando, se dio vuelta y se fue. Lo que sigue es lo que se "
             "pudo averiguar después sobre quién era.",
             "Robert Johnson nació en Misisipi en 1911 y murió en 1938, a "
             "los veintisiete años. Grabó veintinueve canciones en dos "
             "sesiones, en un cuarto de hotel y en un depósito. Es todo lo "
             "que quedó de él: eso, dos fotografías y un certificado de "
             "defunción sin causa anotada.",
             "**La leyenda.** Tocaba mal. Se fue un tiempo y volvió tocando "
             "de una manera que nadie podía explicar. La historia que "
             "circuló entre los músicos fue que había ido a un cruce de "
             "caminos a medianoche, que un hombre alto le había afinado la "
             "guitarra y se la había devuelto, y que el precio se arreglaba "
             "después. Él nunca la desmintió. Grabó canciones tituladas "
             "*Cross Road Blues*, *Me and the Devil Blues* y *Hellhound on "
             "My Trail*, que es un perro del infierno siguiéndole el rastro, "
             "y en las tres canta en primera persona.",
             "**Lo que probablemente pasó.** Se fue a estudiar con Ike "
             "Zimmerman, un guitarrista que ensayaba de noche en un "
             "cementerio porque era el único lugar donde nadie se quejaba "
             "del ruido. Volvió sabiendo tocar porque había practicado un "
             "año entero, solo, de noche, sentado sobre las lápidas. La "
             "versión aburrida casi siempre es la verdadera, y casi siempre "
             "también es un cruce de caminos y un precio.",
             "**Por qué la leyenda ganó igual.** Porque explica algo que la "
             "otra no: la sensación, al escucharlo, de que hay más de una "
             "guitarra sonando. Toca el bajo, el acompañamiento y la melodía "
             "a la vez, en un instrumento solo, con una mano que además "
             "canta por encima. Eso es contrapunto --- tres voces "
             "independientes --- y no lo estudió en ningún lado.",
             "**Cómo grabó.** De cara a la pared, en un rincón, dándole la "
             "espalda al técnico. Se dijo durante décadas que era para que "
             "nadie le viera las manos. Un ingeniero explicó después que el "
             "rincón devuelve el sonido y que era, sencillamente, el mejor "
             "lugar del cuarto. Las dos cosas pueden ser ciertas.",
             "**Cómo murió.** Envenenado, dicen, con una botella de whisky "
             "abierta que aceptó en un baile. Tardó tres días. Tenía "
             "veintisiete años, la misma edad a la que se murieron después "
             "media docena de los que lo escucharon.",
             "**Dónde está enterrado.** No se sabe. Hay tres tumbas con su "
             "nombre en tres cementerios distintos de Misisipi, y las tres "
             "tienen visitas."),
            locked_by="visit_robert",
            legendary=True,
            hint="Hay cosas que no se consiguen. Se te aparecen."),
    ),
)


# ---------------------------------------------------------------------------
# VII. La música de los reprimidos
#
# El único capítulo que no se llena con logros sino con el modo historia: sus
# llaves son claves de sendero (``story_<sendero>_<tramo>``) y quien pregunta
# --- ``app.py`` --- las resuelve contra el estado de la historia igual que
# resuelve las otras contra el registro de logros. Desde acá adentro no hay
# ninguna diferencia: una llave es una cadena que alguien sabe contestar.
#
# El tono también cambia. Los otros capítulos explican; éste cuenta de dónde
# salió cada cosa, que es lo que ninguno de los otros dice.
# ---------------------------------------------------------------------------

_OPPRESSED = Chapter(
    "VII", "La música de los reprimidos",
    "Casi todo lo que suena hoy lo inventó gente a la que no le permitían "
    "tocar. Este capítulo no se llena estudiando: se llena caminando.",
    (
        Entry(
            "cadencia_blues", "La cadencia del pacto",
            ("Tres acordes: el primero, el cuarto y el quinto grado de la "
             "escala, y los tres con séptima menor. En do se escriben C7, F7 "
             "y G7.",
             "Lo raro es justamente eso: los tres llevan séptima. Ya "
             "sabemos, del capítulo de armonía, que un acorde con séptima "
             "menor pide resolver —está incómodo, tira hacia otro lado—. Que "
             "el acorde de reposo, el primer grado, también la lleve es una "
             "contradicción: la casa a la que se vuelve tampoco es un lugar "
             "donde quedarse.",
             "En la práctica común eso era un error. Un tratado del "
             "mil ochocientos te lo hubiera marcado en rojo. En el blues es "
             "la definición del género: nada resuelve del todo, nunca, y esa "
             "insatisfacción permanente es exactamente lo que la música "
             "quiere decir.",
             "**De dónde salió.** De los campos de algodón del delta del "
             "Misisipi, a fines del siglo diecinueve, cantada por personas "
             "que habían sido esclavizadas y por sus hijos. No la escribió "
             "nadie: se pasaba de boca en boca, sin partitura, y cuando "
             "alguien la anotó por primera vez ya tenía cincuenta años.",
             "**La leyenda.** Se cuenta que Robert Johnson, que tocaba mal, "
             "desapareció un tiempo y volvió tocando como nadie. La "
             "explicación que circuló fue que había ido a un cruce de "
             "caminos a medianoche y le había entregado la guitarra a "
             "alguien que se la devolvió afinada. Murió a los veintisiete "
             "años. Nadie sabe dónde está enterrado."),
            locked_by="story_blues_1",
            hint="Se escribe cuando alguien te enseñe a escribirla."),
        Entry(
            "doce_compases", "Los doce compases",
            ("Doce compases, siempre los mismos, siempre en el mismo orden: "
             "cuatro sobre el primer grado, dos sobre el cuarto, dos sobre el "
             "primero otra vez, y los últimos cuatro bajando desde el quinto "
             "hasta el giro que devuelve todo al principio.",
             "Es la forma más repetida de la historia de la música popular. "
             "No es una canción: es un recipiente. Adentro entra cualquier "
             "cosa, y lo que cambia entre una versión y otra es todo menos "
             "el esqueleto.",
             "**Por qué no termina.** El compás doce no cierra: prepara. Ese "
             "último acorde —el quinto grado— empuja de vuelta al compás "
             "uno. Por eso se puede tocar toda la noche sin cortar: la forma "
             "está diseñada para no tener final, sólo un lugar donde alguien "
             "decide parar.",
             "**Lo que salió de acá.** El rhythm and blues, el rock and "
             "roll entero, buena parte del jazz, el soul. Chuck Berry, "
             "Elvis, los Beatles, los Rolling Stones: todos empezaron "
             "tocando doce compases. Ninguna de esas fortunas volvió al "
             "delta del Misisipi."),
            locked_by="story_blues_2",
            hint="Se escribe cuando la rueda dé la vuelta entera."),
        Entry(
            "nota_azul", "La nota azul",
            ("Es la quinta disminuida: la nota que queda justo en el medio de "
             "la octava, a seis semitonos de la tónica. En la menor es el mi "
             "bemol.",
             "No pertenece a ninguna de las dos escalas grandes. No es de la "
             "mayor ni de la menor: cae entre la tercera y la quinta, en un "
             "lugar donde la teoría europea no había puesto nada.",
             "**Por qué existe.** Las escalas de África occidental no "
             "dividen la octava igual que el piano. Cuando esa manera de "
             "cantar se encontró con un instrumento afinado a la europea, "
             "las notas que no existían en el teclado se buscaron doblando "
             "la cuerda o resbalando la voz. La nota azul es la cicatriz de "
             "ese encuentro.",
             "Es el mismo intervalo que el capítulo de contrapunto llama "
             "tritono y que el canto llano tenía prohibido: *diabolus in "
             "musica*, el diablo en la música. Mil años más tarde, la misma "
             "nota que la Iglesia había desterrado se volvió el centro de "
             "todo un género. Nadie hizo ese chiste a propósito.",
             "**Cómo se usa.** De paso, nunca apoyada. Se pisa y se sigue: "
             "es una nota que duele, y lo que la hace funcionar es que no se "
             "queda."),
            locked_by="story_blues_3",
            hint="Se escribe cuando toques la que no existe."),
        Entry(
            "jazzes", "Los jazzes",
            ("«Jazz» no es un género: es una familia de géneros que se "
             "llevan mal entre sí. Vale la pena saber cuál es cuál, porque "
             "suenan a cosas distintas.",
             "**Nueva Orleans (1900–1920).** El primero. Varios instrumentos "
             "de viento improvisando a la vez, cada uno su línea, sobre una "
             "base de marcha. Es contrapunto puro, hecho por gente que no "
             "sabía la palabra contrapunto.",
             "**Swing (1930–1945).** Orquestas grandes, arreglos escritos, "
             "música para bailar. Es el jazz que fue música popular masiva, "
             "el único que lo fue.",
             "**Gypsy jazz (1930–).** Sin batería y sin vientos: dos o tres "
             "guitarras y un contrabajo. Una guitarra marca el pulso "
             "golpeando las cuerdas —«la pompe»— y la otra hace la melodía. "
             "Lo inventaron músicos gitanos en Francia; su nombre propio es "
             "Django Reinhardt, que se quemó la mano izquierda en un "
             "incendio a los dieciocho años y volvió a aprender a tocar "
             "usando dos dedos.",
             "**Bebop (1945–1955).** La reacción. Tempos imposibles, "
             "melodías de corcheas sin respiro, armonía cargada de "
             "tensiones. Deliberadamente difícil de bailar: era música para "
             "escuchar, hecha por músicos que estaban cansados de ser la "
             "orquesta de un salón.",
             "**Cool, modal, free (1955–).** Después el jazz se abrió en "
             "abanico y ya no volvió a juntarse. El modal cambió los acordes "
             "por escalas; el free tiró la armonía entera por la ventana.",
             "**Lo que tienen en común.** El ii-V. Ese par de acordes que "
             "aprendiste está en todos, del primero al último."),
            locked_by="story_jazz_1",
            hint="Se escribe cuando alguien te muestre que no hay un solo "
                 "jazz."),
        Entry(
            "estandar", "El estándar",
            ("Un estándar es una canción que todos los músicos de jazz saben "
             "de memoria y que ninguno toca igual. No son canciones de jazz: "
             "casi todas venían de comedias musicales y de películas de los "
             "años veinte y treinta.",
             "**Para qué sirven.** Son un idioma común. Dos músicos que no "
             "se conocen se sientan, uno dice un título y una tonalidad, y "
             "pueden tocar media hora sin haber ensayado nunca. Eso no "
             "existe en casi ninguna otra música.",
             "**La forma.** Treinta y dos compases repartidos en cuatro "
             "frases de ocho, con el esquema A A B A: se dice una frase, se "
             "repite, se dice otra distinta —el puente— y se vuelve a la "
             "primera. Ese esquema es tan común que se lo reconoce sin "
             "contar.",
             "**Qué se toca de verdad.** La melodía se toca una vez al "
             "principio y una vez al final. En el medio nadie la toca: lo que "
             "queda es el esquema de acordes, dando vueltas, y encima de él "
             "se inventa. La canción es la excusa."),
            locked_by="story_jazz_2",
            hint="Se escribe cuando toques la que sabe todo el mundo."),
        Entry(
            "the_lick", "La frase",
            ("Siete notas: sube por grados desde el segundo grado hasta el "
             "quinto, baja al tercero, salta al primero y sube al segundo. En "
             "re menor son re, mi, fa, sol, mi, do, re.",
             "No tiene autor. Aparece en grabaciones de los años cincuenta, "
             "está en Charlie Parker, está en Coltrane, está en bandas de "
             "sonido, está en canciones pop que no tienen nada que ver con "
             "el jazz.",
             "**Por qué funciona.** Es una escala menor recorrida de la "
             "forma más eficiente posible: sube por grado conjunto —lo que "
             "el capítulo de contrapunto llama el movimiento más barato— y "
             "vuelve con un solo salto. Es lo que le sale a una mano que "
             "conoce la escala.",
             "**Por qué es un chiste.** De tan usada se volvió un lugar "
             "común, y los músicos empezaron a citarla a propósito para "
             "burlarse de sí mismos. Hay recopilaciones enteras de gente "
             "tocándola sin darse cuenta.",
             "**Y sin embargo.** Sigue funcionando. Un lugar común lo es "
             "porque durante mucho tiempo fue verdad."),
            locked_by="story_jazz_3",
            hint="Se escribe cuando te salga sin pensarla."),
        Entry(
            "gospel", "El góspel",
            ("La música que se canta en las iglesias negras de Estados "
             "Unidos. Empieza donde empieza el blues —las mismas personas, "
             "los mismos años— y las dos ramas nunca se separaron del todo.",
             "**El origen.** Los *spirituals*: canciones que las personas "
             "esclavizadas cantaban trabajando, con letras bíblicas que a "
             "veces eran instrucciones para escapar. «Wade in the water» "
             "también quería decir metete en el agua, que el agua no deja "
             "rastro para los perros.",
             "**Cómo suena.** Llamada y respuesta —uno canta una frase y el "
             "coro contesta—, armonías densas de cuatro y cinco voces, y una "
             "manera de cantar donde la nota escrita es apenas el punto de "
             "partida. Nada se canta exactamente como está anotado.",
             "**Su cadencia.** El góspel se apoya en la cadencia plagal, el "
             "amén del capítulo anterior: el cuarto grado cayendo sobre el "
             "primero. No empuja como la cadencia auténtica. Llega y se "
             "queda.",
             "**Lo que salió de acá.** El soul entero. Aretha Franklin, Ray "
             "Charles, Sam Cooke: los tres cantaban en la iglesia antes de "
             "grabar un disco, y a los tres los acusaron de traición por "
             "usar la voz de Dios para cantar otras cosas."),
            locked_by="story_gospel_1",
            hint="Se escribe cuando cantes con tus hermanos."),
        Entry(
            "regla_octava", "La regla de la octava",
            ("El bajo baja de a un escalón, sin saltarse ninguno, desde la "
             "tónica hasta la tónica de la octava de abajo. Sobre cada "
             "escalón se pone el acorde que le corresponde, y varios de ellos "
             "quedan invertidos: con la tercera o la quinta en el bajo, que "
             "es lo que permite que la línea camine sin baches.",
             "**De dónde viene el nombre.** Del siglo dieciocho, y de un "
             "contexto muy distinto: era un ejercicio que se les daba a los "
             "chicos de los conservatorios de Nápoles para que aprendieran a "
             "armonizar cualquier bajo de memoria. Lo llamaban *regola "
             "dell'ottava*.",
             "**Cómo llegó al góspel.** No llegó: se reinventó. Un bajo que "
             "baja por grados y arrastra la armonía es una idea a la que se "
             "llega sola en cuanto uno se sienta al piano y quiere que algo "
             "suene inevitable.",
             "**Qué la hace sonar así.** Cada acorde comparte notas con el "
             "siguiente y el bajo se mueve lo mínimo posible. Es la "
             "definición literal de buena conducción de voces, que es todo "
             "lo que este programa hace. La emoción no está en ningún acorde "
             "particular: está en que ninguno se mueve de más."),
            locked_by="story_gospel_2",
            hint="Se escribe cuando bajes toda la escalera."),
        Entry(
            "amazing_grace", "Amazing Grace",
            ("La escribió John Newton en 1772. Newton había sido capitán de "
             "un barco negrero. La letra es lo que escribió cuando entendió "
             "lo que había hecho: *salvó a un desgraciado como yo*.",
             "La melodía que se canta hoy no es la suya: es una tonada "
             "popular llamada «New Britain», que alguien le acopló en 1835 "
             "en Estados Unidos. La canción tal como existe es un accidente "
             "entre un texto y una melodía que nunca se conocieron.",
             "**Cómo está hecha.** Con cinco notas: es pentatónica, la "
             "escala sin semitonos que existe en casi todas las culturas del "
             "mundo. Por eso se puede cantar sin haberla aprendido y por eso "
             "no suena de ningún país en particular.",
             "**La ironía.** La cantaron, y la siguen cantando, sobre todo "
             "los descendientes de las personas que Newton transportó. Se "
             "canta en entierros y en casamientos, en las dos cosas, y "
             "funciona en las dos.",
             "Es el final del sendero, y es la única pieza de este libro que "
             "no hace falta explicar para que se entienda."),
            locked_by="story_gospel_3",
            hint="Se escribe cuando la gracia te alcance."),
    ),
)


# ---------------------------------------------------------------------------
# IX. Ingeniería
# ---------------------------------------------------------------------------

_ENGINEERING = Chapter(
    "IX", "Ingeniería",
    "Cómo funciona el programa por dentro, en resumen. No hace falta leer "
    "esto para usarlo, pero explica por qué a veces da resultados distintos "
    "con la misma entrada.",
    (
        Entry(
            "problema", "Qué problema resuelve",
            ("Los acordes están dados. Lo que no está dado es qué nota de "
             "cada acorde canta cada voz y en qué octava. Ese reparto tiene "
             "muchísimas combinaciones posibles: con cuatro voces y una "
             "docena de acordes, la cantidad de repartos válidos se cuenta "
             "en miles de millones.",
             "Probarlos todos es imposible. Elegir siempre el más cercano "
             "acorde por acorde tampoco sirve, porque la mejor decisión en "
             "el acorde 3 puede dejarte sin salida en el 7. Hace falta "
             "algo que busque en grande y que mejore de a poco.")),
        Entry(
            "ag", "El algoritmo genético",
            ("La idea es imitar la selección natural. Cada solución "
             "candidata es un «cromosoma»: una lista que dice, para cada "
             "acorde, cuál de sus repartos posibles se usó.",
             "El programa arranca con una población de doscientos "
             "cromosomas al azar. A cada uno le calcula un costo —cuánto se "
             "mueven las voces, cuántas reglas rompe— y después arma la "
             "generación siguiente: los mejores pasan intactos (elitismo), "
             "el resto sale de cruzar pares de padres elegidos por torneo, "
             "y una fracción de los genes muta al azar para que la búsqueda "
             "no se estanque.",
             "Repetido trescientas veces, ese proceso converge a soluciones "
             "muy buenas sin haber mirado ni una milésima del espacio. Como "
             "el azar interviene, dos corridas con la misma entrada dan "
             "resultados parecidos pero no idénticos: por eso el programa "
             "te muestra las tres mejores y no una sola."),
            recipe="Población, generaciones, elitismo, torneo y mutación se "
                   "tocan en el engranaje de abajo a la izquierda. Más "
                   "población y más generaciones dan mejores resultados y "
                   "tardan más."),
        Entry(
            "costo", "Cómo se puntúa una solución",
            ("El costo es una suma, y menos es mejor. Se divide en dos "
             "clases muy distintas.",
             "**Restricciones duras.** Rango vocal, cobertura del acorde, "
             "cruce de voces, y las paralelas o el tritono que hayas "
             "prendido. Romper una de éstas no suma costo: anula el "
             "cromosoma entero, que deja de competir. Por eso una regla "
             "dura nunca aparece violada en el resultado.",
             "**Penalizaciones ponderadas.** Movimiento total —el peso más "
             "grande de todos—, saltos, espaciado, tesitura, quintas "
             "directas, falta de movimiento contrario. Éstas el algoritmo "
             "las negocia entre sí: acepta un espaciado peor si a cambio "
             "las voces se mueven mucho menos.",
             "El dial «¿Qué te importa más?» de la pantalla de reglas mueve "
             "el balance entre el grupo de movimiento y el grupo de "
             "estilo. Todo lo demás son valores por defecto que el estilo "
             "elegido fija y que podés tocar de a uno.")),
        Entry(
            "armonia_motor", "Cómo elige los acordes",
            ("En el Generador, antes de repartir voces hay que decidir qué "
             "acordes van. El programa arma para cada lugar la lista de "
             "acordes posibles en la tonalidad —los siete grados, más los "
             "préstamos y las dominantes secundarias que hayas "
             "habilitado— y le pone un peso a cada uno según su función y "
             "según cuál vino antes.",
             "El Armonizador hace lo mismo pero al revés: recorre la "
             "melodía **de atrás para adelante**. Suena raro hasta que se "
             "piensa un segundo: saber que el acorde siguiente es un punto "
             "de reposo es exactamente lo que te dice que el actual quiere "
             "ser dominante. Hacia adelante esa información todavía no "
             "existe.",
             "Las cadencias famosas del capítulo anterior no se construyen "
             "por peso: son citas guardadas enteras, que el programa "
             "propone cuando la tonalidad, el estilo y la cantidad de "
             "acordes coinciden exactamente con las que la cita necesita.")),
        Entry(
            "adornos", "Por qué los adornos van al final",
            ("Las notas de paso, la sexta de Bach y los gestos de época se "
             "aplican **después** de la búsqueda, sobre la solución "
             "ganadora, y no dentro del cálculo de costo.",
             "El motivo es que el costo premia el mínimo movimiento, y un "
             "adorno siempre agrega movimiento. Dentro del fitness, un "
             "adorno sólo podía ganar si se le pagaba con una recompensa, y "
             "esa recompensa distorsionaba todo lo demás: la búsqueda "
             "empezaba a elegir voicings raros con tal de cobrarla.",
             "Separarlos deja las dos cosas limpias. Primero se resuelve el "
             "problema de conducción; después se decora lo que ya está "
             "bien resuelto.")),
        Entry(
            "sin_dependencias", "Todo escrito a mano",
            ("El motor no usa ninguna librería externa: es Python estándar "
             "puro. El MusicXML, el MIDI y el audio que escuchás con el "
             "botón «Escuchar» están escritos byte a byte por el programa.",
             "La razón es práctica. Sin dependencias el ejecutable queda "
             "chico, arranca rápido y no se rompe cuando una librería de "
             "terceros cambia de versión. La única dependencia real de "
             "todo el proyecto es la que dibuja la ventana.")),
        Entry(
            "cython", "Por qué la búsqueda es rápida",
            ("Evaluar un cromosoma es contar semitonos: restas, restos de "
             "doce y comparaciones. Cada una cuesta poquísimo, pero una "
             "corrida corriente hace **sesenta mil** evaluaciones y cada "
             "una recorre todos los acordes y todos los pares de voces. Son "
             "decenas de millones de operaciones diminutas, y ahí Python "
             "—que revisa el tipo de cada número antes de sumarlo— trabaja "
             "mucho más de lo que la cuenta necesita.",
             "Lo primero fue dejar de hacer trabajo al pedo. Cuando las "
             "reglas duras anulan a la mayoría de los hijos de una "
             "generación, el programa completa la población clonando a los "
             "mejores; durante mucho tiempo volvía a puntuar cada clon, "
             "aunque su costo ya estuviera calculado. Eran cuatro de cada "
             "diez evaluaciones de la corrida, y un mismo cromosoma llegó a "
             "puntuarse siete mil veces. Sacarlas hizo además que valiera "
             "la pena repartir el trabajo entre los procesadores de la "
             "máquina, cosa que antes casi no rendía: los otros núcleos "
             "esperaban mientras el principal recalculaba lo que ya sabía.",
             "Lo segundo fue traducir a C las tres partes que la búsqueda "
             "pisa millones de veces —el evaluador, las reglas de estilo y "
             "la representación de las notas— con una herramienta que se "
             "llama Cython. No es una reescritura: son los mismos archivos "
             "de Python, sin una línea cambiada, con una hoja de tipos al "
             "lado que dice «este número siempre es un entero». Con eso "
             "alcanza para que la suma se compile a una suma de verdad.",
             "Las dos cosas juntas dejaron la búsqueda unas seis veces más "
             "rápida, y el resultado es **exactamente el mismo**: se "
             "verificó nota por nota que la misma semilla sigue dando la "
             "misma partitura. Una optimización que cambie lo que suena no "
             "es una optimización, es otro programa.",
             "Y sigue sin haber dependencias: los archivos compilados son "
             "opcionales. Si no están, el programa levanta los de Python y "
             "hace lo mismo, más despacio. Nada de lo que leíste en los "
             "otros capítulos depende de que existan."),
            recipe="En el engranaje, abajo de la configuración del "
                   "algoritmo, dice cuántos núcleos tiene tu máquina y "
                   "cuántos procesos va a usar la búsqueda. Siempre deja uno "
                   "libre para que la ventana siga respondiendo mientras "
                   "busca."),
    ),
)


CHAPTERS: Tuple[Chapter, ...] = (
    _BASICS, _HARMONY, _COUNTERPOINT, _STYLES, _HISTORY, _CADENCES,
    _OPPRESSED, _VISITS, _ENGINEERING,
)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

#: Todas las llaves que abren contenido, para poder preguntar de una si algo
#: nuevo se escribió sin recorrer los capítulos a mano.
LOCK_KEYS: Tuple[str, ...] = tuple(
    entry.locked_by
    for chapter in CHAPTERS
    for entry in chapter.entries
    if entry.locked_by
)


def unlocked_keys(has_achievement) -> Set[str]:
    """Las llaves de libro que este usuario ya abrió."""
    return {key for key in LOCK_KEYS if has_achievement(key)}


def is_secret(entry: Entry) -> bool:
    """
    ¿Este apartado esconde hasta su título mientras siga cerrado?

    Los del sendero y los legendarios: en los dos casos el título es la mitad
    de lo que hay para revelar, así que se muestra ``? ? ?`` en su lugar. En
    todos los demás el título es justamente la pista de qué hay que hacer, y
    esconderlo no protegería nada.
    """
    return bool(entry.legendary) or entry.locked_by.startswith("story_")


def is_special(chapter: Chapter) -> bool:
    """¿El capítulo se escribe con oro? El que tiene algo que no se estudia."""
    return any(is_secret(entry) for entry in chapter.entries)


def entry_for_lock(key: str):
    """El apartado que abre una llave, o None."""
    for chapter in CHAPTERS:
        for entry in chapter.entries:
            if entry.locked_by == key:
                return chapter, entry
    return None


def counts(has_achievement) -> Tuple[int, int]:
    """Cuántos apartados están escritos sobre el total."""
    written = total = 0
    for chapter in CHAPTERS:
        for entry in chapter.entries:
            total += 1
            if not entry.locked_by or has_achievement(entry.locked_by):
                written += 1
    return written, total
