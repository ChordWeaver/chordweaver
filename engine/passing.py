# -*- coding: utf-8 -*-
"""
Passing tones: the notes that fill the gap between two chord tones.

A passing tone is not part of either chord. It sits between them, on a weaker
beat, and its whole job is to turn a leap into stepwise motion: a voice going
C-E jumps a third, but C-D-E walks. That is why they are worth having even
though every one of them is, strictly speaking, a dissonance.

Model used here
---------------
A passing tone belongs to a *transition*: it sounds during the tail of the
chord it leaves, and resolves into the chord it arrives at. Only voices the
user enabled may take one, and only where there is actually a gap to fill --
inserting a "passing" note into a voice that holds still or moves by a step
produces a wandering line, not a passing tone.

The search decides where they go, so they are scored, not sprinkled on
afterwards: a passing tone that leaves both halves of the motion stepwise
earns its place, one that creates a new leap does not.
"""

from __future__ import annotations

import functools
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from engine.i18n import tr, trf, trs

#: Widest step either leg of the ornament may take. A passing note does not
#: have to sit *between* the two chord tones: rising a tone and falling two
#: before settling is ordinary melodic motion, and restricting the note to
#: the space between the endpoints ruled out most of what singers actually
#: do. What matters is that both legs stay singable.
MAX_LEG = 4

#: Tope duro de adornos por pieza, pase lo que pase con la barra. Se cuentan
#: **transiciones adornadas**, no notas: una figura de tres notas es un
#: adorno, no tres.
#:
#: `crowding` desalienta, no impide: es un costo que la búsqueda puede
#: comprar, y con la frecuencia arriba la compraba --- salían piezas que
#: eran un ejercicio de escalas y no una progresión adornada. El tope se
#: aplica en `ga._prune_stale_passing`, que es lo único que ve el cromosoma
#: entero.
#:
#: Era 5. Sobre dieciséis compases eso es un adorno cada tres compases con
#: la barra al máximo, que no se escucha como una pieza adornada sino como
#: una pieza sin adornar a la que se le escaparon cuatro notas.
HARD_MAX_PASSING = 12


def max_for_density(density: float) -> int:
    """
    Cuántos adornos admite la pieza según la barra de frecuencia.

    La barra decidía sólo el sorteo de la siembra y la mutación, y después
    el evaluador cobraba `crowding` a partir del cuarto **con la barra donde
    estuviera**: el tope era el mismo con la barra abajo que arriba, así que
    moverla no cambiaba lo que se escuchaba. Ahora es la barra la que fija
    el tope, entre uno y `HARD_MAX_PASSING`.
    """
    return max(1, min(HARD_MAX_PASSING, int(round(1 + 11 * density))))


#: Cuantas notas puede tener una figura como maximo.
#:
#: Tres. Con una sola nota el repertorio entero era "una negra entre dos
#: acordes" --- la nota de paso de manual y nada mas: sin relleno de una
#: cuarta, sin bordadura doble y sin grupeto, o sea sin ninguna de las
#: figuras que un cantante hace sin pensarlas. Con cuatro o mas la cola del
#: acorde se pica en notas mas cortas que la subdivision que la pieza tiene
#: declarada, y eso ya no es adornar: es cambiar de compas sin avisar.
MAX_FIGURE = 3

#: Que se considera un paso: el tono y el semitono, nada mas. Es la medida
#: con la que se decide si una figura camina o salta.
STEP = 2

#: Cuantos saltos se le perdonan a una figura. Uno: cero deja afuera el
#: escape ---salir por un salto y bajar caminando, que es de lo mas comun
#: que hay--- y dos ya no es una figura, es la voz haciendo otra cosa.
MAX_LEAPS = 1

#: Cuantas figuras distintas se ofrecen como mucho para una transicion.
MAX_CANDIDATES = 48

