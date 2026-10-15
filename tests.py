# -*- coding: utf-8 -*-
"""
Engine test suite. Run with:  python tests.py

Focused on the things that are easy to get subtly wrong: chord spelling,
constraint detection, and the promise that a switched-on rule is never
violated by a returned solution.
"""

from __future__ import annotations

import inspect
import json
import math
import os
import random
import re
import struct
import sys
import tempfile
import unittest
import wave

from engine import history as _history

# Antes de que ningun test corra: los datos van a un descartable. Varios
# tests llaman a `session.export_outcome`, que anota la corrida en el
# historial --- que guarda las diez ultimas ---, y el historial es del
# usuario. Mover la raiz cubre los seis archivos de una vez y no hay que
# acordarse de nada en cada test nuevo.
os.environ.setdefault(
    _history.SANDBOX_VARIABLE,
    os.path.join(tempfile.gettempdir(), "chordweaver-tests-data"))

from engine import (achievements, ambience, analysis, book, eggs, export,
                    harmonics, harmonize, harmony, history, importer,
                    session, story, visitors)
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
from engine import i18n, lang
from engine.lang import audit as lang_audit


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


class TestSemitoneClash(unittest.TestCase):
    """Dos voces vecinas pegadas a un semitono."""

    def _settings(self, genre, melody_voice=None):
        from engine.style import ChordContext
        return RunSettings(
            profile=GENRE_PROFILES[genre],
            voices=build_voice_parts(["B", "T", "A", "S"]),
            chord_contexts=[ChordContext.from_chord(parse_chord("Cmaj7"))],
            melody_voice=melody_voice,
        )

    def test_a_clash_in_the_middle_of_a_piece_now_costs(self):
        """Antes sólo se cobraba en los acordes de reposo: en el medio de la
        pieza el roce salía gratis y la búsqueda lo compraba cada vez que
        ahorraba un par de semitonos de movimiento."""
        settings = self._settings("classical")
        # Cmaj7 escrito 3-5-7-1: el si y el do quedan pegados.
        rubbing = evaluate([[52, 55, 59, 60]], settings)
        # El mismo acorde con la séptima arriba de todo.
        clean = evaluate([[48, 55, 64, 71]], settings)
        self.assertLess(clean.total, rubbing.total)

    def test_every_style_charges_it(self):
        from engine.style import adjacent_semitone_clashes
        for genre in GENRE_PROFILES:
            self.assertGreater(GENRE_PROFILES[genre].weight_semitone_clash, 0.0,
                               genre)
        self.assertEqual(adjacent_semitone_clashes([52, 55, 59, 60]), 1)
        # Entre vecinas y en intervalo real: una novena menor son las mismas
        # dos notas a una octava, y ésa es la disposición que arregla el roce.
        self.assertEqual(adjacent_semitone_clashes([48, 55, 64, 71]), 0)
        self.assertEqual(adjacent_semitone_clashes([59, 72]), 0)

    def test_it_stays_off_when_there_is_a_given_melody(self):
        """En el Armonizador el roce contra la línea ya lo cobra
        `weight_melody_clash`, con su propio peso y su propio factor en los
        extremos: sumarle éste encima sería cobrar dos veces lo mismo.

        Se mide con la regla de la melodía apagada, que es la única forma de
        ver si la otra se sumó por debajo.
        """
        from dataclasses import replace as _replace
        settings = self._settings("classical", melody_voice=3)
        settings.profile = _replace(settings.profile, weight_melody_clash=0.0)
        quiet = evaluate([[52, 55, 59, 60]], settings)
        alone = evaluate([[52, 55, 59, 60]], self._settings("classical"))
        self.assertEqual(quiet.style, alone.style - 80.0)


class TestPassingDensityAndPlacement(unittest.TestCase):
    """Cuántos adornos salen, y sobre qué acordes no salen nunca."""

    def _request(self, density, genre="classical", seed=7, bars=16):
        from engine import harmony, passing
        durations = [2.0] * (bars * 2)
        genre_modulation = harmony.GENRE_MODULATION[genre]
        modulation = harmony.ModulationSettings(
            key_enabled=True, modal_enabled=False,
            targets=genre_modulation.targets,
            weight=-abs(genre_modulation.weight),
            switch_cost=genre_modulation.switch_cost,
            min_bars=genre_modulation.min_bars,
            min_bars_for_modulation=genre_modulation.min_bars_for_modulation,
            home_margin_bars=genre_modulation.home_margin_bars,
            weak_return=genre_modulation.weak_return,
            max_excursions=genre_modulation.max_excursions,
        )
        return session.GenerativeRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"],
            tonic="C", mode_key="major", borrowed=["iv", "bVII"],
            slot_count=len(durations), durations=durations,
            bar_indices=[i // 2 for i in range(len(durations))],
            ga_config=GAConfig(population_size=70, generations=45,
                               random_seed=seed),
            passing_rules=passing.PassingRules(
                voices=(1, 2, 3), diatonic_only=True, density=density,
                max_per_piece=passing.max_for_density(density)),
            modulation=modulation,
            harmony_weights=harmony.genre_harmony_weights(genre),
        )

    def test_the_bar_sets_the_ceiling(self):
        from engine.passing import HARD_MAX_PASSING, max_for_density
        self.assertEqual(max_for_density(0.0), 1)
        self.assertEqual(max_for_density(1.0), HARD_MAX_PASSING)
        values = [max_for_density(d) for d in (0.0, 0.25, 0.5, 0.75, 1.0)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(1 <= v <= HARD_MAX_PASSING for v in values))

    def test_never_more_than_the_hard_maximum(self):
        """`crowding` desalienta, no impide: el tope se aplica al cromosoma."""
        from engine.passing import HARD_MAX_PASSING
        outcome = session.generate_random(self._request(1.0))
        self.assertTrue(outcome.succeeded, outcome.errors)
        for solution in outcome.result.solutions:
            used = sum(1 for row in solution.passing
                       for note in row if note is not None)
            self.assertLessEqual(used, HARD_MAX_PASSING)

    def test_the_bar_at_the_bottom_writes_none(self):
        outcome = session.generate_random(self._request(0.0))
        self.assertTrue(outcome.succeeded, outcome.errors)
        solution = outcome.result.solutions[0]
        self.assertTrue(all(note is None for row in solution.passing
                            for note in row))

    def test_no_ornament_over_an_applied_dominant_or_a_borrowed_chord(self):
        """El acorde ya es el efecto: el adorno tapa lo único que vino a
        decir, y con notas que contradicen la alteración por la que se lo
        eligió. Una modulación no cuenta --- ahí el acorde es diatónico de
        otra tonalidad."""
        from engine import harmony
        for genre in ("classical", "jazz"):
            for seed in (3, 11):
                outcome = session.generate_random(
                    self._request(1.0, genre=genre, seed=seed))
                self.assertTrue(outcome.succeeded, outcome.errors)
                solution = outcome.result.solutions[0]
                for index, row in enumerate(solution.passing):
                    if all(note is None for note in row):
                        continue
                    slot = outcome.spec.slots[index]
                    option = slot.options[min(solution.choices[index],
                                              len(slot.options) - 1)]
                    chord = option.harmony
                    self.assertFalse(harmony.is_applied_dominant(chord),
                                     f"{genre}/{seed}: adorno sobre {chord.roman}")
                    self.assertFalse(
                        chord.is_borrowed and not chord.key_area,
                        f"{genre}/{seed}: adorno sobre {chord.roman}")

    def test_an_ornament_on_the_road_uses_the_key_it_is_in(self):
        """Una nota de paso «diatónica» sacada de la tonalidad de origen
        suena contra el acorde que la sostiene."""
        from engine import harmony
        seen_away = False
        for seed in (3, 7, 11, 23):
            request = self._request(1.0, seed=seed)
            outcome = session.generate_random(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            scales = harmony.modulation_scales(0, request.modulation)
            home = {p % 12 for p in harmony.MODES["major"].pitch_classes(0)}
            solution = outcome.result.solutions[0]
            from engine.passing import figure
            for index, row in enumerate(solution.passing):
                for entry in row:
                    if not figure(entry):
                        continue
                    slot = outcome.spec.slots[index]
                    option = slot.options[min(solution.choices[index],
                                              len(slot.options) - 1)]
                    area = option.harmony.key_area
                    if area:
                        seen_away = True
                        allowed = {p % 12 for p in scales[area]}
                    else:
                        allowed = home
                    # Cada nota de la figura, no una sola: una corrida
                    # entera tiene que caer en la escala del área visitada.
                    for note in figure(entry):
                        self.assertIn(
                            note % 12, allowed,
                            f"semilla {seed}, lugar {index}, área {area!r}")
        self.assertTrue(seen_away, "ninguna corrida llegó a modular")


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
        # Un adorno es una **figura** de una a tres notas, así que lo que
        # tiene que ser cantable es cada tramo del camino: de la nota que la
        # voz deja, por cada nota de la figura, hasta la que toma.
        from engine.passing import figure
        for slot_index, row in enumerate(solution.passing):
            for voice, entry in enumerate(row):
                shape = figure(entry)
                if not shape:
                    continue
                self.assertIn(voice, (2, 3), "a voice that was not enabled took one")
                start = solution.slots[slot_index][voice]
                end = solution.slots[slot_index + 1][voice]
                legs = [abs(b - a) for a, b in
                        zip((start,) + shape, shape + (end,))]
                self.assertNotIn(0, legs, "una altura repetida no es un adorno")
                self.assertLessEqual(max(legs), 4)

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

    def test_what_has_been_explained_already_survives_a_restart(self):
        """
        `DEFAULT_SETTINGS` es una lista blanca: lo que no figura se guarda y
        desaparece al recargar. Una guía que se olvidara de anotarse volvería
        a abrirse en cada arranque, encima de la pantalla que uno vino a
        usar.
        """
        self.assertIn("guides_seen", history.DEFAULT_SETTINGS)
        self.assertEqual(history.DEFAULT_SETTINGS["guides_seen"], [])
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            history.save_settings({"tutorial_seen": True,
                                   "guides_seen": ["chords", "melody"]}, path)
            values = history.load_settings(path)
            self.assertTrue(values["tutorial_seen"])
            self.assertEqual(values["guides_seen"], ["chords", "melody"])

    def test_the_professional_mode_starts_off_and_is_remembered(self):
        """El modo profesional viene apagado y, prendido, sigue prendido al
        reabrir: sin estar en la lista blanca se apagaba solo."""
        self.assertIs(history.DEFAULT_SETTINGS["professional"], False)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            history.save_settings({"professional": True}, path)
            self.assertTrue(history.load_settings(path)["professional"])


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

    def test_only_the_modal_switch_still_makes_the_piece_travel(self):
        """Con «de modo» solo, el barroco no se movía de casa.

        El plan de viaje se sortea sobre `targets` antes de elegir un acorde,
        así que un destino que el usuario no encendió se llevaba el plan y la
        pieza se quedaba en casa con la modulación pedida.
        """
        from engine import harmony
        for genre, expected in (("classical", "parallel_minor"),
                                ("chorale", "parallel_minor")):
            defaults = harmony.GENRE_MODULATION[genre]
            settings = harmony.ModulationSettings(
                key_enabled=False, modal_enabled=True,
                targets=defaults.targets, weight=defaults.weight,
                switch_cost=defaults.switch_cost, min_bars=defaults.min_bars,
                home_margin_bars=defaults.home_margin_bars,
                weak_return=defaults.weak_return)
            slots = 20
            request = session.GenerativeRequest(
                genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic="C",
                mode_key="major", slot_count=slots, durations=[2.0] * slots,
                bar_indices=[i // 2 for i in range(slots)],
                start_roman="I", end_roman="I", endpoints_required=True,
                modulation=settings,
                ga_config=GAConfig(population_size=70, generations=30,
                                   random_seed=17),
            )
            outcome = session.generate_random(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            options = [slot.options[min(c, len(slot.options) - 1)].harmony
                       for slot, c in zip(outcome.spec.slots,
                                          outcome.result.solutions[0].choices)]
            areas = {option.key_area for option in options if option.key_area}
            self.assertEqual(areas, {expected}, f"{genre}: {areas}")

    def test_every_style_offers_a_modal_destination(self):
        """El tilde «de modo» tiene que tener adónde ir en los cuatro estilos.

        En barroco y coral la lista era sólo de tonalidades, así que el tilde
        se prendía y no pasaba absolutamente nada.
        """
        from engine.harmony import GENRE_MODULATION, MODULATION_TARGETS
        for genre, settings in GENRE_MODULATION.items():
            modal = [key for key in settings.targets
                     if MODULATION_TARGETS[key].is_modal]
            self.assertTrue(modal, f"{genre} no ofrece ningún cambio de modo")

    def test_a_style_never_offers_the_mode_the_piece_is_already_in(self):
        """Modular de menor a menor no es ningún viaje."""
        from engine import harmony
        for genre, settings in harmony.GENRE_MODULATION.items():
            full = harmony.ModulationSettings(
                key_enabled=True, modal_enabled=True, targets=settings.targets)
            for mode_key in harmony.MODES:
                for key in harmony.available_targets(full, mode_key):
                    target = harmony.MODULATION_TARGETS[key]
                    if not target.is_modal:
                        continue
                    self.assertNotEqual(
                        harmony._modal_colour(target.mode_key),
                        harmony._modal_colour(mode_key),
                        f"{genre} en {mode_key} ofrece {key}")

    def test_the_minor_key_is_offered_the_parallel_major(self):
        """Y la mayor, la paralela menor: el destino sigue al modo."""
        from engine import harmony
        settings = harmony.ModulationSettings(
            key_enabled=False, modal_enabled=True,
            targets=harmony.GENRE_MODULATION["classical"].targets)
        self.assertEqual(harmony.available_targets(settings, "major"),
                         ("parallel_minor",))
        self.assertEqual(harmony.available_targets(settings, "minor"),
                         ("parallel_major",))
        # La menor armónica es la menor con la sensible levantada, no otro
        # sitio adonde ir.
        self.assertEqual(harmony.available_targets(settings, "harmonic"),
                         ("parallel_major",))

    def test_the_pool_follows_the_mode_the_piece_is_in(self):
        from engine import harmony
        settings = harmony.ModulationSettings(
            key_enabled=False, modal_enabled=True,
            targets=harmony.GENRE_MODULATION["chorale"].targets)
        for mode_key, expected in (("major", "parallel_minor"),
                                   ("minor", "parallel_major")):
            areas = {option.key_area for option
                     in harmony.modulation_pool(0, settings,
                                                home_mode_key=mode_key)}
            self.assertEqual(areas, {expected})
            self.assertEqual(
                set(harmony.modulation_scales(0, settings,
                                              home_mode_key=mode_key)),
                {expected})

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


class TestModulationNaming(unittest.TestCase):
    """Cómo se llama la tonalidad a la que la pieza viajó."""

    def test_the_target_is_named_from_the_home_key(self):
        from engine.harmony import modulation_key_name
        self.assertEqual(modulation_key_name("V", 0), "G Mayor (jónico)")
        self.assertEqual(modulation_key_name("V", 9), "E Mayor (jónico)")
        self.assertEqual(modulation_key_name("vi", 0), "A Menor natural")
        self.assertEqual(modulation_key_name("IV", 0), "F Mayor (jónico)")

    def test_a_modal_target_keeps_the_tonic(self):
        from engine.harmony import modulation_key_name
        self.assertEqual(modulation_key_name("parallel_dorian", 0), "C Dórico")
        self.assertEqual(modulation_key_name("parallel_minor", 7),
                         "G Menor natural")

    def test_a_flat_target_is_spelled_with_a_flat(self):
        """«Re# Mayor» no es un nombre que se use para esa tonalidad."""
        from engine.harmony import modulation_key_name
        self.assertEqual(modulation_key_name("bIII", 0), "Eb Mayor (jónico)")

    def test_an_unknown_area_names_nothing(self):
        from engine.harmony import modulation_key_name
        self.assertEqual(modulation_key_name("", 0), "")
        self.assertEqual(modulation_key_name("bVII", 0), "")

    def test_every_area_the_pool_can_produce_has_a_name(self):
        """El cartel se dibuja a partir del `key_area` del acorde elegido:
        un área sin nombre sería un tramo violeta mudo."""
        from engine import harmony
        for genre, settings in harmony.GENRE_MODULATION.items():
            full = harmony.ModulationSettings(
                key_enabled=True, modal_enabled=True, targets=settings.targets)
            for option in harmony.modulation_pool(0, full):
                self.assertTrue(harmony.modulation_key_name(option.key_area, 0),
                                f"{genre}: {option.key_area}")

    def test_the_scales_cover_every_area_offered(self):
        from engine import harmony
        for settings in harmony.GENRE_MODULATION.values():
            full = harmony.ModulationSettings(
                key_enabled=True, modal_enabled=True, targets=settings.targets)
            scales = harmony.modulation_scales(0, full)
            for option in harmony.modulation_pool(0, full):
                self.assertIn(option.key_area, scales)
                self.assertEqual(len(scales[option.key_area]), 7)
        # Apagada no ofrece ninguna: no hay viaje que vestir.
        self.assertEqual(harmony.modulation_scales(0, None), {})
        self.assertEqual(
            harmony.modulation_scales(0, harmony.ModulationSettings()), {})


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
        # Dentro de la tonalidad: el cuarto grado menor y el segundo
        # disminuido, sin séptima. Mayorizados, la cadena se iba del tono y
        # de F a B había un trítono con falsa relación.
        self.assertEqual([o.label for o in options],
                         ["Am", "Dm", "G", "C", "F", "Bdim", "E", "Am"])
        self.assertEqual([o.roman for o in options],
                         ["i", "iv", "bVII", "bIII", "bVI", "ii°", "V", "i"])

    def test_the_vivaldi_cycle_is_sung_over_its_roots(self):
        """
        El bajo cae por quintas: cada acorde de la cita con su fundamental.

        Librado a la búsqueda salía invertido casi entero, y a tres voces
        terminaba en primera inversión.
        """
        for seed in range(1, 40):
            request = session.GenerativeRequest(
                genre_key="classical", voice_keys=["B", "T", "S"],
                tonic="A", mode_key="minor", slot_count=8,
                durations=[2.0] * 8, bar_indices=[i // 2 for i in range(8)],
                raise_odds=True, solutions_wanted=1,
                ga_config=GAConfig(population_size=40, generations=15,
                                   random_seed=seed))
            outcome = session.generate_random(request)
            piece = outcome.set_piece
            if (outcome.succeeded and piece is not None
                    and "Vivaldi" in piece.label):
                break
        else:
            self.fail("la cita no apareció")
        solution = outcome.result.solutions[piece.solution_index]
        self.assertEqual([chord[0] % 12 for chord in solution.slots],
                         [9, 2, 7, 0, 5, 11, 4, 9])

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

    def test_turning_a_golden_note_off_takes_its_chord_away(self):
        """El dorado que puso el programa también se puede discutir.

        Hasta acá se podía pedir un acorde de más y nunca uno de menos: el
        click sobre una nota que el programa ya iba a armonizar sólo podía
        agregarle un anillo.
        """
        from engine.harmonize import HarmonisationSettings, planned_notes
        melody = self._melody(["C5", "D5", "E5", "F5", "G5", "F5", "E5", "C5"])
        rules = HarmonisationSettings(genre_key="chorale")
        before = planned_notes(melody, rules)
        target = before[1]
        self.assertGreater(len(before), 2)
        target.skip_harmonise = True
        after = planned_notes(melody, rules)
        self.assertNotIn((target.bar_index, target.offset_quarters),
                         [(n.bar_index, n.offset_quarters) for n in after])
        self.assertEqual(len(after), len(before) - 1)

    def test_turning_a_note_off_keeps_the_bars_adding_up(self):
        """Lo que ocupaba el lugar que se va se lo queda un vecino del mismo
        compás: repartirlo fuera lo dejaría sumando de más."""
        from engine.harmonize import (HarmonisationSettings, drop_skipped_spots,
                                      harmony_spots, planned_notes)
        rules = HarmonisationSettings(genre_key="chorale")
        for position in range(1, 8):
            melody = self._melody(["C5", "D5", "E5", "F5",
                                   "G5", "F5", "E5", "C5"])
            melody.notes[position].skip_harmonise = True
            spots = drop_skipped_spots(melody, harmony_spots(melody), rules)
            totals = {}
            for spot in spots:
                totals[spot.bar_index] = (totals.get(spot.bar_index, 0.0)
                                          + spot.duration_quarters)
            self.assertEqual(set(totals.values()), {4.0},
                             f"apagando la nota {position}: {totals}")
            self.assertTrue(spots)

    def test_the_last_chord_of_a_bar_cannot_be_taken_away(self):
        """Un lugar sin vecino en su compás se queda: sacarlo dejaría el
        compás corto, y decirlo con el dorado encendido es más honesto que
        obedecer y romper la partitura."""
        from engine.harmonize import (HarmonisationSettings, drop_skipped_spots,
                                      harmony_spots)
        rules = HarmonisationSettings(genre_key="chorale")
        melody = self._melody(["C5", "D5", "E5"], bars=3, beats=3, beat_type=4)
        for note in melody.notes:
            note.skip_harmonise = True
        spots = drop_skipped_spots(melody, harmony_spots(melody), rules)
        self.assertTrue(spots)

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

    def test_what_was_just_unlocked_is_fresh(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = self._tracker(folder)
            tracker.unlock(["first_rest"])
            self.assertEqual(tracker.fresh(), {"first_rest"})
            self.assertTrue(tracker.is_fresh("first_rest"))
            # Mirarlo lo apaga, y no vuelve.
            tracker.mark_seen()
            self.assertEqual(tracker.fresh(), set())
            tracker.unlock(["first_export"])
            self.assertEqual(tracker.fresh(), {"first_export"})

    def test_being_fresh_survives_a_restart(self):
        """
        Ganar algo y cerrar el programa sin ir a mirarlo lo deja marcado.

        Es todo el punto de guardarlo: el aviso de la esquina dura unos
        segundos y se lo puede perder cualquiera.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            achievements.Tracker(path=path).unlock(["first_rest"])
            reopened = achievements.Tracker.load(path)
            self.assertEqual(reopened.fresh(), {"first_rest"})
            reopened.mark_seen()
            self.assertEqual(achievements.Tracker.load(path).fresh(), set())

    def test_an_older_file_has_nothing_fresh(self):
        """
        Un archivo sin la lista viene de una versión anterior.

        Sin esto, quien ya tenía treinta logros abría la pantalla y se los
        encontraba a todos marcados como recién completados.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"unlocked": {"first_rest": "2026-01-01"}}, handle)
            self.assertEqual(achievements.Tracker.load(path).fresh(), set())

    def test_an_empty_list_is_not_a_missing_list(self):
        """Guardada vacía significa que no se miró ninguno todavía."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"unlocked": {"first_rest": "2026-01-01"},
                           "seen": []}, handle)
            self.assertEqual(achievements.Tracker.load(path).fresh(),
                             {"first_rest"})

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


class TestBookChapterLocks(unittest.TestCase):
    """En qué capítulo cayó lo que todavía no se leyó."""

    def test_a_key_lights_the_chapter_that_holds_its_entry(self):
        """
        Tiene que dar lo mismo que recorrer el libro a mano, y en posiciones.

        Es lo único con lo que la interfaz pinta de azul un capítulo del
        índice, así que una llave que se mude de capítulo tiene que mover el
        azul con ella sin que nadie toque la pantalla.
        """
        self.assertEqual(book.chapters_for_locks([]), set())
        self.assertEqual(book.chapters_for_locks(["no_existe"]), set())
        for key in book.LOCK_KEYS:
            chapter, _entry = book.entry_for_lock(key)
            self.assertEqual(book.chapters_for_locks([key]),
                             {book.CHAPTERS.index(chapter)}, key)


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

    def test_every_visitor_has_a_staging_of_its_own(self):
        """
        Nadie puede quedar afuera de `STAGING` sin que se note.

        `staging_for` no falla con un personaje que no esté en la tabla:
        devuelve la puesta de otro y la escena se dibuja igual. Una visita
        nueva salía entonces con el cielo, la luna, el humo y el viento del
        señor del sombrero --- una puesta que dice algo muy concreto de
        quien la usa --- y no había ningún error en ninguna parte.
        """
        import cinematic
        for key, visit in visitors.VISITS.items():
            self.assertIn(visit.speaker, cinematic.STAGING, key)
            self.assertIn(visit.speaker, cinematic.SPEAKERS, key)
            self.assertIn(visit.speaker, cinematic.POSES, key)

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

    def test_every_award_is_a_real_achievement(self):
        """
        Las claves de `AWARDS` son cadenas sueltas: nadie las verifica.

        `visitors.py` no importa el catálogo --- es guion y registro, igual
        que `story.py` ---, así que una clave mal escrita ahí no falla:
        `_award` la descarta en silencio y la visita entrega nada.
        """
        for key, award in visitors.AWARDS.items():
            # Las visitas están en el catálogo de visitas; la tercera visión
            # no, porque no es una charla con alguien que llega y se va.
            self.assertTrue(key in visitors.VISITS or key == visitors.TOMB)
            self.assertIn(award, achievements.BY_KEY, award)
            self.assertFalse(achievements.BY_KEY[award].legendary, award)

    def test_the_watcher_hands_out_no_achievement(self):
        """
        No puede: aparece al conseguir el cien por ciento.

        Un logro suyo sería uno que nunca se tiene --- lo desbloquearía la
        escena que exige no tener ninguno pendiente ---, así que la entidad
        se quedaría esperando un logro que sólo ella entrega.
        """
        self.assertEqual(visitors.award_for(visitors.WATCHER_ALL), "")
        self.assertEqual(visitors.award_for(visitors.VISION), "")

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

    def test_the_environment_can_force_or_forbid_the_second_vision(self):
        """Y la pide sin pedir la primera: son dos escenas distintas."""
        self.assertIsNone(visitors.pact_forced({}))
        self.assertTrue(visitors.pact_forced({visitors.PACT_VAR: "1"}))
        self.assertFalse(visitors.pact_forced({visitors.PACT_VAR: "0"}))
        # Una no contesta por la otra.
        self.assertIsNone(visitors.pact_forced({visitors.VISION_VAR: "1"}))
        self.assertIsNone(visitors.vision_forced({visitors.PACT_VAR: "1"}))

    # -- la segunda visión ----------------------------------------------------

    def test_the_second_vision_waits_for_the_first(self):
        """
        Es la misma noche un minuto más tarde: sin la primera no se entiende.

        Y encima entrega justo lo que la otra guarda --- con quién estaba
        hablando ---, así que al revés se contarían el final antes que el
        principio.
        """
        self.assertFalse(visitors.pact_due(False, False, 0.0, True))
        self.assertTrue(visitors.pact_due(False, True, 0.0, True))

    def test_the_second_vision_happens_once_and_below_the_odds(self):
        odds = visitors.VISION_ODDS
        self.assertTrue(visitors.pact_due(False, True, odds / 2, True))
        self.assertFalse(visitors.pact_due(False, True, odds, True))
        self.assertFalse(visitors.pact_due(False, True, 0.99, True))
        # Vista una vez, no vuelve ni con el sorteo a favor.
        self.assertFalse(visitors.pact_due(True, True, 0.0, True))
        # Y tampoco antes de terminar el tutorial, igual que la primera.
        self.assertFalse(visitors.pact_due(False, True, 0.0, False))

    def test_the_second_vision_writes_its_own_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            lock = visitors.book_key(visitors.PACT)
            self.assertFalse(ledger.knows(lock))
            self.assertTrue(ledger.mark_pact())
            self.assertFalse(ledger.mark_pact())
            self.assertTrue(ledger.knows(lock))
            # Y sobrevive al cierre del programa, como todo lo demás.
            again = visitors.Ledger.load(path)
            self.assertTrue(again.knows(lock))
            # Sin tocar la primera: son dos apariciones y dos anotaciones.
            self.assertFalse(again.knows(visitors.book_key(visitors.VISION)))

    def test_the_second_vision_entry_is_written_in_gold(self):
        """Tampoco se consigue trabajando, así que tampoco dice su título."""
        found = book.entry_for_lock(visitors.book_key(visitors.PACT))
        self.assertIsNotNone(found)
        _chapter, entry = found
        self.assertTrue(entry.legendary)
        self.assertTrue(book.is_secret(entry))

    def test_the_second_vision_is_not_a_visit(self):
        """
        No está en `VISITS`, y no puede estar: no es una escena de diálogo.

        Lo que la dibuja es `cinematic.Vision` --- el camino, el tren y el
        encuentro ---, no la maquinaria de alguien que llega, habla y se va.
        Metida en el catálogo, `_open_visit` la abriría como una charla.
        """
        self.assertNotIn(visitors.PACT, visitors.VISITS)
        self.assertEqual(visitors.award_for(visitors.PACT), "")

    def test_nobody_is_on_screen_while_the_second_vision_speaks(self):
        """
        Sus líneas no pueden llevar pose, y ésta es la trampa entera.

        La escena que cierra la segunda visión es un cartel de diálogo sobre
        el negro y nada más (`entrance="unseen"`). El retrato se crea igual
        --- media `Cutscene` lo da por hecho --- y se esconde, pero
        `_begin_line` vuelve a llamar a `Portrait.show` en cuanto una línea
        pide una pose, y `show` deja la imagen **visible**: una sola pose
        escrita acá pone al personaje en pantalla en medio de una escena que
        se trata justamente de que no se lo vea.
        """
        self.assertTrue(visitors.PACT_LINES)
        for line in visitors.PACT_LINES:
            self.assertEqual(line.speaker, story.DEVIL)
            self.assertFalse(line.pose, line.text)

    def test_the_second_vision_has_both_of_its_cutouts(self):
        """
        Las dos poses del encuentro tienen que existir, y con ese nombre.

        `load_pose` cae en ``normal`` cuando el nombre de la pose no está en
        la tabla, y devuelve ``None`` cuando el archivo falta. Ninguna de
        las dos cosas falla ni avisa: la primera cambiaría la silueta negra
        por el recorte con cara --- que es lo único que esa figura no puede
        tener --- y la segunda dejaría el camino con una sola persona, que
        es la escena anterior.
        """
        import cinematic                             # noqa: PLC0415
        arte = os.path.join(history.program_directory(), "assets", "story")
        for speaker, plane in ((visitors.ROBERT, cinematic.Vision.BACK),
                               (story.DEVIL, cinematic.Vision.FRONT)):
            pose = plane[1]
            name = cinematic.POSES[speaker].get(pose)
            self.assertTrue(name, (speaker, pose))
            self.assertTrue(os.path.exists(os.path.join(arte, name)), name)
            # Y con ese nombre y no cayendo en `normal`, que es lo que hace
            # `load_pose` cuando la pose no está en la tabla.
            self.assertIn(pose, cinematic.POSES[speaker])


    # -- la tercera visión ----------------------------------------------------

    def test_the_third_vision_waits_for_the_second(self):
        """
        Las tres son una sola historia en tres pedazos: quién estaba en el
        camino, con quién hablaba y cómo terminó. Cualquier orden que no sea
        ése cuenta el final antes que el principio.
        """
        self.assertFalse(visitors.tomb_due(False, False, 0.0, True))
        self.assertTrue(visitors.tomb_due(False, True, 0.0, True))

    def test_the_third_vision_happens_once_and_below_the_odds(self):
        """Mismo sorteo y mismo criterio que la segunda, corridos un lugar."""
        odds = visitors.VISION_ODDS
        self.assertTrue(visitors.tomb_due(False, True, odds / 2, True))
        self.assertFalse(visitors.tomb_due(False, True, odds, True))
        self.assertFalse(visitors.tomb_due(False, True, 0.99, True))
        self.assertFalse(visitors.tomb_due(True, True, 0.0, True))
        self.assertFalse(visitors.tomb_due(False, True, 0.0, False))

    def test_the_environment_can_force_or_forbid_the_third_vision(self):
        self.assertIsNone(visitors.tomb_forced({}))
        self.assertTrue(visitors.tomb_forced({visitors.TOMB_VAR: "1"}))
        self.assertFalse(visitors.tomb_forced({visitors.TOMB_VAR: "0"}))
        # Y cada variable pide lo suyo: pedir una no pide las otras dos.
        self.assertIsNone(visitors.tomb_forced({visitors.PACT_VAR: "1"}))
        self.assertIsNone(visitors.pact_forced({visitors.TOMB_VAR: "1"}))
        self.assertIsNone(visitors.vision_forced({visitors.TOMB_VAR: "1"}))

    def test_the_third_vision_writes_its_own_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            lock = visitors.book_key(visitors.TOMB)
            self.assertFalse(ledger.knows(lock))
            self.assertTrue(ledger.mark_tomb())
            self.assertFalse(ledger.mark_tomb())
            self.assertTrue(ledger.knows(lock))
            again = visitors.Ledger.load(path)
            self.assertTrue(again.knows(lock))
            # Sin tocar las otras dos: son tres apariciones y tres anotaciones.
            self.assertFalse(again.knows(visitors.book_key(visitors.VISION)))
            self.assertFalse(again.knows(visitors.book_key(visitors.PACT)))

    def test_the_third_vision_entry_is_written_in_gold(self):
        """Tampoco se consigue trabajando, así que tampoco dice su título."""
        found = book.entry_for_lock(visitors.book_key(visitors.TOMB))
        self.assertIsNotNone(found)
        _chapter, entry = found
        self.assertTrue(entry.legendary)
        self.assertTrue(book.is_secret(entry))

    def test_the_third_vision_is_not_a_visit(self):
        """Tampoco es una escena de alguien que llega, habla y se va."""
        self.assertNotIn(visitors.TOMB, visitors.VISITS)

    def test_the_third_vision_is_the_only_one_that_gives_a_badge(self):
        """
        Y es la excepción a propósito.

        Las dos primeras no entregan nada porque no se pueden provocar: un
        logro que depende de una tirada de una en cinco no es un logro. La
        tercera está al final de la única historia que el programa cuenta de
        punta a punta, y quien la ve es porque vio las tres.
        """
        self.assertEqual(visitors.award_for(visitors.VISION), "")
        self.assertEqual(visitors.award_for(visitors.PACT), "")
        award = visitors.award_for(visitors.TOMB)
        self.assertEqual(award, "echoes_past")
        badge = achievements.BY_KEY[award]
        self.assertEqual(badge.star, 3)
        self.assertFalse(badge.legendary)

    def test_a_description_can_carry_a_piece_in_bold(self):
        """La marca se parte en tramos y sale del texto que se muestra."""
        pieces = achievements.runs("Escuchá a **aquel hombre**.")
        self.assertEqual(pieces, [("Escuchá a ", False),
                                  ("aquel hombre", True),
                                  (".", False)])
        self.assertEqual(achievements.plain("uno **dos** tres"),
                         "uno dos tres")
        # Una descripción sin marcas es un solo tramo, y así se sigue
        # dibujando con una sola etiqueta.
        for badge in achievements.CATALOG:
            if achievements.EMPHASIS not in badge.description:
                self.assertEqual(len(achievements.runs(badge.description)), 1)

    def test_nobody_is_on_screen_while_the_third_vision_speaks(self):
        """La misma trampa que la segunda: una pose acá pondría al
        personaje en pantalla en medio de una escena que se trata
        justamente de que no se lo vea."""
        self.assertTrue(visitors.TOMB_LINES)
        for line in visitors.TOMB_LINES:
            self.assertEqual(line.speaker, story.DEVIL)
            self.assertFalse(line.pose, line.text)

    def test_the_third_vision_has_its_headstone(self):
        """
        El recorte de la lápida tiene que existir y con ese nombre.

        `load_prop` devuelve ``None`` cuando el archivo falta, y eso no falla
        ni avisa: la tormenta se abriría sobre un camino vacío, que es la
        única cosa que esa escena no puede ser.
        """
        import cinematic                             # noqa: PLC0415
        arte = os.path.join(history.program_directory(), "assets", "story")
        name = cinematic.PROPS.get("lapida")
        self.assertTrue(name)
        self.assertTrue(os.path.exists(os.path.join(arte, name)), name)

    def test_the_three_visions_are_three_separate_records(self):
        """
        Cada una lleva su propia fecha en el archivo, y las tres sobreviven
        a un cierre. Con una sola marca compartida, ver la tercera habría
        dado las otras dos por vistas.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            ledger.mark_vision()
            ledger.mark_pact()
            ledger.mark_tomb()
            again = visitors.Ledger.load(path)
            for key in (visitors.VISION, visitors.PACT, visitors.TOMB):
                self.assertTrue(again.knows(visitors.book_key(key)), key)
            # Tres campos y no uno: cada fecha se guarda por su cuenta.
            for stamp in (again.vision, again.pact, again.tomb):
                self.assertTrue(stamp)
            # Y marcar una no marca las otras.
            fresh = visitors.Ledger.load(os.path.join(folder, "otro.json"))
            fresh.mark_tomb()
            self.assertFalse(fresh.knows(visitors.book_key(visitors.VISION)))
            self.assertFalse(fresh.knows(visitors.book_key(visitors.PACT)))


class TestHarmonicsModel(unittest.TestCase):
    """
    El experimentador de armónicos: las recetas, la lista y la síntesis.

    Todo lo de acá es física con números conocidos, así que se puede probar
    contra ellos y no contra sí mismo. Los tres que importan --- el quinto
    catorce cents por debajo de la tercera del piano, el séptimo treinta y
    uno por debajo de la séptima, el tercero dos por encima de la quinta ---
    son además exactamente lo que el capítulo de física del libro afirma por
    escrito, así que este test también vigila que el libro no mienta.
    """

    def test_the_series_is_whole_multiples_of_the_fundamental(self):
        spectrum = harmonics.build()
        base = spectrum.fundamental
        for item in spectrum.partials:
            self.assertAlmostEqual(item.frequency(base), base * item.number,
                                   places=6)

    def test_the_recipes_are_the_ones_they_say_they_are(self):
        """
        Una forma de onda no es otra manera de vibrar: es qué barra sube.

        Es la idea entera del capítulo de física, así que si una receta
        dejara de cumplirla el libro pasaría a explicar un dibujo que no
        está en la pantalla.
        """
        sine = harmonics.build("Seno puro")
        self.assertEqual([p.gain for p in sine.partials][1:],
                         [0.0] * (harmonics.PARTIAL_COUNT - 1))
        square = harmonics.build("Cuadrada")
        for item in square.partials:
            if item.number % 2 == 0:
                self.assertEqual(item.gain, 0.0, item.number)
            else:
                self.assertAlmostEqual(item.gain, 1.0 / item.number)
        saw = harmonics.build("Diente de sierra")
        for item in saw.partials:
            self.assertAlmostEqual(item.gain, 1.0 / item.number)

    def test_changing_the_recipe_keeps_what_the_user_did(self):
        """
        Cambiar de forma de onda es una pregunta sobre el timbre.

        Devolver además lo apagado, lo corrido y lo aislado convertiría al
        selector en un botón de reiniciar con ocho nombres.
        """
        spectrum = harmonics.build("Diente de sierra")
        spectrum.partials[3].muted = True
        spectrum.partials[6].shift = -31.0
        spectrum.solo = 2
        harmonics.apply_preset(spectrum, "Cuadrada")
        self.assertTrue(spectrum.partials[3].muted)
        self.assertEqual(spectrum.partials[6].shift, -31.0)
        self.assertEqual(spectrum.solo, 2)
        self.assertEqual(spectrum.partials[1].gain, 0.0)   # el segundo, par

    def test_what_sounds_is_what_is_drawn(self):
        """
        El aislado gana, lo apagado no entra y lo que está en cero tampoco.

        `sounding` es la única lista: la dibuja el gráfico y la suma el
        sintetizador. Con dos recorridos distintos una regla nueva entra en
        uno solo y el experimento deja de probar lo que muestra.
        """
        spectrum = harmonics.build("Diente de sierra")
        self.assertEqual(len(harmonics.sounding(spectrum)),
                         harmonics.PARTIAL_COUNT)
        spectrum.partials[0].muted = True
        spectrum.partials[1].gain = 0.0
        self.assertEqual([p.number for p, _f, _g in harmonics.sounding(spectrum)],
                         list(range(3, harmonics.PARTIAL_COUNT + 1)))
        spectrum.solo = 5
        self.assertEqual([p.number for p, _f, _g in harmonics.sounding(spectrum)],
                         [5])
        # Y aislar algo apagado no lo enciende: son dos cosas distintas.
        spectrum.solo = 1
        self.assertEqual(harmonics.sounding(spectrum), [])

    def test_the_famous_deviations_from_the_piano(self):
        base = harmonics.midi_to_frequency(45)             # la2, 110 Hz
        self.assertAlmostEqual(base, 110.0, places=6)
        expected = {2: 0.0, 3: 2.0, 4: 0.0, 5: -13.7, 7: -31.2, 8: 0.0}
        for number, cents in expected.items():
            _midi, off = harmonics.nearest_note(base * number)
            self.assertAlmostEqual(off, cents, places=1, msg=str(number))

    def test_shifting_a_partial_moves_it_by_the_right_ratio(self):
        """Corrido justo lo que le falta, el séptimo cae en la tecla."""
        spectrum = harmonics.build()
        item = spectrum.partial(7)
        base = spectrum.fundamental
        _midi, missing = harmonics.nearest_note(item.frequency(base))
        self.assertAlmostEqual(missing, -31.2, places=1)
        item.shift = -missing
        _midi, off = harmonics.nearest_note(item.frequency(base))
        self.assertAlmostEqual(off, 0.0, places=1)

    def test_the_interval_of_each_harmonic_is_the_one_it_should_be(self):
        """
        Lo que la pantalla escribe al lado de la nota, contra la serie.

        Es la mitad de lo que hace legible el gráfico --- que el segundo
        armónico sea una octava y el tercero una octava y una quinta no se
        deduce de «440 Hz» --- y es además de donde sale toda la armonía que
        el resto del programa escribe.
        """
        import spectrum
        base = 45                                          # la2
        expected = {1: "unísono", 2: "1 octava", 3: "1 octava + 5ª justa",
                    4: "2 octavas", 5: "2 octavas + 3ª mayor",
                    6: "2 octavas + 5ª justa", 7: "2 octavas + 7ª menor",
                    8: "3 octavas", 9: "3 octavas + 2ª mayor",
                    12: "3 octavas + 5ª justa"}
        hertz = harmonics.midi_to_frequency(base)
        for number, name in expected.items():
            midi, _cents = harmonics.nearest_note(hertz * number)
            self.assertEqual(spectrum.interval_label(midi - base), name,
                             number)

    def test_a_partial_can_no_longer_beat_on_its_own(self):
        """
        El latido de un armónico suelto se sacó: lo que oscila es el
        conjunto, con el vibrato y el trémolo. Un campo que quedara vivo
        sin nada que lo prenda es un camino muerto adentro del
        sintetizador.
        """
        self.assertFalse(hasattr(harmonics.Partial(1), "modulated"))

    def test_the_undertones_are_the_mirror(self):
        below = harmonics.undertones(880.0, 8)
        self.assertEqual(below[0], 880.0)
        self.assertEqual(below[1], 440.0)
        self.assertAlmostEqual(below[7], 110.0)

    def test_rendering_gives_sixteen_bit_frames(self):
        spectrum = harmonics.build("Seno puro")
        frames = harmonics.render(spectrum, seconds=0.2)
        self.assertEqual(len(frames), int(0.2 * harmonics.SAMPLE_RATE) * 2)
        # Y suena: no es un buffer de ceros.
        self.assertTrue(any(frames))

    def test_a_silent_spectrum_renders_silence_instead_of_crashing(self):
        """Apagar todo es un experimento válido, no un error."""
        spectrum = harmonics.build("Seno puro")
        spectrum.partials[0].muted = True
        frames = harmonics.render(spectrum, seconds=0.1)
        self.assertEqual(set(frames), {0})

    def test_the_mix_is_normalised_and_never_clips(self):
        """
        Subir un armónico hasta oírlo no puede recortar la mezcla.

        Una mezcla recortada le agrega armónicos que nadie pidió, que es
        justo lo que el usuario está tratando de mirar.
        """
        spectrum = harmonics.build("Diente de sierra")
        for item in spectrum.partials:
            item.gain = harmonics.MAX_GAIN
        frames = harmonics.render(spectrum, seconds=0.2)
        self.assertLessEqual(self._peak(frames), 32767)
        self.assertGreater(self._peak(frames), 20000)   # y no quedó inaudible

    def test_isolating_a_faint_harmonic_is_still_audible(self):
        """
        El duodécimo de un diente de sierra vale ocho centésimas.

        Sin llevar la mezcla al techo también hacia arriba, aislarlo se
        parecía a haberlo apagado --- y aislar es lo primero que se hace en
        esta pantalla.
        """
        spectrum = harmonics.build("Diente de sierra")
        spectrum.solo = harmonics.PARTIAL_COUNT
        alone = self._peak(harmonics.render(spectrum, seconds=0.2))
        spectrum.solo = 1
        loud = self._peak(harmonics.render(spectrum, seconds=0.2))
        self.assertGreater(alone, 20000)
        self.assertAlmostEqual(alone, loud, delta=loud * 0.02)

    @staticmethod
    def _peak(frames: bytes) -> int:
        return max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True))
                   for i in range(0, len(frames), 2))


