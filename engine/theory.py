# -*- coding: utf-8 -*-
"""
Core music theory primitives for ChordWeaver.

Everything here is pure data + pure functions: no GUI, no I/O. The genetic
algorithm and the exporters build on top of this module.

Pitch representation
--------------------
Pitches are MIDI note numbers (integers). Middle C (C4) is 60, matching the
Scientific Pitch Notation convention used by MuseScore and most notation
software. A "pitch class" is a MIDI number modulo 12 (0 = C, 1 = C#, ...).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Note names
# ---------------------------------------------------------------------------

#: Preferred spelling for each pitch class when we have no key context.
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

#: Base semitone offset of each natural letter above C.
LETTER_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

#: Diatonic step index of each letter, used to spell accidentals correctly.
LETTER_STEPS = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}

_ACCIDENTAL_VALUES = {"": 0, "#": 1, "##": 2, "b": -1, "bb": -2, "x": 2}


def pitch_class(midi: int) -> int:
    """Return the pitch class (0-11) of a MIDI note number."""
    return midi % 12


def octave_of(midi: int) -> int:
    """Return the scientific-pitch-notation octave of a MIDI note (C4 = 60)."""
    return midi // 12 - 1


def note_name(midi: int, prefer_flats: bool = False) -> str:
    """Render a MIDI note as a name with octave, e.g. 60 -> 'C4'."""
    names = FLAT_NAMES if prefer_flats else SHARP_NAMES
    return f"{names[midi % 12]}{octave_of(midi)}"


def parse_note_name(text: str) -> int:
    """
    Parse a note name such as 'C4', 'Bb3' or 'F#5' into a MIDI number.

    Raises ValueError if the text is not a valid note name with an octave.
    """
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]{0,2}|x)?(-?\d+)\s*", text)
    if not match:
        raise ValueError(f"Invalid note name: {text!r}")
    letter, accidental, octave = match.groups()
    letter = letter.upper()
    accidental = accidental or ""
    semitone = LETTER_SEMITONES[letter] + _ACCIDENTAL_VALUES[accidental]
    return semitone + (int(octave) + 1) * 12


def parse_pitch_class(text: str) -> int:
    """Parse a bare note name without octave ('C', 'Bb', 'F#') into 0-11."""
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]{0,2}|x)?\s*", text)
    if not match:
        raise ValueError(f"Invalid pitch class: {text!r}")
    letter, accidental = match.groups()
    letter = letter.upper()
    accidental = accidental or ""
    return (LETTER_SEMITONES[letter] + _ACCIDENTAL_VALUES[accidental]) % 12


def spell_pitch(
    midi: int,
    root_letter: str,
    semitones_above_root: int,
    degree: Optional[str] = None,
) -> Tuple[str, int, int]:
    """
    Work out how a chord tone should be *spelled* on the staff.

    MusicXML needs a letter (step), an alteration and an octave -- writing an
    augmented ninth as D# instead of Eb is what makes the score readable.

    The diatonic size cannot be inferred from the semitone count alone: three
    semitones above C is Eb as a minor third but D# as an augmented ninth.
    So when the caller knows the chord degree (``"#9"``, ``"b3"``, ...) we
    read the size from that label and only fall back to the interval when no
    degree is available (hand-picked notes).

    Returns (step_letter, alteration, octave).
    """
    if degree is not None and degree in _DEGREE_DIATONIC_STEPS:
        diatonic_size = _DEGREE_DIATONIC_STEPS[degree]
    else:
        diatonic_size = _DIATONIC_SIZE_OF_SEMITONES.get(semitones_above_root % 12, 0)
    root_step = LETTER_STEPS[root_letter]
    step_index = (root_step + diatonic_size) % 7
    step_letter = "CDEFGAB"[step_index]

    # Alteration = actual pitch class minus the natural pitch class of that letter.
    natural_pc = LETTER_SEMITONES[step_letter]
    alteration = (midi % 12 - natural_pc + 6) % 12 - 6

    # The octave must follow the *letter*, not the sounding pitch: B#3 sounds
    # like C4 but is written in octave 3.
    octave = octave_of(midi)
    if step_letter == "B" and alteration > 0 and midi % 12 == 0:
        octave -= 1
    elif step_letter == "C" and alteration < 0 and midi % 12 == 11:
        octave += 1
    return step_letter, alteration, octave


#: Maps a semitone interval to the diatonic size it usually represents, so a
#: minor third (3) is spelled as a third and an augmented second is not.
#: Only used for hand-picked notes, where no chord degree is known.
_DIATONIC_SIZE_OF_SEMITONES = {
    0: 0, 1: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 6, 11: 6,
}

#: Diatonic steps above the root for each printed chord degree. Compound
#: degrees are reduced modulo 7 (a ninth is spelled like a second, a
#: thirteenth like a sixth) because the staff letter repeats every octave.
_DEGREE_DIATONIC_STEPS = {
    "1": 0,
    "b9": 1, "9": 1, "#9": 1, "sus2": 1,
    "b3": 2, "3": 2,
    "11": 3, "#11": 3, "sus4": 3,
    "b5": 4, "5": 4, "#5": 4,
    "6": 5, "b13": 5, "13": 5,
    # A diminished seventh is a seventh, not a sixth: Cdim7 spells Bbb, not A.
    "bb7": 6, "b7": 6, "7": 6,
}


# ---------------------------------------------------------------------------
# Voice catalog
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VoiceType:
    """A voice part with its comfortable range.

    Ranges follow standard choral practice (the conservative "comfortable"
    range rather than the extreme professional range), because the GA treats
    range violations as hard failures and a too-wide range makes the
    constraint meaningless.
    """

    key: str
    label: str
    low: int
    high: int

    @property
    def span(self) -> int:
        return self.high - self.low


#: The catalog the user picks voices from. Order matters: it is the order the
#: parts are stacked from lowest to highest when a set is built.
VOICE_CATALOG: Dict[str, VoiceType] = {
    "B": VoiceType("B", "Bass", parse_note_name("E2"), parse_note_name("C4")),
    "Bar": VoiceType("Bar", "Baritone", parse_note_name("A2"), parse_note_name("F4")),
    "T": VoiceType("T", "Tenor", parse_note_name("C3"), parse_note_name("A4")),
    "A": VoiceType("A", "Alto", parse_note_name("F3"), parse_note_name("D5")),
    "MS": VoiceType("MS", "Mezzo-soprano", parse_note_name("A3"), parse_note_name("F5")),
    "S": VoiceType("S", "Soprano", parse_note_name("C4"), parse_note_name("A5")),
}

#: Suggested default sets per voice count (the user may override any of them).
DEFAULT_VOICE_SETS: Dict[int, List[str]] = {
    3: ["B", "A", "S"],
    4: ["B", "T", "A", "S"],
    5: ["B", "T", "A", "MS", "S"],
    6: ["B", "Bar", "T", "A", "MS", "S"],
}


@dataclass
class VoicePart:
    """A concrete voice in the piece: a catalog type plus an effective range.

    The effective range starts as the catalog range but the user can widen or
    narrow it in the parameters screen, so we keep it per-part rather than
    reading the catalog at fitness time.
    """

    voice_type: VoiceType
    low: int
    high: int
    name: str = ""

    @classmethod
    def from_key(cls, key: str, name: Optional[str] = None) -> "VoicePart":
        vt = VOICE_CATALOG[key]
        return cls(voice_type=vt, low=vt.low, high=vt.high, name=name or vt.label)

    def contains(self, midi: int) -> bool:
        return self.low <= midi <= self.high

    def candidates_for_pitch_class(self, pc: int) -> List[int]:
        """Every MIDI note of the given pitch class inside this voice's range."""
        return [m for m in range(self.low, self.high + 1) if m % 12 == pc]


