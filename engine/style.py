# -*- coding: utf-8 -*-
"""
Genre-idiomatic counterpoint rules.

The base fitness function rewards small movement. This module adds the
*stylistic* half: the rules each tradition actually follows, so a classical
setting behaves like species counterpoint and a jazz setting behaves like
guide-tone voice leading, rather than all four genres producing the same
minimal-motion result with different weights.

Sources consulted (summarised, not quoted):

* Species counterpoint (Fux/Palestrina practice): stepwise motion preferred,
  melodic tritones and sevenths forbidden, a leap should be answered by
  motion in the opposite direction, parallel perfect consonances forbidden,
  perfect intervals approached by contrary or oblique motion.
* Bach chorale part-writing: never double the leading tone; a chord seventh
  resolves down by step and the leading tone resolves up to the tonic;
  soprano-alto and alto-tenor stay within an octave while tenor-bass may
  span two; voices must not overlap between adjacent chords; keep common
  tones and move each voice to the nearest chord tone; each voice should sit
  near the middle of its range rather than at the extremes.
* Modal/organum practice: motion overwhelmingly by step, the tritone treated
  as the diabolus in musica, perfect consonances idiomatic (parallel motion
  in fifths and octaves is the point of organum), narrow melodic range.
* Jazz voice leading: the guide tones (third and seventh) carry the harmony
  and should move by step between chords; sevenths resolve down; keep common
  tones; avoid a minor ninth between two upper voices, which is the standard
  "avoid note" test.

Everything here is a *weighted* term. Hard constraints stay in
``fitness.evaluate`` so the user keeps a single, predictable set of switches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from .theory import (
    Chord,
    ROLE_EXTENSION,
    ROLE_FIFTH,
    ROLE_ROOT,
    ROLE_SEVENTH,
    ROLE_THIRD,
)

OCTAVE = 12
TRITONE = 6
MINOR_NINTH = 13


@dataclass
class ChordContext:
    """Harmonic facts about one chord slot, precomputed for the evaluator.

    Working in pitch classes keeps the checks cheap: every rule below is a
    membership test or a small interval comparison, run once per chord and
    once per transition rather than re-deriving chord theory in the hot loop.
    """

    root_pc: int
    third_pc: Optional[int] = None
    seventh_pc: Optional[int] = None
    fifth_pc: Optional[int] = None
    tension_pcs: Set[int] = field(default_factory=set)
    #: True for a dominant-seventh sonority (major third plus minor seventh),
    #: whose third behaves as a leading tone and whose seventh wants to fall.
    is_dominant: bool = False
    #: Pitch class the user pinned to the bass, for a slash chord such as
    #: C/E. None means the bass is free, and the root is what belongs there.
    bass_pc: Optional[int] = None
    #: Cifra romana del acorde dentro de su tonalidad ---"V", "vi", "V/ii"---
    #: cuando quien armó el contexto la sabía. En el Organizador el usuario
    #: escribe cifrados y no declara ninguna tonalidad, así que ahí es None y
    #: las reglas que la miran tienen que arreglárselas sin ella.
    roman: Optional[str] = None

    @property
    def guide_tone_pcs(self) -> Set[int]:
        """Third and seventh: the tones that define the chord's quality."""
        return {pc for pc in (self.third_pc, self.seventh_pc) if pc is not None}

    @property
    def leading_tone_pc(self) -> Optional[int]:
        """The tone that wants to rise by a semitone, if this chord has one."""
        return self.third_pc if self.is_dominant else None

    @classmethod
    def from_chord(cls, chord: Chord, roman: Optional[str] = None) -> "ChordContext":
        third = seventh = fifth = None
        tensions: Set[int] = set()
        third_semitones = seventh_semitones = None

        for tone in chord.tones:
            pc = chord.pitch_class_of(tone)
            if tone.role == ROLE_THIRD:
                third, third_semitones = pc, tone.semitones
            elif tone.role == ROLE_SEVENTH:
                seventh, seventh_semitones = pc, tone.semitones
            elif tone.role == ROLE_FIFTH:
                fifth = pc
            elif tone.role == ROLE_EXTENSION:
                tensions.add(pc)

        is_dominant = third_semitones == 4 and seventh_semitones == 10
        return cls(
            root_pc=chord.root_pc,
            third_pc=third,
            seventh_pc=seventh,
            fifth_pc=fifth,
            tension_pcs=tensions,
            is_dominant=is_dominant,
            bass_pc=chord.bass_pc,
            roman=roman,
        )