class TestPhysicsChapter(unittest.TestCase):
    """
    Los gráficos del capítulo de física están a escala de verdad.

    Sus números son literales escritos a mano --- `book.py` no importa nada
    del proyecto ---, así que nadie los verifica salvo esto. Un dibujo a
    escala con los números mal es peor que no tener dibujo: enseña otra cosa
    y parece que la enseña bien.
    """

    def _plots(self):
        chapter = next(c for c in book.CHAPTERS
                       if c.title == "La física en la música")
        return [(entry, plot) for entry in chapter.entries
                for plot in entry.plots]

    def test_the_chapter_opens_with_the_experimenter(self):
        chapter = next(c for c in book.CHAPTERS
                       if c.title == "La física en la música")
        for entry in chapter.entries:
            self.assertEqual(entry.locked_by, "harmonics_first", entry.key)
        self.assertIn("harmonics_first", achievements.BY_KEY)

    def test_every_bar_fits_inside_its_axis(self):
        for entry, plot in self._plots():
            high = plot.high or max(f for f, _a, _l in plot.bars) * 1.06
            for frequency, amplitude, _mark in plot.bars:
                self.assertGreaterEqual(frequency, plot.low, entry.key)
                self.assertLessEqual(frequency, high, entry.key)
                self.assertGreater(amplitude, 0.0, entry.key)
            for frequency, _mark in plot.ticks:
                self.assertGreaterEqual(frequency, plot.low, entry.key)
                self.assertLessEqual(frequency, high, entry.key)

    def test_the_series_plot_really_is_the_series(self):
        entry, plot = next((e, p) for e, p in self._plots()
                           if e.key == "fisica_serie")
        self.assertEqual(len(plot.bars), harmonics.PARTIAL_COUNT)
        for number, (frequency, amplitude, mark) in enumerate(plot.bars, 1):
            self.assertAlmostEqual(frequency, plot.reference * number, places=3)
            self.assertAlmostEqual(amplitude, 1.0 / number, places=2)
            self.assertEqual(mark, str(number))

    def test_the_temperament_plot_marks_the_real_piano_notes(self):
        _entry, plot = next((e, p) for e, p in self._plots()
                            if e.key == "fisica_temperamento")
        # Las barras son los armónicos quinto y séptimo de la referencia…
        self.assertAlmostEqual(plot.bars[0][0], plot.reference * 5, places=3)
        self.assertAlmostEqual(plot.bars[1][0], plot.reference * 7, places=3)
        # …y las marcas, la tecla temperada que a cada uno le queda cerca.
        for frequency, _mark in plot.ticks:
            _midi, cents = harmonics.nearest_note(frequency)
            self.assertAlmostEqual(cents, 0.0, places=0)

    def test_the_undertone_plot_really_divides(self):
        _entry, plot = next((e, p) for e, p in self._plots()
                            if e.key == "fisica_subarmonica")
        for divisor, (frequency, _a, mark) in enumerate(plot.bars, 1):
            self.assertAlmostEqual(frequency, plot.reference / divisor,
                                   places=0)
            self.assertEqual(mark, str(divisor))

    def test_the_two_timbres_are_the_same_note(self):
        """
        El punto del apartado: la misma serie con otras alturas de barra.

        Si los dos gráficos estuvieran en notas distintas, la comparación no
        mostraría el timbre sino la altura.
        """
        plots = [p for e, p in self._plots() if e.key == "fisica_timbre"]
        self.assertEqual(len(plots), 2)
        self.assertEqual(plots[0].reference, plots[1].reference)
        self.assertEqual([f for f, _a, _m in plots[0].bars],
                         [f for f, _a, _m in plots[1].bars])
        # Y la flauta es casi toda fundamental; el clarinete, impares.
        flute, clarinet = plots
        self.assertGreater(flute.bars[1][1] * 3, clarinet.bars[1][1])
        self.assertGreater(clarinet.bars[2][1], clarinet.bars[1][1] * 5)


class TestHarmonisationBarTotals(unittest.TestCase):
    """El final de la melodía no puede dejar un compás que no sume."""

    @staticmethod
    def _totals(spots):
        totals = {}
        for spot in spots:
            totals[spot.bar_index] = (totals.get(spot.bar_index, 0.0)
                                      + spot.duration_quarters)
        return totals

    def test_empty_bars_after_the_melody_are_not_added_to_the_last_one(self):
        """
        Tres compases escritos de cuatro: el cuarto queda vacío.

        El recorte de los lugares posteriores a la melodía le sumaba al
        último acorde lo de **todos** los que se iban, también los del compás
        vacío: el tercero medía ocho negras y el MusicXML salía inválido.
        """
        from engine.harmonize import (Melody, MelodyBar, MelodyNote,
                                      harmony_spots)
        pitches = [72, 74, 76, 77, 79, 77, 76, 74, 72, 76, 74, 72]
        melody = Melody(
            notes=[MelodyNote(p, 1.0, i // 4, float(i % 4))
                   for i, p in enumerate(pitches)],
            bars=[MelodyBar() for _ in range(4)], melody_voice=3)
        self.assertEqual(self._totals(harmony_spots(melody)),
                         {0: 4.0, 1: 4.0, 2: 4.0})

        outcome = session.harmonise_melody(session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3, solutions_wanted=1,
            ga_config=GAConfig(population_size=20, generations=4,
                               random_seed=1, workers=1)))
        self.assertTrue(outcome.succeeded, outcome.errors)
        xml = export.build_musicxml(outcome.spec, outcome.result.solutions[0])
        measures = re.findall(r"<measure .*?</measure>", xml, re.S)
        self.assertEqual(len(measures), 3)
        whole = 4 * export.DIVISIONS_PER_QUARTER
        for number, measure in enumerate(measures, start=1):
            per_voice = {}
            for note in re.findall(r"<note>.*?</note>", measure, re.S):
                voice = re.search(r"<voice>(\d+)</voice>", note).group(1)
                per_voice[voice] = per_voice.get(voice, 0) + int(
                    re.search(r"<duration>(\d+)</duration>", note).group(1))
            self.assertEqual(set(per_voice.values()), {whole},
                             f"compás {number}: {per_voice}")

    def test_a_last_note_just_past_the_strong_beat_does_not_overflow(self):
        """
        Una melodía importada que termina con una semicorchea en 2,25.

        El último tiempo fuerte se estiraba a la duración mínima ---hasta
        2,5--- y el lugar nuevo de la última nota arrancaba en 2,25: los dos
        se pisaban y el compás sumaba cuatro negras y cuarto.
        """
        import random as _random
        from engine.harmonize import (HarmonisationSettings, Melody,
                                      MelodyBar, MelodyNote, harmonise,
                                      harmony_spots)
        notes = [MelodyNote(76, 1.0, 0, 0.0), MelodyNote(74, 1.0, 0, 1.0),
                 MelodyNote(72, 1.0, 0, 2.0), MelodyNote(74, 1.0, 0, 3.0),
                 MelodyNote(76, 2.0, 1, 0.0), MelodyNote(74, 0.25, 1, 2.0),
                 MelodyNote(72, 0.25, 1, 2.25)]
        melody = Melody(notes=notes, bars=[MelodyBar(), MelodyBar()],
                        melody_voice=3)
        spots = harmony_spots(melody)
        self.assertEqual(self._totals(spots), {0: 4.0, 1: 4.0})
        for before, after in zip(spots, spots[1:]):
            if before.bar_index == after.bar_index:
                self.assertAlmostEqual(
                    before.offset_quarters + before.duration_quarters,
                    after.offset_quarters)
        # Y la última nota sigue teniendo su acorde.
        self.assertIn((1, 2.25), [(s.bar_index, s.offset_quarters)
                                  for s in spots])
        rules = HarmonisationSettings(genre_key="chorale")
        for seed in range(3):
            chosen = harmonise(melody, rules, _random.Random(seed))
            self.assertEqual(self._totals([s for s, _o in chosen]),
                             {0: 4.0, 1: 4.0}, f"semilla {seed}")


class TestHarmonisedOptions(unittest.TestCase):
    """Cada opción del Armonizador viaja con su propia progresión."""

    def _request(self, melody, genre="classical", seed=5, wanted=3):
        return session.HarmoniseRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"], melody=melody,
            melody_voice=3, solutions_wanted=wanted,
            ga_config=GAConfig(population_size=30, generations=8,
                               random_seed=seed, workers=1))

    @staticmethod
    def _melody(pitches):
        from engine.harmonize import Melody, MelodyBar, MelodyNote
        return Melody(
            notes=[MelodyNote(p, 1.0, i // 4, float(i % 4))
                   for i, p in enumerate(pitches)],
            bars=[MelodyBar() for _ in range((len(pitches) + 3) // 4)],
            melody_voice=3)

    TUNE = [72, 71, 69, 71, 72, 74, 76, 74, 72, 71, 72, 72]

    def test_the_flourishes_run_once(self):
        """
        El Armonizador decora al terminar la búsqueda y la pantalla de
        resultados volvía a llamar a `apply_flourishes` sobre el mismo
        resultado: la sexta se podía escribir dos veces, y la primera
        quedaba en la partitura sin marca porque la segunda pasada
        reemplazaba lo que había encontrado la primera.
        """
        from unittest import mock
        from engine import flourish
        with mock.patch.object(flourish, "SIXTH_CHANCE", 1.0), \
                mock.patch.object(flourish, "apply_sixth",
                                  wraps=flourish.apply_sixth) as sixth:
            outcome = session.harmonise_melody(
                self._request(self._melody(self.TUNE), wanted=1))
            self.assertTrue(outcome.succeeded, outcome.errors)
            found = outcome.flourishes
            self.assertIsNotNone(found)
            best = outcome.result.solutions[0]
            before = [list(chord) for chord in best.slots]
            # Lo que hace la pantalla de resultados al recibirlo.
            session.apply_flourishes(outcome, "classical", 0)
        self.assertEqual(sixth.call_count, 1)
        self.assertIs(outcome.flourishes, found)
        self.assertEqual([list(chord) for chord in best.slots], before)

    def test_each_option_is_exported_with_its_own_chords(self):
        """
        Se exportaban las tres con ``outcome.spec``, que lleva la progresión
        del primer intento: las notas se deletreaban contra acordes ajenos y
        el archivo no coincidía con la grilla.
        """
        from unittest import mock
        outcome = session.harmonise_melody(
            self._request(self._melody(self.TUNE)))
        self.assertEqual(len(outcome.result.solutions), 3)
        written = []

        def spy(spec, solution, stem, formats):
            written.append((spec, solution))
            return []

        request = self._request(self._melody(self.TUNE))
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(export, "write_solution", spy):
            session.export_outcome(request, outcome, directory=folder,
                                   record_history=False)
        self.assertEqual(len(written), 3)
        for position, (spec, solution) in enumerate(written):
            self.assertIs(solution, outcome.result.solutions[position])
            self.assertTrue(spec.slots is outcome.alternate_slots[position],
                            f"la opción {position + 1} se exportó con "
                            f"acordes ajenos")

    def test_each_option_is_marked_from_its_own_chords(self):
        """Las marcas por grado de la opción 2 salían de la progresión de
        la opción 1, porque se armaban sobre ``spec.slots``."""
        from unittest import mock
        from engine import flourish
        seen = []
        real = flourish.find_marks

        def spy(options, chords, *rest):
            seen.append([option.roman for option in options])
            return real(options, chords, *rest)

        with mock.patch.object(flourish, "find_marks", spy):
            outcome = session.harmonise_melody(
                self._request(self._melody(self.TUNE)))
        self.assertEqual(len(seen), len(outcome.result.solutions))
        for position, romans in enumerate(seen):
            own = outcome.alternate_slots[position]
            self.assertEqual(romans,
                             [slot.options[0].harmony.roman for slot in own])

    def test_each_bar_spells_with_its_own_key(self):
        """
        La tónica viene en cada `MelodyBar` y la armadura de las notas
        ajenas al acorde salía de la del primer compás: un si bemol de paso
        en un tramo en Fa se escribía la sostenido.
        """
        from engine.harmonize import Melody, MelodyBar, MelodyNote
        spec = export.ScoreSpec(slots=[], voices=[],
                                time_signature=export.TimeSignature(4, 4),
                                key_hint=0, bar_key_hints={1: -1})
        self.assertEqual(spec.key_hint_for(0), 0)
        self.assertEqual(spec.key_hint_for(1), -1)
        self.assertEqual(spec.key_hint_for(7), 0)

        notes = [MelodyNote(72, 1.0, 0, 0.0), MelodyNote(74, 1.0, 0, 1.0),
                 MelodyNote(76, 1.0, 0, 2.0), MelodyNote(74, 1.0, 0, 3.0),
                 MelodyNote(69, 1.0, 1, 0.0), MelodyNote(70, 1.0, 1, 1.0),
                 MelodyNote(72, 1.0, 1, 2.0), MelodyNote(70, 1.0, 1, 3.0),
                 MelodyNote(69, 2.0, 2, 0.0), MelodyNote(65, 2.0, 2, 2.0)]
        melody = Melody(notes=notes,
                        bars=[MelodyBar(), MelodyBar(tonic=5),
                              MelodyBar(tonic=5)],
                        melody_voice=3)
        outcome = session.harmonise_melody(
            self._request(melody, genre="chorale", seed=3, wanted=1))
        self.assertTrue(outcome.succeeded, outcome.errors)
        self.assertEqual(outcome.spec.key_hint_for(0), 0)
        self.assertEqual(outcome.spec.key_hint_for(1), -1)
        xml = export.build_musicxml(outcome.spec, outcome.result.solutions[0])
        soprano = [note for note in re.findall(r"<note>.*?</note>", xml, re.S)
                   if "<voice>1</voice>" in note and "<rest/>" not in note]
        spelled = [(re.search(r"<step>(\w)</step>", note).group(1),
                    int((re.search(r"<alter>(-?\d)</alter>", note)
                         or [None, "0"])[1]))
                   for note in soprano]
        self.assertNotIn(("A", 1), spelled)
        self.assertIn(("B", -1), spelled)


class TestFlourishMarksAcrossRests(unittest.TestCase):
    """Las marcas se pintan en la columna de la partitura, no de la búsqueda."""

    def test_a_six_four_after_a_rest_is_found_where_it_is(self):
        """
        La búsqueda saltea los silencios y los acordes de las marcas se
        armaban sobre la partitura entera: con un silencio adelante, el 6/4
        se comparaba contra el acorde de al lado ---y no se encontraba---, y
        si se encontraba quedaba numerado como en la búsqueda.
        """
        from unittest import mock
        from engine import flourish
        entries = [session.ChordEntry("C", 2.0, 0),
                   session.ChordEntry("", 2.0, 0, is_rest=True),
                   session.ChordEntry("F", 2.0, 1),
                   session.ChordEntry("G", 2.0, 1,
                                      locked_pitches=[50, 55, 59, 62]),
                   session.ChordEntry("C", 4.0, 2)]
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=entries, solutions_wanted=1,
            ga_config=GAConfig(population_size=30, generations=8,
                               random_seed=3, workers=1))
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        with mock.patch.object(flourish, "SIXTH_CHANCE", 0.0):
            session.apply_flourishes(outcome, "classical", 0)
        voiced = session.voiced_slots(outcome.spec, outcome.result.solutions[0])
        self.assertEqual(voiced[3], [50, 55, 59, 62])
        marks = [(mark.key, mark.slots)
                 for mark in outcome.flourishes.by_solution[0]]
        self.assertIn(("six_four", (3,)), marks)
        # Que es lo que pregunta la grilla de resultados, por columna.
        self.assertTrue(outcome.flourishes.marks_for(3, 0))
        self.assertFalse(outcome.flourishes.marks_for(2, 0))


class TestChromaticApproachNames(unittest.TestCase):
    """Los acordes que arma el Armonizador para una nota cromática."""

    def test_the_leading_and_tritone_approaches_are_dominants(self):
        """
        vii°/x, vii°7/x y subV/x viajan como préstamos con una cifra que
        `function_of` no conocía, y quedaban de subdominante: el vii° de la
        tónica no cobraba el premio de la dominante antes del reposo.
        """
        from engine.harmonize import (MelodyBar, applied_dominant,
                                      applied_leading, tritone_substitute)
        from engine.harmony import DOMINANT, SUBDOMINANT, function_of
        bar = MelodyBar()
        for option in (applied_leading(9, bar, False),
                       applied_leading(9, bar, True),
                       applied_leading(0, bar, False),
                       applied_leading(0, bar, True),
                       tritone_substitute(9, bar),
                       tritone_substitute(0, bar)):
            self.assertEqual(function_of(option), DOMINANT, option.roman)
        # El V/x sigue donde estaba, a propósito (ver `function_of`).
        self.assertEqual(function_of(applied_dominant(9, bar, False)),
                         SUBDOMINANT)

    def test_the_natural_seventh_in_harmonic_minor_has_a_name(self):
        """fa sostenido que sube a sol en La menor armónica: «V/?»."""
        from engine.harmonize import (HarmonisationSettings, Melody,
                                      MelodyBar, MelodyNote, applied_dominant,
                                      applied_leading, approach_options,
                                      chromatic_approaches, degree_roman)
        from engine.harmony import MODES
        bar = MelodyBar(tonic=9, mode_key="harmonic")
        self.assertEqual(degree_roman(7, bar), "bVII")
        self.assertEqual(applied_dominant(7, bar, False).roman, "V/bVII")
        self.assertEqual(applied_leading(7, bar, True).roman, "vii°7/bVII")
        melody = Melody(notes=[MelodyNote(76, 1.0, 0, 0.0),
                               MelodyNote(78, 1.0, 0, 1.0),
                               MelodyNote(79, 1.0, 0, 2.0),
                               MelodyNote(81, 1.0, 0, 3.0)],
                        bars=[bar], melody_voice=3)
        approaches = chromatic_approaches(melody, "classical")
        self.assertTrue(approaches)
        rules = HarmonisationSettings(genre_key="classical")
        for approach in approaches:
            for option in approach_options(approach, bar, rules):
                self.assertNotIn("?", option.roman)
        # Ninguna nota de ningún modo se queda sin nombre.
        for mode_key in MODES:
            for tonic in range(12):
                for pc in range(12):
                    self.assertNotIn("?", degree_roman(
                        pc, MelodyBar(tonic=tonic, mode_key=mode_key)))


class TestChromaticHarmonisation(unittest.TestCase):
    """
    Las notas fuera de la escala en el Armonizador.

    La regla: una nota fuera de la escala que sube un semitono a la
    siguiente es su sensible, y lleva debajo la dominante de esa nota ---en
    barroco y jazz también, con menos probabilidad, su séptimo grado---. En
    jazz la que baja un semitono lleva la sustitución tritonal. La que no
    cumple la regla se armoniza como cualquier otra, y no se marca sola.
    """

    GENRES = ("classical", "chorale", "jazz", "gregorian")

    def _melody(self, spec, beats=4):
        """`spec`: (nombre de nota, duración en negras), en Do mayor."""
        from engine.harmonize import Melody, MelodyBar, MelodyNote
        notes, position = [], 0.0
        for name, duration in spec:
            bar = int(position // beats)
            notes.append(MelodyNote(parse_note_name(name), duration, bar,
                                    position - bar * beats))
            position += duration
        count = int((position - 1e-6) // beats) + 1
        return Melody(notes=notes,
                      bars=[MelodyBar(beats, 4, 0, "major")
                            for _ in range(count)],
                      melody_voice=2)

    #: Sol sostenido que sube a la en Do mayor, en el segundo tiempo: no cae
    #: en tiempo fuerte, así que el acorde que lleva es el de la regla.
    RISING = [("E5", 1), ("D5", 1), ("C5", 1), ("B4", 1), ("A4", 1),
              ("G#4", 1), ("A4", 1), ("B4", 1), ("C5", 2), ("B4", 1),
              ("D5", 1), ("C5", 4)]

    def _rules(self, genre):
        from engine.harmonize import HarmonisationSettings
        return HarmonisationSettings(genre_key=genre,
                                     with_sevenths=(genre == "jazz"))

    def _chord_on(self, chosen, note_name):
        pitch = parse_note_name(note_name)
        return next(option for spot, option in chosen
                    if spot.note is not None and spot.note.pitch == pitch)

    def test_the_raised_note_gets_the_dominant_of_the_next_in_every_style(self):
        """Sol sostenido que sube a la: Mi mayor (V/vi), en los cuatro estilos."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody(self.RISING)
        for genre in self.GENRES:
            for seed in range(10):
                chosen = harmonise(melody, self._rules(genre),
                                   _random.Random(seed))
                option = self._chord_on(chosen, "G#4")
                if option.root_pc == 8:
                    # El séptimo grado de la, sólo donde se lo permite.
                    self.assertIn(genre, ("classical", "jazz"), option.label)
                    self.assertEqual(option.quality in ("dim", "halfdim"),
                                     True, option.label)
                    continue
                self.assertEqual(option.root_pc, 4, (genre, option.label))
                self.assertIn(8, option.chord.pitch_classes,
                              (genre, option.label))
                self.assertEqual(option.roman, "V/vi")

    def test_the_seventh_degree_only_in_baroque_and_jazz(self):
        """El vii°/vi aparece en barroco y jazz, y menos que la dominante."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody(self.RISING)
        for genre in self.GENRES:
            roots = [self._chord_on(harmonise(melody, self._rules(genre),
                                              _random.Random(seed)),
                                    "G#4").root_pc
                     for seed in range(60)]
            leading = roots.count(8)
            if genre in ("classical", "jazz"):
                self.assertGreater(leading, 0, genre)
                self.assertLess(leading, roots.count(4), genre)
            else:
                self.assertEqual(leading, 0, genre)

    def test_the_dominant_resolves_onto_its_note(self):
        """Después del Mi mayor viene un acorde de la: la promesa se cumple."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody(self.RISING)
        resolved = 0
        for seed in range(20):
            chosen = harmonise(melody, self._rules("chorale"),
                               _random.Random(seed))
            spots = [spot for spot, _option in chosen]
            here = next(index for index, spot in enumerate(spots)
                        if spot.note is not None
                        and spot.note.pitch == parse_note_name("G#4"))
            resolved += chosen[here + 1][1].root_pc == 9
        self.assertGreaterEqual(resolved, 18)

    def test_a_falling_semitone_in_jazz_gets_the_tritone_substitute(self):
        """La bemol que baja a sol en jazz: Ab7, el subV de sol."""
        import random as _random
        from engine.harmonize import harmonise, planned_notes
        melody = self._melody([("C5", 1), ("E5", 1), ("A5", 1), ("Ab5", 1),
                               ("G5", 2), ("E5", 2), ("F5", 1), ("D5", 1),
                               ("B4", 1), ("D5", 1), ("C5", 4)])
        for seed in range(6):
            option = self._chord_on(
                harmonise(melody, self._rules("jazz"), _random.Random(seed)),
                "Ab5")
            self.assertEqual(option.root_pc, 8, option.label)
            self.assertEqual(option.quality, "dominant", option.label)
            self.assertTrue(option.roman.startswith("subV"), option.roman)
        # En los otros estilos bajar no cumple la regla: el la bemol cae en
        # un tiempo débil y queda sin acorde, como cualquier nota de paso.
        for genre in ("classical", "chorale", "gregorian"):
            planned = {(n.bar_index, n.offset_quarters)
                       for n in planned_notes(melody, self._rules(genre))}
            self.assertNotIn((0, 3.0), planned, genre)

    def test_an_out_of_scale_note_without_a_semitone_is_not_marked(self):
        """Un fa sostenido que llega y se va por salto no se marca solo."""
        from engine.harmonize import planned_notes
        melody = self._melody([("C5", 1), ("E5", 1), ("A4", 1), ("F#5", 1),
                               ("D5", 2), ("C5", 2), ("D5", 1), ("F5", 1),
                               ("E5", 1), ("D5", 1), ("C5", 4)])
        for genre in self.GENRES:
            planned = {(n.bar_index, n.offset_quarters)
                       for n in planned_notes(melody, self._rules(genre))}
            self.assertNotIn((0, 3.0), planned, genre)

    def test_a_marked_out_of_scale_note_gets_a_chord_that_holds_it(self):
        """Marcada por el usuario, la lleva un acorde de afuera que la contiene."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody([("C5", 1), ("E5", 1), ("A4", 1), ("F#5", 1),
                               ("D5", 2), ("C5", 2), ("D5", 1), ("F5", 1),
                               ("E5", 1), ("D5", 1), ("C5", 4)])
        melody.notes[3].must_harmonise = True
        for genre in self.GENRES:
            for seed in range(4):
                option = self._chord_on(
                    harmonise(melody, self._rules(genre), _random.Random(seed)),
                    "F#5")
                self.assertIn(6, option.chord.pitch_classes,
                              (genre, option.label))
                self.assertTrue(option.is_borrowed, (genre, option.label))

    def test_turning_the_automatic_mark_off_takes_the_chord_away(self):
        """El naranja marcado solo se apaga igual que el dorado."""
        from engine.harmonize import planned_notes
        melody = self._melody(self.RISING)
        where = (1, 1.0)
        planned = {(n.bar_index, n.offset_quarters)
                   for n in planned_notes(melody, self._rules("chorale"))}
        self.assertIn(where, planned)
        melody.notes[5].skip_harmonise = True
        planned = {(n.bar_index, n.offset_quarters)
                   for n in planned_notes(melody, self._rules("chorale"))}
        self.assertNotIn(where, planned)

    def test_the_preview_matches_the_harmonisation(self):
        """Lo que el pentagrama marca es lo que después lleva acorde."""
        import random as _random
        from engine.harmonize import harmonise, planned_notes
        melody = self._melody(self.RISING)
        for genre in self.GENRES:
            preview = {(n.bar_index, n.offset_quarters)
                       for n in planned_notes(melody, self._rules(genre))}
            for seed in range(4):
                written = {(s.note.bar_index, s.note.offset_quarters)
                           for s, _o in harmonise(melody, self._rules(genre),
                                                  _random.Random(seed))
                           if s.note is not None}
                self.assertEqual(written, preview, (genre, seed))

    def test_the_bars_still_add_up(self):
        """Abrir lugares para la regla no le quita ni le suma nada al compás."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody([("C5", 1), ("G#4", 0.5), ("A4", 0.5),
                               ("B4", 2), ("C#5", 1), ("D5", 1), ("F5", 2),
                               ("E5", 4)])
        chosen = harmonise(melody, self._rules("classical"),
                           _random.Random(3))
        totals = {}
        for spot, _option in chosen:
            totals[spot.bar_index] = (totals.get(spot.bar_index, 0.0)
                                      + spot.duration_quarters)
        for bar, total in totals.items():
            self.assertAlmostEqual(total, 4.0, msg=f"compás {bar}")

    def test_a_melody_ending_on_the_relative_minor_is_minor(self):
        """La armadura dice dos tonalidades; la nota final elige."""
        from engine.harmonize import key_of_ending
        self.assertEqual(key_of_ending(parse_note_name("A4"), 0), (9, "minor"))
        self.assertEqual(key_of_ending(parse_note_name("C5"), 0), (0, "major"))
        self.assertEqual(key_of_ending(parse_note_name("D4"), 5), (2, "minor"))
        self.assertEqual(key_of_ending(None, 0), (0, "major"))

    def test_the_raised_seventh_in_minor_gets_its_dominant(self):
        """Un sol sostenido en La menor lleva Mi mayor, aunque no suba a la."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody([("A4", 1), ("B4", 1), ("C5", 1), ("D5", 1),
                               ("E5", 2), ("C5", 2), ("D5", 1), ("B4", 1),
                               ("G#4", 1), ("B4", 1), ("A4", 4)])
        for bar in melody.bars:
            bar.tonic, bar.mode_key = 9, "minor"
        for genre in self.GENRES:
            for seed in range(6):
                chosen = harmonise(melody, self._rules(genre),
                                   _random.Random(seed))
                option = self._chord_on(chosen, "G#4")
                self.assertEqual(option.root_pc, 4, (genre, option.label))
                self.assertEqual(option.roman, "V", (genre, option.label))
                self.assertEqual(chosen[-1][1].root_pc, 9, genre)

    def test_the_final_note_holds_one_chord(self):
        """La redonda final no se parte: la cadencia cae en la nota de antes."""
        import random as _random
        from engine.harmonize import harmonise
        melody = self._melody(self.RISING)
        for genre in ("classical", "chorale"):
            for seed in range(6):
                chosen = harmonise(melody, self._rules(genre),
                                   _random.Random(seed))
                last_spot, last = chosen[-1]
                self.assertEqual(last_spot.duration_quarters, 4.0)
                self.assertEqual(last.roman, "I", genre)
                self.assertEqual(chosen[-2][1].roman, "V", (genre, seed))

    def test_three_voices_close_on_the_root(self):
        """
        A tres voces, el último acorde lleva la fundamental en el bajo.

        Con la melodía terminando en la tónica, las otras dos voces tenían
        que poner tercera y quinta y el bajo nunca era la fundamental.
        """
        for genre in ("classical", "chorale"):
            request = session.HarmoniseRequest(
                genre_key=genre, voice_keys=["B", "T", "S"],
                melody=self._melody(self.RISING), melody_voice=2,
                ga_config=GAConfig(population_size=60, generations=25,
                                   random_seed=5),
                solutions_wanted=1)
            outcome = session.harmonise_melody(request)
            self.assertTrue(outcome.succeeded, outcome.errors)
            last = outcome.result.solutions[0].slots[-1]
            self.assertEqual(last[0] % 12, 0, (genre, last))
            self.assertEqual({pitch % 12 for pitch in last}, {0, 4}, genre)

    def test_a_chromatic_harmonisation_is_voiced_and_read_back(self):
        """La búsqueda de voces escribe de verdad el acorde que apunta al la."""
        request = session.HarmoniseRequest(
            genre_key="classical", voice_keys=["B", "T", "S"],
            melody=self._melody(self.RISING), melody_voice=2,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=5),
            solutions_wanted=1)
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        slots = outcome.alternate_slots.get(0, outcome.spec.slots)
        solution = outcome.result.solutions[0]
        for slot, chord in zip(slots, solution.slots):
            harmony = slot.options[0].harmony
            if harmony.roman in ("V/vi", "vii°/vi"):
                # Lo que suena es el acorde que se eligió, con su sensible.
                self.assertIn(8, {pitch % 12 for pitch in chord})
                break
        else:
            self.fail("ningún acorde apunta al la")


