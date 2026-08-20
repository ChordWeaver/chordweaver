# -*- coding: utf-8 -*-
"""
Harmonising a melody someone else wrote.

The other two modes start from chords. This one starts from a line and works
out what could sit underneath it, which is a different problem: the melody is
fixed, and every chord has to accommodate a note that is already decided.

How it works
------------
Chords are placed on strong beats only -- that is where harmony is heard to
change -- and the note that falls there decides what fits. A chord is judged
by the role the melody note plays in it: the third is the most characteristic
place for a melody to sit, the fifth next, the root best at points of repose.
Sixths, sevenths and ninths are available when the user has asked for colour,
at lower priority.

The pass runs **backwards**, from the last chord to the first. Harmony is
heard as approach rather than departure: knowing that the next chord is a
point of rest is what tells you the current one wants to be a dominant, and
that information only exists if the end is decided first.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .harmony import (
    DOMINANT,
    GRAMMARS,
    MODES,
    grammar_cost,
    Mode,
    ChordOption,
    build_chord_pool,
    function_of,
)

#: Melody notes shorter than this are never harmonised on their own.
MIN_DURATION = 0.5


# ---------------------------------------------------------------------------
# The melody
# ---------------------------------------------------------------------------

@dataclass
class MelodyNote:
    """One note of the given line."""

    pitch: int                       # MIDI; None would be a rest
    duration_quarters: float
    bar_index: int
    offset_quarters: float           # from the start of its bar
    is_rest: bool = False
    #: El usuario marcó esta nota: quiere un acorde debajo de ella, caiga
    #: donde caiga. Sin esto, el armonizador escribe sobre los tiempos
    #: fuertes y una nota en el medio del compás se escucha contra el acorde
    #: del tiempo anterior --- que casi siempre está bien, y a veces es
    #: justamente la nota que la persona quería sostener.
    must_harmonise: bool = False


@dataclass
class MelodyBar:
    """A bar of the melody, with its own metre and key."""

    beats: int = 4
    beat_type: int = 4
    tonic: int = 0                   # pitch class
    mode_key: str = "major"

    @property
    def quarters(self) -> float:
        return self.beats * 4.0 / self.beat_type

    @property
    def mode(self) -> Mode:
        return MODES.get(self.mode_key, MODES["major"])


@dataclass
class Melody:
    """A line to harmonise, plus the bars it runs through."""

    notes: List[MelodyNote] = field(default_factory=list)
    bars: List[MelodyBar] = field(default_factory=list)
    #: Which voice the user wrote, as an index into the voice list.
    melody_voice: int = 0

    def bar(self, index: int) -> MelodyBar:
        if 0 <= index < len(self.bars):
            return self.bars[index]
        return MelodyBar()

    def sounding_at(self, bar_index: int, offset: float) -> Optional[MelodyNote]:
        """The note sounding at a moment, if any."""
        for note in self.notes:
            if note.bar_index != bar_index or note.is_rest:
                continue
            if note.offset_quarters <= offset + 1e-6 < (
                    note.offset_quarters + note.duration_quarters):
                return note
        return None

    def next_after(self, bar_index: int, offset: float) -> Optional[MelodyNote]:
        """The next note to begin after a moment."""
        best = None
        for note in self.notes:
            if note.is_rest:
                continue
            position = (note.bar_index, note.offset_quarters)
            if position <= (bar_index, offset):
                continue
            if best is None or position < (best.bar_index, best.offset_quarters):
                best = note
        return best


def strong_beat_offsets(beats: int, beat_type: int) -> List[float]:
    """
    Where harmony is heard to change in a regular metre.

    Simple metres put a secondary accent halfway through when they have an
    even number of beats -- the third beat of a bar of four. Compound metres
    accent the start of each group of three, which is what makes 6/8 two
    beats rather than six.
    """
    quarters_per_beat = 4.0 / beat_type
    if beat_type == 8 and beats % 3 == 0 and beats >= 6:
        group = 3 * quarters_per_beat
        return [index * group for index in range(beats // 3)]
    total = beats * quarters_per_beat
    if beats % 2 == 0 and beats > 2:
        return [0.0, total / 2.0]
    return [0.0]


@dataclass
class HarmonySpot:
    """A strong beat waiting for a chord."""

    bar_index: int
    offset_quarters: float
    duration_quarters: float
    #: The melody note this chord has to accommodate, if there is one.
    note: Optional[MelodyNote] = None
    #: A chord the user pinned here, by roman numeral.
    forced_roman: str = ""
    #: La nota que este lugar tiene que sostener, cuando no se elige sino
    #: que viene dada: la marcó el usuario. `choose_note_for_spot` puede
    #: preferir la nota siguiente cuando entra mucho mejor en los acordes
    #: disponibles, y eso es exactamente lo que no se quiere acá --- se
    #: pidió un acorde para **esta** nota.
    required_note: Optional["MelodyNote"] = None
    #: Grados de la escala a los que queda limitado este lugar, cuando algo
    #: lo exige. Por grado y no por cifra romana porque la cifra cambia con
    #: el modo --- el quinto es "V" en mayor y "v" en menor --- y lo que se
    #: quiere fijar es la función, que no cambia.
    allowed_degrees: Tuple[int, ...] = ()


def bar_events(melody: Melody,
               bar_index: int) -> List[Tuple[Optional[int], float]]:
    """
    One bar of the given line as ``(pitch, quarters)``, gaps filled.

    A ``None`` pitch is a rest. The events are padded to the bar length and
    trimmed if a note runs past it, because a measure whose durations do not
    add up is rejected by every notation program -- and the line the user
    drew is under no obligation to fill its bars exactly.

    This is what the exporter writes for the melody voice. The search never
    sees it: there the line is sampled one note per chord, which is the
    rhythm the counterpoint is judged on.
    """
    bar = melody.bar(bar_index)
    total = bar.quarters
    written = sorted(
        (note for note in melody.notes if note.bar_index == bar_index),
        key=lambda note: note.offset_quarters,
    )

    events: List[Tuple[Optional[int], float]] = []
    cursor = 0.0
    for note in written:
        if note.offset_quarters > cursor + 1e-6:
            events.append((None, note.offset_quarters - cursor))
            cursor = note.offset_quarters
        length = min(note.duration_quarters, total - cursor)
        if length <= 1e-6:
            continue
        events.append((None if note.is_rest else note.pitch, length))
        cursor += length
    if cursor < total - 1e-6:
        events.append((None, total - cursor))
    return events


def harmony_spots(melody: Melody) -> List[HarmonySpot]:
    """Every strong beat in the melody, in order."""
    spots: List[HarmonySpot] = []
    for bar_index, bar in enumerate(melody.bars):
        offsets = strong_beat_offsets(bar.beats, bar.beat_type)
        for position, offset in enumerate(offsets):
            end = (offsets[position + 1] if position + 1 < len(offsets)
                   else bar.quarters)
            spots.append(HarmonySpot(
                bar_index=bar_index,
                offset_quarters=offset,
                duration_quarters=end - offset,
            ))

    # A tune that ends on a weak beat still ends: leaving the final note
    # unharmonised means the cadence lands on whatever happened to fall on
    # the last strong beat, which is usually the note before the arrival.
    last = max((n for n in melody.notes if not n.is_rest),
               key=lambda n: (n.bar_index, n.offset_quarters), default=None)
    if last is not None and spots:
        final = spots[-1]
        already = (final.bar_index == last.bar_index
                   and abs(final.offset_quarters - last.offset_quarters) < 1e-6)
        # Y sólo si la nota cae DESPUÉS del último tiempo fuerte. Cuando el
        # último compás lleva una nota sola al principio --- una melodía que
        # cierra con una redonda, por ejemplo --- la nota cae antes, y este
        # bloque le restaba: el lugar de la mitad del compás quedaba de media
        # negra y se agregaba otro encima del que ya estaba en el uno. El
        # compás sumaba tres negras y media en un cuatro por cuatro, que es
        # una partitura que ningún editor acepta, y encima quedaban dos
        # acordes distintos escritos en el mismo lugar.
        after = (last.bar_index > final.bar_index
                 or (last.bar_index == final.bar_index
                     and last.offset_quarters > final.offset_quarters + 1e-6))
        if not already and after:
            final.duration_quarters = max(
                0.5, last.offset_quarters - final.offset_quarters)
            spots.append(HarmonySpot(
                bar_index=last.bar_index,
                offset_quarters=last.offset_quarters,
                duration_quarters=last.duration_quarters,
            ))

        # Y nada de acordes después de que la melodía terminó. Una línea que
        # no llena su último compás --- nueve negras en cuatro por cuatro,
        # por ejemplo --- dejaba tres tiempos vacíos que igual recibían su
        # acorde, así que la cadencia caía sobre el silencio: la última nota
        # se armonizaba con el anteúltimo acorde y la tónica final sonaba
        # sola, sin nadie escuchándola. Se corta ahí y el último acorde
        # vuelve a ser el de la última nota.
        end_bar, end_offset = last.bar_index, (last.offset_quarters
                                               + last.duration_quarters)
        trimmed = [spot for spot in spots
                   if (spot.bar_index, spot.offset_quarters)
                   < (end_bar, end_offset - 1e-6)]
        if trimmed and len(trimmed) < len(spots):
            # Lo que ocupaban los que se van se lo queda el que queda: el
            # acorde final se estira hasta donde llegaba el último, así que
            # los compases siguen sumando lo que dice el compás y la nota
            # final se sostiene con un acorde solo en vez de con tres.
            trimmed[-1].duration_quarters += sum(
                spot.duration_quarters for spot in spots[len(trimmed):])
            spots = trimmed

    # Y las notas que el usuario marcó, al final: se les abre un lugar
    # propio si no cayó ninguno encima. Va después del recorte porque el
    # recorte reparte duraciones, y un lugar abierto antes se le habría
    # escapado a esa cuenta.
    for note in _sounding_notes(melody):
        if not note.must_harmonise:
            continue
        spot = spot_for_note(spots, note)
        if spot is not None:
            spot.required_note = note
    return spots


def spot_for_note(spots: List[HarmonySpot],
                  note: MelodyNote) -> Optional[HarmonySpot]:
    """
    El lugar de acorde que cae sobre una nota, abriéndolo si no lo hay.

    Es la maniobra que hacía `pin_leading_tone` para su sensible y que ahora
    hacen las dos cosas que necesitan un acorde en un punto que el compás no
    eligió. El lugar que se parte se queda con lo que hay hasta la nota y el
    nuevo con **todo el resto**, no con la duración de la nota: los lugares
    reparten el compás entre ellos, así que dejar el sobrante sin dueño es
    escribir un compás que no suma --- y un compás que no suma lo rechaza
    cualquier editor de partituras.

    Devuelve None cuando la nota cae fuera de todo lugar, que es lo que pasa
    con lo que quedó después de que la melodía terminó.
    """
    here = next((spot for spot in spots
                 if spot.bar_index == note.bar_index
                 and abs(spot.offset_quarters
                         - note.offset_quarters) < 1e-6), None)
    if here is not None:
        return here

    covering = next(
        (spot for spot in spots
         if spot.bar_index == note.bar_index
         and spot.offset_quarters <= note.offset_quarters
         < spot.offset_quarters + spot.duration_quarters), None)
    if covering is None:
        return None
    end = covering.offset_quarters + covering.duration_quarters
    head = note.offset_quarters - covering.offset_quarters
    if head < MIN_DURATION:
        # El lugar de al lado quedaría más corto que cualquier acorde que
        # este programa escribe. Se lo corre entero en vez de partirlo, y lo
        # que quedaba antes de la nota se lo lleva el lugar anterior: correr
        # el lugar y no dárselo a nadie deja ese tiempo sin acorde, y un
        # compás al que le falta un pedazo lo rechaza cualquier editor de
        # partituras.
        position = spots.index(covering)
        earlier = spots[position - 1] if position else None
        if earlier is None or earlier.bar_index != covering.bar_index:
            # No hay a quién dárselo. El acorde entonces arranca un poco
            # antes que la nota, que es lo de menos: igual la sostiene.
            return covering
        earlier.duration_quarters += head
        covering.offset_quarters = note.offset_quarters
        covering.duration_quarters = end - note.offset_quarters
        return covering
    covering.duration_quarters = head
    fresh = HarmonySpot(
        bar_index=note.bar_index,
        offset_quarters=note.offset_quarters,
        duration_quarters=end - note.offset_quarters,
    )
    spots.insert(spots.index(covering) + 1, fresh)
    return fresh


# ---------------------------------------------------------------------------
# How well a melody note sits in a chord
# ---------------------------------------------------------------------------

#: Cost of each role the melody note can play. Lower is better.
#:
#: The third is where a melody most characteristically sits -- it is the note
#: that tells you whether the chord is major or minor, so hearing it on top
#: identifies the harmony. The fifth is neutral and safe. The root is plain
#: and works best where the music comes to rest.
ROLE_COST = {
    3: 0.0,      # minor third
    4: 0.0,      # major third
    7: 14.0,     # fifth
    0: 26.0,     # root
}

#: Colour tones, offered only when the user asked for colour.
COLOUR_COST = {
    9: 44.0,     # sixth
    10: 52.0,    # minor seventh
    11: 52.0,    # major seventh
    2: 58.0,     # ninth
}

#: The root is the natural place to land, so it is cheap at the ends.
ROOT_AT_REST = -22.0

#: A melody note that is in the chord at all beats one that is not, by a wide
#: margin: harmonising a passing note as though it were structural is the
#: main way this kind of thing goes wrong.
NOT_A_CHORD_TONE = 400.0


def note_fit(
    option: ChordOption,
    pitch: int,
    allow_colour: bool,
    at_rest: bool = False,
) -> float:
    """
    What it costs to harmonise this note with this chord.

    Returns a large number when the note is not in the chord at all, so such
    a pairing only survives when nothing else is available.
    """
    interval = (pitch - option.root_pc) % 12
    chord_intervals = {tone.semitones % 12 for tone in option.chord.tones}

    if interval in ROLE_COST and interval in chord_intervals:
        cost = ROLE_COST[interval]
        if interval == 0 and at_rest:
            cost += ROOT_AT_REST
        return cost

    if interval in chord_intervals:
        # A seventh that genuinely belongs to the chord is a normal place for
        # a melody, whether or not extra colour was asked for.
        return COLOUR_COST.get(interval, 60.0)

    if allow_colour and interval in COLOUR_COST:
        return COLOUR_COST[interval]

    return NOT_A_CHORD_TONE


def melodic_weight(cost: float) -> float:
    """
    Scale the melodic fit so it outweighs everything else.

    The whole question this mode answers is what chord holds the note the
    user wrote. Left on the same scale as the progression terms, a chord
    that reads well as harmony could win while leaving the melody note
    outside it -- which is how a Bdim turned up under an A.
    """
    return cost * 3.0


def choose_note_for_spot(
    melody: Melody,
    spot: HarmonySpot,
    options: Sequence[ChordOption],
    allow_colour: bool,
) -> Optional[MelodyNote]:
    """
    Decide which note this chord is really harmonising.

    The note on the beat is the obvious candidate, but it may be a suspension
    or an anacrusis -- a note that resolves into the harmony rather than
    stating it. When the following note fits the available chords markedly
    better, that one is taken as the real target.
    """
    on_beat = melody.sounding_at(spot.bar_index, spot.offset_quarters)
    following = melody.next_after(spot.bar_index, spot.offset_quarters)
    if on_beat is None:
        return following
    if following is None or not options:
        return on_beat

    def best_cost(note: MelodyNote) -> float:
        return min(note_fit(option, note.pitch, allow_colour)
                   for option in options)

    on_beat_cost = best_cost(on_beat)
    following_cost = best_cost(following)
    # Only defer to the next note when it is clearly better, and only when
    # it arrives soon enough to still belong to this chord.
    close_enough = (following.bar_index == spot.bar_index
                    and following.offset_quarters
                    < spot.offset_quarters + spot.duration_quarters)
    if close_enough and following_cost + 40.0 < on_beat_cost:
        return following
    return on_beat


# ---------------------------------------------------------------------------
# Choosing the chords
# ---------------------------------------------------------------------------

@dataclass
class HarmonisationSettings:
    """What the harmoniser is allowed to do."""

    genre_key: str = "chorale"
    allow_colour: bool = False
    #: Whether iv and bVII may be used.
    allow_borrowed: bool = True
    with_sevenths: bool = False
    #: Reward for a dominant standing before a point of repose. Applied when
    #: working backwards, which is the whole reason for going that way.
    dominant_before_rest: float = -70.0
    #: Cost of repeating the same chord on consecutive strong beats.
    #: Kept well below the cost of misplacing the melody: what note the
    #: melody has in the chord matters more than avoiding a repetition.
    repeat: float = 22.0
    #: How often iv is taken in place of IV, and of V.
    borrowed_iv_for_four: float = 0.30
    borrowed_iv_for_five: float = 0.10
    borrowed_flat_seven: float = 0.35


def _pool_for_bar(
    bar: MelodyBar,
    settings: HarmonisationSettings,
) -> List[ChordOption]:
    """The chords available in one bar's key."""
    borrowed = ["iv", "bVII"] if settings.allow_borrowed else []
    return build_chord_pool(bar.tonic, bar.mode, borrowed,
                            settings.with_sevenths)