# ---------------------------------------------------------------------------
# Per-chord rules
# ---------------------------------------------------------------------------

def doubling_penalty(
    pitches: Sequence[int],
    context: ChordContext,
    third_weight: float,
    leading_tone_weight: float,
    seventh_weight: float,
) -> float:
    """
    Score how the chord is doubled.

    Chorale practice doubles roots and fifths freely, doubles thirds only
    reluctantly, and never doubles the leading tone -- two leading tones
    resolving to the tonic produce parallel octaves no matter how they are
    voiced. Doubling a chord seventh is equally unwelcome because both copies
    then have to resolve downwards.
    """
    counts: Dict[int, int] = {}
    for pitch in pitches:
        pc = pitch % 12
        counts[pc] = counts.get(pc, 0) + 1

    cost = 0.0
    leading = context.leading_tone_pc
    if leading is not None and counts.get(leading, 0) > 1:
        cost += leading_tone_weight * (counts[leading] - 1)
    elif context.third_pc is not None and counts.get(context.third_pc, 0) > 1:
        cost += third_weight * (counts[context.third_pc] - 1)

    if context.seventh_pc is not None and counts.get(context.seventh_pc, 0) > 1:
        cost += seventh_weight * (counts[context.seventh_pc] - 1)
    return cost


def minor_ninth_penalty(pitches: Sequence[int], context: ChordContext, weight: float) -> float:
    """
    Penalise minor ninths between voices -- the jazz "avoid note" test.

    A tension sitting a semitone above a chord tone an octave below sounds
    harsh; arrangers either drop the tension or replace it (the 11th on a
    major seventh becomes a #11 for exactly this reason). The interval is
    tolerated above the root, where it is the characteristic b9 colour.
    """
    if not weight:
        return 0.0
    cost = 0.0
    for i in range(len(pitches)):
        for j in range(i + 1, len(pitches)):
            interval = pitches[j] - pitches[i]
            if interval == MINOR_NINTH and pitches[i] % 12 != context.root_pc:
                cost += weight
    return cost


def harmonic_dissonance_penalty(pitches: Sequence[int], weight: float) -> float:
    """
    Penalise seconds and sevenths between voices.

    Modal writing treats these as dissonances to be prepared and resolved;
    since this engine writes block chords with no passing motion, the honest
    approximation is simply to discourage them.
    """
    if not weight:
        return 0.0
    cost = 0.0
    for i in range(len(pitches)):
        for j in range(i + 1, len(pitches)):
            interval = (pitches[j] - pitches[i]) % OCTAVE
            if interval in (1, 2, 10, 11):
                cost += weight
    return cost


# ---------------------------------------------------------------------------
# El 6/4 cadencial
# ---------------------------------------------------------------------------
#
# Se define acá, y no en `fitness` ni en `flourish`, porque los dos lo
# necesitan y tienen que preguntar por lo mismo: el evaluador para que la
# búsqueda lo prefiera, y el post-proceso para poder señalarlo en la
# pantalla. Cuando cada uno tenía su propia idea de qué era un 6/4, lo que
# salía marcado no era lo que se había buscado.

def six_four_arrangement(pitches: Sequence[int], context: ChordContext) -> bool:
    """
    True cuando el acorde está dispuesto **5 - 1 - 3** desde el bajo.

    Un 6/4 no es cualquier acorde con la quinta abajo: es la quinta en el
    bajo, la fundamental encima y la tercera arriba de todo, que es de donde
    salen la cuarta y la sexta que le dan el nombre. Con la tercera en el
    medio ---5-3-1--- los intervalos sobre el bajo son una sexta y una
    cuarta igual, así que un chequeo que sólo mire el conjunto de
    intervalos las da por iguales, y lo que salía marcado como 6/4 era la
    mitad de las veces la otra disposición.

    Las duplicaciones no molestan: lo que se mira es el orden en que
    aparecen las tres notas distintas de abajo hacia arriba, así que a
    cuatro voces un re-sol-si-re sigue siendo un 6/4.
    """
    if context.fifth_pc is None or context.third_pc is None:
        return False
    order = list(dict.fromkeys(pitch % OCTAVE for pitch in pitches))
    return order[:3] == [context.fifth_pc, context.root_pc, context.third_pc]