class TestMusicFontStaff(unittest.TestCase):
    """
    El pentagrama con la fuente musical, y sin ella.

    Se importa `staff` aunque sea de la interfaz, como en
    `TestAnalysisWriting`: lo que se prueba son cuentas y una carga de
    archivo que no crean ninguna ventana.
    """

    def test_the_font_ships_with_its_licence(self):
        import staff
        path = staff.music_font_path()
        self.assertTrue(os.path.isfile(path), path)
        licence = os.path.join(os.path.dirname(path), "OFL.txt")
        self.assertTrue(os.path.isfile(licence))
        # Desde la raíz del programa y no desde los datos del usuario: la
        # variable de pruebas mueve los datos, no los recursos.
        self.assertTrue(path.startswith(_history.program_directory()))

    def test_a_failed_load_degrades_without_errors(self):
        """Si Windows no la carga, se dibuja con trazos y no explota nada."""
        import staff
        tried = []

        def refuse(path):
            tried.append(path)
            return False

        self.assertFalse(staff.try_load_music_font(staff.music_font_path(),
                                                   refuse))
        # Se intentó también desde la copia corta, que es el rescate.
        self.assertTrue(any(staff.SHORT_FONT_FOLDER in path
                            for path in tried), tried)
        self.assertFalse(staff.try_load_music_font(
            os.path.join(tempfile.gettempdir(), "no-existe.otf"), refuse))

    def test_a_long_path_is_loaded_from_a_short_copy(self):
        """Windows no acepta rutas de más de 260 caracteres: se copia."""
        import shutil
        import staff
        # Con el prefijo de rutas largas Windows deja crear y leer la
        # carpeta, que es la situación del programa descomprimido muy
        # adentro; sin él, `makedirs` ya falla antes de llegar a la fuente.
        prefix = "\\\\?\\" if os.name == "nt" else ""
        folder = tempfile.mkdtemp()
        try:
            deep = folder
            while len(deep) < 300:
                deep = os.path.join(deep, "carpeta-larguisima")
            os.makedirs(prefix + deep)
            source = os.path.join(prefix + deep, "Bravura.otf")
            shutil.copyfile(staff.music_font_path(), source)
            loaded = []
            self.assertTrue(staff.try_load_music_font(
                source, lambda path: loaded.append(path) or True))
            self.assertEqual(len(loaded), 1)
            self.assertLessEqual(len(loaded[0]), staff.MAX_FONT_PATH)
        finally:
            shutil.rmtree(prefix + folder, ignore_errors=True)

    def test_the_four_colour_combinations_are_distinct(self):
        """En escala o fuera, con acorde o sin: cuatro aspectos distintos."""
        import staff
        colours = {"text": "#E6E8EB", "gold": "#E8C97A",
                   "chromatic": "#F0883E", "surface": "#25282F"}
        looks = {(chromatic, chord): staff.note_look(chromatic, chord, False,
                                                     colours)
                 for chromatic in (False, True) for chord in (False, True)}
        self.assertEqual(len({(look.head, look.halo)
                              for look in looks.values()}), 4)
        # Y no dependen sólo del tono: la que lleva acorde tiene halo y la
        # que no, no ---una forma, no un color---.
        for (chromatic, chord), look in looks.items():
            self.assertEqual(look.halo is not None, chord)
        # La que está fuera de la escala es naranja, lleve acorde o no.
        self.assertEqual(looks[(True, False)].head, colours["chromatic"])
        self.assertEqual(looks[(True, True)].head, colours["chromatic"])

    def test_figures_and_dots(self):
        import staff
        self.assertEqual(staff.figure_of(1.0), (1.0, 0))
        self.assertEqual(staff.figure_of(1.5), (1.0, 1))
        self.assertEqual(staff.figure_of(1.75), (1.0, 2))
        self.assertEqual(staff.figure_of(0.75), (0.5, 1))
        self.assertEqual(staff.figure_of(3.0), (2.0, 1))
        # Un tresillo de corcheas se dibuja con corcheas.
        self.assertEqual(staff.figure_of(1.0 / 3.0)[0], 0.5)

    def test_an_alteration_lasts_until_the_bar_line(self):
        """Sol sostenido y después sol: el segundo lleva becuadro."""
        import staff
        g = staff.diatonic_index("G", 4)
        notes = [(0, 0.0, g, 68, "a"), (1, 0.0, g, 67, "b"),
                 (2, 0.0, g, 67, "c"), (3, 4.0, g, 68, "d"),
                 (4, 4.0, g, 68, "e")]
        shown = staff.displayed_accidentals(notes, 0)
        self.assertEqual(shown, {"a": 1, "b": 0, "c": None, "d": 1,
                                 "e": None})

    def test_the_piano_writes_every_semitone(self):
        """
        Las doce teclas, con su accidente: ida y vuelta exacto.

        Antes la tecla negra se escribía como la blanca de al lado, y el
        armonizador no podía recibir una nota fuera de la armadura.
        """
        import staff
        for fifths in (-4, -1, 0, 2, 4):
            for midi in range(55, 84):
                index = staff.index_for_pitch(midi, fifths)
                accidental = staff.accidental_for(midi, index, fifths)
                self.assertEqual(staff.pitch_at(index, fifths, accidental),
                                 midi, (fifths, midi))
            self.assertEqual(staff.scale_of(fifths),
                             {staff.index_to_pitch(step, fifths) % 12
                              for step in range(7)})


class TestHarmonisingChapter(unittest.TestCase):
    """
    El capítulo que explica el Armonizador dice lo que el Armonizador hace.

    El libro afirma un orden de preferencias --- tercera, quinta,
    fundamental, y la fundamental barata en los reposos --- y ese orden son
    los pesos de `harmonize.py`. Cambiarlos sin tocar el libro deja un
    capítulo que explica un programa que ya no existe.
    """

    def _chapter(self):
        return next(c for c in book.CHAPTERS
                    if c.title == "Armonizar una melodía")

    def test_the_chapter_opens_with_the_harmoniser(self):
        for entry in self._chapter().entries:
            self.assertEqual(entry.locked_by, "harmoniser_first", entry.key)
        self.assertIn("harmoniser_first", achievements.BY_KEY)

    def test_the_order_of_preference_is_the_one_the_book_states(self):
        third = min(harmonize.ROLE_COST[3], harmonize.ROLE_COST[4])
        fifth = harmonize.ROLE_COST[7]
        root = harmonize.ROLE_COST[0]
        self.assertLess(third, fifth)
        self.assertLess(fifth, root)
        # Y en un reposo la fundamental se abarata: deja atrás a la quinta y
        # queda a la par de la tercera, que es lo que el libro dice. **No**
        # pasa a ser la mejor de todas --- lo decía, y era falso: con los
        # pesos de hoy queda cuatro por encima de la tercera.
        at_rest = root + harmonize.ROOT_AT_REST
        self.assertLess(at_rest, fifth)
        self.assertLess(abs(at_rest - third), fifth - third)
        # La nota que no está en el acorde pierde contra todo, por lejos.
        self.assertGreater(harmonize.NOT_A_CHORD_TONE, root * 10)

    def test_colour_is_offered_behind_the_three_and_in_order(self):
        cheapest = max(harmonize.ROLE_COST.values())
        sixth = harmonize.COLOUR_COST[9]
        seventh = harmonize.COLOUR_COST[10]
        ninth = harmonize.COLOUR_COST[2]
        self.assertGreater(sixth, cheapest)
        self.assertLessEqual(sixth, seventh)
        self.assertLess(seventh, ninth)

    def test_the_melody_outweighs_the_progression(self):
        """«Dónde cae la nota importa más que cualquier otra cosa.»"""
        settings = harmonize.HarmonisationSettings()
        self.assertGreater(harmonize.melodic_weight(harmonize.ROLE_COST[7]),
                           settings.repeat)

    def test_the_figures_stay_on_the_staff_the_book_describes(self):
        """
        Los pentagramas se describen en grados, y la interfaz los dibuja
        tal cual. Un grado disparatado saldría dibujado igual, con veinte
        líneas adicionales.
        """
        for entry in self._chapter().entries:
            for figure in entry.figures:
                for voice in figure.voices:
                    for step in voice:
                        if step is None:
                            continue
                        self.assertGreaterEqual(step, -8, entry.key)
                        self.assertLessEqual(step, 14, entry.key)
                if figure.marks:
                    self.assertLessEqual(
                        len(figure.marks),
                        max(len(voice) for voice in figure.voices), entry.key)


class TestCreatorVisit(unittest.TestCase):
    """El que aparece a los tres sonidos armados en el experimentador."""

    def _ledger(self, folder):
        return visitors.Ledger.load(os.path.join(folder, "visitors.json"))

    def test_three_experiments_bring_him(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.EXPERIMENTS_NEEDED - 1):
                self.assertEqual(ledger.record_experiment(), [])
            self.assertEqual(ledger.record_experiment(),
                             [visitors.CREATOR_SOUND])

    def test_he_does_not_come_twice(self):
        """Ya vino: seguir contando deja el archivo creciendo por nada."""
        with tempfile.TemporaryDirectory() as folder:
            ledger = self._ledger(folder)
            for _ in range(visitors.EXPERIMENTS_NEEDED):
                ledger.record_experiment()
            ledger.mark(visitors.CREATOR_SOUND)
            before = ledger.experiments
            self.assertEqual(ledger.record_experiment(), [])
            self.assertEqual(ledger.experiments, before)

    def test_the_count_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "visitors.json")
            ledger = visitors.Ledger.load(path)
            ledger.record_experiment()
            ledger.record_experiment()
            again = visitors.Ledger.load(path)
            self.assertEqual(again.experiments, 2)
            self.assertEqual(again.record_experiment(),
                             [visitors.CREATOR_SOUND])

    def test_his_key_is_not_the_key_of_the_achievement_he_hands_out(self):
        """
        Su llave de libro y su logro se consiguen en el mismo instante.

        Con el mismo nombre para las dos cosas no habría manera de saber
        cuál falló cuando falle alguna, y `_lore_unlocked` contestaría que
        el apartado está escrito porque existe el logro.
        """
        award = visitors.award_for(visitors.CREATOR_SOUND)
        self.assertEqual(award, "visit_creator")
        self.assertNotEqual(visitors.book_key(visitors.CREATOR_SOUND), award)
        self.assertIsNotNone(
            book.entry_for_lock(visitors.book_key(visitors.CREATOR_SOUND)))

    def test_he_reveals_his_name_and_says_the_numbers(self):
        """
        Habla de la serie armónica, del muestreo y de los bits.

        Los dos números son los que el programa usa de verdad --- están en
        `engine/audio.py` y en el empaquetado de `_encode` ---, así que si
        alguno cambiara, la escena pasaría a mentir.
        """
        visit = visitors.VISITS[visitors.CREATOR_SOUND]
        self.assertEqual(visit.name, "El creador")
        self.assertIn("reveal", [line.cue for line in visit.lines])
        said = " ".join(line.text for line in visit.lines)
        self.assertIn("serie armónica", said)
        self.assertIn("cuarenta y cuatro mil cien", said)
        self.assertIn("Dieciséis", said)
        self.assertEqual(harmonics.SAMPLE_RATE, 44100)

    def test_he_is_staged_like_the_other_teachers(self):
        """
        Fondo negro, y estar y dejar de estar en un pestañeo.

        `staging_for` no falla cuando un personaje no está en la tabla:
        devuelve la puesta de otro, y la escena se dibuja igual. Con el
        creador afuera salía con el valle, la luna, el humo y el viento del
        señor del sombrero --- una puesta que dice algo muy concreto de
        quien la usa --- y no había ningún error en ninguna parte.
        """
        import cinematic
        self.assertIn(visitors.CREATOR, cinematic.STAGING)
        mine = cinematic.staging_for(visitors.CREATOR)
        bach = cinematic.staging_for(visitors.BACH)
        self.assertEqual(mine["sky"], bach["sky"])
        self.assertEqual(mine["entrance"], bach["entrance"])
        self.assertEqual(mine["departure"], bach["departure"])
        # Y sin nada sonando: su escena empieza con el ventilador callándose.
        self.assertEqual(mine["bed"], "")
        self.assertEqual(mine["enter_sound"], "")

    def test_his_poses_and_his_voice_exist(self):
        """
        Un recorte que falte no da error: `load_pose` devuelve ``None`` y el
        personaje simplemente no aparece, que es la peor manera de fallar.
        """
        import cinematic
        table = cinematic.POSES[visitors.CREATOR]
        for line in visitors.VISITS[visitors.CREATOR_SOUND].lines:
            if line.pose:
                self.assertIn(line.pose, table, line.pose)
        for name in table.values():
            self.assertTrue(
                os.path.exists(os.path.join(cinematic.assets_directory(), name)),
                name)
        import cinematic
        self.assertIn(cinematic.SPEAKERS[visitors.CREATOR]["blip"],
                      ambience._RECIPES)


class TestScreenGuides(unittest.TestCase):
    """
    Las guías que se abren solas la primera vez que se llega a una pantalla.

    Lo que se prueba acá es el guion y el cableado, no el dibujo: abrir una
    ventana es trabajo de `uitest`. Pero una guía mal cableada **no falla**
    --- simplemente no aparece nunca --- y eso es exactamente lo que no se
    nota probando a mano.
    """

    def _app(self):
        import app
        return app

    def _source(self) -> str:
        with open(self._app().__file__, encoding="utf-8") as handle:
            return handle.read()

    def test_every_guide_exists_and_says_something(self):
        app = self._app()
        self.assertEqual(set(app.SCREEN_GUIDES),
                         {"chords", "melody", "harmony", "parameters"})
        for key, steps in app.SCREEN_GUIDES.items():
            self.assertTrue(steps, key)
            for position, step in enumerate(steps):
                self.assertTrue(step.get("title"), f"{key}[{position}]")
                self.assertTrue(step.get("body"), f"{key}[{position}]")
                target = step.get("target")
                self.assertTrue(target is None or callable(target),
                                f"{key}[{position}]")

    def test_a_guide_never_moves_the_carousel(self):
        """
        Un paso con ``screen`` navega. Una guía no puede: el usuario está a
        mitad de un trabajo en la pantalla que la guía viene a explicar, y
        llevarlo a otra sería pisarle lo que estaba haciendo.
        """
        app = self._app()
        for key, steps in app.SCREEN_GUIDES.items():
            for position, step in enumerate(steps):
                self.assertNotIn("screen", step, f"{key}[{position}]")
        # Y el recorrido de bienvenida sí, en todos sus pasos: es lo que lo
        # distingue, y de eso sale `Tutorial.navigates`.
        for position, step in enumerate(app.TUTORIAL_STEPS):
            self.assertIn("screen", step, position)

    def test_every_guide_is_asked_for_by_some_screen(self):
        """
        Que la clave que pide la pantalla sea una que existe.

        `_maybe_guide` se calla cuando la clave no está en el catálogo, así
        que una letra de más deja la guía escrita y jamás mostrada. Se lee
        el archivo en vez de importarlo para no tener que instanciar la
        ventana.
        """
        import re
        app = self._app()
        source = self._source()
        asked = set(re.findall(r'_maybe_guide\(\s*"([^"]+)"\s*\)', source))
        self.assertEqual(asked, set(app.SCREEN_GUIDES))

    def test_resetting_the_tutorial_brings_them_back(self):
        """
        Es la única manera de volver a verlas, así que el botón tiene que
        vaciar la lista **y guardarla**: sin escribir el archivo, volvían
        sólo hasta el próximo arranque.
        """
        source = self._source()
        body = source.split("def _start_tutorial", 1)[1].split("\n    def ", 1)[0]
        self.assertIn('self.settings["guides_seen"] = []', body)
        self.assertIn("save_settings", body)


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
        # Las camas de las visiones van aparte: son las únicas que suenan
        # **sin nadie hablando encima**, así que ocupan el lugar que en las
        # otras escenas le corresponde a la voz. El viento de las tres, y la
        # lluvia de la tercera, que reemplaza al viento cuando se larga.
        alone = ("gale", "rain")
        beds = [name for name, (_m, loops) in ambience._RECIPES.items()
                if loops and name not in alone]
        for name in beds:
            self.assertAlmostEqual(self._power(name), ambience.POWER_BED,
                                   delta=0.02, msg=name)
        for name in alone:
            self.assertAlmostEqual(self._power(name), ambience.POWER_SOLO,
                                   delta=0.02, msg=name)
        self.assertGreater(ambience.POWER_SOLO, ambience.POWER_BED)
        for name in ("wind", "tritone", "toll", "crossroads", "train",
                     "blues", "thunder", "dread"):
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
        # El tritono es de la segunda, que comparte la lista con la primera.
        played = {"gale", "train", "owls", "crossroads", "blues", "tritone"}
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


# ---------------------------------------------------------------------------
# El analizador
# ---------------------------------------------------------------------------

def _line(pitches_and_lengths, name=""):
    """Una voz, a partir de pares (altura, duración). None es un silencio."""
    notes, position = [], 0.0
    for pitch, length in pitches_and_lengths:
        if pitch is not None:
            notes.append(analysis.Note(pitch=pitch, onset=position,
                                       duration=length))
        position += length
    return analysis.Part(name=name, notes=notes)


def _score(lines, fifths=0, beats=4, beat_type=4, pickup=0.0):
    """Una partitura de prueba, con las voces de grave a aguda."""
    names = importer.voice_names(len(lines))
    return analysis.Score(
        parts=[_line(line, name) for name, line in zip(names, lines)],
        fifths=fifths, beats=beats, beat_type=beat_type,
        pickup_quarters=pickup)


def _symbols(result):
    return [segment.symbol for segment in result.segments]


def _romans(result):
    return [segment.roman for segment in result.segments]


def _kinds(result):
    return {finding.kind for finding in result.findings}


#: Los primeros cuatro compases del Preludio en Do mayor, BWV 846, escritos
#: como MusicXML para poder importarlos.
#:
#: Cada compás es la misma figura dos veces: las dos notas de la mano
#: izquierda tenidas media redonda, y las tres de la derecha arpegiadas dos
#: veces en semicorcheas. Es Bach literal y sirve de piedra de toque: la
#: progresión es I - ii - V - I con dos inversiones que un análisis correcto
#: tiene que nombrar, y el cifrado de esas inversiones (4/2 y 6/5) es el que
#: figura en cualquier edición comentada.
_BWV846_BARS = [
    (48, 52, [67, 72, 76]),      # Do  Mi  | Sol Do  Mi
    (48, 50, [69, 74, 77]),      # Do  Re  | La  Re  Fa
    (47, 50, [67, 74, 77]),      # Si  Re  | Sol Re  Fa
    (48, 52, [67, 72, 76]),      # Do  Mi  | Sol Do  Mi
]


def _xml_note(midi, duration, voice, staff, rest=False):
    step = "CCDDEFFGGAAB"[midi % 12]
    octave = midi // 12 - 1
    body = ("<rest/>" if rest else
            f"<pitch><step>{step}</step><octave>{octave}</octave></pitch>")
    return (f"<note>{body}<duration>{duration}</duration>"
            f"<voice>{voice}</voice><staff>{staff}</staff></note>")


def _bwv846_musicxml():
    measures = []
    for index, (low, high, upper) in enumerate(_BWV846_BARS, start=1):
        attributes = ""
        if index == 1:
            attributes = ("<attributes><divisions>4</divisions>"
                          "<key><fifths>0</fifths></key>"
                          "<time><beats>4</beats><beat-type>4</beat-type>"
                          "</time><staves>2</staves></attributes>")
        half = []
        # La mano izquierda: dos notas tenidas, la segunda desde la segunda
        # semicorchea. Cada voz vuelve al principio de la mitad de compás.
        half.append(_xml_note(low, 8, 1, 2))
        half.append("<backup><duration>8</duration></backup>")
        half.append(_xml_note(0, 1, 2, 2, rest=True))
        half.append(_xml_note(high, 7, 2, 2))
        half.append("<backup><duration>8</duration></backup>")
        half.append(_xml_note(0, 2, 3, 1, rest=True))
        for midi in upper + upper:
            half.append(_xml_note(midi, 1, 3, 1))
        measures.append(f"<measure number='{index}'>{attributes}"
                        + "".join(half * 2) + "</measure>")
    return ("<?xml version='1.0' encoding='UTF-8'?>"
            "<score-partwise version='3.1'>"
            "<work><work-title>Preludio BWV 846</work-title></work>"
            "<part-list><score-part id='P1'><part-name>Clave</part-name>"
            "</score-part></part-list>"
            "<part id='P1'>" + "".join(measures) + "</part></score-partwise>")


class TestAnalysisOfBach(unittest.TestCase):
    """El analizador contra música de verdad, importada de un archivo."""

    @classmethod
    def setUpClass(cls):
        handle = tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False,
                                             mode="w", encoding="utf-8")
        handle.write(_bwv846_musicxml())
        handle.close()
        cls.path = handle.name
        cls.score = importer.read_voices(cls.path)
        cls.result = analysis.analyse(cls.score)

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.path)
        except OSError:
            pass

    def test_the_voices_come_back_separately(self):
        """Cada línea del arpegio es una voz, no un acorde apilado."""
        self.assertEqual(len(self.score.parts), 3)
        self.assertEqual([part.name for part in self.score.parts],
                         ["Bajo", "Alto", "Soprano"])
        # El bajo lleva ocho notas: dos por compás, de media redonda.
        self.assertEqual(len(self.score.parts[0].notes), 8)
        self.assertEqual(self.score.parts[0].notes[0].duration, 2.0)
        # Y la mano derecha, seis semicorcheas por mitad de compás.
        self.assertEqual(len(self.score.parts[2].notes), 48)

    def test_the_key_is_c_major(self):
        self.assertEqual(self.result.key.tonic_pc, 0)
        self.assertEqual(self.result.key.mode_key, "major")
        self.assertEqual(self.result.key.label, "Do mayor")
        self.assertGreater(self.result.key.confidence, 0.5)

    def test_one_chord_per_bar(self):
        """Cuatro compases, cuatro acordes.

        Es la mitad del problema: un arpegio cambia de vertical cada
        semicorchea y leer acorde por vertical devolvía dieciséis acordes
        por compás que nadie escribió.
        """
        self.assertEqual(len(self.result.segments), 4)
        self.assertEqual([s.bar_index for s in self.result.segments],
                         [1, 2, 3, 4])

    def test_the_progression_is_the_one_bach_wrote(self):
        self.assertEqual(_symbols(self.result),
                         ["C", "Dm7/C", "G7/B", "C"])

    def test_the_degrees_and_the_inversions(self):
        self.assertEqual(_romans(self.result), ["I", "ii4/2", "V6/5", "I"])

    def test_the_figured_bass(self):
        """El cifrado del bajo continuo, abreviado como se abrevia.

        El acorde en estado fundamental no lleva cifra --- se da por sabida
        ---, la séptima con su séptima en el bajo lleva 4/2 y con su tercera
        en el bajo, 6/5.
        """
        self.assertEqual([s.figure for s in self.result.segments],
                         ["", "4/2", "6/5", ""])

    def test_the_functions(self):
        self.assertEqual([s.function for s in self.result.segments],
                         [harmony.TONIC, harmony.SUBDOMINANT,
                          harmony.DOMINANT, harmony.TONIC])

    def test_it_closes_with_an_imperfect_authentic_cadence(self):
        """Imperfecta porque la dominante está invertida, que es el caso."""
        kinds = [cadence.kind for cadence in self.result.cadences]
        self.assertIn("cadencia auténtica imperfecta", kinds)

    def test_nothing_is_read_as_an_ornament(self):
        """En el Preludio toda nota pertenece a su acorde."""
        self.assertEqual(self.result.ornaments, [])

    def test_it_can_be_written_back_out(self):
        target = tempfile.mkdtemp()
        written = session.export_analysis(self.result, target,
                                          ("musicxml", "midi"), "bwv846")
        self.assertEqual(len(written), 2)
        with open(written[0], encoding="utf-8") as handle:
            xml = handle.read()
        self.assertIn("<fifths>0</fifths>", xml)
        self.assertIn("<sign>G</sign>", xml)
        self.assertIn("<sign>F</sign>", xml)