#: Con que peso se sortea cada largo, y cuanto lo corre la barra de
#: frecuencia. Con la barra abajo casi todo es una nota suelta; arriba, las
#: figuras de dos y tres pesan tanto como ella.
FIGURE_WEIGHTS = ((1.00, 0.00), (0.22, 0.85), (0.06, 0.55))

def figure(entry):
    """
    Una entrada de la grilla, siempre como tupla de alturas.

    Se aceptan las tres formas ---nada, un entero, una tupla--- y no solo la
    nueva, porque el entero suelto sigue llegando de afuera: esta escrito asi
    en los historiales que el programa ya guardo, y una figura de una nota
    **es** un entero para cualquiera que la mire de lejos.
    """
    if entry is None:
        return ()
    if isinstance(entry, (list, tuple)):
        return tuple(int(pitch) for pitch in entry)
    return (int(entry),)


def _ladder(low, high, scale_pcs, diatonic_only):
    """Las alturas por las que la figura puede caminar, en orden."""
    if not diatonic_only or not scale_pcs:
        return tuple(range(low, high + 1))
    allowed = {pc % 12 for pc in scale_pcs}
    return tuple(p for p in range(low, high + 1) if p % 12 in allowed)


@functools.lru_cache(maxsize=8192)
def _figures(from_pitch, to_pitch, scale_key, diatonic_only, max_leg,
             max_notes):
    """
    Todas las figuras razonables entre dos alturas, cacheadas.

    Se arma como un camino: se sale de ``from_pitch``, se pisan entre una y
    ``max_notes`` alturas de la escalera, y se llega a ``to_pitch``. Un camino
    vale si **cada tramo entra en la mano** ---nada mas ancho que
    ``max_leg``--- y si a lo sumo uno de esos tramos es un salto. Con esas dos
    reglas salen solas todas las figuras del oficio y ninguna que no lo sea:

    * el **relleno**, el camino escalonado entre las dos --- una nota llena
      una tercera, dos llenan una cuarta, tres una quinta;
    * la **bordadura**, irse a la de al lado y volver, que es lo unico que se
      puede hacer cuando la voz no se mueve;
    * la **bordadura doble**, arriba y abajo antes de seguir;
    * el **grupeto**, la bordadura doble pasando por la nota de salida --- la
      unica figura donde repetir una altura no es un error sino la figura;
    * y el **escape**, salir por un salto y entrar caminando, o al reves.

    Enumerar en vez de escribir las cinco a mano es lo que hace que aparezcan
    tambien las que no tienen nombre. Y esta cacheado porque la busqueda
    pregunta lo mismo miles de veces: los acordes se repiten, las voces caen
    en las mismas alturas y la escala no cambia en toda la pieza.
    """
    span = max_leg + 1
    ladder = _ladder(min(from_pitch, to_pitch) - span,
                     max(from_pitch, to_pitch) + span,
                     scale_key, diatonic_only)
    if not ladder:
        return ()

    out = []
    seen = set()

    def walk(path, at, leaps):
        if len(out) >= MAX_CANDIDATES:
            return
        if path:
            final = abs(to_pitch - at)
            if final and final <= max_leg and leaps + (final > STEP) <= MAX_LEAPS:
                shape = tuple(path)
                if shape not in seen:
                    seen.add(shape)
                    out.append(shape)
        if len(path) >= max_notes:
            return
        for pitch in ladder:
            gap = abs(pitch - at)
            if not gap or gap > max_leg:
                continue          # quedarse quieto no es adornar
            # Repetir una altura que la figura ya piso solo se admite si es
            # la de salida y queda lugar para cerrarla: eso es un grupeto, y
            # cualquier otra repeticion es la misma nota tocada dos veces.
            if pitch in path or (pitch == from_pitch
                                 and len(path) + 2 > max_notes):
                continue
            cost = leaps + (gap > STEP)
            if cost > MAX_LEAPS:
                continue
            path.append(pitch)
            walk(path, pitch, cost)
            path.pop()

    walk([], from_pitch, 0)
    return tuple(out)