def is_cadential_dominant(
    context: Optional[ChordContext],
    following: Optional[ChordContext],
) -> bool:
    """
    True cuando este acorde es la dominante mayor del que viene después.

    Se pregunta por la cifra romana cuando quien armó el contexto la sabe
    ---el Generador y el Armonizador eligen los acordes, así que la
    saben--- y por el intervalo cuando no ---el Organizador, donde el
    usuario escribe cifrados sueltos y no hay ninguna tonalidad declarada:
    ahí lo único que se puede afirmar es que un acorde mayor cae de quinta
    sobre el siguiente, que es exactamente lo que se oye.
    """
    if context is None or following is None:
        return False
    if context.third_pc is None:
        return False
    # Mayor o de dominante: sobre un V menor no hay sensible y el gesto no
    # es el que la fórmula anuncia.
    if (context.third_pc - context.root_pc) % OCTAVE != 4:
        return False
    if context.roman is not None and following.roman is not None:
        return context.roman == "V" and following.roman in ("I", "i")
    return (following.root_pc - context.root_pc) % OCTAVE == 5


def cadential_six_four(
    pitches: Sequence[int],
    context: Optional[ChordContext],
    following: Optional[ChordContext],
) -> bool:
    """La dominante cantada 5-1-3 y resolviendo a donde apunta."""
    if not is_cadential_dominant(context, following):
        return False
    return six_four_arrangement(pitches, context)


# ---------------------------------------------------------------------------
# Per-transition rules
# ---------------------------------------------------------------------------

def voice_overlap_count(previous: Sequence[int], current: Sequence[int]) -> int:
    """
    Count voice overlaps between two adjacent chords.

    Overlap is subtler than crossing: no chord is out of order on its own,
    but a voice moves past where its neighbour just was, which blurs the
    independence of the lines. Chorale writing bars it alongside crossing.
    """
    overlaps = 0
    for i in range(len(current) - 1):
        if current[i] > previous[i + 1]:
            overlaps += 1
        if current[i + 1] < previous[i]:
            overlaps += 1
    return overlaps


def tendency_tone_penalty(
    previous: Sequence[int],
    current: Sequence[int],
    context: ChordContext,
    seventh_weight: float,
    leading_tone_weight: float,
) -> float:
    """
    Check that tendency tones of the *previous* chord resolve properly.

    The seventh of a chord should fall by a step; the leading tone of a
    dominant should rise a semitone. A voice holding a common tone is not
    penalised -- suspension over a repeated harmony is normal -- so only
    genuine movement in the wrong direction costs anything.
    """
    cost = 0.0
    for index, before in enumerate(previous):
        after = current[index]
        motion = after - before
        pc = before % 12

        if seventh_weight and context.seventh_pc is not None and pc == context.seventh_pc:
            # Resolve down by step; holding the note is acceptable.
            if motion != 0 and not (-2 <= motion < 0):
                cost += seventh_weight

        leading = context.leading_tone_pc
        if leading_tone_weight and leading is not None and pc == leading:
            if motion != 0 and motion != 1:
                cost += leading_tone_weight
    return cost


def guide_tone_reward(
    previous: Sequence[int],
    current: Sequence[int],
    previous_context: ChordContext,
    current_context: ChordContext,
    weight: float,
) -> float:
    """
    Reward guide tones that move by step (or stay put) between chords.

    This is the core of jazz voice leading: in circle-of-fifths motion the
    third and seventh of one chord become the seventh and third of the next,
    a semitone or tone away. Returning a negative cost makes the search
    actively seek those connections rather than merely tolerate them.
    """
    if not weight:
        return 0.0
    reward = 0.0
    previous_guides = previous_context.guide_tone_pcs
    current_guides = current_context.guide_tone_pcs
    for index, before in enumerate(previous):
        if before % 12 not in previous_guides:
            continue
        after = current[index]
        if after % 12 in current_guides and abs(after - before) <= 2:
            reward += weight       # weight is negative: a reward
    return reward


def common_tone_reward(previous: Sequence[int], current: Sequence[int], weight: float) -> float:
    """Reward voices that hold a pitch across a chord change."""
    if not weight:
        return 0.0
    return weight * sum(1 for i in range(len(current)) if current[i] == previous[i])