#: Los grados que pueden sostener la sensible antes de la tonica.
#:
#: El quinto siempre: la sensible ES su tercera, y ese semitono subiendo a
#: la tonica es la cadencia entera. En jazz se agrega el septimo, que es el
#: mismo tritono sin la fundamental --- un Bm7b5 sobre un si es lo que ese
#: idioma escribe donde el coral escribe un sol.
LEADING_TONE_DEGREES = (5,)
LEADING_TONE_DEGREES_JAZZ = (5, 7)


def _sounding_notes(melody: Melody) -> List[MelodyNote]:
    """Las notas de verdad, en orden y sin los silencios."""
    return sorted((n for n in melody.notes if not n.is_rest),
                  key=lambda n: (n.bar_index, n.offset_quarters))


def pin_leading_tone(
    melody: Melody,
    spots: List[HarmonySpot],
    settings: HarmonisationSettings,
) -> None:
    """
    Si la anteultima nota es la sensible, ponerle su dominante debajo.

    Una melodia que sube por la sensible a la tonica esta pidiendo una
    cadencia y no otra cosa; armonizarla con cualquier acorde que contenga
    esa nota --- el septimo en primera inversion, un iii --- deja la pieza
    cerrando sin haber cerrado. Y si en ese punto no caia ningun acorde,
    directamente no habia cadencia: la dominante se escuchaba un tiempo
    antes, sobre otra nota, y la sensible pasaba como si fuera de adorno.
    Aca se le abre un lugar propio, con la duracion de la nota.

    No hace nada cuando el modo no tiene sensible --- el menor natural la
    tiene rebajada, y su quinto grado es menor --- porque ahi el acorde que
    se forzaria no contiene la nota que vino a sostener.
    """
    notes = _sounding_notes(melody)
    if len(notes) < 2 or not spots:
        return
    penultimate = notes[-2]
    bar = melody.bar(penultimate.bar_index)
    if penultimate.pitch % 12 != (bar.tonic - 1) % 12:
        return

    degrees = (LEADING_TONE_DEGREES_JAZZ if settings.genre_key == "jazz"
               else LEADING_TONE_DEGREES)
    # Sólo sirve si el acorde que se va a exigir contiene la nota. En el
    # menor natural no la contiene ninguno, y forzarlo igual pondria la
    # sensible como nota extraña encima de su propio acorde.
    pool = _pool_for_bar(bar, settings)
    usable = tuple(
        degree for degree in degrees
        if any(option.scale_degree == degree
               and penultimate.pitch % 12 in {
                   option.chord.pitch_class_of(t) for t in option.chord.tones}
               for option in pool)
    )
    if not usable:
        return

    # Si no caia ningun acorde sobre la sensible, se le abre uno partiendo
    # el que la cubria: la misma maniobra que necesita una nota marcada por
    # el usuario, y por eso vive en `spot_for_note`.
    here = spot_for_note(spots, penultimate)
    if here is not None:
        here.allowed_degrees = usable


