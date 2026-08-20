# -*- coding: utf-8 -*-
"""
Contrapuntal audit.

The question this answers: does each genre profile actually produce writing
that follows its own tradition, or does every genre quietly converge on "the
solution with the least movement" wearing a different label?

Method
------
For a set of ordinary progressions we run each genre, then measure the
*output* against rules the fitness never sees as a single number: how much
motion is stepwise, how often voices move in contrary motion, whether
sevenths resolve down, whether guide tones connect by step, how many
parallel perfect intervals survive, and so on.

Then we compare each genre against a control: the same search with every
style weight switched off, which is pure minimal motion. If a genre's
measurements match the control, its style rules are decorative and the
project's premise fails. They should differ, and differ in the direction the
tradition predicts.

Run with:  python audit.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Sequence

from engine.fitness import GENRE_PROFILES, RunSettings
from engine.ga import ChordSlot, GAConfig, run
from engine.style import ChordContext, bass_consonance_violations, voice_overlap_count
from engine.theory import build_voice_parts, parse_chord
from engine.voicing import build_requirement

PROGRESSIONS = {
    "I-vi-IV-V (triads)": ["C", "Am", "F", "G", "C", "F", "G", "C"],
    "ii-V-I (sevenths)": ["Dm7", "G7", "Cmaj7", "Am7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
    "modal cycle": ["Dm", "C", "F", "C", "Dm", "Am", "Dm", "Dm"],
    "circle of fifths": ["Cmaj7", "A7", "Dm7", "G7", "Em7", "A7", "Dm7", "G7"],
}

SEEDS = [11, 23]


@dataclass
class Measurements:
    """Everything measured on a finished solution, as percentages or counts."""

    stepwise_share: float = 0.0
    contrary_share: float = 0.0
    common_tone_share: float = 0.0
    parallel_perfects: float = 0.0
    overlaps: float = 0.0
    leaps_over_fifth: float = 0.0
    sevenths_resolved: float = 0.0
    guide_tone_steps: float = 0.0
    cadence_dissonances: float = 0.0
    mean_motion: float = 0.0
    widest_spacing: float = 0.0
    perfect_above_bass: float = 0.0
    mean_ambitus: float = 0.0

    def as_row(self) -> List[float]:
        return [
            self.stepwise_share, self.contrary_share, self.common_tone_share,
            self.parallel_perfects, self.overlaps, self.leaps_over_fifth,
            self.sevenths_resolved, self.guide_tone_steps,
            self.cadence_dissonances, self.mean_motion, self.widest_spacing,
            self.perfect_above_bass, self.mean_ambitus,
        ]


LABELS = [
    ("stepwise_share", "% movimiento por grado conjunto (<=2 st)"),
    ("contrary_share", "% pares de voces en mov. contrario"),
    ("common_tone_share", "% voces que mantienen nota comun"),
    ("parallel_perfects", "5tas/8vas paralelas (cantidad)"),
    ("overlaps", "solapamientos de voces (cantidad)"),
    ("leaps_over_fifth", "% saltos mayores a 5ta justa"),
    ("sevenths_resolved", "% septimas que resuelven bajando"),
    ("guide_tone_steps", "% guide tones conectadas por grado"),
    ("cadence_dissonances", "disonancias contra el bajo en reposo"),
    ("mean_motion", "movimiento medio por voz (semitonos)"),
    ("widest_spacing", "hueco maximo entre voces agudas (st)"),
    ("perfect_above_bass", "% intervalos perfectos sobre el bajo"),
    ("mean_ambitus", "ambitus medio por voz (semitonos)"),
]


def measure(chords: Sequence[Sequence[int]], contexts: Sequence[ChordContext]) -> Measurements:
    """Measure a finished solution against style-independent observables."""
    if len(chords) < 2:
        return Measurements()

    voice_count = len(chords[0])
    motions: List[int] = []
    stepwise = held = 0
    contrary_pairs = total_pairs = 0
    parallels = overlaps = 0
    big_leaps = 0
    sevenths_total = sevenths_ok = 0
    guides_total = guides_ok = 0

    for index in range(1, len(chords)):
        previous, current = chords[index - 1], chords[index]
        deltas = [current[v] - previous[v] for v in range(voice_count)]
        motions.extend(abs(d) for d in deltas)
        stepwise += sum(1 for d in deltas if 0 < abs(d) <= 2)
        held += sum(1 for d in deltas if d == 0)
        big_leaps += sum(1 for d in deltas if abs(d) > 7)

        for a in range(voice_count):
            for b in range(a + 1, voice_count):
                total_pairs += 1
                if deltas[a] * deltas[b] < 0:
                    contrary_pairs += 1
                before = (previous[b] - previous[a]) % 12
                after = (current[b] - current[a]) % 12
                same_way = (
                    deltas[a] != 0 and deltas[b] != 0
                    and (deltas[a] > 0) == (deltas[b] > 0)
                )
                if same_way and before == after and before in (0, 7):
                    parallels += 1

        overlaps += voice_overlap_count(previous, current)

        context = contexts[index - 1]
        if context.seventh_pc is not None:
            for v in range(voice_count):
                if previous[v] % 12 == context.seventh_pc:
                    sevenths_total += 1
                    if -2 <= deltas[v] < 0 or deltas[v] == 0:
                        sevenths_ok += 1

        next_context = contexts[index]
        for v in range(voice_count):
            if previous[v] % 12 in context.guide_tone_pcs:
                guides_total += 1
                if (current[v] % 12 in next_context.guide_tone_pcs
                        and abs(deltas[v]) <= 2):
                    guides_ok += 1

    moving = [m for m in motions if m > 0]
    widest = 0
    for chord in chords:
        for i in range(1, len(chord) - 1):
            widest = max(widest, chord[i + 1] - chord[i])

    cadence = (bass_consonance_violations(chords[0])
               + bass_consonance_violations(chords[-1]))

    # Direct observables for the two modal rules: organum leans on perfect
    # intervals above the bass, and chant keeps each line inside a narrow band.
    perfect = total_above_bass = 0
    for chord in chords:
        for pitch in chord[1:]:
            total_above_bass += 1
            if (pitch - chord[0]) % 12 in (0, 5, 7):
                perfect += 1
    ambitus = [
        max(chord[v] for chord in chords) - min(chord[v] for chord in chords)
        for v in range(voice_count)
    ]

    return Measurements(
        stepwise_share=100.0 * stepwise / max(1, len(moving)),
        contrary_share=100.0 * contrary_pairs / max(1, total_pairs),
        common_tone_share=100.0 * held / max(1, len(motions)),
        parallel_perfects=parallels,
        overlaps=overlaps,
        leaps_over_fifth=100.0 * big_leaps / max(1, len(moving)),
        sevenths_resolved=100.0 * sevenths_ok / max(1, sevenths_total) if sevenths_total else float("nan"),
        guide_tone_steps=100.0 * guides_ok / max(1, guides_total) if guides_total else float("nan"),
        cadence_dissonances=cadence,
        mean_motion=sum(motions) / max(1, len(motions)),
        widest_spacing=widest,
        perfect_above_bass=100.0 * perfect / max(1, total_above_bass),
        mean_ambitus=sum(ambitus) / max(1, len(ambitus)),
    )


def average(items: List[Measurements]) -> Measurements:
    if not items:
        return Measurements()
    rows = [m.as_row() for m in items]
    keys = [key for key, _ in LABELS]
    averaged = {}
    for position, key in enumerate(keys):
        values = [row[position] for row in rows if row[position] == row[position]]
        averaged[key] = sum(values) / len(values) if values else float("nan")
    return Measurements(**averaged)


def run_case(symbols: List[str], profile, seed: int) -> Measurements:
    voices = build_voice_parts(["B", "T", "A", "S"])
    slots = [
        ChordSlot(
            requirement=build_requirement(parse_chord(s), 4),
            duration_quarters=2.0,
            bar_index=i // 2,
        )
        for i, s in enumerate(symbols)
    ]
    settings = RunSettings(profile=profile, voices=voices)
    result = run(slots, settings,
                 GAConfig(population_size=140, generations=110,
                          random_seed=seed, workers=1))
    if not result.solutions:
        return None
    contexts = [ChordContext.from_chord(s.requirement.chord) for s in slots]
    return measure(result.solutions[0].slots, contexts)


def control_profile(profile):
    """Same hard rules, every stylistic weight silenced: pure minimal motion."""
    return replace(
        profile,
        weight_leap=0.0, weight_crossing=0.0, weight_spacing=0.0,
        weight_contrary_bonus=0.0, weight_stepwise=0.0, weight_span=0.0,
        weight_tessitura=0.0, weight_direct_fifths=0.0,
        weight_double_third=0.0, weight_double_leading_tone=0.0,
        weight_double_seventh=0.0, weight_unresolved_seventh=0.0,
        weight_unresolved_leading_tone=0.0, weight_overlap=0.0,
        weight_common_tone=0.0, weight_bass_contrary=0.0,
        weight_guide_tone=0.0, weight_leap_compensation=0.0,
        forbidden_melodic_intervals=(), weight_forbidden_melodic=0.0,
        style_max_leap=None, weight_harmonic_dissonance=0.0,
        weight_minor_ninth=0.0, weight_cadence_consonance=0.0,
    )


def main() -> None:
    columns: Dict[str, Measurements] = {}

    control = control_profile(GENRE_PROFILES["jazz"])
    control_runs = []
    for symbols in PROGRESSIONS.values():
        for seed in SEEDS:
            measured = run_case(symbols, control, seed)
            if measured:
                control_runs.append(measured)
    columns["SOLO DISTANCIA"] = average(control_runs)

    for key, profile in GENRE_PROFILES.items():
        runs = []
        for symbols in PROGRESSIONS.values():
            for seed in SEEDS:
                measured = run_case(symbols, profile, seed)
                if measured:
                    runs.append(measured)
        columns[profile.label.upper()] = average(runs)

    names = list(columns)
    header = "  ".join(name[:13].rjust(13) for name in names)
    print(f"{'metrica':<42}{header}")
    print("-" * (42 + len(header)))
    for key, label in LABELS:
        cells = []
        for name in names:
            value = getattr(columns[name], key)
            cells.append(("n/a" if value != value else f"{value:.1f}").rjust(13))
        print(f"{label:<42}" + "  ".join(cells))


if __name__ == "__main__":
    main()