def build_voice_parts(keys: Sequence[str]) -> List[VoicePart]:
    """
    Build the ordered list of voice parts (lowest first) from catalog keys.

    Sorting by the catalog's low note keeps index 0 as the bass, which the
    rest of the engine relies on (bass gets the F clef, spacing rules treat
    the bass specially, and so on).
    """
    parts = [VoicePart.from_key(k) for k in keys]
    parts.sort(key=lambda p: (p.voice_type.low, p.voice_type.high))
    # Disambiguate duplicates: two sopranos become "Soprano 1" / "Soprano 2".
    counts: Dict[str, int] = {}
    for part in parts:
        counts[part.voice_type.key] = counts.get(part.voice_type.key, 0) + 1
    seen: Dict[str, int] = {}
    for part in parts:
        key = part.voice_type.key
        if counts[key] > 1:
            seen[key] = seen.get(key, 0) + 1
            part.name = f"{part.voice_type.label} {seen[key]}"
    return parts


# ---------------------------------------------------------------------------
# Chord symbols
# ---------------------------------------------------------------------------

#: Chord tone roles, used for doubling and omission priorities.
ROLE_ROOT = "root"
ROLE_THIRD = "third"
ROLE_FIFTH = "fifth"
ROLE_SEVENTH = "seventh"
ROLE_EXTENSION = "extension"


