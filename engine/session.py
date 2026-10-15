# -*- coding: utf-8 -*-
"""
High-level façade tying the engine together.

The GUI should only ever need this module: it describes a job with plain data
(chord symbols, durations, switches), calls :func:`generate`, and gets back
solutions plus written files. Keeping the glue here means the interface can be
rewritten -- or replaced by a command line -- without touching the algorithm.
"""

from __future__ import annotations

import random

import os
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import export, flourish, harmonize, harmony, history, importer, passing
from .fitness import GENRE_PROFILES, GenreProfile, RunSettings
from .ga import ChordSlot, GAConfig, GAResult, SlotOption, run
from .style import ChordContext
from .theory import (
    Chord,
    ChordParseError,
    VoicePart,
    build_voice_parts,
    make_custom_chord,
    parse_chord,
    parse_pitch_class,
)
from .voicing import (
    ChordRequirement,
    build_requirement,
    build_voicing_plan,
    check_chord_fits,
    strip_special_voicings,
)
from engine.i18n import tr, trf, trs

#: Durations offered in the UI, expressed in quarter notes.
DURATION_CHOICES: Dict[str, float] = {
    "Whole (4)": 4.0,
    "Half (2)": 2.0,
    "Quarter (1)": 1.0,
    "Eighth (1/2)": 0.5,
}


@dataclass
class ChordEntry:
    """One chord as chosen by the user, before the engine processes it.

    ``symbol`` is an American chord symbol; when the user built the chord by
    hand on the piano instead, ``custom_pitch_classes`` carries the notes and
    the symbol is only a label.
    """

    symbol: str
    duration_quarters: float = 2.0
    bar_index: int = 0
    #: A rest: it takes up its duration but has nothing to voice.
    is_rest: bool = False
    custom_pitch_classes: Optional[List[int]] = None
    forced_omissions: List[str] = field(default_factory=list)
    #: When set, the exact MIDI pitches this chord must be sung with, lowest
    #: voice first. The GA will not touch them (the padlock in the UI).
    locked_pitches: Optional[List[int]] = None

    def to_chord(self) -> Chord:
        if self.custom_pitch_classes:
            return make_custom_chord(self.custom_pitch_classes, self.symbol or "custom")
        return parse_chord(self.symbol)


@dataclass
class JobRequest:
    """Everything the user configured, in one serialisable object."""

    genre_key: str
    voice_keys: List[str]
    entries: List[ChordEntry]
    time_signature: export.TimeSignature = field(
        default_factory=lambda: export.TimeSignature(4, 4)
    )
    bar_time_signatures: Optional[List[export.TimeSignature]] = None
    title: str = "ChordWeaver"
    tempo_bpm: int = 90
    #: Overrides applied on top of the genre profile (the switches screen).
    switch_overrides: Dict[str, Any] = field(default_factory=dict)
    #: Per-voice range overrides, keyed by voice index: {0: (low, high)}.
    range_overrides: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    ga_config: GAConfig = field(default_factory=GAConfig)
    solutions_wanted: int = 3
    #: Voice carrying the vox principalis, for organum. The vox organalis is
    #: the voice immediately below it, so one number describes the pair.
    #: Only the modal style acts on it.
    principalis_voice: Optional[int] = None
    #: Ornaments in the hand-written mode too. The same machinery as the
    #: generator; the only difference is where the scale comes from, since a
    #: typed progression declares no key.
    passing_rules: Optional[passing.PassingRules] = None

    @property
    def voice_count(self) -> int:
        return len(self.voice_keys)


@dataclass
class SetPieceInfo:
    """Which quotation turned up, if any, and where it sits."""

    label: str
    description: str
    #: Index of the solution that is the quotation; the generated ones
    #: follow it.
    solution_index: int = 0
    #: The quotation's chord symbols, shown only over that one solution.
    symbols: List[str] = field(default_factory=list)
    #: Slots carrying the quotation's chords, used when exporting it.
    slots: List = field(default_factory=list)


