# -*- coding: utf-8 -*-
"""
The voice-leading genetic algorithm.

What is being optimised
-----------------------
The user fixes the chords and their order; the GA never changes them. What it
searches for is the *register assignment*: for every chord slot and every
voice, which concrete octave of the assigned chord tone that voice sings.

Chromosome
----------
A chromosome is a list of chord slots; each slot holds one MIDI pitch per
voice. Every gene is drawn from a precomputed candidate table, so a
chromosome is always harmonically correct by construction -- it can only be
*musically* bad (large leaps, parallels, crossings), never wrong about which
notes belong to the chord. That keeps the search space small enough to
explore properly.

Search operators
----------------
* Tournament selection (size configurable, default 3).
* Elitism (default 2): the best chromosomes survive untouched.
* Uniform-ish crossover at a random slot boundary.
* Per-gene mutation that resamples a voice's octave from its candidates.

Hard constraints are handled by rejection: `fitness.evaluate` annuls invalid
chromosomes with an infinite cost, and the seeding routine builds candidates
slot by slot so that valid individuals are found cheaply instead of by blind
luck across the whole progression.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .fitness import (
    INFINITE_COST,
    FitnessBreakdown,
    RunSettings,
    evaluate,
    parallel_interval_violation,
)
from .harmony import HarmonyWeights, progression_cost
from .passing import PassingRules, passing_candidates, score_passing
from .style import (
    CONSONANT_ABOVE_BASS,
    ChordContext,
    bass_consonance_violations,
)
from .theory import VoicePart
from .voicing import ChordRequirement, VoicingPlan


@dataclass
class SlotOption:
    """One chord the search may place in a slot.

    Pairs what the voicing engine needs (``requirement``) with what the
    harmony judge needs (``harmony``). Manual mode builds exactly one of
    these per slot; the random generator builds one per candidate chord.
    """

    requirement: "ChordRequirement"
    harmony: Optional[object] = None      # harmony.ChordOption when generating


@dataclass
class ChordSlot:
    """One rhythmic position in the piece: a chord requirement plus its duration.

    ``locked_pitches`` pins the slot: when set, those exact MIDI pitches are
    what every chromosome sings here and the search never varies them. The
    slot still takes part in the fitness -- its transitions to and from its
    neighbours are scored normally -- so the locked chord shapes the voice
    leading around it instead of being carved out of the piece.
    """

    requirement: ChordRequirement
    duration_quarters: float
    bar_index: int = 0
    #: A rest occupies time but has no notes. The search skips it entirely:
    #: there is nothing to voice, and voice leading is measured across it as
    #: if the two sounding chords were adjacent, which is what a listener
    #: hears when a silence separates them.
    is_rest: bool = False
    locked_pitches: Optional[List[int]] = None
    #: Chords the search may place here. Empty in manual mode, where the user
    #: already chose; populated by the random generator, where picking the
    #: harmony is part of the search.
    options: List = field(default_factory=list)
    #: A bass pitch fixed to the exact note, not merely its pitch class.
    #: Used by the set-piece cadences whose whole point is a bass line.
    locked_bass: Optional[int] = None
    #: Voice index -> exact pitch, for parts the search may not touch. The
    #: harmoniser pins the given melody this way: offering that voice a
    #: single candidate means the search cannot alter it, while the
    #: counterpoint rules still measure everything else against it.
    pinned_voices: Dict[int, int] = field(default_factory=dict)

    @property
    def is_choice(self) -> bool:
        return len(self.options) > 1

    @property
    def is_locked(self) -> bool:
        return self.locked_pitches is not None

    @property
    def symbol(self) -> str:
        return self.requirement.chord.symbol

    @property
    def plan(self) -> VoicingPlan:
        return self.requirement.plan


@dataclass
class Chromosome:
    """A candidate solution: one MIDI pitch per voice for every chord slot."""

    slots: List[List[int]]
    #: Which chord option each slot uses. All zeros in manual mode.
    choices: List[int] = field(default_factory=list)
    #: passing[slot][voice] -> the ornament that voice takes on the way out
    #: of this slot, or None. At most one voice per slot. Empty when off.
    passing: List[List[Optional[int]]] = field(default_factory=list)
    #: How much of each slot's duration its ornament takes, so they are not
    #: all the same length.
    passing_share: List[float] = field(default_factory=list)
    #: The excursion this candidate makes: (key area, first bar, last bar),
    #: or None for a piece that stays home. Held as a plan rather than left
    #: to emerge from independent chord choices -- assembling a contiguous
    #: two-bar visit one mutation at a time essentially never happens, so
    #: the search only ever saw expensive, incoherent wandering.
    mod_plan: Optional[Tuple[str, int, int]] = None
    cost: float = INFINITE_COST
    breakdown: Optional[FitnessBreakdown] = None

    def copy(self) -> "Chromosome":
        return Chromosome(slots=[list(s) for s in self.slots],
                          choices=list(self.choices),
                          passing=[list(p) for p in self.passing],
                          passing_share=list(self.passing_share),
                          mod_plan=self.mod_plan,
                          cost=self.cost)

    def signature(self) -> Tuple[int, ...]:
        """Flat tuple of every pitch and chord choice, to spot duplicates."""
        return (tuple(pitch for slot in self.slots for pitch in slot)
                + tuple(self.choices)
                + tuple(-1 if n is None else n
                        for row in self.passing for n in row))


@dataclass
class GAConfig:
    """Tunable parameters of the search."""

    population_size: int = 200
    generations: int = 300
    elitism: int = 2
    tournament_size: int = 3
    mutation_rate: float = 0.12
    #: Chance that two parents are recombined at all. Crossover is the main
    #: engine of the search -- it recombines whole stretches of good voice
    #: leading -- while mutation only nudges single notes, so this is set
    #: well above `mutation_rate`. When it does not fire, the fitter parent
    #: is copied and mutation alone provides the variation.
    crossover_rate: float = 0.85
    #: Fraction of crossovers that mix voice by voice (uniform) instead of
    #: splitting the progression at one point. Uniform crossover can combine
    #: a good bass line from one parent with a good soprano from another,
    #: which single-point crossover cannot express.
    uniform_crossover_share: float = 0.4
    #: Chance that a mutation retargets a whole slot instead of a single voice.
    slot_mutation_rate: float = 0.05
    random_seed: Optional[int] = None
    #: Stop early when the best cost has not improved for this many
    #: generations. Keeps the UI responsive on easy progressions.
    #:
    #: 100 y no 60. El 60 se calibró cuando el sembrado devolvía dos
    #: individuos distintos y ciento noventa y ocho copias: una población así
    #: mejora despacito y sin mesetas, así que sesenta vueltas quietas
    #: significaban de verdad que no había más para sacar. Con el sembrado
    #: arreglado ---doscientos individuos distintos--- la búsqueda converge
    #: rápido, se planta un rato largo y **después vuelve a mejorar**, y el
    #: corte viejo la mataba justo en esa meseta. Medido en el Generador a 32
    #: compases: cortaba en la generación 187 con un costo de 16162, contra
    #: 13154 llegando a las 300. A 100 ya no corta ahí y recupera la calidad
    #: entera; probado con 140 da exactamente lo mismo, así que la meseta
    #: está entre los dos y no hace falta ir más arriba. En piezas cortas no
    #: cambia nada: ahí el corte nunca llegaba a dispararse.
    stagnation_limit: int = 100
    #: Worker processes for the search. ``None`` means "decide from the
    #: machine this is running on" (see :func:`resolve_worker_count`).
    #: Processes rather than threads: the search is pure Python CPU work, and
    #: the GIL means threads would take turns instead of running in parallel.
    workers: Optional[int] = None
    #: Chance of swapping the chord in a slot, in the generative mode only.
    #: Lower than the per-voice rate because it discards the slot's voicing.
    chord_mutation_rate: float = 0.06
    #: Chance of adding or removing a passing tone in one voice.
    passing_mutation_rate: float = 0.10


@dataclass
class GAResult:
    """Outcome of a run: the best distinct solutions plus some diagnostics."""

    solutions: List[Chromosome]
    generations_run: int
    evaluated: int
    seeded: int
    message: str = ""


class CandidateTable:
    """
    Precomputed legal pitches for every (slot, voice) pair.

    A cell holds every note of the chord that this particular voice can
    actually reach, so the GA is free to decide *which* chord tone each voice
    takes as well as in which octave -- that freedom is what lets doubled
    tones split apart and avoid parallel octaves.

    Building the table once turns the inner loop into a lookup. If any cell
    comes out empty the progression is unsingable as configured, and we can
    tell the user exactly where the problem is.
    """

    def __init__(self, slots: Sequence[ChordSlot], voices: Sequence[VoicePart]):
        self.voices = list(voices)
        #: table[slot][option][voice] -> reachable pitches
        self.table: List[List[List[List[int]]]] = []
        #: required[slot][option] -> pitch classes that must sound
        self.required: List[List[List[int]]] = []
        self.harmony: List[List[object]] = []
        self.empty_cells: List[Tuple[int, int]] = []
        self.locked: List[bool] = []
        #: areas[slot] -> {área tonal: índices de opción}. Se llena a pedido;
        #: ver `options_in_area`.
        self._areas: Dict[int, Dict[str, List[int]]] = {}

        for slot_index, slot in enumerate(slots):
            options = slot.options or [SlotOption(slot.requirement)]
            self.locked.append(slot.is_locked)
            self.harmony.append([opt.harmony for opt in options])

            if slot.is_locked:
                # One candidate per voice: the pinned pitch. Everything
                # downstream (sampling, mutation, repair) then leaves the
                # slot alone for free, with no special cases.
                self.table.append([[[p] for p in slot.locked_pitches]])
                self.required.append([list(options[0].requirement.required_pitch_classes)])
                continue

            slot_tables: List[List[List[int]]] = []
            slot_required: List[List[int]] = []
            for option in options:
                requirement = option.requirement
                slot_required.append(list(requirement.required_pitch_classes))
                row: List[List[int]] = []
                for voice_index, voice in enumerate(self.voices):
                    # The bass of a slash chord -- or of a Neapolitan sixth --
                    # is pinned to one pitch class; every other voice may take
                    # any tone of the chord.
                    if voice_index in slot.pinned_voices:
                        row.append([slot.pinned_voices[voice_index]])
                        continue
                    if voice_index == 0 and slot.locked_bass is not None:
                        # One note, exactly: the line is the point.
                        row.append([slot.locked_bass])
                        continue
                    if voice_index == 0 and requirement.bass_pitch_class is not None:
                        pool = [requirement.bass_pitch_class]
                    elif voice_index == 0:
                        # La voz más grave sólo puede tomar notas que
                        # definen el acorde: nada de color en el bajo, o el
                        # acorde que suena deja de ser el que se escribió.
                        pool = requirement.bass_pitch_classes
                    else:
                        pool = requirement.allowed_pitch_classes
                    candidates = sorted(
                        {m for pc in pool for m in voice.candidates_for_pitch_class(pc)}
                    )
                    row.append(candidates)
                slot_tables.append(row)

            # A slot is only unusable when NO option works: with several
            # chords on offer, one unreachable chord just removes that choice.
            usable = [
                index for index, row in enumerate(slot_tables)
                if all(cell for cell in row)
            ]
            if not usable:
                for voice_index, cell in enumerate(slot_tables[0]):
                    if not cell:
                        self.empty_cells.append((slot_index, voice_index))
                usable = [0]

            self.table.append([slot_tables[i] for i in usable])
            self.required.append([slot_required[i] for i in usable])
            self.harmony[slot_index] = [self.harmony[slot_index][i] for i in usable]

    @property
    def is_usable(self) -> bool:
        return not self.empty_cells

    def describe_problems(self, slots: Sequence[ChordSlot]) -> str:
        parts = []
        for slot_index, voice_index in self.empty_cells:
            voice = self.voices[voice_index]
            parts.append(
                f"{voice.name} no llega a ninguna nota de {slots[slot_index].symbol} "
                f"(acorde {slot_index + 1}) dentro de su registro"
            )
        return "; ".join(parts)

    def candidates(self, slot_index: int, voice_index: int,
                   option: int = 0) -> List[int]:
        return self.table[slot_index][option][voice_index]

    def option_count(self, slot_index: int) -> int:
        return len(self.table[slot_index])

    def options_in_area(self, slot_index: int, area: str) -> List[int]:
        """
        Qué opciones de este lugar pertenecen a un área tonal.

        El área de una opción --- su ``key_area`` --- la fija el pool de
        acordes **antes** de que arranque la búsqueda y no cambia nunca, así
        que esto se calcula una vez por lugar y después es una consulta.
        Se recalculaba en cada llamada, recorriendo todas las opciones y
        haciendo un ``getattr`` por cada una: medido en el Generador a 64
        acordes, **6,3 millones de llamadas en cuarenta generaciones**, el
        ítem con más llamadas de toda la corrida.

        La lista que devuelve **es la de la tabla, no una copia**. Los tres
        lugares que la piden sólo hacen `rng.choice(...)` y `x in ...`; si
        alguna vez hiciera falta modificarla, copiarla ahí.
        """
        by_area = self._areas.get(slot_index)
        if by_area is None:
            by_area = {}
            for index, option in enumerate(self.harmony[slot_index]):
                key = getattr(option, "key_area", "") or ""
                by_area.setdefault(key, []).append(index)
            # La casa: el lugar entero, para cuando el área pedida no tiene
            # ninguna opción y hay que caer en "cualquiera".
            by_area[_ANY_AREA] = list(range(self.option_count(slot_index)))
            self._areas[slot_index] = by_area
        return by_area.get(area) or by_area[_ANY_AREA]

    def required_for(self, slot_index: int, option: int = 0) -> List[int]:
        return self.required[slot_index][option]

    def bass_classes(self, slot_index: int, option: int = 0) -> List[int]:
        """Clases de altura que la voz más grave puede cantar en este lugar.

        Se leen de la propia tabla y no del acorde: la fila del bajo ya se
        armó con la restricción puesta, así que preguntarle a ella es
        preguntar por lo mismo que se le permitió al muestreo, sin ninguna
        chance de que las dos respuestas se separen.
        """
        return sorted({m % 12 for m in self.candidates(slot_index, 0, option)})

    def fixed_voices(self, slot_index: int, option: int = 0) -> Tuple[int, ...]:
        """
        Voices with exactly one reachable note in this slot.

        That single candidate is how every kind of pinning reaches the
        search: a melody note the user wrote, a bass line a set piece owns, a
        padlocked chord. It also covers the accidental case where a voice's
        range admits only one tone of the chord, which is equally immovable.
        Anything reading this must leave those voices where they are.
        """
        row = self.table[slot_index][option]
        return tuple(index for index, cell in enumerate(row) if len(cell) == 1)

    def covers_chord(self, slot_index: int, pitches: Sequence[int],
                     option: int = 0) -> bool:
        """True if the sung pitches include every required tone of the slot."""
        sounded = {p % 12 for p in pitches}
        return all(pc in sounded for pc in self.required_for(slot_index, option))


# ---------------------------------------------------------------------------
# Parallelism
# ---------------------------------------------------------------------------

def resolve_worker_count(requested: Optional[int], workload: int) -> int:
    """
    Decide how many worker processes to use on *this* machine.

    ``requested`` of None means auto-detect. We leave one core free so the
    interface stays responsive while the search runs, and we refuse to spin
    up more workers than there is work for -- on a small progression the cost
    of pickling the population to each process outweighs the parallel gain,
    which is why tiny jobs deliberately stay single-process.

    Note this uses processes, not threads: the search is pure Python CPU
    work, so the GIL would make threads take turns rather than run at once.
    """
    available = os.cpu_count() or 1
    if requested is not None and requested > 0:
        chosen = min(requested, available)
    else:
        chosen = max(1, available - 1)

    # Below this much work per generation, parallelism costs more than it saves.
    if workload < PARALLEL_WORKLOAD_THRESHOLD:
        return 1
    return max(1, min(chosen, MAX_WORKERS))


#: Population x slots below which the search stays single-process.
PARALLEL_WORKLOAD_THRESHOLD = 1200

#: Upper bound on workers; beyond this, pickling overhead dominates.
MAX_WORKERS = 8

#: Llave interna de `CandidateTable.options_in_area` para "todas las opciones
#: de este lugar". No es un área tonal: lleva un carácter que ninguna puede
#: tener para que no se pise con una de verdad.
_ANY_AREA = "\x00todas"


@dataclass
class _ScoreContext:
    """
    Todo lo que hace falta para puntuar un cromosoma, y nada más.

    Es lo **único** que sabe cómo se calcula el costo, y lo usan las dos
    ramas: la secuencial y la de procesos. Estaban escritas por separado y se
    separaron de verdad: la del pool sólo miraba las alturas, así que en el
    Generador ---donde elegir los acordes es la mitad del problema--- se
    perdían el término armónico y los ajustes que dependen de qué acorde
    eligió cada candidato. Medido con las mismas semillas, prendido el
    paralelismo salían 3 de cada 12 progresiones con el mismo acorde repetido
    ocho veces, más 10 unísonos, 15 solapamientos y 5 saltos de más de una
    octava; en secuencial, ninguno de los cuatro defectos.

    Nada de esto cambia durante la corrida, así que viaja **una vez** a cada
    proceso en el inicializador del pool y por cada cromosoma cruzan sólo las
    alturas, las opciones elegidas y los adornos.
    """

    base_settings: RunSettings
    #: required[slot][option] -> clases de altura que no pueden faltar
    required: List[List[List[int]]]
    contexts_by_option: List[List[ChordContext]]
    colours_by_option: List[List[List[int]]]
    #: harmony[slot][option] -> la opción de acorde, o None fuera del generador
    harmony_by_option: List[List[object]]
    option_counts: List[int]
    bar_indices: List[int]
    genre_key: str
    generative: bool
    tonic_pc: int = 0
    harmony_weights: Optional["HarmonyWeights"] = None
    passing_rules: Optional[PassingRules] = None

    def settings_for(self, choices: Sequence[int]) -> RunSettings:
        base = self.base_settings
        count = len(self.required)
        return RunSettings(
            profile=base.profile,
            voices=base.voices,
            required_pitch_classes=[
                self.required[i][choices[i]] for i in range(count)
            ],
            chord_contexts=[
                self.contexts_by_option[i][
                    min(choices[i], len(self.contexts_by_option[i]) - 1)]
                for i in range(count)
            ],
            colour_pitch_classes=[
                self.colours_by_option[i][
                    min(choices[i], len(self.colours_by_option[i]) - 1)]
                for i in range(count)
            ],
            # Rebuilt per candidate like the rest, so the melody rules keep
            # working: dropping it here silently switched them off.
            melody_voice=base.melody_voice,
            principalis_voice=base.principalis_voice,
        )

    def tidy(self, choices: Sequence[int]) -> List[int]:
        """Las opciones elegidas, completadas y recortadas a las que existen."""
        count = len(self.required)
        out = list(choices) or [0] * count
        if len(out) < count:
            out.extend([0] * (count - len(out)))
        return [min(c, self.option_counts[i] - 1) for i, c in enumerate(out)]

    def score(self, slots, choices, passing=None) -> FitnessBreakdown:
        """El costo de un cromosoma. La única definición que hay."""
        picked = self.tidy(choices)
        current = (self.settings_for(picked) if self.generative
                   else self.settings_for([0] * len(self.required)))
        breakdown = evaluate(slots, current)
        if breakdown.valid and self.generative and self.harmony_weights is not None:
            # The progression itself is judged here, on top of how it is
            # voiced: in the random generator choosing the chords is half
            # the problem.
            chosen = [
                self.harmony_by_option[i][picked[i]]
                for i in range(len(self.required))
                if self.harmony_by_option[i][picked[i]] is not None
            ]
            if chosen:
                breakdown.harmony = progression_cost(
                    chosen, self.genre_key, self.harmony_weights,
                    self.tonic_pc, self.bar_indices,
                )
                breakdown.total += breakdown.harmony
        rules = self.passing_rules
        if breakdown.valid and rules is not None and rules.enabled and passing:
            pairs = [(slots[i], slots[i + 1]) for i in range(len(slots) - 1)]
            breakdown.passing = score_passing(pairs, passing, rules)
            breakdown.total += breakdown.passing
        return breakdown


#: Per-process copy of the scoring context, installed by the pool initializer
#: so the (fairly chunky) tables are pickled once per worker instead of once
#: per batch per generation.
_WORKER_CONTEXT: Optional[_ScoreContext] = None


def _init_worker(context: "_ScoreContext") -> None:
    """Pool initializer: stash the scoring context in this process."""
    global _WORKER_CONTEXT
    _WORKER_CONTEXT = context


def _evaluate_batch(jobs):
    """
    Worker entry point: score a batch of chromosomes.

    Defined at module level because process pools pickle the callable by
    name. Cada trabajo son las alturas, las opciones de acorde elegidas y los
    adornos; sólo vuelven los costos, así que lo que cruza el límite entre
    procesos sigue siendo chico.

    Puntúa con el mismo ``_ScoreContext.score`` que la rama secuencial: es la
    única definición del costo que hay, y por eso las dos ramas no se pueden
    volver a separar.
    """
    context = _WORKER_CONTEXT
    return [context.score(slots, choices, passing).total
            for slots, choices, passing in jobs]


def _chord_list(indices: Sequence[int]) -> str:
    """"acorde 3", "acordes 1 y 16", "acordes 1, 4 y 9"."""
    numbers = [str(i + 1) for i in indices]
    if len(numbers) == 1:
        return f"acorde {numbers[0]}"
    if len(numbers) == 2:
        return f"acordes {numbers[0]} y {numbers[1]}"
    return f"acordes {', '.join(numbers[:-1])} y {numbers[-1]}"


def _requirement_dead_end(
    requirement: ChordRequirement,
    profile,
    is_repose: bool,
) -> Optional[str]:
    """
    Por qué este acorde no se puede escribir, o ``None`` si sí se puede.

    Devuelve una frase con ``{subject}`` sin completar: quien llama sabe si
    el sujeto es el cifrado del acorde o "ninguno de los acordes que el
    generador podía poner acá".
    """
    required = requirement.required_pitch_classes

    if profile.forbid_harmonic_tritone:
        tritone = any((b - a) % 12 == 6
                      for i, a in enumerate(required)
                      for b in required[i + 1:])
        if tritone:
            # El tritono puede no estar en el acorde sino en los colores que
            # le agrega el dial --- un Cmaj7 con la oncena tiene Si y Fa ---
            # y decirle al usuario que "Cmaj7 tiene un tritono" cuando no lo
            # tiene es mandarlo a mirar donde no está.
            added = {requirement.plan.chord.pitch_class_of(tone)
                     for tone in requirement.plan.added}
            plain = [pc for pc in required if pc not in added]
            own = any((b - a) % 12 == 6
                      for i, a in enumerate(plain)
                      for b in plain[i + 1:])
            if added and not own:
                return ("{subject} no tiene tritono entre sus notas, pero sí "
                        "con las de color que le agrega el dial. Bajá el "
                        "color, o apagá la regla del tritono.")
            return ("{subject} tiene un tritono entre sus propias notas, así "
                    "que no hay manera de escribirlo sin que suene. Apagá "
                    "esa regla o usá otro acorde.")

    if profile.cadence_consonance_required and is_repose:
        # La consonancia se mide desde el bajo, así que la pregunta es si
        # ALGUNA nota del acorde sirve de bajo con todas las demás
        # consonantes por encima.
        workable = [
            bass for bass in required
            if all((pc - bass) % 12 in CONSONANT_ABOVE_BASS for pc in required)
        ]
        if not workable:
            return ("{subject} es un acorde de reposo y ninguna de sus "
                    "inversiones queda del todo consonante sobre el bajo. "
                    "Poné la consonancia como preferencia en vez de "
                    "exigencia, o cerrá con un acorde más simple.")

    return None


def _slot_dead_end(
    slot: ChordSlot,
    settings: RunSettings,
    is_repose: bool,
) -> Optional[Tuple[str, str]]:
    """
    ``(sujeto, frase)`` si este lugar no tiene salida; ``None`` si la tiene.

    En el Organizador el acorde está escrito y hay una sola posibilidad. En
    el Generador el mismo lugar ofrece decenas, y basta con que **una** se
    pueda escribir para que no haya nada que denunciar: preguntar sólo por
    la primera hacía que un tramo perfectamente resoluble se reportara como
    imposible, y con el mismo cifrado en los dieciséis acordes.
    """
    profile = settings.profile

    if slot.is_locked:
        pitches = slot.locked_pitches or []
        if profile.cadence_consonance_required and is_repose:
            if bass_consonance_violations(pitches):
                return (f"el acorde fijado {slot.symbol}",
                        "{subject} tiene una disonancia sobre su propio bajo, "
                        "y está en un punto de reposo donde se exige "
                        "consonancia. Cambiá el orden de las voces fijadas, o "
                        "poné la consonancia como preferencia.")
        for position, pitch in enumerate(pitches):
            if position >= len(settings.voices):
                break
            if not settings.voices[position].contains(pitch):
                return (f"el acorde fijado {slot.symbol}",
                        "{subject} deja a "
                        f"{settings.voices[position].name} fuera de su "
                        "registro.")
        return None

    options = list(slot.options) or []
    requirements = [option.requirement for option in options] or [slot.requirement]
    reasons = []
    for requirement in requirements:
        reason = _requirement_dead_end(requirement, profile, is_repose)
        if reason is None:
            return None          # con una sola que se pueda escribir, alcanza
        reasons.append(reason)

    if len(requirements) > 1:
        return (f"ninguno de los {len(requirements)} acordes que el generador "
                f"puede poner acá", reasons[0])
    return (slot.symbol, reasons[0])


def diagnose_impossible_slots(
    slots: Sequence[ChordSlot],
    settings: RunSettings,
) -> List[str]:
    """
    Find chords that no voicing can satisfy, and say why.

    Some hard rules can be decided from the chord alone, without searching:
    a dominant seventh *is* a tritone, so banning the harmonic tritone makes
    it unwritable in any register. Detecting that here turns a useless "no
    valid voicing exists" into a message naming the chord and the switch
    responsible, which is the difference between a dead end and a decision
    the user can make.

    Works on pitch classes, so it is exact for these rules and costs nothing.

    Los acordes que fallan por lo mismo salen en una sola línea. En el
    Generador el callejón sin salida suele ser el mismo en todos --- los
    extremos fijados en I, por ejemplo --- y repetir la misma frase una vez
    por acorde llenaba la pantalla de un texto que decía un solo dato.
    """
    repose = {0, len(slots) - 1} if slots else set()
    grouped: "Dict[Tuple[str, str], List[int]]" = {}
    order: List[Tuple[str, str]] = []

    for index, slot in enumerate(slots):
        found = _slot_dead_end(slot, settings, index in repose)
        if found is None:
            continue
        if found not in grouped:
            grouped[found] = []
            order.append(found)
        grouped[found].append(index)

    problems: List[str] = []
    for key in order:
        subject, phrase = key
        indices = grouped[key]
        problems.append(
            f"{_chord_list(indices).capitalize()}: "
            + phrase.format(subject=subject)
        )
    return problems


def choose_modulation_plan(
    slots: Sequence[ChordSlot],
    settings: Optional["ModulationSettings"],
    rng: random.Random,
) -> Optional[Tuple[str, int, int]]:
    """
    Decide where the piece travels, before any chord is chosen.

    Picking the window first is what makes a modulation hold together: the
    visit is contiguous, starts on a downbeat, lasts long enough and leaves
    room at both ends because it was built that way, not because the search
    happened to stumble into it.
    """
    if settings is None or not settings.enabled or not settings.targets:
        return None

    bars = sorted({slot.bar_index for slot in slots})
    if len(bars) < settings.min_bars_for_modulation:
        return None

    margin = settings.home_margin_bars
    first_allowed = bars[0] + margin
    last_allowed = bars[-1] - margin
    if last_allowed - first_allowed + 1 < settings.min_bars:
        return None

    length = rng.randint(settings.min_bars,
                         max(settings.min_bars,
                             min(4, last_allowed - first_allowed + 1)))
    latest_start = last_allowed - length + 1
    if latest_start < first_allowed:
        return None

    # Phrases usually turn on an even bar, so those starts are offered first.
    starts = [b for b in range(first_allowed, latest_start + 1)]
    even = [b for b in starts if b % 2 == 0]
    start = rng.choice(even or starts)
    return (rng.choice(list(settings.targets)), start, start + length - 1)


def _options_for_plan(
    table: CandidateTable,
    slot_index: int,
    bar_index: int,
    plan: Optional[Tuple[str, int, int]],
) -> List[int]:
    """Option indices allowed in this slot given the excursion plan."""
    wanted = ""
    if plan is not None and plan[1] <= bar_index <= plan[2]:
        wanted = plan[0]
    return table.options_in_area(slot_index, wanted)


def _without_repeating(
    table: CandidateTable,
    slot_index: int,
    allowed: Sequence[int],
    choices: Sequence[int],
) -> List[int]:
    """
    Las opciones de este lugar que no repiten la cifra del lugar anterior.

    El sembrado elegía el acorde de cada lugar **sin mirar el de al lado**, y
    la gramática cobra dos cifras romanas iguales seguidas con un costo
    infinito (`harmony.progression_cost`, `weights.forbid_repeat`): el
    cromosoma entero se anulaba por un choque que no se había mirado al
    armarlo. Con una docena de opciones por lugar, la probabilidad de zafar
    en los 63 empalmes de una pieza de 32 compases es (11/12)^63, o sea
    medio por ciento --- y medido da eso: **de 2235 cromosomas sembrados
    sobrevivían 2**, y a veces ninguno. Cuando sobrevivía ninguno el programa
    contestaba "con las reglas prendidas no hay ninguna forma de escribir
    esta progresión", que es falso: la hay, y el sembrado no la buscó bien.
    Dos de cada diez generaciones de 32 compases terminaban así.

    Y cuando *sí* había solución era casi igual de malo, sólo que en
    silencio: una población de doscientos armada con dos individuos distintos
    y ciento noventa y ocho copias no tiene con qué cruzar.

    No afloja ninguna regla --- le enseña al sembrado una que ya existía, del
    mismo modo que ya sabía de rangos, cruces y paralelas. Si **todas** las
    opciones repiten (un lugar con una sola, por ejemplo) devuelve las que
    había: forzar la regla ahí sería quedarse sin ninguna.
    """
    if not choices:
        return list(allowed)
    earlier = table.harmony[slot_index - 1][choices[-1]]
    previous_roman = getattr(earlier, "roman", None)
    if previous_roman is None:
        return list(allowed)
    slot_harmony = table.harmony[slot_index]
    fresh = [index for index in allowed
             if getattr(slot_harmony[index], "roman", None) != previous_roman]
    return fresh or list(allowed)


def _seed_chromosome(
    table: CandidateTable,
    settings: RunSettings,
    rng: random.Random,
    attempts_per_slot: int = 60,
    slots: Sequence[ChordSlot] = (),
    modulation_settings: Optional["ModulationSettings"] = None,
) -> Optional[Chromosome]:
    """
    Build one valid chromosome slot by slot.

    Each slot is sampled repeatedly until it neither breaks a hard constraint
    against the previous slot nor lands outside anyone's range. Solving the
    constraints locally like this is dramatically cheaper than generating a
    whole progression at random and hoping none of its transitions collide --
    with a dozen slots, blind sampling almost never produces a valid
    individual.
    """
    slot_count = len(table.table)
    chosen: List[List[int]] = []

    # Pairwise checks during seeding must not carry the whole-piece coverage
    # table: evaluate() would index it as chords 0 and 1 while we are really
    # looking at slots k-1 and k. Coverage is already guaranteed by
    # _sample_slot, so the pair only needs the rule checks.
    # Pairwise checks during seeding must not carry any *positional* rule.
    # evaluate() reads a two-chord list as a whole piece, so chord 1 of every
    # pair looks like the final chord: with cadence consonance switched on,
    # every passing chord would be forced to be consonant above the bass.
    # Chords like G7 and E7 have no consonant voicing at all, so seeding
    # rejected everything and the population came out empty -- reported to
    # the user as "no valid voicing exists" when in fact one did.
    # Coverage is already guaranteed by _sample_slot; the repose rule is
    # applied below, only to the slots it actually governs.
    pair_settings = RunSettings(
        profile=replace(settings.profile, cadence_consonance_required=False),
        voices=settings.voices,
        required_pitch_classes=None,
    )
    repose_slots = (
        {0, slot_count - 1} if settings.profile.cadence_consonance_required else set()
    )

    plan = choose_modulation_plan(slots, modulation_settings, rng)
    choices: List[int] = []
    for slot_index in range(slot_count):
        previous = chosen[-1] if chosen else None
        best_pick: Optional[List[int]] = None
        best_option = 0

        # Fuera del bucle de intentos: no depende de cuál sea el intento y no
        # consume azar, así que llamarlo sesenta veces por lugar era pagar lo
        # mismo sesenta veces.
        allowed = _options_for_plan(
            table, slot_index, slots[slot_index].bar_index, plan)
        allowed = _without_repeating(table, slot_index, allowed, choices)

        for _ in range(attempts_per_slot):
            option = rng.choice(allowed)
            pick = _sample_slot(table, slot_index, rng, option=option)
            if pick is None:
                continue
            # Repose chords carry their own rule, checked here where we know
            # the slot's real position in the piece.
            if slot_index in repose_slots and bass_consonance_violations(pick):
                continue
            if previous is None:
                best_pick, best_option = pick, option
                break
            trial = evaluate([previous, pick], pair_settings)
            if trial.valid:
                best_pick, best_option = pick, option
                break

        if best_pick is None:
            return None
        chosen.append(best_pick)
        choices.append(best_option)

    return Chromosome(slots=chosen, choices=choices, mod_plan=plan)


def _sample_slot(
    table: CandidateTable,
    slot_index: int,
    rng: random.Random,
    attempts: int = 40,
    option: int = 0,
) -> Optional[List[int]]:
    """
    Draw one random slot assignment that contains every required chord tone.

    Sampling voices independently usually leaves a tone missing, so after a
    plain draw we repair the result: each missing pitch class is handed to a
    voice that can sing it and whose own tone is already covered elsewhere.
    Repairing is far cheaper than rejecting and redrawing.
    """
    voice_count = len(table.voices)
    required = table.required_for(slot_index, option)

    for _ in range(attempts):
        pick = [rng.choice(table.candidates(slot_index, v, option))
                for v in range(voice_count)]
        missing = [pc for pc in required if pc not in {p % 12 for p in pick}]
        if not missing:
            return pick

        for pc in missing:
            # Voices that could sing the missing tone, preferring one whose
            # current note is duplicated elsewhere so nothing else is lost.
            options = [
                v for v in range(voice_count)
                if any(m % 12 == pc for m in table.candidates(slot_index, v, option))
            ]
            if not options:
                break
            sounded = [p % 12 for p in pick]
            redundant = [
                v for v in options
                if sounded.count(pick[v] % 12) > 1 or pick[v] % 12 not in required
            ]
            target = rng.choice(redundant or options)
            replacements = [
                m for m in table.candidates(slot_index, target, option) if m % 12 == pc
            ]
            pick[target] = min(replacements, key=lambda m: abs(m - pick[target]))

        if all(pc in {p % 12 for p in pick} for pc in required):
            return _uncross(pick, table.voices,
                            table.fixed_voices(slot_index, option),
                            table.bass_classes(slot_index, option))

    return None


def _uncross(
    pitches: List[int],
    voices: Sequence[VoicePart],
    fixed: Sequence[int] = (),
    bass_classes: Optional[Sequence[int]] = None,
) -> List[int]:
    """
    Hand the sampled notes out in ascending order when the ranges allow it.

    Sampling each voice independently often produces a crossing (the alto
    drawing a note below the tenor). Sorting is a free repair: it never
    changes which notes sound, only who sings them, so the harmony is
    untouched. If sorting would push someone out of their range we leave the
    original assignment alone and let the evaluator judge it.

    ``fixed`` names voices that must keep their seat as well as their note.
    "Only who sings them" is precisely what a pinned voice cannot afford: the
    harmonising mode pins the user's melody to one voice, and sorting handed
    that note to whoever happened to sort into its place, so the line came
    back rewritten and the exported score showed something the user never
    played. The remaining voices are still sorted among themselves, so the
    repair keeps working everywhere it is safe.

    ``bass_classes`` son las clases de altura que la voz más grave tiene
    permitido cantar. "Sólo cambia quién las canta" **no** es cierto para el
    bajo: cuál es la nota más grave es lo que decide de qué acorde se trata.
    La tabla de candidatos ya le prohíbe al bajo las notas de color, pero
    ordenar las alturas se saltaba esa prohibición por la ventana --- si la
    novena o la oncena era la nota más baja del acorde, el ordenamiento se la
    entregaba al bajo y el acorde escrito pasaba a ser otro. Un ``Dm7`` con
    la oncena agregada volvía si-fa-la-re, o sea un ``Bm7b5``.

    Cuando eso pasa se deja el reparto original, exactamente como cuando
    ordenar dejaría a alguien fuera de su registro: un cruce lo juzga el
    evaluador y se puede pagar, un acorde que no es el que se pidió, no.
    """
    free = [index for index in range(len(pitches)) if index not in set(fixed)]
    ordered = list(pitches)
    for position, pitch in zip(free, sorted(ordered[index] for index in free)):
        ordered[position] = pitch
    if not all(voices[i].contains(ordered[i]) for i in range(len(ordered))):
        return pitches
    if (bass_classes is not None and ordered and 0 in free
            and ordered[0] % 12 not in set(bass_classes)):
        return pitches
    return ordered


def _seed_passing(
    chromosome: Chromosome,
    rules: PassingRules,
    scale_pcs: Sequence[int],
    rng: random.Random,
    bar_of: Optional[Callable[[int], int]] = None,
) -> None:
    """
    Place ornaments up front, according to the density the user chose.

    Leaving them to mutation alone made them almost never appear: a good
    voicing moves by steps, so the openings mutation was looking for barely
    existed. Seeding them means the search starts with ornaments present and
    spends its effort deciding which ones are worth keeping.
    """
    if not rules.enabled:
        return
    bar_of = bar_of or (lambda index: 0)
    voice_count = len(chromosome.slots[0]) if chromosome.slots else 0
    _ensure_passing(chromosome, len(chromosome.slots), voice_count)

    while len(chromosome.passing_share) < len(chromosome.slots):
        chromosome.passing_share.append(0.5)

    for slot_index in range(len(chromosome.slots) - 1):
        if not rules.allows_bar(bar_of(slot_index)):
            continue
        if rng.random() >= rules.density:
            continue
        # One voice per transition: several at once stop reading as
        # decoration and start sounding like a second, clashing harmony.
        eligible = [v for v in rules.voices if v < voice_count]
        rng.shuffle(eligible)
        for voice in eligible:
            options = passing_candidates(
                chromosome.slots[slot_index][voice],
                chromosome.slots[slot_index + 1][voice],
                scale_pcs, rules.diatonic_only, rules.max_leg,
            )
            if options:
                chromosome.passing[slot_index][voice] = rng.choice(options)
                chromosome.passing_share[slot_index] = rng.choice(rules.shares)
                break


def _ensure_passing(chromosome: Chromosome, slot_count: int, voice_count: int) -> None:
    """Give the passing grid the shape the slots and voices require."""
    while len(chromosome.passing) < slot_count:
        chromosome.passing.append([None] * voice_count)
    del chromosome.passing[slot_count:]
    # Crossover builds children without the share list, so it is normalised
    # here alongside the grid rather than only when seeding.
    while len(chromosome.passing_share) < slot_count:
        chromosome.passing_share.append(0.5)
    del chromosome.passing_share[slot_count:]
    for row in chromosome.passing:
        while len(row) < voice_count:
            row.append(None)
        del row[voice_count:]


def _enforce_plan(
    chromosome: Chromosome,
    table: CandidateTable,
    slot_bars: Sequence[int],
    rng: random.Random,
) -> None:
    """
    Make every slot agree with the excursion this candidate is making.

    Crossover splices the chord choices of two parents but the plan travels
    whole from one of them, so a child could inherit foreign chords from a
    window it no longer has -- which showed up as a second, unplanned visit
    to the same key.
    """
    plan = chromosome.mod_plan
    for slot_index in range(len(chromosome.slots)):
        if table.locked[slot_index]:
            continue
        bar = slot_bars[slot_index] if slot_index < len(slot_bars) else 0
        allowed = _options_for_plan(table, slot_index, bar, plan)
        if chromosome.choices[slot_index] not in allowed:
            option = rng.choice(allowed)
            chromosome.choices[slot_index] = option
            fresh = _sample_slot(table, slot_index, rng, option=option)
            if fresh is not None:
                chromosome.slots[slot_index] = fresh


def _ensure_choices(chromosome: Chromosome, slot_count: int) -> None:
    """
    Make the chord-choice list line up with the slots.

    Crossover can hand back a chromosome whose choices are shorter than its
    slots -- the uniform variant mixes positions rather than cutting once --
    and clones start with none at all. Normalising here means every other
    function can index the list without checking first.
    """
    if len(chromosome.choices) < slot_count:
        chromosome.choices.extend([0] * (slot_count - len(chromosome.choices)))
    elif len(chromosome.choices) > slot_count:
        del chromosome.choices[slot_count:]


def _mutate(
    chromosome: Chromosome,
    table: CandidateTable,
    config: GAConfig,
    rng: random.Random,
    passing_rules: Optional[PassingRules] = None,
    scale_pcs: Sequence[int] = (),
    slot_bars: Sequence[int] = (),
    settings: Optional[RunSettings] = None,
) -> None:
    """Mutate in place: resample individual voices, occasionally whole slots."""
    voice_count = len(table.voices)
    _ensure_choices(chromosome, len(chromosome.slots))
    _enforce_plan(chromosome, table, slot_bars, rng)
    _ensure_passing(chromosome, len(chromosome.slots), voice_count)
    for slot_index in range(len(chromosome.slots)):
        if table.locked[slot_index]:
            continue          # a locked slot is never varied

        option = min(chromosome.choices[slot_index],
                     table.option_count(slot_index) - 1)
        chromosome.choices[slot_index] = option

        # Swapping the chord in a slot is a bigger jump than nudging one
        # voice, so it has its own lower rate, and the whole slot is
        # resampled afterwards: the old pitches belong to a chord that is no
        # longer there.
        if (table.option_count(slot_index) > 1
                and rng.random() < config.chord_mutation_rate):
            option = rng.choice(_options_for_plan(
                table, slot_index,
                slot_bars[slot_index] if slot_index < len(slot_bars) else 0,
                chromosome.mod_plan))
            fresh = _sample_slot(table, slot_index, rng, option=option)
            if fresh is not None:
                chromosome.choices[slot_index] = option
                chromosome.slots[slot_index] = fresh
                continue

        # Passing tones live on the way OUT of a slot, so the last one has
        # none: there is no following chord to resolve into.
        if (passing_rules is not None and passing_rules.enabled
                and slot_index < len(chromosome.slots) - 1
                and rng.random() < config.passing_mutation_rate):
            # Rebuild this transition's ornament from scratch: clearing it
            # first is what keeps the "one voice at a time" rule true after
            # mutation, instead of letting voices accumulate.
            for v in range(voice_count):
                chromosome.passing[slot_index][v] = None
            eligible = [v for v in passing_rules.voices if v < voice_count]
            rng.shuffle(eligible)
            for voice_index in eligible:
                if rng.random() >= passing_rules.density:
                    continue
                start = chromosome.slots[slot_index][voice_index]
                end = chromosome.slots[slot_index + 1][voice_index]
                choices_here = passing_candidates(
                    start, end, scale_pcs, passing_rules.diatonic_only,
                    passing_rules.max_leg,
                )
                if choices_here:
                    chromosome.passing[slot_index][voice_index] = rng.choice(choices_here)
                    if slot_index < len(chromosome.passing_share):
                        chromosome.passing_share[slot_index] = rng.choice(
                            passing_rules.shares
                        )
                    break

        touched = False
        if rng.random() < config.slot_mutation_rate:
            fresh = _sample_slot(table, slot_index, rng, option=option)
            if fresh is not None:
                chromosome.slots[slot_index] = fresh
            continue
        for voice_index in range(voice_count):
            if rng.random() < config.mutation_rate:
                candidates = table.candidates(slot_index, voice_index, option)
                chromosome.slots[slot_index][voice_index] = rng.choice(candidates)
                touched = True
        if touched:
            _repair_coverage(chromosome.slots[slot_index], table, slot_index, rng,
                             option)
            chromosome.slots[slot_index] = _uncross(
                chromosome.slots[slot_index], table.voices,
                table.fixed_voices(slot_index, option),
                table.bass_classes(slot_index, option),
            )

    _prune_stale_passing(chromosome, passing_rules)


def _prune_stale_passing(
    chromosome: Chromosome,
    rules: Optional[PassingRules],
) -> None:
    """
    Drop ornaments that stopped making sense after the voicing moved.

    An ornament is chosen against the two pitches around it, but mutation
    goes on changing those pitches afterwards -- so a note that was a proper
    decoration can end up identical to the chord tone it was meant to
    decorate, or too far to reach. Re-checking here keeps the promise that
    what comes out is singable, instead of leaving it to the score to
    discourage.
    """
    if rules is None or not rules.enabled:
        return
    for slot_index in range(len(chromosome.passing)):
        if slot_index + 1 >= len(chromosome.slots):
            for voice in range(len(chromosome.passing[slot_index])):
                chromosome.passing[slot_index][voice] = None
            continue
        for voice, note in enumerate(chromosome.passing[slot_index]):
            if note is None:
                continue
            start = chromosome.slots[slot_index][voice]
            end = chromosome.slots[slot_index + 1][voice]
            if (note == start or note == end
                    or abs(note - start) > rules.max_leg
                    or abs(note - end) > rules.max_leg):
                chromosome.passing[slot_index][voice] = None


def _repair_coverage(
    pitches: List[int],
    table: CandidateTable,
    slot_index: int,
    rng: random.Random,
    option: int = 0,
) -> None:
    """
    Put back any required chord tone a mutation knocked out.

    Without this almost every mutated child fails the coverage constraint and
    gets thrown away, which starves the population and makes the search crawl.
    Repairing in place keeps mutation cheap and productive.
    """
    required = table.required_for(slot_index, option)
    sounded = [p % 12 for p in pitches]
    missing = [pc for pc in required if pc not in sounded]
    if not missing:
        return

    for pc in missing:
        options = [
            v for v in range(len(pitches))
            if any(m % 12 == pc for m in table.candidates(slot_index, v, option))
        ]
        if not options:
            continue
        sounded = [p % 12 for p in pitches]
        # Prefer overwriting a voice whose note is duplicated or not required.
        redundant = [
            v for v in options
            if sounded.count(pitches[v] % 12) > 1 or pitches[v] % 12 not in required
        ]
        target = rng.choice(redundant or options)
        replacements = [m for m in table.candidates(slot_index, target, option)
                        if m % 12 == pc]
        pitches[target] = min(replacements, key=lambda m: abs(m - pitches[target]))


def _crossover(
    parent_a: Chromosome,
    parent_b: Chromosome,
    rng: random.Random,
    config: Optional[GAConfig] = None,
) -> Chromosome:
    """
    Recombine two parents.

    Two flavours, because they explore different things:

    * **Single point** splits the progression in time, so a child inherits
      the opening of one parent and the ending of another. Good at combining
      well-solved passages.
    * **Uniform per voice** gives each voice line wholesale to one parent or
      the other, so a strong bass can be paired with a strong soprano. A
      single-point cut cannot express that, because it always takes every
      voice from the same parent on either side of the cut.

    When crossover does not fire the fitter parent is copied unchanged and
    mutation supplies the variation on its own.
    """
    config = config or GAConfig()
    slot_count = len(parent_a.slots)
    if slot_count == 0:
        return parent_a.copy()

    if rng.random() >= config.crossover_rate:
        better = parent_a if parent_a.cost <= parent_b.cost else parent_b
        return better.copy()

    voice_count = len(parent_a.slots[0])

    if voice_count > 1 and rng.random() < config.uniform_crossover_share:
        # Uniform: decide per voice which parent contributes that whole line.
        picks = [rng.random() < 0.5 for _ in range(voice_count)]
        slots = [
            [
                (parent_a if picks[v] else parent_b).slots[i][v]
                for v in range(voice_count)
            ]
            for i in range(slot_count)
        ]
        return Chromosome(slots=slots)

    if slot_count < 2:
        return parent_a.copy()
    cut = rng.randint(1, slot_count - 1)
    slots = [list(s) for s in parent_a.slots[:cut]]
    slots.extend(list(s) for s in parent_b.slots[cut:])
    # The chord choices travel with the voicings they belong to: splitting
    # them at a different point would hand a slot a voicing built for a
    # chord that is no longer there.
    choices = list(parent_a.choices[:cut]) + list(parent_b.choices[cut:])
    # The count is rebuilt by the repair pass on the child, so it starts
    # from zero rather than inheriting a parent's total.
    passing = ([list(r) for r in parent_a.passing[:cut]]
               + [list(r) for r in parent_b.passing[cut:]])
    shares = (list(parent_a.passing_share[:cut])
              + list(parent_b.passing_share[cut:]))
    # The plan travels whole from one parent: splicing two different
    # excursions would produce a window that is neither.
    # The sixths live in the notes that were spliced in, so the count comes
    # across with them; without this the credit vanished the moment a
    # repaired candidate had a child, which is why no winner ever showed one.
    return Chromosome(slots=slots, choices=choices,
                      passing=passing, passing_share=shares,
                      mod_plan=(parent_a.mod_plan if rng.random() < 0.5
                                else parent_b.mod_plan))


def _restore_locks(chromosome: Chromosome, table: "CandidateTable") -> None:
    """
    Force every locked slot back to its pinned pitches.

    Crossover copies whole stretches between parents, and uniform crossover
    mixes voices, so a locked slot could in principle be assembled from two
    different parents. Both parents hold the same pinned pitches, so this is
    belt-and-braces -- but it costs nothing and means no future operator can
    quietly break the guarantee the padlock makes to the user.
    """
    for slot_index, is_locked in enumerate(table.locked):
        if is_locked:
            chromosome.slots[slot_index] = [
                candidates[0] for candidates in table.table[slot_index]
            ]


def _tournament(
    population: Sequence[Chromosome],
    size: int,
    rng: random.Random,
) -> Chromosome:
    contenders = rng.sample(population, min(size, len(population)))
    return min(contenders, key=lambda c: c.cost)


def run(
    slots: Sequence[ChordSlot],
    settings: RunSettings,
    config: Optional[GAConfig] = None,
    progress: Optional[Callable[[int, float], None]] = None,
    solutions_wanted: int = 3,
    harmony_weights: Optional["HarmonyWeights"] = None,
    tonic_pc: Optional[int] = None,
    passing_rules: Optional[PassingRules] = None,
    scale_pcs: Sequence[int] = (),
) -> GAResult:
    """
    Run the genetic algorithm and return the best distinct solutions.

    ``progress`` is called as ``progress(generation, best_cost)`` so the GUI
    can drive a progress bar without the engine importing anything graphical.
    """
    config = config or GAConfig()
    rng = random.Random(config.random_seed)

    table = CandidateTable(slots, settings.voices)
    # The evaluator needs to know which tones may not go missing. Deriving it
    # here means callers cannot forget to pass it and get silently gutted
    # chords back.
    # Which tones may not go missing, and the harmonic facts behind each
    # slot, both depend on WHICH chord a chromosome chose -- so they are
    # rebuilt per candidate rather than fixed once for the whole run.
    slot_options = [slot.options or [SlotOption(slot.requirement)] for slot in slots]
    # La cifra romana viaja con el contexto cuando existe: es lo que le
    # permite al evaluador reconocer un V que resuelve a la tónica sin tener
    # que adivinar la tonalidad, y ---sobre todo--- lo que hace que la
    # búsqueda y el post-proceso estén mirando el mismo acorde. En el
    # Organizador no hay ninguna, y las reglas que la usan tienen su camino
    # sin ella.
    contexts_by_option = [
        [ChordContext.from_chord(option.requirement.chord,
                                 getattr(option.harmony, "roman", None))
         for option in options]
        for options in slot_options
    ]
    colours_by_option = [
        [
            [option.requirement.chord.pitch_class_of(tone)
             for tone in option.requirement.plan.added]
            for option in options
        ]
        for options in slot_options
    ]
    base_settings = settings

    generative = any(table.option_count(i) > 1 for i in range(len(slots)))
    context = _ScoreContext(
        base_settings=base_settings,
        required=table.required,
        contexts_by_option=contexts_by_option,
        colours_by_option=colours_by_option,
        harmony_by_option=table.harmony,
        option_counts=[table.option_count(i) for i in range(len(slots))],
        bar_indices=[slot.bar_index for slot in slots],
        genre_key=base_settings.profile.key,
        generative=generative,
        tonic_pc=tonic_pc or 0,
        harmony_weights=harmony_weights,
        passing_rules=passing_rules,
    )

    def settings_for(choices: Sequence[int]) -> RunSettings:
        return context.settings_for(choices)

    settings = settings_for([0] * len(slots))
    if not table.is_usable:
        return GAResult(
            solutions=[],
            generations_run=0,
            evaluated=0,
            seeded=0,
            message=table.describe_problems(slots),
        )

    evaluated = 0

    def score(chromosome: Chromosome) -> Chromosome:
        nonlocal evaluated
        breakdown = context.score(chromosome.slots, chromosome.choices,
                                  chromosome.passing)
        chromosome.cost = breakdown.total
        chromosome.breakdown = breakdown
        evaluated += 1
        return chromosome

    # --- seeding -----------------------------------------------------------
    population: List[Chromosome] = []
    seed_attempts = config.population_size * 12
    while len(population) < config.population_size and seed_attempts > 0:
        seed_attempts -= 1
        candidate = _seed_chromosome(
            table, settings, rng, slots=slots,
            modulation_settings=(harmony_weights.modulation
                                 if harmony_weights is not None else None))
        if candidate is None:
            continue
        if passing_rules is not None:
            _seed_passing(candidate, passing_rules, scale_pcs, rng,
                          lambda i: slots[i].bar_index)
        score(candidate)
        if candidate.cost < INFINITE_COST:
            population.append(candidate)

    if not population:
        diagnosis = diagnose_impossible_slots(slots, settings)
        if diagnosis:
            return GAResult(
                solutions=[], generations_run=0, evaluated=evaluated, seeded=0,
                message=" ".join(diagnosis),
            )
        return GAResult(
            solutions=[],
            generations_run=0,
            evaluated=evaluated,
            seeded=0,
            message=(
                "Con las reglas prendidas no hay ninguna forma de escribir esta "
                "progresión. Probá aflojando alguna regla o ampliando el "
                "registro de las voces."
            ),
        )

    seeded = len(population)
    # Top up a short population by cloning, so selection pressure still works.
    while len(population) < config.population_size:
        clone = rng.choice(population).copy()
        _mutate(clone, table, config, rng, passing_rules, scale_pcs,
                [slot.bar_index for slot in slots], base_settings)
        score(clone)
        population.append(clone)

    # --- hall of fame ------------------------------------------------------
    # Distinct solutions are collected across the whole run rather than read
    # off the final population, where elitism tends to leave near-identical
    # copies of one winner.
    hall: Dict[Tuple[int, ...], Chromosome] = {}

    def remember(chromosome: Chromosome) -> None:
        if chromosome.cost >= INFINITE_COST:
            return
        signature = chromosome.signature()
        if signature not in hall or chromosome.cost < hall[signature].cost:
            hall[signature] = chromosome.copy()
            hall[signature].cost = chromosome.cost
            hall[signature].breakdown = chromosome.breakdown

    for chromosome in population:
        remember(chromosome)

    best_cost = min(c.cost for c in population)
    stagnant = 0
    generations_run = 0

    # Parallel scoring, sized to the machine this is actually running on.
    worker_count = resolve_worker_count(
        config.workers, config.population_size * max(1, len(slots))
    )
    pool = None
    if worker_count > 1:
        import multiprocessing as mp
        try:
            pool = mp.Pool(
                worker_count, initializer=_init_worker, initargs=(context,)
            )
        except (OSError, ValueError):
            # Some frozen/sandboxed environments cannot fork; falling back to
            # a single process is slower but always works.
            pool = None

    try:
      for generation in range(config.generations):
          generations_run = generation + 1
          population.sort(key=lambda c: c.cost)
          next_population: List[Chromosome] = [c.copy() for c in population[: config.elitism]]
          for elite, source in zip(next_population, population[: config.elitism]):
              elite.cost = source.cost
              elite.breakdown = source.breakdown

          # Los hijos se despachan **a medida que nacen**, no cuando están
          # todos. Criar cuesta más que puntuar --- medido sobre dieciséis
          # acordes con ocho procesos, 4,8 s de cruce y mutación contra 2,8 s
          # de evaluación --- así que juntar los doscientos antes de mandar
          # el primero dejaba a los ocho procesos de brazos cruzados durante
          # la mitad de cada generación. Ahora la primera tanda sale con
          # veinticinco hijos hechos y el padre sigue criando mientras se
          # puntúa.
          #
          # El orden de cría no cambia ni por un llamado: los mismos torneos,
          # los mismos cruces y las mismas mutaciones en la misma secuencia,
          # así que el generador de azar entrega exactamente lo mismo y la
          # corrida sale idéntica --- no parecida. Lo único que se movió es
          # cuándo cruza cada tanda el límite entre procesos.
          candidates: List[Chromosome] = []
          pending = []
          batch: List[Tuple] = []
          # Las opciones de acorde y los adornos viajan con las alturas: sin
          # ellos el worker puntuaba otra cosa.
          batch_size = max(
              1, -(-config.population_size // max(1, worker_count)))
          guard = config.population_size * 8
          while len(candidates) < config.population_size and guard > 0:
              guard -= 1
              parent_a = _tournament(population, config.tournament_size, rng)
              parent_b = _tournament(population, config.tournament_size, rng)
              child = _crossover(parent_a, parent_b, rng, config)
              _mutate(child, table, config, rng, passing_rules, scale_pcs,
                    [slot.bar_index for slot in slots], base_settings)
              candidates.append(child)
              if pool is not None:
                  batch.append((child.slots, child.choices, child.passing))
                  if len(batch) >= batch_size:
                      pending.append(pool.apply_async(_evaluate_batch, (batch,)))
                      batch = []

          if pool is not None and candidates:
              if batch:
                  pending.append(pool.apply_async(_evaluate_batch, (batch,)))
              costs: List[float] = []
              for handle in pending:
                  costs.extend(handle.get())
              for child, cost in zip(candidates, costs):
                  child.cost = cost
              evaluated += len(candidates)
          else:
              for child in candidates:
                  score(child)

          for child in candidates:
              if len(next_population) >= config.population_size:
                  break
              if child.cost < INFINITE_COST:
                  next_population.append(child)
                  remember(child)

          # If mutation kept producing invalid children, refill from the elites
          # so the population never collapses.
          #
          # El clon es una copia exacta y sin mutar, así que su costo es el
          # del elite del que salió: `Chromosome.copy` ya lo trae y volver a
          # puntuarlo era recalcular un número que ya estaba. No es un ahorro
          # de borde --- con las reglas duras prendidas la mayoría de los
          # hijos sale inválida y este relleno se lleva unas 134 de las 200
          # plazas por generación: medido, 40.000 de las 100.720 evaluaciones
          # de una corrida, todas seriales en el proceso padre mientras los
          # ocho del pool esperaban. Un solo cromosoma se puntuó 7.654 veces.
          #
          # Lo único que falta copiar es el desglose, que `copy` no arrastra.
          # El sorteo se hace igual que antes para no correr el generador de
          # azar: la corrida tiene que salir idéntica, no parecida.
          while len(next_population) < config.population_size:
              source = rng.choice(next_population[: max(1, config.elitism)])
              clone = source.copy()
              clone.breakdown = source.breakdown
              next_population.append(clone)

          population = next_population
          generation_best = min(c.cost for c in population)
          if generation_best < best_cost - 1e-9:
              best_cost = generation_best
              stagnant = 0
          else:
              stagnant += 1

          if progress is not None:
              progress(generations_run, best_cost)

          if stagnant >= config.stagnation_limit:
              break

    finally:
        if pool is not None:
            pool.close()
            pool.join()

    ranked = sorted(hall.values(), key=lambda c: c.cost)
    solutions = _pick_diverse(ranked, solutions_wanted, generative)
    return GAResult(
        solutions=solutions,
        generations_run=generations_run,
        evaluated=evaluated,
        seeded=seeded,
    )


def _pick_diverse(
    ranked: Sequence[Chromosome],
    wanted: int,
    generative: bool = False,
) -> List[Chromosome]:
    """
    Choose the best solutions while keeping them genuinely different.

    Returning the top three by cost alone hands back the same answer with a
    note nudged, which is useless when the point is to offer a real choice.

    When the search also picked the chords, "different" has to mean a
    different *progression*. Measuring only the pitches let all three
    winners share one chord sequence and differ in voicing, so the user saw
    the same harmony three times over. Progressions are separated first, and
    only if that cannot fill the quota do we fall back to voicing
    differences.
    """
    if not ranked:
        return []

    chosen: List[Chromosome] = [ranked[0]]

    if generative:
        # Two chords apart already reads as a different progression, and
        # asking for more forces the search to hand back distant, much worse
        # alternatives just to satisfy the threshold.
        for min_chords in (2, 1):
            for candidate in ranked[1:]:
                if len(chosen) >= wanted:
                    break
                if all(_chord_difference(candidate, other) >= min_chords
                       for other in chosen):
                    chosen.append(candidate)
            if len(chosen) >= wanted:
                return chosen[:wanted]

    for min_differences in (4, 2, 1, 0):
        for candidate in ranked[1:]:
            if len(chosen) >= wanted:
                break
            if candidate in chosen:
                continue
            if all(_difference(candidate, other) >= min_differences for other in chosen):
                chosen.append(candidate)
        if len(chosen) >= wanted:
            break
    return chosen[:wanted]


def _chord_difference(a: Chromosome, b: Chromosome) -> int:
    """How many slots hold a different chord in two candidates."""
    return sum(1 for x, y in zip(a.choices, b.choices) if x != y)


def _difference(a: Chromosome, b: Chromosome) -> int:
    """Number of positions where two chromosomes assign different pitches."""
    return sum(
        1
        for slot_a, slot_b in zip(a.slots, b.slots)
        for pitch_a, pitch_b in zip(slot_a, slot_b)
        if pitch_a != pitch_b
    )