@dataclass(frozen=True)
class ChordTone:
    """One tone of a chord: its interval above the root and its harmonic role."""

    semitones: int          # interval above the root, 0-11 (compound reduced)
    role: str
    degree: str             # human label: "1", "b3", "5", "7", "9", "#11", ...

    @property
    def is_essential(self) -> bool:
        """Third and seventh define the chord quality and are never dropped."""
        return self.role in (ROLE_THIRD, ROLE_SEVENTH)


@dataclass
class Chord:
    """A parsed chord symbol."""

    symbol: str
    root_pc: int
    root_letter: str
    tones: List[ChordTone]
    bass_pc: Optional[int] = None       # for slash chords such as C/G
    bass_letter: Optional[str] = None

    @property
    def pitch_classes(self) -> List[int]:
        """Absolute pitch classes of every chord tone."""
        return [(self.root_pc + t.semitones) % 12 for t in self.tones]

    def pitch_class_of(self, tone: ChordTone) -> int:
        return (self.root_pc + tone.semitones) % 12

    def tone_for_pitch_class(self, pc: int) -> Optional[ChordTone]:
        for tone in self.tones:
            if self.pitch_class_of(tone) == pc:
                return tone
        return None

    def __len__(self) -> int:
        return len(self.tones)


# Quality templates: interval (in semitones) + role + printed degree.
def _t(semitones: int, role: str, degree: str) -> ChordTone:
    return ChordTone(semitones % 12, role, degree)


_ROOT = _t(0, ROLE_ROOT, "1")
_MAJ3 = _t(4, ROLE_THIRD, "3")
_MIN3 = _t(3, ROLE_THIRD, "b3")
_SUS2 = _t(2, ROLE_THIRD, "sus2")
_SUS4 = _t(5, ROLE_THIRD, "sus4")
_P5 = _t(7, ROLE_FIFTH, "5")
_DIM5 = _t(6, ROLE_FIFTH, "b5")
_AUG5 = _t(8, ROLE_FIFTH, "#5")
_MAJ7 = _t(11, ROLE_SEVENTH, "7")
_MIN7 = _t(10, ROLE_SEVENTH, "b7")
_DIM7 = _t(9, ROLE_SEVENTH, "bb7")
_MAJ6 = _t(9, ROLE_EXTENSION, "6")
_NINTH = _t(2, ROLE_EXTENSION, "9")
_FLAT9 = _t(1, ROLE_EXTENSION, "b9")
_SHARP9 = _t(3, ROLE_EXTENSION, "#9")
_ELEVENTH = _t(5, ROLE_EXTENSION, "11")
_SHARP11 = _t(6, ROLE_EXTENSION, "#11")
_THIRTEENTH = _t(9, ROLE_EXTENSION, "13")
_FLAT13 = _t(8, ROLE_EXTENSION, "b13")

