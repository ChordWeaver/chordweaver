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

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

#: Widest step either leg of the ornament may take. A passing note does not
#: have to sit *between* the two chord tones: rising a tone and falling two
#: before settling is ordinary melodic motion, and restricting the note to
#: the space between the endpoints ruled out most of what singers actually
#: do. What matters is that both legs stay singable.
MAX_LEG = 4


@dataclass
class PassingRules:
    """When passing tones may appear and what they are worth."""

    #: Indices of the voices allowed to take a passing tone. Empty disables
    #: the feature entirely.
    voices: Tuple[int, ...] = ()
    #: Reward for an ornament whose two legs are both steps.
    reward: float = -18.0
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

    def allows_bar(self, bar_index: int) -> bool:
        return not self.bars or bar_index in self.bars
    #: Cost per passing tone beyond `max_per_piece`, so the texture does not
    #: turn into a scale exercise.
    crowding: float = 30.0
    max_per_piece: int = 4
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
        active = [v for v, note in enumerate(passing[index]) if note is not None]
        if len(active) > 1:
            # Only one voice decorates at a time.
            total += rules.simultaneous * (len(active) - 1)

        for voice, note in enumerate(passing[index]):
            if note is None:
                continue
            used += 1
            start, end = previous[voice], current[voice]
            first_leg = abs(note - start)
            second_leg = abs(end - note)

            if note == start or note == end:
                total += rules.repeated_note
            elif first_leg <= 2 and second_leg <= 2:
                total += rules.reward          # both legs are steps
            elif first_leg <= rules.max_leg and second_leg <= rules.max_leg:
                total += rules.reward * 0.4    # singable, if less smooth
            else:
                total += rules.clumsy

    if used > rules.max_per_piece:
        total += rules.crowding * (used - rules.max_per_piece)
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
        active = [
            (voice, note) for voice, note in enumerate(notes) if note is not None
        ] if notes else []

        if not active:
            out_pitches.append(list(chord))
            out_durations.append(duration)
            out_is_passing.append(False)
            continue

        head = duration * (1.0 - share)
        tail = duration - head
        out_pitches.append(list(chord))
        out_durations.append(head)
        out_is_passing.append(False)

        moved = list(chord)
        for voice, note in active:
            moved[voice] = note
        out_pitches.append(moved)
        out_durations.append(tail)
        out_is_passing.append(True)

    return out_pitches, out_durations, out_is_passing