def leap_compensation_penalty(
    before_previous: Optional[Sequence[int]],
    previous: Sequence[int],
    current: Sequence[int],
    leap_threshold: int,
    weight: float,
) -> float:
    """
    Penalise a leap that is not answered by motion in the opposite direction.

    Counterpoint treatises are unanimous on this: after a large leap the line
    should turn back, otherwise the melody keeps climbing and loses shape.
    Needs three consecutive chords, so it is skipped at the start of a piece.
    """
    if not weight or before_previous is None:
        return 0.0
    cost = 0.0
    for index in range(len(current)):
        leap = previous[index] - before_previous[index]
        if abs(leap) < leap_threshold:
            continue
        answer = current[index] - previous[index]
        if answer == 0:
            continue
        if (leap > 0) == (answer > 0):
            cost += weight
    return cost


def bass_contrary_reward(previous: Sequence[int], current: Sequence[int], weight: float) -> float:
    """
    Reward upper voices moving against the bass.

    "Move to the nearest chord tone in contrary or oblique motion to the
    bass" is the single most repeated instruction in chorale part-writing,
    because similar motion in every voice turns four independent lines into
    one thickened melody.
    """
    if not weight:
        return 0.0
    bass_motion = current[0] - previous[0]
    if bass_motion == 0:
        return 0.0
    reward = 0.0
    for index in range(1, len(current)):
        motion = current[index] - previous[index]
        if motion == 0:
            continue
        if (motion > 0) != (bass_motion > 0):
            reward += weight       # negative weight = reward
    return reward


def melodic_interval_penalty(
    previous: Sequence[int],
    current: Sequence[int],
    forbidden_intervals: Sequence[int],
    max_leap: Optional[int],
    weight: float,
) -> float:
    """
    Penalise melodic intervals a style does not sing.

    Species counterpoint forbids melodic tritones and sevenths outright and
    keeps leaps small; modal writing is stricter still. Handled as a weighted
    term rather than a hard rule so the user's explicit switches stay the
    only things that can annul a chromosome.
    """
    if not weight:
        return 0.0
    cost = 0.0
    for index in range(len(current)):
        interval = abs(current[index] - previous[index])
        if interval in forbidden_intervals:
            cost += weight
        if max_leap is not None and interval > max_leap:
            cost += weight * (interval - max_leap)
    return cost


# ---------------------------------------------------------------------------
# Consonance at the points of repose
# ---------------------------------------------------------------------------

#: Intervals above the bass this rule counts as consonant, in semitones
#: reduced to one octave: unison/octave, minor and major third, perfect
#: fifth, minor and major sixth, and both sevenths.
#:
#: The perfect fourth is deliberately absent -- against the bass it is
#: treated as a dissonance requiring preparation, which is exactly why a 6/4
#: chord cannot end a phrase. Seconds and the tritone are absent for the
#: same reason.
#:
#: Sevenths are counted as consonant here even though strict thoroughbass
#: prepares and resolves them. The rule exists to judge how a chord is
#: *voiced*, and a seventh is part of the chord the user asked for: ending on
#: a Cmaj7 puts a seventh above the bass in every possible arrangement except
#: an inversion, so charging for it measured their choice of chord rather
#: than the algorithm's voicing of it.
CONSONANT_ABOVE_BASS = {0, 3, 4, 7, 8, 9, 10, 11}


def bass_consonance_violations(pitches: Sequence[int]) -> int:
    """
    Count upper voices forming a dissonance against the bass.

    Consonance in this idiom is measured from the bass upwards, not between
    neighbouring voices: in a 3-5-1 voicing the bass sings the third, so the
    interval to the fifth is a third and the interval to the root is a
    sixth, and both are consonant. The same notes stacked over a different
    bass would be judged differently, which is the whole point of figured
    bass.
    """
    if len(pitches) < 2:
        return 0
    bass = pitches[0]
    return sum(
        1 for pitch in pitches[1:]
        if (pitch - bass) % OCTAVE not in CONSONANT_ABOVE_BASS
    )


def adjacent_semitone_clashes(pitches: Sequence[int]) -> int:
    """
    Count pairs of neighbouring voices a semitone apart.

    Es lo que la medida contra el bajo no puede ver, y es justo lo que se
    escucha. Sobre un Cmaj7 escrito 3-5-7-1 --- mi, sol, si, do --- los tres
    intervalos contra el bajo son una tercera, una quinta y una sexta, todos
    consonantes, así que la cuenta de arriba devuelve cero. Pero el si y el
    do quedan pegados, a un semitono, y en un acorde donde el oído se
    apoya eso raspa: la forma que no raspa es 1-3-5-7, con la séptima arriba
    de todo y ninguna nota encima suya.

    Se mide entre voces **vecinas** y no entre todas: una séptima entre el
    bajo y la soprano es el acorde, no un choque. Y se mira el intervalo
    real, no su clase, porque una novena menor ---las mismas dos notas a una
    octava de distancia--- es exactamente lo que resuelve el problema.
    """
    if len(pitches) < 2:
        return 0
    return sum(1 for lower, upper in zip(pitches, pitches[1:])
               if abs(upper - lower) == 1)


