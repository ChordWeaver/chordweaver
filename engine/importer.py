# -*- coding: utf-8 -*-
"""
Reading a score back in.

Lets the user start from music that already exists: the file is parsed into
the same chord entries the manual mode works with, so an imported piece can
be re-voiced, ornamented and exported exactly like one typed by hand.

What is read
------------
* **The chords** -- what sounds at each rhythmic position, matched against
  the chord vocabulary and named in American notation.
* **The order of the voices** -- which part sings which note. This is kept
  as the starting arrangement and as what the padlock offers, but the search
  is free to change it. That is the point of importing: you bring the
  harmony, the program finds a better way to sing it. Only a padlock makes
  an arrangement binding.
* **The rhythm** -- durations and bar positions, so the imported piece keeps
  its shape.

Parsed with the standard library alone; MusicXML is plain XML and pulling in
a notation library for this would be a heavy dependency for a small job.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .theory import (
    LETTER_SEMITONES,
    QUALITY_TEMPLATES,
    SHARP_NAMES,
    Chord,
    ChordTone,
    ROLE_ROOT,
    parse_chord,
)


class ImportError_(Exception):
    """Raised when a file cannot be read as a score."""


@dataclass
class ImportedChord:
    """One sounding moment recovered from a file."""

    pitches: List[int]              # lowest voice first
    duration_quarters: float
    bar_index: int
    symbol: str = ""
    matched: bool = True            # False when no chord name fitted


@dataclass
class ImportedScore:
    chords: List[ImportedChord] = field(default_factory=list)
    voice_count: int = 0
    beats: int = 4
    beat_type: int = 4
    warnings: List[str] = field(default_factory=list)

    @property
    def bar_count(self) -> int:
        return len({chord.bar_index for chord in self.chords})


def _text(node: Optional[ET.Element], default: str = "") -> str:
    return node.text.strip() if node is not None and node.text else default


def _pitch_to_midi(pitch: ET.Element) -> Optional[int]:
    step = _text(pitch.find("step"))
    if step not in LETTER_SEMITONES:
        return None
    alter = int(float(_text(pitch.find("alter"), "0") or 0))
    octave = int(_text(pitch.find("octave"), "4") or 4)
    return LETTER_SEMITONES[step] + alter + (octave + 1) * 12


def _load_root(path: str) -> ET.Element:
    """Open a .musicxml or a compressed .mxl."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            # A compressed score points at its real content from META-INF.
            names = [n for n in archive.namelist()
                     if n.endswith((".xml", ".musicxml"))
                     and not n.startswith("META-INF")]
            if not names:
                raise ImportError_("El archivo comprimido no contiene una partitura.")
            with archive.open(names[0]) as handle:
                return ET.parse(handle).getroot()
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ImportError_(f"No se pudo leer el archivo: {exc}") from exc


