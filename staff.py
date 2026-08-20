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

import tkinter as tk
from typing import Callable, Dict, List, Optional, Set, Tuple

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
        """Prender o apagar el pedido de acorde sobre una nota."""
        if not 0 <= position < len(self.notes):
            return False
        if position in self.marked:
            self.marked.discard(position)
        else:
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
            self.redraw()
            if self.on_change:
                self.on_change()

    def clear(self) -> None:
        self.notes = []
        self.marked = set()
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
