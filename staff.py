# -*- coding: utf-8 -*-
"""
A staff you can write on.

Notes are entered by clicking where they go, which is how anyone who reads
music expects to enter them. A piano keyboard sits underneath for the cases
where the staff is fiddly -- picking an accidental, or a note far above the
lines -- so neither way of thinking is forced on the user.

The widget owns nothing but the line: it hands back a list of pitches and
durations, and the harmoniser decides what to do with them.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import (Callable, Dict, List, Optional, Sequence, Set,
                    Tuple)

import customtkinter as ctk

#: Staff geometry, in pixels.
#: Generous on purpose. At a tighter spacing a step is only a few pixels and
#: neighbouring notes become impossible to tell apart -- a written G reads as
#: an A, which makes the whole staff untrustworthy.
LINE_GAP = 20               # between adjacent staff lines
STEP = LINE_GAP // 2        # one scale step: line to adjacent space
TOP_MARGIN = 110
LEFT_MARGIN = 150
NOTE_SPACING = 58
#: Lo más apretadas que pueden quedar dos notas antes de que el pentagrama
#: empiece a desplazarse. Es el ancho de una cabeza de nota con su aire: por
#: debajo, dos alturas vecinas dejan de distinguirse y el pentagrama entero
#: deja de ser confiable, que es justo lo que se estaba comprando a cambio
#: de que entrara todo.
MIN_SPACING = 38.0
STAFF_HEIGHT = 340

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

    # -- the ladder ---------------------------------------------------------

    @property
    def _top_index(self) -> int:
        """Staff index of the topmost line."""
        return diatonic_index("F", 5) if self.treble else diatonic_index("A", 3)

    def _y_for(self, index: int) -> float:
        return TOP_MARGIN + (self._top_index - index) * STEP

    def _index_for(self, y: float) -> int:
        return int(round(self._top_index - (y - TOP_MARGIN) / STEP))

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
        usable = max(200, self.canvas.winfo_width() - LEFT_MARGIN - 40)
        return max(MIN_SPACING, min(float(NOTE_SPACING), usable / count))

    def content_width(self) -> float:
        """Cuánto mide el pentagrama escrito, entre en la ventana o no."""
        return LEFT_MARGIN + len(self.notes) * self.spacing() + 40

    # -- desplazamiento -----------------------------------------------------

    def _on_scrolled(self, first: str, last: str) -> None:
        """Mostrar la barra sólo mientras haya algo fuera de la ventana."""
        self.scrollbar.set(first, last)
        needed = float(first) > 0.0 or float(last) < 1.0
        try:
            if needed and not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(fill="x", side="bottom", pady=(2, 0))
            elif not needed and self.scrollbar.winfo_ismapped():
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
        if x < LEFT_MARGIN:
            return -1
        return int((x - LEFT_MARGIN) // self.spacing())

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
        index = self._index_for(event.y)
        # Keep it inside something singable rather than letting a stray click
        # put a note six ledger lines out.
        lowest, highest = self._top_index - 20, self._top_index + 6
        index = max(lowest, min(highest, index))

        if position < len(self.notes):
            # Se reescribe entera, altura y figura. Manteniendo la figura
            # vieja no había forma de corregirla: elegir otra y volver a
            # tocar la nota no hacía nada, y sólo quedaba deshacer hasta
            # llegar a ella. La figura marcada es la herramienta activa.
            self.notes[position] = (index, self.duration)
        else:
            self.notes.append((index, self.duration))
        self.redraw()
        if self.on_change:
            self.on_change()

    def add_pitch(self, midi: int) -> None:
        """Add a note chosen from the piano rather than the staff."""
        octave, semitone = divmod(midi, 12)
        letter = min(LETTERS, key=lambda l: abs(LETTER_SEMITONE[l] - semitone))
        self.notes.append((diatonic_index(letter, octave - 1), self.duration))
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
            self.redraw()
            if self.on_change:
                self.on_change()

    def clear(self) -> None:
        self.notes = []
        self.marked = set()
        self.blocked = set()
        self.harmonised = set()
        self.redraw()
        if self.on_change:
            self.on_change()

    def set_key(self, fifths: int, beats: int, beat_type: int) -> None:
        self.fifths = fifths
        self.beats = beats
        self.beat_type = beat_type
        self.redraw()

    # -- what the harmoniser needs -----------------------------------------

    def pitches(self) -> List[Tuple[int, float]]:
        """(MIDI pitch, duration) for every note written."""
        return [(index_to_pitch(index, self.fifths), duration)
                for index, duration in self.notes]

    def total_quarters(self) -> float:
        return sum(duration for _index, duration in self.notes)

    # -- drawing ------------------------------------------------------------

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        ink = self.colours["text"]
        faint = self.colours["muted"]
        accent = self.colours["accent"]

        width = max(canvas.winfo_width(), 400, int(self.content_width()))
        top = self._y_for(self._top_index)
        for line in range(5):
            y = top + line * LINE_GAP
            canvas.create_line(20, y, width - 20, y, fill=faint)

        canvas.create_text(38, top + 2 * LINE_GAP,
                           text="𝄞" if self.treble else "𝄢",
                           fill=ink, font=("Segoe UI Symbol", 52))
        # The key signature, written where it belongs: without it the user
        # cannot see which notes are altered, and a written F reads the same
        # whether it sounds as F or F sharp.
        x = 66
        if self.fifths:
            order = SHARP_ORDER if self.fifths > 0 else FLAT_ORDER
            glyph = "♯" if self.fifths > 0 else "♭"
            # Standard placement: sharps and flats sit on set lines and
            # spaces, in a fixed order, rather than wherever the note falls.
            positions = (self._sharp_positions() if self.fifths > 0
                         else self._flat_positions())
            for step in range(min(7, abs(self.fifths))):
                y = self._y_for(positions[order[step]])
                canvas.create_text(x, y, text=glyph, fill=ink,
                                   font=("Segoe UI Symbol", 20))
                x += 13

        canvas.create_text(x + 14, top + 2 * LINE_GAP,
                           text=f"{self.beats}/{self.beat_type}",
                           fill=ink, font=("Segoe UI Semibold", 15))

        # Bar lines fall wherever the written durations fill a bar.
        quarters_per_bar = self.beats * 4.0 / self.beat_type
        running = 0.0
        step_x = self.spacing()
        gold = self.colours.get("gold", self.colours["accent"])
        for position, (index, duration) in enumerate(self.notes):
            x = LEFT_MARGIN + position * step_x + step_x / 2
            y = self._y_for(index)
            self._draw_ledgers(x, index, top, faint)

            # Dorada la nota que va a recibir un acorde. Es lo único que
            # contesta la pregunta con la que se escribe una melodía para
            # que otro la armonice: cuál de estas notas va a sostener la
            # armonía y cuál va a pasar por encima de ella.
            pinned = position in self.marked
            colour = gold if (pinned or position in self.harmonised) else ink
            if pinned:
                # Un anillo alrededor de la cabeza: la marcó el usuario, y
                # sin él marcar una nota que el programa ya iba a armonizar
                # no se veía --- el click quedaba sin respuesta.
                canvas.create_oval(x - 15, y - 12, x + 15, y + 12,
                                   outline=gold, width=1)
            filled = duration <= 1.0
            canvas.create_oval(x - 10, y - 7, x + 10, y + 7,
                               fill=colour if filled else "",
                               outline=colour, width=2)
            if duration in DOTTED:
                canvas.create_oval(x + 15, y - 2, x + 19, y + 2,
                                   fill=colour, outline=colour)
            if duration < 4.0:
                up = index < self._top_index - 4
                stem_x = x + 10 if up else x - 10
                stem_y = y - 52 if up else y + 52
                canvas.create_line(stem_x, y, stem_x, stem_y, fill=colour, width=2)
                if duration <= 0.75:
                    canvas.create_line(stem_x, stem_y, stem_x + 9,
                                       stem_y + (11 if up else -11),
                                       fill=colour, width=2)

            running += duration
            if abs(running % quarters_per_bar) < 1e-6:
                bar_x = LEFT_MARGIN + (position + 1) * step_x
                canvas.create_line(bar_x, top, bar_x, top + 4 * LINE_GAP,
                                   fill=faint, width=2)

        canvas.configure(scrollregion=(0, 0, width, STAFF_HEIGHT))
        if not self.notes:
            canvas.create_text(max(canvas.winfo_width(), 400) / 2,
                               top + 2 * LINE_GAP + 60,
                               text="Hacé click en el pentagrama para escribir "
                                    "la melodía",
                               fill=faint, font=("Segoe UI", 12))

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

    def _draw_ledgers(self, x: float, index: int, top: float, colour: str) -> None:
        """Short lines for notes that sit off the staff."""
        highest, lowest = self._top_index, self._top_index - 8
        step = 2
        position = highest + step
        while position <= index:
            y = self._y_for(position)
            self.canvas.create_line(x - 16, y, x + 16, y, fill=colour)
            position += step
        position = lowest - step
        while position >= index:
            y = self._y_for(position)
            self.canvas.create_line(x - 16, y, x + 16, y, fill=colour)
            position -= step


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
GRAND_TOP_MARGIN = 84
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
                 **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.colours = colours
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

        self.canvas = tk.Canvas(self, height=GRAND_HEIGHT, highlightthickness=0,
                                bg=colours["surface"])
        self.scrollbar = ctk.CTkScrollbar(
            self, orientation="horizontal", command=self.canvas.xview,
            height=12, button_color=colours["muted"],
            button_hover_color=colours["accent"], fg_color="transparent")
        self.canvas.configure(xscrollcommand=self._on_scrolled)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_erase)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._on_motion(None))
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel)

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

    def spacing(self) -> float:
        """Cuánto mide una negra, apretándose cuando la pieza es larga."""
        total = self.total_quarters()
        if total <= 0:
            return PIXELS_PER_QUARTER
        usable = max(240, self.canvas.winfo_width() - GRAND_LEFT_MARGIN - 40)
        return max(MIN_PIXELS_PER_QUARTER,
                   min(PIXELS_PER_QUARTER, usable / total))

    def _x_for(self, quarters: float) -> float:
        return GRAND_LEFT_MARGIN + quarters * self.spacing()

    def _time_at(self, x: float) -> float:
        """En qué momento de la pieza, en negras, cae una posición del lienzo."""
        return max(0.0, (x - GRAND_LEFT_MARGIN) / self.spacing())

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
        self.annotations = []
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
        for voice in range(GRAND_VOICE_COUNT):
            position = 0.0
            for order, (index, duration, _accidental) in enumerate(self.voices[voice]):
                if index is None:
                    position += duration
                    continue
                note_x = self._x_for(position + duration / 2.0)
                note_y = self._y_for(index, self.staff_of(voice, index))
                if abs(x - note_x) <= 10 and abs(y - note_y) <= 7:
                    return voice, order
                position += duration
        return None

    # -- clicks -------------------------------------------------------------

    def _on_click(self, event) -> None:
        """Escribir donde se tocó, y contestar qué se escribió."""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if x < GRAND_LEFT_MARGIN:
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
        try:
            if needed and not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(fill="x", side="bottom", pady=(2, 0))
            elif not needed and self.scrollbar.winfo_ismapped():
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
        """Dónde arranca el cifrado del bajo, sin pisar ninguna nota."""
        floor = BASS_TOP_MARGIN + 4 * GRAND_LINE_GAP + FIGURE_CLEARANCE
        lowest = None
        for voice in range(GRAND_VOICE_COUNT):
            for index, _duration, _accidental in self.voices[voice]:
                if index is None or self.staff_of(voice, index):
                    continue
                if lowest is None or index < lowest:
                    lowest = index
        if lowest is None:
            return floor
        return max(floor, self._y_for(lowest, False) + 32)

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        ink = self.colours["text"]
        faint = self.colours["muted"]
        spacing = self.spacing()
        total = self.total_quarters()
        width = max(canvas.winfo_width(), 420,
                    int(GRAND_LEFT_MARGIN + total * spacing + 60))
        top = self._y_for(TREBLE_LINES[-1], True)
        bottom = self._y_for(BASS_LINES[0], False)
        figure_top = self._figure_top()
        rows = max((len(figure) for _o, _s, figure in self.annotations),
                   default=0)
        height = int(figure_top + max(1, min(FIGURE_ROWS, rows)) * FIGURE_LINE
                     + 6)
        try:
            if int(canvas.cget("height")) != height:
                canvas.configure(height=height)
        except (tk.TclError, ValueError):
            pass

        if self.highlight is not None:
            start, end = self.highlight
            canvas.create_rectangle(
                self._x_for(start), top - 10, self._x_for(end), bottom + 10,
                fill=self.colours.get("glow", self.colours["surface"]),
                outline="")

        for group, treble in ((TREBLE_LINES, True), (BASS_LINES, False)):
            for index in group:
                y = self._y_for(index, treble)
                canvas.create_line(24, y, width - 24, y, fill=faint)
        # La barra que une los dos pentagramas: es lo que los hace un sistema
        # y no dos pentagramas puestos uno encima del otro.
        canvas.create_line(24, top, 24, bottom, fill=ink, width=3)

        self._draw_clefs(ink)
        x = self._draw_signature(84, ink)
        beats, beat_type = self.metre_at(1)
        self._draw_metre(x + 16, beats, beat_type, ink)

        self._mark_active(width)
        self._draw_bar_lines(total, width, faint, ink, top, bottom)
        for voice in range(GRAND_VOICE_COUNT):
            self._draw_voice(voice)
        self._draw_motions()
        self._draw_annotations(faint, ink, bottom, figure_top)

        canvas.configure(scrollregion=(0, 0, width, height))
        if self.is_empty():
            canvas.create_text(
                max(canvas.winfo_width(), 420) / 2, bottom + 40,
                text="Elegí una voz y hacé click donde va cada nota, "
                     "o importá una partitura.",
                fill=faint, font=("Segoe UI", 12))

    def _draw_clefs(self, ink: str) -> None:
        """
        Las dos claves.

        La de sol se dibuja **corrida hacia arriba**: el signo no está
        centrado en su propio cuadro ---la cola baja mucho más de lo que
        sube el rulo--- así que puesto con el centro en la segunda línea, que
        es lo que dice la teoría, queda visiblemente hundido contra el
        pentagrama.
        """
        canvas = self.canvas
        canvas.create_text(54, self._y_for(TREBLE_LINES[1], True) - 7,
                           text="𝄞", fill=ink, font=("Segoe UI Symbol", 44))
        canvas.create_text(54, self._y_for(BASS_LINES[3], False) - 2,
                           text="𝄢", fill=ink, font=("Segoe UI Symbol", 36))

    def _draw_metre(self, x: float, beats: int, beat_type: int,
                    colour: str) -> None:
        """El compás, en los dos pentagramas."""
        for treble, lines in ((True, TREBLE_LINES), (False, BASS_LINES)):
            self.canvas.create_text(x, self._y_for(lines[3], treble),
                                    text=str(beats), fill=colour,
                                    font=("Segoe UI Semibold", 14))
            self.canvas.create_text(x, self._y_for(lines[1], treble),
                                    text=str(beat_type), fill=colour,
                                    font=("Segoe UI Semibold", 14))

    def _draw_signature(self, x: float, ink: str) -> float:
        """La armadura, en los dos pentagramas y en el orden de siempre."""
        if not self.fifths:
            return x
        order = SHARP_ORDER if self.fifths > 0 else FLAT_ORDER
        glyph = "♯" if self.fifths > 0 else "♭"
        rows = ((self._sharp_row(5) if self.fifths > 0 else self._flat_row(5),
                 True),
                (self._sharp_row(3) if self.fifths > 0 else self._flat_row(3),
                 False))
        for step in range(min(7, abs(self.fifths))):
            letter = order[step]
            for row, treble in rows:
                self.canvas.create_text(x, self._y_for(row[letter], treble),
                                        text=glyph, fill=ink,
                                        font=("Segoe UI Symbol", 16))
            x += 12
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
                self._y_for(lines[0], treble), fill=colour, outline="")

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
            if bar > 1:
                self.canvas.create_line(x, top, x, bottom, fill=colour, width=1)
            if start < total - EPSILON or bar == 1:
                self.canvas.create_text(x + 5, BAR_NUMBER_Y, text=str(bar),
                                        fill=colour, anchor="w",
                                        font=("Segoe UI", 9))
            if bar > 1 and (beats, beat_type) != previous:
                self._draw_metre(x + 16, beats, beat_type, ink)
            previous = (beats, beat_type)

    def _draw_voice(self, voice: int) -> None:
        """
        Una voz entera, con el color que le toca.

        Todas van con su color y no sólo la que se está escribiendo: el
        color es lo que dice cuál es cuál cuando cuatro voces comparten dos
        pentagramas, y apagando las otras tres esa información se perdía
        justo cuando más hace falta. La voz activa se distingue por otro
        lado --- se dibuja al final, así que queda arriba de las demás.
        """
        canvas = self.canvas
        colour = VOICE_COLOURS[min(3, GRAND_VOICE_COUNT - 1 - voice)]
        faint = self.colours["muted"]
        position = 0.0
        for index, duration, accidental in self.voices[voice]:
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
                continue
            y = self._y_for(index, treble)
            self._draw_ledgers(x, index, faint, treble)
            if accidental is not None:
                canvas.create_text(x - 15, y,
                                   text=ACCIDENTALS.get(accidental, ""),
                                   fill=colour, font=("Segoe UI Symbol", 15))
            filled = duration <= 1.0
            canvas.create_oval(x - 6, y - 5, x + 6, y + 5,
                               fill=colour if filled else "",
                               outline=colour, width=2)
            if duration in DOTTED:
                canvas.create_oval(x + 9, y - 2, x + 13, y + 2,
                                   fill=colour, outline=colour)
            if duration < 4.0:
                # La voz aguda de cada pentagrama lleva la plica para
                # arriba y la grave para abajo: es como se escriben dos
                # voces en una misma clave sin que se confundan.
                up = voice % 2 == 1
                stem_x = x + 6 if up else x - 6
                stem_y = y - 26 if up else y + 26
                canvas.create_line(stem_x, y, stem_x, stem_y, fill=colour,
                                   width=2)
                if duration <= 0.75:
                    canvas.create_line(stem_x, stem_y, stem_x + 8,
                                       stem_y + (10 if up else -10),
                                       fill=colour, width=2)
            position += duration

    def _draw_rest(self, x: float, y: float, duration: float,
                   colour: str) -> None:
        """
        Un silencio, dibujado.

        Con signos de la fuente no se podía: los caracteres musicales de
        Unicode no están en todas las fuentes de sistema, y el que falta se
        dibuja como un rectángulo vacío --- que es exactamente lo que se veía
        en lugar del silencio de negra. Cuatro trazos son más confiables que
        una fuente que puede no estar.
        """
        canvas = self.canvas
        figure = rest_glyph(duration)
        dotted = duration in DOTTED
        if figure >= 4.0:
            # Redonda: colgada de la cuarta línea.
            canvas.create_rectangle(x - 7, y - 8, x + 7, y - 2,
                                    fill=colour, outline="")
        elif figure >= 2.0:
            # Blanca: apoyada sobre la línea del medio.
            canvas.create_rectangle(x - 7, y + 1, x + 7, y + 7,
                                    fill=colour, outline="")
        elif figure >= 1.0:
            # Negra: el zigzag de siempre, con su gancho al pie.
            canvas.create_line(x - 4, y - 12, x + 4, y - 4, fill=colour,
                               width=3)
            canvas.create_line(x + 4, y - 4, x - 4, y + 3, fill=colour,
                               width=3)
            canvas.create_line(x - 4, y + 3, x + 5, y + 11, fill=colour,
                               width=3)
            canvas.create_arc(x - 5, y + 7, x + 5, y + 17, start=40,
                              extent=130, style="arc", outline=colour,
                              width=2)
        else:
            # Corchea y semicorchea: la barra oblicua con una o dos bolitas.
            canvas.create_line(x + 4, y - 9, x - 4, y + 9, fill=colour,
                               width=2)
            canvas.create_oval(x + 1, y - 12, x + 6, y - 7, fill=colour,
                               outline=colour)
            if figure <= 0.25:
                canvas.create_oval(x - 2, y - 4, x + 3, y + 1, fill=colour,
                                   outline=colour)
        if dotted:
            canvas.create_oval(x + 9, y - 2, x + 13, y + 2, fill=colour,
                               outline=colour)

    def _draw_ledgers(self, x: float, index: int, colour: str,
                      treble: bool) -> None:
        """Las líneas cortas de una nota que se salió de su pentagrama."""
        canvas = self.canvas
        lines = TREBLE_LINES if treble else BASS_LINES
        line = lines[-1] + 2
        while line <= index:
            canvas.create_line(x - 12, self._y_for(line, treble), x + 12,
                               self._y_for(line, treble), fill=colour)
            line += 2
        line = lines[0] - 2
        while line >= index:
            canvas.create_line(x - 12, self._y_for(line, treble), x + 12,
                               self._y_for(line, treble), fill=colour)
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
            canvas.create_line(a[0], a[1], b[0], b[1], fill=colour, width=1,
                               dash=(2, 3))
            for (x, y), way in ((a, way_low), (b, way_high)):
                if way == 0:
                    canvas.create_line(x + 11, y, x + 20, y, fill=colour,
                                       width=2)
                    continue
                canvas.create_line(x + 15, y, x + 15, y - 15 * way,
                                   fill=colour, width=2, arrow="last",
                                   arrowshape=(7, 9, 3))

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
        symbol_edge = -1e9
        figure_edge = -1e9
        for onset, symbol, figure in self.annotations:
            head = self._onset_x(onset)
            x = self._x_for(onset) + 6 if head is None else head
            if symbol:
                left = x - 7
                if left >= symbol_edge:
                    canvas.create_text(left, SYMBOL_Y, text=symbol, fill=ink,
                                       anchor="w",
                                       font=("Segoe UI Semibold", 13))
                    symbol_edge = left + 8 * len(symbol) + 6
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
                                   text=text, fill=ink,
                                   anchor="center", font=("Segoe UI", 11))
        for onset, colour in self.flags:
            x = self._x_for(onset)
            canvas.create_line(x, self._y_for(TREBLE_LINES[-1], True) - 8, x,
                               bottom + 8, fill=colour, width=2, dash=(3, 3))