def read_musicxml(path: str) -> ImportedScore:
    """
    Read a score into chord entries.

    Notes are collected by their onset, because that is what makes a chord:
    everything sounding at the same moment belongs together, whatever part
    or staff it was written on. Walking the parts and trusting them to line
    up breaks on the first piece whose voices have different rhythms.
    """
    root = _load_root(path)
    score = ImportedScore()

    divisions = 1.0
    beats, beat_type = 4, 4
    #: onset in quarter notes -> list of (pitch, bar index)
    events: Dict[float, List[int]] = {}
    onset_bar: Dict[float, int] = {}
    onset_duration: Dict[float, float] = {}

    bar_start = 0.0
    for bar_index, measure in enumerate(root.iter("measure")):
        attributes = measure.find("attributes")
        if attributes is not None:
            divisions_node = attributes.find("divisions")
            if divisions_node is not None:
                divisions = float(_text(divisions_node, "1") or 1)
            time_node = attributes.find("time")
            if time_node is not None:
                beats = int(_text(time_node.find("beats"), "4") or 4)
                beat_type = int(_text(time_node.find("beat-type"), "4") or 4)

        cursor = bar_start
        longest = cursor
        previous_duration = 0.0
        # Walked in document order, because <backup> and <forward> move the
        # cursor and only make sense in sequence. Reading just the <note>
        # elements ignores those rewinds, and every voice then lands at a
        # different moment -- which turned a four-part chorale into thirty-two
        # one-note "chords".
        for element in measure:
            if element.tag == "backup":
                cursor -= float(_text(element.find("duration"), "0") or 0) / divisions
                previous_duration = 0.0
                continue
            if element.tag == "forward":
                cursor += float(_text(element.find("duration"), "0") or 0) / divisions
                previous_duration = 0.0
                continue
            if element.tag != "note":
                continue

            duration = float(_text(element.find("duration"), "0") or 0) / divisions
            is_chord = element.find("chord") is not None
            is_rest = element.find("rest") is not None
            pitch_node = element.find("pitch")

            if is_chord:
                # Sounds with the previous note rather than after it.
                cursor -= previous_duration

            if not is_rest and pitch_node is not None:
                midi = _pitch_to_midi(pitch_node)
                if midi is not None:
                    events.setdefault(cursor, []).append(midi)
                    onset_bar.setdefault(cursor, bar_index)
                    onset_duration[cursor] = max(
                        onset_duration.get(cursor, 0.0), duration
                    )

            cursor += duration
            previous_duration = duration
            longest = max(longest, cursor)

        # <backup> rewinds within a bar; taking the furthest point reached
        # keeps the next bar starting where it should.
        bar_start = max(longest, bar_start + beats * 4.0 / beat_type)

    score.beats, score.beat_type = beats, beat_type
    if not events:
        raise ImportError_("La partitura no tiene notas que leer.")

    # A chord is three or more notes sounding together. Anything thinner is
    # ornament -- a passing note moves while the rest of the texture holds,
    # so it shows up as a one- or two-note event between the real chords.
    # Reading those as chords of their own distorted the whole progression.
    MIN_NOTES_FOR_CHORD = 3
    skipped = 0
    for onset in sorted(events):
        pitches = sorted(events[onset])
        if len(pitches) < MIN_NOTES_FOR_CHORD:
            skipped += 1
            continue
        chord = ImportedChord(
            pitches=pitches,
            duration_quarters=onset_duration.get(onset, 1.0) or 1.0,
            bar_index=onset_bar.get(onset, 0),
        )
        symbol = identify_chord(pitches)
        chord.symbol = symbol or "-".join(SHARP_NAMES[p % 12] for p in pitches)
        chord.matched = symbol is not None
        score.chords.append(chord)

    if not score.chords:
        raise ImportError_(
            "No se encontró ningún acorde: la partitura tiene menos de tres "
            "voces sonando a la vez."
        )
    if skipped:
        score.warnings.append(
            f"Se ignoraron {skipped} momento(s) con menos de tres notas: son "
            "notas de adorno, no acordes, y se descartan para no deformar la "
            "progresión."
        )
    score.voice_count = max(len(c.pitches) for c in score.chords)
    uneven = {len(c.pitches) for c in score.chords}
    if len(uneven) > 1:
        score.warnings.append(
            "La partitura no tiene la misma cantidad de voces en todos los "
            f"acordes (van de {min(uneven)} a {max(uneven)}). Se completará "
            "o recortará según las voces que elijas."
        )
    unmatched = sum(1 for c in score.chords if not c.matched)
    if unmatched:
        score.warnings.append(
            f"{unmatched} acorde(s) no coinciden con ningún cifrado conocido; "
            "quedan cargados como notas sueltas."
        )
    return score


#: Qualities tried when naming a chord, ordered so the plainest reading wins
#: a tie -- a C major triad should come back as "C", not as some exotic
#: spelling that happens to contain the same three notes.
_NAMING_ORDER = [
    "", "m", "7", "maj7", "m7", "dim", "aug", "m7b5", "dim7", "sus4", "sus2",
    "6", "m6", "9", "maj9", "m9", "add9", "7sus4", "mmaj7", "6/9", "11", "13",
    "7#9", "7b9", "maj7#11", "7#11", "m11", "m13", "maj13", "aug7",
]


def identify_chord(pitches: Sequence[int]) -> Optional[str]:
    """
    Name a set of sounding pitches in American notation.

    Every root and quality is tried and the exact match is taken. The bass
    note is preferred as the root, and a slash is added when the chord turns
    out to be inverted, so the name describes what is actually heard rather
    than an abstract root position.
    """
    if not pitches:
        return None
    sounding = {p % 12 for p in pitches}
    bass_pc = min(pitches) % 12

    best: Optional[Tuple[Tuple[int, int], str]] = None
    for index, quality in enumerate(_NAMING_ORDER):
        template = QUALITY_TEMPLATES.get(quality)
        if template is None:
            continue
        for root_pc in range(12):
            expected = {(root_pc + tone.semitones) % 12 for tone in template}
            if expected != sounding:
                continue
            # The commoner reading wins first, and only then the one with its
            # root in the bass. F-A-C-D is both an F6 and a Dm7 in first
            # inversion; naming it by the bass gives F6, but a minor seventh
            # is the reading a musician expects, so quality is ranked first.
            score = (index, 0 if root_pc == bass_pc else 1)
            if best is None or score < best[0]:
                symbol = SHARP_NAMES[root_pc] + quality
                if root_pc != bass_pc:
                    symbol += "/" + SHARP_NAMES[bass_pc]
                best = (score, symbol)
    return best[1] if best else None