def harmonise(
    melody: Melody,
    settings: HarmonisationSettings,
    rng: Optional[random.Random] = None,
) -> List[Tuple[HarmonySpot, ChordOption]]:
    """
    Pick a chord for every strong beat.

    Runs from the last spot to the first: the chord after this one is what
    says whether a dominant is wanted here, and that is only known once the
    later chord exists.
    """
    picker = rng or random.Random()
    spots = harmony_spots(melody)
    if not spots:
        return []
    pin_leading_tone(melody, spots, settings)

    chosen: List[Optional[ChordOption]] = [None] * len(spots)

    for index in range(len(spots) - 1, -1, -1):
        spot = spots[index]
        bar = melody.bar(spot.bar_index)
        pool = _pool_for_bar(bar, settings)
        at_rest = index in (0, len(spots) - 1)

        # Una nota marcada no se discute: el lugar existe porque alguien
        # pidió un acorde para ella.
        spot.note = spot.required_note or choose_note_for_spot(
            melody, spot, pool, settings.allow_colour)

        if spot.forced_roman:
            pinned = next((o for o in pool if o.roman == spot.forced_roman), None)
            if pinned is not None:
                chosen[index] = pinned
                continue

        following = chosen[index + 1] if index + 1 < len(chosen) else None
        scored: List[Tuple[float, ChordOption]] = []
        allowed = spot.allowed_degrees
        for option in pool:
            if allowed and option.scale_degree not in allowed:
                continue
            if not _borrowed_allowed(option, index, len(spots), settings, picker):
                continue
            cost = 0.0
            if spot.note is not None:
                cost += melodic_weight(note_fit(
                    option, spot.note.pitch, settings.allow_colour, at_rest))
            cost += _progression_cost(option, following, bar, settings, index,
                                      len(spots))
            scored.append((cost, option))

        if not scored:
            continue
        scored.sort(key=lambda pair: pair[0])
        # A little randomness among near-equal choices, so two runs on the
        # same melody are not identical.
        # Anything within a real margin of the best is fair game, so the same
        # melody comes back harmonised differently on a second run. The
        # margin is generous on purpose: the top few candidates usually hold
        # the melody note equally well and differ only in how they connect.
        best = scored[0][0]
        close = [option for cost, option in scored if cost <= best + 55.0]
        chosen[index] = picker.choice(close) if close else scored[0][1]

    return [(spot, option) for spot, option in zip(spots, chosen)
            if option is not None]


