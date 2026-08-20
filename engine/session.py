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
            errors.append(f"Acorde {position}: {exc}")
            continue

        if not allow_special:
            chord = strip_special_voicings(chord)

        advice = check_chord_fits(chord, request.voice_count)
        if not advice.fits:
            if advice.suggested_omissions:
                warnings.append(f"Acorde {position}: {advice.message}")
            else:
                errors.append(f"Acorde {position}: {advice.message}")
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
                f"Acorde {position}: el candado fija {len(locked)} notas "
                f"pero hay {request.voice_count} voces, así que se ignoró."
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
    found: List[Tuple[int, int, int, float]] = []
    rows = getattr(solution, "passing", None) or []
    shares = getattr(solution, "passing_share", None) or []
    default = getattr(spec, "passing_share", 0.5)
    cursor = 0
    for index, slot in enumerate(spec.slots):
        if slot.is_rest:
            continue
        if cursor < len(rows):
            share = shares[cursor] if cursor < len(shares) else default
            for voice, note in enumerate(rows[cursor]):
                if note is not None:
                    found.append((index, voice, int(note), float(share)))
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

    decorated: Dict[int, List[Tuple[int, int, float]]] = {}
    for entry in ornaments:
        slot, voice, note, share = (list(entry) + [0.5])[:4]
        decorated.setdefault(int(slot), []).append(
            (int(voice), int(note), float(share)))

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
                moved = {voice: note for voice, note, _s in here}
                for voice, pitch in enumerate(chord):
                    if voice == drop_voice:
                        continue
                    if voice in moved:
                        notes.append((pitch, position, head))
                        notes.append((moved[voice], position + head, tail))
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
    quotation = getattr(outcome, "set_piece", None)
    quoted_slots = getattr(quotation, "slots", None) if quotation else None
    for index, solution in enumerate(outcome.result.solutions, start=1):
        stem = history.unique_basename(target, f"{request.title} - option {index}")
        spec = outcome.spec
        if index == 1 and quoted_slots:
            # The quotation is written from its own chords, so the score
            # shows the inversions -- six bars of plain "Am" would lose the
            # bass line the cadence is about. The other options keep the
            # generated chords.
            spec = replace(outcome.spec, slots=quoted_slots)
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
            symbols = [slot.symbol for slot in outcome.spec.slots]
            durations = [slot.duration_quarters for slot in outcome.spec.slots]
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
        pool = pool + harmony.modulation_pool(
            tonic_pc, modulation, request.with_sevenths
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
                 scale_pcs=mode.pitch_classes(tonic_pc))

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

    slots = outcome.spec.slots
    voice_count = len(outcome.spec.voices)
    locked = list(locked or [slot.is_locked for slot in slots])
    result = flourish.FlourishResult()

    def options_of(solution):
        out = []
        for index, slot in enumerate(slots):
            choice = solution.choices[index] if index < len(solution.choices) else 0
            if slot.options:
                out.append(slot.options[min(choice, len(slot.options) - 1)].harmony)
            else:
                out.append(None)
        return out

    def contexts_of(solution):
        """Los acordes en clases de altura, elija lo que elija la solución.

        El Organizador no tiene opciones armónicas ---el usuario escribió los
        cifrados--- así que ahí `options_of` devuelve una lista de None y todo
        lo que se reconoce por grado queda afuera. Esto, en cambio, existe
        siempre, y es lo que le alcanza al 6/4 para reconocerse en los tres
        modos.
        """
        out = []
        for index, slot in enumerate(slots):
            choice = solution.choices[index] if index < len(solution.choices) else 0
            requirement = (slot.options[min(choice, len(slot.options) - 1)].requirement
                           if slot.options else slot.requirement)
            out.append(ChordContext.from_chord(requirement.chord))
        return out

    best = outcome.result.solutions[0]
    options = options_of(best)

    # The sixth: common practice only, and only when the dice say so.
    rng = random.Random()
    if genre_key in ("classical", "chorale") and rng.random() < flourish.SIXTH_CHANCE:
        applied = flourish.apply_sixth(best.slots, locked, voice_count, rng)
        if applied is not None:
            result.sixth_slot, result.forced_slot, _voice = applied
            # The chord is not the triad it was, so its label has to change.
            slot = slots[result.sixth_slot]
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
        found = flourish.find_marks(
            options_of(solution), solution.slots, genre_key, tonic_pc,
            contexts_of(solution),
        )
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
        outcome = run(built, settings, lighter, solutions_wanted=1,
                      tonic_pc=bar.tonic,
                      progress=phase(MAIN_SHARE + share * variant, share,
                                     lighter.generations))
        return built, (outcome.solutions[0] if outcome.solutions else None)

    result = run(slots, settings, request.ga_config,
                 progress=phase(0.0, MAIN_SHARE, request.ga_config.generations),
                 solutions_wanted=1, tonic_pc=bar.tonic)

    # The alternatives are voiced separately, each keeping the slots it was
    # written for.
    alternates = []
    for variant, progression in enumerate(attempts[1:]):
        built, solution = voice(progression, variant)
        if solution is not None:
            alternates.append((built, solution))

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
    ranked = [(result.solutions[0], slots)] if result.solutions else []
    ranked += [(solution, built) for built, solution in alternates]
    ranked.sort(key=lambda pair: pair[0].cost)
    result.solutions = [solution for solution, _built in ranked]

    spec = export.ScoreSpec(
        slots=slots, voices=settings.voices,
        time_signature=export.TimeSignature(bar.beats, bar.beat_type),
        title=request.title, tempo_bpm=request.tempo_bpm,
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
                               for position, (_s, built) in enumerate(ranked)}
    if not result.solutions:
        outcome.errors.append(result.message or "No se encontró una solución.")
    else:
        apply_flourishes(outcome, request.genre_key, bar.tonic)
    return outcome


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
