# -*- coding: utf-8 -*-
"""
Playing a solution back.

The point is to hear the voice leading immediately, without exporting a file
and opening something else. Fidelity is not the goal -- a plain plucked tone
is enough to judge whether the voices move well.

Everything is synthesised here and written to a WAV, then handed to whatever
the operating system already uses to play sound. Going through MIDI would
mean depending on a synthesiser being installed, which is exactly the kind of
thing that works on the developer's machine and nowhere else.
"""

from __future__ import annotations

import math
import os
import platform
import struct
import subprocess
import tempfile
import threading
import wave
from typing import Callable, Optional, Sequence

SAMPLE_RATE = 44100

#: Seconds per quarter note: a quarter at 96 bpm. Slow enough to hear the
#: inner voices, quick enough that eight bars do not become a chore.
SECONDS_PER_QUARTER = 0.625

#: Kept well below 1.0 so six simultaneous voices do not clip when summed.
VOICE_GAIN = 0.11


def midi_to_frequency(midi: int) -> float:
    """Equal temperament, A4 = 440 Hz."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _voice_sample(frequency: float, t: float, duration: float) -> float:
    """
    One voice at time ``t``: a decaying tone with a couple of overtones.

    A bare sine sounds like a test signal and makes it oddly hard to follow
    separate voices. A little second and third harmonic, plus a plucked
    decay, is enough for the ear to pick the lines apart.
    """
    envelope = math.exp(-2.2 * t / max(duration, 0.05))
    attack = min(1.0, t / 0.012)      # a short fade-in avoids a click
    angle = 2.0 * math.pi * frequency * t
    tone = (math.sin(angle)
            + 0.32 * math.sin(2.0 * angle)
            + 0.14 * math.sin(3.0 * angle))
    return tone * envelope * attack


def render_chords(
    chords: Sequence[Sequence[int]],
    durations: Sequence[float],
    tail_seconds: float = 0.7,
    melody: Sequence = (),
    quarter_seconds: Optional[float] = None,
    voices: Sequence = (),
) -> bytes:
    """
    Render a progression to 16-bit mono PCM.

    ``quarter_seconds`` overrides the tempo. The default is deliberately slow
    --- it exists so four voices can be followed by ear --- but a piece meant
    to be heard as music rather than inspected needs to move at its own
    speed, and the story mode has several of those.

    Chord ``i`` sounds for ``durations[i]`` quarter notes. Notes ring on past
    their slot into the next one, which is what keeps the result from
    sounding like a row of disconnected blocks.

    The envelope is computed once per distinct duration and the waveform is
    built with a running phase rather than a sine call per sample, because
    the naive version took over a second for four chords -- long enough for
    the button to feel broken on a full piece.
    """
    if not chords and not melody and not voices:
        return b""
    beat = quarter_seconds or SECONDS_PER_QUARTER

    if not chords and not voices:
        # A melody on its own: the buffer is sized from the line instead.
        span = max((start + length for _p, start, length in melody), default=0.0)
        total_samples = int((span * beat + tail_seconds) * SAMPLE_RATE)
        buffer = [0.0] * total_samples
        envelopes: dict = {}

        def envelope_for(duration: float, length: int) -> list:
            key = (round(duration, 3), length)
            if key not in envelopes:
                shape = []
                for offset in range(length):
                    t = offset / SAMPLE_RATE
                    shape.append(math.exp(-2.2 * t / max(duration, 0.05))
                                 * min(1.0, t / 0.012))
                envelopes[key] = shape
            return envelopes[key]

        for pitch, start_quarters, length_quarters in melody:
            duration = length_quarters * beat
            start = int(start_quarters * beat * SAMPLE_RATE)
            length = min(int((duration + tail_seconds) * SAMPLE_RATE),
                         max(0, total_samples - start))
            if length <= 0:
                continue
            shape = envelope_for(duration, length)
            step = 2.0 * math.pi * midi_to_frequency(pitch) / SAMPLE_RATE
            angle = 0.0
            for offset in range(length):
                tone = (math.sin(angle) + 0.32 * math.sin(2.0 * angle)
                        + 0.14 * math.sin(3.0 * angle))
                buffer[start + offset] += 1.5 * VOICE_GAIN * tone * shape[offset]
                angle += step
        frames = bytearray()
        for value in buffer:
            clamped = -1.0 if value < -1.0 else (1.0 if value > 1.0 else value)
            frames += struct.pack("<h", int(clamped * 32767))
        return bytes(frames)

    total_quarters = sum(durations[i] if i < len(durations) else 2.0
                         for i in range(len(chords)))
    # Las voces sueltas ---las de un acorde adornado--- se miden también:
    # un adorno al final de la última nota cae fuera de lo que suman los
    # acordes y quedaría cortado.
    total_quarters = max(
        [total_quarters]
        + [start + length for _p, start, length in voices])
    total_samples = int((total_quarters * beat + tail_seconds) * SAMPLE_RATE)
    buffer = [0.0] * total_samples

    envelopes: dict = {}

    def envelope_for(duration: float, length: int) -> list:
        key = (round(duration, 3), length)
        if key not in envelopes:
            shape = []
            for offset in range(length):
                t = offset / SAMPLE_RATE
                shape.append(math.exp(-2.2 * t / max(duration, 0.05))
                             * min(1.0, t / 0.012))
            envelopes[key] = shape
        return envelopes[key]

    position = 0.0
    for index, chord in enumerate(chords):
        quarters = durations[index] if index < len(durations) else 2.0
        duration = quarters * beat
        start = int(position * SAMPLE_RATE)
        length = min(int((duration + tail_seconds) * SAMPLE_RATE),
                     max(0, total_samples - start))
        if length <= 0:
            position += duration
            continue
        shape = envelope_for(duration, length)

        for pitch in chord:
            step = 2.0 * math.pi * midi_to_frequency(pitch) / SAMPLE_RATE
            angle = 0.0
            for offset in range(length):
                tone = (math.sin(angle)
                        + 0.32 * math.sin(2.0 * angle)
                        + 0.14 * math.sin(3.0 * angle))
                buffer[start + offset] += VOICE_GAIN * tone * shape[offset]
                angle += step
        position += duration

    # Las voces de un acorde adornado vienen sueltas, cada una con su
    # comienzo y su duración: un adorno es media voz moviéndose mientras
    # las otras sostienen, y eso no se puede decir con una lista de
    # acordes. Suenan al mismo volumen que el resto --- son el resto.
    for pitch, start_quarters, length_quarters in voices:
        duration = length_quarters * beat
        start = int(start_quarters * beat * SAMPLE_RATE)
        length = min(int((duration + tail_seconds) * SAMPLE_RATE),
                     max(0, total_samples - start))
        if length <= 0:
            continue
        shape = envelope_for(duration, length)
        step = 2.0 * math.pi * midi_to_frequency(pitch) / SAMPLE_RATE
        angle = 0.0
        for offset in range(length):
            tone = (math.sin(angle) + 0.32 * math.sin(2.0 * angle)
                    + 0.14 * math.sin(3.0 * angle))
            buffer[start + offset] += VOICE_GAIN * tone * shape[offset]
            angle += step

    # A given melody is laid over the top with its own rhythm. Chords are
    # only placed on strong beats, so playing the harmonisation alone left
    # out every note between them -- most of the tune, in other words.
    for pitch, start_quarters, length_quarters in melody:
        duration = length_quarters * beat
        start = int(start_quarters * beat * SAMPLE_RATE)
        length = min(int((duration + tail_seconds) * SAMPLE_RATE),
                     max(0, total_samples - start))
        if length <= 0:
            continue
        shape = envelope_for(duration, length)
        step = 2.0 * math.pi * midi_to_frequency(pitch) / SAMPLE_RATE
        angle = 0.0
        for offset in range(length):
            tone = (math.sin(angle) + 0.32 * math.sin(2.0 * angle)
                    + 0.14 * math.sin(3.0 * angle))
            # A touch louder than the accompaniment, so the tune leads.
            buffer[start + offset] += 1.5 * VOICE_GAIN * tone * shape[offset]
            angle += step

    frames = bytearray()
    for value in buffer:
        clamped = -1.0 if value < -1.0 else (1.0 if value > 1.0 else value)
        frames += struct.pack("<h", int(clamped * 32767))
    return bytes(frames)


def write_wav(path: str, frames: bytes) -> None:
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)


def _play_file(path: str) -> None:
    """Hand a WAV to whatever this system plays sound with."""
    system = platform.system()
    if system == "Windows":
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)
            return
        except Exception:                                   # noqa: BLE001
            pass
    elif system == "Darwin":
        try:
            subprocess.run(["afplay", path], check=False)
            return
        except FileNotFoundError:
            pass

    for command in (["aplay", "-q", path],
                    ["paplay", path],
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
        try:
            subprocess.run(command, check=False)
            return
        except FileNotFoundError:
            continue


def play_chords(
    chords: Sequence[Sequence[int]],
    durations: Sequence[float],
    on_finished: Optional[Callable[[], None]] = None,
    melody: Sequence = (),
    quarter_seconds: Optional[float] = None,
    voices: Sequence = (),
) -> threading.Thread:
    """
    Render and play a progression on a background thread.

    Returns the thread so the caller can tell whether playback is still
    going; ``on_finished`` fires when it ends, so a button can restore
    itself.
    """
    def work() -> None:
        path = ""
        try:
            frames = render_chords(chords, durations, melody=melody,
                                   quarter_seconds=quarter_seconds,
                                   voices=voices)
            handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            path = handle.name
            handle.close()
            write_wav(path, frames)
            _play_file(path)
        except Exception:                                   # noqa: BLE001
            pass
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if on_finished is not None:
                on_finished()

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread
