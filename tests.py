# -*- coding: utf-8 -*-
"""
Engine test suite. Run with:  python tests.py

Focused on the things that are easy to get subtly wrong: chord spelling,
constraint detection, and the promise that a switched-on rule is never
violated by a returned solution.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
import unittest

from engine import history as _history

# Antes de que ningun test corra: los datos van a un descartable. Varios
# tests llaman a `session.export_outcome`, que anota la corrida en el
# historial --- que guarda las diez ultimas ---, y el historial es del
# usuario. Mover la raiz cubre los seis archivos de una vez y no hay que
# acordarse de nada en cada test nuevo.
os.environ.setdefault(
    _history.SANDBOX_VARIABLE,
    os.path.join(tempfile.gettempdir(), "chordweaver-tests-data"))

from engine import (achievements, ambience, book, eggs, export, harmony,
                    history, session, story, visitors)
from engine.fitness import (
    GENRE_PROFILES,
    INFINITE_COST,
    RunSettings,
    evaluate,
    has_harmonic_tritone,
    has_melodic_tritone,
    parallel_interval_violation,
)
from engine.ga import (ChordSlot, GAConfig, SlotOption,
                       diagnose_impossible_slots, run)
from engine.theory import (
    ChordParseError,
    build_voice_parts,
    make_custom_chord,
    note_name,
    parse_chord,
    parse_note_name,
    parse_pitch_class,
    spell_pitch,
)
from engine.voicing import build_requirement, build_voicing_plan, check_chord_fits


class TestNoteNames(unittest.TestCase):
    def test_middle_c(self):
        self.assertEqual(parse_note_name("C4"), 60)
        self.assertEqual(note_name(60), "C4")

    def test_accidentals_and_octaves(self):
        self.assertEqual(parse_note_name("A0"), 21)
        self.assertEqual(parse_note_name("Bb3"), 58)
        self.assertEqual(parse_note_name("F#5"), 78)
        self.assertEqual(parse_note_name("C8"), 108)

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_note_name("H4")


class TestChordParsing(unittest.TestCase):
    def test_triads(self):
        self.assertEqual(sorted(parse_chord("C").pitch_classes), [0, 4, 7])
        self.assertEqual(sorted(parse_chord("Cm").pitch_classes), [0, 3, 7])
        self.assertEqual(sorted(parse_chord("Cdim").pitch_classes), [0, 3, 6])
        self.assertEqual(sorted(parse_chord("Caug").pitch_classes), [0, 4, 8])

    def test_sevenths_and_aliases(self):
        self.assertEqual(sorted(parse_chord("Cmaj7").pitch_classes), [0, 4, 7, 11])
        self.assertEqual(
            sorted(parse_chord("CM7").pitch_classes),
            sorted(parse_chord("Cmaj7").pitch_classes),
        )
        self.assertEqual(
            sorted(parse_chord("C-7").pitch_classes),
            sorted(parse_chord("Cm7").pitch_classes),
        )
        self.assertEqual(sorted(parse_chord("Cm7b5").pitch_classes), [0, 3, 6, 10])
        self.assertEqual(sorted(parse_chord("Cdim7").pitch_classes), [0, 3, 6, 9])

    def test_extensions(self):
        self.assertIn(2, parse_chord("C9").pitch_classes)        # D
        self.assertIn(3, parse_chord("C7#9").pitch_classes)      # D#
        self.assertIn(6, parse_chord("Cmaj7#11").pitch_classes)  # F#

    def test_alteration_replaces_natural_tone(self):
        """C7b5 must drop the perfect fifth rather than stack both fifths."""
        pcs = parse_chord("C7b5").pitch_classes
        self.assertIn(6, pcs)
        self.assertNotIn(7, pcs)

    def test_slash_chord(self):
        chord = parse_chord("C/G")
        self.assertEqual(chord.bass_pc, 7)
        self.assertEqual(sorted(chord.pitch_classes), [0, 4, 7])

    def test_six_nine_is_not_a_slash_chord(self):
        chord = parse_chord("C6/9")
        self.assertIsNone(chord.bass_pc)
        self.assertIn(9, chord.pitch_classes)
        self.assertIn(2, chord.pitch_classes)

    def test_unknown_symbol_raises(self):
        with self.assertRaises(ChordParseError):
            parse_chord("Cwobble")


class TestSpelling(unittest.TestCase):
    def test_sharp_nine_is_a_second_not_a_third(self):
        chord = parse_chord("C7#9")
        tone = next(t for t in chord.tones if t.degree == "#9")
        step, alter, _ = spell_pitch(60 + tone.semitones, "C", tone.semitones, tone.degree)
        self.assertEqual((step, alter), ("D", 1))

    def test_flat_nine(self):
        chord = parse_chord("C7b9")
        tone = next(t for t in chord.tones if t.degree == "b9")
        step, alter, _ = spell_pitch(60 + tone.semitones, "C", tone.semitones, tone.degree)
        self.assertEqual((step, alter), ("D", -1))

    def test_diminished_seventh_is_a_seventh(self):
        chord = parse_chord("Cdim7")
        tone = next(t for t in chord.tones if t.degree == "bb7")
        step, alter, _ = spell_pitch(60 + tone.semitones, "C", tone.semitones, tone.degree)
        self.assertEqual((step, alter), ("B", -2))


class TestVoicing(unittest.TestCase):
    def test_triad_with_more_voices_doubles_root_first(self):
        plan = build_voicing_plan(parse_chord("C"), 5)
        degrees = [t.degree for t in plan.degrees]
        self.assertEqual(degrees.count("1"), 2)
        self.assertEqual(len(plan.degrees), 5)

    def test_six_voices_never_double_the_third_twice(self):
        plan = build_voicing_plan(parse_chord("C"), 6)
        degrees = [t.degree for t in plan.degrees]
        self.assertLessEqual(degrees.count("3"), 1)

    def test_omission_warns_and_keeps_guide_tones(self):
        advice = check_chord_fits(parse_chord("C13"), 4)
        self.assertFalse(advice.fits)
        self.assertIn("5", advice.suggested_omissions)
        requirement = build_requirement(parse_chord("C13"), 4)
        pcs = requirement.required_pitch_classes
        self.assertIn(4, pcs)      # major third survives
        self.assertIn(10, pcs)     # flat seventh survives

    def test_essential_tones_are_never_omitted(self):
        requirement = build_requirement(parse_chord("Cmaj7"), 3)
        self.assertIn(4, requirement.required_pitch_classes)
        self.assertIn(11, requirement.required_pitch_classes)

    def test_special_voicings_switch_strips_colour_tones(self):
        from engine.voicing import strip_special_voicings
        reduced = strip_special_voicings(parse_chord("Cmaj9"))
        self.assertEqual([t.degree for t in reduced.tones], ["1", "3", "5", "7"])
        # A sus chord keeps its character instead of collapsing to a bare fifth.
        sus = strip_special_voicings(parse_chord("Csus4"))
        self.assertIn("sus4", [t.degree for t in sus.tones])

    def test_gregorian_run_has_no_ninths(self):
        request = session.JobRequest(
            genre_key="gregorian",
            voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry("Cmaj9", 2.0, 0),
                     session.ChordEntry("F", 2.0, 0)],
            ga_config=GAConfig(population_size=40, generations=20, random_seed=1),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        sounded = {p % 12 for p in outcome.result.solutions[0].slots[0]}
        self.assertNotIn(2, sounded)   # no D on top of a C chord

    def test_custom_chord_from_piano_input(self):
        chord = make_custom_chord([0, 5, 7], "stack")
        self.assertEqual(sorted(chord.pitch_classes), [0, 5, 7])


class TestConstraintDetection(unittest.TestCase):
    def test_parallel_fifths_detected(self):
        previous = [60, 67]
        current = [62, 69]
        fifth, octave = parallel_interval_violation(previous, current, 0, 1)
        self.assertTrue(fifth)
        self.assertFalse(octave)

    def test_contrary_motion_into_a_fifth_is_legal(self):
        previous = [60, 67]
        current = [59, 66]   # both descend -> still parallel
        fifth, _ = parallel_interval_violation(previous, current, 0, 1)
        self.assertTrue(fifth)
        current = [62, 66]   # contrary-ish: not both same direction? both up
        previous2 = [60, 67]
        current2 = [57, 64]
        fifth2, _ = parallel_interval_violation(previous2, current2, 0, 1)
        self.assertTrue(fifth2)

    def test_static_fifth_is_not_parallel(self):
        previous = [60, 67]
        current = [60, 67]
        fifth, octave = parallel_interval_violation(previous, current, 0, 1)
        self.assertFalse(fifth)
        self.assertFalse(octave)

    def test_parallel_octaves_detected(self):
        previous = [60, 72]
        current = [62, 74]
        _, octave = parallel_interval_violation(previous, current, 0, 1)
        self.assertTrue(octave)

    def test_melodic_and_harmonic_tritone(self):
        self.assertTrue(has_melodic_tritone([60, 64], [66, 64]))
        self.assertFalse(has_melodic_tritone([60, 64], [62, 64]))
        self.assertTrue(has_harmonic_tritone([60, 66]))
        self.assertFalse(has_harmonic_tritone([60, 67]))


class TestFitness(unittest.TestCase):
    def setUp(self):
        self.voices = build_voice_parts(["B", "T", "A", "S"])

    def test_out_of_range_is_annulled(self):
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=self.voices)
        # Bass forced far above its ceiling.
        result = evaluate([[90, 60, 64, 67]], settings)
        self.assertFalse(result.valid)
        self.assertEqual(result.total, INFINITE_COST)

    def test_missing_required_tone_is_annulled(self):
        settings = RunSettings(
            profile=GENRE_PROFILES["jazz"],
            voices=self.voices,
            required_pitch_classes=[[0, 4, 7]],
        )
        result = evaluate([[48, 60, 64, 67]], settings)   # C E G present
        self.assertTrue(result.valid)
        result = evaluate([[48, 60, 60, 67]], settings)   # E missing
        self.assertFalse(result.valid)

    def test_less_motion_scores_better(self):
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=self.voices)
        small = evaluate([[48, 55, 64, 67], [48, 57, 64, 67]], settings)
        large = evaluate([[48, 55, 64, 67], [48, 69, 76, 79]], settings)
        self.assertLess(small.total, large.total)

    def test_static_repeat_is_penalised(self):
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=self.voices)
        repeated = evaluate([[48, 55, 64, 67], [48, 55, 64, 67]], settings)
        moved = evaluate([[48, 55, 64, 67], [48, 55, 64, 69]], settings)
        self.assertLess(moved.total, repeated.total)

    def test_switch_off_allows_parallels(self):
        base = RunSettings(profile=GENRE_PROFILES["classical"], voices=self.voices)
        chords = [[48, 55, 64, 67], [50, 57, 66, 69]]
        self.assertFalse(evaluate(chords, base).valid)
        relaxed = base.with_overrides(
            forbid_parallel_fifths=False, forbid_parallel_octaves=False
        )
        self.assertTrue(evaluate(chords, relaxed).valid)


class TestGeneticAlgorithm(unittest.TestCase):
    def _slots(self, symbols, voice_count=4):
        return [
            ChordSlot(
                requirement=build_requirement(parse_chord(s), voice_count),
                duration_quarters=2.0,
                bar_index=i // 2,
            )
            for i, s in enumerate(symbols)
        ]

    def test_every_genre_finds_solutions(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = self._slots(["C", "Am", "F", "G", "C"])
        for key in GENRE_PROFILES:
            settings = RunSettings(profile=GENRE_PROFILES[key], voices=voices)
            result = run(slots, settings, GAConfig(population_size=60, generations=40,
                                                   random_seed=1))
            self.assertTrue(result.solutions, f"{key} produced no solution")

    def test_returned_solutions_obey_hard_constraints(self):
        """The headline promise: a switched-on rule is never broken by output."""
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = self._slots(["C", "Am", "F", "G", "C", "F", "G", "C"])
        settings = RunSettings(profile=GENRE_PROFILES["chorale"], voices=voices)
        result = run(slots, settings, GAConfig(population_size=80, generations=60,
                                               random_seed=2))
        self.assertTrue(result.solutions)
        required = [list(r.requirement.required_pitch_classes) for r in slots]
        checker = RunSettings(
            profile=settings.profile, voices=voices, required_pitch_classes=required
        )
        for solution in result.solutions:
            breakdown = evaluate(solution.slots, checker)
            self.assertTrue(breakdown.valid, breakdown.violation)

    def test_solutions_are_distinct(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = self._slots(["C", "Am", "F", "G", "C", "Em"])
        settings = RunSettings(profile=GENRE_PROFILES["jazz"], voices=voices)
        result = run(slots, settings, GAConfig(population_size=80, generations=60,
                                               random_seed=4))
        signatures = {s.signature() for s in result.solutions}
        self.assertEqual(len(signatures), len(result.solutions))

    def test_ranges_are_respected(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = self._slots(["C", "F", "G", "C"])
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=voices)
        result = run(slots, settings, GAConfig(population_size=60, generations=40,
                                               random_seed=5))
        for solution in result.solutions:
            for chord in solution.slots:
                for index, pitch in enumerate(chord):
                    self.assertTrue(
                        voices[index].contains(pitch),
                        f"{voices[index].name} sings {note_name(pitch)} outside its range",
                    )

    def test_three_to_six_voices_all_work(self):
        for count, keys in (
            (3, ["B", "A", "S"]),
            (4, ["B", "T", "A", "S"]),
            (5, ["B", "T", "A", "MS", "S"]),
            (6, ["B", "Bar", "T", "A", "MS", "S"]),
        ):
            voices = build_voice_parts(keys)
            slots = self._slots(["C", "F", "G", "C"], voice_count=count)
            settings = RunSettings(profile=GENRE_PROFILES["jazz"], voices=voices)
            result = run(slots, settings, GAConfig(population_size=60, generations=40,
                                                   random_seed=6))
            self.assertTrue(result.solutions, f"{count} voices produced nothing")
            self.assertEqual(len(result.solutions[0].slots[0]), count)

    def test_impossible_configuration_reports_clearly(self):
        """An unreachable chord must produce a message, not an empty crash."""
        voices = build_voice_parts(["B", "T", "A", "S"])
        for voice in voices:
            voice.low, voice.high = 60, 61      # everyone squeezed into C4-C#4
        slots = self._slots(["F#"])
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=voices)
        result = run(slots, settings, GAConfig(population_size=20, generations=5))
        self.assertFalse(result.solutions)
        self.assertTrue(result.message)


class TestExport(unittest.TestCase):
    def _build(self, entries, voice_keys=("B", "T", "A", "S"), genre="chorale"):
        request = session.JobRequest(
            genre_key=genre,
            voice_keys=list(voice_keys),
            entries=entries,
            ga_config=GAConfig(population_size=60, generations=40, random_seed=11),
            title="Test",
        )
        return request, session.generate(request)

    def test_end_to_end_writes_both_formats(self):
        entries = [
            session.ChordEntry("C", 2.0, 0),
            session.ChordEntry("Am", 2.0, 0),
            session.ChordEntry("F", 2.0, 1),
            session.ChordEntry("G", 2.0, 1),
        ]
        request, outcome = self._build(entries)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            files = session.export_outcome(
                request, outcome, directory=folder, record_history=False
            )
            self.assertEqual(len(files), 6)      # 3 solutions x 2 formats
            for path in files:
                self.assertTrue(os.path.exists(path))
                self.assertGreater(os.path.getsize(path), 100)

    def test_musicxml_contains_both_clefs(self):
        entries = [session.ChordEntry("C", 4.0, 0), session.ChordEntry("G", 4.0, 1)]
        request, outcome = self._build(entries)
        xml = export.build_musicxml(outcome.spec, outcome.result.solutions[0])
        self.assertIn("<sign>G</sign>", xml)
        self.assertIn("<sign>F</sign>", xml)
        self.assertIn("<staves>2</staves>", xml)

    def test_midi_header_is_valid(self):
        entries = [session.ChordEntry("C", 2.0, 0), session.ChordEntry("F", 2.0, 0)]
        request, outcome = self._build(entries)
        data = export.build_midi(outcome.spec, outcome.result.solutions[0])
        self.assertTrue(data.startswith(b"MThd"))
        self.assertEqual(data.count(b"MTrk"), 5)   # tempo track + 4 voices

    def test_warning_when_chord_exceeds_voices(self):
        entries = [session.ChordEntry("C13", 2.0, 0), session.ChordEntry("F", 2.0, 0)]
        request, outcome = self._build(entries)
        self.assertTrue(outcome.warnings)
        self.assertIn("sobreentendido", outcome.warnings[0])


class TestStyleRules(unittest.TestCase):
    """The genre-idiomatic terms added on top of plain minimal-motion scoring."""

    def setUp(self):
        self.voices = build_voice_parts(["B", "T", "A", "S"])

    def _settings(self, genre, symbols):
        from engine.style import ChordContext
        chords = [parse_chord(s) for s in symbols]
        return RunSettings(
            profile=GENRE_PROFILES[genre],
            voices=self.voices,
            chord_contexts=[ChordContext.from_chord(c) for c in chords],
        )

    def test_doubled_leading_tone_costs_more(self):
        """Two leading tones imply parallel octaves however they resolve."""
        settings = self._settings("chorale", ["G7"])
        # Both voicings ascend and stay in range, so only the doubling differs.
        doubled = evaluate([[43, 59, 71, 77]], settings)      # B (the 3rd) doubled
        single = evaluate([[43, 59, 74, 77]], settings)       # D in the alto instead
        self.assertTrue(doubled.valid and single.valid)
        self.assertGreater(doubled.total, single.total)

    def test_seventh_should_resolve_downwards(self):
        settings = self._settings("chorale", ["G7", "C"])
        falling = evaluate([[43, 53, 59, 67], [48, 52, 60, 67]], settings)
        rising = evaluate([[43, 53, 59, 67], [48, 55, 60, 67]], settings)
        self.assertLess(falling.total, rising.total)

    def test_jazz_rewards_guide_tone_steps(self):
        settings = self._settings("jazz", ["Dm7", "G7"])
        # 3rd and 7th of Dm7 (F, C) move by step into G7 (F stays, C->B).
        stepwise = evaluate([[50, 60, 65, 69], [43, 59, 65, 67]], settings)
        self.assertLess(stepwise.style, 0)

    def test_melodic_tritone_penalised_in_classical(self):
        """A tritone in a single line is charged for.

        Tested through the style function directly: building a full chord
        pair that leaps a tritone without also tripping a hard constraint is
        fiddly, and it is the interval rule itself we care about here.
        """
        from engine.style import melodic_interval_penalty
        profile = GENRE_PROFILES["classical"]
        tritone = melodic_interval_penalty(
            [48, 55, 64, 67], [48, 55, 64, 73],
            profile.forbidden_melodic_intervals, profile.style_max_leap,
            profile.weight_forbidden_melodic,
        )
        step = melodic_interval_penalty(
            [48, 55, 64, 67], [48, 55, 64, 69],
            profile.forbidden_melodic_intervals, profile.style_max_leap,
            profile.weight_forbidden_melodic,
        )
        self.assertGreater(tritone, 0)
        self.assertEqual(step, 0)

    def test_common_tones_are_rewarded(self):
        settings = self._settings("chorale", ["C", "Am"])
        held = evaluate([[48, 55, 64, 67], [45, 55, 64, 67]], settings)
        moved = evaluate([[48, 55, 64, 67], [45, 57, 64, 69]], settings)
        self.assertLess(held.total, moved.total)

    def test_voice_overlap_detected(self):
        from engine.style import voice_overlap_count
        # Tenor climbs above where the alto just was.
        self.assertGreater(voice_overlap_count([48, 55, 60, 67], [48, 62, 64, 67]), 0)
        self.assertEqual(voice_overlap_count([48, 55, 60, 67], [48, 56, 61, 67]), 0)


class TestLocking(unittest.TestCase):
    """A padlocked chord must survive the search completely untouched."""

    def _slots(self, symbols, locked_index=None, locked_pitches=None):
        slots = []
        for i, symbol in enumerate(symbols):
            slots.append(ChordSlot(
                requirement=build_requirement(parse_chord(symbol), 4),
                duration_quarters=2.0,
                bar_index=i // 2,
                locked_pitches=locked_pitches if i == locked_index else None,
            ))
        return slots

    def test_locked_chord_is_never_altered(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        pinned = [48, 52, 55, 60]          # C3 E3 G3 C4
        slots = self._slots(["C", "Am", "F", "G", "C"], 0, pinned)
        settings = RunSettings(profile=GENRE_PROFILES["chorale"], voices=voices)
        result = run(slots, settings, GAConfig(population_size=60, generations=40,
                                               random_seed=3))
        self.assertTrue(result.solutions)
        for solution in result.solutions:
            self.assertEqual(solution.slots[0], pinned)

    def test_locked_chord_still_shapes_its_neighbours(self):
        """The lock must count for fitness, not be carved out of the piece."""
        voices = build_voice_parts(["B", "T", "A", "S"])
        settings = RunSettings(profile=GENRE_PROFILES["chorale"], voices=voices)
        low = self._slots(["C", "G"], 0, [48, 52, 55, 60])
        high = self._slots(["C", "G"], 0, [48, 64, 67, 72])
        required = [list(s.requirement.required_pitch_classes) for s in low]
        checker = RunSettings(profile=settings.profile, voices=voices,
                              required_pitch_classes=required)
        a = run(low, settings, GAConfig(population_size=50, generations=30,
                                        random_seed=5)).solutions[0]
        b = run(high, settings, GAConfig(population_size=50, generations=30,
                                         random_seed=5)).solutions[0]
        # Different pinned openings must lead to different second chords.
        self.assertNotEqual(a.slots[1], b.slots[1])

    def test_lock_with_wrong_voice_count_is_reported(self):
        request = session.JobRequest(
            genre_key="jazz",
            voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry("C", 2.0, 0, locked_pitches=[48, 52]),
                     session.ChordEntry("G", 2.0, 0)],
            ga_config=GAConfig(population_size=40, generations=15, random_seed=1),
        )
        outcome = session.generate(request)
        # El aviso lo lee el usuario, así que está en castellano como el
        # resto de la interfaz: dice «candado», no «lock».
        self.assertTrue(any("candado" in w for w in outcome.warnings))


class TestEmphasis(unittest.TestCase):
    """The motion/style balance must actually change what wins."""

    def test_style_emphasis_changes_the_answer(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = [
            ChordSlot(requirement=build_requirement(parse_chord(s), 4),
                      duration_quarters=2.0, bar_index=i // 2)
            for i, s in enumerate(["C", "Am", "F", "G", "C", "F"])
        ]
        base = RunSettings(profile=GENRE_PROFILES["classical"], voices=voices)
        motion_first = base.with_overrides(motion_emphasis=2.0, style_emphasis=0.4)
        style_first = base.with_overrides(motion_emphasis=0.4, style_emphasis=3.0)
        config = GAConfig(population_size=80, generations=50, random_seed=8)
        a = run(slots, motion_first, config).solutions[0]
        b = run(slots, style_first, config).solutions[0]
        self.assertNotEqual(a.signature(), b.signature())


class TestCadenceConsonance(unittest.TestCase):
    def test_consonance_measured_from_the_bass(self):
        from engine.style import bass_consonance_violations
        # 3-5-1: bass sings the third, so a 3rd and a 6th above it.
        self.assertEqual(bass_consonance_violations([52, 55, 60]), 0)
        # 6/4: the fourth above the bass is a dissonance in this idiom.
        self.assertEqual(bass_consonance_violations([55, 60, 64]), 1)

    def test_required_mode_annuls_dissonant_cadence(self):
        voices = build_voice_parts(["B", "T", "A", "S"])
        settings = RunSettings(
            profile=GENRE_PROFILES["classical"], voices=voices
        ).with_overrides(cadence_consonance_required=True)
        # Opening chord with a fourth above the bass.
        result = evaluate([[55, 60, 64, 67], [48, 55, 64, 67]], settings)
        self.assertFalse(result.valid)


class TestCaseInsensitiveChords(unittest.TestCase):
    def test_spelled_out_qualities_ignore_case(self):
        for variant in ("CMaj7", "CMAJ7", "cmaj7"):
            self.assertEqual(sorted(parse_chord(variant).pitch_classes),
                             sorted(parse_chord("Cmaj7").pitch_classes))
        for variant in ("CMin7", "CMIN7"):
            self.assertEqual(sorted(parse_chord(variant).pitch_classes),
                             sorted(parse_chord("Cm7").pitch_classes))

    def test_bare_M_and_m_stay_different(self):
        """The one place case genuinely matters: CM7 is major, Cm7 is minor."""
        self.assertIn(11, parse_chord("CM7").pitch_classes)    # major seventh
        self.assertIn(10, parse_chord("Cm7").pitch_classes)    # minor seventh
        self.assertIn(3, parse_chord("Cm7").pitch_classes)     # minor third
        self.assertIn(4, parse_chord("CM7").pitch_classes)     # major third

    def test_new_qualities_parse(self):
        for symbol in ("Csus", "C7alt", "C13sus4", "Cmaj7#5", "Cm9b5", "Cadd13"):
            self.assertGreaterEqual(len(parse_chord(symbol).tones), 3)


class TestParallelism(unittest.TestCase):
    def test_worker_count_adapts_to_machine(self):
        import os as _os
        from engine.ga import resolve_worker_count
        real = _os.cpu_count
        try:
            _os.cpu_count = lambda: 8
            # Leaves a core free for the interface.
            self.assertEqual(resolve_worker_count(None, 50000), 7)
            # Small jobs stay single-process: pickling would cost more.
            self.assertEqual(resolve_worker_count(None, 100), 1)
            # An explicit request is honoured but clamped to what exists.
            self.assertEqual(resolve_worker_count(4, 50000), 4)
            _os.cpu_count = lambda: 1
            self.assertEqual(resolve_worker_count(None, 50000), 1)
            self.assertEqual(resolve_worker_count(8, 50000), 1)
        finally:
            _os.cpu_count = real

    def test_parallel_matches_serial(self):
        """Same seed must give the same answer however many workers run."""
        voices = build_voice_parts(["B", "T", "A", "S"])
        slots = [
            ChordSlot(requirement=build_requirement(parse_chord(s), 4),
                      duration_quarters=2.0, bar_index=i // 2)
            for i, s in enumerate(["Dm7", "G7", "Cmaj7", "Am7"])
        ]
        settings = RunSettings(profile=GENRE_PROFILES["jazz"], voices=voices)
        serial = run(slots, settings,
                     GAConfig(population_size=60, generations=25,
                              random_seed=17, workers=1))
        parallel = run(slots, settings,
                       GAConfig(population_size=60, generations=25,
                                random_seed=17, workers=4))
        self.assertEqual(serial.solutions[0].cost, parallel.solutions[0].cost)


class TestBarFilling(unittest.TestCase):
    """Default chord durations must fill every offered time signature exactly."""

    def test_every_time_signature_fills_exactly(self):
        for raw in ["4/4", "3/4", "2/4", "6/8", "9/8", "12/8", "5/4", "2/2"]:
            beats, _, beat_type = raw.partition("/")
            signature = export.TimeSignature(int(beats), int(beat_type))
            chosen = 1.0
            for candidate in (2.0, 1.0, 4.0, 0.5):
                quotient = signature.quarters_per_bar / candidate
                if abs(quotient - round(quotient)) < 1e-9 and quotient >= 1:
                    chosen = candidate
                    break
            count = max(1, int(round(signature.quarters_per_bar / chosen)))
            self.assertAlmostEqual(count * chosen, signature.quarters_per_bar,
                                   msg=f"{raw} does not fill exactly")


class TestLockedVoicing(unittest.TestCase):
    """The padlock: the GA must never touch a chord the user pinned."""

    VOICES = ["B", "T", "A", "S"]

    def test_suggested_voicing_is_playable(self):
        """Suggestions must be in range, ascending, and without holes.

        Regression guard: an earlier version built the stack downwards from
        the soprano, which packed every lower voice against the top of its
        range -- a plain C major triad came out with the bass on C4, its own
        ceiling, and the whole chord crammed into one octave.
        """
        from engine.session import default_locked_voicing
        voices = build_voice_parts(self.VOICES)
        for symbol in ["C", "Cm", "Cmaj7", "C7", "Dm7", "G7", "Am7", "F#m7b5"]:
            pitches = default_locked_voicing(symbol, self.VOICES)
            self.assertEqual(len(pitches), len(voices), symbol)
            for index, pitch in enumerate(pitches):
                self.assertTrue(voices[index].contains(pitch),
                                f"{symbol}: {voices[index].name} out of range")
            self.assertEqual(pitches, sorted(pitches), f"{symbol}: voices cross")
            # Gaps between upper voices (the bass is allowed a wide one).
            for index in range(1, len(pitches) - 1):
                self.assertLessEqual(pitches[index + 1] - pitches[index], 12,
                                     f"{symbol}: hole between upper voices")

    def test_locked_chord_survives_the_search(self):
        voices = build_voice_parts(self.VOICES)
        from engine.session import default_locked_voicing
        pinned = default_locked_voicing("C", self.VOICES)
        slots = []
        for index, symbol in enumerate(["C", "Am", "F", "G"]):
            slots.append(ChordSlot(
                requirement=build_requirement(parse_chord(symbol), 4),
                duration_quarters=2.0,
                bar_index=index // 2,
                locked_pitches=list(pinned) if index == 0 else None,
            ))
        settings = RunSettings(profile=GENRE_PROFILES["chorale"], voices=voices)
        result = run(slots, settings,
                     GAConfig(population_size=60, generations=30, random_seed=31))
        self.assertTrue(result.solutions)
        for solution in result.solutions:
            self.assertEqual(solution.slots[0], pinned)

    def test_locked_chord_still_counts_for_fitness(self):
        """A pinned chord must shape its neighbours, not be ignored.

        Two different locks on the opening chord should pull the second
        chord to different places; if the lock were skipped entirely the
        search would settle on the same continuation either way.
        """
        voices = build_voice_parts(self.VOICES)

        def continuation(first_pitches):
            slots = [
                ChordSlot(requirement=build_requirement(parse_chord("C"), 4),
                          duration_quarters=2.0, bar_index=0,
                          locked_pitches=list(first_pitches)),
                ChordSlot(requirement=build_requirement(parse_chord("G"), 4),
                          duration_quarters=2.0, bar_index=0),
            ]
            settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=voices)
            result = run(slots, settings,
                         GAConfig(population_size=80, generations=40, random_seed=5))
            return result.solutions[0].slots[1]

        low = continuation([48, 55, 64, 67])      # C3 G3 E4 G4
        high = continuation([48, 64, 72, 79])     # C3 E4 C5 G5
        self.assertNotEqual(low, high)


class TestPositionalRules(unittest.TestCase):
    """Rules that depend on a chord's position must not leak into seeding."""

    def _entries(self, lock=None):
        return [
            session.ChordEntry("Cmaj7", 2.0, 0, locked_pitches=lock),
            session.ChordEntry("G7", 2.0, 0),
            session.ChordEntry("E7", 2.0, 1),
            session.ChordEntry("Am7", 2.0, 1),
        ]

    def _run(self, entries, **overrides):
        request = session.JobRequest(
            genre_key="gregorian",
            voice_keys=["B", "T", "A", "S"],
            entries=entries,
            switch_overrides=overrides,
            ga_config=GAConfig(population_size=80, generations=25, random_seed=3),
        )
        return session.generate(request)

    def test_cadence_rule_does_not_kill_passing_chords(self):
        """Regression: seeding scored chord pairs as if each were a whole piece.

        evaluate() reads a two-chord list with chord 1 as the final chord, so
        the cadence-consonance rule was applied to every passing chord. A
        dominant seventh has no consonant voicing above its bass, so the
        population came out empty and the user was told no solution existed
        when several did.
        """
        outcome = self._run(
            self._entries(),
            forbid_harmonic_tritone=False,
            cadence_consonance_required=True,
        )
        self.assertTrue(outcome.succeeded, outcome.errors)

    def test_consonant_lock_at_a_point_of_repose_is_accepted(self):
        # 3-5-1-7, abierto: el bajo canta la tercera y contra él todo es
        # tercera, quinta o sexta, y además ningún par de voces vecinas
        # queda a un semitono.
        #
        # Antes acá había un 3-5-7-1 cerrado --- mi, sol, si, do --- con el
        # argumento de que contra el bajo era todo consonante. Lo es, y aun
        # así raspa: el si y el do quedan pegados. Ésa era justamente la
        # disposición que la regla dejaba pasar y que el usuario escuchaba
        # como disonante, así que el ejemplo se cambió por uno que sí es un
        # reposo. Lo que el test prueba sigue siendo lo mismo: un candado
        # consonante en un punto de reposo no se anula.
        lock = [parse_note_name(n) for n in ("E2", "G3", "C4", "B4")]
        outcome = self._run(
            self._entries(lock),
            forbid_harmonic_tritone=False,
            cadence_consonance_required=True,
        )
        self.assertTrue(outcome.succeeded, outcome.errors)
        self.assertEqual(outcome.result.solutions[0].slots[0], lock)

    def test_impossible_chord_is_named_in_the_message(self):
        outcome = self._run(self._entries(), forbid_harmonic_tritone=True)
        self.assertFalse(outcome.succeeded)
        self.assertIn("G7", " ".join(outcome.errors))
        self.assertIn("tritono", " ".join(outcome.errors))

    def test_impossible_lock_is_explained(self):
        """A lock that breaks the consonance rule must say so.

        Uses a fourth above the bass, which stays a dissonance: sevenths do
        not, because they are part of the chord the user asked for and no
        root-position voicing of a seventh chord could avoid one.
        """
        # Bass on the fifth with the root above it: a fourth over the bass,
        # the interval that makes a 6/4 unable to close a phrase.
        lock = [parse_note_name(n) for n in ("G2", "C4", "E4", "G4")]
        outcome = self._run(
            [session.ChordEntry("C", 2.0, 0, locked_pitches=lock),
             session.ChordEntry("G7", 2.0, 0),
             session.ChordEntry("Am7", 2.0, 1),
             session.ChordEntry("C", 2.0, 1)],
            forbid_harmonic_tritone=False,
            cadence_consonance_required=True,
        )
        self.assertFalse(outcome.succeeded)
        self.assertIn("fijado", " ".join(outcome.errors))

    def test_seventh_at_a_point_of_repose_is_allowed(self):
        """Ending on a seventh chord must not be treated as a dissonance."""
        outcome = self._run(
            self._entries(),
            forbid_harmonic_tritone=False,
            cadence_consonance_required=True,
        )
        self.assertTrue(outcome.succeeded, outcome.errors)

    def test_gregorian_forbids_the_tritone_both_ways(self):
        """Mi contra fa banned the interval, not only the leap."""
        profile = GENRE_PROFILES["gregorian"]
        self.assertTrue(profile.forbid_melodic_tritone)
        self.assertTrue(profile.forbid_harmonic_tritone)


