# -*- coding: utf-8 -*-
"""
Playing a solution back.

The point is to hear the voice leading immediately, without exporting a file
and opening something else. Fidelity is not the goal -- a plain plucked tone
is enough to judge whether the voices move well.

Este módulo decide **cuándo** suena cada nota; **cómo** suena lo decide
`engine.timbre`, que es por donde pasan todas las notas que el programa toca
y donde vive el timbre elegido en la configuración.

Everything is synthesised here and written to a WAV, then handed to whatever
the operating system already uses to play sound. Going through MIDI would
mean depending on a synthesiser being installed, which is exactly the kind of
thing that works on the developer's machine and nowhere else.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import threading
import wave
from array import array
from typing import Callable, Optional, Sequence

from . import ambience
from . import timbre as timbres
from .timbre import SAMPLE_RATE

#: Seconds per quarter note: a quarter at 96 bpm. Slow enough to hear the
#: inner voices, quick enough that eight bars do not become a chore.
SECONDS_PER_QUARTER = 0.625

#: Kept well below 1.0 so six simultaneous voices do not clip when summed.
VOICE_GAIN = 0.11


def midi_to_frequency(midi: int) -> float:
    """Equal temperament, A4 = 440 Hz."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def render_chords(
    chords: Sequence[Sequence[int]],
    durations: Sequence[float],
    tail_seconds: float = 0.7,
    melody: Sequence = (),
    quarter_seconds: Optional[float] = None,
    voices: Sequence = (),
    timbre: Optional[timbres.Choice] = None,
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

    Qué onda tiene cada nota lo decide `engine.timbre`: acá sólo se dice
    cuándo empieza, cuánto dura y con qué ganancia, y ``timbre`` pide uno
    en particular en vez del que está puesto (es lo que usa el botón de
    probar de la configuración). Ese módulo sintetiza una vez por altura y
    duración, que es lo que hace que una pieza entera no tarde: un coral
    repite las mismas notas acorde tras acorde.
    """
    if not chords and not melody and not voices:
        return b""
    beat = quarter_seconds or SECONDS_PER_QUARTER

    # La duración total: lo que suman los acordes, y también lo que ocupan
    # las voces sueltas ---las de un acorde adornado--- y la melodía: un
    # adorno al final de la última nota cae fuera de lo que suman los
    # acordes y quedaría cortado.
    total_quarters = sum(durations[i] if i < len(durations) else 2.0
                         for i in range(len(chords)))
    total_quarters = max(
        [total_quarters]
        + [start + length for _p, start, length in voices]
        + [start + length for _p, start, length in melody])
    total_samples = int((total_quarters * beat + tail_seconds) * SAMPLE_RATE)

    events = []

    def place(pitch, start_seconds: float, seconds: float, gain: float,
              start: Optional[int] = None) -> None:
        if start is None:
            start = int(start_seconds * SAMPLE_RATE)
        length = min(int((seconds + tail_seconds) * SAMPLE_RATE),
                     max(0, total_samples - start))
        if length > 0:
            events.append((int(pitch), start, seconds, length, gain))

    position = 0.0
    for index, chord in enumerate(chords):
        quarters = durations[index] if index < len(durations) else 2.0
        duration = quarters * beat
        for pitch in chord:
            place(pitch, position, duration, VOICE_GAIN)
        position += duration

    # Las voces de un acorde adornado vienen sueltas, cada una con su
    # comienzo y su duración: un adorno es media voz moviéndose mientras
    # las otras sostienen, y eso no se puede decir con una lista de
    # acordes. Suenan al mismo volumen que el resto --- son el resto.
    for pitch, start_quarters, length_quarters in voices:
        place(pitch, start_quarters * beat, length_quarters * beat,
              VOICE_GAIN)

    # A given melody is laid over the top with its own rhythm. Chords are
    # only placed on strong beats, so playing the harmonisation alone left
    # out every note between them -- most of the tune, in other words.
    # A touch louder than the accompaniment, so the tune leads.
    for pitch, start_quarters, length_quarters in melody:
        place(pitch, start_quarters * beat, length_quarters * beat,
              1.5 * VOICE_GAIN)

    buffer = timbres.mix(events, total_samples, timbre)
    return encode(buffer)


#: Hasta dónde puede llegar la mezcla. Por encima, la pieza entera se baja
#: en vez de recortarse: un recorte agrega armónicos que nadie tocó y con
#: varias voces suena a parlante roto.
CEILING = 0.97


def encode(buffer: Sequence[float]) -> bytes:
    """
    La mezcla a PCM de 16 bits.

    Con un timbre muy picudo ---el ataque del clave, el chillido de la
    flauta--- seis voces juntas pueden pasarse del techo aunque suenen
    igual de fuerte que la cuerda de siempre. Entonces se baja todo junto:
    el volumen lo iguala `engine.timbre` por sonoridad, y esto es sólo la
    red que impide que se rompa.
    """
    peak = max((abs(value) for value in buffer), default=0.0)
    scale = 32767.0 * (CEILING / peak if peak > CEILING else 1.0)
    frames = array("h", [int(value * scale) for value in buffer])
    if sys.byteorder == "big":
        frames.byteswap()
    return frames.tobytes()


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
    timbre: Optional[timbres.Choice] = None,
) -> threading.Thread:
    """
    Render and play a progression on a background thread.

    Returns the thread so the caller can tell whether playback is still
    going; ``on_finished`` fires when it ends, so a button can restore
    itself.

    El timbre se lee **al empezar**, en el hilo que llama: si el usuario lo
    cambia mientras esto suena, la pieza termina con el que empezó.
    """
    if timbre is None:
        timbre = timbres.current()
    def work() -> None:
        path = ""
        try:
            # Sintetizar es un bucle cerrado de Python que se queda con el
            # GIL en tandas largas: sin esto la ventana se arrastra mientras
            # se arma el sonido (3.000 llamadas a Tk pasaban de 13 ms a más
            # de dos segundos). Tocar el archivo no lo necesita.
            with ambience.fine_switching():
                frames = render_chords(chords, durations, melody=melody,
                                       quarter_seconds=quarter_seconds,
                                       voices=voices, timbre=timbre)
                handle = tempfile.NamedTemporaryFile(suffix=".wav",
                                                     delete=False)
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
