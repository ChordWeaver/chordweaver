# -*- coding: utf-8 -*-
"""
Score and audio export.

Two formats are produced from the same solution:

* **MusicXML** -- opens in MuseScore, Finale, Sibelius, Flat.io, Soundslice
  and friends. Written on two staves: the lowest voice on an F clef, every
  other voice on a G clef, as requested.
* **Standard MIDI File** -- written by hand rather than through a library, so
  the packaged application stays dependency-free and small.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .ga import ChordSlot, Chromosome
from .theory import SHARP_NAMES, VoicePart, octave_of, spell_pitch

#: MusicXML divisions per quarter note. 8 lets us write everything down to a
#: 32nd note with integer durations, which keeps the file tidy.
DIVISIONS_PER_QUARTER = 8

#: MIDI ticks per quarter note.
TICKS_PER_QUARTER = 480

#: Note type names keyed by duration in quarter notes.
_NOTE_TYPES = {
    8.0: "breve",
    6.0: "whole",      # dotted whole
    4.0: "whole",
    3.0: "half",       # dotted half
    2.0: "half",
    1.5: "quarter",    # dotted quarter
    1.0: "quarter",
    0.75: "eighth",    # dotted eighth
    0.5: "eighth",
    0.25: "16th",
}

#: Durations that need a dot.
_DOTTED = {6.0, 3.0, 1.5, 0.75}


@dataclass
class TimeSignature:
    """A time signature, e.g. 4/4 or 6/8."""

    beats: int = 4
    beat_type: int = 4

    @property
    def quarters_per_bar(self) -> float:
        """Length of one bar measured in quarter notes."""
        return self.beats * 4.0 / self.beat_type

    def __str__(self) -> str:
        return f"{self.beats}/{self.beat_type}"


@dataclass
class MelodyLine:
    """The given line, written in the rhythm the user actually wrote it in.

    Only the harmonising mode supplies one. The search sees that line
    sampled one note per chord -- the strong beat is where the harmony is
    decided, and that is what the counterpoint is written against -- but the
    score has to show the tune as played, not as sampled. Without this the
    exported part came back with the passing notes missing and the rhythm
    halved, which read as somebody else's melody.

    Keyed by ``bar_index`` rather than by position, so a piece whose bars do
    not start at zero still lines up. A ``None`` pitch is a rest.
    """

    voice_index: int
    bars: Dict[int, List[Tuple[Optional[int], float]]] = field(default_factory=dict)

    def events_for(self, bar_index: int) -> Optional[List[Tuple[Optional[int], float]]]:
        return self.bars.get(bar_index)


@dataclass
class ScoreSpec:
    """Everything needed to write a score out."""

    slots: List[ChordSlot]
    voices: List[VoicePart]
    time_signature: TimeSignature
    title: str = "ChordWeaver"
    tempo_bpm: int = 90
    #: Optional per-bar time signatures, for pieces that change metre.
    bar_time_signatures: Optional[List[TimeSignature]] = None
    #: How much of a chord's duration a passing tone takes at its tail.
    passing_share: float = 0.5
    #: The user's own line, when there is one. Left as None by the two modes
    #: that have no given melody, and those write every voice from the
    #: chromosome exactly as they always did.
    melody: Optional["MelodyLine"] = None

    def signature_for_bar(self, bar_index: int) -> TimeSignature:
        if self.bar_time_signatures and bar_index < len(self.bar_time_signatures):
            return self.bar_time_signatures[bar_index]
        return self.time_signature


def group_slots_into_bars(spec: ScoreSpec) -> List[List[ChordSlot]]:
    """
    Split the slot list into bars using each slot's ``bar_index``.

    The UI is responsible for making the durations inside a bar add up to the
    bar length; here we just honour the grouping it produced, so a piece that
    changes metre mid-way still comes out right.
    """
    if not spec.slots:
        return []
    bars: List[List[ChordSlot]] = []
    current_index = spec.slots[0].bar_index
    current: List[ChordSlot] = []
    for slot in spec.slots:
        if slot.bar_index != current_index and current:
            bars.append(current)
            current = []
            current_index = slot.bar_index
        current.append(slot)
    if current:
        bars.append(current)
    return bars


def _duration_parts(quarters: float) -> Tuple[str, bool]:
    """Return (note type name, dotted) for a duration in quarter notes."""
    if quarters in _NOTE_TYPES:
        return _NOTE_TYPES[quarters], quarters in _DOTTED
    # Fall back to the closest known duration so odd values still render.
    closest = min(_NOTE_TYPES, key=lambda d: abs(d - quarters))
    return _NOTE_TYPES[closest], closest in _DOTTED


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# MusicXML
# ---------------------------------------------------------------------------

def build_musicxml(spec: ScoreSpec, solution: Chromosome) -> str:
    """
    Render one solution as a MusicXML 3.1 part-wise score.

    Layout: staff 1 (treble) carries every voice except the lowest, staff 2
    (bass) carries the lowest voice alone. MusicXML voice numbers run 1..N
    from the top down, which is what notation programs expect.
    """
    voice_count = len(spec.voices)
    bars = group_slots_into_bars(spec)

    # Map engine voice index (0 = lowest) to MusicXML voice number and staff.
    # The bass sits on staff 2; everyone else shares staff 1.
    # Closed-score choral layout: soprano and alto share the treble staff,
    # tenor and bass share the bass staff. Putting only the bass on the F
    # clef -- as an earlier version did -- writes the tenor far above where
    # any singer reads it, since a tenor part sits below middle C for most
    # of its range.
    LOWER_STAFF_VOICES = {"B", "Bar", "T"}

    def staff_of(voice_index: int) -> int:
        return 2 if spec.voices[voice_index].voice_type.key in LOWER_STAFF_VOICES else 1

    def musicxml_voice(voice_index: int) -> int:
        # Numbering from the top voice downwards keeps notation tidy.
        return voice_count - voice_index

    def stem_of(voice_index: int) -> str:
        return "down" if voice_index % 2 == 0 else "up"

    # How many sounding chords precede each bar, so every voice reads the
    # same chromosome positions no matter how many rests came before.
    sounding_before: List[int] = []
    running = 0
    for bar in bars:
        sounding_before.append(running)
        running += sum(1 for slot in bar if not slot.is_rest)

    measures: List[str] = []
    slot_cursor = 0
    previous_signature: Optional[TimeSignature] = None

    for bar_number, bar_slots in enumerate(bars, start=1):
        signature = spec.signature_for_bar(bar_number - 1)
        attributes = ""
        if bar_number == 1 or signature != previous_signature:
            clef_block = ""
            if bar_number == 1:
                clef_block = (
                    "\n        <staves>2</staves>"
                    "\n        <clef number=\"1\"><sign>G</sign><line>2</line></clef>"
                    "\n        <clef number=\"2\"><sign>F</sign><line>4</line></clef>"
                )
            key_block = (
                "\n        <key><fifths>0</fifths></key>" if bar_number == 1 else ""
            )
            attributes = (
                "\n      <attributes>"
                f"\n        <divisions>{DIVISIONS_PER_QUARTER}</divisions>"
                f"{key_block}"
                f"\n        <time><beats>{signature.beats}</beats>"
                f"<beat-type>{signature.beat_type}</beat-type></time>"
                f"{clef_block}"
                "\n      </attributes>"
            )
            previous_signature = signature

        body: List[str] = []
        # Write staff 1 voices first (top down), then back up and write the bass.
        upper_voices = list(range(voice_count - 1, 0, -1))
        order = upper_voices + [0]

        for position, voice_index in enumerate(order):
            if position > 0:
                total = sum(s.duration_quarters for s in bar_slots)
                body.append(
                    "\n      <backup><duration>"
                    f"{int(round(total * DIVISIONS_PER_QUARTER))}"
                    "</duration></backup>"
                )
            melody_events = (
                spec.melody.events_for(bar_slots[0].bar_index)
                if spec.melody is not None
                and voice_index == spec.melody.voice_index
                else None
            )
            if melody_events is not None:
                # Written from the line itself, so its rhythm survives. The
                # slot is still handed over for spelling: accidentals are
                # read off the chord sounding underneath.
                for melody_pitch, quarters in melody_events:
                    if melody_pitch is None:
                        body.append(_rest_xml(
                            slot=bar_slots[0],
                            voice_number=musicxml_voice(voice_index),
                            staff=staff_of(voice_index),
                            duration_override=quarters,
                        ))
                        continue
                    body.append(_note_xml(
                        pitch=melody_pitch, slot=bar_slots[0],
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index),
                        duration_override=quarters,
                    ))
                continue

            sounding_index = sounding_before[bar_number - 1]
            for slot in bar_slots:
                if slot.is_rest:
                    body.append(_rest_xml(
                        slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                    ))
                    continue
                pitch = solution.slots[sounding_index][voice_index]
                notes = (solution.passing[sounding_index]
                         if sounding_index < len(solution.passing) else [])
                has_passing = any(n is not None for n in notes)
                sounding_index += 1

                if not has_passing:
                    body.append(_note_xml(
                        pitch=pitch, slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index),
                    ))
                    continue

                # Only the voice that ornaments is split. The others hold a
                # single note for the whole duration: re-articulating them
                # made every part move at once, so a single ornament looked
                # like all four voices changing together.
                moved_here = notes[voice_index] if voice_index < len(notes) else None
                if moved_here is None:
                    body.append(_note_xml(
                        pitch=pitch, slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index),
                    ))
                    continue

                # The ornamenting voice splits: the chord tone, then the
                # ornament for the tail.
                share = (solution.passing_share[sounding_index - 1]
                         if sounding_index - 1 < len(solution.passing_share)
                         else spec.passing_share)
                head = slot.duration_quarters * (1.0 - share)
                tail = slot.duration_quarters - head
                moved = notes[voice_index] if voice_index < len(notes) else None
                body.append(_note_xml(
                    pitch=pitch, slot=slot,
                    voice_number=musicxml_voice(voice_index),
                    staff=staff_of(voice_index),
                    stem=stem_of(voice_index),
                    duration_override=head,
                ))
                body.append(_note_xml(
                    pitch=moved if moved is not None else pitch, slot=slot,
                    voice_number=musicxml_voice(voice_index),
                    staff=staff_of(voice_index),
                    stem=stem_of(voice_index),
                    duration_override=tail,
                ))

        slot_cursor += len(bar_slots)
        measures.append(
            f'\n    <measure number="{bar_number}">{attributes}'
            + "".join(body)
            + "\n    </measure>"
        )

    part_names = ", ".join(v.name for v in spec.voices)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">\n'
        '<score-partwise version="3.1">\n'
        "  <work>\n"
        f"    <work-title>{_escape(spec.title)}</work-title>\n"
        "  </work>\n"
        "  <identification>\n"
        "    <encoding>\n"
        "      <software>ChordWeaver</software>\n"
        "    </encoding>\n"
        "  </identification>\n"
        "  <part-list>\n"
        '    <score-part id="P1">\n'
        f"      <part-name>{_escape(part_names)}</part-name>\n"
        "    </score-part>\n"
        "  </part-list>\n"
        '  <part id="P1">'
        + "".join(measures)
        + "\n  </part>\n</score-partwise>\n"
    )


def _rest_xml(slot: ChordSlot, voice_number: int, staff: int,
              duration_override: Optional[float] = None) -> str:
    """Render one <rest> element occupying the slot's duration."""
    length = (duration_override if duration_override is not None
              else slot.duration_quarters)
    duration_units = int(round(length * DIVISIONS_PER_QUARTER))
    note_type, dotted = _duration_parts(length)
    dot_xml = "<dot/>" if dotted else ""
    return (
        "\n      <note>"
        "\n        <rest/>"
        f"\n        <duration>{duration_units}</duration>"
        f"\n        <voice>{voice_number}</voice>"
        f"\n        <type>{note_type}</type>{dot_xml}"
        f"\n        <staff>{staff}</staff>"
        "\n      </note>"
    )