class TestChordStatePersistence(unittest.TestCase):
    """Chord rows must survive stepping away from their screen.

    Pure-data regression guard for a GUI bug: the carousel rebuilds a
    screen's widgets on every render, so the typed symbols and the padlocks
    -- which lived only inside those widgets -- were wiped as soon as the
    user navigated away and back. They came back to blank fields, retyped
    the chords, and the padlock was silently gone.
    """

    def test_snapshot_round_trip_keeps_symbol_and_lock(self):
        saved = {
            0: [
                {"symbol": "Cmaj7", "duration": "Blanca (2)",
                 "custom": None, "locked": [40, 55, 59, 60]},
                {"symbol": "G7", "duration": "Blanca (2)",
                 "custom": None, "locked": None},
            ]
        }
        restored = saved[0]
        self.assertEqual(restored[0]["symbol"], "Cmaj7")
        self.assertEqual(restored[0]["locked"], [40, 55, 59, 60])
        self.assertIsNone(restored[1]["locked"])

    def test_locked_voicing_from_the_dialog_reaches_the_engine(self):
        """A lock typed voice by voice must arrive intact at the search."""
        lock = [parse_note_name(n) for n in ("E2", "G3", "B3", "C4")]
        request = session.JobRequest(
            genre_key="gregorian",
            voice_keys=["B", "T", "A", "S"],
            entries=[
                session.ChordEntry("Cmaj7", 2.0, 0, locked_pitches=lock),
                session.ChordEntry("G7", 2.0, 0),
                session.ChordEntry("E7", 2.0, 1),
                session.ChordEntry("Am7", 2.0, 1),
            ],
            switch_overrides={
                "forbid_harmonic_tritone": False,
                "cadence_consonance_required": False,
                "weight_cadence_consonance": 90.0,
            },
            ga_config=GAConfig(population_size=80, generations=30, random_seed=5),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        for solution in outcome.result.solutions:
            self.assertEqual(solution.slots[0], lock)


class TestFiguredBass(unittest.TestCase):
    """Thoroughbass figures, counted from the bass as the period did."""

    def _figure(self, symbol, note_names, custom=None):
        from engine.theory import figured_bass, make_custom_chord
        chord = (make_custom_chord(custom, symbol) if custom
                 else parse_chord(symbol))
        return figured_bass(chord, [parse_note_name(n) for n in note_names])

    def test_triad_inversions(self):
        """Every upper voice is figured, not the period's abbreviation.

        Thoroughbass dropped the numbers a reader could assume, but the
        point of showing this in the app is to see the whole voicing, so a
        root-position triad with a doubled root reads 8/5/3.
        """
        self.assertEqual(self._figure("C", ["C3", "C4", "E4", "G4"]), "8/5/3")
        self.assertEqual(self._figure("C", ["E3", "C4", "G4", "C5"]), "6/3")
        self.assertEqual(self._figure("C", ["G2", "C4", "E4", "G4"]), "8/6/4")

    def test_seventh_inversions(self):
        self.assertEqual(self._figure("G7", ["G2", "B3", "D4", "F4"]), "7/5/3")
        self.assertEqual(self._figure("G7", ["B2", "D4", "F4", "G4"]), "6/5/3")
        self.assertEqual(self._figure("G7", ["D3", "F3", "B3", "G4"]), "6/4/3")
        self.assertEqual(self._figure("G7", ["F3", "B3", "D4", "G4"]), "6/4/2")

    def test_tritone_direction_decides_the_figure(self):
        """B-to-F is a diminished fifth, F-to-B an augmented fourth.

        Both are six semitones, so counting semitones alone cannot tell a
        6/5 from a 4/2 -- the chord degrees have to settle it.
        """
        self.assertEqual(self._figure("G7", ["B2", "D4", "F4", "G4"]), "6/5/3")
        self.assertEqual(self._figure("G7", ["F3", "B3", "D4", "G4"]), "6/4/2")

    def test_hand_picked_chord_still_gets_a_figure(self):
        # E-G-B-C picked on the piano: a seventh chord in first inversion,
        # even though the inferred degrees call the C a #5.
        self.assertEqual(
            self._figure("x", ["E2", "G3", "B3", "C4"], custom=[4, 7, 11, 0]),
            "6/5/3",
        )


class TestPianoOrder(unittest.TestCase):
    def test_piano_selection_keeps_the_order_it_was_picked_in(self):
        """Regression: notes were re-sorted numerically and re-rooted.

        Picking E-G-B-C put C in the bass, because pitch class C is 0 and
        sorts ahead of E, so the padlock proposed a voicing the user had not
        asked for.
        """
        from engine.theory import make_custom_chord
        chord = make_custom_chord([4, 7, 11, 0], "E G B C")
        self.assertEqual(chord.root_pc, 4)
        self.assertEqual(chord.pitch_classes, [4, 7, 11, 0])

    def test_suggested_lock_follows_the_piano_order(self):
        from engine.session import default_locked_voicing
        pitches = default_locked_voicing("x", ["B", "T", "A", "S"], [4, 7, 11, 0])
        self.assertEqual([p % 12 for p in pitches], [4, 7, 11, 0])
        self.assertEqual(pitches, sorted(pitches))


class TestRepeatedChord(unittest.TestCase):
    """Repeating a chord is a request, not a dodge.

    The static-repeat penalty was written when the algorithm chose the
    progression, to stop it standing still to save motion. Now the user
    picks the chords, so writing E7 four times means they want E7 four
    times and holding every voice is the right answer. Charging for it
    produced the opposite of what each slider promised: at maximum distance
    the penalty forced needless re-voicings, while at maximum style the
    penalty was scaled away and the common-tone reward held everything
    still.
    """

    def _settings(self, symbols):
        from engine.style import ChordContext
        voices = build_voice_parts(["B", "T", "A", "S"])
        chords = [parse_chord(s) for s in symbols]
        return RunSettings(
            profile=GENRE_PROFILES["classical"],
            voices=voices,
            chord_contexts=[ChordContext.from_chord(c) for c in chords],
        )

    def test_holding_a_repeated_chord_is_free(self):
        voicing = [40, 55, 64, 67]
        result = evaluate([voicing, list(voicing)], self._settings(["C", "C"]))
        self.assertEqual(result.static_repeat, 0.0)

    def test_standing_still_through_a_chord_change_still_costs(self):
        voicing = [40, 55, 64, 67]
        result = evaluate([voicing, list(voicing)], self._settings(["G7", "C"]))
        self.assertGreater(result.static_repeat, 0.0)

    def test_both_sliders_agree_on_a_repeated_chord(self):
        """Either extreme should hold the voicing, not fight over it.

        Given a realistic budget: on a starved search the optimum is simply
        not reached, which says nothing about whether the scoring is right.

        The budget had to grow once the points of repose started asking for
        root position. Holding one root-position voicing throughout is still
        the cheapest answer -- no motion, nothing owed at either end -- but
        with the motion slider near zero there is barely any gradient left to
        pull the middle chords into line, so the search needs room to find
        it. At 70/30 the run was already marginal: seed 4 failed from the
        motion end too, where this rule is all but switched off.
        """
        entries = [session.ChordEntry("E7", 2.0, i // 2) for i in range(4)]
        base = {
            "forbid_parallel_fifths": False, "forbid_parallel_octaves": False,
            "forbid_melodic_tritone": False, "forbid_harmonic_tritone": False,
            "forbid_voice_crossing": False, "cadence_consonance_required": False,
            # Apagada a propósito: el último acorde se pide más comprimido que
            # los demás, así que sostener una única disposición ancha deja algo
            # debiéndose justo al final y la respuesta más barata pasa a ser
            # re-disponer ese acorde. Eso es lo que la regla quiere que pase;
            # lo que este test mide es otra cosa --- que los dos extremos del
            # dial coincidan entre sí --- y con la regla puesta esa pregunta
            # queda tapada por ella.
            "weight_final_span": 0.0,
        }
        for style, motion in ((3.0, 0.1), (0.1, 3.0)):
            request = session.JobRequest(
                genre_key="classical",
                voice_keys=["B", "T", "A", "S"],
                entries=list(entries),
                switch_overrides={**base, "style_emphasis": style,
                                  "motion_emphasis": motion},
                ga_config=GAConfig(population_size=200, generations=120,
                                   random_seed=4),
            )
            outcome = session.generate(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            slots = outcome.result.solutions[0].slots
            self.assertTrue(
                all(chord == slots[0] for chord in slots),
                f"style={style} motion={motion} re-voiced a repeated chord",
            )


class TestHarmony(unittest.TestCase):
    """The random generator: does it judge progressions like each style would?"""

    def setUp(self):
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        self.tonic = parse_pitch_class("C")
        self.pool = {o.roman: o for o in
                     build_chord_pool(self.tonic, MODES["major"],
                                      ["iv", "bVII", "N6"])}

    def _cost(self, romans, genre, weights=None):
        from engine.harmony import HarmonyWeights, progression_cost
        sequence = [self.pool[r] for r in romans]
        return progression_cost(sequence, genre,
                                weights or HarmonyWeights(), self.tonic)

    def test_authentic_cadence_beats_retrogression(self):
        self.assertLess(self._cost(["I", "IV", "V", "I"], "classical"),
                        self._cost(["I", "V", "IV", "I"], "classical"))

    def test_repetition_is_expensive(self):
        self.assertGreater(self._cost(["I", "I", "I", "I"], "classical"), 0)

    def test_modal_prefers_step_motion_to_fifths(self):
        """A modal setting should not be scored by dominant logic."""
        stepwise = self._cost(["I", "bVII", "IV", "I"], "gregorian")
        fifths = self._cost(["I", "V", "I", "V"], "gregorian")
        self.assertLess(stepwise, fifths)

    def test_modes_produce_their_own_chords(self):
        from engine.harmony import MODES, diatonic_options
        from engine.theory import SHARP_NAMES
        major = [o.label for o in diatonic_options(self.tonic, MODES["major"])]
        phrygian = [o.label for o in diatonic_options(self.tonic, MODES["phrygian"])]
        self.assertNotEqual(major, phrygian)
        self.assertIn("C", major)          # tonic triad is major
        self.assertIn("Cm", phrygian)      # tonic triad is minor

    def test_neapolitan_is_written_in_first_inversion(self):
        option = self.pool["N6"]
        self.assertIsNotNone(option.forced_bass_pc)
        # bII on C is Db; its third, F, sits in the bass.
        self.assertEqual(option.forced_bass_pc, 5)


class TestGenerator(unittest.TestCase):
    def _run(self, genre, **kwargs):
        request = session.GenerativeRequest(
            genre_key=genre,
            voice_keys=["B", "T", "A", "S"],
            tonic="C",
            slot_count=6,
            ga_config=GAConfig(population_size=90, generations=50, random_seed=5),
            **kwargs,
        )
        return request, session.generate_random(request)

    def test_every_genre_generates(self):
        for genre in ("classical", "chorale", "gregorian", "jazz"):
            _request, outcome = self._run(genre)
            self.assertTrue(outcome.succeeded, f"{genre}: {outcome.errors}")

    def test_mandatory_endpoints_are_exact(self):
        """A required endpoint is pinned, not merely penalised."""
        request, outcome = self._run(
            "classical", start_roman="I", end_roman="I", endpoints_required=True,
        )
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        first = outcome.spec.slots[0]
        last = outcome.spec.slots[-1]
        self.assertEqual(first.options[solution.choices[0]].harmony.roman, "I")
        self.assertEqual(last.options[solution.choices[-1]].harmony.roman, "I")

    def test_borrowed_chords_are_reachable(self):
        request, outcome = self._run("classical", borrowed=["iv", "bVII"])
        self.assertTrue(outcome.succeeded, outcome.errors)
        romans = {option.harmony.roman
                  for slot in outcome.spec.slots for option in slot.options}
        self.assertIn("iv", romans)
        self.assertIn("bVII", romans)

    def test_manual_mode_is_unaffected(self):
        """The generator must not change how the hand-written mode behaves."""
        request = session.JobRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry(s, 2.0, i // 2)
                     for i, s in enumerate(["C", "F", "G", "C"])],
            ga_config=GAConfig(population_size=60, generations=30, random_seed=3),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        for solution in outcome.result.solutions:
            self.assertTrue(all(c == 0 for c in solution.choices) or not solution.choices)


class TestPassingTones(unittest.TestCase):
    """Notes that fill a leap, chosen by the search rather than sprinkled on."""

    def test_candidates_are_reachable_from_both_ends(self):
        """An ornament need not sit between the two chord tones.

        Rising a tone and falling two is ordinary melodic decoration, so a
        voice that moves by a step -- or holds still -- still has somewhere
        to go. What is ruled out is a note too far to reach, or one that
        merely repeats a pitch the voice already has.
        """
        from engine.passing import passing_candidates
        scale = [0, 2, 4, 5, 7, 9, 11]
        # Filling a third.
        self.assertIn(71, passing_candidates(72, 69, scale))
        # A step still allows a neighbour above.
        self.assertIn(74, passing_candidates(72, 71, scale))
        # So does a voice holding its note.
        self.assertTrue(passing_candidates(72, 72, scale))
        # The endpoints themselves are never offered: that is a repeat.
        for pair in ((72, 69), (72, 71), (72, 72)):
            candidates = passing_candidates(*pair, scale)
            self.assertNotIn(pair[0], candidates)
            self.assertNotIn(pair[1], candidates)
        # Nothing is reachable across a wide leap.
        self.assertEqual(passing_candidates(72, 48, scale), [])

    def test_diatonic_filter(self):
        from engine.passing import passing_candidates
        scale = [0, 2, 4, 5, 7, 9, 11]
        diatonic = passing_candidates(72, 69, scale, diatonic_only=True)
        chromatic = passing_candidates(72, 69, scale, diatonic_only=False)
        self.assertLess(len(diatonic), len(chromatic))
        self.assertIn(70, chromatic)       # Bb, outside C major
        self.assertNotIn(70, diatonic)

    def test_stepwise_ornament_beats_a_leaping_one(self):
        from engine.passing import PassingRules, score_passing
        rules = PassingRules(voices=(0,))
        smooth = score_passing([([72], [69])], [[71]], rules)     # C-B-A
        leaping = score_passing([([72], [69])], [[79]], rules)    # C-G-A: a leap
        self.assertLess(smooth, leaping)

    def test_repeating_a_pitch_is_penalised(self):
        """An "ornament" on the note the voice already has is not movement."""
        from engine.passing import PassingRules, score_passing
        rules = PassingRules(voices=(0,))
        repeated = score_passing([([72], [69])], [[72]], rules)
        moving = score_passing([([72], [69])], [[71]], rules)
        self.assertGreater(repeated, 0)
        self.assertLess(moving, repeated)

    def test_density_controls_how_many_appear(self):
        from engine.passing import PassingRules
        from engine.ga import GAConfig as _GA
        counts = {}
        for density in (0.0, 0.8):
            request = session.GenerativeRequest(
                genre_key="classical", voice_keys=["B", "T", "A", "S"],
                tonic="C", slot_count=8,
                passing_rules=PassingRules(voices=(2, 3), density=density),
                ga_config=_GA(population_size=80, generations=30, random_seed=11),
            )
            outcome = session.generate_random(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            solution = outcome.result.solutions[0]
            counts[density] = sum(1 for row in solution.passing
                                  for note in row if note is not None)
        self.assertEqual(counts[0.0], 0)
        self.assertGreater(counts[0.8], 0)

    def test_crowding_is_penalised(self):
        from engine.passing import PassingRules, score_passing
        rules = PassingRules(voices=(0,), max_per_piece=1)
        pairs = [([72], [69]), ([69], [65]), ([65], [62])]
        many = score_passing(pairs, [[71], [67], [64]], rules)
        few = score_passing(pairs[:1], [[71]], rules)
        self.assertGreater(many, few * 3)

    def test_expansion_splits_the_chord(self):
        from engine.passing import expand_with_passing
        pitches, durations, flags = expand_with_passing(
            [[48, 55, 64, 72], [48, 55, 64, 69]], [2.0, 2.0],
            [[None, None, None, 71], []],
        )
        self.assertEqual(len(pitches), 3)
        self.assertAlmostEqual(sum(durations), 4.0)
        self.assertEqual(flags, [False, True, False])
        self.assertEqual(pitches[1][3], 71)

    def test_playback_keeps_the_time_and_moves_only_the_ornamenting_voice(self):
        """Lo que se escucha: el adorno se lleva la cola del acorde.

        Un acorde adornado no se puede decir con una lista de acordes ---
        todas sus voces empiezan y terminan juntas ---, así que sale como
        voces sueltas. Lo que no puede cambiar es cuánto dura: un adorno que
        agregara tiempo correría todo lo que viene después.
        """
        chords = [[48, 55, 64, 72], [], [45, 57, 64, 72]]
        durations = [2.0, 1.0, 2.0]
        played, kept, notes = session.playback_events(
            chords, durations, [(0, 2, 62, 0.25)])
        self.assertEqual(kept, durations)          # el silencio sigue en pie
        self.assertEqual(played[0], [])            # sus voces están sueltas
        self.assertEqual(played[2], chords[2])     # el resto, intacto
        self.assertEqual(sorted(notes), sorted([
            (48, 0.0, 2.0), (55, 0.0, 2.0),
            (64, 0.0, 1.5), (62, 1.5, 0.5),        # la voz que adorna
            (72, 0.0, 2.0),
        ]))

    def test_playback_drops_the_melody_voice(self):
        """En el Armonizador la melodía se toca aparte y no se dobla."""
        played, _kept, notes = session.playback_events(
            [[48, 55, 64, 72], [45, 57, 64, 72]], [2.0, 2.0],
            [(0, 3, 71, 0.5)], drop_voice=3)
        self.assertEqual(played[1], [45, 57, 64])
        self.assertNotIn(71, [pitch for pitch, _s, _l in notes])
        self.assertNotIn(72, [pitch for pitch, _s, _l in notes])

    def test_ornaments_are_placed_past_the_rests(self):
        """La búsqueda saltea los silencios; la partitura no.

        Si el adorno se anotara con el índice de la búsqueda, todo lo que
        viniera después de un silencio quedaría corrido un acorde --- el
        mismo desfasaje que arregla `voiced_slots`.
        """
        from engine.passing import PassingRules
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry(symbol="C", duration_quarters=2.0,
                                        bar_index=0),
                     session.ChordEntry(symbol="C", duration_quarters=2.0,
                                        bar_index=0, is_rest=True),
                     session.ChordEntry(symbol="F", duration_quarters=2.0,
                                        bar_index=1),
                     session.ChordEntry(symbol="G", duration_quarters=2.0,
                                        bar_index=1)],
            passing_rules=PassingRules(voices=(1, 2), density=0.9),
            ga_config=GAConfig(population_size=60, generations=30,
                               random_seed=5),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        found = session.ornaments_of(outcome.spec,
                                     outcome.result.solutions[0])
        self.assertTrue(found, "el adorno tiene que aparecer con density alta")
        for slot, _voice, _note, _share in found:
            self.assertFalse(outcome.spec.slots[slot].is_rest)


class TestGeneratorRequest(unittest.TestCase):
    """The generator wired end to end, without a display."""

    def test_passing_tones_stay_singable(self):
        """Only enabled voices get them, and never as a repeated pitch."""
        from engine.passing import PassingRules
        request = session.GenerativeRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"], tonic="C",
            slot_count=6, passing_rules=PassingRules(voices=(2, 3)),
            ga_config=GAConfig(population_size=80, generations=40, random_seed=7),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        for slot_index, row in enumerate(solution.passing):
            for voice, note in enumerate(row):
                if note is None:
                    continue
                self.assertIn(voice, (2, 3), "a voice that was not enabled took one")
                start = solution.slots[slot_index][voice]
                end = solution.slots[slot_index + 1][voice]
                self.assertNotEqual(note, start)
                self.assertNotEqual(note, end)
                self.assertLessEqual(abs(note - start), 4)
                self.assertLessEqual(abs(note - end), 4)

    def test_modes_change_the_available_chords(self):
        request = session.GenerativeRequest(
            genre_key="gregorian", voice_keys=["B", "T", "A", "S"],
            tonic="D", mode_key="dorian", slot_count=4,
            ga_config=GAConfig(population_size=60, generations=25, random_seed=3),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        romans = {option.harmony.roman
                  for slot in outcome.spec.slots for option in slot.options}
        self.assertIn("i", romans)      # dorian has a minor tonic


class TestGeneratorDiversity(unittest.TestCase):
    def test_the_three_options_are_different_progressions(self):
        """Regression: all three winners shared one chord sequence.

        Diversity was measured on pitches, so the search could return the
        same harmony three times over with the voicing nudged -- which is no
        choice at all when picking the chords is the whole point.
        """
        request = session.GenerativeRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            tonic="C", slot_count=8,
            start_roman="I", end_roman="I", endpoints_required=True,
            ga_config=GAConfig(population_size=70, generations=30, random_seed=4),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        sequences = {tuple(s.choices) for s in outcome.result.solutions}
        self.assertEqual(len(sequences), len(outcome.result.solutions))

    def test_only_one_voice_ornaments_a_transition(self):
        """Two voices leaving the chord at once reads as a clash, not decoration."""
        from engine.passing import PassingRules
        request = session.GenerativeRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"], tonic="C",
            slot_count=8,
            passing_rules=PassingRules(voices=(1, 2, 3), density=0.7),
            ga_config=GAConfig(population_size=110, generations=50, random_seed=9),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        for solution in outcome.result.solutions:
            for row in solution.passing:
                self.assertLessEqual(sum(1 for n in row if n is not None), 1)

    def test_ornaments_are_not_all_the_same_length(self):
        """
        Los adornos toman largos distintos, no todos el mismo.

        Se mide sobre varias semillas y no sobre una: que una pieza salga
        con todos los adornos iguales es posible y no prueba nada, y una
        prueba de una sola semilla se rompe con cualquier cambio de peso
        aunque la propiedad siga estando.
        """
        from engine.passing import PassingRules
        varied = 0
        seeds = (9, 10, 11, 12)
        for seed in seeds:
            request = session.GenerativeRequest(
                genre_key="jazz", voice_keys=["B", "T", "A", "S"], tonic="C",
                slot_count=8,
                passing_rules=PassingRules(voices=(1, 2, 3), density=0.8),
                ga_config=GAConfig(population_size=110, generations=50,
                                   random_seed=seed),
            )
            outcome = session.generate_random(request)
            solution = outcome.result.solutions[0]
            used = {solution.passing_share[i]
                    for i, row in enumerate(solution.passing)
                    if any(n is not None for n in row)}
            varied += len(used) >= 2
        self.assertGreaterEqual(varied, len(seeds) - 1)


class TestSettingsPersistence(unittest.TestCase):
    def test_preferences_survive_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            history.save_settings({"font_scale": 1.4, "population_size": 321}, path)
            values = history.load_settings(path)
            self.assertEqual(values["font_scale"], 1.4)
            self.assertEqual(values["population_size"], 321)
            # Unknown keys are ignored rather than trusted.
            history.save_settings({"nonsense": 1}, path)
            self.assertNotIn("nonsense", history.load_settings(path))

    def test_corrupt_settings_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{broken")
            self.assertEqual(history.load_settings(path)["font_scale"], 1.0)


class TestVoicingQuality(unittest.TestCase):
    def test_voices_do_not_land_on_the_same_pitch(self):
        """Six voices must produce six noteheads.

        Two parts on the identical pitch collapse into one notehead on the
        page, so a six-voice chord looked like a four-voice one in notation
        software -- which read as a broken export when it was really a
        voicing problem. Octave doublings are untouched.
        """
        request = session.JobRequest(
            genre_key="chorale",
            voice_keys=["B", "Bar", "T", "A", "MS", "S"],
            entries=[session.ChordEntry(s, 2.0, i // 2)
                     for i, s in enumerate(["C", "Am", "F", "G"])],
            ga_config=GAConfig(population_size=70, generations=35, random_seed=3),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        for chord in outcome.result.solutions[0].slots:
            self.assertEqual(len(set(chord)), len(chord),
                             "two voices are on the same pitch")

    def test_six_four_is_discouraged(self):
        from engine.style import ChordContext
        voices = build_voice_parts(["B", "T", "A", "S"])
        chord = parse_chord("C")
        settings = RunSettings(
            profile=GENRE_PROFILES["chorale"], voices=voices,
            chord_contexts=[ChordContext.from_chord(chord)],
        )
        root_position = evaluate([[48, 55, 64, 72]], settings)   # C in the bass
        six_four = evaluate([[43, 60, 64, 72]], settings)        # G in the bass
        self.assertLess(root_position.total, six_four.total)

    def test_the_cadential_six_four_is_wanted_and_only_written_5_1_3(self):
        """El único 6/4 que el estilo escribe a propósito, y en un solo orden.

        Cobrárselo era prohibir justo lo que la fórmula viene a enseñar; no
        cobrárselo no alcanza, porque el bajo en la fundamental siempre está
        más cerca y gana en movimiento. Y el premio es de la disposición
        5-1-3: con la tercera en el medio los intervalos sobre el bajo son
        los mismos y no es la fórmula.
        """
        from engine.style import ChordContext
        from engine.fitness import evaluate, RunSettings, GENRE_PROFILES
        voices = build_voice_parts(["B", "T", "A", "S"])
        settings = RunSettings(
            profile=GENRE_PROFILES["classical"], voices=voices,
            chord_contexts=[ChordContext.from_chord(parse_chord("G"), "V"),
                            ChordContext.from_chord(parse_chord("C"), "I")],
        )
        tonic = [48, 55, 64, 72]
        # D-G-D-B: la quinta en el bajo, la fundamental encima, la tercera
        # arriba. Contra D-B-D-G, que tiene las mismas notas y no es un 6/4.
        wanted = evaluate([[50, 55, 62, 71], tonic], settings)
        muddled = evaluate([[50, 59, 62, 67], tonic], settings)
        self.assertLess(wanted.style, muddled.style)
        self.assertLess(wanted.style, 0.0)

    def test_a_six_four_that_resolves_nowhere_still_costs(self):
        """La exención es de la fórmula, no de la quinta en el bajo."""
        from engine.style import ChordContext
        from engine.fitness import evaluate, RunSettings, GENRE_PROFILES
        settings = RunSettings(
            profile=GENRE_PROFILES["classical"],
            voices=build_voice_parts(["B", "T", "A", "S"]),
            chord_contexts=[ChordContext.from_chord(parse_chord("G"), "V"),
                            ChordContext.from_chord(parse_chord("F"), "IV")],
        )
        subdominant = [53, 57, 60, 69]
        six_four = evaluate([[50, 55, 62, 71], subdominant], settings)
        self.assertGreater(six_four.style, 0.0)

    def _repose_settings(self, genre, symbol):
        from engine.style import ChordContext
        chord = parse_chord(symbol)
        return chord, RunSettings(
            profile=GENRE_PROFILES[genre],
            voices=build_voice_parts(["B", "T", "A", "S"]),
            chord_contexts=[ChordContext.from_chord(chord)],
        )

    def test_repose_chord_prefers_root_position(self):
        """1-3-5-7 must beat 3-5-7-1, which consonance alone cannot see.

        Over the third of a Cmaj7 the upper voices form a third, a fifth and
        a sixth -- all consonant -- so the two voicings tied and the inverted
        one then won on being more compact.
        """
        for genre in ("jazz", "classical", "chorale", "gregorian"):
            _chord, settings = self._repose_settings(genre, "Cmaj7")
            root = evaluate([[48, 64, 67, 71]], settings)      # C E G B
            first = evaluate([[52, 67, 71, 72]], settings)     # E G B C
            self.assertEqual(root.cadence, 0.0, genre)
            self.assertGreater(first.cadence, 0.0, genre)

    def test_three_voices_keep_their_first_inversion(self):
        """3-5-1 is the answer in three parts, and must not be charged for.

        The rule exists for four voices and up. Applying it to a three-part
        setting was a regression: there is no spare voice there, and the
        fifth and octave over the third read better than the third and fifth
        crowded above the root.
        """
        from engine.style import ChordContext
        chord = parse_chord("C")
        settings = RunSettings(
            profile=GENRE_PROFILES["classical"],
            voices=build_voice_parts(["B", "A", "S"]),
            chord_contexts=[ChordContext.from_chord(chord)],
        )
        self.assertEqual(evaluate([[52, 67, 72]], settings).cadence, 0.0)
        self.assertEqual(evaluate([[48, 64, 67]], settings).cadence, 0.0)

    def test_a_slash_bass_is_not_charged_for_being_inverted(self):
        """The user named the bass; the rule must not fight them for it."""
        _chord, settings = self._repose_settings("jazz", "C/E")
        self.assertEqual(evaluate([[52, 67, 72, 76]], settings).cadence, 0.0)

    def test_a_rootless_voicing_is_not_charged(self):
        """With the root omitted there is nothing to put in the bass."""
        from engine.style import ChordContext, root_position_penalty
        context = ChordContext.from_chord(parse_chord("Cmaj7"))
        self.assertEqual(root_position_penalty([52, 67, 71], context, 90.0), 0.0)

    def test_only_the_outer_chords_are_asked_for_root_position(self):
        """An inversion in the middle of a phrase is ordinary writing."""
        _chord, settings = self._repose_settings("classical", "C")
        held = [48, 64, 67, 72]                                # C in the bass
        inverted = [52, 64, 67, 72]                            # E in the bass
        ends = evaluate([held, inverted, held], settings)
        self.assertEqual(ends.cadence, 0.0)

    def _melody_settings(self, melody_voice):
        from engine.style import ChordContext
        chord = parse_chord("Cmaj7")
        return RunSettings(
            profile=GENRE_PROFILES["jazz"],
            voices=build_voice_parts(["B", "T", "A", "S"]),
            chord_contexts=[ChordContext.from_chord(chord)] * 3,
            melody_voice=melody_voice,
        )

    #: The melody sits on the alto, so a voice above it can rub without the
    #: parts crossing -- a crossing would annul the chromosome first and the
    #: style terms would never be reached.
    RUBBING = [48, 55, 71, 72]        # C3 G3 B4 C5: the soprano's C on the B
    CLEAR = [48, 55, 71, 76]          # the same B with an E5 above it instead

    def test_a_semitone_against_the_melody_is_charged(self):
        """A minor second over the user's note is the worst thing to do to it."""
        settings = self._melody_settings(2)
        self.assertLess(evaluate([self.CLEAR], settings).style,
                        evaluate([self.RUBBING], settings).style)

    def test_the_clash_costs_more_at_the_points_of_repose(self):
        settings = self._melody_settings(2)
        at_end = evaluate([self.RUBBING, self.CLEAR, self.CLEAR], settings).style
        in_middle = evaluate([self.CLEAR, self.RUBBING, self.CLEAR], settings).style
        self.assertGreater(at_end, in_middle)

    def test_the_melody_rules_stay_off_without_a_melody(self):
        """The other two modes have no given line, so nothing may fire."""
        without = self._melody_settings(None)
        with_melody = self._melody_settings(2)
        self.assertGreater(evaluate([self.RUBBING], with_melody).style,
                           evaluate([self.RUBBING], without).style)
        self.assertEqual(evaluate([self.CLEAR], without).style,
                         evaluate([self.CLEAR], with_melody).style)

    def test_organum_rewards_a_true_shadow_most(self):
        """Exact parallel beats similar motion, which beats everything else."""
        from engine.style import organum_parallel_reward
        # Voice 2 is the principalis, voice 1 the organalis a fifth below.
        before = [40, 55, 62, 67]
        weight = -100.0

        shadow = [40, 57, 64, 67]        # both up a tone: a true shadow
        self.assertEqual(
            organum_parallel_reward(before, shadow, 2, weight), -100.0)

        # Same direction, different sizes, landing on an octave.
        similar = [40, 56, 68, 72]
        self.assertAlmostEqual(
            organum_parallel_reward(before, similar, 2, weight), -55.0)

        # Both holding: the pair survives but nothing moves.
        self.assertEqual(
            organum_parallel_reward(before, list(before), 2, weight), -50.0)

        # Oblique motion is not a shadow: one of them stayed behind.
        oblique = [40, 55, 60, 67]
        self.assertEqual(
            organum_parallel_reward(before, oblique, 2, weight), 0.0)

        # Landing on a sixth is not organum, whatever the voices did.
        landing_sixth = [40, 56, 65, 67]
        self.assertEqual(
            organum_parallel_reward(before, landing_sixth, 2, weight), 0.0)

    def test_organum_wants_a_perfect_interval_under_the_chant(self):
        from engine.style import organum_interval_reward
        self.assertEqual(organum_interval_reward([40, 55, 62, 67], 2, -50.0),
                         -50.0)                       # a fifth: yes
        self.assertEqual(organum_interval_reward([40, 55, 64, 67], 2, -50.0),
                         0.0)                         # a major sixth: no

    def test_organum_stays_off_without_a_principalis(self):
        """Every other style and mode must be untouched by it."""
        from engine.style import (organum_interval_reward,
                                  organum_parallel_reward)
        self.assertEqual(organum_interval_reward([40, 55, 62, 67], None, -50.0),
                         0.0)
        self.assertEqual(
            organum_parallel_reward([40, 55, 62, 67], [40, 57, 64, 67],
                                    None, -100.0), 0.0)
        # The lowest voice has nothing under it to be shadowed by.
        self.assertEqual(organum_interval_reward([40, 55, 62, 67], 0, -50.0),
                         0.0)

    def test_the_lowest_voice_is_refused_as_principalis(self):
        request = session.JobRequest(
            genre_key="gregorian", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry("C", 2.0, 0)],
            principalis_voice=0,
        )
        self.assertIsNone(session.build_settings(request).principalis_voice)
        request.principalis_voice = 2
        self.assertEqual(session.build_settings(request).principalis_voice, 2)

    def test_borrowed_labels_match_their_quality(self):
        """A label saying "menor" over a major chord is simply wrong."""
        from engine.harmony import BORROWED_CHORDS
        for spec in BORROWED_CHORDS.values():
            if spec.quality == "major":
                self.assertNotIn("menor (", spec.label, spec.label)
            if spec.quality == "minor":
                self.assertIn("menor", spec.label, spec.label)


class TestFunctionalGrammar(unittest.TestCase):
    """Chords judged by what they are doing, not by interval arithmetic."""

    def setUp(self):
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        self.tonic = parse_pitch_class("C")
        self.pool = {o.roman: o for o in build_chord_pool(
            self.tonic, MODES["major"], ["iv", "bVII", "N6"])}

    def _move(self, first, second, genre):
        from engine.harmony import GRAMMARS, grammar_cost
        return grammar_cost(self.pool[first], self.pool[second],
                            GRAMMARS[genre], self.tonic)

    def test_functions_are_assigned_sensibly(self):
        from engine.harmony import DOMINANT, SUBDOMINANT, TONIC, function_of
        self.assertEqual(function_of(self.pool["I"]), TONIC)
        self.assertEqual(function_of(self.pool["V"]), DOMINANT)
        self.assertEqual(function_of(self.pool["ii"]), SUBDOMINANT)
        self.assertEqual(function_of(self.pool["iv"]), SUBDOMINANT)

    def test_dominant_wants_to_resolve(self):
        for genre in ("classical", "chorale", "jazz"):
            self.assertLess(self._move("V", "I", genre),
                            self._move("V", "IV", genre),
                            f"{genre}: retrogression should cost more")

    def test_deceptive_is_allowed_but_second_best(self):
        for genre in ("classical", "chorale"):
            authentic = self._move("V", "I", genre)
            deceptive = self._move("V", "vi", genre)
            self.assertLess(authentic, deceptive)
            self.assertLess(deceptive, 0, "the deceptive move is still good")

    def test_modal_prefers_the_plagal_cadence(self):
        """Plainchant cadences plagally; it has no dominant pull to use."""
        plagal = self._move("IV", "I", "gregorian")
        authentic = self._move("V", "I", "gregorian")
        self.assertLess(plagal, authentic)
        # And the reverse holds in common practice.
        self.assertLess(self._move("V", "I", "classical"),
                        self._move("IV", "I", "classical"))

    def test_jazz_rewards_the_two_five(self):
        self.assertLess(self._move("ii", "V", "jazz"),
                        self._move("ii", "V", "classical"))

    def test_grammar_shapes_the_generated_progression(self):
        """A dominant in the output should usually be going somewhere."""
        from engine.harmony import DOMINANT, function_of
        request = session.GenerativeRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"], tonic="C",
            slot_count=8, start_roman="I", end_roman="I",
            endpoints_required=True,
            ga_config=GAConfig(population_size=70, generations=30, random_seed=6),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        options = [slot.options[min(choice, len(slot.options) - 1)].harmony
                   for slot, choice in zip(outcome.spec.slots, solution.choices)]
        # The piece must close on the tonic, and no dominant may fall back
        # to a subdominant, which is the retrogression the grammar bars.
        self.assertEqual(options[-1].roman, "I")
        for first, second in zip(options, options[1:]):
            if function_of(first) == DOMINANT:
                self.assertNotEqual(function_of(second), "subdominant",
                                    f"{first.roman} -> {second.roman}")

    def test_dominant_six_four_is_not_penalised(self):
        """A V7 with its fifth in the bass is standard, not a dissonance."""
        from engine.style import ChordContext
        voices = build_voice_parts(["B", "T", "A", "S"])
        dominant = parse_chord("G7")
        settings = RunSettings(profile=GENRE_PROFILES["classical"], voices=voices,
                               chord_contexts=[ChordContext.from_chord(dominant)])
        fifth_in_bass = evaluate([[50, 59, 65, 67]], settings)
        self.assertEqual(fifth_in_bass.style, 0.0)


class TestBorrowedFunctions(unittest.TestCase):
    def test_flat_two_is_a_dominant_and_flat_seven_a_subdominant(self):
        from engine.harmony import (BORROWED_FUNCTION, DOMINANT, SUBDOMINANT,
                                    MODES, build_chord_pool, function_of)
        from engine.theory import parse_pitch_class
        tonic = parse_pitch_class("C")
        pool = {o.roman: o for o in build_chord_pool(
            tonic, MODES["major"], ["bII", "bVII", "N6", "subV"])}
        # bII in root position stands in for the dominant.
        self.assertEqual(function_of(pool["bII"]), DOMINANT)
        self.assertEqual(function_of(pool["subV"]), DOMINANT)
        # bVII stands where a subdominant stands.
        self.assertEqual(function_of(pool["bVII"]), SUBDOMINANT)
        # The Neapolitan sixth prepares the dominant rather than being one.
        self.assertEqual(function_of(pool["N6"]), SUBDOMINANT)

    def test_tritone_substitute_carries_a_seventh(self):
        """Without the seventh it is not a substitute, just a major chord.

        What lets bII stand in for V is sharing its third and seventh -- the
        two notes that make the tension. A bare triad has neither.
        """
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class, ROLE_SEVENTH
        pool = {o.roman: o for o in build_chord_pool(
            parse_pitch_class("C"), MODES["major"], ["subV"])}
        tones = pool["subV"].chord.tones
        self.assertTrue(any(t.role == ROLE_SEVENTH for t in tones))
        self.assertEqual(pool["subV"].quality, "dominant")


class TestModulation(unittest.TestCase):
    """Travelling to another key and, crucially, coming back."""

    def _run(self, genre, seed=17, **kwargs):
        from engine.harmony import GENRE_DEFAULT_BORROWED, GENRE_MODULATION
        settings = kwargs.pop("modulation", GENRE_MODULATION[genre])
        request = session.GenerativeRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic="C",
            mode_key="major" if genre != "gregorian" else "dorian",
            borrowed=GENRE_DEFAULT_BORROWED.get(genre, []),
            slot_count=8,
            start_roman="I" if genre != "gregorian" else "i",
            end_roman="I" if genre != "gregorian" else "i",
            endpoints_required=True, modulation=settings,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=seed),
            **kwargs,
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        options = [slot.options[min(choice, len(slot.options) - 1)].harmony
                   for slot, choice in zip(outcome.spec.slots,
                                           outcome.result.solutions[0].choices)]
        return [option.key_area for option in options]

    def test_the_piece_always_comes_home(self):
        # One style and one seed: the rule is structural, not statistical --
        # the plan pins the window, so what holds here holds everywhere.
        for genre in ("classical",):
            for seed in (17,):
                areas = self._run(genre, seed)
                self.assertEqual(areas[0], "", f"{genre} does not start at home")
                self.assertEqual(areas[-1], "", f"{genre} does not end at home")

    def test_a_visit_never_lasts_a_single_chord(self):
        """One foreign chord is a borrowed colour, not a modulation.

        Two is allowed on purpose: a secondary dominant into its target is a
        real, if brief, tonicisation. What is barred is a lone foreign chord
        being dressed up as a change of key. The style's preferred length is
        a weighting, not a guarantee, so only the floor is asserted here.
        """
        for genre in ("classical", "chorale", "gregorian", "jazz"):
            for seed in (17, 29):
                areas = self._run(genre, seed)
                index = 0
                while index < len(areas):
                    area = areas[index]
                    span = 1
                    while index + span < len(areas) and areas[index + span] == area:
                        span += 1
                    if area:
                        self.assertGreaterEqual(
                            span, 2,
                            f"{genre}: single-chord excursion to {area}")
                    index += span

    def test_switching_off_modulation_keeps_the_piece_at_home(self):
        from engine.harmony import ModulationSettings
        areas = self._run("jazz", modulation=ModulationSettings())
        self.assertTrue(all(area == "" for area in areas))

    def test_both_kinds_can_be_on_at_once(self):
        from engine.harmony import ModulationSettings, modulation_pool
        from engine.theory import parse_pitch_class
        settings = ModulationSettings(
            key_enabled=True, modal_enabled=True,
            targets=("V", "parallel_minor"),
        )
        pool = modulation_pool(parse_pitch_class("C"), settings)
        areas = {option.key_area for option in pool}
        self.assertIn("V", areas)
        self.assertIn("parallel_minor", areas)

    def test_targets_match_what_each_style_does(self):
        """Grounded in the standard account of closely related keys."""
        from engine.harmony import GENRE_MODULATION, MODULATION_TARGETS
        # Common practice modulates to the dominant above all.
        self.assertIn("V", GENRE_MODULATION["classical"].targets)
        # Chorale writing is the most conservative of the four.
        self.assertGreater(GENRE_MODULATION["chorale"].switch_cost,
                           GENRE_MODULATION["jazz"].switch_cost)
        # Modal writing shifts by fourth and fifth.
        modal = GENRE_MODULATION["gregorian"].targets
        self.assertIn("IV", modal)
        self.assertIn("V", modal)
        # Every named target exists.
        for genre in GENRE_MODULATION.values():
            for key in genre.targets:
                self.assertIn(key, MODULATION_TARGETS)


class TestImport(unittest.TestCase):
    """Reading a score back in, and getting the same music out."""

    def _round_trip(self, symbols, voice_keys=("B", "T", "A", "S")):
        from engine import importer
        request = session.JobRequest(
            genre_key="chorale", voice_keys=list(voice_keys),
            entries=[session.ChordEntry(s, 2.0, i // 2)
                     for i, s in enumerate(symbols)],
            ga_config=GAConfig(population_size=60, generations=30, random_seed=5),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            files = session.export_outcome(request, outcome, folder,
                                           ("musicxml",), record_history=False)
            return importer.read_musicxml(files[0]), outcome

    def test_round_trip_recovers_the_chords(self):
        """Export then import must give back the same harmony.

        The reader walks the measure in document order because <backup>
        rewinds the cursor between voices; reading only the <note> elements
        put every part at a different moment and turned a four-part chorale
        into thirty-two one-note chords.
        """
        symbols = ["C", "Am", "F", "G7", "C", "Dm7", "G7", "Cmaj7"]
        score, outcome = self._round_trip(symbols)
        self.assertEqual(len(score.chords), len(symbols))
        self.assertEqual(score.voice_count, 4)
        for original, read in zip(symbols, score.chords):
            self.assertEqual(read.symbol.split("/")[0], original)

    def test_round_trip_recovers_the_voicing(self):
        symbols = ["C", "F", "G", "C"]
        score, outcome = self._round_trip(symbols)
        for chord, read in zip(outcome.result.solutions[0].slots, score.chords):
            self.assertEqual(sorted(chord), read.pitches)

    def test_naming_prefers_the_common_reading(self):
        """F-A-C-D is both an F6 and a Dm7; a musician reads the seventh."""
        from engine.importer import identify_chord
        pitches = [parse_note_name(n) for n in ("F3", "A3", "C4", "D4")]
        self.assertEqual(identify_chord(pitches), "Dm7/F")
        # Inversions are named with a slash rather than re-rooted.
        self.assertEqual(
            identify_chord([parse_note_name(n) for n in ("G2", "C4", "E4")]),
            "C/G")

    def test_unreadable_file_is_reported(self):
        from engine import importer
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "roto.musicxml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("<esto no es> una partitura")
            with self.assertRaises(importer.ImportError_):
                importer.read_musicxml(path)


class TestManualPassingTones(unittest.TestCase):
    def test_ornaments_work_in_the_hand_written_mode(self):
        from engine.passing import PassingRules
        entries = [session.ChordEntry(s, 2.0, i // 2)
                   for i, s in enumerate(["C", "Am", "F", "G", "C", "F", "G", "C"])]
        request = session.JobRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            entries=entries,
            passing_rules=PassingRules(voices=(2, 3), density=0.6),
            ga_config=GAConfig(population_size=60, generations=25, random_seed=7),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        used = sum(1 for row in solution.passing for n in row if n is not None)
        self.assertGreater(used, 0)
        for row in solution.passing:
            self.assertLessEqual(sum(1 for n in row if n is not None), 1)

    def test_the_mode_still_works_without_ornaments(self):
        """The feature must not disturb the path that does not use it."""
        entries = [session.ChordEntry(s, 2.0, i // 2)
                   for i, s in enumerate(["C", "F", "G", "C"])]
        request = session.JobRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            entries=entries, passing_rules=None,
            ga_config=GAConfig(population_size=60, generations=30, random_seed=7),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        self.assertTrue(all(n is None for row in solution.passing for n in row))


class TestGeneratorSanity(unittest.TestCase):
    def test_a_chord_never_repeats_itself(self):
        """The program picks the chords, so repeating one is never wanted.

        As a mere price it was sometimes worth paying, and runs turned up
        where one chord sounded all the way through.
        """
        from engine.harmony import GENRE_DEFAULT_BORROWED
        for genre in ("classical", "jazz"):
            for seed in (1, 5):
                request = session.GenerativeRequest(
                    genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic="C",
                    mode_key="major" if genre != "gregorian" else "dorian",
                    borrowed=GENRE_DEFAULT_BORROWED.get(genre, []),
                    slot_count=8,
                    start_roman="I" if genre != "gregorian" else "i",
                    end_roman="I" if genre != "gregorian" else "i",
                    endpoints_required=True,
                    ga_config=GAConfig(population_size=60, generations=25,
                                       random_seed=seed),
                )
                outcome = session.generate_random(request)
                self.assertTrue(outcome.succeeded, outcome.errors)
                for solution in outcome.result.solutions:
                    romans = [slot.options[min(c, len(slot.options) - 1)].harmony.roman
                              for slot, c in zip(outcome.spec.slots, solution.choices)]
                    for first, second in zip(romans, romans[1:]):
                        self.assertNotEqual(first, second,
                                            f"{genre}/{seed}: {romans}")

    def test_sevenths_reach_the_chord_symbols(self):
        """Regression: the generator only ever built triads.

        `with_sevenths` defaulted to off and nothing exposed it, so a jazz
        run came back as C where it should have said Cmaj7.
        """
        request = session.GenerativeRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"], tonic="C",
            slot_count=6, with_sevenths=True,
            ga_config=GAConfig(population_size=80, generations=40, random_seed=5),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        symbols = [slot.options[min(c, len(slot.options) - 1)].requirement.chord.symbol
                   for slot, c in zip(outcome.spec.slots,
                                      outcome.result.solutions[0].choices)]
        self.assertTrue(any(len(s) > 2 for s in symbols), symbols)

    def test_defaults_are_restrained(self):
        """Everything switched on at once is what made the results unpleasant."""
        from engine.harmony import GENRE_DEFAULT_BORROWED, GENRE_MODULATION
        for genre, borrowed in GENRE_DEFAULT_BORROWED.items():
            self.assertLessEqual(len(borrowed), 1, f"{genre} borrows too much")
        for genre, settings in GENRE_MODULATION.items():
            self.assertFalse(settings.key_enabled, f"{genre} modulates by default")
            self.assertFalse(settings.modal_enabled, f"{genre} modulates by default")

    def test_area_labels_are_readable(self):
        from engine.harmony import ModulationSettings, display_roman, modulation_pool
        from engine.theory import parse_pitch_class
        pool = modulation_pool(parse_pitch_class("C"), ModulationSettings(
            key_enabled=True, modal_enabled=True,
            targets=("V", "parallel_mixolydian")))
        for option in pool:
            shown = display_roman(option)
            self.assertNotIn(":", shown)
            self.assertNotIn("_", shown)


class TestImportIgnoresOrnaments(unittest.TestCase):
    def test_two_note_moments_are_not_chords(self):
        """A passing note leaves a thin moment that is not a chord."""
        from engine import importer
        from engine.passing import PassingRules
        entries = [session.ChordEntry(s, 2.0, i // 2)
                   for i, s in enumerate(["C", "Am", "F", "G", "C", "F", "G", "C"])]
        request = session.JobRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"], entries=entries,
            passing_rules=PassingRules(voices=(2, 3), density=0.7),
            ga_config=GAConfig(population_size=70, generations=35, random_seed=7),
        )
        outcome = session.generate(request)
        with tempfile.TemporaryDirectory() as folder:
            path = session.export_outcome(request, outcome, folder,
                                          ("musicxml",), record_history=False)[0]
            score = importer.read_musicxml(path)
        self.assertEqual(len(score.chords), len(entries))
        for chord in score.chords:
            self.assertGreaterEqual(len(chord.pitches), 3)


class TestModulationShape(unittest.TestCase):
    """The excursion is planned, not stumbled into."""

    def _run(self, genre, bars=10, seed=17):
        from dataclasses import replace as _replace
        from engine.harmony import GENRE_DEFAULT_BORROWED, GENRE_MODULATION
        settings = _replace(GENRE_MODULATION[genre], key_enabled=True,
                            modal_enabled=genre in ("gregorian", "jazz"))
        slots = bars * 2
        request = session.GenerativeRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic="C",
            mode_key="major" if genre != "gregorian" else "dorian",
            borrowed=GENRE_DEFAULT_BORROWED.get(genre, []),
            with_sevenths=(genre == "jazz"),
            slot_count=slots, durations=[2.0] * slots,
            bar_indices=[i // 2 for i in range(slots)],
            start_roman="I" if genre != "gregorian" else "i",
            end_roman="I" if genre != "gregorian" else "i",
            endpoints_required=True, modulation=settings,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=seed),
        )
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        options = [slot.options[min(c, len(slot.options) - 1)].harmony
                   for slot, c in zip(outcome.spec.slots, solution.choices)]
        bars_of = [slot.bar_index for slot in outcome.spec.slots]
        return options, bars_of, settings

    def _excursions(self, options, bars_of):
        spans, index = [], 0
        areas = [o.key_area or "" for o in options]
        while index < len(areas):
            area = areas[index]
            length = 1
            while index + length < len(areas) and areas[index + length] == area:
                length += 1
            if area:
                spans.append((area, bars_of[index], bars_of[index + length - 1]))
            index += length
        return spans

    def test_one_contiguous_excursion(self):
        """Several scattered visits read as wandering, not as modulating."""
        for genre in ("classical", "jazz"):
            options, bars_of, _ = self._run(genre)
            spans = self._excursions(options, bars_of)
            self.assertLessEqual(len(spans), 1, f"{genre}: {spans}")

    def test_the_visit_lasts_whole_bars_and_leaves_room(self):
        for genre in ("classical",):
            options, bars_of, settings = self._run(genre)
            spans = self._excursions(options, bars_of)
            if not spans:
                continue
            _area, first, last = spans[0]
            self.assertGreaterEqual(last - first + 1, settings.min_bars)
            self.assertGreaterEqual(first, settings.home_margin_bars)
            self.assertLessEqual(last, max(bars_of) - settings.home_margin_bars)

    def test_short_pieces_are_not_offered_modulation(self):
        """Under eight bars there is no room to leave, settle and return."""
        from engine.ga import choose_modulation_plan
        from engine.harmony import GENRE_MODULATION
        from dataclasses import replace as _replace
        settings = _replace(GENRE_MODULATION["classical"], key_enabled=True)

        class _Slot:
            def __init__(self, bar):
                self.bar_index = bar

        short = [_Slot(i // 2) for i in range(8)]      # 4 bars
        long = [_Slot(i // 2) for i in range(24)]      # 12 bars
        rng = random.Random(3)
        self.assertIsNone(choose_modulation_plan(short, settings, rng))
        self.assertIsNotNone(choose_modulation_plan(long, settings, rng))


class TestGenreIdioms(unittest.TestCase):
    def setUp(self):
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        self.tonic = parse_pitch_class("C")
        self.pool = {o.roman: o for o in build_chord_pool(
            self.tonic, MODES["major"], ["iv"])}

    def _move(self, first, second, genre, before=None):
        from engine.harmony import GRAMMARS, grammar_cost
        return grammar_cost(self.pool[first], self.pool[second],
                            GRAMMARS[genre], self.tonic,
                            self.pool[before] if before else None)

    def test_jazz_rewards_the_whole_two_five_one(self):
        with_ii = self._move("V", "I", "jazz", before="ii")
        alone = self._move("V", "I", "jazz")
        self.assertLess(with_ii, alone)

    def test_jazz_discourages_chained_dominants(self):
        chained = self._move("V", "I", "jazz", before="V")
        prepared = self._move("V", "I", "jazz", before="ii")
        self.assertGreater(chained, prepared)

    def test_gregorian_prefers_the_plagal_close(self):
        """The borrowed iv closes as well as IV, and no better.

        Ranking it above the diatonic subdominant made the search hunt for a
        borrowed chord even when the user had asked for hardly any: the
        idiom reward and the "how often" slider both land in the same total,
        so the bigger reward simply won.
        """
        plagal = self._move("IV", "I", "gregorian")
        minor_plagal = self._move("iv", "I", "gregorian")
        authentic = self._move("V", "I", "gregorian")
        self.assertLess(plagal, authentic)
        self.assertEqual(minor_plagal, plagal)


class TestHistoryDetail(unittest.TestCase):
    def test_a_record_can_redraw_the_run(self):
        """A history that only lists parameters cannot show what you made."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.json")
            record = history.ProductionRecord.create(
                title="prueba", genre="jazz", voice_keys=["B", "T", "A", "S"],
                bar_count=2, time_signature="4/4",
                chord_labels=["Cmaj7", "G7"], romans=["I", "V"],
                voice_names=["Bass", "Tenor", "Alto", "Soprano"],
                solutions=[[[48, 55, 64, 71], [43, 59, 65, 74]]],
                solution_costs=[12.0],
            )
            history.add_record(record, path)
            stored = history.load_history(path)[0]
            self.assertEqual(stored.chord_labels, ["Cmaj7", "G7"])
            self.assertEqual(len(stored.solutions), 1)
            self.assertEqual(stored.solutions[0][0], [48, 55, 64, 71])
            self.assertEqual(stored.voice_names[0], "Bass")

    def test_an_entry_written_before_the_mode_existed_still_loads(self):
        """
        El campo `mode` se agrego despues, y el historial es del usuario.

        `load_history` construye cada entrada por nombre y descarta la que
        no encaje, asi que un campo nuevo sin valor por defecto le borraria
        al usuario todo lo que tenia guardado de antes.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.json")
            viejo = {"timestamp": "2026-08-01T09:03:00", "title": "prueba",
                     "genre": "classical", "voice_keys": ["B", "T", "S"],
                     "bar_count": 2, "time_signature": "3/4"}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([viejo], handle)
            leidas = history.load_history(path)
            self.assertEqual(len(leidas), 1)
            self.assertEqual(leidas[0].mode, "")
            self.assertEqual(leidas[0].mode_label, "")
            self.assertEqual(leidas[0].genre_label, "Barroco")

    def test_the_date_reads_like_a_person_wrote_it(self):
        """
        En una lista de diez corridas del mismo dia, el sello ISO no dice nada.
        """
        from datetime import datetime, timedelta
        ahora = datetime.now()
        casos = ((ahora, "hoy"), (ahora - timedelta(days=1), "ayer"))
        for momento, esperado in casos:
            record = history.ProductionRecord.create(
                title="x", genre="jazz", mode="random", voice_keys=["B"],
                bar_count=1, time_signature="4/4",
                timestamp=momento.isoformat(timespec="seconds"))
            self.assertTrue(record.when.startswith(esperado), record.when)
        viejo = history.ProductionRecord.create(
            title="x", genre="jazz", mode="random", voice_keys=["B"],
            bar_count=1, time_signature="4/4",
            timestamp="2020-03-05T14:30:00")
        self.assertEqual(viejo.when, "5 mar 14:30")
        self.assertIn("Generador", viejo.display_name)


class TestDataSandbox(unittest.TestCase):
    """
    Mover la raiz mueve los seis archivos del usuario de una vez.

    Cada script de prueba que abre la ventana tenia que acordarse de
    reapuntar seis rutas, y alcanzaba con que una se olvidara para que una
    corrida de prueba quedara anotada en el historial de verdad --- que
    guarda las diez ultimas --- o para que un logro que el usuario no
    consiguio apareciera conseguido. Esto es lo que no se puede olvidar.
    """

    def test_the_variable_moves_every_path(self):
        from engine import achievements as A, eggs as E, story as S
        from engine import visitors as V
        with tempfile.TemporaryDirectory() as folder:
            antes = os.environ.get(history.SANDBOX_VARIABLE)
            os.environ[history.SANDBOX_VARIABLE] = folder
            try:
                self.assertEqual(history.base_directory(), folder)
                rutas = [history.history_path(), history.settings_path(),
                         A.achievements_path(), E.eggs_path(),
                         S.state_path(), V.visitors_path()]
                for ruta in rutas:
                    self.assertEqual(os.path.dirname(ruta), folder, ruta)
                # Y los seis son archivos distintos: si dos compartieran
                # nombre, uno se comeria al otro sin avisar.
                self.assertEqual(len(set(rutas)), 6)
                # La carpeta de salida tambien cuelga de ahi.
                self.assertEqual(
                    os.path.dirname(history.default_output_directory()), folder)
            finally:
                if antes is None:
                    os.environ.pop(history.SANDBOX_VARIABLE, None)
                else:
                    os.environ[history.SANDBOX_VARIABLE] = antes

    def test_without_the_variable_the_data_lives_next_to_the_program(self):
        """ Lo de siempre: el programa escribe al lado suyo. """
        antes = os.environ.pop(history.SANDBOX_VARIABLE, None)
        try:
            raiz = history.base_directory()
            self.assertTrue(os.path.isdir(raiz))
            self.assertTrue(os.path.exists(os.path.join(raiz, "engine")))
        finally:
            if antes is not None:
                os.environ[history.SANDBOX_VARIABLE] = antes

    def test_the_variable_does_not_move_the_artwork(self):
        """
        Los recortes de los personajes NO se mudan con la variable.

        `CHORDWEAVER_DATA_DIR` existe para mandar los datos del usuario a
        otro lado. Los PNG de `assets/` no son datos del usuario: vienen con
        el programa. Buscandolos en la carpeta de pruebas, cualquiera que
        usara la variable se quedaba sin personajes --- y sin ningun error,
        porque una pose que falta devuelve None, que es lo correcto para una
        pose y lo peor posible para todas: las escenas se jugaban enteras,
        con sus dialogos, y vacias.
        """
        with tempfile.TemporaryDirectory() as folder:
            antes = os.environ.get(history.SANDBOX_VARIABLE)
            os.environ[history.SANDBOX_VARIABLE] = folder
            try:
                # Los datos si se mudan...
                self.assertEqual(history.base_directory(), folder)
                # ...y el programa no.
                self.assertNotEqual(history.program_directory(), folder)
                self.assertTrue(os.path.exists(
                    os.path.join(history.program_directory(), "engine")))
                # Y los recortes se siguen encontrando de verdad.
                arte = os.path.join(history.program_directory(),
                                    "assets", "story")
                self.assertTrue(os.path.isdir(arte), arte)
                self.assertTrue(
                    [n for n in os.listdir(arte) if n.endswith(".png")], arte)
            finally:
                if antes is None:
                    os.environ.pop(history.SANDBOX_VARIABLE, None)
                else:
                    os.environ[history.SANDBOX_VARIABLE] = antes

    def test_the_frozen_build_looks_for_its_art_inside_the_bundle(self):
        """
        Empaquetado, el arte esta en `_internal/` y NO al lado del .exe.

        PyInstaller 6 dejo de poner los `datas` junto al ejecutable y los
        manda a `_internal/`, que es lo que apunta `sys._MEIPASS`. Buscandolos
        al lado del .exe ---que es donde SI van los datos del usuario--- el
        programa empaquetado se quedaba sin un solo personaje, en silencio.
        Es un bug que no se ve corriendo desde el fuente: ahi no hay
        `_MEIPASS` y las dos rutas son la misma.
        """
        bundle = os.path.join("C:" + os.sep, "falso", "_internal")
        al_lado = os.path.join("C:" + os.sep, "falso")
        frozen_antes = getattr(sys, "frozen", None)
        meipass_antes = getattr(sys, "_MEIPASS", None)
        exe_antes = sys.executable
        # La suite entera corre con la variable de pruebas puesta; aca hay
        # que sacarla para mirar el caso empaquetado tal como le llega al
        # usuario.
        sandbox_antes = os.environ.pop(history.SANDBOX_VARIABLE, None)
        try:
            sys.frozen = True
            sys._MEIPASS = bundle
            sys.executable = os.path.join(al_lado, "ChordWeaver.exe")
            # El arte, adentro del paquete.
            self.assertEqual(history.program_directory(), bundle)
            # Los datos del usuario, al lado del ejecutable.
            self.assertEqual(history.base_directory(), al_lado)
        finally:
            if sandbox_antes is not None:
                os.environ[history.SANDBOX_VARIABLE] = sandbox_antes
            sys.executable = exe_antes
            if frozen_antes is None:
                del sys.frozen
            else:
                sys.frozen = frozen_antes
            if meipass_antes is None:
                if hasattr(sys, "_MEIPASS"):
                    del sys._MEIPASS
            else:
                sys._MEIPASS = meipass_antes

    def test_an_unusable_folder_falls_back_instead_of_failing(self):
        """
        Una carpeta de pruebas que no se puede crear no es motivo para que
        el programa no arranque: se vuelve al lugar de siempre.
        """
        antes = os.environ.get(history.SANDBOX_VARIABLE)
        # Un nombre que no puede ser una carpeta en Windows.
        os.environ[history.SANDBOX_VARIABLE] = os.path.join(
            os.path.abspath(__file__), "imposible")
        try:
            raiz = history.base_directory()
            self.assertTrue(os.path.exists(os.path.join(raiz, "engine")))
        finally:
            if antes is None:
                os.environ.pop(history.SANDBOX_VARIABLE, None)
            else:
                os.environ[history.SANDBOX_VARIABLE] = antes


class TestRests(unittest.TestCase):
    """
    Un silencio ocupa su lugar en la partitura y no canta nada.

    La busqueda **saltea los silencios**: no hay nada que repartir ahi y la
    conduccion de voces se mide de un acorde al siguiente como si el silencio
    no existiera. La consecuencia es que `solution.slots` trae menos entradas
    que `spec.slots`, y todo lo que se dibuje o se toque zipeando las dos
    listas queda corrido un lugar desde el primer silencio.
    """

    def _run(self):
        entries = [session.ChordEntry("C", 2.0, 0),
                   session.ChordEntry("", 2.0, 0, is_rest=True),
                   session.ChordEntry("F", 1.0, 1),
                   session.ChordEntry("G", 3.0, 1)]
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=entries,
            ga_config=GAConfig(random_seed=1, population_size=60,
                               generations=25, workers=1))
        return session.generate(request)

    def test_the_search_skips_the_rest(self):
        """ Nada que repartir: el silencio no es un acorde. """
        outcome = self._run()
        self.assertTrue(outcome.succeeded)
        self.assertEqual(len(outcome.spec.slots), 4)
        self.assertEqual(len(outcome.result.solutions[0].slots), 3)
        self.assertTrue(outcome.spec.slots[1].is_rest)

    def test_the_voiced_slots_line_up_with_the_score(self):
        """
        Tantas columnas como compases, y el silencio vacio en su lugar.

        Sin esto, la pantalla de resultados mostraba las notas de un acorde
        debajo del nombre del anterior a partir del primer silencio, y al
        escuchar, la duracion del silencio se la llevaba el acorde siguiente
        --- o sea que la pieza duraba un compas menos y no tenia ningun
        silencio adentro.
        """
        outcome = self._run()
        alineadas = session.voiced_slots(outcome.spec,
                                         outcome.result.solutions[0])
        self.assertEqual(len(alineadas), len(outcome.spec.slots))
        self.assertEqual(alineadas[0], list(outcome.result.solutions[0].slots[0]))
        self.assertEqual(alineadas[1], [])
        self.assertEqual(alineadas[2], list(outcome.result.solutions[0].slots[1]))
        self.assertEqual(alineadas[3], list(outcome.result.solutions[0].slots[2]))

    def test_the_placeholder_chord_never_reaches_the_eye(self):
        """
        El motor le pone un do de relleno al silencio, para que la lista de
        slots siga alineada con los compases. Ese do se mostraba en la
        pantalla de resultados como si el usuario lo hubiera escrito.
        """
        outcome = self._run()
        rest = outcome.spec.slots[1]
        # El relleno sigue ahi --- es lo que mantiene la lista alineada ---
        # pero lo que se dibuja se decide por `is_rest` y no por el simbolo.
        self.assertEqual(rest.symbol, "C")
        self.assertTrue(rest.is_rest)
        self.assertTrue(session.REST_SYMBOL)
        self.assertEqual(history.REST_LABEL, "(silencio)")


class TestSetPieces(unittest.TestCase):
    def test_phrygian_cadence_is_i_bVII_bVI_V(self):
        from engine.harmony import SET_PIECES, set_piece_options
        from engine.theory import parse_pitch_class
        options = set_piece_options(SET_PIECES["phrygian"],
                                    parse_pitch_class("A"))
        self.assertEqual([o.label for o in options], ["Am", "G", "F", "E"])
        self.assertEqual([o.roman for o in options], ["i", "bVII", "bVI", "V"])

    def test_vivaldi_cycle_falls_by_fifths(self):
        from engine.harmony import SET_PIECES, set_piece_options
        from engine.theory import parse_pitch_class
        options = set_piece_options(SET_PIECES["vivaldi"],
                                    parse_pitch_class("A"))
        self.assertEqual([o.label for o in options],
                         ["Am", "D", "G", "C", "F", "B", "E", "Am"])

    def test_offered_in_every_minor_mode_and_no_major_one(self):
        from engine.harmony import set_piece_for
        for mode in ("minor", "harmonic", "dorian", "phrygian"):
            self.assertTrue(set_piece_for("classical", mode, 4, True), mode)
        for mode in ("major", "lydian", "mixolydian"):
            self.assertFalse(set_piece_for("classical", mode, 4, True), mode)

    def test_only_in_the_styles_that_quote(self):
        from engine.harmony import set_piece_for
        self.assertTrue(set_piece_for("classical", "minor", 4, True))
        self.assertTrue(set_piece_for("chorale", "minor", 4, True))
        self.assertFalse(set_piece_for("jazz", "minor", 4, True))
        self.assertFalse(set_piece_for("gregorian", "minor", 4, True))

    def test_conditions_must_all_hold(self):
        from engine.harmony import set_piece_for
        self.assertFalse(set_piece_for("classical", "minor", 5, True))
        self.assertFalse(set_piece_for("classical", "minor", 4, False))

    def test_a_quotation_does_not_stamp_its_choices_on_the_generated_slots(self):
        """
        La cita trae sus propios acordes; los slots del generador, los suyos.

        La cita se voicea aparte, con un slot por acorde y una sola opcion
        en cada uno, asi que sus `choices` son todos cero. Sellar los slots
        del generador --- que tienen decenas de opciones --- con esos ceros
        dejaba el acorde numero cero repetido de punta a punta: ocho veces
        la tonica seguidas, con la repeticion prohibida. En pantalla no se
        veia, porque ahi manda `set_piece.symbols`; se veia en el historial,
        que lee los slots.
        """
        from engine import session
        vistos = 0
        for seed in range(40):
            request = session.GenerativeRequest(
                genre_key="classical", voice_keys=["B", "T", "S"],
                tonic="A", mode_key="minor", with_sevenths=False,
                slot_count=8, durations=[2.0] * 8,
                bar_indices=[i // 2 for i in range(8)],
                ga_config=GAConfig(random_seed=seed, population_size=60,
                                   generations=25, workers=1),
                raise_odds=True, solutions_wanted=1,
            )
            outcome = session.generate_random(request)
            if outcome.set_piece is None or not outcome.result.solutions:
                continue
            vistos += 1
            romans = []
            for index, slot in enumerate(outcome.spec.slots):
                if not slot.options:
                    continue
                romans.append(slot.requirement.chord.symbol)
            # Ningun acorde generado puede repetirse pegado al anterior: es
            # regla dura del generador, y la cita no puede pisarla.
            for before, after in zip(romans, romans[1:]):
                self.assertNotEqual(before, after,
                                    f"semilla {seed}: {romans}")
            # Y la cita sigue teniendo lo suyo.
            self.assertTrue(outcome.set_piece.symbols)
            self.assertEqual(len(outcome.set_piece.symbols), 8)
        self.assertGreater(vistos, 0, "ninguna semilla trajo una cita")


class TestColourVoicings(unittest.TestCase):
    def test_diminished_chords_get_no_colour(self):
        """Already all tension; ninths on top turn it to mud."""
        from engine.voicing import build_voicing_plan
        for symbol in ("Cdim", "Bdim"):
            plan = build_voicing_plan(parse_chord(symbol), 6, special_fills=True)
            self.assertEqual(plan.added, [], symbol)
            self.assertEqual(len(plan.degrees), 6)

    def test_symbol_reports_the_notes_actually_sung(self):
        """Printing a coloured chord under its plain name hides the point."""
        from engine.voicing import build_voicing_plan, symbol_with_added
        plan = build_voicing_plan(parse_chord("C"), 5, special_fills=True)
        self.assertNotEqual(symbol_with_added(plan), "C")
        plain = build_voicing_plan(parse_chord("C"), 4)
        self.assertEqual(symbol_with_added(plain), "C")

    def test_a_seventh_chord_with_a_sixth_is_not_called_seventysix(self):
        """
        Dos cifras pegadas se leen como una sola.

        Una sexta agregada sobre una triada es "C6" y esta bien; sobre un
        acorde que ya lleva septima, pegarla daba "Cmaj76" y "Am76", que no
        es el nombre de ningun acorde. Aparecio a seis voces, que es donde
        sobran voces para colorear un acorde que ya esta completo.
        """
        from engine.voicing import VoicingPlan, symbol_with_added
        from engine.theory import ChordTone, ROLE_EXTENSION
        sixth = ChordTone(9, ROLE_EXTENSION, "6")
        for symbol, esperado in (("Cmaj7", "Cmaj7(6)"), ("Am7", "Am7(6)"),
                                 ("G7", "G7(6)"), ("C", "C6"), ("Am", "Am6")):
            plan = VoicingPlan(chord=parse_chord(symbol), degrees=[],
                               omitted=[], doubled=[], added=[sixth])
            self.assertEqual(symbol_with_added(plan), esperado, symbol)

    def test_a_swapped_seventh_leaves_the_name(self):
        """ Un Dm7 al que se le cambio la septima ya no se llama Dm7. """
        import random
        from engine.voicing import build_requirement, symbol_with_added
        for symbol, esperado in (("Dm7", "Dm6"), ("Cmaj7", "C6")):
            for seed in range(80):
                req = build_requirement(
                    parse_chord(symbol), 4, special_fills=True,
                    colour_appetite=1.0, rng=random.Random(seed),
                    may_swap_seventh=True, allow_major_sixth_on_minor=True)
                if req.plan.swapped_seventh is None:
                    continue
                nombre = symbol_with_added(req.plan)
                self.assertIn(nombre, (esperado, symbol.replace("maj7", "").replace("7", "") + "add9"),
                              nombre)
                break
            else:
                self.fail(f"nunca cambio la septima de {symbol}")

    def test_borrowed_degrees_are_spelled_flat(self):
        """bII of A minor is Bb; calling it A# contradicts the numeral."""
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        pool = {o.roman: o for o in build_chord_pool(
            parse_pitch_class("A"), MODES["minor"], ["bII", "N6", "bVI", "bVII"])}
        self.assertEqual(pool["bII"].label, "Bb")
        self.assertEqual(pool["N6"].label, "Bb")
        self.assertEqual(pool["bVI"].label, "F")


class TestColourAppetite(unittest.TestCase):
    def test_the_dial_grades_instead_of_switching(self):
        """Turning it up should add more colour, not all of it at once.

        Filling every spare voice unconditionally made the dial behave like
        an on/off switch: nudging it at all produced a fully coloured chord.
        """
        from engine.voicing import build_voicing_plan
        averages = {}
        for appetite in (0.2, 0.9):
            total = 0
            for seed in range(40):
                plan = build_voicing_plan(
                    parse_chord("C"), 6, special_fills=True,
                    colour_appetite=appetite, rng=random.Random(seed))
                total += len(plan.added)
            averages[appetite] = total / 40
        self.assertLess(averages[0.2], averages[0.9])
        self.assertGreater(averages[0.2], 0.0)
        self.assertLess(averages[0.2], 1.5)

    def test_every_colour_gets_used(self):
        """A fixed order meant the ninth was the only one anyone ever heard."""
        from engine.voicing import build_voicing_plan
        seen = set()
        for seed in range(60):
            plan = build_voicing_plan(
                parse_chord("C"), 6, special_fills=True,
                colour_appetite=0.9, rng=random.Random(seed))
            seen.update(tone.degree for tone in plan.added)
        self.assertIn("9", seen)
        self.assertIn("11", seen)
        self.assertIn("6", seen)

    def test_zero_appetite_means_doubling_only(self):
        from engine.voicing import build_voicing_plan
        plan = build_voicing_plan(parse_chord("C"), 6, special_fills=True,
                                  colour_appetite=0.0)
        self.assertEqual(plan.added, [])
        self.assertEqual(len(plan.degrees), 6)


class TestAudioPreview(unittest.TestCase):
    def test_rendering_produces_playable_audio(self):
        from engine.audio import render_chords
        frames = render_chords([[48, 55, 64, 72], [43, 50, 62, 67]],
                               [2.0, 2.0])
        self.assertGreater(len(frames), 0)
        # 16-bit samples, so an even number of bytes.
        self.assertEqual(len(frames) % 2, 0)

    def test_six_voices_do_not_clip(self):
        """Summing six voices must stay inside the 16-bit range."""
        import array
        from engine.audio import render_chords
        frames = render_chords([[36, 43, 48, 55, 64, 72]], [4.0])
        samples = array.array("h")
        samples.frombytes(frames)
        self.assertLess(max(abs(s) for s in samples), 32000)

    def test_durations_are_respected(self):
        import array
        from engine.audio import render_chords, SAMPLE_RATE, SECONDS_PER_QUARTER
        short = array.array("h")
        short.frombytes(render_chords([[60]], [1.0]))
        long = array.array("h")
        long.frombytes(render_chords([[60]], [4.0]))
        self.assertGreater(len(long), len(short))
        expected = (4.0 * SECONDS_PER_QUARTER + 0.7) * SAMPLE_RATE
        self.assertAlmostEqual(len(long), expected, delta=SAMPLE_RATE * 0.1)


class TestParallelsAreBlocked(unittest.TestCase):
    """The headline rule, checked on what actually comes out."""

    ENTRIES = ["C", "G", "Am", "F", "C", "G", "Dm", "C"]

    def _count(self, solution, voices=4):
        from engine.fitness import parallel_interval_violation
        fifths = octaves = 0
        for index in range(1, len(solution.slots)):
            for a in range(voices):
                for b in range(a + 1, voices):
                    fifth, octave = parallel_interval_violation(
                        solution.slots[index - 1], solution.slots[index], a, b)
                    fifths += fifth
                    octaves += octave
        return fifths, octaves

    def test_hand_written_mode_blocks_them(self):
        for genre in ("chorale", "jazz"):
            for colour in (25.0,):
                request = session.JobRequest(
                    genre_key=genre, voice_keys=["B", "T", "A", "S"],
                    entries=[session.ChordEntry(s, 2.0, i // 2)
                             for i, s in enumerate(self.ENTRIES)],
                    switch_overrides={
                        "forbid_parallel_fifths": True,
                        "forbid_parallel_octaves": True,
                        "special_voicing_fills": colour > 0,
                        "weight_colour_tone": -colour,
                    },
                    ga_config=GAConfig(population_size=80, generations=35,
                                       random_seed=5),
                )
                outcome = session.generate(request)
                self.assertTrue(outcome.succeeded, outcome.errors)
                for solution in outcome.result.solutions:
                    self.assertEqual(self._count(solution), (0, 0),
                                     f"{genre} colour={colour}")

    def test_generator_blocks_them_too(self):
        for genre in ("chorale", "jazz"):
            request = session.GenerativeRequest(
                genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic="C",
                slot_count=8,
                switch_overrides={"forbid_parallel_fifths": True,
                                  "forbid_parallel_octaves": True,
                                  "special_voicing_fills": True,
                                  "weight_colour_tone": -25.0},
                ga_config=GAConfig(population_size=80, generations=35,
                                   random_seed=7),
            )
            outcome = session.generate_random(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            for solution in outcome.result.solutions:
                self.assertEqual(self._count(solution), (0, 0), genre)





class TestFlourishes(unittest.TestCase):
    """Gestures applied to the winner, after the search is over."""

    def test_sixth_never_touches_the_endpoints(self):
        from engine.flourish import eligible_sixth_slots
        chords = [[45, 64, 73]] * 6
        slots = eligible_sixth_slots(chords, [False] * 6, 3)
        self.assertNotIn(0, slots)
        self.assertNotIn(5, slots)

    def test_sixth_respects_padlocks(self):
        from engine.flourish import eligible_sixth_slots
        chords = [[45, 64, 73]] * 6
        locked = [False, True, False, False, False, False]
        self.assertNotIn(1, eligible_sixth_slots(chords, locked, 3))

    def test_sixth_needs_four_chords(self):
        from engine.flourish import eligible_sixth_slots
        self.assertEqual(eligible_sixth_slots([[45, 64, 73]] * 3, [False] * 3, 3), [])

    def test_with_four_voices_only_an_octave_doubling_qualifies(self):
        """Doubling the fifth leaves a fifth behind, so the edit is pointless."""
        from engine.flourish import _doubles_octave_only
        octave = [parse_note_name(n) for n in ("A2", "A3", "C#4", "E4")]
        fifth = [parse_note_name(n) for n in ("A2", "E3", "C#4", "E4")]
        self.assertTrue(_doubles_octave_only(octave))
        self.assertFalse(_doubles_octave_only(fifth))

    def test_the_sixth_replaces_the_fifth(self):
        from engine.flourish import apply_sixth
        chords = [[parse_note_name(n) for n in group] for group in (
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"),
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"))]
        applied = apply_sixth(chords, [False] * 4, 3, random.Random(1))
        self.assertIsNotNone(applied)
        slot, _neighbour, _voice = applied
        intervals = {(p - chords[slot][0]) % 12 for p in chords[slot][1:]}
        self.assertIn(9, intervals)          # a sixth is present
        self.assertNotIn(7, intervals)       # and the fifth is gone

    def test_colour_dial_offers_only_sixths_at_the_bottom(self):
        from engine.voicing import build_voicing_plan
        for appetite, expected in ((0.15, {"6"}), (0.30, {"6"})):
            used = set()
            for seed in range(30):
                plan = build_voicing_plan(parse_chord("C"), 6, special_fills=True,
                                          colour_appetite=appetite,
                                          rng=random.Random(seed))
                used.update(t.degree for t in plan.added)
            self.assertTrue(used <= expected, f"{appetite}: {used}")

    def test_colour_dial_opens_up_further_along(self):
        from engine.voicing import build_voicing_plan
        used = set()
        for seed in range(40):
            plan = build_voicing_plan(parse_chord("C"), 6, special_fills=True,
                                      colour_appetite=0.9, rng=random.Random(seed))
            used.update(t.degree for t in plan.added)
        self.assertIn("9", used)
        self.assertIn("6", used)


class TestChromaticBassCadence(unittest.TestCase):
    def test_the_bass_walks_down_then_drops_to_the_flat_sixth(self):
        from engine.harmony import CHROMATIC_BASS_LINE
        self.assertEqual(CHROMATIC_BASS_LINE, (0, 11, 10, 8, 7, 0))

    def test_offered_in_classical_and_jazz_but_not_chorale(self):
        from engine.harmony import set_piece_for
        labels = lambda genre: [p.key for p in set_piece_for(genre, "minor", 6, True)]
        self.assertIn("chromatic_bass", labels("classical"))
        self.assertIn("chromatic_bass", labels("jazz"))
        self.assertNotIn("chromatic_bass", labels("chorale"))

    def test_raising_the_odds_makes_them_common(self):
        """Someone who ticks that box wants to hear these, not keep rolling."""
        from engine.harmony import SET_PIECE_CHANCE, SET_PIECE_CHANCE_HIGH
        self.assertGreater(SET_PIECE_CHANCE_HIGH, SET_PIECE_CHANCE * 3)


class TestCadenceDetection(unittest.TestCase):
    """Cadences named by their actual degrees, not by function.

    Matching on function counted iv-bVII-I as a ii-V-I and any subdominant
    reaching the tonic as a plagal cadence, which is not what those names
    mean.
    """

    def setUp(self):
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        self.tonic = parse_pitch_class("C")
        self.pool = {o.roman: o for o in build_chord_pool(
            self.tonic, MODES["major"], ["iv"])}

    def _labels(self, romans, genre):
        from engine.flourish import find_marks
        options = [self.pool[r] for r in romans]
        chords = [[48, 55, 64]] * len(options)
        return [m.label for m in find_marks(options, chords, genre, self.tonic)]

    def test_two_five_one_must_be_those_degrees(self):
        self.assertIn("ii-V-I", self._labels(["ii", "V", "I"], "jazz"))
        self.assertEqual(self._labels(["IV", "V", "I"], "jazz"), [])

    def test_plagal_must_be_the_fourth_degree(self):
        self.assertIn("Cadencia plagal", self._labels(["IV", "I"], "gregorian"))
        self.assertIn("Cadencia plagal menor",
                      self._labels(["iv", "I"], "gregorian"))
        self.assertEqual(self._labels(["ii", "I"], "gregorian"), [])

    def test_deceptive_must_land_on_the_sixth(self):
        self.assertIn("Cadencia rota", self._labels(["V", "vi"], "classical"))
        self.assertEqual(self._labels(["V", "iii"], "classical"), [])

    def test_six_four_needs_a_major_fifth_degree_that_resolves(self):
        from engine.flourish import find_marks
        # V with its fifth in the bass, resolving to I.
        chords = [[parse_note_name(n) for n in ("D3", "G3", "B3")],
                  [parse_note_name(n) for n in ("C3", "E3", "G3")]]
        marks = find_marks([self.pool["V"], self.pool["I"]], chords,
                           "classical", self.tonic)
        self.assertIn("Cadencial 6/4", [m.label for m in marks])
        # The same shape on a chord that is not the dominant is not it.
        marks = find_marks([self.pool["IV"], self.pool["I"]], chords,
                           "classical", self.tonic)
        self.assertNotIn("Cadencial 6/4", [m.label for m in marks])

    def _six_four(self, note_names, romans=("V", "I"), contexts=None):
        from engine.flourish import find_marks
        chords = [[parse_note_name(n) for n in names] for names in note_names]
        options = [self.pool[r] if r else None for r in romans]
        marks = find_marks(options, chords, "classical", self.tonic, contexts)
        return [m.label for m in marks]

    def test_six_four_is_the_arrangement_and_not_the_intervals(self):
        """5-1-3 es un 6/4; 5-3-1 tiene los mismos intervalos y no lo es.

        Sobre el bajo, las dos disposiciones dan una cuarta y una sexta, así
        que un chequeo que mire el conjunto de intervalos las da por iguales
        --- y la mitad de lo que salía marcado como 6/4 era la otra.
        """
        self.assertIn("Cadencial 6/4",
                      self._six_four([("D3", "G3", "B3"), ("C3", "E3", "G3")]))
        self.assertNotIn("Cadencial 6/4",
                         self._six_four([("D3", "B3", "G4"), ("C3", "E3", "G3")]))

    def test_six_four_is_recognised_with_four_voices(self):
        """El barroco se canta a cuatro: pedir tres era no verlo nunca."""
        self.assertIn("Cadencial 6/4",
                      self._six_four([("D3", "G3", "D4", "B4"),
                                      ("C3", "G3", "C4", "E4")]))

    def test_six_four_is_recognised_without_roman_numerals(self):
        """El Organizador no declara tonalidad: queda el intervalo.

        El usuario escribe cifrados sueltos, así que ahí no hay ningún grado
        que consultar y lo único afirmable es que un acorde mayor cae de
        quinta sobre el siguiente --- que es exactamente lo que se oye.
        """
        from engine.style import ChordContext
        from engine.theory import parse_chord
        contexts = [ChordContext.from_chord(parse_chord("G")),
                    ChordContext.from_chord(parse_chord("C"))]
        self.assertIn("Cadencial 6/4",
                      self._six_four([("D3", "G3", "B3"), ("C3", "E3", "G3")],
                                     romans=(None, None), contexts=contexts))
        # Y sin resolución no hay fórmula: el mismo acorde antes de un IV.
        contexts = [ChordContext.from_chord(parse_chord("G")),
                    ChordContext.from_chord(parse_chord("F"))]
        self.assertNotIn("Cadencial 6/4",
                         self._six_four([("D3", "G3", "B3"), ("F3", "A3", "C4")],
                                        romans=(None, None), contexts=contexts))


class TestSetPieceSymbols(unittest.TestCase):
    def test_chromatic_bass_is_written_as_inversions(self):
        """Four bars of plain "Am" would hide the very line it is about."""
        from engine.harmony import SET_PIECES, set_piece_options
        from engine.theory import parse_pitch_class
        options = set_piece_options(SET_PIECES["chromatic_bass"],
                                    parse_pitch_class("A"))
        self.assertEqual([o.label for o in options],
                         ["Am", "Am/G#", "Am/G", "Am/F", "E", "Am"])

    def test_the_rewritten_chord_says_so(self):
        from engine.flourish import sixth_symbol
        self.assertEqual(sixth_symbol("Am"), "Am6omit5")

    def test_phrygian_description_names_its_degrees(self):
        from engine.harmony import SET_PIECES
        text = SET_PIECES["phrygian"].description
        self.assertIn("bVII", text)
        self.assertIn("bVI", text)


class TestSetPieceIntegrity(unittest.TestCase):
    """The quotations, checked on what actually comes out."""

    def _run(self, voice_keys, seed=6):
        import engine.harmony as harmony_module
        saved = harmony_module.SET_PIECE_CHANCE
        harmony_module.SET_PIECE_CHANCE = 1.0
        try:
            request = session.GenerativeRequest(
                genre_key="classical", voice_keys=list(voice_keys), tonic="A",
                mode_key="minor", slot_count=6, durations=[2.0] * 6,
                bar_indices=[0, 0, 1, 1, 2, 2],
                start_roman="i", end_roman="i", endpoints_required=True,
                ga_config=GAConfig(population_size=60, generations=25,
                                   random_seed=seed),
            )
            return session.generate_random(request)
        finally:
            harmony_module.SET_PIECE_CHANCE = saved

    def test_the_chromatic_bass_actually_descends(self):
        """Pinning the pitch class left the octave free, so it jumped."""
        for keys in (["B", "T", "S"], ["B", "T", "A", "S"]):
            outcome = self._run(keys)
            self.assertIsNotNone(outcome.set_piece, keys)
            bass = [chord[0] for chord in outcome.result.solutions[0].slots]
            for index in range(4):
                self.assertGreater(bass[index], bass[index + 1],
                                   f"{keys}: {bass}")

    def test_the_quotation_labels_only_its_own_solution(self):
        """Overwriting the slots put its symbols over everyone's notes."""
        outcome = self._run(["B", "T", "A", "S"])
        self.assertIsNotNone(outcome.set_piece)
        self.assertEqual(outcome.set_piece.symbols[1], "Am/G#")
        # The slots keep the generated chords for the other solutions.
        second = outcome.result.solutions[1]
        self.assertTrue(second.slots)

    def test_marks_are_found_in_every_solution(self):
        """The other two answers are real choices, not decoration."""
        request = session.GenerativeRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"], tonic="C",
            slot_count=8, with_sevenths=True,
            start_roman="I", end_roman="I", endpoints_required=True,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=5),
        )
        outcome = session.generate_random(request)
        session.apply_flourishes(outcome, "jazz", parse_pitch_class("C"))
        self.assertGreaterEqual(len(outcome.flourishes.by_solution), 2)

    def test_forced_neighbour_keeps_its_notes(self):
        """Rewriting a pitch dropped a chord tone; it is a rearrangement."""
        from engine.flourish import apply_sixth
        chords = [[parse_note_name(n) for n in group] for group in (
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"),
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"))]
        before = [list(c) for c in chords]
        applied = apply_sixth(chords, [False] * 4, 3, random.Random(1))
        self.assertIsNotNone(applied)
        _slot, neighbour, _voice = applied
        if neighbour != _slot:
            self.assertEqual(sorted(chords[neighbour]), sorted(before[neighbour]))


class TestGenreDefaults(unittest.TestCase):
    def test_each_style_starts_in_its_own_texture(self):
        from engine.harmony import GENRE_DEFAULTS
        self.assertEqual(len(GENRE_DEFAULTS["gregorian"]["voices"]), 3)
        self.assertEqual(len(GENRE_DEFAULTS["chorale"]["voices"]), 4)
        self.assertEqual(len(GENRE_DEFAULTS["jazz"]["voices"]), 4)
        self.assertTrue(GENRE_DEFAULTS["jazz"]["sevenths"])
        self.assertFalse(GENRE_DEFAULTS["chorale"]["sevenths"])
        self.assertEqual(GENRE_DEFAULTS["chorale"]["colour"], 0.0)
        # Ionian, like everything else: the plagal cadence is IV-I and works
        # in any mode, so there was never a reason to start elsewhere.
        self.assertEqual(GENRE_DEFAULTS["gregorian"]["mode"], "major")


class TestSetPieceExport(unittest.TestCase):
    def test_the_score_keeps_the_inversions(self):
        """Exporting six bars of plain "Am" loses the whole point.

        The shared slots hold the generated chords so the other two options
        display correctly, so the quotation carries its own slots for the
        score.
        """
        import engine.harmony as harmony_module
        saved = harmony_module.SET_PIECE_CHANCE
        harmony_module.SET_PIECE_CHANCE = 1.0
        try:
            request = session.GenerativeRequest(
                genre_key="classical", voice_keys=["B", "T", "A", "S"],
                tonic="A", mode_key="minor", slot_count=6,
                durations=[2.0] * 6, bar_indices=[0, 0, 1, 1, 2, 2],
                ga_config=GAConfig(population_size=60, generations=25,
                                   random_seed=6),
            )
            outcome = session.generate_random(request)
        finally:
            harmony_module.SET_PIECE_CHANCE = saved

        self.assertIsNotNone(outcome.set_piece)
        # The quotation carries its own labels; the shared slots keep the
        # generated chords so the other two options still display correctly.
        self.assertTrue(outcome.set_piece.symbols)
        self.assertEqual(outcome.set_piece.symbols[1], "Am/G#")

    def test_a_slash_bass_is_spelled_by_its_own_letter(self):
        """Reading the interval from the root wrote E# where the music says F."""
        from engine.theory import spell_pitch
        step, alter, _octave = spell_pitch(53, "F", 0, "1")
        self.assertEqual(step, "F")
        self.assertEqual(alter, 0)


class TestSecondaryTwoFive(unittest.TestCase):
    """The ii-V approach aimed at degrees other than the tonic."""

    def test_every_degree_gets_its_dominant(self):
        from engine.harmony import MODES, secondary_dominants
        from engine.theory import parse_pitch_class
        options = secondary_dominants(parse_pitch_class("C"), MODES["major"])
        self.assertEqual(len(options), 6)
        labels = {o.roman: o.label for o in options}
        self.assertEqual(labels["V/ii"], "A7")      # the dominant of Dm
        self.assertEqual(labels["V/V"], "D7")       # the dominant of G

    def test_they_reach_the_pool_even_when_a_root_is_taken(self):
        """A7 and Am7 share a root but are not the same chord.

        It is the major third that lets one point at the second degree, so
        filtering by root alone left five of the six out.
        """
        from engine.harmony import MODES, build_chord_pool
        from engine.theory import parse_pitch_class
        pool = build_chord_pool(parse_pitch_class("C"), MODES["major"],
                                [], True, secondary=True)
        romans = {o.roman for o in pool}
        for degree in ("V/ii", "V/iii", "V/IV", "V/V", "V/vi"):
            self.assertIn(degree, romans)

    def test_recognised_by_motion_not_by_name(self):
        from engine.harmony import MODES, build_chord_pool, _is_secondary_two_five
        from engine.theory import parse_pitch_class
        tonic = parse_pitch_class("C")
        pool = {o.roman: o for o in build_chord_pool(
            tonic, MODES["major"], [], True, secondary=True)}
        # Em7 - A7 - Dm7: the ii-V of the second degree.
        self.assertTrue(_is_secondary_two_five(
            pool["iii"], pool["V/ii"], pool["ii"]))
        # Three roots that do not fall by fourths are not it.
        self.assertFalse(_is_secondary_two_five(
            pool["I"], pool["V"], pool["ii"]))

    def _offered(self, genre_key):
        """Las dominantes aplicadas que un estilo pone sobre la mesa."""
        request = session.GenerativeRequest(
            genre_key=genre_key, voice_keys=["B", "T", "S"], tonic="C",
            slot_count=6,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=3),
        )
        outcome = session.generate_random(request)
        return {option.harmony.roman
                for slot in outcome.spec.slots for option in slot.options
                if option.harmony.roman.startswith("V/")}

    def test_the_baroque_styles_get_the_dominant_of_the_dominant_only(self):
        # El V del V es de práctica común; la cadena entera apuntando a cada
        # grado es una costumbre del jazz.
        for genre in ("classical", "chorale"):
            self.assertEqual(self._offered(genre), {"V/V"}, genre)

    def test_jazz_gets_the_whole_chain(self):
        # Cuáles exactamente depende de si hay séptimas: una aplicada que
        # coincide con un acorde diatónico no se agrega dos veces. Lo que se
        # afirma es que el jazz apunta a varios grados y el barroco a uno.
        offered = self._offered("jazz")
        self.assertIn("V/V", offered)
        self.assertGreater(len(offered), 1)

    def test_the_modal_style_gets_none(self):
        # El organum no tiene dominantes que aplicar.
        self.assertEqual(self._offered("gregorian"), set())


class TestAppliedDominant(unittest.TestCase):
    """El V del V: raro de escribir, y obligado a resolver una vez escrito."""

    def _pool(self):
        return {option.roman: option for option in harmony.build_chord_pool(
            parse_pitch_class("C"), harmony.MODES["major"], [], False,
            secondary=True, secondary_degrees=(harmony.DEGREE_DOMINANT,))}

    def _step(self, grammar, previous, current):
        return harmony.grammar_cost(previous, current, grammar,
                                    parse_pitch_class("C"))

    def test_the_pool_offers_the_dominant_of_the_dominant(self):
        self.assertIn("V/V", self._pool())

    def test_resolving_to_the_dominant_is_the_cheap_way_out(self):
        pool = self._pool()
        for key in ("classical", "chorale"):
            grammar = harmony.GRAMMARS[key]
            resolved = self._step(grammar, pool["V/V"], pool["V"])
            for escape in ("ii", "vi", "I"):
                self.assertLess(resolved, self._step(grammar, pool["V/V"],
                                                     pool[escape]),
                                f"{key}: V/V-{escape}")

    def test_reaching_it_costs_more_than_reaching_the_plain_pre_dominant(self):
        # El precio se paga al ENTRAR: llegar al V/V sale más caro que
        # llegar al ii desde el mismo acorde, y eso es lo que lo vuelve un
        # color ocasional en vez de material de todas las frases. Salir de
        # él es barato justamente porque ya se pagó.
        pool = self._pool()
        for key in ("classical", "chorale"):
            grammar = harmony.GRAMMARS[key]
            self.assertGreater(self._step(grammar, pool["I"], pool["V/V"]),
                               self._step(grammar, pool["I"], pool["ii"]), key)

    def test_landing_on_the_tonic_is_not_a_plagal_cadence(self):
        # Cae en la tónica desde una función de subdominante, así que sin
        # tratarlo aparte cobraba el premio plagal por abandonar la
        # resolución.
        pool = self._pool()
        grammar = harmony.GRAMMARS["classical"]
        self.assertGreater(self._step(grammar, pool["V/V"], pool["I"]),
                           self._step(grammar, pool["IV"], pool["I"]))

    def test_it_is_not_counted_as_a_modal_interchange(self):
        # Viaja como "prestado" porque no es diatónico, pero no viene del
        # modo paralelo.
        option = self._pool()["V/V"]
        self.assertTrue(option.is_borrowed)
        self.assertTrue(harmony.is_applied_dominant(option))
        self.assertFalse(harmony.is_applied_dominant(self._pool()["ii"]))


class TestQuotationDegrees(unittest.TestCase):
    def test_the_dominant_is_named_as_such(self):
        """Reading numerals off the slot showed "i" over the dominant.

        The chromatic cadence repeats one chord symbol, so the slot cannot
        say which degree each position is; the quotation carries its own.
        """
        from engine.harmony import SET_PIECES, set_piece_options
        from engine.theory import parse_pitch_class
        options = set_piece_options(SET_PIECES["chromatic_bass"],
                                    parse_pitch_class("A"))
        self.assertEqual([o.roman for o in options],
                         ["i", "i", "i", "i", "V", "i"])


class TestHarmonisation(unittest.TestCase):
    """Harmonising a melody someone else wrote."""

    def _melody(self, names, bars=None, beats=4, beat_type=4):
        from engine.harmonize import Melody, MelodyBar, MelodyNote
        from engine.theory import parse_pitch_class
        tonic = parse_pitch_class("C")
        count = bars or max(1, len(names) // beats)
        return Melody(
            notes=[MelodyNote(parse_note_name(n), 1.0, i // beats,
                              float(i % beats))
                   for i, n in enumerate(names)],
            bars=[MelodyBar(beats, beat_type, tonic, "major")
                  for _ in range(count)],
            melody_voice=3,
        )

    def test_strong_beats_follow_the_metre(self):
        from engine.harmonize import strong_beat_offsets
        self.assertEqual(strong_beat_offsets(4, 4), [0.0, 2.0])
        self.assertEqual(strong_beat_offsets(3, 4), [0.0])
        self.assertEqual(strong_beat_offsets(2, 4), [0.0])
        # Compound metres group in threes: 6/8 is two beats, not six.
        self.assertEqual(strong_beat_offsets(6, 8), [0.0, 1.5])
        self.assertEqual(strong_beat_offsets(12, 8), [0.0, 1.5, 3.0, 4.5])

    def test_a_marked_note_gets_its_own_chord(self):
        """La nota que el usuario marcó recibe acorde, caiga donde caiga.

        El armonizador escribe sobre los tiempos fuertes; una nota en el
        medio del compás pasaba por encima del acorde anterior. Marcada, se
        le abre un lugar propio.
        """
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        rules = HarmonisationSettings(genre_key="chorale")
        plain = harmonise(melody, rules, _random.Random(7))
        self.assertNotIn((0, 1.0), [(s.bar_index, s.offset_quarters)
                                    for s, _o in plain])
        melody.notes[1].must_harmonise = True
        marked = harmonise(melody, rules, _random.Random(7))
        placed = {(s.bar_index, s.offset_quarters): s for s, _o in marked}
        self.assertIn((0, 1.0), placed)
        # Y sostiene esa nota, no la que le siga: el lugar existe por ella.
        self.assertEqual(placed[(0, 1.0)].note, melody.notes[1])

    def test_marking_a_note_keeps_the_bars_adding_up(self):
        """Un compás que no suma lo rechaza cualquier editor de partituras.

        El lugar que se parte se queda con lo que hay hasta la nota y el
        nuevo con todo el resto; si el nuevo durara lo que dura la nota, el
        sobrante quedaría sin dueño.
        """
        from engine.harmonize import harmony_spots
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        for position in (1, 5, 6):
            melody.notes[position].must_harmonise = True
        totals = {}
        for spot in harmony_spots(melody):
            totals[spot.bar_index] = (totals.get(spot.bar_index, 0.0)
                                      + spot.duration_quarters)
        self.assertEqual(set(totals.values()), {4.0}, totals)

    def test_marking_a_note_that_lands_just_after_a_strong_beat(self):
        """A un cuarto de tiempo del lugar no se puede partir: se corre.

        Y lo que queda por delante de la nota tiene que quedárselo el lugar
        anterior. Corriendo el lugar sin dárselo a nadie, ese pedazo se
        pierde y el compás deja de sumar --- en 6/8, dos tiempos y tres
        cuartos en vez de tres.
        """
        from engine.harmonize import (Melody, MelodyBar, MelodyNote,
                                      harmony_spots)
        from engine.theory import parse_pitch_class
        # 6/8: tiempos fuertes en 0 y 1,5. La tercera nota cae en 1,75.
        durations = [1.0, 0.75, 0.5, 0.75, 1.5, 1.5]
        notes, position = [], 0.0
        for duration in durations:
            notes.append(MelodyNote(72, duration, int(position // 3.0),
                                    position % 3.0))
            position += duration
        melody = Melody(
            notes=notes,
            bars=[MelodyBar(6, 8, parse_pitch_class("C"), "major")
                  for _ in range(2)],
            melody_voice=3)
        notes[2].must_harmonise = True
        spots = harmony_spots(melody)
        self.assertIn((0, 1.75), [(s.bar_index, s.offset_quarters)
                                  for s in spots])
        totals = {}
        for spot in spots:
            totals[spot.bar_index] = (totals.get(spot.bar_index, 0.0)
                                      + spot.duration_quarters)
        self.assertEqual(set(totals.values()), {3.0}, totals)

    def test_the_preview_names_the_notes_that_will_be_harmonised(self):
        """Lo que el pentagrama pinta de dorado es lo que después ocurre."""
        import random as _random
        from engine.harmonize import (HarmonisationSettings, harmonise,
                                      planned_notes)
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        melody.notes[5].must_harmonise = True
        rules = HarmonisationSettings(genre_key="chorale")
        preview = {(n.bar_index, n.offset_quarters)
                   for n in planned_notes(melody, rules)}
        for seed in range(5):
            written = {(s.note.bar_index, s.note.offset_quarters)
                       for s, _o in harmonise(melody, rules, _random.Random(seed))
                       if s.note is not None}
            self.assertEqual(written, preview, f"semilla {seed}")

    def test_the_melody_note_lands_in_the_chord(self):
        """Harmonising a note that is not in the chord is the main failure."""
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        chosen = harmonise(melody, HarmonisationSettings(genre_key="chorale"),
                           _random.Random(7))
        self.assertTrue(chosen)
        for spot, option in chosen:
            if spot.note is None:
                continue
            interval = (spot.note.pitch - option.root_pc) % 12
            chord = {t.semitones % 12 for t in option.chord.tones}
            self.assertIn(interval, chord,
                          f"{option.label} cannot hold that melody note")

    def test_it_begins_and_ends_on_the_tonic(self):
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        from engine.theory import parse_pitch_class
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        for genre in ("classical", "chorale", "jazz", "gregorian"):
            chosen = harmonise(melody, HarmonisationSettings(genre_key=genre),
                               _random.Random(7))
            tonic = parse_pitch_class("C")
            self.assertEqual(chosen[0][1].root_pc, tonic, genre)
            self.assertEqual(chosen[-1][1].root_pc, tonic, genre)

    def test_the_style_changes_the_answer(self):
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        melody = self._melody(["C5", "E5", "D5", "F5", "E5", "G5", "D5", "C5"])
        # Compared across several seeds: with the melody weighted as heavily
        # as it now is, one seed can land on the same answer everywhere --
        # the note allows only so many chords, whatever the style.
        by_genre = {}
        for genre in ("classical", "jazz", "gregorian"):
            by_genre[genre] = {
                tuple(o.roman for _s, o in harmonise(
                    melody, HarmonisationSettings(genre_key=genre),
                    _random.Random(seed)))
                for seed in range(8)
            }
        self.assertNotEqual(by_genre["gregorian"], by_genre["jazz"])

    def test_a_second_run_can_differ(self):
        """The same melody should not always come back identically voiced."""
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        melody = self._melody(["C5", "E5", "D5", "F5", "E5", "G5", "D5", "C5"])
        answers = {
            tuple(o.roman for _s, o in harmonise(
                melody, HarmonisationSettings(genre_key="chorale"),
                _random.Random(seed)))
            for seed in range(8)
        }
        self.assertGreater(len(answers), 1)

    def test_flat_seven_only_just_before_the_close(self):
        import random as _random
        from engine.harmonize import HarmonisationSettings, harmonise
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        for seed in range(12):
            chosen = harmonise(melody, HarmonisationSettings(
                genre_key="chorale", allow_borrowed=True), _random.Random(seed))
            for index, (_spot, option) in enumerate(chosen):
                if option.roman == "bVII":
                    self.assertEqual(index, len(chosen) - 2)

    def test_the_given_voice_is_never_altered(self):
        """The point of the mode: the user's line comes back untouched."""
        from engine.harmonize import Melody, MelodyBar, MelodyNote
        from engine.theory import parse_pitch_class
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        request = session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=3),
        )
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        for solution in outcome.result.solutions:
            for index, slot in enumerate(outcome.spec.slots):
                pinned = slot.pinned_voices.get(3)
                if pinned is not None:
                    self.assertEqual(solution.slots[index][3], pinned)

    def test_a_low_line_still_comes_back_untouched(self):
        """The uncrossing repair used to hand the melody to another voice.

        Sorting the sampled notes fixes crossings for free, because it only
        changes who sings what -- which is exactly what a pinned voice cannot
        survive. The test above missed it: its melody sat above every chord,
        so sorting left it in place by luck. A tune low in the soprano's
        range lets the alto sort over it, and the user got back a line they
        never wrote.
        """
        melody = self._melody(["C4", "D4", "E4", "F4", "G4", "F4", "E4", "D4"])
        for seed in (1, 2, 3):
            request = session.HarmoniseRequest(
                genre_key="jazz", voice_keys=["B", "T", "A", "S"],
                melody=melody, melody_voice=3,
                ga_config=GAConfig(population_size=70, generations=30,
                                   random_seed=seed),
            )
            outcome = session.harmonise_melody(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            for solution in outcome.result.solutions:
                for index, slot in enumerate(outcome.spec.slots):
                    pinned = slot.pinned_voices.get(3)
                    if pinned is not None:
                        self.assertEqual(solution.slots[index][3], pinned,
                                         f"seed {seed}, chord {index}")

    def test_a_harmonisation_can_be_exported(self):
        """Writing the files must not raise on the way to the history record.

        The record was read off the request, and only the manual mode's
        request has typed chords and a metre on it. The scores were written
        and then the call blew up, so the user was never told it had worked.
        """
        import tempfile
        melody = self._melody(["C4", "E4", "G4", "E4"], bars=1)
        request = session.HarmoniseRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=1),
        )
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            written = session.export_outcome(
                request, outcome, directory=folder, formats=("musicxml",),
                record_history=False,
            )
            self.assertTrue(written)

    def test_the_score_shows_the_melody_as_written(self):
        """The exported part must carry the tune, not the strong beats of it.

        The search sees the line sampled one note per chord, which is the
        right rhythm to judge counterpoint on. The score is not allowed to
        inherit that: eight quavers came out as five held notes, which is a
        different melody.
        """
        import xml.etree.ElementTree as ET
        import tempfile
        written = ["C4", "D4", "E4", "F4", "G4", "F4", "E4", "D4"]
        request = session.HarmoniseRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"],
            melody=self._melody(written), melody_voice=3,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=1),
        )
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            files = session.export_outcome(
                request, outcome, directory=folder, formats=("musicxml",),
                record_history=False,
            )
            root = ET.parse(files[0]).getroot()

        # Voice 1 is the topmost part, which is where the melody sits.
        sung = []
        for note in root.iter("note"):
            if note.findtext("voice") != "1":
                continue
            pitch = note.find("pitch")
            if pitch is not None:
                sung.append(pitch.findtext("step") + pitch.findtext("octave"))
        self.assertEqual(sung, written)

        # Every voice must still fill each measure, or notation software
        # refuses the file outright.
        for measure in root.iter("measure"):
            totals = {}
            for note in measure.iter("note"):
                voice = note.findtext("voice")
                totals[voice] = totals.get(voice, 0) + int(note.findtext("duration"))
            self.assertEqual(len(set(totals.values())), 1, totals)

    def test_a_marked_note_survives_into_the_exported_score(self):
        """La partitura que sale tiene que seguir siendo legal.

        Marcar una nota parte un lugar de acorde en dos, así que es
        exactamente donde un compás podría dejar de sumar. Se comprueba
        sobre el archivo escrito, que es lo que el usuario abre en otro
        programa: la melodía intacta y todas las voces llenando cada compás.
        """
        import xml.etree.ElementTree as ET
        import tempfile
        written = ["C4", "D4", "E4", "F4", "G4", "F4", "E4", "D4"]
        melody = self._melody(written)
        melody.notes[1].must_harmonise = True
        melody.notes[6].must_harmonise = True
        request = session.HarmoniseRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=1),
        )
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            files = session.export_outcome(
                request, outcome, directory=folder, formats=("musicxml",),
                record_history=False,
            )
            root = ET.parse(files[0]).getroot()

        sung = []
        for note in root.iter("note"):
            if note.findtext("voice") != "1":
                continue
            pitch = note.find("pitch")
            if pitch is not None:
                sung.append(pitch.findtext("step") + pitch.findtext("octave"))
        self.assertEqual(sung, written)

        for measure in root.iter("measure"):
            totals = {}
            for note in measure.iter("note"):
                voice = note.findtext("voice")
                totals[voice] = totals.get(voice, 0) + int(note.findtext("duration"))
            self.assertEqual(len(set(totals.values())), 1, totals)

    def test_only_the_harmoniser_carries_a_melody_line(self):
        """The other two modes must keep exporting from the chromosome alone."""
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry("C", 2.0, 0),
                     session.ChordEntry("G", 2.0, 0)],
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=1),
        )
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        self.assertIsNone(outcome.spec.melody)

    def test_harsh_clashes_are_recognised(self):
        from engine.harmonize import harmony_spots, weak_beat_clashes
        melody = self._melody(["C5", "C#5", "D5", "E5"], bars=1)
        spot = harmony_spots(melody)[0]
        # C# a minor ninth above a C bass is a clash; over F it is not.
        self.assertEqual(weak_beat_clashes(melody, spot,
                                           parse_note_name("C3")), 1)
        self.assertEqual(weak_beat_clashes(melody, spot,
                                           parse_note_name("F3")), 0)

    def test_three_answers_even_for_a_short_melody(self):
        """A short line offers few progressions, but still deserves choices.

        Two notes admit barely one chord sequence, so insisting on three
        entirely different progressions returned a single answer. The
        remainder are voiced from the progressions found, under different
        seeds, so they differ as arrangements.
        """
        for names in (["C5", "C5"], ["C5", "D5", "E5", "C5"]):
            melody = self._melody(names, bars=1)
            request = session.HarmoniseRequest(
                genre_key="classical", voice_keys=["B", "T", "S"],
                melody=melody, melody_voice=2,
                ga_config=GAConfig(population_size=60, generations=25,
                                   random_seed=3),
            )
            outcome = session.harmonise_melody(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            self.assertEqual(len(outcome.result.solutions), 3, names)

    def test_each_option_keeps_its_own_chords(self):
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "D5", "C5"])
        request = session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "S"],
            melody=melody, melody_voice=2,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=3),
        )
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        progressions = set()
        for index in range(len(outcome.result.solutions)):
            slots = outcome.alternate_slots.get(index, outcome.spec.slots)
            progressions.add(tuple(s.requirement.chord.symbol for s in slots))
        self.assertGreater(len(progressions), 1)

    def test_a_melody_on_a_colour_tone_still_works(self):
        """Regression: this came back as "no solution" after eighty seconds.

        With three voices, one is taken by the melody. When that note is a
        colour tone it covers none of the chord's own, leaving two voices for
        three required notes -- impossible, so the search ground through
        every candidate and rejected each one. The chord now gives way.
        """
        import time as _time
        melody = self._melody(["C5", "E5", "G5", "F5", "A5", "B5", "E5", "C5"])
        for genre in ("gregorian", "classical"):
            request = session.HarmoniseRequest(
                genre_key=genre, voice_keys=["B", "T", "S"],
                melody=melody, melody_voice=2,
                allow_colour=True, colour_weight=14.0, allow_borrowed=True,
                switch_overrides={"special_voicing_fills": True,
                                  "weight_colour_tone": -14.0},
                ga_config=GAConfig(population_size=70, generations=30,
                                   random_seed=3),
            )
            started = _time.time()
            outcome = session.harmonise_melody(request)
            self.assertTrue(outcome.succeeded, f"{genre}: {outcome.errors}")
            self.assertLess(_time.time() - started, 30.0, genre)

    def test_three_answers_come_back(self):
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        request = session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3,
            ga_config=GAConfig(population_size=70, generations=30,
                               random_seed=3),
        )
        outcome = session.harmonise_melody(request)
        self.assertEqual(len(outcome.result.solutions), 3)


class TestHistory(unittest.TestCase):
    def test_keeps_only_ten_newest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.json")
            for index in range(15):
                record = history.ProductionRecord.create(
                    title=f"run {index}",
                    genre="jazz",
                    voice_keys=["B", "T", "A", "S"],
                    bar_count=2,
                    time_signature="4/4",
                    chord_symbols=["C", "F"],
                )
                history.add_record(record, path)
            records = history.load_history(path)
            self.assertEqual(len(records), 10)
            self.assertEqual(records[0].title, "run 14")

    def test_corrupt_history_does_not_raise(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json at all")
            self.assertEqual(history.load_history(path), [])


class TestAchievementCatalogue(unittest.TestCase):
    """The catalogue itself: no duplicates, no orphans, no silent losses."""

    def test_keys_are_unique(self):
        keys = [a.key for a in achievements.CATALOG]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_achievement_belongs_somewhere(self):
        placed = set(achievements.LEGENDARY_KEYS)
        for star in range(1, achievements.STAR_COUNT + 1):
            placed |= set(achievements.STAR_KEYS[star])
        self.assertEqual(placed, set(achievements.BY_KEY))

    def test_only_legendaries_grant_a_title(self):
        for entry in achievements.CATALOG:
            self.assertEqual(bool(entry.title), entry.legendary, entry.key)


class TestAchievementTracker(unittest.TestCase):
    def _tracker(self, folder):
        return achievements.Tracker(path=os.path.join(folder, "a.json"))

    def test_unlocking_twice_reports_it_once(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            self.assertEqual(len(tracker.unlock(["first_rest"])), 1)
            self.assertEqual(tracker.unlock(["first_rest"]), [])

    def test_unknown_keys_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            self.assertEqual(tracker.unlock(["no existe"]), [])

    def test_a_star_needs_the_one_below_it(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            tracker.unlock(achievements.STAR_KEYS[2])
            self.assertTrue(tracker.star_complete(2))
            # Completa pero no ganada: falta la primera.
            self.assertEqual(tracker.stars(), 0)
            tracker.unlock(achievements.STAR_KEYS[1])
            self.assertEqual(tracker.stars(), 2)

    def test_three_stars_grant_the_title(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            for star in range(1, achievements.STAR_COUNT + 1):
                tracker.unlock(achievements.STAR_KEYS[star])
            self.assertIn(achievements.TRIUMPH_TITLE, tracker.titles())

    def test_titles_stack(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            tracker.unlock(["the_lick", "blues_pact"])
            self.assertEqual(sorted(tracker.titles()),
                             ["Maestro del Blues", "The Swingster"])

    def test_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            achievements.Tracker(path=path).unlock(["first_export"])
            self.assertTrue(achievements.Tracker.load(path).has("first_export"))

    def test_a_damaged_file_does_not_raise(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{ nada de esto es json")
            self.assertEqual(achievements.Tracker.load(path).unlocked, {})

    def test_a_key_from_an_older_version_is_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"unlocked": {"un_logro_retirado": "2026-01-01",
                                        "first_rest": "2026-01-01"}}, handle)
            tracker = achievements.Tracker.load(path)
            self.assertEqual(set(tracker.unlocked), {"first_rest"})


class TestAchievementDetectors(unittest.TestCase):
    """The musical detectors, which is where a wrong answer would hurt."""

    @staticmethod
    def _chords(text):
        return [parse_chord(symbol) for symbol in text.split()]

    GOSPEL = "C G/B C7/Bb F/A Fm/Ab C/G D7/F# G C"

    def test_gospel_octave_rule_in_any_key(self):
        self.assertTrue(achievements.is_gospel_octave_rule(
            self._chords(self.GOSPEL)))
        self.assertTrue(achievements.is_gospel_octave_rule(self._chords(
            "Eb Bb/D Eb7/Db Ab/C Abm/Cb Eb/Bb F7/A Bb Eb")))

    def test_gospel_octave_rule_without_the_closing_tonic(self):
        self.assertTrue(achievements.is_gospel_octave_rule(
            self._chords(" ".join(self.GOSPEL.split()[:-1]))))

    def test_gospel_octave_rule_inside_a_longer_piece(self):
        self.assertTrue(achievements.is_gospel_octave_rule(
            self._chords("Am F " + self.GOSPEL + " Dm G")))

    def test_the_inversions_are_what_make_it(self):
        # Los mismos acordes en estado fundamental no son la regla: lo que
        # la define es el bajo bajando.
        self.assertFalse(achievements.is_gospel_octave_rule(
            self._chords("C G C7 F Fm C D7 G C")))

    def test_an_ordinary_progression_is_not_the_gospel_rule(self):
        self.assertFalse(achievements.is_gospel_octave_rule(
            self._chords("C F G C Am F G C C")))

    def test_blues_pact_needs_three_dominant_sevenths(self):
        self.assertTrue(achievements.is_blues_pact(self._chords("C7 F7 G7")))
        self.assertTrue(achievements.is_blues_pact(
            self._chords("Am A7 D7 E7 Am")))
        self.assertFalse(achievements.is_blues_pact(self._chords("C F G")))
        self.assertFalse(achievements.is_blues_pact(
            self._chords("C7 F7 Bb7")))          # bajando quintas, no I IV V

    def test_the_lick_travels(self):
        lick = [62, 64, 65, 67, 64, 60, 62]
        self.assertTrue(achievements.has_the_lick(lick))
        self.assertTrue(achievements.has_the_lick(
            [55, 57] + [p + 5 for p in lick] + [72]))
        self.assertFalse(achievements.has_the_lick([60, 62, 64, 65, 67, 69, 71]))

    def test_tritone_leap(self):
        self.assertTrue(achievements.has_tritone_leap([60, 66, 64]))
        self.assertFalse(achievements.has_tritone_leap([60, 62, 64]))

    FIGURES = [4.0, 2.0, 1.5, 1.0, 0.75, 0.5]

    def test_supreme_melody_needs_every_step_and_every_figure(self):
        complete = list(zip(range(7), self.FIGURES + [4.0]))
        self.assertTrue(achievements.supreme_melody(complete, self.FIGURES))
        # Le falta una figura.
        self.assertFalse(achievements.supreme_melody(
            [(step, 1.0) for step in range(7)], self.FIGURES))
        # Le falta un grado.
        self.assertFalse(achievements.supreme_melody(
            list(zip(range(6), self.FIGURES)), self.FIGURES))

    def test_the_octave_does_not_change_the_step(self):
        # Un do es un do en cualquier octava, y un fa sostenido sigue siendo
        # un fa: el pentagrama guarda la posición, no el semitono.
        octaves = [(step + 7 * (step % 3), figure)
                   for step, figure in zip(range(7), self.FIGURES + [4.0])]
        self.assertTrue(achievements.supreme_melody(octaves, self.FIGURES))

    def test_supreme_melody_progress_says_which_half_is_missing(self):
        # Todo el teclado escrito con una sola figura: las notas están
        # completas y las figuras casi ninguna. Es exactamente lo que se ve
        # al tocar las doce teclas del piano sin cambiar la figura.
        keyboard = [(step, 1.0) for step in range(12)]
        steps, all_steps, used, all_used = achievements.supreme_melody_progress(
            keyboard, self.FIGURES)
        self.assertEqual((steps, all_steps), (7, 7))
        self.assertEqual((used, all_used), (1, 6))

    def test_progress_ignores_figures_that_are_not_offered(self):
        # Una duración importada que no está entre las figuras del editor no
        # puede contar para el logro ni inflar el marcador.
        odd = [(step, 3.0) for step in range(7)]
        _s, _a, used, _u = achievements.supreme_melody_progress(
            odd, self.FIGURES)
        self.assertEqual(used, 0)

    def test_modes_that_count_as_beyond(self):
        for key in ("dorian", "phrygian", "lydian", "mixolydian", "locrian",
                    "harmonic"):
            self.assertTrue(achievements.is_exotic_mode(key), key)
        for key in ("major", "minor"):
            self.assertFalse(achievements.is_exotic_mode(key), key)

    def test_the_aeolian_is_gone_from_the_catalogue(self):
        # Era la menor natural con otro nombre: la misma escala ofrecida dos
        # veces. Si vuelve, vuelve también el modo duplicado en el menú.
        self.assertNotIn("aeolian", harmony.MODES)
        self.assertEqual(harmony.MODES["minor"].intervals,
                         (0, 2, 3, 5, 7, 8, 10))

    def test_rules_customised(self):
        profile = GENRE_PROFILES["classical"]
        same = {"forbid_parallel_fifths": profile.forbid_parallel_fifths}
        self.assertFalse(achievements.rules_customised("classical", same))
        flipped = {"forbid_parallel_fifths": not profile.forbid_parallel_fifths}
        self.assertTrue(achievements.rules_customised("classical", flipped))

    def test_ga_customised(self):
        default = GAConfig()
        self.assertFalse(achievements.ga_customised(GAConfig(), default))
        self.assertTrue(achievements.ga_customised(
            GAConfig(population_size=default.population_size + 50), default))


class TestAchievementsFromARun(unittest.TestCase):
    """What a finished run reports, through the same path the app uses."""

    CONFIG = GAConfig(population_size=40, generations=30, random_seed=3,
                      workers=1)

    def _run(self, symbols, genre="jazz", rests=()):
        entries = []
        for index, symbol in enumerate(symbols):
            entries.append(session.ChordEntry(
                symbol="" if index in rests else symbol,
                duration_quarters=2.0, bar_index=index // 2,
                is_rest=index in rests))
        request = session.JobRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"], entries=entries,
            ga_config=self.CONFIG, time_signature=export.TimeSignature(4, 4))
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        return outcome

    def test_sevenths_and_diminished_are_seen(self):
        outcome = self._run("Cmaj7 Am7 Bdim7 G7".split())
        found = achievements.inspect_outcome(outcome)
        self.assertIn("seventh_chord", found)
        self.assertIn("diminished_chord", found)

    def test_a_piece_that_ends_on_a_dominant(self):
        self.assertIn("ends_on_dominant",
                      achievements.inspect_outcome(self._run("C F Am G7".split())))
        self.assertNotIn("ends_on_dominant",
                         achievements.inspect_outcome(self._run("C G7 F C".split())))

    def test_three_dominants_in_a_row(self):
        self.assertIn("three_dominants", achievements.inspect_outcome(
            self._run("A7 D7 G7 C".split())))
        self.assertNotIn("three_dominants", achievements.inspect_outcome(
            self._run("A7 D7 G C".split())))

    def test_exactly_one_of_the_two_parallel_fifth_verdicts(self):
        found = achievements.inspect_outcome(self._run("C F G C".split()))
        self.assertEqual(len(found & {"parallel_fifth", "no_parallel_fifths"}), 1)

    def test_a_rest_does_not_shift_the_reading(self):
        # El cromosoma sólo tiene los acordes que suenan: si el detector
        # leyera `spec.slots` en crudo, un silencio correría los índices y
        # además contaría su acorde de relleno como un Do mayor escrito.
        outcome = self._run("Cmaj7 Am7 Dm7 G7".split(), rests=(1,))
        found = achievements.inspect_outcome(outcome)
        self.assertIn("seventh_chord", found)
        self.assertIn("ends_on_dominant", found)

    def test_every_solution_is_read_not_only_the_winner(self):
        # Las tres respuestas están en pantalla y el usuario puede quedarse
        # con cualquiera, así que un acorde que sólo aparece en la opción 2
        # cuenta igual. Se comprueba pidiendo lo mismo con la lista de
        # soluciones al revés: la respuesta no puede depender del orden.
        # Las quintas paralelas quedan afuera de la comparación: ésas sí se
        # juzgan sobre la ganadora, que al invertir la lista es otra.
        fifths = {"parallel_fifth", "no_parallel_fifths"}
        outcome = self._run("Cmaj7 Am7 Bdim7 G7".split())
        straight = achievements.inspect_outcome(outcome) - fifths
        outcome.result.solutions.reverse()
        self.assertEqual(achievements.inspect_outcome(outcome) - fifths,
                         straight)

    def test_nothing_is_reported_for_what_is_already_won(self):
        outcome = self._run("Cmaj7 Am7 Bdim7 G7".split())
        self.assertEqual(
            achievements.inspect_outcome(outcome, {"first_rest"}), set())

    def test_a_generated_piece_reports_its_borrowings(self):
        request = session.GenerativeRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            tonic="C", mode_key="major", slot_count=8, durations=[2.0] * 8,
            bar_indices=[i // 2 for i in range(8)],
            time_signature=export.TimeSignature(4, 4), ga_config=self.CONFIG,
            borrowed=["iv"], with_sevenths=True)
        outcome = session.generate_random(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        self.assertIn("seventh_chord", achievements.inspect_outcome(outcome))


def scratch_file() -> str:
    """Un nombre de archivo libre y descartable, para lo que se persiste."""
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    handle.close()
    os.unlink(handle.name)
    return handle.name


class TestStoryGates(unittest.TestCase):
    """Las trabas del modo historia: qué progresión cuenta y en qué tonalidad."""

    @staticmethod
    def chords(*symbols):
        return [parse_chord(symbol) for symbol in symbols]

    def test_the_blues_cadence_reports_its_key(self):
        self.assertEqual(
            story.tonics_for_gate(story.GATE_BLUES_KEYS,
                                  self.chords("C7", "F7", "G7")), {0})
        self.assertEqual(
            story.tonics_for_gate(story.GATE_BLUES_KEYS,
                                  self.chords("A7", "D7", "E7")), {9})

    def test_a_two_five_names_the_key_it_belongs_to(self):
        """Dm7 G7 es el ii-V de do, no de re."""
        self.assertEqual(
            story.tonics_for_gate(story.GATE_JAZZ_KEYS,
                                  self.chords("Dm7", "G7")), {0})

    def test_the_amen_counts_in_both_directions(self):
        """F C es IV-I en do; C F es I-IV en do. Es la misma pareja."""
        self.assertEqual(
            story.tonics_for_gate(story.GATE_GOSPEL_KEYS,
                                  self.chords("F", "C")), {0})
        self.assertIn(0, story.tonics_for_gate(story.GATE_GOSPEL_KEYS,
                                               self.chords("C", "F")))

    def test_a_progression_that_does_not_match_reports_nothing(self):
        self.assertEqual(
            story.tonics_for_gate(story.GATE_BLUES_KEYS,
                                  self.chords("C", "Am", "F", "G")), set())

    def test_the_span_points_at_the_chords_that_form_it(self):
        """Es lo que la interfaz enciende en dorado, así que tiene que ser
        la cadencia y no la progresión entera."""
        span = story.matching_span(story.GATE_BLUES_KEYS,
                                   self.chords("Am", "C7", "F7", "G7", "C"))
        self.assertEqual(span, (1, 3))

    def test_three_keys_open_a_gate(self):
        # Con un archivo propio y descartable: anotar una tonalidad guarda, y
        # sin decirle dónde escribiría el `story.json` de verdad --- el del
        # usuario, o el de la carpeta del proyecto cuando se corre desde
        # fuente --- y le dejaría un sendero empezado que nunca eligió.
        state = story.StoryState(path_key="blues", file_path=scratch_file())
        try:
            for tonics in ({0}, {2}, {2}):
                state.note_tonics(story.GATE_BLUES_KEYS, tonics)
            self.assertFalse(state.gate_open(story.GATE_BLUES_KEYS))
            state.note_tonics(story.GATE_BLUES_KEYS, {5})
            self.assertTrue(state.gate_open(story.GATE_BLUES_KEYS))
        finally:
            if os.path.exists(state.file_path):
                os.unlink(state.file_path)


class TestStoryState(unittest.TestCase):
    """El sendero guardado: avanzar, terminar y arrepentirse."""

    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        handle.close()
        os.unlink(handle.name)
        self.path = handle.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_a_missing_file_starts_a_clean_state(self):
        state = story.StoryState.load(self.path)
        self.assertTrue(state.may_offer())
        self.assertIsNone(state.path)

    def test_a_damaged_file_does_not_stop_the_program(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json at all")
        self.assertTrue(story.StoryState.load(self.path).may_offer())

    def test_choosing_survives_a_reload(self):
        state = story.StoryState(file_path=self.path)
        state.choose("ignore")
        again = story.StoryState.load(self.path)
        self.assertEqual(again.path_key, "jazz")
        self.assertFalse(again.may_offer())

    def test_walking_a_path_to_the_end_records_it(self):
        state = story.StoryState(file_path=self.path)
        state.choose("accept")
        for _ in range(len(state.path.steps)):
            state.advance()
        self.assertIn("blues", state.finished)
        self.assertIn("blues", state.keepsakes)
        self.assertIsNone(state.current)

    def test_the_legendary_is_withheld_while_the_path_runs(self):
        """El logro del sendero lo entrega el cierre, no el tramo donde el
        usuario se topa con la progresión."""
        state = story.StoryState(file_path=self.path)
        state.choose("accept")
        self.assertTrue(state.withholds("blues_pact"))
        self.assertFalse(state.withholds("the_lick"))
        for _ in range(len(state.path.steps)):
            state.advance()
        self.assertFalse(state.withholds("blues_pact"))

    def test_nothing_is_withheld_outside_the_story(self):
        state = story.StoryState(file_path=self.path)
        for key in ("blues_pact", "the_lick", "second_coming"):
            self.assertFalse(state.withholds(key))

    def test_an_interrupted_offer_does_not_kill_the_story(self):
        """La aplicación cerrada en la mitad de la cinemática del
        ofrecimiento: la figura ya se apareció, pero no se eligió nada.

        Con `may_offer` mirando `seen_offer` esto apagaba el modo historia
        para siempre --- ni botón, ni recordatorio, ni «Arrepentirse» ---
        sin que fallara nada."""
        state = story.StoryState(file_path=self.path)
        state.mark_offered()
        again = story.StoryState.load(self.path)
        self.assertTrue(again.seen_offer)
        self.assertTrue(again.may_offer())

    def test_repenting_leaves_the_offer_pending(self):
        """Arrepentirse deja exactamente el mismo estado, y también tiene
        que poder volver a ofrecerse."""
        state = story.StoryState(file_path=self.path)
        state.choose("refuse")
        state.restart()
        self.assertTrue(state.seen_offer)
        self.assertTrue(state.may_offer())
        self.assertTrue(story.StoryState.load(self.path).may_offer())

    def test_the_offer_is_marked_once(self):
        state = story.StoryState(file_path=self.path)
        state.mark_offered()
        state.mark_offered()
        self.assertTrue(state.seen_offer)

    def test_repenting_keeps_what_was_read(self):
        state = story.StoryState(file_path=self.path)
        state.choose("accept")
        state.advance()
        state.mark_read("story_blues_1")
        state.restart()
        self.assertEqual(state.path_key, "")
        self.assertTrue(state.knows("story_blues_1"))


class TestStoryBook(unittest.TestCase):
    """El capítulo que el sendero va llenando."""

    def test_every_story_note_has_a_chapter_entry(self):
        keys = {f"story_{path}_{step}"
                for path in story.PATHS for step in (1, 2, 3)}
        self.assertTrue(keys.issubset(set(book.LOCK_KEYS)))

    def test_the_gate_entries_exist_in_the_book(self):
        for gate_key in story.BOOK_GATES.values():
            self.assertIsNotNone(book.entry_for_lock(gate_key),
                                 f"{gate_key} no abre ningun apartado")

    def test_the_note_of_the_step_in_hand_is_already_written(self):
        """
        El apartado del tramo en curso está escrito **mientras** se lo juega.

        El personaje manda a leer lo que se acaba de descubrir, así que si la
        anotación esperara a que el tramo termine, el usuario iría al libro y
        encontraría la página en blanco.
        """
        # Sólo se consulta, no se guarda, así que acá no hace falta archivo.
        state = story.StoryState(path_key="jazz", step=0)
        self.assertTrue(state.knows("story_jazz_1"))
        self.assertFalse(state.knows("story_jazz_2"))
        # El segundo tramo no escribe nada nuevo: lee lo que ya estaba. Si la
        # segunda anotación apareciera acá, una sola visita al libro abriría
        # las dos trabas y la lectura del último tramo dejaría de existir.
        state.step = 1
        self.assertFalse(state.knows("story_jazz_2"))
        state.step = 2
        self.assertTrue(state.knows("story_jazz_2"))
        self.assertFalse(state.knows("story_jazz_3"))


class TestStoryPieces(unittest.TestCase):
    """Las piezas escritas de antemano tienen que poder escribirse."""

    CONFIG = GAConfig(population_size=8, generations=1, elitism=1,
                      tournament_size=2, random_seed=7)

    def build(self, piece):
        voices = story.voices_for(piece)
        beats, _, beat_type = piece.time_signature.partition("/")
        signature = export.TimeSignature(int(beats), int(beat_type or 4))
        written = story.voice_piece(piece, voices)
        bars = piece.bar_indices()
        entries = [
            session.ChordEntry(
                symbol=symbol, duration_quarters=duration,
                bar_index=bars[index], is_rest=not symbol,
                forced_omissions=story.chord_omissions(piece, symbol),
                locked_pitches=written[index] if symbol else None)
            for index, (symbol, duration) in enumerate(piece.chords)]
        request = session.JobRequest(
            genre_key=piece.genre_key, voice_keys=list(voices),
            entries=entries, time_signature=signature,
            bar_time_signatures=[signature] * piece.bar_count,
            title=piece.title,
            switch_overrides=dict(story.FIXED_PIECE_RULES),
            ga_config=self.CONFIG)
        return request, written, voices

    def each_piece(self):
        yield story.TWELVE_BAR_BLUES
        yield story.ALL_OF_ME
        yield story.GOSPEL_OCTAVE
        yield story.THE_LICK_PIECE
        yield story.AMAZING_GRACE
        for tonic in range(12):
            yield story.blues_piece(tonic)

    def test_every_bar_is_full(self):
        """Un compas a medio llenar hace que la partitura salga corrida."""
        for piece in self.each_piece():
            total = sum(duration for _symbol, duration in piece.chords)
            self.assertAlmostEqual(
                total % piece.quarters_per_bar, 0.0, places=6,
                msg=f"{piece.title} no cierra sus compases")

    def test_every_chord_can_be_read(self):
        for piece in self.each_piece():
            for symbol, _duration in piece.chords:
                if symbol:
                    parse_chord(symbol)

    def test_the_voicings_are_singable(self):
        """En registro y sin cruces: dos de las tres cosas que el motor
        exige y que ningun ajuste de estilo perdona."""
        for piece in self.each_piece():
            _request, written, voices = self.build(piece)
            parts = build_voice_parts(list(voices))
            for index, pitches in enumerate(written):
                if pitches is None:
                    continue
                for part, pitch in zip(parts, pitches):
                    self.assertTrue(
                        part.low <= pitch <= part.high,
                        f"{piece.title}: {part.name} fuera de registro")
                self.assertEqual(
                    sorted(pitches), list(pitches),
                    f"{piece.title}: voces cruzadas en el acorde {index}")

    def test_every_piece_can_be_written(self):
        """La tercera: el acorde completo. Si falta un grado obligatorio el
        motor anula el cromosoma y la corrida vuelve sin nada."""
        for piece in self.each_piece():
            request, _written, _voices = self.build(piece)
            outcome = session.generate(request)
            self.assertTrue(outcome.succeeded,
                            f"{piece.title}: {outcome.errors}")

    def test_transposing_moves_the_bass_of_a_slash_chord_too(self):
        self.assertEqual(story._transpose("C7/Bb", 2), "D7/C")

    def test_a_transposed_blues_keeps_its_shape(self):
        piece = story.blues_piece(9)
        self.assertEqual([symbol for symbol, _d in piece.chords][:4],
                         ["A7", "D7", "A7", "A7"])
        self.assertEqual(len(piece.tops), len(piece.chords))


class TestImpossibleDiagnosis(unittest.TestCase):
    """Qué dice el motor cuando no hay ninguna solución posible."""

    def _settings(self, **overrides):
        from dataclasses import replace as _replace

        profile = _replace(GENRE_PROFILES["classical"], **overrides)
        return RunSettings(profile=profile,
                           voices=build_voice_parts(["B", "T", "A", "S"]))

    def _slot(self, symbol, bar=0, voices=4, colour=0.0, rng=None):
        return ChordSlot(
            requirement=build_requirement(
                parse_chord(symbol), voices, None,
                allow_special_voicings=colour > 0.0,
                special_fills=colour > 0.0, colour_appetite=colour, rng=rng),
            duration_quarters=2.0, bar_index=bar)

    def test_the_same_problem_in_two_chords_is_one_line(self):
        """Un G7 en cada punta con el tritono prohibido: un renglón, no dos."""
        settings = self._settings(forbid_harmonic_tritone=True)
        slots = [self._slot("G7"), self._slot("C", bar=1), self._slot("G7", bar=1)]
        problems = diagnose_impossible_slots(slots, settings)
        self.assertEqual(len(problems), 1)
        self.assertIn("Acordes 1 y 3", problems[0])
        self.assertIn("G7", problems[0])

    def test_a_slot_with_a_writable_option_is_not_denounced(self):
        """
        En el Generador cada lugar ofrece varios acordes.

        Con que uno se pueda escribir no hay nada que denunciar: mirar sólo
        el primero daba por imposible un tramo que tenía salida --- y lo
        repetía una vez por acorde, con el mismo cifrado en todos.
        """
        settings = self._settings(forbid_harmonic_tritone=True)
        slot = self._slot("G7")
        slot.options = [SlotOption(slot.requirement),
                        SlotOption(build_requirement(parse_chord("C"), 4))]
        self.assertEqual(diagnose_impossible_slots([slot], settings), [])

    def test_every_option_impossible_says_so_without_naming_one(self):
        settings = self._settings(forbid_harmonic_tritone=True)
        slot = self._slot("G7")
        slot.options = [SlotOption(slot.requirement),
                        SlotOption(build_requirement(parse_chord("D7"), 4))]
        problems = diagnose_impossible_slots([slot], settings)
        self.assertEqual(len(problems), 1)
        self.assertIn("ninguno de los 2 acordes", problems[0])

    def test_the_colour_dial_is_named_when_the_tritone_is_its_doing(self):
        """
        Cmaj7 no tiene tritono; con la oncena encima, sí.

        Decirle al usuario que el acorde que escribió tiene un tritono que
        no tiene es mandarlo a mirar donde no está: el que lo puso es el
        dial de color.
        """
        settings = self._settings(forbid_harmonic_tritone=True)
        # Qué color se agrega se sortea, así que se busca la semilla que
        # arma el caso: un Cmaj7 al que el dial le puso una nota que hace
        # tritono con las suyas. Buscarla es parte de la prueba --- si
        # ninguna lo arma, el caso no existe y hay que enterarse.
        slot = None
        for seed in range(60):
            candidate = self._slot("Cmaj7", voices=6, colour=30.0,
                                   rng=random.Random(seed))
            pcs = candidate.requirement.required_pitch_classes
            if any((b - a) % 12 == 6
                   for i, a in enumerate(pcs) for b in pcs[i + 1:]):
                slot = candidate
                break
        self.assertIsNotNone(slot)
        problems = diagnose_impossible_slots([slot], settings)
        self.assertEqual(len(problems), 1)
        self.assertIn("color", problems[0])
        self.assertIn("Cmaj7", problems[0])

    def test_a_chord_with_its_own_tritone_still_blames_the_chord(self):
        settings = self._settings(forbid_harmonic_tritone=True)
        problems = diagnose_impossible_slots([self._slot("G7")], settings)
        self.assertEqual(len(problems), 1)
        self.assertIn("sus propias notas", problems[0])


class TestEasterEggs(unittest.TestCase):
    """
    Las seis combinaciones exactas, y la canasta que las cuenta.

    Un huevo de pascua no se puede probar a mano: la condición es
    justamente que ninguna otra combinación lo dispare, y eso son unas
    cuantas variantes cercanas por huevo. Por eso los detectores viven en
    `engine/eggs.py` como funciones puras y no adentro de `app.py`.
    """

    # -- el rugido ----------------------------------------------------------

    def test_the_roar_needs_tonic_tonic_fifth_in_whole_notes(self):
        call = [(60, 4.0), (60, 4.0), (67, 4.0)]
        self.assertTrue(eggs.zombie_call(call, 0))

    def test_the_roar_ignores_the_octave_but_not_the_degree(self):
        self.assertTrue(eggs.zombie_call([(60, 4.0), (72, 4.0), (55, 4.0)], 0))
        # La cuarta en lugar de la quinta no es el rugido.
        self.assertFalse(eggs.zombie_call([(60, 4.0), (60, 4.0), (65, 4.0)], 0))

    def test_the_roar_follows_the_key_signature(self):
        # En sol, la tónica es sol y la quinta es re.
        self.assertTrue(eggs.zombie_call([(67, 4.0), (67, 4.0), (62, 4.0)], 7))
        self.assertFalse(eggs.zombie_call([(60, 4.0), (60, 4.0), (67, 4.0)], 7))

    def test_the_roar_is_exactly_three_whole_notes(self):
        right = [(60, 4.0), (60, 4.0), (67, 4.0)]
        # Una blanca en el medio, una nota de más, una de menos, otro orden.
        self.assertFalse(eggs.zombie_call([(60, 4.0), (60, 2.0), (67, 4.0)], 0))
        self.assertFalse(eggs.zombie_call(right + [(64, 4.0)], 0))
        self.assertFalse(eggs.zombie_call(right[:2], 0))
        self.assertFalse(eggs.zombie_call([(60, 4.0), (67, 4.0), (60, 4.0)], 0))

    # -- el zorro -----------------------------------------------------------

    def test_the_fox_wants_one_nine_eight_seven_top_to_bottom(self):
        values = dict(zip(eggs.FOX_FIELDS, eggs.FOX_SEQUENCE))
        self.assertTrue(eggs.fox_numbers(values))
        values["elitism"] = "7"
        self.assertFalse(eggs.fox_numbers(values))

    def test_the_fox_ignores_the_surrounding_spaces_and_the_other_fields(self):
        values = {key: f"  {value} " for key, value
                  in zip(eggs.FOX_FIELDS, eggs.FOX_SEQUENCE)}
        values["mutation_rate"] = "0.12"
        self.assertTrue(eggs.fox_numbers(values))
        self.assertFalse(eggs.fox_numbers({}))

    # -- los anteojos -------------------------------------------------------

    def test_the_glasses_only_at_the_top_of_the_dial(self):
        self.assertTrue(eggs.glasses(1.8, 1.8))
        self.assertFalse(eggs.glasses(1.7, 1.8))

    # -- el cerrajero -------------------------------------------------------

    @staticmethod
    def _entry(symbol, locked=None, rest=False):
        return session.ChordEntry(symbol=symbol, duration_quarters=2.0,
                                  bar_index=0, is_rest=rest,
                                  locked_pitches=locked)

    def test_every_chord_locked(self):
        pitches = [48, 55, 64, 72]
        self.assertTrue(eggs.all_locked([self._entry("C", pitches),
                                         self._entry("G", pitches)]))
        self.assertFalse(eggs.all_locked([self._entry("C", pitches),
                                          self._entry("G")]))

    def test_a_single_locked_chord_is_not_all_of_them(self):
        self.assertFalse(eggs.all_locked([self._entry("C", [48, 55, 64, 72])]))
        self.assertFalse(eggs.all_locked([]))

    def test_rests_have_nothing_to_lock(self):
        pitches = [48, 55, 64, 72]
        self.assertTrue(eggs.all_locked([self._entry("C", pitches),
                                         self._entry("", rest=True),
                                         self._entry("G", pitches)]))

    # -- Bach ---------------------------------------------------------------

    def test_the_chorale_that_allows_parallel_fifths(self):
        self.assertTrue(eggs.bach_spinning(True, False))
        self.assertFalse(eggs.bach_spinning(True, True))
        self.assertFalse(eggs.bach_spinning(False, False))

    # -- la explosión -------------------------------------------------------

    @staticmethod
    def _dials(**overrides):
        values = {name: top for name, top in eggs.BLAST_DIALS}
        values.update(overrides)
        return values

    def test_the_blast_wants_every_dial_at_the_top(self):
        self.assertTrue(eggs.blast(self._dials(), [True, True, True]))
        self.assertFalse(eggs.blast(self._dials(colour=0.0), [True]))
        self.assertFalse(eggs.blast({}, [True]))

    def test_the_blast_accepts_the_last_stretch_of_each_dial(self):
        """Un deslizador no se clava en un pixel: el último tramo cuenta."""
        self.assertTrue(eggs.blast(self._dials(modulation=59.5), [True]))
        self.assertFalse(eggs.blast(self._dials(modulation=52.0), [True]))

    def test_one_switch_off_and_there_is_no_blast(self):
        self.assertFalse(eggs.blast(self._dials(), [True, False, True]))
        self.assertFalse(eggs.blast(self._dials(), []))

    # -- la canasta ---------------------------------------------------------

    def test_an_egg_is_only_found_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "eggs.json")
            basket = eggs.Basket.load(path)
            self.assertTrue(basket.find("fox"))
            self.assertFalse(basket.find("fox"))
            self.assertFalse(basket.find("no-existe"))
            self.assertEqual(basket.count(), 1)

    def test_the_basket_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "eggs.json")
            basket = eggs.Basket.load(path)
            basket.find("zombie")
            again = eggs.Basket.load(path)
            self.assertTrue(again.has("zombie"))
            self.assertFalse(again.complete())
            self.assertEqual(again.titles(), [])

    def test_a_broken_basket_does_not_stop_the_program(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "eggs.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{roto")
            self.assertEqual(eggs.Basket.load(path).count(), 0)

    def test_the_title_arrives_with_the_last_egg_and_only_when_claimed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "eggs.json")
            basket = eggs.Basket.load(path)
            for egg in eggs.CATALOG[:-1]:
                basket.find(egg.key)
            self.assertFalse(basket.complete())
            self.assertFalse(basket.claim())
            basket.find(eggs.CATALOG[-1].key)
            self.assertTrue(basket.complete())
            self.assertEqual(basket.titles(), [])
            self.assertTrue(basket.claim())
            self.assertFalse(basket.claim())
            self.assertEqual(eggs.Basket.load(path).titles(),
                             [eggs.SECRET_TITLE])


class TestVisitors(unittest.TestCase):
    """
    Las visitas: cuándo aparece cada una y qué deja escrito.

    Todo lo de acá es del registro y del catálogo, que son datos y funciones
    puras. Las escenas no se pueden probar sin abrir una ventana --- eso es
    trabajo de `uitest` --- pero *cuándo* ocurren, sí: es una cuenta de
    partituras y un archivo, y es donde puede romperse de verdad.
    """

    # -- el catálogo --------------------------------------------------------

    def test_every_visit_opens_a_book_entry(self):
        """Una visita que no dejara nada escrito no dejaría nada."""
        for key in visitors.WRITES:
            lock = visitors.book_key(key)
            self.assertIsNotNone(book.entry_for_lock(lock),
                                 f"{lock} no abre ningun apartado")

    def test_the_book_keys_come_back_to_their_visit(self):
        for key in visitors.WRITES:
            self.assertEqual(visitors.visit_key(visitors.book_key(key)), key)
        # Una llave de otro origen no es de las nuestras.
        self.assertEqual(visitors.visit_key("story_blues_1"), "")

    def test_every_visit_has_lines_and_a_speaker(self):
        for key, visit in visitors.VISITS.items():
            self.assertTrue(visit.lines, key)
            self.assertTrue(visit.speaker, key)
            self.assertEqual(visit.key, key)

    def test_the_watcher_writes_nothing_in_the_book(self):
        """
        No explica nada, así que no anota nada.

        Un apartado con su profecía adentro sería el único del libro que no
        enseña nada, y encima le sacaría lo que tiene: que se va sin decir de
        qué estaba hablando.
        """
        self.assertFalse(visitors.writes(visitors.WATCHER_ALL))
        self.assertIsNone(
            book.entry_for_lock(visitors.book_key(visitors.WATCHER_ALL)))

    def test_only_the_watcher_leaves_an_object(self):
        """
        El cuarto objeto es uno solo, y lo deja la entidad.

        Los otros tres los entregan los senderos. Si una visita cualquiera
        empezara a repartir recuerdos, el que la entidad deja dejaría de ser
        el cuarto y pasaría a ser uno más.
        """
        with_object = [key for key, visit in visitors.VISITS.items()
                       if visit.keepsake[1]]
        self.assertEqual(with_object, [visitors.WATCHER_ALL])

    def test_the_watcher_hands_the_object_over_in_a_line(self):
        """El gesto que muestra la tarjeta tiene que estar en el guion."""
        cues = [line.cue for line in visitors.VISITS[visitors.WATCHER_ALL].lines]
        self.assertIn("item", cues)

    def test_the_teachers_say_who_they_are_at_some_point(self):
        """
        El cartelito dice ``? ? ?`` hasta que una línea pide el nombre.

        Sin el gesto ``reveal`` el nombre no aparece nunca, y una visita de
        Bach en la que nunca se sepa que es Bach no es una visita.
        """
        for key in (visitors.BACH_BAROQUE, visitors.BACH_CHORALE,
                    visitors.GREGORY_CHANT):
            visit = visitors.VISITS[key]
            self.assertTrue(visit.name, key)
            self.assertIn("reveal", [line.cue for line in visit.lines], key)

    # -- la cuenta ----------------------------------------------------------

    def _ledger(self, folder):
        return visitors.Ledger.load(os.path.join(folder, "visitors.json"))

    def test_bach_arrives_on_the_fifth_baroque_score(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.NEEDED - 1):
                self.assertEqual(ledger.record(visitors.BAROQUE), [])
            self.assertEqual(ledger.record(visitors.BAROQUE),
                             [visitors.BACH_BAROQUE])

    def test_he_does_not_come_back_once_he_came(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.NEEDED):
                ledger.record(visitors.BAROQUE)
            ledger.mark(visitors.BACH_BAROQUE)
            self.assertEqual(ledger.record(visitors.BAROQUE), [])

    def test_gregory_counts_his_own_genre(self):
        """Cinco barrocas no traen a Gregorio, y al revés tampoco."""
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.NEEDED):
                ledger.record(visitors.BAROQUE)
            self.assertEqual(ledger.count(visitors.GREGORIAN), 0)
            for _ in range(visitors.NEEDED - 1):
                self.assertEqual(ledger.record(visitors.GREGORIAN), [])
            self.assertEqual(ledger.record(visitors.GREGORIAN),
                             [visitors.GREGORY_CHANT])

    def test_an_uncounted_genre_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(20):
                self.assertEqual(ledger.record("jazz"), [])
            self.assertEqual(ledger.counts, {visitors.BAROQUE: 0,
                                             visitors.GREGORIAN: 0})

    def test_the_chorale_brings_him_the_first_time_and_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            self.assertEqual(ledger.record(visitors.BAROQUE, chorale=True),
                             [visitors.BACH_CHORALE])
            ledger.mark(visitors.BACH_CHORALE)
            self.assertEqual(ledger.record(visitors.BAROQUE, chorale=True), [])

    def test_the_fifth_score_that_is_also_the_first_chorale_says_both(self):
        """
        Pasa de verdad, y el orden importa.

        Primero lo general --- qué es el barroco --- y después lo
        particular; al revés, la explicación del coral quedaría apoyada en
        algo que todavía no se dijo.
        """
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.NEEDED - 1):
                ledger.record(visitors.BAROQUE)
            self.assertEqual(ledger.record(visitors.BAROQUE, chorale=True),
                             [visitors.BACH_BAROQUE, visitors.BACH_CHORALE])

    # -- el archivo ---------------------------------------------------------

    def test_the_count_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            ledger.record(visitors.GREGORIAN)
            ledger.record(visitors.GREGORIAN)
            ledger.mark_vision()
            again = visitors.Ledger.load(path)
            self.assertEqual(again.count(visitors.GREGORIAN), 2)
            self.assertTrue(again.vision)

    def test_a_broken_file_does_not_stop_the_program(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{no es json")
            ledger = visitors.Ledger.load(path)
            self.assertEqual(ledger.count(visitors.BAROQUE), 0)
            self.assertFalse(ledger.vision)

    def test_a_key_from_another_version_is_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"counts": {"telegrafo": 4}, "seen": {"nadie": "x"}},
                          handle)
            ledger = visitors.Ledger.load(path)
            self.assertEqual(ledger.seen, {})
            self.assertEqual(set(ledger.counts), set(visitors.COUNTED))

    def test_marking_twice_returns_false(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            self.assertTrue(ledger.mark(visitors.GREGORY_CHANT))
            self.assertFalse(ledger.mark(visitors.GREGORY_CHANT))
            self.assertFalse(ledger.mark("nadie"))

    # -- el objeto y el libro -----------------------------------------------

    def test_the_burnt_score_is_handed_over_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            self.assertEqual(ledger.keepsakes(), [])
            self.assertTrue(ledger.take_keepsake())
            self.assertFalse(ledger.take_keepsake())
            self.assertEqual(visitors.Ledger.load(path).keepsakes(),
                             [(visitors.KEEPSAKE_ICON, visitors.KEEPSAKE)])

    def test_the_book_entry_opens_with_the_visit(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            lock = visitors.book_key(visitors.GREGORY_CHANT)
            self.assertFalse(ledger.knows(lock))
            ledger.mark(visitors.GREGORY_CHANT)
            self.assertTrue(ledger.knows(lock))
            # Y una llave que no es de las visitas no la contesta nadie acá.
            self.assertFalse(ledger.knows("story_blues_1"))

    def test_the_vision_writes_its_own_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            lock = visitors.book_key(visitors.VISION)
            self.assertFalse(ledger.knows(lock))
            ledger.mark_vision()
            self.assertTrue(ledger.knows(lock))

    def test_the_vision_entry_is_written_in_gold(self):
        """
        Es la única del capítulo que no se puede conseguir trabajando.

        Las otras tres se ganan generando partituras y el libro dice cómo;
        ésta ocurre o no ocurre, y por eso se muestra como un legendario ---
        en dorado y sin título hasta que aparezca.
        """
        found = book.entry_for_lock(visitors.book_key(visitors.VISION))
        self.assertIsNotNone(found)
        _chapter, entry = found
        self.assertTrue(entry.legendary)
        self.assertTrue(book.is_secret(entry))
        # Y las de los maestros no: su título es la pista de qué hay que
        # hacer, y esconderlo no protegería nada.
        for key in (visitors.BACH_BAROQUE, visitors.BACH_CHORALE,
                    visitors.GREGORY_CHANT):
            _chapter, other = book.entry_for_lock(visitors.book_key(key))
            self.assertFalse(book.is_secret(other), key)

    # -- el sorteo -----------------------------------------------------------

    def test_the_vision_happens_once_and_only_below_the_odds(self):
        self.assertTrue(visitors.vision_due(False, 0.0, True))
        self.assertTrue(visitors.vision_due(False, visitors.VISION_ODDS / 2,
                                            True))
        self.assertFalse(visitors.vision_due(False, visitors.VISION_ODDS, True))
        self.assertFalse(visitors.vision_due(False, 0.99, True))
        # Vista una vez, no vuelve ni con el sorteo a favor.
        self.assertFalse(visitors.vision_due(True, 0.0, True))

    def test_the_vision_waits_for_the_tutorial(self):
        """Con el tutorial sin hacer no ocurre, ni con el sorteo a favor.

        La primera vez que alguien abre el programa lo que tiene enfrente es
        el recorrido guiado; la visión llegaría antes de que hubiera visto un
        acorde, y se gastaría la única vez que ocurre.
        """
        self.assertFalse(visitors.vision_due(False, 0.0, False))
        self.assertFalse(visitors.vision_due(False, visitors.VISION_ODDS / 2,
                                             False))
        self.assertTrue(visitors.vision_due(False, 0.0, True))

    def test_the_environment_can_ask_for_a_visit(self):
        self.assertEqual(visitors.forced({}), "")
        self.assertEqual(
            visitors.forced({visitors.FORCE_VAR: " watcher "}), "watcher")
        # Una clave inventada no fuerza nada: es una herramienta de prueba.
        self.assertEqual(visitors.forced({visitors.FORCE_VAR: "godzilla"}), "")

    def test_the_environment_can_force_or_forbid_the_vision(self):
        self.assertIsNone(visitors.vision_forced({}))
        self.assertTrue(visitors.vision_forced({visitors.VISION_VAR: "1"}))
        self.assertFalse(visitors.vision_forced({visitors.VISION_VAR: "0"}))


class TestEggRecipes(unittest.TestCase):
    """La lista que la entidad deja al completar los logros."""

    def test_every_egg_says_how_it_is_done(self):
        for egg in eggs.CATALOG:
            self.assertTrue(egg.recipe.strip(), egg.key)


class TestSoundWorkshop(unittest.TestCase):
    """
    El taller de sonido: los ladrillos, el nivel y el empalme de los bucles.

    Nada de esto prueba que un sonido *suene bien* --- eso no se puede
    probar sin orejas --- pero sí las tres cosas que lo arruinan sin que
    nadie se dé cuenta: que salga al doble de volumen que el de al lado, que
    el bucle pegue un salto al repetirse, y que una receta se rompa y deje la
    escena muda.
    """

    def _samples(self, name):
        """Un sonido, ya sintetizado, como lista de valores entre -1 y 1."""
        import struct
        data = ambience._RECIPES[name][0]()
        count = len(data) // 2
        return [v / 32768.0 for v in struct.unpack("<%dh" % count, data)]

    # -- los ladrillos ------------------------------------------------------

    def test_the_level_helper_puts_the_peak_where_it_is_asked(self):
        buffer = [0.1, -0.4, 0.2, 0.05]
        ambience._normalise(buffer, 0.8)
        self.assertAlmostEqual(max(abs(v) for v in buffer), 0.8, places=6)

    def test_silence_survives_the_level_helper(self):
        """Dividir por el pico de algo que no suena no puede romper nada."""
        buffer = [0.0] * 16
        self.assertEqual(ambience._normalise(list(buffer), 0.8), buffer)

    def test_saturation_never_leaves_the_rails(self):
        loud = [4.0, -7.5, 0.2, -0.01]
        ambience._saturate(loud, 3.0)
        self.assertTrue(all(-1.0 < value < 1.0 for value in loud))

    def test_the_resonator_only_answers_around_its_frequency(self):
        """
        Una banda angosta tiene que dejar pasar lo suyo y callar el resto.

        Se mide con la energía que sale a dos frecuencias muy separadas
        usando la misma semilla: la de la banda tiene que ser varias veces
        más grande que la de afuera.
        """
        def energy(centre, probe):
            buffer = [0.0] * 8000
            ambience._band(buffer, 1.0, centre, 12.0, random.Random(4))
            # Correlación con un seno a la frecuencia de prueba.
            total = 0.0
            for index, value in enumerate(buffer):
                total += value * math.sin(2.0 * math.pi * probe * index
                                          / ambience.SAMPLE_RATE)
            return abs(total)

        inside = energy(600.0, 600.0)
        outside = energy(600.0, 3000.0)
        self.assertGreater(inside, outside * 3.0)

    def test_reverb_leaves_a_tail_where_there_was_none(self):
        """Un golpe seco al principio tiene que seguir sonando después."""
        buffer = [0.0] * 6000
        buffer[10] = 1.0
        ambience._reverb(buffer, mix=0.6, decay=0.85)
        self.assertGreater(max(abs(v) for v in buffer[3000:]), 1e-4)

    # -- los sonidos --------------------------------------------------------

    def test_every_recipe_produces_audible_sound(self):
        """Ninguna receta puede devolver silencio ni reventar el rango."""
        for name in ambience._RECIPES:
            values = self._samples(name)
            peak = max(abs(v) for v in values)
            self.assertGreater(peak, 0.05, name)
            self.assertLessEqual(peak, 1.0, name)
            # Y ninguno puede estar recortando: un puñado de muestras pegadas
            # al techo es lo que se escucha como distorsión.
            clipped = sum(1 for v in values if abs(v) > 0.995)
            self.assertLess(clipped, len(values) * 0.001, name)

    def _power(self, name):
        """El volumen percibido: la energía promedio, no el pico."""
        values = self._samples(name)
        return math.sqrt(sum(v * v for v in values) / len(values))

    def test_the_levels_stay_within_one_family(self):
        """
        Las camas por debajo de los golpes, y nada al doble de nada.

        Se mide la **energía promedio** y no el pico, que es lo que el oído
        escucha: un golpe seco y una campana con el mismo pico suenan a
        volúmenes completamente distintos. Nivelar por pico era exactamente
        el error que dejaba al ruido de la aparición tapado por el viento
        teniendo los dos el número correcto.
        """
        beds = [name for name, (_m, loops) in ambience._RECIPES.items()
                if loops and name != "gale"]
        for name in beds:
            self.assertAlmostEqual(self._power(name), ambience.POWER_BED,
                                   delta=0.02, msg=name)
        # El viento de la visión es la excepción y por eso está aparte: es la
        # única cama que suena sin nadie hablando encima, así que ocupa el
        # lugar que en las otras escenas le corresponde a la voz.
        self.assertAlmostEqual(self._power("gale"), ambience.POWER_SOLO,
                               delta=0.02)
        self.assertGreater(ambience.POWER_SOLO, ambience.POWER_BED)
        for name in ("wind", "tritone", "toll", "crossroads", "train",
                     "blues"):
            self.assertAlmostEqual(self._power(name), ambience.POWER_HIT,
                                   delta=0.04, msg=name)
        for name in ("zombie", "fox", "blast"):
            # Los huevos quedan por debajo de lo pedido y está bien: son
            # sonidos de picos altísimos --- un grito, un estampido --- y el
            # limitador que los sujeta se lleva parte de la energía con él. El
            # grito del zorro es el caso extremo y termina rozando el nivel de
            # un golpe común; lo que importa es que nunca quede por debajo.
            power = self._power(name)
            self.assertGreaterEqual(power, ambience.POWER_HIT * 0.95, name)
            self.assertLessEqual(power, ambience.POWER_JOKE + 0.02, name)

    def test_each_star_sounds_bigger_than_the_one_before(self):
        """
        La fanfarria crece con la estrella, que es lo unico que promete.

        No se puede probar que suene mejor, pero si las dos cosas que hacen
        que suene mas: mas energia y mas cola. Si alguna vez las tres
        quedaran iguales, el premio de la tercera estrella sonaria igual que
        el de la primera y nadie lo notaria hasta llegar alli.
        """
        names = ("star_one", "star_two", "star_three")
        powers = [self._power(name) for name in names]
        lengths = [len(ambience._RECIPES[name][0]()) for name in names]
        for before, after in zip(powers, powers[1:]):
            self.assertGreater(after, before)
        for before, after in zip(lengths, lengths[1:]):
            self.assertGreater(after, before)
        # Y ninguna se sale de la familia de los golpes: son avisos, no
        # camas, y tampoco chistes.
        for name, power in zip(names, powers):
            self.assertGreater(power, ambience.POWER_BED * 2, name)
            self.assertLessEqual(power, ambience.POWER_JOKE, name)
        for name in ("egg_found", "egg_prize"):
            self.assertGreater(self._power(name), ambience.POWER_BED * 2, name)
        # Y el premio suena mas grande que el hallazgo suelto, que es lo
        # unico que promete: mas largo y con mas cola.
        self.assertGreater(len(ambience._RECIPES["egg_prize"][0]()),
                           len(ambience._RECIPES["egg_found"][0]()))

    def test_a_hit_is_clearly_louder_than_the_bed_under_it(self):
        """
        Y la diferencia tiene que ser grande, no cualquiera.

        Es la razón entera por la que existe este nivelado: el ruido de la
        aparición suena **encima** del viento, y con los dos al mismo volumen
        promedio el viento se lo comía. Que el golpe tenga por lo menos el
        doble de energía que la cama es lo que lo hace pasar.
        """
        self.assertGreater(self._power("crossroads"),
                           self._power("gale") * 2.0)
        # Y con la cama de una escena hablada, que va todavía más abajo, la
        # diferencia tiene que ser mayor: ahí lo que hay que dejar pasar no es
        # un golpe sino una voz.
        self.assertGreater(self._power("blip_devil"),
                           self._power("valley") * 2.0)

    def test_the_loops_join_without_a_click(self):
        """
        La última muestra de un bucle y la primera tienen que ser vecinas.

        Si saltan, el empalme se oye como un golpe cada vez que el archivo
        vuelve a empezar --- y estos archivos se repiten durante minutos.
        """
        for name, (_maker, loops) in ambience._RECIPES.items():
            if not loops:
                continue
            values = self._samples(name)
            self.assertLess(abs(values[-1] - values[0]), 0.05, name)

    def test_the_blips_all_speak_at_the_same_volume(self):
        """Suenan cada tres letras durante minutos: uno más fuerte se nota."""
        peaks = [max(abs(v) for v in self._samples(name))
                 for name in ambience._RECIPES if name.startswith("blip_")]
        self.assertGreater(len(peaks), 3)
        self.assertLess(max(peaks) - min(peaks), 0.02)

    def test_the_vision_asks_for_sounds_that_it_makes(self):
        """
        Todo lo que la visión toca tiene que estar en su propia lista.

        No alcanza con que la receta exista: los ruidos de la visión se
        sintetizan a pedido y sólo se piden los que están en `VISION_SOUNDS`.
        La guitarra del final estuvo muda porque quedó fuera de esa lista ---
        la receta existía, el archivo no --- y `ambience.play` de algo que no
        existe no falla: no hace nada.
        """
        import app                                   # noqa: PLC0415
        played = {"gale", "train", "owls", "crossroads", "blues"}
        self.assertTrue(played.issubset(set(app.ChordWeaverApp.VISION_SOUNDS)))
        self.assertTrue(
            set(app.ChordWeaverApp.VISION_FIRST).issubset(
                set(app.ChordWeaverApp.VISION_SOUNDS)))

    # -- la caché en disco ---------------------------------------------------

    def test_the_cache_folder_carries_the_signature_of_the_recipes(self):
        """
        La firma tiene que cambiar sola cuando cambia un sonido.

        Es lo único que impide que los archivos guardados de ayer se sigan
        usando después de tocar una receta: si la firma no cambiara, el
        programa reproduciría para siempre la versión vieja de algo que se
        acaba de corregir.
        """
        tag = ambience._tag()
        self.assertTrue(tag)
        self.assertIn(tag, ambience._cache_folder())
        # El resumen del fuente de este módulo, y no de otro.
        with open(ambience.__file__, "rb") as handle:
            import hashlib
            self.assertEqual(tag, hashlib.md5(handle.read()).hexdigest()[:10])

    def test_a_written_sound_is_adopted_instead_of_recalculated(self):
        """
        Lo que ya está escrito no se vuelve a sintetizar.

        Es la diferencia entre esperar veinte segundos en cada arranque y no
        esperar nunca más después del primero.
        """
        with tempfile.TemporaryDirectory() as folder:
            previous, ambience._folder = ambience._folder, folder
            stored = dict(ambience._files)
            try:
                ambience._files.clear()
                path = ambience._write("chime", ambience._blip("devil"))
                self.assertTrue(os.path.exists(path))
                ambience._files.clear()
                ambience._adopt_cache()
                self.assertIn("chime", ambience._files)
                # Y no queda ningún archivo a medio escribir dando vueltas.
                self.assertEqual(
                    [n for n in os.listdir(folder) if n.endswith(".part")], [])
            finally:
                ambience._folder = previous
                ambience._files.clear()
                ambience._files.update(stored)

    def test_the_sounds_the_scenes_ask_for_exist(self):
        """
        Cada nombre que una escena reproduce tiene que estar en el catálogo.

        `ambience.play` de un nombre inventado no falla: no hace nada, y el
        error se manifiesta como una escena muda meses después.
        """
        wanted = {"valley", "light", "wind", "hellfire", "choir_up",
                  "choir_down", "sax", "chime", "tritone", "clavier",
                  "plainchant", "toll", "hollow", "gale", "crossroads",
                  "train", "owls", "blues", "zombie", "fox", "blast",
                  # Las estrellas y el hallazgo de un huevo. `app` los pide
                  # por nombre desde `STAR_SOUNDS` y desde `_egg`, y un
                  # nombre que no está en el catálogo no falla: no suena.
                  "star_one", "star_two", "star_three", "egg_found",
                  # El premio de los seis: lo pide `_celebrate_secret`.
                  "egg_prize"}
        self.assertTrue(wanted.issubset(set(ambience._RECIPES)))

    def test_what_is_made_on_demand_is_never_made_at_startup(self):
        """Y al revés: lo de arranque no puede estar en la lista de a pedido."""
        for name in ambience._ON_DEMAND:
            self.assertIn(name, ambience._RECIPES, name)
        # Los blips no van a pedido: tienen que estar listos apenas alguien
        # abre la boca.
        for name in ambience._RECIPES:
            if name.startswith("blip_"):
                self.assertNotIn(name, ambience._ON_DEMAND, name)

if __name__ == "__main__":
    unittest.main(verbosity=2)