#: Base triad/seventh templates keyed by the normalised quality string.
#: Longer keys must be tested first, which `_QUALITY_ORDER` guarantees.
QUALITY_TEMPLATES: Dict[str, List[ChordTone]] = {
    # Triads
    "": [_ROOT, _MAJ3, _P5],
    "m": [_ROOT, _MIN3, _P5],
    "dim": [_ROOT, _MIN3, _DIM5],
    "aug": [_ROOT, _MAJ3, _AUG5],
    "sus2": [_ROOT, _SUS2, _P5],
    "sus4": [_ROOT, _SUS4, _P5],
    "5": [_ROOT, _P5],                       # power chord
    # Sixths
    "6": [_ROOT, _MAJ3, _P5, _MAJ6],
    "m6": [_ROOT, _MIN3, _P5, _MAJ6],
    "6/9": [_ROOT, _MAJ3, _P5, _MAJ6, _NINTH],
    "m6/9": [_ROOT, _MIN3, _P5, _MAJ6, _NINTH],
    # Sevenths
    "maj7": [_ROOT, _MAJ3, _P5, _MAJ7],
    "7": [_ROOT, _MAJ3, _P5, _MIN7],
    "m7": [_ROOT, _MIN3, _P5, _MIN7],
    "mmaj7": [_ROOT, _MIN3, _P5, _MAJ7],
    "m7b5": [_ROOT, _MIN3, _DIM5, _MIN7],
    "dim7": [_ROOT, _MIN3, _DIM5, _DIM7],
    "aug7": [_ROOT, _MAJ3, _AUG5, _MIN7],
    "augmaj7": [_ROOT, _MAJ3, _AUG5, _MAJ7],
    "7sus4": [_ROOT, _SUS4, _P5, _MIN7],
    "7sus2": [_ROOT, _SUS2, _P5, _MIN7],
    # Ninths
    "maj9": [_ROOT, _MAJ3, _P5, _MAJ7, _NINTH],
    "9": [_ROOT, _MAJ3, _P5, _MIN7, _NINTH],
    "m9": [_ROOT, _MIN3, _P5, _MIN7, _NINTH],
    "mmaj9": [_ROOT, _MIN3, _P5, _MAJ7, _NINTH],
    # Elevenths
    "maj11": [_ROOT, _MAJ3, _P5, _MAJ7, _NINTH, _ELEVENTH],
    "11": [_ROOT, _MAJ3, _P5, _MIN7, _NINTH, _ELEVENTH],
    "m11": [_ROOT, _MIN3, _P5, _MIN7, _NINTH, _ELEVENTH],
    # Thirteenths
    "maj13": [_ROOT, _MAJ3, _P5, _MAJ7, _NINTH, _THIRTEENTH],
    "13": [_ROOT, _MAJ3, _P5, _MIN7, _NINTH, _THIRTEENTH],
    "m13": [_ROOT, _MIN3, _P5, _MIN7, _NINTH, _THIRTEENTH],
    "add9": [_ROOT, _MAJ3, _P5, _NINTH],
    "madd9": [_ROOT, _MIN3, _P5, _NINTH],
    "add11": [_ROOT, _MAJ3, _P5, _ELEVENTH],
    "add13": [_ROOT, _MAJ3, _P5, _THIRTEENTH],
    # Suspended family
    "sus": [_ROOT, _SUS4, _P5],
    "sus4add9": [_ROOT, _SUS4, _P5, _NINTH],
    "9sus4": [_ROOT, _SUS4, _P5, _MIN7, _NINTH],
    "13sus4": [_ROOT, _SUS4, _P5, _MIN7, _NINTH, _THIRTEENTH],
    # Augmented family
    "maj7#5": [_ROOT, _MAJ3, _AUG5, _MAJ7],
    "maj9#5": [_ROOT, _MAJ3, _AUG5, _MAJ7, _NINTH],
    # Half-diminished extensions
    "m9b5": [_ROOT, _MIN3, _DIM5, _MIN7, _NINTH],
    "m11b5": [_ROOT, _MIN3, _DIM5, _MIN7, _NINTH, _ELEVENTH],
    # Altered dominant: root, third and seventh plus the altered tensions.
    # The b9 belongs here -- without it "alt" is just a 7#9#5 and loses the
    # characteristic clash that defines the sonority.
    "7alt": [_ROOT, _MAJ3, _MIN7, _FLAT9, _SHARP9, _AUG5],
    "7b9b5": [_ROOT, _MAJ3, _DIM5, _MIN7, _FLAT9],
    "7#9#5": [_ROOT, _MAJ3, _AUG5, _MIN7, _SHARP9],
    "m6/9": [_ROOT, _MIN3, _P5, _MAJ6, _NINTH],
}

