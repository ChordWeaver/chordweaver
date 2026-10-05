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
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

from . import i18n
from .ga import ChordSlot, Chromosome
from .passing import figure
from .theory import SHARP_NAMES, VoicePart, octave_of, spell_in_key, spell_pitch

#: MusicXML divisions per quarter note. 48 y no 8: una figura de adorno
#: reparte la cola de un acorde en tres, y un tercio de negra no es un
#: número entero de octavos --- se redondeaba a 3 de 8, la voz sumaba 33
#: donde el compás tenía 32, el ``<backup>`` dejaba de coincidir y todas las
#: voces que se escribían después salían corridas contra las primeras.
#: 48 divide exacto por 3 y por 16, así que tresillos y semicorcheas caben.
DIVISIONS_PER_QUARTER = 48

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
    #: La armadura, en sostenidos (+) o bemoles (-). Los tres modos que
    #: generan música escriben en Do y dejan esto en cero: la altura de cada
    #: nota ya viene decidida y la armadura sólo cambiaría cómo se escribe.
    #: El analizador sí la trae, porque analiza una partitura que ya tenía
    #: una y devolverla en Do sería devolver otra partitura.
    fifths: int = 0
    #: Una línea escrita **por voz**, indexada por voz del motor. Es lo
    #: mismo que ``melody`` pero para todas: cuando la partitura ya venía
    #: escrita ---el analizador--- lo que hay que guardar no es un acorde
    #: por hueco sino el ritmo de cada voz. Sin esto, una textura arpegiada
    #: salía con todas las voces reatacando en cada semicorchea: la nota
    #: tenida del bajo se escribía dieciséis veces por compás.
    voice_lines: Optional[Dict[int, "MelodyLine"]] = None
    #: Escribir cada altura por la armadura y no por el acorde. Lo pide lo
    #: que ya venía escrito: ahí la alteración es un hecho de la partitura y
    #: deducirla del acorde que suene encima la cambia.
    spell_by_key: bool = False
    #: La tonalidad de la pieza, en quintas, cuando el modo la conoce: la
    #: armadura que **no** se escribe pero decide cómo se escriben las notas
    #: que no son del acorde ---notas de paso, adornos, la melodía del
    #: armonizador---. Sin ella salían de la tabla de sostenidos: un si
    #: bemol de paso en Fa mayor se escribía la sostenido.
    key_hint: Optional[int] = None
    #: Si el primer compás es una anacrusa. MusicXML lo marca ``implicit``,
    #: que es lo que hace que el programa que lo abra no lo cuente ni le
    #: reclame los tiempos que le faltan.
    pickup: bool = False
    #: La tonalidad de cada compás, en quintas, por ``bar_index``: lo mismo
    #: que ``key_hint`` pero cuando la pieza no está toda en una. La melodía
    #: del Armonizador lleva la tónica en cada `MelodyBar`, y tomando la del
    #: primer compás para toda la pieza, el si bemol de paso de un tramo en
    #: Fa se escribía la sostenido porque arriba de todo decía Do. Un compás
    #: que no figura usa ``key_hint``.
    bar_key_hints: Optional[Dict[int, int]] = None

    def key_hint_for(self, bar_index: int) -> Optional[int]:
        """La tonalidad con que se escriben las notas ajenas al acorde ahí."""
        if self.bar_key_hints and bar_index in self.bar_key_hints:
            return self.bar_key_hints[bar_index]
        return self.key_hint

    def line_for(self, voice_index: int) -> Optional["MelodyLine"]:
        """La línea escrita de una voz, si la hay."""
        if self.melody is not None and self.melody.voice_index == voice_index:
            return self.melody
        if self.voice_lines is not None:
            return self.voice_lines.get(voice_index)
        return None

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


#: Las figuras escribibles, de mayor a menor. Con puntillo incluidas: una
#: negra con puntillo es una figura y escribirla como negra ligada a corchea
#: es escribir dos.
_WRITABLE = (8.0, 6.0, 4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25)