@dataclass
class JobOutcome:
    """Result of a generation run."""

    result: GAResult
    spec: Optional[export.ScoreSpec]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    set_piece: Optional[SetPieceInfo] = None
    #: The melody this was built from, when harmonising. Carried so playback
    #: and export can include every note, not just the ones on strong beats.
    melody: Optional[Any] = None
    #: Slots belonging to options other than the first, when each answer has
    #: its own progression.
    alternate_slots: Dict[int, Any] = field(default_factory=dict)
    #: Devices found or applied in the winning solution, for the interface
    #: to point out.
    flourishes: Optional[flourish.FlourishResult] = None
    #: Lo que la melodía del Armonizador canta al empezar y al terminar cada
    #: acorde, por opción (`_melody_edges`). La sexta de Bach lo mira para no
    #: dejar paralelas contra la melodía real.
    melody_edges: Dict[int, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return bool(self.result and self.result.solutions)


def build_settings(request: JobRequest) -> RunSettings:
    """Turn the request's genre and switches into concrete run settings."""
    profile = GENRE_PROFILES.get(request.genre_key)
    if profile is None:
        raise ValueError(f"Unknown genre: {request.genre_key!r}")

    known_fields = set(GenreProfile.__dataclass_fields__)
    overrides = {k: v for k, v in request.switch_overrides.items() if k in known_fields}
    profile = replace(profile, **overrides)

    voices = build_voice_parts(request.voice_keys)
    for index, (low, high) in request.range_overrides.items():
        if 0 <= index < len(voices):
            voices[index].low = low
            voices[index].high = high

    settings = RunSettings(profile=profile, voices=voices)
    # Organum needs a voice below the chosen one to shadow it, so the lowest
    # voice can never be the principalis; asking for it switches organum off
    # rather than silently reading past the end of the chord.
    principalis = getattr(request, "principalis_voice", None)
    if principalis is not None and 0 < principalis < len(voices):
        settings.principalis_voice = principalis
    return settings


def build_slots(request: JobRequest) -> Tuple[List[ChordSlot], List[str], List[str]]:
    """
    Convert chord entries into GA slots.

    Returns (slots, warnings, errors). A chord that cannot be parsed produces
    an error and stops the run; a chord that has more notes than voices
    produces a warning describing which degrees were dropped, because the
    user asked to be told rather than silently corrected.
    """
    slots: List[ChordSlot] = []
    warnings: List[str] = []
    errors: List[str] = []

    # The special-voicings switch has to be known here, because turning it off
    # changes which tones exist at all rather than merely how they are scored.
    settings_preview = build_settings(request)
    allow_special = settings_preview.profile.allow_special_voicings
    special_fills = settings_preview.profile.special_voicing_fills
    # The colour weight doubles as an appetite: the same dial that tells the
    # scoring how much it likes colour tells the voicing how often to reach
    # for one, so moving it changes the result rather than switching it on.
    appetite = min(1.0, abs(settings_preview.profile.weight_colour_tone) / 30.0)
    colour_rng = random.Random(request.ga_config.random_seed)

    for position, entry in enumerate(request.entries, start=1):
        if entry.is_rest:
            # Rests need no chord at all; a placeholder keeps the slot list
            # aligned with the bars while carrying no notes.
            slots.append(ChordSlot(
                requirement=build_requirement(parse_chord("C"), request.voice_count),
                duration_quarters=entry.duration_quarters,
                bar_index=entry.bar_index,
                is_rest=True,
            ))
            continue
        try:
            chord = entry.to_chord()
        except ChordParseError as exc:
            errors.append(trf("Acorde {position}: {reason}",
                              position=position, reason=exc))
            continue

        if not allow_special:
            chord = strip_special_voicings(chord)

        advice = check_chord_fits(chord, request.voice_count)
        if not advice.fits:
            if advice.suggested_omissions:
                warnings.append(trf("Acorde {position}: {reason}",
                                    position=position,
                                    reason=tr(advice.message)))
            else:
                errors.append(trf("Acorde {position}: {reason}",
                                  position=position,
                                  reason=tr(advice.message)))
                continue

        requirement = build_requirement(
            chord,
            request.voice_count,
            entry.forced_omissions or None,
            allow_special_voicings=allow_special,
            special_fills=special_fills,
            # A major sixth over a minor triad is the jazz m6 sound and has
            # no place in a modal or common-practice setting.
            allow_major_sixth_on_minor=(request.genre_key == "jazz"),
            colour_appetite=appetite, rng=colour_rng,
        )
        locked = entry.locked_pitches
        if locked and len(locked) != request.voice_count:
            warnings.append(
                trf("Acorde {position}: el candado fija {locked} notas "
                    "pero hay {voice_count} voces, así que se ignoró.",
                    position=position, locked=len(locked),
                    voice_count=request.voice_count)
            )
            locked = None

        slots.append(
            ChordSlot(
                requirement=requirement,
                duration_quarters=entry.duration_quarters,
                bar_index=entry.bar_index,
                locked_pitches=list(locked) if locked else None,
            )
        )

    return slots, warnings, errors


def generate(
    request: JobRequest,
    progress: Optional[Callable[[int, float], None]] = None,
) -> JobOutcome:
    """Run the whole pipeline for a request, without writing anything to disk."""
    slots, warnings, errors = build_slots(request)
    if errors:
        return JobOutcome(result=GAResult([], 0, 0, 0), spec=None, warnings=warnings, errors=errors)
    if not slots:
        return JobOutcome(
            result=GAResult([], 0, 0, 0),
            spec=None,
            warnings=warnings,
            errors=["No cargaste ningún acorde."],
        )

    settings = build_settings(request)
    # The search only sees the sounding chords. Voice leading is then
    # measured across a silence as though the chords either side of it were
    # adjacent, which is what a listener actually hears.
    sounding = [slot for slot in slots if not slot.is_rest]
    if not sounding:
        return JobOutcome(
            result=GAResult([], 0, 0, 0), spec=None, warnings=warnings,
            errors=["La pieza no tiene más que silencios."],
        )
    # What counts as diatonic is read off the music itself: a typed or
    # imported progression has no declared key, and inferring one and being
    # wrong is worse than letting the ornaments move through notes the piece
    # has already sounded.
    scale_pcs = importer.scale_from_chords(
        [slot.requirement.required_pitch_classes for slot in sounding]
    )
    result = run(
        sounding,
        settings,
        request.ga_config,
        progress=progress,
        solutions_wanted=request.solutions_wanted,
        passing_rules=request.passing_rules,
        scale_pcs=scale_pcs,
    )

    spec = export.ScoreSpec(
        slots=slots,
        voices=settings.voices,
        time_signature=request.time_signature,
        title=request.title,
        tempo_bpm=request.tempo_bpm,
        bar_time_signatures=request.bar_time_signatures,
    )

    outcome = JobOutcome(result=result, spec=spec, warnings=warnings)
    if not result.solutions:
        outcome.errors.append(result.message or "No se encontró ninguna solución válida.")
    return outcome


#: Lo que se escribe en lugar de un cifrado cuando el compás lleva silencio.
REST_SYMBOL = "\U0001D13D"          # 𝄽, el silencio de negra


def voiced_slots(spec, solution) -> List[List[int]]:
    """
    Las alturas de cada slot de la partitura, con el silencio en su lugar.

    La búsqueda **saltea los silencios**: no hay nada que repartir ahí, y la
    conducción de voces se mide de un acorde al siguiente como si el silencio
    no existiera, que es lo que se oye. La consecuencia es que
    ``solution.slots`` tiene menos entradas que ``spec.slots`` y las dos
    listas dejan de estar alineadas en cuanto aparece un silencio: todo lo
    que venga después queda corrido un lugar. En la pantalla de resultados
    eso se veía como las notas de un acorde debajo del nombre del anterior, y
    al escuchar, como una pieza que dura un compás menos y no tiene ningún
    silencio adentro.

    Acá se devuelven tantas listas como slots tenga la partitura, y el
    silencio es una lista vacía --- que es además lo que el sintetizador
    entiende: un acorde sin notas ocupa su tiempo y no suena.
    """
    out: List[List[int]] = []
    cursor = 0
    for slot in spec.slots:
        if slot.is_rest:
            out.append([])
            continue
        if cursor < len(solution.slots):
            out.append(list(solution.slots[cursor]))
        else:
            out.append([])
        cursor += 1
    return out


def solution_slots(outcome: "JobOutcome", position: int) -> List[ChordSlot]:
    """
    Los slots con los que se escribió la solución número ``position``.

    No siempre son los de ``outcome.spec``. En el Armonizador cada opción
    sale de su propia progresión (``alternate_slots``, indexado como
    ``result.solutions``) y ``spec.slots`` es la del primer intento, que
    después de ordenar por costo puede ser cualquiera de las tres; en el
    Generador, la cita va con los suyos (``set_piece.slots``). Leer los
    acordes de otra opción para exportar o para buscar marcas deletrea y
    rotula una solución contra acordes que no son los que suenan.
    """
    own = (getattr(outcome, "alternate_slots", None) or {}).get(position)
    if own:
        return own
    quotation = getattr(outcome, "set_piece", None)
    if (quotation is not None and getattr(quotation, "slots", None)
            and position == getattr(quotation, "solution_index", 0)):
        return quotation.slots
    return outcome.spec.slots


def ornaments_of(spec, solution) -> List[Tuple[int, int, int, float]]:
    """
    Las notas de adorno de una solución, ubicadas en la partitura.

    Devuelve una tupla por adorno --- ``(slot, voz, altura, porción)`` ---
    con el índice de slot de la **partitura**, no el de la búsqueda: la
    búsqueda saltea los silencios, así que ``solution.passing`` está corrido
    respecto de ``spec.slots`` en cuanto aparece uno, exactamente igual que
    ``solution.slots`` (ver `voiced_slots`).

    La porción es cuánto de la duración del acorde se lleva el adorno al
    final, que la puede fijar cada slot por su cuenta: es lo que hace que no
    todos los adornos duren lo mismo.
    """
    found: List[Tuple[int, int, Tuple[int, ...], float]] = []
    rows = getattr(solution, "passing", None) or []
    shares = getattr(solution, "passing_share", None) or []
    default = getattr(spec, "passing_share", 0.5)
    cursor = 0
    for index, slot in enumerate(spec.slots):
        if slot.is_rest:
            continue
        if cursor < len(rows):
            share = shares[cursor] if cursor < len(shares) else default
            for voice, entry in enumerate(rows[cursor]):
                shape = passing.figure(entry)
                if shape:
                    found.append((index, voice, shape, float(share)))
        cursor += 1
    return found


def playback_events(
    chords: Sequence[Sequence[int]],
    durations: Sequence[float],
    ornaments: Sequence[Sequence] = (),
    drop_voice: Optional[int] = None,
) -> Tuple[List[List[int]], List[float], List[Tuple[int, float, float]]]:
    """
    Lo que hay que mandarle al sintetizador para oír una solución entera.

    Un adorno parte el acorde en dos --- el acorde suena, y sobre el final
    la voz que adorna se mueve mientras las demás sostienen ---, y eso no se
    puede decir con una lista de acordes: todas las voces de un acorde
    empiezan y terminan juntas. Así que el slot adornado se vacía y sus
    voces salen como notas sueltas, cada una con su comienzo y su duración;
    el resto de la partitura queda como estaba.

    Las duraciones no cambian nunca: el adorno se lleva la cola del acorde
    que deja, no un tiempo de más. Un compás que sumaba cuatro sigue
    sumando cuatro.

    ``drop_voice`` saca una voz de todo lo que devuelve, que es lo que hace
    falta cuando esa voz la canta la melodía y se toca aparte.
    """
    out_chords = [list(chord) for chord in chords]
    out_durations = [float(d) for d in durations]
    while len(out_durations) < len(out_chords):
        out_durations.append(2.0)

    decorated: Dict[int, List[Tuple[int, Tuple[int, ...], float]]] = {}
    for entry in ornaments:
        slot, voice, note, share = (list(entry) + [0.5])[:4]
        # `note` puede ser una altura suelta o una figura entera, y de un
        # historial viejo llega siempre suelta: `passing.figure` normaliza
        # las dos formas.
        decorated.setdefault(int(slot), []).append(
            (int(voice), passing.figure(note), float(share)))

    notes: List[Tuple[int, float, float]] = []
    position = 0.0
    for index, chord in enumerate(out_chords):
        quarters = out_durations[index] if index < len(out_durations) else 2.0
        here = decorated.get(index)
        if chord and here:
            share = here[0][2]
            head = quarters * (1.0 - share)
            tail = quarters - head
            if head > 0.0 and tail > 0.0:
                moved = {voice: shape for voice, shape, _s in here if shape}
                # La cola se parte en tantos pedazos como notas tenga la
                # figura mas larga. Es la misma cola: el compas sigue
                # sumando lo que sumaba.
                steps = max((len(s) for s in moved.values()), default=1)
                span = tail / steps
                for voice, pitch in enumerate(chord):
                    if voice == drop_voice:
                        continue
                    shape = moved.get(voice)
                    if shape:
                        notes.append((pitch, position, head))
                        for step in range(steps):
                            note = shape[min(step, len(shape) - 1)]
                            notes.append((note, position + head + span * step,
                                          span))
                    else:
                        notes.append((pitch, position, quarters))
                # Sus voces ya están en `notes`; el slot ocupa su tiempo y
                # no suena por su cuenta, o sonaría todo dos veces.
                out_chords[index] = []
                position += quarters
                continue
        if drop_voice is not None:
            out_chords[index] = [p for v, p in enumerate(chord)
                                 if v != drop_voice]
        position += quarters

    return out_chords, out_durations, notes


def export_outcome(
    request: JobRequest,
    outcome: JobOutcome,
    directory: Optional[str] = None,
    formats: Sequence[str] = ("musicxml", "midi"),
    record_history: bool = True,
) -> List[str]:
    """
    Write every solution of a successful outcome to ``directory``.

    Files are named ``<title> - option N``. When ``directory`` is omitted the
    portable default (``<app folder>/output``) is used, honouring the rule
    that the program writes next to itself unless told otherwise.
    """
    if not outcome.succeeded or outcome.spec is None:
        return []

    target = directory or history.default_output_directory()
    os.makedirs(target, exist_ok=True)

    written: List[str] = []
    for index, solution in enumerate(outcome.result.solutions, start=1):
        stem = history.unique_basename(target, f"{request.title} - option {index}")
        # Cada opción con sus propios acordes (`solution_slots`). La cita,
        # para que la partitura muestre las inversiones --- seis compases de
        # «Am» a secas perderían el bajo del que se trata la cadencia ---. Y
        # en el Armonizador cada opción tiene su progresión: escrita con la
        # del primer intento, las notas ajenas a ese acorde se deletreaban
        # contra acordes ajenos y el archivo no coincidía con la grilla.
        own = solution_slots(outcome, index - 1)
        spec = (outcome.spec if own is outcome.spec.slots
                else replace(outcome.spec, slots=own))
        written.extend(export.write_solution(spec, solution, stem, formats))

    if record_history:
        settings = build_settings(request)
        # Only the manual mode has a request with typed chords and a metre on
        # it. The generative and harmonising requests carry neither, and
        # reading them off the request raised right after the files had been
        # written -- so the score was saved and the user was told nothing.
        # What was actually played is on the finished score either way.
        signature = getattr(request, "time_signature", None) or outcome.spec.time_signature
        entries = getattr(request, "entries", None) or []
        if entries:
            symbols = [entry.symbol for entry in entries]
            durations = [entry.duration_quarters for entry in entries]
        else:
            # Los de la opción ganadora: en el Armonizador cada opción tiene
            # su progresión, y `spec.slots` es la del primer intento, que
            # no siempre queda primera al ordenar por costo.
            shown = (solution_slots(outcome, 0) if outcome.result.solutions
                     else outcome.spec.slots)
            symbols = [slot.symbol for slot in shown]
            durations = [slot.duration_quarters for slot in shown]
        record = history.ProductionRecord.create(
            title=request.title,
            genre=request.genre_key,
            voice_keys=list(request.voice_keys),
            bar_count=len({s.bar_index for s in outcome.spec.slots}),
            time_signature=str(signature),
            chord_symbols=symbols,
            durations=durations,
            switches={
                "forbid_parallel_fifths": settings.profile.forbid_parallel_fifths,
                "forbid_parallel_octaves": settings.profile.forbid_parallel_octaves,
                "forbid_melodic_tritone": settings.profile.forbid_melodic_tritone,
                "forbid_harmonic_tritone": settings.profile.forbid_harmonic_tritone,
                "forbid_voice_crossing": settings.profile.forbid_voice_crossing,
                "allow_special_voicings": settings.profile.allow_special_voicings,
            },
            ga_settings={
                "population_size": request.ga_config.population_size,
                "generations": request.ga_config.generations,
                "elitism": request.ga_config.elitism,
                "tournament_size": request.ga_config.tournament_size,
                "mutation_rate": request.ga_config.mutation_rate,
            },
            solution_costs=[s.cost for s in outcome.result.solutions],
            files=written,
        )
        history.add_record(record)

    return written


def analysis_lines(outcome: JobOutcome, position: int
                   ) -> List[List[Tuple[Optional[int], float]]]:
    """
    Una opción del resultado escrita voz por voz, para el analizador.

    Es lo que llega al analizador cuando se le manda una opción sin pasar
    por un archivo, y tiene que ser exactamente lo que daría exportarla y
    volver a importarla. Por eso sigue paso a paso a `export.build_musicxml`:
    la línea escrita de la voz cuando la hay (la melodía del Armonizador), y
    si no, una nota por slot con el adorno partiendo sólo la voz que se
    mueve, en las mismas divisiones enteras. Lo vigila `TestSendToAnalyser`.

    Devuelve una lista por voz del motor (0 = la más grave) de pares (altura
    o None, duración en negras). Una nota ligada a través de la barra llega
    entera, como la lee el importador.
    """
    spec = outcome.spec
    own = solution_slots(outcome, position)
    if own is not spec.slots:
        spec = replace(spec, slots=own)
    solution = outcome.result.solutions[position]
    units = export.DIVISIONS_PER_QUARTER
    lines: List[List[Tuple[Optional[int], float]]] = [[] for _ in spec.voices]
    tied = [False] * len(spec.voices)
    sounding = 0
    for bar_slots in export.group_slots_into_bars(spec):
        for voice, out in enumerate(lines):
            line = spec.line_for(voice)
            written = (line.events_for(bar_slots[0].bar_index)
                       if line is not None else None)
            if written is not None:
                for event in written:
                    pitch, quarters = event[0], float(event[1])
                    if (pitch is not None and tied[voice] and out
                            and out[-1][0] == pitch):
                        out[-1] = (pitch, out[-1][1] + quarters)
                    else:
                        out.append((pitch, quarters))
                    tied[voice] = (pitch is not None and len(event) > 2
                                   and bool(event[2]))
                continue
            tied[voice] = False
            index = sounding
            for slot in bar_slots:
                quarters = slot.duration_quarters
                if slot.is_rest or index >= len(solution.slots):
                    out.append((None, quarters))
                    continue
                pitch = solution.slots[index][voice]
                notes = (solution.passing[index]
                         if index < len(solution.passing) else [])
                moved = passing.figure(notes[voice]
                                       if voice < len(notes) else None)
                share = (solution.passing_share[index]
                         if index < len(solution.passing_share)
                         else spec.passing_share)
                index += 1
                if not moved:
                    out.append((pitch, quarters))
                    continue
                head = quarters * (1.0 - share)
                out.append((pitch, head))
                whole = int(round(quarters * units))
                held = int(round(head * units))
                for step, note in enumerate(moved):
                    first = held + (whole - held) * step // len(moved)
                    last = held + (whole - held) * (step + 1) // len(moved)
                    out.append((note, (last - first) / units))
        sounding += sum(1 for slot in bar_slots if not slot.is_rest)
    return lines


def default_locked_voicing(
    chord_symbol: str,
    voice_keys: Sequence[str],
    custom_pitch_classes: Optional[Sequence[int]] = None,
) -> List[int]:
    """
    Suggest a starting voicing for the padlock, lowest voice first.

    Stacks the chord tones in order (root, third, fifth, seventh, tensions)
    and puts each in the lowest octave its voice can reach above the voice
    below it, which is the plain textbook close-position voicing the user
    would otherwise have to build by hand before locking it.
    """
    from .theory import build_voice_parts, make_custom_chord, parse_chord

    chord = (
        make_custom_chord(list(custom_pitch_classes), chord_symbol)
        if custom_pitch_classes
        else parse_chord(chord_symbol)
    )
    voices = build_voice_parts(list(voice_keys))
    plan = build_voicing_plan(chord, len(voices))

    # Built from the BASS up. Anchoring the bass low and stacking above it is
    # what produces the textbook close-position voicing; packing each voice
    # against the one above instead squeezes the whole chord into the top of
    # the lower voices' ranges (a C major triad came out as C4-C4-E4-G4, with
    # the bass sitting on its own ceiling).
    count = len(voices)
    pitches: List[int] = [0] * count

    bass_low, bass_high = voices[0].low, voices[0].high
    bass_candidates = voices[0].candidates_for_pitch_class(
        chord.pitch_class_of(plan.degrees[0])
    ) or [bass_low]
    bass_target = bass_low + (bass_high - bass_low) // 3
    pitches[0] = min(bass_candidates, key=lambda m: abs(m - bass_target))

    for index in range(1, count):
        pc = chord.pitch_class_of(plan.degrees[index])
        candidates = voices[index].candidates_for_pitch_class(pc)
        if not candidates:
            candidates = [voices[index].low]
        # Lowest note strictly above the voice below, so nothing crosses and
        # the chord stays as compact as the ranges allow.
        above = [m for m in candidates if m > pitches[index - 1]]
        if not above:
            above = [m for m in candidates if m >= pitches[index - 1]] or candidates
        pitches[index] = min(above)

    # Close any hole left between adjacent upper voices. A voice whose pitch
    # class only fits high in its range (a seventh that can only be sung as
    # B4 by a soprano) strands itself above the rest; raising the voice below
    # it is the cheap repair. The bass is exempt: a wide gap above the bass
    # is idiomatic, a hole between two upper voices is not.
    for index in range(count - 2, 0, -1):
        gap = pitches[index + 1] - pitches[index]
        if gap <= 12:
            continue
        pc = chord.pitch_class_of(plan.degrees[index])
        candidates = voices[index].candidates_for_pitch_class(pc)
        reachable = [
            m for m in candidates
            if pitches[index - 1] <= m <= pitches[index + 1]
        ]
        if reachable:
            pitches[index] = max(reachable)

    return pitches


# ---------------------------------------------------------------------------
# Random generator
# ---------------------------------------------------------------------------

@dataclass
class GenerativeRequest:
    """A request for the random generator, where the search picks the chords."""

    genre_key: str
    voice_keys: List[str]
    tonic: str = "C"
    mode_key: str = "major"
    borrowed: List[str] = field(default_factory=list)
    slot_count: int = 8
    durations: List[float] = field(default_factory=list)
    bar_indices: List[int] = field(default_factory=list)
    time_signature: "export.TimeSignature" = field(
        default_factory=lambda: export.TimeSignature(4, 4)
    )
    with_sevenths: bool = False
    title: str = "ChordWeaver"
    tempo_bpm: int = 90
    switch_overrides: Dict[str, Any] = field(default_factory=dict)
    range_overrides: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    ga_config: GAConfig = field(default_factory=GAConfig)
    solutions_wanted: int = 3
    #: Which voices may take passing tones, and how they are scored.
    passing_rules: Optional[passing.PassingRules] = None
    #: Where the piece may travel. Built from the genre when left as None.
    modulation: Optional[harmony.ModulationSettings] = None
    #: Harmony judgement. Built from the genre when left as None.
    harmony_weights: Optional[harmony.HarmonyWeights] = None
    #: Endpoints: which chord opens and closes, and whether that is a hard
    #: requirement or merely weighted.
    start_roman: Optional[str] = None
    end_roman: Optional[str] = None
    endpoints_required: bool = False
    #: Doubles the chance of a set-piece cadence turning up.
    raise_odds: bool = False
    #: Voice carrying the vox principalis, for organum.
    principalis_voice: Optional[int] = None


def _set_piece_slots(piece, tonic_pc, request, settings, durations, bars):
    """Slots carrying the quotation's own chords, inversions included."""
    voice_count = len(request.voice_keys)
    out = []
    for index, option in enumerate(harmony.set_piece_options(piece, tonic_pc)):
        requirement = build_requirement(
            option.chord, voice_count, None,
            allow_special_voicings=settings.profile.allow_special_voicings,
            special_fills=settings.profile.special_voicing_fills,
            colour_appetite=0.0,
        )
        if piece.bass_line:
            requirement.required_pitch_classes = [option.chord.root_pc]
        if piece.roots_in_bass:
            requirement.bass_pitch_class = option.chord.root_pc
        out.append(ChordSlot(
            requirement=requirement,
            duration_quarters=durations[index] if index < len(durations) else 2.0,
            bar_index=bars[index] if index < len(bars) else index // 2,
            options=[SlotOption(requirement=requirement, harmony=option)],
        ))
    return out


def _voice_set_piece(piece, tonic_pc, request, settings, durations, bars, mode):
    """
    Work out how to sing a fixed progression.

    The chords are already decided, so the search has nothing to choose but
    the register and the order of the voices -- each slot is given exactly
    one option, which is the same mechanism the padlock uses.
    """
    voice_count = len(request.voice_keys)
    options = harmony.set_piece_options(piece, tonic_pc)
    slots = []
    for index, option in enumerate(options):
        requirement = build_requirement(
            option.chord, voice_count, None,
            allow_special_voicings=settings.profile.allow_special_voicings,
            special_fills=settings.profile.special_voicing_fills,
            colour_appetite=0.0,
        )
        # A quotation is a fixed shape, and pinning the bass leaves the other
        # voices little room: with three of them the bass plus two upper
        # parts cannot always cover a triad. The cadence is what the user
        # asked for, so coverage yields to it rather than the other way round.
        if piece.bass_line:
            requirement.required_pitch_classes = [option.chord.root_pc]
        # An inversion pins the bass: that walking line IS the cadence, so it
        # is fixed rather than left for the search to rediscover.
        if option.chord.bass_pc is not None:
            requirement.bass_pitch_class = option.chord.bass_pc
        elif piece.roots_in_bass:
            requirement.bass_pitch_class = option.chord.root_pc
        slots.append(ChordSlot(
            requirement=requirement,
            duration_quarters=durations[index] if index < len(durations) else 2.0,
            bar_index=bars[index] if index < len(bars) else index // 2,
            options=[SlotOption(requirement=requirement, harmony=option)],
        ))

    # A descending bass has to actually descend: pinning the pitch CLASS
    # leaves the octave free, and the search happily jumped up an octave
    # between steps, which destroys the one thing the cadence is about.
    if piece.bass_line:
        bass_part = settings.voices[0]
        start = None
        for candidate in range(bass_part.high, bass_part.low - 1, -1):
            if candidate % 12 == (tonic_pc + piece.bass_line[0]) % 12:
                start = candidate
                break
        if start is not None:
            previous = start
            for index, offset in enumerate(piece.bass_line):
                target_pc = (tonic_pc + offset) % 12
                # Take the nearest pitch at or below the last one, so the
                # line only ever steps down until the cadence turns around.
                pitch = previous
                while pitch % 12 != target_pc:
                    pitch -= 1
                if index and pitch < bass_part.low:
                    pitch += 12
                slots[index].locked_bass = pitch
                previous = pitch

    quoted = run(slots, settings, request.ga_config, solutions_wanted=1,
                 harmony_weights=None, tonic_pc=tonic_pc,
                 passing_rules=request.passing_rules,
                 scale_pcs=mode.pitch_classes(tonic_pc))
    return quoted.solutions[0] if quoted.solutions else None


def generate_random(
    request: GenerativeRequest,
    progress: Optional[Callable[[int, float], None]] = None,
) -> JobOutcome:
    """
    Run the generator: the search chooses the chords *and* voices them.

    A mandatory endpoint is handled by giving that slot a single chord to
    choose from, rather than by penalising the wrong choice afterwards. That
    is exact, it costs nothing, and it keeps the search from spending its
    budget rediscovering a constraint we already know.
    """
    tonic_pc = parse_pitch_class(request.tonic)
    mode = harmony.MODES.get(request.mode_key)
    if mode is None:
        return JobOutcome(result=GAResult([], 0, 0, 0), spec=None,
                          errors=[f"Modo desconocido: {request.mode_key}"])

    # Jazz applies the ii-V approach to any degree, so the dominants those
    # pairs need are always available in that style. The baroque styles get
    # exactly one of them, the V of the V: it belongs to common practice,
    # while the rest of the chain is a jazz habit. Cuánto aparece y con qué
    # obligación de resolver lo decide la gramática, no esta lista.
    applied = {
        "jazz": None,                                   # todos los grados
        "classical": (harmony.DEGREE_DOMINANT,),
        "chorale": (harmony.DEGREE_DOMINANT,),
    }
    pool = harmony.build_chord_pool(
        tonic_pc, mode, request.borrowed, request.with_sevenths,
        secondary=(request.genre_key in applied),
        secondary_degrees=applied.get(request.genre_key),
    )
    modulation = request.modulation
    if modulation is not None and modulation.enabled:
        if not modulation.targets:
            defaults = harmony.GENRE_MODULATION.get(request.genre_key)
            if defaults is not None:
                modulation = replace(modulation, targets=defaults.targets)
        # Los destinos se recortan acá, una sola vez, y no en cada lugar que
        # los mira: el plan de viaje del AG sortea sobre `targets`, así que un
        # destino que el pool no tiene ---uno modal cuando el usuario sólo
        # pidió tonalidades, o el modo en el que la pieza ya está--- se
        # llevaba una de las tres soluciones y no viajaba a ninguna parte.
        modulation = replace(modulation, targets=harmony.available_targets(
            modulation, request.mode_key))
        if not modulation.targets:
            modulation = None
        else:
            pool = pool + harmony.modulation_pool(
                tonic_pc, modulation, request.with_sevenths,
                home_mode_key=request.mode_key,
            )
    if not pool:
        return JobOutcome(result=GAResult([], 0, 0, 0), spec=None,
                          errors=["No hay acordes disponibles en esta tonalidad."])

    settings = build_settings(JobRequest(
        genre_key=request.genre_key,
        voice_keys=request.voice_keys,
        entries=[],
        switch_overrides=request.switch_overrides,
        range_overrides=request.range_overrides,
        # Carried across by hand: the stand-in request is built field by
        # field, so anything left out here is silently dropped, and organum
        # was reaching the manual mode and no other.
        principalis_voice=request.principalis_voice,
    ))
    voice_count = len(request.voice_keys)
    special = settings.profile.special_voicing_fills

    # Un solo sorteador para todo el pool, y no uno por acorde. Estaba
    # sembrado de nuevo dentro de la comprensión, así que los treinta
    # acordes sacaban exactamente el mismo número: o todos tomaban color o
    # ninguno, que es lo contrario de lo que un dial de color debería
    # hacer. Sigue saliendo del seed, así que la corrida sigue siendo
    # reproducible.
    colour_picker = random.Random(request.ga_config.random_seed)

    def options_for(pool_subset):
        return [
            SlotOption(
                requirement=build_requirement(
                    option.chord, voice_count, None,
                    allow_special_voicings=settings.profile.allow_special_voicings,
                    special_fills=special,
                    allow_major_sixth_on_minor=(request.genre_key == "jazz"),
                    colour_appetite=min(
                        1.0, abs(settings.profile.weight_colour_tone) / 30.0),
                    rng=colour_picker,
                    # A cuatro voces y con séptimas, ningún acorde deja una
                    # voz libre y el dial de color no tenía por dónde
                    # entrar: la única puerta es cambiar la séptima por un
                    # color, y sólo donde la séptima es color y no función.
                    may_swap_seventh=not harmony.seventh_is_structural(option),
                ),
                harmony=option,
            )
            for option in pool_subset
        ]

    all_options = options_for(pool)
    durations = request.durations or [2.0] * request.slot_count
    bars = request.bar_indices or [i // 2 for i in range(request.slot_count)]

    slots: List[ChordSlot] = []
    for index in range(request.slot_count):
        subset = all_options
        if request.endpoints_required:
            wanted = (request.start_roman if index == 0
                      else request.end_roman if index == request.slot_count - 1
                      else None)
            if wanted:
                pinned = [o for o in all_options if o.harmony.roman == wanted]
                if pinned:
                    subset = pinned
        slots.append(ChordSlot(
            requirement=subset[0].requirement,
            duration_quarters=durations[index],
            bar_index=bars[index],
            options=subset,
        ))

    # A quotation may stand in for the generated progression. It skips the
    # harmonic search entirely -- the chords are already decided -- and the
    # engine only works out how to sing them. It can only ever be the first
    # of the three answers, so the generated ones are still there underneath.
    set_piece_info: Optional[SetPieceInfo] = None
    rng = random.Random(request.ga_config.random_seed)
    equal = len(set(durations)) <= 1
    candidates = harmony.set_piece_for(
        request.genre_key, request.mode_key, request.slot_count, equal
    )
    chance = (harmony.SET_PIECE_CHANCE_HIGH if getattr(request, "raise_odds", False)
              else harmony.SET_PIECE_CHANCE)
    if candidates and rng.random() < chance:
        set_piece_info = SetPieceInfo(
            label=rng.choice(candidates).label,
            description=next(p.description for p in candidates
                             if p.label == candidates[0].label),
        )

    weights = request.harmony_weights or harmony.genre_harmony_weights(request.genre_key)
    weights.modulation = modulation if (modulation and modulation.enabled) else None
    if not request.endpoints_required:
        weights.start_roman = request.start_roman
        weights.end_roman = request.end_roman
    else:
        weights.start_roman = weights.end_roman = None

    result = run(slots, settings, request.ga_config, progress=progress,
                 solutions_wanted=request.solutions_wanted,
                 harmony_weights=weights, tonic_pc=tonic_pc,
                 passing_rules=request.passing_rules,
                 scale_pcs=mode.pitch_classes(tonic_pc),
                 # Mientras la pieza está de viaje, sus adornos se eligen
                 # con la escala del lugar donde está.
                 area_scales=harmony.modulation_scales(
                     tonic_pc, modulation, home_mode_key=request.mode_key))

    # Cuál eligió la búsqueda, antes de que la cita se meta adelante. Los
    # `slots` de abajo se sellan con esto y no con `solutions[0]`, que puede
    # ser la cita: la cita trae sus propios slots ---uno por acorde y con una
    # sola opción cada uno--- así que sus `choices` son todos cero, y
    # aplicados sobre los slots del generador ---que tienen decenas de
    # opciones--- sellaban el acorde número cero en todas partes. El
    # resultado era una progresión de ocho acordes iguales pegada al pie de
    # la partitura citada, que es lo que veía el historial.
    generated = result.solutions[0] if result.solutions else None

    if set_piece_info is not None and result.solutions:
        piece = next(p for p in harmony.SET_PIECES.values()
                     if p.label == set_piece_info.label)
        quoted = _voice_set_piece(piece, tonic_pc, request, settings,
                                  durations, bars, mode)
        if quoted is not None:
            # The quotation takes first place and the generated answers slide
            # down, so the user still gets two of their own alongside it.
            result.solutions = [quoted] + result.solutions[:
                                                           request.solutions_wanted - 1]
            # The labels are carried separately so the other two solutions
            # keep their own chords on screen -- overwriting the shared slots
            # put the quotation's symbols over everyone's notes.
            quoted_options = harmony.set_piece_options(piece, tonic_pc)
            set_piece_info.symbols = [o.label for o in quoted_options]
            set_piece_info.romans = [o.roman for o in quoted_options]
            # The score, though, is written from the slots, and it has to
            # carry the inversions: exporting six bars of plain "Am" loses
            # the bass line the cadence is entirely about.
            set_piece_info.slots = _set_piece_slots(
                piece, tonic_pc, request, settings, durations, bars
            )
        else:
            set_piece_info = None

    # The score has to show the chords the winner actually chose.
    if generated is not None:
        for index, slot in enumerate(slots):
            choice = (generated.choices[index]
                      if index < len(generated.choices) else 0)
            slot.requirement = slot.options[min(choice, len(slot.options) - 1)].requirement

    spec = export.ScoreSpec(
        slots=slots, voices=settings.voices,
        time_signature=request.time_signature,
        title=request.title, tempo_bpm=request.tempo_bpm,
        key_hint=harmony.key_fifths(tonic_pc, mode),
    )
    outcome = JobOutcome(result=result, spec=spec, set_piece=set_piece_info)
    if not result.solutions:
        outcome.errors.append(result.message or "No se encontró ninguna solución válida.")
    return outcome


def apply_flourishes(
    outcome: "JobOutcome",
    genre_key: str,
    tonic_pc: int = 0,
    locked: Optional[Sequence[bool]] = None,
    raise_odds: bool = False,
) -> None:
    """
    Decorate and annotate the winning solution, after the search.

    Runs on the best chromosome only. The sixth actually rewrites notes; the
    rest is recognition, labelling what the search already chose so the
    interface can point it out.
    """
    if not outcome.succeeded or outcome.spec is None:
        return
    # Una sola vez por resultado. El Armonizador la corre al terminar la
    # búsqueda ---con la tónica de la melodía, que sólo él conoce--- y la
    # pantalla de resultados la volvía a correr encima. La sexta reescribe
    # notas de la solución, así que la segunda pasada podía escribir otra
    # sexta sobre la primera, y como su resultado reemplazaba al anterior,
    # la primera quedaba escrita en la partitura sin ninguna marca.
    if getattr(outcome, "flourishes", None) is not None:
        return

    voice_count = len(outcome.spec.voices)
    # La sexta reescribe `best.slots`, que es de la búsqueda: los silencios
    # no entran y **no está alineado con `spec.slots`**. Así que los
    # candados y las voces fijas se cuentan sobre los lugares que suenan, y
    # lo que vuelve se traduce a columnas de la partitura. Contados sobre
    # `spec.slots`, un silencio corría todos los candados un lugar y la
    # sexta reescribía un acorde con candado ---y lo rotulaba con el nombre
    # del vecino---. Las voces fijas son la melodía del armonizador: la
    # sexta la cambiaba en la solución y la pantalla mostraba otra nota que
    # la que el usuario escribió y que se exportaba.
    own = solution_slots(outcome, 0)
    sounding = [index for index, slot in enumerate(own) if not slot.is_rest]
    locked = list(locked or [own[index].is_locked for index in sounding])
    frozen = [set(getattr(own[index], "pinned_voices", None) or ())
              for index in sounding]
    result = flourish.FlourishResult()

    def harmony_of(solution, slots):
        """
        Lo que eligió una solución en cada lugar que suena, en el orden de
        la búsqueda: las columnas de la partitura que suenan, la opción
        armónica de cada una ---que trae la cifra romana--- y el acorde en
        clases de altura.

        Alineado con ``solution.slots``, que saltea los silencios: armado
        sobre todos los slots de la partitura, un silencio corría cada
        acorde un lugar y el 6/4 se comparaba con el acorde de al lado. Y
        con los slots **de esa solución**: en el Armonizador cada opción
        tiene su progresión, y las otras dos se rotulaban con la del primer
        intento.

        El Organizador no tiene opciones armónicas ---el usuario escribió
        los cifrados--- así que ahí la opción es None y todo lo que se
        reconoce por grado queda afuera. El contexto, en cambio, existe
        siempre, y es lo que le alcanza al 6/4 para reconocerse en los tres
        modos.
        """
        columns = [index for index, slot in enumerate(slots)
                   if not slot.is_rest]
        options, contexts = [], []
        for position, index in enumerate(columns):
            slot = slots[index]
            choice = (solution.choices[position]
                      if position < len(solution.choices) else 0)
            if slot.options:
                picked = slot.options[min(choice, len(slot.options) - 1)]
                options.append(picked.harmony)
                requirement = picked.requirement
            else:
                options.append(None)
                requirement = slot.requirement
            contexts.append(ChordContext.from_chord(requirement.chord))
        return columns, options, contexts

    best = outcome.result.solutions[0]

    # The sixth: common practice only, and only when the dice say so.
    rng = random.Random()
    if genre_key in ("classical", "chorale") and rng.random() < flourish.SIXTH_CHANCE:
        melody = getattr(outcome, "melody", None)
        applied = flourish.apply_sixth(
            best.slots, locked, voice_count, rng, frozen=frozen,
            melody_voice=getattr(melody, "melody_voice", None),
            melody_edges=(getattr(outcome, "melody_edges", None) or {}).get(0))
        if applied is not None:
            sixth, forced, _voice = applied
            # En columnas de la partitura, que es como las cuenta la grilla.
            result.sixth_slot = sounding[sixth] if sixth < len(sounding) else sixth
            result.forced_slot = (sounding[forced] if forced < len(sounding)
                                  else forced)
            # The chord is not the triad it was, so its label has to change.
            slot = own[result.sixth_slot]
            result.sixth_symbol = flourish.sixth_symbol(
                slot.requirement.chord.symbol)
            result.marks.append(flourish.Mark(
                "bach_sixth", "Sexta en lugar de quinta",
                "Las dos voces se mueven en paralelo, pero una quinta se "
                "escribe como sexta: el recurso con que Bach esquiva las "
                "quintas paralelas sin reordenar las voces.",
                (result.sixth_slot, result.forced_slot),
            ))

    # Every solution is examined, not only the winner: the other two are
    # real answers the user may pick, and leaving them unmarked made the
    # highlighting look arbitrary.
    for position, solution in enumerate(outcome.result.solutions):
        columns, options, contexts = harmony_of(
            solution, solution_slots(outcome, position))
        found = flourish.find_marks(
            options, solution.slots, genre_key, tonic_pc, contexts,
        )
        # Las marcas salen en la numeración de la búsqueda y la grilla las
        # busca por columna de la partitura, igual que la sexta de arriba:
        # con un silencio adelante, el 6/4 se pintaba sobre el acorde de al
        # lado.
        found = [replace(mark, slots=tuple(
                     columns[index] if index < len(columns) else index
                     for index in mark.slots))
                 for mark in found]
        if position == 0:
            # The sixth was applied to this solution, so its mark belongs
            # here too -- it was going into `marks` alone, which the display
            # no longer reads.
            found = list(result.marks) + found
            result.marks = list(found)
        result.by_solution[position] = found
    outcome.flourishes = result


# ---------------------------------------------------------------------------
# Harmonisation
# ---------------------------------------------------------------------------

@dataclass
class HarmoniseRequest:
    """A melody to harmonise, and how."""

    genre_key: str
    voice_keys: List[str]
    melody: harmonize.Melody
    #: Which of `voice_keys` the user wrote. The rest are generated.
    melody_voice: int = 0
    title: str = "ChordWeaver"
    tempo_bpm: int = 90
    allow_colour: bool = False
    colour_weight: float = 0.0
    allow_borrowed: bool = True
    with_sevenths: bool = False
    switch_overrides: Dict[str, Any] = field(default_factory=dict)
    range_overrides: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    ga_config: GAConfig = field(default_factory=GAConfig)
    solutions_wanted: int = 3
    #: Chords the user pinned, keyed by strong-beat index.
    forced_chords: Dict[int, str] = field(default_factory=dict)


def harmonise_melody(
    request: HarmoniseRequest,
    progress: Optional[Callable[[int, float], None]] = None,
) -> JobOutcome:
    """
    Work out an accompaniment for a melody the user supplied.

    The chords are chosen first, by what the melody needs; the search then
    only decides how to sing the remaining voices. Three answers come back,
    each a different arrangement of the same progression -- the harmony is
    driven by the melody, so varying it would mean answering a different
    question.
    """
    melody = request.melody
    if not melody.notes:
        return JobOutcome(result=GAResult([], 0, 0, 0), spec=None,
                          errors=["La melodía está vacía."])

    # The melody is given, so the voice carrying it stretches to hold it.
    # Refusing a line because it climbs past a textbook range would be
    # rejecting the one thing the user actually wrote.
    ranges = dict(request.range_overrides)
    sung = [note.pitch for note in melody.notes]
    if sung:
        from .theory import VOICE_CATALOG
        voice_key = request.voice_keys[
            min(request.melody_voice, len(request.voice_keys) - 1)]
        part = VOICE_CATALOG[voice_key]
        low, high = ranges.get(request.melody_voice, (part.low, part.high))
        ranges[request.melody_voice] = (min(low, min(sung)),
                                        max(high, max(sung)))

    settings = build_settings(JobRequest(
        genre_key=request.genre_key,
        voice_keys=request.voice_keys,
        entries=[],
        switch_overrides=request.switch_overrides,
        range_overrides=ranges,
    ))
    # This is the only mode with a line the user wrote, and telling the
    # evaluator which voice carries it is what turns the melody rules on.
    settings.melody_voice = request.melody_voice
    # In this mode the vox principalis is not a choice: it is the line the
    # user wrote. The organalis is the voice under it, as everywhere else.
    if request.melody_voice > 0:
        settings.principalis_voice = request.melody_voice

    rules = harmonize.HarmonisationSettings(
        genre_key=request.genre_key,
        allow_colour=request.allow_colour,
        allow_borrowed=request.allow_borrowed,
        with_sevenths=request.with_sevenths,
    )
    picker = random.Random(request.ga_config.random_seed)

    # El progreso se reparte entre las tres busquedas, no solo la primera.
    #
    # Este modo hace tres corridas: la principal y una por cada alternativa.
    # Solo la primera reportaba, asi que la barra avanzaba, se plantaba
    # donde la primera hubiera terminado --- que con el corte por
    # estancamiento es alrededor de un quinto del camino --- y ahi se
    # quedaba cuatro o cinco segundos mientras las otras dos corrian en
    # silencio. Medido con 32 notas: 9,3 s con barra y 5,0 s sin ella. Una
    # barra que se queda quieta la mitad del tiempo no se lee como una
    # espera sino como un programa colgado.
    total_generations = max(1, request.ga_config.generations)

    def phase(start: float, span: float, generations: int):
        """Un reportero que mapea una corrida a su tramo de la barra."""
        if progress is None:
            return None

        def report(generation: int, best: float) -> None:
            done = start + span * min(1.0, generation / max(1, generations))
            progress(int(done * total_generations), best)

        return report

    #: Cuanto de la barra se lleva la busqueda principal. Las alternativas
    #: corren con una poblacion y una cantidad de generaciones bastante
    #: menores, asi que reparten el resto en partes iguales.
    MAIN_SHARE = 0.6

    # Harmonised more than once, so the three answers are three different
    # progressions rather than three voicings of one. Running it a single
    # time made every option carry identical chords, which is not a choice
    # at all -- the whole point is to offer ways of hearing the same tune.
    attempts, seen = [], set()
    for _ in range(80):
        candidate = harmonize.harmonise(melody, rules, picker)
        if not candidate:
            continue
        signature = tuple(option.roman for _spot, option in candidate)
        if signature in seen:
            continue
        seen.add(signature)
        attempts.append(candidate)
        if len(attempts) >= request.solutions_wanted:
            break

    # A short melody offers few chords that can hold it, so demanding three
    # entirely different progressions can come up short. Rather than return
    # one answer, the remainder are voiced from the progressions already
    # found: same chords, genuinely different arrangements.
    while attempts and len(attempts) < request.solutions_wanted:
        attempts.append(attempts[len(attempts) % max(1, len(seen))])
    if not attempts:
        attempts = [harmonize.harmonise(melody, rules, picker)]
    chosen = attempts[0]
    if not chosen:
        return JobOutcome(result=GAResult([], 0, 0, 0), spec=None,
                          errors=["No se pudo armonizar esta melodía."])

    voice_count = len(request.voice_keys)
    appetite = min(1.0, request.colour_weight / 30.0)
    slots: List[ChordSlot] = []
    for index, (spot, option) in enumerate(chosen):
        if index in request.forced_chords:
            spot.forced_roman = request.forced_chords[index]
        requirement = build_requirement(
            option.chord, voice_count, None,
            allow_special_voicings=settings.profile.allow_special_voicings,
            special_fills=settings.profile.special_voicing_fills,
            colour_appetite=appetite, rng=picker,
        )
        slot = ChordSlot(
            requirement=requirement,
            duration_quarters=spot.duration_quarters,
            bar_index=spot.bar_index,
            options=[SlotOption(requirement=requirement, harmony=option)],
        )
        # The given note is pinned, so the search arranges around it without
        # ever altering what the user wrote.
        if spot.note is not None:
            slot.pinned_voices = {request.melody_voice: spot.note.pitch}
            _make_room_for_melody(requirement, spot.note.pitch, voice_count)
        if index == len(chosen) - 1:
            _close_on_the_root(requirement, slot.pinned_voices, voice_count)
        slots.append(slot)

    bar = melody.bar(0)

    def voice(progression, variant: int = 0):
        """
        Arrange one progression, with the melody pinned in place.

        The variant number becomes the search seed, so two options built on
        the same chords still come back voiced differently -- which is what
        makes a short melody, where few progressions fit, still offer a
        real choice.
        """
        built = []
        for position, (spot, option) in enumerate(progression):
            requirement = build_requirement(
                option.chord, voice_count, None,
                allow_special_voicings=settings.profile.allow_special_voicings,
                special_fills=settings.profile.special_voicing_fills,
                colour_appetite=appetite, rng=picker,
            )
            slot = ChordSlot(
                requirement=requirement,
                duration_quarters=spot.duration_quarters,
                bar_index=spot.bar_index,
                options=[SlotOption(requirement=requirement, harmony=option)],
            )
            if spot.note is not None:
                slot.pinned_voices = {request.melody_voice: spot.note.pitch}
                _make_room_for_melody(requirement, spot.note.pitch,
                                      voice_count)
            if position == len(progression) - 1:
                _close_on_the_root(requirement, slot.pinned_voices,
                                   voice_count)
            built.append(slot)
        # The alternatives ask for a single arrangement each, and the chords
        # are already decided, so they need a fraction of the effort the main
        # search does. Running all three at full size made the mode four
        # times slower than the others for no gain.
        base_seed = request.ga_config.random_seed
        lighter = replace(
            request.ga_config,
            population_size=max(40, request.ga_config.population_size // 3),
            generations=max(20, request.ga_config.generations // 4),
            random_seed=(None if base_seed is None
                         else base_seed + 1000 * (variant + 1)),
        )
        share = (1.0 - MAIN_SHARE) / max(1, request.solutions_wanted - 1)
        edges = _melody_edges(melody, progression)
        outcome = run(built, replace(settings, melody_edges=edges),
                      lighter, solutions_wanted=1,
                      tonic_pc=bar.tonic,
                      progress=phase(MAIN_SHARE + share * variant, share,
                                     lighter.generations))
        return built, edges, (outcome.solutions[0] if outcome.solutions
                              else None)

    edges = _melody_edges(melody, chosen)
    result = run(slots, replace(settings, melody_edges=edges),
                 request.ga_config,
                 progress=phase(0.0, MAIN_SHARE, request.ga_config.generations),
                 solutions_wanted=1, tonic_pc=bar.tonic)

    # The alternatives are voiced separately, each keeping the slots it was
    # written for.
    alternates = []
    for variant, progression in enumerate(attempts[1:]):
        built, heard, solution = voice(progression, variant)
        if solution is not None:
            alternates.append((built, heard, solution))

    # Y recién acá se ordenan las tres por costo, todas juntas.
    #
    # Se appendeaban en el orden en que las progresiones habían aparecido, que
    # no tiene nada que ver con cuál quedó mejor: la opción 1 podía ser la
    # peor de las tres. Medido, salía desordenado dos de cada tres veces
    # ---[993, 920, 889]--- debajo de un cartel que dice, textual, que están
    # ordenadas por costo.
    #
    # Cada solución viaja pegada a los slots con los que se escribió, porque
    # cada una tiene su propia progresión: ordenar las soluciones sin mover
    # los slots pondría los acordes de una arriba de las notas de otra.
    ranked = [(result.solutions[0], slots, edges)] if result.solutions else []
    ranked += [(solution, built, heard) for built, heard, solution in alternates]
    ranked.sort(key=lambda entry: entry[0].cost)
    result.solutions = [solution for solution, _built, _heard in ranked]

    spec = export.ScoreSpec(
        slots=slots, voices=settings.voices,
        time_signature=export.TimeSignature(bar.beats, bar.beat_type),
        title=request.title, tempo_bpm=request.tempo_bpm,
        key_hint=harmony.key_fifths(bar.tonic, bar.mode),
        # Cada compás con su tónica: la melodía la lleva en cada `MelodyBar`,
        # y con la del primero para toda la pieza las notas ajenas al acorde
        # de un tramo en otra tonalidad salían con la armadura de casa.
        bar_key_hints={index: harmony.key_fifths(each.tonic, each.mode)
                       for index, each in enumerate(melody.bars)},
        # The score shows the line as written, not as sampled. Only this mode
        # sets it, so the other two export exactly as they always have.
        melody=export.MelodyLine(
            voice_index=request.melody_voice,
            bars={index: harmonize.bar_events(melody, index)
                  for index in range(len(melody.bars))},
        ),
    )
    outcome = JobOutcome(result=result, spec=spec, melody=melody)
    # Each option carries the chords it was actually built from. Se anota
    # también la que quedó primera --- antes se daba por hecho que era la de
    # `spec.slots` y se la dejaba fuera del diccionario, pero después de
    # ordenar por costo cualquiera de las tres puede encabezar.
    outcome.alternate_slots = {position: built
                               for position, (_s, built, _h) in enumerate(ranked)}
    outcome.melody_edges = {position: heard
                            for position, (_s, _b, heard) in enumerate(ranked)}
    if not result.solutions:
        outcome.errors.append(result.message or "No se encontró una solución.")
    else:
        apply_flourishes(outcome, request.genre_key, bar.tonic)
    return outcome


def _melody_edges(melody, progression
                  ) -> List[Tuple[Optional[int], Optional[int]]]:
    """
    Lo que la melodía canta al empezar y al terminar cada lugar de acorde.

    Un par ``(entrada, salida)`` por lugar, ``None`` donde coincide con la
    nota que el lugar fija (`RunSettings.melody_edges`). La melodía sigue
    moviéndose adentro del acorde mientras las otras voces sostienen, y al
    cambiar de acorde lo que se oye es su última nota: es contra esa que el
    analizador mide las paralelas.
    """
    edges: List[Tuple[Optional[int], Optional[int]]] = []
    for spot, _option in progression:
        pinned = spot.note.pitch if spot.note is not None else None
        start = spot.offset_quarters
        end = start + spot.duration_quarters
        inside = sorted(
            (note for note in melody.notes
             if note.bar_index == spot.bar_index and not note.is_rest
             and note.pitch is not None
             and note.offset_quarters < end - 1e-6
             and note.offset_quarters + note.duration_quarters > start + 1e-6),
            key=lambda note: note.offset_quarters)
        if pinned is None or not inside:
            edges.append((None, None))
            continue
        first, last = inside[0].pitch, inside[-1].pitch
        edges.append((first if first != pinned else None,
                      last if last != pinned else None))
    return edges


def _close_on_the_root(requirement, pinned: Dict[int, int],
                       voice_count: int) -> None:
    """
    El último acorde, con la fundamental en el bajo.

    Con tres voces y la melodía terminando en la tónica, las otras dos tenían
    que poner la tercera y la quinta, así que el bajo nunca podía ser la
    fundamental: casi toda armonización terminaba en primera o en segunda
    inversión. A tres voces la cadencia de manual es otra: fundamental en el
    bajo, la tercera en el medio y la quinta afuera. Eso es lo que se pide
    acá, y la quinta se suelta sólo cuando no queda voz para ella.

    No toca un acorde con séptima ---ahí la regla de posición fundamental del
    evaluador ya decide, y a tres voces una séptima no entra completa---, ni
    uno con el bajo ya fijado, ni el caso en que la melodía es el bajo.
    """
    from .theory import ROLE_FIFTH, ROLE_SEVENTH
    chord = requirement.chord
    if 0 in pinned or chord.bass_pc is not None:
        return
    if requirement.bass_pitch_class is not None:
        return
    if any(tone.role == ROLE_SEVENTH for tone in chord.tones):
        return
    root = chord.root_pc
    if root not in requirement.allowed_pitch_classes:
        return
    requirement.bass_pitch_class = root
    covered = {root} | {pitch % 12 for pitch in pinned.values()}
    free = voice_count - 1 - len(pinned)
    missing = [pc for pc in requirement.required_pitch_classes
               if pc not in covered]
    if len(missing) <= free:
        return
    fifths = {(root + tone.semitones) % 12 for tone in chord.tones
              if tone.role == ROLE_FIFTH}
    requirement.required_pitch_classes = [
        pc for pc in requirement.required_pitch_classes
        if pc not in fifths or pc in covered]


def _make_room_for_melody(requirement, pitch: int, voice_count: int) -> None:
    """
    Let the chord give way to the note the melody actually has.

    One voice is spoken for, so only the rest are free to cover the chord.
    When the melody sits on a colour tone -- a ninth, say -- that note covers
    none of the chord's own, and the remaining voices cannot reach all of
    them. Insisting anyway made the search grind through every candidate and
    reject each one, so a perfectly ordinary melody came back as "no
    solution" after eighty seconds.

    Colour the voicing added is dropped before anything else -- a ninth put
    there to fill a spare voice is decoration, and the melody needs the seat
    more than the decoration does. After that the fifth goes, then the root,
    which is the order a musician thins a chord in.
    """
    sounded = pitch % 12
    required = list(requirement.required_pitch_classes)
    if sounded not in required:
        required.append(sounded)
    free = voice_count
    if len(required) <= free:
        requirement.required_pitch_classes = [
            pc for pc in requirement.required_pitch_classes]
        return

    chord = requirement.chord
    from .theory import ROLE_FIFTH, ROLE_ROOT
    droppable = [chord.pitch_class_of(tone) for tone in requirement.plan.added]
    for role in (ROLE_FIFTH, ROLE_ROOT):
        for tone in chord.tones:
            if tone.role == role:
                droppable.append((chord.root_pc + tone.semitones) % 12)

    keep = [pc for pc in requirement.required_pitch_classes]
    for candidate in droppable:
        if len(keep) + (0 if sounded in keep else 1) <= free:
            break
        if candidate in keep and candidate != sounded:
            keep.remove(candidate)
    requirement.required_pitch_classes = keep


# ---------------------------------------------------------------------------
# El analizador
# ---------------------------------------------------------------------------
#
# El analizador no genera nada: recibe una partitura escrita y le pone
# nombres. Lo único que necesita de la fachada es volver a escribirla, y eso
# se hace con el mismo exportador que usan los tres modos --- una partitura
# analizada se guarda igual que cualquier otra, con las mismas voces en las
# mismas claves.

#: Qué voz del catálogo recibe cada línea, según cuántas haya. De acá sale el
#: reparto de claves al exportar: el exportador manda al pentagrama de fa al
#: bajo, al barítono y al tenor, y al de sol a todo lo demás.
ANALYSIS_VOICE_SETS: Dict[int, List[str]] = {
    1: ["S"],
    2: ["B", "S"],
    3: ["B", "A", "S"],
    4: ["B", "T", "A", "S"],
    5: ["B", "T", "A", "MS", "S"],
    6: ["B", "Bar", "T", "A", "MS", "S"],
}

#: Cómo se escribe cada nota del acorde, para que el exportador la deletree
#: bien. El tamaño del intervalo es lo que decide la letra: tres semitonos
#: son una tercera menor en un acorde menor y una segunda aumentada en otro
#: lado, y el analizador ya sabe cuál de las dos es.
_DEGREE_BY_SIZE = {
    1: {0: "1"},
    2: {2: "sus2"},
    3: {3: "b3", 4: "3"},
    4: {5: "sus4"},
    5: {6: "b5", 7: "5", 8: "#5"},
    6: {9: "6"},
    7: {9: "bb7", 10: "b7", 11: "7"},
}

_ROLE_BY_NAME = {
    "root": "root", "third": "third", "fifth": "fifth", "seventh": "seventh",
}


def _chord_from_reading(reading) -> Chord:
    """Pasar una lectura del analizador al acorde que el exportador entiende."""
    from .theory import ChordTone

    tones = []
    for pc, role, size in reading.tones:
        interval = (pc - reading.root_pc) % 12
        degree = _DEGREE_BY_SIZE.get(size, {}).get(interval, "1")
        tones.append(ChordTone(interval, _ROLE_BY_NAME.get(role, "extension"),
                               degree))
    chord = Chord(symbol=reading.symbol, root_pc=reading.root_pc,
                  root_letter=reading.root_name[0], tones=tones)
    if reading.bass_pc is not None and reading.bass_pc != reading.root_pc:
        chord.bass_pc = reading.bass_pc
        chord.bass_letter = None
    return chord


def _bars_of(score) -> List[Tuple[int, float, float]]:
    """
    Los compases que la pieza ocupa de verdad: número, comienzo y duración.

    `Score.bar_grid` sigue contando más allá del final ---necesita un compás
    de más para ubicar la última nota--- y escribir ésos dejaría compases
    vacíos al final del archivo.
    """
    finish = score.length()
    bars = []
    for number, start, per_bar in score.bar_grid():
        if start >= finish - 1e-6:
            break
        bars.append((number, start, per_bar))
    return bars


def _written_bar(part, start: float, end: float):
    """Lo que canta una voz dentro de un compás: pares (altura, duración).

    Los huecos salen como silencios y una nota que cruza la barra se corta
    en la barra: un compás de MusicXML tiene que sumar lo que dura el
    compás, y una nota que se pasa lo desborda.

    El pedazo que sigue en el compás siguiente lleva un tercer elemento,
    ``True``: el exportador lo liga con lo que viene. Cortada sin marca, una
    síncopa volvía reatacada en la barra ---dos notas donde había una---,
    en el MusicXML y en el MIDI.
    """
    events: List[Tuple] = []
    cursor = start
    for note in part.notes:
        if note.pitch is None or note.end <= start + 1e-6:
            continue
        if note.onset >= end - 1e-6:
            break
        onset = max(note.onset, start)
        finish = min(note.end, end)
        if onset > cursor + 1e-6:
            events.append((None, onset - cursor))
        if finish - onset > 1e-6:
            if note.end > end + 1e-6:
                events.append((note.pitch, finish - onset, True))
            else:
                events.append((note.pitch, finish - onset))
        cursor = max(cursor, finish)
    if end - cursor > 1e-6:
        events.append((None, end - cursor))
    return events


def analysis_score_spec(result, title: str = "Análisis"):
    """
    Armar la partitura exportable de un análisis.

    Lo que se exporta es la pieza **como está escrita**: cada voz con su
    propio ritmo, sus silencios y su armadura. Antes se escribía un hueco
    por sonoridad ---o sea, un ataque de todas las voces cada vez que se
    movía cualquiera---, y en una textura arpegiada eso quiere decir que la
    redonda del bajo salía reatacada dieciséis veces por compás: el Preludio
    de Bach volvía escrito entero en semicorcheas. Los compases salen de la
    grilla de la partitura ---con sus cambios de compás y su anacrusa--- y
    cada voz se escribe adentro de cada uno.

    Devuelve ``(spec, chromosome, filled)``, que es lo que espera
    :func:`engine.export.write_solution`. ``filled`` quedó en ``False``: los
    silencios ahora se escriben como silencios y no hay nada que tapar.
    """
    from .ga import Chromosome

    score = result.score
    voice_count = max(1, len(score.parts))
    keys = ANALYSIS_VOICE_SETS.get(
        voice_count,
        ["B"] + ["T"] * ((voice_count - 2) // 2)
        + ["A"] * (voice_count - 2 - (voice_count - 2) // 2) + ["S"])
    voices = build_voice_parts(keys[:voice_count])

    bars = _bars_of(score)
    if not bars:
        bars = [(1, 0.0, score.metrics_at(1)[0] or 4.0)]

    # El acorde de cada compás es el del segmento que lo gobierna. No se usa
    # para escribir las alturas ---eso lo decide la armadura--- pero el
    # exportador pide un acorde por hueco, y darle el que suena deja el
    # archivo diciendo la verdad si algún día se lo mira.
    slots: List[ChordSlot] = []
    pitch_rows: List[List[int]] = []
    for number, start, per_bar in bars:
        segment = None
        for candidate in result.segments:
            if candidate.start - 1e-6 <= start < candidate.end - 1e-6:
                segment = candidate
                break
        reading = segment.reading if segment is not None else None
        chord = (_chord_from_reading(reading) if reading is not None
                 else make_custom_chord([0], "acorde"))
        try:
            requirement = build_requirement(chord, voice_count)
        except Exception:                                   # noqa: BLE001
            requirement = build_requirement(make_custom_chord([0], "acorde"),
                                            voice_count)
        slots.append(ChordSlot(requirement=requirement,
                               duration_quarters=per_bar, bar_index=number))
        pitch_rows.append([60] * voice_count)

    lines: Dict[int, export.MelodyLine] = {}
    for voice, part in enumerate(score.parts):
        written = {number: _written_bar(part, start, start + per_bar)
                   for number, start, per_bar in bars}
        lines[voice] = export.MelodyLine(voice_index=voice, bars=written)

    signatures = [export.TimeSignature(*score.metre_at(max(1, number)))
                  for number, _start, _per_bar in bars]
    spec = export.ScoreSpec(
        slots=slots, voices=voices,
        time_signature=export.TimeSignature(score.beats, score.beat_type),
        bar_time_signatures=signatures,
        title=title, fifths=score.fifths,
        voice_lines=lines, spell_by_key=True,
        pickup=bool(bars) and bars[0][0] == 0)
    solution = Chromosome(slots=pitch_rows, choices=[0] * len(slots))
    return spec, solution, False


def export_analysis(
    result,
    directory: Optional[str] = None,
    formats: Sequence[str] = ("musicxml", "midi"),
    title: str = "Análisis",
) -> List[str]:
    """
    Escribir la partitura analizada, con los mismos formatos que el resto.

    No se anota en el historial: el historial guarda corridas del motor ---
    qué se le pidió y qué salió --- y un análisis no es una corrida. Nada de
    lo que el historial muestra (género, voces, ajustes del algoritmo)
    existe acá.
    """
    if not result.sonorities:
        return []
    target = directory or history.default_output_directory()
    os.makedirs(target, exist_ok=True)
    spec, solution, _filled = analysis_score_spec(result, title)
    stem = history.unique_basename(target, title)
    return export.write_solution(spec, solution, stem, formats)