#: Aliases the user may type; mapped onto the canonical quality keys above.
QUALITY_ALIASES: Dict[str, str] = {
    "M": "", "maj": "", "major": "", "ma": "",
    "min": "m", "-": "m", "minor": "m",
    "o": "dim", "°": "dim", "dim": "dim",
    "+": "aug", "#5": "aug",
    "M7": "maj7", "Ma7": "maj7", "ma7": "maj7", "Δ": "maj7", "Δ7": "maj7", "maj7": "maj7",
    "dom7": "7",
    "min7": "m7", "-7": "m7",
    "ø": "m7b5", "ø7": "m7b5", "m7-5": "m7b5", "min7b5": "m7b5", "halfdim": "m7b5",
    "o7": "dim7", "°7": "dim7",
    "+7": "aug7", "7#5": "aug7",
    "mM7": "mmaj7", "-maj7": "mmaj7", "mmaj7": "mmaj7",
    "M9": "maj9", "Δ9": "maj9",
    "min9": "m9", "-9": "m9",
    "M13": "maj13",
    "69": "6/9", "6add9": "6/9",
    "sus2add9": "sus2",
    "augM7": "augmaj7", "+maj7": "augmaj7",
    "alt": "7alt", "altered": "7alt",
    "domin7": "7", "dominant7": "7",
    "add2": "add9",
    "maj7+5": "maj7#5",
    "7sus": "7sus4", "9sus": "9sus4", "13sus": "13sus4",
}

#: Alterations that can be appended to any quality, e.g. C7#9, Cmaj7#11.
ALTERATION_TONES: Dict[str, ChordTone] = {
    "b9": _FLAT9,
    "#9": _SHARP9,
    "b5": _DIM5,
    "#5": _AUG5,
    "#11": _SHARP11,
    "b13": _FLAT13,
    "11": _ELEVENTH,
    "9": _NINTH,
    "13": _THIRTEENTH,
    "6": _MAJ6,
}

#: Longest-first so that "maj13" is matched before "maj1"/"maj".
_QUALITY_ORDER = sorted(
    set(QUALITY_TEMPLATES) | set(QUALITY_ALIASES), key=len, reverse=True
)

_ALTERATION_ORDER = sorted(ALTERATION_TONES, key=len, reverse=True)

#: Multi-letter quality words that may be typed in any case: CMAJ7, CMaj7 and
#: Cmaj7 all mean the same chord. Sorted longest-first so "maj" is normalised
#: before the shorter "ma" can match inside it.
#:
#: A bare "m" is deliberately NOT in this list. In American notation the case
#: of a lone letter is the whole distinction: Cm is C minor while CM is C
#: major, so lowercasing it indiscriminately would silently turn every major
#: chord into a minor one.
_CASE_INSENSITIVE_WORDS = sorted(
    ["halfdim", "maj", "min", "dim", "aug", "sus", "add", "dom", "alt", "ma"],
    key=len,
    reverse=True,
)

