# -*- coding: utf-8 -*-
"""
ChordWeaver desktop application.

A carousel of screens: genre, voices, metre, chords, parameters, results.
Every screen can be stepped back to, and nothing is configured through files
or code -- the whole job is described through the interface.

The window never blocks: the genetic algorithm runs on a background thread
and reports progress through a queue that the Tk main loop drains on a timer.
Tk is not thread-safe, so the worker thread never touches a widget directly.
"""

from __future__ import annotations

import os
import queue
import random
import threading
import time
import tkinter as tk
import traceback
from types import SimpleNamespace
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Antes que customtkinter, y antes que cualquier módulo que lo importe: sin
# consola, el primer aviso de una librería mataba el ejecutable. Ver
# `engine.console`.
from engine import console
console.guard_streams()

# Pillow, que customtkinter importa enseguida, también trae módulos
# compilados, y con el programa en una carpeta profunda Windows no los
# carga. Desde una ruta corta, igual que el motor (`engine.shortpath`).
try:
    import PIL
    from engine import __version__ as _VERSION, shortpath
    shortpath.relocate(PIL.__path__, "PIL", _VERSION)
except Exception:                                           # noqa: BLE001
    pass

import customtkinter as ctk


def _rescue_widget_fonts() -> None:
    """
    Volver a cargar las fuentes de customtkinter desde una ruta corta.

    customtkinter las carga al importarse desde su propia carpeta, y Windows
    no carga una fuente cuya ruta pase los 260 caracteres. Sin la de formas,
    customtkinter dibuja los bordes redondeados con círculos y lo avisa:
    «The rendering quality will be bad!». Pasa en cuanto el programa se
    descomprime un par de carpetas adentro, así que se copian las tres a la
    carpeta temporal y se cargan desde ahí.
    """
    import sys
    import shutil
    import tempfile
    if not sys.platform.startswith("win"):
        return
    try:
        from customtkinter.windows.widgets.core_rendering import DrawEngine
        from customtkinter.windows.widgets.font import FontManager
    except ImportError:
        return
    if DrawEngine.preferred_drawing_method != "circle_shapes":
        return
    source = os.path.join(os.path.dirname(ctk.__file__), "assets", "fonts")
    target = os.path.join(tempfile.gettempdir(), "ChordWeaver-fonts")
    loaded = {}
    for name in ("CustomTkinter_shapes_font.otf",
                 os.path.join("Roboto", "Roboto-Regular.ttf"),
                 os.path.join("Roboto", "Roboto-Medium.ttf")):
        short = os.path.join(target, os.path.basename(name))
        try:
            os.makedirs(target, exist_ok=True)
            original = os.path.join(source, name)
            # Por tamaño y no sólo por existencia: una copia cortada a medias
            # ---dos programas abiertos a la vez--- o de otra versión de
            # customtkinter dejaba los bordes con círculos para siempre.
            if (not os.path.exists(short)
                    or os.path.getsize(short) != os.path.getsize(original)):
                shutil.copyfile(original, short)
            loaded[name] = FontManager.load_font(short)
        except OSError:
            loaded[name] = False
    if loaded.get("CustomTkinter_shapes_font.otf"):
        DrawEngine.preferred_drawing_method = "font_shapes"


_rescue_widget_fonts()

import analyzer
import chooser
import cinematic
import homeart
import school
import spectrum
import updater
from engine import __version__ as APP_VERSION
from engine import history, session
from engine.i18n import N, tr, trf, trs
from engine import i18n
from engine.export import TimeSignature
from engine import (achievements, ambience, audio, book, eggs, harmonize,
                    harmony, importer, passing, story, updates, visitors,
                    voicing)
from engine import timbre as timbres
from engine import school as curriculum
from staff import (
    CHROMATIC_COLOUR,
    DURATIONS,
    GRAND_VOICE_COUNT,
    GrandStaff,
    VOICE_COLOURS,
    MelodyPiano,
    StaffEditor,
    legend_swatch,
    pitch_at as staff_pitch,
)
from engine.fitness import GENRE_PROFILES
from engine.ga import GAConfig, resolve_worker_count
from engine.theory import (
    ChordParseError,
    figured_bass,
    intervals_above_bass,
    make_custom_chord,
    SHARP_NAMES,
    VOICE_CATALOG,
    note_name,
    parse_chord,
    parse_note_name,
    parse_pitch_class,
)
from engine.voicing import check_chord_fits

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paleta sobria: un acento contenido sobre grises neutros. Los tres fondos
# están escalonados a propósito -- `SURFACE` es el vidrio de la ventana,
# `SURFACE_LIGHT` es un panel apoyado encima y `SURFACE_RAISED` es ese mismo
# panel levantado por el mouse. Tres pasos alcanzan para que se lea la
# profundidad sin que ninguna pantalla parezca un collage.
ACCENT = "#5B8FD6"
ACCENT_HOVER = "#6FA0E2"
SURFACE = "#1B1D22"
SURFACE_LIGHT = "#25282F"
SURFACE_RAISED = "#30343D"
#: Borde neutro de las tarjetas cuando no están ni elegidas ni bajo el mouse.
BORDER_SOFT = "#353942"
TEXT_MUTED = "#98A0AC"
TEXT_NORMAL = "#E6E8EB"
#: Cuánto se premia un acorde prestado con el dial en su lugar de fábrica.
#: La escala va de 0 a 100; esto es el mismo sexto de camino que tenía la
#: escala vieja, o sea que el punto de partida suena igual que siempre.
BORROWED_DEFAULT = 15.0

#: Used to tint the chords that sit in another key.
MODULATION_TINT = "#3A3560"
#: Un acorde prestado del modo paralelo. Naranja y no violeta: el violeta ya
#: dice "esto está en otra tonalidad", y un préstamo no es una modulación
#: --- sigue en la misma tonalidad, sólo que con una nota de la escala
#: cambiada.
BORROWED_TINT = "#4A3226"
BORROWED_TEXT = "#F0A878"
#: A quotation that turned up instead of a generated progression.
SET_PIECE_TINT = "#4A3A1F"
SET_PIECE_TEXT = "#E8C97A"
MODULATION_TEXT = "#C7BCF5"
OK_GREEN = "#4C9A5E"
WARN = "#C9A227"
ERROR = "#B4534B"
#: Oros de los logros. La lista se recorre en bucle para que un título
#: legendario parezca tener una textura que se mueve: tkinter no sabe pintar
#: un degradado animado sobre un texto, pero sí cambiarle el color, y
#: recorrer estos tonos a ~12 cuadros por segundo se lee como un brillo que
#: viaja. Es una sola llamada a `configure` por cuadro, así que no cuesta
#: nada aunque haya varios títulos en pantalla.
GOLD = "#E8C97A"
GOLD_DIM = "#8A7746"
GOLD_SHADES = ["#C7982F", "#D9AE4E", "#E8C97A", "#F6EBC0", "#FFF8E0",
               "#F6EBC0", "#E8C97A", "#D9AE4E"]
#: Fondo del velo que oscurece la ventana en las animaciones.
VEIL = "#0A0B0D"

#: En el índice del libro, el capítulo donde quedó una anotación sin leer.
#: Azul y no dorado: el oro ya dice otra cosa --- «esto no se estudia, se le
#: aparece a uno» --- y es permanente. Más claro y más frío que `ACCENT` en
#: su tono más azul, que es el del Organizador: si fuera el mismo, se leería
#: como una parte más del modo en curso.
NOTE_BLUE = "#79B8F5"

#: Los tonos del libro de teoría. Es papel viejo traído a la oscuridad de la
#: app: el mismo gesto --- fondo cálido, tinta que no llega a ser blanca, un
#: filete dorado y una tipografía con serifas --- sin irse a un beige que en
#: una ventana oscura encandilaría y rompería con todo lo demás.
PAPER = "#211E1A"
PAPER_EDGE = "#2A2621"
INK = "#E7E0D2"
INK_MUTED = "#A79E8C"
INK_FAINT = "#6F6759"
RULE = "#3B352C"

#: Every font in the interface is derived from these through `scaled()`, so
#: one accessibility setting resizes the whole program rather than a few
#: labels that happened to be remembered.
FONT_SCALE = 1.0


#: Font tuples, built once per (font, scale) pair.
_FONT_CACHE: Dict[tuple, tuple] = {}


def _keep_tk_off_the_worker_thread() -> None:
    """
    Stop Tk objects being finalised on the search thread.

    Several tkinter classes call back into Tk from ``__del__``: fonts delete
    themselves, variables unset themselves, images free themselves. Python
    runs finalisers on whichever thread happens to trigger collection, so
    those calls landed inside the search -- and because Tk serialises access
    from other threads, the worker sat blocked. Measured, the same search
    took 0.5 seconds or 84 depending on where the collector fired, using
    0.3s of CPU the whole time.

    Variables and images do the same thing -- unsetting and freeing
    themselves through Tk -- so all three are covered.

    Suppressing the destructors is safe for this program: these objects live
    as long as the window does, and the process reclaims everything on exit.
    It trades a little Tcl-side memory, freed at shutdown anyway, for a
    search that always takes the time it actually needs.
    """
    import tkinter
    import tkinter.font as tkfont

    def no_op(self) -> None:
        return

    for cls in (tkfont.Font, tkinter.Variable, tkinter.Image):
        if hasattr(cls, "__del__"):
            cls.__del__ = no_op


_keep_tk_off_the_worker_thread()


def scaled(font):
    """
    Return a font tuple resized by the accessibility setting.

    Cached because every call used to hand Tk a fresh tuple, and Tk answers
    a new tuple by creating a font object it later finalises -- sometimes on
    whichever thread the garbage collector happens to be running on. That
    put ``tkinter.font.__del__`` in the middle of the search thread, which
    then blocked on Tk's own lock for tens of seconds at a time.
    """
    key = (font, FONT_SCALE)
    cached = _FONT_CACHE.get(key)
    if cached is None:
        family, size = font[0], font[1]
        rest = font[2:] if len(font) > 2 else ()
        cached = (family, max(7, int(round(size * FONT_SCALE)))) + tuple(rest)
        _FONT_CACHE[key] = cached
    return cached


FONT_TITLE = ("Segoe UI Semibold", 22)
FONT_SUB = ("Segoe UI", 13)
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)

#: La fuente de los iconos decorativos. Segoe UI Symbol es la que trae los
#: bloques de formas geométricas y de música en Windows; el resto de la
#: interfaz usa Segoe UI, que no los tiene todos.
FONT_ICON = ("Segoe UI Symbol", 20)

#: El libro va con serifas. Georgia viene con Windows, está pensada para leer
#: en pantalla y es lo más cerca de un libro que se puede estar sin pelearse
#: con la legibilidad.
FONT_BOOK = ("Georgia", 12)
FONT_BOOK_HEAD = ("Georgia", 21)
#: La letra de las anotaciones a mano. Segoe Script también viene con
#: Windows; si faltara, Tk cae en la fuente por defecto y el texto se lee
#: igual, sólo que sin el gesto.
FONT_HAND = ("Segoe Script", 11)


# ---------------------------------------------------------------------------
# Animación
#
# Tkinter no sabe interpolar nada: no hay transiciones, ni opacidad, ni
# transformaciones. Lo único que se puede animar barato es el color de un
# widget, porque `configure` sobre un color ya construido no vuelve a armar
# el widget. Todo el movimiento de la interfaz sale de estas dos funciones:
# `mix` calcula el color intermedio y `animate` lo reparte en cuadros.
#
# Nada de esto reacomoda la ventana. Animar geometría (padding, tamaño,
# posición) obliga a Tk a recalcular el layout entero en cada cuadro, y en
# las pantallas grandes eso se ve peor que no animar nada.
# ---------------------------------------------------------------------------

def mix(colour_a: str, colour_b: str, position: float) -> str:
    """Color intermedio entre dos hex. ``position`` 0 devuelve el primero."""
    position = 0.0 if position < 0.0 else 1.0 if position > 1.0 else position
    left = (int(colour_a[1:3], 16), int(colour_a[3:5], 16), int(colour_a[5:7], 16))
    right = (int(colour_b[1:3], 16), int(colour_b[3:5], 16), int(colour_b[5:7], 16))
    return "#%02X%02X%02X" % tuple(
        int(round(a + (b - a) * position)) for a, b in zip(left, right)
    )


def animate(widget, frame, steps: int = 6, period: int = 16,
            key: str = "_anim_id", delay: int = 0) -> None:
    """
    Correr ``frame(t)`` con ``t`` de 0 a 1 repartido en ``steps`` cuadros.

    El ``after`` pendiente se guarda en el propio widget bajo ``key`` y se
    cancela antes de arrancar, así dos animaciones sobre la misma propiedad
    no se pisan -- entrar y salir rápido con el mouse dejaba la tarjeta a
    mitad de camino. Se apaga sin ruido en cuanto el widget deja de existir,
    que es lo que hace que cambiar de pantalla no deje temporizadores
    colgados apuntando a widgets muertos.
    """
    pending = getattr(widget, key, None)
    if pending is not None:
        try:
            widget.after_cancel(pending)
        except Exception:              # noqa: BLE001 - widget may be gone
            pass
        setattr(widget, key, None)

    def step(index: int) -> None:
        try:
            if not widget.winfo_exists():
                return
            frame(index / steps)
            if index >= steps:
                setattr(widget, key, None)
                return
            setattr(widget, key, widget.after(period, step, index + 1))
        except tk.TclError:
            return

    try:
        if delay > 0:
            setattr(widget, key, widget.after(delay, step, 0))
        else:
            step(0)
    except tk.TclError:
        return

#: Silence is offered as a chord "quality" in the same menu as the durations
#: it can take, so a rest is created the same way as a chord.
REST_PREFIX = "Silencio "

DURATION_LABELS = [
    ("Redonda (4)", 4.0),
    ("Blanca (2)", 2.0),
    ("Negra c/punto (1½)", 1.5),
    ("Negra (1)", 1.0),
    ("Corchea (1/2)", 0.5),
]

TIME_SIGNATURES = ["4/4", "3/4", "2/4", "6/8", "9/8", "12/8", "5/4", "2/2"]

#: Cuántos compases se pueden pedir desde la interfaz. Era 64.
#:
#: Se baja por lo que cuesta una pieza larga en las dos puntas: la búsqueda
#: crece con la cantidad de acordes ---y en el Generador tiene además que
#: *elegirlos*, no sólo repartirlos---, y la pantalla de acordes arma tres
#: widgets por casilla con dos casillas por compás. A 64 compases eso es una
#: espera larga sin ningún aviso previo, y nadie escribe una pieza de 64
#: compases a mano por accidente: el que la quiera la arma en dos partes.
#:
#: Es un tope **de la interfaz** y no del motor. `cli.py` sigue aceptando lo
#: que se le pida, y `engine/` no sabe que esto existe.
#:
#: Sólo lo miran el Organizador y el Generador, que son los dos modos que
#: pasan por la pantalla de compases; el Armonizador saca la métrica de la
#: melodía dibujada y no pregunta nada de esto.
MAX_BARS = 32

#: Palabras de la interfaz que llegan a `tr()` desde una tabla o una
#: variable y no llevan ninguna marca del castellano: sin esto el auditor no
#: las ve, nadie les escribe la traducción y con la interfaz en inglés
#: salían en castellano ---los nombres de tres de los modos, las figuras, el
#: estilo coral---.
UI_WORDS = (
    N("Organizador"), N("Generador"), N("Armonizador"), N("Experimentador"),
    N("Coral"), N("Historial · detalle"),
    N("Redonda"), N("Blanca"), N("Negra c/punto"), N("Negra"),
    N("Corchea c/punto"), N("Corchea"),
    N("Redonda (4)"), N("Blanca (2)"), N("Negra c/punto (1½)"), N("Negra (1)"),
    N("Corchea (1/2)"),
    N("Silencio Redonda (4)"), N("Silencio Blanca (2)"),
    N("Silencio Negra c/punto (1½)"), N("Silencio Negra (1)"),
    N("Silencio Corchea (1/2)"),
    # Los meses del historial (`ProductionRecord.MONTHS`).
    N("ene"), N("feb"), N("mar"), N("abr"), N("may"), N("jun"),
    N("jul"), N("ago"), N("sep"), N("oct"), N("nov"), N("dic"),
)

#: Los nombres de `theory.VOICE_CATALOG` que no llevan ninguna marca del
#: castellano. `theory` no importa nada del proyecto y no puede marcarlos él;
#: sin esto el auditor no los reconoce y su traducción figura como sobrante.
VOICE_NAMES = (N("Bajo"), N("Mezzosoprano"))

#: El fondo hundido de una ficha de acorde, entre el de la ventana y el de
#: la tarjeta del compás.
CHIP = "#202228"

#: El ancho del medidor de tiempos de cada compás, en píxeles.
METER_WIDTH = 92

#: Cuántos compases por renglón en la pantalla de compases, y el ancho de
#: la fila de puntos que dibuja sus tiempos (doce corcheas de un 12/8).
BAR_TILES = 6
BEAT_DOTS_WIDTH = 100

GENRE_BLURBS = {
    "classical": "El contrapunto de los corales y las invenciones de Bach. Es "
                 "el más estricto de los tres, y con el modo coral se "
                 "endurece todavía más.",
    "gregorian": "Escritura modal, anterior a la tonalidad. Casi todo el "
                 "movimiento es por grado conjunto y el resultado suena a "
                 "canto llano más que a armonía.",
    "jazz": "Armonía extendida. Lo que importa es cómo pasan la tercera y la "
            "séptima de cada acorde al siguiente.",
}

#: Lo que cada estilo hace distinto, en tres o cuatro líneas. Van como lista
#: y no dentro del párrafo porque son justamente los ítems que el usuario
#: compara entre una tarjeta y otra.
GENRE_POINTS = {
    "classical": ("Sin quintas ni octavas paralelas",
                  "Premia el movimiento contrario",
                  "Castiga saltos de tritono y de séptima",
                  "Incluye el modo coral, más estricto"),
    "gregorian": ("Evita el tritono, saltado y entre voces",
                  "Tolera las paralelas perfectas",
                  "Permite organum a la 4ta, la 5ta y la 8va"),
    "jazz": ("Conecta las guide tones por grado conjunto",
             "Mantiene las notas comunes entre acordes",
             "Evita las novenas menores",
             "Deja pasar paralelas y tritonos"),
}

#: Color e icono de cada estilo. La interfaz era de un solo azul de punta a
#: punta y las cuatro pantallas de elegir se leían todas iguales; darle un
#: color propio a cada opción es lo que hace que se distingan de un vistazo,
#: y ese color después tiñe el riel de progreso durante todo el recorrido.
GENRE_THEMES = {
    "classical": ("#C89B4B", "⚜"),
    "gregorian": ("#7FA98C", "✝"),
    "jazz": ("#B07FD6", "♫"),
    # No es elegible como tarjeta -- es el switch "Modo coral" dentro de
    # Barroco -- pero conviene que tenga entrada igual.
    "chorale": ("#C89B4B", "⚜"),
}

#: Los tres modos de trabajo: clave interna, nombre, bajada, descripción,
#: los pasos que va a pedir, color e icono. El nombre es lo único que el
#: usuario ve; la clave es la que el resto del programa consulta y no cambia.
#: La pregunta real de esta pantalla no es "¿cuál te gusta más?" sino "¿qué
#: me va a pedir cada uno?", y la contesta el dibujo de cada tarjeta
#: (`homeart.draw_flow`): lo que ponés vos, una flecha y lo que escribe el
#: programa. Con un párrafo y tres pasos numerados había que leer las tres
#: tarjetas para ver la diferencia. El icono ya no va en la tarjeta; lo usa
#: el historial.
MODE_CARDS = [
    ("manual", N("Organizador"), N("Vos ponés los acordes"), "#5B8FD6", "◧"),
    ("random", N("Generador"), N("El programa pone los acordes"), "#B07FD6", "✧"),
    ("harmonise", N("Armonizador"), N("Vos ponés la melodía"), "#4FAE96", "♪"),
]

#: Lo que todavía se está terminando ---modos y herramientas---. El aviso va
#: **dentro** de la tarjeta, al lado del nombre: es lo que hay que saber
#: antes de elegir, y dicho más adelante llega tarde.
MODE_FLAGS = {"analysis": "BETA"}


#: Las tres herramientas que no componen nada. Tarjetas del mismo tamaño que
#: las de los modos, con su dibujo (`homeart.draw_tool`) y una oración:
#: más chicas, se leían como algo menor, y cada una es un lugar entero del
#: programa.
#:
#: Colores propios, distintos de los tres modos: no son una cuarta y una
#: quinta manera de trabajar, y el riel de progreso no se tiñe con ellos.
TOOL_CARDS = [
    ("lab", N("Experimentador"), N("De qué está hecha una nota"),
     N("Encendé, apagá y mové los armónicos de una nota y escuchá cómo "
       "cambia."),
     "#C9954F", "≈"),
    ("analysis", N("Analizador"), N("Vos traés la partitura"),
     N("Traés una partitura y te dice qué acorde es cada uno, qué función "
       "cumple y qué hacen las voces."),
     "#B5705F", "𝄞"),
    # La escuelita es la tercera: no compone nada y usa al analizador de
    # base ---el alumno escribe, el analizador corrige---, así que es una
    # herramienta y no un modo. Rosa de tiza: ninguno de los otros cinco
    # colores, y lejos del rojo con el que la corrección marca lo que está
    # mal.
    ("school", N("Escuelita"), N("Aprender escribiendo"),
     N("Ocho unidades con ejercicios de escritura que corrige el "
       "analizador."),
     "#D3809F", "✎"),
]

#: La fila de la pantalla inicial donde va el estante de logros y libro:
#: debajo de los modos, el título de las herramientas y las herramientas.
#: La siguiente es la del sendero, y la que sigue queda vacía y es la que se
#: estira, así lo que sobra de alto cae abajo de todo.
HOME_SHELF_ROW = 3


# ---------------------------------------------------------------------------
# Small reusable widgets
# ---------------------------------------------------------------------------

class PianoSelector(ctk.CTkFrame):
    """
    A clickable piano for building a chord by hand.

    Used when the chord the user wants is not something the symbol parser
    knows. Selected keys light up green and are listed with their octave, so
    there is never any doubt which register was picked.
    """

    WHITE_PATTERN = [0, 2, 4, 5, 7, 9, 11]
    BLACK_PATTERN = {1: 0, 3: 1, 6: 3, 8: 4, 10: 5}

    KEY_WIDTH = 26
    KEY_HEIGHT = 96
    BLACK_WIDTH = 16
    BLACK_HEIGHT = 60

    def __init__(self, master, first_octave: int = 3, octaves: int = 3, **kwargs):
        super().__init__(master, fg_color=SURFACE_LIGHT, corner_radius=11, **kwargs)
        self.first_octave = first_octave
        self.octaves = octaves
        self.selected: List[int] = []
        self._rects: Dict[int, int] = {}

        width = octaves * 7 * self.KEY_WIDTH + 2
        self.canvas = tk.Canvas(
            self, width=width, height=self.KEY_HEIGHT + 2,
            bg=SURFACE_LIGHT, highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=(10, 4))
        self.label = ctk.CTkLabel(self, text=tr("Ninguna nota seleccionada"),
                                  font=FONT_SMALL, text_color=TEXT_MUTED)
        self.label.pack(pady=(0, 10))
        self._draw_keys()
        self.canvas.bind("<Button-1>", self._on_click)

    def _draw_keys(self) -> None:
        # NOTE: deliberately not called _draw -- CTkFrame already defines a
        # _draw(no_color_updates=...) that customtkinter calls internally, and
        # shadowing it breaks widget construction.
        self.canvas.delete("all")
        self._rects.clear()

        # White keys first, black keys on top so they capture clicks.
        for octave_index in range(self.octaves):
            octave = self.first_octave + octave_index
            for position, semitone in enumerate(self.WHITE_PATTERN):
                x = (octave_index * 7 + position) * self.KEY_WIDTH + 1
                midi = (octave + 1) * 12 + semitone
                rect = self.canvas.create_rectangle(
                    x, 1, x + self.KEY_WIDTH, self.KEY_HEIGHT,
                    fill="#F2F2F0", outline="#4A4C52",
                )
                self._rects[midi] = rect
                self.canvas.create_text(
                    x + self.KEY_WIDTH / 2, self.KEY_HEIGHT - 12,
                    text=f"{SHARP_NAMES[semitone]}{octave}",
                    font=scaled(("Segoe UI", 7)), fill="#5A5C62",
                )

        for octave_index in range(self.octaves):
            octave = self.first_octave + octave_index
            for semitone, white_index in self.BLACK_PATTERN.items():
                x = ((octave_index * 7 + white_index) * self.KEY_WIDTH
                     + self.KEY_WIDTH - self.BLACK_WIDTH // 2 + 1)
                midi = (octave + 1) * 12 + semitone
                rect = self.canvas.create_rectangle(
                    x, 1, x + self.BLACK_WIDTH, self.BLACK_HEIGHT,
                    fill="#1B1C1F", outline="#0E0F11",
                )
                self._rects[midi] = rect

        self._refresh_colours()

    def _on_click(self, event) -> None:
        # Walk the stack from the top down and take the first item that is
        # actually a key. Reading only the topmost item made the note-name
        # labels swallow the click: the text sits above the white key it
        # belongs to, is not in the key table, and the click was dropped.
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if not items:
            return
        by_id = {rect: midi for midi, rect in self._rects.items()}
        for item in reversed(items):
            midi = by_id.get(item)
            if midi is None:
                continue        # a label, not a key
            if midi in self.selected:
                self.selected.remove(midi)
            else:
                self.selected.append(midi)
            self._refresh_colours()
            return

    def _refresh_colours(self) -> None:
        for midi, rect in self._rects.items():
            is_black = midi % 12 in self.BLACK_PATTERN
            if midi in self.selected:
                self.canvas.itemconfig(rect, fill=OK_GREEN)
            else:
                self.canvas.itemconfig(rect, fill="#1B1C1F" if is_black else "#F2F2F0")

        if self.selected:
            names = ", ".join(note_name(m) for m in sorted(self.selected))
            self.label.configure(text=trf("{selected} notas: {names}",
                                          selected=len(self.selected),
                                          names=names))
        else:
            self.label.configure(text=tr("Ninguna nota seleccionada"))

    def get_pitch_classes(self) -> List[int]:
        return [m % 12 for m in sorted(self.selected)]

    def clear(self) -> None:
        self.selected.clear()
        self._refresh_colours()


def _listed(items: Sequence[str]) -> str:
    """«a, b o c», que es como se enumera en castellano."""
    items = list(items)
    if len(items) < 2:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} o {items[-1]}"


class Tooltip:
    """
    Hover explanation for a widget.

    Rules like "quintas paralelas" or "solapamiento" mean nothing to someone
    who has not studied counterpoint, and the switch labels have no room to
    explain themselves. The tip appears next to the control after a short
    delay so it does not flicker while the pointer crosses the panel.
    """

    DELAY_MS = 350

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.window: Optional[tk.Toplevel] = None
        self.timer: Optional[str] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.timer = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self.timer is not None:
            try:
                self.widget.after_cancel(self.timer)
            except Exception:      # noqa: BLE001 - widget may be gone already
                pass
            self.timer = None

    def _show(self) -> None:
        if self.window is not None:
            return
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 12
            y = self.widget.winfo_rooty() - 4
        except Exception:          # noqa: BLE001
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self.window, background="#15161A",
                         highlightbackground=ACCENT, highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=tr(self.text), background="#15161A", foreground="#E4E6EA",
                 font=scaled(("Segoe UI", 10)), wraplength=330, justify="left",
                 padx=10, pady=8).pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


class LabelledSlider(ctk.CTkFrame):
    """A slider with its end labels pinned under its actual ends.

    Packing the two captions into a separate frame let them drift: the right
    one ended up wherever the frame happened to end, not under the end of the
    track. A three-column grid with the slider spanning it keeps them put.
    """

    def __init__(self, master, low_text: str, high_text: str,
                 from_: float, to: float, value: float, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.slider = ctk.CTkSlider(self, from_=from_, to=to,
                                    progress_color=ACCENT, button_color=ACCENT,
                                    button_hover_color=ACCENT_HOVER)
        self.slider.set(value)
        self.slider.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(self, text=tr(low_text), font=FONT_SMALL,
                     text_color=TEXT_MUTED, anchor="w"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ctk.CTkLabel(self, text=tr(high_text), font=FONT_SMALL,
                     text_color=TEXT_MUTED, anchor="e"
                     ).grid(row=1, column=1, sticky="e", pady=(2, 0))

    def get(self) -> float:
        return self.slider.get()

    def set(self, value: float) -> None:
        self.slider.set(value)


class FlatButton(tk.Label):
    """
    Un botón chico dibujado con tkinter pelado.

    Un ``CTkButton`` no es una etiqueta con un borde: es un marco con un
    canvas adentro donde se dibuja el rectángulo redondeado, y construirlo
    cuesta unos 3 ms. En casi toda la interfaz eso da lo mismo --- hay tres o
    cuatro botones por pantalla ---, pero la pantalla de acordes pone tres
    por cada casilla y las casillas van con los compases: a 64 compases son
    384 botones y algo más de un segundo de ventana congelada sólo en ellos.
    Medida, la misma cantidad de ``tk.Label`` cuesta nueve veces menos.

    Es el mismo criterio, y por el mismo motivo, que el de las filas del
    listado de logros. Lo que se pierde es la esquina redondeada, que en un
    botón de 26 px de alto no se distingue de una recta.

    Habla el vocabulario de ``CTkButton`` ---``configure(text=,
    border_color=, text_color=, state=)``--- a propósito: quien lo use no
    tiene que enterarse de que por dentro es otra cosa, y el candado se sigue
    prendiendo y apagando desde donde siempre.
    """

    def __init__(self, master, text: str, command, *, width: int = 3,
                 font=None, border: str = TEXT_MUTED, hover: str = SURFACE,
                 background: str = SURFACE_LIGHT):
        # `pady=0` y el borde de un píxel dejan la fila a la misma altura que
        # tenía con `CTkButton(height=26)`. Un `tk.Label` mide su alto en
        # líneas de texto, no en píxeles, así que la única manera de igualarlo
        # es no agregarle relleno vertical.
        super().__init__(master, text=tr(text), font=font or FONT_SMALL,
                         fg=TEXT_NORMAL, bg=background, width=width,
                         pady=0, highlightthickness=1,
                         highlightbackground=border, highlightcolor=border,
                         cursor="hand2")
        self._command = command
        self._rest_bg = background
        self._hover_bg = hover
        self.bind("<Button-1>", self._clicked, add="+")
        self.bind("<Enter>", self._entered, add="+")
        self.bind("<Leave>", self._left, add="+")

    # -- lo que hacía `command` y `hover_color` --------------------------------

    def _clicked(self, _event=None) -> None:
        # `state` es la misma llave que usaba el `CTkButton`, así que
        # `configure(state="disabled")` sigue apagándolo. Un `tk.Label`
        # deshabilitado se pone gris pero igual recibe el clic, así que hay
        # que preguntarlo acá.
        if str(self.cget("state")) == "disabled":
            return
        if self._command is not None:
            self._command()

    def _entered(self, _event=None) -> None:
        if str(self.cget("state")) != "disabled":
            self.configure(bg=self._hover_bg)

    def _left(self, _event=None) -> None:
        self.configure(bg=self._rest_bg)

    # -- el vocabulario de customtkinter ---------------------------------------

    def configure(self, cnf=None, **kwargs):
        """Traducir los nombres de opción de ``CTkButton`` a los de ``tk``."""
        if cnf:
            kwargs.update(cnf)
        if "border_color" in kwargs:
            colour = kwargs.pop("border_color")
            kwargs["highlightbackground"] = colour
            kwargs["highlightcolor"] = colour
        if "text_color" in kwargs:
            kwargs["fg"] = kwargs.pop("text_color")
        if "fg_color" in kwargs:
            # El fondo en reposo cambia con él: si no, el primer <Leave>
            # devolvería el color viejo y se desharía solo.
            self._rest_bg = kwargs["fg_color"]
            kwargs["bg"] = kwargs.pop("fg_color")
        return super().configure(**kwargs)

    config = configure


class FlatLabel(tk.Label):
    """
    Un texto chico dibujado con tkinter pelado.

    Un ``CTkLabel`` tampoco es una etiqueta: es un marco con un canvas
    adentro donde se dibuja un rectángulo redondeado --- del color del padre,
    o sea invisible --- y encima la etiqueta de verdad. En la pantalla de
    acordes hay cuatro por compás y los compases los elige el usuario: a 32
    compases son 128 rectángulos redondeados que nadie ve. Medido, dibujar
    los 708 que tenía esa pantalla costaba 497 ms de los 896 que tardaba en
    armarse.

    Es el mismo criterio que `FlatButton` y que las filas del listado de
    logros, y acá no se pierde ni la esquina redondeada: no había ninguna que
    ver.

    Habla ``configure(text_color=)`` como un ``CTkLabel`` a propósito: los
    once lugares que le cambian el color al estado de una casilla siguen
    diciéndolo igual y no tienen que enterarse de que por dentro es otra cosa.
    """

    def __init__(self, master, *, text: str = "", font=None,
                 text_color: str = TEXT_NORMAL,
                 background: str = SURFACE_LIGHT, width: int = 0,
                 anchor: str = "w"):
        super().__init__(master, text=tr(text), font=font or FONT_SMALL,
                         fg=text_color, bg=background, width=width,
                         anchor=anchor, padx=0, pady=0)

    def configure(self, **kwargs):
        colour = kwargs.pop("text_color", None)
        if colour is not None:
            kwargs["fg"] = colour
        return super().configure(**kwargs)

    config = configure


class DurationPicker(tk.Label):
    """
    El selector de duración de una casilla de acorde.

    Un ``CTkOptionMenu`` construye **su propio menú desplegable** ---un
    ``tk.Menu`` con las diez duraciones adentro--- además del marco y el
    canvas donde se dibuja. Medido dentro de la pantalla real, eso son 27 ms
    por casilla y el 71% de lo que tardaba en aparecer la pantalla de
    acordes: a 64 compases, 3,5 de los 4,9 segundos.

    Acá el menú es **uno solo para toda la pantalla**. Se arma la primera vez
    que alguien abre un desplegable y se le vuelven a apuntar los comandos al
    selector que lo pidió, así que abrir el de la casilla 40 cuesta lo mismo
    que abrir el de la primera y crear una casilla no cuesta ningún menú.

    Habla el pedazo de la interfaz de ``CTkOptionMenu`` que el resto del
    programa usa ---``get()``, ``set()`` y un ``command`` que se dispara al
    elegir--- con la misma semántica: ``set()`` **no** dispara el comando,
    igual que en el original, porque se lo llama al construir la casilla y
    ahí no hay nada que revalidar todavía.
    """

    #: El menú compartido, colgado del toplevel: una fila se destruye cada vez
    #: que la pantalla se redibuja y un menú colgado de ella se iría con ella.
    _MENU_ATTR = "_duration_menu_shared"

    #: La flecha que lo delata como desplegable. Va en el texto y no en un
    #: widget aparte: un segundo widget por casilla es justamente lo que esta
    #: clase existe para no tener. Por eso el valor elegido se guarda aparte
    #: de lo que se muestra --- `get()` devuelve el valor, no el rótulo.
    CARET = "  ▾"

    def __init__(self, master, values: Sequence[str], *, width: int = 19,
                 command=None, background: str = SURFACE):
        self._values = list(values)
        self._command = command
        self._value = values[0] if values else ""
        super().__init__(master, text=tr(self._value) + self.CARET,
                         font=FONT_SMALL, fg=TEXT_NORMAL, bg=background,
                         width=width, anchor="w", padx=8, pady=0,
                         highlightthickness=1, highlightbackground=background,
                         cursor="hand2")
        self.bind("<Button-1>", self._open, add="+")

    # -- la interfaz que usa el resto del programa ----------------------------

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        """Elegir sin avisar. Como en ``CTkOptionMenu``, no dispara nada."""
        self._value = value
        self.configure(text=tr(value) + self.CARET)

    # -- el desplegable --------------------------------------------------------

    def _shared_menu(self) -> tk.Menu:
        top = self.winfo_toplevel()
        menu = getattr(top, self._MENU_ATTR, None)
        if menu is None or not menu.winfo_exists():
            menu = tk.Menu(top, tearoff=0, bg=SURFACE_LIGHT, fg=TEXT_NORMAL,
                           activebackground=ACCENT, activeforeground="#FFFFFF",
                           bd=0, font=FONT_SMALL)
            setattr(top, self._MENU_ATTR, menu)
        return menu

    def _open(self, event=None) -> None:
        if str(self.cget("state")) == "disabled":
            return
        menu = self._shared_menu()
        # Se vacía y se vuelve a llenar apuntando a *este* selector. Son diez
        # entradas: cuesta menos que haber creado el menú una vez por casilla,
        # y encima sólo se paga cuando alguien lo abre.
        menu.delete(0, "end")
        for value in self._values:
            # El rótulo va traducido y el comando lleva el valor de
            # siempre: lo que viaja es el castellano.
            menu.add_command(label=tr(value),
                             command=lambda v=value: self._chose(v))
        try:
            menu.tk_popup(self.winfo_rootx(),
                          self.winfo_rooty() + self.winfo_height())
        finally:
            menu.grab_release()

    def _chose(self, value: str) -> None:
        self.set(value)
        if self._command is not None:
            self._command(value)


def descendants(widget) -> List:
    """
    El widget y todo lo que cuelga de él, para atar eventos de una.

    Los hijos se piden por ``tkinter.Misc.winfo_children`` y no por el método
    del widget: ``CTkFrame`` sobreescribe ``winfo_children`` para esconder su
    propio canvas de fondo --- lo considera parte del marco y no un hijo ---
    y ese canvas es justamente toda la superficie visible de una tarjeta. Con
    la versión filtrada quedaban atados los textos pero no el fondo, así que
    un clic en el aire de la tarjeta no hacía nada y parecía que la selección
    fallaba de a ratos.
    """
    found = [widget]
    for child in tk.Misc.winfo_children(widget):
        found.extend(descendants(child))
    return found


def bind_deeply(widgets, sequence: str, callback) -> None:
    """
    Atar un evento a un panel entero: fondo, textos e iconos.

    Sólo se ata sobre los widgets de tkinter, nunca sobre los de
    customtkinter. Un `CTkLabel` no es una ventana: es un marco con un
    canvas y una etiqueta adentro, y su `bind` redirige a esos dos. Como el
    recorrido de `descendants` ya los visita por su cuenta, atar también en
    el envoltorio dejaba dos callbacks sobre la misma ventana y un clic
    disparaba dos veces --- que en una tarjeta de modo no se notaba, pero en
    la de logros apilaba la pantalla dos veces y "Volver" hacía falta
    apretarlo dos veces para salir.
    """
    for widget in widgets:
        if type(widget).bind is not tk.Misc.bind:
            continue
        widget.bind(sequence, callback, add="+")


def unless_professional(method):
    """
    Saltear un enganche de las visitas o del sendero en el modo profesional.

    Va en los métodos que **abren** algo ---una escena, un cartel del
    relato, el botón dorado---, no en los que anotan: lo que el usuario
    hace se sigue contando igual, y al apagar el modo profesional lo que le
    tocaba lo está esperando.
    """
    def wrapper(self, *args, **kwargs):
        if self.settings.get("professional"):
            return None
        return method(self, *args, **kwargs)
    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


def unbind_one(widget, sequence: str, funcid: Optional[str]) -> None:
    """
    Desatar un enlace hecho con ``add="+"`` y dejar los demás donde están.

    Hasta Python 3.12, ``unbind(secuencia, funcid)`` borra **todos** los
    enlaces de la secuencia y no sólo el pedido. Sobre la ventana eso se
    llevaba puesto el `<Configure>` de customtkinter, que es con el que la
    ventana sigue su propio tamaño. Se hace a mano lo que hace 3.13: sacar
    del guion de Tcl sólo los renglones de este enlace y soltar su comando.
    """
    if not funcid:
        return
    try:
        script = str(widget.tk.call("bind", widget._w, sequence))
        mine = 'if {"[%s ' % funcid
        kept: List[str] = []
        for line in script.split("\n"):
            if line.startswith(mine):
                # Y el renglón en blanco que Tk pone antes al sumar con
                # "+": si no, el guion queda distinto del que había.
                if kept and not kept[-1]:
                    kept.pop()
                continue
            kept.append(line)
        keep = "\n".join(kept)
        widget.tk.call("bind", widget._w, sequence,
                       keep if keep.strip() else "")
        widget.deletecommand(funcid)
    except tk.TclError:
        pass


class Hoverable:
    """
    Mixin: saber si el mouse está sobre un panel entero, hijos incluidos.

    Tk manda ``<Leave>`` cada vez que el puntero entra a un hijo, porque cada
    hijo es una ventana distinta. Atado sin más, cruzar una tarjeta la hacía
    parpadear entre los dos estados. Acá la salida se confirma un cuadro
    después preguntando dónde quedó el puntero de verdad: si sigue adentro
    de alguno de los descendientes, no salió.
    """

    def _watch_hover(self, widgets) -> None:
        self._hovered = False
        bind_deeply(widgets, "<Enter>", self._entered)
        bind_deeply(widgets, "<Leave>", self._left)

    def _entered(self, _event=None) -> None:
        if not self._hovered:
            self._hovered = True
            self._paint()

    def _left(self, _event=None) -> None:
        try:
            self.after(24, self._confirm_left)
        except tk.TclError:
            pass

    def _confirm_left(self) -> None:
        try:
            if not self.winfo_exists():
                return
            under = self.winfo_containing(self.winfo_pointerx(),
                                          self.winfo_pointery())
        except (tk.TclError, KeyError):
            under = None
        node = under
        while node is not None:
            if node is self:
                return
            node = getattr(node, "master", None)
        if self._hovered:
            self._hovered = False
            self._paint()


class Card(ctk.CTkFrame, Hoverable):
    """A selectable card, used for the mode and genre choosers.

    Deliberately large: these two screens ask the only two questions that
    change everything downstream, and they were reading like a cramped list
    of radio buttons.

    Cada tarjeta trae su propio color, y ese color es el mismo que después
    tiñe el riel de progreso: elegir "Armonizador" no cambia sólo el texto
    de la pantalla siguiente, cambia el verde del que se pinta el resto del
    recorrido. Es lo que saca a la interfaz del azul único que tenía.

    Los cuatro colores que la tarjeta anima -- borde, fondo, fondo del icono
    y tinta del icono -- se mueven juntos, así que reposo, mouse encima y
    elegida son tres puntos de un mismo trayecto y nunca hay un salto.
    """

    def __init__(self, master, title: str, body: str, command, *,
                 accent: Optional[str] = None, icon: str = "◆",
                 tagline: str = "", subtitle: str = "", steps=(), points=(),
                 wraplength: int = 300, flag: str = "",
                 picture: Optional[Callable[[tk.Canvas, int], None]] = None,
                 picture_height: int = 0, badge: bool = True,
                 serif: bool = False, **kwargs):
        # Resuelto acá y no en la firma: el valor por defecto de un argumento
        # se congela al definir la clase, y `ACCENT` cambia con el modo.
        accent = accent or ACCENT
        super().__init__(master, fg_color=SURFACE_LIGHT, corner_radius=16,
                         border_width=2, border_color=BORDER_SOFT, **kwargs)
        self.command = command
        self.accent = accent
        self.selected = False
        self._hovered = False

        head = ctk.CTkFrame(self, fg_color="transparent")
        # Las de dibujo, con menos aire arriba y abajo del título: son seis
        # en la pantalla inicial, con el estante y el sendero debajo, y en la
        # ventana más chica cada renglón cuenta.
        head.pack(fill="x", padx=20,
                  pady=(16, 6) if picture is not None else (20, 10))
        # Las tarjetas con dibujo no llevan icono: el dibujo ya dice qué hay
        # adentro, y el cuadradito con un signo era lo que hacía que todas
        # las tarjetas del programa se vieran iguales.
        self.badge = None
        if badge:
            self.badge = ctk.CTkLabel(head, text=icon, width=44, height=44,
                                      corner_radius=13,
                                      fg_color=mix(SURFACE_LIGHT, accent, 0.16),
                                      text_color=accent, font=scaled(FONT_ICON))
            self.badge.pack(side="left")

        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left", padx=(13 if badge else 0, 0), fill="x",
                   expand=True)
        titles = ctk.CTkFrame(names, fg_color="transparent")
        titles.pack(anchor="w", fill="x")
        self.title_label = ctk.CTkLabel(
            titles, text=tr(title),
            font=scaled(("Georgia", 20, "bold") if serif
                        else ("Segoe UI Semibold", 19)),
            anchor="w", justify="left")
        self.title_label.pack(side="left")
        # El aviso de que algo todavía se está haciendo. Va pegado al
        # nombre y adentro de la tarjeta: dicho en otro lado ---en la
        # pantalla siguiente, en una nota al pie--- se lee después de haber
        # elegido, que es justo cuando ya no sirve de aviso.
        if flag:
            ctk.CTkLabel(titles, text=tr(flag), font=scaled(("Segoe UI", 10)),
                         text_color=accent,
                         fg_color=mix(SURFACE_LIGHT, accent, 0.22),
                         corner_radius=6, width=46, height=18
                         ).pack(side="left", padx=(8, 0))
        self.subtitle_label = None
        if subtitle:
            self.subtitle_label = ctk.CTkLabel(
                names, text=tr(subtitle), font=FONT_SMALL, text_color=accent,
                anchor="w", justify="left")
            self.subtitle_label.pack(anchor="w", pady=(1, 0))

        # El dibujo va en un lienzo de Tk y no en uno de customtkinter: no
        # tiene fondo transparente, así que `_apply` le copia el de la
        # tarjeta en cada cuadro de la animación.
        #
        # Se vuelve a dibujar con el ancho que le toca de verdad: el de
        # `wraplength` es el que se calculó al armar la pantalla, y con la
        # ventana agrandada o maximizada después el dibujo quedaba corto,
        # con media tarjeta vacía a la derecha. Cambiar lo dibujado no
        # cambia el tamaño del lienzo, así que redibujar en su `<Configure>`
        # no se realimenta.
        self.picture_canvas = None
        if picture is not None:
            canvas = tk.Canvas(self, width=wraplength + 20,
                               height=picture_height, highlightthickness=0,
                               bd=0, bg=SURFACE_LIGHT)
            drawn = [wraplength + 20]
            picture(canvas, drawn[0])
            self._picture, self._drawn = picture, drawn

            def redraw(event, canvas=canvas, drawn=drawn) -> None:
                if abs(event.width - drawn[0]) < 2:
                    return
                drawn[0] = event.width
                canvas.delete("all")
                picture(canvas, event.width)

            canvas.bind("<Configure>", redraw, add="+")
            canvas.pack(fill="x", padx=20, pady=(2, 6 if body else 14))
            self.picture_canvas = canvas

        self.body_label = ctk.CTkLabel(self, text=tr(body),
                                       font=scaled(("Segoe UI", 13)),
                                       text_color=TEXT_MUTED,
                                       wraplength=wraplength,
                                       justify="left", anchor="w")
        if body:
            self.body_label.pack(anchor="w", fill="x", padx=20,
                                 pady=(0, 14 if picture is not None else 12))

        # Los pasos van numerados y las características con viñeta: en un caso
        # el orden significa algo -- es lo que la pantalla va a ir pidiendo --
        # y en el otro no, y numerar una lista sin orden sugiere una secuencia
        # que no existe.
        listed = ([(str(n), text) for n, text in enumerate(steps, start=1)]
                  + [("·", text) for text in points])
        for position, (marker, text) in enumerate(listed, start=1):
            line = ctk.CTkFrame(self, fg_color="transparent")
            line.pack(fill="x", padx=20,
                      pady=(0, 18 if position == len(listed) else 8))
            ctk.CTkLabel(line, text=marker, width=16, anchor="w",
                         text_color=accent,
                         font=scaled(("Segoe UI Semibold", 11))).pack(side="left")
            ctk.CTkLabel(line, text=tr(text), font=scaled(("Segoe UI", 11)),
                         text_color=TEXT_MUTED, anchor="w", justify="left",
                         wraplength=max(120, wraplength - 26)).pack(side="left")

        self.tag_label = None
        if tagline:
            self.tag_label = ctk.CTkLabel(
                self, text=tr(tagline), font=scaled(("Segoe UI", 10)),
                text_color=mix(TEXT_MUTED, accent, 0.5), wraplength=wraplength,
                justify="left", anchor="w")
            self.tag_label.pack(anchor="w", fill="x", padx=20, pady=(0, 18))

        self._now = list(self._targets())
        #: El fondo que está pintado ahora mismo, para no volver a pedirlo.
        self._fill_shown = SURFACE_LIGHT
        family = descendants(self)
        bind_deeply(family, "<Button-1>", lambda _event: self.command())
        self._watch_hover(family)
        try:
            self.configure(cursor="hand2")
        except (tk.TclError, ValueError):      # noqa: BLE001 - cosmetic only
            pass

    # -- estados ------------------------------------------------------------

    def redraw_picture(self) -> None:
        """Volver a dibujar el dibujo, para cuando cambió lo que muestra."""
        canvas = self.picture_canvas
        if canvas is None:
            return
        try:
            canvas.delete("all")
            self._picture(canvas, self._drawn[0])
        except tk.TclError:
            pass

    def _targets(self) -> Tuple[str, str, str, str]:
        """Borde, fondo, fondo del icono y tinta del icono, en este orden."""
        if self.selected:
            return (self.accent,
                    mix(SURFACE_LIGHT, self.accent, 0.10),
                    self.accent,
                    SURFACE)
        if self._hovered:
            return (mix(BORDER_SOFT, self.accent, 0.7),
                    SURFACE_RAISED,
                    mix(SURFACE_RAISED, self.accent, 0.34),
                    self.accent)
        return (BORDER_SOFT, SURFACE_LIGHT,
                mix(SURFACE_LIGHT, self.accent, 0.16), self.accent)

    def _apply(self, values) -> None:
        border, fill, badge_fill, badge_text = values
        # Nada que no haya cambiado. Cada `configure` de éstos es un
        # redibujado entero de customtkinter --- el del fondo, además,
        # propagado a la docena de hijos transparentes de la tarjeta --- y
        # con los colores cuantizados en pocos escalones la mayoría de los
        # cuadros de una animación piden exactamente lo que ya está puesto.
        if values == getattr(self, "_applied", None):
            return
        self._applied = tuple(values)
        try:
            # El fondo se pinta sólo cuando cambia de verdad. `configure(
            # fg_color=...)` cuesta unos 11 ms porque customtkinter lo
            # propaga a todos los hijos transparentes, que en una tarjeta son
            # una docena; el borde y el icono cuestan uno cada uno. Por eso
            # `_tween` mueve el fondo en tres escalones y el resto cuadro a
            # cuadro: a simple vista no se distingue, y la animación pasa de
            # costar casi 300 ms de CPU a costar unos 40.
            if fill != self._fill_shown:
                self.configure(fg_color=fill)
                self._fill_shown = fill
                if self.picture_canvas is not None:
                    self.picture_canvas.configure(bg=fill)
            self.configure(border_color=border)
            if self.badge is not None:
                self.badge.configure(fg_color=badge_fill,
                                     text_color=badge_text)
        except tk.TclError:
            pass

    def _tween(self, start, end, steps: int, period: int, delay: int = 0) -> None:
        """Ir de una tanda de colores a la otra, dejando `_now` en el final."""
        def frame(position: float) -> None:
            # Cuatro escalones, y los mismos para los cuatro colores. Antes
            # sólo el fondo iba a saltos y los otros tres se movían cuadro a
            # cuadro, con lo que cada cuadro seguía costando un redibujado;
            # cuantizados todos juntos, la animación pide cuatro repintados
            # en vez de ocho y a simple vista se ve igual. Con cinco
            # tarjetas en la pantalla inicial eso es medio segundo de
            # diferencia en la única pantalla que se ve al abrir.
            coarse = round(position * 3) / 3
            values = (mix(start[0], end[0], coarse),
                      mix(start[1], end[1], coarse),
                      mix(start[2], end[2], coarse),
                      mix(start[3], end[3], coarse))
            self._apply(values)
            # Anotado en cada cuadro y no sólo al final: si el mouse entra y
            # sale a mitad de camino, la animación siguiente arranca de los
            # colores que hay en pantalla y no de los que había antes.
            self._now = list(values)

        animate(self, frame, steps=steps, period=period, delay=delay)

    def _paint(self, animated: bool = True) -> None:
        end = self._targets()
        if not animated:
            self._now = list(end)
            self._apply(end)
            return
        self._tween(tuple(self._now), end, steps=6, period=18)

    def set_selected(self, value: bool, animated: bool = True) -> None:
        """
        Marcar o desmarcar. Sin animar al armar la pantalla.

        Cada cuadro es un `configure(fg_color=...)` sobre el marco, y
        customtkinter lo propaga a todos los hijos transparentes --- son una
        docena por tarjeta --- así que un cuadro cuesta unos 10 ms. Animar la
        selección inicial de las tres tarjetas costaba unos 200 ms de más
        cada vez que se dibujaba la pantalla, para una transición que nadie
        ve porque arranca y termina en el mismo estado.
        """
        self.selected = value
        self._paint(animated=animated)

    def reveal(self, delay: int = 0) -> None:
        """
        Aparecer desde el fondo de la ventana, con retardo.

        Llamada con retardos escalonados, las tarjetas entran en cascada en
        vez de aparecer las tres de golpe. Es lo único que se anima al
        cambiar de pantalla: mover el layout en cada cuadro obliga a Tk a
        recalcularlo entero y se ve peor que no animar.
        """
        end = self._targets()
        # El fondo no entra en la aparición: arranca donde termina. Pintarlo
        # cuesta siete milésimas por cuadro ---customtkinter lo propaga a la
        # docena de hijos transparentes de la tarjeta--- contra una del
        # borde y media del icono, y el trecho que recorría era de dos
        # grises casi iguales. Con cinco tarjetas en la pantalla inicial eso
        # era un cuarto de segundo de aparición que se leía como demora.
        start = (SURFACE, end[1], SURFACE, SURFACE)
        self._now = list(start)
        self._apply(start)
        self._tween(start, end, steps=4, period=20, delay=delay)


# ---------------------------------------------------------------------------
# Logros
# ---------------------------------------------------------------------------

def shimmer_while(widget, alive, period: int = 110,
                  option: str = "border_color", off: str = BORDER_SOFT) -> None:
    """
    Un brillo dorado que se enciende y se apaga según una condición.

    ``start_shimmer`` no se puede parar: brilla hasta que el widget muere. Acá
    hace falta lo contrario --- una cadencia deja de ser esa cadencia en
    cuanto se le cambia una letra --- así que la condición se vuelve a
    preguntar en cada cuadro y el widget se apaga solo cuando deja de
    cumplirse.

    **El ``configure`` se hace sólo cuando el color cambia de verdad.** Antes
    se hacía siempre, y en un ``CTkEntry`` eso no es escribir un atributo: es
    volver a dibujar el rectángulo redondeado entero en su propio canvas. Este
    brillo se engancha a *cada* casilla de acorde de la pantalla, así que el
    costo iba con la cantidad de compases: con 32 compases eran 64 casillas
    redibujándose nueve veces por segundo, y a partir de unas 80 el bucle de
    Tk ya no lograba drenar la cola --- la pantalla no tardaba en aparecer,
    directamente no aparecía. Medido: 32 compases pasaban de 4 s a 32 s con
    un sendero abierto, y 40 no terminaban nunca.

    Guardando el último color aplicado, las casillas apagadas ---que son
    todas menos las dos o tres de la cadencia--- pagan un ``configure`` la
    primera vez y ninguno más.
    """
    state = {"index": 0, "shown": None}

    def step() -> None:
        try:
            if not widget.winfo_exists():
                return
            if alive():
                colour = GOLD_SHADES[state["index"] % len(GOLD_SHADES)]
            else:
                colour = off
            if colour != state["shown"]:
                widget.configure(**{option: colour})
                state["shown"] = colour
            state["index"] += 1
            widget.after(period, step)
        except tk.TclError:
            return

    step()


def start_shimmer(widget, shades=None, period: int = 90,
                  option: str = "text_color", offset: int = 0) -> None:
    """
    Recorrer una paleta en el color de un texto, en bucle.

    Se reprograma sola mientras el widget siga existiendo y se apaga sin
    ruido en cuanto deja de existir, así que cerrar la ventana que lo
    contiene alcanza para pararla: no hay que acordarse de cancelar nada.

    ``option`` es el nombre de la opción de color: ``text_color`` en un
    widget de customtkinter y ``fg`` en uno de tkinter pelado, que es lo que
    usan las filas del listado de logros.

    ``offset`` corre el punto de la paleta por donde arranca. Una fila de
    widgets con un desfasaje por posición brilla como una ola que la
    recorre, en vez de prenderse y apagarse toda junta --- que es lo que
    pasa cuando todos empiezan en el mismo color.
    """
    palette = shades or GOLD_SHADES
    state = {"index": offset}

    def step() -> None:
        try:
            if not widget.winfo_exists():
                return
            widget.configure(
                **{option: palette[state["index"] % len(palette)]})
            state["index"] += 1
            widget.after(period, step)
        except tk.TclError:
            return

    step()


def handwritten_line(host, text: str, bg: str, wrap: int = 0):
    """
    La anotación a mano: una pluma y una línea manuscrita en oro.

    Es cómo este programa dice que algo se escribió solo, y aparece en dos
    lugares --- al pie del apartado recién abierto, sobre el papel del
    libro, y en el pie de la ventana. Los arma la misma función porque son
    la misma cosa dicha dos veces; con dos copias, la del pie iba a terminar
    pareciéndose a otra cosa.

    **No es un botón ni una tarjeta**: es una nota al margen, y cualquier
    borde o relleno la convierte en un control.
    """
    line = tk.Frame(host, bg=bg)
    tk.Label(line, text="🖋", font=scaled(("Segoe UI Symbol", 13)),
             bg=bg, fg=GOLD).pack(side="left", padx=(0, 8))
    label = tk.Label(line, text=tr(text), font=scaled(FONT_HAND + ("italic",)),
                     bg=bg, fg=GOLD, justify="left", anchor="w")
    if wrap:
        label.configure(wraplength=wrap)
    label.pack(side="left")
    return line


def star_polygon(cx: float, cy: float, outer: float, inner: float,
                 rotation: float = 0.0) -> List[float]:
    """Los diez puntos de una estrella de cinco puntas, lista para el canvas."""
    import math

    points: List[float] = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = rotation + math.pi / 2 + index * math.pi / 5
        points.append(cx + radius * math.cos(angle))
        points.append(cy - radius * math.sin(angle))
    return points


class AchievementBanner(ctk.CTkFrame, Hoverable):
    """
    La tarjeta ancha de logros, debajo de las tres del modo.

    Horizontal a propósito: no es una cuarta opción de trabajo, es un
    resumen, y con la misma forma que las otras se leería como si eligiera
    algo.
    """

    def __init__(self, master, tracker: achievements.Tracker, command, **kwargs):
        super().__init__(master, fg_color=SURFACE_LIGHT, corner_radius=16,
                         border_width=2, border_color=BORDER_SOFT, **kwargs)
        self.command = command
        self._hovered = False
        earned = tracker.stars()
        done, total = tracker.total_progress()

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=(26, 10), pady=18)
        title = ctk.CTkLabel(left, text=tr("Logros"),
                             font=scaled(("Segoe UI Semibold", 21)),
                             anchor="w")
        title.pack(anchor="w")
        titles = tracker.titles()
        subtitle = ctk.CTkLabel(
            left,
            text=(" · ".join(trs(titles)) if titles
                  else trf("{done} de {total} conseguidos",
                           done=done, total=total)),
            font=scaled(("Segoe UI", 13)),
            text_color=GOLD if titles else TEXT_MUTED, anchor="w")
        subtitle.pack(anchor="w", pady=(4, 0))
        if titles:
            start_shimmer(subtitle)

        stars = ctk.CTkFrame(self, fg_color="transparent")
        stars.pack(side="right", padx=(10, 26), pady=18)
        row = ctk.CTkFrame(stars, fg_color="transparent")
        row.pack(anchor="e")
        for star in range(1, achievements.STAR_COUNT + 1):
            got = star <= earned
            ctk.CTkLabel(row, text="★" if got else "☆",
                         font=scaled(("Segoe UI", 26)),
                         text_color=GOLD if got else GOLD_DIM
                         ).pack(side="left", padx=3)
        progress = ctk.CTkLabel(
            stars,
            text=(trf("{done} de {total} conseguidos",
                      done=done, total=total) if tracker.titles()
                  else tr("Mirá qué te falta")),
            font=FONT_SMALL, text_color=TEXT_MUTED)
        progress.pack(anchor="e", pady=(4, 0))

        family = descendants(self)
        bind_deeply(family, "<Button-1>", lambda _event: self.command())
        self._watch_hover(family)
        self._now = list(self._targets())

    def _targets(self) -> Tuple[str, str]:
        if self._hovered:
            return (mix(BORDER_SOFT, GOLD, 0.55), SURFACE_RAISED)
        return (BORDER_SOFT, SURFACE_LIGHT)

    def _paint(self, animated: bool = True) -> None:
        end = self._targets()
        start = tuple(self._now)

        def frame(position: float) -> None:
            border, fill = (mix(a, b, position) for a, b in zip(start, end))
            try:
                self.configure(border_color=border, fg_color=fill)
            except tk.TclError:
                pass
            if position >= 1.0:
                self._now = list(end)

        animate(self, frame, steps=6, period=16)


class BookBanner(ctk.CTkFrame, Hoverable):
    """
    La tarjeta del libro de teoría, al lado de la de logros.

    Va con los colores del libro y no con el acento del modo: es lo único de
    la pantalla principal que no forma parte del trabajo, y conviene que se
    lea como otra cosa antes de leerla.
    """

    def __init__(self, master, written: int, total: int, fresh: int,
                 command, **kwargs):
        super().__init__(master, fg_color=PAPER, corner_radius=16,
                         border_width=2, border_color=RULE, **kwargs)
        self.command = command
        self._hovered = False

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=(26, 10), pady=18)
        ctk.CTkLabel(left, text=tr("Libro de teoría"),
                     font=scaled(("Georgia", 20)), text_color=INK,
                     anchor="w").pack(anchor="w")
        # Corto: la tarjeta pasó a medir media fila y el texto largo se
        # partía en tres renglones, que la dejaba más alta que la de logros
        # y desfasaba la fila entera.
        ctk.CTkLabel(
            left,
            text=tr("Armonía y contrapunto, desde cero."),
            font=scaled(("Georgia", 12)), text_color=INK_MUTED, anchor="w",
            justify="left").pack(anchor="w", pady=(4, 0))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=(10, 26), pady=18)
        if fresh:
            # La pluma sólo aparece cuando hay algo nuevo escrito: si
            # estuviera siempre, dejaría de querer decir nada.
            ctk.CTkLabel(right,
                         text=trf("🖋  {fresh} anotación nueva", fresh=fresh) if fresh == 1
                         else trf("🖋  {fresh} anotaciones nuevas", fresh=fresh),
                         font=scaled(("Segoe UI Semibold", 13)),
                         text_color=GOLD).pack(anchor="e")
        ctk.CTkLabel(right, text=trf("{written} de {total} apartados "
                                     "escritos",
                                     written=written, total=total),
                     font=FONT_SMALL, text_color=INK_FAINT
                     ).pack(anchor="e", pady=(4, 0))

        family = descendants(self)
        bind_deeply(family, "<Button-1>", lambda _event: self.command())
        self._watch_hover(family)
        self._now = list(self._targets())
        try:
            self.configure(cursor="hand2")
        except (tk.TclError, ValueError):      # noqa: BLE001 - cosmetic only
            pass

    def _targets(self) -> Tuple[str, str]:
        if self._hovered:
            return (mix(RULE, GOLD, 0.5), PAPER_EDGE)
        return (RULE, PAPER)

    def _paint(self, animated: bool = True) -> None:
        end = self._targets()
        start = tuple(self._now)

        def frame(position: float) -> None:
            border, fill = (mix(a, b, position) for a, b in zip(start, end))
            try:
                self.configure(border_color=border, fg_color=fill)
            except tk.TclError:
                pass
            if position >= 1.0:
                self._now = list(end)

        animate(self, frame, steps=6, period=18)


class Toast(ctk.CTkFrame):
    """
    El aviso de logro conseguido, arriba a la izquierda.

    Deliberadamente ``place``-ado sobre la ventana y sin ``grab_set``: no es
    un diálogo, no roba el foco y no tapa ningún control con el que se esté
    trabajando. Se va solo, y un clic lo saca antes.
    """

    WIDTH = 300
    LIFETIME_MS = 6500

    def __init__(self, master, achievement: achievements.Achievement,
                 on_close, heading_text: str = "", **kwargs):
        gold = achievement.legendary
        super().__init__(master, fg_color=SURFACE_LIGHT, corner_radius=10,
                         border_width=1,
                         border_color=GOLD if gold else ACCENT,
                         width=self.WIDTH, **kwargs)
        self.on_close = on_close
        self._closed = False
        colour = GOLD if gold else ACCENT

        # Más bajo que antes: el rótulo y las estrellas comparten renglón y
        # la descripción va en uno o dos. Cuatro avisos del alto viejo
        # tapaban media pantalla durante seis segundos.
        # El ancho lo fija un separador invisible y no el texto: si no, cada
        # aviso medía lo que su descripción y la pila quedaba despareja.
        tk.Frame(self, width=self.WIDTH - 4, height=1,
                 bg=SURFACE_LIGHT).pack()
        top = tk.Frame(self, bg=SURFACE_LIGHT)
        top.pack(fill="x", padx=12, pady=(9, 0))
        heading = tk.Label(
            top, text=tr(heading_text) or (tr("¡Logro completado!") if not gold
                                           else tr("¡Logro legendario!")),
            font=scaled(("Segoe UI Semibold", 10)), fg=colour,
            bg=SURFACE_LIGHT, anchor="w")
        heading.pack(side="left")
        if gold:
            start_shimmer(heading, option="fg")
        # La estrella sólo se anuncia cuando el aviso es de un logro de
        # verdad. El modo historia reusa este cartel para sus avisos, y ahí
        # un renglón que dijera "Legendario" mentiría.
        if achievement.key:
            tk.Label(top, text=tr(achievement.star_label),
                     font=scaled(("Segoe UI", 10)), bg=SURFACE_LIGHT,
                     fg=GOLD if gold or achievement.star else TEXT_MUTED
                     ).pack(side="right")

        tk.Label(self, text=tr(achievement.name),
                 font=scaled(("Segoe UI Semibold", 13)), fg=TEXT_NORMAL,
                 bg=SURFACE_LIGHT, anchor="w", justify="left",
                 wraplength=self.WIDTH - 28).pack(anchor="w", padx=12,
                                                  pady=(1, 0))
        # La descripción de un legendario va en itálica y no explica nada:
        # es parte del logro que no se sepa cómo se consiguió.
        tk.Label(self, text=tr(achievements.plain(achievement.description)),
                 font=scaled(("Segoe UI", 10, "italic")) if gold
                 else scaled(("Segoe UI", 10)),
                 fg=TEXT_MUTED, bg=SURFACE_LIGHT, wraplength=self.WIDTH - 28,
                 justify="left", anchor="w").pack(anchor="w", padx=12,
                                                  pady=(1, 10))

        for widget in descendants(self):
            widget.bind("<Button-1>", lambda _event: self.close())
        self.after(self.LIFETIME_MS, self.close)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.place_forget()
            self.destroy()
        except tk.TclError:
            pass
        self.on_close(self)


# ---------------------------------------------------------------------------
# El tutorial
# ---------------------------------------------------------------------------

#: Los pasos, en orden. ``screen`` es el índice del carrusel donde tiene que
#: estar parado el recorrido; ``target`` devuelve el widget a resaltar, o
#: None para un paso sin foco, centrado en la pantalla.
#:
#: El texto está escrito para alguien que no estudió música: nada se da por
#: sabido y ninguna frase usa una palabra que no se haya explicado antes.
TUTORIAL_STEPS: Tuple[dict, ...] = (
    dict(screen=0, target=None,
         title="Qué hace ChordWeaver",
         body="Una progresión de acordes dice qué notas suenan juntas, pero "
              "no qué voz canta cada una. ChordWeaver reparte las notas de "
              "cada acorde entre las voces para que se muevan lo menos "
              "posible y no choquen entre sí.\n\n"
              "Este recorrido dura un minuto. Podés saltearlo cuando "
              "quieras."),
    dict(screen=0, target=lambda app: app.mode_cards["manual"],
         title="Organizador",
         body="Para cuando ya tenés la progresión escrita en cifrado, como C, "
              "Am, F, G. El programa no cambia los acordes ni su orden. Sólo "
              "decide qué nota canta cada voz."),
    dict(screen=0, target=lambda app: app.mode_cards["random"],
         title="Generador",
         body="Para cuando no tenés nada todavía. Elegís la tonalidad y "
              "cuánto se puede arriesgar, y el programa inventa la progresión "
              "y la escribe. Si nunca escribiste armonía, conviene empezar "
              "por acá."),
    dict(screen=0, target=lambda app: app.mode_cards["harmonise"],
         title="Armonizador",
         body="Para cuando tenés una melodía. La escribís en el pentagrama, "
              "decís qué voz la canta y el programa busca los acordes y "
              "escribe las otras voces."),
    dict(screen=0, target=lambda app: app.tool_row,
         title="Herramientas",
         body="Tres lugares que no componen nada. El experimentador desarma "
              "una nota en sus armónicos, el analizador lee una partitura "
              "que traés y la escuelita te enseña con ejercicios que corrige "
              "el analizador."),
    dict(screen=0, target=lambda app: app.achievement_banner,
         title="Logros",
         body="Se desbloquean solos mientras trabajás, muchas veces por algo "
              "que hiciste sin darte cuenta. Valen de una a tres estrellas "
              "según la dificultad."),
    dict(screen=0, target=lambda app: app.book_banner,
         title="Libro de teoría",
         body="Si algo no se entiende, ahí está explicado desde cero, desde "
              "qué es un acorde hasta por qué una cadencia suena a final. Se "
              "va completando a medida que usás el programa."),
    dict(screen=1, target=lambda app: app.genre_cards["classical"],
         title="Barroco",
         body="El estilo decide cómo se pasa de un acorde al siguiente. Los "
              "acordes no cambian.\n\n"
              "El barroco es el lenguaje de Bach y el más estricto de los "
              "tres. Prohíbe que dos voces se muevan en paralelo a ciertas "
              "distancias y premia que vayan en direcciones contrarias. Si "
              "estás empezando, es donde mejor se oye cuando algo sale mal."),
    dict(screen=1, target=lambda app: app.genre_cards["gregorian"],
         title="Gregoriano",
         body="Es anterior a la armonía tal como la conocemos. Las voces se "
              "mueven casi siempre a la nota vecina y evitan el tritono, el "
              "intervalo más tenso. Las paralelas sí se permiten, porque el "
              "canto medieval se basaba en ellas."),
    dict(screen=1, target=lambda app: app.genre_cards["jazz"],
         title="Jazz",
         body="Lo que importa es cómo pasan al acorde siguiente las dos notas "
              "que definen el color de cada acorde. El programa las conecta "
              "por el camino más corto y permite cosas que el barroco "
              "prohíbe. Los acordes son más densos y suenan más modernos."),
    dict(screen=1, target=lambda app: app.rail,
         title="La barra de progreso",
         body="Son siete pantallas: modo, estilo, voces, compases, acordes, "
              "reglas y resultado. La barra se llena a medida que avanzás y "
              "toma el color del modo que elegiste."),
    dict(screen=1, target=lambda app: app.footer,
         title="Avanzar, volver y configurar",
         body="«Siguiente» avanza y «Atrás» vuelve sin perder nada de lo que "
              "cargaste.\n\n"
              "En el engranaje están la configuración, el tamaño de letra y "
              "el botón para volver a ver este tutorial."),
    dict(screen=0, target=None,
         title="Listo",
         body="Eso es todo para empezar. Ahora vamos a los logros, porque "
              "acabás de ganar el primero."),
)


# ---------------------------------------------------------------------------
# Las guías de pantalla
# ---------------------------------------------------------------------------
#
# El recorrido de arriba muestra dónde está cada cosa; éstas explican cómo se
# usa la pantalla en la que uno está parado. Se abren solas la primera vez que
# se llega a la pantalla donde cada modo hace su trabajo de verdad --- los
# acordes en el Organizador, el pentagrama en el Armonizador, las reglas en el
# Generador --- y no vuelven nunca más, salvo que se reinicie el tutorial
# desde el engranaje.
#
# Van sin ``screen``: una guía no puede mover el carrusel. El usuario está a
# mitad de un trabajo y llevarlo a otra pantalla para explicarle ésta sería
# pisarle lo que estaba haciendo. Ver `Tutorial.navigates`.
#
# Los blancos que puedan no existir --- una casilla de acorde, un interruptor
# que este estilo no ofrece --- no hacen falta protegerlos acá: `_target_box`
# los deja pasar y el paso se dibuja centrado.

#: El Organizador, en la pantalla donde se escribe la progresión.
CHORDS_GUIDE: Tuple[dict, ...] = (
    dict(target=None,
         title="Acá se escribe la progresión",
         body="Vos ponés los acordes y el programa decide qué nota canta cada "
              "voz y en qué octava. Los acordes y su orden no se tocan.\n\n"
              "Te muestro qué hace cada cosa en medio minuto. Podés "
              "omitirlo."),
    dict(target=lambda app: app.chord_rows[0]["entries"][0]["entry"],
         title="El cifrado va acá",
         body="Se escribe en cifrado americano. La letra es la nota de base "
              "(C es do, D re, E mi, F fa, G sol, A la, B si) y lo que sigue "
              "dice de qué tipo es el acorde.\n\n"
              "C es do mayor, Cm do menor, C7 lleva séptima, Cmaj7 séptima "
              "mayor y C/G es do mayor con el sol en el bajo. Mientras "
              "escribís, debajo aparecen las notas del acorde o qué está "
              "mal."),
    dict(target=lambda app: app.chord_rows[0]["entries"][0]["duration"],
         title="Cuánto dura cada uno",
         body="Al lado de cada acorde va su duración. Las opciones que "
              "empiezan con «Silencio» dejan ese lugar sin sonar, y el "
              "programa lo respeta."),
    dict(target=lambda app: app.chord_rows[0]["fill_label"],
         title="El compás tiene que cerrar exacto",
         body="Acá ves cuánto llevás puesto y cuánto entra. Si sobra o falta, "
              "no se puede escribir la partitura, porque ningún editor de "
              "música acepta un compás que no suma lo que dice su cifra.\n\n"
              "«+ acorde» agrega otro acorde al compás y la ✕ lo saca."),
    dict(target=lambda app: app.chord_rows[0]["entries"][0]["lock_button"],
         title="El candado fija las voces",
         body="Con el candado le decís qué nota canta cada voz en ese acorde, "
              "y el programa ya no lo cambia. Los acordes vecinos se acomodan "
              "alrededor del que fijaste."),
    dict(target=lambda app: app.chord_rows[0]["entries"][0]["piano_button"],
         title="El piano, para acordes sin nombre",
         body="El botón «piano» de cada casilla abre un teclado para armar el "
              "acorde nota por nota. Sirve para los que el cifrado no puede "
              "nombrar, como un acorde por cuartas o un cluster.\n\n"
              "Arriba a la izquierda, «Importar partitura» carga los acordes "
              "de un MusicXML con su ritmo."),
)

#: El Armonizador, en la pantalla del pentagrama y el piano.
MELODY_GUIDE: Tuple[dict, ...] = (
    dict(target=None,
         title="Acá se dibuja la melodía",
         body="En el Armonizador se parte de una melodía y no de acordes. Vos "
              "la escribís y el programa busca acordes que le queden, sin "
              "cambiarle ninguna nota.\n\n"
              "Te muestro qué hace cada cosa en medio minuto. Podés "
              "omitirlo."),
    dict(target=lambda app: app.staff,
         title="Click en el pentagrama",
         body="Cada click pone una nota donde apuntaste. El pentagrama está "
              "en clave de sol, así que la línea de abajo es mi y cuanto más "
              "arriba, más agudo.\n\n"
              "La nota respeta la armadura. Si la armadura tiene fa "
              "sostenido, un click en el fa escribe fa sostenido."),
    dict(target=lambda app: app.melody_controls,
         title="Qué figura estás escribiendo",
         body="Antes de hacer click, elegí acá cuánto dura la nota. La "
              "redonda es la más larga y la corchea la más corta. Las que "
              "dicen «c/punto» duran una vez y media.\n\n"
              "«Deshacer» (o Ctrl+Z) borra la última nota y «Borrar todo» "
              "empieza de cero. «Escuchar» toca lo que llevás escrito, "
              "todavía sin acordes."),
    dict(target=lambda app: app.melody_piano,
         title="O el piano, si el pentagrama te cuesta",
         body="Hace lo mismo que el click y agrega una nota al final de la "
              "línea, con la figura elegida arriba. Es más cómodo para las "
              "notas alteradas y las que quedan lejos del pentagrama."),
    dict(target=lambda app: app.mark_button,
         title="Las notas doradas llevan acorde",
         body="El programa pone los acordes en los tiempos fuertes y dora las "
              "notas que caen ahí. Las notas que quedan en el medio suenan "
              "sobre el acorde anterior.\n\n"
              "Para poner un acorde en otra nota, prendé «Marcar notas» y "
              "tocala, o hacele click derecho. Lo mismo sirve para sacar uno "
              "que sobra."),
    dict(target=lambda app: app.key_menu,
         title="Armadura, compás y voz",
         body="La armadura fija la tonalidad y qué notas van alteradas. El "
              "compás agrupa los tiempos y decide dónde caen los acordes.\n\n"
              "En «Mi voz es» elegís qué voz escribiste. Suele ser la más "
              "aguda, pero si la melodía va abajo elegí el bajo y el programa "
              "escribe las otras encima."),
)

#: El Generador, en la pantalla de la tonalidad: de dónde salen los acordes.
HARMONY_GUIDE: Tuple[dict, ...] = (
    dict(target=None,
         title="Acá se elige el material",
         body="En el Generador no escribís acordes. Elegís de dónde los puede "
              "sacar el programa.\n\n"
              "Todo arranca con lo que suele usar el estilo elegido, así que "
              "cambiando sólo la tonalidad ya sale algo que suena bien. Te "
              "muestro qué hace cada cosa. Podés omitirlo."),
    dict(target=lambda app: app.tonic_menu.master,
         title="Tonalidad y modo",
         body="La tónica es la nota que suena a casa, la que el oído espera "
              "al final. El modo dice qué escala se arma sobre ella, y de esa "
              "escala salen los siete acordes que puede usar el programa.\n\n"
              "Jónico es el mayor de siempre y eólico el menor. Los otros "
              "cinco cambian una o dos notas de la escala. El dórico suena a "
              "folk, el frigio a música española y el lidio a banda de "
              "sonido."),
    dict(target=lambda app: app.start_roman_entry.master,
         title="Con qué empieza y con qué termina",
         body="Se escriben en números romanos. I es el acorde de la tónica, V "
              "el del quinto grado y vi el del sexto. Las minúsculas son "
              "acordes menores.\n\n"
              "Empezar y terminar en I hace que la pieza suene cerrada. "
              "Terminar en V la deja abierta, como una pregunta. "
              "«Obligatorio» se cumple siempre, «Preferido» se pesa contra "
              "todo lo demás y «Libre» deja elegir al programa."),
    dict(target=lambda app: app.passing_density,
         title="Las notas de paso",
         body="Cuando una voz salta una tercera, queda una nota libre en el "
              "medio. La nota de paso la ocupa, y en vez de saltar de do a mi "
              "la voz hace do-re-mi.\n\n"
              "Elegí qué voces pueden usarlas y cuántas. Se agregan "
              "**después** de repartir las voces, sobre la solución ya "
              "elegida."),
    dict(target=lambda app: app.borrowed_panel,
         title="Los acordes prestados",
         body="Los siete grados de la escala son el material básico. Un "
              "intercambio modal trae un acorde del modo paralelo (el menor "
              "sobre la misma tónica, o al revés) sin cambiar de tonalidad.\n"
              "\nDe ahí salen muchos colores modernos, como un cuarto grado "
              "menor en una pieza mayor o un séptimo bemol antes del final. "
              "El deslizador de abajo regula cuánto los usa."),
    dict(target=lambda app: app.modulation_block,
         title="Modulaciones",
         body="Modular es pasar a otra tonalidad en el medio de la pieza y "
              "volver antes del final. A diferencia de un préstamo, por un "
              "rato la pieza gira alrededor de otra nota.\n\n"
              "Para ir y volver hace falta espacio, así que con menos de ocho "
              "compases queda desactivado. El deslizador de abajo regula "
              "cuánto se aleja."),
    dict(target=lambda app: app.harmony_slider,
         title="Cuánto manda el estilo",
         body="La progresión se arma pesando lo que pide el estilo y lo que "
              "le conviene al movimiento de las voces. Este deslizador decide "
              "cuánto pesa el estilo.\n\n"
              "Hacia «estricto» sale una progresión de manual, con cada "
              "función en su lugar. Hacia «flexible» aparecen giros que el "
              "estilo no usaría."),
)

#: El Generador, en la pantalla de reglas: la última antes de buscar.
PARAMETER_GUIDE: Tuple[dict, ...] = (
    dict(target=None,
         title="La última pantalla antes de buscar",
         body="Los acordes ya están. Acá elegís con qué criterio se reparten "
              "entre las voces.\n\n"
              "Todo arranca con los valores del estilo elegido, así que si no "
              "tocás nada igual sale bien. Te muestro qué hace cada cosa."),
    dict(target=lambda app: app.rules_panel,
         title="Reglas duras",
         body="Las reglas de la izquierda son duras. Si una está prendida, se "
              "descarta cualquier reparto que la rompa, aunque sea bueno en "
              "todo lo demás. Por eso una regla prendida nunca aparece rota "
              "en el resultado.\n\n"
              "Pasá el mouse por cada una para ver qué significa."),
    dict(target=lambda app: app.switch_widgets["forbid_parallel_fifths"],
         title="Por ejemplo, las quintas paralelas",
         body="Son dos voces a distancia de quinta que se mueven juntas en la "
              "misma dirección y mantienen esa distancia. Es la prohibición "
              "más famosa del contrapunto, porque las dos líneas dejan de "
              "oírse como dos y se funden en una.\n\n"
              "Apagarla no rompe nada. Hay estilos enteros que se basan en "
              "eso, como el gregoriano."),
    dict(target=lambda app: app.balance_slider,
         title="Balance",
         body="Todo lo que no es una regla dura se compara entre sí, y este "
              "deslizador decide el balance.\n\n"
              "Hacia la izquierda pesa que las voces se muevan lo menos "
              "posible, y el resultado sale suave y previsible. Hacia la "
              "derecha pesa el estilo (espaciado, movimiento contrario, "
              "tesitura), y las voces se mueven más a cambio de sonar más "
              "idiomáticas. En el medio pesan igual."),
    dict(target=lambda app: app.cadence_menu,
         title="Cuánto cierra el final",
         body="Un acorde de reposo suena cerrado cuando sus intervalos con el "
              "bajo son consonantes. Acá elegís cuánto le importa eso al "
              "programa, desde ignorarlo hasta exigirlo como regla dura.\n\n"
              "Si los finales te suenan abiertos, subilo."),
    dict(target=lambda app: app.next_button,
         title="Generar",
         body="Al apretar «Generar» arrancan doscientas soluciones al azar "
              "que se cruzan y mejoran durante trescientas generaciones. "
              "Tarda unos segundos y se puede cancelar.\n\n"
              "Al final ves las mejores. Como interviene el azar, dos "
              "corridas iguales dan resultados parecidos pero no idénticos."),
)

#: Qué guía va en cada lugar. La clave es lo que se anota en las preferencias
#: como visto, así que no se cambia sin dejar a quien ya la vio viéndola otra
#: vez.
SCREEN_GUIDES: Dict[str, Tuple[dict, ...]] = {
    "chords": CHORDS_GUIDE,
    "melody": MELODY_GUIDE,
    "harmony": HARMONY_GUIDE,
    "parameters": PARAMETER_GUIDE,
}


class Tutorial:
    """
    El recorrido guiado, dibujado encima de la interfaz de verdad.

    No hay una versión de mentira de la aplicación: el tutorial navega el
    carrusel real y resalta los widgets reales, así que lo que el usuario ve
    mientras aprende es exactamente lo que va a ver después.

    El foco se hace con cuatro paneles opacos --- arriba, abajo, izquierda y
    derecha del widget resaltado --- que dejan un hueco justo del tamaño del
    widget. Tk no sabe pintar con transparencia, así que un velo con un
    agujero de verdad no se puede; cuatro rectángulos alrededor del hueco dan
    el mismo resultado y no cuestan nada. Como además tapan todo lo demás,
    también sirven para que no se pueda tocar nada por accidente en el medio
    del recorrido.
    """

    #: Cuánto se aleja el cartel del widget resaltado.
    GAP = 18
    #: Ancho del cartel.
    CARD = 430
    #: Cuánto se espera a que la ventana deje de cambiar de tamaño antes de
    #: volver a dibujar el paso. Arrastrando el borde llegan decenas de
    #: avisos por segundo y cada dibujo rearma el cartel entero.
    RESIZE_MS = 120

    def __init__(self, app: "ChordWeaverApp", steps=TUTORIAL_STEPS,
                 on_finish=None, last_label: str = "Ir a los logros"):
        """
        ``steps`` es la lista de pasos y decide todo lo demás.

        Un paso con ``screen`` mueve el carrusel antes de dibujarse; sin él,
        el recorrido se queda donde está. De ahí sale la diferencia entre el
        recorrido de bienvenida ---que navega las siete pantallas--- y las
        guías de una pantalla sola, que explican lo que ya se tiene enfrente
        y no pueden mover nada porque el usuario está a mitad de un trabajo.

        ``on_finish`` reemplaza lo que pasa al terminar. Vacío es el
        recorrido de bienvenida: marcar la preferencia, entregar el logro y
        llevar a los logros. Una guía sólo se cierra.
        """
        self.app = app
        self.steps = tuple(steps)
        self.on_finish = on_finish
        self.last_label = last_label
        #: ¿Este recorrido mueve el carrusel? Lo contesta la lista de pasos.
        self.navigates = any("screen" in step for step in self.steps)
        self.index = 0
        self.parts: List[tk.Widget] = []
        self.card: Optional[ctk.CTkFrame] = None
        self.veil = mix(SURFACE, VEIL, 0.5)
        #: Los enlaces puestos en la ventana, para desatar justo ésos.
        self._escape_id: Optional[str] = None
        self._resize_id: Optional[str] = None
        #: El redibujado pendiente por un cambio de tamaño, y el tamaño
        #: contra el que se dibujó el paso que está a la vista.
        self._resize_job: Optional[str] = None
        self._size: Tuple[int, int] = (0, 0)
        self._done = False

    # -- ciclo de vida ------------------------------------------------------

    def start(self) -> None:
        app = self.app
        if self.navigates:
            app.detour.clear()
            app.index = 0
            app._render()
        self.index = 0
        if self._escape_id is None:
            self._escape_id = app.bind("<Escape>", lambda _e: self.skip(),
                                       add="+")
            self._resize_id = app.bind("<Configure>", self._on_configure,
                                       add="+")
        app.after(80, self._show)

    def skip(self) -> None:
        self._finish()

    def close(self) -> None:
        """
        Sacar el recorrido de la ventana: el dibujo, los enlaces y el
        redibujado pendiente. Vale llamarla de más.

        `_clear` sólo borra el dibujo, y se usa entre un paso y otro. Esto
        es para cuando el recorrido se va del todo: si quedaba atado, cada
        guía que se abría dejaba un Escape y un `<Configure>` más colgados
        de la ventana.
        """
        # Cerrado es para siempre: un paso que todavía esperaba su `after`
        # ya no se dibuja. Si no, una guía cerrada por un rearmado en sus
        # primeras décimas tapaba la pantalla nueva con sus velos.
        self._done = True
        self._clear()
        if self._resize_job is not None:
            try:
                self.app.after_cancel(self._resize_job)
            except tk.TclError:
                pass
            self._resize_job = None
        unbind_one(self.app, "<Configure>", self._resize_id)
        unbind_one(self.app, "<Escape>", self._escape_id)
        self._resize_id = self._escape_id = None

    def _finish(self) -> None:
        # Una sola vez, y nunca después de `close`: el recorrido de
        # bienvenida que terminara dos veces entregaría el logro y saltaría
        # a los logros dos veces.
        if self._done:
            return
        self.close()
        if self.on_finish is not None:
            self.on_finish()
            return
        app = self.app
        app.tutorial = None
        app.settings["tutorial_seen"] = True
        history.save_settings(app.settings, app.settings_path)
        app._award({"tutorial_done"})
        app._open_detour("achievements", replace=True)

    def _clear(self) -> None:
        for part in self.parts:
            try:
                part.destroy()
            except tk.TclError:
                pass
        self.parts = []
        if self.card is not None:
            try:
                self.card.destroy()
            except tk.TclError:
                pass
            self.card = None

    # -- el tamaño de la ventana ---------------------------------------------
    #
    # Los velos, el marco y el cartel se colocan en píxeles contra el tamaño
    # que tenía la ventana al dibujar el paso. Maximizada después, la
    # pantalla de abajo se reacomodaba y el recorrido se quedaba donde
    # estaba: un velo del tamaño viejo, y un hueco señalando el lugar donde
    # ya no estaba el widget.

    def _on_configure(self, event) -> None:
        # Atado a la ventana, `<Configure>` llega también por cada widget de
        # adentro ---todos llevan la ventana entre sus etiquetas---, los
        # velos de este mismo recorrido incluidos. Sólo cuenta el de la
        # ventana, y sólo si cambió el tamaño: moverla también lo manda.
        if event.widget is not self.app:
            return
        if (event.width, event.height) == self._size:
            return
        # Se agrupan: cada aviso nuevo corre la espera, y se dibuja una vez
        # cuando la ventana se queda quieta.
        try:
            if self._resize_job is not None:
                self.app.after_cancel(self._resize_job)
            self._resize_job = self.app.after(self.RESIZE_MS,
                                              self._follow_resize)
        except tk.TclError:
            self._resize_job = None

    def _follow_resize(self) -> None:
        self._resize_job = None
        # Sin cartel no hay nada a la vista: o el recorrido se cerró, o un
        # paso está esperando que la pantalla nueva se acomode y se va a
        # dibujar solo, ya con el tamaño nuevo.
        if self._done or self.card is None:
            return
        app = self.app
        if getattr(app, "_rendering", False):
            # A mitad de un rearmado. Dibujando ahora, `_render` subiría la
            # pantalla nueva por encima de los velos al terminar.
            self._resize_job = app.after(self.RESIZE_MS, self._follow_resize)
            return
        try:
            size = (app.winfo_width(), app.winfo_height())
        except tk.TclError:
            return
        if size != self._size:
            self._draw()

    # -- pasos --------------------------------------------------------------

    def _advance(self) -> None:
        self.index += 1
        if self.index >= len(self.steps):
            self._finish()
            return
        self._show()

    def _show(self) -> None:
        if self._done:
            return
        app = self.app
        step = self.steps[self.index]
        if self.navigates and app.index != step["screen"]:
            self._clear()
            app.index = step["screen"]
            app._render()
            # Un respiro para que Tk termine de acomodar la pantalla nueva:
            # medir un widget que todavía no fue colocado devuelve 1x1 y el
            # hueco sale del tamaño de un píxel.
            app.after(90, self._draw)
            return
        self._draw()

    def _target_box(self, step) -> Optional[Tuple[int, int, int, int]]:
        """Dónde está el widget a resaltar, en coordenadas de la ventana."""
        resolve = step.get("target")
        if resolve is None:
            return None
        try:
            widget = resolve(self.app)
        except (KeyError, IndexError, TypeError, AttributeError, tk.TclError):
            # Una guía señala widgets que la pantalla arma sola --- la
            # primera casilla de acorde, un interruptor que este modo no
            # ofrece --- y cualquiera de ésos puede no estar. Un paso sin
            # blanco se dibuja centrado, que es exactamente lo que
            # corresponde: se lee igual y no se pierde la explicación.
            return None
        if widget is None:
            return None
        try:
            self.app.update_idletasks()
            if not widget.winfo_exists() or not widget.winfo_ismapped():
                return None
            self._reveal(widget)
            self.app.update_idletasks()
            x = widget.winfo_rootx() - self.app.winfo_rootx()
            y = widget.winfo_rooty() - self.app.winfo_rooty()
            return (x, y, widget.winfo_width(), widget.winfo_height())
        except tk.TclError:
            return None

    @staticmethod
    def _reveal(widget) -> None:
        """
        Traer el blanco a la vista si vive adentro de un marco con scroll.

        `winfo_ismapped` contesta que sí aunque el widget esté por debajo
        del borde: un marco con scroll no desmapea lo que no se ve, sólo lo
        corre. Sin esto, el foco se dibujaba sobre un pedazo de pantalla
        donde no había nada y el paso terminaba señalando el vacío --- que
        es exactamente lo que pasaba con los tildes de modulación, que
        viven al pie de una columna larga.
        """
        holder = widget
        for _ in range(8):
            holder = getattr(holder, "master", None)
            if holder is None:
                return
            canvas = getattr(holder, "_parent_canvas", None)
            if canvas is None:
                continue
            try:
                top = widget.winfo_rooty() - canvas.winfo_rooty()
                if 0 <= top and top + widget.winfo_height() <= canvas.winfo_height():
                    return          # ya se ve entero
                inside = widget.winfo_rooty() - holder.winfo_rooty()
                total = max(1, holder.winfo_height())
                # Un poco de aire arriba: pegado al borde se lee como
                # cortado aunque esté entero.
                canvas.yview_moveto(max(0.0, (inside - 40) / total))
            except (tk.TclError, AttributeError):
                pass
            return

    def _draw(self) -> None:
        app = self.app
        if self._done:
            return
        try:
            if not app.winfo_exists():
                return
        except tk.TclError:
            return
        self._clear()
        step = self.steps[self.index]
        raw = self._target_box(step)
        width, height = app.winfo_width(), app.winfo_height()
        self._size = (width, height)
        self.veil = mix(SURFACE, VEIL, 0.5)

        # El hueco se calcula UNA vez, con su margen incluido, y de acá en
        # adelante todos lo usan: los velos, el marco y la flecha. Calculado
        # por separado en cada lugar, la flecha quedaba metida adentro del
        # margen y se veía como una muesca oscura sobre el borde iluminado.
        box = None
        if raw is not None:
            pad = 6
            x, y, w, h = raw
            box = (max(0, x - pad), max(0, y - pad), w + pad * 2, h + pad * 2)

        if box is None:
            rects = [(0, 0, width, height)]
        else:
            x, y, w, h = box
            rects = [(0, 0, width, y),
                     (0, y + h, width, max(0, height - y - h)),
                     (0, y, x, h),
                     (x + w, y, max(0, width - x - w), h)]

        for left, top, wide, tall in rects:
            if wide <= 0 or tall <= 0:
                continue
            panel = tk.Frame(app, bg=self.veil)
            panel.place(x=left, y=top, width=wide, height=tall)
            # Se traga los clics: durante el recorrido no se puede tocar
            # nada de lo que hay debajo, ni por accidente.
            panel.bind("<Button-1>", lambda _e: None)
            self.parts.append(panel)

        accent = app._mode_accent()
        if box is not None:
            x, y, w, h = box
            for left, top, wide, tall in ((x, y, w, 2), (x, y + h - 2, w, 2),
                                          (x, y, 2, h), (x + w - 2, y, 2, h)):
                edge = tk.Frame(app, bg=accent)
                edge.place(x=left, y=top, width=wide, height=tall)
                self.parts.append(edge)

        self._draw_card(box, step, accent, width, height)

    def _draw_card(self, box, step, accent: str, width: int,
                   height: int) -> None:
        app = self.app
        card = ctk.CTkFrame(app, fg_color=SURFACE_LIGHT, corner_radius=14,
                            border_width=2, border_color=accent)
        self.card = card

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 0))
        # Los pasos son constantes de módulo ---`TUTORIAL_STEPS`,
        # `SCREEN_GUIDES`---, así que el castellano es lo que traen y la
        # traducción va acá, al dibujarse.
        ctk.CTkLabel(head, text=tr(step["title"]),
                     font=scaled(("Segoe UI Semibold", 17)),
                     text_color=accent, anchor="w", justify="left",
                     wraplength=self.CARD - 130).pack(side="left")
        ctk.CTkLabel(head, text=trf("{n} de {total}", n=self.index + 1,
                                    total=len(self.steps)),
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="right")
        ctk.CTkLabel(card, text=tr(step["body"]), font=scaled(("Segoe UI", 12)),
                     text_color=TEXT_NORMAL, wraplength=self.CARD - 40,
                     justify="left", anchor="w"
                     ).pack(anchor="w", padx=20, pady=(10, 14))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        last = self.index == len(self.steps) - 1
        ctk.CTkButton(row, text=tr("Omitir"), width=130, height=34,
                      corner_radius=9, font=FONT_SMALL,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER_SOFT, text_color=TEXT_MUTED,
                      hover_color=SURFACE, command=self.skip
                      ).pack(side="left")
        ctk.CTkButton(row, text=tr(self.last_label) if last
                      else tr("Siguiente  →"),
                      width=150, height=34, corner_radius=9,
                      font=scaled(("Segoe UI Semibold", 12)),
                      fg_color=accent,
                      hover_color=mix(accent, "#FFFFFF", 0.16),
                      command=self._advance).pack(side="right")

        # Medido después de armarlo y colocado sin tamaño: customtkinter no
        # deja pasar `width`/`height` a `place`, así que el cartel se dibuja
        # del tamaño que le pide su contenido y lo único que se calcula acá
        # es dónde ponerlo.
        card.update_idletasks()
        card_w = card.winfo_reqwidth()
        card_h = card.winfo_reqheight()

        if box is None:
            left = (width - card_w) // 2
            top = (height - card_h) // 2
            arrow = None
        else:
            x, y, w, h = box
            left = min(max(12, x + w // 2 - card_w // 2), width - card_w - 12)
            below = y + h + self.GAP + 22
            if below + card_h < height - 12:
                top, arrow = below, ("▲", y + h + 3)
            else:
                top = max(12, y - self.GAP - 22 - card_h)
                arrow = ("▼", y - 25)
        card.place(x=left, y=max(12, top))
        card.lift()

        if arrow is not None:
            glyph, arrow_y = arrow
            mark = tk.Label(app, text=glyph, bg=self.veil, fg=accent,
                            font=scaled(("Segoe UI", 15)), bd=0,
                            padx=0, pady=0)
            mark.place(x=left + card_w // 2 - 9, y=arrow_y)
            mark.lift()
            self.parts.append(mark)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class ChordWeaverApp(ctk.CTk):
    """Main window and carousel controller."""

    def __init__(self):
        super().__init__()
        self.title("ChordWeaver")
        # Grande de entrada. Las pantallas del recorrido ya venían
        # justas, y las del modo historia --- el cartel del sendero, el botón
        # dorado --- necesitan aire; en una ventana chica lo último que se
        # agregó quedaba abajo del pliegue y no se podía ni tocar.
        # Con `CHORDWEAVER_TEST_ORIGIN` (las pruebas) nace en ese lugar,
        # que suele ser otra pantalla. Ver `uitest._placed`.
        self.geometry("1440x1010" + os.environ.get("CHORDWEAVER_TEST_ORIGIN",
                                                   ""))
        self.minsize(1180, 880)
        self.configure(fg_color=SURFACE)
        # El inicio se arma la primera vez antes de que la ventana tenga su
        # tamaño, y sus dibujos dependen de él (`_home_signature`). Cuando
        # la ventana cambia de tamaño estando ahí, se rearma si hace falta.
        self._refit_id = None
        self.bind("<Configure>", self._window_resized, add="+")

        # --- state ---------------------------------------------------------
        self.genre_key: str = "classical"
        self.voice_keys: List[str] = ["B", "T", "A", "S"]
        self.range_overrides: Dict[int, Tuple[int, int]] = {}
        self.bar_count: int = 4
        self.base_time_signature: str = "4/4"
        self.bar_signatures: List[str] = []
        self.chord_rows: List[dict] = []
        self.switch_vars: Dict[str, tk.BooleanVar] = {}
        self.ga_vars: Dict[str, tk.StringVar] = {
            key: tk.StringVar(value=default)
            for key, _label, default, _explanation in self.GA_FIELDS
        }
        self.ga_config = GAConfig()
        self.outcome: Optional[session.JobOutcome] = None
        self.request: Optional[session.JobRequest] = None
        self.progress_queue: "queue.Queue[tuple]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.config_panel: Optional[ctk.CTkFrame] = None
        #: El cartel de las donaciones. Va aparte del de configuración ---y
        #: no reusando aquél--- porque los dos se abren desde el pie y hay
        #: que poder cerrar uno para abrir el otro sin que el engranaje
        #: termine cerrando un cartel que no es el suyo.
        self.donate_panel: Optional[ctk.CTkFrame] = None
        self.saved_chords: Dict[int, List[dict]] = {}
        # Preferences persist next to the program, so the search settings and
        # the text size survive a restart.
        #: Dónde se anota el historial. ``None`` es el archivo de al lado
        #: del programa, que es lo que quiere cualquier usuario. Existe
        #: para que el arnés de pruebas pueda mandarlo a un descartable:
        #: `uitest` genera decenas de partituras seguidas y cada una
        #: quedaba anotada, así que diez corridas de prueba borraban el
        #: historial de verdad --- que sólo guarda las diez últimas ---
        #: sin que nadie se enterara.
        self.history_path = None
        #: Y dónde van las preferencias, por lo mismo. El arnés abre la
        #: ventana decenas de veces y cualquier cosa que llame a
        #: `save_settings` --- el panel de configuración, el final del
        #: tutorial, marcar una anotación como leída --- escribía sobre las
        #: del usuario. `book_seen` es lo peor que se puede pisar ahí: es lo
        #: que decide qué anotaciones le figuran como nuevas.
        self.settings_path = None
        self.settings = history.load_settings()
        #: El idioma que quedó elegido. `main()` ya lo puso ---lo necesitan
        #: el cartel de la primera vez y el de versión nueva, que se dibujan
        #: antes que esta ventana--- pero se vuelve a poner acá para que
        #: armar `ChordWeaverApp` a mano ---un script, el arnés de pruebas---
        #: hable el mismo idioma que el programa abierto normalmente.
        i18n.set_language(str(self.settings.get("language", "") or i18n.DEFAULT))
        # El timbre de las reproducciones, antes de que nada pueda sonar.
        # Si el WAV elegido ya no está, suena el de siempre y el panel de
        # configuración cuenta por qué; abrir el programa no es momento de
        # un cartel de error por algo que no se pidió.
        self._timbre_problem = self._apply_timbre(
            str(self.settings.get("timbre", "") or timbres.DEFAULT),
            str(self.settings.get("timbre_path", "") or ""))
        # Los logros viven al lado del programa, igual que el historial.
        self.achievements = achievements.Tracker.load()
        # Y los huevos de pascua en su propio archivo, por la misma razón por
        # la que el sendero tiene el suyo: no son logros ni preferencias.
        self.eggs = eggs.Basket.load()
        # Las visitas, en el suyo: cuántas partituras van de cada género,
        # quién ya se apareció y si la visión ya ocurrió.
        self.visits = visitors.Ledger.load()
        # La escuelita, en el suyo: qué ejercicios están aprobados y si la
        # graduación ya se vio. Lo que se está escribiendo en cada ejercicio
        # va aparte y sólo en memoria: tiene que sobrevivir a ir al libro y
        # volver, no a cerrar el programa.
        self.school = curriculum.Progress.load()
        self.school_memory: dict = {}
        #: Si la última corrida del generador salió con todo al máximo. Se
        #: decide al dejar la pantalla de armonía y se cobra al terminar.
        self._blast_armed = False
        self.toasts: List[Toast] = []
        #: Los avisos que esperan lugar. Ver `MAX_TOASTS`.
        self._toast_backlog: List[Tuple[object, str]] = []
        #: El recorrido guiado, mientras esté corriendo.
        self.tutorial: Optional["Tutorial"] = None
        #: La guía de la pantalla en curso, mientras esté abierta. Es el
        #: mismo `Tutorial` con otra lista de pasos: ver `SCREEN_GUIDES`.
        self.guide: Optional["Tutorial"] = None
        #: Si las guías de pantalla pueden abrirse. Lo apaga `uitest`: son
        #: velos que tapan la ventana entera y el arnés no podría tocar
        #: nada. Va en memoria y no en las preferencias --- apagarlas no es
        #: una decisión del usuario, es una condición de las pruebas.
        self.guides_enabled = True
        #: Animaciones a pantalla completa pendientes, de a una por vez: una
        #: estrella y un legendario en la misma corrida se muestran en fila
        #: en vez de pisarse.
        self.celebrations: List[tuple] = []
        self.overlay: Optional[ctk.CTkFrame] = None
        #: Pantallas que no son parte del recorrido -- logros, historial, el
        #: detalle de una producción. Es una pila: desde el historial se
        #: entra a un detalle, y "Volver" tiene que devolver al historial y
        #: no al principio.
        self.detour: List[tuple] = []
        self._next_button_hidden = False
        # -- el modo historia ------------------------------------------------
        #: Por dónde va el sendero, guardado al lado del programa igual que
        #: el historial y los logros.
        self.story = story.StoryState.load()
        #: La escena en curso, si hay una. Mientras exista tapa la ventana
        #: entera y nada de abajo se puede tocar.
        self.scene: Optional["cinematic.Cutscene"] = None
        self._story_since = time.monotonic()
        #: El interruptor del ofrecimiento, para el arnés de pruebas. Es un
        #: interruptor **propio** y no `seen_offer`, que es un dato del
        #: usuario: apagarlo con un dato --- como se hacía --- funciona
        #: mientras ese dato signifique lo que a uno le conviene, y deja de
        #: funcionar en silencio el día que cambia de significado.
        self.story_offers = True
        #: Si el vigía del ofrecimiento tiene un turno agendado. Es lo que
        #: evita que se encienda dos veces --- se re-arma desde más de un
        #: lugar --- y termine preguntando el doble de seguido.
        self._story_watching = False
        #: Cinemáticas encoladas: el cierre de un tramo y la apertura del
        #: siguiente son dos escenas, y la segunda espera a que termine la
        #: primera en vez de dibujarse encima.
        self._scene_queue: List[dict] = []
        #: Lo que hay que hacer al terminar cada escena de una tanda, guardado
        #: hasta que termine la última. Ver `_advance_scenes`.
        self._scene_afters: List = []
        # ga_vars were built from the built-in defaults a few lines above;
        # now that the stored preferences are loaded, they win.
        for key, _label, default, _explanation in self.GA_FIELDS:
            self.ga_vars[key].set(str(self.settings.get(key, default)))
        global FONT_SCALE
        FONT_SCALE = float(self.settings.get("font_scale", 1.0))
        self._rescale_fonts()

        self._build_chrome()
        self.mode = "manual"
        self._apply_mode()
        self.index = 0
        self._render()
        if not self.settings.get("tutorial_seen"):
            # La primera vez, y una sola. Va con `after` y no acá mismo
            # porque el recorrido mide los widgets que va a señalar, y hasta
            # que la ventana no está dibujada todos miden un píxel.
            self.after(300, self._maybe_start_tutorial)
        # Los ruidos de la historia se sintetizan en un hilo aparte, mucho
        # antes de que suene nada: son unos segundos de cálculo y hacerlos
        # cuando aparece el personaje congelaría la ventana justo ahí.
        self.after(4000, self._prepare_story_sound)
        self._rearm_story_watch(6000)
        # Y si un sendero quedó terminado sin que su legendario se entregara
        # ---la cinemática de cierre interrumpida---, se entrega ahora.
        self.after(1500, self._story_settle_awards)
        # Y se pregunta una vez al arrancar si ya está todo conseguido. La
        # entidad se decidía **sólo** al ganar un logro, así que quien llegaba
        # al cien por ciento y cerraba el programa antes de que la escena
        # terminara ---la visita se marca cuando termina, no cuando se
        # dispara--- se quedaba sin ella para siempre: no quedaba ningún
        # logro nuevo por ganar que volviera a hacer la pregunta.
        self.after(2500, self._check_watcher)
        # La visión va al principio de todo --- es lo primero que pasa, o no
        # pasa --- y la visita forzada por variable de entorno, un momento
        # después, para no encimarse con ella.
        # Los ruidos de la visión se piden antes que nada si el sorteo la
        # eligió: son cuatro archivos largos y la escena arranca a los pocos
        # segundos de abrir el programa.
        self.after(200, self._warm_vision)
        self.after(1400, self._maybe_vision)
        self.after(2600, self._forced_visit)

    def _maybe_start_tutorial(self) -> None:
        """
        Arrancar el recorrido si todavía hace falta.

        La comprobación se repite acá y no sólo al programar el ``after``
        para que se pueda desactivar entre medio: es lo que hace `uitest`,
        que maneja la interfaz a través de los widgets reales y con el
        tutorial encima no podría tocar nada.
        """
        if not self.settings.get("tutorial_seen"):
            self._start_tutorial()

    def _start_tutorial(self) -> None:
        """Arrancar el recorrido guiado, o reiniciarlo si ya estaba abierto."""
        if getattr(self, "tutorial", None) is not None:
            self.tutorial.close()
        self._close_guide()
        # Reiniciar el recorrido reinicia **todo** lo que se explica: las
        # guías de pantalla son la otra mitad de lo mismo, y quien viene a
        # pedir la explicación de nuevo la viene a pedir entera. Es además
        # la única manera de volver a verlas.
        self.settings["guides_seen"] = []
        history.save_settings(self.settings, self.settings_path)
        self.tutorial = Tutorial(self)
        self.tutorial.start()

    # -- las guías de pantalla ----------------------------------------------
    #
    # Una por modo, en la pantalla donde ese modo hace su trabajo. No las
    # dispara el carrusel sino cada pantalla al terminar de armarse: el
    # blanco de un paso puede ser un widget que la pantalla crea sola --- la
    # primera casilla de acorde --- y desde afuera no hay manera de saber
    # cuándo existe.

    def _maybe_guide(self, key: str) -> None:
        """
        Abrir la guía de esta pantalla si es la primera vez que se llega.

        Se pide desde el final de la pantalla, así que llega con los widgets
        recién creados y todavía sin colocar. De ahí el ``after``: medir un
        widget que Tk no acomodó todavía devuelve 1x1 y el hueco del foco
        sale del tamaño de un píxel.
        """
        if not self.guides_enabled or key not in SCREEN_GUIDES:
            return
        if key in set(self.settings.get("guides_seen") or ()):
            return
        # Nunca encima de otra cosa. El recorrido de bienvenida pasa por
        # estas pantallas y pondría dos velos uno sobre el otro; una escena
        # del sendero o una celebración ocupan la ventana entera.
        if (getattr(self, "tutorial", None) is not None
                or self.guide is not None
                or self.overlay is not None or self.scene is not None
                or self.celebrations or self._scene_queue):
            return
        self.after(220, lambda: self._start_guide(key))

    def _start_guide(self, key: str) -> None:
        steps = SCREEN_GUIDES.get(key)
        if not steps or self.guide is not None:
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        # Entre el pedido y este momento pasaron dos décimas, y en ese rato
        # se pudo haber abierto cualquier cosa --- o el usuario pudo haberse
        # ido a otra pantalla.
        if (getattr(self, "tutorial", None) is not None
                or self.overlay is not None or self.scene is not None):
            return
        # Dada por vista **al abrirse**, y no al terminar como el recorrido
        # de bienvenida. La pantalla se rearma sola por varios motivos ---
        # cambiar el tamaño de letra, volver de la configuración --- y cada
        # rearmado vuelve a preguntar: marcándola al final, una guía cerrada
        # por un rearmado volvía a aparecer enseguida, y no había manera de
        # sacársela de encima.
        seen = list(self.settings.get("guides_seen") or ())
        if key not in seen:
            seen.append(key)
        self.settings["guides_seen"] = seen
        history.save_settings(self.settings, self.settings_path)
        self.guide = Tutorial(self, steps=steps, on_finish=self._close_guide,
                              last_label="Entendido")
        self.guide.start()

    def _close_guide(self) -> None:
        """Cerrar la guía abierta, si hay una. Vale llamarla de más."""
        guide, self.guide = getattr(self, "guide", None), None
        if guide is not None:
            guide.close()

    def _rescale_fonts(self) -> None:
        """Recompute every font constant from the current scale."""
        global FONT_TITLE, FONT_SUB, FONT_BODY, FONT_SMALL
        _FONT_CACHE.clear()
        FONT_TITLE = scaled(("Segoe UI Semibold", 22))
        FONT_SUB = scaled(("Segoe UI", 13))
        FONT_BODY = scaled(("Segoe UI", 12))
        FONT_SMALL = scaled(("Segoe UI", 11))

    def _apply_mode(self) -> None:
        """
        Rebuild the carousel for the chosen mode.

        The two modes share everything except one screen: manual mode asks
        for the chords, the generator asks for the key and what it may borrow.
        Keeping a single carousel means genre, voices, metre, parameters and
        results have exactly one implementation each.
        """
        # Los títulos van marcados con `N` y **no** traducidos: el castellano
        # es la clave con la que `_commit_screen` encuentra qué pantalla hay
        # que cerrar, y quien lo traduce es el `tr()` del rótulo del paso.
        shared_head = [
            (self._screen_mode, N("Modo")),
            (self._screen_genre, N("Género")),
        ]
        # Harmonising fixes the texture by style: four parts for jazz, so a
        # seventh has somewhere to go, three for everything else. Asking the
        # user would only let them pick a texture the mode cannot use.
        if self.mode != "harmonise":
            shared_head.append((self._screen_voices, N("Voces")))
        # The harmonise mode takes its metre from the melody itself, so the
        # bars screen would be asking a question that is already answered.
        if self.mode != "harmonise":
            shared_head.append((self._screen_metre, N("Compases")))
        if self.mode == "manual":
            middle = [(self._screen_chords, N("Acordes"))]
        elif self.mode == "harmonise":
            middle = [(self._screen_melody, N("Melodía"))]
        else:
            middle = [(self._screen_harmony, N("Tonalidad"))]
        shared_tail = [
            (self._screen_parameters, N("Parámetros")),
            (self._screen_results, N("Resultado")),
        ]
        pages = shared_head + middle + shared_tail
        self.screens = [page for page, _title in pages]
        self.screen_titles = [title for _page, title in pages]

    @property
    def _chords_index(self) -> int:
        """Where the chords screen sits, or -1 in generator mode."""
        return 4 if self.mode == "manual" else -1

    # -- screen 0: mode -----------------------------------------------------

    def _screen_mode(self) -> None:
        if self._reusing_home:
            self._refresh_home()
            return
        # Sin bajada: el dibujo de cada tarjeta ya dice qué ponés vos y qué
        # escribe el programa, y ese renglón es el que necesita el cartel
        # del sendero para entrar abajo en la ventana más chica.
        self._heading(tr("Elegí un modo"), "")

        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="both", expand=True, pady=(10, 6))
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="mode")
        # La fila de las tarjetas mide lo que mide la más alta y las otras dos
        # se estiran hasta ahí: quedan parejas sin dejar el hueco enorme que
        # dejaba estirar la fila hasta el pie de la ventana. El aire sobrante
        # cae en la fila de abajo, así el contenido queda arrimado arriba
        # como en todas las demás pantallas.
        grid.grid_rowconfigure(HOME_SHELF_ROW + 2, weight=1)

        art = self._home_art_colours()
        grow = self._home_grow()
        self.mode_cards: Dict[str, Card] = {}
        wrap = self._card_wrap()
        for column, entry in enumerate(MODE_CARDS):
            key, name, subtitle, accent, _icon = entry
            card = Card(grid, name, "",
                        command=lambda k=key: self._select_mode(k),
                        accent=accent, subtitle=subtitle,
                        flag=MODE_FLAGS.get(key, ""), wraplength=wrap,
                        badge=False, serif=True,
                        picture=lambda canvas, width, k=key, a=accent:
                        homeart.draw_flow(canvas, k, a, art, width),
                        picture_height=int(homeart.FLOW_HEIGHT * grow))
            card.grid(row=0, column=column, sticky="nsew", padx=8, pady=(4, 10))
            self.mode_cards[key] = card
        # Sin animar: la pantalla recién se está armando y las tres
        # tarjetas arrancan y terminan en el mismo estado.
        self._select_mode(self.mode, animated=False)

        # Debajo, las tres herramientas que no componen nada ---el
        # experimentador desarma una nota, el analizador desarma una
        # partitura, la escuelita enseña a escribir una--- con su título,
        # del mismo tamaño que los modos y en las mismas tres columnas. Y
        # abajo de todo, los dos lugares donde se mira lo que uno ya hizo o
        # lo que hay para leer, mitad y mitad.
        #
        # Cada fila va en su propia grilla y no en la de las tarjetas: el
        # estante es de dos, y tres no se parten en dos --- con `columnspan`
        # una de las dos quedaba al doble de la otra.
        ctk.CTkLabel(grid, text=tr("Herramientas"),
                     font=scaled(("Georgia", 16, "bold")),
                     text_color=TEXT_MUTED).grid(row=1, column=0, sticky="w",
                                                padx=10, pady=(0, 2))
        tools = ctk.CTkFrame(grid, fg_color="transparent")
        tools.grid(row=2, column=0, columnspan=3, sticky="ew", padx=0,
                   pady=(0, 8))
        tools.grid_columnconfigure(tuple(range(len(TOOL_CARDS))), weight=1,
                                   uniform="herramienta")
        tools.grid_rowconfigure(0, weight=1)
        self.tool_row = tools
        self.tool_cards: Dict[str, Card] = {}
        for column, entry in enumerate(TOOL_CARDS):
            key, name, subtitle, body, accent, _icon = entry
            card = Card(tools, name, body,
                        command=lambda k=key: self._open_detour(k,
                                                                replace=True),
                        accent=accent, subtitle=subtitle,
                        flag=MODE_FLAGS.get(key, ""), wraplength=wrap,
                        badge=False, serif=True,
                        picture=lambda canvas, width, k=key, a=accent:
                        homeart.draw_tool(
                            canvas, k, a, art, width,
                            self._school_state() if k == "school" else None),
                        picture_height=int(homeart.TOOL_HEIGHT * grow))
            # El mismo margen que los modos, así cada herramienta queda
            # exactamente debajo de un modo y la pantalla se lee en columnas.
            card.grid(row=0, column=column, sticky="nsew", padx=8)
            self.tool_cards[key] = card

        self._home_grid = grid
        self._home_lower = self._build_home_lower(grid)
        self._cascade(self.mode_cards.values())
        self._cascade(self.tool_cards.values(), step=40)
        self._home_body = self.body
        self._home_key = self._home_signature()

    def _school_state(self) -> "homeart.SchoolState":
        """Dónde anda el usuario en la escuelita, para el dibujo del inicio."""
        units = curriculum.UNITS
        share = []
        for unit in units:
            items = [entry for lesson in unit.lessons
                     for entry in lesson.exercises]
            passed = sum(1 for entry in items if self.school.has(entry.key))
            share.append(passed / len(items) if items else 0.0)
        done = tuple(share)
        current = None
        label = ""
        if not all(part >= 1.0 for part in done):
            unit = curriculum.unit_of(self.school.current().key)
            if unit is not None and unit in units:
                current, label = units.index(unit), unit.short
        return done, current, label, bool(self.school.graduated)

    def _home_signature(self) -> Tuple:
        """Lo que, si cambia, obliga a rearmar la pantalla inicial entera."""
        return (i18n.language(), FONT_SCALE, len(MODE_CARDS), len(TOOL_CARDS),
                self._card_wrap(), self._home_grow(),
                bool(self.settings.get("professional")))

    def _card_wrap(self) -> int:
        """
        Dónde cortan los renglones de las tarjetas del inicio, en píxeles.

        Según el ancho de la ventana, de a escalones de cuarenta para que
        agrandarla un poco no obligue a rearmar la pantalla. Con el corte
        fijo en 300, en una ventana ancha el texto ocupaba la mitad
        izquierda de cada tarjeta y la otra mitad quedaba vacía.
        """
        try:
            width = self.winfo_width()
        except tk.TclError:
            width = 1
        if width < 600:
            return 300
        return max(300, min(460, ((width - 104) // 3 - 64) // 40 * 40))

    def bring_to_front(self) -> None:
        """Dejar la ventana a la vista: sin minimizar, adelante y con foco."""
        try:
            if self.state() in ("iconic", "withdrawn"):
                self.deiconify()
            self.lift()
            # `-topmost` un instante: es lo único que Windows deja hacer para
            # traer adelante una ventana cuando el foco lo tiene otro
            # programa. Se saca enseguida para no quedar encima de todo.
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except tk.TclError:
            pass

    def _window_resized(self, event) -> None:
        """La ventana cambió de tamaño: mirar, con espera, si el inicio sirve."""
        if event.widget is not self:
            return
        if self._refit_id is not None:
            try:
                self.after_cancel(self._refit_id)
            except tk.TclError:
                pass
        self._refit_id = self.after(250, self._refit_home)

    def _refit_home(self) -> None:
        """
        Rearmar el inicio si el tamaño nuevo de la ventana lo pide.

        Sólo si es la pantalla que se ve y no hay nada encima: un recorrido o
        una guía señalan tarjetas del inicio, una escena o un cartel lo
        tapan, y rearmar debajo de ellos les cambiaba los widgets.
        """
        self._refit_id = None
        try:
            if (self.detour or self._rendering
                    or self.screens[self.index] != self._screen_mode):
                return
        except (AttributeError, IndexError):
            return
        tutorial = getattr(self, "tutorial", None)
        if tutorial is not None and not getattr(tutorial, "_done", True):
            return
        if (getattr(self, "guide", None) is not None
                or getattr(self, "scene", None) is not None
                or getattr(self, "overlay", None) is not None):
            return
        if getattr(self, "_home_key", None) == self._home_signature():
            return
        self._render()

    def _home_grow(self) -> float:
        """
        Cuánto crecen los dibujos de las tarjetas con el alto de la ventana.

        La medida de los dibujos es la que entra en la ventana más chica.
        En la de arranque, más alta, sobraba un cuarto de pantalla vacío
        abajo; agrandar los pentagramas lo aprovecha y en una pantalla
        grande se leen mejor. De a décimos, para que estirar un poco la
        ventana no obligue a rearmar la pantalla.
        """
        try:
            height = self.winfo_height()
        except tk.TclError:
            height = 1
        if height < 400:
            return 1.0
        return round(min(1.4, max(1.0, 1.0 + (height - 900) / 300)), 1)

    @staticmethod
    def _home_art_colours() -> Dict[str, object]:
        """La paleta y las letras de los dibujos de las tarjetas (`homeart`)."""
        return {
            "text": TEXT_NORMAL, "muted": TEXT_MUTED,
            "faint": mix(SURFACE_LIGHT, TEXT_MUTED, 0.45),
            "chip": mix(SURFACE_LIGHT, TEXT_NORMAL, 0.07),
            "card": SURFACE_LIGHT, "surface": SURFACE,
            "gold": mix(TEXT_MUTED, GOLD, 0.6),
            "font_caption": scaled(("Segoe UI Semibold", 8)),
            "font_symbol": scaled(("Segoe UI Semibold", 10)),
            "font_chip": scaled(("Segoe UI Semibold", 13)),
            "font_option": scaled(("Segoe UI Semibold", 10)),
            "font_tiny": scaled(("Segoe UI", 8)),
            "font_roman": scaled(("Georgia", 11, "bold")),
        }

    def _home_reusable(self) -> bool:
        """
        Si la pantalla que viene es la inicial y la guardada todavía sirve.

        Es la pantalla con más tarjetas y la que más se visita: armarla
        costaba más de medio segundo, casi todo de customtkinter dibujando
        bordes redondeados, y se pagaba cada vez que se volvía al principio.
        Las tarjetas no cambian; lo que cambia ---los logros, el libro, el
        sendero--- se rehace en `_refresh_home`.
        """
        body = self._home_body
        if body is None or self.detour:
            return False
        if self.screens[self.index] != self._screen_mode:
            return False
        try:
            if not body.winfo_exists():
                return False
        except tk.TclError:
            return False
        return self._home_key == self._home_signature()

    def _refresh_home(self) -> None:
        """Poner al día la pantalla inicial guardada."""
        for widget in self._home_lower:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._home_lower = self._build_home_lower(self._home_grid)
        # El mouse pudo haberse ido con una tarjeta encendida: al esconder
        # la pantalla no llega ningún `<Leave>`.
        cards = list(self.mode_cards.values()) + list(self.tool_cards.values())
        for card in cards:
            card._hovered = False
        self._select_mode(self.mode, animated=False)
        for card in self.tool_cards.values():
            try:
                card._paint(animated=False)
            except tk.TclError:
                pass
        # La escuelita dibuja dónde anda el usuario, y eso cambia afuera
        # del inicio: al volver de un ejercicio aprobado tiene que moverse.
        school_card = self.tool_cards.get("school")
        if school_card is not None:
            school_card.redraw_picture()

    def _build_home_lower(self, grid) -> List[tk.Misc]:
        """Los logros, el libro y el sendero: la parte del inicio que cambia."""
        shelf = ctk.CTkFrame(grid, fg_color="transparent")
        shelf.grid(row=HOME_SHELF_ROW, column=0, columnspan=3, sticky="ew",
                   padx=0, pady=(0, 6))
        shelf.grid_columnconfigure((0, 1), weight=1, uniform="estante")
        # Las dos se estiran hasta el alto de la más alta. Los logros llevan
        # cinco estrellas de cuerpo 26 y el libro no, así que sin esto la
        # tarjeta del libro quedaba visiblemente más baja que su vecina.
        shelf.grid_rowconfigure(0, weight=1)
        self.achievement_banner = AchievementBanner(
            shelf, self.achievements,
            command=lambda: self._open_detour("achievements", replace=True))
        self.achievement_banner.grid(row=0, column=0, sticky="nsew",
                                     padx=(8, 5))
        written, total = book.counts(self._lore_unlocked)
        self.book_banner = BookBanner(
            shelf, written, total, len(self._fresh_notes()),
            command=lambda: self._open_detour("book", replace=True))
        self.book_banner.grid(row=0, column=1, sticky="nsew", padx=(5, 8))
        built: List[tk.Misc] = [shelf]
        # El recordatorio del sendero, cuando hay uno. Va debajo de todo:
        # es una capa encima del programa, no una cuarta forma de trabajar.
        if not self.settings.get("professional") and (
                self.story.path is not None
                or getattr(self, "_story_knocking", False)):
            holder = ctk.CTkFrame(grid, fg_color="transparent")
            holder.grid(row=HOME_SHELF_ROW + 1, column=0, columnspan=3,
                        sticky="new")
            if self.story.path is not None:
                self._story_banner(holder)
            else:
                self._story_knock(holder)
            built.append(holder)
        return built

    @staticmethod
    def _cascade(cards, step: int = 32) -> None:
        """Encender una fila de tarjetas de a una, de izquierda a derecha.

        El escalón es corto a propósito: la cascada es un gesto, no una
        espera. Con el que tenía, la pantalla inicial ---que es la primera
        que se ve al abrir el programa--- tardaba más de medio segundo en
        terminar de aparecer, y eso no se lee como una animación sino como
        que el programa está cargando.
        """
        for position, card in enumerate(cards):
            card.reveal(delay=position * step)

    def _heading(self, title: str, blurb: str) -> None:
        """
        El encabezado de una pantalla: título grande y una bajada.

        Centralizado porque las nueve pantallas lo repetían con tamaños y
        márgenes apenas distintos, y esas diferencias de dos píxeles eran
        buena parte de lo que hacía que el programa se viera desprolijo.
        """
        # En Georgia, la letra del libro: con todo en Segoe UI el programa
        # se leía como un formulario cualquiera. La serif en los títulos es
        # lo que hace una partitura editada, y el cuerpo sigue en Segoe para
        # que los controles se lean de corrido.
        ctk.CTkLabel(self.body, text=tr(title),
                     font=scaled(("Georgia", 22, "bold")),
                     anchor="w", justify="left").pack(anchor="w")
        if blurb:
            ctk.CTkLabel(self.body, text=tr(blurb), font=scaled(("Segoe UI", 12)),
                         text_color=TEXT_MUTED, wraplength=880,
                         justify="left", anchor="w").pack(anchor="w",
                                                          pady=(4, 16))

    def _select_mode(self, key: str, animated: bool = True) -> None:
        changed = key != self.mode
        self.mode = key
        # The cards belong to whichever render drew them; a stored reference
        # can outlive its widget when the screen is rebuilt, and touching it
        # raises rather than being ignored.
        for card_key, card in list(self.mode_cards.items()):
            try:
                card.set_selected(card_key == key, animated=animated)
            except tk.TclError:
                self.mode_cards.pop(card_key, None)
        # El riel y el logotipo llevan el color del modo, así que elegir una
        # tarjeta se nota en toda la ventana y no sólo dentro de la tarjeta.
        self._update_rail(getattr(self, "_rail_position", 0.0))
        if changed:
            self._apply_mode()

    # -- chrome -------------------------------------------------------------

    def _build_chrome(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(18, 4))

        # El logotipo va partido en dos etiquetas para que la segunda mitad
        # lleve el color del modo elegido. Es la misma pista que da el riel de
        # abajo, en el lugar donde la vista arranca.
        wordmark = ctk.CTkFrame(header, fg_color="transparent", cursor="hand2")
        wordmark.pack(side="left")
        chord = ctk.CTkLabel(wordmark, text=tr("Chord"), font=FONT_TITLE,
                             cursor="hand2")
        chord.pack(side="left")
        self.wordmark_tail = ctk.CTkLabel(wordmark, text=tr("Weaver"), font=FONT_TITLE,
                                          text_color=ACCENT, cursor="hand2")
        self.wordmark_tail.pack(side="left")
        bind_deeply(descendants(wordmark), "<Button-1>",
                    lambda _e: self._go_home())
        Tooltip(chord, tr("Volver al principio"))
        Tooltip(self.wordmark_tail, tr("Volver al principio"))

        self.step_label = ctk.CTkLabel(header, text="", font=FONT_SMALL,
                                       text_color=TEXT_MUTED)
        self.step_label.pack(side="left", padx=16)
        ctk.CTkButton(header, text=tr("Historial"), width=92, height=32,
                      corner_radius=9, font=FONT_SMALL,
                      fg_color="transparent",
                      border_width=1, border_color=BORDER_SOFT,
                      text_color=TEXT_MUTED, hover_color=SURFACE_LIGHT,
                      command=lambda: self._open_detour("history", replace=True)
                      ).pack(side="right")
        # Los logros también se alcanzan desde la tarjeta de la pantalla
        # inicial; acá están para no tener que volver al principio.
        ctk.CTkButton(header, text=tr("Logros"), width=92, height=32,
                      corner_radius=9, font=FONT_SMALL,
                      fg_color="transparent",
                      border_width=1, border_color=BORDER_SOFT,
                      text_color=TEXT_MUTED, hover_color=SURFACE_LIGHT,
                      command=lambda: self._open_detour("achievements", replace=True)
                      ).pack(side="right", padx=(0, 8))

        # El libro, al alcance de la mano desde cualquier pantalla. Va con
        # los otros dos atajos y con los colores del papel: es lo único de la
        # cabecera que no forma parte del trabajo, y conviene que se lea como
        # otra cosa antes de leerse. Se consulta justo cuando aparece una
        # palabra que no se entiende, y eso pasa en cualquier punto del
        # programa --- hasta ahora había que volver al principio.
        self.book_button = ctk.CTkButton(
            header, text="🕮", width=44, height=32, corner_radius=9,
            font=scaled(("Segoe UI Symbol", 19)), fg_color=PAPER,
            border_width=1, border_color=RULE, text_color=INK,
            hover_color=PAPER_EDGE,
            command=lambda: self._open_detour("book", replace=True))
        self.book_button.pack(side="right", padx=(0, 8))
        Tooltip(self.book_button, tr("Libro de teoría"))

        # El riel de progreso. Reemplaza a contar "paso 3 de 7" con la vista:
        # cuánto falta se ve, no se lee. Se pinta del color del modo, así que
        # también recuerda en qué está trabajando el usuario.
        rail = ctk.CTkFrame(self, fg_color=SURFACE_LIGHT, height=4,
                            corner_radius=2)
        rail.pack(fill="x", padx=28, pady=(2, 0))
        rail.pack_propagate(False)
        #: Guardado para que el tutorial pueda señalarlo.
        self.rail = rail
        self.rail_fill = ctk.CTkFrame(rail, fg_color=ACCENT, corner_radius=2)
        self.rail_fill.place(relx=0.0, rely=0.0, relwidth=0.0, relheight=1.0)
        self._rail_position = 0.0

        footer = ctk.CTkFrame(self, fg_color="transparent", height=60)
        # Packed BEFORE the body and anchored to the bottom, so the footer
        # claims its strip first and whatever a screen asks for has to fit in
        # what is left. Packed after, a greedy screen squeezed the buttons
        # flat -- and only on that screen, which is why they looked
        # inconsistent from page to page.
        footer.pack(side="bottom", fill="x", padx=28, pady=(6, 20))
        #: Guardado para que el tutorial pueda señalarlo.
        self.footer = footer
        # Without this the frame shrinks to whatever its children ask for and
        # the buttons end up squashed to a couple of pixels tall.
        footer.pack_propagate(False)
        gear = ctk.CTkButton(footer, text="⚙", width=44, height=42,
                             corner_radius=11,
                             font=scaled(("Segoe UI", 18)),
                             fg_color="transparent", border_width=1,
                             border_color=BORDER_SOFT, text_color=TEXT_MUTED,
                             hover_color=SURFACE_LIGHT,
                             command=self._open_config)
        gear.pack(side="left", padx=(0, 10))
        Tooltip(gear, tr("Configuración y accesibilidad"))

        # Al lado del engranaje, y dorado: es lo único del pie que pide algo
        # en vez de hacer algo, así que tiene que verse ---si no, no está---
        # pero no puede competir con «Siguiente», que es lo que el usuario
        # vino a apretar. El borde dorado alcanza; con relleno sólido quedaba
        # más llamativo que el botón que hace avanzar el programa.
        donate = ctk.CTkButton(footer, text=tr("♥  Donar"), width=104, height=42,
                               corner_radius=11,
                               font=scaled(("Segoe UI", 13)),
                               fg_color="transparent", border_width=1,
                               border_color=GOLD_DIM, text_color=GOLD,
                               hover_color=SURFACE_LIGHT,
                               command=self._open_donate)
        donate.pack(side="left", padx=(0, 10))
        Tooltip(donate, tr("El programa es gratis. Si querés bancarlo, acá te "
                           "digo cómo."))

        self.back_button = ctk.CTkButton(footer, text=tr("←  Atrás"), width=140,
                                         height=42, corner_radius=11,
                                         font=scaled(("Segoe UI", 13)),
                                         fg_color="transparent", border_width=1,
                                         border_color=BORDER_SOFT,
                                         text_color=TEXT_NORMAL,
                                         hover_color=SURFACE_LIGHT,
                                         command=self._go_back)
        self.back_button.pack(side="left", pady=6)
        # A la derecha de «Atrás», y sólo en la pantalla que tiene una
        # configuración de estilo que devolver. No se empaca acá: lo pone y
        # lo saca `_render_screen`, y siempre con `before=` el botón de
        # «Siguiente» --- volver a empacar algo manda al final del orden, y
        # el cartel del pie puede haberse metido en el medio mientras tanto.
        self.reset_button = ctk.CTkButton(footer, text=tr("⟳  Resetear"), width=140,
                                          height=42, corner_radius=11,
                                          font=scaled(("Segoe UI", 13)),
                                          fg_color="transparent", border_width=1,
                                          border_color=BORDER_SOFT,
                                          text_color=TEXT_MUTED,
                                          hover_color=SURFACE_LIGHT,
                                          command=self._reset_harmony)
        Tooltip(self.reset_button,
                tr("Vuelve esta pantalla a los valores del estilo elegido."))
        self.next_button = ctk.CTkButton(footer, text=tr("Siguiente"), width=180,
                                         height=42, corner_radius=11,
                                         font=scaled(("Segoe UI Semibold", 13)),
                                         fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                         command=self._go_next)
        self.next_button.pack(side="right", pady=6)
        self.status_label = ctk.CTkLabel(footer, text="", font=FONT_SMALL,
                                         text_color=TEXT_MUTED)
        self.status_label.pack(side="right", padx=16)

        # El aviso de que algo se anotó solo en el libro. Va en el medio del
        # pie porque no pertenece a ninguna pantalla: una anotación se
        # escribe mientras uno está en cualquier lado. **Y es la misma
        # anotación a mano que el libro pone al pie de un apartado recién
        # abierto** --- ver `handwritten_line`. No dice qué se anotó ni en
        # qué capítulo: eso lo dice el azul del índice.
        self.note_flag = handwritten_line(footer, self.NOTE_FLAG_TEXT,
                                          SURFACE)
        # Un clic lo saca antes de tiempo, que es lo único que hace el clic
        # sobre el cartel de un logro. No lleva a ninguna parte: una nota al
        # margen que además navega es un botón disfrazado.
        bind_deeply(descendants(self.note_flag), "<Button-1>",
                    lambda _event: self._hide_note_flag())
        # Si está puesto en el pie: `pack` no lo contesta, y volver a empacar
        # algo ya empacado lo manda al final del orden --- o sea, de lugar.
        self._note_flag_shown = False
        # El `after` que lo va a sacar, para poder cancelarlo si en el medio
        # se anota otra cosa: la segunda anotación tiene que dejarlo puesto
        # su tiempo entero, no el resto del de la primera.
        self._note_flag_timer = None
        # Si está apagándose ahora mismo. Mientras dura eso el cartel sigue
        # empacado --- se lo saca del pie recién cuando la tinta terminó de
        # irse --- así que hace falta distinguir «puesto» de «yéndose».
        self._note_flag_fading = False
        # Qué había sin leer la última vez que se miró: ver
        # `_refresh_note_flag`.
        self._notes_known = None
        # El escenario ocupa el lugar de la pantalla y no cambia nunca; la
        # pantalla es un marco `place`-ado adentro, y `_render` arma la nueva
        # en otro marco escondido debajo de la vieja. Ver `_render`.
        self.stage = ctk.CTkFrame(self, fg_color="transparent")
        self.stage.pack(fill="both", expand=True, padx=28, pady=8)
        self.body = self._fresh_body()
        self.body.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._rendering = False
        self._render_again = False
        # La pantalla inicial armada y guardada, y con qué idioma y escala
        # se armó. Ver `_home_reusable`.
        self._home_body = None
        self._home_key = None
        self._home_lower: List[tk.Misc] = []
        self._reusing_home = False
        #: Los cuatro marcos que cuelgan de la ventana, anotados para poder
        #: desarmarlos: cambiar de idioma tiene que rehacer también la
        #: cabecera y el pie, que se arman una sola vez y no pasan por
        #: `_render`. Es la lista de lo que hay que destruir, no un dato de
        #: la interfaz --- ver `_switch_language`.
        self._chrome = (header, rail, footer, self.stage)

    # -- la anotación a mano del pie -----------------------------------------

    #: Lo que dice, y siempre lo mismo aunque haya varias anotaciones nuevas:
    #: es una nota al margen, no un contador. La pluma no va acá --- la pone
    #: `handwritten_line`.
    NOTE_FLAG_TEXT = N("Has descubierto algo nuevo")

    #: Cuánto se queda, y es el mismo número que el aviso de un logro a
    #: propósito: el logro suele ser lo que abre el apartado, así que los dos
    #: se prenden juntos y con tiempos distintos uno dejaba al otro solo.
    NOTE_FLAG_MS = Toast.LIFETIME_MS

    #: En cuántos cuadros y cada cuántos milisegundos se prende y se apaga.
    #: Un tercio de segundo: lo suficiente para que se lea como que la tinta
    #: aparece y no como que el cartel se encendió.
    NOTE_FLAG_FADE = (14, 22)

    def _paint_note_flag(self, colour: str) -> None:
        """Pintar la pluma y el renglón del cartel del pie de un color."""
        flag = getattr(self, "note_flag", None)
        if flag is None:
            return
        try:
            for child in flag.winfo_children():
                child.configure(fg=colour)
        except tk.TclError:
            pass

    def _refresh_note_flag(self) -> None:
        """
        Mirar si se anotó algo nuevo y, si sí, prender el cartel del pie.

        Lo dispara que **aparezca** una anotación sin leer, y no que haya
        alguna: preguntando por el estado se prendía de nuevo en cada
        ``_render``, o sea en cada pantalla que el usuario pasara hasta ir a
        leer. Por lo mismo `_notes_known` arranca en ``None``: abrir el
        programa con cosas sin leer no es un descubrimiento.

        Se llama en cada ``_render`` --- que cubre todo lo que escribe en el
        libro y después redibuja --- y a mano en los dos lugares que escriben
        sin redibujar nada: el final de una visita y el de la visión.
        """
        fresh = set(self._fresh_notes())
        known, self._notes_known = self._notes_known, fresh
        if known is None:
            return
        if fresh - known:
            self._flash_note_flag()
        elif not fresh:
            # Se leyó lo último que quedaba mientras el cartel seguía
            # puesto. Sacarlo ahí es más honesto que dejarlo cumplir su
            # tiempo anunciando algo que el usuario ya fue a ver.
            self._hide_note_flag()

    def _flash_note_flag(self) -> None:
        """
        Poner el cartel en el pie, y programar cuándo se va.

        **Aparece escribiéndose, no encendido**: el renglón y la pluma entran
        del color del pie y van al oro en un tercio de segundo. Es una
        anotación a mano, y una anotación a mano no se prende --- y el salto
        de golpe, en el medio del pie y mientras el usuario está mirando otra
        cosa, se leía como un parpadeo de la ventana.

        Lo que **no** se anima es el lugar: el cartel ocupa el hueco que ya
        existe entre «Atrás» y «Siguiente», así que no mueve nada al entrar.
        Animar la geometría de algo empacado sí movería a los vecinos, un
        cuadro por vez.
        """
        flag = getattr(self, "note_flag", None)
        if flag is None:
            return
        steps, period = self.NOTE_FLAG_FADE
        try:
            if not self._note_flag_shown:
                # `expand` lo centra en lo que sobra del pie, que es
                # justamente el hueco entre «Atrás» y «Siguiente». Empacado
                # después que los dos, el orden lo deja siempre en el medio.
                flag.pack(side="left", expand=True, pady=6)
                self._note_flag_shown = True
            # Si estaba yéndose, esto cancela la ida: `animate` cancela el
            # pendiente que haya bajo la misma clave, así que la segunda
            # anotación lo trae de vuelta desde donde estuviera en vez de
            # dejar que la primera termine sacándolo del pie.
            self._note_flag_fading = False
            animate(flag, lambda position:
                    self._paint_note_flag(mix(SURFACE, GOLD, position)),
                    steps=steps, period=period, key="_note_fade")
            if self._note_flag_timer is not None:
                self.after_cancel(self._note_flag_timer)
            self._note_flag_timer = self.after(self.NOTE_FLAG_MS,
                                               self._hide_note_flag)
        except (tk.TclError, ValueError):
            pass

    def _hide_note_flag(self) -> None:
        """
        Sacarlo del pie, apagándolo primero. Lo llama su reloj, o un clic.

        Se despaca recién cuando la tinta terminó de irse, y no antes: es la
        misma razón por la que entra apagado. `_note_flag_shown` sigue en
        ``True`` mientras dura eso --- el cartel *está* en el pie --- y
        `_note_flag_fading` es lo que impide que un segundo clic durante la
        ida lo devuelva al oro para apagarlo de nuevo.
        """
        self._note_flag_timer = None
        flag = getattr(self, "note_flag", None)
        if flag is None or not self._note_flag_shown:
            return
        if self._note_flag_fading:
            return
        self._note_flag_fading = True
        steps, period = self.NOTE_FLAG_FADE

        def frame(position: float) -> None:
            self._paint_note_flag(mix(GOLD, SURFACE, position))
            if position < 1.0:
                return
            self._note_flag_shown = False
            self._note_flag_fading = False
            try:
                flag.pack_forget()
            except tk.TclError:
                pass

        try:
            animate(flag, frame, steps=steps, period=period, key="_note_fade")
        except tk.TclError:
            pass

    def _clear_body(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    #: Las pantallas de fuera del recorrido, con el título que va arriba.
    DETOUR_TITLES = {
        "achievements": "Logros",
        "history": "Historial",
        "record": "Historial · detalle",
        "book": "Libro de teoría",
        "lab": "Experimentador de armónicos",
        "analysis": "Analizador",
        "school": "Escuelita",
    }

    def _open_detour(self, name: str, payload=None,
                     replace: bool = False) -> None:
        """
        Ir a una pantalla que no forma parte del recorrido.

        ``replace`` es para los destinos de arriba --- Logros e Historial ---,
        que no son un paso adentro de nada sino un lugar al que se va. Sin
        eso, los botones del encabezado seguían visibles dentro del desvío y
        cada apretón apilaba otra copia de la misma pantalla: había que
        apretar "Volver" tantas veces como se hubiera tocado el botón.
        """
        if self.detour and self.detour[-1] == (name, payload):
            return
        if replace:
            self.detour = [(name, payload)]
        else:
            self.detour.append((name, payload))
        self._render()

    def _close_detour(self) -> None:
        """Volver de donde se vino, un escalón por vez."""
        if self.detour:
            self.detour.pop()
        self._render()

    def _fresh_body(self) -> "ctk.CTkFrame":
        """Un marco vacío para armar una pantalla, todavía sin ubicar."""
        body = ctk.CTkFrame(self.stage, fg_color="transparent")
        body.pack_propagate(False)
        body.grid_propagate(False)
        return body

    def _render(self) -> None:
        """
        Redibujar la pantalla actual, con doble búfer.

        La pantalla nueva se arma en un marco aparte, se ubica **debajo** de
        la vieja y se le deja hacer todo su dibujo ahí, tapada. Recién
        cuando terminó se la sube y se destruye la vieja, así que el cambio
        es uno solo. Antes se desmapeaba el cuerpo, se lo armaba y se lo
        volvía a mapear: eso evitaba el repintado widget por widget mientras
        se creaban, pero customtkinter dibuja sus bordes redondeados recién
        al recibir su tamaño, que llega al mapear. La pantalla aparecía en
        blanco y después por tramos, con bloques encimados hasta que el
        último se acomodaba: medio segundo largo cada vez que se volvía al
        inicio, que es la pantalla con más tarjetas.

        Windows recorta a los hermanos tapados, así que lo que se dibuja
        debajo no se ve.
        """
        if self._rendering:
            # Un click o un temporizador atendido mientras la pantalla nueva
            # se dibujaba tapada. Sólo se anota: el redibujado se agenda una
            # vez, al terminar. Agendándolo acá con `after_idle`, el mismo
            # `update()` que lo había llamado lo volvía a correr, se volvía
            # a agendar, y el programa quedaba colgado para siempre --- un
            # doble click en una tarjeta alcanzaba.
            self._render_again = True
            return
        # Antes que nada: la guía abierta señala widgets de la pantalla que
        # está por desaparecer. Sus velos están puestos sobre la ventana y
        # no sobre el cuerpo, así que sobrevivirían al rearmado y quedarían
        # tapando la pantalla nueva con un hueco en cualquier parte.
        self._close_guide()
        old = self.body
        kept = self._home_body
        self._reusing_home = self._home_reusable()
        self.body = kept if self._reusing_home else self._fresh_body()
        self._rendering = True
        try:
            # Antes de armar nada: lo que se construya de acá en adelante
            # toma el acento del modo en curso.
            self._apply_accent()
            self._render_screen()
        finally:
            self._reusing_home = False
            if self.body is not old:
                try:
                    self.body.place(x=0, y=0, relwidth=1.0, relheight=1.0)
                    self.body.lower(old)
                    # Que llegue el tamaño y que cada widget se dibuje,
                    # tapado.
                    self.update_idletasks()
                    self.update()
                except tk.TclError:
                    pass
            self._rendering = False
            self.body.lift()
            if old is not self.body:
                # La pantalla inicial no se destruye al irse: queda puesta
                # debajo de la actual, tapada. Sacándola con `place_forget`
                # la vuelta pagaba volver a mapear sus doscientos widgets.
                # Lo que cambia ---logros, libro, sendero--- sí se va: tiene
                # brillos animados que seguían corriendo escondidos, y
                # `_refresh_home` lo rearma al volver.
                if old is self._home_body:
                    old.lower()
                    for widget in self._home_lower:
                        try:
                            widget.destroy()
                        except tk.TclError:
                            pass
                    self._home_lower = []
                else:
                    old.destroy()
            if (kept is not None and kept is not self._home_body
                    and kept is not old):
                # Una pantalla inicial guardada que dejó de servir.
                kept.destroy()
            # Los avisos están `place`-ados sobre la ventana, y todo lo que
            # se acaba de crear queda por encima de ellos en el orden de
            # apilado. Se los vuelve a subir en cada render: si no, el cartel
            # de un logro aparece detrás de la pantalla y no se ve.
            self._reflow_toasts()
            # Y el cartel del pie, que no es de ninguna pantalla pero puede
            # haber aparecido --- o haberse leído --- mientras se armaba
            # ésta.
            self._refresh_note_flag()
            if self._render_again:
                self._render_again = False
                self.after_idle(self._render)

    def _render_screen(self) -> None:
        if not self._reusing_home:
            self._clear_body()
        if self.detour:
            name, payload = self.detour[-1]
            # Los logros y el historial son una pantalla más, no una ventana
            # aparte: el paso siguiente no significa nada acá, así que el
            # botón se esconde y "Atrás" pasa a ser la única salida.
            self.step_label.configure(text=tr(self.DETOUR_TITLES.get(name, "")))
            self.back_button.configure(text=tr("←  Volver"), state="normal",
                                       command=self._close_detour)
            self.reset_button.pack_forget()
            if not self._next_button_hidden:
                self.next_button.pack_forget()
                self._next_button_hidden = True
            self._update_rail(1.0, muted=True)
            {"achievements": self._screen_achievements,
             "history": self._screen_history,
             "record": self._screen_record,
             "book": self._screen_book,
             "lab": self._screen_lab,
             "analysis": self._screen_analysis,
             "school": self._screen_school}[name](payload)
            return

        if self._next_button_hidden:
            # Repuesto delante del texto de estado, que es lo que lo mantiene
            # a la derecha del todo como estaba antes de esconderlo.
            self.next_button.pack(side="right", pady=6,
                                  before=self.status_label)
            self._next_button_hidden = False
        self.back_button.configure(text=tr("←  Atrás"), command=self._go_back)
        self.step_label.configure(
            # El título se traduce acá y no en `_apply_mode`: ahí el
            # castellano es la clave con la que `_commit_screen` encuentra
            # qué pantalla hay que cerrar.
            text=trf("Paso {index} de {screens} · {screen_titles}",
                     index=self.index + 1, screens=len(self.screens),
                     screen_titles=tr(self.screen_titles[self.index]))
        )
        self.back_button.configure(state="normal" if self.index > 0 else "disabled")
        # Los métodos ligados se comparan por igualdad, no por identidad:
        # cada acceso al atributo arma uno nuevo.
        if self.screens[self.index] == self._screen_harmony:
            self.reset_button.pack(side="left", padx=(10, 0), pady=6,
                                   before=self.next_button)
        else:
            self.reset_button.pack_forget()
        self.next_button.configure(
            text=tr("Generar" if self.index == len(self.screens) - 2
               else "Siguiente  →"), state="normal"
        )
        if self.index == len(self.screens) - 1:
            self.next_button.configure(text=tr("Nuevo"))
        self._update_rail((self.index + 1) / len(self.screens))
        self.screens[self.index]()
        # Recién acá, con la pantalla ya armada: `_screen_results` puede
        # dejar `self.outcome` corrido de lo que muestra --- entrar de nuevo
        # a buscar lo vacía --- y hasta ahora el botón lo ignoraba.
        self._refresh_continue_button()

    def _refresh_continue_button(self) -> None:
        """
        Griseado el «Siguiente»/«Nuevo» mientras apretarlo no lleva a nada.

        `_go_next` ya se negaba en silencio --- con la búsqueda corriendo, o
        con el gesto dorado del sendero esperando que se escuche lo que
        salió, tocarlo no hacía nada --- y eso era peor que no tener el
        botón: parecía que el programa se había colgado. Ahora lo dice antes
        de que haga falta tocarlo.

        Se mira `self._results_ready` y no `self.outcome`: en el tramo
        automático del sendero el outcome queda asignado bastante antes de
        que la pantalla muestre nada --- ver `_run_story_piece` ---, así que
        mirar sólo el outcome dejaba el botón activo durante ese hueco.
        `_results_ready` sólo se enciende en `_show_results`, que es donde
        las tres salidas de `_on_finished` ---error, sin solución, éxito---
        terminan de verdad.

        No hace nada fuera de la pantalla de resultados: en las demás
        `_render_screen` ya lo deja en `"normal"` un poco más arriba, y ahí
        nunca hay nada que esperar.
        """
        if self.index != len(self.screens) - 1:
            return
        waiting_listen = getattr(self, "_story_continue_row", None) is not None
        ready = getattr(self, "_results_ready", False) and not waiting_listen
        try:
            self.next_button.configure(state="normal" if ready else "disabled")
        except tk.TclError:
            pass

    # -- el riel de progreso -------------------------------------------------

    def _mode_accent(self) -> str:
        """El color de lo que se está usando ahora mismo.

        Las herramientas también tiñen la interfaz. No son más modos ---el
        riel de progreso sigue apagado adentro de ellas--- pero mientras se
        está adentro son lo que se está usando, y quedarse con el azul del
        modo elegido antes de entrar hacía que el experimentador y el
        analizador fueran los únicos lugares del programa donde el color no
        decía dónde estaba uno. La escuelita, igual.
        """
        detour = self.detour[-1][0] if self.detour else ""
        for key, _name, _sub, _body, accent, _icon in TOOL_CARDS:
            if key == detour:
                return accent
        for key, _name, _sub, accent, _icon in MODE_CARDS:
            if key == self.mode:
                return accent
        return ACCENT

    def _apply_accent(self) -> None:
        """
        Poner el color del modo como acento de toda la interfaz.

        Cada pantalla se rearma entera en cada ``_render`` y todos los widgets
        leen ``ACCENT`` al construirse, así que alcanza con cambiar la
        variable acá: switches, sliders, menús, casillas, barras y botones
        salen del color del modo sin tener que enterarse de nada. Los del
        marco fijo se crean una sola vez, así que a esos hay que retocarlos a
        mano --- lo hace ``_update_rail``.
        """
        global ACCENT, ACCENT_HOVER
        ACCENT = self._mode_accent()
        ACCENT_HOVER = mix(ACCENT, "#FFFFFF", 0.16)

    def _update_rail(self, position: float, muted: bool = False) -> None:
        """
        Correr el riel hasta ``position`` (0 a 1), animado.

        Se anima ``relwidth`` sobre un widget ``place``-ado a propósito:
        ``place`` no participa del cálculo de layout de sus hermanos, así que
        moverlo cuadro a cuadro no obliga a Tk a recalcular la ventana. El
        mismo efecto hecho con ``pack`` sí lo haría.
        """
        rail = getattr(self, "rail_fill", None)
        if rail is None:
            return
        self._apply_accent()
        colour = TEXT_MUTED if muted else self._mode_accent()
        start = getattr(self, "_rail_position", 0.0)
        self._rail_position = position
        # El pie y el encabezado se arman una sola vez, así que el cambio de
        # acento no les llega solo: se los pasa acá, que es lo que corre en
        # cada render y cada vez que se elige un modo.
        try:
            self.next_button.configure(fg_color=ACCENT, hover_color=ACCENT_HOVER)
        except tk.TclError:
            pass
        try:
            # El logotipo lleva siempre el color del modo, incluso en las
            # pantallas de fuera del recorrido: apagarlo ahí lo hacía parecer
            # deshabilitado. El que se apaga es el riel, que es el que está
            # diciendo "acá no estás avanzando".
            self.wordmark_tail.configure(text_color=self._mode_accent())
            rail.configure(fg_color=colour)
        except tk.TclError:
            pass

        def frame(step: float) -> None:
            try:
                rail.place_configure(relwidth=start + (position - start) * step)
            except tk.TclError:
                pass

        animate(rail, frame, steps=9, period=16)

    def _go_next(self) -> None:
        if self.index == self._chords_index:
            self._snapshot_chords()
        if self.index == len(self.screens) - 1:
            # Desde el resultado, «Siguiente» quiere decir volver a empezar
            # --- pero no mientras la búsqueda todavía corre. Sin este guard
            # el usuario se llevaba puesta su propia corrida sin ningún
            # aviso: la pantalla volvía al principio y el resultado, que
            # llegaba unos segundos más tarde, ya no tenía dónde dibujarse.
            # `_go_home` siempre lo miró; esta puerta era la que faltaba.
            if self.worker is not None and self.worker.is_alive():
                return
            self.index = 0
            self._render()
            return
        if not self._commit_screen():
            return
        if self.index == len(self.screens) - 2:
            self._run_search()
            return
        self.index += 1
        self._render()

    def _go_home(self) -> None:
        """
        Back to the first screen, unless a search is running.

        El guard va **antes** que el borrado, y no después. Estaba al revés:
        tocar «Inicio» con una búsqueda en curso no navegaba --- eso está
        bien --- pero para entonces ya había tirado el request, los switches
        y el género elegido. La pantalla seguía igual, así que no se veía
        nada; lo que se veía era después, cuando la búsqueda terminaba y
        «Guardar» reventaba contra un request que ya no existía y la
        partitura se perdía sin un solo mensaje.
        """
        if self.worker is not None and self.worker.is_alive():
            return
        self._reset_to_defaults()
        if self.index == self._chords_index:
            self._snapshot_chords()
        self.detour.clear()
        self.index = 0
        self._render()

    #: Hasta dónde llega el dial del tamaño de letra. Es una constante
    #: porque el huevo de los anteojos pregunta por el tope, y un tope
    #: escrito dos veces se desincroniza en cuanto se toca uno.
    FONT_SCALE_MAX = 1.8

    def _open_config(self) -> None:
        """
        Genetic-algorithm settings, reachable from anywhere.

        These live behind the gear rather than in the carousel because they
        are not part of describing the piece: most runs never touch them, and
        having them inline made the parameters screen look like something you
        had to fill in.

        Rendered as a panel over the main window rather than a separate
        top-level window. A Toplevel is placed by the window manager, which
        on a multi-monitor setup can drop it on whichever screen it likes --
        the panel always appears where the user is already looking.
        """
        if getattr(self, "config_panel", None) is not None:
            self._close_config()
            return
        self._close_donate()          # nunca dos carteles encima

        panel = ctk.CTkFrame(self, fg_color=SURFACE_LIGHT, corner_radius=16,
                             border_width=1, border_color=BORDER_SOFT)
        panel.place(relx=0.5, rely=0.5, anchor="center",
                    relwidth=0.66, relheight=0.86)
        self.config_panel = panel

        # La fila de botones se empaqueta ANTES que el contenido y anclada
        # abajo, así reclama su franja primero y lo que venga después tiene
        # que caber en lo que queda. Empaquetada al final, con la letra al
        # 180% el contenido crecía hasta empujarla fuera del panel y
        # "Aceptar" desaparecía sin manera de llegar a él.
        # La versión, chiquita y gris, pegada al borde de abajo. Va
        # empaquetada ANTES que la fila de botones y también anclada abajo:
        # el que se empaqueta primero se queda con el borde, así que este
        # orden es el que la deja al pie de todo y a los botones encima.
        ctk.CTkLabel(panel, text=trf("ChordWeaver {APP_VERSION}",
                                     APP_VERSION=APP_VERSION),
                     font=scaled(("Segoe UI", 10)), text_color=TEXT_MUTED
                     ).pack(side="bottom", pady=(0, 8))
        buttons = ctk.CTkFrame(panel, fg_color="transparent", height=56)
        buttons.pack(side="bottom", fill="x", pady=(4, 12))
        buttons.pack_propagate(False)
        # Y el resto va adentro de un marco con scroll, por el mismo motivo:
        # a tamaños de letra grandes no entra, y tiene que poder recorrerse.
        window = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        window.pack(side="top", fill="both", expand=True, padx=4, pady=(4, 0))

        # -- el idioma, arriba de todo ---------------------------------------
        #
        # Primero porque es lo único de este panel que cambia lo que el
        # usuario *lee*: quien lo abre buscándolo lo encuentra sin recorrer
        # siete campos del algoritmo, y quien lo abre por otra cosa entiende
        # de entrada en qué idioma está parado.
        #
        # Los rótulos van cada uno en su propio idioma y **sin traducir**:
        # así el que dejó el programa en un idioma que no entiende puede
        # volver. Por eso no pasan por `tr()`.
        ctk.CTkLabel(window, text=tr("Idioma"),
                     font=scaled(("Segoe UI Semibold", 16))
                     ).pack(anchor="w", padx=22, pady=(20, 2))
        ctk.CTkLabel(window,
                     text=tr("Se aplica al instante. Lo que ya generaste no "
                             "cambia, porque los acordes se escriben igual en "
                             "los dos idiomas."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 8))
        language_row = ctk.CTkSegmentedButton(
            window, values=[label for _code, label in i18n.languages()],
            font=FONT_SMALL, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=SURFACE, unselected_hover_color=SURFACE_RAISED,
            command=lambda label: self._switch_language(
                {name: code for code, name in i18n.languages()}[label]))
        language_row.set(i18n.label_of(i18n.language()))
        language_row.pack(anchor="w", padx=22, pady=(0, 4))

        ctk.CTkLabel(window, text=tr("Algoritmo genético"),
                     font=scaled(("Segoe UI Semibold", 16))).pack(anchor="w", padx=22,
                                                          pady=(20, 2))
        ctk.CTkLabel(window,
                     text=tr("Los valores por defecto andan bien para casi todo. "
                             "Pasá el mouse por cada uno para ver qué hace."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 12))

        for key, label, default, explanation in self.GA_FIELDS:
            line = ctk.CTkFrame(window, fg_color="transparent")
            line.pack(fill="x", padx=22, pady=5)
            caption = ctk.CTkLabel(line, text=tr(label), font=FONT_SMALL, width=170,
                                   anchor="w")
            caption.pack(side="left")
            if key not in self.ga_vars:
                # Stored preferences win over the built-in default, so the
                # numbers the user settled on are still there next time.
                self.ga_vars[key] = tk.StringVar(
                    value=str(self.settings.get(key, default))
                )
            entry = ctk.CTkEntry(line, textvariable=self.ga_vars[key], width=100)
            entry.pack(side="left")
            Tooltip(caption, explanation)
            Tooltip(entry, explanation)

        workers = resolve_worker_count(None, 200 * 12)
        ctk.CTkLabel(window,
                     text=trf("Esta máquina tiene {cpu_count} núcleos. La "
                              "búsqueda usa {workers} proceso(s) y deja uno "
                              "libre para que la ventana siga respondiendo.",
                              cpu_count=os.cpu_count(), workers=workers),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=22, pady=(14, 6))

        def modest_machine() -> None:
            """
            Dejar el algoritmo en la versión recortada. Ver
            `LOW_RESOURCE_PRESET` para por qué son esos números y no otros.

            Escribe en las mismas casillas de arriba en vez de guardar un
            modo aparte, así que lo que hizo el botón queda **a la vista** y
            se deshace con "Restaurar valores por defecto" como cualquier
            otra cosa. Un interruptor con un preset escondido detrás sería la
            única parte de esta pantalla donde los números que se leen no son
            los que se usan.
            """
            for key, value in self.LOW_RESOURCE_PRESET.items():
                self.ga_vars[key].set(value)
            message.configure(
                text=tr("Listo. La búsqueda va a tardar más o menos la mitad, "
                        "pero afina menos y vas a oír un poco más de "
                        "movimiento entre acordes."))

        modest = ctk.CTkButton(
            window, text=tr("Equipo modesto"), height=32, width=150,
            corner_radius=10, font=FONT_SMALL, fg_color="transparent",
            border_width=1, border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
            hover_color=SURFACE, command=modest_machine)
        modest.pack(anchor="w", padx=22, pady=(2, 10))

        message = ctk.CTkLabel(window, text="", font=FONT_SMALL, text_color=WARN,
                               wraplength=460, justify="left")
        message.pack(anchor="w", padx=22)
        Tooltip(modest,
                tr("Recorta las generaciones para una máquina lenta, y la "
                   "búsqueda tarda la mitad. Se siguen cumpliendo todas las "
                   "reglas duras, pero queda menos tiempo para pulir la "
                   "conducción de voces. La población no cambia, porque "
                   "bajándola las piezas largas dejan de generarse."))

        def apply_and_close() -> None:
            # Antes de validar: la combinación del zorro no es configuración
            # válida --- una población de 1 se rechaza --- así que leída
            # después nunca llegaría a pasar nada.
            if eggs.fox_numbers({key: var.get()
                                 for key, var in self.ga_vars.items()}):
                self._close_config()
                self._egg_fox()
                return
            if not self._read_ga_config(message):
                return
            # El logro se decide acá y no al terminar una búsqueda: tocar los
            # parámetros y no generar después dejaba el logro sin dar, que es
            # justo lo que pasa cuando alguien entra a mirar la configuración.
            if achievements.ga_customised(self.ga_config,
                                          self._default_ga_config()):
                self._award({"ga_tuned"})
            self.settings["font_scale"] = float(self.font_scale_slider.get())
            self.settings["raise_cadence_odds"] = self.raise_odds_var.get()
            for key, _label, _default, _explain in self.GA_FIELDS:
                self.settings[key] = self.ga_vars[key].get()
            history.save_settings(self.settings, self.settings_path)
            self._close_config()

        self.raise_odds_var = tk.BooleanVar(
            value=bool(self.settings.get("raise_cadence_odds", False)))
        odds = ctk.CTkCheckBox(
            window, text=tr("Elevar probabilidad de cadencias especiales"),
            variable=self.raise_odds_var, font=FONT_SMALL,
            fg_color=ACCENT, hover_color=ACCENT_HOVER)
        odds.pack(anchor="w", padx=22, pady=(14, 2))
        Tooltip(odds,
                tr("Las cadencias completas (la frigia, el ciclo de Vivaldi y "
                   "el bajo cromático) aparecen casi la mitad de las veces "
                   "que se dan las condiciones, en vez de una de cada diez."))

        self._build_sound_settings(window)

        ctk.CTkLabel(window, text=tr("Accesibilidad"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=22,
                                                          pady=(16, 4))
        line = ctk.CTkFrame(window, fg_color="transparent")
        line.pack(fill="x", padx=22, pady=4)
        ctk.CTkLabel(line, text=tr("Tamaño de letra"), font=FONT_SMALL,
                     width=150, anchor="w").pack(side="left")
        self.font_scale_slider = ctk.CTkSlider(line, from_=0.8,
                                               to=self.FONT_SCALE_MAX, width=180,
                                               progress_color=ACCENT,
                                               button_color=ACCENT)
        self.font_scale_slider.set(FONT_SCALE)
        self.font_scale_slider.pack(side="left")
        self.font_scale_label = ctk.CTkLabel(line, text=f"{FONT_SCALE:.0%}",
                                             font=FONT_SMALL, width=50)
        self.font_scale_label.pack(side="left", padx=8)
        def preview_scale(value) -> None:
            """Apply the size immediately, so the user can see what they pick.

            Reading a percentage tells you nothing about whether the text is
            comfortable; the only useful preview is the interface itself at
            that size.
            """
            global FONT_SCALE
            FONT_SCALE = float(value)
            self.font_scale_label.configure(text=f"{FONT_SCALE:.0%}")
            self._rescale_fonts()
            self.settings["font_scale"] = FONT_SCALE
            history.save_settings(self.settings, self.settings_path)
            self._close_config()
            self._render()
            self._open_config()
            # Al tope del dial se ve el programa como se lo vería con
            # lentes. Va después de rearmar la pantalla, que es lo que la
            # viñeta tiene que quedar tapando.
            if eggs.glasses(FONT_SCALE, self.FONT_SCALE_MAX):
                self._egg("glasses")
                self.after(120, self._egg_glasses)

        self.font_scale_slider.configure(command=lambda v:
                                         self.font_scale_label.configure(
                                             text=f"{float(v):.0%}"))
        self.font_scale_slider.bind("<ButtonRelease-1>",
                                    lambda _e: preview_scale(
                                        self.font_scale_slider.get()))
        ctk.CTkLabel(window,
                     text=tr("Se aplica al reabrir el programa. La "
                             "configuración se guarda junto al ejecutable."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=440,
                     justify="left").pack(anchor="w", padx=22, pady=(2, 0))

        # -- el modo profesional --------------------------------------------
        #
        # Se aplica al tocarlo, como el idioma: es una decisión sobre qué
        # programa se quiere tener abierto, no un número que se ajusta y se
        # confirma con «Aceptar».
        ctk.CTkLabel(window, text=tr("Uso profesional"),
                     font=scaled(("Segoe UI Semibold", 14))
                     ).pack(anchor="w", padx=22, pady=(16, 4))
        self.professional_var = tk.BooleanVar(
            value=bool(self.settings.get("professional")))
        ctk.CTkSwitch(window, text=tr("Modo profesional"),
                      variable=self.professional_var, font=FONT_SMALL,
                      progress_color=ACCENT,
                      command=lambda: self._set_professional(
                          self.professional_var.get())
                      ).pack(anchor="w", padx=22, pady=(0, 2))
        ctk.CTkLabel(window,
                     text=tr("Sin visitas, sin apariciones y sin modo "
                             "historia: queda el programa de trabajo. La "
                             "escuelita se gradúa sin ceremonia. No se borra "
                             "nada, y al apagarlo todo vuelve donde estaba."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=440,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 6))

        # -- Volver a ver una aparición -------------------------------------
        #
        # Cada botón aparece **recién cuando esa escena ya ocurrió sola**. Una
        # aparición pasa una vez en la vida del programa y dura un minuto; que
        # no haya manera de volver a mirarla es una pérdida, pero listarlas
        # todas de entrada es peor: el panel de configuración contaría, con
        # nombre y condición, las cinco cosas que el programa esconde.
        #
        # Así el que ya la vio puede repetirla y el que no, no se entera de
        # que existe. La sección entera no se dibuja mientras no haya ninguna.
        # Quién sabe si ya ocurrió lo pregunta el registro por su llave de
        # libro, que es la única de las tres formas de guardar una aparición
        # --- una marca en `seen`, la fecha de la visión, la de la segunda
        # --- que las contesta a todas.
        seen_scenes = [
            (label, key) for label, key in
            (("La entidad", visitors.WATCHER_ALL),
             ("La visión del cruce de caminos", visitors.VISION),
             ("El cruce de caminos, otra vez", visitors.PACT),
             ("El cruce de caminos, años después", visitors.TOMB),
             ("Bach · las cinco barrocas", visitors.BACH_BAROQUE),
             ("Bach · el modo coral", visitors.BACH_CHORALE),
             ("Gregorio · el organum", visitors.GREGORY_CHANT))
            if self.visits.knows(visitors.book_key(key))
        ]
        if seen_scenes and not self.settings.get("professional"):
            ctk.CTkLabel(window, text=tr("Volver a ver"),
                         font=scaled(("Segoe UI Semibold", 14))
                         ).pack(anchor="w", padx=22, pady=(16, 2))
            ctk.CTkLabel(window,
                         text=tr("Las apariciones que ya viste. Se repiten "
                                 "enteras, como la primera vez."),
                         font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=440,
                         justify="left").pack(anchor="w", padx=22, pady=(0, 6))
            for label, key in seen_scenes:
                ctk.CTkButton(window, text=tr(label), height=32, corner_radius=10,
                              font=FONT_SMALL, fg_color="transparent",
                              border_width=1, border_color=GOLD_DIM,
                              text_color=GOLD_DIM, hover_color=SURFACE,
                              anchor="w",
                              command=lambda k=key: self._preview_scene(k)
                              ).pack(anchor="w", fill="x", padx=22, pady=2)

        ctk.CTkLabel(window, text=tr("Ayuda"),
                     font=scaled(("Segoe UI Semibold", 14))
                     ).pack(anchor="w", padx=22, pady=(16, 4))
        ctk.CTkButton(window, text=tr("Ver el tutorial otra vez"), height=34,
                      corner_radius=10, font=FONT_SMALL,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
                      hover_color=SURFACE,
                      command=lambda: (self._close_config(),
                                       self._start_tutorial())
                      ).pack(anchor="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(window,
                     text=tr("Repite el recorrido de bienvenida. Las guías de "
                             "los acordes, del pentagrama y de las reglas "
                             "vuelven a abrirse la próxima vez que llegues a "
                             "esas pantallas."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=440,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 14))

        def restore_defaults() -> None:
            """
            Volver TODO a como viene de fábrica, tamaño de letra incluido.

            El tamaño quedaba afuera: el botón restauraba los siete campos
            del algoritmo y dejaba la letra donde el usuario la hubiera
            puesto, que es justo lo que uno quiere deshacer si la subió
            demasiado y ya no puede leer nada.
            """
            for key, _label, default, _explain in self.GA_FIELDS:
                self.ga_vars[key].set(default)
            self.raise_odds_var.set(False)
            self.settings["raise_cadence_odds"] = False
            # El timbre también vuelve al de siempre. La ruta del WAV se
            # queda: no es una preferencia sino dónde está un archivo, y
            # volver a elegir la muestra no tiene por qué pedir buscarlo.
            # Guardado al momento, como cuando se lo elige en el menú: si
            # después se cierra sin «Aceptar», al reabrir volvía el anterior.
            self._remember_timbre(timbres.DEFAULT)
            self._timbre_problem = self._apply_timbre(timbres.DEFAULT)
            # Va última porque rearma el panel entero: cualquier cosa que
            # tocara widgets después de esto estaría tocando widgets muertos.
            preview_scale(1.0)

        ctk.CTkButton(buttons, text=tr("Restaurar valores por defecto"),
                      height=38, corner_radius=10, font=scaled(FONT_BODY),
                      fg_color="transparent", border_width=1,
                      border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
                      hover_color=SURFACE, command=restore_defaults
                      ).pack(side="left", padx=(22, 6))
        ctk.CTkButton(buttons, text=tr("Aceptar"), height=38, corner_radius=10,
                      font=scaled(("Segoe UI Semibold", 12)), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=apply_and_close).pack(side="right", padx=(6, 22))
        ctk.CTkButton(buttons, text=tr("Cerrar"), height=38, corner_radius=10,
                      font=scaled(FONT_BODY),
                      fg_color="transparent", border_width=1,
                      border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
                      hover_color=SURFACE, command=self._close_config
                      ).pack(side="right", padx=6)

    def _set_professional(self, on: bool) -> None:
        """
        Prender o apagar el modo profesional, al instante.

        Prendido, se va lo que estuviera esperando a la vista ---el llamado
        a la puerta del inicio---. Apagado, el vigía de la figura vuelve a
        mirar: se había quedado quieto, y sin re-armarlo el sendero no
        volvía hasta reabrir el programa.
        """
        on = bool(on)
        if on == bool(self.settings.get("professional")):
            return
        self.settings["professional"] = on
        history.save_settings(self.settings, self.settings_path)
        if on:
            self._story_knocking = False
        else:
            self._story_watching = False
            self._rearm_story_watch()
        self._close_config()
        self._render()
        self._open_config()

    def _switch_language(self, code: str) -> None:
        """
        Cambiar de idioma sin reabrir el programa.

        Se puede porque la traducción ocurre al dibujar y no al importar:
        las tablas de prosa siguen guardando el castellano y quien lo
        convierte es el `tr()` del lugar donde el texto entra a un widget.
        O sea que alcanza con volver a dibujar.

        Volver a dibujar es más que `_render()`: la cabecera y el pie se
        arman una sola vez en `_build_chrome` y no pasan por ahí, así que
        cambiando sólo el cuerpo quedaban «Historial», «Logros» y «Atrás» en
        el idioma viejo. Por eso se destruyen los cuatro marcos y se los
        vuelve a armar.

        El panel de configuración se cierra y se reabre para que se lea en
        el idioma nuevo --- y porque es hijo de la ventana, no del cuerpo, y
        sobreviviría al rearmado.
        """
        if code == i18n.language():
            return
        self.settings["language"] = code
        history.save_settings(self.settings, self.settings_path)
        i18n.set_language(code)
        self._close_config()
        # La guía abierta señala widgets que están por desaparecer, y sus
        # velos están puestos sobre la ventana: sin esto sobreviven al
        # rearmado y quedan tapando la pantalla nueva.
        self._close_guide()
        for widget in getattr(self, "_chrome", ()):
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._build_chrome()
        # El riel y el rótulo del paso salen de acá, y `_build_chrome` los
        # dejó recién nacidos y vacíos.
        self._apply_mode()
        self._render()
        self._open_config()

    def _close_config(self) -> None:
        """Dismiss the settings panel if it is showing."""
        panel = getattr(self, "config_panel", None)
        if panel is not None:
            panel.destroy()
            self.config_panel = None

    # -- el timbre de las reproducciones ------------------------------------

    #: Con qué se prueba un timbre: una cadencia corta, I–V7–I. Más que un
    #: acorde solo porque lo que el programa toca son voces que se mueven, y
    #: un timbre sostenido se juzga en cómo pasa de un acorde al siguiente.
    TIMBRE_TRIAL = ([[48, 64, 67, 72], [43, 62, 65, 71], [48, 64, 67, 72]],
                    [1.0, 1.0, 2.0])

    def _apply_timbre(self, key: str, path: str = "") -> Optional[str]:
        """
        Poner un timbre para todo lo que suene; el motivo si no se pudo.

        Si no se puede, queda sonando el de siempre ---`timbres.use` ya lo
        deja así--- y la preferencia guardada no se toca acá: un WAV en un
        disco desenchufado vuelve a andar la próxima vez que el disco esté.
        """
        try:
            timbres.use(key, path)
        except timbres.TimbreError as exc:
            return str(exc)
        except Exception as exc:                            # noqa: BLE001
            # Un archivo que revienta de una manera que el lector no prevé
            # ---memoria, un formato raro--- no puede impedir que el programa
            # abra: esto corre al arrancar. Queda el timbre de siempre.
            timbres.use(timbres.DEFAULT)
            return str(exc) or exc.__class__.__name__
        return None

    def _remember_timbre(self, key: str, path: Optional[str] = None) -> None:
        self.settings["timbre"] = key
        if path is not None:
            self.settings["timbre_path"] = path
        history.save_settings(self.settings, self.settings_path)

    def _use_instrument(self, path: str) -> None:
        """
        Lo que hace el experimentador al guardar un timbre y pedir usarlo.

        Llega por parámetro (`spectrum.Experimenter(on_instrument=...)`)
        porque el experimentador no importa la aplicación.
        """
        problem = self._apply_timbre(timbres.SAMPLE, path)
        if problem:
            messagebox.showwarning(tr("No se pudo usar el timbre"), problem)
            self._remember_timbre(timbres.DEFAULT)
            return
        self._timbre_problem = None
        self._remember_timbre(timbres.SAMPLE, path)

    def _build_sound_settings(self, window) -> None:
        """
        La sección «Sonido» del engranaje: qué timbre, probarlo, cargar uno.

        Se aplica al momento, como el idioma, y no al apretar «Aceptar»: el
        botón de probar toca lo que está elegido, y elegir algo para oírlo
        y que no suene hasta cerrar el panel no tendría sentido.
        """
        ctk.CTkLabel(window, text=tr("Sonido"),
                     font=scaled(("Segoe UI Semibold", 14))
                     ).pack(anchor="w", padx=22, pady=(16, 2))
        ctk.CTkLabel(window,
                     text=tr("El timbre de todo lo que toca el programa, "
                             "desde los resultados hasta el analizador. Todos "
                             "suenan igual de fuerte y sólo cambia el color."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=440,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 6))

        line = ctk.CTkFrame(window, fg_color="transparent")
        line.pack(fill="x", padx=22, pady=4)
        ctk.CTkLabel(line, text=tr("Timbre"), font=FONT_SMALL, width=150,
                     anchor="w").pack(side="left")
        menu = ctk.CTkOptionMenu(
            line, values=trs([item.label for item in timbres.TIMBRES]),
            width=240, font=FONT_SMALL, dropdown_font=FONT_SMALL,
            fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT)
        menu.pack(side="left")
        trial = ctk.CTkButton(
            line, text=tr("▶  Probar"), width=104, height=30,
            corner_radius=9, font=FONT_SMALL, fg_color="transparent",
            border_width=1, border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
            hover_color=SURFACE)
        trial.pack(side="left", padx=(8, 0))

        blurb = ctk.CTkLabel(window, text="", font=FONT_SMALL,
                             text_color=TEXT_MUTED, wraplength=440,
                             justify="left")
        blurb.pack(anchor="w", padx=22, pady=(2, 4))

        files = ctk.CTkFrame(window, fg_color="transparent")
        files.pack(fill="x", padx=22, pady=(2, 0))
        loader = ctk.CTkButton(
            files, text=tr("Cargar un WAV…"), width=150, height=30,
            corner_radius=9, font=FONT_SMALL, fg_color="transparent",
            border_width=1, border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
            hover_color=SURFACE)
        loader.pack(side="left")
        Tooltip(loader,
                tr("Un timbre guardado con «Guardar timbre…» en el "
                   "experimentador ya sabe qué nota es y qué tramo repetir, y "
                   "suena afinado en todo el teclado. Cualquier otro WAV "
                   "también sirve. En ese caso el programa deduce la nota "
                   "escuchándolo y repite su segunda mitad."))
        detail = ctk.CTkLabel(files, text="", font=FONT_SMALL,
                              text_color=TEXT_MUTED, wraplength=290,
                              justify="left", anchor="w")
        detail.pack(side="left", padx=(10, 0), fill="x", expand=True)

        def refresh() -> None:
            """Que el menú, la línea y el detalle digan lo que suena."""
            chosen = timbres.current()
            try:
                menu.set(tr(timbres.label_of(chosen.key)))
                blurb.configure(text=tr(timbres.blurb_of(chosen.key)))
                problem = getattr(self, "_timbre_problem", None)
                sample = chosen.sample
                if problem:
                    detail.configure(
                        text=trf("No se pudo usar el timbre guardado y suena "
                                 "el de siempre.\n{reason}",
                                 reason=problem), text_color=WARN)
                elif sample is not None:
                    root = int(round(sample.root))
                    note = i18n.note_name(root) + str(root // 12 - 1)
                    seconds = ((sample.loop_end - sample.loop_start + 1)
                               / sample.rate)
                    text = (trf("{name} · es un {note} · repite {seconds:.1f} s",
                                name=sample.name, note=note, seconds=seconds)
                            if sample.from_smpl else
                            trf("{name} · suena como un {note} (deducido "
                                "oyéndolo) · repite su segunda mitad",
                                name=sample.name, note=note))
                    detail.configure(text=text, text_color=TEXT_MUTED)
                else:
                    detail.configure(text="", text_color=TEXT_MUTED)
            except tk.TclError:
                pass

        def fail(problem: str) -> None:
            """Un archivo que no sirve: se avisa y vuelve el de siempre."""
            messagebox.showwarning(tr("No se pudo usar el timbre"), problem)
            self._timbre_problem = None
            self._remember_timbre(timbres.DEFAULT)
            refresh()

        def load() -> None:
            stored = str(self.settings.get("timbre_path", "") or "")
            folder = (os.path.dirname(stored) if stored
                      else history.default_output_directory())
            path = filedialog.askopenfilename(
                title=tr("Elegí el timbre"),
                initialdir=folder if os.path.isdir(folder) else None,
                filetypes=[(tr("Sonido WAV"), "*.wav"),
                           (tr("Todos los archivos"), "*.*")])
            if not path:
                refresh()           # el menú puede haber quedado en la muestra
                return
            problem = self._apply_timbre(timbres.SAMPLE, path)
            if problem:
                fail(problem)
                return
            self._timbre_problem = None
            self._remember_timbre(timbres.SAMPLE, path)
            refresh()

        def pick(label: str) -> None:
            key = timbres.key_for_label(i18n.untr(label))
            path = ""
            if key == timbres.SAMPLE:
                path = str(self.settings.get("timbre_path", "") or "")
                if not path:
                    load()          # todavía no hay ninguno: se lo pide
                    return
            problem = self._apply_timbre(key, path)
            if problem:
                fail(problem)
                return
            self._timbre_problem = None
            self._remember_timbre(key)
            refresh()

        def try_it() -> None:
            playing = getattr(self, "_playing", None)
            if playing is not None and playing.is_alive():
                return              # de a un sonido, como en todo el programa
            chords, durations = self.TIMBRE_TRIAL
            trial.configure(text=tr("♪  Sonando…"), state="disabled")

            def restore() -> None:
                try:
                    trial.configure(text=tr("▶  Probar"), state="normal")
                except tk.TclError:
                    pass            # el panel se cerró mientras sonaba

            self._playing = audio.play_chords(chords, durations,
                                              timbre=timbres.current())
            self._when_done(self._playing, restore)

        menu.configure(command=pick)
        trial.configure(command=try_it)
        loader.configure(command=load)
        refresh()

    #: Las dos maneras de donar, y viven acá y en ningún otro lado. Son dos
    #: porque un alias de transferencia sólo existe adentro de Argentina:
    #: quien esté en cualquier otro lado no tiene dónde pegarlo, y hasta
    #: ahora el cartel le mostraba eso y nada más.
    DONATION_ALIAS = "ilurati.ppay"
    DONATION_LINK = ("https://chordweaver.lemonsqueezy.com/checkout/buy/"
                     "f5185a7e-2962-4626-b816-bf63c6e3a7a4")

    def _open_donate(self) -> None:
        """
        Por qué el programa es gratis, y dónde donar si igual se quiere.

        Es un cartel sobre la ventana y no una ventana aparte, por lo mismo
        que la configuración: una `Toplevel` la ubica el sistema, que en dos
        monitores la puede tirar en el que no se está mirando.

        El texto explica primero y pide después, y lo pide una sola vez: un
        pedido que se repite se lee como un peaje, y acá no hay ninguno --- el
        programa es exactamente el mismo con donación y sin ella.

        Abajo, las dos maneras de hacerlo, cada una en su recuadro y con su
        rótulo: un alias de transferencia sirve adentro de Argentina y en
        ningún otro lado, así que ponerlo solo dejaba a media humanidad
        mirando un dato que no puede usar.
        """
        if getattr(self, "donate_panel", None) is not None:
            self._close_donate()
            return
        self._close_config()          # nunca dos carteles encima

        panel = ctk.CTkFrame(self, fg_color=SURFACE_LIGHT, corner_radius=16,
                             border_width=1, border_color=GOLD_DIM)
        panel.place(relx=0.5, rely=0.5, anchor="center",
                    relwidth=0.62, relheight=0.72)
        self.donate_panel = panel

        # La fila del botón se empaqueta ANTES que el texto y anclada abajo,
        # igual que en la configuración: así se queda con su franja y con la
        # letra al 180% el texto crece hacia adentro del marco con scroll en
        # vez de empujar «Cerrar» fuera del cartel.
        buttons = ctk.CTkFrame(panel, fg_color="transparent", height=56)
        buttons.pack(side="bottom", fill="x", pady=(4, 12))
        buttons.pack_propagate(False)
        window = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        window.pack(side="top", fill="both", expand=True, padx=4, pady=(4, 0))

        # El corazón y el título en el mismo renglón: eran dos renglones que
        # decían lo mismo y se comían el alto que después le falta a lo que
        # hay que leer.
        head = ctk.CTkFrame(window, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(20, 2))
        ctk.CTkLabel(head, text="♥", font=scaled(("Segoe UI", 24)),
                     text_color=GOLD).pack(side="left")
        ctk.CTkLabel(head, text=tr("Donar"),
                     font=scaled(("Segoe UI Semibold", 21))
                     ).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(window,
                     text=tr("El programa es gratis. Esto es por si querés "
                             "bancarlo igual."),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(anchor="w", padx=24, pady=(0, 12))
        # Un filete dorado debajo del encabezado: separa lo que se explica de
        # lo que se pide sin gastar un renglón de texto en decirlo. `tk.Frame`
        # y no `CTkFrame`: una línea de un píxel no necesita esquinas
        # redondeadas ni un lienzo propio.
        tk.Frame(window, background=GOLD_DIM, height=1).pack(
            fill="x", padx=24, pady=(0, 14))

        for paragraph in (
            "ChordWeaver es gratis y va a seguir siéndolo. La música es de "
            "todos, y no me parece bien cobrar por una herramienta para "
            "estudiarla.",
            "Pero el proyecto lleva tiempo y mantenerlo cuesta. Si te sirvió "
            "y querés ayudar, una donación se agradece mucho.",
            "Donar no cambia nada en el programa. No hay funciones "
            "bloqueadas.",
        ):
            ctk.CTkLabel(window, text=tr(paragraph), font=scaled(FONT_BODY),
                         text_color=TEXT_NORMAL, wraplength=560,
                         justify="left").pack(anchor="w", padx=24, pady=(0, 10))

        self._donation_card(
            window, "Desde Argentina", "Alias para transferir",
            self.DONATION_ALIAS, ("Consolas", 20), "Copiar el alias")
        self._donation_card(
            window, "Desde cualquier otro lado", "Con tarjeta, en el navegador",
            self.DONATION_LINK, ("Segoe UI", 12), "Copiar el enlace",
            open_link=True)

        ctk.CTkLabel(window,
                     text=tr("El alias queda copiado mientras el programa "
                             "esté abierto. En Windows, el portapapeles "
                             "depende de la aplicación que copió."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=560,
                     justify="left").pack(anchor="w", padx=24, pady=(4, 12))
        ctk.CTkLabel(window, text=tr("Gracias por usarlo."),
                     font=scaled(("Segoe UI", 13)), text_color=GOLD
                     ).pack(anchor="w", padx=24, pady=(0, 10))

        ctk.CTkButton(buttons, text=tr("Cerrar"), height=38, corner_radius=10,
                      font=scaled(FONT_BODY),
                      fg_color="transparent", border_width=1,
                      border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
                      hover_color=SURFACE, command=self._close_donate
                      ).pack(side="right", padx=(6, 24))

    def _donation_card(self, master, title: str, subtitle: str, value: str,
                       font, copy_label: str, open_link: bool = False) -> None:
        """
        Una de las dos maneras de donar, en su propio recuadro.

        El dato ---el alias o el enlace--- va grande y solo, porque es lo
        único del cartel que hay que llevarse: adentro de un párrafo no se
        encuentra y no se copia bien.
        """
        box = ctk.CTkFrame(master, fg_color=SURFACE, corner_radius=12,
                           border_width=1, border_color=GOLD_DIM)
        box.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(box, text=tr(title),
                     font=scaled(("Segoe UI Semibold", 13)), text_color=GOLD
                     ).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(box, text=tr(subtitle), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        ctk.CTkLabel(box, text=tr(value), font=scaled(font),
                     text_color=TEXT_NORMAL, wraplength=520, justify="left",
                     anchor="w").pack(anchor="w", fill="x", padx=16,
                                      pady=(8, 0))

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(8, 12))
        copy = ctk.CTkButton(row, text=tr(copy_label), width=142, height=30,
                             corner_radius=9, font=FONT_SMALL,
                             fg_color="transparent", border_width=1,
                             border_color=GOLD_DIM, text_color=GOLD,
                             hover_color=SURFACE_LIGHT)

        def copy_value() -> None:
            """Al portapapeles, y que el botón lo diga.

            Sin el aviso no hay manera de saber si el clic hizo algo: el
            portapapeles no se ve. El texto vuelve solo, y sólo si el cartel
            sigue abierto --- el `after` puede caer con el botón ya destruido.
            """
            try:
                self.clipboard_clear()
                self.clipboard_append(value)
            except tk.TclError:
                return
            copy.configure(text=tr("Copiado ✓"))

            def restore() -> None:
                try:
                    copy.configure(text=tr(copy_label))
                except tk.TclError:
                    pass
            self.after(1600, restore)

        copy.configure(command=copy_value)
        copy.pack(side="left")
        if open_link:
            ctk.CTkButton(row, text=tr("Abrir en el navegador"), width=180,
                          height=30, corner_radius=9, font=FONT_SMALL,
                          fg_color=GOLD_DIM, text_color=SURFACE,
                          hover_color=GOLD,
                          command=lambda: self._open_link(value)
                          ).pack(side="left", padx=(8, 0))

    @staticmethod
    def _open_link(url: str) -> None:
        """Abrir una dirección afuera. Nunca levanta: no hay a quién."""
        import webbrowser                                 # noqa: PLC0415

        try:
            webbrowser.open(url)
        except Exception:                                 # noqa: BLE001
            pass

    def _close_donate(self) -> None:
        """Bajar el cartel de las donaciones si está puesto."""
        panel = getattr(self, "donate_panel", None)
        if panel is not None:
            panel.destroy()
            self.donate_panel = None

    def _read_ga_config(self, message_label=None) -> bool:
        """Parse the gear dialog into a GAConfig. False if something is wrong."""
        try:
            config = GAConfig(
                population_size=int(self.ga_vars["population_size"].get()),
                generations=int(self.ga_vars["generations"].get()),
                elitism=int(self.ga_vars["elitism"].get()),
                tournament_size=int(self.ga_vars["tournament_size"].get()),
                mutation_rate=float(self.ga_vars["mutation_rate"].get()),
                crossover_rate=float(self.ga_vars["crossover_rate"].get()),
                uniform_crossover_share=float(
                    self.ga_vars["uniform_crossover_share"].get()
                ),
            )
        except (ValueError, KeyError):
            if message_label is not None:
                message_label.configure(text=tr("Algún valor no es un número válido."))
            return False
        if config.population_size < 10 or config.generations < 1:
            if message_label is not None:
                message_label.configure(
                    text=tr("La población tiene que ser al menos 10 y las "
                            "generaciones al menos 1.")
                )
            return False
        if config.elitism < 0:
            if message_label is not None:
                message_label.configure(
                    text=tr("El elitismo no puede ser negativo.")
                )
            return False
        if config.elitism >= config.population_size:
            if message_label is not None:
                message_label.configure(
                    text=tr("El elitismo tiene que ser menor que la población.")
                )
            return False
        # El torneo tiene que poder elegir a alguien. Con cero o menos, el
        # motor le pedía a `random.sample` una muestra vacía y la búsqueda se
        # cortaba con un error crudo de Python --- «min() iterable argument is
        # empty» --- que no nombra ni el campo ni la pantalla donde está.
        if config.tournament_size < 2:
            if message_label is not None:
                message_label.configure(
                    text=tr("El torneo tiene que ser de al menos 2.")
                )
            return False
        # Las tres tasas son probabilidades. Fuera de 0–1 el motor no falla,
        # que es peor: sigue andando y devuelve otra cosa sin decirlo.
        for key, label in (("mutation_rate", "La tasa de mutación"),
                           ("crossover_rate", "La tasa de cruce"),
                           ("uniform_crossover_share", "La proporción de "
                                                       "cruce uniforme")):
            value = getattr(config, key)
            if not 0.0 <= value <= 1.0:
                if message_label is not None:
                    message_label.configure(
                        text=trf("{label} tiene que estar entre 0 y 1.",
                                 label=label)
                    )
                return False
        self.ga_config = config
        return True

    def _go_back(self) -> None:
        if self.index == self._chords_index:
            self._snapshot_chords()
        if self.index > 0:
            self.index -= 1
            self._render()

    def _commit_screen(self) -> bool:
        """Validate and store the current screen. False blocks navigation."""
        # Keyed by screen title rather than index: the carousel changes shape
        # between modes, and positional keys silently drifted when it did.
        committers = {
            "Voces": self._commit_voices,
            "Melodía": self._commit_melody,
            "Compases": self._commit_metre,
            "Acordes": self._commit_chords,
            "Tonalidad": self._commit_harmony,
            "Parámetros": self._commit_parameters,
        }
        committer = committers.get(self.screen_titles[self.index])
        return committer() if committer else True

    # -- screen 1: genre ----------------------------------------------------

    def _screen_genre(self) -> None:
        # El botón del sendero va acá: es la primera pantalla de cualquier
        # modo, así que se llega a él sin caminar nada. Lo que promete es
        # justamente saltearse la configuración entera --- la pieza
        # sobreescribe todo lo que uno haya elegido ---, y hacerlo esperar
        # cinco pantallas era pedir justo lo que el botón anula.
        self._story_golden_button(self.body)
        self._heading(
            tr("Elegí un estilo"),
            tr("El estilo decide cómo se mueven las voces de un acorde al "
               "siguiente. Cada regla se puede ajustar después, en la "
               "pantalla de reglas."))

        # Sin `expand`: las tarjetas miden lo que mide la más alta y la franja
        # de resumen queda pegada abajo de ellas en vez de irse al pie de la
        # ventana, lejos de lo que resume.
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 6))
        offered = [(key, profile) for key, profile in GENRE_PROFILES.items()
                   if profile.selectable]
        grid.grid_columnconfigure(tuple(range(len(offered))), weight=1,
                                  uniform="genre")

        # La franja de abajo dice, en una línea, con qué queda configurado el
        # programa si se elige esa tarjeta. Antes esa información aparecía
        # recién dos pantallas más adelante, ya aplicada y sin avisar.
        self.genre_note_frame = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT,
                                             corner_radius=12)
        self.genre_note_frame.pack(fill="x", pady=(0, 4))
        self.genre_note = ctk.CTkLabel(self.genre_note_frame, text="",
                                       font=FONT_SMALL, text_color=TEXT_MUTED,
                                       wraplength=900, justify="left",
                                       anchor="w")
        self.genre_note.pack(anchor="w", fill="x", padx=16, pady=11)

        self.genre_cards: Dict[str, Card] = {}
        for position, (key, profile) in enumerate(offered):
            accent, icon = GENRE_THEMES.get(key, (ACCENT, "◆"))
            card = Card(grid, profile.label,
                        GENRE_BLURBS.get(key, profile.description),
                        command=lambda k=key: self._select_genre(k),
                        accent=accent, icon=icon,
                        points=GENRE_POINTS.get(key, ()))
            card.grid(row=0, column=position, sticky="nsew", padx=8,
                      pady=(4, 10))
            self.genre_cards[key] = card
        self._select_genre(self.genre_key, animated=False)
        self._cascade(self.genre_cards.values())

    def _genre_note_text(self, key: str) -> str:
        """Con qué valores queda armado el programa al elegir este estilo."""
        defaults = harmony.GENRE_DEFAULTS.get(key)
        if not defaults:
            return ""
        # Cada pedazo se traduce antes de pegarlo: los tres estaban
        # catalogados y salían igual en castellano con la interfaz en inglés.
        voices = ", ".join(tr(VOICE_CATALOG[voice].label)
                           for voice in defaults["voices"])
        mode = tr(harmony.MODES[defaults["mode"]].label).lower()
        sevenths = (tr("acordes de séptima por defecto") if defaults["sevenths"]
                    else tr("tríadas por defecto"))
        return (trf("Arranca con {voices} · {mode} · {sevenths}. Se puede "
                    "cambiar en las pantallas siguientes.",
                    voices=voices, mode=mode, sevenths=sevenths))

    def _apply_genre_defaults(self) -> None:
        """Set the voices, mode and colour this style normally uses."""
        defaults = harmony.GENRE_DEFAULTS.get(self.genre_key)
        if not defaults:
            return
        self.voice_keys = list(defaults["voices"])
        self.range_overrides = {}
        self._manual_colour = defaults["colour"]
        self._apply_genre_harmony_defaults(defaults)

    def _apply_genre_harmony_defaults(self, defaults=None) -> None:
        """
        Lo que el estilo deja puesto en la pantalla de tonalidad, y nada más.

        Va aparte porque «Resetear» lo vuelve a aplicar sin tocar las voces
        ni los registros: son de otra pantalla y el usuario los eligió antes
        de llegar acá.
        """
        if defaults is None:
            defaults = harmony.GENRE_DEFAULTS.get(self.genre_key)
        if not defaults:
            return
        self._sevenths = defaults["sevenths"]
        self._colour_weight = defaults["colour"]
        self._mode_key = defaults["mode"]
        self._mode_label = harmony.MODES[defaults["mode"]].label

    def _select_genre(self, key: str, animated: bool = True) -> None:
        for card_key, card in list(getattr(self, "genre_cards", {}).items()):
            try:
                card.winfo_exists()
            except tk.TclError:
                self.genre_cards.pop(card_key, None)
        self.genre_key = key
        for card_key, card in list(getattr(self, "genre_cards", {}).items()):
            try:
                card.set_selected(card_key == key, animated=animated)
            except tk.TclError:
                self.genre_cards.pop(card_key, None)
        note = getattr(self, "genre_note", None)
        if note is not None:
            try:
                accent = GENRE_THEMES.get(key, (ACCENT, ""))[0]
                note.configure(text=tr(self._genre_note_text(key)),
                               text_color=mix(TEXT_MUTED, accent, 0.35))
                self.genre_note_frame.configure(
                    fg_color=mix(SURFACE_LIGHT, accent, 0.09))
            except tk.TclError:
                self.genre_note = None

    # -- screen 2: voices ---------------------------------------------------

    def _screen_voices(self) -> None:
        self._forget_genre_settings()
        self._heading(
            tr("Elegí las voces"),
            tr("Entre 3 y 6 voces. Ninguna nota va a salir del rango de su "
               "voz. Si tus cantantes llegan más arriba o más abajo, cambiá "
               "los rangos."))

        # Los atajos, arriba de las voces que tocan: marcan las voces y les
        # ponen el registro de una vez. Se dibujan antes que las filas pero
        # se encienden después (`_mark_voice_preset`), cuando ya hay casillas
        # contra las que comparar.
        shortcuts = ctk.CTkFrame(self.body, fg_color="transparent")
        shortcuts.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(shortcuts, text=tr("Atajos"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(2, 10))
        self.voice_preset_buttons: Dict[str, ctk.CTkButton] = {}
        for preset_key, label, blurb, _voices in self.VOICE_PRESETS:
            button = ctk.CTkButton(
                shortcuts, text=tr(label), height=30, width=10,
                corner_radius=15, font=FONT_SMALL, fg_color="transparent",
                border_width=1, border_color=BORDER_SOFT,
                text_color=TEXT_NORMAL, hover_color=SURFACE_RAISED,
                command=lambda k=preset_key: self._apply_voice_preset(k))
            button.pack(side="left", padx=(0, 8))
            Tooltip(button, tr(blurb))
            self.voice_preset_buttons[preset_key] = button

        container = ctk.CTkFrame(self.body, fg_color="transparent")
        container.pack(fill="both", expand=True)

        self.voice_check_vars: Dict[str, tk.BooleanVar] = {}
        self.range_entries: Dict[str, Tuple[ctk.CTkEntry, ctk.CTkEntry]] = {}
        self.range_vars: Dict[str, Tuple[tk.StringVar, tk.StringVar]] = {}
        self.range_rulers: Dict[str, tk.Canvas] = {}
        # Lo que se ve en las casillas es el registro con el que la voz va a
        # cantar, no el del catálogo: volviendo a esta pantalla después de
        # aplicar un atajo, las casillas mostraban los rangos de fábrica y
        # «Siguiente» los releía de ahí --- el atajo se perdía sin aviso.
        shown_ranges = self._shown_voice_ranges()

        # Organum is a modal device, so the choice only appears where it
        # means something. The harmonising mode does not ask: there the vox
        # principalis is the line the user wrote, and nothing else could be.
        organum = self.genre_key == "gregorian" and self.mode in ("manual", "random")
        self.principalis_var = None
        if organum:
            ctk.CTkLabel(
                self.body,
                text=tr("Organum. Marcá la voz que lleva el canto (vox "
                        "principalis). La de abajo va a ser la vox organalis "
                        "y la va a seguir en paralelo, a la cuarta, la quinta "
                        "o la octava. No puede ser la más grave, porque "
                        "necesita una voz debajo."),
                font=FONT_SMALL, text_color=ACCENT, wraplength=760,
                justify="left").pack(anchor="w", pady=(0, 10))
            self.principalis_var = tk.StringVar(value=self._default_principalis())
            # Con cuál se dibujó la pantalla. Es contra esto que se compara
            # después para saber si el usuario la movió, y no contra un
            # valor fijo que puede no ser el que vio.
            self._principalis_shown = self.principalis_var.get()

        for row, (key, voice) in enumerate(VOICE_CATALOG.items()):
            frame = ctk.CTkFrame(container, fg_color=SURFACE_LIGHT, corner_radius=11)
            frame.pack(fill="x", pady=4)

            var = tk.BooleanVar(value=key in self.voice_keys)
            self.voice_check_vars[key] = var
            var.trace_add("write", lambda *_: self._mark_voice_preset())
            ctk.CTkCheckBox(frame, text=tr(voice.label), variable=var, width=170,
                            font=FONT_BODY, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER).pack(side="left", padx=14, pady=10)

            if organum:
                # A radio button rather than a checkbox: there is exactly one
                # vox principalis, and sharing a single variable is what makes
                # ticking one untick the rest without any bookkeeping.
                principalis = ctk.CTkRadioButton(
                    frame, text=tr("vox principalis"), value=key,
                    variable=self.principalis_var, width=140,
                    font=FONT_SMALL, fg_color=ACCENT,
                    hover_color=ACCENT_HOVER)
                principalis.pack(side="left", padx=(0, 10))
                Tooltip(principalis,
                        trf("{label} lleva el canto. La voz de abajo lo dobla "
                            "en paralelo.",
                            label=tr(voice.label)))

            ctk.CTkLabel(frame, text=tr("rango"), font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(side="left", padx=(10, 6))
            # Con variable y no con `insert`: es lo que deja enterarse de que
            # el usuario escribió algo, para apagar el atajo que estaba
            # encendido.
            low_shown, high_shown = shown_ranges[key]
            low_var = tk.StringVar(value=note_name(low_shown))
            high_var = tk.StringVar(value=note_name(high_shown))
            low = ctk.CTkEntry(frame, width=64, font=FONT_SMALL,
                               textvariable=low_var)
            low.pack(side="left")
            ctk.CTkLabel(frame, text="–", text_color=TEXT_MUTED).pack(side="left", padx=4)
            high = ctk.CTkEntry(frame, width=64, font=FONT_SMALL,
                                textvariable=high_var)
            high.pack(side="left")
            self.range_entries[key] = (low, high)
            self.range_vars[key] = (low_var, high_var)
            for text_var in (low_var, high_var):
                text_var.trace_add("write", lambda *_: self._mark_voice_preset())
            # El registro dibujado sobre una regla de teclado común a todas
            # las filas: con los números solos no se veía dónde se pisan
            # dos voces ni cuánto le queda a cada una de margen.
            ruler = tk.Canvas(frame, height=30, bg=SURFACE_LIGHT,
                              highlightthickness=0, bd=0)
            ruler.pack(side="left", fill="x", expand=True, padx=(22, 18))
            ruler.bind("<Configure>", lambda _e: self._draw_voice_ranges())
            self.range_rulers[key] = ruler

        self.voice_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                       text_color=WARN)
        self.voice_hint.pack(anchor="w", pady=(10, 0))
        self._mark_voice_preset()

    #: Los atajos de la pantalla de voces: ``(clave, nombre, para qué,
    #: voces)``, cada voz ``(voz del catálogo, grave, aguda)``. Las voces
    #: son las del catálogo porque el motor sabe de esas y nada más: un
    #: piano son cuatro líneas igual que un coro, con otros registros.
    #:
    #: * **Canto**: los ámbitos corales de manual (Kostka-Payne), más
    #:   angostos que los del catálogo, que son los de una voz entrenada al
    #:   límite.
    #: * **Piano**: cuatro voces de teclado. Bajan más que un coro ---la mano
    #:   izquierda llega al do grave sin esfuerzo--- y el soprano sube hasta
    #:   el do agudo; el reparto entre las manos lo resuelve el pianista.
    #: * **Cuarteto de cuerdas**: violonchelo, viola y los dos violines, con
    #:   el piso de la cuerda más grave de cada uno y techos de primera y
    #:   tercera posición, que es donde un cuarteto toca un coral.
    VOICE_PRESETS = (
        ("satb", N("Canto (SATB)"),
         N("Coro a cuatro voces con los ámbitos de manual: soprano do4–sol5, "
           "contralto sol3–re5, tenor do3–sol4, bajo mi2–do4."),
         (("B", "E2", "C4"), ("T", "C3", "G4"), ("A", "G3", "D5"),
          ("S", "C4", "G5"))),
        ("piano", N("Piano"),
         N("Cuatro voces de teclado, con más registro que un coro. Bajo "
           "do2–do4, tenor sol2–sol4, contralto re3–re5, soprano sol3–do6."),
         (("B", "C2", "C4"), ("T", "G2", "G4"), ("A", "D3", "D5"),
          ("S", "G3", "C6"))),
        ("quartet", N("Cuarteto de cuerdas"),
         N("Violonchelo do2–mi4, viola do3–do5, segundo violín sol3–mi5 y "
           "primer violín sol3–la5: cada uno desde su cuerda más grave."),
         (("B", "C2", "E4"), ("T", "C3", "C5"), ("A", "G3", "E5"),
          ("S", "G3", "A5"))),
    )

    @classmethod
    def voice_preset(cls, key: str) -> Tuple[List[str], Dict[int, Tuple[int, int]]]:
        """
        Las voces y los registros de un atajo, como los deja `_commit_voices`.

        Ordenadas como las ordena el motor ---por la nota grave del
        catálogo--- y con los registros por posición, que es como los lee
        `session.build_settings`.
        """
        preset = next(p for p in cls.VOICE_PRESETS if p[0] == key)
        ordered = sorted(preset[3], key=lambda v: VOICE_CATALOG[v[0]].low)
        return ([voice for voice, _low, _high in ordered],
                {index: (parse_note_name(low), parse_note_name(high))
                 for index, (_voice, low, high) in enumerate(ordered)})

    def _shown_voice_ranges(self) -> Dict[str, Tuple[int, int]]:
        """El registro de cada voz del catálogo, con lo que el usuario cambió."""
        shown = {key: (voice.low, voice.high)
                 for key, voice in VOICE_CATALOG.items()}
        ordered = sorted(self.voice_keys, key=lambda k: VOICE_CATALOG[k].low)
        for index, key in enumerate(ordered):
            if index in self.range_overrides:
                shown[key] = self.range_overrides[index]
        return shown

    def _apply_voice_preset(self, key: str) -> None:
        """Marcar las voces de un atajo y ponerles su registro."""
        preset = next((p for p in self.VOICE_PRESETS if p[0] == key), None)
        if preset is None:
            return
        wanted = {voice: (low, high) for voice, low, high in preset[3]}
        # Mientras se escriben las casillas, cada una dispara la comparación
        # con los atajos; a mitad de camino no coincide ninguno y los
        # botones parpadeaban. Se compara una sola vez, al final.
        self._presetting = True
        try:
            for voice_key, var in self.voice_check_vars.items():
                var.set(voice_key in wanted)
                low_var, high_var = self.range_vars[voice_key]
                if voice_key in wanted:
                    low, high = wanted[voice_key]
                else:
                    low = note_name(VOICE_CATALOG[voice_key].low)
                    high = note_name(VOICE_CATALOG[voice_key].high)
                low_var.set(low)
                high_var.set(high)
        except tk.TclError:
            return
        finally:
            self._presetting = False
        try:
            self.voice_hint.configure(text="")
        except tk.TclError:
            pass
        self._mark_voice_preset()

    def _voice_preset_matching(self) -> Optional[str]:
        """
        Qué atajo describe exactamente lo que está en pantalla, si alguno.

        Se pregunta mirando las casillas y no recordando qué botón se
        apretó: así tocar a mano una voz apaga el atajo, y armar a mano lo
        mismo que un atajo lo enciende --- el botón dice la verdad sobre lo
        que se va a cantar, no sobre la historia de los clicks.
        """
        try:
            chosen = {k for k, v in self.voice_check_vars.items() if v.get()}
            ranges = {}
            for key in chosen:
                low_var, high_var = self.range_vars[key]
                ranges[key] = (parse_note_name(low_var.get()),
                               parse_note_name(high_var.get()))
        except (ValueError, KeyError, tk.TclError):
            return None
        for preset_key, _label, _blurb, voices in self.VOICE_PRESETS:
            if chosen != {voice for voice, _low, _high in voices}:
                continue
            if all(ranges[voice] == (parse_note_name(low), parse_note_name(high))
                   for voice, low, high in voices):
                return preset_key
        return None

    #: De dónde a dónde va la regla de los registros, en MIDI: del do2 al do6
    #: entra hasta el piano de los atajos. Si alguien escribe algo más allá
    #: la regla se estira.
    RULER_SPAN = (36, 84)

    def _draw_voice_ranges(self) -> None:
        """Las barras de registro de la pantalla de voces, una por fila."""
        rulers = getattr(self, "range_rulers", {})
        if not rulers:
            return
        ranges: Dict[str, Optional[Tuple[int, int]]] = {}
        for key, (low_var, high_var) in self.range_vars.items():
            try:
                low = parse_note_name(low_var.get().strip())
                high = parse_note_name(high_var.get().strip())
                ranges[key] = (min(low, high), max(low, high))
            except Exception:                               # noqa: BLE001
                ranges[key] = None
        known = [r for r in ranges.values() if r is not None]
        start = min([self.RULER_SPAN[0]] + [r[0] for r in known])
        end = max([self.RULER_SPAN[1]] + [r[1] for r in known])
        last = list(rulers)[-1]
        for key, canvas in rulers.items():
            try:
                canvas.delete("all")
                width = max(60, canvas.winfo_width())
            except tk.TclError:
                continue
            pad = 6

            def x_of(midi: float) -> float:
                return pad + (midi - start) / max(1, end - start) * (width - 2 * pad)

            # Un trazo tenue en cada do: la regla es un teclado, y el do es
            # la tecla con la que se cuenta.
            for midi in range(start - start % 12 + 12 * (start % 12 > 0),
                              end + 1, 12):
                x = x_of(midi)
                canvas.create_line(x, 3, x, 27 if key != last else 19,
                                   fill=BORDER_SOFT)
                if key == last:
                    canvas.create_text(x, 25, text=note_name(midi),
                                       fill=TEXT_MUTED, font=("Segoe UI", 8))
            span = ranges.get(key)
            if span is None:
                continue
            chosen = self.voice_check_vars[key].get()
            lane = self.STAFF_LANES.get(key, 0)
            colour = (VOICE_COLOURS[min(3, 3 - lane)] if chosen
                      else mix(SURFACE_LIGHT, TEXT_MUTED, 0.35))
            canvas.create_line(x_of(span[0]), 12, x_of(span[1]), 12,
                               fill=colour, width=8, capstyle="round")

    def _mark_voice_preset(self) -> None:
        """Encender el botón del atajo que coincide, y apagar los demás."""
        if getattr(self, "_presetting", False):
            return
        self._draw_voice_ranges()
        matching = self._voice_preset_matching()
        for key, button in getattr(self, "voice_preset_buttons", {}).items():
            on = key == matching
            try:
                button.configure(
                    fg_color=ACCENT if on else "transparent",
                    border_color=ACCENT if on else BORDER_SOFT,
                    text_color="#FFFFFF" if on else TEXT_NORMAL,
                    hover_color=ACCENT_HOVER if on else SURFACE_RAISED)
            except tk.TclError:
                pass

    def _default_principalis(self) -> str:
        """
        Qué voz aparece marcada como vox principalis al abrir la pantalla.

        Tiene que ser una del conjunto y no la más grave: la organalis es la
        que queda inmediatamente debajo, y sin nadie debajo no hay organum.
        Estaba fijo en el alto, que justamente no está en el trío que el
        gregoriano trae por defecto --- bajo, tenor y soprano ---, así que
        "Siguiente" rebotaba con un error que el usuario no había cometido y
        del que no había manera de salir sin tocar las voces.
        """
        ordered = sorted(self.voice_keys, key=lambda k: VOICE_CATALOG[k].low)
        if not ordered:
            return "A"
        remembered = getattr(self, "_principalis_key", None)
        if remembered in ordered and ordered.index(remembered) > 0:
            return remembered
        return ordered[1] if len(ordered) > 1 else ordered[0]

    def _commit_voices(self) -> bool:
        chosen = [k for k, v in self.voice_check_vars.items() if v.get()]
        if not 3 <= len(chosen) <= 6:
            self.voice_hint.configure(
                text=trf("Elegiste {chosen} voces. Tienen que ser entre 3 "
                         "y 6.",
                         chosen=len(chosen))
            )
            return False

        overrides: Dict[int, Tuple[int, int]] = {}
        ordered = sorted(chosen, key=lambda k: VOICE_CATALOG[k].low)
        for position, key in enumerate(ordered):
            low_entry, high_entry = self.range_entries[key]
            try:
                low = parse_note_name(low_entry.get())
                high = parse_note_name(high_entry.get())
            except ValueError:
                self.voice_hint.configure(
                    text=trf("El rango de {label} no se entiende. Usá "
                             "nombres tipo C4, Bb3, F#5.",
                             label=tr(VOICE_CATALOG[key].label))
                )
                return False
            if low >= high:
                self.voice_hint.configure(
                    text=trf("En {label} la nota grave tiene que ser menor "
                             "que la aguda.",
                             label=tr(VOICE_CATALOG[key].label))
                )
                return False
            overrides[position] = (low, high)

        if getattr(self, "principalis_var", None) is not None:
            chosen_principalis = self.principalis_var.get()
            if chosen_principalis not in ordered:
                self.voice_hint.configure(
                    text=trf("Marcaste {label} como vox principalis, pero "
                             "esa voz no está en el conjunto.",
                             label=tr(VOICE_CATALOG[chosen_principalis].label))
                )
                return False
            if ordered.index(chosen_principalis) == 0:
                self.voice_hint.configure(
                    text=trf("{label} es la voz más grave del conjunto, "
                             "así que no queda ninguna debajo para hacer "
                             "de vox organalis. Elegí una voz más aguda.",
                             label=tr(VOICE_CATALOG[chosen_principalis].label))
                )
                return False

        self.voice_keys = ordered
        self.range_overrides = overrides

        if getattr(self, "principalis_var", None) is not None:
            try:
                chosen = self.principalis_var.get()
            except tk.TclError:
                chosen = None
            if chosen is not None:
                # "Cambiar" es moverla: se compara con la que estaba marcada
                # al dibujar la pantalla, que es de donde salió el radio.
                if chosen != getattr(self, "_principalis_shown", None):
                    self._award({"principalis_changed"})
                self._principalis_key = chosen
        return True

    # -- screen 3: metre ----------------------------------------------------

    def _screen_metre(self) -> None:
        self._heading(
            tr("Elegí el compás y el largo"),
            tr("Cada compás puede tener su propia métrica, y el cambio queda "
               "escrito en la partitura."))

        top = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT, corner_radius=11)
        top.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(top, text=tr("Métrica base"), font=FONT_BODY).pack(side="left",
                                                                   padx=(14, 8), pady=12)
        self.signature_menu = ctk.CTkOptionMenu(
            top, values=TIME_SIGNATURES, width=90, fg_color=ACCENT,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=lambda _v: self._rebuild_bar_rows(),
        )
        self.signature_menu.set(self.base_time_signature)
        self.signature_menu.pack(side="left")

        ctk.CTkLabel(top, text=tr("Compases"), font=FONT_BODY).pack(side="left",
                                                                padx=(26, 8))
        self.bar_count_entry = ctk.CTkEntry(top, width=60)
        self.bar_count_entry.insert(0, str(min(self.bar_count, MAX_BARS)))
        self.bar_count_entry.pack(side="left")
        # El tope dicho de antemano, al lado de donde se teclea. El aviso de
        # `metre_hint` llega cuando el número ya se recortó, que es tarde.
        ctk.CTkLabel(top, text=trf("máx. {MAX_BARS}", MAX_BARS=MAX_BARS), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(8, 0))
        ctk.CTkButton(top, text=tr("Aplicar"), width=80, fg_color="transparent",
                      border_width=1, border_color=TEXT_MUTED,
                      hover_color=SURFACE, command=self._rebuild_bar_rows
                      ).pack(side="left", padx=12)

        self.bars_frame = ctk.CTkScrollableFrame(self.body, fg_color="transparent",
                                                 height=340)
        self.bars_frame.pack(fill="both", expand=True)
        self.metre_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                       text_color=WARN)
        self.metre_hint.pack(anchor="w", pady=(8, 0))
        self._rebuild_bar_rows()

    def _rebuild_bar_rows(self) -> None:
        try:
            count = int(self.bar_count_entry.get())
        except ValueError:
            count = self.bar_count
        asked = count
        count = max(1, min(MAX_BARS, count))
        self.bar_count = count
        # Recortar en silencio deja al usuario mirando 32 filas donde pidió
        # 50 sin nada que le diga por qué. Y el número tecleado se corrige,
        # porque si no la casilla sigue diciendo 50 y el próximo "Aplicar"
        # vuelve a recortar: parecería que el botón no hace nada.
        if self.bar_count_entry.get().strip() != str(count):
            self.bar_count_entry.delete(0, "end")
            self.bar_count_entry.insert(0, str(count))
        hint = getattr(self, "metre_hint", None)
        if hint is not None:
            hint.configure(
                text=(trf("Pediste {asked}, pero el máximo son {MAX_BARS} "
                          "compases.",
                          asked=asked, MAX_BARS=MAX_BARS)
                      if asked > MAX_BARS else ""))
        self.base_time_signature = self.signature_menu.get()

        # Las filas se **reusan**. Este método se llama con cada "Aplicar" y
        # con cada cambio de métrica base, y destruía las sesenta y cuatro
        # filas para volver a crearlas idénticas: pasar de ocho a doce
        # compases costaba doce filas nuevas en vez de cuatro. La caché va
        # atada al marco que las contiene, porque `_screen_metre` arma un
        # `bars_frame` nuevo en cada render y unas filas colgadas del marco
        # anterior serían widgets muertos.
        if getattr(self, "_bar_rows_frame", None) is not self.bars_frame:
            self._bar_rows_frame = self.bars_frame
            self.bar_rows: List[dict] = []

        # Las que sobran se esconden, no se mueren: bajar el número de
        # compases y volver a subirlo es lo más común que se hace acá.
        for row in self.bar_rows[count:]:
            row["frame"].grid_remove()

        # Un mosaico y no una fila por compás: con la fila a todo el ancho,
        # cuatro compases ya ocupaban la pantalla y el desplegable quedaba
        # perdido en una franja vacía. Así entran los treinta y dos.
        self.bars_frame.grid_columnconfigure(tuple(range(BAR_TILES)),
                                             weight=1, uniform="baldosa")
        self.bar_signature_menus: List[DurationPicker] = []
        for index in range(count):
            if index < len(self.bar_rows):
                row = self.bar_rows[index]
            else:
                row = self._build_bar_row(index)
                self.bar_rows.append(row)
            row["frame"].grid(row=index // BAR_TILES, column=index % BAR_TILES,
                              sticky="nsew", padx=5, pady=5)
            existing = (self.bar_signatures[index]
                        if index < len(self.bar_signatures) else None)
            row["menu"].set(existing or self.base_time_signature)
            self._paint_bar_tile(row)
            self.bar_signature_menus.append(row["menu"])

    def _build_bar_row(self, index: int) -> dict:
        """
        Una fila de la pantalla de compases: el número y su métrica.

        El marco sigue siendo un ``CTkFrame`` porque su esquina redondeada se
        ve --- una fila mide cuarenta píxeles de alto y ocupa todo el ancho,
        que es justo donde once píxeles de radio se notan. Lo que se fue son
        los dos que no se distinguen de su versión pelada y sí se pagan: un
        ``CTkLabel``, que por dentro es un marco con un canvas y una etiqueta,
        y sobre todo el ``CTkOptionMenu``, que **construye su propio menú
        desplegable** por fila. Es el mismo número que ya se midió en la
        pantalla de acordes: 27 ms por selector, y acá hay hasta sesenta y
        cuatro. `DurationPicker` comparte un solo menú para toda la ventana.
        """
        frame = ctk.CTkFrame(self.bars_frame, fg_color=SURFACE_LIGHT,
                             corner_radius=11, border_width=1,
                             border_color=BORDER_SOFT)
        inner = tk.Frame(frame, bg=SURFACE_LIGHT)
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        tk.Label(inner, text=str(index + 1),
                 font=scaled(("Segoe UI Semibold", 18)), fg=ACCENT,
                 bg=SURFACE_LIGHT, pady=0).pack(side="left", anchor="n")
        side = tk.Frame(inner, bg=SURFACE_LIGHT)
        side.pack(side="right", anchor="n")
        row: dict = {"frame": frame, "border": BORDER_SOFT}
        menu = DurationPicker(side, TIME_SIGNATURES, width=6,
                              background=SURFACE_RAISED,
                              command=lambda _v, r=row: self._paint_bar_tile(r))
        menu.pack(anchor="e", ipady=3)
        beats = tk.Canvas(side, width=BEAT_DOTS_WIDTH, height=7,
                          bg=SURFACE_LIGHT, highlightthickness=0, bd=0)
        beats.pack(anchor="e", pady=(7, 0))
        row.update(menu=menu, beats=beats)
        return row

    def _paint_bar_tile(self, row: dict) -> None:
        """
        Los tiempos del compás como puntos, y el borde si cambia de métrica.

        Los compuestos van agrupados de a tres --- un 6/8 son dos tiempos de
        tres corcheas, no seis tiempos ---, que es justamente lo que el
        número solo no deja ver. Y el compás que cambia de métrica respecto
        de la base se enciende con el color del modo: un cambio de compás
        en el medio de la pieza tiene que verse de lejos.
        """
        try:
            signature = row["menu"].get()
            beats, _, unit = signature.partition("/")
            beats, unit = int(beats), int(unit or 4)
            canvas = row["beats"]
            canvas.delete("all")
            group = 3 if unit == 8 and beats % 3 == 0 and beats > 3 else beats
            x = BEAT_DOTS_WIDTH - 3.5
            for index in reversed(range(beats)):
                canvas.create_oval(x - 2.5, 1, x + 2.5, 6, width=0,
                                   fill=ACCENT if index % group == 0
                                   else TEXT_MUTED)
                x -= 7 + (4 if index % group == 0 else 0)
            base = getattr(self, "signature_menu", None)
            changed = base is not None and signature != base.get()
            border = ACCENT if changed else BORDER_SOFT
            if row.get("border") != border:
                row["frame"].configure(border_color=border)
                row["border"] = border
        except (tk.TclError, ValueError):
            pass

    def _commit_metre(self) -> bool:
        self.bar_signatures = [menu.get() for menu in self.bar_signature_menus]
        self.base_time_signature = self.signature_menu.get()
        return True

    # -- screen 4: chords ---------------------------------------------------

    def _screen_chords(self) -> None:
        self._heading(
            tr("Escribí la progresión"),
            tr("En cifrado americano, por ejemplo Cmaj7, F#m7b5, Bb13 o C/G. "
               "Las duraciones de cada compás tienen que sumar exacto. Para "
               "un acorde sin nombre, usá el piano."))

        toolbar = ctk.CTkFrame(self.body, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 10))
        import_button = ctk.CTkButton(
            toolbar, text=tr("Importar partitura…"), width=170, height=34,
            corner_radius=9, fg_color="transparent", border_width=1,
            border_color=BORDER_SOFT, text_color=TEXT_NORMAL,
            hover_color=SURFACE_LIGHT, command=self._import_score)
        import_button.pack(side="left")
        # La progresión entera en un renglón, como en una hoja de acordes:
        # con los compases en tarjetas, es lo único que deja leerla de un
        # vistazo. Se rehace con cada tecla y cuesta un `join`.
        strip = ctk.CTkFrame(toolbar, fg_color=SURFACE_LIGHT, corner_radius=9,
                             border_width=1, border_color=BORDER_SOFT,
                             height=34)
        strip.pack(side="left", fill="x", expand=True, padx=(12, 0))
        strip.pack_propagate(False)
        self.chord_preview = FlatLabel(
            strip, text="", font=scaled(("Segoe UI Semibold", 12)),
            text_color=TEXT_NORMAL, background=SURFACE_LIGHT)
        self.chord_preview.pack(side="left", fill="x", expand=True,
                                padx=14, pady=6)
        Tooltip(import_button,
                tr("Carga los acordes de un MusicXML con su ritmo. El "
                   "programa puede reacomodar las voces, salvo en los acordes "
                   "con candado."))

        # Sin adornos en el Organizador. Acá la progresión la escribe el
        # usuario acorde por acorde, y el adorno metía notas que nadie pidió
        # sobre acordes que ya estaban decididos: no sumaba nada que se
        # pudiera controlar desde esta pantalla. El motor los recibe
        # apagados, y apagados a propósito --- ver `_run_search`.

        self.chords_frame = ctk.CTkScrollableFrame(self.body, fg_color="transparent",
                                                   height=380)
        self.chords_frame.pack(fill="both", expand=True)

        self.chord_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                       text_color=WARN, wraplength=940, justify="left")
        self.chord_hint.pack(anchor="w", pady=(8, 0))
        # La consigna del tramo, si el sendero está esperando algo acá. El
        # relato guía en todas las pantallas donde pide algo: adivinar no es
        # parte de lo que se supone que enseña.
        self._story_manual_notice()

        self._rebuild_chord_rows()
        # Después de las filas: el primer paso de la guía señala la primera
        # casilla, y antes de esto no existe ninguna.
        self._maybe_guide("chords")

    def _snapshot_chords(self) -> None:
        """
        Copy what is typed into the chord rows into a plain-data model.

        The carousel destroys and rebuilds each screen's widgets on every
        render, so anything held only in a widget disappears the moment the
        user steps away. That silently wiped both the typed symbols and the
        padlocks: you came back, retyped the chords, and the lock was gone
        without any sign that it had been dropped.
        """
        rows = getattr(self, "chord_rows", None)
        if not rows:
            return
        snapshot: Dict[int, List[dict]] = {}
        for bar_index, row in enumerate(rows):
            items = []
            for record in row["entries"]:
                try:
                    items.append({
                        "symbol": record["entry"].get(),
                        "duration": record["duration"].get(),
                        "custom": record["custom"],
                        "locked": record["locked"],
                        "imported_voicing": record.get("imported_voicing"),
                    })
                except tk.TclError:
                    # A dead widget means this snapshot would be a lie.
                    # Keeping whatever was stored last is always better than
                    # replacing it with blanks.
                    return
            snapshot[bar_index] = items
        self.saved_chords = snapshot

    def _import_score(self) -> None:
        """Load a MusicXML file into the chord rows."""
        path = filedialog.askopenfilename(
            title=tr("Elegí una partitura"),
            filetypes=[(tr("Partituras"), "*.musicxml *.xml *.mxl"),
                       (tr("Todos los archivos"), "*.*")],
            initialdir=history.default_output_directory(),
        )
        if not path:
            return
        try:
            score = importer.read_musicxml(path)
        except importer.ImportError_ as exc:
            messagebox.showerror(tr("No se pudo importar"), str(exc))
            return

        if score.voice_count != len(self.voice_keys):
            if not messagebox.askyesno(
                tr("Cantidad de voces distinta"),
                trf("La partitura tiene {voice_count} voces y elegiste "
                    "{voice_keys}. Los acordes se cargan igual, repartidos "
                    "entre tus voces. ¿Seguimos?",
                    voice_count=score.voice_count,
                    voice_keys=len(self.voice_keys)),
            ):
                return

        # Rebuild the bars from the file, then fill them with what it holds.
        bars = sorted({chord.bar_index for chord in score.chords})
        self.bar_count = max(1, len(bars))
        self.base_time_signature = f"{score.beats}/{score.beat_type}"
        self.bar_signatures = [self.base_time_signature] * self.bar_count

        renumber = {bar: index for index, bar in enumerate(bars)}
        saved: Dict[int, List[dict]] = {}
        for chord in score.chords:
            bar = renumber[chord.bar_index]
            label = next((l for l, v in DURATION_LABELS
                          if abs(v - chord.duration_quarters) < 1e-6), None)
            saved.setdefault(bar, []).append({
                "symbol": chord.symbol,
                "duration": label or "Blanca (2)",
                "custom": None,
                # The arrangement read from the file is offered to the
                # padlock but not applied: importing is for re-voicing, so
                # the search stays free unless the user pins a chord.
                "locked": None,
                "imported_voicing": list(chord.pitches),
            })
        self.saved_chords = saved
        self._render()
        self._award({"import_score"})

        message = trf("Se cargaron {chords} acordes.",
                      chords=len(score.chords))
        # Una partitura trae notas, no cifrados: el nombre de cada acorde se
        # deduce de lo que suena, y eso no siempre tiene una sola respuesta.
        # Una nota de paso o de adorno puede cambiarle la calidad a un acorde,
        # y el bajo se lee como inversión, así que lo escrito vuelve con
        # barra aunque en el original no la tuviera. Conviene decirlo acá y
        # no que se descubra mirando la progresión.
        message += "\n\n" + tr(
            "Los cifrados se deducen de las notas, así que puede haber "
            "inversiones de más o algún acorde con otro nombre. Revisalos "
            "antes de generar.")
        if score.warnings:
            message += "\n\n" + "\n".join(score.warnings)
        messagebox.showinfo(tr("Partitura importada"), message)

    def _rebuild_chord_rows(self) -> None:
        # Deliberately does NOT snapshot: by the time the screen re-renders
        # the previous widgets are already destroyed, so reading them would
        # produce an empty snapshot and overwrite the good one taken on the
        # way out.
        for child in self.chords_frame.winfo_children():
            child.destroy()
        self.chord_rows = []
        # Dos compases por renglón, como en una hoja de acordes: uno debajo
        # del otro, la progresión se leía como un formulario y no como
        # música, y ocho compases ya no entraban en la pantalla.
        self.chords_frame.grid_columnconfigure((0, 1), weight=1,
                                               uniform="compas")

        for bar_index in range(self.bar_count):
            signature = self._signature_for(bar_index)
            bar_frame = ctk.CTkFrame(self.chords_frame, fg_color=SURFACE_LIGHT,
                                     corner_radius=12, border_width=1,
                                     border_color=BORDER_SOFT)
            bar_frame.grid(row=bar_index // 2, column=bar_index % 2,
                           sticky="nsew", padx=(0, 6) if bar_index % 2 == 0
                           else (6, 0), pady=6)

            # De acá para abajo va todo pelado. El marco del compás se queda
            # en `CTkFrame` porque su esquina redondeada se ve; lo de adentro
            # es `tk` puro: un compás lleva una docena de piezas y los
            # compases los elige el usuario. Ver `FlatButton`.
            head = tk.Frame(bar_frame, bg=SURFACE_LIGHT)
            head.pack(fill="x", padx=14, pady=(12, 8))
            FlatLabel(head, text=str(bar_index + 1),
                      font=scaled(("Segoe UI Semibold", 20)),
                      text_color=ACCENT).pack(side="left")
            FlatLabel(head, text=tr("compás"), text_color=TEXT_MUTED
                      ).pack(side="left", padx=(8, 0), pady=(8, 0))
            tk.Label(head, text=str(signature), font=FONT_SMALL,
                     fg=TEXT_NORMAL, bg=SURFACE_RAISED, padx=7, pady=1
                     ).pack(side="left", padx=(8, 0), pady=(8, 0))
            fill_label = FlatLabel(head, text="", text_color=TEXT_MUTED)
            fill_label.pack(side="right", pady=(8, 0))
            meter = tk.Canvas(head, width=METER_WIDTH, height=8,
                              bg=SURFACE_LIGHT, highlightthickness=0, bd=0)
            meter.pack(side="right", padx=(0, 10), pady=(8, 0))

            slots_frame = tk.Frame(bar_frame, bg=SURFACE_LIGHT)
            slots_frame.pack(fill="x", padx=14)
            add = FlatButton(slots_frame, N("+ acorde"),
                             lambda b=bar_index: self._add_chord(b),
                             width=0, border=BORDER_SOFT,
                             hover=SURFACE_RAISED, background=SURFACE_LIGHT)
            add.configure(text_color=TEXT_MUTED, pady=3)
            add.pack(fill="x", pady=(2, 12))

            self.chord_rows.append({
                "bar_index": bar_index,
                "frame": slots_frame,
                "fill_label": fill_label,
                "meter": meter,
                "add": add,
                "entries": [],
            })
            saved = getattr(self, "saved_chords", {}).get(bar_index)
            if saved:
                for item in saved:
                    self._add_chord(
                        bar_index,
                        duration=dict(DURATION_LABELS).get(item["duration"], 2.0),
                        refresh=False,
                        initial=item,
                    )
                self._refresh_fill(bar_index)
                continue

            # Fill the bar with whichever duration divides it evenly, trying
            # half notes first and falling back to shorter values. Picking by
            # size alone breaks on odd metres: 3/4 is not divisible by a half
            # note, so a naive default leaves the bar two thirds full.
            default_duration = 1.0
            for candidate in (2.0, 1.0, 4.0, 0.5):
                quotient = signature.quarters_per_bar / candidate
                if abs(quotient - round(quotient)) < 1e-9 and quotient >= 1:
                    default_duration = candidate
                    break
            needed = max(1, int(round(signature.quarters_per_bar / default_duration)))
            for _ in range(needed):
                self._add_chord(bar_index, duration=default_duration, refresh=False)
            self._refresh_fill(bar_index)
        self._refresh_preview()

    def _signature_for(self, bar_index: int) -> TimeSignature:
        raw = (self.bar_signatures[bar_index]
               if bar_index < len(self.bar_signatures) else self.base_time_signature)
        beats, _, beat_type = raw.partition("/")
        return TimeSignature(int(beats), int(beat_type or 4))

    def _add_chord(self, bar_index: int, duration: float = 2.0,
                   refresh: bool = True, initial: Optional[dict] = None) -> None:
        row = self.chord_rows[bar_index]
        # La ficha: un renglón hundido con una franja a la izquierda que
        # lleva el color del estado, así se ve de lejos qué casilla tiene un
        # problema sin leer ningún texto. Pelada por lo mismo que la
        # cabecera.
        line = tk.Frame(row["frame"], bg=CHIP, highlightthickness=1,
                        highlightbackground=BORDER_SOFT)
        line.pack(fill="x", pady=(0, 6), before=row["add"])
        stripe = tk.Frame(line, bg=BORDER_SOFT, width=3)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(line, bg=CHIP)
        inner.pack(side="left", fill="x", expand=True, padx=(10, 8),
                   pady=(7, 6))
        top = tk.Frame(inner, bg=CHIP)
        top.pack(fill="x")

        entry = ctk.CTkEntry(top, width=150, height=32,
                             placeholder_text=tr("Cmaj7"),
                             font=scaled(("Segoe UI Semibold", 15)),
                             fg_color=SURFACE, border_color=BORDER_SOFT,
                             border_width=1, corner_radius=7)
        entry.pack(side="left")

        duration_values = ([label for label, _ in DURATION_LABELS]
                           + [REST_PREFIX + label for label, _ in DURATION_LABELS])
        # `DurationPicker` y no `CTkOptionMenu`: hay uno por casilla y cada
        # `CTkOptionMenu` se trae su propio menú desplegable puesto. Ver la
        # clase para el número.
        duration_menu = DurationPicker(
            top, duration_values, width=17, background=SURFACE_RAISED,
            command=lambda _v, b=bar_index: (
                self._refresh_fill(b), self._revalidate_bar(b)),
        )
        default_label = next((l for l, v in DURATION_LABELS if v == duration),
                             DURATION_LABELS[1][0])
        duration_menu.set(default_label)
        duration_menu.pack(side="left", padx=(8, 0), ipady=5)

        # Debajo del cifrado y no al costado: con dos compases por renglón
        # el costado no alcanza, y el aviso largo ("no lo reconozco ---
        # probá el piano") empujaba los botones fuera de la ficha.
        status = FlatLabel(inner, text="", text_color=TEXT_MUTED,
                           background=CHIP)
        status.pack(fill="x", pady=(4, 0))

        record = {
            "entry": entry, "duration": duration_menu, "status": status,
            "line": line, "stripe": stripe, "custom": None, "locked": None,
            "lock_button": None, "piano_button": None,
        }

        # Los tres van con `FlatButton` y no con `CTkButton`: son tres por
        # casilla y las casillas van con los compases, así que son los únicos
        # botones del programa cuya cantidad no la decide el diseño sino el
        # usuario. Ver `FlatButton` para el número.
        lock_button = FlatButton(
            top, "🔓", lambda r=record: self._open_lock(r),
            width=3, font=scaled(("Segoe UI", 13)), border=CHIP,
            hover=SURFACE_RAISED, background=CHIP,
        )
        lock_button.pack(side="right", padx=(4, 0))
        record["lock_button"] = lock_button
        Tooltip(lock_button,
                tr("Fija qué nota canta cada voz en este acorde. El programa "
                   "no lo cambia, pero lo tiene en cuenta para los acordes "
                   "vecinos."))

        piano_button = FlatButton(top, "piano",
                                  lambda r=record: self._open_piano(r),
                                  width=6, border=SURFACE_RAISED,
                                  hover=BORDER_SOFT, background=SURFACE_RAISED)
        piano_button.configure(pady=4)
        piano_button.pack(side="right", padx=(4, 0))
        # Guardado para que la guía de esta pantalla pueda señalarlo: es la
        # salida para los acordes que el cifrado no sabe nombrar, y sin
        # señalarlo el paso resaltaba la casilla entera.
        record["piano_button"] = piano_button
        FlatButton(top, "✕", lambda r=record, b=bar_index:
                   self._remove_chord(b, r),
                   width=3, border=CHIP, hover=ERROR,
                   background=CHIP).pack(side="right")

        if initial:
            if initial.get("symbol"):
                entry.insert(0, initial["symbol"])
            if initial.get("duration"):
                duration_menu.set(initial["duration"])
            record["custom"] = initial.get("custom")
            record["locked"] = initial.get("locked")
            record["imported_voicing"] = initial.get("imported_voicing")
            if record["locked"]:
                lock_button.configure(text="🔒", border_color=CHIP,
                                      text_color=ACCENT)
            self._validate_chord(record)

        entry.bind("<KeyRelease>", lambda _e, r=record: self._validate_chord(r))
        row["entries"].append(record)
        # Durante un tramo del sendero, el cifrado se enciende en dorado en
        # cuanto forma parte de la cadencia que hay que escribir.
        self._story_watch_cadence(record)
        if refresh:
            self._refresh_fill(bar_index)
            # Después del `append`: la validación de arriba la refresca
            # cuando la casilla todavía no está en el compás.
            self._refresh_preview()

    def _remove_chord(self, bar_index: int, record: dict) -> None:
        row = self.chord_rows[bar_index]
        if record in row["entries"]:
            row["entries"].remove(record)
            record["line"].destroy()
            self._refresh_fill(bar_index)
            self._refresh_preview()

    def _validate_chord(self, record: dict) -> None:
        """Revisar una casilla y pintar su estado: el texto, la franja y la
        lectura corrida de arriba."""
        self._judge_chord(record)
        stripe = record.get("stripe")
        if stripe is not None:
            try:
                status = record["status"]
                colour = status.cget("fg") if status.cget("text") else BORDER_SOFT
                if colour == TEXT_MUTED:
                    colour = BORDER_SOFT
                stripe.configure(bg=colour)
            except tk.TclError:
                pass
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """La progresión en un renglón: los compases separados por barras."""
        label = getattr(self, "chord_preview", None)
        if label is None:
            return
        bars = []
        for row in getattr(self, "chord_rows", []):
            names = []
            for record in row["entries"]:
                try:
                    if self._is_rest(record):
                        names.append("—")
                        continue
                    names.append(record["entry"].get().strip() or "·")
                except tk.TclError:
                    return
            bars.append("  ".join(names))
        text = "│  " + "  │  ".join(bars) + "  │" if bars else ""
        try:
            label.configure(text=text)
        except tk.TclError:
            pass

    def _judge_chord(self, record: dict) -> None:
        if self._is_rest(record):
            record["status"].configure(text=tr("silencio, no suena nada"),
                                       text_color=TEXT_MUTED)
            record["entry"].configure(state="disabled")
            record["lock_button"].configure(state="disabled")
            return
        record["entry"].configure(state="normal")
        record["lock_button"].configure(state="normal")
        text = record["entry"].get().strip()
        if record.get("locked"):
            record["status"].configure(
                text=trf("bloqueado: {notes}",
                         notes=" ".join(note_name(p) for p in record["locked"])),
                text_color=ACCENT,
            )
            return
        if record["custom"]:
            # Por el mismo aro que un acorde escrito. Las notas del piano
            # salían siempre en verde con su cuenta al lado, aunque fueran
            # más que las voces: el aviso de que iban a faltar notas ---el
            # único que dice que lo que se va a escuchar no es lo que se
            # tocó--- lo daba el cifrado y no el piano, que es justamente el
            # camino por el que se llega a un acorde de seis notas.
            extra = len(record["custom"]) - len(self.voice_keys)
            if extra <= 0:
                record["status"].configure(
                    text=trf("notas propias: {record}",
                             record=len(record['custom'])),
                    text_color=OK_GREEN)
            else:
                # Por la cuenta y no por grados: en un acorde armado a mano
                # los grados los infiere el programa a partir de los
                # intervalos, y «omitiendo 5, 1» sobre seis teclas elegidas
                # a dedo no le dice nada a nadie. Lo que hay que saber es
                # cuántas de las que se tocaron no van a sonar.
                # Las dos formas van escritas enteras y no pegando la
                # terminación del verbo: «va»/«van» es una concordancia del
                # castellano y no existe como pedazo en ningún otro idioma.
                record["status"].configure(
                    text=trf("{record} notas para {voice_keys} voces · "
                             "{extra} no se va a escribir",
                             record=len(record['custom']),
                             voice_keys=len(self.voice_keys), extra=extra)
                    if extra == 1 else
                    trf("{record} notas para {voice_keys} voces · {extra} no "
                        "se van a escribir",
                        record=len(record['custom']),
                        voice_keys=len(self.voice_keys), extra=extra),
                    text_color=WARN)
            return
        if not text:
            record["status"].configure(text="", text_color=TEXT_MUTED)
            return
        try:
            chord = parse_chord(text)
        except ChordParseError:
            record["status"].configure(text=tr("no lo reconozco, probá con el "
                                               "piano"),
                                       text_color=ERROR)
            return
        advice = check_chord_fits(chord, len(self.voice_keys))
        if advice.fits:
            record["status"].configure(
                text=trf("{tones} notas · entra", tones=len(chord.tones)), text_color=OK_GREEN
            )
        elif advice.suggested_omissions:
            record["status"].configure(
                text=trf("omitiendo {value}",
                         value=', '.join(advice.suggested_omissions)),
                text_color=WARN,
            )
        else:
            record["status"].configure(text=tr(advice.message)[:60],
                                       text_color=ERROR)

    def _revalidate_bar(self, bar_index: int) -> None:
        """Re-check every row of a bar, e.g. after a duration became a rest."""
        for record in self.chord_rows[bar_index]["entries"]:
            self._validate_chord(record)

    def _refresh_fill(self, bar_index: int) -> None:
        row = self.chord_rows[bar_index]
        signature = self._signature_for(bar_index)
        total = sum(self._duration_of(r) for r in row["entries"])
        target = signature.quarters_per_bar
        self._draw_meter(row.get("meter"), total, target, signature.beats)
        if abs(total - target) < 1e-6:
            row["fill_label"].configure(text=trf("{total:g}/{target:g} "
                                                 "tiempos",
                                                 total=total, target=target),
                                        text_color=OK_GREEN)
        else:
            row["fill_label"].configure(text=trf("{total:g}/{target:g} "
                                                 "tiempos",
                                                 total=total, target=target),
                                        text_color=WARN)

    @staticmethod
    def _draw_meter(canvas, total: float, target: float, beats: int) -> None:
        """
        Cuánto del compás está lleno, en segmentos de a un tiempo.

        Verde exacto, ámbar si falta y rojo si sobra --- los mismos colores
        que el texto de al lado, que dice el número.
        """
        if canvas is None:
            return
        try:
            canvas.delete("all")
            width = METER_WIDTH
            beats = max(1, beats)
            gap = 3
            share = (width - gap * (beats - 1)) / beats
            if abs(total - target) < 1e-6:
                colour = OK_GREEN
            elif total > target:
                colour = ERROR
            else:
                colour = WARN
            filled = 0.0 if target <= 0 else min(1.0, total / target) * beats
            for index in range(beats):
                left = index * (share + gap)
                canvas.create_rectangle(left, 0, left + share, 8,
                                        fill=SURFACE_RAISED, width=0)
                portion = max(0.0, min(1.0, filled - index))
                if portion > 0:
                    canvas.create_rectangle(left, 0, left + share * portion, 8,
                                            fill=colour, width=0)
        except tk.TclError:
            pass

    @staticmethod
    def _duration_of(record: dict) -> float:
        label = record["duration"].get()
        if label.startswith(REST_PREFIX):
            label = label[len(REST_PREFIX):]
        return dict(DURATION_LABELS).get(label, 2.0)

    @staticmethod
    def _is_rest(record: dict) -> bool:
        return record["duration"].get().startswith(REST_PREFIX)

    def _open_piano(self, record: dict) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Elegir notas a mano")
        window.geometry("640x300")
        window.configure(fg_color=SURFACE)
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(window, text=tr("Tocá las teclas que forman el acorde"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(pady=(16, 4))
        ctk.CTkLabel(window,
                     text=tr("La nota más grave se toma como fundamental."),
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack()

        # Cuántas voces hay, dicho antes de tocar nada. El aviso de la fila
        # llega recién al cerrar la ventana, y para entonces ya se eligieron
        # seis notas sin que nada dijera que sobraban dos.
        limit = ctk.CTkLabel(
            window,
            text=trf("Hay {voice_keys} voces. Si marcás más notas, algunas se "
                     "omiten al escribir.",
                     voice_keys=len(self.voice_keys)),
            font=FONT_SMALL, text_color=TEXT_MUTED)
        limit.pack()

        piano = PianoSelector(window)
        piano.pack(pady=12)
        if record["custom"]:
            piano.selected = [60 + pc for pc in record["custom"]]
            piano._refresh_colours()

        def refresh_limit() -> None:
            """Repintar el aviso con cada tecla."""
            extra = len(piano.get_pitch_classes()) - len(self.voice_keys)
            try:
                if extra > 0:
                    limit.configure(
                        text=trf("Sobran {extra}. Hay {voice_keys} voces, así "
                                 "que {extra2} de estas notas no se van a "
                                 "escribir.",
                                 extra=extra,
                                 voice_keys=len(self.voice_keys),
                                 extra2=extra),
                        text_color=WARN)
                else:
                    limit.configure(
                        text=trf("Hay {voice_keys} voces. Si marcás más "
                                 "notas, algunas se omiten al escribir.",
                                 voice_keys=len(self.voice_keys)),
                        text_color=TEXT_MUTED)
            except tk.TclError:
                pass

        # Encima del click del piano y no en un temporizador: el aviso tiene
        # que contestar a la tecla, no cada tantos milisegundos.
        def on_key(event, _pick=piano._on_click) -> None:
            _pick(event)
            refresh_limit()

        piano.canvas.bind("<Button-1>", on_key)
        refresh_limit()

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(pady=6)

        def accept() -> None:
            pcs = piano.get_pitch_classes()
            if not pcs:
                record["custom"] = None
            else:
                record["custom"] = pcs
                names = "-".join(SHARP_NAMES[pc] for pc in pcs)
                record["entry"].delete(0, "end")
                record["entry"].insert(0, names)
            self._validate_chord(record)
            window.destroy()

        def cancel() -> None:
            window.destroy()

        ctk.CTkButton(buttons, text=tr("Usar estas notas"), fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=accept).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text=tr("Cancelar"), fg_color="transparent",
                      border_width=1, border_color=TEXT_MUTED,
                      hover_color=SURFACE_LIGHT, command=cancel).pack(side="left", padx=6)

    def _open_lock(self, record: dict) -> None:
        """Pin the exact voicing of one chord so the search cannot alter it."""
        symbol = record["entry"].get().strip()
        if not symbol and not record["custom"]:
            messagebox.showinfo(tr("Falta el acorde"),
                                tr("Escribí el acorde antes de bloquearlo."))
            return

        try:
            suggested = session.default_locked_voicing(
                symbol, self.voice_keys, record["custom"]
            )
        except Exception as exc:            # noqa: BLE001
            messagebox.showerror(tr("No se pudo"), trf("No entiendo ese acorde: "
                                                       "{exc}",
                                                       exc=exc))
            return

        current = record["locked"] or record.get("imported_voicing") or suggested

        window = ctk.CTkToplevel(self)
        window.title(trf("Bloquear {symbol}", symbol=symbol))
        window.geometry("560x500")
        window.configure(fg_color=SURFACE)
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(window, text=trf("Voicing fijo para {symbol}",
                                      symbol=symbol),
                     font=scaled(("Segoe UI Semibold", 15))).pack(anchor="w", padx=22,
                                                          pady=(20, 2))
        ctk.CTkLabel(window,
                     text=tr("Escribí qué nota canta cada voz. El programa no "
                             "va a cambiar este acorde, pero lo usa para "
                             "mover los acordes vecinos."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=22, pady=(0, 12))

        from engine.theory import build_voice_parts
        voices = build_voice_parts(self.voice_keys)
        entries: List[ctk.CTkEntry] = []
        # Tracked through StringVars rather than a <KeyRelease> binding:
        # binding the composite CTkEntry did not deliver key events reliably,
        # and a variable trace also fires when the value is set in code.
        field_vars: List[tk.StringVar] = []
        for index, voice in enumerate(voices):
            line = ctk.CTkFrame(window, fg_color="transparent")
            line.pack(fill="x", padx=22, pady=4)
            ctk.CTkLabel(line, text=i18n.tr_name(voice.name), font=FONT_SMALL, width=140,
                         anchor="w").pack(side="left")
            variable = tk.StringVar(
                value=note_name(current[index]) if index < len(current) else ""
            )
            field = ctk.CTkEntry(line, width=90, textvariable=variable)
            field.pack(side="left")
            field_vars.append(variable)
            ctk.CTkLabel(line,
                         text=trf("rango {note_name}–{note_name2}",
                                  note_name=note_name(voice.low),
                                  note_name2=note_name(voice.high)),
                         font=FONT_SMALL, text_color=TEXT_MUTED
                         ).pack(side="left", padx=10)
            entries.append(field)

        # Horizontal read-out: the voicing bottom to top plus the figure it
        # would carry in thoroughbass. Reading four stacked entry boxes and
        # working out the inversion in your head is the hard way to check a
        # voicing; this says it in one line and updates as you type.
        summary = ctk.CTkFrame(window, fg_color=SURFACE, corner_radius=11)
        summary.pack(fill="x", padx=22, pady=(14, 0))
        summary_notes = ctk.CTkLabel(summary, text="", font=scaled(("Segoe UI", 13)),
                                     anchor="w")
        summary_notes.pack(side="left", padx=14, pady=10)
        summary_figure = ctk.CTkLabel(summary, text="", font=scaled(("Segoe UI Semibold", 15)),
                                      text_color=ACCENT)
        summary_figure.pack(side="right", padx=14)
        Tooltip(summary_figure,
                tr("Cifrado barroco: los intervalos se cuentan desde el bajo. "
                   "Un 6/5 es una séptima en primera inversión, o sea con la "
                   "tercera abajo."))

        def refresh_summary(*_args) -> None:
            pitches = []
            for variable in field_vars:
                try:
                    pitches.append(parse_note_name(variable.get()))
                except ValueError:
                    summary_notes.configure(text="—", text_color=TEXT_MUTED)
                    summary_figure.configure(text="")
                    return
            try:
                chord = (make_custom_chord(record["custom"], symbol)
                         if record["custom"] else parse_chord(symbol))
            except Exception:                     # noqa: BLE001
                return
            names = "   ".join(note_name(p) for p in pitches)
            sizes = intervals_above_bass(pitches)
            summary_notes.configure(
                text=trf("bajo → soprano:   {names}      ({value} sobre el "
                         "bajo)",
                         names=names, value='-'.join(['1'] + sizes)),
                text_color=TEXT_NORMAL,
            )
            summary_figure.configure(text=figured_bass(chord, pitches))

        for variable in field_vars:
            variable.trace_add("write", refresh_summary)
        refresh_summary()

        message = ctk.CTkLabel(window, text="", font=FONT_SMALL, text_color=WARN,
                               wraplength=460, justify="left")
        message.pack(anchor="w", padx=22, pady=(8, 0))

        def apply_lock() -> None:
            pitches: List[int] = []
            for index, field in enumerate(entries):
                try:
                    pitch = parse_note_name(field.get())
                except ValueError:
                    message.configure(
                        text=trf("«{value}» no es una nota válida. Usá C4, "
                                 "Bb3, F#5.",
                                 value=field.get())
                    )
                    return
                if not voices[index].contains(pitch):
                    message.configure(
                        text=trf("{name} no llega a {note_name}.",
                                 name=voices[index].name,
                                 note_name=note_name(pitch))
                    )
                    return
                pitches.append(pitch)
            if any(pitches[i] > pitches[i + 1] for i in range(len(pitches) - 1)):
                message.configure(
                    text=tr("Las voces quedan cruzadas. Cada una tiene que "
                            "estar por encima de la anterior.")
                )
                return
            record["locked"] = pitches
            record["lock_button"].configure(text="🔒", border_color=CHIP,
                                            text_color=ACCENT)
            self._validate_chord(record)
            window.destroy()

        def clear_lock() -> None:
            record["locked"] = None
            record["lock_button"].configure(text="🔓", border_color=CHIP,
                                            text_color=TEXT_NORMAL)
            self._validate_chord(record)
            window.destroy()

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(pady=16)
        ctk.CTkButton(buttons, text=tr("Bloquear"), fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=apply_lock
                      ).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text=tr("Quitar candado"), fg_color="transparent",
                      border_width=1, border_color=TEXT_MUTED,
                      hover_color=SURFACE_LIGHT, command=clear_lock
                      ).pack(side="left", padx=6)

    def _commit_chords(self) -> bool:
        entries: List[session.ChordEntry] = []
        problems: List[str] = []

        for bar_index, row in enumerate(self.chord_rows):
            signature = self._signature_for(bar_index)
            total = sum(self._duration_of(r) for r in row["entries"])
            if abs(total - signature.quarters_per_bar) > 1e-6:
                # Una casilla en blanco sigue ocupando su duración, así que el
                # compás puede pasarse de tiempos sin que se vea un solo
                # acorde de más. El mensaje señalaba la duración, que es
                # justamente lo que no está mal, y no la casilla vacía que
                # sobra: había que adivinar que se saca con la ✕.
                empty = sum(1 for r in row["entries"]
                            if not self._is_rest(r)
                            and not r["entry"].get().strip()
                            and not r["custom"])
                extra = ""
                if empty and total > signature.quarters_per_bar:
                    extra = (trf(" Hay {empty} casilla vacía que igual ocupa "
                                 "su duración. Escribí un acorde o borrala "
                                 "con la ✕.",
                                 empty=empty)
                             if empty == 1 else
                             trf(" Hay {empty} casillas vacías que igual "
                                 "ocupan su duración. Escribí acordes o "
                                 "borralas con la ✕.",
                                 empty=empty))
                problems.append(
                    trf("El compás {bar_index} suma {total:g} tiempos y "
                        "necesita {quarters_per_bar:g}.{extra}",
                        bar_index=bar_index + 1, total=total,
                        quarters_per_bar=signature.quarters_per_bar,
                        extra=extra)
                )
                continue
            for record in row["entries"]:
                if self._is_rest(record):
                    entries.append(session.ChordEntry(
                        symbol="",
                        duration_quarters=self._duration_of(record),
                        bar_index=bar_index,
                        is_rest=True,
                    ))
                    continue
                text = record["entry"].get().strip()
                if not text and not record["custom"]:
                    problems.append(trf("Falta un acorde en el compás "
                                        "{bar_index}.",
                                        bar_index=bar_index + 1))
                    continue
                entries.append(session.ChordEntry(
                    symbol=text or "custom",
                    duration_quarters=self._duration_of(record),
                    bar_index=bar_index,
                    custom_pitch_classes=record["custom"],
                    locked_pitches=record["locked"],
                ))

        if problems:
            self.chord_hint.configure(text="  ".join(trs(problems[:3])))
            return False
        if not entries:
            self.chord_hint.configure(text=tr("Todavía no cargaste ningún acorde."))
            return False

        self.chord_entries = entries
        self.chord_hint.configure(text="")

        found = set()
        if any(entry.is_rest for entry in entries):
            found.add("first_rest")
        if sum(1 for entry in entries if entry.locked_pitches) >= 2:
            found.add("two_locks")
        self._award(found)
        self._check_written_chords(entries)
        self._story_note_progress(entries)
        # Con todos los acordes fijados no queda nada que buscar: el
        # algoritmo genético se queda sin decisiones que tomar, y el programa
        # lo dice.
        if eggs.all_locked(entries):
            self._egg("locksmith")
            self._egg_legend("¿Para qué diantres me necesitás entonces?")
        return True

    # -- screen: melody (harmonise mode) ------------------------------------

    KEY_SIGNATURES = [
        (N("Do mayor / La menor"), 0), (N("Sol mayor / Mi menor"), 1),
        (N("Re mayor / Si menor"), 2), (N("La mayor / Fa# menor"), 3),
        (N("Mi mayor / Do# menor"), 4), (N("Fa mayor / Re menor"), -1),
        (N("Sib mayor / Sol menor"), -2), (N("Mib mayor / Do menor"), -3),
        (N("Lab mayor / Fa menor"), -4),
    ]

    #: The texture each style harmonises in. Bass, tenor and soprano for
    #: three parts; alto joins for four.
    HARMONISE_VOICES = {
        "classical": ["B", "T", "S"],
        "chorale": ["B", "T", "S"],
        "gregorian": ["B", "T", "S"],
        "jazz": ["B", "T", "A", "S"],
    }

    def _screen_melody(self) -> None:
        self._forget_genre_settings()
        self.voice_keys = list(self.HARMONISE_VOICES.get(
            self.genre_key, ["B", "T", "S"]))
        self.range_overrides = {}
        self._heading(
            tr("Dibujá la melodía"),
            tr("Hacé click en el pentagrama para poner cada nota, o usá el "
               "piano de abajo. El programa no cambia ninguna nota de tu "
               "melodía."))

        toolbar = ctk.CTkFrame(self.body, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(toolbar, text=tr("Armadura"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.key_menu = ctk.CTkOptionMenu(
            toolbar, values=trs(label for label, _f in self.KEY_SIGNATURES),
            width=180, fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT_HOVER, command=lambda _v: self._sync_staff())
        self.key_menu.set(tr(getattr(self, "_key_label",
                                     self.KEY_SIGNATURES[0][0])))
        self.key_menu.pack(side="left")

        ctk.CTkLabel(toolbar, text=tr("Compás"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(14, 6))
        self.melody_metre = ctk.CTkOptionMenu(
            toolbar, values=["4/4", "3/4", "2/4", "6/8"], width=80,
            fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT_HOVER, command=lambda _v: self._sync_staff())
        self.melody_metre.set(getattr(self, "_melody_metre", "4/4"))
        self.melody_metre.pack(side="left")

        ctk.CTkLabel(toolbar, text=tr("Mi voz es"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(14, 6))
        self.melody_voice_menu = ctk.CTkOptionMenu(
            toolbar, values=trs(VOICE_CATALOG[k].label
                                for k in self.voice_keys),
            width=140, fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT_HOVER, command=lambda _v: self._sync_staff())
        # Por defecto, la voz más aguda: el pentagrama está en clave de sol y
        # lo que uno dibuja ahí cae casi siempre en el registro de la
        # soprano. Cualquier otra voz por defecto rebota contra su registro
        # apenas se escribe un poco arriba.
        saved = getattr(self, "_melody_voice", len(self.voice_keys) - 1)
        saved = min(saved, len(self.voice_keys) - 1)
        self.melody_voice_menu.set(tr(VOICE_CATALOG[self.voice_keys[saved]].label))
        self.melody_voice_menu.pack(side="left")

        # Los accidentes, para escribir notas fuera de la armadura con el
        # mouse. Se eligen antes del click y valen para esa nota sola, como
        # en el analizador; el piano de abajo ya escribe las teclas negras
        # con su accidente. Sin esto el pentagrama tenía siete notas por
        # octava y el armonizador no podía recibir un sol sostenido.
        ctk.CTkLabel(toolbar, text=tr("Accidente"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=(14, 6))
        self.melody_accidentals = {}
        for value, glyph in ((1, "♯"), (-1, "♭"), (0, "♮")):
            button = ctk.CTkButton(
                toolbar, text=glyph, width=34, height=28,
                font=("Segoe UI Symbol", 15), fg_color="transparent",
                border_width=1, border_color=TEXT_MUTED,
                hover_color=SURFACE_LIGHT,
                command=lambda v=value: self._set_melody_accidental(v))
            button.pack(side="left", padx=2)
            self.melody_accidentals[value] = button
        Tooltip(self.melody_accidentals[1],
                tr("La próxima nota que escribas con el mouse lleva este "
                   "accidente. Vale para una sola nota. Tocalo otra vez para "
                   "quitarlo."))

        import_button = ctk.CTkButton(
            toolbar, text=tr("Importar…"), width=110, height=30, font=FONT_SMALL,
            fg_color="transparent", border_width=1, border_color=TEXT_MUTED,
            hover_color=SURFACE_LIGHT, command=self._import_melody)
        import_button.pack(side="right")
        Tooltip(import_button,
                tr("Carga una melodía de un MusicXML. Toma la nota más aguda "
                   "de cada momento, así que sirve aunque la partitura tenga "
                   "varias voces."))

        self.staff = StaffEditor(
            self.body,
            colours={"surface": SURFACE_LIGHT, "text": TEXT_NORMAL,
                     "muted": TEXT_MUTED, "accent": ACCENT, "gold": GOLD,
                     "chromatic": CHROMATIC_COLOUR},
            on_change=self._on_melody_changed)
        self.staff.pack(fill="both", expand=True, pady=(0, 8))
        for index, duration in getattr(self, "_melody_notes", []):
            self.staff.notes.append((index, duration))
        self.staff.marked = set(getattr(self, "_melody_marks", set()))
        self.staff.blocked = set(getattr(self, "_melody_skips", set()))
        # Los accidentes van aparte de las notas (ver `StaffEditor`), así que
        # se guardan y se devuelven aparte: sin esto, volver a esta pantalla
        # convertía cada sol sostenido en un sol.
        self.staff.accidentals = dict(getattr(self, "_melody_accidentals", {}))

        #: La fila de figuras y botones del pentagrama. Con nombre para que
        #: la guía de esta pantalla pueda señalarla entera.
        self.melody_controls = controls = ctk.CTkFrame(
            self.body, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 6))
        self.duration_var = tk.StringVar(
            value=getattr(self, "_duration_label", "Negra"))
        for label, value in DURATIONS:
            ctk.CTkRadioButton(
                controls, text=tr(label), variable=self.duration_var, value=label,
                font=FONT_SMALL, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda v=value: setattr(self.staff, "duration", v)
            # Apretadas: la fila lleva además los cuatro botones del
            # pentagrama y con doce píxeles entre figura y figura el último
            # ---«Borrar todo»--- se quedaba sin la mitad de su ancho.
            ).pack(side="left", padx=(0, 4))
        listen = ctk.CTkButton(controls, text=tr("▶  Escuchar"), width=130,
                               height=30, font=FONT_SMALL, fg_color=ACCENT,
                               hover_color=ACCENT_HOVER)
        listen.configure(command=lambda b=listen: self._play_melody(b))
        listen.pack(side="right", padx=(12, 0))
        Tooltip(listen, tr("Toca la melodía sola, antes de armonizarla."))
        # Entre «Escuchar» y «Deshacer»: es un botón del pentagrama como
        # los otros dos, y con la fila de figuras a la izquierda queda a
        # mano. Lo que significa el dorado sigue explicado abajo.
        self.mark_button = ctk.CTkButton(
            controls, text=tr("Marcar notas"), width=118, height=30,
            font=FONT_SMALL, fg_color="transparent", border_width=1,
            border_color=GOLD_DIM, text_color=GOLD, hover_color=SURFACE_LIGHT,
            command=self._toggle_marking)
        self.mark_button.pack(side="right", padx=(6, 0))
        Tooltip(self.mark_button,
                tr("Encendido, cada click en el pentagrama pone o saca el "
                   "acorde de una nota en vez de escribirla. También sirve "
                   "para las que doró el programa."))
        self.undo_button = ctk.CTkButton(
            controls, text=tr("Deshacer"), width=100, height=30,
            font=FONT_SMALL, fg_color="transparent", border_width=1,
            border_color=TEXT_MUTED, hover_color=SURFACE_LIGHT,
            command=self.staff.undo)
        self.undo_button.pack(side="right", padx=(6, 0))
        Tooltip(self.undo_button, tr("Borra la última nota escrita.  (Ctrl+Z)"))
        ctk.CTkButton(controls, text=tr("Borrar todo"), width=110, height=30,
                      font=FONT_SMALL, fg_color="transparent", border_width=1,
                      border_color=TEXT_MUTED, hover_color=SURFACE_LIGHT,
                      command=self.staff.clear).pack(side="right")

        # Qué significa el dorado. Va acá, pegado al pentagrama y no en un
        # tooltip ni en el texto de arriba: es la única explicación de por
        # qué algunas notas están de otro color, y una explicación que hay
        # que ir a buscar no explica nada.
        #
        # Las muestras las dibuja el mismo `note_look` que pinta el
        # pentagrama: escritas a mano con un «●» de color, la explicación
        # podía decir una cosa y la nota mostrar otra. Son dos preguntas y
        # cada una tiene su canal ---el color dice si la nota está en la
        # escala, el halo si lleva acorde--- así que las tres que importan
        # se distinguen aunque no se distinga el naranja del dorado.
        legend = ctk.CTkFrame(self.body, fg_color="transparent")
        legend.pack(fill="x", pady=(0, 4))
        swatches = ctk.CTkFrame(legend, fg_color="transparent")
        swatches.pack(fill="x")
        palette = {"surface": SURFACE_LIGHT, "text": TEXT_NORMAL,
                   "gold": GOLD, "chromatic": CHROMATIC_COLOUR}
        for chromatic, harmonised, label in (
                (False, True, tr("lleva acorde")),
                (True, False, tr("fuera de la escala")),
                (True, True, tr("fuera de la escala, con acorde"))):
            legend_swatch(swatches, palette, chromatic, harmonised,
                          background=SURFACE).pack(side="left")
            ctk.CTkLabel(swatches, text=label, font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(side="left",
                                                     padx=(2, 14))
        # Un renglón y no dos: lo que antes explicaba el dorado ya lo dicen
        # las muestras, y cada renglón de más empujaba fuera de la ventana
        # el aviso de abajo ---el que dice que la melodía no entra en la
        # voz---. El jazz lleva su propia frase porque es el único estilo
        # donde la nota que baja también se marca sola.
        ctk.CTkLabel(
            legend,
            text=(tr("Con click derecho, o con «Marcar notas» prendido, ponés "
                     "o sacás el acorde de una nota. Una nota naranja que "
                     "sube un semitono lleva sola el dominante de la "
                     "siguiente, y una que baja, el sustituto tritonal.")
                  if self.genre_key == "jazz"
                  else tr("Con click derecho, o con «Marcar notas» prendido, "
                          "ponés o sacás el acorde de una nota. Una nota "
                          "naranja que sube un semitono lleva sola el "
                          "dominante de la siguiente.")),
            font=FONT_SMALL, text_color=TEXT_MUTED, justify="left",
            wraplength=1080).pack(anchor="w")

        # El tramo del sendero que se juega acá no se toca con un botón sino
        # con una tecla: el piano se enciende en dorado y lo único que hay
        # que hacer es tocarla. Mientras esté encendido, el pentagrama no se
        # edita --- lo que va a escribirse ya está decidido.
        story_step = self._story_awaiting("harmonise")
        highlight = None
        if story_step is not None and self.story.gate_open(story_step.gate):
            highlight = self._story_piano_highlight(story_step)
        #: Si el piano del sendero está encendido en esta pantalla. Lo miran
        #: el renglón de abajo y el botón de «Siguiente», que mientras dure
        #: eso dicen otra cosa de la que dirían normalmente.
        self._story_piano_on = bool(highlight)
        self.melody_piano = MelodyPiano(
            self.body,
            colours={"surface": SURFACE_LIGHT, "text": TEXT_NORMAL,
                     "muted": TEXT_MUTED, "accent": ACCENT},
            on_pick=(self._story_piano_pick if highlight
                     else self.staff.add_pitch),
            highlight=highlight)
        self.melody_piano.pack(fill="x", pady=(2, 6))
        if story_step is not None:
            self._story_harmonise_notice(story_step, bool(highlight))
        if highlight:
            # Con el piano encendido, la melodía ya está decidida: dejar
            # escribir encima sólo permitiría llegar a la tecla dorada con
            # una línea a medio hacer que después se pisa sola.
            try:
                self.staff.canvas.unbind("<Button-1>")
                # Y tampoco se marca: la pieza del tramo ya trae sus acordes
                # escritos, así que un pedido sobre una nota no iría a
                # ninguna parte.
                self.staff.canvas.unbind("<Button-3>")
            except tk.TclError:
                pass

        self.melody_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                        text_color=TEXT_MUTED)
        self.melody_hint.pack(anchor="w")
        if highlight:
            # Y «Siguiente» se apaga. Con el piano encendido no hay nada que
            # llevar a la pantalla siguiente ---el pentagrama está vacío y no
            # se puede escribir en él--- así que tocarlo sólo conseguía el
            # aviso de «escribí al menos una nota», que acá miente: no hay
            # que escribir nada, hay que tocar la tecla. Apagado, lo único
            # que se puede hacer en la pantalla es lo que el tramo pide.
            #
            # Se apaga después de `_render_screen`, que lo deja en `normal`
            # antes de armar la pantalla, y vuelve solo en el próximo render
            # por lo mismo.
            try:
                self.next_button.configure(state="disabled")
            except tk.TclError:
                pass
        self.staff.duration = next(
            (v for label, v in DURATIONS if label == self.duration_var.get()), 1.0)
        # Ctrl+Z aprieta el botón de deshacer, y lo aprieta de verdad
        # ---`invoke`, no `staff.undo`--- así que el atajo y el botón no
        # pueden separarse nunca. El atajo va en la ventana y no en el
        # pentagrama: la tecla llega a donde esté el foco, que después de
        # tocar el piano o un radio de figura no es el lienzo.
        self.bind("<Control-z>", self._undo_shortcut)
        self.bind("<Control-Z>", self._undo_shortcut)
        self._sync_staff()
        # No mientras el sendero tenga el piano encendido: ahí la pantalla no
        # se usa como se usa normalmente --- el pentagrama no se edita y lo
        # único que se puede hacer es tocar la tecla dorada ---, así que una
        # guía explicando cómo escribir una melodía estaría explicando algo
        # que en ese momento no se puede hacer.
        if not highlight:
            self._maybe_guide("melody")

    def _undo_shortcut(self, _event=None) -> None:
        """Ctrl+Z, mientras la pantalla de la melodía siga en pie.

        El atajo queda atado a la ventana, así que sigue vivo después de
        cambiar de pantalla; lo que decide si hace algo es que el botón
        exista todavía.
        """
        button = getattr(self, "undo_button", None)
        try:
            if button is not None and button.winfo_exists():
                button.invoke()
        except tk.TclError:
            pass

    def _toggle_marking(self) -> None:
        """Prender o apagar el modo de marcar notas.

        Encendido se ve: un botón que cambia lo que hace el click tiene que
        decir en qué estado está, o el próximo click sorprende.
        """
        if not hasattr(self, "staff"):
            return
        self.staff.marking = not self.staff.marking
        on = self.staff.marking
        try:
            self.mark_button.configure(
                text=tr("Marcando…" if on else "Marcar notas"),
                fg_color=GOLD_DIM if on else "transparent",
                text_color=TEXT_NORMAL if on else GOLD,
                border_color=GOLD if on else GOLD_DIM)
        except tk.TclError:
            pass

    def _set_melody_accidental(self, value: int) -> None:
        """Elegir el accidente de la próxima nota, o soltarlo si ya estaba."""
        if not hasattr(self, "staff"):
            return
        self.staff.pending = None if self.staff.pending == value else value
        self._sync_melody_accidentals()

    def _sync_melody_accidentals(self) -> None:
        """Encender el botón del accidente pendiente, y sólo ése.

        El pentagrama suelta el accidente en cuanto escribe la nota, así que
        el botón se apaga solo al escribir: un botón que siguiera encendido
        prometería un sostenido que la nota siguiente ya no va a llevar.
        """
        pending = getattr(getattr(self, "staff", None), "pending", None)
        for value, button in getattr(self, "melody_accidentals", {}).items():
            chosen = value == pending
            try:
                button.configure(
                    fg_color=CHROMATIC_COLOUR if chosen else "transparent",
                    text_color=SURFACE if chosen else TEXT_NORMAL,
                    border_color=CHROMATIC_COLOUR if chosen else TEXT_MUTED)
            except tk.TclError:
                pass

    def _play_melody(self, button) -> None:
        """Play just the line, so the user can hear what they are writing."""
        if getattr(self, "_playing", None) is not None and self._playing.is_alive():
            return
        written = self.staff.pitches()
        if not written:
            return
        # Tónica, tónica y quinta, las tres redondas, y nada más: el
        # armonizador contesta con otra cosa.
        fifths = next((f for name, f in self.KEY_SIGNATURES
                       if name == i18n.untr(self.key_menu.get())), 0)
        tonic, _mode_key = importer.key_from_fifths(fifths)
        if eggs.zombie_call(written, tonic):
            self._egg_zombie(button)
            return
        line, position = [], 0.0
        for pitch, duration in written:
            line.append((pitch, position, duration))
            position += duration
        button.configure(text=tr("♪  Sonando…"), state="disabled")

        def restore() -> None:
            try:
                button.configure(text=tr("▶  Escuchar"), state="normal")
            except tk.TclError:
                pass

        self._playing = audio.play_chords([], [], melody=line)
        self._when_done(self._playing, restore)

    def _sync_staff(self) -> None:
        """Push the chosen key and metre into the staff."""
        if not hasattr(self, "staff"):
            return
        label = i18n.untr(self.key_menu.get())
        fifths = next((f for name, f in self.KEY_SIGNATURES if name == label), 0)
        beats, beat_type = (int(x) for x in self.melody_metre.get().split("/"))
        voice_label = i18n.untr(self.melody_voice_menu.get())
        index = next((i for i, k in enumerate(self.voice_keys)
                      if VOICE_CATALOG[k].label == voice_label), 0)
        # A low part reads on the bass staff; anything else on the treble.
        self.staff.treble = index >= max(1, len(self.voice_keys) // 2)
        self.staff.set_key(fifths, beats, beat_type)
        self._on_melody_changed()

    def _on_melody_changed(self) -> None:
        if not hasattr(self, "staff"):
            return
        self._sync_melody_accidentals()
        # Con el piano del sendero encendido el renglón dice qué hacer y no
        # cuánto se lleva escrito: el pentagrama está vacío y no se puede
        # escribir en él, así que «0 nota(s) · 0 compás(es)» es un contador
        # de algo que no va a moverse --- y es lo único que hay debajo del
        # botón apagado para explicar por qué está apagado.
        if getattr(self, "_story_piano_on", False):
            try:
                self.melody_hint.configure(
                    text=tr("Tocá la tecla dorada del piano para seguir."),
                    text_color=GOLD)
            except tk.TclError:
                pass
            return
        count = len(self.staff.notes)
        quarters = self.staff.total_quarters()
        per_bar = self.staff.beats * 4.0 / self.staff.beat_type
        bars = quarters / per_bar if per_bar else 0
        self.melody_hint.configure(
            text=trf("{count} nota(s) · {bars:.2g} compás(es)",
                     count=count, bars=bars)
            + ("" if abs(bars - round(bars)) < 1e-6
               else "  ·  el último compás quedó incompleto")
        )
        self._refresh_harmony_preview()
        # «La melodía suprema» se comprueba acá y no al pasar de pantalla:
        # se consigue en el momento en que la melodía la cumple. Nada le
        # dice al usuario cuánto le falta -- eso lo descubre solo -- pero
        # tampoco tiene que adivinar cuándo se guardó lo que escribió.
        if not self.achievements.has("supreme_melody") and self.staff.notes:
            if achievements.supreme_melody(
                    self.staff.notes,
                    [value for _label, value in DURATIONS]):
                self._award({"supreme_melody"})

    def _import_melody(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("Elegí una partitura"),
            filetypes=[(tr("Partituras"), "*.musicxml *.xml *.mxl"),
                       (tr("Todos los archivos"), "*.*")])
        if not path:
            return
        try:
            melody = importer.read_melody(path)
        except importer.ImportError_ as exc:
            messagebox.showerror(tr("No se pudo importar"), str(exc))
            return
        self.staff.clear()
        for note in melody.notes:
            self.staff.add_pitch(note.pitch)
        if melody.bars:
            self.melody_metre.set(f"{melody.bars[0].beats}/{melody.bars[0].beat_type}")
        self._sync_staff()
        self._award({"import_score"})
        messagebox.showinfo(tr("Melodía importada"),
                            trf("Se cargaron {notes} notas.",
                                notes=len(melody.notes)))

    def _commit_melody(self) -> bool:
        if not hasattr(self, "staff"):
            return True
        if not self.staff.notes:
            self.melody_hint.configure(
                text=tr("Escribí al menos una nota antes de seguir."),
                text_color=WARN)
            return False
        self._melody_notes = list(self.staff.notes)
        self._melody_marks = set(self.staff.marked)
        self._melody_skips = set(self.staff.blocked)
        self._melody_accidentals = dict(self.staff.accidentals)
        self._key_label = i18n.untr(self.key_menu.get())
        self._melody_metre = self.melody_metre.get()
        self._duration_label = self.duration_var.get()
        voice_label = i18n.untr(self.melody_voice_menu.get())
        self._melody_voice = next(
            (i for i, k in enumerate(self.voice_keys)
             if VOICE_CATALOG[k].label == voice_label), 0)

        # La voz elegida tiene que poder cantar lo que se dibujó. Sin esta
        # comprobación, una melodía fuera de su registro dejaba pasar la
        # pantalla, se iba a buscar durante varios segundos y volvía con el
        # mensaje genérico de "no hay ninguna forma de escribir esta
        # progresión" --- que no dice lo único que hacía falta saber.
        chosen = VOICE_CATALOG[self.voice_keys[self._melody_voice]]
        pitches = [note.pitch for note in self._build_melody().notes]
        # La nota que **se sale**, no la más aguda. Anunciando `max(pitches)`
        # el aviso nombraba una nota que entraba perfecto cada vez que lo que
        # sobraba era un grave, así que decía que el problema estaba donde no
        # estaba. Y se miran los dos bordes por separado: una línea puede
        # pasarse por arriba y por abajo a la vez.
        too_high = [p for p in pitches if p > chosen.high]
        too_low = [p for p in pitches if p < chosen.low]
        if too_high or too_low:
            if too_high and too_low:
                detail = (trf("La melodía baja hasta {note_name} y sube "
                              "hasta {note_name2}",
                              note_name=note_name(min(too_low)),
                              note_name2=note_name(max(too_high))))
            elif too_high:
                detail = trf("La melodía sube hasta {note_name}",
                             note_name=note_name(max(too_high)))
            else:
                detail = trf("La melodía baja hasta {note_name}",
                             note_name=note_name(min(too_low)))
            # Sin mandar a la pantalla de voces: en el Armonizador no existe
            # ---el modo fija la textura por estilo--- así que el consejo era
            # una puerta que no está.
            self.melody_hint.configure(
                text=trf("{detail}, y {lower} sólo canta de {note_name} a "
                         "{note_name2}. Elegí otra voz en «Mi voz es» o "
                         "movela de octava.",
                         detail=detail, lower=chosen.label.lower(),
                         note_name=note_name(chosen.low),
                         note_name2=note_name(chosen.high)),
                text_color=WARN)
            return False

        found = set()
        if achievements.supreme_melody(self._melody_notes,
                                       [value for _label, value in DURATIONS]):
            found.add("supreme_melody")
        # El salto y la cita se miden en alturas reales, no en posiciones del
        # pentagrama: la armadura decide qué notas son. `pitches` ya se armó
        # arriba, para la comprobación de registro.
        if achievements.has_tritone_leap(pitches):
            found.add("tritone_leap")
        if achievements.has_the_lick(pitches):
            found.add("the_lick")
        self._award(found)
        return True

    def _build_melody(self, written=None, marks=None,
                      key_label=None, metre=None, skips=None,
                      alterations=None):
        """Turn what is on the staff into a melody the engine understands.

        Sin argumentos devuelve la melodía **guardada**, que es la que se va
        a armonizar. Los argumentos existen para la vista previa: mientras el
        usuario dibuja no hay nada guardado todavía, y lo que hay que mirar
        es el pentagrama y los menús tal como están en ese momento.

        `alterations` son los accidentes escritos, por posición (ver
        `StaffEditor.accidentals`). Sin ellos un sol sostenido llegaba al
        armonizador como sol y la nota fuera de la escala no existía.
        """
        if alterations is None:
            alterations = getattr(self, "_melody_accidentals", {})
        label = key_label or getattr(self, "_key_label", self.KEY_SIGNATURES[0][0])
        fifths = next((f for name, f in self.KEY_SIGNATURES if name == label), 0)
        beats, beat_type = (int(x) for x in
                            (metre or getattr(self, "_melody_metre", "4/4")
                             ).split("/"))
        tonic, mode_key = importer.key_from_fifths(fifths)
        per_bar = beats * 4.0 / beat_type
        if written is None:
            written = getattr(self, "_melody_notes", [])
        # La armadura dice dos tonalidades; la nota final elige entre ellas.
        if written:
            tonic, mode_key = harmonize.key_of_ending(
                staff_pitch(written[-1][0], fifths,
                            alterations.get(len(written) - 1)), tonic)
        if marks is None:
            marks = getattr(self, "_melody_marks", set())
        if skips is None:
            skips = getattr(self, "_melody_skips", set())

        notes, bars = [], []
        position = 0.0
        for order, (index, duration) in enumerate(written):
            bar_index = int(position // per_bar)
            while len(bars) <= bar_index:
                bars.append(harmonize.MelodyBar(beats, beat_type, tonic, mode_key))
            notes.append(harmonize.MelodyNote(
                pitch=staff_pitch(index, fifths, alterations.get(order)),
                duration_quarters=duration,
                bar_index=bar_index,
                offset_quarters=position - bar_index * per_bar,
                # Lo que el usuario marcó viaja con la nota, que es lo único
                # que llega hasta el armonizador: la posición en el
                # pentagrama no significa nada del otro lado.
                must_harmonise=order in marks,
                # Y lo que apagó también: sin esto el armonizador vuelve a
                # poner el acorde que el usuario acaba de sacar.
                skip_harmonise=order in skips,
            ))
            position += duration
        if not bars:
            bars.append(harmonize.MelodyBar(beats, beat_type, tonic, mode_key))
        return harmonize.Melody(notes=notes, bars=bars,
                                melody_voice=getattr(self, "_melody_voice", 0))

    def _harmonisation_rules(self):
        """Con qué reglas se arma la vista previa de lo que va a llevar acorde.

        Las dos preguntas que faltan ---color y préstamos--- se contestan dos
        pantallas más adelante y no cambian **dónde** cae un acorde, que es
        lo único que la vista previa dibuja.
        """
        return harmonize.HarmonisationSettings(
            genre_key=self._search_genre(),
            with_sevenths=(self.genre_key == "jazz"),
        )

    def _refresh_harmony_preview(self) -> None:
        """Pintar de dorado las notas que van a recibir un acorde.

        Se recalcula en cada cambio del pentagrama: es barato ---no elige
        acordes, sólo lugares--- y tiene que contestar mientras se escribe,
        que es cuando la respuesta sirve.
        """
        if not hasattr(self, "staff"):
            return
        try:
            melody = self._build_melody(
                written=self.staff.notes, marks=self.staff.marked,
                key_label=i18n.untr(self.key_menu.get()),
                metre=self.melody_metre.get(),
                skips=self.staff.blocked,
                alterations=self.staff.accidentals)
            planned = harmonize.planned_notes(melody, self._harmonisation_rules())
        except (tk.TclError, AttributeError, ValueError):
            return
        chosen = {(note.bar_index, note.offset_quarters) for note in planned}
        self.staff.harmonised = {
            order for order, note in enumerate(melody.notes)
            if (note.bar_index, note.offset_quarters) in chosen
        }
        self.staff.redraw()

    # -- screen: harmony (generator only) -----------------------------------

    ENDPOINT_MODES = [N("Libre"), N("Preferido"), N("Obligatorio")]

    #: Everything the harmony and parameters screens cache between visits.
    #: All of it belongs to a style, so it is dropped when the style changes.
    GENRE_SCOPED = (
        "_borrowed_saved", "_borrowed_weight", "_harmony_emphasis",
        "_colour_weight", "_manual_colour", "_mod_key", "_mod_modal",
        "_strict_counterpoint",
        "_mod_weight", "_sevenths", "_passing_saved", "_passing_density",
        "_passing_chromatic", "_start_roman", "_end_roman", "_start_mode",
        "_end_mode", "_cadence_choice", "_balance_position",
    )

    def _reset_to_defaults(self) -> None:
        """
        Throw away every choice and go back to the genre's defaults.

        Called whenever the user returns to the start, whatever route they
        took. Clearing `_cached_genre` alone was not enough: the parameters
        screen keeps its own state (the balance slider, the cadence menu, the
        switch answers) and those survived, so the last two steps came back
        with the previous run's settings still in place.
        """
        for name in self.GENRE_SCOPED:
            if hasattr(self, name):
                delattr(self, name)
        self.switch_vars.clear()
        self._switch_state = {}
        self._cached_genre = None
        self.outcome = None
        self.request = None

    def _forget_genre_settings(self) -> None:
        """
        Drop every cached choice that belongs to a style.

        Checked here, when a screen is about to read them, rather than only
        when the genre button is pressed: the screens can be reached by
        several routes and one of them skipped the reset, so a jazz setup
        quietly survived into a Gregorian run.
        """
        if getattr(self, "_cached_genre", None) == self.genre_key:
            return
        for name in self.GENRE_SCOPED:
            if hasattr(self, name):
                delattr(self, name)
        self.switch_vars.clear()
        self._switch_state = {}
        self._cached_genre = self.genre_key
        self._apply_genre_defaults()

    #: Todo lo que la pantalla de tonalidad guarda entre visitas, y todo lo
    #: que «Resetear» borra: sacado el atributo, cada control vuelve a leer
    #: el valor con el que lo deja el estilo. No están acá ni las voces, ni
    #: los registros, ni nada de la pantalla de parámetros --- son de otro
    #: paso y resetearlos desde éste sería deshacer algo que no se ve.
    HARMONY_SCOPED = (
        "_tonic", "_mode_label", "_mode_key",
        "_start_roman", "_end_roman", "_start_mode", "_end_mode",
        "_borrowed_saved", "_borrowed_weight", "_harmony_emphasis",
        "_colour_weight", "_mod_key", "_mod_modal", "_mod_weight",
        "_sevenths", "_passing_saved", "_passing_chromatic",
        "_passing_density",
    )

    def _reset_harmony(self) -> None:
        """Devolver la pantalla de tonalidad a lo que trae el estilo."""
        for name in self.HARMONY_SCOPED:
            if hasattr(self, name):
                delattr(self, name)
        self._apply_genre_harmony_defaults()
        self._render()

    def _screen_harmony(self) -> None:
        self._forget_genre_settings()
        self._heading(
            tr("Elegí la tonalidad y los acordes"),
            tr("El programa arma la progresión sólo con lo que permitas acá."))

        columns = ctk.CTkFrame(self.body, fg_color="transparent")
        columns.pack(fill="both", expand=True)
        columns.grid_columnconfigure((0, 1), weight=1, uniform="harm")
        columns.grid_rowconfigure(0, weight=1)

        # A scrollable frame reports its own natural height and grid honours
        # it, so `sticky="nsew"` alone left both panels at ~216px inside a
        # 630px area: two thirds of the screen sat empty and everything went
        # behind a scrollbar that was not needed. The height is set from the
        # space actually on screen instead.
        # Derived from the window height rather than measured. Calling
        # update_idletasks() here forced a full relayout every time the
        # screen was drawn, which made this page take three times as long as
        # any other -- and the answer is the same either way, since the body
        # is simply the window minus the fixed header and footer.
        available = max(360, self.winfo_height() - 260)

        # --- left: key, mode, endpoints ---
        #: Los dos paneles, con nombre para que la guía pueda señalarlos.
        self.material_panel = left = ctk.CTkScrollableFrame(
            columns, fg_color=SURFACE_LIGHT, corner_radius=11,
            height=available)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 4))

        ctk.CTkLabel(left, text=tr("Tonalidad"), font=scaled(("Segoe UI Semibold", 14))
                     ).pack(anchor="w", padx=16, pady=(14, 8))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        self.tonic_menu = ctk.CTkOptionMenu(
            row, values=list(SHARP_NAMES), width=80, fg_color=SURFACE,
            button_color=SURFACE, button_hover_color=ACCENT_HOVER,
            command=self._follow_key_change)
        self.tonic_menu.set(getattr(self, "_tonic", "C"))
        self.tonic_menu.pack(side="left")
        self.mode_menu = ctk.CTkOptionMenu(
            row, values=trs(m.label for m in harmony.MODES.values()),
            width=180,
            fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT_HOVER,
            command=self._follow_key_change)
        self.mode_menu.set(tr(getattr(self, "_mode_label",
                                      harmony.MODES["major"].label)))
        self.mode_menu.pack(side="left", padx=10)

        ctk.CTkLabel(left, text=tr("Acorde inicial y final"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(16, 4))
        ctk.CTkLabel(left,
                     text=tr("Cada uno puede ser libre, preferido u "
                             "obligatorio. Obligatorio deja un solo acorde "
                             "posible en ese lugar."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=16)
        # The tonic is written "I" in a major key and "i" in a minor one, so
        # the default has to follow the mode. Leaving "I" there after a
        # switch to minor blocked the user on a mistake that was not theirs.
        tonic_numeral = "i" if self._mode_key_now() in harmony.MINOR_MODES else "I"

        for label, attr in (("Empieza en", "start"), ("Termina en", "end")):
            line = ctk.CTkFrame(left, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(line, text=tr(label), font=FONT_SMALL, width=90,
                         anchor="w").pack(side="left")
            roman = ctk.CTkEntry(line, width=70)
            roman.insert(0, getattr(self, f"_{attr}_roman", None) or tonic_numeral)
            roman.pack(side="left")
            menu = ctk.CTkOptionMenu(line, values=trs(self.ENDPOINT_MODES),
                                     width=130,
                                     fg_color=SURFACE, button_color=SURFACE,
                                     button_hover_color=ACCENT_HOVER)
            menu.set(tr(getattr(self, f"_{attr}_mode", "Obligatorio")))
            menu.pack(side="left", padx=8)
            setattr(self, f"{attr}_roman_entry", roman)
            setattr(self, f"{attr}_mode_menu", menu)
        # Con qué numeral se escribía la tónica cuando se dibujó la pantalla.
        # Es lo que permite distinguir un campo que quedó en el valor por
        # defecto de uno que el usuario eligió a mano.
        self._tonic_numeral_shown = tonic_numeral

        ctk.CTkLabel(left, text=tr("Notas de paso"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(16, 4))
        ctk.CTkLabel(left,
                     text=tr("Rellenan un salto de tercera con movimiento por "
                             "grado conjunto. Elegí qué voces pueden usarlas."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=16)
        self.passing_vars: Dict[int, tk.BooleanVar] = {}
        for index, key in enumerate(self.voice_keys):
            var = tk.BooleanVar(value=getattr(self, "_passing_saved", {}).get(index, False))
            self.passing_vars[index] = var
            ctk.CTkCheckBox(left, text=tr(VOICE_CATALOG[key].label), variable=var,
                            font=FONT_SMALL, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER).pack(anchor="w", padx=16,
                                                           pady=3)
        ctk.CTkLabel(left, text=tr("Con qué frecuencia aparecen"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(8, 2))
        self.passing_density = LabelledSlider(
            left, N("pocas"), N("muchas"), 0.0, 1.0,
            getattr(self, "_passing_density", 0.45))
        self.passing_density.pack(fill="x", padx=16, pady=(0, 8))

        chrom = ctk.CTkFrame(left, fg_color="transparent")
        chrom.pack(fill="x", padx=16, pady=(6, 16))
        self.passing_chromatic = tk.BooleanVar(
            value=getattr(self, "_passing_chromatic", False))
        chromatic_box = ctk.CTkCheckBox(
            chrom, text=tr("Permitir cromáticas"), variable=self.passing_chromatic,
            font=FONT_SMALL, fg_color=ACCENT, hover_color=ACCENT_HOVER)
        chromatic_box.pack(anchor="w")
        Tooltip(chromatic_box,
                tr("Deja que los adornos usen notas fuera de la escala. Suena "
                   "más rico, pero probablemente haya que retocar alguno a "
                   "mano, porque el programa no juzga si la nota cromática "
                   "encaja."))

        # --- right: borrowed chords ---
        self.borrowed_panel = right = ctk.CTkScrollableFrame(
            columns, fg_color=SURFACE_LIGHT, corner_radius=11,
            height=available)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 4))
        ctk.CTkLabel(right, text=tr("Intercambios modales"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(14, 4))
        ctk.CTkLabel(right,
                     text=tr("Acordes prestados del modo paralelo. Pasá el mouse "
                             "por cada uno para ver qué aporta."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=16, pady=(0, 6))

        self.borrowed_vars: Dict[str, tk.BooleanVar] = {}
        # First visit starts from what the chosen style usually borrows,
        # rather than from nothing.
        saved = getattr(self, "_borrowed_saved", None)
        if saved is None:
            saved = set(harmony.GENRE_DEFAULT_BORROWED.get(self.genre_key, []))
        for key, spec in harmony.BORROWED_CHORDS.items():
            var = tk.BooleanVar(value=key in saved)
            self.borrowed_vars[key] = var
            box = ctk.CTkCheckBox(right, text=tr(spec.label), variable=var,
                                  font=FONT_SMALL, fg_color=ACCENT,
                                  hover_color=ACCENT_HOVER)
            box.pack(anchor="w", padx=16, pady=4)
            Tooltip(box, spec.description)

        ctk.CTkLabel(right, text=tr("Cuánto usarlos"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(14, 2))
        # Reads left-to-right as less-to-more, like every other slider here.
        # Running it the other way meant dragging it down made the program do
        # more of the thing, which nobody expects.
        #
        # La escala llega a 100 y no a 40 porque a 40 el tope no alcanzaba:
        # el premio por prestar un acorde competía contra la gramática
        # entera, y contra ella una progresión diatónica seguía saliendo más
        # barata por mucho margen. Medido sobre diez progresiones de ocho
        # acordes, el tope viejo daba 14% de préstamos --- o sea "muy
        # seguido" y "casi nunca" eran casi lo mismo --- y el nuevo da 60%.
        self.borrowed_slider = LabelledSlider(
            right, N("casi nunca"), N("muy seguido"), 0, 100,
            getattr(self, "_borrowed_weight", BORROWED_DEFAULT))
        self.borrowed_slider.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(right, text=tr("Peso de la armonía frente a la "
                                    "conducción de voces"),
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w",
                                                                  padx=16,
                                                                  pady=(12, 2))
        # The low end used to hand the decision to the voice leading, and the
        # generator was only usable at the top of the range: with the harmony
        # quiet the cheapest progression is barely a progression at all. The
        # scale now runs from "follows the style" to "follows it strictly".
        self.harmony_slider = LabelledSlider(
            right, N("estilo flexible"), N("estilo estricto"),
            4.0, 14.0, getattr(self, "_harmony_emphasis", 8.0))
        self.harmony_slider.pack(fill="x", padx=16, pady=(0, 12))

        self.sevenths_var = tk.BooleanVar(
            value=getattr(self, "_sevenths",
                          harmony.GENRE_SEVENTHS.get(self.genre_key, False)))
        sevenths_box = ctk.CTkCheckBox(
            right, text=tr("Acordes de séptima"), variable=self.sevenths_var,
            font=FONT_SMALL, fg_color=ACCENT, hover_color=ACCENT_HOVER)
        sevenths_box.pack(anchor="w", padx=16, pady=(10, 4))
        Tooltip(sevenths_box,
                tr("Arma los acordes con cuatro notas en vez de tres, por "
                   "ejemplo Cmaj7 en lugar de C. Es lo normal en jazz y la "
                   "excepción en los otros estilos."))

        ctk.CTkLabel(right, text=tr("Modulaciones"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(6, 2))
        ctk.CTkLabel(right,
                     text=tr("La pieza puede pasar a otra tonalidad o cambiar "
                             "de modo sobre la misma tónica. Siempre vuelve "
                             "al punto de partida antes de terminar."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=16)

        genre_modulation = harmony.GENRE_MODULATION.get(
            self.genre_key, harmony.ModulationSettings())
        self.mod_key_var = tk.BooleanVar(
            value=getattr(self, "_mod_key", genre_modulation.key_enabled))
        self.mod_modal_var = tk.BooleanVar(
            value=getattr(self, "_mod_modal", genre_modulation.modal_enabled))
        # Below eight bars there is no room to establish home, travel and
        # come back, so the option is shown greyed with the reason rather
        # than silently doing nothing when ticked.
        enough_bars = self.bar_count >= harmony.ModulationSettings().min_bars_for_modulation
        state = "normal" if enough_bars else "disabled"

        key_box = ctk.CTkCheckBox(right, text=tr("A otra tonalidad"),
                                  variable=self.mod_key_var, font=FONT_SMALL,
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                  state=state)
        key_box.pack(anchor="w", padx=16, pady=(6, 2))
        if not enough_bars:
            self.mod_key_var.set(False)
            self.mod_modal_var.set(False)
        modal_box = ctk.CTkCheckBox(right, text=tr("De modo (misma tónica)"),
                                    variable=self.mod_modal_var, font=FONT_SMALL,
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    state=state)
        modal_box.pack(anchor="w", padx=16, pady=2)
        # Los destinos dependen del estilo y del modo elegido, así que los
        # dos textos ---y si el tilde de modo sirve de algo--- se rehacen
        # cada vez que cambia la tonalidad, no una sola vez al dibujar.
        self._mod_boxes = (key_box, modal_box)
        self._mod_tips = (Tooltip(key_box, ""), Tooltip(modal_box, ""))
        self._mod_enough_bars = enough_bars
        self._refresh_modulation_labels()

        ctk.CTkLabel(right, text=tr("Cuánto se aleja"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(8, 2))
        self.mod_slider = LabelledSlider(
            right, N("casi nunca"), N("muy seguido"), 0.0, 60.0,
            getattr(self, "_mod_weight", abs(genre_modulation.weight)))
        self.mod_slider.pack(fill="x", padx=16, pady=(0, 14))
        #: El bloque de la modulación, para que la guía lo señale entero: son
        #: dos tildes y un deslizador, y señalar uno solo deja los otros dos
        #: fuera de la explicación que los nombra.
        self.modulation_block = key_box

        ctk.CTkLabel(right, text=tr("Acordes con color añadido"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(6, 2))
        ctk.CTkLabel(right,
                     text=tr("Cuando a un acorde le sobran voces, en vez de "
                             "repetir una nota puede agregar una novena, una "
                             "oncena o una sexta."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=16)
        # With five or six voices a plain triad has nothing left to do but
        # double itself, which is why jazz starts with colour switched on
        # once the texture is that thick. Still a slider, still switchable.
        colour_default = getattr(self, "_colour_weight", None)
        if colour_default is None:
            colour_default = (14.0 if self.genre_key == "jazz"
                              and len(self.voice_keys) > 4 else 0.0)
        self.colour_slider = LabelledSlider(
            right, N("sin color"), N("mucho color"), 0.0, 30.0,
            colour_default)
        self.colour_slider.pack(fill="x", padx=16, pady=(4, 16))

        self.harmony_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                         text_color=WARN)
        self.harmony_hint.pack(anchor="w", pady=(8, 0))

        self._maybe_guide("harmony")

    def _pool_now(self):
        """Los acordes que existen en la tonalidad elegida en este momento."""
        return harmony.build_chord_pool(
            parse_pitch_class(self.tonic_menu.get()),
            harmony.MODES[self._mode_key_now()],
            sorted(k for k, v in self.borrowed_vars.items() if v.get()),
        )

    def _follow_key_change(self, _value=None) -> None:
        """
        Poner los grados de arranque y cierre en la tonalidad recién elegida.

        Cambiar a menor dejaba un "I" que en esa tonalidad no existe, y el
        programa recién lo decía al apretar Siguiente. Ahora el campo sigue
        a la tonalidad solo.

        Lo que el usuario haya elegido a mano se respeta mientras siga
        existiendo. Si sólo cambió de caja -- el V del mayor es el v del
        frigio -- se corrige la caja en vez de perder la elección.
        """
        # La pantalla se arma de arriba hacia abajo y los menús existen antes
        # que los campos; un cambio disparado a mitad del armado no tiene
        # todavía a quién escribirle.
        if not (hasattr(self, "start_roman_entry")
                and hasattr(self, "end_roman_entry")
                and hasattr(self, "borrowed_vars")):
            return
        try:
            pool = self._pool_now()
        except (AttributeError, tk.TclError, KeyError):
            return
        available = {option.roman for option in pool}
        mode = harmony.MODES[self._mode_key_now()]
        tonic = next((option.roman for option in pool
                      if option.scale_degree == mode.tonic_degree),
                     "i" if self._mode_key_now() in harmony.MINOR_MODES else "I")
        folded = {roman.lower(): roman for roman in available}
        previous = getattr(self, "_tonic_numeral_shown", "I")

        for field in (self.start_roman_entry, self.end_roman_entry):
            text = field.get().strip()
            if text and text != previous:
                if text in available:
                    continue                      # elección propia, y existe
                same = folded.get(text.lower())
                if same is not None:
                    text = same                   # el mismo grado, otra caja
                else:
                    text = tonic
            else:
                text = tonic
            field.delete(0, "end")
            field.insert(0, text)
        self._tonic_numeral_shown = tonic
        self._refresh_modulation_labels()

    def _modulation_targets_now(self):
        """Los destinos que el estilo ofrece para el modo elegido ahora.

        Devuelve ``(tonalidades, modales)``. Se pregunta con los dos
        interruptores encendidos a propósito: la lista es la de lo que cada
        tilde *ofrecería*, no la de lo que está prendido.
        """
        genre = harmony.GENRE_MODULATION.get(self.genre_key,
                                             harmony.ModulationSettings())
        probe = harmony.ModulationSettings(
            key_enabled=True, modal_enabled=True, targets=genre.targets)
        keys, modals = [], []
        for name in harmony.available_targets(probe, self._mode_key_now()):
            target = harmony.MODULATION_TARGETS[name]
            (modals if target.is_modal else keys).append(target.short_label)
        return keys, modals

    def _refresh_modulation_labels(self) -> None:
        """Poner en los dos tildes lo que realmente pueden hacer.

        El estilo decide los destinos y el modo descarta el que coincide con
        el modo en el que la pieza ya está, así que la lista no es fija: en
        barroco menor el cambio de modo es a mayor y no a menor.
        """
        if not hasattr(self, "_mod_tips"):
            return
        key_tip, modal_tip = self._mod_tips
        key_box, modal_box = self._mod_boxes
        # El menú de tonalidad se arma antes que esta columna, así que un
        # cambio disparado a mitad del redibujado todavía apunta a los
        # tildes de la pantalla anterior.
        try:
            if not (key_box.winfo_exists() and modal_box.winfo_exists()):
                return
        except tk.TclError:
            return
        if not self._mod_enough_bars:
            no_room = (trf("Hacen falta al menos 8 compases para asentar la "
                           "tonalidad, irse y volver. Ahora hay {bar_count}.",
                           bar_count=self.bar_count))
            key_tip.text = modal_tip.text = no_room
            return
        keys, modals = self._modulation_targets_now()
        key_tip.text = (trf("Pasa a otra tonalidad ({listed}) y vuelve.",
                            listed=_listed(keys)) if keys else
                        "Este estilo no viaja a otra tonalidad.")
        if modals:
            modal_tip.text = (trf("La tónica se queda y el modo cambia a "
                                  "{listed}.",
                                  listed=_listed(modals)))
            modal_box.configure(state="normal")
        else:
            # Sin destino modal el tilde se prendía y no pasaba nada.
            modal_tip.text = ("Este estilo no ofrece ningún cambio de modo "
                              "sobre la tónica que elegiste.")
            self.mod_modal_var.set(False)
            modal_box.configure(state="disabled")
        key_box.configure(state="normal" if keys else "disabled")
        if not keys:
            self.mod_key_var.set(False)

    def _mode_key_now(self) -> str:
        """The mode currently chosen, before it has been committed."""
        try:
            label = i18n.untr(self.mode_menu.get())
        except (AttributeError, tk.TclError):
            return getattr(self, "_mode_key", "major")
        return next((k for k, m in harmony.MODES.items() if m.label == label),
                    "major")

    def _commit_harmony(self) -> bool:
        self._tonic = self.tonic_menu.get()
        self._mode_label = i18n.untr(self.mode_menu.get())
        previous_mode = getattr(self, "_mode_key", None)
        self._mode_key = next(
            (k for k, m in harmony.MODES.items() if m.label == self._mode_label),
            "major",
        )
        # Switching between major and minor changes how the tonic is written,
        # so an endpoint left over from the other mode is corrected rather
        # than reported as the user's error.
        if previous_mode != self._mode_key:
            minor_now = self._mode_key in harmony.MINOR_MODES
            for field in (self.start_roman_entry, self.end_roman_entry):
                text = field.get().strip()
                if text in ("I", "i"):
                    field.delete(0, "end")
                    field.insert(0, "i" if minor_now else "I")
        self._start_roman = self.start_roman_entry.get().strip()
        self._end_roman = self.end_roman_entry.get().strip()
        self._start_mode = i18n.untr(self.start_mode_menu.get())
        self._end_mode = i18n.untr(self.end_mode_menu.get())
        self._borrowed_saved = {k for k, v in self.borrowed_vars.items() if v.get()}
        self._borrowed_weight = float(self.borrowed_slider.get())
        self._harmony_emphasis = float(self.harmony_slider.get())
        self._colour_weight = float(self.colour_slider.get())
        self._mod_key = self.mod_key_var.get()
        self._mod_modal = self.mod_modal_var.get()
        self._mod_weight = float(self.mod_slider.get())
        self._sevenths = self.sevenths_var.get()
        self._passing_saved = {i: v.get() for i, v in self.passing_vars.items()}
        self._passing_chromatic = self.passing_chromatic.get()
        self._passing_density = float(self.passing_density.get())

        # A roman numeral that does not exist in this key would silently
        # never match, leaving the endpoint unconstrained without saying so.
        pool = harmony.build_chord_pool(
            parse_pitch_class(self._tonic), harmony.MODES[self._mode_key],
            sorted(self._borrowed_saved),
        )
        available = {option.roman for option in pool}
        for label, roman, mode in (("inicial", self._start_roman, self._start_mode),
                                   ("final", self._end_roman, self._end_mode)):
            if mode != "Libre" and roman and roman not in available:
                self.harmony_hint.configure(
                    text=trf("El acorde {label} «{roman}» no existe en "
                             "esta tonalidad. Disponibles: {value}",
                             label=label, roman=roman,
                             value=', '.join(sorted(available)))
                )
                return False

        # Todo lo prestado permitido y la modulación en el tope del dial. El
        # dial llega a 60; se acepta el último tramo para que no dependa de
        # clavar el pixel exacto.
        if (self._borrowed_saved == set(harmony.BORROWED_CHORDS)
                and self._mod_weight >= 59.0):
            self._award({"thief"})

        # Todo al máximo y todo prendido: se anota acá, que es donde están
        # los diales, y se cobra al terminar la corrida --- que es cuando el
        # generador terminó de dar todo lo que se le pidió.
        self._blast_armed = eggs.blast(
            {"borrowed": self._borrowed_weight,
             "harmony": self._harmony_emphasis,
             "modulation": self._mod_weight,
             "colour": self._colour_weight,
             "passing": self._passing_density},
            list(self._passing_saved.values())
            + [self._passing_chromatic, self._sevenths, self._mod_key,
               self._mod_modal]
            + [key in self._borrowed_saved for key in harmony.BORROWED_CHORDS],
        )
        return True

    # -- screen 5: parameters ----------------------------------------------

    #: Only shown in the hand-written mode; the generator has its own copy
    #: on the harmony screen.
    MANUAL_SWITCHES = [
        ("forbid_harmonic_tritone", "Evitar tritonos entre voces",
         "Descarta cualquier disposición donde dos voces suenen a distancia "
         "de tritono. Sirve sobre todo para que las notas de color añadidas "
         "no formen uno."),
    ]

    SWITCH_LABELS = [
        ("forbid_parallel_fifths", N("Prohibir quintas paralelas"),
         "Dos voces a distancia de quinta que se mueven juntas en la misma "
         "dirección y mantienen la quinta. Es la prohibición más conocida del "
         "contrapunto, porque las dos líneas se oyen como una sola."),
        ("forbid_parallel_octaves", N("Prohibir octavas paralelas"),
         "Lo mismo que las quintas paralelas pero a distancia de octava o "
         "unísono. Suena todavía más fusionado, así que en la práctica común "
         "está igual de prohibido."),
        ("forbid_melodic_tritone", "Prohibir tritono melódico",
         "Que una voz salte un tritono, es decir tres tonos de una vez (por "
         "ejemplo de fa a si). Es un intervalo áspero y difícil de cantar, y "
         "los estilos antiguos lo evitan."),
        ("forbid_voice_crossing", "Prohibir cruce de voces",
         "Que una voz cante más agudo que la voz que tiene arriba (por "
         "ejemplo el tenor por encima del alto). Confunde al oído sobre qué "
         "línea es cuál. Conviene dejarlo prendido salvo en texturas muy "
         "densas de 5 o 6 voces."),
    ]

    # NOTE: consonance at the points of repose is deliberately NOT in this
    # list. It used to appear both here as a hard switch and on the right as
    # a weight menu that ALSO offered "require", so the same decision lived
    # in two places and the switch quietly overrode the menu. It is now the
    # menu alone, whose last option is the hard rule.

    GA_FIELDS = [
        ("population_size", "Población", "200",
         "Cuántas soluciones conviven en cada generación. Más población "
         "explora mejor pero tarda más."),
        ("generations", N("Generaciones"), "300",
         "Cuántas veces se repite el ciclo de selección, cruza y mutación."),
        ("elitism", N("Elitismo"), "2",
         "Cuántas de las mejores soluciones pasan intactas a la generación "
         "siguiente, sin riesgo de perderse."),
        ("tournament_size", "Tamaño de torneo", "3",
         "Cuántos candidatos compiten para ser padres. Más alto = más "
         "presión hacia los mejores, pero menos diversidad."),
        ("crossover_rate", "Prob. de cruza", "0.85",
         "Probabilidad de combinar dos padres. Es lo que más mueve la "
         "búsqueda, porque junta tramos enteros de buena conducción de voces, "
         "y por eso va bastante más alta que la mutación."),
        ("uniform_crossover_share", N("Cruza uniforme"), "0.4",
         "De esas cruzas, qué fracción mezcla voz por voz (permite juntar un "
         "buen bajo con una buena soprano) en vez de cortar la progresión en "
         "un punto."),
        ("mutation_rate", "Tasa de mutación", "0.12",
         "Probabilidad de que una nota cambie de octava o pase a otra nota "
         "del acorde. Sirve para ajustes finos."),
    ]

    #: El algoritmo recortado, para una máquina que no da abasto.
    #:
    #: **La población NO se toca, y es lo más importante de este preset.**
    #: Parece el primer número que uno bajaría ---es el que multiplica todo
    #: el trabajo--- y es el único que no se puede. El sembrado arranca con
    #: `población x 12` intentos de armar un cromosoma válido, y armar uno
    #: exige que *todos* los pares de acordes consecutivos lo sean: con 64
    #: acordes eso decae geométricamente y la corrida entera vive de esos
    #: intentos. Medido en el Generador a 32 compases, bajando la población a
    #: 140 el programa deja de encontrar **cualquier** solución y contesta
    #: "no hay ninguna forma de escribir esta progresión", que además es
    #: mentira. Un modo de bajos recursos que hace fallar la generación no es
    #: un modo de bajos recursos.
    #:
    #: Así que el recorte va entero por las generaciones: la mitad de vueltas
    #: es la mitad de trabajo, y el corte por estancamiento ya venía cortando
    #: antes cuando la búsqueda se planta. Medido sobre cuatro tareas
    #: ---barroco, coral y jazz a 16 acordes, más el Generador a 32
    #: compases---: **72 s -> 37 s**, con un costo entre 14% y 49% peor según
    #: el caso. Eso es lo que cuesta, y por eso el botón lo dice en vez de
    #: prometer que sale gratis.
    #:
    #: Elitismo, torneo y las tasas de cruza y mutación no entran: no cuestan
    #: cómputo, sólo cambian hacia dónde busca.
    LOW_RESOURCE_PRESET = {"generations": "120"}

    #: Switches that only make sense when the program picks the chords.
    GENERATOR_SWITCHES = [
        ("forbid_harmonic_tritone", "Evitar tritonos entre voces",
         "Descarta cualquier disposición donde dos voces suenen a distancia "
         "de tritono. Prendido, no puede haber acordes de séptima de "
         "dominante, porque ese tritono es lo que los define."),
    ]

    def _screen_parameters(self) -> None:
        self._forget_genre_settings()
        # Rebuilt below only for the style that offers it; clearing it
        # here stops a stale widget from a previous render being read.
        self.strict_var = None
        profile = GENRE_PROFILES[self.genre_key]
        self._heading(
            tr("Ajustá las reglas"),
            trf("Arranca con los valores del estilo {label}. Pasá el mouse "
                "por cada opción para ver qué hace.",
                label=tr(profile.label)))

        columns = ctk.CTkFrame(self.body, fg_color="transparent")
        columns.pack(fill="both", expand=True)
        columns.grid_columnconfigure((0, 1), weight=1, uniform="params")

        #: Guardado para que la guía de esta pantalla pueda señalarlo.
        self.rules_panel = rules = ctk.CTkFrame(
            columns, fg_color=SURFACE_LIGHT, corner_radius=11)
        rules.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(rules, text=tr("Reglas duras"), font=scaled(("Segoe UI Semibold", 14))
                     ).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(rules, text=tr("Una solución que rompa una regla prendida se descarta."),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(anchor="w", padx=16, pady=(0, 8))

        switches = list(self.SWITCH_LABELS)
        switches += (self.GENERATOR_SWITCHES if self.mode == "random"
                     else self.MANUAL_SWITCHES)
        remembered = getattr(self, "_switch_state", {})
        #: clave -> el interruptor dibujado. `switch_vars` guarda las
        #: variables, que no se pueden señalar: una guía necesita el widget.
        self.switch_widgets: Dict[str, ctk.CTkSwitch] = {}
        for key, label, explanation in switches:
            # The genre's default, unless the user already answered for this
            # genre. `_forget_genre_settings` wipes the memory when the style
            # changes, so a stale answer can never cross over.
            var = tk.BooleanVar(
                value=remembered.get(key, bool(getattr(profile, key, False))))
            self.switch_vars[key] = var
            switch = ctk.CTkSwitch(rules, text=tr(label), variable=var,
                                   font=FONT_SMALL, progress_color=ACCENT)
            switch.pack(anchor="w", padx=16, pady=7)
            self.switch_widgets[key] = switch
            Tooltip(switch, explanation)

        self.balance_panel = balance = ctk.CTkFrame(
            columns, fg_color=SURFACE_LIGHT, corner_radius=11)
        balance.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(balance, text=tr("Balance"),
                     font=scaled(("Segoe UI Semibold", 14))).pack(anchor="w", padx=16,
                                                          pady=(14, 2))
        ctk.CTkLabel(balance,
                     text=tr("Al comparar dos soluciones cuenta cuánto se "
                             "mueven las voces y cuánto respetan el estilo. "
                             "Acá decidís qué pesa más."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=380,
                     justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        self.balance_value = ctk.CTkLabel(balance, text="", font=FONT_SMALL,
                                          text_color=ACCENT)

        def on_balance(_value=None) -> None:
            position = self.balance_slider.get()
            motion, style = self._emphases_from(position)
            self.balance_value.configure(
                text=trf("distancia ×{motion:.2f}   ·   estilo ×{style:.2f}",
                         motion=motion, style=style)
            )

        self.balance_slider = ctk.CTkSlider(balance, from_=0, to=100, number_of_steps=100,
                                            progress_color=ACCENT,
                                            button_color=ACCENT,
                                            button_hover_color=ACCENT_HOVER,
                                            command=on_balance)
        self.balance_slider.set(getattr(self, "_balance_position", 50))
        self.balance_slider.pack(fill="x", padx=16, pady=(4, 2))

        legend = ctk.CTkFrame(balance, fg_color="transparent")
        legend.pack(fill="x", padx=16)
        ctk.CTkLabel(legend, text=tr("sólo distancia"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(legend, text=tr("sólo estilo"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="right")
        self.balance_value.pack(anchor="w", padx=16, pady=(6, 4))
        on_balance()

        ctk.CTkLabel(balance,
                     text=tr("Consonancia en los acordes de reposo"),
                     font=FONT_BODY).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(balance,
                     text=tr("Se mide desde el bajo, como en el bajo cifrado. "
                             "En un 3-5-1 el bajo canta la tercera y los "
                             "intervalos son de 3ra y 6ta, los dos "
                             "consonantes. La última opción la vuelve regla "
                             "dura."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=380,
                     justify="left").pack(anchor="w", padx=16)
        self.cadence_menu = ctk.CTkOptionMenu(
            balance, values=trs(["Ignorar", "Premiar apenas",
                                 "Premiar fuerte", "Exigir (regla dura)"]),
            width=200, fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=ACCENT_HOVER,
        )
        self.cadence_menu.set(tr(getattr(self, "_cadence_choice",
                                         "Premiar apenas")))
        self.cadence_menu.pack(anchor="w", padx=16, pady=(8, 16))

        if self.genre_key == "classical":
            strict = ctk.CTkFrame(balance, fg_color=SURFACE, corner_radius=11)
            strict.pack(fill="x", padx=16, pady=(6, 14))
            self.strict_var = tk.BooleanVar(
                value=getattr(self, "_strict_counterpoint", False))
            strict_switch = ctk.CTkSwitch(
                strict, text=tr("Modo coral"),
                variable=self.strict_var,
                font=scaled(("Segoe UI Semibold", 15)),
                switch_width=58, switch_height=28,
                progress_color=ACCENT)
            strict_switch.pack(anchor="w", padx=14, pady=(12, 4))
            blurb = ctk.CTkLabel(
                strict,
                text=tr("Coral al estilo de Bach. Es más estricto que el "
                        "barroco, nunca duplica la sensible, resuelve las "
                        "séptimas hacia abajo y cuida el espaciado entre "
                        "voces."),
                font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=380,
                justify="left")
            blurb.pack(anchor="w", padx=14, pady=(0, 12))
            for widget in (strict, strict_switch, blurb):
                Tooltip(widget,
                        tr("Las mismas reglas, con mucho más peso. Salta "
                           "menos (3 semitonos en vez de 4), castiga el doble "
                           "duplicar la sensible, exige que resuelvan las "
                           "séptimas y no tolera voces solapadas."))

        if self.mode == "harmonise":
            ctk.CTkLabel(balance, text=tr("Armonización"),
                         font=scaled(("Segoe UI Semibold", 14))
                         ).pack(anchor="w", padx=16, pady=(14, 4))
            self.harm_colour = tk.BooleanVar(
                value=getattr(self, "_harm_colour", False))
            colour_box = ctk.CTkCheckBox(
                balance, text=tr("Permitir voicings especiales"),
                variable=self.harm_colour, font=FONT_SMALL,
                fg_color=ACCENT, hover_color=ACCENT_HOVER)
            colour_box.pack(anchor="w", padx=16, pady=3)
            Tooltip(colour_box,
                    tr("Deja que la melodía se apoye también en sextas, séptimas "
                       "o novenas, y que los acordes agreguen color en vez de "
                       "duplicar notas."))
            self.harm_borrowed = tk.BooleanVar(
                value=getattr(self, "_harm_borrowed", True))
            borrowed_box = ctk.CTkCheckBox(
                balance, text=tr("Permitir intercambios modales"),
                variable=self.harm_borrowed, font=FONT_SMALL,
                fg_color=ACCENT, hover_color=ACCENT_HOVER)
            borrowed_box.pack(anchor="w", padx=16, pady=(3, 14))
            Tooltip(borrowed_box,
                    tr("Deja usar el cuarto menor en lugar del IV o del V, y el "
                       "séptimo rebajado justo antes del cierre."))

        if self.mode == "manual":
            ctk.CTkLabel(balance, text=tr("Cuánto color"),
                         font=scaled(("Segoe UI Semibold", 14))
                         ).pack(anchor="w", padx=16, pady=(6, 2))
            ctk.CTkLabel(balance,
                         text=tr("Cuánto busca agregar novenas, oncenas o "
                                 "sextas en lugar de duplicar una nota."),
                         font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=360,
                         justify="left").pack(anchor="w", padx=16)
            ctk.CTkLabel(balance,
                         text=tr("Hasta un tercio de la barra sólo agrega "
                                 "sextas, el color más suave. Más arriba suma "
                                 "novenas y oncenas."),
                         font=FONT_SMALL, text_color=TEXT_MUTED, wraplength=360,
                         justify="left").pack(anchor="w", padx=16)
            self.manual_colour_slider = LabelledSlider(
                balance, N("sin color"), N("mucho"), 0.0, 30.0,
                getattr(self, "_manual_colour", 0.0))
            self.manual_colour_slider.pack(fill="x", padx=16, pady=(4, 14))

        self.param_hint = ctk.CTkLabel(self.body, text="", font=FONT_SMALL,
                                       text_color=WARN)
        self.param_hint.pack(anchor="w", pady=(8, 0))

        # Sólo en el Generador. Esta pantalla es la misma en los tres modos,
        # pero los otros dos ya tienen su guía en la pantalla donde hacen su
        # trabajo --- los acordes, el pentagrama ---, y abrirles una segunda
        # en la pantalla siguiente sería dos velos en dos pasos seguidos. En
        # el Generador no hay tal pantalla: el trabajo del usuario **es**
        # esta configuración, así que acá es donde le corresponde.
        if self.mode == "random":
            self._maybe_guide("parameters")

    def _search_genre(self) -> str:
        """
        The style key the engine actually runs with.

        The strict setting is no longer a style of its own on screen, but it
        still is one in the engine: switching it on runs the chorale profile,
        which is exactly the behaviour it promises. Deliberately not used for
        the history record, so the retired name never surfaces anywhere.
        """
        if self.genre_key == "classical" and getattr(
                self, "_strict_counterpoint", False):
            return "chorale"
        return self.genre_key

    def _principalis_index(self) -> Optional[int]:
        """
        Which voice carries the vox principalis, as an index into the set.

        Returns None whenever organum does not apply: another style, the
        harmonising mode (where the written line settles it), a voice that is
        not in the set, or the lowest voice, which has nothing underneath it
        to be shadowed by.
        """
        if self.genre_key != "gregorian" or self.mode == "harmonise":
            return None
        key = getattr(self, "_principalis_key", None)
        if key is None or key not in self.voice_keys:
            return None
        index = self.voice_keys.index(key)
        return index if index > 0 else None

    def _modulation_banner(self, grid, option_slots, solution) -> bool:
        """
        Escribir a qué tonalidad viaja cada tramo, arriba y centrado.

        Un tramo es una corrida de acordes seguidos que comparten área
        tonal; el cartel abarca esa corrida con `columnspan`, así que queda
        en el medio del violeta y no al costado. Los acordes de casa no
        llevan cartel: decir «acá seguimos en Do» en cada compás sería
        ruido, y el tinte ya distingue los dos casos.
        """
        areas = []
        for column, slot in enumerate(option_slots):
            chosen = None
            if slot.options and column < len(solution.choices):
                chosen = slot.options[min(solution.choices[column],
                                          len(slot.options) - 1)]
            areas.append(
                getattr(getattr(chosen, "harmony", None), "key_area", "") or "")
        if not any(areas):
            return False
        tonic_pc = parse_pitch_class(getattr(self, "_tonic", "C"))

        drawn = False
        column = 0
        while column < len(areas):
            area = areas[column]
            end = column
            while end + 1 < len(areas) and areas[end + 1] == area:
                end += 1
            if area:
                name = harmony.modulation_key_name(area, tonic_pc)
                if name:
                    ctk.CTkLabel(
                        grid, text=trf("→  {name}", name=tr(name)),
                        font=FONT_SMALL,
                        text_color=MODULATION_TEXT, fg_color=MODULATION_TINT,
                        corner_radius=6,
                    ).grid(row=0, column=column + 1, columnspan=end - column + 1,
                           padx=2, pady=(0, 3), sticky="ew")
                    drawn = True
            column = end + 1
        return drawn

    @staticmethod
    def _slot_span(slots) -> str:
        """
        Name the chords a device covers, counting from 1 as the grid does.

        Consecutive positions are written as a range, so a cadence reads
        "acordes 4-5" rather than "acordes 4, 5".
        """
        numbers = sorted({int(s) + 1 for s in slots})
        if not numbers:
            return ""
        runs, start, previous = [], numbers[0], numbers[0]
        for number in numbers[1:]:
            if number == previous + 1:
                previous = number
                continue
            runs.append((start, previous))
            start = previous = number
        runs.append((start, previous))

        parts = [str(a) if a == b else f"{a}-{b}" for a, b in runs]
        plural = len(numbers) > 1
        if len(parts) == 1:
            if plural:
                return trf("acordes {numbers}", numbers=parts[0])
            return trf("acorde {number}", number=parts[0])
        return trf("acordes {value} y {numbers}",
                   value=", ".join(parts[:-1]), numbers=parts[-1])

    @staticmethod
    def _emphases_from(position: float) -> Tuple[float, float]:
        """
        Turn one slider position into the two emphasis multipliers.

        A single control is clearer than two independent numbers: sliding
        towards style raises the style multiplier and lowers the motion one
        at the same time, so the total scale of the cost stays comparable and
        only the balance between the halves changes.
        """
        fraction = max(0.0, min(1.0, position / 100.0))
        motion = 2.0 - 1.6 * fraction        # 2.00 -> 0.40
        style = 0.4 + 2.6 * fraction         # 0.40 -> 3.00
        return motion, style

    def _commit_parameters(self) -> bool:
        # The widgets belong to whichever render drew them, and going home
        # rebuilds the screen; reading a stale reference raises rather than
        # returning nothing.
        if not hasattr(self, "balance_slider"):
            return True
        try:
            self._balance_position = self.balance_slider.get()
            self._cadence_choice = i18n.untr(self.cadence_menu.get())
        except tk.TclError:
            return True
        self._switch_state = {key: var.get()
                              for key, var in self.switch_vars.items()}
        if getattr(self, "strict_var", None) is not None:
            try:
                self._strict_counterpoint = self.strict_var.get()
            except tk.TclError:
                pass
        if getattr(self, "harm_colour", None) is not None and self.mode == "harmonise":
            self._harm_colour = self.harm_colour.get()
            self._harm_borrowed = self.harm_borrowed.get()
        if getattr(self, "manual_colour_slider", None) is not None and self.mode == "manual":
            try:
                self._manual_colour = float(self.manual_colour_slider.get())
            except tk.TclError:
                pass
        # The search settings live behind the gear, so they were only ever
        # read when that panel was open: editing them and pressing Generate
        # without reopening it silently used the previous values.
        self._read_ga_config()
        # Coral, con las quintas paralelas permitidas. Es una combinación
        # perfectamente válida --- todos los switches son independientes ---
        # y por eso el programa no la prohíbe: la comenta.
        if eggs.bach_spinning(
                getattr(self, "_strict_counterpoint", False),
                self._switch_state.get("forbid_parallel_fifths", True)):
            self._egg("bach")
            self._egg_legend("¡Agradecé que Bach está muerto!")
        return True

    # -- running ------------------------------------------------------------

    CADENCE_SETTINGS = {
        "Ignorar": (0.0, False),
        "Premiar apenas": (None, False),      # None = keep the genre default
        "Premiar fuerte": (120.0, False),
        "Exigir (regla dura)": (None, True),
    }

    def _run_search(self) -> None:
        # Clear the previous run first. The results screen renders whatever
        # `self.outcome` holds, so switching modes and generating again
        # flashed the old piece until the new one arrived.
        self.outcome = None
        # «Listo» es esto y no `self.outcome`: en el tramo automático del
        # sendero el outcome se asigna bastante antes de que la pantalla
        # muestre nada --- ver `_run_story_piece` --- así que mirar sólo el
        # outcome dejaba a «Nuevo» activo durante ese hueco. `_show_results`
        # es el único lugar en el que las tres salidas de `_on_finished`
        # ---error, sin solución, éxito--- terminan de verdad.
        self._results_ready = False
        # Y el candado de «Escuchá primero» de un intento anterior, si
        # quedó puesto: se vuelve de «Atrás» sin apretar «Seguir» y la fila
        # se destruye con el resto de la pantalla, pero la referencia se
        # quedaba viva. Sin este borrado, un segundo intento que no llegara
        # a cumplir la traba heredaba el candado del primero y «Nuevo»
        # quedaba gris para siempre, sin ninguna fila que lo explicara.
        self._story_continue_row = None
        self._story_continue_button = None
        self._story_listened = False
        # Una corrida normal vuelve al tempo de la casa: el que deja seguir
        # cuatro voces por separado.
        self._story_speed = None
        overrides = {key: var.get() for key, var in self.switch_vars.items()}

        motion, style = self._emphases_from(getattr(self, "_balance_position", 50))
        overrides["motion_emphasis"] = motion
        overrides["style_emphasis"] = style

        weight, required = self.CADENCE_SETTINGS.get(
            getattr(self, "_cadence_choice", "Premiar apenas"), (None, False)
        )
        if weight is not None:
            overrides["weight_cadence_consonance"] = weight
        # Single source of truth: the menu, whose last option is the hard rule.
        overrides["cadence_consonance_required"] = required
        signature = self._signature_for(0)
        bar_signatures = [self._signature_for(i) for i in range(self.bar_count)]

        if self.mode == "harmonise":
            wants_colour = getattr(self, "_harm_colour", False)
            # The manual mode has a dial from 0 to 30; here the same setting
            # is a checkbox, so ticking it has to mean "yes, colour", not
            # "halfway". At 14 it landed on a colour tone under half the
            # time and the box looked broken. Short of the maximum on
            # purpose: at 30 every spare voice takes a colour and a whole
            # piece of it reads mechanically.
            colour = 24.0 if wants_colour else 0.0
            self.request = session.HarmoniseRequest(
                genre_key=self._search_genre(),
                voice_keys=self.voice_keys,
                melody=self._build_melody(),
                melody_voice=getattr(self, "_melody_voice", 0),
                allow_colour=wants_colour,
                colour_weight=colour,
                allow_borrowed=getattr(self, "_harm_borrowed", True),
                with_sevenths=(self.genre_key == "jazz"),
                switch_overrides={
                    **overrides,
                    "special_voicing_fills": colour > 0.5,
                    "weight_colour_tone": -colour,
                },
                range_overrides=self.range_overrides,
                ga_config=self.ga_config,
            )
            self.index = len(self.screens) - 1
            self._render()
            self._start_worker()
            return

        if self.mode == "random":
            self.request = self._build_generative_request(overrides, signature)
            self.index = len(self.screens) - 1
            self._render()
            self._start_worker()
            return

        self.request = session.JobRequest(
            genre_key=self._search_genre(),
            voice_keys=self.voice_keys,
            entries=self.chord_entries,
            time_signature=signature,
            bar_time_signatures=bar_signatures,
            title="ChordWeaver",
            switch_overrides=overrides,
            range_overrides=self.range_overrides,
            ga_config=self.ga_config,
            # Apagados a propósito, no por omisión: ver `_screen_chords`.
            passing_rules=None,
            principalis_voice=self._principalis_index(),
        )
        # The dial alone decides: anything above the bottom of its range
        # counts as switched on. A separate switch for the same choice was
        # only ever a way for the two to disagree.
        colour = getattr(self, "_manual_colour", 0.0)
        self.request.switch_overrides = {
            **self.request.switch_overrides,
            "special_voicing_fills": colour > 0.5,
            "weight_colour_tone": -colour,
        }

        self.index = len(self.screens) - 1
        self._render()
        self._start_worker()

    def _build_generative_request(self, overrides, signature):
        """Assemble the generator's request from the harmony screen."""
        durations, bars = [], []
        for bar_index in range(self.bar_count):
            bar_signature = self._signature_for(bar_index)
            chosen = 1.0
            for candidate in (2.0, 1.0, 4.0, 0.5):
                quotient = bar_signature.quarters_per_bar / candidate
                if abs(quotient - round(quotient)) < 1e-9 and quotient >= 1:
                    chosen = candidate
                    break
            for _ in range(max(1, int(round(bar_signature.quarters_per_bar / chosen)))):
                durations.append(chosen)
                bars.append(bar_index)

        weights = harmony.genre_harmony_weights(
            self._search_genre(), emphasis=getattr(self, "_harmony_emphasis", 4.0)
        )
        # The slider reads as appetite; the engine wants a cost, so a high
        # appetite becomes a strong negative (a reward).
        weights.borrowed = -getattr(self, "_borrowed_weight", BORROWED_DEFAULT)

        start_mode = getattr(self, "_start_mode", "Obligatorio")
        end_mode = getattr(self, "_end_mode", "Obligatorio")
        required = "Obligatorio" in (start_mode, end_mode)

        chosen_voices = tuple(
            index for index, wanted in getattr(self, "_passing_saved", {}).items()
            if wanted
        )
        density = getattr(self, "_passing_density", 0.45)
        rules = passing.PassingRules(
            voices=chosen_voices,
            diatonic_only=not getattr(self, "_passing_chromatic", False),
            density=density,
            # La barra fija también el tope, no sólo el sorteo: con el tope
            # clavado en cuatro, moverla no cambiaba cuántos adornos se
            # llegaban a escuchar.
            max_per_piece=passing.max_for_density(density),
        ) if chosen_voices else None

        genre_modulation = harmony.GENRE_MODULATION.get(
            self.genre_key, harmony.ModulationSettings())
        modulation = harmony.ModulationSettings(
            key_enabled=getattr(self, "_mod_key", genre_modulation.key_enabled),
            modal_enabled=getattr(self, "_mod_modal", genre_modulation.modal_enabled),
            targets=genre_modulation.targets,
            weight=-getattr(self, "_mod_weight", abs(genre_modulation.weight)),
            switch_cost=genre_modulation.switch_cost,
            min_bars=genre_modulation.min_bars,
            min_bars_for_modulation=genre_modulation.min_bars_for_modulation,
            home_margin_bars=genre_modulation.home_margin_bars,
            weak_return=genre_modulation.weak_return,
            max_excursions=genre_modulation.max_excursions,
        )

        # In this mode the dial IS the control: there is no switch to read,
        # so asking `overrides` for one always came back False and the dial
        # did nothing however far it was dragged. Anything above the bottom
        # of the scale turns colour on.
        colour = getattr(self, "_colour_weight", 0.0)
        overrides = {
            **overrides,
            "special_voicing_fills": colour > 0.5,
            "weight_colour_tone": -colour,
        }

        return session.GenerativeRequest(
            genre_key=self._search_genre(),
            voice_keys=self.voice_keys,
            tonic=getattr(self, "_tonic", "C"),
            mode_key=getattr(self, "_mode_key", "major"),
            borrowed=sorted(getattr(self, "_borrowed_saved", set())),
            with_sevenths=getattr(self, "_sevenths",
                                  harmony.GENRE_SEVENTHS.get(self.genre_key, False)),
            slot_count=len(durations),
            durations=durations,
            bar_indices=bars,
            time_signature=signature,
            title="ChordWeaver",
            switch_overrides=overrides,
            range_overrides=self.range_overrides,
            ga_config=self.ga_config,
            principalis_voice=self._principalis_index(),
            harmony_weights=weights,
            start_roman=(getattr(self, "_start_roman", "I")
                         if start_mode != "Libre" else None),
            end_roman=(getattr(self, "_end_roman", "I")
                       if end_mode != "Libre" else None),
            endpoints_required=required,
            passing_rules=rules,
            modulation=modulation if modulation.enabled else None,
            raise_odds=bool(self.settings.get("raise_cadence_odds", False)),
        )

    def _start_worker(self) -> None:
        request = self.request

        def work() -> None:
            last_sent = [0.0]

            def report(generation: int, best: float) -> None:
                # Throttled to a few updates a second. Posting every
                # generation meant the worker spent its time contending for
                # the queue lock with the Tk main loop instead of searching:
                # the same run took half a second or seventy, depending on
                # how the two happened to interleave.
                now = time.monotonic()
                if now - last_sent[0] < 0.1:
                    return
                last_sent[0] = now
                self.progress_queue.put(("progress", generation, best))
            try:
                # Cruzar y mutar son bucles cerrados de Python corriendo en
                # este hilo, y con el intervalo de cambio de fábrica ---5
                # ms--- se quedan con el GIL en tandas largas. Medido sobre
                # una generación de 32 compases: el bucle de Tk llegaba a
                # clavarse **1240 ms** y siete veces pasaba el medio segundo,
                # que es tiempo de sobra para que Windows deje la ventana a
                # medio repintar --- la pantalla de progreso se veía rota, en
                # pedazos. Es el mismo arreglo que ya usaba la síntesis de
                # sonido, y comparte su contador justamente para que los dos
                # no se pisen al devolver el valor original.
                with ambience.fine_switching():
                    if isinstance(request, session.HarmoniseRequest):
                        outcome = session.harmonise_melody(request, progress=report)
                    elif isinstance(request, session.GenerativeRequest):
                        outcome = session.generate_random(request, progress=report)
                    else:
                        outcome = session.generate(request, progress=report)
                self.progress_queue.put(("done", outcome, None))
            except Exception as exc:                      # noqa: BLE001
                self.progress_queue.put(("done", None, exc))

        self.worker = threading.Thread(target=work, daemon=True)
        # Terminar de pintar ANTES de arrancar la búsqueda.
        #
        # Lo primero que hace la búsqueda es levantar el pool, y en Windows
        # eso es lanzar ocho intérpretes de Python: medido, **1,9 segundos**
        # en los que la ventana no atiende un solo repintado. Si arranca con
        # la pantalla de progreso a medio dibujar, esos dos segundos se
        # quedan con medio cartel viejo y medio nuevo --- que es exactamente
        # el "se ve todo fragmentado". Un `update_idletasks` acá no acelera
        # nada; sólo se asegura de que lo que quede congelado esté entero.
        #
        # No alcanza con el `update_idletasks` que ya hace `_render`: entre
        # aquello y esto se arma el pedido, que crea widgets y ensucia otra
        # vez la cola de dibujo.
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        self.worker.start()
        # Cancel any pump still scheduled from an earlier run. Without this
        # each generation left its own timer behind and they piled up, so the
        # interface got slower every time the user pressed generate.
        self._cancel_pump()
        self._pump_id = self.after(80, self._drain_queue)

    def _cancel_pump(self) -> None:
        """Stop the progress pump if one is scheduled."""
        pump_id = getattr(self, "_pump_id", None)
        if pump_id is not None:
            try:
                self.after_cancel(pump_id)
            except (tk.TclError, ValueError):
                pass
            self._pump_id = None

    def _drain_queue(self) -> None:
        """
        Pump worker messages on the Tk thread.

        Tk is not thread-safe, so the background search only ever puts plain
        data on a queue and every widget update happens here.
        """
        # The search runs on a daemon thread, so the window can be closed
        # while it is still going. Every widget touched here may already be
        # gone by then, and Tk raises rather than ignoring it.
        if not self.winfo_exists():
            return
        if getattr(self, "_rendering", False):
            # Mientras se dibuja una pantalla tapada, la vieja sigue viva y
            # arriba: un resultado consumido ahora se dibujaba en ella y se
            # perdía con ella un instante después. Se espera al cambio.
            self._pump_id = self.after(30, self._drain_queue)
            return
        try:
            latest_progress = None
            while True:
                message = self.progress_queue.get_nowait()
                if message[0] == "progress":
                    # Only the most recent reading is kept. Redrawing for
                    # every queued generation made the interface repaint
                    # hundreds of times a second and starve the search that
                    # was producing them -- the same run took 0.5s or 70s
                    # depending on how the two happened to interleave.
                    latest_progress = message
                    continue
                elif message[0] == "done":
                    _, outcome, error = message
                    self._pump_id = None
                    self._on_finished(outcome, error)
                    return
        except queue.Empty:
            if latest_progress is not None:
                _, generation, best = latest_progress
                total = max(1, self.ga_config.generations)
                try:
                    self.progress_bar.set(min(1.0, generation / total))
                    self.progress_text.configure(
                        text=trf("Generación {generation} de {total}   ·   "
                                 "mejor costo {best:.0f}",
                                 generation=generation, total=total,
                                 best=best)
                    )
                except tk.TclError:
                    # La barra ya no existe --- el usuario tocó «Atrás» y la
                    # pantalla de resultados se destruyó con ella. Eso no es
                    # motivo para dejar de bombear: acá se cortaba el
                    # `after` y la búsqueda seguía corriendo entera para que
                    # su resultado se quedara en la cola sin que nadie lo
                    # sacara nunca. Se pierde el dibujo del progreso, que es
                    # lo único que se puede perder; el resultado no.
                    pass
        except tk.TclError:
            return          # window closed mid-search
        try:
            self._pump_id = self.after(80, self._drain_queue)
        except tk.TclError:
            pass

    # -- screen 6: results --------------------------------------------------

    def _screen_results(self) -> None:
        self.results_container = ctk.CTkFrame(self.body, fg_color="transparent")
        self.results_container.pack(fill="both", expand=True)
        # Volver de un desvío ---el analizador, el libro, los logros--- rearma
        # esta pantalla con la búsqueda ya terminada. Sin esto quedaba
        # «Buscando soluciones» para siempre y el resultado no se veía más.
        # `_results_ready` se apaga al arrancar cada búsqueda, así que una
        # nueva no muestra la anterior.
        if self.outcome is not None and getattr(self, "_results_ready", False):
            self.results_container.pack_forget()
            pending = getattr(self, "_story_continue_row", None) is not None
            listened = getattr(self, "_story_listened", False)
            self._draw_outcome(self.outcome)
            # El candado del sendero vivía en el panel viejo: se vuelve a
            # poner, abierto si ya se había escuchado.
            if pending:
                self._story_offer_continue()
                if listened:
                    self._story_mark_listened()
            return

        accent = self._mode_accent()
        # Centrado y en una columna angosta. Arrimado arriba a la izquierda,
        # el estado de la búsqueda quedaba en letra chica en un rincón de una
        # pantalla vacía, que es lo último que uno quiere mirar mientras
        # espera. `pack(expand=True)` sobre un único hijo lo centra en los dos
        # ejes sin necesidad de rellenos.
        panel = ctk.CTkFrame(self.results_container, fg_color="transparent")
        panel.pack(expand=True)

        ctk.CTkLabel(panel, text=tr("Buscando soluciones"),
                     font=scaled(("Segoe UI Semibold", 26))).pack()
        ctk.CTkLabel(panel,
                     text=tr("Prueba miles de repartos de voces y se queda "
                             "con los mejores."),
                     font=scaled(("Segoe UI", 13)), text_color=TEXT_MUTED,
                     wraplength=520, justify="center").pack(pady=(8, 22))

        self.progress_bar = ctk.CTkProgressBar(panel, width=520,
                                               height=10, corner_radius=5,
                                               fg_color=SURFACE_LIGHT,
                                               progress_color=accent)
        self.progress_bar.set(0)
        self.progress_bar.pack()
        self.progress_text = ctk.CTkLabel(panel, text=tr("Preparando…"),
                                          font=scaled(("Segoe UI", 15)),
                                          text_color=TEXT_NORMAL)
        self.progress_text.pack(pady=(16, 0))
        # La barra late mientras se busca. Con poblaciones chicas el avance
        # da saltos largos y la barra se quedaba quieta un rato largo, que se
        # lee como si el programa se hubiera colgado.
        self._pulse_bar(self.progress_bar, accent)

    @staticmethod
    def _pulse_bar(bar, accent: str) -> None:
        """Latido suave en el color de una barra, hasta que deje de existir."""
        dim = mix(accent, SURFACE_LIGHT, 0.45)
        state = {"up": True}

        def cycle() -> None:
            def frame(position: float) -> None:
                near, far = (dim, accent) if state["up"] else (accent, dim)
                bar.configure(progress_color=mix(near, far, position))
                if position >= 1.0:
                    state["up"] = not state["up"]
                    try:
                        if bar.winfo_exists():
                            bar.after(40, cycle)
                    except tk.TclError:
                        return

            animate(bar, frame, steps=10, period=52, key="_pulse_id")

        cycle()

    def _on_finished(self, outcome, error) -> None:
        # El resultado puede llegar con el usuario parado en otra pantalla:
        # «Atrás» durante la búsqueda destruye el panel de resultados y la
        # corrida sigue igual. Se lo devuelve al resultado en vez de tirarlo,
        # que es exactamente lo que pidió cuando apretó generar.
        container = getattr(self, "results_container", None)
        if container is None or not container.winfo_exists():
            self.index = len(self.screens) - 1
            self._render()

        # Built with the container hidden and shown once complete. Tk draws
        # widgets as they are created, so a long piece appeared column by
        # column and the window looked like it had frozen mid-render.
        self.results_container.pack_forget()
        for child in self.results_container.winfo_children():
            child.destroy()

        if error is not None:
            ctk.CTkLabel(self.results_container,
                         text=trf("Se cortó la búsqueda: {error}", error=error),
                         font=FONT_BODY, text_color=ERROR,
                         wraplength=900, justify="left").pack(anchor="w")
            self._show_results()
            return

        self.outcome = outcome
        if not outcome.succeeded:
            self._draw_outcome(outcome)
            return

        try:
            session.apply_flourishes(
                outcome, self._search_genre(),
                parse_pitch_class(getattr(self, "_tonic", "C")),
                raise_odds=bool(self.settings.get("raise_cadence_odds", False)),
            )
        except Exception:                                   # noqa: BLE001
            pass          # a decoration must never cost the user their result
        self._remember_run(outcome)
        # Los tramos automáticos del relato no reparten logros. La pieza la
        # escribió el programa de un botón: dar por descubierta la séptima,
        # el jazz o las quintas paralelas por algo que el usuario no eligió
        # le sacaría de encima la mitad del juego sin que se entere. Queda
        # en el historial, que sí es un registro de lo que pasó.
        # Se guarda aparte porque la bandera se apaga acá y la pantalla se
        # dibuja después: es lo que hace que los acordes de la pieza salgan
        # con el dorado de los legendarios.
        self._story_piece_result = bool(getattr(self, "_story_auto", False))
        if self._story_piece_result:
            self._story_auto = False
        else:
            self._check_run_achievements(outcome)
            self._check_visitors()
            self._story_after_run(outcome)
            # La explosión, si el generador salió con todo arriba. Va en la
            # misma fila que las estrellas para no pisarse con ellas.
            if self._blast_armed:
                self._blast_armed = False
                self._egg("blast")
                self.celebrations.append(("blast", None))
                if self.overlay is None:
                    self.after(700, self._next_celebration)
        self._draw_outcome(outcome)

    def _draw_outcome(self, outcome) -> None:
        """
        Dibujar un resultado en el panel de resultados, que ya está vacío.

        Sólo el dibujo: lo que pasa una vez por búsqueda ---adornos,
        historial, logros, visitas, sendero--- queda en `_on_finished`. Por
        eso `_screen_results` puede volver a llamarla al volver de un desvío.
        """
        if not outcome.succeeded:
            ctk.CTkLabel(self.results_container, text=tr("No se encontró solución"),
                         font=scaled(("Segoe UI Semibold", 16)), text_color=ERROR
                         ).pack(anchor="w")
            for message in outcome.errors:
                ctk.CTkLabel(self.results_container, text=tr(message), font=FONT_SMALL,
                             text_color=TEXT_MUTED, wraplength=900, justify="left"
                             ).pack(anchor="w", pady=2)
            ctk.CTkLabel(self.results_container,
                         text=tr("Probá aflojar alguna regla en la pantalla "
                                 "anterior o ampliar los rangos de las "
                                 "voces."),
                         font=FONT_SMALL, text_color=WARN).pack(anchor="w", pady=(10, 0))
            self._show_results()
            return
        if getattr(outcome, "set_piece", None) is not None:
            banner = ctk.CTkFrame(self.results_container, fg_color=SET_PIECE_TINT,
                                  corner_radius=11)
            banner.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(banner,
                         text=trf("★  {label}",
                                  label=tr(outcome.set_piece.label)),
                         font=scaled(("Segoe UI Semibold", 14)),
                         text_color=SET_PIECE_TEXT).pack(anchor="w", padx=14,
                                                         pady=(10, 2))
            ctk.CTkLabel(banner, text=tr(outcome.set_piece.description),
                         font=FONT_SMALL, text_color=SET_PIECE_TEXT,
                         wraplength=880, justify="left"
                         ).pack(anchor="w", padx=14, pady=(0, 10))

        # «Las mejores soluciones», sin número: el tres estaba escrito a mano
        # y no siempre vuelven tres. Una progresión muy atada devuelve dos, y
        # las piezas del sendero devuelven una sola.
        ctk.CTkLabel(self.results_container, text=tr("Las mejores soluciones"),
                     font=scaled(("Georgia", 22, "bold"))).pack(anchor="w")
        # El costo sigue ordenándolas ---la primera es la más barata--- pero
        # ya no se muestra: es un número interno del algoritmo y a quien mira
        # la partitura no le dice nada. Lo que sí dice cuál es cuál es el
        # orden, y el punto del color en la que el programa eligió.
        ctk.CTkLabel(self.results_container,
                     text=tr("La primera es la que eligió el programa. Las "
                             "otras mueven peor las voces o ceden más en las "
                             "reglas del estilo."),
                     font=FONT_SMALL, text_color=TEXT_MUTED,
                     wraplength=900, justify="left"
                     ).pack(anchor="w", pady=(3, 0))
        for warning in outcome.warnings:
            ctk.CTkLabel(self.results_container, text=tr(warning), font=FONT_SMALL,
                         text_color=WARN, wraplength=900, justify="left"
                         ).pack(anchor="w", pady=2)

        # La partitura o la tabla de nombres de nota. La partitura es lo que
        # se lee; la tabla queda a un click, y es la única con más de cuatro
        # voces porque el sistema tiene cuatro carriles.
        notation = len(outcome.spec.voices) <= GRAND_VOICE_COUNT
        if notation:
            view_row = ctk.CTkFrame(self.results_container,
                                    fg_color="transparent")
            view_row.pack(fill="x", pady=(8, 0))
            toggle = ctk.CTkSegmentedButton(
                view_row, values=trs(["Partitura", "Tabla"]),
                font=FONT_SMALL, height=26,
                selected_color=self._mode_accent(),
                selected_hover_color=ACCENT_HOVER,
                command=lambda value: self._set_results_view(
                    i18n.untr(value)))
            toggle.set(tr("Tabla" if self._results_view == "table"
                          else "Partitura"))
            toggle.pack(side="right")
        table = ctk.CTkScrollableFrame(self.results_container,
                                       fg_color="transparent", height=330)
        table.pack(fill="both", expand=True, pady=(6, 8))
        self._results_table = table
        # Si este resultado va a pedir «Escuchá antes de seguir» --- ver
        # `_story_offer_continue` ---, ya se sabe acá: para la pieza
        # automática del sendero es `_story_piece_result`, sembrado más
        # arriba en `_on_finished`; para el tramo escrito a mano es que
        # `_story_after_run` ya haya abierto el candado, cosa que --- por
        # ese mismo orden --- corre antes que este bucle. Con eso alcanza
        # para saber, antes de dibujar ningún botón, cuáles hay que dorar.
        self._results_gated = bool(
            getattr(self, "_story_piece_result", False)
            or getattr(self, "_story_continue_row", None) is not None)
        self._draw_options()

        export_row = ctk.CTkFrame(self.results_container, fg_color="transparent")
        export_row.pack(fill="x", pady=(4, 0))
        self._show_results()
        self.format_menu = ctk.CTkOptionMenu(
            export_row, values=trs(["MusicXML y MIDI", "Sólo MusicXML",
                                    "Sólo MIDI"]),
            width=170, fg_color=SURFACE_LIGHT, button_color=SURFACE_LIGHT,
            button_hover_color=ACCENT_HOVER,
        )
        self.format_menu.pack(side="left")
        ctk.CTkButton(export_row, text=tr("Guardar como…"), width=150, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self._export_dialog
                      ).pack(side="left", padx=10)
        ctk.CTkButton(export_row, text=tr("Guardar en la carpeta del programa"),
                      width=250, fg_color="transparent", border_width=1,
                      border_color=TEXT_MUTED, hover_color=SURFACE_LIGHT,
                      command=lambda: self._export(None)).pack(side="left")

    def _screen_record(self, record) -> None:
        """Redraw a stored run the way the results screen shows it."""
        self._heading(record.display_name,
                      tr("Las mismas tres opciones, tal como quedaron guardadas."))

        notation = 0 < len(record.voice_names) <= GRAND_VOICE_COUNT
        if notation:
            toggle = ctk.CTkSegmentedButton(
                self.body, values=trs(["Partitura", "Tabla"]),
                font=FONT_SMALL, height=26,
                selected_color=self._record_accent(record),
                command=lambda value: self._set_results_view(
                    i18n.untr(value)))
            toggle.set(tr("Tabla" if self._results_view == "table"
                          else "Partitura"))
            toggle.pack(anchor="e", pady=(0, 4))
        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True, pady=(0, 6))

        accent = self._record_accent(record)
        for position, pitches in enumerate(record.solutions, start=1):
            # El mismo recuadro del color del modo que en la lista, para que
            # una pantalla se lea como continuación de la otra y no como un
            # lugar nuevo.
            block = ctk.CTkFrame(scroll, fg_color=SURFACE_LIGHT,
                                 corner_radius=11, border_width=2,
                                 border_color=accent)
            block.pack(fill="x", pady=5)
            # Sin el costo, igual que en la pantalla de resultados: esta vista
            # es la misma partitura, sólo que guardada.
            heading = ctk.CTkFrame(block, fg_color="transparent")
            heading.pack(fill="x", padx=14, pady=(10, 6))
            ctk.CTkLabel(heading, text="●", font=scaled(("Segoe UI", 12)),
                         text_color=accent if position == 1 else TEXT_MUTED
                         ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(heading, text=trf("Opción {position}",
                                           position=position),
                         font=scaled(("Segoe UI Semibold", 13))
                         ).pack(side="left")
            if record.durations:
                play = ctk.CTkButton(heading, text=tr("▶  Escuchar"), width=130,
                                     height=28, font=FONT_SMALL,
                                     fg_color=accent,
                                     hover_color=mix(accent, "#FFFFFF", 0.18))
                play.configure(command=lambda i=position - 1, b=play:
                               self._play_record(record, b, i))
                play.pack(side="right")
            if notation and self._results_view != "table":
                beats, _, unit = record.time_signature.partition("/")
                try:
                    metre = (1, int(beats), int(unit or 4))
                except ValueError:
                    metre = (1, 4, 4)
                durations = (list(record.durations)
                             or [2.0] * len(record.chord_labels))
                labels = [(label, record.romans[column]
                           if column < len(record.romans) else "",
                           label == history.REST_LABEL, None)
                          for column, label in enumerate(record.chord_labels)]
                self._result_staff(block, heading,
                                   self._lanes_for_names(record.voice_names),
                                   record.voice_names, pitches, durations,
                                   labels, 0, [metre])
                continue
            grid = ctk.CTkScrollableFrame(
                block, fg_color="transparent", orientation="horizontal",
                height=60 + 26 * len(record.voice_names))
            grid.pack(fill="x", padx=14, pady=(0, 10))

            for column, label in enumerate(record.chord_labels):
                resting = label == history.REST_LABEL
                head = ctk.CTkFrame(grid, fg_color="transparent")
                head.grid(row=0, column=column + 1, padx=2)
                ctk.CTkLabel(
                    head,
                    text=session.REST_SYMBOL if resting else label, width=64,
                    text_color=TEXT_MUTED if resting else None,
                    font=(scaled(("Segoe UI Symbol", 15)) if resting
                          else scaled(("Segoe UI Semibold", 11)))).pack()
                if (not resting and column < len(record.romans)
                        and record.romans[column]):
                    ctk.CTkLabel(head, text=tr(record.romans[column]), width=64,
                                 font=FONT_SMALL, text_color=TEXT_MUTED).pack()

            names = record.voice_names
            for voice_index in reversed(range(len(names))):
                row = len(names) - voice_index
                ctk.CTkLabel(grid, text=i18n.tr_name(names[voice_index]), font=FONT_SMALL,
                             text_color=TEXT_MUTED, width=110, anchor="w"
                             ).grid(row=row, column=0, sticky="w")
                for column, chord in enumerate(pitches):
                    ctk.CTkLabel(
                        grid,
                        text=(note_name(chord[voice_index])
                              if voice_index < len(chord) else "·"),
                        font=FONT_SMALL, width=64,
                        text_color=None if chord else TEXT_MUTED
                        ).grid(row=row, column=column + 1, padx=2)

    def _remember_run(self, outcome) -> None:
        """
        File every finished run, not only the ones saved to disk.

        Recording on export meant the history stayed empty for anyone who
        just wanted to hear the result, which is most of the time.
        """
        slots = outcome.spec.slots
        labels, romans = [], []
        best = outcome.result.solutions[0]
        # Una cita trae sus propios acordes y es la que el usuario ve como
        # opción 1. Los `slots` del generador no los llevan --- la pieza está
        # escrita aparte ---, así que leerlos de ahí anotaba en el historial
        # una progresión que no es la que se escuchó.
        quotation = getattr(outcome, "set_piece", None)
        quoted = list(getattr(quotation, "symbols", []) or []) if quotation else []
        quoted_romans = list(getattr(quotation, "romans", []) or []) if quotation else []
        for column, slot in enumerate(slots):
            label, roman = slot.symbol, ""
            if getattr(slot, "is_rest", False):
                labels.append(history.REST_LABEL)
                romans.append("")
                continue
            if column < len(quoted):
                label = quoted[column]
                roman = (quoted_romans[column]
                         if column < len(quoted_romans) else "")
            elif slot.options and column < len(best.choices):
                option = slot.options[min(best.choices[column],
                                          len(slot.options) - 1)]
                # Named as it is actually voiced: an added ninth shows
                # up as Cadd9 rather than as a plain C.
                label = voicing.symbol_with_added(option.requirement.plan)
                if option.harmony is not None:
                    roman = harmony.display_roman(option.harmony)
            labels.append(label)
            romans.append(roman)

        record = history.ProductionRecord.create(
            title=getattr(self.request, "title", "ChordWeaver"),
            genre=self.genre_key,
            mode=self.mode,
            voice_keys=list(self.voice_keys),
            bar_count=len({slot.bar_index for slot in slots}),
            time_signature=str(getattr(self.request, "time_signature", "4/4")),
            chord_symbols=labels,
            durations=[slot.duration_quarters for slot in slots],
            solution_costs=[s.cost for s in outcome.result.solutions],
            voice_names=[v.name for v in outcome.spec.voices],
            chord_labels=labels,
            romans=romans,
            solutions=[session.voiced_slots(outcome.spec, s)
                       for s in outcome.result.solutions],
            # Sin esto, una corrida con notas de adorno se volvía a escuchar
            # desde el historial sin ninguna: lo guardado eran los acordes
            # pelados y el adorno no está en ellos.
            ornaments=[[list(o) for o in session.ornaments_of(outcome.spec, s)]
                       for s in outcome.result.solutions],
        )
        history.add_record(record, self.history_path)

    # -- las opciones del resultado ----------------------------------------

    #: Cómo se muestran las opciones: "staff" (partitura) o "table".
    _results_view = "staff"

    def _set_results_view(self, view: str) -> None:
        """Cambiar entre la partitura y la tabla, sin volver a buscar."""
        self._results_view = "table" if view == "Tabla" else "staff"
        if self.detour and self.detour[-1][0] == "record":
            self._render()
            return
        self._draw_options()

    def _draw_options(self) -> None:
        """Dibujar las opciones del resultado en la vista elegida."""
        table = getattr(self, "_results_table", None)
        outcome = self.outcome
        if table is None or outcome is None:
            return
        try:
            for child in table.winfo_children():
                child.destroy()
        except tk.TclError:
            return
        voice_names = [v.name for v in outcome.spec.voices]
        story_gated = self._results_gated
        for position, solution in enumerate(outcome.result.solutions, start=1):
            self._draw_option(table, outcome, position, solution,
                              story_gated, voice_names)

    def _draw_option(self, table, outcome, position: int, solution,
                     story_gated: bool, voice_names: List[str]) -> None:
        """Una opción: su encabezado, sus marcas y su música."""
        quoted = (getattr(outcome, "set_piece", None) is not None
                  and position == 1)
        # Las piezas del relato salen con el dorado de los legendarios:
        # no las eligió el algoritmo ni las escribió el usuario, están
        # citadas, y son lo único que el sendero tiene para dar.
        legendary = bool(getattr(self, "_story_piece_result", False))
        block = ctk.CTkFrame(
            table, fg_color=SET_PIECE_TINT if quoted else SURFACE_LIGHT,
            corner_radius=12,
            border_width=2 if legendary else 0,
            border_color=GOLD if legendary else SURFACE_LIGHT)
        block.pack(fill="x", pady=5)
        heading = ctk.CTkFrame(block, fg_color="transparent")
        heading.pack(fill="x", padx=14, pady=(10, 6))
        # La primera opción es la que el algoritmo eligió; las otras dos
        # son alternativas. Marcarla con el color del modo evita tener
        # que comparar tres costos para saber cuál es cuál.
        ctk.CTkLabel(heading, text="●", font=scaled(("Segoe UI", 12)),
                     text_color=(SET_PIECE_TEXT if quoted
                                 else self._mode_accent() if position == 1
                                 else TEXT_MUTED)
                     ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(heading,
                     text=(trf("Opción {position}  ·  {label}",
                               position=position,
                               label=outcome.set_piece.label)
                           if quoted else trf("Opción {position}",
                                              position=position)),
                     font=scaled(("Segoe UI Semibold", 13))).pack(side="left")

        # Named devices for THIS option, right above its own grid.
        found = getattr(outcome, "flourishes", None)
        own = found.labels_for(position - 1) if found else []
        for mark in own:
            # Which chords each device covers. Two cadences of different
            # kinds in one option were listed as two nameless lines over
            # chords tinted the same colour, so the darker of the two
            # looked as though it applied to both.
            where = self._slot_span(mark.slots)
            ctk.CTkLabel(block,
                         text=trf("★  {label}{where} — {detail}",
                                  label=tr(mark.label),
                                  where=(" (%s)" % where) if where else "",
                                  detail=tr(mark.detail)),
                         font=FONT_SMALL, text_color=SET_PIECE_TEXT,
                         wraplength=860, justify="left"
                         ).pack(anchor="w", padx=14, pady=(0, 2))
        play = ctk.CTkButton(
            heading, text=tr("▶  Escuchar"), width=140, height=32,
            font=FONT_SMALL,
            fg_color=GOLD_DIM if story_gated else ACCENT,
            hover_color=GOLD if story_gated else ACCENT_HOVER,
            text_color="#1B1D22" if story_gated else None,
            border_width=2 if story_gated else 0,
            border_color=GOLD if story_gated else SURFACE_LIGHT)
        play.configure(command=lambda sol=solution, btn=play,
                       gated=story_gated: self._play_and_mark(
                           sol, btn, gated))
        if story_gated:
            start_shimmer(play, period=110, option="border_color")
        play.pack(side="right")
        Tooltip(play, tr("Reproduce los acordes en orden con un sonido "
                         "simple, respetando sus duraciones. Las notas de "
                         "adorno no se incluyen."))
        # Con menos de tres voces el analizador no tiene acordes que leer.
        if len(voice_names) >= analyzer.MIN_VOICES:
            study = ctk.CTkButton(
                heading, text=tr("Analizar"), width=110, height=32,
                font=FONT_SMALL, fg_color="transparent", border_width=1,
                border_color=TEXT_MUTED, hover_color=SURFACE,
                text_color=TEXT_NORMAL,
                command=lambda: self._analyse_option(outcome, position))
            study.pack(side="right", padx=(0, 8))
            Tooltip(study, tr("Abre esta opción en el analizador, juzgada "
                              "con las reglas del estilo con que se "
                              "generó."))
        # Each option carries its own chords. Reading them off the slot
        # showed the same progression above all three, because the slot
        # only remembers whichever chord the best solution chose.
        # In harmonise mode each option was built from its own
        # progression, so the chord row has to come from that option's
        # slots rather than from the first one's.
        option_slots = getattr(outcome, "alternate_slots", {}).get(
            position - 1, outcome.spec.slots)
        columns = self._option_columns(outcome, position, solution,
                                       option_slots, legendary)
        if (self._results_view != "table"
                and len(voice_names) <= GRAND_VOICE_COUNT):
            self._option_staff(block, heading, outcome, solution, columns,
                               voice_names)
        else:
            self._option_table(block, outcome, solution, option_slots,
                               columns, voice_names, legendary)

    def _option_columns(self, outcome, position: int, solution,
                        option_slots, legendary: bool) -> List[dict]:
        """
        Qué dice y de qué color va cada columna de una opción.

        Lo usan la tabla y la partitura, para que las dos digan lo mismo:
        el cifrado tal como está repartido, el grado, y si es una marca, una
        visita a otra tonalidad o un intercambio modal.
        """
        flourishes = getattr(outcome, "flourishes", None)
        quotation = getattr(outcome, "set_piece", None)
        columns: List[dict] = []
        for column, slot in enumerate(option_slots):
            # Start from how THIS slot is voiced. The hand-written mode
            # has no options list, so reading the name only inside the
            # options branch left it showing the bare chord symbol and
            # hiding every added colour tone.
            label = voicing.symbol_with_added(slot.requirement.plan)
            # Un silencio no tiene acorde. El motor le pone un do de
            # relleno para que la lista de slots siga alineada con los
            # compases, y ese do se estaba mostrando como si el usuario
            # lo hubiera escrito.
            resting = bool(getattr(slot, "is_rest", False))
            # The quotation's symbols belong to ITS solution only; the
            # other two are ordinary answers and keep their own chords.
            quoted_here = bool(position == 1 and quotation
                               and column < len(getattr(quotation, "symbols", [])))
            if quoted_here:
                label = quotation.symbols[column]
            # The rewritten sixth has to survive the same way: wherever the
            # slot carries a list of options -- the generator and the
            # harmoniser -- the chord was renamed from its plan and the
            # "6omit5" was lost.
            sixth_here = bool(position == 1 and flourishes
                              and flourishes.sixth_slot == column
                              and flourishes.sixth_symbol)
            if sixth_here:
                label = flourishes.sixth_symbol
            roman = ""
            chosen_option = None
            if slot.options and column < len(solution.choices):
                chosen_option = slot.options[
                    min(solution.choices[column], len(slot.options) - 1)]
                # Named as it is actually voiced: an added ninth shows
                # up as Cadd9 rather than as a plain C.
                if not (quoted_here or sixth_here):
                    label = voicing.symbol_with_added(
                        chosen_option.requirement.plan)
                # A quotation names its own degrees. Reading them off
                # the slot showed "i" over the dominant in a cadence
                # whose chord symbol repeats.
                if quoted_here and column < len(quotation.romans):
                    roman = quotation.romans[column]
                elif chosen_option.harmony is not None:
                    roman = harmony.display_roman(chosen_option.harmony)
            marks = (flourishes.marks_for(column, position - 1)
                     if flourishes else [])
            # A chord visited in another key is tinted, so where the
            # piece travels is visible at a glance.
            away = bool(chosen_option is not None
                        and getattr(chosen_option.harmony, "key_area", ""))
            # Un intercambio modal se marca en naranja. Las dominantes
            # aplicadas no cuentan: viajan en el mismo campo pero no son un
            # préstamo del modo paralelo.
            lent = bool(chosen_option is not None
                        and chosen_option.harmony is not None
                        and chosen_option.harmony.is_borrowed
                        and not harmony.is_applied_dominant(
                            chosen_option.harmony))
            columns.append({
                "label": label, "roman": roman, "resting": resting,
                "marked": bool(marks), "marks": marks, "away": away,
                "lent": lent, "duration": slot.duration_quarters,
            })
        return columns

    @staticmethod
    def _column_colour(column: dict, legendary: bool) -> Optional[str]:
        """El color de un cifrado: marca, viaje o préstamo; None si ninguno."""
        if column["resting"]:
            return TEXT_MUTED
        if column["marked"] or legendary:
            return SET_PIECE_TEXT
        if column["away"]:
            return MODULATION_TEXT
        if column["lent"]:
            return BORROWED_TEXT
        return None

    def _option_table(self, block, outcome, solution, option_slots,
                      columns: List[dict], voice_names: List[str],
                      legendary: bool) -> None:
        """La opción como tabla: un cifrado por columna y una voz por fila."""
        # Horizontal scrolling: a long piece ran off the edge with no
        # way to reach the later bars. Height follows the number of
        # voices: fixed at 190 the last row fell outside the visible area,
        # so a six-voice setting looked like it had lost its bass.
        grid = ctk.CTkScrollableFrame(
            block, fg_color="transparent", orientation="horizontal",
            height=60 + 26 * len(voice_names))
        grid.pack(fill="x", padx=14, pady=(0, 10))

        # Adónde viaja ESTA opción, escrito arriba del tramo violeta y
        # centrado sobre él. El nombre es lo único que contesta la pregunta
        # con la que uno mira ese tramo.
        if self._modulation_banner(grid, option_slots, solution):
            # La fila del cartel ocupa lugar: sin agrandar la rejilla, la
            # voz más grave se caía fuera de la parte visible.
            grid.configure(height=60 + 26 * len(voice_names) + 24)

        for column, info in enumerate(columns):
            resting = info["resting"]
            marked, away, lent = info["marked"], info["away"], info["lent"]
            header = ctk.CTkFrame(
                grid,
                fg_color=(SET_PIECE_TINT if marked or legendary
                          else MODULATION_TINT if away
                          else BORROWED_TINT if lent else "transparent"),
                corner_radius=6)
            if lent and not away:
                Tooltip(header,
                        tr("Intercambio modal: un acorde prestado del modo "
                           "paralelo. Sigue en la misma tonalidad, con una "
                           "nota de la escala cambiada."))
            if marked:
                # El nombre y la explicación se traducen por separado: el
                # renglón armado con los dos nunca sería una clave.
                Tooltip(header, "  ".join(
                    f"{tr(m.label)}: {tr(m.detail)}" for m in info["marks"]))
            header.grid(row=1, column=column + 1, padx=2, sticky="ew")
            chord_label = ctk.CTkLabel(
                header,
                text=session.REST_SYMBOL if resting else info["label"],
                # El glifo del silencio vive en la fuente de símbolos, la
                # misma con la que el pentagrama dibuja sus claves.
                font=(scaled(("Segoe UI Symbol", 15)) if resting
                      else scaled(("Segoe UI Semibold", 11))),
                width=64,
                text_color=self._column_colour(info, legendary))
            chord_label.pack()
            if resting:
                Tooltip(header, tr("Silencio: acá no suena nada."))
            if legendary:
                # Desfasados por posición: el brillo recorre la progresión
                # de izquierda a derecha en vez de prenderse entero.
                start_shimmer(chord_label, period=110, offset=column)
            if info["roman"] and not resting:
                ctk.CTkLabel(header, text=info["roman"], font=FONT_SMALL,
                             text_color=(MODULATION_TEXT if away
                                         else BORROWED_TEXT if lent
                                         else TEXT_MUTED), width=64).pack()
        chords = session.voiced_slots(outcome.spec, solution)
        for voice_index in reversed(range(len(voice_names))):
            # Una fila más abajo: la primera la ocupa el cartel de la
            # modulación, que existe aunque esta opción no viaje.
            display_row = len(voice_names) - voice_index + 1
            ctk.CTkLabel(grid, text=i18n.tr_name(voice_names[voice_index]),
                         font=FONT_SMALL, text_color=TEXT_MUTED, width=110,
                         anchor="w").grid(row=display_row, column=0,
                                          sticky="w")
            # Alineadas contra los slots de la partitura y no contra las de
            # la solución: la búsqueda saltea los silencios, así que a
            # partir del primero las dos listas iban corridas.
            for column, chord in enumerate(chords):
                ctk.CTkLabel(
                    grid,
                    text=(note_name(chord[voice_index])
                          if voice_index < len(chord) else "·"),
                    font=FONT_SMALL, width=64,
                    text_color=None if chord else TEXT_MUTED
                    ).grid(row=display_row, column=column + 1, padx=2)

    #: El carril de cada tipo de voz en el sistema de dos pentagramas: el
    #: bajo abajo de todo, el tenor en el segundo ---que se reparte entre
    #: las dos claves nota por nota---, la contralto y la soprano arriba.
    STAFF_LANES = {"B": 0, "Bar": 0, "T": 1, "A": 2, "MS": 2, "S": 3}

    def _staff_lanes(self, voices) -> List[int]:
        """En qué carril del sistema va cada voz, de grave a aguda."""
        wanted = [self.STAFF_LANES.get(
            getattr(getattr(voice, "voice_type", None), "key", ""), -1)
            for voice in voices]
        if -1 not in wanted and wanted == sorted(set(wanted)):
            return wanted
        return {1: [3], 2: [0, 3], 3: [0, 2, 3],
                4: [0, 1, 2, 3]}.get(len(voices), list(range(len(voices))))

    def _option_staff(self, block, heading, outcome, solution,
                      columns: List[dict], voice_names: List[str]) -> None:
        """
        La opción como partitura: el sistema de dos pentagramas del
        analizador, sólo para leer, con los cifrados arriba y el grado
        abajo, pintados como en la tabla.

        La tabla de nombres de nota decía lo mismo, pero se leía como una
        planilla y no como música.
        """
        spec = outcome.spec
        lanes = self._staff_lanes(spec.voices)
        chords = session.voiced_slots(spec, solution)
        durations = [slot.duration_quarters for slot in spec.slots]
        # La melodía del Armonizador, como la escribió el usuario: la
        # búsqueda la ve muestreada nota por acorde, y sin esto la partitura
        # mostraba una melodía con la mitad de las notas.
        written: Dict[int, List[Tuple[Optional[int], float]]] = {}
        for voice in range(len(lanes)):
            line = spec.line_for(voice) if hasattr(spec, "line_for") else None
            if line is not None:
                written[voice] = [event for bar in sorted(line.bars)
                                  for event in line.bars[bar]]
        legendary = bool(getattr(self, "_story_piece_result", False))
        labels = [(info["label"], info["roman"], info["resting"],
                   self._column_colour(info, legendary)) for info in columns]
        self._result_staff(block, heading, lanes, voice_names, chords,
                           durations, labels, getattr(spec, "key_hint", None)
                           or 0, self._spec_metres(spec), written)

    @staticmethod
    def _spec_metres(spec) -> List[Tuple[int, int, int]]:
        """Los cambios de compás de una partitura: (compás, tiempos, figura)."""
        signature = spec.time_signature
        metres = [(1, signature.beats, signature.beat_type)]
        last = (signature.beats, signature.beat_type)
        for bar, metre in enumerate(
                getattr(spec, "bar_time_signatures", None) or [], start=1):
            if (metre.beats, metre.beat_type) != last:
                metres.append((bar, metre.beats, metre.beat_type))
                last = (metre.beats, metre.beat_type)
        return metres

    def _analyse_option(self, outcome, position: int) -> None:
        """
        Abrir una opción del resultado en el analizador, ya escrita.

        Va sin archivo: `session.analysis_lines` da lo mismo que exportarla
        e importarla, y el contrapunto se juzga con el estilo con que se
        buscó (el coral, si se pidió el contrapunto estricto). Con más de
        cuatro voces se reduce como al importar, momento a momento.
        """
        from engine.analysis import Note, Part
        lines = session.analysis_lines(outcome, position - 1)
        voices = outcome.spec.voices
        if len(lines) > GRAND_VOICE_COUNT:
            parts = []
            for voice, line in enumerate(lines):
                notes, moment = [], 0.0
                for pitch, quarters in line:
                    if pitch is not None:
                        notes.append(Note(pitch=pitch, onset=moment,
                                          duration=quarters))
                    moment += quarters
                parts.append(Part(name=voices[voice].name, notes=notes))
            kept = importer.kept_voices(parts, GRAND_VOICE_COUNT)
            lines = [importer.written_line(part) for part in kept]
            lanes = list(range(len(lines)))
        else:
            lanes = self._staff_lanes(voices)
        placed: List[list] = [[] for _ in range(GRAND_VOICE_COUNT)]
        for voice, lane in enumerate(lanes):
            placed[lane] = lines[voice]
        fifths = getattr(outcome.spec, "key_hint", None) or 0
        if all(fifths != f for _name, f in self.KEY_SIGNATURES):
            fifths = 0
        piece = SimpleNamespace(
            lines=placed, fifths=fifths,
            metres=self._spec_metres(outcome.spec),
            genre=getattr(self.request, "genre_key", None),
            position=position)
        self._open_detour("analysis", piece)

    def _result_staff(self, block, heading, lanes: List[int],
                      voice_names: List[str], chords, durations: List[float],
                      labels: List[tuple], fifths: int,
                      metres: List[Tuple[int, int, int]],
                      written: Optional[Dict[int, list]] = None) -> None:
        """
        Dibujar un resultado en el sistema de dos pentagramas, sólo para leer.

        Lo comparten la pantalla de resultados y el detalle del historial.
        ``labels`` va una por columna: (cifrado, grado, silencio, color).
        """
        accent = self._mode_accent()
        grand = GrandStaff(
            block, editable=False,
            colours={"surface": SURFACE_LIGHT, "text": TEXT_NORMAL,
                     "muted": TEXT_MUTED, "accent": accent,
                     "glow": mix(SURFACE_LIGHT, accent, 0.18)})
        grand.set_key(fifths, metres[0][1], metres[0][2])
        grand.set_metres(metres)
        lines: List[List[Tuple[Optional[int], float]]] = [
            [] for _ in range(GRAND_VOICE_COUNT)]
        onsets: List[float] = []
        moment = 0.0
        for column, duration in enumerate(durations):
            chord = chords[column] if column < len(chords) else []
            onsets.append(moment)
            for voice, lane in enumerate(lanes):
                lines[lane].append(
                    (chord[voice] if voice < len(chord) else None, duration))
            moment += duration
        for voice, events in (written or {}).items():
            if (voice < len(lanes)
                    and abs(sum(d for _p, d in events) - moment) < 1e-6):
                lines[lanes[voice]] = list(events)
        grand.load(lines)
        grand.annotations = []
        grand.symbol_colours = {}
        # Sin las líneas punteadas de `flags`: en jazz casi todo acorde cae
        # en algún ii-V, y la partitura quedaba rayada de punta a punta. El
        # cifrado en dorado ya dice lo mismo.
        for column, (label, roman, resting, colour) in enumerate(labels):
            if column >= len(onsets) or resting:
                continue
            onset = onsets[column]
            grand.annotations.append(
                (onset, label, [tr(roman)] if roman else []))
            if colour:
                grand.symbol_colours[onset] = colour
        grand.redraw()
        grand.pack(fill="x", padx=14, pady=(0, 10))

        # Qué nota es, al pasar el mouse: la tabla lo decía de entrada, y la
        # partitura lo contesta a pedido sin ocupar lugar.
        reading = ctk.CTkLabel(heading, text="", font=FONT_SMALL,
                               text_color=TEXT_MUTED)
        reading.pack(side="left", padx=(16, 0))

        def hovered(hit) -> None:
            text = ""
            if hit is not None:
                lane, position = hit
                try:
                    pitch = lines[lane][position][0]
                    voice = lanes.index(lane)
                except (IndexError, ValueError):
                    pitch = None
                if pitch is not None and voice < len(voice_names):
                    text = "%s  ·  %s" % (i18n.tr_name(voice_names[voice]),
                                          note_name(pitch))
            try:
                reading.configure(text=text)
            except tk.TclError:
                pass

        grand.on_hover = hovered

    def _lanes_for_names(self, names: List[str]) -> List[int]:
        """Los carriles de unas voces guardadas por nombre (el historial)."""
        by_label = {voice.label: key for key, voice in VOICE_CATALOG.items()}
        by_label.update({"Bass": "B", "Baritone": "Bar", "Mezzo-soprano": "MS"})
        voices = []
        for name in names:
            base, _, number = name.rpartition(" ")
            if not (base and number.isdigit()):
                base = name
            voices.append(SimpleNamespace(
                voice_type=SimpleNamespace(key=by_label.get(base, ""))))
        return self._staff_lanes(voices)

    def _show_results(self) -> None:
        """Reveal the finished results panel in one go."""
        self.results_container.update_idletasks()
        self.results_container.pack(fill="both", expand=True)
        # El único punto por el que pasan las tres salidas de `_on_finished`
        # --- error, sin solución, éxito ---, así que es el lugar correcto
        # para decidir si «Nuevo» ya sirve para algo.
        self._results_ready = True
        self._refresh_continue_button()

    def _play_and_mark(self, solution, button, story_gated: bool) -> None:
        """
        Tocar «▶ Escuchar», y si hace falta, avisarle al sendero.

        El botón de reproducir es el mismo con o sin sendero de por medio;
        lo único que cambia es este paso previo. Separado de `_play_solution`
        para que ese siga siendo el reproductor de siempre y no tenga que
        saber que existe un botón dorado esperando más arriba.
        """
        if story_gated:
            self._story_mark_listened()
        self._play_solution(solution, button)

    def _play_solution(self, solution, button) -> None:
        """
        Play a solution's chords in order.

        Las notas de adorno suenan donde están escritas: el acorde adornado
        se parte en dos y la voz que adorna se mueve sobre el final mientras
        las demás sostienen. Las duraciones no cambian --- el adorno se
        lleva la cola del acorde que deja ---, así que la pieza dura lo
        mismo con adornos que sin ellos.
        """
        if getattr(self, "_playing", None) is not None and self._playing.is_alive():
            return          # one at a time

        durations = [slot.duration_quarters for slot in self.outcome.spec.slots]
        # Con los silencios en su lugar --- un acorde sin notas ocupa su
        # tiempo y no suena. Leyendo `solution.slots` a secas, la duración
        # del silencio le tocaba al acorde siguiente y la pieza sonaba un
        # compás más corta, sin ningún silencio adentro.
        chords = session.voiced_slots(self.outcome.spec, solution)

        # When harmonising, the tune has to be heard: chords sit on strong
        # beats only, so playing the solution alone drops every note between
        # them. The melody is laid over the top with its own rhythm, and the
        # voice carrying it is removed from the chords so it is not doubled.
        melody_line = []
        melody_voice = None
        given = getattr(self.outcome, "melody", None)
        if given is not None:
            melody_voice = getattr(given, "melody_voice", 0)
            per_bar = {}
            for index, bar in enumerate(given.bars):
                per_bar[index] = bar.quarters
            for note in given.notes:
                start = sum(per_bar.get(i, 4.0) for i in range(note.bar_index))
                melody_line.append((note.pitch,
                                    start + note.offset_quarters,
                                    note.duration_quarters))
        chords, durations, ornamented = session.playback_events(
            chords, durations,
            session.ornaments_of(self.outcome.spec, solution),
            drop_voice=melody_voice)
        button.configure(text=tr("♪  Sonando…"), state="disabled")

        def restore() -> None:
            try:
                button.configure(text=tr("▶  Escuchar"), state="normal")
            except tk.TclError:
                pass

        self._playing = audio.play_chords(
            chords, durations, melody=melody_line, voices=ornamented,
            quarter_seconds=getattr(self, "_story_speed", None))
        self._when_done(self._playing, restore)
        self._award({"first_playback"})

    def _export_dialog(self) -> None:
        folder = filedialog.askdirectory(
            title=tr("Elegí dónde guardar la partitura"),
            initialdir=history.default_output_directory(),
        )
        if folder:
            self._export(folder)

    def _export(self, folder: Optional[str]) -> None:
        if not self.outcome or not self.outcome.succeeded:
            return
        choice = i18n.untr(self.format_menu.get())
        formats = {
            "MusicXML y MIDI": ("musicxml", "midi"),
            "Sólo MusicXML": ("musicxml",),
            "Sólo MIDI": ("midi",),
        }[choice]
        # `record_history=False`: la corrida ya quedó anotada cuando terminó
        # la búsqueda (`_remember_run`), que es lo que se quiso desde que se
        # dejó de anotar sólo lo exportado. Este parámetro quedó prendido de
        # la época anterior y anotaba la misma corrida por segunda vez, así
        # que el historial mostraba todo duplicado y las «diez más recientes»
        # eran cinco. El CLI sí lo deja en True: ahí exportar es la corrida.
        written = session.export_outcome(self.request, self.outcome, folder,
                                         formats, record_history=False)
        if written:
            self._award({"first_export"})
            messagebox.showinfo(
                tr("Listo"),
                trf("Se guardaron {written} archivos en:\n{dirname}",
                    written=len(written),
                    dirname=os.path.dirname(written[0])),
            )
        else:
            messagebox.showerror(tr("Error"), tr("No se pudo escribir ningún archivo."))

    # -- history ------------------------------------------------------------

    def _record_accent(self, record) -> str:
        """
        El color del modo con el que se hizo una corrida guardada.

        Las entradas viejas no traen el modo --- el campo se agregó después
        --- así que ésas quedan con el borde neutro de las tarjetas: inventar
        un color sería peor que no tener ninguno.
        """
        for key, _n, _s, accent, _icon in MODE_CARDS:
            if key == record.mode:
                return accent
        return BORDER_SOFT

    @staticmethod
    def _record_icon(record) -> str:
        """El mismo signo que lleva la tarjeta de ese modo en la portada."""
        for key, _n, _s, _accent, icon in MODE_CARDS:
            if key == record.mode:
                return icon
        return "·"

    def _screen_history(self, _payload=None) -> None:
        self._award({"history_open"})
        records = history.load_history(self.history_path)
        self._heading(
            tr("Historial"),
            tr("Las diez últimas corridas, exportadas o no. El color de cada "
               "recuadro es el del modo que se usó."))
        if not records:
            empty = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT,
                                 corner_radius=12)
            empty.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(empty, text=tr("Todavía no hay nada guardado"),
                         font=scaled(("Segoe UI Semibold", 14))
                         ).pack(anchor="w", padx=18, pady=(16, 2))
            ctk.CTkLabel(empty,
                         text=tr("Cuando generes una partitura, va a aparecer "
                                 "acá."),
                         font=FONT_SMALL, text_color=TEXT_MUTED
                         ).pack(anchor="w", padx=18, pady=(0, 16))
            return

        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True, pady=(10, 6))
        for record in records:
            accent = self._record_accent(record)
            # El recuadro del color del modo. Es lo único que hace falta para
            # saber de un vistazo cuál corrida es cuál sin leer una línea: es
            # el mismo color que tenía el riel de progreso mientras se hacía.
            block = ctk.CTkFrame(scroll, fg_color=SURFACE_LIGHT,
                                 corner_radius=11, border_width=2,
                                 border_color=accent)
            block.pack(fill="x", pady=5)

            head = ctk.CTkFrame(block, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(head, text=tr(self._record_icon(record)),
                         font=scaled(("Segoe UI", 15)), text_color=accent
                         ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(head, text=tr(record.mode_label or "Producción"),
                         font=scaled(("Segoe UI Semibold", 13)),
                         text_color=accent).pack(side="left")
            ctk.CTkLabel(head, text=trf("·  {genre}",
                                        genre=tr(record.genre_label)),
                         font=scaled(("Segoe UI", 12)),
                         text_color=TEXT_NORMAL).pack(side="left", padx=(8, 0))
            # La fecha va a la derecha: es lo que se busca para ubicar una
            # corrida, no lo que se lee para saber qué es.
            ctk.CTkLabel(head, text=record.when, font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(side="right")

            if record.chord_symbols:
                ctk.CTkLabel(block, text="   ".join(record.chord_symbols),
                             font=scaled(("Segoe UI Semibold", 12)),
                             text_color=TEXT_NORMAL, wraplength=820,
                             justify="left"
                             ).pack(anchor="w", padx=14, pady=(4, 2))

            # Sin los costos, por lo mismo que se sacaron de la pantalla de
            # resultados: un número que sólo significa algo comparado con
            # otro de la misma corrida no dice nada suelto en una lista.
            voices = ", ".join(i18n.tr_name(name) for name in
                               (record.voice_names or record.voice_keys))
            details = (trf("{voice_keys} voces  ·  {voices}  ·  "
                           "{time_signature}  ·  {bar_count} compases",
                           voice_keys=len(record.voice_keys), voices=voices,
                           time_signature=record.time_signature,
                           bar_count=record.bar_count))
            ctk.CTkLabel(block, text=tr(details), font=FONT_SMALL,
                         text_color=TEXT_MUTED, wraplength=820,
                         justify="left").pack(anchor="w", padx=14)

            buttons = ctk.CTkFrame(block, fg_color="transparent")
            buttons.pack(anchor="w", padx=14, pady=(6, 10))
            if record.solutions and record.durations:
                # El historial guarda las alturas y las duraciones, que es
                # todo lo que hace falta para volver a oírlo. Una lista de
                # cosas que uno hizo y no puede escuchar es un inventario,
                # no un historial.
                play = ctk.CTkButton(buttons, text=tr("▶  Escuchar"), width=130,
                                     height=28, font=FONT_SMALL,
                                     fg_color=accent,
                                     hover_color=mix(accent, "#FFFFFF", 0.18))
                play.configure(command=lambda r=record, b=play:
                               self._play_record(r, b))
                play.pack(side="left")
                Tooltip(play, tr("Toca la primera opción tal como quedó "
                                 "guardada."))
            if record.solutions:
                detail = ctk.CTkButton(
                    buttons, text=tr("Ver detalle"), width=110, height=28,
                    font=FONT_SMALL, fg_color="transparent", border_width=1,
                    border_color=TEXT_MUTED, hover_color=SURFACE,
                    command=lambda r=record: self._open_detour("record", r))
                detail.pack(side="left", padx=(8, 0))

    def _play_record(self, record, button, option: int = 0) -> None:
        """Volver a escuchar una corrida guardada."""
        if getattr(self, "_playing", None) is not None and self._playing.is_alive():
            return          # uno por vez, igual que en los resultados
        if option >= len(record.solutions):
            return
        chords = [list(chord) for chord in record.solutions[option]]
        durations = list(record.durations) or [2.0] * len(chords)
        # Con sus adornos donde estaban. Las entradas escritas antes de que
        # el campo existiera no traen ninguno y suenan como siempre.
        stored = getattr(record, "ornaments", None) or []
        chords, durations, ornamented = session.playback_events(
            chords, durations,
            stored[option] if option < len(stored) else ())
        button.configure(text=tr("♪  Sonando…"), state="disabled")

        def restore() -> None:
            try:
                button.configure(text=tr("▶  Escuchar"), state="normal")
            except tk.TclError:
                pass

        try:
            self._playing = audio.play_chords(chords, durations,
                                              voices=ornamented)
        except Exception:                                   # noqa: BLE001
            restore()
            return
        self._when_done(self._playing, restore)

    # -- el libro de teoría ---------------------------------------------------

    def _fresh_notes(self) -> List[str]:
        """
        Lo que el usuario ganó y todavía no fue a leer.

        Las llaves del libro son claves de logro: el programa ya las detecta,
        ya las guarda y ya las muestra en su pantalla, así que el libro se
        llena solo sin ningún registro nuevo que mantener sincronizado. Lo
        único que hace falta guardar aparte es qué anotaciones ya se leyeron,
        para poder marcar las nuevas.
        """
        seen = set(self.settings.get("book_seen", []))
        return [key for key in book.LOCK_KEYS
                if self._lore_unlocked(key) and key not in seen]

    def _mark_notes_seen(self, keys) -> None:
        """Dar por leídas unas anotaciones. Sólo al mostrarlas de verdad."""
        keys = list(keys)
        if not keys:
            return
        seen = set(self.settings.get("book_seen", []))
        seen.update(keys)
        self.settings["book_seen"] = sorted(seen)
        history.save_settings(self.settings, self.settings_path)
        # Acá y no en el próximo render: pasar de un capítulo a otro no
        # redibuja la pantalla.
        self._refresh_note_flag()

    #: Ancho de la caja de texto del libro. Una columna de lectura, no el
    #: ancho de la ventana: pasadas las setenta y pico de letras por renglón
    #: el ojo pierde el salto de línea y hay que releer.
    BOOK_COLUMN = 620

    def _screen_book(self, payload=None) -> None:
        self._award({"book_read"})
        written, total = book.counts(self._lore_unlocked)

        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text=tr("Libro de teoría"),
                     font=scaled(("Georgia", 22))).pack(side="left")
        ctk.CTkLabel(header, text=trf("{written} de {total} apartados "
                                      "escritos",
                                      written=written, total=total),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(side="left", padx=14)
        pending = len(self._fresh_notes())
        if pending:
            ctk.CTkLabel(header,
                         text=(tr("🖋  1 anotación nueva" if pending == 1
                                  else trf("🖋  {pending} anotaciones nuevas",
                                           pending=pending))),
                         font=scaled(("Segoe UI Semibold", 12)),
                         text_color=GOLD).pack(side="right")

        columns = ctk.CTkFrame(self.body, fg_color="transparent")
        columns.pack(fill="both", expand=True, pady=(0, 4))
        columns.grid_columnconfigure(0, weight=0, minsize=260)
        columns.grid_columnconfigure(1, weight=1)
        columns.grid_rowconfigure(0, weight=1)

        toc = ctk.CTkFrame(columns, fg_color=SURFACE_LIGHT, corner_radius=12)
        toc.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(toc, text=tr("Índice"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=16,
                                                 pady=(14, 6))
        # Abierto en una entrada dada ---lo hace la escuelita, que cita una
        # por lección---: se elige el capítulo de esa entrada y, ya dibujado,
        # se baja hasta ella. Sin esto «Abrir en el libro» dejaba al lector
        # en el capítulo que hubiera tenido abierto la vez anterior.
        found = book.find(payload) if isinstance(payload, str) else None
        if found is not None:
            self._book_chapter = found[0]
        chosen = min(getattr(self, "_book_chapter", 0),
                     len(book.CHAPTERS) - 1)
        self._book_chapter = chosen
        # En qué capítulos cayó lo que todavía no se leyó. Van en azul hasta
        # que el usuario abra el capítulo y el texto se pinte: la cuenta del
        # encabezado dice que hay algo nuevo, pero no **dónde**.
        lit = book.chapters_for_locks(self._fresh_notes())
        self._book_lit = set(lit)
        self.book_buttons: List[ctk.CTkButton] = []
        for index, chapter in enumerate(book.CHAPTERS):
            done = sum(1 for entry in chapter.entries
                       if not entry.locked_by
                       or self._lore_unlocked(entry.locked_by))
            label = f"{chapter.numeral}.  {tr(chapter.title)}"
            if done < len(chapter.entries):
                label += f"   ({done}/{len(chapter.entries)})"
            # Los capítulos que no se llenan estudiando van en dorado, como
            # un legendario: en una lista de títulos todos iguales no había
            # forma de notar que apareció uno nuevo. Quién lo es lo contesta
            # el libro, que es donde está escrito qué se estudia y qué se
            # descubre.
            legendary = book.is_special(chapter)
            fresh = index in lit
            button = ctk.CTkButton(
                toc, text=label, anchor="w", height=42, corner_radius=9,
                font=scaled(("Georgia", 12, "bold") if legendary
                            else ("Georgia", 12)),
                fg_color="transparent", hover_color=SURFACE,
                text_color=NOTE_BLUE if fresh
                else (GOLD if legendary else TEXT_NORMAL),
                command=lambda i=index: self._show_chapter(i))
            button.pack(fill="x", padx=10, pady=2)
            # **El brillo no se le prende a un capítulo en azul**: reescribe
            # el color en bucle y no se puede parar, así que le comería el
            # azul. Se lo prende `_paint_book_index` cuando el azul se apaga.
            if legendary and not fresh:
                start_shimmer(button)
            self.book_buttons.append(button)

        self.book_page = ctk.CTkScrollableFrame(
            columns, fg_color=PAPER, corner_radius=14)
        self.book_page.grid(row=0, column=1, sticky="nsew")
        self._show_chapter(chosen)
        if found is not None:
            self.after(80, lambda key=payload: self._scroll_book_to(key))

    def _scroll_book_to(self, key: str) -> None:
        """Bajar la página del libro hasta el título de una entrada."""
        heading = getattr(self, "_book_headings", {}).get(key)
        page = getattr(self, "book_page", None)
        if heading is None or page is None:
            return
        try:
            self.update_idletasks()
            offset = heading.winfo_rooty() - page.winfo_rooty()
            total = max(1, page.winfo_height())
            page._parent_canvas.yview_moveto(max(0.0, (offset - 18) / total))
        except (tk.TclError, AttributeError):
            pass

    def _show_chapter(self, index: int) -> None:
        """Abrir un capítulo. Sólo se rearma la página, no la pantalla."""
        self._book_chapter = index
        # La página primero y el índice después: escribir la página es lo que
        # da por leídas las anotaciones, así que al revés el capítulo recién
        # abierto se quedaba en azul.
        self._render_book_page()
        self._paint_book_index(index)
        # Al principio del capítulo nuevo. Sin esto, el marco con scroll se
        # quedaba donde lo había dejado el capítulo anterior y uno aterrizaba
        # en la mitad de una página que todavía no había empezado a leer.
        try:
            self.book_page._parent_canvas.yview_moveto(0.0)
        except (tk.TclError, AttributeError):
            pass

    def _paint_book_index(self, index: int) -> None:
        """
        Repintar el índice: qué capítulo está abierto y cuál tiene algo sin
        leer.

        El azul le gana al oro mientras dure. El oro dice qué clase de
        capítulo es --- uno que no se llena estudiando --- y eso no se va a
        ninguna parte, así que vuelve en cuanto el azul se apaga.
        """
        lit = book.chapters_for_locks(self._fresh_notes())
        before = getattr(self, "_book_lit", set())
        for position, button in enumerate(getattr(self, "book_buttons", [])):
            try:
                options = {"fg_color": (SURFACE if position == index
                                        else "transparent")}
                if position in lit:
                    options["text_color"] = NOTE_BLUE
                elif book.is_special(book.CHAPTERS[position]):
                    # El capítulo del sendero conserva su oro aunque no esté
                    # elegido: se lo pinta el brillo, no esta línea. Salvo
                    # que venga de estar en azul --- ahí el brillo nunca se
                    # le prendió, y éste es el momento de prenderlo.
                    if position in before:
                        start_shimmer(button)
                else:
                    options["text_color"] = (GOLD if position == index
                                             else TEXT_NORMAL)
                button.configure(**options)
            except tk.TclError:
                return
        self._book_lit = set(lit)

    def _render_book_page(self) -> None:
        """
        Escribir el capítulo elegido sobre el papel.

        Con widgets de tkinter pelado, igual que las filas de logros: un
        capítulo son cincuenta o sesenta párrafos y cada widget de
        customtkinter dibuja un rectángulo redondeado propio sobre un canvas
        propio. Acá además no hace falta ninguno: no hay nada redondeado ni
        nada que cambie de color, es texto quieto sobre un fondo.
        """
        page = self.book_page
        for child in page.winfo_children():
            child.destroy()
        chapter = book.CHAPTERS[self._book_chapter]
        wrap = self.BOOK_COLUMN
        #: El título de cada entrada, para poder bajar hasta una
        #: (`_scroll_book_to`).
        self._book_headings: Dict[str, tk.Label] = {}

        host = tk.Frame(page, bg=PAPER)
        host.pack(anchor="n", padx=30, pady=(30, 34))

        tk.Label(host, text=trf("CAPÍTULO {numeral}", numeral=chapter.numeral),
                 font=scaled(("Georgia", 10)), bg=PAPER, fg=GOLD_DIM,
                 anchor="w").pack(anchor="w")
        tk.Label(host, text=tr(chapter.title), font=scaled(FONT_BOOK_HEAD),
                 bg=PAPER, fg=INK, wraplength=wrap, justify="left",
                 anchor="w").pack(anchor="w", pady=(2, 10))
        tk.Frame(host, bg=RULE, height=1, width=wrap).pack(fill="x")
        tk.Label(host, text=tr(chapter.blurb),
                 font=scaled(("Georgia", 12, "italic")), bg=PAPER,
                 fg=INK_MUTED, wraplength=wrap, justify="left", anchor="w"
                 ).pack(anchor="w", pady=(12, 4))

        fresh = set(self._fresh_notes())
        written_now: List[str] = []
        for entry in chapter.entries:
            open_now = (not entry.locked_by
                        or self._lore_unlocked(entry.locked_by))
            # Un apartado del sendero ni siquiera muestra su título mientras
            # está cerrado: el título es la mitad de lo que el relato tiene
            # para revelar. Los demás sí, porque ahí el título es la pista.
            secret = book.is_secret(entry)
            heading = tk.Label(
                host, text=tr(entry.heading if open_now or not secret else "? ? ?"),
                font=scaled(("Georgia", 15, "bold")), bg=PAPER,
                fg=INK if open_now else INK_FAINT, wraplength=wrap,
                justify="left", anchor="w")
            heading.pack(anchor="w", pady=(22, 6))
            self._book_headings[entry.key] = heading
            # Y el que además es legendario se escribe con oro, abierto o
            # cerrado: es lo que lo distingue de los tres apartados que tiene
            # al lado, que se consiguen trabajando.
            if entry.legendary:
                if open_now:
                    start_shimmer(heading, option="fg")
                else:
                    heading.configure(fg=GOLD_DIM)
            if not open_now:
                tk.Label(host, text=tr("— sin anotar todavía —"),
                         font=scaled(("Georgia", 11, "italic")), bg=PAPER,
                         fg=INK_FAINT, anchor="w").pack(anchor="w")
                if entry.hint:
                    tk.Label(host, text=tr(entry.hint),
                             font=scaled(("Georgia", 11)), bg=PAPER,
                             fg=INK_FAINT, wraplength=wrap, justify="left",
                             anchor="w").pack(anchor="w", pady=(4, 0))
                continue

            for text in entry.paragraphs:
                # El párrafo se traduce **entero** y se parte después: la
                # entradilla y el cuerpo son dos mitades de una misma frase,
                # y partidas primero ninguna de las dos sería una clave.
                lead, rest = self._split_lead(tr(text))
                if lead:
                    tk.Label(host, text=lead,
                             font=scaled(("Georgia", 12, "bold")), bg=PAPER,
                             fg=INK, wraplength=wrap, justify="left",
                             anchor="w").pack(anchor="w", pady=(8, 1))
                if rest:
                    tk.Label(host, text=rest, font=scaled(FONT_BOOK),
                             bg=PAPER, fg=INK, wraplength=wrap,
                             justify="left", anchor="w"
                             ).pack(anchor="w", pady=(0, 8))
            for figure in entry.figures:
                self._draw_figure(host, figure, wrap)
            for plot in entry.plots:
                self._draw_plot(host, plot, wrap)
            if entry.recipe:
                self._recipe_box(host, entry.recipe, wrap)
            if entry.locked_by in fresh:
                self._handwritten_note(host, wrap)
                written_now.append(entry.locked_by)
            # Leer un apartado del sendero es, para el relato, un objetivo
            # cumplido: es la traba del segundo boton dorado. Se marca aca
            # --- cuando el texto se pinta de verdad --- y no al abrir el
            # capitulo, para que abrirlo de refilon no cuente.
            if entry.locked_by:
                self._story_book_read(entry.locked_by)

        self._mark_notes_seen(written_now)

    @staticmethod
    def _split_lead(text: str) -> Tuple[str, str]:
        """Partir un párrafo que arranca con una entradilla en negrita.

        Tk no sabe poner un tramo en negrita adentro de una etiqueta, así
        que la entradilla se escribe como su propia línea. Se lee igual de
        bien --- termina pareciendo una definición --- y evita tener que
        armar un widget de texto enriquecido para tres párrafos.
        """
        if text.startswith("**") and "**" in text[2:]:
            end = text.index("**", 2)
            return text[2:end], text[end + 2:].strip().replace("**", "")
        # Y los que puedan haber quedado en el medio se sacan igual. Acá una
        # negrita suelta no se puede poner --- ver arriba --- pero los dos
        # asteriscos sí se veían: salían impresos tal cual, que es peor que
        # no destacar nada.
        return "", text.replace("**", "")

    #: Medidas del pentagrama de ejemplo. El espacio entre líneas manda: un
    #: grado --- de una línea al espacio de al lado --- es la mitad de eso.
    STAFF_GAP = 11
    STAFF_STEP = STAFF_GAP / 2

    def _draw_figure(self, host, figure, wrap: int) -> None:
        """
        Un pentagrama de ejemplo, dibujado sobre un canvas.

        Sobre canvas y no con widgets porque es un dibujo: cinco líneas,
        unas cabezas de nota y sus líneas adicionales. Las redondas se usan
        a propósito --- no llevan plica, y así el dibujo no tiene que decidir
        para qué lado va el palito, que es información que acá no significa
        nada.
        """
        columns = max((len(voice) for voice in figure.voices), default=0)
        if not columns:
            return
        left, gap = 58, 52
        width = min(wrap, left + columns * gap + 24)
        # Alto: los cinco renglones más lo que sobresalga arriba y abajo.
        steps = [s for voice in figure.voices for s in voice if s is not None]
        low, high = min(steps + [0]), max(steps + [8])
        top_pad = 16 + max(0, high - 8) * self.STAFF_STEP
        height = int(top_pad + 8 * self.STAFF_STEP
                     + max(0, -low) * self.STAFF_STEP + 32)
        base = top_pad + 8 * self.STAFF_STEP          # y de la línea de abajo

        canvas = tk.Canvas(host, width=width, height=height, bg=PAPER,
                           highlightthickness=0, bd=0)
        canvas.pack(anchor="w", pady=(6, 2))

        def y_of(step: float) -> float:
            return base - step * self.STAFF_STEP

        for line in range(5):
            y = y_of(line * 2)
            canvas.create_line(10, y, width - 10, y, fill=RULE)
        # La de fa se centra entre la cuarta línea y la quinta, que es donde
        # queda su cuerpo; sus dos puntos rodean la cuarta.
        if figure.clef == "fa":
            canvas.create_text(30, y_of(6.6), text="𝄢", fill=INK_MUTED,
                               font=scaled(("Segoe UI Symbol", 30)))
        else:
            canvas.create_text(30, y_of(4), text="𝄞", fill=INK_MUTED,
                               font=scaled(("Segoe UI Symbol", 30)))

        radius_x, radius_y = 6, 4.5
        for voice in figure.voices:
            for column, step in enumerate(voice):
                if step is None:
                    continue
                x = left + column * gap
                y = y_of(step)
                # Líneas adicionales para lo que se sale del pentagrama.
                #
                # Sólo caen en los grados **pares**: los impares son los
                # espacios que quedan entre ellas. Empezando en el grado de
                # la nota, una nota en un espacio de abajo --- un sol3, que
                # es -5 --- se dibujaba con sus dos líneas corridas medio
                # renglón, y quedaban tachándola en vez de sosteniéndola.
                extra = step if step % 2 == 0 else step + 1
                while extra <= -2:
                    canvas.create_line(x - 11, y_of(extra), x + 11,
                                       y_of(extra), fill=RULE)
                    extra += 2
                extra = step if step % 2 == 0 else step - 1
                while extra >= 10:
                    canvas.create_line(x - 11, y_of(extra), x + 11,
                                       y_of(extra), fill=RULE)
                    extra -= 2
                canvas.create_oval(x - radius_x, y - radius_y,
                                   x + radius_x, y + radius_y,
                                   outline=INK, width=2, fill=PAPER)

        for column, mark in enumerate(figure.marks):
            if mark:
                canvas.create_text(left + column * gap, height - 14,
                                   text=_figure_mark(mark), fill=INK_FAINT,
                                   font=scaled(("Georgia", 9)))
        if figure.caption:
            tk.Label(host, text=tr(figure.caption),
                     font=scaled(("Georgia", 10, "italic")), bg=PAPER,
                     fg=INK_MUTED, wraplength=wrap, justify="left",
                     anchor="w").pack(anchor="w", pady=(0, 12))

    #: Alto del gráfico del capítulo de física, y los márgenes de sus ejes.
    #: Dos filas de rótulos debajo del piso: los de las barras y los de las
    #: marcas de referencia. Van en filas distintas porque en el gráfico de
    #: temperamento una barra y su marca están a cinco píxeles --- ése es
    #: justamente el dato --- y los dos rótulos en la misma línea se pisan.
    PLOT_HEIGHT = 206
    PLOT_LEFT = 46
    PLOT_TOP = 16
    PLOT_FLOOR = 130
    #: Cuántos renglones de rótulos caben debajo del piso, y cuánto mide
    #: cada uno. Tres alcanzan para el peor caso, que es la serie
    #: subarmónica: sus cuatro barras más graves quedan a nueve píxeles una
    #: de otra ---amontonarse es justamente lo que el dibujo viene a
    #: mostrar--- y en un solo renglón «8 7 6» se lee «876».
    PLOT_LABEL_ROWS = 3
    PLOT_LABEL_STEP = 11

    def _draw_plot(self, host, plot, wrap: int) -> None:
        """
        Un gráfico a escala: barras por frecuencia, altas por amplitud.

        Es el hermano de `_draw_figure` y la diferencia es toda la razón de
        que exista aparte: un pentagrama de ejemplo no está a escala y no
        tiene por qué estarlo, y acá lo que hay que ver **es** la escala.
        Que las barras de la serie armónica estén igualmente espaciadas es
        el hecho del capítulo, así que las posiciones salen de los hercios
        y no de una grilla cómoda.
        """
        bars = list(plot.bars)
        if not bars:
            return
        left = self.PLOT_LEFT
        right = max(left + 120, wrap - 14)
        floor_y, top = self.PLOT_FLOOR, self.PLOT_TOP

        low = plot.low
        high = plot.high or max(freq for freq, _a, _l in bars) * 1.06
        if high <= low:
            return
        tallest = max((amplitude for _f, amplitude, _l in bars), default=1.0)
        tallest = tallest if tallest > 0 else 1.0

        def x_of(frequency: float) -> float:
            return left + (frequency - low) / (high - low) * (right - left)

        def y_of(amplitude: float) -> float:
            return floor_y - amplitude / tallest * (floor_y - top)

        canvas = tk.Canvas(host, width=right + 14, height=self.PLOT_HEIGHT,
                           bg=PAPER, highlightthickness=0, bd=0)
        canvas.pack(anchor="w", pady=(8, 2))

        for fraction in (0.25, 0.5, 0.75, 1.0):
            y = y_of(fraction * tallest)
            canvas.create_line(left, y, right, y, fill=RULE, dash=(1, 5))
        canvas.create_line(left, floor_y, right, floor_y, fill=INK_MUTED)
        canvas.create_line(left, floor_y, left, top, fill=INK_MUTED)
        canvas.create_text(left - 13, (floor_y + top) / 2, text=tr("amplitud"),
                           anchor="center", fill=INK_FAINT,
                           font=scaled(("Georgia", 9)), angle=90)
        # El eje horizontal, en tres: dónde empieza, qué mide y dónde
        # termina. Sin los dos extremos el dibujo muestra proporciones sin
        # decir de qué, y el rótulo solo no alcanza.
        canvas.create_text((left + right) / 2, floor_y + 54, text=plot.axis,
                           anchor="center", fill=INK_FAINT,
                           font=scaled(("Georgia", 9)))
        canvas.create_text(left, floor_y + 54, text=f"{low:.0f}",
                           anchor="w", fill=INK_FAINT,
                           font=scaled(("Georgia", 9)))
        canvas.create_text(right, floor_y + 54, text=f"{high:.0f}",
                           anchor="e", fill=INK_FAINT,
                           font=scaled(("Georgia", 9)))
        if plot.reference:
            # Arriba a la derecha: arriba a la izquierda le pasaba por encima
            # a la primera barra, que en la serie armónica es justo la más
            # alta de todas.
            canvas.create_text(
                right, 2,
                text=trf("fundamental: {reference:.0f} Hz",
                         reference=plot.reference),
                anchor="ne", fill=INK_FAINT, font=scaled(("Georgia", 9)))

        # Hasta dónde llegó lo escrito en cada renglón de rótulos. Uno que
        # no entre al lado del anterior baja al de abajo.
        taken = [left - 999.0] * self.PLOT_LABEL_ROWS
        rows_used = 1
        for frequency, amplitude, mark in bars:
            x = x_of(frequency)
            y = y_of(amplitude)
            if floor_y - y < 1.5:
                # Una barra que no llega a un píxel se dibuja igual como un
                # zócalo: en la flauta, el octavo armónico vale tres
                # milésimas y desaparecía --- y que esté y sea diminuto es
                # exactamente lo que el gráfico viene a decir.
                y = floor_y - 1.5
            canvas.create_rectangle(x - 3.5, y, x + 3.5, floor_y,
                                    fill=INK_MUTED, outline=INK)
            if mark:
                half = len(mark) * 3.5 + 5.0
                row = next((r for r in range(self.PLOT_LABEL_ROWS)
                            if x - half > taken[r]),
                           self.PLOT_LABEL_ROWS - 1)
                taken[row] = x + half
                rows_used = max(rows_used, row + 1)
                canvas.create_text(x, floor_y + 6 + row * self.PLOT_LABEL_STEP,
                                   text=tr(mark), anchor="n", fill=INK_MUTED,
                                   font=scaled(("Georgia", 9)))

        for frequency, mark in plot.ticks:
            x = x_of(frequency)
            canvas.create_line(x, floor_y + 3, x, top, fill=GOLD_DIM,
                               dash=(2, 3))
            canvas.create_text(x + 3,
                               floor_y + 8 + rows_used * self.PLOT_LABEL_STEP,
                               text=tr(mark), anchor="nw", fill=GOLD_DIM,
                               font=scaled(("Georgia", 9)))

        if plot.caption:
            tk.Label(host, text=tr(plot.caption),
                     font=scaled(("Georgia", 10, "italic")), bg=PAPER,
                     fg=INK_MUTED, wraplength=wrap, justify="left",
                     anchor="w").pack(anchor="w", pady=(0, 12))

    def _recipe_box(self, host, text: str, wrap: int) -> None:
        """El recuadro de «cómo conseguirlo», con su filete al costado."""
        box = tk.Frame(host, bg=PAPER_EDGE)
        box.pack(anchor="w", fill="x", pady=(6, 4))
        tk.Frame(box, bg=GOLD_DIM, width=3).pack(side="left", fill="y")
        inner = tk.Frame(box, bg=PAPER_EDGE)
        inner.pack(side="left", fill="both", expand=True)
        tk.Label(inner, text=tr("CÓMO CONSEGUIRLO"), font=scaled(("Georgia", 9)),
                 bg=PAPER_EDGE, fg=GOLD_DIM, anchor="w"
                 ).pack(anchor="w", padx=12, pady=(9, 2))
        tk.Label(inner, text=tr(text), font=scaled(("Georgia", 11)),
                 bg=PAPER_EDGE, fg=INK_MUTED, wraplength=wrap - 30,
                 justify="left", anchor="w"
                 ).pack(anchor="w", padx=12, pady=(0, 10))

    def _handwritten_note(self, host, wrap: int) -> None:
        """La anotación a mano que marca lo recién escrito."""
        handwritten_line(host, "Has anotado tus nuevos descubrimientos.",
                         PAPER, wrap=wrap - 40).pack(anchor="w", pady=(6, 2))

    # -- logros -------------------------------------------------------------

    def _default_ga_config(self) -> GAConfig:
        """
        La configuración de búsqueda tal como la ofrece el programa.

        Se arma desde ``GA_FIELDS`` y no desde ``GAConfig()`` a propósito:
        lo que el logro pregunta es si el usuario tocó lo que vio en el
        diálogo, y ahí es donde están los valores que vio.
        """
        values: Dict[str, float] = {}
        for key, _label, default, _explanation in self.GA_FIELDS:
            values[key] = float(default) if "." in default else int(default)
        return GAConfig(**values)

    def _award(self, keys) -> None:
        """
        Desbloquear lo que corresponda y avisar.

        Único punto de entrada: todos los enganches del programa terminan
        acá, así que la decisión de qué se muestra y en qué orden está en un
        solo lugar.
        """
        # Un legendario que pertenece a un sendero en curso no se entrega
        # acá: lo entrega el cierre del sendero, que es justamente el relato
        # de cómo se llega a él. Fuera de la historia, nada cambia.
        wanted = {key for key in keys
                  if key and not self.story.withholds(key)}
        if not wanted:
            return
        before = self.achievements.stars()
        fresh = self.achievements.unlock(wanted)
        if not fresh:
            return
        for achievement in fresh:
            if achievement.legendary:
                # Un legendario no lleva aviso: el cartel diría el nombre
                # antes de la animación y arruinaría la sorpresa, que es la
                # mitad de lo que es un logro oculto. Sólo la animación.
                self.celebrations.append(("legendary", achievement))
            else:
                self._show_toast(achievement)
        earned = self.achievements.stars()
        if earned > before:
            # Completar la primera puede completar también la segunda si ya
            # estaba llena: se anuncia sólo la más grande, que es la que
            # cuenta.
            self.achievements.mark_stars_seen(earned)
            self.celebrations.insert(0, ("star", earned))
        if self.celebrations and self.overlay is None:
            self.after(600, self._next_celebration)
        # Un logro puede haber abierto un apartado del libro.
        self._refresh_note_flag()
        # Y si con esto no quedó un solo logro sin conseguir, hay alguien que
        # estuvo mirando todo el tiempo.
        self._check_watcher()

    # -- el aviso de arriba a la izquierda ----------------------------------

    #: Cuántos avisos pueden estar en pantalla a la vez. Una corrida puede
    #: cerrar media docena de logros de golpe: los que no entran esperan en
    #: fila (`_toast_backlog`) y salen cuando se va uno. Con cuatro a la vez
    #: tapaban media pantalla, y cerrando el más viejo para hacer lugar se
    #: perdían avisos que nadie llegaba a leer.
    MAX_TOASTS = 2

    def _show_toast(self, achievement, heading_text: str = "") -> None:
        if len(self.toasts) >= self.MAX_TOASTS:
            self._toast_backlog.append((achievement, heading_text))
            return
        toast = Toast(self, achievement, on_close=self._drop_toast,
                      heading_text=heading_text)
        self.toasts.append(toast)
        self._reflow_toasts()
        # El aviso no se mueve: aparece donde va y se le enciende el borde.
        #
        # Antes entraba deslizándose y eso resultó ser el origen de la
        # "rayita en L" que cruzaba el encabezado. Un widget en movimiento se
        # mapea y se dibuja mientras Tk todavía lo está reubicando, y en
        # algún cuadro se alcanza a ver un pedazo del marco --- dos bordes en
        # ángulo --- antes que el contenido. Encender un color no mueve nada
        # y no puede mostrar un dibujo a medio hacer.
        border = GOLD if achievement.legendary else ACCENT

        def glow(step: float) -> None:
            try:
                toast.configure(border_color=mix(SURFACE_LIGHT, border, step))
            except tk.TclError:
                pass

        animate(toast, glow, steps=6, period=22)

    def _drop_toast(self, toast) -> None:
        if toast in self.toasts:
            self.toasts.remove(toast)
        self._reflow_toasts()
        if self._toast_backlog and len(self.toasts) < self.MAX_TOASTS:
            achievement, heading_text = self._toast_backlog.pop(0)
            # En el próximo respiro: `close` avisa desde adentro de su propio
            # `destroy`, y armar otro cartel ahí mismo lo dibuja a medias.
            self.after(120, lambda: self._show_toast(achievement, heading_text))

    def _reflow_toasts(self) -> None:
        """
        Apilar los avisos vivos arriba a la derecha, de arriba hacia abajo.

        Anclados al borde derecho de la ventana, así que siguen en su lugar
        cuando se la agranda. Arrancan debajo del encabezado y no encima:
        tapar los botones de ahí arriba deja sin usar el historial y los
        logros durante los segundos que el aviso está en pantalla.
        """
        # Bien despegado del riel de progreso: a 62 el primer aviso quedaba
        # justo encima de la barra y parecía parte de ella.
        offset = 78
        for toast in list(self.toasts):
            try:
                toast.place(relx=1.0, x=-18, y=offset, anchor="ne")
                toast.lift()
                toast.update_idletasks()
                offset += toast.winfo_reqheight() + 8
            except tk.TclError:
                self.toasts.remove(toast)

    # -- las animaciones a pantalla completa --------------------------------

    def _next_celebration(self) -> None:
        if self.overlay is not None or not self.celebrations:
            return
        kind, payload = self.celebrations.pop(0)
        # Los huevos de pascua entran en la misma fila que las estrellas y
        # los legendarios: son animaciones a pantalla completa y dos de ellas
        # a la vez se dibujarían una encima de la otra.
        {"star": self._celebrate_star,
         "legendary": self._celebrate_legendary,
         "blast": self._celebrate_blast,
         "secret": self._celebrate_secret}.get(
            kind, self._celebrate_legendary)(payload)

    #: Medidas del lienzo de las animaciones. Fijas y no derivadas del ancho
    #: de la ventana: el velo se dibuja antes de que Tk haya repartido el
    #: espacio, así que preguntarle su tamaño devuelve 1 y la estrella
    #: aparecía pegada al borde izquierdo.
    CELEBRATION_WIDTH = 560
    CELEBRATION_HEIGHT = 300

    def _open_overlay(self) -> Tuple["ctk.CTkFrame", "ctk.CTkFrame"]:
        """El velo que tapa todo, y el bloque centrado donde va el contenido."""
        overlay = ctk.CTkFrame(self, fg_color=VEIL, corner_radius=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        self.overlay = overlay
        content = ctk.CTkFrame(overlay, fg_color="transparent")
        content.place(relx=0.5, rely=0.5, anchor="center")
        # Red de seguridad: el botón aparece recién al terminar la animación,
        # y un velo opaco del que no se pudiera salir dejaría la aplicación
        # inutilizable. Un clic en cualquier parte, o Escape, lo levantan.
        # `bind_all` no se puede usar: customtkinter lo prohíbe en sus
        # widgets. El atajo va en la ventana, que es donde llega la tecla
        # mientras el velo tiene el frente. Sumado y no reemplazando, y al
        # cerrar se desata sólo el suyo: con `unbind("<Escape>")` el velo se
        # llevaba también el Escape del recorrido de bienvenida.
        overlay.bind("<Button-1>", lambda _event: self._close_overlay())
        unbind_one(self, "<Escape>", getattr(self, "_overlay_escape", None))
        self._overlay_escape = self.bind("<Escape>", self._escape_overlay,
                                         add="+")
        return overlay, content

    def _escape_overlay(self, _event=None) -> None:
        if self.overlay is not None:
            self._close_overlay()

    def _close_overlay(self) -> None:
        overlay, self.overlay = self.overlay, None
        if overlay is not None:
            try:
                unbind_one(self, "<Escape>",
                           getattr(self, "_overlay_escape", None))
                self._overlay_escape = None
                overlay.destroy()
            except tk.TclError:
                pass
        # Los avisos quedaron debajo del velo; vuelven arriba al destaparse.
        self._reflow_toasts()
        if self.celebrations:
            self.after(400, self._next_celebration)

    def _animate_star(self, canvas, frames: int, colour: str,
                      on_done, frame: int = 0, halo: bool = False) -> None:
        """
        La estrella que crece y se endereza.

        Se redibuja un par de polígonos por cuadro sobre un lienzo que no
        tiene nada más, que es lo más barato que puede hacer Tk sin dejar de
        ser una animación. ``halo`` agrega una estrella grande y apagada
        girando al revés detrás, que es lo que distingue a un legendario de
        una estrella ganada.
        """
        import math

        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        progress = min(1.0, frame / max(1, frames))
        # Arranca rápido y frena al final, con un rebote corto: la estrella
        # se pasa un poco de tamaño y vuelve.
        eased = 1 - (1 - progress) ** 3
        overshoot = 1.0 + 0.12 * math.sin(math.pi * min(1.0, progress * 1.15))
        size = 118 * eased * overshoot
        cx, cy = self.CELEBRATION_WIDTH / 2, self.CELEBRATION_HEIGHT / 2
        canvas.delete("star")
        if size > 1:
            if halo:
                canvas.create_polygon(
                    star_polygon(cx, cy, size * 1.45, size * 0.36,
                                 rotation=math.pi / 5 - (1 - eased) * math.pi),
                    fill=GOLD_DIM, outline="", tags="star")
            canvas.create_polygon(
                star_polygon(cx, cy, size, size * 0.42,
                             rotation=(1 - eased) * math.pi),
                fill=colour, outline="", tags="star")
        if frame >= frames:
            on_done()
            return
        canvas.after(22, lambda: self._animate_star(
            canvas, frames, colour, on_done, frame + 1, halo))

    def _celebration_canvas(self, content, height: int = 0) -> "tk.Canvas":
        canvas = tk.Canvas(content, bg=VEIL, highlightthickness=0,
                           width=self.CELEBRATION_WIDTH,
                           height=height or self.CELEBRATION_HEIGHT)
        canvas.pack()
        return canvas

    #: La fanfarria de cada estrella. Es el mismo acorde las tres veces,
    #: cada vez con más notas y más sala: lo que sube no es el premio sino
    #: cuánto ocupa.
    STAR_SOUNDS = {1: "star_one", 2: "star_two", 3: "star_three"}

    def _celebrate_star(self, star: int) -> None:
        self._play_cue(self.STAR_SOUNDS.get(star, "star_three"))
        _overlay, content = self._open_overlay()
        canvas = self._celebration_canvas(content)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.pack(fill="x")

        ordinal = {1: "primera", 2: "segunda", 3: "tercera"}.get(star, str(star))

        def reveal() -> None:
            if not holder.winfo_exists():
                return
            headline = ctk.CTkLabel(
                holder, text=trf("¡Ganaste la {ordinal} estrella!",
                                 ordinal=ordinal),
                font=scaled(("Segoe UI Semibold", 26)), text_color=GOLD)
            headline.pack(pady=(6, 6))
            start_shimmer(headline)
            _done, total = self.achievements.star_progress(star)
            ctk.CTkLabel(
                holder,
                text=trf("Completaste los {total} logros de la {ordinal} "
                         "estrella.",
                         total=total, ordinal=ordinal),
                font=scaled(("Segoe UI", 15)), text_color=TEXT_NORMAL
                ).pack()
            if star >= achievements.STAR_COUNT:
                title = ctk.CTkLabel(
                    holder, text=trf("Título obtenido: {TRIUMPH_TITLE}",
                                     TRIUMPH_TITLE=tr(achievements.TRIUMPH_TITLE)),
                    font=scaled(("Segoe UI Semibold", 19)), text_color=GOLD)
                title.pack(pady=(14, 0))
                start_shimmer(title)
            ctk.CTkButton(holder, text=tr("Seguir"), width=180, height=42,
                          font=scaled(("Segoe UI Semibold", 14)),
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=self._close_overlay).pack(pady=(24, 0))

        self._animate_star(canvas, 34, GOLD, reveal)

    def _celebrate_legendary(self, achievement) -> None:
        _overlay, content = self._open_overlay()
        canvas = self._celebration_canvas(content)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.pack(fill="x")

        def reveal() -> None:
            if not holder.winfo_exists():
                return
            heading = ctk.CTkLabel(holder, text=tr("LOGRO LEGENDARIO"),
                                   font=scaled(("Segoe UI Semibold", 15)),
                                   text_color=GOLD)
            heading.pack()
            start_shimmer(heading, period=70)
            name = ctk.CTkLabel(holder, text=tr(achievement.name),
                                font=scaled(("Segoe UI Semibold", 28)),
                                text_color=GOLD)
            name.pack(pady=(6, 8))
            start_shimmer(name, period=70)
            ctk.CTkLabel(holder,
                         text=tr(achievements.plain(achievement.description)),
                         font=scaled(("Segoe UI", 15, "italic")),
                         text_color=TEXT_MUTED, wraplength=520,
                         justify="center").pack()
            if achievement.title:
                title = ctk.CTkLabel(
                    holder, text=trf("Título obtenido: {title}",
                                     title=achievement.title),
                    font=scaled(("Segoe UI Semibold", 19)), text_color=GOLD)
                title.pack(pady=(18, 0))
                start_shimmer(title)
            ctk.CTkButton(holder, text=tr("Seguir"), width=180, height=42,
                          font=scaled(("Segoe UI Semibold", 14)),
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=self._close_overlay).pack(pady=(24, 0))

        self._animate_star(canvas, 34, GOLD, reveal, halo=True)

    # -- los huevos de pascua -----------------------------------------------
    #
    # Seis combinaciones exactas que el programa reconoce y que no están
    # escritas en ninguna pantalla. La condición de cada una vive en
    # `engine/eggs.py` --- son funciones puras, verificables sin abrir la
    # ventana --- y lo que hay acá es sólo la reacción: el ruido, el cartel o
    # la animación.
    #
    # Ninguno da un logro. Lo único que se ve es un contador dorado al pie de
    # la pantalla de logros, que dice cuántos van y jamás cuáles faltan; el
    # premio por completarlos se toca, no se recibe.

    #: Los huevos que traen su propio ruido, y que por lo tanto no llevan el
    #: de "encontraste algo". El grito del zorro y el rugido SON el huevo:
    #: una campanita encima le contestaría el chiste.
    EGGS_WITH_OWN_SOUND = frozenset({"zombie", "fox", "blast"})

    def _egg(self, key: str) -> bool:
        """Anotar un hallazgo. ``True`` sólo la primera vez."""
        try:
            found = self.eggs.find(key)
        except Exception:                                   # noqa: BLE001
            return False          # un huevo no puede romper lo que interrumpe
        if found and key not in self.EGGS_WITH_OWN_SOUND:
            # Los otros tres eran mudos: la viñeta de los anteojos, el
            # cartel del cerrajero y el de Bach ocurrían en silencio, y sin
            # ruido no se distinguen de un mensaje cualquiera del programa.
            self._play_cue("egg_found")
        return found

    def _when_done(self, thread, action, period: int = 120) -> None:
        """
        Llamar a ``action`` cuando el hilo termine, desde el hilo de Tk.

        **Un hilo de fondo no puede agendar nada en Tk.** `after` desde otro
        hilo no es simplemente riesgoso: tkinter lo rechaza con
        ``RuntimeError: main thread is not in main loop``, y como la llamada
        estaba envuelta, lo que pasaba era nada --- el botón de «Escuchar»
        se quedaba en «Sonando…» para siempre y el ruido de un huevo recién
        sintetizado no llegaba a sonar nunca. Así que el que pregunta es Tk,
        que es el mismo criterio con el que el algoritmo genético reporta
        por una cola que el bucle principal drena por timer.
        """
        def check() -> None:
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            if thread is not None and thread.is_alive():
                self.after(period, check)
                return
            action()

        self.after(period, check)

    def _play_cue(self, name: str) -> None:
        """
        Tocar un ruido de los que se hacen a pedido, esperando a que esté.

        `ambience.prepare` no los fabrica: son sonidos que casi ninguna
        sesión va a escuchar. Se sintetizan a pedido en un hilo aparte y se
        tocan de vuelta en el de Tk, que es el único que puede: MCI le cuelga
        cada dispositivo al hilo que lo abrió.
        """
        def wait(tries: int = 0) -> None:
            # Pregunta Tk, no contesta el hilo: `after` desde el hilo que
            # sintetiza no se agenda, se rechaza. Cuarenta intentos son unos
            # seis segundos, de sobra para el más largo de los tres.
            if ambience.made(name):
                ambience.play(name)
                return
            if tries < 40:
                self.after(150, lambda: wait(tries + 1))

        try:
            ambience.summon(name)
            wait()
        except Exception:                                   # noqa: BLE001
            pass          # el sonido es decoración, igual que en la historia

    def _egg_legend(self, text: str, seconds: float = 4.0) -> None:
        """
        Un cartel dorado en el medio de la ventana, que se va solo.

        Va sobre un manto del color del fondo que tapa la ventana entera, y
        no suelto encima de la pantalla. Tk no sabe de transparencias: un
        marco redondeado pinta sus esquinas del color de su padre, y encima
        de un panel claro esas cuatro esquinas se veían como un recuadro
        cuadrado alrededor del borde dorado. Con el manto detrás, lo que hay
        atrás de las esquinas es exactamente lo que el marco cree que hay.

        El manto además es lo que la frase merece: los dos carteles aparecen
        justo al cambiar de pantalla, y son todo el premio de su huevo.
        """
        veil = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        veil.place(relx=0, rely=0, relwidth=1, relheight=1)
        veil.lift()
        card = ctk.CTkFrame(veil, fg_color=SURFACE_LIGHT, corner_radius=16,
                            border_width=2, border_color=SURFACE_LIGHT)
        label = ctk.CTkLabel(card, text=tr(text),
                             font=scaled(("Georgia", 21, "italic")),
                             text_color=GOLD, wraplength=520,
                             justify="center")
        label.pack(padx=34, pady=(24, 6))
        ctk.CTkLabel(card, text=tr("(tocá para cerrar)"), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(pady=(0, 16))
        card.place(relx=0.5, rely=0.5, anchor="center")
        start_shimmer(label)

        def dismiss(_event=None) -> None:
            try:
                veil.destroy()
            except tk.TclError:
                pass

        bind_deeply(descendants(veil), "<Button-1>", dismiss)
        veil.bind("<Button-1>", dismiss)
        self.after(int(seconds * 1000), dismiss)
        animate(card, lambda step: card.configure(
            border_color=mix(SURFACE_LIGHT, GOLD, step)), steps=8, period=24)

    # -- el rugido (armonizador) --------------------------------------------

    def _egg_zombie(self, button) -> None:
        """Tónica, tónica y quinta, las tres redondas: no suena la melodía."""
        self._egg("zombie")
        self._play_cue("zombie")
        try:
            button.configure(text=tr("🧟  GRAAAH…"), state="disabled")
        except tk.TclError:
            return

        def restore() -> None:
            try:
                button.configure(text=tr("▶  Escuchar"), state="normal")
            except tk.TclError:
                pass

        self.after(2600, restore)

    # -- el zorro (parámetros del algoritmo) --------------------------------

    def _egg_fox(self) -> None:
        """1, 9, 8, 7 de arriba hacia abajo. Un susto y nada más."""
        self._egg("fox")
        self._play_cue("fox")
        overlay, _content = self._open_overlay()
        try:
            overlay.configure(fg_color="#07080B")
        except tk.TclError:
            return
        width = max(640, self.winfo_width())
        height = max(420, self.winfo_height())
        canvas = tk.Canvas(overlay, bg="#07080B", highlightthickness=0)
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        canvas.bind("<Button-1>", lambda _event: self._close_overlay())

        # Tres tamaños de golpe, no un acercamiento: Tk no interpola nada y
        # un susto que crece despacio deja de ser un susto. Es el mismo
        # criterio de los tres planos de las cinemáticas.
        sizes = (0.34, 0.72, 1.05)

        def frame(index: int) -> None:
            try:
                if not canvas.winfo_exists():
                    return
            except tk.TclError:
                return
            canvas.delete("all")
            if index >= len(sizes):
                return
            if index == len(sizes) - 1:
                canvas.create_rectangle(0, 0, width, height, fill="#3A1608",
                                        outline="")
            self._draw_fox(canvas, width / 2, height / 2,
                           height * 0.42 * sizes[index])
            canvas.after(70 if index < len(sizes) - 1 else 1500,
                         lambda: frame(index + 1))

        frame(0)
        # Se va sola: un velo del que hubiera que salir a mano convertiría el
        # susto en un trámite.
        self.after(2100, self._close_overlay)

    def _draw_fox(self, canvas, cx: float, cy: float, size: float) -> None:
        """La cara del zorro, en polígonos. No hace falta ninguna imagen."""
        orange, deep, pale, ink = "#E2711D", "#8E3D0E", "#F7EFE2", "#0A0A0C"
        edge = max(1, int(size * 0.035))

        for side in (-1, 1):
            canvas.create_polygon(
                cx + side * 0.94 * size, cy - 0.58 * size,
                cx + side * 0.66 * size, cy - 1.28 * size,
                cx + side * 0.24 * size, cy - 0.68 * size,
                fill=orange, outline=deep, width=edge)
            canvas.create_polygon(
                cx + side * 0.78 * size, cy - 0.64 * size,
                cx + side * 0.63 * size, cy - 1.05 * size,
                cx + side * 0.41 * size, cy - 0.68 * size,
                fill="#3B1D12", outline="")

        canvas.create_polygon(
            cx - 0.98 * size, cy - 0.62 * size,
            cx - 0.60 * size, cy - 0.02 * size,
            cx - 0.24 * size, cy + 0.66 * size,
            cx, cy + 1.00 * size,
            cx + 0.24 * size, cy + 0.66 * size,
            cx + 0.60 * size, cy - 0.02 * size,
            cx + 0.98 * size, cy - 0.62 * size,
            fill=orange, outline=deep, width=edge)

        # El hocico y las mejillas claras, una mitad por lado.
        for side in (-1, 1):
            canvas.create_polygon(
                cx, cy - 0.06 * size,
                cx + side * 0.56 * size, cy + 0.16 * size,
                cx + side * 0.17 * size, cy + 0.74 * size,
                cx, cy + 0.99 * size,
                fill=pale, outline="")

        for side in (-1, 1):
            canvas.create_polygon(
                cx + side * 0.66 * size, cy - 0.30 * size,
                cx + side * 0.22 * size, cy - 0.02 * size,
                cx + side * 0.58 * size, cy + 0.12 * size,
                fill=ink, outline="", smooth=True)
            canvas.create_oval(
                cx + side * 0.50 * size - 0.05 * size, cy - 0.14 * size,
                cx + side * 0.50 * size + 0.05 * size, cy - 0.04 * size,
                fill="#FFD9A0", outline="")

        canvas.create_polygon(
            cx - 0.13 * size, cy + 0.60 * size,
            cx + 0.13 * size, cy + 0.60 * size,
            cx, cy + 0.80 * size,
            fill=ink, outline="", smooth=True)
        canvas.create_line(cx, cy + 0.78 * size, cx, cy + 0.88 * size,
                           fill=ink, width=edge)
        for side in (-1, 1):
            canvas.create_line(cx, cy + 0.88 * size,
                               cx + side * 0.16 * size, cy + 0.80 * size,
                               fill=ink, width=edge, smooth=True)

    # -- los anteojos (tamaño de letra al tope) -----------------------------

    def _egg_glasses(self) -> None:
        """
        La viñeta: el programa se mira desde adentro de un par de lentes.

        Hecha con cinco marcos opacos alrededor y no con un velo: un velo
        taparía justamente lo que el huevo quiere mostrar --- la interfaz
        gigante, vista por los dos cristales. Se va sola a los pocos
        segundos, porque un adorno que se queda es un estorbo.
        """
        shade = "#04060B"
        pieces: List = []

        def block(relx, rely, relwidth, relheight):
            piece = ctk.CTkFrame(self, fg_color=shade, corner_radius=0,
                                 border_width=2, border_color=SURFACE)
            piece.place(relx=relx, rely=rely, relwidth=relwidth,
                        relheight=relheight)
            piece.lift()
            pieces.append(piece)
            return piece

        block(0, 0, 1, 0.13)
        bottom = block(0, 0.87, 1, 0.13)
        block(0, 0.13, 0.055, 0.74)
        block(0.945, 0.13, 0.055, 0.74)
        block(0.477, 0.13, 0.046, 0.74)

        wink = ctk.CTkLabel(bottom, text=tr("¿Mejor así?"),
                            font=scaled(("Georgia", 15, "italic")),
                            text_color=GOLD_DIM, fg_color=shade)
        wink.place(relx=0.5, rely=0.5, anchor="center")

        def dismiss(_event=None) -> None:
            for piece in pieces:
                try:
                    piece.destroy()
                except tk.TclError:
                    pass
            pieces.clear()

        for piece in pieces:
            bind_deeply(descendants(piece), "<Button-1>", dismiss)
            animate(piece, lambda step, p=piece: p.configure(
                border_color=mix(SURFACE, GOLD_DIM, step)), steps=8, period=26)
        self.after(3600, dismiss)

    # -- la explosión (generador con todo al máximo) ------------------------

    def _celebrate_blast(self, _payload=None) -> None:
        """Todo prendido y todos los diales arriba. El generador se pasa."""
        self._play_cue("blast")
        overlay, _content = self._open_overlay()
        width = max(640, self.winfo_width())
        height = max(420, self.winfo_height())
        canvas = tk.Canvas(overlay, bg="#05070B", highlightthickness=0)
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        ground = height * 0.88
        frames = 64

        def draw(frame: int) -> None:
            try:
                if not canvas.winfo_exists():
                    return
            except tk.TclError:
                return
            position = min(1.0, frame / frames)
            canvas.delete("all")

            # El destello: los primeros cuadros son blanco y nada más.
            if position < 0.14:
                canvas.create_rectangle(
                    0, 0, width, height,
                    fill=mix("#FFFFFF", "#05070B", position / 0.14), outline="")

            # La onda de choque corriendo por el piso.
            span = width * 1.3 * position
            if span > 4:
                canvas.create_oval(width / 2 - span, ground - span * 0.16,
                                   width / 2 + span, ground + span * 0.16,
                                   outline=mix("#F0C98A", "#05070B",
                                               min(1.0, position * 1.4)),
                                   width=max(1, int(6 * (1 - position))))
            canvas.create_line(0, ground, width, ground, fill="#241E16", width=3)

            rise = 1 - (1 - position) ** 2
            radius = height * 0.17 * min(1.0, position / 0.22)
            centre = ground - height * (0.12 + 0.52 * rise)
            # El color va del blanco al gris a medida que sube: es la
            # secuencia que hace que se lea como humo y no como fuego eterno.
            heat = min(1.0, max(0.0, (position - 0.15) / 0.7))
            core = mix("#FFF6D8", "#B9B2A8", heat)
            middle = mix("#F5A623", "#7C766E", heat)
            outer = mix("#C2410C", "#4A4642", heat)

            stem = radius * (0.34 + 0.24 * rise)
            canvas.create_polygon(
                width / 2 - stem * 0.6, ground,
                width / 2 - stem, centre,
                width / 2 + stem, centre,
                width / 2 + stem * 0.6, ground,
                fill=middle, outline="")

            # El sombrero: una elipse y cuatro bollones, que es lo que le da
            # la silueta de nube y no de globo.
            cap = radius * (1.35 + 0.5 * rise)
            canvas.create_oval(width / 2 - cap, centre - radius * 0.78,
                               width / 2 + cap, centre + radius * 0.62,
                               fill=outer, outline="")
            for offset in (-0.78, -0.32, 0.32, 0.78):
                canvas.create_oval(
                    width / 2 + cap * offset - radius * 0.52,
                    centre - radius * 0.92,
                    width / 2 + cap * offset + radius * 0.52,
                    centre + radius * 0.12,
                    fill=outer, outline="")
            canvas.create_oval(width / 2 - radius * 0.86, centre - radius * 0.62,
                               width / 2 + radius * 0.86, centre + radius * 0.48,
                               fill=middle, outline="")
            canvas.create_oval(width / 2 - radius * 0.42, centre - radius * 0.34,
                               width / 2 + radius * 0.42, centre + radius * 0.24,
                               fill=core, outline="")

            if frame >= frames:
                self._blast_caption(canvas, width, height)
                return
            canvas.after(30, lambda: draw(frame + 1))

        draw(0)

    def _blast_caption(self, canvas, width: float, height: float) -> None:
        """Lo que queda en pantalla cuando el hongo terminó de subir."""
        canvas.create_text(width / 2, height * 0.16, text="☢",
                           font=scaled(("Segoe UI Symbol", 44)), fill=GOLD)
        canvas.create_text(width / 2, height * 0.26,
                           text=tr("Le pediste todo, a la vez, al máximo."),
                           font=scaled(("Georgia", 20, "italic")), fill=GOLD)
        canvas.create_text(width / 2, height * 0.32,
                           text=tr("Y el generador te lo dio."),
                           font=scaled(("Georgia", 15, "italic")),
                           fill=TEXT_MUTED)
        button = ctk.CTkButton(canvas, text=tr("Seguir"), width=180, height=42,
                               font=scaled(("Segoe UI Semibold", 14)),
                               fg_color=ACCENT, hover_color=ACCENT_HOVER,
                               command=self._close_overlay)
        button.place(relx=0.5, rely=0.42, anchor="center")

    # -- el título secreto --------------------------------------------------

    def _claim_secret_title(self) -> None:
        """Tocar el huevo dorado: la única forma de cobrar el título."""
        if not self.eggs.complete():
            return
        self.eggs.claim()
        self.celebrations.append(("secret", None))
        if self.overlay is None:
            self._next_celebration()

    def _celebrate_secret(self, _payload=None) -> None:
        # El unico premio del programa que hay que ir a tocar, y era el unico
        # que ocurria en silencio: los ruidos se cablearon al *encontrar* un
        # huevo y al ganar una estrella, y este gesto --- que es el final de
        # los seis --- quedo afuera. Va aca y no en `_claim_secret_title`
        # para que suene cada vez que la escena se juega, igual que el de las
        # estrellas.
        self._play_cue("egg_prize")
        _overlay, content = self._open_overlay()
        # Más bajo que el de una estrella: acá abajo va una nota de cuatro
        # renglones y una firma, y con el lienzo de siempre el texto quedaba
        # arrinconado contra el borde de la ventana.
        canvas = self._celebration_canvas(content, height=230)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.pack(fill="x")

        def reveal() -> None:
            if not holder.winfo_exists():
                return
            heading = ctk.CTkLabel(holder, text=tr("TÍTULO SECRETO"),
                                   font=scaled(("Segoe UI Semibold", 15)),
                                   text_color=GOLD)
            heading.pack()
            start_shimmer(heading, period=70)
            name = ctk.CTkLabel(holder, text=tr(eggs.SECRET_TITLE),
                                font=scaled(("Segoe UI Semibold", 28)),
                                text_color=GOLD)
            name.pack(pady=(6, 10))
            start_shimmer(name, period=70)
            ctk.CTkLabel(holder, text=tr(eggs.SECRET_NOTE),
                         font=scaled(("Georgia", 16, "italic")),
                         text_color=TEXT_NORMAL, wraplength=560,
                         justify="center").pack(pady=(2, 0))
            # La firma va con la letra de las anotaciones a mano del libro:
            # es la misma voz. En dorado lleno y no apagado: es lo último
            # que se lee y estaba quedando al borde de no verse.
            signature = ctk.CTkLabel(holder, text=tr(eggs.SECRET_SIGNATURE),
                                     font=scaled(FONT_HAND), text_color=GOLD)
            signature.pack(pady=(14, 0))
            start_shimmer(signature, period=90)
            ctk.CTkButton(holder, text=tr("Seguir"), width=180, height=42,
                          font=scaled(("Segoe UI Semibold", 14)),
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=self._close_overlay).pack(pady=(22, 0))

        self._animate_egg(canvas, 46, reveal)

    def _animate_egg(self, canvas, frames: int, on_done, frame: int = 0) -> None:
        """
        El huevo que crece, se tambalea, se raja y se abre en dos.

        Termina **con algo puesto**: las dos mitades a un lado y otro y una
        estrella dorada en el medio, que se queda. La primera versión
        estallaba en rayos que se apagaban contra el fondo, así que el
        último cuadro era un rectángulo negro vacío encima del texto ---
        justo el momento en el que hay que leer el título.

        Mismo costo que la estrella de los logros: un puñado de figuras por
        cuadro sobre un lienzo que no tiene nada más.
        """
        import math

        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        position = min(1.0, frame / max(1, frames))
        cx = float(canvas.cget("width")) / 2
        cy = float(canvas.cget("height")) / 2
        canvas.delete("egg")

        grow = min(1.0, position / 0.28)
        size = 84 * (1 - (1 - grow) ** 3)
        # El tambaleo: el huevo se mueve de lado, no gira. Tk no rota nada.
        sway = 0.0
        if 0.28 < position < 0.6:
            sway = 9 * math.sin((position - 0.28) * 46)
        rx, ry = size * 0.62, size * 0.86
        x = cx + sway
        opening = max(0.0, (position - 0.68) / 0.32)

        if size > 1:
            # Las dos mitades. Hasta que se abre son un óvalo entero; desde
            # ahí, dos arcos que se separan.
            lift = 34 * opening
            drop = 14 * opening
            shell = mix(GOLD, GOLD_DIM, opening)
            if opening <= 0.0:
                canvas.create_oval(x - rx, cy - ry, x + rx, cy + ry,
                                   fill=GOLD, outline=GOLD_DIM, width=2,
                                   tags="egg")
                canvas.create_oval(x - rx * 0.44, cy - ry * 0.62,
                                   x - rx * 0.04, cy - ry * 0.16,
                                   fill="#FFF8E0", outline="", tags="egg")
            else:
                canvas.create_arc(x - rx, cy - ry - lift, x + rx,
                                  cy + ry - lift, start=0, extent=180,
                                  style=tk.CHORD, fill=shell,
                                  outline=GOLD_DIM, width=2, tags="egg")
                canvas.create_arc(x - rx, cy - ry + drop, x + rx,
                                  cy + ry + drop, start=180, extent=180,
                                  style=tk.CHORD, fill=shell,
                                  outline=GOLD_DIM, width=2, tags="egg")
            if 0.52 < position and opening <= 0.0:
                # La rajadura, dibujada de izquierda a derecha.
                share = min(1.0, (position - 0.52) / 0.16)
                points, steps = [], 8
                for index in range(steps + 1):
                    if index / steps > share:
                        break
                    x_point = x - rx + (2 * rx) * index / steps
                    points.extend((x_point, cy + (-1) ** index * ry * 0.16))
                if len(points) >= 4:
                    canvas.create_line(*points, fill="#3A2F14", width=3,
                                       tags="egg")

        if opening > 0.0:
            # Los rayos salen y se apagan; la estrella crece y se queda.
            for index in range(12):
                angle = index * math.pi / 6
                near = size * (0.5 + 1.2 * opening)
                far = near + size * 0.55 * (1 - opening)
                if far > near:
                    canvas.create_line(
                        cx + near * math.cos(angle), cy - near * math.sin(angle),
                        cx + far * math.cos(angle), cy - far * math.sin(angle),
                        fill=mix(GOLD, VEIL, opening),
                        width=max(1, int(5 * (1 - opening))), tags="egg")
            eased = 1 - (1 - opening) ** 3
            star = 62 * eased
            if star > 1:
                canvas.create_polygon(
                    star_polygon(cx, cy, star, star * 0.42,
                                 rotation=(1 - eased) * math.pi),
                    fill=GOLD, outline="", tags="egg")

        if frame >= frames:
            on_done()
            return
        canvas.after(24, lambda: self._animate_egg(
            canvas, frames, on_done, frame + 1))

    def _egg_counter(self, master) -> None:
        """
        El contador dorado al pie de los logros.

        Dice cuántos van y cuántos hay, y nunca cuáles: un huevo que se
        anuncia deja de ser un huevo. Completo, el huevo late y se puede
        tocar --- ahí está el título.
        """
        found, total = self.eggs.count(), eggs.TOTAL
        complete = self.eggs.complete()

        panel = ctk.CTkFrame(master, fg_color=SURFACE_LIGHT, corner_radius=11)
        panel.pack(fill="x", pady=(20, 6))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        icon = ctk.CTkLabel(row, text="🥚", font=scaled(("Segoe UI Emoji", 26)),
                            text_color=GOLD if found else GOLD_DIM)
        icon.pack(side="left", padx=(2, 10))
        caption = ctk.CTkLabel(row, text=tr("Huevos de pascua"),
                               font=scaled(("Segoe UI Semibold", 14)),
                               text_color=GOLD if found else TEXT_MUTED)
        caption.pack(side="left")
        count = ctk.CTkLabel(row, text=f"{found} / {total}",
                             font=scaled(("Segoe UI Semibold", 16)),
                             text_color=GOLD if found else TEXT_MUTED)
        count.pack(side="right", padx=(0, 4))

        if not complete:
            Tooltip(panel, tr("Hay cosas que el programa hace y no cuenta."))
            return

        note = ctk.CTkLabel(
            panel,
            text=(tr("Los encontraste todos. Tocá el huevo."
                     if not self.eggs.claimed
                     else trf("Título obtenido: {SECRET_TITLE}.",
                              SECRET_TITLE=eggs.SECRET_TITLE))),
            font=FONT_SMALL, text_color=GOLD_DIM)
        note.pack(anchor="w", padx=18, pady=(0, 12))
        for widget in (icon, count, caption):
            start_shimmer(widget)
        bind_deeply(descendants(panel), "<Button-1>",
                    lambda _event: self._claim_secret_title())

    def _egg_guide(self, master) -> None:
        """
        Los seis huevos con los pasos exactos, y sólo después de la entidad.

        Es lo contrario de todo lo que este programa hace con los huevos ---
        el contador dice cuántos hay y jamás cuáles --- y por eso hace falta
        que algo lo justifique. Lo justifica el cien por ciento de los
        logros: llegado ese punto ya no queda nada que arruinar, el usuario
        encontró todo lo que había para encontrar, y lo único que le sigue
        sirviendo es poder mostrárselos a otro.

        Los que todavía le falten se listan igual. A esta altura no es una
        pista: es una lista de pendientes.
        """
        if not self.visits.saw(visitors.WATCHER_ALL):
            return
        panel = ctk.CTkFrame(master, fg_color=SURFACE_LIGHT, corner_radius=11)
        panel.pack(fill="x", pady=(10, 18))
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 2))
        title = ctk.CTkLabel(head, text=tr("Cómo se hace cada uno"),
                             font=scaled(("Segoe UI Semibold", 14)),
                             text_color=GOLD)
        title.pack(side="left")
        start_shimmer(title)
        ctk.CTkLabel(head, text=tr("lo dejó quien estuvo mirando"),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(side="left", padx=10)
        for egg in eggs.CATALOG:
            found = self.eggs.has(egg.key)
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(8, 0))
            ctk.CTkLabel(row, text="🥚" if found else "○",
                         font=scaled(("Segoe UI Emoji", 14)),
                         text_color=GOLD if found else TEXT_MUTED,
                         width=28).pack(side="left", anchor="n")
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=tr(egg.name),
                         font=scaled(("Segoe UI Semibold", 12)),
                         text_color=GOLD_DIM if found else TEXT_NORMAL,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(text, text=tr(egg.recipe), font=FONT_SMALL,
                         text_color=TEXT_MUTED, wraplength=760,
                         justify="left", anchor="w").pack(anchor="w")
        ctk.CTkLabel(panel, text="", height=6).pack()

    # -- la ventana de logros -----------------------------------------------

    def _screen_achievements(self, _payload=None) -> None:
        tracker = self.achievements
        earned = tracker.stars()
        done, total = tracker.total_progress()

        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(header, text=tr("Logros"),
                     font=scaled(("Georgia", 22, "bold"))).pack(side="left")
        ctk.CTkLabel(header, text=trf("{done} de {total}",
                                      done=done, total=total), font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left", padx=12)
        stars_row = ctk.CTkFrame(header, fg_color="transparent")
        stars_row.pack(side="right")
        for star in range(1, achievements.STAR_COUNT + 1):
            got = star <= earned
            ctk.CTkLabel(stars_row, text="★" if got else "☆",
                         font=scaled(("Segoe UI", 30)),
                         text_color=GOLD if got else GOLD_DIM
                         ).pack(side="left", padx=4)

        # El título de los huevos de pascua se muestra junto a los otros: es
        # un título, y una vez cobrado ya no tiene nada que esconder.
        titles = tracker.titles() + self.eggs.titles()
        keepsakes = [story.PATHS[k] for k in self.story.keepsakes
                     if k in story.PATHS]
        # Lo que dejó la entidad. No sale de ningún sendero, así que no es un
        # `Path`: es un icono y un nombre, y nada más.
        relics = self.visits.keepsakes()
        if titles or keepsakes or relics or self.story.path_key:
            strip = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT,
                                 corner_radius=11)
            strip.pack(fill="x", pady=(2, 8))
            ctk.CTkLabel(strip, text=tr("Títulos"), font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(anchor="w", padx=14,
                                                     pady=(10, 0))
            line = ctk.CTkFrame(strip, fg_color="transparent")
            line.pack(fill="x", padx=14, pady=(2, 12))
            for name in titles:
                label = ctk.CTkLabel(line, text=tr(name),
                                     font=scaled(("Segoe UI Semibold", 17)),
                                     text_color=GOLD)
                label.pack(side="left", padx=(0, 18))
                start_shimmer(label)
            if not titles:
                ctk.CTkLabel(line, text=tr("Todavía ninguno."), font=FONT_SMALL,
                             text_color=TEXT_MUTED).pack(side="left")
            # Lo que entregaron los personajes del sendero. No son logros ni
            # dan nada: son la marca de haber llegado hasta el final de un
            # camino, y por eso viven al lado de los títulos y no en el
            # listado.
            for path in keepsakes:
                mark = ctk.CTkLabel(
                    line, text=f"{path.keepsake_icon}  {path.keepsake}",
                    font=scaled(("Georgia", 14)), text_color=GOLD_DIM)
                mark.pack(side="left", padx=(18, 0))
                Tooltip(mark, trf("Recuerdo de {lower}.",
                                  lower=path.name.lower()))
                # Sólo se muestran los recuerdos de los caminos terminados,
                # así que acá el nombre ya no es un spoiler: es el premio.
            for icon, name in relics:
                relic = ctk.CTkLabel(line, text=f"{icon}  {name}",
                                     font=scaled(("Georgia", 14)),
                                     text_color=GOLD_DIM)
                relic.pack(side="left", padx=(18, 0))
                Tooltip(relic, tr("No se llega a leer de quién es, ni de qué."))
            # El arrepentimiento: volver a la encrucijada y elegir de nuevo.
            # Va acá, junto a los títulos, porque es donde se ve lo que un
            # sendero dejó --- y por lo tanto lo que se estaría cambiando.
            if self.story.path_key:
                ctk.CTkButton(
                    line, text=tr("Arrepentirse"), width=140, height=32,
                    corner_radius=9, font=FONT_SMALL,
                    fg_color="transparent", border_width=1,
                    border_color=GOLD_DIM, text_color=GOLD_DIM,
                    hover_color=SURFACE, command=self._repent
                    ).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True, pady=(4, 6))

        ordinals = {1: N("Primera estrella"), 2: N("Segunda estrella"),
                    3: N("Tercera estrella")}
        for star in range(1, achievements.STAR_COUNT + 1):
            got, needed = tracker.star_progress(star)
            head = ctk.CTkFrame(scroll, fg_color="transparent")
            head.pack(fill="x", pady=(14, 4))
            complete = star <= earned
            ctk.CTkLabel(head, text="★" if complete else "☆",
                         font=scaled(("Segoe UI", 20)),
                         text_color=GOLD if complete else GOLD_DIM
                         ).pack(side="left", padx=(4, 8))
            ctk.CTkLabel(head, text=tr(ordinals[star]),
                         font=scaled(("Segoe UI Semibold", 16))).pack(side="left")
            note = trf("{got} de {needed}", got=got, needed=needed)
            if got == needed and not complete:
                # Está llena pero la anterior no: la estrella no se entrega
                # hasta que la de abajo cierre, y decirlo evita que parezca
                # que el programa se olvidó de dársela.
                note += tr(" · falta la estrella anterior")
            ctk.CTkLabel(head, text=note, font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(side="left", padx=12)
            # Un solo panel redondeado por estrella, con las filas adentro
            # separadas por una línea. Antes cada logro era su propia tarjeta
            # -- cuarenta y pico de rectángulos redondeados, que es de donde
            # salía casi todo el tiempo que tardaba en abrirse esta pantalla.
            panel = ctk.CTkFrame(scroll, fg_color=SURFACE_LIGHT,
                                 corner_radius=11)
            panel.pack(fill="x")
            keys = achievements.STAR_KEYS[star]
            for position, key in enumerate(keys):
                self._achievement_row(panel, achievements.BY_KEY[key],
                                      first=position == 0,
                                      last=position == len(keys) - 1)

        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", pady=(20, 4))
        legend = ctk.CTkLabel(head, text=tr("Legendarios"),
                              font=scaled(("Segoe UI Semibold", 16)),
                              text_color=GOLD)
        legend.pack(side="left", padx=(4, 0))
        start_shimmer(legend)
        panel = ctk.CTkFrame(scroll, fg_color=SURFACE_LIGHT, corner_radius=11)
        panel.pack(fill="x")
        for position, key in enumerate(achievements.LEGENDARY_KEYS):
            self._achievement_row(panel, achievements.BY_KEY[key],
                                  first=position == 0,
                                  last=position == len(achievements.LEGENDARY_KEYS) - 1)

        # Al pie de todo, el contador de huevos de pascua --- y debajo la
        # lista entera, si la entidad ya vino a dejarla.
        self._egg_counter(scroll)
        self._egg_guide(scroll)

        # Y recién ahora, con las filas ya pintadas, lo conseguido se da por
        # visto: la marca de recién completado dura hasta que el usuario
        # abre esta pantalla, no hasta que la cierra. Igual que el azul del
        # índice del libro, que se apaga cuando el texto se escribe.
        self.achievements.mark_seen()

    def _achievement_row(self, master, achievement, first: bool = False,
                         last: bool = False) -> None:
        """
        Una línea del listado: conseguido en color, pendiente apagado.

        Hecha con widgets de tkinter pelado y no de customtkinter. Son
        cuarenta y pico de filas y cada widget de customtkinter dibuja su
        propio rectángulo redondeado sobre un canvas propio: medido, las
        mismas cuarenta filas tardan 271 ms hechas con `CTk` y 48 ms hechas
        así. Las esquinas redondeadas las pone el panel que las agrupa, una
        sola vez por estrella, en vez de una por fila.
        """
        unlocked = self.achievements.has(achievement.key)
        # Lo que se ganó y todavía no se vino a mirar. El aviso de arriba a
        # la izquierda dura unos segundos y se lo puede perder cualquiera
        # --- una corrida puede cerrar media docena de logros de golpe ---,
        # así que la marca espera acá hasta que el usuario venga.
        recent = unlocked and self.achievements.is_fresh(achievement.key)
        gold = achievement.legendary
        # Las filas van metidas hacia adentro: son rectángulos rectos y el
        # panel que las contiene tiene las esquinas redondeadas, así que sin
        # este margen la primera y la última se las comerían.
        if not first:
            tk.Frame(master, bg=BORDER_SOFT, height=1).pack(fill="x", padx=12)
        row = tk.Frame(master, bg=SURFACE_LIGHT)
        row.pack(fill="x", padx=12, pady=(9 if first else 0, 9 if last else 0))
        row.grid_columnconfigure(1, weight=1)

        tk.Label(row, text="✔" if unlocked else "○",
                 font=scaled(("Segoe UI", 13)), bg=SURFACE_LIGHT,
                 fg=(GOLD if gold and unlocked
                     else OK_GREEN if unlocked else TEXT_MUTED),
                 width=3).grid(row=0, column=0, sticky="w", padx=(2, 0),
                               pady=(9, 0))
        name = tk.Label(
            row, text=tr(achievement.name), anchor="w", bg=SURFACE_LIGHT,
            font=scaled(("Segoe UI Semibold", 13)),
            fg=(GOLD if gold and unlocked
                else TEXT_NORMAL if unlocked else TEXT_MUTED))
        name.grid(row=0, column=1, sticky="w", pady=(9, 0))
        if gold and unlocked:
            start_shimmer(name, option="fg")
        if gold and achievement.title:
            tk.Label(row,
                     text=(trf("título: {title}",
                               title=tr(achievement.title)) if unlocked
                           else tr("título dorado")),
                     font=scaled(FONT_SMALL), bg=SURFACE_LIGHT,
                     fg=GOLD if unlocked else GOLD_DIM
                     ).grid(row=0, column=2, sticky="e",
                            padx=(8, 0 if recent else 16), pady=(9, 0))
        if recent:
            # En el mismo azul que el índice del libro usa para lo que
            # todavía no se leyó: en este programa el azul es «esto es
            # nuevo», y el oro ya dice otra cosa.
            tk.Label(row, text=tr("recién completado"),
                     font=scaled(("Segoe UI Semibold", 10)),
                     bg=SURFACE_LIGHT, fg=NOTE_BLUE
                     ).grid(row=0, column=3, sticky="e", padx=(8, 16),
                            pady=(9, 0))
        # Los legendarios van en itálica y no cuentan cómo se consiguen.
        italic = ("Segoe UI", 10, "italic") if gold else ("Segoe UI", 10)
        pieces = achievements.runs(tr(achievement.description))
        if len(pieces) == 1:
            tk.Label(row, text=tr(achievement.description), font=scaled(italic),
                     bg=SURFACE_LIGHT, fg=TEXT_MUTED, wraplength=740,
                     justify="left", anchor="w"
                     ).grid(row=1, column=1, columnspan=3, sticky="w",
                            pady=(1, 10))
            return
        # Con una parte en negrita hacen falta dos etiquetas o más, una por
        # tramo, en fila. Sin envolver: los tramos se cortarían cada uno por
        # su cuenta y la frase quedaría escalonada. Es una descripción corta
        # --- la negrita se usa para señalar una palabra, no un párrafo ---
        # así que entra en el renglón.
        line = tk.Frame(row, bg=SURFACE_LIGHT)
        line.grid(row=1, column=1, columnspan=3, sticky="w", pady=(1, 10))
        for text, strong in pieces:
            font = (("Segoe UI Semibold", 10) + italic[2:]) if strong else italic
            tk.Label(line, text=tr(text), font=scaled(font), bg=SURFACE_LIGHT,
                     fg=TEXT_NORMAL if strong else TEXT_MUTED,
                     justify="left", anchor="w").pack(side="left")

    # -- el experimentador de armónicos --------------------------------------
    #
    # Pantalla propia, a la que se entra desde la tarjeta de al lado de la de
    # logros. No es un paso del carrusel --- ése es un trabajo con principio
    # y final: elegir, escribir, buscar, exportar --- sino una mesa para
    # probar cosas, igual que el libro y el historial, y por eso entra como
    # desvío y sale al mismo lugar del que vino.
    #
    # El widget entero está en `spectrum.py`, con los colores por parámetro
    # igual que `staff.py`: la síntesis vive en `engine/harmonics.py` y acá
    # queda sólo el enganche --- qué logro entrega y quién viene a los tres
    # sonidos.

    def _screen_lab(self, _payload=None) -> None:
        """El experimentador de armónicos, a pantalla completa."""
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text=tr("Experimentador de armónicos"),
                     font=scaled(("Georgia", 22, "bold"))).pack(side="left")
        ctk.CTkLabel(header,
                     text=tr("apagá, subí o desafiná los armónicos de una "
                             "nota"),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(side="left", padx=12)

        # Centrado y con un ancho máximo: el gráfico se lee por proporciones
        # --- doce barras igualmente espaciadas --- y estirado a lo ancho de
        # una pantalla grande las barras quedan tan separadas que se deja de
        # ver que forman una serie.
        #
        # Con scroll, y es la única pantalla del programa que lo necesita: el
        # panel mide lo que miden sus partes --- el gráfico no se achica,
        # porque una barra necesita recorrido vertical para poder
        # arrastrarse --- así que en una ventana baja no entra. Sin esto, lo
        # último de la columna izquierda quedaba cortado por el borde y no
        # había manera de llegar a ello.
        host = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        host.pack(fill="both", expand=True)
        host.grid_columnconfigure(0, weight=1)
        host.grid_columnconfigure(1, weight=0, minsize=self.LAB_WIDTH)
        host.grid_columnconfigure(2, weight=1)
        host.grid_rowconfigure(0, weight=1)
        self.lab = spectrum.Experimenter(
            host,
            colours={"panel": SURFACE_LIGHT, "surface": SURFACE,
                     "text": TEXT_NORMAL, "muted": TEXT_MUTED,
                     "accent": ACCENT, "accent_hover": ACCENT_HOVER,
                     "gold": GOLD, "gold_dim": GOLD_DIM,
                     "border": BORDER_SOFT,
                     # Un gris entre el apagado y el fondo, para los
                     # rotulitos que encabezan un grupo de mandos: con
                     # `border` no se leían y con `muted` competían con lo
                     # que rotulan.
                     "faint": mix(TEXT_MUTED, SURFACE_LIGHT, 0.42),
                     # Las fuentes del widget pasan por el mismo escalador
                     # que las de la aplicación, así que la preferencia de
                     # tamaño de letra también lo agranda a él.
                     "font": scaled},
            on_experiment=self._experimented,
            on_instrument=self._use_instrument)
        # `new` y no `n`: que ocupe el ancho entero de su columna. Con
        # `n` el panel medía lo que pedían sus partes y quedaba más
        # angosto que el lugar reservado.
        self.lab.grid(row=0, column=1, sticky="new")

    #: Ancho de la columna del experimentador. Es lo que mide su gráfico con
    #: las doce barras separadas y legibles; por debajo se amontonan y deja
    #: de poderse agarrar una sola con el mouse.
    LAB_WIDTH = 1140

    def _screen_analysis(self, piece=None) -> None:
        """El analizador, a pantalla completa.

        ``piece`` es una opción del resultado que llega ya escrita (ver
        `_analyse_option`); sin ella el sistema arranca vacío."""
        # Se entrega al abrirlo y no al analizar algo: el logro premia haber
        # encontrado la puerta, igual que el del experimentador.
        self._award({"analyser_first"})
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text=tr("Analizador"),
                     font=scaled(("Georgia", 22, "bold"))).pack(side="left")
        ctk.CTkLabel(header,
                     text=(trf("la opción {position} del resultado",
                               position=piece.position) if piece is not None
                           else tr("escribí o importá una partitura para "
                                   "analizarla")),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(side="left", padx=12)

        self.analyzer = analyzer.Analyzer(
            self.body,
            colours={"panel": SURFACE_LIGHT, "surface": SURFACE,
                     "text": TEXT_NORMAL, "muted": TEXT_MUTED,
                     "accent": ACCENT, "accent_hover": ACCENT_HOVER,
                     "gold": GOLD, "gold_dim": GOLD_DIM, "warn": WARN,
                     "border": BORDER_SOFT,
                     # El resaltado del acorde elegido: un gris apenas por
                     # encima del fondo del sistema. Con el acento pleno la
                     # banda tapaba las notas que justamente hay que mirar.
                     "glow": mix(SURFACE_LIGHT, ACCENT, 0.18),
                     "faint": mix(TEXT_MUTED, SURFACE_LIGHT, 0.42),
                     "font": scaled},
            key_signatures=self.KEY_SIGNATURES,
            # Traer una partitura de afuera es el mismo logro acá que en los
            # otros modos. No se inventa uno nuevo: el analizador es una
            # herramienta de lectura, no otra manera de juntar estrellas.
            #
            # Y por lo mismo, escuchar, exportar, poner un silencio y leer
            # lo que hay escrito valen acá lo que valen allá: un logro que
            # premia haber hecho algo se gana haciéndolo, sin importar en
            # qué pantalla estaba uno.
            on_imported=lambda: self._award({"import_score"}),
            on_played=lambda: self._award({"first_playback"}),
            on_exported=lambda: self._award({"first_export"}),
            on_rest=lambda: self._award({"first_rest"}),
            on_analysed=self._analysed)
        self.analyzer.pack(fill="both", expand=True)
        if piece is not None:
            self.analyzer.load_piece(piece.lines, piece.fifths, piece.metres,
                                     genre=piece.genre)

    def _analysed(self, result) -> None:
        """El analizador terminó de leer una partitura.

        Lo que encontró son los mismos hechos que el catálogo premia --- una
        séptima, un disminuido, un ii-V, unas quintas paralelas --- y no hay
        motivo para que valgan sólo cuando los escribe el algoritmo. Lo que
        no sale de acá son los logros que hablan de cómo se hizo la pieza:
        acá no se eligió género, ni reglas, ni voces.
        """
        self._award(achievements.inspect_analysis(result,
                                                  self.achievements.pending()))

    def _experimented(self, fresh: bool) -> None:
        """
        Alguien tocó un sonido en el experimentador.

        ``fresh`` es que la configuración no sea la misma que sonó la vez
        anterior. El logro lo entrega cualquier sonido --- con haber abierto
        esto y apretar «Escuchar» ya se usó ---, pero la cuenta que trae al
        creador sólo avanza con los distintos: apretar tres veces el mismo
        botón no es haber experimentado tres veces.
        """
        self._award({"harmonics_first"})
        if not fresh:
            return
        for key in self.visits.record_experiment():
            self._open_visit(key)

    # -- la escuelita ---------------------------------------------------------
    #
    # Pantalla propia, igual que el analizador y el experimentador, y por el
    # mismo motivo es un desvío y no un paso del carrusel. El widget entero
    # está en `school.py` y lo que se enseña y cómo se corrige en
    # `engine/school.py`; acá queda el enganche: qué colores, qué logros
    # entrega lo que el alumno escribe, cómo se abre el libro en la página
    # citada y la graduación.

    def _screen_school(self, _payload=None) -> None:
        """La escuelita, a pantalla completa."""
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text=tr("Escuelita"),
                     font=scaled(("Georgia", 22, "bold"))).pack(side="left")
        ctk.CTkLabel(header,
                     text=tr("ejercicios de escritura corregidos por el "
                             "analizador"),
                     font=FONT_SMALL, text_color=TEXT_MUTED
                     ).pack(side="left", padx=12)
        self.school_screen = school.School(
            self.body,
            colours={"panel": SURFACE_LIGHT, "surface": SURFACE,
                     "raised": SURFACE_RAISED, "text": TEXT_NORMAL,
                     "muted": TEXT_MUTED,
                     "faint": mix(TEXT_MUTED, SURFACE, 0.45),
                     "accent": ACCENT, "accent_hover": ACCENT_HOVER,
                     "gold": GOLD, "gold_dim": GOLD_DIM, "ok": OK_GREEN,
                     "error": ERROR, "border": BORDER_SOFT,
                     "glow": mix(SURFACE_LIGHT, ACCENT, 0.18),
                     # La cita del libro se dibuja con los colores del
                     # libro: se tiene que leer como el libro hablando, no
                     # como la escuelita resumiendo.
                     "paper": PAPER, "paper_edge": PAPER_EDGE, "ink": INK,
                     "ink_muted": INK_MUTED, "ink_faint": INK_FAINT,
                     "rule": RULE, "font": scaled},
            progress=self.school, memory=self.school_memory,
            entry_written=self._lore_unlocked,
            on_book=self._open_book_at,
            on_lab=lambda: self._open_detour("lab"),
            on_analysed=self._analysed,
            on_played=lambda: self._award({"first_playback"}),
            on_finished=self._open_graduation)
        self.school_screen.pack(fill="both", expand=True)
        # Si la ceremonia quedó a medias ---se cerró el programa en el
        # medio---, vuelve a esperar acá: la graduación se marca al terminar
        # la escena, no al aprobar el último ejercicio.
        if self.school.graduation_due():
            self.after(900, self._open_graduation)

    def _open_book_at(self, key: str) -> None:
        """Abrir el libro en una entrada, encima de lo que se estaba haciendo.

        No reemplaza el desvío: «Volver» tiene que devolver a la lección que
        citó la entrada, con el ejercicio como estaba.
        """
        self._open_detour("book", payload=key)

    #: Los ruidos de la graduación: los de los tres que vienen.
    GRADUATION_SOUNDS = ("plainchant", "blip_gregory", "clavier", "blip_bach",
                         "blip_creator")

    def _open_graduation(self) -> None:
        """
        La graduación: tres escenas seguidas, de un solo pestañeo largo.

        Se encolan juntas en la misma cola de las visitas, así la cola hace
        lo que ya sabe hacer: la pantalla no vuelve al programa entre una y
        otra, y lo que hay que hacer al final ---la marca, el logro--- se
        hace cuando termina la **última**.
        """
        if getattr(self, "_graduation_queued", False):
            return
        if self.settings.get("professional"):
            # Sin la ceremonia, pero con lo que deja: la escuelita queda
            # terminada y el logro es del que hizo los ejercicios.
            self._graduated()
            return
        if (self.scene is not None or self.overlay is not None
                or self.celebrations):
            # Hay otra cosa a pantalla completa ---una escena, la animación
            # de una estrella---: dos cosas encima de la ventana se tapan
            # entre sí. Se vuelve a preguntar cuando la pantalla quede libre.
            self.after(1500, self._open_graduation)
            return
        self._graduation_queued = True
        scenes = curriculum.GRADUATION
        for position, (speaker, lines, name, dream) in enumerate(scenes):
            for sound in self.VISIT_SOUNDS.get(speaker, ()):
                ambience.summon(sound)
            last = position == len(scenes) - 1
            self._queue_scene(
                speaker, lines, reveal_name=name,
                title=curriculum.GRADUATION_TITLE, dream=dream,
                after=self._graduated if last else None)
        self._when_sounds(self.GRADUATION_SOUNDS, self._advance_scenes)

    def _graduated(self) -> None:
        """
        La ceremonia terminó: recién ahora se da por vista y se entrega el
        logro, igual que en las visitas. Cerrar el programa en el medio no
        le cuesta al usuario la escena.
        """
        self._graduation_queued = False
        self.school.mark_graduated()
        self._award([curriculum.AWARD])
        screen = getattr(self, "school_screen", None)
        if screen is not None:
            try:
                screen._draw_trail()
            except tk.TclError:
                pass

    # -- el modo historia ---------------------------------------------------
    #
    # El relato no es una pantalla: es una capa encima de las que ya existen.
    # Un sendero pide siempre las mismas tres cosas en los mismos tres modos
    # --- una progresión escrita a mano en el Organizador, un botón dorado en
    # el Generador y un gesto dorado en el Armonizador --- y todo lo demás
    # del programa sigue funcionando igual mientras tanto.
    #
    # Las cinemáticas van en `cinematic.py`, los ruidos en `engine/ambience`
    # y el guion en `engine/story`. Lo que vive acá es sólo el pegamento:
    # cuándo aparece una escena, qué la desbloquea y qué pantalla la ofrece.

    #: Cada cuánto se pregunta si corresponde que la figura aparezca. La
    #: pregunta es barata --- media docena de comparaciones --- así que
    #: preguntarla seguido no cuesta nada, y con un intervalo largo la
    #: aparición se corría hasta medio minuto respecto del momento en que
    #: efectivamente correspondía.
    STORY_POLL_MS = 4000

    def _prepare_story_sound(self) -> None:
        """Sintetizar los ruidos de la historia, en un hilo aparte."""
        try:
            ambience.prepare()
        except Exception:                                   # noqa: BLE001
            pass          # el sonido es decoración: nunca puede romper nada

    def _watch_story(self) -> None:
        """
        Preguntar, cada tanto, si es momento de que aparezca la figura.

        La condición no es sólo el tiempo: tiene que estar la pantalla
        inicial a la vista, el tutorial terminado, ninguna búsqueda corriendo
        y ningún panel abierto. Interrumpir a alguien en la mitad de cargar
        una progresión sería exactamente lo contrario de lo que la escena
        quiere producir.
        """
        self._story_watching = False
        if not self.story_offers or self.settings.get("professional"):
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        # Si ya hay un sendero elegido no hay nada que vigilar, y el vigía se
        # apaga acá a propósito. Escrito al revés ---con el re-agendado
        # adentro del `if`--- decía lo mismo por accidente: cualquier turno en
        # que `may_offer()` diera `False` mataba el vigía para siempre, y
        # bastaba con que algún día la condición dejara de ser definitiva para
        # que el modo historia no volviera a aparecer nunca sin que nada
        # fallara.
        if not self.story.may_offer():
            return
        # La espera de cinco minutos se paga una sola vez en la vida del
        # programa. Si la figura ya se apareció y el sendero sigue vacío
        # ---la cinemática se cortó por la mitad, o el usuario se
        # arrepintió--- el llamado vuelve en cuanto haya un momento
        # tranquilo: volver a hacerlo esperar por un suspenso que ya se
        # gastó es exactamente lo que se siente como que el relato se
        # perdió para siempre.
        if self._story_quiet() and (
                self.story.seen_offer
                or time.monotonic() - self._story_since >= story.delay_seconds()):
            # **No se abre la escena.** Se enciende un botón en la
            # pantalla inicial y se lo deja esperando ahí. Aparecer de
            # golpe encima de lo que el usuario estuviera mirando era la
            # única cosa del programa que le sacaba el control de las
            # manos, y encima obligaba a que el vigía se asegurara de que
            # el momento fuera tranquilo --- con el botón, el momento lo
            # elige él.
            self._story_knocking = True
            self._render()
            return
        self._rearm_story_watch()

    def _rearm_story_watch(self, delay: Optional[int] = None) -> None:
        """
        Encender el vigía del ofrecimiento, y una sola vez.

        Se re-arma desde tres lugares --- el arranque, su propio turno y el
        arrepentimiento --- y dos cadenas de `after` sueltas preguntarían el
        doble de seguido sin que nada fallara.
        """
        if self._story_watching:
            return
        self._story_watching = True
        self.after(self.STORY_POLL_MS if delay is None else delay,
                   self._watch_story)

    def _story_awaiting(self, mode: str):
        """
        El tramo del sendero que espera algo en este modo, o None.

        Es la pregunta de todas las pantallas al relato, y en el modo
        profesional contesta que no hay ninguno: el sendero queda en pausa
        donde estaba, sin carteles ni teclas doradas.
        """
        if self.settings.get("professional"):
            return None
        return self.story.awaiting(mode)

    def _story_quiet(self) -> bool:
        """¿Está la aplicación en un momento en el que se puede interrumpir?"""
        if self.index != 0 or self.detour:
            return False
        if self.scene is not None or self.overlay is not None:
            return False
        if getattr(self, "config_panel", None) is not None:
            return False
        if getattr(self, "donate_panel", None) is not None:
            return False
        if getattr(self, "tutorial", None) is not None:
            return False
        if not self.settings.get("tutorial_seen"):
            return False
        if self.worker is not None and self.worker.is_alive():
            return False
        return bool(self.toasts) is False

    # -- las escenas --------------------------------------------------------

    def _queue_scene(self, speaker: str, lines, **extra) -> None:
        """Encolar una escena. Se tocan de a una, en orden."""
        lines = list(lines or ())
        if not lines:
            after = extra.get("after")
            if after is not None:
                after()
            return
        self._scene_queue.append(dict(speaker=speaker, lines=lines, **extra))

    def _fade_to_black(self, then) -> None:
        """
        Apagar la ventana antes de abrir una escena.

        La cinemática arranca en negro, pero el salto de la aplicación
        iluminada al negro era de un cuadro y se leía como un corte. Medio
        segundo de fundido lo convierte en una transición --- y es la única
        parte del programa donde se anima el color de un panel entero, que
        es exactamente lo único que Tk hace barato.
        """
        veil = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        veil.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        veil.lift()

        def frame(position: float) -> None:
            try:
                veil.configure(fg_color=mix(SURFACE, "#000000", position))
            except tk.TclError:
                return
            if position >= 1.0:
                then()
                # Se destruye después de que la escena se dibujó encima: al
                # revés se vería la aplicación por un cuadro.
                try:
                    self.after(140, veil.destroy)
                except tk.TclError:
                    pass

        animate(veil, frame, steps=16, period=26)

    def _advance_scenes(self) -> None:
        """
        Tocar la escena que sigue, si no hay ninguna en pantalla.

        Encolar en vez de abrir de una es lo que hace que el cierre de un
        tramo y la apertura del siguiente no se dibujen uno encima del otro
        cuando los dos se disparan en el mismo instante.
        """
        if self.scene is not None or not self._scene_queue:
            return
        entry = dict(self._scene_queue[0])
        # Dos escenas seguidas del mismo personaje son una sola cosa: no se
        # va para volver a entrar, no se cierra la oscuridad en el medio y no
        # se ve la aplicación por debajo. Sólo cambia de tema.
        if entry.get("speaker") == getattr(self, "_scene_speaker", None):
            entry.setdefault("entrance", "present")
            entry.setdefault("opening", False)
        entry.pop("pause", None)
        self._scene_queue.pop(0)
        # Si atrás viene otra escena, ésta no devuelve la pantalla: la deja
        # en negro y la que sigue despierta de ahí. Un pestañeo largo en vez
        # de dos idas y vueltas al programa.
        if self._scene_queue:
            entry["blackout"] = True
        if getattr(self, "_scene_dark", False):
            entry["opening"] = "dark"
        self._scene_dark = bool(self._scene_queue)
        after = entry.pop("after", None)
        speaker = entry.pop("speaker")
        lines = entry.pop("lines")
        # La línea que se lee sobre el negro. La del sendero cambia con el
        # tramo --- la contesta `_story_dream` --- pero una visita trae la
        # suya escrita, porque no hay ningún tramo del que dependa.
        dream = entry.pop("dream", None)

        def done() -> None:
            self.scene = None
            self._scene_speaker = (speaker if self._scene_queue else None)
            # Lo que hay que hacer al terminar --- volver al principio,
            # entregar el logro, avisar de la anotación --- se hace cuando
            # termina la **última** escena de la tanda. Hacerlo entre una y
            # otra devolvía al usuario al programa por un segundo en la mitad
            # de una conversación.
            #
            # Pero se guarda, no se descarta: una escena con algo pendiente
            # puede quedar en el medio de la tanda --- pasa cuando un tramo
            # del sendero y una visita se disparan en la misma corrida --- y
            # tirarlo dejaba al sendero sin volver al principio y sin avisar
            # de lo que había escrito.
            if after is not None:
                self._scene_afters.append(after)
            if not self._scene_queue:
                pending, self._scene_afters = self._scene_afters, []
                for action in pending:
                    action()
            try:
                # Corto: la escena que sigue tiene que estar dibujada antes
                # de que muera la anterior, o entre las dos se ve el
                # programa por un cuadro.
                self.after(60, self._advance_scenes)
            except tk.TclError:
                pass

        self._scene_speaker = speaker

        def open_scene() -> None:
            self.scene = cinematic.speak(
                self, speaker, lines, on_done=done,
                dream=self._story_dream(speaker) if dream is None else dream,
                font_scale=FONT_SCALE, **entry)

        try:
            if entry.get("opening", True) is True:
                self._fade_to_black(open_scene)
            else:
                open_scene()
        except Exception:                                   # noqa: BLE001
            # Una escena que no se puede dibujar no puede dejar al usuario
            # trabado a mitad de un sendero: se la saltea y se sigue.
            #
            # Pero se deja el rastro. Antes se tragaba entera y el tramo
            # desaparecía sin que quedara nada en ninguna parte --- ni un
            # error, ni un log ---, así que desde afuera era idéntico a que
            # el guion no tuviera líneas. El usuario sigue sin ver nada, que
            # es lo correcto; quien esté mirando la consola, sí.
            traceback.print_exc()
            self.scene = None
            done()

    # -- el ofrecimiento ----------------------------------------------------

    def _start_offer(self) -> None:
        if self.scene is not None:
            return
        # Se anota acá y no al contestar: si la escena se corta por la mitad
        # ---la aplicación cerrada, o un cierre a lo bruto--- el llamado
        # tiene que volver enseguida y no dentro de cinco minutos. Que el
        # ofrecimiento haya empezado no da por hecho nada: mientras no haya
        # sendero elegido, `may_offer()` sigue diciendo que sí.
        self.story.mark_offered()
        try:
            # El ofrecimiento no pasa por la cola, así que hay que anotar a
            # mano quién quedó hablando: lo que venga después sigue siendo
            # él, y no tiene que volver a entrar caminando.
            self._scene_speaker = story.DEVIL
            self._fade_to_black(
                lambda: setattr(self, "scene",
                                cinematic.offer(self, self._story_chose,
                                                font_scale=FONT_SCALE)))
        except Exception:                                   # noqa: BLE001
            # Que la escena no se pueda dibujar no puede costarle al usuario
            # el modo historia entero: no se da por hecho el ofrecimiento y
            # se vuelve a intentar en el próximo turno del vigía.
            self.scene = None
            self._rearm_story_watch()

    def _story_chose(self, choice: str) -> None:
        """La respuesta al ofrecimiento: se elige sendero y arranca el relato."""
        self.scene = None
        written = story.unlocked_notes(self.story)
        path_key = self.story.choose(choice)
        path = story.PATHS.get(path_key)
        if path is None:
            return
        # Elegir sendero ya deja escrita la primera anotación: si el aviso
        # esperara al final del primer tramo, el usuario llegaría al botón
        # dorado sin saber que lo que lo enciende ya estaba escrito.
        fresh = story.unlocked_notes(self.story) - written
        # Lo que pasa apenas se contesta --- el señor que se va decepcionado,
        # el señor que arde --- va con él todavía en escena. Recién después
        # entra quien acompaña el sendero.
        aftermath = story.AFTERMATH.get(path_key, ())
        if aftermath:
            # Ignorado, se desvanece; rechazado, arde. Ninguno de los dos
            # se va caminando: una despedida larga es algo que se gana.
            departure = "burn" if path_key == "gospel" else "vanish"
            sky = "ashes" if path_key == "gospel" else "valley"
            self._queue_scene(story.DEVIL, aftermath, departure=departure,
                              sky=sky, entrance="present")
        first = self.story.current
        if first is not None:
            lines = self._story_intro(first)
            if aftermath:
                # El que llega no pisa al que se fue: primero hay un silencio
                # con la escena vacía, y recién después aparece.
                lines = list(story.INTERLUDE) + lines
            self._queue_scene(path.speaker, lines,
                              after=lambda: (self._story_go_home(),
                                             self._story_noted(fresh)),
                              pause=900 if aftermath else 0)
        self._advance_scenes()

    # -- avanzar por el sendero ---------------------------------------------

    def _story_complete_step(self) -> None:
        """
        Dar por hecho el tramo en curso y encadenar lo que sigue.

        El cierre de un tramo y la apertura del siguiente se dicen en **una**
        sola escena: los dos los habla el mismo personaje, y hacerlo irse
        para que vuelva a entrar dos segundos después rompería el hilo.
        """
        path, step = self.story.path, self.story.current
        if path is None or step is None:
            return
        # Avanzar es lo que escribe la anotación, pero el aviso va después
        # de la escena: encima del negro de la cinemática no lo vería nadie.
        written = story.unlocked_notes(self.story)
        self.story.advance()
        fresh = story.unlocked_notes(self.story) - written
        nxt = self.story.current
        if nxt is not None:
            self._queue_scene(path.speaker,
                              list(step.outro) + self._story_intro(nxt),
                              after=lambda: (self._story_go_home(),
                                             self._story_noted(fresh)))
            self._advance_scenes()
            return
        self._queue_scene(
            path.speaker, list(step.outro) + list(path.finale),
            keepsake=(path.keepsake_icon, path.keepsake),
            reveal_name="Django Reinhardt" if path.key == "jazz" else "",
            after=lambda: (self._story_close_path(path),
                           self._story_noted(fresh)))
        self._advance_scenes()

    def _story_dream(self, speaker: str) -> str:
        """
        La línea que se lee sobre el negro, antes de que la escena se abra.

        Cambia con el sendero y con lo que ya pasó, porque su trabajo es
        sostener dos segundos de pantalla vacía: si dijera siempre lo mismo,
        a la tercera vez sería un cartel de carga.
        """
        step = self.story.step if self.story.path is not None else 0
        return story.dream_line(speaker, step)

    def _story_intro(self, step) -> List:
        """
        Lo que el personaje dice al abrir un tramo.

        El relato siempre; el pedido sólo si la traba sigue cerrada. Es muy
        común cumplirla sin querer mientras se juega con el tramo anterior, y
        entonces el personaje pedía algo que ya estaba hecho.
        """
        lines = list(step.intro)
        if step.gate and not self.story.gate_open(step.gate):
            lines += list(step.task)
        return lines

    def _story_go_home(self) -> None:
        """
        Volver al principio al terminar una escena.

        La cinemática se abre encima de donde estuviera el usuario, que casi
        siempre es la pantalla de resultados; al cerrarse lo devolvía ahí, y
        peor: si la corrida ya había terminado, a la pantalla de «buscando
        soluciones» sin nada que buscar. El relato siempre deja al usuario en
        el mismo lugar, que es desde donde arranca el tramo siguiente.
        """
        self.detour.clear()
        self.index = 0
        self.outcome = None
        self.request = None
        self._render()

    def _story_close_path(self, path) -> None:
        """El final: se entrega el legendario que el sendero venía guardando."""
        self._award({path.award})
        self._story_go_home()

    def _story_notice(self, title: str, body: str,
                      heading: str = "El sendero avanza") -> None:
        """Un aviso del relato, con el mismo cartel que usan los logros."""
        self._show_toast(
            achievements.Achievement("", title, body, 0, legendary=True),
            heading_text=heading)

    def _story_noted(self, fresh) -> None:
        """
        El aviso de que el relato dejó algo escrito en el libro.

        Las anotaciones se escriben solas al cruzar un tramo, y son además
        lo que abre la traba del tramo siguiente: sin decirlo, el usuario
        tenía que adivinar que había ido a parar algo al libro, y cuál de
        las dos veces que lo abrió fue la que contó. Se dice **que** se
        anotó y **dónde** leerlo; qué dice, no --- eso es ir a leerlo.
        """
        if not fresh:
            return
        self._story_notice(
            "Anotaste lo que viste",
            ("Hay una entrada nueva en el capítulo del sendero, en el libro "
             "de teoría." if len(fresh) == 1 else
             trf("Hay {fresh} entradas nuevas en el capítulo del sendero, "
                 "en el libro de teoría.",
                 fresh=len(fresh))),
            heading="🖋  Se escribe solo")

    def _story_opened(self, step) -> None:
        """
        El aviso de que una traba cedió.

        No dice qué se destrabó. Nombrarlo acá --- «Los doce compases»,
        «All of Me» --- le contaría al usuario el tramo entero desde un
        cartelito, y lo único que el relato tiene para dar es justamente la
        sorpresa de llegar. Se dice dónde ir y nada más.
        """
        self._story_notice(
            "El camino se ha liberado",
            trf("Algo te está esperando en el {value}.",
                value=tr(self.MODE_NAMES.get(step.where, 'programa'))),
            heading="Se enciende el oro")

    # -- las trabas de los botones dorados ----------------------------------

    def _story_lit_chords(self) -> set:
        """
        Qué acordes escritos forman, ahora mismo, la cadencia del tramo.

        Se recalcula en cada cuadro del brillo, así que tiene que ser
        barato: son media docena de cifrados y un patrón de dos o tres
        acordes. Cuesta menos que el ``configure`` que viene después.
        """
        step = self._story_awaiting("manual")
        if step is None:
            return set()
        gate = story.STEP_GATES.get(step.key, "")
        if not gate:
            return set()
        written = []
        for row in getattr(self, "chord_rows", []):
            for record in row["entries"]:
                if self._is_rest(record):
                    continue
                try:
                    text = record["entry"].get().strip()
                except tk.TclError:
                    return set()
                if text:
                    written.append((id(record), text))
        # Cada acorde encendido vuelve a preguntar, así que sin memoria el
        # cifrado entero se parsearía una vez por acorde y por cuadro. La
        # llave es lo escrito: mientras nadie toque una tecla, la respuesta
        # ya está.
        key = (gate, tuple(text for _mark, text in written))
        cached = getattr(self, "_lit_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        chords, marks = [], []
        for mark, text in written:
            try:
                chords.append(parse_chord(text))
            except ChordParseError:
                continue
            marks.append(mark)
        span = story.matching_span(gate, chords)
        lit = set() if span is None else set(marks[span[0]:span[0] + span[1]])
        self._lit_cache = (key, lit)
        return lit

    def _story_watch_cadence(self, record) -> None:
        """
        Encender el cifrado de un acorde cuando entra en la cadencia.

        El oro que se prende y se apaga es lo que le dice al usuario, sin
        una sola palabra, que lo que acaba de escribir es lo que le pidieron
        --- y se apaga solo si lo desarma.
        """
        if self._story_awaiting("manual") is None:
            return
        shimmer_while(record["entry"],
                      lambda r=record: id(r) in self._story_lit_chords())

    def _story_chords(self, entries) -> List:
        """Los acordes escritos, o nada si alguno no se puede leer."""
        chords = []
        for entry in entries:
            if entry.is_rest:
                continue
            try:
                chords.append(entry.to_chord())
            except ChordParseError:
                return []
        return chords

    def _story_note_progress(self, entries) -> None:
        """
        Anotar lo que una progresión escrita a mano aporta al sendero.

        Corre al confirmar la pantalla de acordes, no al terminar la
        búsqueda: la traba pide escribir la misma cadencia en tres
        tonalidades, y hacer generar tres veces para eso sería pedir otra
        cosa.
        """
        path = self.story.path
        if path is None or self.story.path_key in self.story.finished:
            return
        chords = self._story_chords(entries)
        if not chords:
            return
        for step in path.steps:
            if step.gate not in story.KEY_GATES:
                continue
            before = self.story.gate_open(step.gate)
            if not self.story.note_tonics(
                    step.gate, story.tonics_for_gate(step.gate, chords)):
                continue
            done, needed = self.story.gate_progress(step.gate)
            if self.story.gate_open(step.gate) and not before:
                self._story_opened(step)
            else:
                self._story_notice(
                    trf("{done} de {needed} tonalidades",
                        done=done, needed=needed),
                    step.locked_text + ".",
                    heading="El sendero avanza")

    @unless_professional
    def _story_after_run(self, outcome) -> None:
        """
        ¿La corrida que acaba de terminar completa el tramo a mano?

        Sólo miran acá los tramos del Organizador: los otros dos los dispara
        el botón dorado, que ya sabe qué tramo está cumpliendo.
        """
        step = self._story_awaiting("manual")
        if step is None or outcome is None or not outcome.succeeded:
            return
        gate = story.STEP_GATES.get(step.key, "")
        chords = self._story_chords(getattr(self, "chord_entries", []))
        if not gate or not chords:
            return
        if story.tonics_for_gate(gate, chords):
            self._story_offer_continue()

    # -- lo que se ve en las pantallas --------------------------------------

    #: Cómo se llama cada modo cuando hay que mandar al usuario a uno.
    MODE_NAMES = {"manual": "Organizador", "random": "Generador",
                  "harmonise": "Armonizador"}

    def _story_knock(self, master) -> None:
        """
        Lo que aparece cuando el relato está listo para empezar.

        No dice qué es, no dice qué va a pasar y no se puede adivinar de qué
        se trata: dice que hay algo y que se puede tocar. Todo lo demás ---
        quién, por qué, qué ofrece --- es la escena, y contarlo acá sería
        gastarla en un cartel.

        Brilla como un legendario porque es de esa familia: no es una función
        del programa, es algo que se le apareció al usuario. Y **se queda**.
        Si no lo toca hoy sigue ahí mañana; lo único que el relato no hace
        más es empezar solo.
        """
        panel = ctk.CTkFrame(master, fg_color=SURFACE_LIGHT, corner_radius=16,
                             border_width=2, border_color=GOLD_DIM)
        panel.pack(fill="x", padx=8, pady=(0, 6))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=(18, 12), pady=6)

        mark = ctk.CTkLabel(row, text="✦", font=scaled(("Segoe UI Symbol", 20)),
                            text_color=GOLD)
        mark.pack(side="left", padx=(0, 10))
        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True)
        title = ctk.CTkLabel(texts, text=tr("Hay alguien esperando"),
                             font=scaled(("Georgia", 15, "bold")),
                             text_color=GOLD, anchor="w")
        title.pack(side="left")
        ctk.CTkLabel(texts,
                     text=tr("No golpeó la puerta, no hizo ruido y no se fue. "
                             "Vas a tener que atender vos."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w",
                     justify="left").pack(side="left", padx=(16, 0))
        button = ctk.CTkButton(row, text=tr("Atender"), width=130, height=32,
                               corner_radius=12,
                               font=scaled(("Segoe UI Semibold", 14)),
                               fg_color="transparent", border_width=2,
                               border_color=GOLD, text_color=GOLD,
                               hover_color=SURFACE,
                               command=self._answer_knock)
        button.pack(side="right", padx=(12, 0))
        # El brillo, desfasado entre las tres cosas: recorre el cartel como
        # una ola en vez de prenderse y apagarse todo junto.
        start_shimmer(mark)
        start_shimmer(title, offset=3)
        start_shimmer(button, option="border_color", offset=6)
        start_shimmer(panel, option="border_color", offset=9)
        bind_deeply(descendants(panel), "<Button-1>",
                    lambda _event: self._answer_knock())

    def _answer_knock(self) -> None:
        """Atender. El botón se apaga y la escena empieza."""
        if self.scene is not None:
            return
        self._story_knocking = False
        self._start_offer()

    def _story_banner(self, master) -> None:
        """
        El recordatorio del sendero, en la pantalla inicial.

        Es la única guía permanente que tiene el relato: dice en qué tramo
        está, a qué modo hay que ir y exactamente qué hacer cuando se llegue.
        La consigna está escrita para alguien que no sabe nada de música, que
        es la condición que el resto del programa también se pone.
        """
        path = self.story.path
        if path is None:
            return
        step = self.story.current
        panel = ctk.CTkFrame(master, fg_color=SURFACE_LIGHT, corner_radius=16,
                             border_width=2, border_color=GOLD_DIM)
        # Un solo renglón, debajo del estante: el recuerdo del sendero, su
        # título, lo que hay que hacer y, a la derecha, el tramo. Con las
        # herramientas del mismo tamaño que los modos no entra más que eso
        # en la ventana más chica; el detalle de la consigna va en la ayuda
        # emergente.
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=(18, 20), pady=8)
        ctk.CTkLabel(row, text=path.keepsake_icon,
                     font=scaled(("Segoe UI Symbol", 18)),
                     text_color=GOLD_DIM).pack(side="left", padx=(0, 10))
        title = ctk.CTkLabel(
            row, text=tr(path.title(path.key in self.story.finished)),
            font=scaled(("Georgia", 14, "bold")), text_color=GOLD, anchor="w")
        title.pack(side="left")
        start_shimmer(title)

        if step is None:
            ctk.CTkLabel(row, text=tr("Recorrido hasta el final."),
                         font=scaled(("Segoe UI", 12)), text_color=TEXT_MUTED,
                         anchor="w").pack(side="left", padx=(16, 0))
        else:
            ctk.CTkLabel(
                row, text=trf("Tramo {step} de {total}  ·  en el {where}",
                              step=self.story.step + 1,
                              total=self.story.total_steps(),
                              where=tr(self.MODE_NAMES.get(step.where, ''))),
                font=FONT_SMALL, text_color=TEXT_MUTED, anchor="e"
                ).pack(side="right", padx=(16, 0))
            wrap = max(320, self.winfo_width() - 640)
            if step.gate and not self.story.gate_open(step.gate):
                # Lo único que se pide antes de seguir: leer. Ocupa el lugar
                # de la consigna, que hasta leerlo no se puede cumplir, y va
                # en dorado porque es la acción. Si lo que hay que leer está
                # en el libro, tocarlo lo abre; cómo se cumple, en la ayuda
                # emergente.
                pending = ctk.CTkLabel(
                    row, text=trf("📖  {locked}",
                                  locked=tr(step.locked_text)),
                    font=scaled(("Segoe UI Semibold", 13)), text_color=GOLD,
                    anchor="w", justify="left", wraplength=wrap)
                pending.pack(side="left", padx=(16, 0))
                start_shimmer(pending)
                Tooltip(pending, tr(self._story_gate_how(step)))
                if step.gate in story.BOOK_GATES:
                    pending.configure(cursor="hand2")
                    bind_deeply(descendants(pending), "<Button-1>",
                                lambda _e: self._open_detour("book",
                                                             replace=True))
            else:
                goal = ctk.CTkLabel(row, text=tr(step.goal),
                                    font=scaled(("Segoe UI", 13)),
                                    text_color=TEXT_NORMAL, anchor="w",
                                    justify="left", wraplength=wrap)
                goal.pack(side="left", padx=(16, 0))
                if step.hint:
                    Tooltip(goal, tr(step.hint))
        panel.pack(fill="x", padx=8, pady=(0, 6))

    @unless_professional
    def _story_golden_button(self, master):
        """
        El botón dorado del tramo en curso, si el tramo se juega con uno.

        Aparece siempre que el tramo esté en curso, incluso bloqueado: verlo
        gris y **que él mismo diga qué hay que hacer para encenderlo** es la
        mitad de lo que empuja a seguir. Devuelve el botón, o ``None``.

        Dos condiciones, y las dos importan:

        * **sólo en el modo que el tramo pide.** El botón es el atajo de ese
          tramo, y aparecía en la primera pantalla de los tres modos: si el
          paso era ir al Generador, el botón estaba también en el Organizador
          y en el Armonizador, así que no señalaba nada.
        * **sólo si el tramo se juega con un botón.** El del Armonizador no:
          ese se juega tocando una tecla dorada del piano, que es un gesto y
          no un atajo, y tener las dos cosas lo volvía un botón con un piano
          decorativo al lado.
        """
        step = self.story.current
        if step is None or step.where != "random" or self.mode != "random":
            return None
        open_now = self.story.gate_open(step.gate)
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        button = ctk.CTkButton(
            row,
            text=(tr(step.ready_text) if open_now
                  else trf("🔒  {locked}", locked=tr(step.locked_text))),
            height=46, corner_radius=12,
            font=scaled(("Georgia", 15, "bold")),
            fg_color=GOLD_DIM if open_now else SURFACE_LIGHT,
            hover_color=GOLD if open_now else SURFACE_LIGHT,
            text_color="#1B1D22" if open_now else TEXT_MUTED,
            border_width=2, border_color=GOLD if open_now else BORDER_SOFT,
            state="normal" if open_now else "disabled",
            command=self._story_trigger)
        button.pack(fill="x")
        if open_now:
            start_shimmer(button, period=110, option="border_color")
        else:
            ctk.CTkLabel(
                row, text=tr(self._story_gate_how(step)),
                font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w",
                justify="left", wraplength=940
                ).pack(anchor="w", pady=(4, 0))
        return button

    def _story_gate_how(self, step) -> str:
        """Cómo se cumple la traba, dicho por el programa y no por nadie."""
        if step.gate in story.BOOK_GATES:
            return ("Abrí el libro de teoría desde la pantalla inicial y leé "
                    "el capítulo «La música de los reprimidos». Con abrirlo y "
                    "verlo alcanza.")
        return "Se hace en el Organizador."

    def _story_trigger(self) -> None:
        """El botón dorado: escribe la pieza del tramo sin buscar nada."""
        step = self.story.current
        if step is None or not self.story.gate_open(step.gate):
            return
        piece = story.piece_for(step.key, self._story_tonic())
        if piece is None:
            return
        self._run_story_piece(piece)

    def _story_tonic(self) -> int:
        """
        La tónica menor de la armadura elegida en el Armonizador.

        La nota azul es la quinta bemol **sobre la menor**, así que hace
        falta la relativa menor de la armadura y no su mayor: la menor está
        una tercera menor por debajo, que es lo mismo que nueve semitonos
        por encima.
        """
        label = getattr(self, "_key_label", self.KEY_SIGNATURES[0][0])
        menu = getattr(self, "key_menu", None)
        if menu is not None:
            try:
                label = i18n.untr(menu.get())
            except tk.TclError:
                pass
        fifths = next((f for name, f in self.KEY_SIGNATURES if name == label), 0)
        tonic, _mode = importer.key_from_fifths(fifths)
        return (tonic + 9) % 12

    def _story_manual_notice(self) -> None:
        """La consigna del tramo a mano, arriba de la pantalla de acordes."""
        step = self._story_awaiting("manual")
        if step is None:
            return
        panel = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT,
                             corner_radius=12, border_width=2,
                             border_color=GOLD_DIM)
        panel.pack(fill="x", pady=(4, 0))
        head = ctk.CTkLabel(panel, text=trf("★  {title}",
                                            title=tr(step.title)),
                            font=scaled(("Georgia", 14, "bold")),
                            text_color=GOLD, anchor="w")
        head.pack(anchor="w", padx=16, pady=(10, 2))
        start_shimmer(head)
        ctk.CTkLabel(panel, text=tr(step.goal), font=scaled(("Segoe UI", 13)),
                     text_color=TEXT_NORMAL, anchor="w", justify="left",
                     wraplength=880).pack(anchor="w", padx=16)
        ctk.CTkLabel(panel, text=tr(step.hint), font=FONT_SMALL,
                     text_color=TEXT_MUTED, anchor="w", justify="left",
                     wraplength=880).pack(anchor="w", padx=16, pady=(2, 12))

    def _story_harmonise_notice(self, step, ready: bool) -> None:
        """El cartel del Armonizador: qué tocar, o qué falta para poder."""
        panel = ctk.CTkFrame(self.body, fg_color=SURFACE_LIGHT,
                             corner_radius=12, border_width=2,
                             border_color=GOLD if ready else BORDER_SOFT)
        panel.pack(fill="x", pady=(4, 0))
        head = ctk.CTkLabel(
            panel,
            text=(tr(step.ready_text) if ready
                  else trf("🔒  {locked}", locked=tr(step.locked_text))),
            font=scaled(("Georgia", 14, "bold")),
            text_color=GOLD if ready else TEXT_MUTED, anchor="w")
        head.pack(anchor="w", padx=16, pady=(10, 2))
        if ready:
            start_shimmer(head)
        done, needed = self.story.gate_progress(step.gate)
        ctk.CTkLabel(
            panel,
            text=(tr(step.hint if ready
                     else trf("{locked_text} ({done} de {needed}) y el piano "
                              "se enciende.",
                              locked_text=step.locked_text, done=done,
                              needed=needed))),
            font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w",
            justify="left", wraplength=880).pack(anchor="w", padx=16,
                                                 pady=(0, 12))

    def _story_piano_pick(self, _midi: int) -> None:
        """
        Una tecla dorada tocada: se escribe la pieza del tramo, entera.

        No importa cuál de las encendidas se haya tocado. En el sendero del
        góspel están todas justamente porque el gesto es ese: cualquiera
        sirve.
        """
        if getattr(self, "_story_melody_playing", False):
            return
        step = self._story_awaiting("harmonise")
        if step is None or not self.story.gate_open(step.gate):
            return
        piece = story.piece_for(step.key, self._story_tonic())
        if piece is None:
            return
        # La melodía se dibuja en el pentagrama antes que nada: lo primero
        # que pasa al tocar la tecla es ver aparecer la línea.
        try:
            self.staff.notes = [
                (self._staff_index(pitch), length)
                for pitch, _start, length in piece.melody]
            # La línea es otra: lo que el usuario hubiera marcado apuntaba a
            # notas que ya no están. Los accidentes también: un sostenido
            # que quedara de antes alteraba una nota de la pieza del tramo.
            self.staff.marked = set()
            self.staff.blocked = set()
            self.staff.accidentals = {}
            self.staff.redraw()
            self._melody_notes = list(self.staff.notes)
            self._melody_marks = set()
            self._melody_skips = set()
            self._melody_accidentals = {}
        except (tk.TclError, AttributeError):
            pass
        self._story_hear_melody(piece)

    def _story_hear_melody(self, piece) -> None:
        """
        Escuchar la melodía del tramo, y recién al terminar armonizarla.

        El orden es el del descubrimiento: la línea aparece, suena sola, y
        cuando se apaga la última nota la pantalla ya es la del resultado.
        Escribir la pieza en el mismo gesto se saltaba la melodía --- que es
        justamente lo que el tramo vino a mostrar --- y la dejaba enterrada
        debajo de cuatro voces.
        """
        if not piece.melody:
            self._run_story_piece(piece)
            return
        self._story_melody_playing = True
        hint = getattr(self, "melody_hint", None)
        if hint is not None:
            try:
                hint.configure(text=tr("♪  Escuchá la línea…"), text_color=GOLD)
            except tk.TclError:
                hint = None

        def follow() -> None:
            self._story_melody_playing = False
            if self._story_awaiting("harmonise") is None:
                return          # se cambió de pantalla mientras sonaba
            self._run_story_piece(piece)

        self._playing = audio.play_chords(
            [], [], melody=list(piece.melody),
            quarter_seconds=piece.quarter_seconds)
        self._when_done(self._playing, follow)

    def _staff_index(self, midi: int) -> int:
        """La posición en el pentagrama de una altura, según la armadura."""
        octave, semitone = divmod(midi, 12)
        letters = ("C", "D", "E", "F", "G", "A", "B")
        offsets = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        letter = min(letters, key=lambda l: abs(offsets[l] - semitone))
        return (octave - 1) * 7 + letters.index(letter)

    def _story_piano_highlight(self, step):
        """Qué teclas se encienden en el Armonizador para este tramo."""
        if step.key == "blues_note":
            return {(self._story_tonic() + story.BLUE_NOTE_SEMITONES) % 12}
        if step.key == "jazz_lick":
            # La frase empieza en re, y en re empieza siempre: es una cita,
            # no una progresión que se transporte.
            return {2}
        if step.key == "gospel_grace":
            return "all"
        return set()

    # -- escribir la pieza de un tramo --------------------------------------

    def _story_melody(self, piece, voice_count: int):
        """La melodía de la pieza, en la forma que entiende el motor."""
        if not piece.melody:
            return None
        per_bar = piece.quarters_per_bar
        beats, _, beat_type = piece.time_signature.partition("/")
        bars = [harmonize.MelodyBar(int(beats), int(beat_type or 4))
                for _ in range(piece.bar_count + 1)]
        notes = []
        for pitch, start, length in piece.melody:
            bar_index = int(start / per_bar + 1e-9)
            notes.append(harmonize.MelodyNote(
                pitch=pitch, duration_quarters=length, bar_index=bar_index,
                offset_quarters=start - bar_index * per_bar))
        return harmonize.Melody(notes=notes, bars=bars,
                                melody_voice=voice_count - 1)

    def _run_story_piece(self, piece) -> None:
        """
        Escribir una pieza del relato entera, sin pasar por la búsqueda.

        Cada acorde va con sus alturas fijadas con el mismo candado que usa
        la interfaz, así que el algoritmo genético no tiene nada que elegir:
        una población mínima y una sola generación devuelven exactamente la
        pieza escrita, al instante. Es lo que pide el relato --- que el
        resultado no dependa ni del azar ni de los parámetros --- y se
        consigue con la maquinaria que ya existía, sin un camino paralelo
        que después haya que mantener.
        """
        beats, _, beat_type = piece.time_signature.partition("/")
        signature = TimeSignature(int(beats), int(beat_type or 4))
        bar_indices = piece.bar_indices()
        # La textura la decide la pieza, no lo que el usuario haya elegido:
        # el tramo automático ignora la configuración a propósito.
        voice_keys = story.voices_for(piece)
        try:
            written = story.voice_piece(piece, voice_keys)
        except (ChordParseError, ValueError, IndexError):
            written = [None] * len(piece.chords)

        entries: List[session.ChordEntry] = []
        for position, (symbol, duration) in enumerate(piece.chords):
            bar = bar_indices[position]
            entries.append(session.ChordEntry(
                symbol=symbol, duration_quarters=duration, bar_index=bar,
                is_rest=not symbol,
                forced_omissions=story.chord_omissions(piece, symbol),
                locked_pitches=written[position] if symbol else None))

        request = session.JobRequest(
            genre_key=piece.genre_key,
            voice_keys=list(voice_keys),
            entries=entries,
            time_signature=signature,
            bar_time_signatures=[signature] * max(1, piece.bar_count),
            title=tr(piece.title),
            switch_overrides=dict(story.FIXED_PIECE_RULES),
            ga_config=GAConfig(population_size=8, generations=1, elitism=1,
                               tournament_size=2),
        )
        try:
            outcome = session.generate(request)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror(tr("No se pudo escribir la pieza"), str(exc))
            return
        outcome.melody = self._story_melody(piece, len(voice_keys))

        # Se entra a la pantalla de resultados por el mismo camino que una
        # corrida normal, así que la exportación, la reproducción, el
        # historial y los logros funcionan sin enterarse de nada.
        self.request = request
        self.outcome = outcome
        self._story_auto = True
        # El mismo borrado que al arrancar una búsqueda de verdad, y por el
        # mismo motivo: esto es un intento nuevo, y lo que haya quedado
        # puesto del anterior --- listo, candado, escuchado --- no le
        # pertenece. Acá además importa el orden: `self.outcome` ya quedó
        # asignado arriba, así que sin este apagado la pantalla de espera de
        # abajo se dibujaría con «Nuevo» ya activo.
        self._results_ready = False
        self._story_continue_row = None
        self._story_continue_button = None
        self._story_listened = False
        # Estas piezas se escuchan como música, no para seguir la conducción
        # de voces con el oído, así que van a su propio tempo.
        self._story_speed = piece.quarter_seconds
        self.index = len(self.screens) - 1
        self._render()
        self.after(90, lambda: self._finish_story_piece(outcome))

    def _finish_story_piece(self, outcome) -> None:
        # Una sola opción, no tres.
        #
        # La pieza está escrita en `story.py` y va con todas las alturas
        # fijadas con el candado, así que al algoritmo no le queda nada que
        # elegir: las tres soluciones que devolvía eran la misma nota por
        # nota, con el mismo costo. Tres bloques idénticos, cada uno con su
        # botón de «Escuchar», no ofrecían una elección --- daban a entender
        # que había una y no la había. La pieza es una.
        result = getattr(outcome, "result", None)
        if result is not None and len(getattr(result, "solutions", []) or []) > 1:
            result.solutions = result.solutions[:1]
        self._on_finished(outcome, None)
        step = self.story.current
        if step is not None and step.where in ("random", "harmonise"):
            # La frase de jazz cierra sonando: el gesto del tramo es el
            # acorde que entra tarde, y contarlo sin escucharlo no sería
            # contarlo.
            if step.key == "jazz_lick":
                self.after(600, self._story_play_result)
            self._story_offer_continue()

    def _story_offer_continue(self) -> None:
        """
        Ofrecer seguir el relato, en vez de seguirlo solo.

        La escena que cierra un tramo aparecía sola un segundo después de que
        la partitura estuviera en pantalla, y se comía justo lo único que ese
        tramo tenía para dar: escuchar lo que se acababa de escribir. Ahora
        espera. El botón está arriba de todo, encima de las tres opciones,
        para que se vea sin buscarlo pero después del resultado.

        Y ahora espera **de verdad**: nace gris y bloqueado, con el mismo
        candado que usa el botón dorado del Generador antes de cumplir su
        traba, y sólo se abre cuando se aprieta un «▶ Escuchar» de los que
        quedaron dorados más abajo --- `_play_and_mark` es quien avisa. Antes
        se podía seguir sin haber escuchado un solo acorde de lo que el
        sendero acababa de escribir, que es exactamente lo que el tramo
        pide que se haga.
        """
        container = getattr(self, "results_container", None)
        if container is None:
            return
        try:
            children = container.winfo_children()
        except tk.TclError:
            return
        self._story_listened = False
        row = ctk.CTkFrame(container, fg_color="transparent")
        if children:
            row.pack(fill="x", pady=(0, 10), before=children[0])
        else:
            row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row,
                     text=tr("Escuchá lo que salió. Recién ahí se puede seguir."),
                     font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w"
                     ).pack(anchor="w", pady=(0, 4))
        button = ctk.CTkButton(
            row, text=tr("🔒  Escuchá primero"), height=44, corner_radius=12,
            font=scaled(("Georgia", 15, "bold")), fg_color=SURFACE_LIGHT,
            hover_color=SURFACE_LIGHT, text_color=TEXT_MUTED, border_width=2,
            border_color=BORDER_SOFT, state="disabled",
            command=self._story_continue)
        button.pack(fill="x")
        self._story_continue_row = row
        self._story_continue_button = button
        # Un «Nuevo» activo al pie mientras este candado sigue puesto era la
        # otra puerta de salida: se llegaba al mismo lado sin haber tocado
        # ningún «Escuchar».
        self._refresh_continue_button()

    def _story_mark_listened(self) -> None:
        """
        Se apretó un «▶ Escuchar»: destrabar el botón dorado de seguir.

        No importa cuál de los que hay en pantalla --- en el Organizador
        puede haber hasta tres opciones ---, ni si el sonido llegó a
        terminar: el gesto que cuenta es el click, que es la señal de que se
        fue a escuchar y no se siguió de largo.
        """
        if getattr(self, "_story_listened", False):
            return
        self._story_listened = True
        button = getattr(self, "_story_continue_button", None)
        if button is not None:
            try:
                button.configure(
                    text=tr("★  Seguir"), state="normal", fg_color=GOLD_DIM,
                    hover_color=GOLD, text_color="#1B1D22",
                    border_color=GOLD)
                start_shimmer(button, period=110, option="border_color")
            except tk.TclError:
                pass
        self._refresh_continue_button()

    def _story_continue(self) -> None:
        row = getattr(self, "_story_continue_row", None)
        if row is not None:
            try:
                row.destroy()
            except tk.TclError:
                pass
            self._story_continue_row = None
        self._story_continue_button = None
        self._refresh_continue_button()
        self._story_complete_step()

    def _story_play_result(self) -> None:
        outcome = self.outcome
        if outcome is None or not outcome.succeeded:
            return

        class _Silent:
            """Un botón de mentira: la reproducción quiere uno y acá no hay."""

            def configure(self, **_kwargs) -> None:
                return

        try:
            self._play_solution(outcome.result.solutions[0], _Silent())
        except Exception:                                   # noqa: BLE001
            pass

    def _story_settle_awards(self) -> None:
        """
        Entregar el legendario de un sendero terminado que no lo recibió.

        El camino se da por recorrido al avanzar el último tramo, pero el
        logro lo entrega la escena de cierre: cerrar el programa en la mitad
        de esa cinemática dejaba el sendero marcado como terminado y el
        premio sin dar, y como ya no queda ningún tramo por avanzar, no
        había nada que volviera a intentarlo nunca. Se pregunta al arrancar,
        que es lo mismo que hace `_check_watcher` y por el mismo motivo.
        """
        try:
            pending = {story.PATHS[key].award for key in self.story.finished
                       if key in story.PATHS}
            pending = {key for key in pending
                       if key and not self.achievements.has(key)}
            if pending:
                self._award(pending)
        except Exception:                                   # noqa: BLE001
            pass          # una cuenta pendiente no puede romper el arranque

    # -- el arrepentimiento --------------------------------------------------

    def _repent(self) -> None:
        """Volver a empezar: la figura reaparece y se elige de nuevo."""
        if self.scene is not None:
            return
        if not messagebox.askyesno(
                tr("¿Estás seguro?"),
                tr("Comenzarás tu camino otra vez.\n\n"
                   "Lo que ya conseguiste no se pierde: los logros, los títulos "
                   "y lo que quedó escrito en el libro siguen siendo tuyos. Lo "
                   "que vuelve a cero es el sendero.")):
            return
        self.story.restart()
        self.detour.clear()
        self.index = 0
        self._render()
        self.after(400, self._start_offer)
        # Y se vuelve a encender el vigía. La escena se abre acá nomás, pero
        # si no llega a contestarse ---se cierra el programa en la mitad---
        # el sendero queda vacío y tiene que haber alguien preguntando: sin
        # esto, el arrepentimiento podía costar el modo historia entero.
        self._rearm_story_watch()

    # -- el libro -----------------------------------------------------------

    def _lore_unlocked(self, key: str) -> bool:
        """
        ¿Está escrito el apartado que abre esta llave?

        El libro no distingue de dónde sale una llave: pregunta y alguien
        contesta. Las de siempre son claves de logro; las del capítulo del
        sendero son tramos recorridos, y las del capítulo de las visitas son
        apariciones. Un solo lugar para las tres, así que agregar contenido
        nuevo sigue siendo agregar una `Entry`.
        """
        return (self.achievements.has(key) or self.story.knows(key)
                or self.visits.knows(key))

    @unless_professional
    def _story_book_read(self, key: str) -> None:
        """Dar por leído un apartado del sendero, y destrabar si toca."""
        if key not in story.BOOK_GATES.values():
            return
        if not self.story.mark_read(key):
            return
        for gate, book_key in story.BOOK_GATES.items():
            if book_key != key:
                continue
            step = next((s for s in (self.story.path.steps
                                     if self.story.path else ())
                         if s.gate == gate), None)
            if step is not None:
                self._story_opened(step)


    # -- las visitas ---------------------------------------------------------
    #
    # Bach a las cinco partituras barrocas y otra vez al primer coral,
    # Gregorio a las cinco gregorianas, la entidad al cien por ciento de los
    # logros. Se ponen en escena con la misma maquinaria que el sendero ---
    # la cola, el fundido a negro, la cinemática --- porque son lo mismo
    # visto de afuera: alguien que aparece, dice algo y se va. Lo que cambia
    # es que no piden nada a cambio.

    #: Los ruidos que hace falta tener sintetizados antes de abrir cada
    #: visita. Van a pedido --- cada una ocurre una vez en la vida del
    #: programa --- así que se piden al encolarla y llegan mientras la
    #: pantalla todavía está en negro.
    VISIT_SOUNDS = {
        visitors.BACH: ("clavier", "blip_bach"),
        visitors.GREGORY: ("plainchant", "blip_gregory"),
        visitors.WATCHER: ("toll", "hollow", "blip_watcher"),
        # El creador no trae cama de ambiente, y es a propósito: su escena
        # empieza con el ventilador de la máquina callándose y termina con
        # el ventilador volviendo. Ponerle un fondo sería contradecir lo
        # único que el narrador dice de la sala.
        visitors.CREATOR: ("blip_creator",),
    }

    #: Los de la visión, en el orden en que la escena los pide. **El orden
    #: importa**: se sintetizan de a uno y en un solo hilo, así que lo que va
    #: primero está listo primero.
    #:
    #: Los dos últimos son de una visión cada uno --- la guitarra sólo suena
    #: en la primera, el tritono sólo en la segunda --- y la lista es una
    #: sola igual: el tritono se sintetiza en cada arranque de todos modos y
    #: la guitarra ya está escrita para cuando la segunda puede ocurrir, así
    #: que partirla en dos no ahorraría un segundo y dejaría dos listas que
    #: mantener.
    VISION_SOUNDS = ("gale", "train", "crossroads", "owls", "blues",
                     "tritone", "rain", "thunder", "dread")

    #: Y de ésos, los que tienen que estar **antes** de abrir la escena. La
    #: guitarra no: suena a los veinte segundos, y esperarla retrasaría toda
    #: la visión tres segundos y medio para nada.
    VISION_FIRST = ("gale", "train", "crossroads")

    #: Los de la tercera, que no son los mismos: ahí no hay tren y lo que
    #: tiene que estar listo es la lluvia --- se larga a los seis segundos ---
    #: y el golpe con el que se abre la tormenta.
    TOMB_FIRST = ("gale", "rain", "dread")

    def _when_sounds(self, names, then, tries: int = 0) -> None:
        """
        Abrir algo recién cuando sus ruidos estén sintetizados.

        Los sonidos de las apariciones se hacen a pedido y tardan un par de
        segundos cada uno. Pedirlos y abrir la escena en el mismo gesto
        significaba que los primeros diez segundos pasaban en silencio y el
        ruido llegaba cuando el momento ya había pasado: peor que no sonar.

        Se pregunta desde el hilo de Tk con un temporizador y no se espera
        bloqueando: la ventana tiene que seguir viva mientras tanto.

        **El límite es corto: dos segundos y medio.** Antes eran quince, y
        eran demasiados --- entre tocar el botón y ver algo pasaban ocho o
        diez segundos, y esa espera se siente como que el programa se colgó.
        Con la caché en disco esto tarda cero salvo la primerísima vez, y aun
        en esa vez lo que falte se sigue reintentando desde adentro de la
        escena (`cinematic.SoundCues`), así que cortar la espera no cuesta el
        sonido: cuesta, como mucho, que llegue un segundo tarde.
        """
        if not tries:
            # De a uno y en un solo hilo: cinco hilos sintetizando a la vez
            # tardan más que uno, porque en Python se turnan igual y encima
            # pagan el cambio de contexto.
            ambience.summon_all(list(names))
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        if tries >= 10 or all(ambience.made(name) for name in names):
            then()
            return
        self.after(250, lambda: self._when_sounds(names, then, tries + 1))

    @unless_professional
    def _open_visit(self, key: str) -> None:
        """Encolar una visita y abrirla cuando sus ruidos estén listos."""
        visit = visitors.VISITS.get(key)
        if visit is None:
            return
        self._queue_visit(key)
        self._when_sounds(self.VISIT_SOUNDS.get(visit.speaker, ()),
                          self._advance_scenes)

    def _check_visitors(self) -> None:
        """
        Anotar la partitura que se acaba de terminar y traer a quien toque.

        Se llama en el mismo lugar que los logros de una corrida: una vez,
        en el hilo de Tk, sobre un resultado que ya está en memoria. Los
        tramos automáticos del relato no pasan por acá, igual que no reparten
        logros --- la pieza la escribió el programa de un botón.
        """
        due = self.visits.record(
            self.genre_key,
            chorale=bool(getattr(self, "_strict_counterpoint", False)))
        for key in due:
            self._open_visit(key)

    def _queue_visit(self, key: str) -> None:
        """Encolar una visita, con sus ruidos pedidos por adelantado."""
        visit = visitors.VISITS.get(key)
        if visit is None:
            return
        for name in self.VISIT_SOUNDS.get(visit.speaker, ()):
            ambience.summon(name)
        self._queue_scene(visit.speaker, visit.lines,
                          keepsake=visit.keepsake, reveal_name=visit.name,
                          title=visit.title, dream=visit.dream,
                          after=lambda k=key: self._visit_done(k))

    def _visit_done(self, key: str) -> None:
        """
        Dar la visita por ocurrida: recién cuando la escena terminó.

        No antes. Si se marcara al decidirla, cerrar el programa en la mitad
        de la escena le costaría al usuario una aparición que no llegó a ver
        y que no vuelve a ocurrir nunca.

        **No se vuelve a la pantalla inicial.** Al revés que el sendero, una
        visita se abre encima de la pantalla de resultados de la corrida que
        la disparó, y ésa sigue estando abajo cuando la escena se va: hacer
        volver al usuario al principio le sacaría la partitura que acaba de
        terminar, que es justamente por la que vinieron a felicitarlo.
        """
        visit = visitors.VISITS.get(key)
        if visit is not None and visit.keepsake[1]:
            self.visits.take_keepsake()
        self.visits.mark(key)
        # El logro va acá y no en `_check_visitors`, por lo mismo que la
        # marca: lo que se premia es haber recibido a alguien, y hasta que
        # la escena no terminó no se recibió a nadie.
        self._award([visitors.award_for(key)])
        # Una visita no vuelve a la pantalla inicial, así que acá no hay
        # ningún `_render` que lo prenda: se prende a mano.
        self._refresh_note_flag()
        if visitors.writes(key):
            self._story_notice(
                "Anotaste lo que te dijeron",
                "Hay una entrada nueva en el capítulo de las visitas, en el "
                "libro de teoría.",
                heading="🖋  Se escribe solo")
        if key == visitors.WATCHER_ALL:
            # Lo otro que dejó. Va en su propio cartel: son dos regalos
            # distintos y meterlos en una sola línea deja al segundo
            # pareciendo una aclaración del primero.
            self._story_notice(
                "Se abrió la lista de los huevos",
                "Al pie de los logros están ahora los seis, con los pasos "
                "exactos para volver a provocarlos.",
                heading="🥚  Ya no hay nada que esconder")

    def _check_watcher(self) -> None:
        """
        ¿Está todo conseguido? Entonces aparece.

        No se abre acá mismo: completar el último logro casi siempre trae
        además una estrella o un legendario, que son animaciones a pantalla
        completa, y dos cosas dibujándose encima de la ventana al mismo
        tiempo se tapan entre sí. Se espera a que la pantalla quede libre.
        """
        done, total = self.achievements.total_progress()
        if done < total or self.visits.saw(visitors.WATCHER_ALL):
            return
        if getattr(self, "_watcher_pending", False):
            return
        self._watcher_pending = True
        self._watch_watcher()

    def _watch_watcher(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        if self.visits.saw(visitors.WATCHER_ALL):
            return
        if (self.overlay is not None or self.celebrations
                or self.scene is not None or self.toasts):
            self.after(1200, self._watch_watcher)
            return
        self._watcher_pending = False
        self._open_visit(visitors.WATCHER_ALL)

    # -- la visión -----------------------------------------------------------

    @unless_professional
    def _warm_vision(self) -> None:
        """
        Empezar a sintetizar los ruidos de la visión, por las dudas.

        Se decide acá y no adentro de `_maybe_vision` porque el sorteo se
        tira una sola vez: si lo tirara dos, una podría salir que sí y la
        otra que no. Lo que se hace es preguntar lo barato --- ¿queda alguna
        visión por ver? --- y si queda, poner a calentar. En las cuatro de
        cada cinco veces que el sorteo diga que no, lo único que se perdió
        son unos segundos de un hilo de fondo.

        Lo barato incluye el tutorial: mientras no esté hecho la visión no
        puede ocurrir, y el arranque donde no está hecho es justamente el
        primero de todos --- el peor momento para tener cinco ruidos largos
        sintetizándose de fondo mientras alguien recorre el programa por
        primera vez.

        Las tres visiones comparten casi todos los ruidos, así que alcanza
        con que quede alguna de las tres por ver.
        """
        forced = (visitors.vision_forced(), visitors.pact_forced(),
                  visitors.tomb_forced())
        if any(flag is True for flag in forced):
            ambience.summon_all(self.VISION_SOUNDS)
            return
        if not self.settings.get("tutorial_seen"):
            return
        pending = zip(forced, (self.visits.vision, self.visits.pact,
                               self.visits.tomb))
        if not any(flag is not False and not seen for flag, seen in pending):
            return
        ambience.summon_all(self.VISION_SOUNDS)

    @unless_professional
    def _maybe_vision(self) -> None:
        """
        El cruce de caminos, si el sorteo lo quiere.

        Una de cada cinco veces que se abre el programa, una sola vez en la
        vida, y nunca antes de haber terminado u omitido el tutorial. Es lo
        único acá adentro que no se puede provocar --- ni con un logro, ni
        con un sendero, ni con una combinación --- y por eso es lo único que
        no se anuncia en ninguna parte.

        Son tres, encadenadas: cada una corre el mismo sorteo en los
        arranques en que la anterior ya ocurrió. Se preguntan **en orden y no
        todas a la vez**: cada una tira su propia moneda, y la siguiente sólo
        tira la suya cuando la anterior dijo que no --- que es lo mismo que
        decir que en un arranque puede pasar una, o ninguna, pero nunca dos.

        Si el momento no es tranquilo no se reintenta: la visión es *al
        abrir*, y aparecer diez minutos después en la mitad de un trabajo
        sería otra cosa distinta.
        """
        kind = ""
        if not self._vision_wanted():
            if self._pact_wanted():
                kind = "pact"
            elif self._tomb_wanted():
                kind = "tomb"
            else:
                return
        if not self._story_quiet():
            return
        self._open_vision(kind)

    def _vision_wanted(self) -> bool:
        forced = visitors.vision_forced()
        if forced is False:
            return False
        return bool(forced) or visitors.vision_due(
            bool(self.visits.vision), random.random(),
            bool(self.settings.get("tutorial_seen")))

    def _pact_wanted(self) -> bool:
        forced = visitors.pact_forced()
        if forced is False:
            return False
        return bool(forced) or visitors.pact_due(
            bool(self.visits.pact), bool(self.visits.vision),
            random.random(), bool(self.settings.get("tutorial_seen")))

    def _tomb_wanted(self) -> bool:
        forced = visitors.tomb_forced()
        if forced is False:
            return False
        return bool(forced) or visitors.tomb_due(
            bool(self.visits.tomb), bool(self.visits.pact),
            random.random(), bool(self.settings.get("tutorial_seen")))

    def _open_vision(self, kind: str = "") -> None:
        """
        Abrir una de las tres visiones, con la pantalla ya apagada.

        La segunda y la tercera terminan en negro y no lo sueltan, porque
        atrás viene lo que se dice; la primera devuelve el programa ella
        sola.
        """
        after = {"pact": self._pact_meeting,
                 "tomb": self._tomb_meeting}.get(kind, self._vision_done)

        def open_now() -> None:
            try:
                self.scene = cinematic.vision(
                    self, kind=kind, blackout=bool(kind), on_done=after)
            except Exception:                               # noqa: BLE001
                # Una escena que no se puede dibujar no puede impedir abrir
                # el programa. Se la da por no ocurrida y sigue disponible.
                self.scene = None

        # No arranca hasta tenerlos hechos. Son ruidos largos y la escena los
        # necesita casi enseguida: el tren a los dos segundos, la lluvia a
        # los seis.
        self._when_sounds(
            self.TOMB_FIRST if kind == "tomb" else self.VISION_FIRST,
            lambda: self._fade_to_black(open_now))

    def _vision_done(self) -> None:
        """
        Termina y no dice nada. A propósito.

        Todas las demás cosas que escriben en el libro lo avisan con un
        cartel, porque son cosas que el usuario se ganó y tiene que poder
        encontrar. Ésta no: nadie habló, nadie explicó nada y nadie dijo
        quién era. Un cartelito al final --- «hay una entrada nueva en el
        capítulo tal» --- convierte una aparición en una notificación, y de
        las dos cosas que la escena tenía para dar, el misterio era la
        segunda. La anotación está en el libro para el que vaya a buscarla.
        """
        self.scene = None
        self.visits.mark_vision()
        # El cartel del pie sí se prende, y no contradice nada de lo de
        # arriba: no dice qué pasó ni quién vino, sólo que el libro tiene
        # algo sin leer.
        self._refresh_note_flag()
        # Que el señor del sombrero no aparezca pisándole los talones: la
        # espera de cinco minutos se cuenta desde acá.
        self._story_since = time.monotonic()

    def _pact_meeting(self) -> None:
        """
        Lo que se dice después de la segunda visión: la pantalla negra y una
        línea. Nada más, y es a propósito que sea lo más simple del archivo.

        Va como escena de diálogo y no como un pedazo más de la visión
        porque lo que hace falta es un cuadro de diálogo, que es exactamente
        lo único que `cinematic.Vision` no tiene ni tiene por qué tener. Pero
        de la maquinaria de una escena se le apaga todo lo demás:

        * **`opening=False`** --- no despierta, no hay negro que aguantar y
          no hay párpados que se abran. La visión ya dejó la pantalla negra;
          el cartel aparece encima y listo. Con `"dark"` había un silencio y
          después un pestañeo, que es un pestañeo de más.
        * **`sky="black"`** --- negro pelado. El `void` de las visitas tiene
          un charco de luz y polvo flotando, y las dos cosas dibujan un
          cuarto a oscuras: acá no hay ningún cuarto.
        * **`entrance="unseen"`** --- nadie en pantalla. El que habla es el
          que estaba en el camino hace cinco segundos, y volver a mostrarlo
          de cerca y con su cartelito lo convertiría en alguien que vino de
          visita a explicar algo.
        * **`departure="cut"`** --- al continuar, se esconde el cuadro,
          queda el negro un momento y se vuelve. Sobre negro, cualquier
          salida animada es negro sobre negro.
        """
        self.scene = None
        self._queue_scene(story.DEVIL, visitors.PACT_LINES, opening=False,
                          entrance="unseen", departure="cut", sky="black",
                          dream="", after=self._pact_done)
        self._advance_scenes()

    def _tomb_meeting(self) -> None:
        """
        Y lo que se dice después de la tercera: la misma pantalla negra y una
        línea más.

        Se monta igual que la de la segunda y por los mismos cuatro motivos
        --- sin apertura, sobre negro pelado, sin nadie en pantalla y con
        salida cortada --- así que lo único que cambia entre las dos es qué
        se dice. Que sean dos llamados y no uno con un parámetro es a
        propósito: lo que sigue después tampoco es lo mismo.
        """
        self.scene = None
        self._queue_scene(story.DEVIL, visitors.TOMB_LINES, opening=False,
                          entrance="unseen", departure="cut", sky="black",
                          dream="", after=self._tomb_done)
        self._advance_scenes()

    def _tomb_done(self) -> None:
        """La tercera se da por vista, y con ella se termina la historia."""
        self.visits.mark_tomb()
        # Y el único logro que entrega una visión. Va acá y no al decidirla,
        # igual que la marca: una escena que se corta a la mitad no contó
        # nada, y el logro dice que la historia se escuchó entera.
        self._award([visitors.award_for(visitors.TOMB)])
        self._story_since = time.monotonic()
        self._story_go_home()
        self._refresh_note_flag()

    def _pact_done(self) -> None:
        """
        Se da por vista y se vuelve al principio.

        Al revés que una visita --- que se abre encima de la partitura por la
        que vinieron y la deja ahí cuando termina --- ésta ocurre al abrir el
        programa, así que abajo no hay nada que devolver.

        Tampoco avisa que quedó algo escrito, por lo mismo que no avisa la
        primera: nadie explicó nada y nadie dijo quién era, y un cartel al
        final convierte una aparición en una notificación. El del pie sí se
        prende --- ése no dice qué pasó, sólo que el libro tiene algo sin
        leer.
        """
        self.visits.mark_pact()
        self._story_since = time.monotonic()
        self._story_go_home()
        self._refresh_note_flag()

    def _preview_scene(self, key: str) -> None:
        """
        Abrir una aparición a pedido, desde el botón de prueba.

        **Provisorio**, igual que los botones que llaman acá: es la misma
        puerta que abre `CHORDWEAVER_VISIT`, pero desde adentro del programa
        y sin tener que arrancarlo de nuevo. Se juegan enteras --- con sus
        recompensas --- porque una escena que no entrega lo que entrega no
        sirve para probar si entrega bien.

        Va con `after` y no de una: el panel de configuración tiene que
        haberse cerrado antes de que la cinemática se dibuje encima, o la
        escena queda con el panel puesto por debajo cuando termina.
        """
        self._close_config()

        def play() -> None:
            if self.scene is not None:
                return
            if key in (visitors.VISION, visitors.PACT, visitors.TOMB):
                ambience.summon_all(self.VISION_SOUNDS)
                self._open_vision({visitors.PACT: "pact",
                                   visitors.TOMB: "tomb"}.get(key, ""))
                return
            self._open_visit(key)

        self.after(220, play)

    def _forced_visit(self) -> None:
        """
        La visita que pidió la variable de entorno, si pidió alguna.

        Existe por lo mismo que ``CHORDWEAVER_STORY_DELAY``: la entidad
        aparece al conseguir el último logro y la visión una vez de cada
        cinco, así que sin esto no hay forma de mirar ninguna de las dos por
        segunda vez. Forzada se juega entera, recompensas incluidas, y se
        puede repetir todas las veces que haga falta.
        """
        # La graduación tiene su propia variable: no es una visita del
        # catálogo, es la escena con que termina la escuelita, y llegar a
        # ella de verdad lleva treinta y tres ejercicios.
        if curriculum.graduation_forced() and self.scene is None:
            self._open_graduation()
            return
        key = visitors.forced()
        if not key or self.scene is not None:
            return
        self._open_visit(key)

    # -- enganches ----------------------------------------------------------

    def _check_run_achievements(self, outcome) -> None:
        """
        Todo lo que una corrida terminada puede desbloquear.

        Corre una sola vez por búsqueda, en el hilo de Tk y sobre un
        resultado que ya está en memoria: recorre los acordes una vez y las
        voces sólo si falta alguno de los dos logros de quintas paralelas.
        Si ya está todo conseguido no hace nada en absoluto.
        """
        pending = self.achievements.pending()
        if not pending:
            return
        found = set()

        found.add({"manual": "organiser_first",
                   "random": "generator_first",
                   "harmonise": "harmoniser_first"}.get(self.mode, ""))
        found.add({"classical": "genre_baroque",
                   "gregorian": "genre_gregorian",
                   "jazz": "genre_jazz"}.get(self.genre_key, ""))

        if self.mode == "random" and achievements.is_exotic_mode(
                getattr(self, "_mode_key", "major")):
            found.add("exotic_mode")
        if len(self.voice_keys) >= 6:
            found.add("six_voices")
        signatures = set(self.bar_signatures or [])
        signatures.add(self.base_time_signature)
        signatures.add(getattr(self, "_melody_metre", ""))
        if "5/4" in signatures:
            found.add("time_five_four")
        # El dial de color tiene un nombre distinto en cada modo --- es la
        # misma decisión con tres controles ---, así que se los pregunta a
        # los tres y se queda con el que exista. Y se compara contra el
        # valor con el que el estilo lo deja, no contra cero: el jazz
        # arranca con color y contra cero cualquier corrida de jazz habría
        # contado como rebelde sin que nadie tocara nada.
        style_defaults = harmony.GENRE_DEFAULTS.get(self.genre_key, {})
        colour_default = float(style_defaults.get("colour", 0.0))
        if self.mode == "harmonise":
            colour = 24.0 if getattr(self, "_harm_colour", False) else 0.0
            colour_default = 0.0
        elif self.mode == "random":
            colour = float(getattr(self, "_colour_weight", colour_default))
        else:
            colour = float(getattr(self, "_manual_colour", colour_default))
        # Y los registros se comparan contra los del catálogo. `range_overrides`
        # lleva SIEMPRE las cuatro voces --- se arma leyendo las casillas, estén
        # tocadas o no ---, así que preguntarle si tiene algo adentro daba que sí
        # en todas las corridas del programa.
        custom_ranges = any(
            index < len(self.voice_keys)
            and (low, high) != (VOICE_CATALOG[self.voice_keys[index]].low,
                                VOICE_CATALOG[self.voice_keys[index]].high)
            for index, (low, high) in self.range_overrides.items())
        if achievements.rules_customised(
                self.genre_key,
                getattr(self, "_switch_state", {}),
                balance=getattr(self, "_balance_position", None),
                cadence=getattr(self, "_cadence_choice", None),
                colour=abs(colour - colour_default),
                custom_ranges=custom_ranges):
            found.add("custom_rules")
        if achievements.ga_customised(self.ga_config, self._default_ga_config()):
            found.add("ga_tuned")

        found |= achievements.inspect_outcome(outcome, pending)
        self._award(found)

    def _check_written_chords(self, entries) -> None:
        """Los legendarios que dependen del cifrado que se escribió a mano."""
        if not self.achievements.wants("blues_pact", "second_coming"):
            return
        chords = []
        for entry in entries:
            if entry.is_rest:
                continue
            try:
                chords.append(entry.to_chord())
            except ChordParseError:
                return          # con un acorde ilegible no hay patrón que ver
        self._award(achievements.inspect_written_chords(
            chords, self.achievements.pending()))


#: Las notas en solfeo de los rótulos del libro, por su letra.
_SOLFEGE_LETTERS = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G",
                    "la": "A", "si": "B"}


def _figure_mark(mark: str) -> str:
    """
    Un rótulo de los pentagramas del libro, en el idioma de la pantalla.

    Los que son una nota ---«sol4»--- no se buscan en el catálogo: en inglés
    se dicen con su letra, «G4», igual que en el resto del programa.
    """
    name = mark.rstrip("0123456789")
    octave = mark[len(name):]
    if octave and name in _SOLFEGE_LETTERS:
        return (mark if i18n.is_default()
                else _SOLFEGE_LETTERS[name] + octave)
    return tr(mark)


def main() -> None:
    global FONT_SCALE
    # La consulta de version nueva arranca antes que nada: la respuesta se
    # espera despues, asi la red y el arranque corren juntos. Desde el fuente
    # no pregunta nada --- ver `engine.updates.enabled`.
    updates.start()

    # El cartel va **antes** de construir `ChordWeaverApp`, y no despues con
    # la ventana tapada: construirla deja timers puestos ---el tutorial de la
    # primera vez, la vision del arranque, las visitas--- y cualquier bucle de
    # eventos posterior los dispara. Contestando primero, no hay ninguna
    # ventana de la aplicacion viva que pueda tener nada agendado.
    #
    # La escala de letra se lee aca porque el cartel es lo primero que se
    # dibuja y `ChordWeaverApp.__init__`, que es quien normalmente la pone,
    # todavia no corrio. La vuelve a poner despues, con el mismo valor.
    stored = history.load_settings()
    FONT_SCALE = float(stored.get("font_scale", 1.0) or 1.0)
    palette = {
        "surface": SURFACE, "panel": SURFACE_LIGHT, "text": TEXT_NORMAL,
        "muted": TEXT_MUTED, "accent": ACCENT,
        "accent_hover": ACCENT_HOVER, "border": BORDER_SOFT,
        "gold": GOLD, "font": scaled}

    # El idioma, antes que el cartel de version nueva: ese cartel es lo
    # primero que se dibuja, y preguntar despues lo dejaria escrito en un
    # idioma que el usuario todavia no eligio. Pregunta una sola vez en la
    # vida de la instalacion --- despues se cambia desde el engranaje.
    chooser.settle(stored, history.save_settings, palette)

    if not updater.greet(colours=palette):
        return

    app = ChordWeaverApp()
    # Después del cartel de idioma o del de versión nueva, la ventana del
    # programa es la segunda que se abre en el mismo proceso, y Windows le
    # da el foco a otra cosa cuando la primera se cierra: aparecía detrás de
    # todo o minimizada, y quien había apretado «Ahora no» creía que el
    # programa se había cerrado.
    app.after(150, app.bring_to_front)
    app.mainloop()


if __name__ == "__main__":
    # Required on Windows: child processes re-import this module, and without
    # the guard each one would open another window.
    import multiprocessing
    multiprocessing.freeze_support()
    main()