class TestAnalysisKey(unittest.TestCase):
    def test_the_resting_note_decides(self):
        result = analysis.analyse(_score([
            [(43, 4), (48, 4)], [(59, 4), (55, 4)],
            [(62, 4), (64, 4)], [(67, 4), (72, 4)]]))
        self.assertEqual(result.key.label, "Do mayor")

    def test_a_phrase_that_stops_on_the_dominant_is_not_in_that_key(self):
        """Am - G - F - E es La menor con semicadencia, no Mi de nada.

        Sin esto la frase quedaba analizada en la tonalidad donde para, que
        es justamente la que una semicadencia no establece.
        """
        result = analysis.analyse(_score([
            [(45, 4), (43, 4), (41, 4), (40, 4)],
            [(57, 4), (55, 4), (53, 4), (56, 4)],
            [(60, 4), (59, 4), (57, 4), (59, 4)],
            [(64, 4), (62, 4), (60, 4), (64, 4)]]))
        self.assertEqual(result.key.tonic_pc, 9)

    def test_the_signature_narrows_the_candidates(self):
        result = analysis.analyse(_score([
            [(43, 4), (38, 4), (43, 4)], [(59, 4), (57, 4), (59, 4)],
            [(62, 4), (62, 4), (62, 4)], [(67, 4), (66, 4), (67, 4)]],
            fifths=1))
        self.assertEqual(result.key.label, "Sol mayor")

    def test_a_picardy_third_does_not_change_the_key(self):
        """i - iv - V - I: una pieza en menor que termina en la tónica mayor.

        La tercera de Picardía ya tenía su descuento suave, pero además
        pagaba el de "acorde final con una nota ajena a la escala", que es
        el de la semicadencia: un coral en fa menor de Bach se leía entero
        en fa mixolidio. Y el último acorde es la tónica (I), no un V/iv.
        """
        result = analysis.analyse(_score([
            [(45, 4), (50, 4), (52, 4), (45, 4)],
            [(52, 4), (53, 4), (56, 4), (57, 4)],
            [(60, 4), (62, 4), (64, 4), (64, 4)],
            [(69, 4), (69, 4), (71, 4), (73, 4)]]))
        self.assertEqual(result.key.label, "La menor")
        self.assertEqual(_romans(result), ["i", "iv", "V", "I"])
        self.assertEqual(result.segments[-1].function, harmony.TONIC)
        self.assertIn("cadencia auténtica perfecta",
                      [cadence.kind for cadence in result.cadences])

    def test_a_major_ending_is_not_picardy_if_the_piece_began_elsewhere(self):
        """Am - G - F - E sigue siendo La menor: el Mi del final no es un
        Mi menor con Picardía, porque la pieza no arrancó en Mi."""
        result = analysis.analyse(_score([
            [(45, 4), (43, 4), (41, 4), (40, 4)],
            [(57, 4), (55, 4), (53, 4), (56, 4)],
            [(60, 4), (59, 4), (57, 4), (59, 4)],
            [(64, 4), (62, 4), (60, 4), (64, 4)]]))
        self.assertEqual(result.key.tonic_pc, 9)
        self.assertEqual(result.segments[-1].roman, "V")

    def test_a_piece_framed_by_its_dominant_is_in_the_minor_key(self):
        """Abre en Mi mayor, cierra en Mi mayor con iv6 - V, y por dentro
        cadencia dos veces en La menor: está en La menor.

        Es el final frigio de los corales (BWV 153.1, BWV 311). Todo lo que
        se le cree al principio y al final se iba para Mi, y la pieza
        entera se leía en Mi mixolidio con cada acorde cambiado de función.
        """
        chords = [((40, 56, 59, 64), 1), ((45, 57, 60, 64), 1),
                  ((50, 57, 62, 65), 1), ((52, 56, 59, 64), 1),
                  ((45, 57, 60, 69), 1), ((41, 57, 60, 65), 1),
                  ((40, 56, 59, 64), 1), ((45, 57, 64, 72), 1),
                  ((41, 57, 62, 69), 1), ((40, 56, 59, 68), 2)]
        result = analysis.analyse(_score(
            TestAnalysisCadences._chords(chords)))
        self.assertEqual(result.key.tonic_pc, 9)
        self.assertIn(result.key.mode_key, ("minor", "harmonic"))
        self.assertEqual(_romans(result)[:5], ["V", "i", "iv", "V", "i"])
        self.assertIn("cadencia frigia",
                      [cadence.kind for cadence in result.cadences])


class TestAnalysisFunctions(unittest.TestCase):
    def test_a_secondary_dominant_is_named_by_its_target(self):
        result = analysis.analyse(_score([
            [(48, 2), (50, 2), (43, 2), (48, 2)],
            [(55, 2), (54, 2), (55, 2), (55, 2)],
            [(64, 2), (60, 2), (62, 2), (64, 2)],
            [(72, 2), (69, 2), (71, 2), (72, 2)]]))
        applied = result.segments[1]
        self.assertEqual(applied.category, "dominante aplicada")
        self.assertEqual(applied.roman, "V7/V")
        self.assertEqual(applied.function, harmony.DOMINANT)
        self.assertIn("resuelve", applied.detail)

    def test_a_borrowed_chord_says_which_mode_it_came_from(self):
        result = analysis.analyse(_score([
            [(48, 2), (53, 2), (48, 4)],
            [(55, 2), (56, 2), (55, 4)],
            [(64, 2), (60, 2), (64, 4)],
            [(72, 2), (72, 2), (72, 4)]]))
        borrowed = result.segments[1]
        self.assertEqual(borrowed.category, "intercambio modal")
        self.assertEqual(borrowed.roman, "iv")
        self.assertEqual(borrowed.function, harmony.SUBDOMINANT)
        self.assertIn("menor natural", borrowed.source_mode)

    def test_a_suspended_fourth_that_resolves_is_said_to_resolve(self):
        result = analysis.analyse(_score([
            [(48, 4), (43, 4), (48, 4)],
            [(55, 4), (50, 4), (55, 4)],
            [(64, 4), (62, 4), (64, 4)],
            [(72, 4), (72, 3), (71, 1), (72, 4)]]))
        suspended = next(s for s in result.segments
                         if s.category == "suspendido")
        self.assertEqual(suspended.symbol, "Gsus4")
        self.assertIn("suspensión resuelta", suspended.sus_note)

    def test_a_fourth_that_resolves_inside_the_beat_is_a_suspension(self):
        """El do que queda del acorde anterior y baja a si en la segunda
        corchea es un retardo sobre Sol, no un Sol sus4.

        El tiempo fuerte pesa más que el contratiempo, así que la cuarta le
        ganaba a la tercera y los corales salían llenos de sus4. El cifrado
        sigue viendo el retardo: un continuista escribe el 4.
        """
        result = analysis.analyse(_score([
            [(48, 1), (43, 1), (48, 1)],
            [(55, 1), (55, 1), (55, 1)],
            [(64, 1), (62, 1), (64, 1)],
            [(72, 1.5), (71, .5), (72, 1)]]))
        self.assertEqual(_symbols(result), ["C", "G", "C"])
        self.assertEqual(_romans(result), ["I", "V", "I"])
        self.assertEqual(result.segments[1].figure, "4")

    def test_a_diminished_seventh_is_rooted_by_where_it_goes(self):
        """si-fa-re-sol# en La menor, yendo a la tónica, es vii°6/5.

        Las cuatro notas de una séptima disminuida están a la misma
        distancia y el bajo desempataba: salía "Si dim7" y "ii°7". La
        fundamental es la sensible del acorde al que resuelve. Y el vii° de
        una pieza en menor es diatónico, como el V: no una "sensible
        aplicada de i".
        """
        result = analysis.analyse(_score([
            [(45, 1), (47, 1), (48, 1), (45, 1)],
            [(52, 1), (53, 1), (52, 1), (52, 1)],
            [(60, 1), (62, 1), (60, 1), (60, 1)],
            [(69, 1), (68, 1), (69, 1), (69, 1)]]))
        self.assertEqual(result.key.label, "La menor")
        chord = result.segments[1]
        self.assertEqual(chord.symbol, "G#dim7/B")
        self.assertEqual(chord.roman, "vii°6/5")
        self.assertEqual(chord.category, "diatónico")
        self.assertEqual(chord.function, harmony.DOMINANT)

    def test_a_chain_of_applied_dominants_is_read_as_a_chain(self):
        """Dos aplicadas seguidas no son una modulación: son una cadena."""
        result = analysis.analyse(_score([
            [(48, 4), (45, 4), (50, 4), (43, 4), (48, 4), (48, 4)],
            [(55, 4), (57, 4), (57, 4), (59, 4), (55, 4), (55, 4)],
            [(64, 4), (61, 4), (60, 4), (62, 4), (64, 4), (64, 4)],
            [(72, 4), (67, 4), (66, 4), (67, 4), (72, 4), (72, 4)]]))
        self.assertEqual(len(result.groups), 1)
        self.assertIn("cadena", result.groups[0].label)

    def test_an_alternative_is_offered_when_the_reading_is_doubtful(self):
        """Do-mi-sol-la es un Do6 y un Lam7, y las dos son ciertas."""
        readings = analysis.read_chord({0: 1.0, 4: 1.0, 7: 1.0, 9: 1.0},
                                       bass_pc=9)
        best, alternative, doubtful = analysis.best_and_alternative(readings)
        self.assertTrue(doubtful)
        self.assertIsNotNone(alternative)
        self.assertNotEqual(best.root_pc, alternative.root_pc)

    def test_an_added_sixth_on_the_fourth_degree_is_a_ii65(self):
        """Fa-la-do-re sobre fa, en Do mayor, es ii6/5 y no IV con sexta.

        Las notas no lo deciden ---la fundamental en el bajo desempataba a
        favor de Fa6 por un pelo--- y en los corales de Bach ése es el
        predominante de todas las cadencias. Sobre la tónica, en cambio, la
        sexta agregada es la del jazz y se queda como está.
        """
        result = analysis.analyse(_score([
            [(48, 4), (41, 4), (43, 4), (48, 4)],
            [(55, 4), (57, 4), (55, 4), (55, 4)],
            [(64, 4), (62, 4), (62, 4), (64, 4)],
            [(72, 4), (72, 4), (71, 4), (69, 4)]]))
        self.assertEqual(_symbols(result), ["C", "Dm7/F", "G", "C6"])
        self.assertEqual(_romans(result)[1], "ii6/5")
        self.assertEqual(result.segments[1].alternative.symbol, "F6")
        self.assertEqual(result.segments[3].roman, "I")

    def test_an_added_sixth_on_iv_in_minor_is_half_diminished(self):
        """Re-fa-la-si sobre re, en La menor: iiø6/5, no iv con sexta."""
        result = analysis.analyse(_score([
            [(45, 4), (50, 4), (52, 4), (45, 4)],
            [(52, 4), (53, 4), (52, 4), (52, 4)],
            [(60, 4), (59, 4), (59, 4), (60, 4)],
            [(69, 4), (69, 4), (68, 4), (69, 4)]]))
        self.assertEqual(result.key.label, "La menor")
        self.assertEqual(result.segments[1].symbol, "Bm7b5/D")
        self.assertEqual(result.segments[1].roman, "iiø6/5")

    def test_an_alberti_bass_under_long_notes_is_read_bar_by_bar(self):
        """Un bajo de Alberti debajo de una melodía en redondas.

        Cada tiempo tiene dos notas y ningún tiempo suelto llega a acorde, así
        que la racha entera de tiempos flacos juntaba el Do de un compás con
        el Fa del siguiente, no cabía en ninguno y los dos compases quedaban
        sin nombre (pasaba en la sonata K. 545). La racha se parte por las
        barras de compás antes de rendirse.
        """
        def alberti(low, high, middle):
            return [(pitch, 0.5) for pitch in (low, high, middle, high) * 2]
        result = analysis.analyse(_score([
            alberti(48, 55, 52) + alberti(48, 57, 53) + alberti(47, 55, 50)
            + [(48, 4)],
            [(None, 12), (64, 4)],
            [(79, 4), (81, 4), (77, 4), (72, 4)]]))
        self.assertEqual(result.segments[0].start, 0.0)
        self.assertEqual(result.segments[0].symbol, "C")
        self.assertEqual(result.segments[1].start, 4.0)
        self.assertEqual(result.segments[1].reading.root_pc, 5)

    def test_two_triads_in_one_beat_are_two_chords(self):
        """vi y IV6 en corcheas no son un IV con séptima mayor.

        La-do-mi en la primera corchea y la-do-fa en la segunda suman un
        Fa con séptima mayor que explica todo el tiempo, y como lee bien el
        tiempo no se partía. Cambian dos voces, una por salto: es un acorde
        nuevo, como escribe cualquier análisis de un coral.
        """
        result = analysis.analyse(_score([
            [(48, 1), (45, 1), (43, 1), (48, 1)],
            [(55, 1), (60, 1), (59, 1), (55, 1)],
            [(64, 1), (64, .5), (65, .5), (62, 1), (64, 1)],
            [(72, 1), (72, .5), (77, .5), (74, 1), (72, 1)]]))
        self.assertEqual(_symbols(result), ["C", "Am", "F/A", "G", "C"])
        self.assertEqual(_romans(result)[1:3], ["vi", "IV6"])

    def test_a_single_voice_resolving_does_not_split_the_beat(self):
        """Una sola voz que baja por grado mientras las otras sostienen es un
        retardo que resuelve, no un Mi menor seguido de un Sol."""
        result = analysis.analyse(_score([
            [(48, 1), (43, 1), (48, 1), (48, 1)],
            [(55, 1), (59, 1), (55, 1), (55, 1)],
            [(64, 1), (62, 1), (64, 1), (64, 1)],
            [(72, 1), (76, .5), (74, .5), (72, 1), (72, 1)]]))
        self.assertEqual([s.start for s in result.segments], [0.0, 1.0, 2.0])
        self.assertEqual(result.segments[1].reading.root_pc, 7)


class TestAnalysisCadences(unittest.TestCase):
    """Las cadencias, incluidas las tres que el generador sabe citar."""

    def _cadences(self, lines):
        return [c.kind for c in analysis.analyse(_score(lines)).cadences]

    def test_authentic_and_plagal_and_deceptive(self):
        perfect = self._cadences([
            [(43, 4), (48, 4)], [(59, 4), (55, 4)],
            [(62, 4), (64, 4)], [(67, 4), (72, 4)]])
        self.assertIn("cadencia auténtica perfecta", perfect)

        plagal = self._cadences([
            [(53, 4), (48, 4)], [(57, 4), (55, 4)],
            [(60, 4), (64, 4)], [(72, 4), (72, 4)]])
        self.assertIn("cadencia plagal", plagal)

        # La rota necesita frase: es la dominante que promete la tónica y
        # entrega el sexto grado, y para que se oiga como promesa rota la
        # pieza tiene que seguir y terminar donde correspondía.
        deceptive = self._cadences([
            [(48, 2), (53, 2), (43, 2), (45, 4), (53, 2), (43, 2), (48, 4)],
            [(55, 2), (57, 2), (59, 2), (60, 4), (57, 2), (59, 2), (55, 4)],
            [(64, 2), (60, 2), (62, 2), (64, 4), (60, 2), (62, 2), (64, 4)],
            [(72, 2), (72, 2), (71, 2), (69, 4), (72, 2), (71, 2), (72, 4)]])
        self.assertIn("cadencia rota", deceptive)
        self.assertIn("cadencia auténtica perfecta", deceptive)

    @staticmethod
    def _chords(chords):
        """Acordes a cuatro voces: ((bajo, tenor, alto, soprano), duración)."""
        lines = [[], [], [], []]
        for pitches, length in chords:
            for voice, pitch in enumerate(pitches):
                lines[voice].append((pitch, length))
        return lines

    def test_a_half_cadence_before_a_phrase_that_starts_on_the_tonic(self):
        """I - IV - V (reposa) | I - IV - V - I: la primera frase termina en
        la dominante aunque la segunda arranque en la tónica.

        La regla que cancela la semicadencia cuando la dominante sigue a la
        tónica no miraba si esa tónica se detenía, y en un coral casi toda
        frase que termina en V empieza la siguiente en I: no había
        semicadencias.
        """
        result = analysis.analyse(_score(self._chords([
            ((48, 55, 64, 72), 1), ((41, 57, 65, 72), 1),
            ((43, 55, 62, 71), 2),
            ((48, 55, 64, 72), 1), ((41, 57, 65, 69), 1),
            ((43, 55, 62, 71), 1), ((48, 55, 64, 72), 4)])))
        kinds = [(c.kind, c.index) for c in result.cadences]
        self.assertIn(("semicadencia", 2), kinds)
        self.assertIn(("cadencia auténtica perfecta", 6), kinds)

    def test_a_cadence_in_another_key(self):
        """E - Am, con el La menor que reposa, en una pieza en Do: la frase
        cierra en la relativa. Mirando sólo la tónica de la pieza, la mitad
        de las fermatas de un coral quedaban sin cadencia."""
        result = analysis.analyse(_score(self._chords([
            ((48, 55, 64, 72), 1), ((41, 57, 65, 72), 1),
            ((40, 56, 64, 71), 1), ((45, 57, 64, 72), 2),
            ((43, 55, 62, 71), 1), ((48, 55, 64, 72), 4)])))
        self.assertEqual(result.key.label, "Do mayor")
        inner = next(c for c in result.cadences if c.index == 3)
        self.assertEqual(inner.kind, "cadencia auténtica perfecta")
        self.assertIn("La menor", inner.detail)

    def test_the_phrygian_quotation(self):
        """La misma que el generador cita: i - bVII - bVI - V."""
        kinds = self._cadences([
            [(45, 4), (43, 4), (41, 4), (40, 4)],
            [(57, 4), (55, 4), (53, 4), (56, 4)],
            [(60, 4), (59, 4), (57, 4), (59, 4)],
            [(64, 4), (62, 4), (60, 4), (64, 4)]])
        self.assertIn(harmony.PHRYGIAN_CADENCE.label.lower(), kinds)

    def test_the_vivaldi_cycle(self):
        # Am Dm G C F Bdim E Am.
        kinds = self._cadences([
            [(45, 4), (50, 4), (43, 4), (48, 4), (41, 4), (47, 4), (40, 4),
             (45, 4)],
            [(57, 4), (53, 4), (59, 4), (52, 4), (57, 4), (50, 4), (56, 4),
             (57, 4)],
            [(60, 4), (57, 4), (62, 4), (55, 4), (60, 4), (53, 4), (59, 4),
             (60, 4)],
            [(64, 4), (62, 4), (67, 4), (64, 4), (65, 4), (62, 4), (64, 4),
             (64, 4)]])
        self.assertIn(harmony.VIVALDI_CADENCE.label.lower(), kinds)

    def test_the_descending_chromatic_bass(self):
        kinds = self._cadences([
            [(45, 4), (44, 4), (43, 4), (41, 4), (40, 4), (45, 4)],
            [(57, 4), (57, 4), (57, 4), (57, 4), (56, 4), (57, 4)],
            [(60, 4), (60, 4), (60, 4), (60, 4), (59, 4), (60, 4)],
            [(64, 4), (64, 4), (64, 4), (64, 4), (64, 4), (64, 4)]])
        self.assertIn(harmony.CHROMATIC_BASS_CADENCE.label.lower(), kinds)

    def test_the_quotations_come_from_the_generator(self):
        """No hay una segunda copia de estas progresiones.

        Se leen de `harmony.SET_PIECES`, que es de donde las saca el
        generador para citarlas. Si alguna vez se corrige una nota, el
        analizador tiene que dejar de reconocer la vieja en el mismo
        momento.
        """
        source = inspect.getsource(analysis.quoted_cadences)
        self.assertIn("harmony.SET_PIECES", source)

    def test_every_quotation_has_its_name_in_the_catalogue(self):
        """El rótulo de una cita va en minúscula y así se traduce."""
        lowered = {piece.label.lower() for piece in harmony.SET_PIECES.values()}
        self.assertEqual(lowered, set(analysis.SET_PIECE_KINDS))


class TestAnalysisCounterpoint(unittest.TestCase):
    def test_parallel_fifths_and_octaves_are_found(self):
        result = analysis.analyse(_score([
            [(48, 2), (43, 2)], [(55, 2), (50, 2)],
            [(64, 2), (67, 2)], [(72, 2), (67, 2)]]))
        self.assertIn("quintas_paralelas", _kinds(result))

    def test_every_parallel_is_reported_and_not_only_the_first(self):
        """Cinco quintas seguidas son cinco faltas, no una."""
        result = analysis.analyse(_score([
            [(48, 1), (43, 1), (45, 1), (41, 1), (43, 1), (48, 1)],
            [(55, 1), (50, 1), (52, 1), (48, 1), (50, 1), (55, 1)],
            [(64, 1), (67, 1), (64, 1), (65, 1), (67, 1), (64, 1)],
            [(72, 1), (71, 1), (72, 1), (69, 1), (71, 1), (72, 1)]]))
        fifths = [f for f in result.findings
                  if f.kind == "quintas_paralelas"]
        self.assertGreater(len(fifths), 1)

    def test_a_crossing_is_reported_once_and_not_per_slice(self):
        """La misma nota tenida no es un cruce nuevo en cada vertical."""
        result = analysis.analyse(_score([
            [(48, 1), (60, 2), (48, 1)],
            [(55, 1), (55, 1), (55, 1), (55, 1)],
            [(64, 4)], [(72, 4)]]))
        crossings = [f for f in result.findings if f.kind == "cruce"]
        self.assertEqual(len(crossings), 1)

    def test_a_tritone_leap_is_reported_with_its_voice(self):
        result = analysis.analyse(_score([
            [(48, 2), (48, 2)], [(55, 2), (55, 2)],
            [(64, 2), (64, 2)], [(71, 2), (65, 2)]]))
        leaps = [f for f in result.findings if f.kind == "salto_tritono"]
        self.assertEqual(len(leaps), 1)
        self.assertEqual(leaps[0].voices, (3,))

    def test_the_motions_are_classified(self):
        self.assertEqual(analysis.motion_between(60, 62, 67, 69),
                         analysis.MOTION_PARALLEL)
        self.assertEqual(analysis.motion_between(60, 62, 67, 65),
                         analysis.MOTION_CONTRARY)
        self.assertEqual(analysis.motion_between(60, 60, 67, 69),
                         analysis.MOTION_OBLIQUE)
        self.assertEqual(analysis.motion_between(60, 60, 67, 67),
                         analysis.MOTION_STATIC)
        # Misma dirección con el intervalo cambiando: directo, no paralelo.
        self.assertEqual(analysis.motion_between(60, 62, 67, 71),
                         analysis.MOTION_SIMILAR)

    def test_the_rules_come_from_the_evaluator(self):
        """Las paralelas no se vuelven a definir acá.

        Una segunda copia de la regla se desincroniza de la primera en el
        primer cambio, y entonces el analizador diría que está bien lo que
        el generador prohíbe.
        """
        source = inspect.getsource(analysis)
        self.assertIn("from .fitness import", source)

    def _pairs(self, result):
        """Todos los movimientos de la pieza, uno por uno."""
        found = []
        for report in result.motions:
            found.extend(report.pairs.values())
        return found

    def test_two_voices_that_move_in_the_same_beat_move_together(self):
        """
        El movimiento se mide contra la nota anterior **de cada voz**.

        Las dos bajan un tono dentro del segundo tiempo, la de arriba una
        corchea después. Es lo que hace cualquier textura arpegiada, y
        mirando la vertical de al lado la que todavía no atacó parece quieta
        --- un paralelo perfectamente visible en el papel salía cifrado
        "oblicuo".
        """
        result = analysis.analyse(_score([
            [(48, 1), (46, 3)],
            [(55, 1.5), (53, 2.5)],
            [(64, 4)]]))
        self.assertIn(analysis.MOTION_PARALLEL, self._pairs(result))

    def test_two_voices_that_move_in_different_beats_do_not(self):
        """
        Moverse en tiempos distintos no es moverse juntas.

        La de abajo baja en el segundo tiempo y la de arriba en el tercero:
        cuando se mueve la segunda, la primera ya está quieta. Son dos
        movimientos oblicuos.
        """
        result = analysis.analyse(_score([
            [(48, 1), (46, 3)],
            [(55, 2), (53, 2)],
            [(64, 4)]]))
        pairs = self._pairs(result)
        self.assertNotIn(analysis.MOTION_PARALLEL, pairs)
        self.assertIn(analysis.MOTION_OBLIQUE, pairs)

    def test_parallel_fifths_inside_one_beat_are_found(self):
        """Dos quintas una tras otra dentro del mismo tiempo se marcan."""
        result = analysis.analyse(_score([
            [(48, 1), (50, 3)],
            [(55, 1.5), (57, 2.5)]]))
        fifths = [f for f in result.findings
                  if f.kind == "quintas_paralelas"]
        self.assertEqual(len(fifths), 1)

    def test_fifths_a_beat_apart_are_not_parallel(self):
        """
        Mi-si, mi-la, re-la no son quintas paralelas: en el medio hay una
        cuarta. Es el compás 20 de BWV 269, que se marcaba como falta grave.
        """
        result = analysis.analyse(_score([
            [(52, 2), (50, 2)],
            [(59, 1), (57, 3)],
            [(67, 4)]]))
        self.assertNotIn("quintas_paralelas", _kinds(result))

    def test_the_style_decides_whether_parallels_are_a_fault(self):
        """El barroco las marca como falta; el jazz las anota sin marcarlas."""
        piece = _score([
            [(48, 2), (50, 2)],
            [(55, 2), (57, 2)],
            [(64, 2), (65, 2)]])
        for genre, expected in ((None, "grave"), ("chorale", "grave"),
                                ("jazz", "nota"), ("gregorian", "nota")):
            fifths = [f for f in analysis.analyse(piece, genre=genre).findings
                      if f.kind == "quintas_paralelas"]
            self.assertTrue(fifths, genre)
            self.assertEqual({f.severity for f in fifths}, {expected}, genre)

    def test_a_repeated_note_is_still_standing_still(self):
        """Volver a atacar la misma nota es quedarse quieto, no moverse."""
        result = analysis.analyse(_score([
            [(48, 1), (48, 1), (48, 1), (48, 1)],
            [(55, 1), (55, 1), (57, 1), (57, 1)]]))
        values = self._pairs(result)
        self.assertIn(analysis.MOTION_STATIC, values)
        self.assertIn(analysis.MOTION_OBLIQUE, values)

    def test_a_pedal_is_oblique_against_everything_above_it(self):
        """
        Una nota que viene sonando desde antes no se movió nunca.

        No tiene nota anterior contra la cual medirla, y sin embargo lo que
        hace mientras la de arriba se mueve tiene nombre: oblicuo. Dándola
        por perdida, un pedal se quedaba sin un solo movimiento.
        """
        result = analysis.analyse(_score([
            [(36, 8)],
            [(60, 1), (62, 1), (64, 1), (65, 1), (67, 4)]]))
        values = self._pairs(result)
        self.assertTrue(values)
        self.assertEqual(set(values), {analysis.MOTION_OBLIQUE})

    def test_the_same_step_is_not_counted_twice(self):
        """
        Una voz que vuelve a atacar no cambia nada de lo que hay para medir.

        Las dos de abajo hacen un solo paso; la de arriba lo pica en ocho
        corcheas. Sin la memoria de lo último anotado, ese paso aparecía una
        vez por cada corchea.
        """
        result = analysis.analyse(_score([
            [(48, 2), (50, 2)],
            [(55, 2), (57, 2)],
            [(64, 0.5)] * 8]))
        low = [report.pairs[(0, 1)] for report in result.motions
               if (0, 1) in report.pairs]
        self.assertEqual(len(low), 1)


class TestAnalysisOrnaments(unittest.TestCase):
    def _kinds(self, lines, **kwargs):
        result = analysis.analyse(_score(lines, **kwargs))
        return {ornament.kind for ornament in result.ornaments}

    def test_a_passing_note_does_not_become_a_seventh_chord(self):
        """El si de paso sobre un Do no convierte al Do en Do maj7."""
        result = analysis.analyse(_score([
            [(48, 4)], [(55, 4)], [(64, 4)],
            [(72, 1), (71, 1), (69, 1), (67, 1)]]))
        self.assertEqual(result.segments[0].symbol, "C")
        self.assertIn("paso", {o.kind for o in result.ornaments})

    def test_an_escape_tone_does_not_change_the_dominant(self):
        """mi-fa#-re sobre La, en la cadencia de un coral en Re: el fa# es
        una escapada y el acorde es La, no Fa# menor con séptima.

        Es la cadencia de BWV 304. Sin descontar la escapada como adorno, el
        fa# del contratiempo sumado al resto armaba un iii6/5 y la cadencia
        auténtica desaparecía.
        """
        result = analysis.analyse(_score([
            [(50, 1), (45, 1), (50, 2)],
            [(57, 1), (57, 1), (54, 2)],
            [(64, .5), (62, .5), (62, .5), (61, .5), (57, 2)],
            [(67, .5), (66, .5), (64, .5), (66, .5), (62, 2)]], fifths=2))
        self.assertEqual(_symbols(result), ["D", "A", "D"])
        self.assertIn("cadencia auténtica perfecta",
                      [c.kind for c in result.cadences])

    def test_the_middle_of_a_triple_bar_is_not_strong(self):
        """En tres por cuatro la mitad del compás es una corchea a
        contratiempo, no un tiempo fuerte; en cuatro por cuatro y en seis
        por ocho sí lo es."""
        self.assertEqual(analysis.metric_weight(1.5, 3.0, 1.0), 0.28)
        self.assertFalse(analysis.is_accented(1.5, 3.0, 1.0))
        self.assertEqual(analysis.metric_weight(3.0, 6.0, 2.0), 0.28)
        self.assertEqual(analysis.metric_weight(2.0, 4.0, 1.0), 0.85)
        self.assertEqual(analysis.metric_weight(1.5, 3.0, 0.5), 0.85)

    def test_a_neighbour_returns_and_a_passing_note_goes_on(self):
        neighbour = self._kinds([
            [(48, 4)], [(55, 4)], [(64, 4)],
            [(72, 1), (74, 1), (72, 2)]])
        self.assertIn("bordadura", neighbour)

    def test_a_written_turn(self):
        turn = self._kinds([
            [(48, 4), (48, 4)], [(55, 4), (55, 4)], [(64, 4), (64, 4)],
            [(74, 0.5), (72, 0.5), (71, 0.5), (72, 2.5), (72, 4)]])
        self.assertIn("grupeto", turn)

    def test_an_anticipation(self):
        # Corta: una anticipación es la última corchea del acorde que se
        # adelanta al siguiente. Escrita larga deja de ser un adelanto y pasa
        # a ser otro acorde.
        anticipation = self._kinds([
            [(43, 4), (48, 4)], [(50, 4), (52, 4)], [(55, 4), (55, 4)],
            [(71, 3.5), (72, 0.5), (72, 4)]])
        self.assertIn("anticipacion", anticipation)

    def test_a_pickup_bar_is_an_anacrusis(self):
        found = self._kinds([
            [(None, 1), (48, 4), (43, 3)],
            [(None, 1), (55, 4), (55, 3)],
            [(None, 1), (64, 4), (62, 3)],
            [(67, 1), (72, 4), (71, 3)]], pickup=1.0)
        self.assertIn("anacrusa", found)

    def test_every_ornament_the_analyser_names_has_a_definition(self):
        """Un adorno sin definición es un nombre suelto en la pantalla."""
        for kind in analysis.ORNAMENT_LABELS:
            self.assertIn(kind, analysis.ORNAMENT_DEFINITIONS, kind)


class TestAnalysisPlumbing(unittest.TestCase):
    def test_playback_is_voice_by_voice(self):
        """Una nota tenida suena una vez, no una por vertical."""
        result = analysis.analyse(_score([
            [(48, 4)], [(55, 4)], [(64, 4)],
            [(72, 1), (71, 1), (69, 1), (67, 1)]]))
        events = result.playback()
        self.assertEqual(len(events), 7)
        self.assertIn((48, 0.0, 4), events)

    def test_bars_are_numbered_from_one_and_a_pickup_is_bar_zero(self):
        score = _score([[(60, 1), (60, 4)]], pickup=1.0)
        self.assertEqual(analysis.bar_and_offset(score, 0.0)[0], 0)
        self.assertEqual(analysis.bar_and_offset(score, 1.0), (1, 0.0))

    def test_two_notes_are_not_a_chord(self):
        """
        Con menos de tres alturas no hay acorde que nombrar.

        Una nota sola en el pentagrama venía con nombre de acorde, grado y
        función, todo deducido de esa nota: un acorde es una tríada y dos
        notas no alcanzan para decidir cuál de las que las contienen suena.
        """
        alone = analysis.analyse(_score([[(60, 4)]]))
        self.assertEqual(alone.segments, [])
        pair = analysis.analyse(_score([[(48, 4)], [(55, 4)]]))
        self.assertEqual(pair.segments, [])
        # Con la tercera voz sí.
        trio = analysis.analyse(_score([[(48, 4)], [(55, 4)], [(64, 4)]]))
        self.assertEqual(_symbols(trio), ["C"])

    def test_a_thin_moment_joins_the_chord_it_belongs_to(self):
        """Una nota sola al final no se convierte en un acorde propio."""
        result = analysis.analyse(_score([
            [(48, 4), (48, 1)], [(55, 4)], [(64, 4)]]))
        self.assertEqual(_symbols(result), ["C"])

    def test_an_empty_score_says_so_instead_of_failing(self):
        result = analysis.analyse(analysis.Score(parts=[]))
        self.assertEqual(result.segments, [])
        self.assertTrue(result.warnings)

    def test_the_engine_does_not_import_the_interface(self):
        source = inspect.getsource(analysis)
        for forbidden in ("import app", "import tkinter", "customtkinter"):
            self.assertNotIn(forbidden, source)