def repose_dissonances(pitches: Sequence[int]) -> int:
    """
    Todo lo que hace áspero un acorde de reposo: contra el bajo y entre vecinas.

    Las dos cuentas van juntas porque las dos responden la misma pregunta
    ---¿este acorde se puede usar para terminar?--- y separarlas dejaba
    pasar por consonante el voicing que el usuario escucha como disonante.
    """
    return bass_consonance_violations(pitches) + adjacent_semitone_clashes(pitches)


def root_position_penalty(
    pitches: Sequence[int],
    context: Optional[ChordContext],
    weight: float,
) -> float:
    """
    Charge a chord of repose that is not sung in root position.

    Measuring consonance from the bass alone cannot tell root position from
    first inversion: over the third of a Cmaj7 the remaining voices form a
    third, a fifth and a sixth, all consonant, so 3-5-7-1 scored exactly as
    well as 1-3-5-7 and then won on movement, being the more compact of the
    two. A piece is expected to begin and end on its root, so the root
    belongs in the bass and an inversion has to cost something.

    Three cases are exempt. Below four voices the rule does not apply at all:
    a three-part setting has no spare voice, and its best answer is the
    first-inversion 3-5-1, where the fifth and the octave sit over the third
    rather than the third and fifth crowding above the root. A slash chord
    names its own bass, and charging for it would fight the user who typed
    it. And a rootless voicing has no root to put down there, which is a
    decision the omission pass already made.
    """
    if not weight or context is None or len(pitches) < 4:
        return 0.0
    expected = context.bass_pc if context.bass_pc is not None else context.root_pc
    if expected is None:
        return 0.0
    if expected not in {pitch % 12 for pitch in pitches}:
        return 0.0
    return 0.0 if pitches[0] % 12 == expected else weight


def melody_clash_penalty(
    pitches: Sequence[int],
    melody_voice: Optional[int],
    weight: float,
) -> float:
    """
    Charge a voice sounding a semitone away from the given melody note.

    Only for the harmonising mode, where one voice is a line the user wrote
    and the rest are arranged around it. A minor second against that note is
    the harshest thing the arrangement can do to it: the melody stops being
    heard as a melody and turns into the upper half of a clash.

    Measured on the sounding pitches rather than on pitch classes, and that
    distinction is the whole point. A B in the melody over a Cmaj7 *must*
    meet a C somewhere -- the chord requires it -- so charging the pitch
    class would be charging for the harmony the user already accepted. What
    the search does control is the register: put that C an octave down and
    the semitone becomes a seventh, which is the arrangement this is asking
    for. Minor ninths are left to :func:`minor_ninth_penalty`.
    """
    if not weight or melody_voice is None:
        return 0.0
    if not 0 <= melody_voice < len(pitches):
        return 0.0
    melody = pitches[melody_voice]
    return weight * sum(
        1 for index, pitch in enumerate(pitches)
        if index != melody_voice and abs(pitch - melody) == 1
    )


# ---------------------------------------------------------------------------
# Organum
# ---------------------------------------------------------------------------

#: The intervals organum is built on, reduced to one octave: unison/octave,
#: perfect fourth and perfect fifth. These are the distances the vox organalis
#: keeps below the vox principalis while it shadows it.
PERFECT_ORGANUM_INTERVALS = {0, 5, 7}


def organum_interval_reward(
    pitches: Sequence[int],
    principalis: Optional[int],
    weight: float,
) -> float:
    """
    Reward the vox organalis sitting a perfect interval below the principalis.

    The organalis is always the voice immediately below the chosen one, which
    is what makes the pair a pair: parallel organum doubles a chant at the
    fourth or the fifth, and the doubling voice is the one directly under it.

    Weight is negative in the profile, so this is a reward rather than a cost.
    """
    if not weight or principalis is None or principalis <= 0:
        return 0.0
    if principalis >= len(pitches):
        return 0.0
    interval = (pitches[principalis] - pitches[principalis - 1]) % OCTAVE
    return weight if interval in PERFECT_ORGANUM_INTERVALS else 0.0


