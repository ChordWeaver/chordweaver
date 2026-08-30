# -*- coding: utf-8 -*-
"""
El analizador: una partitura entra, y sale dicha con todas las letras.

Los otros tres modos escriben música. Éste la lee: se le da una partitura
---escrita a mano en el sistema de dos pentagramas o traída de un archivo---
y contesta las dos preguntas con las que se estudia una obra ajena. Qué
acorde es cada momento y qué hace ese acorde en la tonalidad; y qué está
haciendo el contrapunto entre una vertical y la siguiente.

Todo el análisis vive en :mod:`engine.analysis`, que no sabe dibujar. Acá
sólo está lo que se ve: la barra de herramientas, el sistema, los tres
paneles de resultados y la reproducción.

Como :mod:`spectrum`, este módulo **no importa** ``app``: recibe la paleta y
el escalador de fuentes por parámetro. Lo que sí usa es
:class:`staff.GrandStaff`, que tampoco depende de la aplicación.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import customtkinter as ctk

from engine import analysis, audio, history, importer, session
from engine.i18n import tr, trf, trs
from engine import i18n
from staff import (DURATIONS, GRAND_VOICE_COUNT, GRAND_VOICES, LETTERS,
                   VOICE_COLOURS, GrandStaff, pitch_at)

#: Cómo se dice cada letra lo decide el idioma: en castellano una partitura
#: que contesta "F#4" no la lee nadie en voz alta, y en inglés la letra ya es
#: el nombre. La tabla está en `engine.i18n`, que es donde vive todo lo que
#: cambia con el idioma.

#: Cómo se nombra cada figura, por su duración en negras.
FIGURE_NAMES = {4.0: "redonda", 3.0: "blanca con puntillo", 2.0: "blanca",
                1.5: "negra con puntillo", 1.0: "negra",
                0.75: "corchea con puntillo", 0.5: "corchea",
                0.25: "semicorchea"}

#: Cómo se lee cada papel de una nota dentro de su acorde.
ROLE_NAMES = {"root": "la fundamental", "third": "la tercera",
              "fifth": "la quinta", "seventh": "la séptima"}

#: El color de cada gravedad de hallazgo. El grave usa el rojo de la
#: interfaz; el aviso, el dorado; la nota, el gris apagado.
SEVERITY_KEYS = {"grave": "warn", "aviso": "gold", "nota": "muted"}

#: Cuánto se espera antes de volver a analizar después de un cambio. Un
#: análisis cuesta milésimas, pero escribir una nota dispara varios eventos
#: seguidos y sin esta espera se analizaba tres veces por click.
REANALYSE_MS = 220

#: Tope de voces del editor. Cuatro es lo que entra en un sistema de dos
#: pentagramas sin que las plicas se pisen, y es además la textura para la
#: que sirve el análisis contrapuntístico.
MAX_VOICES = GRAND_VOICE_COUNT

#: El color con el que se dibuja cada clase de movimiento cuando se la
#: señala en el sistema. El contrario ---el que mantiene las voces
#: independientes--- va con el color que la interfaz usa para lo que está
#: bien; el paralelo, con el de lo que hay que mirar.
MOTION_COLOURS = {
    analysis.MOTION_CONTRARY: "#3F7D6E",
    analysis.MOTION_OBLIQUE: "#4A6FA5",
    analysis.MOTION_PARALLEL: "#C2554B",
    analysis.MOTION_SIMILAR: "#C08A2E",
    analysis.MOTION_STATIC: "#7A7264",
}

#: Qué es cada clase de movimiento, en una línea. Se lee al pasar el mouse
#: por encima, que es donde hace falta y donde no ocupa lugar.
MOTION_NOTES = {
    analysis.MOTION_CONTRARY:
        "las dos voces se mueven en direcciones opuestas: es lo que las "
        "mantiene independientes",
    analysis.MOTION_OBLIQUE:
        "una se queda quieta y la otra se mueve",
    analysis.MOTION_PARALLEL:
        "las dos en la misma dirección y con el intervalo del mismo tamaño: "
        "es lo que funde dos voces en una",
    analysis.MOTION_SIMILAR:
        "las dos en la misma dirección pero cambiando de intervalo; es por "
        "acá que se hacen las quintas ocultas",
    analysis.MOTION_STATIC:
        "ninguna de las dos se movió",
}

#: Cuántas voces escritas hacen falta para que el analizador conteste algo.
#: Tres, porque un acorde es una tríada: con una nota o con dos no hay nada
#: que nombrar, y ponerse a nombrarlo igual ---como hacía antes--- llenaba la
#: pantalla de acordes, grados y funciones deducidos de una sola nota.
MIN_VOICES = 3


def spanish_pitch(index: int, fifths: int, accidental=None) -> str:
    """Cómo se dice una posición del pentagrama, en el idioma en curso."""
    octave, position = divmod(index, 7)
    letter = LETTERS[position]
    name = i18n.say_letter(letter)
    written = pitch_at(index, fifths, accidental) - pitch_at(index, fifths, 0)
    if accidental is None:
        # Sin accidente propio manda la armadura.
        written = pitch_at(index, fifths) - pitch_at(index, fifths, 0)
    mark = {1: "♯", 2: "♯♯", -1: "♭", -2: "♭♭"}.get(written, "")
    return f"{name}{mark}{octave}"


class Analyzer(ctk.CTkFrame):
    """La pantalla entera del analizador."""

    def __init__(self, master, colours: Dict[str, str],
                 on_imported: Optional[Callable[[], None]] = None,
                 key_signatures: Sequence[Tuple[str, int]] = (),
                 on_played: Optional[Callable[[], None]] = None,
                 on_exported: Optional[Callable[[], None]] = None,
                 on_rest: Optional[Callable[[], None]] = None,
                 on_analysed: Optional[Callable[[object], None]] = None,
                 **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.colours = colours
        self.font = colours.get("font", lambda f: f)
        #: Se llama cuando se leyó una partitura de un archivo. Es lo
        #: único que la aplicación necesita saber de acá: haber traído
        #: música de afuera es un logro, y analizar lo que uno mismo escribió
        #: no lo es.
        self.on_imported = on_imported
        #: Los otros cuatro avisos son para el catálogo de logros. Acá se
        #: escucha, se exporta, se escriben silencios y se leen acordes
        #: igual que en los tres modos que componen, y un logro que premia
        #: haber hecho algo tiene que darse por hecho también acá: leer una
        #: séptima ajena es descubrir la séptima.
        self.on_played = on_played
        self.on_exported = on_exported
        self.on_rest = on_rest
        self.on_analysed = on_analysed
        self.key_signatures = list(key_signatures) or [("Do mayor / La menor", 0)]

        #: Lo que dice el renglón de lectura cuando no hay nada que leer.
        self._resting = ("Pasá el mouse por una nota y acá dice cuál es. "
                         "Click escribe, botón derecho borra; Tab cambia de "
                         "voz y Ctrl+Z deshace.")
        self.result = None
        self._pending = None
        self._playing = None
        self._pickup = 0.0
        self._rows: List[Tuple[ctk.CTkFrame, object]] = []
        self._selected = -1
        #: Los cambios de compás de la pieza: compás -> (tiempos, figura).
        self._metres: Dict[int, Tuple[int, int]] = {1: (4, 4)}
        #: Qué carril del pentagrama es cada voz del análisis. El análisis
        #: sólo ve las voces escritas y el pentagrama tiene siempre cuatro
        #: carriles, así que los números no coinciden en cuanto una voz
        #: queda vacía --- y sin esta tabla las flechas del contrapunto
        #: apuntarían a la voz de al lado.
        self._lanes: List[int] = list(range(GRAND_VOICE_COUNT))
        #: Qué clase de movimiento se está señalando, o None.
        self._motion_shown: Optional[str] = None

        self._build_toolbar()
        self._build_staff()
        self._build_panels()
        self._bind_keys()
        self._sync_staff()
        # La voz activa tiene que arrancar donde dice el menú. Sin esto el
        # menú decía "Soprano" y lo que se escribía iba al bajo, que es la
        # voz cero: escribir en un lugar y que aparezca en otro.
        self._voice_changed()

    # -- construcción -------------------------------------------------------

    def _build_toolbar(self) -> None:
        """
        Los mandos, repartidos por lo que hacen y no por dónde entran.

        A la izquierda lo que describe la partitura ---armadura, compás, qué
        voz se escribe--- y a la derecha lo que se hace con ella entera:
        escucharla, traerla, guardarla. Abajo, lo que se usa nota por nota.

        «Borrar todo» va solo, en la punta opuesta a «Deshacer» y con
        confirmación: estaban uno al lado del otro, del mismo tamaño y del
        mismo color, y el que borra la partitura entera no puede quedar a un
        píxel del que corrige la última nota.
        """
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 6))

        self._label(bar, "Armadura").pack(side="left", padx=(0, 6))
        self.key_menu = self._menu(
            bar, [name for name, _f in self.key_signatures], 168,
            lambda _v: self._sync_staff())
        self.key_menu.set(tr(self.key_signatures[0][0]))
        self.key_menu.pack(side="left")

        self._label(bar, "Compás").pack(side="left", padx=(12, 6))
        self.metre_menu = self._menu(bar, ["4/4", "3/4", "2/4", "6/8", "3/8",
                                           "5/4", "2/2"],
                                     72, lambda _v: self._metre_changed())
        self.metre_menu.set("4/4")
        self.metre_menu.pack(side="left")
        # Un compás rige **desde** un compás y hasta el próximo cambio. Sin
        # esto la partitura entera iba forzada a uno solo, que es lo que
        # ninguna pieza de más de una página hace.
        self._label(bar, "desde el c.").pack(side="left", padx=(6, 4))
        self.metre_from = ctk.CTkEntry(
            bar, width=44, height=30, font=self.font(("Segoe UI", 12)),
            fg_color=self.colours["surface"], border_width=0, justify="center")
        self.metre_from.insert(0, "1")
        self.metre_from.pack(side="left")
        self.metre_from.bind("<Return>", lambda _e: self._metre_changed())
        # Y un compás **solo**. Un cambio de compás rige hasta el próximo,
        # que es como se escribe una obra que cambia de compás y se queda
        # ahí; pero un compás suelto de 2/4 en el medio de una pieza en 4/4
        # es igual de común, y con la marca puesta el compás siguiente
        # vuelve al que regía.
        self.only_one = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            bar, text=tr("sólo ese"), variable=self.only_one, width=20,
            checkbox_width=17, checkbox_height=17,
            font=self.font(("Segoe UI", 11)),
            fg_color=self.colours["accent"],
            hover_color=self.colours["accent_hover"],
            command=self._metre_changed).pack(side="left", padx=(8, 0))
        self.metre_list = self._label(bar, "")
        self.metre_list.pack(side="left", padx=(8, 0))

        self._label(bar, "Escribo la").pack(side="left", padx=(14, 6))
        self.voice_menu = self._menu(bar, list(GRAND_VOICES), 112,
                                     lambda _v: self._voice_changed())
        self.voice_menu.set(tr(GRAND_VOICES[0]))
        self.voice_menu.pack(side="left")

        for text, command in (("Exportar…", self._export),
                              ("Importar…", self._import)):
            ctk.CTkButton(
                bar, text=tr(text), width=104, height=30,
                font=self.font(("Segoe UI", 12)), fg_color="transparent",
                border_width=1, border_color=self.colours["muted"],
                hover_color=self.colours["panel"], command=command
            ).pack(side="right", padx=(6, 0))

        self.play_button = ctk.CTkButton(
            bar, text=tr("▶  Escuchar"), width=124, height=30,
            font=self.font(("Segoe UI", 12)), fg_color=self.colours["accent"],
            hover_color=self.colours["accent_hover"], command=self._play)
        self.play_button.pack(side="right", padx=(6, 0))

        # -- segunda fila: figuras y accidentes -----------------------------
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", pady=(0, 6))
        self.duration_var = tk.StringVar(value="Negra")
        for label, value in DURATIONS:
            ctk.CTkRadioButton(
                tools, text=tr(label), variable=self.duration_var, value=label,
                font=self.font(("Segoe UI", 11)),
                fg_color=self.colours["accent"],
                hover_color=self.colours["accent_hover"],
                command=lambda v=value: setattr(self.staff, "duration", v)
            ).pack(side="left", padx=(0, 5))

        self._label(tools, "Accidente").pack(side="left", padx=(14, 6))
        #: Los accidentes que no están en la armadura. Se eligen antes de
        #: escribir la nota y valen para esa nota sola: es como se escribe
        #: en el papel, donde una alteración accidental dura lo que dura el
        #: compás y no se hereda a la siguiente pieza.
        self.accidental_buttons: Dict[Optional[int], ctk.CTkButton] = {}
        for value, glyph in ((1, "♯"), (-1, "♭"), (0, "♮"), (None, "—")):
            button = ctk.CTkButton(
                tools, text=glyph, width=36, height=28,
                font=self.font(("Segoe UI Symbol", 15)),
                fg_color="transparent", border_width=1,
                border_color=self.colours["muted"],
                hover_color=self.colours["panel"],
                command=lambda v=value: self._set_accidental(v))
            button.pack(side="left", padx=2)
            self.accidental_buttons[value] = button

        self.rest_button = ctk.CTkButton(
            tools, text=tr("Silencio"), width=88, height=28,
            font=self.font(("Segoe UI", 11)), fg_color="transparent",
            border_width=1, border_color=self.colours["muted"],
            hover_color=self.colours["panel"], command=self._toggle_rests)
        self.rest_button.pack(side="left", padx=(14, 0))

        ctk.CTkButton(
            tools, text=tr("↶  Deshacer"), width=104, height=28,
            font=self.font(("Segoe UI", 11)), fg_color="transparent",
            border_width=1, border_color=self.colours["muted"],
            hover_color=self.colours["panel"], command=self._undo
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            tools, text=tr("Borrar todo"), width=98, height=28,
            font=self.font(("Segoe UI", 11)), fg_color="transparent",
            border_width=1, border_color=self.colours["warn"],
            text_color=self.colours["warn"],
            hover_color=self.colours["panel"], command=self._clear
        ).pack(side="right")

    def _bind_keys(self) -> None:
        """
        Los dos atajos que ahorran ir al mouse.

        Van sobre el lienzo del pentagrama y no sobre toda la ventana: el
        analizador es una pantalla más del programa y apoderarse del tabulador
        y del control-zeta en todas las demás sería robarles el suyo. El
        lienzo toma el foco al pasarle el mouse por encima, que es donde uno
        está mientras escribe.
        """
        canvas = self.staff.canvas
        canvas.configure(takefocus=True)
        canvas.bind("<Enter>", lambda _e: canvas.focus_set())
        canvas.bind("<Tab>", self._next_voice)
        canvas.bind("<Shift-Tab>", lambda e: self._next_voice(e, step=-1))
        canvas.bind("<Control-z>", self._undo_event)
        canvas.bind("<Control-Z>", self._undo_event)

    def _next_voice(self, _event=None, step: int = 1) -> str:
        """Pasar a la voz siguiente. Devuelve "break": el tabulador es nuestro."""
        try:
            visible = GRAND_VOICES.index(i18n.untr(self.voice_menu.get()))
        except ValueError:
            visible = 0
        self.voice_menu.set(GRAND_VOICES[(visible + step) % len(GRAND_VOICES)])
        self._voice_changed()
        return "break"

    def _undo_event(self, _event=None) -> str:
        self._undo()
        return "break"

    def _label(self, master, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(master, text=tr(text), font=self.font(("Segoe UI", 11)),
                            text_color=self.colours["muted"])

    def _menu(self, master, values, width, command) -> ctk.CTkOptionMenu:
        return ctk.CTkOptionMenu(
            master, values=trs(values), width=width, height=30,
            font=self.font(("Segoe UI", 12)),
            fg_color=self.colours["surface"], button_color=self.colours["surface"],
            button_hover_color=self.colours["accent_hover"], command=command)

    def _build_staff(self) -> None:
        self.staff = GrandStaff(
            self, colours={"surface": self.colours["surface"],
                           "text": self.colours["text"],
                           "muted": self.colours["muted"],
                           "accent": self.colours["accent"],
                           "glow": self.colours.get("glow",
                                                    self.colours["surface"])},
            on_change=self._schedule, on_pick=self._picked,
            on_hover=self._hovered)
        self.staff.on_rest = self._wrote_rest
        self.staff.pack(fill="x", pady=(0, 4))

        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", pady=(0, 6))
        #: El renglón que contesta "¿qué nota es ésta?". Es lo único que
        #: hace falta para leer una partitura ajena sin contar líneas.
        self.picked = ctk.CTkLabel(
            strip, text=tr(self._resting),
            font=self.font(("Segoe UI", 12)), text_color=self.colours["muted"],
            anchor="w", justify="left", wraplength=980)
        self.picked.pack(side="left")
        legend = ctk.CTkFrame(strip, fg_color="transparent")
        legend.pack(side="right")
        for position, name in enumerate(GRAND_VOICES):
            ctk.CTkLabel(legend, text="●", text_color=VOICE_COLOURS[position],
                         font=self.font(("Segoe UI", 13))).pack(side="left")
            ctk.CTkLabel(legend, text=tr(name),
                         font=self.font(("Segoe UI", 11)),
                         text_color=self.colours["muted"]
                         ).pack(side="left", padx=(2, 10))

    def _build_summary(self) -> None:
        """
        La franja de la tonalidad, encima de los tres paneles.

        Va aparte y no dentro del panel de armonía porque es la respuesta a
        otra pregunta. La tonalidad y las cadencias son de la pieza entera;
        la lista de acordes es de cada momento. Mezcladas en la misma
        columna, lo de la pieza entera se comía media columna y la lista de
        acordes ---que es lo que se viene a mirar--- quedaba en un rincón.
        """
        self.summary = ctk.CTkFrame(self, fg_color=self.colours["panel"],
                                    corner_radius=12)
        self.summary.pack(fill="x", pady=(0, 8))

    def _fill_summary(self) -> None:
        """
        La tonalidad y los puntos de reposo, en un solo renglón.

        Un renglón y no los que hagan falta: los motivos de la lectura son
        frases enteras y puestos tal cual la franja crecía hasta comerse los
        paneles de abajo, que es lo que se viene a leer. Acá va lo corto y
        el motivo completo se lee al pasar el mouse, en el renglón que ya
        existe para eso.
        """
        self._wipe(self.summary)
        row = ctk.CTkFrame(self.summary, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)
        if self.result is None:
            written = self.written_voices()
            ctk.CTkLabel(
                row,
                text=(trf("{written} de {MIN_VOICES} voces escritas",
                          written=written, MIN_VOICES=MIN_VOICES)
                      if written else tr("Sin partitura todavía")),
                font=self.font(("Segoe UI Semibold", 16)),
                text_color=self.colours["muted"]).pack(side="left")
            return

        key = self.result.key
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        confidence = ("lectura clara" if key.confidence >= 0.6
                      else "lectura probable" if key.confidence >= 0.3
                      else "lectura dudosa")
        title = ctk.CTkLabel(left, text=tr(key.label),
                             font=self.font(("Segoe UI Semibold", 18)),
                             anchor="w")
        title.pack(side="left")
        why = ctk.CTkLabel(left, text=tr(confidence),
                           font=self.font(("Segoe UI", 11)),
                           text_color=self.colours["muted"], anchor="w")
        why.pack(side="left", padx=(8, 0))
        reasons = "; ".join(key.reasons[:3]) or "no hay mucho en qué apoyarse"
        for widget in (title, why):
            self._hover(widget, f"{key.label}: {reasons}.")

        # Sólo si hay algo que poner adentro. Un `CTkFrame` vacío mide
        # doscientos píxeles de alto por omisión, y en una pieza sin
        # cadencias ni acordes ajenos ---un modo puro, por ejemplo--- esta
        # franja de un renglón pasaba a medir cuatro veces lo que mide y se
        # comía los tres paneles de abajo.
        if not (self.result.cadences or self.result.groups
                or self.result.warnings):
            return
        chips = ctk.CTkFrame(row, fg_color="transparent")
        chips.pack(side="left", padx=(20, 0))
        for cadence in self.result.cadences:
            self._chip(chips, f"c. {cadence.bar_index}  ·  {cadence.kind}",
                       self.colours["gold"], cadence.detail,
                       command=lambda c=cadence: self._show_span(c.start,
                                                                 c.index))
        for group in self.result.groups:
            self._chip(chips, group.label, self.colours["accent"],
                       group.detail,
                       command=lambda g=group: self._show_span(g.start, g.end))
        for warning in self.result.warnings:
            # Recortado: el aviso entero mide tres renglones y la franja es
            # de una línea. Completo se lee al pasarle el mouse por encima.
            short = warning if len(warning) <= 42 else warning[:40] + "…"
            self._chip(chips, short, self.colours["muted"], warning)

    def _hover(self, widget, text: str) -> None:
        """Lo que dice el renglón de lectura mientras el mouse esté encima."""
        widget.bind("<Enter>", lambda _e: self.picked.configure(
            text=tr(text), text_color=self.colours["muted"]))

    def _show_span(self, first: int, last: int) -> None:
        """Resaltar en el sistema el tramo que va de un segmento a otro."""
        segments = self.result.segments if self.result is not None else []
        if not segments:
            return
        first = max(0, min(first, len(segments) - 1))
        last = max(first, min(last, len(segments) - 1))
        self.staff.highlight = (segments[first].start, segments[last].end)
        self.staff.redraw()

    def _chip(self, master, text: str, colour: str, tip: str,
              command=None) -> None:
        """Un rótulo con borde. El detalle se lee al pasar el mouse.

        Si lleva acción, tocarlo señala en el sistema dónde ocurre lo que
        dice: una cadencia nombrada sin decir dónde cae obliga a buscarla a
        mano, que es lo contrario de lo que un análisis tiene que ahorrar.
        """
        chip = ctk.CTkFrame(master, fg_color="transparent", corner_radius=9,
                            border_width=1, border_color=colour,
                            cursor="hand2" if command else "")
        chip.pack(side="left", padx=(0, 6), pady=2)
        label = ctk.CTkLabel(chip, text=tr(text), font=self.font(("Segoe UI", 11)),
                             text_color=colour)
        label.pack(padx=9, pady=3)
        for widget in (chip, label):
            if tip:
                self._hover(widget, tip)
            if command is not None:
                widget.bind("<Button-1>", lambda _e: command())

    def _build_panels(self) -> None:
        self._build_summary()
        panels = ctk.CTkFrame(self, fg_color="transparent")
        panels.pack(fill="both", expand=True)
        panels.grid_columnconfigure(0, weight=5, uniform="paneles")
        panels.grid_columnconfigure(1, weight=4, uniform="paneles")
        panels.grid_columnconfigure(2, weight=3, uniform="paneles")
        panels.grid_rowconfigure(0, weight=1)

        self.harmony_panel = self._panel(panels, 0, "Acordes, uno por uno")
        self.counterpoint_panel = self._panel(panels, 1, "Contrapunto")
        self.ornament_panel = self._panel(panels, 2, "Adornos melódicos")

    def _panel(self, master, column: int, title: str):
        holder = ctk.CTkFrame(master, fg_color=self.colours["panel"],
                              corner_radius=12)
        holder.grid(row=0, column=column, sticky="nsew",
                    padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
        ctk.CTkLabel(holder, text=tr(title),
                     font=self.font(("Segoe UI Semibold", 14)),
                     anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        body = ctk.CTkScrollableFrame(holder, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        return body

    # -- estado -------------------------------------------------------------

    def _fifths(self) -> int:
        label = i18n.untr(self.key_menu.get())
        return next((f for name, f in self.key_signatures if name == label), 0)

    def _sync_staff(self) -> None:
        first = self._metres.get(1, (4, 4))
        self.staff.set_key(self._fifths(), first[0], first[1])
        self._apply_metres()

    def metres(self) -> Tuple[Tuple[int, int, int], ...]:
        """Los cambios de compás, ordenados y listos para el motor."""
        return tuple(sorted((bar, beats, beat_type)
                            for bar, (beats, beat_type) in self._metres.items()))

    def _apply_metres(self) -> None:
        self.staff.set_metres(self.metres())
        changes = self.metres()
        self.metre_list.configure(
            text=tr("" if len(changes) <= 1 else
               " · ".join(trf("{b}/{t} desde el c.{bar}", b=b, t=t, bar=bar) for bar, b, t in changes[1:])))
        self._schedule()

    def _metre_changed(self) -> None:
        """
        Fijar un compás desde un compás dado.

        Poner en un compás el mismo que ya regía lo saca de la lista, que es
        la única manera razonable de deshacer un cambio sin inventar otro
        botón: el usuario pide lo que quiere que suene y la lista se ordena
        sola.
        """
        try:
            beats, beat_type = (int(x) for x in self.metre_menu.get().split("/"))
        except ValueError:
            return
        try:
            bar = max(1, int(self.metre_from.get().strip() or "1"))
        except ValueError:
            bar = 1
        self.metre_from.delete(0, "end")
        self.metre_from.insert(0, str(bar))
        ruling = self._ruling_before(bar)
        if bar > 1 and (beats, beat_type) == ruling:
            self._metres.pop(bar, None)
            self._metres.pop(bar + 1, None)
        else:
            self._metres[bar] = (beats, beat_type)
            # Un compás solo: el que sigue vuelve al que regía. Sin esto,
            # pedir un 2/4 en el medio se llevaba puesta toda la segunda
            # mitad de la pieza.
            if self.only_one.get():
                self._metres[bar + 1] = ruling
            elif self._metres.get(bar + 1) == ruling:
                self._metres.pop(bar + 1, None)
        first = self._metres.get(1, (4, 4))
        self.staff.set_key(self._fifths(), first[0], first[1])
        self._apply_metres()

    def _ruling_before(self, bar: int) -> Tuple[int, int]:
        """Qué compás regiría en ese compás si no hubiera un cambio ahí."""
        current = self._metres.get(1, (4, 4))
        for at in sorted(self._metres):
            if 1 < at < bar:
                current = self._metres[at]
        return current

    def _voice_changed(self) -> None:
        """La voz elegida se cuenta de aguda a grave; adentro, al revés."""
        name = i18n.untr(self.voice_menu.get())
        try:
            visible = GRAND_VOICES.index(name)
        except ValueError:
            visible = 0
        self.staff.active = max(0, GRAND_VOICE_COUNT - 1 - visible)
        self.staff.redraw()

    def _set_accidental(self, value) -> None:
        self.staff.pending = value
        for key, button in self.accidental_buttons.items():
            chosen = key == value
            button.configure(
                fg_color=self.colours["accent"] if chosen else "transparent",
                border_color=(self.colours["accent"] if chosen
                              else self.colours["muted"]))

    def _toggle_rests(self) -> None:
        """Prender o apagar la escritura de silencios.

        Es un modo y no otro botón porque el silencio se escribe donde
        se escribiría la nota: con esto encendido, cada click pone un
        silencio de la figura elegida en la voz elegida.
        """
        self.staff.writing_rests = not self.staff.writing_rests
        on = self.staff.writing_rests
        self.rest_button.configure(
            fg_color=self.colours["accent"] if on else "transparent",
            border_color=(self.colours["accent"] if on
                          else self.colours["muted"]))

    def _wrote_rest(self) -> None:
        if self.on_rest is not None:
            self.on_rest()

    def _undo(self) -> None:
        self.staff.undo()

    def _clear(self) -> None:
        if not self.staff.is_empty() and not messagebox.askyesno(
                tr("Borrar todo"),
                tr("Esto saca del pentagrama todo lo que hay escrito. "
                   "¿Seguimos?")):
            return
        self._pickup = 0.0
        self.staff.clear()

    # -- análisis -----------------------------------------------------------

    def _schedule(self) -> None:
        """Volver a analizar, pero no en cada tecla."""
        if self._pending is not None:
            try:
                self.after_cancel(self._pending)
            except (tk.TclError, ValueError):
                pass
        self._pending = self.after(REANALYSE_MS, self._analyse)

    def score(self):
        """
        La partitura escrita, tal como la lee el motor.

        Sólo las voces que tienen algo escrito. El pentagrama lleva siempre
        cuatro carriles porque las claves reparten cuatro voces, pero una
        pieza a tres voces son tres voces: pasarle al análisis un carril
        vacío le da una voz que calla toda la pieza, y con ella un
        contrapunto medido contra el silencio.
        """
        lines = self.staff.lines()
        ladder = list(reversed(GRAND_VOICES))
        self._lanes = []
        parts = []
        for lane, line in enumerate(lines):
            if not any(pitch is not None for pitch, _d in line):
                continue
            notes, position = [], 0.0
            for pitch, duration in line:
                # El silencio no entra como nota: ocupa tiempo y nada más.
                # Es lo que hace que una voz que entra tarde entre tarde.
                if pitch is not None:
                    notes.append(analysis.Note(pitch=pitch, onset=position,
                                               duration=duration))
                position += duration
            parts.append(analysis.Part(name=ladder[lane], notes=notes))
            self._lanes.append(lane)
        first = self._metres.get(1, (4, 4))
        return analysis.Score(parts=parts, fifths=self._fifths(),
                              beats=first[0], beat_type=first[1],
                              title="Análisis", pickup_quarters=self._pickup,
                              metres=self.metres())

    def written_voices(self) -> int:
        """Cuántas voces tienen al menos una nota escrita."""
        return len(self.staff.written_voices())

    def _lane_of(self, voice: int) -> int:
        """El carril del pentagrama que corresponde a una voz del análisis."""
        if 0 <= voice < len(self._lanes):
            return self._lanes[voice]
        return min(voice, GRAND_VOICE_COUNT - 1)

    def _voice_of(self, lane: int) -> int:
        """La voz del análisis que corresponde a un carril, o -1."""
        return self._lanes.index(lane) if lane in self._lanes else -1

    def _analyse(self) -> None:
        self._pending = None
        if self.written_voices() < MIN_VOICES:
            self.result = None
            self.staff.annotations = []
            self.staff.flags = []
            self.staff.highlight = None
            self.staff.motions = []
            self._motion_shown = None
            self.staff.redraw()
            self._render_empty()
            return
        self.result = analysis.analyse(self.score())
        if self.on_analysed is not None:
            self.on_analysed(self.result)
        # `score()` dejó la correspondencia en orden de carril, pero el
        # análisis reordena las voces por registro --- un tenor escrito por
        # encima del alto cambia el orden ---, así que se rehace por nombre.
        # Con la vieja, las marcas del contrapunto señalaban la voz de al
        # lado, que es lo mismo que señalar cualquiera.
        ladder = list(reversed(GRAND_VOICES))
        self._lanes = [ladder.index(part.name) if part.name in ladder
                       else position
                       for position, part in enumerate(self.result.score.parts)]
        # Lo que estaba elegido puede no existir en el análisis nuevo, y su
        # resaltado señalaría un tramo de una partitura que ya cambió.
        self._selected = -1
        self.staff.highlight = None
        self.staff.motions = []
        self._motion_shown = None
        self._annotate()
        self._render()

    def _annotate(self) -> None:
        """
        Escribir el cifrado sobre el propio sistema.

        Arriba el cifrado americano y abajo el del bajo continuo, en
        columna. El grado con números romanos ya no va acá: escrito al lado
        del cifrado sumaba un rótulo largo debajo de cada acorde y no había
        forma de leer ninguno de los dos. Está en la lista de acordes, que
        es donde hay ancho.
        """
        result = self.result
        annotations = []
        for segment in result.segments:
            rows = segment.figure.split("/") if segment.figure else []
            annotations.append((segment.start, segment.symbol, rows))
        self.staff.annotations = annotations
        self.staff.flags = [
            (result.sonorities[finding.index].onset,
             self.colours.get(SEVERITY_KEYS.get(finding.severity, "muted"),
                              self.colours["muted"]))
            for finding in result.findings
            if finding.severity == "grave"
            and finding.index < len(result.sonorities)]
        self.staff.redraw()

    # -- pintar los paneles -------------------------------------------------

    @staticmethod
    def _wipe(panel) -> None:
        for child in panel.winfo_children():
            child.destroy()

    def _render_empty(self) -> None:
        self._fill_summary()
        written = self.written_voices()
        missing = MIN_VOICES - written
        if written:
            # Las dos formas enteras: «falta/faltan» y «voz/voces» son
            # concordancias del castellano, y una terminación suelta no se
            # puede traducir.
            first = (trf("Falta {missing} voz: un acorde son tres notas "
                         "sonando, así que hasta que no haya tres voces "
                         "escritas no hay nada que nombrar.", missing=missing)
                     if missing == 1 else
                     trf("Faltan {missing} voces: un acorde son tres notas "
                         "sonando, así que hasta que no haya tres voces "
                         "escritas no hay nada que nombrar.", missing=missing))
        else:
            first = ("Escribí las voces en el sistema o importá una "
                     "partitura. Con tres voces escritas aparece acá la "
                     "tonalidad, los acordes y lo que hace cada uno.\n\n"
                     "Si no tenés ninguna a mano, «Importar…» abre en la "
                     "carpeta de ejemplos: ahí está el Preludio en Do mayor "
                     "de Bach.")
        for panel, text in (
                (self.harmony_panel, first),
                (self.counterpoint_panel,
                 "Acá van los movimientos entre voces y lo que convenga "
                 "mirar: paralelas, saltos difíciles, cruces."),
                (self.ornament_panel,
                 "Y acá, los adornos melódicos: las notas que no pertenecen "
                 "al acorde, con el nombre que les corresponde.")):
            self._wipe(panel)
            ctk.CTkLabel(panel, text=tr(text), font=self.font(("Segoe UI", 12)),
                         text_color=self.colours["muted"], wraplength=250,
                         justify="left", anchor="w").pack(fill="x", padx=10,
                                                          pady=8)

    def _render(self) -> None:
        self._fill_summary()
        self._render_harmony()
        self._render_counterpoint()
        self._render_ornaments()

    def _note(self, panel, text: str, colour: Optional[str] = None,
              size: int = 12, pad: Tuple[int, int] = (2, 2),
              bold: bool = False) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            panel, text=tr(text),
            font=self.font((f"Segoe UI{' Semibold' if bold else ''}", size)),
            text_color=colour or self.colours["text"], wraplength=250,
            justify="left", anchor="w")
        label.pack(fill="x", padx=10, pady=pad)
        return label

    def _render_harmony(self) -> None:
        panel = self.harmony_panel
        self._wipe(panel)
        self._rows = []
        self._note(panel, "Tocá uno para ver dónde cae en la partitura.",
                   self.colours["faint"], 10, (2, 6))
        for index, segment in enumerate(self.result.segments):
            self._rows.append(
                (self._chord_row(panel, index, segment), segment))

    def _chord_row(self, panel, index: int, segment) -> ctk.CTkFrame:
        row = ctk.CTkFrame(panel, fg_color="transparent", corner_radius=8)
        row.pack(fill="x", padx=6, pady=1)

        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x", padx=6, pady=(4, 0))
        ctk.CTkLabel(head, text=trf("c.{bar}", bar=segment.bar_index),
                     font=self.font(("Segoe UI", 10)),
                     text_color=self.colours["muted"], width=34, anchor="w"
                     ).pack(side="left")
        ctk.CTkLabel(head, text=segment.symbol,
                     font=self.font(("Segoe UI Semibold", 14)), anchor="w"
                     ).pack(side="left")
        # El grado va **sin** la cifra de inversión pegada, y la cifra del
        # bajo continuo al lado, en dorado y separada. Los dos son números:
        # escritos uno contra otro, "V4/2" al lado de "4/2" no se leía como
        # un grado y un cifrado sino como un cifrado imposible de cuatro
        # números con una V colgando adelante.
        ctk.CTkLabel(head, text=segment.numeral or segment.roman,
                     font=self.font(("Segoe UI", 13)),
                     text_color=self.colours["accent"], anchor="w"
                     ).pack(side="left", padx=(10, 0))
        if segment.figure:
            ctk.CTkLabel(head, text="·", font=self.font(("Segoe UI", 12)),
                         text_color=self.colours["faint"], anchor="w"
                         ).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(head, text=tr(segment.figure),
                         font=self.font(("Consolas", 13)),
                         text_color=self.colours["gold"], anchor="w"
                         ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(head,
                     text=tr(analysis.FUNCTION_LABELS.get(segment.function, "")),
                     font=self.font(("Segoe UI", 11)),
                     text_color=self.colours["muted"], anchor="e"
                     ).pack(side="right")

        # Cada pedazo se traduce por separado y se pegan después: el
        # renglón armado lleva el cifrado adentro, así que como clave no
        # existiría nunca.
        detail = tr(segment.detail)
        if segment.sus_note:
            detail = tr(segment.sus_note) + (". " + detail if detail else "")
        if segment.alternative is not None:
            detail = (trf("También se puede leer {symbol}. ",
                          symbol=segment.alternative.symbol)
                      + detail)
        if detail:
            ctk.CTkLabel(row, text=detail, font=self.font(("Segoe UI", 11)),
                         text_color=self.colours["muted"], wraplength=250,
                         justify="left", anchor="w"
                         ).pack(fill="x", padx=(46, 6), pady=(0, 4))
        # Cómo se encadena con el siguiente sale sólo en el acorde elegido.
        # Es un renglón por acorde y con veinte acordes la lista pasaba a
        # medir el doble, que es justo lo que hay que poder recorrer de un
        # vistazo.
        if segment.relation and index == self._selected:
            ctk.CTkLabel(row, text=tr("↓  " + segment.relation),
                         font=self.font(("Segoe UI", 10)),
                         text_color=self.colours["faint"], anchor="w"
                         ).pack(fill="x", padx=(46, 6), pady=(0, 4))

        for widget in [row] + _descendants(row):
            widget.bind("<Button-1>", lambda _e, i=index: self._select(i))
        return row

    def _select(self, index: int) -> None:
        """Resaltar en el sistema el acorde que se tocó en la lista."""
        if self.result is None or not 0 <= index < len(self.result.segments):
            return
        self._selected = index
        segment = self.result.segments[index]
        self.staff.highlight = (segment.start, segment.end)
        self.staff.redraw()
        # La lista se rearma porque el acorde elegido muestra un renglón más
        # que los otros. Cuesta lo que cuesta armar unas decenas de etiquetas
        # y evita tener que mantener dos caminos de pintado.
        self._render_harmony()
        for position, (row, _segment) in enumerate(self._rows):
            try:
                row.configure(fg_color=self.colours["surface"]
                              if position == index else "transparent")
            except tk.TclError:
                pass

    def _render_counterpoint(self) -> None:
        panel = self.counterpoint_panel
        self._wipe(panel)
        result = self.result

        summary = result.motion_summary()
        total = sum(summary.values()) or 1
        self._note(panel, "Movimiento entre voces", self.colours["muted"], 11,
                   (4, 2), bold=True)
        self._note(panel,
                   "Tocá uno y se marcan sobre el sistema: un trazo une "
                   "las dos voces del par y una flecha dice adónde va cada "
                   "una.",
                   self.colours["faint"], 10, (0, 4))
        self._motion_rows = {}
        for kind in (analysis.MOTION_CONTRARY, analysis.MOTION_OBLIQUE,
                     analysis.MOTION_PARALLEL, analysis.MOTION_SIMILAR,
                     analysis.MOTION_STATIC):
            count = summary.get(kind, 0)
            if not count:
                continue
            self._motion_rows[kind] = self._bar(panel, kind, count,
                                                count / total)

        graves = [f for f in result.findings if f.severity == "grave"]
        self._note(panel,
                   trf("{findings} cosa(s) para mirar",
                       findings=len(result.findings))
                   + (trf(", {graves} grave(s)", graves=len(graves)) if graves else ""),
                   self.colours["muted"], 11, (10, 4), bold=True)
        if not result.findings:
            self._note(panel, "Ni paralelas, ni cruces, ni saltos difíciles: "
                              "el contrapunto está limpio.",
                       self.colours["muted"], 11, (0, 6))
        for finding in result.findings:
            self._finding_row(panel, finding)

    def _bar(self, panel, label: str, count: int, share: float):
        """Un renglón de movimiento: nombre, barra, cuenta --- y se toca."""
        colour = MOTION_COLOURS.get(label, self.colours["accent"])
        row = ctk.CTkFrame(panel, fg_color="transparent", corner_radius=7,
                           cursor="hand2")
        row.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row, text=tr(label.capitalize()),
                     font=self.font(("Segoe UI", 11)), width=72, anchor="w"
                     ).pack(side="left", padx=(4, 0))
        track = tk.Canvas(row, height=10, highlightthickness=0, bd=0,
                          bg=self.colours["panel"])
        track.pack(side="left", fill="x", expand=True, padx=(2, 6))
        ctk.CTkLabel(row, text=tr(str(count)), font=self.font(("Segoe UI", 11)),
                     text_color=self.colours["muted"], width=30, anchor="e"
                     ).pack(side="right", padx=(0, 4))

        def paint(_event=None) -> None:
            track.delete("all")
            width = max(1, track.winfo_width())
            track.create_rectangle(0, 2, width, 9, outline="",
                                   fill=self.colours["surface"])
            track.create_rectangle(0, 2, max(2, width * share), 9, outline="",
                                   fill=colour)

        track.bind("<Configure>", paint)
        for widget in [row, track] + _descendants(row):
            widget.bind("<Button-1>", lambda _e, k=label: self._show_motion(k))
            self._hover(widget, f"{label.capitalize()}: "
                                f"{MOTION_NOTES.get(label, '')}")
        return row

    def _show_motion(self, kind: str) -> None:
        """
        Dibujar sobre el sistema todos los movimientos de una clase.

        Un trazo por **par de voces**, que es de lo que habla la palabra
        movimiento: une las dos notas y le pone a cada una una flecha con su
        dirección. La lista de antes decía cuántos había y no dónde estaban,
        que es justamente lo único que hace falta para mirarlos.
        """
        if self.result is None:
            return
        if self._motion_shown == kind:
            self._motion_shown = None
            self.staff.motions = []
            self._paint_motion_rows()
            self.staff.redraw()
            return
        self._motion_shown = kind
        colour = MOTION_COLOURS.get(kind, self.colours["accent"])
        sonorities = self.result.sonorities
        marks = []
        for report in self.result.motions:
            if report.index + 1 >= len(sonorities):
                continue
            after = sonorities[report.index + 1]
            for (a, b), value in report.pairs.items():
                if value != kind:
                    continue
                low, high = self._lane_of(a), self._lane_of(b)
                if low == high:
                    continue
                # La dirección la trae el informe: el movimiento se mide
                # contra la nota anterior de cada voz, que en una textura
                # arpegiada no es la de la vertical de al lado --- restando
                # dos verticales, la voz que sostiene salía siempre quieta.
                ways = report.ways.get((a, b), (0, 0))
                # Sobre la vertical de llegada y no sobre la de partida:
                # en una textura arpegiada la voz que sostiene puede estar
                # callada un instante antes de que ataque la otra, y ahí no
                # hay ninguna nota de la que colgar la marca.
                marks.append((after.onset, low, high, ways[0], ways[1],
                              colour))
        self.staff.motions = marks
        self._paint_motion_rows()
        self.staff.redraw()

    def _paint_motion_rows(self) -> None:
        """Marcar cuál de los movimientos está señalado."""
        for kind, row in getattr(self, "_motion_rows", {}).items():
            try:
                row.configure(fg_color=self.colours["surface"]
                              if kind == self._motion_shown else "transparent")
            except tk.TclError:
                pass

    def _finding_row(self, panel, finding) -> None:
        colour = self.colours.get(SEVERITY_KEYS.get(finding.severity, "muted"),
                                  self.colours["muted"])
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=(4, 0))
        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="●", text_color=colour, width=14,
                     font=self.font(("Segoe UI", 12))).pack(side="left")
        ctk.CTkLabel(head, text=tr(finding.label),
                     font=self.font(("Segoe UI Semibold", 12)), anchor="w"
                     ).pack(side="left")
        ctk.CTkLabel(head, text=trf("c. {bar}", bar=finding.bar_index),
                     font=self.font(("Segoe UI", 10)),
                     text_color=self.colours["muted"], anchor="e"
                     ).pack(side="right")
        ctk.CTkLabel(row, text=tr(finding.detail), font=self.font(("Segoe UI", 11)),
                     text_color=self.colours["muted"], wraplength=230,
                     justify="left", anchor="w").pack(fill="x", padx=(18, 4))

    def _render_ornaments(self) -> None:
        panel = self.ornament_panel
        self._wipe(panel)
        result = self.result
        if not result.ornaments:
            self._note(panel, "Ninguna nota se sale del acorde: toda la "
                              "escritura es de notas reales.",
                       self.colours["muted"], 11, (4, 6))
            return
        self._note(panel, trf("{ornaments} adorno(s) melódico(s)",
                              ornaments=len(result.ornaments)),
                   self.colours["muted"], 11, (4, 2), bold=True)
        self._note(panel,
                   "Pasá el mouse por uno y abajo dice qué es; tocalo y se "
                   "marca en el sistema.",
                   self.colours["faint"], 10, (0, 4))
        for ornament in result.ornaments:
            self._ornament_row(panel, ornament)

    def _ornament_row(self, panel, ornament) -> None:
        """
        Un adorno: qué es, en qué compás y en qué tiempo cae.

        Con el tiempo y no sólo con el compás. Un compás de cuatro por
        cuatro tiene dieciséis semicorcheas y decir "compás 3" no alcanza
        para encontrar una: hay que poder ir directo al lugar.
        """
        result = self.result
        beat_quarters = result.score.metrics_at(ornament.bar_index)[1] or 1.0
        beat = ornament.offset / beat_quarters + 1
        row = ctk.CTkFrame(panel, fg_color="transparent", corner_radius=7,
                           cursor="hand2")
        row.pack(fill="x", padx=6, pady=(3, 0))
        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=tr(ornament.label),
                     font=self.font(("Segoe UI Semibold", 12)), anchor="w"
                     ).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(head, text=trf("c.{bar} · t.{beat:g}",
                                    bar=ornament.bar_index, beat=beat),
                     font=self.font(("Segoe UI", 10)),
                     text_color=self.colours["muted"], anchor="e"
                     ).pack(side="right", padx=(0, 4))
        voice = (result.score.parts[ornament.voice].name
                 if ornament.voice < len(result.score.parts) else "")
        ctk.CTkLabel(row, text=f"{voice} · {ornament.detail}",
                     font=self.font(("Segoe UI", 11)),
                     text_color=self.colours["muted"], wraplength=210,
                     justify="left", anchor="w").pack(fill="x", padx=(10, 4))
        definition = analysis.ORNAMENT_DEFINITIONS.get(ornament.kind, "")
        for widget in [row] + _descendants(row):
            self._hover(widget, f"{ornament.label}: {definition}")
            widget.bind("<Button-1>",
                        lambda _e, o=ornament: self._show_ornament(o))

    def _show_ornament(self, ornament) -> None:
        """Marcar en el sistema el momento exacto en el que cae el adorno."""
        length = 0.5
        if ornament.voice < len(self.result.score.parts):
            for note in self.result.score.parts[ornament.voice].notes:
                if abs(note.onset - ornament.onset) < 1e-6:
                    length = note.duration
                    break
        self.staff.highlight = (ornament.onset, ornament.onset + length)
        self.staff.redraw()

    # -- tocar una nota -----------------------------------------------------

    def _hovered(self, hit) -> None:
        """
        Leer la nota que está debajo del mouse.

        Sin tocarla: un click escribe, así que preguntarle a una nota qué es
        tocándola la reemplazaba. Pasar el mouse por encima no cambia nada y
        es lo que uno hace para leer una partitura ajena.
        """
        if hit is None:
            self.picked.configure(text=tr(self._resting),
                                  text_color=self.colours["muted"])
            return
        voice, position = hit
        index, _duration, accidental = self.staff.voices[voice][position]
        if index is None:
            return
        self._picked(voice, position,
                     pitch_at(index, self.staff.fifths, accidental))

    def _picked(self, voice: int, position: int, midi: int) -> None:
        """Contestar qué nota es la que se tocó, y qué hace en su acorde."""
        index, duration, accidental = self.staff.voices[voice][position]
        onset = self.staff.onsets(voice)[position]
        name = spanish_pitch(index, self.staff.fifths, accidental)
        part_name = list(reversed(GRAND_VOICES))[
            min(voice, GRAND_VOICE_COUNT - 1)]
        figure = tr(FIGURE_NAMES.get(duration, trf("{duration:g} negras",
                                                   duration=duration)))
        text = f"{name} · {tr(part_name)} · {figure}"

        if self.result is not None:
            bar, offset = analysis.bar_and_offset(self.result.score, onset)
            beat = offset / (self.result.score.metrics_at(bar)[1] or 1.0) + 1
            text += trf(" · compás {bar}, tiempo {beat:g}", bar=bar, beat=beat)
            segment = next((s for s in self.result.segments
                            if s.start - 1e-6 <= onset < s.end - 1e-6), None)
            if segment is not None and segment.reading is not None:
                role = next((r for pc, r, _s in segment.reading.tones
                             if pc == midi % 12), None)
                if role is not None:
                    text += (trf(" · es {value} de {symbol}",
                                 value=tr(ROLE_NAMES.get(role, role)),
                                 symbol=segment.symbol))
                else:
                    part = self._voice_of(voice)
                    ornament = next(
                        (o for o in self.result.ornaments
                         if o.voice == part and abs(o.onset - onset) < 1e-6),
                        None)
                    text += trf(" · no pertenece a {symbol}",
                                symbol=segment.symbol)
                    if ornament is not None:
                        text += f" — {tr(ornament.label).lower()}"
        # Ya viene traducido por partes: `tr()` sobre el renglón armado no
        # encontraría nunca esa clave, porque la clave sería la frase entera
        # con el nombre de la nota adentro.
        self.picked.configure(text=text, text_color=self.colours["text"])

    # -- escuchar -----------------------------------------------------------

    def written_events(self) -> List[Tuple[int, float, float]]:
        """
        Lo escrito, voz por voz: altura, comienzo y duración.

        Sale del pentagrama y no del análisis. Escuchar lo que uno escribió
        no depende de que se haya podido nombrar un acorde: con dos voces no
        hay análisis, y sin embargo hay música --- y el botón se quedaba
        mudo justo cuando más falta hace oír lo que se está escribiendo.
        """
        events: List[Tuple[int, float, float]] = []
        for line in self.staff.lines():
            position = 0.0
            for pitch, duration in line:
                if pitch is not None and duration > 0:
                    events.append((pitch, position, duration))
                position += duration
        events.sort(key=lambda event: (event[1], event[0]))
        return events

    def _play(self) -> None:
        if self._playing is not None and self._playing.is_alive():
            return
        events = self.written_events()
        if not events:
            messagebox.showinfo(
                tr("Nada que escuchar"),
                tr("Todavía no hay ninguna nota escrita. Poné algunas en el "
                   "sistema o importá una partitura."))
            return
        self.play_button.configure(text=tr("♪  Sonando…"), state="disabled")
        self._playing = audio.play_chords([], [], voices=events)
        if self.on_played is not None:
            self.on_played()
        self._watch_sound()

    def _watch_sound(self) -> None:
        """
        Preguntar desde el hilo principal si el sonido terminó.

        El hilo del sonido no toca Tk: devolver el botón desde ahí sería
        llamar a Tk desde otro hilo, que es lo que el resto del programa
        evita con el mismo rodeo.
        """
        thread = self._playing
        if thread is not None and thread.is_alive():
            self.after(140, self._watch_sound)
            return
        try:
            self.play_button.configure(text=tr("▶  Escuchar"), state="normal")
        except tk.TclError:
            pass

    # -- archivos -----------------------------------------------------------

    def examples_directory(self) -> str:
        """La carpeta de partituras que el programa se trae puestas.

        Es donde el diálogo de importar abre primero: quien nunca exportó
        una partitura de ningún programa se encontraba con un explorador
        vacío y sin nada que probar. Ahí está el preludio de Bach con el que
        se ajustó el analizador."""
        folder = os.path.join(history.program_directory(), "assets",
                              "partituras")
        return folder if os.path.isdir(folder) else ""

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            title="Elegí una partitura",
            initialdir=self.examples_directory() or None,
            filetypes=[("Partituras", "*.musicxml *.xml *.mxl"),
                       ("Todos los archivos", "*.*")])
        if not path:
            return
        try:
            score = importer.read_voices(path)
        except importer.ImportError_ as exc:
            messagebox.showerror(tr("No se pudo importar"), str(exc))
            return
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror(tr("No se pudo importar"),
                                 trf("El archivo no se pudo leer: {exc}",
                                     exc=exc))
            return

        trimmed = max(0, len(score.parts) - MAX_VOICES)
        parts = score.parts[:MAX_VOICES]
        # Cuántas voces hay lo dice la partitura. El compás también, y sus
        # cambios: una pieza que arranca en cuatro por cuatro y pasa a tres
        # se escribía entera en cuatro, y con las barras corridas se corría
        # todo lo que se apoya en ellas.
        self._metres = {1: (score.beats, score.beat_type)}
        for bar, beats, beat_type in score.metres:
            self._metres[max(1, bar)] = (beats, beat_type)
        self.metre_menu.set(f"{score.beats}/{score.beat_type}")
        self.metre_from.delete(0, "end")
        self.metre_from.insert(0, "1")
        label = next((name for name, f in self.key_signatures
                      if f == score.fifths), None)
        if label:
            self.key_menu.set(label)
        self._pickup = score.pickup_quarters
        self.staff.set_key(score.fifths, score.beats, score.beat_type)
        # Las voces se acomodan de grave a aguda contra los carriles del
        # sistema, que es el orden en el que el pentagrama las escribe.
        self.staff.load([importer.written_line(part) for part in parts])
        self._apply_metres()
        self._voice_changed()
        if self.on_imported is not None:
            self.on_imported()
        names = ", ".join(list(reversed(GRAND_VOICES))[:len(parts)])
        message = trf("Se leyeron {parts} voces: {lower}.",
                      parts=len(parts), lower=names.lower())
        if trimmed:
            message += (trf("\n\nLa partitura traía {trimmed} voz/voces más. "
                            "El sistema de dos pentagramas escribe hasta "
                            "cuatro, así que se conservaron las cuatro más "
                            "graves.",
                            trimmed=trimmed))
        messagebox.showinfo(tr("Partitura importada"), message)

    def _export(self) -> None:
        if self.result is None:
            messagebox.showinfo(tr("Nada que exportar"),
                                tr("Escribí o importá una partitura primero."))
            return
        folder = filedialog.askdirectory(
            title="Elegí dónde guardar la partitura")
        if not folder:
            return
        try:
            written = session.export_analysis(self.result, folder,
                                              ("musicxml", "midi"),
                                              "Análisis")
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror(tr("No se pudo exportar"), str(exc))
            return
        if written:
            if self.on_exported is not None:
                self.on_exported()
            messagebox.showinfo(
                tr("Listo"),
                trf("Se guardaron {written} archivos en:\n{dirname}",
                    written=len(written),
                    dirname=os.path.dirname(written[0])))
        else:
            messagebox.showerror(tr("Error"), tr("No se pudo escribir ningún archivo."))


def _descendants(widget) -> List:
    found = []
    try:
        children = widget.winfo_children()
    except Exception:                                       # noqa: BLE001
        return found
    for child in children:
        found.append(child)
        found.extend(_descendants(child))
    return found
