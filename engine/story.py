# -*- coding: utf-8 -*-
"""
El modo historia: los tres senderos, sus diálogos y lo que hay que hacer.

Este módulo es **datos y estado**. No dibuja nada, no suena nada y no importa
ningún toolkit gráfico, igual que el resto de ``engine/``. La cinemática vive
en ``cinematic.py``, los ruidos en ``engine/ambience.py`` y los enganches con
las pantallas en ``app.py``.

Cómo está armado
----------------
Una figura misteriosa aparece después de un rato de uso y ofrece un poder.
La respuesta elige el sendero:

===========  ===========================  ==========================
Respuesta    Sendero                      Quién acompaña
===========  ===========================  ==========================
Aceptar      ``blues``                    el señor del sombrero
Ignorar      ``jazz``                     un guitarrista anónimo
Rechazar     ``gospel``                   Jesús
===========  ===========================  ==========================

Cada sendero son **tres tramos** y siempre los mismos tres lugares: el
primero se hace a mano en el Organizador, el segundo con un botón dorado en
el Generador y el tercero con un gesto dorado en el Armonizador. Los dos
botones dorados nacen **bloqueados**: cada uno pide un objetivo básico
(``Step.gate``) que se cumple usando el programa de la forma de siempre.

Por qué el estado va en su propio archivo
-----------------------------------------
``achievements.json`` es el registro de lo que el usuario consiguió y
``settings.json`` es una lista blanca de preferencias. Un sendero a medio
andar no es ninguna de las dos cosas: tiene contadores, un tramo en curso y
un recuerdo de qué se leyó. Va en ``story.json``, al lado de los otros dos,
con la misma regla de que un archivo roto no puede impedir que el programa
arranque.

Los tramos automáticos
----------------------
Los tres senderos terminan escribiendo una pieza fija --- los doce compases
del blues, *All of Me*, la regla de la octava del góspel, *Amazing Grace*.
Esas piezas viajan acá como listas de cifrados con sus duraciones, y
``app.py`` las convierte en una corrida normal con todas las voces fijadas
con el candado. Es lo que hace que el resultado sea instantáneo y no dependa
ni del algoritmo genético ni de los parámetros que el usuario haya tocado:
con cada acorde fijado no queda nada que buscar.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from itertools import permutations
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import history
from .achievements import BLUES_PACT, first_match, matched_tonics
from .theory import (ROLE_FIFTH, ROLE_ROOT, ROLE_SEVENTH, SHARP_NAMES,
                     Chord, build_voice_parts, parse_chord)
from .voicing import build_requirement

_FILENAME = "story.json"

#: Cuánto hay que estar usando el programa antes de que la figura aparezca:
#: cinco minutos. ``CHORDWEAVER_STORY_DELAY`` lo pisa desde el entorno, que es
#: la única manera de mirar la escena sin esperarla --- y el motivo por el que
#: este número se había quedado en diez segundos.
DEFAULT_DELAY_SECONDS = 300.0


def delay_seconds() -> float:
    raw = os.environ.get("CHORDWEAVER_STORY_DELAY", "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_DELAY_SECONDS
    return max(1.0, value)


# ---------------------------------------------------------------------------
# Quiénes hablan
# ---------------------------------------------------------------------------

#: Las claves de los personajes. El aspecto de cada uno --- su tipografía, su
#: color, cómo se lo dibuja --- vive en ``cinematic.py``: acá sólo está quién
#: es quién.
DEVIL = "devil"
DJANGO = "django"
JESUS = "jesus"
NARRATOR = "narrator"


@dataclass(frozen=True)
class Line:
    """Un mensaje del diálogo. Se avanza tocando «Siguiente»."""

    speaker: str
    text: str
    #: Un gesto que la cinemática interpreta: ``"shake"``, ``"flash"``,
    #: ``"item"``… Vacío es un mensaje normal.
    cue: str = ""
    #: Con qué cara lo dice. Es una clave de ``cinematic.POSES``; vacío deja
    #: la que estuviera puesta, que es lo que corresponde cuando el que habla
    #: es el narrador y el personaje no hizo nada.
    pose: str = ""


@dataclass(frozen=True)
class Step:
    """Un tramo del sendero."""

    key: str
    #: En qué modo se juega: ``manual``, ``random`` o ``harmonise``.
    where: str
    title: str
    #: La consigna, escrita para alguien que no sabe nada de música.
    goal: str
    #: La pista larga, la que dice exactamente qué escribir.
    hint: str
    #: Lo que dice el personaje cuando el tramo empieza.
    intro: Tuple[Line, ...] = ()
    #: Lo que pide para destrabar el botón dorado. Va aparte del relato a
    #: propósito: **sólo se dice si la traba sigue cerrada**. El usuario suele
    #: cumplirla sin querer mientras juega con el tramo anterior, y entonces
    #: el personaje le pedía algo que ya estaba hecho --- que es la forma más
    #: rápida de que un relato deje de tener sentido.
    task: Tuple[Line, ...] = ()
    #: Lo que dice cuando se completa.
    outro: Tuple[Line, ...] = ()
    #: Objetivo básico que desbloquea el botón dorado. Vacío = sin traba.
    gate: str = ""
    #: Lo que dice el botón mientras siga gris.
    locked_text: str = ""
    #: Lo que dice ya desbloqueado.
    ready_text: str = ""


@dataclass(frozen=True)
class Path:
    """Un sendero entero."""

    key: str
    #: Cómo se llama una vez recorrido. Antes de eso no se muestra: el
    #: nombre del camino es el final del relato, y ponerlo en la pantalla
    #: inicial desde el primer día lo regala entero.
    name: str
    #: Cómo se lo nombra mientras se lo está caminando.
    mystery: str
    speaker: str
    #: Qué se gana al terminarlo. Es una clave del catálogo de logros.
    award: str
    #: El recuerdo que entrega el personaje, en texto.
    keepsake: str
    keepsake_icon: str
    steps: Tuple[Step, ...]
    #: El cierre, después del último tramo.
    finale: Tuple[Line, ...] = ()

    def title(self, finished: bool) -> str:
        return self.name if finished else self.mystery


# ---------------------------------------------------------------------------
# Los objetivos básicos que destraban los botones dorados
# ---------------------------------------------------------------------------

#: Cada traba es «hacer esto en tres tonalidades distintas» o «leer tal
#: apartado del libro». Las de tonalidad se cuentan solas mientras el usuario
#: escribe acordes en el Organizador; las de lectura se marcan cuando el
#: apartado aparece de verdad en pantalla.
#: Repetir la progresión en tres tonalidades. Ya no la pide ningún tramo
#: --- resultó un peaje, no un descubrimiento --- pero la detección se queda:
#: es la que enciende en dorado los acordes de la cadencia mientras se
#: escriben, y la que usa la suite para probar que el reconocimiento anda.
GATE_BLUES_KEYS = "blues_keys"
GATE_JAZZ_KEYS = "jazz_keys"
GATE_GOSPEL_KEYS = "gospel_keys"

#: Lo que sí piden los tramos: leer. Cada cinemática deja una anotación nueva
#: en el libro y el botón dorado del tramo siguiente no se enciende hasta que
#: se la haya leído. La última no pide nada: es el cierre.
GATE_BLUES_BOOK = "blues_book"
GATE_BLUES_BOOK2 = "blues_book2"
GATE_JAZZ_BOOK = "jazz_book"
GATE_JAZZ_BOOK2 = "jazz_book2"
GATE_GOSPEL_BOOK = "gospel_book"
GATE_GOSPEL_BOOK2 = "gospel_book2"

#: Cuántas tonalidades distintas pide una traba de repetición.
KEYS_REQUIRED = 3

#: ii - V: un menor y, una cuarta más arriba, un dominante.
TWO_FIVE_SHAPE = ((0, "minor"), (5, "dominant"))
#: I - IV y IV - I: los mismos dos acordes mayores a distancia de cuarta, en
#: los dos órdenes. Se aceptan las dos porque el tramo del góspel se juega
#: escribiendo el amén --- que es IV - I --- y pedir después el orden
#: contrario sería pedir otra cosa con el mismo nombre.
PLAGAL_UP_SHAPE = ((0, "major"), (5, "major"))
PLAGAL_DOWN_SHAPE = ((0, "major"), (7, "major"))

#: Qué patrones mira cada traba de repetición, y en cuánto está la tónica
#: respecto de la fundamental del primer acorde de cada patrón.
KEY_GATES: Dict[str, Tuple[Tuple[Sequence[Tuple[int, str]], int], ...]] = {
    GATE_BLUES_KEYS: ((BLUES_PACT, 0),),
    # El ii está dos semitonos sobre la tónica, así que la tónica está dos
    # por debajo de la fundamental del primer acorde.
    GATE_JAZZ_KEYS: ((TWO_FIVE_SHAPE, -2),),
    # I - IV deja la tónica donde está; en IV - I el primer acorde es el
    # cuarto grado, así que la tónica queda una cuarta más abajo.
    GATE_GOSPEL_KEYS: ((PLAGAL_UP_SHAPE, 0), (PLAGAL_DOWN_SHAPE, -5)),
}

#: Las trabas que se cumplen leyendo. La clave es la misma con la que el
#: libro tiene cerrado el apartado.
BOOK_GATES: Dict[str, str] = {
    GATE_BLUES_BOOK: "story_blues_1",
    GATE_BLUES_BOOK2: "story_blues_2",
    GATE_JAZZ_BOOK: "story_jazz_1",
    GATE_JAZZ_BOOK2: "story_jazz_2",
    GATE_GOSPEL_BOOK: "story_gospel_1",
    GATE_GOSPEL_BOOK2: "story_gospel_2",
}


def tonics_for_gate(gate: str, chords: Sequence[Chord]) -> Set[int]:
    """
    Las tonalidades en las que esta progresión cumple la traba.

    Devuelve clases de altura: la tónica de cada aparición del patrón. Es lo
    que permite pedir «lo mismo en tres tonalidades distintas» sin tener que
    guardar la progresión entera de cada intento.
    """
    variants = KEY_GATES.get(gate)
    if not variants or not chords:
        return set()
    found: Set[int] = set()
    for pattern, offset in variants:
        found |= {(root + offset) % 12
                  for root in matched_tonics(chords, pattern)}
    return found


def matching_span(gate: str, chords: Sequence[Chord]
                  ) -> Optional[Tuple[int, int]]:
    """
    Dónde está escrita la cadencia de esta traba: ``(desde, cuántos)``.

    Existe para que la interfaz pueda encender en dorado exactamente los
    acordes que forman la cadencia y no la progresión entera. Devuelve la
    primera aparición: si el usuario la escribió dos veces, la que importa
    es la primera que se lee.
    """
    variants = KEY_GATES.get(gate)
    if not variants or not chords:
        return None
    for pattern, _offset in variants:
        start = first_match(chords, pattern)
        if start is not None:
            return start, len(pattern)
    return None


#: Qué cadencia mira cada tramo del Organizador. Es la misma traba que
#: después pide repetirla en tres tonalidades, así que el dorado que se
#: enciende mientras se escribe el tramo es el mismo que se enciende cuando
#: se la repite.
STEP_GATES: Dict[str, str] = {
    "blues_cadence": GATE_BLUES_KEYS,
    "jazz_two_five": GATE_JAZZ_KEYS,
    "gospel_plagal": GATE_GOSPEL_KEYS,
}


# ---------------------------------------------------------------------------
# El ofrecimiento
# ---------------------------------------------------------------------------

#: Lo que dice la figura antes de que haya que elegir. Va largo a propósito:
#: es la única aparición sin ruido, y el suspenso lo tiene que sostener el
#: texto solo.
OFFER: Tuple[Line, ...] = (
    Line(NARRATOR, "El aire de la habitación se enfría de golpe."),
    Line(NARRATOR, "Afuera hay pájaros. Adentro, alguien que hace un rato "
                   "no estaba."),
    Line(DEVIL, "Buenas noches. No te asustes: vengo caminando desde hace "
                "mucho y ya casi no hago ruido.", pose="normal"),
    Line(DEVIL, "Te estuve escuchando. Acordes ordenados, voces prolijas, "
                "cada nota en su lugar."),
    Line(DEVIL, "Muy correcto todo. Muy… enseñado.", pose="perfil"),
    Line(DEVIL, "Yo conocí a un muchacho igual que vos. Practicaba de noche, "
                "solo, en un cruce de caminos donde no pasa nadie.",
         pose="normal"),
    Line(DEVIL, "Le faltaba una sola cosa. La misma que te falta a vos.",
         pose="siniestro"),
    Line(DEVIL, "No se estudia. No se hereda. No está en ningún libro que "
                "hayas leído todavía."),
    Line(DEVIL, "Se acepta."),
    Line(DEVIL, "Yo puedo dártela esta misma noche. Vas a tocar de manera "
                "que quien te escuche una vez no se lo saque nunca más de "
                "encima.", pose="normal"),
    Line(DEVIL, "El precio lo arreglamos después. Siempre se arregla "
                "después.", pose="perfil"),
    Line(DEVIL, "¿Y bien? Tres caminos salen de este cuarto y sólo uno lo "
                "elegís vos.", cue="choice", pose="normal"),
)

#: Los tres botones del ofrecimiento, en orden.
CHOICES: Tuple[Tuple[str, str, str], ...] = (
    ("accept", "Aceptar el trato",
     "Le das la mano. Lo que venga después, vendrá."),
    ("ignore", "Ignorarlo",
     "No le contestás. Seguís trabajando como si no estuviera."),
    ("refuse", "Rechazarlo",
     "Lo mirás a los ojos y le decís que no."),
)

CHOICE_PATHS = {"accept": "blues", "ignore": "jazz", "refuse": "gospel"}

#: Lo que pasa apenas se responde, con la figura todavía en escena. Va aparte
#: del primer tramo porque son dos escenas distintas: en una está él y en la
#: otra ya está quien lo reemplaza. Aceptar no tiene entrada acá --- el que
#: se queda es él, y sigue hablando de una.
AFTERMATH: Dict[str, Tuple[Line, ...]] = {
    "jazz": (
        Line(NARRATOR, "No levantás la vista. Seguís acomodando voces como "
                       "si no hubiera nadie."),
        Line(DEVIL, "…", pose="perfil"),
        Line(DEVIL, "Está bien. Me equivoqué de puerta.", pose="normal"),
        Line(DEVIL, "Vas a acordarte de esta noche igual. Todos se "
                    "acuerdan.", pose="siniestro"),
        Line(NARRATOR, "Se da vuelta y camina. No hay portazo, no hay humo: "
                       "sólo alguien yéndose despacio, decepcionado."),
    ),
    "gospel": (
        Line(DEVIL, "¿Que no?", pose="normal"),
        Line(DEVIL, "Nadie me dice que no. Nadie.", pose="enojado"),
        Line(DEVIL, "Te vas a acordar de mí.", cue="shake", pose="enojado"),
        Line(NARRATOR, "El aire de golpe huele a quemado."),
        Line(NARRATOR, "Lo último que se le ve son los ojos, y ni siquiera "
                       "eso dura."),
    ),
}

#: El silencio entre un personaje y el siguiente. Sin esto, el que se va y el
#: que llega se pisan, y lo que tendría que ser una entrada se lee como un
#: cambio de diapositiva.
INTERLUDE: Tuple[Line, ...] = (
    Line(NARRATOR, "…"),
    Line(NARRATOR, "Silencio."),
    Line(NARRATOR, "Un silencio de los que se notan."),
)


# ---------------------------------------------------------------------------
# Sendero del blues
#
# Los personajes no saben cómo se llaman las pantallas de este programa: no
# viven acá. Ellos dicen qué quieren escuchar --- «tres acordes, en este
# orden» --- y el programa, por su cuenta, dice dónde se escribe eso. Es la
# diferencia entre alguien hablándote y un tutorial disfrazado.
# ---------------------------------------------------------------------------

_BLUES = Path(
    "blues", "El sendero del Blues", "El destino aún es incierto…",
    DEVIL, award="blues_pact",
    keepsake="El sombrero de ala ancha", keepsake_icon="🎩",
    steps=(
        Step(
            "blues_cadence", "manual",
            "Tres puertas abiertas",
            "Escribí tres acordes seguidos: C7, F7 y G7. Después generá la "
            "partitura y escuchala.",
            "Es en el Organizador, el modo donde vos ponés los acordes. "
            "Escribí «C7» en el primer compás, «F7» en el segundo y «G7» en "
            "el tercero; el resto llenalo con lo que quieras y dale a "
            "Siguiente hasta generar.",
            intro=(
                Line(DEVIL, "Bien. Dame la mano.", pose="normal"),
                Line(DEVIL, "Ya está. No hubo humo ni truenos: los tratos de "
                            "verdad se hacen en silencio.", cue="shake",
                     pose="siniestro"),
                Line(DEVIL, "Ahora vas a escribir tres acordes. Nada más que "
                            "tres, pero puestos en el orden exacto.",
                     pose="normal"),
                Line(DEVIL, "Se escriben así: C7, F7 y G7. Uno atrás del "
                            "otro, cada uno en su compás."),
                Line(DEVIL, "Ese siete que va al lado de la letra no es un "
                            "adorno. Es una nota que no termina de cerrar, "
                            "que deja la puerta abierta.", pose="perfil"),
                Line(DEVIL, "Tres puertas abiertas seguidas. Eso es lo que "
                            "nadie se anima a escribir.", pose="normal"),
                Line(DEVIL, "Escribilas, y después escuchá lo que sale. Eso "
                            "último no te lo saltees."),
                Line(DEVIL, "Yo te espero acá."),
            ),
            outro=(
                Line(DEVIL, "Ahí está. ¿Lo escuchaste?", pose="siniestro"),
                Line(DEVIL, "Eso que sonó no lo escribiste vos. Estaba "
                            "esperando que alguien pusiera las tres puertas "
                            "en fila.", pose="normal"),
                Line(DEVIL, "Descubriste el poder. Felicitaciones."),
                Line(DEVIL, "Ahora viene lo otro, que es lo difícil: hay que "
                            "dominarlo.", pose="perfil"),
            ),
        ),
        Step(
            "blues_twelve", "random",
            "La rueda",
            "Buscá el botón dorado.",
            "Es en el Generador, el modo donde el programa arma la "
            "progresión. El botón está arriba de todo, en la primera "
            "pantalla: la de estilo.",
            gate=GATE_BLUES_BOOK,
            locked_text="Leé en el libro lo que quedó anotado del pacto",
            ready_text="★  La rueda de doce compases",
            intro=(
                Line(DEVIL, "Tres acordes son una llave. Doce compases son "
                            "una casa.", pose="normal"),
                Line(DEVIL, "Y en esa casa entró todo el mundo después. Lo "
                            "que estén tocando ahora mismo en algún lugar "
                            "salió de ahí, aunque no lo sepan."),
                Line(DEVIL, "Te la voy a dar entera. Sin que tengas que "
                            "pensarla.", pose="siniestro"),
            ),
            task=(
                Line(DEVIL, "Pero antes vas a leer lo que acaba de quedar "
                            "escrito sobre lo que hiciste.", pose="normal"),
                Line(DEVIL, "Nadie usa una llave sin saber qué puerta abre. "
                            "Los que no leyeron terminaron todos igual.",
                     pose="perfil"),
                Line(DEVIL, "Cuando lo hayas leído, va a haber algo dorado "
                            "esperándote. No te lo vas a poder perder."),
            ),
            outro=(
                Line(DEVIL, "Doce compases. Ni uno más.", pose="normal"),
                Line(DEVIL, "Fijate que vuelve al principio siempre. Nunca "
                            "termina de verdad: da la vuelta y arranca otra "
                            "vez."),
                Line(DEVIL, "Así se toca toda la noche sin repetir nada y sin "
                            "irse nunca.", pose="siniestro"),
                Line(DEVIL, "Rechazá la idea del mundo viejo, la de que la "
                            "música se estudia veinte años antes de decir "
                            "algo.", pose="perfil"),
                Line(DEVIL, "Nosotros vamos a ser los dueños del mundo "
                            "nuevo.", pose="normal"),
            ),
        ),
        Step(
            "blues_note", "harmonise",
            "La que no existe",
            "Tocá la tecla dorada.",
            "Es en el Armonizador, el modo donde vos dibujás una melodía. "
            "Una tecla del piano de abajo va a estar titilando: es la única "
            "que hay que tocar.",
            gate=GATE_BLUES_BOOK2,
            locked_text="Leé en el libro lo que quedó anotado de la rueda",
            ready_text="★  La que no existe",
            intro=(
                Line(DEVIL, "Falta una sola nota. La que no está en ninguna "
                            "escala.", pose="normal"),
                Line(DEVIL, "Queda justo en el medio, entre dos notas que sí "
                            "existen. Un lugar donde no debería haber nada."),
                Line(DEVIL, "Los que enseñan te van a decir que está "
                            "desafinada. Tienen razón. Por eso funciona.",
                     pose="siniestro"),
            ),
            task=(
                Line(DEVIL, "Otra vez: primero leé. Ya quedó anotado lo de "
                            "los doce compases.", pose="normal"),
                Line(DEVIL, "Nadie toca esa nota sin saber a quién se la está "
                            "robando.", pose="perfil"),
            ),
        ),
    ),
    finale=(
        Line(DEVIL, "Eso fue. No hay más.", pose="normal"),
        Line(DEVIL, "Lo que acabás de escuchar ya no es mío ni tuyo: es de "
                    "cualquiera que lo escuche una vez."),
        Line(DEVIL, "Tomá. Te lo dejo.", cue="item", pose="siniestro"),
        Line(NARRATOR, "Te pone el sombrero en la cabeza. Pesa más de lo que "
                       "debería."),
        Line(DEVIL, "Sobre el precio no te preocupes hoy.", pose="normal"),
        Line(DEVIL, "Nos vemos el día de tu muerte. No antes.",
             pose="siniestro"),
        Line(NARRATOR, "Y se va como vino, sin apuro, sin ruido."),
    ),
)


# ---------------------------------------------------------------------------
# Sendero del jazz
# ---------------------------------------------------------------------------

_JAZZ = Path(
    "jazz", "El sendero del Jazz", "El destino aún es incierto…",
    DJANGO, award="the_lick",
    keepsake="La guitarra de Django", keepsake_icon="🎸",
    steps=(
        Step(
            "jazz_two_five", "manual",
            "Dos acordes",
            "Escribí dos acordes seguidos: Dm7 y G7, en estilo jazz. "
            "Después generá la partitura y escuchala.",
            "Es en el Organizador, el modo donde vos ponés los acordes. "
            "Elegí el estilo Jazz, escribí «Dm7» en el primer compás y «G7» "
            "en el segundo, llená el resto con lo que quieras y generá.",
            intro=(
                Line(NARRATOR, "Al rato hay alguien más en la puerta. Trae "
                               "una guitarra y no la suelta."),
                Line(DJANGO, "Perdón. No quise interrumpir.", pose="quieto"),
                Line(DJANGO, "Vi todo desde afuera. Hiciste bien en no "
                             "contestarle.", pose="normal"),
                Line(DJANGO, "A ese señor lo conozco. Le ofrece a todo el "
                             "mundo lo mismo y nunca dice cuánto sale."),
                Line(DJANGO, "Yo no te vengo a regalar nada. Te vengo a "
                             "mostrar cómo se hace.", pose="feliz"),
                Line(DJANGO, "Empecemos por lo más chico que existe: dos "
                             "acordes.", pose="normal"),
                Line(DJANGO, "Se escriben Dm7 y G7, en ese orden. Uno tira "
                             "para adelante y el otro cae."),
                Line(DJANGO, "Escribilos, ponelo en jazz, y escuchá cómo "
                             "caen. Escucharlo es la mitad del asunto.",
                     pose="feliz"),
            ),
            outro=(
                Line(DJANGO, "Eso es. Eso es todo.", pose="feliz"),
                Line(DJANGO, "Dos acordes. En medio mundo la música empieza "
                             "y termina ahí.", pose="normal"),
                Line(DJANGO, "Lo que acabás de hacer se llama swing, aunque "
                             "no lo hayas escrito en ningún lado."),
                Line(DJANGO, "Está en tus manos ahora. Y teniéndolo, no hay "
                             "nada que no se pueda hacer.", pose="feliz"),
            ),
        ),
        Step(
            "jazz_standard", "random",
            "Una canción entera",
            "Buscá el botón dorado.",
            "Es en el Generador, el modo donde el programa arma la "
            "progresión. El botón está arriba de todo, en la primera "
            "pantalla: la de estilo.",
            gate=GATE_JAZZ_BOOK,
            locked_text="Leé en el libro lo que quedó anotado de los jazzes",
            ready_text="★  Una canción que sabe todo el mundo",
            intro=(
                Line(DJANGO, "Ahora una canción entera. Una que sepa todo el "
                             "mundo.", pose="normal"),
                Line(DJANGO, "En esto nadie empieza inventando. Todos "
                             "empezamos tocando lo mismo que ya tocaron "
                             "otros, hasta que un día sale distinto.",
                     pose="quieto"),
            ),
            task=(
                Line(DJANGO, "Pero antes andá a leer. Quedó anotado que el "
                             "jazz no es uno solo.", pose="normal"),
                Line(DJANGO, "El mío es de guitarras y sin batería. Hay "
                             "otros, y conviene saber cuál es cuál antes de "
                             "meterse.", pose="quieto"),
                Line(DJANGO, "Cuando lo leas, algo dorado te va a estar "
                             "esperando.", pose="feliz"),
            ),
            outro=(
                Line(DJANGO, "Treinta y dos compases. Así son casi todas.",
                     pose="normal"),
                Line(DJANGO, "Fijate cuántas veces aparece el par que "
                             "aprendiste al principio. Está por todos lados.",
                     pose="feliz"),
                Line(DJANGO, "Todo empieza por el estándar. Uno lo toca mil "
                             "veces igual.", pose="normal"),
                Line(DJANGO, "Y la vez mil uno sale otra cosa, y esa otra "
                             "cosa es lo más lejos que puede llegar una "
                             "persona.", pose="feliz"),
            ),
        ),
        Step(
            "jazz_lick", "harmonise",
            "Siete notas",
            "Tocá la tecla dorada.",
            "Es en el Armonizador, el modo donde vos dibujás una melodía. "
            "Una tecla del piano de abajo va a estar titilando.",
            gate=GATE_JAZZ_BOOK2,
            locked_text="Leé en el libro lo que quedó anotado del estándar",
            ready_text="★  Siete notas",
            intro=(
                Line(DJANGO, "Queda una cosa sola y es una pavada.",
                     pose="feliz"),
                Line(DJANGO, "Siete notas. Las toca todo el mundo, siempre, "
                             "desde hace cien años.", pose="normal"),
                Line(DJANGO, "Es un chiste interno, pero es un chiste que "
                             "sabe todo el planeta, y eso ya no es un "
                             "chiste.", pose="feliz"),
            ),
            task=(
                Line(DJANGO, "Pasá otra vez por el libro. Quedó anotado lo "
                             "del estándar.", pose="normal"),
                Line(DJANGO, "Si no sabés de dónde viene una canción, la "
                             "tocás igual. Pero no es lo mismo.",
                     pose="quieto"),
            ),
        ),
    ),
    finale=(
        Line(DJANGO, "Ahí está. Escuchá cómo cierra.", pose="feliz"),
        Line(NARRATOR, "El último acorde llega tarde a propósito, y se queda."),
        Line(DJANGO, "Ese silencio antes del final es la mitad de la frase.",
             pose="normal"),
        Line(DJANGO, "Estoy orgulloso de vos. Lo digo en serio.",
             pose="feliz"),
        Line(DJANGO, "Tomá, quedátela.", cue="item", pose="guitarra"),
        Line(NARRATOR, "Te da la guitarra. Le faltan cuerdas y está gastada "
                       "en el mismo lugar de siempre."),
        Line(DJANGO, "Me llamo Django. Django Reinhardt.", cue="reveal",
             pose="normal"),
        Line(DJANGO, "Toqué toda mi vida con dos dedos que no me respondían. "
                     "No lo digo por lástima: lo digo porque vos también vas "
                     "a tener algo que no te responda.", pose="quieto"),
        Line(DJANGO, "Buena suerte. La vas a necesitar menos de lo que "
                     "creés.", pose="feliz"),
    ),
)


# ---------------------------------------------------------------------------
# Sendero del góspel
# ---------------------------------------------------------------------------

_GOSPEL = Path(
    "gospel", "El sendero del Gospel", "El destino aún es incierto…",
    JESUS, award="second_coming",
    keepsake="El Sagrado Corazón de Jesús", keepsake_icon="❤",
    steps=(
        Step(
            "gospel_plagal", "manual",
            "El amén",
            "Escribí dos acordes seguidos: F y C. Después generá la partitura "
            "y escuchala.",
            "Es en el Organizador, el modo donde vos ponés los acordes. "
            "Escribí «F» en el primer compás y «C» en el segundo, llená el "
            "resto con lo que quieras y generá.",
            intro=(
                Line(NARRATOR, "Donde había oscuridad se abre una luz que no "
                               "viene de ninguna ventana."),
                Line(JESUS, "Hijo mío.", pose="sereno"),
                Line(JESUS, "Tu valentía no ha pasado desapercibida.",
                     pose="normal"),
                Line(JESUS, "Otros aceptaron. Otros miraron para otro lado. "
                            "Vos lo miraste a la cara y le dijiste que no."),
                Line(JESUS, "Dejame llevarte por el camino, la verdad y la "
                            "vida.", pose="feliz"),
                Line(JESUS, "Vamos a empezar por lo último que se canta y lo "
                            "primero que se aprende: el amén.", pose="normal"),
                Line(JESUS, "Son dos acordes. Se escriben F y C, en ese "
                            "orden."),
                Line(JESUS, "No empuja como los otros. No pide nada. Sólo "
                            "apoya y descansa.", pose="sereno"),
                Line(JESUS, "Escribilos, y quedate a escucharlos.",
                     pose="normal"),
            ),
            outro=(
                Line(JESUS, "Bien hecho, hijo mío.", pose="feliz"),
                Line(JESUS, "Eso que sonó lo cantaron millones de personas "
                            "que nunca supieron leer una nota.", pose="normal"),
                Line(JESUS, "No hace falta saber. Hace falta estar.",
                     pose="sereno"),
                Line(JESUS, "Es hora de que te unas a tus hermanos en la "
                            "música.", pose="feliz"),
            ),
        ),
        Step(
            "gospel_octave", "random",
            "La escalera",
            "Buscá el botón dorado.",
            "Es en el Generador, el modo donde el programa arma la "
            "progresión. El botón está arriba de todo, en la primera "
            "pantalla: la de estilo.",
            gate=GATE_GOSPEL_BOOK,
            locked_text="Leé en el libro lo que quedó anotado del góspel",
            ready_text="★  La escalera",
            intro=(
                Line(JESUS, "Ahora una escalera.", pose="normal"),
                Line(JESUS, "El bajo baja de a un escalón, sin saltarse "
                            "ninguno, desde arriba hasta abajo del todo."),
                Line(JESUS, "Y arriba de cada escalón hay un acorde "
                            "esperándolo. Eso solo ya es una canción entera.",
                     pose="sereno"),
            ),
            task=(
                Line(JESUS, "Antes andá a leer. Quedó anotado de dónde salió "
                            "esta música y quiénes la cantaban.",
                     pose="normal"),
                Line(JESUS, "No es un dato. Es a quién le estás pidiendo "
                            "prestado.", pose="sereno"),
                Line(JESUS, "Cuando lo leas, algo dorado te va a estar "
                            "esperando.", pose="feliz"),
            ),
            outro=(
                Line(JESUS, "Escuchá cómo camina el bajo.", pose="sereno"),
                Line(JESUS, "Nueve acordes y ninguno se luce. Cada uno "
                            "sostiene al siguiente.", pose="normal"),
                Line(JESUS, "La música no se trata de saber ni de ganar."),
                Line(JESUS, "Se trata de vivir, y de ser.", pose="feliz"),
            ),
        ),
        Step(
            "gospel_grace", "harmonise",
            "La gracia",
            "Tocá cualquier tecla del piano dorado.",
            "Es en el Armonizador, el modo donde vos dibujás una melodía. El "
            "piano de abajo va a estar entero en dorado: cualquier tecla "
            "sirve.",
            gate=GATE_GOSPEL_BOOK2,
            locked_text="Leé en el libro lo que quedó anotado de la escalera",
            ready_text="★  La gracia",
            intro=(
                Line(JESUS, "Falta una canción.", pose="normal"),
                Line(JESUS, "La escribió un hombre que había hecho cosas muy "
                            "graves, cuando entendió que igual lo perdonaban.",
                     pose="sereno"),
                Line(JESUS, "La cantan en los entierros y en los casamientos. "
                            "Sirve para las dos cosas."),
                Line(JESUS, "No importa qué toques. Con cualquier cosa "
                            "alcanza. Eso también es parte de lo que te "
                            "quiero enseñar.", pose="feliz"),
            ),
            task=(
                Line(JESUS, "Volvé al libro una vez más. Quedó anotado lo de "
                            "la escalera.", pose="normal"),
                Line(JESUS, "Es la última vez que te lo pido.", pose="sereno"),
            ),
        ),
    ),
    finale=(
        Line(JESUS, "Ahí está.", pose="feliz"),
        Line(JESUS, "No la tocaste vos. La tocaron todos los que la cantaron "
                    "antes, y vos les prestaste las manos.", pose="normal"),
        Line(JESUS, "Creciste mucho, hijo mío. Más de lo que te das cuenta.",
             pose="sereno"),
        Line(JESUS, "Llevate esto.", cue="item", pose="feliz"),
        Line(NARRATOR, "Algo tibio te queda en el pecho. No pesa."),
        Line(JESUS, "Cuando no sepas qué escribir, acordate de que la música "
                    "ya estaba antes que vos y va a estar después.",
             pose="normal"),
        Line(JESUS, "Andá en paz.", pose="feliz"),
    ),
)


PATHS: Dict[str, Path] = {p.key: p for p in (_BLUES, _JAZZ, _GOSPEL)}

#: Los tres finales, para poder preguntar si un logro le pertenece a un
#: sendero sin recorrer el catálogo entero.
PATH_AWARDS: Dict[str, str] = {p.award: p.key for p in PATHS.values()}


# ---------------------------------------------------------------------------
# Las piezas fijas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Piece:
    """
    Una pieza escrita de antemano, lista para escribirse sin buscar nada.

    ``chords`` son pares ``(cifrado, duración en negras)``; un cifrado vacío
    es un silencio. ``melody`` son ternas ``(altura MIDI, comienzo en negras,
    duración en negras)`` y puede estar vacía.
    """

    title: str
    genre_key: str
    time_signature: str
    chords: Tuple[Tuple[str, float], ...]
    melody: Tuple[Tuple[int, float, float], ...] = ()
    #: Nota que cada acorde le pone a la voz más aguda, cuando hay melodía.
    #: ``None`` deja que la voz caiga donde caiga.
    tops: Tuple[Optional[int], ...] = ()
    blurb: str = ""
    #: Cuánto dura una negra al escucharla. El valor de la casa --- 0,625,
    #: unos noventa y seis por minuto --- está pensado para poder seguir la
    #: conducción de cuatro voces con el oído. Estas piezas no se escuchan
    #: para eso: se escuchan como música, y a ese tempo *All of Me* dura un
    #: minuto y medio de acordes larguísimos. Cada una trae el suyo.
    quarter_seconds: float = 0.42

    @property
    def quarters_per_bar(self) -> float:
        beats, _, beat_type = self.time_signature.partition("/")
        return int(beats) * 4.0 / int(beat_type or 4)

    def bar_indices(self) -> List[int]:
        """En qué compás cae cada acorde."""
        per_bar = self.quarters_per_bar
        indices, position = [], 0.0
        for _symbol, duration in self.chords:
            indices.append(int(position / per_bar + 1e-9))
            position += duration
        return indices

    @property
    def bar_count(self) -> int:
        total = sum(duration for _symbol, duration in self.chords)
        return max(1, int(round(total / self.quarters_per_bar)))


def _transpose(symbol: str, semitones: int) -> str:
    """
    Subir un cifrado, incluyendo su bajo cuando lleva barra.

    Sólo se mueve la letra: el resto del cifrado --- la calidad, las cifras,
    las alteraciones de las tensiones --- no depende de la altura.
    """
    if not symbol:
        return symbol
    root, _, bass = symbol.partition("/")
    moved = _transpose_root(root, semitones)
    if bass:
        moved += "/" + _transpose_root(bass, semitones)
    return moved


_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _transpose_root(text: str, semitones: int) -> str:
    if not text:
        return text
    letter = text[0].upper()
    if letter not in _LETTERS:
        return text
    pc = _LETTERS[letter]
    rest = text[1:]
    while rest[:1] in ("#", "b"):
        pc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return SHARP_NAMES[(pc + semitones) % 12] + rest


def transposed(piece: Piece, semitones: int) -> Piece:
    """La misma pieza, corrida de altura. Cero devuelve la original."""
    if semitones % 12 == 0:
        return piece
    step = semitones % 12
    return Piece(
        title=piece.title,
        genre_key=piece.genre_key,
        time_signature=piece.time_signature,
        chords=tuple((_transpose(symbol, step), duration)
                     for symbol, duration in piece.chords),
        melody=tuple((pitch + step, start, length)
                     for pitch, start, length in piece.melody),
        tops=tuple(None if top is None else top + step for top in piece.tops),
        quarter_seconds=piece.quarter_seconds,
        blurb=piece.blurb,
    )


def _bars(*rows: Tuple[str, ...]) -> Tuple[Tuple[str, float], ...]:
    """Un compás de 4/4 por cifrado suelto; dos negras y media por par."""
    out: List[Tuple[str, float]] = []
    for row in rows:
        for symbol in row:
            out.append((symbol, 4.0))
    return tuple(out)


#: Los doce compases, en do. Con el cambio rápido al cuarto grado en el
#: segundo compás y el giro de vuelta en el último, que es lo que hace que la
#: rueda no pare nunca.
TWELVE_BAR_BLUES = Piece(
    title="Doce compases",
    genre_key="jazz",
    time_signature="4/4",
    chords=_bars(("C7", "F7", "C7", "C7"),
                 ("F7", "F7", "C7", "C7"),
                 ("G7", "F7", "C7", "G7")),
    quarter_seconds=0.34,
    blurb="Los doce compases del blues, con el cambio rápido y el giro final.",
)

#: *All of Me* (Gerald Marks y Seymour Simons, 1931). Se escriben los
#: acordes, que son un esquema y no una melodía: la canción se reconoce por
#: cómo se encadenan, y eso es justamente lo que el sendero quiere mostrar.
ALL_OF_ME = Piece(
    title="El estándar",
    genre_key="jazz",
    time_signature="4/4",
    chords=_bars(("C6", "C6", "E7", "E7"),
                 ("A7", "A7", "Dm7", "Dm7"),
                 ("E7", "E7", "Am7", "Am7"),
                 ("D7", "D7", "Dm7", "G7"),
                 ("C6", "C6", "E7", "E7"),
                 ("A7", "A7", "Dm7", "Dm7"),
                 ("F6", "Fm6", "C6", "A7"),
                 ("Dm7", "G7", "C6", "C6")),
    # Bien rápido: son treinta y dos compases de acordes en bloque, y a un
    # tempo de estudio se vuelven un ejercicio de paciencia en vez de una
    # canción.
    quarter_seconds=0.13,
    blurb="Treinta y dos compases con la forma de siempre: A A B A.",
)

#: La regla de la octava del góspel: el bajo baja un escalón por acorde,
#: desde la tónica hasta la tónica de abajo, y arriba de cada escalón hay un
#: acorde que lo sostiene.
GOSPEL_OCTAVE = Piece(
    title="La regla de la octava",
    genre_key="classical",
    time_signature="4/4",
    chords=(("C", 2.0), ("G/B", 2.0), ("C7/Bb", 2.0), ("F/A", 2.0),
            ("Fm/Ab", 2.0), ("C/G", 2.0), ("D7/F#", 2.0), ("G", 2.0),
            ("C", 4.0)),
    quarter_seconds=0.46,
    blurb="Nueve acordes sobre un bajo que baja de a un escalón.",
)

#: The Lick, y el reposo que llega tarde.
#:
#: La frase suena sola --- sin nada abajo --- y recién después, con un compás
#: entero de silencio en el medio, entra el único acorde de la pieza. Es el
#: gesto que pide el sendero: la armonía es sólo ese acorde final, y dura una
#: redonda.
THE_LICK_PIECE = Piece(
    title="La frase",
    genre_key="jazz",
    time_signature="4/4",
    chords=(("", 4.0), ("", 4.0), ("Cmaj7", 4.0)),
    # Cuatro corcheas subiendo, la negra en el medio, y las dos corcheas que
    # bajan a cerrar. Ese es el ritmo, y es la mitad de por qué la frase se
    # reconoce: repartida en corcheas parejas deja de ser el lick y pasa a
    # ser una escala.
    melody=((62, 0.0, 0.5), (64, 0.5, 0.5), (65, 1.0, 0.5), (67, 1.5, 0.5),
            (64, 2.0, 1.0), (60, 3.0, 0.5), (62, 3.5, 0.5)),
    tops=(None, None, 71),
    quarter_seconds=0.30,
    blurb="Siete notas y un acorde que llega tarde a propósito.",
)

#: *Amazing Grace* (melodía «New Britain», 1835), en sol y en tres tiempos.
#: El primer compás lleva la anacrusa: dos tiempos de silencio y la nota con
#: la que se entra.
AMAZING_GRACE = Piece(
    title="Amazing Grace",
    genre_key="classical",
    time_signature="3/4",
    chords=(("", 2.0), ("G", 1.0),
            ("G", 3.0),
            ("G", 2.0), ("D7", 1.0),
            ("C", 3.0),
            ("G", 2.0), ("D7", 1.0),
            ("G", 3.0),
            ("G", 2.0), ("D7", 1.0),
            ("G", 3.0),
            ("G", 3.0)),
    melody=((62, 2.0, 1.0),
            (67, 3.0, 2.0), (71, 5.0, 0.5), (67, 5.5, 0.5),
            (71, 6.0, 2.0), (69, 8.0, 1.0),
            (67, 9.0, 2.0), (64, 11.0, 1.0),
            (62, 12.0, 2.0), (62, 14.0, 1.0),
            (67, 15.0, 2.0), (71, 17.0, 0.5), (67, 17.5, 0.5),
            (71, 18.0, 2.0), (69, 20.0, 1.0),
            (74, 21.0, 2.0), (71, 23.0, 1.0),
            (67, 24.0, 3.0)),
    tops=(None, 62, 67, 71, 69, 67, 62, 62, 67, 71, 69, 74, 67),
    quarter_seconds=0.50,
    blurb="Las dos primeras frases, tal como se cantan.",
)


# ---------------------------------------------------------------------------
# Escribir una pieza a varias voces
# ---------------------------------------------------------------------------
#
# Las piezas del relato no se buscan: están escritas. Lo que hace falta es
# repartirlas entre las voces una sola vez, bien, y pasárselas al motor con
# el candado puesto --- así el resultado es instantáneo y siempre el mismo.
#
# Por qué no alcanza con `session.default_locked_voicing`: ése voicea cada
# acorde en el vacío, sin mirar el anterior, así que una rueda de blues sale
# con las voces saltando en cada compás. Y cuando hay melodía, pisarle la
# nota a la voz más aguda le saca al acorde el grado que esa voz estaba
# cantando --- normalmente la séptima --- y el acorde deja de ser el acorde,
# que es una restricción dura del motor.
#
# Lo de acá abajo reparte los grados primero y elige las octavas después,
# acercando cada voz a donde estaba en el acorde anterior.

#: En qué orden se doblan los grados cuando sobran voces: la fundamental
#: primero, después la quinta. La tercera y la séptima no se doblan --- son
#: las que definen el acorde y duplicarlas lo empasta.
_DOUBLING_ROLES = (ROLE_ROOT, ROLE_FIFTH)


def _degree_classes(requirement) -> List[int]:
    """Las clases de altura que el acorde tiene que hacer sonar."""
    return list(requirement.required_pitch_classes)


def _assign_classes(requirement, count: int, top_pc: Optional[int]
                    ) -> Optional[Tuple[List[int], Set[int]]]:
    """
    Qué grado canta cada voz, de grave a agudo.

    Devuelve también qué voces quedaron **libres**: las que no llevan un
    grado obligatorio sino una duplicación. Esas se pueden reasignar al
    colocarlas, y eso es lo que salva el caso incómodo --- una voz interna a
    la que le tocó doblar la fundamental cuando entre sus vecinas no hay
    ninguna fundamental que quepa.

    Devuelve ``None`` cuando la nota impuesta arriba no deja lugar para
    todos los grados obligatorios: en ese caso el que llama vuelve a probar
    sin ella, porque un acorde incompleto no es el acorde que se pidió.
    """
    chord = requirement.chord
    bass_pc = (requirement.bass_pitch_class
               if requirement.bass_pitch_class is not None
               else (chord.bass_pc if chord.bass_pc is not None
                     else chord.root_pc)) % 12

    pool = _degree_classes(requirement)
    classes: List[Optional[int]] = [None] * count
    classes[0] = bass_pc
    if bass_pc in pool:
        pool.remove(bass_pc)
    if top_pc is not None:
        classes[count - 1] = top_pc
        if top_pc in pool:
            pool.remove(top_pc)

    free: Set[int] = set()
    for index in range(1, count):
        if classes[index] is not None:
            continue
        if pool:
            classes[index] = pool.pop(0)
            continue
        # Sobran voces: se dobla, empezando por la fundamental. Queda
        # marcada como libre, así que si esa nota no entra en el hueco se
        # puede cambiar por otra del acorde sin romper nada.
        free.add(index)
        for role in _DOUBLING_ROLES:
            tone = next((t for t in chord.tones if t.role == role), None)
            if tone is not None:
                classes[index] = chord.pitch_class_of(tone) % 12
                break
        if classes[index] is None:
            classes[index] = bass_pc
    if pool:
        return None           # quedaron grados obligatorios sin cantar
    return [pc for pc in classes if pc is not None], free


def _place(classes: Sequence[int], voices, previous: Optional[Sequence[int]],
           top: Optional[int], free: Optional[Set[int]] = None,
           allowed: Sequence[int] = ()) -> List[int]:
    """
    Elegir la octava de cada grado, de grave a agudo.

    Cada voz se queda con la altura de su grado que menos se aleja de donde
    estaba esa misma voz en el acorde anterior, sin salirse de su registro,
    sin pasar por debajo de la voz de abajo y sin pasar por encima de la
    nota de melodía cuando la hay.

    Una voz **libre** --- las que doblan --- puede además cambiar de grado si
    el que le tocó no le entra en el hueco. Es lo que evita el caso en que
    una voz interna tiene que doblar la fundamental y entre sus dos vecinas
    no hay ninguna fundamental posible.
    """
    count = len(classes)
    free = free or set()
    pitches: List[int] = []
    for index, pc in enumerate(classes):
        if top is not None and index == count - 1:
            pitches.append(top)
            continue
        part = voices[index]
        if previous is not None and index < len(previous):
            target = previous[index]
        else:
            # Sin acorde anterior, el bajo se apoya abajo y el resto en el
            # medio de su registro: es de donde salen las voces cómodas.
            target = (part.low + (part.high - part.low) // 3 if index == 0
                      else (part.low + part.high) // 2)

        options = [pc]
        if index in free:
            options += [other for other in allowed if other % 12 != pc % 12]
        chosen = None
        for candidate_pc in options:
            candidates = part.candidates_for_pitch_class(candidate_pc % 12)
            usable = [m for m in candidates if not pitches or m > pitches[-1]]
            if top is not None:
                usable = [m for m in usable if m < top]
            if usable:
                chosen = min(usable, key=lambda m: (abs(m - target), m))
                break
        if chosen is None:
            candidates = part.candidates_for_pitch_class(pc % 12) or [part.low]
            chosen = min(candidates, key=lambda m: (abs(m - target), m))
        pitches.append(chosen)
    return pitches


def _covers(pitches: Sequence[int], requirement) -> bool:
    sounded = {p % 12 for p in pitches}
    return all(pc % 12 in sounded for pc in requirement.required_pitch_classes)


def _ordered(pitches: Sequence[int], voices) -> bool:
    if any(not part.low <= pitch <= part.high
           for part, pitch in zip(voices, pitches)):
        return False
    return all(pitches[i] < pitches[i + 1] for i in range(len(pitches) - 1))


def voice_chord(requirement, voices, previous: Optional[Sequence[int]],
                top: Optional[int]) -> List[int]:
    """
    Un acorde repartido entre las voces, completo y sin cruces.

    Se intenta primero con la nota de melodía arriba. Si esa nota no es del
    acorde, o si con ella no entran todos los grados obligatorios, se
    escribe el acorde sin ella: la melodía viaja aparte y se sigue oyendo
    igual, mientras que un acorde al que le falta la séptima ya no es el
    acorde que la pieza dice.
    """
    wanted = top
    if wanted is not None:
        part = voices[-1]
        if not part.low <= wanted <= part.high:
            wanted = None
        elif wanted % 12 not in {pc % 12
                                 for pc in requirement.allowed_pitch_classes}:
            wanted = None
    allowed = list(requirement.allowed_pitch_classes)
    for pitch_top in (wanted, None):
        best = _best_arrangement(requirement, voices, previous, pitch_top,
                                 allowed)
        if best is not None:
            return best
    # Último recurso: el reparto tal como salió, sin comprobar nada. Puede no
    # ser elegante, pero un acorde siempre es mejor que ninguno.
    fallback = _assign_classes(requirement, len(voices), None)
    classes, free = (fallback if fallback is not None
                     else ([requirement.chord.root_pc] * len(voices), set()))
    return _place(classes, voices, previous, None, free, allowed)


def _best_arrangement(requirement, voices, previous, pitch_top,
                      allowed) -> Optional[List[int]]:
    """
    El mejor reparto de este acorde, probando todos los órdenes internos.

    A qué voz le toca la tercera y a cuál la duplicación no es indiferente:
    con la melodía puesta arriba, un orden entra y el otro deja a una voz
    interna sin ninguna nota posible entre sus vecinas. Las voces internas
    son dos o tres, así que probar los seis órdenes cuesta menos que
    razonarlo, y de los que quedan bien se elige el que menos mueve las
    voces respecto del acorde anterior.
    """
    class_top = pitch_top % 12 if pitch_top is not None else None
    assigned = _assign_classes(requirement, len(voices), class_top)
    if assigned is None:
        return None
    classes, _free = assigned
    head = classes[0]
    tail = classes[-1] if pitch_top is not None else None
    middles = classes[1:-1] if pitch_top is not None else classes[1:]

    best: Optional[Tuple[int, List[int]]] = None
    for order in sorted(set(permutations(middles))):
        trial = [head] + list(order) + ([tail] if tail is not None else [])
        # Toda voz interna puede cambiar de grado si el suyo no le entra; la
        # comprobación de cobertura de más abajo es la que impide que ese
        # cambio le saque al acorde una nota que necesitaba.
        free = set(range(1, 1 + len(order)))
        pitches = _place(trial, voices, previous, pitch_top, free, allowed)
        if not _ordered(pitches, voices) or not _covers(pitches, requirement):
            continue
        if previous is not None and len(previous) == len(pitches):
            score = sum(abs(a - b) for a, b in zip(pitches, previous))
        else:
            score = pitches[-1] - pitches[0]
        if best is None or score < best[0]:
            best = (score, pitches)
    return best[1] if best is not None else None


def voice_piece(piece: Piece, voice_keys: Sequence[str]
                ) -> List[Optional[List[int]]]:
    """
    Toda la pieza repartida entre las voces, acorde por acorde.

    Devuelve una altura por voz para cada acorde, y ``None`` en los
    silencios. Es lo que va al candado de cada slot.
    """
    voices = build_voice_parts(list(voice_keys))
    tops = piece.tops or (None,) * len(piece.chords)
    written: List[Optional[List[int]]] = []
    previous: Optional[List[int]] = None
    for index, (symbol, _duration) in enumerate(piece.chords):
        if not symbol:
            written.append(None)
            continue
        chord = parse_chord(symbol)
        # Exactamente el mismo requerimiento que va a armar `session` cuando
        # corra la pieza: si acá se calculara otro, el voicing cubriría un
        # acorde y el motor estaría pidiendo otro.
        requirement = build_requirement(
            chord, len(voices), chord_omissions(piece, symbol) or None,
            allow_major_sixth_on_minor=(piece.genre_key == "jazz"),
            colour_appetite=0.0)
        top = tops[index] if index < len(tops) else None
        pitches = voice_chord(requirement, voices, previous, top)
        written.append(pitches)
        previous = pitches
    return written


#: Con cuántas voces se escribe una pieza del relato. Siempre cuatro: es la
#: textura que el programa usa por defecto y la que hace que la partitura
#: exportada se lea como cualquier otra.
PIECE_VOICES: Tuple[str, ...] = ("B", "T", "A", "S")


def voices_for(_piece: Piece) -> List[str]:
    return list(PIECE_VOICES)


def chord_omissions(piece: Piece, symbol: str) -> List[str]:
    """
    Qué grado se deja sin cantar en este acorde.

    Con melodía y cuatro voces, un acorde de séptima no entra: la voz más
    aguda la ocupa la melodía y quedan tres para cuatro grados obligatorios,
    así que la séptima se queda sin quién la cante y el motor rechaza el
    acorde por incompleto.

    La salida no es agregar una quinta voz sino sacar la quinta del acorde,
    que es lo que hace cualquier pianista: de un acorde de séptima, la quinta
    es lo primero que sobra --- no dice nada que la fundamental no diga ya ---
    mientras que la tercera y la séptima son las dos notas que definen de qué
    acorde se trata.
    """
    if not piece.melody or not symbol:
        return []
    chord = parse_chord(symbol)
    if any(tone.role == ROLE_SEVENTH for tone in chord.tones):
        return ["5"]
    return []


#: Las reglas duras que una pieza escrita de antemano no tiene por qué
#: cumplir. Un blues de doce compases mueve las voces en paralelo, la regla
#: de la octava del góspel también, y el tritono es la mitad de lo que dice
#: un acorde de séptima de dominante: son la música, no un error. El motor
#: las apagaría igual si el usuario tocara los interruptores, así que esto no
#: es un camino aparte --- es la misma configuración, puesta por el relato.
FIXED_PIECE_RULES: Dict[str, bool] = {
    "forbid_parallel_fifths": False,
    "forbid_parallel_octaves": False,
    "forbid_melodic_tritone": False,
    "forbid_harmonic_tritone": False,
    "forbid_voice_crossing": False,
    "cadence_consonance_required": False,
}


# ---------------------------------------------------------------------------
# Lo que se lee sobre el negro
# ---------------------------------------------------------------------------

#: La línea que aparece mientras la pantalla está en negro, antes de que la
#: escena se abra. Su trabajo es sostener dos segundos de nada, así que
#: cambia con quién viene y con cuánto se lleva andado: repetida siempre
#: igual, a la tercera vez sería un cartel de carga.
DREAMS: Dict[str, Tuple[str, ...]] = {
    DEVIL: (
        "Se te cierran los ojos. Hace rato que estás con esto.",
        "Los volvés a cerrar. Ya sabés adónde llevan.",
        "No hace falta dormirse del todo para llegar hasta él.",
        "Una última vez. Después no hay más.",
    ),
    DJANGO: (
        "Se te cierran los ojos. Alguien afina, muy lejos.",
        "Otra vez esa guitarra, del otro lado del sueño.",
        "El acorde queda dando vueltas cuando cerrás los ojos.",
    ),
    JESUS: (
        "Se te cierran los ojos. Hay claridad del otro lado.",
        "La luz sigue ahí cuando dejás de mirar.",
        "No es oscuridad. Es lo que hay antes de que amanezca.",
    ),
    NARRATOR: ("Se te cierran los ojos.",),
}


def dream_line(speaker: str, step: int) -> str:
    lines = DREAMS.get(speaker) or DREAMS[NARRATOR]
    return lines[min(max(0, step), len(lines) - 1)]


#: El grado que suena a nota azul: la quinta bemol sobre la tónica menor. Es
#: la nota que no está en ninguna escala y que queda justo en el medio entre
#: dos que sí.
BLUE_NOTE_SEMITONES = 6

#: La cabeza de blues que se escribe sola en el Armonizador, en grados sobre
#: la tónica: pentatónica menor más la nota azul.
#:
#: Está escrita compás por compás y con una regla que no es decorativa: la
#: nota que cae en el primer tiempo de cada compás es siempre una nota del
#: acorde de ese compás. Es lo que permite que la voz más aguda cante la
#: melodía sin dejar al acorde incompleto --- y además es como se escribe un
#: blues de verdad. La nota azul aparece sólo en el medio del compás, de
#: paso y nunca apoyada, que es exactamente lo que dice el libro.
BLUES_HEAD: Tuple[Tuple[int, float], ...] = (
    (0, 2.0), (3, 1.0), (5, 1.0),        # 1   I7
    (3, 2.0), (5, 1.0), (3, 1.0),        # 2   IV7
    (0, 2.0), (10, 1.0), (7, 1.0),       # 3   I7
    (7, 2.0), (5, 2.0),                  # 4   I7
    (5, 2.0), (3, 1.0), (5, 1.0),        # 5   IV7
    (3, 2.0), (0, 2.0),                  # 6   IV7
    (0, 2.0), (6, 1.0), (7, 1.0),        # 7   I7  · la nota azul
    (10, 2.0), (7, 2.0),                 # 8   I7
    (7, 2.0), (5, 1.0), (7, 1.0),        # 9   V7
    (5, 2.0), (3, 1.0), (0, 1.0),        # 10  IV7
    (0, 2.0), (6, 1.0), (7, 1.0),        # 11  I7  · otra vez
    (5, 2.0), (7, 2.0),                  # 12  V7
)


def blues_head_melody(tonic_pc: int) -> Tuple[Tuple[int, float, float], ...]:
    """
    La cabeza del blues sobre una tónica, en el registro de la soprano.

    La tónica se lleva a la octava que empieza en do4, que es justo donde
    arranca el registro de la soprano: así la línea entera --- que sube hasta
    una séptima sobre la tónica --- le entra sin salirse por ningún lado.
    """
    base = 60 + (tonic_pc % 12)
    line, position = [], 0.0
    for step, duration in BLUES_HEAD:
        line.append((base + step, position, duration))
        position += duration
    return tuple(line)


def blues_piece(tonic_pc: int) -> Piece:
    """Los doce compases con su melodía, en la tonalidad que se pida."""
    piece = transposed(TWELVE_BAR_BLUES, tonic_pc)
    melody = blues_head_melody(tonic_pc)
    per_bar = piece.quarters_per_bar
    # La voz más aguda canta la nota que la melodía tenga sonando cuando el
    # acorde entra: así lo que se ve escrito y lo que se escucha arriba son
    # lo mismo.
    tops: List[Optional[int]] = []
    position = 0.0
    for _symbol, duration in piece.chords:
        tops.append(_melody_at(melody, position))
        position += duration
    return Piece(
        title="Los doce compases",
        genre_key="jazz",
        time_signature=piece.time_signature,
        chords=piece.chords,
        melody=melody,
        tops=tuple(tops),
        quarter_seconds=0.34,
        blurb=f"Blues de doce compases en {SHARP_NAMES[tonic_pc % 12]}, "
              f"con la nota azul en la melodía. "
              f"{int(per_bar)} tiempos por compás.",
    )


def _melody_at(melody: Sequence[Tuple[int, float, float]],
               moment: float) -> Optional[int]:
    """Qué nota de la melodía está sonando en ese momento, si hay alguna."""
    for pitch, start, length in melody:
        if start <= moment + 1e-6 < start + length:
            return pitch
    return None


#: Qué pieza corresponde a cada tramo automático.
STEP_PIECES = {
    # El tramo del Generador escribe la rueda sola, sin melodía: la cabeza
    # del blues llega recién en el tramo siguiente, que es de lo que trata.
    "blues_twelve": lambda tonic: TWELVE_BAR_BLUES,
    "jazz_standard": lambda tonic: ALL_OF_ME,
    "gospel_octave": lambda tonic: GOSPEL_OCTAVE,
    "blues_note": blues_piece,
    "jazz_lick": lambda tonic: THE_LICK_PIECE,
    "gospel_grace": lambda tonic: AMAZING_GRACE,
}


def piece_for(step_key: str, tonic_pc: int = 0) -> Optional[Piece]:
    maker = STEP_PIECES.get(step_key)
    return maker(tonic_pc) if maker is not None else None


# ---------------------------------------------------------------------------
# El estado guardado
# ---------------------------------------------------------------------------

class StoryState:
    """
    Por dónde va el usuario, persistido en ``story.json``.

    Guarda sólo cuando algo cambió, igual que el registro de logros: avanzar
    de tramo es raro y preguntar por el tramo en curso pasa en cada pantalla.
    """

    def __init__(self, path_key: str = "", step: int = 0,
                 seen_offer: bool = False, finished: Optional[List[str]] = None,
                 gates: Optional[Dict[str, List[int]]] = None,
                 read: Optional[List[str]] = None,
                 keepsakes: Optional[List[str]] = None,
                 file_path: Optional[str] = None):
        self.path_key = path_key if path_key in PATHS else ""
        self.step = max(0, step)
        #: Si la figura ya se apareció alguna vez. Se anota al **abrir** la
        #: escena y no al contestarla, y se conserva al arrepentirse: el
        #: suspenso de la primera aparición es de una sola vez y no se puede
        #: fabricar de nuevo. Decide **cómo** vuelve a aparecer ---sin la
        #: espera, que ya se pagó---, nunca **si** aparece: eso lo contesta
        #: `may_offer`.
        self.seen_offer = seen_offer
        #: Senderos terminados. Se pueden tener los tres.
        self.finished: List[str] = list(finished or [])
        #: Traba -> tonalidades ya conseguidas, en clases de altura.
        self.gates: Dict[str, List[int]] = {k: list(v) for k, v
                                            in (gates or {}).items()}
        #: Apartados del libro que el usuario ya vio abiertos.
        self.read: List[str] = list(read or [])
        #: Los recuerdos que entregaron los personajes.
        self.keepsakes: List[str] = list(keepsakes or [])
        self.file_path = file_path

    # -- persistencia -------------------------------------------------------

    @classmethod
    def load(cls, file_path: Optional[str] = None) -> "StoryState":
        target = file_path or state_path()
        if not os.path.exists(target):
            return cls(file_path=file_path)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return cls(file_path=file_path)
        if not isinstance(raw, dict):
            return cls(file_path=file_path)
        gates = raw.get("gates", {})
        if not isinstance(gates, dict):
            gates = {}
        clean = {str(k): [int(x) % 12 for x in v]
                 for k, v in gates.items() if isinstance(v, list)}
        return cls(
            path_key=str(raw.get("path", "")),
            step=int(raw.get("step", 0) or 0),
            seen_offer=bool(raw.get("seen_offer", False)),
            finished=[str(x) for x in raw.get("finished", [])
                      if str(x) in PATHS],
            gates=clean,
            read=[str(x) for x in raw.get("read", [])],
            keepsakes=[str(x) for x in raw.get("keepsakes", []) if str(x) in PATHS],
            file_path=file_path,
        )

    def save(self) -> None:
        target = self.file_path or state_path()
        try:
            with open(target, "w", encoding="utf-8") as handle:
                json.dump({"path": self.path_key, "step": self.step,
                           "seen_offer": self.seen_offer,
                           "finished": self.finished,
                           "gates": self.gates, "read": self.read,
                           "keepsakes": self.keepsakes},
                          handle, indent=2, ensure_ascii=False)
        except OSError:
            pass          # una carpeta de sólo lectura no puede romper nada

    # -- dónde estamos ------------------------------------------------------

    @property
    def path(self) -> Optional[Path]:
        return PATHS.get(self.path_key)

    @property
    def active(self) -> bool:
        """¿Hay un sendero en curso, con tramos por delante?"""
        path = self.path
        return path is not None and self.step < len(path.steps)

    @property
    def current(self) -> Optional[Step]:
        path = self.path
        if path is None or self.step >= len(path.steps):
            return None
        return path.steps[self.step]

    def step_at(self, index: int) -> Optional[Step]:
        path = self.path
        if path is None or not 0 <= index < len(path.steps):
            return None
        return path.steps[index]

    def total_steps(self) -> int:
        path = self.path
        return len(path.steps) if path is not None else 0

    def awaiting(self, where: str) -> Optional[Step]:
        """El tramo en curso, si es de este modo de trabajo."""
        step = self.current
        return step if step is not None and step.where == where else None

    # -- el ofrecimiento ----------------------------------------------------

    def may_offer(self) -> bool:
        """
        ¿Corresponde que la figura aparezca?

        Pregunta **sólo por el sendero**, y esto es lo único definitivo:
        mientras no haya uno elegido, el ofrecimiento sigue pendiente.
        Preguntando además por `seen_offer` ---que se levanta al abrir la
        escena--- un ofrecimiento empezado y no terminado apagaba el modo
        historia para siempre: cerrar la aplicación en la mitad de la
        cinemática dejaba la marca puesta con el sendero todavía vacío, y
        entonces no había botón ---el ofrecimiento ya había ocurrido---, ni
        recordatorio, ni «Arrepentirse», porque las tres cosas cuelgan de
        tener un sendero. El relato quedaba inalcanzable sin que fallara
        nada. Lo mismo pasaba al arrepentirse, que deja exactamente ese
        estado a propósito.
        """
        return not self.path_key

    def mark_offered(self) -> None:
        """
        La figura se apareció. Se anota al abrir la escena, no al elegir.

        Es lo que evita que el ofrecimiento vuelva a hacerse esperar cinco
        minutos cuando la cinemática se cortó por la mitad: el suspenso ya
        se gastó, así que lo que corresponde es que el llamado vuelva a
        estar ahí en cuanto haya un momento tranquilo.
        """
        if self.seen_offer:
            return
        self.seen_offer = True
        self.save()

    def choose(self, choice: str) -> str:
        """Elegir un sendero desde la respuesta del ofrecimiento."""
        key = CHOICE_PATHS.get(choice, "")
        self.seen_offer = True
        self.path_key = key
        self.step = 0
        self.save()
        return key

    def restart(self) -> None:
        """Arrepentirse: se vuelve a empezar desde el ofrecimiento."""
        self.path_key = ""
        self.step = 0
        self.save()

    # -- avanzar ------------------------------------------------------------

    def advance(self) -> None:
        if self.path is None:
            return
        self.step += 1
        if self.step >= len(self.path.steps) and self.path_key not in self.finished:
            self.finished.append(self.path_key)
            if self.path_key not in self.keepsakes:
                self.keepsakes.append(self.path_key)
        self.save()

    def withholds(self, key: str) -> bool:
        """
        ¿Este logro le pertenece a un sendero que todavía está a mitad?

        El legendario de cada camino se entrega en el cierre, no en el tramo
        donde el usuario se topa con la progresión: el sendero es justamente
        el relato de cómo se llega a él. Si el sendero no está empezado, el
        logro se comporta como siempre.
        """
        owner = PATH_AWARDS.get(key, "")
        return bool(owner) and owner == self.path_key and self.active

    # -- las trabas ---------------------------------------------------------

    def gate_progress(self, gate: str) -> Tuple[int, int]:
        if gate in BOOK_GATES:
            return (1 if BOOK_GATES[gate] in self.read else 0), 1
        return len(self.gates.get(gate, [])), KEYS_REQUIRED

    def gate_open(self, gate: str) -> bool:
        if not gate:
            return True
        done, needed = self.gate_progress(gate)
        return done >= needed

    def note_tonics(self, gate: str, tonics: Set[int]) -> bool:
        """Anotar tonalidades nuevas para una traba. Devuelve si cambió algo."""
        if not tonics or gate not in KEY_GATES:
            return False
        stored = set(self.gates.get(gate, []))
        merged = stored | {t % 12 for t in tonics}
        if merged == stored:
            return False
        self.gates[gate] = sorted(merged)
        self.save()
        return True

    def mark_read(self, book_key: str) -> bool:
        """Dar por leído un apartado. Devuelve si es la primera vez."""
        if not book_key or book_key in self.read:
            return False
        self.read.append(book_key)
        self.save()
        return True

    # -- el libro -----------------------------------------------------------

    def knows(self, book_key: str) -> bool:
        """
        ¿Está escrito ya este apartado del capítulo del sendero?

        Un apartado se abre cuando el tramo que le corresponde quedó atrás, y
        una vez abierto no se vuelve a cerrar aunque el usuario se arrepienta
        y arranque otro camino: lo que ya leyó, lo leyó.
        """
        return book_key in unlocked_notes(self)


def unlocked_notes(state: "StoryState") -> Set[str]:
    """
    Los apartados del libro que este estado deja escritos.

    Se escribe **una anotación por cinemática**, y ni una más. El personaje
    manda a leer justo lo que se acaba de descubrir, así que:

    * al empezar el sendero ya está escrita la primera --- si esperara a que
      el primer tramo termine, el usuario iría al libro y encontraría la
      página en blanco;
    * la segunda aparece recién al llegar al último tramo.

    Escribirlas antes las volvía inútiles: se abría el libro una vez, se
    leían las dos de una, y las dos trabas quedaban abiertas sin que el
    usuario volviera a pasar por ahí.
    """
    open_now: Set[str] = set()
    for path_key, path in PATHS.items():
        if path_key in state.finished:
            reached = len(path.steps)
        elif path_key == state.path_key:
            reached = max(1, state.step)
        else:
            continue
        for index in range(min(reached, len(path.steps))):
            open_now.add(f"story_{path_key}_{index + 1}")
    # Lo ya leído se queda escrito para siempre, aunque se cambie de camino.
    open_now.update(state.read)
    return open_now


def state_path() -> str:
    return os.path.join(history.base_directory(), _FILENAME)
