# -*- coding: utf-8 -*-
"""
Command-line front end for the ChordWeaver engine.

The graphical application is the intended way in, but this exists so the
algorithm can be driven, scripted and sanity-checked without a display.

Examples
--------
    python cli.py --chords "Cmaj7 Am7 Dm7 G7" --genre jazz
    python cli.py --chords "C Am F G C F G C" --genre chorale --voices B,T,A,S
    python cli.py --chords "Dm7 G7 Cmaj7" --duration 1 --time 3/4 --no-parallel-fifths
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from engine import history, session
from engine.export import TimeSignature
from engine.fitness import GENRE_PROFILES
from engine.ga import GAConfig
from engine.theory import VOICE_CATALOG, note_name


def parse_time_signature(text: str) -> TimeSignature:
    """Leer un compás como ``4/4``.

    Con ``argparse.ArgumentTypeError`` el error sale como el de cualquier otra
    opción mal escrita --- una línea diciendo qué está mal --- en vez del
    traceback de ``int()`` que salía antes, que le pedía al usuario leer el
    código para enterarse de que se había equivocado tipeando.
    """
    beats, _, beat_type = text.partition("/")
    try:
        top, bottom = int(beats), int(beat_type or 4)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"compás inválido: {text!r}. Se escribe como 4/4 o 6/8.")
    if top < 1 or bottom < 1:
        raise argparse.ArgumentTypeError(
            f"compás inválido: {text!r}. Los dos números tienen que ser "
            f"mayores que cero.")
    return TimeSignature(top, bottom)


def positive_duration(text: str) -> float:
    """Una duración en negras. Cero escribe un MusicXML que ningún editor lee."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"duración inválida: {text!r}")
    if value <= 0:
        raise argparse.ArgumentTypeError(
            "la duración tiene que ser mayor que cero: con 0 la partitura "
            "sale con notas de duración nula y no la abre ningún editor.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimise voice leading across a chord progression."
    )
    parser.add_argument("--chords", required=True,
                        help="Space-separated chord symbols, e.g. \"C Am F G\"")
    parser.add_argument("--genre", default="classical", choices=sorted(GENRE_PROFILES))
    parser.add_argument("--voices", default="B,T,A,S",
                        help=f"Comma-separated voice keys from: {', '.join(VOICE_CATALOG)}")
    parser.add_argument("--duration", type=positive_duration, default=2.0,
                        help="Chord duration in quarter notes (4, 2, 1 or 0.5)")
    parser.add_argument("--time", type=parse_time_signature,
                        default=TimeSignature(4, 4),
                        help="Time signature, e.g. 4/4 or 6/8")
    parser.add_argument("--tempo", type=int, default=90)
    parser.add_argument("--title", default="ChordWeaver")
    parser.add_argument("--out", default=None,
                        help="Output folder (defaults to <app folder>/output)")
    parser.add_argument("--format", default="both", choices=["musicxml", "midi", "both"])
    parser.add_argument("--population", type=int, default=200)
    parser.add_argument("--generations", type=int, default=300)
    parser.add_argument("--seed", type=int, default=None)

    switches = parser.add_argument_group("rule switches")
    switches.add_argument("--no-parallel-fifths", dest="forbid_parallel_fifths",
                          action="store_true", default=None)
    switches.add_argument("--allow-parallel-fifths", dest="forbid_parallel_fifths",
                          action="store_false", default=None)
    switches.add_argument("--no-parallel-octaves", dest="forbid_parallel_octaves",
                          action="store_true", default=None)
    switches.add_argument("--allow-parallel-octaves", dest="forbid_parallel_octaves",
                          action="store_false", default=None)
    switches.add_argument("--no-tritone", dest="forbid_melodic_tritone",
                          action="store_true", default=None)
    switches.add_argument("--allow-tritone", dest="forbid_melodic_tritone",
                          action="store_false", default=None)
    switches.add_argument("--allow-crossing", dest="forbid_voice_crossing",
                          action="store_false", default=None)
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    symbols = args.chords.split()
    signature = args.time
    quarters_per_bar = signature.quarters_per_bar

    # Pack chords into bars until each bar is full.
    entries: List[session.ChordEntry] = []
    bar_index, filled = 0, 0.0
    for symbol in symbols:
        if filled + args.duration > quarters_per_bar + 1e-9:
            bar_index += 1
            filled = 0.0
        entries.append(session.ChordEntry(symbol, args.duration, bar_index))
        filled += args.duration

    overrides = {
        key: value
        for key, value in (
            ("forbid_parallel_fifths", args.forbid_parallel_fifths),
            ("forbid_parallel_octaves", args.forbid_parallel_octaves),
            ("forbid_melodic_tritone", args.forbid_melodic_tritone),
            ("forbid_voice_crossing", args.forbid_voice_crossing),
        )
        if value is not None
    }

    request = session.JobRequest(
        genre_key=args.genre,
        voice_keys=args.voices.split(","),
        entries=entries,
        time_signature=signature,
        title=args.title,
        tempo_bpm=args.tempo,
        switch_overrides=overrides,
        ga_config=GAConfig(
            population_size=args.population,
            generations=args.generations,
            random_seed=args.seed,
        ),
    )

    print(f"Genre: {args.genre} | voices: {args.voices} | {signature} | {len(entries)} chords")
    outcome = session.generate(request)

    for warning in outcome.warnings:
        print(f"  warning: {warning}")
    if not outcome.succeeded:
        for error in outcome.errors:
            print(f"  error: {error}")
        return 1

    print(f"\nSearched {outcome.result.generations_run} generations, "
          f"{outcome.result.evaluated} evaluations.\n")
    for index, solution in enumerate(outcome.result.solutions, start=1):
        print(f"Option {index}  (cost {solution.cost:.0f})")
        for slot_index, slot in enumerate(outcome.spec.slots):
            pitches = " ".join(
                note_name(p).ljust(4) for p in reversed(solution.slots[slot_index])
            )
            print(f"   {slot.symbol:<9} {pitches}")
        print()

    formats = ("musicxml", "midi") if args.format == "both" else (args.format,)
    written = session.export_outcome(request, outcome, args.out, formats)
    print("Written:")
    for path in written:
        print(f"   {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