def _writable_pieces(quarters: float) -> List[float]:
    """
    Repartir una duración en figuras que existan, de mayor a menor.

    Una duración que no es ninguna figura ---la mitad de un tresillo, lo que
    queda de un compás partido por una barra--- no se puede escribir con un
    solo signo. Antes se la escribía con la figura más parecida y el
    ``<duration>`` de la real: el archivo sonaba bien y se veía mal, con
    corcheas que decían durar una negra. Repartida y ligada, dice lo que
    dura y se ve lo que es.
    """
    if quarters <= 1e-6:
        return []
    pieces: List[float] = []
    left = quarters
    for value in _WRITABLE:
        while left >= value - 1e-6:
            pieces.append(value)
            left -= value
    if left > 1e-6:
        # Lo que no cierre con ninguna figura se escribe igual: mentirle a
        # la duración correría todo lo que viene después.
        pieces.append(round(left, 6))
    return pieces or [quarters]


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
    #: Por voz, la altura que llega ligada desde el compás anterior: una
    #: línea escrita marca con un tercer elemento la nota que sigue después
    #: de la barra (ver `session._written_bar`).
    carried: Dict[int, Optional[int]] = {}

    for bar_number, bar_slots in enumerate(bars, start=1):
        signature = spec.signature_for_bar(bar_number - 1)
        bar_key = spec.key_hint_for(bar_slots[0].bar_index)
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
                f"\n        <key><fifths>{spec.fifths}</fifths></key>"
                if bar_number == 1 else ""
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
            line = spec.line_for(voice_index)
            written = (line.events_for(bar_slots[0].bar_index)
                       if line is not None else None)
            if written is not None:
                # Written from the line itself, so its rhythm survives. The
                # slot is still handed over for spelling: accidentals are
                # read off the chord sounding underneath, unless the spec
                # says to read them off the key signature instead.
                arriving = carried.pop(voice_index, None)
                for event_index, event in enumerate(written):
                    pitch, quarters = event[0], event[1]
                    goes_on = len(event) > 2 and bool(event[2])
                    comes_tied = (event_index == 0 and pitch is not None
                                  and pitch == arriving)
                    if goes_on:
                        carried[voice_index] = pitch
                    pieces = _writable_pieces(quarters)
                    for position, span in enumerate(pieces):
                        if pitch is None:
                            body.append(_rest_xml(
                                slot=bar_slots[0],
                                voice_number=musicxml_voice(voice_index),
                                staff=staff_of(voice_index),
                                duration_override=span,
                            ))
                            continue
                        # Una nota repartida en varias figuras se liga: son
                        # una sola nota escrita con mas de un signo. Y lo
                        # mismo a través de la barra: la que viene del
                        # compás anterior termina una ligadura y la que
                        # sigue en el próximo la empieza.
                        stop = position > 0 or comes_tied
                        start = position < len(pieces) - 1 or goes_on
                        tie = ("both" if stop and start else "stop" if stop
                               else "start" if start else None)
                        body.append(_note_xml(
                            pitch=pitch, slot=bar_slots[0],
                            voice_number=musicxml_voice(voice_index),
                            staff=staff_of(voice_index),
                            stem=stem_of(voice_index), fifths=spec.fifths,
                            key_hint=bar_key,
                            duration_override=span, tie=tie,
                            spell_by_key=spec.spell_by_key,
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
                has_passing = any(figure(n) for n in notes)
                sounding_index += 1

                if not has_passing:
                    body.append(_note_xml(
                        pitch=pitch, slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index), fifths=spec.fifths,
                        key_hint=bar_key,
                    ))
                    continue

                # Only the voice that ornaments is split. The others hold a
                # single note for the whole duration: re-articulating them
                # made every part move at once, so a single ornament looked
                # like all four voices changing together.
                moved_here = figure(notes[voice_index]
                                    if voice_index < len(notes) else None)
                if not moved_here:
                    body.append(_note_xml(
                        pitch=pitch, slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index), fifths=spec.fifths,
                        key_hint=bar_key,
                    ))
                    continue

                # The ornamenting voice splits: the chord tone, then the
                # ornament for the tail.
                share = (solution.passing_share[sounding_index - 1]
                         if sounding_index - 1 < len(solution.passing_share)
                         else spec.passing_share)
                head = slot.duration_quarters * (1.0 - share)
                body.append(_note_xml(
                    pitch=pitch, slot=slot,
                    voice_number=musicxml_voice(voice_index),
                    staff=staff_of(voice_index),
                    stem=stem_of(voice_index), fifths=spec.fifths,
                    key_hint=bar_key,
                    duration_override=head,
                ))
                # La cola se reparte entre las notas de la figura. Una figura
                # de una nota escribe exactamente lo que escribia antes; una
                # de tres escribe tres, y el compas sigue sumando lo mismo
                # porque lo que se reparte es la misma cola.
                # Repartida en divisiones enteras, como el MIDI la reparte en
                # ticks: cada pedazo va de una frontera redondeada a la
                # siguiente, así que la voz suma exactamente lo que el
                # compás aunque la división no sea exacta.
                units = DIVISIONS_PER_QUARTER
                whole = int(round(slot.duration_quarters * units))
                held = int(round(head * units))
                count = len(moved_here)
                for index, moved in enumerate(moved_here):
                    first = held + (whole - held) * index // count
                    last = held + (whole - held) * (index + 1) // count
                    body.append(_note_xml(
                        pitch=moved, slot=slot,
                        voice_number=musicxml_voice(voice_index),
                        staff=staff_of(voice_index),
                        stem=stem_of(voice_index), fifths=spec.fifths,
                        key_hint=bar_key,
                        duration_override=(last - first) / units,
                    ))

        slot_cursor += len(bar_slots)
        # La anacrusa se marca `implicit`: es un compas incompleto a
        # proposito, y sin la marca cualquier editor lo cuenta como el
        # primero y avisa que le faltan tiempos.
        implicit = ' implicit="yes"' if spec.pickup and bar_number == 1 else ""
        measures.append(
            f'\n    <measure number="{bar_number}"{implicit}>{attributes}'
            + "".join(body)
            + "\n    </measure>"
        )

    # En el idioma en que se exporta: el catálogo de voces está en
    # castellano, y un archivo exportado en inglés decía «Bajo, Tenor».
    part_names = ", ".join(i18n.tr_name(v.name) for v in spec.voices)
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