def planned_notes(
    melody: Melody,
    settings: HarmonisationSettings,
) -> List[MelodyNote]:
    """
    Qué notas van a recibir un acorde, sin armonizar nada todavía.

    Es la misma cuenta que hace `harmonise` --- los mismos lugares, la misma
    elección de nota por lugar --- pero sin elegir acordes, así que no
    depende del azar y se puede correr en cada tecla mientras el usuario
    dibuja. Existe para que el pentagrama pueda pintarlas de dorado: la
    pregunta "¿a cuál de estas notas le va a poner un acorde?" no tenía
    respuesta hasta después de esperar la búsqueda entera, y era la única
    manera de entender por qué una nota sonaba contra la armonía anterior.
    """
    spots = harmony_spots(melody)
    if not spots:
        return []
    pin_leading_tone(melody, spots, settings)
    seen = set()
    out: List[MelodyNote] = []
    for spot in spots:
        pool = _pool_for_bar(melody.bar(spot.bar_index), settings)
        note = spot.required_note or choose_note_for_spot(
            melody, spot, pool, settings.allow_colour)
        if note is None:
            continue
        where = (note.bar_index, note.offset_quarters)
        if where in seen:
            continue
        seen.add(where)
        out.append(note)
    return out


def _borrowed_allowed(
    option: ChordOption,
    index: int,
    total: int,
    settings: HarmonisationSettings,
    picker: random.Random,
) -> bool:
    """
    Whether a borrowed chord may be considered here.

    Both have narrow uses: the minor subdominant stands in for IV, and less
    often for V; the flat seventh belongs immediately before the close, where
    it approaches the tonic from below.
    """
    if not option.is_borrowed:
        return True
    if not settings.allow_borrowed:
        return False
    if option.roman == "iv":
        return picker.random() < max(settings.borrowed_iv_for_four,
                                     settings.borrowed_iv_for_five)
    if option.roman == "bVII":
        if index != total - 2:
            return False
        return picker.random() < settings.borrowed_flat_seven
    return False