_WORD_PATTERNS = [
    (re.compile(re.escape(word), re.IGNORECASE), word)
    for word in _CASE_INSENSITIVE_WORDS
]


def _normalise_quality(text: str) -> str:
    """
    Fold the case of multi-letter quality words, leaving lone m/M alone.

    ``"MAJ7"`` and ``"Maj7"`` both become ``"maj7"``; ``"M7"`` is untouched
    and resolves through the alias table to a major seventh.
    """
    for pattern, canonical in _WORD_PATTERNS:
        text = pattern.sub(canonical, text)
    return text


def _is_case_sensitive_token(token: str) -> bool:
    """
    True when a token's capitalisation carries meaning.

    Case matters in exactly one place in chord symbols: a bare ``M`` means
    major while a bare ``m`` means minor, so ``CM7`` and ``Cm7`` are
    different chords. That ambiguity only exists while the letter stands
    alone -- once it is followed by more letters the word is spelled out and
    unambiguous, which is why ``maj7``, ``Maj7`` and ``MAJ7`` are all the
    same chord. So: the letter is case-sensitive when nothing alphabetic
    follows it.
    """
    if not token or token[0] not in ("m", "M"):
        return False
    rest = token[1:]
    return not any(character.isalpha() for character in rest)


def _token_matches(text: str, token: str) -> bool:
    """Prefix match that is case-tolerant except where case is meaningful."""
    if not token:
        return False
    candidate = text[:len(token)]
    if _is_case_sensitive_token(token):
        # First letter exact, remainder (digits, accidentals) case-tolerant.
        return (
            candidate[:1] == token[:1]
            and candidate[1:].lower() == token[1:].lower()
        )
    return candidate.lower() == token.lower()


class ChordParseError(ValueError):
    """Raised when a chord symbol cannot be understood."""


def parse_chord(symbol: str) -> Chord:
    """
    Parse an American chord symbol into a :class:`Chord`.

    Handles roots with accidentals, the qualities in ``QUALITY_TEMPLATES``
    plus their common aliases, trailing alterations (``#11``, ``b9``, ...)
    and slash bass notes (``C/G``).
    """
    raw = symbol.strip()
    if not raw:
        raise ChordParseError("Empty chord symbol")

    # Slash bass -------------------------------------------------------------
    bass_pc: Optional[int] = None
    bass_letter: Optional[str] = None
    body = raw
    if "/" in raw:
        head, _, tail = raw.rpartition("/")
        # "6/9" is a quality, not a slash chord: only treat the tail as a bass
        # note when it actually parses as one.
        try:
            bass_pc = parse_pitch_class(tail)
            bass_letter = tail.strip()[0].upper()
            body = head
        except ValueError:
            bass_pc = None
            body = raw

    # Root -------------------------------------------------------------------
    root_match = re.match(r"([A-Ga-g])([#b]{0,2}|x)?", body)
    if not root_match:
        raise ChordParseError(f"no se entiende la fundamental de {symbol!r}")
    root_letter = root_match.group(1).upper()
    root_accidental = root_match.group(2) or ""
    root_pc = (LETTER_SEMITONES[root_letter] + _ACCIDENTAL_VALUES[root_accidental]) % 12
    remainder = _normalise_quality(body[root_match.end():].strip())

    # Quality ----------------------------------------------------------------
    quality_key = ""
    for candidate in _QUALITY_ORDER:
        if candidate and _token_matches(remainder, candidate):
            quality_key = QUALITY_ALIASES.get(candidate, candidate)
            remainder = remainder[len(candidate):]
            break
    else:
        if remainder and not remainder[0] in "(#b123456789":
            raise ChordParseError(f"Unknown chord quality in {symbol!r}")

    if quality_key not in QUALITY_TEMPLATES:
        raise ChordParseError(f"Unknown chord quality {quality_key!r} in {symbol!r}")

    tones = list(QUALITY_TEMPLATES[quality_key])

    # Alterations ------------------------------------------------------------
    remainder = remainder.replace("(", "").replace(")", "").replace(" ", "")
    while remainder:
        for alt in _ALTERATION_ORDER:
            if _token_matches(remainder, alt):
                new_tone = ALTERATION_TONES[alt]
                # An alteration replaces the tone playing the same role
                # (C7b5 must drop the natural fifth, not stack both).
                tones = [t for t in tones if not _same_slot(t, new_tone)]
                tones.append(new_tone)
                remainder = remainder[len(alt):]
                break
        else:
            raise ChordParseError(
                f"Unrecognised text {remainder!r} in chord symbol {symbol!r}"
            )

    tones.sort(key=lambda t: (_ROLE_SORT.get(t.role, 9), t.semitones))
    return Chord(
        symbol=raw,
        root_pc=root_pc,
        root_letter=root_letter,
        tones=tones,
        bass_pc=bass_pc,
        bass_letter=bass_letter,
    )