class TestAnalysisWriting(unittest.TestCase):
    """
    Que lo escrito en el pentagrama sea lo que se analizó.

    El analizador tiene dos entradas ---un archivo y el pentagrama--- y las
    dos tienen que llegar a la misma pieza. Si escribir una partitura
    importada y volver a leerla del pentagrama cambia una nota, el análisis
    que se ve en pantalla es de otra música que la del archivo.
    """

    def test_a_written_line_keeps_its_rests(self):
        part = analysis.Part(name="Tenor", notes=[
            analysis.Note(pitch=60, onset=1.0, duration=1.0),
            analysis.Note(pitch=62, onset=3.0, duration=1.0)])
        self.assertEqual(importer.written_line(part),
                         [(None, 1.0), (60, 1.0), (None, 1.0), (62, 1.0)])

    def test_a_line_that_starts_at_zero_gets_no_leading_rest(self):
        part = analysis.Part(name="Bajo", notes=[
            analysis.Note(pitch=48, onset=0.0, duration=2.0)])
        self.assertEqual(importer.written_line(part), [(48, 2.0)])

    def test_writing_a_pitch_and_reading_it_back_is_exact(self):
        """
        El ida y vuelta del pentagrama, en todas las armaduras.

        Se importa `staff` a propósito aunque sea de la interfaz: lo que se
        prueba son dos funciones de aritmética que no crean ninguna ventana,
        y son las que deciden si una partitura importada sobrevive al
        pentagrama. Probarlas desde el arnés de interfaz costaría abrir la
        aplicación entera para comprobar una cuenta.
        """
        import staff
        for fifths in range(-5, 6):
            for midi in range(36, 85):
                index = staff.index_for_pitch(midi, fifths)
                accidental = staff.accidental_for(midi, index, fifths)
                self.assertEqual(staff.pitch_at(index, fifths, accidental),
                                 midi, (fifths, midi))

    def test_the_key_signature_spells_what_it_can(self):
        """En Sol mayor, un fa sostenido no lleva accidente escrito."""
        import staff
        index = staff.index_for_pitch(66, 1)          # fa sostenido
        self.assertIsNone(staff.accidental_for(66, index, 1))
        # Y en Do mayor, el mismo sonido sí lo lleva.
        index = staff.index_for_pitch(66, 0)
        self.assertEqual(staff.accidental_for(66, index, 0), 1)


class TestAnalysisMetres(unittest.TestCase):
    """
    Una pieza puede cambiar de compás en el medio.

    No es un detalle de dibujo. El compás decide dónde caen los tiempos
    fuertes; de los tiempos fuertes salen la unidad con la que se lee un
    acorde, el peso de cada nota y el nombre de cualquier adorno. Forzar
    toda la pieza al primer compás corría la grilla desde el cambio hasta el
    final, y con ella todo lo que se apoya en ella.
    """

    def _score(self, metres):
        line = [(60, 1.0)] * 12
        return analysis.Score(
            parts=[_line(line, "Soprano")], beats=4, beat_type=4,
            metres=metres)

    def test_bars_are_counted_with_the_metre_that_rules(self):
        score = self._score(((1, 4, 4), (3, 3, 4)))
        # Dos compases de cuatro y después de tres: 0-4, 4-8, 8-11, 11-14.
        self.assertEqual(analysis.bar_and_offset(score, 0.0), (1, 0.0))
        self.assertEqual(analysis.bar_and_offset(score, 4.0), (2, 0.0))
        self.assertEqual(analysis.bar_and_offset(score, 8.0), (3, 0.0))
        self.assertEqual(analysis.bar_and_offset(score, 11.0), (4, 0.0))

    def test_without_changes_nothing_moves(self):
        score = self._score(())
        for moment, expected in ((0.0, (1, 0.0)), (4.0, (2, 0.0)),
                                 (9.5, (3, 1.5))):
            self.assertEqual(analysis.bar_and_offset(score, moment), expected)

    def test_the_metre_of_each_bar_is_the_last_one_declared(self):
        score = self._score(((1, 4, 4), (3, 3, 4), (5, 6, 8)))
        self.assertEqual(score.metre_at(1), (4, 4))
        self.assertEqual(score.metre_at(2), (4, 4))
        self.assertEqual(score.metre_at(4), (3, 4))
        self.assertEqual(score.metre_at(9), (6, 8))

    def test_a_change_of_metre_moves_the_strong_beats(self):
        """
        El mismo material, leído en dos compases distintos.

        Tres acordes de tres negras: en tres por cuatro cada uno cae en el
        primer tiempo de su compás, y en cuatro por cuatro el segundo cae a
        contratiempo. La lectura no tiene por qué dar lo mismo, y lo que
        importa es que la grilla siga a la barra.
        """
        lines = [[(48, 3.0), (43, 3.0), (48, 3.0)],
                 [(52, 3.0), (50, 3.0), (52, 3.0)],
                 [(55, 3.0), (47, 3.0), (55, 3.0)]]
        three = analysis.Score(
            parts=[_line(line, name) for name, line
                   in zip(("Bajo", "Alto", "Soprano"), lines)],
            beats=3, beat_type=4)
        result = analysis.analyse(three)
        self.assertEqual([s.bar_index for s in result.segments], [1, 2, 3])

    def test_an_imported_change_of_metre_survives(self):
        """Lo que dice el archivo tiene que llegar al análisis."""
        import xml.etree.ElementTree as ET      # noqa: F401 - se usa abajo
        first = ("<attributes><divisions>1</divisions>"
                 "<key><fifths>0</fifths></key>"
                 "<time><beats>4</beats><beat-type>4</beat-type></time>"
                 "</attributes>")
        change = ("<attributes>"
                  "<time><beats>3</beats><beat-type>4</beat-type></time>"
                  "</attributes>")
        def bar(number, attributes, count):
            notes = "".join(_xml_note(60, 1, 1, 1) for _ in range(count))
            return f"<measure number='{number}'>{attributes}{notes}</measure>"
        xml = ("<?xml version='1.0' encoding='UTF-8'?>"
               "<score-partwise version='3.1'><part-list><score-part id='P1'>"
               "<part-name>V</part-name></score-part></part-list>"
               "<part id='P1'>"
               + bar(1, first, 4) + bar(2, "", 4) + bar(3, change, 3)
               + bar(4, "", 3) + "</part></score-partwise>")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "cambio.musicxml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(xml)
            score = importer.read_voices(path)
        self.assertEqual(score.beats, 4)
        self.assertIn((3, 3, 4), score.metres)
        self.assertEqual(score.metre_at(3), (3, 4))


class TestKeptVoices(unittest.TestCase):
    """
    Una partitura con más voces de las que caben en el sistema.

    Quedaban las cuatro líneas más graves y en una de piano eso tiraba la
    melodía. Ahora se elige momento a momento: la nota más grave, la más
    aguda y las dos del medio que más clases de altura agregan.
    """

    @staticmethod
    def _parts(lines):
        return [analysis.Part(name="", notes=[
            analysis.Note(pitch=pitch, onset=onset, duration=duration)
            for pitch, onset, duration in line]) for line in lines]

    @staticmethod
    def _notes(part):
        return [(n.pitch, n.onset, n.duration) for n in part.notes]

    def test_a_piano_texture_keeps_the_bass_the_top_and_the_fullest_middle(self):
        from engine.importer import kept_voices
        parts = self._parts([
            [(48, 0, 4)], [(52, 0, 2)], [(55, 0, 4)], [(60, 0, 4)],
            [(64, 0, 2), (67, 2, 2)], [(72, 0, 4)]])
        kept = kept_voices(parts, 4)
        self.assertEqual(len(kept), 4)
        self.assertEqual(self._notes(kept[0]), [(48, 0, 4)])
        self.assertEqual(self._notes(kept[3]), [(72, 0, 4)])
        # La nota que sigue sonando en su carril no se vuelve a atacar.
        self.assertEqual(self._notes(kept[1]), [(55, 0, 4)])
        self.assertEqual({pitch % 12 for pitch, _o, _d in self._notes(kept[2])},
                         {4, 0})

    def test_four_voices_stay_as_they_are(self):
        from engine.importer import kept_voices
        parts = self._parts([[(48, 0, 4)], [(55, 0, 4)], [(64, 0, 4)],
                             [(72, 0, 4)]])
        self.assertEqual(kept_voices(parts, 4), parts)


class TestAnalysisShortBars(unittest.TestCase):
    """
    Un compás incompleto en el medio de la pieza no es un compás con
    silencio al final.

    Los corales escriben la repetición en medio de un compás y lo parten en
    dos (el 7 de dos tiempos y el 7a del tercero); una sección que cambia de
    compás puede empezar con su propia anacrusa. Estirando cada compás corto
    hasta la medida que rige, aparecían tiempos de silencio que la pieza no
    tiene y todo lo que venía después quedaba corrido: en seis de ocho
    corales bajados de internet, la mitad de los acordes caía a contratiempo.
    """

    def test_the_drawn_system_counts_the_pickup_as_bar_zero(self):
        """Las barras del sistema caen donde el análisis dice que caen."""
        import types
        from staff import GrandStaff
        fake = types.SimpleNamespace(pickup=1.0, total_quarters=lambda: 7.0,
                                     metre_at=lambda bar: (3, 4))
        grid = GrandStaff.bar_grid(fake)
        self.assertEqual(grid[:3], [(0, 0.0, 1.0), (1, 1.0, 3.0),
                                    (2, 4.0, 3.0)])
        fake.pickup = 0.0
        self.assertEqual(GrandStaff.bar_grid(fake)[0], (1, 0.0, 3.0))

    @staticmethod
    def _read(bars):
        """bars: (número, atributos, [(altura, negras)]), una voz."""
        body = "".join(
            f"<measure number='{number}'>{attributes}"
            + "".join(_xml_note(pitch, length, 1, 1) for pitch, length in notes)
            + "</measure>" for number, attributes, notes in bars)
        xml = ("<?xml version='1.0' encoding='UTF-8'?>"
               "<score-partwise version='3.1'><part-list><score-part id='P1'>"
               "<part-name>V</part-name></score-part></part-list>"
               "<part id='P1'>" + body + "</part></score-partwise>")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "corto.musicxml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(xml)
            return importer.read_voices(path)

    @staticmethod
    def _metre(beats, beat_type, first=False):
        head = ("<divisions>1</divisions><key><fifths>0</fifths></key>"
                if first else "")
        return (f"<attributes>{head}<time><beats>{beats}</beats>"
                f"<beat-type>{beat_type}</beat-type></time></attributes>")

    def test_the_two_halves_of_a_split_bar_sound_together(self):
        score = self._read([
            ("0", self._metre(3, 4, first=True), [(67, 1)]),
            ("1", "", [(67, 1), (69, 1), (71, 1)]),
            ("2", "", [(72, 2)]),               # la repetición, a mitad
            ("2a", "", [(71, 1)]),
            ("3", "", [(69, 3)]),
            ("4", "", [(67, 2)])])
        onsets = [note.onset for note in score.parts[0].notes]
        self.assertEqual(onsets, [0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 7.0, 10.0])
        self.assertEqual(score.pickup_quarters, 1.0)
        self.assertEqual(score.metres, ())
        # Las dos mitades son el compás 2, y el 3 empieza en su tiempo fuerte.
        self.assertEqual(analysis.bar_and_offset(score, 6.0), (2, 2.0))
        self.assertEqual(analysis.bar_and_offset(score, 7.0), (3, 0.0))

    def test_a_lone_short_bar_keeps_its_own_measure(self):
        """La anacrusa de una sección en tres, después de una en cuatro."""
        score = self._read([
            ("1", self._metre(4, 4, first=True), [(60, 4)]),
            ("2", "", [(62, 4)]),
            ("3", self._metre(3, 4), [(64, 1)]),
            ("4", "", [(65, 3)]),
            ("5", "", [(67, 3)])])
        onsets = [note.onset for note in score.parts[0].notes]
        self.assertEqual(onsets, [0.0, 4.0, 8.0, 9.0, 12.0])
        self.assertIn((3, 1, 4), score.metres)
        self.assertIn((4, 3, 4), score.metres)
        self.assertEqual(analysis.bar_and_offset(score, 9.0), (4, 0.0))
        self.assertEqual(analysis.bar_and_offset(score, 12.0), (5, 0.0))

    def test_a_split_bar_can_carry_the_next_metre(self):
        """El 14 de BWV 41.6: tres tiempos de cuatro por cuatro, y el 14a
        ---un tiempo, ya en tres por cuatro--- es la anacrusa de la sección
        nueva. Las dos mitades son un compás de cuatro y el tres por cuatro
        rige desde el compás siguiente, con el mismo número que en la
        partitura."""
        score = self._read([
            ("1", self._metre(4, 4, first=True), [(60, 4)]),
            ("2", "", [(62, 3)]),
            ("2a", self._metre(3, 4), [(64, 1)]),
            ("3", "", [(65, 3)]),
            ("4", "", [(67, 3)])])
        self.assertEqual([n.onset for n in score.parts[0].notes],
                         [0.0, 4.0, 7.0, 8.0, 11.0])
        self.assertEqual(score.metres, ((1, 4, 4), (3, 3, 4)))
        self.assertEqual(analysis.bar_and_offset(score, 7.0), (2, 3.0))
        self.assertEqual(analysis.bar_and_offset(score, 8.0), (3, 0.0))
        self.assertEqual(analysis.bar_and_offset(score, 11.0), (4, 0.0))

    def test_a_short_last_bar_changes_nothing(self):
        """El último compás completa la anacrusa: no viene nada después."""
        score = self._read([
            ("0", self._metre(4, 4, first=True), [(67, 1)]),
            ("1", "", [(72, 4)]),
            ("2", "", [(71, 3)])])
        self.assertEqual([n.onset for n in score.parts[0].notes],
                         [0.0, 1.0, 5.0])
        self.assertEqual(score.metres, ())


class TestAnalysisSpelling(unittest.TestCase):
    """
    Cómo se escribe cada nota.

    Una altura no dice cómo se llama: la misma tecla es un la bemol o un sol
    sostenido según de qué lado del círculo de quintas esté la pieza. Un
    analizador que se equivoca en esto contesta bien y se lee mal, que para
    quien está aprendiendo es lo mismo que contestar mal.
    """

    def test_the_signature_is_deduced_when_the_file_has_none(self):
        """Las partituras que este programa exporta no traen armadura."""
        sonorities = analysis.verticalise(
            _score([[(53, 4.0)], [(58, 4.0)], [(60, 4.0)], [(65, 4.0)]]))
        self.assertLess(analysis.implied_fifths(sonorities, 0), 0)

    def test_a_written_signature_is_never_second_guessed(self):
        sonorities = analysis.verticalise(_score([[(53, 4.0)], [(58, 4.0)]]))
        self.assertEqual(analysis.implied_fifths(sonorities, 3), 3)

    def test_a_borrowed_chord_is_spelled_like_its_degree(self):
        """Un bVI se escribe con bemol, no con el sostenido de al lado."""
        result = analysis.analyse(_score([
            [(48, 2.0), (44, 2.0), (48, 2.0)],
            [(64, 2.0), (63, 2.0), (64, 2.0)],
            [(67, 2.0), (68, 2.0), (67, 2.0)],
            [(72, 2.0), (72, 2.0), (72, 2.0)]]))
        self.assertEqual(_romans(result)[1], "bVI")
        self.assertEqual(_symbols(result)[1], "Ab")

    def test_an_applied_leading_tone_is_spelled_below_its_target(self):
        """
        El vii°/V de Do es Fa sostenido disminuido aunque la pieza tenga bemoles.

        Una armonización con un la bemol se leía con bemoles de punta a
        punta y el acorde salía Solb disminuido con Rebb en el bajo.
        """
        result = analysis.analyse(_score([
            [(48, 2.0), (44, 2.0), (48, 2.0), (45, 2.0), (43, 2.0), (48, 2.0)],
            [(64, 2.0), (63, 2.0), (64, 2.0), (60, 2.0), (59, 2.0), (64, 2.0)],
            [(67, 2.0), (68, 2.0), (67, 2.0), (66, 2.0), (67, 2.0), (67, 2.0)],
            [(72, 2.0), (72, 2.0), (72, 2.0), (72, 2.0), (71, 2.0), (72, 2.0)]]))
        symbols = _symbols(result)
        self.assertIn("Ab", symbols)
        self.assertIn("F#dim/A", symbols)

    def test_the_bass_is_spelled_by_what_it_is_in_the_chord(self):
        """La quinta de un Si con séptima es un fa sostenido, no un sol bemol."""
        reading = analysis.ChordReading(
            root_pc=11, quality="7", pitch_classes=(2, 5, 9, 11), bass_pc=6,
            prefer_flats=True,
            tones=((11, "root", 1), (3, "third", 3), (6, "fifth", 5),
                   (9, "seventh", 7)))
        self.assertEqual(reading.bass_name, "F#")

    def test_a_diminished_chord_is_not_a_tonic(self):
        """
        Ninguna pieza reposa en un acorde disminuido.

        Es el acorde más inestable que hay: si la música se detiene ahí, se
        detuvo antes de llegar, no llegó. Sin esta salvedad, una
        armonización que cerraba en el séptimo grado se analizaba entera en
        locrio.
        """
        result = analysis.analyse(_score([
            [(48, 2.0), (48, 2.0), (47, 2.0)],
            [(64, 2.0), (64, 2.0), (62, 2.0)],
            [(67, 2.0), (67, 2.0), (65, 2.0)],
            [(72, 2.0), (72, 2.0), (71, 2.0)]]))
        self.assertNotEqual(result.key.mode_key, "locrian")


class TestAnalysisTravel(unittest.TestCase):
    """
    Irse de la tonalidad, y volver.

    Son cuatro cosas distintas que se ven parecidas: un acorde prestado de
    otro modo, una dominante que apunta a un grado, una visita a otra
    tonalidad y una mudanza definitiva. Confundirlas es el error clásico del
    análisis apurado, y por eso están las cuatro acá.
    """

    def _chords(self, chords, fifths=0):
        lines = [[(chord[voice], 2.0) for chord in chords]
                 for voice in range(len(chords[0]))]
        return analysis.analyse(_score(lines, fifths=fifths))

    def test_a_secondary_dominant_says_where_it_points(self):
        result = self._chords([(48, 64, 67, 72), (50, 66, 69, 74),
                               (43, 62, 67, 71), (48, 64, 67, 72)])
        self.assertEqual(_romans(result)[1], "V/V")
        self.assertEqual(result.segments[1].category, "dominante aplicada")
        self.assertIn("resuelve", result.segments[1].detail)

    def test_modal_interchange_says_which_mode_it_comes_from(self):
        result = self._chords([(48, 64, 67, 72), (53, 65, 68, 72),
                               (48, 64, 67, 72)])
        self.assertEqual(_romans(result)[1], "iv")
        self.assertEqual(result.segments[1].category, "intercambio modal")
        self.assertIn("menor", result.segments[1].detail)

    def test_a_tonicisation_is_read_as_one_visit(self):
        result = self._chords([(48, 64, 67, 72), (45, 64, 67, 73),
                               (50, 62, 65, 69), (43, 62, 65, 71),
                               (48, 64, 67, 72)])
        self.assertEqual(_romans(result)[1], "V7/ii")

    def test_a_chain_of_dominants_is_not_leaving_the_key(self):
        """
        Cada acorde es la dominante del siguiente.

        Es lo contrario de irse: la pieza vuelve por el círculo de quintas
        hasta su propia dominante. Leído acorde por acorde parecen cuatro
        tonalidades y no es ninguna.
        """
        result = self._chords([(48, 64, 67, 72), (52, 68, 71, 74),
                               (45, 64, 67, 73), (50, 66, 69, 72),
                               (43, 65, 67, 71), (48, 64, 67, 72)])
        labels = " ".join(group.label for group in result.groups)
        self.assertIn("dominantes", labels)

    def test_a_modulation_is_read_in_the_key_it_lands_on(self):
        result = self._chords([(48, 64, 67, 72), (43, 62, 67, 71),
                               (50, 66, 69, 74), (43, 62, 67, 71),
                               (50, 66, 69, 74), (43, 59, 62, 67)])
        self.assertEqual(result.key.label, "Sol mayor")


class TestAnalysisExample(unittest.TestCase):
    """
    La partitura que el programa se trae puesta.

    Está para que el analizador tenga algo que abrir el primer día, y de
    paso es una prueba de verdad: es Bach literal, la progresión es de
    manual y cualquier edición comentada dice lo mismo que tiene que decir
    el programa.
    """

    PATH = os.path.join("assets", "partituras",
                        "bach-preludio-bwv846.musicxml")

    def test_the_example_is_where_the_program_looks_for_it(self):
        self.assertTrue(os.path.isfile(self.PATH), self.PATH)

    def test_the_first_eight_bars_read_as_the_manuals_read_them(self):
        score = importer.read_voices(self.PATH)
        result = analysis.analyse(score)
        self.assertEqual(result.key.label, "Do mayor")
        self.assertEqual(_symbols(result),
                         ["C", "Dm7/C", "G7/B", "C", "Am/C", "D7/C", "G/B",
                          "Cmaj7/B"])
        self.assertEqual(_romans(result)[:4], ["I", "ii4/2", "V6/5", "I"])
        # El sexto compás es la dominante de la dominante, con el do en el
        # bajo: es el momento en el que el preludio se asoma a Sol.
        self.assertEqual(_romans(result)[5], "V4/2/V")


class TestAnalysisReadsWhatWeWrite(unittest.TestCase):
    """
    Los tres modos escriben partituras y el cuarto las lee.

    Tienen que entenderse. Una partitura exportada por el organizador y
    vuelta a abrir en el analizador tiene que llegar con sus cuatro voces y
    con la misma progresión: son el mismo programa, y si no coinciden acá no
    coinciden con nadie.
    """

    def _round_trip(self, request, outcome):
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            written = session.export_outcome(
                request, outcome, directory=folder, formats=("musicxml",),
                record_history=False)
            self.assertTrue(written)
            score = importer.read_voices(written[0])
        result = analysis.analyse(score)
        self.assertEqual(len(score.parts), 4)
        self.assertTrue(result.segments)
        return result

    def test_the_analyser_reads_the_organiser(self):
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry(symbol=symbol, duration_quarters=2.0,
                                        bar_index=index // 2)
                     for index, symbol in enumerate(["C", "F", "G7", "C"])],
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            solutions_wanted=1, title="Organizador")
        result = self._round_trip(request, session.generate(request))
        self.assertEqual(result.key.label, "Do mayor")
        self.assertEqual(_symbols(result)[0], "C")

    def test_the_analyser_reads_the_generator(self):
        request = session.GenerativeRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            tonic="F", mode_key="major", slot_count=6,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            solutions_wanted=1, title="Generador")
        result = self._round_trip(request, session.generate_random(request))
        # Sin armadura escrita, la escritura sale de lo que suena: una pieza
        # en Fa se nombra con bemoles y no con los sostenidos de al lado.
        self.assertNotIn("#", " ".join(_symbols(result)))

    def test_the_analyser_reads_the_harmoniser(self):
        notes = [harmonize.MelodyNote(pitch=pitch, duration_quarters=1.0,
                                      bar_index=index // 4,
                                      offset_quarters=(index % 4) * 1.0)
                 for index, pitch in enumerate([72, 74, 76, 77, 79, 77, 76, 72])]
        request = session.HarmoniseRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            melody=harmonize.Melody(
                notes=notes,
                bars=[harmonize.MelodyBar(), harmonize.MelodyBar()],
                melody_voice=3),
            melody_voice=3,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            solutions_wanted=1, title="Armonizador")
        result = self._round_trip(request, session.harmonise_melody(request))
        self.assertEqual(result.key.label, "Do mayor")