def _progression_cost(
    option: ChordOption,
    following: Optional[ChordOption],
    bar: MelodyBar,
    settings: HarmonisationSettings,
    index: int,
    total: int,
) -> float:
    """How well this chord leads into the one already chosen after it."""
    cost = 0.0
    # Both ends want the tonic: a harmonisation that opens somewhere else
    # leaves the key unstated, and one that closes elsewhere leaves it open.
    if index in (0, total - 1) and option.root_pc != bar.tonic:
        # Decisive: a harmonisation that opens or closes away from the tonic
        # leaves the key unstated, whatever the style's grammar prefers.
        cost += 260.0
    if following is None:
        return cost

    if option.roman == following.roman:
        cost += settings.repeat

    # A dominant leading into a point of repose is the shape the backward
    # pass exists to find.
    if following.root_pc == bar.tonic and function_of(option) == DOMINANT:
        cost += settings.dominant_before_rest

    # The style's own grammar decides the rest, so a harmonisation sounds
    # like the idiom it was asked for: the same melody gets ii-V motion in
    # jazz and plagal closes in the modal setting.
    grammar = GRAMMARS.get(settings.genre_key)
    if grammar is not None:
        cost += grammar_cost(option, following, grammar, bar.tonic) * 0.6

    # The closing gesture is what makes a harmonisation sound like its style,
    # so the last approach is weighted well above the rest. Kept to the
    # cadence alone: pushing the whole progression this hard would flatten
    # the melodic fit that the mode exists to serve.
    if index == total - 2 and following.root_pc == bar.tonic:
        if settings.genre_key == "gregorian":
            if option.roman in ("IV", "iv"):
                cost += -150.0          # the plagal close
        elif settings.genre_key == "jazz":
            if option.roman == "V":
                cost += -120.0          # and the ii before it, below
        elif option.roman == "V":
            cost += -130.0              # the authentic cadence
    # In jazz the chord before the dominant wants to be the second degree.
    if (settings.genre_key == "jazz" and index == total - 3
            and following.roman == "V" and option.roman == "ii"):
        cost += -110.0
    return cost