def scale_from_chords(chords: Sequence[Sequence[int]]) -> List[int]:
    """
    The pitch classes a piece actually uses.

    Passing tones need to know what counts as diatonic, and an imported or
    hand-typed progression has no declared key. Collecting what the music
    already sounds is a better answer than guessing a key and being wrong:
    ornaments then move through notes the piece has established.
    """
    used: Dict[int, int] = {}
    for chord in chords:
        for pitch in chord:
            pc = pitch % 12
            used[pc] = used.get(pc, 0) + 1
    return sorted(used)


# ---------------------------------------------------------------------------
# Reading a single line
# ---------------------------------------------------------------------------

def read_melody(path: str):
    """
    Read a score as one melodic line, for the harmoniser.

    Where :func:`read_musicxml` looks for chords, this keeps the top note of
    every moment and the rhythm it is written in. A melody to harmonise is
    usually written as a single line anyway; taking the top note means a
    score that happens to carry more than one still yields the tune.
    """
    from .harmonize import Melody, MelodyBar, MelodyNote

    root = _load_root(path)
    divisions = 1.0
    beats, beat_type = 4, 4
    fifths = 0

    bars: List = []
    notes: List = []

    for bar_index, measure in enumerate(root.iter("measure")):
        attributes = measure.find("attributes")
        if attributes is not None:
            node = attributes.find("divisions")
            if node is not None:
                divisions = float(_text(node, "1") or 1)
            time_node = attributes.find("time")
            if time_node is not None:
                beats = int(_text(time_node.find("beats"), "4") or 4)
                beat_type = int(_text(time_node.find("beat-type"), "4") or 4)
            key_node = attributes.find("key")
            if key_node is not None:
                fifths = int(_text(key_node.find("fifths"), "0") or 0)

        tonic, mode_key = key_from_fifths(fifths)
        bars.append(MelodyBar(beats=beats, beat_type=beat_type,
                              tonic=tonic, mode_key=mode_key))

        cursor = 0.0
        previous = 0.0
        highest: Dict[float, int] = {}
        lengths: Dict[float, float] = {}
        for element in measure:
            if element.tag == "backup":
                cursor -= float(_text(element.find("duration"), "0") or 0) / divisions
                previous = 0.0
                continue
            if element.tag == "forward":
                cursor += float(_text(element.find("duration"), "0") or 0) / divisions
                previous = 0.0
                continue
            if element.tag != "note":
                continue

            duration = float(_text(element.find("duration"), "0") or 0) / divisions
            if element.find("chord") is not None:
                cursor -= previous
            pitch_node = element.find("pitch")
            if element.find("rest") is None and pitch_node is not None:
                midi = _pitch_to_midi(pitch_node)
                if midi is not None:
                    # The top note of the moment is the melody.
                    if cursor not in highest or midi > highest[cursor]:
                        highest[cursor] = midi
                        lengths[cursor] = duration
            cursor += duration
            previous = duration

        for offset in sorted(highest):
            notes.append(MelodyNote(
                pitch=highest[offset],
                duration_quarters=lengths.get(offset, 1.0) or 1.0,
                bar_index=bar_index,
                offset_quarters=offset,
            ))

    if not notes:
        raise ImportError_("La partitura no tiene notas que leer.")
    return Melody(notes=notes, bars=bars or [MelodyBar()])


#: Major keys by their signature, as a count of sharps (positive) or flats.
_KEY_TONICS = {0: 0, 1: 7, 2: 2, 3: 9, 4: 4, 5: 11, 6: 6, 7: 1,
               -1: 5, -2: 10, -3: 3, -4: 8, -5: 1, -6: 6, -7: 11}


def key_from_fifths(fifths: int, minor: bool = False):
    """Turn a key signature into a tonic and a mode."""
    tonic = _KEY_TONICS.get(max(-7, min(7, fifths)), 0)
    if minor:
        return (tonic + 9) % 12, "minor"
    return tonic, "major"