def figure_candidates(from_pitch, to_pitch, scale_pcs, diatonic_only=True,
                      max_leg=MAX_LEG, max_notes=MAX_FIGURE):
    """Las figuras posibles para esta transicion. Ver `_figures`."""
    return _figures(int(from_pitch), int(to_pitch),
                    tuple(sorted({int(pc) % 12 for pc in scale_pcs})),
                    bool(diatonic_only), int(max_leg),
                    max(1, min(MAX_FIGURE, int(max_notes))))


def pick_figure(candidates, rng, density=0.45, length=0):
    """
    Sortear una figura: primero el largo, despues cual.

    El largo va primero a proposito. Sorteando parejo entre todas salian casi
    siempre las de tres notas ---hay muchas mas combinaciones de tres que de
    una--- y una pieza en la que cada adorno es una corrida no suena
    adornada, suena nerviosa. Con el largo aparte manda la barra de
    frecuencia y no la combinatoria.

    ``length`` fuerza un largo, que es lo que hace falta cuando otra voz ya
    adorno esta transicion: las dos figuras tienen que durar lo mismo o no
    hay forma de repartir la cola del acorde entre las dos.
    """
    if not candidates:
        return ()
    buckets = {}
    for shape in candidates:
        buckets.setdefault(len(shape), []).append(shape)
    if length:
        pool = buckets.get(length)
        return tuple(rng.choice(pool)) if pool else ()
    sizes = sorted(buckets)
    weights = []
    for size in sizes:
        base, slope = FIGURE_WEIGHTS[min(size, len(FIGURE_WEIGHTS)) - 1]
        weights.append(max(1e-6, base + slope * density))
    roll = rng.random() * sum(weights)
    for size, weight in zip(sizes, weights):
        roll -= weight
        if roll <= 0.0:
            return rng.choice(buckets[size])
    return rng.choice(buckets[sizes[-1]])


@dataclass
class PassingRules:
    """When passing tones may appear and what they are worth."""

    #: Indices of the voices allowed to take a passing tone. Empty disables
    #: the feature entirely.
    voices: Tuple[int, ...] = ()
    #: Reward for an ornament whose two legs are both steps. Subido de 18:
    #: dentro del tope, un adorno correcto tiene que ganarle con holgura a
    #: dejar la transición pelada, o la búsqueda se queda por debajo del
    #: tope y la barra vuelve a no notarse.
    reward: float = -24.0
    #: Cost for one that leaps on either leg.
    clumsy: float = 25.0
    #: Cost when the ornament repeats a pitch the voice already has, which
    #: reads as the same note struck twice rather than as movement.
    repeated_note: float = 40.0
    #: Chance that any given transition gets an ornament. This is what makes
    #: them appear at all: left to mutation they were vanishingly rare,
    #: because good voice leading is already stepwise and rarely leaves a gap.
    density: float = 0.45
    #: Widest step either leg may take.
    max_leg: int = MAX_LEG
    #: How much of the departing chord's duration the ornament takes. Several
    #: values are offered so the ornaments are not all the same length: a bar
    #: of identical quarter-note decorations sounds mechanical.
    shares: Tuple[float, ...] = (0.5, 0.25, 0.75)
    #: Bar numbers (0-based) where ornaments are allowed. Empty means all.
    bars: Tuple[int, ...] = ()
    #: Cost when more than one voice ornaments the same transition. Two
    #: voices moving off the chord at once stop sounding like decoration and
    #: start sounding like a second, clashing harmony.
    simultaneous: float = 200.0
    #: Cuanto rinde cada tramo de una figura respecto del anterior. Menos de
    #: uno: la corrida de tres notas tiene que valer mas que la nota suelta y
    #: bastante menos que tres notas sueltas, o la busqueda cambia todos los
    #: adornos por corridas y la pieza se vuelve un estudio de escalas.
    decay: float = 0.62
    #: Cuantas notas puede tener una figura aca. La barra de frecuencia no la
    #: toca; lo que la barra decide es cuantas figuras y de que largo se
    #: sortean --- ver `pick_figure`.
    max_notes: int = MAX_FIGURE

    def allows_bar(self, bar_index: int) -> bool:
        return not self.bars or bar_index in self.bars
    #: Cost per passing tone beyond `max_per_piece`, so the texture does not
    #: turn into a scale exercise.
    #:
    #: Subido de 30, que en la práctica no separaba nada: al lado del resto
    #: del costo de una pieza ---cientos--- un adorno de más costaba 30 y
    #: rendía 24 de premio, o sea seis netos, y la búsqueda los compraba
    #: todos. Medido sobre seis semillas de 16 compases, con la barra en
    #: 0,25 (tope 2) salían igual entre 3 y 5 adornos: la barra sólo
    #: distinguía "ninguno" de "los que entren". Tiene que ganarle al premio
    #: por varias veces para que el tope se note.
    crowding: float = 140.0
    #: Lo fija la barra de frecuencia; ver `max_for_density`.
    max_per_piece: int = 3
    #: Only diatonic passing tones when True; chromatic ones are allowed
    #: otherwise, which is idiomatic in jazz and out of place in plainchant.
    diatonic_only: bool = True
    #: Fraction of the departing chord's duration the passing tone takes.
    share: float = 0.5

    @property
    def enabled(self) -> bool:
        return bool(self.voices)


