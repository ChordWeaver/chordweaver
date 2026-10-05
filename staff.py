# -*- coding: utf-8 -*-
"""
A staff you can write on.

Notes are entered by clicking where they go, which is how anyone who reads
music expects to enter them. A piano keyboard sits underneath for the cases
where the staff is fiddly -- picking an accidental, or a note far above the
lines -- so neither way of thinking is forced on the user.

The widget owns nothing but the line: it hands back a list of pitches and
durations, and the harmoniser decides what to do with them.

Cómo se dibuja
--------------
Con Bravura, la fuente SMuFL de Steinberg (licencia SIL OFL 1.1, en
`assets/fonts/`). Las cabezas, las claves, los silencios, los accidentes y
las banderas son signos de la fuente y no trazos: dibujados a mano con óvalos
y rayas se veían como el dibujo de una partitura y no como una partitura.

La fuente se carga **en privado** (sólo para este proceso) y se mide contra
la distancia entre líneas: en SMuFL un cuerpo mide cuatro espacios de
pentagrama, así que pidiéndola a `4 × espacio` píxeles una cabeza ocupa
exactamente un espacio y cae justa entre dos líneas. Si la fuente no se
puede cargar ---otra plataforma, un archivo que falta--- el pentagrama se
dibuja con los trazos de siempre y sigue funcionando igual: lo que cambia es
cómo se ve, nunca qué significa un click.
"""

from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import tkinter as tk
from dataclasses import dataclass
from typing import (Callable, Dict, List, Optional, Sequence, Set,
                    Tuple)

import customtkinter as ctk

from engine.i18n import tr, trf, trs
from engine import i18n
from engine.history import program_directory

#: Staff geometry, in pixels.
#: Generous on purpose. At a tighter spacing a step is only a few pixels and
#: neighbouring notes become impossible to tell apart -- a written G reads as
#: an A, which makes the whole staff untrustworthy.
LINE_GAP = 20               # between adjacent staff lines
STEP = LINE_GAP // 2        # one scale step: line to adjacent space
#: Lo justo para la nota más aguda que deja escribir un click (seis grados
#: sobre la quinta línea) y, con `STAFF_HEIGHT`, para la más grave (veinte
#: debajo): el lienzo no tiene que ser más alto que eso, porque lo que
#: sobra acá le falta abajo a la pantalla de la melodía.
TOP_MARGIN = 100
#: Dónde empiezan las notas **como mínimo**. Lo que hay antes ---clave,
#: armadura y compás--- se mide en cada dibujo, y con cuatro sostenidos ya no
#: entra acá: la armadura se dibujaba encima de la primera nota.
LEFT_MARGIN = 150
NOTE_SPACING = 58
#: Lo más apretadas que pueden quedar dos notas antes de que el pentagrama
#: empiece a desplazarse. Es el ancho de una cabeza de nota con su aire y el
#: de un accidente delante: por debajo, dos alturas vecinas dejan de
#: distinguirse y el sostenido de una nota se dibuja encima de la anterior.
#: Con las cabezas de la fuente ---un espacio y un quinto de ancho, que es lo
#: que mide una cabeza de verdad--- los treinta y ocho de antes no alcanzaban.
MIN_SPACING = 44.0
STAFF_HEIGHT = 320

#: Note durations offered, in quarter notes.
DURATIONS = [
    ("Redonda", 4.0),
    ("Blanca", 2.0),
    ("Negra c/punto", 1.5),
    ("Negra", 1.0),
    ("Corchea c/punto", 0.75),
    ("Corchea", 0.5),
]

#: Durations written with a dot, so the note can be drawn with one.
DOTTED = (1.5, 0.75, 3.0)

#: Letter names in scale order, and their semitone offsets.
LETTERS = ("C", "D", "E", "F", "G", "A", "B")
LETTER_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

#: How many sharps or flats each key signature carries, and in what order.
SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")


def diatonic_index(letter: str, octave: int) -> int:
    """Position on the staff ladder: every letter is one step."""
    return octave * 7 + LETTERS.index(letter)


def index_to_pitch(index: int, fifths: int) -> int:
    """
    Turn a staff position into a MIDI pitch, applying the key signature.

    A note written on a line does not say which semitone it is -- the key
    signature does. Applying it here means what the user clicks is what the
    key says it should be, rather than always a natural.
    """
    octave, position = divmod(index, 7)
    letter = LETTERS[position]
    semitone = LETTER_SEMITONE[letter]
    if fifths > 0 and letter in SHARP_ORDER[:fifths]:
        semitone += 1
    elif fifths < 0 and letter in FLAT_ORDER[:abs(fifths)]:
        semitone -= 1
    return (octave + 1) * 12 + semitone


def scale_of(fifths: int) -> Set[int]:
    """Las clases de altura que la armadura deja sin alterar: la escala."""
    return {index_to_pitch(step, fifths) % 12 for step in range(7)}


# ---------------------------------------------------------------------------
# La fuente musical
# ---------------------------------------------------------------------------

MUSIC_FONT_FAMILY = "Bravura"
#: Dónde vive, relativo a la raíz del programa. Se resuelve contra
#: `program_directory()` y nunca contra `base_directory()`: ésa la mueve la
#: variable de pruebas, y la fuente es del programa, no del usuario.
MUSIC_FONT_FILE = ("assets", "fonts", "Bravura.otf")
#: Windows no carga una fuente cuya ruta pase los 260 caracteres. El programa
#: descomprimido un par de carpetas adentro llega fácil, y entonces se la
#: copia a la carpeta temporal y se la carga desde ahí ---lo mismo que hace
#: `_rescue_widget_fonts` en `app.py` con las de customtkinter---.
MAX_FONT_PATH = 259
SHORT_FONT_FOLDER = "ChordWeaver-fonts"
#: Cargarla sólo para este proceso: no se instala nada en el sistema.
FR_PRIVATE = 0x10
#: Apagable desde afuera, para probar el dibujo por trazos sin desinstalar
#: nada.
USE_MUSIC_FONT = True

#: None mientras no se intentó; después, si quedó cargada.
_font_loaded: Optional[bool] = None


def music_font_path() -> str:
    return os.path.join(program_directory(), *MUSIC_FONT_FILE)


