# -*- coding: utf-8 -*-
"""
Analizar una partitura que ya está escrita.

El resto del programa va en la dirección contraria: alguien pone los acordes
y la búsqueda escribe las voces. Acá las voces ya están escritas y lo que
falta es el nombre de lo que hacen --- qué acorde es cada momento, en qué
tonalidad, qué función cumple, y qué le está pasando al contrapunto entre
una vertical y la siguiente.

Cómo está armado
----------------
1. :func:`verticalise` corta la pieza en **sonoridades**: cada tramo en el
   que no cambia ninguna voz. Es la unidad mínima; todo lo demás se arma
   agrupándolas.
2. :func:`read_chord` le pone nombre a un puñado de alturas pesadas por
   duración y por posición métrica. Gana el acorde que más notas de su
   tríada más séptima encuentre sonando, y cuando el segundo candidato
   queda cerca se devuelven los dos: una tríada en primera inversión es
   genuinamente ambigua y decidir por el usuario sería mentirle.
3. :func:`detect_key` mira la armadura, la nota de arranque y la de reposo,
   y de ahí sale la tonalidad --- que puede ser un modo, porque una armadura
   sola no distingue mayor de dórico.
4. :func:`label_segment` decide si el acorde es diatónico, una dominante
   aplicada, un intercambio modal o cromatismo suelto, y qué área funcional
   ocupa.
5. El contrapunto se mide aparte: movimientos entre pares de voces, quintas
   y octavas paralelas, saltos de trítono, cruces, y las notas que no
   pertenecen al acorde con el nombre que les corresponde.

Este módulo es puro: no dibuja, no lee archivos y no importa nada de la
interfaz. Las reglas duras que ya existen ---paralelas y quintas ocultas---
se **piden prestadas** a :mod:`engine.fitness` en vez de reescribirse:
una segunda copia de la misma regla se desincroniza de la primera en el
primer cambio, y entonces el analizador diría que está bien lo que el
generador prohíbe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import harmony
from .fitness import (GENRE_PROFILES, direct_perfect_violation,
                      parallel_interval_violation)
from .theory import (FLAT_NAMES, LETTER_SEMITONES, LETTER_STEPS,
                     SHARP_NAMES)
from engine.i18n import N, tr, trf, trs
from engine import i18n

OCTAVE = 12
TRITONE = 6
PERFECT_FIFTH = 7

#: Cuánto se puede correr un ataque y seguir contando como simultáneo. Una
#: partitura importada trae divisiones que no siempre caen redondas y dos
#: voces que atacan juntas pueden diferir en una millonésima de negra; sin
#: esta tolerancia esa nada partía la vertical en dos.
EPSILON = 1e-6


# ---------------------------------------------------------------------------
# Lo que entra
# ---------------------------------------------------------------------------

@dataclass
class Note:
    """Una nota de una voz, ubicada en el tiempo de la pieza entera."""

    pitch: Optional[int]            # MIDI, o None si es un silencio
    onset: float                    # negras desde el comienzo
    duration: float                 # negras

    @property
    def end(self) -> float:
        return self.onset + self.duration

    @property
    def is_rest(self) -> bool:
        return self.pitch is None


@dataclass
class Part:
    """Una voz entera.

    El orden de las voces dentro de :class:`Score` es el del motor: índice 0
    es la más grave. Todo lo que sigue lo da por sentado --- el bajo es
    quien manda en el cifrado y en la inversión --- así que una partitura
    leída al revés se ordena antes de entrar acá.
    """

    name: str
    notes: List[Note] = field(default_factory=list)

    def sounding_at(self, moment: float,
                    cursor: int = 0) -> Tuple[Optional[Note], int]:
        """
        La nota que suena en ese instante, y por dónde quedó la búsqueda.

        El cursor es lo que hace que recorrer la pieza entera cueste lo que
        cuesta leerla una vez. Sin él, cada vertical volvía a recorrer la voz
        desde el principio y una partitura de cuatro voces y doscientos
        compases tardaba lo suficiente como para que la pantalla pareciera
        colgada.
        """
        index = min(cursor, len(self.notes))
        while index < len(self.notes) and self.notes[index].end <= moment + EPSILON:
            index += 1
        if index < len(self.notes):
            note = self.notes[index]
            if note.onset - EPSILON <= moment < note.end - EPSILON:
                return (None if note.is_rest else note), index
        return None, index

    def voiced(self) -> List[Note]:
        return [n for n in self.notes if not n.is_rest]

    def mean_pitch(self) -> float:
        pitches = [n.pitch for n in self.voiced()]
        return sum(pitches) / len(pitches) if pitches else 0.0


@dataclass
class Score:
    """La pieza a analizar."""

    parts: List[Part] = field(default_factory=list)
    fifths: int = 0                 # armadura, en sostenidos (+) o bemoles (-)
    beats: int = 4
    beat_type: int = 4
    title: str = ""
    #: Negras que ocupa la anacrusa inicial. Un primer compás incompleto
    #: corre la grilla entera: sin este dato, todos los tiempos fuertes de
    #: la pieza quedan medidos donde no están.
    pickup_quarters: float = 0.0
    #: Los cambios de compás: ``(compás, tiempos, figura)``, ordenados y
    #: contando los compases desde 1. ``beats``/``beat_type`` son el compás
    #: de arranque y esta lista dice desde dónde rige cada uno de los
    #: siguientes.
    #:
    #: No es un adorno de la partitura: el compás es lo que define dónde
    #: caen los tiempos fuertes, y de los tiempos fuertes salen la unidad
    #: con la que se lee un acorde, el peso de cada nota y el nombre de
    #: cualquier adorno. Forzar una pieza entera a un solo compás cambia el
    #: análisis, no sólo el dibujo.
    metres: Tuple[Tuple[int, int, int], ...] = ()

    @property
    def quarters_per_bar(self) -> float:
        """Lo que dura el compás **de arranque**.

        Para medir un instante cualquiera está :meth:`metrics_at`, que sabe
        de los cambios; esto es sólo el valor por omisión.
        """
        return self.beats * 4.0 / self.beat_type

    @property
    def beat_quarters(self) -> float:
        return 4.0 / self.beat_type

    def metre_at(self, bar: int) -> Tuple[int, int]:
        """Qué compás rige en ese compás de la pieza."""
        beats, beat_type = self.beats, self.beat_type
        for at, count, figure in self.metres:
            if at <= max(1, bar):
                beats, beat_type = count, figure
            else:
                break
        return beats, beat_type

    def metrics_at(self, bar: int) -> Tuple[float, float]:
        """(lo que dura el compás, lo que dura un tiempo), en negras."""
        beats, beat_type = self.metre_at(bar)
        return beats * 4.0 / beat_type, 4.0 / beat_type

    def bar_grid(self) -> List[Tuple[int, float, float]]:
        """
        Los compases de la pieza: número, dónde empieza y cuánto dura.

        La anacrusa es el compás 0 y dura lo que ocupe. Se calcula una vez y
        queda guardada: se la consulta una vez por vertical y por nota, y
        recorrerla desde el principio en cada consulta convertía un análisis
        en un cuadrado.
        """
        cached = getattr(self, "_grid_cache", None)
        if cached is not None:
            return cached
        finish = self.length()
        grid: List[Tuple[int, float, float]] = []
        moment = 0.0
        if self.pickup_quarters > EPSILON:
            grid.append((0, 0.0, self.pickup_quarters))
            moment = self.pickup_quarters
        bar = 1
        while True:
            per_bar = self.metrics_at(bar)[0] or 4.0
            grid.append((bar, moment, per_bar))
            moment += per_bar
            bar += 1
            if moment > finish + EPSILON or bar > 9999:
                break
        object.__setattr__(self, "_grid_cache", grid)
        return grid

    def length(self) -> float:
        return max((n.end for part in self.parts for n in part.notes),
                   default=0.0)

    def in_register_order(self) -> "Score":
        """La misma pieza con las voces ordenadas de grave a aguda."""
        return Score(parts=sorted(self.parts, key=lambda p: p.mean_pitch()),
                     fifths=self.fifths, beats=self.beats,
                     beat_type=self.beat_type, title=self.title,
                     pickup_quarters=self.pickup_quarters,
                     metres=tuple(self.metres))


# ---------------------------------------------------------------------------
# Sonoridades
# ---------------------------------------------------------------------------

@dataclass
class Sonority:
    """Un tramo en el que no cambia ninguna voz."""

    onset: float
    duration: float
    #: Una altura por voz, en el orden de `Score.parts`; None si esa voz
    #: calla. Conservar el hueco importa: sin él las voces se corren de
    #: índice y una comparación de paralelas termina midiendo entre voces
    #: que no son las que suenan.
    pitches: List[Optional[int]] = field(default_factory=list)
    bar_index: int = 0
    offset: float = 0.0             # posición dentro del compás, en negras
    #: Qué voces atacan acá; las demás vienen sonando de antes.
    attacks: Tuple[int, ...] = ()
    #: Qué voces están, en esta vertical, tocando una nota con forma de
    #: adorno. Pesan menos a la hora de decidir el acorde.
    ornamental: Tuple[int, ...] = ()
    #: Qué voces sostienen acá una cuarta (o segunda) suspendida que resuelve
    #: dentro del mismo tiempo (`_suspension_inside`). Pesan como adorno al
    #: leer el acorde pero, a diferencia de las de arriba, el cifrado las
    #: sigue viendo: un continuista sí escribe el 4 de un retardo.
    resolving: Tuple[int, ...] = ()

    @property
    def end(self) -> float:
        return self.onset + self.duration

    @property
    def sounding(self) -> List[int]:
        return [p for p in self.pitches if p is not None]

    @property
    def bass(self) -> Optional[int]:
        sounding = self.sounding
        return min(sounding) if sounding else None

    @property
    def pitch_classes(self) -> List[int]:
        return sorted({p % 12 for p in self.sounding})


#: Cuánto pesa una nota con forma de adorno al decidir la armonía. No cero:
#: a veces la nota de paso es de verdad la séptima del acorde y hay que
#: dejarle la posibilidad de ganar si el resto de la textura la acompaña.
ORNAMENT_WEIGHT = 0.15


#: Lo más que puede durar una escapada, en negras. Más larga que una
#: corchea deja de oírse como un adorno de paso y pasa a ser melodía.
ESCAPE_MAX = 0.5


def _ornament_shaped(part: Part, score: Optional[Score] = None) -> set:
    """
    Los comienzos de las notas de una voz que tienen forma de adorno.

    La forma, no la función: entra por grado conjunto, sale por grado
    conjunto y no dura más que sus vecinas. Es el perfil de la nota de paso
    y de la bordadura, que juntas son la enorme mayoría de las notas ajenas
    que hay escritas.

    Y la escapada, cuando se sabe dónde caen los tiempos: entra por grado,
    sale por salto en la dirección contraria, es corta y cae fuera del
    tiempo. Es el adorno de las cadencias de los corales ---mi-fa#-re sobre
    un La--- y sin descontarla el fa# de paso convertía la dominante en un
    Fa# menor con séptima.

    Esto corre **antes** de leer los acordes y es lo que impide que un si de
    paso sobre un acorde de do convierta al acorde en un do con séptima
    mayor. Sin este paso, cualquier voz que se mueva por grados va
    inventando acordes de séptima en cada tiempo.
    """
    notes = part.voiced()
    marked = set()
    for index in range(1, len(notes) - 1):
        before, note, after = notes[index - 1], notes[index], notes[index + 1]
        if not (1 <= abs(note.pitch - before.pitch) <= 2):
            continue
        if note.duration > before.duration:
            continue
        if 1 <= abs(after.pitch - note.pitch) <= 2:
            if note.duration > after.duration:
                continue
            marked.add(round(note.onset, 6))
        elif (score is not None and abs(after.pitch - note.pitch) >= 3
              and (note.pitch > before.pitch) != (after.pitch > note.pitch)
              and note.duration <= ESCAPE_MAX + EPSILON):
            bar, offset = bar_and_offset(score, note.onset)
            per_bar, beat = score.metrics_at(bar)
            if not is_strong(offset, per_bar, beat):
                marked.add(round(note.onset, 6))
    return marked


def _boundaries(score: Score) -> List[float]:
    """Cada instante en el que alguna voz empieza o termina una nota."""
    points = {0.0}
    for part in score.parts:
        for note in part.notes:
            points.add(round(note.onset, 6))
            points.add(round(note.end, 6))
    return sorted(points)


def bar_and_offset(score: Score, moment: float) -> Tuple[int, float]:
    """En qué compás cae un instante y a cuántas negras de su comienzo.

    Los compases se numeran desde 1 y la anacrusa es el compás 0, que es la
    convención con la que se cita música: el primer compás completo de una
    pieza con anacrusa es el 1.
    """
    grid = score.bar_grid()
    low, high = 0, len(grid) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if grid[middle][1] <= moment + EPSILON:
            low = middle
        else:
            high = middle - 1
    bar, start, per_bar = grid[low]
    if bar == 0:
        # La anacrusa se mide desde el final del compás que le falta: su
        # última negra es la última negra de un compás completo, que es de
        # donde sale que su nota final caiga en parte débil.
        return 0, moment + (score.metrics_at(1)[0] - score.pickup_quarters)
    if moment >= start + per_bar - EPSILON and low == len(grid) - 1:
        # Más allá del último compás calculado: se sigue contando con el
        # mismo compás en vez de devolver un número que no existe.
        extra = int((moment - start) // per_bar)
        return bar + extra, moment - start - extra * per_bar
    return bar, moment - start


def verticalise(score: Score) -> List[Sonority]:
    """
    Cortar la pieza en sonoridades.

    Se corta en cada ataque y en cada final de nota, no cada tanto tiempo:
    una grilla fija de corcheas se pierde los tresillos y parte en dos las
    notas largas sin motivo, y las dos cosas ensucian después la lectura de
    acordes.
    """
    points = _boundaries(score)
    result: List[Sonority] = []
    cursors = [0] * len(score.parts)
    shaped = [_ornament_shaped(part, score) for part in score.parts]
    for start, end in zip(points, points[1:]):
        if end - start <= EPSILON:
            continue
        middle = (start + end) / 2.0
        pitches: List[Optional[int]] = []
        attacks: List[int] = []
        candidates: List[int] = []
        for index, part in enumerate(score.parts):
            note, cursors[index] = part.sounding_at(middle, cursors[index])
            pitches.append(None if note is None else note.pitch)
            if note is None:
                continue
            if abs(note.onset - start) <= EPSILON:
                attacks.append(index)
            if round(note.onset, 6) in shaped[index]:
                candidates.append(index)
        if not any(p is not None for p in pitches):
            continue
        # Una voz que se mueve mientras las otras sostienen está adornando;
        # cuatro voces que se mueven a la vez están cambiando de acorde. La
        # forma sola no alcanza para distinguirlas y el contexto sí, así que
        # una nota con forma de adorno sólo cuenta como tal si algo se queda
        # quieto debajo.
        sounding = sum(1 for p in pitches if p is not None)
        holding = sounding - len(attacks)
        ornamental = tuple(candidates) if holding > 0 else ()
        bar_index, offset = bar_and_offset(score, start)
        result.append(Sonority(onset=start, duration=end - start,
                               pitches=pitches, bar_index=bar_index,
                               offset=offset, attacks=tuple(attacks),
                               ornamental=ornamental))
    return result


def metric_weight(offset: float, per_bar: float, beat_quarters: float) -> float:
    """
    Cuánto pesa una posición del compás a la hora de decidir la armonía.

    La armonía se decide en los tiempos fuertes: lo que cae entre medio es,
    casi siempre, adorno. Sin esta cuenta una corchea de paso pesa lo mismo
    que la nota del acorde y la lectura se va detrás de los adornos, que es
    exactamente lo que hay que evitar.
    """
    if abs(offset) <= EPSILON:
        return 1.0
    # La mitad del compás es fuerte sólo si cae en un tiempo: el tercero del
    # cuatro por cuatro, el segundo pulso del seis por ocho. En un compás de
    # tres no cae en ninguno ---la mitad de un tres por cuatro es la corchea
    # que sigue al segundo tiempo--- y contándola como fuerte, en un coral en
    # tres la nota de paso de esa corchea pesaba casi como un primer tiempo.
    half = per_bar / 2.0
    on_a_beat = (beat_quarters > 0
                 and abs(half / beat_quarters - round(half / beat_quarters))
                 <= EPSILON)
    if (per_bar >= 3.0 * beat_quarters and on_a_beat
            and abs(offset - half) <= EPSILON):
        return 0.85                     # la mitad del compás
    if beat_quarters > 0 and abs(offset / beat_quarters
                                 - round(offset / beat_quarters)) <= EPSILON:
        return 0.7                      # otro tiempo del compás
    return 0.28                         # contratiempo


def is_strong(offset: float, per_bar: float, beat_quarters: float) -> bool:
    """¿Cae en un tiempo del compás, fuerte o no, pero en un tiempo?"""
    return metric_weight(offset, per_bar, beat_quarters) >= 0.7


def is_accented(offset: float, per_bar: float, beat_quarters: float) -> bool:
    """
    ¿Cae en una parte **fuerte**: el primer tiempo o la mitad del compás?

    No es lo mismo que caer en un tiempo. Una nota de paso en el segundo
    tiempo de un cuatro por cuatro no es una nota de paso acentuada --- el
    segundo tiempo es débil ---, y llamarla así le pone nombre de disonancia
    expuesta a algo que pasa desapercibido.
    """
    return metric_weight(offset, per_bar, beat_quarters) >= 0.85


# ---------------------------------------------------------------------------
# Lectura de acordes
# ---------------------------------------------------------------------------

#: Los acordes que el analizador sabe reconocer, con los intervalos de cada
#: uno sobre su fundamental y el papel de cada intervalo.
#:
#: El orden importa: a igualdad de notas encontradas gana el que está
#: primero, y por eso arriba están las tríadas. Un do-mi-sol es un Do y no
#: un Do con la séptima omitida, aunque las dos lecturas expliquen las
#: mismas tres notas.
_ROOT, _THIRD, _FIFTH, _SEVENTH = "root", "third", "fifth", "seventh"

#: Cada nota lleva tres datos: a cuántos semitonos está de la fundamental,
#: qué papel cumple y **de qué tamaño es el intervalo escrito**. El tamaño no
#: se puede deducir de los semitonos --- ocho semitonos son una quinta
#: aumentada en un acorde aumentado y una sexta menor en cualquier otro --- y
#: es justamente lo que hace falta para cifrar: el bajo continuo escribe
#: tamaños, no semitonos.
#: Cuánto se prefiere cada acorde a igualdad de notas explicadas. No es un
#: adorno del puntaje: es lo que impide que una lectura rara le gane a la
#: obvia por un pelo. Las suspendidas van en contra porque casi nunca son la
#: explicación correcta de tres notas sueltas --- un do-re-sol de paso no es
#: un Do con la segunda suspendida, es un Do al que le está pasando algo por
#: encima --- y la segunda suspendida más todavía: en la música que este
#: programa analiza prácticamente no existe como acorde.
TEMPLATE_PREFERENCE = {
    "": 0.06, "m": 0.06,
    "7": 0.05, "m7": 0.045, "maj7": 0.04,
    "dim": 0.03, "m7b5": 0.03, "dim7": 0.03,
    "mmaj7": 0.0, "6": 0.0, "m6": 0.0,
    "aug": -0.02, "aug7": -0.04,
    "sus4": -0.06, "7sus4": -0.05, "sus2": -0.20,
}

TEMPLATES: Tuple[Tuple[str, Tuple[Tuple[int, str, int], ...]], ...] = (
    ("",       ((0, _ROOT, 1), (4, _THIRD, 3), (7, _FIFTH, 5))),
    ("m",      ((0, _ROOT, 1), (3, _THIRD, 3), (7, _FIFTH, 5))),
    ("7",      ((0, _ROOT, 1), (4, _THIRD, 3), (7, _FIFTH, 5), (10, _SEVENTH, 7))),
    ("m7",     ((0, _ROOT, 1), (3, _THIRD, 3), (7, _FIFTH, 5), (10, _SEVENTH, 7))),
    ("maj7",   ((0, _ROOT, 1), (4, _THIRD, 3), (7, _FIFTH, 5), (11, _SEVENTH, 7))),
    ("dim",    ((0, _ROOT, 1), (3, _THIRD, 3), (6, _FIFTH, 5))),
    ("m7b5",   ((0, _ROOT, 1), (3, _THIRD, 3), (6, _FIFTH, 5), (10, _SEVENTH, 7))),
    ("dim7",   ((0, _ROOT, 1), (3, _THIRD, 3), (6, _FIFTH, 5), (9, _SEVENTH, 7))),
    ("sus4",   ((0, _ROOT, 1), (5, _THIRD, 4), (7, _FIFTH, 5))),
    ("aug",    ((0, _ROOT, 1), (4, _THIRD, 3), (8, _FIFTH, 5))),
    ("mmaj7",  ((0, _ROOT, 1), (3, _THIRD, 3), (7, _FIFTH, 5), (11, _SEVENTH, 7))),
    ("7sus4",  ((0, _ROOT, 1), (5, _THIRD, 4), (7, _FIFTH, 5), (10, _SEVENTH, 7))),
    ("sus2",   ((0, _ROOT, 1), (2, _THIRD, 2), (7, _FIFTH, 5))),
    ("6",      ((0, _ROOT, 1), (4, _THIRD, 3), (7, _FIFTH, 5), (9, _SEVENTH, 6))),
    ("m6",     ((0, _ROOT, 1), (3, _THIRD, 3), (7, _FIFTH, 5), (9, _SEVENTH, 6))),
    ("aug7",   ((0, _ROOT, 1), (4, _THIRD, 3), (8, _FIFTH, 5), (10, _SEVENTH, 7))),
)

#: Cuánto descuenta que falte cada nota del acorde. La tercera es la que
#: define la calidad y su ausencia deja el acorde sin decidir; la quinta se
#: omite todo el tiempo sin que nadie se entere, y por eso casi no cuesta.
MISSING_COST = {_ROOT: 0.28, _THIRD: 0.30, _FIFTH: 0.05, _SEVENTH: 0.22}

#: A partir de qué presencia se le cree la séptima a un acorde, como
#: fracción de lo que le tocaría si el acorde sonara parejo. La mitad: por
#: debajo de eso la nota está de visita.
#:
#: Existe porque "está o no está" es demasiado grueso para la séptima. Un si
#: de paso que dura una corchea sobre un acorde de do de dos tiempos hace
#: que la lectura "do con séptima mayor" explique el cien por ciento del
#: material, y explicarlo todo es lo que decide: la lectura correcta --- un
#: do a secas --- perdía por dejar afuera una corchea.
#:
#: **Sólo la séptima.** Se probó con las cuatro notas y rompió lo que venía
#: bien: en una textura arpegiada la fundamental de un acorde invertido
#: suena poco por definición ---el bajo tiene otra nota y la fundamental
#: pasa de visita en el arpegio---, así que castigarla por flaca convertía
#: un V con la tercera en el bajo en un vii° con la fundamental en el bajo.
#: Las dos lecturas usan las mismas notas y la que gana no puede decidirse
#: por cuánto dura cada una.
SUPPORT_SHARE = 0.5

#: Cuánto pesa, además, lo que el acorde deja sin explicar. Sin este
#: agregado una nota que sobra sólo costaba lo que dejaba de sumar, y salía
#: barato ignorar una voz entera: un acorde que explica el 80% del material
#: le ganaba a otro que explica el 100% pero al que le falta una nota
#: propia. Acá lo que sobra cuesta más que lo que falta, que es el orden
#: correcto --- una nota que suena y no encaja es evidencia en contra.
EXTRA_COST = 0.6

#: Cuánto suma que las notas del acorde pertenezcan a la armadura. Desempata
#: lo que las notas no alcanzan a decidir: si suenan re, la y do y la tercera
#: no aparece por ningún lado, el acorde puede ser un Rem7 o un Re7 --- las
#: dos lecturas explican exactamente lo mismo --- y en una pieza sin
#: alteraciones es un Rem7. La evidencia manda igual: en cuanto el fa
#: sostenido suena, el Re7 gana por lejos y esto no alcanza para taparlo.
SIGNATURE_FIT = 0.10

#: Lo que descuenta leer una suspendida cuyo bajo no es su fundamental.
#: Una cuarta suspendida se apoya sobre el bajo del acorde al que suspende;
#: "La sus4 con el re en el bajo" no es lo que nadie llamaría a un re con su
#: quinta al aire, y sin este descuento ganaba justamente ahí --- porque a
#: la suspendida no le falta la tercera, le sobra la cuarta en su lugar.
SUSPENDED_OFF_BASS = 0.35

#: Lo que suma tener la fundamental en el bajo. Chico a propósito: rompe
#: empates a favor del estado fundamental sin poder tapar una lectura que
#: explique más notas.
ROOT_POSITION_BONUS = 0.06

#: Diferencia por debajo de la cual dos lecturas se consideran igual de
#: buenas y se muestran las dos.
#:
#: Medido contra el caso que hay que atrapar: do-mi-sol-la con el la en el
#: bajo es un Lam7 y un Do6, y las dos lecturas son ciertas --- es el
#: ejemplo de manual de acorde ambiguo. Con un margen más chico esa
#: diferencia quedaba afuera por centésimas y la segunda lectura no se
#: ofrecía nunca.
AMBIGUITY_MARGIN = 0.13

#: Puntaje mínimo para que una lectura merezca ofrecerse como alternativa.
MIN_ALTERNATIVE = 0.42

#: Cifrado de cada inversión, para el numeral romano.
TRIAD_FIGURES = {0: "", 1: "6", 2: "6/4"}
SEVENTH_FIGURES = {0: "7", 1: "6/5", 2: "4/3", 3: "4/2"}


@dataclass
class ChordReading:
    """Un acorde posible para un momento de la pieza."""

    root_pc: int
    quality: str
    pitch_classes: Tuple[int, ...]
    bass_pc: Optional[int] = None
    inversion: int = 0              # -1 si el bajo no pertenece al acorde
    score: float = 0.0
    missing: Tuple[str, ...] = ()
    extra: Tuple[int, ...] = ()
    prefer_flats: bool = False
    #: (clase de altura, papel, tamaño del intervalo sobre la fundamental).
    #: De acá sale el cifrado del bajo continuo.
    tones: Tuple[Tuple[int, str, int], ...] = ()

    @property
    def root_name(self) -> str:
        return (FLAT_NAMES if self.prefer_flats else SHARP_NAMES)[self.root_pc]

    @property
    def bass_name(self) -> str:
        """
        Cómo se escribe el bajo, según qué nota del acorde sea.

        Por su papel y no por su altura: la quinta de un Si con séptima se
        escribe fa sostenido aunque la pieza vaya llena de bemoles, porque
        una quinta se cuenta de si a fa y no de si a sol. Preguntándole el
        nombre a la tabla de siempre salía "Si7/Solb", que es un acorde con
        una cuarta disminuida en el bajo --- otro acorde.
        """
        names = FLAT_NAMES if self.prefer_flats else SHARP_NAMES
        if self.bass_pc is None:
            return ""
        size = next((s for pc, _role, s in self.tones if pc == self.bass_pc),
                    None)
        if size is None:
            return names[self.bass_pc]
        step = (LETTER_STEPS.get(self.root_name[0], 0) + size - 1) % 7
        letter = "CDEFGAB"[step]
        alter = (self.bass_pc - LETTER_SEMITONES[letter] + 6) % 12 - 6
        return letter + {1: "#", 2: "##", -1: "b", -2: "bb"}.get(alter, "")

    @property
    def symbol(self) -> str:
        """Cifrado americano, con la barra cuando está invertido."""
        names = FLAT_NAMES if self.prefer_flats else SHARP_NAMES
        text = names[self.root_pc] + self.quality
        if self.bass_pc is not None and self.bass_pc != self.root_pc:
            text += "/" + self.bass_name
        return text

    @property
    def has_seventh(self) -> bool:
        return len(self.pitch_classes) >= 4 and self.quality not in ("6", "m6")

    @property
    def figure(self) -> str:
        """El cifrado de inversión que acompaña al numeral romano."""
        table = SEVENTH_FIGURES if self.has_seventh else TRIAD_FIGURES
        return table.get(max(0, self.inversion), "")

    def contains(self, pitch: int) -> bool:
        return pitch % 12 in self.pitch_classes


#: Las plantillas ya trasladadas a las doce fundamentales. Armar los
#: conjuntos en cada lectura costaba más que la lectura entera: hay doscientas
#: combinaciones y una pieza de cien compases las prueba varios miles de veces.
_CANDIDATES: List[Tuple[str, int, Tuple[int, ...], Tuple[int, ...],
                        Tuple[Tuple[int, str, int], ...], float]] = []
for _quality, _template in TEMPLATES:
    for _root in range(12):
        _stack = tuple((_root + step) % 12 for step, _role, _size in _template)
        _CANDIDATES.append((
            _quality, _root, tuple(sorted(set(_stack))), _stack,
            tuple(((_root + step) % 12, role, size)
                  for step, role, size in _template),
            TEMPLATE_PREFERENCE.get(_quality, 0.0),
        ))


#: Las lecturas ya hechas, por pedido. Seis de cada diez llamadas repiten
#: las mismas notas con el mismo peso ---un mismo tiempo se lee entero, por
#: mitades y junto al de al lado, y al editar una nota se reanaliza todo lo
#: demás tal cual estaba---, y esta función es el 90 % del análisis.
_READINGS: Dict[tuple, List[ChordReading]] = {}
READINGS_KEPT = 4096


def read_chord(
    weights: Dict[int, float],
    bass_pc: Optional[int] = None,
    prefer_flats: bool = False,
    diatonic: Sequence[int] = (),
) -> List[ChordReading]:
    """Las lecturas de `_read_chord`, recordadas.

    Cada llamada se lleva **copias**: quien llama les cambia `prefer_flats`
    a las que elige, y sobre las guardadas eso cambiaría la escritura de
    cualquier otro tiempo con las mismas notas.
    """
    key = (tuple(sorted(weights.items())), bass_pc, prefer_flats,
           tuple(sorted(set(diatonic))))
    known = _READINGS.get(key)
    if known is None:
        known = _read_chord(weights, bass_pc, prefer_flats, diatonic)
        if len(_READINGS) >= READINGS_KEPT:
            _READINGS.clear()
        _READINGS[key] = known
    return [_clone(reading) for reading in known]


def _clone(reading: ChordReading) -> ChordReading:
    """Una copia de una lectura. `copy.copy` tardaba cinco veces más, y con
    ciento noventa lecturas por llamada se comía lo que ahorra la memoria."""
    twin = object.__new__(ChordReading)
    twin.__dict__ = reading.__dict__.copy()
    return twin


def _read_chord(
    weights: Dict[int, float],
    bass_pc: Optional[int] = None,
    prefer_flats: bool = False,
    diatonic: Sequence[int] = (),
) -> List[ChordReading]:
    """
    Nombrar un puñado de clases de altura pesadas.

    ``weights`` es cuánto suena cada clase de altura: duración por peso
    métrico. Se prueban todas las fundamentales contra todas las plantillas
    y gana la que **más notas del acorde encuentre sonando** --- que es lo
    que pide el análisis tradicional: la tríada más la séptima, y el que
    cubra más.

    Devuelve las lecturas ordenadas de mejor a peor, con el puntaje ya
    normalizado entre 0 y 1, así que quien llame puede decidir si la segunda
    está lo bastante cerca como para mostrarla también.
    """
    total = sum(weights.values())
    if total <= 0:
        return []
    signature = set(diatonic)

    readings: List[ChordReading] = []
    for quality, root_pc, pcs, stack, tones, preference in _CANDIDATES:
        covered = sum(w for pc, w in weights.items() if pc in pcs) / total
        expected = SUPPORT_SHARE / len(tones)
        thin = 0.0
        missing_roles = []
        for pc, role, _size in tones:
            share = weights.get(pc, 0.0) / total
            if share <= 0.0:
                missing_roles.append(role)
                thin += MISSING_COST[role]
            elif role == _SEVENTH and share < expected:
                # Suena, pero apenas. Se cobra la parte proporcional de lo
                # que costaría que faltara.
                thin += MISSING_COST[role] * (1.0 - share / expected)
        missing = tuple(missing_roles)
        value = (covered - EXTRA_COST * (1.0 - covered) - thin + preference)
        if signature:
            value += SIGNATURE_FIT * sum(
                1 for pc in pcs if pc in signature) / len(pcs)
        if bass_pc == root_pc:
            value += ROOT_POSITION_BONUS
        elif quality in ("sus4", "sus2", "7sus4") and bass_pc is not None:
            value -= SUSPENDED_OFF_BASS
        # La inversión se cuenta por terceras apiladas, no por clase de
        # altura: en un acorde de séptima la tercera inversión es la séptima
        # en el bajo, y ordenar los números pondría esa nota en cualquier lado.
        inversion = stack.index(bass_pc) if bass_pc in stack else -1
        readings.append(ChordReading(
            root_pc=root_pc, quality=quality, pitch_classes=pcs,
            bass_pc=bass_pc, inversion=inversion, score=value,
            missing=missing, tones=tones,
            extra=tuple(pc for pc in sorted(weights) if pc not in pcs),
            prefer_flats=prefer_flats))
    readings.sort(key=lambda r: -r.score)
    return readings


def best_and_alternative(
    readings: Sequence[ChordReading],
) -> Tuple[Optional[ChordReading], Optional[ChordReading], bool]:
    """
    La lectura elegida, la que le compite, y si la cosa está dudosa.

    Hay dos motivos para ofrecer una segunda lectura. Uno es el empate: dos
    acordes que explican las mismas notas casi igual de bien --- do-mi-sol-la
    es un Do6 y un Lam7 y no hay nada en esas cuatro notas que lo decida. El
    otro es la inversión: cuando el acorde elegido no está en estado
    fundamental, la lectura que toma el bajo como fundamental es la que
    cualquiera se pregunta primero, y merece estar escrita aunque pierda.
    """
    if not readings:
        return None, None, False
    best = readings[0]
    # Sobre la misma fundamental no hay alternativa que ofrecer: un La menor
    # y un La disminuido cuando la quinta no suena son la misma lectura con
    # una nota inventada de distinta manera, y ofrecerlos como dos opciones
    # es ruido. Lo que compite de verdad es otra fundamental.
    rival = next((r for r in readings[1:] if r.root_pc != best.root_pc), None)
    doubtful = rival is not None and (best.score - rival.score) <= AMBIGUITY_MARGIN

    alternative = rival if doubtful else None
    if alternative is None and best.inversion > 0 and best.bass_pc is not None:
        on_the_bass = next(
            (r for r in readings
             if r.root_pc == best.bass_pc and r.score >= MIN_ALTERNATIVE),
            None)
        alternative = on_the_bass
    return best, alternative, doubtful


# ---------------------------------------------------------------------------
# Segmentación armónica
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """Un tramo de la pieza gobernado por un solo acorde."""

    start: float
    end: float
    bar_index: int
    offset: float
    sonorities: List[int] = field(default_factory=list)
    reading: Optional[ChordReading] = None
    alternative: Optional[ChordReading] = None
    doubtful: bool = False
    #: La disposición que se muestra: la vertical más llena del segmento.
    pitches: List[Optional[int]] = field(default_factory=list)
    #: Las clases de altura que suenan en la vertical que representa al
    #: segmento y **no** pertenecen al acorde, sin contar las que están
    #: adornando. Son las que el continuista igual tiene que cifrar: una
    #: cuarta suspendida o una novena sostenida son parte de lo que suena y
    #: sin ellas la cifra describe un acorde que nadie escuchó.
    figured_extras: Tuple[int, ...] = ()
    #: Todas las clases de altura que suenan en el segmento, adornos
    #: incluidos. El cifrado las necesita para saber si una nota del acorde
    #: llegó a sonar en algún momento.
    sounding_pcs: Tuple[int, ...] = ()
    #: Cuando la lectura es un acorde con sexta agregada: esa lectura y la
    #: séptima que explica las mismas notas ---Do6 y Lam7/Do son el mismo
    #: puñado---. Cuál de las dos se nombra lo decide la tonalidad
    #: (`_read_added_sixth`), que todavía no se conoce cuando se leen los
    #: acordes.
    added_sixth: Optional[Tuple[ChordReading, ChordReading]] = None
    # -- lo que agrega el análisis funcional --------------------------------
    roman: str = ""
    #: El grado solo, sin la cifra de inversión pegada. `roman` es lo que se
    #: escribe en un análisis armónico ---"V4/2/V"--- y ahí los números son
    #: parte del nombre del grado; pero puesto al lado del cifrado del bajo
    #: continuo, que también son números, no hay forma de saber dónde
    #: termina uno y empieza el otro: "V4/2" se leía como un cifrado "4/2"
    #: con una V colgando. Separados, cada uno se lee por lo que es.
    numeral: str = ""
    function: str = ""
    category: str = ""
    detail: str = ""
    source_mode: str = ""
    target_degree: int = 0
    relation: str = ""
    figure: str = ""
    sus_note: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def symbol(self) -> str:
        return self.reading.symbol if self.reading else "?"


def _weights_over(
    score: Score,
    sonorities: Sequence[Sonority],
    indices: Sequence[int],
) -> Dict[int, float]:
    """Cuánto suena cada clase de altura dentro de un tramo."""
    weights: Dict[int, float] = {}
    for position in indices:
        sonority = sonorities[position]
        per_bar, beat = score.metrics_at(sonority.bar_index)
        weight = sonority.duration * metric_weight(sonority.offset, per_bar, beat)
        bass = sonority.bass
        for voice, pitch in enumerate(sonority.pitches):
            if pitch is None:
                continue
            # El bajo pesa más: es la voz que decide la inversión y la que
            # el oído toma como fundamento, y sin este empujón una nota de
            # paso en una voz interna podía cambiar el acorde entero.
            share = weight * (1.35 if pitch == bass else 1.0)
            if voice in sonority.ornamental or voice in sonority.resolving:
                share *= ORNAMENT_WEIGHT
            weights[pitch % 12] = weights.get(pitch % 12, 0.0) + share
    return weights


def _heard(sonorities: Sequence[Sonority], indices: Sequence[int],
           real: bool = False) -> set:
    """
    Las clases de altura que suenan en el tramo, tenidas incluidas.

    Con ``real``, sin las notas con forma de adorno: para decidir si un
    tramo cabe en un acorde se descuentan igual que al leerlo. Contándolas,
    un re de paso sobre un bajo solo en do no cabía en el Do de al lado y el
    tiempo quedaba sin nombre en medio de dos Do.
    """
    return {pitch % 12 for i in indices
            for voice, pitch in enumerate(sonorities[i].pitches)
            if pitch is not None
            and not (real and (voice in sonorities[i].ornamental
                               or voice in sonorities[i].resolving))}


def _too_thin(sonorities: Sequence[Sonority], indices: Sequence[int]) -> bool:
    """
    Un tramo con demasiado poco material para nombrar un acorde propio.

    El piso de tres voces de la pieza no alcanza: en una pieza a cuatro
    voces, un tiempo en el que canta la soprano sola tiene una nota, y esa
    nota salía cifrada como acorde --- un fa suelto pasaba a ser Fa mayor
    con grado y función. Se mide sobre lo que **suena** en el tramo,
    tenidas incluidas, y de dos maneras a la vez: cuántas notas suenan
    juntas como máximo y cuántas clases de altura se oyen en todo el tramo.

    Con tres notas juntas siempre alcanza, aunque se doblen en octavas: es
    el coral que dobla la fundamental y omite la quinta. Con dos alcanza si
    entre las dos recorren tres clases de altura --- un bajo de Alberti
    debajo de una melodía dibuja el acorde aunque nunca suenen tres a la
    vez ---. Una línea sola no alcanza nunca: una melodía no es un acorde.
    """
    widest = max((len(sonorities[i].sounding) for i in indices), default=0)
    if widest >= MIN_VOICES_FOR_CHORD:
        return False
    if widest <= 1:
        return True
    return len(_heard(sonorities, indices)) < MIN_VOICES_FOR_CHORD


def _thin_run(sonorities: Sequence[Sonority], indices: Sequence[int],
              best: Optional[ChordReading]) -> Optional[ChordReading]:
    """
    La lectura de una racha de tramos flacos seguidos, o None.

    Se nombra sólo si hubo al menos dos voces sonando juntas --- una línea
    sola no es un acorde aunque arpegie --- y si **todas** las notas que se
    oyen son del acorde leído. Lo segundo es lo que separa a dos voces que
    dibujan una tríada de un dúo que camina por grados: el dúo junta cinco
    clases de altura que ningún acorde explica.
    """
    if best is None:
        return None
    widest = max((len(sonorities[i].sounding) for i in indices), default=0)
    if widest < 2:
        return None
    heard = _heard(sonorities, indices, real=True)
    if len(heard) < MIN_VOICES_FOR_CHORD:
        return None
    return best if heard <= set(best.pitch_classes) else None


def _window_indices(sonorities: Sequence[Sonority],
                    start: float, end: float) -> List[int]:
    return [i for i, s in enumerate(sonorities)
            if s.onset < end - EPSILON and s.end > start + EPSILON]


#: Por debajo de este puntaje, la lectura de un tiempo entero se considera
#: mala y se prueba partirlo en dos. Un tiempo con dos acordes distintos
#: --- media negra cada uno --- lee pésimo como acorde único, y ése es
#: justamente el caso que hay que rescatar.
SPLIT_THRESHOLD = 0.72

#: Cuánto tiene que mejorar la lectura al partir un tiempo para que valga la
#: pena partirlo. Sin margen, cualquier adorno consigue su propio acorde.
SPLIT_GAIN = 0.12

#: Las tríadas con las que se arma un tiempo partido. La aumentada no: en
#: medio tiempo casi siempre es una apoyatura sobre una tríada mayor.
_TRIADS = ("", "m", "dim")


def _two_triads(whole: ChordReading,
                halves: Sequence[Optional[ChordReading]]) -> bool:
    """
    ¿El acorde de séptima de este tiempo es la suma de dos tríadas seguidas?

    Es el otro caso en que un tiempo tiene dos acordes, y el umbral de
    `SPLIT_THRESHOLD` no lo ve porque el tiempo entero lee **bien**: sol-si
    bemol-re en la primera corchea y mi bemol-sol-si bemol en la segunda
    suman un Mi bemol con séptima mayor que explica todo, y la lectura
    "Mibmaj7/Sol" salía en lugar de vi - IV6, que es lo que está escrito. En
    los corales de Bach el ritmo armónico baja a la corchea todo el tiempo.

    Se pide mucho para partir, porque partir de más es justo lo que hay que
    evitar ---una nota de paso no abre un acorde---: las dos mitades leen
    cada una una tríada con su fundamental y su tercera, con fundamentales
    distintas, cada una explica su mitad al menos tan bien como la séptima
    explica el tiempo, y entre las dos son exactamente las notas de esa
    séptima. Una nota de paso no llega a esto: ya entra con su peso de
    adorno, y la mitad donde suena no lee una tríada completa por ella.
    """
    if len(whole.pitch_classes) < 4 or len(halves) != 2:
        return False
    for half in halves:
        if half is None or half.quality not in _TRIADS:
            return False
        if {_ROOT, _THIRD} & set(half.missing) or half.extra:
            return False
        if half.score < whole.score:
            return False
    first, second = halves
    if first.root_pc == second.root_pc:
        return False
    return (set(first.pitch_classes) | set(second.pitch_classes)
            == set(whole.pitch_classes))


#: Las suspendidas, con la nota que suspende (semitonos sobre la
#: fundamental) y adónde puede resolver, también en semitonos sobre la
#: fundamental: la cuarta baja a la tercera, mayor o menor; la segunda sube
#: a la tercera o baja a la fundamental, que es el retardo de novena.
_SUSPENDED_TONE = {"sus4": (5, (3, 4)), "7sus4": (5, (3, 4)),
                   "sus2": (2, (3, 4, 0))}


def _suspension_inside(sonorities: Sequence[Sonority], indices: Sequence[int],
                       reading: ChordReading, start: float, end: float) -> bool:
    """
    Marcar la cuarta suspendida que resuelve dentro del mismo tiempo.

    Una cuarta que suena en la primera corchea del tiempo y baja a la
    tercera en la segunda es un retardo, no un acorde suspendido: el acorde
    de ese tiempo es la tríada, como dice cualquier análisis de un coral. Por
    pesar el tiempo fuerte más que el contratiempo, la cuarta ganaba y el
    coral salía lleno de "Re sus4" donde Bach escribió Re mayor con un
    retardo. La que dura el tiempo entero y resuelve en el siguiente sí sigue
    siendo suspendida ---ésa se nombra y se dice que resuelve---: lo que
    decide es si la resolución llega **antes de que termine el tiempo**.

    Marca las verticales donde suena la nota suspendida (`resolving`) y
    devuelve si marcó alguna. Sólo si algo ataca en el tiempo: una
    suspensión es una nota que se queda mientras las otras cambian, y si la
    vertical viene entera del tiempo anterior no hay nada contra qué
    suspender ---y marcarla descontaría también el tiempo de antes, que la
    comparte---.
    """
    spec = _SUSPENDED_TONE.get(reading.quality)
    if (spec is None or not indices
            or sonorities[indices[0]].onset < start - EPSILON):
        return False
    step, targets = spec
    suspended = (reading.root_pc + step) % 12
    thirds = {(reading.root_pc + target) % 12 for target in targets}
    first = sonorities[indices[0]]
    marked = False
    for voice, pitch in enumerate(first.pitches):
        if pitch is None or pitch % 12 != suspended:
            continue
        held: List[int] = []
        for position in indices:
            sonority = sonorities[position]
            now = (sonority.pitches[voice]
                   if voice < len(sonority.pitches) else None)
            if now == pitch:
                held.append(position)
                continue
            if (now is not None and held and 1 <= abs(now - pitch) <= 2
                    and now % 12 in thirds
                    and sonority.onset < end - EPSILON):
                for spot in held:
                    if voice not in sonorities[spot].resolving:
                        sonorities[spot].resolving = tuple(
                            sorted(set(sonorities[spot].resolving) | {voice}))
                        marked = True
            break
    return marked


def _changes_harmony(before: Sonority, after: Sonority) -> bool:
    """
    ¿El paso de una vertical a la otra cambia de acorde o resuelve un adorno?

    Una sola voz que se mueve por grado conjunto mientras las demás se
    quedan es una resolución: la cuarta suspendida que baja a la tercera, la
    apoyatura que sube a la nota real. La mitad del tiempo donde está la
    disonancia lee una tríada que nadie escribió ---si sobre re-fa sostenido
    queda el si de antes, "Si menor"--- y partir ahí convierte un retardo en
    un acorde. Cambiar de acorde es otra cosa: se mueven dos voces o más, o
    alguna llega por salto.
    """
    moved = [(was, now) for was, now in zip(before.pitches, after.pitches)
             if was is not None and now is not None and was != now]
    return len(moved) >= 2 or any(abs(now - was) > 2 for was, now in moved)


def harmonic_segments(score: Score,
                      sonorities: Sequence[Sonority]) -> List[Segment]:
    """
    Agrupar las sonoridades en acordes.

    Se lee **un acorde por tiempo**, no uno por vertical: en música a varias
    voces cada nota de paso cambia la vertical sin cambiar la armonía, y
    leer acorde por vertical devuelve una progresión de fantasía llena de
    acordes que nadie escribió. El tiempo del compás es la unidad en la que
    se decide la armonía, y por eso es la unidad en la que se la lee.

    Después se hacen dos cosas: partir el tiempo que lea mal --- porque a
    veces sí hay dos acordes en un tiempo --- y unir los tiempos seguidos
    que lean el mismo acorde, para que un acorde de dos compases se muestre
    una vez y no ocho.
    """
    if not sonorities:
        return []
    fifths = implied_fifths(sonorities, score.fifths)
    prefer_flats = fifths < 0
    signature = signature_scale(fifths)
    finish = max(s.end for s in sonorities)

    # La grilla se arma compás por compás y no sumando siempre la misma
    # negra: con un cambio de compás en el medio, sumar el tiempo del
    # primero deja la grilla corrida respecto de las barras desde ahí hasta
    # el final, y con ella todos los tiempos fuertes de la segunda mitad.
    grid: List[float] = []
    for bar, start, per_bar in score.bar_grid():
        beat = score.metrics_at(max(1, bar))[1] or 1.0
        steps = max(1, int(round(per_bar / beat)))
        for step in range(steps):
            moment = start + step * beat
            if moment < finish - EPSILON and (not grid
                                              or moment > grid[-1] + EPSILON):
                grid.append(moment)
    if not grid:
        grid.append(0.0)
    grid.append(finish)

    # El piso es de **la pieza** y se mide en voces. Aplicado tiempo por
    # tiempo ---como estaba--- cualquier tiempo con las voces dobladas en
    # octavas quedaba sin acorde propio y se le sumaba al de antes: un compás
    # con tres acordes distintos salía cifrado una sola vez. Y medido en
    # alturas distintas, un coral que dobla la fundamental y omite la quinta
    # se quedaba sin análisis. Lo que hay que evitar es nombrar acordes con
    # una voz o dos escritas, y eso se cuenta mirando cuántas voces hay.
    if sum(1 for part in score.parts if part.voiced()) < MIN_VOICES_FOR_CHORD:
        return []

    raw: List[Tuple[Segment, bool]] = []
    for start, end in zip(grid, grid[1:]):
        indices = _window_indices(sonorities, start, end)
        if not indices:
            continue
        pieces = [(start, end, indices)]
        weights = _weights_over(score, sonorities, indices)
        bass_pc = _bass_of(sonorities, indices)
        whole = read_chord(weights, bass_pc, prefer_flats, signature)
        # Dos vueltas: una doble suspensión ---la cuarta y la novena sobre
        # el mismo bajo--- se lee primero sus4 y, descontada la cuarta, sus2.
        for _turn in range(2):
            if not (whole and _suspension_inside(sonorities, indices,
                                                 whole[0], start, end)):
                break
            whole = read_chord(_weights_over(score, sonorities, indices),
                               bass_pc, prefer_flats, signature)
        if (whole and end - start > beat / 2
                and (whole[0].score < SPLIT_THRESHOLD
                     or len(whole[0].pitch_classes) >= 4)):
            middle = (start + end) / 2.0
            left = _window_indices(sonorities, start, middle)
            right = _window_indices(sonorities, middle, end)
            if left and right:
                halves = []
                for a, b, part in ((start, middle, left), (middle, end, right)):
                    reading = read_chord(_weights_over(score, sonorities, part),
                                         _bass_of(sonorities, part),
                                         prefer_flats, signature)
                    halves.append((a, b, part, reading[0] if reading else None))
                worst = min(h[3].score if h[3] is not None else 0.0
                            for h in halves)
                if ((whole[0].score < SPLIT_THRESHOLD
                     and worst >= whole[0].score + SPLIT_GAIN)
                        or (_two_triads(whole[0], [h[3] for h in halves])
                            and _changes_harmony(sonorities[left[-1]],
                                                 sonorities[right[0]]))):
                    pieces = [(a, b, part) for a, b, part, _r in halves]

        for a, b, part in pieces:
            bar_index, offset = bar_and_offset(score, a)
            raw.append((Segment(start=a, end=b, bar_index=bar_index,
                                offset=offset, sonorities=list(part)),
                        _too_thin(sonorities, part)))

    # Unir los tramos seguidos que lean lo mismo, y recién ahí quedarse con
    # la lectura definitiva: leer sobre el segmento ya unido usa toda su
    # duración, que es más evidencia que la de un tiempo suelto.
    #
    # Un tramo flaco (`_too_thin`) no abre un acorde. Se suma al de antes si
    # cabe entero en él --- el bajo que repite la fundamental después del
    # acorde ---, o al que viene si cabe en ése --- las voces que entran de
    # a una sobre un bajo que ya venía sonando: esa nota tenida es parte del
    # acorde que las otras completan, y dejándola afuera el acorde empezaba
    # recién cuando entraba la última voz. Si no cabe en ninguno, la racha
    # de tramos flacos seguidos se lee entera (`_thin_run`): dos voces en
    # blancas que dibujan fa-la y después fa-do son un Fa aunque ningún
    # tiempo suelto llegue a tres notas.
    merged: List[Segment] = []
    waiting: List[Segment] = []

    def read(segment: Segment) -> Optional[ChordReading]:
        readings = read_chord(
            _weights_over(score, sonorities, segment.sonorities),
            _bass_of(sonorities, segment.sonorities), prefer_flats, signature)
        return best_and_alternative(readings)[0]

    def place(segment: Segment, best: Optional[ChordReading]) -> None:
        if (merged and best is not None and merged[-1].reading is not None
                and _same_harmony(merged[-1].reading, best)
                and abs(merged[-1].end - segment.start) <= EPSILON):
            merged[-1].end = segment.end
            merged[-1].sonorities.extend(segment.sonorities)
            return
        segment.reading = best
        merged.append(segment)

    def joined(run: List[Segment], last: Optional[Segment] = None) -> Segment:
        pieces = run + ([last] if last is not None else [])
        return Segment(start=pieces[0].start, end=pieces[-1].end,
                       bar_index=pieces[0].bar_index, offset=pieces[0].offset,
                       sonorities=[position for piece in pieces
                                   for position in piece.sonorities])

    def boundary(piece: Segment) -> int:
        """Qué tan fuerte es la barra donde empieza un tramo: 2 el compás,
        1 la mitad del compás, 0 un tiempo cualquiera."""
        per_bar = score.metrics_at(piece.bar_index)[0]
        if abs(piece.offset) <= EPSILON:
            return 2
        return 1 if abs(piece.offset - per_bar / 2.0) <= EPSILON else 0

    def settle_run(run: List[Segment]) -> None:
        """
        Leer una racha de tramos flacos, entera o por partes.

        Entera si cabe en un acorde. Si no, se parte por donde la música se
        parte ---primero en las barras de compás, después en la mitad del
        compás--- y se prueba cada pedazo. Es lo que pasa con un bajo de
        Alberti debajo de una melodía en blancas: cada tiempo tiene dos
        notas, ningún tiempo suelto llega a un acorde, y la racha entera
        junta el Do de un compás con el Fa del siguiente y no cabía en
        ninguno, así que compases enteros quedaban sin nombre.
        """
        if not run:
            return
        whole = joined(run)
        best = _thin_run(sonorities, whole.sonorities, read(whole))
        if best is not None:
            place(whole, best)
            return
        strengths = [boundary(piece) for piece in run[1:]]
        strongest = max(strengths, default=0)
        if strongest == 0:
            return
        start = 0
        for index, strength in enumerate(strengths, start=1):
            if strength == strongest:
                settle_run(run[start:index])
                start = index
        settle_run(run[start:])

    def settle() -> None:
        if not waiting:
            return
        run = list(waiting)
        waiting.clear()
        settle_run(run)

    for segment, thin in raw:
        heard = _heard(sonorities, segment.sonorities, real=True)
        if thin:
            if waiting and abs(waiting[-1].end - segment.start) > EPSILON:
                settle()
            if (not waiting and merged and merged[-1].reading is not None
                    and abs(merged[-1].end - segment.start) <= EPSILON
                    and heard <= set(merged[-1].reading.pitch_classes)):
                merged[-1].end = segment.end
                merged[-1].sonorities.extend(segment.sonorities)
            else:
                waiting.append(segment)
            continue
        best = read(segment)
        if waiting:
            # Lo que de la racha cabe en este acorde se le suma: no sólo la
            # racha entera, también su cola. El tiempo flaco que está justo
            # antes es casi siempre el principio de este acorde ---el bajo
            # que lo empieza solo--- aunque lo que vino más atrás sea otro.
            cut = len(waiting)
            if (best is not None
                    and abs(waiting[-1].end - segment.start) <= EPSILON):
                allowed = set(best.pitch_classes)
                while cut > 0 and _heard(
                        sonorities, joined(waiting[cut - 1:]).sonorities,
                        real=True) <= allowed:
                    cut -= 1
            tail = waiting[cut:]
            del waiting[cut:]
            settle()
            if tail:
                segment = joined(tail, segment)
        place(segment, best)
    settle()

    for segment in merged:
        weights = _weights_over(score, sonorities, segment.sonorities)
        readings = read_chord(weights,
                              _bass_of(sonorities, segment.sonorities),
                              prefer_flats, signature)
        best, alternative, doubtful = best_and_alternative(readings)
        segment.reading = best
        segment.alternative = alternative
        segment.doubtful = doubtful
        twin = _seventh_twin(best, readings)
        segment.added_sixth = (best, twin) if twin is not None else None
        vertical = _representative(score, sonorities, segment)
        segment.pitches = list(vertical.pitches) if vertical is not None else []
        entering = (sonorities[segment.sonorities[0]]
                    if segment.sonorities else None)
        segment.figured_extras = _hanging(entering, segment.reading)
        segment.sounding_pcs = tuple(sorted(
            {pitch % 12 for position in segment.sonorities
             for pitch in sonorities[position].sounding}))
    return merged


def _representative(score: Score, sonorities: Sequence[Sonority],
                    segment: Segment) -> Optional[Sonority]:
    """
    La vertical que representa al segmento en pantalla.

    La más llena, y a igualdad de voces la que caiga en la posición más
    fuerte. La primera no sirve: en una textura arpegiada el segmento
    empieza con una nota sola, y mostrar esa nota como si fuera el acorde
    deja al usuario mirando un do donde hay un Do con séptima.
    """
    best = None
    best_key = (-1, -1.0)
    for position in segment.sonorities:
        sonority = sonorities[position]
        per_bar, beat = score.metrics_at(sonority.bar_index)
        rank = (len(sonority.sounding),
                metric_weight(sonority.offset, per_bar, beat))
        if rank > best_key:
            best_key, best = rank, sonority
    return best


def _hanging(sonority: Optional[Sonority],
             reading: Optional[ChordReading]) -> Tuple[int, ...]:
    """
    Lo que suena al entrar el acorde y no es del acorde, sin contar adornos.

    Es lo que se le escapaba al cifrado: con cuatro voces sonando, una que
    sostiene una nota ajena --- la cuarta de una suspensión, una novena ---
    desaparecía de la cifra, porque la cifra salía del acorde y esa nota no
    está en el acorde. La nota que adorna sí se calla, que es lo correcto:
    un continuista no cifra una nota de paso.

    Se mira **la vertical con la que el acorde entra**, que es la que el
    continuista tiene delante al leer esa nota del bajo, y se exige que haya
    una sola nota ajena. Con dos o más lo que falla es la lectura del acorde
    --- pasa en un segmento largo que junta dos armonías --- y cifrarlas
    todas devolvía cifras de cuatro números que no dicen nada.
    """
    if sonority is None or reading is None:
        return ()
    if sonority.bass is None or sonority.bass % 12 != reading.bass_pc:
        return ()
    inside = set(reading.pitch_classes)
    found = []
    for voice, pitch in enumerate(sonority.pitches):
        if pitch is None or pitch % 12 in inside:
            continue
        if voice in sonority.ornamental:
            continue
        if pitch % 12 not in found:
            found.append(pitch % 12)
    return tuple(found) if len(found) == 1 else ()


def _same_harmony(before: ChordReading, after: ChordReading) -> bool:
    """
    Dos lecturas seguidas que son el mismo acorde.

    Iguales, o una contenida en la otra sobre la misma fundamental. Lo
    segundo es lo que pasa en cualquier textura arpegiada: la séptima llega
    tarde, así que el primer tiempo lee tríada y el segundo lee séptima. Son
    el mismo acorde --- la séptima no lo empieza de nuevo --- y separarlos
    llenaba el análisis de acordes que duraban medio tiempo.
    """
    if before.root_pc != after.root_pc:
        return False
    if before.bass_pc != after.bass_pc:
        # Un cambio de bajo es un acorde nuevo aunque las notas de arriba no
        # se muevan: cambia la inversión, cambia el cifrado y, en un bajo
        # cromático descendente, cambia lo único que está pasando en la
        # pieza. Uniéndolos, seis acordes de esa cadencia se leían como uno.
        return False
    if before.quality == after.quality:
        return True
    first, second = set(before.pitch_classes), set(after.pitch_classes)
    return first <= second or second <= first


#: La séptima que tiene las mismas notas que cada acorde con sexta agregada,
#: y a qué distancia está su fundamental: Do6 es Lam7 (la, una sexta mayor
#: arriba de do) y Dom6 es Lað7.
_SIXTH_TWINS = {"6": "m7", "m6": "m7b5"}


def _seventh_twin(best: Optional[ChordReading],
                  readings: Sequence[ChordReading]) -> Optional[ChordReading]:
    """La lectura como séptima de un acorde leído con sexta agregada."""
    if best is None or best.quality not in _SIXTH_TWINS:
        return None
    root = (best.root_pc + 9) % 12
    wanted = _SIXTH_TWINS[best.quality]
    return next((r for r in readings
                 if r.root_pc == root and r.quality == wanted
                 and set(r.pitch_classes) == set(best.pitch_classes)), None)


def _read_added_sixth(segment: Segment, key: KeyReading) -> None:
    """
    Nombrar como séptima el acorde con sexta agregada que no es la tónica.

    Do-mi-sol-la con el do en el bajo es un Do6 y un Lam7 en primera
    inversión, y las notas no deciden: la fundamental en el bajo desempata
    a favor del Do6 por un pelo. Pero el análisis tonal dice otra cosa según
    dónde esté el acorde. Sobre el cuarto grado es el ii6/5 ---el
    predominante más común de la música tonal, la "sexta agregada" de
    Rameau--- y leyéndolo Do6 los corales de Bach salían llenos de IV y de
    iv donde cualquier análisis escribe ii6/5 y iiø6/5. Sobre la tónica, en
    cambio, es el acorde de tónica con sexta del jazz, y ahí se queda. Y
    sobre la dominante tampoco se toca: Sol-si-re-mi es una dominante con
    la sexta de adorno, no un iii6/5.

    Se decide desde el par guardado y no desde la lectura del momento, así
    que se puede volver a pedir con otra tonalidad ---la escuelita relee con
    la de la consigna--- y contesta lo mismo que si hubiera sido la primera.
    La lectura que pierde queda como alternativa: las dos son ciertas.
    """
    if segment.added_sixth is None:
        return
    sixth, seventh = segment.added_sixth
    on_tonic_or_dominant = ((sixth.root_pc - key.tonic_pc) % 12
                            in (0, PERFECT_FIFTH))
    chosen, other = (sixth, seventh) if on_tonic_or_dominant else (seventh, sixth)
    chosen.prefer_flats = other.prefer_flats = (
        segment.reading.prefer_flats if segment.reading is not None
        else sixth.prefer_flats)
    segment.reading, segment.alternative = chosen, other
    segment.doubtful = True


def _root_diminished_sevenths(segments: Sequence[Segment]) -> None:
    """
    Darle a cada séptima disminuida la fundamental que dice su resolución.

    La séptima disminuida es simétrica: sus cuatro notas están a tres
    semitonos una de otra y cualquiera de ellas puede ser la fundamental. Las
    notas no deciden y el bajo desempataba, así que en un coral en si menor
    el vii°6 ---la#-do#-mi con el do# en el bajo, y el sol de paso--- salía
    "Do#dim7" y se nombraba sensible del sexto grado. Lo que decide es
    adónde va: la fundamental es la sensible del acorde que sigue, un
    semitono debajo de él. Si el que sigue no está a un semitono de ninguna
    de las cuatro, se queda como estaba.
    """
    for index, segment in enumerate(segments[:-1]):
        reading = segment.reading
        following = segments[index + 1].reading
        if reading is None or following is None or reading.quality != "dim7":
            continue
        root = (following.root_pc - 1) % 12
        if root == reading.root_pc or root not in reading.pitch_classes:
            continue
        segment.reading = _rerooted(reading, root)


def _rerooted(reading: ChordReading, root: int) -> ChordReading:
    """La misma lectura simétrica, contada desde otra de sus notas."""
    entry = next(c for c in _CANDIDATES
                 if c[0] == reading.quality and c[1] == root)
    _quality, _root, pcs, stack, tones, _preference = entry
    absent = {pc for pc, role, _size in reading.tones if role in reading.missing}
    return ChordReading(
        root_pc=root, quality=reading.quality, pitch_classes=pcs,
        bass_pc=reading.bass_pc,
        inversion=(stack.index(reading.bass_pc)
                   if reading.bass_pc in stack else -1),
        score=reading.score,
        missing=tuple(role for pc, role, _size in tones if pc in absent),
        extra=reading.extra, prefer_flats=reading.prefer_flats, tones=tones)


def _bass_of(sonorities: Sequence[Sonority],
             indices: Sequence[int]) -> Optional[int]:
    """La clase de altura del bajo al empezar el tramo.

    Al empezar y no la más grave de todo el tramo: la inversión de un acorde
    la decide la nota que el bajo tiene cuando el acorde entra. Si el bajo
    después baja una tercera de paso, el acorde no cambió de inversión.
    """
    for position in indices:
        bass = sonorities[position].bass
        if bass is not None:
            return bass % 12
    return None


# ---------------------------------------------------------------------------
# Tonalidad
# ---------------------------------------------------------------------------

#: Cómo se nombran las notas, y lo decide el idioma: el castellano las dice
#: con solfeo ---Do, Re, Mi--- y el inglés con las letras que el motor ya
#: usa por dentro. La tabla vive en `engine.i18n` porque no es de acá: la
#: usan también el analizador y el pentagrama.

#: Cómo se nombra cada modo en el rótulo de la tonalidad.
MODE_NAMES = {
    "major": N("mayor"), "minor": N("menor"), "harmonic": N("menor armónica"),
    "dorian": N("dórico"), "phrygian": N("frigio"), "lydian": N("lidio"),
    "mixolydian": N("mixolidio"), "locrian": N("locrio"),
}

#: Qué modos se prueban al buscar la tonalidad, y cuánto se prefiere cada
#: uno a igualdad de evidencia. Mayor y menor van primero porque son lo que
#: una pieza es casi siempre; los modos existen y aparecen, pero declarar
#: dórico una pieza en menor que pasa una vez por el sexto mayor sería
#: cambiar el análisis entero por una nota.
KEY_CANDIDATE_MODES = (
    ("major", 0.55), ("minor", 0.50), ("harmonic", 0.30),
    ("dorian", 0.10), ("mixolydian", 0.10), ("phrygian", 0.06),
    ("lydian", 0.04), ("locrian", 0.0),
)


def spanish_note(pc: int, prefer_flats: bool = False) -> str:
    """Cómo se dice esa altura en el idioma en curso."""
    return i18n.note_name(pc, prefer_flats)


@dataclass
class KeyReading:
    """La tonalidad de la pieza y por qué se la eligió."""

    tonic_pc: int
    mode_key: str
    fifths: int = 0
    score: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    #: La partitura no trae armadura pero la música se escribe con bemoles.
    #: Es lo que pasa con todo lo que este programa exporta, que escribe en
    #: Do y pone los accidentes nota por nota.
    flat_spelling: bool = False

    @property
    def prefer_flats(self) -> bool:
        return self.fifths < 0 or self.flat_spelling

    @property
    def scale(self) -> List[int]:
        return harmony.MODES[self.mode_key].pitch_classes(self.tonic_pc)

    @property
    def label(self) -> str:
        return (f"{spanish_note(self.tonic_pc, self.prefer_flats)} "
                f"{tr(MODE_NAMES.get(self.mode_key, self.mode_key))}")


#: La escala de la armadura, como conjunto de clases de altura. Se arma
#: apilando quintas desde Fa, que es como se arma una armadura de verdad.
def signature_scale(fifths: int) -> List[int]:
    pcs = {(5 + 7 * step) % 12 for step in range(7)}   # Fa Do Sol Re La Mi Si
    if fifths > 0:
        for step in range(min(7, fifths)):
            pcs.discard((5 + 7 * step) % 12)
            pcs.add((6 + 7 * step) % 12)
    elif fifths < 0:
        for step in range(min(7, -fifths)):
            pcs.discard((11 - 7 * step) % 12)
            pcs.add((10 - 7 * step) % 12)
    return sorted(pcs)


def implied_fifths(sonorities: Sequence[Sonority], given: int = 0) -> int:
    """
    Qué armadura explica mejor lo que suena.

    Cuando la partitura trae armadura, manda la armadura y no hay nada que
    deducir. Cuando no la trae ---y no la traen las partituras que este
    mismo programa exporta, que escriben todo en Do y ponen los accidentes
    nota por nota--- hay que deducirla, porque de ella sale **cómo se
    escribe cada nota**: la misma altura es un la bemol o un sol sostenido
    según de qué lado del círculo de quintas esté la pieza, y una
    armonización en Fa leída con nombres de sostenidos se lee como si fuera
    de otra música.

    Se prueban las quince armaduras y gana la que deje menos notas afuera,
    con una preferencia mínima por la más simple para los empates.
    """
    if given:
        return given
    weights: Dict[int, float] = {}
    for sonority in sonorities:
        for pitch in sonority.sounding:
            weights[pitch % 12] = weights.get(pitch % 12, 0.0) + sonority.duration
    total = sum(weights.values())
    if not total:
        return 0
    best, best_value = 0, None
    for fifths in range(-6, 7):
        scale = set(signature_scale(fifths))
        value = (sum(w for pc, w in weights.items() if pc in scale) / total
                 - 0.012 * abs(fifths))
        if best_value is None or value > best_value + EPSILON:
            best, best_value = fifths, value
    return best


#: Lo que vale, junto, la evidencia del principio y del final de una pieza
#: en `detect_key`: el bajo final (2,6), el bajo inicial (0,9), el primer
#: acorde (1,4), empezar y terminar igual (0,8) y el acorde de reposo (1,8).
#: Una pieza que abre y cierra sobre la dominante se la acredita a su tónica
#: (`_framed_by_dominant`).
FRAME_EVIDENCE = 7.5

#: Cuánto mejor tiene que caer el material en la tonalidad menor que en la
#: del acorde que enmarca la pieza, como fracción de lo que suena.
FRAME_MARGIN = 0.08

#: Cuántas veces, por lo menos, tiene que resolver la dominante en la tónica
#: menor dentro de la pieza.
FRAME_ARRIVALS = 2


def _framed_by_dominant(segments: Sequence[Segment], weights: Dict[int, float],
                        total: float) -> Optional[int]:
    """
    La tónica menor de una pieza que abre y cierra sobre su dominante.

    Es el final frigio de los corales: la melodía está en un modo que
    termina sobre mi, Bach la armoniza en la menor y la pieza ---que además
    suele arrancar con la anacrusa sobre ese mismo acorde--- empieza y
    termina en Mi mayor. Todo lo que `detect_key` le cree al principio y al
    final se iba para Mi, y el coral entero se leía en Mi mixolidio con la
    mitad de los acordes cambiados de función.

    Se pide todo a la vez para no inventarlo en una pieza que de verdad está
    en Mi: que el primer y el último acorde sean el mismo acorde mayor, que
    el material caiga claramente mejor en la menor de una quinta abajo que
    en cualquier modo sobre el propio acorde, y que por dentro la dominante
    resuelva en esa tónica menor más de una vez.
    """
    if len(segments) < 3:
        return None
    first, last = segments[0].reading, segments[-1].reading
    if (first is None or last is None or first.root_pc != last.root_pc
            or first.quality not in ("", "7") or last.quality != ""):
        return None
    tonic = (last.root_pc + 5) % 12

    def fit(root: int, modes: Sequence[str]) -> float:
        return max(sum(w for pc, w in weights.items()
                       if pc in harmony.MODES[mode].pitch_classes(root))
                   for mode in modes) / total

    # Contra los modos en que ese acorde mayor puede ser la tónica sin
    # licencia. Los menores sobre el mismo acorde comparten las notas con la
    # menor de una quinta abajo ---mi frigio y la menor son la misma escala---
    # y no se pueden separar por el material: eso es justamente lo que
    # decide la cadencia de adentro.
    own = fit(last.root_pc, ("major", "mixolydian", "lydian"))
    if fit(tonic, ("minor", "harmonic")) < own + FRAME_MARGIN:
        return None
    arrivals = 0
    for before, after in zip(segments[1:-2], segments[2:-1]):
        chord, goal = before.reading, after.reading
        if chord is None or goal is None:
            continue
        if goal.root_pc != tonic or goal.quality not in ("m", "m7"):
            continue
        if ((chord.quality in ("", "7")
             and (chord.root_pc - tonic) % 12 == PERFECT_FIFTH)
                or (chord.quality in ("dim", "dim7")
                    and (tonic - chord.root_pc) % 12 == 1)):
            arrivals += 1
    return tonic if arrivals >= FRAME_ARRIVALS else None


def detect_key(score: Score,
               sonorities: Sequence[Sonority],
               segments: Sequence[Segment]) -> KeyReading:
    """
    De qué tonalidad es la pieza.

    Tres evidencias, en orden de peso:

    * **La nota de reposo.** Donde la música se queda quieta al final es la
      tónica, y es lo más confiable que hay: una pieza puede empezar en
      cualquier acorde, pero termina en el suyo.
    * **La armadura.** Dice qué siete notas se usan, y por eso no alcanza
      sola: una armadura sin alteraciones sirve para Do mayor, La menor y
      Re dórico por igual. Sirve para armar la lista de candidatos.
    * **Lo que suena.** Cuánto del material cae dentro de la escala, y si
      la sensible aparece --- porque una sensible sostenida en una pieza
      con armadura de La menor es lo que separa la menor armónica de la
      natural.
    """
    weights: Dict[int, float] = {}
    for sonority in sonorities:
        per_bar, beat = score.metrics_at(sonority.bar_index)
        weight = sonority.duration * metric_weight(sonority.offset, per_bar, beat)
        for pitch in sonority.sounding:
            weights[pitch % 12] = weights.get(pitch % 12, 0.0) + weight
    total = sum(weights.values()) or 1.0

    # La armadura **escrita** arma la lista de candidatos: es lo que el
    # compositor declaró y no se discute. La deducida sirve sólo para
    # escribir los nombres, que es otra pregunta --- usándola también para
    # esto, una pieza en Do con dos préstamos del menor pasaba a analizarse
    # en mixolidio, porque los préstamos corrían la armadura deducida.
    diatonic = set(signature_scale(score.fifths))
    flat_spelling = implied_fifths(sonorities, score.fifths) < 0
    first_bass = next((s.bass for s in sonorities if s.bass is not None), None)
    last_bass = next((s.bass for s in reversed(sonorities)
                      if s.bass is not None), None)
    first_root = segments[0].reading.root_pc if segments and segments[0].reading else None
    last = segments[-1].reading if segments and segments[-1].reading else None
    penultimate = (segments[-2].reading
                   if len(segments) >= 2 and segments[-2].reading else None)
    framed = _framed_by_dominant(segments, weights, total)

    scored: List[KeyReading] = []
    for tonic_pc in range(12):
        for mode_key, preference in KEY_CANDIDATE_MODES:
            scale = harmony.MODES[mode_key].pitch_classes(tonic_pc)
            reasons: List[str] = []
            value = preference

            inside = sum(w for pc, w in weights.items() if pc in scale) / total
            value += 3.0 * inside

            shared = len(set(scale) & diatonic)
            value += 0.45 * shared
            if shared == 7:
                reasons.append("usa exactamente las notas de la armadura")

            if last_bass is not None and last_bass % 12 == tonic_pc:
                value += 2.6
                reasons.append("la pieza reposa sobre la tónica en el bajo")
            if first_bass is not None and first_bass % 12 == tonic_pc:
                value += 0.9
                reasons.append("arranca desde la tónica en el bajo")
            if first_root is not None and first_root == tonic_pc:
                # El primero pesa casi tanto como el último. Una pieza puede
                # empezar en cualquier acorde, pero la enorme mayoría
                # empieza en el suyo: es lo que instala la tonalidad en el
                # oído antes de que haya con qué compararla. Con el peso
                # simbólico que tenía, un fragmento que se iba a reposar a
                # otro grado se leía entero en la tonalidad de ese grado.
                value += 1.4
                reasons.append("arranca en la tónica")
                if last is not None and last.root_pc == tonic_pc:
                    # Empezar y terminar en el mismo acorde es la evidencia
                    # más barata que hay y no estaba contada: dos veces la
                    # misma nota en los dos lugares donde la tonalidad se
                    # afirma.
                    value += 0.8
                    reasons.append("empieza y termina en el mismo acorde")
            # Un acorde disminuido no reposa: es el más inestable que hay
            # y ninguna pieza termina en él como tónica. Sin esta salvedad,
            # una armonización que cerraba en un vii° se analizaba entera en
            # locrio --- un modo que casi no se usa --- sólo por dónde se
            # detuvo la búsqueda.
            resting = (last is not None and last.root_pc == tonic_pc
                       and last.quality not in ("dim", "dim7", "m7b5", "aug"))
            if resting:
                value += 1.8
                reasons.append(trf("el último acorde es {symbol}",
                                   symbol=last.symbol))
                major_tonic = 4 in [(pc - tonic_pc) % 12 for pc in last.pitch_classes]
                # La tercera de Picardía existe en la música tonal en modo
                # menor y no en los modos: un frigio que termina con la
                # tercera mayor no es un frigio con licencia, es que la
                # tónica era otra. Por eso el descuento suave es sólo para
                # la menor, y el resto paga el error completo.
                if mode_key in ("minor", "harmonic") and major_tonic:
                    value -= 0.35
                    reasons.append("termina con tercera de Picardía")
                elif mode_key in ("dorian", "phrygian", "locrian") and major_tonic:
                    value -= 1.2
                elif not major_tonic and mode_key in ("major", "lydian",
                                                      "mixolydian"):
                    value -= 1.2
                foreign = set(last.pitch_classes) - set(scale)
                if (mode_key in ("minor", "harmonic") and major_tonic
                        and tonic_pc in (first_root,
                                         None if first_bass is None
                                         else first_bass % 12)
                        and framed != (tonic_pc + 5) % 12):
                    # La tercera de Picardía ya pagó lo suyo arriba y no
                    # vuelve a cobrarse acá: es ajena a la escala menor por
                    # definición. Sin esta salvedad un coral en fa menor que
                    # cierra en Fa mayor pagaba dos veces su final y se leía
                    # entero en fa mixolidio. Vale sólo si la pieza arrancó
                    # en esa tónica: es la tónica que se ilumina al final de
                    # una pieza que ya la había instalado, no un acorde
                    # mayor cualquiera donde la música se detiene. Y no si
                    # ese acorde enmarca la pieza como dominante de otra
                    # tónica (`_framed_by_dominant`): ahí no es Picardía.
                    foreign.discard((tonic_pc + 4) % 12)
                if foreign:
                    # El acorde de reposo tiene una nota que no es de la
                    # escala. Como la tónica de una tonalidad es diatónica
                    # por definición, lo más probable es que la pieza no
                    # repose ahí sino que se detenga sobre su dominante ---
                    # que es exactamente lo que hace una semicadencia.
                    value -= 1.5

            # Un fragmento que arranca en un acorde y se detiene sobre la
            # dominante de ese acorde no está en la tonalidad donde para: se
            # paró en una semicadencia. Sin esto, cuatro acordes que
            # terminan en la dominante quedaban analizados en la tonalidad
            # de la dominante, y con ellos toda la frase.
            if last is not None and first_bass is not None:
                fifth_above = (last.root_pc - tonic_pc) % 12 == PERFECT_FIFTH
                major_last = 4 in [(pc - last.root_pc) % 12
                                   for pc in last.pitch_classes]
                if fifth_above and major_last and first_bass % 12 == tonic_pc:
                    value += 2.2
                    reasons.append("arranca en la tónica y se detiene sobre "
                                   "su dominante: la frase queda en "
                                   "semicadencia")

            if (penultimate is not None and last is not None
                    and last.root_pc == tonic_pc
                    and (penultimate.root_pc - tonic_pc) % 12 == PERFECT_FIFTH):
                value += 1.6
                reasons.append("cierra con una cadencia sobre la dominante")

            if framed == tonic_pc and mode_key in ("minor", "harmonic"):
                # Todo lo que el principio y el final le daban al acorde que
                # enmarca la pieza es, en realidad, de esta tónica.
                value += FRAME_EVIDENCE
                reasons.append("abre y cierra sobre su dominante y cadencia "
                               "en ella por dentro")

            leading = (tonic_pc + 11) % 12
            leading_weight = weights.get(leading, 0.0) / total
            if mode_key in ("minor", "dorian", "phrygian"):
                # Una sensible con peso real contradice el séptimo bajo del
                # modo: la pieza es menor armónica, no natural.
                value -= 4.0 * leading_weight
            elif mode_key == "harmonic":
                value += 3.0 * leading_weight - 0.25

            scored.append(KeyReading(tonic_pc=tonic_pc, mode_key=mode_key,
                                     fifths=score.fifths, score=value,
                                     reasons=reasons,
                                     flat_spelling=flat_spelling))

    if not scored:
        return KeyReading(tonic_pc=0, mode_key="major", fifths=score.fifths,
                          flat_spelling=flat_spelling)
    scored.sort(key=lambda k: -k.score)
    best = scored[0]
    # La confianza se mide contra la mejor lectura que proponga **otra**
    # tónica. La segunda de la lista suele ser la misma tónica en otro modo
    # --- La menor y La menor armónica --- y esa competencia no pone en duda
    # nada de lo que sigue: la tónica es la misma.
    rival = next((k for k in scored[1:] if k.tonic_pc != best.tonic_pc), None)
    gap = best.score - rival.score if rival is not None else 1.5
    best.confidence = max(0.0, min(1.0, gap / 1.5))
    return best


# ---------------------------------------------------------------------------
# Análisis funcional
# ---------------------------------------------------------------------------

_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")

#: Cómo se lee cada área funcional en pantalla.
FUNCTION_LABELS = {
    harmony.TONIC: "tónica",
    harmony.SUBDOMINANT: "subdominante",
    harmony.DOMINANT: "dominante",
}

#: Los modos de los que se puede tomar prestado un acorde, y en qué orden se
#: los prefiere cuando más de uno explica el préstamo.
#:
#: La menor melódica no está en `harmony.MODES` --- el generador no la
#: ofrece --- pero un intercambio modal sí puede venir de ella (el IV mayor
#: de una pieza en menor es exactamente eso), así que se la agrega acá y
#: sólo acá.
MELODIC_MINOR = (0, 2, 3, 5, 7, 9, 11)

INTERCHANGE_MODES: Tuple[Tuple[str, str, Tuple[int, ...]], ...] = (
    ("minor", "menor natural (eólico)", harmony.MODES["minor"].intervals),
    ("harmonic", "menor armónica", harmony.MODES["harmonic"].intervals),
    ("major", "mayor (jónico)", harmony.MODES["major"].intervals),
    ("mixolydian", "mixolidio", harmony.MODES["mixolydian"].intervals),
    ("dorian", "dórico", harmony.MODES["dorian"].intervals),
    ("melodic", "menor melódica", MELODIC_MINOR),
    ("phrygian", "frigio", harmony.MODES["phrygian"].intervals),
    ("lydian", "lidio", harmony.MODES["lydian"].intervals),
    ("locrian", "locrio", harmony.MODES["locrian"].intervals),
)

#: Calidad de la tríada que sale de cada grado, por los intervalos que hay
#: entre sus notas. Se usa para reconocer de qué grado de qué modo viene un
#: préstamo.
_QUALITY_BY_INTERVALS = {
    (4, 7): "", (3, 7): "m", (3, 6): "dim", (4, 8): "aug",
}


def _degree_numeral(root_pc: int, key: KeyReading) -> str:
    """
    El numeral romano de una fundamental, con su alteración si la tiene.

    Un acorde ajeno no tiene grado, pero sí tiene un lugar: bVI se llama así
    porque está un semitono debajo del sexto grado de la escala. Se busca el
    grado más cercano y se escribe la diferencia.
    """
    scale = key.scale
    if (key.mode_key in ("minor", "harmonic")
            and root_pc == (key.tonic_pc + 11) % 12):
        # La sensible de una pieza en menor es su séptimo grado, subido, y
        # se escribe vii°. Buscándola como "un semitono debajo de un grado"
        # aparecía primero la tónica, y el vii° de La menor salía "bI°".
        return "VII"
    for offset, sign in ((0, ""), (-1, "b"), (1, "#")):
        for index, pc in enumerate(scale):
            if (pc + offset) % 12 == root_pc:
                return sign + _ROMAN[index]
    return "?"


def _case_numeral(numeral: str, quality: str) -> str:
    """Mayúscula o minúscula según la calidad, con su símbolo si lo lleva."""
    minor_like = quality in ("m", "m7", "dim", "dim7", "m7b5", "mmaj7", "m6")
    accidental = "".join(c for c in numeral if c in "b#")
    body = numeral[len(accidental):]
    text = accidental + (body.lower() if minor_like else body)
    if quality in ("dim", "dim7"):
        text += "°"
    elif quality == "m7b5":
        text += "ø"
    elif quality == "aug":
        text += "+"
    return text


def _bare_numeral(reading: ChordReading, key: KeyReading) -> str:
    """El grado solo, sin la cifra de inversión."""
    numeral = _case_numeral(_degree_numeral(reading.root_pc, key), reading.quality)
    if reading.quality in ("sus4", "7sus4"):
        return numeral + ("7sus4" if reading.quality == "7sus4" else "sus4")
    return numeral


def _roman_with_figure(reading: ChordReading, key: KeyReading) -> str:
    numeral = _bare_numeral(reading, key)
    if reading.quality in ("sus4", "7sus4"):
        return numeral
    figure = reading.figure
    return numeral + (figure if figure else "")


def _minor_scale_tolerance(key: KeyReading) -> List[int]:
    """
    Las notas que una pieza en menor usa sin dejar de ser diatónica.

    En modo menor la sexta y la séptima suben o no según hacia dónde va la
    línea, y las cuatro notas conviven en la misma pieza sin que ninguna sea
    ajena. Analizar el V de una menor como acorde prestado sería no haber
    entendido el modo menor.
    """
    if key.mode_key not in ("minor", "harmonic"):
        return list(key.scale)
    # Sólo la sensible, y no también la sexta mayor. La sexta subida es la
    # menor melódica, y el acorde que la trae --- un IV mayor en una pieza
    # en menor --- es un intercambio modal de manual: tolerarla acá sería
    # esconder justo lo que hay que señalar.
    return sorted(set(key.scale) | {(key.tonic_pc + 11) % 12})


def label_segment(segment: Segment, key: KeyReading,
                  following: Optional[Segment] = None) -> None:
    """
    Decidir qué es y qué hace un acorde dentro de la tonalidad.

    Escribe sobre el propio segmento: numeral, área funcional, categoría
    ---diatónico, dominante aplicada, intercambio modal, cromático--- y una
    explicación en castellano de por qué.
    """
    _read_added_sixth(segment, key)
    reading = segment.reading
    if reading is None:
        segment.roman, segment.function, segment.category = "?", "", "desconocido"
        segment.numeral = "?"
        segment.detail = "no se pudo nombrar el acorde"
        return

    scale = key.scale
    tolerant = _minor_scale_tolerance(key)
    pcs = set(reading.pitch_classes)
    segment.roman = _roman_with_figure(reading, key)
    segment.numeral = _bare_numeral(reading, key)
    _spell_like_its_degree(segment)

    # -- suspensiones -------------------------------------------------------
    if reading.quality in ("sus4", "sus2", "7sus4"):
        segment.category = "suspendido"
        third = (reading.root_pc + (4 if (reading.root_pc + 4) % 12 in tolerant
                                    else 3)) % 12
        resolves = (following is not None and following.reading is not None
                    and following.reading.root_pc == reading.root_pc
                    and third in following.reading.pitch_classes)
        if resolves:
            segment.sus_note = ("la cuarta baja a la tercera sobre la misma "
                                "fundamental: es una suspensión resuelta")
            segment.detail = (trf("{symbol} resuelve en {symbol2}",
                                  symbol=reading.symbol,
                                  symbol2=following.reading.symbol))
        else:
            segment.sus_note = ("la cuarta ocupa el lugar de la tercera y no "
                                "se corrige: queda como sonoridad suspendida")
            segment.detail = "cuarta suspendida sin resolver"
        if reading.root_pc in scale:
            degree = scale.index(reading.root_pc) + 1
            segment.function = harmony.DEGREE_FUNCTION.get(
                degree, harmony.SUBDOMINANT)
        else:
            segment.function = harmony.SUBDOMINANT
        return

    # -- diatónico ----------------------------------------------------------
    # La fundamental se busca en la escala tolerante y no en la natural: en
    # menor, el vii° y el vii°7 se arman sobre la sensible, que es tan del
    # modo como el V que la lleva. Con la escala natural salían como
    # "sensible aplicada de i", que es nombrar dos veces lo mismo.
    if reading.root_pc in tolerant and pcs <= set(tolerant):
        degree = (scale.index(reading.root_pc) + 1
                  if reading.root_pc in scale else 7)
        segment.category = "diatónico"
        segment.function = harmony.DEGREE_FUNCTION.get(degree, harmony.SUBDOMINANT)
        segment.detail = trf("{degree}º grado de {label}",
                             degree=degree, label=key.label)
        return

    # -- tercera de Picardía ------------------------------------------------
    # El acorde final de una pieza en menor, con la tercera mayor. Es la
    # tónica, no la dominante del cuarto grado: sin esta pregunta caía en la
    # puerta de abajo y el último acorde de un coral en menor ---que es como
    # Bach termina casi todos--- salía cifrado "V/iv" en el lugar donde la
    # pieza reposa. Sólo el último: en el medio de la pieza, la tónica mayor
    # sí suele ir hacia el cuarto grado.
    if (following is None and key.mode_key in ("minor", "harmonic")
            and reading.root_pc == key.tonic_pc and reading.quality == ""):
        segment.category = "intercambio modal"
        segment.source_mode = "mayor (jónico)"
        segment.function = harmony.TONIC
        segment.detail = ("tercera de Picardía: la pieza en menor termina en "
                          "la tónica mayor")
        return

    # -- dominante aplicada (interdominante) --------------------------------
    if reading.quality in ("", "7"):
        # A una quinta abajo está el acorde al que apunta. La tónica queda
        # afuera: la dominante de la tónica es el V, que ya salió por la
        # puerta de lo diatónico, y llamarlo "V/I" sería inventar un efecto
        # donde sólo hay una dominante.
        target_pc = (reading.root_pc + 5) % 12
        if target_pc in scale and target_pc != key.tonic_pc:
            degree = scale.index(target_pc) + 1
            target_quality = _degree_quality(scale, degree - 1)
            numeral = _ROMAN[degree - 1]
            numeral = numeral.lower() if target_quality in ("m", "dim") else numeral
            arrives = (following is not None and following.reading is not None
                       and following.reading.root_pc == target_pc)
            segment.category = "dominante aplicada"
            _spell_towards(segment, target_pc, key, 4)
            # "V4/2 de V" es como se lee: la cifra va con el numeral y el
            # destino después. Separarla con un espacio dejaba "V7/V 4/2",
            # que se lee como si el 4/2 fuera del acorde de destino.
            segment.roman = "V" + (reading.figure if reading.quality == "7"
                                   else reading.figure or "") + "/" + numeral
            segment.numeral = "V/" + numeral
            segment.function = harmony.DOMINANT
            segment.target_degree = degree
            target_name = spanish_note(target_pc, key.prefer_flats)
            segment.detail = (
                trf("interdominante: es la dominante de {target_name} "
                    "({numeral}), y ",
                    target_name=target_name, numeral=numeral)
                + ("resuelve en él" if arrives else "no llega a resolver"))
            return

    # -- séptima disminuida / sensible aplicada -----------------------------
    if reading.quality in ("dim7", "dim", "m7b5"):
        target_pc = (reading.root_pc + 1) % 12
        if target_pc in scale:
            degree = scale.index(target_pc) + 1
            numeral = _ROMAN[degree - 1]
            if _degree_quality(scale, degree - 1) in ("m", "dim"):
                numeral = numeral.lower()
            arrives = (following is not None and following.reading is not None
                       and following.reading.root_pc == target_pc)
            if target_pc != key.tonic_pc or reading.root_pc not in scale:
                segment.category = "sensible aplicada"
                _spell_towards(segment, target_pc, key, -1)
                segment.roman = ("vii°7/" if reading.quality == "dim7"
                                 else "viiø7/" if reading.quality == "m7b5"
                                 else "vii°/") + numeral
                segment.numeral = segment.roman
                segment.function = harmony.DOMINANT
                segment.target_degree = degree
                segment.detail = (
                    trf("sensible aplicada: está un semitono debajo de "
                        "{spanish_note} y ",
                        spanish_note=spanish_note(target_pc, key.prefer_flats))
                    + ("resuelve en él" if arrives else "no llega a resolver"))
                return

    # -- sustituto tritonal -------------------------------------------------
    if (reading.quality == "7" and following is not None
            and following.reading is not None
            and (reading.root_pc - following.reading.root_pc) % 12 == 1):
        segment.category = "sustituto tritonal"
        segment.roman = "subV/" + _degree_numeral(
            following.reading.root_pc, key)
        segment.numeral = segment.roman
        segment.function = harmony.DOMINANT
        segment.detail = (trf("reemplaza a la dominante de {spanish_note}: "
                              "comparte con ella la tercera y la séptima y "
                              "resuelve bajando un semitono",
                              spanish_note=spanish_note(following.reading.root_pc, key.prefer_flats)))
        return

    # -- intercambio modal --------------------------------------------------
    borrowed = _borrowed_from(reading, key)
    if borrowed is not None:
        mode_key, mode_label, degree = borrowed
        segment.category = "intercambio modal"
        segment.source_mode = mode_label
        segment.function = _borrowed_function(segment.roman, key, reading)
        segment.detail = (trf("préstamo del {mode_label} de "
                              "{spanish_note}: ahí es el {degree}º grado",
                              mode_label=tr(mode_label),
                              spanish_note=spanish_note(key.tonic_pc, key.prefer_flats),
                              degree=degree))
        spec = harmony.BORROWED_CHORDS.get(_borrow_key(segment.roman))
        if spec is not None:
            segment.detail += ". " + tr(spec.description)
        return

    # -- cromatismo suelto --------------------------------------------------
    segment.category = "cromático"
    segment.function = harmony.SUBDOMINANT
    segment.detail = ("no pertenece a la escala ni se explica como "
                      "dominante aplicada o préstamo: es un acorde cromático")


def _spell_towards(segment: Segment, target_pc: int, key: KeyReading,
                   letters: int) -> None:
    """
    Escribir un acorde aplicado desde la letra de la nota a la que apunta.

    La sensible aplicada está una letra debajo de su destino y la dominante
    aplicada cuatro arriba. Con la preferencia de la pieza sola, una
    armonización en Do con un la bemol se leía con bemoles de punta a punta
    y el vii°/V salía Solb disminuido con Rebb en el bajo: el mismo sonido
    que Fa sostenido disminuido, escrito como otro acorde.
    """
    order = "CDEFGAB"
    target = harmony.root_name(target_pc, harmony.key_fifths(
        key.tonic_pc, harmony.MODES[key.mode_key]))
    wanted = order[(order.index(target[0]) + letters) % 7]
    for reading in (segment.reading, segment.alternative):
        if reading is None:
            continue
        if SHARP_NAMES[reading.root_pc][0] == wanted:
            reading.prefer_flats = False
        elif FLAT_NAMES[reading.root_pc][0] == wanted:
            reading.prefer_flats = True


def _spell_like_its_degree(segment: Segment) -> None:
    """
    Escribir el acorde con la alteración con la que se lo nombra.

    Un acorde que se llama bVI se escribe con bemol, y uno que se llama #iv
    con sostenido: el nombre del grado ya decidió de qué lado del círculo de
    quintas está esa nota. Sin esto, el sexto bemol de una pieza en Do
    aparecía como "Sol♯ mayor" al lado de un "bVI" --- las dos cosas ciertas
    y contradiciéndose en el mismo renglón.
    """
    numeral = segment.roman
    if not numeral or numeral[0] not in "b#":
        return
    flats = numeral[0] == "b"
    for reading in (segment.reading, segment.alternative):
        if reading is not None:
            reading.prefer_flats = flats


def _degree_quality(scale: Sequence[int], degree_index: int) -> str:
    """La calidad de la tríada que sale de un grado de la escala."""
    root = scale[degree_index % 7]
    third = (scale[(degree_index + 2) % 7] - root) % 12
    fifth = (scale[(degree_index + 4) % 7] - root) % 12
    return _QUALITY_BY_INTERVALS.get((third, fifth), "")


def _borrowed_from(reading: ChordReading,
                   key: KeyReading) -> Optional[Tuple[str, str, int]]:
    """
    De qué modo paralelo viene un acorde que no es de la tonalidad.

    Se prueban los modos sobre **la misma tónica**, que es lo que hace que
    un préstamo sea un préstamo y no una modulación: la pieza no se fue a
    otro lado, se trajo un acorde de su propio nombre en otro modo.
    """
    pcs = set(reading.pitch_classes)
    for mode_key, mode_label, intervals in INTERCHANGE_MODES:
        if mode_key == key.mode_key:
            continue
        scale = [(key.tonic_pc + step) % 12 for step in intervals]
        if not pcs <= set(scale):
            continue
        if reading.root_pc not in scale:
            continue
        degree_index = scale.index(reading.root_pc)
        expected = _degree_quality(scale, degree_index)
        actual = reading.quality
        # La séptima no cambia de qué modo viene el acorde: un iv y un iv7
        # se piden prestados al mismo lugar.
        base = {"m7": "m", "maj7": "", "7": "", "m7b5": "dim",
                "dim7": "dim", "mmaj7": "m", "6": "", "m6": "m"}.get(actual, actual)
        if base == expected:
            return mode_key, mode_label, degree_index + 1
    return None


#: De qué préstamo del catálogo se trata, leído del numeral. Sirve para
#: reaprovechar las descripciones que el generador ya tiene escritas en vez
#: de escribir otras.
def _borrow_key(roman: str) -> str:
    return roman.rstrip("0123456789/").strip()


def _borrowed_function(roman: str, key: KeyReading,
                       reading: ChordReading) -> str:
    """Qué área ocupa un préstamo.

    Primero se pregunta al catálogo del generador, que ya tiene decidido
    dónde se para cada uno de los préstamos habituales. Lo que no esté ahí
    cae al grado más cercano.
    """
    catalogued = harmony.BORROWED_FUNCTION.get(_borrow_key(roman))
    if catalogued:
        return catalogued
    scale = key.scale
    for index, pc in enumerate(scale):
        if abs(((reading.root_pc - pc + 6) % 12) - 6) <= 1:
            return harmony.DEGREE_FUNCTION.get(index + 1, harmony.SUBDOMINANT)
    return harmony.SUBDOMINANT


# ---------------------------------------------------------------------------
# Relaciones entre acordes y cadencias
# ---------------------------------------------------------------------------

#: Cómo se llama cada movimiento de fundamental, en semitonos ascendentes.
ROOT_MOTION_NAMES = {
    0: "misma fundamental",
    1: "ascenso de semitono", 11: "descenso de semitono",
    2: "ascenso de segunda", 10: "descenso de segunda",
    3: "ascenso de tercera menor", 9: "descenso de tercera menor",
    4: "ascenso de tercera mayor", 8: "descenso de tercera mayor",
    5: "ascenso de cuarta (descenso de quinta)",
    7: "ascenso de quinta (descenso de cuarta)",
    6: "tritono",
}


@dataclass
class Cadence:
    """Un punto de reposo, con el nombre que le corresponde."""

    kind: str
    index: int              # segmento donde cae la resolución
    bar_index: int
    detail: str
    #: Primer segmento del giro. Para las cadencias de dos acordes es el
    #: anterior a `index`; para las citas de varios acordes, donde empieza
    #: la cita.
    start: int = 0


def relate(segments: Sequence[Segment], key: KeyReading) -> List[Cadence]:
    """
    Escribir la relación de cada acorde con el siguiente y encontrar las
    cadencias.

    La relación se escribe sobre el propio segmento (``relation``); las
    cadencias salen aparte porque son un hecho de la frase y no del acorde:
    lo que hace cadencia a un V-I es que además ahí la música se detiene.
    """
    cadences: List[Cadence] = []
    if not segments:
        return cadences

    durations = sorted(s.duration for s in segments)
    median = durations[len(durations) // 2] if durations else 1.0

    for index, segment in enumerate(segments):
        following = segments[index + 1] if index + 1 < len(segments) else None
        if segment.reading is None:
            continue
        if following is None or following.reading is None:
            segment.relation = tr("final de la pieza")
            continue
        motion = (following.reading.root_pc - segment.reading.root_pc) % 12
        name = ROOT_MOTION_NAMES.get(motion, "movimiento cromático")
        area_from = FUNCTION_LABELS.get(segment.function, segment.function)
        area_to = FUNCTION_LABELS.get(following.function, following.function)
        # Se traduce cada pedazo y se pegan después: el renglón armado no
        # existe como clave del catálogo.
        if area_from and area_to:
            segment.relation = f"{tr(name)} · {tr(area_from)} → {tr(area_to)}"
        else:
            segment.relation = tr(name)

        # Una cadencia necesita las dos cosas: el giro y el reposo. El
        # reposo se reconoce porque el acorde de llegada dura más que la
        # media o porque ahí se termina la pieza.
        resting = (following.duration >= median * 1.5
                   or index + 2 >= len(segments))
        cadence = _cadence_kind(segment, following, key)
        # (el reposo se comprueba abajo)
        if (cadence and cadence[0] == "semicadencia"
                and index + 2 < len(segments)):
            # La frase no se detuvo: la dominante sigue de largo hasta la
            # tónica, y lo que hay ahí es la preparación de una cadencia
            # auténtica, no una cadencia propia. Siempre que esa tónica
            # también se detenga, que es lo que hace de ella la cadencia:
            # si la tónica pasa de largo, es la frase siguiente que arranca,
            # y el reposo estaba en la dominante. Sin esta salvedad no había
            # semicadencias en un coral, donde casi toda frase que termina
            # en la dominante empieza la siguiente desde la tónica.
            after = segments[index + 2]
            if (after.reading is not None
                    and after.reading.root_pc == key.tonic_pc
                    and after.function == harmony.TONIC
                    and (after.duration >= median * 1.5
                         or index + 3 >= len(segments))):
                cadence = None
        if cadence and resting:
            cadences.append(Cadence(kind=cadence[0], index=index + 1,
                                    bar_index=following.bar_index,
                                    detail=cadence[1], start=index))

    cadences.extend(quoted_cadences(segments, key))
    cadences.sort(key=lambda c: (c.start, c.index))
    return cadences


# ---------------------------------------------------------------------------
# Cadencias de cita
# ---------------------------------------------------------------------------
#
# Tres de las cadencias que hay que reconocer no son un giro de dos acordes
# sino una progresión entera con nombre propio, y el generador ya las tiene
# escritas: son las mismas `harmony.SET_PIECES` que puede citar al componer.
# Se leen de ahí y no se vuelven a escribir acá --- si alguna vez se corrige
# una nota de la frigia, el analizador tiene que dejar de reconocer la vieja
# en el mismo momento en que el generador deja de escribirla.

#: Cuántos semitonos tiene la tercera de cada calidad, como las nombra
#: `harmony.SetPiece`.
_SET_PIECE_THIRDS = {"major": 4, "minor": 3, "dim": 3, "halfdim": 3,
                     "dominant": 4}


def _third_of(reading: ChordReading) -> Optional[int]:
    """El intervalo de tercera del acorde, en semitonos sobre la fundamental."""
    for pc, role, _size in reading.tones:
        if role == _THIRD:
            return (pc - reading.root_pc) % 12
    return None


def _fits_set_piece(window: Sequence[Segment], piece, anchor: int) -> bool:
    """
    ¿Estos acordes son esa cita, leída desde esa tónica?

    Se compara fundamental y calidad, nada más. La séptima no se exige ni se
    prohíbe: el V de una frigia es un V con o sin séptima, y una cita no deja
    de serlo por eso. La disposición tampoco --- salvo donde la cita **es**
    una línea de bajo, y entonces el bajo sí se comprueba.
    """
    for position, (offset, quality) in enumerate(piece.chords):
        segment = window[position]
        reading = segment.reading
        if reading is None:
            return False
        root = (anchor + offset) % 12
        third = _SET_PIECE_THIRDS.get(quality, 4)
        if piece.bass_line:
            # Una cita que **es** una línea de bajo se reconoce por el bajo y
            # por las notas que suenan encima, no por el nombre del acorde.
            # El cuarto acorde del bajo cromático es la tónica con el sexto
            # bemol debajo, y eso se lee con la misma facilidad como un
            # séptima mayor sobre ese sexto: las dos lecturas son correctas y
            # sólo una coincide con el nombre que le puso el generador.
            if reading.bass_pc != (anchor + piece.bass_line[position]) % 12:
                return False
            wanted = {root, (root + third) % 12, (root + 7) % 12}
            if not wanted <= set(segment.sounding_pcs):
                return False
            continue
        if reading.root_pc != root:
            return False
        if _third_of(reading) != third:
            return False
    return True


def quoted_cadences(segments: Sequence[Segment],
                    key: KeyReading) -> List[Cadence]:
    """
    Buscar las progresiones con nombre propio que el generador sabe citar.

    Se prueban en todas las alturas y no sólo en la tónica de la pieza: un
    ciclo de quintas puede empezar donde quiera, y encontrarlo sólo cuando
    arranca en la tónica sería no encontrarlo casi nunca. Cuando no arranca
    en la tónica se lo dice, que es la mitad de lo interesante.
    """
    found: List[Cadence] = []
    taken: set = set()
    #: De la más larga a la más corta: el ciclo de Vivaldi contiene tramos
    #: que por sí solos parecen otra cosa, y la cita larga es la lectura
    #: correcta cuando entra entera.
    pieces = sorted(harmony.SET_PIECES.values(), key=len, reverse=True)
    for piece in pieces:
        length = len(piece.chords)
        for start in range(len(segments) - length + 1):
            window = segments[start:start + length]
            if any(position in taken
                   for position in range(start, start + length)):
                continue
            first = window[0].reading
            if first is None:
                continue
            anchor = (first.root_pc - piece.chords[0][0]) % 12
            if not _fits_set_piece(window, piece, anchor):
                continue
            taken.update(range(start, start + length))
            home = anchor == key.tonic_pc
            detail = tr(piece.description)
            if not home:
                detail += (trf(" Acá aparece sobre {spanish_note}, que no "
                               "es la tónica de la pieza.",
                               spanish_note=spanish_note(anchor, key.prefer_flats)))
            found.append(Cadence(kind=piece.label.lower(),
                                 index=start + length - 1,
                                 bar_index=window[-1].bar_index,
                                 detail=detail, start=start))
    return found


def _cadence_kind(before: Segment, after: Segment,
                  key: KeyReading) -> Optional[Tuple[str, str]]:
    if before.reading is None or after.reading is None:
        return None
    tonic = key.tonic_pc
    to_tonic = after.reading.root_pc == tonic
    from_dominant = (before.function == harmony.DOMINANT
                     and (before.reading.root_pc - tonic) % 12 == PERFECT_FIFTH)
    if from_dominant and to_tonic:
        perfect = (before.reading.inversion == 0 and after.reading.inversion == 0)
        return (("cadencia auténtica perfecta" if perfect
                 else "cadencia auténtica imperfecta"),
                "la dominante resuelve en la tónica"
                + ("" if perfect else ", pero alguno de los dos está invertido"))
    if from_dominant and (after.reading.root_pc - tonic) % 12 in (8, 9):
        return ("cadencia rota",
                "la dominante promete la tónica y entrega el sexto grado")
    if (before.function == harmony.SUBDOMINANT and to_tonic
            and (before.reading.root_pc - tonic) % 12 in (5, 2)):
        return ("cadencia plagal",
                "la subdominante llega a la tónica sin pasar por la dominante")
    if (after.function == harmony.DOMINANT
            and (after.reading.root_pc - tonic) % 12 == PERFECT_FIFTH):
        if (before.reading.root_pc - tonic) % 12 == 5 and before.reading.inversion == 1:
            return ("cadencia frigia",
                    "el bajo baja un semitono desde el cuarto grado hasta la "
                    "dominante")
        return ("semicadencia", "la frase se detiene sobre la dominante")
    # -- cadencia en otra tonalidad -----------------------------------------
    # Una dominante que resuelve en un acorde que no es la tónica ni la
    # dominante de la pieza: la frase cierra en otra tonalidad. Es lo que
    # hacen casi todas las frases del medio de un coral ---la relativa, la
    # subdominante, el tercer grado---, y mirando sólo la tónica de la pieza
    # la mitad de las fermatas de un coral quedaban sin cadencia.
    target = after.reading
    if (target.root_pc != tonic and target.quality in ("", "m")
            and before.reading.quality in ("", "7")
            and (before.reading.root_pc - target.root_pc) % 12 == PERFECT_FIFTH):
        perfect = before.reading.inversion == 0 and target.inversion == 0
        name = (f"{spanish_note(target.root_pc, key.prefer_flats)} "
                f"{tr(MODE_NAMES['major' if target.quality == '' else 'minor'])}")
        return (("cadencia auténtica perfecta" if perfect
                 else "cadencia auténtica imperfecta"),
                trf("la dominante de {name} resuelve en él: la frase cierra "
                    "en {name}, fuera de la tonalidad de la pieza", name=name))
    return None


# ---------------------------------------------------------------------------
# Conjuntos de acordes ajenos
# ---------------------------------------------------------------------------

@dataclass
class ForeignGroup:
    """Una tanda de acordes que no son de la tonalidad, leídos juntos."""

    start: int              # índice del primer segmento
    end: int                # índice del último, inclusive
    label: str
    detail: str


#: Cuántas **voces escritas** hace falta que haya para poder hablar de
#: acordes. Tres: un acorde es una tríada, y con una voz o dos no hay manera
#: de saber cuál de las tríadas que las contienen es la que suena. Sin este
#: piso, una nota sola en el pentagrama ya venía con nombre de acorde, grado
#: y función --- todo inventado.
#:
#: Se cuentan **voces** y no alturas distintas. Contando alturas, un coral a
#: cuatro voces que dobla la fundamental y omite la quinta ---que es lo más
#: común que hay--- no llegaba a tres clases de altura en ninguna vertical y
#: se quedaba sin análisis entero.
MIN_VOICES_FOR_CHORD = 3

#: Cuántos acordes seguidos hacen falta para hablar de una visita a otra
#: tonalidad en vez de un acorde de color suelto.
MIN_GROUP = 2

#: Hasta cuántos acordes es una tonicización de paso. Más que eso y la pieza
#: se fue de verdad: eso ya es una modulación.
TONICISATION_LIMIT = 3


def foreign_groups(segments: Sequence[Segment],
                   key: KeyReading) -> List[ForeignGroup]:
    """
    Juntar los acordes ajenos que se explican todos por lo mismo.

    Un acorde de fuera de la escala puede ser un color; tres seguidos son
    otra tonalidad. Se buscan tandas de acordes ajenos y se prueba si existe
    una tonalidad en la que **todos** ellos, más el acorde en el que la
    tanda desemboca, sean diatónicos. Si la hay, la pieza estuvo de visita
    ahí, y decirlo explica los tres de una vez en lugar de justificar cada
    uno por su lado.
    """
    groups: List[ForeignGroup] = []
    index = 0
    while index < len(segments):
        if segments[index].category in ("diatónico", "desconocido", ""):
            index += 1
            continue
        start = index
        while (index < len(segments)
               and segments[index].category not in ("diatónico", "desconocido", "")):
            index += 1
        end = index - 1
        if end - start + 1 < MIN_GROUP:
            continue
        run = list(segments[start:end + 1])
        landing = segments[index] if index < len(segments) else None
        if landing is not None:
            run.append(landing)
        home = _key_containing(run)
        if home is None:
            if _is_dominant_chain(segments, start, end):
                groups.append(ForeignGroup(
                    start=start, end=end,
                    label=trf("cadena de {end} dominantes",
                              end=end - start + 1),
                    detail="cada acorde es la dominante del que le sigue: la "
                           "pieza no se fue de la tonalidad, viene cayendo por "
                           "quintas hasta volver a ella"))
                continue
            groups.append(ForeignGroup(
                start=start, end=end,
                label=f"{end - start + 1} acordes ajenos seguidos",
                detail="no comparten una tonalidad: son colores sueltos, no "
                       "una visita a otra parte"))
            continue
        tonic_pc, mode_key = home
        if tonic_pc == key.tonic_pc and mode_key == key.mode_key:
            continue
        name = (f"{spanish_note(tonic_pc, key.prefer_flats)} "
                f"{tr(MODE_NAMES[mode_key])}")
        short = (end - start + 1) <= TONICISATION_LIMIT
        groups.append(ForeignGroup(
            start=start, end=end,
            label=("tonicización de " if short else "modulación a ") + name,
            detail=("estos acordes son todos diatónicos de " + name
                    + (", y la pieza vuelve enseguida" if short
                       else ": la pieza se instala ahí"))))
    return groups


def _is_dominant_chain(segments: Sequence[Segment], start: int,
                       end: int) -> bool:
    """
    Una tanda de aplicadas donde cada una cae en la siguiente.

    Es la otra explicación posible de varios acordes ajenos seguidos, y es
    la contraria a la de la modulación: no hay ninguna tonalidad que los
    contenga a todos justamente porque cada uno es la dominante prestada del
    que viene, y por eso mismo la pieza nunca se fue de casa.
    """
    if end <= start:
        return False
    for index in range(start, end + 1):
        segment = segments[index]
        if segment.category not in ("dominante aplicada", "sustituto tritonal"):
            return False
        following = segments[index + 1] if index + 1 < len(segments) else None
        if following is None or following.reading is None or segment.reading is None:
            return False
        step = (segment.reading.root_pc - following.reading.root_pc) % 12
        if step not in (PERFECT_FIFTH, 1):      # quinta abajo, o sustituto
            return False
    return True


def _key_containing(segments: Sequence[Segment]) -> Optional[Tuple[str, str]]:
    """La tonalidad en la que todos estos acordes son diatónicos, si existe."""
    readings = [s.reading for s in segments if s.reading is not None]
    if not readings:
        return None
    best = None
    for tonic_pc in range(12):
        for mode_key in ("major", "minor", "harmonic"):
            scale = set(harmony.MODES[mode_key].pitch_classes(tonic_pc))
            if mode_key in ("minor", "harmonic"):
                scale |= {(tonic_pc + 11) % 12}
            if all(set(r.pitch_classes) <= scale and r.root_pc in scale
                   for r in readings):
                # La última palabra la tiene el acorde de llegada: si es la
                # tónica de esa tonalidad, es ahí donde la música fue.
                score = 2 if readings[-1].root_pc == tonic_pc else 0
                score += 1 if mode_key == "major" else 0
                if best is None or score > best[0]:
                    best = (score, (tonic_pc, mode_key))
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Contrapunto: movimientos
# ---------------------------------------------------------------------------

MOTION_PARALLEL = "paralelo"
MOTION_SIMILAR = "directo"
MOTION_CONTRARY = "contrario"
MOTION_OBLIQUE = "oblicuo"
MOTION_STATIC = "quieto"

#: Tamaño diatónico de cada distancia en semitonos, para decidir si dos
#: voces mantienen "el mismo intervalo". Sin escritura no hay forma de saber
#: si tres semitonos son una tercera menor o una segunda aumentada, y para
#: esto da igual: lo que importa es que el intervalo no cambió de tamaño.
_GENERIC_SIZE = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 4, 6: 5, 7: 5, 8: 6, 9: 6,
                 10: 7, 11: 7}


def generic_interval(low: int, high: int) -> int:
    """Tamaño del intervalo entre dos alturas, en grados (1 = unísono)."""
    distance = abs(high - low)
    octaves, remainder = divmod(distance, 12)
    return octaves * 7 + _GENERIC_SIZE[remainder]


def motion_between(a_before: int, a_after: int,
                   b_before: int, b_after: int) -> str:
    """
    Qué clase de movimiento hacen dos voces entre dos acordes.

    Paralelo es el caso estricto: las dos en la misma dirección **y** el
    intervalo entre ellas sin cambiar de tamaño. Las dos en la misma
    dirección con el intervalo cambiando es movimiento directo, que es otra
    cosa y tiene otras consecuencias --- las quintas ocultas se hacen por
    movimiento directo, no por paralelo.
    """
    move_a = a_after - a_before
    move_b = b_after - b_before
    if move_a == 0 and move_b == 0:
        return MOTION_STATIC
    if move_a == 0 or move_b == 0:
        return MOTION_OBLIQUE
    if (move_a > 0) != (move_b > 0):
        return MOTION_CONTRARY
    before = generic_interval(min(a_before, b_before), max(a_before, b_before))
    after = generic_interval(min(a_after, b_after), max(a_after, b_after))
    return MOTION_PARALLEL if before == after else MOTION_SIMILAR


@dataclass
class MotionReport:
    """Los movimientos de un paso, par de voces por par de voces."""

    index: int              # sonoridad de partida
    bar_index: int
    offset: float
    pairs: Dict[Tuple[int, int], str] = field(default_factory=dict)
    #: Hacia dónde va cada una de las dos voces del par: -1, 0 o 1. Se
    #: guarda acá porque el movimiento no se mide contra la vertical de al
    #: lado sino contra la nota anterior **de cada voz**, así que la
    #: dirección no se puede deducir después restando dos verticales.
    ways: Dict[Tuple[int, int], Tuple[int, int]] = field(default_factory=dict)

    def count(self, kind: str) -> int:
        return sum(1 for value in self.pairs.values() if value == kind)


# ---------------------------------------------------------------------------
# Contrapunto: hallazgos
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """Algo que el contrapunto hace y conviene mirar."""

    kind: str
    label: str
    detail: str
    severity: str           # "grave" | "aviso" | "nota"
    index: int              # sonoridad donde empieza
    bar_index: int
    offset: float
    voices: Tuple[int, ...] = ()


SEVERITY_ORDER = {"grave": 0, "aviso": 1, "nota": 2}


def _both_sound(before: Sonority, after: Sonority, voice: int) -> bool:
    return (voice < len(before.pitches) and voice < len(after.pitches)
            and before.pitches[voice] is not None
            and after.pitches[voice] is not None)


def _voice_name(names: Sequence[str], index: int) -> str:
    return names[index] if index < len(names) else f"voz {index + 1}"


def _way(step: int) -> int:
    """Hacia dónde va una voz: arriba, abajo o a ningún lado."""
    return 0 if step == 0 else (1 if step > 0 else -1)


#: Cuánto silencio hace falta para que una voz se olvide de dónde venía.
#: Una negra: menos que eso es la separación entre dos notas ---así se
#: escriben los arpegios, con cada nota un pelo más corta que su figura---
#: y no un silencio. Sin este margen, cada nota del preludio de Bach entraba
#: "desde la nada" y no quedaba un solo movimiento que medir.
QUIET_ENOUGH = 1.0

#: Un momento anterior a cualquier momento de cualquier pieza. Es la marca
#: de la voz que viene sonando desde antes de que empezara a pasar algo.
SINCE_FOREVER = 1e9


def _previous_notes(
    sonorities: Sequence[Sonority],
) -> List[List[Optional[Tuple[int, float, float]]]]:
    """
    Para cada vertical, de dónde viene la nota que cada voz está tocando.

    Devuelve, voz por voz, ``(nota anterior, cuándo empezó, cuándo empezó la
    de ahora)``. Es lo que hace falta para medir el movimiento en una
    textura donde las voces no atacan a la vez: la nota anterior de una voz
    no está en la vertical de al lado ---ahí la voz sigue sosteniendo la
    misma--- sino más atrás, en el momento en que esa voz se movió. En un
    coral las dos cosas coinciden, porque las cuatro voces atacan juntas.

    Volver a atacar la misma nota empieza una nota nueva: repetir es
    quedarse quieto, y quedarse quieto mientras la otra se mueve es un
    movimiento oblicuo. Una voz que entra desde el silencio, en cambio, no
    viene de ningún lado y su casilla queda vacía.
    """
    width = max((len(sonority.pitches) for sonority in sonorities), default=0)
    sounding: List[Optional[int]] = [None] * width
    started = [0.0] * width
    before: List[Optional[int]] = [None] * width
    before_started = [0.0] * width
    quiet = [0.0] * width
    result: List[List[Optional[Tuple[int, float, float]]]] = []
    for sonority in sonorities:
        for voice in range(width):
            pitch = (sonority.pitches[voice]
                     if voice < len(sonority.pitches) else None)
            if pitch is None:
                quiet[voice] += sonority.duration
                if quiet[voice] >= QUIET_ENOUGH - EPSILON:
                    sounding[voice] = None
                    before[voice] = None
                continue
            quiet[voice] = 0.0
            if voice in sonority.attacks:
                before[voice] = sounding[voice]
                before_started[voice] = started[voice]
                sounding[voice] = pitch
                started[voice] = sonority.onset
        result.append([
            None if before[voice] is None
            else (before[voice], before_started[voice], started[voice])
            for voice in range(width)])
    return result


def _beat_of(score: Score, moment: float) -> Tuple[int, int]:
    """En qué compás y en qué tiempo de ese compás cae un instante."""
    bar, offset = bar_and_offset(score, moment)
    beat = score.metrics_at(max(1, bar))[1] or 1.0
    return bar, int(offset // beat + EPSILON)


def counterpoint(score: Score,
                 sonorities: Sequence[Sonority],
                 segments: Sequence[Segment] = (),
                 genre: Optional[str] = None) -> Tuple[List[Finding],
                                                       List[MotionReport]]:
    """
    Medir el contrapunto entre verticales consecutivas.

    Las paralelas y las quintas ocultas se preguntan a `engine.fitness`, que
    es donde el resto del programa las tiene definidas. Lo demás ---saltos
    de trítono, cruces, solapamientos, unísonos--- se cuenta acá, pero con
    las mismas definiciones que usa el evaluador, que están escritas en
    `MUSIC_LOGIC.md`.

    Los segmentos entran para poder distinguir dos cosas que se ven iguales
    y no lo son: unas quintas paralelas entre dos acordes son una falta de
    escritura, y las mismas quintas entre una nota de paso y la que sigue
    son un accidente de la ornamentación --- se oyen mucho menos y ningún
    tratado las prohíbe igual. Sin los segmentos no hay forma de separarlas
    y el informe se llena de faltas que no lo son.
    """
    names = [part.name for part in score.parts]
    findings: List[Finding] = []
    reports: List[MotionReport] = []
    # El estilo decide si unas paralelas son una falta. Sin estilo se juzga
    # como el barroco, que es como se enseña la escritura a cuatro voces;
    # el jazz y el gregoriano las usan a propósito, y marcarlas en rojo era
    # corregirle a la música algo que hace bien.
    profile = GENRE_PROFILES.get(genre or "classical",
                                 GENRE_PROFILES["classical"])

    def chord_tone(sonority: Sonority, voice: int) -> bool:
        pitch = sonority.pitches[voice] if voice < len(sonority.pitches) else None
        if pitch is None:
            return False
        segment = _segment_at(segments, sonority.onset) if segments else None
        if segment is None or segment.reading is None:
            return True
        return segment.reading.contains(pitch)

    def structural(before: Sonority, after: Sonority, *voices: int) -> bool:
        """¿El paso ocurre entre notas reales del acorde, en las dos voces?"""
        return all(chord_tone(before, v) and chord_tone(after, v) for v in voices)

    previous = _previous_notes(sonorities)
    #: El último paso anotado para cada par de voces. Una voz que vuelve a
    #: atacar no cambia nada de lo que hay para medir, y sin esto el mismo
    #: paralelo aparecía una vez por cada corchea de la voz de arriba.
    registered: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}

    def in_chord(pitch: int, moment: float) -> bool:
        """¿Esa altura es del acorde que gobierna ese instante?"""
        segment = _segment_at(segments, moment) if segments else None
        if segment is None or segment.reading is None:
            return True
        return segment.reading.contains(pitch)

    for index, sonority in enumerate(sonorities):
        pitches = sonority.pitches
        # -- cruce de voces, dentro de una misma vertical -------------------
        for voice in range(len(pitches) - 1):
            low, high = pitches[voice], pitches[voice + 1]
            if low is None or high is None:
                continue
            if low > high:
                findings.append(Finding(
                    kind="cruce", label="Cruce de voces",
                    detail=(trf("{voice_name} canta por encima de "
                                "{voice_name2}",
                                voice_name=_voice_name(names, voice),
                                voice_name2=_voice_name(names, voice + 1))),
                    severity="grave", index=index,
                    bar_index=sonority.bar_index, offset=sonority.offset,
                    voices=(voice, voice + 1)))
            elif low == high:
                findings.append(Finding(
                    kind="unisono", label="Unísono entre voces vecinas",
                    detail=(trf("{voice_name} y {voice_name2} caen en la "
                                "misma nota: la textura pierde una voz",
                                voice_name=_voice_name(names, voice),
                                voice_name2=_voice_name(names, voice + 1))),
                    severity="nota", index=index,
                    bar_index=sonority.bar_index, offset=sonority.offset,
                    voices=(voice, voice + 1)))

        if index + 1 >= len(sonorities):
            continue
        following = sonorities[index + 1]
        report = MotionReport(index=index, bar_index=sonority.bar_index,
                              offset=sonority.offset)

        voices = range(len(pitches))
        for a in voices:
            if not _both_sound(sonority, following, a):
                continue
            move = following.pitches[a] - sonority.pitches[a]
            # -- salto de trítono, voz por voz ------------------------------
            if abs(move) == TRITONE:
                findings.append(Finding(
                    kind="salto_tritono", label="Salto de trítono",
                    detail=(trf("{voice_name} salta un trítono: es el "
                                "salto más difícil de cantar y la "
                                "escritura vocal lo evita",
                                voice_name=_voice_name(names, a))),
                    severity="aviso", index=index,
                    bar_index=sonority.bar_index, offset=sonority.offset,
                    voices=(a,)))
            for b in voices:
                if b <= a or not _both_sound(sonority, following, b):
                    continue
                # -- solapamiento -----------------------------------------
                if b == a + 1:
                    if following.pitches[a] > sonority.pitches[b]:
                        findings.append(Finding(
                            kind="solapamiento", label="Solapamiento",
                            detail=(trf("{voice_name} sube por encima de "
                                        "donde estaba {voice_name2}",
                                        voice_name=_voice_name(names, a),
                                        voice_name2=_voice_name(names, b))),
                            severity="aviso", index=index,
                            bar_index=sonority.bar_index,
                            offset=sonority.offset, voices=(a, b)))
                    elif following.pitches[b] < sonority.pitches[a]:
                        findings.append(Finding(
                            kind="solapamiento", label="Solapamiento",
                            detail=(trf("{voice_name} baja por debajo de "
                                        "donde estaba {voice_name2}",
                                        voice_name=_voice_name(names, b),
                                        voice_name2=_voice_name(names, a))),
                            severity="aviso", index=index,
                            bar_index=sonority.bar_index,
                            offset=sonority.offset, voices=(a, b)))
        # -- movimientos y paralelas, par por par --------------------------
        # Se miden aparte del resto, y contra la nota que cada voz **acaba
        # de dejar** en vez de contra la vertical de al lado. Las dos cosas
        # son la misma en un coral, donde las cuatro voces atacan juntas; en
        # una textura arpegiada no se parecen en nada: ahí las voces entran
        # por turno, así que la vertical vecina dice que la que todavía no
        # atacó está quieta --- y dos voces que bajan una tras otra, que en
        # el papel se ven bajando juntas, salían cifradas "oblicuo" y sus
        # quintas paralelas no las veía nadie.
        was = previous[index + 1]
        for a in range(len(following.pitches)):
            for b in range(a + 1, len(following.pitches)):
                if a not in following.attacks and b not in following.attacks:
                    continue
                now_a = following.pitches[a]
                now_b = following.pitches[b]
                if now_a is None or now_b is None:
                    continue
                left, right = was[a], was[b]
                # Una voz que **acaba de entrar** desde el silencio no viene
                # de ninguna nota y no hay movimiento que medirle. Una que
                # viene sonando desde el principio de la pieza tampoco tiene
                # nota anterior, pero ésa no está entrando: está sosteniendo,
                # y sostener mientras la otra se mueve es movimiento
                # oblicuo. La diferencia entre las dos es si ataca acá.
                if left is None and a in following.attacks:
                    continue
                if right is None and b in following.attacks:
                    continue
                was_a, from_a, since_a = (left if left is not None
                                          else (now_a, -SINCE_FOREVER,
                                                -SINCE_FOREVER))
                was_b, from_b, since_b = (right if right is not None
                                          else (now_b, -SINCE_FOREVER,
                                                -SINCE_FOREVER))
                # Las dos notas de partida tienen que haber sonado juntas
                # en algún momento: si no, no hubo intervalo entre ellas y
                # no hay nada que pueda conservarse ni invertirse. Cuando no
                # coincidieron es porque una viene sosteniendo desde mucho
                # antes ---una pedal, una redonda debajo de un arpegio--- y
                # lo que hace mientras la otra se mueve es quedarse quieta:
                # eso es un movimiento oblicuo y no un paso entre dos notas
                # que nunca sonaron una contra otra.
                if max(from_a, from_b) >= min(since_a, since_b) - EPSILON:
                    if since_a <= from_b + EPSILON:
                        was_a = now_a
                    if since_b <= from_a + EPSILON:
                        was_b = now_b
                    if was_a != now_a and was_b != now_b:
                        continue
                # Dos voces que se mueven en tiempos distintos no se mueven
                # juntas: la que se movió antes ya está quieta cuando se
                # mueve la otra, y cada paso es un movimiento oblicuo. Mi-si,
                # mi-la, re-la no son quintas paralelas: en el medio suena una
                # cuarta. Dentro de un mismo tiempo sí cuentan juntas, que es
                # como se escribe un arpegio: el bajo y el alto del preludio de
                # Bach se mueven con una semicorchea de diferencia y lo que se
                # oye es el acorde entero cambiando.
                if (was_a != now_a and was_b != now_b
                        and since_a != since_b
                        and _beat_of(score, since_a) != _beat_of(score, since_b)):
                    if since_a < since_b:
                        was_a = now_a
                    else:
                        was_b = now_b
                step = (was_a, now_a, was_b, now_b)
                if registered.get((a, b)) == step:
                    continue
                registered[(a, b)] = step
                report.pairs[(a, b)] = motion_between(*step)
                report.ways[(a, b)] = (_way(now_a - was_a), _way(now_b - was_b))

                fifth, octave = parallel_interval_violation(
                    [was_a, was_b], [now_a, now_b], 0, 1)
                if not (fifth or octave):
                    continue
                # Contra el momento en que **empezó** cada nota de partida y
                # no contra el final del tramo: el corte entre dos segmentos
                # se lleva por delante lo que pasa un pelo antes de la
                # barra, y la nota de partida quedaba preguntándole al
                # acorde siguiente si le pertenece.
                real = (in_chord(was_a, from_a)
                        and in_chord(was_b, from_b)
                        and in_chord(now_a, following.onset)
                        and in_chord(now_b, following.onset))
                allowed = not (profile.forbid_parallel_fifths if fifth
                               else profile.forbid_parallel_octaves)
                # Cada pedazo se traduce solo y recién después se pegan: la
                # frase armada no está en ningún catálogo.
                detail = (trf("{voice_name} y {voice_name2} se mueven en "
                              "la misma dirección conservando ",
                              voice_name=_voice_name(names, a),
                              voice_name2=_voice_name(names, b))
                          + tr("la quinta justa" if fifth else "la octava"))
                if not real:
                    detail += tr(", pero entre notas de adorno y no entre "
                                 "acordes")
                elif allowed:
                    detail += tr(", algo que este estilo permite")
                findings.append(Finding(
                    kind="quintas_paralelas" if fifth else "octavas_paralelas",
                    label=("Quintas paralelas" if fifth
                           else "Octavas paralelas"),
                    detail=detail,
                    severity="grave" if real and not allowed else "nota",
                    index=index + 1,
                    bar_index=following.bar_index, offset=following.offset,
                    voices=(a, b)))
        reports.append(report)

        # -- quintas y octavas ocultas, entre voces extremas ----------------
        sounding = [v for v in voices if _both_sound(sonority, following, v)]
        if len(sounding) >= 2:
            low, high = sounding[0], sounding[-1]
            pair_before = [sonority.pitches[low], sonority.pitches[high]]
            pair_after = [following.pitches[low], following.pitches[high]]
            if direct_perfect_violation(pair_before, pair_after, 0, 1):
                interval = (pair_after[1] - pair_after[0]) % OCTAVE
                findings.append(Finding(
                    kind="quintas_ocultas",
                    label=("Octava oculta" if interval == 0
                           else "Quinta oculta"),
                    detail=("las voces extremas llegan por movimiento directo "
                            "a una consonancia perfecta, y la superior llega "
                            "por salto"),
                    severity="aviso", index=index,
                    bar_index=sonority.bar_index, offset=sonority.offset,
                    voices=(low, high)))

    findings.sort(key=lambda f: (f.index, SEVERITY_ORDER.get(f.severity, 3)))
    return _collapse(findings), reports


#: Hallazgos que describen **una vertical** y no un paso entre dos. Son los
#: únicos que hay que deduplicar: una nota tenida se parte en tantas
#: verticales como notas se muevan encima, y un cruce de voces que dura una
#: blanca aparecía cuatro veces seguidas diciendo lo mismo.
#:
#: Los otros no se tocan. Cinco quintas paralelas seguidas son cinco faltas
#: distintas entre cinco pares de acordes distintos, y juntarlas en una sola
#: escondía cuatro.
PER_SONORITY_KINDS = ("cruce", "unisono")


def _collapse(findings: Sequence[Finding]) -> List[Finding]:
    """Juntar el mismo hallazgo de vertical repetido en verticales seguidas."""
    kept: List[Finding] = []
    seen: Dict[Tuple[str, Tuple[int, ...]], int] = {}
    for finding in findings:
        if finding.kind not in PER_SONORITY_KINDS:
            kept.append(finding)
            continue
        signature = (finding.kind, finding.voices)
        previous = seen.get(signature)
        seen[signature] = finding.index
        if previous is not None and finding.index - previous <= 1:
            continue
        kept.append(finding)
    return kept


# ---------------------------------------------------------------------------
# Cifrado barroco
# ---------------------------------------------------------------------------

#: Las abreviaturas del bajo continuo. El bajo cifrado escribe los
#: intervalos que suenan sobre el bajo, pero cuatro siglos de práctica
#: abreviaron los casos frecuentes: una tríada en estado fundamental no
#: lleva número --- se da por sabida --- y la primera inversión lleva un 6
#: solo, porque la tercera también se da por sabida.
SHARP_SIGN = "\u266f"
FLAT_SIGN = "\u266d"
#: El becuadro. Una nota natural en una armadura con bemoles está
#: subida respecto de la armadura, pero no se cifra con sostenido: el
#: continuista lee el signo que va a escribir, y ahí lo que va es un
#: becuadro.
NATURAL_SIGN = "\u266e"

FIGURE_ABBREVIATIONS = {
    (3, 5): "",             # estado fundamental: sin cifra
    (3, 6): "6",
    (4, 6): "6/4",
    (3, 5, 7): "7",
    (3, 5, 6): "6/5",
    (3, 4, 6): "4/3",
    (2, 4, 6): "4/2",
    (4, 5): "5/4",          # cuarta suspendida
    (2, 5): "5/2",
    # La tercera y la quinta solas no llevan cifra: el estado fundamental
    # se toca sin que nadie lo escriba, y "3" a secas quiere decir otra cosa
    # --- que hay que tocar la tercera y **sólo** la tercera.
    (3,): "", (5,): "", (6,): "6", (4,): "4", (7,): "7",
    (3, 4): "4/3",
    (5, 6): "6/5",
}


def baroque_figure(reading: Optional[ChordReading],
                   pitches: Sequence[Optional[int]],
                   key: KeyReading,
                   heard: Optional[Sequence[int]] = None,
                   extras: Sequence[int] = ()) -> str:
    """
    El cifrado del bajo continuo para un acorde.

    Se cifra **el acorde** y no una vertical suelta. En un coral las dos
    cosas dan lo mismo, porque cada vertical es el acorde entero; en una
    textura arpegiada no: un compás de Do con la séptima que llega en la
    última corchea es un acorde de séptima todo el compás, y cifrar la
    primera vertical devolvería la cifra de una tríada que nadie escribió.

    De los tamaños de intervalo sale el número, y de la práctica sale la
    abreviatura: sin cifra el estado fundamental, 6 la primera inversión,
    6/4 la segunda, y 7 - 6/5 - 4/3 - 4/2 las cuatro del acorde de séptima.
    Lo alterado respecto de la armadura lleva su accidente pegado al número,
    que es de lo que el cifrado avisa: un continuista lee un bajo y necesita
    saber qué subir, no cómo se llama el acorde.
    """
    sounding = [p for p in pitches if p is not None]
    # El cifrado del bajo continuo es la distancia de lo que suena **al
    # bajo**, así que con una sola nota no hay nada que cifrar: un 6 suelto
    # encima de una nota sola es una cifra que no existe. Pero la cuenta se
    # hace sobre **el tramo** y no sobre la vertical que se dibuja: en una
    # textura arpegiada el acorde entra de a una nota por vez, y midiendo la
    # primera vertical media pieza se quedaba sin cifrar.
    ringing = set(heard) if heard is not None else {p % 12 for p in sounding}
    if not sounding or len(ringing) < 2:
        return ""
    if reading is None:
        return _figure_from_pitches(sounding, key)
    bass_size = next((size for pc, _role, size in reading.tones
                      if pc == reading.bass_pc), None)
    if bass_size is None:
        # El bajo no es del acorde --- una nota pedal, un bajo de paso ---
        # así que la cifra no se puede leer de la inversión y hay que
        # medirla contra lo que suena.
        return _figure_from_pitches(sounding, key)

    scale = set(signature_scale(key.fifths))
    sizes = {}
    #: Los tamaños que se cifran aunque esa nota no llegue a sonar.
    assumed = set()
    for pc, role, size in reading.tones:
        if pc == reading.bass_pc:
            continue
        if role in (_FIFTH, _SEVENTH) and pc not in ringing:
            # Una quinta que no suena no se cifra. La tercera sí, aunque
            # falte: es lo que el continuista tiene que tocar igual.
            continue
        above = ((size - bass_size) % 7) + 1
        sizes[above] = _alteration(reading.root_name[0], size, pc, key.fifths)
        if pc not in ringing:
            assumed.add(above)

    # Y lo que suena sin ser del acorde. Cuando hay algo así, lo que no suena
    # se cae de la cifra: una cuarta suspendida sobre una tríada se escribe
    # "5/4" y no "5/4/3", porque la tercera todavía no llegó --- ése es el
    # sentido de la suspensión, y anotarla igual sería cifrar el acorde de
    # después.
    if extras:
        for size in assumed:
            sizes.pop(size, None)
        bass_step = (LETTER_STEPS.get(reading.root_name[0], 0)
                     + bass_size - 1) % 7
        bass_letter = "CDEFGAB"[bass_step]
        bass_pitch = min(sounding)
        for pitch in sorted(sounding):
            if pitch % 12 not in extras:
                continue
            above = ((generic_interval(bass_pitch, pitch) - 1) % 7) + 1
            if above == 1:
                continue                # la octava del bajo no se cifra
            sizes[above] = _alteration(bass_letter, above, pitch % 12,
                                       key.fifths)
    if len(sizes) > 3:
        # Nadie escribe una cifra de cuatro números, así que sobra alguno.
        # Se van primero los que se dan por sabidos ---la tercera y la
        # quinta, que el continuista toca igual--- y sólo si aún así no
        # entra, el más chico de los que quedan. Descartando siempre el más
        # chico, un 4/2 con la tercera sonando encima perdía el 2, que es
        # justamente el número que dice qué acorde es.
        for size in (3, 5):
            if len(sizes) <= 3:
                break
            sizes.pop(size, None)
        for size in sorted(sizes)[:max(0, len(sizes) - 3)]:
            sizes.pop(size, None)
    return _abbreviate(sizes)


#: En qué orden se escriben las alteraciones de una armadura. Repetido acá
#: --- también está en el pentagrama --- porque el motor no puede importar
#: nada de la interfaz.
SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")


def _signature_alteration(letter: str, fifths: int) -> int:
    """Cuánto altera la armadura a una letra: +1, -1 o nada."""
    if fifths > 0 and letter in SHARP_ORDER[:min(7, fifths)]:
        return 1
    if fifths < 0 and letter in FLAT_ORDER[:min(7, -fifths)]:
        return -1
    return 0


def _sign(written: int) -> str:
    """El signo que se dibuja al lado del número."""
    if written > 0:
        return SHARP_SIGN
    if written < 0:
        return FLAT_SIGN
    return NATURAL_SIGN


def _alteration(root_letter: str, size: int, pc: int,
                fifths: int) -> Optional[int]:
    """
    Qué accidente lleva escrito una nota del acorde, o nada si no lleva.

    Se devuelve la alteración **escrita** ---la que el continuista va a
    dibujar--- y no la diferencia con la armadura: en una armadura de
    bemoles, una nota natural está subida respecto de la armadura y se
    cifra igual con becuadro, no con sostenido.

    Se resuelve por la **letra** y no por vecindad con la escala. Un la
    bemol y un sol sostenido suenan igual y no se cifran igual, y preguntar
    "¿hay una nota de la escala un semitono más abajo?" contesta que sí para
    los dos: el la bemol tiene al sol y el sol sostenido tiene al sol. La
    letra desempata, y la letra la da el intervalo escrito --- la tercera de
    un acorde de fa se escribe con la, sea la o la bemol.
    """
    step = LETTER_STEPS.get(root_letter, 0)
    letter = "CDEFGAB"[(step + size - 1) % 7]
    natural = LETTER_SEMITONES[letter]
    written = (pc - natural + 6) % 12 - 6
    if written == _signature_alteration(letter, fifths):
        return None                     # la armadura ya lo dice
    return written


def _figure_from_pitches(sounding: Sequence[int], key: KeyReading) -> str:
    """La cifra medida sobre lo que suena, cuando no hay acorde que leer."""
    if len(sounding) < 2:
        return ""
    bass = min(sounding)
    scale = set(signature_scale(key.fifths))
    sizes = {}
    for pitch in sounding:
        if pitch == bass:
            continue
        size = ((generic_interval(bass, pitch) - 1) % 7) + 1
        if size == 1:
            continue                    # la octava no se cifra
        alteration = None
        if pitch % 12 not in scale:
            alteration = 1 if (pitch % 12 - 1) % 12 in scale else -1
        if alteration is not None or size not in sizes:
            sizes[size] = alteration
    return _abbreviate(sizes)


def _abbreviate(sizes: Dict[int, Optional[int]]) -> str:
    """
    Pasar los tamaños a la cifra que se escribe, con sus accidentes.

    La tercera y la quinta **se dan por sabidas**: un acorde de séptima al
    que le falta la quinta se cifra "7" y no "7/3", porque el continuista
    toca la tercera de todos modos. Por eso, cuando la combinación exacta no
    figura en la tabla, se vuelve a probar sin ellas antes de ponerse a
    apilar números --- que es lo que devolvía cifras que nadie escribe.
    """
    if not sizes:
        return ""
    text = FIGURE_ABBREVIATIONS.get(tuple(sorted(sizes)))
    if text is None:
        assumed = tuple(sorted(size for size in sizes if size not in (3, 5)))
        text = FIGURE_ABBREVIATIONS.get(assumed)
    if text is None:
        text = "/".join(str(size) for size in sorted(sizes, reverse=True))
    marks = {size: _sign(value)
             for size, value in sizes.items() if value is not None}
    if not marks:
        return text
    if text == "" and 3 in marks:
        # Una tercera alterada sobre un bajo sin cifra se escribe con el
        # accidente solo. Es la marca de la sensible en el bajo continuo.
        return marks[3]
    parts = []
    for chunk in (text.split("/") if text else []):
        parts.append(marks.get(_as_size(chunk), "") + chunk)
    for size, mark in sorted(marks.items(), reverse=True):
        if str(size) not in text:
            parts.append(mark + str(size))
    return "/".join(parts)


def _as_size(chunk: str) -> int:
    try:
        return int(chunk)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Notas ajenas al acorde y adornos
# ---------------------------------------------------------------------------

@dataclass
class Ornament:
    """Una nota que no pertenece al acorde, con el nombre que le toca."""

    kind: str
    label: str
    voice: int
    onset: float
    bar_index: int
    offset: float
    pitch: int
    detail: str


#: Los adornos que el analizador reconoce, con su definición corta. Está acá
#: y no en la pantalla porque es parte del análisis: si una definición
#: cambia, cambia también lo que se detecta.
ORNAMENT_DEFINITIONS = {
    "paso": "Une dos notas del acorde por grados conjuntos, en la misma "
            "dirección. Cae en parte débil.",
    "paso_acentuado": "Una nota de paso que cae en parte fuerte, sonando "
                      "contra el acorde antes de resolver.",
    "bordadura": "Se aparta de una nota del acorde por grado conjunto y "
                 "vuelve a ella.",
    "doble_bordadura": "Rodea la nota del acorde por arriba y por abajo "
                       "antes de volver a ella.",
    "apoyatura": "Llega por salto a una nota ajena en parte fuerte y "
                 "resuelve por grado conjunto en dirección contraria.",
    "escapada": "Se va de la nota del acorde por grado conjunto y salta en "
                "dirección contraria.",
    "retardo": "Una nota del acorde anterior se queda sonando sobre el "
               "acorde nuevo y baja después por grado conjunto.",
    "retardo_ascendente": "Como el retardo, pero resuelve subiendo.",
    "anticipacion": "Llega antes de tiempo a una nota del acorde siguiente.",
    "cambiata": "Baja por grado conjunto, salta una tercera hacia abajo y "
                "vuelve a subir por grado conjunto.",
    "grupeto": "Rodea la nota principal por arriba y por abajo y termina en "
               "ella: cuatro o cinco notas rápidas.",
    "mordente": "Un golpe rapidísimo a la nota vecina y vuelta inmediata.",
    "pedal": "Una nota que se sostiene mientras la armonía cambia por "
             "encima o por debajo.",
    "anacrusa": "Una o más notas que preceden al primer tiempo fuerte de "
                "una frase.",
}

#: Las cadencias de cita se nombran con el rótulo del generador en
#: minúscula (`Cadence.kind`), y así llegan al catálogo.
SET_PIECE_KINDS = (N("cadencia frigia"), N("ciclo de vivaldi"),
                   N("bajo cromático descendente"))

ORNAMENT_LABELS = {
    "paso": N("Nota de paso"), "paso_acentuado": N("Nota de paso acentuada"),
    "bordadura": N("Bordadura"), "doble_bordadura": N("Doble bordadura"),
    "apoyatura": N("Apoyatura"), "escapada": N("Escapada"),
    "retardo": N("Retardo (suspensión)"), "retardo_ascendente": N("Retardo ascendente"),
    "anticipacion": N("Anticipación"), "cambiata": N("Nota cambiata"),
    "grupeto": N("Grupeto"), "mordente": N("Mordente"), "pedal": N("Nota pedal"),
    "anacrusa": N("Anacrusa"),
}

#: Cuánto tiene que durar una nota, en negras, para que su vecina de vuelta
#: cuente como bordadura y no como mordente. Un mordente es un golpe: por
#: encima de una semicorchea deja de oírse como tal.
MORDENT_MAX = 0.26


def _segment_at(segments: Sequence[Segment], moment: float) -> Optional[Segment]:
    for segment in segments:
        if segment.start - EPSILON <= moment < segment.end - EPSILON:
            return segment
    return segments[-1] if segments else None


def ornaments(score: Score, segments: Sequence[Segment]) -> List[Ornament]:
    """
    Encontrar y nombrar las notas que no pertenecen al acorde.

    Cada nota se compara con el acorde que gobierna su momento. La que
    pertenece se calla; la que no, se clasifica por **cómo se llega y cómo
    se sale**, que es lo único que distingue a un adorno de otro: una nota
    de paso y una bordadura pueden ser la misma altura en el mismo lugar y
    lo que las separa es que una sigue de largo y la otra vuelve.
    """
    found: List[Ornament] = []
    if not segments:
        return found

    for voice, part in enumerate(score.parts):
        notes = part.voiced()
        for position, note in enumerate(notes):
            segment = _segment_at(segments, note.onset)
            if segment is None or segment.reading is None or note.pitch is None:
                continue
            bar_index, offset = bar_and_offset(score, note.onset)
            per_bar, beat = score.metrics_at(bar_index)
            previous = notes[position - 1] if position else None
            following = notes[position + 1] if position + 1 < len(notes) else None

            if segment.reading.contains(note.pitch):
                pedal = _pedal(note, segments, voice)
                if pedal is not None:
                    found.append(Ornament(
                        kind="pedal", label=ORNAMENT_LABELS["pedal"],
                        voice=voice, onset=note.onset, bar_index=bar_index,
                        offset=offset, pitch=note.pitch, detail=pedal))
                continue

            kind, detail = _classify(note, previous, following, segment,
                                     segments, offset, per_bar, beat)
            if kind is None:
                continue
            found.append(Ornament(
                kind=kind, label=ORNAMENT_LABELS.get(kind, kind), voice=voice,
                onset=note.onset, bar_index=bar_index, offset=offset,
                pitch=note.pitch, detail=detail))

        found.extend(_turns(part, voice, score, segments))
        found.extend(_anacruses(part, voice, score))
    found.sort(key=lambda o: (o.onset, o.voice))
    return found


def _classify(note: Note, previous: Optional[Note], following: Optional[Note],
              segment: Segment, segments: Sequence[Segment], offset: float,
              per_bar: float, beat: float) -> Tuple[Optional[str], str]:
    """Qué adorno es esta nota, mirando de dónde viene y adónde va."""
    if previous is None or previous.pitch is None:
        return None, ""
    approach = note.pitch - previous.pitch
    strong = is_strong(offset, per_bar, beat)
    accented = is_accented(offset, per_bar, beat)

    if following is None or following.pitch is None:
        if approach == 0:
            return "retardo", "queda sonando del acorde anterior y no resuelve"
        return None, ""
    departure = following.pitch - note.pitch

    # Retardo: la nota se quedó del acorde anterior y baja por grado
    # conjunto. Es lo primero que se pregunta porque es lo único que se
    # reconoce por lo que pasó *antes* del acorde y no por la figura.
    if approach == 0 and strong:
        if -2 <= departure < 0:
            return "retardo", ("viene sonando del acorde anterior y baja por "
                               "grado conjunto a una nota del acorde")
        if 0 < departure <= 2:
            return "retardo_ascendente", ("viene sonando del acorde anterior "
                                          "y sube por grado conjunto")

    step_in = 1 <= abs(approach) <= 2
    step_out = 1 <= abs(departure) <= 2

    if step_in and step_out and (approach > 0) == (departure > 0):
        return (("paso_acentuado" if accented else "paso"),
                "entra y sale por grado conjunto en la misma dirección")

    if step_in and step_out and departure == -approach:
        if note.duration <= MORDENT_MAX:
            return "mordente", "golpe a la nota vecina y vuelta inmediata"
        # Los dos renglones enteros y no pegados de a pedazos: «hacia
        # arriba» y «hacia abajo» quedan en el medio de la frase, y en otro
        # idioma el medio de una frase no cae en el mismo lugar.
        return ("bordadura",
                "se aparta por grado conjunto hacia arriba y vuelve a la "
                "misma nota" if approach > 0 else
                "se aparta por grado conjunto hacia abajo y vuelve a la "
                "misma nota")

    if abs(approach) >= 3 and step_out and (approach > 0) != (departure > 0):
        if accented:
            return "apoyatura", ("llega por salto a una nota ajena en parte "
                                 "fuerte y resuelve por grado conjunto")
        return "apoyatura", "llega por salto y resuelve por grado conjunto"

    if (step_in and abs(departure) >= 3 and not accented
            and (approach > 0) != (departure > 0)):
        if abs(departure) == 3 and approach < 0:
            return "cambiata", ("baja por grado conjunto, salta una tercera "
                                "hacia abajo y vuelve subiendo")
        return "escapada", ("se va por grado conjunto y salta en dirección "
                            "contraria")

    following_segment = _segment_at(segments, following.onset)
    if (following_segment is not None and following_segment.reading is not None
            and following_segment is not segment
            and following_segment.reading.contains(note.pitch)
            and note.pitch == following.pitch):
        return "anticipacion", "llega antes de tiempo a una nota del acorde siguiente"

    return None, ""


def _pedal(note: Note, segments: Sequence[Segment], voice: int) -> Optional[str]:
    """¿Esta nota se sostiene mientras la armonía cambia debajo o encima?"""
    covered = [s for s in segments
               if s.start < note.end - EPSILON and s.end > note.onset + EPSILON]
    if len(covered) < 2:
        return None
    foreign = [s for s in covered
               if s.reading is not None and not s.reading.contains(note.pitch)]
    if not foreign:
        return None
    return (trf("se sostiene durante {covered} acordes y no pertenece a "
                "{foreign} de ellos",
                covered=len(covered), foreign=len(foreign)))


def _turns(part: Part, voice: int, score: Score,
           segments: Sequence[Segment]) -> List[Ornament]:
    """
    Los grupetos: cuatro notas que rodean a la principal y terminan en ella.

    Se busca la figura escrita ---superior, principal, inferior, principal---
    y su variante de cinco notas que empieza en la principal. Las dos tienen
    que ser rápidas: la misma sucesión en negras no es un grupeto, es una
    melodía.
    """
    found: List[Ornament] = []
    notes = part.voiced()
    for index in range(len(notes) - 3):
        window = notes[index:index + 4]
        # Las tres primeras tienen que ser rápidas; la última es la nota
        # principal a la que el giro llega, y ésa dura lo que dure. Pedirle
        # a las cuatro que fueran cortas descartaba justamente el grupeto
        # bien escrito, que es el que desemboca en una nota tenida.
        if any(n.duration > 0.5 for n in window[:3]):
            continue
        pitches = [n.pitch for n in window]
        main = pitches[1]
        if pitches[3] != main:
            continue
        upper, lower = pitches[0] - main, pitches[2] - main
        if not (1 <= upper <= 2 and -2 <= lower <= -1):
            if not (1 <= lower <= 2 and -2 <= upper <= -1):
                continue
        segment = _segment_at(segments, window[1].onset)
        if segment is None or segment.reading is None:
            continue
        if not segment.reading.contains(main):
            continue
        bar_index, offset = bar_and_offset(score, window[0].onset)
        found.append(Ornament(
            kind="grupeto", label=ORNAMENT_LABELS["grupeto"], voice=voice,
            onset=window[0].onset, bar_index=bar_index, offset=offset,
            pitch=main,
            detail="rodea la nota del acorde por arriba y por abajo y "
                   "vuelve a ella"))
    return found


def _anacruses(part: Part, voice: int, score: Score) -> List[Ornament]:
    """
    Las anacrusas: lo que suena antes del primer tiempo fuerte de una frase.

    Dos casos, y son el mismo hecho visto en dos escalas. El compás inicial
    incompleto es la anacrusa de la pieza. Y dentro de la pieza, una voz que
    vuelve a entrar sobre el final de un compás y sigue en el tiempo fuerte
    del siguiente está entrando en anacrusa: el silencio de antes es lo que
    marca dónde empieza la frase.
    """
    found: List[Ornament] = []
    notes = part.voiced()
    if not notes:
        return found

    if score.pickup_quarters > EPSILON:
        for note in notes:
            if note.onset >= score.pickup_quarters - EPSILON:
                break
            bar_index, offset = bar_and_offset(score, note.onset)
            found.append(Ornament(
                kind="anacrusa", label=ORNAMENT_LABELS["anacrusa"], voice=voice,
                onset=note.onset, bar_index=bar_index, offset=offset,
                pitch=note.pitch,
                detail="está antes del primer compás completo: es la "
                       "anacrusa de la pieza"))

    for index, note in enumerate(notes[:-1]):
        following = notes[index + 1]
        this_bar, offset = bar_and_offset(score, note.onset)
        per_bar, beat = score.metrics_at(this_bar)
        _next_bar, next_offset = bar_and_offset(score, following.onset)
        silent_before = (index == 0
                         or notes[index - 1].end < note.onset - EPSILON)
        leads_in = (abs(following.onset - note.end) <= EPSILON
                    and abs(next_offset) <= EPSILON
                    and offset > per_bar - beat - EPSILON)
        if silent_before and leads_in and note.onset > EPSILON:
            bar_index, _o = bar_and_offset(score, note.onset)
            found.append(Ornament(
                kind="anacrusa", label=ORNAMENT_LABELS["anacrusa"], voice=voice,
                onset=note.onset, bar_index=bar_index, offset=offset,
                pitch=note.pitch,
                detail="la voz vuelve a entrar sobre el final del compás y "
                       "sigue en el tiempo fuerte: entra en anacrusa"))
    return found


# ---------------------------------------------------------------------------
# El análisis completo
# ---------------------------------------------------------------------------

@dataclass
class Analysis:
    """Todo lo que se pudo decir de una partitura."""

    score: Score
    key: KeyReading
    sonorities: List[Sonority] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    cadences: List[Cadence] = field(default_factory=list)
    groups: List[ForeignGroup] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    motions: List[MotionReport] = field(default_factory=list)
    ornaments: List[Ornament] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # -- lecturas cómodas para la pantalla ---------------------------------

    def findings_at(self, index: int) -> List[Finding]:
        return [f for f in self.findings if f.index == index]

    def ornaments_in(self, segment: Segment) -> List[Ornament]:
        return [o for o in self.ornaments
                if segment.start - EPSILON <= o.onset < segment.end - EPSILON]

    def motion_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for report in self.motions:
            for kind in report.pairs.values():
                summary[kind] = summary.get(kind, 0) + 1
        return summary

    def counts(self) -> Dict[str, int]:
        totals: Dict[str, int] = {}
        for finding in self.findings:
            totals[finding.kind] = totals.get(finding.kind, 0) + 1
        return totals

    def playback(self) -> List[Tuple[int, float, float]]:
        """
        Las notas de la pieza para escucharla: altura, comienzo y largo.

        Voz por voz y no vertical por vertical. Una redonda del bajo debajo
        de cuatro negras de la soprano son cinco verticales, y tocarlas como
        cinco acordes vuelve a atacar el bajo en cada una: se oye un
        martilleo en vez de una nota tenida. Con las notas de verdad, cada
        voz suena una vez y dura lo que dura.
        """
        events: List[Tuple[int, float, float]] = []
        for part in self.score.parts:
            for note in part.notes:
                if note.pitch is None or note.duration <= 0:
                    continue
                events.append((note.pitch, note.onset, note.duration))
        events.sort(key=lambda event: (event[1], event[0]))
        return events


def analyse(score: Score, genre: Optional[str] = None) -> Analysis:
    """
    Analizar una partitura de punta a punta.

    `genre` es el estilo contra el que se juzga el contrapunto (una clave de
    `GENRE_PROFILES`). Sin él, el barroco.

    El orden importa y no es negociable: primero las verticales, después los
    acordes ---que no necesitan la tonalidad para leerse---, después la
    tonalidad ---que sí necesita los acordes--- y recién entonces la función
    de cada uno, que necesita las dos cosas.
    """
    ordered = score.in_register_order()
    sonorities = verticalise(ordered)
    warnings: List[str] = []
    if not sonorities:
        return Analysis(score=ordered,
                        key=KeyReading(0, "major", ordered.fifths),
                        warnings=["La partitura no tiene notas que analizar."])

    segments = harmonic_segments(ordered, sonorities)
    key = detect_key(ordered, sonorities, segments)
    _root_diminished_sevenths(segments)

    for index, segment in enumerate(segments):
        following = segments[index + 1] if index + 1 < len(segments) else None
        label_segment(segment, key, following)
        segment.figure = baroque_figure(segment.reading, segment.pitches,
                                        key, segment.sounding_pcs,
                                        segment.figured_extras)

    cadences = relate(segments, key)
    groups = foreign_groups(segments, key)
    findings, motions = counterpoint(ordered, sonorities, segments, genre)
    decorations = ornaments(ordered, segments)

    if key.confidence < 0.35:
        warnings.append(
            trf("La tonalidad no está clara: {label} es la lectura más "
                "probable, pero hay otras cerca.",
                label=key.label))

    return Analysis(score=ordered, key=key, sonorities=sonorities,
                    segments=segments, cadences=cadences, groups=groups,
                    findings=findings, motions=motions, ornaments=decorations,
                    warnings=warnings)