def passing_candidates(
    from_pitch: int,
    to_pitch: int,
    scale_pcs: Sequence[int],
    diatonic_only: bool = True,
    max_leg: int = MAX_LEG,
) -> List[int]:
    """
    Notes a voice can touch on its way from one chord to the next.

    The note has to be reachable from where the voice is and still get where
    it is going, and it has to differ from both -- a repeated pitch is not an
    ornament, it is the same note struck twice. It does NOT have to lie
    between the two: a voice that rises a tone and then falls two is
    decorating its line just as legitimately as one filling a third.
    """
    low = min(from_pitch, to_pitch) - max_leg
    high = max(from_pitch, to_pitch) + max_leg
    allowed = {pc % 12 for pc in scale_pcs} if diatonic_only else None

    candidates = []
    for note in range(low, high + 1):
        if note == from_pitch or note == to_pitch:
            continue          # repeating a note is not an ornament
        if abs(note - from_pitch) > max_leg or abs(note - to_pitch) > max_leg:
            continue
        if allowed is not None and note % 12 not in allowed:
            continue
        candidates.append(note)
    return candidates


def score_passing(
    transitions: Sequence[Tuple[Sequence[int], Sequence[int]]],
    passing: Sequence[Sequence[Optional[int]]],
    rules: PassingRules,
) -> float:
    """
    Score a whole set of passing-tone decisions.

    ``transitions[i]`` is the pair of chords either side of transition ``i``,
    and ``passing[i][voice]`` is the note that voice takes there, or None.
    """
    if not rules.enabled:
        return 0.0

    total = 0.0
    used = 0
    for index, (previous, current) in enumerate(transitions):
        if index >= len(passing):
            break
        shapes = {}
        for voice, entry in enumerate(passing[index]):
            shape = figure(entry)
            if shape:
                shapes[voice] = shape
        if not shapes:
            continue
        # Se cuenta la **transicion**, no las notas: una figura de tres notas
        # es un adorno, no tres. El tope de la barra habla de cuantas veces
        # se adorna la pieza, no de cuanto dura cada adorno.
        used += 1
        total += _score_transition(previous, current, shapes, rules)

    if used > rules.max_per_piece:
        total += rules.crowding * (used - rules.max_per_piece)
    return total