def organum_parallel_reward(
    previous: Sequence[int],
    current: Sequence[int],
    principalis: Optional[int],
    weight: float,
) -> float:
    """
    Reward the organalis shadowing the principalis in parallel motion.

    Graded rather than all-or-nothing, because the harmony is not always able
    to offer an exact shadow: the two voices may only sing tones of the chord
    they are in, so a strict transposition is sometimes simply unavailable.
    Paying for the near misses as well is what makes the search reach for the
    gesture instead of giving up on it wherever it cannot be perfect.

    * both voices moving by the same number of semitones -- a true shadow --
      earns the whole reward;
    * moving the same way by different amounts earns rather more than half:
      the pair is still travelling together, which is what the ear takes for
      organum when the scale will not allow an exact transposition;
    * both holding still earns half: the pair is intact, it just is not
      moving.

    Nothing is paid unless the pair *lands* on a perfect interval, so the
    reward can never talk the search into parallel seconds.

    An earlier middle tier asked for the interval to be preserved as well as
    the direction. That is unreachable by arithmetic: if the reduced interval
    survives and both voices move, their steps can only differ by a whole
    octave. It never once fired.
    """
    if not weight or principalis is None or principalis <= 0:
        return 0.0
    if principalis >= len(current) or principalis >= len(previous):
        return 0.0

    organalis = principalis - 1
    arrived = (current[principalis] - current[organalis]) % OCTAVE
    if arrived not in PERFECT_ORGANUM_INTERVALS:
        return 0.0

    step_principalis = current[principalis] - previous[principalis]
    step_organalis = current[organalis] - previous[organalis]

    if step_principalis == step_organalis:
        return weight if step_principalis else weight * 0.5

    if (step_principalis and step_organalis
            and (step_principalis > 0) == (step_organalis > 0)):
        return weight * 0.55
    return 0.0


def _repose_positions(chords: Sequence[Sequence[int]]) -> List[int]:
    """The points of repose: the first chord, and the last when there is one."""
    return [0] if len(chords) == 1 else [0, len(chords) - 1]


def cadence_consonance_penalty(
    chords: Sequence[Sequence[int]],
    weight: float,
) -> float:
    """
    Charge for dissonance against the bass in the first and last chords.

    Only the outer chords are checked: those are the points of repose, where
    a listener expects the harmony to settle. Everything in between is free
    to be as dissonant as the style allows.
    """
    if not weight or not chords:
        return 0.0
    return weight * sum(
        repose_dissonances(chords[position])
        for position in _repose_positions(chords)
    )


def repose_root_position_penalty(
    chords: Sequence[Sequence[int]],
    contexts: Optional[Sequence[Optional[ChordContext]]],
    weight: float,
) -> float:
    """
    Charge the first and last chords for being sung inverted.

    Weighted separately from the dissonance count above, because the two
    need different scales: the jazz profile keeps its consonance weight
    deliberately gentle so a closing major seventh is not punished, and
    reusing that number left inversions costing far too little to matter.
    """
    if not weight or not chords or not contexts:
        return 0.0
    total = 0.0
    for position in _repose_positions(chords):
        context = contexts[position] if position < len(contexts) else None
        total += root_position_penalty(chords[position], context, weight)
    return total


def ambitus_penalty(
    chords: Sequence[Sequence[int]],
    max_span: int,
    weight: float,
) -> float:
    """
    Penalise a voice that roams over too wide a range across the piece.

    Chant and early modal polyphony keep each line inside a narrow ambitus --
    typically a sixth or so around the modal final. Minimal-motion scoring
    does not produce this on its own: a line can wander a long way while
    every individual step stays small, which is precisely what the audit
    showed happening.
    """
    if not weight or not chords:
        return 0.0
    cost = 0.0
    for voice in range(len(chords[0])):
        line = [chord[voice] for chord in chords]
        span = max(line) - min(line)
        if span > max_span:
            cost += weight * (span - max_span)
    return cost


def perfect_consonance_reward(pitches: Sequence[int], weight: float) -> float:
    """
    Reward perfect consonances against the bass.

    Organum and early modal practice are built on octaves, fifths and
    fourths; rewarding them is what makes the modal profile sound archaic
    rather than merely smooth. Returns a negative cost when ``weight`` is
    negative, as the profiles set it.
    """
    if not weight or len(pitches) < 2:
        return 0.0
    bass = pitches[0]
    return weight * sum(
        1 for pitch in pitches[1:] if (pitch - bass) % OCTAVE in (0, 5, 7)
    )