_ROLE_SORT = {ROLE_ROOT: 0, ROLE_THIRD: 1, ROLE_FIFTH: 2, ROLE_SEVENTH: 3, ROLE_EXTENSION: 4}

#: Degrees that occupy the same "slot" and therefore replace each other.
_SLOT_GROUPS = [
    {"5", "b5", "#5"},
    {"9", "b9", "#9"},
    {"11", "#11"},
    {"13", "b13", "6"},
]


def _same_slot(a: ChordTone, b: ChordTone) -> bool:
    if a.degree == b.degree:
        return True
    for group in _SLOT_GROUPS:
        if a.degree in group and b.degree in group:
            return True
    return False


def make_custom_chord(pitch_classes: Sequence[int], label: str = "custom") -> Chord:
    """
    Build a Chord from hand-picked pitch classes (the piano-input path).

    The lowest picked note is treated as the root and every other note gets a
    role inferred from its interval, so the doubling and omission logic keeps
    working for chords the parser does not know.
    """
    if not pitch_classes:
        raise ChordParseError("A custom chord needs at least one note")
    # The order given is the order the user chose, lowest voice first, and it
    # is preserved. Re-sorting numerically would silently re-root the chord:
    # picking E-G-B-C on the piano would come back as C-E-G-B, because pitch
    # class C is 0 and sorts ahead of E, and the bass note the user actually
    # wanted would end up in an upper voice.
    ordered = list(dict.fromkeys(pc % 12 for pc in pitch_classes))
    root_pc = ordered[0]
    tones: List[ChordTone] = []
    for pc in ordered:
        interval = (pc - root_pc) % 12
        tones.append(ChordTone(interval, _infer_role(interval), _infer_degree(interval)))
    return Chord(
        symbol=label,
        root_pc=root_pc,
        root_letter=SHARP_NAMES[root_pc][0],
        tones=tones,
    )


def _infer_role(interval: int) -> str:
    if interval == 0:
        return ROLE_ROOT
    if interval in (3, 4, 2, 5):
        return ROLE_THIRD if interval in (3, 4) else ROLE_EXTENSION
    if interval in (6, 7, 8):
        return ROLE_FIFTH
    if interval in (10, 11):
        return ROLE_SEVENTH
    return ROLE_EXTENSION


def _infer_degree(interval: int) -> str:
    return {
        0: "1", 1: "b9", 2: "9", 3: "b3", 4: "3", 5: "11",
        6: "b5", 7: "5", 8: "#5", 9: "6", 10: "b7", 11: "7",
    }[interval]


# ---------------------------------------------------------------------------
# Figured bass
# ---------------------------------------------------------------------------

