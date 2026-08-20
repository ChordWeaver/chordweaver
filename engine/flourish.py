# -*- coding: utf-8 -*-
"""
Flourishes applied to the winner, after the search is over.

Everything here runs on the single best chromosome once the genetic
algorithm has finished. That is deliberate: these are period gestures, not
optimisation targets, and trying to teach the fitness function to want them
meant fighting it -- the plain voicing is always cheaper in raw motion, so a
flourish could only win by being paid for, and paying for it distorted
everything else.

Doing it afterwards makes each one a small, verifiable edit to a solution
that is already good, instead of a pressure on the search.

Two kinds of thing live here:

* **Edits** -- the sixth that sidesteps a parallel fifth actually changes
  notes.
* **Marks** -- a ii-V, a plagal cadence, a cadential six-four: these are
  recognised in what the search already produced and only labelled, so the
  interface can point them out.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from .harmony import DOMINANT, SUBDOMINANT, TONIC, function_of
from .style import ChordContext, cadential_six_four

#: Chance that the winning chromosome gets the sixth treatment at all.
#: High on purpose: the gesture is one of the things the baroque
#: setting is *for*, and at 0.10 most pieces never showed it, so the
#: feature was invisible to anyone not generating dozens of them.
SIXTH_CHANCE = 0.80


@dataclass
class Mark:
    """Something worth pointing out in a finished solution.

    ``slots`` are the chord positions to highlight; ``label`` names the
    device and ``detail`` explains it in one line.
    """

    key: str
    label: str
    detail: str
    slots: Tuple[int, ...]


@dataclass
class FlourishResult:
    """What the post-processing did and found."""

    marks: List[Mark] = field(default_factory=list)
    #: Slot whose chord was rewritten as a sixth, if that happened.
    sixth_slot: Optional[int] = None
    #: Slot forced into the voicing that would have made parallel fifths.
    forced_slot: Optional[int] = None
    #: How the rewritten chord should be labelled.
    sixth_symbol: str = ""

    #: Marks found in each solution, keyed by its position in the results.
    by_solution: Dict[int, List[Mark]] = field(default_factory=dict)

    def marks_for(self, slot_index: int, solution: int = 0) -> List[Mark]:
        found = self.by_solution.get(solution, self.marks if solution == 0 else [])
        return [m for m in found if slot_index in m.slots]

    def labels_for(self, solution: int) -> List[Mark]:
        """
        Distinct devices in one solution, for the banner above it.

        Repeated occurrences of one device are reported on a single line, but
        their slots are merged rather than dropped, so the banner can say
        which chords each device covers. Without that a piece holding both a
        plain and a minor plagal listed two nameless lines over four chords
        tinted identically, and the darker label read as though it covered
        the plain cadence too.
        """
        found = self.by_solution.get(solution, [])
        order: List[str] = []
        merged: Dict[str, Mark] = {}
        for mark in found:
            previous = merged.get(mark.label)
            if previous is None:
                merged[mark.label] = mark
                order.append(mark.label)
                continue
            # A new object: the stored marks are what `marks_for` reads
            # per chord, and those must keep their own slots.
            merged[mark.label] = replace(
                previous,
                slots=tuple(sorted(set(previous.slots) | set(mark.slots))),
            )
        return [merged[label] for label in order]


# ---------------------------------------------------------------------------
# The sixth that sidesteps a parallel fifth
# ---------------------------------------------------------------------------

def _doubles_octave_only(pitches: Sequence[int]) -> bool:
    """
    True when the only doubling in this chord is at the octave.

    With more than three voices the trick only makes sense if the spare
    voice is doubling the root: if it is doubling the fifth, replacing one
    copy still leaves the other, the parallel survives, and the edit
    achieves nothing.
    """
    classes = [p % 12 for p in pitches]
    doubled = {pc for pc in classes if classes.count(pc) > 1}
    if len(doubled) != 1:
        return False
    # The doubled tone must be the bass note, i.e. an octave doubling.
    return next(iter(doubled)) == pitches[0] % 12


def eligible_sixth_slots(
    chords: Sequence[Sequence[int]],
    locked: Sequence[bool],
    voice_count: int,
) -> List[int]:
    """
    Slots that could take the sixth.

    Never the first or the last -- those are the points of repose -- never a
    padlocked chord, and with four or more voices only where the doubling is
    at the octave.
    """
    if len(chords) < 4 or voice_count not in (3, 4):
        return []

    candidates = []
    for index in range(1, len(chords) - 1):
        if index < len(locked) and locked[index]:
            continue
        if voice_count > 3 and not _doubles_octave_only(chords[index]):
            continue
        candidates.append(index)
    return candidates


def apply_sixth(
    chords: List[List[int]],
    locked: Sequence[bool],
    voice_count: int,
    rng: random.Random,
) -> Optional[Tuple[int, int]]:
    """
    Rewrite one chord as a sixth and force its neighbour into parallel fifths.

    The point of the gesture is that the two chords *would* have made
    parallel fifths, and the sixth is what saves them -- so the neighbour is
    deliberately moved into the voicing that would have collided. Returns
    (sixth slot, forced neighbour) or None when nothing suitable was found.

    Edits ``chords`` in place. Returns the sixth's slot, the forced
    neighbour, and which voice carries the sixth.
    """
    options = eligible_sixth_slots(chords, locked, voice_count)
    if not options:
        return None

    rng.shuffle(options)
    for slot in options:
        # The neighbour has to be available too: not an endpoint, not locked.
        neighbours = [n for n in (slot - 1, slot + 1)
                      if 0 < n < len(chords) - 1
                      and not (n < len(locked) and locked[n])]
        if not neighbours:
            continue
        neighbour = rng.choice(neighbours)

        chord = chords[slot]
        bass = chord[0]
        # Which voice carries the fifth: that is the one that becomes a sixth.
        fifth_voice = next(
            (v for v in range(1, len(chord)) if (chord[v] - bass) % 12 == 7),
            None,
        )
        if fifth_voice is None:
            continue

        sixth = chord[fifth_voice] + 2          # a whole tone up from the fifth
        moved = list(chord)
        moved[fifth_voice] = sixth
        if moved != sorted(moved):
            continue

        # The neighbour is REARRANGED, never rewritten: the same notes it
        # already had, moved between voices so that voice ends up a fifth
        # above the bass. Replacing a pitch outright dropped a chord tone and
        # left the chord incomplete.
        other = list(chords[neighbour])
        wanted_pc = (other[0] + 7) % 12
        holder = next((v for v in range(1, len(other))
                       if other[v] % 12 == wanted_pc), None)
        if holder is None or holder == fifth_voice:
            # No voice is carrying that fifth, so there is nothing to swap
            # into place. Leaving the neighbour alone is fine: the sixth
            # still stands on its own as a colour, it simply is not
            # dramatising an avoided parallel.
            chords[slot] = moved
            return slot, slot, fifth_voice
        forced = list(other)
        forced[fifth_voice], forced[holder] = forced[holder], forced[fifth_voice]
        if forced != sorted(forced) or set(forced) != set(other):
            continue

        chords[slot] = moved
        chords[neighbour] = forced
        return slot, neighbour, fifth_voice
    return None


def sixth_symbol(base_symbol: str) -> str:
    """
    How a chord reads once its fifth has become a sixth.

    Printed explicitly because the chord genuinely changed: it is no longer
    the triad the user asked for, and calling it one would hide the edit.
    """
    return f"{base_symbol}6omit5"


# ---------------------------------------------------------------------------
# Marks: devices recognised in what the search produced
# ---------------------------------------------------------------------------

def _resolves(previous, current, tonic_pc: int) -> bool:
    """True when a dominant falls a fifth to where it points."""
    return (current.root_pc - previous.root_pc) % 12 == 5


def find_marks(
    options: Sequence,
    chords: Sequence[Sequence[int]],
    genre_key: str,
    tonic_pc: int,
    contexts: Optional[Sequence] = None,
) -> List[Mark]:
    """
    Recognise idiomatic gestures in a finished progression.

    Nothing here changes a note: these are labels for things the search
    already chose, so the interface can point out what came out well.

    ``options`` son las opciones armónicas elegidas, que traen la cifra
    romana; el Organizador no elige acordes ---los escribe el usuario--- así
    que ahí vienen en None y todo lo que se reconoce por grado queda afuera.
    ``contexts`` es el acorde de cada lugar visto en clases de altura, que
    sí existe siempre: alcanza para el 6/4, que se puede reconocer sin saber
    en qué tonalidad estamos.
    """
    marks: List[Mark] = []
    if not options:
        return marks
    if any(o is None for o in options):
        return _six_four_marks(options, chords, contexts)

    for index in range(1, len(options)):
        previous, current = options[index - 1], options[index]
        previous_function = function_of(previous)
        current_function = function_of(current)

        if genre_key == "jazz":
            # ii-V-I literally: the second degree, the fifth, the tonic.
            # Matching by function counted iv-bVII-I and every other
            # subdominant-dominant pair as the same thing, which is not what
            # the name means.
            before = options[index - 2] if index >= 2 else None
            secondary = (before is not None
                         and previous.roman.startswith("V/")
                         and (previous.root_pc - before.root_pc) % 12 == 5
                         and (current.root_pc - previous.root_pc) % 12 == 5)
            if secondary:
                marks.append(Mark(
                    "secondary_two_five", f"ii-V hacia {current.roman}",
                    "El mismo giro de siempre, pero apuntado a otro grado: "
                    "toma prestada la dominante de donde va y aterriza ahí.",
                    (index - 2, index - 1, index),
                ))
            if (index >= 2
                    and options[index - 2].roman == "ii"
                    and previous.roman == "V"
                    and current.roman in ("I", "i")):
                marks.append(Mark(
                    "two_five", "ii-V-I",
                    "El giro que sostiene casi todo el repertorio: la "
                    "subdominante prepara la dominante y ésta resuelve.",
                    (index - 2, index - 1, index),
                ))
            # The tritone substitute, resolving down a semitone as the
            # dominant it stands in for would have.
            if (previous.roman in ("subV", "bII")
                    and (current.root_pc - previous.root_pc) % 12 == 11):
                marks.append(Mark(
                    "tritone_sub", "Sustituto tritonal",
                    "Un dominante a un semitono por encima reemplaza al V y "
                    "resuelve deslizándose hacia abajo.",
                    (index - 1, index),
                ))

        if genre_key == "gregorian":
            # IV-I and iv-I, by name: any subdominant landing on the tonic is
            # not a plagal cadence, only the fourth degree is.
            if previous.roman in ("IV", "iv") and current.roman in ("I", "i"):
                minor = previous.roman == "iv"
                marks.append(Mark(
                    "plagal_minor" if minor else "plagal",
                    "Cadencia plagal menor" if minor else "Cadencia plagal",
                    ("La subdominante menor cierra sobre la tónica: el mismo "
                     "gesto que el plagal mayor, más oscuro."
                     if minor else
                     "La subdominante cierra directamente sobre la tónica, "
                     "sin pasar por la dominante."),
                    (index - 1, index),
                ))

        # The deceptive cadence proper: V going to vi (or VI in minor).
        # Any dominant failing to resolve is simply an unresolved dominant;
        # the cadence has a specific destination.
        if previous.roman == "V" and current.roman in ("vi", "VI"):
            marks.append(Mark(
                "deceptive", "Cadencia rota",
                "El V prepara la tónica y cae en el sexto grado: la "
                "resolución se posterga y la frase sigue.",
                (index - 1, index),
            ))

    marks.extend(_six_four_marks(options, chords, contexts))
    return marks


def _context_at(options, contexts, index: int):
    """
    El acorde de un lugar, visto como clases de altura y con su cifra.

    Se arma de la opción armónica cuando la hay ---así viaja la cifra
    romana--- y del contexto que pasó quien llamó cuando no. Los dos caminos
    devuelven lo mismo, que es lo que le permite al 6/4 reconocerse igual en
    los tres modos.
    """
    option = options[index] if index < len(options) else None
    if option is not None and getattr(option, "chord", None) is not None:
        return ChordContext.from_chord(option.chord, getattr(option, "roman", None))
    if contexts and index < len(contexts):
        return contexts[index]
    return None


def _six_four_marks(options, chords, contexts=None) -> List[Mark]:
    """
    Find a cadential six-four: a major V with its fifth in the bass.

    Sólo donde la dominante resuelve a donde apunta ---en el Generador y el
    Armonizador se pregunta por la cifra, en el Organizador por el intervalo,
    que es lo único que hay cuando el usuario escribió los cifrados a
    mano--- y sólo si está dispuesta 5-1-3. Con la tercera en el medio los
    intervalos sobre el bajo son los mismos y el chequeo viejo la daba por
    buena: lo que salía marcado como 6/4 era la otra disposición la mitad de
    las veces.

    Se reconoce con cualquier cantidad de voces. Estaba limitado a tres, que
    es una manera de no verlo nunca: el barroco se canta a cuatro.
    """
    marks: List[Mark] = []
    for index, chord in enumerate(chords):
        if index + 1 >= len(chords):
            continue
        context = _context_at(options, contexts, index)
        following = _context_at(options, contexts, index + 1)
        if not cadential_six_four(chord, context, following):
            continue
        marks.append(Mark(
            "six_four", "Cadencial 6/4",
            "El V con su quinta en el bajo, la fundamental encima y la "
            "tercera arriba: la fórmula que anuncia la cadencia y retrasa "
            "un momento la resolución.",
            (index,),
        ))
    return marks