# ---------------------------------------------------------------------------
# The weak-beat notes
# ---------------------------------------------------------------------------

#: Intervals above the bass that are harsh enough to matter even in passing.
#: A minor ninth is the sharpest dissonance there is, and a tritone against
#: the bass unsettles the harmony rather than decorating it.
HARSH_ABOVE_BASS = (1, 6)


def weak_beat_clashes(
    melody: Melody,
    spot: HarmonySpot,
    bass_pitch: int,
) -> int:
    """
    Count the ugly collisions a chord makes with the notes passing over it.

    The melody's weak-beat notes are free to be passing tones -- that is what
    they are for -- but a minor ninth or a tritone against the bass is heard
    as a mistake rather than as movement, so those are worth avoiding when
    there is a choice.
    """
    clashes = 0
    end = spot.offset_quarters + spot.duration_quarters
    for note in melody.notes:
        if note.is_rest or note.bar_index != spot.bar_index:
            continue
        if not (spot.offset_quarters <= note.offset_quarters < end):
            continue
        if abs(note.offset_quarters - spot.offset_quarters) < 1e-6:
            continue          # the strong-beat note is judged separately
        if (note.pitch - bass_pitch) % 12 in HARSH_ABOVE_BASS:
            clashes += 1
    return clashes


def clash_penalty(
    melody: Melody,
    spots: Sequence[HarmonySpot],
    chords: Sequence[Sequence[int]],
    weight: float = 55.0,
) -> float:
    """Total cost of the harsh collisions in a finished harmonisation."""
    total = 0.0
    for index, spot in enumerate(spots):
        if index >= len(chords) or not chords[index]:
            continue
        total += weight * weak_beat_clashes(melody, spot, chords[index][0])
    return total