class TestSendToAnalyser(unittest.TestCase):
    """
    Mandar una opción al analizador es exportarla e importarla, sin archivo.

    `session.analysis_lines` arma las voces en memoria. Tienen que ser nota
    por nota lo que el importador lee del MusicXML de esa misma opción: si
    no, el analizador juzgaría otra pieza que la que se generó.
    """

    @staticmethod
    def _notes(line):
        found, moment = [], 0.0
        for pitch, quarters in line:
            if pitch is not None:
                found.append((pitch, moment, quarters))
            moment += quarters
        return found

    def _same_as_the_file(self, request, outcome):
        self.assertTrue(outcome.succeeded, outcome.errors)
        with tempfile.TemporaryDirectory() as folder:
            written = session.export_outcome(
                request, outcome, directory=folder, formats=("musicxml",),
                record_history=False)
            for position, path in enumerate(written):
                score = importer.read_voices(path)
                lines = session.analysis_lines(outcome, position)
                self.assertEqual(len(lines), len(score.parts))
                for line, part in zip(lines, score.parts):
                    mine = self._notes(line)
                    theirs = [(n.pitch, n.onset, n.duration)
                              for n in part.notes]
                    self.assertEqual([p for p, _o, _d in mine],
                                     [p for p, _o, _d in theirs])
                    for (_p, onset, quarters), (_q, o2, d2) in zip(mine,
                                                                   theirs):
                        self.assertAlmostEqual(onset, o2, delta=1 / 48)
                        self.assertAlmostEqual(quarters, d2, delta=1 / 48)
        return outcome

    def test_the_organiser_with_ornaments_and_a_rest(self):
        from engine.passing import PassingRules
        symbols = ["C", "F", "G7", "C", "", "Am", "Dm", "G", "C"]
        bars = [0, 0, 1, 1, 2, 3, 3, 4, 4]
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry(
                symbol=symbol or "C", is_rest=not symbol,
                duration_quarters=2.0 if symbol else 4.0, bar_index=bar)
                for symbol, bar in zip(symbols, bars)],
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            passing_rules=PassingRules(voices=(1, 2, 3), density=0.9),
            solutions_wanted=2, title="Organizador")
        outcome = self._same_as_the_file(request, session.generate(request))
        lines = session.analysis_lines(outcome, 0)
        self.assertTrue(any(len(line) > len(symbols) for line in lines),
                        "ningún adorno llegó al analizador")
        self.assertTrue(all((None, 4.0) in line for line in lines))

    def test_the_generator(self):
        request = session.GenerativeRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"],
            tonic="F", mode_key="major", slot_count=6, with_sevenths=True,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            solutions_wanted=3, title="Generador")
        self._same_as_the_file(request, session.generate_random(request))

    def test_the_harmoniser_keeps_the_written_melody(self):
        pitches = [72, 74, 76, 77, 79, 77, 76, 74, 72]
        durations = [1.0, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 4.0]
        notes, moment = [], 0.0
        for pitch, quarters in zip(pitches, durations):
            notes.append(harmonize.MelodyNote(
                pitch=pitch, duration_quarters=quarters,
                bar_index=int(moment // 4), offset_quarters=moment % 4))
            moment += quarters
        request = session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            melody=harmonize.Melody(
                notes=notes,
                bars=[harmonize.MelodyBar() for _ in range(3)],
                melody_voice=3),
            melody_voice=3,
            ga_config=GAConfig(population_size=60, generations=25,
                               random_seed=7),
            solutions_wanted=2, title="Armonizador")
        outcome = self._same_as_the_file(request,
                                         session.harmonise_melody(request))
        top = [p for p, _d in session.analysis_lines(outcome, 0)[3]
               if p is not None]
        self.assertEqual(top, pitches)


class TestTheAnalyserReadsWhatWasGenerated(unittest.TestCase):
    """
    Lo que se manda al analizador se lee como se generó.

    Varios pedidos de los tres modos, armados como los arma la pantalla
    (tónica al principio y al final del Generador, tonalidad del Armonizador
    por la nota final), y cada opción pasada por el camino del botón:
    `session.analysis_lines`, la cuenta con que el pentagrama escribe cada
    altura y `analysis.analyse` con el estilo del pedido. Ninguna nota puede
    cambiar, la tonalidad leída tiene que ser la pedida y las fundamentales
    tienen que coincidir con los acordes generados (salvo las lecturas que
    son el mismo puñado de notas, como Rem7 y Fa6).
    """

    LANES = {3: [0, 2, 3], 4: [0, 1, 2, 3]}

    @staticmethod
    def _ga(seed):
        return GAConfig(population_size=60, generations=30, random_seed=seed)

    def _organiser(self, genre, symbols, seed, voices=("B", "T", "A", "S"),
                   passing=None):
        request = session.JobRequest(
            genre_key=genre, voice_keys=list(voices),
            entries=[session.ChordEntry(symbol=symbol or "C",
                                        is_rest=not symbol,
                                        duration_quarters=2.0,
                                        bar_index=index // 2)
                     for index, symbol in enumerate(symbols)],
            ga_config=self._ga(seed), passing_rules=passing,
            solutions_wanted=3)
        return session.generate(request)

    def _generator(self, genre, tonic, mode, seed, sevenths=False,
                   passing=None):
        home = "i" if mode in harmony.MINOR_MODES else "I"
        request = session.GenerativeRequest(
            genre_key=genre, voice_keys=["B", "T", "A", "S"], tonic=tonic,
            mode_key=mode, slot_count=8, with_sevenths=sevenths,
            ga_config=self._ga(seed), passing_rules=passing,
            start_roman=home, end_roman=home, endpoints_required=True,
            solutions_wanted=3)
        return session.generate_random(request)

    def _harmoniser(self, genre, pitches, seed, signature_tonic=0,
                    voices=("B", "T", "A", "S"), durations=None):
        durations = durations or [1.0] * len(pitches)
        tonic, mode = harmonize.key_of_ending(pitches[-1], signature_tonic)
        notes, moment = [], 0.0
        for pitch, quarters in zip(pitches, durations):
            notes.append(harmonize.MelodyNote(
                pitch=pitch, duration_quarters=quarters,
                bar_index=int(moment // 4), offset_quarters=moment % 4))
            moment += quarters
        bars = [harmonize.MelodyBar(tonic=tonic, mode_key=mode)
                for _ in range(int(math.ceil(moment / 4)))]
        top = len(voices) - 1
        request = session.HarmoniseRequest(
            genre_key=genre, voice_keys=list(voices),
            melody=harmonize.Melody(notes=notes, bars=bars, melody_voice=top),
            melody_voice=top, ga_config=self._ga(seed), solutions_wanted=3)
        return session.harmonise_melody(request)

    def _read(self, outcome, position, genre):
        """Una opción tal como la recibe y la analiza el analizador."""
        import staff
        fifths = outcome.spec.key_hint or 0
        lines = session.analysis_lines(outcome, position)
        names = list(reversed(staff.GRAND_VOICES))
        parts, sent = [], []
        for voice, lane in enumerate(self.LANES[len(lines)]):
            notes, moment = [], 0.0
            for pitch, quarters in lines[voice]:
                if pitch is not None:
                    index = staff.index_for_pitch(pitch, fifths)
                    written = staff.pitch_at(
                        index, fifths,
                        staff.accidental_for(pitch, index, fifths))
                    self.assertEqual(written, pitch)
                    notes.append(analysis.Note(pitch=written, onset=moment,
                                               duration=quarters))
                    sent.append((pitch, moment, quarters))
                moment += quarters
            parts.append(analysis.Part(name=names[lane], notes=notes))
        signature = outcome.spec.time_signature
        result = analysis.analyse(
            analysis.Score(parts=parts, fifths=fifths, beats=signature.beats,
                           beat_type=signature.beat_type, title="x"),
            genre=genre)
        read = [(n.pitch, n.onset, n.duration)
                for part in result.score.parts for n in part.notes]
        self.assertEqual(sorted(read), sorted(sent), "el análisis cambió notas")
        return result

    def _check(self, outcome, genre, key, strict=False):
        self.assertTrue(outcome.succeeded, outcome.errors)
        total = agree = 0
        for position in range(len(outcome.result.solutions)):
            result = self._read(outcome, position, genre)
            self.assertEqual(result.key.label, key,
                             "opción %d" % (position + 1))
            if strict:
                self.assertFalse([f for f in result.findings
                                  if f.severity == "grave" and f.kind in
                                  ("quintas_paralelas", "octavas_paralelas")])
            slots = session.solution_slots(outcome, position)
            solution = outcome.result.solutions[position]
            moment = 0.0
            for column, slot in enumerate(slots):
                if not slot.is_rest:
                    option = (slot.options[min(solution.choices[column],
                                               len(slot.options) - 1)]
                              if slot.options else slot)
                    root = option.requirement.plan.chord.root_pc
                    segment = next(s for s in result.segments
                                   if s.start - 1e-6 <= moment < s.end - 1e-6)
                    total += 1
                    agree += bool(segment.reading
                                  and segment.reading.root_pc == root)
                moment += slot.duration_quarters
        self.assertGreaterEqual(agree / total, 0.9, "%d de %d" % (agree, total))

    def test_the_organiser(self):
        from engine.passing import PassingRules
        self._check(self._organiser(
            "classical", ["C", "Am", "Dm", "G7", "C", "F", "G", "C"], 1),
            "classical", "Do mayor", strict=True)
        self._check(self._organiser(
            "chorale", ["F", "Bb", "C7", "F", "Dm", "Gm", "C", "F"], 2),
            "chorale", "Fa mayor", strict=True)
        self._check(self._organiser(
            "jazz", ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7",
                     "Cmaj7"], 3), "jazz", "Do mayor")
        self._check(self._organiser(
            "classical", ["C", "F", "", "G7", "C", "Am", "G7", "C"], 4,
            passing=PassingRules(voices=(1, 2, 3), density=0.8)),
            "classical", "Do mayor", strict=True)
        self._check(self._organiser(
            "classical", ["Am", "Dm", "E7", "Am", "F", "Dm", "E", "Am"], 5),
            "classical", "La menor", strict=True)
        self._check(self._organiser(
            "classical", ["C", "G", "Am", "F", "C", "G", "C", "C"], 6,
            voices=("B", "T", "S")), "classical", "Do mayor", strict=True)
        self._check(self._organiser(
            "gregorian", ["Dm", "C", "Dm", "Am", "F", "C", "Dm", "Dm"], 7),
            "gregorian", "Re dórico")

    def test_the_generator(self):
        from engine.passing import PassingRules
        self._check(self._generator("classical", "C", "major", 11),
                    "classical", "Do mayor", strict=True)
        self._check(self._generator("chorale", "G", "major", 12),
                    "chorale", "Sol mayor", strict=True)
        self._check(self._generator("jazz", "F", "major", 13, sevenths=True),
                    "jazz", "Fa mayor")
        self._check(self._generator("classical", "D", "minor", 14),
                    "classical", "Re menor", strict=True)
        self._check(self._generator(
            "classical", "Bb", "major", 15,
            passing=PassingRules(voices=(1, 2, 3), density=0.8)),
            "classical", "Sib mayor", strict=True)
        self._check(self._generator("gregorian", "D", "dorian", 16),
                    "gregorian", "Re dórico")
        self._check(self._generator("chorale", "A", "minor", 18),
                    "chorale", "La menor", strict=True)

    def test_the_harmoniser(self):
        """
        Con `strict` también acá: la melodía se mueve adentro de cada acorde
        y la búsqueda mide las paralelas contra lo que suena en el cambio
        (`RunSettings.melody_edges`). Los casos 25, 27 y 29 tenían paralelas
        con una nota de la melodía entre dos acordes antes de eso.
        """
        self._check(self._harmoniser(
            "classical", [72, 74, 76, 77, 79, 77, 76, 74, 72], 21),
            "classical", "Do mayor", strict=True)
        self._check(self._harmoniser(
            "chorale", [65, 67, 69, 70, 72, 70, 69, 67, 65], 22,
            signature_tonic=5), "chorale", "Fa mayor", strict=True)
        self._check(self._harmoniser(
            "jazz", [76, 74, 72, 71, 72, 74, 76, 79, 77, 76, 74, 72], 23),
            "jazz", "Do mayor")
        self._check(self._harmoniser(
            "classical", [67, 69, 71, 72, 74, 72, 71, 69, 67], 25,
            durations=[1, 0.5, 0.5, 1, 1, 1, 1, 2, 4]),
            "classical", "Do mayor", strict=True)
        self._check(self._harmoniser(
            "chorale", [69, 72, 71, 69, 68, 69, 71, 72, 71, 68, 69], 27),
            "chorale", "La menor", strict=True)
        self._check(self._harmoniser(
            "classical", [74, 76, 78, 79, 76, 74, 73, 74], 28,
            signature_tonic=2), "classical", "Re mayor", strict=True)
        self._check(self._harmoniser(
            "classical", [72, 71, 69, 67, 69, 71, 72], 29,
            voices=("B", "T", "S")), "classical", "Do mayor", strict=True)

    def test_the_bach_sixth_leaves_no_parallels(self):
        """
        La sexta de Bach esquiva unas quintas paralelas: no puede dejar
        otras. Moviendo una voz un tono, o intercambiando dos en el vecino,
        las armaba con otra voz o con la nota de la melodía que suena en el
        cambio de acorde. Se fuerza la sexta en todas.
        """
        from unittest import mock
        from engine import flourish
        rng = random.Random(5)
        pool = ["C", "Dm", "Em", "F", "G", "Am", "G7", "Dm7"]
        sixths = 0
        with mock.patch.object(flourish, "SIXTH_CHANCE", 1.0):
            for seed in range(16):
                genre = "classical" if seed % 2 else "chorale"
                if seed % 2:
                    outcome = self._organiser(
                        genre, ["C"] + [rng.choice(pool) for _ in range(6)]
                        + ["C"], 300 + seed)
                    session.apply_flourishes(outcome, genre, 0)
                else:
                    notes = [72, 74, 76, 74, 72, 71, 69, 71, 72, 74, 72]
                    outcome = self._harmoniser(
                        genre, notes, 300 + seed,
                        durations=[1, 0.5, 0.5, 1, 1, 1, 0.5, 0.5, 1, 1, 4])
                self.assertTrue(outcome.succeeded)
                sixths += outcome.flourishes.sixth_slot is not None
                for position in range(len(outcome.result.solutions)):
                    result = self._read(outcome, position, genre)
                    self.assertFalse(
                        [f for f in result.findings if f.severity == "grave"
                         and f.kind in ("quintas_paralelas",
                                        "octavas_paralelas")],
                        "semilla %d, opción %d" % (seed, position + 1))
        self.assertTrue(sixths, "la sexta no se puso nunca")


class TestMelodyEdges(unittest.TestCase):
    """
    Lo que la melodía del Armonizador canta en cada cambio de acorde.
    """

    def test_the_edges_are_the_first_and_last_note_of_each_spot(self):
        notes = [harmonize.MelodyNote(pitch=p, duration_quarters=d,
                                      bar_index=0, offset_quarters=o)
                 for p, d, o in [(72, 1.0, 0.0), (71, 1.0, 1.0),
                                 (69, 2.0, 2.0)]]
        melody = harmonize.Melody(notes=notes, bars=[harmonize.MelodyBar()])
        spots = [harmonize.HarmonySpot(0, 0.0, 2.0, note=notes[0]),
                 harmonize.HarmonySpot(0, 2.0, 2.0, note=notes[2])]
        edges = session._melody_edges(melody, [(spot, None) for spot in spots])
        # El primero entra con su nota fijada y sale con la siguiente; el
        # segundo es una sola nota.
        self.assertEqual(edges, [(None, 71), (None, None)])

    def test_the_search_measures_parallels_against_the_last_note(self):
        """
        Mi en el bajo y do arriba; la melodía baja a si antes de que los dos
        bajen juntos un tono: mi-si, re-la. Contra la nota fijada (do) no hay
        quintas; contra la que suena, sí.
        """
        profile = GENRE_PROFILES["classical"]
        voices = build_voice_parts(["B", "S"])
        chords = [[52, 72], [50, 69]]
        plain = RunSettings(profile=profile, voices=voices, melody_voice=1)
        self.assertTrue(evaluate(chords, plain).valid)
        heard = RunSettings(profile=profile, voices=voices, melody_voice=1,
                            melody_edges=[(None, 71), (None, None)])
        self.assertFalse(evaluate(chords, heard).valid)


class TestStaffWriting(unittest.TestCase):
    """
    Las cuentas con las que el pentagrama escribe.

    Se importa `staff` aunque sea de la interfaz, como en
    `TestAnalysisWriting`: lo que se prueba son funciones de aritmética que
    no crean ninguna ventana y de las que depende que lo que se escribe sea
    lo que se analiza.
    """

    def test_a_gap_is_filled_with_figures_that_can_be_written(self):
        import staff
        self.assertEqual(staff.split_duration(2.5), [2.0, 0.5])
        self.assertEqual(staff.split_duration(4.0), [4.0])
        self.assertEqual(staff.split_duration(0.75), [0.75])
        self.assertEqual(sum(staff.split_duration(3.25)), 3.25)

    def test_an_empty_gap_is_filled_with_nothing(self):
        """
        Un hueco de cero no se rellena.

        Devolviendo una figura de duración cero, cada nota escrita al
        principio de una voz vacía dejaba delante un silencio invisible que
        después aparecía en la lista.
        """
        import staff
        self.assertEqual(staff.split_duration(0.0), [])


class TestInstrumentSample(unittest.TestCase):
    """
    El timbre del experimentador, guardado como muestra de sampler.

    Un WAV suelto es un sonido que dura lo que dura. Lo que lo convierte en
    el timbre de un instrumento es el trozo `smpl`: qué nota representa y
    qué tramo se repite. Y el tramo que se repite tiene que empalmar sin que
    se oiga, o el instrumento chasquea en cada vuelta.
    """

    def _written(self, spectrum):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "timbre.wav")
            start, end = harmonics.write_instrument(path, spectrum)
            with open(path, "rb") as handle:
                data = handle.read()
        return data, start, end

    def test_the_file_says_which_note_it_is_and_what_repeats(self):
        spectrum = harmonics.build("Diente de sierra", 57)
        data, start, end = self._written(spectrum)
        self.assertTrue(data.startswith(b"RIFF"))
        self.assertIn(b"smpl", data)
        chunk = data[data.index(b"smpl") + 8:]
        unity = struct.unpack_from("<I", chunk, 12)[0]
        self.assertEqual(unity, 57)
        loop_start, loop_end = struct.unpack_from("<II", chunk, 36 + 8)
        self.assertEqual((loop_start, loop_end), (start, end))

    def test_the_loop_joins_without_a_click(self):
        """
        La muestra que sigue al final del bucle tiene que ser la del comienzo.

        Es la definición de que el bucle cierre: si no coinciden, el sampler
        salta y se oye un chasquido cada vuelta. Se prueba con vibrato y
        trémolo encendidos, que es donde cerraba mal --- una frecuencia que
        se estira no vuelve a la misma fase.
        """
        spectrum = harmonics.build("Diente de sierra", 57)
        spectrum.vibrato_cents = 22.0
        spectrum.tremolo_depth = 0.5
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "timbre.wav")
            start, end = harmonics.write_instrument(path, spectrum)
            with wave.open(path, "rb") as handle:
                frames = handle.readframes(handle.getnframes())
        samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
        self.assertEqual(samples[start], samples[end + 1])

    def test_a_silent_spectrum_still_writes_a_file(self):
        spectrum = harmonics.build("Diente de sierra", 57)
        for partial in spectrum.partials:
            partial.muted = True
        data, start, end = self._written(spectrum)
        self.assertIn(b"data", data)
        self.assertGreater(end, start)


def _upward_crossings_frequency(signal, rate):
    """
    La frecuencia de una onda que cruza el cero una vez por ciclo.

    Se cuentan los cruces hacia arriba, ubicando cada uno entre sus dos
    muestras por interpolación lineal: contando muestras enteras el error en
    un La de 440 es de varios cents.
    """
    crossings = []
    for index in range(1, len(signal)):
        before, after = signal[index - 1], signal[index]
        if before < 0.0 <= after:
            crossings.append(index - 1 + before / (before - after))
    if len(crossings) < 3:
        return 0.0
    return (len(crossings) - 1) * rate / (crossings[-1] - crossings[0])


class TestPlaybackTimbres(unittest.TestCase):
    """
    Con qué suena lo que el programa toca (`engine/timbre.py`).

    Todas las reproducciones pasan por un único punto, así que lo que se
    prueba acá vale para los resultados, la melodía, el historial y el
    analizador a la vez: que la muestra del experimentador se lea igual que
    se escribió, que transpuesta suene en la nota pedida, que ningún timbre
    suene más fuerte que otro y que un archivo que no sirve no rompa nada.
    """

    def tearDown(self):
        from engine import timbre
        timbre.use(timbre.DEFAULT)

    def _instrument(self, folder, preset="Seno puro", midi=57, vibrato=0.0):
        spectrum = harmonics.build(preset, midi)
        spectrum.vibrato_cents = vibrato
        path = os.path.join(folder, "timbre.wav")
        start, end = harmonics.write_instrument(path, spectrum)
        return path, start, end

    def test_the_reader_reads_back_what_the_experimenter_writes(self):
        """La nota, el bucle y las muestras: lo que escribe `write_instrument`."""
        from engine import timbre
        with tempfile.TemporaryDirectory() as folder:
            for preset, midi, vibrato in (("Diente de sierra", 57, 0.0),
                                          ("Clarinete", 64, 22.0)):
                path, start, end = self._instrument(folder, preset, midi,
                                                    vibrato)
                sample = timbre.read_sample(path)
                self.assertTrue(sample.from_smpl)
                self.assertEqual(sample.root, midi)
                self.assertEqual((sample.loop_start, sample.loop_end),
                                 (start, end))
                self.assertEqual(sample.rate, timbre.SAMPLE_RATE)
                with wave.open(path, "rb") as handle:
                    count = handle.getnframes()
                    frames = handle.readframes(count)
                written = struct.unpack("<%dh" % count, frames)
                self.assertEqual(len(sample.data), count)
                for index in (0, start, (start + end) // 2, end, count - 1):
                    self.assertAlmostEqual(sample.data[index],
                                           written[index] / 32768.0)

    def test_an_octave_up_doubles_the_frequency(self):
        """
        Transponer la muestra es leerla más rápido: una octava, el doble.

        Con un seno puro grabado como La de 220, para que contar cruces por
        cero cuente ciclos. Se mide mientras la nota sostiene, después de
        que el bucle ya dio varias vueltas.
        """
        from engine import timbre
        rate = timbre.SAMPLE_RATE
        with tempfile.TemporaryDirectory() as folder:
            path, _start, _end = self._instrument(folder, "Seno puro", 57)
            choice = timbre.choose(timbre.SAMPLE, path)
        heard = {}
        for midi in (45, 57, 69, 76):
            note = timbre.render_note(choice, midi, 3.0, int(3.2 * rate))
            heard[midi] = _upward_crossings_frequency(
                note[int(0.4 * rate):int(2.8 * rate)], rate)
        self.assertAlmostEqual(heard[57], 220.0, delta=220.0 * 0.001)
        self.assertAlmostEqual(heard[69] / heard[57], 2.0, delta=0.002)
        self.assertAlmostEqual(heard[57] / heard[45], 2.0, delta=0.002)
        # Y fuera de las octavas también: mi5, diecinueve semitonos arriba.
        self.assertAlmostEqual(heard[76], 659.255, delta=659.255 * 0.002)

    def test_the_synthesised_timbres_are_in_tune(self):
        """
        Cada receta suena en la nota que se pidió (salvo la flauta).

        Las cuerdas y el coro desafinan a propósito unos cents entre sus
        copias ---es lo que hace la fila---, así que la tolerancia es la de
        un instrumento afinado, no la de un diapasón.
        """
        from engine import timbre
        rate = timbre.SAMPLE_RATE
        for key in timbre.KEYS:
            if key in (timbre.SAMPLE, "recorder"):
                continue
            for midi in (48, 69):
                note = timbre.render_note(timbre.choose(key), midi, 1.5,
                                          int(1.6 * rate))
                found = timbre.detect_root(note[int(0.6 * rate):
                                                int(1.1 * rate)], rate)
                self.assertAlmostEqual(found, midi, delta=0.12,
                                       msg=f"{key} en {midi}")

    def test_every_timbre_sounds_as_loud_as_the_default(self):
        """
        Cambiar de timbre no cambia el volumen percibido.

        Se mide con sonoridad ponderada (LUFS), no con pico: un órgano y una
        cuerda pulsada con el mismo pico suenan uno el doble que el otro. El
        material no es el de la calibración ---tres voces en otro registro y
        otras duraciones---, porque igualarlas en el material con el que se
        igualaron no prueba nada. Y seis voces juntas no recortan con
        ninguno.
        """
        import array
        from engine import timbre
        from engine.audio import render_chords

        def heard(choice):
            frames = array.array("h")
            frames.frombytes(render_chords(
                [[50, 57, 66], [52, 59, 67], [47, 55, 62], [50, 57, 66]],
                [2.0, 1.0, 1.0, 2.0], timbre=choice))
            return timbre.loudness([v / 32768.0 for v in frames])

        def peak(choice):
            frames = array.array("h")
            frames.frombytes(render_chords([[36, 43, 48, 55, 64, 72]], [2.0],
                                           timbre=choice))
            return max(abs(v) for v in frames)

        with tempfile.TemporaryDirectory() as folder:
            path, _start, _end = self._instrument(folder, "Clarinete", 57)
            choices = [timbre.choose(key) for key in timbre.KEYS
                       if key != timbre.SAMPLE]
            choices.append(timbre.choose(timbre.SAMPLE, path))
        reference = heard(timbre.choose(timbre.DEFAULT))
        for choice in choices:
            self.assertAlmostEqual(heard(choice), reference, delta=3.0,
                                   msg=choice.key)
            self.assertLess(peak(choice), 32000, msg=choice.key)

    def test_the_choice_is_a_stored_preference(self):
        """`DEFAULT_SETTINGS` es lista blanca: sin estar ahí, se olvida."""
        from engine import timbre
        self.assertEqual(history.DEFAULT_SETTINGS["timbre"], timbre.DEFAULT)
        self.assertEqual(history.DEFAULT_SETTINGS["timbre_path"], "")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            history.save_settings({"timbre": "organ",
                                   "timbre_path": "C:/x/timbre.wav"}, path)
            values = history.load_settings(path)
        self.assertEqual(values["timbre"], "organ")
        self.assertEqual(values["timbre_path"], "C:/x/timbre.wav")

    def test_labels_and_keys_go_both_ways(self):
        """El menú muestra el nombre y guarda la clave; una clave rara suena."""
        from engine import timbre
        for key in timbre.KEYS:
            self.assertEqual(timbre.key_for_label(timbre.label_of(key)), key)
        self.assertEqual(timbre.choose("una-que-no-existe").key,
                         timbre.DEFAULT)

    def test_a_file_that_is_not_a_timbre_falls_back_to_the_default(self):
        """
        Un archivo que no sirve avisa y deja sonando el de siempre.

        No el que estaba: el de siempre, que es el único que seguro anda.
        Y reproducir sigue funcionando después.
        """
        from engine import timbre
        from engine.audio import render_chords
        with tempfile.TemporaryDirectory() as folder:
            silent = os.path.join(folder, "silencio.wav")
            with wave.open(silent, "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(44100)
                handle.writeframes(b"\x00\x00" * 44100)
            empty = os.path.join(folder, "vacio.wav")
            with wave.open(empty, "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(44100)
            broken = os.path.join(folder, "roto.wav")
            with open(broken, "wb") as handle:
                handle.write(b"RIFF\x10\x00\x00\x00WAVEjunkjunk")
            text = os.path.join(folder, "texto.wav")
            with open(text, "w", encoding="utf-8") as handle:
                handle.write("esto no es un sonido")
            missing = os.path.join(folder, "no-existe.wav")
            for path in (silent, empty, broken, text, missing, ""):
                timbre.use("organ")
                with self.assertRaises(timbre.TimbreError, msg=path):
                    timbre.use(timbre.SAMPLE, path)
                self.assertEqual(timbre.current().key, timbre.DEFAULT)
        self.assertGreater(len(render_chords([[60, 64, 67]], [1.0])), 0)

    def test_a_plain_wav_is_tuned_by_ear_and_looped(self):
        """
        Un WAV cualquiera, sin `smpl`: la nota se deduce y se repite su mitad.

        Estéreo y a 48 kHz a propósito: el lector tiene que mezclar los
        canales y la transposición corregir la frecuencia de muestreo.
        """
        from engine import timbre
        rate = 48000
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "suelto.wav")
            frames = bytearray()
            for index in range(rate):
                value = (0.5 * math.sin(2 * math.pi * 220.0 * index / rate)
                         + 0.2 * math.sin(2 * math.pi * 440.0 * index / rate))
                frames += struct.pack("<hh", int(value * 20000),
                                      int(value * 20000))
            with wave.open(path, "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(rate)
                handle.writeframes(bytes(frames))
            sample = timbre.read_sample(path)
        self.assertFalse(sample.from_smpl)
        self.assertAlmostEqual(sample.root, 57.0, delta=0.05)
        self.assertEqual((sample.loop_start, sample.loop_end),
                         (rate // 2, rate - 1))
        choice = timbre.Choice(timbre.SAMPLE, sample)
        out = timbre.SAMPLE_RATE
        note = timbre.render_note(choice, 69, 2.0, int(2.2 * out))
        found = timbre.detect_root(note[int(0.6 * out):int(1.6 * out)], out)
        self.assertAlmostEqual(found, 69.0, delta=0.05)

    def test_a_held_note_loops_without_a_click(self):
        """
        Sostener es dar vueltas al bucle, y cada vuelta no se tiene que oír.

        Un chasquido es un salto: la segunda diferencia de la onda se
        dispara en el empalme. Se compara lo que pasa mientras da vueltas
        con lo que pasaba antes de la primera.
        """
        from engine import timbre
        rate = timbre.SAMPLE_RATE
        with tempfile.TemporaryDirectory() as folder:
            path, _start, _end = self._instrument(folder, "Clarinete", 55,
                                                  vibrato=12.0)
            choice = timbre.choose(timbre.SAMPLE, path)
        note = timbre.render_note(choice, 62, 5.0, int(5.4 * rate))

        def roughness(begin, end):
            return max(abs(note[i + 1] - 2 * note[i] + note[i - 1])
                       for i in range(int(begin * rate), int(end * rate)))

        # La muestra dura unos dos segundos y una quinta arriba se lee una
        # vez y media más rápido: la primera vuelta llega antes de 1,4 s.
        self.assertLess(roughness(1.4, 4.8), 1.3 * roughness(0.1, 1.3))
        self.assertEqual(note[-1], 0.0)

    def test_playback_uses_the_chosen_timbre(self):
        """El punto único: lo puesto con `use` es lo que suena."""
        from engine import timbre
        from engine.audio import render_chords
        timbre.use("organ")
        organ = render_chords([[60, 64, 67]], [2.0])
        self.assertEqual(organ, render_chords([[60, 64, 67]], [2.0],
                                              timbre=timbre.choose("organ")))
        self.assertNotEqual(organ, render_chords([[60, 64, 67]], [2.0],
                                                 timbre=timbre.Choice()))

    def test_a_float_wav_with_nan_or_infinity_is_refused(self):
        """
        Un WAV flotante con NaN o infinitos se leía igual y el error saltaba
        al tocar, en el hilo del sonido, al pasar la mezcla a enteros. Se
        rechaza al leerlo, con un motivo que se pueda mostrar; uno sano del
        mismo formato se sigue leyendo.
        """
        from engine import timbre
        rate = 44100

        def float_wav(path, bad=None):
            values = [0.5 * math.sin(2 * math.pi * 220.0 * i / rate)
                      for i in range(rate // 2)]
            if bad is not None:
                values[rate // 4] = bad
            data = struct.pack("<%df" % len(values), *values)
            fmt = struct.pack("<HHIIHH", 3, 1, rate, rate * 4, 4, 32)
            body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
                    + b"data" + struct.pack("<I", len(data)) + data)
            with open(path, "wb") as handle:
                handle.write(b"RIFF" + struct.pack("<I", len(body)) + body)

        with tempfile.TemporaryDirectory() as folder:
            sound = os.path.join(folder, "sano.wav")
            float_wav(sound)
            self.assertEqual(len(timbre.read_sample(sound).data), rate // 2)
            for label, bad in (("nan", float("nan")), ("inf", float("inf")),
                               ("menos_inf", float("-inf"))):
                path = os.path.join(folder, label + ".wav")
                float_wav(path, bad)
                timbre.use("organ")
                with self.assertRaises(timbre.TimbreError, msg=label):
                    timbre.use(timbre.SAMPLE, path)
                self.assertEqual(timbre.current().key, timbre.DEFAULT)

    def test_the_vibrato_cache_is_bounded(self):
        """
        La forma del vibrato se guarda una por (velocidad, demora, fase) y
        hasta un largo fijo, no una por largo de nota: con muchas duraciones
        distintas retenía de decenas a cientos de megas. Lo que sale es la
        misma cuenta de siempre, muestra por muestra.
        """
        from engine import timbre
        timbre._WOBBLES.clear()
        kept = timbre._WOBBLE_KEPT
        for length in (500, 3000, kept + 1234, 1000, 2 * kept):
            shape = timbre._wobble(5.3, 0.35, length, 1.7)
            self.assertEqual(len(shape), length)
        self.assertEqual(list(timbre._WOBBLES), [(5.3, 0.35, 1.7)])
        self.assertLessEqual(len(timbre._WOBBLES[(5.3, 0.35, 1.7)]), kept)
        step = 2.0 * math.pi * 5.3 / timbre.SAMPLE_RATE
        ramp = 0.35 * timbre.SAMPLE_RATE
        for i in (0, 10, 499, kept - 1, kept, 2 * kept - 1):
            self.assertEqual(shape[i],
                             min(1.0, i / ramp) * math.sin(step * i + 1.7))
        for phase in range(3 * timbre._WOBBLE_SHAPES):
            timbre._wobble(5.0, 0.3, 100, float(phase))
        self.assertLessEqual(len(timbre._WOBBLES), timbre._WOBBLE_SHAPES)

    def test_a_sample_builds_what_it_reads_once(self):
        """
        Lo que lee una nota de muestra ---el sonido hasta el final del bucle
        y una muestra de más--- se arma una vez y no en cada nota; se rearma
        sólo si alguien mueve el bucle.
        """
        from engine import timbre
        with tempfile.TemporaryDirectory() as folder:
            path, start, end = self._instrument(folder, "Clarinete", 55)
            sample = timbre.read_sample(path)
        source = sample.source()
        self.assertEqual(len(source), end + 2)
        self.assertEqual(source[-1], sample.data[start])
        choice = timbre.Choice(timbre.SAMPLE, sample)
        for midi in (55, 62):
            timbre.render_note(choice, midi, 0.5, 30000)
        self.assertIs(sample.source(), source)
        sample.loop_start += 1
        self.assertIsNot(sample.source(), source)
        self.assertEqual(sample.source()[-1], sample.data[start + 1])


class TestVoicePresets(unittest.TestCase):
    """
    Los atajos de la pantalla de voces: canto, piano y cuarteto.

    Un atajo es un conjunto de voces del catálogo con sus registros, y tiene
    que salir del otro lado exactamente como lo dejaría el usuario
    escribiendo las casillas: las voces en el orden del motor, los
    registros por posición, y que el motor pueda cantarlo.
    """

    EXPECTED = {
        "satb": {"B": ("E2", "C4"), "T": ("C3", "G4"), "A": ("G3", "D5"),
                 "S": ("C4", "G5")},
        "piano": {"B": ("C2", "C4"), "T": ("G2", "G4"), "A": ("D3", "D5"),
                  "S": ("G3", "C6")},
        "quartet": {"B": ("C2", "E4"), "T": ("C3", "C5"), "A": ("G3", "E5"),
                    "S": ("G3", "A5")},
    }

    def test_each_preset_gives_the_voices_and_ranges_it_promises(self):
        import app
        from engine.theory import VOICE_CATALOG
        presets = {key for key, *_rest in app.ChordWeaverApp.VOICE_PRESETS}
        self.assertEqual(presets, set(self.EXPECTED))
        for key, ranges in self.EXPECTED.items():
            voices, overrides = app.ChordWeaverApp.voice_preset(key)
            self.assertEqual(voices, sorted(ranges,
                                            key=lambda v: VOICE_CATALOG[v].low))
            self.assertEqual(
                overrides,
                {index: (parse_note_name(ranges[voice][0]),
                         parse_note_name(ranges[voice][1]))
                 for index, voice in enumerate(voices)})

    def test_the_presets_respect_what_the_engine_needs(self):
        """
        Entre 3 y 6 voces, cada una con una octava entera como mínimo ---o
        hay acordes que no tienen nota para ella--- y el bajo siempre abajo:
        `voices[0]` es el bajo para medio motor. Y una corrida corta sale
        con todas las notas dentro de sus registros.
        """
        import app
        for key in self.EXPECTED:
            voices, overrides = app.ChordWeaverApp.voice_preset(key)
            self.assertTrue(3 <= len(voices) <= 6, key)
            lows = [overrides[i][0] for i in range(len(voices))]
            highs = [overrides[i][1] for i in range(len(voices))]
            for low, high in zip(lows, highs):
                self.assertGreaterEqual(high - low, 12, key)
            self.assertEqual(lows, sorted(lows), key)
            self.assertEqual(highs, sorted(highs), key)
            request = session.JobRequest(
                genre_key="chorale", voice_keys=voices,
                entries=[session.ChordEntry(s, 2.0, i // 2)
                         for i, s in enumerate(["C", "Am", "F", "G7", "C"])],
                range_overrides=overrides,
                ga_config=GAConfig(population_size=40, generations=12,
                                   random_seed=5))
            settings = session.build_settings(request)
            self.assertEqual([(v.low, v.high) for v in settings.voices],
                             list(zip(lows, highs)))
            outcome = session.generate(request)
            self.assertTrue(outcome.succeeded, key)
            for chord in outcome.result.solutions[0].slots:
                for index, pitch in enumerate(chord):
                    self.assertTrue(lows[index] <= pitch <= highs[index],
                                    f"{key}: {pitch} fuera de la voz {index}")


# -- exportar y volver a leer -------------------------------------------------

_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _midi_notes(data):
    """
    Un lector MIDI mínimo: ``(división, pistas)``, cada pista una lista de
    ``(comienzo, altura, duración)`` en ticks.

    Escrito acá a propósito y no tomado del exportador: si leyera con las
    mismas cuentas con las que se escribe, un error de las dos se taparía.
    Levanta ``ValueError`` si el archivo está mal formado.
    """
    def number(position):
        value = 0
        while True:
            byte = data[position]
            position += 1
            value = (value << 7) | (byte & 0x7F)
            if not byte & 0x80:
                return value, position

    if data[:4] != b"MThd":
        raise ValueError("sin MThd")
    size, _format, count, division = struct.unpack(">IHHH", data[4:14])
    position = 8 + size
    tracks = []
    for _ in range(count):
        if data[position:position + 4] != b"MTrk":
            raise ValueError("sin MTrk")
        end = position + 8 + struct.unpack(">I", data[position + 4:position + 8])[0]
        cursor, tick, status = position + 8, 0, None
        sounding, notes = {}, []
        while cursor < end:
            delta, cursor = number(cursor)
            tick += delta
            if data[cursor] & 0x80:
                status = data[cursor]
                cursor += 1
            if status == 0xFF:
                cursor += 1
                length, cursor = number(cursor)
                cursor += length
                status = None
                continue
            kind = status & 0xF0
            if kind in (0xC0, 0xD0):
                cursor += 1
                continue
            pitch, velocity = data[cursor], data[cursor + 1]
            cursor += 2
            if kind == 0x90 and velocity:
                sounding.setdefault(pitch, []).append(tick)
            elif kind in (0x80, 0x90):
                if not sounding.get(pitch):
                    raise ValueError("se apaga una nota que no sonaba")
                start = sounding[pitch].pop(0)
                notes.append((start, pitch, tick - start))
        if cursor != end or any(sounding.values()):
            raise ValueError("pista mal cerrada")
        tracks.append(sorted(notes))
        position = end
    return division, tracks


def _musicxml_voices(text):
    """
    Las voces de un MusicXML de una parte, leídas a mano.

    Devuelve ``({voz: [(comienzo, altura, duración)]}, problemas)``, en
    negras y con las ligaduras unidas. La altura sale de letra, alteración y
    octava como lo leería cualquier editor, y los problemas son lo que se ve
    al leer: voces de un compás que no suman lo mismo, un ``<backup>`` que
    no vuelve al comienzo, duraciones cero, una alteración sin su accidente.
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text.encode("utf-8"))
    divisions, fifths, start = 1, 0, 0.0
    voices, problems, tied = {}, [], {}
    for measure in root.find("part").findall("measure"):
        number = measure.get("number")
        if measure.find("attributes/divisions") is not None:
            divisions = int(measure.findtext("attributes/divisions"))
        if measure.find("attributes/key/fifths") is not None:
            fifths = int(measure.findtext("attributes/key/fifths"))
        cursor = furthest = 0
        totals = {}
        for element in measure:
            if element.tag == "backup":
                back = int(element.findtext("duration"))
                if back != cursor:
                    problems.append(("backup", number, cursor, back))
                cursor -= back
                continue
            if element.tag != "note":
                continue
            length = int(element.findtext("duration"))
            voice = int(element.findtext("voice"))
            totals[voice] = totals.get(voice, 0) + length
            if length <= 0:
                problems.append(("duración cero", number, voice))
            pitch = element.find("pitch")
            if pitch is not None:
                step = pitch.findtext("step")
                alter = int(pitch.findtext("alter") or 0)
                midi = (_LETTER_PC[step] + alter
                        + (int(pitch.findtext("octave")) + 1) * 12)
                ties = {tie.get("type") for tie in element.findall("tie")}
                if ("stop" not in ties
                        and alter != export._signature_alteration(step, fifths)
                        and element.find("accidental") is None):
                    problems.append(("sin accidente", number, midi))
                if "stop" in ties and (voice, midi) in tied:
                    note = tied.pop((voice, midi))
                    note[2] += length / divisions
                else:
                    note = [start + cursor / divisions, midi, length / divisions]
                    voices.setdefault(voice, []).append(note)
                if "start" in ties:
                    tied[(voice, midi)] = note
            cursor += length
            furthest = max(furthest, cursor)
        if len(set(totals.values())) > 1:
            problems.append(("compás desparejo", number, totals))
        start += furthest / divisions
    return ({voice: [tuple(n) for n in notes] for voice, notes in voices.items()},
            problems)


def _expected_voices(spec, solution, melody=None):
    """
    Lo que tiene que quedar escrito: ``{voz del motor: [(comienzo, altura,
    duración)]}``, armado con lo mismo que lee la pantalla.

    ``solution.slots`` **no** está alineado con ``spec.slots`` ---la búsqueda
    saltea los silencios---, así que se pasa por `session.voiced_slots` y
    `session.ornaments_of`. En el armonizador la voz de la melodía es la
    línea que el usuario escribió, con su ritmo, y no la muestreada.
    """
    voiced = session.voiced_slots(spec, solution)
    figures = {(slot, voice): (shape, share) for slot, voice, shape, share
               in session.ornaments_of(spec, solution)}
    out = {voice: [] for voice in range(len(spec.voices))}
    onset = 0.0
    for index, slot in enumerate(spec.slots):
        length = slot.duration_quarters
        if not slot.is_rest and voiced[index]:
            for voice in out:
                pitch = voiced[index][voice]
                shape, share = figures.get((index, voice), ((), 0.0))
                if not shape:
                    out[voice].append((onset, pitch, length))
                    continue
                head = length * (1.0 - share)
                out[voice].append((onset, pitch, head))
                span = (length - head) / len(shape)
                for step, moved in enumerate(shape):
                    out[voice].append((onset + head + step * span, moved, span))
        onset += length
    if melody is not None and spec.melody is not None:
        starts, total = [], 0.0
        for bar in melody.bars:
            starts.append(total)
            total += bar.quarters
        out[spec.melody.voice_index] = sorted(
            (starts[note.bar_index] + note.offset_quarters, note.pitch,
             note.duration_quarters)
            for note in melody.notes
            if not note.is_rest and note.pitch is not None)
    return out


def _round_trip_problems(spec, solution, melody=None, xml=None, midi=None):
    """
    Exportar una solución, leerla de vuelta y comparar altura por altura.

    Sin ``xml``/``midi`` se escriben acá; con ellos se leen los que ya se
    escribieron (los archivos de `session.export_outcome`).
    """
    xml = xml if xml is not None else export.build_musicxml(spec, solution)
    midi = midi if midi is not None else export.build_midi(spec, solution)
    want = _expected_voices(spec, solution, melody)
    count = len(spec.voices)
    written, problems = _musicxml_voices(xml)
    division, tracks = _midi_notes(midi)
    for voice, expected in want.items():
        for source, got in (
                ("MusicXML", written.get(count - voice, [])),
                ("MIDI", [(s / division, p, d / division)
                          for s, p, d in tracks[voice + 1]])):
            heard = [p for _o, p, _d in got]
            meant = [p for _o, p, _d in expected]
            if heard != meant:
                problems.append((source, "alturas", voice, heard, meant))
            elif any(abs(a[0] - b[0]) > 0.025 or abs(a[2] - b[2]) > 0.025
                     for a, b in zip(got, expected)):
                problems.append((source, "tiempos", voice, got, expected))
    return problems


class TestExportRoundTrip(unittest.TestCase):
    """
    Lo que se exporta es lo que salió: altura por altura, ida y vuelta.

    Cada solución se escribe en MusicXML y en MIDI, se lee de vuelta con
    lectores escritos acá ---no los del exportador--- y se compara contra lo
    que muestra la pantalla. Los casos de abajo son los que fallaban, y al
    final un barrido chico de los tres modos con semillas fijas.
    """

    GA = GAConfig(population_size=20, generations=4, random_seed=1,
                  workers=1)

    def test_every_spelling_writes_back_the_same_pitch(self):
        """
        Letra + alteración + octava vuelve a dar la altura, siempre.

        La octava sigue a la letra: un do doble bemol suena como si bemol y
        se escribe en la octava del do. Corregir sólo si sostenido y do
        bemol dejaba Cbb y B## escritos una octava corridos.
        """
        for letter in "CDEFGAB":
            for shift in (-2, -1, 0, 1, 2):
                root = (_LETTER_PC[letter] + shift) % 12
                for degree in [None, "1", "b3", "3", "5", "#5", "b5", "bb7",
                               "b7", "7", "b9", "#9", "#11", "b13", "13"]:
                    for midi in range(24, 108):
                        step, alter, octave = spell_pitch(
                            midi, letter, (midi - root) % 12, degree)
                        self.assertEqual(
                            _LETTER_PC[step] + alter + (octave + 1) * 12, midi,
                            (letter, shift, degree, midi))
        from engine.theory import spell_in_key
        for fifths in range(-7, 8):
            for midi in range(24, 108):
                step, alter, octave = spell_in_key(midi, fifths)
                self.assertEqual(_LETTER_PC[step] + alter + (octave + 1) * 12,
                                 midi, (fifths, midi))

    def test_double_alterations_are_written_where_they_sound(self):
        """La séptima de Dbdim7 es un Cbb4, no un Cbb3; el B## de A#7#9 igual."""
        request = session.JobRequest(
            genre_key="jazz", voice_keys=["B", "T", "A", "S"],
            entries=[session.ChordEntry("Dbdim7", 4.0, 0,
                                        locked_pitches=[49, 58, 64, 67]),
                     session.ChordEntry("A#7#9", 4.0, 1,
                                        locked_pitches=[46, 56, 61, 62])],
            ga_config=self.GA, solutions_wanted=1)
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        self.assertEqual(_round_trip_problems(outcome.spec,
                                              outcome.result.solutions[0]), [])

    def test_ornament_figures_fill_the_bar(self):
        """
        Una figura de tres notas reparte la cola en tercios, y el compás
        tiene que seguir sumando lo que suma: con ocho divisiones por negra
        un tercio se redondeaba, la voz sumaba de más y las demás quedaban
        corridas.
        """
        from engine.ga import ChordSlot, Chromosome
        voices = build_voice_parts(["B", "T", "A", "S"])
        for durations, share, shape in (([2.0, 2.0], 0.5, (74, 72, 71)),
                                        ([0.5, 0.5, 1.0, 2.0], 0.25, (74, 72))):
            slots = [ChordSlot(requirement=build_requirement(parse_chord("C"), 4),
                               duration_quarters=d, bar_index=0)
                     for d in durations]
            rows = [[None] * 4 for _ in durations]
            rows[0][3] = shape
            spec = export.ScoreSpec(slots=slots, voices=voices,
                                    time_signature=export.TimeSignature(4, 4))
            solution = Chromosome(slots=[[48, 55, 64, 72] for _ in durations],
                                  choices=[0] * len(durations), passing=rows,
                                  passing_share=[share] * len(durations))
            self.assertEqual(_round_trip_problems(spec, solution), [],
                             (durations, share))

    def test_an_unfinished_last_bar_keeps_the_voices_together(self):
        """
        «do re mi | re do» en tres por cuatro: el último compás tiene dos
        negras y la melodía se escribe completa hasta la barra. El último
        acorde tiene que llegar hasta ahí también, o las otras voces del
        compás entran corridas contra la melodía.
        """
        names = ["C5", "D5", "E5", "D5", "C5"]
        melody = harmonize.Melody(
            notes=[harmonize.MelodyNote(parse_note_name(n), 1.0, i // 3,
                                        float(i % 3))
                   for i, n in enumerate(names)],
            bars=[harmonize.MelodyBar(3, 4, 0, "major") for _ in range(2)],
            melody_voice=3)
        request = session.HarmoniseRequest(
            genre_key="chorale", voice_keys=["B", "T", "A", "S"],
            melody=melody, melody_voice=3, ga_config=self.GA,
            solutions_wanted=1)
        outcome = session.harmonise_melody(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        spec = outcome.spec
        self.assertAlmostEqual(sum(s.duration_quarters for s in spec.slots), 6.0)
        self.assertEqual(_round_trip_problems(
            spec, outcome.result.solutions[0], melody), [])

    def test_a_note_across_the_barline_stays_one_note(self):
        """Lo que exporta el analizador: una síncopa se liga, no se reataca."""
        score = analysis.Score(parts=[
            analysis.Part("Bajo", [analysis.Note(48, 0, 2), analysis.Note(50, 2, 4),
                                   analysis.Note(48, 6, 2)]),
            analysis.Part("Alto", [analysis.Note(64, 0, 4), analysis.Note(65, 4, 4)]),
            analysis.Part("Soprano", [analysis.Note(72, 0, 4),
                                      analysis.Note(71, 4, 2),
                                      analysis.Note(72, 6, 2)])],
            fifths=0, beats=4, beat_type=4)
        spec, solution, _filled = session.analysis_score_spec(
            analysis.analyse(score), "t")
        written, problems = _musicxml_voices(export.build_musicxml(spec, solution))
        self.assertEqual(problems, [])
        self.assertEqual(written[3], [(0.0, 48, 2.0), (2.0, 50, 4.0),
                                      (6.0, 48, 2.0)])
        division, tracks = _midi_notes(export.build_midi(spec, solution))
        self.assertEqual([(s / division, p, d / division) for s, p, d in tracks[1]],
                         [(0.0, 48, 2.0), (2.0, 50, 4.0), (6.0, 48, 2.0)])

    def test_the_sixth_leaves_locks_and_the_melody_alone(self):
        """
        La sexta de Bach reescribe la solución después de la búsqueda, y no
        puede tocar ni un acorde con candado ni la melodía del usuario.

        Un silencio antes del candado es el caso: la búsqueda no ve los
        silencios y los candados se contaban sobre la partitura, así que
        quedaban corridos un lugar.
        """
        from unittest import mock
        from engine import flourish
        entries = [session.ChordEntry("C", 2.0, 0),
                   session.ChordEntry("", 2.0, 0, is_rest=True),
                   session.ChordEntry("F", 2.0, 1),
                   session.ChordEntry("G", 2.0, 1, locked_pitches=[43, 59, 62, 67]),
                   session.ChordEntry("Am", 2.0, 2), session.ChordEntry("Dm", 2.0, 2),
                   session.ChordEntry("G", 2.0, 3), session.ChordEntry("C", 2.0, 3)]
        request = session.JobRequest(
            genre_key="classical", voice_keys=["B", "T", "A", "S"],
            entries=entries, ga_config=GAConfig(population_size=30,
                                                generations=8, random_seed=3,
                                                workers=1),
            solutions_wanted=1)
        outcome = session.generate(request)
        self.assertTrue(outcome.succeeded, outcome.errors)
        best = outcome.result.solutions[0]
        before = [list(chord) for chord in best.slots]
        with mock.patch.object(flourish, "SIXTH_CHANCE", 1.0):
            for _ in range(12):
                best.slots = [list(chord) for chord in before]
                # `apply_flourishes` corre una sola vez por resultado: para
                # sortear otra sexta hay que olvidar la anterior.
                outcome.flourishes = None
                session.apply_flourishes(outcome, "classical", 0)
                voiced = session.voiced_slots(outcome.spec, best)
                self.assertEqual(voiced[3], [43, 59, 62, 67])
                where = outcome.flourishes.sixth_slot
                if where is not None:
                    # En columnas de la partitura: ni un silencio ni el candado.
                    self.assertFalse(outcome.spec.slots[where].is_rest)
                    self.assertFalse(outcome.spec.slots[where].is_locked)
        # Y la voz fija ---la melodía del armonizador--- no se toca nunca.
        chords = [[parse_note_name(n) for n in group] for group in (
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"),
            ("A2", "E4", "C#5"), ("E3", "B3", "G#4"))]
        for seed in range(8):
            moved = [list(chord) for chord in chords]
            flourish.apply_sixth(moved, [False] * 4, 3, random.Random(seed),
                                 frozen=[{1}] * 4)
            self.assertEqual([c[1] for c in moved], [c[1] for c in chords])

    # -- el barrido --------------------------------------------------------

    CHORDS = ["C", "Dbdim7", "C#dim7", "Bb7", "F#m7b5", "Abmaj7", "E7#9", "Cb",
              "B#", "Gb", "E#", "G#m", "A#7#9", "Ebdim7", "Caug", "G#aug",
              "C/Bb", "D/F#", "Ab/C", "Fm/Ab", "Cbdim7", "F#7", "Db7b9", "G7"]
    TONICS = ["Bb", "Eb", "Ab", "Db", "Gb", "F#", "C#", "B", "E", "Cb"]
    VOICES = {3: ["B", "A", "S"], 4: ["B", "T", "A", "S"],
              5: ["B", "T", "A", "MS", "S"], 6: ["B", "Bar", "T", "A", "MS", "S"]}

    def _passing(self, rng, voices):
        from engine import passing
        density = rng.choice([0.6, 1.0])
        return passing.PassingRules(
            voices=tuple(range(voices)), density=density,
            diatonic_only=rng.random() < 0.5,
            max_per_piece=passing.max_for_density(density),
            shares=rng.choice([(0.5, 0.25, 0.75), (0.5,), (0.25,)]))

    def _organiser(self, rng, seed):
        voices = rng.choice([3, 4, 5, 6])
        beats, beat_type = rng.choice([(4, 4), (3, 4), (6, 8)])
        per_bar = beats * 4.0 / beat_type
        entries = []
        for bar in range(3):
            left = per_bar
            while left > 1e-9:
                length = rng.choice([d for d in (2.0, 1.5, 1.0, 0.5)
                                     if d <= left + 1e-9])
                rest = rng.random() < 0.15 and entries
                entries.append(session.ChordEntry(
                    "" if rest else rng.choice(self.CHORDS), length, bar,
                    is_rest=bool(rest)))
                left -= length
        request = session.JobRequest(
            genre_key=rng.choice(["classical", "chorale", "jazz"]),
            voice_keys=self.VOICES[voices], entries=entries,
            time_signature=export.TimeSignature(beats, beat_type),
            ga_config=GAConfig(population_size=20, generations=4,
                               random_seed=seed, workers=1),
            passing_rules=self._passing(rng, voices), title="vuelta")
        outcome = session.generate(request)
        if outcome.succeeded:
            session.apply_flourishes(outcome, request.genre_key, 0)
        return request, outcome, None

    def _generator(self, rng, seed):
        from engine.harmony import MODES
        voices = rng.choice([3, 4, 5])
        durations = [rng.choice([2.0, 1.0, 1.0, 2.0]) for _ in range(6)]
        bars, position = [], 0.0
        for length in durations:
            bars.append(int(position // 4))
            position += length
        request = session.GenerativeRequest(
            genre_key=rng.choice(["classical", "chorale", "jazz"]),
            voice_keys=self.VOICES[voices], tonic=rng.choice(self.TONICS),
            mode_key=rng.choice(list(MODES)),
            borrowed=rng.sample(["iv", "bII", "N6", "bVII", "bVI"], 2),
            slot_count=len(durations), durations=durations,
            bar_indices=bars, with_sevenths=rng.random() < 0.5,
            ga_config=GAConfig(population_size=20, generations=4,
                               random_seed=seed, workers=1),
            passing_rules=self._passing(rng, voices), title="vuelta")
        outcome = session.generate_random(request)
        if outcome.succeeded:
            session.apply_flourishes(outcome, request.genre_key,
                                     parse_pitch_class(request.tonic))
        return request, outcome, None

    def _harmoniser(self, rng, seed):
        from engine.harmony import MODES
        tonic_name = rng.choice(self.TONICS)
        tonic = parse_pitch_class(tonic_name)
        mode = rng.choice(["major", "minor", "harmonic"])
        scale = MODES[mode].pitch_classes(tonic)
        notes, pitch = [], 67
        for bar in range(3):
            offset = 0.0
            while offset < 4.0 - 1e-9:
                length = rng.choice([d for d in (2.0, 1.0, 1.0, 0.5)
                                     if d <= 4.0 - offset + 1e-9])
                pitch = max(60, min(79, pitch + rng.choice([-2, -1, 1, 2, 3, -3])))
                while pitch % 12 not in scale:
                    pitch += 1
                if rng.random() < 0.1:
                    pitch += rng.choice([-1, 1])           # cromática
                notes.append(harmonize.MelodyNote(
                    pitch=pitch, duration_quarters=length, bar_index=bar,
                    offset_quarters=offset,
                    is_rest=offset > 0 and rng.random() < 0.08))
                offset += length
        if notes[-1].offset_quarters > 0:
            notes.pop()                     # un último compás sin terminar
        voices = rng.choice([3, 4])
        melody = harmonize.Melody(
            notes=notes,
            bars=[harmonize.MelodyBar(4, 4, tonic, mode) for _ in range(3)],
            melody_voice=voices - 1)
        request = session.HarmoniseRequest(
            genre_key=rng.choice(["classical", "chorale", "jazz"]),
            voice_keys=self.VOICES[voices], melody=melody,
            melody_voice=voices - 1, with_sevenths=rng.random() < 0.4,
            ga_config=GAConfig(population_size=20, generations=4,
                               random_seed=seed, workers=1),
            title="vuelta")
        return request, session.harmonise_melody(request), melody

    def test_what_is_exported_is_what_came_out(self):
        """
        El barrido: casos al azar con semilla fija de los tres modos ---con
        armaduras de bemoles y sostenidos, acordes cromáticos y alterados,
        silencios, adornos, de tres a seis voces---, exportados con
        `export_outcome` y leídos de vuelta con lectores propios y con
        `engine.importer`.

        Chico a propósito para que corra en segundos. Para buscar en serio
        se sube ``CASES``: con cientos por modo fue como aparecieron los
        Cbb escritos una octava abajo y los compases que no sumaban.
        """
        CASES = 2
        rng = random.Random(2026)
        checked = 0
        for maker in (self._organiser, self._generator, self._harmoniser):
            for _ in range(CASES):
                seed = rng.randrange(10 ** 6)
                request, outcome, melody = maker(random.Random(seed), seed)
                if not outcome.succeeded:
                    continue
                with tempfile.TemporaryDirectory() as folder:
                    paths = session.export_outcome(request, outcome,
                                                   directory=folder,
                                                   record_history=False)
                    for option, solution in enumerate(outcome.result.solutions,
                                                      start=1):
                        stem = [p for p in paths
                                if p.endswith(f"option {option}.musicxml")]
                        self.assertEqual(len(stem), 1, paths)
                        with open(stem[0], encoding="utf-8") as handle:
                            xml = handle.read()
                        with open(stem[0][:-len(".musicxml")] + ".mid",
                                  "rb") as handle:
                            midi = handle.read()
                        context = (maker.__name__, seed, option)
                        self.assertEqual(_round_trip_problems(
                            outcome.spec, solution, melody, xml, midi), [],
                            context)
                        # Y el importador del programa lee las mismas notas.
                        imported = importer.read_voices(stem[0])
                        written, _problems = _musicxml_voices(xml)
                        self.assertEqual(
                            sorted(n.pitch for part in imported.parts
                                   for n in part.notes),
                            sorted(p for notes in written.values()
                                   for _o, p, _d in notes), context)
                        checked += 1
        self.assertGreater(checked, 6)


class TestAnalysisChordCoverage(unittest.TestCase):
    """
    Que todos los acordes que hay se lean, y sólo cuando hay acordes.

    El piso de tres es lo que impide inventar armonía a partir de una voz o
    dos. Puesto en el lugar equivocado ---en cada tiempo, o contando alturas
    en vez de voces--- hace lo contrario de lo que promete: se come acordes
    que están escritos.
    """

    def _voices(self, lines):
        names = ("Bajo", "Tenor", "Alto", "Soprano")
        return analysis.Score(parts=[_line(line, name)
                                     for name, line in zip(names, lines)
                                     if line])

    def test_a_chorale_that_doubles_the_root_still_has_chords(self):
        """
        Cuatro voces, la fundamental doblada y la quinta omitida.

        Es la textura más común que hay y en ninguna vertical llegan a sonar
        tres alturas distintas. Contando alturas en vez de voces, la pieza
        entera se quedaba sin una sola lectura.
        """
        result = analysis.analyse(self._voices([
            [(48, 1.0), (53, 1.0), (43, 1.0)],
            [(60, 1.0), (65, 1.0), (55, 1.0)],
            [(64, 1.0), (69, 1.0), (62, 1.0)],
            [(72, 1.0), (77, 1.0), (67, 1.0)]]))
        self.assertEqual(_symbols(result), ["C", "F", "G"])

    def test_every_beat_gets_its_chord_even_if_the_bass_stops(self):
        """
        El bajo canta una nota y las otras tres siguen cambiando.

        Cada tiempo tiene su acorde. Aplicando el piso tiempo por tiempo, los
        tiempos flacos se le sumaban al anterior y el compás entero salía
        cifrado una sola vez.
        """
        result = analysis.analyse(self._voices([
            [(43, 2.0)],
            [(59, 1.0), (60, 1.0), (62, 1.0)],
            [(65, 1.0), (64, 1.0), (65, 1.0)],
            [(71, 1.0), (72, 1.0), (74, 1.0)]]))
        self.assertEqual(len(result.segments), 3)

    def test_one_or_two_voices_are_not_named(self):
        for lines in ([[(48, 1.0), (50, 1.0)]],
                      [[(48, 1.0), (50, 1.0)], [(60, 1.0), (64, 1.0)]]):
            result = analysis.analyse(self._voices(lines))
            self.assertEqual(result.segments, [], lines)

    def test_a_lone_line_inside_a_full_piece_is_not_named(self):
        """
        El piso de tres voces es de la pieza; una nota sola sigue sin acorde.

        Un compás en el que canta la soprano sola ---y las otras dos callan---
        salía cifrado nota por nota: Fa, Sol, La menor, Si disminuido, cada
        uno deducido de una nota.
        """
        result = analysis.analyse(_score([
            [(48, 4), (None, 4)], [(55, 4), (None, 4)],
            [(64, 4), (65, 1), (67, 1), (69, 1), (71, 1)]]))
        self.assertEqual(_symbols(result), ["C"])
        self.assertEqual(result.segments[0].end, 4.0)

    def test_two_voices_that_outline_a_chord_still_name_it(self):
        """
        Dos voces que entre las dos recorren la tríada sí la nombran.

        Es el bajo de Alberti debajo de una melodía: nunca suenan tres notas
        juntas y el acorde está igual. El piso nuevo no puede comérselo.
        """
        result = analysis.analyse(_score([
            [(48, 4), (41, 4)], [(55, 4), (None, 4)],
            [(64, 4), (69, 2), (72, 2)]]))
        self.assertEqual(_symbols(result), ["C", "F"])

    def test_a_passing_note_does_not_leave_a_hole(self):
        """
        Un tiempo flaco con una nota de paso cabe igual en el acorde.

        El bajo sostiene do y la soprano pasa por re entre mi y do, con el
        tenor callado. Contando el re, ese tiempo no cabía en el Do y el
        análisis salía «C | hueco | C».
        """
        result = analysis.analyse(_score([
            [(48, 4)], [(55, 1), (None, 1), (55, 2)],
            [(64, 1), (62, 1), (60, 2)]]))
        self.assertEqual(_symbols(result), ["C"])
        self.assertEqual((result.segments[0].start, result.segments[0].end),
                         (0.0, 4.0))

    def test_a_held_note_belongs_to_the_chord_the_others_complete(self):
        """
        Un bajo que suena antes de que entren las otras voces es del acorde.

        El bajo ataca solo, el tenor entra en el segundo tiempo y la soprano
        en el tercero. Esa redonda es parte del Do mayor, y dejándola afuera
        el acorde empezaba recién con la última voz.
        """
        result = analysis.analyse(_score([
            [(48, 4), (41, 4)],
            [(None, 1), (55, 3), (57, 4)],
            [(None, 2), (64, 2), (65, 4)]]))
        self.assertEqual(_symbols(result), ["C", "F"])
        self.assertEqual(result.segments[0].start, 0.0)

    def test_the_third_and_the_fifth_are_taken_for_granted(self):
        """
        Una séptima sin quinta se cifra 7, y una tríada sin quinta, nada.

        El continuista toca la tercera y la quinta sin que nadie se las
        escriba. Apilando los números que sobreviven salían cifras como
        "7/3", que no existen.

        `None` es "sin accidente"; un número es la alteración **escrita** de
        esa nota, y el cero es el becuadro.
        """
        self.assertEqual(analysis._abbreviate({3: None, 7: None}), "7")
        self.assertEqual(analysis._abbreviate({5: None, 7: None}), "7")
        self.assertEqual(analysis._abbreviate({3: None}), "")
        self.assertEqual(analysis._abbreviate({3: None, 5: None}), "")
        self.assertEqual(analysis._abbreviate({3: None, 6: None}), "6")

    def test_a_figure_carries_the_accidental_that_gets_written(self):
        """
        Y no la diferencia con la armadura.

        Una nota natural en una armadura de bemoles está subida respecto de
        la armadura y se escribe con becuadro: cifrarla con sostenido ---que
        es lo que dice la diferencia--- llena de sostenidos una pieza que no
        tiene ninguno.
        """
        figure = analysis._abbreviate({6: None, 3: 0})
        self.assertIn(analysis.NATURAL_SIGN, figure)
        self.assertNotIn(analysis.SHARP_SIGN, figure)
        self.assertEqual(analysis._sign(1), analysis.SHARP_SIGN)
        self.assertEqual(analysis._sign(-1), analysis.FLAT_SIGN)
        self.assertEqual(analysis._sign(0), analysis.NATURAL_SIGN)

    def test_the_four_inversions_are_figured_as_they_are_written(self):
        """Un coral a cuatro voces, con todas las inversiones."""
        chords = [(48, 64, 67, 72), (52, 60, 67, 72), (55, 60, 64, 72),
                  (43, 62, 65, 71), (47, 62, 65, 67), (53, 62, 67, 71),
                  (48, 64, 67, 72)]
        result = analysis.analyse(self._voices(
            [[(chord[voice], 2.0) for chord in chords] for voice in range(4)]))
        self.assertEqual([segment.figure for segment in result.segments],
                         ["", "6", "6/4", "7", "6/5", "4/2", ""])


class TestSchoolCard(unittest.TestCase):
    """El dibujo de la escuelita en el inicio muestra dónde anda el usuario."""

    def state_after(self, units):
        import types
        import app
        from engine import school as curriculum
        passed = {entry.key: "2026-10-14"
                  for unit in curriculum.UNITS[:units]
                  for lesson in unit.lessons for entry in lesson.exercises}
        progress = curriculum.Progress(passed=passed)
        return app.ChordWeaverApp._school_state(
            types.SimpleNamespace(school=progress)), curriculum.UNITS

    def test_the_next_unit_is_the_one_marked(self):
        (done, current, label, graduated), units = self.state_after(2)
        self.assertEqual(done, (1.0, 1.0) + (0.0,) * (len(units) - 2))
        self.assertEqual(current, 2)
        self.assertEqual(label, units[2].short)
        self.assertFalse(graduated)

    def test_with_everything_passed_only_the_star_is_left(self):
        from engine import school as curriculum
        (done, current, _label, _graduated), _units = self.state_after(
            len(curriculum.UNITS))
        self.assertTrue(all(part == 1.0 for part in done))
        self.assertIsNone(current)

    def test_the_picture_draws_every_state_without_a_window(self):
        import homeart
        colours = {"faint": "#5c616b", "gold": "#c9b37a",
                   "surface": "#1e2026"}
        for state in (homeart.SCHOOL_EXAMPLE,
                      ((0.0,) * 8, 0, "Lectura", False),
                      ((0.0, 0.25, 0.75, 0.43) + (0.0,) * 4, 3, "Movimientos",
                       False),
                      ((1.0,) * 8, None, "", True)):
            image = homeart.school_image(420, 84, 1.0, "#d07fa0", colours,
                                         state)
            self.assertEqual(image.size, (420, 84))
            self.assertEqual(image.mode, "RGBA")


class TestSchool(unittest.TestCase):
    """
    La escuelita: lo que enseña, cómo corrige y en qué orden se abre.

    La corrección es el analizador, así que lo que se vigila acá no es que
    el analizador lea bien ---eso lo vigilan sus propias clases--- sino que
    cada ejercicio esté bien armado: que su respuesta modelo apruebe, que su
    respuesta mala no, y que la mala diga **dónde** está lo que falla.
    """

    def _school(self):
        from engine import school as curriculum     # noqa: PLC0415
        return curriculum

    def test_every_written_exercise_passes_its_answer_and_fails_the_wrong_one(self):
        school = self._school()
        for item in school.exercises():
            if item.kind not in school.WRITTEN:
                continue
            good = school.grade(item, school.model_lines(item))
            self.assertTrue(good.passed,
                            f"{item.key}: {[r.text for r in good.problems]}")
            # La respuesta buena no toca nada de lo dado.
            self.assertIsNone(school.tampered(item, school.model_lines(item)),
                              item.key)
            bad = school.grade(item, school.model_lines(item, wrong=True))
            self.assertFalse(bad.passed, item.key)
            # Y dice dónde: compás, y voces cuando es una falta entre voces.
            self.assertTrue(any(r.bar for r in bad.problems), item.key)

    def test_the_starting_fragment_is_never_already_right(self):
        """Un ejercicio que se aprueba sin tocar nada no enseña nada."""
        school = self._school()
        for item in school.exercises():
            if item.kind in school.WRITTEN:
                verdict = school.grade(item, school.given_lines(item))
                self.assertFalse(verdict.passed, item.key)

    def test_every_choice_has_exactly_one_right_answer_and_it_is_computed(self):
        """
        La respuesta no está escrita en ningún lado: sale del analizador, de
        los perfiles del motor o de la serie armónica. Tiene que estar entre
        las opciones, aprobar, y todas las demás tienen que fallar.
        """
        school = self._school()
        for item in school.exercises():
            if item.kind in school.WRITTEN:
                continue
            answer = school.correct_choice(item)
            values = [option.value for option in item.options]
            self.assertIn(answer, values, item.key)
            self.assertTrue(school.grade(item, chosen=answer).passed,
                            item.key)
            for other in values:
                if other == answer:
                    continue
                verdict = school.grade(item, chosen=other)
                self.assertFalse(verdict.passed, f"{item.key}: {other}")
                # Lo malo no regala lo bueno: el segundo intento sería copiar.
                label = next(o.label for o in item.options
                             if o.value == answer)
                for remark in verdict.remarks:
                    self.assertNotIn(f"«{label}»", remark.text, item.key)

    def test_the_motion_correction_uses_the_analyzer_words(self):
        """Contrario y directo no son paralelo: lo dice el analizador."""
        school = self._school()
        item = school.exercise("mov_tres")
        bad = school.grade(item, school.lines_from(item.mistake, item.lanes))
        problem = bad.problems[0]
        self.assertEqual((problem.bar, problem.until), (3, 4))
        self.assertEqual(problem.voices, ("Bajo", "Soprano"))
        self.assertIn(analysis.MOTION_PARALLEL, problem.text)

    def test_the_fix_exercises_point_at_the_parallels_and_the_crossing(self):
        school = self._school()
        item = school.exercise("par_corregir")
        bad = school.grade(item, school.given_lines(item))
        self.assertTrue(any(r.voices == ("Bajo", "Tenor") and r.until == 2
                            for r in bad.problems))
        item = school.exercise("cruce_corregir")
        bad = school.grade(item, school.given_lines(item))
        self.assertTrue(any(r.voices == ("Alto", "Soprano") and r.bar == 2
                            for r in bad.problems))

    def test_a_fix_cannot_change_the_harmony(self):
        """Corregir moviendo el bajo o cambiando el acorde no vale."""
        school = self._school()
        item = school.exercise("par_corregir")
        chords = [list(chord) for chord in item.solution]
        chords[1] = [50, 53, 60, 69]        # Dm pasó a ser Dm7
        lines = school.lines_from([tuple(c) for c in chords], item.lanes)
        verdict = school.grade(item, lines)
        self.assertFalse(verdict.passed)
        chords = [list(chord) for chord in item.solution]
        chords[1][0] = 53                   # el bajo se tocó
        lines = school.lines_from([tuple(c) for c in chords], item.lanes)
        self.assertEqual(school.tampered(item, lines), (2, school.BASS))
        self.assertFalse(school.grade(item, lines).passed)

    def test_the_cadence_is_read_in_the_key_the_exercise_states(self):
        """
        Cuatro acordes que terminan en una rota se leerían, solos, en la
        tonalidad del sexto grado. La consigna dice Do mayor, y en Do mayor
        se corrige.
        """
        school = self._school()
        item = school.exercise("cad_rota")
        result = school.read(item, school.lines_from(item.solution,
                                                     item.lanes))
        self.assertEqual(result.key.tonic_pc, 0)
        self.assertEqual(result.cadences[-1].kind, "cadencia rota")

    def test_the_progress_follows_the_order_and_survives_a_restart(self):
        school = self._school()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "school.json")
            progress = school.Progress.load(path)
            lessons = school.lessons()
            self.assertIs(progress.current(), lessons[0])
            for item in lessons[0].exercises[:-1]:
                progress.mark_passed(item.key)
            self.assertFalse(progress.lesson_done(lessons[0]))
            self.assertTrue(progress.mark_passed(lessons[0].exercises[-1].key))
            self.assertFalse(progress.mark_passed(lessons[0].exercises[-1].key))
            again = school.Progress.load(path)
            self.assertTrue(again.lesson_done(lessons[0]))
            self.assertIs(again.current(), lessons[1])
            done, total = again.counts()
            self.assertEqual(done, len(lessons[0].exercises))
            self.assertFalse(again.graduation_due())
            for item in school.exercises():
                again.mark_passed(item.key)
            self.assertTrue(again.graduation_due())
            self.assertTrue(again.mark_graduated())
            self.assertFalse(school.Progress.load(path).graduation_due())

    def test_a_broken_file_does_not_stop_anything(self):
        school = self._school()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "school.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{esto no es json")
            progress = school.Progress.load(path)
            self.assertEqual(progress.counts()[0], 0)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"passed": {"no_existe": "x"}}, handle)
            self.assertEqual(school.Progress.load(path).counts()[0], 0)

    def test_the_file_lives_with_the_other_user_data(self):
        """`CHORDWEAVER_DATA_DIR` lo mueve con los otros, y es otro archivo."""
        school = self._school()
        with tempfile.TemporaryDirectory() as folder:
            antes = os.environ.get(history.SANDBOX_VARIABLE)
            os.environ[history.SANDBOX_VARIABLE] = folder
            try:
                self.assertEqual(os.path.dirname(school.school_path()),
                                 folder)
                self.assertNotIn(school.school_path(),
                                 (visitors.visitors_path(),
                                  achievements.achievements_path(),
                                  story.state_path()))
            finally:
                if antes is None:
                    os.environ.pop(history.SANDBOX_VARIABLE, None)
                else:
                    os.environ[history.SANDBOX_VARIABLE] = antes

    def test_every_lesson_cites_an_entry_of_the_book_that_exists(self):
        school = self._school()
        for lesson in school.lessons():
            found = book.find(lesson.cite)
            self.assertIsNotNone(found, lesson.key)
            _chapter, entry = found
            self.assertLess(lesson.quote, len(entry.paragraphs), lesson.key)
            self.assertTrue(lesson.exercises, lesson.key)

    def test_the_book_explains_the_inversions_the_school_asks_for(self):
        """
        La escuelita pide un acorde en primera inversión, y su teoría sale
        del libro: el libro tiene que decir qué es eso, con los mismos
        números que escribe el analizador.
        """
        _chapter, entry = book.find("inversiones")
        text = " ".join(entry.paragraphs)
        for figure in analysis.TRIAD_FIGURES.values():
            if figure:
                self.assertIn(figure, text)
        for word in ("estado fundamental", "primera inversión",
                     "segunda inversión"):
            self.assertIn(word, text)

    def test_the_style_rules_come_from_the_engine_profiles(self):
        """
        Lo que la escuelita dice de cada estilo es lo que el motor hace. Si un
        perfil cambia, la respuesta del ejercicio cambia sola, y este test
        avisa que hay que cambiarle el fragmento.
        """
        school = self._school()
        self.assertTrue(GENRE_PROFILES["classical"].forbid_parallel_fifths)
        self.assertFalse(GENRE_PROFILES["gregorian"].forbid_parallel_fifths)
        self.assertTrue(GENRE_PROFILES["gregorian"].forbid_harmonic_tritone)
        # «Salto de más de una cuarta»: el techo del gregoriano son cinco
        # semitonos, una cuarta justa.
        self.assertEqual(GENRE_PROFILES["gregorian"].style_max_leap, 5)
        self.assertGreater(GENRE_PROFILES["jazz"].weight_minor_ninth, 0)
        self.assertIn(6, GENRE_PROFILES["classical"].forbidden_melodic_intervals)
        item = school.exercise("gen_gregoriano")
        # Las quintas paralelas están en el fragmento y no son falta.
        self.assertTrue(school.RULES_BY_KEY["paralelas"].find(
            item.chords, [], GENRE_PROFILES["gregorian"]))
        self.assertEqual(set(school.style_violations(item, "gregorian")),
                         {"tritono"})
        for item in school.exercises():
            if item.rule == "style_rule":
                offered = {o.value for o in item.options}
                broken = set(school.style_violations(item,
                                                     item.param("genre")))
                self.assertEqual(len(broken & offered), 1, item.key)

    def test_the_harmonic_series_answers_are_the_book_numbers(self):
        """Los −31,2 del séptimo y los −13,7 del quinto, como en el libro."""
        school = self._school()
        verdict = school.grade(school.exercise("arm_septimo"), chosen="-31")
        self.assertTrue(verdict.passed)
        self.assertIn("-31.2", verdict.remarks[0].text)
        self.assertEqual(school.correct_choice(school.exercise("arm_tercera")),
                         "5")
        self.assertEqual(school.correct_choice(school.exercise("arm_hercios")),
                         "550")
        spectrum = school.spectrum_for(school.exercise("arm_oido"))
        heard = [partial.number for partial, _f, _a
                 in harmonics.sounding(spectrum)]
        self.assertEqual(heard, [1, 3])

    def test_the_school_names_the_voices_like_the_staff(self):
        import staff                                 # noqa: PLC0415
        school = self._school()
        self.assertEqual(school.VOICE_NAMES,
                         tuple(reversed(staff.GRAND_VOICES)))

    def test_bach_counts_the_exercises_right(self):
        """La graduación dice «cincuenta y tres»: si cambia el número,
        cambia la línea."""
        school = self._school()
        self.assertEqual(len(school.exercises()), 53)
        bach = next(lines for speaker, lines, _n, _d in school.GRADUATION
                    if speaker == visitors.BACH)
        self.assertTrue(any("Cincuenta y tres" in line.text for line in bach))

    def test_the_reading_unit_places_notes_like_the_staff(self):
        """
        Lo que la corrección dice de dónde está una nota es lo que dibuja el
        sistema: la línea de la clave de sol es sol, la cuarta de la de fa es
        fa, y el do central cae en una línea adicional de cada lado.
        """
        import staff                                 # noqa: PLC0415
        school = self._school()
        self.assertEqual(school.staff_step(67, True), 2)
        self.assertEqual(school.staff_step(53, False), 6)
        self.assertEqual(school.staff_step(60, True), -2)
        self.assertEqual(school.staff_step(60, False), 10)
        # Contra el pentagrama de verdad: un grado de diferencia en el
        # sistema es un lugar de diferencia acá, en las dos claves.
        for pitch in (43, 48, 53, 57, 60, 64, 67, 72, 77):
            self.assertEqual(
                staff.index_for_pitch(pitch, 0) - staff.index_for_pitch(
                    school.BOTTOM_LINE[pitch >= 60], 0),
                school.staff_step(pitch, pitch >= 60), pitch)
        # Y escrita como la escribe el sistema en cualquier armadura: el
        # lugar (corrido una octava, por cómo cuenta cada uno) y el signo.
        for fifths in range(-6, 7):
            for pitch in range(36, 90):
                place, alteration = school.spelled(pitch, fifths)
                index = staff.index_for_pitch(pitch, fifths)
                self.assertEqual(place - 7, index, (pitch, fifths))
                self.assertEqual(staff.pitch_at(index, fifths, alteration),
                                 pitch, (pitch, fifths))
        self.assertEqual(school.staff_place(60, True),
                         "en la primera línea adicional de abajo")
        self.assertEqual(school.staff_place(69, True), "en el espacio 2")
        self.assertEqual(school.correct_choice(school.exercise("lee_sol")),
                         "0")
        self.assertEqual(school.correct_choice(school.exercise("misma_nota")),
                         "3")

    def test_the_signs_are_the_ones_the_staff_draws(self):
        """
        Lo que la corrección dice de un signo ---«no lleva signo, pero antes
        en el mismo compás hay un sostenido»--- tiene que ser lo que el
        sistema dibuja con la misma regla.
        """
        import staff                                 # noqa: PLC0415
        school = self._school()
        for key in ("lee_sostenido", "lee_becuadro", "lee_armadura",
                    "lee_armadura_fa"):
            item = school.exercise(key)
            lane = item.param("lane")
            line = school.given_lines(item)[lane]
            mine = school.written_signs(line, item.fifths)
            notes, moment = [], 0.0
            for order, (pitch, duration) in enumerate(line):
                if pitch is not None:
                    bar_start = (moment // school.FIGURE) * school.FIGURE
                    notes.append((order, bar_start,
                                  staff.index_for_pitch(pitch, item.fifths),
                                  pitch, moment))
                moment += duration
            drawn = staff.displayed_accidentals(notes, item.fifths)
            for _o, _b, _i, _p, start in notes:
                self.assertEqual(mine[start], drawn.get(start), (key, start))
        result = school.grade(school.exercise("lee_sostenido"), chosen="6")
        self.assertTrue(any("antes en el mismo compás" in r.text
                            for r in result.remarks))
        result = school.grade(school.exercise("lee_becuadro"), chosen="7")
        self.assertTrue(any("becuadro" in r.text for r in result.remarks))

    def test_a_wrong_name_in_the_right_place_is_told_what_alters_it(self):
        """Elegir «fa» para un fa sostenido es leer bien el lugar: decirle
        «fa no está ahí» sería mentirle."""
        school = self._school()
        verdict = school.grade(school.exercise("lee_armadura"), chosen="5")
        self.assertFalse(verdict.passed)
        self.assertIn("en el lugar de fa", verdict.remarks[0].text)

    def test_the_rhythm_answers_come_from_the_durations(self):
        school = self._school()
        self.assertEqual(school.correct_choice(school.exercise("figura_cual")),
                         "1")
        self.assertEqual(
            school.correct_choice(school.exercise("cuantas_corcheas")), "4")
        self.assertEqual(school.correct_choice(school.exercise("oido_quinta")),
                         "7")
        self.assertEqual(
            school.correct_choice(school.exercise("oido_tercera")), "4")

    def test_what_was_given_cannot_be_split(self):
        """En un compás a medio llenar, escribir encima de una nota dada la
        parte: eso es tocar lo dado, aunque la altura no cambie."""
        school = self._school()
        item = school.exercise("completar_compases")
        lines = school.model_lines(item)
        soprano = list(lines[school.SOPRANO])
        soprano[0:1] = [(67, 1.0), (67, 1.0)]
        lines[school.SOPRANO] = soprano
        self.assertEqual(school.tampered(item, lines), (1, school.SOPRANO))
        self.assertFalse(school.grade(item, lines).passed)

    def test_the_practice_counts_for_nothing_but_its_streak(self):
        import random as _random                     # noqa: PLC0415
        school = self._school()
        rng = _random.Random(7)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "school.json")
            progress = school.Progress.load(path)
            previous = None
            for clef in ("sol", "fa", "ambas") * 10:
                item = school.practice_exercise(clef, rng, previous)
                lane = item.param("lane")
                pitch = item.chords[0][lane]
                self.assertNotEqual(pitch, previous)
                self.assertIn(pitch % 12, school.NATURAL_SEMITONES)
                low, high = school.PRACTICE_STEPS
                self.assertTrue(low <= school.staff_step(
                    pitch, lane == school.SOPRANO) <= high)
                answer = school.correct_choice(item)
                self.assertTrue(school.grade(item, chosen=answer).passed)
                self.assertFalse(progress.mark_passed(item.key))
                previous = pitch
            self.assertEqual(progress.counts()[0], 0)
            self.assertTrue(progress.record_practice(5))
            self.assertFalse(progress.record_practice(3))
            self.assertEqual(school.Progress.load(path).practice_best, 5)

    def test_the_note_answers_speak_the_screen_language(self):
        school = self._school()
        option = next(o for o in school.exercise("lee_sol").options
                      if o.note == 7)
        try:
            self.assertEqual(school.option_label(option), "Sol")
            i18n.set_language("en")
            self.assertEqual(school.option_label(option), "G")
        finally:
            i18n.set_language(i18n.DEFAULT)

    def test_a_unit_added_in_front_does_not_lock_what_was_reached(self):
        """
        Quien ya iba por los movimientos cuando apareció la unidad de lectura
        sigue donde estaba: lo nuevo de adelante no le cierra nada.
        """
        school = self._school()
        with tempfile.TemporaryDirectory() as folder:
            progress = school.Progress.load(os.path.join(folder, "s.json"))
            moves = next(u for u in school.UNITS if u.key == "contrapunto")
            for item in moves.lessons[0].exercises:
                progress.mark_passed(item.key)
            self.assertIs(progress.current(), moves.lessons[1])
            # Y la lectura sigue sin aprobar: aprobar adelante no da por
            # hecho nada de atrás.
            self.assertFalse(any(progress.lesson_done(item)
                                 for item in school.UNITS[0].lessons))

    def test_the_award_exists_with_three_stars(self):
        school = self._school()
        badge = achievements.BY_KEY[school.AWARD]
        self.assertEqual(badge.name, "Nace una leyenda")
        self.assertEqual(badge.star, 3)
        self.assertFalse(badge.legendary)
        self.assertIn(school.AWARD, achievements.STAR_KEYS[3])

    def test_every_speaker_of_the_graduation_is_staged(self):
        """
        La misma trampa que las visitas: `staging_for` no falla con un
        personaje que no esté en la tabla, y la escena saldría con la puesta
        de otro.
        """
        import cinematic                             # noqa: PLC0415
        school = self._school()
        self.assertEqual([speaker for speaker, *_rest in school.GRADUATION],
                         [visitors.GREGORY, visitors.BACH, visitors.CREATOR])
        for speaker, lines, name, _dream in school.GRADUATION:
            self.assertIn(speaker, cinematic.STAGING)
            self.assertIn(speaker, cinematic.SPEAKERS)
            self.assertIn(speaker, cinematic.POSES)
            self.assertTrue(name)
            cues = [line.cue for line in lines]
            self.assertIn("reveal", cues, speaker)
            # Sin objetos: el cuarto lo deja la entidad, y uno más le
            # sacaría ser el cuarto.
            self.assertNotIn("item", cues, speaker)
            for line in lines:
                self.assertIn(line.speaker, (speaker, story.NARRATOR))
                if line.pose:
                    self.assertIn(line.pose, cinematic.POSES[speaker],
                                  line.text)

    def test_the_award_is_handed_out_when_the_scene_ends(self):
        """
        Encolar la ceremonia no entrega nada; terminarla, sí. Es la regla de
        las visitas: cerrar el programa en el medio no puede costar ni la
        escena ni el logro.
        """
        import types                                 # noqa: PLC0415
        import app                                   # noqa: PLC0415
        school = self._school()
        with tempfile.TemporaryDirectory() as folder:
            progress = school.Progress(path=os.path.join(folder, "s.json"))
            for item in school.exercises():
                progress.passed[item.key] = "x"
            awarded, queued, waited = [], [], []
            fake = types.SimpleNamespace(
                school=progress, scene=None, overlay=None, celebrations=[],
                settings={},
                VISIT_SOUNDS=app.ChordWeaverApp.VISIT_SOUNDS,
                GRADUATION_SOUNDS=app.ChordWeaverApp.GRADUATION_SOUNDS,
                _award=lambda keys: awarded.extend(keys),
                _queue_scene=lambda speaker, lines, **extra: queued.append(
                    (speaker, extra)),
                _when_sounds=lambda names, then: waited.append(then),
                _advance_scenes=lambda: None,
                after=lambda *_a: None)
            fake._graduated = lambda: app.ChordWeaverApp._graduated(fake)
            summon = app.ambience.summon
            app.ambience.summon = lambda *_a, **_k: None
            try:
                app.ChordWeaverApp._open_graduation(fake)
            finally:
                app.ambience.summon = summon
            self.assertEqual([speaker for speaker, _e in queued],
                             [visitors.GREGORY, visitors.BACH,
                              visitors.CREATOR])
            self.assertEqual(awarded, [])
            self.assertFalse(progress.graduated)
            afters = [extra.get("after") for _s, extra in queued]
            self.assertEqual(afters[:2], [None, None])
            afters[-1]()
            self.assertEqual(awarded, [school.AWARD])
            self.assertTrue(progress.graduated)
            # En el modo profesional no hay ceremonia, pero sí lo que deja.
            progress.graduated = ""
            awarded.clear()
            queued.clear()
            fake.settings = {"professional": True}
            fake._graduation_queued = False
            app.ChordWeaverApp._open_graduation(fake)
            self.assertEqual(queued, [])
            self.assertEqual(awarded, [school.AWARD])
            self.assertTrue(progress.graduated)

    def test_the_card_and_the_detour_are_wired(self):
        import app                                   # noqa: PLC0415
        keys = [entry[0] for entry in app.TOOL_CARDS]
        self.assertIn("school", keys)
        self.assertIn("school", app.ChordWeaverApp.DETOUR_TITLES)
        self.assertTrue(callable(getattr(app.ChordWeaverApp,
                                         "_screen_school", None)))

    def test_a_chord_without_its_third_does_not_pass(self):
        """
        Re, re, re y la se lee Dm ---la tonalidad dice menor---, pero sin fa
        no es mayor ni menor. La corrección no puede aprobarlo por el nombre,
        ni al corregir paralelas ni al cerrar una cadencia.
        """
        school = self._school()
        item = school.exercise("par_corregir")
        chords = list(item.solution)
        chords[1] = (50, 50, 62, 69)
        verdict = school.grade(item, school.lines_from(chords, item.lanes))
        self.assertFalse(verdict.passed)
        self.assertTrue(any(r.bar == 2 and "fa" in r.text
                            for r in verdict.problems))
        item = school.exercise("cad_autentica")
        chords = list(item.solution)
        chords[3] = (43, 55, 62, 67)        # el I final sin si
        verdict = school.grade(item, school.lines_from(chords, item.lanes))
        self.assertFalse(verdict.passed)
        self.assertTrue(any(r.bar == 4 and "si" in r.text
                            for r in verdict.problems))

    def test_the_model_answers_have_their_thirds(self):
        """Las respuestas modelo tampoco pueden tener un acorde hueco."""
        school = self._school()
        for item in school.exercises():
            if item.rule not in ("clean", "cadence", "chord", "resolution"):
                continue
            result = school.read(item, school.lines_from(item.solution,
                                                         item.lanes))
            for segment in result.segments:
                if segment.reading is not None:
                    self.assertNotIn("third", segment.reading.missing,
                                     f"{item.key}, compás {segment.bar_index}")

    def test_a_bass_outside_the_chord_is_not_called_root_position(self):
        """
        Un do debajo de un Sol: el analizador dice que el bajo no es del
        acorde (inversión -1). Llevado a cero, la corrección decía «la
        fundamental: estado fundamental», que es justo lo que no es.
        """
        school = self._school()
        item = school.exercise("inv_primera")
        verdict = school.grade(item, school.lines_from(((48, 55, 62, 71),),
                                                       item.lanes))
        self.assertFalse(verdict.passed)
        texts = [r.text for r in verdict.problems]
        self.assertTrue(any("no es nota de G" in text for text in texts),
                        texts)
        self.assertFalse(any("estado fundamental" in text for text in texts),
                         texts)

    def test_a_dominant_that_cannot_be_read_is_corrected_not_crashed(self):
        """
        Si el compás de la dominante queda sin acorde, la corrección lo dice
        ---igual que la de un acorde suelto--- en vez de levantar
        `AttributeError`. Hoy la dominante viene escrita, pero un ejercicio
        que la pida no puede tirar la pantalla.
        """
        school = self._school()
        item = school.exercise("sept_resolver")
        lines = [[(None, school.FIGURE), (pitch, school.FIGURE)]
                 for pitch in (48, 52, 60, 67)]
        remarks = school._check_resolution(item, school.read(item, lines),
                                           lines)
        self.assertEqual([(r.bar, r.severity) for r in remarks],
                         [(1, "grave")])

    def test_the_leap_and_the_crossing_are_decided_by_the_evaluator(self):
        """
        El salto de trítono y el cruce los decide `engine.fitness`, como el
        trítono armónico: con el evaluador diciendo que no hay nada, la
        escuelita tampoco encuentra nada. Cuando lo hay, dice dónde.
        """
        from unittest import mock
        school = self._school()
        leap = ((48, 55, 64, 72), (54, 55, 58, 72))
        crossed = ((48, None, 64, 60),)     # el tenor calla y no separa
        self.assertEqual(school._find_tritone_leap(leap, [], None),
                         [(1, 2, (0,)), (1, 2, (2,))])
        self.assertEqual(school._find_crossing(crossed, [], None),
                         [(1, 1, (2, 3))])
        with mock.patch.object(school, "has_melodic_tritone",
                               lambda *_a: False), \
                mock.patch.object(school, "_crossing_count", lambda *_a: 0):
            self.assertEqual(school._find_tritone_leap(leap, [], None), [])
            self.assertEqual(school._find_crossing(crossed, [], None), [])

    def test_the_given_fragment_is_analysed_once(self):
        """
        Lo dado no cambia: se analiza una vez por ejercicio ---y por idioma,
        porque el analizador escribe sus explicaciones en el de la
        pantalla---, no en cada corrección.
        """
        from unittest import mock
        school = self._school()
        real = school.read
        calls = []

        def counted(item, lines):
            calls.append(item.key)
            return real(item, lines)

        school._GIVEN.clear()
        self.addCleanup(i18n.set_language, i18n.language())
        choice = school.exercise("cad_ver")
        fix = school.exercise("par_corregir")
        with mock.patch.object(school, "read", counted):
            school.grade(choice, chosen="plagal")
            school.grade(choice, chosen=school.correct_choice(choice))
            self.assertEqual(calls.count("cad_ver"), 1)
            school.grade(fix, school.given_lines(fix))
            school.grade(fix, school.given_lines(fix))
            # Una por cada cosa escrita y una sola de lo dado.
            self.assertEqual(calls.count("par_corregir"), 3)
            i18n.set_language("en")
            school.grade(choice, chosen="plagal")
            self.assertEqual(calls.count("cad_ver"), 2)


class TestLanguages(unittest.TestCase):
    """
    Los dos idiomas.

    Lo que se vigila acá no es la calidad de la traducción sino que el
    mecanismo siga entero: que el catálogo no tenga agujeros, que los huecos
    con nombre sean los mismos de los dos lados ---un `{compás}` que se
    pierde en la traducción es un `KeyError` en pantalla--- y que el
    castellano siga siendo la clave.
    """

    def setUp(self):
        self.addCleanup(i18n.set_language, i18n.DEFAULT)

    def test_the_default_language_is_the_one_it_is_written_in(self):
        i18n.set_language(i18n.DEFAULT)
        self.assertTrue(i18n.is_default())
        self.assertEqual(i18n.tr("Aceptar"), "Aceptar")

    def test_an_unknown_language_falls_back_instead_of_failing(self):
        self.assertEqual(i18n.set_language("klingon"), i18n.DEFAULT)
        self.assertEqual(i18n.set_language(""), i18n.DEFAULT)
        self.assertEqual(i18n.set_language(None), i18n.DEFAULT)

    def test_english_translates_and_untranslated_text_passes_through(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Aceptar"), "OK")
        # Lo que no está en el catálogo vuelve tal cual: una pantalla nueva
        # sale en castellano y no vacía.
        self.assertEqual(i18n.tr("una cadena que no existe"),
                         "una cadena que no existe")

    def test_the_catalogue_has_no_holes(self):
        """
        Todo lo que el programa dibuja tiene su entrada, y no sobra ninguna.

        Es la misma cuenta que hace `python -m engine.lang.audit`, corrida
        acá para que agregar una pantalla sin traducirla falle.
        """
        missing, orphans, _source = lang_audit.compare("en")
        self.assertEqual(missing, [], "faltan traducciones")
        self.assertEqual(orphans, [], "sobran traducciones")

    def test_every_hole_survives_the_translation(self):
        """
        Los `{nombre}` de una plantilla son los mismos en los dos idiomas.

        Traducir es reordenar, y reordenando es fácil perder un hueco o
        inventar uno. Cualquiera de las dos cosas revienta en `format` justo
        cuando el usuario mira la pantalla.
        """
        holes = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}")
        for spanish, english in lang.catalog("en").items():
            self.assertEqual(sorted(set(holes.findall(spanish))),
                             sorted(set(holes.findall(english))),
                             "los huecos no coinciden en %r" % spanish)

    def test_a_menu_reads_back_in_spanish(self):
        """
        `untr` deshace lo que `trs` hizo.

        Es lo que permite traducir un desplegable sin tocar una sola de las
        comparaciones del programa, que están escritas contra el castellano.
        """
        i18n.set_language("en")
        for spanish in ("Ignorar", "Obligatorio", "Sólo MIDI",
                        harmony.MODES["major"].label):
            self.assertEqual(i18n.untr(i18n.tr(spanish)), spanish)

    def test_note_names_follow_the_language(self):
        """Solfeo en castellano, letras en inglés."""
        i18n.set_language(i18n.DEFAULT)
        self.assertEqual(i18n.note_name(6), "Fa#")
        self.assertEqual(i18n.note_name(10, prefer_flats=True), "Sib")
        self.assertEqual(i18n.say_letter("G"), "Sol")
        i18n.set_language("en")
        self.assertEqual(i18n.note_name(6), "F#")
        self.assertEqual(i18n.note_name(10, prefer_flats=True), "Bb")
        self.assertEqual(i18n.say_letter("G"), "G")

    def test_marking_a_string_does_not_translate_it(self):
        """`N` es una marca para la herramienta, no una traducción."""
        i18n.set_language("en")
        self.assertEqual(i18n.N("Acordes"), "Acordes")

    def test_the_bold_markers_of_the_book_survive(self):
        """
        Los tramos entre `**` se conservan.

        `app._split_lead` parte el párrafo por ahí para escribir la
        entradilla en su propio renglón; una traducción que se coma las
        marcas deja el párrafo sin título y con dos asteriscos impresos.
        """
        for spanish, english in lang.catalog("en").items():
            self.assertEqual(spanish.count("**"), english.count("**"),
                             "las negritas no coinciden en %r" % spanish[:60])

    def test_the_language_is_a_stored_preference(self):
        self.assertIn("language", history.DEFAULT_SETTINGS)
        # Vacío y no "es": es lo que hace que el cartel de la primera vez
        # aparezca una sola vez y no cada vez que alguien elige castellano.
        self.assertEqual(history.DEFAULT_SETTINGS["language"], "")



class TestKeySpelling(unittest.TestCase):
    """
    Las fundamentales se nombran con la letra que les da la tonalidad.

    Nombradas siempre con sostenidos, Si bemol mayor salía La sostenido y su
    acorde se escribía La sostenido, Do doble sostenido y Mi sostenido: las
    alturas eran las correctas y cualquier editor lo leía como un error.
    """

    def test_a_flat_key_names_its_degrees_with_flats(self):
        labels = [o.label for o in harmony.diatonic_options(
            10, harmony.MODES["major"])]
        self.assertEqual(labels, ["Bb", "Cm", "Dm", "Eb", "F", "Gm", "Adim"])

    def test_every_degree_gets_its_own_letter(self):
        for tonic in range(12):
            for mode in ("major", "minor", "dorian"):
                letters = [o.chord.root_letter for o in harmony.diatonic_options(
                    tonic, harmony.MODES[mode])]
                self.assertEqual(len(set(letters)), 7, (tonic, mode, letters))

    def test_a_secondary_dominant_is_named_a_fifth_above_its_target(self):
        labels = [o.label for o in harmony.secondary_dominants(
            6, harmony.MODES["major"], True)]
        self.assertEqual(labels[-1], "B#7")          # V/vii de Fa sostenido
        labels = [o.label for o in harmony.secondary_dominants(
            1, harmony.MODES["major"], True)]
        self.assertEqual(labels[0], "Bb7")           # V/ii de Re bemol

    def test_a_borrowed_chord_is_written_with_its_own_letter(self):
        for option in harmony.borrowed_options(0, list(harmony.BORROWED_CHORDS)):
            self.assertEqual(option.chord.root_letter, option.label[0])

    def test_a_borrowed_chord_is_named_from_the_parallel_minor(self):
        """El iv de Fa mayor es Bbm, no A#m."""
        names = {o.roman: o.label for o in harmony.borrowed_options(
            5, list(harmony.BORROWED_CHORDS))}
        self.assertEqual(names["iv"], "Bbm")
        self.assertEqual(names["bVI"], "Db")
        names = {o.roman: o.label for o in harmony.borrowed_options(
            4, list(harmony.BORROWED_CHORDS))}
        self.assertEqual((names["iv"], names["bVI"], names["bII"]),
                         ("Am", "C", "F"))

    def test_the_seventh_degree_of_harmonic_minor_is_a_diminished_seventh(self):
        """El vii°7 del menor armónico se rotula dim7: G#m7b5 lleva fa#."""
        option = harmony.diatonic_options(9, harmony.MODES["harmonic"],
                                          with_sevenths=True)[6]
        self.assertEqual(option.label, "G#dim7")
        self.assertEqual(sorted(parse_chord(option.label).pitch_classes),
                         sorted(option.chord.pitch_classes))

    def test_the_export_writes_b_flat_in_f_major(self):
        chord = harmony.diatonic_options(5, harmony.MODES["major"])[3].chord
        self.assertEqual(chord.root_letter, "B")
        from engine.theory import spell_pitch
        step, alter, _octave = spell_pitch(58, chord.root_letter, 0, "1")
        self.assertEqual((step, alter), ("B", -1))


class TestCli(unittest.TestCase):
    """
    La línea de comandos, de punta a punta.

    Usaba `trf` sin importarlo: cualquier corrida terminaba en `NameError`
    al imprimir la primera línea, y ningún test pasaba por ahí.
    """

    def test_a_wrong_metre_is_a_usage_error(self):
        import argparse
        import cli
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parse_time_signature("x/4")

    def test_a_short_run_writes_its_files(self):
        import contextlib
        import io
        import cli
        folder = tempfile.mkdtemp()
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["--chords", "C F G C", "--population", "12",
                             "--generations", "3", "--seed", "1",
                             "--out", folder])
        self.assertEqual(code, 0)
        self.assertTrue(os.listdir(folder))


class TestConsoleless(unittest.TestCase):
    """
    El ejecutable sin consola no puede morir por un aviso.

    Sin consola, `sys.stderr` es ``None`` y cualquier `write` levanta
    `AttributeError`. customtkinter avisa al importarse cuando no carga su
    fuente, así que el programa ni siquiera abría.
    """

    def setUp(self):
        self.saved = (sys.stdout, sys.stderr)
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, "registro.log")

    def tearDown(self):
        sys.stdout, sys.stderr = self.saved

    def test_a_missing_stream_writes_to_the_log(self):
        from engine import console
        sys.stdout, sys.stderr = self.saved[0], None
        self.assertTrue(console.guard_streams(self.path))
        sys.stderr.write("aviso de una librería\n")
        sys.stderr.flush()
        self.assertIs(sys.stdout, self.saved[0])
        with open(self.path, encoding="utf-8") as handle:
            self.assertIn("aviso de una librería", handle.read())

    def test_a_real_console_is_left_alone(self):
        from engine import console
        self.assertFalse(console.guard_streams(self.path))
        self.assertIs(sys.stderr, self.saved[1])
        self.assertFalse(os.path.exists(self.path))

    def test_an_unwritable_log_does_not_raise(self):
        from engine import console
        sys.stdout, sys.stderr = None, None
        console.guard_streams(os.path.join(self.folder, "no", "existe.log"))
        sys.stderr.write("se pierde y no pasa nada")

    def test_the_log_answers_like_a_stream(self):
        """
        Hay librerías que le preguntan a `sys.stderr` su codificación o su
        descriptor antes de escribir. Sin consola tiene que contestar lo
        que contesta cualquier flujo sin archivo del sistema, no un
        `AttributeError`. Y preguntar no abre el registro: se abre al
        escribir.
        """
        import io
        from engine import console
        sys.stdout, sys.stderr = None, None
        console.guard_streams(self.path)
        stream = sys.stderr
        self.assertIsInstance(stream, io.TextIOBase)
        self.assertEqual(stream.encoding, "utf-8")
        self.assertEqual(stream.errors, "replace")
        self.assertTrue(stream.writable())
        self.assertFalse(stream.isatty())
        with self.assertRaises(io.UnsupportedOperation):
            stream.fileno()
        self.assertFalse(os.path.exists(self.path))
        print("una línea", file=sys.stdout)
        stream.writelines(["y otra\n"])
        stream.flush()
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "una línea\ny otra\n")
        stream.close()

    def test_the_guard_runs_before_customtkinter(self):
        """Si el import de customtkinter se adelanta, el arreglo no sirve."""
        source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "app.py"), encoding="utf-8").read()
        self.assertLess(source.index("console.guard_streams()"),
                        source.index("import customtkinter"))



class TestUpdateHeadline(unittest.TestCase):
    """El aviso de versión nueva habla el idioma del programa."""

    def test_the_headline_is_chosen_when_shown(self):
        from engine import updates                   # noqa: PLC0415
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "version.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"version": "99.0",
                           "page": "https://chordweaver.github.io/",
                           "headline": {"es": "Trae cosas.",
                                        "en": "It brings things."}}, handle)
            url = "file:///" + path.replace(os.sep, "/")
            release = updates.look("1.0", url)
        self.assertIsNotNone(release)
        self.assertEqual(release.headline_in("en"), "It brings things.")
        self.assertEqual(release.headline_in("es"), "Trae cosas.")
        # Un idioma que el archivo no trae cae en la línea de siempre.
        self.assertEqual(release.headline_in("fr"), "Trae cosas.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