def _note_xml(
    pitch: int,
    slot: ChordSlot,
    voice_number: int,
    staff: int,
    stem: str,
    duration_override: Optional[float] = None,
) -> str:
    """Render one <note> element, spelling accidentals from the chord degree."""
    chord = slot.requirement.chord
    interval = (pitch - chord.root_pc) % 12
    tone = chord.tone_for_pitch_class(pitch % 12)
    degree = tone.degree if tone is not None else None

    # A note that is not part of the chord -- the bass of a slash chord, a
    # passing tone -- has no degree to spell it by, and reading the interval
    # from the root produced things like E# where the music says F. Those
    # are spelled from the note itself instead.
    if tone is None and chord.bass_pc is not None and pitch % 12 == chord.bass_pc:
        step, alter, octave = spell_pitch(pitch, SHARP_NAMES[chord.bass_pc][0],
                                          0, "1")
    else:
        step, alter, octave = spell_pitch(pitch, chord.root_letter, interval,
                                          degree)

    length = (duration_override if duration_override is not None
              else slot.duration_quarters)
    duration_units = int(round(length * DIVISIONS_PER_QUARTER))
    note_type, dotted = _duration_parts(length)
    alter_xml = f"<alter>{alter}</alter>" if alter else ""
    dot_xml = "<dot/>" if dotted else ""
    accidental_xml = ""
    if alter == 1:
        accidental_xml = "<accidental>sharp</accidental>"
    elif alter == -1:
        accidental_xml = "<accidental>flat</accidental>"
    elif alter == 2:
        accidental_xml = "<accidental>double-sharp</accidental>"
    elif alter == -2:
        accidental_xml = "<accidental>flat-flat</accidental>"

    return (
        "\n      <note>"
        f"\n        <pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
        f"\n        <duration>{duration_units}</duration>"
        f"\n        <voice>{voice_number}</voice>"
        f"\n        <type>{note_type}</type>{dot_xml}{accidental_xml}"
        f"\n        <stem>{stem}</stem>"
        f"\n        <staff>{staff}</staff>"
        "\n      </note>"
    )