#: En qué orden altera una armadura a las letras. Sirve para no escribir un
#: sostenido que la armadura ya puso: un fa sostenido en Sol mayor no lleva
#: accidente, y escribírselo igual llena la partitura de alteraciones de más.
_SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
_FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")


def _signature_alteration(letter: str, fifths: int) -> int:
    if fifths > 0 and letter in _SHARP_ORDER[:min(7, fifths)]:
        return 1
    if fifths < 0 and letter in _FLAT_ORDER[:min(7, -fifths)]:
        return -1
    return 0


def _note_xml(
    pitch: int,
    slot: ChordSlot,
    voice_number: int,
    staff: int,
    stem: str,
    duration_override: Optional[float] = None,
    fifths: int = 0,
    tie: Optional[str] = None,
    spell_by_key: bool = False,
    key_hint: Optional[int] = None,
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
    if spell_by_key:
        # Lo que ya venía escrito se escribe como estaba: la armadura manda
        # y el acorde no opina. Deducirlo del acorde llenaba de sostenidos
        # una armonización leída en Fa.
        step, alter, octave = spell_in_key(pitch, fifths)
    elif tone is None and chord.bass_pc is not None and pitch % 12 == chord.bass_pc:
        # Con la letra con la que se escribió el bajo: «C/Bb» es un si
        # bemol, y leyéndolo de la tabla de sostenidos salía la sostenido.
        step, alter, octave = spell_pitch(
            pitch, chord.bass_letter or SHARP_NAMES[chord.bass_pc][0], 0, "1")
    elif tone is None and key_hint is not None:
        # Una nota ajena al acorde no tiene grado del que deducirse: la
        # escribe la tonalidad.
        step, alter, octave = spell_in_key(pitch, key_hint)
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
    # Sólo lo que la armadura no puso ya. Con la armadura en Do ---los tres
    # modos que generan música--- esto no cambia nada, porque ahí toda
    # alteración es un accidente.
    if alter != _signature_alteration(step, fifths):
        accidental_xml = {
            1: "<accidental>sharp</accidental>",
            -1: "<accidental>flat</accidental>",
            2: "<accidental>double-sharp</accidental>",
            -2: "<accidental>flat-flat</accidental>",
            # La séptima disminuida de un acorde que ya arranca alterado
            # ---Cbdim7 lleva un si triple bemol--- también existe.
            3: "<accidental>triple-sharp</accidental>",
            -3: "<accidental>triple-flat</accidental>",
            0: "<accidental>natural</accidental>",
        }.get(alter, "")

    # La ligadura de prolongación se escribe dos veces: `<tie>` es lo que
    # suena y `<tied>` es lo que se dibuja, y un programa de notación
    # necesita las dos. La cola de una ligadura no repite el accidente: la
    # nota es la misma que ya estaba sonando.
    tie_xml = tied_xml = ""
    kinds = (("start", "stop") if tie == "both" else (tie,) if tie else ())
    for kind in kinds:
        tie_xml += '<tie type="%s"/>' % kind
        tied_xml += '<tied type="%s"/>' % kind
    if tie in ("stop", "both"):
        accidental_xml = ""
    tie_line = ("\n        " + tie_xml) if tie_xml else ""
    notations = (("\n        <notations>" + tied_xml + "</notations>")
                 if tied_xml else "")

    return (
        "\n      <note>"
        f"\n        <pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
        f"\n        <duration>{duration_units}</duration>"
        f"{tie_line}"
        f"\n        <voice>{voice_number}</voice>"
        f"\n        <type>{note_type}</type>{dot_xml}{accidental_xml}"
        f"\n        <stem>{stem}</stem>"
        f"\n        <staff>{staff}</staff>"
        f"{notations}"
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
    title = spec.title.encode("ascii", "replace")[:127]
    meta_events: List[Tuple[int, bytes]] = [
        (0, b"\xff\x51\x03" + tempo_bytes),
        (
            0,
            b"\xff\x58\x04"
            + bytes([signature.beats, denominator_power, 24, 8]),
        ),
        # Recortado como el nombre de cada voz: el largo de un meta-evento va
        # en un byte acá, y un título de más de 127 caracteres corrompía el
        # archivo (y uno de más de 255 hacía fallar la exportación).
        (0, b"\xff\x03" + bytes([len(title)]) + title),
    ]
    tracks.append(_midi_track(meta_events))

    for voice_index, voice in enumerate(spec.voices):
        events: List[Tuple[int, bytes]] = []
        # Sin acentos y no con signos de pregunta: el nombre de pista MIDI
        # es ASCII, y «Barítono» se grababa «Bar?tono».
        name = unicodedata.normalize("NFKD", i18n.tr_name(voice.name)).encode(
            "ascii", "ignore")[:127]
        events.append((0, b"\xff\x03" + bytes([len(name)]) + name))
        channel = min(voice_index, 15)

        pending_rest_ticks = 0
        sounding_index = 0

        line = spec.line_for(voice_index)
        if line is not None:
            # La nota que cruza la barra no se apaga: sigue sonando y se le
            # suman los ticks del primer pedazo del compás siguiente. Es la
            # misma ligadura que escribe el MusicXML.
            held: Optional[Tuple[int, int]] = None      # (altura, ticks)
            for bar_slots in group_slots_into_bars(spec):
                for event_index, event in enumerate(
                        line.events_for(bar_slots[0].bar_index) or []):
                    melody_pitch, quarters = event[0], event[1]
                    goes_on = len(event) > 2 and bool(event[2])
                    ticks = int(round(quarters * TICKS_PER_QUARTER))
                    if (held is not None and event_index == 0
                            and melody_pitch == held[0]):
                        held = (held[0], held[1] + ticks)
                    else:
                        if held is not None:
                            events.append((held[1], bytes([0x80 | channel,
                                                           held[0], 0])))
                            held = None
                        if melody_pitch is None:
                            pending_rest_ticks += ticks
                            continue
                        events.append((pending_rest_ticks,
                                       bytes([0x90 | channel, melody_pitch,
                                              velocity])))
                        pending_rest_ticks = 0
                        held = (melody_pitch, ticks)
                    if not goes_on:
                        events.append((held[1], bytes([0x80 | channel,
                                                       held[0], 0])))
                        held = None
            if held is not None:
                events.append((held[1], bytes([0x80 | channel, held[0], 0])))
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
            moved = figure(notes[voice_index]
                           if voice_index < len(notes) else None)
            sounding_index += 1

            if not moved:
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
            # La cola, repartida entre las notas de la figura. El ultimo
            # pedazo se lleva lo que sobra de la division entera para que el
            # compas cierre en el tick exacto.
            span = tail_ticks // len(moved)
            for index, note in enumerate(moved):
                last = index == len(moved) - 1
                length = tail_ticks - span * index if last else span
                events.append((0, bytes([0x90 | channel, note, velocity])))
                events.append((length, bytes([0x80 | channel, note, 0])))

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
