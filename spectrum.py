# -*- coding: utf-8 -*-
"""
El experimentador de armónicos: un gráfico que además es el instrumento.

La idea es que no haya distancia entre mirar y escuchar. El gráfico no
ilustra el sonido: **es** el sonido. Cada barra es un armónico, arrastrarla
lo amplifica, correrla lo desafina, y el botón toca exactamente lo que se
está viendo --- las dos cosas leen la misma lista de
:func:`engine.harmonics.sounding`.

Por qué el control va en el dibujo
----------------------------------
La versión obvia era una fila de deslizadores por armónico. Son doce
armónicos y dos cosas que hacerle a cada uno, o sea veinticuatro
deslizadores de ``customtkinter``, cada uno con su propio lienzo: la
pantalla tardaba en abrirse y de todos modos había que mirar a otro lado
para saber qué estaba tocando cada fila. Con el arrastre sobre el lienzo
queda un solo dibujo, se abre instantáneo, y la mano está sobre el armónico
que está cambiando.

Sin dependencias, igual que el resto: ``tkinter`` y ``customtkinter`` para
la ventana, y la síntesis a mano en ``engine/harmonics.py``. Este módulo no
importa ``app``; los colores llegan por parámetro, como en ``staff.py``.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from engine import harmonics
from engine.i18n import N, tr, trf, trs
from engine import i18n
from engine.theory import SHARP_NAMES

#: Medidas del gráfico. El alto es lo único que no se estira: una barra
#: necesita recorrido vertical para que arrastrarla se sienta como subir un
#: volumen y no como apretar un botón.
PLOT_HEIGHT = 322
PLOT_PAD_LEFT = 46
PLOT_PAD_RIGHT = 16
PLOT_PAD_TOP = 24
#: Dos filas debajo del piso: el número de cada armónico y, más abajo, los
#: hercios y el rótulo del eje. En una sola fila el «frecuencia →» se comía
#: el 11 y el 12.
PLOT_PAD_BOTTOM = 44

#: Ancho de una barra y cuánto alrededor cuenta como «le diste».
BAR_WIDTH = 14
GRAB = 18

#: El teclado de abajo: dos octavas para elegir la fundamental. Se dibuja
#: centrado y con un ancho fijo --- quince teclas blancas ---, no estirado al
#: panel: una tecla que cambia de ancho con la ventana deja de parecer una
#: tecla.
KEY_WIDTH = 38
KEY_HEIGHT = 88
BLACK_WIDTH = 24
BLACK_HEIGHT = 55
KEYBOARD_WIDTH = KEY_WIDTH * 15

WHITE_SEMITONES = (0, 2, 4, 5, 7, 9, 11)
BLACK_BEFORE = {1: 0, 3: 1, 6: 3, 8: 4, 10: 5}

#: Cuántos píxeles de arrastre vertical valen toda la escala de amplitud, y
#: cuántos de arrastre horizontal valen todo el desvío posible. Los dos
#: bastante más largos que el recorrido que cubren: arrastrar es un gesto
#: grueso y con la escala pegada al dibujo cualquier temblor de la mano
#: saltaba media barra.
DRAG_SPAN = float(PLOT_HEIGHT - PLOT_PAD_TOP - PLOT_PAD_BOTTOM) * 1.7
SHIFT_SPAN = 165.0

#: Cuánto hay que arrastrar antes de que el gesto elija un eje y se quede con
#: él hasta soltar. Correr un armónico de lugar y amplificarlo son dos cosas
#: distintas, y sin esto no había manera de hacer una sola: mover el mouse en
#: línea recta es imposible, así que un arrastre horizontal siempre subía o
#: bajaba la barra de paso. Elegido el eje, el otro queda quieto; para mover
#: el otro se suelta y se vuelve a agarrar.
AXIS_LOCK = 7.0

#: Nombres de nota en castellano. El resto del programa escribe en cifrado
#: americano ---es lo que el usuario tipea--- pero acá lo que se está
#: leyendo es física, y quien abre esta pantalla puede no saber que A es la.
SOLFEGE = {"C": "do", "C#": "do♯", "D": "re", "D#": "re♯", "E": "mi",
           "F": "fa", "F#": "fa♯", "G": "sol", "G#": "sol♯", "A": "la",
           "A#": "la♯", "B": "si"}


def note_label(midi: int) -> str:
    """``la3`` o ``A3``, según el idioma, y con su octava."""
    if midi <= 0:
        return ""
    name = SHARP_NAMES[midi % 12]
    # En inglés la letra ya es el nombre; en castellano se dice con solfeo
    # y en minúscula, que es como se nombra una altura concreta.
    if i18n.language() == "en":
        return f"{name}{midi // 12 - 1}"
    return f"{SOLFEGE.get(name, name)}{midi // 12 - 1}"


def hz_label(frequency: float) -> str:
    """
    Con la coma decimal del castellano, y sin decimales de más.

    Sin separador de miles: en castellano el de miles es el punto, y
    ``1.540 Hz`` al lado de ``220,0 Hz`` se lee como un número con coma
    decimal puesta del otro lado.
    """
    if frequency >= 1000.0:
        return trf("{frequency:.0f} Hz", frequency=frequency)
    # La coma decimal es del castellano; en inglés el separador es el punto.
    written = f"{frequency:.1f}"
    if i18n.language() != "en":
        written = written.replace(".", ",")
    return written + " Hz"


def cents_label(cents: float) -> str:
    """``+2¢``, ``−14¢``, o vacío cuando la nota cae justo."""
    if abs(cents) < 0.5:
        return tr("justo")
    return f"{'+' if cents > 0 else '−'}{abs(cents):.0f}¢"


#: Cómo se llama cada distancia dentro de una octava, en semitonos. Van
#: marcadas con `N` porque las traduce `interval_label` al dibujarlas, lejos
#: de acá: sin la marca, la herramienta que junta las claves no las ve.
INTERVALS = (
    N("unísono"), N("2ª menor"), N("2ª mayor"), N("3ª menor"), N("3ª mayor"),
    N("4ª justa"), N("tritono"), N("5ª justa"), N("6ª menor"), N("6ª mayor"),
    N("7ª menor"), N("7ª mayor"))


def interval_label(semitones: int) -> str:
    """
    A qué distancia de la fundamental está esto.

    Es lo que hace legible la serie de un vistazo: que el segundo armónico
    sea una octava y el tercero una octava y una quinta no se deduce de
    ``440 Hz``, y es de donde sale toda la armonía del programa.

    Se cuenta contra la tecla más cercana, así que un armónico corrido lo
    dice corrido --- que es exactamente lo que uno quiere ver al correrlo.
    """
    if semitones <= 0:
        return tr(INTERVALS[0])
    octaves, rest = divmod(int(semitones), 12)
    name = tr(INTERVALS[rest])
    if not octaves:
        return name
    span = tr("1 octava") if octaves == 1 else trf("{octaves} octavas",
                                                   octaves=octaves)
    return span if rest == 0 else f"{span} + {name}"


class Experimenter(ctk.CTkFrame):
    """
    El panel entero: gráfico, teclado, controles del armónico elegido.

    ``on_experiment`` se llama cada vez que se toca un sonido, con
    ``fresh=True`` cuando la configuración cambió respecto de la última que
    sonó. Apretar «Escuchar» tres veces seguidas sin mover nada es una sola
    cosa escuchada tres veces, no tres experimentos, y quien lleva la cuenta
    afuera no tiene por qué saber mirar un espectro para darse cuenta.
    """

    #: Con qué ancho arrancan los párrafos. Angosto a propósito: mientras
    #: sea chico no le piden lugar a nadie, y el lugar lo reparte el
    #: gráfico. Ver `_wrapping`.
    PARAGRAPH_MIN = 200

    def __init__(self, master, colours: Dict[str, str],
                 on_experiment: Optional[Callable[[bool], None]] = None,
                 on_instrument: Optional[Callable[[str], None]] = None,
                 **kwargs):
        super().__init__(master, fg_color=colours["panel"], corner_radius=12,
                         **kwargs)
        self.colours = colours
        self.on_experiment = on_experiment
        #: A quién avisar si, después de guardar un timbre, el usuario pide
        #: que el programa toque con él. Llega por parámetro porque este
        #: módulo no importa la aplicación; sin nadie que escuche, guardar
        #: no pregunta nada.
        self.on_instrument = on_instrument
        self.spectrum = harmonics.build()
        self.preset_name = harmonics.DEFAULT_PRESET
        #: Qué armónico está elegido. Siempre hay uno: sin ninguno, los
        #: controles de abajo estarían vacíos la primera vez que se abre y
        #: no habría manera de adivinar que el gráfico se toca.
        self.selected = 1
        self._dragging: Optional[int] = None
        self._drag_from: Tuple[float, float] = (0.0, 0.0)
        self._drag_start: Tuple[float, float] = (0.0, 0.0)
        self._drag_ceiling = 1.0
        #: Con qué eje se quedó el arrastre en curso: ``"x"``, ``"y"`` o
        #: vacío mientras todavía no se movió lo suficiente para decidir.
        self._axis = ""
        self._sound = None
        #: La configuración que sonó la última vez, para no contar dos veces
        #: el mismo experimento.
        self._last_heard: Optional[tuple] = None
        self._bars: List[Tuple[int, float]] = []
        #: Los párrafos cuyo ancho manda el gráfico. Ver `_wrapping`.
        self._paragraphs: List = []

        self._build()
        self._redraw()
        self._refresh_controls()

    # -- armado -------------------------------------------------------------

    def _build(self) -> None:
        """
        El panel, de arriba abajo: el gráfico primero y los mandos después.

        El gráfico va entero y a lo ancho porque es a la vez lo que se mira y
        lo que se toca. Debajo, dos columnas: a la izquierda lo que le pasa
        al armónico elegido y a todo el conjunto, a la derecha qué nota es.
        Poner el teclado abajo de todo dejaba la elección de la nota ---que
        es lo primero que uno hace--- al final del recorrido de la vista.
        """
        colours = self.colours
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(head, text=tr("Una nota, desarmada"),
                     font=self._font(("Segoe UI Semibold", 17))
                     ).pack(side="left")
        self.play_button = ctk.CTkButton(
            head, text=tr("▶  Escuchar"), width=128, height=34, corner_radius=9,
            font=self._font(("Segoe UI", 13)), fg_color=colours["accent"],
            hover_color=colours["accent_hover"], command=self.play)
        self.play_button.pack(side="right")
        # El timbre, para lleváselo a otro programa. Va al lado de
        # «Escuchar» porque es la misma acción mirada de lejos: una es oírlo
        # acá y la otra es oírlo en otro lado.
        self.save_button = ctk.CTkButton(
            head, text=tr("Guardar timbre…"), width=140, height=34,
            corner_radius=9, font=self._font(("Segoe UI", 12)),
            fg_color="transparent", border_width=1,
            border_color=colours["border"], text_color=colours["muted"],
            hover_color=colours["surface"], command=self.save_instrument)
        self.save_button.pack(side="right", padx=(0, 8))

        # En dos etiquetas y no en una: tkinter no sabe poner un tramo en
        # negrita adentro de un texto, y lo único que hay que leer sí o sí
        # es cómo se toca el gráfico. Es el mismo recurso que usa el libro
        # para sus entradillas.
        intro = ctk.CTkLabel(
            self,
            text=tr("Todo sonido tiene una frecuencia de base y además sus "
                    "múltiplos enteros. Cada barra es uno de esos múltiplos."),
            font=self._font(("Segoe UI", 11)), text_color=colours["muted"],
            justify="left", anchor="w")
        intro.pack(fill="x", padx=18, pady=(4, 1))
        self._wrapping(intro)
        how = ctk.CTkLabel(
            self,
            text=tr("Arrastrá una barra hacia arriba para subirla, o hacia el "
                    "costado para desafinarla."),
            font=self._font(("Segoe UI Semibold", 11)),
            text_color=colours["text"], justify="left", anchor="w")
        how.pack(fill="x", padx=18, pady=(0, 8))
        self._wrapping(how)

        self.plot = tk.Canvas(self, height=PLOT_HEIGHT, bg=colours["surface"],
                              highlightthickness=0, bd=0)
        self.plot.pack(fill="x", padx=16)
        self.plot.bind("<Button-1>", self._on_press)
        self.plot.bind("<B1-Motion>", self._on_drag)
        self.plot.bind("<ButtonRelease-1>", self._on_release)
        self.plot.bind("<Double-Button-1>", self._on_double)
        self.plot.bind("<Configure>", lambda _e: self._redraw())

        # -- lo que se sabe del armónico elegido ----------------------------
        self.reading = tk.Label(
            self, text="", bg=colours["panel"], fg=colours["text"],
            font=self._font(("Consolas", 13)), anchor="w", justify="left")
        self.reading.pack(fill="x", padx=20, pady=(12, 0))
        self.gloss = tk.Label(
            self, text="", bg=colours["panel"], fg=colours["muted"],
            font=self._font(("Segoe UI", 11, "italic")), anchor="w",
            justify="left", height=2)
        self.gloss.pack(fill="x", padx=20, pady=(2, 10))
        self._wrapping(self.gloss)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=KEYBOARD_WIDTH + 8)

        mandos = ctk.CTkFrame(body, fg_color="transparent")
        mandos.grid(row=0, column=0, sticky="nw", padx=(0, 16))

        self._caption(mandos, "El armónico elegido")
        buttons = ctk.CTkFrame(mandos, fg_color="transparent")
        buttons.pack(fill="x", pady=(0, 10))
        self.solo_button = self._chip(buttons, "Aislar", self.toggle_solo)
        self.mute_button = self._chip(buttons, "Silenciar", self.toggle_mute)
        self._chip(buttons, N("Centrar"), self.recentre)

        self._caption(mandos, "Todos a la vez")
        recipe = ctk.CTkFrame(mandos, fg_color="transparent")
        recipe.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(recipe, text=tr("Forma de onda"),
                     font=self._font(("Segoe UI", 11)), width=76, anchor="w",
                     text_color=colours["muted"]).pack(side="left")
        self.preset_menu = ctk.CTkOptionMenu(
            recipe, values=trs(harmonics.PRESET_NAMES), width=176, height=28,
            font=self._font(("Segoe UI", 11)), corner_radius=8,
            fg_color=colours["surface"], button_color=colours["surface"],
            button_hover_color=colours["accent"],
            command=self._chose_preset)
        self.preset_menu.set(tr(self.preset_name))
        self.preset_menu.pack(side="left")

        self.vibrato = self._slider(mandos, "Vibrato", "la afinación oscila",
                                    0.0, 45.0, self._on_vibrato)
        self.tremolo = self._slider(mandos, "Trémolo", "el volumen oscila",
                                    0.0, 1.0, self._on_tremolo)

        # -- de qué nota son estos armónicos --------------------------------
        note = ctk.CTkFrame(body, fg_color="transparent")
        note.grid(row=0, column=1, sticky="ne")
        self._caption(note, "La nota de la que salen")
        self.keys = tk.Canvas(note, height=KEY_HEIGHT + 4,
                              width=KEYBOARD_WIDTH, bg=colours["panel"],
                              highlightthickness=0, bd=0)
        self.keys.pack(anchor="e")
        self.keys.bind("<Button-1>", self._on_key)
        self._draw_keys()

        foot = ctk.CTkFrame(note, fg_color="transparent")
        foot.pack(fill="x", pady=(8, 0))
        self.fundamental_label = ctk.CTkLabel(
            foot, text="", font=self._font(("Segoe UI", 12)),
            text_color=colours["muted"])
        self.fundamental_label.pack(side="left")
        ctk.CTkButton(
            foot, text=tr("Reiniciar"), width=90, height=28, corner_radius=8,
            font=self._font(("Segoe UI", 11)), fg_color="transparent",
            border_width=1, border_color=colours["border"],
            text_color=colours["muted"], hover_color=colours["surface"],
            command=self.reset).pack(side="right")

    def _caption(self, master, text: str) -> None:
        """El rotulito que encabeza un grupo de mandos."""
        ctk.CTkLabel(master, text=tr(text).upper(),
                     font=self._font(("Segoe UI Semibold", 9)),
                     text_color=self.colours["faint"], anchor="w"
                     ).pack(anchor="w", pady=(0, 5))

    def _font(self, spec):
        """Las fuentes pasan por el escalador de la aplicación si lo hay."""
        scaler = self.colours.get("font")
        return scaler(spec) if callable(scaler) else spec

    def _wrapping(self, label) -> None:
        """
        Registrar un párrafo para que su ancho lo mande el gráfico.

        Un ``wraplength`` fijo es un ancho **pedido**: un párrafo largo lo
        reclama entero y estira el panel que lo contiene. Y como el ancho
        del panel es el del gráfico, elegir un armónico con descripción
        larga ensanchaba el panel diecisiete píxeles y **corría todas las
        barras de lugar** --- justo debajo del mouse que acababa de tocar
        una.

        Arrancan angostos, así que no piden nada y el ancho lo reparte el
        gráfico. Quien se los ensancha después es `_redraw`, con la medida
        del lienzo.

        **No se atan a su propio ``<Configure>``**, que es lo que parecía
        obvio y colgaba el programa: cambiarle el ``wraplength`` a una
        etiqueta le cambia el alto, eso vuelve a acomodar el panel, el
        acomodo dispara otro ``<Configure>`` y la ventana se queda
        recalculando para siempre. Midiendo el lienzo se corta el lazo: el
        lienzo no depende de los párrafos.
        """
        label.configure(wraplength=self.PARAGRAPH_MIN)
        self._paragraphs.append(label)

    def _fit_paragraphs(self, width: int) -> None:
        """Acomodar los párrafos al ancho del gráfico."""
        wanted = max(self.PARAGRAPH_MIN, width - 24)
        for label in self._paragraphs:
            try:
                if abs(int(label.cget("wraplength") or 0) - wanted) > 2:
                    label.configure(wraplength=wanted)
            except (tk.TclError, ValueError):
                pass

    def _chip(self, master, text: str, command) -> ctk.CTkButton:
        button = ctk.CTkButton(
            master, text=tr(text), width=88, height=26, corner_radius=8,
            font=self._font(("Segoe UI", 11)), fg_color="transparent",
            border_width=1, border_color=self.colours["border"],
            text_color=self.colours["muted"],
            hover_color=self.colours["surface"], command=command)
        button.pack(side="left", padx=(0, 6))
        return button

    def _slider(self, master, title: str, hint: str, low: float, high: float,
                command) -> ctk.CTkSlider:
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(row, text=tr(title), font=self._font(("Segoe UI", 11)),
                     text_color=self.colours["muted"], width=76, anchor="w"
                     ).pack(side="left")
        slider = ctk.CTkSlider(row, from_=low, to=high, width=176, height=14,
                               command=command,
                               button_color=self.colours["accent"],
                               progress_color=self.colours["accent"])
        slider.set(low)
        slider.pack(side="left")
        ctk.CTkLabel(row, text=tr(hint), font=self._font(("Segoe UI", 10)),
                     text_color=self.colours["faint"]
                     ).pack(side="left", padx=(12, 0))
        return slider

    # -- el gráfico ---------------------------------------------------------

    def _geometry(self) -> Tuple[float, float, float, float]:
        """Los bordes útiles del lienzo: izquierda, derecha, piso, techo."""
        width = max(self.plot.winfo_width(), 320)
        return (PLOT_PAD_LEFT, width - PLOT_PAD_RIGHT,
                PLOT_HEIGHT - PLOT_PAD_BOTTOM, PLOT_PAD_TOP)

    def _scale(self) -> Tuple[float, float]:
        """Cuánto vale un hercio en píxeles, y cuánto vale una unidad de amplitud."""
        left, right, floor_y, top = self._geometry()
        span = self.spectrum.fundamental * (harmonics.PARTIAL_COUNT + 0.7)
        ceiling = max(1.0, harmonics.peak_gain(self.spectrum))
        return (right - left) / span, (floor_y - top) / ceiling

    def _redraw(self) -> None:
        canvas = self.plot
        try:
            canvas.delete("all")
        except tk.TclError:
            return
        colours = self.colours
        left, right, floor_y, top = self._geometry()
        per_hz, per_gain = self._scale()
        ceiling = max(1.0, harmonics.peak_gain(self.spectrum))
        # El lienzo ya está medido, así que es el momento de decirle a los
        # párrafos cuánto lugar tienen.
        self._fit_paragraphs(int(right - left) + PLOT_PAD_LEFT + PLOT_PAD_RIGHT)

        # Rejilla de amplitud. Tres líneas alcanzan para dar escala sin que
        # el fondo compita con las barras.
        for fraction in (0.25, 0.5, 0.75, 1.0):
            y = floor_y - fraction * ceiling * per_gain
            canvas.create_line(left, y, right, y, fill=colours["border"],
                               dash=(1, 4))
        canvas.create_line(left, floor_y, right, floor_y,
                           fill=colours["muted"])
        canvas.create_line(left, floor_y, left, top, fill=colours["muted"])
        canvas.create_text(left - 11, (floor_y + top) / 2, text=tr("amplitud"),
                           anchor="center", fill=colours["muted"],
                           font=self._font(("Segoe UI", 9)), angle=90)
        canvas.create_text(right, floor_y + 28, text=tr("frecuencia →"),
                           anchor="e", fill=colours["faint"],
                           font=self._font(("Segoe UI", 9)))
        canvas.create_text(left, floor_y + 28,
                           text=trf("{frequency}  y sus múltiplos",
                                    frequency=hz_label(
                                        self.spectrum.fundamental)),
                           anchor="w", fill=colours["faint"],
                           font=self._font(("Segoe UI", 9)))

        self._bars = []
        base = self.spectrum.fundamental
        solo = self.spectrum.solo
        wobbling = self.spectrum.vibrato_cents > 0.0
        for item in self.spectrum.partials:
            exact = left + base * item.number * per_hz
            x = left + item.frequency(base) * per_hz
            self._bars.append((item.number, x))
            silent = item.muted or item.gain <= 0.0 or (
                solo and item.number != solo)
            chosen = item.number == self.selected

            # Dónde caería sin correr, cuando se lo corrió: el desvío se ve
            # como distancia y no como un número en otra parte de la
            # pantalla.
            if abs(item.shift) > 0.4:
                canvas.create_line(exact, floor_y, exact, floor_y - 7,
                                   fill=colours["muted"], dash=(2, 2))
                canvas.create_line(exact, floor_y - 4, x, floor_y - 4,
                                   fill=colours["gold_dim"])

            height = max(0.0, item.gain) * per_gain
            if silent:
                colour = colours["border"]
            elif solo == item.number:
                colour = colours["gold"]
            elif chosen:
                colour = colours["accent_hover"]
            else:
                colour = colours["accent"]
            if height > 1.0:
                if wobbling and not silent:
                    # Con vibrato, las barras se dibujan a rayas: la
                    # afinación está oscilando y una barra maciza es lo que
                    # se dibuja cuando está quieta. Es lo único que un
                    # dibujo detenido puede decir sobre algo que se mueve, y
                    # se lee como un fuelle --- que es bastante lo que hace
                    # un vibrato.
                    steps = max(2, int(height // 7))
                    for piece in range(steps):
                        y0 = floor_y - height * (piece + 0.45) / steps
                        y1 = floor_y - height * piece / steps
                        canvas.create_rectangle(x - BAR_WIDTH / 2, y0,
                                                x + BAR_WIDTH / 2, y1,
                                                fill=colour, outline="")
                else:
                    canvas.create_rectangle(x - BAR_WIDTH / 2, floor_y - height,
                                            x + BAR_WIDTH / 2, floor_y,
                                            fill=colour, outline="")
            else:
                # Apagado o en cero: queda el zócalo, que es lo que se
                # agarra para volver a subirlo.
                canvas.create_rectangle(x - BAR_WIDTH / 2, floor_y - 3,
                                        x + BAR_WIDTH / 2, floor_y,
                                        fill=colours["border"], outline="")
            if chosen:
                y = floor_y - max(height, 3.0)
                canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                   outline=colours["text"], width=1)
            canvas.create_text(x, floor_y + 7, text=tr(str(item.number)),
                               anchor="n",
                               fill=(colours["text"] if chosen
                                     else colours["muted"]),
                               font=self._font(("Segoe UI", 8)))

    # -- interacción con el gráfico -----------------------------------------

    def _nearest_bar(self, x: float) -> Optional[int]:
        best, distance = None, GRAB + 1.0
        for number, position in self._bars:
            gap = abs(position - x)
            if gap < distance:
                best, distance = number, gap
        return best

    def _on_press(self, event) -> None:
        number = self._nearest_bar(event.x)
        if number is None:
            return
        item = self.spectrum.partial(number)
        if item is None:
            return
        self.selected = number
        self._dragging = number
        self._drag_from = (float(event.x), float(event.y))
        self._drag_start = (item.gain, item.shift)
        # La escala del eje se congela mientras dura el arrastre. Subir una
        # barra sube el techo del gráfico, así que recalculándola en cada
        # movimiento el píxel valía distinto según cuánto se hubiera subido
        # y la mano perdía la cuenta de lo que estaba haciendo.
        self._drag_ceiling = max(1.0, harmonics.peak_gain(self.spectrum))
        self._axis = ""
        self._redraw()
        self._refresh_controls()

    def _on_drag(self, event) -> None:
        if self._dragging is None:
            return
        item = self.spectrum.partial(self._dragging)
        if item is None:
            return
        gain0, shift0 = self._drag_start
        across = event.x - self._drag_from[0]
        up = self._drag_from[1] - event.y
        if not self._axis:
            if max(abs(across), abs(up)) < AXIS_LOCK:
                return          # todavía no se movió lo suficiente
            self._axis = "x" if abs(across) > abs(up) else "y"
        if self._axis == "y":
            rise = up / DRAG_SPAN * self._drag_ceiling
            item.gain = max(0.0, min(harmonics.MAX_GAIN, gain0 + rise))
        else:
            run = across / SHIFT_SPAN
            item.shift = max(-harmonics.MAX_SHIFT_CENTS,
                             min(harmonics.MAX_SHIFT_CENTS,
                                 shift0 + run * harmonics.MAX_SHIFT_CENTS))
        # Subir una barra que estaba apagada es encenderla: dejarla muda
        # mientras crece sería pedirle al usuario que adivine por qué el
        # dibujo cambió y el sonido no.
        if item.gain > 0.0:
            item.muted = False
        self._redraw()
        self._refresh_controls()

    def _on_release(self, _event) -> None:
        self._dragging = None
        self._axis = ""

    def _on_double(self, event) -> None:
        """Dos clics aíslan un armónico, y dos más lo devuelven al conjunto."""
        number = self._nearest_bar(event.x)
        if number is None:
            return
        self.selected = number
        self.toggle_solo()

    # -- los botones --------------------------------------------------------

    def _chosen(self) -> Optional[harmonics.Partial]:
        return self.spectrum.partial(self.selected)

    def toggle_solo(self) -> None:
        self.spectrum.solo = (0 if self.spectrum.solo == self.selected
                              else self.selected)
        self._redraw()
        self._refresh_controls()

    def toggle_mute(self) -> None:
        item = self._chosen()
        if item is None:
            return
        item.muted = not item.muted
        self._redraw()
        self._refresh_controls()

    def recentre(self) -> None:
        """Devolver el armónico elegido a su múltiplo exacto."""
        item = self._chosen()
        if item is None:
            return
        item.shift = 0.0
        self._redraw()
        self._refresh_controls()

    def _chose_preset(self, name: str) -> None:
        # El desplegable devuelve el renglón que se ve; lo que se guarda y
        # con lo que se busca la receta es el nombre castellano.
        name = i18n.untr(name)
        self.preset_name = name
        harmonics.apply_preset(self.spectrum, name)
        self._redraw()
        self._refresh_controls()

    def _on_vibrato(self, value) -> None:
        was = self.spectrum.vibrato_cents > 0.0
        self.spectrum.vibrato_cents = float(value)
        # Sólo cuando cruza el cero: el dibujo cambia al prenderse y al
        # apagarse, y redibujar en cada píxel del deslizador es repintar
        # doce barras cincuenta veces por segundo para nada.
        if was != (self.spectrum.vibrato_cents > 0.0):
            self._redraw()

    def _on_tremolo(self, value) -> None:
        self.spectrum.tremolo_depth = float(value)

    def reset(self) -> None:
        midi = self.spectrum.midi
        self.spectrum = harmonics.build(self.preset_name, midi)
        self.selected = 1
        self.vibrato.set(0.0)
        self.tremolo.set(0.0)
        self._redraw()
        self._refresh_controls()
        self._draw_keys()

    # -- el teclado ---------------------------------------------------------

    def _draw_keys(self) -> None:
        canvas = self.keys
        try:
            canvas.delete("all")
        except tk.TclError:
            return
        colours = self.colours
        self._key_boxes: List[Tuple[int, float, float, float, float]] = []
        white = 0
        for midi in range(harmonics.LOWEST_MIDI, harmonics.HIGHEST_MIDI + 1):
            if midi % 12 not in WHITE_SEMITONES:
                continue
            x = white * KEY_WIDTH
            lit = midi == self.spectrum.midi
            canvas.create_rectangle(
                x, 0, x + KEY_WIDTH, KEY_HEIGHT,
                fill=colours["accent"] if lit else "#EFEFEF",
                outline=colours["panel"])
            self._key_boxes.append((midi, x, 0, x + KEY_WIDTH, KEY_HEIGHT))
            white += 1
        # Las negras después, para que queden encima.
        white = 0
        for midi in range(harmonics.LOWEST_MIDI, harmonics.HIGHEST_MIDI + 1):
            step = midi % 12
            if step in WHITE_SEMITONES:
                white += 1
                continue
            x = white * KEY_WIDTH - BLACK_WIDTH / 2
            lit = midi == self.spectrum.midi
            canvas.create_rectangle(
                x, 0, x + BLACK_WIDTH, BLACK_HEIGHT,
                fill=colours["accent"] if lit else "#1A1A1A",
                outline=colours["panel"])
            self._key_boxes.append((midi, x, 0, x + BLACK_WIDTH, BLACK_HEIGHT))

    def _on_key(self, event) -> None:
        # De atrás para adelante: las negras se dibujaron encima, así que
        # tienen que ganar cuando el clic cae sobre las dos.
        for midi, x0, y0, x1, y1 in reversed(self._key_boxes):
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.spectrum.midi = midi
                self._draw_keys()
                self._redraw()
                self._refresh_controls()
                self.play()
                return

    # -- lectura de lo elegido ----------------------------------------------

    def _refresh_controls(self) -> None:
        item = self._chosen()
        if item is None:
            return
        base = self.spectrum.fundamental
        frequency = item.frequency(base)
        midi, cents = harmonics.nearest_note(frequency)
        ratio = f"{item.number}:1" if item.number > 1 else "la fundamental"
        self.reading.configure(
            text=(trf("Armónico {number:>2}   {hz_label:>10}   ≈ "
                      "{note_label} {cents_label}   ·   {interval_label}",
                      number=item.number, hz_label=hz_label(frequency),
                      note_label=note_label(midi),
                      cents_label=cents_label(cents),
                      interval_label=interval_label(midi - self.spectrum.midi))))
        self.gloss.configure(text=tr(self._gloss_for(item, ratio, cents)))
        self.fundamental_label.configure(
            text=trf("Fundamental: {note_label} · {hz_label}",
                     note_label=note_label(self.spectrum.midi),
                     hz_label=hz_label(base)))

        chosen = self.colours["gold"]
        idle = self.colours["muted"]
        soloed = self.spectrum.solo == item.number
        self.solo_button.configure(
            text=tr("Aislado" if soloed else "Aislar"),
            text_color=chosen if soloed else idle,
            border_color=chosen if soloed else self.colours["border"])
        self.mute_button.configure(
            text=tr("Silenciado" if item.muted else "Silenciar"),
            text_color=chosen if item.muted else idle,
            border_color=chosen if item.muted else self.colours["border"])


    def _gloss_for(self, item: harmonics.Partial, ratio: str,
                   cents: float) -> str:
        """
        La frase que explica qué es este armónico.

        Es lo único de la pantalla que enseña algo sin que haya que ir al
        libro, así que dice la relación con la fundamental y ---cuando hay
        una--- la trampa: el séptimo y el undécimo no existen en el piano.
        """
        if abs(item.shift) > 0.4:
            return (trf("Corrido {cents_label} de su múltiplo exacto. Contra "
                        "los demás produce pulsaciones, porque dos "
                        "frecuencias casi iguales se suman y se restan por "
                        "turnos.",
                        cents_label=cents_label(item.shift)))
        meanings = {
            1: "La nota que creés estar oyendo. Casi nunca es la más fuerte.",
            2: "Una octava justa arriba. Duplicar la frecuencia es la única "
               "operación que el oído no escucha como otra nota.",
            3: "Una octava y una quinta. De acá sale la quinta, el intervalo "
               "sobre el que se apoya la armonía.",
            4: N("Dos octavas."),
            5: "Dos octavas y una tercera mayor. Cae catorce cents por debajo "
               "de la tercera del piano, y por eso un acorde afinado de oído "
               "no suena igual que uno afinado en un teclado.",
            6: "Dos octavas y una quinta.",
            7: "Una séptima que no está en ninguna escala, treinta y un cents "
               "más baja que la del piano. Es el sonido del blues, y un "
               "instrumento temperado no la puede tocar.",
            8: N("Tres octavas."),
            9: "Tres octavas y una segunda mayor, la novena de los acordes.",
            10: "Tres octavas y una tercera mayor.",
            11: "Queda justo entre la cuarta y el tritono. Las trompas "
                "naturales lo tenían, y sonaba desafinado a propósito.",
            12: "Tres octavas y una quinta.",
        }
        note = tr(meanings.get(item.number, ""))
        if self.spectrum.solo == item.number:
            note = tr("Aislado, es lo único que suena. ") + note
        return note

    # -- sonido -------------------------------------------------------------

    def _signature(self) -> tuple:
        """Con qué se compara si esto ya se escuchó."""
        return (self.spectrum.midi, self.spectrum.solo,
                round(self.spectrum.vibrato_cents, 1),
                round(self.spectrum.tremolo_depth, 2),
                tuple((p.number, round(p.gain, 3), round(p.shift, 1),
                       p.muted)
                      for p in self.spectrum.partials))

    def save_instrument(self) -> None:
        """
        Guardar el timbre como muestra de sampler.

        No es «exportar el sonido»: el archivo sale con la nota que
        representa y con el tramo que se repite anotados adentro, que es lo
        que hace que un sampler lo tome como el timbre de un instrumento y
        no como un ruido de dos segundos. Lo difícil ---que el empalme del
        bucle no se oiga--- lo resuelve :func:`harmonics.write_instrument`.
        """
        name = note_label(self.spectrum.midi).replace("♯", "s")
        path = filedialog.asksaveasfilename(
            title=tr("Guardar el timbre como muestra"),
            defaultextension=".wav",
            initialfile=trf("ChordWeaver {preset_name} {name}.wav",
                            preset_name=self.preset_name, name=name),
            filetypes=[(tr("Muestra de sampler"), "*.wav")])
        if not path:
            return
        self.save_button.configure(text=tr("Guardando…"), state="disabled")
        self.update_idletasks()
        try:
            start, end = harmonics.write_instrument(path, self.spectrum)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror(tr("No se pudo guardar"), str(exc))
            return
        finally:
            try:
                self.save_button.configure(text=tr("Guardar timbre…"),
                                           state="normal")
            except tk.TclError:
                pass
        seconds = (end - start + 1) / harmonics.SAMPLE_RATE
        told = trf("Se guardó {basename}.\n\n"
                   "El archivo indica que la muestra es un {name} y que el "
                   "bucle dura {seconds:.1f} s. Cualquier sampler que lea WAV "
                   "(TX16Wx, Kontakt, el AudioFileProcessor de LMMS, el "
                   "Simpler de Live o Polyphone para armar un SoundFont) lo "
                   "va a tocar afinado en todo el teclado y sostenido "
                   "mientras la tecla esté apretada.",
                   basename=os.path.basename(path), name=name,
                   seconds=seconds)
        if self.on_instrument is None:
            messagebox.showinfo(tr("Timbre guardado"), told)
            return
        # Y el sampler más a mano es este mismo programa: la misma muestra
        # puede tocar los resultados, la melodía y el analizador. Se
        # pregunta en el mismo cartel para no apilar dos.
        if messagebox.askyesno(
                tr("Timbre guardado"),
                told + "\n\n" + tr("¿Querés que el programa use este timbre "
                                   "para todo lo que toca? Lo podés cambiar "
                                   "cuando quieras desde el engranaje.")):
            self.on_instrument(path)

    def play(self) -> None:
        """Tocar lo que se está viendo."""
        if self._sound is not None and self._sound.is_alive():
            return          # de a uno, igual que el resto del programa
        try:
            self.play_button.configure(text=tr("♪  Sonando"), state="disabled")
        except tk.TclError:
            pass
        signature = self._signature()
        fresh = signature != self._last_heard
        self._last_heard = signature
        self._sound = harmonics.play(self.spectrum)
        self._watch_sound()
        if self.on_experiment is not None:
            self.on_experiment(fresh)

    def _watch_sound(self, period: int = 120) -> None:
        """
        Devolver el botón cuando el ruido termine, **preguntando desde Tk**.

        El hilo del sonido no puede agendar nada: `after` desde otro hilo lo
        rechaza tkinter con ``RuntimeError``, y con la llamada envuelta lo
        que pasaba era nada --- el botón se quedaba en «Sonando» para
        siempre. Es el mismo criterio con el que la aplicación espera a
        cualquiera de sus hilos.
        """
        try:
            if not self.winfo_exists():
                return
            if self._sound is not None and self._sound.is_alive():
                self.after(period, self._watch_sound)
                return
            self.play_button.configure(text=tr("▶  Escuchar"), state="normal")
        except tk.TclError:
            return