# ---------------------------------------------------------------------------
# MIDI
# ---------------------------------------------------------------------------

def _variable_length(value: int) -> bytes:
    """Encode an integer as a MIDI variable-length quantity."""
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
        value >>= 7
    out = bytearray()
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(out)


def _midi_track(events: Sequence[Tuple[int, bytes]]) -> bytes:
    """Wrap timed events into an MTrk chunk. Events are (delta_ticks, data)."""
    payload = bytearray()
    for delta, data in events:
        payload += _variable_length(delta)
        payload += data
    payload += _variable_length(0) + b"\xff\x2f\x00"     # end of track
    return b"MTrk" + struct.pack(">I", len(payload)) + bytes(payload)


def build_midi(spec: ScoreSpec, solution: Chromosome, velocity: int = 80) -> bytes:
    """
    Render one solution as a type-1 Standard MIDI File, one track per voice.

    Writing the bytes directly avoids a third-party MIDI dependency, which
    matters because the application ships as a self-contained folder.
    """
    tracks: List[bytes] = []

    # Track 0: tempo and time signature only.
    microseconds_per_quarter = int(round(60_000_000 / max(1, spec.tempo_bpm)))
    tempo_bytes = microseconds_per_quarter.to_bytes(3, "big")
    signature = spec.time_signature
    denominator_power = max(0, (spec.time_signature.beat_type.bit_length() - 1))
    meta_events: List[Tuple[int, bytes]] = [
        (0, b"\xff\x51\x03" + tempo_bytes),
        (
            0,
            b"\xff\x58\x04"
            + bytes([signature.beats, denominator_power, 24, 8]),
        ),
        (0, b"\xff\x03" + bytes([len(spec.title)]) + spec.title.encode("ascii", "replace")),
    ]
    tracks.append(_midi_track(meta_events))

    for voice_index, voice in enumerate(spec.voices):
        events: List[Tuple[int, bytes]] = []
        name = voice.name.encode("ascii", "replace")[:127]
        events.append((0, b"\xff\x03" + bytes([len(name)]) + name))
        channel = min(voice_index, 15)

        pending_rest_ticks = 0
        sounding_index = 0

        if spec.melody is not None and voice_index == spec.melody.voice_index:
            for bar_slots in group_slots_into_bars(spec):
                for melody_pitch, quarters in (
                        spec.melody.events_for(bar_slots[0].bar_index) or []):
                    ticks = int(round(quarters * TICKS_PER_QUARTER))
                    if melody_pitch is None:
                        pending_rest_ticks += ticks
                        continue
                    events.append((pending_rest_ticks,
                                   bytes([0x90 | channel, melody_pitch, velocity])))
                    pending_rest_ticks = 0
                    events.append((ticks,
                                   bytes([0x80 | channel, melody_pitch, 0])))
            tracks.append(_midi_track(events))
            continue

        for slot in spec.slots:
            ticks = int(round(slot.duration_quarters * TICKS_PER_QUARTER))
            if slot.is_rest:
                # Nothing sounds; the silence is carried as delta time onto
                # whatever note comes next.
                pending_rest_ticks += ticks
                continue
            pitch = solution.slots[sounding_index][voice_index]
            notes = (solution.passing[sounding_index]
                     if sounding_index < len(solution.passing) else [])
            moved = notes[voice_index] if voice_index < len(notes) else None
            sounding_index += 1

            if moved is None:
                events.append((pending_rest_ticks,
                               bytes([0x90 | channel, pitch, velocity])))
                pending_rest_ticks = 0
                events.append((ticks, bytes([0x80 | channel, pitch, 0])))
                continue

            share = (solution.passing_share[sounding_index - 1]
                     if sounding_index - 1 < len(solution.passing_share)
                     else spec.passing_share)
            head_ticks = int(round(ticks * (1.0 - share)))
            tail_ticks = ticks - head_ticks
            events.append((pending_rest_ticks,
                           bytes([0x90 | channel, pitch, velocity])))
            pending_rest_ticks = 0
            events.append((head_ticks, bytes([0x80 | channel, pitch, 0])))
            events.append((0, bytes([0x90 | channel, moved, velocity])))
            events.append((tail_ticks, bytes([0x80 | channel, moved, 0])))

        tracks.append(_midi_track(events))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TICKS_PER_QUARTER)
    return header + b"".join(tracks)


def write_solution(
    spec: ScoreSpec,
    solution: Chromosome,
    path_without_extension: str,
    formats: Sequence[str] = ("musicxml", "midi"),
) -> List[str]:
    """
    Write one solution to disk in the requested formats.

    Returns the list of paths actually written.
    """
    written: List[str] = []
    if "musicxml" in formats:
        path = f"{path_without_extension}.musicxml"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(build_musicxml(spec, solution))
        written.append(path)
    if "midi" in formats:
        path = f"{path_without_extension}.mid"
        with open(path, "wb") as handle:
            handle.write(build_midi(spec, solution))
        written.append(path)
    return written