#: Standard figures keyed by the set of generic intervals sounding above the
#: bass. Thoroughbass writes those intervals out, but centuries of practice
#: abbreviated the common cases: a first-inversion triad is written "6"
#: rather than "6/3" because the third is taken for granted.
_FIGURE_BY_INTERVALS = {
    frozenset({"3", "5"}): "5/3",      # root-position triad
    frozenset({"3", "6"}): "6",        # first inversion
    frozenset({"4", "6"}): "6/4",      # second inversion
    frozenset({"3", "5", "7"}): "7",   # root-position seventh
    frozenset({"3", "5", "6"}): "6/5", # first inversion
    frozenset({"3", "4", "6"}): "4/3", # second inversion
    frozenset({"2", "4", "6"}): "4/2", # third inversion
    frozenset({"3"}): "3",
    frozenset({"5"}): "5",
    frozenset({"6"}): "6",
}

#: Generic interval name for each semitone distance above the bass, used when
#: a chord is too extended for the classical figures to cover.
TRITONE_SEMITONES = 6

_GENERIC_INTERVAL = {
    0: "1", 1: "2", 2: "2", 3: "3", 4: "3", 5: "4",
    6: "5", 7: "5", 8: "6", 9: "6", 10: "7", 11: "7",
}


def figured_bass(chord: "Chord", pitches: Sequence[int]) -> str:
    """
    Return the thoroughbass figure for a voicing, measured from the bass.

    Every sounding voice except the bass itself is counted, so a root
    position seventh reads 7/5/3 rather than the abbreviated 7. Period
    practice dropped the intervals a reader could take for granted, but the
    point here is to *see* the voicing, and the shorthand hides exactly the
    numbers you want to check.

    Intervals are read off the chord degrees where possible, because those
    know whether a tritone is an augmented fourth or a diminished fifth -- B
    to F inside a G7 is a diminished fifth while F to B is an augmented
    fourth, and the two give different figures.
    """
    if len(pitches) < 2:
        return ""

    sizes = _sizes_from_degrees(chord, pitches) or _sizes_from_semitones(pitches)
    if not sizes:
        return ""
    return "/".join(sorted(sizes, key=int, reverse=True))


def _sizes_from_semitones(pitches: Sequence[int]) -> List[str]:
    """Fallback interval sizes, guessed from semitone distances."""
    bass = pitches[0]
    sizes = []
    for pitch in pitches[1:]:
        distance = (pitch - bass) % 12
        sizes.append("8" if distance == 0 else _GENERIC_INTERVAL[distance])
    return sorted(set(sizes), key=int, reverse=True)


def _sizes_from_degrees(chord: "Chord", pitches: Sequence[int]) -> Optional[List[str]]:
    """
    Interval sizes above the bass, read from the chord's own degrees.

    Returns None when the degrees cannot be trusted: a chord built note by
    note on the piano has degrees that were only guessed from intervals, and
    a hand-picked E-G-B-C is read as root, b3, 5 and #5 -- that #5 spells the
    C as a B#, which would count as a fifth above the bass instead of a sixth.
    """
    def diatonic_step(pitch: int) -> Optional[int]:
        tone = chord.tone_for_pitch_class(pitch % 12)
        if tone is None:
            return None
        return _DEGREE_DIATONIC_STEPS.get(tone.degree)

    all_steps = [_DEGREE_DIATONIC_STEPS.get(t.degree) for t in chord.tones]
    if None in all_steps or len(set(all_steps)) != len(all_steps):
        return None

    bass_step = diatonic_step(pitches[0])
    if bass_step is None:
        return None

    sizes = []
    for pitch in pitches[1:]:
        if (pitch - pitches[0]) % 12 == 0:
            sizes.append("8")
            continue
        step = diatonic_step(pitch)
        if step is None:
            return None
        sizes.append(str(((step - bass_step) % 7) + 1))
    return sorted(set(sizes), key=int, reverse=True)


def intervals_above_bass(pitches: Sequence[int]) -> List[str]:
    """Generic interval of each upper voice above the bass, lowest voice first."""
    if not pitches:
        return []
    return [_GENERIC_INTERVAL[(p - pitches[0]) % 12] for p in pitches[1:]]