def _score_transition(previous, current, shapes, rules):
    """
    Lo que vale una transicion adornada: las figuras y como conviven.

    Cada figura se juzga por **sus tramos** --- de la nota que deja, por cada
    nota de la figura, hasta la que toma --- y no por la nota suelta: una
    figura de tres notas que camina entera es tres veces la misma cosa buena,
    y una que camina dos tramos y se despena en el tercero no es "casi
    buena", es un salto raro con adorno adelante.

    El premio por tramo **no es lineal**: el segundo rinde menos que el
    primero y el tercero menos que el segundo. Lineal, la busqueda descubria
    enseguida que la corrida de tres vale tres veces la nota suelta y llenaba
    la pieza de corridas --- que es el mismo error de antes, al reves.
    """
    total = 0.0
    for voice, shape in shapes.items():
        start, end = previous[voice], current[voice]
        legs = [abs(b - a) for a, b in zip((start,) + shape, shape + (end,))]
        # Una altura repetida contra la nota que la voz ya tenia o va a tener
        # solo se perdona adentro de una figura: en un grupeto la nota de
        # salida vuelve a sonar y eso **es** el grupeto.
        if len(shape) == 1 and (shape[0] == start or shape[0] == end):
            total += rules.repeated_note
            continue
        if any(leg == 0 for leg in legs):
            total += rules.repeated_note
            continue
        if max(legs) > rules.max_leg:
            total += rules.clumsy
            continue
        if sum(1 for leg in legs if leg > STEP) > MAX_LEAPS:
            total += rules.clumsy
            continue
        earned = 0.0
        for position, leg in enumerate(legs):
            weight = rules.decay ** position
            earned += (rules.reward if leg <= STEP
                       else rules.reward * 0.35) * weight
        total += earned

    if len(shapes) > 1:
        # Sigue adornando una sola voz por transicion: varias a la vez dejan
        # de leerse como decoracion y suenan como una segunda armonia que
        # choca. Lo unico que cambio con las figuras es que ahora cada voz
        # trae varias notas, no que puedan ser varias voces.
        total += rules.simultaneous * (len(shapes) - 1)
    return total


def expand_with_passing(
    chords: Sequence[Sequence[int]],
    durations: Sequence[float],
    passing: Sequence[Sequence[Optional[int]]],
    share: float = 0.5,
) -> Tuple[List[List[int]], List[float], List[bool]]:
    """
    Turn a solution into the sequence of events a score actually contains.

    Every chord that carries a passing tone is split in two: the chord itself
    for the first part of its duration, then a second event where the voices
    with a passing tone move to it while the rest hold. Returns the pitches,
    the durations, and a flag marking which events are passing events, so the
    exporter can notate them without re-deriving any of it.
    """
    out_pitches: List[List[int]] = []
    out_durations: List[float] = []
    out_is_passing: List[bool] = []

    for index, chord in enumerate(chords):
        duration = durations[index]
        notes = passing[index] if index < len(passing) else []
        active = []
        if notes:
            for voice, entry in enumerate(notes):
                shape = figure(entry)
                if shape:
                    active.append((voice, shape))

        if not active:
            out_pitches.append(list(chord))
            out_durations.append(duration)
            out_is_passing.append(False)
            continue

        # Todas las figuras de una transicion tienen el mismo largo --- lo
        # piden la siembra y el evaluador --- asi que la cola se parte en
        # tantos pedazos iguales como notas tenga la figura. Si por lo que
        # fuera llegaran largos distintos manda el mas largo y las voces
        # cortas sostienen su ultima nota: es feo, pero el compas suma.
        steps = max(len(shape) for _voice, shape in active)
        head = duration * (1.0 - share)
        tail = duration - head
        out_pitches.append(list(chord))
        out_durations.append(head)
        out_is_passing.append(False)

        slice_length = tail / steps if steps else tail
        for position in range(steps):
            moved = list(chord)
            for voice, shape in active:
                moved[voice] = shape[min(position, len(shape) - 1)]
            out_pitches.append(moved)
            out_durations.append(slice_length)
            out_is_passing.append(True)

    return out_pitches, out_durations, out_is_passing