def _add_private_font(path: str) -> bool:
    """Pedirle a Windows la fuente, sólo para este proceso."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        added = ctypes.windll.gdi32.AddFontResourceExW(
            ctypes.c_wchar_p(path), FR_PRIVATE, 0)
    except (AttributeError, OSError, ValueError):
        return False
    return bool(added)


def _short_copy(path: str) -> Optional[str]:
    """Una copia de la fuente en una ruta que Windows sí acepta."""
    folder = os.path.join(tempfile.gettempdir(), SHORT_FONT_FOLDER)
    short = os.path.join(folder, os.path.basename(path))
    try:
        os.makedirs(folder, exist_ok=True)
        if (not os.path.exists(short)
                or os.path.getsize(short) != os.path.getsize(path)):
            shutil.copyfile(path, short)
    except OSError:
        return None
    return short


def try_load_music_font(path: str,
                        loader: Callable[[str], bool] = _add_private_font
                        ) -> bool:
    """
    Cargar la fuente desde esa ruta, con la copia corta si hace falta.

    `loader` es lo que de verdad la carga; existe como parámetro para que
    las pruebas puedan simular una carga que falla sin tocar el sistema.
    """
    if not os.path.isfile(path):
        return False
    if len(path) <= MAX_FONT_PATH and loader(path):
        return True
    short = _short_copy(path)
    return short is not None and short != path and loader(short)


def load_music_font() -> bool:
    """Cargar Bravura una sola vez por proceso. True si quedó disponible."""
    global _font_loaded
    if _font_loaded is None:
        try:
            _font_loaded = try_load_music_font(music_font_path())
        except Exception:                                   # noqa: BLE001
            # Una fuente que no carga no puede llevarse puesto el pentagrama:
            # sin ella se dibuja con trazos, que es como se dibujó siempre.
            _font_loaded = False
    return _font_loaded


def music_font(widget, pixels: int) -> Optional[Tuple[Tuple[str, int], int]]:
    """
    La fuente musical a ese cuerpo, con su ascenso, o None si no está.

    Se pasa como descripción ---``("Bravura", -64)``--- y no como objeto
    `Font`: Tk guarda la fuente por su descripción, y un objeto `Font` se
    borra a sí mismo desde `__del__`, que puede correr en cualquier hilo.
    El tamaño va en negativo porque así Tk lo lee en píxeles, que es en lo
    que está medido el pentagrama.

    Se comprueba que Tk haya encontrado **esa** familia: si la carga privada
    no funcionó, Windows contesta con Arial sin quejarse, y una cabeza de
    nota en Arial es un rectángulo vacío.
    """
    if not USE_MUSIC_FONT or not load_music_font():
        return None
    font = (MUSIC_FONT_FAMILY, -int(pixels))
    try:
        family = str(widget.tk.call("font", "actual", font, "-family"))
        if family != MUSIC_FONT_FAMILY:
            return None
        ascent = int(widget.tk.call("font", "metrics", font, "-ascent"))
    except (tk.TclError, ValueError):
        return None
    return font, ascent


#: Los signos que se usan, por su nombre SMuFL. Los puntos de código son los
#: de la especificación (glyphnames.json): el Área de Uso Privado que
#: SMuFL reserva para la notación.
GLYPHS = {
    "brace": "",
    "gClef": "",
    "fClef": "",
    "noteheadWhole": "",
    "noteheadHalf": "",
    "noteheadBlack": "",
    "augmentationDot": "",
    "flag8thUp": "",
    "flag8thDown": "",
    "flag16thUp": "",
    "flag16thDown": "",
    "flag32ndUp": "",
    "flag32ndDown": "",
    "accidentalFlat": "",
    "accidentalNatural": "",
    "accidentalSharp": "",
    "accidentalDoubleSharp": "",
    "accidentalDoubleFlat": "",
    "restWhole": "",
    "restHalf": "",
    "restQuarter": "",
    "rest8th": "",
    "rest16th": "",
    "rest32nd": "",
}
for _digit in range(10):
    GLYPHS[f"timeSig{_digit}"] = chr(0xE080 + _digit)

#: Ancho de cada signo, en espacios de pentagrama (de `Bravura.json`,
#: `glyphAdvanceWidths`). Hace falta saberlo antes de dibujar: la cabeza se
#: centra en su lugar y el accidente se pega a su izquierda.
WIDTHS = {
    "brace": 0.28, "gClef": 2.684, "fClef": 2.736,
    "noteheadWhole": 1.688, "noteheadHalf": 1.18, "noteheadBlack": 1.18,
    "augmentationDot": 0.4,
    "flag8thUp": 1.056, "flag8thDown": 1.224, "flag16thUp": 1.116,
    "flag16thDown": 1.168, "flag32ndUp": 1.048, "flag32ndDown": 1.096,
    "accidentalFlat": 0.904, "accidentalNatural": 0.672,
    "accidentalSharp": 0.996, "accidentalDoubleSharp": 0.988,
    "accidentalDoubleFlat": 1.644,
    "restWhole": 1.132, "restHalf": 1.132, "restQuarter": 1.08,
    "rest8th": 1.0, "rest16th": 1.28, "rest32nd": 1.452,
    "timeSig0": 1.88, "timeSig1": 1.336, "timeSig2": 1.784,
    "timeSig3": 1.684, "timeSig4": 1.8, "timeSig5": 1.676,
    "timeSig6": 1.736, "timeSig7": 1.636, "timeSig8": 1.744,
    "timeSig9": 1.736,
}

#: Grosores y distancias de grabado, en espacios (`engravingDefaults` de
#: Bravura, salvo donde se dice otra cosa).
STEM_THICKNESS = 0.12
LEDGER_EXTENSION = 0.4
BEAM_THICKNESS = 0.5
BEAM_SPACING = 0.25
#: Dónde se pega la plica a la cabeza, arriba o abajo del centro.
STEM_ATTACH = 0.168
#: El largo de una plica: una octava, tres espacios y medio. Más corta se
#: lee como un dibujo; el sistema de dos pentagramas la acorta medio
#: espacio porque tiene dos voces por pentagrama y todo el alto contado.
STEM_LENGTH = 3.5
#: Lo más corta que puede quedar una plica cuando algo arriba ---el cifrado
#: americano del sistema--- no la deja crecer. Por debajo de esto una negra
#: se lee como una cabeza suelta con un palito.
MIN_STEM_LENGTH = 2.25
#: Lo más que sube o baja una barra de corcheas de punta a punta, en
#: espacios, y lo más empinada que puede ser. Una barra que copia el salto
#: entero de la melodía se lee como una rampa, y dos semicorcheas pegadas
#: con un espacio de desnivel quedaban unidas por una pared.
MAX_BEAM_SLANT = 1.0
MAX_BEAM_SLOPE = 0.27

#: Los accidentes, por su valor.
ACCIDENTAL_GLYPHS = {1: "accidentalSharp", -1: "accidentalFlat",
                     0: "accidentalNatural", 2: "accidentalDoubleSharp",
                     -2: "accidentalDoubleFlat"}
#: Y escritos con caracteres, para cuando la fuente musical no está.
ACCIDENTAL_TEXT = {1: "♯", -1: "♭", 0: "♮", 2: "𝄪", -2: "𝄫"}


def figure_of(duration: float) -> Tuple[float, int]:
    """
    Qué figura dibuja esa duración: (figura en negras, cuántos puntillos).

    El doble puntillo existe: el tenor del preludio de Bach entra con una
    negra con doble puntillo, y dibujada como blanca decía que duraba un
    cuarto más de lo que dura. Una duración que no es ninguna figura ---un
    tresillo importado--- se dibuja con la figura que la contiene sin
    pasarse por mucho: un tercio de negra es una corchea de tresillo, no una
    semicorchea.
    """
    for figure in (4.0, 2.0, 1.0, 0.5, 0.25, 0.125):
        if abs(duration - figure * 1.5) < 1e-6:
            return figure, 1
        if abs(duration - figure * 1.75) < 1e-6:
            return figure, 2
    for figure in (4.0, 2.0, 1.0, 0.5, 0.25, 0.125):
        if figure <= duration * 1.5 + 1e-6:
            return figure, 0
    return 0.125, 0


def _head_glyph(figure: float) -> str:
    if figure >= 4.0:
        return "noteheadWhole"
    if figure >= 2.0:
        return "noteheadHalf"
    return "noteheadBlack"


def _beam_levels(figure: float) -> int:
    """Cuántas barras (o banderas) lleva una figura."""
    if figure >= 1.0:
        return 0
    if figure >= 0.5:
        return 1
    if figure >= 0.25:
        return 2
    return 3


def _blend(colour: str, under: str, amount: float) -> str:
    """Mezclar dos colores `#rrggbb`: `amount` del primero sobre el segundo."""
    try:
        top = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
        bottom = [int(under[i:i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, IndexError, TypeError):
        return colour
    mixed = [round(t * amount + b * (1.0 - amount)) for t, b in zip(top, bottom)]
    return "#%02X%02X%02X" % tuple(max(0, min(255, c)) for c in mixed)


# ---------------------------------------------------------------------------
# Los colores de la melodía del Armonizador
# ---------------------------------------------------------------------------

#: El naranja de la nota fuera de la escala, cuando quien arma el pentagrama
#: no pasa uno propio. Bien separado del oro ---que dice «lleva acorde»--- en
#: el tono y no sólo en el brillo: los dos tienen que poder estar en la misma
#: nota sin confundirse.
CHROMATIC_COLOUR = "#F0883E"
#: Cuánto del oro lleva el halo de una nota con acorde.
HALO_STRENGTH = 0.32


@dataclass(frozen=True)
class NoteLook:
    """Cómo se pinta una nota de la melodía."""

    head: str                       # cabeza, plica y accidente
    halo: Optional[str] = None      # el disco detrás: lleva acorde
    ring: Optional[str] = None      # el anillo: lo marcó el usuario


def note_look(chromatic: bool, harmonised: bool, pinned: bool,
              colours: Dict[str, str]) -> NoteLook:
    """
    El color y la forma de una nota, según las dos preguntas que contesta.

    Son dos preguntas y cada una tiene su propio canal, para que las cuatro
    combinaciones se distingan sin depender sólo del tono:

    * **¿Está en la escala?** Lo dice el color de la cabeza: naranja la que
      no está, y su accidente con ella.
    * **¿Lleva acorde?** Lo dice la forma: un halo dorado detrás de la
      cabeza. La nota de la escala que lleva acorde además se pinta de
      dorado, que es lo que el pentagrama siempre dijo.

    Un anillo fino encima dice que la marcó el usuario y no el programa.
    """
    ink = colours.get("text", "#E6E8EB")
    gold = colours.get("gold", colours.get("accent", "#E8C97A"))
    orange = colours.get("chromatic", CHROMATIC_COLOUR)
    surface = colours.get("surface", "#25282F")
    if chromatic:
        head = orange
    else:
        head = gold if harmonised else ink
    halo = _blend(gold, surface, HALO_STRENGTH) if harmonised else None
    return NoteLook(head=head, halo=halo, ring=gold if pinned else None)


# ---------------------------------------------------------------------------
# El grabador: lo que sabe dibujar una partitura
# ---------------------------------------------------------------------------

@dataclass
class EngravedNote:
    """Una nota lista para dibujar su plica, su bandera o su barra."""

    x: float                    # centro de la cabeza
    y: float
    figure: float
    up: bool
    colour: str
    head_width: float
    #: A qué grupo de barra pertenece, o None si va con bandera.
    group: Optional[Tuple] = None
    dotted: bool = False
    tags: Tuple[str, ...] = ()


class Engraver:
    """
    Los signos de una partitura sobre un lienzo de Tk, a un tamaño dado.

    Todo se mide en **espacios de pentagrama** y se convierte acá: la misma
    cuenta sirve para el pentagrama de una línea (veinte píxeles por
    espacio) y para el sistema (dieciséis). Con la fuente musical cada signo
    es un carácter; sin ella, el trazo que se usaba antes.
    """

    def __init__(self, canvas: tk.Canvas, space: float):
        self.canvas = canvas
        self.space = float(space)
        loaded = music_font(canvas, int(round(4 * space)))
        self.font, self.ascent = loaded if loaded else (None, 0)
        self.stem_width = max(1, int(round(STEM_THICKNESS * space + 0.4)))
        self._braces: Dict[int, Optional[Tuple[Tuple[str, int], int]]] = {}

    @property
    def engraved(self) -> bool:
        """¿Se dibuja con la fuente? Si no, con trazos."""
        return self.font is not None

    def width(self, name: str) -> float:
        return WIDTHS[name] * self.space

    def glyph(self, x: float, y: float, name: str, colour: str,
              tags: Sequence[str] = ()) -> int:
        """
        Un signo con su origen en (x, y), como lo define SMuFL.

        Tk no ancla un texto en su línea de base, así que se lo ancla en la
        esquina de arriba y se lo sube lo que mide el ascenso de la fuente.
        """
        return self.canvas.create_text(
            x, y - self.ascent, text=GLYPHS[name], font=self.font,
            fill=colour, anchor="nw", tags=tuple(tags))

    # -- las piezas de una nota --------------------------------------------

    def head_width(self, figure: float) -> float:
        return self.width(_head_glyph(figure))

    def head(self, x: float, y: float, figure: float, colour: str,
             tags: Sequence[str] = ()) -> None:
        """Una cabeza centrada en (x, y)."""
        name = _head_glyph(figure)
        if self.engraved:
            self.glyph(x - self.width(name) / 2.0, y, name, colour, tags)
            return
        rx, ry = 0.5 * self.space, 0.36 * self.space
        self.canvas.create_oval(x - rx, y - ry, x + rx, y + ry,
                                fill=colour if figure < 2.0 else "",
                                outline=colour, width=2, tags=tuple(tags))

    def dot(self, x: float, y: float, colour: str,
            tags: Sequence[str] = ()) -> None:
        """El puntillo, con su borde izquierdo en x."""
        if self.engraved:
            self.glyph(x, y, "augmentationDot", colour, tags)
            return
        r = 0.18 * self.space
        self.canvas.create_oval(x, y - r, x + 2 * r, y + r, fill=colour,
                                outline=colour, tags=tuple(tags))

    def accidental(self, right: float, y: float, value: int, colour: str,
                   tags: Sequence[str] = ()) -> float:
        """Un accidente con su borde derecho en `right`. Devuelve el izquierdo."""
        name = ACCIDENTAL_GLYPHS.get(value)
        if name is None:
            return right
        left = right - self.width(name)
        if self.engraved:
            self.glyph(left, y, name, colour, tags)
        else:
            self.canvas.create_text(
                (left + right) / 2.0, y, text=ACCIDENTAL_TEXT[value],
                fill=colour, font=("Segoe UI Symbol",
                                   max(9, int(round(0.95 * self.space)))),
                tags=tuple(tags))
        return left

    def flag(self, stem_x: float, end_y: float, up: bool, figure: float,
             colour: str, tags: Sequence[str] = ()) -> None:
        """La bandera, colgada de la punta de la plica."""
        levels = _beam_levels(figure)
        if not levels:
            return
        left = stem_x - self.stem_width / 2.0
        if self.engraved:
            name = {1: "flag8th", 2: "flag16th", 3: "flag32nd"}[levels]
            name += "Up" if up else "Down"
            # El origen de la bandera no es exactamente la punta de la
            # plica: SMuFL dice dónde se pega (`stemUpNW`, `stemDownSW`,
            # en espacios y con la y para arriba), y el origen queda donde
            # ese ancla cae sobre la punta.
            anchor = {"flag8thUp": -0.04, "flag16thUp": -0.088,
                      "flag32ndUp": 0.376, "flag8thDown": 0.132,
                      "flag16thDown": 0.128, "flag32ndDown": -0.448}[name]
            self.glyph(left, end_y + anchor * self.space, name, colour, tags)
            return
        reach = 0.9 * self.space
        for level in range(levels):
            offset = level * 0.6 * self.space * (1 if up else -1)
            self.canvas.create_line(
                stem_x, end_y + offset, stem_x + reach,
                end_y + offset + (1.1 if up else -1.1) * self.space,
                fill=colour, width=2, tags=tuple(tags))

    def stem(self, x: float, y1: float, y2: float, colour: str,
             tags: Sequence[str] = ()) -> None:
        self.canvas.create_line(x, y1, x, y2, fill=colour,
                                width=self.stem_width, tags=tuple(tags))

    def stem_x(self, note: EngravedNote) -> float:
        """La plica va del lado derecho subiendo y del izquierdo bajando."""
        half = note.head_width / 2.0 - self.stem_width / 2.0
        return note.x + half if note.up else note.x - half

    def stems(self, notes: Sequence[EngravedNote], length: float,
              reach: Optional[float] = None,
              beam_colour: Optional[str] = None,
              ceiling: Optional[float] = None) -> None:
        """
        Plicas, banderas y barras de una línea de notas.

        Las notas de un mismo grupo ---corcheas y menores dentro de un mismo
        tiempo--- van unidas por una barra; una sola en su tiempo lleva
        bandera. `reach` es la altura de la línea del medio: una plica de
        una nota lejos del pentagrama llega por lo menos hasta ahí, que es
        la regla de cualquier grabado. `ceiling` es hasta dónde puede subir
        una plica: en el sistema, el renglón del cifrado americano. Para no
        pisarlo la plica se acorta, pero no por debajo de `MIN_STEM_LENGTH`.
        """
        index = 0
        while index < len(notes):
            note = notes[index]
            group = [note]
            if note.group is not None and _beam_levels(note.figure):
                while (index + len(group) < len(notes)
                       and notes[index + len(group)].group == note.group
                       and _beam_levels(notes[index + len(group)].figure)):
                    group.append(notes[index + len(group)])
            if len(group) > 1:
                self._beamed(group, length, beam_colour, ceiling)
            else:
                self._single(note, length, reach, ceiling)
            index += len(group)

    def _single(self, note: EngravedNote, length: float,
                reach: Optional[float],
                ceiling: Optional[float] = None) -> None:
        if note.figure >= 4.0:
            return
        x = self.stem_x(note)
        attach = STEM_ATTACH * self.space
        if note.up:
            start, end = note.y - attach, note.y - length * self.space
            if reach is not None:
                end = min(end, reach)
            if ceiling is not None:
                end = max(end, min(ceiling,
                                   note.y - MIN_STEM_LENGTH * self.space))
        else:
            start, end = note.y + attach, note.y + length * self.space
            if reach is not None:
                end = max(end, reach)
        self.stem(x, start, end, note.colour, note.tags)
        self.flag(x, end, note.up, note.figure, note.colour, note.tags)

    def _beamed(self, group: Sequence[EngravedNote], length: float,
                beam_colour: Optional[str] = None,
                ceiling: Optional[float] = None) -> None:
        """
        Un grupo unido por barras.

        La barra sigue la dirección de la melodía, pero recortada: copiando
        el salto entero, dos corcheas a distancia de octava quedan unidas
        por una rampa. Y se corre entera hasta que la plica más corta mida
        lo que tiene que medir.
        """
        up = group[0].up
        xs = [self.stem_x(note) for note in group]
        first, last = group[0], group[-1]
        span = max(1.0, xs[-1] - xs[0])
        rise = last.y - first.y
        limit = min(MAX_BEAM_SLANT * self.space, MAX_BEAM_SLOPE * span)
        rise = max(-limit, min(limit, rise))
        slope = rise / span
        reach = length * self.space
        if up:
            base = min(note.y - slope * (x - xs[0])
                       for note, x in zip(group, xs)) - reach
        else:
            base = max(note.y - slope * (x - xs[0])
                       for note, x in zip(group, xs)) + reach
        if up and ceiling is not None:
            # La barra baja entera hasta quedar debajo del techo, mientras
            # la plica más corta siga midiendo lo mínimo.
            highest = min(base + slope * (x - xs[0]) for x in xs)
            room = min(note.y - MIN_STEM_LENGTH * self.space
                       - (base + slope * (x - xs[0]))
                       for note, x in zip(group, xs))
            shift = min(ceiling - highest, room)
            if shift > 0:
                base += shift

        def beam_y(x: float) -> float:
            return base + slope * (x - xs[0])

        attach = STEM_ATTACH * self.space
        for note, x in zip(group, xs):
            start = note.y - attach if up else note.y + attach
            self.stem(x, start, beam_y(x), note.colour, note.tags)

        thick = BEAM_THICKNESS * self.space
        step = (BEAM_THICKNESS + BEAM_SPACING) * self.space
        inward = 1.0 if up else -1.0
        half = self.stem_width / 2.0
        # Una barra une notas que pueden estar pintadas distinto ---una
        # dorada y una blanca---; quien dibuja decide de qué color va, y si
        # no dice nada va con la primera.
        colour = beam_colour or group[0].colour
        tags = group[0].tags
        levels = [_beam_levels(note.figure) for note in group]
        # La primera barra, entera.
        self._beam(xs[0] - half, xs[-1] + half, beam_y, 0.0, thick, inward,
                   colour, tags)
        # Las demás, entre vecinas que las llevan las dos, o un muñón hacia
        # la vecina cuando la lleva sola (la semicorchea de un puntillo).
        stub = 1.1 * self.space
        for level in range(2, 4):
            offset = (level - 1) * step
            position = 0
            while position < len(group):
                if levels[position] < level:
                    position += 1
                    continue
                end = position
                while end + 1 < len(group) and levels[end + 1] >= level:
                    end += 1
                if end > position:
                    self._beam(xs[position] - half, xs[end] + half, beam_y,
                               offset, thick, inward, colour, tags)
                else:
                    # El muñón mira hacia la nota con la que se cuenta: la
                    # de antes si es la última del grupo o si viene detrás
                    # de un puntillo, la de después si no.
                    towards_left = (position == len(group) - 1
                                    or (position > 0
                                        and group[position - 1].dotted))
                    x = xs[position]
                    if towards_left:
                        self._beam(x - stub, x + half, beam_y, offset, thick,
                                   inward, colour, tags)
                    else:
                        self._beam(x - half, x + stub, beam_y, offset, thick,
                                   inward, colour, tags)
                position = end + 1

    def _beam(self, x1: float, x2: float, beam_y: Callable[[float], float],
              offset: float, thick: float, inward: float, colour: str,
              tags: Sequence[str]) -> None:
        y1 = beam_y(x1) + offset * inward
        y2 = beam_y(x2) + offset * inward
        self.canvas.create_polygon(
            x1, y1, x2, y2, x2, y2 + thick * inward, x1, y1 + thick * inward,
            fill=colour, outline=colour, width=1, tags=tuple(tags))

    # -- silencios ----------------------------------------------------------

    def rest(self, x: float, middle: float, duration: float, colour: str,
             tags: Sequence[str] = ()) -> None:
        """
        Un silencio centrado en x, sobre la línea del medio de su renglón.

        La redonda cuelga de la línea de arriba y la blanca se apoya en la
        del medio, que es donde SMuFL pone el origen de cada una.
        """
        figure, dots = figure_of(duration)
        name = {4.0: "restWhole", 2.0: "restHalf", 1.0: "restQuarter",
                0.5: "rest8th", 0.25: "rest16th"}.get(figure, "rest32nd")
        width = self.width(name)
        if self.engraved:
            base = middle - self.space if name == "restWhole" else middle
            self.glyph(x - width / 2.0, base, name, colour, tags)
        else:
            self._stroked_rest(x, middle, figure, colour, tags)
        for dot in range(dots):
            self.dot(x + width / 2.0 + (0.3 + 0.6 * dot) * self.space,
                     middle - 0.5 * self.space, colour, tags)

    def _stroked_rest(self, x: float, y: float, figure: float, colour: str,
                      tags: Sequence[str]) -> None:
        """
        El silencio dibujado con trazos, para cuando la fuente no está.

        Con caracteres de Unicode no se podía: los musicales no están en
        todas las fuentes de sistema, y el que falta se dibuja como un
        rectángulo vacío. Cuatro trazos son más confiables que una fuente
        que puede no estar.
        """
        canvas = self.canvas
        tags = tuple(tags)
        s = self.space / 16.0
        if figure >= 4.0:
            canvas.create_rectangle(x - 7 * s, y - 8 * s, x + 7 * s, y - 2 * s,
                                    fill=colour, outline="", tags=tags)
        elif figure >= 2.0:
            canvas.create_rectangle(x - 7 * s, y + 1 * s, x + 7 * s, y + 7 * s,
                                    fill=colour, outline="", tags=tags)
        elif figure >= 1.0:
            canvas.create_line(x - 4 * s, y - 12 * s, x + 4 * s, y - 4 * s,
                               fill=colour, width=3, tags=tags)
            canvas.create_line(x + 4 * s, y - 4 * s, x - 4 * s, y + 3 * s,
                               fill=colour, width=3, tags=tags)
            canvas.create_line(x - 4 * s, y + 3 * s, x + 5 * s, y + 11 * s,
                               fill=colour, width=3, tags=tags)
        else:
            canvas.create_line(x + 4 * s, y - 9 * s, x - 4 * s, y + 9 * s,
                               fill=colour, width=2, tags=tags)
            canvas.create_oval(x + 1 * s, y - 12 * s, x + 6 * s, y - 7 * s,
                               fill=colour, outline=colour, tags=tags)
            if figure <= 0.25:
                canvas.create_oval(x - 2 * s, y - 4 * s, x + 3 * s, y + 1 * s,
                                   fill=colour, outline=colour, tags=tags)

    # -- el encabezado ------------------------------------------------------

    def clef_width(self, treble: bool) -> float:
        return self.width("gClef" if treble else "fClef")

    def clef(self, x: float, line_y: float, treble: bool, colour: str,
             tags: Sequence[str] = ()) -> None:
        """
        Una clave con su borde izquierdo en x.

        `line_y` es la línea que la clave nombra: la segunda (sol) o la
        cuarta (fa). Ahí va el origen del signo, que es lo que la hace
        decir lo que dice.
        """
        if self.engraved:
            self.glyph(x, line_y, "gClef" if treble else "fClef", colour, tags)
            return
        # Sin la fuente, los caracteres de siempre, corridos a ojo: el signo
        # no está centrado en su propio cuadro.
        if treble:
            self.canvas.create_text(
                x + self.clef_width(True) / 2.0, line_y - 1.0 * self.space,
                text="𝄞", fill=colour,
                font=("Segoe UI Symbol", int(round(2.6 * self.space))),
                tags=tuple(tags))
        else:
            self.canvas.create_text(
                x + self.clef_width(False) / 2.0, line_y + 0.6 * self.space,
                text="𝄢", fill=colour,
                font=("Segoe UI Symbol", int(round(2.1 * self.space))),
                tags=tuple(tags))

    def number_width(self, value: int) -> float:
        return sum(self.width(f"timeSig{digit}") for digit in str(value))

    def number(self, centre: float, y: float, value: int, colour: str,
               tags: Sequence[str] = ()) -> None:
        """Un número de compás centrado en `centre`, con su centro en y."""
        if self.engraved:
            x = centre - self.number_width(value) / 2.0
            for digit in str(value):
                self.glyph(x, y, f"timeSig{digit}", colour, tags)
                x += self.width(f"timeSig{digit}")
            return
        self.canvas.create_text(
            centre, y, text=tr(str(value)), fill=colour,
            font=("Segoe UI Semibold", max(9, int(round(0.85 * self.space)))),
            tags=tuple(tags))

    def metre_width(self, beats: int, beat_type: int) -> float:
        return max(self.number_width(beats), self.number_width(beat_type))

    def brace(self, x: float, top: float, bottom: float, colour: str,
              tags: Sequence[str] = ()) -> float:
        """La llave del sistema. Devuelve hasta dónde llega a la derecha."""
        height = int(round(bottom - top))
        if height not in self._braces:
            self._braces[height] = music_font(self.canvas, height)
        loaded = self._braces[height]
        if loaded is None:
            self.canvas.create_line(x + 6, top, x + 6, bottom, fill=colour,
                                    width=3, tags=tuple(tags))
            return x + 8
        font, ascent = loaded
        self.canvas.create_text(x, bottom - ascent, text=GLYPHS["brace"],
                                font=font, fill=colour, anchor="nw",
                                tags=tuple(tags))
        return x + WIDTHS["brace"] * height / 4.0


def beam_unit(beats: int, beat_type: int) -> float:
    """
    Cuánto abarca una barra de corcheas, en negras.

    Un tiempo: las corcheas de un cuatro por cuatro van de a dos, y las de
    un seis por ocho de a tres, porque el tiempo de un compás compuesto es
    la negra con puntillo.
    """
    if beat_type == 8 and beats % 3 == 0:
        return 1.5
    return 4.0 / beat_type


def displayed_accidentals(
    notes: Sequence[Tuple[object, float, int, int, object]],
    fifths: int,
) -> Dict[object, Optional[int]]:
    """
    Qué accidente se **escribe** delante de cada nota, compás por compás.

    Recibe (orden en el tiempo, comienzo de su compás, posición en el
    pentagrama, altura MIDI, nombre) y devuelve, por nombre, el accidente
    a dibujar o None. Se recorren en el orden del tiempo y no en el de la
    lista: lo que rige al llegar a una nota es lo que sonó **antes**.

    Una alteración dura hasta la barra: un sol sostenido seguido de un sol
    natural en el mismo compás pide un becuadro, aunque el sol natural no
    tenga ningún accidente propio --- sin él, quien lee la partitura canta
    otro sol sostenido. Y repetir el mismo sostenido dentro del compás no
    lo vuelve a escribir. Es sólo cómo se dibuja: lo que suena es la altura
    de cada nota, que no cambia.
    """
    shown: Dict[object, Optional[int]] = {}
    state: Dict[Tuple[float, int], int] = {}
    for _order, bar_start, index, pitch, key in sorted(
            notes, key=lambda item: item[0]):
        natural = pitch_at(index, fifths, 0)
        alteration = pitch - natural
        current = state.get((bar_start, index))
        if current is None:
            current = index_to_pitch(index, fifths) - natural
        if alteration != current:
            shown[key] = max(-2, min(2, alteration))
            state[(bar_start, index)] = alteration
        else:
            shown[key] = None
    return shown


class StaffEditor(ctk.CTkFrame):
    """A single-line staff the user can click notes onto."""

    def __init__(
        self,
        master,
        colours: Dict[str, str],
        on_change: Optional[Callable[[], None]] = None,
        treble: bool = True,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.colours = colours
        self.on_change = on_change
        self.treble = treble
        self.fifths = 0
        self.beats = 4
        self.beat_type = 4
        self.duration = 1.0
        #: (staff index, duration) pairs, in order.
        self.notes: List[Tuple[int, float]] = []
        #: El accidente escrito de cada nota, por posición: 1 sostenido, -1
        #: bemol, 0 becuadro. La que no está sigue a la armadura. Va aparte
        #: de `notes` y no adentro de cada par porque `notes` lo lee y lo
        #: escribe la aplicación entera como pares, y un tercer elemento
        #: rompía cada uno de esos lugares.
        self.accidentals: Dict[int, int] = {}
        #: El accidente que va a llevar la próxima nota escrita con el
        #: mouse, o None. Vale para una nota sola, como en el papel.
        self.pending: Optional[int] = None
        #: Posiciones que van a recibir un acorde. Las calcula el programa a
        #: partir de la melodía escrita y se repintan en cada cambio; el
        #: pentagrama sólo las dibuja.
        self.harmonised: Set[int] = set()
        #: Posiciones que el usuario marcó a mano. Son un pedido y no un
        #: cálculo: reciben un acorde caigan donde caigan.
        self.marked: Set[int] = set()
        #: Posiciones que el usuario apagó a mano. Son el pedido contrario:
        #: acá NO va acorde, aunque el programa lo hubiera puesto solo. Sin
        #: esto el dorado calculado no se podía discutir --- el click sobre
        #: una nota que el programa ya iba a armonizar sólo podía agregarle
        #: un anillo, nunca sacarle el acorde.
        self.blocked: Set[int] = set()
        #: Mientras está en True, un click marca en vez de escribir.
        self.marking = False
        self._engraver: Optional[Engraver] = None
        #: Lo que hay dibujado, para no volver a dibujar lo mismo. La
        #: aplicación redibuja dos veces por cada nota ---al escribirla y al
        #: recalcular cuáles llevan acorde---, y la segunda casi nunca cambia
        #: nada.
        self._drawn: Optional[tuple] = None

        self.canvas = tk.Canvas(self, height=STAFF_HEIGHT, highlightthickness=0,
                                bg=colours["surface"])
        # La barra va debajo del pentagrama y sólo se ve cuando hace falta.
        # Apretar las notas hasta que entren tiene un límite --- por debajo
        # de `MIN_SPACING` una cabeza de nota se confunde con la vecina ---
        # y pasado ese punto la melodía se salía por el borde derecho: las
        # últimas notas existían en el modelo y no en la pantalla.
        self.scrollbar = ctk.CTkScrollbar(
            self, orientation="horizontal", command=self.canvas.xview,
            height=12, button_color=colours["muted"],
            button_hover_color=colours["accent"], fg_color="transparent")
        self.canvas.configure(xscrollcommand=self._on_scrolled)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        # El click derecho marca sin tener que prender nada: es el atajo del
        # botón de marcar, para quien ya sabe lo que quiere.
        self.canvas.bind("<Button-3>", self._on_mark_click)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    @property
    def engraver(self) -> Engraver:
        """El grabador del lienzo, armado la primera vez que se dibuja."""
        if self._engraver is None:
            self._engraver = Engraver(self.canvas, LINE_GAP)
        return self._engraver

    # -- the ladder ---------------------------------------------------------

    @property
    def _top_index(self) -> int:
        """Staff index of the topmost line."""
        return diatonic_index("F", 5) if self.treble else diatonic_index("A", 3)

    def _y_for(self, index: int) -> float:
        return TOP_MARGIN + (self._top_index - index) * STEP

    def _index_for(self, y: float) -> int:
        return int(round(self._top_index - (y - TOP_MARGIN) / STEP))

    # -- el encabezado ------------------------------------------------------

    #: Dónde arranca la clave.
    CLEF_X = 24

    def _header(self) -> Tuple[float, float, float]:
        """Dónde van la armadura y el compás, y dónde empiezan las notas.

        Se mide con los anchos de la fuente aunque se dibuje con trazos: la
        cuenta del click no puede depender de qué fuente encontró Windows.
        """
        space = float(LINE_GAP)
        clef = WIDTHS["gClef" if self.treble else "fClef"] * space
        key_x = self.CLEF_X + clef + 0.8 * space
        count = min(7, abs(self.fifths))
        sign = "accidentalSharp" if self.fifths > 0 else "accidentalFlat"
        advance = (WIDTHS[sign] + 0.12) * space
        metre_x = key_x + count * advance + (0.6 * space if count else 0.0)
        metre_width = max(sum(WIDTHS[f"timeSig{d}"] for d in str(self.beats)),
                          sum(WIDTHS[f"timeSig{d}"]
                              for d in str(self.beat_type))) * space
        left = max(float(LEFT_MARGIN), metre_x + metre_width + 1.2 * space)
        return key_x, metre_x, left

    def left_margin(self) -> float:
        """Dónde empieza la primera nota."""
        return self._header()[2]

    # -- editing ------------------------------------------------------------

    def spacing(self) -> float:
        """
        Cuánto ocupa cada nota, apretándose cuando hay muchas.

        A la separación cómoda una melodía larga se salía por el borde
        derecho y las últimas notas simplemente no existían para el ojo.
        Repartir el ancho disponible entre las notas escritas las mantiene
        todas a la vista, pero sólo hasta `MIN_SPACING`: por debajo de eso
        una cabeza de nota se toca con la siguiente y una sol escrita se lee
        como un la, que es peor que tener que desplazarse. Pasado ese punto
        la separación se planta y el pentagrama se corre de costado.
        """
        count = len(self.notes)
        if count <= 1:
            return float(NOTE_SPACING)
        usable = max(200, self.canvas.winfo_width() - self.left_margin() - 40)
        return max(MIN_SPACING, min(float(NOTE_SPACING), usable / count))

    def content_width(self) -> float:
        """Cuánto mide el pentagrama escrito, entre en la ventana o no."""
        return self.left_margin() + len(self.notes) * self.spacing() + 40

    # -- desplazamiento -----------------------------------------------------

    def _on_scrolled(self, first: str, last: str) -> None:
        """Mostrar la barra sólo mientras haya algo fuera de la ventana."""
        self.scrollbar.set(first, last)
        needed = float(first) > 0.0 or float(last) < 1.0
        try:
            if needed and not self.scrollbar.winfo_manager():
                self.scrollbar.pack(fill="x", side="bottom", pady=(2, 0))
            elif not needed and self.scrollbar.winfo_manager():
                self.scrollbar.pack_forget()
        except tk.TclError:
            pass

    def _on_wheel(self, event) -> None:
        """La rueda mueve el pentagrama de costado: es lo único que se mueve."""
        try:
            if self.canvas.bbox("all") is None:
                return
            self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        except tk.TclError:
            pass

    def _position_at(self, event) -> int:
        """Qué nota escrita cae bajo el mouse, o -1 si el click fue al aire.

        En coordenadas del lienzo, no de la ventana: con el pentagrama
        corrido, `event.x` es dónde cayó el mouse en la pantalla y no sobre
        qué nota, así que escribir después de desplazarse pisaba una nota
        anterior.
        """
        x = self.canvas.canvasx(event.x)
        left = self.left_margin()
        if x < left:
            return -1
        return int((x - left) // self.spacing())

    def toggle_mark(self, position: int) -> bool:
        """Prender o apagar el acorde sobre una nota.

        Rota entre los dos estados que se ven, no entre los tres que hay
        adentro: dorada o no dorada. Da igual si el dorado lo puso el
        usuario o lo calculó el programa --- el click apaga lo que esté
        encendido y enciende lo que esté apagado, que es lo único que se
        puede predecir mirando la pantalla.
        """
        if not 0 <= position < len(self.notes):
            return False
        if position in self.marked or position in self.harmonised:
            self.marked.discard(position)
            self.blocked.add(position)
        else:
            self.blocked.discard(position)
            self.marked.add(position)
        self.redraw()
        if self.on_change:
            self.on_change()
        return True

    def _on_mark_click(self, event) -> None:
        self.toggle_mark(self._position_at(event))

    def _on_click(self, event) -> None:
        position = self._position_at(event)
        if position < 0:
            return
        # Con el modo de marcar prendido, el pentagrama no se escribe: cada
        # click prende o apaga el dorado. Es un modo y no un click distinto
        # porque el click de escribir ya hace dos cosas ---poner una nota y
        # corregir la que estuviera--- y agregarle una tercera lo volvía
        # imposible de predecir.
        if self.marking:
            self.toggle_mark(position)
            return
        index = self._index_for(self.canvas.canvasy(event.y))
        # Keep it inside something singable rather than letting a stray click
        # put a note six ledger lines out.
        lowest, highest = self._top_index - 20, self._top_index + 6
        index = max(lowest, min(highest, index))
        accidental = self._normalised(index, self.pending)
        self.pending = None

        if position < len(self.notes):
            # Se reescribe entera, altura y figura. Manteniendo la figura
            # vieja no había forma de corregirla: elegir otra y volver a
            # tocar la nota no hacía nada, y sólo quedaba deshacer hasta
            # llegar a ella. La figura marcada es la herramienta activa.
            self.notes[position] = (index, self.duration)
        else:
            position = len(self.notes)
            self.notes.append((index, self.duration))
        self._set_accidental(position, accidental)
        self.redraw()
        if self.on_change:
            self.on_change()

    def _normalised(self, index: int, accidental: Optional[int]
                    ) -> Optional[int]:
        """El accidente que hay que guardar: ninguno si la armadura ya lo dice."""
        if accidental is None:
            return None
        if pitch_at(index, self.fifths, accidental) == index_to_pitch(
                index, self.fifths):
            return None
        return accidental

    def _set_accidental(self, position: int, accidental: Optional[int]) -> None:
        if accidental is None:
            self.accidentals.pop(position, None)
        else:
            self.accidentals[position] = accidental

    def add_pitch(self, midi: int) -> None:
        """Add a note chosen from the piano rather than the staff.

        Con la altura exacta, accidente incluido. Antes se buscaba la letra
        más cercana y una tecla negra se escribía como la blanca de al lado:
        el piano tenía doce notas y el pentagrama siete.
        """
        index = index_for_pitch(midi, self.fifths)
        position = len(self.notes)
        self.notes.append((index, self.duration))
        self._set_accidental(position, accidental_for(midi, index, self.fifths))
        self.redraw()
        if self.on_change:
            self.on_change()

    def undo(self) -> None:
        if self.notes:
            self.notes.pop()
            # La marca se va con la nota: si no, la siguiente que se escriba
            # en ese lugar nacería marcada sin que nadie la haya tocado.
            self.marked.discard(len(self.notes))
            self.blocked.discard(len(self.notes))
            self.accidentals.pop(len(self.notes), None)
            self.redraw()
            if self.on_change:
                self.on_change()

    def clear(self) -> None:
        self.notes = []
        self.marked = set()
        self.blocked = set()
        self.harmonised = set()
        self.accidentals = {}
        self.redraw()
        if self.on_change:
            self.on_change()

    def set_key(self, fifths: int, beats: int, beat_type: int) -> None:
        self.fifths = fifths
        self.beats = beats
        self.beat_type = beat_type
        self.redraw()

    # -- what the harmoniser needs -----------------------------------------

    def pitch_of(self, position: int) -> int:
        """La altura de una nota escrita, con su accidente si lo lleva."""
        index, _duration = self.notes[position]
        return pitch_at(index, self.fifths, self.accidentals.get(position))

    def pitches(self) -> List[Tuple[int, float]]:
        """(MIDI pitch, duration) for every note written."""
        return [(self.pitch_of(position), duration)
                for position, (_index, duration) in enumerate(self.notes)]

    def total_quarters(self) -> float:
        return sum(duration for _index, duration in self.notes)

    def out_of_scale(self, position: int) -> bool:
        """¿Esa nota cae fuera de la escala de la armadura?"""
        return self.pitch_of(position) % 12 not in scale_of(self.fifths)

    # -- drawing ------------------------------------------------------------

    def _signature(self) -> tuple:
        """Todo lo que cambia el dibujo, y nada más."""
        return (tuple(self.notes), tuple(sorted(self.accidentals.items())),
                frozenset(self.harmonised), frozenset(self.marked),
                frozenset(self.blocked), self.fifths, self.beats,
                self.beat_type, self.treble, self.canvas.winfo_width(),
                tuple(sorted(self.colours.items())))

    def redraw(self) -> None:
        signature = self._signature()
        if signature == self._drawn and self.canvas.find_all():
            return
        self._drawn = signature
        self._redraw()

    def _redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        engraver = self.engraver
        space = float(LINE_GAP)
        ink = self.colours["text"]
        faint = self.colours["muted"]

        width = max(canvas.winfo_width(), 400, int(self.content_width()))
        top = self._y_for(self._top_index)
        for line in range(5):
            y = top + line * LINE_GAP
            canvas.create_line(20, y, width - 20, y, fill=faint)

        key_x, metre_x, left = self._header()
        clef_line = top + (3 if self.treble else 1) * LINE_GAP
        engraver.clef(self.CLEF_X, clef_line, self.treble, ink)
        # The key signature, written where it belongs: without it the user
        # cannot see which notes are altered, and a written F reads the same
        # whether it sounds as F or F sharp.
        if self.fifths:
            order = SHARP_ORDER if self.fifths > 0 else FLAT_ORDER
            value = 1 if self.fifths > 0 else -1
            sign = ACCIDENTAL_GLYPHS[value]
            advance = (WIDTHS[sign] + 0.12) * space
            # Standard placement: sharps and flats sit on set lines and
            # spaces, in a fixed order, rather than wherever the note falls.
            positions = (self._sharp_positions() if self.fifths > 0
                         else self._flat_positions())
            x = key_x
            for step in range(min(7, abs(self.fifths))):
                y = self._y_for(positions[order[step]])
                engraver.accidental(x + WIDTHS[sign] * space, y, value, ink)
                x += advance
        metre_centre = metre_x + engraver.metre_width(
            self.beats, self.beat_type) / 2.0
        engraver.number(metre_centre, top + LINE_GAP, self.beats, ink)
        engraver.number(metre_centre, top + 3 * LINE_GAP, self.beat_type, ink)

        # Bar lines fall wherever the written durations fill a bar.
        quarters_per_bar = self.beats * 4.0 / self.beat_type
        unit = beam_unit(self.beats, self.beat_type)
        step_x = self.spacing()
        middle_index = self._top_index - 4
        middle_y = self._y_for(middle_index)
        scale = scale_of(self.fifths)

        # Qué accidente se escribe delante de cada nota: el de la nota si
        # cambia lo que rige en ese compás, y nada si ya rige.
        running = 0.0
        placed = []
        for position, (index, duration) in enumerate(self.notes):
            bar_start = math.floor(running / quarters_per_bar + 1e-9) \
                * quarters_per_bar
            placed.append((position, bar_start, index, self.pitch_of(position),
                           position))
            running += duration
        shown = displayed_accidentals(placed, self.fifths)

        running = 0.0
        heads: List[EngravedNote] = []
        for position, (index, duration) in enumerate(self.notes):
            figure, dots = figure_of(duration)
            column = left + position * step_x + step_x / 2
            y = self._y_for(index)
            pitch = self.pitch_of(position)
            sign = shown.get(position)
            head_width = engraver.head_width(figure)
            x = column
            if sign is not None:
                # Un accidente delante pide aire: con las notas apretadas se
                # dibujaba encima de la anterior. La cabeza se corre dentro de
                # su propia columna, que es donde la busca el click.
                needed = (head_width / 2.0 + 0.18 * space
                          + WIDTHS[ACCIDENTAL_GLYPHS[sign]] * space + 2.0)
                room = step_x - head_width / 2.0
                x += max(0.0, min(needed - room,
                                  step_x / 2.0 - head_width / 2.0 - 2.0))

            # Dorada la nota que va a recibir un acorde. Es lo único que
            # contesta la pregunta con la que se escribe una melodía para
            # que otro la armonice: cuál de estas notas va a sostener la
            # armonía y cuál va a pasar por encima de ella. Y naranja la que
            # está fuera de la escala, con el halo dorado detrás si además
            # lleva acorde: ver `note_look`.
            look = note_look(pitch % 12 not in scale,
                             position in self.marked
                             or position in self.harmonised,
                             position in self.marked, self.colours)
            if look.halo is not None:
                rx, ry = head_width / 2.0 + 0.36 * space, 0.82 * space
                canvas.create_oval(x - rx, y - ry, x + rx, y + ry,
                                   fill=look.halo, outline="")
            if look.ring is not None:
                # Un anillo alrededor de la cabeza: la marcó el usuario, y
                # sin él marcar una nota que el programa ya iba a armonizar
                # no se veía --- el click quedaba sin respuesta.
                rx, ry = head_width / 2.0 + 0.6 * space, 1.02 * space
                canvas.create_oval(x - rx, y - ry, x + rx, y + ry,
                                   outline=look.ring, width=1)
            self._draw_ledgers(x, index, head_width, faint)
            if sign is not None:
                engraver.accidental(x - head_width / 2.0 - 0.18 * space, y,
                                    sign, look.head)
            engraver.head(x, y, figure, look.head)
            on_line = (self._top_index - index) % 2 == 0
            for dot in range(dots):
                # Sobre una línea, el puntillo sube al espacio de arriba:
                # puesto sobre la línea no se lo distingue de ella.
                engraver.dot(x + head_width / 2.0 + (0.3 + 0.6 * dot) * space,
                             y - (STEP if on_line else 0), look.head)

            bar_start = math.floor(running / quarters_per_bar + 1e-9) \
                * quarters_per_bar
            group = (bar_start, math.floor((running - bar_start) / unit + 1e-9))
            heads.append(EngravedNote(
                x=x, y=y, figure=figure, up=index < middle_index,
                colour=look.head, head_width=head_width, group=group,
                dotted=dots > 0))

            running += duration
            if abs(running % quarters_per_bar) < 1e-6:
                bar_x = left + (position + 1) * step_x
                canvas.create_line(bar_x, top, bar_x, top + 4 * LINE_GAP,
                                   fill=faint, width=2)

        self._draw_stems(heads, middle_y)

        canvas.configure(scrollregion=(0, 0, width, STAFF_HEIGHT))
        if not self.notes:
            canvas.create_text(max(canvas.winfo_width(), 400) / 2,
                               top + 2 * LINE_GAP + 60,
                               text=tr("Hacé click en el pentagrama para escribir "
                                       "la melodía"),
                               fill=faint, font=("Segoe UI", 12))

    def _draw_stems(self, heads: List[EngravedNote], middle_y: float) -> None:
        """
        Las plicas, con la dirección de cada grupo decidida entera.

        Una nota sola mira hacia el lado contrario de donde está: plica para
        arriba debajo de la línea del medio. Un grupo de corcheas mira
        entero hacia el mismo lado, el que pide la nota más alejada del
        medio --- las dos direcciones mezcladas debajo de una misma barra no
        existen.
        """
        index = 0
        while index < len(heads):
            note = heads[index]
            end = index + 1
            if _beam_levels(note.figure):
                while (end < len(heads) and heads[end].group == note.group
                       and _beam_levels(heads[end].figure)):
                    end += 1
            group = heads[index:end]
            if len(group) > 1:
                far = max(group, key=lambda n: abs(n.y - middle_y))
                up = far.y > middle_y
                for member in group:
                    member.up = up
            index = end
        self.engraver.stems(heads, STEM_LENGTH, reach=middle_y,
                            beam_colour=self.colours["text"])

    def _sharp_positions(self) -> Dict[str, int]:
        """Where each sharp is written, by letter."""
        octave = 5 if self.treble else 3
        base = {"F": diatonic_index("F", octave), "C": diatonic_index("C", octave),
                "G": diatonic_index("G", octave), "D": diatonic_index("D", octave),
                "A": diatonic_index("A", octave - 1),
                "E": diatonic_index("E", octave), "B": diatonic_index("B", octave - 1)}
        return base

    def _flat_positions(self) -> Dict[str, int]:
        """Where each flat is written, by letter."""
        octave = 5 if self.treble else 3
        return {"B": diatonic_index("B", octave - 1),
                "E": diatonic_index("E", octave),
                "A": diatonic_index("A", octave - 1),
                "D": diatonic_index("D", octave),
                "G": diatonic_index("G", octave - 1),
                "C": diatonic_index("C", octave),
                "F": diatonic_index("F", octave - 1)}

    def _draw_ledgers(self, x: float, index: int, head_width: float,
                      colour: str) -> None:
        """Short lines for notes that sit off the staff."""
        reach = head_width / 2.0 + LEDGER_EXTENSION * LINE_GAP
        highest, lowest = self._top_index, self._top_index - 8
        step = 2
        position = highest + step
        while position <= index:
            y = self._y_for(position)
            self.canvas.create_line(x - reach, y, x + reach, y, fill=colour,
                                    width=2)
            position += step
        position = lowest - step
        while position >= index:
            y = self._y_for(position)
            self.canvas.create_line(x - reach, y, x + reach, y, fill=colour,
                                    width=2)
            position -= step


def legend_swatch(master, colours: Dict[str, str], chromatic: bool,
                  harmonised: bool, background: Optional[str] = None
                  ) -> tk.Canvas:
    """
    Una cabeza de nota suelta, pintada como en el pentagrama.

    Es para el renglón que explica los colores: dibujada por el mismo
    `note_look` que pinta la melodía, la explicación no puede decir una
    cosa y el pentagrama mostrar otra.
    """
    # Chica a propósito: va en un renglón de texto y no puede ser más alta
    # que él, o el renglón empuja fuera de la ventana lo que viene abajo.
    space = 8.0
    size = int(2.6 * space) + 2
    canvas = tk.Canvas(master, width=size + 4, height=size,
                       highlightthickness=0,
                       bg=background or colours.get("surface", "#25282F"))
    engraver = Engraver(canvas, space)
    look = note_look(chromatic, harmonised, False, colours)
    x, y = (size + 4) / 2.0, size / 2.0
    width = engraver.head_width(1.0)
    if look.halo is not None:
        rx, ry = width / 2.0 + 0.36 * space, 0.82 * space
        canvas.create_oval(x - rx, y - ry, x + rx, y + ry, fill=look.halo,
                           outline="")
    engraver.head(x, y, 1.0, look.head)
    return canvas


class MelodyPiano(ctk.CTkFrame):
    """
    A keyboard for adding one note at a time.

    Separate from the chord piano because the two ask different questions:
    that one collects pitch classes for a chord, this one needs an exact
    note in an exact octave, since a melody lives in a register.
    """

    WHITE = (0, 2, 4, 5, 7, 9, 11)
    BLACK = {1: 0, 3: 1, 6: 3, 8: 4, 10: 5}
    KEY_WIDTH = 34
    KEY_HEIGHT = 116
    BLACK_WIDTH = 21
    BLACK_HEIGHT = 72

    #: Los dos oros del titileo: el encendido y el apagado. Son los mismos
    #: de la interfaz, repetidos acá para que el widget siga sin depender de
    #: `app.py` --- igual que los colores, que llegan por parámetro.
    GLOW_ON = ("#F6EBC0", "#C7982F")
    GLOW_OFF = ("#D9AE4E", "#8A7746")

    def __init__(self, master, colours: Dict[str, str],
                 on_pick: Callable[[int], None],
                 low_octave: int = 3, octaves: int = 3,
                 highlight=None, **kwargs):
        super().__init__(master, fg_color=colours["surface"], corner_radius=8,
                         **kwargs)
        self.colours = colours
        self.on_pick = on_pick
        self.low_octave = low_octave
        self.octaves = octaves
        #: Qué teclas se resaltan: un conjunto de clases de altura, o la
        #: cadena ``"all"`` para el teclado entero. Se usa una sola vez en
        #: todo el programa --- el modo historia --- pero vive acá porque
        #: dibujar una tecla es asunto del piano y de nadie más.
        self.highlight = "all" if highlight == "all" else {
            int(pc) % 12 for pc in (highlight or ())}
        self._glowing = False

        width = self.KEY_WIDTH * 7 * octaves + 20
        self.canvas = tk.Canvas(self, height=self.KEY_HEIGHT + 20, width=width,
                                highlightthickness=0, bg=colours["surface"])
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_click)
        self._keys: List[Tuple[int, int, int, int, int]] = []
        self._draw_keys()
        if self.highlight:
            self._blink()

    def _lit(self, midi: int) -> bool:
        if self.highlight == "all":
            return True
        return bool(self.highlight) and (midi % 12) in self.highlight

    def _blink(self) -> None:
        """
        Prender y apagar el oro, hasta que el widget deje de existir.

        Medio segundo por estado: más rápido late y distrae, más lento deja
        de leerse como una invitación a tocar esa tecla.
        """
        try:
            if not self.winfo_exists():
                return
            self._glowing = not self._glowing
            self._draw_keys()
            self.after(520, self._blink)
        except tk.TclError:
            return

    def _draw_keys(self) -> None:
        """Named to avoid CustomTkinter's own ``_draw``, which it calls with
        keyword arguments this one does not take."""
        canvas = self.canvas
        canvas.delete("all")
        self._keys = []
        gold_fill, gold_edge = (self.GLOW_ON if self._glowing else self.GLOW_OFF)

        for octave in range(self.octaves):
            base = (self.low_octave + octave + 1) * 12
            for position, semitone in enumerate(self.WHITE):
                x = (octave * 7 + position) * self.KEY_WIDTH + 10
                lit = self._lit(base + semitone)
                canvas.create_rectangle(x, 10, x + self.KEY_WIDTH,
                                        10 + self.KEY_HEIGHT,
                                        fill=gold_fill if lit else "#F2F2F2",
                                        outline=gold_edge if lit else "#8A8A8A",
                                        width=2 if lit else 1)
                if semitone == 0:
                    canvas.create_text(x + self.KEY_WIDTH / 2,
                                       10 + self.KEY_HEIGHT - 10,
                                       text=f"C{self.low_octave + octave}",
                                       fill="#666", font=("Segoe UI", 8))
                self._keys.append((x, 10, x + self.KEY_WIDTH,
                                   10 + self.KEY_HEIGHT, base + semitone))

        # Black keys are drawn second so they sit on top, and searched first.
        for octave in range(self.octaves):
            base = (self.low_octave + octave + 1) * 12
            for semitone, left_white in self.BLACK.items():
                x = ((octave * 7 + left_white) * self.KEY_WIDTH + 10
                     + self.KEY_WIDTH - self.BLACK_WIDTH / 2)
                lit = self._lit(base + semitone)
                canvas.create_rectangle(x, 10, x + self.BLACK_WIDTH,
                                        10 + self.BLACK_HEIGHT,
                                        fill=gold_edge if lit else "#1A1A1A",
                                        outline=gold_fill if lit else "#000",
                                        width=2 if lit else 1)
                self._keys.insert(0, (x, 10, x + self.BLACK_WIDTH,
                                      10 + self.BLACK_HEIGHT, base + semitone))

    def _on_click(self, event) -> None:
        for x1, y1, x2, y2, midi in self._keys:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.on_pick(midi)
                return


# ---------------------------------------------------------------------------
# Sistema de dos pentagramas
# ---------------------------------------------------------------------------

#: Lo que se considera el mismo instante. Una división de compás importada
#: no siempre cae redonda.
EPSILON = 1e-6

#: Cuánto mide una negra, en píxeles. Es lo que separa dos notas seguidas de
#: la misma voz, y de acá sale que las voces se vean alineadas: dos negras
#: del bajo ocupan exactamente lo que cuatro corcheas del soprano.
#: Medido contra el caso apretado: cuatro compases de semicorcheas. A esta
#: escala una semicorchea se lleva quince píxeles, que es apenas más que una
#: cabeza de nota --- por debajo, las cabezas se tocan y una corrida de
#: semicorcheas deja de poder leerse. El piso es el punto donde el sistema
#: deja de apretarse y se corre de costado, por el mismo motivo.
PIXELS_PER_QUARTER = 62.0
MIN_PIXELS_PER_QUARTER = 40.0
#: Lo que se deja entre dos cabezas de la figura más corta escrita, medido
#: en anchos de cabeza. Con las cabezas de la fuente ---que miden lo que
#: mide una cabeza de verdad, más que los óvalos de antes--- el piso de
#: arriba dejaba las semicorcheas del preludio de Bach pisándose. El piso
#: sube **sólo** cuando hay figuras cortas: una pieza en negras sigue
#: entrando como entraba.
SHORTEST_ROOM = 1.15

#: El sistema se dibuja más apretado que el pentagrama de una línea, y no
#: por gusto: acá hay **dos** pentagramas, el hueco que los separa, el
#: cifrado americano arriba y el del bajo abajo, y todo eso comparte la
#: ventana con los tres paneles del análisis. Con la separación del
#: pentagrama suelto el sistema se llevaba media pantalla y los paneles
#: quedaban en una franja donde no entraba ni el primer acorde.
#:
#: Ocho píxeles por grado siguen siendo suficientes para distinguir una
#: nota de su vecina, que es el único límite que importa.
GRAND_LINE_GAP = 16
GRAND_STEP = GRAND_LINE_GAP // 2

#: Las cuatro voces del sistema, de aguda a grave tal como se las elige, con
#: el color con el que se dibuja cada una. El orden interno ---el que ve el
#: análisis--- es el contrario, de grave a aguda, como en todo el motor.
GRAND_VOICES = ("Soprano", "Alto", "Tenor", "Bajo")
VOICE_COLOURS = ("#C2554B", "#C08A2E", "#3F7D6E", "#4A6FA5")

#: Cuántas voces lleva el sistema. Fijo, y no una preferencia: dos claves
#: reparten cuatro voces ---bajo y tenor abajo, alto y soprano arriba--- y
#: ése es el reparto del coral. Cuántas están escritas se cuenta mirando el
#: pentagrama, que es donde está la respuesta; preguntárselo al usuario era
#: pedirle un dato que él ya escribió.
GRAND_VOICE_COUNT = 4

#: Índices de las cinco líneas de cada pentagrama, en la escalera diatónica.
TREBLE_LINES = (30, 32, 34, 36, 38)         # mi4 sol4 si4 re5 fa5
BASS_LINES = (18, 20, 22, 24, 26)           # sol2 si2 re3 fa3 la3
MIDDLE_C = 28

#: Hasta dónde puede llegar un click. Más allá el sistema se llena de líneas
#: adicionales y deja de leerse.
HIGHEST_INDEX = 44                          # do6
LOWEST_INDEX = 12                           # do2

#: Cuánto aire hay entre los dos pentagramas.
#:
#: Se probó sin aire, con la escalera diatónica corrida entera: es lo
#: exacto ---el do central queda justo en el medio--- y es ilegible. Los dos
#: pentagramas se leen como una sola grilla de diez líneas y no hay forma de
#: saber cuál es cuál. El hueco es lo que los separa en dos claves, que es
#: como se lee un sistema de verdad, y el precio es que la escalera se
#: **corta**: la altura de una nota se mide contra su propio pentagrama y no
#: contra el sistema entero.
STAFF_GAP = 4 * GRAND_LINE_GAP

#: De arriba hacia abajo: los números de compás, los cifrados americanos, el
#: sistema, y debajo el cifrado del bajo.
#:
#: El margen de arriba es el doble del que había. Con el anterior, una nota
#: por encima de la quinta línea se dibujaba **encima del cifrado**, y una
#: nota lo bastante aguda se dibujaba fuera del lienzo: existía en la voz y
#: no en la pantalla.
BAR_NUMBER_Y = 10
SYMBOL_Y = 26
#: Cuánto más abajo va el segundo renglón de cifrados, para el que no entra
#: al lado del anterior. Queda entre el primero y el pentagrama.
SYMBOL_STEP = 17
GRAND_TOP_MARGIN = 84
#: Dónde empiezan las notas como mínimo; como en el pentagrama de una línea,
#: lo que ocupen la clave, la armadura y el compás se mide en cada dibujo.
GRAND_LEFT_MARGIN = 150
BASS_TOP_MARGIN = GRAND_TOP_MARGIN + 4 * GRAND_LINE_GAP + STAFF_GAP

#: Cuánto baja cada renglón del cifrado del bajo. El cifrado se escribe en
#: columna ---el 6 sobre el 5, no "6/5"---, que es como se escribe de
#: verdad y además es lo que deja el ancho para las notas y no para los
#: rótulos.
FIGURE_LINE = 13

#: Lo mínimo que se despega el cifrado del pentagrama de fa. Si hay notas
#: más abajo, el cifrado baja con ellas: el alto del lienzo se calcula en
#: cada dibujo y no es una constante.
FIGURE_CLEARANCE = 36

#: Cuántos renglones de cifra caben. Tres: el cifrado del bajo continuo más
#: alto que se escribe es de tres números, y dejando que crezca solo el
#: cuarto se dibujaba fuera del lienzo.
FIGURE_ROWS = 3
GRAND_HEIGHT = int(BASS_TOP_MARGIN + 4 * GRAND_LINE_GAP + FIGURE_CLEARANCE
                   + FIGURE_ROWS * FIGURE_LINE)

#: Los accidentes que se pueden pedir a mano, además de lo que diga la
#: armadura. `None` es "lo que diga la armadura".
ACCIDENTALS = {1: "♯", -1: "♭", 0: "♮"}

#: Las figuras que se pueden escribir, de mayor a menor. Sirven para
#: repartir un hueco en silencios escribibles: un silencio de 1,37 negras no
#: existe, y un hueco de 2,5 negras son una blanca y una corchea.
WRITABLE = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25)

#: Cuántos pasos atrás guarda el pentagrama. Cien alcanza para toda una
#: sesión de escritura y no cuesta nada: cada paso es la lista de notas, que
#: en una partitura de cuatro voces son unos pocos cientos de tuplas.
UNDO_DEPTH = 100

#: El largo de las plicas del sistema, en espacios: medio espacio menos que
#: en el pentagrama suelto, porque acá hay dos voces por pentagrama y las
#: plicas de una apuntan hacia el cifrado de arriba.
GRAND_STEM_LENGTH = 3.0
#: Hasta dónde sube una plica del sistema: el pie del cifrado americano.
#: Con las plicas de tres espacios, un soprano por encima del pentagrama
#: atravesaba el nombre del acorde que justamente se estaba leyendo.
GRAND_STEM_CEILING = SYMBOL_Y + 14

#: La marca de lo que se dibuja **encima** de la partitura: el tramo
#: resaltado, los rótulos del análisis, los movimientos y la barra de la voz
#: activa. Cambian mucho más seguido que las notas ---cada vez que se elige
#: un acorde de la lista--- y se redibujan solos, sin volver a armar cada
#: cabeza, plica y barra de la pieza.
OVERLAY_TAG = "overlay"


def rest_glyph(duration: float) -> str:
    """El silencio más parecido a esta duración, como duración."""
    return min((4.0, 2.0, 1.0, 0.5, 0.25), key=lambda value: abs(value - duration))


def pitch_at(index: int, fifths: int, accidental=None) -> int:
    """
    La altura de una posición del pentagrama, con su accidente si lo lleva.

    Sin accidente manda la armadura, que es lo que hace que escribir en Sol
    mayor dé fa sostenidos sin tener que ponerlos. Con accidente manda el
    accidente, incluido el becuadro, que es justamente el que sirve para
    contradecir a la armadura.
    """
    if accidental is None:
        return index_to_pitch(index, fifths)
    octave, position = divmod(index, 7)
    letter = LETTERS[position]
    return (octave + 1) * 12 + LETTER_SEMITONE[letter] + accidental


def index_for_pitch(midi: int, fifths: int) -> int:
    """
    La posición del pentagrama que mejor escribe una altura.

    Se prefiere la letra que la armadura ya altera --- en Sol mayor un fa
    sostenido se escribe en la línea del fa y no en la del sol con un
    bemol --- y si ninguna sirve, la más cercana.

    Junto con :func:`pitch_at` forma un ida y vuelta exacto: cualquier
    altura escrita y vuelta a leer da la misma altura, en cualquier
    armadura. Eso es lo que permite importar una partitura, escribirla en el
    pentagrama y analizarla sin que cambie una nota.
    """
    octave, _semitone = divmod(midi, 12)
    best, best_cost = None, 99
    for step, _letter in enumerate(LETTERS):
        for shift in (0, -1, 1):
            index = (octave + shift) * 7 + step
            if not LOWEST_INDEX - 6 <= index <= HIGHEST_INDEX + 6:
                continue
            distance = midi - pitch_at(index, fifths, 0)
            if abs(distance) > 2:
                continue
            # Cuesta menos lo que la armadura ya escribe.
            cost = 0 if index_to_pitch(index, fifths) == midi else abs(distance) * 2
            if cost < best_cost:
                best, best_cost = index, cost
    return best if best is not None else (midi // 12) * 7


def accidental_for(midi: int, index: int, fifths: int) -> Optional[int]:
    """Qué accidente hay que escribirle a una altura en esa posición."""
    if index_to_pitch(index, fifths) == midi:
        return None
    return max(-2, min(2, midi - pitch_at(index, fifths, 0)))


def split_duration(total: float) -> List[float]:
    """
    Repartir un hueco en figuras que se puedan escribir.

    De mayor a menor, que es como se escribe un silencio largo: dos negras y
    media son una blanca y una corchea. Lo que no cierre exacto queda como
    un resto suelto ---puede pasar con una partitura importada con
    tresillos--- y se escribe igual: mentir sobre la duración correría todo
    lo que viene después.
    """
    if total <= EPSILON:
        # Un hueco de cero no se rellena con nada. Devolviendo una figura de
        # duracion cero, el pentagrama se llenaba de silencios invisibles
        # que despues aparecian en la lista de la voz.
        return []
    pieces: List[float] = []
    left = total
    for figure in WRITABLE:
        while left >= figure - EPSILON:
            pieces.append(figure)
            left -= figure
    if left > EPSILON:
        pieces.append(round(left, 6))
    return pieces or [total]


class GrandStaff(ctk.CTkFrame):
    """
    Un sistema de dos pentagramas para escribir a varias voces.

    Es el pariente ancho de :class:`StaffEditor`. Aquél lleva una línea sola
    y ordena las notas por columnas; acá hay cuatro voces con ritmos
    distintos, así que cada nota se ubica por **el tiempo en el que suena** y
    no por el lugar que ocupa en su lista. Es lo único que permite ver que
    una redonda del bajo dura lo que cuatro negras del soprano, que es la
    mitad de lo que se mira en un análisis.

    Se escribe **donde se hace click**: la altura sale de la posición
    vertical y el momento de la horizontal. Un click sobre una nota ya
    escrita la parte ---la nota vieja se queda con lo que sobra a cada
    lado--- en vez de reemplazarla entera, que es lo que permite meter una
    corchea de paso en el medio de una redonda sin que la redonda
    desaparezca y sin que se corra ni una voz.

    El widget no analiza nada. Devuelve las voces con sus alturas y
    duraciones y dibuja los rótulos que le pasen; quién los calcula es
    asunto de otro.
    """

    def __init__(self, master, colours: Dict[str, str],
                 on_change: Optional[Callable[[], None]] = None,
                 on_pick: Optional[Callable[[int, int, int], None]] = None,
                 on_hover: Optional[Callable[[Optional[Tuple[int, int]]], None]] = None,
                 editable: bool = True,
                 figures: bool = True,
                 **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.colours = colours
        #: Con False no se guarda lugar para el cifrado debajo del sistema.
        #: La escuelita no cifra nada, y ese renglón vacío era justo lo que
        #: le faltaba abajo a la corrección.
        self.figures = figures
        #: Con False el sistema sólo muestra: el click no escribe, el botón
        #: derecho no borra y no se marca la voz activa. Es como se ven los
        #: resultados de los modos que generan.
        self.editable = editable
        self.on_change = on_change
        #: Se llama al tocar una nota escrita, con (voz, posición, altura).
        #: Es lo que contesta "¿qué nota es ésta?", que es la pregunta con la
        #: que se lee una partitura ajena.
        self.on_pick = on_pick
        #: Se llama al pasar el mouse por encima de una nota escrita, con
        #: (voz, posición), o con None al salir de ella. Es la lectura que
        #: no cambia nada: para saber qué nota es no hace falta tocarla, y
        #: tocarla ahora la escribe.
        self.on_hover = on_hover
        #: Se llama cuando el click escribe un **silencio**. `on_pick`
        #: contesta qué nota se escribió y un silencio no es ninguna, así
        #: que quien quiera enterarse de que se puso uno --- el catálogo de
        #: logros --- necesita su propio aviso.
        self.on_rest: Optional[Callable[[], None]] = None
        self._hovering: Optional[Tuple[int, int]] = None
        self.voice_count = GRAND_VOICE_COUNT
        self.fifths = 0
        self.beats = 4
        self.beat_type = 4
        #: Los cambios de compás: (compás, tiempos, figura), ordenados y
        #: contando desde 1. El primero es el compás de arranque.
        self.metres: List[Tuple[int, int, int]] = [(1, 4, 4)]
        #: Lo que dura la anacrusa, en negras; cero si la pieza empieza en
        #: el uno. Es el compás 0, igual que en `analysis.Score.bar_grid`:
        #: sin ella las barras de un coral que arranca en anacrusa quedaban
        #: corridas respecto de lo que el análisis decía de cada compás.
        self.pickup = 0.0
        self.duration = 1.0
        self.active = 0                     # índice interno: 0 es el bajo
        #: El accidente que va a llevar la próxima nota, o None.
        self.pending: Optional[int] = None
        #: Por voz (de grave a aguda): (índice en el pentagrama, duración,
        #: accidente o None). Un índice ``None`` es un silencio: ocupa
        #: tiempo y no suena.
        self.voices: List[List[Tuple[Optional[int], float, Optional[int]]]] = [
            [] for _ in range(GRAND_VOICE_COUNT)]
        #: Mientras está en True, un click escribe un silencio en vez de una
        #: nota.
        self.writing_rests = False
        #: Rótulos del análisis: (comienzo en negras, cifrado americano,
        #: renglones del cifrado del bajo).
        self.annotations: List[Tuple[float, str, Sequence[str]]] = []
        #: El color de cada cifrado de arriba, por instante. Lo que no está
        #: va con la tinta de siempre. Es lo que deja ver en la partitura
        #: lo mismo que la tabla de resultados pinta de color: un préstamo,
        #: una modulación, una marca.
        self.symbol_colours: Dict[float, str] = {}
        #: Tramo resaltado, en negras, o None.
        self.highlight: Optional[Tuple[float, float]] = None
        #: Compases donde hay algo señalado, con su color.
        self.flags: List[Tuple[float, str]] = []
        #: Movimientos señalados: (instante, voz grave, voz aguda, hacia
        #: dónde va cada una ---1 sube, -1 baja, 0 se queda---, color). Un
        #: movimiento es entre **dos voces distintas**: se dibuja como una
        #: sola cosa que las une, y no como dos flechas sueltas que se leen
        #: como una voz moviéndose consigo misma.
        self.motions: List[Tuple[float, int, int, int, int, str]] = []
        #: Lo que se escribió antes, para poder deshacerlo.
        self._past: List[List[List[Tuple[Optional[int], float, Optional[int]]]]] = []
        self._engraver: Optional[Engraver] = None
        #: La geometría fija mientras dura un dibujo; ver `_layout`.
        self._fixed: Optional[Tuple[float, float]] = None
        #: Qué partitura hay dibujada en el lienzo: si no cambió, un dibujo
        #: rehace sólo lo de encima. Ver `OVERLAY_TAG`.
        self._drawn: Optional[tuple] = None
        #: Y qué hay dibujado encima, capa por capa, por lo mismo.
        self._layers: Dict[str, tuple] = {}
        self._region: Optional[tuple] = None

        self.canvas = tk.Canvas(self, height=GRAND_HEIGHT, highlightthickness=0,
                                bg=colours["surface"])
        self.scrollbar = ctk.CTkScrollbar(
            self, orientation="horizontal", command=self.canvas.xview,
            height=12, button_color=colours["muted"],
            button_hover_color=colours["accent"], fg_color="transparent")
        self.canvas.configure(xscrollcommand=self._on_scrolled)
        self.canvas.pack(fill="both", expand=True)
        if editable:
            self.canvas.bind("<Button-1>", self._on_click)
            self.canvas.bind("<Button-3>", self._on_erase)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._on_motion(None))
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel)

    @property
    def engraver(self) -> Engraver:
        """El grabador del lienzo, armado la primera vez que se dibuja."""
        if self._engraver is None:
            self._engraver = Engraver(self.canvas, GRAND_LINE_GAP)
        return self._engraver

    # -- la escalera, una por clave ----------------------------------------

    #: La voz que puede escribirse en cualquiera de los dos pentagramas.
    #: Es el tenor: en un coral va abajo, con el bajo, y en una partitura de
    #: piano la mano derecha necesita dos voces en la clave de sol. Dejarlo
    #: clavado en el fa obligaba a escribir la voz interna de arriba con
    #: seis líneas adicionales, que no es una partitura de piano sino un
    #: dibujo de una.
    SPLIT_VOICE = GRAND_VOICE_COUNT // 2 - 1

    def staff_of(self, voice: int, index: Optional[int] = None) -> bool:
        """¿Esta nota se escribe en clave de sol?

        La mitad grave va al pentagrama de fa y la mitad aguda al de sol, que
        es el reparto del coral a cuatro voces: bajo y tenor abajo, alto y
        soprano arriba.

        El tenor es la excepción y se reparte **nota por nota**: del do
        central para arriba se escribe en la clave de sol y para abajo en la
        de fa, que es como se reparte de verdad una voz que cruza el medio
        del teclado. Sin la altura ---cuando hay que contestar por la voz
        entera y no por una nota--- vale su pentagrama de siempre.
        """
        if index is not None and voice == self.SPLIT_VOICE:
            return index >= MIDDLE_C
        return voice >= GRAND_VOICE_COUNT // 2

    #: Cuántas líneas adicionales se dejan escribir por encima o por debajo
    #: del pentagrama de una voz. Seis: dos octavas de cabezas de nota,
    #: que es más de lo que ninguna voz de coral necesita y bastante menos
    #: que la distancia hasta el otro pentagrama.
    LEDGER_ROOM = 6

    def writable_range(self, voice: int) -> Tuple[int, int]:
        """Hasta dónde puede llegar una voz **en su propio pentagrama**.

        Cada voz se escribe en la clave que le toca, así que un click a la
        altura del otro pentagrama no es una nota de esta voz: es un click
        fuera de su alcance, y se lo lleva a la nota más alta (o más baja)
        que sí puede escribir. Sin este tope, el tenor escrito a la altura
        del pentagrama de sol quedaba dibujado ahí ---con seis líneas
        adicionales--- y sonando una nota que no es la que la línea de ese
        pentagrama dice: dos partituras distintas en el mismo lugar.
        """
        if voice == self.SPLIT_VOICE:
            # El tenor llega a los dos pentagramas: es la voz que se escribe
            # a un lado o al otro del do central según dónde esté la nota.
            return (LOWEST_INDEX, HIGHEST_INDEX)
        if self.staff_of(voice):
            return (TREBLE_LINES[0] - self.LEDGER_ROOM, HIGHEST_INDEX)
        return (LOWEST_INDEX, BASS_LINES[-1] + self.LEDGER_ROOM)

    @staticmethod
    def _y_for(index: int, treble: bool = True) -> float:
        if treble:
            return GRAND_TOP_MARGIN + (TREBLE_LINES[-1] - index) * GRAND_STEP
        return BASS_TOP_MARGIN + (BASS_LINES[-1] - index) * GRAND_STEP

    def _clef_at(self, y: float) -> bool:
        """Qué clave rige a esa altura del lienzo, para la voz activa.

        Sólo el tenor pregunta: las otras tres tienen un pentagrama y nada
        más, y un click a la altura del otro no es una nota de esa voz sino
        un click fuera de su alcance.
        """
        if self.active != self.SPLIT_VOICE:
            return self.staff_of(self.active)
        border = (self._y_for(MIDDLE_C, True)
                  + self._y_for(MIDDLE_C - 1, False)) / 2.0
        return y <= border

    @staticmethod
    def _index_for(y: float, treble: bool = True) -> int:
        if treble:
            return int(round(TREBLE_LINES[-1]
                             - (y - GRAND_TOP_MARGIN) / GRAND_STEP))
        return int(round(BASS_LINES[-1] - (y - BASS_TOP_MARGIN) / GRAND_STEP))

    # -- el encabezado ------------------------------------------------------

    #: Dónde arrancan las claves: a la derecha de la llave y de la barra de
    #: la voz activa.
    CLEF_X = 30

    def _header(self) -> Tuple[float, float, float]:
        """Dónde van la armadura y el compás, y dónde empiezan las notas."""
        space = float(GRAND_LINE_GAP)
        clef = max(WIDTHS["gClef"], WIDTHS["fClef"]) * space
        key_x = self.CLEF_X + clef + 0.7 * space
        count = min(7, abs(self.fifths))
        sign = "accidentalSharp" if self.fifths > 0 else "accidentalFlat"
        advance = (WIDTHS[sign] + 0.12) * space
        metre_x = key_x + count * advance + (0.6 * space if count else 0.0)
        beats, beat_type = self.metre_at(1)
        metre_width = max(sum(WIDTHS[f"timeSig{d}"] for d in str(beats)),
                          sum(WIDTHS[f"timeSig{d}"] for d in str(beat_type))
                          ) * space
        left = max(float(GRAND_LEFT_MARGIN),
                   metre_x + metre_width + 1.4 * space)
        return key_x, metre_x, left

    def left_margin(self) -> float:
        """Dónde empieza el tiempo cero."""
        return self._header()[2]

    def _shortest(self) -> float:
        """La figura más corta escrita, en negras."""
        shortest = 4.0
        for voice in self.voices:
            for _index, duration, _accidental in voice:
                if duration > EPSILON:
                    shortest = min(shortest, figure_of(duration)[0])
        return shortest

    def spacing(self) -> float:
        """Cuánto mide una negra, apretándose cuando la pieza es larga.

        El piso sube con la figura más corta que haya escrita: una
        semicorchea tiene que poder dibujarse al lado de otra sin pisarla.
        """
        total = self.total_quarters()
        if total <= 0:
            return PIXELS_PER_QUARTER
        usable = max(240, self.canvas.winfo_width() - self.left_margin() - 40)
        head = WIDTHS["noteheadBlack"] * GRAND_LINE_GAP
        floor = max(MIN_PIXELS_PER_QUARTER,
                    SHORTEST_ROOM * head / max(0.125, self._shortest()))
        return max(floor, min(PIXELS_PER_QUARTER, usable / total))

    def _layout(self) -> Tuple[float, float]:
        """Dónde empieza el tiempo cero y cuánto mide una negra.

        Mientras se dibuja (o se busca qué nota hay bajo el mouse) se
        calcula una sola vez: cada nota preguntaba las dos cosas, y las dos
        recorren la pieza entera --- una cuenta cuadrática por cada dibujo y
        por cada movimiento del mouse.
        """
        if self._fixed is not None:
            return self._fixed
        return self.left_margin(), self.spacing()

    def _x_for(self, quarters: float) -> float:
        left, spacing = self._layout()
        return left + quarters * spacing

    def _time_at(self, x: float) -> float:
        """En qué momento de la pieza, en negras, cae una posición del lienzo."""
        left, spacing = self._layout()
        return max(0.0, (x - left) / spacing)

    # -- los compases -------------------------------------------------------

    def metre_at(self, bar: int) -> Tuple[int, int]:
        """Qué compás rige en ese compás de la pieza."""
        beats, beat_type = self.beats, self.beat_type
        for at, count, figure in self.metres:
            if at <= max(1, bar):
                beats, beat_type = count, figure
            else:
                break
        return beats, beat_type

    def bar_grid(self, upto: Optional[float] = None) -> List[Tuple[int, float,
                                                                  float]]:
        """Los compases hasta ese momento: número, comienzo y duración."""
        finish = self.total_quarters() if upto is None else upto
        grid: List[Tuple[int, float, float]] = []
        moment, bar = 0.0, 1
        if self.pickup > EPSILON:
            grid.append((0, 0.0, self.pickup))
            moment = self.pickup
        while True:
            beats, beat_type = self.metre_at(bar)
            per_bar = beats * 4.0 / beat_type or 4.0
            grid.append((bar, moment, per_bar))
            moment += per_bar
            bar += 1
            if moment > finish + EPSILON or bar > 9999:
                break
        return grid

    def bar_of(self, moment: float) -> Tuple[int, float, float]:
        """El compás que contiene un instante: número, comienzo y duración."""
        bar, start, per_bar = 1, 0.0, 4.0
        for number, begin, length in self.bar_grid(moment + 1.0):
            if begin <= moment + EPSILON:
                bar, start, per_bar = number, begin, length
            else:
                break
        return bar, start, per_bar

    def set_metres(self, metres: Sequence[Tuple[int, int, int]]) -> None:
        """Fijar los cambios de compás de la pieza."""
        ordered = sorted({int(bar): (int(bar), int(count), int(figure))
                          for bar, count, figure in metres}.values())
        self.metres = ordered or [(1, self.beats, self.beat_type)]
        self.beats, self.beat_type = self.metres[0][1], self.metres[0][2]
        self.redraw()

    # -- lo que hay escrito -------------------------------------------------

    def total_quarters(self) -> float:
        return max((sum(d for _i, d, _a in voice) for voice in self.voices),
                   default=0.0)

    def is_empty(self) -> bool:
        return not any(self.voices)

    def written_voices(self) -> List[int]:
        """Qué voces tienen al menos una nota escrita, de grave a aguda."""
        return [voice for voice, line in enumerate(self.voices)
                if any(index is not None for index, _d, _a in line)]

    def lines(self) -> List[List[Tuple[Optional[int], float]]]:
        """Por voz, de grave a aguda: (altura MIDI o None, duración)."""
        return [[(None if index is None
                  else pitch_at(index, self.fifths, accidental), duration)
                 for index, duration, accidental in voice]
                for voice in self.voices]

    def onsets(self, voice: int) -> List[float]:
        position, out = 0.0, []
        for _index, duration, _accidental in self.voices[voice]:
            out.append(position)
            position += duration
        return out

    def onset_of(self, voice: int, position: int) -> float:
        return sum(d for _i, d, _a in self.voices[voice][:position])

    # -- edición ------------------------------------------------------------

    def set_key(self, fifths: int, beats: int, beat_type: int) -> None:
        self.fifths = fifths
        self.beats = beats
        self.beat_type = beat_type
        if self.metres and self.metres[0][0] == 1:
            self.metres[0] = (1, beats, beat_type)
        else:
            self.metres.insert(0, (1, beats, beat_type))
        self.redraw()

    def _remember(self) -> None:
        """Guardar el estado de antes de tocar nada."""
        self._past.append([list(voice) for voice in self.voices])
        del self._past[:-UNDO_DEPTH]

    def add(self, index: int, duration: Optional[float] = None,
            accidental=None, voice: Optional[int] = None) -> None:
        target = self.active if voice is None else voice
        self._remember()
        self.voices[target].append(
            (index, self.duration if duration is None else duration, accidental))
        self._changed()

    def undo(self) -> None:
        """Volver al estado anterior, sea cual sea el cambio que se hizo.

        Antes era "sacar la última nota de la voz activa", que no es lo
        mismo: escribir en el medio, borrar, importar o limpiar no se podían
        deshacer, y deshacer después de cambiar de voz sacaba una nota de
        otro lado.
        """
        if not self._past:
            return
        self.voices = self._past.pop()
        self._changed()

    def clear(self) -> None:
        self._remember()
        self.voices = [[] for _ in range(GRAND_VOICE_COUNT)]
        self.pickup = 0.0
        self.annotations = []
        self.symbol_colours = {}
        self.highlight = None
        self.flags = []
        self.motions = []
        self._changed()

    def load(self, lines: Sequence[Sequence[Tuple[int, float]]]) -> None:
        """Escribir en el pentagrama unas voces que vienen de otro lado.

        Cada altura se escribe con el accidente que necesite para sonar como
        suena: la armadura resuelve lo que puede y lo que le sobra se marca.
        Sin esto, importar una partitura en Fa mayor y volver a leerla del
        pentagrama devolvía si naturales.
        """
        self._remember()
        self.voices = [[] for _ in range(GRAND_VOICE_COUNT)]
        for voice, line in enumerate(lines[:GRAND_VOICE_COUNT]):
            for pitch, duration in line:
                if pitch is None:
                    self.voices[voice].append((None, duration, None))
                    continue
                index = index_for_pitch(pitch, self.fifths)
                self.voices[voice].append(
                    (index, duration,
                     accidental_for(pitch, index, self.fifths)))
        self._changed()

    def _changed(self) -> None:
        self.redraw()
        if self.on_change:
            self.on_change()

    # -- escribir donde se tocó ---------------------------------------------

    def _snap(self, moment: float) -> float:
        """
        Llevar un instante a la cuadrícula de la figura elegida.

        La cuadrícula se mide **desde el comienzo del compás** y no desde el
        principio de la pieza. Con un cambio de compás en el medio, medir
        desde el cero deja las corcheas de la segunda mitad a contratiempo
        de sus propias barras; y una nota que arranca antes de la barra y
        termina después se dibuja partida por la barra, que es justamente lo
        que no puede pasar.
        """
        duration = self.duration or 1.0
        _bar, start, per_bar = self.bar_of(moment)
        inside = moment - start
        # Contra el **centro** de cada lugar y no contra su comienzo: la
        # nota se dibuja en el medio del tramo que ocupa, así que apuntando
        # a la cabeza de una nota se estaba apuntando media figura más allá
        # de donde empieza --- y la nota nueva caía en el lugar siguiente.
        slot = int(math.floor((inside - duration / 2.0) / duration + 0.5))
        slot = max(0.0, min(slot * duration, max(0.0, per_bar - duration)))
        return start + slot

    def _write(self, moment: float, index: Optional[int],
               accidental: Optional[int]) -> Optional[int]:
        """
        Poner una nota (o un silencio) en ese momento de la voz activa.

        Devuelve en qué lugar de la lista quedó.

        Lo que cae **dentro** de una nota escrita la parte en tres: lo que
        sobra antes, la nota nueva y lo que sobra después, las dos puntas
        con la altura que tenía. Es lo que permite escribir una corchea de
        paso encima de una redonda tenida --- que era el caso que rompía el
        análisis: reemplazando la redonda entera, esa voz se quedaba muda el
        resto del compás y la corchea pasaba a ser un acorde entero ella
        sola.

        Y lo que cae más allá del final se rellena con silencios repartidos
        en figuras escribibles, así la nota queda donde se la puso y las
        voces no se corren entre sí.
        """
        voice = self.voices[self.active]
        duration = self.duration or 1.0
        target = self._snap(moment)
        self._remember()
        cursor = 0.0
        for order, (written, length, mark) in enumerate(voice):
            if not cursor - EPSILON <= target < cursor + length - EPSILON:
                cursor += length
                continue
            head = target - cursor
            tail = length - head - duration
            if tail < -EPSILON:
                # No entra: la nota nueva se come lo que quedaba y nada más.
                duration = length - head
                tail = 0.0
            pieces: List[Tuple[Optional[int], float, Optional[int]]] = []
            if head > EPSILON:
                pieces += [(written, piece, mark if position == 0 else None)
                           for position, piece in enumerate(split_duration(head))]
            pieces.append((index, duration, accidental))
            place = len(pieces) - 1
            if tail > EPSILON:
                pieces += [(written, piece, None)
                           for piece in split_duration(tail)]
            voice[order:order + 1] = pieces
            self._changed()
            return order + place

        for piece in split_duration(max(0.0, target - cursor)):
            voice.append((None, piece, None))
        voice.append((index, duration, accidental))
        self._changed()
        return len(voice) - 1

    def erase(self, voice: int, position: int) -> None:
        """
        Sacar una nota sin correr las demás.

        Se convierte en un silencio de la misma duración en vez de
        desaparecer: si desapareciera, todo lo que esa voz tiene escrito
        después se adelantaría, y una voz corrida contra las otras cambia la
        armonía de cada tiempo. Sólo cuando la nota está al final se la saca
        de verdad, con los silencios que hayan quedado colgando detrás.
        """
        if not 0 <= voice < len(self.voices):
            return
        line = self.voices[voice]
        if not 0 <= position < len(line):
            return
        self._remember()
        if position == len(line) - 1:
            del line[position:]
            while line and line[-1][0] is None:
                line.pop()
        else:
            index, duration, _accidental = line[position]
            line[position] = (None, duration, None)
        self._changed()

    def note_at(self, x: float, y: float):
        """Qué nota escrita cae bajo el mouse, o None.

        El blanco es la cabeza de la nota y nada más. Con un blanco
        proporcional a la duración, una redonda se llevaba cien píxeles a
        cada lado y no se podía escribir cerca de ella.
        """
        left, spacing = self._layout()
        for voice in range(GRAND_VOICE_COUNT):
            position = 0.0
            for order, (index, duration, _accidental) in enumerate(self.voices[voice]):
                if index is None:
                    position += duration
                    continue
                note_x = left + (position + duration / 2.0) * spacing
                note_y = self._y_for(index, self.staff_of(voice, index))
                # Media cabeza de ancho, y nunca menos de diez píxeles. Con
                # Bravura una redonda mide 1,7 espacios ---unos 27 px--- y con
                # el blanco fijo de diez su borde no se podía tocar.
                reach = max(10.0, GRAND_LINE_GAP * (0.85 if duration >= 4 else 0.6))
                if abs(x - note_x) <= reach and abs(y - note_y) <= 7:
                    return voice, order
                position += duration
        return None

    # -- clicks -------------------------------------------------------------

    def _on_click(self, event) -> None:
        """Escribir donde se tocó, y contestar qué se escribió."""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if x < self.left_margin():
            return
        moment = self._time_at(x)
        if self.writing_rests:
            self._write(moment, None, None)
            if self.on_rest is not None:
                self.on_rest()
            return
        # Contra la clave **de la voz que se escribe**, y no contra el
        # pentagrama más cercano al mouse. Los dos pentagramas no son una
        # escalera continua: cada clave tiene su propia geometría, así que
        # una altura leída con la del sol y dibujada con la del fa cae a
        # cinco líneas de donde se hizo el click. Leyéndola con la misma
        # clave con la que se la va a dibujar, la nota aparece exactamente
        # bajo el cursor --- y el tenor escrito por encima del pentagrama de
        # fa queda donde uno lo puso, con sus líneas adicionales.
        index = self._index_for(y, self._clef_at(y))
        low, high = self.writable_range(self.active)
        index = max(low, min(high, index))
        if self.active == self.SPLIT_VOICE:
            # El tenor se escribe en los dos pentagramas, así que la altura
            # se lee con la clave del pentagrama donde se hizo el click y
            # después se la obliga a quedar de ese lado del do central: si
            # no, un click en la parte de arriba del pentagrama de fa daba
            # una nota que se dibuja en el de sol, cinco líneas más allá de
            # donde se la puso.
            if self._clef_at(y):
                index = max(MIDDLE_C, index)
            else:
                index = min(MIDDLE_C - 1, index)
        position = self._write(moment, index, self.pending)
        self.pending = None
        if position is not None and self.on_pick is not None:
            written, _duration, accidental = self.voices[self.active][position]
            self.on_pick(self.active, position,
                         pitch_at(written, self.fifths, accidental))

    def _on_motion(self, event) -> None:
        """Avisar qué nota está debajo del mouse, sin tocar nada."""
        if self.on_hover is None:
            return
        hit = None
        if event is not None:
            hit = self.note_at(self.canvas.canvasx(event.x),
                               self.canvas.canvasy(event.y))
        if hit == self._hovering:
            return
        self._hovering = hit
        self.on_hover(hit)

    def _on_erase(self, event) -> None:
        """El botón derecho borra la nota que está debajo."""
        hit = self.note_at(self.canvas.canvasx(event.x),
                           self.canvas.canvasy(event.y))
        if hit is None:
            return
        self.erase(*hit)

    def _on_scrolled(self, first: str, last: str) -> None:
        self.scrollbar.set(first, last)
        needed = float(first) > 0.0 or float(last) < 1.0
        # Por quién la administra y no por si se ve: antes de que la ventana
        # se muestre no se ve nada, y preguntando eso la barra puesta con el
        # primer dibujo ---más angosto--- no se sacaba nunca.
        try:
            if needed and not self.scrollbar.winfo_manager():
                self.scrollbar.pack(fill="x", side="bottom", pady=(2, 0))
            elif not needed and self.scrollbar.winfo_manager():
                self.scrollbar.pack_forget()
        except tk.TclError:
            pass

    def _on_wheel(self, event) -> None:
        try:
            if self.canvas.bbox("all") is None:
                return
            self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        except tk.TclError:
            pass

    # -- dibujo -------------------------------------------------------------

    def _figure_top(self) -> float:
        """Dónde arranca el cifrado del bajo, sin pisar ninguna nota.

        Ni ninguna plica: las de las voces graves de cada pentagrama bajan
        tres espacios, y contando sólo la cabeza el cifrado quedaba
        atravesado por la plica de su propia nota del bajo.
        """
        floor = BASS_TOP_MARGIN + 4 * GRAND_LINE_GAP + FIGURE_CLEARANCE
        deepest = self._deepest()
        if deepest is None:
            return floor
        return max(floor, deepest + 14)

    def _deepest(self) -> Optional[float]:
        """Lo más bajo que se dibuja en el pentagrama de fa, plicas incluidas."""
        deepest = None
        stem = GRAND_STEM_LENGTH * GRAND_LINE_GAP
        for voice in range(GRAND_VOICE_COUNT):
            down = voice % 2 == 0
            for index, duration, _accidental in self.voices[voice]:
                if index is None or self.staff_of(voice, index):
                    continue
                y = self._y_for(index, False)
                if down and figure_of(duration)[0] < 4.0:
                    y += stem
                if deepest is None or y > deepest:
                    deepest = y
        return deepest

    def _score_signature(self) -> tuple:
        """Todo lo que decide cómo se dibujan las notas, y nada más."""
        return (self.fifths, self.beats, self.beat_type, tuple(self.metres),
                self.pickup,
                tuple(tuple(line) for line in self.voices),
                self.canvas.winfo_width(), self._fixed,
                tuple(sorted(self.colours.items())))

    def redraw(self) -> None:
        """
        Dibujar el sistema.

        Si las notas, la armadura, los compases y el ancho son los mismos
        que la última vez, se rehace sólo lo de encima (`OVERLAY_TAG`). El
        analizador redibuja cada vez que se elige un acorde o un hallazgo de
        la lista ---para correr el resaltado--- y rearmar cientos de signos
        para mover un rectángulo era la mitad de la espera.
        """
        self._fixed = None
        self._fixed = (self.left_margin(), self.spacing())
        try:
            signature = self._score_signature()
            if signature == self._drawn:
                self._draw_overlays()
            else:
                self._layers = {}
                self._redraw()
                self._drawn = signature
        finally:
            self._fixed = None

    def _width(self) -> int:
        left, spacing = self._layout()
        return max(self.canvas.winfo_width(), 420,
                   int(left + self.total_quarters() * spacing + 40))

    def _layer(self, name: str, signature: tuple) -> bool:
        """
        ¿Hay que rehacer esta capa de encima? Si sí, borra la que había.

        Sólo se rehace la capa que cambió. Tk repinta el rectángulo que
        envuelve todo lo que se tocó, así que borrar y volver a escribir los
        rótulos de punta a punta para mover el resaltado repintaba la
        partitura entera --- que es lo que cuesta, mucho más que armarla.
        """
        if self._layers.get(name) == signature:
            return False
        self.canvas.delete(OVERLAY_TAG + "-" + name)
        self._layers[name] = signature
        return True

    def _draw_overlays(self) -> None:
        """Lo de encima de la partitura; ver `OVERLAY_TAG`."""
        canvas = self.canvas
        ink = self.colours["text"]
        faint = self.colours["muted"]
        width = self._width()
        top = self._y_for(TREBLE_LINES[-1], True)
        bottom = self._y_for(BASS_LINES[0], False)
        figure_top = self._figure_top()
        rows = max((len(figure) for _o, _s, figure in self.annotations),
                   default=0)
        if self.figures or rows:
            height = int(figure_top + max(1, min(FIGURE_ROWS, rows))
                         * FIGURE_LINE + 6)
        else:
            deepest = self._deepest()
            height = int(max(bottom + 22,
                             deepest + 14 if deepest is not None else 0))
        try:
            if int(canvas.cget("height")) != height:
                canvas.configure(height=height)
        except (tk.TclError, ValueError):
            pass

        if self._layer("band", (self.highlight,)):
            if self.highlight is not None:
                start, end = self.highlight
                band = canvas.create_rectangle(
                    self._x_for(start), top - 10, self._x_for(end),
                    bottom + 10,
                    fill=self.colours.get("glow", self.colours["surface"]),
                    outline="", tags=(OVERLAY_TAG, OVERLAY_TAG + "-band"))
                # Debajo de todo: el resaltado es el fondo del tramo, no una
                # tapa encima de sus notas.
                canvas.tag_lower(band)
        if self._layer("active", (self.active, self.editable)):
            if self.editable:
                self._mark_active(width)
        if self._layer("motions", (tuple(self.motions),)):
            self._draw_motions()
        if self._layer("labels", (tuple((onset, symbol, tuple(figure))
                                        for onset, symbol, figure
                                        in self.annotations),
                                  tuple(sorted(self.symbol_colours.items())),
                                  tuple(self.flags), figure_top)):
            self._draw_annotations(faint, ink, bottom, figure_top)
        # Y la región de desplazamiento sólo si cambió: volver a ponerla,
        # aunque sea igual, le pide a Tk que repinte el lienzo entero.
        region = (0, 0, width, height)
        if region != self._region:
            canvas.configure(scrollregion=region)
            self._region = region
            # Tk avisa el desplazamiento cuando cambia la vista, no cuando la
            # región pasa a entrar entera: con la ventana agrandada después
            # del primer dibujo, la barra quedaba puesta sin nada que mover.
            try:
                self._on_scrolled(*canvas.xview())
            except tk.TclError:
                pass

    def _redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._region = None
        ink = self.colours["text"]
        faint = self.colours["muted"]
        total = self.total_quarters()
        width = self._width()
        top = self._y_for(TREBLE_LINES[-1], True)
        bottom = self._y_for(BASS_LINES[0], False)

        for group, treble in ((TREBLE_LINES, True), (BASS_LINES, False)):
            for index in group:
                y = self._y_for(index, treble)
                canvas.create_line(24, y, width - 24, y, fill=faint)
        # La llave y la barra que unen los dos pentagramas: es lo que los
        # hace un sistema y no dos pentagramas puestos uno encima del otro.
        self.engraver.brace(2, top, bottom, ink)
        canvas.create_line(24, top, 24, bottom, fill=ink, width=2)

        self._draw_clefs(ink)
        key_x, metre_x, _left = self._header()
        self._draw_signature(key_x, ink)
        beats, beat_type = self.metre_at(1)
        self._draw_metre(metre_x + self.engraver.metre_width(beats, beat_type)
                         / 2.0, beats, beat_type, ink)

        self._draw_bar_lines(total, width, faint, ink, top, bottom)
        shown = self._shown_accidentals()
        for voice in range(GRAND_VOICE_COUNT):
            self._draw_voice(voice, shown)
        if self.is_empty():
            canvas.create_text(
                max(canvas.winfo_width(), 420) / 2, bottom + 40,
                text=tr("Elegí una voz y hacé click donde va cada nota, "
                        "o importá una partitura."),
                fill=faint, font=("Segoe UI", 12))
        self._draw_overlays()

    def _draw_clefs(self, ink: str) -> None:
        """Las dos claves: la de sol en la segunda línea, la de fa en la cuarta."""
        self.engraver.clef(self.CLEF_X, self._y_for(TREBLE_LINES[1], True),
                           True, ink)
        self.engraver.clef(self.CLEF_X, self._y_for(BASS_LINES[3], False),
                           False, ink)

    def _draw_metre(self, x: float, beats: int, beat_type: int,
                    colour: str) -> None:
        """El compás, en los dos pentagramas, centrado en x."""
        for treble, lines in ((True, TREBLE_LINES), (False, BASS_LINES)):
            self.engraver.number(x, self._y_for(lines[3], treble), beats,
                                 colour)
            self.engraver.number(x, self._y_for(lines[1], treble), beat_type,
                                 colour)

    def _draw_signature(self, x: float, ink: str) -> float:
        """La armadura, en los dos pentagramas y en el orden de siempre."""
        if not self.fifths:
            return x
        order = SHARP_ORDER if self.fifths > 0 else FLAT_ORDER
        value = 1 if self.fifths > 0 else -1
        sign = ACCIDENTAL_GLYPHS[value]
        sign_width = WIDTHS[sign] * GRAND_LINE_GAP
        advance = (WIDTHS[sign] + 0.12) * GRAND_LINE_GAP
        rows = ((self._sharp_row(5) if self.fifths > 0 else self._flat_row(5),
                 True),
                (self._sharp_row(3) if self.fifths > 0 else self._flat_row(3),
                 False))
        for step in range(min(7, abs(self.fifths))):
            letter = order[step]
            for row, treble in rows:
                self.engraver.accidental(x + sign_width,
                                         self._y_for(row[letter], treble),
                                         value, ink)
            x += advance
        return x

    @staticmethod
    def _sharp_row(octave: int) -> Dict[str, int]:
        return {"F": diatonic_index("F", octave), "C": diatonic_index("C", octave),
                "G": diatonic_index("G", octave), "D": diatonic_index("D", octave),
                "A": diatonic_index("A", octave - 1),
                "E": diatonic_index("E", octave),
                "B": diatonic_index("B", octave - 1)}

    @staticmethod
    def _flat_row(octave: int) -> Dict[str, int]:
        return {"B": diatonic_index("B", octave - 1),
                "E": diatonic_index("E", octave),
                "A": diatonic_index("A", octave - 1),
                "D": diatonic_index("D", octave),
                "G": diatonic_index("G", octave - 1),
                "C": diatonic_index("C", octave),
                "F": diatonic_index("F", octave - 1)}

    def _mark_active(self, width: float) -> None:
        """
        Una barra del color de la voz activa, al costado de su pentagrama.

        Un click lee la altura contra el pentagrama más cercano, así que
        tocar la clave de sol escribiendo el bajo da una nota de bajo muy
        aguda --- correcta y desconcertante. Esta barra dice de antemano en
        qué clave se está escribiendo, que es lo único que faltaba para que
        no sorprenda.
        """
        colour = VOICE_COLOURS[min(3, GRAND_VOICE_COUNT - 1 - self.active)]
        # El tenor se marca en los dos: es la única voz que se puede
        # escribir a los dos lados del do central, y marcarle uno solo
        # decía justo lo contrario de lo que hace.
        clefs = ((True, False) if self.active == self.SPLIT_VOICE
                 else (self.staff_of(self.active),))
        for treble in clefs:
            lines = TREBLE_LINES if treble else BASS_LINES
            self.canvas.create_rectangle(
                17, self._y_for(lines[-1], treble), 21,
                self._y_for(lines[0], treble), fill=colour, outline="",
                tags=(OVERLAY_TAG, OVERLAY_TAG + "-active"))

    def _draw_bar_lines(self, total: float, width: float, colour: str,
                        ink: str, top: float, bottom: float) -> None:
        """
        Las barras de compás, y el compás nuevo donde cambia.

        Se camina compás por compás en vez de sumar siempre lo mismo: un
        cambio de compás en el medio corre todas las barras que vienen
        después, y dibujarlas donde estaban dejaba la partitura diciendo una
        cosa y sonando otra.
        """
        previous = self.metre_at(1)
        for bar, start, per_bar in self.bar_grid(total):
            beats, beat_type = self.metre_at(bar)
            x = self._x_for(start)
            if x > width - 24:
                break
            if start > EPSILON:
                self.canvas.create_line(x, top, x, bottom, fill=colour, width=1)
            if bar >= 1 and (start < total - EPSILON or bar == 1):
                self.canvas.create_text(x + 5, BAR_NUMBER_Y, text=tr(str(bar)),
                                        fill=colour, anchor="w",
                                        font=("Segoe UI", 9))
            if bar > 1 and (beats, beat_type) != previous:
                self._draw_metre(x + 16, beats, beat_type, ink)
            previous = (beats, beat_type)

    def _shown_accidentals(self) -> Dict[Tuple[int, int], Optional[int]]:
        """
        Qué accidente se dibuja delante de cada nota, por (voz, posición).

        La regla del compás vale **por pentagrama**: un sol sostenido del
        soprano obliga al becuadro del sol natural que el alto canta después
        en el mismo compás, porque los dos se leen en la misma clave.
        """
        starts = [begin for _number, begin, _length in self.bar_grid()]
        by_staff: Dict[bool, List] = {True: [], False: []}
        for voice in range(GRAND_VOICE_COUNT):
            position, bar = 0.0, 0
            for order, (index, duration, accidental) in enumerate(
                    self.voices[voice]):
                while (bar + 1 < len(starts)
                       and starts[bar + 1] <= position + EPSILON):
                    bar += 1
                if index is not None:
                    by_staff[self.staff_of(voice, index)].append((
                        (position, voice), starts[bar], index,
                        pitch_at(index, self.fifths, accidental),
                        (voice, order)))
                position += duration
        shown: Dict[Tuple[int, int], Optional[int]] = {}
        for notes in by_staff.values():
            shown.update(displayed_accidentals(notes, self.fifths))
        return shown

    def _draw_voice(self, voice: int,
                    shown: Optional[Dict[Tuple[int, int], Optional[int]]] = None
                    ) -> None:
        """
        Una voz entera, con el color que le toca.

        Todas van con su color y no sólo la que se está escribiendo: el
        color es lo que dice cuál es cuál cuando cuatro voces comparten dos
        pentagramas, y apagando las otras tres esa información se perdía
        justo cuando más hace falta. La voz activa se distingue por otro
        lado --- se dibuja al final, así que queda arriba de las demás.
        """
        engraver = self.engraver
        space = float(GRAND_LINE_GAP)
        colour = VOICE_COLOURS[min(3, GRAND_VOICE_COUNT - 1 - voice)]
        faint = self.colours["muted"]
        # La voz aguda de cada pentagrama lleva la plica para arriba y la
        # grave para abajo: es como se escriben dos voces en una misma clave
        # sin que se confundan.
        up = voice % 2 == 1
        position = 0.0
        heads: List[EngravedNote] = []
        grid = self.bar_grid()
        for order, (index, duration, accidental) in enumerate(self.voices[voice]):
            # La clave se pregunta nota por nota: el tenor se escribe a un
            # lado o al otro del do central, así que la voz entera no tiene
            # un pentagrama sino cada una de sus notas.
            treble = self.staff_of(voice, index)
            lines = TREBLE_LINES if treble else BASS_LINES
            x = self._x_for(position + duration / 2.0)
            if index is None:
                # Cada voz descansa en su propio renglón y con su color. Con
                # todas en la misma línea, el silencio de una voz se dibujaba
                # encima de la nota de la otra: dos cosas distintas en el
                # mismo lugar, y ninguna de las dos legible.
                row = lines[3] if voice % 2 else lines[1]
                self._draw_rest(x, self._y_for(row, treble), duration, colour)
                position += duration
                # Un silencio corta la barra: lo que venga después es otro
                # grupo aunque caiga en el mismo tiempo.
                heads.append(None)
                continue
            y = self._y_for(index, treble)
            figure, dots = figure_of(duration)
            head_width = engraver.head_width(figure)
            self._draw_ledgers(x, index, faint, treble, head_width)
            sign = (shown.get((voice, order), accidental) if shown is not None
                    else accidental)
            if sign is not None:
                engraver.accidental(x - head_width / 2.0 - 0.18 * space, y,
                                    sign, colour)
            engraver.head(x, y, figure, colour)
            for dot in range(dots):
                engraver.dot(x + head_width / 2.0 + (0.3 + 0.6 * dot) * space,
                             y - (GRAND_STEP if index % 2 == 0 else 0), colour)
            bar_start, unit = 0.0, 1.0
            for number, begin, _length in grid:
                if begin <= position + EPSILON:
                    bar_start = begin
                    unit = beam_unit(*self.metre_at(number))
                else:
                    break
            group = (bar_start,
                     math.floor((position - bar_start) / unit + 1e-9))
            heads.append(EngravedNote(x=x, y=y, figure=figure, up=up,
                                      colour=colour, head_width=head_width,
                                      group=group, dotted=dots > 0))
            position += duration
        # Las plicas van por tramos entre silencios.
        run: List[EngravedNote] = []
        for note in heads + [None]:
            if note is None:
                if run:
                    engraver.stems(run, GRAND_STEM_LENGTH,
                                   ceiling=GRAND_STEM_CEILING)
                run = []
            else:
                run.append(note)

    def _draw_rest(self, x: float, y: float, duration: float,
                   colour: str) -> None:
        """
        Un silencio, con la fuente musical si está y con trazos si no.

        `y` es la línea que hace de centro del renglón de esa voz.
        """
        self.engraver.rest(x, y, duration, colour)

    def _draw_ledgers(self, x: float, index: int, colour: str,
                      treble: bool, head_width: Optional[float] = None) -> None:
        """Las líneas cortas de una nota que se salió de su pentagrama."""
        canvas = self.canvas
        if head_width is None:
            head_width = self.engraver.head_width(1.0)
        reach = head_width / 2.0 + LEDGER_EXTENSION * GRAND_LINE_GAP
        lines = TREBLE_LINES if treble else BASS_LINES
        line = lines[-1] + 2
        while line <= index:
            canvas.create_line(x - reach, self._y_for(line, treble), x + reach,
                               self._y_for(line, treble), fill=colour, width=2)
            line += 2
        line = lines[0] - 2
        while line >= index:
            canvas.create_line(x - reach, self._y_for(line, treble), x + reach,
                               self._y_for(line, treble), fill=colour, width=2)
            line -= 2

    def _onset_x(self, moment: float) -> Optional[float]:
        """
        Dónde cae la cabeza de la nota que empieza en ese instante.

        Los rótulos se dibujaban en el borde izquierdo del tramo y la nota se
        dibuja en su **centro**, así que el cifrado quedaba corrido media
        figura a la izquierda de lo que describe --- media figura que con una
        redonda son sesenta píxeles, y el rótulo aparecía debajo del acorde
        anterior.
        """
        best = None
        for voice in range(GRAND_VOICE_COUNT):
            position = 0.0
            for index, duration, _accidental in self.voices[voice]:
                if position > moment + EPSILON:
                    break
                if abs(position - moment) <= EPSILON and index is not None:
                    x = self._x_for(position + duration / 2.0)
                    best = x if best is None else min(best, x)
                    break
                position += duration
        return best

    def _note_around(self, voice: int, moment: float):
        """La nota de esa voz que suena en ese instante: (x, y) o None."""
        position = 0.0
        for index, duration, _accidental in self.voices[voice]:
            if position - EPSILON <= moment < position + duration - EPSILON:
                if index is None:
                    return None
                return (self._x_for(position + duration / 2.0),
                        self._y_for(index, self.staff_of(voice, index)))
            position += duration
        return None

    def _draw_motions(self) -> None:
        """
        Los movimientos señalados, entre las dos voces de cada par.

        Un trazo fino que **une las dos notas** --- eso es el par --- y, al
        costado de cada una, una flecha corta que dice hacia dónde va esa
        voz. Un movimiento contrario se reconoce viendo las dos flechas
        apuntando al revés, y un paralelo viéndolas apuntar igual.

        Antes se dibujaba una flecha por voz, de la nota que dejaba a la que
        tomaba, y eso se lee como una voz moviéndose consigo misma: la
        flecha contaba la melodía de cada voz y no la relación entre las
        dos, que es de lo que habla el movimiento.
        """
        canvas = self.canvas
        for moment, low, high, way_low, way_high, colour in self.motions:
            a = self._note_around(low, moment)
            b = self._note_around(high, moment)
            if a is None or b is None:
                continue
            tags = (OVERLAY_TAG, OVERLAY_TAG + "-motions")
            canvas.create_line(a[0], a[1], b[0], b[1], fill=colour, width=1,
                               dash=(2, 3), tags=tags)
            for (x, y), way in ((a, way_low), (b, way_high)):
                if way == 0:
                    canvas.create_line(x + 13, y, x + 22, y, fill=colour,
                                       width=2, tags=tags)
                    continue
                canvas.create_line(x + 17, y, x + 17, y - 15 * way,
                                   fill=colour, width=2, arrow="last",
                                   arrowshape=(7, 9, 3), tags=tags)

    def _draw_annotations(self, faint: str, ink: str, bottom: float,
                          figure_top: float) -> None:
        """
        Los rótulos del análisis.

        Arriba el cifrado americano; abajo el cifrado del bajo continuo, en
        **columna**, que es como se escribe de verdad: el 6 sobre el 5. El
        grado con números romanos no está: se lee en la lista de acordes,
        donde hay ancho para ponerlo entero, y acá competía por el único
        lugar que no sobra --- el de al lado de la nota.
        """
        canvas = self.canvas
        # Hasta dónde llega lo último que se escribió en cada renglón. Los
        # rótulos van pegados a la nota que describen, así que en una pieza
        # con un acorde por corchea se pisan unos con otros hasta no leerse
        # ninguno --- y eso pasa en cuanto se cambia la armadura a una que no
        # es la de la pieza, porque entonces casi cada vertical es un acorde
        # distinto. El que no entra no se dibuja: la lista de acordes de al
        # lado los tiene todos y con ancho para leerlos.
        #
        # El ancho de cada cifrado se mide en el lienzo, no se estima: con
        # ocho píxeles por letra un «D6omit5» se metía encima del acorde de
        # al lado. Y el que no entra en su renglón prueba uno más abajo antes
        # de quedarse sin dibujar: en el resultado no hay otra lista que los
        # muestre, y un acorde sin nombre era un hueco en la partitura.
        symbol_edges = [-1e9, -1e9]
        figure_edge = -1e9
        for onset, symbol, figure in self.annotations:
            head = self._onset_x(onset)
            x = self._x_for(onset) + 6 if head is None else head
            if symbol:
                left = x - 7
                for row, y in enumerate((SYMBOL_Y, SYMBOL_Y + SYMBOL_STEP)):
                    if left < symbol_edges[row]:
                        continue
                    item = canvas.create_text(
                        left, y, text=symbol,
                        fill=self.symbol_colours.get(onset, ink), anchor="w",
                        font=("Segoe UI Semibold", 13),
                        tags=(OVERLAY_TAG, OVERLAY_TAG + "-labels"))
                    box = canvas.bbox(item)
                    symbol_edges[row] = (box[2] if box
                                         else left + 9 * len(symbol)) + 6
                    break
            rows = [text for text in figure[:FIGURE_ROWS] if text]
            if not rows:
                continue
            width = 8 * max(len(text) for text in rows)
            if x - width / 2.0 < figure_edge:
                continue
            figure_edge = x + width / 2.0 + 4
            for row, text in enumerate(rows):
                # Centrada bajo la cabeza: una cifra es una columna de números
                # y va debajo de su nota del bajo, como en el papel. Con la
                # tinta de la partitura y no con el acento: es un rótulo que
                # se lee, no un realce, y en azul sobre el fondo oscuro no se
                # distinguía un 6 de un 5.
                canvas.create_text(x, figure_top + row * FIGURE_LINE,
                                   text=tr(text), fill=ink,
                                   anchor="center", font=("Segoe UI", 11),
                                   tags=(OVERLAY_TAG,
                                         OVERLAY_TAG + "-labels"))
        for onset, colour in self.flags:
            x = self._x_for(onset)
            canvas.create_line(x, self._y_for(TREBLE_LINES[-1], True) - 8, x,
                               bottom + 8, fill=colour, width=2, dash=(3, 3),
                               tags=(OVERLAY_TAG, OVERLAY_TAG + "-labels"))
